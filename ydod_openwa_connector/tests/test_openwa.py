import hashlib
import hmac
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import SQL

from odoo.addons.ydod_openwa_connector.models.openwa_session import OpenwaSession

PARAM = 'ydod_openwa_connector.'


@tagged('post_install', '-at_install')
class TestOpenwa(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.icp = cls.env['ir.config_parameter'].sudo()
        cls.icp.set_str(PARAM + 'country_code', '62')
        cls.icp.set_str(PARAM + 'webhook_secret', 'top-secret')
        cls.icp.set_bool(PARAM + 'require_opt_in', False)
        cls.company = cls.env.company
        cls.company2 = cls.env['res.company'].create({'name': 'WA Other Company'})
        cls.user = new_test_user(cls.env, login='wa_user', groups='base.group_user,ydod_openwa_connector.group_openwa_user')
        cls.manager = new_test_user(cls.env, login='wa_manager',
                                    groups='base.group_user,ydod_openwa_connector.group_openwa_manager')
        cls.admin = new_test_user(cls.env, login='wa_admin', groups='base.group_user,base.group_system')
        cls.partner = cls.env['res.partner'].create({'name': 'Budi Santoso', 'phone': '0812-3456 789'})
        cls.session = cls.env['openwa.session'].create({
            'name': 'Test Session', 'remote_id': 'test-1', 'status': 'connected',
            'dedicated_number_confirmed': True, 'min_delay_seconds': 0, 'hourly_cap': 50,
        })
        cls.session2 = cls.env['openwa.session'].create({'name': 'Other Session', 'company_id': cls.company2.id})
        cls.Message = cls.env['openwa.message']

    def _log(self, **vals):
        return self.Message.create({'direction': 'out', 'session_id': self.session.id,
                                    'wa_number': '628123456789@c.us', **vals})

    def _sign(self, body):
        return 'sha256=' + hmac.new(b'top-secret', body, hashlib.sha256).hexdigest()

    # ---------------------------------------------------------------- numbers
    def test_normalize(self):
        self.assertEqual(self.Message._openwa_normalize('0812-3456 789'), '628123456789@c.us')
        self.assertEqual(self.Message._openwa_normalize('+62 812 3456789'), '628123456789@c.us')
        self.assertEqual(self.Message._openwa_normalize('012345678', country_code='60'), '6012345678@c.us')
        self.assertEqual(self.partner.whatsapp_number, '628123456789@c.us')
        for bad in ('abc', '123'):
            with self.assertRaises(UserError):
                self.Message._openwa_normalize(bad)

    def test_invalid_phone_no_call(self):
        partner = self.env['res.partner'].create({'name': 'Bad Phone', 'phone': 'abc'})
        self.assertFalse(partner.whatsapp_number)
        with patch.object(OpenwaSession, '_openwa_request') as mock, self.assertRaises(UserError):
            self.Message.send_message(partner, 'Hi', session=self.session)
        mock.assert_not_called()

    # ---------------------------------------------------------------- sending
    def test_send_text(self):
        with patch.object(OpenwaSession, '_openwa_request', return_value={'id': 'MSG1'}) as mock:
            log = self.Message.with_user(self.user).send_message(self.partner, 'Hi there', session=self.session)
        self.assertEqual(log.status, 'sent')
        self.assertEqual(log.openwa_message_id, 'MSG1')
        self.assertEqual(log.user_id, self.user)
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args, ('POST', '/api/messages/send-text'))
        self.assertEqual(mock.call_args.kwargs['json']['chatId'], '628123456789@c.us')
        self.assertTrue(self.partner.message_ids.filtered(lambda m: 'Hi there' in (m.body or '')))
        self.assertEqual(self.partner.openwa_message_count, 1)

    def test_send_media(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'offer.txt', 'raw': b'offer', 'res_model': 'res.partner', 'res_id': self.partner.id})
        with patch.object(OpenwaSession, '_openwa_request', return_value={'data': {'id': 'MSG2'}}) as mock:
            log = self.Message.send_message(self.partner, 'Offer', attachment=attachment, session=self.session)
        self.assertEqual(mock.call_args.args[1], '/api/messages/send-media')
        self.assertEqual(mock.call_args.kwargs['json']['filename'], 'offer.txt')
        self.assertEqual((log.status, log.attachment_name), ('sent', 'offer.txt'))

    def test_safeguards(self):
        self.icp.set_bool(PARAM + 'require_opt_in', True)
        with patch.object(OpenwaSession, '_openwa_request') as mock:
            with self.assertRaises(UserError):
                self.Message.send_message(self.partner, 'Hi', session=self.session)
            mock.assert_not_called()
            self.partner.whatsapp_opt_in = True
            self.assertTrue(self.partner.whatsapp_opt_in_date)
            self.session.dedicated_number_confirmed = False
            self.assertFalse(self.session.is_usable)
            with self.assertRaises(UserError):
                self.Message.send_message(self.partner, 'Hi', session=self.session)
            self.session.write({'dedicated_number_confirmed': True, 'status': 'disconnected'})
            with self.assertRaises(UserError):
                self.Message.send_message(self.partner, 'Hi', session=self.session)
            mock.assert_not_called()

    def test_pacing(self):
        self.session.hourly_cap = 2
        old = self._log() | self._log()
        with patch.object(OpenwaSession, '_openwa_request', return_value={'id': 'X'}) as mock:
            with self.assertRaises(UserError):
                self.Message.send_message(self.partner, 'Third', session=self.session)
            # logs older than one hour are not counted
            self.env.cr.execute(SQL("UPDATE openwa_message SET create_date = %s WHERE id IN %s",
                                    self.env.cr.now() - timedelta(minutes=61), tuple(old.ids)))
            self.Message.invalidate_model(['create_date'])
            self.assertEqual(self.Message.send_message(self.partner, 'Ok', session=self.session).status, 'sent')
            # minimum delay: last message 10 seconds ago blocks
            last = self._log()
            self.env.cr.execute(SQL("UPDATE openwa_message SET create_date = %s WHERE id = %s",
                                    self.env.cr.now() - timedelta(seconds=10), last.id))
            self.Message.invalidate_model(['create_date'])
            self.session.write({'hourly_cap': 50, 'min_delay_seconds': 60})
            with self.assertRaises(UserError):
                self.Message.send_message(self.partner, 'Too fast', session=self.session)
        self.assertEqual(mock.call_count, 1)
        with self.assertRaises(ValidationError):
            self.session.hourly_cap = 0

    def test_api_error(self):
        with patch.object(OpenwaSession, '_openwa_request', side_effect=requests.Timeout('timed out')):
            log = self.Message.send_message(self.partner, 'Hi', session=self.session)
            self.assertEqual(log.status, 'failed')
            self.assertIn('timed out', log.error)
            wizard = self.env['openwa.send.wizard'].with_user(self.user).create({
                'partner_id': self.partner.id, 'session_id': self.session.id, 'body': 'Hi'})
            with self.assertRaises(UserError):
                wizard.action_send()
        empty = self.env['openwa.send.wizard'].create({'partner_id': self.partner.id, 'session_id': self.session.id})
        with self.assertRaises(UserError):
            empty.action_send()

    def test_wizard_defaults(self):
        self.icp.set_int(PARAM + 'default_session_id', self.session.id)
        wizard = self.env['openwa.send.wizard'].with_user(self.user).with_context(
            active_model='res.partner', active_id=self.partner.id).create({'body': 'Hello'})
        self.assertEqual(wizard.partner_id, self.partner)
        self.assertEqual(wizard.session_id, self.session)
        self.assertEqual(wizard.wa_number, '+628123456789')

    # ---------------------------------------------------------------- webhook
    def test_signature(self):
        body = b'{"event": "session.status"}'
        Session = self.env['openwa.session']
        self.assertTrue(Session._openwa_verify_signature(body, self._sign(body)))
        self.assertFalse(Session._openwa_verify_signature(body + b' ', self._sign(body)))
        self.assertFalse(Session._openwa_verify_signature(body, None))
        self.icp.set_str(PARAM + 'webhook_secret', False)
        self.assertFalse(Session._openwa_verify_signature(body, self._sign(body)))

    def test_webhook_inbound_known_partner(self):
        self.session.user_ids = self.user
        payload = {'event': 'message.received', 'data': {'id': 'IN1', 'from': '628123456789@c.us', 'body': 'Hello'}}
        log = self.Message._openwa_process_webhook(self.session, payload)
        self.assertEqual((log.direction, log.status, log.partner_id), ('in', 'received', self.partner))
        channel = self.env['discuss.channel'].search([('openwa_session_id', '=', self.session.id)])
        self.assertEqual(channel.openwa_partner_id, self.partner)
        self.assertIn(self.user.partner_id, channel.channel_member_ids.partner_id)
        self.assertEqual(channel.message_ids[:1].author_id, self.partner)
        self.assertIn('Hello', channel.message_ids[:1].body)
        # duplicate delivery is ignored
        self.Message._openwa_process_webhook(self.session, payload)
        self.assertEqual(self.Message.search_count([('openwa_message_id', '=', 'IN1')]), 1)
        # a reply written in Discuss goes back over WhatsApp
        with patch.object(OpenwaSession, '_openwa_request', return_value={'id': 'OUT9'}) as mock:
            channel.with_user(self.user).message_post(body='We deliver tomorrow', message_type='comment')
        self.assertEqual(mock.call_args.kwargs['json']['chatId'], '628123456789@c.us')
        self.assertTrue(self.Message.search([('openwa_message_id', '=', 'OUT9'), ('direction', '=', 'out')]))

    def test_webhook_unknown_number_fallback(self):
        self.icp.set_int(PARAM + 'fallback_user_id', self.manager.id)
        payload = {'event': 'message.received', 'data': {'id': 'IN2', 'from': '6285711112222@c.us', 'body': 'Hi?'}}
        log = self.Message._openwa_process_webhook(self.session, payload)
        self.assertFalse(log.partner_id)
        self.assertEqual(log.user_id, self.manager)
        channel = self.env['discuss.channel'].browse(log.res_id)
        self.assertIn(self.manager.partner_id, channel.channel_member_ids.partner_id)

    def test_webhook_status(self):
        log = self._log(openwa_message_id='OUT1', status='sent')
        self.Message._openwa_process_webhook(self.session, {'event': 'message.status',
                                                            'data': {'id': 'OUT1', 'status': 'read'}})
        self.assertEqual(log.status, 'read')
        self.assertTrue(log.read_at)
        self.Message._openwa_process_webhook(self.session, {'event': 'session.status',
                                                            'data': {'status': 'disconnected'}})
        self.assertEqual(self.session.status, 'disconnected')
        self.assertFalse(self.Message._openwa_process_webhook(self.session, {'event': 'unknown.event'}))

    # ---------------------------------------------------------------- access
    def test_access_rights(self):
        own = self._log(user_id=self.user.id)
        other = self._log(user_id=self.manager.id)
        visible = self.Message.with_user(self.user).search([('id', 'in', (own | other).ids)])
        self.assertEqual(visible, own)
        with self.assertRaises(AccessError):
            self.env['openwa.session'].with_user(self.user).create({'name': 'Nope'})
        with self.assertRaises(AccessError):
            self.session2.with_user(self.user).read(['name'])
        session = self.env['openwa.session'].with_user(self.manager).create({'name': 'Managed'})
        session.write({'hourly_cap': 10})
        self.assertEqual(self.Message.with_user(self.manager).search_count([('id', 'in', (own | other).ids)]), 2)
        session.unlink()
        self.assertTrue(self.admin.has_group('ydod_openwa_connector.group_openwa_manager'))

    def test_connection(self):
        response = MagicMock(ok=True, status_code=200, content=b'{}', headers={'Content-Type': 'application/json'})
        response.json.return_value = {'status': 'ok', 'version': '1.4.2'}
        settings = self.env['res.config.settings'].create({'openwa_base_url': 'http://wa.test/', 'openwa_api_key': 'k'})
        with patch('odoo.addons.ydod_openwa_connector.models.openwa_session.requests.request',
                   return_value=response) as mock:
            action = settings.action_openwa_test_connection()
        self.assertIn('1.4.2', action['params']['message'])
        self.assertEqual(mock.call_args.args[1], 'http://wa.test/api/health')
        self.assertEqual(mock.call_args.kwargs['headers']['X-API-Key'], 'k')
