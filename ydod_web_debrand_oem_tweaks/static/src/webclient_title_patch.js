/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

/**
 * Replaces the "Odoo" part of the browser tab title with the configured
 * system name. The title service is wrapped at boot so that every later
 * call made by the web client (zopenerp part) keeps the custom name.
 */
export const ydodTitleService = {
    dependencies: ["title"],
    start(env, { title }) {
        const systemName = ((session.ydod_tweaks || {}).ydod_system_name || "").trim();
        if (!systemName || !title || typeof title.setParts !== "function") {
            return;
        }
        const originalSetParts = title.setParts.bind(title);
        const brand = (parts) =>
            parts && "zopenerp" in parts ? { ...parts, zopenerp: systemName } : parts;
        try {
            title.setParts = (parts) => originalSetParts(brand(parts));
        } catch {
            // Frozen service object: fall back to setting the part once.
        }
        originalSetParts({ zopenerp: systemName });
    },
};

registry.category("services").add("ydod_title", ydodTitleService);
