from odoo import api, fields, models, _


class YdodReplenishRequest(models.Model):
    _name = 'ydod.replenish.request'
    _description = 'Replenishment Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    orderpoint_id = fields.Many2one(
        'stock.warehouse.orderpoint', string='Reordering Rule', required=True,
        ondelete='cascade', readonly=True)
    product_id = fields.Many2one(
        'product.product', related='orderpoint_id.product_id', store=True, readonly=True)
    product_uom_id = fields.Many2one(
        'uom.uom', related='orderpoint_id.product_uom', string='Unit of Measure', store=True, readonly=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', related='orderpoint_id.warehouse_id', store=True, readonly=True)
    location_id = fields.Many2one(
        'stock.location', related='orderpoint_id.location_id', store=True, readonly=True)
    responsible_buyer_id = fields.Many2one(
        'res.users', related='orderpoint_id.responsible_buyer_id', string='Responsible Buyer',
        store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    product_qty = fields.Float(
        string='Quantity to Order', digits='Product Unit', required=True, readonly=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', required=True, tracking=True, copy=False)
    request_date = fields.Datetime(string='Requested On', default=fields.Datetime.now, readonly=True)
    decision_date = fields.Datetime(readonly=True, copy=False)
    decided_by = fields.Many2one('res.users', readonly=True, copy=False)
    reject_reason = fields.Text(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ydod.replenish.request') or _('New')
        requests = super().create(vals_list)
        for request in requests:
            if request.responsible_buyer_id:
                request.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=request.responsible_buyer_id.id,
                    summary=_('Replenishment request to review'),
                    note=_(
                        'A replenishment of %(qty)s %(uom)s of %(product)s is pending your approval.',
                        qty=request.product_qty,
                        uom=request.product_uom_id.display_name,
                        product=request.product_id.display_name,
                    ),
                )
        return requests

    def action_approve(self):
        for request in self:
            if request.state != 'pending':
                continue
            request.orderpoint_id.with_context(skip_replenish_approval=True)._procure_orderpoint_confirm(
                company_id=request.company_id)
            request.write({
                'state': 'approved',
                'decision_date': fields.Datetime.now(),
                'decided_by': self.env.user.id,
            })
            request.activity_feedback(['mail.mail_activity_data_todo'])

    def action_reject(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Replenishment Request'),
            'res_model': 'ydod.replenish.request.reject',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_ids': [(6, 0, self.ids)]},
        }
