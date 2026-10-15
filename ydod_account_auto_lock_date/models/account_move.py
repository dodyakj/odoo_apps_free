from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _check_fiscal_lock_dates(self):
        if self.env.user.has_group('ydod_account_auto_lock_date.group_account_lock_date_bypass'):
            for move in self:
                hard_lock = move.company_id.user_hard_lock_date
                if hard_lock and move.date and move.date <= hard_lock:
                    return super()._check_fiscal_lock_dates()
            return True
        return super()._check_fiscal_lock_dates()

    def action_post(self):
        res = super().action_post()
        if self.env.user.has_group('ydod_account_auto_lock_date.group_account_lock_date_bypass'):
            for move in self.filtered(lambda m: m.state == 'posted'):
                company = move.company_id
                company_locks = [
                    (company.fiscalyear_lock_date, self.env._('Global Lock Date')),
                    (company.sale_lock_date if move.journal_id and move.journal_id.type == 'sale' else None, self.env._('Sales Lock Date')),
                    (company.purchase_lock_date if move.journal_id and move.journal_id.type == 'purchase' else None, self.env._('Purchase Lock Date')),
                    (company.tax_lock_date if move._affect_tax_report() else None, self.env._('Tax Lock Date')),
                ]
                active_locks = [(ld, name) for ld, name in company_locks if ld and move.date and move.date <= ld]
                if active_locks:
                    lock_desc = ", ".join(f"{name} ({ld})" for ld, name in active_locks)
                    move.message_post(
                        body=self.env._(
                            "<strong>Lock Date Bypass:</strong> Journal entry posted on %(date)s in locked period (%(locks)s) by authorized user %(user)s.",
                            date=move.date,
                            locks=lock_desc,
                            user=self.env.user.display_name,
                        ),
                        subtype_xmlid="mail.mt_note",
                    )
                    self.env['account.lock.date.audit'].sudo().create({
                        'company_id': company.id,
                        'user_id': self.env.user.id,
                        'date': fields.Datetime.now(),
                        'lock_type': 'all',
                        'old_date': active_locks[0][0],
                        'new_date': move.date,
                        'action_type': 'bypass_entry',
                        'move_id': move.id,
                        'reason': self.env._("Role bypass posting in closed period (%s)", lock_desc),
                    })
        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _check_tax_lock_date(self):
        if self.env.user.has_group('ydod_account_auto_lock_date.group_account_lock_date_bypass'):
            return True
        return super()._check_tax_lock_date()
