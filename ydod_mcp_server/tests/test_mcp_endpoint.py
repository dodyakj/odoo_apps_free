import json
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestMcpEndpoint(HttpCase):

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('ydod_mcp_server.enabled', 'True')
        icp.set_param('ydod_mcp_server.rate_limit', 0)
        icp.set_param('ydod_mcp_server.default_limit', 80)
        Allow = self.env['ydod.mcp.model']
        Allow.with_context(active_test=False).search([]).unlink()
        self.partner_entry = Allow.create({
            'model_id': self.env['ir.model']._get('res.partner').id, 'mode': 'read', 'row_limit': 2})
        self.tag_entry = Allow.create({
            'model_id': self.env['ir.model']._get('res.partner.category').id, 'mode': 'readwrite',
            'method_names': 'action_archive'})
        self.user = new_test_user(self.env, login='mcp_http_user', groups='base.group_user')
        self.manager = new_test_user(self.env, login='mcp_http_manager',
                                     groups='base.group_user,base.group_partner_manager')
        self.key = self._make_key(self.user)
        self.manager_key = self._make_key(self.manager)

    def _make_key(self, user):
        return self.env['res.users.apikeys'].with_user(user).sudo()._generate(
            'rpc', 'MCP test', fields.Datetime.now() + timedelta(hours=6))

    def _post(self, payload, key=None, headers=None):
        all_headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        if key:
            all_headers['Authorization'] = 'Bearer %s' % key
        all_headers.update(headers or {})
        self.env.flush_all()
        return self.url_open('/mcp', data=json.dumps(payload), headers=all_headers)

    def _rpc(self, method, params=None, key=None, headers=None):
        response = self._post({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}},
                              key or self.key, headers)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _tool(self, name, key=None, **arguments):
        return self._rpc('tools/call', {'name': name, 'arguments': arguments}, key)['result']

    def _content(self, result):
        return json.loads(result['content'][0]['text'])

    def test_protocol(self):
        response = self._post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-06-18', 'capabilities': {},
            'clientInfo': {'name': 'test-client', 'version': '9.9'}}}, self.key)
        result = response.json()['result']
        self.assertEqual(result['protocolVersion'], '2025-06-18')
        self.assertIn('tools', result['capabilities'])
        self.assertTrue(result['instructions'])
        session = response.headers.get('Mcp-Session-Id')
        self.assertTrue(session)
        fallback = self._rpc('initialize', {'protocolVersion': '1999-01-01'})['result']
        self.assertEqual(fallback['protocolVersion'], '2025-11-25')
        self.assertEqual(self._rpc('ping')['result'], {})
        notif = self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, self.key)
        self.assertEqual(notif.status_code, 202)
        self.assertEqual(self._post([{'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}], self.key).json()['error']['code'],
                         -32600)
        self.assertEqual(self._rpc('does/not/exist')['error']['code'], -32601)
        self._rpc('tools/list', headers={'Mcp-Session-Id': session})
        log = self.env['ydod.mcp.log'].search(
            [('session_id', '=', session), ('jsonrpc_method', '=', 'tools/list')], limit=1)
        self.assertEqual(log.client_name, 'test-client')
        sse = self._post({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/list'}, self.key,
                         {'Accept': 'text/event-stream'})
        self.assertTrue(sse.text.startswith('event: message\ndata: '))
        prompts = self._rpc('prompts/list')['result']['prompts']
        self.assertIn('summarise_record', [p['name'] for p in prompts])
        prompt = self._rpc('prompts/get', {'name': 'find_records',
                                           'arguments': {'model': 'res.partner', 'description': 'vip'}})
        self.assertEqual(prompt['result']['messages'][0]['role'], 'user')

    def test_authentication(self):
        self.assertEqual(self._post({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}).status_code, 401)
        self.assertEqual(self._post({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, 'deadbeef' * 5).status_code, 401)
        portal = new_test_user(self.env, login='mcp_http_portal', groups='base.group_portal')
        portal_key = self._make_key(portal)
        self.assertEqual(self._post({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, portal_key).status_code, 403)
        archived = new_test_user(self.env, login='mcp_http_archived', groups='base.group_user')
        archived_key = self._make_key(archived)
        archived.active = False
        self.assertIn(self._post({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, archived_key).status_code,
                      (401, 403))
        self.assertEqual(self._rpc('ping')['result'], {})

    def test_tools_list_and_fields(self):
        tools = self._rpc('tools/list')['result']['tools']
        schema = next(t for t in tools if t['name'] == 'search_read')['inputSchema']
        self.assertEqual(schema['properties']['model']['enum'], ['res.partner', 'res.partner.category'])
        self.tag_entry.active = False
        tools = self._rpc('tools/list')['result']['tools']
        schema = next(t for t in tools if t['name'] == 'search_read')['inputSchema']
        self.assertEqual(schema['properties']['model']['enum'], ['res.partner'])
        self.assertNotIn('create', [t['name'] for t in tools])
        self.tag_entry.active = True
        fields_info = self._content(self._tool('get_fields', model='res.partner'))['inputSchema']
        self.assertIn('contact', fields_info['properties']['type']['enum'])
        self.assertNotIn('image_1920', fields_info['properties'])
        tag_fields = self._content(self._tool('get_fields', model='res.partner.category'))['inputSchema']
        self.assertIn('name', tag_fields['required'])
        self.assertTrue(self._tool('get_fields', model='res.users')['isError'])

    def test_read_only_mode(self):
        partners = self.env['res.partner'].create([{'name': 'MCP RO %s' % i} for i in range(3)])
        result = self._tool('search_read', model='res.partner', domain=[['name', 'like', 'MCP RO']],
                            fields=['name'], limit=10)
        self.assertFalse(result['isError'])
        self.assertEqual(len(self._content(result)['records']), 2)
        self.assertTrue(self._tool('create', model='res.partner', values={'name': 'X'})['isError'])
        self.assertTrue(self._tool('write', model='res.partner', ids=partners[:1].ids,
                                   values={'name': 'X'})['isError'])
        self.partner_entry.field_ids = self.env['ir.model.fields']._get('res.partner', 'name')
        self.assertTrue(self._tool('search_read', model='res.partner', fields=['email'])['isError'])
        self.assertTrue(self._tool('search_read', model='res.partner',
                                   domain=[['email', '=', 'a@b.c']])['isError'])
        read = self._content(self._tool('read', model='res.partner', ids=partners[:1].ids))
        self.assertEqual(set(read['records'][0]), {'id', 'name'})
        resource = self._rpc('resources/read', {'uri': 'odoo://res.partner/%s' % partners[0].id})['result']
        self.assertEqual(json.loads(resource['contents'][0]['text'])['name'], 'MCP RO 0')
        self.assertEqual(self._rpc('resources/read', {'uri': 'odoo://not a uri'})['error']['code'], -32602)
        models_res = self._rpc('resources/read', {'uri': 'odoo://models'})['result']
        self.assertIn('res.partner', models_res['contents'][0]['text'])

    def test_read_write_and_call_method(self):
        self.partner_entry.mode = 'readwrite'
        self.partner_entry.row_limit = 0
        created = self._tool('create', key=self.manager_key, model='res.partner',
                             values={'name': 'MCP New', 'email': 'new@example.com'})
        self.assertFalse(created['isError'], created)
        partner = self.env['res.partner'].browse(self._content(created)['id'])
        self.assertEqual(partner.email, 'new@example.com')
        written = self._tool('write', key=self.manager_key, model='res.partner', ids=partner.ids,
                             values={'phone': '+1 555 0101'})
        self.assertFalse(written['isError'])
        partner.invalidate_recordset()
        self.assertEqual(partner.phone, '+1 555 0101')
        self.partner_entry.field_ids = self.env['ir.model.fields']._get('res.partner', 'name')
        self.assertTrue(self._tool('write', key=self.manager_key, model='res.partner', ids=partner.ids,
                                   values={'phone': '0'})['isError'])
        tag = self.env['res.partner.category'].create({'name': 'MCP Tag'})
        archived = self._tool('call_method', key=self.manager_key, model='res.partner.category',
                              method='action_archive', ids=tag.ids)
        self.assertFalse(archived['isError'], archived)
        tag.invalidate_recordset()
        self.assertFalse(tag.active)
        for method in ('action_unarchive', 'unlink', '_compute_display_name'):
            self.assertTrue(self._tool('call_method', key=self.manager_key, model='res.partner.category',
                                       method=method, ids=tag.ids)['isError'])

    def test_access_rights_and_record_rules(self):
        self.partner_entry.mode = 'readwrite'
        other = self.env['res.partner'].create({'name': 'MCP Other'})
        result = self._tool('write', model='res.partner', ids=other.ids, values={'name': 'Hacked'})
        self.assertTrue(result['isError'])
        company_b = self.env['res.company'].create({'name': 'MCP Company B'})
        visible = self.env['res.partner'].create({'name': 'MCP Rule A', 'company_id': self.env.company.id})
        hidden = self.env['res.partner'].create({'name': 'MCP Rule B', 'company_id': company_b.id})
        rows = self._content(self._tool('search_read', model='res.partner', fields=['name'],
                                        domain=[['id', 'in', [visible.id, hidden.id]]]))['records']
        self.assertEqual([r['id'] for r in rows], [visible.id])
        read = self._content(self._tool('read', model='res.partner', ids=[visible.id, hidden.id], fields=['name']))
        self.assertEqual([r['id'] for r in read['records']], [visible.id])
        self.assertEqual(read['not_found'], [hidden.id])
        log = self.env['ydod.mcp.log'].search([('tool', '=', 'write'), ('user_id', '=', self.user.id)], limit=1)
        self.assertEqual(log.status, 'denied')

    def test_logging_and_rollback(self):
        self.partner_entry.mode = 'readwrite'
        Log = self.env['ydod.mcp.log']
        partner = self.env['res.partner'].create({'name': 'MCP Keep'})
        before = Log.search_count([])
        self._tool('search_read', model='res.partner', domain=[['id', '=', partner.id]], fields=['name'])
        self.assertEqual(Log.search_count([]), before + 1)
        log = Log.search([], limit=1)
        self.assertEqual((log.tool, log.status, log.result_summary), ('search_read', 'success', '1 records'))
        self.assertGreaterEqual(log.duration_ms, 0)
        self.assertIn('res.partner', log.arguments)
        failed = self._tool('write', key=self.manager_key, model='res.partner', ids=partner.ids,
                            values={'name': 'MCP Changed', 'type': 'not_a_type'})
        self.assertTrue(failed['isError'])
        partner.invalidate_recordset()
        self.assertEqual(partner.name, 'MCP Keep')
        log = Log.search([], limit=1)
        self.assertEqual((log.tool, log.status), ('write', 'error'))
        self.assertTrue(log.error_message)

    def test_rate_limit_and_kill_switch(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('ydod_mcp_server.rate_limit', 2)
        self.assertIn('result', self._rpc('tools/call', {'name': 'list_models'}))
        self.assertIn('result', self._rpc('tools/call', {'name': 'list_models'}))
        limited = self._rpc('tools/call', {'name': 'list_models'})
        self.assertEqual(limited['error']['code'], -32000)
        self.assertEqual(limited['error']['data']['reason'], 'rate_limited')
        icp.set_param('ydod_mcp_server.rate_limit', 0)
        icp.set_param('ydod_mcp_server.enabled', False)
        disabled = self._rpc('tools/list')
        self.assertEqual(disabled['error']['code'], -32000)
        self.assertEqual(disabled['error']['data']['reason'], 'disabled')
