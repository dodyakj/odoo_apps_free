import json
import logging
import re
import time
import uuid
from datetime import timedelta
from urllib.parse import urlparse

from odoo import fields, http, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.http import request
from odoo.tools import SQL

from odoo.addons.ydod_mcp_server.models.ydod_mcp_model import FORBIDDEN_METHODS, split_method_names

_logger = logging.getLogger(__name__)

PROTOCOL_VERSIONS = ['2025-11-25', '2025-06-18', '2025-03-26']
SERVER_INFO = {'name': 'odoo-mcp-server', 'title': 'Odoo MCP Server (yDoD)', 'version': '19.0.1.0'}
INSTRUCTIONS = (
    'This server exposes allowlisted Odoo models. Start with list_models, then call get_fields to learn '
    'field names, types, selection values and required fields before using search_read, read, create, '
    'write or call_method. Domains use the Odoo syntax, e.g. [["is_company", "=", true]]. Many2one values '
    'are record ids, x2many values are lists of ids. Every call runs with the access rights of the API key user.'
)
TOOL_NAMES = ('list_models', 'get_fields', 'search_read', 'read', 'create', 'write', 'call_method')
WRITE_TOOLS = ('create', 'write', 'call_method')
EXCLUDED_TYPES = ('binary', 'properties', 'properties_definition')
RECORD_URI = re.compile(r'^odoo://([a-z0-9_]+(?:\.[a-z0-9_]+)*)/(\d+)$')
ORDER_RE = re.compile(r'^\s*\w+(\s+(asc|desc))?(\s*,\s*\w+(\s+(asc|desc))?)*\s*$', re.IGNORECASE)
BEARER_RE = re.compile(r'^bearer\s+(.+)$', re.IGNORECASE)
PROMPTS = [
    {'name': 'summarise_record', 'title': 'Summarise a record',
     'description': 'Read one Odoo record and write a short business summary of it.',
     'arguments': [{'name': 'model', 'description': 'Technical model name, e.g. res.partner', 'required': True},
                   {'name': 'id', 'description': 'Record id', 'required': True}]},
    {'name': 'find_records', 'title': 'Find records matching a description',
     'description': 'Translate a plain-language description into an Odoo domain and list the matching records.',
     'arguments': [{'name': 'model', 'description': 'Technical model name', 'required': True},
                   {'name': 'description', 'description': 'What you are looking for', 'required': True}]},
]


class McpError(Exception):
    def __init__(self, code, message, data=None, status='error'):
        super().__init__(message)
        self.code, self.message, self.data, self.status = code, message, data, status


class ToolError(Exception):
    def __init__(self, message, status='error'):
        super().__init__(message)
        self.message, self.status = message, status


def param_int(icp, key, default=0):
    try:
        return int(icp.get_param(key, default))
    except (TypeError, ValueError):
        return default


def param_bool(icp, key):
    return str(icp.get_param(key) or '').strip().lower() not in ('', 'false', '0')


def jsonable(value):
    if isinstance(value, models.BaseModel):
        return {'model': value._name, 'ids': value.ids}
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return None
    return str(value)


