const quotes = [
    "Stay consistent, success follows.",
    "Small steps every day.",
    "Discipline beats motivation.",
    "Your future self will thank you.",
    "Keep pushing forward."
];

let qIndex = 0;
let currentPage = 1;
let totalPages = 1;
let direction = "next";
let isPageLoaded = false;
const INDIA_TIMEZONE = "Asia/Kolkata";
const DASHBOARD_LIVE_REFRESH_INTERVAL_MS = 60000;
let countdownTimers = [];

function buildDashboardAjaxUrl(params = {}) {
    const url = new URL(window.location.pathname, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
            url.searchParams.set(key, value);
        }
    });
    return `${url.pathname}${url.search}`;
}

function rotateQuotes() {
    const el = document.getElementById("quoteText");
    if (!el) return;

    el.style.opacity = 0;
    el.style.transform = "translateY(10px)";

    setTimeout(() => {
        qIndex = (qIndex + 1) % quotes.length;
        el.innerText = quotes[qIndex];
        el.style.opacity = 1;
        el.style.transform = "translateY(0)";
    }, 400);
}

function animateLeaveProgress() {
    document.querySelectorAll(".leave-progress .progress-fill").forEach(bar => {
        const startValue = bar.dataset.start || bar.dataset.from;
        if (!startValue) return;

        const startDate = parseTimelineDate(startValue);
        if (!startDate) return;

        const endDate = bar.dataset.end
            ? parseTimelineDate(bar.dataset.end, { endOfFullDay: bar.dataset.fullDay === "true" })
            : null;
        const now = new Date();
        let percent = 0;

        if (endDate && endDate > startDate) {
            percent = ((now - startDate) / (endDate - startDate)) * 100;
        } else {
            const totalDays = 30;
            const diff = (startDate - now) / (1000 * 60 * 60 * 24);
            percent = 100 - (diff * 100 / totalDays);
        }

        percent = Math.max(0, Math.min(100, percent));

        setTimeout(() => {
            bar.style.width = percent + "%";
        }, 200);
    });
}

function parseTimelineDate(value, { endOfFullDay = false } = {}) {
    if (!value) return null;

    const dateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (dateOnlyMatch) {
        const [, year, month, day] = dateOnlyMatch.map(Number);
        const parsed = new Date(year, month - 1, day);
        if (endOfFullDay) parsed.setDate(parsed.getDate() + 1);
        return parsed;
    }

    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatClockTime(date) {
    return date.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
        hour12: true
    });
}

function formatDuration(milliseconds, includeDays = true) {
    const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const timeText = `${hours}h ${minutes}m ${seconds}s`;
    return includeDays && days > 0 ? `${days}d ${timeText}` : timeText;
}

function updateLiveLeaveStatuses() {
    document.querySelectorAll(".live-leave-status").forEach(el => {
        const isFullDay = el.dataset.kind === "full" || el.dataset.fullDay === "true";
        const start = parseTimelineDate(el.dataset.start || el.dataset.time);
        const end = parseTimelineDate(el.dataset.end || el.dataset.time, { endOfFullDay: isFullDay });

        if (!start || !end) {
            el.innerText = "";
            return;
        }

        const now = new Date();

        if (now < start) {
            const diff = start - now;
            el.innerText = diff < 86400000
                ? `Starts in ${formatDuration(diff, false)}`
                : `${formatDuration(diff)} to start`;
            el.dataset.state = "upcoming";
            el.classList.toggle("urgent", diff < 15 * 60 * 1000);
            return;
        }

        if (now >= end) {
            el.innerText = `Ended.. at ${formatClockTime(end)}`;
            el.dataset.state = "ended";
            el.classList.remove("urgent");
            return;
        }

        el.innerText = `Started.. ${formatDuration(end - now)} left`;
        el.dataset.state = "started";
        el.classList.remove("urgent");
    });
}

function startCountdown() {
    countdownTimers.forEach(timerId => clearInterval(timerId));
    countdownTimers = [];
    updateLiveLeaveStatuses();
    animateLeaveProgress();
    countdownTimers.push(setInterval(() => {
        updateLiveLeaveStatuses();
        animateLeaveProgress();
    }, DASHBOARD_LIVE_REFRESH_INTERVAL_MS));
}

function syncDividerPointer(targetCard) {
    const line = document.querySelector(".global-line");
    const dot = document.getElementById("activeDot");
    if (!line || !dot || !targetCard) return;

    const lineRect = line.getBoundingClientRect();
    const cardRect = targetCard.getBoundingClientRect();
    const dotHalf = dot.offsetHeight / 2;
    const targetTop = cardRect.top + (cardRect.height / 2) - lineRect.top - dotHalf;
    const maxTop = Math.max(0, lineRect.height - dot.offsetHeight);
    const nextTop = Math.max(0, Math.min(maxTop, targetTop));

    dot.style.top = `${nextTop}px`;
    dot.classList.remove("pointer-upcoming", "pointer-last", "pointer-recent");
    const sectionCard = targetCard.closest(".main-leave-card");
    if (sectionCard?.classList.contains("upcoming")) {
        dot.classList.add("pointer-upcoming");
    } else if (sectionCard?.classList.contains("last")) {
        dot.classList.add("pointer-last");
    } else if (sectionCard?.classList.contains("recent")) {
        dot.classList.add("pointer-recent");
    }
    dot.classList.add("active");
}

function initDashboardDividerPointer() {
    const rightPanel = document.querySelector(".right-panel");
    const line = document.querySelector(".global-line");
    const dot = document.getElementById("activeDot");
    if (!rightPanel || !line || !dot) return;

    const pointerCards = rightPanel.querySelectorAll(".main-leave-card, .inner-leave-card, .activity-card");
    pointerCards.forEach(card => {
        card.addEventListener("mouseenter", () => syncDividerPointer(card));
        card.addEventListener("focusin", () => syncDividerPointer(card));
    });

    rightPanel.addEventListener("mouseleave", () => {
        dot.classList.remove("active");
    });

    window.addEventListener("resize", () => {
        const hoveredCard = rightPanel.querySelector(".main-leave-card:hover, .inner-leave-card:hover, .activity-card:hover");
        if (hoveredCard) syncDividerPointer(hoveredCard);
    });

    const firstCard = rightPanel.querySelector(".main-leave-card");
    if (firstCard) syncDividerPointer(firstCard);
}

