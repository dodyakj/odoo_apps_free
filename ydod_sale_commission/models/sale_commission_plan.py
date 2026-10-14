from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleCommissionPlan(models.Model):
    _name = 'sale.commission.plan'
    _description = 'Sales Commission Plan'
    _order = 'scope, name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    scope = fields.Selection(
        [
            ('user', 'Salesperson'),
            ('team', 'Sales Team'),
            ('company', 'Company (Default)'),
        ],
        string='Applies To',
        required=True,
        default='company',
    )
    user_id = fields.Many2one('res.users', string='Salesperson')
    team_id = fields.Many2one('crm.team', string='Sales Team')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company,
    )
    rate = fields.Float(string='Commission Rate (%)', required=True, default=5.0)

    @api.onchange('scope')
    def _onchange_scope(self):
        if self.scope != 'user':
            self.user_id = False
        if self.scope != 'team':
            self.team_id = False

    @api.constrains('scope', 'user_id', 'team_id')
    def _check_scope_consistency(self):
        for plan in self:
            if plan.scope == 'user' and not plan.user_id:
                raise ValidationError(self.env._("Select a salesperson for a salesperson-scoped commission plan."))
            if plan.scope == 'team' and not plan.team_id:
                raise ValidationError(self.env._("Select a sales team for a team-scoped commission plan."))

    @api.constrains('rate')
    def _check_rate(self):
        for plan in self:
            if not (0 <= plan.rate <= 100):
                raise ValidationError(self.env._("The commission rate must be between 0 and 100."))

    @api.model
    def _get_applicable_plan(self, order):
        """Return the most specific active commission plan for a confirmed sale order."""
        company_domain = [('company_id', '=', order.company_id.id)]
        if order.user_id:
            plan = self.search(
                company_domain + [('scope', '=', 'user'), ('user_id', '=', order.user_id.id)], limit=1,
            )
            if plan:
                return plan
        if order.team_id:
            plan = self.search(
                company_domain + [('scope', '=', 'team'), ('team_id', '=', order.team_id.id)], limit=1,
            )
            if plan:
                return plan
        return self.search(company_domain + [('scope', '=', 'company')], limit=1)
