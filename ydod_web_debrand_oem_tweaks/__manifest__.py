# -*- coding: utf-8 -*-
{
    'name': ('OEM White Label & Backend Tweaks: Window Title, User Menu Links, Login Branding, Debug '
     'Guard & Draggable Dialogs'),
    'version': '18.0.1.0.0',
    'summary': ('White label / debrand Odoo: custom window title, remove Powered by Odoo, customize user '
     'menu links, environment ribbon, debug mode restriction, draggable and resizable dialogs '
     'and chat windows.'),
    'description': ('\n'
     'OEM White Label & Backend Tweaks\n'
     '================================\n'
     'For Odoo partners, resellers, integrators and in-house IT administrators who deliver\n'
     'Odoo Community under their own brand. Everything is configured from one\n'
     '"White Label & Tweaks" block in Settings, without code or XML changes.\n'
     '\n'
     'Key features\n'
     '------------\n'
     '* Replace "Odoo" in the browser window / tab title with your own system name.\n'
     '* Hide or replace the "Powered by Odoo" link on the login and database selector pages.\n'
     '* Rename, re-point or hide the user-menu entries Documentation, Support, Shortcuts\n'
     '  and "My Odoo.com account", plus an optional About entry.\n'
     '* Developer-mode shortcut and quick language switcher in the user menu.\n'
     '* Environment ribbon (TEST, DEMO, STAGING...) with custom text and colour.\n'
     '* Debug guard: only Settings administrators may enter debug mode.\n'
     '* Draggable and resizable backend dialogs and Discuss chat windows (min 300x200px).\n'
     '* All values stored as system parameters (ir.config_parameter), no new tables.\n'),
    'category': 'Custom',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base_setup', 'web'],
    'data': ['views/res_config_settings_views.xml', 'views/login_templates.xml'],
    'demo': ['demo/ydod_tweaks_demo.xml'],
    'assets': {'web.assets_backend': ['ydod_web_debrand_oem_tweaks/static/src/**/*']},
    'images': ['static/description/demo.gif', 'static/description/banner.png'],
    'installable': True,
    'application': False,
}
