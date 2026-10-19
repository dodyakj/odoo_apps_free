# -*- coding: utf-8 -*-
{
    'name': 'Contact Document Expiry & Compliance Tracker',
    'version': '18.0.1.0.0',
    'summary': ('Track expiration dates for IDs, trade licenses, certifications, and insurance policies '
     'for customers and vendors with automated alerts.'),
    'description': ('Track expiration dates for IDs, trade licenses, certifications, and insurance policies '
     'for customers and vendors with automated alerts, compliance dashboard, and '
     'notifications.'),
    'category': 'Contacts',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['contacts', 'mail'],
    'data': [   'security/ir.model.access.csv',
        'data/document_type_data.xml',
        'data/ir_cron_data.xml',
        'wizard/document_notify_wizard_views.xml',
        'views/contact_document_views.xml',
        'views/res_partner_views.xml',
        'views/document_type_views.xml',
        'views/contact_document_type_views.xml',
        'views/menus.xml'],
    'demo': ['demo/contact_document_demo.xml'],
    'images': [   'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png'],
    'installable': True,
    'application': True,
}
