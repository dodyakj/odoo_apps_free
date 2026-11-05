# -*- coding: utf-8 -*-
{
    'name': 'Budget Management for Community: Analytic Budgets, Planned vs Actual & Graph Analysis',
    'version': '20.0.1.0.0',
    'summary': ('Budget management for Odoo Community: analytic budgets per cost centre and GL accounts, '
     'planned vs actual vs theoretical, achievement %, over-budget alerts, pivot and graph '
     'budget analysis.'),
    'description': ('\n'
     'Budget Management for Odoo Community\n'
     '====================================\n'
     'Brings budgets back to Odoo Community, where budgeting is Enterprise-only.\n'
     '\n'
     '* Budgets with Draft, Confirmed, Validated, Done and Cancelled workflow tracked in the '
     'chatter.\n'
     '* Budget lines per analytic account (cost centre / project) and position (group of '
     'general ledger accounts).\n'
     '* Actual amount computed from posted analytic items, theoretical amount prorated by '
     'elapsed days.\n'
     '* Achievement % with red / green decorations and an Over Budget filter.\n'
     '* View Entries drill-down to the exact analytic items behind every actual amount.\n'
     '* List, form, pivot and graph views; Budget Analysis report under Accounting > '
     'Reporting.\n'
     '* Copy a budget to the next period in one click.\n'
     '* Budget User and Budget Manager groups with multi-company access rules.\n'
     '* Daily scheduled action refreshing actual amounts.\n'
     '\n'
     'For accountants, financial controllers and department managers who need planned vs '
     'actual\n'
     'financial control without spreadsheets or Odoo Enterprise.\n'),
    'category': 'Accounting/Accounting',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [   'security/ydod_budget_security.xml',
        'security/ir.access.csv',
        'data/ydod_budget_cron.xml',
        'views/ydod_budget_line_views.xml',
        'views/ydod_budget_views.xml',
        'views/ydod_budget_menus.xml'],
    'demo': ['demo/ydod_budget_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png',
        'static/description/screenshot_5.png',
        'static/description/screenshot_6.png'],
    'installable': True,
    'application': False,
}
