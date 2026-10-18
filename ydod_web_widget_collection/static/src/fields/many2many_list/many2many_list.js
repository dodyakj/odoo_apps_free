/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Shows the records of a Many2many / One2many field as a vertical list
 * (bullet, number or plain). Each item opens its record; an optional limit
 * collapses the rest behind a "+N more" link.
 */
export class YdodMany2manyListField extends Component {
    static template = "ydod_web_widget_collection.Many2manyListField";
    static props = {
        ...standardFieldProps,
        style: { type: String, optional: true },
        limit: { type: Number, optional: true },
        openTarget: { type: String, optional: true },
        noOpen: { type: Boolean, optional: true },
    };
    static defaultProps = {
        style: "bullet",
        limit: 0,
        openTarget: "current",
        noOpen: false,
    };

    setup() {
        this.action = useService("action");
        this.state = useState({ expanded: false });
    }

    get items() {
        const list = this.props.record.data[this.props.name];
        const records = (list && list.records) || [];
        return records.map((rec) => ({
            key: rec.id,
            id: rec.resId || false,
            name: (rec.data && rec.data.display_name) || _t("Unnamed"),
        }));
    }

    get styleName() {
        return ["bullet", "number", "plain"].includes(this.props.style) ? this.props.style : "bullet";
    }

    get limit() {
        const limit = parseInt(this.props.limit, 10);
        return limit > 0 ? limit : 0;
    }

    get visibleItems() {
        if (!this.limit || this.state.expanded) {
            return this.items;
        }
        return this.items.slice(0, this.limit);
    }

    get hiddenCount() {
        return this.items.length - this.visibleItems.length;
    }

    get canCollapse() {
        return this.state.expanded && this.limit > 0 && this.items.length > this.limit;
    }

    get moreLabel() {
        return _t("+%s more", this.hiddenCount);
    }

    get canOpen() {
        return !this.props.noOpen;
    }

    get relation() {
        const field = this.props.record.fields[this.props.name];
        return field && field.relation;
    }

    get listClass() {
        return this.styleName === "plain" ? "o_ydod_m2m_list list-unstyled mb-0" : "o_ydod_m2m_list mb-0 ps-3";
    }

    toggleExpanded() {
        this.state.expanded = !this.state.expanded;
    }

    async openRecord(item) {
        if (!this.canOpen || !item.id || !this.relation) {
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: this.relation,
            res_id: item.id,
            views: [[false, "form"]],
            target: this.props.openTarget === "new" ? "new" : "current",
        });
    }
}

export const ydodMany2manyListField = {
    component: YdodMany2manyListField,
    displayName: _t("yDoD Many2many List"),
    supportedTypes: ["many2many", "one2many"],
    relatedFields: () => [{ name: "display_name", type: "char" }],
    supportedOptions: [
        {
            label: _t("List style"),
            name: "style",
            type: "selection",
            choices: [
                { label: _t("Bullet"), value: "bullet" },
                { label: _t("Number"), value: "number" },
                { label: _t("Plain"), value: "plain" },
            ],
            default: "bullet",
        },
        { label: _t("Limit (0 = unlimited)"), name: "limit", type: "number", default: 0 },
        {
            label: _t("Open target"),
            name: "open_target",
            type: "selection",
            choices: [
                { label: _t("Current window"), value: "current" },
                { label: _t("Dialog"), value: "new" },
            ],
            default: "current",
        },
        { label: _t("Disable opening"), name: "no_open", type: "boolean", default: false },
    ],
    extractProps({ options }) {
        return {
            style: ["bullet", "number", "plain"].includes(options.style) ? options.style : "bullet",
            limit: options.limit ? Number(options.limit) || 0 : 0,
            openTarget: options.open_target === "new" ? "new" : "current",
            noOpen: Boolean(options.no_open),
        };
    },
};

registry.category("fields").add("ydod_many2many_list", ydodMany2manyListField);
