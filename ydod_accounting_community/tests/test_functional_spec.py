# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo import fields
from psycopg2 import IntegrityError


@tagged('post_install', '-at_install')
class TestFunctionalSpec(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env['res.company'].create({
            'name': 'yDoD Functional Test Company A',
            'currency_id': cls.env.ref('base.USD').id,
        })
        cls.company_b = cls.env['res.company'].create({
            'name': 'yDoD Functional Test Company B',
            'currency_id': cls.env.ref('base.USD').id,
        })

        cls.user_accountant = cls.env['res.users'].create({
            'name': 'Test Accountant Role User',
            'login': 'test_accountant_role',
            'email': 'accountant_role@ydod.test',
            'company_id': cls.company_a.id,
            'company_ids': [fields.Command.set([cls.company_a.id])],
            'group_ids': [fields.Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('account.group_account_user').id,
                cls.env.ref('ydod_accounting_community.group_accounting_user').id,
            ])],
        })

        cls.user_manager = cls.env['res.users'].create({
            'name': 'Test Manager Role User',
            'login': 'test_manager_role',
            'email': 'manager_role@ydod.test',
            'company_id': cls.company_a.id,
            'company_ids': [fields.Command.set([cls.company_a.id])],
            'group_ids': [fields.Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('account.group_account_manager').id,
                cls.env.ref('ydod_accounting_community.group_accounting_manager').id,
            ])],
        })

        # Chart of accounts setup for company A
        cls.acc_bank = cls.env['account.account'].create({
            'name': 'Test Bank A',
            'code': '102001',
            'account_type': 'asset_cash',
            'company_ids': [fields.Command.link(cls.company_a.id)],
        })
        cls.acc_receivable = cls.env['account.account'].create({
            'name': 'Test Receivable A',
            'code': '120001',
            'account_type': 'asset_receivable',
            'reconcile': True,
            'company_ids': [fields.Command.link(cls.company_a.id)],
        })
        cls.acc_income = cls.env['account.account'].create({
            'name': 'Test Sales Income A',
            'code': '400001',
            'account_type': 'income',
            'company_ids': [fields.Command.link(cls.company_a.id)],
        })
        cls.acc_expense = cls.env['account.account'].create({
            'name': 'Test Operating Expense A',
            'code': '500001',
            'account_type': 'expense',
            'company_ids': [fields.Command.link(cls.company_a.id)],
        })
        cls.acc_retained = cls.env['account.account'].create({
            'name': 'Test Retained Earnings A',
            'code': '990001',
            'account_type': 'equity_unaffected',
            'company_ids': [fields.Command.link(cls.company_a.id)],
        })
        cls.company_a.retained_earnings_account_id = cls.acc_retained

        cls.acc_asset = cls.env['account.account'].create({
            'name': 'Test Fixed Asset Vehicle',
            'code': '150001',
            'account_type': 'asset_fixed',
            'company_ids': [fields.Command.link(cls.company_a.id)],
        })
        cls.acc_accum_depr = cls.env['account.account'].create({
            'name': 'Test Accum Depreciation Vehicle',
            'code': '159001',
            'account_type': 'asset_non_current',
            'company_ids': [fields.Command.link(cls.company_a.id)],
        })
        cls.acc_depr_expense = cls.env['account.account'].create({
            'name': 'Test Depreciation Expense',
            'code': '650001',
            'account_type': 'expense',
            'company_ids': [fields.Command.link(cls.company_a.id)],
        })

        cls.journal_general = cls.env['account.journal'].create({
            'name': 'General Test Journal',
            'code': 'GENA',
            'type': 'general',
            'company_id': cls.company_a.id,
        })
        cls.journal_bank = cls.env['account.journal'].create({
            'name': 'Bank Test Journal',
            'code': 'BNKA',
            'type': 'bank',
            'company_id': cls.company_a.id,
            'default_account_id': cls.acc_bank.id,
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Accounting Customer Corp',
            'company_id': cls.company_a.id,
        })

    def test_ydod_fiscal_year_constraints(self):
        """Test fiscal year date constraints, unique code per company, and closed date modification."""
        # 1. Date constraint: start date must precede end date
        with mute_logger('odoo.sql_db'), self.assertRaises((ValidationError, IntegrityError, Exception)):
            self.env['ydod.fiscal.year'].create({
                'name': 'Invalid FY Dates',
                'code': 'FYINV1',
                'date_from': '2026-12-31',
                'date_to': '2026-01-01',
                'company_id': self.company_a.id,
            })

        # 2. Unique code constraint per company
        self.env['ydod.fiscal.year'].create({
            'name': 'FY2026 Normal',
            'code': 'FY26-UNIQ',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': self.company_a.id,
        })
        with mute_logger('odoo.sql_db'), self.assertRaises((ValidationError, IntegrityError, Exception)):
            self.env['ydod.fiscal.year'].create({
                'name': 'FY2026 Duplicate Code',
                'code': 'FY26-UNIQ',
                'date_from': '2026-01-01',
                'date_to': '2026-12-31',
                'company_id': self.company_a.id,
            })

        # 3. Closed state date modification constraint
        fy_closed = self.env['ydod.fiscal.year'].create({
            'name': 'FY2025 Closed',
            'code': 'FY25-CLS',
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'company_id': self.company_a.id,
            'state': 'closed',
        })
        with self.assertRaises(ValidationError):
            fy_closed.write({'date_to': '2025-11-30'})

    def test_ydod_closing_wizard_execution(self):
        """Test fiscal year closing wizard: clearing P&L to retained earnings, lock dates, and draft entry protection."""
        fy = self.env['ydod.fiscal.year'].create({
            'name': 'FY2026 Full Closing',
            'code': 'FY26-CLOSE',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': self.company_a.id,
        })
        fy.action_open()

        # Create posted operational move in period: Revenue 1200 (credit), Expense 500 (debit), Bank 700 (debit)
        move_posted = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_general.id,
            'date': '2026-08-15',
            'ref': 'Operating Revenue & Expense',
            'company_id': self.company_a.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': self.acc_income.id,
                    'name': 'Consulting Sales',
                    'debit': 0.0,
                    'credit': 1200.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_expense.id,
                    'name': 'Software Licenses',
                    'debit': 500.0,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_bank.id,
                    'name': 'Net Bank Inflow',
                    'debit': 700.0,
                    'credit': 0.0,
                }),
            ],
        })
        move_posted.action_post()

        # Edge Case: Draft move in period should block fiscal closing
        draft_move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_general.id,
            'date': '2026-09-01',
            'ref': 'Unposted Draft Move',
            'company_id': self.company_a.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': self.acc_expense.id,
                    'name': 'Draft Expense',
                    'debit': 100.0,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_bank.id,
                    'name': 'Draft Bank',
                    'debit': 0.0,
                    'credit': 100.0,
                }),
            ],
        })

        wizard = self.env['ydod.fiscal.year.close.wizard'].create({
            'fiscal_year_id': fy.id,
            'journal_id': self.journal_general.id,
            'closing_account_id': self.acc_retained.id,
            'closing_date': fy.date_to,
            'description': 'Test FY2026 Closing',
            'company_id': self.company_a.id,
        })

        with self.assertRaises(UserError):
            wizard.action_close_fiscal_year()

        # Cancel draft move and proceed
        draft_move.unlink()

        # Execute closing
        res = wizard.action_close_fiscal_year()
        self.assertTrue(res)
        self.assertEqual(fy.state, 'closed')
        self.assertTrue(bool(fy.closing_move_id))
        self.assertEqual(fy.closing_move_id.state, 'posted')
        self.assertTrue(fy.closing_move_id.is_closing_entry)

        # Check P&L accounts zeroed out as of date_to
        income_groups = self.env['account.move.line']._read_group(
            [('account_id', '=', self.acc_income.id), ('date', '<=', fy.date_to), ('parent_state', '=', 'posted')],
            aggregates=['balance:sum'],
        )
        self.assertAlmostEqual(income_groups[0][0] or 0.0, 0.0)

        expense_groups = self.env['account.move.line']._read_group(
            [('account_id', '=', self.acc_expense.id), ('date', '<=', fy.date_to), ('parent_state', '=', 'posted')],
            aggregates=['balance:sum'],
        )
        self.assertAlmostEqual(expense_groups[0][0] or 0.0, 0.0)

        # Check company lock date updated
        self.assertEqual(self.company_a.fiscalyear_lock_date, fy.date_to)

    def test_bank_recon_audit_calculations(self):
        """Test bank reconciliation wizard GL balance, uncleared items, and auto-matching suggestions."""
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_bank.id,
            'date': '2026-04-10',
            'ref': 'Bank Capital Injection',
            'company_id': self.company_a.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': self.acc_bank.id,
                    'name': 'Deposit',
                    'debit': 3000.0,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_income.id,
                    'name': 'Capital',
                    'debit': 0.0,
                    'credit': 3000.0,
                }),
            ],
        })
        move.action_post()

        wizard = self.env['ydod.bank.recon.report.wizard'].create({
            'journal_id': self.journal_bank.id,
            'statement_date': '2026-04-30',
            'statement_balance': 3000.0,
            'company_id': self.company_a.id,
        })

        self.assertAlmostEqual(wizard.gl_balance, 3000.0)
        self.assertAlmostEqual(wizard.uncleared_deposits, 3000.0)
        self.assertAlmostEqual(wizard.uncleared_payments, 0.0)

        # Difference computation
        expected_diff = wizard.statement_balance - wizard.gl_balance - wizard.uncleared_deposits + wizard.uncleared_payments
        self.assertAlmostEqual(wizard.balance_difference, expected_diff)

        # Test smart match action
        action_match = wizard.action_auto_match_suggestions()
        self.assertEqual(action_match['res_model'], 'ydod.reconcile.lines.wizard')

    def test_manual_reconciliation_wizard(self):
        """Test multi-line manual reconciliation with balanced matching and write-offs."""
        # 1. Balanced items
        move1 = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_general.id,
            'date': '2026-05-01',
            'ref': 'Invoice 1',
            'company_id': self.company_a.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': self.acc_receivable.id,
                    'partner_id': self.partner.id,
                    'name': 'Receivable 1',
                    'debit': 250.0,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_income.id,
                    'name': 'Income 1',
                    'debit': 0.0,
                    'credit': 250.0,
                }),
            ],
        })
        move1.action_post()

        move2 = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_general.id,
            'date': '2026-05-05',
            'ref': 'Payment 1',
            'company_id': self.company_a.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': self.acc_bank.id,
                    'name': 'Bank In',
                    'debit': 250.0,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_receivable.id,
                    'partner_id': self.partner.id,
                    'name': 'Receivable Payment 1',
                    'debit': 0.0,
                    'credit': 250.0,
                }),
            ],
        })
        move2.action_post()

        rec_lines = (move1.line_ids + move2.line_ids).filtered(lambda l: l.account_id == self.acc_receivable)
        wizard = self.env['ydod.reconcile.lines.wizard'].create({
            'line_ids': [fields.Command.set(rec_lines.ids)],
            'company_id': self.company_a.id,
        })
        self.assertAlmostEqual(wizard.balance_difference, 0.0)
        wizard.action_reconcile()
        self.assertTrue(all(l.reconciled for l in rec_lines))

    def test_security_roles_and_multi_company(self):
        """Test role access permissions and multi-company isolation."""
        fy = self.env['ydod.fiscal.year'].create({
            'name': 'FY2026 Permissions Check',
            'code': 'FY26-PERM',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': self.company_a.id,
        })

        # Accountant can read
        fy_read = fy.with_user(self.user_accountant).read(['name', 'state'])
        self.assertEqual(fy_read[0]['name'], 'FY2026 Permissions Check')

        # Accountant cannot close fiscal year via wizard
        wizard_accountant = self.env['ydod.fiscal.year.close.wizard'].with_user(self.user_accountant)
        with self.assertRaises(AccessError):
            wizard_accountant.create({
                'fiscal_year_id': fy.id,
                'journal_id': self.journal_general.id,
                'closing_account_id': self.acc_retained.id,
                'closing_date': fy.date_to,
                'description': 'Unauthorized Close Attempt',
                'company_id': self.company_a.id,
            })

        # Multi-company isolation: Company B fiscal year invisible to User in Company A
        fy_b = self.env['ydod.fiscal.year'].create({
            'name': 'Company B FY 2026',
            'code': 'COB-2026',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': self.company_b.id,
        })
        search_b = self.env['ydod.fiscal.year'].with_user(self.user_manager).search([('id', '=', fy_b.id)])
        self.assertFalse(search_b)

    def test_fixed_asset_depreciation_lifecycle(self):
        """Test fixed asset creation, board computation, confirmation, and depreciation posting."""
        asset = self.env['ydod.account.asset'].create({
            'name': 'Operations Delivery Van',
            'code': 'VAN-001',
            'purchase_date': '2026-01-01',
            'purchase_value': 12000.0,
            'salvage_value': 0.0,
            'method_number': 12,
            'method_period': 'months',
            'account_asset_id': self.acc_asset.id,
            'account_depreciation_id': self.acc_accum_depr.id,
            'account_expense_id': self.acc_depr_expense.id,
            'journal_id': self.journal_general.id,
            'company_id': self.company_a.id,
        })

        # Compute board
        asset.action_compute_depreciation_board()
        self.assertEqual(len(asset.line_ids), 12)
        self.assertAlmostEqual(asset.line_ids[0].amount, 1000.0)

        # Confirm asset
        asset.action_confirm()
        self.assertEqual(asset.state, 'running')

        # Post first depreciation line
        line1 = asset.line_ids[0]
        line1.action_post_entry()
        self.assertEqual(line1.state, 'posted')
        self.assertTrue(bool(line1.move_id))
        self.assertEqual(line1.move_id.state, 'posted')

        # Verify cumulative asset values
        self.assertAlmostEqual(asset.value_depreciated, 1000.0)
        self.assertAlmostEqual(asset.value_residual, 11000.0)

    def test_budget_analytic_actuals(self):
        """Test budget vs actual aggregation across accounts."""
        budget = self.env['ydod.account.budget'].create({
            'name': 'Q1 2026 Operating Plan',
            'date_from': '2026-01-01',
            'date_to': '2026-03-31',
            'company_id': self.company_a.id,
            'line_ids': [
                fields.Command.create({
                    'name': 'Software Licensing Line',
                    'date_from': '2026-01-01',
                    'date_to': '2026-03-31',
                    'planned_amount': 5000.0,
                    'account_ids': [fields.Command.link(self.acc_expense.id)],
                }),
            ],
        })
        budget.action_confirm()
        budget.action_approve()
        self.assertEqual(budget.state, 'approved')

        # Post expense in budget period
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_general.id,
            'date': '2026-02-15',
            'ref': 'Cloud Server Subscription',
            'company_id': self.company_a.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': self.acc_expense.id,
                    'name': 'Cloud Fee',
                    'debit': 2000.0,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_bank.id,
                    'name': 'Bank Paid',
                    'debit': 0.0,
                    'credit': 2000.0,
                }),
            ],
        })
        move.action_post()

        b_line = budget.line_ids[0]
        b_line._compute_practical_amount()
        self.assertAlmostEqual(b_line.practical_amount, 2000.0)
        self.assertAlmostEqual(b_line.percentage, 40.0)

    def test_move_approval_workflow(self):
        """Test multi-level approval on journal moves."""
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_general.id,
            'date': '2026-06-10',
            'ref': 'Significant Capital Purchase',
            'company_id': self.company_a.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': self.acc_asset.id,
                    'name': 'Office Server Hardware',
                    'debit': 15000.0,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_bank.id,
                    'name': 'Bank Out',
                    'debit': 0.0,
                    'credit': 15000.0,
                }),
            ],
        })

        move.action_submit_for_approval()
        self.assertEqual(move.approval_state, 'to_approve')

        # Direct post is blocked while awaiting approval
        with self.assertRaises(UserError):
            move.action_post()

        # Manager approves
        move.with_user(self.user_manager).action_approve()
        self.assertEqual(move.approval_state, 'approved')
        self.assertEqual(move.approver_id, self.user_manager)

        # Move can now be posted
        move.action_post()
        self.assertEqual(move.state, 'posted')

    def test_financial_reports_wizard(self):
        """Test financial reports wizard calculations and CSV/Excel export."""
        report_wiz = self.env['ydod.financial.report.wizard'].create({
            'report_type': 'trial_balance',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': self.company_a.id,
        })
        tb_data = report_wiz._get_trial_balance_data()
        self.assertIn('lines', tb_data)
        self.assertIn('totals', tb_data)

        # Test P&L data
        report_wiz.report_type = 'pnl'
        pnl_data = report_wiz._get_pnl_data()
        self.assertIn('income_lines', pnl_data)
        self.assertIn('expense_lines', pnl_data)

        # Test Balance Sheet data
        report_wiz.report_type = 'balance_sheet'
        bs_data = report_wiz._get_balance_sheet_data()
        self.assertIn('asset_lines', bs_data)
        self.assertIn('liability_lines', bs_data)
        self.assertIn('equity_lines', bs_data)

        # Test Excel export
        export_action = report_wiz.action_export_excel()
        self.assertEqual(export_action.get('type'), 'ir.actions.act_url')
