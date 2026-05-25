(function () {
    const POLL_INTERVAL = 60000;
    const NOTIFICATION_PAGE_SIZE = 50;
    let notificationAudioContext = null;
    let notificationAudioUnlocked = false;
    let pendingNotificationAudio = [];
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

    function getNotificationAudioContext() {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;

        if (!AudioCtx) {
            return null;
        }

        try {
            if (!notificationAudioContext) {
                notificationAudioContext = new AudioCtx();
            }
            return notificationAudioContext;
        } catch (error) {
            return null;
        }
    }

    function unlockNotificationAudio() {
        const audioContext = getNotificationAudioContext();

        if (!audioContext) {
            return;
        }

        const finishUnlock = function () {
            notificationAudioUnlocked = true;
            const queuedAudio = pendingNotificationAudio.slice();
            pendingNotificationAudio = [];
            queuedAudio.forEach(function (callback) {
                try {
                    callback();
                } catch (error) {
                    // Ignore queued audio failures silently.
                }
            });
        };

        if (audioContext.state === "suspended") {
            audioContext.resume().then(finishUnlock).catch(function () {});
        } else {
            finishUnlock();
        }
    }

    function runWhenNotificationAudioReady(callback) {
        const audioContext = getNotificationAudioContext();

        if (!audioContext) {
            return;
        }

        const runCallback = function () {
            notificationAudioUnlocked = true;
            try {
                callback(audioContext);
            } catch (error) {
                // Ignore audio failures silently.
            }
        };

        if (audioContext.state === "suspended") {
            audioContext.resume().then(runCallback).catch(function () {
                pendingNotificationAudio.push(function () {
                    runWhenNotificationAudioReady(callback);
                });
            });
            return;
        }

        runCallback();
    }

    ["pointerdown", "keydown", "touchstart"].forEach(function (eventName) {
        window.addEventListener(eventName, unlockNotificationAudio, { once: true, passive: true });
    });

    window.armNotificationAudio = unlockNotificationAudio;

    function playNotificationTone(statusClass, activityLabel) {
        if (!notificationAudioUnlocked) {
            runWhenNotificationAudioReady(function () {
                playNotificationTone(statusClass, activityLabel);
            });
            return;
        }

        const audioContext = getNotificationAudioContext();

        if (!audioContext) {
            return;
        }

        if (audioContext.state === "suspended") {
            runWhenNotificationAudioReady(function () {
                playNotificationTone(statusClass, activityLabel);
            });
            return;
        }

        try {
            const now = audioContext.currentTime;
            const masterGain = audioContext.createGain();
            const normalizedActivity = String(activityLabel || "").trim().toLowerCase();
            const bellLayers = statusClass === "approved"
                ? [
                    { frequency: 659, volume: 0.07, start: 0, duration: 0.34 },
                    { frequency: 880, volume: 0.078, start: 0.18, duration: 0.38 },
                    { frequency: 1175, volume: 0.066, start: 0.38, duration: 0.44 },
                    { frequency: 1568, volume: 0.046, start: 0.58, duration: 0.5 },
                    { frequency: 2093, volume: 0.024, start: 0.76, duration: 0.34 },
                ]
                : statusClass === "rejected"
                    ? [
                        { frequency: 523, volume: 0.076, start: 0, duration: 0.42 },
                        { frequency: 392, volume: 0.084, start: 0.24, duration: 0.5 },
                        { frequency: 294, volume: 0.07, start: 0.52, duration: 0.54 },
                        { frequency: 220, volume: 0.042, start: 0.78, duration: 0.48 },
                    ]
                    : normalizedActivity === "updated"
                        ? [
                            { frequency: 784, volume: 0.076, start: 0, duration: 0.28 },
                            { frequency: 622, volume: 0.064, start: 0.22, duration: 0.3 },
                            { frequency: 988, volume: 0.074, start: 0.46, duration: 0.38 },
                            { frequency: 1319, volume: 0.038, start: 0.68, duration: 0.3 },
                        ]
                        : [
                            { frequency: 740, volume: 0.078, start: 0, duration: 0.34 },
                            { frequency: 988, volume: 0.074, start: 0.2, duration: 0.38 },
                            { frequency: 1245, volume: 0.058, start: 0.44, duration: 0.42 },
                            { frequency: 932, volume: 0.038, start: 0.7, duration: 0.34 },
                        ];

            masterGain.gain.setValueAtTime(1.6, now);
            masterGain.connect(audioContext.destination);

            bellLayers.forEach(function (layer) {
                const oscillator = audioContext.createOscillator();
                const gain = audioContext.createGain();
                const startAt = now + layer.start;
                const stopAt = startAt + layer.duration;

                oscillator.type = "sine";
                oscillator.frequency.setValueAtTime(layer.frequency, startAt);
                oscillator.frequency.exponentialRampToValueAtTime(
                    layer.frequency * (statusClass === "approved" ? 1.006 : 0.992),
                    stopAt
                );

                gain.gain.setValueAtTime(0.0001, startAt);
                gain.gain.exponentialRampToValueAtTime(layer.volume, startAt + 0.025);
                gain.gain.exponentialRampToValueAtTime(0.0001, stopAt);

                oscillator.connect(gain);
                gain.connect(masterGain);
                oscillator.start(startAt);
                oscillator.stop(stopAt + 0.03);
            });

            if (statusClass === "approved") {
                window.setTimeout(function () { speakNotificationAlert("Approved", { pitch: 1.16, rate: 0.98 }); }, 190);
            } else if (statusClass === "rejected") {
                window.setTimeout(function () { speakNotificationAlert("Rejected", { pitch: 0.82, rate: 0.92 }); }, 210);
            } else if (normalizedActivity === "updated") {
                window.setTimeout(function () { speakNotificationAlert("Updated", { pitch: 1.04, rate: 0.9 }); }, 760);
            } else {
                window.setTimeout(function () { speakNotificationAlert("Applied", { pitch: 1.1, rate: 0.94 }); }, 620);
            }
        } catch (error) {
            // Ignore audio failures silently.
        }
    }

    function buildLocalBrowserNotification(item) {
        const isEmployeeDecision = Boolean(item && item.target_panel);
        const isHrPending = Boolean(item && item.employee_id) && !isEmployeeDecision;
        const leaveType = String(item && item.leave_type || "Leave").trim();
        const status = String(item && item.status || item && item.status_class || "").trim();
        const schedule = String(item && item.schedule_text || "").trim();
        const employeeName = String(item && item.display_name || item && item.username || "Employee").trim();

        if (isEmployeeDecision) {
            return {
                title: String(item.headline_text || (leaveType + " Leave " + status)).trim(),
                body: [
                    schedule,
                    item.reviewer_name ? ("Reviewed by " + item.reviewer_name) : "",
                ].filter(Boolean).join(" | "),
            };
        }

        if (isHrPending) {
            return {
                title: ((item.activity_label || "New") + " leave request").trim(),
                body: [
                    employeeName,
                    leaveType + " leave",
                    schedule,
                ].filter(Boolean).join(" | "),
            };
        }

        return {
            title: "Leave Management",
            body: String(item && item.display_name || item && item.created_at || "You have a new update.").trim(),
        };
    }

    function showLocalBrowserNotification(item) {
        if (!("Notification" in window) || Notification.permission !== "granted") {
            return;
        }

        try {
            const detail = buildLocalBrowserNotification(item || {});
            const notification = new Notification(detail.title || "Leave Management", {
                body: detail.body || "You have a new update.",
                icon: "/static/images/ms-technology-logo.png",
                badge: "/static/images/ms-technology-logo.png",
                tag: "lms-bell-" + String(item && item.id || Date.now()),
                renotify: true,
                data: {
                    url: item && item.target_url || "/",
                },
            });

            notification.onclick = function () {
                window.focus();
                const targetUrl = notification.data && notification.data.url;
                if (targetUrl) {
                    window.location.href = targetUrl;
                }
                notification.close();
            };
        } catch (error) {
            // Ignore local notification failures silently.
        }
    }

    function playCommunicationTone(typeClass) {
        if (!notificationAudioUnlocked) {
            return;
        }

        const audioContext = getNotificationAudioContext();

        if (!audioContext) {
            return;
        }

        try {
            const now = audioContext.currentTime;
            const isAnnouncement = typeClass === "announcement";
            const baseFrequency = isAnnouncement ? 880 : 784;
            const masterGain = audioContext.createGain();
            const bellLayers = isAnnouncement
                ? [0, 1.15, 2.3].flatMap(function (repeatStart) {
                    return [
                        { frequency: baseFrequency, volume: 0.05, start: repeatStart, duration: 0.22 },
                        { frequency: baseFrequency * 1.34, volume: 0.046, start: repeatStart + 0.23, duration: 0.24 },
                        { frequency: baseFrequency * 1.5, volume: 0.034, start: repeatStart + 0.52, duration: 0.32 },
                    ];
                })
                : [
                    { frequency: 660, volume: 0.028, start: 0, duration: 0.28 },
                    { frequency: 880, volume: 0.032, start: 0.22, duration: 0.48 },
                    { frequency: 1320, volume: 0.01, start: 0.24, duration: 0.34 },
                ];

            masterGain.gain.setValueAtTime(0.82, now);
            masterGain.connect(audioContext.destination);

            bellLayers.forEach(function (layer) {
                const oscillator = audioContext.createOscillator();
                const gain = audioContext.createGain();
                const startAt = now + layer.start;
                const stopAt = startAt + layer.duration;

                oscillator.type = isAnnouncement ? "triangle" : "sine";
                oscillator.frequency.setValueAtTime(layer.frequency, startAt);
                oscillator.frequency.exponentialRampToValueAtTime(layer.frequency * (isAnnouncement ? 1.006 : 0.988), stopAt);

                gain.gain.setValueAtTime(0.0001, startAt);
                gain.gain.exponentialRampToValueAtTime(layer.volume, startAt + 0.018);
                gain.gain.exponentialRampToValueAtTime(0.0001, stopAt);

                oscillator.connect(gain);
                gain.connect(masterGain);
                oscillator.start(startAt);
                oscillator.stop(stopAt + 0.03);
            });

            if (isAnnouncement) {
                [760, 1900, 3040].forEach(function (delay) {
                    window.setTimeout(speakAnnouncementAlert, delay);
                });
            } else {
                window.setTimeout(function () { speakNotificationAlert("Message", { pitch: 1.08, rate: 0.98 }); }, 170);
            }
        } catch (error) {
            // Ignore audio failures silently.
        }
    }

    function speakAnnouncementAlert() {
        const speech = window.speechSynthesis;

        if (!speech || typeof window.SpeechSynthesisUtterance !== "function") {
            return;
        }

        try {
            speech.cancel();

            const message = new SpeechSynthesisUtterance("Announcement");
            message.volume = 1;
            message.rate = 0.94;
            message.pitch = 1.08;

            speech.speak(message);
        } catch (error) {
            // Ignore speech failures silently.
        }
    }

    function speakNotificationAlert(text, options) {
        const speech = window.speechSynthesis;

        if (!speech || typeof window.SpeechSynthesisUtterance !== "function") {
            return;
        }

        try {
            const settings = options || {};
            const message = new SpeechSynthesisUtterance(text);
            message.volume = 1;
            message.rate = settings.rate || 0.96;
            message.pitch = settings.pitch || 1;

            speech.speak(message);
        } catch (error) {
            // Ignore speech failures silently.
        }
    }

    function playLeaveActionTone(action) {
        if (!notificationAudioUnlocked) {
            runWhenNotificationAudioReady(function () {
                playLeaveActionTone(action);
            });
            return;
        }

        const audioContext = getNotificationAudioContext();

        if (!audioContext) {
            return;
        }

        if (audioContext.state === "suspended") {
            runWhenNotificationAudioReady(function () {
                playLeaveActionTone(action);
            });
            return;
        }

        try {
            if (action === "delete") {
                const duration = 0.62;
                const sampleRate = audioContext.sampleRate;
                const frameCount = Math.floor(sampleRate * duration);
                const noiseBuffer = audioContext.createBuffer(1, frameCount, sampleRate);
                const output = noiseBuffer.getChannelData(0);
                const noise = audioContext.createBufferSource();
                const filter = audioContext.createBiquadFilter();
                const gain = audioContext.createGain();
                const now = audioContext.currentTime;

                for (let i = 0; i < frameCount; i += 1) {
                    output[i] = (Math.random() * 2 - 1) * (1 - i / frameCount);
                }

                noise.buffer = noiseBuffer;
                filter.type = "bandpass";
                filter.frequency.setValueAtTime(5200, now);
                filter.frequency.exponentialRampToValueAtTime(1100, now + duration);
                filter.Q.setValueAtTime(1.8, now);

                gain.gain.setValueAtTime(0.0001, now);
                gain.gain.exponentialRampToValueAtTime(0.075, now + 0.035);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

                noise.connect(filter);
                filter.connect(gain);
                gain.connect(audioContext.destination);
                noise.start(now);
                noise.stop(now + duration);
                window.setTimeout(function () {
                    speakNotificationAlert("Deleted", { pitch: 0.92, rate: 0.94 });
                }, 640);
                return;
            }

            const toneMap = {
                apply: [
                    { frequency: 659, volume: 0.048, start: 0, duration: 0.18 },
                    { frequency: 880, volume: 0.052, start: 0.12, duration: 0.22 },
                    { frequency: 1319, volume: 0.034, start: 0.28, duration: 0.26 },
                ],
                edit: [
                    { frequency: 740, volume: 0.076, start: 0, duration: 0.24 },
                    { frequency: 587, volume: 0.064, start: 0.2, duration: 0.26 },
                    { frequency: 988, volume: 0.072, start: 0.42, duration: 0.34 },
                    { frequency: 1319, volume: 0.036, start: 0.62, duration: 0.28 },
                ],
            };
            const layers = toneMap[action] || toneMap.apply;
            const now = audioContext.currentTime;
            const masterGain = audioContext.createGain();

            masterGain.gain.setValueAtTime(action === "edit" ? 1.55 : 1.15, now);
            masterGain.connect(audioContext.destination);

            layers.forEach(function (layer) {
                const oscillator = audioContext.createOscillator();
                const gain = audioContext.createGain();
                const startAt = now + layer.start;
                const stopAt = startAt + layer.duration;

                oscillator.type = action === "edit" ? "triangle" : "sine";
                oscillator.frequency.setValueAtTime(layer.frequency, startAt);
                oscillator.frequency.exponentialRampToValueAtTime(layer.frequency * (action === "edit" ? 0.996 : 1.006), stopAt);

                gain.gain.setValueAtTime(0.0001, startAt);
                gain.gain.exponentialRampToValueAtTime(layer.volume, startAt + 0.018);
                gain.gain.exponentialRampToValueAtTime(0.0001, stopAt);

                oscillator.connect(gain);
                gain.connect(masterGain);
                oscillator.start(startAt);
                oscillator.stop(stopAt + 0.03);
            });

            window.setTimeout(function () {
                speakNotificationAlert(action === "edit" ? "Leave updated" : "Leave applied", {
                    pitch: action === "edit" ? 1.04 : 1.12,
                    rate: action === "edit" ? 0.9 : 0.96
                });
            }, action === "edit" ? 760 : 150);
        } catch (error) {
            // Ignore audio failures silently.
        }
    }

    function playLeaveErrorTone() {
        if (!notificationAudioUnlocked) {
            runWhenNotificationAudioReady(playLeaveErrorTone);
            return;
        }

        const audioContext = getNotificationAudioContext();

        if (!audioContext) {
            return;
        }

        if (audioContext.state === "suspended") {
            runWhenNotificationAudioReady(playLeaveErrorTone);
            return;
        }

        try {
            const now = audioContext.currentTime;
            const layers = [
                { frequency: 440, endFrequency: 260, volume: 0.04, start: 0, duration: 0.46 },
                { frequency: 330, endFrequency: 185, volume: 0.03, start: 0.08, duration: 0.5 },
            ];

            layers.forEach(function (layer) {
                const oscillator = audioContext.createOscillator();
                const gain = audioContext.createGain();
                const startAt = now + layer.start;
                const stopAt = startAt + layer.duration;

                oscillator.type = "sawtooth";
                oscillator.frequency.setValueAtTime(layer.frequency, startAt);
                oscillator.frequency.exponentialRampToValueAtTime(layer.endFrequency, stopAt);

                gain.gain.setValueAtTime(0.0001, startAt);
                gain.gain.exponentialRampToValueAtTime(layer.volume, startAt + 0.025);
                gain.gain.exponentialRampToValueAtTime(0.0001, stopAt);

                oscillator.connect(gain);
                gain.connect(audioContext.destination);
                oscillator.start(startAt);
                oscillator.stop(stopAt + 0.03);
            });
            window.setTimeout(function () {
                speakNotificationAlert("Error", { pitch: 0.78, rate: 0.9 });
            }, 520);
        } catch (error) {
            // Ignore audio failures silently.
        }
    }

    function playDataUpdateTone() {
        if (!notificationAudioUnlocked) {
            runWhenNotificationAudioReady(playDataUpdateTone);
            return;
        }

        const audioContext = getNotificationAudioContext();

        if (!audioContext) {
            return;
        }

        if (audioContext.state === "suspended") {
            runWhenNotificationAudioReady(playDataUpdateTone);
            return;
        }

        try {
            const now = audioContext.currentTime;
            const layers = [
                { frequency: 587, volume: 0.024, start: 0, duration: 0.22 },
                { frequency: 784, volume: 0.028, start: 0.12, duration: 0.34 },
                { frequency: 1175, volume: 0.01, start: 0.18, duration: 0.24 },
            ];

            layers.forEach(function (layer) {
                const oscillator = audioContext.createOscillator();
                const gain = audioContext.createGain();
                const startAt = now + layer.start;
                const stopAt = startAt + layer.duration;

                oscillator.type = "sine";
                oscillator.frequency.setValueAtTime(layer.frequency, startAt);
                oscillator.frequency.exponentialRampToValueAtTime(layer.frequency * 1.004, stopAt);

                gain.gain.setValueAtTime(0.0001, startAt);
                gain.gain.exponentialRampToValueAtTime(layer.volume, startAt + 0.018);
                gain.gain.exponentialRampToValueAtTime(0.0001, stopAt);

                oscillator.connect(gain);
                gain.connect(audioContext.destination);
                oscillator.start(startAt);
                oscillator.stop(stopAt + 0.03);
            });
        } catch (error) {
            // Ignore audio failures silently.
        }
    }

    window.playCommunicationTone = playCommunicationTone;
    window.playDataUpdateTone = playDataUpdateTone;
    window.playHrDecisionTone = function (statusClass) {
        const normalizedStatus = String(statusClass || "").trim().toLowerCase();
        if (normalizedStatus === "approved" || normalizedStatus === "rejected") {
            if (!notificationAudioUnlocked) {
                runWhenNotificationAudioReady(function () {
                    playNotificationTone(normalizedStatus);
                });
                return;
            }

            const audioContext = getNotificationAudioContext();
            if (audioContext && audioContext.state === "suspended") {
                runWhenNotificationAudioReady(function () {
                    playNotificationTone(normalizedStatus);
                });
                return;
            }

            playNotificationTone(normalizedStatus);
        }
    };
    window.playLeaveErrorTone = playLeaveErrorTone;
    window.playLeaveActionTone = playLeaveActionTone;

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
                String(item.reviewer_name || ""),
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

                return typeof window.parseJsonOrSessionExpired === "function" ? window.parseJsonOrSessionExpired(response) : response.json();
            }).then(function (payload) {
                if (payload.sessionExpired) {
                    if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(payload);
                    return payload;
                }
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
                            (isEmployeeDecisionNotification
                                ? '<small class="notification-reviewer-line">Reviewed by ' + escapeHtml(item.reviewer_name || "HR Team") + '</small>'
                                : '') +
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
            const hadFetchedOnce = hasFetchedOnce;
            const previousKnownIds = new Set(knownIds);
            const previousUnreadCount = knownIds.filter(function (id) {
                return !readIds.has(id);
            }).length;
            const previousSignatures = new Map(
                latestNotifications.map(function (item) {
                    return [String(item.id || ""), getNotificationSignature(item)];
                })
            );

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
            const newNotifications = notifications.filter(function (item) {
                const itemId = String(item.id);
                const wasKnown = previousKnownIds.has(itemId);
                const signatureChanged = wasKnown && previousSignatures.get(itemId) !== getNotificationSignature(item);
                return (!wasKnown || signatureChanged) && !item.is_read;
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
            const nextUnreadCount = ids.filter(function (id) {
                return !readIds.has(id);
            }).length;
            updateNewIndicators();
            hasFetchedOnce = true;
            renderNotifications(notifications);
            broadcastNotificationState();
            dropdown.classList.add("is-hydrated");

            if (hadFetchedOnce && (newNotifications.length || nextUnreadCount > previousUnreadCount)) {
                const latestNewNotification = newNotifications[0] || notifications.find(function (item) {
                    return !item.is_read;
                }) || {};
                if (typeof window.armNotificationAudio === "function") {
                    window.armNotificationAudio();
                }
                playNotificationTone(latestNewNotification.status_class || "", latestNewNotification.activity_label || "");
                flashNotificationScreen(latestNewNotification.status_class || "");
            }
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

                    return typeof window.parseJsonOrSessionExpired === "function" ? window.parseJsonOrSessionExpired(response) : response.json();
                })
                .then(function (payload) {
                    if (payload.sessionExpired) {
                        if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(payload);
                        return payload;
                    }
                    handlePayload(payload, requestId, settings);
                    return payload;
                });
        }

        function fetchNotifications(options) {
            const settings = options || {};
            const shouldShowSkeleton =
                dropdown.classList.contains("is-open") &&
                !list.querySelector("[data-notification-id]") &&
                !list.querySelector(".notification-empty");

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
