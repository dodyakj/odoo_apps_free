from datetime import date, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestYdodAsset(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Asset Test Company', 'currency_id': cls.env.company.currency_id.id})
        Account = cls.env['account.account'].with_company(cls.company)

        def account(code, account_type, **kw):
            return Account.create(dict(code=code, name=f'Test {code}', account_type=account_type,
                                       company_id=cls.company.id, **kw))

        cls.account_asset = account('YT1710', 'asset_fixed')
        cls.account_accum = account('YT1719', 'asset_fixed')
        cls.account_expense = account('YT6811', 'expense_depreciation')
        cls.account_other = account('YT6100', 'expense')
        cls.account_loss = account('YT6819', 'expense')
        account('YT2110', 'liability_payable', reconcile=True)
        Journal = cls.env['account.journal']
        cls.journal = Journal.create({'name': 'Depreciation', 'code': 'YDEP', 'type': 'general',
                                      'company_id': cls.company.id})
        cls.bill_journal = Journal.create({'name': 'Test Bills', 'code': 'YBIL', 'type': 'purchase',
                                           'company_id': cls.company.id})
        cls.category = cls.env['ydod.asset.category'].create({
            'name': 'Test Equipment', 'company_id': cls.company.id,
            'account_asset_id': cls.account_asset.id, 'account_depreciation_id': cls.account_accum.id,
            'account_expense_id': cls.account_expense.id, 'journal_id': cls.journal.id,
            'method_number': 12, 'method_period': 'month', 'prorata': False,
            'auto_create': True, 'auto_confirm': True,
        })
        cls.today = fields.Date.context_today(cls.env['ydod.asset'])

    def _asset(self, **values):
        vals = {'name': 'Test Asset', 'category_id': self.category.id, 'original_value': 12000,
                'acquisition_date': date(2025, 1, 1), 'prorata': False, 'method_number': 12}
        vals.update(values)
        return self.env['ydod.asset'].create(vals)

    def _recent_asset(self, months_ago=3, life=6):
        year, month = divmod(self.today.year * 12 + self.today.month - 1 - months_ago, 12)
        start = date(year, month + 1, 1)
        asset = self._asset(acquisition_date=start, method_number=life, original_value=6000)
        asset.action_confirm()
        return asset

    def test_monthly_schedule_without_prorata(self):
        asset = self._asset()
        asset.action_confirm()
        moves = asset.depreciation_move_ids.sorted('date')
        self.assertEqual(asset.state, 'running')
        self.assertEqual(len(moves), 12)
        self.assertEqual(set(moves.mapped('asset_depreciation_amount')), {1000.0})
        self.assertEqual(set(moves.mapped('state')), {'draft'})
        self.assertEqual(moves[0].date, date(2025, 1, 31))
        self.assertEqual(moves[1].date, date(2025, 2, 28))
        self.assertEqual(moves[-1].date, date(2025, 12, 31))
        self.assertEqual(moves[-1].asset_remaining_value, 0.0)
        line = moves[0].line_ids.filtered(lambda l: l.account_id == self.account_expense)
        self.assertEqual(line.debit, 1000.0)
        self.assertEqual(moves[0].ref, 'Test Asset: 1/12')

    def test_prorata_schedule(self):
        asset = self._asset(original_value=10000, salvage_value=1000, method_number=3,
                            acquisition_date=date(2025, 1, 16), prorata=True)
        asset.action_confirm()
        moves = asset.depreciation_move_ids.sorted('date')
        self.assertEqual(len(moves), 4)
        self.assertAlmostEqual(moves[0].asset_depreciation_amount, 1548.39)
        self.assertAlmostEqual(sum(moves.mapped('asset_depreciation_amount')), 9000.0)
        self.assertEqual(moves[-1].date, date(2025, 4, 30))
        self.assertAlmostEqual(moves[-1].asset_remaining_value, 1000.0)

    def test_rounding_and_base(self):
        asset = self._asset(original_value=1000, method_number=3)
        asset.action_confirm()
        amounts = asset.depreciation_move_ids.sorted('date').mapped('asset_depreciation_amount')
        self.assertEqual(len(amounts), 3)
        for amount, expected in zip(amounts, [333.33, 333.33, 333.34]):
            self.assertEqual(asset.currency_id.compare_amounts(amount, expected), 0)
        opening = self._asset(original_value=1000, already_depreciated=400, method_number=6)
        self.assertEqual(opening.depreciable_base, 600.0)
        self.assertEqual(opening.book_value, 600.0)
        opening.action_confirm()
        self.assertAlmostEqual(opening.depreciation_move_ids.sorted('date')[-1].asset_remaining_value, 0.0)

    def test_asset_from_vendor_bill(self):
        vendor = self.env['res.partner'].create({'name': 'Test Vendor'})
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': vendor.id, 'journal_id': self.bill_journal.id,
            'invoice_date': date(2025, 3, 10),
            'invoice_line_ids': [
                Command.create({'name': 'Forklift', 'quantity': 1, 'price_unit': 5000,
                                'account_id': self.account_asset.id, 'tax_ids': [Command.clear()]}),
                Command.create({'name': 'Office supplies', 'quantity': 1, 'price_unit': 200,
                                'account_id': self.account_other.id, 'tax_ids': [Command.clear()]}),
            ],
        })
        bill.action_post()
        assets = self.env['ydod.asset'].search([('invoice_id', '=', bill.id)])
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets.state, 'running')
        self.assertEqual(assets.name, 'Forklift')
        self.assertEqual(assets.partner_id, vendor)
        self.assertEqual(assets.original_value, 5000.0)
        self.assertEqual(assets.acquisition_date, date(2025, 3, 10))
        self.assertEqual(assets.category_id, self.category)
        self.assertEqual(bill.source_asset_count, 1)
        with self.assertRaises(UserError):
            bill.button_draft()

    def test_cron_posts_due_entries_and_closes(self):
        asset = self._recent_asset()
        due = asset.depreciation_move_ids.filtered(lambda m: m.date <= self.today)
        self.assertTrue(due)
        self.env['ydod.asset']._cron_post_depreciation()
        self.assertEqual(set(due.mapped('state')), {'posted'})
        self.assertEqual(set((asset.depreciation_move_ids - due).mapped('state')), {'draft'})
        self.assertEqual(asset.depreciated_value, sum(due.mapped('asset_depreciation_amount')))
        self.assertEqual(asset.state, 'running')
        finished = self._recent_asset(months_ago=6, life=2)
        self.env['ydod.asset']._cron_post_depreciation()
        self.assertEqual(finished.state, 'closed')
        self.assertEqual(finished.book_value, 0.0)

    def test_cron_skips_locked_period(self):
        asset = self._recent_asset()
        moves = asset.depreciation_move_ids.sorted('date')
        # Bypass the 17.0 check that refuses to lock a period holding draft entries
        self.env.cr.execute("UPDATE res_company SET fiscalyear_lock_date = %s WHERE id = %s",
                            (moves[0].date, self.company.id))
        self.company.invalidate_recordset(['fiscalyear_lock_date'])
        self.env['ydod.asset']._cron_post_depreciation()
        self.assertEqual(moves[0].state, 'draft')
        self.assertEqual(moves[1].state, 'posted')
        self.assertTrue(any('locked' in (message.body or '') for message in asset.message_ids))

    def test_reset_to_draft_and_dispose(self):
        asset = self._recent_asset()
        self.env['ydod.asset']._cron_post_depreciation()
        posted = asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
        asset.action_reset_to_draft()
        self.assertEqual(asset.state, 'draft')
        self.assertEqual(asset.depreciation_move_ids, posted)
        asset.action_confirm()
        self.assertEqual(len(asset.depreciation_move_ids), 6)
        asset.write({'disposal_date': self.today + timedelta(days=1), 'disposal_account_id': self.account_loss.id})
        book_value = asset.book_value
        asset.action_dispose()
        move = asset.disposal_move_id
        self.assertEqual(asset.state, 'closed')
        self.assertEqual(move.state, 'posted')
        self.assertFalse(asset.depreciation_move_ids.filtered(lambda m: m.state == 'draft'))
        self.assertAlmostEqual(sum(move.line_ids.mapped('debit')), sum(move.line_ids.mapped('credit')))
        loss_line = move.line_ids.filtered(lambda l: l.account_id == self.account_loss)
        self.assertAlmostEqual(loss_line.debit, book_value)
        asset_line = move.line_ids.filtered(lambda l: l.account_id == self.account_asset)
        self.assertAlmostEqual(asset_line.credit, 6000.0)

    def test_dispose_requires_account(self):
        asset = self._recent_asset()
        with self.assertRaises(UserError):
            asset.action_dispose()
        with self.assertRaises(UserError):
            asset.unlink()

    def test_constraints(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception) as salvage_error:
            self._asset(original_value=1000, salvage_value=1500)
        self.assertIn('check constraint', str(salvage_error.exception))
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception) as life_error:
            self._asset(method_number=0)
        self.assertIn('check constraint', str(life_error.exception))
        with self.assertRaises(ValidationError):
            self._asset(acquisition_date=date(2025, 5, 1), first_depreciation_date=date(2025, 4, 1))

    def test_access_rights(self):
        asset = self._asset()
        company_ids = [Command.set(self.company.ids)]
        user = new_test_user(self.env, login='ydod_asset_user', groups='base.group_user,account.group_account_user',
                             company_id=self.company.id, company_ids=company_ids)
        manager = new_test_user(self.env, login='ydod_asset_manager',
                                groups='base.group_user,account.group_account_manager',
                                company_id=self.company.id, company_ids=company_ids)
        self.assertEqual(asset.with_user(user).name, 'Test Asset')
        with self.assertRaises(AccessError):
            self.env['ydod.asset'].with_user(user).create({
                'name': 'Denied', 'category_id': self.category.id, 'original_value': 100})
        with self.assertRaises(AccessError):
            asset.with_user(user).write({'name': 'Denied'})
        with self.assertRaises(AccessError):
            asset.with_user(user).action_confirm()
        managed = self.env['ydod.asset'].with_user(manager).create({
            'name': 'Managed', 'category_id': self.category.id, 'original_value': 1200,
            'acquisition_date': date(2025, 1, 1)})
        managed.write({'salvage_value': 200})
        managed.action_confirm()
        self.assertEqual(managed.state, 'running')
        managed.action_reset_to_draft()
        managed.unlink()
        other_company = self.env['res.company'].create({'name': 'Other Asset Company'})
        outsider = new_test_user(self.env, login='ydod_asset_outsider',
                                 groups='base.group_user,account.group_account_user',
                                 company_id=other_company.id, company_ids=[Command.set(other_company.ids)])
        with self.assertRaises(AccessError):
            asset.with_user(outsider).read(['name'])
