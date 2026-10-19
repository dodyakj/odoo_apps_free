from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class YdodMenuAccess(models.Model):
    _name = 'ydod.menu.access'
    _description = 'Menu Restriction'
    _order = 'menu_id, user_id, group_id, id'
    _rec_name = 'menu_id'

    user_id = fields.Many2one(
        'res.users', string='User', ondelete='cascade', index=True,
        domain=[('share', '=', False)],
        help="User who must not see the menu. Leave empty when restricting a group.")
    group_id = fields.Many2one(
        'res.groups', string='Group', ondelete='cascade', index=True,
        help="Group whose members must not see the menu. Leave empty when restricting a user.")
    menu_id = fields.Many2one(
        'ir.ui.menu', string='Menu', required=True, ondelete='cascade', index=True,
        help="Menu to hide. Its sub-menus disappear with it in the web client.")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True, ondelete='cascade',
        default=lambda self: self.env.company,
        help="The rule only applies to users who have access to this company.")
    cascade = fields.Boolean(
        string='Inherited from Parent', default=False, readonly=True,
        help="Set automatically when the rule was created by the Cascade to Sub-Menus action.")

    def name_get(self):
        result = []
        for rule in self:
            target = rule.user_id.name or rule.group_id.full_name or ''
            result.append((rule.id, "%s - %s" % (rule.menu_id.complete_name or '', target)))
        return result

    @api.constrains('user_id', 'group_id', 'menu_id', 'company_id')
    def _check_target_and_unique(self):
        for rule in self:
            if bool(rule.user_id) == bool(rule.group_id):
                raise ValidationError(_(
                    "A menu restriction must target either a user or a group (exactly one of them)."))
        others = self.sudo().search(
            [('id', 'not in', self.ids), ('menu_id', 'in', self.menu_id.ids),
             ('company_id', 'in', self.company_id.ids)])
        seen = {(o.user_id.id, o.group_id.id, o.menu_id.id, o.company_id.id) for o in others}
        for rule in self:
            key = (rule.user_id.id, rule.group_id.id, rule.menu_id.id, rule.company_id.id)
            if key in seen:
                raise ValidationError(_(
                    "The menu %(menu)s is already hidden for %(target)s in company %(company)s.",
                    menu=rule.menu_id.complete_name,
                    target=rule.user_id.name or rule.group_id.full_name,
                    company=rule.company_id.name))
            seen.add(key)

    def _ydod_invalidate_menu_cache(self):
        # load_menus() results are cached per user: drop them so changes apply immediately.
        self.env['ir.ui.menu'].clear_caches()

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules._ydod_invalidate_menu_cache()
        return rules

    def write(self, vals):
        result = super().write(vals)
        self._ydod_invalidate_menu_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self._ydod_invalidate_menu_cache()
        return result
