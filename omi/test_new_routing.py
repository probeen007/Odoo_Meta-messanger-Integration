import sys
sys.path.append(r"d:\Professional\odoo\odoo-src")
import odoo
import requests
import json
import hmac
import hashlib

DB_NAME = "odoo18_dev"
odoo.tools.config.parse_config(["-c", r"d:\Professional\odoo\odoo.conf"])
registry = odoo.registry(DB_NAME)

# 1. Setup Page ID mapping in DB
print("Configuring Page ID mapping in Odoo database...")
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    # Set page ID for company 1
    env["ir.config_parameter"].sudo().set_param("messenger.page_id.1", "1093861113817654")
    
    # Delete test channels to ensure a fresh webhook run
    channels = env["discuss.channel"].search([("messenger_psid", "in", ["27159895853670527"])])
    if channels:
        channels.unlink()
    cr.commit()

# 2. Simulate Webhook message from Harry Doe (PSID 27159895853670527) to Page 1093861113817654
app_secret = "3487af711ab114e37743aba11ab56a03"

payload = {
    "object": "page",
    "entry": [
        {
            "id": "1093861113817654",
            "time": 1718100000000,
            "messaging": [
                {
                    "sender": {"id": "27159895853670527"},
                    "recipient": {"id": "1093861113817654"},
                    "timestamp": 1718100000000,
                    "message": {
                        "mid": "mid.newrouting123",
                        "text": "Checking if page-based multi-company routing works!"
                    }
                }
            ]
        }
    ]
}

body = json.dumps(payload).encode("utf-8")
signature = "sha256=" + hmac.new(
    app_secret.encode("utf-8"),
    body,
    digestmod=hashlib.sha256
).hexdigest()

headers = {
    "Content-Type": "application/json",
    "X-Hub-Signature-256": signature
}

url = "http://localhost:8069/webhook/messenger"
resp = requests.post(url, data=body, headers=headers)
print("Response status:", resp.status_code)
print("Response text:", resp.text)

# 3. Query DB to verify created channel name, company association, and members
print("Verifying created channel in database...")
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    channel = env["discuss.channel"].search([("messenger_psid", "=", "27159895853670527")], limit=1)
    if channel:
        print("--- Verification Succeeded! ---")
        print("Channel ID:", channel.id)
        print("Channel Name:", channel.name)
        print("Company ID:", channel._get_channel_company_id())
    else:
        print("--- Verification Failed: Channel not found! ---")
