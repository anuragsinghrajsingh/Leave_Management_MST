(function () {
    "use strict";

    const state = {
        config: null,
        registration: null,
        banner: null,
        quickButton: null,
        bannerClosedThisPage: false,
    };

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") || "" : "";
    }

    function isAuthenticated() {
        return document.body && document.body.dataset.authenticated === "true";
    }

    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; i += 1) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    function deviceLabel() {
        const width = window.innerWidth || 0;
        if (/Android/i.test(navigator.userAgent)) return "Android";
        if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) return "iOS";
        if (/Mac/i.test(navigator.platform || "")) return "Mac";
        if (/Win/i.test(navigator.platform || "")) return "Windows";
        return width < 768 ? "Mobile browser" : "Desktop browser";
    }

    function hideBanner() {
        if (state.banner) {
            state.banner.remove();
            state.banner = null;
        }
    }

    function buildQuickButton() {
        if (state.quickButton || Notification.permission !== "default") return;

        const button = document.createElement("button");
        button.type = "button";
        button.className = "push-quick-enable";
        button.textContent = "Enable notifications";
        button.addEventListener("click", enablePush);
        document.body.appendChild(button);
        state.quickButton = button;
    }

    function removeQuickButton() {
        if (state.quickButton) {
            state.quickButton.remove();
            state.quickButton = null;
        }
    }

    function buildBanner() {
        if (state.banner || Notification.permission !== "default") return;

        const banner = document.createElement("div");
        banner.className = "push-enable-banner";
        banner.innerHTML = [
            '<div class="push-enable-copy">',
            "<strong>Enable notifications</strong>",
            "<span>Get leave, message, and announcement alerts on this device.</span>",
            "</div>",
            '<div class="push-enable-actions">',
            '<button type="button" class="push-enable-btn" data-push-enable>Enable</button>',
            '<button type="button" class="push-dismiss-btn" data-push-dismiss aria-label="Dismiss notification prompt">&times;</button>',
            "</div>",
        ].join("");

        banner.querySelector("[data-push-enable]").addEventListener("click", enablePush);
        banner.querySelector("[data-push-dismiss]").addEventListener("click", function () {
            state.bannerClosedThisPage = true;
            hideBanner();
            buildQuickButton();
        });

        document.body.appendChild(banner);
        state.banner = banner;
    }

    function showStatus(message, isError) {
        if (!state.banner) return;
        const copy = state.banner.querySelector(".push-enable-copy span");
        if (copy) copy.textContent = message;
        state.banner.classList.toggle("is-error", !!isError);
    }

    function postJson(url, payload) {
        return fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
                "X-Requested-With": "XMLHttpRequest",
            },
            credentials: "same-origin",
            body: JSON.stringify(payload || {}),
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("Request failed.");
            }
            return response.json();
        });
    }

    function saveSubscription(subscription) {
        const json = subscription.toJSON();
        return postJson(state.config.subscribeUrl, {
            endpoint: json.endpoint,
            keys: json.keys,
            browser: navigator.userAgent,
            deviceLabel: deviceLabel(),
        });
    }

    function sendTestNotification() {
        return postJson(state.config.testUrl, {}).catch(function () {
            return null;
        });
    }

    function enablePush() {
        if (!state.config || !state.registration) return;

        showStatus("Opening browser permission...", false);
        Notification.requestPermission().then(function (permission) {
            if (permission !== "granted") {
                showStatus("Notifications were not enabled in the browser.", true);
                return null;
            }

            return state.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(state.config.publicKey),
            });
        }).then(function (subscription) {
            if (!subscription) return null;
            showStatus("Saving this device...", false);
            return saveSubscription(subscription);
        }).then(function (result) {
            if (!result) return;
            showStatus("Notifications enabled on this device.", false);
            removeQuickButton();
            sendTestNotification();
            window.setTimeout(function () {
                hideBanner();
            }, 1800);
        }).catch(function () {
            showStatus("Could not enable notifications. Check browser permission and VAPID keys.", true);
        });
    }

    function init() {
        if (!isAuthenticated()) return;
        if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return;
        if (window.location.protocol !== "https:" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") return;

        fetch("/api/push/config/", {
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
        }).then(function (response) {
            return response.ok ? response.json() : null;
        }).then(function (config) {
            if (!config || !config.enabled || !config.publicKey) return null;
            state.config = config;
            return navigator.serviceWorker.register("/service-worker.js");
        }).then(function (registration) {
            if (!registration) return;
            state.registration = registration;
            return registration.pushManager.getSubscription();
        }).then(function (subscription) {
            if (subscription) {
                removeQuickButton();
                saveSubscription(subscription).catch(function () {});
                return;
            }
            if (Notification.permission === "default") {
                buildQuickButton();
                if (!state.bannerClosedThisPage) {
                    buildBanner();
                }
            }
        }).catch(function () {});
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
}());
