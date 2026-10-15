# -*- coding: utf-8 -*-
{
    'name': 'Auto Lock Accounting Period & Role-Based Bypass',
    'version': '19.0.1.0.0',
    'summary': ('Automate monthly accounting period locking on a set schedule, audit lock date changes, '
     'and allow authorized managers to bypass lock dates without opening periods to everyone.'),
    'description': ('\n'
     'Auto Lock Accounting Period & Role-Based Bypass\n'
     '================================================\n'
     'Automates monthly accounting lock dates on a configurable closing schedule, logs every\n'
     'lock date change in a comprehensive audit trail and chatter, and provides role-based\n'
     'bypass capabilities for Chief Accountants and Financial Controllers to post backdated\n'
     'entries without opening periods to all users.\n'
     '\n'
     'Key Features:\n'
     '-------------\n'
     '* Scheduled Auto-Lock: Automatically advances sales, purchase, tax, and fiscal lock\n'
     '  dates to the end of the previous month on a designated closing day (e.g. 10th of every '
     'month).\n'
     '* Role-Based Lock Bypass: Dedicated security group allowing authorized managers to '
     'post,\n'
     '  edit, or adjust entries in locked periods without lifting lock dates for other users.\n'
     '* Audit Trail & History: Records all lock date transitions with user, timestamp, prior\n'
     '  date, new date, trigger source, and reason.\n'
     '* Real-Time Chatter Logging: Changes are recorded directly in the company chatter for\n'
     '  full transparency.\n'
     '* Flexible Lock Targets: Choose whether to lock sales, purchases, tax returns, global\n'
     '  fiscal year, or custom combinations.\n'
     '* Manual Run & Validation: One-click test execution directly from Invoicing/Accounting\n'
     '  settings with safety checks against bank reconciliations.\n'
     '    '),
    'category': 'Accounting',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [   'security/account_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/account_lock_date_audit_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_menuitem.xml'],
    'demo': ['demo/account_lock_date_audit_demo.xml'],
    'images': [   'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png'],
    'installable': True,
    'application': False,
}
