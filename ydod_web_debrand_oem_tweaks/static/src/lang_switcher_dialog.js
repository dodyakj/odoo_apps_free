/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class YdodLangSwitcherDialog extends Component {
    setup() {
        this.orm = useService("orm");
        this.user = useService("user");
        this.currentLang = this.user.lang || (this.user.context && this.user.context.lang) || "";
        this.state = useState({ langs: [], loading: true, saving: false });
        onWillStart(async () => {
            const langs = await this.orm.call("res.lang", "get_installed", []);
            this.state.langs = langs.map(([code, name]) => ({ code, name }));
            this.state.loading = false;
        });
    }

    get title() {
        return _t("Choose your language");
    }

    async selectLang(code) {
        if (this.state.saving) {
            return;
        }
        if (code === this.currentLang) {
            this.close();
            return;
        }
        this.state.saving = true;
        await this.orm.write("res.users", [this.user.userId], { lang: code });
        browser.location.reload();
    }

    close() {
        if (this.props.close) {
            this.props.close();
        }
    }
}
YdodLangSwitcherDialog.template = "ydod_web_debrand_oem_tweaks.LangSwitcherDialog";
YdodLangSwitcherDialog.components = { Dialog };
YdodLangSwitcherDialog.props = { close: { type: Function, optional: true } };
