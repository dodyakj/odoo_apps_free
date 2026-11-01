import ast
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

PARAM = 'ydod_global_search.'
RELATIONAL = ('many2one', 'one2many', 'many2many')
SEARCH_TYPES = ('char', 'text', 'html', 'selection') + RELATIONAL
DISPLAY_TYPES = SEARCH_TYPES + ('integer', 'float', 'monetary', 'date', 'datetime', 'boolean')


def _clamp(value, low, high):
    return max(low, min(high, int(value or 0)))


class YdodGlobalSearchModel(models.Model):
    _name = 'ydod.global.search.model'
    _description = 'Global Search Model'
    _order = 'sequence, id'

    name = fields.Char(string='Label', required=True, translate=True)
    sequence = fields.Integer(default=10)
    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        domain=[('transient', '=', False), ('abstract', '=', False)])
    model_name = fields.Char(related='model_id.model', store=True, readonly=True, string='Technical Name')
    extra_domain = fields.Char(default='[]', help="Optional domain ANDed with the search, "
                               "e.g. [('customer_rank', '>', 0)]")
    limit = fields.Integer(string='Result Limit', help='Maximum results for this model, 0 uses the global setting.')
    active = fields.Boolean(default=True)
    field_ids = fields.One2many('ydod.global.search.field', 'search_model_id', string='Fields')
    field_count = fields.Integer(compute='_compute_field_count', string='Fields Count')

    _model_unique = models.Constraint('unique(model_id)', 'This model is already configured.')
    _limit_positive = models.Constraint('CHECK("limit" >= 0)', 'Limit cannot be negative.')

    @api.depends('field_ids')
    def _compute_field_count(self):
        real_ids = [rid for rid in self.ids if isinstance(rid, int)]
        counts = dict(self.env['ydod.global.search.field']._read_group(
            [('search_model_id', 'in', real_ids)], ['search_model_id'], ['__count']))
        counts = {config.id: count for config, count in counts.items()}
        for rec in self:
            rec.field_count = counts.get(rec.id, len(rec.field_ids))

    @api.onchange('model_id')
    def _onchange_model_id(self):
        for rec in self:
            if rec.model_id and not rec.name:
                rec.name = rec.model_id.name

    @api.constrains('extra_domain', 'model_id')
    def _check_extra_domain(self):
        for rec in self:
            try:
                value = ast.literal_eval(rec.extra_domain or '[]')
                if not isinstance(value, list):
                    raise ValueError('not a list')
                Domain(value).validate(self.env[rec.model_name].sudo())
            except Exception as e:  # noqa: BLE001
                raise ValidationError(self.env._(
                    'Invalid extra domain %(domain)s: %(error)s', domain=rec.extra_domain, error=e))

    @api.constrains('active', 'field_ids')
    def _check_search_line(self):
        for rec in self:
            if rec.active and not rec.field_ids.filtered('use_search'):
                raise ValidationError(self.env._(
                    'The active search model "%s" needs at least one field line used for search.', rec.name))

    # ------------------------------------------------------------------
    # Search API (called from the web client)
    # ------------------------------------------------------------------
    @api.model
    def _ydod_params(self):
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'enabled': icp.get_bool(PARAM + 'enabled', True),
            'min_chars': _clamp(icp.get_int(PARAM + 'min_chars', 2), 1, 10),
            'delay': _clamp(icp.get_int(PARAM + 'delay', 300), 0, 2000),
            'total_limit': _clamp(icp.get_int(PARAM + 'total_limit', 50), 1, 200),
            'model_limit': _clamp(icp.get_int(PARAM + 'model_limit', 8), 1, 50),
            'shortcut': icp.get_str(PARAM + 'shortcut', 'ctrl+shift+k') or 'ctrl+shift+k',
            'float_button': icp.get_bool(PARAM + 'float_button', False),
            'float_size': _clamp(icp.get_int(PARAM + 'float_size', 48), 24, 120),
            'float_position': icp.get_str(PARAM + 'float_position', 'bottom_right') or 'bottom_right',
        }

    @api.model
    def ydod_get_ui_config(self):
        return self._ydod_params()

    @api.model
    def _ydod_path_readable(self, model, path):
        for step in (path or '').split('.'):
            field = model._fields.get(step)
            if not field:
                return False
            if field.groups and not self.env.su and not self.env.user.has_groups(field.groups):
                return False
            if field.relational:
                model = self.env[field.comodel_name]
                if not model.has_access('read'):
                    return False
        return True

    def _ydod_lines(self, model):
        """Return the (search lines, display lines) of this config the user may read."""
        search_lines, display_lines = [], []
        for line in self.field_ids.sorted('sequence'):
            if not self._ydod_path_readable(model, line.full_path):
                _logger.debug('Global search: skip unreadable path %s.%s', self.model_name, line.full_path)
                continue
            if line.use_search:
                search_lines.append(line)
            if line.use_display:
                display_lines.append(line)
        return search_lines, display_lines

    def _ydod_domain(self, term, paths):
        leaves = [(path, 'ilike', term) for path in paths]
        domain = ['|'] * (len(leaves) - 1) + leaves
        extra = ast.literal_eval(self.extra_domain or '[]')
        return ['&'] + domain + list(extra) if extra else domain

    @api.model
    def _ydod_values(self, record, path):
        value = record.mapped(path)
        if isinstance(value, models.BaseModel):
            return value.mapped('display_name')
        field = record._fields[path.split('.')[0]]
        if '.' not in path and field.type == 'selection':
            labels = dict(field._description_selection(self.env))
            value = [labels.get(v, v) for v in value]
        result = []
        for v in value:
            if v is False or v is None or v == '':
                continue
            result.append(f'{v:,.2f}' if isinstance(v, float) else str(v))
        return result

    def _ydod_search_one(self, term, limit):
        self.ensure_one()
        if self.model_name not in self.env.registry:
            return None
        model = self.env[self.model_name]
        if not model.has_access('read'):
            _logger.debug('Global search: user %s cannot read %s', self.env.uid, self.model_name)
            return None
        search_lines, display_lines = self._ydod_lines(model)
        if not search_lines:
            return None
        domain = self._ydod_domain(term, [line.full_path for line in search_lines])
        top_fields = [
            line.full_path for line in display_lines
            if '.' not in line.full_path and model._fields[line.full_path].type not in ('one2many', 'many2many')
        ]
        rows = model.search_read(domain, ['display_name'] + top_fields, limit=limit)
        records = model.browse([row['id'] for row in rows])
        for line in set(search_lines + display_lines):
            records.mapped(line.full_path)  # batch prefetch through the ORM cache
        needle = term.lower()
        items = []
        for row, record in zip(rows, records):
            score = sum(
                line.weight for line in search_lines
                if any(needle in v.lower() for v in self._ydod_values(record, line.full_path)))
            values = []
            for line in display_lines:
                vals = self._ydod_values(record, line.full_path)
                if vals:
                    text = ', '.join(vals[:3]) + (', …' if len(vals) > 3 else '')
                    values.append({'label': model._fields[line.full_path.split('.')[0]].string, 'value': text})
            items.append({'id': row['id'], 'name': row['display_name'], 'score': score, 'values': values})
        items.sort(key=lambda item: -item['score'])
        if not items:
            return None
        return {'config_id': self.id, 'name': self.name, 'model': self.model_name, 'records': items}

    @api.model
    def ydod_search(self, term):
        term = (term or '').strip()
        params = self._ydod_params()
        if not params['enabled'] or len(term) < params['min_chars']:
            return []
        configs = self.search([])
        configs.field_ids.read(['full_path', 'use_search', 'use_display', 'weight', 'sequence'])
        results, remaining = [], params['total_limit']
        for config in configs:
            if remaining <= 0:
                break
            group = config._ydod_search_one(term, min(config.limit or params['model_limit'], remaining))
            if group:
                results.append(group)
                remaining -= len(group['records'])
        return results

    @api.model
    def ydod_get_action(self, config_id, term):
        config = self.browse(int(config_id)).exists()
        term = (term or '').strip()
        if not config or not term or config.model_name not in self.env.registry:
            return False
        model = self.env[config.model_name]
        search_lines = config._ydod_lines(model)[0]
        if not search_lines:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': f'{config.name}: {term}',
            'res_model': config.model_name,
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': config._ydod_domain(term, [line.full_path for line in search_lines]),
            'target': 'current',
        }


