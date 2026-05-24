(function () {
    "use strict";

        function parseJsonScriptData(elementId, fallback)
        {
            const node = document.getElementById(elementId);
            if (!node) return fallback;

            try
            {
                const parsed = JSON.parse(node.textContent || "null");
                if (typeof parsed === "string")
                {
                    return JSON.parse(parsed || "null") || fallback;
                }
                return parsed || fallback;
            }
            catch (error)
            {
                return fallback;
            }
        }

        const companyHolidayDates = parseJsonScriptData("company-holidays-data", []);
        const companyHolidayMap = new Map(companyHolidayDates.map((holiday) => [holiday.date, holiday]));
        const existingLeaveRanges = parseJsonScriptData("existing-leaves-data", []);
        const leaveType = document.getElementById("leaveType");
        const form = document.querySelector(".leave-form");
        const fromTimeBlock = document.getElementById("fromTimeBlock");
        const toTimeBlock = document.getElementById("toTimeBlock");
        const fromDate = document.getElementById("fromDate");
        const toDate = document.getElementById("toDate");
        const toDatePicker = document.getElementById("toDatePicker");
        const fromHour = document.getElementById("fromHour");
        const fromMinute = document.getElementById("fromMinute");
        const fromMeridiem = document.getElementById("fromMeridiem");
        const fromDateTime = document.getElementById("fromDateTime");
        const toDateTime = document.getElementById("toDateTime");
        const toDateHidden = document.getElementById("toDateHidden");
        const datePickers = Array.from(document.querySelectorAll(".custom-date-picker"));
        const toTime = document.getElementById("toTime");
        const reason = document.getElementById("reason");
        const typeHint = document.getElementById("typeHint");
        const timeWarning = document.getElementById("timeWarning");
        const leaveTypeDropdown = document.getElementById("leaveTypeDropdown");
        const leaveTypeTrigger = document.getElementById("leaveTypeTrigger");
        const leaveTypeMenu = document.getElementById("leaveTypeMenu");
        const leaveTypeValue = leaveTypeTrigger.querySelector(".custom-select-value");
        const leaveTypeOptions = leaveTypeMenu.querySelectorAll(".custom-option");
        const timeSelectDropdowns = Array.from(document.querySelectorAll(".time-select-shell"));
        const instructionCard = document.getElementById("instructionCard");
        const instructionContent = document.getElementById("instructionContent");
        const toggleBtn = document.getElementById("toggleBtn");
        const timeHourShell = fromHour.closest(".time-select-shell");
        const timeMinuteShell = fromMinute.closest(".time-select-shell");
        const timeMeridiemShell = fromMeridiem.closest(".time-select-shell");
        const inlineWarnings = {
            leaveType: document.getElementById("leaveTypeWarning"),
            fromDate: document.getElementById("fromDateWarning"),
            fromTime: document.getElementById("fromTimeWarning"),
            toDate: document.getElementById("toDateWarning"),
            reason: document.getElementById("reasonWarning")
        };
        const storedApplyTime = {
            Short: { hour: "", minute: "" },
            Half: { hour: "", minute: "" }
        };
        const todayValue = formatValueDate(new Date());
        fromDate.min = todayValue;
        toDate.min = fromDate.value || todayValue;

        function setInlineWarning(block, warningEl, message = "") {
            if (!block || !warningEl) {
                return;
            }

            const hasMessage = !!message;
            block.classList.toggle("invalid", hasMessage);
            warningEl.classList.toggle("visible", hasMessage);
            warningEl.textContent = hasMessage ? message : "";
        }

        function clearTimeFieldHighlights() {
            [timeHourShell, timeMinuteShell, timeMeridiemShell].forEach((shell) => {
                shell?.classList.remove("invalid-time");
            });
        }

        function clearInlineWarning(key) {
            const warningEl = inlineWarnings[key];
            const block = warningEl?.closest(".field-block");
            setInlineWarning(block, warningEl, "");
            if (key === "leaveType") {
                leaveTypeDropdown.classList.remove("field-invalid");
            }
            if (key === "fromTime") {
                clearTimeFieldHighlights();
            }
        }

        function showInlineWarning(key, message) {
            const warningEl = inlineWarnings[key];
            const block = warningEl?.closest(".field-block");
            setInlineWarning(block, warningEl, message);
            if (key === "leaveType") {
                leaveTypeDropdown.classList.add("field-invalid");
            }
        }

        function clearAllInlineWarnings() {
            Object.keys(inlineWarnings).forEach(clearInlineWarning);
        }

        function isTimeLeave() {
            return leaveType.value === "Short" || leaveType.value === "Half";
        }

        function setTypeHint(message, state = "default") {
            typeHint.classList.remove("hint-animating", "is-warning", "is-soft-warning");
            void typeHint.offsetWidth;
            typeHint.textContent = message;
            if (state === "warning") {
                typeHint.classList.add("is-warning");
            } else if (state === "soft-warning") {
                typeHint.classList.add("is-soft-warning");
            }
            typeHint.classList.add("hint-animating");
        }

        function getDefaultHintMessage() {
            return isTimeLeave()
                ? "Time is required for Short and Half leave"
                : "Dates only for regular leave";
        }

        function syncToDateLockState() {
            const locked = isTimeLeave();

            if (!toDatePicker) {
                return;
            }

            if (locked) {
                toDatePicker.classList.add("is-locked");
                toDatePicker.querySelector(".date-trigger")?.setAttribute("aria-disabled", "true");
                closeDatePickers();
                toDate.value = fromDate.value || "";
            } else {
                toDatePicker.classList.remove("is-locked");
                toDatePicker.querySelector(".date-trigger")?.setAttribute("aria-disabled", "false");
            }

            syncDatePicker(toDatePicker);
            renderDatePicker(toDatePicker);
        }

        function showTimeWarning(message = "") {
            if (!message) {
                timeWarning.textContent = "";
                timeWarning.classList.remove("visible", "is-warning", "is-soft-warning");
                return;
            }

            const state = message.includes("slightly late") ? "soft-warning" : "warning";
            timeWarning.classList.remove("visible", "is-warning", "is-soft-warning");
            void timeWarning.offsetWidth;
            timeWarning.textContent = message;
            timeWarning.classList.add("visible");
            timeWarning.classList.add(state === "soft-warning" ? "is-soft-warning" : "is-warning");
        }

        function formatHourLabel(hour24) {
            return String(hour24 > 12 ? hour24 - 12 : hour24);
        }

        function storeCurrentTimeForType(type) {
            if (!(type === "Short" || type === "Half")) {
                return;
            }

            if (fromHour.value !== "" && fromMinute.value !== "") {
                storedApplyTime[type] = {
                    hour: fromHour.value,
                    minute: fromMinute.value
                };
            }
        }

        function clearStoredTimeForCurrentType() {
            if (!isTimeLeave()) {
                return;
            }

            storedApplyTime[leaveType.value] = {
                hour: "",
                minute: ""
            };
        }

        function getDateTimingRules() {
            if (!fromDate.value || !isTimeLeave()) {
                return null;
            }

            const now = new Date();
            const [year, month, day] = fromDate.value.split("-").map(Number);
            const selectedDate = new Date(year, month - 1, day);
            selectedDate.setHours(0, 0, 0, 0);

            const today = new Date();
            today.setHours(0, 0, 0, 0);

            const isToday = selectedDate.getTime() === today.getTime();
            const startHour = 10;
            const endHour = leaveType.value === "Short" ? 16 : 14;

            let minHour = startHour;
            let minMinute = 0;

            if (isToday) {
                const minTime = new Date(now.getTime() + (2 * 60 + 2) * 60 * 1000);
                const relaxedMin = new Date(minTime.getTime() - (7 * 60 * 1000));

                minHour = relaxedMin.getHours();
                minMinute = relaxedMin.getMinutes();

                if (minHour < startHour) {
                    minHour = startHour;
                    minMinute = 0;
                }

                if (minTime.toDateString() !== now.toDateString() || minHour > endHour) {
                    return {
                        isToday,
                        startHour,
                        endHour,
                        minHour,
                        minMinute,
                        unavailable: true
                    };
                }
            }

            return {
                isToday,
                startHour,
                endHour,
                minHour,
                minMinute,
                unavailable: false
            };
        }

        function restoreStoredTimeForCurrentType(preferredHour = "", preferredMinute = "") {
            if (!isTimeLeave() || !fromDate.value) {
                return;
            }

            const rules = getDateTimingRules();
            if (!rules || rules.unavailable) {
                return;
            }

            const restore = storedApplyTime[leaveType.value] || { hour: "", minute: "" };
            const targetHour = restore.hour || preferredHour;
            const targetMinute = restore.minute || preferredMinute;

            if (!targetHour) {
                return;
            }

            const hourExists = [...fromHour.options].some((option) => option.value === targetHour);
            if (!hourExists) {
                return;
            }

            fromHour.value = targetHour;
            updateAMPM();
            updateMinuteOptions(rules.isToday, rules.minHour, rules.minMinute);

            const minuteExists = [...fromMinute.options].some((option) => option.value === targetMinute);
            if (minuteExists) {
                fromMinute.value = targetMinute;
                storedApplyTime[leaveType.value] = {
                    hour: targetHour,
                    minute: targetMinute
                };
                timeSelectDropdowns.forEach(syncTimeSelect);
                updateToTime();
            }
        }

        function toggleTimeFields() {
            const needsTime = isTimeLeave();
            const blocks = [fromTimeBlock, toTimeBlock];

            if (needsTime) {
                blocks.forEach((block) => {
                    block.dataset.mode = "shown";
                    block.classList.remove("leaving");
                    if (block.classList.contains("hidden")) {
                        block.classList.remove("hidden");
                        block.classList.remove("entering");
                        void block.offsetWidth;
                        block.classList.add("entering");
                    }
                });
            } else {
                closeTimeSelectMenus();
                blocks.forEach((block) => {
                    block.dataset.mode = "hidden";
                    block.classList.remove("entering");
                    block.classList.remove("leaving");
                    block.classList.add("hidden");
                });
            }

            setTypeHint(getDefaultHintMessage());
            syncToDateLockState();

            if (!needsTime) {
                toTime.value = "";
                fromDateTime.value = "";
                toDateTime.value = "";
                toDateHidden.value = "";
                fromHour.innerHTML = '<option value="">Hour</option>';
                fromMinute.innerHTML = '<option value="">Minute</option>';
                fromMeridiem.value = "AM";
                timeSelectDropdowns.forEach(buildTimeSelect);
                showTimeWarning("");
            }
        }

        function closeLeaveTypeMenu() {
            leaveTypeDropdown.classList.remove("open");
            leaveTypeTrigger.setAttribute("aria-expanded", "false");
        }

        function openLeaveTypeMenu() {
            leaveTypeDropdown.classList.add("open");
            leaveTypeTrigger.setAttribute("aria-expanded", "true");
        }

        function setLeaveType(value) {
            const previousType = leaveType.value;
            storeCurrentTimeForType(previousType);
            leaveType.value = value;
            const selectedOption = Array.from(leaveTypeOptions).find((option) => option.dataset.value === value);
            leaveTypeValue.textContent = selectedOption && value
                ? selectedOption.querySelector(".option-title").textContent
                : "Select leave type";

            leaveTypeOptions.forEach((option) => {
                option.classList.toggle("selected", option.dataset.value === value);
            });

            toggleTimeFields();
            handleDateChange(fromDate);
            restoreStoredTimeForCurrentType();
        }

        function updateAMPM() {
            const hour = parseInt(fromHour.value, 10);
            if (Number.isNaN(hour)) {
                fromMeridiem.value = "AM";
            } else {
                fromMeridiem.value = hour >= 12 ? "PM" : "AM";
            }
            const meridiemDropdown = fromMeridiem.closest(".custom-select");
            if (meridiemDropdown) {
                syncTimeSelect(meridiemDropdown);
            }
        }

        function updateMinuteOptions(isToday = false, minHour = 10, minMinute = 0) {
            const previousMinute = fromMinute.value;
            fromMinute.innerHTML = '<option value="">Minute</option>';

            const selectedHour = parseInt(fromHour.value, 10);
            if (Number.isNaN(selectedHour)) {
                buildTimeSelect(fromMinute.closest(".custom-select"));
                return;
            }

            for (let minute = 0; minute < 60; minute += 1) {
                if (isToday && selectedHour === minHour && minute < minMinute) {
                    continue;
                }

                const option = document.createElement("option");
                option.value = String(minute);
                option.textContent = String(minute).padStart(2, "0");
                fromMinute.appendChild(option);
            }

            if ([...fromMinute.options].some((option) => option.value === previousMinute)) {
                fromMinute.value = previousMinute;
            } else {
                fromMinute.selectedIndex = 0;
            }

            buildTimeSelect(fromMinute.closest(".custom-select"));
        }

        function generateTimeOptions() {
            fromHour.innerHTML = '<option value="">Hour</option>';
            fromMinute.innerHTML = '<option value="">Minute</option>';
            toTime.value = "";
            fromDateTime.value = "";
            toDateTime.value = "";
            toDateHidden.value = "";
            showTimeWarning("");

            if (!isTimeLeave() || !fromDate.value) {
                timeSelectDropdowns.forEach(syncTimeSelect);
                return;
            }

            const rules = getDateTimingRules();
            if (!rules) {
                timeSelectDropdowns.forEach(syncTimeSelect);
                return;
            }

            const { isToday, startHour, endHour, minHour, minMinute, unavailable } = rules;

            if (unavailable) {
                showTimeWarning("No valid time available for today.");
                timeSelectDropdowns.forEach(buildTimeSelect);
                return;
            }

            for (let hour = startHour; hour <= endHour; hour += 1) {
                if (isToday && hour < minHour) {
                    continue;
                }

                const option = document.createElement("option");
                option.value = String(hour);
                option.textContent = formatHourLabel(hour);
                fromHour.appendChild(option);
            }

            updateAMPM();
            updateMinuteOptions(isToday, minHour, minMinute);
            timeSelectDropdowns.forEach(buildTimeSelect);
        }

        function formatDisplayDate(date) {
            const day = String(date.getDate()).padStart(2, "0");
            const month = String(date.getMonth() + 1).padStart(2, "0");
            const year = date.getFullYear();
            return `${day}-${month}-${year}`;
        }

        function formatValueDate(date) {
            const day = String(date.getDate()).padStart(2, "0");
            const month = String(date.getMonth() + 1).padStart(2, "0");
            const year = date.getFullYear();
            return `${year}-${month}-${day}`;
        }

        function formatUpcomingDate(value, formatStyle = "long") {
            const date = parseValueDate(value);
            if (!date) {
                return "";
            }

            if (formatStyle === "compact") {
                return date.toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric"
                });
            }

            return date.toLocaleDateString("en-US", {
                month: formatStyle,
                day: "numeric",
                year: "numeric"
            });
        }

        function setUpcomingDates(formatStyle = "long") {
            document.querySelectorAll(".upcoming-card [data-responsive-date]").forEach((el) => {
                const text = formatUpcomingDate(el.dataset.dateValue, formatStyle);
                if (text) {
                    el.textContent = text;
                }
            });
        }

        function formatResponsiveAppliedDateTime(value, formatStyle = "long") {
            const appliedDate = new Date(value);
            if (Number.isNaN(appliedDate.getTime())) {
                return "Unknown";
            }

            if (formatStyle === "compact") {
                return appliedDate.toLocaleString("en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                    hour12: true,
                });
            }

            return formatAppliedDateTime(value, formatStyle);
        }

        function setUpcomingAppliedTimes(formatStyle = "long") {
            document.querySelectorAll(".upcoming-card .applied-time[data-time]").forEach((el) => {
                el.innerHTML = `
                    <span class="responsive-date-variant responsive-date-variant-full">Applied: ${formatResponsiveAppliedDateTime(el.dataset.time, "long")}</span>
                    <span class="responsive-date-variant responsive-date-variant-short">Applied: ${formatResponsiveAppliedDateTime(el.dataset.time, "short")}</span>
                    <span class="responsive-date-variant responsive-date-variant-compact">Applied: ${formatResponsiveAppliedDateTime(el.dataset.time, "compact")}</span>
                `;
            });
        }

        function getUpcomingRowAvailableWidth(target) {
            const tile = target.closest(".mini-tile") || target.parentElement;
            if (!tile) {
                return target.clientWidth;
            }

            const tileRect = tile.getBoundingClientRect();
            return Math.max(0, tileRect.width - 16);
        }

        function upcomingRowOverflows(target) {
            const availableWidth = getUpcomingRowAvailableWidth(target);
            if (!availableWidth) {
                return target.scrollWidth > target.clientWidth + 1;
            }

            const targetRect = target.getBoundingClientRect();

            return (
                target.scrollWidth > target.clientWidth + 1 ||
                targetRect.width > availableWidth + 1
            );
        }

        function setUpcomingRowFormat(target, formatStyle) {
            if (target.matches(".applied-time[data-time]")) {
                target.innerText = "Applied: " + formatResponsiveAppliedDateTime(target.dataset.time, formatStyle);
                return;
            }

            target.querySelectorAll("[data-responsive-date]").forEach((el) => {
                const text = formatUpcomingDate(el.dataset.dateValue, formatStyle);
                if (text) {
                    el.textContent = text;
                }
            });

            if (target.matches("[data-responsive-date]")) {
                const text = formatUpcomingDate(target.dataset.dateValue, formatStyle);
                if (text) {
                    target.textContent = text;
                }
            }
        }

        function applyResponsiveUpcomingRows() {
            setUpcomingAppliedTimes("long");
        }

        function getCompanyHoliday(date) {
            return companyHolidayMap.get(formatValueDate(date)) || null;
        }

        function getExistingLeave(date) {
            const target = formatValueDate(date);
            const getStatusPriority = (leave) => {
                const normalizedStatus = String(leave?.status || "").trim().toLowerCase();
                if (normalizedStatus === "pending") return 3;
                if (normalizedStatus === "approved") return 2;
                if (normalizedStatus === "rejected") return 1;
                return 0;
            };
            const getSortTime = (leave) => {
                const rawValue = leave?.updated_at || leave?.approved_at || leave?.rejected_at || leave?.created_at || "";
                const timeValue = rawValue ? Date.parse(rawValue) : NaN;
                return Number.isFinite(timeValue) ? timeValue : Number(leave?.id || 0);
            };
            return existingLeaveRanges
                .filter((leave) => target >= leave.from && target <= leave.to)
                .sort((first, second) => {
                    const statusDiff = getStatusPriority(second) - getStatusPriority(first);
                    if (statusDiff) {
                        return statusDiff;
                    }

                    const timeDiff = getSortTime(second) - getSortTime(first);
                    if (timeDiff) {
                        return timeDiff;
                    }

                    return (Number(second.id) || 0) - (Number(first.id) || 0);
                })[0] || null;
        }

        function parseValueDate(value) {
            if (!value) {
                return null;
            }

            const [year, month, day] = value.split("-").map(Number);
            if (!year || !month || !day) {
                return null;
            }

            return new Date(year, month - 1, day);
        }

        function closeDatePickers() {
            datePickers.forEach((picker) => {
                picker.classList.remove("open");
                picker.classList.remove("open-up");
                const menu = getDatePickerMenu(picker);
                if (menu) {
                    menu.classList.remove("is-open", "open-up");
                    menu.style.removeProperty("--date-menu-top");
                    menu.style.removeProperty("--date-menu-left");
                    menu.style.removeProperty("--date-pointer-left");
                    menu.style.removeProperty("--calendar-month-gradient");
                    picker._dateMenuTop = null;
                    picker._dateMenuLeft = null;
                    picker._dateMenuOpenUp = false;
                    if (menu.parentElement !== picker) {
                        picker.appendChild(menu);
                    }
                }
                picker.querySelector(".date-trigger")?.setAttribute("aria-expanded", "false");
            });
            document.querySelectorAll(".field-block.has-open-date-menu, .field-row.has-open-date-menu, .form-panel.has-open-date-menu").forEach((element) => {
                element.classList.remove("has-open-date-menu");
            });
        }

        function syncDatePicker(picker) {
            const hiddenInput = picker.querySelector("input[type='hidden']");
            const valueElement = picker.querySelector(".date-value");
            const selectedDate = parseValueDate(hiddenInput.value);
            valueElement.textContent = selectedDate ? formatDisplayDate(selectedDate) : "dd-mm-yyyy";
        }

        function getInputMinDate(input) {
            const minValue = input.min;
            return minValue ? parseValueDate(minValue) : null;
        }

        function getMonthStart(date) {
            return new Date(date.getFullYear(), date.getMonth(), 1);
        }

        function getMinimumViewDate(input) {
            return getMonthStart(getInputMinDate(input) || new Date());
        }

        function handleDateChange(changedInput) {
            const todayString = formatValueDate(new Date());
            fromDate.min = todayString;
            toDate.min = fromDate.value || todayString;

            const previousHour = fromHour.value;
            const previousMinute = fromMinute.value;

            if (changedInput === fromDate) {
                if (isTimeLeave()) {
                    toDate.value = fromDate.value || "";
                } else if (fromDate.value && toDate.value && toDate.value < fromDate.value) {
                    toDate.value = "";
                }

                const toViewDate = parseValueDate(toDate.value || fromDate.value || todayString);
                if (toViewDate && toDatePicker) {
                    toDatePicker._viewDate = new Date(toViewDate.getFullYear(), toViewDate.getMonth(), 1);
                }
            }

            if (changedInput === toDate) {
                const selectedToDate = parseValueDate(toDate.value || toDate.min || todayString);
                if (selectedToDate && toDatePicker) {
                    toDatePicker._viewDate = new Date(selectedToDate.getFullYear(), selectedToDate.getMonth(), 1);
                }
            }

            if (isTimeLeave()) {
                generateTimeOptions();
                restoreStoredTimeForCurrentType(previousHour, previousMinute);
                updateToTime();
            } else {
                fromDateTime.value = "";
                toDateTime.value = "";
                toDateHidden.value = "";
                showTimeWarning("");
            }

            datePickers.forEach(syncDatePicker);
            datePickers.forEach(renderDatePicker);
            syncToDateLockState();
            repositionOpenDatePickers();
        }

        function updateToTime() {
            if (!isTimeLeave()) {
                return;
            }

            const hour24 = parseInt(fromHour.value, 10);
            const minute = parseInt(fromMinute.value, 10);

            if (Number.isNaN(hour24) || Number.isNaN(minute) || !fromDate.value) {
                toTime.value = "";
                fromDateTime.value = "";
                toDateTime.value = "";
                toDateHidden.value = "";
                return;
            }

            const now = new Date();
            const start = new Date(fromDate.value);
            start.setHours(hour24, minute, 0, 0);

            if (fromDate.value === formatValueDate(now)) {
                const minAllowed = new Date(now.getTime() + (2 * 60 + 1) * 60 * 1000);
                const relaxedMin = new Date(minAllowed.getTime() - (7 * 60 * 1000));

                if (start < relaxedMin) {
                    showTimeWarning("You must apply at least 2 hours before current time.");
                    toTime.value = "";
                    fromDateTime.value = "";
                    toDateTime.value = "";
                    toDateHidden.value = "";
                    return;
                }

                if (start >= relaxedMin && start < minAllowed) {
                    showTimeWarning("You are applying slightly late (within 7 minute grace period).");
                } else {
                    showTimeWarning("");
                }
            } else {
                showTimeWarning("");
            }

            const duration = leaveType.value === "Short" ? 2 : 4;
            const end = new Date(start.getTime() + duration * 60 * 60 * 1000);

            if (end.getHours() >= 19) {
                showTimeWarning("Leave cannot extend beyond 7:00 PM.");
                toTime.value = "";
                fromDateTime.value = "";
                toDateTime.value = "";
                toDateHidden.value = "";
                return;
            }

            toDate.value = fromDate.value;
            toDateHidden.value = fromDate.value;
            fromDateTime.value = start.toISOString();
            toDateTime.value = end.toISOString();
            toTime.value = `${String((end.getHours() % 12) || 12).padStart(2, "0")}:${String(end.getMinutes()).padStart(2, "0")} ${end.getHours() >= 12 ? "PM" : "AM"}`;
        }

        function renderDatePicker(picker) {
            const hiddenInput = picker.querySelector("input[type='hidden']");
            const menu = getDatePickerMenu(picker);
            const currentLabel = menu?.querySelector(".date-current");
            const prevButton = menu?.querySelector(".prev-month");
            const grid = menu?.querySelector(".date-grid");

            if (!hiddenInput || !currentLabel || !grid) {
                return;
            }

            const selectedDate = parseValueDate(hiddenInput.value);
            const minimumViewDate = getMinimumViewDate(hiddenInput);
            let viewDate = picker._viewDate || selectedDate || new Date();

            if (getMonthStart(viewDate) < minimumViewDate) {
                viewDate = minimumViewDate;
                picker._viewDate = new Date(minimumViewDate);
            }

            const monthStart = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
            const monthEnd = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0);
            const firstDayIndex = (monthStart.getDay() + 6) % 7;
            const daysInMonth = monthEnd.getDate();
            const today = new Date();

            picker.dataset.calendarMonth = String(monthStart.getMonth() + 1);
            const openMenu = getDatePickerMenu(picker);
            if (openMenu?.classList.contains("is-open")) {
                openMenu.style.setProperty(
                    "--calendar-month-gradient",
                    getComputedStyle(picker).getPropertyValue("--calendar-month-gradient")
                );
            }
            currentLabel.textContent = monthStart.toLocaleDateString("en-US", { month: "long", year: "numeric" });
            if (prevButton) {
                prevButton.disabled = monthStart <= minimumViewDate;
            }
            grid.innerHTML = "";

            for (let i = 0; i < firstDayIndex; i += 1) {
                const dayButton = document.createElement("button");
                dayButton.type = "button";
                dayButton.className = "date-day muted";
                dayButton.textContent = "";
                dayButton.disabled = true;
                grid.appendChild(dayButton);
            }

            for (let day = 1; day <= daysInMonth; day += 1) {
                const date = new Date(viewDate.getFullYear(), viewDate.getMonth(), day);
                const dayButton = document.createElement("button");
                dayButton.type = "button";
                dayButton.className = "date-day";
                const dayNumber = document.createElement("span");
                dayNumber.className = "date-day-number";
                dayNumber.textContent = String(day);
                dayButton.appendChild(dayNumber);
                const companyHoliday = getCompanyHoliday(date);
                const existingLeave = getExistingLeave(date);

                const minDate = getInputMinDate(hiddenInput);
                const isToday =
                    date.getFullYear() === today.getFullYear() &&
                    date.getMonth() === today.getMonth() &&
                    date.getDate() === today.getDate();
                const isWeekend = date.getDay() === 0 || date.getDay() === 6;
                const isCompanyHolidayBlocked = !!companyHoliday;
                const existingLeaveStatus = String(existingLeave?.status || "").trim().toLowerCase();
                const existingLeaveBlocksSelection = existingLeave && existingLeaveStatus !== "rejected";
                const isDisabled = (minDate && date < minDate) || existingLeaveBlocksSelection || isWeekend || isCompanyHolidayBlocked;

                const isSelected =
                    selectedDate &&
                    date.getFullYear() === selectedDate.getFullYear() &&
                    date.getMonth() === selectedDate.getMonth() &&
                    date.getDate() === selectedDate.getDate();

                if (isToday) {
                    dayButton.classList.add("today");
                }

                if (isWeekend) {
                    dayButton.classList.add("weekend");
                }

                if (companyHoliday) {
                    dayButton.classList.add("company-holiday");
                    if (!companyHoliday.is_optional) {
                        dayButton.classList.add("company-holiday-blocked");
                    }
                    dayButton.title = companyHoliday.is_optional
                        ? `Optional Company Holiday: ${companyHoliday.name}. This date is blocked in the calendar.`
                        : `Company Holiday: ${companyHoliday.name}. This date cannot be selected.`;
                }

                if (existingLeave) {
                    const statusClass = existingLeaveStatus;
                    const leaveTypeLabel = document.createElement("span");
                    leaveTypeLabel.className = "date-day-leave-type";
                    leaveTypeLabel.textContent = existingLeave.type || "Leave";
                    dayButton.classList.add("existing-leave", `existing-leave-${statusClass}`);
                    dayButton.appendChild(leaveTypeLabel);
                    dayButton.title = `${existingLeave.type} leave ${statusClass || "applied"} on this date`;
                }

                if (isWeekend && !existingLeave && !companyHoliday) {
                    dayButton.title = "Weekend cannot be selected.";
                }

                if (isSelected) {
                    dayButton.classList.add("selected");
                }

                if (isDisabled) {
                    if (!existingLeave) {
                        dayButton.classList.add("muted");
                    }
                    dayButton.disabled = true;
                }

                if (!isDisabled) {
                    dayButton.addEventListener("click", () => {
                        hiddenInput.value = formatValueDate(date);
                        picker._viewDate = new Date(date.getFullYear(), date.getMonth(), 1);
                        handleDateChange(hiddenInput);
                        closeDatePickers();
                    });
                }

                grid.appendChild(dayButton);
            }

            const remainder = grid.children.length % 7;
            const cellsToAdd = remainder === 0 ? 0 : 7 - remainder;
            for (let day = 1; day <= cellsToAdd; day += 1) {
                const dayButton = document.createElement("button");
                dayButton.type = "button";
                dayButton.className = "date-day muted";
                dayButton.textContent = "";
                dayButton.disabled = true;
                grid.appendChild(dayButton);
            }
        }

        function positionDatePickerMenu(picker, keepVerticalPosition = false) {
            const menu = getDatePickerMenu(picker);
            const trigger = picker.querySelector(".date-trigger");

            if (!menu || !trigger || !picker.classList.contains("open")) {
                return;
            }

            const gap = 8;
            const viewportWidth = window.visualViewport?.width || window.innerWidth;
            const viewportHeight = window.visualViewport?.height || window.innerHeight;
            const viewportTop = window.visualViewport?.offsetTop || 0;
            const viewportLeft = window.visualViewport?.offsetLeft || 0;
            const margin = 8;
            const triggerRect = trigger.getBoundingClientRect();
            const menuRect = menu.getBoundingClientRect();
            const menuWidth = Math.ceil(menuRect.width || 258);
            const menuHeight = Math.ceil(menuRect.height || 282);
            const triggerCenter = triggerRect.left + (triggerRect.width / 2);
            const spaceBelow = viewportTop + viewportHeight - triggerRect.bottom;
            const spaceAbove = triggerRect.top - viewportTop;
            const openUp = spaceBelow < menuHeight + gap + margin && spaceAbove > spaceBelow;
            let top = openUp ? triggerRect.top - menuHeight - gap : triggerRect.bottom + gap;
            let left = triggerRect.left;

            if (keepVerticalPosition && picker._dateMenuTop !== null && picker._dateMenuTop !== undefined) {
                top = picker._dateMenuTop;
            } else {
                top = Math.max(viewportTop + margin, Math.min(top, viewportTop + viewportHeight - menuHeight - margin));
                picker._dateMenuTop = top;
                picker._dateMenuOpenUp = openUp;
            }

            left = Math.max(viewportLeft + margin, Math.min(left, viewportLeft + viewportWidth - menuWidth - margin));
            picker._dateMenuLeft = left;
            const pointerLeft = Math.max(18, Math.min(triggerCenter - left, menuWidth - 18));

            picker.classList.toggle("open-up", keepVerticalPosition ? !!picker._dateMenuOpenUp : openUp);
            menu.classList.toggle("open-up", keepVerticalPosition ? !!picker._dateMenuOpenUp : openUp);
            menu.style.setProperty("--date-menu-top", `${Math.round(top)}px`);
            menu.style.setProperty("--date-menu-left", `${Math.round(left)}px`);
            menu.style.setProperty("--date-pointer-left", `${Math.round(pointerLeft)}px`);
        }

        function getDatePickerMenu(picker) {
            return picker._dateMenu || picker.querySelector(".date-menu");
        }

        function openDatePicker(picker) {
            const trigger = picker.querySelector(".date-trigger");
            const menu = getDatePickerMenu(picker);

            picker.classList.add("open");
            trigger?.setAttribute("aria-expanded", "true");
            const block = picker.closest(".field-block");
            const row = picker.closest(".field-row");
            const panel = picker.closest(".form-panel");
            block?.classList.add("has-open-date-menu");
            row?.classList.add("has-open-date-menu");
            panel?.classList.add("has-open-date-menu");
            renderDatePicker(picker);
            if (menu) {
                const gradient = getComputedStyle(picker).getPropertyValue("--calendar-month-gradient");
                menu.style.setProperty("--calendar-month-gradient", gradient);
                menu.classList.add("is-open");
                if (menu.parentElement !== document.body) {
                    document.body.appendChild(menu);
                }
            }
            positionDatePickerMenu(picker);
        }

        function repositionOpenDatePickers() {
            datePickers.forEach((picker) => {
                if (picker.classList.contains("open")) {
                    positionDatePickerMenu(picker);
                }
            });
        }

        function buildDatePicker(picker) {
            const trigger = picker.querySelector(".date-trigger");
            const prevButton = picker.querySelector(".prev-month");
            const nextButton = picker.querySelector(".next-month");
            const todayButton = picker.querySelector(".today-action");
            const clearButton = picker.querySelector(".clear-action");
            const hiddenInput = picker.querySelector("input[type='hidden']");
            picker._dateMenu = picker.querySelector(".date-menu");

            picker._viewDate = parseValueDate(hiddenInput.value) || new Date();
            syncDatePicker(picker);
            renderDatePicker(picker);

            trigger.addEventListener("click", () => {
                if (picker.classList.contains("is-locked")) {
                    return;
                }
                const isOpen = picker.classList.contains("open");
                closeDatePickers();
                if (!isOpen) {
                    openDatePicker(picker);
                }
            });

            trigger.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    if (picker.classList.contains("is-locked")) {
                        return;
                    }
                    const isOpen = picker.classList.contains("open");
                    closeDatePickers();
                    if (!isOpen) {
                        openDatePicker(picker);
                    }
                }
            });

            prevButton.addEventListener("click", () => {
                const minimumViewDate = getMinimumViewDate(hiddenInput);
                const previousViewDate = new Date(picker._viewDate.getFullYear(), picker._viewDate.getMonth() - 1, 1);

                if (previousViewDate < minimumViewDate) {
                    picker._viewDate = new Date(minimumViewDate);
                    renderDatePicker(picker);
                    positionDatePickerMenu(picker, true);
                    return;
                }

                picker._viewDate = previousViewDate;
                renderDatePicker(picker);
                positionDatePickerMenu(picker, true);
            });

            nextButton.addEventListener("click", () => {
                picker._viewDate = new Date(picker._viewDate.getFullYear(), picker._viewDate.getMonth() + 1, 1);
                renderDatePicker(picker);
                positionDatePickerMenu(picker, true);
            });

            todayButton.addEventListener("click", () => {
                const today = new Date();
                hiddenInput.value = formatValueDate(today);
                picker._viewDate = new Date(today.getFullYear(), today.getMonth(), 1);
                handleDateChange(hiddenInput);
                closeDatePickers();
            });

            clearButton.addEventListener("click", () => {
                hiddenInput.value = "";
                picker._viewDate = new Date();
                handleDateChange(hiddenInput);
                closeDatePickers();
            });
        }

        function closeTimeSelectMenus() {
            timeSelectDropdowns.forEach((dropdown) => {
                dropdown.classList.remove("open");
                const trigger = dropdown.querySelector(".custom-select-trigger");
                trigger.setAttribute("aria-expanded", "false");
            });
            document.querySelectorAll(".field-row.has-open-time-menu, .form-panel.has-open-time-menu").forEach((element) => {
                element.classList.remove("has-open-time-menu");
            });
        }

        function syncTimeSelect(dropdown) {
            const nativeSelect = dropdown.querySelector("select");
            const valueElement = dropdown.querySelector(".custom-select-value");
            const options = dropdown.querySelectorAll(".custom-option");
            const selectedOption = nativeSelect.options[nativeSelect.selectedIndex];

            valueElement.textContent = selectedOption ? selectedOption.textContent : nativeSelect.options[0].textContent;

            options.forEach((option) => {
                option.classList.toggle("selected", option.dataset.value === nativeSelect.value);
            });
        }

        function renderTimeSelectMenu(dropdown) {
            const nativeSelect = dropdown.querySelector("select");
            const menu = dropdown.querySelector(".custom-select-menu");

            if (!nativeSelect || !menu) {
                return;
            }

            const menuLabel = dropdown.dataset.menuLabel || "Select";
            menu.innerHTML = "";
            menu.setAttribute("data-menu-label", menuLabel);

            Array.from(nativeSelect.options).forEach((option, index) => {
                const isResetOption = !option.value && index === 0 && (menuLabel === "Hour" || menuLabel === "Minute");

                if (!option.value && index === 0 && !isResetOption) {
                    return;
                }

                const optionButton = document.createElement("button");
                optionButton.type = "button";
                optionButton.className = "custom-option";
                optionButton.dataset.value = option.value;

                const title = document.createElement("span");
                title.className = "option-title";
                title.textContent = isResetOption ? menuLabel : option.textContent;
                optionButton.appendChild(title);

                optionButton.addEventListener("click", () => {
                    nativeSelect.value = option.value;
                    syncTimeSelect(dropdown);
                    closeTimeSelectMenus();
                    nativeSelect.dispatchEvent(new Event("change", { bubbles: true }));
                });

                menu.appendChild(optionButton);
            });
        }

        function buildTimeSelect(dropdown) {
            const nativeSelect = dropdown.querySelector("select");
            const trigger = dropdown.querySelector(".custom-select-trigger");
            const menu = dropdown.querySelector(".custom-select-menu");

            if (!nativeSelect || !trigger || !menu) {
                return;
            }

            renderTimeSelectMenu(dropdown);

            if (dropdown.dataset.bound === "true") {
                syncTimeSelect(dropdown);
                return;
            }

            trigger.addEventListener("click", () => {
                const isOpen = dropdown.classList.contains("open");
                closeTimeSelectMenus();
                if (!isOpen) {
                    dropdown.classList.add("open");
                    trigger.setAttribute("aria-expanded", "true");
                    const row = dropdown.closest(".field-row");
                    const panel = dropdown.closest(".form-panel");
                    row?.classList.add("has-open-time-menu");
                    panel?.classList.add("has-open-time-menu");
                }
            });

            trigger.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    const isOpen = dropdown.classList.contains("open");
                    closeTimeSelectMenus();
                    if (!isOpen) {
                        dropdown.classList.add("open");
                        trigger.setAttribute("aria-expanded", "true");
                        const row = dropdown.closest(".field-row");
                        const panel = dropdown.closest(".form-panel");
                        row?.classList.add("has-open-time-menu");
                        panel?.classList.add("has-open-time-menu");
                    }
                }
            });

            dropdown.dataset.bound = "true";
            syncTimeSelect(dropdown);
        }

        function formatAppliedDateTime(value, monthStyle = "long") {
            const appliedDate = new Date(value);
            if (Number.isNaN(appliedDate.getTime())) {
                return "Unknown";
            }

            return appliedDate.toLocaleString("en-US", {
                month: monthStyle,
                day: "numeric",
                year: "numeric",
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
            });
        }

        function parseTimelineDate(value, { endOfFullDay = false } = {}) {
            if (!value) {
                return null;
            }

            const dateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
            if (dateOnlyMatch) {
                const [, year, month, day] = dateOnlyMatch.map(Number);
                const parsed = new Date(year, month - 1, day);
                if (endOfFullDay) {
                    parsed.setDate(parsed.getDate() + 1);
                }
                return parsed;
            }

            const parsed = new Date(value);
            return Number.isNaN(parsed.getTime()) ? null : parsed;
        }

        function formatClockTime(date) {
            return date.toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
                second: "2-digit",
                hour12: true
            });
        }

        function getDurationParts(milliseconds) {
            const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
            const days = Math.floor(totalSeconds / 86400);
            const hours = Math.floor((totalSeconds % 86400) / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;

            return { days, hours, minutes, seconds };
        }

        function formatDuration(milliseconds, { includeDays = true } = {}) {
            const { days, hours, minutes, seconds } = getDurationParts(milliseconds);
            const timeText = `${hours}h ${minutes}m ${seconds}s`;

            if (includeDays && days > 0) {
                return `${days}d ${timeText}`;
            }

            return timeText;
        }

        function animateLeaveProgress() {
            document.querySelectorAll(".leave-progress .progress-fill").forEach((bar) => {
                const startValue = bar.dataset.start || bar.dataset.from;
                const endValue = bar.dataset.end;
                if (!startValue) {
                    return;
                }

                const startDate = parseTimelineDate(startValue);
                if (!startDate) {
                    return;
                }

                const endDate = endValue
                    ? parseTimelineDate(endValue, { endOfFullDay: bar.dataset.fullDay === "true" })
                    : null;
                const now = new Date();
                let percent = 0;

                if (endDate && endDate > startDate) {
                    percent = ((now - startDate) / (endDate - startDate)) * 100;
                } else {
                    const totalDays = 30;
                    const diff = (startDate - now) / (1000 * 60 * 60 * 24);
                    percent = 100 - (diff * 100 / totalDays);
                }

                percent = Math.max(0, Math.min(100, percent));

                requestAnimationFrame(() => {
                    bar.style.width = `${percent}%`;
                });
            });
        }

        function updateLeaveTimelineStatus() {
            document.querySelectorAll(".leave-live-status").forEach((el) => {
                const isFullDay = el.dataset.kind === "full";
                const start = parseTimelineDate(el.dataset.start);
                const end = parseTimelineDate(el.dataset.end, { endOfFullDay: isFullDay });

                if (!start || !end) {
                    el.innerText = "";
                    return;
                }

                const now = new Date();

                if (now < start) {
                    const diff = start - now;
                    el.innerText = diff < 86400000
                        ? `Starts in ${formatDuration(diff, { includeDays: false })}`
                        : `${formatDuration(diff)} to start`;
                    el.dataset.state = "upcoming";
                    return;
                }

                if (now >= end) {
                    el.innerText = `Ended.. at ${formatClockTime(end)}`;
                    el.dataset.state = "ended";
                    return;
                }

                el.innerText = `Started.. ${formatDuration(end - now)} left`;
                el.dataset.state = "started";
            });
        }

        function startLeaveTimelineStatus() {
            updateLeaveTimelineStatus();
            animateLeaveProgress();
            setInterval(() => {
                updateLeaveTimelineStatus();
                animateLeaveProgress();
            }, 1000);
        }

        toggleBtn.addEventListener("click", () => {
            const collapsed = instructionCard.classList.toggle("collapsed");
            instructionContent.style.display = collapsed ? "none" : "block";
            toggleBtn.textContent = collapsed ? "Show" : "Hide";
        });

        if (window.matchMedia("(max-width: 640px)").matches) {
            instructionCard.classList.add("collapsed");
            instructionContent.style.display = "none";
            toggleBtn.textContent = "Show";
        }

        leaveTypeTrigger.addEventListener("click", () => {
            clearInlineWarning("leaveType");
            if (leaveTypeDropdown.classList.contains("open")) {
                closeLeaveTypeMenu();
            } else {
                openLeaveTypeMenu();
            }
        });

        leaveTypeTrigger.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                clearInlineWarning("leaveType");
                event.preventDefault();
                if (leaveTypeDropdown.classList.contains("open")) {
                    closeLeaveTypeMenu();
                } else {
                    openLeaveTypeMenu();
                }
            }
        });

        leaveTypeOptions.forEach((option) => {
            option.addEventListener("click", () => {
                setLeaveType(option.dataset.value);
                clearInlineWarning("leaveType");
                closeLeaveTypeMenu();
            });
        });

        document.addEventListener("click", (event) => {
            if (!leaveTypeDropdown.contains(event.target)) {
                closeLeaveTypeMenu();
            }

            if (!timeSelectDropdowns.some((dropdown) => dropdown.contains(event.target))) {
                closeTimeSelectMenus();
            }

            if (!datePickers.some((picker) => picker.contains(event.target))) {
                const clickedDateMenu = datePickers.some((picker) => getDatePickerMenu(picker)?.contains(event.target));
                if (!clickedDateMenu) {
                    closeDatePickers();
                }
            }
        });
        window.addEventListener("resize", () => {
            repositionOpenDatePickers();
            applyResponsiveUpcomingRows();
        });
        window.addEventListener("scroll", repositionOpenDatePickers, true);

        fromDate.addEventListener("change", () => handleDateChange(fromDate));
        toDate.addEventListener("change", () => handleDateChange(toDate));
        fromDate.addEventListener("change", () => clearInlineWarning("fromDate"));
        toDate.addEventListener("change", () => clearInlineWarning("toDate"));
        fromDatePicker.querySelector(".date-trigger")?.addEventListener("click", () => clearInlineWarning("fromDate"));
        toDatePicker.querySelector(".date-trigger")?.addEventListener("click", () => clearInlineWarning("toDate"));
        fromHour.addEventListener("change", () => {
            if (!fromHour.value) {
                clearStoredTimeForCurrentType();
            }
            if (fromDate.value) {
                const rules = getDateTimingRules();
                if (rules && !rules.unavailable) {
                    updateAMPM();
                    updateMinuteOptions(rules.isToday, rules.minHour, rules.minMinute);
                }
            }
            updateToTime();
        });
        fromMinute.addEventListener("change", () => {
            if (!fromMinute.value) {
                clearStoredTimeForCurrentType();
            }
            updateToTime();
        });
        fromMeridiem.addEventListener("change", updateAMPM);
        fromHour.addEventListener("change", () => clearInlineWarning("fromTime"));
        fromMinute.addEventListener("change", () => clearInlineWarning("fromTime"));
        fromMeridiem.addEventListener("change", () => clearInlineWarning("fromTime"));
        fromTimeBlock.querySelectorAll(".custom-select-trigger").forEach((trigger) => {
            trigger.addEventListener("click", () => clearInlineWarning("fromTime"));
        });
        reason.addEventListener("input", () => clearInlineWarning("reason"));
        timeSelectDropdowns.forEach(buildTimeSelect);
        datePickers.forEach(buildDatePicker);

        [fromTimeBlock, toTimeBlock].forEach((block) => {
            block.addEventListener("animationend", () => {
                if (block.classList.contains("leaving") && block.dataset.mode === "hidden") {
                    block.classList.add("hidden");
                    block.classList.remove("leaving");
                }

                block.classList.remove("entering");
            });
        });

        typeHint.addEventListener("animationend", () => {
            typeHint.classList.remove("hint-animating");
        });

        document.querySelectorAll(".applied-time").forEach((el) => {
            if (el.closest(".upcoming-card")) {
                return;
            }

            el.innerText = "Applied: " + formatAppliedDateTime(el.dataset.time);
        });

        applyResponsiveUpcomingRows();
        if (document.fonts?.ready) {
            document.fonts.ready.then(applyResponsiveUpcomingRows);
        }
        startLeaveTimelineStatus();

        function getResponsePath(responseUrl) {
            try {
                return new URL(responseUrl || window.location.href, window.location.href).pathname;
            } catch (error) {
                return "";
            }
        }

        function isMyLeavePath(responseUrl) {
            return getResponsePath(responseUrl).replace(/\/+$/, "") === "/my_leave";
        }

        function setSubmitButtonState(button, state, text) {
            if (!button) {
                return;
            }

            if (!button.dataset.defaultText) {
                button.dataset.defaultText = button.textContent.trim();
            }

            button.classList.toggle("is-processing", state === "processing");
            button.classList.toggle("is-success", state === "success");

            if (state === "processing") {
                button.innerHTML = '<span class="submit-btn-label">' + (text || "Submitting") + '</span><span class="submit-btn-dots" aria-hidden="true"><span>.</span><span>.</span><span>.</span></span><span class="submit-btn-spinner" aria-hidden="true"></span>';
            } else if (state === "success") {
                button.textContent = text || "Leave applied - opening My Leave";
            } else {
                button.textContent = text || button.dataset.defaultText || "Submit Leave";
            }
        }

        function resetSubmitButtonState(button) {
            if (!button) {
                return;
            }

            button.classList.remove("is-processing", "is-success");
            button.textContent = button.dataset.defaultText || "Submit Leave";
            button.disabled = false;
        }

        function redirectAfterApplyTone(targetUrl, submitButton) {
            try {
                window.sessionStorage.removeItem("leave-apply-success-tone-pending");
            } catch (error) {
                // Ignore storage failures.
            }

            setSubmitButtonState(submitButton, "success", "Leave applied - opening My Leave");

            if (typeof window.playLeaveActionTone === "function") {
                window.playLeaveActionTone("apply");
            }

            window.setTimeout(() => {
                window.location.href = targetUrl || "/my_leave/";
            }, 1250);
        }

        function redirectAfterErrorTone(targetUrl) {
            if (typeof window.playLeaveErrorTone === "function") {
                window.playLeaveErrorTone();
            }

            window.setTimeout(() => {
                if (targetUrl) {
                    window.location.href = targetUrl;
                } else {
                    window.location.reload();
                }
            }, 420);
        }

        async function readApplyResponse(response) {
            const contentType = response.headers.get("content-type") || "";

            if (contentType.includes("application/json")) {
                const payload = typeof window.parseJsonOrSessionExpired === "function"
                    ? await window.parseJsonOrSessionExpired(response)
                    : await response.json();
                return { response, payload };
            }

            return { response, payload: null };
        }

        form.addEventListener("submit", (event) => {
            clearAllInlineWarnings();

            let hasError = false;

            if (!leaveType.value) {
                showInlineWarning("leaveType", "Please select a leave type.");
                hasError = true;
            }

            if (!fromDate.value) {
                showInlineWarning("fromDate", "Please select a from date.");
                hasError = true;
            }

            if (!reason.value.trim()) {
                showInlineWarning("reason", "Please enter a reason.");
                hasError = true;
            }

            if (isTimeLeave()) {
                storeCurrentTimeForType(leaveType.value);
                toDate.value = fromDate.value;
                toDateHidden.value = fromDate.value;
                restoreStoredTimeForCurrentType(fromHour.value, fromMinute.value);

                const hasCurrentTimeState =
                    !!toTime.value &&
                    !!fromDateTime.value &&
                    !!toDateTime.value &&
                    !!fromHour.value &&
                    !!fromMinute.value;

                if (!hasCurrentTimeState) {
                    updateToTime();
                }

                if (!fromDateTime.value || !toDateTime.value) {
                    clearTimeFieldHighlights();
                    if (!fromHour.value) {
                        timeHourShell?.classList.add("invalid-time");
                    }
                    if (!fromMinute.value) {
                        timeMinuteShell?.classList.add("invalid-time");
                    }
                    if (!fromMeridiem.value) {
                        timeMeridiemShell?.classList.add("invalid-time");
                    }
                    showInlineWarning("fromTime", "Please choose a valid time.");
                    hasError = true;
                    event.preventDefault();
                }
            } else if (!toDate.value) {
                showInlineWarning("toDate", "Please select a to date.");
                hasError = true;
            }

            if (hasError) {
                event.preventDefault();
                if (typeof window.playLeaveErrorTone === "function") {
                    window.playLeaveErrorTone();
                }
                return;
            }

            event.preventDefault();

            if (form.dataset.submitting === "true") {
                return;
            }

            form.dataset.submitting = "true";
            const submitButton = event.submitter || form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
            }
            setSubmitButtonState(submitButton, "processing", "Submitting");

            fetch(form.action || window.location.href, {
                method: "POST",
                headers: {
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: new FormData(form),
                credentials: "same-origin"
            })
                .then(readApplyResponse)
                .then(({ response, payload }) => {
                    if (payload?.sessionExpired) {
                        if (typeof window.redirectAfterSessionExpired === "function") {
                            window.redirectAfterSessionExpired(payload);
                        }
                        return;
                    }

                    if (payload?.success === true) {
                        redirectAfterApplyTone(payload.redirect_url || response.url || "/my_leave/", submitButton);
                        return;
                    }

                    if (!payload && isMyLeavePath(response.url)) {
                        redirectAfterApplyTone(response.url, submitButton);
                        return;
                    }

                    form.dataset.submitting = "";
                    resetSubmitButtonState(submitButton);
                    redirectAfterErrorTone(response.url || window.location.href);
                })
                .catch(() => {
                    form.dataset.submitting = "";
                    resetSubmitButtonState(submitButton);
                    redirectAfterErrorTone(window.location.href);
                });
        });

        try {
            const shouldPlayApplySuccessTone = window.sessionStorage.getItem("leave-apply-success-tone-pending") === "1";
            const successFlashText = Array.from(document.querySelectorAll(".flash-success"))
                .map((flash) => flash.textContent || "")
                .join(" ");
            const hasApplySuccess = /leave\s+applied|applied\s+successfully|applied\s+range/i.test(successFlashText);

            if (shouldPlayApplySuccessTone && hasApplySuccess) {
                window.sessionStorage.removeItem("leave-apply-success-tone-pending");
                if (typeof window.playLeaveActionTone === "function") {
                    window.playLeaveActionTone("apply");
                }
            } else if (shouldPlayApplySuccessTone && document.querySelector(".flash-error, .flash-warning")) {
                window.sessionStorage.removeItem("leave-apply-success-tone-pending");
                if (typeof window.playLeaveErrorTone === "function") {
                    window.playLeaveErrorTone();
                }
            }
        } catch (error) {
            // Ignore storage/audio failures.
        }

        const savedFromDatetime = fromDateTime.value ? new Date(fromDateTime.value) : null;
        const applyLeaveConfig = document.getElementById("apply-leave-js-config");
        const initialLeaveType = leaveType.value || (applyLeaveConfig ? applyLeaveConfig.dataset.initialLeaveType : "");
        setLeaveType(initialLeaveType);

        if (savedFromDatetime instanceof Date && !Number.isNaN(savedFromDatetime.getTime()) && isTimeLeave()) {
            const selectedDate = formatValueDate(savedFromDatetime);
            if (!fromDate.value) {
                fromDate.value = selectedDate;
            }
            toDate.value = fromDate.value;
            generateTimeOptions();
            fromHour.value = String(savedFromDatetime.getHours());
            updateAMPM();
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            const selected = new Date(fromDate.value);
            selected.setHours(0, 0, 0, 0);
            const isToday = selected.getTime() === today.getTime();
            let minHour = 10;
            let minMinute = 0;
            if (isToday) {
                const minTime = new Date(Date.now() + (2 * 60 + 2) * 60 * 1000);
                const relaxedMin = new Date(minTime.getTime() - (7 * 60 * 1000));
                minHour = relaxedMin.getHours();
                minMinute = relaxedMin.getMinutes();
                if (minHour < 10) {
                    minHour = 10;
                    minMinute = 0;
                }
            }
            updateMinuteOptions(isToday, minHour, minMinute);
            fromMinute.value = String(savedFromDatetime.getMinutes());
            timeSelectDropdowns.forEach(syncTimeSelect);
            updateToTime();
        } else {
            handleDateChange(fromDate);
            timeSelectDropdowns.forEach(syncTimeSelect);
        }
}());

