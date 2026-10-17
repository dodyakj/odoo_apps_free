# -*- coding: utf-8 -*-
{
    'name': 'Replenishment Approval Workflow',
    'version': '18.0.1.0.0',
    'summary': ("Require a purchasing manager's sign-off before a triggered reordering rule turns into a "
     'purchase order'),
    'description': ('\n'
     'Replenishment Approval Workflow\n'
     '================================\n'
     '\n'
     'Adds a manager approval step between a triggered reordering rule and the resulting\n'
     'purchase order, so automatic replenishment never generates a commitment to a vendor\n'
     'without human review.\n'
     '\n'
     'Key Features\n'
     '------------\n'
     '* "Require Approval" checkbox on Reordering Rules (per orderpoint).\n'
     '* Replenishment triggers on flagged orderpoints create a pending Replenishment Request\n'
     '  instead of an RFQ.\n'
     '* Approve / Reject actions on the request; approving generates the normal purchase\n'
     '  order through the standard procurement flow.\n'
     '* Rejection requires a reason, kept on the record for audit.\n'
     '* Dedicated list / kanban view of pending requests, filterable by warehouse and\n'
     '  responsible buyer.\n'
     '* Activity notification to the responsible buyer when a new request is created.\n'),
    'category': 'Inventory',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['stock', 'purchase', 'mail'],
    'data': [   'security/ir.model.access.csv',
        'security/ydod_replenish_request_security.xml',
        'data/ydod_replenish_request_data.xml',
        'wizard/ydod_replenish_request_reject_views.xml',
        'views/stock_warehouse_orderpoint_views.xml',
        'views/ydod_replenish_request_views.xml'],
    'demo': ['demo/ydod_replenish_request_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png'],
    'installable': True,
    'application': False,
}
