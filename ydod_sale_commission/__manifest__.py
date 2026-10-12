# -*- coding: utf-8 -*-
{
    'name': 'Sales Commission Management',
    'version': '19.0.1.0.0',
    'summary': ('Automatically calculate salesperson/team commissions on confirmed sale orders with '
     'configurable plans and a payout report.'),
    'description': ('\n'
     'Sales Commission Management\n'
     '============================\n'
     'Stop tracking sales commissions in spreadsheets.\n'
     '\n'
     '* Define commission plans with a percentage rate, scoped to a salesperson, a sales team, '
     'or a company-wide default.\n'
     '* Commission lines are automatically generated when a sale order is confirmed, based on '
     "the order's untaxed total and the applicable plan rate.\n"
     '* Every commission line keeps a reference, the salesperson, base amount, rate, computed '
     'commission, and a lock/paid status for a full audit trail.\n'
     '* Review total commissions per salesperson, team, and period with dedicated list and '
     'pivot views, filterable by date range and paid status.\n'
     '* Lock or manually override a computed commission line whenever an adjustment is '
     'needed.\n'
     '    '),
    'category': 'Sales/Sales',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['sale_management'],
    'data': [   'security/ir.model.access.csv',
        'security/sale_commission_security.xml',
        'data/ir_sequence_data.xml',
        'views/sale_commission_plan_views.xml',
        'views/sale_commission_line_views.xml',
        'views/sale_order_views.xml',
        'views/sale_commission_menus.xml'],
    'demo': ['demo/sale_commission_demo.xml'],
    'images': [   'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png'],
    'installable': True,
    'application': False,
}
