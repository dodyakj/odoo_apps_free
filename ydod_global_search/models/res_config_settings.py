import re

from odoo import fields, models
from odoo.exceptions import ValidationError

SHORTCUT_RE = re.compile(r'^(ctrl|alt|shift|meta)(\+(ctrl|alt|shift|meta))*\+[a-z0-9]$')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ydod_gs_enabled = fields.Boolean(
        string='Enable Global Search', default=True, config_parameter='ydod_global_search.enabled')
    ydod_gs_min_chars = fields.Integer(
        string='Minimum Characters', default=2, config_parameter='ydod_global_search.min_chars')
    ydod_gs_delay = fields.Integer(
        string='Typing Delay (ms)', default=300, config_parameter='ydod_global_search.delay')
    ydod_gs_total_limit = fields.Integer(
        string='Total Result Limit', default=50, config_parameter='ydod_global_search.total_limit')
    ydod_gs_model_limit = fields.Integer(
        string='Results per Model', default=8, config_parameter='ydod_global_search.model_limit')
    ydod_gs_shortcut = fields.Char(
        string='Keyboard Shortcut', default='ctrl+shift+k', config_parameter='ydod_global_search.shortcut')
    ydod_gs_float_button = fields.Boolean(
        string='Floating Button', config_parameter='ydod_global_search.float_button')
    ydod_gs_float_size = fields.Integer(
        string='Button Size (px)', default=48, config_parameter='ydod_global_search.float_size')
    ydod_gs_float_position = fields.Selection(
        [('bottom_right', 'Bottom Right'), ('bottom_left', 'Bottom Left'),
         ('top_right', 'Top Right'), ('top_left', 'Top Left')],
        string='Button Position', default='bottom_right', config_parameter='ydod_global_search.float_position')

    def set_values(self):
        for rec in self:
            shortcut = (rec.ydod_gs_shortcut or 'ctrl+shift+k').strip().lower().replace(' ', '')
            if not SHORTCUT_RE.match(shortcut):
                raise ValidationError(self.env._(
                    'Invalid shortcut "%s": use modifiers and one key separated by "+", e.g. ctrl+shift+k.',
                    rec.ydod_gs_shortcut))
            rec.ydod_gs_shortcut = shortcut
            rec.ydod_gs_min_chars = max(1, min(10, rec.ydod_gs_min_chars))
            rec.ydod_gs_delay = max(0, min(2000, rec.ydod_gs_delay))
            rec.ydod_gs_total_limit = max(1, min(200, rec.ydod_gs_total_limit))
            rec.ydod_gs_model_limit = max(1, min(50, rec.ydod_gs_model_limit))
            rec.ydod_gs_float_size = max(24, min(120, rec.ydod_gs_float_size))
        res = super().set_values()
        # Falsy values delete the parameter, which would bring back a non-zero default:
        # store them explicitly so "disabled" and "no delay" survive a reload.
        icp = self.env['ir.config_parameter'].sudo()
        for rec in self[:1]:
            if not rec.ydod_gs_enabled:
                icp.set_param('ydod_global_search.enabled', 'False')
            if not rec.ydod_gs_delay:
                icp.set_param('ydod_global_search.delay', '0')
        return res
