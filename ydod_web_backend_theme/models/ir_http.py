from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super().session_info()
        user = self.env.user
        if user and not user._is_public():
            result.update(user._ydod_session_values())
        return result
