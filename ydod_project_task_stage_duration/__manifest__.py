# -*- coding: utf-8 -*-
{
    'name': 'Project Task Stage Duration & Bottleneck Tracker',
    'version': '16.0.1.0.0',
    'summary': ('Automatically logs time spent in each kanban stage, provides real-time time-in-stage '
     'counters, and flags workflow bottlenecks so managers can spot delayed tasks without Odoo '
     'Enterprise.'),
    'description': ('\n'
     'Project Task Stage Duration & Bottleneck Tracker\n'
     '=================================================\n'
     '\n'
     'Gain deep visibility into task cycle times, eliminate workflow stalls, and identify '
     'project bottlenecks in Odoo Community.\n'
     '\n'
     'Key Features\n'
     '------------\n'
     '* **Automated Stage Duration Logging**: Accurately records stage entrance timestamps, '
     'exit timestamps, responsible users, and elapsed durations (hours and days) for every '
     'stage transition.\n'
     '* **Live Time-in-Stage Counter**: Real-time duration badges rendered right on Kanban '
     'task cards and form view headers.\n'
     '* **Intelligent Bottleneck Detection**: Configurable maximum duration thresholds per '
     'project stage trigger immediate visual warning tags when deadlines slip.\n'
     '* **Audit Timeline in Chatter**: Automatically posts concise transition summaries with '
     'elapsed duration directly to the task chatter.\n'
     '* **Dedicated Stage History Tab**: Comprehensive audit trail on each task form detailing '
     'the full chronological journey from inception to completion.\n'
     '* **Stage Duration Reporting & Pivot Analysis**: Multi-dimensional pivot tables and '
     'charts grouped by stage, project, and team members with average duration metrics.\n'
     '\n'
     'Target Users\n'
     '------------\n'
     '* Project Managers and Operations Leads tracking delivery timelines and SLAs.\n'
     '* Agile and Scrum teams analyzing sprint cycle times and stage lead times.\n'
     '* Service agencies needing verifiable stage audit trails without Enterprise licenses.\n'),
    'category': 'Project',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['project'],
    'data': [   'security/ir.model.access.csv',
        'security/project_task_stage_duration_security.xml',
        'views/project_task_stage_history_views.xml',
        'views/project_task_type_views.xml',
        'views/project_task_views.xml',
        'views/project_task_stage_duration_menus.xml'],
    'demo': ['demo/project_task_stage_duration_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png'],
    'installable': True,
    'application': False,
}
