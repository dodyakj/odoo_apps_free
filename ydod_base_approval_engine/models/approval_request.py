from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression

STATES = [
    ('to_approve', 'To Approve'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
]


class YdodApprovalRequest(models.Model):
    _name = 'ydod.approval.request'
    _description = 'Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='/')
    res_model = fields.Char(string='Document Model', required=True, readonly=True, index=True)
    res_id = fields.Many2oneReference(string='Document ID', model_field='res_model', required=True, readonly=True, index=True)
    res_name = fields.Char(string='Document', readonly=True)
    rule_id = fields.Many2one('ydod.approval.rule', string='Rule', required=True, readonly=True, ondelete='restrict', index=True)
    requester_id = fields.Many2one('res.users', string='Requested By', readonly=True, default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', readonly=True)
    approver_user_ids = fields.Many2many('res.users', string='Approvers', readonly=True)
    approver_group_id = fields.Many2one('res.groups', string='Approver Group', readonly=True)
    state = fields.Selection(STATES, default='to_approve', required=True, tracking=True, index=True)
    decision_date = fields.Datetime(readonly=True)
    decided_by_id = fields.Many2one('res.users', string='Decided By', readonly=True)
    reject_reason = fields.Text(readonly=True)
    doc_activity_ids = fields.Many2many('mail.activity', string='Approver Activities', readonly=True)
    can_decide = fields.Boolean(compute='_compute_can_decide', search='_search_can_decide')

    def init(self):
        # one pending request per record and rule
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ydod_approval_request_pending_unique "
            "ON %s (res_model, res_id, rule_id) WHERE state = 'to_approve'" % self._table)

    @api.depends('approver_user_ids', 'approver_group_id')
    @api.depends_context('uid')
    def _compute_can_decide(self):
        user = self.env.user
        groups = user.groups_id
        for request in self:
            request.can_decide = user in request.approver_user_ids or (
                bool(request.approver_group_id) and request.approver_group_id in groups)

    def _search_can_decide(self, operator, value):
        if operator in ('in', 'not in'):
            positive = any(value) if operator == 'in' else not any(value)
        elif operator in ('=', '!='):
            positive = bool(value) if operator == '=' else not value
        else:
            raise UserError(_("Unsupported search operator on 'can decide': %s", operator))
        domain = expression.OR([
            [('approver_user_ids', 'in', [self.env.uid])],
            [('approver_group_id', 'in', self.env.user.groups_id.ids)],
        ])
        return domain if positive else ['!'] + domain

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('ydod.approval.request') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if {'res_model', 'res_id', 'rule_id'} & set(vals):
            raise UserError(_("The document and rule of an approval request cannot be changed."))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_document(self):
        self.ensure_one()
        if self.res_model not in self.env:
            return None
        document = self.env[self.res_model].sudo().browse(self.res_id).exists()
        return document or None

    def _get_approvers(self):
        self.ensure_one()
        group_users = self.approver_group_id.sudo().users.filtered(lambda u: not u.share)
        return self.approver_user_ids | group_users

    def _post_on_document(self, body, partner_ids=None):
        """Post ``body`` in the document chatter, or on the request when the model has none."""
        for request in self:
            document = request._get_document()
            target = document if document is not None and hasattr(document, 'message_post') else request.sudo()
            target.message_post(
                body=body, message_type='comment', subtype_xmlid='mail.mt_note',
                partner_ids=partner_ids or [])

    def _check_can_decide(self):
        is_manager = self.env.user.has_group('ydod_base_approval_engine.group_approval_manager')
        for request in self:
            if request.state != 'to_approve':
                raise UserError(_("Request %s is not waiting for approval.", request.name))
            if not (request.can_decide or is_manager):
                raise UserError(_("You are not an approver of request %s.", request.name))

    # ------------------------------------------------------------------
    # Request
    # ------------------------------------------------------------------
    @api.model
    def action_request_for(self, records):
        """Create a pending approval request for each record (Action menu entry)."""
        if not records:
            return False
        records.check_access_rights('write')
        records.check_access_rule('write')
        rule_by_id = self.env['ydod.approval.rule']._ydod_match_rules(records)
        missing = records.filtered(lambda r: r.id not in rule_by_id)
        if missing:
            raise UserError(_("No approval rule applies to %s.", ', '.join(missing.mapped('display_name'))))
        existing = self.sudo().search([
            ('res_model', '=', records._name),
            ('res_id', 'in', records.ids),
            ('state', 'in', ('to_approve', 'approved')),
        ])
        existing_state = {(req.res_id, req.rule_id.id): req.state for req in existing}
        has_company = 'company_id' in records._fields and records._fields['company_id'].type == 'many2one'
        vals_list = []
        for record in records.sudo():
            rule = rule_by_id[record.id]
            state = existing_state.get((record.id, rule.id))
            if state == 'approved':
                raise UserError(_("%s is already approved.", record.display_name))
            if state == 'to_approve':
                raise UserError(_("%s is already waiting for approval.", record.display_name))
            company = (record.company_id if has_company else False) or rule.company_id or self.env.company
            vals_list.append({
                'res_model': records._name,
                'res_id': record.id,
                'res_name': record.display_name,
                'rule_id': rule.id,
                'requester_id': self.env.uid,
                'company_id': company.id,
                'approver_user_ids': [(6, 0, rule.approver_user_ids.ids)],
                'approver_group_id': rule.approver_group_id.id,
            })
        requests = self.sudo().create(vals_list)
        requests._notify_approvers()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Approval requested: %s", ', '.join(requests.mapped('name'))),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _notify_approvers(self):
        for request in self:
            approvers = request._get_approvers()
            document = request._get_document()
            has_activity = document is not None and hasattr(document, 'activity_schedule')
            target = document if has_activity else request
            activities = self.env['mail.activity']
            for user in approvers:
                activities |= target.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=_("Approval %s", request.name),
                    note=_("Please approve or reject %s (rule: %s).", request.res_name, request.rule_id.name))
            request.doc_activity_ids = [(6, 0, activities.ids)]
            request.message_subscribe(partner_ids=approvers.partner_id.ids)
            if document is not None and hasattr(document, 'message_subscribe'):
                document.message_subscribe(partner_ids=approvers.partner_id.ids)
            # plain text bodies are escaped by message_post
            body = _(
                "Approval requested by %(user)s (%(ref)s, rule %(rule)s).",
                user=request.requester_id.name, ref=request.name, rule=request.rule_id.name)
            request._post_on_document(body, partner_ids=approvers.partner_id.ids)

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------
    def action_approve(self):
        self._check_can_decide()
        self.sudo().write({'state': 'approved', 'decision_date': fields.Datetime.now(), 'decided_by_id': self.env.uid})
        self._post_decision(_("Approved"))
        return True

    def action_reject(self):
        self._check_can_decide()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Reject Approval"),
            'res_model': 'ydod.approval.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_ids': [(6, 0, self.ids)]},
        }

    def _do_reject(self, reason):
        self._check_can_decide()
        self.sudo().write({
            'state': 'rejected', 'decision_date': fields.Datetime.now(),
            'decided_by_id': self.env.uid, 'reject_reason': reason,
        })
        self._post_decision(_("Rejected"), reason)
        return True

    def action_cancel(self):
        is_manager = self.env.user.has_group('ydod_base_approval_engine.group_approval_manager')
        for request in self:
            if request.state != 'to_approve':
                raise UserError(_("Only pending requests can be cancelled."))
            if request.requester_id != self.env.user and not is_manager:
                raise UserError(_("Only the requester or an Approval Manager can cancel %s.", request.name))
        self.sudo().doc_activity_ids.unlink()
        self.sudo().write({'state': 'cancelled', 'decision_date': fields.Datetime.now(), 'decided_by_id': self.env.uid})
        self._post_decision(_("Cancelled"))
        return True

    def _post_decision(self, label, reason=None):
        by_document = defaultdict(lambda: self.browse())
        for request in self:
            by_document[(request.res_model, request.res_id)] |= request
        for requests in by_document.values():
            text = _(
                "%(decision)s by %(user)s (%(refs)s)",
                decision=label, user=self.env.user.name, refs=', '.join(requests.mapped('name')))
            if reason:
                text += " - " + _("Reason: %s", reason)
            requests[0]._post_on_document(text, partner_ids=requests.requester_id.partner_id.ids)
        activities = self.sudo().doc_activity_ids
        if activities:
            activities.action_feedback(feedback=reason or label)

    def action_open_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }
