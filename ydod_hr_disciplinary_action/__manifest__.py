# -*- coding: utf-8 -*-
{
    'name': 'Employee Disciplinary Actions & Warning Management',
    'version': '18.0.1.0.0',
    'summary': ('Track employee misconduct, formal warnings, and disciplinary history with a structured '
     'approval workflow and private records.'),
    'description': ('Track employee misconduct, formal warnings, and disciplinary history with a structured '
     'approval workflow and private records.'),
    'category': 'Human Resources',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['hr', 'mail'],
    'data': [   'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/disciplinary_action_views.xml'],
    'demo': ['data/disciplinary_action_demo.xml'],
    'images': [   'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png'],
    'installable': True,
    'application': True,
}
