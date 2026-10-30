/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { YdodLangSwitcherDialog } from "./lang_switcher_dialog";

const userMenuRegistry = registry.category("user_menuitems");

function openUrl(url) {
    browser.open(url, "_blank");
}

/**
 * Hide, rename or re-point a standard user-menu entry.
 */
function overrideItem(key, { hide = false, label = "", url = "" }) {
    if (!userMenuRegistry.contains(key)) {
        return;
    }
    if (hide) {
        userMenuRegistry.remove(key);
        return;
    }
    if (!label && !url) {
        return;
    }
    const original = userMenuRegistry.get(key);
    userMenuRegistry.add(
        key,
        (env) => {
            const item = original(env);
            if (!item) {
                return item;
            }
            const result = { ...item };
            if (label) {
                result.description = label;
            }
            if (url) {
                result.href = url;
                result.callback = () => openUrl(url);
            }
            return result;
        },
        { force: true }
    );
}

function toggleDebug(env) {
    const url = new URL(browser.location.href);
    url.searchParams.set("debug", env.debug ? "" : "1");
    browser.location.href = url.href;
}

export const ydodUserMenuService = {
    dependencies: [],
    start() {
        const tweaks = session.ydod_tweaks || {};
        overrideItem("documentation", {
            hide: tweaks.ydod_menu_documentation_hide,
            label: tweaks.ydod_menu_documentation_label,
            url: tweaks.ydod_menu_documentation_url,
        });
        overrideItem("support", {
            hide: tweaks.ydod_menu_support_hide,
            label: tweaks.ydod_menu_support_label,
            url: tweaks.ydod_menu_support_url,
        });
        overrideItem("shortcuts", {
            hide: tweaks.ydod_menu_shortcuts_hide,
            label: tweaks.ydod_menu_shortcuts_label,
        });
        overrideItem("odoo_account", {
            hide: tweaks.ydod_menu_account_hide,
            label: tweaks.ydod_menu_account_label,
            url: tweaks.ydod_menu_account_url,
        });

        const aboutUrl = tweaks.ydod_menu_about_url;
        if (aboutUrl) {
            userMenuRegistry.add(
                "ydod_about",
                () => ({
                    type: "item",
                    id: "ydod_about",
                    description: tweaks.ydod_menu_about_label || _t("About"),
                    href: aboutUrl,
                    callback: () => openUrl(aboutUrl),
                    sequence: 35,
                }),
                { force: true }
            );
        }

        const debugAllowed = !tweaks.ydod_debug_guard || session.ydod_is_system;
        if (tweaks.ydod_menu_debug_toggle && debugAllowed) {
            userMenuRegistry.add(
                "ydod_debug",
                (env) => ({
                    type: "item",
                    id: "ydod_debug",
                    description: env.debug
                        ? _t("Deactivate Developer Mode")
                        : _t("Activate Developer Mode"),
                    callback: () => toggleDebug(env),
                    sequence: 38,
                }),
                { force: true }
            );
        }

        if (tweaks.ydod_menu_lang_switch) {
            userMenuRegistry.add(
                "ydod_lang",
                (env) => ({
                    type: "item",
                    id: "ydod_lang",
                    description: _t("Language"),
                    callback: () => env.services.dialog.add(YdodLangSwitcherDialog, {}),
                    sequence: 39,
                }),
                { force: true }
            );
        }
    },
};

registry.category("services").add("ydod_user_menu", ydodUserMenuService);
