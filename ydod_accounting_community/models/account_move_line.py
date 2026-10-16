# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def action_manual_reconcile(self):
        """Reconcile selected lines together, verifying balance."""
        if not self:
            return False
        unrec_lines = self.filtered(lambda l: not l.reconciled)
        if not unrec_lines:
            raise UserError(_("Selected entries are already reconciled."))
        return unrec_lines.reconcile()
