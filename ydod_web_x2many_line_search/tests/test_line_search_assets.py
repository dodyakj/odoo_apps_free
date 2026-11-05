from xml.etree import ElementTree

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open

TEMPLATE_PATH = "ydod_web_x2many_line_search/static/src/line_search/x2many_field_patch.xml"
SCSS_PATH = "ydod_web_x2many_line_search/static/src/line_search/line_search.scss"
HIGHLIGHT_PATH = "ydod_web_x2many_line_search/static/src/line_search/line_search_highlight.js"
BOX_PATH = "ydod_web_x2many_line_search/static/src/line_search/line_search_box.js"
MATCHER_PATH = "ydod_web_x2many_line_search/static/src/line_search/line_search_matcher.js"
FIELD_PATH = "ydod_web_x2many_line_search/static/src/line_search/x2many_field_patch.js"
BOX_TEMPLATE_PATH = "ydod_web_x2many_line_search/static/src/line_search/line_search_box.xml"
SERVICE_PATH = "ydod_web_x2many_line_search/static/src/line_search/line_search_service.js"
RENDERER_PATH = "ydod_web_x2many_line_search/static/src/line_search/list_renderer_patch.js"


def _read(path):
    with file_open(path, "r") as asset_file:
        return asset_file.read()


@tagged("post_install", "-at_install")
class TestLineSearchAssets(TransactionCase):
    """The search box must not depend on the inner structure of web.X2ManyField."""

    def _template_nodes(self):
        with file_open(TEMPLATE_PATH, "rb") as template_file:
            return list(ElementTree.fromstring(template_file.read()).iter())

    def test_no_xpath_into_standard_template(self):
        nodes = self._template_nodes()
        self.assertFalse([node for node in nodes if node.tag == "xpath"])
        self.assertFalse([node for node in nodes if node.get("t-inherit") == "web.X2ManyField"])

    def test_wrapper_calls_standard_template(self):
        wrappers = [
            node for node in self._template_nodes()
            if node.get("t-name") == "ydod_web_x2many_line_search.X2ManyField"
        ]
        self.assertEqual(len(wrappers), 1)
        inner = list(wrappers[0].iter())
        self.assertTrue([node for node in inner if node.get("t-call") == "web.X2ManyField"])
        self.assertTrue([
            node for node in inner if node.get("t-component") == "this.lineSearchBoxComponent"
        ])

    def test_non_matching_rows_are_hidden_on_the_dom(self):
        """Rows are hidden even when the list renderer does not re-render."""
        scss = _read(SCSS_PATH)
        self.assertIn("tr.o_data_row.o_x2m_line_search_hidden", scss)
        self.assertIn("display: none !important", scss)
        highlight = _read(HIGHLIGHT_PATH)
        self.assertIn("export function applyRowVisibility", highlight)
        self.assertIn("o_selected_row", highlight)
        box = _read(BOX_PATH)
        self.assertIn("applyRowVisibility(", box)
        self.assertIn("MutationObserver", box)

    def test_typed_text_stays_readable(self):
        """Form view input styles must not hide the characters typed in the box."""
        scss = _read(SCSS_PATH)
        for rule in ("-webkit-text-fill-color", "caret-color", "min-width: 120px", "opacity: 1"):
            self.assertIn(rule, scss)
        self.assertNotIn("@import", scss)

    def test_box_uses_font_awesome_icons(self):
        """Odoo 17 ships Font Awesome: the box shows a magnifier and a clear icon."""
        with file_open(BOX_TEMPLATE_PATH, "rb") as template_file:
            nodes = list(ElementTree.fromstring(template_file.read()).iter())
        icons = [node for node in nodes if node.tag == "i"]
        self.assertTrue(icons)
        for icon in icons:
            classes = (icon.get("class") or "") + " " + (icon.get("t-attf-class") or "")
            self.assertIn("fa", classes.split())
            self.assertFalse(icon.get("data-icon"))
        search_icon = [node for node in icons if "o_x2m_line_search_icon" in (
            node.get("t-attf-class") or "")][0]
        self.assertIn("fa-search", search_icon.get("t-attf-class"))
        self.assertTrue([node for node in icons if "fa-times" in (node.get("class") or "")])

    def test_owl2_api_only(self):
        """Odoo 17 runs Owl 2: no Owl 3 / Odoo 20 helpers may be imported."""
        for path in (BOX_PATH, FIELD_PATH, MATCHER_PATH, HIGHLIGHT_PATH):
            source = _read(path)
            for token in ("@web/owl2/utils", "useProps", "signal(", "proxy("):
                self.assertNotIn(token, source, f"{token} found in {path}")

    def test_odoo_module_headers(self):
        """Odoo 17 only transpiles JS files flagged as Odoo modules."""
        for path in (BOX_PATH, FIELD_PATH, MATCHER_PATH, HIGHLIGHT_PATH, SERVICE_PATH, RENDERER_PATH):
            self.assertTrue(_read(path).startswith("/** @odoo-module **/"), path)

    def test_bootstrap_51_classes(self):
        """Odoo 17 ships Bootstrap 5.1: text-bg-* helpers do not exist yet."""
        self.assertNotIn("text-bg-", _read(BOX_TEMPLATE_PATH))

    def test_box_does_not_depend_on_input_group(self):
        """The input is styled by the module itself, not by form or input-group rules."""
        with file_open(BOX_TEMPLATE_PATH, "rb") as template_file:
            nodes = list(ElementTree.fromstring(template_file.read()).iter())
        inputs = [node for node in nodes if node.tag == "input"]
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0].get("placeholder"), "Search lines...")
        self.assertFalse([n for n in nodes if "input-group" in (n.get("class") or "")])
        scss = _read(SCSS_PATH)
        self.assertIn("input.o_x2m_line_search_input", scss)
        self.assertIn(".o_x2m_line_search_icon", scss)

    def test_box_is_compact(self):
        """The box stays small above the list: compact height and width."""
        scss = _read(SCSS_PATH)
        self.assertIn("height: 26px", scss)
        self.assertIn("width: 260px", scss)
        self.assertNotIn("max-width: 420px", scss)
        self.assertNotIn("font-size: 18px", scss)

    def test_box_is_above_and_not_covered_by_the_list(self):
        """The box sits on its own row above the list and stays on top of it."""
        scss = _read(SCSS_PATH)
        self.assertIn(".o_x2m_line_search_host", scss)
        self.assertIn("flex-direction: column", scss)
        self.assertIn("order: -1", scss)
        self.assertIn("position: sticky", scss)
        self.assertIn("z-index: 5", scss)
        self.assertNotIn("background:", scss)
        box = _read(BOX_PATH)
        self.assertIn('classList.add("o_x2m_line_search_host")', box)
        self.assertIn('classList.remove("o_x2m_line_search_host")', box)

    def test_matches_displayed_row_text(self):
        """Any part of the text shown in a row is found, also widget-rendered text."""
        matcher = _read(MATCHER_PATH)
        self.assertIn("export function renderedRowTexts", matcher)
        self.assertIn("textTypes.includes(", matcher)
        self.assertIn("/\\p{Mn}/gu", matcher)
        field = _read(FIELD_PATH)
        self.assertIn("renderedRowTexts(this.lineSearchGetContainer?.())", field)
        box = _read(BOX_PATH)
        self.assertIn("this.props.setContainer?.(", box)
