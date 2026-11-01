/** @odoo-module **/

import { Component, proxy, signal, t, useProps, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { GLOBAL_SEARCH_MODEL } from "./global_search_config";

export class GlobalSearchDialog extends Component {
    static template = "ydod_global_search.GlobalSearchDialog";

    props = useProps({
        config: t.object().optional(),
        close: t.function().optional(),
    });
    inputRef = signal(null, { type: t.ref() });
    panelRef = signal(null, { type: t.ref() });

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({ term: "", groups: [], activeIndex: 0, loading: false, searched: false });
        this.flat = [];
        this.timer = null;
        this.requestId = 0;
        onMounted(() => this.inputRef()?.focus());
        onWillUnmount(() => clearTimeout(this.timer));
    }

    get config() {
        return this.props.config || {};
    }

    close() {
        this.requestId++;
        this.props.close?.();
    }

    onBackdropClick(ev) {
        if (ev.target === ev.currentTarget) {
            this.close();
        }
    }

    onInput(ev) {
        this.state.term = ev.target.value;
        clearTimeout(this.timer);
        const term = this.state.term.trim();
        const requestId = ++this.requestId;
        if (term.length < (this.config.min_chars || 1)) {
            this.setGroups([]);
            this.state.loading = false;
            this.state.searched = false;
            return;
        }
        this.timer = setTimeout(async () => {
            this.state.loading = true;
            let groups = [];
            try {
                groups = await this.orm.call(GLOBAL_SEARCH_MODEL, "ydod_search", [term]);
            } finally {
                if (requestId === this.requestId) {
                    this.state.loading = false;
                }
            }
            if (requestId !== this.requestId) {
                return; // stale response
            }
            this.state.searched = true;
            this.setGroups(groups);
        }, this.config.delay || 0);
    }

    setGroups(groups) {
        const flat = [];
        for (const group of groups) {
            for (const record of group.records) {
                record.idx = flat.length;
                flat.push({ group, record });
            }
        }
        this.flat = flat;
        this.state.groups = groups;
        this.state.activeIndex = 0;
    }

    onKeydown(ev) {
        const count = this.flat.length;
        switch (ev.key) {
            case "ArrowDown":
            case "ArrowUp":
                ev.preventDefault();
                if (count) {
                    const step = ev.key === "ArrowDown" ? 1 : -1;
                    this.state.activeIndex = (this.state.activeIndex + step + count) % count;
                    requestAnimationFrame(() =>
                        this.panelRef()
                            ?.querySelector(".o_ydod_gs_active")
                            ?.scrollIntoView({ block: "nearest" })
                    );
                }
                break;
            case "Enter": {
                ev.preventDefault();
                const item = this.flat[this.state.activeIndex];
                if (item) {
                    if (ev.ctrlKey || ev.metaKey) {
                        this.openList(item.group);
                    } else {
                        this.openRecord(item.group, item.record);
                    }
                }
                break;
            }
            case "Escape":
                ev.preventDefault();
                ev.stopPropagation();
                this.close();
                break;
        }
    }

    async openRecord(group, record) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: group.model,
            res_id: record.id,
            views: [[false, "form"]],
            target: "current",
        });
        this.close();
    }

    async openList(group) {
        const action = await this.orm.call(GLOBAL_SEARCH_MODEL, "ydod_get_action", [
            group.config_id,
            this.state.term,
        ]);
        if (action) {
            await this.action.doAction(action);
        }
        this.close();
    }
}

let closeOpenDialog = null;

/** Open the search popup through the dialog service (only one at a time). */
export function openGlobalSearch(dialogService, config) {
    if (closeOpenDialog || !config?.enabled) {
        return;
    }
    closeOpenDialog = dialogService.add(
        GlobalSearchDialog,
        { config },
        { onClose: () => (closeOpenDialog = null) }
    );
}
