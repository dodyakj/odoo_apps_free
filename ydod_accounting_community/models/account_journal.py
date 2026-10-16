# -*- coding: utf-8 -*-
from odoo import models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def action_open_bank_reconcile_audit(self):
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        return {
            'name': self.env._("Bank Reconciliation Statement - %s", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.reconcile.statement',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_journal_id': self.id,
                'default_company_id': self.company_id.id,
                'default_currency_id': currency.id if currency else False,
            },
        }
