    (function ()
    {
        const formShell = document.getElementById("employeeFormShell");
        const formToggle = document.getElementById("employeeFormToggle");
        const employeeForm = document.getElementById("employeeCreateForm");
        const sickTotalField = document.getElementById("sickTotalField");
        const earnedTotalField = document.getElementById("earnedTotalField");
        const totalLeaveField = document.getElementById("totalLeaveField");
        const totalLeaveRemainingField = document.getElementById("totalLeaveRemainingField");
        const createEmployeeButton = document.getElementById("createEmployeeButton");
        const phoneField = document.getElementById("phoneField");
        const submitWrap = document.getElementById("submitWrap");
        const searchInput = document.getElementById("employeeSearchInput");
        const searchStatusBox = document.getElementById("searchStatusBox");
        const employeeGrid = document.getElementById("employeeGrid");
        const pagination = document.getElementById("directoryPagination");
        const rosterPanel = document.getElementById("directoryRosterPanel");
        const addressModal = document.getElementById("addressModal");
        const addressModalTitle = document.getElementById("addressModalTitle");
        const addressModalText = document.getElementById("addressModalText");
        const addressModalPhoto = document.getElementById("addressModalPhoto");
        const addressModalInitials = document.getElementById("addressModalInitials");
        const addressModalEmployeeName = document.getElementById("addressModalEmployeeName");
        const addressModalEmployeeId = document.getElementById("addressModalEmployeeId");
        const addressModalEmployeeDepartment = document.getElementById("addressModalEmployeeDepartment");
        const addressModalEditButton = document.getElementById("addressModalEditButton");
        const addressModalEditForm = document.getElementById("addressModalEditForm");
        const addressModalTextarea = document.getElementById("addressModalTextarea");
        const notificationToggle = document.getElementById("notification-toggle");
        const notificationDropdown = document.querySelector(".notification-dropdown");
        const heroEmployeeTotal = document.getElementById("heroEmployeeTotal");
        const listEmployeeTotal = document.getElementById("listEmployeeTotal");
        const joinDatePicker = document.getElementById("employeeJoinDatePicker");
        const joinDateInput = document.getElementById("employeeJoinDate");
        const employeeDetailsConfig = document.getElementById("employee-details-js-config");
        const joinDateTodayString = employeeDetailsConfig ? employeeDetailsConfig.dataset.joinDateToday : "";
        const updateEmployeeContactUrlTemplate = employeeDetailsConfig ? employeeDetailsConfig.dataset.updateContactUrlTemplate : "";
        const employeeDetailUrlTemplate = employeeDetailsConfig ? employeeDetailsConfig.dataset.employeeDetailUrlTemplate : "";
        const ADDRESS_MODAL_ANIMATION_MS = 190;
        let currentPage = 1;
        let addressModalCloseTimer = null;
        let lastCardsPerPage = null;
        let directoryAnimationTimer = null;
        let activeAddressEmployeeId = "";
        const employeeCardRefreshInFlight = new Set();

        if (addressModal)
        {
            addressModal.hidden = false;
            addressModal.setAttribute("aria-hidden", "true");
            addressModal.classList.remove("is-open", "is-closing");
        }
        const employeeCards = employeeGrid ? Array.from(employeeGrid.querySelectorAll("[data-employee-card]")) : [];
        const employeePlaceholderCards = employeeGrid ? Array.from(employeeGrid.querySelectorAll(".employee-card-placeholder")) : [];

        function ensureFlashMessagesContainer()
        {
            let container = document.getElementById("flash-messages");

            if (!container)
            {
                container = document.createElement("div");
                container.id = "flash-messages";
                document.body.appendChild(container);
            }

            return container;
        }

        function dismissFlashMessage(flash)
        {
            if (!flash || flash.dataset.closing === "true")
            {
                return;
            }

            flash.dataset.closing = "true";
            flash.classList.add("flash-exit");
            setTimeout(function ()
            {
                if (flash.parentNode)
                {
                    flash.parentNode.removeChild(flash);
                }
            }, 220);
        }

        function renderFlashMessages(messages)
        {
            if (!Array.isArray(messages) || !messages.length)
            {
                return;
            }

            const container = ensureFlashMessagesContainer();

            messages.forEach(function (message, index)
            {
                const tags = String(message && message.tags ? message.tags : "").trim();
                const title = String(message && message.title ? message.title : "Update");
                const text = String(message && message.text ? message.text : "").trim();

                if (!text)
                {
                    return;
                }

                const flash = document.createElement("div");
                flash.className = "flash" + (tags ? " flash-" + tags : "");
                flash.setAttribute("data-flash", "");
                flash.innerHTML = [
                    '<span class="flash-accent" aria-hidden="true"></span>',
                    '<span class="flash-icon" aria-hidden="true"></span>',
                    '<div class="flash-copy">',
                    '<strong class="flash-title"></strong>',
                    '<p></p>',
                    '</div>',
                    '<button type="button" class="flash-dismiss" aria-label="Dismiss message">&times;</button>'
                ].join("");

                flash.querySelector(".flash-title").textContent = title;
                flash.querySelector("p").textContent = text;

                const dismissBtn = flash.querySelector(".flash-dismiss");
                if (dismissBtn)
                {
                    dismissBtn.addEventListener("click", function ()
                    {
                        dismissFlashMessage(flash);
                    });
                }

                container.appendChild(flash);

                setTimeout(function ()
                {
                    dismissFlashMessage(flash);
                }, 4200 + index * 250);
            });
        }

        function showEmployeeDetailsToast(title, text, tags)
        {
            renderFlashMessages([
                {
                    title: title || "Update failed",
                    text: text || "Unable to save changes.",
                    tags: tags || "error"
                }
            ]);
        }

        function getCardsPerPage()
        {
            return window.matchMedia("(max-width: 640px)").matches ? 6 : 10;
        }

        function animateDirectoryPageSwitch()
        {
            if (!employeeGrid)
            {
                return;
            }

            if (directoryAnimationTimer)
            {
                clearTimeout(directoryAnimationTimer);
            }

            employeeGrid.classList.remove("is-page-switching");
            requestAnimationFrame(function ()
            {
                employeeGrid.classList.add("is-page-switching");
                directoryAnimationTimer = setTimeout(function ()
                {
                    employeeGrid.classList.remove("is-page-switching");
                    directoryAnimationTimer = null;
                }, 260);
            });
        }

        function runRosterTransition(updateFn)
        {
            if (typeof updateFn !== "function")
            {
                return;
            }

            if (!rosterPanel || typeof window.startAsyncSurfaceSkeleton !== "function" || typeof window.finishAsyncSurfaceSkeleton !== "function")
            {
                updateFn();
                return;
            }

            window.startAsyncSurfaceSkeleton(rosterPanel);

            requestAnimationFrame(function ()
            {
                updateFn();

                requestAnimationFrame(function ()
                {
                    window.finishAsyncSurfaceSkeleton(rosterPanel);
                });
            });
        }
        let submitAttempted = false;
        let employeeCreateConfirmed = false;

        function getCsrfToken()
        {
            const tokenField = document.querySelector("input[name='csrfmiddlewaretoken']");
            return tokenField ? tokenField.value : "";
        }

        function getEmployeeUpdateUrl(employeeId)
        {
            return updateEmployeeContactUrlTemplate.replace(/0\/$/, String(employeeId) + "/");
        }

        function escapeHtml(value)
        {
            return String(value || "").replace(/[&<>"']/g, function (character)
            {
                return {
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    "\"": "&quot;",
                    "'": "&#39;"
                }[character] || character;
            });
        }

        function renderAddressPreview(address, details)
        {
            const text = String(address || "").trim() || "Address not added yet.";
            if (text.length <= 48)
            {
                return escapeHtml(text);
            }
            const moreAttributes = [
                'type="button"',
                'class="inline-more-btn"',
                'data-address-more',
                'data-employee-name="' + escapeHtml(details.employeeName || "") + '"',
                'data-employee-id="' + escapeHtml(details.employeeCode || "") + '"',
                'data-employee-department="' + escapeHtml(details.department || "") + '"',
                'data-employee-photo="' + escapeHtml(details.photo || "") + '"',
                'data-employee-username="' + escapeHtml(details.username || "") + '"',
                'data-address="' + escapeHtml(text) + '"'
            ];
            return escapeHtml(text.slice(0, 48)) + '...<button ' + moreAttributes.join(" ") + '>more</button>';
        }

        function bindAddressMoreButtons(scope)
        {
            (scope || document).querySelectorAll("[data-address-more]").forEach(function (button)
            {
                if (button.dataset.boundAddressMore === "true")
                {
                    return;
                }
                button.dataset.boundAddressMore = "true";
                button.addEventListener("click", function (event)
                {
                    event.preventDefault();
                    event.stopPropagation();
                    openAddressModal({
                        employeeName: button.dataset.employeeName || "Employee",
                        employeeUsername: button.dataset.employeeUsername || "",
                        employeeId: button.dataset.employeeId || "",
                        employeeDepartment: button.dataset.employeeDepartment || "",
                        employeePhoto: button.dataset.employeePhoto || "",
                        address: button.dataset.address || "",
                        employeeUserId: button.closest("[data-employee-card]") ? button.closest("[data-employee-card]").dataset.employeeId : ""
                    });
                });
            });
        }

        function setInlineEditState(container, editing)
        {
            const display = container.querySelector("[data-inline-edit-display]");
            const form = container.querySelector("[data-inline-edit-form]");
            const openButton = container.querySelector("[data-inline-edit-open]");
            if (display) display.hidden = !!editing;
            if (form) form.hidden = !editing;
            if (openButton) openButton.setAttribute("aria-pressed", editing ? "true" : "false");
            container.classList.toggle("is-inline-editing", !!editing);
            if (editing && form)
            {
                const firstField = form.querySelector("input, textarea");
                if (firstField)
                {
                    firstField.focus();
                    if (typeof firstField.select === "function")
                    {
                        firstField.select();
                    }
                }
            }
        }

        function submitInlineEdit(container)
        {
            if (!container || container.dataset.inlineEditSaving === "true")
            {
                return Promise.resolve();
            }
            const employeeId = container.dataset.employeeId;
            const fieldName = container.dataset.inlineEditField;
            const form = container.querySelector("[data-inline-edit-form]");
            const field = form ? form.querySelector("input, textarea") : null;
            const value = field ? field.value.trim() : "";
            container.dataset.inlineEditSaving = "true";
            return saveEmployeeField(employeeId, fieldName, value).then(function (data)
            {
                const card = container.closest("[data-employee-card]");
                if (card)
                {
                    if (fieldName === "phone")
                    {
                        syncPhoneDisplay(card, data.value);
                    }
                    if (fieldName === "address")
                    {
                        syncAddressDisplay(card, data.value);
                        if (String(activeAddressEmployeeId) === String(employeeId))
                        {
                            addressModalText.textContent = data.value;
                            if (addressModalTextarea)
                            {
                                addressModalTextarea.value = data.value;
                            }
                        }
                    }
                }
                setInlineEditState(container, false);
            }).catch(function (error)
            {
                showEmployeeDetailsToast("Unable to save", error.message || "Unable to save changes.", "error");
            }).finally(function ()
            {
                delete container.dataset.inlineEditSaving;
            });
        }

        function saveEmployeeField(employeeId, fieldName, fieldValue)
        {
            return fetch(getEmployeeUpdateUrl(employeeId), {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: new URLSearchParams({
                    field: fieldName,
                    value: fieldValue
                })
            }).then(function (response)
            {
                return response.json().then(function (data)
                {
                    if (!response.ok)
                    {
                        throw new Error(data.detail || "Unable to save changes.");
                    }
                    return data;
                });
            });
        }

        function updateTotalLeave()
        {
            const sick = parseFloat(sickTotalField ? sickTotalField.value : "0");
            const earned = parseFloat(earnedTotalField ? earnedTotalField.value : "0");
            const total = (Number.isFinite(sick) ? sick : 0) + (Number.isFinite(earned) ? earned : 0);
            if (totalLeaveField)
            {
                totalLeaveField.value = String(total % 1 === 0 ? total.toFixed(0) : total.toFixed(2).replace(/0+$/, "").replace(/\.$/, ""));
            }
            if (totalLeaveRemainingField)
            {
                totalLeaveRemainingField.value = String(total % 1 === 0 ? total.toFixed(0) : total.toFixed(2).replace(/0+$/, "").replace(/\.$/, ""));
            }
        }

        function parseValueDate(value)
        {
            if (!value) return null;
            const parts = String(value).split("-");
            if (parts.length !== 3) return null;
            const parsed = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
            return Number.isNaN(parsed.getTime()) ? null : parsed;
        }

        function formatValueDate(date)
        {
            return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0");
        }

        function formatDisplayDate(date)
        {
            return String(date.getDate()).padStart(2, "0") + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + date.getFullYear();
        }

        function getTodayReferenceDate()
        {
            const browserToday = new Date();
            const normalizedBrowserToday = new Date(browserToday.getFullYear(), browserToday.getMonth(), browserToday.getDate());
            const parsed = parseValueDate(joinDateTodayString);
            if (parsed)
            {
                const serverToday = new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
                return normalizedBrowserToday > serverToday ? normalizedBrowserToday : serverToday;
            }
            return normalizedBrowserToday;
        }

        function getDefaultJoinViewDate()
        {
            const selectedDate = parseValueDate(joinDateInput ? joinDateInput.value : "");
            const sourceDate = selectedDate || getTodayReferenceDate();
            return new Date(sourceDate.getFullYear(), sourceDate.getMonth(), 1);
        }

        function clampJoinViewDate(viewDate)
        {
            const normalizedView = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
            const minView = getDefaultJoinViewDate();
            return normalizedView < minView ? minView : normalizedView;
        }

        function closeJoinDatePicker()
        {
            if (!joinDatePicker) return;
            const wasOpenUp = joinDatePicker.classList.contains("open-up");
            joinDatePicker.classList.remove("open");
            const trigger = joinDatePicker.querySelector(".date-trigger");
            if (trigger) trigger.setAttribute("aria-expanded", "false");
            window.clearTimeout(joinDatePicker._closeTimer);
            joinDatePicker._closeTimer = window.setTimeout(function ()
            {
                if (!joinDatePicker.classList.contains("open"))
                {
                    joinDatePicker.classList.remove("open-up");
                }
            }, wasOpenUp ? 230 : 10);
        }

        function syncJoinDatePicker()
        {
            if (!joinDatePicker || !joinDateInput) return;
            const valueElement = joinDatePicker.querySelector(".date-value");
            const selectedDate = parseValueDate(joinDateInput.value);
            if (valueElement) valueElement.textContent = selectedDate ? formatDisplayDate(selectedDate) : "dd-mm-yyyy";
        }

        function renderJoinDatePicker()
        {
            if (!joinDatePicker || !joinDateInput) return;
            const currentLabel = joinDatePicker.querySelector(".date-current");
            const grid = joinDatePicker.querySelector(".date-grid");
            const selectedDate = parseValueDate(joinDateInput.value);
            const today = getTodayReferenceDate();
            const viewDate = clampJoinViewDate(joinDatePicker._viewDate || getDefaultJoinViewDate());
            joinDatePicker._viewDate = viewDate;
            const monthStart = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
            const monthEnd = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0);
            const firstDayIndex = (monthStart.getDay() + 6) % 7;
            const daysInMonth = monthEnd.getDate();
            const minDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());

            if (currentLabel)
            {
                currentLabel.textContent = monthStart.toLocaleDateString("en-US", { month: "long", year: "numeric" });
            }
            const prevButton = joinDatePicker.querySelector(".prev-month");
            if (prevButton)
            {
                const minView = getDefaultJoinViewDate();
                prevButton.disabled = viewDate.getFullYear() === minView.getFullYear() && viewDate.getMonth() === minView.getMonth();
            }
            if (!grid) return;
            grid.innerHTML = "";

            for (let i = 0; i < firstDayIndex; i += 1)
            {
                const blankCell = document.createElement("button");
                blankCell.type = "button";
                blankCell.className = "date-day muted";
                blankCell.disabled = true;
                grid.appendChild(blankCell);
            }

            for (let day = 1; day <= daysInMonth; day += 1)
            {
                const date = new Date(viewDate.getFullYear(), viewDate.getMonth(), day);
                const dayButton = document.createElement("button");
                dayButton.type = "button";
                dayButton.className = "date-day";
                dayButton.textContent = String(day);

                const isToday = date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() && date.getDate() === today.getDate();
                const isWeekend = date.getDay() === 0 || date.getDay() === 6;
                const isSelected = selectedDate && date.getFullYear() === selectedDate.getFullYear() && date.getMonth() === selectedDate.getMonth() && date.getDate() === selectedDate.getDate();
                const isPast = date < minDate;

                if (isToday) dayButton.classList.add("today");
                if (isWeekend) dayButton.classList.add("weekend");
                if (isSelected) dayButton.classList.add("selected");
                if (isPast)
                {
                    dayButton.classList.add("muted");
                    dayButton.disabled = true;
                }

                if (!isPast) dayButton.addEventListener("click", function ()
                {
                    joinDateInput.value = formatValueDate(date);
                    joinDatePicker._viewDate = new Date(date.getFullYear(), date.getMonth(), 1);
                    syncJoinDatePicker();
                    clearFieldError(joinDateInput);
                    validateRequiredFields(submitAttempted);
                    closeJoinDatePicker();
                });

                grid.appendChild(dayButton);
            }

        }

        function buildJoinDatePicker()
        {
            if (!joinDatePicker || !joinDateInput) return;
            const trigger = joinDatePicker.querySelector(".date-trigger");
            const prevButton = joinDatePicker.querySelector(".prev-month");
            const nextButton = joinDatePicker.querySelector(".next-month");
            const todayButton = joinDatePicker.querySelector(".today-action");
            const clearButton = joinDatePicker.querySelector(".clear-action");

            joinDatePicker._viewDate = clampJoinViewDate(getDefaultJoinViewDate());
            syncJoinDatePicker();
            renderJoinDatePicker();

            function openPicker()
            {
                const isOpen = joinDatePicker.classList.contains("open");
                closeJoinDatePicker();
                if (isOpen) return;
                joinDatePicker._viewDate = clampJoinViewDate(getDefaultJoinViewDate());
                window.clearTimeout(joinDatePicker._closeTimer);
                const dateMenu = joinDatePicker.querySelector(".date-menu");
                const shellRect = joinDatePicker.getBoundingClientRect();
                const menuHeight = dateMenu ? Math.max(dateMenu.offsetHeight || 0, 318) : 318;
                const viewportPadding = 18;
                const spaceBelow = window.innerHeight - shellRect.bottom - viewportPadding;
                const spaceAbove = shellRect.top - viewportPadding;
                const openUp = spaceAbove >= menuHeight || spaceAbove >= spaceBelow;

                joinDatePicker.classList.toggle("open-up", openUp);
                joinDatePicker.classList.add("open");
                if (trigger) trigger.setAttribute("aria-expanded", "true");
                renderJoinDatePicker();
            }

            if (trigger)
            {
                trigger.addEventListener("click", openPicker);
                trigger.addEventListener("keydown", function (event)
                {
                    if (event.key === "Enter" || event.key === " ")
                    {
                        event.preventDefault();
                        openPicker();
                    }
                });
            }

            if (prevButton) prevButton.addEventListener("click", function ()
            {
                joinDatePicker._viewDate = clampJoinViewDate(new Date(joinDatePicker._viewDate.getFullYear(), joinDatePicker._viewDate.getMonth() - 1, 1));
                renderJoinDatePicker();
            });

            if (nextButton) nextButton.addEventListener("click", function ()
            {
                joinDatePicker._viewDate = clampJoinViewDate(new Date(joinDatePicker._viewDate.getFullYear(), joinDatePicker._viewDate.getMonth() + 1, 1));
                renderJoinDatePicker();
            });

            if (todayButton) todayButton.addEventListener("click", function ()
            {
                const today = getTodayReferenceDate();
                joinDateInput.value = formatValueDate(today);
                joinDatePicker._viewDate = clampJoinViewDate(getDefaultJoinViewDate());
                syncJoinDatePicker();
                clearFieldError(joinDateInput);
                validateRequiredFields(submitAttempted);
                closeJoinDatePicker();
            });

            if (clearButton) clearButton.addEventListener("click", function ()
            {
                joinDateInput.value = "";
                joinDatePicker._viewDate = clampJoinViewDate(getDefaultJoinViewDate());
                syncJoinDatePicker();
                validateRequiredFields(submitAttempted);
                closeJoinDatePicker();
            });
        }

        function requiredFields()
        {
            return employeeForm ? Array.from(employeeForm.querySelectorAll("input[required]")) : [];
        }

        function normalizePhoneValue(value)
        {
            const digits = String(value || "").replace(/\D/g, "");
            const localDigits = digits.startsWith("91") ? digits.slice(2) : digits;
            return "+91 " + localDigits.slice(0, 10);
        }

        function ensurePhonePrefix()
        {
            if (!phoneField) return;
            phoneField.value = normalizePhoneValue(phoneField.value);
        }

        function setFieldError(input, message)
        {
            if (!input) return;
            input.setAttribute("aria-invalid", "true");
            const field = input.closest(".field");
            if (!field) return;
            let feedback = field.querySelector(".field-feedback.client-feedback");
            if (!feedback)
            {
                feedback = document.createElement("div");
                feedback.className = "field-feedback client-feedback";
                field.appendChild(feedback);
            }
            const messageNode = document.createElement("p");
            messageNode.textContent = message;
            feedback.replaceChildren(messageNode);
        }

        function clearFieldError(input)
        {
            if (!input) return;
            const field = input.closest(".field");
            const feedback = field ? field.querySelector(".field-feedback.client-feedback") : null;
            if (feedback) feedback.remove();
            if (!field || !field.querySelector(".field-feedback"))
            {
                input.setAttribute("aria-invalid", "false");
            }
        }

        function getFieldLabel(input)
        {
            const field = input ? input.closest(".field") : null;
            const label = field ? field.querySelector("span") : null;
            return label ? label.textContent.trim() : "Required field";
        }

        function syncFieldAccentState(input)
        {
            if (!input) return;
            const field = input.closest(".field");
            if (!field) return;

            let hasValue = false;
            if (input === phoneField)
            {
                const digits = String(input.value || "").replace(/\D/g, "");
                hasValue = digits.length > 2;
            }
            else
            {
                hasValue = String(input.value || "").trim().length > 0;
            }

            field.classList.toggle("has-value", hasValue);
        }

        function syncAllFieldAccentStates()
        {
            requiredFields().forEach(syncFieldAccentState);
            if (joinDateInput) syncFieldAccentState(joinDateInput);
        }

        function validateRequiredFields(showErrors)
        {
            let allValid = true;
            const issues = [];
            requiredFields().forEach(function (input)
            {
                const value = String(input.value || "").trim();
                const isPhone = input === phoneField;
                const phoneDigits = isPhone ? value.replace(/\D/g, "") : "";
                const phoneIsEmpty = isPhone ? phoneDigits.length <= 2 : false;
                const phoneIsInvalid = isPhone ? (phoneDigits.length > 2 && !/^91\d{10}$/.test(phoneDigits)) : false;

                if (!value || phoneIsEmpty)
                {
                    allValid = false;
                    const message = isPhone ? "Phone is required." : (getFieldLabel(input) + " is required.");
                    issues.push(message);
                    if (showErrors)
                    {
                        setFieldError(input, message);
                    }
                    else
                    {
                        clearFieldError(input);
                    }
                }
                else if (phoneIsInvalid)
                {
                    allValid = false;
                    issues.push("Phone must include a valid 10-digit Indian mobile number.");
                    if (showErrors)
                    {
                        setFieldError(input, "Phone must include a valid 10-digit Indian mobile number.");
                    }
                    else
                    {
                        clearFieldError(input);
                    }
                }
                else if (input.validity && !input.validity.valid)
                {
                    allValid = false;
                    const message = input.validationMessage || (getFieldLabel(input) + " is invalid.");
                    issues.push(message);
                    if (showErrors)
                    {
                        setFieldError(input, message);
                    }
                    else
                    {
                        clearFieldError(input);
                    }
                }
                else
                {
                    clearFieldError(input);
                }
            });

            const passwordField = document.getElementById("passwordField");
            const confirmPasswordField = document.getElementById("confirmPasswordField");
            if (passwordField && confirmPasswordField && passwordField.value && confirmPasswordField.value && passwordField.value !== confirmPasswordField.value)
            {
                allValid = false;
                issues.push("Confirm password does not match password.");
                if (showErrors)
                {
                    setFieldError(confirmPasswordField, "Password confirmation does not match.");
                }
            }

            if (createEmployeeButton)
            {
                createEmployeeButton.disabled = !allValid;
            }
            if (submitWrap)
            {
                submitWrap.dataset.tooltip = allValid ? "" : issues.join("\n");
            }
            return allValid;
        }

        function updateEmployeeTotals(totalOverride)
        {
            const total = typeof totalOverride === "number"
                ? totalOverride
                : (employeeGrid ? employeeGrid.querySelectorAll("[data-employee-card]").length : 0);
            const safeTotal = Number.isFinite(Number(total)) ? Number(total) : 0;
            if (heroEmployeeTotal)
            {
                heroEmployeeTotal.dataset.countupTarget = String(safeTotal);
                heroEmployeeTotal.textContent = String(safeTotal);
                if (typeof window.animateCountUp === "function")
                {
                    window.animateCountUp(heroEmployeeTotal, safeTotal, { duration: 280 });
                }
                else
                {
                    heroEmployeeTotal.textContent = String(safeTotal);
                }
            }
            if (listEmployeeTotal)
            {
                listEmployeeTotal.dataset.countupTarget = String(safeTotal);
                listEmployeeTotal.dataset.count = String(safeTotal);
                listEmployeeTotal.textContent = String(safeTotal) + " employees";
                if (typeof window.animateCountUp === "function")
                {
                    window.animateCountUp(listEmployeeTotal, safeTotal, { suffix: " employees", duration: 280 });
                }
                else
                {
                    listEmployeeTotal.textContent = String(safeTotal) + " employees";
                }
            }

            document.dispatchEvent(new CustomEvent("countup:refresh", {
                detail: {
                    root: document,
                    duration: 180
                }
            }));
        }

        function filteredCards()
        {
            return employeeCards.filter(function (card)
            {
                return !card.dataset.filteredOut;
            });
        }

        function renderPagination()
        {
            if (!pagination || !employeeGrid) return;
            const cards = filteredCards();
            const cardsPerPage = getCardsPerPage();
            const pageCount = Math.ceil(cards.length / cardsPerPage);
            if (pageCount <= 1)
            {
                pagination.hidden = true;
                pagination.innerHTML = "";
                cards.forEach(function (card) { card.hidden = false; });
                employeePlaceholderCards.forEach(function (card, index)
                {
                    card.hidden = !(cards.length > 0 && index < Math.max(0, cardsPerPage - cards.length));
                });
                requestAnimationFrame(applyResponsiveTrim);
                lastCardsPerPage = cardsPerPage;
                refreshVisibleEmployeeCards();
                return;
            }

            pagination.hidden = false;
            currentPage = Math.min(currentPage, pageCount);
            const start = (currentPage - 1) * cardsPerPage;
            const end = start + cardsPerPage;
            const visibleCards = cards.slice(start, end);
            employeeCards.forEach(function (card)
            {
                card.hidden = visibleCards.indexOf(card) === -1;
            });
            employeePlaceholderCards.forEach(function (card, index)
            {
                card.hidden = index >= Math.max(0, cardsPerPage - visibleCards.length);
            });
            requestAnimationFrame(applyResponsiveTrim);
            refreshVisibleEmployeeCards();

            pagination.innerHTML = "";
            const first = document.createElement("button");
            first.type = "button";
            first.className = "page-btn page-nav-btn";
            first.innerHTML = '<span aria-hidden="true">&laquo;</span><span>First</span>';
            first.disabled = currentPage === 1;
            first.addEventListener("click", function ()
            {
                runRosterTransition(function ()
                {
                    currentPage = 1;
                    renderPagination();
                    animateDirectoryPageSwitch();
                });
            });
            pagination.appendChild(first);

            const prev = document.createElement("button");
            prev.type = "button";
            prev.className = "page-btn page-nav-btn";
            prev.innerHTML = '<span aria-hidden="true">&lsaquo;</span><span>Prev</span>';
            prev.disabled = currentPage === 1;
            prev.addEventListener("click", function ()
            {
                runRosterTransition(function ()
                {
                    currentPage -= 1;
                    renderPagination();
                    animateDirectoryPageSwitch();
                });
            });
            pagination.appendChild(prev);

            const status = document.createElement("span");
            status.className = "page-status";
            status.textContent = "Page " + currentPage + " of " + pageCount;
            pagination.appendChild(status);

            const next = document.createElement("button");
            next.type = "button";
            next.className = "page-btn page-nav-btn";
            next.innerHTML = '<span>Next</span><span aria-hidden="true">&rsaquo;</span>';
            next.disabled = currentPage === pageCount;
            next.addEventListener("click", function ()
            {
                runRosterTransition(function ()
                {
                    currentPage += 1;
                    renderPagination();
                    animateDirectoryPageSwitch();
                });
            });
            pagination.appendChild(next);

            const last = document.createElement("button");
            last.type = "button";
            last.className = "page-btn page-nav-btn";
            last.innerHTML = '<span>Last</span><span aria-hidden="true">&raquo;</span>';
            last.disabled = currentPage === pageCount;
            last.addEventListener("click", function ()
            {
                runRosterTransition(function ()
                {
                    currentPage = pageCount;
                    renderPagination();
                    animateDirectoryPageSwitch();
                });
            });
            pagination.appendChild(last);
            lastCardsPerPage = cardsPerPage;
        }

        function runSearch()
        {
            if (!employeeGrid) return;
            const query = String(searchInput ? searchInput.value : "").trim().toLowerCase().replace(/\s+/g, " ");
            let matchCount = 0;
            employeeCards.forEach(function (card)
            {
                const haystack = String(card.dataset.search || "").replace(/\s+/g, " ");
                const matched = !query || haystack.includes(query);
                if (matched)
                {
                    matchCount += 1;
                    delete card.dataset.filteredOut;
                }
                else
                {
                    card.dataset.filteredOut = "true";
                    card.hidden = true;
                }
            });

            if (searchStatusBox)
            {
                searchStatusBox.hidden = !(query && matchCount === 0);
            }
            updateEmployeeTotals(matchCount);
            currentPage = 1;
            renderPagination();
        }

        function toggleFormShell()
        {
            if (!formShell || !formToggle) return;
            
            // Activate 'Graphics Simplification' bridge for low-power performance
            formShell.classList.add("is-morphing");
            
            const isCollapsing = !formShell.classList.contains("is-collapsed");
            formShell.classList.toggle("is-collapsed");
            formToggle.setAttribute("aria-expanded", isCollapsing ? "false" : "true");
            
            // Restore full visual richness after the movement is complete
            setTimeout(function() {
                formShell.classList.remove("is-morphing");
            }, 200);
        }

        function getInitials(fullName, username)
        {
            const name = String(fullName || "").trim();
            const user = String(username || "EM").trim();
            const parts = name ? name.split(/\s+/).filter(Boolean) : [];
            if (parts.length >= 2)
            {
                return (parts[0][0] + parts[1][0]).toUpperCase();
            }
            if (parts.length === 1)
            {
                return parts[0].slice(0, 2).toUpperCase();
            }
            return user.slice(0, 2).toUpperCase();
        }

        function getEmployeeDetailUrl(employeeId)
        {
            return employeeDetailUrlTemplate.replace(/0\/?$/, String(employeeId) + "/");
        }

        function setEmployeeCardText(card, key, value)
        {
            const element = card ? card.querySelector('[data-employee-card-balance="' + key + '"]') : null;
            if (!element || element.textContent.trim() === value) return;

            element.textContent = value;
            element.classList.remove("count-pulse");
            void element.offsetWidth;
            element.classList.add("count-pulse");
        }

        function setEmployeeCardPhoto(card, employee)
        {
            const photoWrap = card ? card.querySelector("[data-employee-card-photo]") : null;
            if (!photoWrap || !employee) return;

            const displayName = employee.display_name || employee.username || "Employee";
            const username = employee.username || "";

            if (employee.photo_url)
            {
                let image = photoWrap.querySelector("img.employee-avatar");
                if (!image)
                {
                    image = document.createElement("img");
                    image.className = "employee-avatar";
                    photoWrap.replaceChildren(image);
                }
                if (image.getAttribute("src") !== employee.photo_url)
                {
                    image.src = employee.photo_url;
                }
                image.alt = displayName;
                return;
            }

            let fallback = photoWrap.querySelector(".employee-avatar-fallback");
            if (!fallback)
            {
                fallback = document.createElement("div");
                fallback.className = "employee-avatar employee-avatar-fallback";
                fallback.setAttribute("data-avatar-fallback", "");
                photoWrap.replaceChildren(fallback);
            }
            fallback.setAttribute("aria-label", displayName);
            fallback.dataset.fullName = displayName;
            fallback.dataset.username = username;
            fallback.textContent = getInitials(displayName, username);
        }

        function updateEmployeeCardSnapshot(card, employee)
        {
            setEmployeeCardPhoto(card, employee);
            setEmployeeCardText(card, "leave", String((employee.sick_used || 0) + (employee.earned_used || 0)) + " / " + String((employee.sick_total || 0) + (employee.earned_total || 0)) + " used");
            setEmployeeCardText(card, "sick", String(employee.sick_used || 0) + " / " + String(employee.sick_total || 0));
            setEmployeeCardText(card, "earned", String(employee.earned_used || 0) + " / " + String(employee.earned_total || 0));
            setEmployeeCardText(card, "unpaid", String(employee.unpaid_taken || 0));
        }

        function refreshEmployeeCard(card)
        {
            const employeeId = card ? String(card.dataset.employeeId || "") : "";
            if (!employeeId || !employeeDetailUrlTemplate || employeeCardRefreshInFlight.has(employeeId)) return;

            employeeCardRefreshInFlight.add(employeeId);
            fetch(getEmployeeDetailUrl(employeeId) + "?_ts=" + Date.now(), {
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache"
                },
                cache: "no-store"
            })
                .then(function (response)
                {
                    if (!response.ok) throw new Error("Unable to load latest employee card.");
                    return response.json();
                })
                .then(function (employee)
                {
                    updateEmployeeCardSnapshot(card, employee);
                })
                .catch(function ()
                {
                    return null;
                })
                .finally(function ()
                {
                    employeeCardRefreshInFlight.delete(employeeId);
                });
        }

        function refreshVisibleEmployeeCards()
        {
            if (document.hidden) return;
            employeeCards.filter(function (card)
            {
                return !card.hidden;
            }).forEach(refreshEmployeeCard);
        }

        function syncPhoneDisplay(card, phoneValue)
        {
            const display = card.querySelector('[data-inline-edit-field="phone"] [data-inline-edit-display]');
            const input = card.querySelector('[data-inline-edit-field="phone"] input[name="phone"]');
            const safePhone = String(phoneValue || "").trim() || "Not added";
            if (display)
            {
                display.innerHTML = '<a class="detail-link" data-phone-link href="tel:' + escapeHtml(safePhone.replace(/\s+/g, "")) + '">' + escapeHtml(safePhone) + "</a>";
            }
            if (input)
            {
                input.value = safePhone === "Not added" ? "" : safePhone;
            }
        }

        function syncAddressDisplay(card, addressValue)
        {
            const block = card.querySelector('[data-inline-edit-field="address"]');
            if (!block)
            {
                return;
            }
            const display = block.querySelector("[data-inline-edit-display]");
            const textarea = block.querySelector('textarea[name="address"]');
            const identityName = card.querySelector(".employee-identity h4");
            const employeeName = identityName ? (identityName.dataset.fullText || identityName.textContent || "Employee") : "Employee";
            const employeeCodeNode = card.querySelector(".meta-chips span");
            const departmentNode = card.querySelector(".meta-chip-department");
            const photoNode = card.querySelector(".employee-avatar");
            const usernameNode = card.querySelector(".employee-identity > p");
            const details = {
                employeeName: employeeName,
                employeeCode: employeeCodeNode ? employeeCodeNode.textContent.trim() : "",
                department: departmentNode ? (departmentNode.dataset.fullText || departmentNode.textContent.trim()) : "",
                photo: photoNode && photoNode.tagName === "IMG" ? photoNode.getAttribute("src") : "",
                username: usernameNode ? usernameNode.textContent.replace(/^@/, "").trim() : ""
            };
            if (display)
            {
                display.innerHTML = renderAddressPreview(addressValue, details);
                bindAddressMoreButtons(display);
            }
            if (textarea)
            {
                textarea.value = String(addressValue || "");
            }
        }

        function openAddressModal(details)
        {
            if (!addressModal) return;
            if (addressModalCloseTimer)
            {
                clearTimeout(addressModalCloseTimer);
                addressModalCloseTimer = null;
            }
            const employeeName = String(details && details.employeeName ? details.employeeName : "Employee").trim() || "Employee";
            const employeeUsername = String(details && details.employeeUsername ? details.employeeUsername : "").trim();
            const employeeId = String(details && details.employeeId ? details.employeeId : "Not available").trim();
            const employeeDepartment = String(details && details.employeeDepartment ? details.employeeDepartment : "Not specified").trim();
            const employeePhoto = String(details && details.employeePhoto ? details.employeePhoto : "").trim();
            const employeeAddress = String(details && details.address ? details.address : "").trim();
            activeAddressEmployeeId = String(details && details.employeeUserId ? details.employeeUserId : "").trim();

            addressModalTitle.textContent = "Address";
            addressModalText.textContent = employeeAddress;
            if (addressModalTextarea)
            {
                addressModalTextarea.value = employeeAddress;
            }
            if (addressModalEditForm)
            {
                addressModalEditForm.hidden = true;
            }
            if (addressModalText)
            {
                addressModalText.hidden = false;
            }
            if (addressModalEditButton)
            {
                addressModalEditButton.hidden = false;
            }
            addressModalEmployeeName.textContent = employeeName;
            addressModalEmployeeId.textContent = employeeId;
            addressModalEmployeeDepartment.textContent = employeeDepartment;

            if (employeePhoto)
            {
                addressModalPhoto.src = employeePhoto;
                addressModalPhoto.alt = employeeName;
                addressModalPhoto.hidden = false;
                addressModalInitials.hidden = true;
                addressModalInitials.textContent = "";
            }
            else
            {
                addressModalPhoto.hidden = true;
                addressModalPhoto.removeAttribute("src");
                addressModalPhoto.alt = "";
                addressModalInitials.hidden = false;
                addressModalInitials.textContent = getInitials(employeeName, employeeUsername);
            }

            addressModal.classList.remove("is-closing");
            addressModal.setAttribute("aria-hidden", "false");
            addressModal.classList.add("is-open");
        }

        function closeAddressModal()
        {
            if (!addressModal || !addressModal.classList.contains("is-open")) return;
            addressModal.classList.remove("is-open");
            addressModal.classList.add("is-closing");
            addressModal.setAttribute("aria-hidden", "true");
            addressModalCloseTimer = setTimeout(function ()
            {
                addressModal.classList.remove("is-closing");
                addressModalCloseTimer = null;
                activeAddressEmployeeId = "";
            }, ADDRESS_MODAL_ANIMATION_MS);
        }

        function getFilenameFromDisposition(disposition)
        {
            const match = String(disposition || "").match(/filename="?([^"]+)"?/i);
            return match ? match[1] : "";
        }

        function downloadBlob(blob, filename)
        {
            const objectUrl = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = objectUrl;
            if (filename)
            {
                link.download = filename;
            }
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(objectUrl);
        }

        async function downloadPdf(downloadUrl, filename, token)
        {
            const formData = new FormData();
            formData.append("token", token || "");

            const response = await fetch(downloadUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: formData
            });

            if (!response.ok)
            {
                throw new Error("Archive download failed");
            }

            const blob = await response.blob();
            const responseFilename = getFilenameFromDisposition(response.headers.get("Content-Disposition"));
            downloadBlob(blob, filename || responseFilename || "employee-archive.pdf");
        }

        function applyAvatarInitials()
        {
            document.querySelectorAll("[data-avatar-fallback]").forEach(function (element)
            {
                const fullName = String(element.dataset.fullName || "").trim();
                const username = String(element.dataset.username || "EM").trim();
                const parts = fullName ? fullName.split(/\s+/).filter(Boolean) : [];
                let initials = "";
                if (parts.length >= 2)
                {
                    initials = (parts[0][0] + parts[1][0]).toUpperCase();
                }
                else if (parts.length === 1)
                {
                    initials = parts[0].slice(0, 2).toUpperCase();
                }
                else
                {
                    initials = username.slice(0, 2).toUpperCase();
                }
                element.textContent = initials;
            });
        }

        function applyResponsiveTrim()
        {
            document.querySelectorAll("[data-responsive-trim]").forEach(function (element)
            {
                const fullText = String(element.dataset.fullText || element.textContent || "").trim();
                if (!fullText)
                {
                    return;
                }

                element.textContent = fullText;
                if (element.offsetParent === null)
                {
                    return;
                }

                let availableWidth = element.clientWidth;
                if (element.classList.contains("meta-chip-department"))
                {
                    const chipsRow = element.closest(".meta-chips");
                    const idChip = chipsRow ? chipsRow.querySelector("span:first-child") : null;
                    if (chipsRow)
                    {
                        const rowStyle = window.getComputedStyle(chipsRow);
                        const gap = parseFloat(rowStyle.columnGap || rowStyle.gap || "0") || 0;
                        const rowWidth = chipsRow.clientWidth;
                        const idWidth = idChip ? idChip.offsetWidth : 0;
                        availableWidth = Math.max(24, rowWidth - idWidth - gap);
                        element.style.maxWidth = availableWidth + "px";
                    }
                }
                else
                {
                    element.style.maxWidth = "";
                }

                if (availableWidth <= 0)
                {
                    return;
                }

                if (element.scrollWidth <= availableWidth)
                {
                    return;
                }

                let low = 1;
                let high = fullText.length;
                let best = fullText;

                while (low <= high)
                {
                    const mid = Math.floor((low + high) / 2);
                    const candidate = fullText.slice(0, mid).trimEnd() + "..";
                    element.textContent = candidate;

                    if (element.scrollWidth <= availableWidth)
                    {
                        best = candidate;
                        low = mid + 1;
                    }
                    else
                    {
                        high = mid - 1;
                    }
                }

                element.textContent = best;
            });
        }

        function bindDeleteButtons()
        {
            document.querySelectorAll("[data-delete-employee]").forEach(function (button)
            {
                if (button.dataset.boundDelete === "true") return;
                button.dataset.boundDelete = "true";
                button.addEventListener("click", async function ()
                {
                    const card = button.closest("[data-employee-card]");
                    const deleteUrl = button.dataset.deleteUrl;
                    const employeeName = button.dataset.employeeName || "this employee";
                    if (!card || !deleteUrl) return;
                    const shouldDelete = typeof window.showThemeConfirm === "function"
                        ? await window.showThemeConfirm("Delete " + employeeName + "? A PDF archive will download before the record is removed.", {
                            title: "Delete employee",
                            confirmText: "Delete",
                            variant: "delete"
                        })
                        : window.confirm("Delete " + employeeName + "? A PDF archive will download before the record is removed.");
                    if (!shouldDelete) return;

                    fetch(deleteUrl, {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": getCsrfToken(),
                            "X-Requested-With": "XMLHttpRequest"
                        }
                    })
                        .then(function (response)
                        {
                            if (!response.ok) throw new Error("Delete failed");
                            return response.json();
                        })
                        .then(function (payload)
                        {
                            if (payload.download_url && payload.download_token)
                            {
                                return downloadPdf(payload.download_url, payload.filename, payload.download_token)
                                    .then(function ()
                                    {
                                        return payload;
                                    });
                            }
                            return payload;
                        })
                        .then(function (payload)
                        {
                            card.remove();
                            updateEmployeeTotals();
                            runSearch();
                            const successMessage = payload.message || "Employee deleted successfully.";
                            if (typeof window.showThemeAlert === "function")
                            {
                                window.showThemeAlert(successMessage, {
                                    title: "Employee deleted",
                                    variant: "success",
                                    confirmText: "Done"
                                });
                            }
                            else
                            {
                                window.alert(successMessage);
                            }
                        })
                        .catch(function ()
                        {
                            window.alert("Unable to delete employee right now.");
                        });
                });
            });
        }

        if (formToggle) formToggle.addEventListener("click", toggleFormShell);
        buildJoinDatePicker();
        if (sickTotalField) sickTotalField.addEventListener("input", updateTotalLeave);
        if (earnedTotalField) earnedTotalField.addEventListener("input", updateTotalLeave);

        document.querySelectorAll("[data-password-toggle]").forEach(function (button)
        {
            button.addEventListener("click", function ()
            {
                const input = document.getElementById(button.dataset.passwordTarget);
                const icon = button.querySelector(".password-action-icon-eye");
                if (!input) return;
                const show = input.type === "password";
                input.type = show ? "text" : "password";
                button.setAttribute("aria-pressed", show ? "true" : "false");
                button.title = show ? "Hide password" : "Show password";
                if (icon) icon.textContent = show ? "🙈" : "👁️";
            });
        });

        document.querySelectorAll("[data-password-reset]").forEach(function (button)
        {
            button.addEventListener("click", function ()
            {
                const input = document.getElementById(button.dataset.passwordTarget);
                if (!input) return;
                input.value = "";
                input.type = "password";
                const toggle = document.querySelector("[data-password-toggle][data-password-target='" + button.dataset.passwordTarget + "']");
                if (toggle)
                {
                    toggle.setAttribute("aria-pressed", "false");
                    toggle.title = "Show password";
                    const icon = toggle.querySelector(".password-action-icon-eye");
                    if (icon) icon.textContent = "👁️";
                }
                validateRequiredFields(submitAttempted);
            });
        });

        requiredFields().forEach(function (input)
        {
            input.addEventListener("input", function ()
            {
                syncFieldAccentState(input);
                validateRequiredFields(submitAttempted);
            });
            input.addEventListener("change", function ()
            {
                syncFieldAccentState(input);
            });
        });

        if (joinDateInput)
        {
            joinDateInput.addEventListener("change", function ()
            {
                syncFieldAccentState(joinDateInput);
                syncJoinDatePicker();
                validateRequiredFields(submitAttempted);
            });
        }

        if (phoneField)
        {
            ensurePhonePrefix();
            phoneField.addEventListener("focus", ensurePhonePrefix);
            phoneField.addEventListener("click", function ()
            {
                if (phoneField.selectionStart < 4)
                {
                    phoneField.setSelectionRange(phoneField.value.length, phoneField.value.length);
                }
            });
            phoneField.addEventListener("input", function ()
            {
                ensurePhonePrefix();
                phoneField.setSelectionRange(phoneField.value.length, phoneField.value.length);
                syncFieldAccentState(phoneField);
                validateRequiredFields(submitAttempted);
            });
            phoneField.addEventListener("keydown", function (event)
            {
                if ((event.key === "Backspace" || event.key === "Delete") && phoneField.selectionStart <= 4)
                {
                    event.preventDefault();
                }
            });
        }

        if (employeeForm)
        {
            employeeForm.addEventListener("submit", async function (event)
            {
                ensurePhonePrefix();
                submitAttempted = true;
                if (!validateRequiredFields(true))
                {
                    event.preventDefault();
                    return;
                }
                if (employeeCreateConfirmed)
                {
                    return;
                }
                event.preventDefault();
                const shouldCreate = typeof window.showThemeConfirm === "function"
                    ? await window.showThemeConfirm("Create this employee record?", {
                        title: "Create employee",
                        confirmText: "Create",
                        variant: "confirm"
                    })
                    : window.confirm("Create this employee record?");
                if (shouldCreate)
                {
                    employeeCreateConfirmed = true;
                    employeeForm.requestSubmit();
                }
            });
        }

        if (searchInput)
        {
            searchInput.addEventListener("input", function ()
            {
                runRosterTransition(runSearch);
            });
            searchInput.addEventListener("search", function ()
            {
                runRosterTransition(runSearch);
            });
        }

        window.addEventListener("resize", function ()
        {
            const nextCardsPerPage = getCardsPerPage();
            if (lastCardsPerPage !== nextCardsPerPage)
            {
                currentPage = 1;
                renderPagination();
            }
            requestAnimationFrame(applyResponsiveTrim);
        });

        bindAddressMoreButtons(document);

        document.querySelectorAll("[data-inline-edit-open]").forEach(function (button)
        {
            button.addEventListener("click", function ()
            {
                const container = button.closest("[data-inline-edit-card]");
                if (container)
                {
                    if (container.querySelector("[data-inline-edit-form]") && !container.querySelector("[data-inline-edit-form]").hidden)
                    {
                        submitInlineEdit(container);
                    }
                    else
                    {
                        setInlineEditState(container, true);
                    }
                }
            });
        });

        document.querySelectorAll("[data-inline-edit-form]").forEach(function (form)
        {
            form.addEventListener("submit", function (event)
            {
                event.preventDefault();
                const container = form.closest("[data-inline-edit-card]");
                if (!container)
                {
                    return;
                }
                submitInlineEdit(container);
            });

            form.addEventListener("focusout", function ()
            {
                const container = form.closest("[data-inline-edit-card]");
                window.setTimeout(function ()
                {
                    if (!container || !form.hidden && !form.contains(document.activeElement))
                    {
                        submitInlineEdit(container);
                    }
                }, 0);
            });
        });

        if (addressModalEditButton && addressModalEditForm && addressModalTextarea)
        {
            addressModalEditButton.addEventListener("click", function ()
            {
                if (!addressModalEditForm.hidden)
                {
                    addressModalEditForm.requestSubmit();
                }
                else
                {
                    addressModalEditButton.hidden = true;
                    addressModalText.hidden = true;
                    addressModalEditForm.hidden = false;
                    addressModalTextarea.focus();
                    addressModalTextarea.select();
                }
            });
        }

        if (addressModalEditForm)
        {
            addressModalEditForm.addEventListener("submit", function (event)
            {
                event.preventDefault();
                if (!activeAddressEmployeeId)
                {
                    return;
                }
                const nextAddress = addressModalTextarea.value.trim();
                saveEmployeeField(activeAddressEmployeeId, "address", nextAddress).then(function (data)
                {
                    const card = employeeGrid ? employeeGrid.querySelector('[data-employee-card][data-employee-id="' + activeAddressEmployeeId + '"]') : null;
                    if (card)
                    {
                        syncAddressDisplay(card, data.value);
                    }
                    addressModalText.textContent = data.value;
                    addressModalEditForm.hidden = true;
                    addressModalText.hidden = false;
                    addressModalEditButton.hidden = false;
                }).catch(function (error)
                {
                    showEmployeeDetailsToast("Unable to save", error.message || "Unable to save address.", "error");
                });
            });

            addressModalEditForm.addEventListener("focusout", function ()
            {
                window.setTimeout(function ()
                {
                    if (!addressModalEditForm.hidden && !addressModalEditForm.contains(document.activeElement))
                    {
                        addressModalEditForm.requestSubmit();
                    }
                }, 0);
            });
        }

        document.querySelectorAll("[data-close-address-modal]").forEach(function (button)
        {
            button.addEventListener("click", closeAddressModal);
        });

        document.addEventListener("click", function (event)
        {
            if (joinDatePicker && !joinDatePicker.contains(event.target))
            {
                closeJoinDatePicker();
            }
            if (notificationToggle && notificationDropdown && !notificationDropdown.contains(event.target))
            {
                notificationToggle.checked = false;
            }
        });

        document.addEventListener("keydown", function (event)
        {
            if (event.key === "Escape")
            {
                closeJoinDatePicker();
                closeAddressModal();
            }
        });

        window.addEventListener("focus", refreshVisibleEmployeeCards);
        window.addEventListener("pageshow", refreshVisibleEmployeeCards);
        window.addEventListener("storage", function (event)
        {
            if (event.key === "profile-photo-updated")
            {
                refreshVisibleEmployeeCards();
            }
        });
        document.addEventListener("visibilitychange", function ()
        {
            if (!document.hidden)
            {
                refreshVisibleEmployeeCards();
            }
        });
        setInterval(refreshVisibleEmployeeCards, 60000);

        updateTotalLeave();
        syncAllFieldAccentStates();
        validateRequiredFields(false);
        updateEmployeeTotals();
        applyAvatarInitials();
        applyResponsiveTrim();
        bindDeleteButtons();
        runSearch();
        if (employeeDetailsConfig && employeeDetailsConfig.dataset.hasFieldErrors === "true" && formShell && formShell.classList.contains("is-collapsed"))
        {
            toggleFormShell();
        }
    })();

