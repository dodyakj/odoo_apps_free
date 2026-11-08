import threading
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL, format_datetime, html_escape

# markupsafe.Markup, reached through odoo.tools
Markup = type(html_escape(''))

# Per-thread state of the cron run being logged: ``run`` holds the current
# log id, ``trigger`` and ``rerun_of`` are set by method_direct_trigger.
CRON_LOG_LOCAL = threading.local()

LOG_STATUS = [
    ('running', 'Running'),
    ('success', 'Success'),
    ('failed', 'Failed'),
    ('skipped', 'Skipped'),
    ('timeout', 'Timeout'),
]


class CronTaskLog(models.Model):
    _name = 'cron.task.log'
    _description = 'Scheduled Action Run Log'
    _order = 'date_start desc, id desc'

    cron_id = fields.Many2one('ir.cron', string='Scheduled Action', required=True, readonly=True,
                              index=True, ondelete='cascade')
    date_start = fields.Datetime('Started', required=True, readonly=True)
    date_end = fields.Datetime('Ended', readonly=True)
    duration = fields.Float('Duration (s)', compute='_compute_duration', store=True,
                            aggregator='avg', digits=(16, 1))
    status = fields.Selection(LOG_STATUS, required=True, readonly=True, default='running', index=True)
    trigger_type = fields.Selection([('scheduled', 'Scheduled'), ('manual', 'Manual')], string='Trigger',
                                    required=True, readonly=True, default='scheduled')
    traceback = fields.Text(readonly=True)
    error_summary = fields.Char('Error', readonly=True)
    record_count = fields.Integer('Records Processed', readonly=True, aggregator='sum')
    message = fields.Text(readonly=True)
    user_id = fields.Many2one('res.users', string='Run As', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True, index=True)
    rerun_of_id = fields.Many2one('cron.task.log', string='Re-run Of', readonly=True, ondelete='set null')
    rerun_ids = fields.One2many('cron.task.log', 'rerun_of_id', string='Re-runs')

    _record_count_positive = models.Constraint(
        'CHECK(record_count >= 0)', 'Records processed cannot be negative.')
    _date_order = models.Constraint(
        'CHECK(date_end IS NULL OR date_end >= date_start)', 'End must be after start.')
    _cron_date_idx = models.Index('(cron_id, date_start DESC)')
    _status_date_idx = models.Index('(status, date_start)')

    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for log in self:
            if log.date_start and log.date_end:
                log.duration = (log.date_end - log.date_start).total_seconds()
            else:
                log.duration = 0.0

    @api.depends('cron_id.name', 'date_start')
    def _compute_display_name(self):
        for log in self:
            log.display_name = '%s - %s' % (log.cron_id.name or '', format_datetime(self.env, log.date_start))

    @staticmethod
    def _summarize_traceback(text):
        lines = [line.strip() for line in (text or '').splitlines() if line.strip()]
        return lines[-1][:255] if lines else False

    @api.model
    def _get_positive_param(self, key, default):
        """Positive integer system parameter, ``default`` when unset or invalid."""
        value = self.env['ir.config_parameter'].sudo().get_param(key)
        try:
            value = int(value)
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    @api.model
    def log_progress(self, processed=None, message=None, skipped=False):
        """Report progress from inside a cron method.

        :param int processed: records processed, added to ``record_count``
        :param str message: note appended to ``message``
        :param bool skipped: mark the run as skipped (nothing to do)
        :return: False when no logged run is active, True otherwise
        """
        run = getattr(CRON_LOG_LOCAL, 'run', None)
        if not run:
            return False
        if skipped:
            run['skipped'] = True
        if processed or message:
            with self.env['ir.cron']._cron_log_env() as env:
                log = env['cron.task.log'].browse(run['log_id']).exists()
                vals = {}
                if processed:
                    vals['record_count'] = log.record_count + int(processed)
                if message:
                    vals['message'] = '%s\n%s' % (log.message, message) if log.message else str(message)
                log.write(vals)
        return True

    def action_rerun(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(self.env._("Only Settings administrators can re-run scheduled actions."))
        if self.status not in ('failed', 'timeout'):
            raise UserError(self.env._("Only failed or timed-out runs can be re-run."))
        return self.cron_id.with_context(cron_task_log_rerun_of=self.id).method_direct_trigger()

    def action_open_cron(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.cron',
            'res_id': self.cron_id.id,
            'view_mode': 'form',
        }

    def _post_failure_alerts(self):
        """Post a message on the alert channel of the failed / timed-out runs."""
        for log in self.sudo().filtered(lambda rec: rec.cron_id.log_alert_channel_id):
            status = dict(LOG_STATUS)[log.status]
            body = Markup(
                '<p><strong>%s</strong> %s: %s</p><p>%s</p><p><a href="%s">%s</a></p>'
            ) % (
                self.env._("Scheduled action"), log.cron_id.name, status,
                log.error_summary or '',
                '/odoo/action-ydod_base_cron_task_log.action_cron_task_log/%s' % log.id,
                self.env._("Open run log"),
            )
            log.cron_id.log_alert_channel_id.message_post(
                body=body, message_type='comment', subtype_xmlid='mail.mt_comment')

    @api.model
    def _cron_mark_timeouts(self):
        """Turn runs that never reported a result (killed worker) into timeouts."""
        minutes = self._get_positive_param('ydod_base_cron_task_log.timeout_minutes', 60)
        limit = fields.Datetime.now() - timedelta(minutes=minutes)
        logs = self.sudo().search([('status', '=', 'running'), ('date_start', '<', limit)])
        if logs:
            logs.write({
                'status': 'timeout',
                'error_summary': self.env._(
                    "No result after %(minutes)s minutes: the worker was probably killed "
                    "(limit_time_real) or the server restarted.", minutes=minutes),
            })
            logs._post_failure_alerts()
        return len(logs)

    @api.model
    def _cron_purge_logs(self):
        """Delete old logs with one statement, honouring per-job overrides."""
        success_days = self._get_positive_param('ydod_base_cron_task_log.success_retention_days', 30)
        failed_days = self._get_positive_param('ydod_base_cron_task_log.failed_retention_days', 90)
        self.env.flush_all()
        self.env.cr.execute(SQL(
            """
            DELETE FROM cron_task_log log
             USING ir_cron cron
             WHERE log.cron_id = cron.id
               AND ((log.status IN ('success', 'skipped')
                     AND log.date_start < %(now)s - make_interval(
                         days => COALESCE(NULLIF(cron.log_retention_success_days, 0), %(success)s)))
                 OR (log.status IN ('failed', 'timeout')
                     AND log.date_start < %(now)s - make_interval(
                         days => COALESCE(NULLIF(cron.log_retention_failed_days, 0), %(failed)s))))
            """,
            now=fields.Datetime.now(), success=success_days, failed=failed_days,
        ))
        deleted = self.env.cr.rowcount
        self.invalidate_model()
        return deleted
