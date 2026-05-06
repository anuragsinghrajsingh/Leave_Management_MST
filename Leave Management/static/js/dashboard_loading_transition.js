(function () {
    "use strict";

    const config = document.body ? document.body.dataset : {};
    const duration = Number.parseInt(config.duration || "0", 10);
    const targetUrl = config.targetUrl || "/";
    const targetPercent = Number.parseInt(config.targetPercent || "100", 10);
    const fill = document.getElementById("progress-fill");
    const value = document.getElementById("progress-value");
    const countdown = document.getElementById("countdown");
    const toastCountdown = document.getElementById("toast-countdown");
    let remaining = Number.isFinite(duration) && duration > 0 ? duration : 0;

    function render() {
        const elapsed = Math.max(0, duration - remaining);
        const percent = duration > 0
            ? Math.min(targetPercent, Math.round((elapsed / duration) * targetPercent))
            : targetPercent;
        const seconds = Math.max(0, remaining);

        if (fill) fill.style.width = percent + "%";
        if (value) value.textContent = percent + "%";
        if (countdown) countdown.textContent = seconds;
        if (toastCountdown) toastCountdown.textContent = seconds;
    }

    render();

    const timer = window.setInterval(function () {
        remaining -= 1;
        render();
        if (remaining <= 0) {
            window.clearInterval(timer);
        }
    }, 1000);

    window.setTimeout(function () {
        window.location.replace(targetUrl);
    }, duration * 1000);
}());
