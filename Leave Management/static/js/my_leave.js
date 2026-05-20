const myLeaveConfigElement = document.getElementById("my-leave-js-config");
const myLeaveConfig = myLeaveConfigElement ? myLeaveConfigElement.dataset : {};
const myLeaveCalendarDataUrl = myLeaveConfig.calendarDataUrl || "";
const myLeaveUrl = myLeaveConfig.myLeaveUrl || "";

function buildInlineReasonMoreButton(reasonText, fullText) {
    const moreBtn = document.createElement("button");
    moreBtn.type = "button";
    moreBtn.className = "reason-inline-more";
    moreBtn.textContent = "...more";
    moreBtn.dataset.reason = fullText;
    moreBtn.dataset.title = reasonText.dataset.title || "Reason";
    moreBtn.addEventListener("click", function () {
        openReasonTextModal(moreBtn.dataset.title, moreBtn.dataset.reason, moreBtn);
    });
    return moreBtn;
}

function fitInlineReason(reasonText, fullText) {
    const safeText = String(fullText || "").trim();
    reasonText.classList.remove("is-truncated");
    reasonText.replaceChildren(document.createTextNode(safeText || "-"));
    reasonText.dataset.full = safeText;
    if (!safeText) {
        return;
    }
    requestAnimationFrame(function () {
        if (reasonText.scrollHeight <= reasonText.clientHeight + 2) {
            return;
        }
        reasonText.classList.add("is-truncated");
        let low = 0;
        let high = safeText.length;
        let bestFit = "";
        while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            const candidate = safeText.slice(0, mid).trimEnd();
            reasonText.replaceChildren(document.createTextNode(candidate), buildInlineReasonMoreButton(reasonText, safeText));
            if (reasonText.scrollHeight <= reasonText.clientHeight + 2) {
                bestFit = candidate;
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }
        if (!bestFit) {
            bestFit = safeText.slice(0, Math.max(8, Math.floor(safeText.length / 2))).trimEnd();
        }
        reasonText.replaceChildren(document.createTextNode(bestFit), buildInlineReasonMoreButton(reasonText, safeText));
    });
}

function hydrateInlineReasons(root = document) {
    root.querySelectorAll(".js-inline-reason").forEach((node) => {
        const fullText = (node.dataset.full || node.textContent || "").trim();
        fitInlineReason(node, fullText);
    });
}

function formatRelativeLeaveAge(isoValue) {
    if (!isoValue) {
        return "-";
    }
    const target = new Date(isoValue);
    if (Number.isNaN(target.getTime())) {
        return "-";
    }
    const now = new Date();
    const diffMs = Math.max(0, now.getTime() - target.getTime());
    const diffMinutes = Math.floor(diffMs / (60 * 1000));
    const diffHours = Math.floor(diffMs / (60 * 60 * 1000));
    const minuteRemainder = String(diffMinutes % 60).padStart(2, "0");
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const startOfTarget = new Date(target.getFullYear(), target.getMonth(), target.getDate());
    const msPerDay = 24 * 60 * 60 * 1000;
    const diffDays = Math.max(0, Math.floor((startOfToday - startOfTarget) / msPerDay));
    if (diffMinutes <= 0) {
        return "just now";
    }
    if (diffMinutes === 1) {
        return "1 min ago";
    }
    if (diffMinutes <= 59) {
        return `${diffMinutes} min ago`;
    }
    if (diffHours === 1) {
        return `1 hour, ${minuteRemainder} min ago`;
    }
    if (diffHours <= 23) {
        return `${diffHours} hour, ${minuteRemainder} min ago`;
    }
    if (diffDays <= 6) {
        const dayUnit = diffDays === 1 ? "day" : "days";
        return `${diffDays} ${dayUnit} ago`;
    }
    return target.toLocaleDateString("en-US", {
        month: "short",
        day: "2-digit",
        year: "numeric"
    });
}

function hydrateRelativeDates() {
    document.querySelectorAll("[data-relative-datetime]").forEach((node) => {
        const formatted = formatRelativeLeaveAge(node.dataset.relativeDatetime);
        const count = Number.parseInt(node.dataset.relativeCount || "0", 10);
        if (formatted === "-") {
            node.textContent = "-";
            return;
        }
        node.textContent = count > 0 ? `${formatted} (${count})` : formatted;
    });
}

function hydrateDayBlocks() {
    document.querySelectorAll(".js-days-block").forEach((block) => {
        const valueNode = block.querySelector(".js-days-value");
        const labelNode = block.querySelector(".js-days-label");
        if (!valueNode || !labelNode) {
            return;
        }
        const targetValue = Number(block.dataset.daysTarget || "0");
        const suffixText = block.dataset.daysSuffix || "";
        const labelText = block.dataset.daysLabel || "";
        if (!Number.isFinite(targetValue)) {
            return;
        }
        valueNode.textContent = `${targetValue}${suffixText}`;
        labelNode.textContent = labelText;
    });
}

