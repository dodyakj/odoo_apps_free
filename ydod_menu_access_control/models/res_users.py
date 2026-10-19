from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    ydod_menu_access_ids = fields.One2many(
        'ydod.menu.access', 'user_id', string='Hidden Menus',
        help="Menus this user cannot see.")
    ydod_menu_access_count = fields.Integer(
        string='Hidden Menu Count', compute='_compute_ydod_menu_access_count')

    @api.depends('ydod_menu_access_ids')
    def _compute_ydod_menu_access_count(self):
        for user in self:
            user.ydod_menu_access_count = len(user.ydod_menu_access_ids)

    def action_ydod_open_copy_wizard(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'ydod_menu_access_control.action_ydod_menu_access_copy')
        action['context'] = {'default_source_user_id': self.id}
        return action

    def action_ydod_view_menu_access(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'ydod_menu_access_control.action_ydod_menu_access')
        action['domain'] = [('user_id', '=', self.id)]
        action['context'] = {'default_user_id': self.id}
        return action
