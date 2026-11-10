# -*- coding: utf-8 -*-
{
    'name': ('OpenWA Connector Core: Self-Hosted WhatsApp Sessions, QR Pairing, Discuss Inbox & Signed '
     'Webhooks'),
    'version': '20.0.1.0.0',
    'summary': ('Send and receive WhatsApp messages from Odoo Community through your self-hosted OpenWA '
     '(whatsapp-web.js / Baileys) server: QR pairing, Send WhatsApp from contacts, replies in '
     'Discuss, HMAC-signed webhooks, delivery/read log, opt-in and anti-ban pacing.'),
    'description': ('\n'
     'OpenWA Connector Core\n'
     '=====================\n'
     'Connect Odoo Community to a self-hosted OpenWA WhatsApp gateway (whatsapp-web.js / '
     'Baileys)\n'
     'without the paid, Meta-verified WhatsApp Business API.\n'
     '\n'
     '* Connection settings: OpenWA base URL, X-API-Key, webhook HMAC secret, timeout, country '
     'code,\n'
     '  default session and a Test Connection button.\n'
     '* WhatsApp sessions: create on server, start, stop, refresh, scan the pairing QR code in '
     'Odoo.\n'
     '* Send WhatsApp wizard on contacts and on any record linked to a partner: text and '
     'attachments,\n'
     '  phone numbers normalised to 62xxx@c.us.\n'
     '* Incoming WhatsApp messages land in Discuss conversations of the users assigned to the '
     'session\n'
     '  number; replying in Discuss sends the answer back over WhatsApp.\n'
     '* HMAC-SHA256 signed webhook for message.received, delivery / read statuses and session '
     'status.\n'
     '* Message log with direction, status, sent / delivered / read timestamps and errors.\n'
     '* Anti-ban safeguards: dedicated number confirmation, opt-in, minimum delay and hourly '
     'cap.\n'
     '* Python service send_message() for other modules (e.g. ydod_notify_gateway) and server '
     'actions.\n'),
    'category': 'Productivity/Discuss',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web'],
    'data': [   'security/groups.xml',
        'security/ir.access.csv',
        'wizard/openwa_send_wizard_views.xml',
        'views/openwa_session_views.xml',
        'views/openwa_message_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml'],
    'demo': ['demo/openwa_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png',
        'static/description/screenshot_5.png'],
    'installable': True,
    'application': True,
}
