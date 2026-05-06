(function () {
    "use strict";

    const currentScript = document.currentScript;
    const targetUrl = currentScript && currentScript.dataset.targetUrl
        ? currentScript.dataset.targetUrl
        : "/";
    const navigationEntry = window.performance && window.performance.getEntriesByType
        ? window.performance.getEntriesByType("navigation")[0]
        : null;
    const legacyNavigation = window.performance && window.performance.navigation
        ? window.performance.navigation.type
        : null;
    const isHistoryNavigation = (navigationEntry && navigationEntry.type === "back_forward")
        || legacyNavigation === 2;

    if (isHistoryNavigation) {
        window.location.replace(targetUrl);
    }
}());
