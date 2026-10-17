# -*- coding: utf-8 -*-
{
    'name': 'Recurring Invoices & Subscriptions for Community',
    'version': '18.0.1.0.0',
    'summary': ('Automate recurring customer invoices and vendor bills on flexible schedules (weekly, '
     'monthly, quarterly, annual) with auto-post and email options, bringing subscription '
     'billing to Odoo Community.'),
    'description': ('\n'
     'Recurring Invoices & Subscriptions for Odoo 18.0 Community\n'
     '==========================================================\n'
     'Streamline repeat billing and automate subscription revenue without Enterprise '
     'editions.\n'
     '\n'
     'Key Features:\n'
     '-------------\n'
     '* Flexible Recurrence Frequencies: Daily, weekly, monthly, quarterly, and annual billing '
     'intervals.\n'
     '* Dual Direction Support: Handles both Customer Invoices (sales/subscriptions) and '
     'Vendor Bills (recurring expenses/utilities).\n'
     '* Auto-Post & Auto-Email: Automatically post invoices on due date and send them directly '
     'to clients by email.\n'
     '* Full Invoicing History: Direct bidirectional link between recurring profiles and '
     'generated invoices with cumulative revenue tracking.\n'
     '* 1-Click Convert: Turn any confirmed customer invoice or vendor bill into a recurring '
     'profile instantly.\n'
     '* Manual Execution: Ad-hoc "Generate Invoice Now" button for instant on-demand billing '
     'ahead of cron schedule.\n'
     '* Configurable Expiry: Run indefinitely, stop at a specific date, or end after a fixed '
     'count of billing cycles.\n'
     '    '),
    'category': 'Accounting/Invoicing',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [   'security/account_recurring_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/account_recurring_invoice_views.xml',
        'views/account_move_views.xml',
        'views/account_recurring_menu.xml'],
    'demo': ['demo/account_recurring_demo.xml'],
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
