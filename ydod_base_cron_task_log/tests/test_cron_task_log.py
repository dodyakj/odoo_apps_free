from datetime import timedelta

from odoo import api, fields
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


class CronTaskLogCommon:
    """Records and helpers shared by the test classes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.Log = cls.env['cron.task.log']
        cls.channel = cls.env['discuss.channel'].create({'name': 'Cron Alerts Test'})
        cls.now = fields.Datetime.now()

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('ydod_base_cron_task_log.success_retention_days', '30')
        icp.set_param('ydod_base_cron_task_log.failed_retention_days', '90')
        icp.set_param('ydod_base_cron_task_log.timeout_minutes', '60')

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


@tagged('post_install', '-at_install')
class TestCronTaskLog(CronTaskLogCommon, TransactionCase):
    """Maintenance jobs, dashboard statistics, constraints and access rights."""

    def test_timeout_detection(self):
        cron = self._make_cron(log_alert_channel_id=self.channel.id)
        stale = self._make_log(cron, 'running', timedelta(hours=2))
        fresh = self._make_log(cron, 'running', timedelta(minutes=5))
        self.Log._cron_mark_timeouts()
        self.assertEqual(stale.status, 'timeout')
        self.assertTrue(stale.error_summary)
        self.assertFalse(stale.date_end)
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

    def test_invalid_parameters_use_defaults(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('ydod_base_cron_task_log.timeout_minutes', 'soon')
        icp.set_param('ydod_base_cron_task_log.success_retention_days', '-3')
        self.assertEqual(self.Log._get_positive_param('ydod_base_cron_task_log.timeout_minutes', 60), 60)
        self.assertEqual(self.Log._get_positive_param('ydod_base_cron_task_log.success_retention_days', 30), 30)
        self.assertEqual(self.Log._get_positive_param('ydod_base_cron_task_log.failed_retention_days', 90), 90)

        cron = self._make_cron()
        recent = self._make_log(cron, 'success', timedelta(days=20))
        old = self._make_log(cron, 'success', timedelta(days=40))
        self.Log._cron_purge_logs()
        self.assertTrue(recent.exists())
        self.assertFalse(old.exists())

    def test_dashboard_statistics(self):
        cron = self._make_cron()
        self._make_log(cron, 'failed', timedelta(days=10))
        for hours in (4, 3, 2):
            self._make_log(cron, 'success', timedelta(hours=hours), duration=10)
        self._make_log(cron, 'failed', timedelta(minutes=1))
        cron.invalidate_recordset()
        self.assertEqual(sorted(cron.log_ids.mapped('duration')), [0.0, 0.0, 10.0, 10.0, 10.0])
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
        self.assertEqual(crons[1].success_rate_7d, 100.0)

    def test_log_constraints(self):
        cron = self._make_cron()
        log = self._make_log(cron, 'success', timedelta(hours=1), duration=10)
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception) as caught:
            log.write({'record_count': -1})
            log.env.flush_all()
        self.assertRegex(str(caught.exception), 'record_count_positive|cannot be negative')
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception) as caught:
            log.write({'date_end': log.date_start - timedelta(seconds=1)})
            log.env.flush_all()
        self.assertRegex(str(caught.exception), 'date_order|End must be after start')

        summary = self.Log._summarize_traceback(
            "Traceback (most recent call last):\n  File \"job.py\", line 1\nValueError: %s\n\n" % ('x' * 300))
        self.assertTrue(summary.startswith('ValueError: x'))
        self.assertEqual(len(summary), 255)

    def test_access_rights(self):
        cron = self._make_cron()
        log_a = self._make_log(cron, 'failed', timedelta(hours=1))
        user = new_test_user(self.env, login='cron_log_internal', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.Log.with_user(user).search([])
        with self.assertRaises(AccessError):
            log_a.with_user(user).action_rerun()

        # administrators read and delete logs, only the jobs write them
        with self.assertRaises(AccessError):
            log_a.with_user(self.admin).write({'message': 'edited'})

        company_b = self.env['res.company'].create({'name': 'Cron Log Company B'})
        admin_b = new_test_user(
            self.env, login='cron_log_admin_b', groups='base.group_user,base.group_system',
            company_id=company_b.id, company_ids=[Command.set(company_b.ids)])
        log_b = self._make_log(cron, 'success', timedelta(hours=1), company_id=company_b.id)
        visible = self.Log.with_user(admin_b).search([('id', 'in', (log_a | log_b).ids)])
        self.assertEqual(visible, log_b)

        log_a.with_user(self.admin).unlink()
        self.assertFalse(log_a.exists())

        # SQL CHECK constraint: psycopg2 error, rolled back by assertRaises()
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception) as caught:
            cron.write({'log_retention_failed_days': -5})
            cron.env.flush_all()
        self.assertRegex(str(caught.exception), 'log_retention_positive|Retention days cannot be negative')
        self.assertEqual(cron.log_retention_failed_days, 0)


@tagged('post_install', '-at_install')
class TestCronTaskLogRun(CronTaskLogCommon, HttpCase):
    """Real job executions.

    The job (ir.cron._run_job behind method_direct_trigger) and the log entries
    run on registry.cursor(). Odoo 19 has no registry.enter_test_mode() any
    more: HttpCase keeps the registry in test mode, where those cursors are
    savepoints of the test transaction. The jobs see the records created here
    and everything is rolled back with the test.
    """

    def setUp(self):
        super().setUp()
        self.assertTrue(self._cursor_shares_test_transaction(),
                        "registry.cursor() must open savepoints of the test transaction")

    def _cursor_shares_test_transaction(self):
        """True when registry.cursor() runs on the connection of the test."""
        self.cr.execute("SELECT pg_backend_pid()")
        pid = self.cr.fetchone()[0]
        with self.registry.cursor() as cr:
            cr.execute("SELECT pg_backend_pid()")
            return cr.fetchone()[0] == pid

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
        self.assertIs(cron.with_user(self.admin).method_direct_trigger(), True)
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
