# -*- coding: utf-8 -*-
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super().session_info()
        user = self.env.user
        result['ydod_chatter_position'] = user.ydod_chatter_position or 'sided'
        param_bottombar = self.env['ir.config_parameter'].sudo().get_param(
            'ydod_backend_responsive.enable_mobile_bottombar', 'True'
        )
        result['ydod_enable_mobile_bottombar'] = (
            str(param_bottombar).strip().lower() in ('true', '1')
        )
        return result
