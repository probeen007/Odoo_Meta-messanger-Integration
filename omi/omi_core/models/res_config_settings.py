from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    messenger_active = fields.Boolean(
        string="Enable Meta Messenger Integration",
        related="company_id.messenger_active",
        readonly=False,
    )
    messenger_page_access_token = fields.Char(
        string="Messenger Page Access Token",
        related="company_id.messenger_page_access_token",
        readonly=False,
    )
    messenger_app_secret = fields.Char(
        string="Messenger App Secret",
        related="company_id.messenger_app_secret",
        readonly=False,
    )
    messenger_verify_token = fields.Char(
        string="Messenger Verify Token",
        related="company_id.messenger_verify_token",
        readonly=False,
    )
    messenger_page_id = fields.Char(
        string="Messenger Page ID",
        related="company_id.messenger_page_id",
        readonly=False,
    )

