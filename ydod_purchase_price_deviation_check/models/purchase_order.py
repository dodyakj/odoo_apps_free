from odoo import api, fields, models
from odoo.exceptions import AccessError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    has_price_deviation = fields.Boolean(
        string="Has Price Deviation", compute='_compute_price_deviation', store=True)
    price_deviation_count = fields.Integer(
        string="Deviating Lines", compute='_compute_price_deviation', store=True)
    price_deviation_status = fields.Selection(
        [('ok', "Within Tolerance"), ('flagged', "Deviation to Approve"), ('approved', "Deviation Approved")],
        string="Price Deviation", compute='_compute_price_deviation', store=True, index=True)
    price_deviation_justification = fields.Text(
        string="Deviation Justification", copy=False, readonly=True)
    price_deviation_approver_id = fields.Many2one(
        'res.users', string="Deviation Approved By", copy=False, readonly=True)
    price_deviation_date = fields.Datetime(string="Deviation Approved On", copy=False, readonly=True)
    price_deviation_needs_approval = fields.Boolean(compute='_compute_price_deviation_needs_approval')

    @api.depends('order_line.price_deviation_level', 'price_deviation_approver_id')
    def _compute_price_deviation(self):
        for order in self:
            count = len(order.order_line.filtered(lambda l: l.price_deviation_level == 'flagged'))
            order.price_deviation_count = count
            order.has_price_deviation = bool(count)
            if not count:
                order.price_deviation_status = 'ok'
            else:
                order.price_deviation_status = 'approved' if order.price_deviation_approver_id else 'flagged'

    @api.depends_context('uid')
    @api.depends('price_deviation_status', 'state')
    def _compute_price_deviation_needs_approval(self):
        is_manager = self.env.user.has_group('purchase.group_purchase_manager')
        for order in self:
            order.price_deviation_needs_approval = (
                is_manager
                and order.price_deviation_status == 'flagged'
                and order.state in ('draft', 'sent', 'to approve')
            )

    def _approval_allowed(self):
        # Unjustified deviations always go through 'To Approve', even for managers:
        # they approve them with a justification from the dedicated wizard.
        allowed = super()._approval_allowed()
        if allowed and self.price_deviation_status == 'flagged':
            return False
        return allowed

    def button_draft(self):
        self.write({
            'price_deviation_justification': False,
            'price_deviation_approver_id': False,
            'price_deviation_date': False,
        })
        return super().button_draft()

    def action_open_price_deviation_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Approve Price Deviation"),
            'res_model': 'purchase.price.deviation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_ids': self.ids},
        }

    def _approve_price_deviation(self, justification, approver_id=False):
        """ Record the manager justification, log it with the deviating prices and
        confirm or approve the orders. """
        approver = self.env['res.users'].browse(approver_id) if approver_id else self.env.user
        if not approver.has_group('purchase.group_purchase_manager'):
            raise AccessError(self.env._("Only a Purchase Administrator can approve price deviations."))
        flagged = self.filtered(lambda o: o.price_deviation_status == 'flagged')
        for order in flagged:
            lines = order.order_line.filtered(lambda l: l.price_deviation_level == 'flagged')
            order.write({
                'price_deviation_justification': justification,
                'price_deviation_approver_id': approver.id,
                'price_deviation_date': fields.Datetime.now(),
            })
            order.message_post_with_source(
                'ydod_purchase_price_deviation_check.message_price_deviation_approved',
                render_values={'lines': lines, 'approver': approver, 'justification': justification},
                subtype_xmlid='mail.mt_note',
            )
        to_confirm = self.filtered(lambda o: o.state in ('draft', 'sent'))
        to_approve = self.filtered(lambda o: o.state == 'to approve')
        to_confirm.with_context(validate_analytic=True).button_confirm()
        to_approve.button_approve()
        return True
