# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestHrAnnouncement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref('base.main_company')
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_manager = cls.env.ref('ydod_hr_announcement.group_hr_announcement_manager')

        # Create basic employee user with strictly base.group_user only
        cls.user_employee = cls.env['res.users'].create({
            'name': 'Standard Employee User',
            'login': 'test_standard_employee',
            'email': 'std_employee@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.group_user.write({'user_ids': [(4, cls.user_employee.id)]})
        cls.user_employee.write({'group_ids': [(6, 0, [cls.group_user.id])]})

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Standard Employee',
            'user_id': cls.user_employee.id,
            'company_id': cls.company.id,
        })

        # Create announcement manager user
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Announcement Manager User',
            'login': 'test_announcement_manager',
            'email': 'ann_manager@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.group_user.write({'user_ids': [(4, cls.user_manager.id)]})
        cls.group_manager.write({'user_ids': [(4, cls.user_manager.id)]})

        cls.manager_employee = cls.env['hr.employee'].create({
            'name': 'Announcement Manager Employee',
            'user_id': cls.user_manager.id,
            'company_id': cls.company.id,
        })

    def test_publish_workflow(self):
        """Test draft -> published -> expired -> draft state transitions."""
        announcement = self.env['hr.announcement'].create({
            'name': 'Company Townhall Q4',
            'announcement_type': 'general',
            'target': 'all',
            'state': 'draft',
            'company_id': self.company.id,
        })
        self.assertEqual(announcement.state, 'draft')
        self.assertFalse(announcement.publish_date)

        # Publish
        announcement.action_publish()
        self.assertEqual(announcement.state, 'published')
        self.assertTrue(announcement.publish_date)

        # Expire
        announcement.action_expire()
        self.assertEqual(announcement.state, 'expired')

        # Reset to draft
        announcement.action_draft()
        self.assertEqual(announcement.state, 'draft')

    def test_target_resolution(self):
        """Verify targeted department employees receive mail.message notification upon publish."""
        dept = self.env['hr.department'].create({
            'name': 'Product Design',
            'company_id': self.company.id,
        })

        # Create 3 employees in this department with distinct partners
        partners = self.env['res.partner']
        for i in range(1, 4):
            user = self.env['res.users'].create({
                'name': f'Designer {i}',
                'login': f'designer_{i}_{self.env.cr.dbname}',
                'email': f'designer{i}@example.com',
                'company_id': self.company.id,
                'company_ids': [(6, 0, [self.company.id])],
            })
            self.group_user.write({'user_ids': [(4, user.id)]})
            self.env['hr.employee'].create({
                'name': f'Designer {i}',
                'user_id': user.id,
                'department_id': dept.id,
                'company_id': self.company.id,
            })
            partners |= user.partner_id

        announcement = self.env['hr.announcement'].create({
            'name': 'Design Guidelines 2026',
            'target': 'department',
            'department_ids': [(4, dept.id)],
            'state': 'draft',
            'company_id': self.company.id,
        })

        announcement.action_publish()
        self.assertEqual(announcement.state, 'published')

        # Verify mail.message posted with the targeted partners
        messages = announcement.message_ids.filtered(lambda m: m.message_type == 'notification')
        self.assertTrue(messages)
        posted_message = messages[0]
        for partner in partners:
            self.assertIn(partner, posted_message.partner_ids)

    def test_read_receipt_creation(self):
        """Publish announcement, mark as read, verify idempotency and unique constraint."""
        announcement = self.env['hr.announcement'].create({
            'name': 'Annual Policy Refresh',
            'target': 'all',
            'state': 'draft',
            'company_id': self.company.id,
        })
        announcement.action_publish()

        # Employee marks as read
        announcement.with_user(self.user_employee).action_mark_read()
        receipt = self.env['hr.announcement.read'].search([
            ('announcement_id', '=', announcement.id),
            ('employee_id', '=', self.employee.id),
        ])
        self.assertTrue(receipt)
        self.assertEqual(receipt.employee_id, self.employee)
        self.assertTrue(receipt.read_date)
        self.assertTrue(announcement.with_user(self.user_employee).is_read)

        # Calling mark_read again does not create a duplicate
        announcement.with_user(self.user_employee).action_mark_read()
        receipt_count = self.env['hr.announcement.read'].search_count([
            ('announcement_id', '=', announcement.id),
            ('employee_id', '=', self.employee.id),
        ])
        self.assertEqual(receipt_count, 1)

        # Direct duplicate creation violates unique constraint
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self.env['hr.announcement.read'].create({
                'announcement_id': announcement.id,
                'employee_id': self.employee.id,
            })

    def test_computed_read_count(self):
        """Verify read_count, target_employee_count computations and stat action."""
        dept = self.env['hr.department'].create({
            'name': 'Customer Care',
            'company_id': self.company.id,
        })
        employees = self.env['hr.employee']
        for i in range(1, 4):
            emp = self.env['hr.employee'].create({
                'name': f'Support Agent {i}',
                'department_id': dept.id,
                'company_id': self.company.id,
            })
            employees |= emp

        announcement = self.env['hr.announcement'].create({
            'name': 'Shift Schedule Adjustments',
            'target': 'department',
            'department_ids': [(4, dept.id)],
            'state': 'draft',
            'company_id': self.company.id,
        })
        announcement.action_publish()

        self.assertEqual(announcement.target_employee_count, 3)
        self.assertEqual(announcement.read_count, 0)

        # Create 2 read receipts
        self.env['hr.announcement.read'].create({
            'announcement_id': announcement.id,
            'employee_id': employees[0].id,
        })
        self.env['hr.announcement.read'].create({
            'announcement_id': announcement.id,
            'employee_id': employees[1].id,
        })

        announcement.invalidate_recordset(['read_count'])
        self.assertEqual(announcement.read_count, 2)
        self.assertEqual(announcement.target_employee_count, 3)

        # Test action_view_reads
        action = announcement.action_view_reads()
        self.assertEqual(action.get('res_model'), 'hr.announcement.read')
        self.assertEqual(action.get('view_mode'), 'list')

    def test_expiry_cron(self):
        """Verify scheduled action automatically expires overdue published announcements."""
        yesterday = fields.Date.today() - timedelta(days=1)
        announcement = self.env['hr.announcement'].create({
            'name': 'Flash Feedback Survey',
            'target': 'all',
            'state': 'published',
            'expiry_date': yesterday,
            'company_id': self.company.id,
        })
        self.assertEqual(announcement.state, 'published')

        self.env['hr.announcement']._cron_expire_announcements()
        self.assertEqual(announcement.state, 'expired')

    def test_expiry_date_constraint(self):
        """Verify draft announcement cannot be created with an expiry date in the past."""
        yesterday = fields.Date.today() - timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.env['hr.announcement'].create({
                'name': 'Outdated Draft Notice',
                'state': 'draft',
                'expiry_date': yesterday,
                'company_id': self.company.id,
            })

    def test_unique_name_company(self):
        """Verify announcement title uniqueness per company."""
        self.env['hr.announcement'].create({
            'name': 'Exclusive Notice Title',
            'company_id': self.company.id,
        })
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self.env['hr.announcement'].create({
                'name': 'Exclusive Notice Title',
                'company_id': self.company.id,
            })

    def test_access_employee_cannot_write(self):
        """Verify standard employee can read published, cannot read draft, cannot write/create/delete."""
        announcement = self.env['hr.announcement'].create({
            'name': 'Leadership Note',
            'state': 'published',
            'company_id': self.company.id,
        })

        # Employee can read published announcement
        self.assertEqual(announcement.with_user(self.user_employee).name, 'Leadership Note')

        # Employee cannot create announcements
        with self.assertRaises(AccessError):
            self.env['hr.announcement'].with_user(self.user_employee).create({
                'name': 'Unauthorized Creation',
                'company_id': self.company.id,
            })

        # Employee cannot write to announcements
        with self.assertRaises(AccessError):
            announcement.with_user(self.user_employee).write({
                'name': 'Tampered Title',
            })

        # Employee cannot unlink announcements
        with self.assertRaises(AccessError):
            announcement.with_user(self.user_employee).unlink()

        # Employee cannot read draft announcements
        draft_ann = self.env['hr.announcement'].create({
            'name': 'Draft Secret Note',
            'state': 'draft',
            'company_id': self.company.id,
        })
        with self.assertRaises(AccessError):
            draft_ann.with_user(self.user_employee).read(['name'])

    def test_access_manager_full_crud(self):
        """Verify HR Announcement Manager has full CRUD capabilities."""
        mgr_announcement = self.env['hr.announcement'].with_user(self.user_manager).create({
            'name': 'Manager Authorized Notice',
            'target': 'all',
            'company_id': self.company.id,
        })
        self.assertTrue(mgr_announcement.id)

        mgr_announcement.write({'name': 'Manager Authorized Notice Updated'})
        self.assertEqual(mgr_announcement.name, 'Manager Authorized Notice Updated')

        read_record = self.env['hr.announcement'].with_user(self.user_manager).browse(mgr_announcement.id)
        self.assertEqual(read_record.name, 'Manager Authorized Notice Updated')

        ann_id = mgr_announcement.id
        mgr_announcement.unlink()
        self.assertFalse(self.env['hr.announcement'].browse(ann_id).exists())

    def test_multi_company_isolation(self):
        """Verify employees in Company A cannot see announcements from Company B."""
        company_b = self.env['res.company'].create({'name': 'Branch Beta'})

        user_b = self.env['res.users'].create({
            'name': 'Employee Beta',
            'login': f'emp_beta_{self.env.cr.dbname}',
            'email': 'beta@example.com',
            'company_id': company_b.id,
            'company_ids': [(6, 0, [company_b.id])],
        })
        self.group_user.write({'user_ids': [(4, user_b.id)]})

        ann_a = self.env['hr.announcement'].create({
            'name': 'Alpha HQ Policy',
            'state': 'published',
            'company_id': self.company.id,
        })
        ann_b = self.env['hr.announcement'].create({
            'name': 'Beta Branch Internal Note',
            'state': 'published',
            'company_id': company_b.id,
        })

        # Employee in Company A querying announcements
        visible_announcements = self.env['hr.announcement'].with_user(self.user_employee).with_context(
            allowed_company_ids=[self.company.id]
        ).search([])

        self.assertIn(ann_a, visible_announcements)
        self.assertNotIn(ann_b, visible_announcements)

        # Attempting direct read on Company B announcement raises AccessError
        with self.assertRaises(AccessError):
            ann_b.with_user(self.user_employee).with_context(
                allowed_company_ids=[self.company.id]
            ).read(['name'])
