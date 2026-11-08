import logging
import traceback
from contextlib import contextmanager
from datetime import timedelta
from functools import partial

from odoo import SUPERUSER_ID, _, api, fields, models

from .cron_task_log import CRON_LOG_LOCAL, LOG_STATUS

_logger = logging.getLogger(__name__)


class IrCron(models.Model):
    _inherit = 'ir.cron'

    log_enabled = fields.Boolean('Log Runs', default=True,
                                 help="Record every execution of this job in the Cron Task Logs.")
    log_alert_channel_id = fields.Many2one(
        'discuss.channel', string='Failure Alert Channel', domain=[('channel_type', '=', 'channel')],
        help="Discuss channel that receives a message when a run fails or times out.")
    log_retention_success_days = fields.Integer(
        'Keep Successful Logs (days)', default=0,
        help="Retention of successful and skipped logs. 0 uses the system parameter (30 days by default).")
    log_retention_failed_days = fields.Integer(
        'Keep Failed Logs (days)', default=0,
        help="Retention of failed and timed-out logs. 0 uses the system parameter (90 days by default).")
    log_ids = fields.One2many('cron.task.log', 'cron_id', string='Run Logs')
    log_count = fields.Integer('Log Count', compute='_compute_log_stats')
    last_log_date = fields.Datetime('Last Run', compute='_compute_log_stats')
    last_log_status = fields.Selection(LOG_STATUS, string='Last Status', compute='_compute_log_stats')
    success_rate_7d = fields.Float('Success Rate (7 days)', compute='_compute_log_stats', digits=(16, 1))
    avg_duration_7d = fields.Float('Avg Duration (7 days)', compute='_compute_log_stats', digits=(16, 1))
    failure_count_7d = fields.Integer('Failures (7 days)', compute='_compute_log_stats')
    log_color = fields.Integer('Log Color', compute='_compute_log_stats')

    _sql_constraints = [
        ('log_retention_positive',
         'CHECK(log_retention_success_days >= 0 AND log_retention_failed_days >= 0)',
         'Retention days cannot be negative.'),
    ]

    @api.depends('log_ids')
    def _compute_log_stats(self):
        Log = self.env['cron.task.log']
        cron_ids = self._origin.ids
        totals = {
            cron.id: (count, date_max, id_max)
            for cron, count, date_max, id_max in Log._read_group(
                [('cron_id', 'in', cron_ids)], ['cron_id'], ['__count', 'date_start:max', 'id:max'])
        }
        last_status = {log.id: log.status for log in Log.browse([t[2] for t in totals.values()])}
        recent = {}
        since = fields.Datetime.now() - timedelta(days=7)
        for cron, status, count, duration in Log._read_group(
                [('cron_id', 'in', cron_ids), ('date_start', '>=', since), ('status', '!=', 'running')],
                ['cron_id', 'status'], ['__count', 'duration:sum']):
            stats = recent.setdefault(cron.id, {'ok': 0, 'ko': 0, 'duration': 0.0})
            stats['ok' if status in ('success', 'skipped') else 'ko'] += count
            stats['duration'] += duration or 0.0
        for cron in self:
            count, date_max, id_max = totals.get(cron._origin.id, (0, False, False))
            stats = recent.get(cron._origin.id, {'ok': 0, 'ko': 0, 'duration': 0.0})
            finished = stats['ok'] + stats['ko']
            status = last_status.get(id_max, False)
            cron.log_count = count
            cron.last_log_date = date_max
            cron.last_log_status = status
            cron.success_rate_7d = stats['ok'] * 100.0 / finished if finished else 0.0
            cron.avg_duration_7d = stats['duration'] / finished if finished else 0.0
            cron.failure_count_7d = stats['ko']
            cron.log_color = 1 if status in ('failed', 'timeout') else 10 if status in ('success', 'skipped') else 0

    def action_view_cron_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ydod_base_cron_task_log.action_cron_task_log')
        action['domain'] = [('cron_id', '=', self.id)]
        action['context'] = {'default_cron_id': self.id}
        action['display_name'] = _("Logs: %s", self.name)
        return action

    # ------------------------------------------------------------------
    # Execution hooks
    # ------------------------------------------------------------------

    @contextmanager
    def _cron_log_env(self):
        """Superuser environment on a separate cursor, committed on exit.

        Log entries survive the rollback of the job's own transaction.
        """
        with self.env.registry.cursor() as cr:
            # the job's transaction is still open meanwhile (until the end of
            # the request for manual runs): never wait forever on its locks
            cr.execute("SET LOCAL lock_timeout = '10s'")
            env = api.Environment(cr, SUPERUSER_ID, {})
            yield env
            env.flush_all()

    def _cron_log_start(self, trigger_type, rerun_of_id):
        try:
            with self._cron_log_env() as env:
                allowed = self.env.context.get('allowed_company_ids')
                user = env['res.users'].browse(self.env.uid)
                vals = {
                    'cron_id': self.id,
                    'date_start': fields.Datetime.now(),
                    'trigger_type': trigger_type,
                    'user_id': user.id,
                    'company_id': allowed[0] if allowed else user.company_id.id,
                    'rerun_of_id': rerun_of_id or False,
                }
                log = env['cron.task.log'].create(vals)
                return log.id, vals
        except Exception:  # noqa: BLE001 - logging must never block the job
            _logger.warning("Cron task log: cannot create the log of job %s", self.id, exc_info=True)
            return False

    def _cron_log_finish(self, log_id, start_vals, status, error=None):
        try:
            with self._cron_log_env() as env:
                vals = {'status': status, 'date_end': fields.Datetime.now()}
                if error:
                    vals.update(traceback=error, error_summary=env['cron.task.log']._summarize_traceback(error))
                log = env['cron.task.log'].browse(log_id).exists()
                if log:
                    log.write(vals)
                else:
                    # the job's rollback also undid the 'running' entry
                    # (nested savepoints): write the complete entry again
                    log = env['cron.task.log'].create({**start_vals, **vals})
                log_id = log.id
        except Exception:  # noqa: BLE001
            _logger.warning("Cron task log: cannot close log %s", log_id, exc_info=True)
            return
        if status != 'failed':
            return
        # separate transaction: a failing alert must not lose the failed status
        try:
            with self._cron_log_env() as env:
                env['cron.task.log'].browse(log_id)._post_failure_alerts()
        except Exception:  # noqa: BLE001
            _logger.warning("Cron task log: cannot post the alert of log %s", log_id, exc_info=True)

    def _cron_log_run(self, trigger_type, rerun_of_id, run_job):
        """Call ``run_job()`` and record its execution in a cron.task.log entry."""
        started = self._cron_log_start(trigger_type, rerun_of_id)
        if not started:
            return run_job()
        log_id, start_vals = started
        previous = getattr(CRON_LOG_LOCAL, 'run', None)
        run = CRON_LOG_LOCAL.run = {'log_id': log_id, 'cron_id': self.id, 'skipped': False, 'error': None}
        try:
            result = run_job()
        except Exception:
            self._cron_log_finish(log_id, start_vals, 'failed', run['error'] or traceback.format_exc())
            raise
        else:
            if run['error']:
                # scheduled run: _callback() rolled the job back and swallowed the error
                self._cron_log_finish(log_id, start_vals, 'failed', run['error'])
            else:
                self._cron_log_finish(log_id, start_vals, 'skipped' if run['skipped'] else 'success')
            return result
        finally:
            CRON_LOG_LOCAL.run = previous

    @api.model
    def _callback(self, cron_name, server_action_id, job_id):
        # runs of the scheduler, including the ones requested by _trigger()
        cron = self.browse(job_id)
        # logging switched off: no separate cursor, no overhead
        if not cron.sudo().log_enabled:
            return super()._callback(cron_name, server_action_id, job_id)
        context = self.env.context
        return cron._cron_log_run(
            context.get('cron_task_log_trigger') or 'scheduled',
            context.get('cron_task_log_rerun_of'),
            partial(super()._callback, cron_name, server_action_id, job_id),
        )

    @api.model
    def _handle_callback_exception(self, cron_name, server_action_id, job_id, job_exception):
        # super()._callback() does not re-raise the job's error: it calls this
        # hook, which rolls the job back. Keep the traceback for the log.
        run = getattr(CRON_LOG_LOCAL, 'run', None)
        if run and run['cron_id'] == job_id:
            run['error'] = ''.join(traceback.format_exception(
                type(job_exception), job_exception, job_exception.__traceback__))
        return super()._handle_callback_exception(cron_name, server_action_id, job_id, job_exception)

    def method_direct_trigger(self):
        # 'Run Manually' runs the server action here, without _callback()
        # same checks as super() first: a refused or locked run is not logged
        self.check_access_rights('write')
        rerun_of_id = self.env.context.get('cron_task_log_rerun_of')
        for cron in self:
            if not cron.sudo().log_enabled:
                super(IrCron, cron).method_direct_trigger()
                continue
            cron._try_lock()
            # like super(), the job runs as the scheduler user
            cron.with_user(cron.user_id)._cron_log_run(
                'manual', rerun_of_id, super(IrCron, cron).method_direct_trigger)
        return True
