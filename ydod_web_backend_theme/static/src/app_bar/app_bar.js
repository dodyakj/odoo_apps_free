import { Component, proxy, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useEnv } from "@web/owl2/utils";
import { session } from "@web/session";

const NAVBAR_FALLBACK_HEIGHT = 46;
const FAVICON_URL = "/ydod_web_backend_theme/favicon";

/** Company selected in the company switcher (cids cookie), if any. */
function getActiveCompanyId() {
    const match = document.cookie.match(/(?:^|;\s*)cids=([^;]*)/);
    const cid = match && parseInt(decodeURIComponent(match[1]).split(/[-,]/)[0], 10);
    return cid || session.user_companies?.current_company || false;
}

export class YdodAppBar extends Component {
    static template = "ydod_web_backend_theme.AppBar";

    setup() {
        const env = useEnv();
        this.menu = useService("menu");
        this.orm = useService("orm");
        this.mode = session.ydod_app_bar_mode || "expanded";
        this.companyId = getActiveCompanyId();
        this.theme = (session.ydod_company_themes || {})[this.companyId] || {
            has_background: session.ydod_has_background,
            background_color: session.ydod_background_color,
            unique: 0,
        };
        this.state = proxy({
            order: [...(session.ydod_app_order || [])],
            currentAppId: this.menu.getCurrentApp()?.id || false,
            appsOpen: false,
            top: NAVBAR_FALLBACK_HEIGHT,
            dragId: false,
            dragOverId: false,
        });

        env.bus?.addEventListener("MENUS:APP-CHANGED", () => {
            this.state.currentAppId = this.menu.getCurrentApp()?.id || false;
            this.state.appsOpen = false;
        });

        // The web client lives as long as the page: no listener cleanup needed.
        onMounted(() => {
            this.state.top = this.getNavbarBottom();
            if (this.mode !== "hidden") {
                document.body.classList.add(`ydod_appbar_${this.mode}`);
            }
            this.updateFavicon();
            // Open our full-window apps menu instead of the navbar dropdown.
            document.addEventListener("click", (ev) => this.onDocumentClick(ev), true);
            document.addEventListener("keydown", (ev) => {
                if (ev.key === "Escape" && this.state.appsOpen) {
                    this.state.appsOpen = false;
                }
            });
        });
    }

    /** Apps of the menu service, sorted by the user's saved order. */
    get apps() {
        const apps = this.menu.getApps();
        const rank = new Map(this.state.order.map((id, index) => [id, index]));
        const position = (app, index) => (rank.has(app.id) ? rank.get(app.id) : apps.length + index);
        return apps
            .map((app, index) => ({ app, rank: position(app, index) }))
            .sort((a, b) => a.rank - b.rank)
            .map((entry) => entry.app);
    }

    get overlayStyle() {
        const styles = [
            `top: ${this.state.top}px`,
            `background-color: ${this.theme.background_color || "#714B67"}`,
        ];
        if (this.theme.has_background && this.companyId) {
            styles.push(
                `background-image: url('/web/image/res.company/${this.companyId}/ydod_background_image?unique=${this.theme.unique}')`
            );
        }
        return styles.join("; ");
    }

    getNavbarBottom() {
        const navbar = document.querySelector(".o_main_navbar");
        return navbar ? Math.round(navbar.getBoundingClientRect().bottom) : NAVBAR_FALLBACK_HEIGHT;
    }

    iconUrl(app) {
        return `/web/image/ir.ui.menu/${app.id}/web_icon_data`;
    }

    updateFavicon() {
        if (!this.companyId) {
            return;
        }
        const href = `${FAVICON_URL}?cid=${this.companyId}&unique=${this.theme.unique || 0}`;
        for (const link of document.querySelectorAll("link[rel~='icon']")) {
            if ((link.getAttribute("href") || "").startsWith(FAVICON_URL)) {
                link.setAttribute("href", href);
            }
        }
    }

    onDocumentClick(ev) {
        if (ev.target.closest && ev.target.closest(".o_navbar_apps_menu")) {
            ev.preventDefault();
            ev.stopPropagation();
            this.toggleApps();
        }
    }

    toggleApps() {
        if (!this.state.appsOpen) {
            this.state.top = this.getNavbarBottom();
        }
        this.state.appsOpen = !this.state.appsOpen;
    }

    openApp(app) {
        this.state.appsOpen = false;
        this.state.currentAppId = app.id;
        this.menu.selectMenu(app);
    }

    onDragStart(ev, app) {
        this.state.dragId = app.id;
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", String(app.id));
    }

    onDragOver(ev, app) {
        if (!this.state.dragId) {
            return;
        }
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
        this.state.dragOverId = app.id;
    }

    onDragEnd() {
        this.state.dragId = false;
        this.state.dragOverId = false;
    }

    async onDrop(ev, app) {
        ev.preventDefault();
        const dragId = this.state.dragId;
        this.onDragEnd();
        if (!dragId || dragId === app.id) {
            return;
        }
        const order = this.apps.map((item) => item.id).filter((id) => id !== dragId);
        order.splice(order.indexOf(app.id), 0, dragId);
        this.state.order = order;
        await this.orm.call("res.users", "ydod_set_app_order", [order]);
    }
}

registry.category("main_components").add("ydod_web_backend_theme.AppBar", {
    Component: YdodAppBar,
    props: {},
});
