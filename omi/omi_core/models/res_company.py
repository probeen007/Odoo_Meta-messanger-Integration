import logging
import requests
from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    messenger_active = fields.Boolean(
        string="Enable Meta Messenger Integration",
        compute="_compute_messenger_fields",
        inverse="_inverse_messenger_fields",
        store=False,
    )
    messenger_page_access_token = fields.Char(
        string="Messenger Page Access Token",
        compute="_compute_messenger_fields",
        inverse="_inverse_messenger_fields",
        store=False,
        groups="base.group_system",
    )
    messenger_app_secret = fields.Char(
        string="Messenger App Secret",
        compute="_compute_messenger_fields",
        inverse="_inverse_messenger_fields",
        store=False,
        groups="base.group_system",
    )
    messenger_verify_token = fields.Char(
        string="Messenger Verify Token",
        compute="_compute_messenger_fields",
        inverse="_inverse_messenger_fields",
        store=False,
        groups="base.group_system",
    )
    messenger_page_id = fields.Char(
        string="Messenger Page ID",
        compute="_compute_messenger_fields",
        inverse="_inverse_messenger_fields",
        store=False,
        groups="base.group_system",
    )

    def _compute_messenger_fields(self):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        for company in self:
            company.messenger_active = get_param(f"messenger.active.{company.id}") == "True"
            company.messenger_page_access_token = get_param(f"messenger.page_access_token.{company.id}") or ""
            company.messenger_app_secret = get_param(f"messenger.app_secret.{company.id}") or ""
            company.messenger_verify_token = get_param(f"messenger.verify_token.{company.id}") or ""
            company.messenger_page_id = get_param(f"messenger.page_id.{company.id}") or ""

    def _inverse_messenger_fields(self):
        set_param = self.env["ir.config_parameter"].sudo().set_param
        for company in self:
            set_param(f"messenger.active.{company.id}", str(company.messenger_active))
            set_param(f"messenger.page_access_token.{company.id}", company.messenger_page_access_token or "")
            set_param(f"messenger.app_secret.{company.id}", company.messenger_app_secret or "")
            set_param(f"messenger.verify_token.{company.id}", company.messenger_verify_token or "")
            set_param(f"messenger.page_id.{company.id}", company.messenger_page_id or "")

            # Dynamically fetch and store Facebook Page ID automatically if token changes
            token = company.messenger_page_access_token
            if token:
                try:
                    resp = requests.get(
                        "https://graph.facebook.com/v25.0/me",
                        params={"fields": "id", "access_token": token},
                        timeout=5
                    )
                    if resp.ok:
                        page_id = resp.json().get("id")
                        if page_id:
                            set_param(f"messenger.page_id.{company.id}", str(page_id))
                            _logger.info("Facebook Page ID automatically resolved: %s for company %s", page_id, company.name)
                except Exception:
                    _logger.warning("Could not dynamically resolve Facebook Page ID during config save for company %s", company.name)
