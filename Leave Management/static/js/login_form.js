(function () {
    "use strict";

    document.querySelectorAll("[data-password-toggle]").forEach(function (toggleButton) {
        const input = toggleButton.parentElement
            ? toggleButton.parentElement.querySelector("input")
            : null;
        const label = toggleButton.querySelector("[data-password-toggle-label]");
        const openIcon = toggleButton.querySelector("[data-eye-open]");
        const closedIcon = toggleButton.querySelector("[data-eye-closed]");

        if (!input) return;

        toggleButton.addEventListener("click", function () {
            const isPassword = input.type === "password";
            input.type = isPassword ? "text" : "password";
            if (label) {
                label.textContent = isPassword ? "Hide" : "Show";
            }
            if (openIcon && closedIcon) {
                openIcon.hidden = isPassword;
                closedIcon.hidden = !isPassword;
            }
            toggleButton.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
            toggleButton.blur();
        });
    });

    document.querySelectorAll(".login-form input[type='password']").forEach(function (input) {
        const warning = input.closest(".login-form").querySelector("[data-caps-warning]");
        if (!warning) return;

        input.addEventListener("keyup", function (event) {
            warning.hidden = !event.getModifierState("CapsLock");
        });

        input.addEventListener("keydown", function (event) {
            warning.hidden = !event.getModifierState("CapsLock");
        });

        input.addEventListener("blur", function () {
            warning.hidden = true;
        });
    });

    (function () {
        const input = document.getElementById("hr-password");
        if (!input) return;

        const card = input.closest(".hr-login-card");
        const toast = card ? card.querySelector("[data-caps-toast]") : null;
        if (!toast) return;

        let isWatchingCaps = false;
        let capsLockOn = false;

        function setCapsToast(isCapsOn) {
            capsLockOn = !!isCapsOn;
            toast.hidden = !capsLockOn;
        }

        function inferCapsLockFromKey(event) {
            if (!event || !event.key || event.key.length !== 1) return null;

            const isLetter = (event.key >= "a" && event.key <= "z") || (event.key >= "A" && event.key <= "Z");
            if (!isLetter) return null;

            const isUpper = event.key === event.key.toUpperCase();
            return event.shiftKey ? !isUpper : isUpper;
        }

        function updateCapsWarning(event) {
            if (!isWatchingCaps) return;

            if (event && typeof event.getModifierState === "function") {
                setCapsToast(event.getModifierState("CapsLock"));
                return;
            }

            const inferred = inferCapsLockFromKey(event);
            if (inferred !== null) {
                setCapsToast(inferred);
            }
        }

        input.addEventListener("focus", function () {
            isWatchingCaps = true;
            setCapsToast(false);
        });

        input.addEventListener("blur", function () {
            isWatchingCaps = false;
            setCapsToast(false);
        });

        input.addEventListener("keydown", updateCapsWarning);
        input.addEventListener("keyup", updateCapsWarning);

        document.addEventListener("keydown", function (event) {
            if (!isWatchingCaps) return;

            if (event.key === "CapsLock") {
                setCapsToast(!capsLockOn);
                return;
            }

            updateCapsWarning(event);
        });

        document.addEventListener("keyup", updateCapsWarning);

        window.addEventListener("blur", function () {
            isWatchingCaps = false;
            setCapsToast(false);
        });
    }());

    document.querySelectorAll(".login-form, .hr-form").forEach(function (form) {
        const card = form.closest(".admin-login-card, .login-card, .hr-login-card");
        const feedback = card ? card.querySelector("[data-login-feedback]") : null;
        if (!feedback) return;

        function hideFeedback() {
            const visibleItems = Array.from(feedback.querySelectorAll("[data-login-feedback-item]")).filter(function (item) {
                return item.style.display !== "none";
            });

            if (visibleItems.length === 0) {
                feedback.hidden = true;
                feedback.style.display = "none";
                feedback.setAttribute("aria-hidden", "true");
            }
        }

        form.querySelectorAll("input[name='username'], input[name='password']").forEach(function (input) {
            input.addEventListener("input", function () {
                const fieldName = input.name;

                feedback.querySelectorAll("[data-login-feedback-item]").forEach(function (item) {
                    if (item.dataset.clearOn === fieldName) {
                        item.hidden = true;
                        item.style.display = "none";
                        item.setAttribute("aria-hidden", "true");
                    }
                });

                hideFeedback();
            });
        });
    });
}());
