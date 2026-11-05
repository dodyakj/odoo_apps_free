# -*- coding: utf-8 -*-
{
    'name': 'X2Many Line Search: Instant Search Box on One2many & Many2many Lists',
    'version': '17.0.1.0.0',
    'summary': ('Search, filter and highlight lines of any one2many / many2many list in form views (order '
     'lines, invoice lines, moves, BoM components) with a live match counter, Alt+F hotkey and '
     'no XML changes.'),
    'description': ('\n'
     'X2Many Line Search\n'
     '==================\n'
     'Adds an instant search box above every one2many and many2many list inside form views:\n'
     'sales order lines, invoice lines, picking moves, BoM components and any other embedded '
     'list.\n'
     '\n'
     '* Zero-config: works on every x2many list widget, including section_and_note_one2many\n'
     '* Global on/off switch in General Settings\n'
     '* Per-field opt-out with options="{\'line_search\': False}"\n'
     '* Loads the remaining lines once, then filters in the browser with no server call per '
     'keystroke\n'
     '* Matches all visible columns: text, many2one names, tags, selection labels, numbers, '
     'dates, and any text displayed in the row (e.g. line descriptions under the product)\n'
     '* Partial-word matching anywhere in the line, compact search box on its own row above '
     'the list\n'
     '* The box stays visible on top while scrolling long lists and is never covered by the '
     'list\n'
     '* Case- and accent-insensitive, multi-word (AND) search\n'
     '* Highlights matches and shows a live counter such as 12 / 340\n'
     '* Alt+F focuses the search box, Esc clears it\n'
     '* Safe in edit mode: hidden lines keep their unsaved changes\n'),
    'category': 'Technical/Web',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['web', 'base_setup'],
    'data': ['data/ir_config_parameter.xml', 'views/res_config_settings_views.xml'],
    'assets': {'web.assets_backend': ['ydod_web_x2many_line_search/static/src/**/*']},
    'images': ['static/description/demo.gif', 'static/description/banner.png'],
    'installable': True,
    'application': False,
}
