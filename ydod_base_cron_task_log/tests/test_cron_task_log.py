from datetime import timedelta

from odoo import api, fields
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestCronTaskLog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.Log = cls.env['cron.task.log']
        cls.channel = cls.env['discuss.channel'].create({'name': 'Cron Alerts Test'})
        cls.now = fields.Datetime.now()

    def setUp(self):
        super().setUp()
        self._ensure_test_mode()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_int('ydod_base_cron_task_log.success_retention_days', 30)
        icp.set_int('ydod_base_cron_task_log.failed_retention_days', 90)
        icp.set_int('ydod_base_cron_task_log.timeout_minutes', 60)

    def _ensure_test_mode(self):
        """registry.cursor() must return a test cursor sharing self.cr, so the
        separate log cursor and the job cursor are rolled back with the test.

        A test cursor shares the connection of self.cr, so both report the
        same PostgreSQL backend: this does not depend on the cursor class name.
        """
        self.cr.execute("SELECT pg_backend_pid()")
        test_pid = self.cr.fetchone()[0]
        cursor_info = []

        def in_test_mode():
            with self.registry.cursor() as cr:
                cursor_info[:] = ['%s.%s' % (type(cr).__module__, type(cr).__qualname__)]
                cr.execute("SELECT pg_backend_pid()")
                return cr.fetchone()[0] == test_pid

        def enter_registry():
            self.registry.enter_test_mode(self.cr)
            self.addCleanup(self.registry.leave_test_mode)

        def enter_helper(name):
            def enter():
                result = getattr(self, name)()
                # recent versions expose the helper as a context manager
                if hasattr(result, '__enter__'):
                    result.__enter__()
                    self.addCleanup(result.__exit__, None, None, None)
            return enter

        attempts = []
        if hasattr(self.registry, 'enter_test_mode'):
            attempts.append(('registry.enter_test_mode', enter_registry))
        for name in ('registry_enter_test_mode', 'enter_registry_test_mode'):
            if hasattr(self, name):
                attempts.append((name, enter_helper(name)))

        tried = []
        for label, enter in [('already active', None)] + attempts:
            if enter is not None:
                try:
                    enter()
                    tried.append(label)
                except Exception as e:  # noqa: BLE001 - report every attempt
                    tried.append('%s: %r' % (label, e))
                    continue
            if in_test_mode():
                return
        self.fail("registry.cursor() must share the test transaction (tried %s, got %s)" % (tried, cursor_info))

    def _make_cron(self, code='pass', **vals):
        return self.env['ir.cron'].create({
            'name': 'Test Cron Task Log Job',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'state': 'code',
            'code': code,
            'user_id': self.admin.id,
            'interval_number': 1,
            'interval_type': 'days',
            **vals,
        })

    def _run(self, cron):
        """Run the job like the scheduler does (ir.cron._run_job): _callback on
        a new cursor, its exception caught inside the job transaction, which
        then closes normally. The exception is re-raised for the test."""
        name, action_id = cron.cron_name, cron.ir_actions_server_id.id
        self.env.flush_all()
        error = None
        try:
            with self.registry.cursor() as cr:
                env = api.Environment(cr, self.admin.id, {})
                try:
                    env['ir.cron'].browse(cron.id)._callback(name, action_id)
                except Exception as e:  # noqa: BLE001 - re-raised below
                    error = e
        finally:
            self.env.invalidate_all()
        if error is not None:
            raise error

    def _make_log(self, cron, status, age, duration=0, **vals):
        start = self.now - age
        return self.Log.create({
            'cron_id': cron.id,
            'status': status,
            'date_start': start,
            'date_end': False if status == 'running' else start + timedelta(seconds=duration),
            'company_id': self.env.company.id,
            'user_id': self.admin.id,
            **vals,
        })

    def test_success_run_with_progress(self):
        cron = self._make_cron(
            "env['cron.task.log'].log_progress(processed=3, message='ok')\n"
            "env['cron.task.log'].log_progress(processed=3, message='ok')")
        self._run(cron)
        log = cron.log_ids
        self.assertEqual(len(log), 1)
        self.assertRecordValues(log, [{
            'status': 'success',
            'record_count': 6,
            'message': 'ok\nok',
            'trigger_type': 'scheduled',
            'user_id': self.admin.id,
            'company_id': self.admin.company_id.id,
        }])
        self.assertTrue(log.date_end)
        self.assertGreaterEqual(log.duration, 0)
        self.assertIn(cron.name, log.display_name)

    def test_failed_run_keeps_traceback(self):
        cron = self._make_cron(
            "env['res.partner'].create({'name': 'Cron Task Log Rolled Back'})\nraise UserError('boom')",
            log_alert_channel_id=self.channel.id)
        # Not self.assertRaises(): Odoo wraps it in a savepoint of the test
        # cursor that is rolled back when the exception is raised, and the log
        # written through the (shared) test cursors would be rolled back too.
        try:
            self._run(cron)
        except UserError:
            pass
        else:
            self.fail("The failing job must raise its UserError")
        log = cron.log_ids
        self.assertEqual(log.status, 'failed')
        self.assertIn('boom', log.traceback)
        self.assertIn('boom', log.error_summary)
        self.assertTrue(log.date_end)
        self.assertFalse(self.env['res.partner'].search([('name', '=', 'Cron Task Log Rolled Back')]))
        alert = self.channel.message_ids.filtered(lambda m: 'boom' in (m.body or ''))
        self.assertEqual(len(alert), 1)
        self.assertIn('/odoo/action-ydod_base_cron_task_log.action_cron_task_log/%s' % log.id, alert.body)

    def test_skipped_disabled_and_outside_run(self):
        cron = self._make_cron("env['cron.task.log'].log_progress(skipped=True)")
        self._run(cron)
        self.assertEqual(cron.log_ids.status, 'skipped')

        quiet = self._make_cron(log_enabled=False)
        self._run(quiet)
        self.assertFalse(quiet.log_ids)

        self.assertFalse(self.Log.log_progress(processed=1, message='not in a cron'))

    def test_manual_trigger_and_rerun(self):
        cron = self._make_cron()
        cron.with_user(self.admin).method_direct_trigger()
        self.env.invalidate_all()
        self.assertRecordValues(cron.log_ids, [{'trigger_type': 'manual', 'status': 'success'}])

        failed = self._make_log(cron, 'failed', timedelta(hours=1), error_summary='boom')
        failed.with_user(self.admin).action_rerun()
        self.env.invalidate_all()
        self.assertEqual(len(failed.rerun_ids), 1)
        self.assertRecordValues(failed.rerun_ids, [{'trigger_type': 'manual', 'status': 'success'}])
        self.assertEqual(cron.log_count, 3)

        with self.assertRaises(UserError):
            failed.rerun_ids.with_user(self.admin).action_rerun()

    def test_timeout_detection(self):
        cron = self._make_cron(log_alert_channel_id=self.channel.id)
        stale = self._make_log(cron, 'running', timedelta(hours=2))
        fresh = self._make_log(cron, 'running', timedelta(minutes=5))
        self.Log._cron_mark_timeouts()
        self.assertEqual(stale.status, 'timeout')
        self.assertTrue(stale.error_summary)
        self.assertEqual(fresh.status, 'running')
        self.channel.invalidate_recordset(['message_ids'])
        link = '/odoo/action-ydod_base_cron_task_log.action_cron_task_log/%s' % stale.id
        self.assertTrue(self.channel.message_ids.filtered(lambda m: link in (m.body or '')))

    def test_retention_purge(self):
        cron = self._make_cron()
        short = self._make_cron(log_retention_success_days=10)
        success_40 = self._make_log(cron, 'success', timedelta(days=40))
        success_20 = self._make_log(cron, 'success', timedelta(days=20))
        skipped_40 = self._make_log(cron, 'skipped', timedelta(days=40))
        failed_60 = self._make_log(cron, 'failed', timedelta(days=60))
        timeout_100 = self._make_log(cron, 'timeout', timedelta(days=100))
        running_200 = self._make_log(cron, 'running', timedelta(days=200))
        short_15 = self._make_log(short, 'success', timedelta(days=15))
        short_5 = self._make_log(short, 'success', timedelta(days=5))
        self.Log._cron_purge_logs()
        self.assertFalse(success_40.exists())
        self.assertFalse(skipped_40.exists())
        self.assertFalse(timeout_100.exists())
        self.assertFalse(short_15.exists())
        self.assertTrue(success_20.exists())
        self.assertTrue(failed_60.exists())
        self.assertTrue(running_200.exists())
        self.assertTrue(short_5.exists())

    def test_dashboard_statistics(self):
        cron = self._make_cron()
        self._make_log(cron, 'failed', timedelta(days=10))
        for hours in (4, 3, 2):
            self._make_log(cron, 'success', timedelta(hours=hours), duration=10)
        self._make_log(cron, 'failed', timedelta(minutes=1))
        cron.invalidate_recordset()
        self.assertRecordValues(cron, [{
            'log_count': 5,
            'success_rate_7d': 75.0,
            'failure_count_7d': 1,
            'last_log_status': 'failed',
            'log_color': 1,
        }])
        self.assertAlmostEqual(cron.avg_duration_7d, 7.5)

        crons = cron | self._make_cron() | self._make_cron()
        for other in crons[1:]:
            self._make_log(other, 'success', timedelta(hours=1), duration=5)

        def count_queries(records):
            # read the fields like the views do: the compute runs once for the
            # whole recordset (calling it directly would write each value)
            self.env.invalidate_all()
            records = self.env['ir.cron'].browse(records.ids)
            start = self.cr.sql_log_count
            records.mapped('log_color')
            return self.cr.sql_log_count - start

        count_queries(crons)  # warm up caches
        self.assertEqual(count_queries(crons[:1]), count_queries(crons))
        self.assertEqual(crons[1].log_color, 10)

    def test_access_rights(self):
        cron = self._make_cron()
        user = new_test_user(self.env, login='cron_log_internal', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.Log.with_user(user).search([])

        company_b = self.env['res.company'].create({'name': 'Cron Log Company B'})
        admin_b = new_test_user(
            self.env, login='cron_log_admin_b', groups='base.group_user,base.group_system',
            company_id=company_b.id, company_ids=[Command.set(company_b.ids)])
        log_a = self._make_log(cron, 'success', timedelta(hours=1))
        log_b = self._make_log(cron, 'success', timedelta(hours=1), company_id=company_b.id)
        visible = self.Log.with_user(admin_b).search([('id', 'in', (log_a | log_b).ids)])
        self.assertEqual(visible, log_b)

        with mute_logger('odoo.sql_db'), self.assertRaises(Exception), self.cr.savepoint():
            cron.write({'log_retention_failed_days': -5})
            cron.env.flush_all()
