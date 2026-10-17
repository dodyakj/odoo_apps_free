import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";

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

        this.close = () => {
            this.state.isOpen = false;
            this.state.query = "";
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
}

registry.category("main_components").add("ydod_app_drawer", {
    Component: AppDrawer,
});

patch(NavBar.prototype, {
    _openAppMenuSidebar() {
        this.env.bus.trigger("TOGGLE_APP_DRAWER");
    },
});
