(function () {
    "use strict";

    function callGlobal(name, args) {
        const fn = window[name];
        if (typeof fn === "function") {
            return fn.apply(window, args || []);
        }
        return undefined;
    }

    function shouldHandleKeyboardClick(event) {
        return event.key === "Enter" || event.key === " ";
    }

    function getActionElement(target) {
        return target && target.closest ? target.closest("[data-action]") : null;
    }

    function sanitizeHTML(html) {
        const template = document.createElement("template");
        template.innerHTML = String(html || "");

        template.content.querySelectorAll("script, iframe, object, embed, base, meta").forEach(function (node) {
            node.remove();
        });

        template.content.querySelectorAll("*").forEach(function (node) {
            Array.from(node.attributes).forEach(function (attribute) {
                const name = attribute.name.toLowerCase();
                const value = String(attribute.value || "").trim().toLowerCase();

                if (name.startsWith("on") || name === "srcdoc") {
                    node.removeAttribute(attribute.name);
                    return;
                }

                if (
                    (name === "href" || name === "src" || name === "action" || name === "formaction" || name === "xlink:href") &&
                    (value.startsWith("javascript:") || value.startsWith("vbscript:"))
                ) {
                    node.removeAttribute(attribute.name);
                }
            });
        });

        return template.content;
    }

    window.setSafeHTML = function (target, html) {
        if (!target) return;
        target.replaceChildren(sanitizeHTML(html));
    };

    document.addEventListener("click", function (event) {
        const actionElement = getActionElement(event.target);
        if (!actionElement) return;

        const action = actionElement.dataset.action;

        if (actionElement.tagName === "A" && actionElement.getAttribute("href") === "#") {
            event.preventDefault();
        }

        switch (action) {
            case "close-modal":
                event.preventDefault();
                callGlobal("closeModal");
                break;

            case "dashboard-prev-page":
                event.preventDefault();
                callGlobal("prevPage");
                break;

            case "dashboard-next-page":
                event.preventDefault();
                callGlobal("nextPage");
                break;

            case "close-reason-modal":
                event.preventDefault();
                callGlobal("closeReasonModal");
                break;

            case "open-reject":
                event.preventDefault();
                callGlobal("openReject", [actionElement.dataset.leaveId]);
                break;

            case "close-reject":
                event.preventDefault();
                callGlobal("closeReject");
                break;

            case "close-decision-confirm":
                event.preventDefault();
                callGlobal("closeDecisionConfirm", [actionElement.dataset.refresh === "true"]);
                break;

            case "close-employee-modal":
                event.preventDefault();
                callGlobal("closeEmployeeModal");
                break;

            case "approve-leave-popup":
                event.preventDefault();
                callGlobal("approveLeaveFromPopup", [actionElement.dataset.leaveId]);
                break;

            case "open-leave-calendar":
                event.preventDefault();
                window.lastModalTrigger = actionElement;
                callGlobal("openLeaveCalendar");
                break;

            case "open-filter-modal":
                event.preventDefault();
                window.lastModalTrigger = actionElement;
                callGlobal("openFilterModal", [actionElement.dataset.status]);
                break;

            case "close-calendar-detail":
                event.preventDefault();
                callGlobal("closeCalendarDetail");
                break;

            case "open-edit-leave":
                event.preventDefault();
                window.lastModalTrigger = actionElement;
                callGlobal("openEditLeave", [actionElement]);
                break;

            case "open-reason-modal":
                event.preventDefault();
                callGlobal("openReasonModal", [actionElement]);
                break;

            case "open-password-modal":
                event.preventDefault();
                callGlobal("openPasswordModal");
                break;

            case "edit-profile-field":
                event.preventDefault();
                callGlobal("editField", [actionElement.dataset.field]);
                break;

            case "close-view-photo":
                event.preventDefault();
                callGlobal("closeViewPhoto");
                break;

            case "close-edit-photo":
                event.preventDefault();
                callGlobal("closeEditPhoto");
                break;

            case "reset-editor":
                event.preventDefault();
                callGlobal("resetEditor");
                break;

            case "zoom-out":
                event.preventDefault();
                callGlobal("zoomOut");
                break;

            case "zoom-in":
                event.preventDefault();
                callGlobal("zoomIn");
                break;

            case "reset-zoom":
                event.preventDefault();
                callGlobal("resetZoom");
                break;

            case "rotate-image":
                event.preventDefault();
                callGlobal("rotateImage");
                break;

            case "save-cropped-image":
                event.preventDefault();
                callGlobal("saveCroppedImage");
                break;

            case "close-password-modal":
                event.preventDefault();
                callGlobal("closePasswordModal");
                break;

            case "toggle-password":
                event.preventDefault();
                callGlobal("togglePassword", [actionElement]);
                break;

            case "clear-password":
                event.preventDefault();
                callGlobal("clearPassword", [actionElement]);
                break;

            default:
                break;
        }
    });

    document.addEventListener("mouseover", function (event) {
        const actionElement = getActionElement(event.target);
        if (!actionElement || actionElement.dataset.action !== "activate-line") return;
        if (event.relatedTarget && actionElement.contains(event.relatedTarget)) return;

        callGlobal("activateLine", [actionElement]);
    });

    document.addEventListener("keydown", function (event) {
        const actionElement = getActionElement(event.target);
        if (!actionElement) return;

        const editableTarget = event.target && event.target.closest
            ? event.target.closest("input, textarea, select, [contenteditable='true']")
            : null;

        if (editableTarget) return;

        if (actionElement.dataset.action === "edit-photo-key") {
            callGlobal("handleEditPhotoKey", [event]);
            return;
        }

        if (!shouldHandleKeyboardClick(event)) return;

        const tagName = actionElement.tagName;
        if (tagName === "BUTTON" || tagName === "A") return;

        event.preventDefault();
        actionElement.click();
    });

    document.addEventListener("input", function (event) {
        const actionElement = getActionElement(event.target);
        if (!actionElement || actionElement.dataset.action !== "count-words") return;

        callGlobal("countWords");
    });

    document.addEventListener("click", async function (event) {
        const confirmElement = event.target && event.target.closest
            ? event.target.closest("[data-confirm-click]")
            : null;
        if (!confirmElement) return;

        if (confirmElement.dataset.themeConfirmPassed === "true") {
            delete confirmElement.dataset.themeConfirmPassed;
            return;
        }

        event.preventDefault();
        event.stopImmediatePropagation();
        const message = confirmElement.dataset.confirmClick || "Are you sure?";
        const confirmed = typeof window.showThemeConfirm === "function"
            ? await window.showThemeConfirm(message, {
                title: message.toLowerCase().includes("delete") ? "Delete leave" : "Confirm action",
                confirmText: message.toLowerCase().includes("delete") ? "Delete" : "Confirm",
                variant: message.toLowerCase().includes("delete") ? "delete" : "confirm"
            })
            : window.confirm(message);
        if (!confirmed) {
            return;
        }

        confirmElement.dataset.themeConfirmPassed = "true";
        confirmElement.click();
    }, true);

    document.addEventListener("submit", async function (event) {
        const form = event.target;
        if (!form || !form.matches || !form.matches("[data-confirm-submit]")) return;

        if (form.dataset.themeConfirmPassed === "true") {
            delete form.dataset.themeConfirmPassed;
            return;
        }

        event.preventDefault();
        event.stopImmediatePropagation();
        const message = form.dataset.confirmSubmit || "Are you sure?";
        const confirmed = typeof window.showThemeConfirm === "function"
            ? await window.showThemeConfirm(message, {
                title: message.toLowerCase().includes("delete") ? "Delete leave" : "Confirm action",
                confirmText: message.toLowerCase().includes("delete") ? "Delete" : "Confirm",
                variant: message.toLowerCase().includes("delete") ? "delete" : "confirm"
            })
            : window.confirm(message);
        if (!confirmed) {
            return;
        }

        form.dataset.themeConfirmPassed = "true";
        if (typeof form.requestSubmit === "function") {
            form.requestSubmit(event.submitter || undefined);
        }
        else {
            form.submit();
        }
    }, true);
}());
