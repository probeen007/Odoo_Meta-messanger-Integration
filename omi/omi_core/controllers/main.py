import hashlib
import hmac
import json
import logging

import requests

from odoo import http
from odoo.http import request, Response
from werkzeug.exceptions import Forbidden

_logger = logging.getLogger(__name__)


class MessengerWebhook(http.Controller):
    @http.route(
        "/webhook/messenger",
        type="http",
        auth="public",
        csrf=False,
        methods=["GET", "POST"],
    )
    def webhook_messenger(self, **kwargs):
        if request.httprequest.method == "GET":
            return self._handle_verification()
        return self._handle_message()

    def _handle_verification(self):
        mode = request.httprequest.args.get("hub.mode")
        verify_token = request.httprequest.args.get("hub.verify_token")
        challenge = request.httprequest.args.get("hub.challenge")

        if not (mode == "subscribe" and verify_token):
            _logger.warning("Messenger webhook verification failed: bad parameters.")
            return Response("Forbidden", status=403, content_type="text/plain")

        # Find the verify token param in ir.config_parameter to avoid search on non-stored fields
        params = request.env["ir.config_parameter"].sudo().search([
            ("key", "like", "messenger.verify_token.%"),
            ("value", "=", verify_token)
        ])
        
        company = None
        for param in params:
            parts = param.key.split(".")
            if len(parts) == 3 and parts[2].isdigit():
                cid = int(parts[2])
                # Check if messenger is active for this company
                if request.env["ir.config_parameter"].sudo().get_param(f"messenger.active.{cid}") == "True":
                    company = request.env["res.company"].sudo().browse(cid)
                    break

        if not company:
            _logger.warning("Messenger webhook verification failed: no matching active company.")
            return Response("Forbidden", status=403, content_type="text/plain")

        _logger.info("Messenger webhook verification succeeded for company: %s", company.name)
        return Response(challenge or "", status=200, content_type="text/plain")

    def _handle_message(self):
        raw_body = request.httprequest.get_data() or b""

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            _logger.exception("Invalid JSON payload in Messenger webhook.")
            return Response("Bad Request", status=400)

        company = self._find_company_for_payload(payload, raw_body)
        if not company:
            _logger.warning("No matching active company found for this payload.")
            raise Forbidden()

        self._process_payload(payload, company)
        return Response("EVENT_RECEIVED", status=200, content_type="text/plain")

    def _find_company_for_payload(self, payload, raw_body):
        # 1. Extract Page ID from payload
        page_id = None
        entries = payload.get("entry") or []
        if entries:
            page_id = entries[0].get("id")
            if not page_id:
                messaging = entries[0].get("messaging") or []
                if messaging:
                    page_id = (messaging[0].get("recipient") or {}).get("id")

        provided_signature = request.httprequest.headers.get("X-Hub-Signature-256", "")
        if not provided_signature:
            _logger.warning("Missing X-Hub-Signature-256 header.")
            raise Forbidden()

        sudo_env = request.env["ir.config_parameter"].sudo()

        # Try to find the company matching this Page ID
        if page_id:
            params = sudo_env.search([
                ("key", "like", "messenger.page_id.%"),
                ("value", "=", str(page_id))
            ])
            for param in params:
                parts = param.key.split(".")
                if len(parts) == 3 and parts[2].isdigit():
                    cid = int(parts[2])
                    if sudo_env.get_param(f"messenger.active.{cid}") == "True":
                        app_secret = sudo_env.get_param(f"messenger.app_secret.{cid}")
                        if app_secret:
                            expected_hash = hmac.new(
                                app_secret.encode("utf-8"),
                                raw_body,
                                digestmod=hashlib.sha256,
                            ).hexdigest()
                            if hmac.compare_digest(f"sha256={expected_hash}", provided_signature):
                                return request.env["res.company"].sudo().browse(cid)

        # Fallback: validate signature against all active companies (backwards compatibility)
        params = sudo_env.search([
            ("key", "like", "messenger.app_secret.%"),
            ("value", "!=", False)
        ])
        for param in params:
            parts = param.key.split(".")
            if len(parts) == 3 and parts[2].isdigit():
                cid = int(parts[2])
                if sudo_env.get_param(f"messenger.active.{cid}") == "True":
                    app_secret = param.value
                    expected_hash = hmac.new(
                        app_secret.encode("utf-8"),
                        raw_body,
                        digestmod=hashlib.sha256,
                    ).hexdigest()
                    if hmac.compare_digest(f"sha256={expected_hash}", provided_signature):
                        return request.env["res.company"].sudo().browse(cid)

        return None

    def _get_messenger_user_name(self, psid, token):
        """Fetch the display name of a Messenger user via the Graph API.
        Returns the real name string, or None if it could not be resolved.
        """
        if not token:
            return None
        try:
            resp = requests.get(
                f"https://graph.facebook.com/v25.0/{psid}",
                params={"fields": "name", "access_token": token},
                timeout=10,
            )
            _logger.info("Graph API name lookup for PSID %s → HTTP %s: %s", psid, resp.status_code, resp.text[:200])
            if resp.ok:
                name = resp.json().get("name")
                if name:
                    return name
        except requests.RequestException:
            _logger.warning("Could not fetch Messenger user name for PSID %s", psid)
        return None

    def _process_payload(self, payload, company):
        if payload.get("object") != "page":
            _logger.info("Ignoring non-page Messenger event payload.")
            return

        token = company.messenger_page_access_token
        # Use company context so all records are created under the correct company
        env = request.env(context=dict(request.env.context, allowed_company_ids=[company.id]))
        channels_env = env["discuss.channel"].sudo()
        root_partner = env.ref("base.partner_root", raise_if_not_found=False)

        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                message_data = event.get("message") or {}
                if message_data.get("is_echo"):
                    continue

                sender_psid = (event.get("sender") or {}).get("id")
                text = message_data.get("text")

                if not sender_psid or not text:
                    continue

                # Find or create res.partner for this Messenger sender
                partner_id_param = f"messenger.partner_psid.{sender_psid}"
                partner_id_str = env["ir.config_parameter"].sudo().get_param(partner_id_param)
                partner = env["res.partner"].sudo().browse(int(partner_id_str)) if (partner_id_str and partner_id_str.isdigit()) else env["res.partner"]

                resolved_name = None
                if not partner:
                    resolved_name = self._get_messenger_user_name(sender_psid, token)
                    partner_name = resolved_name if resolved_name else f"Messenger User: {sender_psid}"
                    partner = env["res.partner"].sudo().create({
                        "name": partner_name,
                        "company_id": company.id,
                    })
                    env["ir.config_parameter"].sudo().set_param(partner_id_param, str(partner.id))
                    _logger.info("Created partner %s (ID %s) for PSID %s", partner.name, partner.id, sender_psid)

                channel = channels_env.search(
                    [("messenger_psid", "=", sender_psid)],
                    limit=1,
                )

                if not channel:
                    admin_group = env.ref("base.group_system", raise_if_not_found=False)
                    if admin_group:
                        # Only add admin users who have access to the target company
                        company_admins = admin_group.sudo().users.filtered(
                            lambda u: company.id in u.company_ids.ids
                        )
                        admin_partners = company_admins.partner_id
                    else:
                        admin_partners = env["res.partner"]

                    if not resolved_name:
                        resolved_name = self._get_messenger_user_name(sender_psid, token)
                    channel_name = f"Messenger: {resolved_name}" if resolved_name else f"Messenger: {sender_psid}"

                    channel = channels_env.with_company(company).create(
                        {
                            "name": channel_name,
                            "channel_type": "group",
                            "messenger_psid": sender_psid,
                            "is_messenger_channel": True,
                        }
                    )
                    # Add admins and the sender partner to the channel members
                    member_partners = admin_partners | partner
                    channel.add_members(partner_ids=member_partners.ids, post_joined_message=False)

                    # Store channel → company association (no DB column needed)
                    request.env["ir.config_parameter"].sudo().set_param(
                        f"messenger.channel_company.{channel.id}", str(company.id)
                    )
                    _logger.info("Created Messenger channel for PSID %s (company: %s, name: %s)", sender_psid, company.name, channel_name)

                else:
                    # If existing channel still has a PSID-based name, try to update it.
                    if channel.name and sender_psid in channel.name:
                        if not resolved_name:
                            resolved_name = self._get_messenger_user_name(sender_psid, token)
                        if resolved_name:
                            channel.sudo().write({"name": f"Messenger: {resolved_name}"})
                            if partner and partner.name == f"Messenger User: {sender_psid}":
                                partner.sudo().write({"name": resolved_name})
                            _logger.info("Updated channel and partner name for PSID %s → %s", sender_psid, resolved_name)

                post_kwargs = {
                    "body": text,
                    "message_type": "comment",
                    "subtype_xmlid": "mail.mt_comment",
                    "author_id": partner.id,
                }

                channel.message_post(**post_kwargs)

