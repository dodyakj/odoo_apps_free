from datetime import date
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestYdodBudget(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Budget Test Company'})
        cls.company_b = cls.env['res.company'].create({'name': 'Budget Other Company'})
        Account = cls.env['account.account'].with_company(cls.company)
        cls.expense_1 = Account.create({
            'name': 'Budget Marketing', 'code': '690001', 'account_type': 'expense',
            'company_ids': [Command.set(cls.company.ids)],
        })
        cls.expense_2 = Account.create({
            'name': 'Budget Travel', 'code': '690002', 'account_type': 'expense',
            'company_ids': [Command.set(cls.company.ids)],
        })
        cls.revenue = Account.create({
            'name': 'Budget Consulting', 'code': '790001', 'account_type': 'income',
            'company_ids': [Command.set(cls.company.ids)],
        })
        cls.liability = Account.create({
            'name': 'Budget Payable', 'code': '490001', 'account_type': 'liability_current',
            'company_ids': [Command.set(cls.company.ids)],
        })
        cls.journal = cls.env['account.journal'].with_company(cls.company).create({
            'name': 'Budget Miscellaneous', 'code': 'BUDG', 'type': 'general', 'company_id': cls.company.id,
        })
        project_plan, _other_plans = cls.env['account.analytic.plan']._get_all_plans()
        cls.analytic = cls.env['account.analytic.account'].create({
            'name': 'Budget Cost Centre', 'plan_id': project_plan.id, 'company_id': cls.company.id,
        })
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user = Users.create({
            'name': 'Budget User', 'login': 'ydod_budget_user',
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'group_ids': [Command.set(cls.env.ref('ydod_account_budget.group_budget_user').ids)],
        })
        cls.manager = Users.create({
            'name': 'Budget Manager', 'login': 'ydod_budget_manager',
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'group_ids': [Command.set(cls.env.ref('ydod_account_budget.group_budget_manager').ids)],
        })
        cls.user_b = Users.create({
            'name': 'Budget User B', 'login': 'ydod_budget_user_b',
            'company_id': cls.company_b.id, 'company_ids': [Command.set(cls.company_b.ids)],
            'group_ids': [Command.set(cls.env.ref('ydod_account_budget.group_budget_user').ids)],
        })

    def _create_budget(self, date_from='2026-01-01', date_to='2026-12-31', lines=None):
        return self.env['ydod.budget'].create({
            'name': 'FY Budget',
            'company_id': self.company.id,
            'date_from': date_from,
            'date_to': date_to,
            'line_ids': [Command.create(vals) for vals in (lines or [])],
        })

    def _line_vals(self, **kwargs):
        vals = {
            'analytic_account_id': self.analytic.id,
            'position_name': 'Marketing Expenses',
            'planned_amount': -3650.0,
        }
        vals.update(kwargs)
        return vals

    def _entry(self, account, amount, post=True):
        move = self.env['account.move'].with_company(self.company).create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': '2026-03-15',
            'line_ids': [
                Command.create({
                    'name': 'Budget expense', 'account_id': account.id, 'debit': amount, 'credit': 0.0,
                    'analytic_distribution': {str(self.analytic.id): 100},
                }),
                Command.create({
                    'name': 'Counterpart', 'account_id': self.liability.id, 'debit': 0.0, 'credit': amount,
                }),
            ],
        })
        if post:
            move.action_post()
        return move

    def _freeze(self, day):
        return patch.object(self.registry['ydod.budget.line'], '_get_today', lambda self: day)

    def test_actual_amount_from_posted_items(self):
        budget = self._create_budget(lines=[
            self._line_vals(general_account_ids=[Command.set(self.expense_1.ids)]),
            self._line_vals(position_name='All Accounts'),
        ])
        line_filtered, line_all = budget.line_ids.sorted('id')
        self._entry(self.expense_1, 1000.0)
        self._entry(self.expense_1, 500.0, post=False)
        self._entry(self.expense_2, 300.0)
        budget.action_refresh()
        self.assertAlmostEqual(line_filtered.actual_amount, -1000.0)
        self.assertAlmostEqual(line_all.actual_amount, -1300.0)
        self.assertAlmostEqual(budget.actual_total, -2300.0)
        action = line_filtered.action_open_entries()
        items = self.env['account.analytic.line'].search(action['domain'])
        self.assertAlmostEqual(sum(items.mapped('amount')), line_filtered.actual_amount)

    def test_cron_refreshes_confirmed_budgets(self):
        budget = self._create_budget(lines=[self._line_vals()])
        budget.with_user(self.manager).action_confirm()
        self._entry(self.expense_1, 250.0)
        self.env['ydod.budget.line']._cron_refresh_amounts()
        self.assertAlmostEqual(budget.line_ids.actual_amount, -250.0)

    def test_theoretical_amount(self):
        budget = self._create_budget(lines=[self._line_vals()])
        line = budget.line_ids
        with self._freeze(date(2026, 7, 2)):
            line._refresh_amounts()
        self.assertAlmostEqual(line.theoretical_amount, -1830.0)
        with self._freeze(date(2025, 12, 31)):
            line._refresh_amounts()
        self.assertAlmostEqual(line.theoretical_amount, 0.0)
        with self._freeze(date(2027, 1, 1)):
            line._refresh_amounts()
        self.assertAlmostEqual(line.theoretical_amount, -3650.0)

    def test_achievement_and_over_budget(self):
        budget = self._create_budget(lines=[
            self._line_vals(),
            self._line_vals(position_name='Consulting Revenue', planned_amount=1000.0),
        ])
        expense, revenue = budget.line_ids.sorted('id')
        expense.sudo().write({'actual_amount': -600.0, 'theoretical_amount': -500.0})
        self.assertAlmostEqual(expense.achievement_percent, 120.0)
        self.assertTrue(expense.is_over_budget)
        revenue.sudo().write({'actual_amount': 100.0, 'theoretical_amount': 500.0})
        self.assertAlmostEqual(revenue.achievement_percent, 20.0)
        self.assertFalse(revenue.is_over_budget)
        expense.sudo().write({'actual_amount': -100.0, 'theoretical_amount': 0.0})
        self.assertEqual(expense.achievement_percent, 0.0)

    def test_constraints(self):
        budget = self._create_budget()
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception), self.cr.savepoint():
            self.env['ydod.budget.line'].create(self._line_vals(
                budget_id=budget.id, date_from='2026-05-01', date_to='2026-04-01'))
        with self.assertRaises(ValidationError):
            self.env['ydod.budget.line'].create(self._line_vals(
                budget_id=budget.id, date_from='2025-12-01', date_to='2026-01-31'))
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception), self.cr.savepoint():
            self._create_budget(date_from='2026-12-31', date_to='2026-01-01')
        line = self.env['ydod.budget.line'].create(self._line_vals(budget_id=budget.id))
        self.assertEqual(line.date_from, budget.date_from)
        self.assertEqual(line.date_to, budget.date_to)

    def test_workflow(self):
        budget = self._create_budget(lines=[self._line_vals()])
        with self.assertRaises(AccessError):
            budget.with_user(self.user).action_confirm()
        budget_manager = budget.with_user(self.manager)
        budget_manager.action_confirm()
        self.assertEqual(budget.state, 'confirm')
        self.assertEqual(budget.line_ids.state, 'confirm')
        budget_manager.action_validate()
        self.assertEqual(budget.state, 'validate')
        with self.assertRaises(UserError):
            budget_manager.unlink()
        budget_manager.action_done()
        self.assertEqual(budget.state, 'done')
        with self.assertRaises(UserError):
            budget_manager.action_cancel()
        other = self._create_budget().with_user(self.manager)
        other.action_cancel()
        other.action_draft()
        self.assertEqual(other.state, 'draft')

    def test_access_rights(self):
        budget = self.env['ydod.budget'].with_user(self.user).create({
            'name': 'User Draft', 'date_from': '2026-01-01', 'date_to': '2026-12-31',
            'line_ids': [Command.create(self._line_vals())],
        })
        self.assertEqual(budget.company_id, self.company)
        budget.line_ids.planned_amount = -1000.0
        self.assertEqual(budget.line_ids.planned_amount, -1000.0)
        with self.assertRaises(AccessError):
            budget.unlink()
        budget.with_user(self.manager).action_confirm()
        budget.with_user(self.manager).action_validate()
        with self.assertRaises(AccessError):
            budget.line_ids.with_user(self.user).write({'planned_amount': -2000.0})
        with self.assertRaises(AccessError):
            budget.with_user(self.user).write({'name': 'Changed'})
        with self.assertRaises(AccessError):
            budget.with_user(self.user_b).read(['name'])

    def test_copy_next_period(self):
        budget = self._create_budget(lines=[self._line_vals(planned_amount=-1200.0)])
        budget.with_user(self.manager).action_confirm()
        with self.assertRaises(UserError):
            budget.with_user(self.manager).action_copy_next_period()
        budget.with_user(self.manager).action_validate()
        with self.assertRaises(AccessError):
            budget.with_user(self.user).action_copy_next_period()
        action = budget.with_user(self.manager).action_copy_next_period()
        new_budget = self.env['ydod.budget'].browse(action['res_id'])
        self.assertEqual(new_budget.state, 'draft')
        self.assertEqual(new_budget.date_from, date(2027, 1, 1))
        self.assertEqual(new_budget.date_to, date(2027, 12, 31))
        self.assertEqual(new_budget.line_ids.planned_amount, -1200.0)
        self.assertEqual(new_budget.line_ids.date_to, date(2027, 12, 31))

    def test_copy_leap_day(self):
        budget = self._create_budget('2028-01-01', '2028-12-31', lines=[
            self._line_vals(date_from='2028-02-01', date_to='2028-02-29'),
        ])
        budget.with_user(self.manager).action_confirm()
        budget.with_user(self.manager).action_validate()
        action = budget.with_user(self.manager).action_copy_next_period()
        line = self.env['ydod.budget'].browse(action['res_id']).line_ids
        self.assertEqual(line.date_from, date(2029, 2, 1))
        self.assertEqual(line.date_to, date(2029, 2, 28))