function animateNumber(el, start, end, duration = 1200) {
    let startTime = null;
    el.classList.add("animating");

    function easeOutBack(t) {
        const c1 = 1.70158;
        const c3 = c1 + 1;
        return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
    }

    function update(currentTime) {
        if (!startTime) startTime = currentTime;

        let progress = (currentTime - startTime) / duration;
        progress = Math.min(progress, 1);

        const eased = easeOutBack(progress);
        const value = Math.floor(eased * (end - start) + start);
        el.innerText = value;

        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            el.innerText = end;
            setTimeout(() => {
                el.classList.remove("animating");
            }, 300);
        }
    }

    requestAnimationFrame(update);
}

function isNewEntry(dateStr) {
    const now = new Date();
    const target = new Date(dateStr);
    const diffMin = (now - target) / (1000 * 60);
    return diffMin < 60;
}

function updateNewBadges() {
    document.querySelectorAll(".activity-card").forEach(card => {
        const timeEl = card.querySelector(".applied-time");
        if (!timeEl) return;

        const baseTime = timeEl.dataset.createdTime || timeEl.dataset.time;
        const isNew = isNewEntry(baseTime);
        const header = card.querySelector(".activity-header");
        if (!header) return;

        let badge = header.querySelector(".new-badge");

        if (isNew && !badge) {
            badge = document.createElement("span");
            badge.className = "new-badge";
            badge.innerText = "New";
            header.insertBefore(badge, header.children[1]);
        }

        if (!isNew && badge) {
            badge.remove();
        }
    });
}

function animateSlide(container, directionValue, callback) {
    container.classList.remove(
        "slide-in-left",
        "slide-in-right",
        "slide-out-left",
        "slide-out-right",
        "activity-page-enter",
        "activity-page-leave",
        "is-paginating"
    );
    const viewport = container.closest(".activity-viewport") || container.parentElement;
    const oldGrid = container.cloneNode(true);
    const isNext = directionValue === "next";
    const incomingStart = isNext ? "translateX(104%)" : "translateX(-104%)";
    const outgoingEnd = isNext ? "translateX(-104%)" : "translateX(104%)";

    oldGrid.removeAttribute("id");
    oldGrid.classList.add("activity-grid-clone");
    oldGrid.setAttribute("aria-hidden", "true");
    viewport.appendChild(oldGrid);

    container.classList.add("is-paginating");
    container.style.transition = "none";
    container.style.transform = incomingStart;

    setTimeout(() => {
        callback();
        void container.offsetWidth;

        oldGrid.style.transition = "transform 0.58s cubic-bezier(0.22, 1, 0.36, 1)";
        container.style.transition = "transform 0.58s cubic-bezier(0.22, 1, 0.36, 1)";
        oldGrid.style.transform = outgoingEnd;
        container.style.transform = "translateX(0)";

        setTimeout(() => {
            container.classList.remove("is-paginating");
            container.style.transition = "";
            container.style.transform = "";
            oldGrid.remove();
        }, 620);
    }, 20);
}

