/** @odoo-module **/

import { FormRenderer } from "@web/views/form/form_renderer";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        const chatterPos = session.ydod_chatter_position || "sided";
        if (chatterPos === "bottom") {
            document.body.classList.add("ydod_chatter_bottom");
        } else {
            document.body.classList.remove("ydod_chatter_bottom");
        }
    },
});
