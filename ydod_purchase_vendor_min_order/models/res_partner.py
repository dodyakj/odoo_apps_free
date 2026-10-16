from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    min_order_amount = fields.Monetary(
        string="Minimum Order Amount",
        currency_field="currency_id",
        help="Minimum total untaxed amount required for a purchase order to this vendor.",
    )
    min_order_quantity = fields.Float(
        string="Minimum Order Quantity",
        help="Minimum total product quantity required for a purchase order to this vendor.",
    )
