const dashboardModalAnimationMs = 120;
    let rejectModalCloseTimer = null;
    let reasonModalCloseTimer = null;
    let dashboardQueueRequest = null;
    let dashboardLiveRefreshRequest = null;
    let dashboardKnownNotificationSignature = null;
    let activeReasonAnchor = null;
    let currentRejectLeaveId = null;
    let currentRejectLeaveSnapshot = null;
    let decisionConfirmState = null;

    const heroQuotes = [
        {
            text: "The purpose of an organization is to enable common men to do uncommon things.",
            author: "Peter Drucker",
            source: "Management: Tasks, Responsibilities, Practices"
        },
        {
            text: "Leadership is the art of accomplishing more than the science of management says is possible.",
            author: "Colin Powell",
            source: "The Powell Principles"
        },
        {
            text: "You can't make good decisions unless you have good information and can separate facts from opinion and speculation.",
            author: "Colin Powell",
            source: "It Worked For Me: In Life and Leadership"
        },
        {
            text: "Management is doing things right; leadership is doing the right things.",
            author: "Peter Drucker",
            source: "Management thinker"
        },
        {
            text: "The best way to predict the future is to create it.",
            author: "Peter Drucker",
            source: "Leadership principle"
        },
        {
            text: "Outstanding leaders go out of their way to boost the self-esteem of their personnel.",
            author: "Sam Walton",
            source: "Made in America"
        },
        {
            text: "A leader is one who knows the way, goes the way, and shows the way.",
            author: "John C. Maxwell",
            source: "Leadership Gold"
        },
        {
            text: "The growth and development of people is the highest calling of leadership.",
            author: "Harvey S. Firestone",
            source: "Leadership principle"
        },
        {
            text: "Hire character. Train skill.",
            author: "Peter Schutz",
            source: "Leadership principle"
        },
        {
            text: "People may take a job for more money, but they often leave it for more recognition.",
            author: "Bob Nelson",
            source: "1001 Ways to Reward Employees"
        },
        {
            text: "Leadership is about making others better as a result of your presence.",
            author: "Sheryl Sandberg",
            source: "Leadership principle"
        },
        {
            text: "The function of leadership is to produce more leaders, not more followers.",
            author: "Ralph Nader",
            source: "Leadership principle"
        },
        {
            text: "Train people well enough so they can leave, treat them well enough so they don't want to.",
            author: "Richard Branson",
            source: "Leadership principle"
        },
        {
            text: "Customers will never love a company until the employees love it first.",
            author: "Simon Sinek",
            source: "Leadership principle"
        },
        {
            text: "When people are financially invested, they want a return. When people are emotionally invested, they want to contribute.",
            author: "Simon Sinek",
            source: "Start With Why"
        },
        {
            text: "Great vision without great people is irrelevant.",
            author: "Jim Collins",
            source: "Good to Great"
        },
        {
            text: "The way management treats associates is exactly how the associates will treat the customers.",
            author: "Sam Walton",
            source: "Made in America"
        },
        {
            text: "Before you are a leader, success is all about growing yourself. When you become a leader, success is all about growing others.",
            author: "Jack Welch",
            source: "Leadership principle"
        },
        {
            text: "To win in the marketplace you must first win in the workplace.",
            author: "Doug Conant",
            source: "Leadership principle"
        },
        {
            text: "The speed of the boss is the speed of the team.",
            author: "Lee Iacocca",
            source: "Leadership principle"
        },
        {
            text: "Effective leadership is not about making speeches or being liked; leadership is defined by results.",
            author: "Peter Drucker",
            source: "Management thinker"
        },
        {
            text: "Do not hire a man who does your work for money, but him who does it for love of it.",
            author: "Henry David Thoreau",
            source: "Leadership principle"
        },
        {
            text: "An organization's ability to learn, and translate that learning into action rapidly, is the ultimate competitive advantage.",
            author: "Jack Welch",
            source: "Leadership principle"
        },
        {
            text: "Culture is simply a shared way of doing something with passion.",
            author: "Brian Chesky",
            source: "Leadership principle"
        },
        {
            text: "Treat employees like they make a difference and they will.",
            author: "Jim Goodnight",
            source: "Leadership principle"
        },
        {
            text: "Leaders think and talk about the solutions. Followers think and talk about the problems.",
            author: "Brian Tracy",
            source: "Leadership principle"
        },
        {
            text: "Time is the scarcest resource, and unless it is managed, nothing else can be managed.",
            author: "Peter Drucker",
            source: "Management thinker"
        }
    ];

    let currentHeroQuote = 0;

    function renderHeroQuote(index)
    {
        const quote = heroQuotes[index];
        const quoteText = document.getElementById("heroQuoteText");

        if (!quoteText)
        {
            return;
        }

        quoteText.textContent = quote.text;
    }

    function rotateHeroQuote()
    {
        currentHeroQuote = (currentHeroQuote + 1) % heroQuotes.length;
        renderHeroQuote(currentHeroQuote);
    }

    function updateRelativeAppliedTime()
    {
        document.querySelectorAll(".applied-relative").forEach(function (element)
        {
            const rawTime = element.dataset.time;
            const formatted = formatRelativeLeaveAge(rawTime);
            if (formatted)
            {
                element.textContent = formatted;
            }
        });
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
            const match = String(fallbackValue).match(/(\d{1,2}:\d{2}\s?[AP]M)$/i);
            if (match)
            {
                return match[1].replace(/\s+/g, " ").toUpperCase();
            }
        }

        return "-";
    }

    function formatPopupDateLabel(isoValue, fallbackValue)
    {
        const relativeLabel = formatRelativeLeaveAge(isoValue);

        if (relativeLabel)
        {
            return relativeLabel;
        }

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
            const dateOnly = String(fallbackValue)
                .replace(/\s+\d{1,2}:\d{2}\s?[AP]M$/i, "")
                .trim();

            return dateOnly || "-";
        }

        return "-";
    }

    function hydrateRelativeUpdatedDates()
    {
        document.querySelectorAll("[data-relative-datetime]").forEach(function (node)
        {
            const formatted = formatRelativeLeaveAge(node.dataset.relativeDatetime);
            const count = Number.parseInt(node.dataset.relativeCount || "0", 10);
            const fallbackDate = formatPopupDateLabel(node.dataset.relativeDatetime, node.textContent || "");

            node.textContent = count > 0 ? `${formatted || fallbackDate} (${count})` : (formatted || fallbackDate);
        });
    }

    function animateDayCounters()
    {
        document.querySelectorAll(".days-block").forEach(function (block)
        {
            const counter = block.querySelector(".days-counter");
            const label = block.querySelector(".days-label");
            const target = Number.parseFloat(block.dataset.target || "0");
            const finalDisplay = block.dataset.display || "0";
            const duration = 700;
            const startTime = performance.now();

            if (!counter)
            {
                return;
            }

            if (!Number.isFinite(target) || target < 0)
            {
                counter.textContent = finalDisplay;
                return;
            }

            if (!Number.isInteger(target))
            {
                counter.textContent = String(target).replace(/\.0+$/, "");
                return;
            }

            if (label && target === 1)
            {
                label.textContent = "day";
            }

            function step(now)
            {
                const progress = Math.min((now - startTime) / duration, 1);
                counter.textContent = progress < 1 ? String(Math.round(target * progress)) : finalDisplay;

                if (progress < 1)
                {
                    requestAnimationFrame(step);
                }
            }

            requestAnimationFrame(step);
        });
    }

    function refreshDashboardQueueSectionState()
    {
        updateRelativeAppliedTime();
        hydrateRelativeUpdatedDates();
        animateDayCounters();
        updateReasonButtons();
        document.dispatchEvent(new CustomEvent("countup:refresh", {
            detail: { root: document.querySelector(".request-table-card") || document }
        }));
        document.dispatchEvent(new CustomEvent("countup:refresh", {
            detail: { root: document.querySelector(".hero-highlights") || document }
        }));
    }

    function refreshDashboardLiveSections()
    {
        const heroHighlights = document.querySelector(".hero-highlights");
        const queueCard = document.querySelector(".request-table-card");

        if (!heroHighlights || !queueCard)
        {
            return;
        }

        if (dashboardLiveRefreshRequest && typeof dashboardLiveRefreshRequest.abort === "function")
        {
            dashboardLiveRefreshRequest.abort();
        }

        const controller = new AbortController();
        dashboardLiveRefreshRequest = controller;

        heroHighlights.classList.add("is-loading");
        queueCard.classList.add("is-loading");

        fetch(window.location.href, {
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            },
            signal: controller.signal
        })
            .then(function (response)
            {
                if (!response.ok)
                {
                    throw new Error("Unable to refresh dashboard.");
                }

                return response.text();
            })
            .then(function (html)
            {
                const parser = new DOMParser();
                const nextDocument = parser.parseFromString(html, "text/html");
                const nextHeroHighlights = nextDocument.querySelector(".hero-highlights");
                const nextQueueCard = nextDocument.querySelector(".request-table-card");

                if (!nextHeroHighlights || !nextQueueCard)
                {
                    throw new Error("Dashboard sections not found.");
                }

                window.setSafeHTML(heroHighlights, nextHeroHighlights.innerHTML);
                window.setSafeHTML(queueCard, nextQueueCard.innerHTML);
                refreshDashboardQueueSectionState();
            })
            .catch(function (error)
            {
                if (error.name !== "AbortError")
                {
                    window.location.reload();
                }
            })
            .finally(function ()
            {
                if (dashboardLiveRefreshRequest === controller)
                {
                    dashboardLiveRefreshRequest = null;
                }

                heroHighlights.classList.remove("is-loading");
                queueCard.classList.remove("is-loading");
            });
    }

    function buildDashboardNotificationSignature(notifications)
    {
        if (!Array.isArray(notifications))
        {
            return "";
        }

        return notifications.map(function (item)
        {
            return [
                String(item.id || ""),
                String(item.leave_type || ""),
                String(item.schedule_text || ""),
                String(item.activity_text || ""),
                String(item.updated_text || ""),
                String(item.status_class || ""),
                String(item.display_name || ""),
                String(item.headline_text || "")
            ].join("|");
        }).join("||");
    }

    function loadDashboardQueuePage(pageNumber)
    {
        const queueCard = document.querySelector(".request-table-card");

        if (!queueCard || !pageNumber)
        {
            return;
        }

        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.set("queue_page", pageNumber);
        const currentPage = Number.parseInt(new URL(window.location.href).searchParams.get("queue_page") || "1", 10);
        const nextPage = Number.parseInt(pageNumber, 10);
        const pagingDirectionClass = nextPage > currentPage ? "is-paging-forward" : "is-paging-backward";

        if (dashboardQueueRequest && typeof dashboardQueueRequest.abort === "function")
        {
            dashboardQueueRequest.abort();
        }

        const controller = new AbortController();
        dashboardQueueRequest = controller;

        queueCard.classList.remove("is-paging-forward", "is-paging-backward");
        queueCard.classList.add(pagingDirectionClass);
        queueCard.classList.add("is-loading");

        fetch(nextUrl.toString(), {
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            },
            signal: controller.signal
        })
            .then(function (response)
            {
                if (!response.ok)
                {
                    throw new Error("Unable to load queue page.");
                }

                return response.text();
            })
            .then(function (html)
            {
                const parser = new DOMParser();
                const nextDocument = parser.parseFromString(html, "text/html");
                const nextQueueCard = nextDocument.querySelector(".request-table-card");

                if (!nextQueueCard)
                {
                    throw new Error("Queue section not found.");
                }

                window.setSafeHTML(queueCard, nextQueueCard.innerHTML);
                window.history.replaceState({}, "", nextUrl.toString());
                refreshDashboardQueueSectionState();
            })
            .catch(function (error)
            {
                if (error.name !== "AbortError")
                {
                    window.location.href = nextUrl.toString();
                }
            })
            .finally(function ()
            {
                if (dashboardQueueRequest === controller)
                {
                    dashboardQueueRequest = null;
                }

                queueCard.classList.remove("is-loading");
                setTimeout(function ()
                {
                    queueCard.classList.remove("is-paging-forward", "is-paging-backward");
                }, 220);
            });
    }

    renderHeroQuote(currentHeroQuote);
    setInterval(rotateHeroQuote, 60000);
    updateRelativeAppliedTime();
    hydrateRelativeUpdatedDates();
    animateDayCounters();
    setInterval(updateRelativeAppliedTime, 60000);
    setInterval(hydrateRelativeUpdatedDates, 60000);

    function updateReasonButtons()
    {
        document.querySelectorAll(".reason-text").forEach(function (reasonText)
        {
            const fullText = reasonText.dataset.full || reasonText.textContent.trim();
            reasonText.textContent = fullText;

            if (reasonText.scrollHeight <= reasonText.clientHeight + 2)
            {
                reasonText.classList.remove("is-truncated");
                return;
            }

            let trimmedText = fullText;

            while (trimmedText.length > 0)
            {
                reasonText.textContent = trimmedText + "...more";

                if (reasonText.scrollHeight <= reasonText.clientHeight + 2)
                {
                    reasonText.classList.add("is-truncated");
                    const moreLabel = document.createElement("span");
                    moreLabel.className = "reason-inline-more";
                    moreLabel.textContent = "...more";
                    reasonText.replaceChildren(document.createTextNode(trimmedText), moreLabel);
                    return;
                }

                trimmedText = trimmedText.slice(0, -1).trimEnd();
            }
        });
    }

    function openReasonModal(reasonText)
    {
        const modal = document.getElementById("reasonModal");
        const title = document.getElementById("reasonModalTitle");
        const content = document.getElementById("reasonModalContent");
        const employee = document.getElementById("reasonModalEmployee");
        const leaveType = document.getElementById("reasonModalLeaveType");
        const appliedLabel = document.getElementById("reasonModalAppliedLabel");
        const updatedLabel = document.getElementById("reasonModalUpdatedLabel");
        const scheduleDate = document.getElementById("reasonModalScheduleDate");
        const scheduleTime = document.getElementById("reasonModalScheduleTime");
        const days = document.getElementById("reasonModalDays");
        const applied = document.getElementById("reasonModalApplied");
        const appliedTime = document.getElementById("reasonModalAppliedTime");
        const updated = document.getElementById("reasonModalUpdated");
        const updatedTime = document.getElementById("reasonModalUpdatedTime");

        if (reasonModalCloseTimer)
        {
            clearTimeout(reasonModalCloseTimer);
            reasonModalCloseTimer = null;
        }

        activeReasonAnchor = reasonText.closest(".reason-box") || reasonText;
        const anchorRect = activeReasonAnchor.getBoundingClientRect();
        const anchorCenterX = anchorRect.left + (anchorRect.width / 2);
        const anchorCenterY = anchorRect.top + (anchorRect.height / 2);
        const viewportCenterX = window.innerWidth / 2;
        const viewportCenterY = window.innerHeight / 2;

        modal.style.setProperty("--reason-origin-x", (anchorCenterX - viewportCenterX) + "px");
        modal.style.setProperty("--reason-origin-y", (anchorCenterY - viewportCenterY) + "px");

        const dayParts = String(reasonText.dataset.days || "").split("|");
        let dayText = "-";
        const appliedIso = reasonText.dataset.appliedIso || "";
        const updatedIso = reasonText.dataset.updatedIso || "";
        const updatedCount = Number.parseInt(reasonText.dataset.updatedCount || "0", 10) || 0;
        const useMobileReasonLabels = window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
        const scheduleDateText = (reasonText.dataset.scheduleDate || "-").replace(/\s*->\s*/g, " \u27F6 ");
        const scheduleTimeText = (reasonText.dataset.scheduleTime || "-").replace(/\s*->\s*/g, " \u27F6 ");
        const leaveTypeClass = reasonText.dataset.leaveTypeClass || "default";
        const showScheduleTime = leaveTypeClass === "short" || leaveTypeClass === "half";

        if (dayParts.length === 2)
        {
            const fromDate = new Date(dayParts[0]);
            const toDate = new Date(dayParts[1]);

            if (!Number.isNaN(fromDate.getTime()) && !Number.isNaN(toDate.getTime()))
            {
                const totalDays = Math.max(1, Math.round((toDate - fromDate) / 86400000) + 1);
                dayText = totalDays + (totalDays === 1 ? " day" : " days");
            }
        }

        title.textContent = "Reason detail";
        modal.classList.remove("reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half", "reason-theme-default");
        modal.classList.add("reason-theme-" + leaveTypeClass);
        employee.textContent = reasonText.dataset.employee || "Employee";
        leaveType.textContent = (reasonText.dataset.leaveType || "Leave type") + " Leave";
        leaveType.className = "reason-modal-chip reason-modal-type-chip reason-modal-type-" + leaveTypeClass;
        scheduleDate.textContent = scheduleDateText;
        scheduleTime.textContent = showScheduleTime ? scheduleTimeText : "";
        scheduleTime.hidden = !showScheduleTime;
        scheduleTime.classList.toggle("reason-modal-schedule-time-accent", showScheduleTime);
        days.textContent = dayText;
        window.setSafeHTML(appliedLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">🕒</span><span>${useMobileReasonLabels ? "Applied At" : "Applied"}</span></span>`);
        const relativeApplied = formatRelativeLeaveAge(appliedIso);
        const relativeUpdated = formatRelativeLeaveAge(updatedIso);
        applied.textContent = relativeApplied || (reasonText.dataset.applied || "-");
        appliedTime.textContent = formatPopupClockTime(appliedIso, reasonText.dataset.applied || "");
        window.setSafeHTML(updatedLabel, `<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">🔄</span><span>${useMobileReasonLabels ? "Updated At" : (updatedCount === 1 ? "1 update" : `${updatedCount} updates`)}</span></span>`);
        updated.textContent = updatedIso ? (relativeUpdated || (reasonText.dataset.updated || "-")) : "Not updated";
        updatedTime.textContent = updatedIso ? formatPopupClockTime(updatedIso, reasonText.dataset.updated || "") : "-";
        content.textContent = reasonText.dataset.full;
        modal.classList.remove("is-closing");
        modal.style.display = "flex";
        requestAnimationFrame(() => modal.classList.add("is-open"));
        modal.setAttribute("aria-hidden", "false");
    }

    function closeReasonModal()
    {
        const modal = document.getElementById("reasonModal");
        const content = document.getElementById("reasonModalContent");
        const employee = document.getElementById("reasonModalEmployee");
        const leaveType = document.getElementById("reasonModalLeaveType");
        const appliedLabel = document.getElementById("reasonModalAppliedLabel");
        const updatedLabel = document.getElementById("reasonModalUpdatedLabel");
        const scheduleDate = document.getElementById("reasonModalScheduleDate");
        const scheduleTime = document.getElementById("reasonModalScheduleTime");
        const days = document.getElementById("reasonModalDays");
        const applied = document.getElementById("reasonModalApplied");
        const appliedTime = document.getElementById("reasonModalAppliedTime");
        const updated = document.getElementById("reasonModalUpdated");
        const updatedTime = document.getElementById("reasonModalUpdatedTime");

        if (modal.style.display === "none")
        {
            return;
        }

        if (document.activeElement && modal.contains(document.activeElement) && typeof document.activeElement.blur === "function")
        {
            document.activeElement.blur();
        }

        modal.classList.remove("is-open");
        modal.classList.add("is-closing");
        modal.setAttribute("aria-hidden", "true");
        reasonModalCloseTimer = setTimeout(function ()
        {
            modal.style.display = "none";
            modal.classList.remove("is-closing");
            modal.classList.remove("reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half");
            modal.classList.add("reason-theme-default");
            content.textContent = "";
            employee.textContent = "Employee";
            leaveType.textContent = "Leave type";
            leaveType.className = "reason-modal-chip reason-modal-type-chip reason-modal-type-default";
            window.setSafeHTML(appliedLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">🕒</span><span>Applied</span></span>');
            window.setSafeHTML(updatedLabel, '<span class="reason-meta-label-content"><span class="reason-meta-label-icon" aria-hidden="true">🔄</span><span>0 updates</span></span>');
            scheduleDate.textContent = "-";
            scheduleTime.textContent = "-";
            scheduleTime.hidden = false;
            scheduleTime.classList.remove("reason-modal-schedule-time-accent");
            days.textContent = "-";
            applied.textContent = "-";
            appliedTime.textContent = "-";
            updated.textContent = "-";
            updatedTime.textContent = "-";
            activeReasonAnchor = null;
            reasonModalCloseTimer = null;
        }, dashboardModalAnimationMs);
    }

    function getDashboardLeaveThemeClass(leaveType)
    {
        const normalized = String(leaveType || "").trim().toLowerCase();

        if (normalized === "sick")
        {
            return "sick";
        }

        if (normalized === "earned")
        {
            return "earned";
        }

        if (normalized === "unpaid")
        {
            return "unpaid";
        }

        if (normalized === "short")
        {
            return "short";
        }

        if (normalized === "half")
        {
            return "half";
        }

        return "default";
    }

    function setMetaLineValue(node, text)
    {
        if (!node)
        {
            return;
        }

        const valueNode = node.querySelector("span:last-child");

        if (valueNode)
        {
            valueNode.textContent = text || "-";
            return;
        }

        node.textContent = text || "-";
    }

    function getLeaveUpdateCount(leave)
    {
        const count = Number.parseInt(leave && leave.updatedCount != null ? leave.updatedCount : 0, 10);
        return Number.isFinite(count) && count > 0 ? count : 0;
    }

    function formatUpdatedAtHeading(leave)
    {
        const count = getLeaveUpdateCount(leave);
        return count > 0 ? `Updated At (${count})` : "Updated At";
    }

    function setDecisionConfirmTypeIcon(icon, leaveType)
    {
        if (!icon)
        {
            return;
        }

        const resolvedType = getDashboardLeaveThemeClass(leaveType);
        const iconMap = {
            sick: "✚",
            earned: "✦",
            unpaid: "○",
            short: "◴",
            half: "◐",
            default: "◆"
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
        const typeClass = getDashboardLeaveThemeClass(leave && leave.leaveType);
        const typeSymbolMap = {
            sick: "✚",
            earned: "✦",
            unpaid: "○",
            short: "◴",
            half: "◐",
            default: "📖"
        };

        if (typeIcon)
        {
            typeIcon.textContent = typeSymbolMap[typeClass] || typeSymbolMap.default;
        }

        typeChip.dataset.leaveTypeClass = typeClass;
        setMetaLineValue(typeChip, leave && leave.leaveType ? leave.leaveType : "Leave");
    }

    function getDashboardLeaveDetails(leaveId)
    {
        const leaveRow = document.querySelector(`[data-leave-row][data-leave-id="${leaveId}"]`);
        const reasonText = leaveRow ? leaveRow.querySelector(".reason-text") : null;

        if (!leaveRow || !reasonText)
        {
            return null;
        }

        const daysBlock = leaveRow.querySelector(".days-block");

        return {
            id: String(leaveId),
            employee: reasonText.dataset.employee || "-",
            leaveType: reasonText.dataset.leaveType || "Leave",
            typeClass: reasonText.dataset.leaveTypeClass || "default",
            scheduleDate: reasonText.dataset.scheduleDate || "-",
            scheduleTime: reasonText.dataset.scheduleTime || "-",
            daysText: daysBlock && daysBlock.dataset.display
                ? `${daysBlock.dataset.display} ${daysBlock.querySelector(".days-label") ? daysBlock.querySelector(".days-label").textContent.trim() : ""}`.trim()
                : "-",
            applied: reasonText.dataset.applied || "-",
            appliedIso: reasonText.dataset.appliedIso || "",
            updated: reasonText.dataset.updated || "-",
            updatedIso: reasonText.dataset.updatedIso || "",
            updatedCount: Number.parseInt(reasonText.dataset.updatedCount || "0", 10) || 0,
            reason: reasonText.dataset.full || reasonText.textContent.trim() || ""
        };
    }

    function resetRejectSectionCards()
    {
        const grid = document.getElementById("rejectReasonSectionGrid");
        const button = document.getElementById("rejectReasonToggleAll");

        if (grid)
        {
            grid.classList.add("is-hidden");
        }

        if (button)
        {
            button.innerHTML = '<span class="reject-review-toggle-btn-icon" aria-hidden="true">&#9662;</span><span class="reject-review-toggle-btn-text">Show Notes</span>';
            button.setAttribute("aria-label", "Show notes");
            button.setAttribute("aria-expanded", "false");
        }
    }

    function populateRejectModal(leave)
    {
        const modal = document.getElementById("rejectModal");
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
        const typeClass = getDashboardLeaveThemeClass(leave && leave.typeClass);

        if (!modal)
        {
            return;
        }

        modal.classList.remove("reason-theme-sick", "reason-theme-unpaid", "reason-theme-earned", "reason-theme-short", "reason-theme-half", "reason-theme-default");
        modal.classList.add("reason-theme-" + typeClass);

        setRejectTypeChip(typeChip, leave);
        setMetaLineValue(scheduleDate, leave && leave.scheduleDate ? leave.scheduleDate.replace(/\s*->\s*/g, " ⟶ ") : "-");
        setMetaLineValue(scheduleTime, leave && leave.scheduleTime ? leave.scheduleTime.replace(/\s*->\s*/g, " ⟶ ") : "-");
        setMetaLineValue(days, leave && leave.daysText ? leave.daysText : "-");
        setMetaLineValue(applied, formatPopupDateLabel(leave && leave.appliedIso, leave && leave.applied));
        setMetaLineValue(appliedTime, formatPopupClockTime(leave && leave.appliedIso, leave && leave.applied));

        if (updatedHeading)
        {
            updatedHeading.textContent = formatUpdatedAtHeading(leave);
        }

        if (leave && leave.updatedIso)
        {
            setMetaLineValue(updated, formatPopupDateLabel(leave.updatedIso, leave.updated));
            setMetaLineValue(updatedTime, formatPopupClockTime(leave.updatedIso, leave.updated));
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
        const typeClass = getDashboardLeaveThemeClass(leave && leave.typeClass);

        if (!modal || !submit || !cancel)
        {
            return Promise.resolve(false);
        }

        modal.dataset.variant = variant;
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

        setMetaLineValue(employee, leave && leave.employee ? leave.employee : "Employee");
        setMetaLineValue(type, leave && leave.leaveType ? leave.leaveType : "Leave");
        setDecisionConfirmTypeIcon(typeIcon, leave && leave.typeClass);
        setMetaLineValue(scheduleDate, leave && leave.scheduleDate ? leave.scheduleDate.replace(/\s*->\s*/g, " ⟶ ") : "-");
        setMetaLineValue(scheduleTime, leave && leave.scheduleTime ? leave.scheduleTime.replace(/\s*->\s*/g, " ⟶ ") : "-");
        setMetaLineValue(days, leave && leave.daysText ? leave.daysText : "-");
        setMetaLineValue(applied, formatPopupDateLabel(leave && leave.appliedIso, leave && leave.applied));
        setMetaLineValue(appliedTime, formatPopupClockTime(leave && leave.appliedIso, leave && leave.applied));
        if (updatedHeading)
        {
            updatedHeading.textContent = formatUpdatedAtHeading(leave);
        }
        setMetaLineValue(updated, leave && leave.updatedIso ? formatPopupDateLabel(leave.updatedIso, leave.updated) : "Not updated");
        setMetaLineValue(updatedTime, leave && leave.updatedIso ? formatPopupClockTime(leave.updatedIso, leave.updated) : "-");

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

        modal.classList.remove("is-closing");
        modal.style.display = "flex";
        requestAnimationFrame(function ()
        {
            modal.classList.add("is-open");
        });
        modal.setAttribute("aria-hidden", "false");

        return new Promise(function (resolve)
        {
            decisionConfirmState = { resolve: resolve };
        });
    }

    function closeDecisionConfirm(confirmed)
    {
        const modal = document.getElementById("decisionConfirmModal");
        const state = decisionConfirmState;

        if (!modal || (modal.style.display === "none" && !state))
        {
            return;
        }

        decisionConfirmState = null;
        modal.classList.remove("is-open");
        modal.classList.add("is-closing");
        modal.setAttribute("aria-hidden", "true");

        window.setTimeout(function ()
        {
            modal.style.display = "none";
            modal.classList.remove("is-closing");

            if (state && typeof state.resolve === "function")
            {
                state.resolve(!!confirmed);
            }
        }, dashboardModalAnimationMs);
    }

    function openReject(leaveId)
    {
        const modal = document.getElementById("rejectModal");
        const form = document.getElementById("rejectForm");
        const textarea = document.getElementById("rejectionReason");
        const leave = getDashboardLeaveDetails(leaveId);

        if (!leave)
        {
            window.alert("Unable to load this leave request.");
            return;
        }

        if (rejectModalCloseTimer)
        {
            clearTimeout(rejectModalCloseTimer);
            rejectModalCloseTimer = null;
        }

        currentRejectLeaveId = String(leaveId);
        currentRejectLeaveSnapshot = leave;
        form.action = "/reject-leave/" + leaveId + "/";
        form.dataset.leaveId = String(leaveId);
        populateRejectModal(leave);
        resetRejectSectionCards();
        modal.classList.remove("is-closing");
        modal.style.display = "flex";
        requestAnimationFrame(function ()
        {
            modal.classList.add("is-open");
        });
        modal.setAttribute("aria-hidden", "false");
        syncRejectionReasonCount();

        textarea.focus();
    }

    function closeReject()
    {
        const modal = document.getElementById("rejectModal");
        const textarea = document.getElementById("rejectionReason");
        const form = document.getElementById("rejectForm");

        if (modal.style.display === "none")
        {
            return;
        }

        modal.classList.remove("is-open");
        modal.classList.add("is-closing");
        modal.setAttribute("aria-hidden", "true");
        rejectModalCloseTimer = setTimeout(function ()
        {
            modal.style.display = "none";
            modal.classList.remove("is-closing");
            textarea.value = "";
            if (form)
            {
                form.removeAttribute("data-leave-id");
            }
            currentRejectLeaveId = null;
            currentRejectLeaveSnapshot = null;
            syncRejectionReasonCount();
            rejectModalCloseTimer = null;
        }, dashboardModalAnimationMs);
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

    function renderActionError(message)
    {
        renderFlashMessages([{
            tags: "error",
            title: "Action needed",
            text: message || "Unable to update this leave request right now."
        }]);
    }

    function setLeaveActionBusyState(leaveId, isBusy)
    {
        if (!leaveId)
        {
            return;
        }

        const leaveRow = document.querySelector(`[data-leave-row][data-leave-id="${leaveId}"]`);

        if (leaveRow)
        {
            leaveRow.classList.toggle("is-loading", Boolean(isBusy));
        }

        document.querySelectorAll(`[data-leave-action-form][data-leave-id="${leaveId}"] button[type="submit"], [data-leave-row][data-leave-id="${leaveId}"] .reject-btn`).forEach(function (button)
        {
            button.disabled = Boolean(isBusy);
        });
    }

    function submitLeaveActionForm(form)
    {
        if (!form || form.dataset.submitting === "true")
        {
            return;
        }

        const leaveId = form.dataset.leaveId || "";
        const formData = new FormData(form);

        form.dataset.submitting = "true";
        setLeaveActionBusyState(leaveId, true);

        fetch(form.action, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json"
            },
            body: formData
        })
            .then(function (response)
            {
                return response.json().catch(function ()
                {
                    return {};
                }).then(function (payload)
                {
                    if (!response.ok)
                    {
                        throw new Error(payload.detail || "Unable to update this leave request right now.");
                    }

                    return payload;
                });
            })
            .then(function (payload)
            {
                renderFlashMessages(payload.messages);
                closeReject();
                refreshDashboardLiveSections();
                window.dispatchEvent(new CustomEvent("hr-notifications:refresh", {
                    detail: {
                        leaveId: leaveId
                    }
                }));
            })
            .catch(function (error)
            {
                renderActionError(error.message || "Unable to update this leave request right now.");
            })
            .finally(function ()
            {
                delete form.dataset.submitting;
                setLeaveActionBusyState(leaveId, false);
            });
    }

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

            const shouldHide = !rejectReasonSectionGrid.classList.contains("is-hidden");
            rejectReasonSectionGrid.classList.toggle("is-hidden", shouldHide);
            rejectReasonToggleAllButton.innerHTML = shouldHide
                ? '<span class="reject-review-toggle-btn-icon" aria-hidden="true">&#9662;</span><span class="reject-review-toggle-btn-text">Show Notes</span>'
                : '<span class="reject-review-toggle-btn-icon" aria-hidden="true">&#9652;</span><span class="reject-review-toggle-btn-text">Hide Notes</span>';
            rejectReasonToggleAllButton.setAttribute("aria-label", shouldHide ? "Show notes" : "Hide notes");
            rejectReasonToggleAllButton.setAttribute("aria-expanded", shouldHide ? "false" : "true");
        });
    }

    if (rejectForm)
    {
        rejectForm.addEventListener("submit", function (event)
        {
            event.preventDefault();

            const rejectionReason = rejectionReasonTextarea ? rejectionReasonTextarea.value.trim() : "";

            if (!currentRejectLeaveId)
            {
                window.alert("No leave request selected for rejection.");
                return;
            }

            if (!rejectionReason)
            {
                if (rejectionReasonTextarea)
                {
                    rejectionReasonTextarea.focus();
                }
                return;
            }

            openDecisionConfirm({
                variant: "reject",
                leave: currentRejectLeaveSnapshot || getDashboardLeaveDetails(currentRejectLeaveId),
                note: rejectionReason
            }).then(function (confirmed)
            {
                if (!confirmed)
                {
                    if (rejectionReasonTextarea)
                    {
                        rejectionReasonTextarea.focus();
                    }
                    return;
                }

                submitLeaveActionForm(rejectForm);
            });
        });
    }

    document.addEventListener("keydown", function (event)
    {
        if (event.key === "Escape")
        {
            closeReasonModal();
            closeReject();
            closeDecisionConfirm(false);
        }
    });

    document.addEventListener("click", function (event)
    {
        const notificationToggle = document.getElementById("notification-toggle");
        const notificationDropdown = document.querySelector(".notification-dropdown");
        const queuePageLink = event.target.closest(".dashboard-page-btn[data-queue-page]");

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

        if (queuePageLink)
        {
            event.preventDefault();
            loadDashboardQueuePage(queuePageLink.dataset.queuePage);
            return;
        }

        const reasonText = event.target.closest(".reason-text.is-truncated");
        const reasonBox = event.target.closest(".reason-box");
        const truncatedReason = reasonBox ? reasonBox.querySelector(".reason-text.is-truncated") : null;

        if (!reasonText && !truncatedReason)
        {
            return;
        }

        openReasonModal(reasonText || truncatedReason);
    });

    document.addEventListener("submit", function (event)
    {
        const leaveActionForm = event.target.closest("[data-leave-action-form]");

        if (!leaveActionForm)
        {
            return;
        }

        event.preventDefault();

        if (leaveActionForm.id === "rejectForm")
        {
            return;
        }

        if (!leaveActionForm.dataset.leaveId)
        {
            const leaveIdMatch = String(leaveActionForm.action || "").match(/\/(\d+)\/?$/);

            if (leaveIdMatch)
            {
                leaveActionForm.dataset.leaveId = leaveIdMatch[1];
            }
        }

        const leaveId = leaveActionForm.dataset.leaveId || "";
        const leave = getDashboardLeaveDetails(leaveId);

        openDecisionConfirm({
            variant: "approve",
            leave: leave
        }).then(function (confirmed)
        {
            if (!confirmed)
            {
                return;
            }

            submitLeaveActionForm(leaveActionForm);
        });
    });

    window.addEventListener("hr-notification-state-sync", function (event)
    {
        const notifications = event && event.detail && Array.isArray(event.detail.notifications)
            ? event.detail.notifications
            : null;

        if (!notifications)
        {
            return;
        }

        const nextSignature = buildDashboardNotificationSignature(notifications);

        if (dashboardKnownNotificationSignature === null)
        {
            dashboardKnownNotificationSignature = nextSignature;
            return;
        }

        if (nextSignature === dashboardKnownNotificationSignature)
        {
            return;
        }

        dashboardKnownNotificationSignature = nextSignature;
        refreshDashboardLiveSections();
    });

    window.addEventListener("load", updateReasonButtons);
    window.addEventListener("resize", updateReasonButtons);
