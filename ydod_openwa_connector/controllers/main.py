import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class OpenwaWebhookController(http.Controller):

    @http.route('/openwa/webhook/<string:token>', type='http', auth='public', methods=['POST'],
                csrf=False, save_session=False)
    def openwa_webhook(self, token, **kwargs):
        session = request.env['openwa.session'].sudo().search([('webhook_token', '=', token)], limit=1)
        if not session:
            return request.make_json_response({'error': 'unknown session'}, status=404)
        body = request.httprequest.get_data()
        signature = request.httprequest.headers.get('X-OpenWA-Signature')
        if not session._openwa_verify_signature(body, signature):
            _logger.warning("OpenWA webhook: invalid signature for session %s", session.id)
            return request.make_json_response({'error': 'invalid signature'}, status=401)
        try:
            payload = json.loads(body or b'{}')
        except ValueError:
            return request.make_json_response({'error': 'invalid json'}, status=400)
        if isinstance(payload, dict):
            request.env['openwa.message'].sudo()._openwa_process_webhook(session, payload)
        return request.make_json_response({'status': 'ok'})
