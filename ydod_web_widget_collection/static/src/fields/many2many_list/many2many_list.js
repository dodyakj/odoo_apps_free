/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _lt, _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { sprintf } from "@web/core/utils/strings";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const LIST_STYLES = ["bullet", "number", "plain"];

/**
 * Shows the records of a Many2many / One2many field as a vertical list
 * (bullet, number or plain). Each item opens its record; an optional limit
 * collapses the rest behind a "+N more" link.
 */
export class YdodMany2manyListField extends Component {
    setup() {
        this.action = useService("action");
        this.state = useState({ expanded: false });
    }

    get items() {
        const list = this.props.value;
        const records = (list && list.records) || [];
        return records.map((rec) => ({
            key: rec.id,
            id: rec.resId || false,
            name: (rec.data && rec.data.display_name) || _t("Unnamed"),
        }));
    }

    get styleName() {
        return LIST_STYLES.includes(this.props.listStyle) ? this.props.listStyle : "bullet";
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
        return sprintf(_t("+%s more"), this.hiddenCount);
    }

    get canOpen() {
        return !this.props.noOpen;
    }

    get relation() {
        const fields = (this.props.record && this.props.record.fields) || {};
        const field = fields[this.props.name];
        return field && field.relation;
    }

    get listClass() {
        return this.styleName === "plain"
            ? "o_ydod_m2m_list list-unstyled mb-0"
            : "o_ydod_m2m_list mb-0 ps-3";
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

YdodMany2manyListField.template = "ydod_web_widget_collection.Many2manyListField";
YdodMany2manyListField.props = {
    ...standardFieldProps,
    listStyle: { type: String, optional: true },
    limit: { type: Number, optional: true },
    openTarget: { type: String, optional: true },
    noOpen: { type: Boolean, optional: true },
};
YdodMany2manyListField.defaultProps = {
    listStyle: "bullet",
    limit: 0,
    openTarget: "current",
    noOpen: false,
};
YdodMany2manyListField.displayName = _lt("yDoD Many2many List");
YdodMany2manyListField.supportedTypes = ["many2many", "one2many"];
// display_name of the linked records is read together with the list, in the
// same request as the other sub-records' data: no RPC per item.
YdodMany2manyListField.fieldsToFetch = {
    display_name: { name: "display_name", type: "char" },
};
YdodMany2manyListField.isEmpty = (record, fieldName) => {
    const list = record.data[fieldName];
    return !list || !list.records || !list.records.length;
};
YdodMany2manyListField.extractProps = ({ attrs }) => {
    const options = attrs.options || {};
    return {
        listStyle: LIST_STYLES.includes(options.style) ? options.style : "bullet",
        limit: options.limit ? Number(options.limit) || 0 : 0,
        openTarget: options.open_target === "new" ? "new" : "current",
        noOpen: Boolean(options.no_open),
    };
};

registry.category("fields").add("ydod_many2many_list", YdodMany2manyListField);
