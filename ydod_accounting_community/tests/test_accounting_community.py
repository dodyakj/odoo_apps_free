# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo import fields


@tagged('post_install', '-at_install')
class TestAccountingCommunity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'yDoD Test Accounting Company',
            'currency_id': cls.env.ref('base.USD').id,
        })
        cls.company_b = cls.env['res.company'].create({
            'name': 'yDoD Test Company B',
            'currency_id': cls.env.ref('base.USD').id,
        })

        cls.user_accountant = cls.env['res.users'].create({
            'name': 'Test Accountant User',
            'login': 'test_accountant_ydod',
            'email': 'accountant@ydod.test',
            'company_id': cls.company.id,
            'company_ids': [fields.Command.set([cls.company.id])],
            'groups_id': [fields.Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('account.group_account_user').id,
            ])],
        })

        cls.user_manager = cls.env['res.users'].create({
            'name': 'Test Manager User',
            'login': 'test_manager_ydod',
            'email': 'manager@ydod.test',
            'company_id': cls.company.id,
            'company_ids': [fields.Command.set([cls.company.id])],
            'groups_id': [fields.Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('account.group_account_manager').id,
            ])],
        })

        cls.acc_bank = cls.env['account.account'].create({
            'name': 'Test Bank Account',
            'code': '101001',
            'account_type': 'asset_cash',
            'company_id': cls.company.id,
        })

        cls.acc_income = cls.env['account.account'].create({
            'name': 'Test Operating Revenue',
            'code': '401001',
            'account_type': 'income',
            'company_id': cls.company.id,
        })

        cls.acc_expense = cls.env['account.account'].create({
            'name': 'Test Operating Expense',
            'code': '501001',
            'account_type': 'expense',
            'company_id': cls.company.id,
        })

        cls.acc_retained = cls.env['account.account'].create({
            'name': 'Test Retained Earnings',
            'code': '999001',
            'account_type': 'equity_unaffected',
            'company_id': cls.company.id,
        })

        cls.journal_general = cls.env['account.journal'].create({
            'name': 'Miscellaneous Test Journal',
            'code': 'MISCT',
            'type': 'general',
            'company_id': cls.company.id,
        })

        cls.journal_bank = cls.env['account.journal'].create({
            'name': 'Test Commercial Bank',
            'code': 'BNKT',
            'type': 'bank',
            'company_id': cls.company.id,
            'default_account_id': cls.acc_bank.id,
        })

    def test_fiscal_year_date_constraint(self):
        """Verify constraint error is raised when date_from is later than date_to."""
        with self.assertRaises(ValidationError):
            self.env['account.fiscal.year'].create({
                'name': 'Invalid FY 2026',
                'code': 'FY26-INV',
                'date_from': '2026-12-31',
                'date_to': '2026-01-01',
                'company_id': self.company.id,
            })

    def test_fiscal_year_name_unique(self):
        """Ensure creating duplicate fiscal year names within the same company raises a constraint error."""
        self.env['account.fiscal.year'].create({
            'name': 'FY2026-UNIQUE',
            'code': 'FY26U1',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': self.company.id,
        })
        with self.assertRaises(ValidationError):
            self.env['account.fiscal.year'].create({
                'name': 'FY2026-UNIQUE',
                'code': 'FY26U2',
                'date_from': '2026-01-01',
                'date_to': '2026-12-31',
                'company_id': self.company.id,
            })

    def test_fiscal_year_state_workflow(self):
        """Verify state transitions from draft to open and finally to closed."""
        fy = self.env['account.fiscal.year'].create({
            'name': 'FY2028 Test Workflow',
            'code': 'FY28W',
            'date_from': '2028-01-01',
            'date_to': '2028-12-31',
            'company_id': self.company.id,
        })
        self.assertEqual(fy.state, 'draft')
        fy.action_open()
        self.assertEqual(fy.state, 'open')
        fy.action_close()
        self.assertEqual(fy.state, 'closed')
        fy.action_draft()
        self.assertEqual(fy.state, 'draft')

    def test_closing_entry_generation(self):
        """Validate closing entry zeroes all P&L account balances into the retained earnings account."""
        fy = self.env['account.fiscal.year'].create({
            'name': 'FY2026 Closing Test',
            'code': 'FY26C',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': self.company.id,
        })
        fy.action_open()

        # Create posted entry in period: Revenue 500 (credit), Expense 200 (debit), Bank 300 (debit)
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_general.id,
            'date': '2026-06-15',
            'ref': 'Operating Transaction',
            'company_id': self.company.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': self.acc_income.id,
                    'name': 'Product Sales',
                    'debit': 0.0,
                    'credit': 500.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_expense.id,
                    'name': 'Office Supplies',
                    'debit': 200.0,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_bank.id,
                    'name': 'Cash Inflow',
                    'debit': 300.0,
                    'credit': 0.0,
                }),
            ],
        })
        move.action_post()
        self.assertEqual(fy.move_count, 1)

        # Generate closing entry
        res = fy.action_generate_closing_entry()
        self.assertTrue(res)
        self.assertEqual(fy.state, 'closed')
        self.assertTrue(bool(fy.closing_move_id))
        self.assertEqual(fy.closing_move_id.state, 'posted')

        # Verify net P&L balances as of date_to are zeroed out
        domain_income = [
            ('account_id', '=', self.acc_income.id),
            ('date', '<=', fy.date_to),
            ('parent_state', '=', 'posted'),
        ]
        income_groups = self.env['account.move.line']._read_group(domain_income, aggregates=['balance:sum'])
        income_balance = income_groups[0][0] or 0.0
        self.assertAlmostEqual(income_balance, 0.0)

        domain_expense = [
            ('account_id', '=', self.acc_expense.id),
            ('date', '<=', fy.date_to),
            ('parent_state', '=', 'posted'),
        ]
        expense_groups = self.env['account.move.line']._read_group(domain_expense, aggregates=['balance:sum'])
        expense_balance = expense_groups[0][0] or 0.0
        self.assertAlmostEqual(expense_balance, 0.0)

    def test_reconcile_wizard_gl_balance(self):
        """Verify bank reconcile wizard computes accurate GL balance using _read_group."""
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_bank.id,
            'date': '2026-03-10',
            'ref': 'Bank Capital Deposit',
            'company_id': self.company.id,
            'line_ids': [
                fields.Command.create({
                    'account_id': self.acc_bank.id,
                    'name': 'Initial Bank Balance',
                    'debit': 1500.0,
                    'credit': 0.0,
                }),
                fields.Command.create({
                    'account_id': self.acc_income.id,
                    'name': 'Capital Inflow',
                    'debit': 0.0,
                    'credit': 1500.0,
                }),
            ],
        })
        move.action_post()

        wizard = self.env['account.bank.reconcile.statement'].create({
            'journal_id': self.journal_bank.id,
            'statement_date': '2026-03-31',
            'bank_statement_balance': 1500.0,
        })
        self.assertAlmostEqual(wizard.gl_balance, 1500.0)
        self.assertAlmostEqual(wizard.uncleared_balance, 1500.0)

    def test_reconcile_wizard_difference(self):
        """Verify variance calculation correctly subtracts GL and uncleared items from statement balance."""
        wizard = self.env['account.bank.reconcile.statement'].create({
            'journal_id': self.journal_bank.id,
            'statement_date': '2026-05-01',
            'bank_statement_balance': 2500.0,
        })
        expected_diff = wizard.bank_statement_balance - wizard.gl_balance - wizard.uncleared_balance
        self.assertAlmostEqual(wizard.difference, expected_diff)

    def test_user_read_only_access(self):
        """Confirm standard users cannot create, modify, or close fiscal years."""
        fy = self.env['account.fiscal.year'].create({
            'name': 'FY2026 Security Check',
            'code': 'FY26SEC',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': self.company.id,
        })

        # Read is allowed
        fy_read = fy.with_user(self.user_accountant).read(['name', 'state'])
        self.assertEqual(fy_read[0]['name'], 'FY2026 Security Check')

        # Create is blocked
        with self.assertRaises(AccessError):
            self.env['account.fiscal.year'].with_user(self.user_accountant).create({
                'name': 'Unauthorized FY',
                'code': 'UNAUTH',
                'date_from': '2026-01-01',
                'date_to': '2026-12-31',
                'company_id': self.company.id,
            })

        # Write is blocked
        with self.assertRaises(AccessError):
            fy.with_user(self.user_accountant).write({'name': 'Tampered Name'})

        # Closing is blocked
        with self.assertRaises(AccessError):
            fy.with_user(self.user_accountant).action_close()

    def test_multi_company_security(self):
        """Confirm record rules prevent users in Company A from viewing or closing Company B fiscal years."""
        fy_b = self.env['account.fiscal.year'].create({
            'name': 'Company B Fiscal Year 2026',
            'code': 'COB-FY26',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': self.company_b.id,
        })

        # User in Company A searching fiscal years cannot see Company B fiscal year
        visible_fys = self.env['account.fiscal.year'].with_user(self.user_manager).search([
            ('id', '=', fy_b.id),
        ])
        self.assertFalse(visible_fys)

        # Attempting to write directly to Company B fiscal year raises AccessError
        with self.assertRaises(AccessError):
            fy_b.with_user(self.user_manager).write({'code': 'COB-HACKED'})
