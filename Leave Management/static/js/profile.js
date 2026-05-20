const profileConfigElement = document.getElementById("profile-js-config");
const profileConfig = profileConfigElement ? profileConfigElement.dataset : {};
const profileUrl = profileConfig.profileUrl || "";
const profileBalanceUnpaid = Number(profileConfig.balanceUnpaid || 0);
const profileBalanceSickUsed = Number(profileConfig.balanceSickUsed || 0);
const profileBalanceEarnedUsed = Number(profileConfig.balanceEarnedUsed || 0);
const profileBalanceSickTotal = Number(profileConfig.balanceSickTotal || 0);
const profileBalanceEarnedTotal = Number(profileConfig.balanceEarnedTotal || 0);
const profileTotalUsed = Number(profileConfig.totalUsed || 0);
const profileShortTaken = Number(profileConfig.shortTaken || 0);
const profileHalfTaken = Number(profileConfig.halfTaken || 0);
const profileHasPasswordErrors = profileConfig.hasPasswordErrors === "true";
function getCSRFToken() 
        {
            return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        }

        document.addEventListener("DOMContentLoaded", function()
        {
            const passLink = document.querySelector(".dropdown-content .pass");
            const logoutLink = document.querySelector(".dropdown-content .logout-btn");
            const editorClose = document.querySelector(".editor-close");
            const editorButtons = document.querySelectorAll(".editor-controls button");
            const resetZoomBtn = document.querySelector('.editor-controls button[data-action="reset-zoom"]');
            const rotateImageBtn = document.querySelector('.editor-controls button[data-action="rotate-image"]');
            const editIcons = document.querySelectorAll(".edit-icon");
            const dirtyDots = document.querySelectorAll(".unsaved-dot");
            const savedLabels = document.querySelectorAll(".save-indicator");
            const passwordToggles = document.querySelectorAll(".toggle-pass");
            const detailStatusChip = document.getElementById("detailStatusChip");
            const completionTextNode = document.getElementById("completionText");
            const completionValue = parseInt(completionTextNode ? completionTextNode.textContent : "0", 10);
            const passwordRules = {
                ruleLength: "\u2717 8 characters",
                ruleUpper: "\u2717 1 uppercase letter",
                ruleNumber: "\u2717 1 number",
                ruleSymbol: "\u2717 1 symbol"
            };
            if (passLink) passLink.textContent = "Change Password";
            if (logoutLink) logoutLink.textContent = "Logout";
            if (editorClose) editorClose.innerHTML = "&times;";

            if (editorButtons.length >= 4)
            {
                editorButtons[0].innerHTML = "&#8722;";
                editorButtons[1].textContent = "+";
            }

            if (resetZoomBtn) resetZoomBtn.innerHTML = "&#10226;";
            if (rotateImageBtn) rotateImageBtn.innerHTML = "&#8635;";
            applyCompletionColor(completionValue);

            editIcons.forEach((icon) => icon.innerHTML = "&#9998;");
            dirtyDots.forEach((dot) => dot.innerHTML = "&#9679;");
            savedLabels.forEach((label) => label.innerHTML = "&#10003; Saved");
            passwordToggles.forEach((toggle) => toggle.innerHTML = "&#128065;");

            if (detailStatusChip)
            {
                detailStatusChip.textContent = completionValue >= 90 ? "Ready for review" : "Editable fields included";
            }

            Object.entries(passwordRules).forEach(([id, value]) =>
            {
                const rule = document.getElementById(id);
                if (rule) rule.textContent = value;
            });

        });




        const leaveCtx = document.getElementById("leaveChart");

        /* ✅ ADDED: usage check */
        const unpaidUsed = profileBalanceUnpaid;
        const sickUsed = profileBalanceSickUsed;
        const earnedUsed = profileBalanceEarnedUsed;

        const noLeaveUsed = (unpaidUsed === 0 && sickUsed === 0 && earnedUsed === 0);

        /* ================= EXISTING CODE ================= */

        function renderCustomLegend(containerId, items, chartInstance)
        {
            const container = document.getElementById(containerId);
            if (!container) return;

            container.innerHTML = items.map((item, index) => `
                <button type="button" class="legend-item stacked" data-index="${index}" style="--legend-color: ${item.color}">
                    <span class="legend-dot"></span>
                    <div class="legend-info">
                        <strong class="legend-label">${item.label}</strong>
                        <small class="legend-value" data-target="${item.target}" data-suffix="${item.suffix || ''}">0${item.suffix || ''}</small>
                    </div>
                </button>
            `).join("");

            if (chartInstance)
            {
                container.querySelectorAll(".legend-item").forEach((node) =>
                {
                    const index = Number(node.dataset.index);

                    const syncLegendState = () =>
                    {
                        node.classList.toggle("is-hidden", !chartInstance.getDataVisibility(index));
                    };

                    syncLegendState();

                    node.addEventListener("click", () =>
                    {
                        chartInstance.toggleDataVisibility(index);
                        chartInstance.update();
                        syncLegendState();
                    });
                });
            }

            container.querySelectorAll("small[data-target]").forEach((node) =>
            {
                const target = parseFloat(node.dataset.target || "0");
                const suffix = node.dataset.suffix || "";
                const duration = 900;
                const start = performance.now();

                function tick(now)
                {
                    const progress = Math.min((now - start) / duration, 1);
                    const eased = 1 - Math.pow(1 - progress, 3);
                    const rawValue = target * eased;
                    const value = rawValue % 1 === 0 ? rawValue.toFixed(0) : rawValue.toFixed(2);
                    node.textContent = `${value}${suffix}`;

                    if (progress < 1) requestAnimationFrame(tick);
                }

                requestAnimationFrame(tick);
            });
        }

        function renderChartEmptyState(canvas, title, body)
        {
            if (!canvas) return;

            canvas.style.display = "none";

            const chartBody = canvas.closest(".chart-body");
            const chartLegend = chartBody ? chartBody.querySelector(".chart-legend") : null;

            if (chartBody) {
                chartBody.classList.add("chart-body-empty");
            }

            if (chartLegend) {
                chartLegend.innerHTML = "";
                chartLegend.hidden = true;
            }

            const empty = document.createElement("div");
            empty.className = "chart-empty-state";
            empty.innerHTML = `
                <div class="chart-empty-icon">◌</div>
                <h4>${title}</h4>
                <p>${body}</p>
            `;

            canvas.parentNode.appendChild(empty);
        }

        const centerLabelPlugin = {
            id: "centerLabelPlugin",
            afterDatasetsDraw(chart, args, pluginOptions)
            {
                if (!pluginOptions || !pluginOptions.text) return;

                const meta = chart.getDatasetMeta(0);
                if (!meta || !meta.data || !meta.data.length) return;

                const { ctx } = chart;
                const x = meta.data[0].x;
                const y = meta.data[0].y;

                ctx.save();
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillStyle = pluginOptions.color || "#0f172a";
                ctx.font = `800 ${pluginOptions.valueSize || 22}px "Manrope", sans-serif`;
                ctx.fillText(pluginOptions.text, x, y - 6);
                ctx.fillStyle = pluginOptions.subColor || "#64748b";
                ctx.font = `700 ${pluginOptions.labelSize || 10}px "Manrope", sans-serif`;
                ctx.fillText(pluginOptions.subtext || "", x, y + 16);
                ctx.restore();
            }
        };

        /* ✅ ADDED: condition before chart (ONLY LINE CHANGE) */
        if (!noLeaveUsed)
        {
        const leaveChart = new Chart(leaveCtx, 
        {
            type: "pie",
            data: 
            {
                labels: ["Unpaid", "Sick", "Earned"],
                datasets: [
                {
                    data: [
                        profileBalanceUnpaid,
                        profileBalanceSickUsed,
                        profileBalanceEarnedUsed
                    ],
                    backgroundColor: 
                    [
                        "#7dd3fc",
                        "#f87171",
                        "#34d399",
                    ],
                    borderWidth: 2,
                    borderColor: "#ffffff",
                    hoverOffset: 6,
                    radius: "100%"
                }]
            },

            options: 
            {
                responsive: true,
                maintainAspectRatio: false,
                layout:
                {
                    padding: 3
                },

                animation:
                {
                    animateRotate:true,
                    duration:1500,
                    easing:"easeOutQuart",
                },

                plugins: 
                {
                    legend:
                    {
                        display:false,
                        position:"bottom",
                        labels:
                        {
                            boxWidth:14,
                            boxHeight:14,
                            padding:15,
                            font:
                            {
                                size:16,
                                weight:"600"
                            }
                        }
                    },

                    tooltip:
                    {
                        enabled: true,

                        backgroundColor: "rgba(17, 24, 39, 0.9)",
                        borderColor: "rgba(255,255,255,0.15)",
                        borderWidth: 1,

                        cornerRadius: 12,
                        padding: 12,

                        titleColor: "#ffffff",
                        bodyColor: "#e5e7eb",

                        displayColors: false,

                        titleFont:
                        {
                            size: 13,
                            weight: "600"
                        },

                        bodyFont:
                        {
                            size: 12
                        },

                        bodySpacing: 4,
                        titleSpacing: 6,

                        caretSize: 6,

                        callbacks:
                        {
                            title:function(context)
                            {
                                const label = context[0].chart.data.labels[context[0].dataIndex];

                                const titles=
                                {
                                    "Unpaid":"🌴 Unpaid Leave Usage",
                                    "Sick":"💊 Sick Leave Details",
                                    "Earned":"⭐ Earned Leave Details"
                                };

                                return titles[label] || label;
                            },

                            label:function(context)
                            {
                                const label = context.chart.data.labels[context.dataIndex];
                                const used = context.raw;

                                if(label==="Unpaid")
                                {
                                    return `Used: ${used}`;
                                }

                                if(label==="Sick")
                                {
                                    const total = profileBalanceSickTotal;
                                    const remaining = total - used;
                                    const percent = ((used/total)*100).toFixed(1);

                                    return [
                                        `Used: ${used}`,
                                        `Remaining: ${remaining}`,
                                        `Total: ${total}`,
                                        `Usage: ${percent}%`
                                    ];
                                }

                                if(label==="Earned")
                                {
                                    const total = profileBalanceEarnedTotal;
                                    const remaining = total - used;
                                    const percent = ((used/total)*100).toFixed(1);

                                    return [
                                        `Used: ${used}`,
                                        `Remaining: ${remaining}`,
                                        `Total: ${total}`,
                                        `Usage: ${percent}%`
                                    ];
                                }
                            }
                        }
                    }
                },
                centerLabelPlugin:
                {
                    text: profileTotalUsed,
                    subtext: "used",
                    color: "#0f172a",
                    subColor: "#64748b"
                }
            }
        , plugins: [centerLabelPlugin]});
        renderCustomLegend("leaveChartLegend", [
            { label: "Unpaid", target: unpaidUsed, suffix: " used", color: "#7dd3fc" },
            { label: "Sick", target: sickUsed, suffix: " used", color: "#f87171" },
            { label: "Earned", target: earnedUsed, suffix: " used", color: "#34d399" }
        ], leaveChart);
        }


        /* ================= YOUR EXISTING TOOLTIP ================= */

        function externalTooltipHandler(context) 
        {
            const { chart, tooltip } = context;

            let tooltipEl = document.getElementById("chart-tooltip");

            if (!tooltipEl) 
            {
                tooltipEl = document.createElement("div");
                tooltipEl.id = "chart-tooltip";
                tooltipEl.innerHTML = `
                    <div class="tooltip-glass">
                        <div class="tooltip-content"></div>
                        <div class="tooltip-arrow"></div>
                    </div>
                `;
                document.body.appendChild(tooltipEl);
            }

            const content = tooltipEl.querySelector(".tooltip-content");

            if (tooltip.opacity === 0) 
            {
                tooltipEl.style.opacity = 0;
                tooltipEl.style.transform = "translateY(6px) scale(0.95)";
                return;
            }

            const index = tooltip.dataPoints[0].dataIndex;
            const label = chart.data.labels[index];
            const value = tooltip.dataPoints[0].raw;

            let html = "";

            if (label === "Unpaid") 
            {
                html = `
                    <div class="tooltip-title">🌴 Unpaid Leave</div>
                    <div class="tooltip-row">Used: <b>${value}</b></div>
                `;
            }

            if (label === "Sick") 
            {
                const total = profileBalanceSickTotal;
                const remaining = total - value;
                const percent = ((value / total) * 100).toFixed(1);

                html = `
                    <div class="tooltip-title">💊 Sick Leave</div>
                    <div class="tooltip-row">Used: <b>${value}</b></div>
                    <div class="tooltip-row">Remaining: <b>${remaining}</b></div>
                    <div class="tooltip-row">Total: <b>${total}</b></div>
                    <div class="tooltip-row highlight">Usage: ${percent}%</div>
                `;
            }

            if (label === "Earned") 
            {
                const total = profileBalanceEarnedTotal;
                const remaining = total - value;
                const percent = ((value / total) * 100).toFixed(1);

                html = `
                    <div class="tooltip-title">⭐ Earned Leave</div>
                    <div class="tooltip-row">Used: <b>${value}</b></div>
                    <div class="tooltip-row">Remaining: <b>${remaining}</b></div>
                    <div class="tooltip-row">Total: <b>${total}</b></div>
                    <div class="tooltip-row highlight">Usage: ${percent}%</div>
                `;
            }

            if (!html) 
            {
                html = `<b>${label}</b><br>Value: ${value}`;
            }

            content.innerHTML = html;

            const rect = chart.canvas.getBoundingClientRect();
            const tooltipWidth = tooltipEl.offsetWidth;
            const tooltipHeight = tooltipEl.offsetHeight;
            const showOnRight = tooltip.caretX <= (chart.width / 2);

            let x;
            let y = rect.top + tooltip.caretY - (tooltipHeight / 2);

            if (showOnRight) 
            {
                x = rect.right + 14;
                tooltipEl.classList.add("right");
                tooltipEl.classList.remove("left");
            } 
            else 
            {
                x = rect.left - tooltipWidth - 14;
                tooltipEl.classList.add("left");
                tooltipEl.classList.remove("right");
            }

            y = Math.max(12, Math.min(y, window.innerHeight - tooltipHeight - 12));

            tooltipEl.style.top = `${y}px`;
            tooltipEl.style.left = `${x}px`;

            tooltipEl.style.opacity = 1;
            tooltipEl.style.transform = "translateY(0) scale(1)";
        }


        /* ✅ ADDED: message block (BOTTOM) */
        if (noLeaveUsed)
        {
            renderChartEmptyState(
                leaveCtx,
                "No leave activity yet",
                "Full leave usage will appear here once earned, sick, or unpaid leave is utilized."
            );
        }







        const shortUsed = profileShortTaken;
        const halfUsed = profileHalfTaken;

        const chartEl = document.getElementById("shortHalfChart");

        /* 🚫 IF NO USAGE → SHOW MESSAGE */
        if (shortUsed === 0 && halfUsed === 0) 
        {
            renderChartEmptyState(
                chartEl,
                "No short or half leave used",
                "Monthly short and half leave utilization will be shown here when used."
            );
        }

        /* ✅ IF ANY USAGE → SHOW CHART */
        else
        {
            const shortHalfChart = new Chart(chartEl, 
            {
                type: "doughnut",

                data:
                {
                    labels: ["Short", "Half"],
                    datasets: [
                    {
                        data: [shortUsed, halfUsed],   // ✅ using USED values

                        backgroundColor:
                        [
                            "#818cf8",
                            "#fbbf24"
                        ],

                        borderWidth: 2,
                        borderColor: "#ffffff",
                        hoverOffset: 6,
                        radius: "100%"
                    }]
                },

                options:
                {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "65%",
                    layout:
                    {
                        padding: 3
                    },

                    animation:
                    {
                        duration: 1500,
                        easing: "easeOutQuart"
                    },

                    plugins:
                    {
                        legend:
                        {
                            display: false,
                            position: "bottom",
                            labels:
                            {
                                boxWidth: 14,
                                boxHeight : 14, 
                                padding: 15,
                                font:
                                {
                                    size: 16,
                                    weight: "600"
                                }
                            }
                        },

                        tooltip:
                        {
                            enabled: true,

                            backgroundColor: "rgba(17, 24, 39, 0.9)",
                            borderColor: "rgba(255,255,255,0.15)",
                            borderWidth: 1,

                            cornerRadius: 12,
                            padding: 12,

                            titleColor: "#ffffff",
                            bodyColor: "#e5e7eb",

                            displayColors: false,

                            titleFont:
                            {
                                size: 13,
                                weight: "600"
                            },

                            bodyFont:
                            {
                                size: 12
                            },

                            bodySpacing: 4,
                            titleSpacing: 6,

                            caretSize: 6,

                            callbacks:
                            {
                                title: function(context)
                                {
                                    const label = context[0].label;

                                    const titles =
                                    {
                                        "Short": "⏱ Short Leave",
                                        "Half": "🌓 Half Day Leave"
                                    };

                                    return titles[label] || label;
                                },

                                label: function(context)
                                {
                                    const label = context.label;
                                    const used = context.raw;

                                    let total = 0;

                                    if (label === "Short") total = 2;
                                    if (label === "Half") total = 1;

                                    const remaining = total - used;
                                    const percent = total > 0 ? ((used / total) * 100).toFixed(0) : 0;

                                    return [
                                        `Used: ${used}`,
                                        `Remaining: ${remaining}`,
                                        `Total: ${total}`,
                                        `Usage: ${percent}%`
                                    ];
                                }
                            }
                        }
                    },
                    centerLabelPlugin:
                    {
                        text: `${shortUsed + halfUsed}`,
                        subtext: "monthly used",
                        color: "#0f172a",
                        subColor: "#64748b",
                        valueSize: 20,
                        labelSize: 9
                    }
                }
            , plugins: [centerLabelPlugin]});
            renderCustomLegend("shortHalfChartLegend", [
                { label: "Short", target: shortUsed, suffix: " used", color: "#818cf8" },
                { label: "Half", target: halfUsed, suffix: " used", color: "#fbbf24" }
            ], shortHalfChart);
        }
        function showSaved(id) 
        {
            const el = document.getElementById(id + "Saved");
            el.classList.add("show");

            setTimeout(() => 
            {
                el.classList.remove("show");
            }, 1500);
        }


        setTimeout(function()
        {
            document.querySelectorAll(".message").forEach(function(msg)
            {
                msg.style.opacity = "0";

                setTimeout(()=>msg.remove(),300);
            });

        },4000);


        const tabs = document.querySelectorAll(".tab");
        const contents = document.querySelectorAll(".tab-content");

        tabs.forEach(tab => 
        {
            tab.addEventListener("click", () => 
            {
                tabs.forEach(t => t.classList.remove("active"));
                contents.forEach(c => c.classList.remove("active"));

                tab.classList.add("active");
                document.getElementById(tab.dataset.tab).classList.add("active");
            });
        });

        function countWords()
        {
            const textarea = document.getElementById("bioInput");
            const counter = document.getElementById("bioCounter");

            let words = textarea.value.trim().split(/\s+/);

            if (textarea.value.trim() === "")
            {
                words = [];
            }

            if (words.length > 50)
            {
                textarea.value = words.slice(0, 50).join(" ");
                words = textarea.value.trim().split(/\s+/);
            }

            counter.innerText = words.length + " / 50 words";
        }

        window.countWords = countWords;

        /* =====================================================
        INLINE PROFILE EDITING SYSTEM
        ===================================================== */

        document.querySelectorAll(".edit-input").forEach(input =>
        {
            input.addEventListener("blur", saveField);

            input.addEventListener("keydown", function(e)
            {
                if(e.key === "Enter" && this.tagName !== "TEXTAREA")
                {
                    e.preventDefault();
                    saveField.call(this);
                }
            });
        });

        document.querySelectorAll(".edit-input").forEach(input =>
        {
            input.addEventListener("input", function()
            {
                const field = this.dataset.field;
                const dot = document.getElementById(field + "Dirty");

                if(!dot) return;

                /* compare with original value */
                if(this.value !== this.dataset.original)
                {
                    dot.classList.remove("hidden");
                }
                else
                {
                    dot.classList.add("hidden");
                }
            });
        });

        document.addEventListener("keydown", function(e)
        {
            if(e.key === "Enter" && e.target.tagName !== "TEXTAREA")
            {
                e.preventDefault();
            }
        });

        document.addEventListener("keydown", function(e)
        {
            if(e.key === "Escape")
            {
                document.querySelectorAll(".edit-input").forEach(input =>
                {
                    if(!input.classList.contains("hidden"))
                    {
                        cancelEdit(input);
                    }
                });
            }
        });

        function cancelEdit(input)
        {
            const field = input.dataset.field;

            const text = document.getElementById(field + "Text");

            input.classList.add("hidden");
            text.style.display = "block";

            /* reset value to original */
            input.value = text.innerText;

            /* hide validation */
            const error = document.getElementById(field + "Error");
            if(error) error.classList.add("hidden");

            /* hide counter */
            const counter = document.getElementById("bioCounter");
            if(counter) counter.classList.add("hidden");

            const dot = document.getElementById(field + "Dirty");
            if(dot) dot.classList.add("hidden");
        }


        /* =====================================================
        EDIT FIELD
        ===================================================== */

        function editField(field)
        {
            const text = document.getElementById(field + "Text");
            const input = document.getElementById(field + "Input");
            const counter = document.getElementById("bioCounter");

            if(!input.classList.contains("hidden"))
            {
                saveField.call(input);
                return;
            }

            text.style.display = "none";
            input.classList.remove("hidden");

            /* store original value */
            input.dataset.original = input.value;

            input.focus();

            if(field === "bio")
            {
                counter.classList.remove("hidden");
                countWords();
            }
        }

        /* =====================================================
        SAVE FIELD (AJAX)
        ===================================================== */

        const lastCompletionNode = document.getElementById("completionText");
        let lastCompletion = parseInt(lastCompletionNode ? lastCompletionNode.textContent : "0", 10) || 0;

        function getCompletionColor(percent)
        {
            if(percent >= 80) return "#22c55e";
            if(percent >= 60) return "#3b82f6";
            if(percent >= 40) return "#f59e0b";
            return "#ef4444";
        }

        function applyCompletionColor(percent)
        {
            const circle = document.querySelector(".completion-chart .circle");
            if(!circle) return;

            circle.style.stroke = getCompletionColor(percent);
        }

        function updateCompletionUI(newPercent)
        {
            const text = document.getElementById("completionText");
            const circle = document.querySelector(".completion-chart .circle");

            if(!text || !circle)
            {
                lastCompletion = newPercent;
                return;
            }

            const oldPercent = parseInt(text.textContent.replace("%","")) || 0;
            const diff = newPercent - oldPercent;
            

            applyCompletionColor(newPercent);

            // ✨ SHOW DIFF
            showCompletionDiff(diff);

            // 🎬 ANIMATION
            const duration = 600;
            const start = performance.now();

            function animate(time)
            {
                const progress = Math.min((time - start) / duration, 1);
                const ease = 1 - Math.pow(1 - progress, 3);

                const value = Math.round(oldPercent + (newPercent - oldPercent) * ease);

                text.innerHTML = value + "%";
                circle.style.setProperty("--progress", value);

                if(progress < 1)
                {
                    requestAnimationFrame(animate);
                }
                else
                {
                    lastCompletion = newPercent;  // ✅ update AFTER animation

}
            }

            requestAnimationFrame(animate);
            checkCompletionBadges(newPercent);
        }


        function showCompletionDiff(diff)
        {
            if(diff === 0) return;

            const chart = document.querySelector(".masthead-completion-card") || document.querySelector(".completion-chart");
            if(!chart) return;

            const el = document.createElement("div");
            el.className = "completion-diff";

            if(diff > 0)
            {
                el.innerText = "+" + Math.abs(diff) + "%";
                el.classList.add("increase");
            }
            else
            {
                el.innerText = "-" + Math.abs(diff) + "%";
                el.classList.add("decrease");
            }

            chart.appendChild(el);

            setTimeout(() => el.classList.add("show"), 10);
            setTimeout(() => el.remove(), 1200);
        }


        let confettiTriggered = false;
        
        function launchConfetti()
        {
            confetti({
                particleCount: 120,
                spread: 70,
                origin: { y: 0.6 }
            });

            // burst effect
            setTimeout(() =>
            {
                confetti({
                    particleCount: 80,
                    angle: 60,
                    spread: 55,
                    origin: { x: 0 }
                });

                confetti({
                    particleCount: 80,
                    angle: 120,
                    spread: 55,
                    origin: { x: 1 }
                });
            }, 200);
        }

        function checkCompletionBadges(percent)
        {
            if(percent >= 100)
            {
                showBadge("🏆 Profile Master");

launchConfetti();
            }
            else if(percent >= 80)
            {
                showBadge("🔥 Almost There");
            }
            else if(percent >= 50)
            {
                showBadge("💪 Halfway Done");
            }
        }



        function showBadge(text)
        {
            const badge = document.createElement("div");
            badge.className = "completion-badge";
            badge.innerText = text;

            document.body.appendChild(badge);

            setTimeout(() => badge.classList.add("show"), 10);

            setTimeout(() =>
            {
                badge.classList.remove("show");

                setTimeout(() => badge.remove(), 300);
            }, 2000);
        }



        function saveField()
        {
            const field = this.dataset.field;

            if(!field) return;
            
            const value = this.value;

            const text = document.getElementById(field + "Text");
            const input = this;
            const indicator = document.getElementById(field + "Saved");
            const counter = document.getElementById("bioCounter");

            fetch(profileUrl,
            {
                method:"POST",
                headers:
                {
                    "Content-Type":"application/json",
                    "X-CSRFToken": getCSRFToken() || getCookie("csrftoken")
                },
                body: JSON.stringify(
                {
                    field: field,
                    value: value,
                    update_inline: true
                })
            })
            .then(res => typeof window.parseJsonOrSessionExpired === "function" ? window.parseJsonOrSessionExpired(res) : res.json())
            .then(data =>
            {
                if (data.sessionExpired)
                {
                    if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(data);
                    return;
                }

                if(data.error)
                {
                    const errorBox = document.getElementById(field + "Error");

                    if(errorBox)
                    {
                        errorBox.innerText = data.error;
                        errorBox.classList.remove("hidden");
                    }
                    return;
                }

                /* Update UI */
                text.innerText = value;

                if(data.completion !== undefined)
                {
                    updateCompletionUI(data.completion);
                }

                const dot = document.getElementById(field + "Dirty");
                if(dot) dot.classList.add("hidden");

                /* update original value */
                input.dataset.original = value;

                /* hide validation error */
                const errorBox = document.getElementById(field + "Error");
                if(errorBox) errorBox.classList.add("hidden");

                input.classList.add("hidden");
                text.style.display = "block";

                /* hide word counter */
                if(counter) counter.classList.add("hidden");

                /* saved animation */
                if(indicator)
                {
                    indicator.classList.remove("hidden");
                    indicator.classList.add("show");

                    setTimeout(()=>
                    {
                        indicator.classList.remove("show");
                        indicator.classList.add("hidden");
                    },2000);
                }

                if (typeof window.playDataUpdateTone === "function")
                {
                    window.playDataUpdateTone();
                }
            })
            .catch(err => console.error(err));
        }


        /* =====================================================
        MODAL OPEN / CLOSE
        ===================================================== */

        function openPasswordModal()
        {
            const modal = document.getElementById("passwordModal");
            if(!modal) return;
            modal.style.display = "flex";

            document.body.style.overflow = "hidden";
        }

        function closePasswordModal()
        {
            const modal = document.getElementById("passwordModal");
            if(!modal) return;
            modal.style.display = "none";
            document.body.style.overflow = "";

            const form = modal.querySelector("form");
            if(!form) return;

// only clear inputs manually (safe)
            form.querySelectorAll("input").forEach(input =>
            {
                if(input.type !== "hidden")  // keep csrf token safe
                {
                    input.value = "";
                }
            });

            document.getElementById("passwordRules").style.display = "none";

            document.getElementById("passwordStrength").innerText = "";
            document.getElementById("strengthFill").style.width = "0%";

            document.getElementById("passwordMatch").innerText = "";
            document.getElementById("currentWarning").style.display = "none";
            document.getElementById("passwordStrengthContainer").style.display = "none";

            document.getElementById("updatePasswordBtn").disabled = true;

            /* reset password visibility icons */
            document.querySelectorAll(".toggle-pass").forEach(icon =>
            {
                icon.innerText = "👁️";
            });
            document.querySelectorAll(".toggle-pass").forEach(icon =>
            {
                icon.innerHTML = "&#128065;";
            });

            form.querySelectorAll("input").forEach(input =>
            {
                if(input.type === "text")
                {
                    input.type = "password";
                }
            });
            

            /* REMOVE FIELD ERRORS */
            // ❌ DO NOT REMOVE ELEMENTS → just hide text
            document.querySelectorAll("#passwordModal .field-error").forEach(e =>
            {
                e.innerText = "";
                e.style.display = "none";
            });

            document.querySelectorAll("#passwordModal .input-error").forEach(e =>
            {
                e.classList.remove("input-error");
            });

}

        document.addEventListener("DOMContentLoaded", function()
        {
            const hasPasswordErrors = profileHasPasswordErrors;

            if(hasPasswordErrors)
            {
                openPasswordModal();
            }
        });


        /* CLOSE MODAL ON OUTSIDE CLICK */

        window.onclick = function(event)
        {
            const passwordModal = document.getElementById("passwordModal");
            const viewphoto = document.getElementById("viewPhotoModal");
            const editphoto = document.getElementById("editPhotoModal");

            if (event.target === passwordModal)
            {
                closePasswordModal();
            }

            if (event.target === viewphoto)
            {
                closeViewPhoto();
            }

            if (event.target === editphoto)
            {
                closeEditPhoto();
            }
        };


        /* ESC KEY CLOSE */

        document.addEventListener("keydown", function(e)
        {
            const passwordModal = document.getElementById("passwordModal");
            const viewphoto = document.getElementById("viewPhotoModal");
            const editphoto = document.getElementById("editPhotoModal");

            if (e.key === "Escape" )
            {
                if(passwordModal)
                {
                    closePasswordModal();
                }

                if(viewphoto)
                {
                    closeViewPhoto();
                }

                if(editphoto)
                {
                    closeEditPhoto();
                }
            }
        });


        /* =====================================================
        SHOW / HIDE PASSWORD
        ===================================================== */

        function togglePassword(icon)
        {
            const input = icon.parentElement.querySelector("input");
            if(!input) return;

            const isHidden = input.type === "password";
            input.type = isHidden ? "text" : "password";
            icon.innerHTML = isHidden ? "&#128584;" : "&#128065;";
            return;

            if(input.type === "password")
            {
                input.type = "text";
                icon.innerText = "🙈";
            }
            else
            {
                input.type = "password";
                icon.innerText = "👁️";
            }
        }


        /* =====================================================
        PASSWORD STRENGTH CHECK
        ===================================================== */

        document.addEventListener("DOMContentLoaded", function ()
        {
            const oldPass = document.getElementById("id_old_password");
            const newPass = document.getElementById("id_new_password1");
            const confirmPass = document.getElementById("id_new_password2");
            document.getElementById("id_old_password").required = true;

            newPass.readOnly = true;
            confirmPass.readOnly = true;

            const strengthText = document.getElementById("passwordStrength");
            const strengthFill = document.getElementById("strengthFill");

            const matchText = document.getElementById("passwordMatch");

            const updateBtn = document.getElementById("updatePasswordBtn");

            const ruleLength = document.getElementById("ruleLength");
            const ruleUpper = document.getElementById("ruleUpper");
            const ruleNumber = document.getElementById("ruleNumber");
            const ruleSymbol = document.getElementById("ruleSymbol");

            const warning = document.getElementById("currentWarning");

            function showCurrentPasswordWarning()
            {
                warning.style.display = "block";
            }

            /* if user clicks disabled new password */

            newPass.addEventListener("click", function()
            {
                if(newPass.readOnly)
                {
                    showCurrentPasswordWarning();
                }
            });

            /* if user clicks disabled confirm password */

            confirmPass.addEventListener("click", function()
            {
                if(confirmPass.readOnly)
                {
                    return;
                }

                if(oldPass.value.trim() === "")
                {
                    warning.style.display = "block";
                }
            });

            oldPass.addEventListener("input", function()
            {
                if(oldPass.value.trim() !== "")
                {
                    newPass.readOnly = false;
                    warning.style.display = "none";
                }
                else
                {
                    newPass.readOnly = true;
                    confirmPass.readOnly = true;
                }
            });

            function validatePassword()
            {
                const value = newPass.value;

                let validLength = value.length >= 8;
                let validUpper = /[A-Z]/.test(value);
                let validNumber = /[0-9]/.test(value);
                let validSymbol = /[^A-Za-z0-9]/.test(value);

                ruleLength.className = validLength ? "rule-valid" : "rule-invalid";
                ruleUpper.className = validUpper ? "rule-valid" : "rule-invalid";
                ruleNumber.className = validNumber ? "rule-valid" : "rule-invalid";
                ruleSymbol.className = validSymbol ? "rule-valid" : "rule-invalid";

                ruleLength.innerText = (validLength ? "✓" : "✗") + " 8 characters";
                ruleUpper.innerText = (validUpper ? "✓" : "✗") + " 1 uppercase letter";
                ruleNumber.innerText = (validNumber ? "✓" : "✗") + " 1 number";
                ruleSymbol.innerText = (validSymbol ? "✓" : "✗") + " 1 symbol";


                /* strength calculation */

                let score = 0;
                if (validLength) score++;
                if (validUpper) score++;
                if (validNumber) score++;
                if (validSymbol) score++;

                if (score <= 1)
                {
                    strengthText.innerText = "Weak Password";
                    strengthText.className = "password-strength-text strength-weak";
                    strengthFill.style.width = "33%";
                    strengthFill.style.background = "#e74c3c"; // red for medium
                }
                else if (score === 2 || score === 3)
                {
                    strengthText.innerText = "Medium Password";
                    strengthText.className = "password-strength-text strength-medium";
                    strengthFill.style.width = "66%";
                    strengthFill.style.background = "#f39c12"; // orange for medium
                }
                else
                {
                    strengthText.innerText = "Strong Password";
                    strengthText.className = "password-strength-text strength-strong";
                    strengthFill.style.width = "100%";
                    strengthFill.style.background = "#27ae60"; // green for medium
                }

                if(validLength && validUpper && validNumber && validSymbol)
                {
                    confirmPass.readOnly = false;
                }
                else
                {
                    confirmPass.readOnly = true;
                }

                checkMatch();
                updateButtonState();
            }

            function checkMatch()
            {
                const oldValue = oldPass.value;
                const newValue = newPass.value;
                const confirmValue = confirmPass.value;

                let validRules =
                    newValue.length >= 8 &&
                    /[A-Z]/.test(newValue) &&
                    /[0-9]/.test(newValue) &&
                    /[^A-Za-z0-9]/.test(newValue);

                if(confirmPass.readOnly)
                {
                    matchText.innerText = "";
                    return;
                }

                if (confirmValue.length === 0)
                {
                    matchText.innerText = "";
                    return;
                }

                if (newValue === oldValue)
                {
                    matchText.innerText = "New password cannot be same as old password";
                    matchText.className = "password-match match-error";
                    return;
                }

                if (confirmValue !== newValue)
                {
                    matchText.innerText = "Passwords do not match";
                    matchText.className = "password-match match-error";
                }
                else
                {
                    matchText.innerText = "Passwords match";
                    matchText.className = "password-match match-success";
                }


                if(
                    oldPass.value !== "" &&
                    validRules &&
                    confirmValue === newValue &&
                    newValue !== oldValue
                )

                updateButtonState();
            }

            function updateButtonState()
            {
                const oldValue = oldPass.value.trim();
                const newValue = newPass.value;
                const confirmValue = confirmPass.value;

                const validRules =
                    newValue.length >= 8 &&
                    /[A-Z]/.test(newValue) &&
                    /[0-9]/.test(newValue) &&
                    /[^A-Za-z0-9]/.test(newValue);

                if(
                    oldValue !== "" &&
                    validRules &&
                    confirmValue !== "" &&
                    confirmValue === newValue &&
                    newValue !== oldValue
                )
                {
                    updateBtn.disabled = false;
                }
                else
                {
                    updateBtn.disabled = true;
                }
            }

            oldPass.addEventListener("input", function()
            {
                if(oldPass.value.trim() !== "")
                {
                    warning.style.display = "none";
                }
            });

            newPass.addEventListener("focus", function()
            {
                if(oldPass.value.trim() === "")
                {
                    warning.style.display = "block";
                    this.blur();
                }
            });

            newPass.addEventListener("input", function()
            {
                const rules = document.getElementById("passwordRules");
                const strengthBox = document.getElementById("passwordStrengthContainer");

                if(newPass.value.trim() !== "")
                {
                    rules.style.display = "grid";
                    strengthBox.style.display = "block";
                }
                else
                {
                    rules.style.display = "none";
                    strengthBox.style.display = "none";
                }

                validatePassword();
            });

            confirmPass.addEventListener("focus", function()
            {
                if(oldPass.value.trim() === "")
                {
                    warning.style.display = "block";
                    this.blur();
                    return;
                }

                /* hide rules when confirm starts */
                document.getElementById("passwordRules").style.display = "none";
            });

            confirmPass.addEventListener("input", function()
            {
                document.getElementById("passwordRules").style.display = "none";

                checkMatch();
                updateButtonState();
            });
        });

        function clearPassword(icon)
        {
            const input = icon.parentElement.querySelector("input");
            document.getElementById("updatePasswordBtn").disabled = true;
            const strengthContainer = document.getElementById("passwordStrengthContainer");

            input.value = "";
            input.dispatchEvent(new Event("input"));

            const newPass = document.getElementById("id_new_password1");
            const confirmPass = document.getElementById("id_new_password2");

            const rules = document.getElementById("passwordRules");
            const strengthText = document.getElementById("passwordStrength");
            const strengthFill = document.getElementById("strengthFill");
            const matchText = document.getElementById("passwordMatch");
            const warning = document.getElementById("currentWarning");

            /* reset rules + strength */
            if(newPass.value === "")
            {
                rules.style.display = "none";
                strengthContainer.style.display = "none";

                strengthText.innerText = "";
                strengthFill.style.width = "0%";
            }

            /* reset confirm check */
            if(confirmPass.value === "")
            {
                matchText.innerText = "";
            }

            /* clear warning */
            warning.style.display = "none";

            /* lock confirm field again */
            confirmPass.readOnly = true;
        }


        document.querySelectorAll("#passwordModal input").forEach(input =>
        {
            input.addEventListener("input", function()
            {
                // remove error text
                const error = this.closest(".form-group").querySelector(".field-error");
                if(error)
                {
                    error.innerText = "";
                    error.style.display = "none";
                }

                // remove red border
                const wrapper = this.closest(".password-wrapper");
                if(wrapper)
                {
                    wrapper.classList.remove("input-error");
                }
            });
        });


        /* =========================================================
        VIEW PHOTO MODAL
        ========================================================= */

        function openViewPhoto()
        {
            document.getElementById("viewPhotoModal").style.display = "flex";
        }

        function closeViewPhoto()
        {
            document.getElementById("viewPhotoModal").style.display = "none";
            document.body.style.overflow = "";
        }

        /* =========================================================
        EDIT PHOTO MODAL
        ========================================================= */

        function openEditPhoto()
        {
            resetEditor();

            document.getElementById("photoError").classList.add("hidden");
            document.getElementById("uploadArea").classList.remove("error");

            document.getElementById("editPhotoModal").style.display = "flex";
        }

        function handleEditPhotoKey(event)
        {
            if(event.key === "Enter" || event.key === " ")
            {
                openEditPhoto();
            }
        }

        function closeEditPhoto()
        {
            document.getElementById("editPhotoModal").style.display = "none";
            document.body.style.overflow = "";
            resetEditor();
        }

        /* =========================================================
        GLOBAL VARIABLES
        ========================================================= */

        let cropper = null;
        let editing = false;

        /* zoom configuration */

        const MIN_ZOOM = 0.160;
        const MAX_ZOOM = 3;
        const ZOOM_STEP = 0.1;

        let currentZoom = MIN_ZOOM;

        /* DOM references */

        const uploadArea  = document.getElementById("uploadArea");
        const photoInput  = document.getElementById("photoInput");
        const image       = document.getElementById("cropImage");

        const editorLayer = document.getElementById("editorLayer");
        const controls    = document.getElementById("editorControls");
        const uploadBtn   = document.getElementById("uploadPhotoBtn");

        const zoomSlider  = document.getElementById("zoomSlider");
        const previewImg  = document.getElementById("previewAvatar");

        /* =========================================================
        UPDATE ZOOM STATE
        Keeps slider + buttons synchronized
        ========================================================= */

        function updateZoomState()
        {
            if(!cropper) return;

            const percent = ((currentZoom - MIN_ZOOM) / (MAX_ZOOM - MIN_ZOOM)) * 100;

            if(zoomSlider)
            {
                zoomSlider.value = Math.max(0, Math.min(100, percent));
            }

            const zoomInBtn = document.getElementById("zoomInBtn");
            const zoomOutBtn = document.getElementById("zoomOutBtn");
            const resetZoomBtn = document.getElementById("resetZoomBtn");

            if(zoomInBtn)
            {
                zoomInBtn.disabled = currentZoom >= MAX_ZOOM;
            }

            if(zoomOutBtn)
            {
                zoomOutBtn.disabled = currentZoom <= MIN_ZOOM;
            }

            if(resetZoomBtn)
            {
                resetZoomBtn.disabled = currentZoom === MIN_ZOOM;
            }
        }


        /* =========================================================
        UPLOAD AREA CLICK
        ========================================================= */

        uploadArea.addEventListener("click", function()
        {
            if(editing) return;

            photoInput.click();
        });

        /* =========================================================
        FILE SELECT / IMAGE LOAD
        ========================================================= */

        photoInput.addEventListener("change", function()
        {
            const file = this.files[0];

            if(!file) return;

            // ✅ ADD THIS BLOCK
            const allowed = ["image/jpeg", "image/png", "image/webp"];

            if (!allowed.includes(file.type))
            {
                showPhotoError("Only JPG, PNG or WEBP images allowed.");
                this.value = "";
                return;
            }

            if (file.size > 3 * 1024 * 1024)
            {
                showPhotoError("Image must be under 3MB.");
                this.value = "";
                return;
            }

            const url = URL.createObjectURL(file);
            image.src = url;

            image.onload = function()
            {
                uploadArea.style.display = "none";

                editorLayer.classList.remove("hidden");
                controls.classList.remove("hidden");
                uploadBtn.classList.remove("hidden");

                editing = true;

                if(cropper)
                {
                    cropper.destroy();
                }

                cropper = new Cropper(image,
                {
                    aspectRatio:1,
                    viewMode:1,
                    dragMode:'move',
                    autoCropArea:0.6,
                    background:false,
                    responsive:true,
                    wheelZoomRatio:0.1,

                    /* when cropper ready */

                    ready: async function ()
                    {
                        currentZoom = MIN_ZOOM;

                        cropper.zoomTo(currentZoom);

                        zoomSlider.value = 0;

                        updateZoomState();

                        // ✅ THIS IS THE CORRECT PLACE
                        await centerFace(image);
                    },
                    /* zoom event (mouse wheel sync) */

                    zoom(event)
                    {
                        currentZoom = event.detail.ratio;

                        currentZoom =
                            Math.max(MIN_ZOOM,
                            Math.min(MAX_ZOOM, currentZoom));

                        updateZoomState();
                    },

                    /* live preview */

                    crop()
                    {
                        const canvas = cropper.getCroppedCanvas({
                            width:150,
                            height:150
                        });

                        previewImg.src = canvas.toDataURL();
                    }
                });

            };
        });


        /* =========================================================
        DRAG & DROP SUPPORT
        ========================================================= */

        uploadArea.addEventListener("dragover", function(e)
        {
            e.preventDefault();
        });

        uploadArea.addEventListener("drop", function(e)
        {
            e.preventDefault();

            const file = e.dataTransfer.files[0];
            if (!file) return;

            const allowed = ["image/jpeg", "image/png", "image/webp"];

            if (!allowed.includes(file.type))
            {
                showPhotoError("Only JPG, PNG or WEBP images allowed.");
                return;
            }

            if (file.size > 3 * 1024 * 1024)
            {
                showPhotoError("Image must be under 3MB.");
                return;
            }

            photoInput.files = e.dataTransfer.files;
            photoInput.dispatchEvent(new Event("change"));
        });


        /* =========================================================
        ZOOM BUTTONS
        ========================================================= */

        function zoomIn()
        {
            if(!cropper) return;

            if(currentZoom >= MAX_ZOOM) return;

            currentZoom += ZOOM_STEP;

            cropper.zoomTo(currentZoom);

            updateZoomState();
        }

        function zoomOut()
        {
            if(!cropper) return;

            if(currentZoom <= MIN_ZOOM) return;

            currentZoom -= ZOOM_STEP;

            cropper.zoomTo(currentZoom);

            updateZoomState();
        }


        /* =========================================================
        SLIDER CONTROL
        ========================================================= */

        zoomSlider.addEventListener("input", function()
        {
            if(!cropper) return;

            const percent = this.value / 100;

            currentZoom =
                MIN_ZOOM + percent * (MAX_ZOOM - MIN_ZOOM);

            cropper.zoomTo(currentZoom);

            updateZoomState();
        });


        /* =========================================================
        RESET ZOOM
        ========================================================= */

        function resetZoom()
        {
            if(!cropper) return;

            currentZoom = MIN_ZOOM;
            currentRotation = 0; // 🔥 add this

            cropper.zoomTo(currentZoom);
            cropper.rotateTo(0); // 🔥 reset rotation too

            updateZoomState();
        }


        /* =========================================================
        SAVE CROPPED IMAGE
        ========================================================= */


        function showPhotoError(msg)
        {
            const errorBox = document.getElementById("photoError");
            const uploadArea = document.getElementById("uploadArea");

            if(!errorBox || !uploadArea) return;  // ✅ prevent crash as removing error-field result in making csrf token empty/null 

            errorBox.innerText = msg;
            errorBox.classList.remove("hidden");

            uploadArea.classList.add("error");

            setTimeout(() =>
            {
                errorBox.classList.add("hidden");
                uploadArea.classList.remove("error");
            }, 4000);
        }


        function saveCroppedImage()
        {
            if(!cropper) return;

            const uploadBtn = document.getElementById("uploadPhotoBtn");
            const loader = document.getElementById("uploadLoader");
            const text = document.getElementById("uploadText");

            /* START LOADING */
            uploadBtn.disabled = true;
            loader.classList.remove("hidden");
            text.innerText = "Uploading...";


            const canvas = cropper.getCroppedCanvas(
            {
                width:400,
                height:400
            });

            canvas.toBlob(function(blob)
            {
                const formData = new FormData();

                formData.append("profile_photo", blob, "avatar.jpg");
                formData.append("update_photo","1");

                fetch(profileUrl,
                {
                    method:"POST",
                    body:formData,
                    credentials: "same-origin",
                    headers:
                    {
                        "X-CSRFToken": getCSRFToken() || getCookie("csrftoken")
                    }
                })
                .then(res => typeof window.parseJsonOrSessionExpired === "function" ? window.parseJsonOrSessionExpired(res) : res.json())
                .then(data => 
                {
                    /* STOP LOADING */
                    uploadBtn.disabled = false;
                    loader.classList.add("hidden");
                    text.innerText = "Upload Photo";

                    if (data.sessionExpired)
                    {
                        if (typeof window.redirectAfterSessionExpired === "function") window.redirectAfterSessionExpired(data);
                        return;
                    }

                    if(data.error)
                    {
                        showPhotoError(data.error);
                        return;
                    }

                    /* UPDATE PROFILE PHOTO IN UI */
                    const avatar = document.getElementById("profileViewPhotoTrigger");
                    const viewPhoto = document.getElementById("viewProfileImg");
                    const headerAvatar = document.querySelector(".profile-icon img, .profile-icon .profile-avatar-initials");
                    const dropdownAvatar = document.querySelector(".user-info-media img, .user-info .dropdown-avatar-initials");

                    const newURL = data.photo_url + "?t=" + Date.now();

                    function updatePhotoElement(element, className)
                    {
                        if (!element) return;

                        if (element.id === "profileViewPhotoTrigger" && element.tagName !== "IMG")
                        {
                            element.textContent = "";
                            element.classList.remove("profile-photo-initials", "avatar-updating");
                            setTimeout(() =>
                            {
                                element.style.backgroundImage = `url("${newURL}")`;
                                element.style.backgroundSize = "cover";
                                element.style.backgroundPosition = "center";
                                element.classList.add("avatar-updating");
                            }, 50);
                            return;
                        }

                        let image = element;
                        if (element.tagName !== "IMG")
                        {
                            image = document.createElement("img");
                            image.id = element.id || "";
                            image.className = className;
                            image.alt = element.getAttribute("aria-label") || "Profile";

                            if (element.classList.contains("dropdown-avatar-initials"))
                            {
                                const media = document.createElement("span");
                                media.className = "user-info-media";
                                media.appendChild(image);
                                element.replaceWith(media);
                            }
                            else
                            {
                                element.replaceWith(image);
                            }
                        }

                        image.classList.remove("avatar-updating", "profile-photo-initials", "profile-photo-view-initials");

                        setTimeout(() =>
                        {
                            image.src = newURL;
                            image.classList.add("avatar-updating");
                        }, 50);
                    }

                    updatePhotoElement(avatar, "avatar");
                    updatePhotoElement(viewPhoto, "photo-view-img");
                    updatePhotoElement(headerAvatar, "avatar");
                    updatePhotoElement(dropdownAvatar, "");

                    if(data.completion !== undefined)
                    {
                        updateCompletionUI(data.completion);
                    }

                    try
                    {
                        localStorage.setItem("profile-photo-updated", JSON.stringify({
                            at: Date.now(),
                            photo_url: data.photo_url || ""
                        }));
                    }
                    catch (error)
                    {
                        window.dispatchEvent(new CustomEvent("profile-photo-updated", {
                            detail: {
                                photo_url: data.photo_url || ""
                            }
                        }));
                    }

                    closeEditPhoto();

                    if (typeof window.playDataUpdateTone === "function")
                    {
                        window.playDataUpdateTone();
                    }
                })
                .catch(() =>
                {
                    uploadBtn.disabled = false;
                    loader.classList.add("hidden");
                    text.innerText = "Upload Photo";

                    showPhotoError("Upload failed. Please try again.");
                });
            });
        }



        /* =====================================================
        GET DJANGO CSRF TOKEN
        ===================================================== */

        function getCookie(name)
        {
            let cookieValue = null;

            if (document.cookie && document.cookie !== "")
            {
                const cookies = document.cookie.split(";");

                for (let i = 0; i < cookies.length; i++)
                {
                    const cookie = cookies[i].trim();

                    if (cookie.substring(0, name.length + 1) === (name + "="))
                    {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }

            return cookieValue;
        }


        /* =========================================================
        RESET EDITOR
        Resets everything when modal closes or image cancelled
        ========================================================= */

        function resetEditor()
        {
            if(cropper)
            {
                cropper.destroy();
                cropper = null;
            }

            editing = false;

            currentRotation = 0;

            /* reset file input */
            photoInput.value = "";

            /* reset image */
            image.src = "";

            /* show upload area again */
            uploadArea.style.display = "flex";

            /* hide editor */
            editorLayer.classList.add("hidden");
            controls.classList.add("hidden");
            uploadBtn.classList.add("hidden");

            /* reset zoom */
            currentZoom = MIN_ZOOM;
            zoomSlider.value = 0;

            /* reset preview */

            if(previewImg)
            {
                previewImg.src = "";
            }
        }

        /* =========================================================
        🔥 FULL AI FACE SYSTEM (FINAL)
        ========================================================= */

        let faceModelLoaded = false;
        let previewFrame;

        /* ================= LOAD MODELS ================= */

        async function loadFaceModel() 
        {
            if (faceModelLoaded) return;

            const MODEL_URL = "https://justadudewhohacks.github.io/face-api.js/models";

            await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
            await faceapi.nets.faceLandmark68TinyNet.loadFromUri(MODEL_URL);

            faceModelLoaded = true;
            console.log("Models loaded ✅");
        }

        /* ================= EYE ANGLE ================= */

        function getEyeAngle(landmarks) 
        {
            const leftEye = landmarks.getLeftEye()[0];
            const rightEye = landmarks.getRightEye()[3];

            const dx = rightEye.x - leftEye.x;
            const dy = rightEye.y - leftEye.y;

            return Math.atan2(dy, dx) * (180 / Math.PI);
        }

        /* ================= SMOOTH CROP ================= */

        function animateCrop(target) 
        {
            const duration = 300;
            const start = performance.now();
            const initial = cropper.getCropBoxData();

            function animate(time) 
            {
                const progress = Math.min((time - start) / duration, 1);
                const ease = 1 - Math.pow(1 - progress, 3);

                cropper.setCropBoxData(
                {
                    left: initial.left + (target.left - initial.left) * ease,
                    top: initial.top + (target.top - initial.top) * ease,
                    width: initial.width + (target.width - initial.width) * ease,
                    height: initial.height + (target.height - initial.height) * ease
                });

                if (progress < 1) requestAnimationFrame(animate);
            }

            requestAnimationFrame(animate);
        }

        /* ================= MAIN AI FACE LOGIC ================= */

        async function centerFace(imageElement) 
        {
            try 
            {
                await loadFaceModel();

                await new Promise(r => setTimeout(r, 300));

                const detections = await faceapi
                    .detectAllFaces(imageElement, new faceapi.TinyFaceDetectorOptions())
                    .withFaceLandmarks(true);

                if (!detections.length) return;

                // 👥 BEST FACE
                let best = detections[0];
                detections.forEach(d => 
                {
                    if (d.detection.box.area > best.detection.box.area) 
                    {
                        best = d;
                    }
                });

                const face = best.detection.box;
                const landmarks = best.landmarks;

                // 🎯 ALIGN FACE

const canvasData = cropper.getCanvasData();
                const scaleX = canvasData.width / imageElement.naturalWidth;
                const scaleY = canvasData.height / imageElement.naturalHeight;

                // 🧠 SMART POSITION
                let centerX = canvasData.left + (face.x + face.width / 2) * scaleX;
                let centerY = canvasData.top + (face.y + face.height * 0.35) * scaleY;

                // 🔍 AUTO ZOOM
                const faceWidthScaled = face.width * scaleX;
                const size = faceWidthScaled / 0.6;

                animateCrop(
                    {
                    left: centerX - size / 2,
                    top: centerY - size / 2,
                    width: size,
                    height: size
                });

            } 
            catch (err) 
            {
                console.error("Face detection failed:", err);
            }
        }

        let currentRotation = 0;

        function rotateImage()
        {
            if (!cropper) return;

            currentRotation += 15; // rotate by 15 degrees
            cropper.rotateTo(currentRotation);
        }
