from odoo import fields, models


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    require_approval = fields.Boolean(
        string='Require Approval',
        help="If checked, a replenishment triggered on this reordering rule creates a pending "
             "Replenishment Request instead of directly generating a purchase order.")
    responsible_buyer_id = fields.Many2one(
        'res.users', string='Responsible Buyer', default=lambda self: self.env.user,
        help="User notified and expected to approve or reject the replenishment requests "
             "created from this reordering rule.")

    def _procure_orderpoint_confirm(self, use_new_cursor=False, company_id=None, raise_user_error=True):
        if not self.env.context.get('skip_replenish_approval'):
            to_approve = self.filtered(
                lambda o: o.require_approval and o.product_uom.compare(o.qty_to_order, 0.0) == 1)
            if to_approve:
                to_approve._create_replenish_requests()
                remaining = self - to_approve
                if not remaining:
                    return {}
                return super(StockWarehouseOrderpoint, remaining)._procure_orderpoint_confirm(
                    use_new_cursor=use_new_cursor, company_id=company_id, raise_user_error=raise_user_error)
        return super()._procure_orderpoint_confirm(
            use_new_cursor=use_new_cursor, company_id=company_id, raise_user_error=raise_user_error)

    def _create_replenish_requests(self):
        request_model = self.env['ydod.replenish.request']
        existing = request_model.search([
            ('orderpoint_id', 'in', self.ids),
            ('state', '=', 'pending'),
        ])
        orderpoints_with_pending = existing.orderpoint_id
        vals_list = [{
            'orderpoint_id': orderpoint.id,
            'company_id': orderpoint.company_id.id,
            'product_qty': orderpoint.qty_to_order,
        } for orderpoint in (self - orderpoints_with_pending)]
        if vals_list:
            request_model.sudo().create(vals_list)
