from lxml import etree

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestYdodWidgetViews(TransactionCase):
    """The widgets are declared by a single attribute: inherited views using
    them must validate server-side and keep widget/options in get_views."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.form_view = cls.env.ref('base.view_partner_form')
        cls.plain_user = cls.env['res.users'].create({
            'name': 'yDoD Plain User',
            'login': 'ydod_widget_plain_user',
            'email': 'ydod_widget_plain_user@example.com',
            'groups_id': [Command.set([cls.env.ref('base.group_user').id])],
        })
        cls.admin_user = cls.env.ref('base.user_admin')

    def _create_inherited_form(self, inner_arch, name='ydod widget test view'):
        return self.env['ir.ui.view'].create({
            'name': name,
            'model': 'res.partner',
            'inherit_id': self.form_view.id,
            'arch': (
                '<xpath expr="//notebook" position="inside">'
                '<page string="yDoD Test" name="ydod_test">%s</page></xpath>' % inner_arch
            ),
        })

    def _form_arch(self, user=None):
        model = self.env['res.partner']
        if user is not None:
            model = model.with_user(user)
        views = model.get_views([(self.form_view.id, 'form')])
        return views['views']['form']['arch']

    def _widget_nodes(self, arch, widget):
        """Widget nodes added by this test's own page only: the optional demo
        views also put yDoD widgets on the partner form, and tests must not
        depend on demo data being loaded or not."""
        tree = etree.fromstring(arch.encode('utf-8'))
        return tree.xpath("//page[@name='ydod_test']//field[@widget='%s']" % widget)

    def test_toggle_label_view(self):
        self._create_inherited_form(
            '<field name="active" widget="ydod_toggle_label" '
            'options="{\'on_label\': \'Active\', \'off_label\': \'Archived\', '
            '\'on_color\': \'#198754\', \'off_color\': \'#6c757d\'}"/>'
        )
        arch = self._form_arch()
        nodes = self._widget_nodes(arch, 'ydod_toggle_label')
        self.assertTrue(nodes, 'toggle widget must survive get_views')
        self.assertIn("'on_label': 'Active'", nodes[0].get('options'))
        self.assertIn("'off_label': 'Archived'", nodes[0].get('options'))

    def test_print_preview_and_many2many_list_views(self):
        self._create_inherited_form(
            '<field name="comment" widget="ydod_html_print_preview" '
            'options="{\'page_size\': \'A4\', \'orientation\': \'landscape\', \'title\': \'Notes\'}"/>'
            '<field name="category_id" widget="ydod_many2many_list" '
            'options="{\'style\': \'number\', \'limit\': 2}"/>'
        )
        arch = self._form_arch()
        preview = self._widget_nodes(arch, 'ydod_html_print_preview')
        m2m = self._widget_nodes(arch, 'ydod_many2many_list')
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0].get('name'), 'comment')
        self.assertIn("'orientation': 'landscape'", preview[0].get('options'))
        self.assertEqual(len(m2m), 1)
        self.assertEqual(m2m[0].get('name'), 'category_id')
        self.assertIn("'limit': 2", m2m[0].get('options'))

    def test_wrong_field_type_validates_server_side(self):
        # The widget type check is a client-side concern: the server accepts the arch.
        view = self._create_inherited_form('<field name="name" widget="ydod_toggle_label"/>')
        self.assertTrue(view.exists())
        self.assertTrue(self._widget_nodes(self._form_arch(), 'ydod_toggle_label'))

    def test_field_groups_still_apply(self):
        self._create_inherited_form(
            '<field name="active" widget="ydod_toggle_label" groups="base.group_system" '
            'options="{\'on_label\': \'Yes\', \'off_label\': \'No\'}"/>'
        )
        # Administrator (base.group_system) sees the widget.
        admin_nodes = self._widget_nodes(self._form_arch(self.admin_user), 'ydod_toggle_label')
        self.assertEqual(len(admin_nodes), 1)
        self.assertNotIn(admin_nodes[0].get('invisible'), ('1', 'True', 'true'))
        # A plain internal user does not: the node is stripped (or forced invisible).
        plain_nodes = self._widget_nodes(self._form_arch(self.plain_user), 'ydod_toggle_label')
        for node in plain_nodes:
            self.assertIn(node.get('invisible'), ('1', 'True', 'true'))
        self.assertFalse(
            [n for n in plain_nodes if n.get('invisible') not in ('1', 'True', 'true')],
            'plain users must not get a field restricted to base.group_system',
        )
