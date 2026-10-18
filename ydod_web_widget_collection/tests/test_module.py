from odoo.tests import TransactionCase, tagged

MODULE = 'ydod_web_widget_collection'
WIDGET_FILES = [
    'static/src/fields/toggle_label/toggle_label.js',
    'static/src/fields/toggle_label/toggle_label.xml',
    'static/src/fields/toggle_label/toggle_label.scss',
    'static/src/fields/html_print_preview/html_print_preview.js',
    'static/src/fields/html_print_preview/html_print_preview.xml',
    'static/src/fields/html_print_preview/html_print_preview.scss',
    'static/src/fields/many2many_list/many2many_list.js',
    'static/src/fields/many2many_list/many2many_list.xml',
    'static/src/fields/many2many_list/many2many_list.scss',
]


@tagged('post_install', '-at_install')
class TestYdodWidgetModule(TransactionCase):

    def _bundle_paths(self, bundle):
        """All file paths (js, xml, scss) declared for an asset bundle.

        ``ir.asset._get_asset_paths(bundle, assets_params)`` returns every
        file of the bundle whatever its extension; the js/css split happens
        later in the AssetsBundle. Entries are tuples whose first element is
        the addon-relative path.
        """
        entries = self.env['ir.asset']._get_asset_paths(bundle, {})
        paths = set()
        for entry in entries:
            path = entry[0] if isinstance(entry, (tuple, list)) else entry
            paths.add(str(path).replace('\\', '/'))
        return paths

    def test_backend_bundle_contains_widgets(self):
        paths = self._bundle_paths('web.assets_backend')
        for widget_file in WIDGET_FILES:
            expected = '%s/%s' % (MODULE, widget_file)
            self.assertTrue(
                any(path.endswith(expected) for path in paths),
                '%s must be part of web.assets_backend' % expected,
            )

    def test_frontend_bundle_excludes_widgets(self):
        paths = self._bundle_paths('web.assets_frontend')
        for widget_file in WIDGET_FILES:
            expected = '%s/%s' % (MODULE, widget_file)
            self.assertFalse(
                any(path.endswith(expected) for path in paths),
                '%s must not be part of web.assets_frontend' % expected,
            )

    def test_module_record(self):
        module = self.env['ir.module.module'].search([('name', '=', MODULE)], limit=1)
        self.assertTrue(module, 'module record must exist')
        self.assertEqual(module.state, 'installed')
        # The manifest category 'Hidden' maps to base.module_category_hidden,
        # whose display name is 'Technical' since Odoo 17.
        self.assertEqual(module.category_id, self.env.ref('base.module_category_hidden'))
        self.assertFalse(module.application)
        self.assertEqual(module.dependencies_id.mapped('name'), ['web'])
        self.assertTrue(module.license, 'a license must be declared')
        self.assertTrue(module.author, 'an author must be declared')

    def test_no_models_no_menus(self):
        # ir.model.modules is a non-stored computed field: check the xml ids instead.
        ModelData = self.env['ir.model.data']
        model_data = ModelData.search([('module', '=', MODULE), ('model', '=', 'ir.model')])
        self.assertFalse(model_data, 'the module must not define models')
        menu_data = ModelData.search([('module', '=', MODULE), ('model', '=', 'ir.ui.menu')])
        self.assertFalse(menu_data, 'the module must not add menus')
        action_data = ModelData.search([
            ('module', '=', MODULE),
            ('model', 'in', ['ir.actions.act_window', 'ir.actions.client', 'ir.actions.server']),
        ])
        self.assertFalse(action_data, 'the module must not add actions')
