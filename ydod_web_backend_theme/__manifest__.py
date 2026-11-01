# -*- coding: utf-8 -*-
{
    'name': 'yDoD Backend Theme: Side App Bar, Branded Apps Menu & Brand Colours',
    'version': '20.0.1.0.0',
    'summary': ('Backend theme for Odoo Community: side app bar with per-user app order, full-window apps '
     'menu over a company background, brand colors from Settings with one-click reset, and a '
     'per-company favicon.'),
    'description': ('\n'
     'yDoD Backend Theme\n'
     '==================\n'
     '\n'
     "Give the Odoo Community backend your company's look and faster navigation without\n"
     'forking any source file.\n'
     '\n'
     '* Side app bar on every backend page listing every app the user may open, with the\n'
     '  current app highlighted and one click to switch.\n'
     '* Per-user app order by drag and drop, stored on the user and restored at every login.\n'
     '* Per-user app bar mode in My Preferences: Expanded, Icons only or Hidden.\n'
     '* Full-window apps menu below the navbar over a per-company background image, with a\n'
     '  fallback colour.\n'
     '* Brand, primary, success, info, warning and danger colours plus the app bar palette,\n'
     '  set in Settings > General Settings > Backend Theme and compiled into a generated SCSS\n'
     '  asset (ir.asset), so upgrades have nothing to merge.\n'
     '* Reset to Defaults restores the standard Odoo palette in one click.\n'
     '* Per-company favicon (.ico, .png or .svg) in the browser tab.\n'
     '* Depends only on base_setup and web, no external libraries.\n'),
    'category': 'Themes/Backend',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base_setup', 'web'],
    'data': [   'views/res_config_settings_views.xml',
        'views/res_company_views.xml',
        'views/res_users_views.xml',
        'views/webclient_templates.xml'],
    'demo': ['demo/ydod_web_backend_theme_demo.xml'],
    'assets': {   'web._assets_primary_variables': [   (   'prepend',
                                                 'ydod_web_backend_theme/static/src/scss/colors.scss')],
        'web.assets_backend': [   'ydod_web_backend_theme/static/src/app_bar/app_bar.scss',
                                  'ydod_web_backend_theme/static/src/app_bar/app_bar.xml',
                                  'ydod_web_backend_theme/static/src/app_bar/app_bar.js']},
    'images': ['static/description/demo.gif', 'static/description/banner.png'],
    'installable': True,
    'application': False,
    'uninstall_hook': 'uninstall_hook',
}
