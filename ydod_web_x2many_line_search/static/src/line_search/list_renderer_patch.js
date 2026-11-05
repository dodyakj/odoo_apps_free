import { useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        // subscribe to the search state of the enclosing x2many field
        this.lineSearchState = this.env.lineSearch ? useState(this.env.lineSearch) : null;
    },

    getRowClass(record) {
        const classes = super.getRowClass(...arguments);
        const lineSearch = this.lineSearchState;
        if (
            !lineSearch ||
            !lineSearch.filtering ||
            lineSearch.visibleIds.has(record.id) ||
            record.isNew ||
            record === this.props.list?.editedRecord
        ) {
            return classes;
        }
        // only hide the row: the record and its pending changes stay in the list
        return `${classes || ""} d-none`;
    },
});
