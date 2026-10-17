from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestProjectTaskStageDuration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_main = cls.env.company

        cls.stage_new = cls.env['project.task.type'].create({
            'name': 'New',
            'sequence': 1,
            'max_duration_hours': 0.0,
        })
        cls.stage_in_progress = cls.env['project.task.type'].create({
            'name': 'In Progress',
            'sequence': 2,
            'max_duration_hours': 24.0,
        })
        cls.stage_review = cls.env['project.task.type'].create({
            'name': 'Review',
            'sequence': 3,
            'max_duration_hours': 8.0,
        })
        cls.stage_done = cls.env['project.task.type'].create({
            'name': 'Done',
            'sequence': 4,
            'max_duration_hours': 0.0,
            'fold': True,
        })

        cls.project = cls.env['project.project'].create({
            'name': 'Duration Tracking Test Project',
            'company_id': cls.company_main.id,
            'type_ids': [
                (4, cls.stage_new.id),
                (4, cls.stage_in_progress.id),
                (4, cls.stage_review.id),
                (4, cls.stage_done.id),
            ],
        })

        group_user = cls.env.ref('base.group_user')
        group_project_user = cls.env.ref('project.group_project_user')
        group_project_manager = cls.env.ref('project.group_project_manager')

        cls.project_user = cls.env['res.users'].create({
            'name': 'Project Regular User',
            'login': 'project_user_duration_test',
            'email': 'proj_user@test.example',
            'company_id': cls.company_main.id,
            'company_ids': [(6, 0, [cls.company_main.id])],
            'groups_id': [(6, 0, [group_user.id, group_project_user.id])],
        })

        cls.project_manager = cls.env['res.users'].create({
            'name': 'Project Manager User',
            'login': 'project_mgr_duration_test',
            'email': 'proj_mgr@test.example',
            'company_id': cls.company_main.id,
            'company_ids': [(6, 0, [cls.company_main.id])],
            'groups_id': [(6, 0, [group_user.id, group_project_manager.id])],
        })

    def _create_task(self, name='Test Task', stage=None):
        return self.env['project.task'].create({
            'name': name,
            'project_id': self.project.id,
            'stage_id': stage.id if stage else self.stage_new.id,
            'company_id': self.company_main.id,
        })

    def test_task_create_initial_history(self):
        """Test initial stage history and entry date initialization upon task creation."""
        task = self._create_task(name='Initial History Verification')
        self.assertTrue(task.stage_entered_date)
        self.assertEqual(len(task.stage_history_ids), 1)

        history = task.stage_history_ids
        self.assertEqual(history.task_id, task)
        self.assertEqual(history.stage_id, self.stage_new)
        self.assertTrue(history.is_current)
        self.assertFalse(history.date_end)
        self.assertEqual(history.duration_hours, 0.0)
        self.assertEqual(history.duration_days, 0.0)
        self.assertEqual(history.user_id, self.env.user)
        self.assertEqual(history.company_id, task.company_id)
        self.assertFalse(task.is_stage_bottleneck)
        self.assertTrue(task.current_stage_duration_display)

    def test_stage_transition_and_duration_calculation(self):
        """Test active record closing, duration calculation, and new stage creation."""
        now = fields.Datetime.now()
        hours_ago = 5.0
        start_time = now - timedelta(hours=hours_ago)

        task = self._create_task(name='Transition Test Task')
        initial_history = task.stage_history_ids.filtered('is_current')
        initial_history.sudo().write({'date_start': start_time})
        task.sudo().write({'stage_entered_date': start_time})

        task.write({'stage_id': self.stage_in_progress.id})

        self.assertEqual(len(task.stage_history_ids), 2)
        closed_history = task.stage_history_ids.filtered(lambda h: not h.is_current)
        active_history = task.stage_history_ids.filtered('is_current')

        self.assertEqual(closed_history.stage_id, self.stage_new)
        self.assertTrue(closed_history.date_end)
        self.assertAlmostEqual(closed_history.duration_hours, hours_ago, delta=0.1)
        self.assertAlmostEqual(closed_history.duration_days, hours_ago / 24.0, delta=0.01)

        self.assertEqual(active_history.stage_id, self.stage_in_progress)
        self.assertFalse(active_history.date_end)
        self.assertEqual(active_history.duration_hours, 0.0)

    def test_is_stage_bottleneck_and_search(self):
        """Test bottleneck computation and search filter when stage threshold is exceeded."""
        now = fields.Datetime.now()
        task = self.env['project.task'].create({
            'name': 'Bottleneck Evaluation Task',
            'project_id': self.project.id,
            'stage_id': self.stage_review.id,  # threshold: 8 hours
        })

        # Scenario A: Within threshold (3 hours elapsed)
        within_threshold = now - timedelta(hours=3)
        task.sudo().write({'stage_entered_date': within_threshold})
        task.invalidate_recordset(['is_stage_bottleneck', 'current_stage_duration_hours'])
        self.assertFalse(task.is_stage_bottleneck)

        search_bottlenecks = self.env['project.task'].search([
            ('id', '=', task.id),
            ('is_stage_bottleneck', '=', True),
        ])
        self.assertNotIn(task, search_bottlenecks)

        # Scenario B: Exceeded threshold (12 hours elapsed > 8h)
        exceeded_threshold = now - timedelta(hours=12)
        task.sudo().write({'stage_entered_date': exceeded_threshold})
        task.invalidate_recordset(['is_stage_bottleneck', 'current_stage_duration_hours'])
        self.assertTrue(task.is_stage_bottleneck)

        search_bottlenecks = self.env['project.task'].search([
            ('id', '=', task.id),
            ('is_stage_bottleneck', '=', True),
        ])
        self.assertIn(task, search_bottlenecks)

        search_non_bottlenecks = self.env['project.task'].search([
            ('id', '=', task.id),
            ('is_stage_bottleneck', '=', False),
        ])
        self.assertNotIn(task, search_non_bottlenecks)

    def test_chatter_notification(self):
        """Test chatter message generated with duration summary upon stage change."""
        task = self._create_task(name='Chatter Notification Task')
        initial_msg_count = len(task.message_ids)

        task.write({'stage_id': self.stage_in_progress.id})

        new_messages = task.message_ids
        self.assertGreater(len(new_messages), initial_msg_count)
        latest_msg = new_messages[0]
        self.assertIn(self.stage_new.name, latest_msg.body)
        self.assertIn(self.stage_in_progress.name, latest_msg.body)
        self.assertIn('Time spent in', latest_msg.body)

    def test_stage_reentry_back_and_forth(self):
        """Test task moving back and forth between stages creates distinct history records."""
        task = self._create_task(name='Reentry Task')
        self.assertEqual(len(task.stage_history_ids), 1)

        task.write({'stage_id': self.stage_in_progress.id})
        self.assertEqual(len(task.stage_history_ids), 2)

        task.write({'stage_id': self.stage_new.id})
        self.assertEqual(len(task.stage_history_ids), 3)

        new_stage_histories = task.stage_history_ids.filtered(lambda h: h.stage_id == self.stage_new)
        self.assertEqual(len(new_stage_histories), 2)

        active_histories = task.stage_history_ids.filtered('is_current')
        self.assertEqual(len(active_histories), 1)
        self.assertEqual(active_histories.stage_id, self.stage_new)

    def test_security_project_user_and_manager(self):
        """Test security: Project User can read history, cannot modify/unlink/create history directly, but can change task stage."""
        task = self._create_task(name='Security Test Task')
        history = task.stage_history_ids[0]

        # 1. Project User can read history
        history_read = history.with_user(self.project_user).read(['stage_id', 'duration_hours', 'is_current'])
        self.assertTrue(history_read)

        # 2. Project User cannot modify history directly
        with self.assertRaises(AccessError):
            history.with_user(self.project_user).write({'duration_hours': 100.0})

        # 3. Project User cannot delete history
        with self.assertRaises(AccessError):
            history.with_user(self.project_user).unlink()

        # 4. Project User cannot create history record manually
        with self.assertRaises(AccessError):
            self.env['project.task.stage.history'].with_user(self.project_user).create({
                'task_id': task.id,
                'stage_id': self.stage_in_progress.id,
                'company_id': task.company_id.id,
            })

        # 5. Project User CAN update task stage (automated history logging works via sudo)
        task.with_user(self.project_user).write({'stage_id': self.stage_review.id})
        self.assertEqual(task.stage_id, self.stage_review)
        self.assertEqual(len(task.stage_history_ids), 2)

        # 5b. Project User can create a task and initial history is logged
        task_user = self.env['project.task'].with_user(self.project_user).create({
            'name': 'User Created Task',
            'project_id': self.project.id,
            'stage_id': self.stage_new.id,
            'company_id': self.company_main.id,
        })
        self.assertEqual(len(task_user.stage_history_ids), 1)
        self.assertEqual(task_user.stage_history_ids.user_id, self.project_user)

        # 6. Project Manager has full access on stage history
        active_history = task.stage_history_ids.filtered('is_current')
        active_history.with_user(self.project_manager).write({'duration_hours': 1.5})
        self.assertEqual(active_history.duration_hours, 1.5)

    def test_security_multi_company(self):
        """Test multi-company record rules isolate stage history across companies."""
        company_b = self.env['res.company'].create({'name': 'Secondary Company'})
        project_b = self.env['project.project'].create({
            'name': 'Company B Project',
            'company_id': company_b.id,
            'type_ids': [(4, self.stage_new.id)],
        })
        task_b = self.env['project.task'].create({
            'name': 'Company B Task',
            'project_id': project_b.id,
            'stage_id': self.stage_new.id,
            'company_id': company_b.id,
        })
        history_b = task_b.stage_history_ids

        # User in company A only should not see history from company B
        search_as_user_a = self.env['project.task.stage.history'].with_user(self.project_user).search([
            ('id', '=', history_b.id),
        ])
        self.assertFalse(search_as_user_a)

    def test_sql_constraints(self):
        """Test SQL constraints on stage type max_duration_hours and stage history dates."""
        # 1. max_duration_hours must be non-negative
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            with self.cr.savepoint():
                self.env['project.task.type'].create({
                    'name': 'Negative Threshold Stage',
                    'max_duration_hours': -10.0,
                })

        # 2. date_end must be >= date_start
        now = fields.Datetime.now()
        task = self._create_task(name='SQL Constraint Test Task')
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            with self.cr.savepoint():
                self.env['project.task.stage.history'].create({
                    'task_id': task.id,
                    'stage_id': self.stage_new.id,
                    'company_id': task.company_id.id,
                    'date_start': now,
                    'date_end': now - timedelta(hours=2),
                })
