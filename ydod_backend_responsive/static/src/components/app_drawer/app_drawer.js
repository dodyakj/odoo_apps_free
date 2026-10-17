/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AppDrawer extends Component {
    static template = "ydod_backend_responsive.AppDrawer";

    setup() {
        this.menuService = useService("menu");
        this.state = useState({
            isOpen: false,
            query: "",
        });

        this.onToggleDrawer = () => {
            this.state.isOpen = !this.state.isOpen;
            if (this.state.isOpen) {
                this.state.query = "";
            }
        };

        this.onKeyDown = (ev) => {
            if (ev.key === "Escape" && this.state.isOpen) {
                this.close();
            }
        };

        this.env.bus.addEventListener("TOGGLE_APP_DRAWER", this.onToggleDrawer);
        onMounted(() => {
            window.addEventListener("keydown", this.onKeyDown);
        });
        onWillUnmount(() => {
            this.env.bus.removeEventListener("TOGGLE_APP_DRAWER", this.onToggleDrawer);
            window.removeEventListener("keydown", this.onKeyDown);
        });
    }

    get apps() {
        return this.menuService.getApps();
    }

    get filteredApps() {
        const query = this.state.query.trim().toLowerCase();
        const apps = !query
            ? this.apps
            : this.apps.filter((app) =>
                app.name.toLowerCase().includes(query)
            );
        return apps.map((app) => {
            let icon = app.webIconData;
            if (icon && !icon.startsWith("data:image")) {
                const prefix = icon.startsWith("P") ? "data:image/svg+xml;base64," : "data:image/png;base64,";
                icon = prefix + icon.replace(/\s/g, "");
            }
            return {
                ...app,
                webIconData: icon,
            };
        });
    }

    selectApp(app) {
        this.menuService.selectMenu(app);
        this.close();
    }

    close() {
        this.state.isOpen = false;
        this.state.query = "";
    }
}

registry.category("main_components").add("ydod_app_drawer", {
    Component: AppDrawer,
});
