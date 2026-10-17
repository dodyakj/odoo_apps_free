# -*- coding: utf-8 -*-
{
    'name': 'yDoD Accounting Community',
    'version': '16.0.1.0.0',
    'summary': ('Transforms Odoo Community Invoicing into a full-featured Accounting application with '
     'dedicated menus, advisor rights, fiscal year closing, journal items reconciliation, and '
     'financial dashboards.'),
    'description': ('\n'
     'yDoD Accounting Community\n'
     '=========================\n'
     'Transform Odoo 16.0 Community Invoicing into a professional, enterprise-grade accounting '
     'application.\n'
     '\n'
     'Key Features:\n'
     '-------------\n'
     '* **Complete Accounting Menus**: Unlocks top-level Accounting menus (Journal Entries, '
     'Journal Items, Manual Reconciliation, Reporting, and Configuration) directly in Odoo '
     'Community.\n'
     '* **Fiscal Year & Period Closing**: Configure custom fiscal years with strict boundary '
     'constraints and automated year-end closing journal entry creation.\n'
     '* **Retained Earnings Automation**: One-click P&L account balance clearance to '
     'accumulated earnings upon period close.\n'
     '* **Bank Reconciliation Statement**: Audit wizard comparing physical bank statement '
     'balances with general ledger book balances and in-transit uncleared payments.\n'
     '* **Journal Items Fast Reconciliation**: Fast-track manual reconciliation tool on move '
     'lines for quick matching and verification.\n'
     '* **Multi-Company Security**: Built-in multi-company isolation rules ensuring complete '
     'privacy across legal entities.\n'
     '* **QWeb Audit Reports**: Ready-to-print Bank Reconciliation Statement and Fiscal Year '
     'Closing Summary PDF reports.\n'
     '\n'
     'Keywords: odoo community accounting, fiscal year closing, bank reconciliation statement, '
     'journal items reconciliation, odoo 16 accounting, financial year period closing, '
     'retained earnings automation, accountant advisor menus.\n'),
    'category': 'Accounting',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['account', 'mail'],
    'data': [   'security/account_fiscal_year_security.xml',
        'security/ir.model.access.csv',
        'report/report_actions.xml',
        'report/report_bank_reconcile_statement.xml',
        'report/report_fiscal_year_closing.xml',
        'views/account_bank_reconcile_statement_views.xml',
        'views/account_fiscal_year_views.xml',
        'views/account_move_line_views.xml',
        'views/account_journal_views.xml',
        'views/accounting_menus.xml'],
    'demo': ['demo/account_fiscal_year_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png'],
    'installable': True,
    'application': True,
}
