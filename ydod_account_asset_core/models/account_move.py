from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    asset_id = fields.Many2one('ydod.asset', string='Asset', readonly=True, index=True, copy=False,
                               ondelete='restrict')
    asset_depreciation_amount = fields.Monetary(string='Depreciation', readonly=True, copy=False,
                                                currency_field='company_currency_id')
    asset_cumulative_depreciation = fields.Monetary(string='Cumulative Depreciation', readonly=True, copy=False,
                                                    currency_field='company_currency_id')
    asset_remaining_value = fields.Monetary(string='Remaining Value', readonly=True, copy=False,
                                            currency_field='company_currency_id')
    source_asset_count = fields.Integer(compute='_compute_source_asset_count', string='Assets')

    @api.depends()
    def _compute_source_asset_count(self):
        groups = self.env['ydod.asset'].sudo()._read_group(
            [('invoice_id', 'in', self.ids)], ['invoice_id'], ['__count'])
        counts = {move.id: count for move, count in groups}
        for move in self:
            move.source_asset_count = counts.get(move.id, 0)

    def _post(self, soft=True):
        posted = super()._post(soft)
        bills = posted.filtered(lambda m: m.move_type == 'in_invoice' and m.state == 'posted')
        if bills:
            self.env['ydod.asset'].sudo()._create_from_bills(bills)
        return posted

    def button_draft(self):
        assets = self.env['ydod.asset'].sudo().search([('invoice_id', 'in', self.ids)])
        if assets.filtered(lambda a: a.state != 'draft'):
            raise UserError(_(
                "This bill created assets that are already running or closed. "
                "Reset or remove those assets before resetting the bill to draft."))
        res = super().button_draft()
        assets.unlink()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_asset_entry(self):
        if not self.env.context.get('ydod_asset_unlink') and any(move.asset_id for move in self):
            raise UserError(_(
                "Depreciation entries are managed from their asset: use Reset to Draft or Dispose on the asset."))

    def action_view_source_assets(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('ydod_account_asset_core.action_ydod_asset')
        action['domain'] = [('invoice_id', '=', self.id)]
        action['context'] = {'create': False}
        return action

    def action_open_asset(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ydod.asset',
            'res_id': self.asset_id.id,
            'view_mode': 'form',
        }
