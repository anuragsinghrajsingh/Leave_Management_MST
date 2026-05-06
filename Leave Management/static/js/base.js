const modal = document.getElementById("modal");
            const modalContent = document.getElementById("modal-content");
            const MODAL_ANIMATION_MS = 170;
            const POPUP_SKELETON_DELAY_MS = 150;
            const SURFACE_SKELETON_DELAY_MS = 150;
            const SURFACE_SKELETON_MIN_VISIBLE_MS = 90;
            let modalCloseTimer = null;

            window.addEventListener("pageshow", function (event)
            {
                const isAuthenticatedPage = document.body && document.body.dataset.authenticated === "true";
                const navEntries = typeof performance.getEntriesByType === "function" ? performance.getEntriesByType("navigation") : [];
                const navType = navEntries.length ? navEntries[0].type : "";
                const restoredFromHistory = event.persisted || navType === "back_forward";

                if (!isAuthenticatedPage || !restoredFromHistory)
                {
                    return;
                }

                window.location.replace(window.location.href);
            });

            function startAsyncPopupSkeleton(popupElement)
            {
                if (!popupElement)
                {
                    return;
                }

                if (popupElement._popupSkeletonTimer)
                {
                    clearTimeout(popupElement._popupSkeletonTimer);
                }

                if (popupElement._popupSkeletonRevealTimer)
                {
                    clearTimeout(popupElement._popupSkeletonRevealTimer);
                }

                popupElement.classList.remove("popup-loading");
                popupElement._popupSkeletonRevealTimer = setTimeout(() =>
                {
                    popupElement.classList.add("popup-loading");
                    popupElement._popupSkeletonRevealTimer = null;
                }, POPUP_SKELETON_DELAY_MS);
            }

            function finishAsyncPopupSkeleton(popupElement)
            {
                if (!popupElement)
                {
                    return;
                }

                if (popupElement._popupSkeletonTimer)
                {
                    clearTimeout(popupElement._popupSkeletonTimer);
                    popupElement._popupSkeletonTimer = null;
                }

                if (popupElement._popupSkeletonRevealTimer)
                {
                    clearTimeout(popupElement._popupSkeletonRevealTimer);
                    popupElement._popupSkeletonRevealTimer = null;
                }

                popupElement.classList.remove("popup-loading");
            }

            window.startAsyncPopupSkeleton = startAsyncPopupSkeleton;
            window.finishAsyncPopupSkeleton = finishAsyncPopupSkeleton;

            function startAsyncSurfaceSkeleton(surfaceElement)
            {
                if (!surfaceElement)
                {
                    return;
                }

                if (surfaceElement._surfaceSkeletonRevealTimer)
                {
                    clearTimeout(surfaceElement._surfaceSkeletonRevealTimer);
                }

                if (surfaceElement._surfaceSkeletonHideTimer)
                {
                    clearTimeout(surfaceElement._surfaceSkeletonHideTimer);
                    surfaceElement._surfaceSkeletonHideTimer = null;
                }

                surfaceElement.dataset.surfaceLoadingState = "pending";
                surfaceElement._surfaceSkeletonStartedAt = Date.now();
                surfaceElement._surfaceSkeletonRevealTimer = setTimeout(() =>
                {
                    surfaceElement.classList.add("async-surface-loading");
                    surfaceElement.dataset.surfaceLoadingState = "visible";
                    surfaceElement._surfaceSkeletonRevealTimer = null;
                }, SURFACE_SKELETON_DELAY_MS);
            }

            function finishAsyncSurfaceSkeleton(surfaceElement)
            {
                if (!surfaceElement)
                {
                    return;
                }

                if (surfaceElement._surfaceSkeletonRevealTimer)
                {
                    clearTimeout(surfaceElement._surfaceSkeletonRevealTimer);
                    surfaceElement._surfaceSkeletonRevealTimer = null;
                }

                const hideSurface = () =>
                {
                    surfaceElement.classList.remove("async-surface-loading");
                    surfaceElement.dataset.surfaceLoadingState = "idle";
                    surfaceElement._surfaceSkeletonHideTimer = null;
                };

                if (!surfaceElement.classList.contains("async-surface-loading"))
                {
                    hideSurface();
                    return;
                }

                const elapsed = Date.now() - (surfaceElement._surfaceSkeletonStartedAt || Date.now());
                const remaining = Math.max(0, SURFACE_SKELETON_MIN_VISIBLE_MS - elapsed);

                surfaceElement._surfaceSkeletonHideTimer = setTimeout(hideSurface, remaining);
            }

            window.startAsyncSurfaceSkeleton = startAsyncSurfaceSkeleton;
            window.finishAsyncSurfaceSkeleton = finishAsyncSurfaceSkeleton;

            function openModal() // function openModal(html) 
            {
                // const modal = document.getElementById("modal");
                // const modalContent = document.getElementById("modal-content");
                
                //modalContent.innerHTML = html;

                if (modalCloseTimer)
                {
                    clearTimeout(modalCloseTimer);
                    modalCloseTimer = null;
                }

                modal.classList.remove("is-closing");
                modal.style.display = "flex";
                requestAnimationFrame(() => modal.classList.add("is-open"));
                modal.setAttribute("aria-hidden", "false");
                trapFocus(modal);
            }

            function closeModal() 
            {
                // const modal = document.getElementById("modal");
                // const modalContent = document.getElementById("modal-content");
                // For Edit Leave form
                const formHome = document.getElementById("form-home");
                const formTemplate = document.getElementById("edit-leave-template");

                //For Calendar
                const modalBox = document.querySelector(".modal-box");

                if (modal.style.display === "none")
                {
                    return;
                }

                const activeElement = document.activeElement;

                if (activeElement && modal.contains(activeElement) && typeof activeElement.blur === "function")
                {
                    activeElement.blur();
                }

                modal.classList.remove("is-open");
                modal.classList.add("is-closing");
                modal.classList.remove("communication-detail-open");
                modal.classList.remove("popup-edit-modal-host");
                modal.setAttribute("aria-hidden", "true");

                modalBox.classList.remove("wide"); // For Calendar
                modalBox.classList.remove("expanded-calendar"); // For Calendar
                modalBox.classList.remove("compact-calendar"); // For Calendar
                
                // Remove calendar toggle if somehow still present
                const existingToggle = document.getElementById("calendar-toggle-icon");
                if (existingToggle) existingToggle.remove();


                modalCloseTimer = setTimeout(() =>
                {
                    modal.style.display = "none";      // for closing the modal
                    modal.classList.remove("is-closing");
                    modal.classList.remove("communication-detail-open");
                    modalContent.innerHTML = "";       // Empty 'modal' the container so that next time we open it, we start fresh without any leftover content from previous usage.

                    // MOVE FORM BACK HOME (CRITICAL)
                    if (formTemplate && formHome) 
                    {
                        formHome.appendChild(formTemplate);
                    }

                    modalCloseTimer = null;
                }, MODAL_ANIMATION_MS);
            }

            /* ==========================
                ESC key support
            ========================== */

