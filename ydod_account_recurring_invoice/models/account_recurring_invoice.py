# -*- coding: utf-8 -*-
import calendar
from datetime import date, timedelta
from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError


class AccountRecurringInvoice(models.Model):
    _name = 'account.recurring.invoice'
    _description = 'Recurring Invoice Schedule'
    _order = 'date_next_execution desc, id desc'

    _sql_constraints = [
        ('check_interval', 'CHECK(recurring_interval > 0)', 'The recurrence interval must be strictly greater than zero.'),
        ('check_cycle_limit', 'CHECK(cycle_limit >= 0)', 'The cycle limit cannot be negative.'),
    ]

    name = fields.Char(string='Schedule Title', required=True, copy=True)
    code = fields.Char(string='Reference', required=True, copy=False, default='/', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', required=True, copy=False, index=True)
    move_type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Vendor Bill'),
    ], string='Invoice Type', default='out_invoice', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id', store=True, readonly=False, precompute=True)
    journal_id = fields.Many2one('account.journal', string='Journal')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms')

    recurring_interval = fields.Integer(string='Repeat Every', default=1, required=True)
    recurring_rule_type = fields.Selection([
        ('daily', 'Days'),
        ('weekly', 'Weeks'),
        ('monthly', 'Months'),
        ('quarterly', 'Quarters'),
        ('yearly', 'Years'),
    ], string='Recurrence Unit', default='monthly', required=True)
    date_start = fields.Date(string='Start Date', default=fields.Date.context_today, required=True)
    date_next_execution = fields.Date(string='Next Execution Date', default=fields.Date.context_today, required=True, index=True)

    end_type = fields.Selection([
        ('forever', 'No End Date (Continuous)'),
        ('until_date', 'End Date'),
        ('cycle_limit', 'Fixed Cycle Limit'),
    ], string='Recurrence End', default='forever', required=True)
    date_end = fields.Date(string='End Date')
    cycle_limit = fields.Integer(string='Cycle Limit', default=12)
    cycle_count = fields.Integer(string='Cycles Completed', compute='_compute_invoice_stats', store=True)

    auto_post = fields.Boolean(string='Auto-Post Invoices', default=False, help='If enabled, generated invoices will be automatically confirmed and posted.')
    send_email = fields.Boolean(string='Auto-Send Email', default=False, help='If enabled, posted invoices will be automatically emailed to the partner.')

    line_ids = fields.One2many('account.recurring.invoice.line', 'recurring_id', string='Invoice Lines', copy=True)
    invoice_ids = fields.One2many('account.move', 'recurring_id', string='Generated Invoices', readonly=True)
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_stats', store=True)
    total_billed_amount = fields.Monetary(string='Total Billed', compute='_compute_invoice_stats', currency_field='currency_id', store=True)
    amount_total = fields.Monetary(string='Recurring Amount', compute='_compute_amount', currency_field='currency_id', store=True)
    description = fields.Text(string='Internal Notes')

    @api.depends('company_id', 'partner_id')
    def _compute_currency_id(self):
        for rec in self:
            if rec.partner_id and rec.partner_id.currency_id:
                rec.currency_id = rec.partner_id.currency_id
            elif rec.company_id:
                rec.currency_id = rec.company_id.currency_id
            else:
                rec.currency_id = self.env.company.currency_id

    @api.depends('line_ids.price_subtotal')
    def _compute_amount(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('price_subtotal'))

    @api.depends('invoice_ids', 'invoice_ids.state', 'invoice_ids.amount_total')
    def _compute_invoice_stats(self):
        for rec in self:
            valid_invoices = rec.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
            rec.invoice_count = len(valid_invoices)
            rec.cycle_count = len(valid_invoices)
            rec.total_billed_amount = sum(valid_invoices.mapped('amount_total'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', '/') == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code('account.recurring.invoice') or '/'
        return super().create(vals_list)

    def _get_next_date(self, current_date):
        self.ensure_one()
        interval = self.recurring_interval or 1
        rule_type = self.recurring_rule_type
        if rule_type == 'daily':
            return current_date + timedelta(days=interval)
        elif rule_type == 'weekly':
            return current_date + timedelta(weeks=interval)
        elif rule_type == 'monthly':
            month = current_date.month - 1 + interval
            year = current_date.year + month // 12
            month = month % 12 + 1
            day = min(current_date.day, calendar.monthrange(year, month)[1])
            return date(year, month, day)
        elif rule_type == 'quarterly':
            month = current_date.month - 1 + (interval * 3)
            year = current_date.year + month // 12
            month = month % 12 + 1
            day = min(current_date.day, calendar.monthrange(year, month)[1])
            return date(year, month, day)
        elif rule_type == 'yearly':
            year = current_date.year + interval
            day = min(current_date.day, calendar.monthrange(year, current_date.month)[1])
            return date(year, current_date.month, day)
        return current_date

    def action_start(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Please add at least one line before starting the schedule."))
            rec.state = 'running'

    def action_pause(self):
        self.write({'state': 'paused'})

    def action_resume(self):
        self.write({'state': 'running'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def _generate_invoice(self, execution_date=None):
        self.ensure_one()
        if self.state != 'running' or not self.line_ids:
            return False

        inv_date = execution_date or self.date_next_execution or fields.Date.context_today(self)
        if self.end_type == 'until_date' and self.date_end and inv_date > self.date_end:
            self.state = 'closed'
            return False
        if self.end_type == 'cycle_limit' and self.cycle_limit > 0 and self.cycle_count >= self.cycle_limit:
            self.state = 'closed'
            return False

        invoice_lines = []
        for line in self.line_ids:
            line_vals = {
                'name': line.name or (line.product_id.display_name if line.product_id else '/'),
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
            }
            if line.product_id:
                line_vals['product_id'] = line.product_id.id
            if line.tax_ids:
                line_vals['tax_ids'] = [Command.set(line.tax_ids.ids)]
            invoice_lines.append(Command.create(line_vals))

        move_vals = {
            'move_type': self.move_type,
            'partner_id': self.partner_id.id,
            'invoice_date': inv_date,
            'date': inv_date,
            'company_id': self.company_id.id,
            'recurring_id': self.id,
            'invoice_line_ids': invoice_lines,
        }
        if self.currency_id:
            move_vals['currency_id'] = self.currency_id.id
        if self.journal_id:
            move_vals['journal_id'] = self.journal_id.id
        if self.payment_term_id:
            move_vals['invoice_payment_term_id'] = self.payment_term_id.id

        new_invoice = self.env['account.move'].create(move_vals)

        if self.auto_post:
            try:
                new_invoice.action_post()
                if self.send_email and new_invoice.state == 'posted':
                    try:
                        template_ref = new_invoice._get_mail_template()
                        template = self.env.ref(template_ref, raise_if_not_found=False) if isinstance(template_ref, str) else template_ref
                        if template:
                            template.send_mail(new_invoice.id, force_send=True)
                    except Exception:
                        pass
            except Exception:
                pass

        next_date = self._get_next_date(inv_date)
        write_vals = {'date_next_execution': next_date}
        if self.end_type == 'until_date' and self.date_end and next_date > self.date_end:
            write_vals['state'] = 'closed'
        elif self.end_type == 'cycle_limit' and self.cycle_limit > 0 and (self.cycle_count + 1) >= self.cycle_limit:
            write_vals['state'] = 'closed'
        self.write(write_vals)

        return new_invoice

    def action_generate_invoice(self):
        invoices = self.env['account.move']
        for rec in self:
            inv = rec._generate_invoice()
            if inv:
                invoices |= inv
        if len(invoices) == 1:
            return {
                'name': _('Generated Invoice'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': invoices.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif invoices:
            return {
                'name': _('Generated Invoices'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'domain': [('id', 'in', invoices.ids)],
                'view_mode': 'tree,form',
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window_close'}

    def action_view_invoices(self):
        self.ensure_one()
        action = {
            'name': _('Generated Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('recurring_id', '=', self.id)],
            'context': {'default_move_type': self.move_type, 'default_recurring_id': self.id},
        }
        if self.invoice_count == 1:
            inv = self.invoice_ids.filtered(lambda i: i.state != 'cancel')[:1] or self.invoice_ids[:1]
            if inv:
                action['res_id'] = inv.id
                action['view_mode'] = 'form'
        return action

    @api.model
    def _cron_generate_recurring_invoices(self):
        today = fields.Date.context_today(self)
        running_schedules = self.search([
            ('state', '=', 'running'),
            ('date_next_execution', '<=', today),
        ])
        for schedule in running_schedules:
            try:
                schedule._generate_invoice()
            except Exception:
                pass


class AccountRecurringInvoiceLine(models.Model):
    _name = 'account.recurring.invoice.line'
    _description = 'Recurring Invoice Schedule Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    recurring_id = fields.Many2one('account.recurring.invoice', string='Recurring Schedule', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Company', related='recurring_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='recurring_id.currency_id')
    product_id = fields.Many2one('product.product', string='Product')
    name = fields.Text(string='Description', required=True, compute='_compute_name', store=True, readonly=False, precompute=True)
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    price_unit = fields.Float(string='Unit Price', default=0.0, required=True, compute='_compute_price_unit', store=True, readonly=False, precompute=True)
    discount = fields.Float(string='Discount (%)', default=0.0)
    tax_ids = fields.Many2many('account.tax', string='Taxes', compute='_compute_tax_ids', store=True, readonly=False, precompute=True)
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_price_subtotal', store=True, currency_field='currency_id')

    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            if line.product_id and not line.name:
                line.name = line.product_id.display_name or line.product_id.name

    @api.depends('product_id', 'recurring_id.move_type')
    def _compute_price_unit(self):
        for line in self:
            if line.product_id:
                move_type = line.recurring_id.move_type or 'out_invoice'
                line.price_unit = line.product_id.lst_price if move_type == 'out_invoice' else line.product_id.standard_price
            elif not line.price_unit:
                line.price_unit = 0.0

    @api.depends('product_id', 'recurring_id.move_type', 'recurring_id.company_id')
    def _compute_tax_ids(self):
        for line in self:
            if line.product_id:
                move_type = line.recurring_id.move_type or 'out_invoice'
                comp = line.recurring_id.company_id
                if move_type == 'out_invoice':
                    line.tax_ids = line.product_id.taxes_id.filtered(lambda t: t.company_id == comp)
                else:
                    line.tax_ids = line.product_id.supplier_taxes_id.filtered(lambda t: t.company_id == comp)
            elif not line.tax_ids:
                line.tax_ids = False

    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_price_subtotal(self):
        for line in self:
            discounted_price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.price_subtotal = line.quantity * discounted_price
