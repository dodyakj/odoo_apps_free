# -*- coding: utf-8 -*-
{
    'name': 'yDoD Menu Access Control - User & Group Wise',
    'version': '17.0.1.0.0',
    'summary': ('Hide any menu or sub-menu for specific users or groups: central Menu Restrictions '
     'screen, user-form and menu-form tabs, Copy Hidden Menus wizard, Cascade to Sub-Menus. '
     'Administrators always keep full menu visibility.'),
    'description': ('\n'
     'yDoD Menu Access Control - User & Group Wise\n'
     '============================================\n'
     'Fine-grained menu visibility for Odoo Community and Enterprise.\n'
     '\n'
     '* Hide any menu or sub-menu for a specific user from the user form (Menu Restrictions '
     'tab).\n'
     '* Hide a menu for a whole user group from the menu form (Restrict Access tab).\n'
     '* Central "Menu Restrictions" screen under Settings > Users & Companies.\n'
     "* Copy Hidden Menus wizard: replicate one user's hidden menus to many users in one "
     'click.\n'
     "* Cascade to Sub-Menus: propagate a menu's restrictions to all of its descendants.\n"
     '* Company-scoped rules for multi-company databases.\n'
     '* System administrators are never restricted and always see every menu.\n'
     '\n'
     'Keywords: menu access control, hide menu, user menu restrictions, group menu '
     'restrictions,\n'
     'menu visibility, restrict menu, Odoo 17.\n'
     '    '),
    'category': 'Tools',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [   'security/ydod_menu_access_security.xml',
        'security/ir.model.access.csv',
        'data/ydod_menu_access_actions.xml',
        'wizard/ydod_menu_access_copy_views.xml',
        'views/ydod_menu_access_views.xml',
        'views/res_users_views.xml',
        'views/ir_ui_menu_views.xml',
        'views/ydod_menu_access_menus.xml'],
    'demo': ['demo/ydod_menu_access_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png'],
    'installable': True,
    'application': False,
}
