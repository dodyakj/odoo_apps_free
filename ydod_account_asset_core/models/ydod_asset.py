import calendar
from datetime import date, timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_date


class YdodAsset(models.Model):
    _name = 'ydod.asset'
    _description = 'Fixed Asset'
    _inherit = ['mail.thread']
    _order = 'acquisition_date desc, id desc'

    name = fields.Char(required=True, tracking=True)
    category_id = fields.Many2one('ydod.asset.category', string='Category', required=True, tracking=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True, compute='_compute_company_id',
        store=True, readonly=False, precompute=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    state = fields.Selection(
        [('draft', 'Draft'), ('running', 'Running'), ('closed', 'Closed')],
        string='Status', required=True, default='draft', readonly=True, copy=False, tracking=True)
    original_value = fields.Monetary(string='Original Value', required=True, tracking=True, group_operator='sum')
    salvage_value = fields.Monetary(string='Salvage Value', default=0.0, tracking=True)
    already_depreciated = fields.Monetary(
        string='Already Depreciated', default=0.0,
        help="Depreciation booked before go-live. No journal entry is created for this amount.")
    acquisition_date = fields.Date(required=True, default=fields.Date.context_today)
    first_depreciation_date = fields.Date(
        required=True, compute='_compute_first_depreciation_date', store=True, readonly=False, precompute=True)
    method_number = fields.Integer(
        string='Useful Life', required=True, compute='_compute_method_number', store=True, readonly=False,
        precompute=True, help="Number of periods still to depreciate.")
    method_period = fields.Selection(
        [('month', 'Months'), ('year', 'Years')], string='Period', required=True,
        compute='_compute_method_period', store=True, readonly=False, precompute=True)
    prorata = fields.Boolean(string='Prorata Temporis', compute='_compute_prorata', store=True,
                             readonly=False, precompute=True)
    partner_id = fields.Many2one('res.partner', string='Vendor')
    invoice_id = fields.Many2one('account.move', string='Source Bill', readonly=True, index=True,
                                 copy=False, ondelete='set null')
    invoice_line_id = fields.Many2one('account.move.line', string='Source Bill Line', readonly=True,
                                      copy=False, ondelete='set null')
    depreciation_move_ids = fields.One2many('account.move', 'asset_id', string='Depreciation Entries',
                                            readonly=True, copy=False)
    disposal_move_id = fields.Many2one('account.move', string='Disposal Entry', readonly=True, copy=False)
    disposal_date = fields.Date(copy=False)
    disposal_account_id = fields.Many2one(
        'account.account', string='Disposal Account', copy=False, check_company=True,
        help="Account debited with the remaining book value (loss on disposal).")
    depreciable_base = fields.Monetary(compute='_compute_depreciable_base', store=True)
    depreciated_value = fields.Monetary(string='Accumulated Depreciation', compute='_compute_depreciated_value',
                                        store=True, group_operator='sum')
    book_value = fields.Monetary(string='Net Book Value', compute='_compute_book_value', store=True,
                                 group_operator='sum')
    move_count = fields.Integer(compute='_compute_move_count', string='Journal Entries')

    _sql_constraints = [
        ('check_original_value', 'CHECK(original_value > 0)', 'Original value must be positive.'),
        ('check_values',
         'CHECK(salvage_value >= 0 AND already_depreciated >= 0 '
         'AND salvage_value + already_depreciated <= original_value)',
         'Salvage value and already depreciated amount must be positive and not exceed the original value.'),
        ('check_method_number', 'CHECK(method_number > 0)', 'Useful life must be positive.'),
    ]

    @api.depends('category_id')
    def _compute_company_id(self):
        for asset in self:
            asset.company_id = asset.category_id.company_id or asset.company_id or self.env.company

    @api.depends('acquisition_date')
    def _compute_first_depreciation_date(self):
        for asset in self:
            asset.first_depreciation_date = asset.acquisition_date

    # One compute per field: precompute skips a shared method when some of its fields are in vals
    @api.depends('category_id')
    def _compute_method_number(self):
        for asset in self:
            asset.method_number = asset.category_id.method_number or asset.method_number or 1

    @api.depends('category_id')
    def _compute_method_period(self):
        for asset in self:
            asset.method_period = asset.category_id.method_period or asset.method_period or 'month'

    @api.depends('category_id')
    def _compute_prorata(self):
        for asset in self:
            asset.prorata = asset.category_id.prorata

    @api.depends('original_value', 'salvage_value', 'already_depreciated')
    def _compute_depreciable_base(self):
        for asset in self:
            asset.depreciable_base = asset.original_value - asset.salvage_value - asset.already_depreciated

    @api.depends('already_depreciated', 'depreciation_move_ids.state', 'depreciation_move_ids.asset_depreciation_amount')
    def _compute_depreciated_value(self):
        for asset in self:
            posted = asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
            asset.depreciated_value = asset.already_depreciated + sum(posted.mapped('asset_depreciation_amount'))

    @api.depends('original_value', 'depreciated_value')
    def _compute_book_value(self):
        for asset in self:
            asset.book_value = asset.original_value - asset.depreciated_value

    @api.depends('depreciation_move_ids', 'disposal_move_id')
    def _compute_move_count(self):
        for asset in self:
            asset.move_count = len(asset.depreciation_move_ids) + len(asset.disposal_move_id)

    @api.constrains('first_depreciation_date', 'acquisition_date', 'category_id', 'company_id')
    def _check_dates_company(self):
        for asset in self:
            if asset.first_depreciation_date < asset.acquisition_date:
                raise ValidationError(_("The first depreciation date cannot be before the acquisition date."))
            if asset.category_id.company_id != asset.company_id:
                raise ValidationError(_("The asset and its category must belong to the same company."))

    def unlink(self):
        if any(a.state != 'draft' or a.depreciation_move_ids.filtered(lambda m: m.state == 'posted') for a in self):
            raise UserError(_("Only draft assets without posted depreciation entries can be deleted."))
        self._unlink_draft_moves()
        return super().unlink()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group('account.group_account_manager'):
            raise AccessError(_("Only accounting administrators can manage assets."))

    def _unlink_draft_moves(self):
        drafts = self.depreciation_move_ids.filtered(lambda m: m.state == 'draft')
        drafts.with_context(ydod_asset_unlink=True, force_delete=True).unlink()

    def _period_end(self, day):
        if self.method_period == 'year':
            return date(day.year, 12, 31)
        return date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])

    def _round(self, amount):
        """Round to the currency precision without float artefacts (333.34, not 333.34000000000003)."""
        self.ensure_one()
        return round(self.currency_id.round(amount), self.currency_id.decimal_places)

    def _get_schedule(self):
        """Return the remaining straight-line schedule as a list of (date, amount)."""
        self.ensure_one()
        posted = self.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
        residual = self.currency_id.round(self.depreciable_base - sum(posted.mapped('asset_depreciation_amount')))
        if self.currency_id.compare_amounts(residual, 0) <= 0:
            return []
        if posted:
            start = max(posted.mapped('date')) + timedelta(days=1)
            periods, prorata = max(self.method_number - len(posted), 1), False
        else:
            start, periods, prorata = self.first_depreciation_date, self.method_number, self.prorata
        per_period = residual / periods
        period_end = self._period_end(start)
        factor = 1.0
        if prorata:
            period_start = date(start.year, 1, 1) if self.method_period == 'year' else start.replace(day=1)
            factor = ((period_end - start).days + 1) / ((period_end - period_start).days + 1)
        amounts = [per_period * factor] + [per_period] * (periods - 1)
        if factor < 1:
            amounts.append(per_period * (1 - factor))
        rounded = [self._round(amount) for amount in amounts[:-1]]
        rounded.append(self._round(residual - sum(rounded)))
        schedule = []
        for amount in rounded:
            schedule.append((period_end, amount))
            period_end = self._period_end(period_end + timedelta(days=1))
        return schedule

    def _prepare_depreciation_moves(self):
        self.ensure_one()
        posted = self.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
        schedule = self._get_schedule()
        total = len(posted) + len(schedule)
        cumulative = self.already_depreciated + sum(posted.mapped('asset_depreciation_amount'))
        category = self.category_id
        vals_list = []
        for index, (move_date, amount) in enumerate(schedule, start=len(posted) + 1):
            cumulative = self._round(cumulative + amount)
            label = _("%(asset)s: %(index)s/%(total)s", asset=self.name, index=index, total=total)
            vals_list.append({
                'move_type': 'entry',
                'journal_id': category.journal_id.id,
                'date': move_date,
                'ref': label,
                'asset_id': self.id,
                'asset_depreciation_amount': amount,
                'asset_cumulative_depreciation': cumulative,
                'asset_remaining_value': self._round(self.original_value - cumulative),
                'line_ids': [
                    Command.create({'name': label, 'account_id': category.account_expense_id.id,
                                    'debit': amount, 'credit': 0.0}),
                    Command.create({'name': label, 'account_id': category.account_depreciation_id.id,
                                    'debit': 0.0, 'credit': amount}),
                ],
            })
        return vals_list

    def _prepare_disposal_move(self):
        self.ensure_one()
        category = self.category_id
        label = _("%(asset)s: Disposal", asset=self.name)
        lines = [Command.create({'name': label, 'account_id': category.account_asset_id.id,
                                 'debit': 0.0, 'credit': self.original_value})]
        if not self.currency_id.is_zero(self.depreciated_value):
            lines.append(Command.create({'name': label, 'account_id': category.account_depreciation_id.id,
                                         'debit': self.depreciated_value, 'credit': 0.0}))
        if not self.currency_id.is_zero(self.book_value):
            lines.append(Command.create({'name': label, 'account_id': self.disposal_account_id.id,
                                         'debit': self.book_value, 'credit': 0.0}))
        return {'move_type': 'entry', 'journal_id': category.journal_id.id, 'date': self.disposal_date,
                'ref': label, 'line_ids': lines}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_confirm(self):
        self._check_manager()
        for asset in self:
            if asset.state == 'closed':
                raise UserError(_("Closed assets cannot be confirmed."))
            if asset.currency_id.compare_amounts(asset.depreciable_base, 0) <= 0:
                raise UserError(_("Asset %s has nothing to depreciate.", asset.name))
        self._unlink_draft_moves()
        vals_list = [vals for asset in self for vals in asset._prepare_depreciation_moves()]
        self.env['account.move'].create(vals_list)
        self.write({'state': 'running'})
        return True

    def action_reset_to_draft(self):
        self._check_manager()
        if any(asset.state != 'running' for asset in self):
            raise UserError(_("Only running assets can be reset to draft."))
        self._unlink_draft_moves()
        self.write({'state': 'draft'})
        return True

    def action_dispose(self):
        self._check_manager()
        for asset in self:
            if asset.state != 'running':
                raise UserError(_("Only running assets can be disposed."))
            if not asset.disposal_date or not asset.disposal_account_id:
                raise UserError(_("Set the disposal date and disposal account of %s first.", asset.name))
            posted_dates = asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted').mapped('date')
            if posted_dates and asset.disposal_date <= max(posted_dates):
                raise UserError(_(
                    "The disposal date must be after the last posted depreciation entry (%s).", max(posted_dates)))
        self._unlink_draft_moves()
        moves = self.env['account.move'].create([asset._prepare_disposal_move() for asset in self])
        moves._post(soft=False)
        for asset, move in zip(self, moves):
            asset.write({'disposal_move_id': move.id, 'state': 'closed'})
        return True

    def _action_open_moves(self, moves, name):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'views': [(self.env.ref('account.view_move_tree').id, 'tree'), (False, 'form')],
            'domain': [('id', 'in', moves.ids)],
            'context': {'create': False},
        }

    def action_view_moves(self):
        self.ensure_one()
        return self._action_open_moves(self.depreciation_move_ids | self.disposal_move_id, _("Journal Entries"))

    def action_view_schedule(self):
        self.ensure_one()
        action = self._action_open_moves(self.depreciation_move_ids, _("Depreciation Schedule"))
        action['views'] = [(self.env.ref('ydod_account_asset_core.view_move_list_asset_schedule').id, 'tree'),
                           (False, 'form')]
        return action

    # ------------------------------------------------------------------
    # Automation
    # ------------------------------------------------------------------
    @api.model
    def _create_from_bills(self, bills):
        lines = bills.invoice_line_ids.filtered(lambda l: l.display_type == 'product' and l.account_id)
        if not lines:
            return self.browse()
        categories = self.env['ydod.asset.category'].search([
            ('auto_create', '=', True),
            ('account_asset_id', 'in', lines.account_id.ids),
            ('company_id', 'in', bills.company_id.ids),
        ])
        mapping = {(c.company_id.id, c.account_asset_id.id): c for c in categories}
        vals_list = []
        for line in lines:
            category = mapping.get((line.company_id.id, line.account_id.id))
            if not category or line.company_currency_id.is_zero(line.balance):
                continue
            move = line.move_id
            vals_list.append({
                'name': line.name or line.product_id.display_name or move.name,
                'category_id': category.id,
                'company_id': category.company_id.id,
                'original_value': abs(line.balance),
                'acquisition_date': move.invoice_date or move.date,
                'partner_id': move.partner_id.id,
                'invoice_id': move.id,
                'invoice_line_id': line.id,
            })
        assets = self.create(vals_list)
        assets.filtered(lambda a: a.category_id.auto_confirm).action_confirm()
        return assets

    @api.model
    def _cron_post_depreciation(self):
        today = fields.Date.context_today(self)
        moves = self.env['account.move'].search(
            [('asset_id', '!=', False), ('state', '=', 'draft'), ('date', '<=', today)], order='date, id')
        for move in moves:
            locks = move._get_violated_lock_dates(move.date, False)
            if locks:
                move.asset_id.message_post(body=_(
                    "Depreciation entry %(ref)s dated %(date)s was not posted because the period is locked (%(locks)s).",
                    ref=move.ref, date=format_date(self.env, move.date),
                    locks=', '.join('%s: %s' % (lock_type, format_date(self.env, lock_date))
                                    for lock_date, lock_type in locks)))
                continue
            try:
                with self.env.cr.savepoint():
                    move._post(soft=False)
            except UserError as error:
                move.asset_id.message_post(body=_(
                    "Depreciation entry %(ref)s could not be posted: %(error)s", ref=move.ref, error=error.args[0]))
        self.search([('state', '=', 'running')])._close_fully_depreciated()
        return True

    def _close_fully_depreciated(self):
        to_close = self.filtered(
            lambda a: not a.depreciation_move_ids.filtered(lambda m: m.state == 'draft')
            and a.currency_id.compare_amounts(a.book_value, a.salvage_value) == 0)
        to_close.write({'state': 'closed'})
        return to_close

    @api.model
    def _load_demo_data(self):
        company = self.env.company
        journal = self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
        bill_journal = self.env['account.journal'].search(
            [('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
        if not journal or self.env['ydod.asset.category'].with_context(active_test=False).search_count(
                [('company_id', '=', company.id)]):
            return
        Account = self.env['account.account'].with_company(company)

        def account(code, name, account_type):
            found = Account.search([('company_id', '=', company.id), ('code', '=', code)], limit=1)
            return found or Account.create({'code': code, 'name': name, 'account_type': account_type,
                                            'company_id': company.id})

        accumulated = account('171900', 'Accumulated Depreciation', 'asset_fixed')
        expense = Account.search([('company_id', '=', company.id), ('account_type', '=', 'expense_depreciation')],
                                 limit=1) or account('681100', 'Depreciation Expense', 'expense_depreciation')
        loss = account('681900', 'Loss on Asset Disposal', 'expense')
        Category = self.env['ydod.asset.category']
        common = {'company_id': company.id, 'account_depreciation_id': accumulated.id,
                  'account_expense_id': expense.id, 'journal_id': journal.id}
        office, vehicles, buildings, hardware = Category.create([
            dict(common, name='Office Equipment', account_asset_id=account('171100', 'Office Equipment', 'asset_fixed').id,
                 method_number=36, method_period='month', prorata=True, auto_create=True, auto_confirm=True),
            dict(common, name='Vehicles', account_asset_id=account('171200', 'Vehicles', 'asset_fixed').id,
                 method_number=5, method_period='year', prorata=False),
            dict(common, name='Buildings', account_asset_id=account('171300', 'Buildings', 'asset_fixed').id,
                 method_number=20, method_period='year', prorata=True),
            dict(common, name='Computer Hardware', account_asset_id=account('171400', 'Computer Hardware', 'asset_fixed').id,
                 method_number=48, method_period='month', prorata=True, auto_create=True),
        ])
        today = fields.Date.context_today(self)
        year_start = date(today.year, 1, 1)
        laptop, avanza, building, printer, furniture = self.create([
            {'name': 'Laptop Dell Latitude', 'category_id': office.id, 'original_value': 18000000,
             'acquisition_date': year_start},
            {'name': 'Toyota Avanza 1.5 G', 'category_id': vehicles.id, 'original_value': 285000000,
             'salvage_value': 35000000, 'already_depreciated': 50000000,
             'acquisition_date': date(today.year - 1, 1, 1), 'first_depreciation_date': year_start,
             'method_number': 4},
            {'name': 'Head Office Building Jakarta', 'category_id': buildings.id, 'original_value': 2400000000,
             'salvage_value': 400000000, 'acquisition_date': today.replace(day=1)},
            {'name': 'Epson L6270 Printer', 'category_id': office.id, 'original_value': 9500000,
             'acquisition_date': date(today.year - 2, 1, 1), 'method_number': 12},
            {'name': 'Meeting Room Furniture Set', 'category_id': office.id, 'original_value': 45000000,
             'salvage_value': 5000000, 'acquisition_date': date(today.year - 1, 7, 1),
             'disposal_account_id': loss.id},
        ])
        (laptop | avanza | printer | furniture).action_confirm()
        self._cron_post_depreciation()
        posted_dates = furniture.depreciation_move_ids.filtered(lambda m: m.state == 'posted').mapped('date')
        furniture.disposal_date = max(posted_dates + [today]) + timedelta(days=1)
        furniture.action_dispose()
        if bill_journal:
            vendor = self.env['res.partner'].create({'name': 'PT Mitra Komputer Nusantara', 'is_company': True})
            bill = self.env['account.move'].create({
                'move_type': 'in_invoice', 'partner_id': vendor.id, 'journal_id': bill_journal.id,
                'invoice_date': today.replace(day=1), 'ref': 'INV/MKN/0457',
                'invoice_line_ids': [
                    Command.create({'name': 'Dell PowerEdge R760 Server', 'quantity': 1, 'price_unit': 120000000,
                                    'account_id': hardware.account_asset_id.id, 'tax_ids': [Command.clear()]}),
                    Command.create({'name': 'HP LaserJet Pro M404dn', 'quantity': 1, 'price_unit': 7800000,
                                    'account_id': office.account_asset_id.id, 'tax_ids': [Command.clear()]}),
                ],
            })
            bill.action_post()
