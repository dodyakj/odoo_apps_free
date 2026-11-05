from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    x2many_line_search_enabled = fields.Boolean(
        string="Search box on x2many lists",
        config_parameter="ydod_web_x2many_line_search.enabled",
        help="Show a search box above every one2many / many2many list in form views for all users. "
             "Takes effect after the browser is reloaded.",
    )
