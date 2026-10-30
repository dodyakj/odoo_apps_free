from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.ydod_web_debrand_oem_tweaks.models.ir_http import PARAM_PREFIX, TWEAK_DEFAULTS


@tagged('post_install', '-at_install')
class TestWhiteLabelTweaks(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env['ir.config_parameter'].sudo()
        cls.ICP.search([('key', '=like', PARAM_PREFIX + '%')]).unlink()
        cls.user = new_test_user(cls.env, login='ydod_internal_user', groups='base.group_user')
        cls.admin = new_test_user(
            cls.env, login='ydod_admin_user', groups='base.group_user,base.group_system')
        cls.IrHttp = cls.env['ir.http']

    def _set(self, key, value):
        self.ICP.set_str(PARAM_PREFIX + key, value)

    def test_settings_store(self):
        settings = self.env['res.config.settings'].with_user(self.admin).create({
            'ydod_system_name': 'Acme ERP',
            'ydod_ribbon_text': 'STAGING',
            'ydod_ribbon_color': '#F0AD4E',
            'ydod_menu_support_label': 'Acme Helpdesk',
            'ydod_menu_support_url': 'https://acme.example/helpdesk',
            'ydod_menu_account_hide': True,
            'ydod_debug_guard': True,
        })
        settings.execute()
        self.assertEqual(self.ICP.get_str(PARAM_PREFIX + 'ydod_system_name'), 'Acme ERP')
        self.assertEqual(self.ICP.get_str(PARAM_PREFIX + 'ydod_ribbon_text'), 'STAGING')
        self.assertEqual(self.ICP.get_str(PARAM_PREFIX + 'ydod_ribbon_color'), '#F0AD4E')
        self.assertEqual(self.ICP.get_str(PARAM_PREFIX + 'ydod_menu_support_label'), 'Acme Helpdesk')
        self.assertEqual(
            self.ICP.get_str(PARAM_PREFIX + 'ydod_menu_support_url'), 'https://acme.example/helpdesk')
        self.assertEqual(self.ICP.get_str(PARAM_PREFIX + 'ydod_menu_account_hide'), 'True')
        self.assertEqual(self.ICP.get_str(PARAM_PREFIX + 'ydod_debug_guard'), 'True')

    def test_get_tweaks(self):
        self._set('ydod_system_name', 'Acme ERP')
        self._set('ydod_menu_shortcuts_hide', 'True')
        self._set('ydod_chat_draggable', 'True')
        self._set('ydod_ribbon_text', 'TEST')
        self._set('ydod_unknown_key', 'ignored')
        expected = dict(TWEAK_DEFAULTS)
        expected.update({
            'ydod_system_name': 'Acme ERP',
            'ydod_menu_shortcuts_hide': True,
            'ydod_chat_draggable': True,
            'ydod_ribbon_text': 'TEST',
        })
        tweaks = self.IrHttp._ydod_get_tweaks()
        self.assertEqual(tweaks, expected)
        self.assertIs(tweaks['ydod_dialog_draggable'], False)
        self.assertNotIn('web.base.url', tweaks)
        self.assertNotIn('ydod_unknown_key', tweaks)

    def test_url_constraint(self):
        Settings = self.env['res.config.settings']
        with self.assertRaises(ValidationError):
            Settings.create({'ydod_menu_support_url': 'javascript:alert(1)'})
        with self.assertRaises(ValidationError):
            Settings.create({'ydod_menu_about_url': '//evil.example'})
        Settings.create({'ydod_menu_support_url': '/odoo/help'})
        Settings.create({'ydod_menu_documentation_url': 'https://acme.example'})

    def test_color_constraint(self):
        Settings = self.env['res.config.settings']
        with self.assertRaises(ValidationError):
            Settings.create({'ydod_ribbon_color': 'red'})
        settings = Settings.create({'ydod_ribbon_color': '#00AA55'})
        self.assertEqual(settings.ydod_ribbon_color, '#00AA55')

    def test_replace_requires_text(self):
        Settings = self.env['res.config.settings']
        with self.assertRaises(ValidationError):
            Settings.create({'ydod_login_footer_mode': 'replace', 'ydod_login_footer_text': False})
        Settings.create({'ydod_login_footer_mode': 'replace', 'ydod_login_footer_text': 'Powered by Acme'})

    def test_debug_guard(self):
        self._set('ydod_debug_guard', 'True')
        self.assertFalse(self.IrHttp._ydod_debug_allowed(self.user))
        self.assertTrue(self.IrHttp._ydod_debug_allowed(self.admin))
        self._set('ydod_debug_guard', False)
        self.assertTrue(self.IrHttp._ydod_debug_allowed(self.user))
        self.assertTrue(self.IrHttp._ydod_debug_allowed(self.admin))

    def test_access_user(self):
        with self.assertRaises(AccessError):
            self.env['res.config.settings'].with_user(self.user).create({'ydod_system_name': 'Hacked'})
        settings = self.env['res.config.settings'].create({'ydod_system_name': 'Hacked'})
        with self.assertRaises(AccessError):
            settings.with_user(self.user).execute()
        self.assertFalse(self.ICP.get_str(PARAM_PREFIX + 'ydod_system_name'))

    def test_login_branding_edge(self):
        self.assertEqual(self.IrHttp._ydod_login_branding(), {'mode': 'standard', 'text': '', 'url': ''})
        self._set('ydod_login_footer_mode', 'hide')
        self._set('ydod_login_footer_text', 'Powered by Acme')
        self.assertEqual(self.IrHttp._ydod_login_branding(), {'mode': 'hide', 'text': '', 'url': ''})
        self._set('ydod_login_footer_mode', 'replace')
        self._set('ydod_login_footer_url', 'https://acme.example')
        self.assertEqual(
            self.IrHttp._ydod_login_branding(),
            {'mode': 'replace', 'text': 'Powered by Acme', 'url': 'https://acme.example'})
        self._set('ydod_login_footer_url', 'javascript:alert(1)')
        self.assertEqual(self.IrHttp._ydod_login_branding()['url'], '')
