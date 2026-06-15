import logging
import re

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')


def _strip_html(html_str):
    """Strip HTML tags and collapse whitespace to get plain text."""
    if not html_str:
        return ''
    text = _HTML_TAG_RE.sub(' ', str(html_str))
    return _WHITESPACE_RE.sub(' ', text).strip()



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

            # Skip echoing messages that originated from Facebook (posted by OdooBot/root partner).
            if root_partner_id and author_id == root_partner_id:
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

        token = self.env["ir.config_parameter"].sudo().get_param("messenger.page_access_token")
        if not token:
            _logger.error("Skipping outbound Messenger send: page access token is missing.")
            return

        url = f"https://graph.facebook.com/v21.0/me/messages?access_token={token}"
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


    def get_messenger_sidebar_threads(self):
        channels = self.search(
            [("is_messenger_channel", "=", True)],
            order="write_date desc, id desc",
        )
        result = []
        for channel in channels:
            last_message = channel.message_ids[-1] if channel.message_ids else False
            preview = ""
            if last_message and last_message.body:
                preview = _strip_html(last_message.body or "").strip()
            result.append(
                {
                    "id": channel.id,
                    "name": channel.display_name or channel.name or f"Messenger: {channel.messenger_psid}",
                    "psid": channel.messenger_psid,
                    "preview": preview,
                    "unread_count": channel.message_needaction_counter or 0,
                    "last_date": str(channel.last_interest_dt) if channel.last_interest_dt else False,
                }
            )
        return result