from odoo import api, models

LINE_SEARCH_PARAM = "ydod_web_x2many_line_search.enabled"


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def _x2many_line_search_enabled(self):
        """Return whether the x2many line search box is globally enabled."""
        return self.env["ir.config_parameter"].sudo().get_param(LINE_SEARCH_PARAM, "False") == "True"

    def session_info(self):
        result = super().session_info()
        if self.env.user and self.env.user._is_internal():
            result["x2many_line_search"] = self._x2many_line_search_enabled()
        return result
