from odoo import api, fields, models, _, Command


class AccountMove(models.Model):
    _inherit = 'account.move'

    recurring_id = fields.Many2one(
        'account.recurring.invoice',
        string='Recurring Schedule',
        readonly=True,
        index=True,
        copy=False,
    )

    def action_create_recurring_schedule(self):
        self.ensure_one()
        if self.recurring_id:
            return self.action_view_recurring_schedule()

        lines = []
        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type or l.display_type == 'product'):
            lines.append(Command.create({
                'product_id': line.product_id.id if line.product_id else False,
                'name': line.name or (line.product_id.display_name if line.product_id else '/'),
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'tax_ids': [Command.set(line.tax_ids.ids)] if line.tax_ids else False,
            }))

        schedule_vals = {
            'name': _("Recurrence for %s") % (self.name or self.partner_id.name),
            'partner_id': self.partner_id.id,
            'move_type': self.move_type,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'journal_id': self.journal_id.id if self.journal_id else False,
            'payment_term_id': self.invoice_payment_term_id.id if self.invoice_payment_term_id else False,
            'date_start': fields.Date.context_today(self),
            'date_next_execution': fields.Date.context_today(self),
            'line_ids': lines,
        }
        schedule = self.env['account.recurring.invoice'].create(schedule_vals)
        self.recurring_id = schedule.id

        return {
            'name': _('Recurring Schedule'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.recurring.invoice',
            'res_id': schedule.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_recurring_schedule(self):
        self.ensure_one()
        if not self.recurring_id:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'name': _('Recurring Schedule'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.recurring.invoice',
            'res_id': self.recurring_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
