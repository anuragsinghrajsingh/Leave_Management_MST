(function () {
    "use strict";

    const config = document.body ? document.body.dataset : {};
    const duration = Number.parseInt(config.duration || "0", 10);
    const targetUrl = config.targetUrl || "/";
    const roleSelectUrl = "/portal/";
    const countdown = document.getElementById("toast-countdown");
    const progressValue = document.getElementById("progress-value");
    const progressFill = document.getElementById("progress-fill");
    const navigationEntry = window.performance && window.performance.getEntriesByType
        ? window.performance.getEntriesByType("navigation")[0]
        : null;
    const legacyNavigation = window.performance && window.performance.navigation
        ? window.performance.navigation.type
        : null;
    const isHistoryNavigation = (navigationEntry && navigationEntry.type === "back_forward")
        || legacyNavigation === 2;
    let remaining = Number.isFinite(duration) && duration > 0 ? duration : 0;

    if (isHistoryNavigation) {
        window.location.replace(roleSelectUrl);
        return;
    }

    function updateProgress() {
        const completed = Math.max(0, duration - remaining);
        const rawPercent = duration > 0 ? Math.round((completed / duration) * 100) : 100;
        const visiblePercent = Math.min(100, Math.max(8, rawPercent || 8));

        if (progressValue) {
            progressValue.textContent = visiblePercent + "%";
        }

        if (progressFill) {
            progressFill.style.width = visiblePercent + "%";
        }

        if (countdown) {
            countdown.textContent = remaining > 0 ? remaining : 0;
        }
    }

    function goNext() {
        window.location.replace(targetUrl);
    }

    if (window.history && window.history.replaceState) {
        window.history.replaceState({ loader: true }, "", window.location.href);
    }

    updateProgress();

    const interval = window.setInterval(function () {
        remaining -= 1;
        updateProgress();

        if (remaining <= 0) {
            window.clearInterval(interval);
        }
    }, 1000);

    window.setTimeout(goNext, duration * 1000);

    window.addEventListener("pageshow", function (event) {
        if (event.persisted) {
            goNext();
        }
    });
}());
