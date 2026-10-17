# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.date_utils import relativedelta


class YdodAccountAsset(models.Model):
    _name = 'ydod.account.asset'
    _description = "Fixed Asset"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'purchase_date desc, id desc'

    _sql_constraints = [
        ('check_values', 'CHECK(purchase_value >= salvage_value)', 'Purchase value must be greater than or equal to salvage value.'),
    ]

    name = fields.Char(string="Asset Name", required=True, tracking=True)
    code = fields.Char(string="Reference", copy=False)
    purchase_date = fields.Date(
        string="Acquisition Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    purchase_value = fields.Monetary(
        string="Original Cost",
        required=True,
        default=0.0,
        currency_field='currency_id',
        tracking=True,
    )
    salvage_value = fields.Monetary(
        string="Salvage Value",
        default=0.0,
        currency_field='currency_id',
        tracking=True,
    )
    depreciable_value = fields.Monetary(
        string="Depreciable Value",
        compute='_compute_depreciable_value',
        store=True,
        currency_field='currency_id',
    )
    method_number = fields.Integer(
        string="Number of Depreciations",
        default=36,
        required=True,
        help="Number of periodic depreciation entries to calculate.",
    )
    method_period = fields.Selection(
        selection=[
            ('months', 'Months'),
            ('years', 'Years'),
        ],
        string="Frequency",
        default='months',
        required=True,
    )
    account_asset_id = fields.Many2one(
        comodel_name='account.account',
        string="Fixed Asset Account",
        required=True,
    )
    account_depreciation_id = fields.Many2one(
        comodel_name='account.account',
        string="Accumulated Depreciation Account",
        required=True,
    )
    account_expense_id = fields.Many2one(
        comodel_name='account.account',
        string="Depreciation Expense Account",
        required=True,
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Depreciation Journal",
        required=True,
        domain="[('type', '=', 'general')]",
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
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('running', 'Running'),
            ('paused', 'Paused'),
            ('closed', 'Closed'),
        ],
        string="Status",
        default='draft',
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        comodel_name='ydod.account.asset.line',
        inverse_name='asset_id',
        string="Depreciation Board",
    )
    value_depreciated = fields.Monetary(
        string="Total Depreciated",
        compute='_compute_depreciation_values',
        store=True,
        currency_field='currency_id',
    )
    value_residual = fields.Monetary(
        string="Residual Value",
        compute='_compute_depreciation_values',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('purchase_value', 'salvage_value')
    def _compute_depreciable_value(self):
        for asset in self:
            asset.depreciable_value = max(0.0, (asset.purchase_value or 0.0) - (asset.salvage_value or 0.0))

    @api.depends('journal_id', 'company_id')
    def _compute_currency_id(self):
        for asset in self:
            if asset.journal_id and asset.journal_id.currency_id:
                asset.currency_id = asset.journal_id.currency_id
            elif asset.company_id and asset.company_id.currency_id:
                asset.currency_id = asset.company_id.currency_id
            else:
                asset.currency_id = self.env.company.currency_id

    @api.depends('purchase_value', 'line_ids.state', 'line_ids.amount')
    def _compute_depreciation_values(self):
        for asset in self:
            posted_lines = asset.line_ids.filtered(lambda l: l.state == 'posted')
            depreciated = sum(posted_lines.mapped('amount'))
            asset.value_depreciated = depreciated
            asset.value_residual = max(0.0, (asset.purchase_value or 0.0) - depreciated)

    def action_compute_depreciation_board(self):
        for asset in self:
            if asset.state not in ('draft', 'running'):
                raise UserError(self.env._("Depreciation board can only be computed for draft or running assets."))
            posted_lines = asset.line_ids.filtered(lambda l: l.state == 'posted')
            draft_lines = asset.line_ids.filtered(lambda l: l.state == 'draft')
            draft_lines.unlink()

            posted_amount = sum(posted_lines.mapped('amount'))
            remaining_to_depreciate = max(0.0, asset.depreciable_value - posted_amount)
            num_remaining = max(1, asset.method_number - len(posted_lines))

            if asset.currency_id.is_zero(remaining_to_depreciate) or num_remaining <= 0:
                continue

            per_period_amount = asset.currency_id.round(remaining_to_depreciate / num_remaining)
            start_date = asset.purchase_date or fields.Date.context_today(self)
            if posted_lines:
                start_date = max(posted_lines.mapped('depreciation_date'))

            cumulative_depr = posted_amount
            curr_remaining = asset.purchase_value - posted_amount
            new_lines = []
            seq = len(posted_lines) + 1

            for i in range(1, num_remaining + 1):
                if asset.method_period == 'months':
                    line_date = start_date + relativedelta(months=i)
                else:
                    line_date = start_date + relativedelta(years=i)

                if i == num_remaining:
                    # Final period absorbs rounding difference
                    line_amount = asset.currency_id.round(remaining_to_depreciate - (per_period_amount * (num_remaining - 1)))
                else:
                    line_amount = per_period_amount

                cumulative_depr += line_amount
                curr_remaining = max(0.0, curr_remaining - line_amount)

                new_lines.append(fields.Command.create({
                    'name': self.env._("%s - Depr #%d", asset.name, seq),
                    'sequence': seq,
                    'depreciation_date': line_date,
                    'amount': line_amount,
                    'depreciated_value': cumulative_depr,
                    'remaining_value': curr_remaining,
                    'state': 'draft',
                }))
                seq += 1

            if new_lines:
                asset.write({'line_ids': new_lines})
        return True

    def action_confirm(self):
        for asset in self:
            if not asset.line_ids:
                asset.action_compute_depreciation_board()
            asset.write({'state': 'running'})
            asset.message_post(body=self.env._("Asset '%s' confirmed and activated.", asset.name))

    def action_pause(self):
        self.write({'state': 'paused'})

    def action_resume(self):
        self.write({'state': 'running'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reset_draft(self):
        for asset in self:
            if any(line.state == 'posted' for line in asset.line_ids):
                raise UserError(self.env._("Cannot reset to draft while posted depreciation entries exist."))
            asset.write({'state': 'draft'})

    def action_post_pending_depreciation(self):
        today = fields.Date.context_today(self)
        for asset in self.filtered(lambda a: a.state == 'running'):
            pending = asset.line_ids.filtered(lambda l: l.state == 'draft' and l.depreciation_date <= today)
            for line in pending:
                line.action_post_entry()


class YdodAccountAssetLine(models.Model):
    _name = 'ydod.account.asset.line'
    _description = "Fixed Asset Depreciation Line"
    _order = 'depreciation_date, sequence, id'

    asset_id = fields.Many2one(
        comodel_name='ydod.account.asset',
        string="Asset",
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(string="Description", required=True)
    sequence = fields.Integer(string="Sequence", default=1)
    depreciation_date = fields.Date(string="Depreciation Date", required=True)
    amount = fields.Monetary(string="Depreciation Amount", required=True, currency_field='currency_id')
    depreciated_value = fields.Monetary(string="Cumulative Depreciation", currency_field='currency_id')
    remaining_value = fields.Monetary(string="Residual Value", currency_field='currency_id')
    move_id = fields.Many2one(
        comodel_name='account.move',
        string="Posted Move",
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('posted', 'Posted'),
        ],
        string="Status",
        default='draft',
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='asset_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='asset_id.currency_id',
        readonly=True,
    )

    def action_post_entry(self):
        self.ensure_one()
        if self.state == 'posted':
            return True
        asset = self.asset_id
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': asset.journal_id.id,
            'date': self.depreciation_date,
            'ref': self.name,
            'company_id': asset.company_id.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': asset.account_expense_id.id,
                    'name': self.name,
                    'debit': self.amount,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': asset.account_depreciation_id.id,
                    'name': self.name,
                    'debit': 0.0,
                    'credit': self.amount,
                }),
            ],
        })
        move.action_post()
        self.write({
            'move_id': move.id,
            'state': 'posted',
        })
        return True
