"""Tests for ydod_api_false_to_null module."""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestApiFalseToNull(TransactionCase):
    """Test False-to-None conversion in API responses."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env['res.partner']
        # Create test partner with various field types
        cls.partner = cls.partner_model.create({
            'name': 'Test Partner',
            'email': 'test@example.com',
            'phone': False,  # Char field, empty
            'comment': False,  # HTML field, empty
            'parent_id': False,  # Many2one, empty
            'is_company': False,  # Boolean, explicit False
            'active': True,  # Boolean, explicit True
            'tz': False,  # Selection, empty
        })
        # Create child partner for One2many test
        cls.child_partner = cls.partner_model.create({
            'name': 'Child Partner',
            'parent_id': cls.partner.id,
            'email': False,
            'phone': False,
        })
        cls.regular_user = cls.env['res.users'].create({
            'name': 'API False to NULL Test User',
            'login': 'ydod_api_false_to_null_test_user',
        })
        cls.regular_user.write({
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(
            'ydod_api_false_to_null.enabled', 'False'
        )

    def _call_read(self, model, ids, fields=None, context=None):
        """Helper to call read with optional context."""
        if context:
            model = model.with_context(context)
        return model.browse(ids).read(fields or [])

    def _call_search_read(self, model, domain, fields=None, context=None):
        """Helper to call search_read with optional context."""
        if context:
            model = model.with_context(context)
        return model.search_read(domain, fields or [])

    def _call_web_read(self, model, ids, fields=None, context=None):
        """Helper to call web_read with optional context."""
        if context:
            model = model.with_context(context)
        specification = {field: {} for field in (fields or [])}
        return model.browse(ids).web_read(specification)

    # --- Context-based activation tests ---

    def test_read_context_enabled_converts_non_boolean_false_to_none(self):
        """Empty Char, HTML, Many2one, and Selection become None; Boolean stays False."""
        ctx = {'api_false_to_null': True}
        result = self._call_read(self.partner_model, [self.partner.id], context=ctx)
        self.assertEqual(len(result), 1)
        rec = result[0]
        # Non-Boolean fields with False -> None
        self.assertIsNone(rec.get('phone'))
        self.assertIsNone(rec.get('comment'))
        self.assertIsNone(rec.get('parent_id'))
        self.assertIsNone(rec.get('tz'))
        # Boolean fields preserve False/True
        self.assertIs(rec.get('is_company'), False)
        self.assertIs(rec.get('active'), True)
        # Populated fields unchanged
        self.assertEqual(rec.get('name'), 'Test Partner')
        self.assertEqual(rec.get('email'), 'test@example.com')

    def test_search_read_context_enabled_converts_requested_fields(self):
        """search_read converts empty fields while preserving x2many IDs."""
        ctx = {'api_false_to_null': True}
        result = self._call_search_read(
            self.partner_model,
            [('id', '=', self.partner.id)],
            ['name', 'phone', 'child_ids'],
            context=ctx
        )
        self.assertEqual(len(result), 1)
        parent = result[0]
        self.assertIsNone(parent.get('phone'))  # parent's empty Char
        # Classic search_read returns related record IDs, not nested records.
        self.assertEqual(parent.get('child_ids'), [self.child_partner.id])

    def test_web_read_context_enabled_works(self):
        """web_read() (used by web client) also converts when context set."""
        ctx = {'api_false_to_null': True}
        result = self._call_web_read(self.partner_model, [self.partner.id], ['phone', 'is_company'], context=ctx)
        self.assertEqual(len(result), 1)
        rec = result[0]
        self.assertIsNone(rec.get('phone'))
        self.assertIs(rec.get('is_company'), False)

    def test_web_read_without_context_preserves_false(self):
        """web_read() retains standard values when conversion is not enabled."""
        result = self._call_web_read(
            self.partner_model, [self.partner.id], ['phone', 'is_company']
        )
        self.assertIs(result[0].get('phone'), False)
        self.assertIs(result[0].get('is_company'), False)

    def test_web_read_converts_empty_nested_many2one_safely(self):
        """Conversion happens after web_read has finished resolving relations."""
        result = self.partner_model.with_context(api_false_to_null=True).browse(
            self.partner.id
        ).web_read({
            'parent_id': {'fields': {'name': {}}},
        })
        self.assertIsNone(result[0]['parent_id'])

    def test_web_read_recurses_into_one2many_records(self):
        """web_read converts empty fields on related records recursively."""
        result = self.partner_model.with_context(api_false_to_null=True).browse(
            self.partner.id
        ).web_read({
            'child_ids': {
                'fields': {
                    'name': {},
                    'email': {},
                    'phone': {},
                    'is_company': {},
                },
            },
        })
        child = result[0]['child_ids'][0]
        self.assertEqual(child['name'], 'Child Partner')
        self.assertIsNone(child['email'])
        self.assertIsNone(child['phone'])
        self.assertIs(child['is_company'], False)

    def test_context_false_disables_even_if_global_true(self):
        """Context key False overrides global parameter True."""
        # Set global parameter
        self.env['ir.config_parameter'].sudo().set_param('ydod_api_false_to_null.enabled', 'True')
        # But context explicitly False
        ctx = {'api_false_to_null': False}
        result = self._call_read(self.partner_model, [self.partner.id], ['phone', 'is_company'], context=ctx)
        rec = result[0]
        # Should NOT convert because context=False
        self.assertIs(rec.get('phone'), False)
        self.assertIs(rec.get('is_company'), False)

    # --- Global parameter activation tests ---

    def test_global_parameter_enables_conversion_without_context(self):
        """Global ir.config_parameter enables conversion for all requests."""
        self.env['ir.config_parameter'].sudo().set_param('ydod_api_false_to_null.enabled', 'True')
        # No context key
        result = self._call_read(self.partner_model, [self.partner.id], ['phone', 'is_company'])
        rec = result[0]
        self.assertIsNone(rec.get('phone'))
        self.assertIs(rec.get('is_company'), False)

    def test_global_parameter_false_disables_conversion(self):
        """Global parameter False (default) means no conversion without context."""
        self.env['ir.config_parameter'].sudo().set_param('ydod_api_false_to_null.enabled', 'False')
        result = self._call_read(self.partner_model, [self.partner.id], ['phone', 'is_company'])
        rec = result[0]
        self.assertIs(rec.get('phone'), False)
        self.assertIs(rec.get('is_company'), False)

    # --- Boolean field preservation tests ---

    def test_boolean_true_remains_true(self):
        """Boolean field with value True stays True."""
        ctx = {'api_false_to_null': True}
        result = self._call_read(self.partner_model, [self.partner.id], ['active'], context=ctx)
        self.assertIs(result[0].get('active'), True)

    def test_boolean_false_remains_false(self):
        """Boolean field with value False stays False (not converted to None)."""
        ctx = {'api_false_to_null': True}
        result = self._call_read(self.partner_model, [self.partner.id], ['is_company'], context=ctx)
        self.assertIs(result[0].get('is_company'), False)

    # --- Many2one specific tests ---

    def test_many2one_false_becomes_none(self):
        """Empty Many2one (False) becomes None."""
        ctx = {'api_false_to_null': True}
        result = self._call_read(self.partner_model, [self.partner.id], ['parent_id'], context=ctx)
        self.assertIsNone(result[0].get('parent_id'))

    def test_many2one_with_record_stays_dict(self):
        """Many2one with actual record stays as dict with the requested fields."""
        ctx = {'api_false_to_null': True}
        result = self.partner_model.with_context(ctx).browse(
            self.child_partner.id
        ).web_read({
            'parent_id': {'fields': {'name': {}}},
        })
        parent_id = result[0].get('parent_id')
        self.assertIsInstance(parent_id, dict)
        self.assertEqual(parent_id.get('id'), self.partner.id)
        self.assertEqual(parent_id.get('name'), 'Test Partner')

    def test_classic_read_many2one_with_record_preserves_pair(self):
        """Classic read keeps Odoo's standard (id, display_name) value."""
        result = self._call_read(
            self.partner_model,
            [self.child_partner.id],
            ['parent_id'],
            context={'api_false_to_null': True},
        )
        parent_id = result[0]['parent_id']
        self.assertIsInstance(parent_id, tuple)
        self.assertEqual(parent_id[0], self.partner.id)
        self.assertEqual(parent_id[1], 'Test Partner')

    # --- Selection field test ---

    def test_selection_false_becomes_none(self):
        """Empty Selection field (False) becomes None."""
        ctx = {'api_false_to_null': True}
        result = self._call_read(self.partner_model, [self.partner.id], ['tz'], context=ctx)
        self.assertIsNone(result[0].get('tz'))

    # --- Standard web client unaffected test ---

    def test_standard_web_client_unaffected_without_context(self):
        """Standard web client (no context key) receives False for empty fields."""
        # No context, no global parameter
        result = self._call_read(self.partner_model, [self.partner.id], ['phone', 'is_company'])
        rec = result[0]
        self.assertIs(rec.get('phone'), False)
        self.assertIs(rec.get('is_company'), False)

    # --- Edge cases ---

    def test_empty_result_list_returns_empty(self):
        """Empty recordset returns empty list."""
        ctx = {'api_false_to_null': True}
        result = self._call_read(self.partner_model, [], ['name'], context=ctx)
        self.assertEqual(result, [])

    def test_read_without_fields_converts_all_fields(self):
        """read() without fields argument converts all non-Boolean False fields."""
        ctx = {'api_false_to_null': True}
        result = self._call_read(self.partner_model, [self.partner.id], context=ctx)
        rec = result[0]
        # Check a few known non-Boolean fields that are False
        self.assertIsNone(rec.get('phone'))
        self.assertIsNone(rec.get('comment'))
        self.assertIsNone(rec.get('parent_id'))
        # Boolean fields still preserved
        self.assertIs(rec.get('is_company'), False)
        self.assertIs(rec.get('active'), True)

    def test_nested_many2one_in_one2many_converted(self):
        """Nested Many2one inside One2many record also converted."""
        self.partner_model.create({
            'name': 'Grandchild',
            'parent_id': self.child_partner.id,
            'email': False,
        })
        ctx = {'api_false_to_null': True}
        # web_read accepts nested relation specifications; search_read does not
        # accept dotted field names and only returns related IDs.
        result = self.partner_model.with_context(ctx).browse(self.partner.id).web_read({
            'child_ids': {
                'fields': {
                    'name': {},
                    'child_ids': {
                        'fields': {
                            'name': {},
                            'email': {},
                            'parent_id': {'fields': {'name': {}}},
                        },
                    },
                },
            },
        })
        child = result[0]['child_ids'][0]
        grandchildren = child.get('child_ids', [])
        self.assertEqual(len(grandchildren), 1)
        gc = grandchildren[0]
        self.assertIsNone(gc.get('email'))
        # The nested parent_id (Many2one) should be a dict, not converted to None
        self.assertIsInstance(gc.get('parent_id'), dict)
        self.assertEqual(gc['parent_id']['id'], self.child_partner.id)

    def test_conversion_only_when_activated(self):
        """Conversion runs only when context key or global parameter is True."""
        # Default: no conversion
        result = self._call_read(self.partner_model, [self.partner.id], ['phone'])
        self.assertIs(result[0].get('phone'), False)

        # Context True: conversion
        result = self._call_read(self.partner_model, [self.partner.id], ['phone'], context={'api_false_to_null': True})
        self.assertIsNone(result[0].get('phone'))

        # Global True: conversion
        self.env['ir.config_parameter'].sudo().set_param('ydod_api_false_to_null.enabled', 'True')
        result = self._call_read(self.partner_model, [self.partner.id], ['phone'])
        self.assertIsNone(result[0].get('phone'))

        # Global True but context False: no conversion
        result = self._call_read(self.partner_model, [self.partner.id], ['phone'], context={'api_false_to_null': False})
        self.assertIs(result[0].get('phone'), False)

    def test_global_parameter_access_is_limited_to_system_administrators(self):
        """Only users in the System group can manage the global toggle."""
        parameters = self.env['ir.config_parameter'].with_user(self.regular_user)
        with self.assertRaises(AccessError):
            parameters.set_param('ydod_api_false_to_null.enabled', 'True')

        self.env['ir.config_parameter'].with_user(
            self.env.ref('base.user_admin')
        ).set_param('ydod_api_false_to_null.enabled', 'True')
