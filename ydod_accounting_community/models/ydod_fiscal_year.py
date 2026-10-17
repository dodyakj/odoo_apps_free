# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class YdodFiscalYear(models.Model):
    _name = 'ydod.fiscal.year'
    _description = "Fiscal Year"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    _sql_constraints = [
        (
            'check_dates',
            'CHECK(date_from <= date_to)',
            'Fiscal year start date must precede end date.',
        ),
        (
            'code_company_uniq',
            'UNIQUE(code, company_id)',
            'Fiscal year code must be unique per company.',
        ),
    ]

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
                raise ValidationError(_("Fiscal year start date must precede end date."))

    @api.constrains('code', 'company_id')
    def _check_code_unique(self):
        for company in self.company_id:
            fys = self.filtered(lambda r: r.company_id == company)
            codes = [c for c in fys.mapped('code') if c]
            if len(codes) != len(set(codes)):
                raise ValidationError(_("Fiscal year code must be unique per company."))
            domain = [
                ('company_id', '=', company.id),
                ('code', 'in', codes),
                ('id', 'not in', fys.ids),
            ]
            if self.search_count(domain):
                raise ValidationError(_("Fiscal year code must be unique per company."))

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            df = fields.Date.to_date(vals.get('date_from'))
            dt = fields.Date.to_date(vals.get('date_to'))
            if df and dt and df > dt:
                raise ValidationError(_("Fiscal year start date must precede end date."))
            code = vals.get('code')
            company_id = vals.get('company_id') or self.env.company.id
            if code and company_id:
                if self.search_count([('code', '=', code), ('company_id', '=', company_id)]):
                    raise ValidationError(_("Fiscal year code must be unique per company."))
        seen = set()
        for vals in vals_list:
            code = vals.get('code')
            company_id = vals.get('company_id') or self.env.company.id
            if code and company_id:
                key = (code, company_id)
                if key in seen:
                    raise ValidationError(_("Fiscal year code must be unique per company."))
                seen.add(key)
        return super().create(vals_list)

    def write(self, vals):
        if any(f in vals for f in ('date_from', 'date_to')):
            for fy in self:
                if fy.state == 'closed':
                    raise ValidationError(_("Cannot modify dates of a closed fiscal year."))
        for record in self:
            df = fields.Date.to_date(vals.get('date_from', record.date_from))
            dt = fields.Date.to_date(vals.get('date_to', record.date_to))
            if df and dt and df > dt:
                raise ValidationError(_("Fiscal year start date must precede end date."))
            code = vals.get('code', record.code)
            company_id = vals.get('company_id', record.company_id.id if record.company_id else False)
            if ('code' in vals or 'company_id' in vals) and code and company_id:
                if self.search_count([('code', '=', code), ('company_id', '=', company_id), ('id', '!=', record.id)]):
                    raise ValidationError(_("Fiscal year code must be unique per company."))
        return super().write(vals)

    def action_open(self):
        self.check_access_rights('write')
        self.check_access_rule('write')
        self.write({'state': 'open'})
        for fy in self:
            fy.message_post(body=_("Fiscal year '%s' opened.", fy.name))

    def action_draft(self):
        self.check_access_rights('write')
        self.check_access_rule('write')
        for fy in self:
            if fy.closing_move_id and fy.closing_move_id.state == 'posted':
                raise UserError(_("Cannot reset to draft while a posted closing entry exists."))
        self.write({'state': 'draft'})
        for fy in self:
            fy.message_post(body=_("Fiscal year '%s' reset to draft.", fy.name))

    def action_close(self):
        self.check_access_rights('write')
        self.check_access_rule('write')
        self.write({'state': 'closed'})
        for fy in self:
            fy.message_post(body=_("Fiscal year '%s' closed.", fy.name))

    def action_open_close_wizard(self):
        self.ensure_one()
        return {
            'name': _("Close Fiscal Year - %s", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'ydod.fiscal.year.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fiscal_year_id': self.id,
                'default_company_id': self.company_id.id,
                'default_closing_date': self.date_to,
                'default_description': _("Fiscal Year Closing - %s", self.name),
            },
        }

    def action_view_moves(self):
        self.ensure_one()
        return {
            'name': _("Journal Entries (%s)", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
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
