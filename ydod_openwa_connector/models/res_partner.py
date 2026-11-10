from odoo import api, fields, models

from .openwa_session import PARAM


class ResPartner(models.Model):
    _inherit = 'res.partner'

    whatsapp_opt_in = fields.Boolean(string="WhatsApp Opt-in", tracking=True,
                                     help="The contact agreed to be contacted on WhatsApp.")
    whatsapp_opt_in_date = fields.Datetime(string="WhatsApp Opt-in Date", readonly=True)
    whatsapp_number = fields.Char(compute='_compute_whatsapp_number', store=True, index=True)
    openwa_message_count = fields.Integer(string="WhatsApp Messages", compute='_compute_openwa_message_count')

    @api.depends('phone')
    def _compute_whatsapp_number(self):
        country_code = self.env['ir.config_parameter'].sudo().get_str(PARAM + 'country_code') or '62'
        normalize = self.env['openwa.message']._openwa_normalize
        for partner in self:
            partner.whatsapp_number = partner.phone and normalize(
                partner.phone, country_code=country_code, raise_error=False) or False

    @api.depends()
    def _compute_openwa_message_count(self):
        counts = dict(self.env['openwa.message']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count']))
        for partner in self:
            partner.openwa_message_count = counts.get(partner, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('whatsapp_opt_in'):
                vals['whatsapp_opt_in_date'] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        if 'whatsapp_opt_in' in vals:
            vals['whatsapp_opt_in_date'] = vals['whatsapp_opt_in'] and fields.Datetime.now() or False
        return super().write(vals)

    def action_view_openwa_messages(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ydod_openwa_connector.action_openwa_message')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action
