class SolutionsDashboard {
    constructor() {
        this.solutions = [];
        this.counts = {};
        this.filter = "all";
        this.eventSource = null;
        this.testResults = new Map();

        this.countProjects = document.getElementById("countProjects");
        this.countFullStack = document.getElementById("countFullStack");
        this.countMvp = document.getElementById("countMvp");
        this.countDesktop = document.getElementById("countDesktop");
        this.gridTitle = document.getElementById("gridTitle");
        this.gridSubtitle = document.getElementById("gridSubtitle");
        this.solutionGrid = document.getElementById("solutionGrid");
        this.filterGroup = document.getElementById("filterGroup");
        this.streamStatus = document.getElementById("streamStatus");
        this.streamLog = document.getElementById("streamLog");

        this.rescanBtn = document.getElementById("rescanBtn");
        this.testMvpBtn = document.getElementById("testMvpBtn");
        this.testAllBtn = document.getElementById("testAllBtn");
        this.stopStreamBtn = document.getElementById("stopStreamBtn");

        this.detailsDialog = document.getElementById("detailsDialog");
        this.dialogTitle = document.getElementById("dialogTitle");
        this.dialogBody = document.getElementById("dialogBody");
        this.closeDialogBtn = document.getElementById("closeDialogBtn");
    }

    async init() {
        this.bindEvents();
        await this.loadOverview(false);
    }

    bindEvents() {
        this.rescanBtn.addEventListener("click", () => this.loadOverview(true));
        this.testMvpBtn.addEventListener("click", () => this.startStream("mvp28"));
        this.testAllBtn.addEventListener("click", () => this.startStream("all"));
        this.stopStreamBtn.addEventListener("click", () => this.stopStream("Stopped by user."));
        this.closeDialogBtn.addEventListener("click", () => this.detailsDialog.close());

        this.filterGroup.addEventListener("click", (event) => {
            const btn = event.target.closest("button[data-filter]");
            if (!btn) return;
            this.filter = btn.dataset.filter;
            for (const node of this.filterGroup.querySelectorAll(".filter-btn")) {
                node.classList.toggle("active", node === btn);
            }
            this.renderGrid();
        });

        this.solutionGrid.addEventListener("click", (event) => {
            const testBtn = event.target.closest("button[data-test-solution]");
            if (testBtn) {
                this.startStream("custom", [testBtn.dataset.testSolution]);
                return;
            }

            const detailBtn = event.target.closest("button[data-show-details]");
            if (detailBtn) {
                const solution = this.solutions.find((item) => item.solution_id === detailBtn.dataset.showDetails);
                if (solution) this.showDetails(solution);
            }
        });
    }

