from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestMcpModels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ydod.mcp.model'].with_context(active_test=False).search([]).unlink()
        cls.country_model = cls.env['ir.model']._get('res.country')
        cls.partner_model = cls.env['ir.model']._get('res.partner')
        cls.user = new_test_user(cls.env, login='mcp_model_user', groups='base.group_user')
        cls.admin = new_test_user(cls.env, login='mcp_model_admin', groups='base.group_system')
        cls.Log = cls.env['ydod.mcp.log']

    def _log(self, **vals):
        return self.Log.create(dict({'jsonrpc_method': 'tools/call', 'status': 'success'}, **vals))

    def test_method_names_constraint(self):
        Allow = self.env['ydod.mcp.model']
        for bad in ('_private', 'unlink', 'does_not_exist', 'name'):
            with self.assertRaises(ValidationError):
                Allow.create({'model_id': self.partner_model.id, 'mode': 'readwrite', 'method_names': bad})
        entry = Allow.create({'model_id': self.partner_model.id, 'mode': 'readwrite',
                              'method_names': 'action_archive, action_unarchive'})
        self.assertEqual(entry.model_name, 'res.partner')

    def test_unique_and_limits(self):
        Allow = self.env['ydod.mcp.model']
        Allow.create({'model_id': self.country_model.id})
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            Allow.create({'model_id': self.country_model.id})
        with self.assertRaises(ValidationError):
            Allow.create({'model_id': self.partner_model.id, 'row_limit': -1})

    def test_field_belongs_to_model(self):
        foreign = self.env['ir.model.fields']._get('res.country', 'code')
        with self.assertRaises(ValidationError):
            self.env['ydod.mcp.model'].create({'model_id': self.partner_model.id, 'field_ids': [foreign.id]})

    def test_display_name_and_log_count(self):
        entry = self.env['ydod.mcp.model'].create({'model_id': self.country_model.id, 'mode': 'read'})
        self.assertIn('Read-only', entry.display_name)
        self._log(model_name='res.country')
        self._log(model_name='res.country', status='error')
        self._log(model_name='res.partner')
        entry.invalidate_recordset(['log_count'])
        self.assertEqual(entry.log_count, 2)
        action = entry.action_view_logs()
        self.assertEqual(action['domain'], [('model_name', '=', 'res.country')])

    def test_log_immutable_and_purge(self):
        icp = self.env['ir.config_parameter'].sudo()
        old = self._log(date=fields.Datetime.now() - timedelta(days=10))
        recent = self._log(date=fields.Datetime.now() - timedelta(days=1))
        with self.assertRaises(UserError):
            recent.write({'status': 'error'})
        icp.set_param('ydod_mcp_server.log_retention_days', 0)
        self.Log._cron_purge()
        self.assertTrue(old.exists())
        icp.set_param('ydod_mcp_server.log_retention_days', 5)
        self.Log._cron_purge()
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_access_rights(self):
        own = self._log(user_id=self.user.id)
        other = self._log(user_id=self.admin.id)
        with self.assertRaises(AccessError):
            self.env['ydod.mcp.model'].with_user(self.user).search([])
        visible = self.Log.with_user(self.user).search([('id', 'in', (own | other).ids)])
        self.assertEqual(visible, own)
        with self.assertRaises(AccessError):
            own.with_user(self.user).unlink()
        entry = self.env['ydod.mcp.model'].with_user(self.admin).create({'model_id': self.country_model.id})
        entry.with_user(self.admin).write({'mode': 'readwrite'})
        self.assertEqual(self.Log.with_user(self.admin).search([('id', 'in', (own | other).ids)]), own | other)
        other.with_user(self.admin).unlink()
        self.assertFalse(other.exists())

    def test_settings(self):
        settings = self.env['res.config.settings'].create({})
        self.assertTrue(settings.ydod_mcp_endpoint_url.endswith('/mcp'))
        self.assertIn('mcp-remote', settings.ydod_mcp_client_snippet)
        self.assertIn('claude mcp add --transport http', settings.ydod_mcp_client_snippet)
        settings.ydod_mcp_rate_limit = -1
        with self.assertRaises(ValidationError):
            settings.set_values()
        settings.ydod_mcp_rate_limit = 5
        settings.set_values()
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param('ydod_mcp_server.rate_limit'), '5')
