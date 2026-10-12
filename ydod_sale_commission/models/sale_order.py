from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    commission_line_ids = fields.One2many(
        'sale.commission.line', 'sale_order_id', string='Commission Lines',
    )
    commission_count = fields.Integer(compute='_compute_commission_total')
    commission_total = fields.Monetary(compute='_compute_commission_total')

    def _compute_commission_total(self):
        for order in self:
            order.commission_count = len(order.commission_line_ids)
            order.commission_total = sum(order.commission_line_ids.mapped('commission_amount'))

    def _action_confirm(self):
        res = super()._action_confirm()
        self._create_commission_lines()
        return res

    def _create_commission_lines(self):
        plan_model = self.env['sale.commission.plan']
        values_list = []
        for order in self:
            if not order.user_id or order.commission_line_ids:
                continue
            plan = plan_model._get_applicable_plan(order)
            if not plan:
                continue
            values_list.append(order._prepare_commission_line_values(plan))
        if values_list:
            self.env['sale.commission.line'].create(values_list)

    def _prepare_commission_line_values(self, plan):
        self.ensure_one()
        return {
            'sale_order_id': self.id,
            'plan_id': plan.id,
            'user_id': self.user_id.id,
            'team_id': self.team_id.id,
            'company_id': self.company_id.id,
            'date_order': self.date_order and self.date_order.date(),
            'base_amount': self.amount_untaxed,
            'rate': plan.rate,
        }

    def action_view_commission_lines(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'ydod_sale_commission.action_sale_commission_line',
        )
        action['domain'] = [('sale_order_id', '=', self.id)]
        action['context'] = {'default_sale_order_id': self.id, 'default_user_id': self.user_id.id}
        return action
