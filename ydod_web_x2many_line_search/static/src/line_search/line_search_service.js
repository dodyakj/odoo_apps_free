/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";

/**
 * Forward options="{'line_search': False}" of x2many fields to the component
 * through its crudOptions prop.
 */
function patchFieldDescriptors() {
    for (const [, descriptor] of registry.category("fields").getEntries()) {
        const Comp = descriptor?.component;
        if (
            !Comp ||
            !(Comp === X2ManyField || Comp.prototype instanceof X2ManyField) ||
            typeof descriptor.extractProps !== "function" ||
            descriptor.lineSearchPatched
        ) {
            continue;
        }
        const extractProps = descriptor.extractProps;
        try {
            descriptor.extractProps = function (fieldInfo, dynamicInfo) {
                const props = extractProps.call(this, fieldInfo, dynamicInfo);
                if (props && fieldInfo?.options?.line_search === false) {
                    props.crudOptions = { ...(props.crudOptions || {}), line_search: false };
                }
                return props;
            };
            descriptor.lineSearchPatched = true;
        } catch {
            // frozen descriptor: crudOptions already carries the field options
        }
    }
}

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
        patchFieldDescriptors();
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
