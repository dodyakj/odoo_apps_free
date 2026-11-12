from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Methods that can never be exposed through call_method, even when configured.
FORBIDDEN_METHODS = frozenset({
    'unlink', 'sudo', 'with_user', 'with_context', 'with_env', 'with_company', 'with_prefetch',
    'browse', 'create', 'write', 'read', 'search', 'search_read', 'search_count', 'search_fetch',
    'copy', 'copy_data', 'export_data', 'load', 'fields_get', 'default_get', 'name_create',
    'check_access', 'has_access', 'exists', 'ensure_one', 'mapped', 'filtered', 'sorted',
    'invalidate_model', 'invalidate_recordset', 'flush_model', 'flush_recordset', 'modified',
    'web_read', 'web_search_read', 'web_save', 'read_group', 'get_metadata', 'init',
})


def split_method_names(value):
    return [name.strip() for name in (value or '').split(',') if name.strip()]


class YdodMcpModel(models.Model):
    _name = 'ydod.mcp.model'
    _description = 'MCP Allowed Model'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        domain=[('transient', '=', False)])
    model_name = fields.Char(
        related='model_id.model', string='Technical Name', store=True, readonly=True, index=True)
    mode = fields.Selection(
        [('read', 'Read-only'), ('readwrite', 'Read-write')],
        required=True, default='read',
        help='Read-only allows list_models, get_fields, search_read and read. '
             'Read-write also allows create, write and call_method.')
    field_ids = fields.Many2many(
        'ir.model.fields', string='Allowed Fields',
        domain="[('model_id', '=', model_id), ('ttype', '!=', 'binary')]",
        help='Fields the AI may read and write. Leave empty to allow every readable non-binary field.')
    method_names = fields.Char(
        string='Allowed Methods',
        help="Comma-separated public methods allowed for call_method, e.g. 'action_confirm,action_cancel'.")
    row_limit = fields.Integer(
        default=0, help='Maximum rows per call. 0 uses the default limit from the settings.')
    description = fields.Text(help='Hint shown to the AI in list_models and the odoo://models resource.')
    active = fields.Boolean(default=True)
    log_count = fields.Integer(compute='_compute_log_count', string='Tool Calls')

    _sql_constraints = [
        ('unique_model', 'unique(model_id)', 'This model is already in the MCP allowlist.'),
    ]

    @api.depends('model_id.name', 'mode')
    def _compute_display_name(self):
        return super()._compute_display_name()

    def name_get(self):
        modes = dict(self._fields['mode']._description_selection(self.env))
        return [(record.id, '%s (%s)' % (record.model_id.name or '', modes.get(record.mode, '')))
                for record in self]

    @api.depends('model_name')
    def _compute_log_count(self):
        names = [name for name in self.mapped('model_name') if name]
        counts = {}
        if names:
            groups = self.env['ydod.mcp.log']._read_group(
                [('model_name', 'in', names)], ['model_name'], ['model_name'])
            counts = {group['model_name']: group['model_name_count'] for group in groups}
        for record in self:
            record.log_count = counts.get(record.model_name, 0)

    @api.constrains('method_names', 'model_id')
    def _check_method_names(self):
        for record in self:
            if not record.method_names:
                continue
            model_cls = type(self.env[record.model_name]) if record.model_name in self.env else None
            for name in split_method_names(record.method_names):
                if name.startswith('_') or name in FORBIDDEN_METHODS:
                    raise ValidationError(_(
                        "The method '%(method)s' is private or forbidden and cannot be exposed to MCP clients.",
                        method=name))
                if model_cls is None or name in model_cls._fields or not callable(getattr(model_cls, name, None)):
                    raise ValidationError(_(
                        "The method '%(method)s' does not exist on model %(model)s.",
                        method=name, model=record.model_name))

    @api.constrains('row_limit')
    def _check_row_limit(self):
        if any(record.row_limit < 0 for record in self):
            raise ValidationError(_('The row limit cannot be negative.'))

    @api.constrains('field_ids', 'model_id')
    def _check_field_ids(self):
        for record in self:
            if record.field_ids.filtered(lambda f: f.model_id != record.model_id):
                raise ValidationError(_(
                    'Every allowed field must belong to the model %(model)s.', model=record.model_name))

    def action_view_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tool Call Log'),
            'res_model': 'ydod.mcp.log',
            'view_mode': 'tree,form',
            'domain': [('model_name', '=', self.model_name)],
            'context': {'create': False},
        }
