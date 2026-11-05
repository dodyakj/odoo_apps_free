from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MANAGER_GROUP = 'ydod_account_budget.group_budget_manager'


class YdodBudget(models.Model):
    _name = 'ydod.budget'
    _description = 'Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Responsible', tracking=True,
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    date_from = fields.Date(string='Start Date', required=True, tracking=True)
    date_to = fields.Date(string='End Date', required=True, tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirm', 'Confirmed'),
            ('validate', 'Validated'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        string='Status', required=True, default='draft', readonly=True,
        tracking=True, index=True, copy=False,
    )
    line_ids = fields.One2many('ydod.budget.line', 'budget_id', string='Budget Lines', copy=True)
    note = fields.Html(string='Notes')
    planned_total = fields.Monetary(string='Planned Amount', compute='_compute_totals', store=True)
    theoretical_total = fields.Monetary(string='Theoretical Amount', compute='_compute_totals', store=True)
    actual_total = fields.Monetary(string='Actual Amount', compute='_compute_totals', store=True)
    line_count = fields.Integer(compute='_compute_line_count')

    _check_dates = models.Constraint(
        'CHECK(date_to >= date_from)',
        'The budget end date must be on or after its start date.',
    )

    @api.depends('line_ids.planned_amount', 'line_ids.theoretical_amount', 'line_ids.actual_amount')
    def _compute_totals(self):
        for budget in self:
            budget.planned_total = sum(budget.line_ids.mapped('planned_amount'))
            budget.theoretical_total = sum(budget.line_ids.mapped('theoretical_amount'))
            budget.actual_total = sum(budget.line_ids.mapped('actual_amount'))

    @api.depends('line_ids')
    def _compute_line_count(self):
        for budget in self:
            budget.line_count = len(budget.line_ids)

    @api.constrains('date_from', 'date_to')
    def _check_line_dates(self):
        for budget in self:
            if budget.date_from and budget.date_to and budget.date_to < budget.date_from:
                raise ValidationError(self.env._("The budget end date must be on or after its start date."))
        self.line_ids._check_dates_in_budget()

    def unlink(self):
        if any(budget.state not in ('draft', 'cancel') for budget in self):
            raise UserError(self.env._("Only draft or cancelled budgets can be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _check_manager(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._("Only Budget Managers can change the status of a budget."))

    def _change_state(self, allowed_states, new_state):
        self._check_manager()
        if any(budget.state not in allowed_states for budget in self):
            raise UserError(self.env._("This action is not allowed in the current status of the budget."))
        self.write({'state': new_state})
        return True

    def action_confirm(self):
        return self._change_state(('draft',), 'confirm')

    def action_validate(self):
        return self._change_state(('confirm',), 'validate')

    def action_done(self):
        return self._change_state(('validate',), 'done')

    def action_cancel(self):
        return self._change_state(('draft', 'confirm', 'validate'), 'cancel')

    def action_draft(self):
        return self._change_state(('cancel',), 'draft')

    def action_refresh(self):
        if any(budget.state == 'cancel' for budget in self):
            raise UserError(self.env._("Cancelled budgets cannot be refreshed."))
        self.line_ids._refresh_amounts()
        return True

    def action_copy_next_period(self):
        self._check_manager()
        new_budgets = self.browse()
        for budget in self:
            if budget.state not in ('validate', 'done'):
                raise UserError(self.env._("Only validated or done budgets can be copied to the next period."))
            delta = relativedelta(budget.date_to + timedelta(days=1), budget.date_from)
            new_budgets |= budget.copy({
                'name': self.env._("%s (Next Period)", budget.name),
                'date_from': budget.date_from + delta,
                'date_to': budget.date_to + delta,
                'line_ids': [Command.create({
                    'analytic_account_id': line.analytic_account_id.id,
                    'position_name': line.position_name,
                    'general_account_ids': [Command.set(line.general_account_ids.ids)],
                    'date_from': line.date_from + delta,
                    'date_to': line.date_to + delta,
                    'planned_amount': line.planned_amount,
                }) for line in budget.line_ids],
            })
        action = {
            'type': 'ir.actions.act_window',
            'name': self.env._("Budgets"),
            'res_model': 'ydod.budget',
        }
        if len(new_budgets) == 1:
            action.update(view_mode='form', res_id=new_budgets.id)
        else:
            action.update(view_mode='list,form', domain=[('id', 'in', new_budgets.ids)])
        return action

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Budget Lines"),
            'res_model': 'ydod.budget.line',
            'view_mode': 'list,form,pivot,graph',
            'domain': [('budget_id', '=', self.id)],
            'context': {'default_budget_id': self.id},
        }
