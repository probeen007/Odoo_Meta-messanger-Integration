import logging
import re

import requests

from odoo import api, fields, models
from odoo.addons.mail.tools.discuss import Store

_logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')


def _strip_html(html_str):
    """Strip HTML tags and collapse whitespace to get plain text."""
    if not html_str:
        return ''
    text = _HTML_TAG_RE.sub(' ', str(html_str))
    return _WHITESPACE_RE.sub(' ', text).strip()


def _get_channel_company_param(channel_id):
    """ir.config_parameter key for channel → company association (no DB column needed)."""
    return f"messenger.channel_company.{channel_id}"


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    messenger_psid = fields.Char(index=True, copy=False)
    is_messenger_channel = fields.Boolean(default=False, copy=False)

    _sql_constraints = [
        (
            "messenger_psid_unique",
            "unique(messenger_psid)",
            "Messenger PSID must be unique.",
        )
    ]

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)

        root_partner = self.env.ref("base.partner_root", raise_if_not_found=False)
        root_partner_id = root_partner.id if root_partner else False

        for channel in self:
            if not channel.is_messenger_channel:
                continue

            # Prefer author_id from the created message record (covers UI posts
            # where author_id is not passed explicitly in kwargs but is resolved
            # by Odoo internally inside message_post → _message_compute_author).
            author_id = (
                message.author_id.id
                if message and getattr(message, "author_id", False)
                else kwargs.get("author_id")
            )

            # Skip echoing messages that originated from Facebook (posted by OdooBot/root partner or the customer partner).
            partner_id_str = self.env["ir.config_parameter"].sudo().get_param(
                f"messenger.partner_psid.{channel.messenger_psid}"
            )
            customer_partner_id = int(partner_id_str) if (partner_id_str and partner_id_str.isdigit()) else False

            if (root_partner_id and author_id == root_partner_id) or (customer_partner_id and author_id == customer_partner_id):
                continue

            body_html = kwargs.get("body", "")
            text = _strip_html(body_html or "").strip()

            if not text:
                continue

            channel._send_to_messenger(text)

        return message

    def _send_to_messenger(self, text):
        self.ensure_one()

        if not self.messenger_psid:
            _logger.warning("Skipping outbound Messenger send: channel has no PSID.")
            return

        # Get credentials from the channel's own company
        company_id = self._get_channel_company_id()
        company = self.env["res.company"].browse(company_id)
        if not company.messenger_active:
            _logger.warning("Skipping outbound Messenger send: Messenger not active for company %s.", company.name)
            return

        token = company.messenger_page_access_token
        if not token:
            _logger.error("Skipping outbound Messenger send: page access token missing for company %s.", company.name)
            return

        url = f"https://graph.facebook.com/v25.0/me/messages?access_token={token}"
        payload = {
            "recipient": {"id": self.messenger_psid},
            "messaging_type": "RESPONSE",
            "message": {"text": text},
        }

        try:
            response = requests.post(url, json=payload, timeout=15)
            _logger.info(
                "Messenger send result — channel %s, PSID %s, HTTP %s",
                self.id, self.messenger_psid, response.status_code,
            )
            response.raise_for_status()
        except requests.RequestException:
            _logger.exception(
                "Failed to send Messenger message for channel %s (PSID: %s).",
                self.id,
                self.messenger_psid,
            )

    def _get_channel_company_id(self):
        """Return the company ID that owns this Messenger channel.
        Stored in ir.config_parameter to avoid any DB schema change.
        Falls back to the first Messenger-active company if not found.
        """
        self.ensure_one()
        val = self.env["ir.config_parameter"].sudo().get_param(
            _get_channel_company_param(self.id)
        )
        if val and val.isdigit():
            return int(val)
        # Fallback: return first active company
        companies = self.env["res.company"].sudo().search([])
        active = companies.filtered(lambda c: c.messenger_active)
        return active[0].id if active else self.env.company.id

    @api.model
    def get_messenger_sidebar_threads(self, *args, **kwargs):
        """Return serialized store data for Messenger channels belonging to the current company."""
        current_company = self.env.company
        is_active = bool(current_company.messenger_active)

        # If Messenger is not active for this company, return empty store data.
        if not is_active:
            return {
                "is_active": False,
                "store_data": Store().get_result(),
            }

        cid = current_company.id
        get = self.env["ir.config_parameter"].sudo().get_param

        all_channels = self.search(
            [("is_messenger_channel", "=", True)],
            order="write_date desc, id desc",
        )

        # Keep only channels associated with the current company.
        channels = all_channels.filtered(
            lambda c: get(_get_channel_company_param(c.id), str(cid)) == str(cid)
        )

        return {
            "is_active": True,
            "store_data": Store(channels).get_result(),
        }

    def _channel_basic_info(self):
        self.ensure_one()
        data = super()._channel_basic_info()
        data["is_messenger_channel"] = self.is_messenger_channel
        if self.is_messenger_channel:
            data["messenger_company_id"] = self._get_channel_company_id()
            data["messenger_psid"] = self.messenger_psid
            last_messages = self.message_ids.sorted(lambda m: m.id, reverse=True)
            last_message = last_messages[0] if last_messages else False
            preview = ""
            if last_message and last_message.body:
                preview = _strip_html(last_message.body or "").strip()
            data["preview"] = preview
        return data

    def _bus_send_store(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], Store):
            store = args[0]
            for channel in self:
                if channel.is_messenger_channel:
                    store.add(channel, {
                        "is_messenger_channel": True,
                        "messenger_company_id": channel._get_channel_company_id(),
                        "messenger_psid": channel.messenger_psid,
                    })
        else:
            new_args = list(args)
            for i, arg in enumerate(new_args):
                if isinstance(arg, dict):
                    if self.is_messenger_channel:
                        arg["is_messenger_channel"] = True
                        arg["messenger_company_id"] = self._get_channel_company_id()
                        arg["messenger_psid"] = self.messenger_psid
            args = tuple(new_args)

            if "values" in kwargs and isinstance(kwargs["values"], dict):
                if self.is_messenger_channel:
                    kwargs["values"]["is_messenger_channel"] = True
                    kwargs["values"]["messenger_company_id"] = self._get_channel_company_id()
                    kwargs["values"]["messenger_psid"] = self.messenger_psid

        return super()._bus_send_store(*args, **kwargs)

    def _to_store(self, store: Store):
        res = super()._to_store(store)
        for channel in self:
            if channel.is_messenger_channel:
                company_id = channel._get_channel_company_id()
                last_messages = channel.message_ids.sorted(lambda m: m.id, reverse=True)
                last_message = last_messages[0] if last_messages else False
                preview = ""
                if last_message and last_message.body:
                    preview = _strip_html(last_message.body or "").strip()
                store.add(channel, {
                    "is_messenger_channel": True,
                    "messenger_company_id": company_id,
                    "preview": preview,
                })
        return res