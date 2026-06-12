import odoo
from odoo import api, SUPERUSER_ID

DB_NAME = 'odoo18_dev'

odoo.tools.config.parse_config([
    '-c', r'd:\Professional\odoo\odoo.conf',
    r'--addons-path=d:\Professional\odoo\odoo-src\addons,d:\Professional\odoo,d:\Professional\odoo 2\omi'
])

with odoo.registry(DB_NAME).cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    params = env['ir.config_parameter'].sudo().search([('key', 'like', 'messenger.%')])
    for param in params:
        print(f"Key: {param.key}, Value: {param.value}")
