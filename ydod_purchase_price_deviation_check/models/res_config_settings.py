from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    price_deviation_check = fields.Boolean(
        related='company_id.price_deviation_check', readonly=False)
    price_deviation_tolerance = fields.Float(
        related='company_id.price_deviation_tolerance', readonly=False)
    price_deviation_tolerance_amount = fields.Monetary(
        related='company_id.price_deviation_tolerance_amount', readonly=False,
        currency_field='company_currency_id')