document.addEventListener("DOMContentLoaded", function () {
        const tabs = Array.from(document.querySelectorAll(".status-tab"));
        const panels = Array.from(document.querySelectorAll(".leave-panel"));
        function formatRelativeLeaveAge(isoValue) {
            if (!isoValue) {
                return "-";
            }
            const target = new Date(isoValue);
            if (Number.isNaN(target.getTime())) {
                return "-";
            }
            const now = new Date();
            const diffMs = Math.max(0, now.getTime() - target.getTime());
            const diffMinutes = Math.floor(diffMs / (60 * 1000));
            const diffHours = Math.floor(diffMs / (60 * 60 * 1000));
            const minuteRemainder = String(diffMinutes % 60).padStart(2, "0");
            const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            const startOfTarget = new Date(target.getFullYear(), target.getMonth(), target.getDate());
            const msPerDay = 24 * 60 * 60 * 1000;
            const diffDays = Math.max(0, Math.floor((startOfToday - startOfTarget) / msPerDay));
            if (diffMinutes <= 0) {
                return "just now";
            }
            if (diffMinutes === 1) {
                return "1 min ago";
            }
            if (diffMinutes <= 59) {
                return `${diffMinutes} min ago`;
            }
            if (diffHours === 1) {
                return `1 hour, ${minuteRemainder} min ago`;
            }
            if (diffHours <= 23) {
                return `${diffHours} hour, ${minuteRemainder} min ago`;
            }
            if (diffDays <= 6) {
                const dayUnit = diffDays === 1 ? "day" : "days";
                return `${diffDays} ${dayUnit} ago`;
            }
            return target.toLocaleDateString("en-US", {
                month: "short",
                day: "2-digit",
                year: "numeric"
            });
        }
        function hydrateRelativeDates() {
            document.querySelectorAll("[data-relative-datetime]").forEach((node) => {
                const formatted = formatRelativeLeaveAge(node.dataset.relativeDatetime);
                const count = Number.parseInt(node.dataset.relativeCount || "0", 10);
                if (formatted === "-") {
                    node.textContent = "-";
                    return;
                }
                node.textContent = count > 0 ? `${formatted} (${count})` : formatted;
            });
        }
        function animateDayValue(valueNode, labelNode, targetValue, suffixText = "", labelText = "") {
            const finalValue = Math.max(1, Number(targetValue) || 1);
            const duration = 480;
            const startTime = performance.now();
            valueNode.textContent = `0${suffixText}`;
            labelNode.textContent = labelText;
            function step(now) {
                const progress = Math.min((now - startTime) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const currentValue = Math.max(0, Math.round(finalValue * eased));
                valueNode.textContent = `${Math.min(currentValue, finalValue)}${suffixText}`;
                if (progress < 1) {
                    window.requestAnimationFrame(step);
                    return;
                }
                valueNode.textContent = `${finalValue}${suffixText}`;
            }
            window.requestAnimationFrame(step);
        }
        function hydrateDayBlocks() {
            document.querySelectorAll(".js-days-block").forEach((block) => {
                const valueNode = block.querySelector(".js-days-value");
                const labelNode = block.querySelector(".js-days-label");
                if (!valueNode || !labelNode) {
                    return;
                }
                const targetValue = Number(block.dataset.daysTarget || "0");
                const suffixText = block.dataset.daysSuffix || "";
                const labelText = block.dataset.daysLabel || "";
                if (!Number.isFinite(targetValue)) {
                    return;
                }
                valueNode.textContent = `${targetValue}${suffixText}`;
                labelNode.textContent = labelText;
            });
        }
        function animateDayBlocksForPanel(targetId) {
            const panel = document.getElementById(targetId);
            if (!panel) {
                return;
            }
            panel.querySelectorAll(".js-days-block").forEach((block) => {
                if (block.closest("tr")?.hidden) {
                    return;
                }
                const valueNode = block.querySelector(".js-days-value");
                const labelNode = block.querySelector(".js-days-label");
                const targetValue = Number(block.dataset.daysTarget || valueNode?.textContent || "1");
                const suffixText = block.dataset.daysSuffix || "";
                const labelText = block.dataset.daysLabel || "";
                if (!valueNode || !labelNode) {
                    return;
                }
                animateDayValue(valueNode, labelNode, targetValue, suffixText, labelText);
            });
        }
        hydrateRelativeDates();
        function setupTablePagination() {
            document.querySelectorAll(".js-paginated-table").forEach((wrapper) => {
                const panel = wrapper.closest(".leave-panel");
                const tbody = wrapper.querySelector("tbody");
                if (!panel || !tbody) {
                    return;
                }
                if (typeof refreshPanelPagination === "function") {
                    refreshPanelPagination(panel.id);
                    return;
                }
                const pagination = panel.querySelector(`[data-pagination-for="${panel.id}"]`);
                const rows = Array.from(tbody.querySelectorAll("tr:not(.table-empty-row)"));
                const emptyRow = tbody.querySelector(".table-empty-row");
                if (!pagination || rows.length === 0) {
                    if (pagination) {
                        pagination.hidden = true;
                        pagination.classList.add("is-hidden");
                    }
                    if (emptyRow) {
                        emptyRow.hidden = false;
                    }
                    return;
                }
                const firstBtn = pagination.querySelector('[data-page-action="first"]');
                const prevBtn = pagination.querySelector('[data-page-action="prev"]');
                const nextBtn = pagination.querySelector('[data-page-action="next"]');
                const lastBtn = pagination.querySelector('[data-page-action="last"]');
                const status = pagination.querySelector(".pagination-status");
                const rowsPerPage = parseInt(wrapper.dataset.rowsPerPage || "5", 10);
                const totalPages = Math.max(1, Math.ceil(rows.length / rowsPerPage));
                let currentPage = 1;
                const renderPage = () => {
                    rows.forEach((row, index) => {
                        const start = (currentPage - 1) * rowsPerPage;
                        const end = start + rowsPerPage;
                        row.hidden = !(index >= start && index < end);
                    });
                    status.textContent = `Page ${currentPage} of ${totalPages}`;
                    if (firstBtn) {
                        firstBtn.disabled = currentPage === 1;
                    }
                    if (prevBtn) {
                        prevBtn.disabled = currentPage === 1;
                    }
                    if (nextBtn) {
                        nextBtn.disabled = currentPage === totalPages;
                    }
                    if (lastBtn) {
                        lastBtn.disabled = currentPage === totalPages;
                    }
                    const hidePagination = totalPages <= 1;
                    pagination.hidden = hidePagination;
                    pagination.classList.toggle("is-hidden", hidePagination);
                    hydrateInlineReasons(panel);
                    animateDayBlocksForPanel(panel.id);
                };
                panel._paginationController = {
                    showRow(row) {
                        const rowIndex = rows.indexOf(row);
                        if (rowIndex === -1) {
                            return;
                        }
                        currentPage = Math.floor(rowIndex / rowsPerPage) + 1;
                        renderPage();
                    }
                };
                if (firstBtn) {
                    firstBtn.onclick = () => {
                        if (currentPage !== 1) {
                            currentPage = 1;
                            renderPage();
                        }
                    };
                }
                if (prevBtn) {
                    prevBtn.onclick = () => {
                        if (currentPage > 1) {
                            currentPage -= 1;
                            renderPage();
                        }
                    };
                }
                if (nextBtn) {
                    nextBtn.onclick = () => {
                        if (currentPage < totalPages) {
                            currentPage += 1;
                            renderPage();
                        }
                    };
                }
                if (lastBtn) {
                    lastBtn.onclick = () => {
                        if (currentPage !== totalPages) {
                            currentPage = totalPages;
                            renderPage();
                        }
                    };
                }
                renderPage();
            });
        }
        function highlightLeaveRow(targetPanel, targetLeaveId, options = {}) {
            if (!targetPanel || !targetLeaveId) {
                return;
            }
            activatePanel(targetPanel);
            const row = document.querySelector(`.leave-row[data-leave-id="${targetLeaveId}"]`);
            if (!row) {
                return;
            }
            const panel = row.closest(".leave-panel");
            if (panel && panel._paginationController) {
                panel._paginationController.showRow(row);
            }
            row.classList.add("notification-highlight");
            row.scrollIntoView({ behavior: "smooth", block: "center" });
            if (options.cleanQueryParams) {
                const params = new URLSearchParams(window.location.search);
                params.delete("panel");
                params.delete("highlight_leave");
                const cleanUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}${window.location.hash || ""}`;
                window.history.replaceState({}, "", cleanUrl);
            }
            window.setTimeout(() => {
                row.classList.remove("notification-highlight");
            }, 4200);
        }
        function highlightLeaveFromNotification() {
            let targetPanel = "";
            let targetLeaveId = "";
            try {
                const stored = window.sessionStorage.getItem("employeeNotificationHighlight");
                if (stored) {
                    const parsed = JSON.parse(stored);
                    targetPanel = parsed.panel || "";
                    targetLeaveId = String(parsed.leaveId || "");
                    window.sessionStorage.removeItem("employeeNotificationHighlight");
                }
            } catch (error) {
                // Ignore storage failures silently.
            }
            const params = new URLSearchParams(window.location.search);
            targetPanel = targetPanel || params.get("panel") || "";
            targetLeaveId = targetLeaveId || String(params.get("highlight_leave") || "");
            highlightLeaveRow(targetPanel, targetLeaveId, {
                cleanQueryParams: params.has("panel") || params.has("highlight_leave")
            });
        }
        function activatePanel(targetId) {
            tabs.forEach((tab) => {
                const active = tab.dataset.target === targetId;
                tab.classList.toggle("is-active", active);
                tab.setAttribute("aria-selected", active ? "true" : "false");
            });
            panels.forEach((panel) => {
                const active = panel.id === targetId;
                panel.classList.toggle("is-active", active);
                panel.hidden = !active;
            });
            const activePanel = panels.find((panel) => panel.id === targetId);
            if (activePanel) {
                hydrateInlineReasons(activePanel);
            }
            animateDayBlocksForPanel(targetId);
        }
        tabs.forEach((tab) => {
            tab.addEventListener("click", function () {
                activatePanel(tab.dataset.target);
            });
        });
        window.myLeaveActivatePanel = activatePanel;
        window.highlightMyLeaveRow = highlightLeaveRow;
        activatePanel("pending-panel");
        hydrateDayBlocks();
        hydrateInlineReasons();
        setupTablePagination();
        animateDayBlocksForPanel("pending-panel");
        highlightLeaveFromNotification();
    });
    function closeCalendarSelectMenus() {
        document.querySelectorAll(".calendar-custom-select.open").forEach((dropdown) => {
            dropdown.classList.remove("open");
            dropdown.classList.remove("open-up");
            const trigger = dropdown.querySelector(".calendar-select-trigger");
            if (trigger) {
                trigger.setAttribute("aria-expanded", "false");
            }
        });
    }
    function syncCalendarSelect(dropdown) {
        const nativeSelect = dropdown.querySelector("select");
        const valueElement = dropdown.querySelector(".calendar-select-value");
        const options = dropdown.querySelectorAll(".calendar-select-option");
        const selectedOption = nativeSelect?.options[nativeSelect.selectedIndex];
        if (!nativeSelect || !valueElement) {
            return;
        }
        const selectKind = dropdown.dataset.selectKind || "";
        const selectedMeta = getCalendarSelectMeta(selectKind, nativeSelect.value, selectedOption ? selectedOption.textContent.trim() : "");
        valueElement.dataset.symbol = selectedMeta.symbol || "";
        valueElement.textContent = selectedMeta.label || "";
        options.forEach((option) => {
            const isSelected = option.dataset.value === nativeSelect.value;
            option.classList.toggle("selected", isSelected);
            option.setAttribute("aria-selected", isSelected ? "true" : "false");
        });
    }
    function getCalendarSelectMeta(selectKind, value, text) {
        const cleanText = (text || "").trim();
        if (selectKind === "month") {
            const monthText = cleanText || "Select Month";
            return {
                label: monthText,
                symbol: monthText ? monthText.slice(0, 3).toUpperCase() : "MON",
            };
        }
        if (selectKind === "format") {
            const label = cleanText || "Select format";
            const formatMap = {
                csv: "CSV",
                excel: "XLS",
                pdf: "PDF",
                word: "DOC",
                json: "JSN",
                ics: "CAL",
                print: "PRT",
                "": "FMT",
            };
            return {
                label,
                symbol: formatMap[String(value || "").toLowerCase()] || label.slice(0, 3).toUpperCase(),
            };
        }
        return {
            label: cleanText,
            symbol: cleanText ? cleanText.slice(0, 3).toUpperCase() : "",
        };
    }
    function renderCalendarSelectMenu(dropdown) {
        const nativeSelect = dropdown.querySelector("select");
        const menu = dropdown.querySelector(".calendar-select-menu");
        if (!nativeSelect || !menu) {
            return;
        }
        menu.replaceChildren();
        const selectKind = dropdown.dataset.selectKind || "";
        Array.from(nativeSelect.options).forEach((option) => {
            const optionButton = document.createElement("button");
            optionButton.type = "button";
            optionButton.className = "calendar-select-option";
            optionButton.dataset.value = option.value;
            const meta = getCalendarSelectMeta(selectKind, option.value, option.textContent);
            const symbol = document.createElement("span");
            symbol.className = "calendar-select-option-symbol";
            symbol.textContent = meta.symbol;
            optionButton.appendChild(symbol);
            const title = document.createElement("span");
            title.className = "calendar-select-option-title";
            title.textContent = meta.label;
            optionButton.appendChild(title);
            optionButton.addEventListener("click", () => {
                nativeSelect.value = option.value;
                syncCalendarSelect(dropdown);
                closeCalendarSelectMenus();
                nativeSelect.dispatchEvent(new Event("change", { bubbles: true }));
            });
            menu.appendChild(optionButton);
        });
    }
    function setCalendarSelectDisabled(nativeSelect, disabled) {
        if (!nativeSelect) {
            return;
        }
        nativeSelect.disabled = disabled;
        const dropdown = nativeSelect.closest(".calendar-custom-select");
        if (!dropdown) {
            return;
        }
        const trigger = dropdown.querySelector(".calendar-select-trigger");
        dropdown.classList.toggle("is-disabled", disabled);
        if (trigger) {
            trigger.tabIndex = disabled ? -1 : 0;
            trigger.setAttribute("aria-disabled", disabled ? "true" : "false");
        }
        if (disabled) {
            dropdown.classList.remove("open");
            trigger?.setAttribute("aria-expanded", "false");
        }
    }
    function buildCalendarSelect(nativeSelect) {
        const shell = document.createElement("div");
        shell.className = "calendar-custom-select calendar-select-shell";
        shell.dataset.selectKind = nativeSelect.id === "export-format"
            ? "format"
            : "month";
        nativeSelect.classList.add("calendar-native-select");
        const trigger = document.createElement("div");
        trigger.className = "calendar-select-trigger";
        trigger.setAttribute("role", "button");
        trigger.setAttribute("tabindex", nativeSelect.disabled ? "-1" : "0");
        trigger.setAttribute("aria-haspopup", "listbox");
        trigger.setAttribute("aria-expanded", "false");
        trigger.setAttribute("aria-disabled", nativeSelect.disabled ? "true" : "false");
        const display = document.createElement("div");
        display.className = "calendar-select-display";
        const value = document.createElement("span");
        value.className = "calendar-select-value";
        const icon = document.createElement("span");
        icon.className = "calendar-select-icon";
        icon.setAttribute("aria-hidden", "true");
        trigger.appendChild(value);
        trigger.appendChild(icon);
        display.appendChild(trigger);
        const menu = document.createElement("div");
        menu.className = "calendar-select-menu";
        menu.setAttribute("role", "listbox");
        shell.appendChild(nativeSelect);
        shell.appendChild(display);
        shell.appendChild(menu);
        renderCalendarSelectMenu(shell);
        syncCalendarSelect(shell);
        shell.classList.toggle("is-disabled", nativeSelect.disabled);
        const openMenu = () => {
            if (nativeSelect.disabled) {
                return;
            }
            const isOpen = shell.classList.contains("open");
            closeCalendarSelectMenus();
            if (!isOpen) {
                const triggerRect = trigger.getBoundingClientRect();
                const estimatedMenuHeight = 196;
                const spaceBelow = window.innerHeight - triggerRect.bottom;
                const spaceAbove = triggerRect.top;
                const forceUp = shell.dataset.selectKind === "format";
                const forceDown = shell.dataset.selectKind === "month";
                shell.classList.toggle("open-up", !forceDown && (forceUp || (spaceBelow < estimatedMenuHeight && spaceAbove > spaceBelow)));
                shell.classList.add("open");
                trigger.setAttribute("aria-expanded", "true");
                requestAnimationFrame(() => {
                    const selectedOption = shell.querySelector(".calendar-select-option.selected");
                    const currentMonthOption = shell.dataset.selectKind === "month"
                        ? shell.querySelector(`.calendar-select-option[data-value="${new Date().getMonth()}"]`)
                        : null;
                    const targetOption = shell.dataset.selectKind === "month" && !/^\d+$/.test(nativeSelect.value)
                        ? (currentMonthOption || selectedOption)
                        : (selectedOption || currentMonthOption);
                    targetOption?.scrollIntoView({ block: "center" });
                });
            }
        };
        trigger.addEventListener("click", openMenu);
        trigger.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openMenu();
            }
            if (event.key === "Escape") {
                closeCalendarSelectMenus();
            }
        });
        return shell;
    }
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".calendar-custom-select")) {
            closeCalendarSelectMenus();
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeCalendarSelectMenus();
        }
    });
    function showLeaveCalendarSkeleton()
    {
        const modalContent = document.getElementById("modal-content");
        const sharedModal = document.getElementById("modal");
        const modalBox = document.querySelector(".modal-box");
        if (!modalContent || !modalBox) return;
        sharedModal?.classList.remove("popup-filter-modal-host", "popup-edit-modal-host");
        modalBox.classList.remove("popup-edit-modal-box", "popup-filter-modal-box", "reason-modal", "expanded-calendar", "compact-calendar");
        modalBox.classList.add("compact-calendar", "calendar-loading");
        window.setSafeHTML(modalContent, `
            <div class="calendar-skeleton" role="status" aria-live="polite" aria-label="Loading leave calendar">
                <div class="calendar-skeleton-title">
                    <span class="calendar-skeleton-icon"></span>
                    <span class="calendar-skeleton-copy">
                        <span class="calendar-skeleton-line calendar-skeleton-line-title"></span>
                        <span class="calendar-skeleton-line calendar-skeleton-line-subtitle"></span>
                    </span>
                </div>
                <div class="calendar-skeleton-legend">
                    <span></span><span></span><span></span><span></span><span></span>
                </div>
                <div class="calendar-skeleton-nav">
                    <span></span><span></span><span></span>
                </div>
                <div class="calendar-skeleton-grid">
                    ${Array.from({ length: 42 }, () => "<span></span>").join("")}
                </div>
                <div class="calendar-skeleton-actions">
                    <span></span><span></span>
                </div>
            </div>
        `);
        openModal();
    }
    function openLeaveCalendar() 
    {
        showLeaveCalendarSkeleton();
        fetch(myLeaveCalendarDataUrl)
            .then(res => typeof window.parseJsonOrSessionExpired === "function" ? window.parseJsonOrSessionExpired(res) : res.json())
            .then(data => 
            {
                if (data.sessionExpired)
                {
                    showAjaxMessages(data.messages);
                    if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(data);
                    return;
                }
                // Load all data (leaves, holidays, company closures) from response
                const leaves = data.leaves;
                const holidays = data.holidays;
                const companyHolidays = data.company_holidays || [];
                /* ========================================= CLEAR PREVIOUS CONTENT ========================================= */
                const modalContent = document.getElementById("modal-content");
                const sharedModal = document.getElementById("modal");
                const modalBox = document.querySelector(".modal-box");
                modalContent.replaceChildren();
                sharedModal?.classList.remove("popup-filter-modal-host", "popup-edit-modal-host");
                if (modalBox) {
                    modalBox.classList.remove("popup-edit-modal-box", "popup-filter-modal-box", "reason-modal", "expanded-calendar", "compact-calendar", "calendar-loading");
                }
                /* ========================================= TITLE ================================================= */
                const title = document.createElement("h3");
                title.textContent = "My Leave Calendar";
                title.classList.add("calendar-title");
                title.dataset.compactSubtitle = "Track and manage your leaves with ease";
                title.dataset.expandedSubtitle = "Visualize and manage your leaves across months";
                /* ========================================= LEGEND ================================================= */
                const formatLegendCount = (value) => String(value || 0).padStart(2, "0");
                const countLeavesByStatus = (status) => {
                    const normalizedStatus = String(status || "").toLowerCase();
                    const uniqueLeaves = new Set();
                    leaves.forEach((leave, index) => {
                        if (String(leave.status || "").toLowerCase() !== normalizedStatus) return;
                        uniqueLeaves.add(leave.id || `${leave.from}|${leave.to}|${leave.type}|${leave.status}|${index}`);
                    });
                    return uniqueLeaves.size;
                };
                const countUniqueHolidayDates = (items) => new Set(
                    (items || [])
                        .map((item) => item.date)
                        .filter(Boolean)
                ).size;
                const legendCounts = {
                    pending: countLeavesByStatus("Pending"),
                    approved: countLeavesByStatus("Approved"),
                    rejected: countLeavesByStatus("Rejected"),
                    public: countUniqueHolidayDates(holidays),
                    company: countUniqueHolidayDates(companyHolidays)
                };
                const legend = document.createElement("div");
                legend.className = "calendar-legend";
                window.setSafeHTML(legend, `
                    <span class="legend-item pending" data-count="${formatLegendCount(legendCounts.pending)}">Pending</span>
                    <span class="legend-item approved" data-count="${formatLegendCount(legendCounts.approved)}">Approved</span>
                    <span class="legend-item rejected" data-count="${formatLegendCount(legendCounts.rejected)}">Rejected</span>
                    <span class="legend-item public" data-count="${formatLegendCount(legendCounts.public)}"><span class="legend-label-compact">Holiday</span><span class="legend-label-expanded">National Holiday</span></span>
                    <span class="legend-item company" data-count="${formatLegendCount(legendCounts.company)}">Company Closed</span>
                `);
                /* ====================================== Export Calendar ======================================== */
                const info = {
                    companyName: "MS Technology",
                    watermark: "CONFIDENTIAL",
                    logoBase64: null,
                    userDisplayName: document.getElementById("export-user").dataset.username
                };

const exportWrapper = document.createElement("div");
                exportWrapper.className = "export-wrapper";
                window.setSafeHTML(exportWrapper, `
                    <select id="export-format">
                        <option value="">Select Format</option>
                        <option value="csv">CSV</option>
                        <option value="excel">Excel (.xlsx)</option>
                        <option value="pdf">PDF</option>
                        <option value="word">Word (.docx)</option>
                        <option value="json">JSON</option>
                        <option value="ics">iCal (.ics)</option>
                        <option value="print">Print</option>
                    </select>
                    <select id="export-month">
                        <option value="">Select Month</option>
                        <option value="All">Whole Year</option>
                        ${Array.from({length:12}).map((_,i)=>`
                            <option value="${i}"> ${new Date(0,i).toLocaleString("default",{month:"long"})} </option>
                        `).join("")}
                    </select>
                    <button id="export-btn" class="export-btn" disabled>Export Calendar</button>
                    <span id="export-spinner" class="spinner hidden"></span>
                `);
                const exportFormat = exportWrapper.querySelector("#export-format");
                const exportMonth  = exportWrapper.querySelector("#export-month");
                const exportBtn    = exportWrapper.querySelector("#export-btn");
                const spinner      = exportWrapper.querySelector("#export-spinner");
                const exportFormatShell = buildCalendarSelect(exportFormat);
                const exportMonthShell = buildCalendarSelect(exportMonth);
                exportWrapper.insertBefore(exportFormatShell, exportBtn);
                exportWrapper.insertBefore(exportMonthShell, exportBtn);
                function toggleExportBtn() 
                {
                    exportBtn.disabled = !(exportFormat.value && exportMonth.value);
                }
                exportFormat.onchange = toggleExportBtn;
                exportMonth.onchange  = toggleExportBtn;
                // When export button is clicked, show spinner, filter leaves based on selected month, and 
                // call export function with filtered data and selected format. Hide spinner after export is done.
                exportBtn.onclick = () => 
                {
                    spinner.classList.remove("hidden");
                    const selectedFormat = exportFormat.value;
                    const selectedMonth  = exportMonth.value;
                    const filteredLeaves = filterLeavesByMonth(leaves, selectedMonth);
                    setTimeout(() => 
                    {
                        exportCalendar(filteredLeaves, selectedFormat, selectedMonth, info);
                        spinner.classList.add("hidden");
                    }, 300);
                };
                /* ========================================= MONTH JUMP ======================================== */
                // This dropdown is for quick navigation within the calendar modal. 
                // It does not affect export month selection, which is separate and allows "Whole Year" option.
                const monthSelect = document.createElement("select");
                monthSelect.className = "month-jump";
                const year = new Date().getFullYear();
                
                for (let m = 0; m < 12; m++) 
                {
                    const option = document.createElement("option");
                    option.value = m;
                    option.textContent = new Date(year, m).toLocaleString("default", { month: "long" });
                    monthSelect.appendChild(option);
                }
                // Declare expanded variable to track whether we are in compact mode (showing only selected month) or expanded mode (showing all months).
                let expanded = false;
                const currentMonthIndex = new Date().getMonth();
                monthSelect.value = currentMonthIndex;
                const monthSelectShell = buildCalendarSelect(monthSelect);
                const monthNav = document.createElement("div");
                monthNav.className = "calendar-month-nav";
                const prevMonthBtn = document.createElement("button");
                prevMonthBtn.type = "button";
                prevMonthBtn.className = "calendar-month-step calendar-month-prev";
                prevMonthBtn.setAttribute("aria-label", "Previous month");
                prevMonthBtn.innerHTML = "&#8249;";
                const nextMonthBtn = document.createElement("button");
                nextMonthBtn.type = "button";
                nextMonthBtn.className = "calendar-month-step calendar-month-next";
                nextMonthBtn.setAttribute("aria-label", "Next month");
                nextMonthBtn.innerHTML = "&#8250;";
                monthNav.appendChild(prevMonthBtn);
                monthNav.appendChild(monthSelectShell);
                monthNav.appendChild(nextMonthBtn);
                // Auto select current month in export (compact default)
                // This is a bit tricky because monthSelect and exportMonth are different dropdowns, but we want them to be in sync for better UX.
                exportMonth.value = currentMonthIndex;
                // Compact mode default behaviour is to auto-select current month in export dropdown, because it makes sense that 
                //if user is looking at current month in calendar, they are likely interested in exporting that month.
                setCalendarSelectDisabled(exportMonth, true);  // disable export month dropdown when month is selected in compact calendar view as first time calendar will open in compact view
                syncCalendarSelect(exportMonthShell);
                toggleExportBtn();
                // When month is selected from dropdown, if in compact mode, show that month and hide others. 
                // If in expanded mode, scroll to that month.
                monthSelect.onchange = () => 
                {
                    const selectedMonth = parseInt(monthSelect.value);
                    if (!expanded) 
                    {
                        // ?? Compact mode ? switch visible month
                        Array.from(yearContainer.children).forEach((monthDiv, index) => 
                        {
                            if (index === selectedMonth) 
                            {
                                monthDiv.style.display = "block";
                                // smooth fade switch
                                monthDiv.style.opacity = "0";
                                monthDiv.style.transform = "translateY(8px)";
                                requestAnimationFrame(() => 
                                {
                                    monthDiv.style.transition = "opacity 0.3s ease, transform 0.3s ease";
                                    monthDiv.style.opacity = "1";
                                    monthDiv.style.transform = "translateY(0)";
                                });
                            } 
                            else 
                            {
                                monthDiv.style.display = "none";
                            }
                        });
                        
                        // Auto select current month in export (compact default)
                        exportMonth.value = selectedMonth;
                        setCalendarSelectDisabled(exportMonth, true);  // disable export month dropdown when month is selected in calendar view
                        syncCalendarSelect(exportMonthShell);
                        toggleExportBtn();
                    } 
                    else 
                    {
                        // ?? Expanded mode ? scroll to month
                        const target = document.getElementById(`month-${selectedMonth}`);
                        
                        if (target) 
                        {
                            const containerRect = yearContainer.getBoundingClientRect();
                            const targetRect = target.getBoundingClientRect();
                            const scrollPosition = yearContainer.scrollTop + (targetRect.top - containerRect.top);
                            yearContainer.scrollTo({ top: scrollPosition, behavior: "smooth" });
                        }
                    }
                };
                function stepCalendarMonth(direction)
                {
                    const current = parseInt(monthSelect.value || currentMonthIndex, 10);
                    monthSelect.value = (current + direction + 12) % 12;
                    monthSelect.dispatchEvent(new Event("change", { bubbles: true }));
                    syncCalendarSelect(monthSelectShell);
                }
                prevMonthBtn.onclick = () => stepCalendarMonth(-1);
                nextMonthBtn.onclick = () => stepCalendarMonth(1);
                
                /* ====================================== YEAR CONTAINER ====================================== */
                const yearContainer = document.createElement("div");
                yearContainer.className = "year-calendar";
                for (let month = 0; month < 12; month++) 
                {
                    yearContainer.appendChild( buildMonthCalendar(year, month, leaves, holidays, companyHolidays) );
                }
                // By default, show only current month and hide others to reduce overwhelm and draw attention to current month. 
                // User can then choose to expand full year if desired.
                Array.from(yearContainer.children).forEach((monthDiv, index) => 
                {
                    if (index !== currentMonthIndex) 
                    {
                        monthDiv.style.display = "none";
                    }
                });
                /* ====================================== IN-MODAL OVERLAY (HIDDEN) ====================================== */
                const detailOverlay = document.createElement("div");
                detailOverlay.id = "calendar-detail-overlay";
                detailOverlay.style.display = "none";
                window.setSafeHTML(detailOverlay, `
                    <div class="detail-box">
                        <span class="close" role="button" tabindex="0" aria-label="Close modal" data-action="close-calendar-detail">&times;</span>
                        <div id="calendar-detail-content"></div>
                    </div>
                `);
                // When overlay is clicked, if click target is the overlay itself (not the detail box inside), close the overlay. 
                // This allows users to click outside the detail box to close it, while still allowing interaction 
                // with the detail box content without accidentally closing it.
                detailOverlay.addEventListener("click", (e) => 
                {
                    // If click is directly on the overlay (not inside the box)
                    if (e.target.id === "calendar-detail-overlay") 
                    {
                        closeCalendarDetail();
                    }
                });
                /* =========================================== APPEND ALL ===================================== */
                modalContent.appendChild(title);
                modalContent.appendChild(legend);
                modalContent.appendChild(monthNav);
                modalContent.appendChild(yearContainer);
                modalContent.appendChild(detailOverlay);
                modalContent.appendChild(exportWrapper);
                
                // Make modal wider for calendar view only ( in your existing modal, just add a class to trigger wider styles)
                modalBox.classList.add("compact-calendar");
                // ===== Inject Calendar Toggle Button (Only For Calendar) =====
                // ===== ADD CALENDAR TOGGLE BUTTON (ONLY FOR CALENDAR) =====
                // Remove existing toggle if somehow still present
                const oldToggle = document.getElementById("calendar-toggle-icon");
                if (oldToggle) oldToggle.remove();
                const toggleIcon = document.createElement("button");
                toggleIcon.id = "calendar-toggle-icon";
                toggleIcon.className = "calendar-toggle-icon";
                toggleIcon.type = "button";
                window.setSafeHTML(toggleIcon, `
                    <span class="expand-icon">&#9638;</span>
                    <span class="collapse-icon">&minus;</span>
                `);
                toggleIcon.title = "Expand Full Year";
                // Find the existing close button
                const closeBtn = document.querySelector(".modal-header .close");
                if (closeBtn && !document.getElementById("calendar-toggle-icon")) 
                {
                    closeBtn.parentNode.insertBefore(toggleIcon, closeBtn);
                }
                // When toggle button is clicked, if currently in compact mode (showing only current month), 
                // expand to show all months and change button to "Show Only Current Month". 
                // If currently in expanded mode (showing all months), collapse to show only current month and 
                // change button back to "Expand Full Year".
                toggleIcon.onclick = () => 
                {
                    closeCalendarSelectMenus();
                    expanded = !expanded;
                    const currentMonthIndexcollapse = new Date().getMonth();
                    // When expanding, we want to show all months with a smooth fade-in. When collapsing, 
                    // we want to hide non-current months with a smooth fade-out, while keeping current month visible.
                    Array.from(yearContainer.children).forEach((monthDiv, index) =>
                    {
                        if (expanded)
                        {
                            monthDiv.classList.add("month-hidden");  // start hidden
                            monthDiv.style.display = "block";       // make visible in layout
                            requestAnimationFrame(() => 
                            {
                                monthDiv.classList.remove("month-hidden");
                            });
                            // Auto select current month in export (compact default) - when we expand to show all months, 
                            // we want to reset export month selection to "Select Month" to encourage user to choose a month if they want to export, since now they can see all months.
                            setCalendarSelectDisabled(exportMonth, false);
                            syncCalendarSelect(exportMonthShell);
                        }
                        else
                        {
                            if (index === parseInt(monthSelect.value))
                            {
                                monthDiv.style.display = "block";
                                monthDiv.classList.remove("month-hidden");
                            }
                            else
                            {
                                monthDiv.classList.add("month-hidden");
                                setTimeout(() => 
                                {
                                    monthDiv.style.display = "none";
                                }, 300);
                            }
                        }
                    });
                    if (expanded) 
                    {
                        modalBox.classList.remove("compact-calendar", "expanded-calendar");
                        modalBox.classList.add("expanded-calendar");
                        toggleIcon.classList.remove("compact");
                        toggleIcon.classList.add("expanded");
                        // After expanding, auto-scroll to the month selected in the dropdown for better UX.
                        // This is needed because when we expand, all months become visible and 
                        // we want to scroll to the month that user is interested in (selected in dropdown), 
                        // rather than leaving them at the top of the calendar.
                        setTimeout(() => 
                        {
                            const selectedMonthIndex = parseInt(monthSelect.value);
                            const target = document.getElementById(`month-${selectedMonthIndex}`);
                            if (!target) return;
                            const containerRect = yearContainer.getBoundingClientRect();
                            const targetRect = target.getBoundingClientRect();
                            // Increased offset to 25px to ensure no month titles (especially right-most ones) are cut off
                            const scrollPosition = yearContainer.scrollTop + (targetRect.top - containerRect.top) - 25;
                            yearContainer.scrollTo({ top: scrollPosition, behavior: "smooth" });
                        }, 350);
                        // When switching to expanded ? reset export month
                        exportMonth.value = "All";   // shows "Select month"
                        // OR use this if you prefer auto whole year:
                        // exportMonth.value = "All";
                        toggleExportBtn();
                    } 
                    
                    else 
                    {
                        modalBox.classList.remove("expanded-calendar", "compact-calendar");
                        modalBox.classList.add("compact-calendar");
                        toggleIcon.classList.remove("expanded");
                        toggleIcon.classList.add("compact");
                        // ?? Restore export month
                        const selectedMonthIndex = parseInt(monthSelect.value);
                        exportMonth.value = selectedMonthIndex;
                        setCalendarSelectDisabled(exportMonth, true); // Enable export month dropdown in compact mode since month is determined by calendar view
                        syncCalendarSelect(exportMonthShell);
                        toggleExportBtn();
                    }
                    toggleIcon.title = expanded ? "Collapse to Current Month" : "Expand Full Year";
                };
                
                // ?? Subtle fade-in for current month
                // When the calendar modal is opened, the current month will fade in subtly to draw attention, while other months remain hidden. 
                // This provides a smoother and more engaging visual experience right from the start.
                // The expand/collapse toggle can then be used to view other months with smooth transitions.
                const currentMonthDiv = yearContainer.children[currentMonthIndex];
                // ?? Premium fade + blur + soft scale
                currentMonthDiv.classList.add("month-enter");
                currentMonthDiv.classList.add("month-shadow-enter");
                requestAnimationFrame(() => 
                {
                    currentMonthDiv.classList.add("month-enter-active");
                    currentMonthDiv.classList.add("month-shadow-active");
                });
                openModal();
            })
            .catch(() =>
            {
                const modalContent = document.getElementById("modal-content");
                const modalBox = document.querySelector(".modal-box");
                modalBox?.classList.remove("calendar-loading");
                if (modalContent) {
                    window.setSafeHTML(modalContent, `
                        <div class="calendar-load-error">
                            <strong>Calendar could not load</strong>
                            <span>Please try opening it again.</span>
                        </div>
                    `);
                }
            });
    }
    function buildMonthCalendar(year, month, leaves, holidays, companyHolidays)
    {
        const getLeaveSortTime = (leave) => {
            const rawValue = leave?.created_at || leave?.updated_at || leave?.approved_at || leave?.rejected_at || "";
            const timeValue = rawValue ? Date.parse(rawValue) : NaN;
            return Number.isFinite(timeValue) ? timeValue : Number(leave?.id || 0);
        };
        const getLatestLeaveForDate = (dateStr) => {
            return leaves
                .filter((leave) => dateStr >= leave.from && dateStr <= leave.to)
                .sort((a, b) => {
                    const timeDiff = getLeaveSortTime(b) - getLeaveSortTime(a);
                    if (timeDiff) return timeDiff;
                    return Number(b.id || 0) - Number(a.id || 0);
                })[0] || null;
        };
        const monthContainer = document.createElement("div");
        monthContainer.id = `month-${month}`;
        monthContainer.className = `month-container month-theme-${month}`;
        const monthName = new Date(year, month).toLocaleString("default", { month: "long" });
        const header = document.createElement("h4");
        header.textContent = monthName + " " + year;
        header.className = "month-title";
        const grid = document.createElement("div");
        grid.className = "calendar-grid";
        const days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
        days.forEach(d => 
        {
            const h = document.createElement("div");
            h.className = "calendar-header";
            if (d === "Sat" || d === "Sun") {
                h.classList.add("weekend-header");
            }
            h.textContent = d;
            grid.appendChild(h);
        });
        const divider = document.createElement("div");
        divider.className = "calendar-row-divider";
        grid.appendChild(divider);
        const firstDay = (new Date(year, month, 1).getDay() + 6) % 7;
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        for (let i = 0; i < firstDay; i++) 
        {
            const emptyCell = document.createElement("div");
            emptyCell.className = "calendar-cell empty";
            emptyCell.setAttribute("aria-hidden", "true");
            grid.appendChild(emptyCell);
        }
        for (let day = 1; day <= daysInMonth; day++) 
        {
            const cell = document.createElement("div");
            cell.className = "calendar-cell";
            cell.textContent = day;
            const dayOfWeek = new Date(year, month, day).getDay();
            if (dayOfWeek === 0 || dayOfWeek === 6) {
                cell.classList.add("weekend-cell");
            }
            const dateStr = `${year}-${String(month+1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
            // Highlight today's date with a special class for distinct styling. 
            // This makes it easy for users to quickly identify the current day in the calendar.
            const today = new Date();
            const todayStr = today.getFullYear() + "-" + String(today.getMonth()+1).padStart(2,"0") + "-" + String(today.getDate()).padStart(2,"0");
            if (dateStr === todayStr) 
            {
                cell.classList.add("today-highlight");
            }
            const holiday = holidays.find(h => h.date === dateStr);
            const companyDay = companyHolidays.find(h => h.date === dateStr);
            const leave = getLatestLeaveForDate(dateStr);
            const tooltipParts = [];
            /* ===============================
            4?? TOOLTIP PREVIEW (HOVER)
            =============================== */
            if (leave) 
            {
                tooltipParts.push(`Leave Type: ${leave.type}`);
                tooltipParts.push(`Date: ${leave.from} -> ${leave.to}`);
                tooltipParts.push(`Status: ${leave.status}`);
            }
            if (companyDay) 
            {
                const companyDot = document.createElement("span");
                companyDot.className = "holiday-dot company-dot";
                cell.appendChild(companyDot);
                tooltipParts.push(`${companyDay.is_optional ? "Optional" : "Company"} Holiday: ${companyDay.name}`);
            }
            // 1?? Company closure (highest priority)

// 2?? Public holiday
            if (holiday) 
            {
                const publicDot = document.createElement("span");
                publicDot.className = "holiday-dot public-dot";
                cell.appendChild(publicDot);
                tooltipParts.push(`Public Holiday: ${holiday.name}`);
            }
            if (tooltipParts.length)
            {
                cell.title = tooltipParts.join("\n");
            }
            /* ===============================
            EXISTING LEAVE MARKING
            =============================== */
            if (leave) 
            {
                const type = document.createElement("small");
                type.textContent = leave.type;
                type.title = leave.type;
                cell.appendChild(type);
                
                //DETECT POSITION OF DAY IN A LEAVE RANGE
                const isStart = dateStr === leave.from;
                const isEnd   = dateStr === leave.to;
                cell.classList.add("leave", leave.status.toLowerCase());
                cell.dataset.leaveId = leave.id;
                if (isStart) cell.classList.add("leave-start");
                else if (isEnd) cell.classList.add("leave-end");
                else cell.classList.add("leave-middle");
                cell.style.cursor = "pointer";
                cell.onclick = () => openCalendarDetail(leave);
            }
            grid.appendChild(cell);
        }
        const totalCellsRequired = Math.ceil((firstDay + daysInMonth) / 7) * 7;
        for (let i = firstDay + daysInMonth; i < totalCellsRequired; i++) {
            const emptyCell = document.createElement("div");
            emptyCell.className = "calendar-cell empty";
            emptyCell.setAttribute("aria-hidden", "true");
            grid.appendChild(emptyCell);
        }
        monthContainer.appendChild(header);
        monthContainer.appendChild(grid);
        return monthContainer;
    }
    /* Export Calendar Start */
    function filterLeavesByMonth(leaves, month) 
    {
        if (month === "All") return leaves;
        return leaves.filter(l => 
        {
            const startMonth = new Date(l.from).getMonth();
            const endMonth   = new Date(l.to).getMonth();
            return startMonth <= month && month <= endMonth;
        });
    }
    function exportCalendar(leaves, format, month, info) 
    {
        if (!leaves.length) 
        {
            if (typeof window.showThemeAlert === "function")
            {
                window.showThemeAlert("No leaves to export", {
                    title: "Export calendar",
                    variant: "export",
                    confirmText: "OK"
                });
            }
            else
            {
                alert("No leaves to export");
            }
            return;
        }
        switch (format) 
        {
            case "csv":   exportCSV(leaves, info); break;
            case "excel": exportExcel(leaves, info ); break;
            case "pdf":   exportPDF(leaves, info); break;
            case "word":  exportWord(leaves, info); break;
            case "json":  exportJSON(leaves); break;
            case "ics":   exportICS(leaves); break;
            case "print": printCalendar(leaves, info); break;
        }
    }
    function exportCSV(leaves, info) 
    {
        let csv = "Type,From,To,Status,Reviewed By,Reason\n";
        leaves.forEach(l => 
        {
            csv += `"${l.type}","${l.from}","${l.to}","${l.status}","${(l.reviewed_by||"").replace(/"/g,'""')}","${(l.reason||"").replace(/"/g,'""')}"\n`;
        });
        downloadFile(csv, "my_leave_calendar.csv", "text/csv");
    }
    function exportExcel(leaves, info) 
    {
        const data = leaves.map(l => (
        {
            Type: l.type,
            From: l.from, To: l.to,
            Status: l.status,
            "Reviewed By": l.reviewed_by || "",
            Reason: l.reason || ""
        }));
        const ws = XLSX.utils.json_to_sheet(data);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "Leaves");
        XLSX.writeFile(wb, "my_leave_calendar.xlsx");
    }
    function exportPDF(leaves, info) 
    {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        doc.setFontSize(14);
        doc.text("Your Company Name", 14, 10);
        doc.setFontSize(16);
        doc.text("My Leave Calendar", 14, 15);
        doc.setFontSize(10);
        doc.text("User: " + info.userDisplayName, 14, 16);
        doc.setTextColor(200);
        doc.text("CONFIDENTIAL", 60, 150, { angle: 45 });
        doc.setTextColor(0);
        doc.autoTable({
            head: [["Type","From","To","Status","Reviewed By","Reason"]],
            body: leaves.map(l => [ l.type, l.from, l.to, l.status, l.reviewed_by || "", l.reason || "" ]),
            startY: 25
        });
        doc.save("leave_calendar.pdf");
    }
    
    function exportWord(leaves, info) 
    {
        const 
        {
            Document, Packer, Paragraph, TextRun,
            Table, TableRow, TableCell
        } = window.docx;
        const header = new Paragraph(
        {
            children: [
                new TextRun({ text: "Your Company Name", bold: true, size: 28 }),
                new TextRun({ text: "\nUser: " + info.userDisplayName, size: 20 })
            ]
        });
        const rows = [
            new TableRow(
            {
                children: ["Type","From","To","Status","Reviewed By","Reason"].map(h =>
                    new TableCell(
                    {
                        children: [new Paragraph({ children:[new TextRun({text:h,bold:true})] })]
                    })
                )
            }),
            ...leaves.map(l =>
                new TableRow(
                {
                    children: [l.type,l.from,l.to,l.status,l.reviewed_by||"",l.reason||""].map(v => new TableCell({ children:[new Paragraph(v)] }))
                })
            )
        ];
        const doc = new Document(
        {
            sections: [{ children: [header, new Paragraph(""), new Table({ rows })] }]
        });
        Packer.toBlob(doc).then(blob => 
        {
            downloadBlob(blob, "leave_calendar.docx");
        });
    }
    function exportJSON(leaves) 
    {
        downloadFile(
            JSON.stringify(leaves, null, 2),
            "my_leave_calendar.json",
            "application/json"
        );
    }
    function exportICS(leaves) 
    {
        let ics = "BEGIN:VCALENDAR\nVERSION:2.0\nCALSCALE:GREGORIAN\n";
        leaves.forEach(l => 
        {
            ics += `BEGIN:VEVENT
            SUMMARY:${l.type} Leave (${l.status})
            DTSTART:${l.from.replace(/-/g,"")}
            DTEND:${l.to.replace(/-/g,"")}
            DESCRIPTION:${l.reason || ""}${l.reviewed_by ? ` | Reviewed By: ${l.reviewed_by}` : ""}
            END:VEVENT\n`;
        });
        ics += "END:VCALENDAR";
        downloadFile(ics, "my_leave_calendar.ics", "text/calendar");
    }
    function printCalendar(leaves, info) 
    {
        const printWindow = window.open("", "_blank");

        if (!printWindow)
        {
            return;
        }

        const printDocument = printWindow.document;
        printDocument.title = "My Leave Calendar";
        printDocument.body.replaceChildren();

        const heading = printDocument.createElement("h2");
        heading.textContent = info.companyName || "";

        const userLine = printDocument.createElement("p");
        userLine.textContent = "User: " + (info.userDisplayName || "");

        const table = printDocument.createElement("table");
        table.setAttribute("border", "1");
        table.setAttribute("cellspacing", "0");
        table.setAttribute("cellpadding", "6");

        const headerRow = printDocument.createElement("tr");
        ["Type", "From", "To", "Status", "Reviewed By", "Reason"].forEach(function (label)
        {
            const headerCell = printDocument.createElement("th");
            headerCell.textContent = label;
            headerRow.appendChild(headerCell);
        });
        table.appendChild(headerRow);

        leaves.forEach(function (leave)
        {
            const row = printDocument.createElement("tr");

            [leave.type, leave.from, leave.to, leave.status, leave.reviewed_by || "", leave.reason || ""].forEach(function (value)
            {
                const cell = printDocument.createElement("td");
                cell.textContent = value || "";
                row.appendChild(cell);
            });

            table.appendChild(row);
        });

        printDocument.body.append(heading, userLine, table);
        printWindow.print();
    }
    function downloadFile(content, filename, type) 
    {
        const blob = new Blob([content], { type });
        downloadBlob(blob, filename);
    }
    function downloadBlob(blob, filename)
    {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    function getCalendarLeaveTypeClass(leaveType)
    {
        const normalized = String(leaveType || "").toLowerCase();
        return ["sick", "unpaid", "earned", "short", "half"].includes(normalized) ? normalized : "default";
    }
    function formatCalendarDetailDate(dateValue)
    {
        if (!dateValue) return "-";
        const parsed = new Date(`${dateValue}T00:00:00`);
        if (Number.isNaN(parsed.getTime())) return dateValue;
        return parsed.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" });
    }
    function formatCalendarDetailTimeRange(leave)
    {
        if (leave?.from_datetime && leave?.to_datetime)
        {
            const start = new Date(leave.from_datetime);
            const end = new Date(leave.to_datetime);
            if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()))
            {
                return `${start.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true })} - ${end.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true })}`;
            }
        }
        return "Full day";
    }
    function restoreEditLeaveTemplateHome()
    {
        const formHome = document.getElementById("form-home");
        const template = document.getElementById("edit-leave-template");
        if (formHome && template && template.parentElement !== formHome)
        {
            template.classList.remove("calendar-inline-edit-template");
            formHome.appendChild(template);
        }
    }
    function openCalendarDetail(leave)
    {
        restoreEditLeaveTemplateHome();
        const overlay = document.getElementById("calendar-detail-overlay");
        const content = document.getElementById("calendar-detail-content");
        overlay?.querySelector(".detail-box")?.classList.remove("is-calendar-editing");
        const safeLeaveId = encodeURIComponent(String(leave.id ?? ""));
        const safeLeaveType = escapeHtml(leave.type);
        const safeLeaveReason = escapeHtml(leave.reason || "-");
        const safeLeaveStatus = escapeHtml(leave.status);
        const typeClass = getCalendarLeaveTypeClass(leave.type);
        const hasPendingActions = leave.status === "Pending";
        const appliedText = formatAjaxRelativeLeaveAge(leave.created_at);
        const updatedText = leave.updated_at ? formatAjaxRelativeLeaveAge(leave.updated_at) : "Not updated";
        window.setSafeHTML(content, `
            <section class="calendar-detail-card calendar-detail-${typeClass} ${hasPendingActions ? "has-detail-actions" : "has-no-detail-actions"}">
                <div class="calendar-detail-head">
                    <span class="calendar-detail-symbol" aria-hidden="true"></span>
                    <div>
                        <p>Leave detail</p>
                        <h4><span class="calendar-detail-type-chip">${safeLeaveType} Leave</span></h4>
                    </div>
                    <span class="calendar-detail-status calendar-detail-status-${safeLeaveStatus.toLowerCase()}">${safeLeaveStatus}</span>
                </div>
                <div class="calendar-detail-grid">
                    <div class="calendar-detail-metric">
                        <span>Schedule</span>
                        <strong>${escapeHtml(formatCalendarDetailDate(leave.from))} - ${escapeHtml(formatCalendarDetailDate(leave.to))}</strong>
                        <small>${escapeHtml(formatCalendarDetailTimeRange(leave))}</small>
                    </div>
                    <div class="calendar-detail-metric">
                        <span>Applied</span>
                        <strong>${escapeHtml(appliedText)}</strong>
                        <small>${escapeHtml(leave.created_at ? new Date(leave.created_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true }) : "-")}</small>
                    </div>
                    <div class="calendar-detail-metric">
                        <span>Updated</span>
                        <strong>${escapeHtml(updatedText)}</strong>
                        <small>${escapeHtml(leave.updated_at ? new Date(leave.updated_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true }) : "-")}</small>
                    </div>
                </div>
                <div class="calendar-detail-reason">
                    <span>Reason</span>
                    <p>${safeLeaveReason}</p>
                </div>
            </section>
            
            ${hasPendingActions ? `
                <div class="detail-actions">
                    
                    <button class="edit-btn" type="button" data-calendar-edit-leave> &#9998; Edit </button>
                    
                    <form method="post" action="/delete-leave/${safeLeaveId}/"
                        data-confirm-submit="Delete this leave?">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                        <button type="submit" class="delete-btn">&#128465; Delete</button>
                    </form>
                </div>
            ` : ""}
        `);
        const editButton = content.querySelector("[data-calendar-edit-leave]");
        if (editButton)
        {
            editButton.addEventListener("click", () => openInlineEdit(leave));
        }
        overlay.style.display = "flex";
        requestAnimationFrame(() => overlay.classList.add("show"));
    }
    function closeCalendarDetail()
    {
        restoreEditLeaveTemplateHome();
        const overlay = document.getElementById("calendar-detail-overlay");
        if (!overlay) return;
        overlay.querySelector(".detail-box")?.classList.remove("is-calendar-editing");
        overlay.classList.remove("show");
        setTimeout(() => overlay.style.display = "none", 300);
    }
    
    function openInlineEdit(leave)
    {
        const content = document.getElementById("calendar-detail-content");
        if (!content) return;
        document.querySelector("#calendar-detail-overlay .detail-box")?.classList.add("is-calendar-editing");
        const fakeButton = document.createElement("button");
        fakeButton.dataset.id = String(leave.id ?? "");
        fakeButton.dataset.type = String(leave.type ?? "");
        fakeButton.dataset.from = String(leave.from ?? "");
        fakeButton.dataset.to = String(leave.to ?? "");
        fakeButton.dataset.reason = String(leave.reason || "");
        fakeButton.dataset.fromdatetime = String(leave.from_datetime || "");
        fakeButton.dataset.todatetime = String(leave.to_datetime || "");
        openEditLeave(fakeButton, {
            inlineHost: content,
            calendarInline: true,
            afterSuccessfulEdit: () => closeCalendarDetail()
        });
    }
    function getCSRFToken() 
    {
        return document.getElementById("csrf-token").value;
    }
    const csrfToken = document.getElementById("csrf-token").value;
    let currentFilterState = {};
    function loadCurrentFilterState()
    {
        const node = document.getElementById("my-leave-filters-json");
        if (!node) return {};
        try
        {
            return JSON.parse(node.value || "{}");
        }
        catch (error)
        {
            return {};
        }
    }
    currentFilterState = loadCurrentFilterState();
    function escapeHtml(value)
    {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }
    function formatAjaxRelativeLeaveAge(isoValue)
    {
        if (!isoValue)
        {
            return "-";
        }
        const target = new Date(isoValue);
        if (Number.isNaN(target.getTime()))
        {
            return "-";
        }
        const now = new Date();
        const diffMs = Math.max(0, now.getTime() - target.getTime());
        const diffMinutes = Math.floor(diffMs / (60 * 1000));
        const diffHours = Math.floor(diffMs / (60 * 60 * 1000));
        const minuteRemainder = String(diffMinutes % 60).padStart(2, "0");
        const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const startOfTarget = new Date(target.getFullYear(), target.getMonth(), target.getDate());
        const msPerDay = 24 * 60 * 60 * 1000;
        const diffDays = Math.max(0, Math.floor((startOfToday - startOfTarget) / msPerDay));
        if (diffMinutes <= 0) return "just now";
        if (diffMinutes === 1) return "1 min ago";
        if (diffMinutes <= 59) return `${diffMinutes} min ago`;
        if (diffHours === 1) return `1 hour, ${minuteRemainder} min ago`;
        if (diffHours <= 23) return `${diffHours} hour, ${minuteRemainder} min ago`;
        if (diffDays <= 6) return `${diffDays} ${diffDays === 1 ? "day" : "days"} ago`;
        return target.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" });
    }
    function getLeaveTypeSymbol(leaveType)
    {
        const symbolMap = {
            Sick: "+",
            Unpaid: "\u263C",
            Earned: "\u2605",
            Short: "\u25D4",
            Half: "\u25D0",
        };
        return symbolMap[leaveType] || "\u2726";
    }
    function getLeaveCode(leaveType)
    {
        if (leaveType === "Short") return "S";
        if (leaveType === "Half") return "H";
        return (leaveType || "").slice(0, 1).toUpperCase();
    }
    const myLeavePopupFilterTypes = [
        { value: "Short", label: "Short (2 Hours)", symbol: "\u23F1" },
        { value: "Half", label: "Half (4 Hours)", symbol: "\u25D0" },
        { value: "Sick", label: "Sick", symbol: "\u271A" },
        { value: "Earned", label: "Earned", symbol: "\u2726" },
        { value: "Unpaid", label: "Unpaid", symbol: "\u25C8" },
    ];
    function formatPopupFilterMonth(monthValue)
    {
        if (!monthValue)
        {
            return "";
        }
        const parts = String(monthValue).split("-");
        if (parts.length !== 2)
        {
            return monthValue;
        }
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const monthIndex = Number(parts[1]) - 1;
        return monthIndex >= 0 && monthIndex < monthNames.length ? `${monthNames[monthIndex]} ${parts[0]}` : monthValue;
    }
    function normalizePopupFilterMonthValue(value)
    {
        if (!value)
        {
            return "";
        }
        const rawValue = String(value).trim();
        const numericMatch = rawValue.match(/^(\d{4})-(\d{1,2})$/);
        if (numericMatch)
        {
            const year = Number(numericMatch[1]);
            const month = Number(numericMatch[2]);
            if (Number.isFinite(year) && Number.isFinite(month) && month >= 1 && month <= 12)
            {
                return `${year}-${String(month).padStart(2, "0")}`;
            }
        }
        const labelMatch = rawValue.match(/^([A-Za-z]{3,9})\s+(\d{4})$/);
        if (!labelMatch)
        {
            return rawValue;
        }
        const monthKey = String(labelMatch[1] || "").toLowerCase();
        const year = Number(labelMatch[2]);
        const monthMap = {
            jan: 1, january: 1,
            feb: 2, february: 2,
            mar: 3, march: 3,
            apr: 4, april: 4,
            may: 5,
            jun: 6, june: 6,
            jul: 7, july: 7,
            aug: 8, august: 8,
            sep: 9, sept: 9, september: 9,
            oct: 10, october: 10,
            nov: 11, november: 11,
            dec: 12, december: 12
        };
        const month = monthMap[monthKey];
        if (!Number.isFinite(year) || !month)
        {
            return rawValue;
        }
        return `${year}-${String(month).padStart(2, "0")}`;
    }
    function parsePopupLeaveDate(value)
    {
        if (!value)
        {
            return null;
        }
        const parsed = new Date(value);
        return Number.isNaN(parsed.getTime()) ? null : parsed;
    }
    function formatPopupFilterDisplayDate(value)
    {
        const parsed = parsePopupLeaveDate(value);
        if (!parsed)
        {
            return "dd-mm-yyyy";
        }
        return String(parsed.getDate()).padStart(2, "0") + "-" + String(parsed.getMonth() + 1).padStart(2, "0") + "-" + parsed.getFullYear();
    }
    function closeMyLeavePopupFilterPickers(exceptShell)
    {
        document.querySelectorAll(".popup-filter-month-shell.open, .popup-filter-date-shell.open, .popup-filter-leave-shell.open").forEach((shell) =>
        {
            if (shell === exceptShell) return;
            shell.classList.remove("open", "open-up");
            const trigger = shell.querySelector(".month-trigger, .date-trigger, .popup-filter-leave-trigger");
            if (trigger) trigger.setAttribute("aria-expanded", "false");
        });
    }
    function buildMyLeavePopupFilterLeaveType(shell)
    {
        if (!shell || shell.dataset.bound === "true")
        {
            return;
        }
        const hiddenInput = shell.querySelector('input[type="hidden"]');
        const trigger = shell.querySelector(".popup-filter-leave-trigger");
        const valueNode = shell.querySelector(".popup-filter-leave-value");
        const menu = shell.querySelector(".popup-filter-leave-menu");
        const options = Array.from(shell.querySelectorAll(".popup-filter-leave-option"));
        if (!hiddenInput || !trigger || !valueNode || !menu || !options.length)
        {
            return;
        }
        const sync = () =>
        {
            const selected = options.find((option) => (option.dataset.value || "") === (hiddenInput.value || "")) || options[0];
            window.setSafeHTML(valueNode, selected.dataset.displayLabel || '<span class="popup-filter-leave-value-symbol" aria-hidden="true">&#9679;</span><span class="popup-filter-leave-value-text">All types</span>');
            options.forEach((option) => option.classList.toggle("is-selected", option === selected));
        };
        const scrollToSelectedOption = () =>
        {
            const selected = options.find((option) => option.classList.contains("is-selected")) || options[0];
            if (!selected) return;
            const targetTop = selected.offsetTop - ((menu.clientHeight - selected.offsetHeight) / 2);
            const maxScrollTop = Math.max(0, menu.scrollHeight - menu.clientHeight);
            menu.scrollTop = Math.max(0, Math.min(targetTop, maxScrollTop));
        };
        const close = () =>
        {
            shell.classList.remove("open");
            trigger.setAttribute("aria-expanded", "false");
        };
        trigger.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            const willOpen = !shell.classList.contains("open");
            closeMyLeavePopupFilterPickers(shell);
            if (willOpen)
            {
                shell.classList.add("open");
                trigger.setAttribute("aria-expanded", "true");
                requestAnimationFrame(scrollToSelectedOption);
            }
            else
            {
                close();
            }
        });
        trigger.addEventListener("keydown", (event) =>
        {
            if (event.key === "Enter" || event.key === " ")
            {
                event.preventDefault();
                trigger.click();
            }
        });
        options.forEach((option) =>
        {
            option.addEventListener("click", () =>
            {
                hiddenInput.value = option.dataset.value || "";
                hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
                sync();
                close();
            });
        });
        hiddenInput.addEventListener("input", sync);
        hiddenInput.addEventListener("change", sync);
        document.addEventListener("click", (event) =>
        {
            if (!shell.contains(event.target))
            {
                close();
            }
        });
        shell.dataset.bound = "true";
        sync();
    }
    function buildMyLeavePopupFilterMonthPicker(shell)
    {
        if (!shell || shell.dataset.bound === "true")
        {
            return;
        }
        const hiddenInput = shell.querySelector('input[type="hidden"]');
        const trigger = shell.querySelector(".month-trigger");
        const menu = shell.querySelector(".month-menu");
        const valueNode = shell.querySelector(".month-value");
        const currentNode = shell.querySelector(".month-current");
        const grid = shell.querySelector(".month-grid");
        const prevButton = shell.querySelector(".prev-year");
        const nextButton = shell.querySelector(".next-year");
        const currentButton = shell.querySelector(".today-action");
        const clearButton = shell.querySelector(".clear-action");
        if (!hiddenInput || !trigger || !menu || !valueNode || !currentNode || !grid)
        {
            return;
        }
        const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        let viewYear = null;
        let manualYear = false;
        let openedAt = 0;
        const getToday = () =>
        {
            const parts = String(myLeaveConfig.currentMonth || "").split("-");
            const serverYear = Number(parts[0]);
            const serverMonth = Number(parts[1]);
            if (Number.isFinite(serverYear) && Number.isFinite(serverMonth) && serverYear > 2000)
            {
                return { year: serverYear, month: serverMonth };
            }
            const now = new Date();
            return { year: now.getFullYear(), month: now.getMonth() + 1 };
        };
        const getMonthFromHidden = () =>
        {
            const normalized = normalizePopupFilterMonthValue(hiddenInput.value || hiddenInput.getAttribute("value") || "");
            const match = String(normalized).trim().match(/^(\d{4})-(\d{2})$/);
            if (!match)
            {
                return null;
            }
            const year = Number(match[1]);
            const month = Number(match[2]);
            if (!Number.isFinite(year) || !Number.isFinite(month) || month < 1 || month > 12)
            {
                return null;
            }
            hiddenInput.value = normalized;
            return { year, month };
        };
        const initialHidden = getMonthFromHidden();
        const formatMonthValue = (year, month) => String(year) + "-" + String(month).padStart(2, "0");
        const getSelected = () => getMonthFromHidden();
        const getSelectedOrToday = () => getSelected() || getToday();
        const forceViewYearFromHidden = () =>
        {
            const selected = getSelected();
            if (selected && !manualYear)
            {
                viewYear = selected.year;
                currentNode.textContent = String(viewYear);
            }
        };
        const sync = () =>
        {
            valueNode.textContent = formatPopupFilterMonth(hiddenInput.value) || "Select month";
            shell.parentElement.classList.toggle("has-value", !!hiddenInput.value);
        };
        const close = () =>
        {
            const wasOpenUp = shell.classList.contains("open-up");
            shell.classList.remove("open");
            trigger.setAttribute("aria-expanded", "false");
            viewYear = null;
            manualYear = false;
            openedAt = 0;
            window.clearTimeout(shell._closeTimer);
            shell._closeTimer = window.setTimeout(() =>
            {
                if (!shell.classList.contains("open"))
                {
                    shell.classList.remove("open-up");
                }
            }, wasOpenUp ? 230 : 10);
            sync();
        };
        const render = () =>
        {
            const selected = getSelected();
            const today = getToday();
            if (!Number.isFinite(viewYear))
            {
                viewYear = selected ? selected.year : today.year;
            }
            currentNode.textContent = String(viewYear);
            grid.replaceChildren();
            monthLabels.forEach((label, index) =>
            {
                const month = index + 1;
                const button = document.createElement("button");
                button.type = "button";
                button.className = "month-option";
                button.textContent = label;
                button.classList.toggle("is-current", viewYear === today.year && month === today.month);
                button.classList.toggle("is-selected", !!selected && selected.year === viewYear && selected.month === month);
                button.addEventListener("click", (event) =>
                {
                    event.stopPropagation();
                    hiddenInput.value = formatMonthValue(viewYear, month);
                    sync();
                    hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                    hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
                    close();
                });
                grid.appendChild(button);
            });
        };
        const open = () =>
        {
            if (hiddenInput.disabled || shell.classList.contains("is-disabled")) return;
            const isOpen = shell.classList.contains("open");
            closeMyLeavePopupFilterPickers(shell);
            if (isOpen)
            {
                close();
                return;
            }
            manualYear = false;
            const selected = getMonthFromHidden();
            const today = getToday();
            viewYear = selected && Number.isFinite(selected.year) ? selected.year : today.year;
            openedAt = Date.now();
            window.clearTimeout(shell._closeTimer);
            const menuHeight = Math.max(menu.offsetHeight || 0, 176);
            const shellRect = shell.getBoundingClientRect();
            const viewportPadding = 18;
            const spaceBelow = window.innerHeight - shellRect.bottom - viewportPadding;
            const spaceAbove = shellRect.top - viewportPadding;
            shell.classList.toggle("open-up", spaceAbove >= menuHeight || spaceAbove >= spaceBelow);
            shell.classList.add("open");
            trigger.setAttribute("aria-expanded", "true");
            sync();
            render();
            currentNode.textContent = String(viewYear);
        };
        trigger.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            open();
        });
        trigger.addEventListener("keydown", (event) =>
        {
            if (event.key === "Enter" || event.key === " ")
            {
                event.preventDefault();
                open();
            }
        });
        prevButton?.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            if (Date.now() - openedAt < 300) return;
            viewYear = (Number.isFinite(viewYear) ? viewYear : getSelectedOrToday().year) - 1;
            manualYear = true;
            render();
        });
        nextButton?.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            if (Date.now() - openedAt < 300) return;
            viewYear = (Number.isFinite(viewYear) ? viewYear : getSelectedOrToday().year) + 1;
            manualYear = true;
            render();
        });
        currentButton?.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            const today = getToday();
            manualYear = false;
            viewYear = today.year;
            hiddenInput.value = formatMonthValue(today.year, today.month);
            sync();
            render();
            hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
            hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
        });
        clearButton?.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            manualYear = false;
            hiddenInput.value = "";
            viewYear = getToday().year;
            sync();
            render();
            hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
            hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
        });
        hiddenInput.addEventListener("input", () =>
        {
            if (shell.classList.contains("open"))
            {
                forceViewYearFromHidden();
                render();
            }
            sync();
        });
        hiddenInput.addEventListener("change", () =>
        {
            if (shell.classList.contains("open"))
            {
                forceViewYearFromHidden();
                render();
            }
            sync();
        });
        document.addEventListener("click", (event) =>
        {
            if (!shell.contains(event.target))
            {
                close();
            }
        });
        shell.dataset.bound = "true";
        if (initialHidden)
        {
            viewYear = initialHidden.year;
        }
        sync();
        render();
    }
    function showMyLeavePopupFilterPointWarning(shell, message)
    {
        if (!shell || !message)
        {
            return;
        }
        const field = shell.closest(".popup-filter-field") || shell.parentElement;
        if (!field)
        {
            return;
        }
        let warning = field.querySelector(".popup-filter-point-warning");
        if (!warning)
        {
            warning = document.createElement("div");
            warning.className = "popup-filter-point-warning";
            warning.setAttribute("role", "alert");
            field.appendChild(warning);
        }
        warning.textContent = message;
        warning.hidden = false;
        field.classList.add("has-point-warning");
        shell.classList.add("is-warning");
        window.clearTimeout(field._popupFilterWarningTimer);
        field._popupFilterWarningTimer = window.setTimeout(() =>
        {
            warning.hidden = true;
            field.classList.remove("has-point-warning");
            shell.classList.remove("is-warning");
        }, 2600);
    }
    function buildMyLeavePopupFilterDatePicker(shell)
    {
        if (!shell || shell.dataset.bound === "true")
        {
            return;
        }
        const hiddenInput = shell.querySelector('input[type="hidden"]');
        const trigger = shell.querySelector(".date-trigger");
        const valueNode = shell.querySelector(".date-value");
        const menu = shell.querySelector(".date-menu");
        const currentNode = shell.querySelector(".date-current");
        const grid = shell.querySelector(".date-grid");
        const prevButton = shell.querySelector(".prev-month");
        const nextButton = shell.querySelector(".next-month");
        const todayButton = shell.querySelector(".today-action");
        const clearButton = shell.querySelector(".clear-action");
        if (!hiddenInput || !trigger || !valueNode || !menu || !currentNode || !grid)
        {
            return;
        }
        const readMyLeaveJson = (id, fallback) =>
        {
            const node = document.getElementById(id);
            if (!node) return fallback;
            try
            {
                return JSON.parse(node.value || "[]");
            }
            catch (error)
            {
                return fallback;
            }
        };
        const companyHolidays = readMyLeaveJson("my-leave-company-holidays-json", []);
        const existingLeaves = readMyLeaveJson("my-leave-existing-leaves-json", []);
        const parseDate = (value) =>
        {
            const parts = String(value || "").split("-");
            if (parts.length !== 3) return null;
            const date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
            return Number.isNaN(date.getTime()) ? null : date;
        };
        const formatDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
        const getCurrentEditLeaveId = () => String(document.getElementById("edit-leave-form")?.dataset.editLeaveId || "");
        const getCompanyHoliday = (dateStr) => companyHolidays.find((holiday) => holiday.date === dateStr);
        const getAppliedLeave = (dateStr) =>
        {
            const currentId = getCurrentEditLeaveId();
            return existingLeaves.find((leave) =>
                String(leave.id || "") !== currentId
                && (leave.status === "Pending" || leave.status === "Approved")
                && leave.from <= dateStr
                && leave.to >= dateStr
            );
        };
        const getDateBlockMeta = (date, minimum) =>
        {
            const dateStr = formatDate(date);
            const companyHoliday = getCompanyHoliday(dateStr);
            const appliedLeave = getAppliedLeave(dateStr);
            const isWeekend = date.getDay() === 0 || date.getDay() === 6;
            const beforeMinimum = !!minimum && date < minimum;
            const reasons = [];
            if (beforeMinimum) reasons.push("Past date");
            if (isWeekend) reasons.push("Weekend");
            if (companyHoliday) reasons.push(`${companyHoliday.is_optional ? "Optional" : "Company"} holiday: ${companyHoliday.name}`);
            if (appliedLeave) reasons.push(`${appliedLeave.status} leave: ${appliedLeave.type}`);
            return {
                dateStr,
                companyHoliday,
                appliedLeave,
                isWeekend,
                beforeMinimum,
                disabled: beforeMinimum || isWeekend || !!companyHoliday || !!appliedLeave,
                tooltip: reasons.join(" | "),
            };
        };
        const getNextSelectableDate = (startDate, minimum) =>
        {
            const candidate = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate());
            const floor = minimum && candidate < minimum ? minimum : candidate;
            candidate.setFullYear(floor.getFullYear(), floor.getMonth(), floor.getDate());
            for (let offset = 0; offset < 370; offset += 1)
            {
                if (!getDateBlockMeta(candidate, minimum).disabled)
                {
                    return new Date(candidate.getFullYear(), candidate.getMonth(), candidate.getDate());
                }
                candidate.setDate(candidate.getDate() + 1);
            }
            return floor;
        };
        const today = () =>
        {
            const browserToday = new Date();
            const normalizedBrowserToday = new Date(browserToday.getFullYear(), browserToday.getMonth(), browserToday.getDate());
            const parts = String(myLeaveConfig.today || "").split("-");
            const year = Number(parts[0]);
            const month = Number(parts[1]);
            const day = Number(parts[2]);
            if (Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day))
            {
                const serverToday = new Date(year, month - 1, day);
                return normalizedBrowserToday > serverToday ? normalizedBrowserToday : serverToday;
            }
            return normalizedBrowserToday;
        };
        const getMinimum = () =>
        {
            const form = hiddenInput.form || shell.closest("form");
            if (hiddenInput.name === "from_date")
            {
                return today();
            }
            if (hiddenInput.name === "to_date" && form)
            {
                const fromDate = parseDate(form.querySelector('input[name="from_date"]')?.value || "");
                return fromDate ? new Date(fromDate.getFullYear(), fromDate.getMonth(), fromDate.getDate()) : today();
            }
            return null;
        };
        const getPreferredOpenDate = () =>
        {
            const todayDate = today();
            const minimumDate = getMinimum();
            const selectedDate = parseDate(hiddenInput.value);
            if (selectedDate && (!minimumDate || selectedDate >= minimumDate))
            {
                return selectedDate;
            }
            if (hiddenInput.name === "from_date")
            {
                return todayDate;
            }
            if (minimumDate && todayDate < minimumDate)
            {
                return minimumDate;
            }
            return todayDate;
        };
        const getViewDate = () =>
        {
            const selected = parseDate(hiddenInput.value);
            const source = hiddenInput.name === "from_date" ? getPreferredOpenDate() : (selected || getPreferredOpenDate());
            return new Date(source.getFullYear(), source.getMonth(), 1);
        };
        const sync = () =>
        {
            valueNode.textContent = formatPopupFilterDisplayDate(hiddenInput.value);
            shell.parentElement.classList.toggle("has-value", !!hiddenInput.value);
        };
        const close = () =>
        {
            const wasOpenUp = shell.classList.contains("open-up");
            shell.classList.remove("open");
            trigger.setAttribute("aria-expanded", "false");
            delete shell.dataset.previewValue;
            delete shell._viewDate;
            window.clearTimeout(shell._closeTimer);
            shell._closeTimer = window.setTimeout(() =>
            {
                if (!shell.classList.contains("open"))
                {
                    shell.classList.remove("open-up");
                }
            }, wasOpenUp ? 230 : 10);
        };
        const render = () =>
        {
            const selected = parseDate(hiddenInput.value);
            const preview = parseDate(shell.dataset.previewValue || "");
            const effectiveSelected = hiddenInput.name === "from_date"
                ? (preview || getPreferredOpenDate())
                : (preview || selected || getPreferredOpenDate());
            const currentToday = today();
            const minimum = getMinimum();
            const sourceViewDate = shell._viewDate || preview || getViewDate();
            const viewDate = new Date(sourceViewDate.getFullYear(), sourceViewDate.getMonth(), 1);
            const monthStart = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
            const daysInMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0).getDate();
            const firstDayIndex = (monthStart.getDay() + 6) % 7;
            shell._viewDate = viewDate;
            currentNode.textContent = monthStart.toLocaleDateString("en-US", { month: "long", year: "numeric" });
            grid.replaceChildren();
            if (prevButton)
            {
                prevButton.disabled = !!minimum && viewDate.getFullYear() === minimum.getFullYear() && viewDate.getMonth() === minimum.getMonth();
            }
            for (let index = 0; index < firstDayIndex; index += 1)
            {
                const blank = document.createElement("button");
                blank.type = "button";
                blank.className = "date-day muted";
                blank.disabled = true;
                grid.appendChild(blank);
            }
            for (let day = 1; day <= daysInMonth; day += 1)
            {
                const date = new Date(viewDate.getFullYear(), viewDate.getMonth(), day);
                const dateMeta = getDateBlockMeta(date, minimum);
                const button = document.createElement("button");
                button.type = "button";
                button.className = "date-day";
                button.textContent = String(day);
                button.classList.toggle("today", date.getTime() === currentToday.getTime());
                button.classList.toggle("weekend", dateMeta.isWeekend);
                button.classList.toggle("company-holiday", !!dateMeta.companyHoliday);
                button.classList.toggle("optional-company-holiday", !!dateMeta.companyHoliday?.is_optional);
                button.classList.toggle("pending-leave-date", dateMeta.appliedLeave?.status === "Pending");
                button.classList.toggle("approved-leave-date", dateMeta.appliedLeave?.status === "Approved");
                button.classList.toggle("past-disabled", dateMeta.beforeMinimum);
                button.classList.toggle("blocked-date", dateMeta.disabled);
                button.classList.toggle("selected", !!effectiveSelected && date.getFullYear() === effectiveSelected.getFullYear() && date.getMonth() === effectiveSelected.getMonth() && date.getDate() === effectiveSelected.getDate());
                button.classList.toggle("muted", !!dateMeta.beforeMinimum);
                button.disabled = !!dateMeta.beforeMinimum;
                if (dateMeta.disabled)
                {
                    button.setAttribute("aria-disabled", "true");
                }
                if (dateMeta.tooltip)
                {
                    button.title = dateMeta.tooltip;
                    button.setAttribute("aria-label", `${day}: ${dateMeta.tooltip}`);
                }
                if (!dateMeta.disabled)
                {
                    button.addEventListener("click", () =>
                    {
                        hiddenInput.value = formatDate(date);
                        shell._viewDate = new Date(date.getFullYear(), date.getMonth(), 1);
                        sync();
                        hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
                        close();
                    });
                }
                grid.appendChild(button);
            }
        };
        let dateOpenedAt = 0;
        const open = () =>
        {
            if (hiddenInput.disabled || shell.classList.contains("is-disabled"))
            {
                const form = hiddenInput.form || shell.closest("form");
                const monthInput = form ? form.querySelector('input[name="month"]') : null;
                const fromInput = form ? form.querySelector('input[name="from_date"]') : null;

                if (monthInput && monthInput.value)
                {
                    showMyLeavePopupFilterPointWarning(shell, "Clear Month to use date range.");
                }
                else if (hiddenInput.name === "to_date" && fromInput && !fromInput.value)
                {
                    showMyLeavePopupFilterPointWarning(shell, "Select From Date first.");
                }
                return;
            }
            const isOpen = shell.classList.contains("open");
            closeMyLeavePopupFilterPickers(shell);
            if (isOpen)
            {
                close();
                return;
            }
            const openDate = getPreferredOpenDate();
            shell.dataset.previewValue = formatDate(openDate);
            shell._viewDate = new Date(openDate.getFullYear(), openDate.getMonth(), 1);
            window.clearTimeout(shell._closeTimer);
            const isEditLeavePicker = !!shell.closest("#edit-leave-template");
            let openUp = false;
            if (!isEditLeavePicker)
            {
                const menuHeight = Math.max(menu.offsetHeight || 0, 318);
                const shellRect = shell.getBoundingClientRect();
                const viewportPadding = 18;
                const spaceBelow = window.innerHeight - shellRect.bottom - viewportPadding;
                const spaceAbove = shellRect.top - viewportPadding;
                openUp = spaceAbove >= menuHeight || spaceAbove >= spaceBelow;
            }
            shell.classList.toggle("open-up", openUp);
            shell.classList.add("open");
            trigger.setAttribute("aria-expanded", "true");
            dateOpenedAt = Date.now();
            render();
        };
        trigger.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            open();
        });
        trigger.addEventListener("keydown", (event) =>
        {
            if (event.key === "Enter" || event.key === " ")
            {
                event.preventDefault();
                open();
            }
        });
        prevButton?.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            if (Date.now() - dateOpenedAt < 300) return;
            shell._viewDate = new Date(shell._viewDate.getFullYear(), shell._viewDate.getMonth() - 1, 1);
            render();
        });
        nextButton?.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            if (Date.now() - dateOpenedAt < 300) return;
            shell._viewDate = new Date(shell._viewDate.getFullYear(), shell._viewDate.getMonth() + 1, 1);
            render();
        });
        todayButton?.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            const minimum = getMinimum();
            const todayDate = today();
            const nextDate = getNextSelectableDate(minimum && todayDate < minimum ? minimum : todayDate, minimum);
            hiddenInput.value = formatDate(nextDate);
            shell._viewDate = new Date(nextDate.getFullYear(), nextDate.getMonth(), 1);
            sync();
            render();
            hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
            hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
        });
        clearButton?.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            hiddenInput.value = "";
            shell._viewDate = getViewDate();
            sync();
            render();
            hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
            hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
        });
        hiddenInput.addEventListener("input", () =>
        {
            sync();
            shell._viewDate = getViewDate();
            render();
        });
        hiddenInput.addEventListener("change", () =>
        {
            sync();
            shell._viewDate = getViewDate();
            render();
        });
        document.addEventListener("click", (event) =>
        {
            if (!shell.contains(event.target))
            {
                close();
            }
        });
        shell.dataset.bound = "true";
        shell._renderDatePicker = render;
        shell._syncDatePicker = sync;
        shell._viewDate = getViewDate();
        sync();
        render();
    }
    function buildPendingLeavePillHtml(leave)
    {
        return `
            <span class="leave-pill leave-pill-${escapeHtml(leave.leave_type_class)}">
                <span class="leave-pill-symbol">${escapeHtml(leave.leave_symbol || getLeaveTypeSymbol(leave.leave_type))}</span>
                <span class="leave-pill-code">${escapeHtml(leave.leave_code || getLeaveCode(leave.leave_type))}</span>
                <span class="leave-pill-name">${escapeHtml(leave.leave_type)}</span>
            </span>
        `;
    }
    function buildPendingScheduleHtml(leave)
    {
        const scheduleTimeClass = leave.leave_type === "Short"
            ? " schedule-time-short"
            : leave.leave_type === "Half"
                ? " schedule-time-half"
                : "";
        const timeHtml = leave.from_time_display && leave.to_time_display
            ? `
                <span>${escapeHtml(leave.from_time_display)}</span>
                <span class="range-arrow">&rarr;</span>
                <span>${escapeHtml(leave.to_time_display)}</span>
            `
            : `<span>Full day</span>`;
        return `
            <div class="schedule-block">
                <div class="schedule-line">
                    <span class="meta-icon" data-meta-icon="calendar" aria-hidden="true"></span>
                    <strong>${escapeHtml(leave.from_date_display)}</strong>
                    <span class="range-arrow">&rarr;</span>
                    <strong>${escapeHtml(leave.to_date_display)}</strong>
                </div>
                <div class="schedule-line schedule-time${scheduleTimeClass}">
                    <span class="meta-icon" data-meta-icon="clock" aria-hidden="true"></span>
                    ${timeHtml}
                </div>
            </div>
        `;
    }
    function buildPendingUpdatedHtml(leave)
    {
        const relativeText = formatAjaxRelativeLeaveAge(leave.updated_iso);
        const count = Number(leave.updated_count || 0);
        const dateText = relativeText === "-" ? "-" : (count > 0 ? `${relativeText} (${count})` : relativeText);
        if (!leave.updated_iso)
        {
            return `
                <div class="applied-block">
                    <div class="applied-line">
                        <span class="meta-icon meta-icon-updated" data-meta-icon="updated" aria-hidden="true"></span>
                        <strong>-</strong>
                    </div>
                </div>
            `;
        }
        return `
            <div class="applied-block">
                <div class="applied-line">
                    <span class="meta-icon meta-icon-updated" data-meta-icon="updated" aria-hidden="true"></span>
                    <strong data-relative-datetime="${escapeHtml(leave.updated_iso)}" data-relative-count="${count}">${escapeHtml(dateText)}</strong>
                </div>
                <div class="applied-line">
                    <span class="meta-icon meta-icon-updated-time" data-meta-icon="clock" aria-hidden="true"></span>
                    <span>${escapeHtml(leave.updated_time_display || "")}</span>
                </div>
            </div>
        `;
    }
    function updatePendingDaysBlock(block, leave)
    {
        if (!block) return;
        const valueNode = block.querySelector(".js-days-value");
        const labelNode = block.querySelector(".js-days-label");
        block.dataset.leaveType = leave.leave_type;
        block.dataset.fromDate = leave.from_date;
        block.dataset.toDate = leave.to_date;
        if (!valueNode || !labelNode) return;
        block.dataset.daysTarget = String(leave.days_target ?? 0);
        block.dataset.daysSuffix = leave.days_suffix || "";
        block.dataset.daysLabel = leave.days_label || "days";
        valueNode.textContent = leave.days_value_display || "0";
        labelNode.textContent = leave.days_label || "days";
    }
    function applyPendingInlineReason(node, fullText)
    {
        if (!node) return;
        const safeText = String(fullText || "").trim();
        node.dataset.title = node.dataset.title || "Leave Reason";
        fitInlineReason(node, safeText);
    }
    function updatePendingCounts(count)
    {
        [
            document.querySelector('#pending-panel .card-summary-badge strong'),
            document.querySelector('.summary-panel-open-requests strong')
        ].forEach((node) =>
        {
            if (!node) return;
            node.textContent = String(count);
            node.dataset.countupTarget = String(count);
        });
    }
    function setCurrentFilterState(nextState)
    {
        currentFilterState = nextState;
        const node = document.getElementById("my-leave-filters-json");
        if (node)
        {
            node.value = JSON.stringify(currentFilterState);
        }
    }
    function normalizeFilterState(filterState)
    {
        const normalized = {
            leave_type: filterState.leave_type || null,
            month: filterState.month || null,
            from_date: filterState.from_date || null,
            to_date: filterState.to_date || null,
        };
        if (normalized.month)
        {
            normalized.from_date = null;
            normalized.to_date = null;
        }
        else if (normalized.from_date || normalized.to_date)
        {
            normalized.month = null;
        }
        return normalized;
    }
    function hasActiveFilter(filterState)
    {
        return Boolean(filterState.leave_type || filterState.month || filterState.from_date || filterState.to_date);
    }
    function getPanelStatusLabel(panelId)
    {
        const status = panelId.replace("-panel", "");
        return status.charAt(0).toUpperCase() + status.slice(1);
    }
    function updateStatusPanelCount(status, count)
    {
        const panelId = getPanelIdFromStatus(status);
        const summaryCount = document.querySelector(`#${panelId} .card-summary-badge strong`);
        [summaryCount].forEach((node) =>
        {
            if (!node) return;
            node.textContent = String(count);
            node.dataset.countupTarget = String(count);
        });
        if (status === "Pending")
        {
            const summaryOpenRequests = document.querySelector('.summary-panel-open-requests strong');
            if (summaryOpenRequests)
            {
                summaryOpenRequests.textContent = String(count);
                summaryOpenRequests.dataset.countupTarget = String(count);
            }
        }
    }
    function renderFilterBadges(status)
    {
        const panelId = getPanelIdFromStatus(status);
        const panel = document.getElementById(panelId);
        const header = panel?.querySelector(".table-header");
        const filterButton = header?.querySelector(".filter-btn");
        const filterState = normalizeFilterState(currentFilterState[status] || {});
        const indicator = document.querySelector(`[data-tab-filter-indicator="${status}"]`);
        if (!header || !filterButton) return;
        if (indicator)
        {
            indicator.classList.toggle("hidden", !hasActiveFilter(filterState));
        }
        let badges = header.querySelector(".filter-badges");
        if (!hasActiveFilter(filterState))
        {
            if (badges) badges.remove();
            return;
        }
        if (!badges)
        {
            badges = document.createElement("div");
            badges.className = "filter-badges";
            filterButton.insertAdjacentElement("afterend", badges);
        }
        const badgeParts = [];
        if (filterState.leave_type)
        {
            badgeParts.push(`<span class="badge">&#127991; ${escapeHtml(filterState.leave_type)} <button type="button" class="badge-clear-btn" data-filter-status="${escapeHtml(status)}" data-filter-field="leave_type" aria-label="Clear leave type filter">&#10006;</button></span>`);
        }
        if (filterState.month)
        {
            badgeParts.push(`<span class="badge">&#128467; ${escapeHtml(filterState.month)} <button type="button" class="badge-clear-btn" data-filter-status="${escapeHtml(status)}" data-filter-field="month" aria-label="Clear month filter">&#10006;</button></span>`);
        }
        else if (filterState.from_date || filterState.to_date)
        {
            badgeParts.push(`<span class="badge">&#128197; ${escapeHtml(filterState.from_date || "...")} &rarr; ${escapeHtml(filterState.to_date || "...")} <button type="button" class="badge-clear-btn" data-filter-status="${escapeHtml(status)}" data-filter-field="date_range" aria-label="Clear date range filter">&#10006;</button></span>`);
        }
        window.setSafeHTML(badges, badgeParts.join(""));
    }
    function rowMatchesFilter(row, filterState)
    {
        const leaveType = row.dataset.leaveType || "";
        const fromDate = row.dataset.fromDate || "";
        const toDate = row.dataset.toDate || "";
        if (filterState.leave_type && leaveType !== filterState.leave_type)
        {
            return false;
        }
        if (filterState.month && fromDate.slice(0, 7) !== filterState.month)
        {
            return false;
        }
        if (!filterState.month)
        {
            if (filterState.from_date && fromDate < filterState.from_date)
            {
                return false;
            }
            if (filterState.to_date && toDate > filterState.to_date)
            {
                return false;
            }
        }
        return true;
    }
    function applyFilterStateToPanel(status)
    {
        const panelId = getPanelIdFromStatus(status);
        const panel = document.getElementById(panelId);
        if (!panel) return;
        const filterState = normalizeFilterState(currentFilterState[status] || {});
        const rows = Array.from(panel.querySelectorAll("tbody tr.leave-row"));
        rows.forEach((row) =>
        {
            const matches = rowMatchesFilter(row, filterState);
            row.classList.toggle("filter-hidden", !matches);
            if (!matches)
            {
                row.hidden = true;
            }
        });
        renderFilterBadges(status);
        const visibleCount = rows.filter((row) => !row.classList.contains("filter-hidden")).length;
        updateStatusPanelCount(status, visibleCount);
        refreshPanelPagination(panelId);
    }
    function renumberPendingRows()
    {
        document.querySelectorAll('#pending-panel tbody tr.leave-row:not(.filter-hidden)').forEach((row, index) =>
        {
            const serialCell = row.querySelector(".sn-cell");
            if (serialCell)
            {
                serialCell.textContent = String(index + 1);
            }
        });
    }
    function refreshPanelPagination(panelId)
    {
        const panel = document.getElementById(panelId);
        const wrapper = panel?.querySelector(".js-paginated-table");
        const tbody = panel?.querySelector("tbody");
        const pagination = panel?.querySelector(`[data-pagination-for="${panelId}"]`);
        if (!panel || !wrapper || !tbody || !pagination) return;
        let emptyRow = tbody.querySelector(".table-empty-row");
        const rowsPerPage = parseInt(wrapper.dataset.rowsPerPage || "5", 10);
        const firstBtn = pagination.querySelector('[data-page-action="first"]');
        const prevBtn = pagination.querySelector('[data-page-action="prev"]');
        const nextBtn = pagination.querySelector('[data-page-action="next"]');
        const lastBtn = pagination.querySelector('[data-page-action="last"]');
        const status = pagination.querySelector(".pagination-status");
        const getRows = () => Array.from(tbody.querySelectorAll("tr.leave-row:not(.filter-hidden)"));
        const getTotalPages = () => Math.max(1, Math.ceil(getRows().length / rowsPerPage));
        let currentPage = Number.parseInt(panel.dataset.paginationPage || "1", 10) || 1;
        const renderPage = () =>
        {
            const rows = getRows();
            if (rows.length === 0)
            {
                wrapper.classList.add("is-empty");
                if (emptyRow) emptyRow.hidden = false;
                pagination.hidden = true;
                pagination.classList.add("is-hidden");
                panel.dataset.paginationPage = "1";
                return;
            }
            wrapper.classList.remove("is-empty");
            tbody.querySelectorAll(".table-empty-row").forEach((row) =>
            {
                row.hidden = true;
            });
            const totalPages = getTotalPages();
            currentPage = Math.min(Math.max(currentPage, 1), totalPages);
            panel.dataset.paginationPage = String(currentPage);
            rows.forEach((row, index) =>
            {
                const start = (currentPage - 1) * rowsPerPage;
                const end = start + rowsPerPage;
                const shouldHide = !(index >= start && index < end);
                row.hidden = shouldHide;
                row.classList.toggle("pagination-hidden", shouldHide);
            });
            if (status) status.textContent = `Page ${currentPage} of ${totalPages}`;
            if (firstBtn) firstBtn.disabled = currentPage === 1;
            if (prevBtn) prevBtn.disabled = currentPage === 1;
            if (nextBtn) nextBtn.disabled = currentPage === totalPages;
            if (lastBtn) lastBtn.disabled = currentPage === totalPages;
            const hidePagination = totalPages <= 1;
            pagination.hidden = hidePagination;
            pagination.classList.toggle("is-hidden", hidePagination);
            hydrateInlineReasons(panel);
        };
        const rows = getRows();
        if (rows.length === 0)
        {
            wrapper.classList.add("is-empty");
            if (!emptyRow)
            {
                emptyRow = document.createElement("tr");
                emptyRow.className = "table-empty-row";
                const colCount = panelId === "pending-panel" ? 8 : panelId === "approved-panel" ? 8 : 9;
                const emptyDefs = {
                    "pending-panel": {
                        theme: "mle-pending",
                        title: "Nothing in the Queue",
                        message: "No pending leave requests right now. Apply when you need time off.",
                        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3h14" stroke-width="2" opacity="0.6"/><path d="M5 21h14" stroke-width="2" opacity="0.6"/><path d="M7 3v3c0 2.8 2.2 5 5 5s5-2.2 5-5V3" opacity="0.3"/><path d="M7 21v-3c0-2.8 2.2-5 5-5s5 2.2 5 5v3" opacity="0.3"/><circle cx="12" cy="12" r="0.8" fill="currentColor" opacity="0.6" class="mle-sand"/><circle cx="11.2" cy="17" r="0.5" fill="currentColor" opacity="0.4"/><circle cx="12.8" cy="17.5" r="0.5" fill="currentColor" opacity="0.4"/><circle cx="12" cy="16.5" r="0.6" fill="currentColor" opacity="0.5"/></svg>'
                    },
                    "approved-panel": {
                        theme: "mle-approved",
                        title: "All Clear Here",
                        message: "No approved leaves to display. Approved requests will appear here.",
                        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4" opacity="0.25" fill="currentColor"/><line x1="12" y1="1" x2="12" y2="4" stroke-width="2" opacity="0.5" class="mle-ray"/><line x1="12" y1="20" x2="12" y2="23" stroke-width="2" opacity="0.5" class="mle-ray"/><line x1="1" y1="12" x2="4" y2="12" stroke-width="2" opacity="0.5" class="mle-ray"/><line x1="20" y1="12" x2="23" y2="12" stroke-width="2" opacity="0.5" class="mle-ray"/><line x1="4.22" y1="4.22" x2="6.34" y2="6.34" stroke-width="1.5" opacity="0.35"/><line x1="17.66" y1="17.66" x2="19.78" y2="19.78" stroke-width="1.5" opacity="0.35"/><line x1="4.22" y1="19.78" x2="6.34" y2="17.66" stroke-width="1.5" opacity="0.35"/><line x1="17.66" y1="6.34" x2="19.78" y2="4.22" stroke-width="1.5" opacity="0.35"/><path d="m9 12 2 2 4-4" stroke-width="2.5" opacity="0.8" class="mle-check"/></svg>'
                    },
                    "rejected-panel": {
                        theme: "mle-rejected",
                        title: "Nothing Declined",
                        message: "No rejected requests found. That\u2019s great \u2014 your requests are going through!",
                        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" opacity="0.2"/><polyline points="14 2 14 8 20 8" opacity="0.3"/><line x1="8" y1="13" x2="16" y2="13" opacity="0.15" stroke-width="1.2"/><line x1="8" y1="17" x2="12" y2="17" opacity="0.1" stroke-width="1.2"/><line x1="9" y1="9" x2="10" y2="9" opacity="0.1" stroke-width="1.2"/><line x1="9.5" y1="11.5" x2="14.5" y2="16.5" stroke-width="2.2" opacity="0.7" class="mle-cross"/><line x1="14.5" y1="11.5" x2="9.5" y2="16.5" stroke-width="2.2" opacity="0.7" class="mle-cross"/></svg>'
                    }
                };
                const def = emptyDefs[panelId] || emptyDefs["pending-panel"];
                const emptyCell = document.createElement("td");
                emptyCell.colSpan = colCount;
                window.setSafeHTML(emptyCell, '<div class="mle-empty-state ' + def.theme + '">' +
                    '<div class="mle-particles">' +
                        '<span class="mle-dot md1"></span>' +
                        '<span class="mle-dot md2"></span>' +
                        '<span class="mle-dot md3"></span>' +
                        '<span class="mle-dot md4"></span>' +
                        '<span class="mle-dot md5"></span>' +
                        '<span class="mle-dot md6"></span>' +
                        '<span class="mle-dot md7"></span>' +
                        '<span class="mle-dot md8"></span>' +
                    '</div>' +
                    '<div class="mle-stars">' +
                        '<span class="mle-star ms1">\u2726</span>' +
                        '<span class="mle-star ms2">\u2727</span>' +
                        '<span class="mle-star ms3">\u22C6</span>' +
                        '<span class="mle-star ms4">\u2726</span>' +
                        '<span class="mle-star ms5">\u2727</span>' +
                        '<span class="mle-star ms6">\u22C6</span>' +
                        '<span class="mle-star ms7">\u2726</span>' +
                        '<span class="mle-star ms8">\u2727</span>' +
                        '<span class="mle-star ms9">\u2734</span>' +
                        '<span class="mle-star ms10">\u2726</span>' +
                    '</div>' +
                    '<div class="mle-core">' +
                        '<div class="mle-visual">' +
                            '<div class="mle-aura"></div>' +
                            '<div class="mle-icon-anchor">' +
                                '<div class="mle-icon-float">' + def.icon + '</div>' +
                            '</div>' +
                        '</div>' +
                        '<div class="mle-content">' +
                            '<strong class="mle-title">' + def.title + '</strong>' +
                            '<p class="mle-message">' + def.message + '</p>' +
                        '</div>' +
                    '</div>' +
                '</div>');
                emptyRow.replaceChildren(emptyCell);
                tbody.appendChild(emptyRow);
            }
            if (emptyRow) emptyRow.hidden = false;
            pagination.hidden = true;
            pagination.classList.add("is-hidden");
            return;
        }
        panel._paginationController = {
            showRow(row)
            {
                const rows = getRows();
                const rowIndex = rows.indexOf(row);
                if (rowIndex === -1) return;
                currentPage = Math.floor(rowIndex / rowsPerPage) + 1;
                renderPage();
            }
        };
        if (firstBtn) firstBtn.onclick = () => { if (currentPage !== 1) { currentPage = 1; renderPage(); } };
        if (prevBtn) prevBtn.onclick = () => { if (currentPage > 1) { currentPage -= 1; renderPage(); } };
        if (nextBtn) nextBtn.onclick = () => { const totalPages = getTotalPages(); if (currentPage < totalPages) { currentPage += 1; renderPage(); } };
        if (lastBtn) lastBtn.onclick = () => { const totalPages = getTotalPages(); if (currentPage !== totalPages) { currentPage = totalPages; renderPage(); } };
        renderPage();
    }
    function refreshPendingPagination()
    {
        refreshPanelPagination("pending-panel");
    }
    function refreshAllMyLeavePanelPagination()
    {
        ["pending-panel", "approved-panel", "rejected-panel"].forEach((panelId) =>
        {
            refreshPanelPagination(panelId);
        });
    }
    function updateMyLeaveCountElement(element, value)
    {
        if (!element)
        {
            return;
        }
        const safeValue = Number.isFinite(Number(value)) ? Number(value) : 0;
        element.dataset.countupTarget = String(safeValue);
        element.textContent = String(safeValue);
        if (typeof window.animateCountUp === "function")
        {
            window.animateCountUp(element, safeValue, { duration: 260 });
        }
    }
    function setMyLeaveSectionCountElement(element, value)
    {
        if (!element)
        {
            return;
        }
        const safeValue = Number.isFinite(Number(value)) ? Number(value) : 0;
        element.dataset.countupTarget = String(safeValue);
        element.dataset.countupLastTarget = String(safeValue);
        element.dataset.countupPlayed = "true";
        element.textContent = String(safeValue);
    }
    function updateMyLeavePanelCounts(counts)
    {
        if (!counts || typeof counts !== "object")
        {
            return;
        }
        const panelMap = {
            pending: "pending-panel",
            approved: "approved-panel",
            rejected: "rejected-panel"
        };
        Object.entries(panelMap).forEach(([key, panelId]) =>
        {
            const count = counts[key] ?? 0;
            const panelCount = document.querySelector(`#${panelId} .card-summary-badge strong`);
            updateMyLeaveCountElement(panelCount, count);
        });
    }
    function getVisibleMyLeaveRowCount(panelId)
    {
        const panel = document.getElementById(panelId);
        if (!panel)
        {
            return 0;
        }
        return Array.from(panel.querySelectorAll("tbody tr.leave-row"))
            .filter((row) => !row.classList.contains("filter-hidden"))
            .length;
    }
    function syncMyLeavePanelCountsFromRows()
    {
        const panelMap = {
            pending: "pending-panel",
            approved: "approved-panel",
            rejected: "rejected-panel"
        };
        Object.entries(panelMap).forEach(([key, panelId]) =>
        {
            const count = getVisibleMyLeaveRowCount(panelId);
            const panelCount = document.querySelector(`#${panelId} .card-summary-badge strong`);
            setMyLeaveSectionCountElement(panelCount, count);
        });
    }
    function syncMyLeaveTopBarCounts(counts = {})
    {
        const panelMap = {
            pending: "pending-panel",
            approved: "approved-panel",
            rejected: "rejected-panel"
        };
        Object.entries(panelMap).forEach(([key, panelId]) =>
        {
            const fallback = getVisibleMyLeaveRowCount(panelId);
            const rawCount = Number(counts[key]);
            const count = Number.isFinite(rawCount) ? rawCount : fallback;
            const panelCount = document.querySelector(`#${panelId} .card-summary-badge strong`);
            updateMyLeaveCountElement(panelCount, count);
        });
    }
    function syncMyLeaveStatusTabCounts(counts = {})
    {
        const panelMap = {
            pending: "pending-panel",
            approved: "approved-panel",
            rejected: "rejected-panel"
        };
        Object.entries(panelMap).forEach(([key, panelId]) =>
        {
            const fallback = getVisibleMyLeaveRowCount(panelId);
            const rawCount = Number(counts[key]);
            const count = Number.isFinite(rawCount) ? rawCount : fallback;
            const tabCount = document.querySelector(`.status-tab[data-target="${panelId}"] [data-live-count]`);
            setMyLeaveSectionCountElement(tabCount, count);
        });
    }
    function updatePendingRowFromPayload(leave)
    {
        const row = document.querySelector(`#pending-panel .leave-row[data-leave-id="${leave.id}"]`);
        if (!row) return;
        row.className = `leave-row leave-row-${leave.leave_type_class}`;
        window.setSafeHTML(row.children[1], buildPendingLeavePillHtml(leave));
        window.setSafeHTML(row.children[2], buildPendingScheduleHtml(leave));
        window.setSafeHTML(row.children[5], buildPendingUpdatedHtml(leave));
        updatePendingDaysBlock(row.querySelector(".js-days-block"), leave);
        applyPendingInlineReason(row.querySelector(".js-inline-reason"), leave.reason);
        const editBtn = row.querySelector(".edit-btn");
        if (editBtn)
        {
            editBtn.dataset.type = leave.leave_type;
            editBtn.dataset.from = leave.from_date;
            editBtn.dataset.to = leave.to_date;
            editBtn.dataset.reason = leave.reason || "";
            editBtn.dataset.fromdatetime = leave.from_datetime_iso || "";
            editBtn.dataset.todatetime = leave.to_datetime_iso || "";
        }
        row.dataset.leaveType = leave.leave_type;
        row.dataset.fromDate = leave.from_date;
        row.dataset.toDate = leave.to_date;
    }
    let myLeaveLiveNotificationSignature = "";
    let myLeaveLiveNotificationInitialized = false;
    let myLeaveRefreshInFlight = false;
    let myLeaveRefreshQueued = null;
    function getMyLeaveDecisionNotifications(notifications)
    {
        if (!Array.isArray(notifications))
        {
            return [];
        }
        return notifications.filter((item) => item && item.target_panel);
    }
    function buildMyLeaveNotificationSignature(notifications, totalCount = 0)
    {
        const itemsSig = getMyLeaveDecisionNotifications(notifications)
            .map((item) => [
                item.id || "",
                item.target_panel || "",
                item.status || "",
                item.status_class || "",
                item.updated_text || "",
                item.applied_text || "",
                item.reviewer_name || ""
            ].join(":"))
            .join("|");
        return `${totalCount}:${itemsSig}`;
    }
    function getActiveMyLeavePanelId()
    {
        return document.querySelector(".leave-panel.is-active")?.id || "pending-panel";
    }
    function applyAllMyLeaveFilters()
    {
        ["Pending", "Approved", "Rejected"].forEach((status) =>
        {
            applyFilterStateToPanel(status);
        });
    }
    async function refreshMyLeaveLiveData(options = {})
    {
        if (myLeaveRefreshInFlight)
        {
            myLeaveRefreshQueued = options;
            return;
        }
        myLeaveRefreshInFlight = true;
        try
        {
            const response = await fetch(`${myLeaveUrl}?section=live_data`, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Cache-Control": "no-cache"
                },
                credentials: "same-origin",
                cache: "no-store"
            });
            if (!response.ok)
            {
                throw new Error("Unable to refresh my leave data.");
            }
            const payload = typeof window.parseJsonOrSessionExpired === "function"
                ? await window.parseJsonOrSessionExpired(response)
                : await response.json();
            if (payload.sessionExpired)
            {
                showAjaxMessages(payload.messages);
                if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(payload);
                return;
            }
            const activePanelId = options.activePanel || getActiveMyLeavePanelId();
            const summaryHost = document.querySelector("[data-my-leave-summary]");
            const statsHost = document.querySelector("[data-my-leave-stats]");
            const pendingBody = document.querySelector('[data-my-leave-table-body="pending"]');
            const approvedBody = document.querySelector('[data-my-leave-table-body="approved"]');
            const rejectedBody = document.querySelector('[data-my-leave-table-body="rejected"]');
            if (summaryHost && typeof payload.summary_html === "string")
            {
                window.setSafeHTML(summaryHost, payload.summary_html);
            }
            if (statsHost && typeof payload.stats_html === "string")
            {
                window.setSafeHTML(statsHost, payload.stats_html);
            }
            if (pendingBody && typeof payload.pending_rows_html === "string")
            {
                window.setSafeHTML(pendingBody, payload.pending_rows_html);
            }
            if (approvedBody && typeof payload.approved_rows_html === "string")
            {
                window.setSafeHTML(approvedBody, payload.approved_rows_html);
            }
            if (rejectedBody && typeof payload.rejected_rows_html === "string")
            {
                window.setSafeHTML(rejectedBody, payload.rejected_rows_html);
            }
            hydrateRelativeDates();
            hydrateDayBlocks();
            hydrateInlineReasons();
            renumberPendingRows();
            updateMyLeavePanelCounts(payload.counts);
            applyAllMyLeaveFilters();
            refreshAllMyLeavePanelPagination();
            syncMyLeavePanelCountsFromRows();
            syncMyLeaveTopBarCounts(payload.live_counts || payload.counts);
            syncMyLeaveStatusTabCounts(payload.live_counts || payload.counts);
            
            document.dispatchEvent(new CustomEvent("countup:refresh", {
                detail: {
                    root: document,
                    duration: 220,
                    force: true
                }
            }));
            
            // Multiple passes to ensure absolute sync after any animations or filter transitions
            requestAnimationFrame(() => {
                syncMyLeavePanelCountsFromRows();
                syncMyLeaveTopBarCounts(payload.live_counts || payload.counts);
                syncMyLeaveStatusTabCounts(payload.live_counts || payload.counts);
            });
            
            window.setTimeout(() =>
            {
                syncMyLeavePanelCountsFromRows();
                syncMyLeaveTopBarCounts(payload.live_counts || payload.counts);
                syncMyLeaveStatusTabCounts(payload.live_counts || payload.counts);
            }, 350);

            if (typeof window.myLeaveActivatePanel === "function")
            {
                window.myLeaveActivatePanel(activePanelId);
            }
            if (options.targetPanel && options.highlightLeaveId && typeof window.highlightMyLeaveRow === "function")
            {
                window.highlightMyLeaveRow(options.targetPanel, String(options.highlightLeaveId));
            }
        }
        catch (error)
        {
            console.error("My leave live refresh error:", error);
        }
        finally
        {
            myLeaveRefreshInFlight = false;
            if (myLeaveRefreshQueued)
            {
                const nextOptions = myLeaveRefreshQueued;
                myLeaveRefreshQueued = null;
                refreshMyLeaveLiveData(nextOptions);
            }
        }
    }
    function ensureAjaxMessageHost()
    {
        let host = document.getElementById("ajax-message-stack");
        if (host) return host;
        host = document.createElement("div");
        host.id = "ajax-message-stack";
        host.style.position = "fixed";
        host.style.top = "18px";
        host.style.right = "18px";
        host.style.zIndex = "9999";
        host.style.display = "grid";
        host.style.gap = "10px";
        host.style.maxWidth = "360px";
        document.body.appendChild(host);
        return host;
    }
    function showAjaxMessages(messages)
    {
        if (!Array.isArray(messages) || messages.length === 0) return;
        const host = ensureAjaxMessageHost();
        messages.forEach((message) =>
        {
            const item = document.createElement("div");
            const isError = String(message.tags || "").includes("error");
            const isWarning = String(message.tags || "").includes("warning");
            item.style.background = isError ? "#fff1f2" : isWarning ? "#fff7ed" : "#effaf5";
            item.style.border = `1px solid ${isError ? "#fda4af" : isWarning ? "#fdba74" : "#86efac"}`;
            item.style.borderRadius = "14px";
            item.style.boxShadow = "0 14px 30px rgba(15, 23, 42, 0.14)";
            item.style.padding = "12px 14px";
            item.style.color = "#16324f";
            item.style.fontSize = "0.92rem";
            item.style.lineHeight = "1.35";
            const title = document.createElement("strong");
            title.textContent = message.title || "Update";
            title.style.display = "block";
            title.style.marginBottom = "4px";
            const text = document.createElement("div");
            text.textContent = message.text || "";
            item.appendChild(title);
            item.appendChild(text);
            host.appendChild(item);
            window.setTimeout(() =>
            {
                item.remove();
                if (!host.childElementCount)
                {
                    host.remove();
                }
            }, isError ? 6500 : 4200);
        });
    }
    async function parseAjaxResponse(response)
    {
        if (typeof window.parseJsonOrSessionExpired === "function")
        {
            return window.parseJsonOrSessionExpired(response);
        }

        try
        {
            return await response.json();
        }
        catch (error)
        {
            return {
                success: false,
                messages: [{ title: "Action needed", text: "Could not read the server response.", tags: "error" }]
            };
        }
    }
    async function parseAjaxResponseLenient(response, fallbackMessage)
    {
        const contentType = response.headers.get("content-type") || "";
        if (response.redirected || (!contentType.includes("application/json") && !response.ok))
        {
            return typeof window.buildSessionExpiredPayload === "function"
                ? window.buildSessionExpiredPayload(response)
                : {
                    success: false,
                    sessionExpired: true,
                    redirectUrl: response.url || "/portal/",
                    messages: [{ title: "Session expired", text: "Please log in again.", tags: "error" }]
                };
        }

        if (contentType.includes("application/json"))
        {
            return parseAjaxResponse(response);
        }
        return {
            success: response.ok,
            messages: fallbackMessage
                ? [{ title: "Success", text: fallbackMessage, tags: "success" }]
                : []
        };
    }
    async function submitPendingLeaveAjax(url, formData)
    {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": getCSRFToken()
            },
            body: formData,
            credentials: "same-origin"
        });
        const payload = await parseAjaxResponse(response);
        if (payload.sessionExpired)
        {
            showAjaxMessages(payload.messages);
            if (typeof window.redirectAfterSessionExpired === "function")
            {
                window.redirectAfterSessionExpired(payload);
            }
            return payload;
        }

        if (!response.ok || payload.success === false)
        {
            showAjaxMessages(payload.messages);
            if (typeof window.playLeaveErrorTone === "function")
            {
                window.playLeaveErrorTone();
            }
            return payload;
        }
        showAjaxMessages(payload.messages);
        return payload;
    }
    function getPanelIdFromStatus(status)
    {
        return `${String(status || "").toLowerCase()}-panel`;
    }
    window.bindPendingLeaveEditAjax = function (form)
    {
        if (!form) return;
        form.onsubmit = async function (event)
        {
            event.preventDefault();
            const shouldUpdate = typeof window.showThemeConfirm === "function"
                ? await window.showThemeConfirm("Update this leave request?", {
                    title: "Confirm update",
                    confirmText: "Update",
                    variant: "update"
                })
                : window.confirm("Update this leave request?");
            if (!shouldUpdate)
            {
                return false;
            }
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.disabled = true;
            const payload = await submitPendingLeaveAjax(form.action, new FormData(form));
            if (submitBtn) submitBtn.disabled = false;
            if (!payload.success || !payload.leave)
            {
                return false;
            }
            if (typeof window.playLeaveActionTone === "function")
            {
                window.playLeaveActionTone("edit");
            }
            await refreshMyLeaveLiveData({
                activePanel: "pending-panel",
                targetPanel: "pending-panel",
                highlightLeaveId: payload.leave.id
            });
            if (typeof form._afterSuccessfulEdit === "function")
            {
                form._afterSuccessfulEdit(payload);
            }
            else if (typeof closeModal === "function")
            {
                closeModal();
            }
            return false;
        };
    };
    document.addEventListener("DOMContentLoaded", () =>
    {
        document.addEventListener("submit", async (event) =>
        {
            const form = event.target.closest(".js-pending-delete-form");
            if (!form) return;
            event.preventDefault();
            const shouldDelete = typeof window.showThemeConfirm === "function"
                ? await window.showThemeConfirm("Delete this leave?", {
                    title: "Delete leave",
                    confirmText: "Delete",
                    variant: "delete"
                })
                : window.confirm("Delete this leave?");
            if (!shouldDelete)
            {
                return;
            }
            const submitBtn = form.querySelector('button[type="submit"]');
            const row = form.closest(".leave-row");
            
            if (submitBtn) submitBtn.disabled = true;
            if (row) {
                row.style.opacity = "0.4";
                row.style.pointerEvents = "none";
                row.classList.add("deleting-feedback");
            }
            
            const payload = await submitPendingLeaveAjax(form.action, new FormData(form));
            if (submitBtn) submitBtn.disabled = false;
            
            if (!payload.success)
            {
                if (row) {
                    row.style.opacity = "";
                    row.style.pointerEvents = "";
                    row.classList.remove("deleting-feedback");
                }
                return;
            }
            if (typeof window.playLeaveActionTone === "function")
            {
                window.playLeaveActionTone("delete");
            }
            
            // Immediate UI update for the counts if available
            if (payload.live_counts) {
                syncMyLeaveTopBarCounts(payload.live_counts);
                syncMyLeaveStatusTabCounts(payload.live_counts);
            }
            
            await refreshMyLeaveLiveData({
                activePanel: "pending-panel"
            });
        });
        document.addEventListener("invalid", (event) =>
        {
            if (!event.target.closest("#edit-leave-form"))
            {
                return;
            }
            if (typeof window.playLeaveErrorTone === "function")
            {
                window.playLeaveErrorTone();
            }
        }, true);
        document.addEventListener("click", async (event) =>
        {
            const clearControl = event.target.closest('.filter-badges [data-filter-field], .filter-badges form[action*="clear-status-filter-field"] button');
            if (!clearControl) return;
            event.preventDefault();
            const panel = clearControl.closest(".leave-panel");
            const clearForm = clearControl.closest("form");
            const normalizedStatus = clearControl.dataset.filterStatus || (panel ? getPanelStatusLabel(panel.id) : "");
            const filterField = clearControl.dataset.filterField || "";
            if (!normalizedStatus) return;
            const nextState = { ...currentFilterState };
            const current = normalizeFilterState(nextState[normalizedStatus] || {});
            if (filterField === "date_range")
            {
                current.from_date = null;
                current.to_date = null;
            }
            else if (filterField)
            {
                current[filterField] = null;
            }
            if (hasActiveFilter(current))
            {
                nextState[normalizedStatus] = current;
            }
            else
            {
                delete nextState[normalizedStatus];
            }
            setCurrentFilterState(nextState);
            applyFilterStateToPanel(normalizedStatus);
            const requestUrl = filterField
                ? `/clear-status-filter-field/${normalizedStatus}/${filterField}/`
                : clearForm?.action;
            const response = await fetch(requestUrl, {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCSRFToken(),
                    "Cache-Control": "no-cache"
                },
                credentials: "same-origin",
                cache: "no-store"
            });
            const payload = await parseAjaxResponseLenient(response, "Filter updated.");
            if (!response.ok || payload.success === false)
            {
                showAjaxMessages(payload.messages);
                return;
            }
            showAjaxMessages(payload.messages);
        });
        ["Pending", "Approved", "Rejected"].forEach((status) =>
        {
            applyFilterStateToPanel(status);
        });
    });
    window.addEventListener("hr-notification-state-sync", function (event)
    {
        const detail = event.detail || {};
        const notificationDropdown = document.querySelector(".notification-dropdown[data-notification-api]");
        if (
            !notificationDropdown ||
            detail.apiUrl !== notificationDropdown.dataset.notificationApi ||
            detail.userKey !== notificationDropdown.dataset.notificationUserKey
        )
        {
            return;
        }
        if (detail.leaveCounts)
        {
            syncMyLeaveStatusTabCounts(detail.leaveCounts);
        }
        if (!Array.isArray(detail.notifications))
        {
            return;
        }
        const signature = buildMyLeaveNotificationSignature(detail.notifications, detail.notifications.length);
        if (!myLeaveLiveNotificationInitialized)
        {
            myLeaveLiveNotificationInitialized = true;
            myLeaveLiveNotificationSignature = signature;
            return;
        }
        if (!signature || signature === myLeaveLiveNotificationSignature)
        {
            return;
        }
        myLeaveLiveNotificationSignature = signature;
        const latestDecision = getMyLeaveDecisionNotifications(detail.notifications)[0] || {};
        refreshMyLeaveLiveData({
            activePanel: getActiveMyLeavePanelId(),
            targetPanel: latestDecision.target_panel || "",
            highlightLeaveId: latestDecision.id || ""
        });
    });
    const now = new Date();
    const today = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0") + "-" + String(now.getDate()).padStart(2, "0");
    document.getElementById("edit-from").min = today;
    document.getElementById("edit-to").min = today;
    // Once from_date is selected, user must NOT be able to pick a to_date before it
    document.addEventListener("DOMContentLoaded", () => 
    {
        const fromDate = document.getElementById("edit-from");
        const toDate = document.getElementById("edit-to");
        if (!fromDate || !toDate) return;
        toDate.addEventListener("change", () => 
        {
            // Block all dates before from_date
            toDate.min = fromDate.value;
            // If already selected to_date is invalid, clear it
            if (toDate.value && toDate.value < fromDate.value) 
            {
                toDate.value = "";
            }
        });
        fromDate.addEventListener("change", () => 
        {
            // Block all dates before from_date
            toDate.min = fromDate.value || today;
            // If already selected to_date is invalid, clear it
            if (toDate.value && toDate.value < fromDate.value) 
            {
                toDate.value = "";
            }
        });
    });
    
    let editStoredTime = 
    {
        Short: { hour: "", minute: "" },
        Half: { hour: "", minute: "" }
    };
    function rememberEditTimeForType(type)
    {
        if (type !== "Short" && type !== "Half") return;
        const hourSelect = document.getElementById("edit-hour");
        const minuteSelect = document.getElementById("edit-minute");
        editStoredTime[type] =
        {
            hour: hourSelect?.value || "",
            minute: minuteSelect?.value || ""
        };
    }
    function restoreEditTimeForType(type, fallbackHour = "", fallbackMinute = "")
    {
        if (type !== "Short" && type !== "Half") return;
        const hourSelect = document.getElementById("edit-hour");
        const minuteSelect = document.getElementById("edit-minute");
        const toTime = document.getElementById("edit-to-time");
        const ampm = document.getElementById("edit-ampm");
        if (!hourSelect || !minuteSelect) return;
        const stored = editStoredTime[type] || { hour: "", minute: "" };
        const restoreHour = stored.hour !== "" ? stored.hour : fallbackHour;
        const restoreMinute = stored.minute !== "" ? stored.minute : fallbackMinute;
        const hourValid = Array.from(hourSelect.options).some((option) => option.value === String(restoreHour));
        if (!hourValid)
        {
            hourSelect.value = "";
            minuteSelect.value = "";
            if (toTime) toTime.value = "";
            if (ampm) ampm.value = "";
            refreshEditTimeDropdowns();
            return;
        }
        hourSelect.value = restoreHour;
        hourSelect.dispatchEvent(new Event("change", { bubbles: true }));
        window.setTimeout(() =>
        {
            const minuteValid = Array.from(minuteSelect.options).some((option) => option.value === String(restoreMinute));
            if (minuteValid)
            {
                minuteSelect.value = restoreMinute;
                calculate_end_time();
            }
            else
            {
                minuteSelect.value = "";
                if (toTime) toTime.value = "";
            }
            refreshEditTimeDropdowns();
        }, 0);
    }
    function setEditTimeLayout(form, isTimeBased)
    {
        if (!form) return;
        form.classList.toggle("is-time-based", !!isTimeBased);
        form.classList.toggle("is-date-only", !isTimeBased);
    }
    function getEditTimeMenuLabel(shell)
    {
        const fullLabel = shell?.dataset.menuLabel || "Select";
        const isMobile = window.matchMedia && window.matchMedia("(max-width: 640px)").matches;
        if (!isMobile) return fullLabel;
        if (fullLabel === "Hour") return "Hr";
        if (fullLabel === "Minute") return "Min";
        return fullLabel;
    }
    function updateEditDurationSummary()
    {
        const leaveType = document.getElementById("edit-leave-type");
        const fromDate = document.getElementById("edit-from");
        const toDate = document.getElementById("edit-to");
        const value = document.getElementById("edit-duration-value");
        if (!leaveType || !fromDate || !toDate || !value)
        {
            return;
        }
        if (leaveType.value === "Short")
        {
            value.textContent = "2 Hours";
            syncEditSubmitState(fromDate.form);
            return;
        }
        if (leaveType.value === "Half")
        {
            value.textContent = "4 Hours";
            syncEditSubmitState(fromDate.form);
            return;
        }
        if (!fromDate.value || !toDate.value)
        {
            value.textContent = "-";
            syncEditSubmitState(fromDate.form);
            return;
        }
        const start = new Date(`${fromDate.value}T00:00:00`);
        const end = new Date(`${toDate.value}T00:00:00`);
        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start)
        {
            value.textContent = "-";
            syncEditSubmitState(fromDate.form);
            return;
        }
        const dayCount = Math.floor((end - start) / (24 * 60 * 60 * 1000)) + 1;
        value.textContent = `${dayCount} ${dayCount === 1 ? "Day" : "Days"}`;
        syncEditSubmitState(fromDate.form);
    }
    function getEditFormSnapshot(form)
    {
        if (!form) return {};
        return {
            type: form.querySelector("#edit-leave-type")?.value || "",
            from: form.querySelector("#edit-from")?.value || "",
            to: form.querySelector("#edit-to")?.value || "",
            reason: (form.querySelector("#edit-reason")?.value || "").trim(),
            fromDatetime: form.querySelector("#edit_from_datetime")?.value || "",
            toDatetime: form.querySelector("#edit_to_datetime")?.value || "",
        };
    }
    function syncEditSubmitState(form)
    {
        if (!form) return;
        const submitBtn = form.querySelector('button[type="submit"]');
        if (!submitBtn) return;
        const original = form.dataset.originalSnapshot || "";
        const snapshot = getEditFormSnapshot(form);
        const current = JSON.stringify(snapshot);
        const isTimeBased = snapshot.type === "Short" || snapshot.type === "Half";
        const hasValidDateRange = !!snapshot.from && !!snapshot.to && snapshot.to >= snapshot.from;
        const hasRequiredTimeRange = !isTimeBased || (!!snapshot.fromDatetime && !!snapshot.toDatetime);
        const isComplete = !!snapshot.type && hasValidDateRange && !!snapshot.reason && hasRequiredTimeRange;
        submitBtn.disabled = !isComplete || (!!original && current === original);
        submitBtn.classList.toggle("is-disabled-by-no-change", submitBtn.disabled);
    }
    function storeEditOriginalSnapshot(form)
    {
        if (!form) return;
        form.dataset.originalSnapshot = JSON.stringify(getEditFormSnapshot(form));
        syncEditSubmitState(form);
    }
    function bindEditChangeTracking(form)
    {
        if (!form || form.dataset.changeTrackingBound === "true") return;
        form.addEventListener("input", () => syncEditSubmitState(form));
        form.addEventListener("change", () => window.setTimeout(() => syncEditSubmitState(form), 0));
        form.dataset.changeTrackingBound = "true";
    }
    function refreshEditDatePickers()
    {
        const form = document.getElementById("edit-leave-form");
        form?.querySelectorAll(".popup-filter-date-shell").forEach((shell) =>
        {
            if (typeof shell._syncDatePicker === "function") shell._syncDatePicker();
            if (typeof shell._renderDatePicker === "function") shell._renderDatePicker();
        });
    }
    function applyEditLeaveDateRules()
    {
        const leaveType = document.getElementById("edit-leave-type");
        const fromDate = document.getElementById("edit-from");
        const toDate = document.getElementById("edit-to");
        if (!leaveType || !fromDate || !toDate) return;
        const isTimeBased = leaveType.value === "Short" || leaveType.value === "Half";
        const toDateShell = toDate.closest(".popup-filter-date-shell");
        fromDate.min = today;
        toDate.min = fromDate.value || today;
        if (isTimeBased)
        {
            toDateShell?.classList.add("is-disabled");
            if (fromDate.value && toDate.value !== fromDate.value)
            {
                toDate.value = fromDate.value;
                toDate.dispatchEvent(new Event("input", { bubbles: true }));
                toDate.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }
        else
        {
            toDateShell?.classList.remove("is-disabled");
            if (fromDate.value && toDate.value && toDate.value < fromDate.value)
            {
                toDate.value = "";
                toDate.dispatchEvent(new Event("input", { bubbles: true }));
                toDate.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }
        refreshEditDatePickers();
        updateEditDurationSummary();
    }
    function closeEditTimeDropdowns(exceptShell = null)
    {
        document.querySelectorAll("[data-time-select-shell].open").forEach((shell) =>
        {
            if (shell === exceptShell) return;
            shell.classList.remove("open");
            shell.querySelector(".custom-select-trigger")?.setAttribute("aria-expanded", "false");
        });
    }
    function syncEditTimeDropdown(select)
    {
        const shell = select?.closest("[data-time-select-shell]");
        if (!shell) return;
        const triggerText = shell.querySelector(".custom-select-value");
        const menu = shell.querySelector(".custom-select-menu");
        const selectedOption = select.options[select.selectedIndex] || select.options[0];
        const menuLabel = shell.dataset.menuLabel || "Select";
        const displayMenuLabel = getEditTimeMenuLabel(shell);
        if (triggerText)
        {
            triggerText.textContent = selectedOption?.value ? selectedOption.textContent : displayMenuLabel;
        }
        if (!menu) return;
        menu.replaceChildren();
        menu.setAttribute("data-menu-label", displayMenuLabel);
        Array.from(select.options).forEach((option, index) =>
        {
            const isResetOption = !option.value && index === 0 && (menuLabel === "Hour" || menuLabel === "Minute");
            if (!option.value && index === 0 && !isResetOption)
            {
                return;
            }
            const item = document.createElement("button");
            item.type = "button";
            item.className = "custom-option";
            item.dataset.value = option.value;
            const title = document.createElement("span");
            title.className = "option-title";
            title.textContent = isResetOption ? displayMenuLabel : option.textContent;
            item.appendChild(title);
            item.classList.toggle("selected", option.value === select.value);
            item.addEventListener("click", () =>
            {
                select.value = option.value;
                syncEditTimeDropdown(select);
                closeEditTimeDropdowns();
                select.dispatchEvent(new Event("change", { bubbles: true }));
            });
            menu.appendChild(item);
        });
    }
    function bindEditTimeDropdown(select)
    {
        const shell = select?.closest("[data-time-select-shell]");
        const trigger = shell?.querySelector(".custom-select-trigger");
        if (!select || !shell || !trigger || shell.dataset.bound === "true") return;
        trigger.addEventListener("click", (event) =>
        {
            event.stopPropagation();
            const shouldOpen = !shell.classList.contains("open");
            closeEditTimeDropdowns(shell);
            shell.classList.toggle("open", shouldOpen);
            trigger.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
        });
        trigger.addEventListener("keydown", (event) =>
        {
            if (event.key === "Enter" || event.key === " ")
            {
                event.preventDefault();
                trigger.click();
            }
        });
        select.addEventListener("change", () => syncEditTimeDropdown(select));
        if (select.id === "edit-ampm")
        {
            select.addEventListener("change", () =>
            {
                const hour = parseInt(document.getElementById("edit-hour")?.value, 10);
                select.value = Number.isNaN(hour) ? "" : (hour >= 12 ? "PM" : "AM");
                syncEditTimeDropdown(select);
            });
        }
        shell.dataset.bound = "true";
        syncEditTimeDropdown(select);
    }
    function refreshEditTimeDropdowns()
    {
        ["edit-hour", "edit-minute", "edit-ampm"].forEach((id) =>
        {
            const select = document.getElementById(id);
            bindEditTimeDropdown(select);
            syncEditTimeDropdown(select);
        });
    }
    document.addEventListener("click", (event) =>
    {
        if (!event.target.closest("[data-time-select-shell]"))
        {
            closeEditTimeDropdowns();
        }
    });
    window.addEventListener("resize", () =>
    {
        const form = document.getElementById("edit-leave-form");
        if (form && form.closest("#modal-content"))
        {
            refreshEditTimeDropdowns();
        }
    });
    // =======================================
    // OPEN EDIT LEAVE
    // =======================================
    function openEditLeave(btn, options = {})
    {
        const formTemplate = document.getElementById("edit-leave-template");
        const sharedModal = document.getElementById("modal");
        const modalBox = document.querySelector(".modal-box");
        const inlineHost = options.inlineHost || null;
        if (!inlineHost)
        {
            sharedModal?.classList.remove("popup-filter-modal-host");
            sharedModal?.classList.add("popup-edit-modal-host");
            if (modalBox) {
                modalBox.classList.remove("reason-modal", "compact-calendar", "expanded-calendar", "popup-filter-modal-box", "popup-edit-modal-box");
                modalBox.classList.add("popup-edit-modal-box");
            }
            modalContent.replaceChildren();
            modalContent.appendChild(formTemplate);
        }
        else
        {
            inlineHost.replaceChildren();
            inlineHost.appendChild(formTemplate);
            formTemplate.classList.add("calendar-inline-edit-template");
        }
        const form = document.getElementById("edit-leave-form");
        const title = formTemplate.querySelector(".edit-template-title-copy h3");
        const titleText = formTemplate.querySelector(".edit-template-title-copy p");
        const cancelBtn = form.querySelector(".edit-cancel-btn");
        form.classList.toggle("calendar-inline-edit-form", !!options.calendarInline);
        if (options.calendarInline)
        {
            if (title) title.textContent = "Edit from Calendar";
            if (titleText) titleText.hidden = true;
            if (cancelBtn) cancelBtn.dataset.action = "close-calendar-detail";
        }
        else
        {
            if (title) title.textContent = "Edit Leave";
            if (titleText) titleText.hidden = false;
            if (cancelBtn) cancelBtn.dataset.action = "close-modal";
            formTemplate.classList.remove("calendar-inline-edit-template");
        }
        buildMyLeavePopupFilterLeaveType(form.querySelector(".popup-filter-leave-shell"));
        form.querySelectorAll(".popup-filter-date-shell").forEach((shell) => buildMyLeavePopupFilterDatePicker(shell));
        form.reset(); // ?? clears previous values
        refreshEditTimeDropdowns();
        
        editStoredTime.Short = { hour: "", minute: "" };
        editStoredTime.Half  = { hour: "", minute: "" };
        form.action = `/edit-leave/${btn.dataset.id}/`;
        if (window.bindPendingLeaveEditAjax)
        {
            window.bindPendingLeaveEditAjax(form);
        }
        form._afterSuccessfulEdit = typeof options.afterSuccessfulEdit === "function" ? options.afterSuccessfulEdit : null;
        form.dataset.editLeaveId = btn.dataset.id || "";
        form.dataset.originalLeaveType = btn.dataset.type || "";
        const leaveType = document.getElementById("edit-leave-type");
        const fromDate = document.getElementById("edit-from");
        const toDate = document.getElementById("edit-to");
        const reason = document.getElementById("edit-reason");
        const fromTimeField = document.getElementById("edit_from_time_field");
        const toTimeField = document.getElementById("edit_to_time_field");
        const toDateShell = toDate.closest(".popup-filter-date-shell");
        leaveType.value = btn.dataset.type;
        leaveType.dataset.prevType = btn.dataset.type;
        setEditTimeLayout(form, btn.dataset.type === "Short" || btn.dataset.type === "Half");
        fromDate.value = btn.dataset.from;
        toDate.value = btn.dataset.to;
        reason.value = btn.dataset.reason;
        applyEditLeaveDateRules();
        [leaveType, fromDate, toDate].forEach((input) =>
        {
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
        });
        updateEditDurationSummary();
        document.getElementById("edit-existing-datetime").value = btn.dataset.fromdatetime || "";
        // Show time section if Short/Half
        if (btn.dataset.type === "Short" || btn.dataset.type === "Half")
        {
            fromTimeField.style.display = "block";
            toTimeField.style.display = "block";
            
            toDateShell?.classList.add("is-disabled");
            toDate.value = fromDate.value;
            toDate.dispatchEvent(new Event("input", { bubbles: true }));
            toDate.dispatchEvent(new Event("change", { bubbles: true }));
            generate_edit_time_fields(btn.dataset.type);
            // Populate existing time
            if (btn.dataset.fromdatetime && btn.dataset.todatetime)
            {
                const start = new Date(btn.dataset.fromdatetime);
                const hourSelect = document.getElementById("edit-hour");
                const minuteSelect = document.getElementById("edit-minute");
                const ampm = document.getElementById("edit-ampm");
                hourSelect.value = start.getHours();
                
                if (hourSelect.options.length > 1) 
                {
                    hourSelect.dispatchEvent(new Event("change"));
                }
                // wait for minute options to render
                setTimeout(() =>
                {
                    if (minuteSelect.options.length > 1) 
                    {
                        minuteSelect.value = start.getMinutes();
                        calculate_end_time();
                        rememberEditTimeForType(btn.dataset.type);
                        refreshEditTimeDropdowns();
                    }
                }, 0);
                
                ampm.value = start.getHours() >= 12 ? "PM" : "AM";
                calculate_end_time();
            }
        }
        else
        {
            fromTimeField.style.display = "none";
            toTimeField.style.display = "none";
            toDateShell?.classList.remove("is-disabled");
             // ?? Clear warning
            const warning = document.getElementById("edit-time-warning");
            if (warning) warning.innerText = "";
            const existingTimeBox = document.getElementById("edit-existing-time");
            if (existingTimeBox) existingTimeBox.style.display = "none";
        }
        // Handle leave type change
        // FIXED EVENT STACKING
        leaveType.onchange = function ()
        {
            const hourSelect = document.getElementById("edit-hour");
            const minuteSelect = document.getElementById("edit-minute");
            const toTime = document.getElementById("edit-to-time");
            const newType = this.value;
            const previousType = leaveType.dataset.prevType || btn.dataset.type;
            // ?? If previous type was Short or Half ? store its time
            rememberEditTimeForType(previousType);
            // Update tracker
            leaveType.dataset.prevType = newType;
            // ?? If new type is Short or Half
            if (newType === "Short" || newType === "Half")
            {
                setEditTimeLayout(form, true);
                fromTimeField.style.display = "block";
                toTimeField.style.display = "block";
                toDateShell?.classList.add("is-disabled");
                toDate.value = fromDate.value;
                toDate.dispatchEvent(new Event("input", { bubbles: true }));
                toDate.dispatchEvent(new Event("change", { bubbles: true }));
                applyEditLeaveDateRules();
                // Remember current selection before regenerating
                const previousHour = hourSelect.value;
                const previousMinute = minuteSelect.value;
                // Regenerate dropdowns
                generate_edit_time_fields(newType);
                restoreEditTimeForType(newType, previousHour, previousMinute);
            }
            else 
            {
                rememberEditTimeForType(previousType);
                setEditTimeLayout(form, false);
                fromTimeField.style.display = "none";
                toTimeField.style.display = "none";
                toTime.value = ""; // ?? Also clear when hiding
                toDateShell?.classList.remove("is-disabled");
                const warning = document.getElementById("edit-time-warning");
                if (warning) warning.innerText = "";
                const existingTimeBox = document.getElementById("edit-existing-time");
                if (existingTimeBox) existingTimeBox.style.display = "none";
                applyEditLeaveDateRules();
            }
            updateEditDurationSummary();
        };
        fromDate.onchange = function ()
        {
            const type = leaveType.value;
            applyEditLeaveDateRules();

            if (type !== "Short" && type !== "Half")
            {
                updateEditDurationSummary();
                return;
            }
            toDate.value = this.value;
            toDate.dispatchEvent(new Event("input", { bubbles: true }));
            toDate.dispatchEvent(new Event("change", { bubbles: true }));
            applyEditLeaveDateRules();
            updateEditDurationSummary();
            const hourSelect = document.getElementById("edit-hour");
            const minuteSelect = document.getElementById("edit-minute");
            const toTime = document.getElementById("edit-to-time");
            // store current selection
            rememberEditTimeForType(type);
            // regenerate dropdowns with strict rules
            generate_strict_edit_time(type);
            restoreEditTimeForType(type);
        };
        toDate.onchange = updateEditDurationSummary;
        bindEditChangeTracking(form);
        window.setTimeout(() =>
        {
            storeEditOriginalSnapshot(form);
            syncEditSubmitState(form);
        }, 20);
        if (!inlineHost)
        {
            openModal();
        }
    }
    // =======================================
    // GENERATE HOURS & MINUTES
    // =======================================
    function generate_edit_time_fields(type)
    {
        const fromDate = document.getElementById("edit-from");
        // If date exists, generate strict time
        if (fromDate.value)
        {
            generate_strict_edit_time(type);
            return;
        }
        const hourSelect = document.getElementById("edit-hour");
        const minuteSelect = document.getElementById("edit-minute");
        hourSelect.innerHTML = '<option value="">Hour</option>';
        minuteSelect.innerHTML = '<option value="">Minute</option>';
        if (type !== "Short" && type !== "Half")
        {
            refreshEditTimeDropdowns();
            return;
        }
        const startHour = 10;
        const endHour = (type === "Short") ? 16 : 14;
        // Generate Hours
        for (let h = startHour; h <= endHour; h++) 
        {
            const opt = document.createElement("option");
            opt.value = h;
            opt.textContent = h > 12 ? h - 12 : h;
            hourSelect.appendChild(opt);
        }
        // Generate Minutes
        for (let m = 0; m < 60; m++) 
        {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m.toString().padStart(2, "0");
            minuteSelect.appendChild(opt);
        }
        // Remove previous listeners by resetting handlers
        hourSelect.onchange = null;
        minuteSelect.onchange = null;
        // Reset minute when hour changes
        const ampm = document.getElementById("edit-ampm");
        const toTime = document.getElementById("edit-to-time");
        hourSelect.onchange = function () 
        {
            const selectedHour = parseInt(this.value);
            if (this.value === "") 
            {
                // ?? Reset to default
                ampm.value = "";
                minuteSelect.value = "";
                toTime.value = "";
                refreshEditTimeDropdowns();
                return;
            }
            // Set AM/PM
            ampm.value = selectedHour >= 12 ? "PM" : "AM";
            // ?? Reset minute and end time
            minuteSelect.value = "";
            toTime.value = "";
            refreshEditTimeDropdowns();
        };
        minuteSelect.onchange = calculate_end_time;
        refreshEditTimeDropdowns();
    }
    let TEST_TIME = "14:30";  // Example: TEST_TIME = "14:30";
    // =======================================
    // STRICT HOUR + MINUTE GENERATION
    // =======================================
    function generate_strict_edit_time(type)
    {
        const hourSelect = document.getElementById("edit-hour");
        const minuteSelect = document.getElementById("edit-minute");
        const fromDate = document.getElementById("edit-from");
        const warning = document.getElementById("edit-time-warning");
        const form = document.getElementById("edit-leave-form");
        const originalType = form?.dataset.originalLeaveType || "";
        const originalIsTimeBased = originalType === "Short" || originalType === "Half";
        hourSelect.innerHTML = '<option value="">Hour</option>';
        minuteSelect.innerHTML = '<option value="">Minute</option>';
        warning.innerText = "";
        if (!fromDate.value)
        {
            refreshEditTimeDropdowns();
            return;
        }
        if (type !== "Short" && type !== "Half")
        {
            refreshEditTimeDropdowns();
            return;
        }
        const startHour = 10;
        const endHour = (type === "Short") ? 16 : 14;
        const now = new Date();
        const selectedDate = new Date(fromDate.value);
        selectedDate.setHours(0,0,0,0);
        const today = new Date();
        today.setHours(0,0,0,0);
        let minHour = startHour;
        let minMinute = 0;
        // Handle Past Dates and Times
        if ( selectedDate < today )
        {
            warning.innerText = "Cannot change time for past leave.";
            const existingDatetime = document.getElementById("edit-existing-datetime").value;
            if (originalIsTimeBased && existingDatetime)
            {
                const start = new Date(existingDatetime);
                const hour = start.getHours();
                const minute = start.getMinutes();
                // Reset dropdowns
                hourSelect.innerHTML = "";
                minuteSelect.innerHTML = "";
                hourSelect.onchange = null;
                minuteSelect.onchange = null;
                const hourOption = document.createElement("option");
                hourOption.value = hour;
                hourOption.textContent = hour > 12 ? hour - 12 : hour;
                hourOption.selected = true;
                hourSelect.appendChild(hourOption);
                const minuteOption = document.createElement("option");
                minuteOption.value = minute;
                minuteOption.textContent = minute.toString().padStart(2,"0");
                minuteOption.selected = true;
                minuteSelect.appendChild(minuteOption);
                const ampm = document.getElementById("edit-ampm");
                ampm.value = hour >= 12 ? "PM" : "AM";
                calculate_end_time();
                refreshEditTimeDropdowns();
            }
            else
            {
                const ampm = document.getElementById("edit-ampm");
                hourSelect.innerHTML = '<option value="">Hour</option>';
                minuteSelect.innerHTML = '<option value="">Minute</option>';
                hourSelect.value = "";
                minuteSelect.value = "";
                if (ampm) ampm.value = "";
                const toTime = document.getElementById("edit-to-time");
                if (toTime) toTime.value = "";
                hourSelect.onchange = null;
                minuteSelect.onchange = null;
                refreshEditTimeDropdowns();
            }
            return;
        }
        // Handle Today's Date and Time
        if (selectedDate.getTime() === today.getTime())
        {
            const minAllowed = new Date(now.getTime() + 2 * 60 * 60 * 1000);
            minHour = minAllowed.getHours();
            minMinute = minAllowed.getMinutes();
            if (minHour < startHour)
            {
                minHour = startHour;
                minMinute = 0;
            }
            // Handle Todays Date and Past Times
            
            if ( minHour > endHour || minAllowed.toDateString() !== today.toDateString() )
            {
                warning.innerText = "No valid time available for today.";
                
                const existingDatetime = document.getElementById("edit-existing-datetime").value;
                if (originalIsTimeBased && existingDatetime)
                {
                    const start = new Date(existingDatetime);
                    const hour = start.getHours();
                    const minute = start.getMinutes();
                    // Disable generation
                    hourSelect.onchange = null;
                    minuteSelect.onchange = null;
                    // Inject hour option
                    const hourOption = document.createElement("option");
                    hourOption.value = hour;
                    hourOption.textContent = hour > 12 ? hour - 12 : hour;
                    hourOption.selected = true;
                    hourSelect.appendChild(hourOption);
                    // Inject minute option
                    const minuteOption = document.createElement("option");
                    minuteOption.value = minute;
                    minuteOption.textContent = minute.toString().padStart(2, "0");
                    minuteOption.selected = true;
                    minuteSelect.appendChild(minuteOption);
                    const ampm = document.getElementById("edit-ampm");
                    ampm.value = hour >= 12 ? "PM" : "AM";
                    calculate_end_time();
                    refreshEditTimeDropdowns();
                }
                else
                {
                    const ampm = document.getElementById("edit-ampm");
                    hourSelect.value = "";
                    minuteSelect.value = "";
                    if (ampm) ampm.value = "";
                    const toTime = document.getElementById("edit-to-time");
                    if (toTime) toTime.value = "";
                    refreshEditTimeDropdowns();
                }
                return;
            }
        }
        // Generate hours
        for (let h = startHour; h <= endHour; h++)
        {
            if (selectedDate.getTime() === today.getTime() && h < minHour)
                continue;
            const opt = document.createElement("option");
            opt.value = h;
            opt.textContent = h > 12 ? h - 12 : h;
            hourSelect.appendChild(opt);
        }
        // Hour change logic
        hourSelect.onchange = function ()
        {
            minuteSelect.innerHTML = '<option value="">Minute</option>';
            const ampm = document.getElementById("edit-ampm");
            const toTime = document.getElementById("edit-to-time");
            if (this.value === "")
            {
                ampm.value = "";
                toTime.value = "";
                refreshEditTimeDropdowns();
                return;
            }
            const selectedHour = parseInt(this.value);
            ampm.value = selectedHour >= 12 ? "PM" : "AM";
            toTime.value = "";
            const existingDatetime_forminutes = document.getElementById("edit-existing-datetime").value;
            let existingMinute = null;
            if (existingDatetime_forminutes)
            {
                existingMinute = new Date(existingDatetime_forminutes).getMinutes();
            }
            for (let m = 0; m < 60; m++)
            {
                // ? allow applied minute
                if ( selectedDate.getTime() === today.getTime() && selectedHour === minHour && m < minMinute && m !== existingMinute )
                    continue;
                const opt = document.createElement("option");
                opt.value = m;
                opt.textContent = m.toString().padStart(2, "0");
                minuteSelect.appendChild(opt);
            }
            refreshEditTimeDropdowns();
        };
        // ?? If hour already selected (edit case), generate minutes immediately
        if (hourSelect.value !== "")
        {
            hourSelect.onchange();
        }
        minuteSelect.onchange = calculate_end_time;
        refreshEditTimeDropdowns();
    }
    // =======================================
    // END TIME CALCULATION
    // =======================================
    function calculate_end_time()
    {
        const leaveType = document.getElementById("edit-leave-type");
        const fromDate = document.getElementById("edit-from");
        const hourSelect = document.getElementById("edit-hour");
        const minuteSelect = document.getElementById("edit-minute");
        const toTime = document.getElementById("edit-to-time");
        const fromHidden = document.getElementById("edit_from_datetime");
        const toHidden = document.getElementById("edit_to_datetime");
        if (!fromDate.value || !hourSelect.value || minuteSelect.value === "")
            return;
        const start = new Date(fromDate.value);
        start.setHours(parseInt(hourSelect.value));
        start.setMinutes(parseInt(minuteSelect.value));
        let duration = 0;
        if (leaveType.value === "Short") duration = 2;
        if (leaveType.value === "Half") duration = 4;
        if (duration === 0) return;
        const end = new Date(start.getTime() + duration * 60 * 60 * 1000);
        const displayHour = end.getHours() > 12 ? end.getHours() - 12 : (end.getHours() === 0 ? 12 : end.getHours());
        const displayMinute = end.getMinutes().toString().padStart(2, "0");
        const ampm = end.getHours() >= 12 ? "PM" : "AM";
        toTime.value = `${displayHour}:${displayMinute} ${ampm}`;
        fromHidden.value = start.toISOString();
        toHidden.value = end.toISOString();
        updateEditDurationSummary();
        syncEditSubmitState(fromHidden.form);
    }
    let reasonModalCloseTimer = null;
    let activeReasonAnchor = null;
    function showManagedModal(modal)
    {
        if (!modal) return;
        if (modal._closeTimer)
        {
            clearTimeout(modal._closeTimer);
            modal._closeTimer = null;
        }
        modal._lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        modal.classList.remove("is-closing");
        modal.style.display = "flex";
        modal.setAttribute("aria-hidden", "false");
    }
    function hideManagedModal(modal, onClosed)
    {
        if (!modal) return;
        const activeElement = document.activeElement;
        if (activeElement instanceof HTMLElement && modal.contains(activeElement))
        {
            activeElement.blur();
        }
        modal.classList.add("is-closing");
        modal.setAttribute("aria-hidden", "true");
        if (modal._closeTimer)
        {
            clearTimeout(modal._closeTimer);
        }
        modal._closeTimer = setTimeout(function ()
        {
            modal.style.display = "none";
            modal.classList.remove("is-closing");
            modal._closeTimer = null;
            if (typeof onClosed === "function") onClosed();
            if (modal._lastFocusedElement instanceof HTMLElement && document.contains(modal._lastFocusedElement))
            {
                modal._lastFocusedElement.focus({ preventScroll: true });
            }
            modal._lastFocusedElement = null;
        }, 400);
    }
    function formatReasonModalClockTime(isoValue, fallbackText)
    {
        if (isoValue)
        {
            const date = new Date(isoValue);
            if (!Number.isNaN(date.getTime()))
            {
                return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true });
            }
        }
        const match = String(fallbackText || "").match(/\b\d{1,2}:\d{2}\s*[AP]M\b/i);
        return match ? match[0].toUpperCase() : "-";
    }
    function formatReasonModalDate(dateValue)
    {
        if (!dateValue) return "-";
        const parsed = new Date(`${dateValue}T00:00:00`);
        if (Number.isNaN(parsed.getTime())) return dateValue;
        return parsed.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" });
    }
    function formatReasonModalRelativeAge(isoValue)
    {
        if (!isoValue) return "";
        const target = new Date(isoValue);
        if (Number.isNaN(target.getTime())) return "";
        const now = new Date();
        const diffMs = Math.max(0, now.getTime() - target.getTime());
        const diffMinutes = Math.floor(diffMs / (60 * 1000));
        const diffHours = Math.floor(diffMs / (60 * 60 * 1000));
        const minuteRemainder = String(diffMinutes % 60).padStart(2, "0");
        const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const startOfTarget = new Date(target.getFullYear(), target.getMonth(), target.getDate());
        const diffDays = Math.max(0, Math.floor((startOfToday - startOfTarget) / (24 * 60 * 60 * 1000)));
        if (diffMinutes <= 0) return "just now";
        if (diffMinutes === 1) return "1 min ago";
        if (diffMinutes <= 59) return `${diffMinutes} min ago`;
        if (diffHours === 1) return `1 hour, ${minuteRemainder} min ago`;
        if (diffHours <= 23) return `${diffHours} hour, ${minuteRemainder} min ago`;
        if (diffDays <= 6) return `${diffDays} ${diffDays === 1 ? "day" : "days"} ago`;
        return target.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" });
    }
    function getReasonModalRowMeta(reasonText)
    {
        const row = reasonText.closest("tr.leave-row");
        const panelId = row?.dataset.leavePanel || reasonText.closest(".leave-panel")?.id || "pending-panel";
        const statusKey = panelId.replace("-panel", "");
        const leaveType = row?.dataset.leaveType || "Leave";
        const leaveTypeClass = ["sick", "unpaid", "earned", "short", "half"].includes(leaveType.toLowerCase())
            ? leaveType.toLowerCase()
            : "default";
        const daysBlock = row?.querySelector(".js-days-block");
        const scheduleBlock = row?.querySelector(".schedule-block");
        const appliedBlock = row?.children?.[4]?.querySelector(".applied-block");
        const decisionBlock = row?.children?.[5]?.querySelector(".applied-block");
        const reviewerBlock = panelId !== "pending-panel" ? row?.children?.[6]?.querySelector(".reviewer-block") : null;
        const updatedCountNode = panelId === "pending-panel"
            ? row?.children?.[5]?.querySelector("[data-relative-count]")
            : null;
        const title = reasonText.dataset.title || "Leave Reason";
        const isRejectionReason = title.toLowerCase().includes("reject");
        return {
            row,
            title: isRejectionReason ? "Rejection Reason" : "",
            reasonContext: isRejectionReason ? "rejected-note" : (statusKey === "rejected" ? "rejected-employee" : statusKey),
            leaveType,
            leaveTypeClass,
            scheduleDate: `${formatReasonModalDate(row?.dataset.fromDate)} -> ${formatReasonModalDate(row?.dataset.toDate)}`,
            scheduleTime: scheduleBlock?.querySelector(".schedule-time")?.textContent?.replace(/\s+/g, " ").trim() || "-",
            daysDisplay: `${daysBlock?.querySelector(".js-days-value")?.textContent?.trim() || "-"} ${daysBlock?.querySelector(".js-days-label")?.textContent?.trim() || ""}`.trim(),
            appliedIso: appliedBlock?.querySelector("[data-relative-datetime]")?.dataset.relativeDatetime || "",
            applied: appliedBlock?.textContent?.replace(/\s+/g, " ").trim() || "-",
            updatedIso: panelId === "pending-panel" ? (updatedCountNode?.dataset.relativeDatetime || "") : "",
            updatedCount: Number.parseInt(updatedCountNode?.dataset.relativeCount || "0", 10) || 0,
            decisionIso: panelId !== "pending-panel" ? (decisionBlock?.querySelector("[data-relative-datetime]")?.dataset.relativeDatetime || "") : "",
            decision: panelId !== "pending-panel" ? (decisionBlock?.textContent?.replace(/\s+/g, " ").trim() || "-") : "-",
            decisionLabel: statusKey === "approved" ? "Approved At" : statusKey === "rejected" ? "Rejected At" : "",
            reviewer: reviewerBlock?.textContent?.replace(/\s+/g, " ").trim() || "HR Team",
            reviewerLabel: statusKey === "approved" ? "Approved By" : statusKey === "rejected" ? "Rejected By" : ""
        };
    }
    function openReasonTextModal(titleText, reasonText, sourceElement = null)
    {
        const reasonNode = sourceElement?.closest?.(".reason-text") || sourceElement;
        if (!reasonNode) return;
        if (titleText) reasonNode.dataset.title = titleText;
        if (reasonText) reasonNode.dataset.full = reasonText;
        openReasonModal(reasonNode);
    }
    function openReasonModal(reasonText)
    {
        const modal = document.getElementById("reasonModal");
        const title = document.getElementById("reasonModalTitle");
        const content = document.getElementById("reasonModalContent");
        const employee = document.getElementById("reasonModalEmployee");
        const leaveType = document.getElementById("reasonModalLeaveType");
        const metaGrid = document.getElementById("reasonModalMetaGrid");
        const appliedLabel = document.getElementById("reasonModalAppliedLabel");
        const updatedLabel = document.getElementById("reasonModalUpdatedLabel");
        const decisionCard = document.getElementById("reasonModalDecisionCard");
        const decisionLabel = document.getElementById("reasonModalDecisionLabel");
        const reviewerCard = document.getElementById("reasonModalReviewerCard");
        const reviewerLabel = document.getElementById("reasonModalReviewerLabel");
        const scheduleDate = document.getElementById("reasonModalScheduleDate");
        const scheduleTime = document.getElementById("reasonModalScheduleTime");
        const days = document.getElementById("reasonModalDays");
        const applied = document.getElementById("reasonModalApplied");
        const appliedTime = document.getElementById("reasonModalAppliedTime");
        const updated = document.getElementById("reasonModalUpdated");
        const updatedTime = document.getElementById("reasonModalUpdatedTime");
        const decision = document.getElementById("reasonModalDecision");
        const decisionTime = document.getElementById("reasonModalDecisionTime");
        const reviewer = document.getElementById("reasonModalReviewer");
        const fieldLabel = document.getElementById("reasonModalFieldLabel");
        if (!modal || !reasonText) return;
        if (reasonModalCloseTimer)
        {
            clearTimeout(reasonModalCloseTimer);
            reasonModalCloseTimer = null;
        }
        activeReasonAnchor = reasonText.closest(".reason-box") || reasonText;
        modal.dataset.sourceLeaveId = reasonText.closest("tr.leave-row")?.dataset.leaveId || "";
        modal.dataset.sourceReasonTitle = reasonText.dataset.title || "";
        if (activeReasonAnchor && typeof activeReasonAnchor.getBoundingClientRect === "function")
        {
            const anchorRect = activeReasonAnchor.getBoundingClientRect();
            modal.style.setProperty("--reason-origin-x", (anchorRect.left + anchorRect.width / 2 - window.innerWidth / 2) + "px");
            modal.style.setProperty("--reason-origin-y", (anchorRect.top + anchorRect.height / 2 - window.innerHeight / 2) + "px");
        }
        const meta = getReasonModalRowMeta(reasonText);
        const contextLabels = {
            pending: { title: "Pending Reason", label: "Pending Reason", icon: "&#9203;" },
            approved: { title: "Approved Reason", label: "Approved Reason", icon: "&#10003;" },
            "rejected-employee": { title: "Rejected Leave Reason", label: "Employee Reason", icon: "&#128221;" },
            "rejected-note": { title: "Rejection Reason", label: "Rejection Reason", icon: "&#10006;" }
        };
        const contextCopy = contextLabels[meta.reasonContext] || contextLabels.pending;
        const hasDecision = Boolean(meta.decisionIso);
        const showScheduleTime = meta.leaveTypeClass === "short" || meta.leaveTypeClass === "half";
        title.textContent = meta.title || contextCopy.title;
        modal.classList.remove(
            "reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half", "reason-theme-default",
            "reason-context-pending", "reason-context-approved", "reason-context-rejected-employee", "reason-context-rejected-note"
        );
        modal.classList.add("reason-theme-" + meta.leaveTypeClass);
        modal.classList.add("reason-context-" + meta.reasonContext);
        employee.textContent = "My Leave";
        leaveType.textContent = meta.leaveType + " Leave";
        leaveType.className = "reason-modal-chip reason-modal-type-chip reason-modal-type-" + meta.leaveTypeClass;
        scheduleDate.textContent = meta.scheduleDate.replace(/\s*->\s*/g, " \u27F6 ");
        scheduleTime.textContent = showScheduleTime ? meta.scheduleTime.replace(/\s*->\s*/g, " \u27F6 ") : "";
        scheduleTime.hidden = !showScheduleTime;
        scheduleTime.classList.toggle("reason-modal-schedule-time-accent", showScheduleTime);
        days.textContent = meta.daysDisplay || "-";
        window.setSafeHTML(appliedLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128338;</span><span>Applied</span></span>');
        applied.textContent = formatReasonModalRelativeAge(meta.appliedIso) || meta.applied || "-";
        appliedTime.textContent = formatReasonModalClockTime(meta.appliedIso, meta.applied);
        window.setSafeHTML(updatedLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128260;</span><span>${meta.updatedCount === 1 ? "1 update" : `${meta.updatedCount} updates`}</span></span>`);
        updated.textContent = meta.updatedIso ? (formatReasonModalRelativeAge(meta.updatedIso) || "-") : "Not updated";
        updatedTime.textContent = meta.updatedIso ? formatReasonModalClockTime(meta.updatedIso, "") : "-";
        if (metaGrid) metaGrid.classList.toggle("has-decision", hasDecision);
        if (decisionCard) decisionCard.hidden = !hasDecision;
        if (reviewerCard) reviewerCard.hidden = !hasDecision;
        if (decisionLabel)
        {
            const isRejectedDecision = meta.decisionLabel.toLowerCase().includes("reject");
            window.setSafeHTML(decisionLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">${isRejectedDecision ? "&#9940;" : "&#10003;"}</span><span>${meta.decisionLabel || "Decision At"}</span></span>`);
        }
        if (decision) decision.textContent = hasDecision ? (formatReasonModalRelativeAge(meta.decisionIso) || meta.decision || "-") : "-";
        if (decisionTime) decisionTime.textContent = hasDecision ? formatReasonModalClockTime(meta.decisionIso, meta.decision) : "-";
        if (reviewerLabel)
        {
            const isRejectedReviewer = meta.reviewerLabel.toLowerCase().includes("reject");
            window.setSafeHTML(reviewerLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128100;</span><span>${meta.reviewerLabel || (isRejectedReviewer ? "Rejected By" : "Approved By")}</span></span>`);
        }
        if (reviewer) reviewer.textContent = hasDecision ? (meta.reviewer || "HR Team") : "-";
        window.setSafeHTML(fieldLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">${contextCopy.icon}</span><span>${contextCopy.label}</span></span>`);
        content.textContent = reasonText.dataset.full || reasonText.textContent || "";
        modal.classList.remove("is-closing");
        showManagedModal(modal);
        requestAnimationFrame(function ()
        {
            modal.classList.add("is-open");
        });
    }
    function closeReasonModal()
    {
        const modal = document.getElementById("reasonModal");
        const title = document.getElementById("reasonModalTitle");
        const content = document.getElementById("reasonModalContent");
        const employee = document.getElementById("reasonModalEmployee");
        const leaveType = document.getElementById("reasonModalLeaveType");
        const metaGrid = document.getElementById("reasonModalMetaGrid");
        const appliedLabel = document.getElementById("reasonModalAppliedLabel");
        const updatedLabel = document.getElementById("reasonModalUpdatedLabel");
        const decisionCard = document.getElementById("reasonModalDecisionCard");
        const decisionLabel = document.getElementById("reasonModalDecisionLabel");
        const reviewerCard = document.getElementById("reasonModalReviewerCard");
        const reviewerLabel = document.getElementById("reasonModalReviewerLabel");
        const scheduleDate = document.getElementById("reasonModalScheduleDate");
        const scheduleTime = document.getElementById("reasonModalScheduleTime");
        const days = document.getElementById("reasonModalDays");
        const applied = document.getElementById("reasonModalApplied");
        const appliedTime = document.getElementById("reasonModalAppliedTime");
        const updated = document.getElementById("reasonModalUpdated");
        const updatedTime = document.getElementById("reasonModalUpdatedTime");
        const decision = document.getElementById("reasonModalDecision");
        const decisionTime = document.getElementById("reasonModalDecisionTime");
        const reviewer = document.getElementById("reasonModalReviewer");
        const fieldLabel = document.getElementById("reasonModalFieldLabel");
        if (!modal) return;
        modal.classList.remove("is-open");
        hideManagedModal(modal, function ()
        {
            title.textContent = "Reason detail";
            content.textContent = "";
            employee.textContent = "My Leave";
            leaveType.textContent = "Leave type";
            leaveType.className = "reason-modal-chip reason-modal-type-chip reason-modal-type-default";
            if (metaGrid) metaGrid.classList.remove("has-decision");
            window.setSafeHTML(appliedLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128338;</span><span>Applied</span></span>');
            window.setSafeHTML(updatedLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128260;</span><span>0 updates</span></span>');
            if (decisionLabel) window.setSafeHTML(decisionLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#10003;</span><span>Approved At</span></span>');
            if (decisionCard) decisionCard.hidden = true;
            if (reviewerLabel) window.setSafeHTML(reviewerLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128100;</span><span>Approved By</span></span>');
            if (reviewerCard) reviewerCard.hidden = true;
            window.setSafeHTML(fieldLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128221;</span><span>Reason</span></span>');
            scheduleDate.textContent = "-";
            scheduleTime.textContent = "-";
            scheduleTime.hidden = false;
            scheduleTime.classList.remove("reason-modal-schedule-time-accent");
            days.textContent = "-";
            applied.textContent = "-";
            appliedTime.textContent = "-";
            updated.textContent = "-";
            updatedTime.textContent = "-";
            if (decision) decision.textContent = "-";
            if (decisionTime) decisionTime.textContent = "-";
            if (reviewer) reviewer.textContent = "-";
            modal.dataset.sourceLeaveId = "";
            modal.dataset.sourceReasonTitle = "";
            modal.classList.remove(
                "reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half",
                "reason-context-pending", "reason-context-approved", "reason-context-rejected-employee", "reason-context-rejected-note"
            );
            modal.classList.add("reason-theme-default");
            activeReasonAnchor = null;
            reasonModalCloseTimer = null;
        });
    }
    function getActiveReasonModalSource(modal)
    {
        const anchoredReason = activeReasonAnchor?.matches?.(".reason-text")
            ? activeReasonAnchor
            : activeReasonAnchor?.querySelector?.(".reason-text");
        if (anchoredReason && document.contains(anchoredReason)) return anchoredReason;
        const leaveId = modal?.dataset.sourceLeaveId || "";
        if (!leaveId) return null;
        const row = Array.from(document.querySelectorAll("tr.leave-row"))
            .find((candidate) => candidate.dataset.leaveId === leaveId);
        if (!row) return null;
        const sourceTitle = modal?.dataset.sourceReasonTitle || "";
        return Array.from(row.querySelectorAll(".reason-text")).find((node) => node.dataset.title === sourceTitle)
            || row.querySelector(".reason-text");
    }
    function refreshOpenReasonModalRelativeDates()
    {
        const modal = document.getElementById("reasonModal");
        if (!modal || modal.getAttribute("aria-hidden") !== "false") return;
        const reasonText = getActiveReasonModalSource(modal);
        if (!reasonText) return;
        const meta = getReasonModalRowMeta(reasonText);
        const applied = document.getElementById("reasonModalApplied");
        const updated = document.getElementById("reasonModalUpdated");
        const decision = document.getElementById("reasonModalDecision");
        if (applied) applied.textContent = formatReasonModalRelativeAge(meta.appliedIso) || meta.applied || "-";
        if (updated) updated.textContent = meta.updatedIso ? (formatReasonModalRelativeAge(meta.updatedIso) || "-") : "Not updated";
        if (decision && meta.decisionIso) decision.textContent = formatReasonModalRelativeAge(meta.decisionIso) || meta.decision || "-";
    }
    function refreshLiveRelativeDates()
    {
        hydrateRelativeDates();
        refreshOpenReasonModalRelativeDates();
    }
    window.setInterval(refreshLiveRelativeDates, 60 * 1000);
    document.addEventListener("visibilitychange", function ()
    {
        if (!document.hidden) refreshLiveRelativeDates();
    });
    document.addEventListener("keydown", function (event)
    {
        if (event.key !== "Escape") return;
        const reasonModal = document.getElementById("reasonModal");
        if (reasonModal && reasonModal.getAttribute("aria-hidden") === "false")
        {
            closeReasonModal();
        }
    });
    function setupFilterExclusivity(container) 
    {
        const monthInput = container.querySelector('input[name="month"]');
        const fromDate = container.querySelector('input[name="from_date"]');
        const toDate = container.querySelector('input[name="to_date"]');
        const monthShell = container.querySelector(".popup-filter-month-shell");
        const dateShells = Array.from(container.querySelectorAll(".popup-filter-date-shell"));
        if (!monthInput || !fromDate || !toDate) return;
        function syncPopupFilterDateInputs()
        {
            const hasMonth = !!monthInput.value;
            const hasRange = !!(fromDate.value || toDate.value);
            const parsedFromDate = fromDate.value ? new Date(fromDate.value + "T00:00:00") : null;
            const parsedToDate = toDate.value ? new Date(toDate.value + "T00:00:00") : null;
            if (parsedFromDate && parsedToDate && parsedToDate < parsedFromDate)
            {
                toDate.value = fromDate.value;
            }
            monthInput.disabled = hasRange;
            monthShell?.classList.toggle("is-disabled", hasRange);
            fromDate.disabled = hasMonth;
            dateShells[0]?.classList.toggle("is-disabled", hasMonth);
            const toDisabled = hasMonth || !fromDate.value;
            toDate.disabled = toDisabled;
            dateShells[1]?.classList.toggle("is-disabled", toDisabled);
        }
        [monthInput, fromDate, toDate].forEach((input) =>
        {
            input.addEventListener("input", syncPopupFilterDateInputs);
            input.addEventListener("change", syncPopupFilterDateInputs);
        });
        syncPopupFilterDateInputs();
    }
    function setupPopupFilterClearButtonState(filterForm)
    {
        if (!filterForm) return;
        const clearButton = filterForm.querySelector(".popup-filter-clear-btn");
        const fields = Array.from(filterForm.querySelectorAll('input[name="leave_type"], input[name="month"], input[name="from_date"], input[name="to_date"]'));
        if (!clearButton || !fields.length) return;
        const syncClearButton = () =>
        {
            const values = Object.fromEntries(fields.map((field) => [field.name, field.value]));
            clearButton.disabled = !hasActiveFilter(normalizeFilterState(values));
        };
        fields.forEach((field) =>
        {
            field.addEventListener("input", syncClearButton);
            field.addEventListener("change", syncClearButton);
        });
        syncClearButton();
    }
    function openFilterModal(status)
    {
        const modalContent = document.getElementById("modal-content");
        const sharedModal = document.getElementById("modal");
        const modalBox = document.querySelector(".modal-box");
        sharedModal?.classList.remove("popup-edit-modal-host");
        sharedModal?.classList.add("popup-filter-modal-host");
        if (modalBox)
        {
            modalBox.classList.remove("reason-modal", "compact-calendar", "expanded-calendar", "popup-edit-modal-box");
            modalBox.classList.add("popup-filter-modal-box");
        }
        modalContent.replaceChildren();
        const current = normalizeFilterState(currentFilterState[status] || {});
        const hasFilters = current.leave_type || current.month || current.from_date || current.to_date;
        const statusLabel = status.charAt(0).toUpperCase() + status.slice(1);
        const leaveTypeOptions = myLeavePopupFilterTypes.map((type) =>
        {
            return `<button type="button" class="popup-filter-leave-option custom-option" data-value="${escapeHtml(type.value)}" data-display-label="<span class=&quot;popup-filter-leave-value-symbol&quot; aria-hidden=&quot;true&quot;>${escapeHtml(type.symbol || "&#9679;")}</span><span class=&quot;popup-filter-leave-value-text&quot;>${escapeHtml(type.label)}</span>"><span class="popup-filter-leave-option-symbol" aria-hidden="true">${escapeHtml(type.symbol || "&#9679;")}</span><span class="option-title">${escapeHtml(type.label)}</span><span class="popup-filter-leave-option-check" aria-hidden="true">&#10003;</span></button>`;
        }).join("");
        const content = document.createElement("div");
        content.className = "popup-filter-modal-content";
        window.setSafeHTML(content, `
            <div class="popup-filter-modal-head">
                <p class="popup-filter-modal-eyebrow">History Filter</p>
                <div class="popup-filter-modal-title-row">
                    <span class="popup-filter-modal-title-icon" aria-hidden="true">&#128269;</span>
                    <h3>${escapeHtml(statusLabel)} Requests</h3>
                </div>
                <p class="popup-filter-modal-subtext">Filter only this section. Other tabs keep their own saved filters.</p>
                <div class="popup-filter-modal-note" role="note" aria-label="Filter note">
                    <span class="popup-filter-modal-note-icon" aria-hidden="true">!</span>
                    <div class="popup-filter-modal-note-copy">
                        <strong>Filter rule</strong>
                        <span>Use either <em>Month</em> or <em>From Date - To Date</em> at one time.</span>
                    </div>
                </div>
            </div>
            <form method="post" action="/apply-status-filter/${status}/" class="popup-filter-form">
                <input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}">
                <div class="popup-filter-grid">
                    <label class="popup-filter-field">
                        <span class="popup-filter-field-heading"><span class="popup-filter-field-heading-badge">01</span><span class="popup-filter-field-heading-icon popup-filter-field-heading-icon-leave" aria-hidden="true">&#9679;</span><span class="popup-filter-field-heading-text">Leave Type</span><span class="popup-filter-field-heading-line" aria-hidden="true"></span></span>
                        <div class="popup-filter-shell popup-filter-leave-shell custom-select select-shell leave-type-shell">
                            <input type="hidden" name="leave_type" value="${escapeHtml(current.leave_type || "")}">
                            <div class="custom-select-display"><button type="button" class="popup-filter-leave-trigger custom-select-trigger" aria-haspopup="listbox" aria-expanded="false"><span class="popup-filter-leave-value custom-select-value"><span class="popup-filter-leave-value-symbol" aria-hidden="true">&#9679;</span><span class="popup-filter-leave-value-text">All types</span></span><span class="popup-filter-leave-icon custom-select-icon" aria-hidden="true"></span></button></div>
                            <div class="popup-filter-leave-menu custom-select-menu" role="listbox"><button type="button" class="popup-filter-leave-option custom-option is-all-types" data-value="" data-display-label="<span class=&quot;popup-filter-leave-value-symbol&quot; aria-hidden=&quot;true&quot;>&#9679;</span><span class=&quot;popup-filter-leave-value-text&quot;>All types</span>"><span class="popup-filter-leave-option-symbol" aria-hidden="true">&#9679;</span><span class="option-title">All types</span><span class="popup-filter-leave-option-check" aria-hidden="true">&#10003;</span></button>${leaveTypeOptions}</div>
                        </div>
                    </label>
                    <label class="popup-filter-field">
                        <span class="popup-filter-field-heading"><span class="popup-filter-field-heading-badge">02</span><span class="popup-filter-field-heading-icon popup-filter-field-heading-icon-month" aria-hidden="true">&#128197;</span><span class="popup-filter-field-heading-text">Month</span><span class="popup-filter-field-heading-line" aria-hidden="true"></span></span>
                        <div class="popup-filter-shell popup-filter-month-shell custom-month-picker">
                            <input type="hidden" name="month" value="${escapeHtml(current.month || "")}">
                            <div class="month-display"><div class="month-trigger" role="button" tabindex="0" aria-haspopup="dialog" aria-expanded="false"><span class="month-value">Select month</span><span class="month-icon" aria-hidden="true"></span></div></div>
                            <div class="month-menu" role="dialog" aria-label="Month calendar"><div class="month-menu-header"><button type="button" class="month-nav prev-year" aria-label="Previous year">&#8249;</button><div class="month-current"></div><button type="button" class="month-nav next-year" aria-label="Next year">&#8250;</button></div><div class="month-grid"></div><div class="month-actions"><button type="button" class="month-action today-action">Current</button><button type="button" class="month-action clear-action">Clear</button></div></div>
                        </div>
                    </label>
                    <label class="popup-filter-field">
                        <span class="popup-filter-field-heading"><span class="popup-filter-field-heading-badge">03</span><span class="popup-filter-field-heading-icon popup-filter-field-heading-icon-date" aria-hidden="true">&#128198;</span><span class="popup-filter-field-heading-text">From Date</span><span class="popup-filter-field-heading-line" aria-hidden="true"></span></span>
                        <div class="popup-filter-shell popup-filter-date-shell custom-date-picker">
                            <input type="hidden" name="from_date" value="${escapeHtml(current.from_date || "")}">
                            <div class="date-display"><div class="date-trigger" role="button" tabindex="0" aria-haspopup="dialog" aria-expanded="false"><span class="date-value">dd-mm-yyyy</span><span class="date-icon" aria-hidden="true"></span></div></div>
                            <div class="date-menu" role="dialog" aria-label="From date calendar"><div class="date-menu-header"><button type="button" class="date-nav prev-month" aria-label="Previous month">&#8249;</button><div class="date-current"></div><button type="button" class="date-nav next-month" aria-label="Next month">&#8250;</button></div><div class="date-weekdays"><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span><span>Su</span></div><div class="date-grid"></div><div class="date-actions"><button type="button" class="date-action today-action">Today</button><button type="button" class="date-action clear-action">Clear</button></div></div>
                        </div>
                    </label>
                    <label class="popup-filter-field">
                        <span class="popup-filter-field-heading"><span class="popup-filter-field-heading-badge">04</span><span class="popup-filter-field-heading-icon popup-filter-field-heading-icon-date" aria-hidden="true">&#128198;</span><span class="popup-filter-field-heading-text">To Date</span><span class="popup-filter-field-heading-line" aria-hidden="true"></span></span>
                        <div class="popup-filter-shell popup-filter-date-shell custom-date-picker">
                            <input type="hidden" name="to_date" value="${escapeHtml(current.to_date || "")}">
                            <div class="date-display"><div class="date-trigger" role="button" tabindex="0" aria-haspopup="dialog" aria-expanded="false"><span class="date-value">dd-mm-yyyy</span><span class="date-icon" aria-hidden="true"></span></div></div>
                            <div class="date-menu" role="dialog" aria-label="To date calendar"><div class="date-menu-header"><button type="button" class="date-nav prev-month" aria-label="Previous month">&#8249;</button><div class="date-current"></div><button type="button" class="date-nav next-month" aria-label="Next month">&#8250;</button></div><div class="date-weekdays"><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span><span>Su</span></div><div class="date-grid"></div><div class="date-actions"><button type="button" class="date-action today-action">Today</button><button type="button" class="date-action clear-action">Clear</button></div></div>
                        </div>
                    </label>
                </div>
                <div class="popup-filter-actions"><button type="submit" class="popup-filter-clear-btn clear-btn" formaction="/clear-status-filter/${status}/" formmethod="post" ${!hasFilters ? "disabled" : ""}>Clear All Filter</button><button type="submit" class="popup-filter-apply-btn apply-btn">Apply Filter</button></div>
            </form>
        `);
        modalContent.appendChild(content);
        const filterForm = content.querySelector(".popup-filter-form");
        if (filterForm)
        {
            filterForm.onsubmit = async function (event)
            {
                event.preventDefault();
                const submitter = event.submitter;
                const actionUrl = submitter?.formAction || filterForm.action;
                const submitMethod = (submitter?.formMethod || filterForm.method || "post").toUpperCase();
                const isResetAction = submitter?.classList.contains("clear-btn");
                if (isResetAction)
                {
                    const shouldClear = typeof window.showThemeConfirm === "function"
                        ? await window.showThemeConfirm(`Are you sure you want to clear all filters for ${status} Leaves Section?`, {
                            title: "Clear filters",
                            confirmText: "Clear filters",
                            variant: "confirm"
                        })
                        : window.confirm(`Are you sure you want to clear all filters for ${status} Leaves Section?`);
                    if (!shouldClear) return false;
                }
                const submitBtn = submitter instanceof HTMLButtonElement ? submitter : null;
                if (submitBtn) submitBtn.disabled = true;
                const response = await fetch(actionUrl, {
                    method: submitMethod,
                    headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": getCSRFToken() },
                    body: new FormData(filterForm),
                    credentials: "same-origin",
                    cache: "no-store"
                });
                const payload = await parseAjaxResponseLenient(response, isResetAction ? "Filters cleared." : "Filter applied.");
                if (submitBtn) submitBtn.disabled = false;
                const formData = new FormData(filterForm);
                const normalizedMonth = normalizePopupFilterMonthValue(String(formData.get("month") || ""));
                const nextState = { ...currentFilterState };
                const normalized = normalizeFilterState({
                    leave_type: formData.get("leave_type"),
                    month: normalizedMonth,
                    from_date: formData.get("from_date"),
                    to_date: formData.get("to_date"),
                });
                if (isResetAction || !hasActiveFilter(normalized)) delete nextState[status];
                else nextState[status] = normalized;
                setCurrentFilterState(nextState);
                applyFilterStateToPanel(status);
                showAjaxMessages(payload.messages);
                if (!response.ok || payload.success === false) return false;
                if (typeof closeModal === "function") closeModal();
                return false;
            };
        }
        buildMyLeavePopupFilterLeaveType(content.querySelector(".popup-filter-leave-shell"));
        buildMyLeavePopupFilterMonthPicker(content.querySelector(".popup-filter-month-shell"));
        content.querySelectorAll(".popup-filter-date-shell").forEach((shell) => buildMyLeavePopupFilterDatePicker(shell));
        setupFilterExclusivity(content);
        setupPopupFilterClearButtonState(filterForm);
        openModal();
    }

    window.openLeaveCalendar = openLeaveCalendar;
    window.closeCalendarDetail = closeCalendarDetail;
    window.openEditLeave = openEditLeave;
    window.openFilterModal = openFilterModal;
