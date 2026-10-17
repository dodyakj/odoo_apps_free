import { FormRenderer } from "@web/views/form/form_renderer";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { SIZES } from "@web/core/ui/ui_service";

patch(FormRenderer.prototype, {
    mailLayout(hasAttachmentContainer) {
        const chatterPos = session.ydod_chatter_position || "sided";
        if (chatterPos === "bottom") {
            return "BOTTOM_CHATTER";
        }
        if (super.mailLayout) {
            const layout = super.mailLayout(hasAttachmentContainer);
            if (chatterPos === "sided" && layout === "BOTTOM_CHATTER" && this.uiService && this.uiService.size >= SIZES.LG) {
                return "SIDE_CHATTER";
            }
            return layout;
        }
        return "NONE";
    },
});
