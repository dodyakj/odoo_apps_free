# -*- coding: utf-8 -*-
{
    'name': 'yDoD PostgreSQL Query Execute: SQL Console with Notes, Examples, History & PDF Export',
    'version': '16.0.1.0.0',
    'summary': ('SQL console for administrators: run PostgreSQL queries from the Odoo backend, document '
     'them with notes, keep a run history and print results to PDF.'),
    'description': ('\n'
     'yDoD PostgreSQL Query Execute\n'
     '=============================\n'
     'Run SQL statements on the Odoo PostgreSQL database from Settings > Technical,\n'
     'without psql or shell access. Built for system administrators, technical\n'
     'consultants, support engineers and developers.\n'
     '\n'
     'Key features\n'
     '------------\n'
     '* SQL console: execute SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER or DROP\n'
     '  and see the result as a table with column names, row count and duration.\n'
     '* Documentation note on every saved query: what it does, why, and the dangers.\n'
     '* Example library: ready-to-use queries for common support tasks.\n'
     '* Execution history: user, date, duration, rows affected and error message,\n'
     '  with a "Load into editor" button to reuse any past statement.\n'
     '* PDF export of the result table in portrait or landscape.\n'
     '* Safety guards: savepoint isolation, explicit "Allow data modification"\n'
     '  tick for write statements, maximum displayed rows.\n'
     '* Restricted to the Settings / Administration group.\n'
     '\n'
     'Keywords: sql console, postgresql query, execute sql odoo, database query tool,\n'
     'query history, sql result pdf, sql examples library, odoo administrator database.\n'
     '    '),
    'category': 'Custom',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [   'security/ir.model.access.csv',
        'data/ydod_sql_query_examples.xml',
        'report/ydod_sql_query_reports.xml',
        'views/ydod_sql_query_views.xml',
        'views/ydod_sql_query_history_views.xml',
        'views/ydod_sql_menus.xml'],
    'demo': ['demo/ydod_sql_query_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png'],
    'installable': True,
    'application': False,
}
