from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestYdodSqlQuery(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Query = cls.env['ydod.sql.query']
        cls.History = cls.env['ydod.sql.query.history']
        cls.user_internal = cls.env['res.users'].create({
            'name': 'SQL Internal User',
            'login': 'ydod_sql_internal',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })
        cls.user_system = cls.env['res.users'].create({
            'name': 'SQL System User',
            'login': 'ydod_sql_system',
            'group_ids': [Command.set([cls.env.ref('base.group_system').id])],
        })

    def _create_query(self, sql_text, **vals):
        values = {'name': 'Test query', 'sql_text': sql_text}
        values.update(vals)
        return self.Query.create(values)

    def _table_exists(self, table_name):
        self.env.cr.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table_name,))
        return bool(self.env.cr.fetchall())

    def test_select_result(self):
        query = self._create_query("-- leading comment\nSELECT 1 AS one, 'a' AS txt")
        self.assertEqual(query.statement_type, 'read')
        self.assertEqual(query.state, 'draft')
        self.assertIn('Execute the query', query.result_html)
        query.action_execute()
        self.assertEqual(query.state, 'done')
        self.assertFalse(query.error_message)
        self.assertEqual(query.result_json['columns'], ['one', 'txt'])
        self.assertEqual(query.result_json['rows'], [[1, 'a']])
        self.assertFalse(query.result_json['truncated'])
        self.assertEqual(query.row_count, 1)
        self.assertGreaterEqual(query.duration_ms, 0)
        self.assertEqual(query.last_run_user_id, self.env.user)
        self.assertTrue(query.last_run_date)
        self.assertIn('<table class="table table-sm table-striped">', query.result_html)
        self.assertIn('<th>txt</th>', query.result_html)
        self.assertEqual(len(query.history_ids), 1)
        history = query.history_ids
        self.assertEqual(history.state, 'done')
        self.assertFalse(history.is_write)
        self.assertEqual(history.row_count, 1)
        self.assertEqual(history.user_id, self.env.user)
        self.assertEqual(history.sql_text, query.sql_text)

    def test_write_requires_allow(self):
        query = self._create_query("CREATE TABLE ydod_t_guard (id int)")
        self.assertEqual(query.statement_type, 'write')
        with self.assertRaises(UserError):
            query.action_execute()
        self.assertEqual(query.state, 'draft')
        self.assertFalse(query.history_ids)
        self.assertFalse(self._table_exists('ydod_t_guard'))

        setup = self._create_query(
            "CREATE TABLE ydod_t_side (id int);\n"
            "CREATE FUNCTION ydod_t_side_insert() RETURNS int LANGUAGE sql AS $$\n"
            "    INSERT INTO ydod_t_side (id) VALUES (1) RETURNING id\n"
            "$$", allow_write=True)
        self.assertEqual(setup.statement_type, 'write')
        setup.action_execute()
        self.assertEqual(setup.state, 'done', setup.error_message)
        self.assertTrue(self._table_exists('ydod_t_side'))

        probe = self._create_query("SELECT ydod_t_side_insert() AS inserted_id")
        self.assertEqual(probe.statement_type, 'read')
        probe.action_execute()
        self.assertEqual(probe.state, 'done', probe.error_message)
        self.assertEqual(probe.result_json['rows'], [[1]])
        self.env.cr.execute("SELECT count(*) FROM ydod_t_side")
        self.assertEqual(self.env.cr.fetchone()[0], 0, "read statements must be rolled back")

    def test_write_executed(self):
        create = self._create_query("CREATE TABLE ydod_t_exec (id int, label varchar)", allow_write=True)
        create.action_execute()
        self.assertEqual(create.state, 'done', create.error_message)
        self.assertEqual(create.row_count, 0)
        self.assertTrue(self._table_exists('ydod_t_exec'))

        insert = self._create_query(
            "INSERT INTO ydod_t_exec (id, label) VALUES (1, 'a'), (2, 'b')", allow_write=True)
        insert.action_execute()
        self.assertEqual(insert.state, 'done', insert.error_message)
        self.assertEqual(insert.row_count, 2)
        self.assertTrue(insert.history_ids.is_write)
        self.assertEqual(insert.history_ids.row_count, 2)
        self.assertIn('2 row(s) affected', insert.result_html)

        update = self._create_query("UPDATE ydod_t_exec SET label = upper(label)", allow_write=True)
        update.action_execute()
        self.assertEqual(update.row_count, 2)
        self.env.cr.execute("SELECT label FROM ydod_t_exec ORDER BY id")
        self.assertEqual([row[0] for row in self.env.cr.fetchall()], ['A', 'B'])

        drop = self._create_query("DROP TABLE ydod_t_exec", allow_write=True)
        drop.action_execute()
        self.assertEqual(drop.state, 'done', drop.error_message)
        self.assertFalse(self._table_exists('ydod_t_exec'))
        self.assertEqual((create + insert + update + drop).mapped('statement_type'), ['write'] * 4)

    def test_error_isolated(self):
        query = self._create_query("SELECT * FROM ydod_missing_table")
        query.action_execute()
        self.assertEqual(query.state, 'error')
        self.assertIn('does not exist', query.error_message)
        self.assertFalse(query.result_json)
        self.assertEqual(query.row_count, 0)
        self.assertIn('last run failed', query.result_html)
        self.assertEqual(query.history_ids.state, 'error')
        self.assertIn('does not exist', query.history_ids.error_message)
        partner = self.env['res.partner'].create({'name': 'After error'})
        self.assertTrue(partner.id, "the transaction must stay usable after a failed statement")
        query.write({'sql_text': 'SELECT 1 AS fixed'})
        query.action_execute()
        self.assertEqual(query.state, 'done')
        self.assertFalse(query.error_message)

    def test_truncation_and_constraints(self):
        query = self._create_query("SELECT generate_series(1, 50) AS n", max_rows=10)
        query.action_execute()
        self.assertEqual(query.state, 'done', query.error_message)
        self.assertEqual(len(query.result_json['rows']), 10)
        self.assertTrue(query.result_json['truncated'])
        self.assertEqual(query.row_count, 50)
        self.assertIn('Showing 10 of 50 rows', query.result_html)

        with self.assertRaises(ValidationError):
            query.write({'max_rows': 0})
        with self.assertRaises(ValidationError):
            query.write({'max_rows': 6000})
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self._create_query("SELECT 1", max_rows=0)
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self._create_query("SELECT 1", max_rows=6000)
        self.assertEqual(query.max_rows, 10)

        for forbidden in ('COMMIT', 'rollback', '-- only a comment', 'SELECT 1; COMMIT'):
            with self.assertRaises(ValidationError, msg=forbidden):
                self._create_query(forbidden)

    def test_access_rights(self):
        internal_query = self.Query.with_user(self.user_internal)
        internal_history = self.History.with_user(self.user_internal)
        with self.assertRaises(AccessError):
            internal_query.search([])
        with self.assertRaises(AccessError):
            internal_query.create({'name': 'Forbidden', 'sql_text': 'SELECT 1'})
        with self.assertRaises(AccessError):
            internal_history.search([])
        with self.assertRaises(AccessError):
            internal_history.create({'name': 'Forbidden', 'sql_text': 'SELECT 1', 'state': 'done'})

        query = self.Query.with_user(self.user_system).create({
            'name': 'Admin query', 'sql_text': 'SELECT 1 AS one'})
        query.action_execute()
        self.assertEqual(query.state, 'done')
        self.assertEqual(query.last_run_user_id, self.user_system)
        history = self.History.with_user(self.user_system).search([('query_id', '=', query.id)])
        self.assertEqual(len(history), 1)
        self.assertEqual(history.user_id, self.user_system)
        with self.assertRaises(AccessError):
            history.write({'name': 'Tampered'})
        query.unlink()
        self.assertFalse(query.exists())
        self.assertTrue(history.exists())
        self.assertFalse(history.query_id)

    def test_history_count_and_load(self):
        query = self._create_query("SELECT 1 AS one", note='<p>Documented query</p>', orientation='landscape')
        for _ in range(3):
            query.action_execute()
        self.assertEqual(query.history_count, 3)
        self.assertEqual(len(query.history_ids), 3)
        other = self._create_query("SELECT 2 AS two")
        self.assertEqual(other.history_count, 0)

        last_run = query.history_ids[0]
        action = last_run.action_load_into_editor()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'ydod.sql.query')
        new_query = self.Query.browse(action['res_id'])
        self.assertEqual(new_query.name, 'Test query (copy)')
        self.assertEqual(new_query.sql_text, query.sql_text)
        self.assertIn('Documented query', new_query.note)
        self.assertEqual(new_query.orientation, 'landscape')
        self.assertFalse(new_query.allow_write)
        self.assertEqual(new_query.state, 'draft')
        self.assertFalse(new_query.history_ids)

        view_action = query.action_view_history()
        self.assertEqual(view_action['res_model'], 'ydod.sql.query.history')
        self.assertEqual(view_action['domain'], [('query_id', '=', query.id)])

    def test_print_pdf(self):
        query = self._create_query("SELECT 1 AS one, 'x' AS label", name='PDF query')
        with self.assertRaises(UserError):
            query.action_print_pdf()
        query.action_execute()
        portrait = self.env.ref('ydod_postgresql_query_execute.action_report_sql_query_portrait')
        landscape = self.env.ref('ydod_postgresql_query_execute.action_report_sql_query_landscape')
        action = query.action_print_pdf()
        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(action['report_name'], portrait.report_name)
        self.assertEqual(action['name'], portrait.name)
        self.assertEqual(portrait.paperformat_id.orientation, 'Portrait')

        query.write({'orientation': 'landscape'})
        action = query.action_print_pdf()
        self.assertEqual(action['name'], landscape.name)
        self.assertEqual(landscape.paperformat_id.orientation, 'Landscape')

        html = self.env['ir.actions.report']._render_qweb_html(
            'ydod_postgresql_query_execute.action_report_sql_query_landscape', query.ids)[0]
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn('PDF query', html)
        self.assertIn('<th>one</th>', html)
        self.assertIn('<th>label</th>', html)
