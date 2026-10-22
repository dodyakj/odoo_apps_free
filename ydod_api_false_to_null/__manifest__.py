# -*- coding: utf-8 -*-
{
    'name': 'API False to NULL Converter',
    'version': '20.0.1.0.0',
    'summary': ('Automatically converts False values to null in JSON-RPC/REST API responses for '
     'non-Boolean fields while preserving actual Boolean true/false.'),
    'description': ('Technical utility module that converts False to null in API responses for empty '
     'non-Boolean fields (Char, Text, Many2one, Date, Selection, etc.) while keeping Boolean '
     "fields intact. Activated via context key {'api_false_to_null': True} or global "
     'ir.config_parameter. Works recursively on nested relational data from read(), '
     'search_read(), and web_read(). Zero configuration, no database changes, pure Python.'),
    'category': 'Extra Tools',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': ['data/ir_config_parameter.xml'],
    'images': ['static/description/demo.gif', 'static/description/banner.png'],
    'installable': True,
    'application': False,
}
