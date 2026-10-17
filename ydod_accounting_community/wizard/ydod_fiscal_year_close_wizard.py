# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class YdodFiscalYearCloseWizard(models.TransientModel):
    _name = 'ydod.fiscal.year.close.wizard'
    _description = "Fiscal Year Close Wizard"

    fiscal_year_id = fields.Many2one(
        comodel_name='ydod.fiscal.year',
        string="Fiscal Year",
        required=True,
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Closing Journal",
        required=True,
        domain="[('type', '=', 'general')]",
    )
    closing_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Retained Earnings Account",
        required=True,
    )
    closing_date = fields.Date(
        string="Closing Date",
        required=True,
    )
    description = fields.Char(
        string="Description",
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        fy_id = res.get('fiscal_year_id') or self.env.context.get('default_fiscal_year_id')
        if fy_id:
            fy = self.env['ydod.fiscal.year'].browse(fy_id)
            res['fiscal_year_id'] = fy.id
            res['company_id'] = fy.company_id.id
            res['closing_date'] = fy.date_to
            res['description'] = _("Fiscal Year Closing - %s", fy.name)

            # Auto-populate retained earnings account
            company = fy.company_id
            if company.retained_earnings_account_id:
                res['closing_account_id'] = company.retained_earnings_account_id.id
            else:
                account = self.env['account.account'].search([
                    *self.env['account.account']._check_company_domain(company),
                    ('account_type', '=', 'equity_unaffected'),
                ], limit=1)
                if not account:
                    account = self.env['account.account'].search([
                        *self.env['account.account']._check_company_domain(company),
                        ('internal_group', '=', 'equity'),
                    ], limit=1)
                if account:
                    res['closing_account_id'] = account.id

            # Auto-populate general journal
            journal = self.env['account.journal'].search([
                ('type', '=', 'general'),
                ('company_id', '=', company.id),
            ], limit=1)
            if journal:
                res['journal_id'] = journal.id

        return res

    def action_close_fiscal_year(self):
        self.ensure_one()
        fy = self.fiscal_year_id
        if fy.state == 'closed':
            raise UserError(_("This fiscal year is already closed."))

        draft_count = self.env['account.move'].search_count([
            ('company_id', '=', self.company_id.id),
            ('date', '>=', fy.date_from),
            ('date', '<=', fy.date_to),
            ('state', '=', 'draft'),
        ])
        if draft_count:
            raise UserError(_(
                "There are %d draft journal entries in this fiscal period. Please post or cancel them before closing.",
                draft_count,
            ))

        domain = [
            ('company_id', '=', self.company_id.id),
            ('date', '>=', fy.date_from),
            ('date', '<=', fy.date_to),
            ('parent_state', '=', 'posted'),
            ('account_id.internal_group', 'in', ['income', 'expense']),
        ]
        groups = self.env['account.move.line'].read_group(
            domain,
            fields=['account_id', 'balance'],
            groupby=['account_id'],
        )

        lines_to_create = []
        net_pl_balance = 0.0

        for res in groups:
            acc_id = res['account_id'][0]
            account = self.env['account.account'].browse(acc_id)
            bal = res.get('balance', 0.0) or 0.0
            if self.company_id.currency_id.is_zero(bal):
                continue
            net_pl_balance += bal
            debit = -bal if bal < 0 else 0.0
            credit = bal if bal > 0 else 0.0
            lines_to_create.append(fields.Command.create({
                'account_id': account.id,
                'name': _("FY Closing - Clear %s", account.name),
                'debit': debit,
                'credit': credit,
            }))

        if not lines_to_create:
            lines_to_create.append(fields.Command.create({
                'account_id': self.closing_account_id.id,
                'name': _("FY Closing - Retained Earnings (Balanced Zero)"),
                'debit': 0.0,
                'credit': 0.0,
            }))
        else:
            re_debit = net_pl_balance if net_pl_balance > 0 else 0.0
            re_credit = -net_pl_balance if net_pl_balance < 0 else 0.0
            lines_to_create.append(fields.Command.create({
                'account_id': self.closing_account_id.id,
                'name': _("FY Closing - Transfer Net Income/Loss"),
                'debit': re_debit,
                'credit': re_credit,
            }))

        closing_move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'date': self.closing_date,
            'ref': self.description,
            'company_id': self.company_id.id,
            'fiscal_year_id': fy.id,
            'is_closing_entry': True,
            'line_ids': lines_to_create,
        })
        closing_move.action_post()

        fy.write({
            'closing_move_id': closing_move.id,
            'state': 'closed',
        })

        # Set lock date automatically on company
        self.company_id.sudo().write({
            'fiscalyear_lock_date': fy.date_to,
        })

        fy.message_post(body=_(
            "Fiscal Year closed. Closing entry %s generated and posted.", closing_move.name
        ))

        return {
            'name': _("Closing Journal Entry"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': closing_move.id,
        }
