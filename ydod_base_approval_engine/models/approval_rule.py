import functools
import types
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import datetime, safe_eval, time

FORBIDDEN_METHODS = {'create', 'write', 'unlink', 'copy', 'read', 'search', 'browse', 'name_create'}
REQUEST_ACTION_CODE = "action = env['ydod.approval.request'].action_request_for(records)"


def _make_guard(method_name, origin):
    """Wrap ``origin`` so that it only runs on records that passed approval."""
    @functools.wraps(origin)
    def guard(self, *args, **kwargs):
        if not self.env.context.get('ydod_approval_checked'):
            self.env['ydod.approval.rule']._ydod_check_approval(self, method_name)
        return origin(self.with_context(ydod_approval_checked=True), *args, **kwargs)
    guard._ydod_approval_guard = True
    guard.origin = origin
    return guard


class YdodApprovalRule(models.Model):
    _name = 'ydod.approval.rule'
    _description = 'Approval Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10, help="Lowest first: the first matching rule applies.")
    active = fields.Boolean(default=True)
    model_id = fields.Many2one(
        'ir.model', string='Model', required=True, ondelete='cascade',
        domain=[('transient', '=', False)])
    model_name = fields.Char(related='model_id.model', store=True, index=True, string='Model Name')
    domain = fields.Char(default='[]', help="Only documents matching this condition need approval.")
    method_names = fields.Char(
        string='Guarded Methods', required=True,
        help="Comma-separated public methods blocked until approval, e.g. action_confirm,action_post")
    approver_user_ids = fields.Many2many('res.users', string='Approver Users', domain=[('share', '=', False)])
    approver_group_id = fields.Many2one('res.groups', string='Approver Group')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
        help="Leave empty to apply the rule to all companies.")
    server_action_id = fields.Many2one('ir.actions.server', string='Request Action', readonly=True, ondelete='set null')
    request_ids = fields.One2many('ydod.approval.request', 'rule_id', string='Requests')
    note = fields.Text()
    request_pending_count = fields.Integer(compute='_compute_request_counts', string='Pending')
    request_decided_count = fields.Integer(compute='_compute_request_counts', string='Decided')

    def _compute_request_counts(self):
        pending, decided = defaultdict(int), defaultdict(int)
        saved = self.filtered('id')
        if saved:
            groups = self.env['ydod.approval.request'].read_group(
                [('rule_id', 'in', saved.ids)], ['rule_id', 'state'], ['rule_id', 'state'], lazy=False)
            for group in groups:
                rule_id, state, count = group['rule_id'][0], group['state'], group['__count']
                if state == 'to_approve':
                    pending[rule_id] += count
                elif state in ('approved', 'rejected'):
                    decided[rule_id] += count
        for rule in self:
            rule.request_pending_count = pending[rule.id]
            rule.request_decided_count = decided[rule.id]

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('approver_user_ids', 'approver_group_id')
    def _check_approvers(self):
        for rule in self:
            if not rule.approver_user_ids and not rule.approver_group_id:
                raise ValidationError(_("Rule '%s' needs at least one approver user or an approver group.", rule.name))

    @api.constrains('method_names', 'model_id')
    def _check_method_names(self):
        for rule in self:
            names = rule._ydod_method_list()
            if not names:
                raise ValidationError(_("Rule '%s' must guard at least one method.", rule.name))
            # ir.model is only readable by administrators: read the target model in sudo
            model_name = rule.sudo().model_id.model
            Model = self.env[model_name]
            for name in names:
                if name.startswith('_') or name in FORBIDDEN_METHODS or not callable(getattr(Model, name, None)):
                    raise ValidationError(_(
                        "'%(method)s' is not a public method of model %(model)s that can be guarded.",
                        method=name, model=model_name))

    @api.constrains('domain', 'model_id')
    def _check_domain(self):
        for rule in self:
            try:
                domain = rule._ydod_eval_domain()
                if not isinstance(domain, (list, tuple)):
                    raise ValueError("not a list")
                self.env[rule.sudo().model_id.model].sudo()._search(list(domain))
            except Exception as error:
                raise ValidationError(_("Invalid domain on rule '%(rule)s': %(error)s", rule=rule.name, error=error)) from error

    # ------------------------------------------------------------------
    # CRUD and registry
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        self._sync_request_actions()
        self._update_registry()
        return rules

    def write(self, vals):
        res = super().write(vals)
        if {'active', 'model_id', 'method_names'} & set(vals):
            self._sync_request_actions()
            self._update_registry()
        return res

    def unlink(self):
        res = super().unlink()
        self._sync_request_actions()
        self._update_registry()
        return res

    def _update_registry(self):
        """Re-install the method guards and notify the other workers."""
        if self.env.registry.ready and not self.env.context.get('import_file'):
            # re-sync the model patches, and notify other workers (as base_automation);
            # unchanged guards are kept so model classes are only touched when needed
            self._ydod_install_guards(self._ydod_guarded_methods())
            self.env.registry.registry_invalidated = True

    def _ydod_guarded_methods(self):
        methods_by_model = defaultdict(set)
        for rule in self.sudo().search([]):
            methods_by_model[rule.model_name].update(rule._ydod_method_list())
        return methods_by_model

    def _register_hook(self):
        super()._register_hook()
        self._ydod_install_guards(self._ydod_guarded_methods())

    def _ydod_install_guards(self, methods_by_model):
        """Remove the guards no rule needs any more, then add the missing ones."""
        for Model in self.env.registry.values():
            wanted = methods_by_model.get(Model._name, set())
            for name, attr in list(vars(Model).items()):
                if name not in wanted and isinstance(attr, types.FunctionType) \
                        and getattr(attr, '_ydod_approval_guard', False):
                    delattr(Model, name)
        for model_name, method_names in methods_by_model.items():
            Model = self.env.registry.get(model_name)
            if Model is None:
                continue
            for method_name in method_names:
                origin = getattr(Model, method_name, None)
                if callable(origin) and not getattr(origin, '_ydod_approval_guard', False):
                    setattr(Model, method_name, _make_guard(method_name, origin))

    def _unregister_hook(self):
        super()._unregister_hook()
        for Model in self.env.registry.values():
            for name, attr in list(vars(Model).items()):
                if isinstance(attr, types.FunctionType) and getattr(attr, '_ydod_approval_guard', False):
                    delattr(Model, name)

    @api.model
    def _sync_request_actions(self):
        """Keep one 'Request Approval' server action per model with active rules."""
        rules = self.env['ydod.approval.rule'].sudo().search([])
        Action = self.env['ir.actions.server'].sudo()
        actions = Action.search([('state', '=', 'code'), ('code', '=', REQUEST_ACTION_CODE)])
        models_needed = rules.model_id
        (actions.filtered(lambda a: a.model_id not in models_needed)).unlink()
        action_by_model = {a.model_id.id: a for a in actions.exists()}
        missing = models_needed.filtered(lambda m: m.id not in action_by_model)
        if missing:
            new_actions = Action.create([{
                'name': _("Request Approval"),
                'model_id': model.id,
                'binding_model_id': model.id,
                'binding_view_types': 'list,form',
                'state': 'code',
                'code': REQUEST_ACTION_CODE,
            } for model in missing])
            # noupdate xml ids: kept on upgrade, removed with the module on uninstall
            self.env['ir.model.data'].sudo().create([{
                'module': 'ydod_base_approval_engine',
                'name': 'request_action_%s_%s' % (action.model_id.model.replace('.', '_'), action.id),
                'model': 'ir.actions.server',
                'res_id': action.id,
                'noupdate': True,
            } for action in new_actions])
            action_by_model.update({a.model_id.id: a for a in new_actions})
        for rule in rules:
            action = action_by_model[rule.model_id.id]
            if rule.server_action_id != action:
                rule.server_action_id = action
        archived = self.env['ydod.approval.rule'].sudo().with_context(active_test=False).search(
            [('active', '=', False), ('server_action_id', '!=', False)])
        archived.server_action_id = False

    # ------------------------------------------------------------------
    # Matching and guard
    # ------------------------------------------------------------------
    def _ydod_method_list(self):
        self.ensure_one()
        return [name.strip() for name in (self.method_names or '').split(',') if name.strip()]

    def _ydod_eval_domain(self):
        self.ensure_one()
        return safe_eval(self.domain or '[]', {
            'uid': self.env.uid,
            'user': self.env.user,
            'datetime': datetime,
            'time': time,
            'context_today': lambda: fields.Date.context_today(self),
        })

    @api.model
    def _ydod_match_rules(self, records):
        """Return {record id: first matching active rule} for ``records``."""
        result = {}
        remaining = records.sudo()
        rules = self.sudo().search([('model_name', '=', records._name)], order='sequence, id')
        has_company = 'company_id' in records._fields and records._fields['company_id'].type == 'many2one'
        for rule in rules:
            if not remaining:
                break
            candidates = remaining
            if rule.company_id:
                if has_company:
                    candidates = remaining.filtered(lambda r: (r.company_id or self.env.company) == rule.company_id)
                elif rule.company_id != self.env.company:
                    continue
            matched = candidates.filtered_domain(rule._ydod_eval_domain())
            for record in matched:
                result[record.id] = rule
            remaining -= matched
        return result

    @api.model
    def _ydod_check_approval(self, records, method_name):
        records = records.browse([rid for rid in records._ids if isinstance(rid, int)])
        if not records:
            return
        guarded = {
            rid: rule for rid, rule in self._ydod_match_rules(records).items()
            if method_name in rule._ydod_method_list()
        }
        if not guarded:
            return
        approved = self.env['ydod.approval.request'].sudo().search([
            ('res_model', '=', records._name),
            ('res_id', 'in', list(guarded)),
            ('rule_id', 'in', list({rule.id for rule in guarded.values()})),
            ('state', '=', 'approved'),
        ])
        approved_keys = {(req.res_id, req.rule_id.id) for req in approved}
        blocked = [rid for rid, rule in guarded.items() if (rid, rule.id) not in approved_keys]
        if blocked:
            record = records.browse(blocked[0]).sudo()
            raise UserError(_(
                "This document requires approval: '%(document)s' must be approved under rule "
                "'%(rule)s' before it can be processed. Use Action > Request Approval and wait "
                "for an approver's decision.",
                document=record.display_name, rule=guarded[blocked[0]].name))

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def _action_view_requests(self, states):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Approval Requests"),
            'res_model': 'ydod.approval.request',
            'view_mode': 'tree,kanban,form',
            'domain': [('rule_id', '=', self.id), ('state', 'in', states)],
            'context': {'create': False},
        }

    def action_view_pending(self):
        return self._action_view_requests(['to_approve'])

    def action_view_decided(self):
        return self._action_view_requests(['approved', 'rejected'])
