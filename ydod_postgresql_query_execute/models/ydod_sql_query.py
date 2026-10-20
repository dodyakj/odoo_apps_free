import math
import re
import time

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape

READ_KEYWORDS = {'SELECT', 'EXPLAIN', 'SHOW', 'TABLE', 'VALUES', 'WITH'}
WRITE_IN_CTE = re.compile(r'\b(INSERT|UPDATE|DELETE|MERGE)\b', re.IGNORECASE)
TRANSACTION_KEYWORDS = {'BEGIN', 'START', 'COMMIT', 'END', 'ABORT', 'ROLLBACK', 'SAVEPOINT', 'RELEASE'}
COMMENT_RE = re.compile(r'/\*.*?\*/|--[^\n]*', re.DOTALL)
FIRST_WORD_RE = re.compile(r'[A-Za-z]+')


class YdodSqlQuery(models.Model):
    _name = 'ydod.sql.query'
    _description = 'SQL Query'
    _order = 'is_example, name, id'

    name = fields.Char(required=True)
    sql_text = fields.Text(string='SQL', required=True)
    note = fields.Html(string='Note', help='What the query does, why it exists and what it could break.')
    allow_write = fields.Boolean(
        string='Allow data modification',
        help='Write statements (INSERT, UPDATE, DELETE, CREATE, ALTER, DROP...) are refused while unticked.')
    max_rows = fields.Integer(string='Max rows', required=True, default=lambda self: self._default_max_rows(),
                              help='Maximum number of rows displayed and stored for the result.')
    orientation = fields.Selection([('portrait', 'Portrait'), ('landscape', 'Landscape')],
                                   string='PDF Orientation', required=True, default='portrait')
    is_example = fields.Boolean(string='Example', copy=False)
    statement_type = fields.Selection([('read', 'Read'), ('write', 'Write')], compute='_compute_statement_type',
                                      store=True, string='Statement Type')
    state = fields.Selection([('draft', 'Not run'), ('done', 'Success'), ('error', 'Error')],
                             string='Status', readonly=True, default='draft', copy=False)
    error_message = fields.Text(readonly=True, copy=False)
    result_json = fields.Json(string='Result Data', readonly=True, copy=False)
    result_html = fields.Html(string='Result', compute='_compute_result_html', sanitize=False)
    row_count = fields.Integer(string='Rows', readonly=True, copy=False)
    duration_ms = fields.Float(string='Duration (ms)', digits=(16, 2), readonly=True, copy=False)
    last_run_date = fields.Datetime(string='Last Run', readonly=True, copy=False)
    last_run_user_id = fields.Many2one('res.users', string='Last Run By', readonly=True, copy=False)
    history_ids = fields.One2many('ydod.sql.query.history', 'query_id', string='History')
    history_count = fields.Integer(compute='_compute_history_count')

    _check_max_rows_range = models.Constraint(
        'CHECK(max_rows BETWEEN 1 AND 5000)',
        'Max rows must be between 1 and 5000.')

    @api.model
    def _default_max_rows(self):
        """Default row cap: system parameter ydod_postgresql_query_execute.default_max_rows, else 200."""
        key = 'ydod_postgresql_query_execute.default_max_rows'
        try:
            value = int(self.env['ir.config_parameter'].sudo().get_param(key, '200'))
        except (TypeError, ValueError):
            value = 200
        return min(max(value, 1), 5000)

    @api.model
    def _split_statements(self, sql_text):
        """Return the comment-free, non-empty statements of a SQL text."""
        clean = COMMENT_RE.sub(' ', sql_text or '')
        return [part.strip() for part in clean.split(';') if part.strip()]

    @api.model
    def _first_keyword(self, statement):
        match = FIRST_WORD_RE.search(statement)
        return match.group(0).upper() if match else ''

    @api.depends('sql_text')
    def _compute_statement_type(self):
        for query in self:
            statement_type = 'read'
            for statement in self._split_statements(query.sql_text):
                keyword = self._first_keyword(statement)
                if keyword not in READ_KEYWORDS or (keyword == 'WITH' and WRITE_IN_CTE.search(statement)):
                    statement_type = 'write'
                    break
            query.statement_type = statement_type

    @api.depends('result_json', 'state', 'row_count')
    def _compute_result_html(self):
        for query in self:
            result = query.result_json or {}
            columns = result.get('columns') or []
            rows = result.get('rows') or []
            if query.state == 'draft':
                html = '<p class="text-muted">Execute the query to see its result here.</p>'
            elif query.state == 'error':
                html = '<p class="text-muted">The last run failed: see the error message above.</p>'
            elif not columns:
                html = '<p class="text-muted">Statement executed: %s row(s) affected.</p>' % query.row_count
            else:
                parts = ['<table class="table table-sm table-striped"><thead><tr>']
                parts.extend('<th>%s</th>' % html_escape(str(col)) for col in columns)
                parts.append('</tr></thead><tbody>')
                for row in rows:
                    parts.append('<tr>')
                    parts.extend(
                        '<td>%s</td>' % ('' if cell is None else html_escape(str(cell))) for cell in row)
                    parts.append('</tr>')
                parts.append('</tbody></table>')
                if not rows:
                    parts.append('<p class="text-muted">No rows returned.</p>')
                elif result.get('truncated'):
                    parts.append('<p class="text-muted">Showing %s of %s rows.</p>' % (len(rows), query.row_count))
                html = ''.join(parts)
            query.result_html = html

    @api.depends('history_ids')
    def _compute_history_count(self):
        groups = self.env['ydod.sql.query.history']._read_group(
            [('query_id', 'in', self.ids)], ['query_id'], ['__count'])
        counts = {query.id: count for query, count in groups}
        for query in self:
            query.history_count = counts.get(query.id, 0)

    @api.constrains('sql_text')
    def _check_sql_text(self):
        for query in self:
            statements = self._split_statements(query.sql_text)
            if not statements:
                raise ValidationError(self.env._("The SQL text contains no statement."))
            for statement in statements:
                if self._first_keyword(statement) in TRANSACTION_KEYWORDS:
                    raise ValidationError(self.env._(
                        "Transaction control statements (BEGIN, COMMIT, ROLLBACK, SAVEPOINT...) are not allowed."))

    @api.constrains('max_rows')
    def _check_max_rows(self):
        for query in self:
            if not 1 <= query.max_rows <= 5000:
                raise ValidationError(self.env._("Max rows must be between 1 and 5000."))

    @api.model
    def _cell_to_json(self, value):
        if value is None or isinstance(value, (bool, int, str)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else str(value)
        if isinstance(value, (bytes, memoryview)):
            return '<binary %d bytes>' % len(value)
        return str(value)

    def action_execute(self):
        self.ensure_one()
        is_write = self.statement_type == 'write'
        if is_write and not self.allow_write:
            raise UserError(self.env._("This statement modifies data: tick Allow data modification first."))
        sql_text = self.sql_text
        max_rows = self.max_rows
        cr = self.env.cr
        self.env.flush_all()
        columns, rows, row_count, truncated, error_message = [], [], 0, False, False
        start = time.perf_counter()
        duration_ms = 0.0
        try:
            # The savepoint isolates the statement: a PostgreSQL error is rolled
            # back by the context manager and the request transaction stays valid.
            with cr.savepoint() as savepoint:
                cr.execute(sql_text, log_exceptions=False)  # pylint: disable=sql-injection
                if cr.description:
                    columns = [column.name for column in cr.description]
                    rows = [[self._cell_to_json(cell) for cell in row] for row in cr.fetchmany(max_rows)]
                    row_count = cr.rowcount if cr.rowcount >= 0 else len(rows)
                    truncated = row_count > len(rows)
                else:
                    row_count = max(cr.rowcount, 0)
                duration_ms = (time.perf_counter() - start) * 1000
                if not is_write:
                    # read statements never leave a trace, even through volatile functions
                    savepoint.rollback()
        except Exception as exc:  # noqa: BLE001 - any PostgreSQL error must be reported in the form
            duration_ms = (time.perf_counter() - start) * 1000
            error_message = str(exc).strip()
            columns, rows, row_count, truncated = [], [], 0, False
        else:
            if is_write:
                # the savepoint was released: drop ORM caches made stale by the write
                self.env.invalidate_all()
        now = fields.Datetime.now()
        state = 'error' if error_message else 'done'
        self.env['ydod.sql.query.history'].create({
            'query_id': self.id,
            'name': self.name,
            'sql_text': sql_text,
            'user_id': self.env.uid,
            'run_date': now,
            'duration_ms': duration_ms,
            'row_count': row_count,
            'is_write': is_write,
            'state': state,
            'error_message': error_message,
        })
        self.write({
            'state': state,
            'error_message': error_message,
            'result_json': {'columns': columns, 'rows': rows, 'truncated': truncated} if columns else False,
            'row_count': row_count,
            'duration_ms': duration_ms,
            'last_run_date': now,
            'last_run_user_id': self.env.uid,
        })
        return None

    def action_print_pdf(self):
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(self.env._("Execute the query first."))
        report = self.env.ref('ydod_postgresql_query_execute.action_report_sql_query_%s' % self.orientation)
        return report.report_action(self, config=False)

    def action_view_history(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'ydod_postgresql_query_execute.action_ydod_sql_query_history')
        action['domain'] = [('query_id', '=', self.id)]
        action['context'] = {'default_query_id': self.id}
        return action
