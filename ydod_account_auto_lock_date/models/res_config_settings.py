from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    auto_lock_enabled = fields.Boolean(
        related='company_id.auto_lock_enabled',
        readonly=False,
    )
    auto_lock_day = fields.Integer(
        related='company_id.auto_lock_day',
        readonly=False,
    )
    auto_lock_target = fields.Selection(
        related='company_id.auto_lock_target',
        readonly=False,
    )
    auto_lock_sale = fields.Boolean(
        related='company_id.auto_lock_sale',
        readonly=False,
    )
    auto_lock_purchase = fields.Boolean(
        related='company_id.auto_lock_purchase',
        readonly=False,
    )
    auto_lock_tax = fields.Boolean(
        related='company_id.auto_lock_tax',
        readonly=False,
    )
    auto_lock_fiscalyear = fields.Boolean(
        related='company_id.auto_lock_fiscalyear',
        readonly=False,
    )
    auto_lock_last_run = fields.Datetime(
        related='company_id.auto_lock_last_run',
        readonly=True,
    )

    def action_run_auto_lock(self):
        self.ensure_one()
        return self.company_id.action_run_auto_lock()

    def action_view_lock_audit_logs(self):
        self.ensure_one()
        return self.company_id.action_view_lock_audit_logs()

    def action_view_bypass_users(self):
        self.ensure_one()
        group = self.env.ref('ydod_account_auto_lock_date.group_account_lock_date_bypass', raise_if_not_found=False)
        return {
            'name': self.env._("Authorized Lock Bypass Users"),
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'domain': [('all_group_ids', 'in', [group.id])] if group else [],
            'context': {'default_group_ids': [(4, group.id)]} if group else {},
        }
