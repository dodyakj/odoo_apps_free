from datetime import datetime, timedelta
import os
import shutil
import tempfile
from unittest.mock import patch

import psycopg2

from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestBackupManager(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref('ydod_database_backup_manager.group_backup_user')
        cls.group_manager = cls.env.ref('ydod_database_backup_manager.group_backup_manager')

        cls.user_reader = cls.env['res.users'].create({
            'name': 'Backup Test Reader',
            'login': 'backup_test_reader',
            'email': 'reader@example.com',
            'group_ids': [Command.link(cls.group_user.id)],
        })
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Backup Test Manager',
            'login': 'backup_test_manager',
            'email': 'manager@example.com',
            'group_ids': [Command.link(cls.group_manager.id)],
        })

    def setUp(self):
        super().setUp()
        self.test_dir = tempfile.mkdtemp(prefix="odoo_backup_test_")
        # Deactivate any pre-existing records during testing
        self.env['ydod.backup.config'].search([]).write({'active': False})

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        super().tearDown()

    def test_01_config_validation_and_constraints(self):
        """Test default values, validation, and SQL/Python constraints."""
        config = self.env['ydod.backup.config'].create({
            'name': 'Test Default Config',
            'db_name': 'test_db_default',
            'local_path': self.test_dir,
        })
        self.assertTrue(config.active)
        self.assertEqual(config.backup_format, 'zip')
        self.assertEqual(config.destination_type, 'local')
        self.assertEqual(config.retention_days, 7)
        self.assertEqual(config.ftp_port, 21)
        self.assertEqual(config.log_count, 0)
        self.assertFalse(config.last_run_date)
        self.assertFalse(config.last_run_status)

        # SQL constraint: retention_days >= 0
        with mute_logger('odoo.sql_db'), self.assertRaises(psycopg2.IntegrityError):
            with self.env.cr.savepoint():
                self.env['ydod.backup.config'].create({
                    'name': 'Invalid Negative Retention',
                    'db_name': 'test_db',
                    'retention_days': -5,
                    'local_path': self.test_dir,
                })

        # SQL constraint: ftp_port between 1 and 65535
        with mute_logger('odoo.sql_db'), self.assertRaises(psycopg2.IntegrityError):
            with self.env.cr.savepoint():
                self.env['ydod.backup.config'].create({
                    'name': 'Invalid FTP Port',
                    'db_name': 'test_db',
                    'destination_type': 'ftp',
                    'ftp_host': 'ftp.example.com',
                    'ftp_port': 70000,
                })

        # Python constraint: local_path required for local destination
        with self.assertRaises(ValidationError):
            self.env['ydod.backup.config'].create({
                'name': 'Missing Local Path',
                'db_name': 'test_db',
                'destination_type': 'local',
                'local_path': '',
            })

        # Python constraint: ftp_host required for ftp destination
        with self.assertRaises(ValidationError):
            self.env['ydod.backup.config'].create({
                'name': 'Missing FTP Host',
                'db_name': 'test_db',
                'destination_type': 'ftp',
                'ftp_host': '',
            })

    def test_02_successful_local_backup_and_computed_fields(self):
        """Test local backup execution, log record generation, and computed fields."""
        config = self.env['ydod.backup.config'].create({
            'name': 'Test Local Execution',
            'db_name': 'test_db_exec',
            'destination_type': 'local',
            'local_path': self.test_dir,
            'retention_days': 7,
        })

        def fake_dump(db_name, stream, backup_format='zip'):
            stream.write(b"MOCK_ODOO_BACKUP_DATA_STREAM_TEST")

        with patch('odoo.addons.ydod_database_backup_manager.models.backup_config._dump_database', side_effect=fake_dump):
            action_res = config.action_backup_now()

        self.assertIsInstance(action_res, dict)
        self.assertEqual(action_res.get('tag'), 'display_notification')
        self.assertEqual(action_res.get('params', {}).get('type'), 'success')

        # Check file created in local destination
        files = os.listdir(self.test_dir)
        self.assertTrue(len(files) >= 1)
        self.assertTrue(any(f.startswith("backup_test_db_exec_") and f.endswith(".zip") for f in files))

        # Check logs and computed fields
        self.assertEqual(config.log_count, 1)
        self.assertEqual(config.last_run_status, 'success')
        self.assertTrue(config.last_run_date)

        log = config.log_ids[0]
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.db_name, 'test_db_exec')
        self.assertEqual(log.destination_summary, os.path.abspath(self.test_dir))
        self.assertFalse(log.error_message)

        # Check stat button action
        stat_action = config.action_view_logs()
        self.assertEqual(stat_action.get('res_model'), 'ydod.backup.log')
        self.assertIn(('config_id', '=', config.id), stat_action.get('domain', []))

    def test_03_retention_cleanup(self):
        """Test that retention cleanup removes outdated archives and keeps recent ones."""
        db_name = 'test_retention_db'
        old_filename = f"backup_{db_name}_20200101_120000.zip"
        recent_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        recent_filename = f"backup_{db_name}_{recent_timestamp}.zip"

        old_file_path = os.path.join(self.test_dir, old_filename)
        recent_file_path = os.path.join(self.test_dir, recent_filename)

        with open(old_file_path, 'wb') as f:
            f.write(b"OLD_BACKUP")
        with open(recent_file_path, 'wb') as f:
            f.write(b"RECENT_BACKUP")

        old_mtime = (datetime.now() - timedelta(days=15)).timestamp()
        os.utime(old_file_path, (old_mtime, old_mtime))

        config = self.env['ydod.backup.config'].create({
            'name': 'Test Retention',
            'db_name': db_name,
            'local_path': self.test_dir,
            'retention_days': 7,
        })

        config._cleanup_local_backups(self.test_dir, db_name, 'zip', config.retention_days)

        self.assertFalse(os.path.exists(old_file_path), "Old backup should be purged by retention.")
        self.assertTrue(os.path.exists(recent_file_path), "Recent backup should be preserved.")

    def test_04_ftp_transfer_error_handling(self):
        """Test FTP failure handling when server cannot be reached."""
        config = self.env['ydod.backup.config'].create({
            'name': 'Test FTP Failure Config',
            'db_name': 'test_ftp_db',
            'destination_type': 'ftp',
            'ftp_host': 'unreachable.nonexistent.ftp.server.domain',
            'ftp_port': 2121,
            'ftp_user': 'fake_user',
            'ftp_password': 'fake_password',
        })

        def fake_dump(db_name, stream, backup_format='zip'):
            stream.write(b"MOCK_DUMP_BYTES")

        with mute_logger('odoo.addons.ydod_database_backup_manager.models.backup_config'):
            with patch('odoo.addons.ydod_database_backup_manager.models.backup_config._dump_database', side_effect=fake_dump):
                log = config._execute_backup()

        self.assertEqual(log.status, 'failed')
        self.assertTrue(log.error_message)
        self.assertEqual(config.last_run_status, 'failed')
        self.assertEqual(config.log_count, 1)

    def test_05_failure_notification_dispatch(self):
        """Test that failure alert notification is dispatched when backup raises an error."""
        config = self.env['ydod.backup.config'].create({
            'name': 'Test Alert Config',
            'db_name': 'test_alert_db',
            'destination_type': 'local',
            'local_path': self.test_dir,
            'notify_user_ids': [Command.link(self.user_manager.id)],
        })

        with mute_logger('odoo.addons.ydod_database_backup_manager.models.backup_config'):
            with patch('odoo.addons.ydod_database_backup_manager.models.backup_config._dump_database', side_effect=RuntimeError("Simulated backup crash")):
                with patch.object(type(config), '_send_failure_notification') as mock_notify:
                    log = config._execute_backup()
                    self.assertEqual(log.status, 'failed')
                    mock_notify.assert_called_once()

    def test_06_security_access_rights(self):
        """Test ACL permissions between group_backup_user and group_backup_manager."""
        config = self.env['ydod.backup.config'].create({
            'name': 'Test Security Config',
            'db_name': 'test_security_db',
            'local_path': self.test_dir,
        })

        # Backup User: can read config
        read_res = config.with_user(self.user_reader).read(['name', 'db_name'])
        self.assertTrue(read_res)
        self.assertEqual(read_res[0]['name'], 'Test Security Config')

        # Backup User: cannot create config
        with self.assertRaises(AccessError):
            self.env['ydod.backup.config'].with_user(self.user_reader).create({
                'name': 'Unauthorized Config',
                'db_name': 'test_unauth',
                'local_path': self.test_dir,
            })

        # Backup User: cannot trigger manual backup
        with self.assertRaises(AccessError):
            config.with_user(self.user_reader).action_backup_now()

        # Backup Manager: can update config
        config.with_user(self.user_manager).write({'retention_days': 14})
        self.assertEqual(config.retention_days, 14)

    def test_07_cron_execution(self):
        """Test that cron_run_backups processes all active configurations."""
        active_config = self.env['ydod.backup.config'].create({
            'name': 'Cron Active Config',
            'db_name': 'test_cron_active',
            'active': True,
            'local_path': self.test_dir,
        })
        inactive_config = self.env['ydod.backup.config'].create({
            'name': 'Cron Inactive Config',
            'db_name': 'test_cron_inactive',
            'active': False,
            'local_path': self.test_dir,
        })

        def fake_dump(db_name, stream, backup_format='zip'):
            stream.write(b"MOCK_CRON_BACKUP_BYTES")

        with patch('odoo.addons.ydod_database_backup_manager.models.backup_config._dump_database', side_effect=fake_dump):
            self.env['ydod.backup.config'].cron_run_backups()

        self.assertEqual(active_config.log_count, 1)
        self.assertEqual(inactive_config.log_count, 0)
