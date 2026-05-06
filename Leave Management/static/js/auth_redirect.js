(function () {
    "use strict";

    const currentScript = document.currentScript;
    const loginUrl = currentScript && currentScript.dataset.loginUrl
        ? currentScript.dataset.loginUrl
        : "/login/";

    window.location.replace(loginUrl);
}());
