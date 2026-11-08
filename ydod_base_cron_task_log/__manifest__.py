# -*- coding: utf-8 -*-
{
    'name': ('Cron Task Log: Scheduled Action Run History, Failure Tracebacks, Success Rate Dashboard '
     '& Re-run'),
    'version': '16.0.1.0.0',
    'summary': ('Cron log and scheduled action monitor: record every ir.cron run with status, duration, '
     'full traceback and records processed, see a success rate dashboard, get Discuss failure '
     'alerts, re-run failed jobs and purge old logs automatically.'),
    'description': ('\n'
     'Cron Task Log - Scheduled Action Monitor for Odoo administrators\n'
     '================================================================\n'
     '\n'
     'In Odoo Community, scheduled actions fail silently: the only trace is in the server '
     'log.\n'
     'This module records every ir.cron execution (scheduler, Run Manually button and '
     '_trigger())\n'
     'in a dedicated cron job history, written on a separate cursor so failures survive the '
     'rollback.\n'
     '\n'
     'Key features:\n'
     '\n'
     '* One log per run: scheduled action, start / end, duration, status (running, success, '
     'failed,\n'
     '  skipped, timeout), trigger (scheduled or manual), full Python traceback, error '
     'summary,\n'
     '  records processed, notes, user and company\n'
     "* Developer helper ``env['cron.task.log'].log_progress(processed=, message=, "
     'skipped=)``\n'
     '* Logs smart button and last-run banner on the Scheduled Action form\n'
     '* Cron Dashboard kanban: last run, 7-day success rate, average duration, failures, red '
     'stripe\n'
     '* Quick filters: Failed (last 24 hours), Timeouts, Manual runs, Today\n'
     '* Re-run now button on failed or timed-out runs, linked to the original log\n'
     '* Failure and timeout alerts posted to a Discuss channel\n'
     '* Timeout detection for workers killed by limit_time_real\n'
     '* Automatic retention purge with separate periods for successful and failed runs,\n'
     '  per-job overrides and a per-job switch to turn logging off\n'
     '* Settings administrators only, multi-company record rules, no Enterprise or queue_job\n'),
    'category': 'Tools / Administration',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail'],
    'data': [   'security/ir.model.access.csv',
        'security/cron_task_log_security.xml',
        'data/cron_task_log_data.xml',
        'views/cron_task_log_views.xml',
        'views/ir_cron_views.xml',
        'views/menus.xml'],
    'demo': ['demo/cron_task_log_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png'],
    'installable': True,
    'application': False,
}
