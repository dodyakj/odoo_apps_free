/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AppDrawer extends Component {
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
            this.onNavbarAppsClick = (ev) => {
                const appsBtn = ev.target.closest(".o_navbar_apps_menu");
                if (appsBtn) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    this.state.isOpen = !this.state.isOpen;
                    if (this.state.isOpen) {
                        this.state.query = "";
                    }
                }
            };
            document.addEventListener("click", this.onNavbarAppsClick, true);
        });

        onWillUnmount(() => {
            this.env.bus.removeEventListener("TOGGLE_APP_DRAWER", this.onToggleDrawer);
            window.removeEventListener("keydown", this.onKeyDown);
            if (this.onNavbarAppsClick) {
                document.removeEventListener("click", this.onNavbarAppsClick, true);
            }
        });
    }

    get apps() {
        return this.menuService.getApps();
    }

    get filteredApps() {
        const query = this.state.query.trim().toLowerCase();
        if (!query) {
            return this.apps;
        }
        return this.apps.filter((app) =>
            app.name.toLowerCase().includes(query)
        );
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

AppDrawer.template = "ydod_backend_responsive.AppDrawer";

registry.category("main_components").add("ydod_app_drawer", {
    Component: AppDrawer,
});
