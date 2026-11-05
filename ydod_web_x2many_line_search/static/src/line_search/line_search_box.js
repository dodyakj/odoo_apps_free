import { Component, useEffect, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { applyRowVisibility, clearRanges, highlightCells } from "./line_search_highlight";

export class LineSearchBox extends Component {
    static template = "ydod_web_x2many_line_search.LineSearchBox";
    static props = {
        lineSearch: Object,
        onInput: Function,
        onClear: Function,
        setContainer: { type: Function, optional: true },
    };

    setup() {
        const lineSearchService = useService("x2many_line_search");
        this.lineSearch = useState(this.props.lineSearch);
        this.rootRef = useRef("root");
        this.inputRef = useRef("input");
        this.ranges = [];
        this.frame = null;
        useEffect(
            () => {
                const unregister = lineSearchService.register({
                    getEl: () => this.rootRef.el,
                    focus: () => this.focus(),
                });
                // the field matches the text displayed in the rows of the list
                this.props.setContainer?.(() => this.rootRef.el?.parentElement);
                // rows re-rendered by the list (paging, new lines, edits) get
                // their visibility and highlight back
                const container = this.rootRef.el?.parentElement;
                // the field widget stacks the box on its own row above the list
                container?.classList.add("o_x2m_line_search_host");
                const observer = new MutationObserver(() => {
                    if (this.props.lineSearch.filtering) {
                        this.scheduleHighlight();
                    }
                });
                if (container) {
                    observer.observe(container, { childList: true, subtree: true });
                }
                return () => {
                    container?.classList.remove("o_x2m_line_search_host");
                    this.props.setContainer?.(null);
                    observer.disconnect();
                    unregister();
                    cancelAnimationFrame(this.frame);
                    clearRanges(this.ranges);
                };
            },
            () => []
        );
        useEffect(
            () => this.scheduleHighlight(),
            () => [this.lineSearch.version, this.lineSearch.filtering]
        );
    }

    scheduleHighlight() {
        const lineSearch = this.props.lineSearch;
        applyRowVisibility(this.rootRef.el?.parentElement, lineSearch);
        cancelAnimationFrame(this.frame);
        // wait for the list renderer to apply the new row classes
        this.frame = requestAnimationFrame(() => {
            this.frame = requestAnimationFrame(() => {
                const container = this.rootRef.el?.parentElement;
                applyRowVisibility(container, lineSearch);
                const words = lineSearch.filtering ? lineSearch.words : [];
                highlightCells(container, words || [], this.ranges);
            });
        });
    }

    focus() {
        const input = this.inputRef.el;
        if (input) {
            input.focus();
            input.select();
            this.rootRef.el?.scrollIntoView({ block: "nearest" });
        }
    }

    onInput(ev) {
        this.props.onInput(ev.target.value);
    }

    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.onClear();
        }
    }
}
