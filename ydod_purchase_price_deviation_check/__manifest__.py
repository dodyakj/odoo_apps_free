# -*- coding: utf-8 -*-
{
    'name': 'Purchase Price Deviation Guard',
    'version': '18.0.1.0.0',
    'summary': ('Flag PO lines priced above the last purchase or vendor price and route them to manager '
     'approval'),
    'description': ('\n'
     'Purchase Price Deviation Guard\n'
     '==============================\n'
     'Compares every purchase order line with a reference price (last confirmed\n'
     'purchase of the product, converted to the line unit and currency, or the\n'
     'vendor pricelist as a fallback). Lines exceeding the configured tolerance are\n'
     'flagged and the order goes to the standard "To Approve" state. A Purchase\n'
     'Manager must approve it with a justification, which is logged in the chatter.\n'),
    'category': 'Inventory/Purchase',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['purchase'],
    'data': [   'security/ir.model.access.csv',
        'data/mail_templates.xml',
        'wizard/price_deviation_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/product_category_views.xml',
        'views/purchase_order_views.xml'],
    'demo': ['demo/price_deviation_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png'],
    'installable': True,
    'application': False,
}