function renderLeaveCard(leave, isNew) {
    let bodyHTML = "";
    let durationHTML = "";
    const newBadge = isNew ? `<span class="new-badge">New</span>` : "";
    let leaveTypeClass = "leave-type-fulltype";
    const fromDateLabel = formatShortDateLabel(leave.from_date || leave.from_datetime);
    const toDateLabel = formatShortDateLabel(leave.to_date);

    if (leave.type === "Short" || leave.type === "Half") {
        leaveTypeClass = "leave-type-short";
    } else if (leave.type === "Sick") {
        leaveTypeClass = "leave-type-sick";
    } else if (leave.type === "Unpaid") {
        leaveTypeClass = "leave-type-unpaid";
    } else if (leave.type === "Earned") {
        leaveTypeClass = "leave-type-earned";
    }

    if (leave.type === "Short" || leave.type === "Half") {
        const fromTime = leave.from_time || formatIndiaTime(leave.from_datetime);
        const toTime = leave.to_time || leave.to_datetime || "";

        bodyHTML = `
            <p class="date-line"><strong>${fromDateLabel}</strong></p>
            <p class="date-line time-line">
                <strong>${escapeHtml(fromTime)}</strong>
                <span class="arrow">&rarr;</span>
                <strong>${escapeHtml(toTime)}</strong>
            </p>
        `;
    } else {
        bodyHTML = `
            <p class="date-line">
                <strong>${fromDateLabel}</strong>
                <span class="arrow">&rarr;</span>
                <strong>${toDateLabel}</strong>
            </p>
        `;
    }

    if (leave.type === "Short") {
        durationHTML = `Short leave for <span class="duration-number" data-unit="hour">2</span> hours`;
    } else if (leave.type === "Half") {
        durationHTML = `Half day for <span class="duration-number" data-unit="hour">4</span> hours`;
    } else {
        durationHTML = `<span class="duration-number" data-unit="day">${leave.duration}</span> day${leave.duration > 1 ? "s" : ""}`;
    }

    const safeReason = (leave.reason || "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    const displayReason = leave.reason
        ? leave.reason.replace(/</g, "&lt;").replace(/>/g, "&gt;")
        : "No reason provided";
    const showMore = leave.reason && leave.reason.length > 100;

    const activityTypeClass = leave.type === "Short"
        ? "activity-short"
        : leave.type === "Half"
            ? "activity-half"
            : "";
    const reasonBoxClass = leave.type === "Short" || leave.type === "Half"
        ? "reason-box"
        : "reason-box reason-box-full-day";

    return `
        <div class="activity-card pagination-card ${leave.status.toLowerCase()} ${activityTypeClass}">
            <div class="activity-header">
                <span class="leave-type ${leaveTypeClass}">${leave.type}</span>
                ${newBadge}
                <span class="status ${leave.status.toLowerCase()}">${leave.status}</span>
            </div>

            <div class="activity-body">${bodyHTML}</div>

            <div class="activity-extra">
                <p class="applied-time" data-created-time="${escapeHtml(leave.created)}" data-updated-time="${escapeHtml(leave.updated || "")}"></p>
                <p class="activity-duration ${leaveTypeClass}">${durationHTML}</p>

                <div class="${reasonBoxClass}"
                    data-status="${escapeHtml(leave.status || "")}"
                    data-leave-type="${escapeHtml(leave.type || "")}"
                    data-from-date="${escapeHtml(fromDateLabel || "")}"
                    data-to-date="${escapeHtml(toDateLabel || "")}"
                    data-from-time="${escapeHtml(leave.from_time || "")}"
                    data-to-time="${escapeHtml(leave.to_time || "")}"
                    data-duration="${escapeHtml(String(leave.duration || ""))}"
                    data-created="${escapeHtml(leave.created || "")}"
                    data-updated="${escapeHtml(leave.updated || "")}"
                    data-approved="${escapeHtml(leave.approved || "")}"
                    data-rejected="${escapeHtml(leave.rejected || "")}">
                    <div class="reason-label">Reason</div>
                    <div class="reason-divider"></div>
                    <div class="reason-content">
                        ${displayReason}
                    </div>
                    ${leave.reason && leave.reason.length > 30 ? `<span class="more-btn" data-reason="${safeReason}" style="display: none;">... more</span>` : ""}
                </div>
            </div>
        </div>
    `;
}

function getRecentActivityEmptyHtml() {
    return `
        <div class="dashboard-empty-state dashboard-recent-empty-state">
            <span class="dashboard-empty-icon" aria-hidden="true">&#9881;</span>
            <strong>No recent activity</strong>
            <p>Your latest leave requests and status changes will appear here.</p>
        </div>
    `;
}

function formatIndiaTime(value) {
    if (!value) return "--";

    const parsed = new Date(value);
    if (isNaN(parsed)) {
        const match24 = String(value).match(/^(\d{1,2}):(\d{2})(?::\d{2})?$/);
        if (match24) {
            let hours = parseInt(match24[1], 10);
            const minutes = match24[2];
            const suffix = hours >= 12 ? "PM" : "AM";
            hours = hours % 12 || 12;
            return `${hours}:${minutes} ${suffix}`;
        }

        return String(value);
    }

    return parsed.toLocaleTimeString("en-IN", {
        timeZone: INDIA_TIMEZONE,
        hour: "numeric",
        minute: "2-digit",
        hour12: true
    });
}

function renderActivityLeaves(container, leaves) {
    container.innerHTML = "";
    container.classList.toggle("is-empty", !leaves || leaves.length === 0);

    if (!leaves || leaves.length === 0) {
        container.innerHTML = getRecentActivityEmptyHtml();
        return;
    }

    leaves.forEach(leave => {
        const isNew = isNewEntry(leave.created);
        container.insertAdjacentHTML("beforeend", renderLeaveCard(leave, isNew));
    });

    updateAppliedTimeElements(container);
    updateNewBadges();
    syncReasonMoreButtons();
}

function loadLeaves(page, options = {}) {
    const shouldAnimate = options.animate !== false;

    fetch(buildDashboardAjaxUrl({ page }), {
        headers: {
            "X-Requested-With": "XMLHttpRequest"
        }
    })
    .then(res => typeof window.parseJsonOrSessionExpired === "function" ? window.parseJsonOrSessionExpired(res) : res.json())
    .then(data => {
        if (data.sessionExpired) {
            if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(data);
            return;
        }

        const container = document.getElementById("activityContainer");
        if (!container) return;

        if (shouldAnimate) {
            animateSlide(container, direction, () => renderActivityLeaves(container, data.leaves));
        } else {
            renderActivityLeaves(container, data.leaves);
        }

        currentPage = data.current_page;
        totalPages = data.total_pages || 1;
        const pageNumber = document.getElementById("pageNumber");
        if (pageNumber) pageNumber.innerText = `Page ${data.current_page} of ${data.total_pages}`;
        const firstBtn = document.querySelector(".first-btn");
        const prevBtn = document.querySelector(".prev-btn");
        const nextBtn = document.querySelector(".next-btn");
        const lastBtn = document.querySelector(".last-btn");
        if (firstBtn) firstBtn.disabled = !data.has_prev;
        if (prevBtn) prevBtn.disabled = !data.has_prev;
        if (nextBtn) nextBtn.disabled = !data.has_next;
        if (lastBtn) lastBtn.disabled = !data.has_next;
        if (lastBtn) lastBtn.dataset.totalPages = totalPages;

        const nav = document.querySelector(".pagination");
        if (nav) {
            if (!data.has_next && !data.has_prev) {
                nav.classList.add("hidden");
            } else {
                nav.classList.remove("hidden");
            }
        }
    })
    .catch(err => {
        console.error("Pagination Error:", err);
    });
}

function formatAppliedDateTime(dateStr) {
    if (!dateStr) return "--";

    let target = new Date(dateStr);

    if (isNaN(target)) {
        try {
            const clean = dateStr.replace(",", "");
            const parts = clean.split(" ");
            const monthMap = {
                January: 0, February: 1, March: 2, April: 3, May: 4, June: 5,
                July: 6, August: 7, September: 8, October: 9, November: 10, December: 11
            };

            const month = monthMap[parts[0]];
            const day = parseInt(parts[1], 10);
            const year = parseInt(parts[2], 10);

            let hours = 0;
            let minutes = 0;

            if (parts.length >= 5) {
                let [h, m] = parts[3].split(":").map(Number);
                const modifier = parts[4];

                if (modifier === "PM" && h !== 12) h += 12;
                if (modifier === "AM" && h === 12) h = 0;

                hours = h;
                minutes = m;
            }

            target = new Date(year, month, day, hours, minutes);
        } catch {
            return "--";
        }
    }

    if (isNaN(target)) return "--";

    const now = new Date();
    const diffMs = now - target;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHr = Math.floor(diffMin / 60);

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const targetDay = new Date(target);
    targetDay.setHours(0, 0, 0, 0);

    const diffDays = Math.round((targetDay - today) / (1000 * 60 * 60 * 24));
    const time = target.toLocaleTimeString("en-IN", {
        timeZone: INDIA_TIMEZONE,
        hour: "numeric",
        minute: "2-digit",
        hour12: true
    });

    if (diffSec < 60) return "Just now";
    if (diffMin < 60) return `${diffMin} min ago`;
    if (diffHr < 24 && diffDays === 0) return `${diffHr} hr ago`;
    if (diffDays === 0) return `Today, ${time}`;
    if (diffDays === -1) return `Yesterday, ${time}`;
    if (diffDays > -7) return `${Math.abs(diffDays)} days ago, ${time}`;

    return target.toLocaleString("en-IN", {
        timeZone: INDIA_TIMEZONE,
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true
    });
}

function formatExactDateTime(dateStr) {
    if (!dateStr) return "--";

    const parsed = new Date(dateStr);
    if (isNaN(parsed)) {
        return String(dateStr);
    }

    return parsed.toLocaleString("en-IN", {
        timeZone: INDIA_TIMEZONE,
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true
    });
}

function updateAppliedTimeElements(root = document) {
    root.querySelectorAll(".applied-time").forEach(el => {
        const createdTime = el.dataset.createdTime || el.dataset.time || "";
        const updatedTime = el.dataset.updatedTime || "";
        const displayTime = updatedTime || createdTime;
        const label = updatedTime ? "Updated" : "Applied";

        el.innerText = `${label}: ${formatAppliedDateTime(displayTime)}`;

        if (updatedTime && createdTime) {
            el.dataset.tooltip = `Applied: ${formatExactDateTime(createdTime)}`;
            el.classList.add("has-applied-tooltip");
            el.setAttribute("tabindex", "0");
        } else {
            delete el.dataset.tooltip;
            el.classList.remove("has-applied-tooltip");
            el.classList.remove("is-tooltip-open");
            el.removeAttribute("tabindex");
        }
    });
}

function closeAppliedTooltips() {
    document.querySelectorAll(".applied-time.is-tooltip-open").forEach(el => {
        el.classList.remove("is-tooltip-open");
    });
}

function formatShortDateLabel(dateStr) {
    if (!dateStr) return "--";

    const parsed = new Date(dateStr);
    if (isNaN(parsed)) {
        return String(dateStr);
    }

    return parsed.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric"
    });
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function getLeaveCardClass(leave) {
    return leave?.leave_type ? `leave-card-${String(leave.leave_type).toLowerCase()}` : "empty-leave-card";
}

