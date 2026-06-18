import { Thread } from "@mail/core/common/thread_model";
import { Record } from "@mail/core/common/record";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        this.is_messenger_channel = Record.attr(false);
        this.messenger_company_id = Record.attr();
        this.messenger_psid = Record.attr("");
        this.preview = Record.attr("");
    },

    _computeDiscussAppCategory() {
        if (this.is_messenger_channel) {
            return undefined;
        }
        return super._computeDiscussAppCategory(...arguments);
    },

    get displayName() {
        if (this.is_messenger_channel) {
            return this.name;
        }
        return super.displayName;
    },

    notifyMessageToUser(message) {
        if (this.is_messenger_channel) {
            const companyService = this.store.env.services.company;
            const currentCompanyId = companyService ? companyService.currentCompany.id : null;
            if (currentCompanyId && this.messenger_company_id !== currentCompanyId) {
                return; // Suppress notification / chat window popup for wrong company context
            }
        }
        return super.notifyMessageToUser(...arguments);
    },
});
