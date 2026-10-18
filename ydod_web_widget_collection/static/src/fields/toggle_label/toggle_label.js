/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Boolean switch that displays a configurable text (and color) for the
 * current state. Usage:
 *   <field name="active" widget="ydod_toggle_label"
 *          options="{'on_label': 'Active', 'off_label': 'Archived'}"/>
 */
export class YdodToggleLabelField extends Component {
    static template = "ydod_web_widget_collection.ToggleLabelField";
    static props = {
        ...standardFieldProps,
        onLabel: { type: String, optional: true },
        offLabel: { type: String, optional: true },
        onColor: { type: String, optional: true },
        offColor: { type: String, optional: true },
        labelPosition: { type: String, optional: true },
        autosave: { type: Boolean, optional: true },
    };
    static defaultProps = {
        labelPosition: "right",
        autosave: true,
    };

    get value() {
        return Boolean(this.props.record.data[this.props.name]);
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
     * Keep the click inside the widget so a list row does not open or
     * switch to edition when the user only wants to flip the switch.
     *
     * @param {MouseEvent} ev
     */
    onWrapperClick(ev) {
        ev.stopPropagation();
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
        await this.props.record.update(
            { [this.props.name]: newValue },
            { save: this.props.autosave }
        );
    }
}

export const ydodToggleLabelField = {
    component: YdodToggleLabelField,
    displayName: _t("yDoD Labeled Toggle"),
    supportedTypes: ["boolean"],
    supportedOptions: [
        { label: _t("On label"), name: "on_label", type: "string" },
        { label: _t("Off label"), name: "off_label", type: "string" },
        { label: _t("On color"), name: "on_color", type: "string" },
        { label: _t("Off color"), name: "off_color", type: "string" },
        {
            label: _t("Label position"),
            name: "label_position",
            type: "selection",
            choices: [
                { label: _t("Right"), value: "right" },
                { label: _t("Left"), value: "left" },
            ],
            default: "right",
        },
        { label: _t("Autosave"), name: "autosave", type: "boolean", default: true },
    ],
    extractProps({ options }, dynamicInfo) {
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
        // Like the core boolean_toggle: only the readonly modifier disables the
        // switch, so it stays clickable in non-editable list views.
        if (dynamicInfo && typeof dynamicInfo.readonly === "boolean") {
            props.readonly = dynamicInfo.readonly;
        }
        return props;
    },
};

registry.category("fields").add("ydod_toggle_label", ydodToggleLabelField);