function getEmptyLeaveCardHtml(variant, cardKind = "upcoming") {
    const isLast = cardKind === "last";
    const isFull = variant === "full";
    const iconClass = isFull ? "icon-flag" : "icon-clock";
    const icon = isFull ? "&#9873;" : "&#9719;";
    const label = isFull ? "Sick / Earned / Unpaid" : "Short / Half";
    const tag = isFull ? "Full Day" : "Time Based";
    const title = isFull
        ? (isLast ? "No full leave recorded" : "No full leave planned")
        : (isLast ? "No time leave recorded" : "No time leave planned");
    const text = isFull
        ? (isLast ? "<span class=\"dashboard-empty-full-history-line\">Your previous sick, earned, and unpaid</span><span class=\"dashboard-empty-full-history-line\">leave history will appear here.</span>" : "Sick, earned, and unpaid approvals will appear here.")
        : (isLast ? "<span class=\"dashboard-empty-short-history-line\">Your previous short and half-day</span><span class=\"dashboard-empty-short-history-line\">leave history will appear here.</span>" : "Short and half-day approvals will appear here.");
    const textClass = isLast ? ` class="${isFull ? "dashboard-empty-full-history" : "dashboard-empty-short-history"}"` : "";

    return `
        <div class="card-top">
            <div class="icon-badge-group">
                <div class="icon-badge ${iconClass}">${icon}</div>
                <span class="icon-label ${isFull ? "icon-label-full" : "icon-label-short"}">${label}</span>
            </div>
            <span class="type-tag">${tag}</span>
        </div>
        <div class="card-body">
            <div class="dashboard-empty-state">
                <span class="dashboard-empty-icon" aria-hidden="true">${isFull ? "&#9670;" : "&#9201;"}</span>
                <strong>${title}</strong>
                <p${textClass}>${text}</p>
            </div>
        </div>
    `;
}

function syncDashboardCardState(card, leave, variant, cardKind = "upcoming") {
    if (!card) return;

    card.classList.remove(
        "leave-card-sick",
        "leave-card-earned",
        "leave-card-unpaid",
        "leave-card-short",
        "leave-card-half",
        "empty-leave-card"
    );

    card.classList.add(getLeaveCardClass(leave));

    if (leave) {
        card.dataset.leaveType = leave.leave_type || "";
        const startValue = leave.timeline_start || leave.countdown_start || leave.progress_from || "";
        const endValue = leave.timeline_end || leave.countdown_end || leave.to_date || "";
        if (startValue) card.dataset.start = startValue;
        if (endValue) card.dataset.end = endValue;
    } else {
        delete card.dataset.leaveType;
        delete card.dataset.start;
        delete card.dataset.end;
    }
}

