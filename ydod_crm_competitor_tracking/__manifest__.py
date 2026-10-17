# -*- coding: utf-8 -*-
{
    'name': 'CRM Competitor Tracking & Win/Loss Analysis',
    'version': '20.0.1.0.0',
    'summary': ('Lets sales teams tag which competitors they are up against on each opportunity, then '
     'automatically records the win/loss outcome and stage reached, with a report showing win '
     'rate and deal count per competitor so reps know who they are really fighting and where '
     'deals are lost.'),
    'description': ('\n'
     'CRM Competitor Tracking & Win/Loss Analysis\n'
     '=============================================\n'
     '\n'
     'Tag competitors on your opportunities and let the system build your battle cards for '
     'you.\n'
     '\n'
     '* Lightweight Competitor directory (name, website, notes).\n'
     '* Tag competitors directly on the opportunity form and kanban card.\n'
     '* Automatic win/loss snapshot (result + stage reached) the moment an opportunity is won '
     'or lost.\n'
     '* Smart button on every competitor showing all related opportunities.\n'
     '* Pivot and graph report of win rate, loss rate and deal value per competitor.\n'),
    'category': 'Sales/CRM',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['crm', 'mail'],
    'data': [   'security/ir.access.csv',
        'views/ydod_crm_competitor_views.xml',
        'views/ydod_crm_competitor_result_views.xml',
        'views/crm_lead_views.xml',
        'views/menus.xml'],
    'demo': ['demo/ydod_crm_competitor_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png'],
    'installable': True,
    'application': False,
}
