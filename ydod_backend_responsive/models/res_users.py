# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _default_ydod_chatter_position(self):
        icp = self.env['ir.config_parameter'].sudo()
        if hasattr(icp, 'get_param'):
            return icp.get_param('ydod_backend_responsive.default_chatter_position', 'sided') or 'sided'
        return 'sided'

    ydod_chatter_position = fields.Selection(
        selection=[
            ('sided', 'Sided (Next to Form)'),
            ('bottom', 'Bottom (Stacked Below)'),
        ],
        string='Chatter Position',
        default=_default_ydod_chatter_position,
        required=True,
        help="Preferred placement of chatter on wide screens (sided drawer or stacked below the form).",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['ydod_chatter_position']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['ydod_chatter_position']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'ydod_chatter_position' in vals and vals['ydod_chatter_position'] not in ('sided', 'bottom'):
                raise ValidationError(_("Chatter position must be either 'sided' or 'bottom'."))
        return super().create(vals_list)

    def write(self, vals):
        if 'ydod_chatter_position' in vals and vals['ydod_chatter_position'] not in ('sided', 'bottom'):
            raise ValidationError(_("Chatter position must be either 'sided' or 'bottom'."))
        return super().write(vals)

    @api.constrains('ydod_chatter_position')
    def _check_ydod_chatter_position(self):
        for record in self:
            if record.ydod_chatter_position and record.ydod_chatter_position not in ('sided', 'bottom'):
                raise ValidationError(_("Chatter position must be either 'sided' or 'bottom'."))
