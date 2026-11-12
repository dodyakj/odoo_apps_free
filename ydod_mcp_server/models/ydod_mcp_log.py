from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

PURGE_BATCH = 10000


class YdodMcpLog(models.Model):
    _name = 'ydod.mcp.log'
    _description = 'MCP Tool Call Log'
    _order = 'date desc, id desc'
    _rec_name = 'jsonrpc_method'

    date = fields.Datetime(required=True, readonly=True, default=fields.Datetime.now, index=True)
    user_id = fields.Many2one('res.users', string='User', readonly=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    api_key_id = fields.Many2one('res.users.apikeys', string='API Key', readonly=True, ondelete='set null')
    session_id = fields.Char(string='Session', readonly=True, index=True)
    client_name = fields.Char(readonly=True)
    client_version = fields.Char(readonly=True)
    jsonrpc_method = fields.Char(string='JSON-RPC Method', readonly=True)
    tool = fields.Char(readonly=True, index=True)
    model_name = fields.Char(string='Model', readonly=True, index=True)
    arguments = fields.Text(readonly=True)
    duration_ms = fields.Integer(string='Duration (ms)', readonly=True, aggregator='avg')
    result_summary = fields.Char(readonly=True)
    status = fields.Selection(
        [('success', 'Success'), ('error', 'Error'), ('denied', 'Denied'), ('rate_limited', 'Rate Limited')],
        required=True, readonly=True, index=True, default='success')
    error_message = fields.Text(readonly=True)

    _key_date_idx = models.Index('(api_key_id, date)')
    _session_method_idx = models.Index('(session_id, jsonrpc_method)')

    def write(self, vals):
        raise UserError(self.env._('MCP tool call logs are immutable and cannot be modified.'))

    @api.model
    def _cron_purge(self):
        days = self.env['ir.config_parameter'].sudo().get_int('ydod_mcp_server.log_retention_days', 30)
        if days <= 0:
            return
        limit_date = fields.Datetime.now() - timedelta(days=days)
        logs = self.sudo().with_context(active_test=False)
        while True:
            batch = logs.search([('date', '<', limit_date)], limit=PURGE_BATCH)
            if not batch:
                break
            batch.unlink()
