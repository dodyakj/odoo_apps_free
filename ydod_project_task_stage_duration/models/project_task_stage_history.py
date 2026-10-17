from odoo import api, fields, models


class ProjectTaskStageHistory(models.Model):
    _name = 'project.task.stage.history'
    _description = 'Project Task Stage History'
    _order = 'date_start desc, id desc'

    task_id = fields.Many2one(
        'project.task',
        string='Task',
        required=True,
        ondelete='cascade',
        index=True,
    )
    stage_id = fields.Many2one(
        'project.task.type',
        string='Stage',
        required=True,
        ondelete='restrict',
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        related='task_id.project_id',
        store=True,
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        readonly=True,
        default=lambda self: self.env.user,
    )
    date_start = fields.Datetime(
        string='Date Start',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )
    date_end = fields.Datetime(
        string='Date End',
        readonly=True,
    )
    duration_hours = fields.Float(
        string='Duration (Hours)',
        readonly=True,
        aggregator='avg',
        digits=(16, 2),
    )
    duration_days = fields.Float(
        string='Duration (Days)',
        compute='_compute_duration_days',
        store=True,
        aggregator='avg',
        digits=(16, 2),
    )
    is_current = fields.Boolean(
        string='Current Stage',
        default=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    _check_date_order = models.Constraint(
        'CHECK(date_end IS NULL OR date_end >= date_start)',
        'Stage exit timestamp must be greater than or equal to enter timestamp.',
    )
    _task_is_current_idx = models.Index('(task_id, is_current)')

    @api.depends('duration_hours')
    def _compute_duration_days(self):
        for record in self:
            record.duration_days = round((record.duration_hours or 0.0) / 24.0, 2)

    def _compute_display_name(self):
        for record in self:
            task_name = record.task_id.name or ''
            stage_name = record.stage_id.name or ''
            record.display_name = f"{task_name} - {stage_name}" if task_name else stage_name
