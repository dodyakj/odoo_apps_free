/** @odoo-module **/

import { Component, proxy, useListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadGlobalSearchConfig, matchShortcut } from "./global_search_config";
import { openGlobalSearch } from "./global_search_dialog";

const FLOAT_POSITIONS = {
    bottom_right: "bottom: 24px; right: 24px;",
    bottom_left: "bottom: 24px; left: 24px;",
    top_right: "top: 64px; right: 24px;",
    top_left: "top: 64px; left: 24px;",
};

class GlobalSearchBase extends Component {
    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = proxy({ config: null });
        loadGlobalSearchConfig(this.orm).then((config) => {
            this.state.config = config;
        });
    }

    get enabled() {
        return Boolean(this.state.config?.enabled);
    }

    open() {
        openGlobalSearch(this.dialog, this.state.config);
    }
}

export class GlobalSearchSystray extends GlobalSearchBase {
    static template = "ydod_global_search.GlobalSearchSystray";
}

export class GlobalSearchLauncher extends GlobalSearchBase {
    static template = "ydod_global_search.GlobalSearchLauncher";

    setup() {
        super.setup();
        useListener(window, "keydown", (ev) => {
            if (this.enabled && matchShortcut(ev, this.state.config.shortcut)) {
                ev.preventDefault();
                this.open();
            }
        });
    }

    get showFloat() {
        return this.enabled && this.state.config.float_button;
    }

    get floatStyle() {
        const size = this.state.config.float_size || 48;
        const position = FLOAT_POSITIONS[this.state.config.float_position] || FLOAT_POSITIONS.bottom_right;
        return `width: ${size}px; height: ${size}px; font-size: ${Math.round(size * 0.4)}px; ${position}`;
    }
}

registry.category("systray").add("ydod_global_search.systray", { Component: GlobalSearchSystray }, { sequence: 5 });
registry.category("main_components").add("ydod_global_search.launcher", { Component: GlobalSearchLauncher });
