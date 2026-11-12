# -*- coding: utf-8 -*-
{
    'name': 'MCP Server Core - Claude Desktop, Claude Code & Cursor for Odoo',
    'version': '16.0.1.0.0',
    'summary': ('Native Model Context Protocol (MCP) server for Odoo: connect Claude Desktop, Claude '
     'Code, Cursor and any MCP client with per-user API keys, a model allowlist, rate limit '
     'and a full tool call audit log.'),
    'description': ('\n'
     'MCP Server Core turns Odoo Community into a native Model Context Protocol (MCP) server\n'
     'at /mcp (JSON-RPC 2.0 over Streamable HTTP), written as a plain Odoo controller with no\n'
     'external library and no LLM or AI provider key inside Odoo.\n'
     '\n'
     'Key features:\n'
     '- initialize, ping, tools/list, tools/call, resources/list, resources/templates/list,\n'
     '  resources/read, prompts/list and prompts/get\n'
     "- Authentication with the user's standard Odoo API key as a Bearer token; every call "
     'runs\n'
     '  as that user so access rights, record rules and multi-company apply\n'
     '- Model allowlist: read-only or read-write mode, allowed fields, allowed public '
     'methods,\n'
     '  row limit per call\n'
     '- Generic tools list_models, get_fields, search_read, read, create, write and '
     'call_method\n'
     '  with JSON input schemas generated from the Odoo field definitions\n'
     '- Record resources odoo://<model>/<id> and odoo://models\n'
     '- Per-API-key rate limit, global kill switch and tool call log with automatic purge\n'
     '- Ready-to-paste configuration for Claude Desktop, Claude Code and Cursor\n'),
    'category': 'Tools / AI Integration',
    'author': 'Dody Ahmad Kusuma Jaya',
    'maintainer': 'Dody Ahmad Kusuma Jaya',
    'website': 'https://profile.dodyakj.online',
    'support': 'dodyakj@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail'],
    'data': [   'security/ir.model.access.csv',
        'security/ydod_mcp_security.xml',
        'data/ir_config_parameter_data.xml',
        'data/ir_cron_data.xml',
        'views/ydod_mcp_model_views.xml',
        'views/ydod_mcp_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml'],
    'demo': ['demo/ydod_mcp_demo.xml'],
    'images': [   'static/description/demo.gif',
        'static/description/banner.png',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
        'static/description/screenshot_4.png',
        'static/description/screenshot_5.png'],
    'installable': True,
    'application': False,
}
