# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    _date_acc_comp_idx = models.Index("(date, account_id, company_id)")

    def action_manual_reconcile(self):
        """Reconcile selected lines together, verifying balance."""
        if not self:
            return False
        unrec_lines = self.filtered(lambda l: not l.reconciled)
        if not unrec_lines:
            raise UserError(self.env._("Selected entries are already reconciled."))
        return unrec_lines.reconcile()
