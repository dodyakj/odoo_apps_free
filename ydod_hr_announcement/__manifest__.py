# -*- coding: utf-8 -*-
{
    'name': 'HR Official Announcements & Company Notices',
    'version': '19.0.1.0.0',
    'summary': 'Lets HR publish official company announcements with targeting and read-receipt tracking',
    'description': ('\n'
     'HR Official Announcements & Company Notices\n'
     '===========================================\n'
     'Manage and broadcast official company announcements within Odoo Community:\n'
     '* Create announcements with rich-text content, attachments, and categorization (General, '
     'Warning, Reward, Greeting).\n'
     '* Target broadcasts to the entire company, specific departments, or selected employees.\n'
     '* Track per-employee read receipts with timestamps and unread counters.\n'
     '* Automated notifications in Discuss and chatter on publication.\n'
     '* Scheduled auto-expiration via daily cron job.\n'
     '* Kanban and list views with color-coded type badges and unread indicators.\n'
     '* Multi-company support for corporate environments.\n'
     '    '),
    'category': 'Human Resources',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['hr', 'mail'],
    'data': [   'security/hr_announcement_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/hr_announcement_views.xml',
        'views/hr_announcement_menus.xml'],
    'demo': ['demo/hr_announcement_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png'],
    'installable': True,
    'application': False,
}
