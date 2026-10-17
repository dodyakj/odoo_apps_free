# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    fiscal_year_id = fields.Many2one(
        comodel_name='ydod.fiscal.year',
        string="Fiscal Year",
        readonly=True,
        copy=False,
        index=True,
    )
    is_closing_entry = fields.Boolean(
        string="Closing Entry",
        readonly=True,
        copy=False,
        default=False,
    )
    approval_state = fields.Selection(
        selection=[
            ('not_required', 'Not Required'),
            ('to_approve', 'To Approve'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string="Approval Status",
        default='not_required',
        tracking=True,
        copy=False,
    )
    approver_id = fields.Many2one(
        comodel_name='res.users',
        string="Approved / Rejected By",
        readonly=True,
        copy=False,
    )

    def action_submit_for_approval(self):
        for move in self:
            if move.state != 'draft':
                raise UserError(self.env._("Only draft moves can be submitted for approval."))
            move.approval_state = 'to_approve'
            move.message_post(body=self.env._("Document submitted for manager approval."))

    def action_approve(self):
        for move in self:
            if move.approval_state != 'to_approve':
                continue
            move.approval_state = 'approved'
            move.approver_id = self.env.user
            move.message_post(body=self.env._("Document approved by %s.", self.env.user.name))

    def action_reject(self):
        for move in self:
            if move.approval_state != 'to_approve':
                continue
            move.approval_state = 'rejected'
            move.approver_id = self.env.user
            move.message_post(body=self.env._("Document rejected by %s.", self.env.user.name))

    def action_post(self):
        for move in self:
            if move.approval_state == 'to_approve':
                raise UserError(self.env._("This document requires manager approval before it can be posted."))
            if move.approval_state == 'rejected':
                raise UserError(self.env._("This document was rejected and cannot be posted."))
        return super().action_post()
