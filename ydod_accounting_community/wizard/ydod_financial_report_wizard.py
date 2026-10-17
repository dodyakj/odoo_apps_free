# -*- coding: utf-8 -*-
import base64
import csv
import io
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class YdodFinancialReportWizard(models.TransientModel):
    _name = 'ydod.financial.report.wizard'
    _description = "Financial Reports Wizard"

    report_type = fields.Selection(
        selection=[
            ('trial_balance', 'Trial Balance'),
            ('pnl', 'Profit and Loss'),
            ('balance_sheet', 'Balance Sheet'),
            ('general_ledger', 'General Ledger'),
            ('partner_ledger', 'Partner Ledger'),
            ('aged_receivable', 'Aged Receivable'),
            ('aged_payable', 'Aged Payable'),
            ('cash_flow', 'Cash Flow Statement'),
        ],
        string="Report Type",
        required=True,
        default='trial_balance',
    )
    date_from = fields.Date(
        string="Start Date",
    )
    date_to = fields.Date(
        string="End Date",
        required=True,
        default=fields.Date.context_today,
    )
    target_move = fields.Selection(
        selection=[
            ('posted', 'All Posted Entries'),
            ('all', 'All Entries'),
        ],
        string="Target Moves",
        required=True,
        default='posted',
    )
    enable_comparison = fields.Boolean(
        string="Enable Comparison",
        default=False,
    )
    comparison_date_from = fields.Date(
        string="Comparison Start Date",
    )
    comparison_date_to = fields.Date(
        string="Comparison End Date",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    def _get_target_state_domain(self):
        return [('parent_state', '=', 'posted')] if self.target_move == 'posted' else [('parent_state', '!=', 'cancel')]

    def _get_trial_balance_data(self):
        self.ensure_one()
        state_domain = self._get_target_state_domain()
        company = self.company_id

        # 1. Initial balances (before date_from)
        initial_map = {}
        if self.date_from:
            dom_init = [
                ('company_id', '=', company.id),
                ('date', '<', self.date_from),
                *state_domain,
            ]
            init_groups = self.env['account.move.line']._read_group(
                dom_init,
                groupby=['account_id'],
                aggregates=['debit:sum', 'credit:sum', 'balance:sum'],
            )
            for acc, deb, cred, bal in init_groups:
                initial_map[acc.id] = {'debit': deb or 0.0, 'credit': cred or 0.0, 'balance': bal or 0.0}

        # 2. Period balances (date_from to date_to)
        dom_period = [
            ('company_id', '=', company.id),
            ('date', '<=', self.date_to),
            *state_domain,
        ]
        if self.date_from:
            dom_period.append(('date', '>=', self.date_from))

        period_groups = self.env['account.move.line']._read_group(
            dom_period,
            groupby=['account_id'],
            aggregates=['debit:sum', 'credit:sum', 'balance:sum'],
        )
        period_map = {}
        for acc, deb, cred, bal in period_groups:
            period_map[acc.id] = {'debit': deb or 0.0, 'credit': cred or 0.0, 'balance': bal or 0.0}

        # All accounts with activity
        all_account_ids = set(initial_map.keys()) | set(period_map.keys())
        accounts = self.env['account.account'].browse(all_account_ids).sorted(key=lambda a: a.code)

        lines = []
        tot_init_debit = tot_init_credit = 0.0
        tot_period_debit = tot_period_credit = 0.0
        tot_end_debit = tot_end_credit = 0.0

        for acc in accounts:
            init_bal = initial_map.get(acc.id, {}).get('balance', 0.0)
            p_deb = period_map.get(acc.id, {}).get('debit', 0.0)
            p_cred = period_map.get(acc.id, {}).get('credit', 0.0)
            end_bal = init_bal + (p_deb - p_cred)

            if company.currency_id.is_zero(init_bal) and company.currency_id.is_zero(p_deb) and company.currency_id.is_zero(p_cred):
                continue

            init_d = init_bal if init_bal > 0 else 0.0
            init_c = -init_bal if init_bal < 0 else 0.0
            end_d = end_bal if end_bal > 0 else 0.0
            end_c = -end_bal if end_bal < 0 else 0.0

            tot_init_debit += init_d
            tot_init_credit += init_c
            tot_period_debit += p_deb
            tot_period_credit += p_cred
            tot_end_debit += end_d
            tot_end_credit += end_c

            lines.append({
                'code': acc.code,
                'name': acc.name,
                'initial_debit': init_d,
                'initial_credit': init_c,
                'period_debit': p_deb,
                'period_credit': p_cred,
                'ending_debit': end_d,
                'ending_credit': end_c,
            })

        return {
            'lines': lines,
            'totals': {
                'initial_debit': tot_init_debit,
                'initial_credit': tot_init_credit,
                'period_debit': tot_period_debit,
                'period_credit': tot_period_credit,
                'ending_debit': tot_end_debit,
                'ending_credit': tot_end_credit,
            },
        }

    def _get_pnl_data(self):
        self.ensure_one()
        state_domain = self._get_target_state_domain()
        company = self.company_id

        # Current period
        dom_curr = [
            ('company_id', '=', company.id),
            ('date', '<=', self.date_to),
            ('account_id.internal_group', 'in', ['income', 'expense']),
            *state_domain,
        ]
        if self.date_from:
            dom_curr.append(('date', '>=', self.date_from))

        curr_groups = self.env['account.move.line']._read_group(
            dom_curr,
            groupby=['account_id'],
            aggregates=['balance:sum'],
        )
        curr_map = {acc.id: (bal or 0.0) for acc, bal in curr_groups}

        # Comparison period
        comp_map = {}
        if self.enable_comparison and self.comparison_date_to:
            dom_comp = [
                ('company_id', '=', company.id),
                ('date', '<=', self.comparison_date_to),
                ('account_id.internal_group', 'in', ['income', 'expense']),
                *state_domain,
            ]
            if self.comparison_date_from:
                dom_comp.append(('date', '>=', self.comparison_date_from))

            comp_groups = self.env['account.move.line']._read_group(
                dom_comp,
                groupby=['account_id'],
                aggregates=['balance:sum'],
            )
            comp_map = {acc.id: (bal or 0.0) for acc, bal in comp_groups}

        all_acc_ids = set(curr_map.keys()) | set(comp_map.keys())
        accounts = self.env['account.account'].browse(all_acc_ids).sorted(key=lambda a: a.code)

        income_lines = []
        expense_lines = []
        total_income_curr = total_income_comp = 0.0
        total_expense_curr = total_expense_comp = 0.0

        for acc in accounts:
            c_bal = curr_map.get(acc.id, 0.0)
            cmp_bal = comp_map.get(acc.id, 0.0)

            # In Odoo, income accounts typically have credit (negative balance), expenses have debit (positive balance)
            if acc.internal_group == 'income':
                val_curr = -c_bal
                val_comp = -cmp_bal
                total_income_curr += val_curr
                total_income_comp += val_comp
                income_lines.append({
                    'code': acc.code,
                    'name': acc.name,
                    'current': val_curr,
                    'comparison': val_comp,
                    'diff': val_curr - val_comp,
                })
            else:
                val_curr = c_bal
                val_comp = cmp_bal
                total_expense_curr += val_curr
                total_expense_comp += val_comp
                expense_lines.append({
                    'code': acc.code,
                    'name': acc.name,
                    'current': val_curr,
                    'comparison': val_comp,
                    'diff': val_curr - val_comp,
                })

        net_profit_curr = total_income_curr - total_expense_curr
        net_profit_comp = total_income_comp - total_expense_comp

        return {
            'income_lines': income_lines,
            'expense_lines': expense_lines,
            'total_income_curr': total_income_curr,
            'total_income_comp': total_income_comp,
            'total_expense_curr': total_expense_curr,
            'total_expense_comp': total_expense_comp,
            'net_profit_curr': net_profit_curr,
            'net_profit_comp': net_profit_comp,
            'net_profit_diff': net_profit_curr - net_profit_comp,
        }

    def _get_balance_sheet_data(self):
        self.ensure_one()
        state_domain = self._get_target_state_domain()
        company = self.company_id

        # Current period (inception up to date_to)
        dom_curr = [
            ('company_id', '=', company.id),
            ('date', '<=', self.date_to),
            ('account_id.internal_group', 'in', ['asset', 'liability', 'equity', 'income', 'expense']),
            *state_domain,
        ]
        curr_groups = self.env['account.move.line']._read_group(
            dom_curr,
            groupby=['account_id'],
            aggregates=['balance:sum'],
        )
        curr_map = {acc.id: (bal or 0.0) for acc, bal in curr_groups}

        # Comparison period
        comp_map = {}
        if self.enable_comparison and self.comparison_date_to:
            dom_comp = [
                ('company_id', '=', company.id),
                ('date', '<=', self.comparison_date_to),
                ('account_id.internal_group', 'in', ['asset', 'liability', 'equity', 'income', 'expense']),
                *state_domain,
            ]
            comp_groups = self.env['account.move.line']._read_group(
                dom_comp,
                groupby=['account_id'],
                aggregates=['balance:sum'],
            )
            comp_map = {acc.id: (bal or 0.0) for acc, bal in comp_groups}

        all_acc_ids = set(curr_map.keys()) | set(comp_map.keys())
        accounts = self.env['account.account'].browse(all_acc_ids).sorted(key=lambda a: a.code)

        asset_lines = []
        liability_lines = []
        equity_lines = []

        total_assets_curr = total_assets_comp = 0.0
        total_liab_curr = total_liab_comp = 0.0
        total_equity_curr = total_equity_comp = 0.0
        unallocated_pnl_curr = unallocated_pnl_comp = 0.0

        for acc in accounts:
            c_bal = curr_map.get(acc.id, 0.0)
            cmp_bal = comp_map.get(acc.id, 0.0)

            if acc.internal_group in ('income', 'expense'):
                unallocated_pnl_curr -= c_bal
                unallocated_pnl_comp -= cmp_bal
                continue

            if acc.internal_group == 'asset':
                val_curr = c_bal
                val_comp = cmp_bal
                total_assets_curr += val_curr
                total_assets_comp += val_comp
                asset_lines.append({
                    'code': acc.code,
                    'name': acc.name,
                    'current': val_curr,
                    'comparison': val_comp,
                    'diff': val_curr - val_comp,
                })
            elif acc.internal_group == 'liability':
                val_curr = -c_bal
                val_comp = -cmp_bal
                total_liab_curr += val_curr
                total_liab_comp += val_comp
                liability_lines.append({
                    'code': acc.code,
                    'name': acc.name,
                    'current': val_curr,
                    'comparison': val_comp,
                    'diff': val_curr - val_comp,
                })
            elif acc.internal_group == 'equity':
                val_curr = -c_bal
                val_comp = -cmp_bal
                total_equity_curr += val_curr
                total_equity_comp += val_comp
                equity_lines.append({
                    'code': acc.code,
                    'name': acc.name,
                    'current': val_curr,
                    'comparison': val_comp,
                    'diff': val_curr - val_comp,
                })

        total_equity_curr += unallocated_pnl_curr
        total_equity_comp += unallocated_pnl_comp

        return {
            'asset_lines': asset_lines,
            'liability_lines': liability_lines,
            'equity_lines': equity_lines,
            'unallocated_pnl_curr': unallocated_pnl_curr,
            'unallocated_pnl_comp': unallocated_pnl_comp,
            'total_assets_curr': total_assets_curr,
            'total_assets_comp': total_assets_comp,
            'total_liab_curr': total_liab_curr,
            'total_liab_comp': total_liab_comp,
            'total_equity_curr': total_equity_curr,
            'total_equity_comp': total_equity_comp,
            'total_liab_equity_curr': total_liab_curr + total_equity_curr,
            'total_liab_equity_comp': total_liab_comp + total_equity_comp,
        }

    def _get_aged_partner_data(self, account_type):
        self.ensure_one()
        today = self.date_to
        dom = [
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', '=', account_type),
            ('date', '<=', self.date_to),
            ('reconciled', '=', False),
            *self._get_target_state_domain(),
        ]
        lines = self.env['account.move.line'].search(dom, order='partner_id, date_maturity, date')
        partner_data = {}

        for l in lines:
            partner = l.partner_id or self.env['res.partner'].browse()
            p_name = partner.name or _("Unknown Partner")
            if p_name not in partner_data:
                partner_data[p_name] = {
                    'current': 0.0,
                    'days_1_30': 0.0,
                    'days_31_60': 0.0,
                    'days_61_90': 0.0,
                    'days_91_120': 0.0,
                    'days_over_120': 0.0,
                    'total': 0.0,
                }
            due_date = l.date_maturity or l.date
            overdue_days = (today - due_date).days if due_date else 0
            # for payable, normal balance is negative, so flip sign for presentation
            amount = l.amount_residual if account_type == 'asset_receivable' else -l.amount_residual

            if overdue_days <= 0:
                partner_data[p_name]['current'] += amount
            elif overdue_days <= 30:
                partner_data[p_name]['days_1_30'] += amount
            elif overdue_days <= 60:
                partner_data[p_name]['days_31_60'] += amount
            elif overdue_days <= 90:
                partner_data[p_name]['days_61_90'] += amount
            elif overdue_days <= 120:
                partner_data[p_name]['days_91_120'] += amount
            else:
                partner_data[p_name]['days_over_120'] += amount
            partner_data[p_name]['total'] += amount

        return partner_data

    def _get_cash_flow_data(self):
        self.ensure_one()
        company = self.company_id
        state_domain = self._get_target_state_domain()

        # Opening balance
        opening_cash = 0.0
        if self.date_from:
            dom_open = [
                ('company_id', '=', company.id),
                ('date', '<', self.date_from),
                ('account_id.account_type', '=', 'asset_cash'),
                *state_domain,
            ]
            groups = self.env['account.move.line']._read_group(dom_open, aggregates=['balance:sum'])
            opening_cash = groups[0][0] or 0.0 if groups else 0.0

        # Period moves on cash accounts
        dom_period = [
            ('company_id', '=', company.id),
            ('date', '<=', self.date_to),
            ('account_id.account_type', '=', 'asset_cash'),
            *state_domain,
        ]
        if self.date_from:
            dom_period.append(('date', '>=', self.date_from))

        groups = self.env['account.move.line']._read_group(
            dom_period,
            aggregates=['debit:sum', 'credit:sum', 'balance:sum'],
        )
        period_debit = groups[0][0] or 0.0 if groups else 0.0
        period_credit = groups[0][1] or 0.0 if groups else 0.0
        net_cash_change = groups[0][2] or 0.0 if groups else 0.0

        return {
            'opening_cash': opening_cash,
            'period_inflows': period_debit,
            'period_outflows': period_credit,
            'net_change': net_cash_change,
            'closing_cash': opening_cash + net_cash_change,
        }

    def action_print_pdf(self):
        self.ensure_one()
        report_ref_map = {
            'trial_balance': 'ydod_accounting_community.action_report_trial_balance',
            'pnl': 'ydod_accounting_community.action_report_pnl',
            'balance_sheet': 'ydod_accounting_community.action_report_balance_sheet',
            'general_ledger': 'ydod_accounting_community.action_report_trial_balance',
            'partner_ledger': 'ydod_accounting_community.action_report_trial_balance',
            'aged_receivable': 'ydod_accounting_community.action_report_aged_partner',
            'aged_payable': 'ydod_accounting_community.action_report_aged_partner',
            'cash_flow': 'ydod_accounting_community.action_report_cash_flow',
        }
        ref = report_ref_map.get(self.report_type, 'ydod_accounting_community.action_report_trial_balance')
        return self.env.ref(ref).report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        if self.report_type == 'trial_balance':
            data = self._get_trial_balance_data()
            writer.writerow(["Code", "Account Name", "Initial Debit", "Initial Credit", "Period Debit", "Period Credit", "Ending Debit", "Ending Credit"])
            for l in data['lines']:
                writer.writerow([l['code'], l['name'], l['initial_debit'], l['initial_credit'], l['period_debit'], l['period_credit'], l['ending_debit'], l['ending_credit']])
            t = data['totals']
            writer.writerow(["TOTAL", "", t['initial_debit'], t['initial_credit'], t['period_debit'], t['period_credit'], t['ending_debit'], t['ending_credit']])

        elif self.report_type == 'pnl':
            data = self._get_pnl_data()
            writer.writerow(["Section", "Code", "Account Name", "Current Period", "Comparison Period", "Difference"])
            for l in data['income_lines']:
                writer.writerow(["Income", l['code'], l['name'], l['current'], l['comparison'], l['diff']])
            writer.writerow(["Total Income", "", "", data['total_income_curr'], data['total_income_comp'], data['total_income_curr'] - data['total_income_comp']])
            for l in data['expense_lines']:
                writer.writerow(["Expense", l['code'], l['name'], l['current'], l['comparison'], l['diff']])
            writer.writerow(["Total Expense", "", "", data['total_expense_curr'], data['total_expense_comp'], data['total_expense_curr'] - data['total_expense_comp']])
            writer.writerow(["Net Profit / (Loss)", "", "", data['net_profit_curr'], data['net_profit_comp'], data['net_profit_diff']])

        elif self.report_type == 'balance_sheet':
            data = self._get_balance_sheet_data()
            writer.writerow(["Section", "Code", "Account Name", "Current Period", "Comparison Period", "Difference"])
            for l in data['asset_lines']:
                writer.writerow(["Assets", l['code'], l['name'], l['current'], l['comparison'], l['diff']])
            writer.writerow(["Total Assets", "", "", data['total_assets_curr'], data['total_assets_comp'], data['total_assets_curr'] - data['total_assets_comp']])
            for l in data['liability_lines']:
                writer.writerow(["Liabilities", l['code'], l['name'], l['current'], l['comparison'], l['diff']])
            writer.writerow(["Total Liabilities", "", "", data['total_liab_curr'], data['total_liab_comp'], data['total_liab_curr'] - data['total_liab_comp']])
            for l in data['equity_lines']:
                writer.writerow(["Equity", l['code'], l['name'], l['current'], l['comparison'], l['diff']])
            writer.writerow(["Unallocated Earnings", "", "", data['unallocated_pnl_curr'], data['unallocated_pnl_comp'], data['unallocated_pnl_curr'] - data['unallocated_pnl_comp']])
            writer.writerow(["Total Equity", "", "", data['total_equity_curr'], data['total_equity_comp'], data['total_equity_curr'] - data['total_equity_comp']])
            writer.writerow(["Total Liabilities & Equity", "", "", data['total_liab_equity_curr'], data['total_liab_equity_comp'], data['total_liab_equity_curr'] - data['total_liab_equity_comp']])

        elif self.report_type in ('aged_receivable', 'aged_payable'):
            acc_type = 'asset_receivable' if self.report_type == 'aged_receivable' else 'liability_payable'
            data = self._get_aged_partner_data(acc_type)
            writer.writerow(["Partner", "Current", "1 - 30 Days", "31 - 60 Days", "61 - 90 Days", "91 - 120 Days", "120+ Days", "Total"])
            for partner, vals in data.items():
                writer.writerow([partner, vals['current'], vals['days_1_30'], vals['days_31_60'], vals['days_61_90'], vals['days_91_120'], vals['days_over_120'], vals['total']])

        elif self.report_type == 'cash_flow':
            data = self._get_cash_flow_data()
            writer.writerow(["Indicator", "Amount"])
            writer.writerow(["Opening Cash Balance", data['opening_cash']])
            writer.writerow(["Period Cash Inflows", data['period_inflows']])
            writer.writerow(["Period Cash Outflows", data['period_outflows']])
            writer.writerow(["Net Change in Cash", data['net_change']])
            writer.writerow(["Closing Cash Balance", data['closing_cash']])

        csv_content = output.getvalue()
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.report_type}_{self.date_to}.csv",
            'type': 'binary',
            'datas': base64.b64encode(csv_content.encode('utf-8-sig')),
            'mimetype': 'text/csv',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
