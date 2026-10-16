# -*- coding: utf-8 -*-
{
    'name': 'Customer Invoice Overdue Aging Summary & Dunning Alerts',
    'version': '20.0.1.0.0',
    'summary': ('Provides real-time customer invoice aging buckets, credit limit warnings on invoice '
     'validation, and automated daily alerts for sales reps on overdue accounts.'),
    'category': 'Invoicing',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [   'security/ir.access.csv',
        'data/cron_data.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml'],
    'demo': ['data/demo_data.xml'],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
}
