import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    def _create_demo_data(self):
        """On a fresh database the chart of accounts is installed after this module:
        load the asset demo data once the company has its journals and accounts."""
        res = super()._create_demo_data()
        module = self.env.ref('base.module_ydod_account_asset_core', raise_if_not_found=False)
        if module and module.demo:
            try:
                with self.env.cr.savepoint():
                    self.env['ydod.asset']._load_demo_data()
            except Exception:
                _logger.warning('Error while loading asset demo data', exc_info=True)
        return res
