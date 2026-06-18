import { discussSidebarItemsRegistry } from "@mail/core/public_web/discuss_sidebar";
import { markEventHandled } from "@web/core/utils/misc";

import { Component, onWillDestroy, onWillStart, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { useService } from "@web/core/utils/hooks";

class MessengerThreadItem extends Component {
    static template = "omi_core.MessengerThreadItem";
    static props = ["thread", "onOpen"];
    static components = {};

    setup() {
        super.setup();
        this.store = useState(useService("mail.store"));
        this.floating = useDropdownState();
        this.open = this.open.bind(this);
    }

    get thread() {
        return this.props.thread;
    }

    get isActive() {
        return (
            this.store.discuss.thread?.model === "discuss.channel" &&
            this.store.discuss.thread?.id === this.thread.id
        );
    }

    open(ev) {
        markEventHandled(ev, "sidebar.openThread");
        this.props.onOpen(this.thread);
    }
}

export class DiscussSidebarMessenger extends Component {
    static template = "omi_core.DiscussSidebarMessenger";
    static props = {};
    static components = { Dropdown, MessengerThreadItem };

    setup() {
        super.setup();
        this.store = useState(useService("mail.store"));
        this.orm = useService("orm");
        this.companyService = useService("company");
        this.floating = useDropdownState();
        this.state = useState({
            loading: false,
            isActiveCompany: false,
        });
        this.refresh = this.refresh.bind(this);
        this.openThread = this.openThread.bind(this);
        this.refreshTimer = null;
        onWillStart(async () => {
            await this.refresh();
            if (this.state.isActiveCompany) {
                this.refreshTimer = setInterval(() => this.refresh(), 15000);
            }
        });
        onWillDestroy(() => {
            if (this.refreshTimer) {
                clearInterval(this.refreshTimer);
            }
        });
    }

    get threads() {
        const currentCompanyId = this.companyService.currentCompany.id;
        return Object.values(this.store.Thread.records)
            .filter(thread => thread.is_messenger_channel && thread.messenger_company_id === currentCompanyId)
            .sort((t1, t2) => {
                return (t2.lastInterestDt || t2.id) - (t1.lastInterestDt || t1.id);
            });
    }

    get hasItems() {
        return this.threads.length > 0;
    }

    async refresh() {
        this.state.loading = true;
        try {
            const result = await this.orm.call(
                "discuss.channel",
                "get_messenger_sidebar_threads",
                [[]]
            );
            this.state.isActiveCompany = result.is_active;
            if (result.is_active) {
                this.store.insert(result.store_data);
            }
        } finally {
            this.state.loading = false;
        }
    }

    async openThread(thread) {
        if (thread) {
            thread.setAsDiscussThread();
        }
    }
}

discussSidebarItemsRegistry.add("omi_messenger", DiscussSidebarMessenger, { sequence: 25 });
