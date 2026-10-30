from odoo import api, models
from odoo.http import request

PARAM_PREFIX = 'ydod_web_debrand_oem_tweaks.'
DEFAULT_RIBBON_COLOR = '#D9534F'
LOGIN_FOOTER_MODES = ('standard', 'hide', 'replace')

# Every setting delivered to the web client, with its default value.
# Boolean defaults mark the keys whose stored string is parsed as a boolean.
TWEAK_DEFAULTS = {
    'ydod_system_name': '',
    'ydod_login_footer_mode': 'standard',
    'ydod_login_footer_text': '',
    'ydod_login_footer_url': '',
    'ydod_menu_documentation_hide': False,
    'ydod_menu_documentation_label': '',
    'ydod_menu_documentation_url': '',
    'ydod_menu_support_hide': False,
    'ydod_menu_support_label': '',
    'ydod_menu_support_url': '',
    'ydod_menu_shortcuts_hide': False,
    'ydod_menu_shortcuts_label': '',
    'ydod_menu_account_hide': False,
    'ydod_menu_account_label': '',
    'ydod_menu_account_url': '',
    'ydod_menu_about_label': '',
    'ydod_menu_about_url': '',
    'ydod_ribbon_text': '',
    'ydod_ribbon_color': DEFAULT_RIBBON_COLOR,
    'ydod_debug_guard': False,
    'ydod_menu_debug_toggle': False,
    'ydod_menu_lang_switch': False,
    'ydod_dialog_draggable': False,
    'ydod_chat_draggable': False,
}


def _to_bool(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def is_safe_url(url):
    """Accept only absolute http(s) links and site-relative paths."""
    url = (url or '').strip()
    if url.startswith('//'):
        return False
    return url.startswith(('http://', 'https://', '/'))


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @api.model
    def _ydod_get_tweaks(self):
        params = self.env['ir.config_parameter'].sudo().search_read(
            [('key', '=like', PARAM_PREFIX + '%')], ['key', 'value'])
        stored = {
            param['key'][len(PARAM_PREFIX):]: param['value']
            for param in params if param['key'].startswith(PARAM_PREFIX)
        }
        tweaks = {}
        for key, default in TWEAK_DEFAULTS.items():
            value = stored.get(key)
            if isinstance(default, bool):
                tweaks[key] = _to_bool(value)
            else:
                tweaks[key] = (value or '').strip() or default
        return tweaks

    def session_info(self):
        result = super().session_info()
        result['ydod_tweaks'] = self._ydod_get_tweaks()
        result['ydod_is_system'] = self.env.user.has_group('base.group_system')
        return result

    @api.model
    def _ydod_debug_allowed(self, user):
        if not self.env['ir.config_parameter'].sudo().get_bool(PARAM_PREFIX + 'ydod_debug_guard'):
            return True
        return bool(user) and user.has_group('base.group_system')

    @classmethod
    def _ydod_enforce_debug_guard(cls):
        if not request or not request.session.debug or not request.session.uid:
            return
        user = request.env['res.users'].sudo().browse(request.session.uid).exists()
        if not request.env['ir.http']._ydod_debug_allowed(user):
            request.session.debug = ''

    @classmethod
    def _handle_debug(cls):
        parent = getattr(super(), '_handle_debug', None)
        if parent:
            parent()
        cls._ydod_enforce_debug_guard()

    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        cls._ydod_enforce_debug_guard()

    @api.model
    def _ydod_login_branding(self):
        tweaks = self._ydod_get_tweaks()
        mode = tweaks['ydod_login_footer_mode']
        if mode not in LOGIN_FOOTER_MODES:
            mode = 'standard'
        text = tweaks['ydod_login_footer_text']
        if mode == 'replace' and text:
            url = tweaks['ydod_login_footer_url']
            return {'mode': 'replace', 'text': text, 'url': url if is_safe_url(url) else ''}
        if mode == 'replace':
            mode = 'standard'
        return {'mode': mode, 'text': '', 'url': ''}
