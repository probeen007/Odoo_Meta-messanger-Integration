from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    messenger_page_access_token = fields.Char(
        string="Messenger Page Access Token",
        config_parameter="messenger.page_access_token",
    )
    messenger_app_secret = fields.Char(
        string="Messenger App Secret",
        config_parameter="messenger.app_secret",
    )
    messenger_verify_token = fields.Char(
        string="Messenger Verify Token",
        config_parameter="messenger.verify_token",
    )
