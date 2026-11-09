from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

ACTION_CODE = "action = env['ydod.approval.request'].action_request_for(records)"


@tagged('post_install', '-at_install')
class TestApprovalEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_b = cls.env['res.company'].create({'name': 'Approval Test Company B'})

        def user(login, groups='base.group_user'):
            return new_test_user(
                cls.env, login, groups=groups, email=f'{login}@example.com', notification_type='inbox')

        cls.requester = user('apr_requester', 'base.group_user,base.group_partner_manager')
        cls.approver = user('apr_approver')
        cls.outsider = user('apr_outsider')
        cls.group_member = user('apr_member')
        cls.manager = user('apr_manager', 'ydod_base_approval_engine.group_approval_manager')
        cls.approver_group = cls.env['res.groups'].create({
            'name': 'Test Approvers',
            'users': [Command.link(cls.group_member.id)],
        })
        cls.Rule = cls.env['ydod.approval.rule']
        cls.Request = cls.env['ydod.approval.request']
        cls.rule = cls.Rule.create({
            'name': 'ACME archiving',
            'sequence': 1,
            'model_id': cls.env.ref('base.model_res_partner').id,
            'domain': "[('name', 'ilike', 'ACME')]",
            'method_names': 'action_archive',
            'approver_user_ids': [Command.set(cls.approver.ids)],
            'approver_group_id': cls.approver_group.id,
            'company_id': False,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'ACME Industries'})
        cls.partner_b = cls.env['res.partner'].create({'name': 'ACME Logistics'})
        cls.other_partner = cls.env['res.partner'].create({'name': 'Beta Supplies'})

    def setUp(self):
        super().setUp()
        # the test transaction is rolled back, but guards patched on model classes are not:
        # remove the guards installed by rules created during the test
        initial = self._guard_keys()

        def remove_test_guards():
            for model_name, name in self._guard_keys() - initial:
                delattr(self.registry[model_name], name)
        self.addCleanup(remove_test_guards)

    def _guard_keys(self):
        return {
            (Model._name, name)
            for Model in self.registry.values()
            for name, attr in vars(Model).items()
            if getattr(attr, '_ydod_approval_guard', False)
        }

    def _request(self, partner):
        self.Request.with_user(self.requester).action_request_for(partner.with_user(self.requester))
        return self.Request.search([
            ('res_model', '=', 'res.partner'), ('res_id', '=', partner.id), ('state', '=', 'to_approve')])

    def test_guard_blocks_matching_document(self):
        with self.assertRaises(UserError) as cm:
            self.partner.with_user(self.requester).action_archive()
        self.assertIn('This document requires approval', str(cm.exception))
        self.assertTrue(self.partner.active)
        self.other_partner.with_user(self.requester).action_archive()
        self.assertFalse(self.other_partner.active)

    def test_request_approve_flow(self):
        request = self._request(self.partner)
        self.assertEqual(len(request), 1)
        self.assertEqual(request.rule_id, self.rule)
        self.assertEqual(request.requester_id, self.requester)
        self.assertTrue(request.name.startswith('APR/'))
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'), ('res_id', '=', self.partner.id),
            ('user_id', '=', self.approver.id)])
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.activity_type_id, self.env.ref('mail.mail_activity_data_todo'))
        self.assertIn(self.approver.partner_id, self.partner.message_partner_ids)

        request.with_user(self.approver).action_approve()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.decided_by_id, self.approver)
        # done activities are deleted in Odoo 16.0
        self.assertFalse(activity.exists())
        self.assertTrue(any('Approved' in str(m.body) for m in self.partner.message_ids))

        self.partner.with_user(self.requester).action_archive()
        self.assertFalse(self.partner.active)

    def test_reject_requires_reason(self):
        request = self._request(self.partner)
        Wizard = self.env['ydod.approval.reject.wizard'].with_user(self.approver)
        wizard = Wizard.create({'request_ids': [Command.set(request.ids)], 'reason': '   '})
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertEqual(request.state, 'to_approve')

        wizard = Wizard.create({'request_ids': [Command.set(request.ids)], 'reason': 'Credit limit exceeded'})
        wizard.action_confirm()
        self.assertEqual(request.state, 'rejected')
        self.assertEqual(request.reject_reason, 'Credit limit exceeded')
        self.assertTrue(any('Credit limit exceeded' in str(m.body) for m in self.partner.message_ids))

        new_request = self._request(self.partner)
        self.assertEqual(len(new_request), 1)
        self.assertNotEqual(new_request, request)

    def test_constraints(self):
        vals = {
            'res_model': 'res.partner', 'res_id': self.partner.id, 'rule_id': self.rule.id,
            'approver_user_ids': [Command.set(self.approver.ids)],
        }
        self.Request.create(vals)
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self.Request.create(vals)

        base = {
            'name': 'Invalid', 'model_id': self.env.ref('base.model_res_partner').id,
            'method_names': 'action_archive', 'approver_user_ids': [Command.set(self.approver.ids)],
        }
        with self.assertRaises(ValidationError):
            self.Rule.create(dict(base, approver_user_ids=False))
        with self.assertRaises(ValidationError):
            self.Rule.create(dict(base, method_names='write'))
        with self.assertRaises(ValidationError):
            self.Rule.create(dict(base, method_names='nonexistent_method'))
        with self.assertRaises(ValidationError):
            self.Rule.create(dict(base, domain="[('no_such_field', '=', 1)]"))

    def test_approval_not_reusable(self):
        request = self._request(self.partner)
        request.with_user(self.approver).action_approve()
        with self.assertRaises(UserError):
            self.partner_b.with_user(self.requester).action_archive()
        self.assertTrue(self.partner_b.active)
        with self.assertRaises(UserError):
            request.write({'res_id': self.partner_b.id})
        with self.assertRaises(UserError):
            self.Request.with_user(self.requester).action_request_for(self.partner.with_user(self.requester))

    def test_access_rights(self):
        request = self._request(self.partner)
        with self.assertRaises(AccessError):
            request.with_user(self.outsider).read(['state'])
        # AccessError is a subclass of UserError; Odoo's assertRaises takes a single class
        with self.assertRaises(UserError):
            request.with_user(self.outsider).action_approve()
        with self.assertRaises(UserError):
            request.with_user(self.requester).action_approve()
        request.with_user(self.group_member).action_approve()
        self.assertEqual(request.state, 'approved')

        rule_vals = {
            'name': 'Tag rule', 'model_id': self.env.ref('base.model_res_partner_category').id,
            'method_names': 'action_archive', 'approver_user_ids': [Command.set(self.approver.ids)],
        }
        with self.assertRaises(AccessError):
            self.Rule.with_user(self.requester).create(rule_vals)
        self.assertTrue(self.Rule.with_user(self.manager).create(rule_vals))

    def test_cancel(self):
        request = self._request(self.partner)
        with self.assertRaises(UserError):
            request.with_user(self.approver).action_cancel()
        request.with_user(self.requester).action_cancel()
        self.assertEqual(request.state, 'cancelled')

    def test_archive_rule_removes_guard_and_action(self):
        category = self.env['res.partner.category'].create({'name': 'Strategic'})
        tag_rule = self.Rule.create({
            'name': 'Tag archiving', 'model_id': self.env.ref('base.model_res_partner_category').id,
            'method_names': 'action_archive', 'approver_user_ids': [Command.set(self.approver.ids)],
        })
        Category = self.registry['res.partner.category']
        self.assertTrue(getattr(Category.action_archive, '_ydod_approval_guard', False))
        self.assertTrue(tag_rule.server_action_id)
        self.assertEqual(tag_rule.server_action_id.binding_model_id, tag_rule.model_id)
        with self.assertRaises(UserError):
            category.action_archive()

        tag_rule.action_archive()
        self.assertFalse(getattr(Category.action_archive, '_ydod_approval_guard', False))
        self.assertFalse(self.env['ir.actions.server'].search_count([
            ('model_id', '=', tag_rule.model_id.id), ('code', '=', ACTION_CODE)]))
        category.action_archive()
        self.assertFalse(category.active)

    def test_counters_and_search(self):
        request = self._request(self.partner)
        self.assertIn(request, self.Request.with_user(self.approver).search([('can_decide', '=', True)]))
        self.assertIn(request, self.Request.with_user(self.group_member).search([('can_decide', '=', True)]))
        self.assertNotIn(request, self.Request.with_user(self.requester).search([('can_decide', '=', True)]))
        self.assertTrue(request.with_user(self.approver).can_decide)
        self.assertFalse(request.with_user(self.requester).can_decide)

        self.assertEqual(self.approver.approval_waiting_count, 1)
        self.assertEqual(self.group_member.approval_waiting_count, 1)
        self.assertEqual(self.requester.approval_waiting_count, 0)
        self.assertEqual(self.rule.request_pending_count, 1)
        self.assertEqual(self.rule.request_decided_count, 0)
        request.with_user(self.approver).action_approve()
        self.rule.invalidate_recordset(['request_pending_count', 'request_decided_count'])
        self.assertEqual(self.rule.request_pending_count, 0)
        self.assertEqual(self.rule.request_decided_count, 1)

    def test_multi_company_isolation(self):
        partner_c = self.env['res.partner'].create({'name': 'ACME Overseas'})
        request = self.Request.create({
            'res_model': 'res.partner', 'res_id': partner_c.id, 'rule_id': self.rule.id,
            'requester_id': self.requester.id, 'company_id': self.company_b.id,
        })
        self.assertFalse(self.Request.with_user(self.requester).search([('id', '=', request.id)]))
        rule_b = self.Rule.create({
            'name': 'Company B rule', 'model_id': self.env.ref('base.model_res_partner_category').id,
            'method_names': 'action_archive', 'approver_user_ids': [Command.set(self.approver.ids)],
            'company_id': self.company_b.id,
        })
        self.assertFalse(self.Rule.with_user(self.requester).search([('id', '=', rule_b.id)]))
        self.assertTrue(self.Rule.with_user(self.requester).search([('id', '=', self.rule.id)]))
