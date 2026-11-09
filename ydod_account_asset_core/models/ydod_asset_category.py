from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class YdodAssetCategory(models.Model):
    _name = 'ydod.asset.category'
    _description = 'Asset Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    account_asset_id = fields.Many2one(
        'account.account', string='Fixed Asset Account', required=True, check_company=True,
        help="Vendor bill lines booked on this account can create assets automatically.")
    account_depreciation_id = fields.Many2one(
        'account.account', string='Accumulated Depreciation Account', required=True, check_company=True)
    account_expense_id = fields.Many2one(
        'account.account', string='Depreciation Expense Account', required=True, check_company=True)
    journal_id = fields.Many2one(
        'account.journal', string='Depreciation Journal', required=True, check_company=True,
        domain="[('type', '=', 'general')]")
    method_number = fields.Integer(string='Useful Life', required=True, default=60,
                                   help="Number of depreciation periods.")
    method_period = fields.Selection(
        [('month', 'Months'), ('year', 'Years')], string='Period', required=True, default='month')
    prorata = fields.Boolean(string='Prorata Temporis', default=True,
                             help="Depreciate the first period by the number of remaining days.")
    auto_create = fields.Boolean(string='Create from Vendor Bills',
                                 help="Create an asset for each posted vendor bill line on the fixed asset account.")
    auto_confirm = fields.Boolean(string='Confirm Automatically',
                                  help="Assets created from vendor bills are confirmed straight away.")
    asset_count = fields.Integer(compute='_compute_asset_count', string='Assets')

    _sql_constraints = [
        ('check_method_number', 'CHECK(method_number > 0)', 'Useful life must be positive.'),
        ('unique_asset_account', 'UNIQUE(company_id, account_asset_id)',
         'Only one asset category can use a given fixed asset account per company.'),
    ]

    @api.depends()
    def _compute_asset_count(self):
        groups = self.env['ydod.asset']._read_group(
            [('category_id', 'in', self.ids)], ['category_id'], ['__count'])
        counts = {category.id: count for category, count in groups}
        for category in self:
            category.asset_count = counts.get(category.id, 0)

    @api.constrains('company_id', 'account_asset_id', 'account_depreciation_id', 'account_expense_id', 'journal_id')
    def _check_company_consistency(self):
        for category in self:
            accounts = category.account_asset_id | category.account_depreciation_id | category.account_expense_id
            if any(account.company_id != category.company_id for account in accounts) \
                    or category.journal_id.company_id != category.company_id:
                raise ValidationError(_(
                    "The accounts and journal of category %s must belong to its company.", category.name))

    def action_view_assets(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('ydod_account_asset_core.action_ydod_asset')
        action['domain'] = [('category_id', '=', self.id)]
        action['context'] = {'default_category_id': self.id}
        return action
