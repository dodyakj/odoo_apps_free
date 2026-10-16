from odoo import models, fields, api, _
from datetime import date

class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_risk_score = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ], string='Customer Risk Score', default='low', tracking=True, help='Assessed payment risk based on historical timeliness.')

    aging_current = fields.Monetary(string='Current', compute='_compute_invoice_aging', currency_field='currency_id')
    aging_1_30 = fields.Monetary(string='1-30 Days', compute='_compute_invoice_aging', currency_field='currency_id')
    aging_31_60 = fields.Monetary(string='31-60 Days', compute='_compute_invoice_aging', currency_field='currency_id')
    aging_61_90 = fields.Monetary(string='61-90 Days', compute='_compute_invoice_aging', currency_field='currency_id')
    aging_90_plus = fields.Monetary(string='90+ Days', compute='_compute_invoice_aging', currency_field='currency_id')
    total_overdue_amount = fields.Monetary(string='Total Overdue', compute='_compute_invoice_aging', currency_field='currency_id')

    @api.depends('invoice_ids.state', 'invoice_ids.amount_residual', 'invoice_ids.invoice_date_due')
    def _compute_invoice_aging(self):
        today = fields.Date.context_today(self)
        for partner in self:
            current = 0.0
            d1_30 = 0.0
            d31_60 = 0.0
            d61_90 = 0.0
            d90_plus = 0.0
            total_overdue = 0.0

            invoices = partner.invoice_ids.filtered(lambda inv: inv.move_type == 'out_invoice' and inv.state == 'posted' and inv.payment_state != 'paid')
            for inv in invoices:
                residual = inv.amount_residual
                due_date = inv.invoice_date_due or today
                delta_days = (today - due_date).days

                if delta_days <= 0:
                    current += residual
                elif delta_days <= 30:
                    d1_30 += residual
                    total_overdue += residual
                elif delta_days <= 60:
                    d31_60 += residual
                    total_overdue += residual
                elif delta_days <= 90:
                    d61_90 += residual
                    total_overdue += residual
                else:
                    d90_plus += residual
                    total_overdue += residual

            partner.aging_current = current
            partner.aging_1_30 = d1_30
            partner.aging_31_60 = d31_60
            partner.aging_61_90 = d61_90
            partner.aging_90_plus = d90_plus
            partner.total_overdue_amount = total_overdue

    @api.model
    def _cron_send_overdue_dunning_alerts(self):
        partners = self.search([('total_overdue_amount', '>', 0.0)])
        for partner in partners:
            sales_person = partner.user_id
            if sales_person and sales_person.email:
                body = self.env._(
                    "Hello %s,<br/><br/>This is an automated daily dunning alert. Customer <b>%s</b> currently has an overdue balance of <b>%.2f</b>.<br/>"
                    "Aging Breakdown:<br/>"
                    "- 1-30 Days: %.2f<br/>"
                    "- 31-60 Days: %.2f<br/>"
                    "- 61-90 Days: %.2f<br/>"
                    "- 90+ Days: %.2f<br/><br/>Please follow up with the customer promptly.<br/>Regards,<br/>Odoo Invoicing Engine"
                ) % (
                    sales_person.name,
                    partner.name,
                    partner.total_overdue_amount,
                    partner.aging_1_30,
                    partner.aging_31_60,
                    partner.aging_61_90,
                    partner.aging_90_plus
                )
                mail_values = {
                    'subject': self.env._("Overdue Aging Alert: %s") % partner.name,
                    'body_html': body,
                    'email_to': sales_person.email,
                    'email_from': self.env.company.email or 'noreply@example.com',
                }
                self.env['mail.mail'].sudo().create(mail_values).send()
        return True
