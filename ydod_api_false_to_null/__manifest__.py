# -*- coding: utf-8 -*-
{
    'name': 'API False to NULL Converter',
    'version': '19.0.1.0.0',
    'summary': 'Convert empty non-Boolean False values to JSON null in Odoo API read responses.',
    'description': ('Developer utility for JSON-RPC and REST integrations. Converts False values from empty '
     'non-Boolean fields to None in read(), search_read(), and web_read() results, while '
     'preserving real Boolean values. Enable conversion per request with the api_false_to_null '
     'context key or globally with a System Parameter. Handles nested relational data without '
     'adding business models or database schema.'),
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
