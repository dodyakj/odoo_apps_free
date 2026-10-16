# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountFiscalYear(models.Model):
    _name = 'account.fiscal.year'
    _description = "Fiscal Year"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    _check_dates = models.Constraint(
        'CHECK(date_from <= date_to)',
        'Fiscal year start date must precede end date.',
    )
    _name_company_uniq = models.Constraint(
        'UNIQUE(name, company_id)',
        'Fiscal year name must be unique per company.',
    )
    _company_dates_idx = models.Index("(company_id, date_from, date_to)")

    name = fields.Char(string="Fiscal Year", required=True, tracking=True)
    code = fields.Char(string="Code", required=True, tracking=True)
    date_from = fields.Date(string="Start Date", required=True, tracking=True)
    date_to = fields.Date(string="End Date", required=True, tracking=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('open', 'Open'),
            ('closed', 'Closed'),
        ],
        string="Status",
        required=True,
        default='draft',
        tracking=True,
    )
    closing_move_id = fields.Many2one(
        comodel_name='account.move',
        string="Closing Entry",
        readonly=True,
        copy=False,
    )
    move_count = fields.Integer(
        string="Moves Count",
        compute='_compute_move_count',
        readonly=True,
    )

    @api.constrains('date_from', 'date_to')
    def _check_fiscal_year_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError(self.env._("Fiscal year start date must precede end date."))

    @api.constrains('name', 'company_id')
    def _check_name_unique(self):
        for company in self.company_id:
            fys = self.filtered(lambda r: r.company_id == company)
            names = fys.mapped('name')
            if len(names) != len(set(names)):
                raise ValidationError(self.env._("Fiscal year name must be unique per company."))
            domain = [
                ('company_id', '=', company.id),
                ('name', 'in', names),
                ('id', 'not in', fys.ids),
            ]
            if self.search_count(domain):
                raise ValidationError(self.env._("Fiscal year name must be unique per company."))

    @api.depends('date_from', 'date_to', 'company_id')
    def _compute_move_count(self):
        for fy in self:
            if not fy.date_from or not fy.date_to or not fy.company_id:
                fy.move_count = 0
                continue
            groups = self.env['account.move']._read_group(
                domain=[
                    ('company_id', '=', fy.company_id.id),
                    ('date', '>=', fy.date_from),
                    ('date', '<=', fy.date_to),
                    ('state', '=', 'posted'),
                ],
                aggregates=['__count'],
            )
            fy.move_count = groups[0][0] if groups else 0

    def action_open(self):
        self.check_access('write')
        self.write({'state': 'open'})

    def action_draft(self):
        self.check_access('write')
        for fy in self:
            if fy.closing_move_id and fy.closing_move_id.state == 'posted':
                raise UserError(self.env._("Cannot reset to draft while a posted closing entry exists."))
        self.write({'state': 'draft'})

    def action_close(self):
        self.check_access('write')
        self.write({'state': 'closed'})

    def action_view_moves(self):
        self.ensure_one()
        return {
            'name': self.env._("Journal Entries (%s)", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('state', '=', 'posted'),
            ],
            'context': {
                'default_company_id': self.company_id.id,
            },
        }

    def _get_retained_earnings_account(self):
        self.ensure_one()
        company = self.company_id
        account = False
        if hasattr(company, 'get_unaffected_earnings_account'):
            account = company.get_unaffected_earnings_account()
        if not account:
            account = self.env['account.account'].search([
                *self.env['account.account']._check_company_domain(company),
                ('account_type', '=', 'equity_unaffected'),
            ], limit=1)
        if not account:
            account = self.env['account.account'].search([
                *self.env['account.account']._check_company_domain(company),
                ('internal_group', '=', 'equity'),
            ], limit=1)
        if not account:
            account = self.env['account.account'].create({
                'name': self.env._("Undistributed Profits/Losses"),
                'code': '999999',
                'account_type': 'equity_unaffected',
                'company_ids': [fields.Command.link(company.id)],
            })
        return account

    def action_generate_closing_entry(self):
        self.ensure_one()
        self.check_access('write')

        draft_count = self.env['account.move'].search_count([
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'draft'),
        ])
        if draft_count:
            raise UserError(self.env._(
                "There are %d unposted draft journal entries in this fiscal period. Please post or cancel them before closing.",
                draft_count,
            ))

        retained_account = self._get_retained_earnings_account()
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': self.env._("Miscellaneous Operations"),
                'code': 'MISC',
                'type': 'general',
                'company_id': self.company_id.id,
            })

        domain = [
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('parent_state', '=', 'posted'),
            ('account_id.internal_group', 'in', ['income', 'expense']),
        ]
        groups = self.env['account.move.line']._read_group(
            domain,
            groupby=['account_id'],
            aggregates=['balance:sum'],
        )

        lines_to_create = []
        net_pl_balance = 0.0

        for account, balance in groups:
            bal = balance or 0.0
            if self.company_id.currency_id.is_zero(bal):
                continue
            net_pl_balance += bal
            debit = -bal if bal < 0 else 0.0
            credit = bal if bal > 0 else 0.0
            lines_to_create.append(fields.Command.create({
                'account_id': account.id,
                'name': self.env._("FY Closing - Transfer %s balance", account.name),
                'debit': debit,
                'credit': credit,
            }))

        if not lines_to_create:
            lines_to_create.append(fields.Command.create({
                'account_id': retained_account.id,
                'name': self.env._("FY Closing - Retained Earnings (Balanced)"),
                'debit': 0.0,
                'credit': 0.0,
            }))
        else:
            re_debit = net_pl_balance if net_pl_balance > 0 else 0.0
            re_credit = -net_pl_balance if net_pl_balance < 0 else 0.0
            lines_to_create.append(fields.Command.create({
                'account_id': retained_account.id,
                'name': self.env._("FY Closing - Retained Earnings Transfer"),
                'debit': re_debit,
                'credit': re_credit,
            }))

        closing_move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.date_to,
            'ref': self.env._("Closing Entry - %s", self.name),
            'company_id': self.company_id.id,
            'line_ids': lines_to_create,
        })
        closing_move.action_post()

        self.write({
            'closing_move_id': closing_move.id,
            'state': 'closed',
        })

        return {
            'name': self.env._("Closing Journal Entry"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': closing_move.id,
        }
