from odoo import fields, models


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    max_duration_hours = fields.Float(
        string='Max Duration (Hours)',
        default=0.0,
        help='Maximum allowed duration in hours before stage is considered bottleneck (0 for unlimited).',
    )

    _sql_constraints = [
        (
            'check_max_duration_hours',
            'CHECK(max_duration_hours >= 0)',
            'Maximum duration threshold must be non-negative.',
        ),
    ]
