import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .ir_http import DEFAULT_RIBBON_COLOR, PARAM_PREFIX, is_safe_url

COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
URL_FIELDS = (
    'ydod_login_footer_url',
    'ydod_menu_documentation_url',
    'ydod_menu_support_url',
    'ydod_menu_account_url',
    'ydod_menu_about_url',
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Branding
    ydod_system_name = fields.Char(
        string='System Name', config_parameter=PARAM_PREFIX + 'ydod_system_name',
        help="Replaces 'Odoo' in the browser tab title. Leave blank to keep 'Odoo'.")

    # Login page
    ydod_login_footer_mode = fields.Selection(
        [('standard', 'Standard (Powered by Odoo)'), ('hide', 'Hide'), ('replace', 'Replace with my text')],
        string='Login Footer', default='standard',
        config_parameter=PARAM_PREFIX + 'ydod_login_footer_mode')
    ydod_login_footer_text = fields.Char(
        string='Footer Text', config_parameter=PARAM_PREFIX + 'ydod_login_footer_text')
    ydod_login_footer_url = fields.Char(
        string='Footer Link', config_parameter=PARAM_PREFIX + 'ydod_login_footer_url')

    # User menu
    ydod_menu_documentation_hide = fields.Boolean(
        string='Hide Documentation', config_parameter=PARAM_PREFIX + 'ydod_menu_documentation_hide')
    ydod_menu_documentation_label = fields.Char(
        string='Documentation Label', config_parameter=PARAM_PREFIX + 'ydod_menu_documentation_label')
    ydod_menu_documentation_url = fields.Char(
        string='Documentation URL', config_parameter=PARAM_PREFIX + 'ydod_menu_documentation_url')
    ydod_menu_support_hide = fields.Boolean(
        string='Hide Support', config_parameter=PARAM_PREFIX + 'ydod_menu_support_hide')
    ydod_menu_support_label = fields.Char(
        string='Support Label', config_parameter=PARAM_PREFIX + 'ydod_menu_support_label')
    ydod_menu_support_url = fields.Char(
        string='Support URL', config_parameter=PARAM_PREFIX + 'ydod_menu_support_url')
    ydod_menu_shortcuts_hide = fields.Boolean(
        string='Hide Shortcuts', config_parameter=PARAM_PREFIX + 'ydod_menu_shortcuts_hide')
    ydod_menu_shortcuts_label = fields.Char(
        string='Shortcuts Label', config_parameter=PARAM_PREFIX + 'ydod_menu_shortcuts_label')
    ydod_menu_account_hide = fields.Boolean(
        string="Hide 'My Odoo.com account'", config_parameter=PARAM_PREFIX + 'ydod_menu_account_hide')
    ydod_menu_account_label = fields.Char(
        string='Account Label', config_parameter=PARAM_PREFIX + 'ydod_menu_account_label')
    ydod_menu_account_url = fields.Char(
        string='Account URL', config_parameter=PARAM_PREFIX + 'ydod_menu_account_url')
    ydod_menu_about_label = fields.Char(
        string='About Label', config_parameter=PARAM_PREFIX + 'ydod_menu_about_label')
    ydod_menu_about_url = fields.Char(
        string='About URL', config_parameter=PARAM_PREFIX + 'ydod_menu_about_url',
        help='Adds an About entry to the user menu. Leave blank for no entry.')

    # Environment
    ydod_ribbon_text = fields.Char(
        string='Ribbon Text', config_parameter=PARAM_PREFIX + 'ydod_ribbon_text',
        help='For example TEST, DEMO or STAGING. Leave blank to hide the ribbon.')
    ydod_ribbon_color = fields.Char(
        string='Ribbon Colour', default=DEFAULT_RIBBON_COLOR,
        config_parameter=PARAM_PREFIX + 'ydod_ribbon_color')

    # Feature switches
    ydod_debug_guard = fields.Boolean(
        string='Restrict Debug Mode to Administrators', config_parameter=PARAM_PREFIX + 'ydod_debug_guard')
    ydod_menu_debug_toggle = fields.Boolean(
        string='Developer Mode Shortcut', config_parameter=PARAM_PREFIX + 'ydod_menu_debug_toggle')
    ydod_menu_lang_switch = fields.Boolean(
        string='Language Switcher', config_parameter=PARAM_PREFIX + 'ydod_menu_lang_switch')
    ydod_dialog_draggable = fields.Boolean(
        string='Draggable & Resizable Dialogs', config_parameter=PARAM_PREFIX + 'ydod_dialog_draggable')
    ydod_chat_draggable = fields.Boolean(
        string='Draggable & Resizable Chat Windows', config_parameter=PARAM_PREFIX + 'ydod_chat_draggable')

    @api.constrains(*URL_FIELDS)
    def _check_ydod_urls(self):
        for settings in self:
            for fname in URL_FIELDS:
                value = (settings[fname] or '').strip()
                if value and not is_safe_url(value):
                    raise ValidationError(self.env._(
                        "%s must be empty or start with 'http://', 'https://' or '/'.",
                        settings._fields[fname].string))

    @api.constrains('ydod_ribbon_color')
    def _check_ydod_ribbon_color(self):
        for settings in self:
            color = (settings.ydod_ribbon_color or '').strip()
            if color and not COLOR_RE.match(color):
                raise ValidationError(self.env._(
                    "The ribbon colour must be a hexadecimal colour such as #D9534F."))

    @api.constrains('ydod_login_footer_mode', 'ydod_login_footer_text')
    def _check_ydod_login_footer(self):
        for settings in self:
            if settings.ydod_login_footer_mode == 'replace' and not (settings.ydod_login_footer_text or '').strip():
                raise ValidationError(self.env._(
                    "Enter the footer text that replaces 'Powered by Odoo' on the login page."))
