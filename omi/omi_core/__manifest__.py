{
    "name": "Meta Messenger Discuss Integration",
    "summary": "Handle Facebook Messenger chats directly from Odoo Discuss",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "author": "Your Company",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "omi_core/static/src/discuss/messenger_sidebar/messenger_sidebar.js",
            "omi_core/static/src/discuss/messenger_sidebar/messenger_sidebar.xml",
            "omi_core/static/src/discuss/messenger_sidebar/messenger_sidebar.scss",
        ],
    },
    "installable": True,
    "application": False,
    "external_dependencies": {
        "python": ["requests", "cryptography"],
    },
}
