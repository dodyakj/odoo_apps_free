import base64
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

_logger = logging.getLogger(__name__)

PARAM = 'ydod_openwa_connector.'

STATUS_MAP = {
    'connected': 'connected', 'ready': 'connected', 'working': 'connected', 'authenticated': 'connected',
    'open': 'connected', 'pairing': 'pairing', 'qr': 'pairing', 'scan_qr': 'pairing', 'qr_ready': 'pairing',
    'starting': 'pairing', 'initializing': 'pairing', 'failed': 'failed', 'error': 'failed',
    'auth_failure': 'failed',
}


def _unwrap(result):
    """OpenWA answers either the object itself or {"data": {...}}."""
    if isinstance(result, dict) and isinstance(result.get('data'), dict):
        return result['data']
    return result if isinstance(result, dict) else {}


class OpenwaSession(models.Model):
    _name = 'openwa.session'
    _description = 'OpenWA WhatsApp Session'
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char(required=True, tracking=True, help="Session name sent to the OpenWA server.")
    remote_id = fields.Char(string="OpenWA Session ID", readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    status = fields.Selection([
        ('pairing', 'Pairing'),
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('failed', 'Failed'),
    ], required=True, readonly=True, default='disconnected', tracking=True)
    phone_number = fields.Char(readonly=True, help="Number paired with this session, as reported by OpenWA.")
    qr_image = fields.Binary(string="Pairing QR", attachment=True, readonly=True, copy=False)
    last_status_at = fields.Datetime(readonly=True, copy=False)
    last_error = fields.Text(readonly=True, copy=False)
    webhook_token = fields.Char(
        required=True, readonly=True, copy=False, groups='base.group_system',
        default=lambda self: secrets.token_urlsafe(24))
    webhook_url = fields.Char(compute='_compute_webhook_url', groups='base.group_system')
    dedicated_number_confirmed = fields.Boolean(
        string="Dedicated Number Confirmed", tracking=True,
        help="Confirm that this WhatsApp number is a dedicated business number, not a personal one.")
    min_delay_seconds = fields.Integer(string="Minimum Delay (s)", default=8,
                                       help="Minimum gap in seconds between two outgoing messages.")
    hourly_cap = fields.Integer(string="Hourly Cap", default=60,
                                help="Maximum outgoing messages per rolling hour.")
    user_ids = fields.Many2many(
        'res.users', 'openwa_session_inbox_user_rel', 'session_id', 'user_id',
        string="Discuss Inbox Users", domain=[('share', '=', False)],
        help="Users who receive the incoming WhatsApp chats of this number in Discuss. When empty, "
             "users whose own phone matches the session number, then the fallback user, receive them.")
    active = fields.Boolean(default=True)
    openwa_message_ids = fields.One2many('openwa.message', 'session_id', string="WhatsApp Messages")
    wa_message_count = fields.Integer(string="Message Count", compute='_compute_wa_message_count')
    is_usable = fields.Boolean(compute='_compute_is_usable')

    _sql_constraints = [
        ('webhook_token_uniq', 'UNIQUE(webhook_token)', 'Webhook token must be unique.'),
        ('remote_company_uniq', 'UNIQUE(remote_id, company_id)', 'Session already linked.'),
    ]

    @api.depends('webhook_token')
    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for session in self:
            session.webhook_url = f"{base_url}/openwa/webhook/{session.webhook_token}"

    @api.depends('openwa_message_ids')
    def _compute_wa_message_count(self):
        counts = dict(self.env['openwa.message']._read_group(
            [('session_id', 'in', self.ids)], ['session_id'], ['__count']))
        for session in self:
            session.wa_message_count = counts.get(session, 0)

    @api.depends('status', 'dedicated_number_confirmed', 'remote_id')
    def _compute_is_usable(self):
        for session in self:
            session.is_usable = bool(
                session.status == 'connected' and session.dedicated_number_confirmed and session.remote_id)

    @api.constrains('min_delay_seconds', 'hourly_cap')
    def _check_pacing(self):
        for session in self:
            if session.min_delay_seconds < 0 or session.hourly_cap < 1:
                raise ValidationError(self.env._(
                    "The minimum delay cannot be negative and the hourly cap must be at least 1."))

    # ------------------------------------------------------------------ API
    @api.model
    def _openwa_request(self, method, path, json=None, base_url=None, api_key=None, timeout=None):
        """Single HTTP wrapper for the OpenWA REST API. Never logs the headers."""
        icp = self.env['ir.config_parameter'].sudo()
        base_url = (base_url or icp.get_param(PARAM + 'base_url') or '').rstrip('/')
        if not base_url:
            raise UserError(self.env._("The OpenWA base URL is not configured (Settings > WhatsApp)."))
        headers = {'X-API-Key': api_key or icp.get_param(PARAM + 'api_key') or '', 'Accept': 'application/json'}
        timeout = timeout or int(icp.get_param(PARAM + 'timeout') or 15)
        try:
            response = requests.request(method, base_url + path, json=json, headers=headers, timeout=timeout)
        except requests.RequestException as error:
            raise UserError(self.env._("OpenWA request %(path)s failed: %(error)s", path=path, error=error)) from error
        if not response.ok:
            raise UserError(self.env._(
                "OpenWA request %(path)s returned HTTP %(status)s: %(text)s",
                path=path, status=response.status_code, text=(response.text or '')[:300]))
        if (response.headers.get('Content-Type') or '').startswith('image/'):
            return {'_image': base64.b64encode(response.content)}
        try:
            return response.json() if response.content else {}
        except ValueError:
            return {}

    @api.model
    def _openwa_verify_signature(self, body, signature):
        secret = self.env['ir.config_parameter'].sudo().get_param(PARAM + 'webhook_secret')
        if not secret or not signature:
            return False
        signature = signature.strip()
        if signature.startswith('sha256='):
            signature = signature[7:]
        expected = hmac.new(secret.encode(), body or b'', hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _openwa_set_status(self, remote_status, phone=None):
        status = STATUS_MAP.get(str(remote_status or '').lower(), 'disconnected')
        for session in self:
            vals = {'status': status, 'last_status_at': fields.Datetime.now()}
            if phone:
                vals['phone_number'] = str(phone).split('@')[0].split(':')[0]
            if status != 'pairing':
                vals['qr_image'] = False
            session.write(vals)

    def _openwa_check_pacing(self):
        self.ensure_one()
        messages = self.env['openwa.message'].sudo()
        domain = [('session_id', '=', self.id), ('direction', '=', 'out')]
        now = self.env.cr.now()
        if messages.search_count(domain + [('create_date', '>=', now - timedelta(hours=1))]) >= self.hourly_cap:
            raise UserError(self.env._(
                "Session %(name)s reached its limit of %(cap)s messages per hour. Try again later.",
                name=self.name, cap=self.hourly_cap))
        if self.min_delay_seconds:
            last = messages.search(domain, order='create_date desc', limit=1)
            if last and (now - last.create_date).total_seconds() < self.min_delay_seconds:
                raise UserError(self.env._(
                    "Please wait %(delay)s seconds between two messages of session %(name)s.",
                    delay=self.min_delay_seconds, name=self.name))

    def _openwa_inbox_users(self):
        """Users who receive the incoming chats of this session in Discuss."""
        self.ensure_one()
        users = self.user_ids.filtered('active')
        if not users and self.phone_number:
            number = self.env['openwa.message']._openwa_normalize(self.phone_number, raise_error=False)
            if number:
                users = self.env['res.users'].sudo().search(
                    [('partner_id.whatsapp_number', '=', number), ('share', '=', False)])
        if not users:
            user_id = self.env['ir.config_parameter'].sudo().get_param(PARAM + 'fallback_user_id')
            users = self.env['res.users'].sudo().browse(int(user_id or 0)).exists()
        return users or self.create_uid or self.env.ref('base.user_admin')

    def _openwa_get_channel(self, number, partner):
        """Discuss conversation of a WhatsApp contact, shared with the session inbox users."""
        self.ensure_one()
        channel_model = self.env['discuss.channel'].sudo()
        channel = channel_model.search(
            [('openwa_session_id', '=', self.id), ('openwa_wa_number', '=', number)], limit=1)
        partners = self._openwa_inbox_users().partner_id
        if not channel:
            channel = channel_model.create({
                'name': self.env._("WhatsApp: %s", partner.name or '+' + number.split('@')[0]),
                'channel_type': 'group',
                'openwa_session_id': self.id,
                'openwa_wa_number': number,
                'openwa_partner_id': partner.id,
                'channel_member_ids': [Command.create({'partner_id': pid}) for pid in partners.ids],
            })
        elif partners - channel.channel_member_ids.partner_id:
            channel._add_members(partners=partners - channel.channel_member_ids.partner_id,
                                 post_joined_message=False)
        return channel

    # -------------------------------------------------------------- buttons
    def _openwa_run(self, func, success):
        self.ensure_one()
        try:
            func()
        except UserError as error:
            self.last_error = str(error)
            return self._openwa_notify(str(error), 'danger')
        self.last_error = False
        return self._openwa_notify(success, 'success')

    def _openwa_notify(self, message, kind):
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': self.env._("OpenWA"), 'message': message, 'type': kind, 'sticky': kind == 'danger',
            'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}}}

    def _openwa_create_remote(self):
        data = _unwrap(self._openwa_request('POST', '/api/sessions', json={'name': self.name}))
        self.remote_id = data.get('id') or data.get('sessionId') or self.name

    def action_create_on_server(self):
        return self._openwa_run(self._openwa_create_remote, self.env._("Session created on the OpenWA server."))

    def action_start(self):
        def start():
            if not self.remote_id:
                self._openwa_create_remote()
            self._openwa_request('POST', f'/api/sessions/{self.remote_id}/start')
            icp = self.env['ir.config_parameter'].sudo()
            self._openwa_request('POST', '/api/webhooks', json={
                'sessionId': self.remote_id,
                'url': f"{icp.get_param('web.base.url', '')}/openwa/webhook/{self.sudo().webhook_token}",
                'secret': icp.get_param(PARAM + 'webhook_secret') or '',
                'events': ['message.received', 'message.status', 'session.status'],
            })
            self._openwa_set_status('pairing')
            self._openwa_fetch_qr()
        return self._openwa_run(start, self.env._("Session started: scan the QR code with WhatsApp."))

    def action_stop(self):
        def stop():
            if self.remote_id:
                self._openwa_request('POST', f'/api/sessions/{self.remote_id}/stop')
            self._openwa_set_status('disconnected')
        return self._openwa_run(stop, self.env._("Session stopped."))

    def action_refresh(self):
        def refresh():
            if not self.remote_id:
                raise UserError(self.env._("Create the session on the OpenWA server first."))
            data = _unwrap(self._openwa_request('GET', f'/api/sessions/{self.remote_id}'))
            self._openwa_set_status(data.get('status') or data.get('state'),
                                    phone=data.get('phone') or data.get('phoneNumber'))
            if self.status == 'pairing':
                self._openwa_fetch_qr()
        return self._openwa_run(refresh, self.env._("Status refreshed."))

    def _openwa_fetch_qr(self):
        data = self._openwa_request('GET', f'/api/sessions/{self.remote_id}/qr')
        qr = data.get('_image') or _unwrap(data).get('qr') or _unwrap(data).get('qrCode') or ''
        if isinstance(qr, str) and ',' in qr:
            qr = qr.split(',', 1)[1]
        self.qr_image = qr or False

    def action_view_messages(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ydod_openwa_connector.action_openwa_message')
        action['domain'] = [('session_id', '=', self.id)]
        return action
