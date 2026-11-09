from odoo import fields, models
from odoo.exceptions import UserError


class YdodApprovalRejectWizard(models.TransientModel):
    _name = 'ydod.approval.reject.wizard'
    _description = 'Reject Approval Request'

    request_ids = fields.Many2many('ydod.approval.request', string='Requests', required=True)
    reason = fields.Text(required=True, help="Posted in the chatter of the document.")

    def action_confirm(self):
        self.ensure_one()
        reason = (self.reason or '').strip()
        if not reason:
            raise UserError(self.env._("Please enter a reason for the rejection."))
        self.request_ids._do_reject(reason)
        return {'type': 'ir.actions.act_window_close'}
