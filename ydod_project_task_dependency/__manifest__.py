# -*- coding: utf-8 -*-
{
    'name': 'Project Task Dependencies & Blocking Guards',
    'version': '19.0.1.0.0',
    'summary': ('Enable task predecessors and blocking logic in Odoo Community to prevent closing tasks '
     'before their dependencies are finished.'),
    'description': ('\n'
     'Project Task Dependencies & Blocking Guards\n'
     '===========================================\n'
     'Manage execution order in Odoo Community:\n'
     '- Define task predecessors and successors\n'
     '- Prevent closing tasks while dependencies remain open\n'
     '- Visual warning alerts on blocked tasks\n'
     '- One-click navigation smart buttons\n'
     '- Automated unblocking chatter alerts\n'
     '    '),
    'category': 'Project',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['project'],
    'data': ['views/project_task_views.xml'],
    'demo': ['demo/project_task_demo.xml'],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
