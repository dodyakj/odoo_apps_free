from odoo import api, fields, models


class PurchasePriceDeviationWizard(models.TransientModel):
    _name = 'purchase.price.deviation.wizard'
    _description = "Approve Purchase Price Deviation"

    order_ids = fields.Many2many('purchase.order', string="Orders", required=True)
    line_ids = fields.Many2many(
        'purchase.order.line', string="Deviating Lines", compute='_compute_line_ids')
    justification = fields.Text(
        string="Justification", required=True,
        help="Why the higher prices are accepted. Logged in the chatter of each order.")

    @api.depends('order_ids')
    def _compute_line_ids(self):
        for wizard in self:
            wizard.line_ids = wizard.order_ids.order_line.filtered(
                lambda l: l.price_deviation_level == 'flagged')

    def action_approve(self):
        self.ensure_one()
        self.order_ids._approve_price_deviation(self.justification)
        return {'type': 'ir.actions.act_window_close'}
