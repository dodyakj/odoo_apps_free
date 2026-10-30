/** @odoo-module **/

import { Component, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

const MIN_WIDTH = 300;
const MIN_HEIGHT = 200;
const HANDLE_SIZE = 14;
const INTERACTIVE = "button, a, input, select, textarea, [contenteditable='true'], .dropdown-menu";

const TARGETS = {
    chat: { container: ".o-mail-ChatWindow", header: ".o-mail-ChatWindow-header" },
    dialog: { container: ".modal-content", header: ".modal-header" },
};

function getTranslate(el) {
    return [parseFloat(el.dataset.ydodTx || "0"), parseFloat(el.dataset.ydodTy || "0")];
}

function setTranslate(el, x, y) {
    el.dataset.ydodTx = String(x);
    el.dataset.ydodTy = String(y);
    el.style.transform = `translate(${x}px, ${y}px)`;
}

/**
 * Invisible main component holding one delegated pointerdown listener:
 * drag dialogs / chat windows by their header, resize them from the
 * bottom-left and bottom-right corners, never below MIN_WIDTH x MIN_HEIGHT.
 */
export class YdodDragResize extends Component {
    static template = "ydod_web_debrand_oem_tweaks.DragResize";
    static props = {};

    setup() {
        const tweaks = session.ydod_tweaks || {};
        this.enabled = {
            chat: Boolean(tweaks.ydod_chat_draggable),
            dialog: Boolean(tweaks.ydod_dialog_draggable),
        };
        document.body.classList.toggle("o_ydod_chat_drag", this.enabled.chat);
        document.body.classList.toggle("o_ydod_dialog_drag", this.enabled.dialog);
        if (this.enabled.chat || this.enabled.dialog) {
            useExternalListener(document, "pointerdown", (ev) => this.onPointerDown(ev));
        }
    }

    findTarget(node) {
        for (const kind of ["chat", "dialog"]) {
            if (!this.enabled[kind]) {
                continue;
            }
            const el = node.closest(TARGETS[kind].container);
            if (el) {
                return { el, header: TARGETS[kind].header };
            }
        }
        return null;
    }

    onPointerDown(ev) {
        if (ev.button !== 0 || !(ev.target instanceof Element)) {
            return;
        }
        const found = this.findTarget(ev.target);
        if (!found) {
            return;
        }
        const { el, header } = found;
        const rect = el.getBoundingClientRect();
        const nearBottom = ev.clientY >= rect.bottom - HANDLE_SIZE;
        let mode = null;
        if (nearBottom && ev.clientX <= rect.left + HANDLE_SIZE) {
            mode = "bl";
        } else if (nearBottom && ev.clientX >= rect.right - HANDLE_SIZE) {
            mode = "br";
        } else {
            const headerEl = ev.target.closest(header);
            if (headerEl && el.contains(headerEl) && !ev.target.closest(INTERACTIVE)) {
                mode = "move";
            }
        }
        if (mode) {
            ev.preventDefault();
            this.startInteraction(el, mode, ev, rect);
        }
    }

    startInteraction(el, mode, startEv, startRect) {
        const startX = startEv.clientX;
        const startY = startEv.clientY;
        const [tx0, ty0] = getTranslate(el);
        let moved = false;
        document.body.classList.add("o_ydod_dragging");

        const onMove = (ev) => {
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;
            moved = moved || Math.abs(dx) + Math.abs(dy) > 3;
            if (mode === "move") {
                // keep the header reachable inside the viewport
                const minDy = -startRect.top;
                setTranslate(el, tx0 + dx, ty0 + Math.max(dy, minDy));
                return;
            }
            const width = Math.max(MIN_WIDTH, mode === "br" ? startRect.width + dx : startRect.width - dx);
            const height = Math.max(MIN_HEIGHT, startRect.height + dy);
            Object.assign(el.style, {
                width: `${width}px`,
                maxWidth: "none",
                height: `${height}px`,
                maxHeight: "none",
            });
            el.classList.add("o_ydod_resized");
            // anchor the top edge and the opposite side edge
            const rect = el.getBoundingClientRect();
            const wantedLeft = mode === "br" ? startRect.left : startRect.right - width;
            const [tx, ty] = getTranslate(el);
            setTranslate(el, tx + wantedLeft - rect.left, ty + startRect.top - rect.top);
        };

        const onUp = () => {
            document.removeEventListener("pointermove", onMove);
            document.removeEventListener("pointerup", onUp);
            document.removeEventListener("pointercancel", onUp);
            document.body.classList.remove("o_ydod_dragging");
            if (moved) {
                // swallow the click following a drag (e.g. chat header fold)
                const swallow = (clickEv) => {
                    clickEv.preventDefault();
                    clickEv.stopPropagation();
                };
                window.addEventListener("click", swallow, { capture: true, once: true });
                setTimeout(() => window.removeEventListener("click", swallow, { capture: true }), 0);
            }
        };

        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
        document.addEventListener("pointercancel", onUp);
    }
}

registry.category("main_components").add("ydod_drag_resize", { Component: YdodDragResize });
