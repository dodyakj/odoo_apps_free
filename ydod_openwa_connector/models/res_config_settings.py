from odoo import fields, models

from .openwa_session import PARAM, _unwrap


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    openwa_base_url = fields.Char(string="OpenWA Base URL", config_parameter=PARAM + 'base_url')
    openwa_api_key = fields.Char(string="X-API-Key", config_parameter=PARAM + 'api_key', groups='base.group_system')
    openwa_webhook_secret = fields.Char(string="Webhook HMAC Secret", config_parameter=PARAM + 'webhook_secret',
                                        groups='base.group_system')
    openwa_timeout = fields.Integer(string="Request Timeout (s)", config_parameter=PARAM + 'timeout', default=15)
    openwa_default_session_id = fields.Many2one('openwa.session', string="Default Session",
                                                config_parameter=PARAM + 'default_session_id')
    openwa_country_code = fields.Char(string="Country Code", config_parameter=PARAM + 'country_code', default='62')
    openwa_fallback_user_id = fields.Many2one('res.users', string="Fallback User",
                                              config_parameter=PARAM + 'fallback_user_id',
                                              domain=[('share', '=', False)])
    openwa_require_opt_in = fields.Boolean(string="Require Opt-in", config_parameter=PARAM + 'require_opt_in')

    def set_values(self):
        icp = self.env['ir.config_parameter'].sudo()
        old_code = icp.get_param(PARAM + 'country_code') or '62'
        super().set_values()
        if (icp.get_param(PARAM + 'country_code') or '62') != old_code:
            partner_model = self.env['res.partner'].sudo().with_context(active_test=False)
            partners = partner_model.search([('phone', '!=', False)])
            self.env.add_to_compute(partner_model._fields['whatsapp_number'], partners)
            partners.flush_recordset(['whatsapp_number'])

    def action_openwa_test_connection(self):
        self.ensure_one()
        result = self.env['openwa.session']._openwa_request(
            'GET', '/api/health', base_url=self.openwa_base_url, api_key=self.openwa_api_key,
            timeout=self.openwa_timeout or 15)
        data = {**(result if isinstance(result, dict) else {}), **_unwrap(result)}
        version = data.get('version') or data.get('status') or self.env._("unknown")
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': self.env._("OpenWA connection OK"),
            'message': self.env._("Connected to the OpenWA server, version %s.", version),
            'type': 'success',
        }}
