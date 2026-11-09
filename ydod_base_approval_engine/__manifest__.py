# -*- coding: utf-8 -*-
{
    'name': 'Approval Engine Core - Dynamic Approval Rules for Any Document',
    'version': '19.0.1.0.0',
    'summary': ('Dynamic approval engine: one-step approval rules for sales orders, invoices, transfers, '
     'expenses and any model, with Request Approval, Approve / Reject, reject reasons in '
     'chatter and approver activities.'),
    'description': ('\n'
     'Approval Engine Core\n'
     '====================\n'
     'A generic, reusable single-step approval engine for Odoo 19.0 Community.\n'
     '\n'
     '* Approval rules for any model: target model, domain condition, guarded\n'
     '  confirm methods (action_confirm, action_post, button_validate, ...),\n'
     '  approver users and/or an approver group, company and priority.\n'
     '* The original confirm button is blocked with "This document requires\n'
     '  approval" until an assigned approver approves the document.\n'
     '* "Request Approval" entry in the Action menu of the target model, a To Do\n'
     '  activity and a chatter note for each approver.\n'
     '* One-click Approve, Reject with a mandatory reason posted in the\n'
     '  document chatter.\n'
     '* "My Approvals" menu and "Waiting My Approval" smart button on users.\n'
     '* Approval Manager group, approver-only decisions and multi-company rules.\n'),
    'category': 'Tools / Workflow',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [   'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizard/approval_reject_wizard_views.xml',
        'views/approval_rule_views.xml',
        'views/approval_request_views.xml',
        'views/res_users_views.xml',
        'views/menus.xml'],
    'demo': ['demo/approval_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png',
        'static/description/screenshot_5.png',
        'static/description/screenshot_6.png',
        'static/description/screenshot_7.png',
        'static/description/screenshot_8.png'],
    'installable': True,
    'application': True,
}
