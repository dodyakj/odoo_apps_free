# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class YdodFiscalYear(models.Model):
    _name = 'ydod.fiscal.year'
    _description = "Fiscal Year"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    _check_dates = models.Constraint(
        'CHECK(date_from <= date_to)',
        'Fiscal year start date must precede end date.',
    )
    _code_company_uniq = models.Constraint(
        'UNIQUE(code, company_id)',
        'Fiscal year code must be unique per company.',
    )
    _company_dates_idx = models.Index("(company_id, date_from, date_to)")

    name = fields.Char(string="Fiscal Year", required=True, tracking=True)
    code = fields.Char(string="Code", required=True, tracking=True)
    date_from = fields.Date(string="Start Date", required=True, tracking=True)
    date_to = fields.Date(string="End Date", required=True, tracking=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('open', 'Open'),
            ('closed', 'Closed'),
        ],
        string="Status",
        required=True,
        default='draft',
        tracking=True,
    )
    closing_move_id = fields.Many2one(
        comodel_name='account.move',
        string="Closing Entry",
        readonly=True,
        copy=False,
    )
    move_count = fields.Integer(
        string="Moves Count",
        compute='_compute_move_count',
        readonly=True,
    )

    @api.constrains('date_from', 'date_to')
    def _check_fiscal_year_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError(self.env._("Fiscal year start date must precede end date."))

    @api.constrains('code', 'company_id')
    def _check_code_unique(self):
        for company in self.company_id:
            fys = self.filtered(lambda r: r.company_id == company)
            codes = [c for c in fys.mapped('code') if c]
            if len(codes) != len(set(codes)):
                raise ValidationError(self.env._("Fiscal year code must be unique per company."))
            domain = [
                ('company_id', '=', company.id),
                ('code', 'in', codes),
                ('id', 'not in', fys.ids),
            ]
            if self.search_count(domain):
                raise ValidationError(self.env._("Fiscal year code must be unique per company."))

    @api.depends('date_from', 'date_to', 'company_id')
    def _compute_move_count(self):
        for fy in self:
            if not fy.date_from or not fy.date_to or not fy.company_id:
                fy.move_count = 0
                continue
            groups = self.env['account.move']._read_group(
                domain=[
                    ('company_id', '=', fy.company_id.id),
                    ('date', '>=', fy.date_from),
                    ('date', '<=', fy.date_to),
                    ('state', '=', 'posted'),
                ],
                aggregates=['__count'],
            )
            fy.move_count = groups[0][0] if groups else 0

    def write(self, vals):
        if any(f in vals for f in ('date_from', 'date_to')):
            for fy in self:
                if fy.state == 'closed':
                    raise ValidationError(self.env._("Cannot modify dates of a closed fiscal year."))
        return super().write(vals)

    def action_open(self):
        self.check_access('write')
        self.write({'state': 'open'})
        for fy in self:
            fy.message_post(body=self.env._("Fiscal year '%s' opened.", fy.name))

    def action_draft(self):
        self.check_access('write')
        for fy in self:
            if fy.closing_move_id and fy.closing_move_id.state == 'posted':
                raise UserError(self.env._("Cannot reset to draft while a posted closing entry exists."))
        self.write({'state': 'draft'})
        for fy in self:
            fy.message_post(body=self.env._("Fiscal year '%s' reset to draft.", fy.name))

    def action_close(self):
        self.check_access('write')
        self.write({'state': 'closed'})
        for fy in self:
            fy.message_post(body=self.env._("Fiscal year '%s' closed.", fy.name))

    def action_open_close_wizard(self):
        self.ensure_one()
        return {
            'name': self.env._("Close Fiscal Year - %s", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'ydod.fiscal.year.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fiscal_year_id': self.id,
                'default_company_id': self.company_id.id,
                'default_closing_date': self.date_to,
                'default_description': self.env._("Fiscal Year Closing - %s", self.name),
            },
        }

    def action_view_moves(self):
        self.ensure_one()
        return {
            'name': self.env._("Journal Entries (%s)", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('state', '=', 'posted'),
            ],
            'context': {
                'default_company_id': self.company_id.id,
            },
        }
