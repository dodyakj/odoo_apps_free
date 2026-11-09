# -*- coding: utf-8 -*-
{
    'name': 'Fixed Asset Core: Asset Register & Straight-Line Depreciation for Community',
    'version': '20.0.1.0.0',
    'summary': ('Fixed asset management for Odoo Community: asset register, assets from vendor bills, '
     'straight-line depreciation schedule with prorata and automatic posting of depreciation '
     'entries.'),
    'description': ('\n'
     'Fixed Asset Core - Asset Register and Straight-Line Depreciation\n'
     '================================================================\n'
     '\n'
     'Since Odoo 17 asset management is Enterprise-only. This module brings a compact,\n'
     'reliable fixed asset register to Odoo Community Invoicing for accountants, finance\n'
     'teams and SME owners (including Indonesian companies applying PSAK 16 or the\n'
     'tax straight-line method / penyusutan aset garis lurus).\n'
     '\n'
     'Key features\n'
     '------------\n'
     '* Asset categories with fixed asset, accumulated depreciation and expense accounts,\n'
     '  depreciation journal, useful life, monthly or yearly period and prorata.\n'
     '* Assets created automatically when a vendor bill is posted, or registered manually\n'
     '  (opening balances with already depreciated amounts).\n'
     '* Straight-line depreciation schedule stored as draft journal entries, prorata by\n'
     '  days on the first period, exact rounding on the last entry.\n'
     '* Daily scheduled action posting due depreciation entries, skipping locked periods.\n'
     '* Disposal with write-off of the remaining book value, reset to draft, chatter '
     'tracking.\n'
     '* Asset register list and pivot with gross value, accumulated depreciation and\n'
     '  net book value; Assets smart button on vendor bills; multi-company rules.\n'),
    'category': 'Accounting/Accounting',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [   'security/ir.access.csv',
        'data/ir_cron_data.xml',
        'views/ydod_asset_category_views.xml',
        'views/ydod_asset_views.xml',
        'views/account_move_views.xml',
        'views/menus.xml'],
    'demo': ['demo/ydod_asset_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png',
        'static/description/screenshot_5.png',
        'static/description/screenshot_6.png',
        'static/description/screenshot_7.png',
        'static/description/screenshot_8.png',
        'static/description/screenshot_9.png'],
    'installable': True,
    'application': False,
}
