# -*- coding: utf-8 -*-
{
    'name': 'Widget Collection: Labeled Toggle, HTML Print Preview & Many2many List',
    'version': '16.0.1.0.0',
    'summary': ('Three drop-in OWL field widgets for any form or list view: boolean toggle with custom '
     'on/off labels, HTML print preview with Save as PDF, and a clickable many2many / one2many '
     'vertical list.'),
    'description': ('\n'
     'yDoD Widget Collection\n'
     '======================\n'
     'Three reusable backend field widgets for Odoo 16.0 Community and Enterprise, built as\n'
     'native OWL 2 components on the standard field registry. Developers, integrators and\n'
     'functional consultants add them to any form or list view with a single ``widget``\n'
     'attribute: no Python, no new models, no menus, no external JavaScript library.\n'
     '\n'
     'Widgets\n'
     '-------\n'
     '* **Labeled toggle** (``ydod_toggle_label``, Boolean fields): a Bootstrap switch that\n'
     '  shows configurable on/off texts and colors next to the switch. Works in form and\n'
     '  editable or read-only list views, honors ``readonly`` and autosaves like the standard\n'
     "  ``boolean_toggle`` (disable with ``'autosave': False``).\n"
     '* **HTML print preview** (``ydod_html_print_preview``, Html fields): renders the field\n'
     '  in an isolated A4 / A3 / A5 / Letter / Legal paper frame (sandboxed iframe) and adds '
     'a\n'
     "  *Print / Save as PDF* button that opens the browser's native print dialog with only\n"
     '  the paper content. No wkhtmltopdf, no bundled PDF library.\n'
     '* **Many2many list** (``ydod_many2many_list``, Many2many and One2many fields): shows\n'
     '  the linked records as a bulleted, numbered or plain vertical list instead of crowded\n'
     '  tags. Every item opens its record in one click; an optional ``limit`` adds a\n'
     '  *+N more* / *Show less* collapse without any extra request.\n'
     '\n'
     'Usage examples\n'
     '--------------\n'
     'Labeled toggle::\n'
     '\n'
     '    <field name="active" widget="ydod_toggle_label"\n'
     '           options="{\'on_label\': \'Active\', \'off_label\': \'Archived\',\n'
     "                     'on_color': '#198754', 'off_color': '#6c757d',\n"
     '                     \'label_position\': \'right\', \'autosave\': False}"/>\n'
     '\n'
     'Labeled toggle in a list::\n'
     '\n'
     '    <tree editable="bottom">\n'
     '        <field name="active" widget="ydod_toggle_label"\n'
     '               options="{\'on_label\': \'Yes\', \'off_label\': \'No\'}"/>\n'
     '    </tree>\n'
     '\n'
     'HTML print preview::\n'
     '\n'
     '    <field name="comment" widget="ydod_html_print_preview"\n'
     '           options="{\'page_size\': \'A4\', \'orientation\': \'portrait\',\n'
     '                     \'title\': \'Partner notes\', \'hide_button\': False}"/>\n'
     '\n'
     'Many2many list::\n'
     '\n'
     '    <field name="category_id" widget="ydod_many2many_list"\n'
     '           options="{\'style\': \'bullet\', \'limit\': 3,\n'
     '                     \'open_target\': \'current\', \'no_open\': False}"/>\n'
     '\n'
     'Option defaults: ``on_label`` On, ``off_label`` Off, Bootstrap success / secondary\n'
     'colors, ``label_position`` right, ``autosave`` True; ``page_size`` A4, ``orientation``\n'
     'portrait, ``title`` record display name; ``style`` bullet (also number, plain),\n'
     '``limit`` 0 = unlimited, ``open_target`` current (or new).\n'
     '\n'
     'Keywords: widget, boolean toggle label, html print preview, save as pdf, many2many '
     'list,\n'
     'one2many list, owl field widget, odoo 16 community, ydod.\n'),
    'category': 'Hidden',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [],
    'demo': ['demo/res_partner_demo_views.xml'],
    'assets': {   'web.assets_backend': [   'ydod_web_widget_collection/static/src/fields/toggle_label/toggle_label.scss',
                                  'ydod_web_widget_collection/static/src/fields/toggle_label/toggle_label.xml',
                                  'ydod_web_widget_collection/static/src/fields/toggle_label/toggle_label.js',
                                  'ydod_web_widget_collection/static/src/fields/html_print_preview/html_print_preview.scss',
                                  'ydod_web_widget_collection/static/src/fields/html_print_preview/html_print_preview.xml',
                                  'ydod_web_widget_collection/static/src/fields/html_print_preview/html_print_preview.js',
                                  'ydod_web_widget_collection/static/src/fields/many2many_list/many2many_list.scss',
                                  'ydod_web_widget_collection/static/src/fields/many2many_list/many2many_list.xml',
                                  'ydod_web_widget_collection/static/src/fields/many2many_list/many2many_list.js']},
    'images': ['static/description/demo.gif', 'static/description/banner.png'],
    'installable': True,
    'application': False,
}
