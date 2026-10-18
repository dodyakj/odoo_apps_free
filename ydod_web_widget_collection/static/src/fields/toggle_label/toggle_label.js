/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _lt, _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Boolean switch that displays a configurable text (and color) for the
 * current state. Usage:
 *   <field name="active" widget="ydod_toggle_label"
 *          options="{'on_label': 'Active', 'off_label': 'Archived'}"/>
 */
export class YdodToggleLabelField extends Component {
    get value() {
        return Boolean(this.props.value);
    }

    get isReadonly() {
        return Boolean(this.props.readonly);
    }

    get label() {
        if (this.value) {
            return this.props.onLabel || _t("On");
        }
        return this.props.offLabel || _t("Off");
    }

    get color() {
        return (this.value ? this.props.onColor : this.props.offColor) || "";
    }

    get labelStyle() {
        return this.color ? `color: ${this.color};` : "";
    }

    get switchStyle() {
        if (!this.color) {
            return "";
        }
        if (this.value) {
            return `background-color: ${this.color}; border-color: ${this.color};`;
        }
        return `border-color: ${this.color};`;
    }

    get wrapperClass() {
        const classes = ["o_ydod_toggle_label", "d-inline-flex", "align-items-center", "gap-2"];
        classes.push(this.value ? "o_ydod_toggle_on" : "o_ydod_toggle_off");
        if (this.props.labelPosition === "left") {
            classes.push("flex-row-reverse");
        }
        if (this.isReadonly) {
            classes.push("o_ydod_toggle_readonly");
        }
        return classes.join(" ");
    }

    /**
     * An active switch must not open the record (readonly list) or re-enter
     * edition when clicked; a disabled one lets the click bubble so the row
     * behaves like any other cell.
     *
     * @param {MouseEvent} ev
     */
    onWrapperClick(ev) {
        if (!this.isReadonly) {
            ev.stopPropagation();
        }
    }

    /**
     * @param {Event} ev change event of the checkbox
     */
    async onChange(ev) {
        if (this.isReadonly) {
            ev.target.checked = this.value;
            return;
        }
        const newValue = Boolean(ev.target.checked);
        if (newValue === this.value) {
            return;
        }
        // Same contract as the core boolean_toggle: saves immediately when the
        // record is not in edition (readonly list / kanban) and autosave is on.
        await this.props.update(newValue, { save: this.props.autosave });
    }
}

YdodToggleLabelField.template = "ydod_web_widget_collection.ToggleLabelField";
YdodToggleLabelField.props = {
    ...standardFieldProps,
    onLabel: { type: String, optional: true },
    offLabel: { type: String, optional: true },
    onColor: { type: String, optional: true },
    offColor: { type: String, optional: true },
    labelPosition: { type: String, optional: true },
    autosave: { type: Boolean, optional: true },
};
YdodToggleLabelField.defaultProps = {
    labelPosition: "right",
    autosave: true,
};
YdodToggleLabelField.displayName = _lt("yDoD Labeled Toggle");
YdodToggleLabelField.supportedTypes = ["boolean"];
// A false boolean is a value, not an empty field (same as the core BooleanField).
YdodToggleLabelField.isEmpty = () => false;
YdodToggleLabelField.extractProps = ({ attrs }) => {
    const options = attrs.options || {};
    const props = {
        labelPosition: options.label_position === "left" ? "left" : "right",
        autosave: "autosave" in options ? Boolean(options.autosave) : true,
    };
    if (options.on_label) {
        props.onLabel = String(options.on_label);
    }
    if (options.off_label) {
        props.offLabel = String(options.off_label);
    }
    if (options.on_color) {
        props.onColor = String(options.on_color);
    }
    if (options.off_color) {
        props.offColor = String(options.off_color);
    }
    return props;
};

registry.category("fields").add("ydod_toggle_label", YdodToggleLabelField);
