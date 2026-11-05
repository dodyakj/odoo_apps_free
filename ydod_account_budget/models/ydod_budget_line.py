from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import ValidationError

REFRESH_TRIGGER_FIELDS = {'analytic_account_id', 'general_account_ids', 'date_from', 'date_to', 'planned_amount'}


class YdodBudgetLine(models.Model):
    _name = 'ydod.budget.line'
    _description = 'Budget Line'
    _order = 'budget_id desc, date_from, id'
    _rec_name = 'position_name'

    budget_id = fields.Many2one('ydod.budget', string='Budget', required=True, ondelete='cascade', index=True)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account', required=True, index=True,
        domain="[('company_id', 'in', [company_id, False])]",
    )
    position_name = fields.Char(string='Position', required=True)
    general_account_ids = fields.Many2many(
        'account.account', 'ydod_budget_line_account_rel', 'line_id', 'account_id',
        string='General Accounts',
        help="Journal accounts included in this position. Leave empty to include all accounts.",
    )
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    company_id = fields.Many2one(related='budget_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='budget_id.currency_id')
    state = fields.Selection(related='budget_id.state', store=True, string='Status')
    user_id = fields.Many2one(related='budget_id.user_id', store=True, string='Responsible')
    planned_amount = fields.Monetary(
        required=True, default=0.0,
        help="Negative for expenses, positive for revenue.",
    )
    actual_amount = fields.Monetary(readonly=True, copy=False, aggregator='sum')
    theoretical_amount = fields.Monetary(readonly=True, copy=False, aggregator='sum')
    achievement_percent = fields.Float(
        string='Achievement (%)', compute='_compute_achievement', store=True, aggregator=None,
    )
    is_over_budget = fields.Boolean(string='Over Budget', compute='_compute_achievement', store=True)

    _check_dates = models.Constraint(
        'CHECK(date_to >= date_from)',
        'The line end date must be on or after its start date.',
    )
    _budget_analytic_idx = models.Index('(budget_id, analytic_account_id)')

    @api.depends('planned_amount', 'actual_amount', 'theoretical_amount')
    def _compute_achievement(self):
        for line in self:
            theoretical = line.theoretical_amount
            line.achievement_percent = line.actual_amount / theoretical * 100.0 if theoretical else 0.0
            line.is_over_budget = line.planned_amount < 0 and line.actual_amount < theoretical

    @api.onchange('budget_id')
    def _onchange_budget_id(self):
        for line in self:
            if line.budget_id:
                line.date_from = line.budget_id.date_from
                line.date_to = line.budget_id.date_to

    @api.constrains('date_from', 'date_to', 'budget_id')
    def _check_dates_in_budget(self):
        for line in self:
            budget = line.budget_id
            if line.date_to < line.date_from:
                raise ValidationError(self.env._("The line end date must be on or after its start date."))
            if line.date_from < budget.date_from or line.date_to > budget.date_to:
                raise ValidationError(self.env._(
                    "The dates of line '%(line)s' must lie within the budget period %(start)s - %(end)s.",
                    line=line.position_name, start=budget.date_from, end=budget.date_to,
                ))

    @api.constrains('analytic_account_id', 'budget_id')
    def _check_analytic_company(self):
        for line in self:
            company = line.analytic_account_id.company_id
            if company and company != line.budget_id.company_id:
                raise ValidationError(self.env._(
                    "The analytic account %s belongs to another company than the budget.",
                    line.analytic_account_id.display_name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        budgets = self.env['ydod.budget'].browse({vals['budget_id'] for vals in vals_list if vals.get('budget_id')})
        budget_by_id = {budget.id: budget for budget in budgets}
        for vals in vals_list:
            budget = budget_by_id.get(vals.get('budget_id'))
            if budget:
                if not vals.get('date_from'):
                    vals['date_from'] = budget.date_from
                if not vals.get('date_to'):
                    vals['date_to'] = budget.date_to
        lines = super().create(vals_list)
        lines._refresh_amounts()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if REFRESH_TRIGGER_FIELDS & set(vals):
            self._refresh_amounts()
        return res

    # ------------------------------------------------------------------
    # Amounts
    # ------------------------------------------------------------------
    def _get_today(self):
        return fields.Date.context_today(self)

    @api.model
    def _posted_domain(self):
        return ['|', ('move_line_id', '=', False), ('move_line_id.parent_state', '=', 'posted')]

    def _get_theoretical_amount(self, today):
        self.ensure_one()
        if not self.date_from or not self.date_to or today < self.date_from:
            return 0.0
        if today >= self.date_to:
            return self.planned_amount
        total_days = (self.date_to - self.date_from).days + 1
        elapsed_days = (today - self.date_from).days + 1
        return self.planned_amount * elapsed_days / total_days

    def _refresh_amounts(self):
        """Recompute actual and theoretical amounts with one grouped query per analytic plan column."""
        lines = self.exists().filtered(lambda l: l.date_from and l.date_to and l.analytic_account_id)
        if not lines:
            return
        today = self._get_today()
        AnalyticLine = self.env['account.analytic.line'].sudo()
        accounts_by_column = defaultdict(set)
        for account in lines.analytic_account_id.sudo():
            accounts_by_column[account.plan_id._column_name()].add(account.id)

        # {analytic account id: [(general account id, company id, day, amount)]}
        items = defaultdict(list)
        date_min = min(lines.mapped('date_from'))
        date_max = max(lines.mapped('date_to'))
        for column, account_ids in accounts_by_column.items():
            if column not in AnalyticLine._fields:
                continue
            domain = [
                (column, 'in', list(account_ids)),
                ('date', '>=', date_min),
                ('date', '<=', date_max),
                ('company_id', 'in', lines.company_id.ids),
            ] + self._posted_domain()
            groups = AnalyticLine._read_group(
                domain, [column, 'general_account_id', 'company_id', 'date:day'], ['amount:sum'],
            )
            for analytic, general, company, day, amount in groups:
                items[analytic.id].append((general.id, company.id, fields.Date.to_date(day), amount))

        values = defaultdict(lambda: self.browse())
        for line in lines:
            general_ids = set(line.general_account_ids.ids)
            actual = sum(
                amount
                for general_id, company_id, day, amount in items.get(line.analytic_account_id.id, ())
                if company_id == line.company_id.id
                and line.date_from <= day <= line.date_to
                and (not general_ids or general_id in general_ids)
            )
            currency = line.currency_id or self.env.company.currency_id
            key = (currency.round(actual), currency.round(line._get_theoretical_amount(today)))
            values[key] |= line
        for (actual, theoretical), group in values.items():
            group.sudo().write({'actual_amount': actual, 'theoretical_amount': theoretical})

    @api.model
    def _cron_refresh_amounts(self, batch_size=1000):
        lines = self.search([('state', 'in', ('confirm', 'validate'))])
        for company, company_lines in lines.grouped('company_id').items():
            for start in range(0, len(company_lines), batch_size):
                company_lines[start:start + batch_size].with_company(company)._refresh_amounts()

    def _get_analytic_domain(self):
        self.ensure_one()
        column = self.analytic_account_id.sudo().plan_id._column_name()
        domain = [
            (column, '=', self.analytic_account_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
        ] + self._posted_domain()
        if self.general_account_ids:
            domain.append(('general_account_id', 'in', self.general_account_ids.ids))
        return domain

    def action_open_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Analytic Items: %s", self.position_name),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form',
            'domain': self._get_analytic_domain(),
            'context': {'create': False},
        }
