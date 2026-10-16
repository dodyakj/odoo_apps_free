from odoo import models, api, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super().action_post()
        for move in self:
            if move.move_type == 'out_invoice' and move.partner_id:
                partner = move.partner_id
                if partner.credit_limit > 0.0:
                    current_credit = partner.credit + move.amount_residual
                    if current_credit > partner.credit_limit:
                        if partner.customer_risk_score == 'high':
                            raise UserError(
                                self.env._("Cannot post invoice! Customer '%s' has exceeded their credit limit (Credit: %.2f, Limit: %.2f) and is flagged as HIGH risk.")
                                % (partner.name, current_credit, partner.credit_limit)
                            )
        return res
