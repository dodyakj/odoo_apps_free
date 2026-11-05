from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

PARAM = "ydod_web_x2many_line_search.enabled"


@tagged("post_install", "-at_install")
class TestLineSearchSetting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.admin = cls.env.ref("base.user_admin")
        cls.basic_user = cls.env["res.users"].create({
            "name": "Line Search Basic User",
            "login": "line_search_basic_user",
            "groups_id": [Command.set([cls.env.ref("base.group_user").id])],
        })

    def _enabled_param(self):
        return self.ICP.get_param(PARAM, "False") == "True"

    def _set_enabled(self, value):
        settings = self.env["res.config.settings"].with_user(self.admin).create({
            "x2many_line_search_enabled": value,
        })
        settings.execute()

    def test_enabled_after_install(self):
        self.assertEqual(self.ICP.get_param(PARAM), "True")
        self.assertTrue(self.env["ir.http"]._x2many_line_search_enabled())

    def test_settings_default_value(self):
        settings = self.env["res.config.settings"].with_user(self.admin).create({})
        self.assertTrue(settings.x2many_line_search_enabled)

    def test_admin_can_switch_off_and_on(self):
        self._set_enabled(False)
        self.assertFalse(self._enabled_param())
        self.assertFalse(self.env["ir.http"]._x2many_line_search_enabled())
        self.assertIs(self.env["ir.http"].with_user(self.admin)._x2many_line_search_enabled(), False)
        self._set_enabled(True)
        self.assertTrue(self._enabled_param())
        self.assertTrue(self.env["ir.http"]._x2many_line_search_enabled())

    def test_basic_user_cannot_change_setting(self):
        with self.assertRaises(AccessError):
            self.env["res.config.settings"].with_user(self.basic_user).create({
                "x2many_line_search_enabled": False,
            })
        self.assertTrue(self._enabled_param())

    def test_setting_in_general_settings_form(self):
        arch = self.env["res.config.settings"].with_user(self.admin).get_view(view_type="form")["arch"]
        self.assertIn('name="x2many_line_search_enabled"', arch)
        self.assertIn('id="ydod_x2many_line_search"', arch)

    def test_basic_user_reads_flag(self):
        enabled = self.env["ir.http"].with_user(self.basic_user)._x2many_line_search_enabled()
        self.assertTrue(enabled)
        self.assertTrue(self.basic_user._is_internal())
