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
    const weeklyReportOpenBtn = document.getElementById("weeklyReportOpenBtn");
    const weeklyReportModal = document.getElementById("weeklyReportModal");
    const weeklyReportFrame = document.getElementById("weeklyReportFrame");
    const weeklyReportLoader = document.getElementById("weeklyReportLoader");
    const weeklyReportStatus = document.getElementById("weeklyReportStatus");
    const weeklyReportRange = document.getElementById("weeklyReportRange");
    const weeklyReportWeekButtons = weeklyReportModal ? Array.from(weeklyReportModal.querySelectorAll("[data-weekly-report-week]")) : [];
    const weeklyReportCustomRange = document.getElementById("weeklyReportCustomRange");
    const weeklyReportStartDate = document.getElementById("weeklyReportStartDate");
    const weeklyReportEndDate = document.getElementById("weeklyReportEndDate");
    const weeklyReportApplyRangeBtn = document.getElementById("weeklyReportApplyRangeBtn");
    let weeklyReportEmployeeFilter = document.getElementById("weeklyReportEmployeeFilter");
    const weeklyReportDownloadBtn = document.getElementById("weeklyReportDownloadBtn");
    const weeklyReportEmailBtn = document.getElementById("weeklyReportEmailBtn");
    const weeklyReportPrintBtn = document.getElementById("weeklyReportPrintBtn");

    let activeFilterValue = employeeFilterSelect ? employeeFilterSelect.value : "";
    let reportCurrentPage = 1;
    let activeWeeklyReportWeek = "current";
    let activeWeeklyReportEmployeeIds = [];
    let weeklyReportLoaded = false;
    let isSyncingWeeklyReportEmployeeFilter = false;
    const reportRowsPerPage = 5;

    function getCsrfToken() {
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        return metaToken ? String(metaToken.getAttribute("content") || "").trim() : "";
    }

    function buildWeeklyReportUrl(baseUrl, week) {
        const url = new URL(baseUrl, window.location.origin);
        url.searchParams.set("week", week || activeWeeklyReportWeek);
        if ((week || activeWeeklyReportWeek) === "custom") {
            if (weeklyReportStartDate && weeklyReportStartDate.value) {
                url.searchParams.set("start", weeklyReportStartDate.value);
            }
            if (weeklyReportEndDate && weeklyReportEndDate.value) {
                url.searchParams.set("end", weeklyReportEndDate.value);
            }
        }
        if (activeWeeklyReportEmployeeIds.length) {
            url.searchParams.set("employee", activeWeeklyReportEmployeeIds.join(","));
        }
        return url.toString();
    }

    function setWeeklyReportStatus(message, isError) {
        if (!weeklyReportStatus) return;

        weeklyReportStatus.textContent = message || "";
        weeklyReportStatus.hidden = !message;
        weeklyReportStatus.classList.toggle("is-error", !!isError);
        weeklyReportStatus.classList.toggle("is-success", !!message && !isError);
    }

    function setWeeklyReportLoading(isLoading) {
        if (weeklyReportLoader) weeklyReportLoader.hidden = !isLoading;
        if (weeklyReportFrame) weeklyReportFrame.classList.toggle("is-loading", !!isLoading);
        [weeklyReportDownloadBtn, weeklyReportEmailBtn, weeklyReportPrintBtn].forEach(function (button) {
            if (button) button.disabled = !!isLoading;
        });
    }

    function syncWeeklyReportWeekButtons() {
        weeklyReportWeekButtons.forEach(function (button) {
            const isActive = button.dataset.weeklyReportWeek === activeWeeklyReportWeek;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
        if (weeklyReportCustomRange) {
            weeklyReportCustomRange.hidden = activeWeeklyReportWeek !== "custom";
        }
    }

    function getWeeklyReportEmployeeControls(frameDocument) {
        const filter = frameDocument ? frameDocument.getElementById("weeklyReportEmployeeFilter") : null;
        return {
            filter,
            trigger: frameDocument ? frameDocument.getElementById("weeklyReportEmployeeFilterTrigger") : null,
            allCheckbox: filter ? filter.querySelector(".weekly-report-employee-all") : null,
            checkboxes: filter ? Array.from(filter.querySelectorAll(".weekly-report-employee-checkbox")) : [],
            applyButton: frameDocument ? frameDocument.getElementById("weeklyReportEmployeeApplyBtn") : null,
            clearButton: frameDocument ? frameDocument.getElementById("weeklyReportEmployeeClearBtn") : null
        };
    }

    function updateWeeklyReportEmployeeTrigger(frameDocument) {
        const controls = getWeeklyReportEmployeeControls(frameDocument);
        if (!controls.trigger || !controls.allCheckbox) return;

        const selected = controls.checkboxes.filter(function (checkbox) {
            return checkbox.checked;
        });

        if (controls.allCheckbox.checked || selected.length === 0) {
            controls.trigger.textContent = "All Employees";
        } else if (selected.length === 1) {
            controls.trigger.textContent = selected[0].dataset.label || "1 Employee";
        } else {
            controls.trigger.textContent = `${selected.length} Employees Selected`;
        }
    }

    function getPendingWeeklyReportEmployeeIds(frameDocument) {
        const controls = getWeeklyReportEmployeeControls(frameDocument);
        if (!controls.filter || (controls.allCheckbox && controls.allCheckbox.checked)) return [];

        return controls.checkboxes.filter(function (checkbox) {
            return checkbox.checked;
        }).map(function (checkbox) {
            return String(checkbox.value || "");
        }).filter(Boolean);
    }

    function areWeeklyReportEmployeeIdsEqual(firstIds, secondIds) {
        const first = (firstIds || []).map(String).sort();
        const second = (secondIds || []).map(String).sort();
        if (first.length !== second.length) return false;

        return first.every(function (value, index) {
            return value === second[index];
        });
    }

    function syncWeeklyReportEmployeeActionButtons(frameDocument) {
        const controls = getWeeklyReportEmployeeControls(frameDocument);
        if (!controls.filter) return;

        const pendingIds = getPendingWeeklyReportEmployeeIds(frameDocument);
        if (controls.applyButton) {
            controls.applyButton.disabled = areWeeklyReportEmployeeIdsEqual(pendingIds, activeWeeklyReportEmployeeIds);
        }
        if (controls.clearButton) {
            controls.clearButton.disabled = activeWeeklyReportEmployeeIds.length === 0;
        }
    }

    function syncWeeklyReportEmployeeFilter() {
        if (!weeklyReportFrame) return;

        const frameDocument = weeklyReportFrame.contentDocument;
        if (!frameDocument) return;

        const controls = getWeeklyReportEmployeeControls(frameDocument);
        weeklyReportEmployeeFilter = controls.filter;
        if (!weeklyReportEmployeeFilter) return;

        isSyncingWeeklyReportEmployeeFilter = true;

        controls.checkboxes.forEach(function (checkbox) {
            checkbox.checked = activeWeeklyReportEmployeeIds.includes(String(checkbox.value || ""));
        });
        if (controls.allCheckbox) {
            controls.allCheckbox.checked = activeWeeklyReportEmployeeIds.length === 0;
        }
        updateWeeklyReportEmployeeTrigger(frameDocument);
        syncWeeklyReportEmployeeActionButtons(frameDocument);

        if (controls.trigger) {
            controls.trigger.addEventListener("click", function () {
                weeklyReportEmployeeFilter.classList.toggle("is-open");
            });
        }

        if (controls.allCheckbox) {
            controls.allCheckbox.addEventListener("change", function () {
                if (controls.allCheckbox.checked) {
                    controls.checkboxes.forEach(function (checkbox) {
                        checkbox.checked = false;
                    });
                }
                updateWeeklyReportEmployeeTrigger(frameDocument);
                syncWeeklyReportEmployeeActionButtons(frameDocument);
            });
        }

        controls.checkboxes.forEach(function (checkbox) {
            checkbox.addEventListener("change", function () {
                if (controls.allCheckbox) {
                    controls.allCheckbox.checked = !controls.checkboxes.some(function (item) {
                        return item.checked;
                    });
                }
                updateWeeklyReportEmployeeTrigger(frameDocument);
                syncWeeklyReportEmployeeActionButtons(frameDocument);
            });
        });

        if (controls.applyButton) {
            controls.applyButton.addEventListener("click", function () {
                if (isSyncingWeeklyReportEmployeeFilter || controls.applyButton.disabled) return;
                filterWeeklyReportEmployees();
                weeklyReportEmployeeFilter.classList.remove("is-open");
                loadWeeklyReport(activeWeeklyReportWeek);
            });
        }

        if (controls.clearButton) {
            controls.clearButton.addEventListener("click", function () {
                if (controls.clearButton.disabled) return;
                activeWeeklyReportEmployeeIds = [];
                if (controls.allCheckbox) controls.allCheckbox.checked = true;
                controls.checkboxes.forEach(function (checkbox) {
                    checkbox.checked = false;
                });
                updateWeeklyReportEmployeeTrigger(frameDocument);
                syncWeeklyReportEmployeeActionButtons(frameDocument);
                weeklyReportEmployeeFilter.classList.remove("is-open");
                loadWeeklyReport(activeWeeklyReportWeek);
            });
        }

        frameDocument.addEventListener("click", function (event) {
            if (!weeklyReportEmployeeFilter.contains(event.target)) {
                weeklyReportEmployeeFilter.classList.remove("is-open");
            }
        });

        frameDocument.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                weeklyReportEmployeeFilter.classList.remove("is-open");
            }
        });

        isSyncingWeeklyReportEmployeeFilter = false;
        filterWeeklyReportEmployees();
    }

    function filterWeeklyReportEmployees() {
        if (!weeklyReportFrame) return;

        const frameDocument = weeklyReportFrame.contentDocument;
        if (!frameDocument) return;

        const controls = getWeeklyReportEmployeeControls(frameDocument);
        weeklyReportEmployeeFilter = controls.filter;
        if (!weeklyReportEmployeeFilter) return;

        const selectedIds = controls.checkboxes.filter(function (checkbox) {
            return checkbox.checked;
        }).map(function (checkbox) {
            return String(checkbox.value || "");
        }).filter(Boolean);
        activeWeeklyReportEmployeeIds = controls.allCheckbox && controls.allCheckbox.checked ? [] : selectedIds;

        frameDocument.querySelectorAll(".employee-card").forEach(function (card) {
            const employeeId = String(card.dataset.weeklyReportUserId || "");
            card.style.display = activeWeeklyReportEmployeeIds.length === 0 || activeWeeklyReportEmployeeIds.includes(employeeId) ? "" : "none";
        });
        updateWeeklyReportEmployeeTrigger(frameDocument);
        syncWeeklyReportEmployeeActionButtons(frameDocument);
    }

    async function loadWeeklyReport(week) {
        if (!weeklyReportOpenBtn || !weeklyReportFrame) return;

        activeWeeklyReportWeek = week || activeWeeklyReportWeek || "current";
        syncWeeklyReportWeekButtons();
        setWeeklyReportStatus("", false);

        if (activeWeeklyReportWeek === "custom") {
            if (!weeklyReportStartDate || !weeklyReportEndDate || !weeklyReportStartDate.value || !weeklyReportEndDate.value) {
                setWeeklyReportStatus("Choose both from and to dates for the custom report.", true);
                return;
            }
            if (weeklyReportEndDate.value < weeklyReportStartDate.value) {
                setWeeklyReportStatus("To date cannot be earlier than from date.", true);
                return;
            }
        }

        setWeeklyReportLoading(true);

        try {
            const response = await fetch(buildWeeklyReportUrl(weeklyReportOpenBtn.dataset.previewUrl, activeWeeklyReportWeek), {
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                },
                cache: "no-store"
            });
            const payload = typeof window.parseJsonOrSessionExpired === "function"
                ? await window.parseJsonOrSessionExpired(response)
                : await response.json();

            if (payload.sessionExpired) {
                if (typeof window.redirectAfterSessionExpired === "function") {
                    window.redirectAfterSessionExpired(payload);
                }
                return;
            }

            if (!response.ok || payload.success === false) {
                throw new Error(payload.detail || "Unable to load weekly report.");
            }

            weeklyReportFrame.srcdoc = payload.html || "";
            weeklyReportFrame.addEventListener("load", syncWeeklyReportEmployeeFilter, { once: true });
            weeklyReportLoaded = true;
            if (weeklyReportRange) {
                weeklyReportRange.textContent = `${payload.period_start} - ${payload.period_end}`;
            }
        } catch (error) {
            setWeeklyReportStatus(error.message || "Unable to load weekly report.", true);
        } finally {
            setWeeklyReportLoading(false);
        }
    }

    function openWeeklyReportModal() {
        if (!weeklyReportModal) return;

        weeklyReportModal.classList.add("is-open");
        weeklyReportModal.setAttribute("aria-hidden", "false");
        document.body.classList.add("weekly-report-modal-open");

        if (!weeklyReportLoaded) {
            loadWeeklyReport("current");
        }
    }

    function closeWeeklyReportModal() {
        if (!weeklyReportModal) return;

        weeklyReportModal.classList.remove("is-open");
        weeklyReportModal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("weekly-report-modal-open");
    }

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

    function getActiveAnalyticsUrl() {
        const params = new URLSearchParams();
        if (activeFilterValue) {
            params.set("employee", activeFilterValue);
        }

        const query = params.toString();
        return query ? `${window.location.pathname}?${query}` : window.location.pathname;
    }

    async function fetchAnalytics(url, options) {
        const config = Object.assign({
            silent: false,
            preservePage: false,
            updateHistory: true
        }, options || {});
        const previousPage = reportCurrentPage;

        if (!config.silent && typeof window.startAsyncSurfaceSkeleton === "function") {
            window.startAsyncSurfaceSkeleton(reportTablePanel);
        }

        if (!config.silent && reportApplyButton) reportApplyButton.disabled = true;

        try {
            const response = await fetch(url, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache"
                },
                cache: "no-store"
            });

            if (!response.ok) throw new Error("Network response was not ok");

            const data = typeof window.parseJsonOrSessionExpired === "function"
                ? await window.parseJsonOrSessionExpired(response)
                : await response.json();
            if (data.sessionExpired) {
                if (typeof window.redirectAfterSessionExpired === "function") {
                    window.redirectAfterSessionExpired(data);
                }
                return;
            }

            if (reportTableBody) {
                window.setSafeHTML(reportTableBody, data.table_html);
            }
            reportCurrentPage = config.preservePage ? previousPage : 1;

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

            if (config.updateHistory) {
                window.history.pushState({ path: url }, "", url);
            }
            filterReportRows(reportSearchInput ? reportSearchInput.value : "");
            activeFilterValue = employeeFilterSelect ? employeeFilterSelect.value : "";
            syncApplyButton();

            if (!config.silent && typeof window.finishAsyncSurfaceSkeleton === "function") {
                window.finishAsyncSurfaceSkeleton(reportTablePanel);
            }
        } catch (error) {
            console.error("Error fetching analytics:", error);
            if (!config.silent) {
                if (reportApplyButton) reportApplyButton.disabled = false;
                window.location.href = url;
            }
        }
    }

    function refreshLiveAnalytics() {
        if (document.hidden) return;

        fetchAnalytics(getActiveAnalyticsUrl(), {
            silent: true,
            preservePage: true,
            updateHistory: false
        });
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

    if (weeklyReportOpenBtn) {
        weeklyReportOpenBtn.addEventListener("click", openWeeklyReportModal);
    }

    if (weeklyReportModal) {
        weeklyReportModal.addEventListener("click", function (event) {
            if (event.target.closest("[data-weekly-report-close]")) {
                closeWeeklyReportModal();
            }
        });
    }

    weeklyReportWeekButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            const week = button.dataset.weeklyReportWeek || "current";
            activeWeeklyReportEmployeeIds = [];
            if (week === activeWeeklyReportWeek && week !== "custom" && weeklyReportLoaded) return;
            activeWeeklyReportWeek = week;
            syncWeeklyReportWeekButtons();
            if (week === "custom") {
                setWeeklyReportStatus("Choose a date range, then click Apply.", false);
                return;
            }
            loadWeeklyReport(week);
        });
    });

    if (weeklyReportApplyRangeBtn) {
        weeklyReportApplyRangeBtn.addEventListener("click", function () {
            activeWeeklyReportEmployeeIds = [];
            loadWeeklyReport("custom");
        });
    }

    if (weeklyReportDownloadBtn && weeklyReportOpenBtn) {
        weeklyReportDownloadBtn.addEventListener("click", function () {
            window.location.href = buildWeeklyReportUrl(weeklyReportOpenBtn.dataset.downloadUrl, activeWeeklyReportWeek);
        });
    }

    if (weeklyReportEmailBtn && weeklyReportOpenBtn) {
        weeklyReportEmailBtn.addEventListener("click", async function () {
            setWeeklyReportStatus("", false);
            weeklyReportEmailBtn.disabled = true;
            weeklyReportEmailBtn.textContent = "Sending...";

            try {
                const response = await fetch(buildWeeklyReportUrl(weeklyReportOpenBtn.dataset.emailUrl, activeWeeklyReportWeek), {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCsrfToken(),
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    cache: "no-store"
                });
                const payload = typeof window.parseJsonOrSessionExpired === "function"
                    ? await window.parseJsonOrSessionExpired(response)
                    : await response.json();

                if (payload.sessionExpired) {
                    if (typeof window.redirectAfterSessionExpired === "function") {
                        window.redirectAfterSessionExpired(payload);
                    }
                    return;
                }

                if (!response.ok || payload.success === false) {
                    throw new Error(payload.message || payload.detail || "Unable to email weekly report.");
                }

                setWeeklyReportStatus(payload.message || "Weekly report emailed.", false);
            } catch (error) {
                setWeeklyReportStatus(error.message || "Unable to email weekly report.", true);
            } finally {
                weeklyReportEmailBtn.disabled = false;
                weeklyReportEmailBtn.textContent = "Email Report";
            }
        });
    }

    if (weeklyReportPrintBtn && weeklyReportFrame) {
        weeklyReportPrintBtn.addEventListener("click", function () {
            if (!weeklyReportFrame.contentWindow) return;
            weeklyReportFrame.contentWindow.focus();
            weeklyReportFrame.contentWindow.print();
        });
    }

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && weeklyReportModal && weeklyReportModal.classList.contains("is-open")) {
            closeWeeklyReportModal();
        }
    });

    filterReportRows(reportSearchInput ? reportSearchInput.value : "");

    window.addEventListener("focus", refreshLiveAnalytics);
    window.addEventListener("pageshow", refreshLiveAnalytics);
    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            refreshLiveAnalytics();
        }
    });
    setInterval(refreshLiveAnalytics, 60000);

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
