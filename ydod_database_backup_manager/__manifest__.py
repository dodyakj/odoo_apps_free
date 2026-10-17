# -*- coding: utf-8 -*-
{
    'name': 'Automatic Database Backup to Local, Remote & Cloud Mount Storage',
    'version': '20.0.1.0.0',
    'summary': ('Schedule automated Odoo database backups with retention cleanup, remote FTP transfer, '
     'local and cloud-mounted storage sync, execution history, and email failure alerts '
     'without external Python dependencies.'),
    'description': ('\n'
     'Automatic Database Backup Manager for Odoo 20.0\n'
     '================================================\n'
     'A dependable, enterprise-grade backup solution built entirely on standard Python\n'
     'and Odoo Community libraries.\n'
     '\n'
     'Key Features:\n'
     '-------------\n'
     '* **Flexible Storage Destinations**: Store backups to local folders, network mounts\n'
     '  (NFS, CIFS, Samba), cloud mounts (Google Drive, OneDrive, Dropbox, Nextcloud, S3 via '
     'rclone/FUSE),\n'
     '  and remote FTP servers.\n'
     '* **Zero External Dependencies**: Uses only Python standard libraries (shutil, ftplib)\n'
     '  and native Odoo APIs. No external pip packages required.\n'
     '* **Scheduled Automation**: Automated daily, weekly, or monthly database backups\n'
     '  powered by native Odoo cron jobs.\n'
     '* **One-Click Manual Backup**: Trigger instant backups directly from configuration '
     'forms\n'
     '  with immediate UI feedback and metrics.\n'
     '* **Automatic Retention Policy**: Automatically clean up backups older than N days to '
     'prevent\n'
     '  disk overflow and control storage costs.\n'
     '* **Audit Trail & Execution History**: Detailed logs of every backup run, including '
     'archive\n'
     '  file size, duration, database name, and full error tracebacks.\n'
     '* **Email Failure Alerts**: Immediate email notification to designated administrators\n'
     '  and chatter notes when any backup fails.\n'
     '* **Strict Role-Based Security**: Dedicated Backup User (audit/read-only) and Backup '
     'Manager\n'
     '  (full administration) access controls.\n'
     '    '),
    'category': 'Custom',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [   'security/backup_security.xml',
        'security/ir.access.csv',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/backup_log_views.xml',
        'views/backup_config_views.xml',
        'views/backup_menus.xml'],
    'demo': ['demo/backup_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png'],
    'installable': True,
    'application': True,
}
