# -*- coding: utf-8 -*-
{
    'name': 'Web Responsive: Mobile & Tablet Backend UI',
    'version': '18.0.1.0.0',
    'summary': ('Transforms Odoo Community backend into a fluid, touch-friendly responsive interface with '
     'an app drawer, mobile navbar, collapsible chatter, and auto-scroll tables.'),
    'description': ('\n'
     'yDoD Web Responsive: Mobile & Tablet Backend UI\n'
     '===============================================\n'
     'Transforms the Odoo Community backend into an intuitive, modern, touch-optimized mobile '
     'experience.\n'
     'Enjoy full mobility with zero external dependencies, seamless performance, and native '
     'app aesthetics.\n'
     '\n'
     'Key Features:\n'
     '-------------\n'
     '* **Full-Screen App Drawer (App Switcher)**: Instant access to all apps on mobile and '
     'tablet screens with live search and smooth animations.\n'
     '* **Adaptive Bottom Navigation Bar**: Sticky one-thumb bottom bar on mobile viewports '
     '(<768px) with quick shortcuts to Apps, Back, Menu, and Chatter.\n'
     '* **Flexible Chatter Placement**: Allows each user to choose whether chatter is docked '
     'on the side (aside) or stacked below the form.\n'
     '* **Sticky Table Headers**: Keep table column headers fixed while scrolling through '
     'large data sets on phones and tablets.\n'
     '* **Horizontal Scroll Indicators**: Visual cues for wide data tables to eliminate '
     'accidental layout clipping.\n'
     '* **Touch-Optimized Controls**: Enlarged buttons, inputs, and checkboxes (minimum 44px) '
     'meeting modern mobile accessibility standards.\n'
     '* **Mobile Dialog Optimization**: Full-screen modal sheets on mobile viewports for '
     'effortless form completion.\n'
     '* **Clean & Lightweight**: 100% native OWL components and SCSS styling with zero '
     'third-party or proprietary dependencies.\n'),
    'category': 'Extra Tools',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [   'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'views/backend_responsive_menus.xml'],
    'demo': ['demo/res_users_demo.xml'],
    'assets': {   'web.assets_backend': [   'ydod_backend_responsive/static/src/scss/backend_responsive.scss',
                                  'ydod_backend_responsive/static/src/scss/responsive_tables.scss',
                                  'ydod_backend_responsive/static/src/scss/touch_controls.scss',
                                  'ydod_backend_responsive/static/src/components/app_drawer/app_drawer.js',
                                  'ydod_backend_responsive/static/src/components/app_drawer/app_drawer.xml',
                                  'ydod_backend_responsive/static/src/components/bottom_navbar/bottom_navbar.js',
                                  'ydod_backend_responsive/static/src/components/bottom_navbar/bottom_navbar.xml',
                                  'ydod_backend_responsive/static/src/components/chatter/chatter_patch.js',
                                  'ydod_backend_responsive/static/src/components/chatter/chatter_patch.xml']},
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png'],
    'installable': True,
    'application': False,
}
