# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountBankReconcileStatement(models.TransientModel):
    _name = 'account.bank.reconcile.statement'
    _description = "Bank Reconciliation Statement"

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Bank Journal",
        required=True,
        domain="[('type', '=', 'bank')]",
    )
    statement_date = fields.Date(
        string="Statement Date",
        required=True,
        default=fields.Date.context_today,
    )
    bank_statement_balance = fields.Monetary(
        string="Bank Statement Balance",
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
        string="General Ledger Balance",
        compute='_compute_balances',
        currency_field='currency_id',
        readonly=True,
    )
    uncleared_balance = fields.Monetary(
        string="Uncleared / In-Transit Items",
        compute='_compute_balances',
        currency_field='currency_id',
        readonly=True,
    )
    difference = fields.Monetary(
        string="Reconciliation Variance",
        compute='_compute_difference',
        currency_field='currency_id',
        readonly=True,
    )

    @api.constrains('statement_date')
    def _check_statement_date_required(self):
        for rec in self:
            if not rec.statement_date:
                raise ValidationError(self.env._("Statement audit cutoff date is required."))

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
                rec.uncleared_balance = 0.0
                continue
            account_id = rec.journal_id.default_account_id.id
            domain = [
                ('account_id', '=', account_id),
                ('date', '<=', rec.statement_date),
                ('parent_state', '=', 'posted'),
            ]
            groups = self.env['account.move.line']._read_group(
                domain,
                groupby=['reconciled'],
                aggregates=['balance:sum'],
            )
            total_gl = 0.0
            uncleared = 0.0
            for reconciled, bal_sum in groups:
                bal = bal_sum or 0.0
                total_gl += bal
                if not reconciled:
                    uncleared += bal
            rec.gl_balance = total_gl
            rec.uncleared_balance = uncleared

    @api.depends('bank_statement_balance', 'gl_balance', 'uncleared_balance')
    def _compute_difference(self):
        for rec in self:
            rec.difference = (rec.bank_statement_balance or 0.0) - (rec.gl_balance or 0.0) - (rec.uncleared_balance or 0.0)

    def _get_uncleared_lines(self):
        self.ensure_one()
        if not self.journal_id or not self.journal_id.default_account_id or not self.statement_date:
            return self.env['account.move.line']
        return self.env['account.move.line'].search([
            ('account_id', '=', self.journal_id.default_account_id.id),
            ('date', '<=', self.statement_date),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
        ], order='date desc, id desc')

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('ydod_accounting_community.action_report_bank_reconcile_statement').report_action(self)

    def action_view_uncleared_lines(self):
        self.ensure_one()
        account_id = self.journal_id.default_account_id.id if self.journal_id else False
        return {
            'name': self.env._("Uncleared Transactions - %s", self.journal_id.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
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
