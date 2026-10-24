# -*- coding: utf-8 -*-
from odoo import fields, models


class HrAnnouncementRead(models.Model):
    _name = 'hr.announcement.read'
    _description = 'HR Announcement Read Receipt'
    _order = 'read_date desc, id desc'
    _check_company_auto = True

    announcement_id = fields.Many2one(
        comodel_name='hr.announcement',
        string='Announcement',
        required=True,
        ondelete='cascade',
        index=True,
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    read_date = fields.Datetime(
        string='Read Date',
        required=True,
        default=fields.Datetime.now,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related='announcement_id.company_id',
        store=True,
        index=True,
    )

    _sql_constraints = [
        ('unique_read_per_employee', 'UNIQUE(announcement_id, employee_id)', 'Each employee can have only one read receipt per announcement.'),
    ]