function renderDashboardLeaveInnerCard(leave, variant, cardKind = "upcoming") {
    if (!leave) {
        return getEmptyLeaveCardHtml(variant, cardKind);
    }

    if (variant === "short") {
        const iconLabelClass = leave.is_half ? "icon-label-half" : "icon-label-short";
        const durationText = leave.is_half ? "Half day for 4 hours" : "Short leave for 2 hours";
        const progressHtml = leave.card_kind === "upcoming"
            ? `
                <div class="leave-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" data-start="${escapeHtml(leave.timeline_start || leave.countdown_start || leave.progress_from)}" data-end="${escapeHtml(leave.timeline_end || leave.countdown_end)}"></div>
                    </div>
                    <div class="progress-text live-leave-status" data-kind="time" data-start="${escapeHtml(leave.timeline_start || leave.countdown_start || leave.progress_from)}" data-end="${escapeHtml(leave.timeline_end || leave.countdown_end)}"></div>
                </div>
            `
            : "";

        return `
            <div class="card-top">
                <div class="icon-badge-group">
                    <div class="icon-badge icon-clock">&#9719;</div>
                    <span class="icon-label ${iconLabelClass}">${escapeHtml(leave.leave_type)}</span>
                </div>
                <span class="type-tag">Time Based</span>
            </div>
            <div class="card-body">
                <div class="time-block">
                    <span>${escapeHtml(leave.from_time)}</span>
                    <span class="arrow">&rarr;</span>
                    <span>${escapeHtml(leave.to_time)}</span>
                </div>
                <p class="leave-date">${escapeHtml(leave.from_date)}</p>
                <p class="leave-meta applied-time" data-created-time="${escapeHtml(leave.created_at)}" data-updated-time="${escapeHtml(leave.updated_at || "")}"></p>
                <p class="leave-meta leave-duration leave-type-short">${durationText}</p>
                ${progressHtml}
            </div>
        `;
    }

    const fullDuration = `${leave.duration} day${leave.duration > 1 ? "s" : ""}`;
    const fullProgressHtml = leave.card_kind === "upcoming"
        ? `
            <div class="leave-progress">
                <div class="progress-bar">
                    <div class="progress-fill" data-start="${escapeHtml(leave.timeline_start || leave.progress_from)}" data-end="${escapeHtml(leave.timeline_end || leave.to_date)}" data-full-day="true"></div>
                </div>
                <div class="progress-text live-leave-status" data-kind="full" data-start="${escapeHtml(leave.timeline_start || leave.progress_from)}" data-end="${escapeHtml(leave.timeline_end || leave.to_date)}"></div>
            </div>
        `
        : "";

    return `
        <div class="card-top">
            <div class="icon-badge-group">
                <div class="icon-badge icon-flag">&#9873;</div>
                <span class="icon-label icon-label-full">${escapeHtml(leave.leave_type)}</span>
            </div>
            <span class="type-tag">Full Day</span>
        </div>
        <div class="card-body">
            <div class="date-range">
                <span>${escapeHtml(leave.from_date)}</span>
                <span class="arrow">&rarr;</span>
                <span>${escapeHtml(leave.to_date)}</span>
            </div>
            <p class="leave-meta applied-time" data-created-time="${escapeHtml(leave.created_at)}" data-updated-time="${escapeHtml(leave.updated_at || "")}"></p>
            ${leave.card_kind === "last" ? `<p class="leave-meta leave-duration leave-type-fulltype">${fullDuration}</p>` : ""}
            ${fullProgressHtml}
        </div>
    `;
}

function updateDashboardCard(selector, leave, variant, emptyText, cardKind = "upcoming") {
    const card = document.querySelector(selector);
    if (!card) return;

    syncDashboardCardState(card, leave, variant, cardKind);
    card.innerHTML = leave
        ? renderDashboardLeaveInnerCard(leave, variant, cardKind)
        : getEmptyLeaveCardHtml(variant, cardKind);
}

function formatStatValue(value, decimals = 2) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
        return "0";
    }
    return numericValue.toFixed(decimals).replace(/\.00$/, "").replace(/(\.\d*[1-9])0+$/, "$1");
}

function formatBalanceStatValue(value, decimals = 2) {
    const formattedValue = formatStatValue(value, decimals);
    if (formattedValue === "0") return "00";

    const sign = formattedValue.startsWith("-") ? "-" : "";
    const unsignedValue = sign ? formattedValue.slice(1) : formattedValue;
    const [wholePart, decimalPart] = unsignedValue.split(".");
    const paddedWhole = wholePart.padStart(2, "0");

    return `${sign}${paddedWhole}${decimalPart ? `.${decimalPart}` : ""}`;
}

function normalizeBalanceCardNumbers() {
    document.querySelectorAll(".overview-card .stat-card .count").forEach(el => {
        const targetValue = el.dataset.balanceCountTarget || el.textContent;
        el.textContent = formatBalanceStatValue(targetValue);
    });
}

