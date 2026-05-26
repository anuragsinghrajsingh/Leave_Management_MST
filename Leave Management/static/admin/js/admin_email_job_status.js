(function () {
    "use strict";

    const terminalStatuses = new Set(["completed", "completed_with_failures", "failed"]);

    function text(value) {
        return value === null || value === undefined || value === "" ? "-" : String(value);
    }

    function setText(root, selector, value) {
        const element = root.querySelector(selector);
        if (element) {
            element.textContent = text(value);
        }
    }

    function statusClass(status) {
        return "admin-email-job-status--" + String(status || "unknown").replace(/[^a-z0-9_-]/gi, "-").toLowerCase();
    }

    function renderItems(root, items) {
        const tbody = root.querySelector("[data-admin-email-job-items]");
        if (!tbody) {
            return;
        }

        if (!items || !items.length) {
            tbody.innerHTML = '<tr><td colspan="5">No users in this job.</td></tr>';
            return;
        }

        tbody.innerHTML = items.map(function (item) {
            const user = text(item.user);
            const username = item.username ? " (" + text(item.username) + ")" : "";
            return [
                "<tr>",
                "<td>", escapeHtml(user + username), "</td>",
                "<td>", escapeHtml(item.email), "</td>",
                '<td><span class="admin-email-job-row-status ', statusClass(item.status), '">',
                escapeHtml(item.status_label || item.status),
                "</span></td>",
                "<td>", escapeHtml(item.message), "</td>",
                "<td>", escapeHtml(item.finished_at), "</td>",
                "</tr>",
            ].join("");
        }).join("");
    }

    function escapeHtml(value) {
        return text(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function updatePanel(root, data) {
        const status = root.querySelector("[data-admin-email-job-status]");
        if (status) {
            status.className = "admin-email-job-live__badge " + statusClass(data.status);
            status.textContent = text(data.status_label || data.status);
        }

        root.querySelectorAll("[data-admin-email-job-count]").forEach(function (element) {
            const key = element.getAttribute("data-admin-email-job-count");
            element.textContent = text(data[key] || 0);
        });

        setText(root, "[data-admin-email-job-updated]", "Last checked now. Started: " + text(data.started_at) + " | Finished: " + text(data.finished_at));
        renderItems(root, data.items || []);
    }

    function startPolling(root) {
        const url = root.getAttribute("data-admin-email-job-status-url");
        const pollMs = parseInt(root.getAttribute("data-admin-email-job-poll-ms") || "3000", 10);
        const initialStatus = root.getAttribute("data-admin-email-job-initial-status") || "";
        const reloadKey = "admin-email-job-final-reload:" + window.location.pathname;
        let stopped = false;

        function poll() {
            if (stopped || !url) {
                return;
            }

            fetch(url, {
                credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Status request failed");
                    }
                    return response.json();
                })
                .then(function (data) {
                    updatePanel(root, data);
                    if (terminalStatuses.has(data.status)) {
                        stopped = true;
                        if (!terminalStatuses.has(initialStatus) && window.sessionStorage.getItem(reloadKey) !== data.status) {
                            window.sessionStorage.setItem(reloadKey, data.status);
                            window.setTimeout(function () {
                                window.location.reload();
                            }, 800);
                        }
                        return;
                    }
                    window.setTimeout(poll, pollMs);
                })
                .catch(function () {
                    setText(root, "[data-admin-email-job-updated]", "Live status temporarily unavailable. Refresh the page for latest data.");
                    window.setTimeout(poll, Math.max(pollMs, 5000));
                });
        }

        poll();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-admin-email-job-status-url]").forEach(startPolling);
    });
}());
