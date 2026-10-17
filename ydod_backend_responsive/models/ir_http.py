# -*- coding: utf-8 -*-
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super().session_info()
        user = self.env.user
        result['ydod_chatter_position'] = getattr(user, 'ydod_chatter_position', 'sided') or 'sided'
        icp = self.env['ir.config_parameter'].sudo()
        if hasattr(icp, 'get_bool'):
            result['ydod_enable_mobile_bottombar'] = icp.get_bool(
                'ydod_backend_responsive.enable_mobile_bottombar', True
            )
        elif hasattr(icp, 'get_param'):
            param_bottombar = icp.get_param(
                'ydod_backend_responsive.enable_mobile_bottombar', 'True'
            )
            result['ydod_enable_mobile_bottombar'] = (
                str(param_bottombar).strip().lower() in ('true', '1')
            )
        else:
            result['ydod_enable_mobile_bottombar'] = True
        return result
