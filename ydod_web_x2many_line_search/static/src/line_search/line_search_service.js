/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

function distance(rect, x, y) {
    const dx = Math.max(rect.left - x, 0, x - rect.right);
    const dy = Math.max(rect.top - y, 0, y - rect.bottom);
    return Math.hypot(dx, dy);
}

export const x2manyLineSearchService = {
    dependencies: ["hotkey", "ui"],
    start(env, { hotkey, ui }) {
        const entries = new Set();
        const pointer = { x: null, y: null };
        const api = {
            register(entry) {
                entries.add(entry);
                return () => entries.delete(entry);
            },
        };
        if (!session.x2many_line_search) {
            return api;
        }
        document.addEventListener(
            "pointermove",
            (ev) => {
                pointer.x = ev.clientX;
                pointer.y = ev.clientY;
            },
            { passive: true }
        );

        function focusBestBox() {
            const scope = ui.activeElement;
            const candidates = [...entries]
                .map((entry) => ({ entry, el: entry.getEl() }))
                .filter(
                    ({ el }) =>
                        el &&
                        el.isConnected &&
                        el.getClientRects().length &&
                        (!scope || !scope.contains || scope.contains(el))
                );
            if (!candidates.length) {
                return;
            }
            candidates.sort((a, b) =>
                a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1
            );
            let best = candidates[0];
            if (pointer.x !== null) {
                let bestDistance = Infinity;
                for (const candidate of candidates) {
                    const area = candidate.el.parentElement || candidate.el;
                    const d = distance(area.getBoundingClientRect(), pointer.x, pointer.y);
                    if (d < bestDistance) {
                        bestDistance = d;
                        best = candidate;
                    }
                }
            }
            best.entry.focus();
        }

        hotkey.add("alt+f", focusBestBox, {
            allowRepeat: false,
            bypassEditableProtection: true,
            global: true,
        });
        return api;
    },
};

registry.category("services").add("x2many_line_search", x2manyLineSearchService);
