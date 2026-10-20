# -*- coding: utf-8 -*-
{
    'name': 'Accounting Community',
    'version': '16.0.1.1.0',
    'summary': ('Full-featured Accounting suite for Odoo 16 Community: Balance Sheet, Profit & Loss, '
     'Trial Balance, General Ledger, Aged Balances, Cash Flow, Fixed Asset Depreciation, '
     'Analytic Budgets, Bank Reconciliation with Smart Matching, Payment Follow-up, '
     'Multi-level Approval, and Fiscal Year Closing.'),
    'description': ('\n'
     'yDoD Accounting Community\n'
     '=========================\n'
     'Transform Odoo 16.0 Community Invoicing into a complete, enterprise-grade accounting and '
     'financial management suite.\n'
     '\n'
     'Key Highlights & Features:\n'
     '--------------------------\n'
     '* **Comprehensive Financial Statements**:\n'
     '  - Balance Sheet (Neraca) with period comparison and unallocated earnings calculation.\n'
     '  - Profit and Loss (Laba Rugi) with side-by-side comparative period analysis and '
     'variance metrics.\n'
     '  - Trial Balance (Neraca Saldo) detailing opening balances, period debit/credit '
     'movements, and ending balances.\n'
     '  - General Ledger and Partner Ledger tracking complete audit trails.\n'
     '  - Aged Receivable and Aged Payable reports (Current, 1-30, 31-60, 61-90, 91-120, 120+ '
     'days).\n'
     '  - Cash Flow Statement (Laporan Arus Kas) monitoring operating inflows and '
     'disbursements.\n'
     '  - One-click export to Excel / CSV and publication-ready QWeb PDF reports.\n'
     '\n'
     '* **Fixed Asset Management & Automated Depreciation**:\n'
     '  - Full asset lifecycle tracking: Acquisition, depreciation board scheduling, pausing, '
     'and disposal.\n'
     '  - Automatic straight-line monthly and annual depreciation board computation.\n'
     '  - Single-click and automated posting of due depreciation journal entries.\n'
     '\n'
     '* **Budget vs Realization per Analytic Account**:\n'
     '  - Plan financial targets across financial and analytic accounts.\n'
     '  - Real-time aggregation of practical actual amounts via general ledger and analytic '
     'lines.\n'
     '  - Visual achievement progress bars and variance tracking.\n'
     '\n'
     '* **Smart Bank Reconciliation & Auto-Matching**:\n'
     '  - Audit wizard reconciling physical bank statements against general ledger balances '
     'and in-transit items.\n'
     '  - Smart pattern matching suggesting counterpart unreconciled move lines.\n'
     '  - Manual journal item matching tool with automated write-off posting for '
     'reconciliation discrepancies.\n'
     '\n'
     '* **Multi-Level Approval Workflow**:\n'
     '  - Two-stage validation on journal entries and customer/vendor documents.\n'
     '  - Dedicated submit, approve, and reject actions with automated chatter audit logs and '
     'mail activities.\n'
     '\n'
     '* **Automated Customer Payment Follow-Up**:\n'
     '  - Identify overdue accounts receivable balances.\n'
     '  - Automatic email notification dispatch and automated scheduling of debtor call '
     'activities.\n'
     '\n'
     '* **Fiscal Year Closing & Retained Earnings Automation**:\n'
     '  - Configure custom fiscal year periods with strict date boundary and unique code '
     'constraints.\n'
     '  - Automated year-end closing wizard clearing P&L account balances to designated '
     'Retained Earnings.\n'
     '  - Automatic setting of company fiscal year lock dates upon period closure.\n'
     '\n'
     '* **Multi-Company & Multi-Currency Security**:\n'
     '  - Native multi-company record rules isolating legal entities.\n'
     '  - Full multi-currency support with precision rounding.\n'
     '  - Detailed security roles for Accountants (User) and Financial Advisors (Manager).\n'),
    'category': 'Accounting',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['account', 'mail'],
    'data': [   'security/accounting_security.xml',
        'security/ir.model.access.csv',
        'report/report_actions.xml',
        'report/report_bank_reconcile_statement.xml',
        'report/report_fiscal_year_closing.xml',
        'report/report_financial_reports.xml',
        'views/ydod_fiscal_year_close_wizard_views.xml',
        'views/ydod_bank_recon_report_wizard_views.xml',
        'views/ydod_reconcile_lines_wizard_views.xml',
        'views/ydod_financial_report_wizard_views.xml',
        'views/ydod_followup_views.xml',
        'views/account_bank_reconcile_statement_views.xml',
        'views/ydod_fiscal_year_views.xml',
        'views/account_fiscal_year_views.xml',
        'views/ydod_asset_views.xml',
        'views/ydod_budget_views.xml',
        'views/account_move_line_views.xml',
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'views/res_company_views.xml',
        'views/accounting_menus.xml'],
    'demo': ['demo/account_fiscal_year_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png',
        'static/description/screenshot_5.png',
        'static/description/screenshot_6.png',
        'static/description/screenshot_7.png'],
    'installable': True,
    'application': True,
}
