# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install')
class TestBackendResponsive(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_system = cls.env.ref('base.group_system')

        # Create standard user (internal user without system group)
        cls.standard_user = cls.env['res.users'].create({
            'name': 'Standard Responsive Test User',
            'login': 'standard_test_responsive_user',
            'email': 'standard_test@example.com',
            'group_ids': [(6, 0, [cls.group_user.id])],
            'ydod_chatter_position': 'sided',
        })

        # Create manager user (system administrator)
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Manager Responsive Test User',
            'login': 'manager_test_responsive_user',
            'email': 'manager_test@example.com',
            'group_ids': [(6, 0, [cls.group_user.id, cls.group_system.id])],
            'ydod_chatter_position': 'sided',
        })

    def _set_config(self, key, value):
        icp = self.env['ir.config_parameter'].sudo()
        if hasattr(icp, 'set_str'):
            icp.set_str(key, value)
        else:
            icp.set_param(key, value)

    def _get_config(self, key, default=''):
        icp = self.env['ir.config_parameter'].sudo()
        if hasattr(icp, 'get_str'):
            return icp.get_str(key, default)
        return icp.get_param(key, default)

    def _get_config_bool(self, key, default=True):
        icp = self.env['ir.config_parameter'].sudo()
        if hasattr(icp, 'get_bool'):
            return icp.get_bool(key, default)
        val = icp.get_param(key, str(default))
        return str(val).strip().lower() in ('true', '1')

    def test_default_chatter_position_assignment(self):
        """Verify new users receive the configured default chatter position."""
        # Scenario 1: Default chatter position is 'sided'
        self._set_config('ydod_backend_responsive.default_chatter_position', 'sided')
        new_user_1 = self.env['res.users'].create({
            'name': 'New User Sided',
            'login': 'new_user_sided_unique_login',
            'email': 'new_user_sided@example.com',
        })
        self.assertEqual(
            new_user_1.ydod_chatter_position,
            'sided',
            "New user should receive default 'sided' chatter position",
        )

        # Scenario 2: Change default to 'bottom'
        self._set_config('ydod_backend_responsive.default_chatter_position', 'bottom')
        new_user_2 = self.env['res.users'].create({
            'name': 'New User Bottom',
            'login': 'new_user_bottom_unique_login',
            'email': 'new_user_bottom@example.com',
        })
        self.assertEqual(
            new_user_2.ydod_chatter_position,
            'bottom',
            "New user should receive default 'bottom' chatter position after config update",
        )

        # Revert config parameter back to sided
        self._set_config('ydod_backend_responsive.default_chatter_position', 'sided')

    def test_user_can_update_own_chatter_position(self):
        """Verify standard users can write to their own ydod_chatter_position."""
        # Ensure user starts with 'sided'
        self.standard_user.sudo().write({'ydod_chatter_position': 'sided'})
        self.assertEqual(self.standard_user.ydod_chatter_position, 'sided')

        # Standard user writes to their own preference
        self.standard_user.with_user(self.standard_user).write({
            'ydod_chatter_position': 'bottom'
        })
        self.assertEqual(
            self.standard_user.ydod_chatter_position,
            'bottom',
            "Standard user must be able to update their own chatter position preference",
        )

        # Standard user toggles back to 'sided'
        self.standard_user.with_user(self.standard_user).write({
            'ydod_chatter_position': 'sided'
        })
        self.assertEqual(
            self.standard_user.ydod_chatter_position,
            'sided',
            "Standard user must be able to switch back to sided chatter position",
        )

    def test_manager_config_settings_persistence(self):
        """Verify administrators can update and persist global responsive defaults."""
        settings = self.env['res.config.settings'].with_user(self.manager_user).create({
            'ydod_default_chatter_position': 'bottom',
            'ydod_enable_mobile_bottombar': False,
        })
        settings.execute()

        # Check that configuration parameters were updated
        param_chatter = self._get_config('ydod_backend_responsive.default_chatter_position')
        self.assertEqual(param_chatter, 'bottom')

        param_bottombar = self._get_config_bool('ydod_backend_responsive.enable_mobile_bottombar')
        self.assertFalse(param_bottombar)

        # Reset back for clean state
        settings_reset = self.env['res.config.settings'].with_user(self.manager_user).create({
            'ydod_default_chatter_position': 'sided',
            'ydod_enable_mobile_bottombar': True,
        })
        settings_reset.execute()

    def test_chatter_position_selection_validation(self):
        """Verify setting an invalid selection value raises a ValidationError."""
        with self.assertRaises(ValidationError):
            self.standard_user.sudo().write({
                'ydod_chatter_position': 'invalid_placement'
            })

    def test_user_cannot_modify_global_settings(self):
        """Verify standard internal users cannot execute write on res.config.settings."""
        with self.assertRaises(AccessError):
            self.env['res.config.settings'].with_user(self.standard_user).create({
                'ydod_default_chatter_position': 'bottom',
                'ydod_enable_mobile_bottombar': False,
            }).execute()