    async loadOverview(refresh = false) {
        this.logLine(refresh ? "Rescanning workspace inventory..." : "Loading workspace inventory...");
        const url = refresh ? "/api/solutions/overview?refresh=true" : "/api/solutions/overview";
        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok) {
            this.logLine(`Inventory load failed (${response.status})`, "fail");
            return;
        }
        const payload = await response.json();
        this.solutions = payload.solutions || [];
        this.counts = payload.counts || {};
        this.renderMetrics();
        this.renderGrid();
        this.logLine(
            `Inventory ready: ${this.counts.top_level_projects || 0} projects, ${this.counts.mvp || 0} MVP.`
        );
    }

    renderMetrics() {
        this.countProjects.textContent = this.counts.top_level_projects || 0;
        this.countFullStack.textContent = this.counts.full_stack || 0;
        this.countMvp.textContent = this.counts.mvp || 0;
        this.countDesktop.textContent = this.counts.desktop || 0;
    }

    visibleSolutions() {
        if (this.filter === "all") return this.solutions;
        if (this.filter === "mvp") return this.solutions.filter((item) => item.is_mvp);
        return this.solutions.filter((item) => item.category === this.filter);
    }

    renderGrid() {
        const list = this.visibleSolutions();
        this.gridTitle.textContent =
            this.filter === "mvp" ? "MVP 28 Solutions" : `${this.filter === "all" ? "All" : this.filter} Solutions`;
        this.gridSubtitle.textContent = `${list.length} visible solution cards`;
        this.solutionGrid.innerHTML = "";

        if (!list.length) {
            this.solutionGrid.innerHTML = "<p>No solution available for this view.</p>";
            return;
        }

        for (const solution of list) {
            const card = document.createElement("article");
            card.className = "solution-card";
            const test = this.testResults.get(solution.solution_id);
            const status = test ? test.status : "untested";

            const badges = [
                `<span class="badge">${solution.category}</span>`,
                `<span class="badge">${solution.platform}</span>`,
            ];
            if (solution.is_mvp) badges.push('<span class="badge mvp">MVP 28</span>');
            if (status !== "untested") badges.push(this.statusBadge(status, test.score));
            if (solution.duplicate_group) badges.push('<span class="badge">duplicate</span>');
            let semanticHint = "";
            if (test && test.content_audit) {
                const label = test.content_audit.passed ? "plain-lang ok" : "plain-lang review";
                const cls = test.content_audit.passed ? "status-pass" : "status-warn";
                const pagesPassed = Number(test.content_audit.pages_passed || 0);
                const pagesTested = Number(test.content_audit.pages_tested || 0);
                const suffix = pagesTested > 0 ? ` ${pagesPassed}/${pagesTested}` : "";
                badges.push(`<span class="badge ${cls}">${label}${suffix}</span>`);
                const issues = Array.isArray(test.content_audit.issues) ? test.content_audit.issues : [];
                const shouldShowSemanticHint = status !== "pass" || !test.content_audit.passed;
                if (issues.length && shouldShowSemanticHint) {
                    semanticHint = `<p class="semantic-hint">${this.escape(issues[0])}</p>`;
                }
            }

            // Prioritize discovered URLs (from config/registry) over guessed defaults
            const discoveredUrls = solution.discovered_urls || [];
            const allUrls = solution.local_urls || [];
            const primaryUrl = discoveredUrls[0] || allUrls[0];
            const openButton = primaryUrl
                ? `<a class="btn btn-small" href="${primaryUrl}" target="_blank" rel="noopener">Open URL</a>`
                : `<button class="btn btn-small" disabled>No URL</button>`;

            // Live status indicator based on test results
            let liveIndicator = "";
            if (test && test.checks) {
                const portCheck = test.checks.find(c => c.name === "port_open");
                if (portCheck && portCheck.detail !== "No local URLs to probe") {
                    if (portCheck.passed) {
                        liveIndicator = '<span class="live-dot live" title="Service is running"></span>';
                    } else {
                        liveIndicator = '<span class="live-dot down" title="Service not responding"></span>';
                    }
                } else if (discoveredUrls.length === 0) {
                    liveIndicator = '<span class="live-dot unknown" title="No discovered URL"></span>';
                }
            }

            card.innerHTML = `
                <div class="card-head">
                    <h4 class="card-title">${liveIndicator}${this.escape(solution.name)}</h4>
                    <div class="badges">${badges.join("")}</div>
                </div>
                <p class="path">${this.escape(solution.path)}</p>
                ${semanticHint}
                <div class="card-actions">
                    ${openButton}
                    <button class="btn btn-small" data-test-solution="${solution.solution_id}">Test</button>
                    <button class="btn btn-small" data-show-details="${solution.solution_id}">Details</button>
                </div>
            `;
            this.solutionGrid.appendChild(card);
        }
    }

    statusBadge(status, score) {
        const normalized = status || "untested";
        if (normalized === "pass") return `<span class="badge status-pass">pass ${score}%</span>`;
        if (normalized === "warn") return `<span class="badge status-warn">warn ${score}%</span>`;
        if (normalized === "fail") return `<span class="badge status-fail">fail ${score}%</span>`;
        return '<span class="badge">untested</span>';
    }

    showDetails(solution) {
        const test = this.testResults.get(solution.solution_id);
        this.dialogTitle.textContent = `${solution.name} (${solution.solution_id})`;
        if (!test) {
            this.dialogBody.innerHTML = "<p>No test run yet for this solution.</p>";
            this.detailsDialog.showModal();
            return;
        }

        const audit = test.content_audit || {};
        const issues = Array.isArray(audit.issues) ? audit.issues : [];
        const recommendations = Array.isArray(audit.recommendations) ? audit.recommendations : [];
        const samples = Array.isArray(audit.samples) ? audit.samples : [];
        const sampleRows = samples
            .slice(0, 6)
            .map((sample) => {
                const sampleIssues = Array.isArray(sample.issues) ? sample.issues.join(" | ") : "";
                return `
                    <tr>
                        <td>${this.escape(sample.source_label || sample.source_ref || "n/a")}</td>
                        <td>${this.escape(String(sample.score ?? 0))}</td>
                        <td>${sample.passed ? "pass" : "review"}</td>
                        <td>${this.escape(sampleIssues || "-")}</td>
                    </tr>
                `;
            })
            .join("");

        const checks = Array.isArray(test.checks) ? test.checks : [];
        const failedChecks = checks.filter((check) => !check.passed);
        const checkText = failedChecks.length
            ? failedChecks.map((check) => `${check.name}: ${check.detail}`).join("\n")
            : "No failing structural checks.";

        // Build live status section from port_open and http_live checks
        const portCheck = checks.find(c => c.name === "port_open");
        const httpCheck = checks.find(c => c.name === "http_live");
        let liveSection = "";
        if (portCheck || httpCheck) {
            const portHtml = portCheck
                ? `<p><strong>Port probe:</strong> <span class="${portCheck.passed ? 'status-pass' : 'status-fail'}">${portCheck.passed ? '● UP' : '● DOWN'}</span> — ${this.escape(portCheck.detail)}</p>`
                : "";
            const httpHtml = httpCheck
                ? `<p><strong>HTTP check:</strong> <span class="${httpCheck.passed ? 'status-pass' : 'status-fail'}">${httpCheck.passed ? '● OK' : '● FAIL'}</span> — ${this.escape(httpCheck.detail)}</p>`
                : "";
            const screenshotHtml = test.screenshot_path
                ? `<div class="screenshot-proof"><p><strong>Visual proof:</strong></p><img src="${test.screenshot_path}?t=${Date.now()}" alt="Live screenshot" class="screenshot-img"></div>`
                : "";
            liveSection = `
                <section>
                    <h4>Live Service Status</h4>
                    ${portHtml}
                    ${httpHtml}
                    ${screenshotHtml}
                </section>
            `;
        }

        // Show discovered vs default URLs
        const discoveredUrls = solution.discovered_urls || [];
        const allUrls = solution.local_urls || [];
        const urlSection = `
            <section>
                <h4>URLs</h4>
                <p><strong>Discovered (from config):</strong> ${discoveredUrls.length ? discoveredUrls.map(u => `<a href="${u}" target="_blank">${u}</a>`).join(", ") : "none"}</p>
                <p><strong>All (incl. guessed):</strong> ${allUrls.length ? allUrls.join(", ") : "none"}</p>
            </section>
        `;

        this.dialogBody.innerHTML = `
            ${liveSection}
            ${urlSection}
            <section>
                <p><strong>Test status:</strong> ${this.escape(test.status || "unknown")} (${this.escape(String(test.score || 0))}%)</p>
                <p><strong>Plain-language:</strong> ${audit.passed ? "pass" : "review"} (${this.escape(String(audit.score || 0))}%)</p>
                <p><strong>Pages:</strong> ${this.escape(String(audit.pages_passed || 0))}/${this.escape(String(audit.pages_tested || 0))}</p>
                <p><strong>Main source:</strong> ${this.escape(audit.source_ref || "none")}</p>
            </section>
            <section>
                <h4>Top issues</h4>
                <p>${this.escape(issues.join(" | ") || "No semantic issue detected.")}</p>
            </section>
            <section>
                <h4>Rewrite suggestions</h4>
                <p>${this.escape(recommendations.join(" | ") || "No suggestion.")}</p>
            </section>
            <section>
                <h4>Page samples</h4>
                <table class="details-table">
                    <thead>
                        <tr><th>Source</th><th>Score</th><th>Status</th><th>Issues</th></tr>
                    </thead>
                    <tbody>${sampleRows || '<tr><td colspan="4">No samples collected.</td></tr>'}</tbody>
                </table>
            </section>
            <section>
                <h4>Structural failures</h4>
                <pre>${this.escape(checkText)}</pre>
            </section>
        `;
        this.detailsDialog.showModal();
    }

    startStream(scope, solutionIds = []) {
        this.stopStream();
        const params = new URLSearchParams();
        params.set("scope", scope);
        for (const id of solutionIds) params.append("solution_id", id);

        const streamUrl = `/api/solutions/test-stream?${params.toString()}`;
        this.streamStatus.textContent = `Streaming: ${scope}`;
        this.logLine(`Stream started (${scope})`);
        const source = new EventSource(streamUrl);
        this.eventSource = source;

        source.addEventListener("start", (event) => {
            const data = JSON.parse(event.data);
            this.logLine(`Test batch started (${data.scope}).`);
        });

        source.addEventListener("solution", (event) => {
            const data = JSON.parse(event.data);
            const result = data.result;
            this.testResults.set(result.solution_id, result);
            this.renderGrid();
            this.logLine(
                `(${data.index}/${data.total}) ${result.name}: ${result.status.toUpperCase()} (${result.score}%)`,
                result.status
            );
        });

        source.addEventListener("complete", (event) => {
            const data = JSON.parse(event.data);
            const summary = data.summary || {};
            this.streamStatus.textContent = `Done in ${data.duration_seconds}s`;
            this.logLine(
                `Completed: pass=${summary.pass || 0} warn=${summary.warn || 0} fail=${summary.fail || 0} avg=${summary.average_score || 0}% plain=${summary.plain_language_pass || 0}/${summary.total || 0} missing-source=${summary.plain_language_missing_source || 0}`
            );
            this.stopStream();
        });

        source.onerror = () => {
            this.logLine("Stream disconnected.", "warn");
            this.stopStream("Disconnected");
        };
    }

    stopStream(statusText = "Idle") {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.streamStatus.textContent = statusText;
    }

    logLine(message, type = "") {
        const node = document.createElement("div");
        node.className = `stream-line ${type}`.trim();
        const stamp = new Date().toLocaleTimeString();
        node.textContent = `[${stamp}] ${message}`;
        this.streamLog.prepend(node);
    }

    escape(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }
}

window.addEventListener("DOMContentLoaded", () => {
    const dashboard = new SolutionsDashboard();
    dashboard.init().catch((err) => {
        // Keep this surfaced in console for deep debugging if the UI fails.
        console.error("Solutions dashboard failed to initialize", err);
    });
});
