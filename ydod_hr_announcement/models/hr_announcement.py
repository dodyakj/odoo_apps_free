# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrAnnouncement(models.Model):
    _name = 'hr.announcement'
    _description = 'HR Announcement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'publish_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Title',
        required=True,
        size=256,
        tracking=True,
    )
    body = fields.Html(
        string='Announcement Body',
        sanitize=True,
    )
    announcement_type = fields.Selection(
        selection=[
            ('general', 'General'),
            ('warning', 'Warning'),
            ('reward', 'Reward'),
            ('greeting', 'Greeting'),
        ],
        string='Type',
        required=True,
        default='general',
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('expired', 'Expired'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
    )
    target = fields.Selection(
        selection=[
            ('all', 'All Employees'),
            ('department', 'Departments'),
            ('employee', 'Specific Employees'),
        ],
        string='Target Audience',
        required=True,
        default='all',
        tracking=True,
    )
    department_ids = fields.Many2many(
        comodel_name='hr.department',
        relation='hr_announcement_department_rel',
        column1='announcement_id',
        column2='department_id',
        string='Target Departments',
        check_company=True,
    )
    employee_ids = fields.Many2many(
        comodel_name='hr.employee',
        relation='hr_announcement_employee_rel',
        column1='announcement_id',
        column2='employee_id',
        string='Target Employees',
        check_company=True,
    )
    publish_date = fields.Datetime(
        string='Published Date',
        readonly=True,
        copy=False,
    )
    expiry_date = fields.Date(
        string='Expiry Date',
        copy=False,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    read_ids = fields.One2many(
        comodel_name='hr.announcement.read',
        inverse_name='announcement_id',
        string='Read Receipts',
    )

    read_count = fields.Integer(
        string='Read Count',
        compute='_compute_read_count',
        store=True,
    )
    target_employee_count = fields.Integer(
        string='Target Employee Count',
        compute='_compute_target_employee_count',
    )
    is_read = fields.Boolean(
        string='Read by Me',
        compute='_compute_is_read',
        search='_search_is_read',
    )

    _sql_constraints = [
        ('unique_name_company', 'UNIQUE(name, company_id)', 'Announcement title must be unique per company.'),
    ]

    @api.constrains('expiry_date', 'state')
    def _check_expiry_date(self):
        today = fields.Date.today()
        for record in self:
            if record.state == 'draft' and record.expiry_date and record.expiry_date < today:
                raise ValidationError(_("Expiry date must be today or in the future."))

    @api.depends('read_ids')
    def _compute_read_count(self):
        read_data = self.env['hr.announcement.read']._read_group(
            [('announcement_id', 'in', self.ids)],
            ['announcement_id'],
            ['__count'],
        )
        counts = {announcement.id: count for announcement, count in read_data}
        for record in self:
            record.read_count = counts.get(record.id, 0)

    def _get_target_employees(self):
        self.ensure_one()
        Employee = self.env['hr.employee'].sudo()
        domain = [('company_id', '=', self.company_id.id)] if self.company_id else []
        if self.target == 'all':
            return Employee.search(domain)
        elif self.target == 'department':
            if not self.department_ids:
                return Employee.browse()
            return Employee.search(domain + [('department_id', 'in', self.department_ids.ids)])
        elif self.target == 'employee':
            if not self.employee_ids:
                return Employee.browse()
            if self.company_id:
                return self.employee_ids.filtered(lambda e: not e.company_id or e.company_id == self.company_id)
            return self.employee_ids
        return Employee.browse()

    @api.depends('target', 'department_ids', 'employee_ids', 'company_id')
    def _compute_target_employee_count(self):
        all_counts = {}
        for record in self:
            if record.target == 'all':
                comp_id = record.company_id.id
                if comp_id not in all_counts:
                    dom = [('company_id', '=', comp_id)] if comp_id else []
                    all_counts[comp_id] = self.env['hr.employee'].sudo().search_count(dom)
                record.target_employee_count = all_counts[comp_id]
            elif record.target == 'department':
                if not record.department_ids:
                    record.target_employee_count = 0
                else:
                    dom = [('department_id', 'in', record.department_ids.ids)]
                    if record.company_id:
                        dom.append(('company_id', '=', record.company_id.id))
                    record.target_employee_count = self.env['hr.employee'].sudo().search_count(dom)
            elif record.target == 'employee':
                if record.company_id:
                    record.target_employee_count = len(record.employee_ids.filtered(
                        lambda e: not e.company_id or e.company_id == record.company_id
                    ))
                else:
                    record.target_employee_count = len(record.employee_ids)
            else:
                record.target_employee_count = 0

    @api.depends_context('uid')
    def _compute_is_read(self):
        employee = self.env.user.employee_id or self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1
        )
        if not employee or not self.ids:
            for record in self:
                record.is_read = False
            return
        read_announcement_ids = set(
            self.env['hr.announcement.read'].sudo().search([
                ('announcement_id', 'in', self.ids),
                ('employee_id', '=', employee.id),
            ]).mapped('announcement_id.id')
        )
        for record in self:
            record.is_read = record.id in read_announcement_ids

    def _search_is_read(self, operator, value):
        employee = self.env.user.employee_id or self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1
        )
        if not employee:
            if (operator == '=' and value) or (operator == '!=' and not value):
                return [('id', '=', 0)]
            return []
        read_announcement_ids = self.env['hr.announcement.read'].sudo().search([
            ('employee_id', '=', employee.id),
        ]).mapped('announcement_id.id')
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', read_announcement_ids)]
        return [('id', 'not in', read_announcement_ids)]

    def _get_target_partners(self):
        self.ensure_one()
        employees = self._get_target_employees()
        partners = self.env['res.partner']
        for emp in employees:
            partner = emp.user_partner_id or emp.work_contact_id
            if partner:
                partners |= partner
        return partners

    def action_publish(self):
        for record in self:
            record.write({
                'state': 'published',
                'publish_date': fields.Datetime.now(),
            })
            partners = record._get_target_partners()
            if partners:
                record.message_post(
                    body=record.body or record.name,
                    subject=record.name,
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment',
                    partner_ids=partners.ids,
                )
        return True

    def action_expire(self):
        self.write({'state': 'expired'})
        return True

    def action_draft(self):
        for record in self:
            vals = {'state': 'draft'}
            if record.expiry_date and record.expiry_date < fields.Date.today():
                vals['expiry_date'] = False
            record.write(vals)
        return True

    def action_mark_read(self, employee=None):
        ReadReceipt = self.env['hr.announcement.read'].sudo()
        for record in self:
            emp = employee or record.env.user.employee_id or record.env['hr.employee'].sudo().search(
                [('user_id', '=', record.env.uid)], limit=1
            )
            if not emp:
                continue
            existing = ReadReceipt.search([
                ('announcement_id', '=', record.id),
                ('employee_id', '=', emp.id),
            ], limit=1)
            if not existing:
                try:
                    ReadReceipt.create({
                        'announcement_id': record.id,
                        'employee_id': emp.id,
                        'read_date': fields.Datetime.now(),
                    })
                except Exception:
                    pass
        self.invalidate_recordset(['is_read', 'read_count'])
        return True

    def action_view_read_receipts(self):
        self.ensure_one()
        return {
            'name': _('Read Receipts'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.announcement.read',
            'view_mode': 'tree',
            'domain': [('announcement_id', '=', self.id)],
            'context': {'default_announcement_id': self.id},
        }

    @api.model
    def _cron_expire_announcements(self):
        records = self.search([
            ('state', '=', 'published'),
            ('expiry_date', '<', fields.Date.today()),
        ])
        records.write({'state': 'expired'})
        return True
