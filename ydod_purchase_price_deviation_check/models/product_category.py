from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    price_deviation_override = fields.Boolean(
        string="Custom Price Tolerance",
        help="Use a specific purchase price tolerance for this category and its sub-categories "
             "instead of the company default.")
    price_deviation_tolerance = fields.Float(string="Price Tolerance (%)", default=10.0)
    price_deviation_tolerance_amount = fields.Float(
        string="Price Tolerance Amount", digits='Product Price',
        help="Optional minimum increase per unit, in company currency.")

    def _get_price_deviation_tolerance(self, company):
        """ Return (percent, amount) of the closest category with an override,
        or the company defaults. """
        categ = self
        while categ:
            if categ.price_deviation_override:
                return categ.price_deviation_tolerance, categ.price_deviation_tolerance_amount
            categ = categ.parent_id
        return company.price_deviation_tolerance, company.price_deviation_tolerance_amount
