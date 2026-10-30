import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

const DEFAULT_COLOR = "#D9534F";
const COLOR_RE = /^#[0-9A-Fa-f]{6}$/;

/**
 * Fixed corner ribbon marking non-production environments (TEST, STAGING...).
 * Renders nothing when no ribbon text is configured.
 */
export class YdodEnvRibbon extends Component {
    static template = "ydod_web_debrand_oem_tweaks.EnvRibbon";
    static props = {};

    setup() {
        const tweaks = session.ydod_tweaks || {};
        this.text = (tweaks.ydod_ribbon_text || "").trim();
        const color = (tweaks.ydod_ribbon_color || "").trim();
        this.color = COLOR_RE.test(color) ? color : DEFAULT_COLOR;
    }

    get style() {
        return `background-color: ${this.color};`;
    }
}

registry.category("main_components").add("ydod_env_ribbon", { Component: YdodEnvRibbon });
