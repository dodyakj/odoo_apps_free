from odoo import fields, models


class YdodSqlQueryHistory(models.Model):
    _name = 'ydod.sql.query.history'
    _description = 'SQL Query Execution History'
    _order = 'run_date desc, id desc'

    query_id = fields.Many2one('ydod.sql.query', string='Query', ondelete='set null', index=True, readonly=True)
    name = fields.Char(string='Query Name', required=True, readonly=True)
    sql_text = fields.Text(string='SQL', required=True, readonly=True)
    user_id = fields.Many2one('res.users', string='Run By', required=True, readonly=True,
                              default=lambda self: self.env.user)
    run_date = fields.Datetime(string='Run Date', required=True, readonly=True, index=True,
                               default=fields.Datetime.now)
    duration_ms = fields.Float(string='Duration (ms)', digits=(16, 2), readonly=True)
    row_count = fields.Integer(string='Rows', readonly=True)
    is_write = fields.Boolean(string='Write Statement', readonly=True)
    state = fields.Selection([('done', 'Success'), ('error', 'Error')], string='Status', required=True,
                             readonly=True)
    error_message = fields.Text(readonly=True)

    def action_load_into_editor(self):
        self.ensure_one()
        query = self.query_id
        new_query = self.env['ydod.sql.query'].create({
            'name': self.env._("%s (copy)", self.name),
            'sql_text': self.sql_text,
            'note': query.note if query else False,
            'allow_write': False,
            'max_rows': query.max_rows if query else self.env['ydod.sql.query']._default_max_rows(),
            'orientation': query.orientation if query else 'portrait',
            'state': 'draft',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("SQL Query"),
            'res_model': 'ydod.sql.query',
            'res_id': new_query.id,
            'view_mode': 'form',
            'target': 'current',
        }
