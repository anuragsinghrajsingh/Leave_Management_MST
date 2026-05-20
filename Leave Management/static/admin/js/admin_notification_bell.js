(function () {
    const POLL_MS = 45000;
    const PAGE_SIZE = 10;

    function getCookie(name) {
        const part = document.cookie
            .split(";")
            .map(function (item) { return item.trim(); })
            .find(function (item) { return item.startsWith(name + "="); });
        return part ? decodeURIComponent(part.split("=").slice(1).join("=")) : "";
    }

    function csrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input && input.value ? input.value : getCookie("csrftoken");
    }

    function post(url, data) {
        const body = new URLSearchParams();
        Object.keys(data || {}).forEach(function (key) {
            body.append(key, data[key]);
        });

        return fetch(url, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken(),
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
            credentials: "same-origin",
            body: body.toString(),
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("Request failed");
            }
            return response.json();
        });
    }

    function initials(value) {
        const parts = String(value || "Admin")
            .trim()
            .split(/\s+/)
            .filter(Boolean);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return (parts[0] || "AD").slice(0, 2).toUpperCase();
    }

    function text(node, value) {
        if (node) {
            node.textContent = value || "-";
        }
    }

    function createBeep() {
        let audioContext = null;
        let unlocked = false;

        function unlock() {
            if (unlocked) {
                return;
            }
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextClass) {
                return;
            }
            audioContext = audioContext || new AudioContextClass();
            if (audioContext.state === "suspended") {
                audioContext.resume();
            }
            unlocked = true;
        }

        function play() {
            if (!unlocked || !audioContext) {
                return;
            }
            const oscillator = audioContext.createOscillator();
            const gain = audioContext.createGain();
            oscillator.type = "sine";
            oscillator.frequency.setValueAtTime(880, audioContext.currentTime);
            oscillator.frequency.exponentialRampToValueAtTime(660, audioContext.currentTime + 0.12);
            gain.gain.setValueAtTime(0.0001, audioContext.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.18, audioContext.currentTime + 0.015);
            gain.gain.exponentialRampToValueAtTime(0.0001, audioContext.currentTime + 0.18);
            oscillator.connect(gain);
            gain.connect(audioContext.destination);
            oscillator.start();
            oscillator.stop(audioContext.currentTime + 0.2);
        }

        return { unlock: unlock, play: play, isUnlocked: function () { return unlocked; } };
    }

    function initBell(root) {
        const toggle = root.querySelector("[data-admin-bell-toggle]");
        const panel = root.querySelector("[data-admin-bell-panel]");
        const list = root.querySelector("[data-admin-bell-list]");
        const countNode = root.querySelector("[data-admin-bell-count]");
        const markAllButton = root.querySelector("[data-admin-bell-mark-all]");
        const detailModal = document.querySelector("[data-admin-bell-detail-modal]");
        const feedUrl = root.dataset.feedUrl;
        const seenUrl = root.dataset.seenUrl;
        const readUrl = root.dataset.readUrl;
        const readAllUrl = root.dataset.readAllUrl;
        const beep = createBeep();
        let lastNewCount = 0;
        let latestItems = [];
        let hasLoaded = false;
        let hasMore = false;
        let loadingMore = false;

        if (!toggle || !panel || !list || !countNode || !feedUrl || !seenUrl || !readUrl || !readAllUrl) {
            return;
        }

        function updateCount(count) {
            countNode.textContent = String(count || 0);
            countNode.classList.toggle("hidden", !count);
            toggle.classList.toggle("has-new", !!count);
            if (markAllButton) {
                markAllButton.disabled = !count;
            }
        }

        function mergeItems(items, append) {
            const incoming = items || [];
            if (!append) {
                latestItems = incoming;
                return;
            }
            const known = new Set(latestItems.map(function (item) { return String(item.id); }));
            incoming.forEach(function (item) {
                if (!known.has(String(item.id))) {
                    latestItems.push(item);
                }
            });
        }

        function render(items, append) {
            mergeItems(items, append);
            if (!latestItems.length) {
                list.innerHTML = '<span class="admin-bell-empty">No admin messages yet.</span>';
                return;
            }

            list.innerHTML = latestItems.map(function (item) {
                const hasMore = String(item.body_full || "").length > String(item.body_preview || "").length;
                return [
                    '<button type="button" class="admin-bell-item ' + (!item.is_read ? 'is-unread' : '') + '" data-admin-bell-message-id="' + item.id + '">',
                    '<span class="admin-bell-avatar">' + initials(item.sender) + '</span>',
                    '<span class="admin-bell-copy">',
                    '<strong>' + escapeText(item.title) + '</strong>',
                    '<span>' + escapeText(item.sender) + ' • ' + escapeText(item.type_label) + '</span>',
                    '<span class="admin-bell-message-preview">' + escapeText(item.body_full || item.body_preview) + '</span>',
                    (hasMore ? '<span class="admin-bell-more-label">...More</span>' : ''),
                    '<small>' + escapeText(item.created_at) + '</small>',
                    (!item.is_read ? '<em class="admin-bell-new-label">New</em>' : ''),
                    '</span>',
                    '</button>'
                ].join("");
            }).join("");
        }

        function escapeText(value) {
            return String(value || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
        }

        function feedRequest(offset) {
            const url = new URL(feedUrl, window.location.origin);
            url.searchParams.set("offset", String(offset || 0));
            url.searchParams.set("limit", String(PAGE_SIZE));
            return fetch(url.toString(), {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Feed failed");
                    }
                    return response.json();
                });
        }

        function refresh(allowSound) {
            return feedRequest(0)
                .then(function (payload) {
                    const newCount = Number(payload.new_count || 0);
                    hasMore = !!payload.has_more;
                    updateCount(Number(payload.count || 0));
                    render(payload.items || [], false);
                    if (allowSound && hasLoaded && newCount > lastNewCount) {
                        beep.play();
                    }
                    lastNewCount = newCount;
                    hasLoaded = true;
                })
                .catch(function () {
                    if (!hasLoaded) {
                        list.innerHTML = '<span class="admin-bell-empty">Could not load admin messages.</span>';
                    }
                });
        }

        function loadMore() {
            if (loadingMore || !hasMore) {
                return;
            }
            loadingMore = true;
            feedRequest(latestItems.length)
                .then(function (payload) {
                    hasMore = !!payload.has_more;
                    updateCount(Number(payload.count || 0));
                    render(payload.items || [], true);
                })
                .catch(function () {})
                .finally(function () {
                    loadingMore = false;
                });
        }

        function markSeen() {
            post(seenUrl, {})
                .then(function (payload) {
                    updateCount(Number(payload.count || 0));
                    lastNewCount = 0;
                })
                .catch(function () {});
        }

        function openDetail(item) {
            if (!detailModal || !item) {
                return;
            }
            text(detailModal.querySelector("[data-admin-bell-detail-title]"), item.title);
            text(detailModal.querySelector("[data-admin-bell-detail-type]"), item.type_label);
            text(detailModal.querySelector("[data-admin-bell-detail-created]"), item.created_at);
            text(detailModal.querySelector("[data-admin-bell-detail-sender]"), item.sender);
            text(detailModal.querySelector("[data-admin-bell-detail-target]"), item.target);
            text(detailModal.querySelector("[data-admin-bell-detail-body]"), item.body_full);
            detailModal.classList.add("is-open");

            post(readUrl, { communication_id: item.id })
                .then(function (payload) {
                    item.is_read = true;
                    updateCount(Number(payload.count || 0));
                    render(latestItems, false);
                })
                .catch(function () {});
        }

        function closeDetail() {
            if (detailModal) {
                detailModal.classList.remove("is-open");
            }
        }

        toggle.addEventListener("click", function (event) {
            event.stopPropagation();
            beep.unlock();
            root.classList.toggle("is-open");
            toggle.setAttribute("aria-expanded", root.classList.contains("is-open") ? "true" : "false");
            if (root.classList.contains("is-open")) {
                markSeen();
            }
        });

        if (markAllButton) {
            markAllButton.addEventListener("click", function (event) {
                event.stopPropagation();
                post(readAllUrl, {})
                    .then(function (payload) {
                        latestItems.forEach(function (item) {
                            item.is_read = true;
                        });
                        updateCount(Number(payload.count || 0));
                        render(latestItems, false);
                        lastNewCount = 0;
                    })
                    .catch(function () {});
            });
        }

        list.addEventListener("scroll", function () {
            if (list.scrollTop + list.clientHeight >= list.scrollHeight - 24) {
                loadMore();
            }
        });

        list.addEventListener("click", function (event) {
            const button = event.target.closest("[data-admin-bell-message-id]");
            if (!button) {
                return;
            }
            const item = latestItems.find(function (entry) {
                return String(entry.id) === String(button.dataset.adminBellMessageId);
            });
            openDetail(item);
        });

        document.addEventListener("click", function (event) {
            if (!root.contains(event.target)) {
                root.classList.remove("is-open");
                toggle.setAttribute("aria-expanded", "false");
            }
            if (detailModal && (event.target === detailModal || event.target.closest("[data-admin-bell-detail-close]"))) {
                closeDetail();
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                root.classList.remove("is-open");
                toggle.setAttribute("aria-expanded", "false");
                closeDetail();
            }
        });

        document.addEventListener("click", function () {
            beep.unlock();
        }, { once: true });

        refresh(false);
        window.setInterval(function () {
            refresh(true);
        }, POLL_MS);
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-admin-notification-bell]").forEach(initBell);
    });
})();
