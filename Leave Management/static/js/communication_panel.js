(function () {
    const POLL_INTERVAL = 60000;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function getCookie(name) {
        const cookieValue = document.cookie
            .split(";")
            .map(function (part) { return part.trim(); })
            .find(function (part) { return part.startsWith(name + "="); });

        return cookieValue ? decodeURIComponent(cookieValue.split("=").slice(1).join("=")) : "";
    }

    function getCsrfToken() {
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            return String(metaToken.getAttribute("content") || "").trim();
        }

        return getCookie("csrftoken");
    }

    function readResponsePayload(response) {
        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
            return response.json();
        }

        return response.text().then(function (text) {
            const error = new Error(text || "Unexpected server response.");
            error.responseText = text;
            throw error;
        });
    }

    function buildInitials(fullName, username) {
        const source = String(fullName || "").trim();
        const parts = source ? source.split(/\s+/).filter(Boolean) : [];

        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }

        if (parts.length === 1) {
            return parts[0].slice(0, 2).toUpperCase();
        }

        return String(username || "CM").slice(0, 2).toUpperCase();
    }

    function getListEmptyText(listType, role, currentMode, fallbackText) {
        if (role === "HR") {
            return currentMode === "DIRECT" ? "No personal messages yet." : "No announcements yet.";
        }

        if (listType === "announcement") {
            return "No announcements yet.";
        }

        if (listType === "direct") {
            return "No messages with HR yet.";
        }

        return fallbackText;
    }

    function renderItems(items) {
        return items.map(function (item) {
            const avatar = item.photo_url
                ? '<img src="' + escapeHtml(item.photo_url) + '" alt="' + escapeHtml(item.sender_name) + '" class="communication-avatar">'
                : '<span class="communication-avatar communication-avatar-fallback" aria-label="' + escapeHtml(item.sender_name) + '">' +
                    escapeHtml(buildInitials(item.sender_name, item.username)) +
                  "</span>";

            return (
                '<article class="communication-item communication-item-' + escapeHtml(item.type_class || "direct") + ' communication-item-' + escapeHtml(item.direction_class || "incoming") + (item.is_new && !item.is_read ? ' is-new' : '') + (item.is_read && !item.is_outgoing ? ' is-read' : '') + '"' +
                    ' data-communication-id="' + escapeHtml(item.id) + '"' +
                    ' data-communication-type="' + escapeHtml(item.type_class || "direct") + '"' +
                    ' data-communication-read="' + (item.is_read ? "true" : "false") + '"' +
                    ' data-communication-new="' + (item.is_new ? "true" : "false") + '"' +
                    ' data-communication-outgoing="' + (item.is_outgoing ? "true" : "false") + '"' +
                    ' data-communication-title="' + escapeHtml(item.title) + '"' +
                    ' data-communication-audience="' + escapeHtml(item.audience_label) + '"' +
                    ' data-communication-time="' + escapeHtml(item.created_at) + '"' +
                    ' data-communication-body="' + escapeHtml(item.body_full || "") + '">' +
                    avatar +
                    '<div class="communication-copy">' +
                        '<div class="communication-copy-top">' +
                            '<strong class="communication-title">' + escapeHtml(item.title) + "</strong>" +
                            '<small class="communication-time">' + escapeHtml(item.created_at) + "</small>" +
                        "</div>" +
                        '<div class="communication-copy-meta">' +
                            '<p class="communication-audience">' + escapeHtml(item.audience_label) + "</p>" +
                            '<span class="communication-tag">' + escapeHtml(item.type_label) + "</span>" +
                        "</div>" +
                    "</div>" +
                "</article>"
            );
        }).join("");
    }

    function renderListContents(list, items, emptyText) {
        const actionsNode = list.querySelector(".communication-list-actions");

        Array.from(list.children).forEach(function (child) {
            if (actionsNode && child === actionsNode) {
                return;
            }

            child.remove();
        });

        if (!items.length) {
            list.insertAdjacentHTML("beforeend", '<div class="communication-empty">' + escapeHtml(emptyText) + "</div>");
            return;
        }

        list.insertAdjacentHTML("beforeend", renderItems(items));
    }

    function formatMessageBody(value) {
        return escapeHtml(value || "").replace(/\n/g, "<br>");
    }

    function openCommunicationDetailModal(item) {
        const modal = document.getElementById("modal");
        const modalContent = document.getElementById("modal-content");

        if (!modal || !modalContent) {
            return;
        }

        const title = item.dataset.communicationTitle || "Message";
        const audience = item.dataset.communicationAudience || "";
        const time = item.dataset.communicationTime || "";
        const body = item.dataset.communicationBody || "";
        const type = item.dataset.communicationType || "direct";
        const icon = type === "announcement" ? "AN" : "DM";
        const themeClass = type === "announcement" ? "is-announcement" : "is-direct";

        modalContent.innerHTML =
            '<div class="communication-detail-modal ' + themeClass + '">' +
                '<div class="communication-detail-head">' +
                    '<div class="communication-detail-badge">' + escapeHtml(icon) + "</div>" +
                    '<div class="communication-detail-head-copy">' +
                        '<p class="communication-detail-kicker">' + escapeHtml(audience) + "</p>" +
                        '<h3>' + escapeHtml(title) + "</h3>" +
                        '<span class="communication-detail-time">' + escapeHtml(time) + "</span>" +
                    "</div>" +
                "</div>" +
                '<div class="communication-detail-body">' + formatMessageBody(body) + "</div>" +
            "</div>";

        modal.classList.add("communication-detail-open");

        if (typeof openModal === "function") {
            openModal();
        } else {
            modal.style.display = "flex";
        }
    }

    function initCommunicationDropdown(dropdown) {
        dropdown.classList.remove("is-hydrated");
        const apiUrl = dropdown.dataset.communicationApi;
        const postUrl = dropdown.dataset.communicationPost;
        const role = dropdown.dataset.role || "";
        const userKey = dropdown.dataset.communicationUserKey || role || "anonymous";
        const emptyText = dropdown.dataset.emptyText || "No announcements or messages yet.";
        const trigger = dropdown.querySelector(".communication-trigger");
        const panel = dropdown.querySelector(".communication-panel");
        const lists = Array.from(dropdown.querySelectorAll("[data-communication-list]"));
        const form = dropdown.querySelector("[data-communication-form]");
        const typeInput = dropdown.querySelector("[data-communication-type-input]");
        const recipientField = dropdown.querySelector("[data-communication-recipient-field]");
        const totalBadge = dropdown.querySelector("[data-communication-total]");
        const totalMeta = dropdown.querySelector("[data-communication-total-meta]");
        const newBadge = dropdown.querySelector("[data-communication-new-badge]");
        const feedback = dropdown.querySelector("[data-communication-feedback]");
        const titleLabel = dropdown.querySelector("[data-communication-title-label]");
        const titleInput = dropdown.querySelector("[data-communication-title-input]");
        const bodyLabel = dropdown.querySelector("[data-communication-body-label]");
        const bodyInput = dropdown.querySelector("[data-communication-body-input]");
        const submitButton = dropdown.querySelector("[data-communication-submit-btn]");
        const markReadButtons = dropdown.querySelectorAll("[data-communication-mark-read]");
        const modeButtons = dropdown.querySelectorAll("[data-communication-mode]");
        const pageTabs = dropdown.querySelectorAll("[data-communication-page-target]");
        const pageCountNodes = dropdown.querySelectorAll("[data-communication-page-count]");
        const modeCountNodes = dropdown.querySelectorAll("[data-communication-mode-count]");

        if (!apiUrl || !postUrl || !trigger || !panel || !lists.length || !form || !typeInput || !totalBadge || !totalMeta || !newBadge) {
            return;
        }

        const readApiUrl = "/api/communications/read/";
        const seenApiUrl = "/api/communications/seen/";
        let knownIds = [];
        let readIds = new Set(Array.from(dropdown.querySelectorAll('[data-communication-id][data-communication-read="true"]')).map(function (item) {
            return String(item.dataset.communicationId);
        }));
        let highlightedIds = new Set(Array.from(dropdown.querySelectorAll('[data-communication-id][data-communication-new="true"]')).map(function (item) {
            return String(item.dataset.communicationId);
        }));
        let currentMode = typeInput.value || "ANNOUNCEMENT";
        let currentPage = role === "HR" ? "compose" : "announcement";
        let hasFetchedOnce = false;
        let feedbackTimer = null;
        const formDrafts = {
            ANNOUNCEMENT: { title: "", body: "", recipient: "" },
            DIRECT: { title: "", body: "", recipient: "" },
        };

        function updateCount(count) {
            totalBadge.textContent = count;
            totalMeta.textContent = count;
            totalBadge.classList.toggle("hidden", count <= 0);
        }

        function updateUnreadCount() {
            updateCount(knownIds.filter(function (id) {
                return !readIds.has(id);
            }).length);
        }

        function updateNewBadge() {
            const count = Array.from(highlightedIds).filter(function (id) {
                return knownIds.includes(id) && !readIds.has(id);
            }).length;
            if (count > 0) {
                newBadge.textContent = count;
                newBadge.classList.remove("hidden");
            } else {
                newBadge.textContent = "";
                newBadge.classList.add("hidden");
            }
        }

        function clearNewHighlights() {
            if (!highlightedIds.size) {
                return;
            }

            const idsToClear = Array.from(highlightedIds);
            highlightedIds.clear();
            updateNewBadge();
            filterRenderedItems();
            refreshSectionCountsFromDom();
            postSeenState(idsToClear);
        }
        dropdown.__communicationClearNew = clearNewHighlights;

        function setFeedback(message, isError) {
            if (!feedback) {
                return;
            }

            if (feedbackTimer) {
                window.clearTimeout(feedbackTimer);
                feedbackTimer = null;
            }

            if (!message) {
                feedback.textContent = "";
                feedback.classList.add("hidden");
                feedback.classList.remove("is-error", "is-success");
                return;
            }

            feedback.textContent = message;
            feedback.classList.remove("hidden");
            feedback.classList.toggle("is-error", !!isError);
            feedback.classList.toggle("is-success", !isError);

            if (!isError) {
                feedbackTimer = window.setTimeout(function () {
                    setFeedback("", false);
                }, 2600);
            }
        }

        function getActiveDraftKey() {
            return role === "HR" ? (currentMode === "DIRECT" ? "DIRECT" : "ANNOUNCEMENT") : "DIRECT";
        }

        function saveCurrentDraft() {
            const key = getActiveDraftKey();
            formDrafts[key] = {
                title: titleInput ? String(titleInput.value || "") : "",
                body: bodyInput ? String(bodyInput.value || "") : "",
                recipient: role === "HR" && form.elements.recipient_id ? String(form.elements.recipient_id.value || "") : "",
            };
        }

        function restoreDraft(modeKey) {
            const draft = formDrafts[modeKey] || { title: "", body: "", recipient: "" };

            if (titleInput) {
                titleInput.value = draft.title || "";
            }

            if (bodyInput) {
                bodyInput.value = draft.body || "";
            }

            if (role === "HR" && form.elements.recipient_id) {
                form.elements.recipient_id.value = draft.recipient || "";
            }
        }

        function clearDraft(modeKey) {
            formDrafts[modeKey] = { title: "", body: "", recipient: "" };
        }

        function updateFormCopy() {
            if (role !== "HR") {
                return;
            }

            if (titleLabel) {
                titleLabel.textContent = currentMode === "DIRECT" ? "Subject" : "Title";
            }

            if (titleInput) {
                titleInput.placeholder = currentMode === "DIRECT"
                    ? "Write a short message subject"
                    : "Write a short title";
            }

            if (bodyLabel) {
                bodyLabel.textContent = currentMode === "DIRECT" ? "Message to Employee" : "Announcement Message";
            }

            if (bodyInput) {
                bodyInput.placeholder = currentMode === "DIRECT"
                    ? "Write your personal message to the employee"
                    : "Share the update you want employees to see";
            }

            if (submitButton) {
                submitButton.textContent = currentMode === "DIRECT" ? "Send message" : "Send update";
            }
        }

        function updateSectionCounts(items) {
            const unseenAnnouncementCount = items.filter(function (item) {
                return item.type_class === "announcement" && !item.is_outgoing && !readIds.has(String(item.id));
            }).length;
            const unseenDirectCount = items.filter(function (item) {
                return item.type_class === "direct" && !item.is_outgoing && !readIds.has(String(item.id));
            }).length;
            const newAnnouncementCount = items.filter(function (item) {
                return item.type_class === "announcement" && !item.is_outgoing && highlightedIds.has(String(item.id)) && !readIds.has(String(item.id));
            }).length;
            const newDirectCount = items.filter(function (item) {
                return item.type_class === "direct" && !item.is_outgoing && highlightedIds.has(String(item.id)) && !readIds.has(String(item.id));
            }).length;

            pageCountNodes.forEach(function (node) {
                const target = node.dataset.communicationPageCount || "";
                const count = target === "announcement" ? unseenAnnouncementCount : unseenDirectCount;
                node.textContent = count;
                node.classList.toggle("hidden", count <= 0);
                const tab = node.closest("[data-communication-page-target]");
                if (tab) {
                    const hasNew = target === "announcement" ? newAnnouncementCount > 0 : newDirectCount > 0;
                    tab.classList.toggle("has-new", hasNew);
                }
            });

            modeCountNodes.forEach(function (node) {
                const target = (node.dataset.communicationModeCount || "").toUpperCase();
                const count = target === "ANNOUNCEMENT" ? unseenAnnouncementCount : unseenDirectCount;
                node.textContent = count;
                node.classList.toggle("hidden", count <= 0);
                const button = node.closest("[data-communication-mode]");
                if (button) {
                    const hasNew = target === "ANNOUNCEMENT" ? newAnnouncementCount > 0 : newDirectCount > 0;
                    button.classList.toggle("has-new", hasNew);
                }
            });

            updateMarkReadButtons(unseenAnnouncementCount, unseenDirectCount);
        }

        function updateMarkReadButtons(unseenAnnouncementCount, unseenDirectCount) {
            markReadButtons.forEach(function (button) {
                const target = (button.dataset.communicationMarkTarget || "active").toLowerCase();
                let count = 0;
                let label = "Mark the message as read";
                let shouldShow = true;

                if (target === "announcement") {
                    count = unseenAnnouncementCount;
                    label = "Mark the announcement as read";
                } else if (target === "direct") {
                    count = unseenDirectCount;
                    label = role === "HR" ? "Mark all Employee Messages as Read" : "Mark the message as read";
                } else if (role === "HR") {
                    count = currentMode === "DIRECT" ? unseenDirectCount : unseenAnnouncementCount;
                    label = currentMode === "DIRECT" ? "Mark the message as read" : "Mark the announcement as read";
                } else {
                    count = currentPage === "compose" ? unseenDirectCount : unseenAnnouncementCount;
                    label = currentPage === "compose" ? "Mark the message as read" : "Mark the announcement as read";
                }

                if (role === "HR" && target === "direct") {
                    shouldShow = currentMode === "DIRECT";
                }

                if (role === "HR" && target === "announcement") {
                    shouldShow = false;
                }

                if (count <= 0) {
                    shouldShow = false;
                }

                button.textContent = label;
                button.classList.toggle("hidden", !shouldShow);
                button.disabled = count <= 0;
                button.setAttribute("aria-disabled", count <= 0 ? "true" : "false");
            });
        }

        function refreshSectionCountsFromDom() {
            const items = Array.from(dropdown.querySelectorAll("[data-communication-id]")).map(function (item) {
                return {
                    id: item.dataset.communicationId || "",
                    type_class: item.dataset.communicationType || "",
                    is_outgoing: item.dataset.communicationOutgoing === "true",
                };
            });

            updateSectionCounts(items);
        }

        function getUnreadCountsFromRenderedDom() {
            const items = Array.from(dropdown.querySelectorAll("[data-communication-id]"));

            return items.reduce(function (accumulator, item) {
                const type = String(item.dataset.communicationType || "");
                const isOutgoing = item.dataset.communicationOutgoing === "true";
                const isRead = item.dataset.communicationRead === "true";

                if (isOutgoing || isRead) {
                    return accumulator;
                }

                if (type === "announcement") {
                    accumulator.announcement += 1;
                } else if (type === "direct") {
                    accumulator.direct += 1;
                }

                return accumulator;
            }, { announcement: 0, direct: 0 });
        }

        function syncInitialMarkReadButtonsFromDom() {
            const counts = getUnreadCountsFromRenderedDom();
            updateMarkReadButtons(counts.announcement, counts.direct);
        }

        function markItemsAsRead(targetType) {
            let changed = false;

            knownIds.forEach(function (id) {
                const item = dropdown.querySelector('[data-communication-id="' + id + '"]');

                if (!item || readIds.has(id) || (item.dataset.communicationType || "") !== targetType) {
                    return;
                }

                readIds.add(id);
                highlightedIds.delete(id);
                changed = true;
            });

            if (!changed) {
                return;
            }

            postMarkRead({ target_type: targetType.toUpperCase() }).catch(function () {});
        }

        function postSeenState(ids) {
            const communicationIds = Array.isArray(ids) ? ids.map(String).filter(Boolean) : [];

            if (!communicationIds.length) {
                return Promise.resolve();
            }

            return fetch(seenApiUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({ ids: communicationIds }),
            }).catch(function () {});
        }

        function applyMode(mode) {
            saveCurrentDraft();
            setFeedback("", false);
            currentMode = mode;
            typeInput.value = mode;
            modeButtons.forEach(function (button) {
                button.classList.toggle("is-active", button.dataset.communicationMode === mode);
            });

            if (recipientField) {
                recipientField.classList.toggle("hidden", mode !== "DIRECT");
            }

            updateFormCopy();
            restoreDraft(mode);
            filterRenderedItems();
            refreshSectionCountsFromDom();
            syncInitialMarkReadButtonsFromDom();
        }

        function filterRenderedItems() {
            lists.forEach(function (list) {
                const listType = list.dataset.communicationList || "all";
                let visibleCount = 0;

                list.querySelectorAll(".communication-item[data-communication-id]").forEach(function (item) {
                    const itemType = item.dataset.communicationType || "";
                    const itemId = String(item.dataset.communicationId || "");
                    let matches = true;

                    if (role === "HR") {
                        const targetType = currentMode === "DIRECT" ? "direct" : "announcement";
                        matches = itemType === targetType;
                    } else if (listType === "announcement") {
                        matches = itemType === "announcement";
                    } else if (listType === "direct") {
                        matches = itemType === "direct";
                    }

                    item.classList.toggle("hidden", !matches);
                    item.classList.toggle("is-new", highlightedIds.has(itemId) && !readIds.has(itemId));
                    item.classList.toggle("is-read", readIds.has(itemId) && !highlightedIds.has(itemId));
                    if (matches) {
                        visibleCount += 1;
                    }
                });

                const listEmptyText = getListEmptyText(listType, role, currentMode, emptyText);
                const emptyNode = list.querySelector(".communication-empty");

                if (emptyNode) {
                    emptyNode.classList.toggle("hidden", visibleCount !== 0);
                    emptyNode.textContent = listEmptyText;
                } else if (visibleCount === 0) {
                    list.insertAdjacentHTML("beforeend", '<div class="communication-empty">' + listEmptyText + "</div>");
                }
            });
        }

        function openPage(pageName) {
            setFeedback("", false);
            currentPage = pageName;
            dropdown.querySelectorAll("[data-communication-page]").forEach(function (page) {
                page.classList.toggle("is-active", page.dataset.communicationPage === pageName);
            });

            pageTabs.forEach(function (tab) {
                tab.classList.toggle("is-active", tab.dataset.communicationPageTarget === pageName);
            });

            const unreadAnnouncementCount = knownIds.filter(function (id) {
                const item = dropdown.querySelector('[data-communication-id="' + id + '"]');
                return item && !readIds.has(id) && item.dataset.communicationType === "announcement";
            }).length;
            const unreadDirectCount = knownIds.filter(function (id) {
                const item = dropdown.querySelector('[data-communication-id="' + id + '"]');
                return item && !readIds.has(id) && item.dataset.communicationType === "direct";
            }).length;
            updateMarkReadButtons(unreadAnnouncementCount, unreadDirectCount);
        }

        function updatePointerPosition() {
            const panelRect = panel.getBoundingClientRect();
            const triggerRect = trigger.getBoundingClientRect();
            const pointerSize = window.innerWidth <= 768 ? 14 : 18;
            const triggerCenterX = triggerRect.left + (triggerRect.width / 2);
            let rightOffset = panelRect.right - triggerCenterX - (pointerSize / 2);

            rightOffset = Math.max(10, Math.min(panelRect.width - pointerSize - 10, rightOffset));
            panel.style.setProperty("--communication-pointer-right", rightOffset + "px");
        }

        function handlePayload(payload) {
            const items = Array.isArray(payload.items) ? payload.items : [];
            const nextIds = items
                .filter(function (item) { return !item.is_outgoing; })
                .map(function (item) { return String(item.id); });
            knownIds = nextIds;
            readIds = new Set(items.filter(function (item) {
                return item.is_read && !item.is_outgoing;
            }).map(function (item) {
                return String(item.id);
            }));
            highlightedIds = new Set(items.filter(function (item) {
                return !item.is_outgoing && item.is_new && !item.is_read;
            }).map(function (item) {
                return String(item.id);
            }));
            lists.forEach(function (list) {
                const listType = list.dataset.communicationList || "all";
                let filteredItems = items;

                if (role !== "HR" && listType === "announcement") {
                    filteredItems = items.filter(function (item) { return item.type_class === "announcement"; });
                } else if (role !== "HR" && listType === "direct") {
                    filteredItems = items.filter(function (item) { return item.type_class === "direct"; });
                }

                renderListContents(list, filteredItems, getListEmptyText(listType, role, currentMode, emptyText));
                list.querySelectorAll(".communication-item[data-communication-id]").forEach(function (item) {
                    item.addEventListener("click", function () {
                        const itemId = String(item.dataset.communicationId || "");
                        readIds.add(itemId);
                        highlightedIds.delete(itemId);
                        updateNewBadge();
                        filterRenderedItems();
                        refreshSectionCountsFromDom();
                        updateUnreadCount();
                        openCommunicationDetailModal(item);
                        postMarkRead({ ids: [itemId] }).catch(function () {});
                    });
                });
            });
            updateSectionCounts(items);
            filterRenderedItems();
            updateUnreadCount();
            updateNewBadge();
            dropdown.classList.add("is-hydrated");
            hasFetchedOnce = true;
        }

        function fetchFeed() {
            const hasRenderedItems = lists.some(function (list) {
                return !!list.querySelector("[data-communication-id]");
            });
            const shouldShowSkeleton =
                dropdown.classList.contains("is-open") &&
                !hasRenderedItems;

            if (shouldShowSkeleton && typeof window.startAsyncPopupSkeleton === "function") {
                window.startAsyncPopupSkeleton(panel);
            }

            fetch(apiUrl + (apiUrl.includes("?") ? "&" : "?") + "_ts=" + Date.now(), {
                headers: { "X-Requested-With": "XMLHttpRequest" }
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Communication fetch failed.");
                    }
                    return readResponsePayload(response);
                })
                .then(handlePayload)
                .catch(function () {})
                .finally(function () {
                    dropdown.classList.add("is-hydrated");
                    if (shouldShowSkeleton && typeof window.finishAsyncPopupSkeleton === "function") {
                        window.finishAsyncPopupSkeleton(panel);
                    }
                });
        }

        function submitForm(event) {
            event.preventDefault();
            setFeedback("", false);

            const formData = new FormData(form);
            if (role === "HR" && typeInput.value === "DIRECT" && !String(formData.get("recipient_id") || "").trim()) {
                setFeedback("Select an employee for a personal message.", true);
                return;
            }

            const csrfToken = String(formData.get("csrfmiddlewaretoken") || getCsrfToken() || "").trim();

            if (submitButton) {
                submitButton.disabled = true;
            }

            fetch(postUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: formData,
            })
                .then(function (response) {
                    return readResponsePayload(response).then(function (payload) {
                        if (!response.ok) {
                            throw new Error(payload.error || "Unable to send message.");
                        }
                        return payload;
                    });
                })
                .then(function (payload) {
                    const submittedMode = role === "HR" ? (currentMode === "DIRECT" ? "DIRECT" : "ANNOUNCEMENT") : "DIRECT";
                    clearDraft(submittedMode);
                    if (titleInput) {
                        titleInput.value = "";
                    }
                    if (bodyInput) {
                        bodyInput.value = "";
                    }
                    if (role === "HR" && form.elements.recipient_id) {
                        form.elements.recipient_id.value = "";
                    }
                    setFeedback("Sent successfully.", false);
                    handlePayload(payload);
                })
                .catch(function (error) {
                    setFeedback(error.message && !/^<!DOCTYPE/i.test(error.message) ? error.message : "Unable to send message right now.", true);
                })
                .finally(function () {
                    if (submitButton) {
                        submitButton.disabled = false;
                    }
                });
        }

        function postMarkRead(payload) {
            return fetch(readApiUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify(payload),
            })
                .then(readResponsePayload)
                .then(function (payload) {
                    handlePayload(payload);
                    return payload;
                });
        }

        knownIds = Array.from(dropdown.querySelectorAll("[data-communication-id]")).filter(function (item) {
            return item.dataset.communicationOutgoing !== "true";
        }).map(function (item) {
            return String(item.dataset.communicationId);
        });
        updateCount(Number(totalBadge.textContent || totalMeta.textContent || 0));
        updateNewBadge();
        filterRenderedItems();
        refreshSectionCountsFromDom();
        syncInitialMarkReadButtonsFromDom();

        if (role === "HR") {
            applyMode("ANNOUNCEMENT");
        }
        openPage(role === "HR" ? "compose" : "announcement");

        modeButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                applyMode(button.dataset.communicationMode || "ANNOUNCEMENT");
            });
        });

        pageTabs.forEach(function (tab) {
            tab.addEventListener("click", function () {
                openPage(tab.dataset.communicationPageTarget || "inbox");
            });
        });

        markReadButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                const target = button.dataset.communicationMarkTarget || "active";
                const resolvedTarget = target === "active"
                    ? (role === "HR" ? (currentMode === "DIRECT" ? "direct" : "announcement") : (currentPage === "compose" ? "direct" : "announcement"))
                    : target;

                markItemsAsRead(resolvedTarget);
            });
        });

        trigger.addEventListener("click", function (event) {
            event.preventDefault();
            event.stopPropagation();

            filterRenderedItems();
            refreshSectionCountsFromDom();
            syncInitialMarkReadButtonsFromDom();

            const willOpen = !dropdown.classList.contains("is-open");

            if (willOpen && typeof window.closeHeaderMenusExcept === "function") {
                window.closeHeaderMenusExcept({ keepCommunication: dropdown });
            }

            document.querySelectorAll(".communication-dropdown.is-open").forEach(function (openDropdown) {
                if (openDropdown !== dropdown) {
                    openDropdown.classList.remove("is-open");
                    const openTrigger = openDropdown.querySelector(".communication-trigger");
                    if (openTrigger) {
                        openTrigger.setAttribute("aria-expanded", "false");
                    }
                }
            });

            dropdown.classList.toggle("is-open", willOpen);
            trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");

            if (willOpen) {
                updatePointerPosition();
                window.requestAnimationFrame(function () {
                    filterRenderedItems();
                    refreshSectionCountsFromDom();
                    syncInitialMarkReadButtonsFromDom();
                });
                fetchFeed();
            } else {
                setFeedback("", false);
                clearNewHighlights();
            }
        });

        window.addEventListener("resize", function () {
            if (dropdown.classList.contains("is-open")) {
                updatePointerPosition();
            }
        });

        form.addEventListener("submit", submitForm);
        fetchFeed();
        window.setInterval(fetchFeed, POLL_INTERVAL);
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".communication-dropdown[data-communication-api]").forEach(initCommunicationDropdown);

        document.addEventListener("click", function (event) {
            if (event.target && event.target.closest("#modal")) {
                return;
            }

            document.querySelectorAll(".communication-dropdown.is-open").forEach(function (dropdown) {
                if (dropdown.contains(event.target)) {
                    return;
                }

                dropdown.classList.remove("is-open");
                const trigger = dropdown.querySelector(".communication-trigger");
                if (trigger) {
                    trigger.setAttribute("aria-expanded", "false");
                }
                const feedbackNode = dropdown.querySelector("[data-communication-feedback]");
                if (feedbackNode) {
                    feedbackNode.textContent = "";
                    feedbackNode.classList.add("hidden");
                    feedbackNode.classList.remove("is-error", "is-success");
                }
                if (dropdown.__communicationClearNew) {
                    dropdown.__communicationClearNew();
                }
            });
        });
    });
})();
