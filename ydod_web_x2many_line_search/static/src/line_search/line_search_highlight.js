/** @odoo-module **/

import { normalizeText } from "./line_search_matcher";

const HIGHLIGHT_NAME = "o_line_search";
const MAX_HIGHLIGHTED_ROWS = 500;

function getHighlight() {
    if (typeof CSS === "undefined" || !CSS.highlights || typeof Highlight === "undefined") {
        return null;
    }
    let highlight = CSS.highlights.get(HIGHLIGHT_NAME);
    if (!highlight) {
        highlight = new Highlight();
        CSS.highlights.set(HIGHLIGHT_NAME, highlight);
    }
    return highlight;
}

export const HIDDEN_CLASS = "o_x2m_line_search_hidden";

/**
 * Hide the rows of `container` that do not match. The list renderer does not
 * always re-render when only the query changes, so the visibility is applied
 * on the existing rows; the edited row always stays visible.
 */
export function applyRowVisibility(container, lineSearch) {
    if (!container) {
        return;
    }
    const filtering = Boolean(lineSearch.filtering);
    const visibleIds = lineSearch.visibleIds || new Set();
    for (const row of container.querySelectorAll("tr.o_data_row")) {
        const hide =
            filtering &&
            Boolean(row.dataset.id) &&
            !row.classList.contains("o_selected_row") &&
            !visibleIds.has(row.dataset.id);
        row.classList.toggle(HIDDEN_CLASS, hide);
    }
}

export function clearRanges(ranges) {
    const highlight = getHighlight();
    if (highlight) {
        for (const range of ranges) {
            highlight.delete(range);
        }
    }
    ranges.length = 0;
}

/**
 * Add the matching text of the visible cells of `container` to the shared
 * CSS highlight. The DOM itself is never modified.
 */
export function highlightCells(container, words, ranges) {
    clearRanges(ranges);
    const highlight = getHighlight();
    if (!highlight || !container || !words.length) {
        return;
    }
    const rows = container.querySelectorAll(`tr.o_data_row:not(.d-none):not(.${HIDDEN_CLASS})`);
    if (rows.length > MAX_HIGHLIGHTED_ROWS) {
        return;
    }
    for (const row of rows) {
        for (const cell of row.querySelectorAll("td.o_data_cell")) {
            const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
            let node;
            while ((node = walker.nextNode())) {
                const raw = node.nodeValue;
                if (!raw || !raw.trim()) {
                    continue;
                }
                let text = "";
                const offsets = [];
                for (let i = 0; i < raw.length; i++) {
                    const part = normalizeText(raw[i]);
                    for (let k = 0; k < part.length; k++) {
                        offsets.push(i);
                    }
                    text += part;
                }
                for (const word of words) {
                    let index = text.indexOf(word);
                    while (index !== -1) {
                        const range = new Range();
                        range.setStart(node, offsets[index]);
                        range.setEnd(node, offsets[index + word.length - 1] + 1);
                        highlight.add(range);
                        ranges.push(range);
                        index = text.indexOf(word, index + word.length);
                    }
                }
            }
        }
    }
}
