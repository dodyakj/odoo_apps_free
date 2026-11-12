import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ydod_mcp_enabled = fields.Boolean(string='Enable MCP Server', config_parameter='ydod_mcp_server.enabled')
    ydod_mcp_default_limit = fields.Integer(
        string='Default Row Limit', config_parameter='ydod_mcp_server.default_limit', default=80)
    ydod_mcp_rate_limit = fields.Integer(
        string='Rate Limit (calls/minute per key)', config_parameter='ydod_mcp_server.rate_limit', default=60)
    ydod_mcp_log_retention_days = fields.Integer(
        string='Log Retention (days)', config_parameter='ydod_mcp_server.log_retention_days', default=30)
    ydod_mcp_endpoint_url = fields.Char(string='Endpoint URL', compute='_compute_ydod_mcp_endpoint')
    ydod_mcp_client_snippet = fields.Text(string='Client Configuration', compute='_compute_ydod_mcp_endpoint')

    @api.depends('company_id')
    def _compute_ydod_mcp_endpoint(self):
        base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url').rstrip('/')
        url = base_url + '/mcp'
        desktop = json.dumps({
            'mcpServers': {
                'odoo': {
                    'command': 'npx',
                    'args': ['-y', 'mcp-remote', url, '--header', 'Authorization: Bearer ${ODOO_API_KEY}'],
                    'env': {'ODOO_API_KEY': '<your Odoo API key>'},
                },
            },
        }, indent=2)
        snippet = (
            '// Claude Desktop (claude_desktop_config.json) and Cursor (.cursor/mcp.json)\n'
            f'{desktop}\n\n'
            '# Claude Code (Streamable HTTP transport)\n'
            f'claude mcp add --transport http odoo {url} --header "Authorization: Bearer <your Odoo API key>"\n'
        )
        for record in self:
            record.ydod_mcp_endpoint_url = url
            record.ydod_mcp_client_snippet = snippet

    def set_values(self):
        for record in self:
            if min(record.ydod_mcp_default_limit, record.ydod_mcp_rate_limit,
                   record.ydod_mcp_log_retention_days) < 0:
                raise ValidationError(self.env._(
                    'The MCP default row limit, rate limit and log retention must be zero or positive.'))
        return super().set_values()
