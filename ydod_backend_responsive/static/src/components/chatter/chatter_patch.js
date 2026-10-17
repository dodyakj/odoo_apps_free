/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

if (session.ydod_chatter_position === "bottom") {
    document.body.classList.add("ydod_chatter_bottom");
}

patch(FormController.prototype, "ydod_backend_responsive.form_controller", {
    get className() {
        const result = this._super();
        const chatterPos = session.ydod_chatter_position || "sided";
        if (chatterPos === "bottom") {
            delete result["o_xxl_form_view h-100"];
        }
        return result;
    },
});
