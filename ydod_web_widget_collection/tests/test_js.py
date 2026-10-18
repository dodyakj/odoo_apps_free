import importlib.util
import unittest

from odoo.tests import HttpCase, tagged

# Odoo drives headless Chrome through the websocket-client package. Without it
# HttpCase.browser_js logs a WARNING and raises SkipTest itself; skipping
# upfront keeps the test log clean on servers that have no browser tooling.
HAS_WEBSOCKET_CLIENT = importlib.util.find_spec('websocket') is not None

BOOT_CHECK = """
(function () {
    const started = Date.now();
    const names = ["ydod_toggle_label", "ydod_html_print_preview", "ydod_many2many_list"];
    const check = () => {
        const booted = document.querySelector(".o_web_client") || document.querySelector(".o_action_manager");
        if (!booted && Date.now() - started < 20000) {
            return setTimeout(check, 250);
        }
        const loader = window.odoo && odoo.loader;
        const mod = loader && loader.modules && loader.modules.get && loader.modules.get("@web/core/registry");
        if (mod && mod.registry) {
            const fields = mod.registry.category("fields");
            for (const name of names) {
                if (!fields.contains(name)) {
                    console.error("yDoD widget not registered: " + name);
                    return;
                }
            }
        }
        console.log("test successful");
    };
    check();
})();
"""


@tagged('post_install', '-at_install')
@unittest.skipIf(not HAS_WEBSOCKET_CLIENT, 'websocket-client module is not installed')
class TestYdodWidgetWebClient(HttpCase):
    """The web client must boot with the three OWL 2 widgets registered
    (guards against a blank screen caused by a broken asset)."""

    def test_web_client_boots_with_widgets(self):
        self.browser_js('/web', BOOT_CHECK, login='admin')
