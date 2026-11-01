from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

from odoo.addons.ydod_global_search import _ydod_create_default_configs

PARAM = 'ydod_global_search.'


@tagged('post_install', '-at_install')
class TestGlobalSearch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['ydod.global.search.model']
        cls.Config.with_context(active_test=False).search([]).unlink()
        cls.icp = cls.env['ir.config_parameter'].sudo()
        cls.icp.set_bool(PARAM + 'enabled', True)
        cls.icp.set_int(PARAM + 'min_chars', 2)
        cls.icp.set_int(PARAM + 'total_limit', 50)
        cls.icp.set_int(PARAM + 'model_limit', 8)
        cls.user = new_test_user(cls.env, login='ydod_gs_user', groups='base.group_user')
        cls.admin = new_test_user(cls.env, login='ydod_gs_admin', groups='base.group_user,base.group_system')

    def _config(self, model, lines, **vals):
        fields_model = self.env['ir.model.fields']
        return self.Config.create(dict({
            'name': model,
            'model_id': self.env['ir.model']._get(model).id,
            'field_ids': [
                Command.create(dict({'field_id': fields_model._get(model, fname).id}, **opts))
                for fname, opts in lines
            ],
        }, **vals))

    def _group(self, results, model):
        return next((group for group in results if group['model'] == model), None)

    def test_default_configs(self):
        _ydod_create_default_configs(self.env)
        config = self.Config.search([('model_name', '=', 'res.partner')])
        self.assertEqual(len(config), 1)
        self.assertTrue(config.active)
        self.assertTrue(config.field_ids.filtered(lambda line: line.full_path == 'name' and line.use_search))
        self.assertGreaterEqual(config.field_count, 5)
        _ydod_create_default_configs(self.env)
        self.assertEqual(self.Config.search_count([('model_name', '=', 'res.partner')]), 1)

    def test_search_grouping_and_rank(self):
        self._config('res.partner', [
            ('name', {'weight': 20}),
            ('email', {'weight': 5, 'use_display': True}),
        ], name='Contacts')
        self.env['res.partner'].create([
            {'name': 'Other', 'email': 'zyx@ex.com'},
            {'name': 'Zyx Alpha'},
        ])
        group = self._group(self.Config.ydod_search('zyx'), 'res.partner')
        self.assertEqual(group['name'], 'Contacts')
        self.assertEqual([r['name'] for r in group['records']], ['Zyx Alpha', 'Other'])
        self.assertEqual([r['score'] for r in group['records']], [20, 5])
        other = group['records'][1]
        self.assertEqual(other['values'][0]['value'], 'zyx@ex.com')

    def test_relational_path(self):
        config = self._config('res.partner', [
            ('name', {'weight': 10}),
            ('parent_id', {'path': 'name', 'weight': 5, 'use_display': True}),
        ])
        self.assertEqual(config.field_ids[1].full_path, 'parent_id.name')
        parent = self.env['res.partner'].create({'name': 'Qwerty Corp', 'is_company': True})
        child = self.env['res.partner'].create({'name': 'Jane Child', 'parent_id': parent.id})
        group = self._group(self.Config.ydod_search('qwerty'), 'res.partner')
        row = next(r for r in group['records'] if r['id'] == child.id)
        self.assertEqual(row['score'], 5)
        self.assertEqual(row['values'][0]['value'], parent.display_name)

    def test_constraints(self):
        config = self._config('res.partner', [('name', {})])
        Line = self.env['ydod.global.search.field']
        name_field = self.env['ir.model.fields']._get('res.partner', 'name')
        parent_field = self.env['ir.model.fields']._get('res.partner', 'parent_id')
        with self.assertRaises(ValidationError):
            Line.create({'search_model_id': config.id, 'field_id': name_field.id, 'path': 'foo'})
        with self.assertRaises(ValidationError):
            Line.create({'search_model_id': config.id, 'field_id': parent_field.id, 'path': 'email.foo'})
        with self.assertRaises(ValidationError):
            Line.create({'search_model_id': config.id, 'field_id': parent_field.id, 'path': 'no_such_field'})
        with self.assertRaises(ValidationError):
            Line.create({'search_model_id': config.id, 'field_id': name_field.id,
                         'use_search': False, 'use_display': False})
        with self.assertRaises(ValidationError):
            Line.create({'search_model_id': config.id,
                         'field_id': self.env['ir.model.fields']._get('res.country', 'name').id})
        with self.assertRaises(ValidationError):
            config.extra_domain = 'not a list'
        with self.assertRaises(ValidationError):
            self._config('res.country', [('name', {'use_search': False, 'use_display': True})])

    def test_constraint_negative_weight(self):
        config = self._config('res.partner', [('name', {})])
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception), self.cr.savepoint():
            config.field_ids.weight = -1
            self.env.flush_all()

    def test_constraint_duplicate_model(self):
        self._config('res.partner', [('name', {})])
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception), self.cr.savepoint():
            self._config('res.partner', [('email', {})])
            self.env.flush_all()

    def test_limits_and_min_chars(self):
        self._config('res.partner', [('name', {})], sequence=10)
        self._config('res.partner.category', [('name', {})], sequence=20)
        self.env['res.partner'].create([{'name': f'Limitx Person {i}'} for i in range(5)])
        self.env['res.partner.category'].create([{'name': f'Limitx Tag {i}'} for i in range(3)])
        self.icp.set_int(PARAM + 'min_chars', 3)
        self.assertEqual(self.Config.ydod_search('ab'), [])
        self.icp.set_int(PARAM + 'model_limit', 2)
        group = self._group(self.Config.ydod_search('limitx'), 'res.partner')
        self.assertEqual(len(group['records']), 2)
        self.icp.set_int(PARAM + 'model_limit', 10)
        self.icp.set_int(PARAM + 'total_limit', 6)
        results = self.Config.ydod_search('limitx')
        self.assertEqual(sum(len(g['records']) for g in results), 6)
        self.assertEqual(len(self._group(results, 'res.partner.category')['records']), 1)
        self.icp.set_bool(PARAM + 'enabled', False)
        self.assertEqual(self.Config.ydod_search('limitx'), [])

    def test_access_user(self):
        self._config('res.partner', [('name', {})])
        self._config('ir.config_parameter', [('key', {})])
        self.env['res.partner'].create([
            # is_company is computed in 20.0: own commercial entity with a VAT
            {'name': 'Rstr Corp', 'vat': 'BE0477472701'},
            {'name': 'Rstr Person'},
        ])
        self.env['ir.access'].create({
            'name': 'test: companies only',
            'model_id': self.env['ir.model']._get('res.partner').id,
            'operation': 'r',
            'domain': "[('is_company', '=', True)]",
        })
        Config = self.Config.with_user(self.user)
        group = self._group(Config.ydod_search('rstr'), 'res.partner')
        self.assertEqual([r['name'] for r in group['records']], ['Rstr Corp'])
        self.assertIsNone(self._group(Config.ydod_search('ydod_global'), 'ir.config_parameter'))
        self.assertTrue(self._group(self.Config.ydod_search('ydod_global'), 'ir.config_parameter'))

    def test_multi_company(self):
        self._config('res.partner', [('name', {})])
        company_a = self.env.company
        company_b = self.env['res.company'].create({'name': 'Ydod Company B'})
        self.env['res.partner'].create([
            {'name': 'Mcomp Remote', 'company_id': company_b.id},
            {'name': 'Mcomp Local', 'company_id': company_a.id},
        ])
        user = new_test_user(self.env, login='ydod_gs_mc', groups='base.group_user',
                             company_id=company_a.id, company_ids=[Command.set(company_a.ids)])
        Config = self.Config.with_user(user).with_context(allowed_company_ids=company_a.ids)
        names = [r['name'] for r in self._group(Config.ydod_search('mcomp'), 'res.partner')['records']]
        self.assertIn('Mcomp Local', names)
        self.assertNotIn('Mcomp Remote', names)

    def test_acl_config(self):
        config = self._config('res.partner', [('name', {})])
        as_user = self.Config.with_user(self.user)
        self.assertEqual(as_user.search([('id', '=', config.id)]).name, 'res.partner')
        with self.assertRaises(AccessError):
            config.with_user(self.user).write({'name': 'Hacked'})
        with self.assertRaises(AccessError):
            config.field_ids.with_user(self.user).write({'weight': 1})
        with self.assertRaises(AccessError):
            as_user.create({'name': 'Tags', 'model_id': self.env['ir.model']._get('res.partner.category').id})
        with self.assertRaises(AccessError):
            config.with_user(self.user).unlink()
        as_admin = config.with_user(self.admin)
        as_admin.write({'name': 'Contacts'})
        self.assertEqual(config.name, 'Contacts')
        tags = self._config('res.partner.category', [('name', {})]).with_user(self.admin)
        tags.unlink()
        self.assertEqual(as_user.ydod_search(''), [])
        action = as_user.ydod_get_action(config.id, 'acl')
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'res.partner')
        self.assertIn(('name', 'ilike', 'acl'), action['domain'])
        new_cfg = self.Config.with_user(self.admin).create({
            'name': 'Countries',
            'model_id': self.env['ir.model']._get('res.country').id,
            'field_ids': [Command.create({'field_id': self.env['ir.model.fields']._get('res.country', 'name').id})],
        })
        self.assertEqual(new_cfg.field_count, 1)
