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

        expected_token = (
            request.env["ir.config_parameter"].sudo().get_param("messenger.verify_token")
        )

        if mode == "subscribe" and verify_token and verify_token == expected_token:
            _logger.info("Messenger webhook verification succeeded.")
            return Response(challenge or "", status=200, content_type="text/plain")

        _logger.warning("Messenger webhook verification failed.")
        return Response("Forbidden", status=403, content_type="text/plain")

    def _handle_message(self):
        raw_body = request.httprequest.get_data() or b""

        self._validate_signature(raw_body)

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            _logger.exception("Invalid JSON payload in Messenger webhook.")
            return Response("Bad Request", status=400)

        self._process_payload(payload)
        return Response("EVENT_RECEIVED", status=200, content_type="text/plain")

    def _validate_signature(self, raw_body):
        provided_signature = request.httprequest.headers.get("X-Hub-Signature-256", "")
        if not provided_signature:
            _logger.warning("Missing X-Hub-Signature-256 header.")
            raise Forbidden()

        app_secret = request.env["ir.config_parameter"].sudo().get_param("messenger.app_secret")
        if not app_secret:
            _logger.error("Messenger app secret is not configured.")
            raise Forbidden()

        expected_hash = hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        expected_signature = f"sha256={expected_hash}"

        if not hmac.compare_digest(expected_signature, provided_signature):
            _logger.warning("Invalid Messenger webhook signature.")
            raise Forbidden()

    def _get_messenger_user_name(self, psid, token):
        """Fetch the display name of a Messenger user via the Graph API.
        Returns the real name string, or None if it could not be resolved.
        """
        if not token:
            return None
        try:
            resp = requests.get(
                f"https://graph.facebook.com/v21.0/{psid}",
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

    def _process_payload(self, payload):
        if payload.get("object") != "page":
            _logger.info("Ignoring non-page Messenger event payload.")
            return

        channels_env = request.env["discuss.channel"].sudo()
        root_partner = request.env.ref("base.partner_root", raise_if_not_found=False)
        token = request.env["ir.config_parameter"].sudo().get_param("messenger.page_access_token")

        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                message_data = event.get("message") or {}
                if message_data.get("is_echo"):
                    continue

                sender_psid = (event.get("sender") or {}).get("id")
                text = message_data.get("text")

                if not sender_psid or not text:
                    continue

                channel = channels_env.search(
                    [("messenger_psid", "=", sender_psid)],
                    limit=1,
                )

                if not channel:
                    admin_group = request.env.ref("base.group_system", raise_if_not_found=False)
                    admin_partners = admin_group.sudo().users.partner_id if admin_group else request.env["res.partner"]

                    # Resolve real name from Meta Graph API
                    resolved_name = self._get_messenger_user_name(sender_psid, token)
                    channel_name = f"Messenger: {resolved_name}" if resolved_name else f"Messenger: {sender_psid}"

                    channel = channels_env.create(
                        {
                            "name": channel_name,
                            "channel_type": "chat",
                            "messenger_psid": sender_psid,
                            "is_messenger_channel": True,
                        }
                    )
                    if admin_partners:
                        channel.add_members(partner_ids=admin_partners.ids, post_joined_message=False)
                    _logger.info("Created Messenger channel for PSID %s (name: %s)", sender_psid, channel_name)

                else:
                    # If existing channel still has a PSID-based name, try to update it.
                    if channel.name and sender_psid in channel.name:
                        resolved_name = self._get_messenger_user_name(sender_psid, token)
                        if resolved_name:
                            channel.sudo().write({"name": f"Messenger: {resolved_name}"})
                            _logger.info("Updated channel name for PSID %s → %s", sender_psid, resolved_name)

                post_kwargs = {
                    "body": text,
                    "message_type": "comment",
                    "subtype_xmlid": "mail.mt_comment",
                }
                if root_partner:
                    post_kwargs["author_id"] = root_partner.id

                channel.message_post(**post_kwargs)

