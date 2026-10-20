# -*- coding: utf-8 -*-
{
    'name': 'Chatter Quick Replies & Canned Responses',
    'version': '20.0.1.0.0',
    'summary': 'Create and insert pre-defined text templates into the chatter and email composer.',
    'description': ('Chatter Quick Replies & Canned Responses\n'
     '========================================\n'
     'Boost productivity across your team with reusable text snippets and canned responses.\n'
     'Organize replies by category, keep personal shortcuts or share team-wide standard '
     'templates.\n'
     '\n'
     'Key Features:\n'
     '-------------\n'
     '* Reusable snippet library for common greetings, inquiries, and troubleshooting steps\n'
     '* Personal vs Global replies for custom workflows or standardized team answers\n'
     '* Category organization to keep messages structured and easy to find\n'
     '* Rich text HTML support for formatted templates\n'
     '* Clean search and management interface\n'),
    'category': 'Productivity',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['mail'],
    'data': ['security/ir.access.csv', 'views/mail_quick_reply_views.xml', 'views/menus.xml'],
    'demo': ['data/mail_quick_reply_demo.xml'],
    'images': [   'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png'],
    'installable': True,
    'application': True,
}
