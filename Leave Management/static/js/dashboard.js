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
let countdownTimers = [];

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

function activateLine(card) {
    const dot = document.getElementById("activeDot");
    const wrapper = document.querySelector(".leave-wrapper");

    if (!dot || !wrapper || !card) return;

    const cardRect = card.getBoundingClientRect();
    const wrapperRect = wrapper.getBoundingClientRect();
    const offset = cardRect.top - wrapperRect.top + (cardRect.height / 2);

    dot.style.top = offset + "px";
    dot.classList.add("active");
}

function animateLeaveProgress() {
    document.querySelectorAll(".leave-progress .progress-fill").forEach(bar => {
        const fromValue = bar.dataset.from;
        if (!fromValue) return;

        const fromDate = new Date(fromValue);
        const today = new Date();
        const totalDays = 30;
        const diff = (fromDate - today) / (1000 * 60 * 60 * 24);
        const percent = Math.max(0, Math.min(100, 100 - (diff * 100 / totalDays)));

        setTimeout(() => {
            bar.style.width = percent + "%";
        }, 200);
    });
}

function startCountdown() {
    countdownTimers.forEach(timerId => clearInterval(timerId));
    countdownTimers = [];

    document.querySelectorAll(".live-countdown").forEach(el => {
        const start = new Date(el.dataset.start || el.dataset.time);
        const end = new Date(el.dataset.end || el.dataset.time);

        if (isNaN(start) || isNaN(end)) {
            el.innerText = "Invalid time";
            return;
        }

        function update() {
            const now = new Date();
            const startDiff = start - now;
            const endDiff = end - now;
            const startingNowWindow = start.getTime() + (15 * 60 * 1000);

            if (now >= end) {
                el.innerText = "Leave completed";
                el.classList.remove("urgent");
                return;
            }

            if (now >= start && now < new Date(startingNowWindow)) {
                el.innerText = "Starting now";
                el.classList.add("urgent");
                return;
            }

            const diff = now < start ? startDiff : endDiff;
            const hrs = Math.floor(diff / (1000 * 60 * 60));
            const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const secs = Math.floor((diff % (1000 * 60)) / 1000);
            const totalMinutes = diff / (1000 * 60);

            if (now < start) {
                el.innerText = `Starts in ${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
            } else {
                el.innerText = `Time left ${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
            }

            if (now < start && totalMinutes <= 15) {
                el.classList.add("urgent");
            } else {
                el.classList.remove("urgent");
            }
        }

        update();
        countdownTimers.push(setInterval(update, 1000));
    });
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
    container.classList.remove("slide-in-left", "slide-in-right", "slide-out-left", "slide-out-right");
    void container.offsetWidth;
    container.classList.add(directionValue === "next" ? "slide-out-left" : "slide-out-right");

    setTimeout(() => {
        callback();
        container.classList.remove("slide-out-left", "slide-out-right");
        void container.offsetWidth;
        container.classList.add(directionValue === "next" ? "slide-in-right" : "slide-in-left");

        setTimeout(() => {
            container.classList.remove("slide-in-left", "slide-in-right");
        }, 320);
    }, 240);
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
        const parts = leave.from_datetime.split(" ");
        const fromTime = parts.slice(3).join(" ");

        bodyHTML = `
            <p class="date-line"><strong>${fromDateLabel}</strong></p>
            <p class="date-line time-line">
                <strong>${fromTime}</strong>
                <span class="arrow">&rarr;</span>
                <strong>${leave.to_datetime}</strong>
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
        <div class="activity-card ${leave.status.toLowerCase()} ${activityTypeClass}">
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

function loadLeaves(page) {
    fetch(`/dashboard?page=${page}`, {
        headers: {
            "X-Requested-With": "XMLHttpRequest"
        }
    })
    .then(res => res.json())
    .then(data => {
        const container = document.getElementById("activityContainer");
        if (!container) return;

        animateSlide(container, direction, () => {
            container.innerHTML = "";

            if (!data.leaves || data.leaves.length === 0) {
                container.innerHTML = "<p class='empty-state'>No recent activity</p>";
                return;
            }

            data.leaves.forEach(leave => {
                const isNew = isNewEntry(leave.created);
                container.insertAdjacentHTML("beforeend", renderLeaveCard(leave, isNew));

                const card = container.lastElementChild;
                const durationEl = card.querySelector(".duration-number");

                if (durationEl) {
                    const value = parseInt(durationEl.innerText, 10);
                    const unit = durationEl.dataset.unit;

                    if (!isNaN(value)) {
                        animateNumber(durationEl, 0, value, unit === "hour" ? 2000 : 1500);
                    }
                }
            });

            updateAppliedTimeElements(container);
            updateNewBadges();
            syncReasonMoreButtons();
        });

        currentPage = data.current_page;
        totalPages = data.total_pages || 1;
        document.getElementById("pageNumber").innerText = `Page ${data.current_page} of ${data.total_pages}`;
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
        if (!data.has_next && !data.has_prev) {
            nav.classList.add("hidden");
        } else {
            nav.classList.remove("hidden");
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

function renderDashboardLeaveInnerCard(leave, variant) {
    if (!leave) {
        const emptyText = variant === "full"
            ? (leave && leave.card_kind === "last" ? "No full leave recorded" : "No full leave planned")
            : (leave && leave.card_kind === "last" ? "No short leave recorded" : "No short leave planned");
        return `<p class="empty">${emptyText}</p>`;
    }

    if (variant === "short") {
        const iconLabelClass = leave.is_half ? "icon-label-half" : "icon-label-short";
        const durationText = leave.is_half ? "Half day for 4 hours" : "Short leave for 2 hours";
        const progressHtml = leave.card_kind === "upcoming"
            ? `
                <div class="leave-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" data-from="${escapeHtml(leave.progress_from)}"></div>
                    </div>
                    <div class="progress-text">
                        ${leave.is_today
                            ? `<span class="live-countdown" data-start="${escapeHtml(leave.countdown_start)}" data-end="${escapeHtml(leave.countdown_end)}"></span>`
                            : `${leave.days_left} days left`}
                    </div>
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
                    <div class="progress-fill" data-from="${escapeHtml(leave.progress_from)}"></div>
                </div>
                <div class="progress-text">${leave.days_left} days left</div>
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

function updateDashboardCard(selector, leave, variant, emptyText) {
    const card = document.querySelector(selector);
    if (!card) return;

    card.innerHTML = leave
        ? renderDashboardLeaveInnerCard(leave, variant)
        : `<p class="empty">${emptyText}</p>`;
}

function formatStatValue(value, decimals = 2) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
        return "0";
    }
    return numericValue.toFixed(decimals).replace(/\.00$/, "").replace(/(\.\d*[1-9])0+$/, "$1");
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
        if (countEl) countEl.textContent = formatStatValue(summary.earned_remaining);
        if (metaEl) metaEl.textContent = `${formatStatValue(summary.earned_used)} used of ${formatStatValue(summary.earned_total)}`;
    }

    const sickCard = document.querySelector(".sick-balance-card");
    if (sickCard) {
        const countEl = sickCard.querySelector(".count");
        const metaEl = sickCard.querySelector("small");
        if (countEl) countEl.textContent = formatStatValue(summary.sick_remaining);
        if (metaEl) metaEl.textContent = `${formatStatValue(summary.sick_used)} used of ${formatStatValue(summary.sick_total)}`;
    }

    const unpaidCard = document.querySelector(".unpaid-balance-card");
    if (unpaidCard) {
        const countEl = unpaidCard.querySelector(".count");
        const metaEl = unpaidCard.querySelector("small");
        if (countEl) countEl.textContent = formatStatValue(summary.unpaid_used);
        if (metaEl) metaEl.textContent = `${formatStatValue(summary.unpaid_used)} used so far`;
    }

    const approvedCard = document.querySelector(".approved-card");
    if (approvedCard) {
        const countEl = approvedCard.querySelector(".count");
        if (countEl) countEl.textContent = String(summary.approved_count ?? 0);
    }

    const pendingCard = document.querySelector(".pending-card");
    if (pendingCard) {
        const countEl = pendingCard.querySelector(".count");
        if (countEl) countEl.textContent = String(summary.pending_count ?? 0);

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
        if (countEl) countEl.textContent = String(summary.rejected_count ?? 0);
    }
}

