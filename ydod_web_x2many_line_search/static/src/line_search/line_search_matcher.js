/** @odoo-module **/

import { registry } from "@web/core/registry";

const formatters = registry.category("formatters");
const SECTION_TYPES = ["line_section", "line_subsection"];

export function normalizeText(text) {
    return String(text ?? "")
        .normalize("NFD")
        .replace(/\p{Mn}/gu, "")
        .toLowerCase();
}

export function splitWords(query) {
    return normalizeText(query).split(/\s+/).filter(Boolean);
}

function displayType(record) {
    return record.data?.display_type || false;
}

function tryFormat(type, value, options = {}) {
    if (!formatters.contains(type)) {
        return "";
    }
    try {
        return formatters.get(type)(value, options) || "";
    } catch {
        return "";
    }
}

function fieldText(record, name) {
    const field = record.fields?.[name];
    const value = record.data?.[name];
    if (!field || value === undefined || value === null || value === false) {
        return "";
    }
    switch (field.type) {
        case "many2one":
            return String((Array.isArray(value) ? value[1] : value.display_name) ?? "");
        case "one2many":
        case "many2many":
            return (value.records || []).map((r) => r.data?.display_name || "").join(" ");
        case "selection": {
            const option = (field.selection || []).find(([key]) => key === value);
            return option ? `${option[1]} ${value}` : String(value);
        }
        case "integer":
        case "float":
        case "monetary": {
            const options = { digits: field.digits };
            const formatted = tryFormat(field.type === "integer" ? "integer" : "float", value, options);
            return `${value} ${formatted}`;
        }
        case "date":
        case "datetime":
            return tryFormat(field.type, value);
        case "html":
            return String(value).replace(/<[^>]*>/g, " ");
        case "boolean":
        case "binary":
        case "properties":
        case "json":
            return "";
        default:
            return typeof value === "object" ? "" : String(value);
    }
}

/**
 * Names of the field columns of the embedded list, falling back to the
 * fields loaded on the list when the arch columns are not available.
 * Hidden text columns are kept: line descriptions are often hidden as a
 * column but displayed by the product widget of another cell.
 */
export function getSearchFieldNames(archInfo, list) {
    const hidden = [true, "True", "1", "true"];
    const textTypes = ["char", "text", "html"];
    const fields = list?.fields || {};
    let names = (archInfo?.columns || [])
        .filter(
            (col) =>
                col.type === "field" &&
                col.name &&
                (!hidden.includes(col.column_invisible) ||
                    textTypes.includes(fields[col.name]?.type))
        )
        .map((col) => col.name);
    if (!names.length) {
        names = Object.keys(list?.activeFields || {});
    }
    return [...new Set(names)];
}

export function recordSearchText(record, names) {
    return normalizeText(names.map((name) => fieldText(record, name)).join(" "));
}

/**
 * Normalized text displayed in the rendered rows of `container`, keyed by
 * record id: whatever a widget shows in a cell (product with description,
 * badges, input values in edit mode) can be found by any part of it.
 */
export function renderedRowTexts(container) {
    const texts = new Map();
    if (!container) {
        return texts;
    }
    for (const row of container.querySelectorAll("tr.o_data_row[data-id]")) {
        const parts = [];
        for (const cell of row.querySelectorAll("td.o_data_cell")) {
            parts.push(cell.textContent || "");
            for (const input of cell.querySelectorAll("input, textarea")) {
                parts.push(input.value || "");
            }
        }
        texts.set(row.dataset.id, normalizeText(parts.join(" ").replace(/\s+/g, " ")));
    }
    return texts;
}

/**
 * Compute which rows stay visible for the given words.
 * Sections stay visible when they or one of their lines match, notes follow
 * their section. Sections and notes are not counted.
 */
export function computeLineSearch(records, words, getText) {
    const visibleIds = new Set();
    const matches = (record) => {
        const text = getText(record);
        return words.every((word) => text.includes(word));
    };
    let matched = 0;
    let total = 0;
    let parent = null;
    let current = { section: null, parent: null, selfHit: false, anyHit: false, notes: [] };
    const groups = [current];
    for (const record of records) {
        const type = displayType(record);
        if (SECTION_TYPES.includes(type)) {
            current = {
                section: record,
                parent: type === "line_subsection" ? parent : null,
                selfHit: matches(record),
                anyHit: false,
                notes: [],
            };
            if (type === "line_section") {
                parent = current;
            }
            groups.push(current);
        } else if (type === "line_note") {
            current.notes.push({ record, hit: matches(record) });
        } else {
            total++;
            if (matches(record)) {
                matched++;
                current.anyHit = true;
                visibleIds.add(record.id);
            }
        }
    }
    for (const group of groups) {
        group.visible = Boolean(group.section) && (group.selfHit || group.anyHit);
        if (group.visible && group.parent) {
            group.parent.visible = true;
        }
    }
    for (const group of groups) {
        if (group.visible) {
            visibleIds.add(group.section.id);
        }
        for (const note of group.notes) {
            if (group.section ? group.visible : note.hit) {
                visibleIds.add(note.record.id);
            }
        }
    }
    return { visibleIds, matched, total };
}
