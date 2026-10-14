from odoo import fields, models


class YdodReplenishRequestReject(models.TransientModel):
    _name = 'ydod.replenish.request.reject'
    _description = 'Reject Replenishment Request'

    request_ids = fields.Many2many('ydod.replenish.request', string='Requests', required=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        for request in self.request_ids:
            if request.state != 'pending':
                continue
            request.write({
                'state': 'rejected',
                'decision_date': fields.Datetime.now(),
                'decided_by': self.env.user.id,
                'reject_reason': self.reason,
            })
            request.activity_feedback(['mail.mail_activity_data_todo'])
        return {'type': 'ir.actions.act_window_close'}
