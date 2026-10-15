from odoo import api, fields, models


class AccountLockDateAudit(models.Model):
    _name = 'account.lock.date.audit'
    _description = 'Accounting Lock Date Audit Log'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Audit Reference',
        compute='_compute_name',
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Changed By',
        default=lambda self: self.env.user,
        required=True,
        index=True,
        readonly=True,
    )
    date = fields.Datetime(
        string='Timestamp',
        default=fields.Datetime.now,
        required=True,
        index=True,
        readonly=True,
    )
    lock_type = fields.Selection([
        ('sale', 'Sales Lock Date'),
        ('purchase', 'Purchase Lock Date'),
        ('tax', 'Tax Return Lock Date'),
        ('fiscalyear', 'Global / Fiscal Year Lock Date'),
        ('hard', 'Hard Lock Date'),
        ('all', 'All / Multiple Lock Dates'),
    ], string='Lock Type', required=True, default='sale', readonly=True)
    field_name = fields.Char(
        string='Technical Field',
        readonly=True,
    )
    old_date = fields.Date(
        string='Previous Lock Date',
        readonly=True,
    )
    new_date = fields.Date(
        string='New Lock Date',
        readonly=True,
    )
    action_type = fields.Selection([
        ('auto_cron', 'Scheduled Auto-Lock'),
        ('manual_update', 'Manual Setting Change'),
        ('manual_run', 'Manual Auto-Lock Run'),
        ('bypass_entry', 'Bypass Entry Posting'),
    ], string='Action Source', default='manual_update', required=True, readonly=True)
    reason = fields.Char(
        string='Reason / Note',
        readonly=True,
    )
    move_id = fields.Many2one(
        'account.move',
        string='Related Journal Entry',
        ondelete='set null',
        readonly=True,
    )

    @api.depends('lock_type', 'date', 'action_type')
    def _compute_name(self):
        for record in self:
            dt_str = record.date.strftime('%Y-%m-%d %H:%M') if record.date else ''
            type_label = dict(record._fields['lock_type'].selection).get(record.lock_type, record.lock_type or '')
            record.name = f"{type_label} ({dt_str})" if dt_str else (type_label or self.env._('Audit Log'))

    @api.depends('name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name or self.env._("Audit Log #%s", record.id)
