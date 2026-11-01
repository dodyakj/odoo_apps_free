/** @odoo-module **/

export const GLOBAL_SEARCH_MODEL = "ydod.global.search.model";

let configPromise = null;

/**
 * Read the Global Search UI options once per page load (shared by the
 * systray item and the launcher).
 */
export function loadGlobalSearchConfig(orm) {
    if (!configPromise) {
        configPromise = orm
            .call(GLOBAL_SEARCH_MODEL, "ydod_get_ui_config", [])
            .catch(() => ({ enabled: false }));
    }
    return configPromise;
}

/**
 * Return true when the keyboard event matches a shortcut such as "ctrl+shift+k".
 */
export function matchShortcut(ev, shortcut) {
    const parts = (shortcut || "").toLowerCase().split("+").filter(Boolean);
    const key = parts.pop();
    if (!key) {
        return false;
    }
    const mods = new Set(parts);
    if (
        ev.ctrlKey !== mods.has("ctrl") ||
        ev.altKey !== mods.has("alt") ||
        ev.shiftKey !== mods.has("shift") ||
        ev.metaKey !== mods.has("meta")
    ) {
        return false;
    }
    const code = /[0-9]/.test(key) ? `Digit${key}` : `Key${key.toUpperCase()}`;
    return ev.code === code || (ev.key || "").toLowerCase() === key;
}
