const employeeData = JSON.parse(document.getElementById("employee-data").textContent);
    const manageAllConfigElement = document.getElementById("manage-all-js-config");
    const manageAllConfig = manageAllConfigElement ? manageAllConfigElement.dataset : {};
    const csrfToken = manageAllConfig.csrfToken || "";
    const defaultProfileImage = manageAllConfig.defaultProfileImage || "";
    const manageEmployeeDetailApiTemplate = manageAllConfig.employeeDetailUrlTemplate || "";
    const manageSummaryApiUrl = manageAllConfig.summaryUrl || "";
    const approveLeaveUrlTemplate = manageAllConfig.approveLeaveUrlTemplate || "";
    const rejectLeaveUrlTemplate = manageAllConfig.rejectLeaveUrlTemplate || "";
    const popupTableSection = document.getElementById("popupTableSection");
    const popupTableToggle = document.getElementById("togglePopupTable");
    const popupTableToggleLabel = document.getElementById("togglePopupTableLabel");
    const popupHistoryTabs = Array.from(document.querySelectorAll(".popup-history-tab"));
    const popupFilterButton = document.getElementById("openPopupFilterBtn");
    const popupFilterButtonCount = document.getElementById("popupFilterBtnCount");
    const popupFilterBadges = document.getElementById("popupFilterBadges");
    const popupTableWrapper = document.getElementById("popupTableWrapper");
    const popupTableInner = popupTableWrapper ? popupTableWrapper.querySelector(".compact-table-inner") : null;
    const popupTablePagination = document.getElementById("popupTablePagination");
    const detailHistoryTable = document.getElementById("detailHistoryTable");
    const detailTableHead = document.getElementById("detailTableHead");
    const sharedModalContent = document.getElementById("modal-content");
    const employeeModalDialog = document.querySelector("#employeeModal .employee-modal-dialog");
    const manageEmployeeDirectory = document.getElementById("manageEmployeeDirectory");
    const employeeSearchInput = document.getElementById("employeeSearchInput");
    const employeeSearchEmpty = document.getElementById("employeeSearchEmpty");
    const employeeCountBadge = document.querySelector(".employee-count-badge");
    const manageDirectoryPagination = document.getElementById("manageDirectoryPagination");
    const employeeSummaryPanel = document.getElementById("employeeSummaryPanel");
    const mobileSummaryTabs = Array.from(document.querySelectorAll(".mobile-summary-tab"));
    const employeeBellDropdowns = Array.from(document.querySelectorAll("[data-employee-bell]"));
    const employeeProfileCards = Array.from(document.querySelectorAll(".employee-profile-card:not(.employee-profile-card-placeholder)"));
    const employeePlaceholderCards = Array.from(document.querySelectorAll(".employee-profile-card-placeholder"));
    const manageSummaryMetrics = {
        pending: document.querySelector('[data-manage-summary-metric="pending"]'),
        approved: document.querySelector('[data-manage-summary-metric="approved"]'),
        rejected: document.querySelector('[data-manage-summary-metric="rejected"]')
    };
    let manageDirectoryCurrentPage = 1;
    let manageDirectoryLastPageSize = null;
    let manageDirectoryAnimationTimer = null;
    let pendingHighlightEmployeeId = "";
    let pendingHighlightLeaveId = "";
    const notificationDropdown = document.querySelector(".notification-dropdown[data-notification-api]");
    const notificationApiUrl = notificationDropdown ? notificationDropdown.dataset.notificationApi || "" : "";
    const notificationUserKey = notificationDropdown ? notificationDropdown.dataset.notificationUserKey || notificationApiUrl || "anonymous" : "";
    const employeeBellState = {
        notifications: [],
        readIds: new Set(),
        highlightedIds: new Set()
    };
    let hasAnimatedEmployeeBellInitialCount = false;
    let employeeModalFetchToken = 0;
    let activePopupHistoryStatus = "pending";
    let currentEmployeeDetail = null;
    let currentRejectLeaveId = null;
    let currentRejectLeaveSnapshot = null;
    let popupActionInFlight = false;
    let popupFilterOwnerId = "";
    const employeeCardRefreshInFlight = new Set();
    let pendingEmployeeCardPhotoReload = false;
    let reasonModalCloseTimer = null;
    let decisionConfirmState = null;
    let activeReasonAnchor = null;
    const popupLeaveTypeMeta = [
        { key: "short", label: "Short (2 Hours)", symbol: "\u23F1" },
        { key: "half", label: "Half (4 Hours)", symbol: "\u25D0" },
        { key: "sick", label: "Sick", symbol: "\u271A" },
        { key: "earned", label: "Earned", symbol: "\u2726" },
        { key: "unpaid", label: "Unpaid", symbol: "\u25C8" }
    ];
    const popupHistoryFilters = {
        pending: createEmptyPopupHistoryFilter(),
        approved: createEmptyPopupHistoryFilter(),
        rejected: createEmptyPopupHistoryFilter()
    };
    const popupHistoryPages = {
        pending: 1,
        approved: 1,
        rejected: 1
    };
    const POPUP_HISTORY_PAGE_SIZE = 5;
    const POPUP_HISTORY_MOBILE_PAGE_SIZE = 4;

    function getPopupHistoryPageSize()
    {
        return window.matchMedia && window.matchMedia("(max-width: 640px)").matches
            ? POPUP_HISTORY_MOBILE_PAGE_SIZE
            : POPUP_HISTORY_PAGE_SIZE;
    }

    function syncPopupTabFilterIndicators()
    {
        const statuses = ["pending", "approved", "rejected"];
        statuses.forEach(function (status)
        {
            const filters = popupHistoryFilters[status];
            const tab = document.querySelector(`.popup-history-tab[data-history-status="${status}"]`);

            if (!tab)
            {
                return;
            }

            const hasActiveFilter = !!(filters.leave_type || filters.month || filters.from_date || filters.to_date);
            tab.classList.toggle("has-filter", hasActiveFilter);
        });
    }

    function ensureFlashMessagesContainer()
    {
        let container = document.getElementById("flash-messages");

        if (!container)
        {
            container = document.createElement("div");
            container.id = "flash-messages";
            document.body.appendChild(container);
        }

        return container;
    }

    function dismissFlashMessage(flash)
    {
        if (!flash || flash.dataset.closing === "true")
        {
            return;
        }

        flash.dataset.closing = "true";
        flash.classList.add("flash-exit");
        setTimeout(function ()
        {
            if (flash.parentNode)
            {
                flash.parentNode.removeChild(flash);
            }
        }, 220);
    }

    function renderFlashMessages(messages)
    {
        if (!Array.isArray(messages) || !messages.length)
        {
            return;
        }

        const container = ensureFlashMessagesContainer();

        messages.forEach(function (message, index)
        {
            const tags = String(message && message.tags ? message.tags : "").trim();
            const title = String(message && message.title ? message.title : "Update");
            const text = String(message && message.text ? message.text : "").trim();

            if (!text)
            {
                return;
            }

            const flash = document.createElement("div");
            flash.className = "flash" + (tags ? " flash-" + tags : "");
            flash.setAttribute("data-flash", "");
            flash.innerHTML = [
                '<span class="flash-accent" aria-hidden="true"></span>',
                '<span class="flash-icon" aria-hidden="true"></span>',
                '<div class="flash-copy">',
                '<strong class="flash-title"></strong>',
                '<p></p>',
                '</div>',
                '<button type="button" class="flash-dismiss" aria-label="Dismiss message">&times;</button>'
            ].join("");

            flash.querySelector(".flash-title").textContent = title;
            flash.querySelector("p").textContent = text;

            const dismissBtn = flash.querySelector(".flash-dismiss");
            if (dismissBtn)
            {
                dismissBtn.addEventListener("click", function ()
                {
                    dismissFlashMessage(flash);
                });
            }

            container.appendChild(flash);

            setTimeout(function ()
            {
                dismissFlashMessage(flash);
            }, 4200 + index * 250);
        });
    }

    const popupHistoryDefinitions = {
        pending: {
            heading: "Pending Requests",
            countSuffix: " Pending Requests",
            emptyTitle: "No pending requests",
            emptyMessage: "No pending leave requests are available for this employee yet.",
            themeClass: "cosmic-pending",
            emptyIcon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" class="cosmic-icon-timer">
                <circle cx="12" cy="12" r="10" opacity="0.15" stroke-dasharray="4 4" />
                <path d="M12 2v2M22 12h-2M12 22v-2M2 12h2" opacity="0.3" />
                <line x1="12" y1="12" x2="12" y2="5" class="cosmic-clock-hand-min" opacity="0.7" />
                <line x1="12" y1="12" x2="16" y2="14" class="cosmic-clock-hand-hour" opacity="0.9" />
                <circle cx="12" cy="12" r="1" fill="currentColor">
                    <animate attributeName="opacity" values="1;0.2;1" dur="2s" repeatCount="indefinite" />
                </circle>
            </svg>`,
            columns: [
                { key: "serial", label: "#" },
                { key: "type", label: "Type" },
                { key: "schedule", label: "Schedule" },
                { key: "days", label: "Days" },
                { key: "applied", label: "Applied At" },
                { key: "decision", label: "Updated At" },
                { key: "reason", label: "Reason" },
                { key: "action", label: "Action" }
            ]
        },
        approved: {
            heading: "Approved Requests",
            countSuffix: " Approved Requests",
            emptyTitle: "No approved requests",
            emptyMessage: "No approved leave requests are available for this employee yet.",
            themeClass: "cosmic-approved",
            emptyIcon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" class="cosmic-icon-shield">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" class="cosmic-shield-base" opacity="0.2" />
                <path d="m9 12 2 2 4-4" class="cosmic-checkmark" stroke-width="2.5" opacity="0.9" />
                <g class="cosmic-sparkles">
                    <circle cx="18" cy="6" r="0.5" class="cosmic-star s1" fill="currentColor" />
                    <circle cx="6" cy="18" r="0.5" class="cosmic-star s2" fill="currentColor" />
                    <circle cx="4" cy="7" r="0.5" class="cosmic-star s3" fill="currentColor" />
                </g>
            </svg>`,
            columns: [
                { key: "serial", label: "#" },
                { key: "type", label: "Type" },
                { key: "schedule", label: "Schedule" },
                { key: "days", label: "Days" },
                { key: "applied", label: "Applied At" },
                { key: "decision", label: "Approved At" },
                { key: "reviewer", label: "Approved By" },
                { key: "reason", label: "Reason" }
            ]
        },
        rejected: {
            heading: "Rejected Requests",
            countSuffix: " Rejected Requests",
            emptyTitle: "No rejected requests",
            emptyMessage: "No rejected leave requests are available for this employee yet.",
            themeClass: "cosmic-rejected",
            emptyIcon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" class="cosmic-icon-off">
                <circle cx="12" cy="12" r="10" class="cosmic-off-ring" stroke-dasharray="3 3" opacity="0.15" />
                <circle cx="12" cy="12" r="8" opacity="0.05" />
                <path d="m15 9-6 6M9 9l6 6" class="cosmic-cross" stroke-width="2.5" opacity="0.9" />
                <g class="cosmic-ash">
                    <circle cx="12" cy="4" r="0.4" class="cosmic-drift d1" fill="currentColor" opacity="0.3" />
                    <circle cx="20" cy="16" r="0.3" class="cosmic-drift d2" fill="currentColor" opacity="0.2" />
                </g>
            </svg>`,
            columns: [
                { key: "serial", label: "#" },
                { key: "type", label: "Type" },
                { key: "schedule", label: "Schedule" },
                { key: "days", label: "Days" },
                { key: "applied", label: "Applied At" },
                { key: "decision", label: "Rejected At" },
                { key: "reviewer", label: "Rejected By" },
                { key: "reason", label: "Reason" },
                { key: "rejection", label: "Rejection Reason" }
            ]
        }
    };

    function getPopupHistoryHeaderIcon(key)
    {
        const iconMap = {
            serial: "&#8470;",
            type: "&#127991;",
            schedule: "&#128197;",
            days: "&#9203;",
            applied: "&#128338;",
            decision: "&#10003;",
            reviewer: "&#128100;",
            reason: "&#128221;",
            rejection: "&#9940;",
            action: "&#9881;"
        };

        return iconMap[String(key || "").toLowerCase()] || "&#9679;";
    }

    function getManageDirectoryPageSize()
    {
        return window.matchMedia("(max-width: 640px)").matches ? 9 : 8;
    }

    function getManageEmployeeDetailApiUrl(employeeId)
    {
        return manageEmployeeDetailApiTemplate.replace(/0\/?$/, String(employeeId) + "/");
    }

    function createEmptyPopupHistoryFilter()
    {
        return {
            leave_type: "",
            month: "",
            from_date: "",
            to_date: ""
        };
    }

    function clonePopupHistoryFilter(filterState)
    {
        return Object.assign(createEmptyPopupHistoryFilter(), filterState || {});
    }

    function resetPopupHistoryFilters()
    {
        popupHistoryFilters.pending = createEmptyPopupHistoryFilter();
        popupHistoryFilters.approved = createEmptyPopupHistoryFilter();
        popupHistoryFilters.rejected = createEmptyPopupHistoryFilter();
        popupHistoryPages.pending = 1;
        popupHistoryPages.approved = 1;
        popupHistoryPages.rejected = 1;
    }

    function getPopupFilterState(status)
    {
        const key = String(status || "").toLowerCase();
        return popupHistoryFilters[key] || createEmptyPopupHistoryFilter();
    }

    function getPopupHistoryPage(status)
    {
        const key = String(status || "").toLowerCase();
        return popupHistoryPages[key] || 1;
    }

    function setPopupHistoryPage(status, page)
    {
        const key = String(status || "").toLowerCase();
        popupHistoryPages[key] = Math.max(1, Number(page) || 1);
    }

    function hasPopupFilterState(status)
    {
        const state = getPopupFilterState(status);
        return !!(state.leave_type || state.month || state.from_date || state.to_date);
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

    function getPopupStatusLeaves(selected, status)
    {
        return (selected.leaves || []).filter(function (leave)
        {
            return String(leave.status || "").toLowerCase() === status;
        });
    }

    function applyPopupHistoryFilters(leaves, status)
    {
        const state = getPopupFilterState(status);

        return (leaves || []).filter(function (leave)
        {
            const leaveType = String(leave.type || "").toLowerCase();
            const fromDate = parsePopupLeaveDate(leave.from_date);
            const toDate = parsePopupLeaveDate(leave.to_date) || fromDate;

            if (state.leave_type && leaveType !== String(state.leave_type).toLowerCase())
            {
                return false;
            }

            if (state.month && fromDate)
            {
                const leaveMonth = `${fromDate.getFullYear()}-${String(fromDate.getMonth() + 1).padStart(2, "0")}`;

                if (leaveMonth !== state.month)
                {
                    return false;
                }
            }

            if ((state.from_date || state.to_date) && fromDate)
            {
                const filterFrom = state.from_date ? new Date(`${state.from_date}T00:00:00`) : null;
                const filterTo = state.to_date ? new Date(`${state.to_date}T23:59:59`) : null;

                if (filterFrom && toDate && toDate < filterFrom)
                {
                    return false;
                }

                if (filterTo && fromDate > filterTo)
                {
                    return false;
                }
            }

            return true;
        });
    }

    function getPopupFilterLeaveTypeOptions(status)
    {
        if (!currentEmployeeDetail)
        {
            return [];
        }

        const availableKeys = new Set();
        const fallbackTypes = [];
        const seenFallback = new Set();

        (currentEmployeeDetail.leaves || []).forEach(function (leave)
        {
            const key = String(leave.type || "");
            const normalized = key.trim().toLowerCase();

            if (!key)
            {
                return;
            }

            const knownType = popupLeaveTypeMeta.find(function (item)
            {
                return normalized.includes(item.key);
            });

            if (knownType)
            {
                availableKeys.add(knownType.key);
                return;
            }

            if (!seenFallback.has(normalized))
            {
                seenFallback.add(normalized);
                fallbackTypes.push({
                    value: key,
                    label: key
                });
            }
        });

        const orderedKnownTypes = popupLeaveTypeMeta
            .filter(function (item)
            {
                return availableKeys.has(item.key);
            })
            .map(function (item)
            {
                return {
                    value: item.label.split(" (")[0],
                    label: item.label,
                    symbol: item.symbol
                };
            });

        return orderedKnownTypes.concat(fallbackTypes);
    }

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
        return monthIndex >= 0 && monthIndex < monthNames.length
            ? `${monthNames[monthIndex]} ${parts[0]}`
            : monthValue;
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
            jan: 1,
            january: 1,
            feb: 2,
            february: 2,
            mar: 3,
            march: 3,
            apr: 4,
            april: 4,
            may: 5,
            jun: 6,
            june: 6,
            jul: 7,
            july: 7,
            aug: 8,
            august: 8,
            sep: 9,
            sept: 9,
            september: 9,
            oct: 10,
            october: 10,
            nov: 11,
            november: 11,
            dec: 12,
            december: 12
        };

        const month = monthMap[monthKey];

        if (!Number.isFinite(year) || !month)
        {
            return rawValue;
        }

        return `${year}-${String(month).padStart(2, "0")}`;
    }

    function buildPopupFilterMonthPicker(shell)
    {
        if (!shell || shell.dataset.bound === "true")
        {
            return;
        }

        const hiddenInput = shell.querySelector('input[type="hidden"]');
        const trigger = shell.querySelector(".month-trigger");
        const valueNode = shell.querySelector(".month-value");
        const menu = shell.querySelector(".month-menu");
        const currentNode = shell.querySelector(".month-current");
        const grid = shell.querySelector(".month-grid");
        const prevButton = shell.querySelector(".prev-year");
        const nextButton = shell.querySelector(".next-year");
        const clearButton = shell.querySelector(".clear-action");
        const currentButton = shell.querySelector(".today-action");

        if (!hiddenInput || !trigger || !valueNode || !menu || !currentNode || !grid)
        {
            return;
        }

        const getMonthFromHidden = function ()
        {
            // Accept both property and attribute; normalize legacy values like "Apr 2026".
            const raw = hiddenInput.value || hiddenInput.getAttribute("value") || "";
            const normalized = normalizePopupFilterMonthValue(raw);
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

            // Keep the input property in sync so subsequent reads are deterministic.
            hiddenInput.value = normalized;
            return { year: year, month: month };
        };

        const initialHidden = getMonthFromHidden();

        const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        let viewYear = null;
        let manualYear = false;
        let openedAt = 0;
        let menuPortal = null;
        let menuPortalContent = null;
        let menuPortalShell = null;
        const originalMenuParent = menu.parentNode;
        const originalMenuNextSibling = menu.nextSibling;

        const getToday = function ()
        {
            const parts = String(manageAllConfig.currentMonth || "").split("-");
            const serverYear = Number(parts[0]);
            const serverMonth = Number(parts[1]);

            if (Number.isFinite(serverYear) && Number.isFinite(serverMonth) && serverYear > 2000)
            {
                return { year: serverYear, month: serverMonth };
            }

            const now = new Date();
            return { year: now.getFullYear(), month: now.getMonth() + 1 };
        };

        const formatMonthValue = function (year, month)
        {
            return String(year) + "-" + String(month).padStart(2, "0");
        };

        const getSelected = function ()
        {
            return getMonthFromHidden();
        };

        const getSelectedOrToday = function ()
        {
            return getSelected() || getToday();
        };

        const syncDisplay = function ()
        {
            const activeValue = hiddenInput.value;
            valueNode.textContent = formatPopupFilterMonth(activeValue) || "Select month";
            shell.parentElement.classList.toggle("has-value", !!activeValue);
        };

        const forceViewYearFromHidden = function ()
        {
            const selected = getSelected();
            if (!selected)
            {
                return;
            }

            // Unless the user manually navigated with arrows, always align the menu year to the selected field value.
            if (!manualYear)
            {
                viewYear = selected.year;
                currentNode.textContent = String(viewYear);
            }
        };

        const close = function ()
        {
            const wasOpenUp = shell.classList.contains("open-up");
            shell.classList.remove("open");
            trigger.setAttribute("aria-expanded", "false");
            restoreMenu();
            viewYear = null;
            manualYear = false;
            openedAt = 0;
            window.clearTimeout(shell._closeTimer);
            shell._closeTimer = window.setTimeout(function ()
            {
                if (!shell.classList.contains("open"))
                {
                    shell.classList.remove("open-up");
                }
            }, wasOpenUp ? 230 : 10);
            syncDisplay();
        };

        const mountMenu = function (openUp)
        {
            if (!menuPortal)
            {
                menuPortal = document.createElement("div");
                menuPortal.className = "popup-filter-menu-portal";
                menuPortalContent = document.createElement("div");
                menuPortalContent.className = "popup-filter-modal-content popup-filter-menu-portal-content";
                menuPortalShell = document.createElement("div");
                menuPortalShell.className = "popup-filter-month-shell custom-month-picker";
                menuPortalContent.appendChild(menuPortalShell);
                menuPortal.appendChild(menuPortalContent);
            }

            menuPortalShell.classList.toggle("open-up", !!openUp);
            menuPortalShell.classList.add("open");
            if (!menuPortal.isConnected)
            {
                document.body.appendChild(menuPortal);
            }
            if (menu.parentNode !== menuPortalShell)
            {
                menuPortalShell.appendChild(menu);
            }
            shell._restorePopupMenu = restoreMenu;
        };

        function restoreMenu()
        {
            menu.style.removeProperty("--popup-month-menu-left");
            menu.style.removeProperty("--popup-month-menu-top");
            menu.style.removeProperty("--popup-month-menu-bottom");
            menu.style.maxHeight = "";
            menu.style.overflowY = "";
            if (menuPortalShell)
            {
                menuPortalShell.classList.remove("open", "open-up", "is-positioning");
            }
            if (originalMenuParent && menu.parentNode !== originalMenuParent)
            {
                originalMenuParent.insertBefore(menu, originalMenuNextSibling);
            }
            if (menuPortal && menuPortal.parentNode)
            {
                menuPortal.parentNode.removeChild(menuPortal);
            }
            delete shell._restorePopupMenu;
        }

        const positionMenu = function (openUp)
        {
            const viewportPadding = 12;
            const menuGap = 2;
            const shellRect = shell.getBoundingClientRect();
            const menuRect = menu.getBoundingClientRect();
            const menuWidth = menuRect.width || menu.offsetWidth || menu.scrollWidth || 282;
            const menuHeight = menuRect.height || menu.offsetHeight || menu.scrollHeight || 176;
            const maxLeft = Math.max(viewportPadding, window.innerWidth - viewportPadding - menuWidth);
            const preferredLeft = shellRect.right - menuWidth;
            const left = Math.min(Math.max(viewportPadding, preferredLeft), maxLeft);
            const top = shellRect.bottom + menuGap;
            const bottom = Math.max(viewportPadding, window.innerHeight - shellRect.top + menuGap);

            menu.style.setProperty("--popup-month-menu-left", left + "px");
            if (openUp)
            {
                menu.style.setProperty("--popup-month-menu-top", "auto");
                menu.style.setProperty("--popup-month-menu-bottom", bottom + "px");
            }
            else
            {
                menu.style.setProperty("--popup-month-menu-top", top + "px");
                menu.style.setProperty("--popup-month-menu-bottom", "auto");
            }
        };

        const render = function ()
        {
            const selected = getSelected();
            const today = getToday();

            // Only set viewYear if it hasn't been set yet (null after close or first init).
            // Callers (open, prev, next, current, clear) are responsible for setting viewYear.
            if (!Number.isFinite(viewYear))
            {
                viewYear = selected ? selected.year : today.year;
            }

            currentNode.textContent = String(viewYear);
            grid.replaceChildren();

            monthLabels.forEach(function (label, index)
            {
                const monthNumber = index + 1;
                const button = document.createElement("button");
                button.type = "button";
                button.className = "month-option";
                button.textContent = label;

                if (viewYear === today.year && monthNumber === today.month)
                {
                    button.classList.add("is-current");
                }

                if (selected && viewYear === selected.year && monthNumber === selected.month)
                {
                    button.classList.add("is-selected");
                }

                button.addEventListener("click", function (e)
                {
                    e.stopPropagation();
                    hiddenInput.value = formatMonthValue(viewYear, monthNumber);
                    syncDisplay();
                    hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                    hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
                    close();
                });

                grid.appendChild(button);
            });
        };

        const open = function ()
        {
            if (hiddenInput.disabled || shell.classList.contains("is-disabled"))
            {
                return;
            }

            const isOpen = shell.classList.contains("open");

            if (isOpen)
            {
                close();
                return;
            }

            document.querySelectorAll(".popup-filter-month-shell.open, .popup-filter-date-shell.open, .popup-filter-leave-shell.open").forEach(function (openShell)
            {
                openShell.classList.remove("open");
                openShell.classList.remove("open-up");
                if (typeof openShell._restorePopupMenu === "function")
                {
                    openShell._restorePopupMenu();
                }
                const openTrigger = openShell.querySelector(".month-trigger, .date-trigger, .popup-filter-leave-trigger");
                if (openTrigger)
                {
                    openTrigger.setAttribute("aria-expanded", "false");
                }
            });

            manualYear = false;

            // Normalize any legacy values like "Apr 2026" ? "2026-04"
            getMonthFromHidden();

            // Set viewYear from the selected value or current year (do NOT auto-seed the hidden input,
            // otherwise the mutual exclusion with date pickers deadlocks)
            var nowForYear = new Date();
            var currentYear = nowForYear.getFullYear();
            var selected = getMonthFromHidden();
            viewYear = (selected && Number.isFinite(selected.year)) ? selected.year : currentYear;

            // Record open timestamp to guard against phantom clicks on nav buttons
            openedAt = Date.now();
            window.clearTimeout(shell._closeTimer);

            const menuHeight = menu.getBoundingClientRect().height || menu.offsetHeight || menu.scrollHeight || 176;
            const shellRect = shell.getBoundingClientRect();
            const viewportPadding = 18;
            const openUp = true;

            shell.classList.add("is-positioning");
            shell.classList.toggle("open-up", openUp);
            mountMenu(openUp);
            positionMenu(openUp);
            shell.offsetHeight;
            shell.classList.add("open");
            trigger.setAttribute("aria-expanded", "true");
            syncDisplay();
            render();
            positionMenu(openUp);
            requestAnimationFrame(function ()
            {
                shell.classList.remove("is-positioning");
                positionMenu(openUp);
                requestAnimationFrame(function ()
                {
                    if (shell.classList.contains("open"))
                    {
                        positionMenu(openUp);
                    }
                });
            });

            // Force the header text AFTER render, as an absolute safety net
            currentNode.textContent = String(viewYear);
        };

        trigger.addEventListener("click", function (e)
        {
            e.stopPropagation();
            open();
        });
        menu.addEventListener("click", function (e)
        {
            e.stopPropagation();
        });
        trigger.addEventListener("keydown", function (event)
        {
            if (event.key === "Enter" || event.key === " ")
            {
                event.preventDefault();
                open();
            }
        });

        if (prevButton)
        {
            prevButton.addEventListener("click", function (e)
            {
                e.stopPropagation();
                // Ignore phantom clicks that fire immediately after the calendar opens
                // (the prev button can land under the cursor when the panel appears)
                if (Date.now() - openedAt < 300) { return; }
                const baseYear = Number.isFinite(viewYear) ? viewYear : getSelectedOrToday().year;
                viewYear = baseYear - 1;
                manualYear = true;
                render();
            });
        }

        if (nextButton)
        {
            nextButton.addEventListener("click", function (e)
            {
                e.stopPropagation();
                // Ignore phantom clicks that fire immediately after the calendar opens
                if (Date.now() - openedAt < 300) { return; }
                const baseYear = Number.isFinite(viewYear) ? viewYear : getSelectedOrToday().year;
                viewYear = baseYear + 1;
                manualYear = true;
                render();
            });
        }

        if (currentButton)
        {
            currentButton.addEventListener("click", function (e)
            {
                e.stopPropagation();
                const today = getToday();
                manualYear = false;
                viewYear = today.year;
                hiddenInput.value = formatMonthValue(today.year, today.month);
                syncDisplay();
                render();
                hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
            });
        }

        if (clearButton)
        {
            clearButton.addEventListener("click", function (e)
            {
                e.stopPropagation();
                manualYear = false;
                hiddenInput.value = "";
                viewYear = getToday().year;
                syncDisplay();
                render();
                hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
            });
        }

        hiddenInput.addEventListener("input", function ()
        {
            if (!shell.classList.contains("open"))
            {
                syncDisplay();
                return;
            }
            forceViewYearFromHidden();
            syncDisplay();
            render();
        });

        hiddenInput.addEventListener("change", function ()
        {
            if (!shell.classList.contains("open"))
            {
                syncDisplay();
                return;
            }
            forceViewYearFromHidden();
            syncDisplay();
            render();
        });

        document.addEventListener("click", function (event)
        {
            if (!shell.contains(event.target) && !menu.contains(event.target))
            {
                close();
            }
        });

        shell.dataset.bound = "true";
        if (initialHidden)
        {
            viewYear = initialHidden.year;
        }
        syncDisplay();
        render();
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

    function showPopupFilterPointWarning(shell, message)
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
        field._popupFilterWarningTimer = window.setTimeout(function ()
        {
            warning.hidden = true;
            field.classList.remove("has-point-warning");
            shell.classList.remove("is-warning");
        }, 2600);
    }

    function buildPopupFilterDatePicker(shell)
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
        let menuPortal = null;
        let menuPortalContent = null;
        let menuPortalShell = null;
        const originalMenuParent = menu.parentNode;
        const originalMenuNextSibling = menu.nextSibling;

        const parseValueDate = function (value)
        {
            if (!value)
            {
                return null;
            }

            const parts = String(value).split("-");
            if (parts.length !== 3)
            {
                return null;
            }

            const parsed = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
            return Number.isNaN(parsed.getTime()) ? null : parsed;
        };

        const formatValueDate = function (date)
        {
            return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0");
        };

        const getTodayDate = function ()
        {
            const browserToday = new Date();
            const normalizedBrowserToday = new Date(browserToday.getFullYear(), browserToday.getMonth(), browserToday.getDate());
            const parts = String(manageAllConfig.today || "").split("-");
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

        const getMinimumSelectableDate = function ()
        {
            const form = hiddenInput.form || shell.closest("form");

            if (hiddenInput.name === "to_date" && form)
            {
                const fromInput = form.querySelector('input[name="from_date"]');
                const fromDate = parseValueDate(fromInput ? fromInput.value : "");

                if (fromDate)
                {
                    return new Date(fromDate.getFullYear(), fromDate.getMonth(), fromDate.getDate());
                }
                return getTodayDate();
            }

            return null;
        };

        const getPreferredOpenDate = function ()
        {
            const today = getTodayDate();
            const minimumDate = getMinimumSelectableDate();

            if (hiddenInput.name === "from_date")
            {
                return today;
            }

            if (minimumDate && today < minimumDate)
            {
                return minimumDate;
            }

            return today;
        };

        const getViewDate = function ()
        {
            const selectedDate = parseValueDate(hiddenInput.value);
            const sourceDate = hiddenInput.name === "from_date"
                ? getPreferredOpenDate()
                : (selectedDate || getPreferredOpenDate());
            return new Date(sourceDate.getFullYear(), sourceDate.getMonth(), 1);
        };

        const sync = function ()
        {
            valueNode.textContent = formatPopupFilterDisplayDate(hiddenInput.value);
            shell.parentElement.classList.toggle("has-value", !!hiddenInput.value);
        };

        const close = function ()
        {
            const wasOpenUp = shell.classList.contains("open-up");
            shell.classList.remove("open");
            trigger.setAttribute("aria-expanded", "false");
            restoreMenu();
            delete shell.dataset.previewValue;
            delete shell._viewDate;
            window.clearTimeout(shell._closeTimer);
            shell._closeTimer = window.setTimeout(function ()
            {
                if (!shell.classList.contains("open"))
                {
                    shell.classList.remove("open-up");
                }
            }, wasOpenUp ? 230 : 10);
        };

        const mountMenu = function (openUp)
        {
            if (!menuPortal)
            {
                menuPortal = document.createElement("div");
                menuPortal.className = "popup-filter-menu-portal";
                menuPortalContent = document.createElement("div");
                menuPortalContent.className = "popup-filter-modal-content popup-filter-menu-portal-content";
                menuPortalShell = document.createElement("div");
                menuPortalShell.className = "popup-filter-date-shell custom-date-picker";
                menuPortalContent.appendChild(menuPortalShell);
                menuPortal.appendChild(menuPortalContent);
            }

            menuPortalShell.classList.toggle("open-up", !!openUp);
            menuPortalShell.classList.add("open");
            if (!menuPortal.isConnected)
            {
                document.body.appendChild(menuPortal);
            }
            if (menu.parentNode !== menuPortalShell)
            {
                menuPortalShell.appendChild(menu);
            }
            shell._restorePopupMenu = restoreMenu;
        };

        function restoreMenu()
        {
            menu.style.removeProperty("--popup-date-menu-left");
            menu.style.removeProperty("--popup-date-menu-top");
            menu.style.removeProperty("--popup-date-menu-bottom");
            menu.style.maxHeight = "";
            menu.style.overflowY = "";
            if (menuPortalShell)
            {
                menuPortalShell.classList.remove("open", "open-up");
            }
            if (originalMenuParent && menu.parentNode !== originalMenuParent)
            {
                originalMenuParent.insertBefore(menu, originalMenuNextSibling);
            }
            if (menuPortal && menuPortal.parentNode)
            {
                menuPortal.parentNode.removeChild(menuPortal);
            }
            delete shell._restorePopupMenu;
        }

        const positionMenu = function (openUp)
        {
            const viewportPadding = 12;
            const menuGap = 2;
            const shellRect = shell.getBoundingClientRect();
            const menuRect = menu.getBoundingClientRect();
            const menuWidth = menuRect.width || menu.offsetWidth || menu.scrollWidth || 236;
            const menuHeight = menuRect.height || menu.offsetHeight || menu.scrollHeight || 318;
            const maxLeft = Math.max(viewportPadding, window.innerWidth - viewportPadding - menuWidth);
            const preferredLeft = hiddenInput.name === "to_date"
                ? shellRect.right - menuWidth
                : shellRect.left;
            const left = Math.min(Math.max(viewportPadding, preferredLeft), maxLeft);
            const top = shellRect.bottom + menuGap;
            const bottom = Math.max(viewportPadding, window.innerHeight - shellRect.top + menuGap);

            menu.style.setProperty("--popup-date-menu-left", left + "px");
            if (openUp)
            {
                menu.style.setProperty("--popup-date-menu-top", "auto");
                menu.style.setProperty("--popup-date-menu-bottom", bottom + "px");
            }
            else
            {
                menu.style.setProperty("--popup-date-menu-top", top + "px");
                menu.style.setProperty("--popup-date-menu-bottom", "auto");
            }
        };

        const render = function ()
        {
            const selectedDate = parseValueDate(hiddenInput.value);
            const previewDate = parseValueDate(shell.dataset.previewValue || "");
            const effectiveSelectedDate = hiddenInput.name === "from_date"
                ? (previewDate || getPreferredOpenDate())
                : (previewDate || selectedDate || getPreferredOpenDate());
            const normalizedToday = getTodayDate();
            const minimumDate = getMinimumSelectableDate();
            const sourceViewDate = shell._viewDate || previewDate || getViewDate();
            const viewDate = new Date(sourceViewDate.getFullYear(), sourceViewDate.getMonth(), 1);
            const monthStart = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
            const monthEnd = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0);
            const firstDayIndex = (monthStart.getDay() + 6) % 7;
            const daysInMonth = monthEnd.getDate();

            shell._viewDate = viewDate;
            currentNode.textContent = monthStart.toLocaleDateString("en-US", { month: "long", year: "numeric" });

            if (prevButton)
            {
                prevButton.disabled = !!minimumDate && viewDate.getFullYear() === minimumDate.getFullYear() && viewDate.getMonth() === minimumDate.getMonth();
            }

            grid.replaceChildren();

            for (let i = 0; i < firstDayIndex; i += 1)
            {
                const blankCell = document.createElement("button");
                blankCell.type = "button";
                blankCell.className = "date-day muted";
                blankCell.disabled = true;
                grid.appendChild(blankCell);
            }

            for (let day = 1; day <= daysInMonth; day += 1)
            {
                const date = new Date(viewDate.getFullYear(), viewDate.getMonth(), day);
                const dayButton = document.createElement("button");
                dayButton.type = "button";
                dayButton.className = "date-day";
                dayButton.textContent = String(day);

                const isToday = date.getTime() === normalizedToday.getTime();
                const isWeekend = date.getDay() === 0 || date.getDay() === 6;
                const isSelected = effectiveSelectedDate && date.getFullYear() === effectiveSelectedDate.getFullYear() && date.getMonth() === effectiveSelectedDate.getMonth() && date.getDate() === effectiveSelectedDate.getDate();
                const isBeforeMinimum = minimumDate ? date < minimumDate : false;

                if (isToday) dayButton.classList.add("today");
                if (isWeekend) dayButton.classList.add("weekend");
                if (isSelected) dayButton.classList.add("selected");
                if (isBeforeMinimum)
                {
                    dayButton.classList.add("muted");
                    dayButton.disabled = true;
                }

                if (!isBeforeMinimum)
                {
                    dayButton.addEventListener("click", function ()
                    {
                        hiddenInput.value = formatValueDate(date);
                        shell._viewDate = new Date(date.getFullYear(), date.getMonth(), 1);
                        sync();
                        hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
                        close();
                    });
                }

                grid.appendChild(dayButton);
            }

        };

        var dateOpenedAt = 0;

        const open = function ()
        {
            if (hiddenInput.disabled || shell.classList.contains("is-disabled"))
            {
                const form = hiddenInput.form || shell.closest("form");
                const monthInput = form ? form.querySelector('input[name="month"]') : null;
                const fromInput = form ? form.querySelector('input[name="from_date"]') : null;

                if (monthInput && monthInput.value)
                {
                    showPopupFilterPointWarning(shell, "Clear Month to use date range.");
                }
                else if (hiddenInput.name === "to_date" && fromInput && !fromInput.value)
                {
                    showPopupFilterPointWarning(shell, "Select From Date first.");
                }
                return;
            }

            const isOpen = shell.classList.contains("open");

            document.querySelectorAll(".popup-filter-month-shell.open, .popup-filter-date-shell.open, .popup-filter-leave-shell.open").forEach(function (openShell)
            {
                openShell.classList.remove("open");
                openShell.classList.remove("open-up");
                if (typeof openShell._restorePopupMenu === "function")
                {
                    openShell._restorePopupMenu();
                }
                const openTrigger = openShell.querySelector(".month-trigger, .date-trigger, .popup-filter-leave-trigger");
                if (openTrigger)
                {
                    openTrigger.setAttribute("aria-expanded", "false");
                }
            });

            if (isOpen)
            {
                close();
                return;
            }

            const openDate = getPreferredOpenDate();
            shell.dataset.previewValue = formatValueDate(openDate);
            shell._viewDate = new Date(openDate.getFullYear(), openDate.getMonth(), 1);
            window.clearTimeout(shell._closeTimer);
            const menuHeight = menu.getBoundingClientRect().height || menu.offsetHeight || menu.scrollHeight || 318;
            const shellRect = shell.getBoundingClientRect();
            const viewportPadding = 18;
            const openUp = true;

            shell.classList.toggle("open-up", openUp);
            mountMenu(openUp);
            positionMenu(openUp);
            shell.classList.add("open");
            trigger.setAttribute("aria-expanded", "true");
            dateOpenedAt = Date.now();
            render();
            positionMenu(openUp);
            requestAnimationFrame(function ()
            {
                if (shell.classList.contains("open"))
                {
                    positionMenu(openUp);
                }
            });
        };

        trigger.addEventListener("click", function (e) { e.stopPropagation(); open(); });
        menu.addEventListener("click", function (e) { e.stopPropagation(); });
        trigger.addEventListener("keydown", function (event)
        {
            if (event.key === "Enter" || event.key === " ")
            {
                event.preventDefault();
                open();
            }
        });

        if (prevButton)
        {
            prevButton.addEventListener("click", function (e)
            {
                e.stopPropagation();
                if (Date.now() - dateOpenedAt < 300) { return; }
                shell._viewDate = new Date(shell._viewDate.getFullYear(), shell._viewDate.getMonth() - 1, 1);
                render();
            });
        }

        if (nextButton)
        {
            nextButton.addEventListener("click", function (e)
            {
                e.stopPropagation();
                if (Date.now() - dateOpenedAt < 300) { return; }
                shell._viewDate = new Date(shell._viewDate.getFullYear(), shell._viewDate.getMonth() + 1, 1);
                render();
            });
        }

        if (todayButton)
        {
            todayButton.addEventListener("click", function (e)
            {
                e.stopPropagation();
                const today = getTodayDate();
                hiddenInput.value = formatValueDate(today);
                shell._viewDate = new Date(today.getFullYear(), today.getMonth(), 1);
                sync();
                render();
                hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
            });
        }

        if (clearButton)
        {
            clearButton.addEventListener("click", function (e)
            {
                e.stopPropagation();
                hiddenInput.value = "";
                shell._viewDate = getViewDate();
                sync();
                render();
                hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
            });
        }

        document.addEventListener("click", function (event)
        {
            if (!shell.contains(event.target) && !menu.contains(event.target))
            {
                close();
            }
        });

        shell.dataset.bound = "true";
        shell._viewDate = getViewDate();
        sync();
        render();
    }

    function buildPopupFilterLeaveTypeDropdown(shell)
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

        const sync = function ()
        {
            const selected = options.find(function (option)
            {
                return (option.dataset.value || "") === (hiddenInput.value || "");
            }) || options[0];

            window.setSafeHTML(valueNode, selected.dataset.displayLabel || '<span class="popup-filter-leave-value-symbol" aria-hidden="true">&#9679;</span><span class="popup-filter-leave-value-text">All types</span>');
            options.forEach(function (option)
            {
                option.classList.toggle("is-selected", option === selected);
            });
        };

        const scrollToSelectedOption = function ()
        {
            const selected = options.find(function (option)
            {
                return option.classList.contains("is-selected");
            }) || options[0];

            if (!selected)
            {
                return;
            }

            const targetTop = selected.offsetTop - ((menu.clientHeight - selected.offsetHeight) / 2);
            const maxScrollTop = Math.max(0, menu.scrollHeight - menu.clientHeight);
            menu.scrollTop = Math.max(0, Math.min(targetTop, maxScrollTop));
        };

        const close = function ()
        {
            shell.classList.remove("open");
            trigger.setAttribute("aria-expanded", "false");
        };

        trigger.addEventListener("click", function ()
        {
            const willOpen = !shell.classList.contains("open");
            document.querySelectorAll(".popup-filter-month-shell.open, .popup-filter-date-shell.open, .popup-filter-leave-shell.open").forEach(function (openShell)
            {
                openShell.classList.remove("open");
                openShell.classList.remove("open-up");
                if (typeof openShell._restorePopupMenu === "function")
                {
                    openShell._restorePopupMenu();
                }
                const openTrigger = openShell.querySelector(".month-trigger, .date-trigger, .popup-filter-leave-trigger");
                if (openTrigger)
                {
                    openTrigger.setAttribute("aria-expanded", "false");
                }
            });

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

        trigger.addEventListener("keydown", function (event)
        {
            if (event.key === "Enter" || event.key === " ")
            {
                event.preventDefault();
                trigger.click();
            }
        });

        options.forEach(function (option)
        {
            option.addEventListener("click", function ()
            {
                hiddenInput.value = option.dataset.value || "";
                sync();
                hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
                hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
                close();
            });
        });

        document.addEventListener("click", function (event)
        {
            if (!shell.contains(event.target))
            {
                close();
            }
        });

        shell.dataset.bound = "true";
        sync();
    }

    function getPopupLeaveTypeBadgeClass(value)
    {
        const normalized = String(value || "").trim().toLowerCase();

        if (normalized.includes("sick"))
        {
            return "is-sick";
        }

        if (normalized.includes("unpaid"))
        {
            return "is-unpaid";
        }

        if (normalized.includes("earned"))
        {
            return "is-earned";
        }

        if (normalized.includes("short"))
        {
            return "is-short";
        }

        if (normalized.includes("half"))
        {
            return "is-half";
        }

        return "is-neutral";
    }

    function getPopupLeaveTypeDisplayLabel(value)
    {
        const normalized = String(value || "").trim().toLowerCase();
        const match = popupLeaveTypeMeta.find(function (item)
        {
            return normalized.includes(item.key);
        });

        return match ? match.label : String(value || "");
    }

    function formatManageRelativeLeaveAge(isoValue)
    {
        if (!isoValue)
        {
            return null;
        }

        const target = new Date(isoValue);

        if (Number.isNaN(target.getTime()))
        {
            return null;
        }

        const now = new Date();
        const diffMs = Math.max(0, now.getTime() - target.getTime());
        const diffMinutes = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const minuteRemainder = diffMinutes % 60;
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMinutes < 1)
        {
            return "Just now";
        }

        if (diffMinutes < 60)
        {
            return diffMinutes + " min" + (diffMinutes > 1 ? "s" : "") + " ago";
        }

        if (diffHours < 24)
        {
            return diffHours + " hour" + (diffHours > 1 ? "s" : "") + ", " + minuteRemainder + " min ago";
        }

        if (diffDays === 1)
        {
            return "Yesterday";
        }

        if (diffDays < 7)
        {
            return diffDays + " days ago";
        }

        return null;
    }

    function formatManagePopupClockTime(isoValue, fallbackValue)
    {
        if (isoValue)
        {
            const target = new Date(isoValue);

            if (!Number.isNaN(target.getTime()))
            {
                return target.toLocaleTimeString("en-US", {
                    hour: "numeric",
                    minute: "2-digit",
                    hour12: true
                });
            }
        }

        if (fallbackValue)
        {
            const match = String(fallbackValue).match(/(\d{1,2}:\d{2}\s?[AP]M)$/i);
            if (match)
            {
                return match[1].replace(/\s+/g, " ").toUpperCase();
            }
        }

        return "-";
    }

    function formatManagePopupDateText(isoValue, fallbackValue)
    {
        if (isoValue)
        {
            const target = new Date(isoValue);

            if (!Number.isNaN(target.getTime()))
            {
                return target.toLocaleDateString("en-US", {
                    month: "short",
                    day: "2-digit",
                    year: "numeric"
                });
            }
        }

        if (fallbackValue)
        {
            const fallbackText = String(fallbackValue).trim().replace(/\s+/g, " ");
            const withoutTime = fallbackText.replace(/\s+\d{1,2}:\d{2}\s?[AP]M$/i, "");
            return withoutTime || fallbackText || "-";
        }

        return "-";
    }

    function renderPopupDecisionBlock(options)
    {
        const iso = String(options.iso || "").trim();
        const fallback = String(options.fallback || "").trim();
        const relativeText = formatRelativeLeaveAge(iso);
        const primaryText = relativeText || formatManagePopupDateText(iso, fallback);
        const secondaryText = formatManagePopupClockTime(iso, fallback);
        const extraClass = options.extraClass ? ` ${options.extraClass}` : "";
        const dateIconClass = options.dateIconClass ? ` ${options.dateIconClass}` : "";
        const timeIconClass = options.timeIconClass ? ` ${options.timeIconClass}` : "";
        const absoluteText = formatManagePopupDateText(iso, fallback);
        const updateCount = Number.parseInt(options.count || "0", 10);
        const countText = updateCount > 0 ? ` (${updateCount})` : "";

        return `
            <div class="applied-block decision-block${extraClass}">
                <div class="applied-line">
                    <span class="meta-icon${dateIconClass}">${options.dateIcon || "&#128197;"}</span>
                    <strong title="${escapeHtml(absoluteText)}">${escapeHtml(primaryText)}${escapeHtml(countText)}</strong>
                </div>
                <div class="applied-line">
                    <span class="meta-icon${timeIconClass}">${options.timeIcon || "&#128339;"}</span>
                    <span>${escapeHtml(secondaryText)}</span>
                </div>
            </div>
        `;
    }

    function renderPopupFilterBadges(status)
    {
        if (!popupFilterBadges)
        {
            return;
        }

        const state = getPopupFilterState(status);
        const badges = [];

        if (state.leave_type)
        {
            badges.push(`<button type="button" class="popup-filter-badge popup-filter-badge-leave-type ${getPopupLeaveTypeBadgeClass(state.leave_type)}" data-popup-filter-clear="leave_type"><span class="popup-filter-badge-icon" aria-hidden="true"></span><span class="popup-filter-badge-text"><span class="popup-filter-badge-label">Leave Type</span><span class="popup-filter-badge-value">${escapeHtml(getPopupLeaveTypeDisplayLabel(state.leave_type))}</span></span><span class="popup-filter-badge-clear">&times;</span></button>`);
        }

        if (state.month)
        {
            badges.push(`<button type="button" class="popup-filter-badge" data-popup-filter-clear="month"><span class="popup-filter-badge-icon">&#128197;</span><span class="popup-filter-badge-text"><span class="popup-filter-badge-label">Month</span><span class="popup-filter-badge-value">${escapeHtml(formatPopupFilterMonth(state.month))}</span></span><span class="popup-filter-badge-clear">&times;</span></button>`);
        }

        if (state.from_date || state.to_date)
        {
            badges.push(`<button type="button" class="popup-filter-badge" data-popup-filter-clear="date_range"><span class="popup-filter-badge-icon">&#128467;</span><span class="popup-filter-badge-text"><span class="popup-filter-badge-label">Date Range</span><span class="popup-filter-badge-value">${escapeHtml(state.from_date || "...")} &rarr; ${escapeHtml(state.to_date || "...")}</span></span><span class="popup-filter-badge-clear">&times;</span></button>`);
        }

        window.setSafeHTML(popupFilterBadges, badges.join(""));
        popupFilterBadges.hidden = badges.length === 0;

        if (popupFilterButton)
        {
            popupFilterButton.classList.toggle("has-active-filter", badges.length > 0);
        }

        if (popupFilterButtonCount)
        {
            popupFilterButtonCount.textContent = String(badges.length);
            popupFilterButtonCount.hidden = badges.length === 0;
        }
    }

    function openPopupHistoryFilterModal()
    {
        if (!currentEmployeeDetail || !sharedModalContent)
        {
            return;
        }

        const status = activePopupHistoryStatus;
        const filterState = clonePopupHistoryFilter(getPopupFilterState(status));
        const leaveTypeOptions = getPopupFilterLeaveTypeOptions(status);
        const statusLabel = status.charAt(0).toUpperCase() + status.slice(1);
        const hasActiveModalFilter = function ()
        {
            return !!(filterState.leave_type || filterState.month || filterState.from_date || filterState.to_date);
        };

        window.setSafeHTML(sharedModalContent, `
            <div class="popup-filter-modal-content">
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
                <form class="popup-filter-form" id="popupHistoryFilterForm">
                    <div class="popup-filter-grid">
                        <label class="popup-filter-field">
                            <span class="popup-filter-field-heading">
                                <span class="popup-filter-field-heading-badge">01</span>
                                <span class="popup-filter-field-heading-icon popup-filter-field-heading-icon-leave" aria-hidden="true">&#9679;</span>
                                <span class="popup-filter-field-heading-text">Leave Type</span>
                                <span class="popup-filter-field-heading-line" aria-hidden="true"></span>
                            </span>
                            <div class="popup-filter-shell popup-filter-leave-shell custom-select select-shell leave-type-shell">
                                <input type="hidden" name="leave_type" value="${escapeHtml(filterState.leave_type)}">
                                <div class="custom-select-display">
                                    <button type="button" class="popup-filter-leave-trigger custom-select-trigger" aria-haspopup="listbox" aria-expanded="false">
                                        <span class="popup-filter-leave-value custom-select-value"><span class="popup-filter-leave-value-symbol" aria-hidden="true">&#9679;</span><span class="popup-filter-leave-value-text">All types</span></span>
                                        <span class="popup-filter-leave-icon custom-select-icon" aria-hidden="true"></span>
                                    </button>
                                </div>
                                <div class="popup-filter-leave-menu custom-select-menu" role="listbox">
                                    <button type="button" class="popup-filter-leave-option custom-option is-all-types" data-value="" data-display-label="<span class=&quot;popup-filter-leave-value-symbol&quot; aria-hidden=&quot;true&quot;>&#9679;</span><span class=&quot;popup-filter-leave-value-text&quot;>All types</span>"><span class="popup-filter-leave-option-symbol" aria-hidden="true">&#9679;</span><span class="option-title">All types</span><span class="popup-filter-leave-option-check" aria-hidden="true">&#10003;</span></button>
                                    ${leaveTypeOptions.map(function (type)
                                    {
                                        return `<button type="button" class="popup-filter-leave-option custom-option" data-value="${escapeHtml(type.value)}" data-display-label="<span class=&quot;popup-filter-leave-value-symbol&quot; aria-hidden=&quot;true&quot;>${escapeHtml(type.symbol || "\u25CF")}</span><span class=&quot;popup-filter-leave-value-text&quot;>${escapeHtml(type.label)}</span>"><span class="popup-filter-leave-option-symbol" aria-hidden="true">${escapeHtml(type.symbol || "\u25CF")}</span><span class="option-title">${escapeHtml(type.label)}</span><span class="popup-filter-leave-option-check" aria-hidden="true">&#10003;</span></button>`;
                                    }).join("")}
                                </div>
                            </div>
                        </label>
                        <label class="popup-filter-field">
                            <span class="popup-filter-field-heading">
                                <span class="popup-filter-field-heading-badge">02</span>
                                <span class="popup-filter-field-heading-icon popup-filter-field-heading-icon-month" aria-hidden="true">&#128197;</span>
                                <span class="popup-filter-field-heading-text">Month</span>
                                <span class="popup-filter-field-heading-line" aria-hidden="true"></span>
                            </span>
                            <div class="popup-filter-shell popup-filter-month-shell custom-month-picker">
                                <input type="hidden" name="month" value="${escapeHtml(filterState.month)}">
                                <div class="month-display">
                                    <div class="month-trigger" role="button" tabindex="0" aria-haspopup="dialog" aria-expanded="false">
                                        <span class="month-value">Select month</span>
                                        <span class="month-icon" aria-hidden="true"></span>
                                    </div>
                                </div>
                                <div class="month-menu" role="dialog" aria-label="Month calendar">
                                    <div class="month-menu-header">
                                        <button type="button" class="month-nav prev-year" aria-label="Previous year">&#8249;</button>
                                        <div class="month-current"></div>
                                        <button type="button" class="month-nav next-year" aria-label="Next year">&#8250;</button>
                                    </div>
                                    <div class="month-grid"></div>
                                    <div class="month-actions">
                                        <button type="button" class="month-action today-action">Current</button>
                                        <button type="button" class="month-action clear-action">Clear</button>
                                    </div>
                                </div>
                            </div>
                        </label>
                        <label class="popup-filter-field">
                            <span class="popup-filter-field-heading">
                                <span class="popup-filter-field-heading-badge">03</span>
                                <span class="popup-filter-field-heading-icon popup-filter-field-heading-icon-date" aria-hidden="true">&#128198;</span>
                                <span class="popup-filter-field-heading-text">From Date</span>
                                <span class="popup-filter-field-heading-line" aria-hidden="true"></span>
                            </span>
                            <div class="popup-filter-shell popup-filter-date-shell custom-date-picker">
                                <input type="hidden" name="from_date" value="${escapeHtml(filterState.from_date)}">
                                <div class="date-display">
                                    <div class="date-trigger" role="button" tabindex="0" aria-haspopup="dialog" aria-expanded="false">
                                        <span class="date-value">dd-mm-yyyy</span>
                                        <span class="date-icon" aria-hidden="true"></span>
                                    </div>
                                </div>
                                <div class="date-menu" role="dialog" aria-label="From date calendar">
                                    <div class="date-menu-header">
                                        <button type="button" class="date-nav prev-month" aria-label="Previous month">&#8249;</button>
                                        <div class="date-current"></div>
                                        <button type="button" class="date-nav next-month" aria-label="Next month">&#8250;</button>
                                    </div>
                                    <div class="date-weekdays">
                                        <span>Mo</span>
                                        <span>Tu</span>
                                        <span>We</span>
                                        <span>Th</span>
                                        <span>Fr</span>
                                        <span>Sa</span>
                                        <span>Su</span>
                                    </div>
                                    <div class="date-grid"></div>
                                    <div class="date-actions">
                                        <button type="button" class="date-action today-action">Today</button>
                                        <button type="button" class="date-action clear-action">Clear</button>
                                    </div>
                                </div>
                            </div>
                        </label>
                        <label class="popup-filter-field">
                            <span class="popup-filter-field-heading">
                                <span class="popup-filter-field-heading-badge">04</span>
                                <span class="popup-filter-field-heading-icon popup-filter-field-heading-icon-date" aria-hidden="true">&#128198;</span>
                                <span class="popup-filter-field-heading-text">To Date</span>
                                <span class="popup-filter-field-heading-line" aria-hidden="true"></span>
                            </span>
                            <div class="popup-filter-shell popup-filter-date-shell custom-date-picker">
                                <input type="hidden" name="to_date" value="${escapeHtml(filterState.to_date)}">
                                <div class="date-display">
                                    <div class="date-trigger" role="button" tabindex="0" aria-haspopup="dialog" aria-expanded="false">
                                        <span class="date-value">dd-mm-yyyy</span>
                                        <span class="date-icon" aria-hidden="true"></span>
                                    </div>
                                </div>
                                <div class="date-menu" role="dialog" aria-label="To date calendar">
                                    <div class="date-menu-header">
                                        <button type="button" class="date-nav prev-month" aria-label="Previous month">&#8249;</button>
                                        <div class="date-current"></div>
                                        <button type="button" class="date-nav next-month" aria-label="Next month">&#8250;</button>
                                    </div>
                                    <div class="date-weekdays">
                                        <span>Mo</span>
                                        <span>Tu</span>
                                        <span>We</span>
                                        <span>Th</span>
                                        <span>Fr</span>
                                        <span>Sa</span>
                                        <span>Su</span>
                                    </div>
                                    <div class="date-grid"></div>
                                    <div class="date-actions">
                                        <button type="button" class="date-action today-action">Today</button>
                                        <button type="button" class="date-action clear-action">Clear</button>
                                    </div>
                                </div>
                            </div>
                        </label>
                    </div>
                    <div class="popup-filter-actions">
                        <button type="button" class="popup-filter-clear-btn" id="popupHistoryFilterClear">Clear All Filter</button>
                        <button type="submit" class="popup-filter-apply-btn">Apply Filter</button>
                    </div>
                </form>
            </div>
        `);

        openModal();

        const form = document.getElementById("popupHistoryFilterForm");
        const clearButton = document.getElementById("popupHistoryFilterClear");

        if (form)
        {
            const leaveTypeShell = form.querySelector(".popup-filter-leave-shell");
            const monthInput = form.querySelector('input[name="month"]');
            const fromDateInput = form.querySelector('input[name="from_date"]');
            const toDateInput = form.querySelector('input[name="to_date"]');
            const monthPickerShell = form.querySelector(".popup-filter-month-shell");
            const datePickerShells = Array.from(form.querySelectorAll(".popup-filter-date-shell"));
            const syncPopupClearButton = function ()
            {
                if (!clearButton)
                {
                    return;
                }

                const hasFormFilter = !!(
                    (leaveTypeShell && leaveTypeShell.querySelector('input[name="leave_type"]') && leaveTypeShell.querySelector('input[name="leave_type"]').value) ||
                    (monthInput && monthInput.value) ||
                    (fromDateInput && fromDateInput.value) ||
                    (toDateInput && toDateInput.value)
                );

                clearButton.disabled = !hasFormFilter;
                clearButton.setAttribute("aria-disabled", String(!hasFormFilter));
            };
            const syncPopupFilterDateInputs = function ()
            {
                const hasMonth = !!(monthInput && monthInput.value);
                const hasRange = !!((fromDateInput && fromDateInput.value) || (toDateInput && toDateInput.value));
                const parsedFromDate = fromDateInput && fromDateInput.value ? new Date(fromDateInput.value + "T00:00:00") : null;
                const parsedToDate = toDateInput && toDateInput.value ? new Date(toDateInput.value + "T00:00:00") : null;

                if (parsedFromDate && parsedToDate && parsedToDate < parsedFromDate && toDateInput)
                {
                    toDateInput.value = fromDateInput.value;
                }

                if (monthInput)
                {
                    monthInput.disabled = hasRange;
                    monthPickerShell.classList.toggle("is-disabled", hasRange);
                }

                if (fromDateInput)
                {
                    fromDateInput.disabled = hasMonth;
                    if (datePickerShells[0])
                    {
                        datePickerShells[0].classList.toggle("is-disabled", hasMonth);
                    }
                }

                if (toDateInput)
                {
                    const hasFromDate = !!(fromDateInput && fromDateInput.value);
                    const toDisabled = hasMonth || !hasFromDate;
                    toDateInput.disabled = toDisabled;
                    if (datePickerShells[1])
                    {
                        datePickerShells[1].classList.toggle("is-disabled", toDisabled);
                    }
                }

                syncPopupClearButton();
            };

            if (leaveTypeShell)
            {
                buildPopupFilterLeaveTypeDropdown(leaveTypeShell);
                const leaveTypeInput = leaveTypeShell.querySelector('input[name="leave_type"]');
                if (leaveTypeInput)
                {
                    leaveTypeInput.addEventListener("input", syncPopupClearButton);
                    leaveTypeInput.addEventListener("change", syncPopupClearButton);
                }
            }

            if (monthPickerShell)
            {
                buildPopupFilterMonthPicker(monthPickerShell);
            }

            datePickerShells.forEach(function (shell)
            {
                buildPopupFilterDatePicker(shell);
            });

            [monthInput, fromDateInput, toDateInput].forEach(function (input)
            {
                if (!input)
                {
                    return;
                }

                input.addEventListener("input", syncPopupFilterDateInputs);
                input.addEventListener("change", syncPopupFilterDateInputs);
            });

            syncPopupFilterDateInputs();
            syncPopupClearButton();

            form.addEventListener("submit", function (event)
            {
                event.preventDefault();
                const formData = new FormData(form);
                const normalizedMonth = normalizePopupFilterMonthValue(String(formData.get("month") || ""));

                popupHistoryFilters[status] = {
                    leave_type: String(formData.get("leave_type") || ""),
                    month: normalizedMonth,
                    from_date: String(formData.get("from_date") || ""),
                    to_date: String(formData.get("to_date") || "")
                };
                setPopupHistoryPage(status, 1);
                syncPopupTabFilterIndicators();

                closeModal();
                renderPopupHistoryTable(currentEmployeeDetail);
            });
        }

        if (clearButton)
        {
            clearButton.disabled = !hasActiveModalFilter();
            clearButton.setAttribute("aria-disabled", String(!hasActiveModalFilter()));
            clearButton.addEventListener("click", async function ()
            {
                if (clearButton.disabled)
                {
                    return;
                }

                const shouldClear = typeof window.showThemeConfirm === "function"
                    ? await window.showThemeConfirm(`Are you sure you want to clear all filters for ${statusLabel} Requests Section?`, {
                        title: "Clear filters",
                        confirmText: "Clear filters",
                        variant: "confirm"
                    })
                    : window.confirm(`Are you sure you want to clear all filters for ${statusLabel} Requests Section?`);

                if (!shouldClear)
                {
                    return;
                }

                popupHistoryFilters[status] = createEmptyPopupHistoryFilter();
                setPopupHistoryPage(status, 1);
                syncPopupTabFilterIndicators();
                closeModal();
                renderPopupHistoryTable(currentEmployeeDetail);
            });
        }
    }

    function upsertEmployeeSnapshot(snapshot, options)
    {
        const employeeId = String(snapshot && snapshot.id || "");

        if (!employeeId)
        {
            return snapshot;
        }

        const existingIndex = employeeData.findIndex(function (employee)
        {
            return String(employee.id) === employeeId;
        });

        if (existingIndex >= 0)
        {
            employeeData[existingIndex] = snapshot;
        }
        else
        {
            employeeData.push(snapshot);
        }

        updateEmployeeCardFromSnapshot(snapshot, options);
        return snapshot;
    }

    function fetchManageEmployeeDetail(employeeId, options)
    {
        return fetch(getManageEmployeeDetailApiUrl(employeeId) + "?_ts=" + Date.now(), {
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache"
            },
            cache: "no-store"
        })
            .then(function (response)
            {
                if (!response.ok)
                {
                    throw new Error("Unable to load latest employee detail.");
                }

                return typeof window.parseJsonOrSessionExpired === "function" ? window.parseJsonOrSessionExpired(response) : response.json();
            })
            .then(function (payload)
            {
                if (payload.sessionExpired)
                {
                    if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(payload);
                    return null;
                }
                return upsertEmployeeSnapshot(payload, options);
            });
    }

    function refreshEmployeeCardSnapshot(employeeId, options)
    {
        const normalizedId = String(employeeId || "");

        if (!normalizedId || employeeCardRefreshInFlight.has(normalizedId))
        {
            return Promise.resolve(null);
        }

        employeeCardRefreshInFlight.add(normalizedId);

        return fetchManageEmployeeDetail(normalizedId, options)
            .catch(function ()
            {
                return null;
            })
            .finally(function ()
            {
                employeeCardRefreshInFlight.delete(normalizedId);
            });
    }

    function refreshVisibleEmployeeCards(options)
    {
        const shouldForcePhotoReload = Boolean(
            pendingEmployeeCardPhotoReload || (options && options.forcePhotoReload)
        );

        if (shouldForcePhotoReload)
        {
            pendingEmployeeCardPhotoReload = true;
        }

        if (document.hidden)
        {
            return;
        }

        const refreshOptions = shouldForcePhotoReload
            ? { forcePhotoReload: true }
            : options;

        employeeProfileCards
            .filter(function (card)
            {
                return !card.hidden && card.dataset.employeeId;
            })
            .forEach(function (card)
            {
                refreshEmployeeCardSnapshot(card.dataset.employeeId, refreshOptions);
            });

        pendingEmployeeCardPhotoReload = false;
    }

    function setManageSummaryMetric(key, value)
    {
        const metric = manageSummaryMetrics[key];

        if (!metric)
        {
            return;
        }

        const nextValue = Number(value || 0);
        const nextText = String(nextValue);

        if (metric.textContent.trim() === nextText)
        {
            return;
        }

        metric.dataset.countupTarget = nextText;
        metric.textContent = nextText;
        metric.classList.remove("count-pulse");
        void metric.offsetWidth;
        metric.classList.add("count-pulse");
    }

    function refreshManageSummaryMetrics()
    {
        if (!manageSummaryApiUrl || document.hidden)
        {
            return;
        }

        fetch(manageSummaryApiUrl + "?_ts=" + Date.now(), {
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache"
            },
            cache: "no-store"
        })
            .then(function (response)
            {
                if (!response.ok)
                {
                    throw new Error("Unable to load latest manage-all summary.");
                }

                return typeof window.parseJsonOrSessionExpired === "function" ? window.parseJsonOrSessionExpired(response) : response.json();
            })
            .then(function (summary)
            {
                if (summary.sessionExpired)
                {
                    if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(summary);
                    return;
                }
                setManageSummaryMetric("pending", summary.pending);
                setManageSummaryMetric("approved", summary.approved);
                setManageSummaryMetric("rejected", summary.rejected);
            })
            .catch(function ()
            {
                return null;
            });
    }

    function refreshManageAllLiveData(options)
    {
        refreshVisibleEmployeeCards(options);
        refreshManageSummaryMetrics();
    }

    function getLeaveActionUrl(urlTemplate, leaveId)
    {
        return urlTemplate.replace(/0\/?$/, String(leaveId) + "/");
    }

    function findCurrentEmployeeLeave(leaveId)
    {
        if (!currentEmployeeDetail || !Array.isArray(currentEmployeeDetail.leaves))
        {
            return null;
        }

        const normalizedId = String(leaveId);
        return currentEmployeeDetail.leaves.find(function (leave)
        {
            return String(leave.id) === normalizedId;
        }) || null;
    }

    function getManageLeaveThemeClass(typeClass)
    {
        const normalized = String(typeClass || "default").toLowerCase();
        const allowed = ["sick", "unpaid", "earned", "short", "half"];
        return allowed.indexOf(normalized) >= 0 ? normalized : "default";
    }

    function getManageLeaveScheduleDateText(leave)
    {
        return `${leave && leave.from_date ? leave.from_date : "-"} \u27F6 ${leave && leave.to_date ? leave.to_date : "-"}`;
    }

    function getManageLeaveScheduleTimeText(leave)
    {
        if (leave && leave.from_time && leave.to_time)
        {
            return `${leave.from_time} \u27F6 ${leave.to_time}`;
        }

        return "Full day";
    }

    function getManageLeaveDaysText(leave)
    {
        return String(leave && leave.days_value_display ? leave.days_value_display : calculateLeaveDayCount(leave && leave.from_date, leave && leave.to_date, leave && leave.type));
    }

    function getManageLeaveDaysValueText(leave)
    {
        const fullText = getManageLeaveDaysText(leave);
        const matchedValue = String(fullText || "").match(/[\d.]+/);
        return matchedValue ? matchedValue[0] : fullText;
    }

    function setMetaLineValue(container, text)
    {
        if (!container)
        {
            return;
        }

        const target = container.querySelector("span:last-child");

        if (target)
        {
            target.textContent = text || "-";
            return;
        }

        container.textContent = text || "-";
    }

    function getLeaveUpdateCount(leave)
    {
        const rawCount = leave && leave.no_of_times_updated != null ? leave.no_of_times_updated : 0;
        const count = Number.parseInt(rawCount, 10);
        return Number.isFinite(count) && count > 0 ? count : 0;
    }

    function formatUpdatedAtHeading(leave)
    {
        const count = getLeaveUpdateCount(leave);
        return count > 0 ? `Updated At (${count})` : "Updated At";
    }

    function setDecisionConfirmTypeIcon(icon, typeClass)
    {
        if (!icon)
        {
            return;
        }

        const resolvedType = getManageLeaveThemeClass(typeClass);
        const iconMap = {
            sick: "\u271A",
            earned: "\u2605",
            unpaid: "\u25CE",
            short: "\u25F7",
            half: "\u25D0",
            default: "\u25C6"
        };

        icon.setAttribute("data-leave-type", resolvedType);
        icon.textContent = iconMap[resolvedType] || iconMap.default;
    }

    function setRejectTypeChip(typeChip, leave)
    {
        if (!typeChip)
        {
            return;
        }

        const typeIcon = document.getElementById("rejectModalTypeIcon");
        const typeClass = getManageLeaveThemeClass(leave && leave.type_class);
        const typeSymbolMap = {
            sick: "&#10010;",
            earned: "&#10022;",
            unpaid: "&#9673;",
            short: "&#9716;",
            half: "&#9681;",
            default: "&#128278;&#65038;"
        };

        if (typeIcon)
        {
            typeIcon.innerHTML = typeSymbolMap[typeClass] || typeSymbolMap.default;
        }

        typeChip.dataset.leaveTypeClass = typeClass;
        setMetaLineValue(typeChip, leave && leave.type ? leave.type : "Leave");
    }

    function resetRejectSectionCards()
    {
        const grid = document.getElementById("rejectReasonSectionGrid");
        const button = document.getElementById("rejectReasonToggleAll");

        if (grid)
        {
            if (grid._motionTimer)
            {
                clearTimeout(grid._motionTimer);
                grid._motionTimer = null;
            }

            grid.classList.remove("is-revealing", "is-hiding");
            grid.classList.add("is-hidden");
        }

        if (button)
        {
            button.innerHTML = '<span class="reject-review-toggle-btn-icon" aria-hidden="true">&#9662;</span><span class="reject-review-toggle-btn-text">Show Notes</span>';
            button.setAttribute("aria-label", "Show notes");
            button.setAttribute("aria-expanded", "false");
        }
    }

    function setRejectReasonSectionsVisible(shouldShow, animate)
    {
        const grid = document.getElementById("rejectReasonSectionGrid");
        const button = document.getElementById("rejectReasonToggleAll");

        if (!grid)
        {
            return;
        }

        if (grid._motionTimer)
        {
            clearTimeout(grid._motionTimer);
            grid._motionTimer = null;
        }

        grid.classList.remove("is-revealing", "is-hiding");

        if (shouldShow)
        {
            grid.classList.remove("is-hidden");

            if (animate)
            {
                grid.classList.add("is-revealing");
                grid._motionTimer = window.setTimeout(function ()
                {
                    grid.classList.remove("is-revealing");
                    grid._motionTimer = null;
                }, 320);
            }
        }
        else if (animate && !grid.classList.contains("is-hidden"))
        {
            grid.classList.add("is-hiding");
            grid._motionTimer = window.setTimeout(function ()
            {
                grid.classList.remove("is-hiding");
                grid.classList.add("is-hidden");
                grid._motionTimer = null;
            }, 320);
        }
        else
        {
            grid.classList.add("is-hidden");
        }

        if (button)
        {
            button.innerHTML = shouldShow
                ? '<span class="reject-review-toggle-btn-icon" aria-hidden="true">&#9652;</span><span class="reject-review-toggle-btn-text">Hide Notes</span>'
                : '<span class="reject-review-toggle-btn-icon" aria-hidden="true">&#9662;</span><span class="reject-review-toggle-btn-text">Show Notes</span>';
            button.setAttribute("aria-label", shouldShow ? "Hide notes" : "Show notes");
            button.setAttribute("aria-expanded", shouldShow ? "true" : "false");
        }
    }

    function populateRejectModal(leave)
    {
        const modal = document.getElementById("rejectModal");
        const employeeChip = document.getElementById("rejectModalEmployeeChip");
        const typeChip = document.getElementById("rejectModalTypeChip");
        const scheduleDate = document.getElementById("rejectModalScheduleDate");
        const scheduleTime = document.getElementById("rejectModalScheduleTime");
        const days = document.getElementById("rejectModalDays");
        const applied = document.getElementById("rejectModalApplied");
        const appliedTime = document.getElementById("rejectModalAppliedTime");
        const updatedHeading = document.getElementById("rejectModalUpdatedHeading");
        const updated = document.getElementById("rejectModalUpdated");
        const updatedTime = document.getElementById("rejectModalUpdatedTime");
        const reason = document.getElementById("rejectModalReason");
        const typeClass = getManageLeaveThemeClass(leave && leave.type_class);

        if (!modal)
        {
            return;
        }

        modal.classList.remove("reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half", "reason-theme-default");
        modal.classList.add("reason-theme-" + typeClass);

        if (employeeChip)
        {
            employeeChip.textContent = currentEmployeeDetail && (currentEmployeeDetail.display_name || currentEmployeeDetail.username)
                ? (currentEmployeeDetail.display_name || currentEmployeeDetail.username)
                : "Employee";
        }

        setRejectTypeChip(typeChip, leave);
        setMetaLineValue(scheduleDate, getManageLeaveScheduleDateText(leave));
        setMetaLineValue(scheduleTime, getManageLeaveScheduleTimeText(leave));
        setMetaLineValue(days, getManageLeaveDaysValueText(leave));
        setMetaLineValue(applied, formatManagePopupDateText(leave && leave.applied_at_iso, leave && leave.applied_at));
        setMetaLineValue(appliedTime, formatPopupClockTime(leave && leave.applied_at_iso, leave && leave.applied_at));

        if (updatedHeading)
        {
            updatedHeading.textContent = formatUpdatedAtHeading(leave);
        }

        if (leave && leave.updated_at_iso)
        {
            setMetaLineValue(updated, formatManagePopupDateText(leave.updated_at_iso, leave.updated_at));
            setMetaLineValue(updatedTime, formatPopupClockTime(leave.updated_at_iso, leave.updated_at));
        }
        else
        {
            setMetaLineValue(updated, "Not updated");
            setMetaLineValue(updatedTime, "-");
        }

        if (reason)
        {
            reason.value = leave && leave.reason ? leave.reason : "No reason was added by the employee.";
        }
    }

    function setManagedModalButtonOrigin(modal, trigger)
    {
        if (!modal)
        {
            return;
        }

        const source = trigger instanceof HTMLElement
            ? trigger
            : (window.lastModalTrigger instanceof HTMLElement ? window.lastModalTrigger : null);

        if (!source || typeof source.getBoundingClientRect !== "function")
        {
            modal.style.removeProperty("--button-origin-x");
            modal.style.removeProperty("--button-origin-y");
            return;
        }

        const rect = source.getBoundingClientRect();
        const originX = rect.left + (rect.width / 2) - (window.innerWidth / 2);
        const originY = rect.top + (rect.height / 2) - (window.innerHeight / 2);

        modal.style.setProperty("--button-origin-x", originX.toFixed(1) + "px");
        modal.style.setProperty("--button-origin-y", originY.toFixed(1) + "px");
    }

    function openDecisionConfirm(config)
    {
        const modal = document.getElementById("decisionConfirmModal");
        const title = document.getElementById("decisionConfirmTitle");
        const eyebrow = document.getElementById("decisionConfirmEyebrow");
        const intro = document.getElementById("decisionConfirmIntro");
        const icon = document.getElementById("decisionConfirmIcon");
        const badgeIcon = document.getElementById("decisionConfirmBadgeIcon");
        const message = document.getElementById("decisionConfirmMessage");
        const subtext = document.getElementById("decisionConfirmSubtext");
        const employee = document.getElementById("decisionConfirmEmployee");
        const type = document.getElementById("decisionConfirmType");
        const typeIcon = document.getElementById("decisionConfirmTypeIcon");
        const scheduleDate = document.getElementById("decisionConfirmScheduleDate");
        const scheduleTime = document.getElementById("decisionConfirmScheduleTime");
        const days = document.getElementById("decisionConfirmDays");
        const applied = document.getElementById("decisionConfirmApplied");
        const appliedTime = document.getElementById("decisionConfirmAppliedTime");
        const updatedHeading = document.getElementById("decisionConfirmUpdatedHeading");
        const updated = document.getElementById("decisionConfirmUpdated");
        const updatedTime = document.getElementById("decisionConfirmUpdatedTime");
        const noteRow = document.getElementById("decisionConfirmNoteRow");
        const reasonNote = document.getElementById("decisionConfirmReasonNote");
        const note = document.getElementById("decisionConfirmNote");
        const reasonHeading = document.getElementById("decisionConfirmReasonHeading");
        const reasonContent = document.getElementById("decisionConfirmReasonContent");
        const noteHeading = document.getElementById("decisionConfirmNoteHeading");
        const noteContent = document.getElementById("decisionConfirmNoteContent");
        const submit = document.getElementById("decisionConfirmSubmit");
        const cancel = document.getElementById("decisionConfirmCancel");
        const leave = config && config.leave ? config.leave : null;
        const variant = config && config.variant === "reject" ? "reject" : "approve";
        const typeClass = getManageLeaveThemeClass(leave && leave.type_class);
        const resolvedUpdatedIso = leave && (leave.updated_at_iso || leave.approved_at_iso || leave.rejected_at_iso)
            ? (leave.updated_at_iso || leave.approved_at_iso || leave.rejected_at_iso)
            : "";
        const resolvedUpdatedText = leave && (leave.updated_at || leave.approved_at || leave.rejected_at)
            ? (leave.updated_at || leave.approved_at || leave.rejected_at)
            : "-";
        if (!modal || !submit || !cancel)
        {
            return Promise.resolve(false);
        }

        modal.dataset.variant = variant;
        setManagedModalButtonOrigin(modal, config && config.trigger);
        modal.classList.remove("reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half", "reason-theme-default");
        modal.classList.add("reason-theme-" + typeClass);

        if (eyebrow)
        {
            eyebrow.textContent = variant === "reject" ? "Reject request" : "Approve Request";
        }

        if (title)
        {
            title.textContent = variant === "reject" ? "Confirm rejection" : "";
        }

        if (intro)
        {
            intro.textContent = variant === "reject"
                ? "Please review the request details before confirming this decision."
                : "";
        }

        if (icon)
        {
            icon.innerHTML = variant === "reject" ? "&#9940;" : "&#10003;";
        }

        if (badgeIcon)
        {
            badgeIcon.innerHTML = variant === "reject" ? "&#9940;" : "&#10022;";
        }

        if (message)
        {
            message.textContent = variant === "reject"
                ? "You are about to reject this leave request."
                : "You are about to approve this leave request.";
        }

        if (subtext)
        {
            subtext.textContent = variant === "reject"
                ? "This will update the employee record and save the rejection note."
                : "This will immediately move the request into approved history.";
        }

        setMetaLineValue(employee, currentEmployeeDetail && (currentEmployeeDetail.display_name || currentEmployeeDetail.username) ? (currentEmployeeDetail.display_name || currentEmployeeDetail.username) : "Employee");
        setMetaLineValue(type, leave && leave.type ? leave.type : "Leave");
        setDecisionConfirmTypeIcon(typeIcon, leave && leave.type_class);
        setMetaLineValue(scheduleDate, getManageLeaveScheduleDateText(leave));
        setMetaLineValue(scheduleTime, getManageLeaveScheduleTimeText(leave));
        setMetaLineValue(days, getManageLeaveDaysText(leave));
        setMetaLineValue(applied, formatManagePopupDateText(leave && leave.applied_at_iso, leave && leave.applied_at));
        setMetaLineValue(appliedTime, formatPopupClockTime(leave && leave.applied_at_iso, leave && leave.applied_at));
        if (updatedHeading)
        {
            updatedHeading.textContent = formatUpdatedAtHeading(leave);
        }
        setMetaLineValue(updated, formatManagePopupDateText(resolvedUpdatedIso, resolvedUpdatedText));
        setMetaLineValue(updatedTime, formatPopupClockTime(resolvedUpdatedIso, resolvedUpdatedText));
        if (noteRow)
        {
            const noteText = config && config.note ? String(config.note).trim() : "";
            const reasonText = leave && leave.reason ? String(leave.reason).trim() : "";

            if (variant === "reject")
            {
                noteRow.hidden = false;

                if (reasonNote)
                {
                    reasonNote.hidden = false;
                }

                if (note)
                {
                    note.hidden = !noteText;
                }

                if (reasonHeading)
                {
                    reasonHeading.textContent = "Employee Reason";
                }

                if (reasonContent)
                {
                    reasonContent.textContent = reasonText || "No reason was added by the employee.";
                }

                if (noteHeading)
                {
                    noteHeading.textContent = "Rejection Notes";
                }

                if (noteContent)
                {
                    noteContent.textContent = noteText || "-";
                }
            }
            else
            {
                noteRow.hidden = false;

                if (reasonNote)
                {
                    reasonNote.hidden = false;
                }

                if (note)
                {
                    note.hidden = true;
                }

                if (reasonHeading)
                {
                    reasonHeading.textContent = "Employee Reason";
                }

                if (reasonContent)
                {
                    reasonContent.textContent = reasonText || "No reason was added by the employee.";
                }
            }
        }

        submit.className = variant === "reject" ? "reject-btn decision-confirm-submit-btn" : "approve-btn decision-confirm-submit-btn";
        submit.innerHTML = variant === "reject"
            ? '<span aria-hidden="true">&#9940;</span><span>Confirm Reject</span>'
            : '<span aria-hidden="true">&#10003;</span><span>Confirm Approve</span>';

        return new Promise(function (resolve)
        {
            decisionConfirmState = { resolve: resolve };
            showManagedModal(modal);
        });
    }

    function closeDecisionConfirm(confirmed)
    {
        const modal = document.getElementById("decisionConfirmModal");
        const state = decisionConfirmState;

        if (!modal || (!state && modal.getAttribute("aria-hidden") === "true"))
        {
            return;
        }

        decisionConfirmState = null;

        hideManagedModal(modal, function ()
        {
            if (state && typeof state.resolve === "function")
            {
                state.resolve(!!confirmed);
            }
        });
    }

    function setPopupActionLoading(isLoading)
    {
        popupActionInFlight = !!isLoading;

        document.querySelectorAll("#detailTableBody .approve-btn, #detailTableBody .reject-btn").forEach(function (button)
        {
            button.disabled = popupActionInFlight;
        });

        const rejectForm = document.getElementById("rejectForm");
        const rejectTextarea = document.getElementById("rejectionReason");
        const decisionConfirmSubmit = document.getElementById("decisionConfirmSubmit");
        const decisionConfirmCancel = document.getElementById("decisionConfirmCancel");

        if (rejectForm)
        {
            const submitButton = rejectForm.querySelector('button[type="submit"]');

            if (submitButton)
            {
                submitButton.disabled = popupActionInFlight;
            }
        }

        if (rejectTextarea)
        {
            rejectTextarea.disabled = popupActionInFlight;
        }

        if (decisionConfirmSubmit)
        {
            decisionConfirmSubmit.disabled = popupActionInFlight;
        }

        if (decisionConfirmCancel)
        {
            decisionConfirmCancel.disabled = popupActionInFlight;
        }
    }

    function showPopupActionError(message)
    {
        window.alert(message || "Unable to update leave request right now.");
    }

    function refreshEmployeeModalAfterAction(snapshot, nextStatus)
    {
        if (!snapshot)
        {
            return;
        }

        upsertEmployeeSnapshot(snapshot);
        activePopupHistoryStatus = nextStatus || activePopupHistoryStatus;
        renderEmployeeModal(snapshot);
        setPopupTableCollapsed(false);
        refreshManageSummaryMetrics();
    }

    function refreshHrNotificationsAfterDecision(leaveId)
    {
        window.dispatchEvent(new CustomEvent("hr-notifications:refresh", {
            detail: {
                apiUrl: notificationApiUrl,
                leaveId: leaveId
            }
        }));
    }

    function approveLeaveRequest(leaveId)
    {
        if (popupActionInFlight || !currentEmployeeDetail)
        {
            return;
        }

        setPopupActionLoading(true);

        fetch(getLeaveActionUrl(approveLeaveUrlTemplate, leaveId), {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest"
            },
            body: "",
            credentials: "same-origin"
        })
            .then(function (response)
            {
                const payloadPromise = typeof window.parseJsonOrSessionExpired === "function"
                    ? window.parseJsonOrSessionExpired(response)
                    : response.json().catch(function () { return {}; });
                return payloadPromise.then(function (payload)
                {
                    if (payload.sessionExpired)
                    {
                        if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(payload);
                        return payload;
                    }
                    if (!response.ok)
                    {
                        throw new Error(payload.detail || "Unable to approve leave.");
                    }

                    return payload;
                });
            })
            .then(function (payload)
            {
                if (payload && payload.sessionExpired)
                {
                    renderFlashMessages(payload.messages);
                    return;
                }
                renderFlashMessages(payload.messages);
                refreshEmployeeModalAfterAction(payload.employee_detail, "approved");
                refreshHrNotificationsAfterDecision(leaveId);
            })
            .catch(function (error)
            {
                showPopupActionError(error && error.message ? error.message : "Unable to approve leave.");
            })
            .finally(function ()
            {
                setPopupActionLoading(false);
            });
    }

    function approveLeaveFromPopup(leaveId)
    {
        const leave = findCurrentEmployeeLeave(leaveId);

        if (!leave || popupActionInFlight)
        {
            return;
        }

        openDecisionConfirm({
            variant: "approve",
            leave: leave,
            trigger: window.lastModalTrigger
        }).then(function (confirmed)
        {
            if (!confirmed)
            {
                return;
            }

            approveLeaveRequest(leaveId);
        });
    }

    function rejectLeaveFromPopup(leaveId, rejectionReason)
    {
        if (popupActionInFlight || !currentEmployeeDetail)
        {
            return Promise.resolve();
        }

        setPopupActionLoading(true);

        return fetch(getLeaveActionUrl(rejectLeaveUrlTemplate, leaveId), {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest"
            },
            body: "rejection_reason=" + encodeURIComponent(rejectionReason || ""),
            credentials: "same-origin"
        })
            .then(function (response)
            {
                const payloadPromise = typeof window.parseJsonOrSessionExpired === "function"
                    ? window.parseJsonOrSessionExpired(response)
                    : response.json().catch(function () { return {}; });
                return payloadPromise.then(function (payload)
                {
                    if (payload.sessionExpired)
                    {
                        if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(payload);
                        return payload;
                    }
                    if (!response.ok)
                    {
                        throw new Error(payload.detail || "Unable to reject leave.");
                    }

                    return payload;
                });
            })
            .then(function (payload)
            {
                if (payload && payload.sessionExpired)
                {
                    renderFlashMessages(payload.messages);
                    return payload;
                }
                return payload;
            })
            .catch(function (error)
            {
                showPopupActionError(error && error.message ? error.message : "Unable to reject leave.");
                throw error;
            })
            .finally(function ()
            {
                setPopupActionLoading(false);
            });
    }

    function animateManageDirectoryPageSwitch()
    {
        if (!manageEmployeeDirectory)
        {
            return;
        }

        const grid = manageEmployeeDirectory.querySelector(".employee-grid");
        if (!grid)
        {
            return;
        }

        if (manageDirectoryAnimationTimer)
        {
            clearTimeout(manageDirectoryAnimationTimer);
        }

        grid.classList.remove("is-page-switching");
        requestAnimationFrame(function ()
        {
            grid.classList.add("is-page-switching");
            manageDirectoryAnimationTimer = setTimeout(function ()
            {
                grid.classList.remove("is-page-switching");
                manageDirectoryAnimationTimer = null;
            }, 260);
        });
    }

    function getInitials(fullName, username)
    {
        const normalizedName = String(fullName || "").trim();
        const normalizedUsername = String(username || "").trim();
        const parts = normalizedName.split(/\s+/).filter(Boolean);

        if (parts.length >= 2)
        {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }

        if (parts.length === 1)
        {
            return parts[0].slice(0, 2).toUpperCase();
        }

        return normalizedUsername.slice(0, 2).toUpperCase() || "EM";
    }

    function formatEmployeeBalanceText(used, total)
    {
        return `${used ?? 0} / ${total ?? 0}`;
    }

    function setEmployeeCardBalance(card, key, used, total)
    {
        const balance = card ? card.querySelector(`[data-card-balance="${key}"]`) : null;

        if (!balance)
        {
            return;
        }

        const nextText = formatEmployeeBalanceText(used, total);

        if (balance.textContent.trim() === nextText)
        {
            return;
        }

        balance.textContent = nextText;
        balance.classList.remove("count-pulse");
        void balance.offsetWidth;
        balance.classList.add("count-pulse");
    }

    function reloadEmployeeCardPhoto(image, photoUrl)
    {
        const reloadToken = String(Date.now()) + Math.random();
        image.dataset.photoReloadToken = reloadToken;

        fetch(photoUrl, {
            cache: "no-store",
            headers: {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache"
            }
        })
            .then(function (response)
            {
                if (!response.ok)
                {
                    throw new Error("Unable to refresh employee photo.");
                }

                return response.blob();
            })
            .then(function (blob)
            {
                if (image.dataset.photoReloadToken !== reloadToken)
                {
                    return;
                }

                const previousObjectUrl = image.dataset.employeePhotoObjectUrl || "";
                const nextObjectUrl = URL.createObjectURL(blob);

                image.src = nextObjectUrl;
                image.dataset.employeePhotoObjectUrl = nextObjectUrl;

                if (previousObjectUrl)
                {
                    URL.revokeObjectURL(previousObjectUrl);
                }
            })
            .catch(function ()
            {
                if (image.dataset.photoReloadToken === reloadToken)
                {
                    image.src = photoUrl;
                }
            });
    }

    function setEmployeeCardPhoto(card, employee, options)
    {
        const photoWrap = card ? card.querySelector("[data-employee-card-photo]") : null;

        if (!photoWrap || !employee)
        {
            return;
        }

        const displayName = employee.display_name || employee.username || "Employee";
        const username = employee.username || "";

        if (employee.photo_url)
        {
            let image = photoWrap.querySelector("img.employee-photo");

            if (!image)
            {
                image = document.createElement("img");
                image.className = "employee-photo";
                photoWrap.replaceChildren(image);
            }

            if (options && options.forcePhotoReload)
            {
                reloadEmployeeCardPhoto(image, employee.photo_url);
            }
            else if (image.getAttribute("src") !== employee.photo_url)
            {
                const previousObjectUrl = image.dataset.employeePhotoObjectUrl || "";
                image.src = employee.photo_url;

                if (previousObjectUrl)
                {
                    URL.revokeObjectURL(previousObjectUrl);
                    delete image.dataset.employeePhotoObjectUrl;
                }
            }

            image.alt = displayName;
            return;
        }

        let fallback = photoWrap.querySelector(".employee-photo-fallback");

        if (!fallback)
        {
            fallback = document.createElement("div");
            fallback.className = "employee-photo employee-photo-fallback";
            fallback.setAttribute("data-avatar-fallback", "");
            photoWrap.replaceChildren(fallback);
        }

        fallback.setAttribute("aria-label", displayName);
        fallback.dataset.fullName = displayName;
        fallback.dataset.username = username;
        fallback.textContent = getInitials(displayName, username);
    }

    function updateEmployeeCardFromSnapshot(employee, options)
    {
        if (!employee || !employee.id)
        {
            return;
        }

        const card = document.querySelector(`.employee-profile-card[data-employee-id="${String(employee.id)}"]`);

        if (!card)
        {
            return;
        }

        setEmployeeCardPhoto(card, employee, options);
        setEmployeeCardBalance(card, "sick", employee.sick_used, employee.sick_total);
        setEmployeeCardBalance(card, "earned", employee.earned_used, employee.earned_total);
    }

    function getEmployeeBellItems()
    {
        return Array.from(document.querySelectorAll("[data-employee-bell-item]"));
    }

    function getRenderedMainNotifications()
    {
        if (!notificationDropdown)
        {
            return [];
        }

        return Array.from(notificationDropdown.querySelectorAll("[data-notification-item][data-notification-id]")).map(function (item)
        {
            return {
                id: String(item.dataset.notificationId || ""),
                employee_id: String(item.dataset.notificationEmployeeId || ""),
                leave_type_class: String((item.className.match(/notification-item-([a-z-]+)/) || [])[1] || item.dataset.notificationTypeClass || "default"),
                leave_type: String((item.querySelector(".notification-type") || {}).textContent || "").trim(),
                schedule_text: String((item.querySelector(".notification-subtitle") || {}).textContent || "").trim(),
                activity_line: String((item.querySelector(".notification-time") || {}).textContent || "").trim(),
                is_read: item.dataset.notificationRead === "true",
                is_new: item.dataset.notificationNew === "true"
            };
        }).filter(function (item)
        {
            return item.id && item.employee_id;
        });
    }

    function normalizeEmployeeBellNotifications(notifications)
    {
        return (Array.isArray(notifications) ? notifications : []).map(function (item)
        {
            const fallbackActivityLine = String(
                item.activity_line || ((item.activity_label || "") + " " + (item.activity_text || item.created_at || "")).trim()
            );
            const normalizedActivityLine = String(item.updated_text || "").trim()
                ? ("Updated " + String(item.updated_text || "").trim())
                : fallbackActivityLine.replace(/^Applied\s+(.+?)\s*\/\s*Updated\s+(.+)$/i, "Updated $2");

            return {
                id: String(item.id || ""),
                employee_id: String(item.employee_id || ""),
                leave_type: String(item.leave_type || "Leave"),
                leave_type_class: String(item.leave_type_class || "default"),
                schedule_text: String(item.schedule_text || ""),
                activity_label: String(item.activity_label || ""),
                activity_text: String(item.activity_text || item.created_at || ""),
                activity_line: normalizedActivityLine,
                is_read: !!item.is_read,
                is_new: !!item.is_new && !item.is_read
            };
        }).filter(function (item)
        {
            return item.id && item.employee_id;
        });
    }

    function renderEmployeeBellItem(item, employeeId)
    {
        const itemId = String(item.id || "");
        const leaveTypeClass = item.leave_type_class || "default";
        const isRead = employeeBellState.readIds.has(itemId);
        const isNew = employeeBellState.highlightedIds.has(itemId) && !isRead;
        const scheduleText = String(item.schedule_text || "").trim();
        const activityLine = String(item.activity_line || "").trim();
        const leaveSymbolMap = {
            earned: "&#9733;",
            sick: "+",
            unpaid: "&#9673;",
            short: "&#9684;",
            half: "&#9681;",
            default: "&#8226;"
        };
        const leaveSymbol = leaveSymbolMap[leaveTypeClass] || leaveSymbolMap.default;

        return (
            '<div class="employee-bell-item employee-bell-item-' + escapeHtml(leaveTypeClass) + (isRead ? ' is-read' : '') + (isNew ? ' is-new' : '') + '"' +
                ' data-employee-bell-item' +
                ' data-employee-id="' + escapeHtml(employeeId) + '"' +
                ' data-leave-id="' + escapeHtml(itemId) + '"' +
                ' data-leave-new="' + (isNew ? 'true' : 'false') + '"' +
                ' role="button" tabindex="0"' +
                ' aria-label="Open ' + escapeHtml(item.leave_type || "leave") + ' request details">' +
                '<strong><span class="employee-bell-type-symbol employee-bell-type-symbol-' + escapeHtml(leaveTypeClass) + '">' + escapeHtml(leaveSymbol) + '</span><span>' + escapeHtml(item.leave_type || "Leave") + '</span></strong>' +
                '<small class="employee-bell-schedule">' + escapeHtml(scheduleText) + '</small>' +
                '<small class="employee-bell-activity">' + escapeHtml(activityLine) + '</small>' +
            '</div>'
        );
    }

    function animateEmployeeBellCounts(forceFromZero)
    {
        const animateFromZeroOnThisPass = !!forceFromZero && !hasAnimatedEmployeeBellInitialCount;
        let animatedNonZero = false;

        employeeBellDropdowns.forEach(function (dropdown)
        {
            const badgeCount = dropdown.querySelector(".employee-bell-count");
            const panelCount = dropdown.querySelector(".employee-bell-panel-header span");
            const targetValue = Number(
                (panelCount && panelCount.dataset.countupTarget) ||
                (badgeCount && badgeCount.dataset.countupTarget) ||
                0
            );
            const count = Number.isFinite(targetValue) ? targetValue : 0;
            const previousBadgeValue = badgeCount ? Number(badgeCount.dataset.countupLastValue || 0) : 0;
            const previousPanelValue = panelCount ? Number(panelCount.dataset.countupLastValue || 0) : 0;

            if (animateFromZeroOnThisPass && count > 0)
            {
                animatedNonZero = true;
            }

            if (badgeCount && typeof window.animateCountUp === "function")
            {
                window.animateCountUp(badgeCount, count, {
                    duration: 260,
                    from: animateFromZeroOnThisPass && count > 0 ? 0 : previousBadgeValue,
                    force: true
                });
                badgeCount.dataset.countupLastValue = String(count);
            }
            else if (badgeCount)
            {
                badgeCount.textContent = String(count);
                badgeCount.dataset.countupLastValue = String(count);
            }

            if (panelCount && typeof window.animateCountUp === "function")
            {
                window.animateCountUp(panelCount, count, {
                    duration: 260,
                    from: animateFromZeroOnThisPass && count > 0 ? 0 : previousPanelValue,
                    force: true
                });
                panelCount.dataset.countupLastValue = String(count);
            }
            else if (panelCount)
            {
                panelCount.textContent = String(count);
                panelCount.dataset.countupLastValue = String(count);
            }
        });

        if (animateFromZeroOnThisPass && animatedNonZero)
        {
            hasAnimatedEmployeeBellInitialCount = true;
        }
    }

    function renderEmployeeBellDropdowns(options)
    {
        const settings = options || {};
        const groupedNotifications = new Map();

        employeeBellState.notifications.forEach(function (item)
        {
            if (!groupedNotifications.has(item.employee_id))
            {
                groupedNotifications.set(item.employee_id, []);
            }

            groupedNotifications.get(item.employee_id).push(item);
        });

        employeeBellDropdowns.forEach(function (dropdown)
        {
            const employeeId = String(dropdown.dataset.employeeId || "");
            const bellList = dropdown.querySelector(".employee-bell-list");
            const panelCount = dropdown.querySelector(".employee-bell-panel-header span");
            const badgeCount = dropdown.querySelector(".employee-bell-count");
            const newBadge = dropdown.querySelector(".employee-bell-new-badge");
            const markReadButton = dropdown.querySelector("[data-employee-bell-mark-read]");
            const employeeNotifications = groupedNotifications.get(employeeId) || [];
            const unreadCount = employeeNotifications.filter(function (item)
            {
                return !employeeBellState.readIds.has(String(item.id || ""));
            }).length;
            const newCount = employeeNotifications.filter(function (item)
            {
                const itemId = String(item.id || "");
                return employeeBellState.highlightedIds.has(itemId) && !employeeBellState.readIds.has(itemId);
            }).length;

            if (bellList)
            {
                window.setSafeHTML(bellList, employeeNotifications.length
                    ? employeeNotifications.map(function (item)
                    {
                        return renderEmployeeBellItem(item, employeeId);
                    }).join("")
                    : '<div class="employee-bell-empty">' +
                        '<div class="profile-bell-zone">' +
                            '<div class="notif-icon-visual">' +
                                '<div class="radiant-bell-container" role="img" aria-label="No pending requests">' +
                                    '<div class="svg-bell-wrapper">' +
                                        '<svg class="bell-svg" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
                                            '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" class="bell-body-outline"></path>' +
                                            '<path d="M13.73 21a2 2 0 0 1-3.46 0" class="bell-clapper-glow"></path>' +
                                        '</svg>' +
                                    '</div>' +
                                    '<div class="bell-echo echo-1"></div>' +
                                    '<div class="bell-echo echo-2"></div>' +
                                '</div>' +
                            '</div>' +
                            '<div class="notif-empty-copy">' +
                                '<span class="notif-empty-title">No pending requests.</span>' +
                            '</div>' +
                        '</div>' +
                    '</div>');
            }

            dropdown.classList.toggle("has-alert", unreadCount > 0);
            dropdown.setAttribute("aria-label", unreadCount + " unread pending requests");

            if (panelCount)
            {
                panelCount.textContent = String(unreadCount);
                panelCount.dataset.countupTarget = String(unreadCount);
            }

            if (badgeCount)
            {
                badgeCount.textContent = unreadCount > 0 ? String(unreadCount) : "";
                badgeCount.dataset.countupTarget = String(unreadCount);
                badgeCount.hidden = unreadCount <= 0;
                badgeCount.classList.toggle("hidden", unreadCount <= 0);
            }

            if (newBadge)
            {
                newBadge.textContent = newCount > 0 ? String(newCount) : "";
                newBadge.hidden = newCount <= 0;
                newBadge.classList.toggle("hidden", newCount <= 0);
            }

            if (markReadButton)
            {
                markReadButton.classList.toggle("is-disabled", unreadCount <= 0);
                markReadButton.setAttribute("aria-disabled", unreadCount <= 0 ? "true" : "false");
                markReadButton.tabIndex = unreadCount <= 0 ? -1 : 0;
            }

        });

        animateEmployeeBellCounts(settings.animateFromZero === true);
    }

    function applyEmployeeBellState(detail, options)
    {
        const settings = options || {};
        const normalizedNotifications = normalizeEmployeeBellNotifications(
            Array.isArray(detail && detail.notifications) ? detail.notifications : getRenderedMainNotifications()
        );
        const normalizedReadIds = Array.isArray(detail && detail.readIds)
            ? detail.readIds.map(String).filter(Boolean)
            : normalizedNotifications.filter(function (item) { return item.is_read; }).map(function (item) { return item.id; });
        const normalizedHighlightedIds = Array.isArray(detail && detail.highlightedIds)
            ? detail.highlightedIds.map(String).filter(Boolean)
            : normalizedNotifications.filter(function (item) { return item.is_new && !item.is_read; }).map(function (item) { return item.id; });

        employeeBellState.notifications = normalizedNotifications;
        employeeBellState.readIds = new Set(normalizedReadIds);
        employeeBellState.highlightedIds = new Set(normalizedHighlightedIds.filter(function (id)
        {
            return !employeeBellState.readIds.has(id);
        }));

        renderEmployeeBellDropdowns(settings);
    }

    function syncEmployeeBellFromMainRenderedState(options)
    {
        const renderedNotifications = getRenderedMainNotifications();
        const detail = {
            notifications: renderedNotifications,
            readIds: renderedNotifications.filter(function (item)
            {
                return item.is_read;
            }).map(function (item)
            {
                return item.id;
            }),
            highlightedIds: renderedNotifications.filter(function (item)
            {
                return item.is_new && !item.is_read;
            }).map(function (item)
            {
                return item.id;
            })
        };

        applyEmployeeBellState(detail, options);
    }

    function scheduleEmployeeBellBootstrap()
    {
        syncEmployeeBellFromMainRenderedState({ animateFromZero: true });

        [60, 180, 420].forEach(function (delay)
        {
            window.setTimeout(function ()
            {
                syncEmployeeBellFromMainRenderedState();
            }, delay);
        });
    }

    function broadcastEmployeeBellState()
    {
        window.dispatchEvent(new CustomEvent("hr-notification-state-sync", {
            detail: {
                apiUrl: notificationApiUrl,
                userKey: notificationUserKey,
                notifications: employeeBellState.notifications.slice(),
                readIds: Array.from(employeeBellState.readIds),
                highlightedIds: Array.from(employeeBellState.highlightedIds)
            }
        }));
    }

    function markManageBellNotificationAsRead(leaveId)
    {
        if (!leaveId || !notificationApiUrl)
        {
            return;
        }

        const normalizedLeaveId = String(leaveId);
        employeeBellState.readIds.add(normalizedLeaveId);
        employeeBellState.highlightedIds.delete(normalizedLeaveId);
        renderEmployeeBellDropdowns();
        broadcastEmployeeBellState();

        fetch("/api/notifications/read/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify({ ids: [normalizedLeaveId] })
        }).catch(function () {});
    }

    function markManageBellNotificationsSeen(leaveIds)
    {
        const ids = Array.isArray(leaveIds)
            ? leaveIds.map(function (value) { return String(value || "").trim(); }).filter(Boolean)
            : [];

        if (!ids.length)
        {
            return;
        }

        ids.forEach(function (leaveId)
        {
            employeeBellState.highlightedIds.delete(String(leaveId));
        });

        renderEmployeeBellDropdowns();
        broadcastEmployeeBellState();

        fetch("/api/notifications/seen/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify({ ids: ids })
        }).catch(function () {});
    }

    function markEmployeeBellAllRead(employeeId)
    {
        if (!employeeId || !notificationApiUrl)
        {
            return;
        }

        const idsToMark = employeeBellState.notifications.filter(function (item)
        {
            return String(item.employee_id) === String(employeeId) && !employeeBellState.readIds.has(String(item.id || ""));
        }).map(function (item)
        {
            return String(item.id || "");
        }).filter(Boolean);

        if (!idsToMark.length)
        {
            return;
        }

        idsToMark.forEach(function (leaveId)
        {
            employeeBellState.readIds.add(leaveId);
            employeeBellState.highlightedIds.delete(leaveId);
        });

        renderEmployeeBellDropdowns();
        broadcastEmployeeBellState();

        fetch("/api/notifications/read/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify({ ids: idsToMark })
        }).catch(function () {});
    }

    function setDetailAvatar(selected)
    {
        const photo = document.getElementById("detailPhoto");
        const fallback = document.getElementById("detailPhotoFallback");
        const displayName = selected.display_name || selected.username || "Employee";
        const username = selected.username || "";

        photo.alt = displayName;
        fallback.setAttribute("aria-label", displayName);
        fallback.dataset.fullName = displayName;
        fallback.dataset.username = username;
        fallback.textContent = getInitials(displayName, username);

        if (selected.photo_url)
        {
            photo.src = selected.photo_url;
            photo.classList.remove("hidden");
            fallback.classList.add("hidden");
            return;
        }

        photo.src = defaultProfileImage;
        photo.classList.add("hidden");
        fallback.classList.remove("hidden");
    }

    function escapeHtml(value)
    {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function setMobileSummarySet(summarySet)
    {
        if (!employeeSummaryPanel)
        {
            return;
        }

        employeeSummaryPanel.dataset.mobileSet = summarySet;
        mobileSummaryTabs.forEach(function (tab)
        {
            const isActive = tab.dataset.summarySet === summarySet;
            tab.classList.toggle("is-active", isActive);
            tab.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
    }

    function getMatchingEmployeeCards(searchValue)
    {
        const query = String(searchValue || "").trim().toLowerCase();
        return employeeProfileCards.filter(function (card)
        {
            const haystack = [
                card.dataset.searchName || "",
                card.dataset.searchUsername || "",
                card.dataset.searchEmployeeId || "",
                card.dataset.searchPhone || "",
                card.dataset.searchDepartment || ""
            ].join(" ");

            return !query || haystack.includes(query);
        });
    }

    function renderManageDirectoryPagination(totalPages)
    {
        if (!manageDirectoryPagination)
        {
            return;
        }

        if (totalPages <= 1)
        {
            manageDirectoryPagination.hidden = true;
            manageDirectoryPagination.replaceChildren();
            return;
        }

        manageDirectoryPagination.hidden = false;
        window.setSafeHTML(manageDirectoryPagination, `
            <button
                type="button"
                class="directory-page-btn directory-page-nav"
                data-manage-nav="first"
                ${manageDirectoryCurrentPage === 1 ? "disabled" : ""}
                aria-label="First page"
            ><span aria-hidden="true">&laquo;</span><span>First</span></button>
            <button
                type="button"
                class="directory-page-btn directory-page-nav"
                data-manage-nav="prev"
                ${manageDirectoryCurrentPage === 1 ? "disabled" : ""}
                aria-label="Previous page"
            ><span aria-hidden="true">&lsaquo;</span><span>Prev</span></button>
            <span class="directory-page-status">Page ${manageDirectoryCurrentPage} of ${totalPages}</span>
            <button
                type="button"
                class="directory-page-btn directory-page-nav"
                data-manage-nav="next"
                ${manageDirectoryCurrentPage === totalPages ? "disabled" : ""}
                aria-label="Next page"
            ><span>Next</span><span aria-hidden="true">&rsaquo;</span></button>
            <button
                type="button"
                class="directory-page-btn directory-page-nav"
                data-manage-nav="last"
                ${manageDirectoryCurrentPage === totalPages ? "disabled" : ""}
                aria-label="Last page"
            ><span>Last</span><span aria-hidden="true">&raquo;</span></button>
        `);
    }

    function renderManageDirectory(searchValue, options)
    {
        const settings = options || {};
        const query = String(searchValue || "").trim().toLowerCase();
        const matchingCards = getMatchingEmployeeCards(query);
        const pageSize = getManageDirectoryPageSize();
        const totalPages = Math.max(1, Math.ceil(matchingCards.length / pageSize));

        if (settings.page)
        {
            manageDirectoryCurrentPage = Math.min(Math.max(1, settings.page), totalPages);
        }
        else if (manageDirectoryCurrentPage > totalPages)
        {
            manageDirectoryCurrentPage = totalPages;
        }

        const startIndex = (manageDirectoryCurrentPage - 1) * pageSize;
        const visibleCards = new Set(matchingCards.slice(startIndex, startIndex + pageSize));

        employeeProfileCards.forEach(function (card)
        {
            card.hidden = !visibleCards.has(card);
        });

        employeePlaceholderCards.forEach(function (card, index)
        {
            const shouldShowPlaceholder = matchingCards.length > 0 && index < Math.max(0, pageSize - visibleCards.size);
            card.hidden = !shouldShowPlaceholder;
        });

        if (employeeSearchEmpty)
        {
            employeeSearchEmpty.hidden = query === "" || matchingCards.length !== 0;
        }

        if (employeeCountBadge)
        {
            employeeCountBadge.dataset.count = String(matchingCards.length);
            employeeCountBadge.dataset.countupTarget = String(matchingCards.length);
            if (typeof window.animateCountUp === "function")
            {
                window.animateCountUp(employeeCountBadge, matchingCards.length, { suffix: " members", duration: 280 });
            }
            else
            {
                employeeCountBadge.textContent = matchingCards.length + " members";
            }
        }

        renderManageDirectoryPagination(matchingCards.length > 0 ? Math.max(1, totalPages) : 0);
        manageDirectoryLastPageSize = pageSize;
        animateEmployeeBellCounts();
        refreshManageAllLiveData();

        return {
            matchingCards: matchingCards,
            totalPages: totalPages
        };
    }

    function goToManageDirectoryPage(pageNumber)
    {
        runManageDirectoryTransition(function ()
        {
            renderManageDirectory(employeeSearchInput ? employeeSearchInput.value : "", { page: pageNumber });
            animateManageDirectoryPageSwitch();
        });
    }

    function revealEmployeeCard(employeeId)
    {
        const targetCard = employeeProfileCards.find(function (card)
        {
            return String(card.dataset.employeeId) === String(employeeId);
        });

        if (!targetCard)
        {
            return false;
        }

        const query = employeeSearchInput ? employeeSearchInput.value : "";
        const matchingCards = getMatchingEmployeeCards(query);
        const targetIndex = matchingCards.findIndex(function (card)
        {
            return String(card.dataset.employeeId) === String(employeeId);
        });

        if (targetIndex === -1)
        {
            return false;
        }

        const pageNumber = Math.floor(targetIndex / getManageDirectoryPageSize()) + 1;
        renderManageDirectory(query, { page: pageNumber });

        requestAnimationFrame(function ()
        {
            targetCard.scrollIntoView({ behavior: "smooth", block: "center" });
        });

        return true;
    }

    function runManageDirectoryTransition(updateFn)
    {
        if (typeof updateFn !== "function")
        {
            return;
        }

        if (!manageEmployeeDirectory || typeof window.startAsyncSurfaceSkeleton !== "function" || typeof window.finishAsyncSurfaceSkeleton !== "function")
        {
            updateFn();
            return;
        }

        window.startAsyncSurfaceSkeleton(manageEmployeeDirectory);

        requestAnimationFrame(function ()
        {
            updateFn();

            requestAnimationFrame(function ()
            {
                window.finishAsyncSurfaceSkeleton(manageEmployeeDirectory);

                requestAnimationFrame(function ()
                {
                    animateEmployeeBellCounts();
                });
            });
        });
    }

    function closeEmployeeBellDropdowns()
    {
        const seenLeaveIds = [];

        employeeBellDropdowns.forEach(function (dropdown)
        {
            const wasOpen = dropdown.classList.contains("is-open");

            if (wasOpen)
            {
                Array.from(dropdown.querySelectorAll('[data-employee-bell-item][data-leave-new="true"]')).forEach(function (item)
                {
                    const leaveId = String(item.dataset.leaveId || "");

                    if (leaveId)
                    {
                        seenLeaveIds.push(leaveId);
                    }
                });
            }

            dropdown.classList.remove("is-open");
            const card = dropdown.closest(".employee-profile-card");
            const panel = dropdown.querySelector(".employee-bell-panel");

            if (card)
            {
                card.classList.remove("has-open-bell");
            }

            if (panel)
            {
                panel.classList.remove("is-align-left", "is-align-right", "is-align-center");
            }
        });

        if (seenLeaveIds.length)
        {
            markManageBellNotificationsSeen(seenLeaveIds);
        }
    }

    function positionEmployeeBellDropdown(dropdown)
    {
        const panel = dropdown.querySelector(".employee-bell-panel");

        if (!panel)
        {
            return;
        }

        panel.classList.remove("is-align-left", "is-align-right", "is-align-center");

        if (window.innerWidth > 640)
        {
            panel.classList.add("is-align-left");
            return;
        }

        const rect = dropdown.getBoundingClientRect();
        const panelWidth = Math.min(162, window.innerWidth - 24);
        const spaceToRight = window.innerWidth - rect.left;
        const spaceToLeft = rect.right;

        if (spaceToRight >= panelWidth + 8)
        {
            panel.classList.add("is-align-right");
        }
        else if (spaceToLeft >= panelWidth + 8)
        {
            panel.classList.add("is-align-left");
        }
        else
        {
            panel.classList.add("is-align-center");
        }
    }

    function updateEmployeeCardDensity(card)
    {
        if (!card)
        {
            return;
        }

        const cardWidth = card.getBoundingClientRect().width;
        card.classList.toggle("is-tight", cardWidth <= 455);
        card.classList.toggle("is-ultra-tight", cardWidth <= 405);
    }

    function updateAllEmployeeCardDensity()
    {
        employeeProfileCards.forEach(function (card)
        {
            updateEmployeeCardDensity(card);
        });
        animateEmployeeBellCounts();
    }
    function renderPopupTableHead(status)
    {
        const definition = popupHistoryDefinitions[status] || popupHistoryDefinitions.pending;

        if (!detailTableHead || !detailHistoryTable)
        {
            return;
        }

        detailHistoryTable.dataset.view = status;
        window.setSafeHTML(detailTableHead, `
            <tr>
                ${definition.columns.map(function (column)
                {
                    return `
                        <th data-column-key="${escapeHtml(column.key)}">
                            <span class="detail-th-content">
                                <span class="detail-th-icon" aria-hidden="true">${getPopupHistoryHeaderIcon(column.key)}</span>
                                <span class="detail-th-label">${escapeHtml(column.label)}</span>
                            </span>
                        </th>
                    `;
                }).join("")}
            </tr>
        `);
    }
    function renderEmptyRow(status)
    {
        const definition = popupHistoryDefinitions[status] || popupHistoryDefinitions.pending;

        return `
            <tr class="cosmic-tr">
                <td colspan="${definition.columns.length}">
                    <div class="cosmic-empty-state ${definition.themeClass}">
                        <div class="cosmic-interactive-core">
                            <div class="cosmic-visual-zone">
                                <div class="cosmic-aura"></div>
                                <div class="cosmic-particle-field">
                                    <span class="cosmic-dot v1"></span>
                                    <span class="cosmic-dot v2"></span>
                                    <span class="cosmic-dot v3"></span>
                                    <span class="cosmic-dot v4"></span>
                                    <span class="cosmic-dot v5"></span>
                                </div>
                                <div class="cosmic-stars">
                                    <span class="c-star s1"></span>
                                    <span class="c-star s2"></span>
                                    <span class="c-star s3"></span>
                                    <span class="c-star s4"></span>
                                    <span class="c-star s5"></span>
                                    <span class="c-star s6"></span>
                                    <span class="c-star s7"></span>
                                    <span class="c-star s8"></span>
                                </div>
                                <div class="cosmic-icon-anchor">
                                    <div class="cosmic-icon-reveal-wrapper">
                                        ${definition.emptyIcon}
                                    </div>
                                </div>
                            </div>
                            <div class="cosmic-content">
                                <strong class="cosmic-title">${escapeHtml(definition.emptyTitle)}</strong>
                                <p class="cosmic-message">${escapeHtml(definition.emptyMessage)}</p>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    function renderLeaveRow(leave, index, status)
    {
        const leaveSymbolMap = {
            sick: "+",
            unpaid: "&#9749;",
            earned: "&#9733;",
            short: "&#9201;",
            half: "&#9680;",
            default: "&#10023;"
        };
        const leaveSymbol = leaveSymbolMap[leave.type_class] || leaveSymbolMap.default;
        const leaveDayCount = String(leave.days_value_display || calculateLeaveDayCount(leave.from_date, leave.to_date, leave.type));
        const leaveDayValue = Number.parseFloat(leave.days_target ?? leave.days_value ?? leaveDayCount);
        const leaveDaySuffix = leave.days_suffix != null ? String(leave.days_suffix) : leaveDayCount.replace(/^[\d.]+\s*/, "");
        const canAnimateLeaveDay = Number.isFinite(leaveDayValue) && Number.isInteger(leaveDayValue);
        const leaveDayChip = canAnimateLeaveDay
            ? `<span class="leave-day-chip" data-day-value="${leaveDayValue}" data-day-suffix="${escapeHtml(leaveDaySuffix)}">${escapeHtml(leaveDayCount)}</span>`
            : `<span class="leave-day-chip">${escapeHtml(leaveDayCount)}</span>`;
        const scheduleDateModalText = `${leave.from_date || "-"} -> ${leave.to_date || "-"}`;
        const scheduleTimeModalText = leave.from_time && leave.to_time
            ? `${leave.from_time} -> ${leave.to_time}`
            : "Full day";
        const reasonEmployeeName = currentEmployeeDetail && (currentEmployeeDetail.display_name || currentEmployeeDetail.name || currentEmployeeDetail.username)
            ? (currentEmployeeDetail.display_name || currentEmployeeDetail.name || currentEmployeeDetail.username)
            : (leave.employee_name || "Employee");
        const reasonMetaAttributes = [
            `data-employee="${escapeHtml(reasonEmployeeName)}"`,
            `data-leave-type="${escapeHtml(leave.type || "Leave")}"`,
            `data-leave-type-class="${escapeHtml(leave.type_class || "default")}"`,
            `data-history-status="${escapeHtml(status || "pending")}"`,
            `data-schedule-date="${escapeHtml(scheduleDateModalText)}"`,
            `data-schedule-time="${escapeHtml(scheduleTimeModalText)}"`,
            `data-days-display="${escapeHtml(leaveDayCount)}"`,
            `data-applied="${escapeHtml(leave.applied_at || "-")}"`,
            `data-applied-iso="${escapeHtml(leave.applied_at_iso || "")}"`,
            `data-updated="${escapeHtml(leave.updated_at || "-")}"`,
            `data-updated-iso="${escapeHtml(leave.updated_at_iso || "")}"`,
            `data-updated-count="${escapeHtml(String(leave.no_of_times_updated || 0))}"`,
            `data-reviewer="${escapeHtml(leave.reviewed_by || "HR Team")}"`
        ].join(" ");
        const timeHighlightClass = (leave.type_class === "short" || leave.type_class === "half")
            ? ` schedule-time-highlight schedule-time-highlight-${escapeHtml(leave.type_class)}`
            : "";
        const scheduleText = leave.from_time && leave.to_time
            ? `
                <div class="schedule-line">
                    <span class="meta-icon">&#128197;</span>
                    <strong>${escapeHtml(leave.from_date)}</strong>
                    <span class="range-arrow">&rarr;</span>
                    <strong>${escapeHtml(leave.to_date)}</strong>
                </div>
                <div class="schedule-line schedule-time${timeHighlightClass}">
                    <span class="meta-icon">&#128339;</span>
                    <span>${escapeHtml(leave.from_time)}</span>
                    <span class="range-arrow${timeHighlightClass ? "" : " normal-time-range-arrow"}">&rarr;</span>
                    <span>${escapeHtml(leave.to_time)}</span>
                </div>
            `
            : `
                <div class="schedule-line">
                    <span class="meta-icon">&#128197;</span>
                    <strong>${escapeHtml(leave.from_date)}</strong>
                    <span class="range-arrow">&rarr;</span>
                    <strong>${escapeHtml(leave.to_date)}</strong>
                </div>
                <div class="schedule-line schedule-time">
                    <span class="meta-icon">&#128339;</span>
                    <span>Full day</span>
                </div>
            `;
        const baseCells = `
            <td><span class="serial-chip">${index + 1}</span></td>
            <td>
                <span class="leave-type-pill leave-type-pill-${escapeHtml(leave.type_class)}">
                    <span class="leave-pill-symbol">${leaveSymbol}</span>
                    <span class="leave-pill-code">${escapeHtml(leave.type.slice(0, 1).toUpperCase())}</span>
                    <span>${escapeHtml(leave.type)}</span>
                </span>
            </td>
            <td><div class="schedule-stack">${scheduleText}</div></td>
            <td><div class="days-cell">${leaveDayChip}</div></td>
            <td>
                ${renderPopupDecisionBlock({
                    iso: leave.applied_at_iso,
                    fallback: leave.applied_at,
                    dateIcon: "&#128197;",
                    timeIcon: "&#128339;"
                })}
            </td>
        `;

        if (status === "pending")
        {
            return `
                <tr data-leave-id="${leave.id}">
                    ${baseCells}
                    <td>
                        ${renderPopupDecisionBlock({
                            iso: leave.updated_at_iso,
                            fallback: leave.updated_at,
                            dateIcon: "&#128198;",
                            timeIcon: "&#128345;",
                            dateIconClass: "meta-icon-updated",
                            timeIconClass: "meta-icon-updated-time",
                            count: leave.no_of_times_updated || 0
                        })}
                    </td>
                    <td>
                        <div class="reason-box">
                            <p class="reason-text" data-full="${escapeHtml(leave.reason)}" ${reasonMetaAttributes} data-reason-context="pending">${escapeHtml(leave.reason)}</p>
                        </div>
                    </td>
                    <td>
                        <div class="action-group compact-action-group">
                            <button type="button" class="approve-btn" data-action="approve-leave-popup" data-leave-id="${escapeHtml(leave.id)}">Approve</button>
                            <button type="button" class="reject-btn" data-action="open-reject" data-leave-id="${escapeHtml(leave.id)}">Reject</button>
                        </div>
                    </td>
                </tr>
            `;
        }

        if (status === "approved")
        {
            return `
                <tr data-leave-id="${leave.id}">
                    ${baseCells}
                    <td>
                        ${renderPopupDecisionBlock({
                            iso: leave.approved_at_iso,
                            fallback: leave.approved_at,
                            dateIcon: "&#10003;",
                            timeIcon: "&#128339;",
                            extraClass: "decision-block-approved"
                        })}
                    </td>
                    <td><div class="popup-reviewer-cell">${escapeHtml(leave.reviewed_by || "HR Team")}</div></td>
                    <td>
                        <div class="reason-box">
                            <p class="reason-text" data-full="${escapeHtml(leave.reason)}" ${reasonMetaAttributes} data-reason-context="approved" data-decision="${escapeHtml(leave.approved_at || "-")}" data-decision-iso="${escapeHtml(leave.approved_at_iso || "")}" data-decision-label="Approved At" data-reviewer-label="Approved By">${escapeHtml(leave.reason)}</p>
                        </div>
                    </td>
                </tr>
            `;
        }

        const rejectionReason = leave.rejection_reason && leave.rejection_reason !== "-" ? leave.rejection_reason : "No rejection note added.";

        return `
            <tr data-leave-id="${leave.id}">
                ${baseCells}
                <td>
                    ${renderPopupDecisionBlock({
                        iso: leave.rejected_at_iso,
                        fallback: leave.rejected_at,
                        dateIcon: "&#9940;",
                        timeIcon: "&#128339;",
                        extraClass: "decision-block-rejected"
                    })}
                </td>
                <td><div class="popup-reviewer-cell">${escapeHtml(leave.reviewed_by || "HR Team")}</div></td>
                <td>
                    <div class="reason-box">
                        <p class="reason-text" data-full="${escapeHtml(leave.reason)}" ${reasonMetaAttributes} data-reason-context="rejected-employee" data-decision="${escapeHtml(leave.rejected_at || "-")}" data-decision-iso="${escapeHtml(leave.rejected_at_iso || "")}" data-decision-label="Rejected At" data-reviewer-label="Rejected By">${escapeHtml(leave.reason)}</p>
                    </div>
                </td>
                <td>
                    <div class="reason-box rejection-box">
                        <p class="reason-text action-reason-text" data-full="${escapeHtml(rejectionReason)}" ${reasonMetaAttributes} data-reason-context="rejected-note" data-modal-title="${escapeHtml(leave.type)} Rejection Reason" data-decision="${escapeHtml(leave.rejected_at || "-")}" data-decision-iso="${escapeHtml(leave.rejected_at_iso || "")}" data-decision-label="Rejected At" data-reviewer-label="Rejected By">${escapeHtml(rejectionReason)}</p>
                    </div>
                </td>
            </tr>
        `;
    }

    function renderPopupTableSkeletonRows(rowCount)
    {
        const totalRows = Math.max(1, Number(rowCount) || 5);
        const skeletonRowTemplate = `
            <tr class="detail-skeleton-row" aria-hidden="true">
                <td><span class="detail-skeleton-chip"></span></td>
                <td><span class="detail-skeleton-pill"></span></td>
                <td>
                    <div class="detail-skeleton-stack">
                        <span class="detail-skeleton-line w-90"></span>
                        <span class="detail-skeleton-line w-70"></span>
                    </div>
                </td>
                <td><span class="detail-skeleton-chip"></span></td>
                <td>
                    <div class="detail-skeleton-stack">
                        <span class="detail-skeleton-line w-70"></span>
                        <span class="detail-skeleton-line w-55"></span>
                    </div>
                </td>
                <td>
                    <div class="detail-skeleton-stack">
                        <span class="detail-skeleton-line w-95"></span>
                        <span class="detail-skeleton-line w-80"></span>
                    </div>
                </td>
                <td>
                    <div class="detail-skeleton-action-pair">
                        <span class="detail-skeleton-pill"></span>
                        <span class="detail-skeleton-pill"></span>
                    </div>
                </td>
            </tr>
        `;

        return Array.from({ length: totalRows }, function ()
        {
            return skeletonRowTemplate;
        }).join("");
    }

    function syncPopupTableViewportHeight()
    {
        if (!popupTableInner)
        {
            return;
        }

        const tableHead = document.getElementById("detailTableHead");
        const tableBody = document.getElementById("detailTableBody");

        if (!tableHead || !tableBody)
        {
            popupTableInner.style.maxHeight = "";
            return;
        }

        const visibleRows = Array.from(tableBody.querySelectorAll("tr")).filter(function (row)
        {
            return !row.classList.contains("detail-skeleton-row") && !row.querySelector(".empty-table-state");
        });

        const headerHeight = tableHead.offsetHeight || 0;
        const cache = syncPopupTableViewportHeight._rowHeightCache || (syncPopupTableViewportHeight._rowHeightCache = {
            pending: 56,
            approved: 56,
            rejected: 56
        });
        const currentStatus = activePopupHistoryStatus || "pending";

        if (visibleRows.length)
        {
            const sampleRows = visibleRows.slice(0, Math.min(5, visibleRows.length));
            const totalSampleHeight = sampleRows.reduce(function (sum, row)
            {
                return sum + row.offsetHeight;
            }, 0);
            const averageRowHeight = totalSampleHeight / sampleRows.length;

            if (averageRowHeight > 0)
            {
                cache[currentStatus] = averageRowHeight;
            }
        }

        const baseRowHeight = cache[currentStatus] || 56;
        const visibleRowCount = visibleRows.length ? Math.min(visibleRows.length, 5) : 1;
        const rowViewportHeight = baseRowHeight * visibleRowCount;
        const bufferHeight = 6;

        popupTableInner.style.maxHeight = Math.ceil(headerHeight + rowViewportHeight + bufferHeight) + "px";
    }

    function refreshPopupTableAfterLayout()
    {
        if (refreshPopupTableAfterLayout._timer)
        {
            clearTimeout(refreshPopupTableAfterLayout._timer);
            refreshPopupTableAfterLayout._timer = null;
        }

        const runRefresh = function ()
        {
            if (!popupTableInner || !document.body.contains(popupTableInner))
            {
                return;
            }

            const employeeModal = document.getElementById("employeeModal");

            if (employeeModal && employeeModal.getAttribute("aria-hidden") === "true")
            {
                return;
            }

            if (popupTableSection && popupTableSection.classList.contains("is-collapsed"))
            {
                return;
            }

            syncPopupTableViewportHeight();
            updateReasonButtons();
        };

        requestAnimationFrame(function ()
        {
            requestAnimationFrame(runRefresh);
        });

        refreshPopupTableAfterLayout._timer = window.setTimeout(runRefresh, 180);
    }

    function pulsePopupTableToggleSkeleton()
    {
        if (!popupTableSection)
        {
            return;
        }

        if (popupTableSection._toggleSkeletonTimer)
        {
            clearTimeout(popupTableSection._toggleSkeletonTimer);
            popupTableSection._toggleSkeletonTimer = null;
        }

        popupTableSection._toggleSkeletonTimer = window.setTimeout(function ()
        {
            popupTableSection.classList.add("table-toggle-loading");
            popupTableSection._toggleSkeletonTimer = null;
        }, 180);
    }

    function clearPopupTableToggleSkeleton()
    {
        if (!popupTableSection)
        {
            return;
        }

        if (popupTableSection._toggleSkeletonTimer)
        {
            clearTimeout(popupTableSection._toggleSkeletonTimer);
            popupTableSection._toggleSkeletonTimer = null;
        }

        popupTableSection.classList.remove("table-toggle-loading");
    }

    function calculateLeaveDayCount(fromDate, toDate, leaveType)
    {
        if (leaveType === "Short")
        {
            return "0.25 day";
        }

        if (leaveType === "Half")
        {
            return "0.5 day";
        }

        const start = new Date(fromDate);
        const end = new Date(toDate);

        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()))
        {
            return "1 day";
        }

        const startMs = start.setHours(0, 0, 0, 0);
        const endMs = end.setHours(0, 0, 0, 0);
        const totalDays = Math.floor((endMs - startMs) / 86400000) + 1;
        return `${totalDays} ${totalDays === 1 ? "day" : "days"}`;
    }

    function formatRelativeLeaveAge(isoValue)
    {
        if (!isoValue)
        {
            return null;
        }

        const target = new Date(isoValue);

        if (Number.isNaN(target.getTime()))
        {
            return null;
        }

        const diffMs = Date.now() - target.getTime();

        if (diffMs < 0)
        {
            return null;
        }

        const diffMinutes = Math.floor(diffMs / 60000);

        if (diffMinutes < 1)
        {
            return "Just now";
        }

        if (diffMinutes < 60)
        {
            return diffMinutes + " min" + (diffMinutes > 1 ? "s" : "") + " ago";
        }

        const diffHours = Math.floor(diffMinutes / 60);
        const minuteRemainder = diffMinutes % 60;

        if (diffHours < 24)
        {
            return diffHours + " hour" + (diffHours > 1 ? "s" : "") + ", " + minuteRemainder + " min ago";
        }

        const diffDays = Math.floor(diffHours / 24);

        if (diffDays === 1)
        {
            return "Yesterday";
        }

        if (diffDays < 7)
        {
            return diffDays + " days ago";
        }

        return null;
    }

    function formatPopupClockTime(isoValue, fallbackValue)
    {
        if (isoValue)
        {
            const target = new Date(isoValue);

            if (!Number.isNaN(target.getTime()))
            {
                return target.toLocaleTimeString("en-US", {
                    hour: "numeric",
                    minute: "2-digit",
                    hour12: true
                });
            }
        }

        if (fallbackValue)
        {
            const match = String(fallbackValue).match(/(\d{1,2}:\d{2}\s?[AP]M)/i);

            if (match)
            {
                return match[1].replace(/\s+/g, " ").toUpperCase();
            }
        }

        return "-";
    }

    function updateReasonButtons()
    {
        document.querySelectorAll(".reason-text").forEach(function (reasonText)
        {
            const fullText = reasonText.dataset.full || reasonText.textContent.trim();
            reasonText.classList.remove("is-truncated");
            reasonText.textContent = fullText;

            requestAnimationFrame(function ()
            {
                if (reasonText.scrollHeight <= reasonText.clientHeight + 2)
                {
                    return;
                }

                reasonText.classList.add("is-truncated");

                let trimmedText = fullText;
                let low = 0;
                let high = fullText.length;
                let bestFit = "";

                while (low <= high)
                {
                    const mid = Math.floor((low + high) / 2);
                    const candidate = fullText.slice(0, mid).trimEnd();
                    const testMoreLabel = document.createElement("span");
                    testMoreLabel.className = "reason-inline-more";
                    testMoreLabel.textContent = "...more";
                    reasonText.replaceChildren(document.createTextNode(candidate), testMoreLabel);

                    if (reasonText.scrollHeight <= reasonText.clientHeight + 2)
                    {
                        bestFit = candidate;
                        low = mid + 1;
                    }
                    else
                    {
                        high = mid - 1;
                    }
                }

                if (!bestFit)
                {
                    bestFit = trimmedText.slice(0, Math.max(8, Math.floor(trimmedText.length / 2))).trimEnd();
                }

                const moreLabel = document.createElement("span");
                moreLabel.className = "reason-inline-more";
                moreLabel.textContent = "...more";
                reasonText.replaceChildren(document.createTextNode(bestFit), moreLabel);
            });
        });
    }

    function animateTableDayChips()
    {
        document.querySelectorAll(".leave-day-chip[data-day-value]").forEach(function (chip)
        {
            const dayValue = Number(chip.dataset.dayValue || 0);
            const daySuffix = chip.dataset.daySuffix || "";

            chip.dataset.countupTarget = String(dayValue);

            if (typeof window.animateCountUp === "function")
            {
                window.animateCountUp(chip, dayValue, { duration: 260, suffix: daySuffix ? " " + daySuffix : "" });
                return;
            }

            chip.textContent = String(dayValue) + (daySuffix ? " " + daySuffix : "");
        });
    }

    function getPreferredPopupHistoryStatus(selected)
    {
        if (!selected)
        {
            return "pending";
        }

        if (selected.pending_count)
        {
            return "pending";
        }

        if (selected.approved_count)
        {
            return "approved";
        }

        if (selected.rejected_count)
        {
            return "rejected";
        }

        return "pending";
    }

    function updatePopupHistoryTabs(selected)
    {
        const valueMap = {
            pending: Number(selected && selected.pending_count ? selected.pending_count : 0),
            approved: Number(selected && selected.approved_count ? selected.approved_count : 0),
            rejected: Number(selected && selected.rejected_count ? selected.rejected_count : 0)
        };
        const countElementMap = {
            pending: document.getElementById("detailPendingTableCount"),
            approved: document.getElementById("detailApprovedTableCount"),
            rejected: document.getElementById("detailRejectedTableCount")
        };

        popupHistoryTabs.forEach(function (tab)
        {
            const status = tab.dataset.historyStatus;
            const isActive = status === activePopupHistoryStatus;
            const countElement = countElementMap[status];
            const value = valueMap[status] || 0;

            tab.classList.toggle("is-active", isActive);
            tab.setAttribute("aria-selected", isActive ? "true" : "false");

            if (!countElement)
            {
                return;
            }

            countElement.dataset.countupTarget = String(value);

            if (typeof window.animateCountUp === "function")
            {
                window.animateCountUp(countElement, value, { duration: 260 });
                return;
            }

            countElement.textContent = String(value);
        });
    }

    function renderPopupHistoryTable(selected)
    {
        syncPopupTabFilterIndicators();
        const tableBody = document.getElementById("detailTableBody");
        const detailTableCount = document.getElementById("detailTableCount");
        const detailHistoryTable = document.getElementById("detailHistoryTable");
        const popupTableWrapper = document.getElementById("popupTableWrapper");
        const definition = popupHistoryDefinitions[activePopupHistoryStatus] || popupHistoryDefinitions.pending;
        const formattedName = selected.display_name
            ? selected.display_name
            : selected.username
                ? selected.username.charAt(0).toUpperCase() + selected.username.slice(1)
                : "Employee";
        const statusLeaves = getPopupStatusLeaves(selected, activePopupHistoryStatus);
        const filteredLeaves = applyPopupHistoryFilters(statusLeaves, activePopupHistoryStatus);
        const popupHistoryPageSize = getPopupHistoryPageSize();
        const totalPages = Math.max(1, Math.ceil(filteredLeaves.length / popupHistoryPageSize));
        const currentPage = Math.min(getPopupHistoryPage(activePopupHistoryStatus), totalPages);
        const startIndex = (currentPage - 1) * popupHistoryPageSize;
        const pagedLeaves = filteredLeaves.slice(startIndex, startIndex + popupHistoryPageSize);

        setPopupHistoryPage(activePopupHistoryStatus, currentPage);

        updatePopupHistoryTabs(selected);
        renderPopupFilterBadges(activePopupHistoryStatus);
        window.setSafeHTML(document.getElementById("detailTableTitle"), `<span class="title-name-chip">${escapeHtml(formattedName)}</span><span class="title-separator">-</span><span class="title-label-chip title-label-chip-${escapeHtml(activePopupHistoryStatus)}">${escapeHtml(definition.heading)}</span>`);

        if (detailTableCount)
        {
            detailTableCount.dataset.count = filteredLeaves.length;
            window.setSafeHTML(detailTableCount, `<span class="popup-count-number">${filteredLeaves.length}</span><span class="popup-count-suffix">${escapeHtml(definition.countSuffix.trim())}</span>`);
        }

        window.setSafeHTML(tableBody, pagedLeaves.length
            ? pagedLeaves.map(function (leave, index)
            {
                return renderLeaveRow(leave, startIndex + index, activePopupHistoryStatus);
            }).join("")
            : renderEmptyRow(activePopupHistoryStatus));

        if (detailTableHead)
        {
            if (pagedLeaves.length)
            {
                renderPopupTableHead(activePopupHistoryStatus);
                detailTableHead.hidden = false;
            }
            else
            {
                detailTableHead.replaceChildren();
                detailTableHead.hidden = true;
            }
        }

        if (popupTableWrapper)
        {
            popupTableWrapper.classList.toggle("is-empty", pagedLeaves.length === 0);
        }

        if (popupTablePagination)
        {
            popupTablePagination.dataset.context = activePopupHistoryStatus;
            if (filteredLeaves.length <= popupHistoryPageSize)
            {
                popupTablePagination.hidden = true;
                popupTablePagination.replaceChildren();
            }
            else
            {
                const buttons = [];
                buttons.push(`<button type="button" class="popup-page-btn popup-page-nav"${currentPage === 1 ? " disabled" : ""} data-popup-page="1"><span aria-hidden="true">&laquo;</span><span>First</span></button>`);
                buttons.push(`<button type="button" class="popup-page-btn popup-page-nav"${currentPage === 1 ? " disabled" : ""} data-popup-page="${currentPage - 1}"><span aria-hidden="true">&#8249;</span><span>Prev</span></button>`);

                buttons.push(`<span class="popup-page-status" aria-live="polite">${currentPage} of ${totalPages}</span>`);

                buttons.push(`<button type="button" class="popup-page-btn popup-page-nav"${currentPage === totalPages ? " disabled" : ""} data-popup-page="${currentPage + 1}"><span>Next</span><span aria-hidden="true">&#8250;</span></button>`);
                buttons.push(`<button type="button" class="popup-page-btn popup-page-nav"${currentPage === totalPages ? " disabled" : ""} data-popup-page="${totalPages}"><span>Last</span><span aria-hidden="true">&raquo;</span></button>`);

                window.setSafeHTML(popupTablePagination, buttons.join(""));
                popupTablePagination.hidden = false;
            }
        }

        animateTableDayChips();
        refreshPopupTableAfterLayout();
    }

    function renderEmployeeModal(selected)
    {
        if (!selected)
        {
            return;
        }

        if (typeof window.startAsyncSurfaceSkeleton === "function")
        {
            window.startAsyncSurfaceSkeleton(popupTableSection);
        }

        if (popupFilterOwnerId && popupFilterOwnerId !== String(selected.id))
        {
            resetPopupHistoryFilters();
        }

        popupFilterOwnerId = String(selected.id);
        currentEmployeeDetail = selected;
        activePopupHistoryStatus = getPreferredPopupHistoryStatus(selected);
        renderPopupTableHead(activePopupHistoryStatus);
        const tableBody = document.getElementById("detailTableBody");
        window.setSafeHTML(tableBody, renderPopupTableSkeletonRows(5));

        setDetailAvatar(selected);
        document.getElementById("detailUsername").textContent = selected.display_name || selected.username;
        document.getElementById("detailDepartmentChip").textContent = selected.department;
        document.getElementById("detailRoleChip").textContent = selected.role;
        document.getElementById("detailEmail").textContent = selected.email;
        document.getElementById("detailPhone").textContent = selected.phone;
        document.getElementById("detailJoin").textContent = `Joined ${selected.date_of_joining}`;
        document.getElementById("detailEmployeeId").textContent = selected.employee_id;
        const detailTotal = document.getElementById("detailTotal");
        const detailPending = document.getElementById("detailPending");
        const detailApproved = document.getElementById("detailApproved");
        const detailRejected = document.getElementById("detailRejected");
        const detailEarnedRemaining = document.getElementById("detailEarnedRemaining");
        const detailEarnedUsed = document.getElementById("detailEarnedUsed");
        const detailEarnedTotal = document.getElementById("detailEarnedTotal");
        const detailSickRemaining = document.getElementById("detailSickRemaining");
        const detailSickUsed = document.getElementById("detailSickUsed");
        const detailSickTotal = document.getElementById("detailSickTotal");
        const detailUnpaidTaken = document.getElementById("detailUnpaidTaken");
        const detailShortUsedMonth = document.getElementById("detailShortUsedMonth");
        const detailShortTotalMonth = document.getElementById("detailShortTotalMonth");
        const detailHalfUsedMonth = document.getElementById("detailHalfUsedMonth");
        const detailHalfTotalMonth = document.getElementById("detailHalfTotalMonth");
        const detailTableCount = document.getElementById("detailTableCount");
        const animateMetric = function (element, value, options)
        {
            if (!element)
            {
                return;
            }

            element.dataset.countupTarget = String(value);

            if (typeof window.animateCountUp === "function")
            {
                window.animateCountUp(element, value, Object.assign({ duration: 320 }, options || {}));
                return;
            }

            const suffix = options && options.suffix ? options.suffix : "";
            element.textContent = String(value) + suffix;
        };

        animateMetric(detailTotal, selected.total_requests);
        animateMetric(detailPending, selected.pending_count);
        animateMetric(detailApproved, selected.approved_count);
        animateMetric(detailRejected, selected.rejected_count);
        document.getElementById("detailLatest").textContent = selected.latest_leave_type;
        document.getElementById("detailLatestApplied").textContent = selected.latest_applied_at;
        document.getElementById("detailAddress").textContent = selected.address;
        const bioElement = document.getElementById("detailBio");
        bioElement.textContent = selected.bio;
        bioElement.dataset.full = selected.bio || "";
        bioElement.dataset.employee = selected.display_name || selected.username;
        bioElement.dataset.modalTitle = (selected.display_name || selected.username) + " bio";
        animateMetric(detailEarnedRemaining, selected.earned_remaining);
        animateMetric(detailEarnedUsed, selected.earned_used);
        animateMetric(detailEarnedTotal, selected.earned_total);
        animateMetric(detailSickRemaining, selected.sick_remaining);
        animateMetric(detailSickUsed, selected.sick_used);
        animateMetric(detailSickTotal, selected.sick_total);
        animateMetric(detailUnpaidTaken, selected.unpaid_taken);
        animateMetric(detailShortUsedMonth, selected.short_used_month);
        animateMetric(detailShortTotalMonth, selected.short_total_month);
        animateMetric(detailHalfUsedMonth, selected.half_used_month);
        animateMetric(detailHalfTotalMonth, selected.half_total_month);
        renderPopupHistoryTable(selected);

        const modal = document.getElementById("employeeModal");
        showManagedModal(modal);
        setPopupTableCollapsed(true);

        if (pendingHighlightEmployeeId && String(selected.id) === String(pendingHighlightEmployeeId) && pendingHighlightLeaveId)
        {
            const targetRow = tableBody.querySelector('[data-leave-id="' + pendingHighlightLeaveId + '"]');

            if (targetRow)
            {
                setPopupTableCollapsed(false);
                targetRow.classList.add("notification-highlight");
                scrollEmployeeModalToTableSection();
                window.setTimeout(function ()
                {
                    scrollPopupTableToLeave(targetRow);
                }, 320);

                window.setTimeout(function ()
                {
                    targetRow.classList.remove("notification-highlight");
                }, 4200);
            }

            pendingHighlightEmployeeId = "";
            pendingHighlightLeaveId = "";
        }

        requestAnimationFrame(function ()
        {
            clearPopupTableToggleSkeleton();

            if (typeof window.finishAsyncSurfaceSkeleton === "function")
            {
                window.finishAsyncSurfaceSkeleton(popupTableSection);
            }

            refreshPopupTableAfterLayout();
        });
    }

    popupHistoryTabs.forEach(function (tab)
    {
        tab.addEventListener("click", function ()
        {
            const nextStatus = tab.dataset.historyStatus;

            if (!nextStatus || nextStatus === activePopupHistoryStatus || !currentEmployeeDetail)
            {
                return;
            }

            activePopupHistoryStatus = nextStatus;
            renderPopupHistoryTable(currentEmployeeDetail);
        });
    });

    if (popupFilterButton)
    {
        popupFilterButton.addEventListener("click", function ()
        {
            openPopupHistoryFilterModal();
        });
    }

    if (popupFilterBadges)
    {
        popupFilterBadges.addEventListener("click", function (event)
        {
            const clearButton = event.target.closest ? event.target.closest("[data-popup-filter-clear]") : null;

            if (!clearButton || !currentEmployeeDetail)
            {
                return;
            }

            const field = clearButton.dataset.popupFilterClear;
            const nextState = clonePopupHistoryFilter(getPopupFilterState(activePopupHistoryStatus));

            if (field === "date_range")
            {
                nextState.from_date = "";
                nextState.to_date = "";
            }
            else if (field)
            {
                nextState[field] = "";
            }

            const badge = clearButton.closest ? clearButton.closest(".popup-filter-badge") : null;
            const applyFilterClear = function ()
            {
                popupHistoryFilters[activePopupHistoryStatus] = nextState;
                setPopupHistoryPage(activePopupHistoryStatus, 1);
                syncPopupTabFilterIndicators();
                renderPopupHistoryTable(currentEmployeeDetail);
            };

            if (!badge)
            {
                applyFilterClear();
                return;
            }

            badge.classList.add("is-removing");
            window.setTimeout(applyFilterClear, 150);
        });
    }

    if (popupTablePagination)
    {
        popupTablePagination.addEventListener("click", function (event)
        {
            const pageButton = event.target.closest ? event.target.closest("[data-popup-page]") : null;

            if (!pageButton || pageButton.disabled || !currentEmployeeDetail)
            {
                return;
            }

            setPopupHistoryPage(activePopupHistoryStatus, Number(pageButton.dataset.popupPage || 1));
            renderPopupHistoryTable(currentEmployeeDetail);
        });
    }

    function openEmployeeModal(employeeId, options)
    {
        const modalOptions = Object.assign({ refresh: true }, options || {});
        const selected = employeeData.find(function (employee)
        {
            return String(employee.id) === String(employeeId);
        });

        if (!selected && !modalOptions.refresh)
        {
            return;
        }

        if (!modalOptions.refresh)
        {
            renderEmployeeModal(selected);
            return;
        }

        const tableBody = document.getElementById("detailTableBody");
        const requestToken = ++employeeModalFetchToken;

        if (typeof window.startAsyncSurfaceSkeleton === "function")
        {
            window.startAsyncSurfaceSkeleton(popupTableSection);
        }

        pulsePopupTableToggleSkeleton();

        if (tableBody)
        {
            window.setSafeHTML(tableBody, renderPopupTableSkeletonRows(5));
        }

        fetchManageEmployeeDetail(employeeId)
            .then(function (freshEmployee)
            {
                if (requestToken !== employeeModalFetchToken)
                {
                    return;
                }

                renderEmployeeModal(freshEmployee);
            })
            .catch(function ()
            {
                if (requestToken !== employeeModalFetchToken)
                {
                    return;
                }

                if (selected)
                {
                    renderEmployeeModal(selected);
                    return;
                }

                clearPopupTableToggleSkeleton();

                if (typeof window.finishAsyncSurfaceSkeleton === "function")
                {
                    window.finishAsyncSurfaceSkeleton(popupTableSection);
                }
            });
    }

    function closeEmployeeModal()
    {
        const modal = document.getElementById("employeeModal");
        hideManagedModal(modal);
    }

    function setPopupTableCollapsed(isCollapsed)
    {
        if (!popupTableSection || !popupTableToggle || !popupTableToggleLabel)
        {
            return;
        }

        const wasCollapsed = popupTableSection.classList.contains("is-collapsed");
        popupTableSection.classList.remove("is-expanding", "is-collapsing");

        const popupCount = document.getElementById("detailTableCount");
        popupTableSection.classList.toggle("is-collapsed", isCollapsed);
        popupTableToggle.setAttribute("aria-expanded", String(!isCollapsed));
        popupTableToggleLabel.textContent = isCollapsed ? "Expand" : "Minimize";

        if (wasCollapsed !== isCollapsed)
        {
            popupTableSection.classList.add(isCollapsed ? "is-collapsing" : "is-expanding");

            if (popupTableSection._tableMotionTimer)
            {
                clearTimeout(popupTableSection._tableMotionTimer);
            }

            popupTableSection._tableMotionTimer = window.setTimeout(function ()
            {
                popupTableSection.classList.remove("is-expanding", "is-collapsing");
                popupTableSection._tableMotionTimer = null;
            }, 320);
        }

        if (popupCount)
        {
            popupCount.classList.toggle("is-animated", isCollapsed);
        }

        if (!isCollapsed)
        {
            cuePopupTableScroll();
            refreshPopupTableAfterLayout();
        }
    }

    function cuePopupTableScroll()
    {
        if (!popupTableWrapper || !popupTableInner)
        {
            return;
        }

        if (popupTableWrapper._hintTimer)
        {
            clearTimeout(popupTableWrapper._hintTimer);
            popupTableWrapper._hintTimer = null;
        }

        popupTableWrapper.classList.remove("show-x-scroll-hint");
        popupTableInner.classList.remove("show-y-scroll-hint");

        requestAnimationFrame(function ()
        {
            if (popupTableSection && popupTableSection.classList.contains("is-collapsed"))
            {
                return;
            }

            const canScrollX = popupTableWrapper.scrollWidth > popupTableWrapper.clientWidth + 12;
            const canScrollY = popupTableInner.scrollHeight > popupTableInner.clientHeight + 12;

            if (canScrollX)
            {
                popupTableWrapper.classList.add("show-x-scroll-hint");
                popupTableWrapper.scrollTo({ left: 56, behavior: "smooth" });
                setTimeout(function ()
                {
                    popupTableWrapper.scrollTo({ left: 0, behavior: "smooth" });
                }, 220);
            }

            if (canScrollY)
            {
                popupTableInner.classList.add("show-y-scroll-hint");
                popupTableInner.scrollTo({ top: 26, behavior: "smooth" });
                setTimeout(function ()
                {
                    popupTableInner.scrollTo({ top: 0, behavior: "smooth" });
                }, 240);
            }

            popupTableWrapper._hintTimer = setTimeout(function ()
            {
                popupTableWrapper.classList.remove("show-x-scroll-hint");
                popupTableInner.classList.remove("show-y-scroll-hint");
                popupTableWrapper._hintTimer = null;
            }, 1400);
        });
    }

    function scrollPopupTableToLeave(targetRow)
    {
        if (!targetRow || !popupTableInner)
        {
            return;
        }

        function getOffsetTopWithinAncestor(element, ancestor)
        {
            let offset = 0;
            let current = element;

            while (current && current !== ancestor)
            {
                offset += current.offsetTop;
                current = current.offsetParent;
            }

            return offset;
        }

        requestAnimationFrame(function ()
        {
            requestAnimationFrame(function ()
            {
                const rowTop = getOffsetTopWithinAncestor(targetRow, popupTableInner);
                const stickyHeaderOffset = 56;
                const centeredTop = Math.max(
                    0,
                    rowTop - stickyHeaderOffset - Math.max(0, (popupTableInner.clientHeight / 2) - (targetRow.offsetHeight / 2))
                );

                popupTableInner.scrollTo({
                    top: centeredTop,
                    behavior: "smooth"
                });
            });
        });
    }

    function scrollEmployeeModalToTableSection()
    {
        if (!employeeModalDialog || !popupTableSection)
        {
            return;
        }

        requestAnimationFrame(function ()
        {
            const targetTop = Math.max(0, popupTableSection.offsetTop - 12);
            employeeModalDialog.scrollTo({ top: targetTop, behavior: "smooth" });
        });
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

        if (reasonModalCloseTimer)
        {
            clearTimeout(reasonModalCloseTimer);
            reasonModalCloseTimer = null;
        }

        const reasonTrigger = window.lastModalTrigger instanceof HTMLElement && reasonText.contains(window.lastModalTrigger)
            ? window.lastModalTrigger
            : null;
        activeReasonAnchor = reasonTrigger || reasonText;

        if (activeReasonAnchor && typeof activeReasonAnchor.getBoundingClientRect === "function")
        {
            const anchorRect = activeReasonAnchor.getBoundingClientRect();
            const anchorCenterX = anchorRect.left + (anchorRect.width / 2);
            const anchorCenterY = anchorRect.top + (anchorRect.height / 2);
            const viewportCenterX = window.innerWidth / 2;
            const viewportCenterY = window.innerHeight / 2;

            modal.style.setProperty("--reason-origin-x", (anchorCenterX - viewportCenterX) + "px");
            modal.style.setProperty("--reason-origin-y", (anchorCenterY - viewportCenterY) + "px");
        }
        else
        {
            modal.style.removeProperty("--reason-origin-x");
            modal.style.removeProperty("--reason-origin-y");
        }

        let dayText = reasonText.dataset.daysDisplay || "-";
        const appliedIso = reasonText.dataset.appliedIso || "";
        const updatedIso = reasonText.dataset.updatedIso || "";
        const decisionIso = reasonText.dataset.decisionIso || "";
        const decisionLabelText = reasonText.dataset.decisionLabel || "";
        const reviewerText = reasonText.dataset.reviewer || "HR Team";
        const reviewerLabelText = reasonText.dataset.reviewerLabel || "";
        const updatedCount = Number.parseInt(reasonText.dataset.updatedCount || "0", 10) || 0;
        const useMobileReasonLabels = window.matchMedia && window.matchMedia("(max-width: 640px)").matches;
        const scheduleDateText = (reasonText.dataset.scheduleDate || "-").replace(/\s*->\s*/g, " \u27F6 ");
        const scheduleTimeText = (reasonText.dataset.scheduleTime || "-").replace(/\s*->\s*/g, " \u27F6 ");
        const leaveTypeClass = reasonText.dataset.leaveTypeClass || "default";
        const leaveTypeLabel = reasonText.dataset.leaveType || "Leave type";
        const reasonContext = reasonText.dataset.reasonContext || reasonText.dataset.historyStatus || "pending";
        const showScheduleTime = leaveTypeClass === "short" || leaveTypeClass === "half";
        const contextLabels = {
            pending: { title: "Pending Reason", label: "Pending Reason", icon: "&#9203;" },
            approved: { title: "Approved Reason", label: "Approved Reason", icon: "&#10003;" },
            "rejected-employee": { title: "Rejected Leave Reason", label: "Employee Reason", icon: "&#128221;" },
            "rejected-note": { title: "Rejection Reason", label: "Rejection Reason", icon: "&#10006;" }
        };
        const contextCopy = contextLabels[reasonContext] || contextLabels.pending;

        title.textContent = reasonText.dataset.modalTitle || contextCopy.title;
        modal.classList.remove(
            "reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half", "reason-theme-default",
            "reason-context-pending", "reason-context-approved", "reason-context-rejected-employee", "reason-context-rejected-note"
        );
        modal.classList.add("reason-theme-" + leaveTypeClass);
        modal.classList.add("reason-context-" + reasonContext);
        employee.textContent = reasonText.dataset.employee || "Employee";
        leaveType.textContent = leaveTypeLabel + " Leave";
        leaveType.className = "reason-modal-chip reason-modal-type-chip reason-modal-type-" + leaveTypeClass;
        scheduleDate.textContent = scheduleDateText;
        scheduleTime.textContent = showScheduleTime ? scheduleTimeText : "";
        scheduleTime.hidden = !showScheduleTime;
        scheduleTime.classList.toggle("reason-modal-schedule-time-accent", showScheduleTime);
        days.textContent = dayText;
        window.setSafeHTML(appliedLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128338;</span><span>${useMobileReasonLabels ? "Applied At" : "Applied"}</span></span>`);

        const relativeApplied = formatRelativeLeaveAge(appliedIso);
        const relativeUpdated = formatRelativeLeaveAge(updatedIso);
        const relativeDecision = formatRelativeLeaveAge(decisionIso);
        const hasDecision = reasonContext !== "pending" && Boolean(decisionIso || (reasonText.dataset.decision && reasonText.dataset.decision !== "-"));
        applied.textContent = relativeApplied || (reasonText.dataset.applied || "-");
        appliedTime.textContent = formatPopupClockTime(appliedIso, reasonText.dataset.applied || "");
        window.setSafeHTML(updatedLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128260;</span><span>${useMobileReasonLabels ? "Updated At" : (updatedCount === 1 ? "1 update" : `${updatedCount} updates`)}</span></span>`);
        updated.textContent = updatedIso ? (relativeUpdated || (reasonText.dataset.updated || "-")) : "Not updated";
        updatedTime.textContent = updatedIso ? formatPopupClockTime(updatedIso, reasonText.dataset.updated || "") : "-";
        if (metaGrid)
        {
            metaGrid.classList.toggle("has-decision", hasDecision);
        }

        if (decisionCard)
        {
            decisionCard.hidden = !hasDecision;
        }
        if (reviewerCard)
        {
            reviewerCard.hidden = !hasDecision;
        }

        modal.classList.toggle("reason-has-decision", hasDecision);

        if (decisionLabel)
        {
            const isRejectedDecision = decisionLabelText.toLowerCase().includes("reject");
            window.setSafeHTML(decisionLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">${isRejectedDecision ? "&#9940;" : "&#10003;"}</span><span>${decisionLabelText || "Decision At"}</span></span>`);
        }

        if (decision)
        {
            decision.textContent = hasDecision ? (relativeDecision || (reasonText.dataset.decision || "-")) : "-";
        }

        if (decisionTime)
        {
            decisionTime.textContent = hasDecision ? formatPopupClockTime(decisionIso, reasonText.dataset.decision || "") : "-";
        }
        if (reviewerLabel)
        {
            window.setSafeHTML(reviewerLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128100;</span><span>${reviewerLabelText || "Reviewed By"}</span></span>`);
        }
        if (reviewer)
        {
            reviewer.textContent = hasDecision ? reviewerText : "-";
        }
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

        modal.classList.remove("is-open");

        hideManagedModal(modal, function ()
        {
            title.textContent = "Reason detail";
            content.textContent = "";
            employee.textContent = "Employee";
            leaveType.textContent = "Leave type";
            leaveType.className = "reason-modal-chip reason-modal-type-chip reason-modal-type-default";
            if (metaGrid)
            {
                metaGrid.classList.remove("has-decision");
            }
            window.setSafeHTML(appliedLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128338;</span><span>Applied</span></span>');
            window.setSafeHTML(updatedLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128260;</span><span>0 updates</span></span>');
            if (decisionLabel)
            {
                window.setSafeHTML(decisionLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#10003;</span><span>Approved At</span></span>');
            }
            if (decisionCard)
            {
                decisionCard.hidden = true;
            }
            if (reviewerLabel)
            {
                window.setSafeHTML(reviewerLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">&#128100;</span><span>Approved By</span></span>');
            }
            if (reviewerCard)
            {
                reviewerCard.hidden = true;
            }
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
            if (decision)
            {
                decision.textContent = "-";
            }
            if (decisionTime)
            {
                decisionTime.textContent = "-";
            }
            if (reviewer)
            {
                reviewer.textContent = "-";
            }
            modal.classList.remove(
                "reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half",
                "reason-context-pending", "reason-context-approved", "reason-context-rejected-employee", "reason-context-rejected-note"
            );
            modal.classList.add("reason-theme-default");
            modal.classList.remove("reason-has-decision");
            activeReasonAnchor = null;
            reasonModalCloseTimer = null;
        });
    }

    function openReject(leaveId)
    {
        const modal = document.getElementById("rejectModal");
        const form = document.getElementById("rejectForm");
        const textarea = document.getElementById("rejectionReason");
        const leave = findCurrentEmployeeLeave(leaveId);

        if (!leave)
        {
            showPopupActionError("Unable to load this leave request.");
            return;
        }

        currentRejectLeaveId = leaveId;
        currentRejectLeaveSnapshot = leave;
        form.action = getLeaveActionUrl(rejectLeaveUrlTemplate, leaveId);
        populateRejectModal(leave);
        resetRejectSectionCards();
        setManagedModalButtonOrigin(modal, window.lastModalTrigger);
        showManagedModal(modal);
        syncRejectionReasonCount();
        textarea.focus();
    }

    function closeReject()
    {
        const modal = document.getElementById("rejectModal");
        const textarea = document.getElementById("rejectionReason");

        hideManagedModal(modal, function ()
        {
            currentRejectLeaveId = null;
            currentRejectLeaveSnapshot = null;
            textarea.value = "";
            syncRejectionReasonCount();
        });
    }

    function showManagedModal(modal)
    {
        if (!modal)
        {
            return;
        }

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
        if (!modal)
        {
            return;
        }

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

             if (modal._lastFocusedElement instanceof HTMLElement && document.contains(modal._lastFocusedElement))
            {
                modal._lastFocusedElement.focus({ preventScroll: true });
            }

            modal._lastFocusedElement = null;

            if (typeof onClosed === "function")
            {
                onClosed();
            }
        }, 260);
    }

    document.querySelectorAll(".employee-profile-card").forEach(function (card)
    {
        card.addEventListener("click", function ()
        {
            openEmployeeModal(card.dataset.employeeId);
        });
    });

    const rejectForm = document.getElementById("rejectForm");
    const decisionConfirmCancel = document.getElementById("decisionConfirmCancel");
    const decisionConfirmSubmit = document.getElementById("decisionConfirmSubmit");
    const rejectionReasonTextarea = document.getElementById("rejectionReason");
    const rejectionReasonCount = document.getElementById("rejectionReasonCount");
    const rejectReasonToggleAllButton = document.getElementById("rejectReasonToggleAll");
    const rejectReasonSectionGrid = document.getElementById("rejectReasonSectionGrid");

    function syncRejectionReasonCount()
    {
        if (!rejectionReasonTextarea || !rejectionReasonCount)
        {
            return;
        }

        const currentLength = rejectionReasonTextarea.value ? rejectionReasonTextarea.value.length : 0;
        const maxLength = Number(rejectionReasonTextarea.getAttribute("maxlength") || 100);
        rejectionReasonCount.textContent = currentLength + "/" + maxLength;
    }

    if (decisionConfirmCancel)
    {
        decisionConfirmCancel.addEventListener("click", function ()
        {
            closeDecisionConfirm(false);
        });
    }

    if (decisionConfirmSubmit)
    {
        decisionConfirmSubmit.addEventListener("click", function ()
        {
            closeDecisionConfirm(true);
        });
    }

    if (rejectionReasonTextarea)
    {
        rejectionReasonTextarea.addEventListener("input", syncRejectionReasonCount);
        syncRejectionReasonCount();
    }

    if (rejectReasonToggleAllButton)
    {
        rejectReasonToggleAllButton.addEventListener("click", function ()
        {
            if (!rejectReasonSectionGrid)
            {
                return;
            }

            const shouldShow = rejectReasonSectionGrid.classList.contains("is-hidden") || rejectReasonSectionGrid.classList.contains("is-hiding");
            setRejectReasonSectionsVisible(shouldShow, true);
        });
    }

    if (rejectForm)
    {
        rejectForm.addEventListener("submit", function (event)
        {
            event.preventDefault();

            const textarea = document.getElementById("rejectionReason");
            const rejectionReason = textarea ? textarea.value.trim() : "";

            if (!currentRejectLeaveId)
            {
                showPopupActionError("No leave request selected for rejection.");
                return;
            }

            if (!rejectionReason)
            {
                if (textarea)
                {
                    textarea.focus();
                }
                return;
            }

            const activeLeave = currentRejectLeaveSnapshot || findCurrentEmployeeLeave(currentRejectLeaveId);

            openDecisionConfirm({
                variant: "reject",
                leave: activeLeave,
                note: rejectionReason,
                trigger: event.submitter || document.activeElement
            }).then(function (confirmed)
            {
                if (!confirmed)
                {
                    if (textarea)
                    {
                        textarea.focus();
                    }
                    return null;
                }

                return rejectLeaveFromPopup(currentRejectLeaveId, rejectionReason);
            })
                .then(function (payload)
                {
                    if (!payload)
                    {
                        return;
                    }

                    closeReject();
                    renderFlashMessages(payload.messages);
                    refreshEmployeeModalAfterAction(payload.employee_detail, "rejected");
                    refreshHrNotificationsAfterDecision(payload.leave_id || currentRejectLeaveId);
                })
                .catch(function ()
                {
                    if (textarea)
                    {
                        textarea.focus();
                    }
                });
        });
    }

    if (typeof ResizeObserver === "function")
    {
        const employeeCardResizeObserver = new ResizeObserver(function (entries)
        {
            entries.forEach(function (entry)
            {
                updateEmployeeCardDensity(entry.target);
            });
        });

        employeeProfileCards.forEach(function (card)
        {
            employeeCardResizeObserver.observe(card);
        });
    }
    else
    {
        updateAllEmployeeCardDensity();
    }

    window.addEventListener("resize", function ()
    {
        refreshPopupTableAfterLayout();
    });

    window.addEventListener("focus", refreshManageAllLiveData);
    window.addEventListener("pageshow", refreshManageAllLiveData);
    window.addEventListener("profile-photo-updated", function ()
    {
        pendingEmployeeCardPhotoReload = true;
        refreshManageAllLiveData({ forcePhotoReload: true });
    });
    window.addEventListener("storage", function (event)
    {
        if (event.key === "profile-photo-updated")
        {
            pendingEmployeeCardPhotoReload = true;
            refreshManageAllLiveData({ forcePhotoReload: true });
        }
    });
    document.addEventListener("visibilitychange", function ()
    {
        if (!document.hidden)
        {
            refreshManageAllLiveData();
        }
    });
    setInterval(refreshManageAllLiveData, 60000);

    employeeBellDropdowns.forEach(function (dropdown)
    {
        dropdown.addEventListener("keydown", function (event)
        {
            const markReadButton = event.target.closest ? event.target.closest("[data-employee-bell-mark-read]") : null;

            if (!markReadButton)
            {
                return;
            }

            if (markReadButton.classList.contains("is-disabled"))
            {
                event.preventDefault();
                return;
            }

            if (event.key === "Enter" || event.key === " ")
            {
                event.preventDefault();
                event.stopPropagation();
                markEmployeeBellAllRead(dropdown.dataset.employeeId || "");
            }
        });

        dropdown.addEventListener("pointerdown", function (event)
        {
            const markReadButton = event.target.closest ? event.target.closest("[data-employee-bell-mark-read]") : null;
            if (markReadButton)
            {
                event.stopPropagation();
                return;
            }

            const bellItem = event.target.closest ? event.target.closest("[data-employee-bell-item]") : null;
            if (bellItem)
            {
                return;
            }

            event.stopPropagation();
        });

        dropdown.addEventListener("click", function (event)
        {
            const markReadButton = event.target.closest ? event.target.closest("[data-employee-bell-mark-read]") : null;
            if (markReadButton)
            {
                if (markReadButton.classList.contains("is-disabled"))
                {
                    event.preventDefault();
                    event.stopPropagation();
                    return;
                }

                event.preventDefault();
                event.stopPropagation();
                markEmployeeBellAllRead(dropdown.dataset.employeeId || "");
                return;
            }

            const bellItem = event.target.closest ? event.target.closest("[data-employee-bell-item]") : null;
            if (bellItem)
            {
                return;
            }

            event.stopPropagation();
            event.preventDefault();
            const shouldOpen = !dropdown.classList.contains("is-open");
            closeEmployeeBellDropdowns();

            if (shouldOpen)
            {
                dropdown.classList.add("is-open");
                const card = dropdown.closest(".employee-profile-card");

                if (card)
                {
                    card.classList.add("has-open-bell");
                }
                positionEmployeeBellDropdown(dropdown);

            }
        });
    });

    window.addEventListener("hr-notification-state-sync", function (event)
    {
        const detail = event.detail || {};

        if (detail.apiUrl !== notificationApiUrl || detail.userKey !== notificationUserKey)
        {
            return;
        }

        applyEmployeeBellState(detail);
    });

    document.addEventListener("DOMContentLoaded", function ()
    {
        scheduleEmployeeBellBootstrap();
    });

    window.addEventListener("load", function ()
    {
        syncEmployeeBellFromMainRenderedState();
    });

    window.addEventListener("pageshow", function ()
    {
        syncEmployeeBellFromMainRenderedState();
    });

    window.addEventListener("resize", function ()
    {
        const openDropdown = employeeBellDropdowns.find(function (dropdown)
        {
            return dropdown.classList.contains("is-open");
        });

        if (openDropdown)
        {
            positionEmployeeBellDropdown(openDropdown);
        }

        const nextPageSize = getManageDirectoryPageSize();
        if (manageDirectoryLastPageSize !== nextPageSize)
        {
            renderManageDirectory(employeeSearchInput ? employeeSearchInput.value : "", { page: 1 });
        }

        updateAllEmployeeCardDensity();
    });

    if (popupTableToggle)
    {
        popupTableToggle.addEventListener("click", function ()
        {
            const isCollapsed = popupTableSection && popupTableSection.classList.contains("is-collapsed");
            setPopupTableCollapsed(!isCollapsed);
        });
    }

    mobileSummaryTabs.forEach(function (tab)
    {
        tab.addEventListener("click", function ()
        {
            setMobileSummarySet(tab.dataset.summarySet);
        });
    });

    if (employeeSearchInput)
    {
        employeeSearchInput.addEventListener("input", function ()
        {
            runManageDirectoryTransition(function ()
            {
                renderManageDirectory(employeeSearchInput.value, { page: 1 });
            });
        });
    }

    if (manageDirectoryPagination)
    {
        manageDirectoryPagination.addEventListener("click", function (event)
        {
            const pageButton = event.target.closest("[data-manage-page]");
            const navButton = event.target.closest("[data-manage-nav]");

            if (pageButton)
            {
                goToManageDirectoryPage(Number(pageButton.dataset.managePage));
                return;
            }

            if (!navButton)
            {
                return;
            }

            if (navButton.dataset.manageNav === "prev")
            {
                goToManageDirectoryPage(manageDirectoryCurrentPage - 1);
                return;
            }

            if (navButton.dataset.manageNav === "first")
            {
                goToManageDirectoryPage(1);
                return;
            }

            if (navButton.dataset.manageNav === "last")
            {
                const query = employeeSearchInput ? employeeSearchInput.value : "";
                const totalPages = Math.max(1, Math.ceil(getMatchingEmployeeCards(query).length / getManageDirectoryPageSize()));
                goToManageDirectoryPage(totalPages);
                return;
            }

            goToManageDirectoryPage(manageDirectoryCurrentPage + 1);
        });
    }

    scheduleEmployeeBellBootstrap();
    renderManageDirectory(employeeSearchInput ? employeeSearchInput.value : "", { page: 1 });
    updateAllEmployeeCardDensity();

    const params = new URLSearchParams(window.location.search);
    const employeeToOpen = params.get("employee");
    const highlightLeaveFromQuery = params.get("highlight_leave");

    try
    {
        const storedHrHighlight = window.sessionStorage.getItem("hrNotificationHighlight");
        if (storedHrHighlight)
        {
            const parsedHrHighlight = JSON.parse(storedHrHighlight);
            pendingHighlightEmployeeId = parsedHrHighlight.employeeId || "";
            pendingHighlightLeaveId = parsedHrHighlight.leaveId || "";
            window.sessionStorage.removeItem("hrNotificationHighlight");
        }
    }
    catch (error)
    {
        pendingHighlightEmployeeId = "";
        pendingHighlightLeaveId = "";
    }

    if (!pendingHighlightEmployeeId && employeeToOpen)
    {
        pendingHighlightEmployeeId = employeeToOpen;
    }

    if (!pendingHighlightLeaveId && highlightLeaveFromQuery)
    {
        pendingHighlightLeaveId = highlightLeaveFromQuery;
    }

    if (employeeToOpen)
    {
        const employeeWasRevealed = revealEmployeeCard(employeeToOpen);

        if (employeeWasRevealed)
        {
            requestAnimationFrame(function ()
            {
                openEmployeeModal(employeeToOpen, { refresh: !!pendingHighlightLeaveId });
            });
        }
        else
        {
            openEmployeeModal(employeeToOpen, { refresh: !!pendingHighlightLeaveId });
        }

        const cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.delete("employee");
        cleanUrl.searchParams.delete("highlight_leave");
        window.history.replaceState({}, "", cleanUrl.toString());
    }

    document.addEventListener("click", function (event)
    {
        const notificationToggle = document.getElementById("notification-toggle");
        const notificationDropdown = document.querySelector(".notification-dropdown");

        if (
            notificationToggle &&
            notificationDropdown &&
            notificationToggle.checked &&
            !notificationDropdown.contains(event.target) &&
            event.target !== notificationToggle
        )
        {
            notificationToggle.checked = false;
        }

        if (!event.target.closest("[data-employee-bell]"))
        {
            closeEmployeeBellDropdowns();
        }

        const employeeBellItem = event.target.closest("[data-employee-bell-item]");
        if (employeeBellItem)
        {
            event.preventDefault();
            event.stopPropagation();

            pendingHighlightEmployeeId = employeeBellItem.dataset.employeeId || "";
            pendingHighlightLeaveId = employeeBellItem.dataset.leaveId || "";

            if (!pendingHighlightEmployeeId || !pendingHighlightLeaveId)
            {
                return;
            }

            markManageBellNotificationAsRead(pendingHighlightLeaveId);
            closeEmployeeBellDropdowns();
            openEmployeeModal(pendingHighlightEmployeeId, { refresh: true });
            return;
        }

        const inlineMore = event.target.closest(".reason-inline-more");
        const reasonText = inlineMore ? inlineMore.closest(".reason-text.is-truncated") : event.target.closest(".reason-text.is-truncated");

        if (reasonText && inlineMore)
        {
            window.lastModalTrigger = inlineMore;
            openReasonModal(reasonText);
        }
    });

    document.addEventListener("keydown", function (event)
    {
        const employeeBellItem = event.target.closest ? event.target.closest("[data-employee-bell-item]") : null;
        if (employeeBellItem && (event.key === "Enter" || event.key === " "))
        {
            event.preventDefault();
            employeeBellItem.click();
            return;
        }

        if (event.key === "Escape")
        {
            const decisionConfirmModal = document.getElementById("decisionConfirmModal");
            const rejectModal = document.getElementById("rejectModal");
            const reasonModal = document.getElementById("reasonModal");
            const employeeModal = document.getElementById("employeeModal");

            if (decisionConfirmModal && decisionConfirmModal.getAttribute("aria-hidden") === "false")
            {
                closeDecisionConfirm(false);
                return;
            }

            if (rejectModal && rejectModal.getAttribute("aria-hidden") === "false")
            {
                closeReject();
                return;
            }

            if (reasonModal && reasonModal.getAttribute("aria-hidden") === "false")
            {
                closeReasonModal();
                return;
            }

            if (employeeModal && employeeModal.getAttribute("aria-hidden") === "false")
            {
                closeEmployeeModal();
            }
        }
    });
