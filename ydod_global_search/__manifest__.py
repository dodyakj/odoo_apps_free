# -*- coding: utf-8 -*-
{
    'name': 'Global All Search: One Popup to Find Contacts, Products, Orders & Invoices',
    'version': '16.0.1.0.0',
    'summary': ('Global search popup (spotlight / omnibox) with keyboard shortcut, systray icon and '
     'floating button to find contacts, products, sales orders, purchase orders and invoices '
     'from one place, with admin-configured models and fields.'),
    'description': ('\n'
     'Global All Search by yDoD\n'
     '=========================\n'
     'Find any business record from one quick search popup instead of opening menu after '
     'menu.\n'
     '\n'
     '* Administrators choose the searchable models (contacts, products, sales orders,\n'
     '  purchase orders, invoices, ...) and the fields that are matched and displayed,\n'
     '  including Many2one, One2many and Many2many relations through dotted paths.\n'
     '* Open the popup with a configurable keyboard shortcut (default Ctrl+Shift+K),\n'
     '  the systray magnifier or an optional floating button.\n'
     '* Results grouped by model, ranked by field weight, with key values per record.\n'
     '* Keyboard navigation: Up/Down, Enter to open, Ctrl+Enter for the filtered list, Esc to '
     'close.\n'
     '* Settings for minimum characters, typing delay, total and per-model result limits.\n'
     '* Secure: searches run as the current user, respecting access rights, record rules\n'
     '  and multi-company.\n'),
    'category': 'Productivity',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base_setup', 'web'],
    'data': [   'security/ir.model.access.csv',
        'views/global_search_model_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml'],
    'demo': ['demo/global_search_demo.xml'],
    'assets': {   'web.assets_backend': [   'ydod_global_search/static/src/global_search.scss',
                                  'ydod_global_search/static/src/global_search_config.js',
                                  'ydod_global_search/static/src/global_search_dialog.js',
                                  'ydod_global_search/static/src/global_search_dialog.xml',
                                  'ydod_global_search/static/src/global_search_launcher.js',
                                  'ydod_global_search/static/src/global_search_launcher.xml']},
    'images': ['static/description/demo.gif', 'static/description/banner.png'],
    'installable': True,
    'application': False,
    'post_init_hook': '_ydod_create_default_configs',
}
