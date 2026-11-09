from collections import defaultdict

from odoo import _, api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    approval_waiting_count = fields.Integer(
        string='Waiting My Approval', compute='_compute_approval_waiting_count')

    @api.depends_context('uid')
    def _compute_approval_waiting_count(self):
        pending = self.env['ydod.approval.request'].sudo().search([('state', '=', 'to_approve')])
        request_ids = defaultdict(set)
        for user in self:
            user_groups = user.groups_id
            for request in pending:
                if user in request.approver_user_ids or (
                        request.approver_group_id and request.approver_group_id in user_groups):
                    request_ids[user.id].add(request.id)
        for user in self:
            user.approval_waiting_count = len(request_ids[user.id])

    def _approval_waiting_domain(self):
        self.ensure_one()
        return [
            ('state', '=', 'to_approve'),
            '|', ('approver_user_ids', 'in', [self.id]), ('approver_group_id', 'in', self.groups_id.ids),
        ]

    def action_view_waiting_approvals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Waiting Approval of %s", self.name),
            'res_model': 'ydod.approval.request',
            'view_mode': 'tree,kanban,form',
            'domain': self._approval_waiting_domain(),
            'context': {'create': False},
        }
