from datetime import timedelta

from odoo import api, fields, models
from odoo.orm.domains import Domain


class ProjectTask(models.Model):
    _inherit = 'project.task'

    stage_history_ids = fields.One2many(
        'project.task.stage.history',
        'task_id',
        string='Stage History',
        readonly=True,
    )
    stage_entered_date = fields.Datetime(
        string='Stage Entered Date',
        readonly=True,
        copy=False,
    )
    current_stage_duration_hours = fields.Float(
        string='Time in Stage (Hours)',
        compute='_compute_current_stage_duration',
        aggregator='avg',
        store=False,
    )
    current_stage_duration_display = fields.Char(
        string='Time in Current Stage',
        compute='_compute_current_stage_duration',
        store=False,
    )
    is_stage_bottleneck = fields.Boolean(
        string='Is Bottleneck',
        compute='_compute_is_stage_bottleneck',
        search='_search_is_stage_bottleneck',
        store=False,
    )

    @api.model
    def _format_duration(self, hours):
        if not hours or hours <= 0:
            return "0m"
        total_seconds = int(hours * 3600)
        days = total_seconds // 86400
        rem_hours = (total_seconds % 86400) // 3600
        rem_mins = (total_seconds % 3600) // 60
        if days > 0:
            return f"{days}d {rem_hours}h"
        if rem_hours > 0:
            return f"{rem_hours}h {rem_mins}m"
        if rem_mins > 0:
            return f"{rem_mins}m"
        return "< 1m"

    @api.depends('stage_entered_date')
    def _compute_current_stage_duration(self):
        now = fields.Datetime.now()
        for task in self:
            if task.stage_entered_date:
                total_seconds = max(0.0, (now - task.stage_entered_date).total_seconds())
                duration_hours = round(total_seconds / 3600.0, 2)
                task.current_stage_duration_hours = duration_hours
                task.current_stage_duration_display = self._format_duration(duration_hours)
            else:
                task.current_stage_duration_hours = 0.0
                task.current_stage_duration_display = ""

    @api.depends('stage_entered_date', 'stage_id.max_duration_hours')
    def _compute_is_stage_bottleneck(self):
        now = fields.Datetime.now()
        for task in self:
            if task.stage_id.max_duration_hours > 0 and task.stage_entered_date:
                elapsed_hours = max(0.0, (now - task.stage_entered_date).total_seconds() / 3600.0)
                task.is_stage_bottleneck = elapsed_hours > task.stage_id.max_duration_hours
            else:
                task.is_stage_bottleneck = False

    def _search_is_stage_bottleneck(self, operator, value):
        if operator in ('=', '!='):
            positive = (operator == '=') == bool(value)
        elif operator == 'in':
            positive = True in value and False not in value
        else:
            return NotImplemented

        stages = self.env['project.task.type'].sudo().search([('max_duration_hours', '>', 0)])
        if not stages:
            return [('id', '!=', False)] if not positive else [('id', '=', False)]

        now = fields.Datetime.now()
        domain_parts = []
        for stage in stages:
            cutoff = now - timedelta(hours=stage.max_duration_hours)
            domain_parts.append([
                ('stage_id', '=', stage.id),
                ('stage_entered_date', '!=', False),
                ('stage_entered_date', '<=', cutoff),
            ])
        bottleneck_domain = Domain.OR(domain_parts)
        return list(bottleneck_domain) if positive else list(~bottleneck_domain)

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if 'stage_entered_date' not in vals:
                vals['stage_entered_date'] = now
        tasks = super().create(vals_list)
        history_vals = []
        for task in tasks:
            if task.stage_id:
                history_vals.append({
                    'task_id': task.id,
                    'stage_id': task.stage_id.id,
                    'user_id': self.env.user.id,
                    'date_start': task.stage_entered_date or now,
                    'is_current': True,
                    'company_id': task.company_id.id or self.env.company.id,
                })
            else:
                task.stage_entered_date = False
        if history_vals:
            self.env['project.task.stage.history'].sudo().create(history_vals)
        return tasks

    def write(self, vals):
        if 'stage_id' not in vals:
            return super().write(vals)

        new_stage_id = vals['stage_id']
        now = fields.Datetime.now()
        new_stage = self.env['project.task.type'].browse(new_stage_id) if new_stage_id else False

        changing_tasks = self.filtered(lambda t: t.stage_id.id != new_stage_id)
        if not changing_tasks:
            return super().write(vals)

        active_histories = self.env['project.task.stage.history'].sudo().search([
            ('task_id', 'in', changing_tasks.ids),
            ('is_current', '=', True),
        ])
        histories_by_task = {h.task_id.id: h for h in active_histories}

        old_stage_info = {}
        for task in changing_tasks:
            old_stage = task.stage_id
            active_h = histories_by_task.get(task.id)
            if active_h:
                start_dt = active_h.date_start or task.stage_entered_date or now
                duration_hours = round(max(0.0, (now - start_dt).total_seconds()) / 3600.0, 2)
                active_h.write({
                    'date_end': now,
                    'duration_hours': duration_hours,
                    'is_current': False,
                })
                old_stage_info[task.id] = (old_stage, duration_hours)
            elif old_stage:
                start_dt = task.stage_entered_date or now
                duration_hours = round(max(0.0, (now - start_dt).total_seconds()) / 3600.0, 2)
                old_stage_info[task.id] = (old_stage, duration_hours)
            else:
                old_stage_info[task.id] = (False, 0.0)

        write_vals = dict(vals)
        if 'stage_entered_date' not in write_vals:
            write_vals['stage_entered_date'] = now if new_stage_id else False

        res = super(ProjectTask, changing_tasks).write(write_vals)
        other_tasks = self - changing_tasks
        if other_tasks:
            super(ProjectTask, other_tasks).write(vals)

        if new_stage_id:
            new_histories = []
            for task in changing_tasks:
                new_histories.append({
                    'task_id': task.id,
                    'stage_id': new_stage_id,
                    'user_id': self.env.user.id,
                    'date_start': now,
                    'is_current': True,
                    'company_id': task.company_id.id or self.env.company.id,
                })
            if new_histories:
                self.env['project.task.stage.history'].sudo().create(new_histories)

        for task in changing_tasks:
            old_stage, dur_hours = old_stage_info.get(task.id, (False, 0.0))
            if old_stage and new_stage:
                dur_text = task._format_duration(dur_hours)
                body = self.env._(
                    "Stage changed from <b>%(old_stage)s</b> to <b>%(new_stage)s</b>.<br/>Time spent in %(old_stage)s: <b>%(duration)s</b> (%(hours).2f hours).",
                    old_stage=old_stage.name,
                    new_stage=new_stage.name,
                    duration=dur_text,
                    hours=dur_hours,
                )
            elif new_stage:
                body = self.env._("Stage set to <b>%(new_stage)s</b>.", new_stage=new_stage.name)
            else:
                body = self.env._("Stage removed (previously <b>%(old_stage)s</b>).", old_stage=old_stage.name)

            task.message_post(body=body, subtype_xmlid='mail.mt_note')

        return res