document.addEventListener("keydown", (e) => 
            {
                if (e.key !== "Escape") return;

                const detailOverlay = document.getElementById("calendar-detail-overlay");

                // 1️⃣ Close calendar detail overlay first
                if (detailOverlay && detailOverlay.style.display === "flex") 
                {
                    closeCalendarDetail();
                    return;
                }

                // 2️⃣ Otherwise close main modal
                if (modal && modal.style.display === "flex") 
                {
                    closeModal();
                }
            });

            
            function trapFocus(element) 
            {
                const focusable = element.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');

                if (!focusable.length) return;

                const first = focusable[0];
                const last = focusable[focusable.length - 1];

                first.focus();

                element.addEventListener("keydown", (e) => 
                {
                    if (e.key !== "Tab") return;

                    if (e.shiftKey && document.activeElement === first) 
                    {
                        e.preventDefault();
                        last.focus();
                    } 
                    
                    else if (!e.shiftKey && document.activeElement === last) 
                    {
                        e.preventDefault();
                        first.focus();
                    }
                });
            }

            document.querySelectorAll("[data-flash]").forEach((flash, index) =>
            {
                const dismissBtn = flash.querySelector(".flash-dismiss");
                const removeFlash = () =>
                {
                    flash.classList.add("flash-exit");
                    setTimeout(() => flash.remove(), 220);
                };

                if (dismissBtn)
                {
                    dismissBtn.addEventListener("click", removeFlash);
                }

                setTimeout(removeFlash, 4200 + index * 250);
            });

            function applyInitials(selector, fallbackValue)
            {
                document.querySelectorAll(selector).forEach((element) =>
                {
                    const fullName = String(element.dataset.fullName || "").trim();
                    const username = String(element.dataset.username || fallbackValue).trim();
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

            applyInitials("[data-user-initials]", "HR");
            applyInitials("[data-avatar-fallback]", "EM");

            const PAGE_SKELETON_DELAY_MS = 150;
            const PAGE_SKELETON_ENABLED = true;
            let pageSkeletonTimer = null;

            function dismissPageSkeletons()
            {
                document.querySelectorAll("[data-page-skeleton]").forEach((skeleton) =>
                {
                    if (skeleton.dataset.dismissed === "true")
                    {
                        return;
                    }

                    skeleton.dataset.dismissed = "true";
                    skeleton.classList.add("is-leaving");

                    setTimeout(() =>
                    {
                        skeleton.classList.remove("is-visible", "is-leaving");
                    }, 320);
                });
            }

            function armPageSkeletons()
            {
                if (!PAGE_SKELETON_ENABLED)
                {
                    return;
                }

                pageSkeletonTimer = setTimeout(() =>
                {
                    document.querySelectorAll("[data-page-skeleton]").forEach((skeleton) =>
                    {
                        skeleton.classList.add("is-visible");
                    });
                }, PAGE_SKELETON_DELAY_MS);
            }

            function finishPageSkeletons()
            {
                if (pageSkeletonTimer)
                {
                    clearTimeout(pageSkeletonTimer);
                    pageSkeletonTimer = null;
                }

                const visibleSkeleton = document.querySelector("[data-page-skeleton].is-visible");

                if (visibleSkeleton)
                {
                    setTimeout(function ()
                    {
                        dismissPageSkeletons();
                        setTimeout(function ()
                        {
                            startInitialCountUps(false);
                        }, 360);
                    }, 80);
                    return;
                }

                document.querySelectorAll("[data-page-skeleton]").forEach((skeleton) =>
                {
                    skeleton.dataset.dismissed = "true";
                    skeleton.classList.remove("is-visible", "is-leaving");
                });

                setTimeout(function ()
                {
                    startInitialCountUps(false);
                }, 120);
            }

            function showDeferredNavigationSkeleton()
            {
                if (!PAGE_SKELETON_ENABLED)
                {
                    return;
                }

                const skeletons = document.querySelectorAll("[data-page-skeleton]");

                if (!skeletons.length)
                {
                    return;
                }

                if (pageSkeletonTimer)
                {
                    clearTimeout(pageSkeletonTimer);
                }

                pageSkeletonTimer = setTimeout(() =>
                {
                    skeletons.forEach((skeleton) =>
                    {
                        skeleton.dataset.dismissed = "false";
                        skeleton.classList.remove("is-leaving");
                        skeleton.classList.add("is-visible");
                    });
                }, PAGE_SKELETON_DELAY_MS);
            }

            document.addEventListener("click", (event) =>
            {
                const link = event.target.closest("a[href]");

                if (!link)
                {
                    return;
                }

                const href = link.getAttribute("href") || "";
                const target = (link.getAttribute("target") || "").toLowerCase();
                const url = href ? new URL(href, window.location.href) : null;

                if (
                    event.defaultPrevented ||
                    event.button !== 0 ||
                    event.metaKey ||
                    event.ctrlKey ||
                    event.shiftKey ||
                    event.altKey ||
                    !href ||
                    href.startsWith("#") ||
                    href.startsWith("javascript:") ||
                    link.dataset.noPageSkeleton === "true" ||
                    link.hasAttribute("download") ||
                    target === "_blank" ||
                    !url ||
                    url.origin !== window.location.origin
                )
                {
                    return;
                }

                showDeferredNavigationSkeleton();
            }, true);

            document.addEventListener("submit", (event) =>
            {
                const form = event.target;

                if (!(form instanceof HTMLFormElement) || form.dataset.noPageSkeleton === "true")
                {
                    return;
                }

                setTimeout(() =>
                {
                    if (!event.defaultPrevented)
                    {
                        showDeferredNavigationSkeleton();
                    }
                }, 0);
            }, true);

            if (document.readyState === "complete")
            {
                requestAnimationFrame(finishPageSkeletons);
            }
            else
            {
                window.addEventListener("load", finishPageSkeletons, { once: true });
            }

            window.addEventListener("load", function ()
            {
                setTimeout(function ()
                {
                    if (typeof window.refreshAllCountUps === "function")
                    {
                        window.refreshAllCountUps({ duration: 260 });
                    }
                }, 420);
            }, { once: true });

            function resolveHeaderTooltip(element)
            {
                const explicitLabel = (element.getAttribute("aria-label") || "").trim();
                const textLabel = (element.textContent || "").trim().replace(/\s+/g, " ");

                if (element.closest(".nav-links"))
                {
                    const navText = textLabel.toLowerCase();

                    if (navText === "dashboard")
                    {
                        return "Dashboard: jump to your main workspace and quick leave summary.";
                    }

                    if (navText === "apply leave")
                    {
                        return "Apply Leave: create a new leave request with dates, type, and reason.";
                    }

                    if (navText === "my leaves")
                    {
                        return "My Leaves: review your requests, balances, and approval history.";
                    }

                    if (navText === "manage all")
                    {
                        return "Manage All: review team requests and take HR actions in one place.";
                    }

                    if (navText === "employees")
                    {
                        return "Employees: open the employee directory and profile details.";
                    }

                    if (navText === "reports")
                    {
                        return "Reports: open attendance and leave analytics for the team.";
                    }
                }

                if (element.classList.contains("notification-trigger"))
                {
                    return explicitLabel || "Notifications: open the latest alerts and updates.";
                }

                if (element.classList.contains("communication-trigger"))
                {
                    return explicitLabel || "Messages: open announcements and direct communication.";
                }

                if (element.classList.contains("hamburger"))
                {
                    return "Navigation menu: expand the page links on smaller screens.";
                }

                if (element.classList.contains("profile-icon") || element.classList.contains("profile-menu-trigger"))
                {
                    return explicitLabel || "Profile menu: open account actions and sign out.";
                }

                return explicitLabel || textLabel;
            }

            function updateHeaderTooltipSide(element)
            {
                const rect = element.getBoundingClientRect();
                const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
                const safeWidth = Math.min(240, Math.max(160, viewportWidth - 20));
                const leftSpace = rect.left;
                const rightSpace = viewportWidth - rect.right;
                let side = "center";

                if (rightSpace < safeWidth * 0.45)
                {
                    side = "left";
                }
                else if (leftSpace < safeWidth * 0.45)
                {
                    side = "right";
                }

                element.setAttribute("data-header-tooltip-side", side);
            }

            document.querySelectorAll("header .nav-links a, header .notification-trigger, header .communication-trigger, header .profile-icon, header .profile-menu-trigger, header .hamburger").forEach((element) =>
            {
                if (element.hasAttribute("data-header-tooltip"))
                {
                    return;
                }

                const title = resolveHeaderTooltip(element);

                if (title)
                {
                    element.removeAttribute("title");
                    element.setAttribute("data-header-tooltip", title);
                    element.setAttribute("data-header-tooltip-side", "center");
                    element.addEventListener("mouseenter", () => updateHeaderTooltipSide(element));
                    element.addEventListener("focus", () => updateHeaderTooltipSide(element));
                    element.addEventListener("touchstart", () => updateHeaderTooltipSide(element), { passive: true });
                }
            });

            const countUpFrameStore = new WeakMap();
            const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            const countUpDebugStorageKey = "countup_debug_enabled";

            function isCountUpDebugEnabled()
            {
                try
                {
                    return window.__COUNTUP_DEBUG__ === true || window.localStorage.getItem(countUpDebugStorageKey) === "1";
                }
                catch (error)
                {
                    return window.__COUNTUP_DEBUG__ === true;
                }
            }

            function countUpDebugLog()
            {
                if (!isCountUpDebugEnabled())
                {
                    return;
                }

                try
                {
                    console.log.apply(console, ["[countup]"].concat(Array.from(arguments)));
                }
                catch (error)
                {
                    // Ignore logging issues.
                }
            }

            window.setCountUpDebug = function (enabled)
            {
                const value = enabled === true;
                window.__COUNTUP_DEBUG__ = value;

                try
                {
                    window.localStorage.setItem(countUpDebugStorageKey, value ? "1" : "0");
                }
                catch (error)
                {
                    // Ignore storage failures.
                }
            };

            function stopCountUp(element)
            {
                const activeFrame = countUpFrameStore.get(element);

                if (activeFrame)
                {
                    cancelAnimationFrame(activeFrame);
                    countUpFrameStore.delete(element);
                }
            }

            function formatCountUpValue(value, decimals)
            {
                if (decimals > 0)
                {
                    return Number(value).toFixed(decimals).replace(/0+$/, "").replace(/\.$/, "");
                }

                return String(Math.round(value));
            }

            function parseCurrentCountUpValue(element)
            {
                if (!element)
                {
                    return 0;
                }

                const rawText = String(element.textContent || "").trim();

                if (!rawText)
                {
                    return 0;
                }

                const numericMatch = rawText.match(/-?\d+(?:\.\d+)?/);

                if (!numericMatch)
                {
                    return 0;
                }

                const parsed = Number(numericMatch[0]);
                return Number.isFinite(parsed) ? parsed : 0;
            }

            function parseCountUpTargetValue(rawValue)
            {
                if (rawValue === undefined || rawValue === null)
                {
                    return NaN;
                }

                if (typeof rawValue === "number")
                {
                    return Number.isFinite(rawValue) ? rawValue : NaN;
                }

                const normalized = String(rawValue).replace(/,/g, "").trim();
                const direct = Number(normalized);

                if (Number.isFinite(direct))
                {
                    return direct;
                }

                const numericMatch = normalized.match(/-?\d+(?:\.\d+)?/);

                if (!numericMatch)
                {
                    return NaN;
                }

                const parsed = Number(numericMatch[0]);
                return Number.isFinite(parsed) ? parsed : NaN;
            }

            window.animateCountUp = function (element, rawTargetValue, options)
            {
                if (!element)
                {
                    return;
                }

                const settings = options || {};
                const parsedTarget = parseCountUpTargetValue(
                    rawTargetValue !== undefined && rawTargetValue !== null
                        ? rawTargetValue
                        : element.dataset.countupTarget || element.dataset.countup || 0
                );

                if (!Number.isFinite(parsedTarget))
                {
                    countUpDebugLog("skip-invalid-target", {
                        element: element.id || element.className || element.tagName,
                        rawTargetValue: rawTargetValue,
                        datasetTarget: element.dataset.countupTarget || element.dataset.countup || ""
                    });
                    return;
                }

                const decimals = Number.isFinite(settings.decimals)
                    ? settings.decimals
                    : Math.max(0, parseInt(element.dataset.countupDecimals || "0", 10) || 0);
                const prefix = settings.prefix !== undefined ? settings.prefix : (element.dataset.countupPrefix || "");
                const suffix = settings.suffix !== undefined ? settings.suffix : (element.dataset.countupSuffix || "");
                const duration = Number.isFinite(settings.duration) ? settings.duration : 1100;
                const startValue = Number.isFinite(settings.from) ? settings.from : parseCurrentCountUpValue(element);
                const force = settings.force === true;
                const lastTarget = Number(element.dataset.countupLastTarget);
                const hasActiveAnimation = countUpFrameStore.has(element);

                if (!force && Number.isFinite(lastTarget) && Math.abs(lastTarget - parsedTarget) < 0.0001)
                {
                    if (hasActiveAnimation)
                    {
                        countUpDebugLog("skip-active-same-target", {
                            element: element.id || element.className || element.tagName,
                            target: parsedTarget
                        });
                        return;
                    }

                    const currentValue = parseCurrentCountUpValue(element);
                    if (Math.abs(currentValue - parsedTarget) < 0.0001)
                    {
                        element.textContent = prefix + formatCountUpValue(parsedTarget, decimals) + suffix;
                        countUpDebugLog("skip-already-at-target", {
                            element: element.id || element.className || element.tagName,
                            target: parsedTarget
                        });
                        return;
                    }
                }

                stopCountUp(element);

                const applyValue = function (value)
                {
                    element.textContent = prefix + formatCountUpValue(value, decimals) + suffix;
                };

                element.dataset.countupLastTarget = String(parsedTarget);
                countUpDebugLog("animate", {
                    element: element.id || element.className || element.tagName,
                    from: startValue,
                    to: parsedTarget,
                    duration: duration
                });

                if (prefersReducedMotion || duration <= 0)
                {
                    applyValue(parsedTarget);
                    return;
                }

                const startTime = performance.now();

                function step(now)
                {
                    const progress = Math.min((now - startTime) / duration, 1);
                    const currentValue = startValue + ((parsedTarget - startValue) * progress);
                    applyValue(currentValue);

                    if (progress < 1)
                    {
                        const frame = requestAnimationFrame(step);
                        countUpFrameStore.set(element, frame);
                        return;
                    }

                    countUpFrameStore.delete(element);
                    applyValue(parsedTarget);
                }

                const initialFrame = requestAnimationFrame(step);
                countUpFrameStore.set(element, initialFrame);
            };

            window.animateCountUpGroup = function (root, options)
            {
                const scope = root || document;
                const settings = options || {};
                const force = settings.force === true;
                scope.querySelectorAll("[data-countup]").forEach(function (element)
                {
                    if (!force && element.dataset.countupPlayed === "true")
                    {
                        return;
                    }

                    element.dataset.countupPlayed = "true";
                    element.dataset.countupLastTarget = "";

                    requestAnimationFrame(function ()
                    {
                        window.animateCountUp(element, undefined, {
                            from: force ? parseCurrentCountUpValue(element) : 0,
                            force: force
                        });
                    });
                });
            };

            window.refreshAllCountUps = function (options)
            {
                const settings = options || {};
                const root = settings.root || document;
                const duration = Number.isFinite(settings.duration) ? settings.duration : 320;

                root.querySelectorAll("[data-countup]").forEach(function (element)
                {
                    window.animateCountUp(element, undefined, {
                        from: parseCurrentCountUpValue(element),
                        duration: duration,
                        force: true
                    });
                });
            };

            document.addEventListener("countup:refresh", function (event)
            {
                const detail = event && event.detail ? event.detail : {};
                if (typeof window.refreshAllCountUps === "function")
                {
                    window.refreshAllCountUps({
                        root: detail.root || document,
                        duration: Number.isFinite(detail.duration) ? detail.duration : 260
                    });
                }
            });

            function startInitialCountUps(force)
            {
                window.animateCountUpGroup(document, { force: force === true });
            }

            window.addEventListener("pageshow", function (event)
            {
                if (!event.persisted)
                {
                    return;
                }

                document.querySelectorAll("[data-countup]").forEach(function (element)
                {
                    element.dataset.countupPlayed = "false";
                    element.dataset.countupLastTarget = "";
                });

                setTimeout(function ()
                {
                    startInitialCountUps(false);
                }, 300);
            });

// AUTO-REMOVE FLASH MESSAGES AFTER 3 SECONDS

            setTimeout(() => 
            {
                document.querySelectorAll('.flash').forEach(msg => 
                {
                    msg.style.opacity = '0';
                    msg.style.transform = 'translateX(20px)';
                    setTimeout(() => msg.remove(), 700);
                });

            }, 7000);

            document.addEventListener("click", (event) =>
            {
                const navLinks = document.querySelector(".nav-links");
                const hamburger = document.querySelector(".hamburger");
                const profileToggle = document.getElementById("profile-toggle");
                const profileDropdown = document.querySelector(".profile-dropdown");
                const navIsOpen = !!(navLinks && navLinks.classList.contains("is-open"));

                if (!navLinks || !hamburger || !navIsOpen)
                {
                    if (
                        profileToggle &&
                        profileDropdown &&
                        profileToggle.checked &&
                        !profileDropdown.contains(event.target) &&
                        event.target !== profileToggle
                    )
                    {
                        profileToggle.checked = false;
                    }

                    return;
                }

                if (
                    !navLinks.contains(event.target) &&
                    !hamburger.contains(event.target)
                )
                {
                    navLinks.classList.remove("is-open");
                }

                if (
                    profileToggle &&
                    profileDropdown &&
                    profileToggle.checked &&
                    !profileDropdown.contains(event.target) &&
                    event.target !== profileToggle
                )
                {
                    profileToggle.checked = false;
                }
            });

            const navLinks = document.querySelector(".nav-links");
            const profileToggle = document.getElementById("profile-toggle");
            const profileContent = document.querySelector(".dropdown-content");
            const HEADER_POPUP_SKELETON_MS = 180;

            function pulseHeaderPopupSkeleton(surface)
            {
                if (!surface || typeof window.startAsyncPopupSkeleton !== "function" || typeof window.finishAsyncPopupSkeleton !== "function")
                {
                    return;
                }

                const hasMeaningfulContent = surface === navLinks
                    ? !!surface.querySelector("a[href]")
                    : surface === profileContent
                        ? !!surface.querySelector(".user-info, a, button")
                        : !!surface.children.length;

                if (hasMeaningfulContent)
                {
                    return;
                }

                window.startAsyncPopupSkeleton(surface);

                setTimeout(function ()
                {
                    window.finishAsyncPopupSkeleton(surface);
                }, HEADER_POPUP_SKELETON_MS);
            }

            function closeHeaderMenusExcept(options)
            {
                const settings = options || {};

                document.querySelectorAll(".communication-dropdown.is-open").forEach(function (dropdown)
                {
                    if (settings.keepCommunication === dropdown)
                    {
                        return;
                    }

                    dropdown.classList.remove("is-open");
                    const trigger = dropdown.querySelector(".communication-trigger");
                    if (trigger)
                    {
                        trigger.setAttribute("aria-expanded", "false");
                    }
                });

                document.querySelectorAll(".notification-dropdown.is-open").forEach(function (dropdown)
                {
                    if (settings.keepNotification === dropdown)
                    {
                        return;
                    }

                    dropdown.classList.remove("is-open");
                    const trigger = dropdown.querySelector(".notification-trigger");
                    if (trigger)
                    {
                        trigger.setAttribute("aria-expanded", "false");
                    }
                });

                document.querySelectorAll(".profile-header-dropdown.is-open").forEach(function (dropdown)
                {
                    if (settings.keepProfileHeader === dropdown)
                    {
                        return;
                    }

                    dropdown.classList.remove("is-open");
                    const trigger = dropdown.querySelector(".profile-menu-trigger");
                    if (trigger)
                    {
                        trigger.setAttribute("aria-expanded", "false");
                    }
                });

                const legacyProfileToggle = document.getElementById("profile-toggle");
                if (legacyProfileToggle && settings.keepLegacyProfile !== true)
                {
                    legacyProfileToggle.checked = false;
                }

                const mobileNav = document.querySelector(".nav-links");
                if (mobileNav && settings.keepHamburger !== true)
                {
                    mobileNav.classList.remove("is-open");
                }
            }

            window.closeHeaderMenusExcept = closeHeaderMenusExcept;

            if (navLinks)
            {
                function setHamburgerOpenState(isOpen)
                {
                    navLinks.classList.toggle("is-open", isOpen);

                    if (isOpen)
                    {
                        closeHeaderMenusExcept({ keepHamburger: true });
                        pulseHeaderPopupSkeleton(navLinks);
                    }
                    else if (typeof window.finishAsyncPopupSkeleton === "function")
                    {
                        window.finishAsyncPopupSkeleton(navLinks);
                    }
                }

                const hamburgerTrigger = document.querySelector(".hamburger");

                if (hamburgerTrigger)
                {
                    hamburgerTrigger.addEventListener("click", function (event)
                    {
                        event.preventDefault();
                        event.stopPropagation();
                        setHamburgerOpenState(!navLinks.classList.contains("is-open"));
                    });
                }
            }

            if (profileToggle && profileContent)
            {
                profileToggle.addEventListener("change", function ()
                {
                    if (profileToggle.checked)
                    {
                        closeHeaderMenusExcept({ keepLegacyProfile: true });
                        pulseHeaderPopupSkeleton(profileContent);
                    }
                    else if (typeof window.finishAsyncPopupSkeleton === "function")
                    {
                        window.finishAsyncPopupSkeleton(profileContent);
                    }
                });
            }

            document.querySelectorAll(".profile-header-dropdown").forEach(function (dropdown)
            {
                const trigger = dropdown.querySelector(".profile-menu-trigger");

                if (!trigger)
                {
                    return;
                }

                trigger.addEventListener("click", function (event)
                {
                    event.preventDefault();
                    event.stopPropagation();

                    const willOpen = !dropdown.classList.contains("is-open");

                    if (willOpen && typeof window.closeHeaderMenusExcept === "function")
                    {
                        window.closeHeaderMenusExcept({ keepProfileHeader: dropdown });
                    }

                    document.querySelectorAll(".profile-header-dropdown.is-open").forEach(function (openDropdown)
                    {
                        if (openDropdown === dropdown)
                        {
                            return;
                        }

                        openDropdown.classList.remove("is-open");
                        const openTrigger = openDropdown.querySelector(".profile-menu-trigger");
                        if (openTrigger)
                        {
                            openTrigger.setAttribute("aria-expanded", "false");
                        }
                    });

                    dropdown.classList.toggle("is-open", willOpen);
                    trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
                });
            });

            document.addEventListener("click", function (event)
            {
                document.querySelectorAll(".profile-header-dropdown.is-open").forEach(function (dropdown)
                {
                    if (dropdown.contains(event.target))
                    {
                        return;
                    }

                    dropdown.classList.remove("is-open");
                    const trigger = dropdown.querySelector(".profile-menu-trigger");
                    if (trigger)
                    {
                        trigger.setAttribute("aria-expanded", "false");
                    }
                });
            });

            window.addEventListener("pageshow", function (event) 
            {
                if (event.persisted) 
                {
                    document.querySelector("form").reset();
                }
            });
