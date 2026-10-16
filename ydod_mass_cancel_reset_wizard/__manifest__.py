# -*- coding: utf-8 -*-
{
    'name': 'Mass Document Cancel & Reset to Draft Wizard',
    'version': '20.0.1.0.0',
    'summary': ('Allows managers to cancel and reset multiple Sales Orders, Purchase Orders, Invoices, '
     'and Stock Transfers at once from list views with a mandatory cancellation reason logged '
     'into the chatter.'),
    'description': ('Allows managers to cancel and reset multiple Sales Orders, Purchase Orders, Invoices, '
     'and Stock Transfers at once from list views with a mandatory cancellation reason logged '
     'into the chatter.'),
    'category': 'Productivity',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['sale', 'purchase', 'account', 'stock', 'mail'],
    'data': [   'security/security.xml',
        'security/ir.access.csv',
        'wizard/mass_cancel_wizard_views.xml',
        'views/server_actions.xml'],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
