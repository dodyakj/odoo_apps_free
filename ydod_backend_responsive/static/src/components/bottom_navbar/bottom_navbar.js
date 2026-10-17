/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

export class BottomNavBar extends Component {
    setup() {
        this.ui = useService("ui");
        this.actionService = useService("action");
        this.menuService = useService("menu");

        this.state = useState({
            isSmall: window.innerWidth < 768,
        });

        this.onResize = () => {
            const isSmall = window.innerWidth < 768;
            if (this.state.isSmall !== isSmall) {
                this.state.isSmall = isSmall;
                if (isSmall) {
                    document.body.classList.add("ydod_has_bottombar");
                } else {
                    document.body.classList.remove("ydod_has_bottombar");
                }
            }
        };

        onMounted(() => {
            window.addEventListener("resize", this.onResize);
            if (this.state.isSmall && this.isEnabled) {
                document.body.classList.add("ydod_has_bottombar");
            }
        });

        onWillUnmount(() => {
            window.removeEventListener("resize", this.onResize);
            document.body.classList.remove("ydod_has_bottombar");
        });
    }

    get isEnabled() {
        return session.ydod_enable_mobile_bottombar !== false;
    }

    get isVisible() {
        return this.state.isSmall && this.isEnabled;
    }

    openApps() {
        this.env.bus.trigger("TOGGLE_APP_DRAWER");
    }

    goBack() {
        if (this.actionService.canRestore && this.actionService.canRestore()) {
            this.actionService.restore();
        } else {
            window.history.back();
        }
    }

    toggleActions() {
        const burgerBtn = document.querySelector(".o_burger_menu_btn, .o_sidebar_toggler");
        if (burgerBtn) {
            burgerBtn.click();
        } else {
            this.env.bus.trigger("TOGGLE_APP_DRAWER");
        }
    }

    scrollToChatter() {
        const chatter = document.querySelector(".o_FormRenderer_chatterContainer, .oe_chatter");
        if (chatter) {
            chatter.scrollIntoView({ behavior: "smooth" });
        }
    }
}

BottomNavBar.template = "ydod_backend_responsive.BottomNavBar";

registry.category("main_components").add("ydod_bottom_navbar", {
    Component: BottomNavBar,
});
