# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ydod_default_chatter_position = fields.Selection(
        selection=[
            ('sided', 'Sided (Next to Form)'),
            ('bottom', 'Bottom (Stacked Below)'),
        ],
        string='Default Chatter Position',
        default='sided',
        config_parameter='ydod_backend_responsive.default_chatter_position',
        readonly=False,
        help="Default chatter placement for newly created users.",
    )
    ydod_enable_mobile_bottombar = fields.Boolean(
        string='Enable Mobile Bottom Navigation Bar',
        default=True,
        readonly=False,
        help="Activate sticky bottom navigation bar on mobile viewports (<768px).",
    )

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'ydod_backend_responsive.enable_mobile_bottombar',
            'True' if self.ydod_enable_mobile_bottombar else 'False',
        )

    @api.model
    def get_values(self):
        res = super().get_values()
        val = self.env['ir.config_parameter'].sudo().get_param(
            'ydod_backend_responsive.enable_mobile_bottombar', 'True'
        )
        res['ydod_enable_mobile_bottombar'] = str(val).strip().lower() in ('true', '1')
        return res
