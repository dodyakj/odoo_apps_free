from collections import defaultdict

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    approval_waiting_count = fields.Integer(
        string='Waiting My Approval', compute='_compute_approval_waiting_count')

    @api.depends_context('uid')
    def _compute_approval_waiting_count(self):
        groups = self.env['ydod.approval.request'].sudo()._read_group(
            [('state', '=', 'to_approve')],
            ['approver_user_ids', 'approver_group_id'], ['id:array_agg'])
        request_ids = defaultdict(set)
        for user in self:
            user_groups = user.all_group_ids
            for approver, group, ids in groups:
                if approver == user or (group and group in user_groups):
                    request_ids[user.id].update(ids)
        for user in self:
            user.approval_waiting_count = len(request_ids[user.id])

    def _approval_waiting_domain(self):
        self.ensure_one()
        return [
            ('state', '=', 'to_approve'),
            '|', ('approver_user_ids', 'in', [self.id]), ('approver_group_id', 'in', self.all_group_ids.ids),
        ]

    def action_view_waiting_approvals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Waiting Approval of %s", self.name),
            'res_model': 'ydod.approval.request',
            'view_mode': 'list,kanban,form',
            'domain': self._approval_waiting_domain(),
            'context': {'create': False},
        }
