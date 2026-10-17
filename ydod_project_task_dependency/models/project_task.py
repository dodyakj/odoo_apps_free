from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    predecessor_ids = fields.Many2many(
        'project.task',
        'project_task_predecessor_rel',
        'task_id',
        'predecessor_id',
        string='Predecessors',
        check_company=True,
        help="Tasks that must be completed before this task can be finished."
    )
    successor_ids = fields.Many2many(
        'project.task',
        'project_task_predecessor_rel',
        'predecessor_id',
        'task_id',
        string='Successors',
        check_company=True,
        help="Tasks that are waiting for this task to be completed."
    )
    is_blocked = fields.Boolean(
        string='Is Blocked',
        compute='_compute_is_blocked',
        store=True,
        recursive=True
    )
    blocked_count = fields.Integer(
        string='Predecessor Count',
        compute='_compute_dependency_counts'
    )
    blocking_count = fields.Integer(
        string='Successor Count',
        compute='_compute_dependency_counts'
    )

    @api.depends('predecessor_ids', 'predecessor_ids.state')
    def _compute_is_blocked(self):
        for task in self:
            task.is_blocked = any(
                p.state not in ('1_done', '1_canceled')
                for p in task.predecessor_ids
            )

    @api.depends('predecessor_ids', 'successor_ids')
    def _compute_dependency_counts(self):
        for task in self:
            task.blocked_count = len(task.predecessor_ids)
            task.blocking_count = len(task.successor_ids)

    @api.constrains('predecessor_ids')
    def _check_dependency_recursion(self):
        for task in self:
            visited = set()
            stack = list(task.predecessor_ids)
            while stack:
                current = stack.pop()
                if current.id == task.id:
                    raise ValidationError(self.env._(
                        "Recursive dependency detected: task '%(task_name)s' cannot depend on itself directly or indirectly.",
                        task_name=task.name,
                    ))
                if current.id not in visited:
                    visited.add(current.id)
                    stack.extend(current.predecessor_ids)

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        for task in tasks:
            if task.state == '1_done' and task.is_blocked:
                blocking_tasks = task.predecessor_ids.filtered(
                    lambda p: p.state not in ('1_done', '1_canceled')
                )
                task_names = ", ".join(blocking_tasks.mapped('name'))
                raise ValidationError(self.env._(
                    "Task '%(task_name)s' is blocked by unfinished predecessor tasks: %(blocking_tasks)s.",
                    task_name=task.name,
                    blocking_tasks=task_names,
                ))
        return tasks

    def write(self, vals):
        blocked_before = {}
        if vals.get('state') in ('1_done', '1_canceled'):
            for task in self:
                for successor in task.successor_ids:
                    blocked_before[successor.id] = successor.is_blocked

        res = super().write(vals)

        if vals.get('state') == '1_done' or ('predecessor_ids' in vals and any(t.state == '1_done' for t in self)):
            for task in self:
                if task.state == '1_done' and task.is_blocked:
                    blocking_tasks = task.predecessor_ids.filtered(
                        lambda p: p.state not in ('1_done', '1_canceled')
                    )
                    task_names = ", ".join(blocking_tasks.mapped('name'))
                    raise ValidationError(self.env._(
                        "Task '%(task_name)s' is blocked by unfinished predecessor tasks: %(blocking_tasks)s. Please complete them first.",
                        task_name=task.name,
                        blocking_tasks=task_names,
                    ))

        if vals.get('state') in ('1_done', '1_canceled'):
            for task in self:
                for successor in task.successor_ids:
                    if blocked_before.get(successor.id) and not successor.is_blocked:
                        successor.message_post(
                            body=self.env._(
                                "Dependency resolved: This task is now unblocked because predecessor task '%(task_name)s' has been completed.",
                                task_name=task.name,
                            )
                        )
        return res

    def action_view_predecessors(self):
        self.ensure_one()
        return {
            'name': self.env._('Predecessor Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.predecessor_ids.ids)],
            'context': {
                'default_successor_ids': [(4, self.id)],
                'default_project_id': self.project_id.id,
            },
        }

    def action_view_successors(self):
        self.ensure_one()
        return {
            'name': self.env._('Successor Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.successor_ids.ids)],
            'context': {
                'default_predecessor_ids': [(4, self.id)],
                'default_project_id': self.project_id.id,
            },
        }
