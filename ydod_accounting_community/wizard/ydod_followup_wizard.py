# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class YdodAccountFollowup(models.TransientModel):
    _name = 'ydod.account.followup'
    _description = "Customer Payment Follow-Up Wizard"

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer",
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    overdue_amount = fields.Monetary(
        string="Overdue Amount",
        compute='_compute_overdue_data',
        currency_field='currency_id',
    )
    total_due_amount = fields.Monetary(
        string="Total Outstanding",
        compute='_compute_overdue_data',
        currency_field='currency_id',
    )
    invoice_ids = fields.Many2many(
        comodel_name='account.move',
        string="Open Invoices",
        compute='_compute_overdue_data',
    )

    @api.depends('partner_id', 'company_id')
    def _compute_overdue_data(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.partner_id:
                rec.overdue_amount = 0.0
                rec.total_due_amount = 0.0
                rec.invoice_ids = False
                continue

            moves = self.env['account.move'].search([
                ('partner_id', '=', rec.partner_id.id),
                ('company_id', '=', rec.company_id.id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted'),
                ('payment_state', 'not in', ['paid', 'in_payment', 'reversed']),
            ])
            rec.invoice_ids = moves
            overdue_sum = sum(
                m.amount_residual for m in moves
                if m.invoice_date_due and m.invoice_date_due < today
            )
            total_sum = sum(m.amount_residual for m in moves)
            rec.overdue_amount = overdue_sum
            rec.total_due_amount = total_sum

    def action_send_followup(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(self.env._("Please select a partner."))

        # Post reminder message on partner chatter
        body = self.env._(
            "Automatic Payment Follow-up: Total outstanding is %s, with %s currently overdue across %d invoice(s).",
            self.total_due_amount,
            self.overdue_amount,
            len(self.invoice_ids),
        )
        self.partner_id.message_post(body=body)

        # Schedule follow-up activity
        self.partner_id.activity_schedule(
            activity_type_id=self.env.ref('mail.mail_activity_data_call').id,
            summary=self.env._("Payment Follow-up Call: %s", self.partner_id.name),
            note=body,
            user_id=self.env.user.id,
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._("Follow-up Dispatched"),
                'message': self.env._("Follow-up reminder and activity logged for %s.", self.partner_id.name),
                'type': 'success',
                'sticky': False,
            },
        }
