# -*- coding: utf-8 -*-
{
    'name': 'Purchase Vendor Minimum Order Guard',
    'version': '19.0.1.0.0',
    'summary': ('Enforces supplier-level minimum order values and quantities on RFQs and POs to avoid '
     'vendor surcharges and rejected orders.'),
    'description': ('\n'
     'Purchase Vendor Minimum Order Guard\n'
     '===================================\n'
     'Enforce vendor-level minimum order amount (MOV) and minimum order quantity (MOQ) on '
     'purchase orders and requests for quotation.\n'
     '\n'
     'Key Features:\n'
     '-------------\n'
     '* Set Minimum Order Amount and Minimum Order Quantity directly on vendor partner forms.\n'
     '* Real-time warning alert banner on Purchase Orders when requirements are not reached.\n'
     '* Prevents RFQ/PO confirmation if thresholds are not met.\n'
     '* Manager override permission to allow authorized users to bypass minimum thresholds for '
     'emergency orders.\n'
     '* Dedicated search filter and group-by on purchase orders to track compliance.\n'
     '    '),
    'category': 'Inventory/Purchase',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['purchase'],
    'data': [   'security/groups.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/purchase_order_views.xml'],
    'demo': ['demo/demo_data.xml'],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
