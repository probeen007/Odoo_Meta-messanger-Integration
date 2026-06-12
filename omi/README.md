# Meta Messenger Discuss Integration (OMI)

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL_3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-purple.svg)](https://www.odoo.com)

A premium Odoo 18.0 module that integrates Facebook Messenger directly into Odoo's native **Discuss** application. Chat with customers on Facebook Messenger without leaving your Odoo dashboard.

---

## Features

- **Real-Time Synchronization**: Two-way real-time messaging between Facebook Messenger and Odoo.
- **Native Discuss Integration**: Automatically creates `discuss.channel` threads for incoming chats.
- **Discuss Sidebar Category**: Registers a dedicated "Messenger" section in the Discuss sidebar.
- **Auto-Join for Admins**: Automatically adds active system administrators to incoming Messenger channels to ensure immediate visibility.
- **Secure Webhooks**: Implements secure, SHA-256 HMAC signature validation for all incoming Meta API payloads.
- **Outbound Message Tags**: Uses Meta's `HUMAN_AGENT` tag to safely send agent replies to users.

---

## Prerequisites

Ensure your Python environment contains the required external dependencies:

```bash
pip install requests cryptography
```

---

## Installation & Setup

### 1. Install the Module
1. Copy the `omi_core` directory to your Odoo custom addons path.
2. Update your Odoo module list:
   - Activate **Developer Mode** in Odoo.
   - Navigate to **Apps** -> Click **Update Apps List**.
3. Search for **Meta Messenger Discuss Integration** (`omi_core`) and click **Activate**.

### 2. Configure Meta Credentials
1. Go to **Settings** -> **General Settings** -> **Discuss**.
2. Scroll to the **Meta Messenger Integration** section:
   - **Page Access Token**: Paste your Facebook Page Access Token.
   - **App Secret**: Paste your Facebook Developer App Secret (used for verifying incoming webhook signatures).
   - **Verification Token**: Define a secure verification token (e.g. `meta_messenger_verify_token_2026`).

### 3. Expose Your Webhook
Meta requires an `HTTPS` endpoint to send webhooks. You can use Cloudflare Tunnel or any reverse proxy to expose your local port `8069`:
- **Callback URL**: `https://your-domain.com/webhook/messenger`
- **Verify Token**: Must match the **Verification Token** configured in Odoo.

---

##  Testing the Webhook Locally

You can simulate a Facebook Messenger webhook message using `curl`:

```bash
curl -X POST http://localhost:8069/webhook/messenger \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=GENERATE_HMAC_SHA256_SIGNATURE_HERE" \
  -d '{
    "object": "page",
    "entry": [
      {
        "id": "YOUR_PAGE_ID",
        "time": 1718456099000,
        "messaging": [
          {
            "sender": {"id": "TEST_USER_PSID"},
            "recipient": {"id": "YOUR_PAGE_ID"},
            "timestamp": 1718456099000,
            "message": {
              "mid": "mid.test_message_1",
              "text": "Hello, this is a test message!"
            }
          }
        ]
      }
    ]
  }'
```

---

##  License & Credits

This project is licensed under the LGPL-3 License. See the [LICENSE](LICENSE) file for details.

