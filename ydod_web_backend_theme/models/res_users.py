from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    ydod_app_bar_mode = fields.Selection(
        [('expanded', 'Expanded'), ('icons', 'Icons only'), ('hidden', 'Hidden')],
        string='App Bar', required=True, default='expanded', user_writeable=True,
        help='How the side app bar is displayed in the backend.')
    ydod_app_order = fields.Json(
        string='App Order', default=lambda self: [], user_writeable=True,
        help='Ordered list of root menu ids shown in the side app bar.')

    @api.model
    def ydod_set_app_order(self, menu_ids):
        """Store the app order of the current user, silently dropping stale ids."""
        if not isinstance(menu_ids, (list, tuple)):
            menu_ids = []
        visible_roots = set(self.env['ir.ui.menu'].get_user_roots().ids)
        order = []
        for menu_id in menu_ids:
            if isinstance(menu_id, int) and not isinstance(menu_id, bool) \
                    and menu_id in visible_roots and menu_id not in order:
                order.append(menu_id)
        self.env.user.write({'ydod_app_order': order})
        return order

    def _ydod_session_values(self):
        """Theme values sent to the web client in session_info."""
        self.ensure_one()
        user = self.sudo()
        companies = (user.company_ids | self.env.company).with_context(bin_size=True)
        themes = {
            str(company.id): {
                'has_background': bool(company.ydod_background_image),
                'background_color': company.ydod_background_color or '#714B67',
                'unique': company.write_date and int(company.write_date.timestamp()) or 0,
            }
            for company in companies
        }
        active = themes.get(str(self.env.company.id), {})
        return {
            'ydod_app_bar_mode': user.ydod_app_bar_mode or 'expanded',
            'ydod_app_order': user.ydod_app_order or [],
            'ydod_has_background': active.get('has_background', False),
            'ydod_background_color': active.get('background_color', '#714B67'),
            'ydod_company_themes': themes,
        }
