from odoo import _, api, fields, models
from odoo.exceptions import UserError


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    ydod_menu_access_ids = fields.One2many(
        'ydod.menu.access', 'menu_id', string='Menu Restrictions',
        help="Users and groups that cannot see this menu.")
    ydod_menu_access_count = fields.Integer(
        string='Restriction Count', compute='_compute_ydod_menu_access_count')

    @api.depends('ydod_menu_access_ids')
    def _compute_ydod_menu_access_count(self):
        for menu in self:
            menu.ydod_menu_access_count = len(menu.ydod_menu_access_ids)

    @api.model
    def _ydod_restricted_menu_ids(self):
        """Menu ids hidden for the current user (one grouped query).

        System administrators are never restricted.
        """
        user = self.env.user
        if not user or user._is_system():
            return []
        domain = [
            ('company_id', 'in', user.sudo().company_ids.ids),
            '|', ('user_id', '=', user.id), ('group_id', 'in', user.groups_id.ids),
        ]
        rows = self.env['ydod.menu.access'].sudo().read_group(domain, ['menu_id'], ['menu_id'])
        return [row['menu_id'][0] for row in rows if row['menu_id']]

    def _load_menus_blacklist(self):
        return super()._load_menus_blacklist() + self._ydod_restricted_menu_ids()

    @api.model
    @api.returns('self')
    def get_user_roots(self):
        roots = super().get_user_roots()
        restricted = set(self._ydod_restricted_menu_ids())
        if restricted:
            roots = roots.filtered(lambda menu: menu.id not in restricted)
        return roots

    def action_ydod_cascade_restrictions(self):
        """Copy every restriction of the selected menus to all their sub-menus."""
        Access = self.env['ydod.menu.access']
        sources = Access.search([('menu_id', 'in', self.ids)])
        if not sources:
            raise UserError(_(
                "The selected menus have no restriction to cascade. "
                "Add a user or a group in the Restrict Access tab first."))
        all_menus = self.with_context(**{'ir.ui.menu.full_list': True})
        descendants = all_menus.search([('id', 'child_of', self.ids), ('id', 'not in', self.ids)])
        existing = {
            (rule.user_id.id, rule.group_id.id, rule.menu_id.id, rule.company_id.id)
            for rule in Access.search([('menu_id', 'in', descendants.ids)])
        }
        vals_list = []
        for source in sources:
            prefix = source.menu_id.parent_path
            for child in descendants:
                key = (source.user_id.id, source.group_id.id, child.id, source.company_id.id)
                if key in existing or not child.parent_path.startswith(prefix):
                    continue
                existing.add(key)
                vals_list.append({
                    'user_id': source.user_id.id,
                    'group_id': source.group_id.id,
                    'menu_id': child.id,
                    'company_id': source.company_id.id,
                    'cascade': True,
                })
        Access.create(vals_list)
        return True
