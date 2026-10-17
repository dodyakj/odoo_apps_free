# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class YdodAccountBudget(models.Model):
    _name = 'ydod.account.budget'
    _description = "Financial Budget"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    _sql_constraints = [
        ('check_budget_dates', 'CHECK(date_from <= date_to)', 'Budget start date must precede end date.'),
    ]

    name = fields.Char(string="Budget Name", required=True, tracking=True)
    date_from = fields.Date(string="Start Date", required=True, tracking=True)
    date_to = fields.Date(string="End Date", required=True, tracking=True)
    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        string="Currency",
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('approved', 'Approved'),
            ('done', 'Done'),
            ('canceled', 'Canceled'),
        ],
        string="Status",
        default='draft',
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        comodel_name='ydod.account.budget.line',
        inverse_name='budget_id',
        string="Budget Lines",
    )
    total_planned_amount = fields.Monetary(
        string="Total Planned",
        compute='_compute_totals',
        currency_field='currency_id',
    )
    total_practical_amount = fields.Monetary(
        string="Total Actual",
        compute='_compute_totals',
        currency_field='currency_id',
    )
    total_percentage = fields.Float(
        string="Achievement %",
        compute='_compute_totals',
    )

    @api.depends('line_ids.planned_amount', 'line_ids.practical_amount')
    def _compute_totals(self):
        for budget in self:
            planned = sum(budget.line_ids.mapped('planned_amount'))
            actual = sum(budget.line_ids.mapped('practical_amount'))
            budget.total_planned_amount = planned
            budget.total_practical_amount = actual
            budget.total_percentage = (actual / planned * 100.0) if planned else 0.0

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError(_("Budget start date must precede end date."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            df = fields.Date.to_date(vals.get('date_from'))
            dt = fields.Date.to_date(vals.get('date_to'))
            if df and dt and df > dt:
                raise ValidationError(_("Budget start date must precede end date."))
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            df = fields.Date.to_date(vals.get('date_from', record.date_from))
            dt = fields.Date.to_date(vals.get('date_to', record.date_to))
            if df and dt and df > dt:
                raise ValidationError(_("Budget start date must precede end date."))
        return super().write(vals)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_cancel(self):
        self.write({'state': 'canceled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class YdodAccountBudgetLine(models.Model):
    _name = 'ydod.account.budget.line'
    _description = "Budget Line"

    budget_id = fields.Many2one(
        comodel_name='ydod.account.budget',
        string="Budget",
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(string="Description", required=True)
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Analytic Account",
    )
    account_ids = fields.Many2many(
        comodel_name='account.account',
        relation='ydod_budget_line_account_rel',
        column1='line_id',
        column2='account_id',
        string="Financial Accounts",
    )
    date_from = fields.Date(string="Start Date", required=True)
    date_to = fields.Date(string="End Date", required=True)
    planned_amount = fields.Monetary(
        string="Planned Amount",
        required=True,
        default=0.0,
        currency_field='currency_id',
    )
    practical_amount = fields.Monetary(
        string="Actual Amount",
        compute='_compute_practical_amount',
        store=True,
        currency_field='currency_id',
    )
    percentage = fields.Float(
        string="Achievement %",
        compute='_compute_percentage',
        store=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='budget_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='budget_id.currency_id',
        readonly=True,
    )

    @api.depends('budget_id.state', 'analytic_account_id', 'account_ids', 'date_from', 'date_to', 'planned_amount')
    def _compute_practical_amount(self):
        for line in self:
            if not line.date_from or not line.date_to or not line.company_id:
                line.practical_amount = 0.0
                continue

            # If analytic account specified, query account.analytic.line first
            if line.analytic_account_id:
                domain = [
                    ('account_id', '=', line.analytic_account_id.id),
                    ('date', '>=', line.date_from),
                    ('date', '<=', line.date_to),
                    ('company_id', '=', line.company_id.id),
                ]
                if line.account_ids:
                    domain.append(('general_account_id', 'in', line.account_ids.ids))
                groups = self.env['account.analytic.line'].read_group(domain, ['amount:sum'], [])
                actual = abs(groups[0]['amount'] or 0.0) if groups and groups[0].get('amount') else 0.0
            else:
                # Query move lines
                domain = [
                    ('company_id', '=', line.company_id.id),
                    ('date', '>=', line.date_from),
                    ('date', '<=', line.date_to),
                    ('parent_state', '=', 'posted'),
                ]
                if line.account_ids:
                    domain.append(('account_id', 'in', line.account_ids.ids))
                else:
                    domain.append(('account_id.internal_group', '=', 'expense'))
                groups = self.env['account.move.line'].read_group(domain, ['debit:sum'], [])
                actual = groups[0]['debit'] or 0.0 if groups and groups[0].get('debit') else 0.0

            line.practical_amount = actual

    @api.depends('planned_amount', 'practical_amount')
    def _compute_percentage(self):
        for line in self:
            if line.planned_amount:
                line.percentage = (line.practical_amount / line.planned_amount) * 100.0
            else:
                line.percentage = 0.0
