import { FormRenderer } from "@web/views/form/form_renderer";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

patch(FormRenderer.prototype, {
    mailLayout(hasAttachmentContainer) {
        const chatterPos = session.ydod_chatter_position || "sided";
        if (chatterPos === "bottom") {
            return "BOTTOM_CHATTER";
        }
        if (super.mailLayout) {
            return super.mailLayout(hasAttachmentContainer);
        }
        return "NONE";
    },
});
