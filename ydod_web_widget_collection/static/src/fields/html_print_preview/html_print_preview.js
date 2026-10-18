/** @odoo-module **/

import { Component, useRef } from "@odoo/owl";
import { _lt, _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { sprintf } from "@web/core/utils/strings";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Paper sizes in millimeters (width, height) in portrait orientation.
const PAGE_SIZES = {
    A3: [297, 420],
    A4: [210, 297],
    A5: [148, 210],
    Letter: [216, 279],
    Legal: [216, 356],
};

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/**
 * Renders an Html field inside an isolated, paper-styled iframe and offers a
 * "Print / Save as PDF" button that uses the browser's native print dialog.
 */
export class YdodHtmlPrintPreviewField extends Component {
    setup() {
        this.iframeRef = useRef("iframe");
        this._cache = { key: null, doc: "" };
    }

    get rawValue() {
        const value = this.props.value;
        return value ? String(value) : "";
    }

    get hasContent() {
        const text = this.rawValue.replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim();
        return text.length > 0 || /<(img|table|hr|video|svg)\b/i.test(this.rawValue);
    }

    get pageSize() {
        const requested = String(this.props.pageSize || "A4");
        const match = Object.keys(PAGE_SIZES).find(
            (size) => size.toLowerCase() === requested.toLowerCase()
        );
        return match || "A4";
    }

    get orientation() {
        return this.props.orientation === "landscape" ? "landscape" : "portrait";
    }

    get pageLabel() {
        return this.orientation === "landscape"
            ? sprintf(_t("%s landscape"), this.pageSize)
            : sprintf(_t("%s portrait"), this.pageSize);
    }

    get title() {
        const data = (this.props.record && this.props.record.data) || {};
        const displayName = data.display_name;
        return (
            this.props.title ||
            (typeof displayName === "string" && displayName) ||
            this.props.fieldLabel ||
            _t("Document")
        );
    }

    get paperWidthMm() {
        const [w, h] = PAGE_SIZES[this.pageSize];
        return this.orientation === "landscape" ? h : w;
    }

    get paperHeightMm() {
        const [w, h] = PAGE_SIZES[this.pageSize];
        return this.orientation === "landscape" ? w : h;
    }

    get paperStyle() {
        return `width: ${this.paperWidthMm}mm; max-width: 100%; min-height: ${this.paperHeightMm}mm;`;
    }

    /** Memoized per value/page settings so unrelated record updates do not reload the iframe. */
    get srcdoc() {
        const key = [this.rawValue, this.pageSize, this.orientation, this.title].join("\u0000");
        if (this._cache.key !== key) {
            this._cache = { key, doc: this._buildDocument() };
        }
        return this._cache.doc;
    }

    _buildDocument() {
        const css = `
@page { size: ${this.pageSize} ${this.orientation}; margin: 15mm; }
html, body { margin: 0; padding: 0; background-color: #ffffff; color: #212529; }
body { font-family: "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: 11pt; line-height: 1.5;
       padding: 15mm; box-sizing: border-box; word-wrap: break-word; }
h1 { font-size: 20pt; } h2 { font-size: 16pt; } h3 { font-size: 14pt; } h4, h5, h6 { font-size: 12pt; }
img { max-width: 100%; height: auto; }
table { border-collapse: collapse; max-width: 100%; }
td, th { padding: 4px 8px; vertical-align: top; }
table.table-bordered td, table.table-bordered th { border: 1px solid #dee2e6; }
blockquote { border-left: 3px solid #adb5bd; margin: 0.5em 0; padding-left: 1em; color: #495057; }
pre { background-color: #f8f9fa; padding: 0.75em; border: 1px solid #dee2e6; white-space: pre-wrap; }
a { color: #0d6efd; }
@media print { body { padding: 0; } }
`;
        return (
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\"/>" +
            `<title>${escapeHtml(this.title)}</title><style>${css}</style></head>` +
            `<body>${this.rawValue}</body></html>`
        );
    }

    onIframeLoad() {
        const iframe = this.iframeRef.el;
        if (!iframe) {
            return;
        }
        try {
            const doc = iframe.contentDocument;
            if (doc && doc.documentElement) {
                const height = doc.documentElement.scrollHeight;
                if (height > 0) {
                    iframe.style.height = `${height}px`;
                }
            }
        } catch (error) {
            // The document is same-origin; this guard only protects exotic browsers.
        }
    }

    onPrint() {
        const iframe = this.iframeRef.el;
        const win = iframe && iframe.contentWindow;
        if (!win) {
            return;
        }
        win.focus();
        win.print();
    }
}

YdodHtmlPrintPreviewField.template = "ydod_web_widget_collection.HtmlPrintPreviewField";
YdodHtmlPrintPreviewField.props = {
    ...standardFieldProps,
    pageSize: { type: String, optional: true },
    orientation: { type: String, optional: true },
    title: { type: String, optional: true },
    fieldLabel: { type: String, optional: true },
    hideButton: { type: Boolean, optional: true },
};
YdodHtmlPrintPreviewField.defaultProps = {
    pageSize: "A4",
    orientation: "portrait",
    hideButton: false,
};
YdodHtmlPrintPreviewField.displayName = _lt("yDoD HTML Print Preview");
YdodHtmlPrintPreviewField.supportedTypes = ["html"];
// Always rendered: an empty field shows the "Nothing to print" placeholder.
YdodHtmlPrintPreviewField.isEmpty = () => false;
YdodHtmlPrintPreviewField.extractProps = ({ attrs, field }) => {
    const options = attrs.options || {};
    const props = {
        pageSize: options.page_size ? String(options.page_size) : "A4",
        orientation: options.orientation === "landscape" ? "landscape" : "portrait",
        hideButton: Boolean(options.hide_button),
    };
    if (options.title) {
        props.title = String(options.title);
    }
    const label = attrs.string || (field && field.string);
    if (label) {
        props.fieldLabel = String(label);
    }
    return props;
};

registry.category("fields").add("ydod_html_print_preview", YdodHtmlPrintPreviewField);