class McpHandler:
    """State of one MCP JSON-RPC request, executed as the API key user."""

    def __init__(self, env):
        self.env = env
        icp = env['ir.config_parameter'].sudo()
        self.default_limit = param_int(icp, 'ydod_mcp_server.default_limit', 80) or 80
        entries = env['ydod.mcp.model'].sudo().search([])
        self.entries = {e.model_name: e for e in entries if e.model_name in env}
        self._fields_cache = {}
        self.tool = self.model_name = self.summary = self.error = False
        self.status = 'success'

    # ---------------------------------------------------------------- helpers
    def _entry(self, model, write=False):
        entry = self.entries.get(model) if isinstance(model, str) else None
        if not entry:
            raise ToolError("Model '%s' is not in the MCP allowlist. Call list_models to see the allowed models."
                            % model, 'denied')
        if write and entry.mode != 'readwrite':
            raise ToolError("Model '%s' is read-only for MCP clients: create, write and call_method are refused."
                            % model)
        return entry

    def _fields(self, entry):
        if entry.model_name not in self._fields_cache:
            desc = self.env[entry.model_name].fields_get(
                attributes=['type', 'string', 'help', 'selection', 'required', 'relation', 'readonly', 'store'])
            allowed = set(entry.field_ids.mapped('name'))
            self._fields_cache[entry.model_name] = {
                name: d for name, d in desc.items()
                if d.get('type') not in EXCLUDED_TYPES and (not allowed or name in allowed or name == 'id')}
        return self._fields_cache[entry.model_name]

    def _field_list(self, entry, allowed, requested):
        if not requested:
            if entry.field_ids:
                return [n for n in allowed if n != 'id']
            return [n for n, d in allowed.items()
                    if d.get('store') and d['type'] not in ('one2many', 'many2many') and n != 'id']
        if not isinstance(requested, list) or not all(isinstance(f, str) for f in requested):
            raise ToolError('fields must be a list of field names.')
        self._check_names(requested, allowed)
        return requested

    def _check_names(self, names, allowed):
        bad = sorted(set(names) - set(allowed) - {'id'})
        if bad:
            raise ToolError('Field(s) not allowed or unknown: %s. Call get_fields for the allowed fields.'
                            % ', '.join(bad), 'denied')

    def _domain(self, domain, allowed):
        if not isinstance(domain, list):
            raise ToolError('domain must be a list, e.g. [["name", "ilike", "abc"]].')
        result = []
        for leaf in domain:
            if leaf in ('&', '|', '!'):
                result.append(leaf)
                continue
            if not isinstance(leaf, (list, tuple)) or len(leaf) != 3 or not isinstance(leaf[0], str):
                raise ToolError('Invalid domain term: %s' % json.dumps(leaf, default=str))
            self._check_names([leaf[0].split('.')[0]], allowed)
            result.append(tuple(leaf))
        return result

    def _limit(self, entry, requested):
        cap = entry.row_limit or self.default_limit
        requested = int(requested or 0)
        return min(requested, cap) if requested > 0 else cap

    def _ids(self, ids):
        if isinstance(ids, int) and not isinstance(ids, bool):
            ids = [ids]
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            raise ToolError('ids must be a non-empty list of integer record ids.')
        return ids

    def _values(self, entry, values, allowed):
        if not isinstance(values, dict) or not values:
            raise ToolError('values must be a non-empty object of field names and values.')
        self._check_names([k for k in values if k != 'id'], allowed)
        if 'id' in values:
            raise ToolError('The id field cannot be written.', 'denied')
        result = {}
        for name, value in values.items():
            ftype = allowed[name]['type']
            if ftype in ('one2many', 'many2many'):
                if not isinstance(value, list) or not all(isinstance(v, int) for v in value):
                    raise ToolError('Field %s expects a list of record ids.' % name)
                value = [Command.set(value)]
            elif ftype == 'datetime' and isinstance(value, str):
                value = value.replace('T', ' ').rstrip('Z')[:19]
            result[name] = value
        return result

    def _model_info(self, entry):
        methods = [m for m in split_method_names(entry.method_names)
                   if not m.startswith('_') and m not in FORBIDDEN_METHODS] if entry.mode == 'readwrite' else []
        return {'model': entry.model_name, 'name': entry.model_id.name, 'mode': entry.mode,
                'description': entry.description or '', 'methods': methods,
                'row_limit': entry.row_limit or self.default_limit}

    @staticmethod
    def _json_schema(desc):
        ftype = desc['type']
        schema = {
            'char': {'type': 'string'}, 'text': {'type': 'string'}, 'html': {'type': 'string'},
            'integer': {'type': 'integer'}, 'float': {'type': 'number'}, 'monetary': {'type': 'number'},
            'boolean': {'type': 'boolean'}, 'many2one': {'type': 'integer'},
            'date': {'type': 'string', 'format': 'date'},
            'datetime': {'type': 'string', 'format': 'date-time'},
            'one2many': {'type': 'array', 'items': {'type': 'integer'}},
            'many2many': {'type': 'array', 'items': {'type': 'integer'}},
        }.get(ftype, {}).copy()
        if ftype == 'selection':
            schema = {'type': 'string', 'enum': [key for key, _label in desc.get('selection') or []]}
        text = desc.get('string') or ''
        if desc.get('relation'):
            text += ' (id of %s)' % desc['relation']
        if ftype == 'datetime':
            text += ' (UTC, YYYY-MM-DD HH:MM:SS)'
        if desc.get('readonly'):
            text += ' [readonly]'
        if desc.get('help'):
            text += ': ' + desc['help']
        schema['description'] = text
        return schema

    # ------------------------------------------------------------ protocol
    def initialize(self, params):
        version = params.get('protocolVersion')
        return {
            'protocolVersion': version if version in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
            'capabilities': {'tools': {'listChanged': False},
                             'resources': {'subscribe': False, 'listChanged': False},
                             'prompts': {'listChanged': False}},
            'serverInfo': SERVER_INFO,
            'instructions': INSTRUCTIONS,
        }

    def tools_list(self, params):
        model = {'type': 'string', 'description': 'Technical name of an allowlisted Odoo model'}
        if self.entries:
            model['enum'] = sorted(self.entries)
        ids = {'type': 'array', 'items': {'type': 'integer'}, 'description': 'Record ids'}
        field_list = {'type': 'array', 'items': {'type': 'string'}, 'description': 'Field names (see get_fields)'}
        values = {'type': 'object', 'description': 'Field values keyed by field name (see get_fields)'}

        def tool(name, title, description, props, required, read_only):
            return {'name': name, 'title': title, 'description': description,
                    'inputSchema': {'type': 'object', 'properties': props, 'required': required},
                    'annotations': {'readOnlyHint': read_only, 'destructiveHint': False}}
        tools = [
            tool('list_models', 'List models', 'List the Odoo models this server exposes with mode, '
                 'description, allowed methods and row limit.', {}, [], True),
            tool('get_fields', 'Get fields', 'Return a JSON Schema of the allowed fields of a model: type, '
                 'label, help, selection values, relation and required flags.', {'model': model}, ['model'], True),
            tool('search_read', 'Search and read', 'Search records with an Odoo domain and return the '
                 'requested fields.', {
                     'model': model, 'fields': field_list,
                     'domain': {'type': 'array', 'description': 'Odoo domain, e.g. [["is_company", "=", true]]'},
                     'limit': {'type': 'integer', 'description': 'Maximum rows (capped by the row limit)'},
                     'offset': {'type': 'integer'},
                     'order': {'type': 'string', 'description': 'e.g. "name asc, id desc"'}}, ['model'], True),
            tool('read', 'Read records', 'Read records by id.', {'model': model, 'ids': ids, 'fields': field_list},
                 ['model', 'ids'], True),
        ]
        if any(e.mode == 'readwrite' for e in self.entries.values()):
            tools += [
                tool('create', 'Create record', 'Create one record on a read-write model.',
                     {'model': model, 'values': values}, ['model', 'values'], False),
                tool('write', 'Update records', 'Update records on a read-write model.',
                     {'model': model, 'ids': ids, 'values': values}, ['model', 'ids', 'values'], False),
                tool('call_method', 'Call method', 'Call an allowed public method (e.g. action_confirm) '
                     'on records of a read-write model.', {
                         'model': model, 'method': {'type': 'string'}, 'ids': ids,
                         'args': {'type': 'array'}, 'kwargs': {'type': 'object'}}, ['model', 'method'], False),
            ]
        return {'tools': tools}

    def tools_call(self, params):
        name, args = params.get('name'), params.get('arguments') or {}
        if name not in TOOL_NAMES:
            raise McpError(-32601, 'Unknown tool: %s' % name)
        if not isinstance(args, dict):
            raise McpError(-32602, 'Tool arguments must be an object.')
        self.tool = name
        self.model_name = args.get('model') if isinstance(args.get('model'), str) else False
        try:
            with self.env.cr.savepoint():
                result = getattr(self, 'tool_' + name)(args)
        except ToolError as e:
            return self._tool_error(e.message, e.status)
        except AccessError as e:
            return self._tool_error(str(e.args[0] if e.args else e), 'denied')
        except UserError as e:
            return self._tool_error(str(e.args[0] if e.args else e))
        except Exception as e:  # noqa: BLE001 - every failure must come back to the AI as a tool error
            _logger.info('MCP tool %s failed: %s', name, e)
            return self._tool_error('%s: %s' % (type(e).__name__, e))
        return {'content': [{'type': 'text', 'text': json.dumps(result, default=str)}],
                'structuredContent': result, 'isError': False}

    def _tool_error(self, message, status='error'):
        self.status, self.error = status, message
        return {'content': [{'type': 'text', 'text': message}], 'isError': True}

    def resources_list(self, params):
        return {'resources': [{
            'uri': 'odoo://models', 'name': 'models', 'title': 'Allowed Odoo models',
            'description': 'Models exposed by this MCP server with mode and description.',
            'mimeType': 'application/json'}]}

    def resources_templates_list(self, params):
        return {'resourceTemplates': [{
            'uriTemplate': 'odoo://{model}/{id}', 'name': 'record', 'title': 'Odoo record',
            'description': 'One record of an allowlisted model as JSON, e.g. odoo://res.partner/7.',
            'mimeType': 'application/json'}]}

    def resources_read(self, params):
        uri = params.get('uri')
        if uri == 'odoo://models':
            data = [self._model_info(e) for e in self.entries.values()]
        else:
            match = RECORD_URI.match(uri) if isinstance(uri, str) else None
            if not match:
                raise McpError(-32602, 'Unknown or malformed resource URI: %s' % uri, {'uri': uri})
            self.model_name = match.group(1)
            try:
                with self.env.cr.savepoint():
                    data = self.tool_read({'model': match.group(1), 'ids': [int(match.group(2))]})['records']
            except Exception as e:  # noqa: BLE001 - unreadable resources are reported to the client
                message = getattr(e, 'message', None) or (e.args[0] if e.args else type(e).__name__)
                raise McpError(-32602, str(message), {'uri': uri}, 'denied')
            if not data:
                raise McpError(-32602, 'Resource not found: %s' % uri, {'uri': uri})
            data = data[0]
        self.summary = uri
        return {'contents': [{'uri': uri, 'mimeType': 'application/json', 'text': json.dumps(data, default=str)}]}

    def prompts_list(self, params):
        return {'prompts': PROMPTS}

    def prompts_get(self, params):
        prompt = next((p for p in PROMPTS if p['name'] == params.get('name')), None)
        if not prompt:
            raise McpError(-32602, 'Unknown prompt: %s' % params.get('name'))
        args = params.get('arguments') or {}
        missing = [a['name'] for a in prompt['arguments'] if not args.get(a['name'])]
        if missing:
            raise McpError(-32602, 'Missing prompt arguments: %s' % ', '.join(missing))
        if prompt['name'] == 'summarise_record':
            text = ('Read the resource odoo://%(model)s/%(id)s (or call the read tool on model %(model)s with '
                    'ids [%(id)s]) and write a concise business summary of this record: key facts, status, '
                    'amounts, dates and related partners.' % args)
        else:
            text = ('Call get_fields on model %(model)s, build an Odoo domain that matches this description: '
                    '"%(description)s", then call search_read with that domain and present the results as a '
                    'short table.' % args)
        return {'description': prompt['description'],
                'messages': [{'role': 'user', 'content': {'type': 'text', 'text': text}}]}

    # --------------------------------------------------------------- tools
    def tool_list_models(self, args):
        data = [self._model_info(e) for e in self.entries.values()]
        self.summary = '%s models' % len(data)
        return {'models': data}

    def tool_get_fields(self, args):
        entry = self._entry(args.get('model'))
        allowed = self._fields(entry)
        props = {n: self._json_schema(d) for n, d in allowed.items() if n != 'id'}
        self.summary = '%s fields' % len(props)
        return {'model': entry.model_name, 'mode': entry.mode, 'inputSchema': {
            'type': 'object', 'properties': props,
            'required': sorted(n for n, d in allowed.items() if d.get('required') and n != 'id')}}

    def tool_search_read(self, args):
        entry = self._entry(args.get('model'))
        allowed = self._fields(entry)
        names = self._field_list(entry, allowed, args.get('fields'))
        domain = self._domain(args.get('domain') or [], allowed)
        order = args.get('order') or None
        if order:
            if not isinstance(order, str) or not ORDER_RE.match(order):
                raise ToolError('order must look like "name asc, id desc".')
            self._check_names([part.split()[0] for part in order.split(',')], allowed)
        limit = self._limit(entry, args.get('limit'))
        rows = self.env[entry.model_name].search_read(
            domain, names, offset=int(args.get('offset') or 0), limit=limit, order=order)
        self.summary = '%s records' % len(rows)
        return {'records': jsonable(rows), 'count': len(rows), 'limit': limit}

    def tool_read(self, args):
        entry = self._entry(args.get('model'))
        allowed = self._fields(entry)
        names = self._field_list(entry, allowed, args.get('fields'))
        ids = self._ids(args.get('ids'))
        limit = self._limit(entry, None)
        if len(ids) > limit:
            raise ToolError('At most %s ids can be read per call.' % limit)
        records = self.env[entry.model_name].with_context(active_test=False).search([('id', 'in', ids)])
        rows = records.read(names)
        self.summary = '%s records' % len(rows)
        return {'records': jsonable(rows), 'not_found': sorted(set(ids) - set(records.ids))}

    def tool_create(self, args):
        entry = self._entry(args.get('model'), write=True)
        values = self._values(entry, args.get('values'), self._fields(entry))
        model = self.env[entry.model_name]
        missing = [n for n, f in model._fields.items()
                   if f.required and f.store and not f.compute and not f.related and n not in values]
        missing = [n for n in missing if n not in model.default_get(missing)]
        if missing:
            raise ToolError('Missing required field(s): %s.' % ', '.join(missing))
        record = model.create(values)
        self.summary = 'ids %s' % record.id
        return {'id': record.id}

    def tool_write(self, args):
        entry = self._entry(args.get('model'), write=True)
        ids = self._ids(args.get('ids'))
        values = self._values(entry, args.get('values'), self._fields(entry))
        records = self.env[entry.model_name].browse(ids)
        missing = sorted(set(ids) - set(records.exists().ids))
        if missing:
            raise ToolError('Records not found: %s.' % missing)
        records.write(values)
        self.summary = 'ids %s' % ','.join(map(str, ids))
        return {'ids': ids, 'updated': True}

    def tool_call_method(self, args):
        entry = self._entry(args.get('model'), write=True)
        method = args.get('method')
        allowed = self._model_info(entry)['methods']
        if not isinstance(method, str) or method not in allowed:
            raise ToolError("Method '%s' is not allowed on %s. Allowed methods: %s."
                            % (method, entry.model_name, ', '.join(allowed) or 'none'), 'denied')
        records = self.env[entry.model_name]
        if args.get('ids'):
            records = records.browse(self._ids(args['ids']))
            if len(records.exists()) != len(records):
                raise ToolError('Some records do not exist.')
        call_args, call_kwargs = args.get('args') or [], args.get('kwargs') or {}
        if not isinstance(call_args, list) or not isinstance(call_kwargs, dict):
            raise ToolError('args must be a list and kwargs an object.')
        result = getattr(records, method)(*call_args, **call_kwargs)
        self.summary = '%s on ids %s' % (method, ','.join(map(str, records.ids)) or '-')
        return {'result': jsonable(result)}


