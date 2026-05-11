(function () {
    "use strict";

    const reportSearchInput = document.getElementById("reportSearch");
    const reportTableBody = document.getElementById("reportTableBody");
    const reportSearchEmpty = document.getElementById("reportSearchEmpty");
    const visibleReportCount = document.getElementById("visibleReportCount");
    const visibleReportCountToolbar = document.getElementById("visibleReportCountToolbar");
    const visibleReportCountMobile = document.getElementById("visibleReportCountMobile");
    const employeesShownCount = document.getElementById("employeesShownCount");
    const reportTotalRequests = document.getElementById("reportTotalRequests");
    const reportApprovedTotal = document.getElementById("reportApprovedTotal");
    const reportPendingTotal = document.getElementById("reportPendingTotal");
    const reportRejectedTotal = document.getElementById("reportRejectedTotal");
    const reportApprovalRateCopy = document.getElementById("reportApprovalRateCopy");
    const reportActionQueue = document.getElementById("reportActionQueue");
    const reportActionQueueValue = document.getElementById("reportActionQueueValue");
    const reportCoverage = document.getElementById("reportCoverage");
    const reportCoverageValue = document.getElementById("reportCoverageValue");
    const reportDecisionQuality = document.getElementById("reportDecisionQuality");
    const reportDecisionQualityValue = document.getElementById("reportDecisionQualityValue");
    const employeeFilterDropdown = document.getElementById("employeeFilterDropdown");
    const employeeFilterSelect = document.getElementById("employeeFilter");
    const employeeFilterTrigger = document.getElementById("employeeFilterTrigger");
    const employeeFilterMenu = document.getElementById("employeeFilterMenu");
    const employeeFilterValue = employeeFilterTrigger ? employeeFilterTrigger.querySelector(".custom-select-value") : null;
    const employeeFilterOptions = employeeFilterMenu ? Array.from(employeeFilterMenu.querySelectorAll(".custom-option")) : [];
    const reportFilterForm = document.querySelector(".report-filter-form");
    const reportTablePanel = document.getElementById("reportTablePanel");
    const reportTablePagination = document.getElementById("reportTablePagination");
    const reportApplyButton = reportFilterForm ? reportFilterForm.querySelector('button[type="submit"]') : null;

    let activeFilterValue = employeeFilterSelect ? employeeFilterSelect.value : "";
    let reportCurrentPage = 1;
    const reportRowsPerPage = 5;

    function syncApplyButton() {
        if (!reportApplyButton || !employeeFilterSelect) return;

        const isChanged = employeeFilterSelect.value !== activeFilterValue;
        reportApplyButton.disabled = !isChanged;
    }

    function runReportSurfaceTransition(surfaceElement, updateFn) {
        if (typeof updateFn !== "function") return;

        if (!surfaceElement || typeof window.startAsyncSurfaceSkeleton !== "function" || typeof window.finishAsyncSurfaceSkeleton !== "function") {
            updateFn();
            return;
        }

        window.startAsyncSurfaceSkeleton(surfaceElement);

        requestAnimationFrame(function () {
            updateFn();

            requestAnimationFrame(function () {
                window.finishAsyncSurfaceSkeleton(surfaceElement);
            });
        });
    }

    function animateMetric(element, value, options) {
        if (!element) return;

        const safeValue = Number.isFinite(Number(value)) ? Number(value) : 0;
        const config = Object.assign({ duration: 280 }, options || {});
        const suffix = typeof config.suffix === "function" ? config.suffix(safeValue) : (config.suffix || "");
        config.suffix = suffix;
        element.dataset.countupTarget = String(safeValue);
        element.textContent = String(safeValue) + suffix;
        if (typeof window.animateCountUp === "function") {
            window.animateCountUp(element, safeValue, config);
        } else {
            element.textContent = String(safeValue) + suffix;
        }
    }

    function getReportEmployeeSuffix(value) {
        return Number(value) === 1 ? " employee" : " employees";
    }

    function renderReportPagination(matchingRows) {
        if (!reportTablePagination) return;

        const rows = Array.isArray(matchingRows) ? matchingRows : [];
        const totalPages = Math.ceil(rows.length / reportRowsPerPage);

        if (totalPages <= 1) {
            reportTablePagination.hidden = true;
            reportTablePagination.replaceChildren();
            rows.forEach(function (row) {
                row.hidden = false;
            });
            return;
        }

        reportCurrentPage = Math.min(Math.max(1, reportCurrentPage), totalPages);
        const start = (reportCurrentPage - 1) * reportRowsPerPage;
        const end = start + reportRowsPerPage;

        rows.forEach(function (row, index) {
            row.hidden = !(index >= start && index < end);
        });

        reportTablePagination.hidden = false;
        window.setSafeHTML(reportTablePagination, `
            <button type="button" class="report-page-btn" data-report-page-action="first" ${reportCurrentPage === 1 ? "disabled" : ""} aria-label="First page"><span aria-hidden="true">&laquo;</span><span>First</span></button>
            <button type="button" class="report-page-btn" data-report-page-action="prev" ${reportCurrentPage === 1 ? "disabled" : ""} aria-label="Previous page"><span aria-hidden="true">&lsaquo;</span><span>Prev</span></button>
            <span class="report-page-status">Page ${reportCurrentPage} of ${totalPages}</span>
            <button type="button" class="report-page-btn" data-report-page-action="next" ${reportCurrentPage === totalPages ? "disabled" : ""} aria-label="Next page"><span>Next</span><span aria-hidden="true">&rsaquo;</span></button>
            <button type="button" class="report-page-btn" data-report-page-action="last" ${reportCurrentPage === totalPages ? "disabled" : ""} aria-label="Last page"><span>Last</span><span aria-hidden="true">&raquo;</span></button>
        `);
    }

    function filterReportRows(searchValue) {
        if (!reportTableBody) return;

        const query = String(searchValue || "").trim().toLowerCase();
        const rows = Array.from(reportTableBody.querySelectorAll("tr[data-employee-name]"));
        const matchingRows = [];
        let visibleRows = 0;
        let totalRequests = 0;
        let approvedTotal = 0;
        let pendingTotal = 0;
        let rejectedTotal = 0;

        const animateVisibleTableMetrics = function () {
            if (typeof window.animateCountUp !== "function") return;

            rows.forEach(function (row) {
                if (row.hidden) return;

                row.querySelectorAll("[data-countup]").forEach(function (element) {
                    const target = parseFloat(element.dataset.countupTarget || element.textContent || "0");
                    if (!Number.isFinite(target)) return;

                    window.animateCountUp(element, target, { duration: 280 });
                });
            });
        };

        rows.forEach(function (row) {
            const haystack = [
                row.dataset.employeeName || "",
                row.dataset.employeeId || "",
                row.dataset.phone || "",
                row.dataset.department || ""
            ].join(" ");
            const isMatch = !query || haystack.includes(query);
            row.hidden = true;

            if (isMatch) {
                matchingRows.push(row);
                visibleRows += 1;
                totalRequests += parseInt((row.children[1] ? row.children[1].textContent : "0").trim(), 10) || 0;
                approvedTotal += parseInt((row.children[2] ? row.children[2].textContent : "0").trim(), 10) || 0;
                pendingTotal += parseInt((row.children[3] ? row.children[3].textContent : "0").trim(), 10) || 0;
                rejectedTotal += parseInt((row.children[4] ? row.children[4].textContent : "0").trim(), 10) || 0;
            }
        });

        animateMetric(visibleReportCount, visibleRows, { suffix: getReportEmployeeSuffix });
        animateMetric(visibleReportCountToolbar, visibleRows, { suffix: getReportEmployeeSuffix });
        animateMetric(visibleReportCountMobile, visibleRows);
        animateMetric(employeesShownCount, visibleRows);
        animateMetric(reportTotalRequests, totalRequests);
        animateMetric(reportApprovedTotal, approvedTotal);
        animateMetric(reportPendingTotal, pendingTotal);
        animateMetric(reportRejectedTotal, rejectedTotal);

        const approvalRate = totalRequests ? Math.round((approvedTotal / totalRequests) * 100) : 0;
        if (reportApprovalRateCopy) {
            reportApprovalRateCopy.textContent = approvalRate + "% overall approval rate";
        }
        if (reportActionQueue) {
            animateMetric(reportActionQueueValue, pendingTotal);
        }
        if (reportCoverage) {
            animateMetric(reportCoverageValue, visibleRows);
        }
        if (reportDecisionQuality) {
            animateMetric(reportDecisionQualityValue, approvalRate);
        }

        renderReportPagination(matchingRows);
        animateVisibleTableMetrics();

        if (reportSearchEmpty) {
            reportSearchEmpty.hidden = !query || visibleRows !== 0 || rows.length === 0;
        }

        document.dispatchEvent(new CustomEvent("countup:refresh", {
            detail: {
                root: reportTablePanel || document,
                duration: 180
            }
        }));
    }

    function closeEmployeeFilterDropdown() {
        if (!employeeFilterDropdown || !employeeFilterTrigger) return;

        employeeFilterDropdown.classList.remove("open");
        employeeFilterTrigger.setAttribute("aria-expanded", "false");
    }

    function openEmployeeFilterDropdown() {
        if (!employeeFilterDropdown || !employeeFilterTrigger) return;

        employeeFilterDropdown.classList.add("open");
        employeeFilterTrigger.setAttribute("aria-expanded", "true");
    }

    function setEmployeeFilterValue(value, label) {
        if (!employeeFilterSelect || !employeeFilterValue) return;

        employeeFilterSelect.value = value;
        employeeFilterValue.textContent = label;

        employeeFilterOptions.forEach(function (option) {
            option.classList.toggle("selected", option.dataset.value === value);
        });

        syncApplyButton();
    }

    if (reportSearchInput) {
        reportSearchInput.addEventListener("input", function () {
            runReportSurfaceTransition(reportTablePanel, function () {
                reportCurrentPage = 1;
                filterReportRows(reportSearchInput.value);
            });
        });
    }

    if (reportTablePagination) {
        reportTablePagination.addEventListener("click", function (event) {
            const button = event.target.closest("[data-report-page-action]");
            if (!button) return;

            const rows = Array.from(reportTableBody ? reportTableBody.querySelectorAll("tr[data-employee-name]") : []);
            const query = String(reportSearchInput ? reportSearchInput.value : "").trim().toLowerCase();
            const matchingRows = rows.filter(function (row) {
                const haystack = [
                    row.dataset.employeeName || "",
                    row.dataset.employeeId || "",
                    row.dataset.phone || "",
                    row.dataset.department || ""
                ].join(" ");
                return !query || haystack.includes(query);
            });
            const totalPages = Math.max(1, Math.ceil(matchingRows.length / reportRowsPerPage));

            if (button.dataset.reportPageAction === "first") {
                reportCurrentPage = 1;
            } else if (button.dataset.reportPageAction === "prev") {
                reportCurrentPage = Math.max(1, reportCurrentPage - 1);
            } else if (button.dataset.reportPageAction === "next") {
                reportCurrentPage = Math.min(totalPages, reportCurrentPage + 1);
            } else if (button.dataset.reportPageAction === "last") {
                reportCurrentPage = totalPages;
            }

            runReportSurfaceTransition(reportTablePanel, function () {
                filterReportRows(reportSearchInput ? reportSearchInput.value : "");
            });
        });
    }

    if (employeeFilterTrigger) {
        employeeFilterTrigger.addEventListener("click", function () {
            const isOpen = employeeFilterDropdown.classList.contains("open");

            if (isOpen) {
                closeEmployeeFilterDropdown();
            } else {
                openEmployeeFilterDropdown();
            }
        });

        employeeFilterTrigger.addEventListener("keydown", function (event) {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                const isOpen = employeeFilterDropdown.classList.contains("open");
                if (isOpen) {
                    closeEmployeeFilterDropdown();
                } else {
                    openEmployeeFilterDropdown();
                }
            }

            if (event.key === "Escape") {
                closeEmployeeFilterDropdown();
            }
        });
    }

    employeeFilterOptions.forEach(function (option) {
        option.addEventListener("click", function () {
            setEmployeeFilterValue(option.dataset.value || "", option.textContent.trim());
            closeEmployeeFilterDropdown();
        });
    });

    async function fetchAnalytics(url) {
        if (typeof window.startAsyncSurfaceSkeleton === "function") {
            window.startAsyncSurfaceSkeleton(reportTablePanel);
        }

        if (reportApplyButton) reportApplyButton.disabled = true;

        try {
            const response = await fetch(url, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            if (!response.ok) throw new Error("Network response was not ok");

            const data = await response.json();

            if (reportTableBody) {
                window.setSafeHTML(reportTableBody, data.table_html);
            }
            reportCurrentPage = 1;

            const focusTarget = document.getElementById("focusTarget");
            const scopeTargetName = document.getElementById("scopeTargetName");
            const customSelectText = document.querySelector(".custom-select-value");

            if (focusTarget) {
                focusTarget.textContent = data.selected_employee_name_simple;
            }
            if (scopeTargetName) {
                scopeTargetName.textContent = data.selected_employee_name_simple;
            }
            if (customSelectText) {
                customSelectText.textContent = data.selected_employee_name;
            }

            animateMetric(reportTotalRequests, data.metrics.total_requests);
            animateMetric(reportApprovedTotal, data.metrics.approved_total);
            animateMetric(reportPendingTotal, data.metrics.pending_total);
            animateMetric(reportRejectedTotal, data.metrics.rejected_total);
            animateMetric(employeesShownCount, data.metrics.report_employee_count);
            animateMetric(reportCoverageValue, data.metrics.report_employee_count);
            animateMetric(reportActionQueueValue, data.metrics.pending_total);
            animateMetric(reportDecisionQualityValue, data.metrics.approval_rate_overall);

            if (reportApprovalRateCopy) {
                reportApprovalRateCopy.textContent = data.metrics.approval_rate_overall + "% overall approval rate";
            }

            window.history.pushState({ path: url }, "", url);
            filterReportRows(reportSearchInput ? reportSearchInput.value : "");
            activeFilterValue = employeeFilterSelect ? employeeFilterSelect.value : "";
            syncApplyButton();

            if (typeof window.finishAsyncSurfaceSkeleton === "function") {
                window.finishAsyncSurfaceSkeleton(reportTablePanel);
            }
        } catch (error) {
            console.error("Error fetching analytics:", error);
            if (reportApplyButton) reportApplyButton.disabled = false;
            window.location.href = url;
        }
    }

    if (reportFilterForm) {
        reportFilterForm.addEventListener("submit", function (event) {
            event.preventDefault();
            if (reportApplyButton && reportApplyButton.disabled) return;

            const formData = new FormData(reportFilterForm);
            const params = new URLSearchParams(formData);
            const url = `${window.location.pathname}?${params.toString()}`;
            fetchAnalytics(url);
        });

        syncApplyButton();
    }

    filterReportRows(reportSearchInput ? reportSearchInput.value : "");

    document.addEventListener("click", function (event) {
        const notificationToggle = document.getElementById("notification-toggle");
        const notificationDropdown = document.querySelector(".notification-dropdown");

        if (
            notificationToggle &&
            notificationDropdown &&
            notificationToggle.checked &&
            !notificationDropdown.contains(event.target) &&
            event.target !== notificationToggle
        ) {
            notificationToggle.checked = false;
        }

        if (
            employeeFilterDropdown &&
            employeeFilterDropdown.classList.contains("open") &&
            !employeeFilterDropdown.contains(event.target)
        ) {
            closeEmployeeFilterDropdown();
        }
    });
}());
