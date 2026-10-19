from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestYdodMenuAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Access = cls.env['ydod.menu.access']
        cls.Menu = cls.env['ir.ui.menu']
        cls.company_a = cls.env.ref('base.main_company')
        cls.company_b = cls.env['res.company'].create({'name': 'YDoD Test Company B'})
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_manager = cls.env.ref('ydod_menu_access_control.group_menu_access_manager')
        cls.group_test = cls.env['res.groups'].create({'name': 'YDoD Test Group'})
        cls.user_alpha = cls._create_user('Alpha', 'ydod_alpha', cls.group_user, cls.company_a)
        cls.user_beta = cls._create_user('Beta', 'ydod_beta', cls.group_user, cls.company_a)
        cls.user_gamma = cls._create_user('Gamma', 'ydod_gamma', cls.group_user, cls.company_b)
        cls.user_manager = cls._create_user(
            'Manager', 'ydod_manager', cls.group_user + cls.group_manager, cls.company_a)
        cls.user_admin = cls.env.ref('base.user_admin')
        cls.group_test.write({'user_ids': [Command.link(cls.user_alpha.id)]})
        action = cls.env['ir.actions.act_window'].create({
            'name': 'YDoD Test Partners', 'res_model': 'res.partner', 'view_mode': 'list,form'})
        action_ref = 'ir.actions.act_window,%d' % action.id
        cls.menu_root = cls.Menu.create({'name': 'YDoD Test Root'})
        cls.menu_child = cls.Menu.create({
            'name': 'YDoD Test Child', 'parent_id': cls.menu_root.id, 'action': action_ref})
        cls.menu_grandchild = cls.Menu.create({
            'name': 'YDoD Test Grandchild', 'parent_id': cls.menu_child.id, 'action': action_ref})

    @classmethod
    def _create_user(cls, name, login, groups, company):
        user = cls.env['res.users'].create({
            'name': name,
            'login': login,
            'email': login + '@example.com',
            'company_id': company.id,
            'company_ids': [Command.set([company.id])],
        })
        user.write({'group_ids': [Command.set(groups.ids)]})
        return user

    def _rule(self, menu, user=None, group=None, company=None):
        return self.Access.create({
            'menu_id': menu.id,
            'user_id': user.id if user else False,
            'group_id': group.id if group else False,
            'company_id': (company or self.company_a).id,
        })

    def _visible_ids(self, user):
        self.env.registry.clear_cache()
        return set(self.Menu.with_user(user).load_menus(False).keys())

    def test_user_restriction_hides_menu_for_that_user_only(self):
        self.assertIn(self.menu_child.id, self._visible_ids(self.user_alpha))
        self._rule(self.menu_child, user=self.user_alpha)
        visible_alpha = self._visible_ids(self.user_alpha)
        self.assertNotIn(self.menu_child.id, visible_alpha)
        self.assertNotIn(self.menu_grandchild.id, visible_alpha, "sub-menus of a hidden menu disappear too")
        self.assertIn(self.menu_root.id, visible_alpha)
        self.assertIn(self.menu_child.id, self._visible_ids(self.user_beta))

    def test_group_restriction_hides_menu_for_members(self):
        self._rule(self.menu_child, group=self.group_test)
        self.assertNotIn(self.menu_child.id, self._visible_ids(self.user_alpha))
        self.assertIn(self.menu_child.id, self._visible_ids(self.user_beta))

    def test_root_menu_restriction(self):
        self._rule(self.menu_root, user=self.user_alpha)
        self.assertNotIn(self.menu_root.id, self._visible_ids(self.user_alpha))
        self.assertNotIn(self.menu_root, self.Menu.with_user(self.user_alpha).get_user_roots())
        self.assertIn(self.menu_root, self.Menu.with_user(self.user_beta).get_user_roots())

    def test_system_admin_bypasses_restrictions(self):
        self._rule(self.menu_child, user=self.user_admin)
        self._rule(self.menu_root, group=self.env.ref('base.group_system'))
        visible = self._visible_ids(self.user_admin)
        self.assertIn(self.menu_root.id, visible)
        self.assertIn(self.menu_child.id, visible)

    def test_multi_company_scope(self):
        self._rule(self.menu_child, user=self.user_gamma, company=self.company_a)
        self.assertIn(self.menu_child.id, self._visible_ids(self.user_gamma),
                      "a rule in company A must not affect a user who only works in company B")
        self._rule(self.menu_child, user=self.user_gamma, company=self.company_b)
        self.assertNotIn(self.menu_child.id, self._visible_ids(self.user_gamma))

    def test_constraints(self):
        with self.assertRaises(ValidationError):
            self._rule(self.menu_child, user=self.user_alpha, group=self.group_test)
        with self.assertRaises(ValidationError):
            self._rule(self.menu_child)
        self._rule(self.menu_child, user=self.user_alpha)
        with self.assertRaises(ValidationError):
            self._rule(self.menu_child, user=self.user_alpha)
        self._rule(self.menu_child, group=self.group_test)
        with self.assertRaises(ValidationError):
            self._rule(self.menu_child, group=self.group_test)
        # same menu and user in another company is a different rule
        self._rule(self.menu_child, user=self.user_alpha, company=self.company_b)

    def test_counts_and_display_name(self):
        rule = self._rule(self.menu_child, user=self.user_alpha)
        self._rule(self.menu_grandchild, user=self.user_alpha)
        self._rule(self.menu_child, group=self.group_test)
        self.assertEqual(self.user_alpha.ydod_menu_access_count, 2)
        self.assertEqual(self.menu_child.ydod_menu_access_count, 2)
        self.assertEqual(self.menu_grandchild.ydod_menu_access_count, 1)
        self.assertIn('YDoD Test Child', rule.display_name)
        self.assertIn('Alpha', rule.display_name)

    def test_copy_wizard(self):
        self._rule(self.menu_child, user=self.user_alpha)
        self._rule(self.menu_grandchild, user=self.user_alpha)
        self._rule(self.menu_grandchild, user=self.user_beta)
        self._rule(self.menu_root, user=self.user_beta)
        wizard = self.env['ydod.menu.access.copy'].create({
            'source_user_id': self.user_alpha.id,
            'target_user_ids': [Command.set([self.user_beta.id, self.user_gamma.id])],
        })
        self.assertEqual(wizard.source_menu_access_count, 2)
        wizard.action_copy()
        self.assertEqual(self.user_beta.ydod_menu_access_ids.menu_id,
                         self.menu_root + self.menu_child + self.menu_grandchild)
        self.assertEqual(self.user_gamma.ydod_menu_access_ids.menu_id, self.menu_child + self.menu_grandchild)
        self.assertEqual(self.user_alpha.ydod_menu_access_count, 2)
        wizard_overwrite = self.env['ydod.menu.access.copy'].create({
            'source_user_id': self.user_alpha.id,
            'target_user_ids': [Command.set([self.user_beta.id])],
            'overwrite': True,
        })
        wizard_overwrite.action_copy()
        self.assertEqual(self.user_beta.ydod_menu_access_ids.menu_id, self.menu_child + self.menu_grandchild)
        with self.assertRaises(UserError):
            self.env['ydod.menu.access.copy'].create({
                'source_user_id': self.user_manager.id,
                'target_user_ids': [Command.set([self.user_beta.id])],
            }).action_copy()

    def test_cascade_to_sub_menus(self):
        with self.assertRaises(UserError):
            self.menu_root.action_ydod_cascade_restrictions()
        self._rule(self.menu_root, user=self.user_alpha)
        self._rule(self.menu_root, group=self.group_test)
        self.menu_root.action_ydod_cascade_restrictions()
        for menu in self.menu_child + self.menu_grandchild:
            rules = menu.ydod_menu_access_ids
            self.assertEqual(len(rules), 2)
            self.assertTrue(all(rules.mapped('cascade')))
            self.assertEqual(rules.user_id, self.user_alpha)
            self.assertEqual(rules.group_id, self.group_test)
        self.menu_root.action_ydod_cascade_restrictions()
        self.assertEqual(self.menu_grandchild.ydod_menu_access_count, 2, "cascade never duplicates rules")
        self.assertEqual(self.menu_root.ydod_menu_access_count, 2)

    def test_access_rights(self):
        rule_a = self._rule(self.menu_child, user=self.user_beta, company=self.company_a)
        rule_b = self._rule(self.menu_child, user=self.user_gamma, company=self.company_b)
        Manager = self.Access.with_user(self.user_manager)
        found = Manager.search([('menu_id', '=', self.menu_child.id)])
        self.assertIn(rule_a, found)
        self.assertNotIn(rule_b, found)
        own = Manager.create({
            'menu_id': self.menu_grandchild.id, 'user_id': self.user_alpha.id, 'company_id': self.company_a.id})
        own.write({'menu_id': self.menu_root.id})
        own.unlink()
        with self.assertRaises(AccessError):
            Manager.create({
                'menu_id': self.menu_grandchild.id, 'user_id': self.user_gamma.id, 'company_id': self.company_b.id})
        with self.assertRaises(AccessError):
            Manager.browse(rule_b.id).read(['menu_id'])
        with self.assertRaises(AccessError):
            self.Access.with_user(self.user_alpha).search([])
        with self.assertRaises(AccessError):
            self.Access.with_user(self.user_alpha).create({
                'menu_id': self.menu_root.id, 'user_id': self.user_beta.id, 'company_id': self.company_a.id})
        Admin = self.Access.with_user(self.user_admin)
        self.assertEqual(Admin.search([('menu_id', '=', self.menu_child.id)]), rule_a + rule_b)
        admin_rule = Admin.create({
            'menu_id': self.menu_root.id, 'user_id': self.user_gamma.id, 'company_id': self.company_b.id})
        admin_rule.unlink()