class McpServerController(http.Controller):

    @http.route('/mcp', type='http', auth='bearer', methods=['POST', 'GET', 'DELETE'], csrf=False)
    def mcp_endpoint(self, **kwargs):
        httpreq = request.httprequest
        bearer = BEARER_RE.match(httpreq.headers.get('Authorization', ''))
        if not bearer:
            return self._plain(401, 'Missing Authorization: Bearer <Odoo API key> header.',
                               [('WWW-Authenticate', 'Bearer')])
        origin = httpreq.headers.get('Origin')
        if origin:
            base = urlparse(request.env['ir.config_parameter'].sudo().get_param('web.base.url', ''))
            parsed = urlparse(origin)
            if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
                return self._plain(403, 'Origin not allowed.')
        user = request.env.user
        if not user.active or user.share:
            return self._plain(403, 'Only active internal users can use the MCP server.')
        if httpreq.method == 'GET':
            return self._plain(405, 'Server-initiated streams are not supported.', [('Allow', 'POST')])
        if httpreq.method == 'DELETE':
            return self._plain(200, '')
        try:
            payload = json.loads(httpreq.get_data(as_text=True) or 'null')
        except ValueError:
            return self._reply(self._error(None, -32700, 'Parse error'))
        if isinstance(payload, list):
            return self._reply(self._error(None, -32600, 'Batch requests are not supported.'))
        if not isinstance(payload, dict) or payload.get('jsonrpc') != '2.0':
            return self._reply(self._error(None, -32600, 'Invalid Request'))
        if 'id' not in payload or 'method' not in payload:
            return self._plain(202, '')
        if not isinstance(payload['method'], str):
            return self._reply(self._error(payload['id'], -32600, 'Invalid Request'))
        return self._handle(payload, bearer.group(1).strip())

    def _handle(self, payload, token):
        start = time.monotonic()
        req_id, method, params = payload['id'], payload['method'], payload.get('params') or {}
        if method == 'ping':
            return self._reply({'jsonrpc': '2.0', 'id': req_id, 'result': {}})
        user = request.env.user
        company_ids = [user.company_id.id] + [cid for cid in user.company_ids.ids if cid != user.company_id.id]
        env = request.env(context=dict(request.env.context, allowed_company_ids=company_ids))
        Log = env['ydod.mcp.log'].sudo()
        icp = env['ir.config_parameter'].sudo()
        env.cr.execute(SQL('SELECT id FROM res_users_apikeys WHERE user_id = %s AND index = %s ORDER BY id LIMIT 1',
                           user.id, token[:8]))
        key_row = env.cr.fetchone()
        key_id = key_row[0] if key_row else False
        headers = []
        if method == 'initialize':
            session_id = uuid.uuid4().hex
            headers.append(('Mcp-Session-Id', session_id))
            info = params.get('clientInfo') if isinstance(params, dict) else None
            info = info if isinstance(info, dict) else {}
            client = (str(info.get('name') or ''), str(info.get('version') or ''))
        else:
            session_id = request.httprequest.headers.get('Mcp-Session-Id') or False
            init = session_id and Log.search(
                [('session_id', '=', session_id), ('jsonrpc_method', '=', 'initialize')], limit=1)
            client = (init.client_name, init.client_version) if init else (False, False)
        handler = McpHandler(env)
        response = None
        try:
            if not isinstance(params, dict):
                raise McpError(-32602, 'params must be an object.')
            if not param_bool(icp, 'ydod_mcp_server.enabled'):
                raise McpError(-32000, 'The MCP server is disabled by the administrator.',
                               {'reason': 'disabled'}, 'denied')
            rate_limit = param_int(icp, 'ydod_mcp_server.rate_limit', 60)
            if rate_limit > 0:
                since = fields.Datetime.now() - timedelta(seconds=60)
                owner = ('api_key_id', '=', key_id) if key_id else ('user_id', '=', user.id)
                if Log.search_count([owner, ('date', '>=', since), ('status', '!=', 'rate_limited')]) >= rate_limit:
                    raise McpError(-32000, 'Rate limit exceeded: %s calls per minute per API key.' % rate_limit,
                                   {'reason': 'rate_limited', 'limit': rate_limit}, 'rate_limited')
            route = getattr(handler, method.replace('/', '_'), None) if method in (
                'initialize', 'tools/list', 'tools/call', 'resources/list', 'resources/templates/list',
                'resources/read', 'prompts/list', 'prompts/get') else None
            if not route:
                raise McpError(-32601, 'Method not found: %s' % method)
            response = {'jsonrpc': '2.0', 'id': req_id, 'result': route(params)}
        except McpError as e:
            handler.status, handler.error = e.status, e.message
            response = self._error(req_id, e.code, e.message, e.data)
        except Exception as e:  # noqa: BLE001 - malformed params must not crash the endpoint
            _logger.warning('MCP request %s failed: %s', method, e)
            handler.status, handler.error = 'error', str(e)
            response = self._error(req_id, -32603, 'Internal error: %s' % e)
        arguments = params.get('arguments') if method == 'tools/call' and isinstance(params, dict) else params
        Log.create({
            'user_id': user.id,
            'company_id': user.company_id.id,
            'api_key_id': key_id,
            'session_id': session_id,
            'client_name': client[0],
            'client_version': client[1],
            'jsonrpc_method': method[:64],
            'tool': handler.tool,
            'model_name': handler.model_name,
            'arguments': json.dumps(arguments, default=str)[:4000] if arguments else False,
            'duration_ms': int((time.monotonic() - start) * 1000),
            'result_summary': handler.summary,
            'status': handler.status,
            'error_message': handler.error,
        })
        return self._reply(response, headers)

    @staticmethod
    def _error(req_id, code, message, data=None):
        error = {'code': code, 'message': message}
        if data:
            error['data'] = data
        return {'jsonrpc': '2.0', 'id': req_id, 'error': error}

    @staticmethod
    def _plain(status, text, headers=None):
        return request.make_response(text, headers=[('Content-Type', 'text/plain')] + (headers or []), status=status)

    @staticmethod
    def _reply(body, headers=None):
        data = json.dumps(body, default=str)
        accept = [part.split(';')[0].strip() for part in request.httprequest.headers.get('Accept', '').split(',')]
        headers = list(headers or [])
        if 'text/event-stream' in accept and 'application/json' not in accept:
            return request.make_response('event: message\ndata: %s\n\n' % data,
                                         headers=[('Content-Type', 'text/event-stream'),
                                                  ('Cache-Control', 'no-cache')] + headers)
        return request.make_response(data, headers=[('Content-Type', 'application/json')] + headers)