class YdodGlobalSearchField(models.Model):
    _name = 'ydod.global.search.field'
    _description = 'Global Search Field'
    _order = 'sequence, id'

    search_model_id = fields.Many2one(
        'ydod.global.search.model', string='Search Model', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one('ir.model.fields', string='Field', required=True, ondelete='cascade')
    path = fields.Char(string='Sub-path', help="Optional dotted path after a relational field, e.g. 'email' "
                       "for partner_id.email or 'product_id.name' for order_line.product_id.name")
    full_path = fields.Char(compute='_compute_full_path', store=True)
    field_type = fields.Selection(related='field_id.ttype', string='Type')
    use_search = fields.Boolean(string='Search', default=True)
    use_display = fields.Boolean(string='Display', default=False)
    weight = fields.Integer(default=10, help='Added to the score of a record when this path matches.')

    _weight_positive = models.Constraint('CHECK(weight >= 0)', 'Weight cannot be negative.')

    @api.depends('field_id.name', 'path')
    def _compute_full_path(self):
        for rec in self:
            path = (rec.path or '').strip().strip('.')
            name = rec.field_id.name or ''
            rec.full_path = f'{name}.{path}' if name and path else name

    @api.constrains('field_id', 'search_model_id')
    def _check_field_model(self):
        for rec in self:
            if rec.field_id.model_id != rec.search_model_id.model_id:
                raise ValidationError(self.env._(
                    'Field "%s" does not belong to the configured model.', rec.field_id.name))

    @api.constrains('use_search', 'use_display')
    def _check_usage(self):
        for rec in self:
            if not rec.use_search and not rec.use_display:
                raise ValidationError(self.env._('A field line must be used for search, display or both.'))

    @api.constrains('field_id', 'path', 'use_search')
    def _check_path(self):
        for rec in self:
            model = self.env[rec.search_model_id.model_name]
            steps = rec.full_path.split('.')
            for index, step in enumerate(steps):
                field = model._fields.get(step)
                if not field:
                    raise ValidationError(self.env._(
                        'Invalid path "%(path)s": unknown field "%(step)s".', path=rec.full_path, step=step))
                if index < len(steps) - 1:
                    if field.type not in RELATIONAL:
                        raise ValidationError(self.env._(
                            'Invalid path "%(path)s": "%(step)s" is not a relational field.',
                            path=rec.full_path, step=step))
                    model = self.env[field.comodel_name]
                elif field.type not in (SEARCH_TYPES if rec.use_search else DISPLAY_TYPES):
                    raise ValidationError(self.env._(
                        'Invalid path "%(path)s": fields of type %(type)s cannot be used here.',
                        path=rec.full_path, type=field.type))
