# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class YdodBankReconReportWizard(models.TransientModel):
    _name = 'ydod.bank.recon.report.wizard'
    _description = "Bank Reconciliation Audit Wizard"

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Bank Journal",
        required=True,
        domain="[('type', '=', 'bank')]",
    )
    statement_date = fields.Date(
        string="Statement Cutoff Date",
        required=True,
        default=fields.Date.context_today,
    )
    statement_balance = fields.Monetary(
        string="Bank Statement Ending Balance",
        required=True,
        currency_field='currency_id',
        default=0.0,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Currency",
        compute='_compute_currency_id',
        store=True,
        readonly=False,
    )
    gl_balance = fields.Monetary(
        string="General Ledger Book Balance",
        compute='_compute_balances',
        store=True,
        currency_field='currency_id',
    )
    uncleared_payments = fields.Monetary(
        string="Uncleared Payments / Outflows",
        compute='_compute_balances',
        store=True,
        currency_field='currency_id',
    )
    uncleared_deposits = fields.Monetary(
        string="Uncleared Deposits / Inflows",
        compute='_compute_balances',
        store=True,
        currency_field='currency_id',
    )
    balance_difference = fields.Monetary(
        string="Reconciliation Variance",
        compute='_compute_difference',
        store=True,
        currency_field='currency_id',
    )
    bank_statement_balance = fields.Monetary(
        string="Bank Statement Balance",
        related='statement_balance',
        currency_field='currency_id',
    )
    difference = fields.Monetary(
        string="Variance",
        related='balance_difference',
        currency_field='currency_id',
    )
    uncleared_balance = fields.Monetary(
        string="Uncleared / In-Transit Items",
        compute='_compute_uncleared_balance',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('uncleared_payments', 'uncleared_deposits')
    def _compute_uncleared_balance(self):
        for rec in self:
            rec.uncleared_balance = (rec.uncleared_deposits or 0.0) - (rec.uncleared_payments or 0.0)

    def _get_uncleared_lines(self):
        self.ensure_one()
        if not self.journal_id or not self.journal_id.default_account_id:
            return self.env['account.move.line']
        return self.env['account.move.line'].search([
            ('account_id', '=', self.journal_id.default_account_id.id),
            ('date', '<=', self.statement_date),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
        ], order='date desc, id desc')


    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            self.company_id = self.journal_id.company_id
            self.currency_id = self.journal_id.currency_id or self.journal_id.company_id.currency_id

    @api.depends('journal_id', 'company_id')
    def _compute_currency_id(self):
        for rec in self:
            if rec.journal_id and rec.journal_id.currency_id:
                rec.currency_id = rec.journal_id.currency_id
            elif rec.journal_id and rec.journal_id.company_id:
                rec.currency_id = rec.journal_id.company_id.currency_id
            else:
                rec.currency_id = rec.company_id.currency_id or self.env.company.currency_id

    @api.depends('journal_id', 'statement_date')
    def _compute_balances(self):
        for rec in self:
            if not rec.journal_id or not rec.statement_date or not rec.journal_id.default_account_id:
                rec.gl_balance = 0.0
                rec.uncleared_payments = 0.0
                rec.uncleared_deposits = 0.0
                continue

            account_id = rec.journal_id.default_account_id.id
            domain = [
                ('account_id', '=', account_id),
                ('date', '<=', rec.statement_date),
                ('parent_state', '=', 'posted'),
            ]
            groups = self.env['account.move.line'].read_group(
                domain,
                fields=['reconciled', 'debit', 'credit', 'balance'],
                groupby=['reconciled'],
                lazy=False,
            )

            total_gl = 0.0
            unrec_debits = 0.0
            unrec_credits = 0.0

            for g in groups:
                bal_sum = g.get('balance', 0.0) or 0.0
                debit_sum = g.get('debit', 0.0) or 0.0
                credit_sum = g.get('credit', 0.0) or 0.0
                total_gl += bal_sum
                if not g.get('reconciled'):
                    unrec_debits += debit_sum
                    unrec_credits += credit_sum

            rec.gl_balance = total_gl
            rec.uncleared_deposits = unrec_debits
            rec.uncleared_payments = unrec_credits

    @api.depends('statement_balance', 'gl_balance', 'uncleared_payments', 'uncleared_deposits')
    def _compute_difference(self):
        for rec in self:
            # Adjusted book balance = gl_balance + uncleared_payments - uncleared_deposits
            # Variance = statement_balance - (gl_balance + uncleared_payments - uncleared_deposits)
            rec.balance_difference = (rec.statement_balance or 0.0) - (rec.gl_balance or 0.0) - (rec.uncleared_deposits or 0.0) + (rec.uncleared_payments or 0.0)

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('ydod_accounting_community.action_report_ydod_bank_recon_wizard').report_action(self)

    def action_view_uncleared_lines(self):
        self.ensure_one()
        account_id = self.journal_id.default_account_id.id if self.journal_id else False
        return {
            'name': _("Uncleared Transactions - %s", self.journal_id.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'tree,form',
            'domain': [
                ('account_id', '=', account_id),
                ('date', '<=', self.statement_date),
                ('parent_state', '=', 'posted'),
                ('reconciled', '=', False),
            ],
            'context': {
                'search_default_posted': 1,
            },
        }

    def action_auto_match_suggestions(self):
        """Find matching pairs of unreconciled lines with opposite amounts and open reconciliation wizard."""
        self.ensure_one()
        if not self.journal_id or not self.journal_id.default_account_id:
            return False

        account_id = self.journal_id.default_account_id.id
        lines = self.env['account.move.line'].search([
            ('account_id', '=', account_id),
            ('date', '<=', self.statement_date),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
        ], order='date desc, id desc')

        matched_line_ids = []
        positive_lines = {round(l.balance, 2): l for l in lines if l.balance > 0}
        for l in lines:
            if l.balance < 0:
                opp_amount = round(-l.balance, 2)
                if opp_amount in positive_lines:
                    counterpart = positive_lines.pop(opp_amount)
                    matched_line_ids.extend([l.id, counterpart.id])

        return {
            'name': _("Smart Match Suggestions - %s", self.journal_id.name),
            'type': 'ir.actions.act_window',
            'res_model': 'ydod.reconcile.lines.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_ids': [fields.Command.set(matched_line_ids)],
                'default_company_id': self.company_id.id,
                'default_currency_id': self.currency_id.id,
            },
        }
