from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    price_deviation_check = fields.Boolean(
        string="Price Deviation Check", default=True,
        help="Flag purchase order lines priced above their reference price and require manager approval.")
    price_deviation_tolerance = fields.Float(
        string="Price Tolerance (%)", default=10.0,
        help="Maximum accepted increase over the reference price, in percent.")
    price_deviation_tolerance_amount = fields.Monetary(
        string="Price Tolerance Amount", currency_field='currency_id',
        help="Optional minimum increase per unit (company currency) before a line is flagged. "
             "Avoids alerts on cheap items where a small change is a large percentage.")