function updateDashboardSummary(summary) {
    if (!summary) return;

    const balanceValueEl = document.querySelector(".balance-value");
    if (balanceValueEl) {
        balanceValueEl.textContent = formatStatValue(summary.leaves_remaining);
    }

    const balanceTotalValueEl = document.querySelector(".balance-total-value");
    if (balanceTotalValueEl) {
        balanceTotalValueEl.textContent = formatStatValue(summary.leave_total_value);
    }

    const earnedCard = document.querySelector(".earned-balance-card");
    if (earnedCard) {
        const countEl = earnedCard.querySelector(".count");
        const metaEl = earnedCard.querySelector("small");
        if (countEl) {
            countEl.dataset.balanceCountTarget = String(summary.earned_remaining);
            countEl.textContent = formatBalanceStatValue(summary.earned_remaining);
        }
        if (metaEl) metaEl.textContent = `${formatBalanceStatValue(summary.earned_used)} used of ${formatBalanceStatValue(summary.earned_total)}`;
    }

    const sickCard = document.querySelector(".sick-balance-card");
    if (sickCard) {
        const countEl = sickCard.querySelector(".count");
        const metaEl = sickCard.querySelector("small");
        if (countEl) {
            countEl.dataset.balanceCountTarget = String(summary.sick_remaining);
            countEl.textContent = formatBalanceStatValue(summary.sick_remaining);
        }
        if (metaEl) metaEl.textContent = `${formatBalanceStatValue(summary.sick_used)} used of ${formatBalanceStatValue(summary.sick_total)}`;
    }

    const unpaidCard = document.querySelector(".unpaid-balance-card");
    if (unpaidCard) {
        const countEl = unpaidCard.querySelector(".count");
        const metaEl = unpaidCard.querySelector("small");
        if (countEl) {
            countEl.dataset.balanceCountTarget = String(summary.unpaid_used);
            countEl.textContent = formatBalanceStatValue(summary.unpaid_used);
        }
        if (metaEl) metaEl.textContent = "Used so far";
    }

    const approvedCard = document.querySelector(".approved-card");
    if (approvedCard) {
        const countEl = approvedCard.querySelector(".count");
        if (countEl) {
            countEl.dataset.balanceCountTarget = String(summary.approved_count ?? 0);
            countEl.textContent = formatBalanceStatValue(summary.approved_count ?? 0, 0);
        }
    }

    const pendingCard = document.querySelector(".pending-card");
    if (pendingCard) {
        const countEl = pendingCard.querySelector(".count");
        if (countEl) {
            countEl.dataset.balanceCountTarget = String(summary.pending_count ?? 0);
            countEl.textContent = formatBalanceStatValue(summary.pending_count ?? 0, 0);
        }

        const existingAlert = pendingCard.querySelector(".stat-alert");
        const existingSmall = pendingCard.querySelector("small");
        if ((summary.pending_count ?? 0) > 2) {
            if (existingSmall) existingSmall.remove();
            if (!existingAlert) {
                const alert = document.createElement("div");
                alert.className = "warning-text stat-alert";
                alert.textContent = "Needs attention";
                pendingCard.appendChild(alert);
            }
        } else {
            if (existingAlert) existingAlert.remove();
            if (!existingSmall) {
                const small = document.createElement("small");
                small.textContent = "Awaiting review";
                pendingCard.appendChild(small);
            } else {
                existingSmall.textContent = "Awaiting review";
            }
        }
    }

    const rejectedCard = document.querySelector(".rejected-card");
    if (rejectedCard) {
        const countEl = rejectedCard.querySelector(".count");
        if (countEl) {
            countEl.dataset.balanceCountTarget = String(summary.rejected_count ?? 0);
            countEl.textContent = formatBalanceStatValue(summary.rejected_count ?? 0, 0);
        }
    }
}

function refreshDashboardCards() {
    fetch(buildDashboardAjaxUrl({ section: "cards" }), {
        headers: {
            "X-Requested-With": "XMLHttpRequest"
        }
    })
    .then(res => {
        if (!res.ok) {
            throw new Error("Unable to refresh dashboard cards.");
        }
        return typeof window.parseJsonOrSessionExpired === "function" ? window.parseJsonOrSessionExpired(res) : res.json();
    })
    .then(data => {
        if (data.sessionExpired) {
            if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(data);
            return;
        }

        updateDashboardSummary(data.summary || null);
        updateDashboardCard(".main-leave-card.upcoming .inner-leave-card.short", data.upcoming?.short || null, "short", "No short leave planned", "upcoming");
        updateDashboardCard(".main-leave-card.upcoming .inner-leave-card.full", data.upcoming?.full || null, "full", "No full leave planned", "upcoming");
        updateDashboardCard(".main-leave-card.last .inner-leave-card.short", data.last?.short || null, "short", "No short leave recorded", "last");
        updateDashboardCard(".main-leave-card.last .inner-leave-card.full", data.last?.full || null, "full", "No full leave recorded", "last");

        updateAppliedTimeElements();

        document.querySelectorAll(".time-block").forEach(block => {
            const parts = block.querySelectorAll("span");
            if (parts.length >= 3) {
                parts[0].textContent = formatIndiaTime(parts[0].textContent);
                parts[2].textContent = formatIndiaTime(parts[2].textContent);
            }
        });

        animateLeaveProgress();
        startCountdown();
        loadLeaves(currentPage, { animate: false });
    })
    .catch(err => {
        console.error("Dashboard card refresh error:", err);
    });
}

function nextPage() {
    if (currentPage >= totalPages) return;
    direction = "next";
    loadLeaves(currentPage + 1);
}

function prevPage() {
    if (currentPage > 1) {
        direction = "prev";
        loadLeaves(currentPage - 1);
    }
}

function firstPage() {
    if (currentPage <= 1) return;
    direction = "prev";
    loadLeaves(1);
}

function lastPage() {
    if (currentPage >= totalPages) return;
    direction = "next";
    loadLeaves(totalPages);
}

function getReasonModalTypeClass(leaveType) {
    const key = String(leaveType || "").toLowerCase();
    return ["sick", "unpaid", "earned", "short", "half"].includes(key) ? key : "default";
}

function getReasonModalContext(status) {
    const key = String(status || "").toLowerCase();
    if (key === "approved") return "approved";
    if (key === "rejected") return "rejected-employee";
    return "pending";
}

