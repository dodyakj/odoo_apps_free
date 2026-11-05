/** @odoo-module **/

import { reactive, useEffect, useSubEnv } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { LineSearchBox } from "./line_search_box";
import {
    computeLineSearch,
    getSearchFieldNames,
    recordSearchText,
    renderedRowTexts,
    splitWords,
} from "./line_search_matcher";

const DEBOUNCE_DELAY = 120;

// render the search box above the standard template, which stays untouched
if (X2ManyField.template === "web.X2ManyField") {
    X2ManyField.template = "ydod_web_x2many_line_search.X2ManyField";
}

patch(X2ManyField.prototype, "ydod_web_x2many_line_search", {
    setup() {
        this._super(...arguments);
        const activeField = this.activeField || this.props.record.activeFields[this.props.name] || {};
        const options = activeField.options || {};
        const active =
            Boolean(session.x2many_line_search) &&
            activeField.viewMode === "list" &&
            options.line_search !== false;
        // shared state: the search box and the list renderer subscribe to it
        this.lineSearch = reactive({
            active,
            query: "",
            words: [],
            filtering: false,
            visibleIds: new Set(),
            matched: 0,
            total: 0,
            version: 0,
            loading: false,
            loadedAll: false,
        });
        this.lineSearchBoxComponent = LineSearchBox;
        this.lineSearchCache = new Map();
        this.lineSearchTimer = null;
        this.lineSearchFrame = null;
        this.lineSearchGetContainer = null;
        useSubEnv({ lineSearch: active ? this.lineSearch : null });
        if (!active) {
            return;
        }
        useEffect(
            () => () => {
                clearTimeout(this.lineSearchTimer);
                cancelAnimationFrame(this.lineSearchFrame);
            },
            () => []
        );
        // keep the counter right when lines are added or removed while filtering
        useEffect(
            () => {
                if (this.lineSearch.filtering && !this.lineSearch.loading) {
                    this.lineSearchFilter();
                }
            },
            () => [this.lineSearchGetList()?.records?.length]
        );
    },

    lineSearchSetContainer(getter) {
        this.lineSearchGetContainer = getter;
    },

    lineSearchGetList() {
        return this.props.value || this.props.record.data[this.props.name];
    },

    onLineSearchInput(query) {
        this.lineSearch.query = query;
        clearTimeout(this.lineSearchTimer);
        if (!splitWords(query).length) {
            this.lineSearchReset();
            return;
        }
        this.lineSearchTimer = setTimeout(() => this.lineSearchRun(), DEBOUNCE_DELAY);
    },

    onLineSearchClear() {
        clearTimeout(this.lineSearchTimer);
        this.lineSearch.query = "";
        this.lineSearchReset();
    },

    lineSearchReset() {
        Object.assign(this.lineSearch, {
            filtering: false,
            words: [],
            visibleIds: new Set(),
            matched: 0,
            total: 0,
            version: this.lineSearch.version + 1,
        });
        this.lineSearchCache.clear();
    },

    async lineSearchRun() {
        const lineSearch = this.lineSearch;
        const list = this.lineSearchGetList();
        if (!list) {
            return;
        }
        if (!lineSearch.loadedAll) {
            // load the lines beyond the current page once, like the pager does
            lineSearch.loadedAll = true;
            const loaded = (list.records || []).length;
            if (typeof list.load === "function" && list.count > loaded) {
                lineSearch.loading = true;
                try {
                    const unselected =
                        typeof list.unselectRecord === "function"
                            ? await list.unselectRecord(true)
                            : true;
                    if (unselected === false) {
                        lineSearch.loadedAll = false;
                    } else {
                        await list.load({ offset: 0, limit: list.count });
                        this.render();
                    }
                } catch {
                    // errors are reported by the rpc layer; keep filtering loaded lines
                } finally {
                    lineSearch.loading = false;
                }
            }
        }
        this.lineSearchFilter();
        // lines loaded just now are rendered on the next frames: match their
        // displayed text too
        cancelAnimationFrame(this.lineSearchFrame);
        this.lineSearchFrame = requestAnimationFrame(() => {
            this.lineSearchFrame = requestAnimationFrame(() => {
                if (this.lineSearch.filtering) {
                    this.lineSearchFilter();
                }
            });
        });
    },

    lineSearchFilter() {
        const lineSearch = this.lineSearch;
        const list = this.lineSearchGetList();
        const words = splitWords(lineSearch.query);
        if (!list || !words.length) {
            this.lineSearchReset();
            return;
        }
        const names = getSearchFieldNames(this.archInfo, list);
        const editedRecord = list.editedRecord;
        const rowTexts = renderedRowTexts(this.lineSearchGetContainer?.());
        const result = computeLineSearch(
            list.records || [],
            words,
            (record) =>
                `${this.lineSearchText(record, names, editedRecord)} ${rowTexts.get(record.id) || ""}`
        );
        // new lines and the line being edited are never hidden
        for (const record of list.records || []) {
            if (record.isNew || record === editedRecord) {
                result.visibleIds.add(record.id);
            }
        }
        Object.assign(lineSearch, {
            filtering: true,
            words,
            visibleIds: result.visibleIds,
            matched: result.matched,
            total: result.total,
            version: lineSearch.version + 1,
        });
    },

    lineSearchText(record, names, editedRecord) {
        const cached = this.lineSearchCache.get(record.id);
        const volatile = record.isDirty || record.dirty || record.isNew || record === editedRecord;
        if (cached && cached.record === record && !volatile) {
            return cached.text;
        }
        const text = recordSearchText(record, names);
        this.lineSearchCache.set(record.id, { record, text });
        return text;
    },
});
