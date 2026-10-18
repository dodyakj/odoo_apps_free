from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DisciplinaryAction(models.Model):
    _name = 'ydod.disciplinary.action'
    _description = 'Disciplinary Action'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'incident_date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True,
        index=True
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        string='Department',
        readonly=True,
        store=True
    )
    job_id = fields.Many2one(
        'hr.job',
        related='employee_id.job_id',
        string='Job Position',
        readonly=True,
        store=True
    )
    manager_id = fields.Many2one(
        'res.users',
        string='Reported By',
        tracking=True,
        default=lambda self: self.env.user,
        required=True
    )
    action_type = fields.Selection([
        ('verbal', 'Verbal Warning'),
        ('written', 'Written Warning'),
        ('final', 'Final Written Warning'),
        ('suspension', 'Suspension'),
        ('termination', 'Termination'),
    ], string='Action Type', required=True, tracking=True, default='verbal')
    
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Severity', required=True, tracking=True, default='medium')

    incident_date = fields.Date(
        string='Incident Date',
        required=True,
        tracking=True,
        default=fields.Date.context_today
    )
    expiration_date = fields.Date(
        string='Warning Expiration Date',
        tracking=True,
        help='Date when this warning expires and is no longer active against the employee.'
    )
    
    subject = fields.Char(
        string='Subject',
        required=True,
        tracking=True
    )
    description = fields.Html(
        string='Incident Details & Findings',
        required=True
    )
    corrective_action = fields.Html(
        string='Required Corrective Actions'
    )
    employee_remarks = fields.Text(
        string='Employee Remarks / Defense'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Pending Review'),
        ('confirmed', 'Confirmed / Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ydod.disciplinary.action') or _('New')
        return super().create(vals_list)

    @api.constrains('incident_date', 'expiration_date')
    def _check_dates(self):
        for record in self:
            if record.incident_date and record.expiration_date:
                if record.expiration_date < record.incident_date:
                    raise ValidationError(_('The warning expiration date cannot be earlier than the incident date.'))

    def action_submit(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'submitted'

    def action_confirm(self):
        for record in self:
            if record.state in ('draft', 'submitted'):
                record.state = 'confirmed'

    def action_expire(self):
        for record in self:
            record.state = 'expired'

    def action_cancel(self):
        for record in self:
            record.state = 'cancelled'

    def action_draft(self):
        for record in self:
            record.state = 'draft'
