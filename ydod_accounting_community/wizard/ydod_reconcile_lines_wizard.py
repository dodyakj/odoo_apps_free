# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class YdodReconcileLinesWizard(models.TransientModel):
    _name = 'ydod.reconcile.lines.wizard'
    _description = "Manual Reconciliation Wizard"

    line_ids = fields.Many2many(
        comodel_name='account.move.line',
        string="Journal Items to Reconcile",
        required=True,
    )
    writeoff_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Write-off Journal",
        domain="[('type', '=', 'general')]",
    )
    writeoff_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Write-off Account",
    )
    writeoff_label = fields.Char(
        string="Write-off Description",
        default="Reconciliation Variance Write-off",
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    balance_difference = fields.Monetary(
        string="Balance Difference",
        compute='_compute_balance_difference',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('line_ids', 'line_ids.balance')
    def _compute_balance_difference(self):
        for rec in self:
            rec.balance_difference = sum(rec.line_ids.mapped('balance'))

    def action_suggest_matches(self):
        self.ensure_one()
        if not self.line_ids:
            return False
        first_line = self.line_ids[0]
        account = first_line.account_id
        target_amount = -self.balance_difference

        candidates = self.env['account.move.line'].search([
            ('account_id', '=', account.id),
            ('company_id', '=', self.company_id.id),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('id', 'not in', self.line_ids.ids),
        ], limit=20)

        # Look for exact opposite match
        exact_matches = candidates.filtered(lambda l: abs(l.balance - target_amount) < 0.001)
        if exact_matches:
            self.write({'line_ids': [fields.Command.link(exact_matches[0].id)]})
        elif first_line.partner_id:
            partner_matches = candidates.filtered(lambda l: l.partner_id == first_line.partner_id)
            if partner_matches:
                self.write({'line_ids': [fields.Command.link(partner_matches[0].id)]})

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_reconcile(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: not l.reconciled)
        if not lines:
            raise UserError(self.env._("All selected journal items are already reconciled."))

        if self.currency_id.is_zero(self.balance_difference):
            return lines.reconcile()

        # Variance exists: post write-off move
        if not self.writeoff_journal_id:
            raise UserError(self.env._("Please select a write-off journal to reconcile the variance of %s.", self.balance_difference))
        if not self.writeoff_account_id:
            raise UserError(self.env._("Please select a write-off account to reconcile the variance of %s.", self.balance_difference))

        target_account = lines[0].account_id
        diff = self.balance_difference

        # If diff > 0, debits exceed credits by diff -> counterpart in target account must be credit diff
        target_debit = 0.0 if diff > 0 else -diff
        target_credit = diff if diff > 0 else 0.0

        writeoff_debit = diff if diff > 0 else 0.0
        writeoff_credit = 0.0 if diff > 0 else -diff

        writeoff_move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.writeoff_journal_id.id,
            'date': fields.Date.context_today(self),
            'ref': self.writeoff_label,
            'company_id': self.company_id.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': target_account.id,
                    'name': self.writeoff_label,
                    'debit': target_debit,
                    'credit': target_credit,
                    'partner_id': lines[0].partner_id.id if lines[0].partner_id else False,
                }),
                fields.Command.create({
                    'account_id': self.writeoff_account_id.id,
                    'name': self.writeoff_label,
                    'debit': writeoff_debit,
                    'credit': writeoff_credit,
                }),
            ],
        })
        writeoff_move.action_post()

        counterpart_line = writeoff_move.line_ids.filtered(lambda l: l.account_id == target_account)
        all_lines = lines | counterpart_line
        return all_lines.reconcile()
