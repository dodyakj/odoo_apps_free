import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    getRowClass(record) {
        const classes = super.getRowClass(...arguments);
        const lineSearch = this.env.lineSearch;
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
