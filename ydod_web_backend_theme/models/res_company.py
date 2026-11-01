import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.mimetypes import guess_mimetype

HEX_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
FAVICON_MIMETYPES = ('image/x-icon', 'image/vnd.microsoft.icon', 'image/png', 'image/svg+xml')


def guess_favicon_mimetype(value):
    """Return the mimetype of a binary favicon value, or False when empty."""
    if not value:
        return False
    raw = value.content
    if not raw:
        return False
    if raw[:4] == b'\x00\x00\x01\x00':
        return 'image/x-icon'
    return guess_mimetype(raw, default='application/octet-stream')


class ResCompany(models.Model):
    _inherit = 'res.company'

    ydod_background_image = fields.Image(
        string='Apps Menu Background', max_width=1920, max_height=1920,
        help='Image shown behind the full-window apps menu for this company.')
    ydod_background_color = fields.Char(
        string='Apps Menu Colour', default='#714B67',
        help='Hex colour used behind the apps menu when no background image is set.')
    ydod_favicon = fields.Binary(
        string='Favicon', attachment=True,
        help='Browser tab icon for this company, in .ico, .png or .svg format.')
    ydod_favicon_mimetype = fields.Char(
        string='Favicon Type', compute='_compute_ydod_favicon_mimetype',
        store=True, readonly=True)

    @api.depends('ydod_favicon')
    def _compute_ydod_favicon_mimetype(self):
        for company in self.with_context(bin_size=False):
            company.ydod_favicon_mimetype = guess_favicon_mimetype(company.ydod_favicon)

    @api.constrains('ydod_background_color')
    def _check_ydod_background_color(self):
        for company in self:
            color = company.ydod_background_color
            if color and not HEX_COLOR.match(color):
                raise ValidationError(self.env._(
                    'The apps menu colour "%(color)s" of %(company)s must be a hex colour such as #714B67.',
                    color=color, company=company.name))

    @api.constrains('ydod_favicon')
    def _check_ydod_favicon(self):
        for company in self:
            mimetype = company.ydod_favicon_mimetype
            if company.ydod_favicon and mimetype not in FAVICON_MIMETYPES:
                raise ValidationError(self.env._(
                    'The favicon must be an .ico, .png or .svg file (detected type: %(type)s).',
                    type=mimetype))
