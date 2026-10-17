# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    retained_earnings_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Default Retained Earnings Account",
        help="Default equity account used for fiscal year closing profit & loss transfer.",
    )
