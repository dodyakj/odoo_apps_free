from odoo import _, api, fields, models
from odoo.exceptions import UserError


class YdodMenuAccessCopy(models.TransientModel):
    _name = 'ydod.menu.access.copy'
    _description = 'Copy Hidden Menus'

    source_user_id = fields.Many2one(
        'res.users', string='Copy From', required=True, domain=[('share', '=', False)],
        default=lambda self: self._default_source_user_id())
    source_menu_access_count = fields.Integer(
        string='Hidden Menus to Copy', related='source_user_id.ydod_menu_access_count')
    target_user_ids = fields.Many2many(
        'res.users', 'ydod_menu_access_copy_user_rel', 'wizard_id', 'user_id',
        string='Copy To', required=True,
        domain="[('share', '=', False), ('id', '!=', source_user_id)]")
    overwrite = fields.Boolean(
        string='Replace Existing Restrictions',
        help="Remove the current hidden menus of the target users before copying.")

    @api.model
    def _default_source_user_id(self):
        if self.env.context.get('active_model') == 'res.users':
            return self.env.context.get('active_id')
        return False

    def action_copy(self):
        self.ensure_one()
        sources = self.source_user_id.ydod_menu_access_ids
        if not sources:
            raise UserError(_(
                "%(user)s has no hidden menu to copy.", user=self.source_user_id.name))
        targets = self.target_user_ids - self.source_user_id
        Access = self.env['ydod.menu.access']
        current = Access.search_fetch(
            [('user_id', 'in', targets.ids)], ['user_id', 'menu_id', 'company_id'])
        existing = set()
        if self.overwrite:
            current.unlink()
        else:
            existing = {(r.user_id.id, r.menu_id.id, r.company_id.id) for r in current}
        vals_list = []
        for target in targets:
            for source in sources:
                key = (target.id, source.menu_id.id, source.company_id.id)
                if key in existing:
                    continue
                existing.add(key)
                vals_list.append({
                    'user_id': target.id,
                    'menu_id': source.menu_id.id,
                    'company_id': source.company_id.id,
                    'cascade': source.cascade,
                })
        Access.create(vals_list)
        return {'type': 'ir.actions.act_window_close'}