function refreshDashboardCards() {
    fetch("/dashboard?section=cards", {
        headers: {
            "X-Requested-With": "XMLHttpRequest"
        }
    })
    .then(res => {
        if (!res.ok) {
            throw new Error("Unable to refresh dashboard cards.");
        }
        return res.json();
    })
    .then(data => {
        updateDashboardSummary(data.summary || null);
        updateDashboardCard(".main-leave-card.upcoming .inner-leave-card.short", data.upcoming?.short || null, "short", "No short leave planned");
        updateDashboardCard(".main-leave-card.upcoming .inner-leave-card.full", data.upcoming?.full || null, "full", "No full leave planned");
        updateDashboardCard(".main-leave-card.last .inner-leave-card.short", data.last?.short || null, "short", "No short leave recorded");
        updateDashboardCard(".main-leave-card.last .inner-leave-card.full", data.last?.full || null, "full", "No full leave recorded");

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

    const reasonBox = sourceElement?.closest?.(".reason-box");
    const reasonContent = reasonBox?.querySelector(".reason-content");
    const status = reasonBox?.dataset.status || "";
    const type = reasonBox?.dataset.leaveType || "Leave";
    const typeClass = getReasonModalTypeClass(type);
    const context = getReasonModalContext(status);
    const contextLabels = {
        pending: { title: "Pending Reason", label: "Pending Reason", icon: "&#9203;" },
        approved: { title: "Approved Reason", label: "Approved Reason", icon: "&#10003;" },
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
    modalreason.classList.add("show", "is-open");
    modalreason.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
}

function closeReasonModal() {
    const modal = document.getElementById("reasonModal");
    if (modal) {
        modal.classList.remove("show", "is-open", "is-closing");
        modal.style.display = "none";
        modal.setAttribute("aria-hidden", "true");
        modal.classList.remove(
            "reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half",
            "reason-context-pending", "reason-context-approved", "reason-context-rejected-employee", "reason-context-rejected-note"
        );
        modal.classList.add("reason-theme-default");
    }
    document.body.style.overflow = "";
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
    animateLeaveProgress();
    startCountdown();

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
        const shouldShowMore = isClamped || fullReason.length > 30;
        
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

window.addEventListener("hr-notification-state-sync", function (event) {
    const detail = event.detail || {};
    if (!Array.isArray(detail.notifications)) {
        return;
    }

    refreshDashboardCards();
});
