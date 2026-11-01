import re

from odoo import http
from odoo.http import request

DEFAULT_FAVICON = '/web/static/img/favicon.ico'


class YdodBackendTheme(http.Controller):

    def _ydod_active_company(self, cid=None):
        """Company of the current session, following the company switcher."""
        if not request.session.uid:
            return None
        user = request.env.user
        if not user or user._is_public():
            return None
        allowed_ids = user.company_ids.ids
        candidates = [cid or ''] + re.split(r'[-,]', request.cookies.get('cids', ''))
        for candidate in candidates:
            if str(candidate).isdigit() and int(candidate) in allowed_ids:
                return request.env['res.company'].sudo().browse(int(candidate))
        return user.company_id.sudo()

    @http.route('/ydod_web_backend_theme/favicon', type='http', auth='public')
    def ydod_favicon(self, cid=None, **kwargs):
        company = self._ydod_active_company(cid)
        if company:
            company.fetch(['ydod_favicon', 'ydod_favicon_mimetype', 'write_date'])
        if not company or not company.ydod_favicon:
            return request.redirect(DEFAULT_FAVICON)
        etag = '"ydod-%s-%s"' % (company.id, int(company.write_date.timestamp()))
        # the web client requests ?cid=<company>&unique=<write_date>, which can be
        # cached for a day; the bare URL is revalidated so a company switch shows
        cache = 'private, max-age=86400' if cid else 'private, no-cache'
        headers = [('Cache-Control', cache), ('ETag', etag)]
        if request.httprequest.headers.get('If-None-Match') == etag:
            return request.make_response(b'', headers=headers, status=304)
        headers.append(('Content-Type', company.ydod_favicon_mimetype or 'image/x-icon'))
        return request.make_response(company.ydod_favicon.content, headers=headers)