function formatReasonModalRelativeAge(isoValue) {
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

function formatReasonModalClockTime(isoValue) {
    if (!isoValue) return "-";
    const target = new Date(isoValue);
    if (Number.isNaN(target.getTime())) return "-";
    return target.toLocaleTimeString("en-IN", {
        timeZone: INDIA_TIMEZONE,
        hour: "numeric",
        minute: "2-digit",
        hour12: true
    });
}

function setReasonModalLabel(element, icon, label) {
    if (!element) return;
    element.innerHTML = `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">${icon}</span><span>${label}</span></span>`;
}

let dashboardReasonModalCloseTimer = null;

function openReasonModal(sourceElement) {
    const modalreason = document.getElementById("reasonModal");
    const title = document.getElementById("reasonModalTitle");
    const content = document.getElementById("reasonModalContent");
    const employee = document.getElementById("reasonModalEmployee");
    const leaveType = document.getElementById("reasonModalLeaveType");
    const metaGrid = document.getElementById("reasonModalMetaGrid");
    const scheduleDate = document.getElementById("reasonModalScheduleDate");
    const scheduleTime = document.getElementById("reasonModalScheduleTime");
    const days = document.getElementById("reasonModalDays");
    const applied = document.getElementById("reasonModalApplied");
    const appliedTime = document.getElementById("reasonModalAppliedTime");
    const updated = document.getElementById("reasonModalUpdated");
    const updatedTime = document.getElementById("reasonModalUpdatedTime");
    const decisionCard = document.getElementById("reasonModalDecisionCard");
    const decisionLabel = document.getElementById("reasonModalDecisionLabel");
    const decision = document.getElementById("reasonModalDecision");
    const decisionTime = document.getElementById("reasonModalDecisionTime");
    const fieldLabel = document.getElementById("reasonModalFieldLabel");

    if (!modalreason || !content) return;

    if (dashboardReasonModalCloseTimer) {
        clearTimeout(dashboardReasonModalCloseTimer);
        dashboardReasonModalCloseTimer = null;
    }

    const reasonBox = sourceElement?.closest?.(".reason-box");
    const reasonContent = reasonBox?.querySelector(".reason-content");
    const status = reasonBox?.dataset.status || "";
    const type = reasonBox?.dataset.leaveType || "Leave";
    const typeClass = getReasonModalTypeClass(type);
    const context = getReasonModalContext(status);
    const contextLabels = {
        pending: { title: "Pending Leave Reason", label: "Pending Reason", icon: "&#9203;" },
        approved: { title: "Approved Leave Reason", label: "Approved Reason", icon: "&#10003;" },
        "rejected-employee": { title: "Rejected Leave Reason", label: "Employee Reason", icon: "&#128221;" }
    };
    const contextCopy = contextLabels[context] || contextLabels.pending;
    const decisionIso = context === "approved" ? reasonBox?.dataset.approved : context === "rejected-employee" ? reasonBox?.dataset.rejected : "";
    const hasDecision = Boolean(decisionIso);
    const showScheduleTime = typeClass === "short" || typeClass === "half";
    const durationValue = Number.parseInt(reasonBox?.dataset.duration || "0", 10);
    const daysDisplay = typeClass === "short"
        ? "2 hours"
        : typeClass === "half"
            ? "4 hours"
            : `${durationValue || "-"} ${durationValue === 1 ? "day" : "days"}`;

    if (sourceElement && typeof sourceElement.getBoundingClientRect === "function") {
        const anchorRect = sourceElement.getBoundingClientRect();
        modalreason.style.setProperty("--reason-origin-x", (anchorRect.left + anchorRect.width / 2 - window.innerWidth / 2) + "px");
        modalreason.style.setProperty("--reason-origin-y", (anchorRect.top + anchorRect.height / 2 - window.innerHeight / 2) + "px");
    }

    modalreason.classList.remove(
        "reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half", "reason-theme-default",
        "reason-context-pending", "reason-context-approved", "reason-context-rejected-employee", "reason-context-rejected-note",
        "is-closing"
    );
    modalreason.classList.add("reason-theme-" + typeClass, "reason-context-" + context);

    if (title) title.textContent = contextCopy.title;
    if (employee) employee.textContent = "My Leave";
    if (leaveType) {
        leaveType.textContent = `${type} Leave`;
        leaveType.className = "reason-modal-chip reason-modal-type-chip reason-modal-type-" + typeClass;
    }
    if (scheduleDate) scheduleDate.textContent = `${reasonBox?.dataset.fromDate || "-"} \u27F6 ${reasonBox?.dataset.toDate || "-"}`;
    if (scheduleTime) {
        scheduleTime.textContent = showScheduleTime ? `${reasonBox?.dataset.fromTime || "-"} \u27F6 ${reasonBox?.dataset.toTime || "-"}` : "";
        scheduleTime.hidden = !showScheduleTime;
        scheduleTime.classList.toggle("reason-modal-schedule-time-accent", showScheduleTime);
    }
    if (days) days.textContent = daysDisplay;
    if (applied) applied.textContent = formatReasonModalRelativeAge(reasonBox?.dataset.created) || "-";
    if (appliedTime) appliedTime.textContent = formatReasonModalClockTime(reasonBox?.dataset.created);
    if (updated) updated.textContent = reasonBox?.dataset.updated ? (formatReasonModalRelativeAge(reasonBox.dataset.updated) || "-") : "Not updated";
    if (updatedTime) updatedTime.textContent = reasonBox?.dataset.updated ? formatReasonModalClockTime(reasonBox.dataset.updated) : "-";
    if (metaGrid) metaGrid.classList.toggle("has-decision", hasDecision);
    if (decisionCard) decisionCard.hidden = !hasDecision;
    if (decisionLabel) setReasonModalLabel(decisionLabel, context === "rejected-employee" ? "&#9940;" : "&#10003;", context === "rejected-employee" ? "Rejected At" : "Approved At");
    if (decision) decision.textContent = hasDecision ? (formatReasonModalRelativeAge(decisionIso) || "-") : "-";
    if (decisionTime) decisionTime.textContent = hasDecision ? formatReasonModalClockTime(decisionIso) : "-";
    setReasonModalLabel(fieldLabel, contextCopy.icon, contextCopy.label);
    content.innerText = sourceElement?.dataset.reason || reasonContent?.dataset.full || reasonContent?.textContent?.trim() || "No reason provided";
    modalreason.style.display = "flex";
    modalreason.classList.remove("is-closing");
    modalreason.setAttribute("aria-hidden", "false");
    requestAnimationFrame(function () {
        modalreason.classList.add("show", "is-open");
    });
    document.body.style.overflow = "hidden";
}

function closeReasonModal() {
    const modal = document.getElementById("reasonModal");
    if (modal) {
        modal.classList.remove("is-open");
        modal.classList.add("is-closing");
        modal.setAttribute("aria-hidden", "true");
        if (dashboardReasonModalCloseTimer) {
            clearTimeout(dashboardReasonModalCloseTimer);
        }
        dashboardReasonModalCloseTimer = setTimeout(function () {
            modal.classList.remove("show", "is-closing");
            modal.style.display = "none";
            modal.classList.remove(
                "reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half",
                "reason-context-pending", "reason-context-approved", "reason-context-rejected-employee", "reason-context-rejected-note"
            );
            modal.classList.add("reason-theme-default");
            dashboardReasonModalCloseTimer = null;
            document.body.style.overflow = "";
        }, 400);
    }
}

document.addEventListener("DOMContentLoaded", function() {
    const reasonModal = document.getElementById("reasonModal");
    if (reasonModal) {
        reasonModal.style.display = "none";
        reasonModal.setAttribute("aria-hidden", "true");
    }

    setInterval(rotateQuotes, 10000);

    document.querySelectorAll(".inner-leave-card").forEach(card => {
        card.addEventListener("mouseenter", () => {
            card.style.zIndex = "2";
        });

        card.addEventListener("mouseleave", () => {
            card.style.zIndex = "1";
        });
    });

    updateAppliedTimeElements();

    document.querySelectorAll(".time-block").forEach(block => {
        const parts = block.querySelectorAll("span");
        if (parts.length >= 3) {
            parts[0].textContent = formatIndiaTime(parts[0].textContent);
            parts[2].textContent = formatIndiaTime(parts[2].textContent);
        }
    });

    document.querySelectorAll(".duration-number").forEach(el => {
        const value = parseInt(el.innerText, 10);
        const unit = el.dataset.unit;

        if (!isNaN(value)) {
            animateNumber(el, 0, value, unit === "hour" ? 2000 : 1500);
        }
    });

    updateNewBadges();
    normalizeBalanceCardNumbers();
    const activityContainer = document.getElementById("activityContainer");
    if (activityContainer) {
        activityContainer.classList.toggle("is-empty", !activityContainer.querySelector(".activity-card"));
    }
    setTimeout(normalizeBalanceCardNumbers, 1800);
    setTimeout(normalizeBalanceCardNumbers, 2600);
    animateLeaveProgress();
    startCountdown();
    initDashboardDividerPointer();

    const nav = document.querySelector(".pagination");
    if (nav) {
        const hasNext = nav.dataset.hasNext === "true";
        const hasPrev = nav.dataset.hasPrev === "true";
        const lastBtn = nav.querySelector(".last-btn");
        totalPages = Number.parseInt(lastBtn?.dataset.totalPages || "1", 10) || 1;

        if (!hasNext && !hasPrev) {
            nav.classList.add("hidden");
        } else {
            nav.classList.remove("hidden");
        }
    }

    syncReasonMoreButtons();
    window.addEventListener("resize", syncReasonMoreButtons);

    setTimeout(() => {
        isPageLoaded = true;
        syncReasonMoreButtons();
    }, 300);
});

document.addEventListener("countup:refresh", function () {
    setTimeout(normalizeBalanceCardNumbers, 360);
});

function syncReasonMoreButtons() {
    document.querySelectorAll(".reason-content").forEach(el => {
        const box = el.closest(".reason-box");
        if (!box) return;
        let moreBtn = box.querySelector(".more-btn");
        const fullReason = el.dataset.full || el.textContent.trim();

        // Reset display to check natural height
        if (moreBtn) moreBtn.style.display = "none";
        
        // We detect overflow by comparing scrollHeight to clientHeight.
        const isClamped = el.scrollHeight > (el.clientHeight + 2); // Add small buffer
        const shouldShowMore = isClamped;
        
        if (shouldShowMore) {
            if (!moreBtn) {
                moreBtn = document.createElement("span");
                moreBtn.className = "more-btn";
                moreBtn.textContent = "... more";
                box.appendChild(moreBtn);
            }
            moreBtn.dataset.reason = fullReason;
            moreBtn.style.display = "inline-block";
        }
    });
}

document.addEventListener("click", function(e) {
    const firstPageBtn = e.target.closest("[data-action='dashboard-first-page']");
    if (firstPageBtn) {
        e.preventDefault();
        firstPage();
        return;
    }

    const prevPageBtn = e.target.closest("[data-action='dashboard-prev-page']");
    if (prevPageBtn) {
        e.preventDefault();
        prevPage();
        return;
    }

    const nextPageBtn = e.target.closest("[data-action='dashboard-next-page']");
    if (nextPageBtn) {
        e.preventDefault();
        nextPage();
        return;
    }

    const lastPageBtn = e.target.closest("[data-action='dashboard-last-page']");
    if (lastPageBtn) {
        e.preventDefault();
        lastPage();
        return;
    }

    if (e.target.closest("[data-action='close-reason-modal']")) {
        e.preventDefault();
        closeReasonModal();
        return;
    }

    const appliedTime = e.target.closest(".applied-time.has-applied-tooltip");
    if (appliedTime) {
        e.preventDefault();
        e.stopPropagation();
        const shouldOpen = !appliedTime.classList.contains("is-tooltip-open");
        closeAppliedTooltips();
        if (shouldOpen) {
            appliedTime.classList.add("is-tooltip-open");
        }
        return;
    }

    closeAppliedTooltips();

    const moreBtn = e.target.closest(".more-btn");
    if (moreBtn) {
        e.preventDefault();
        e.stopPropagation();
        openReasonModal(moreBtn);
        return;
    }

    const modal = document.getElementById("reasonModal");
    if (modal && e.target === modal) {
        closeReasonModal();
    }
});

setInterval(() => {
    updateAppliedTimeElements();

    updateNewBadges();
}, 60000);

document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") {
        closeReasonModal();
    }
});

let lastDashboardNotificationSignature = "";

window.addEventListener("hr-notification-state-sync", function (event) {
    const detail = event.detail || {};
    if (!Array.isArray(detail.notifications)) {
        return;
    }

    const nextSignature = detail.notifications.map(function (item) {
        return [
            item.id,
            item.status,
            item.updated_at || item.updated || "",
            item.is_read ? "read" : "unread"
        ].join(":");
    }).join("|");

    if (nextSignature === lastDashboardNotificationSignature) {
        return;
    }

    lastDashboardNotificationSignature = nextSignature;
    refreshDashboardCards();
});
