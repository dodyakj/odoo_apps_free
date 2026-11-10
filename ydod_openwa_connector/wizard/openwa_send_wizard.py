from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.openwa_session import PARAM


class OpenwaSendWizard(models.TransientModel):
    _name = 'openwa.send.wizard'
    _description = 'Send WhatsApp Message'

    res_model = fields.Char()
    res_id = fields.Integer()
    partner_id = fields.Many2one('res.partner', string="Contact", required=True)
    wa_number = fields.Char(string="WhatsApp Number", compute='_compute_wa_number')
    session_id = fields.Many2one('openwa.session', string="Session", required=True,
                                 domain=[('status', '=', 'connected')])
    body = fields.Text(string="Message")
    attachment_id = fields.Many2one('ir.attachment', string="Attachment",
                                    domain="[('res_model', '=', res_model), ('res_id', '=', res_id)]")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        model, res_id = self.env.context.get('active_model'), self.env.context.get('active_id')
        if model in self.env and res_id:
            record = self.env[model].browse(res_id).exists()
            if record:
                res.update(res_model=model, res_id=record.id)
                if model == 'res.partner':
                    res['partner_id'] = record.id
                elif 'partner_id' in record._fields and record._fields['partner_id'].comodel_name == 'res.partner':
                    res['partner_id'] = record.partner_id.id
        session_id = int(self.env['ir.config_parameter'].sudo().get_param(PARAM + 'default_session_id') or 0)
        session = self.env['openwa.session'].search([('id', '=', session_id), ('status', '=', 'connected')])
        if session and not res.get('session_id'):
            res['session_id'] = session.id
        return res

    @api.depends('partner_id.phone')
    def _compute_wa_number(self):
        normalize = self.env['openwa.message']._openwa_normalize
        for wizard in self:
            number = normalize(wizard.partner_id.phone, raise_error=False) if wizard.partner_id.phone else False
            wizard.wa_number = number and '+' + number.split('@')[0] or False

    def action_send(self):
        self.ensure_one()
        if not self.body and not self.attachment_id:
            raise UserError(self.env._("Write a message or choose an attachment."))
        record = None
        if self.res_model in self.env and self.res_id:
            record = self.env[self.res_model].browse(self.res_id).exists() or None
        log = self.env['openwa.message'].send_message(
            self.partner_id, self.body, attachment=self.attachment_id or None, record=record, session=self.session_id)
        if log.status == 'failed':
            raise UserError(self.env._("The WhatsApp message could not be sent: %s", log.error))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': self.env._("WhatsApp"),
            'message': self.env._("Message sent to %s.", self.partner_id.display_name),
            'type': 'success',
            'next': {'type': 'ir.actions.act_window_close'},
        }}
