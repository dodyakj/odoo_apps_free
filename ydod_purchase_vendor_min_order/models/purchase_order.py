from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    vendor_min_order_amount = fields.Monetary(
        string="Vendor Minimum Amount",
        related="partner_id.min_order_amount",
        currency_field="currency_id",
        readonly=True,
    )
    vendor_min_order_quantity = fields.Float(
        string="Vendor Minimum Quantity",
        related="partner_id.min_order_quantity",
        readonly=True,
    )

    total_ordered_qty = fields.Float(
        string="Total Ordered Quantity",
        compute="_compute_total_ordered_qty",
        store=True,
    )
    meets_min_amount = fields.Boolean(
        string="Meets Minimum Amount",
        compute="_compute_meets_minimums",
        store=True,
    )
    meets_min_quantity = fields.Boolean(
        string="Meets Minimum Quantity",
        compute="_compute_meets_minimums",
        store=True,
    )
    meets_minimums = fields.Boolean(
        string="Meets All Minimums",
        compute="_compute_meets_minimums",
        store=True,
    )

    @api.depends("order_line.product_qty")
    def _compute_total_ordered_qty(self):
        for order in self:
            order.total_ordered_qty = sum(order.order_line.mapped("product_qty"))

    @api.depends(
        "amount_untaxed",
        "total_ordered_qty",
        "vendor_min_order_amount",
        "vendor_min_order_quantity",
        "currency_id",
    )
    def _compute_meets_minimums(self):
        for order in self:
            rounding = order.currency_id.rounding if order.currency_id else 0.01
            order.meets_min_amount = (
                not order.vendor_min_order_amount
                or float_compare(
                    order.amount_untaxed,
                    order.vendor_min_order_amount,
                    precision_rounding=rounding,
                ) >= 0
            )
            order.meets_min_quantity = (
                not order.vendor_min_order_quantity
                or float_compare(
                    order.total_ordered_qty,
                    order.vendor_min_order_quantity,
                    precision_digits=2,
                ) >= 0
            )
            order.meets_minimums = order.meets_min_amount and order.meets_min_quantity

    def button_confirm(self):
        for order in self:
            if not order.meets_minimums:
                has_override = self.env.user.has_group(
                    "ydod_purchase_vendor_min_order.group_purchase_min_order_override"
                ) or self.env.user.has_group("purchase.group_purchase_manager")
                if not has_override:
                    missing = []
                    currency_symbol = order.currency_id.symbol or ""
                    if not order.meets_min_amount:
                        missing.append(
                            self.env._(
                                "- Minimum Untaxed Amount: required %(required).2f %(curr)s, current is %(current).2f %(curr)s",
                                required=order.vendor_min_order_amount,
                                current=order.amount_untaxed,
                                curr=currency_symbol,
                            )
                        )
                    if not order.meets_min_quantity:
                        missing.append(
                            self.env._(
                                "- Minimum Total Quantity: required %(required).2f units, current is %(current).2f units",
                                required=order.vendor_min_order_quantity,
                                current=order.total_ordered_qty,
                            )
                        )
                    raise UserError(
                        self.env._(
                            "Purchase Order %(order)s does not meet the minimum requirements for vendor '%(vendor)s':\n%(details)s\n\nPlease adjust the order or request an authorized manager to confirm.",
                            order=order.name or "",
                            vendor=order.partner_id.name or "",
                            details="\n".join(missing),
                        )
                    )
                order.message_post(
                    body=self.env._(
                        "Purchase Order confirmed below vendor minimum order thresholds by manager %s.",
                        self.env.user.name,
                    )
                )
        return super().button_confirm()
