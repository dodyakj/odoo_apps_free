from datetime import date, timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError

LOCK_DATE_FIELDS = [
    'fiscalyear_lock_date',
    'tax_lock_date',
    'sale_lock_date',
    'purchase_lock_date',
    'hard_lock_date',
]

FIELD_TO_TYPE = {
    'sale_lock_date': 'sale',
    'purchase_lock_date': 'purchase',
    'tax_lock_date': 'tax',
    'fiscalyear_lock_date': 'fiscalyear',
    'hard_lock_date': 'hard',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    auto_lock_enabled = fields.Boolean(
        string="Enable Scheduled Auto-Lock",
        default=False,
        help="Automatically advance accounting lock dates on a recurring monthly schedule.",
    )
    auto_lock_day = fields.Integer(
        string="Closing Day of Month",
        default=10,
        help="Day of the month (1-28) on which the previous month's accounting period is locked.",
    )
    auto_lock_target = fields.Selection([
        ('sale_purchase', 'Sales & Purchases (Period Lock)'),
        ('all_soft', 'All Soft Locks (Sales, Purchases, Tax, Fiscal Year)'),
        ('fiscalyear', 'Fiscal Year / Global Lock Only'),
        ('custom', 'Custom Selection'),
    ], string="Lock Levels to Advance", default='sale_purchase', required=True)
    auto_lock_sale = fields.Boolean(
        string="Auto-Lock Sales",
        default=True,
    )
    auto_lock_purchase = fields.Boolean(
        string="Auto-Lock Purchases",
        default=True,
    )
    auto_lock_tax = fields.Boolean(
        string="Auto-Lock Taxes",
        default=False,
    )
    auto_lock_fiscalyear = fields.Boolean(
        string="Auto-Lock Global / Fiscal Year",
        default=False,
    )
    auto_lock_last_run = fields.Datetime(
        string="Last Auto-Lock Execution",
        readonly=True,
        copy=False,
    )
    auto_lock_audit_ids = fields.One2many(
        'account.lock.date.audit',
        'company_id',
        string="Lock Date Audit Logs",
    )
    auto_lock_audit_count = fields.Integer(
        string="Audit Log Count",
        compute="_compute_auto_lock_audit_count",
    )

    @api.constrains('auto_lock_day', 'auto_lock_enabled')
    def _check_auto_lock_day(self):
        for company in self:
            if company.auto_lock_enabled and (company.auto_lock_day < 1 or company.auto_lock_day > 28):
                raise ValidationError(self.env._("The Closing Day of Month must be between 1 and 28."))

    @api.depends('auto_lock_audit_ids')
    def _compute_auto_lock_audit_count(self):
        audit_data = self.env['account.lock.date.audit']._read_group(
            domain=[('company_id', 'in', self.ids)],
            groupby=['company_id'],
            aggregates=['__count'],
        )
        count_map = {company.id: count for company, count in audit_data}
        for company in self:
            company.auto_lock_audit_count = count_map.get(company.id, 0)

    def action_view_lock_audit_logs(self):
        self.ensure_one()
        return {
            'name': self.env._("Lock Date Audit Trail"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.lock.date.audit',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', self.id)],
            'context': {'default_company_id': self.id},
        }

    def _get_auto_lock_target_date(self, today=None):
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        if today.day >= self.auto_lock_day:
            first_day_current_month = today.replace(day=1)
            return first_day_current_month - timedelta(days=1)
        else:
            first_day_current_month = today.replace(day=1)
            last_day_prev_month = first_day_current_month - timedelta(days=1)
            first_day_prev_month = last_day_prev_month.replace(day=1)
            return first_day_prev_month - timedelta(days=1)

    def _get_auto_lock_fields_to_update(self):
        self.ensure_one()
        if self.auto_lock_target == 'sale_purchase':
            return ['sale_lock_date', 'purchase_lock_date']
        elif self.auto_lock_target == 'all_soft':
            return ['sale_lock_date', 'purchase_lock_date', 'tax_lock_date', 'fiscalyear_lock_date']
        elif self.auto_lock_target == 'fiscalyear':
            return ['fiscalyear_lock_date']
        elif self.auto_lock_target == 'custom':
            res = []
            if self.auto_lock_sale:
                res.append('sale_lock_date')
            if self.auto_lock_purchase:
                res.append('purchase_lock_date')
            if self.auto_lock_tax:
                res.append('tax_lock_date')
            if self.auto_lock_fiscalyear:
                res.append('fiscalyear_lock_date')
            return res
        return []

    def action_run_auto_lock(self):
        self._execute_auto_lock(is_manual=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._("Auto-Lock Completed"),
                'message': self.env._("Accounting lock dates evaluated and updated according to closing rules."),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def _cron_auto_lock_dates(self):
        companies = self.search([('auto_lock_enabled', '=', True)])
        today = fields.Date.context_today(self)
        for company in companies:
            if today.day >= company.auto_lock_day:
                company._execute_auto_lock(is_manual=False)

    def _execute_auto_lock(self, is_manual=False):
        for company in self:
            target_date = company._get_auto_lock_target_date()
            fields_to_check = company._get_auto_lock_fields_to_update()
            vals = {}
            for fname in fields_to_check:
                current_val = company[fname]
                if not current_val or target_date > current_val:
                    vals[fname] = target_date

            if vals:
                reason = (
                    self.env._("Manual Auto-Lock Trigger")
                    if is_manual
                    else self.env._("Scheduled Monthly Auto-Lock (Day %s)", company.auto_lock_day)
                )
                ctx = {
                    'auto_lock_cron': not is_manual,
                    'auto_lock_manual': is_manual,
                    'lock_change_reason': reason,
                }
                try:
                    company.with_context(**ctx).write(vals)
                    company.auto_lock_last_run = fields.Datetime.now()
                except Exception as e:
                    company.message_post(
                        body=self.env._(
                            "<strong>Auto-Lock Failed:</strong> Could not update lock dates to %s: %s",
                            target_date, str(e)
                        ),
                        subtype_xmlid="mail.mt_note",
                    )
            else:
                company.auto_lock_last_run = fields.Datetime.now()

    def write(self, vals):
        field_labels = {
            'sale_lock_date': self.env._('Sales Lock Date'),
            'purchase_lock_date': self.env._('Purchase Lock Date'),
            'tax_lock_date': self.env._('Tax Return Lock Date'),
            'fiscalyear_lock_date': self.env._('Global / Fiscal Year Lock Date'),
            'hard_lock_date': self.env._('Hard Lock Date'),
        }

        tracked_changes = {}
        for company in self:
            for fname in LOCK_DATE_FIELDS:
                if fname in vals:
                    old_date = company[fname]
                    new_date = fields.Date.to_date(vals[fname])
                    if old_date != new_date:
                        tracked_changes.setdefault(company.id, []).append((fname, old_date, new_date))

        res = super().write(vals)

        for company in self:
            changes = tracked_changes.get(company.id, [])
            for fname, old_val, new_val in changes:
                is_cron = self.env.context.get('auto_lock_cron')
                is_manual_run = self.env.context.get('auto_lock_manual')
                reason = self.env.context.get('lock_change_reason') or (
                    self.env._("Scheduled Auto-Lock") if is_cron
                    else (self.env._("Manual Auto-Lock Run") if is_manual_run else self.env._("Manual Setting Change"))
                )
                action_type = 'auto_cron' if is_cron else ('manual_run' if is_manual_run else 'manual_update')

                self.env['account.lock.date.audit'].sudo().create({
                    'company_id': company.id,
                    'user_id': self.env.user.id,
                    'date': fields.Datetime.now(),
                    'field_name': fname,
                    'lock_type': FIELD_TO_TYPE.get(fname, 'sale'),
                    'old_date': old_val,
                    'new_date': new_val,
                    'action_type': action_type,
                    'reason': reason,
                })

                label = field_labels.get(fname, fname)
                company.message_post(
                    body=self.env._(
                        "<strong>Accounting Lock Date Updated</strong><br/>"
                        "<b>%(label)s</b> changed from %(old_date)s to <b>%(new_date)s</b>.<br/>"
                        "<b>Source:</b> %(action_source)s | <b>User:</b> %(user)s<br/>"
                        "<b>Reason:</b> %(reason)s",
                        label=label,
                        old_date=old_val or self.env._("None"),
                        new_date=new_val or self.env._("None"),
                        action_source=dict(self.env['account.lock.date.audit']._fields['action_type'].selection).get(action_type, action_type),
                        user=self.env.user.display_name,
                        reason=reason,
                    ),
                    subtype_xmlid="mail.mt_note",
                )
        return res

    def _get_user_lock_date(self, soft_lock_date_field, ignore_exceptions=False):
        if not ignore_exceptions and self.env.user.has_group('ydod_account_auto_lock_date.group_account_lock_date_bypass'):
            return date.min
        return super()._get_user_lock_date(soft_lock_date_field, ignore_exceptions=ignore_exceptions)

    def _get_lock_date_violations(self, accounting_date, fiscalyear=True, sale=True, purchase=True, tax=True, hard=True):
        if self.env.user.has_group('ydod_account_auto_lock_date.group_account_lock_date_bypass'):
            return super()._get_lock_date_violations(
                accounting_date,
                fiscalyear=False,
                sale=False,
                purchase=False,
                tax=False,
                hard=hard,
            )
        return super()._get_lock_date_violations(
            accounting_date,
            fiscalyear=fiscalyear,
            sale=sale,
            purchase=purchase,
            tax=tax,
            hard=hard,
        )
