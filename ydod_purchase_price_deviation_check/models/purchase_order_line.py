from odoo import api, fields, models
from odoo.tools.float_utils import float_compare


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    price_reference = fields.Float(
        string="Reference Price", digits='Product Price', compute='_compute_price_deviation', store=True,
        help="Net unit price of the last confirmed purchase of this product (falling back to the vendor "
             "pricelist), converted to the unit and currency of this line.")
    price_reference_source = fields.Selection(
        [('last_po', "Last Purchase"), ('pricelist', "Vendor Pricelist")],
        string="Reference Source", compute='_compute_price_deviation', store=True)
    price_deviation_rate = fields.Float(
        string="Price Deviation", compute='_compute_price_deviation', store=True, aggregator='max',
        help="Difference between the net unit price and the reference price.")
    price_deviation_level = fields.Selection(
        [('ok', "Within Tolerance"), ('flagged', "Above Tolerance")],
        string="Price Check", compute='_compute_price_deviation', store=True, index='btree_not_null')

    @api.depends('product_id', 'uom_id', 'product_qty', 'price_unit', 'discount', 'display_type',
                 'order_id.partner_id', 'order_id.currency_id', 'order_id.company_id')
    def _compute_price_deviation(self):
        for line in self:
            reference, source = line._get_price_deviation_reference()
            price = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            rate = (price - reference) / reference if reference else 0.0
            level = False
            company = line.company_id or line.env.company
            if reference and company.price_deviation_check:
                percent, amount = line.product_id.categ_id._get_price_deviation_tolerance(company)
                if amount:
                    amount = company.currency_id._convert(
                        amount, line.currency_id or company.currency_id, company,
                        line.order_id.date_order or fields.Date.context_today(line), round=False)
                exceeded = (
                    float_compare(rate * 100.0, percent, precision_digits=2) > 0
                    and float_compare(price - reference, amount, precision_digits=6) > 0
                )
                level = 'flagged' if exceeded else 'ok'
            line.price_reference = reference
            line.price_reference_source = source
            line.price_deviation_rate = rate
            line.price_deviation_level = level

    def _get_price_deviation_reference(self):
        """ Return (net unit price, source) used as reference for this line. """
        self.ensure_one()
        if self.display_type or self.is_downpayment or not self.product_id:
            return 0.0, False
        company = self.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        uom = self.uom_id or self.product_id.uom_id
        date = self.order_id.date_order or fields.Date.context_today(self)
        order = self.order_id._origin
        domain = [
            ('state', '=', 'purchase'),
            ('company_id', '=', company.id),
            ('order_line.product_id', '=', self.product_id.id),
        ]
        if order:
            domain.append(('id', '!=', order.id))
            if order.date_approve:
                domain.append(('date_approve', '<', order.date_approve))
        last_order = self.env['purchase.order'].sudo().search(domain, order='date_approve desc, id desc', limit=1)
        last_line = last_order.order_line.filtered(
            lambda l: l.product_id.id == self.product_id.id).sorted('id')[-1:]
        if last_line:
            price = last_line.price_unit * (1.0 - (last_line.discount or 0.0) / 100.0)
            price = last_line.currency_id._convert(price, currency, company, date, round=False)
            return last_line.uom_id._compute_price(price, uom), 'last_po'
        seller = self._get_seller_info() if self.order_id else {}
        if seller and seller.get('supplierinfo'):
            price = seller['price'] * (1.0 - (seller.get('discount') or 0.0) / 100.0)
            price = seller['currency_id']._convert(price, currency, company, date, round=False)
            return seller['uom_id']._compute_price(price, uom), 'pricelist'
        return 0.0, False
