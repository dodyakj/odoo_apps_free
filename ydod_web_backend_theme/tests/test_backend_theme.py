from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.res_config_settings import PARAM_PREFIX, SCSS_PATH, SCSS_URL


@tagged('post_install', '-at_install')
class TestBackendTheme(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref('base.group_user')
        cls.user, cls.other_user = cls.env['res.users'].create([{
            'name': f'yDoD Theme User {index}',
            'login': f'ydod_theme_user_{index}',
            'password': f'ydod_theme_user_{index}_pwd',
            'group_ids': [Command.set(group_user.ids)],
        } for index in (1, 2)])

    def setUp(self):
        super().setUp()
        self.env['res.config.settings']._ydod_remove_theme()

    def _attachments(self):
        return self.env['ir.attachment'].search([('url', '=', SCSS_URL)])

    def _assets(self):
        return self.env['ir.asset'].search([('path', '=', SCSS_URL)])

    def _save(self, **values):
        settings = self.env['res.config.settings'].create(values)
        settings.set_values()
        return settings

    def test_brand_color_generates_asset(self):
        self._save(ydod_color_brand='#112233')
        attachment = self._attachments()
        self.assertEqual(len(attachment), 1)
        self.assertEqual(attachment.mimetype, 'text/scss')
        self.assertTrue(attachment.public)
        self.assertIn('$o-brand-odoo: #112233;', attachment.raw.content.decode())
        asset = self._assets()
        self.assertEqual(len(asset), 1)
        self.assertEqual(asset.directive, 'replace')
        self.assertEqual(asset.target, SCSS_PATH)
        self.assertEqual(asset.bundle, 'web._assets_primary_variables')

    def test_unchanged_colors_do_not_rewrite(self):
        self._save(ydod_color_brand='#112233')
        write_date = self._attachments().write_date
        settings_class = self.env.registry['res.config.settings']
        with patch.object(settings_class, '_ydod_write_scss', autospec=True) as write_scss:
            self._save(ydod_color_brand='#112233')
        write_scss.assert_not_called()
        self.assertEqual(self._attachments().write_date, write_date)

        self._save(ydod_color_primary='#00aa55')
        attachment = self._attachments()
        self.assertEqual(len(attachment), 1)
        content = attachment.raw.content.decode()
        self.assertIn('$o-brand-odoo: #112233;', content)
        self.assertIn('$o-brand-primary: #00aa55;', content)
        self.assertEqual(len(self._assets()), 1)

    def test_invalid_colors(self):
        with self.assertRaises(ValidationError):
            self.env['res.config.settings'].create({'ydod_color_primary': 'red'})
        company = self.env['res.company'].create({'name': 'yDoD Colour Company'})
        self.assertEqual(company.ydod_background_color, '#714B67')
        with self.assertRaises(ValidationError):
            company.write({'ydod_background_color': 'red'})

    def test_reset_theme(self):
        settings = self._save(ydod_color_brand='#112233', ydod_appbar_bg='#000000')
        self.assertTrue(self._attachments())
        result = settings.action_ydod_reset_theme()
        self.assertEqual(result, {'type': 'ir.actions.client', 'tag': 'reload'})
        self.assertFalse(self._attachments())
        self.assertFalse(self._assets())
        params = self.env['ir.config_parameter'].search([('key', '=like', PARAM_PREFIX + '%')])
        self.assertFalse(params)

    def test_settings_access(self):
        Settings = self.env['res.config.settings'].with_user(self.user)
        with self.assertRaises(AccessError):
            Settings.create({'ydod_color_brand': '#112233'})
        with self.assertRaises(AccessError):
            Settings.action_ydod_reset_theme()

    def test_user_app_bar_mode(self):
        self.assertEqual(self.user.ydod_app_bar_mode, 'expanded')
        self.user.with_user(self.user).write({'ydod_app_bar_mode': 'icons'})
        self.assertEqual(self.user.ydod_app_bar_mode, 'icons')
        with self.assertRaises(AccessError):
            self.other_user.with_user(self.user).write({'ydod_app_bar_mode': 'hidden'})
        values = self.user.with_user(self.user)._ydod_session_values()
        self.assertEqual(values['ydod_app_bar_mode'], 'icons')
        self.assertEqual(values['ydod_app_order'], [])
        self.assertIn('ydod_has_background', values)

    def test_app_order_filters_ids(self):
        action = self.env.ref('base.action_res_users')
        Menu = self.env['ir.ui.menu']
        root = Menu.create({'name': 'yDoD Root App', 'action': f'{action._name},{action.id}'})
        child = Menu.create({
            'name': 'yDoD Child Menu',
            'parent_id': root.id,
            'action': f'{action._name},{action.id}',
        })
        order = self.env['res.users'].with_user(self.user).ydod_set_app_order(
            [root.id, 999999, child.id, root.id, 'x'])
        self.assertEqual(order, [root.id])
        self.assertEqual(self.user.ydod_app_order, [root.id])
        self.assertEqual(self.env['res.users'].with_user(self.user).ydod_set_app_order('bad'), [])
