# -*- coding: utf-8 -*-
from odoo import fields, models


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
        config_parameter='ydod_backend_responsive.enable_mobile_bottombar',
        readonly=False,
        help="Activate sticky bottom navigation bar on mobile viewports (<768px).",
    )
