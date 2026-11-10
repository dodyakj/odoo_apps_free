import base64
import re

import requests
from markupsafe import Markup

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, UserError

from .openwa_session import PARAM, _unwrap

STATUS_RANK = {'queued': 0, 'sent': 1, 'delivered': 2, 'read': 3}
ACK_MAP = {-1: 'failed', 0: 'queued', 1: 'sent', 2: 'delivered', 3: 'read', 4: 'read'}


class OpenwaMessage(models.Model):
    _name = 'openwa.message'
    _description = 'OpenWA WhatsApp Message'
    _order = 'create_date desc, id desc'
    _rec_name = 'wa_number'

    direction = fields.Selection([('in', 'Incoming'), ('out', 'Outgoing')], required=True, readonly=True)
    session_id = fields.Many2one('openwa.session', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='session_id.company_id', store=True)
    partner_id = fields.Many2one('res.partner', string="Contact", index=True)
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user, index=True)
    res_model = fields.Char(string="Related Model")
    res_id = fields.Many2oneReference(string="Related ID", model_field='res_model')
    related_record_name = fields.Char(string="Related Record", compute='_compute_related_record_name')
    wa_number = fields.Char(string="WhatsApp Number", required=True, index=True)
    body = fields.Text()
    attachment_name = fields.Char()
    attachment_id = fields.Many2one('ir.attachment', ondelete='set null')
    openwa_message_id = fields.Char(string="OpenWA Message ID", index=True, readonly=True)
    status = fields.Selection([
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
        ('received', 'Received'),
    ], required=True, default='queued', index=True)
    sent_at = fields.Datetime(readonly=True)
    delivered_at = fields.Datetime(readonly=True)
    read_at = fields.Datetime(readonly=True)
    error = fields.Text(readonly=True)

    _sql_constraints = [
        ('openwa_id_uniq', 'UNIQUE(session_id, openwa_message_id)', 'Duplicate OpenWA message id.'),
    ]

    def init(self):
        tools.create_index(self._cr, 'openwa_message_pacing_idx', self._table,
                           ['session_id', 'direction', 'create_date'])

    @api.depends('res_model', 'res_id')
    def _compute_related_record_name(self):
        for message in self:
            name = False
            if message.res_model in self.env and message.res_id:
                record = self.env[message.res_model].browse(message.res_id).exists()
                try:
                    name = record.display_name if record else False
                except AccessError:
                    name = False
            message.related_record_name = name

    @api.model
    def _openwa_normalize(self, number, country_code=None, raise_error=True):
        """'0812-3456 789' -> '628123456789@c.us' (country code from the settings, default 62)."""
        digits = re.sub(r'[\s\-.()+]', '', (number or '').split('@')[0])
        if digits.startswith('00'):
            digits = digits[2:]
        elif digits.startswith('0'):
            country_code = country_code or self.env['ir.config_parameter'].sudo().get_param(
                PARAM + 'country_code') or '62'
            digits = country_code + digits[1:]
        if not digits.isdigit() or not 8 <= len(digits) <= 15:
            if raise_error:
                raise UserError(self.env._("'%s' is not a valid WhatsApp number.", number or ''))
            return False
        return digits + '@c.us'

    # -------------------------------------------------------------- sending
    @api.model
    def send_message(self, partner, body, attachment=None, record=None, session=None):
        """Public service: send a WhatsApp text or file to a partner and return the openwa.message log.

        Safeguard violations raise UserError before any HTTP call; API errors return a failed log.
        """
        if not session:
            session_id = self.env['ir.config_parameter'].sudo().get_param(PARAM + 'default_session_id')
            session = self.env['openwa.session'].sudo().browse(int(session_id or 0)).exists()
        return self._openwa_send(session, partner, body, attachment=attachment, record=record)

    @api.model
    def _openwa_send(self, session, partner, body, attachment=None, record=None, wa_number=None,
                     check_opt_in=True, channel=None):
        partner = partner or self.env['res.partner']
        if not partner and not wa_number:
            raise UserError(self.env._("Select a contact to send the WhatsApp message to."))
        phone = partner.mobile or partner.phone
        if not wa_number and not phone:
            raise UserError(self.env._("%s has no mobile or phone number.", partner.display_name))
        number = wa_number or self._openwa_normalize(phone)
        icp = self.env['ir.config_parameter'].sudo()
        if check_opt_in and partner and icp.get_param(PARAM + 'require_opt_in') and not partner.whatsapp_opt_in:
            raise UserError(self.env._(
                "%s has not opted in to WhatsApp messages. Tick 'WhatsApp Opt-in' on the contact "
                "once the customer agreed to be contacted.", partner.display_name))
        if not session:
            raise UserError(self.env._("No WhatsApp session selected and no default session configured."))
        session = session.sudo()
        if not session.dedicated_number_confirmed:
            raise UserError(self.env._(
                "Session %s cannot be used until its dedicated number is confirmed.", session.name))
        if session.status != 'connected' or not session.remote_id:
            raise UserError(self.env._("Session %s is not connected.", session.name))
        session._openwa_check_pacing()

        payload = {'sessionId': session.remote_id, 'chatId': number}
        if attachment:
            payload.update(filename=attachment.name, mimetype=attachment.mimetype or 'application/octet-stream',
                           data=base64.b64encode(attachment.raw or b'').decode(), caption=body or '')
            path = '/api/messages/send-media'
        else:
            payload['text'] = body or ''
            path = '/api/messages/send-text'
        log = self.sudo().create({
            'direction': 'out',
            'session_id': session.id,
            'partner_id': partner.id,
            'user_id': self.env.user.id,
            'res_model': record._name if record else False,
            'res_id': record.id if record else False,
            'wa_number': number,
            'body': body,
            'attachment_id': attachment.id if attachment else False,
            'attachment_name': attachment.name if attachment else False,
        })
        try:
            data = _unwrap(session._openwa_request('POST', path, json=payload))
        except (UserError, requests.RequestException) as error:
            log.write({'status': 'failed', 'error': str(error)})
            return log.sudo(False)
        log.write({
            'status': 'sent',
            'sent_at': fields.Datetime.now(),
            'openwa_message_id': data.get('id') or data.get('messageId') or False,
        })
        log._openwa_post_outgoing_notes(record, channel)
        return log.sudo(False)

    def _openwa_post_outgoing_notes(self, record, channel):
        self.ensure_one()
        note = Markup('<p><i class="fa fa-whatsapp"></i> %s</p><p>%s</p>') % (
            self.env._("WhatsApp sent to +%s", self.wa_number.split('@')[0]), self.body or '')
        attachment_ids = self.attachment_id.ids
        targets = [self.partner_id] if self.partner_id else []
        if record and record != self.partner_id and hasattr(record, 'message_post'):
            targets.append(record)
        for target in targets:
            target.sudo().message_post(body=note, subtype_xmlid='mail.mt_note', attachment_ids=attachment_ids,
                                       author_id=self.user_id.partner_id.id)
        if not channel:
            channel = self.env['discuss.channel'].sudo().search(
                [('openwa_session_id', '=', self.session_id.id), ('openwa_wa_number', '=', self.wa_number)], limit=1)
            if channel:
                channel.with_context(openwa_skip_send=True).message_post(
                    body=self.body or '', message_type='comment', subtype_xmlid='mail.mt_comment',
                    author_id=self.user_id.partner_id.id, attachment_ids=attachment_ids)

    # -------------------------------------------------------------- webhook
    @api.model
    def _openwa_process_webhook(self, session, payload):
        event = payload.get('event') or payload.get('type') or ''
        data = payload.get('data') or payload.get('payload') or {}
        if event in ('message.received', 'message'):
            return self._openwa_process_inbound(session, data)
        if event.startswith('message.') or event == 'message_ack':
            return self._openwa_process_status(session, data, event)
        if event == 'session.status':
            session._openwa_set_status(data.get('status') or data.get('state'),
                                       phone=data.get('phone') or data.get('phoneNumber'))
            return session
        return False

    @api.model
    def _openwa_process_inbound(self, session, data):
        sender = data.get('from') or data.get('chatId') or ''
        if data.get('fromMe') or sender.endswith('@g.us') or sender == 'status@broadcast':
            return False
        msg_id = data.get('id') or data.get('messageId') or False
        if isinstance(msg_id, dict):
            msg_id = msg_id.get('_serialized') or msg_id.get('id')
        messages = self.sudo()
        if msg_id and messages.search_count([('session_id', '=', session.id), ('openwa_message_id', '=', msg_id)]):
            return False
        number = self._openwa_normalize(sender, raise_error=False)
        if not number:
            return False
        partner = self.env['res.partner'].sudo().search([('whatsapp_number', '=', number)], limit=1)
        body = data.get('body') or data.get('text') or data.get('caption') or ''
        if data.get('hasMedia') and not body:
            body = self.env._("[media message]")
        channel = session._openwa_get_channel(number, partner)
        log = messages.create({
            'direction': 'in',
            'session_id': session.id,
            'partner_id': partner.id,
            'user_id': session._openwa_inbox_users()[:1].id,
            'res_model': 'discuss.channel',
            'res_id': channel.id,
            'wa_number': number,
            'body': body,
            'openwa_message_id': msg_id,
            'status': 'received',
        })
        channel.with_context(openwa_skip_send=True).message_post(
            body=body, message_type='comment', subtype_xmlid='mail.mt_comment',
            author_id=partner.id or False,
            email_from=False if partner else self.env._("WhatsApp +%s", number.split('@')[0]))
        return log

    @api.model
    def _openwa_process_status(self, session, data, event):
        msg_id = data.get('id') or data.get('messageId')
        if isinstance(msg_id, dict):
            msg_id = msg_id.get('_serialized') or msg_id.get('id')
        status = data.get('status') or ACK_MAP.get(data.get('ack')) or event.split('.')[-1]
        status = str(status).lower()
        log = self.sudo().search([('session_id', '=', session.id), ('openwa_message_id', '=', msg_id)], limit=1)
        if not log or not msg_id:
            return False
        now = fields.Datetime.now()
        if status == 'failed':
            log.write({'status': 'failed', 'error': data.get('error') or self.env._("Reported as failed by OpenWA.")})
        elif status in STATUS_RANK and log.direction == 'out':
            vals = {f'{status}_at': now} if status != 'queued' else {}
            if STATUS_RANK[status] > STATUS_RANK.get(log.status, -1):
                vals['status'] = status
            log.write(vals)
        return log

    def action_open_related(self):
        self.ensure_one()
        if self.res_model == 'discuss.channel':
            return {'type': 'ir.actions.act_url', 'target': 'self',
                    'url': f'/odoo/action-mail.action_discuss?active_id={self.res_id}'}
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model, 'res_id': self.res_id,
                'view_mode': 'form', 'target': 'current'}
