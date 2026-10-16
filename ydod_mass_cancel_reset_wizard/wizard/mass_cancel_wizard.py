# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class MassCancelWizard(models.TransientModel):
    _name = 'ydod.mass.cancel.wizard'
    _description = 'Mass Document Cancel & Reset Wizard'

    reason = fields.Text(string='Cancellation Reason', required=True)
    operation_type = fields.Selection([
        ('cancel', 'Cancel Documents'),
        ('reset', 'Reset to Draft')
    ], string='Operation Type', required=True, default='cancel')
    model_name = fields.Char(string='Target Model', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group('ydod_mass_cancel_reset_wizard.group_mass_cancel_manager'):
            raise UserError(_("You are not authorized to perform mass cancel and reset operations."))

        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise UserError(_("No records selected for this operation."))

        records = self.env[self.model_name].browse(active_ids)
        
        if self.operation_type == 'cancel':
            for rec in records:
                if hasattr(rec, 'message_post'):
                    rec.message_post(
                        body=_("<b>Document Cancelled via Mass Action.</b><br/><b>Reason:</b> %s") % self.reason
                    )
                
                if self.model_name == 'sale.order':
                    if rec.state in ('sale', 'done'):
                        rec.action_cancel()
                elif self.model_name == 'purchase.order':
                    if rec.state in ('purchase', 'done'):
                        rec.button_cancel()
                elif self.model_name == 'account.move':
                    if rec.state == 'posted':
                        rec.button_cancel()
                elif self.model_name == 'stock.picking':
                    if rec.state not in ('done', 'cancel'):
                        rec.action_cancel()
                        
        elif self.operation_type == 'reset':
            for rec in records:
                if hasattr(rec, 'message_post'):
                    rec.message_post(
                        body=_("<b>Document Reset to Draft via Mass Action.</b><br/><b>Reason / Note:</b> %s") % self.reason
                    )
                
                if self.model_name == 'sale.order':
                    if rec.state == 'cancel':
                        rec.action_draft()
                elif self.model_name == 'purchase.order':
                    if rec.state == 'cancel':
                        try:
                            rec.button_draft()
                        except Exception:
                            pass
                elif self.model_name == 'account.move':
                    if rec.state == 'cancel':
                        rec.button_draft()
                elif self.model_name == 'stock.picking':
                    if rec.state == 'cancel':
                        if hasattr(rec, 'action_to_draft'):
                            rec.action_to_draft()

        return {'type': 'ir.actions.act_window_close'}
