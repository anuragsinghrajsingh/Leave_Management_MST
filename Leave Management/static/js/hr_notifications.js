(function () {
    const POLL_INTERVAL = 60000;
    const NOTIFICATION_PAGE_SIZE = 50;
    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function getCsrfToken() {
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        return metaToken ? String(metaToken.getAttribute("content") || "").trim() : "";
    }

    function playNotificationTone() {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;

        if (!AudioCtx) {
            return;
        }

        try {
            const audioContext = new AudioCtx();
            const oscillator = audioContext.createOscillator();
            const gain = audioContext.createGain();

            oscillator.type = "sine";
            oscillator.frequency.setValueAtTime(880, audioContext.currentTime);
            gain.gain.setValueAtTime(0.0001, audioContext.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.05, audioContext.currentTime + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, audioContext.currentTime + 0.18);

            oscillator.connect(gain);
            gain.connect(audioContext.destination);
            oscillator.start();
            oscillator.stop(audioContext.currentTime + 0.18);

            oscillator.onended = function () {
                audioContext.close().catch(function () {});
            };
        } catch (error) {
            // Ignore audio failures silently.
        }
    }

    function flashNotificationScreen(statusClass) {
        if (statusClass !== "approved" && statusClass !== "rejected") {
            return;
        }

        const flash = document.createElement("div");
        flash.className = "notification-screen-flash notification-screen-flash-" + statusClass;
        document.body.appendChild(flash);

        requestAnimationFrame(function () {
            flash.classList.add("is-visible");
        });

        window.setTimeout(function () {
            flash.classList.remove("is-visible");
            window.setTimeout(function () {
                if (flash.parentNode) {
                    flash.parentNode.removeChild(flash);
                }
            }, 520);
        }, 260);
    }

    function initNotificationDropdown(dropdown) {
        dropdown.classList.remove("is-hydrated");
        const apiUrl = dropdown.dataset.notificationApi;
        const fallbackAvatar = dropdown.dataset.fallbackAvatar || "";
        const emptyText = dropdown.dataset.notificationEmpty || "No pending requests right now.";
        const userKey = dropdown.dataset.notificationUserKey || apiUrl || "anonymous";
        const trigger = dropdown.querySelector(".notification-trigger");
        const panel = dropdown.querySelector(".notification-panel");
        const list = dropdown.querySelector("[data-notification-list]");
        const totalBadge = dropdown.querySelector(".notification-count");
        const totalMeta = dropdown.querySelector("[data-notification-total]");
        const newBadge = dropdown.querySelector("[data-notification-new-badge]");
        const newPill = dropdown.querySelector("[data-notification-new-pill]");
        const markReadButton = dropdown.querySelector("[data-notification-mark-read]");

        if (!apiUrl || !trigger || !panel || !list || !totalBadge || !totalMeta || !newBadge || !newPill) {
            return;
        }

        const readApiUrl = "/api/notifications/read/";
        const seenApiUrl = "/api/notifications/seen/";
        const employeeHighlightStorageKey = "employeeNotificationHighlight";
        const hrHighlightStorageKey = "hrNotificationHighlight";

        let knownIds = Array.from(list.querySelectorAll("[data-notification-id]")).map(function (item) {
            return String(item.dataset.notificationId);
        });
        let serverReadIds = new Set(Array.from(list.querySelectorAll('[data-notification-id][data-notification-read="true"]')).map(function (item) {
            return String(item.dataset.notificationId);
        }));
        let readIds = new Set(Array.from(serverReadIds));
        let highlightedIds = new Set(Array.from(list.querySelectorAll('[data-notification-id][data-notification-new="true"]')).map(function (item) {
            return String(item.dataset.notificationId);
        }));
        let latestNotifications = [];
        let latestLeaveCounts = null;
        let hasFetchedOnce = false;
        let firstFetchEmptyGuardUsed = false;
        let dropdownInitAt = Date.now();
        let acceptedAnyNonEmptyPayload = false;
        let consecutiveSuspiciousEmptyPayloads = 0;
        let fetchSequence = 0;
        let latestHandledFetchId = 0;
        let nextNotificationOffset = knownIds.length;
        let hasMoreNotifications = true;
        let isLoadingMoreNotifications = false;

        function getNotificationSignature(item) {
            return [
                String(item.id || ""),
                String(item.display_name || ""),
                String(item.leave_type || ""),
                String(item.from_date || ""),
                String(item.to_date || ""),
                String(item.from_time || ""),
                String(item.to_time || ""),
                String(item.created_at || ""),
                String(item.status || ""),
                String(item.status_class || ""),
            ].join("|");
        }

        function buildNotificationAvatar(item) {
            if (item.photo_url) {
                return '<img src="' + escapeHtml(item.photo_url) + '" alt="' + escapeHtml(item.display_name) + '" class="notification-avatar">';
            }

            return (
                '<span class="notification-avatar notification-avatar-fallback" aria-label="' + escapeHtml(item.display_name) + '"' +
                    ' data-avatar-fallback data-full-name="' + escapeHtml(item.display_name) + '"' +
                    ' data-username="' + escapeHtml(item.username || item.display_name || "EM") + '">' +
                    escapeHtml(((item.display_name || item.username || "EM").trim().split(/\s+/).filter(Boolean).slice(0, 2).map(function (part) { return part.charAt(0); }).join("") || (item.username || "EM").slice(0, 2)).toUpperCase()) +
                '</span>'
            );
        }

        function updateTotal(count) {
            const safeCount = Number.isFinite(Number(count)) ? Number(count) : 0;
            totalBadge.dataset.countupTarget = String(safeCount);
            totalMeta.dataset.countupTarget = String(safeCount);
            totalBadge.textContent = String(safeCount);
            totalMeta.textContent = String(safeCount);

            if (typeof window.animateCountUp === "function") {
                window.animateCountUp(totalBadge, safeCount, { duration: 260 });
                window.animateCountUp(totalMeta, safeCount, { duration: 260 });
            }

            if (safeCount > 0) {
                totalBadge.classList.remove("hidden");
            } else {
                totalBadge.classList.add("hidden");
            }

            document.dispatchEvent(new CustomEvent("countup:refresh", {
                detail: {
                    root: dropdown,
                    duration: 180
                }
            }));
        }

        function updateNewIndicators() {
            const newCount = Array.from(highlightedIds).filter(function (id) {
                return knownIds.includes(id) && !readIds.has(id);
            }).length;
            const unreadCount = knownIds.filter(function (id) {
                return !readIds.has(id);
            }).length;

            if (newCount > 0) {
                newBadge.textContent = newCount;
                newPill.textContent = newCount + " new";
                newBadge.classList.remove("hidden");
                newPill.classList.remove("hidden");
            } else {
                newBadge.textContent = "";
                newPill.textContent = "";
                newBadge.classList.add("hidden");
                newPill.classList.add("hidden");
            }
            if (markReadButton) {
                markReadButton.classList.remove("hidden");
                markReadButton.disabled = unreadCount <= 0;
            }
        }

        function syncRenderedNewState() {
            list.querySelectorAll("[data-notification-id]").forEach(function (item) {
                const itemId = String(item.dataset.notificationId || "");
                item.classList.toggle("is-new", highlightedIds.has(itemId));
                item.classList.toggle("is-read", readIds.has(itemId) && !highlightedIds.has(itemId));
            });
        }

        function broadcastNotificationState() {
            window.dispatchEvent(new CustomEvent("hr-notification-state-sync", {
                detail: {
                    apiUrl: apiUrl,
                    userKey: userKey,
                    readIds: Array.from(readIds),
                    highlightedIds: Array.from(highlightedIds),
                    notifications: hasFetchedOnce ? latestNotifications.slice() : null,
                    leaveCounts: latestLeaveCounts,
                }
            }));
        }

        function removeNotificationsByIds(ids) {
            const notificationIds = Array.isArray(ids)
                ? ids.map(function (id) { return String(id || "").trim(); }).filter(Boolean)
                : [];

            if (!notificationIds.length) {
                return;
            }

            const idSet = new Set(notificationIds);
            knownIds = knownIds.filter(function (id) {
                return !idSet.has(String(id));
            });
            latestNotifications = latestNotifications.filter(function (item) {
                return !idSet.has(String(item.id || ""));
            });
            notificationIds.forEach(function (id) {
                readIds.delete(id);
                serverReadIds.delete(id);
                highlightedIds.delete(id);
            });

            list.querySelectorAll("[data-notification-id]").forEach(function (item) {
                if (idSet.has(String(item.dataset.notificationId || "")) && item.parentNode) {
                    item.parentNode.removeChild(item);
                }
            });

            updateTotal(knownIds.filter(function (id) {
                return !readIds.has(id);
            }).length);
            updateNewIndicators();

            if (!knownIds.length) {
                renderNotifications([]);
            }

            broadcastNotificationState();
        }

        function syncInitialState() {
            updateTotal(Number(totalBadge.textContent || totalMeta.textContent || 0));
            updateNewIndicators();
            syncRenderedNewState();
            broadcastNotificationState();
        }

        function postReadState(payload) {
            const csrfToken = getCsrfToken();

            return fetch(readApiUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify(payload)
            }).then(function (response) {
                if (!response.ok) {
                    throw new Error("Unable to update notification state.");
                }

                return response.json();
            }).then(function (payload) {
                serverReadIds = new Set((payload.read_ids || []).map(String));
                readIds = new Set(Array.from(serverReadIds));
                highlightedIds = new Set(Array.from(highlightedIds).filter(function (id) {
                    return !readIds.has(id);
                }));
                updateTotal(typeof payload.count === "number" ? payload.count : knownIds.filter(function (id) {
                    return !readIds.has(id);
                }).length);
                syncRenderedNewState();
                broadcastNotificationState();
                return payload;
            });
        }

        function postSeenState(ids) {
            const notificationIds = Array.isArray(ids) ? ids.map(String).filter(Boolean) : [];

            if (!notificationIds.length) {
                return Promise.resolve();
            }

            return fetch(seenApiUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({ ids: notificationIds })
            }).catch(function () {});
        }

        function renderNotifications(notifications) {
            latestNotifications = notifications.slice();

            if (!notifications.length) {
                list.innerHTML = `
                <div class="notification-empty">
                    <!-- Decorative Backdrop -->
                    <div class="notif-decorative-system">
                        <div class="notif-star notif-s-1">
                            <svg viewBox="0 0 24 24"><path d="M12 0L14.59 9.41L24 12L14.59 14.59L12 24L9.41 14.59L0 12L9.41 9.41L12 0Z" fill="currentColor"/></svg>
                        </div>
                        <div class="notif-star notif-s-2">
                            <svg viewBox="0 0 24 24"><path d="M12 0L14.59 9.41L24 12L14.59 14.59L12 24L9.41 14.59L0 12L9.41 9.41L12 0Z" fill="currentColor"/></svg>
                        </div>
                        <div class="notif-star notif-s-3">
                            <svg viewBox="0 0 24 24"><path d="M12 0L14.59 9.41L24 12L14.59 14.59L12 24L9.41 14.59L0 12L9.41 9.41L12 0Z" fill="currentColor"/></svg>
                        </div>
                        <span class="notif-d-icon dot-pink" style="top: 20%; left: 80%;"></span>
                        <span class="notif-d-icon dot-teal" style="top: 60%; left: 10%;"></span>
                        <span class="notif-d-icon dot-indigo" style="top: 85%; left: 75%;"></span>
                    </div>

                    <div class="notif-interactive-zone">
                        <div class="notif-icon-visual">
                            <div class="radiant-bell-container">
                                <div class="bell-echo echo-1"></div>
                                <div class="bell-echo echo-2"></div>
                                <div class="bell-echo echo-3"></div>
                                <div class="svg-bell-wrapper">
                                    <svg class="bell-svg" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                        <defs>
                                            <linearGradient id="bellGradientJS" x1="0%" y1="0%" x2="100%" y2="100%">
                                                <stop offset="0%" style="stop-color:#6366f1;stop-opacity:1" />
                                                <stop offset="100%" style="stop-color:#a855f7;stop-opacity:1" />
                                            </linearGradient>
                                        </defs>
                                        <path class="bell-body" d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" fill="url(#bellGradientJS)"></path>
                                        <path class="bell-clapper" d="M13.73 21a2 2 0 0 1-3.46 0" fill="#f59e0b"></path>
                                    </svg>
                                </div>
                            </div>
                        </div>

                        <div class="notif-empty-copy">
                            <h4 class="notif-empty-title">All Clear.</h4>
                            <p class="notif-empty-text">No active alerts to review.</p>
                        </div>
                    </div>
                </div>`;
                return;
            }

            list.innerHTML = notifications.map(function (item) {
                const itemId = String(item.id);
                const isNew = highlightedIds.has(itemId) ? " is-new" : "";
                const isRead = (item.is_read || readIds.has(itemId)) && !highlightedIds.has(itemId) ? " is-read" : "";
                const isHrPendingNotification = Boolean(item.employee_id) && !item.target_panel;
                const isEmployeeDecisionNotification = Boolean(item.target_panel);
                const subtitleHtml = isHrPendingNotification
                    ? '<small class="notification-subtitle">' + escapeHtml(item.schedule_text || "") + '</small>'
                    : (isEmployeeDecisionNotification ? '<small class="notification-subtitle">' + escapeHtml(item.schedule_text || "") + '</small>' : '');
                const timeText = isHrPendingNotification
                    ? escapeHtml(((item.activity_label || "Applied") + ' ' + (item.activity_text || item.created_at || "")).trim())
                    : (isEmployeeDecisionNotification
                        ? escapeHtml((item.updated_text
                            ? ('Updated ' + item.updated_text)
                            : ('Applied ' + (item.applied_text || ""))).trim())
                        : escapeHtml(item.created_at || ""));
                const nameText = isEmployeeDecisionNotification
                    ? escapeHtml(item.headline_text || item.display_name || "")
                    : escapeHtml(item.display_name || "");
                return (
                    '<a href="' + escapeHtml(item.target_url) + '" class="notification-item notification-item-' + escapeHtml(item.leave_type_class) + ' notification-item-status-' + escapeHtml(item.status_class || "default") + isNew + isRead + '" data-notification-item data-notification-id="' + escapeHtml(itemId) + '" data-notification-read="' + (item.is_read ? 'true' : 'false') + '" data-notification-new="' + (item.is_new ? 'true' : 'false') + '" data-notification-leave-id="' + escapeHtml(item.id) + '" data-notification-target-panel="' + escapeHtml(item.target_panel || "") + '" data-notification-employee-id="' + escapeHtml(item.employee_id || "") + '">' +
                        '<div class="notification-visual">' +
                            buildNotificationAvatar(item) +
                            '<span class="notification-type notification-type-compact' + (isEmployeeDecisionNotification ? (' notification-status-text notification-status-text-' + escapeHtml(item.status_class || "default")) : '') + '">' + escapeHtml(item.leave_type) + '</span>' +
                        '</div>' +
                        '<div class="notification-copy">' +
                            '<span class="notification-name">' + nameText + '</span>' +
                            subtitleHtml +
                            '<small class="notification-meta-line">' +
                        '<span class="notification-time">' + timeText + '</span>' +
                            '</small>' +
                        '</div>' +
                    '</a>'
                );
            }).join("");

            list.querySelectorAll("[data-notification-item]").forEach(function (item) {
                item.addEventListener("click", function (event) {
                    event.preventDefault();
                    const itemId = String(item.dataset.notificationId || "");
                    highlightedIds.delete(itemId);
                    readIds.add(itemId);
                    updateNewIndicators();
                    updateTotal(knownIds.filter(function (id) {
                        return !readIds.has(id);
                    }).length);
                    syncRenderedNewState();
                    broadcastNotificationState();

                    const targetPanel = item.dataset.notificationTargetPanel || "";
                    const targetLeaveId = item.dataset.notificationLeaveId || itemId;
                    const targetEmployeeId = item.dataset.notificationEmployeeId || "";

                    if (targetPanel && targetLeaveId) {
                        try {
                            window.sessionStorage.setItem(employeeHighlightStorageKey, JSON.stringify({
                                panel: targetPanel,
                                leaveId: String(targetLeaveId),
                            }));
                        } catch (error) {
                            // Ignore storage failures silently.
                        }
                    } else if (targetEmployeeId && targetLeaveId) {
                        try {
                            window.sessionStorage.setItem(hrHighlightStorageKey, JSON.stringify({
                                employeeId: String(targetEmployeeId),
                                leaveId: String(targetLeaveId),
                            }));
                        } catch (error) {
                            // Ignore storage failures silently.
                        }
                    }

                    let handledInlineOnManageAll = false;

                    if (
                        targetEmployeeId &&
                        targetLeaveId &&
                        typeof window.openManageAllLeaveFromNotification === "function"
                    ) {
                        try {
                            handledInlineOnManageAll = window.openManageAllLeaveFromNotification(
                                String(targetEmployeeId),
                                String(targetLeaveId)
                            ) === true;
                        } catch (error) {
                            handledInlineOnManageAll = false;
                        }
                    }

                    postReadState({ ids: [itemId] })
                        .catch(function () {})
                        .finally(function () {
                            if (handledInlineOnManageAll) {
                                return;
                            }
                            window.location.href = item.getAttribute("href");
                        });
                });
            });

            syncRenderedNewState();
        }

        function mergeNotificationPage(existingItems, nextItems) {
            const merged = Array.isArray(existingItems) ? existingItems.slice() : [];
            const seen = new Set(merged.map(function (item) {
                return String(item.id || "");
            }));

            (Array.isArray(nextItems) ? nextItems : []).forEach(function (item) {
                const itemId = String(item.id || "");
                if (!itemId || seen.has(itemId)) {
                    return;
                }
                seen.add(itemId);
                merged.push(item);
            });

            return merged;
        }

        function clearNewHighlights() {
            if (!highlightedIds.size) {
                return;
            }

            const idsToClear = Array.from(highlightedIds);
            highlightedIds.clear();
            updateNewIndicators();
            syncRenderedNewState();
            broadcastNotificationState();
            postSeenState(idsToClear);
        }
        dropdown.__notificationClearNew = clearNewHighlights;

        function markAllNotificationsRead() {
            if (!latestNotifications.length && !knownIds.length) {
                return;
            }

            latestNotifications.forEach(function (item) {
                readIds.add(String(item.id));
            });

            highlightedIds.clear();
            updateNewIndicators();
            syncRenderedNewState();
            updateTotal(knownIds.filter(function (id) {
                return !readIds.has(id);
            }).length);
            broadcastNotificationState();
            postReadState({ all: true }).catch(function () {});
        }

        function handlePayload(payload, fetchId, options) {
            const settings = options || {};
            const forceAcceptEmpty = settings.forceAcceptEmpty === true;
            const appendPage = settings.append === true;

            if (!appendPage && Number.isFinite(fetchId) && fetchId < latestHandledFetchId) {
                return;
            }
            if (!appendPage && Number.isFinite(fetchId)) {
                latestHandledFetchId = fetchId;
            }

            const notifications = Array.isArray(payload.notifications) ? payload.notifications : [];
            latestLeaveCounts = payload && typeof payload.leave_counts === "object" ? payload.leave_counts : latestLeaveCounts;
            hasMoreNotifications = payload && typeof payload.has_more === "boolean" ? payload.has_more : false;
            nextNotificationOffset = Number.isFinite(Number(payload && payload.next_offset))
                ? Number(payload.next_offset)
                : (appendPage ? latestNotifications.length + notifications.length : notifications.length);

            if (appendPage) {
                if (!notifications.length) {
                    return;
                }

                const mergedNotifications = mergeNotificationPage(latestNotifications, notifications);
                const mergedIds = mergedNotifications.map(function (item) {
                    return String(item.id);
                });
                const pageReadIds = new Set(notifications.filter(function (item) {
                    return item.is_read;
                }).map(function (item) {
                    return String(item.id);
                }));
                const pageNewIds = notifications.filter(function (item) {
                    return item.is_new && !item.is_read;
                }).map(function (item) {
                    return String(item.id);
                });

                serverReadIds = new Set(Array.from(serverReadIds).concat(Array.from(pageReadIds)));
                readIds = new Set(Array.from(readIds).concat(Array.from(pageReadIds)));
                pageNewIds.forEach(function (id) {
                    if (!readIds.has(id)) {
                        highlightedIds.add(id);
                    }
                });
                knownIds = mergedIds;
                updateTotal(Number(payload && payload.count));
                updateNewIndicators();
                hasFetchedOnce = true;
                renderNotifications(mergedNotifications);
                broadcastNotificationState();
                dropdown.classList.add("is-hydrated");
                return;
            }

            const payloadCount = Number(payload && payload.count);
            const hasRenderableItems =
                knownIds.length > 0 ||
                !!list.querySelector("[data-notification-id]");
            const existingBadgeCount = Number(totalBadge.dataset.countupTarget || totalBadge.textContent || 0);
            const badgeHasCount = Number.isFinite(existingBadgeCount) && existingBadgeCount > 0;
            const suspiciousEmptyPayload =
                notifications.length === 0 &&
                Number.isFinite(payloadCount) &&
                payloadCount === 0 &&
                (hasRenderableItems || badgeHasCount);

            // Guard against a transient stale/empty first response that can briefly zero-out
            // server-rendered notifications and badges before the next poll.
            if (
                !forceAcceptEmpty &&
                !hasFetchedOnce &&
                !firstFetchEmptyGuardUsed &&
                suspiciousEmptyPayload
            ) {
                firstFetchEmptyGuardUsed = true;
                window.setTimeout(fetchNotifications, 900);
                return;
            }

            // Hard guard for inconsistent empty payloads that can arrive during page init/navigation.
            if (
                !forceAcceptEmpty &&
                suspiciousEmptyPayload &&
                (
                    (Date.now() - dropdownInitAt < 70000 && !acceptedAnyNonEmptyPayload) ||
                    consecutiveSuspiciousEmptyPayloads < 1
                )
            ) {
                consecutiveSuspiciousEmptyPayloads += 1;
                window.setTimeout(fetchNotifications, 900);
                return;
            }

            if (notifications.length > 0 || (Number.isFinite(payloadCount) && payloadCount > 0)) {
                acceptedAnyNonEmptyPayload = true;
                consecutiveSuspiciousEmptyPayloads = 0;
            } else if (suspiciousEmptyPayload) {
                // Accept only after retry confirmation path.
                consecutiveSuspiciousEmptyPayloads = 0;
            }

            const ids = notifications.map(function (item) {
                return String(item.id);
            });
            serverReadIds = new Set(notifications.filter(function (item) {
                return item.is_read;
            }).map(function (item) {
                return String(item.id);
            }));
            readIds = new Set(Array.from(serverReadIds));
            highlightedIds = new Set(
                notifications.filter(function (item) {
                    return item.is_new && !item.is_read;
                }).map(function (item) {
                    return String(item.id);
                })
            );
            knownIds = ids;
            nextNotificationOffset = Number.isFinite(Number(payload && payload.next_offset))
                ? Number(payload.next_offset)
                : ids.length;
            hasMoreNotifications = payload && typeof payload.has_more === "boolean"
                ? payload.has_more
                : ids.length >= NOTIFICATION_PAGE_SIZE;
            updateTotal(ids.filter(function (id) {
                return !readIds.has(id);
            }).length);
            updateNewIndicators();
            hasFetchedOnce = true;
            renderNotifications(notifications);
            broadcastNotificationState();
            dropdown.classList.add("is-hydrated");
        }

        function buildNotificationPageUrl(offset) {
            const separator = apiUrl.includes("?") ? "&" : "?";
            return apiUrl + separator +
                "limit=" + encodeURIComponent(String(NOTIFICATION_PAGE_SIZE)) +
                "&offset=" + encodeURIComponent(String(offset)) +
                "&_ts=" + Date.now();
        }

        function fetchNotificationPage(offset, options) {
            const settings = options || {};
            const requestId = ++fetchSequence;
            const requestUrl = buildNotificationPageUrl(offset);

            return fetch(requestUrl, {
                cache: "no-store",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache"
                }
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Notification fetch failed.");
                    }

                    return response.json();
                })
                .then(function (payload) {
                    handlePayload(payload, requestId, settings);
                    return payload;
                });
        }

        function fetchNotifications(options) {
            const settings = options || {};
            const shouldShowSkeleton =
                dropdown.classList.contains("is-open") &&
                !list.querySelector("[data-notification-id]");

            if (shouldShowSkeleton && typeof window.startAsyncPopupSkeleton === "function") {
                window.startAsyncPopupSkeleton(panel);
            }

            fetchNotificationPage(0, settings)
                .catch(function () {
                    // Ignore polling failures silently.
                })
                .finally(function () {
                    dropdown.classList.add("is-hydrated");
                    if (shouldShowSkeleton && typeof window.finishAsyncPopupSkeleton === "function") {
                        window.finishAsyncPopupSkeleton(panel);
                    }
                });
        }

        function loadMoreNotifications() {
            if (!dropdown.classList.contains("is-open") || !hasMoreNotifications || isLoadingMoreNotifications) {
                return;
            }

            isLoadingMoreNotifications = true;
            fetchNotificationPage(nextNotificationOffset, { append: true, forceAcceptEmpty: true })
                .catch(function () {})
                .finally(function () {
                    isLoadingMoreNotifications = false;
                });
        }

        list.addEventListener("scroll", function () {
            const distanceFromBottom = list.scrollHeight - list.scrollTop - list.clientHeight;
            if (distanceFromBottom <= 120) {
                loadMoreNotifications();
            }
        });

        function setOpenState(isOpen) {
            dropdown.classList.toggle("is-open", isOpen);
            trigger.setAttribute("aria-expanded", isOpen ? "true" : "false");

            if (isOpen) {
                fetchNotifications();
            } else {
                clearNewHighlights();
            }
        }

        trigger.addEventListener("click", function (event) {
            event.preventDefault();
            event.stopPropagation();

            const willOpen = !dropdown.classList.contains("is-open");

            if (willOpen && typeof window.closeHeaderMenusExcept === "function") {
                window.closeHeaderMenusExcept({ keepNotification: dropdown });
            }

            document.querySelectorAll(".notification-dropdown.is-open").forEach(function (openDropdown) {
                if (openDropdown !== dropdown) {
                    openDropdown.classList.remove("is-open");
                    const openTrigger = openDropdown.querySelector(".notification-trigger");
                    if (openTrigger) {
                        openTrigger.setAttribute("aria-expanded", "false");
                    }
                }
            });

            setOpenState(willOpen);
        });

        if (markReadButton) {
            markReadButton.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                markAllNotificationsRead();
            });
        }

        window.addEventListener("hr-notification-state-sync", function (event) {
            const detail = event.detail || {};

            if (detail.apiUrl !== apiUrl || detail.userKey !== userKey) {
                return;
            }

            readIds = new Set(Array.isArray(detail.readIds) ? detail.readIds.map(String) : []);
            if (Array.isArray(detail.highlightedIds)) {
                highlightedIds = new Set(detail.highlightedIds.map(String));
            } else {
                highlightedIds = new Set(Array.from(highlightedIds).filter(function (id) {
                    return !readIds.has(id);
                }));
            }

            updateNewIndicators();
            syncRenderedNewState();
            updateTotal(knownIds.filter(function (id) {
                return !readIds.has(id);
            }).length);
        });

        window.addEventListener("hr-notifications:refresh", function (event) {
            const detail = event.detail || {};

            if (detail.apiUrl && detail.apiUrl !== apiUrl) {
                return;
            }

            removeNotificationsByIds(detail.leaveIds || (detail.leaveId ? [detail.leaveId] : []));
            fetchNotifications({ forceAcceptEmpty: true });
        });

        syncInitialState();
        fetchNotifications();
        setInterval(fetchNotifications, POLL_INTERVAL);
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".notification-dropdown[data-notification-api]").forEach(initNotificationDropdown);

        document.addEventListener("click", function (event) {
            document.querySelectorAll(".notification-dropdown.is-open").forEach(function (dropdown) {
                if (dropdown.contains(event.target)) {
                    return;
                }

                dropdown.classList.remove("is-open");
                const trigger = dropdown.querySelector(".notification-trigger");
                if (trigger) {
                    trigger.setAttribute("aria-expanded", "false");
                }
                const list = dropdown.querySelector("[data-notification-list]");
                if (list) {
                    dropdown.__notificationClearNew && dropdown.__notificationClearNew();
                }
            });
        });
    });
})();
