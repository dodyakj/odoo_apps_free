from odoo import api, fields, models


class SaleCommissionLine(models.Model):
    _name = 'sale.commission.line'
    _description = 'Sales Commission Line'
    _inherit = ['mail.thread']
    _order = 'date_order desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True, default=lambda self: self.env._('New'),
    )
    sale_order_id = fields.Many2one(
        'sale.order', string='Sales Order', required=True, ondelete='cascade', index=True,
    )
    partner_id = fields.Many2one(related='sale_order_id.partner_id', string='Customer', store=True)
    plan_id = fields.Many2one('sale.commission.plan', string='Commission Plan')
    user_id = fields.Many2one('res.users', string='Salesperson', required=True, tracking=True)
    team_id = fields.Many2one('crm.team', string='Sales Team')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Currency', store=True)
    date_order = fields.Date(string='Order Date')
    base_amount = fields.Monetary(string='Base Amount (Untaxed)', required=True)
    rate = fields.Float(string='Rate (%)', required=True)
    commission_amount = fields.Monetary(string='Commission', required=True, tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('locked', 'Locked'),
            ('paid', 'Paid'),
        ],
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._('New')) == self.env._('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.commission.line') or self.env._('New')
            if 'commission_amount' not in vals:
                vals['commission_amount'] = vals.get('base_amount', 0.0) * vals.get('rate', 0.0) / 100.0
        return super().create(vals_list)

    def action_recompute(self):
        for line in self:
            if line.state == 'draft':
                line.commission_amount = line.base_amount * line.rate / 100.0

    def action_lock(self):
        self.filtered(lambda line: line.state == 'draft').write({'state': 'locked'})

    def action_reset_to_draft(self):
        self.filtered(lambda line: line.state != 'paid').write({'state': 'draft'})

    def action_mark_paid(self):
        self.write({'state': 'paid'})
