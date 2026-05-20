document.addEventListener("DOMContentLoaded", function () 
{
    const leaveType = document.querySelector("[name='leave_type']");

    const fromDate = document.querySelector("[name='from_date']");
    const toDate = document.querySelector("[name='to_date']");

    const fromDateTimeDate = document.querySelector("[name='from_datetime_0']");
    const fromDateTimeTime = document.querySelector("[name='from_datetime_1']");

    const toDateTimeDate = document.querySelector("[name='to_datetime_0']");
    const toDateTimeTime = document.querySelector("[name='to_datetime_1']");
    const deductedFrom = document.querySelector("[name='deducted_from']");


    const fromDateRow = document.querySelector(".form-row.field-from_date");
    const toDateRow = document.querySelector(".form-row.field-to_date");

    const fromDT = document.querySelector(".form-row.field-from_datetime");
    const toDT = document.querySelector(".form-row.field-to_datetime");


    function hideAll()
    {
        fromDateRow.style.display = "none";
        toDateRow.style.display = "none";
        fromDT.style.display = "none";
        toDT.style.display = "none";
    }


    function handleUI()
    {
        const type = leaveType.value;

        // ❌ No type
        if (!type)
        {
            hideAll();
            return;
        }

        // ⏱ Short / Half → only datetime
        if (type === "Short" || type === "Half")
        {
            fromDateRow.style.display = "none";
            toDateRow.style.display = "none";

            fromDT.style.display = "block";
            toDT.style.display = "block";
        }

        // 📅 Others → only date + auto time
        else
        {
            fromDateRow.style.display = "block";
            toDateRow.style.display = "block";

            fromDT.style.display = "block";
            toDT.style.display = "block";

            // ⏰ Default time
            fromDateTimeTime.value = "10:00:00";
            toDateTimeTime.value = "19:00:00";
        }

        syncDeductedFrom();
    }

    function syncDeductedFrom()
    {
        if (!deductedFrom || !leaveType) return;

        const type = leaveType.value;
        if (type === "Sick" || type === "Earned" || type === "Unpaid")
        {
            deductedFrom.value = type;
            return;
        }

        if ((type === "Short" || type === "Half") && !deductedFrom.value)
        {
            deductedFrom.value = "Earned";
        }
    }

    function syncfrom()
    {
        const type = leaveType.value;

        if (!type) return;

        if (type === "Unpaid" || type === "Sick" || type === "Earned")
        {
            if (fromDate.value)
            {
                const val = fromDate.value;

                fromDateTimeDate.value = val;
                fromDateTimeTime.value = "10:00:00";
                toDateTimeTime.value = "19:00:00";
            }
        }

        else if (type === "Short" || type === "Half")
        {
            if (fromDate.value)
            {
                const val = fromDate.value;
                fromDateTimeDate.value = val;
            }
        }
    }


    function syncto()
    {
        const type = leaveType.value;

        if (!type) return;

        if (type === "Unpaid" || type === "Sick" || type === "Earned")
        {
            if (toDate.value)
            {
                const val = toDate.value;

                toDateTimeDate.value = val;
                fromDateTimeTime.value = "10:00:00";
                toDateTimeTime.value = "19:00:00";
            }
        }

        else if (type === "Short" || type === "Half")
        {
            if (fromDate.value)
            {
                const val = fromDate.value;
                toDateTimeDate.value = val;
                toDate.value = val;
                autoSetLeaveDuration(); 
            }
        }
    }


    // 🎯 EVENTS
    leaveType.addEventListener("change", handleUI);
    leaveType.addEventListener("change", syncDeductedFrom);

    // 🔥 RUN ON CHANGE
    fromDate.addEventListener("change", syncfrom);
    toDate.addEventListener("change", syncto);

    fromDateTimeDate.addEventListener("change", syncfrom);
    toDateTimeDate.addEventListener("change", syncto);


    setInterval(syncfrom, 300);
    setInterval(syncto, 300);


    // 🚀 INIT
    handleUI();


    
    const statusField = document.querySelector("[name='status']");
    const rejectionRow = document.querySelector(".form-row.field-rejection_reason");

    function toggleRejectionField()
    {
        if (!statusField || !rejectionRow) return;

        if (statusField.value === "Rejected")
        {
            rejectionRow.style.display = "block";
        }
        else
        {
            rejectionRow.style.display = "none";

            const rejection = document.querySelector("[name='rejection_reason']");
            rejection.value = "";
        }
    }

    statusField.addEventListener("change", toggleRejectionField);
    toggleRejectionField();



    function addHours(timeStr, hoursToAdd)
    {
        if (!timeStr) return "";

        const parts = timeStr.split(":");

        let h = parseInt(parts[0]);
        let m = parseInt(parts[1]);
        let s = parts[2] ? parseInt(parts[2]) : 0;

        let date = new Date();
        date.setHours(h, m, s);

        date.setHours(date.getHours() + hoursToAdd);

        const hh = String(date.getHours()).padStart(2, "0");
        const mm = String(date.getMinutes()).padStart(2, "0");
        const ss = String(date.getSeconds()).padStart(2, "0");

        return `${hh}:${mm}:${ss}`;
    }


    function autoSetLeaveDuration()
    {
        const type = leaveType.value;

        if (!fromDateTimeTime.value) return;

        if (type === "Short")
        {
            toDateTimeTime.value = addHours(fromDateTimeTime.value, 2);
        }

        else if (type === "Half")
        {
            toDateTimeTime.value = addHours(fromDateTimeTime.value, 4);
        }
    }

    const checker = document.querySelector("[data-admin-leave-conflict-checker]");
    if (checker)
    {
        const form = Array.from(document.querySelectorAll("form")).find(function (candidate) {
            return candidate.querySelector("[name='leave_type']");
        }) || checker.closest("form") || document.getElementById("leave_form");
        const checkButton = checker.querySelector("[data-admin-conflict-check]");
        const applyButton = checker.querySelector("[data-admin-conflict-apply]");
        const resultBox = checker.querySelector("[data-admin-conflict-result]");
        const state = checker.querySelector("[data-admin-conflict-state]");
        const tokenInput = document.querySelector("[name='admin_conflict_preview_token']");
        const decisionInput = document.querySelector("[name='admin_conflict_preview_decision']");
        let lastPreview = null;

        function escapeHtml(value)
        {
            return String(value || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
        }

        function getCookie(name)
        {
            const cookie = document.cookie.split(";").map(function (part) { return part.trim(); }).find(function (part) {
                return part.startsWith(name + "=");
            });
            return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
        }

        function getCsrfToken()
        {
            const input = form ? form.querySelector("[name='csrfmiddlewaretoken']") : null;
            return input && input.value ? input.value : getCookie("csrftoken");
        }

        function clearPreview()
        {
            lastPreview = null;
            if (tokenInput) tokenInput.value = "";
            if (decisionInput) decisionInput.value = "";
            if (state) state.textContent = "Preview not checked after latest field change.";
            if (applyButton) applyButton.style.display = "none";
        }

        function listHtml(items, emptyText)
        {
            if (!items || !items.length)
            {
                return "<p>" + escapeHtml(emptyText) + "</p>";
            }
            return "<ul class='admin-conflict-list'>" + items.map(function (item) {
                return "<li>" + escapeHtml(item) + "</li>";
            }).join("") + "</ul>";
        }

        function renderPreview(preview)
        {
            const status = preview.status || "safe";
            const decisionValue = status === "safe" ? "reviewed" : "override";
            const decisionText = status === "safe"
                ? "I reviewed this preview and want to save."
                : "I understand the warnings/conflicts and want to override.";
            const requested = preview.requested_range || {};
            const effective = preview.effective_range || {};
            const breakdown = preview.breakdown || {};
            const currentBalance = preview.current_balance || {};
            const expectedBalance = preview.expected_balance || {};
            const rangeChanged = requested.from !== effective.from || requested.to !== effective.to;

            resultBox.className = "admin-conflict-result is-visible " + status;
            resultBox.innerHTML = [
                "<h3>Preview status: " + escapeHtml(status.toUpperCase()) + "</h3>",
                "<div class='admin-conflict-grid'>",
                    "<div class='admin-conflict-card'><strong>Requested range</strong>" + escapeHtml(requested.from || "-") + " to " + escapeHtml(requested.to || "-") + "</div>",
                    "<div class='admin-conflict-card'><strong>Effective range</strong>" + escapeHtml(effective.from || "-") + " to " + escapeHtml(effective.to || "-") + "</div>",
                    "<div class='admin-conflict-card'><strong>WFH bridge mode</strong>" + escapeHtml(preview.admin_skip_wfh_bridge ? "Admin bypass selected" : "Employee-style auto expansion") + "</div>",
                    "<div class='admin-conflict-card'><strong>Working days / value</strong>" + escapeHtml(breakdown.working_days ?? "-") + "</div>",
                    "<div class='admin-conflict-card'><strong>WFH bridge dates</strong>" + escapeHtml((preview.auto_added_dates || []).join(", ") || "None") + "</div>",
                    "<div class='admin-conflict-card'><strong>Weekend days</strong>" + escapeHtml(breakdown.weekend_days ?? 0) + "</div>",
                    "<div class='admin-conflict-card'><strong>Company holidays</strong>" + escapeHtml(breakdown.company_holiday_days ?? 0) + "</div>",
                    "<div class='admin-conflict-card'><strong>Current balance</strong>Total remaining: " + escapeHtml(currentBalance.total_leave_remaining ?? "-") + " | Sick remaining: " + escapeHtml(currentBalance.sick_remaining ?? "-") + " | Sick used: " + escapeHtml(currentBalance.sick_used ?? "-") + " | Earned remaining: " + escapeHtml(currentBalance.earned_remaining ?? "-") + " | Earned used: " + escapeHtml(currentBalance.earned_used ?? "-") + " | Unpaid: " + escapeHtml(currentBalance.unpaid ?? "-") + "</div>",
                    "<div class='admin-conflict-card'><strong>Expected balance</strong>Total remaining: " + escapeHtml(expectedBalance.total_leave_remaining ?? "-") + " | Sick remaining: " + escapeHtml(expectedBalance.sick_remaining ?? "-") + " | Sick used: " + escapeHtml(expectedBalance.sick_used ?? "-") + " | Earned remaining: " + escapeHtml(expectedBalance.earned_remaining ?? "-") + " | Earned used: " + escapeHtml(expectedBalance.earned_used ?? "-") + " | Unpaid: " + escapeHtml(expectedBalance.unpaid ?? "-") + "</div>",
                "</div>",
                "<h4>Warnings</h4>",
                listHtml(preview.warnings, "No warnings."),
                "<h4>Conflicts</h4>",
                listHtml(preview.conflicts, "No conflicts."),
                "<div class='admin-conflict-decision'><label><input type='checkbox' data-admin-conflict-decision value='" + decisionValue + "'> " + escapeHtml(decisionText) + "</label></div>"
            ].join("");

            if (applyButton)
            {
                applyButton.style.display = rangeChanged ? "" : "none";
            }

            const checkbox = resultBox.querySelector("[data-admin-conflict-decision]");
            checkbox.addEventListener("change", function () {
                if (decisionInput) decisionInput.value = checkbox.checked ? checkbox.value : "";
                if (state) state.textContent = checkbox.checked ? "Preview decision confirmed. Save is allowed." : "Confirm preview decision before saving.";
            });
        }

        function runPreview()
        {
            if (!form || !checkButton) return;

            const formData = new FormData(form);
            formData.append("object_id", checker.dataset.objectId || "");
            checkButton.disabled = true;
            if (state) state.textContent = "Checking...";

            fetch(checker.dataset.previewUrl, {
                method: "POST",
                body: formData,
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
                .then(function (response) {
                    return response.json().then(function (payload) {
                        if (!response.ok || !payload.success) throw new Error(payload.error || "Preview failed.");
                        return payload;
                    });
                })
                .then(function (payload) {
                    lastPreview = payload.preview;
                    if (tokenInput) tokenInput.value = lastPreview.token || "";
                    if (decisionInput) decisionInput.value = "";
                    if (state) state.textContent = "Preview checked. Confirm decision below.";
                    renderPreview(lastPreview);
                })
                .catch(function (error) {
                    clearPreview();
                    resultBox.className = "admin-conflict-result is-visible conflict";
                    resultBox.innerHTML = "<p class='admin-conflict-error'>" + escapeHtml(error.message || "Preview failed.") + "</p>";
                })
                .finally(function () {
                    checkButton.disabled = false;
                });
        }

        function setInputValue(selector, value)
        {
            const input = document.querySelector(selector);
            if (input) input.value = value || "";
        }

        checkButton.addEventListener("click", runPreview);

        if (applyButton)
        {
            applyButton.addEventListener("click", function () {
                if (!lastPreview || !lastPreview.effective_datetime) return;
                const effective = lastPreview.effective_datetime;
                const requested = lastPreview.requested_range || {};
                setInputValue("[name='requested_from_date']", requested.from);
                setInputValue("[name='requested_to_date']", requested.to);
                setInputValue("[name='from_date']", effective.from_date);
                setInputValue("[name='to_date']", effective.to_date);
                setInputValue("[name='from_datetime_0']", effective.from_date);
                setInputValue("[name='to_datetime_0']", effective.to_date);
                setInputValue("[name='from_datetime_1']", effective.from_time);
                setInputValue("[name='to_datetime_1']", effective.to_time);
                clearPreview();
                runPreview();
            });
        }

        [
            "[name='user']",
            "[name='leave_type']",
            "[name='status']",
            "[name='deducted_from']",
            "[name='reason']",
            "[name='rejection_reason']",
            "[name='admin_skip_wfh_bridge']",
            "[name='from_date']",
            "[name='to_date']",
            "[name='from_datetime_0']",
            "[name='from_datetime_1']",
            "[name='to_datetime_0']",
            "[name='to_datetime_1']"
        ].forEach(function (selector) {
            const input = document.querySelector(selector);
            if (input)
            {
                input.addEventListener("change", clearPreview);
                input.addEventListener("input", clearPreview);
            }
        });

        if (form)
        {
            form.addEventListener("submit", function (event) {
                const submitter = event.submitter;
                if (submitter && submitter.name === "_saveasnew") return;
                if (!tokenInput || !tokenInput.value || !decisionInput || !decisionInput.value)
                {
                    event.preventDefault();
                    if (state) state.textContent = "Run preview and confirm decision before saving.";
                    resultBox.className = "admin-conflict-result is-visible conflict";
                    resultBox.innerHTML = "<p class='admin-conflict-error'>Run admin conflict/impact preview and confirm the decision before saving.</p>";
                    checker.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            });
        }
    }
});
