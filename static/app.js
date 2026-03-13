// WebSocket connection
let ws = null;
let isConnected = false;

// --- DOM Elements (Centralized) ---
const urlInput = document.getElementById('urlInput');
const navigateBtn = document.getElementById('navigateBtn');
const queryInput = document.getElementById('queryInput');
const analyzeBtn = document.getElementById('analyzeBtn');
const extractDomBtn = document.getElementById('extractDomBtn');
const screenshotBtn = document.getElementById('screenshotBtn');
const taskInput = document.getElementById('taskInput');
const executeBtn = document.getElementById('executeBtn');

// Status & Indicators
const statusDot = document.getElementById('connectionStatus'); // Fixed ID from index.html
const statusText = document.getElementById('statusText');
const previewContainer = document.getElementById('previewContainer');
const livePreview = document.getElementById('livePreview');
const previewPlaceholder = document.getElementById('previewPlaceholder'); // Fixed ID
const pageTitle = document.getElementById('pageTitle');

// Tabs & Output
const consoleOutput = document.getElementById('consoleOutput');
const domOutput = document.getElementById('domOutput');
const semanticOutput = document.getElementById('semanticOutput');
const tabButtons = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');

// Mode Switcher Elements
const browserModeBtn = document.getElementById('browserModeBtn');
const researchModeBtn = document.getElementById('researchModeBtn');
const browserPanelEl = document.getElementById('browserPanel');
const researchPanelEl = document.getElementById('researchPanel');

// --- Helper Functions ---

function logConsole(message, type = 'info') {
    if (!consoleOutput) return;
    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.textContent = `[${timestamp}] ${message}`;
    consoleOutput.prepend(entry);
}

// --- WebSocket Logic ---

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    logConsole(`Connecting to ${wsUrl}...`, 'info');
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        isConnected = true;
        if (statusDot) {
            statusDot.style.background = '#10B981'; // Green
            statusDot.classList.add('connected');
        }
        if (statusText) statusText.textContent = 'Connected';
        logConsole('WebSocket connected', 'success');
    };

    ws.onclose = () => {
        isConnected = false;
        if (statusDot) {
            statusDot.style.background = '#EF4444'; // Red
            statusDot.classList.remove('connected');
        }
        if (statusText) statusText.textContent = 'Disconnected';
        logConsole('WebSocket disconnected', 'warning');
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
        logConsole('WebSocket error occurred', 'error');
    };

    ws.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            handleMessage(message);
        } catch (e) {
            logConsole(`Error parsing message: ${e}`, 'error');
        }
    };
}

function handleMessage(message) {
    const { type, data } = message;

    switch (type) {
        case 'navigation':
            handleNavigation(data);
            logConsole(`Navigated to: ${data.url}`, 'success');
            break;
        case 'analysis':
            if (semanticOutput) {
                // Formatting for readability
                const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
                semanticOutput.innerText = text;
            }
            logConsole('AI Analysis received', 'success');
            break;
        case 'dom':
            if (domOutput) domOutput.textContent = JSON.stringify(data, null, 2);
            logConsole('DOM extracted', 'success');
            break;
        case 'status':
            // Visual pulse for the autonomous agent
            if (data.status === 'Thinking...') {
                logConsole(`[AGENT] ${data.message}`, 'info');
                if (statusText) statusText.textContent = data.message;
                if (statusDot) statusDot.style.animation = 'pulse 1s infinite';
            } else {
                if (statusDot) statusDot.style.animation = 'none';
            }
            break;
        case 'error':
            logConsole(`Server Error: ${data}`, 'error');
            break;
        // ═══ DEEP AUDIT MESSAGES ═══
        case 'audit_progress':
            handleAuditProgress(data);
            break;
        case 'audit_complete':
            window._lastAuditData = data;
            handleAuditComplete(data);
            break;
        default:
            logConsole(`Received: ${type}`, 'info');
    }
}

// ═══ DEEP AUDIT HANDLERS ═══

function handleAuditProgress(data) {
    const auditLog = document.getElementById('auditLog');
    const auditStatus = document.getElementById('auditStatus');

    if (auditLog) {
        const entry = document.createElement('div');
        entry.className = `audit-log-entry audit-${data.phase || 'active'}`;

        if (data.phase === 'phase') {
            entry.style.fontWeight = 'bold';
            entry.style.color = '#818cf8';
            entry.style.borderLeft = '3px solid #818cf8';
            entry.style.paddingLeft = '8px';
            entry.style.marginTop = '8px';
        } else if (data.phase === 'completed') {
            entry.style.color = '#10B981';
            entry.style.fontWeight = 'bold';
        } else if (data.phase === 'warning') {
            entry.style.color = '#F59E0B';
        }

        entry.textContent = data.message;
        auditLog.appendChild(entry);
        auditLog.scrollTop = auditLog.scrollHeight;
    }

    if (auditStatus) {
        auditStatus.textContent = data.message;
    }

    logConsole(`[AUDIT] ${data.message}`, data.phase === 'completed' ? 'success' : 'info');
}

function handleAuditComplete(data) {
    const auditReport = document.getElementById('auditReport');
    const startAuditBtn = document.getElementById('startAuditBtn');
    if (startAuditBtn) startAuditBtn.disabled = false;

    // Store CSV for download
    window._xrayCsv = data.xray_csv || '';

    if (!auditReport) return;

    let html = '';

    // ── Xray CSV Download Button ──
    if (window._xrayCsv) {
        html += `<div style="margin-bottom:16px;display:flex;gap:8px;">`;
        html += `<button onclick="downloadXrayCsv()" style="padding:8px 16px;background:linear-gradient(135deg,#10B981,#059669);border:none;border-radius:8px;color:white;font-weight:600;cursor:pointer;font-size:12px;">📥 Download Xray CSV</button>`;
        html += `<button onclick="downloadJsonReport()" style="padding:8px 16px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border:none;border-radius:8px;color:white;font-weight:600;cursor:pointer;font-size:12px;">📄 Download JSON Report</button>`;
        html += `</div>`;
    }

    // ── Executive Summary ──
    const strategy = data.strategy || {};
    html += `<div class="report-section">`;
    html += `<h3>📋 Executive Summary</h3>`;
    html += `<p>${strategy.executive_summary || 'N/A'}</p>`;
    html += `</div>`;

    // ── Sitemap Stats ──
    const sm = data.sitemap || {};
    html += `<div class="report-section">`;
    html += `<h3>🕷️ Site Map</h3>`;
    html += `<div class="stat-grid">`;
    html += `<div class="stat"><span class="stat-value">${sm.pages_crawled || 0}</span><span class="stat-label">Pages</span></div>`;
    html += `<div class="stat"><span class="stat-value">${sm.total_links || 0}</span><span class="stat-label">Links</span></div>`;
    html += `<div class="stat"><span class="stat-value">${sm.total_buttons || 0}</span><span class="stat-label">Buttons</span></div>`;
    html += `<div class="stat"><span class="stat-value">${sm.total_forms || 0}</span><span class="stat-label">Forms</span></div>`;
    html += `<div class="stat"><span class="stat-value">${sm.total_images || 0}</span><span class="stat-label">Images</span></div>`;
    html += `</div></div>`;

    // ── Workflows ──
    const wfs = (data.workflows || {}).workflows || [];
    html += `<div class="report-section">`;
    html += `<h3>🔄 E2E Workflows (${wfs.length})</h3>`;
    for (const wf of wfs) {
        html += `<div class="workflow-card">`;
        html += `<strong>[${(wf.priority || '?').toUpperCase()}]</strong> ${wf.name || 'Unnamed'}`;
        if (wf.pre_conditions && wf.pre_conditions.length) {
            html += `<div style="font-size:11px;color:var(--text-tertiary);margin-top:4px;">Pre: ${wf.pre_conditions.join(', ')}</div>`;
        }
        html += `<div class="workflow-steps">`;
        for (const step of (wf.steps || [])) {
            html += `<div class="step">→ ${step.action || step.description || 'Action'}`;
            if (step.assertion) html += ` <em style="color:#818cf8">[${step.assertion}]</em>`;
            html += `</div>`;
        }
        html += `</div>`;
        if (wf.expected_outcome) {
            html += `<div style="font-size:11px;color:#10B981;margin-top:4px;">✓ ${wf.expected_outcome}</div>`;
        }
        html += `</div>`;
    }
    html += `</div>`;

    // ── Test Plan Full Spec ──
    const tp = (data.test_plan || {}).test_plan || {};
    const cats = tp.categories || [];

    // Plan Header
    html += `<div class="report-section">`;
    html += `<h3>✅ Test Plan: ${tp.name || 'Functional Test Plan'}</h3>`;
    html += `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px;margin-bottom:12px;">`;
    html += `<div><strong>Version:</strong> ${tp.version || '1.0'}</div>`;
    html += `<div><strong>Created:</strong> ${tp.created || 'N/A'}</div>`;
    html += `<div style="grid-column:1/-1;"><strong>Objective:</strong> ${tp.objective || 'N/A'}</div>`;
    html += `</div>`;

    // Scope
    const scope = tp.scope || {};
    if ((scope.in_scope || []).length > 0 || (scope.out_of_scope || []).length > 0) {
        html += `<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">`;
        html += `<div><strong style="color:#10B981;">✓ In Scope</strong><ul style="margin:4px 0;padding-left:16px;font-size:12px;">`;
        for (const s of (scope.in_scope || [])) html += `<li>${s}</li>`;
        html += `</ul></div>`;
        html += `<div><strong style="color:#EF4444;">✗ Out of Scope</strong><ul style="margin:4px 0;padding-left:16px;font-size:12px;">`;
        for (const s of (scope.out_of_scope || [])) html += `<li>${s}</li>`;
        html += `</ul></div>`;
        html += `</div>`;
    }

    // Methodology
    if ((tp.testing_methodology || []).length > 0) {
        html += `<div style="margin-bottom:12px;"><strong>Methodology:</strong> `;
        html += (tp.testing_methodology || []).map(m => `<span class="badge" style="background:rgba(99,102,241,0.15);color:#a5b4fc;margin-right:4px;">${m}</span>`).join('');
        html += `</div>`;
    }

    // Entry / Exit Criteria
    html += `<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">`;
    html += `<div><strong style="color:#F59E0B;">⬇ Entry Criteria</strong><ul style="margin:4px 0;padding-left:16px;font-size:12px;">`;
    for (const c of (tp.entry_criteria || [])) html += `<li>${c}</li>`;
    html += `</ul></div>`;
    html += `<div><strong style="color:#10B981;">⬆ Exit Criteria</strong><ul style="margin:4px 0;padding-left:16px;font-size:12px;">`;
    for (const c of (tp.exit_criteria || [])) html += `<li>${c}</li>`;
    html += `</ul></div></div>`;

    // Test Environment
    const env = tp.test_environment || {};
    if (Object.keys(env).length > 0) {
        html += `<div style="margin-bottom:12px;"><strong>Test Environment:</strong><div style="display:flex;gap:16px;font-size:12px;margin-top:4px;">`;
        if (env.browsers) html += `<div>🌐 ${(env.browsers || []).join(', ')}</div>`;
        if (env.devices) html += `<div>📱 ${(env.devices || []).join(', ')}</div>`;
        if (env.tools) html += `<div>🔧 ${(env.tools || []).join(', ')}</div>`;
        html += `</div></div>`;
    }

    // Risks
    if ((tp.risks || []).length > 0) {
        html += `<div style="margin-bottom:12px;"><strong>⚠️ Risks:</strong>`;
        for (const r of tp.risks) {
            html += `<div class="recommendation" style="margin-top:4px;">`;
            html += `${r.risk} <span class="badge impact-${r.impact || 'medium'}">${r.impact || '?'}</span>`;
            html += ` → <em>${r.mitigation || 'No mitigation'}</em>`;
            html += `</div>`;
        }
        html += `</div>`;
    }

    // Test Categories
    html += `<div style="margin-top:12px;"><strong>Total Tests: ${tp.total_tests || 0}</strong></div>`;
    for (const cat of cats) {
        html += `<div class="test-category">`;
        html += `<strong>${cat.name}</strong> (${(cat.tests || []).length} tests)`;
        html += `<ul>`;
        for (const t of (cat.tests || []).slice(0, 8)) {
            const sevClass = t.severity === 'blocker' || t.severity === 'critical' ? 'impact-high' : t.severity === 'major' ? 'impact-medium' : 'impact-low';
            html += `<li>`;
            html += `<code>${t.id || '?'}</code> ${t.summary || t.description || ''}`;
            html += ` <span class="badge ${sevClass}">${t.severity || t.priority || '?'}</span>`;
            if (t.steps && t.steps.length) {
                html += ` <em style="color:var(--text-tertiary);font-size:11px;">(${t.steps.length} steps)</em>`;
            }
            html += `</li>`;
        }
        if ((cat.tests || []).length > 8) {
            html += `<li style="color:var(--text-tertiary);">... +${(cat.tests || []).length - 8} more</li>`;
        }
        html += `</ul></div>`;
    }
    html += `</div>`;

    // ── Critical Issues ──
    if ((strategy.critical_issues || []).length > 0) {
        html += `<div class="report-section">`;
        html += `<h3>🔴 Critical Issues</h3>`;
        html += `<ul>`;
        for (const issue of strategy.critical_issues) html += `<li>${issue}</li>`;
        html += `</ul></div>`;
    }

    // ── Recommendations ──
    if ((strategy.recommendations || []).length > 0) {
        html += `<div class="report-section">`;
        html += `<h3>💡 Recommendations</h3>`;
        for (const rec of strategy.recommendations) {
            html += `<div class="recommendation">`;
            html += `<strong>#${rec.priority || '?'}</strong> ${rec.action || ''} `;
            html += `<span class="badge impact-${rec.impact || 'medium'}">Impact: ${rec.impact || '?'}</span> `;
            html += `<span class="badge effort-${rec.effort || 'medium'}">Effort: ${rec.effort || '?'}</span>`;
            html += `</div>`;
        }
        html += `</div>`;
    }

    // ── Next Steps ──
    if ((strategy.next_steps || []).length > 0) {
        html += `<div class="report-section">`;
        html += `<h3>🚀 Next Steps</h3>`;
        html += `<ol>`;
        for (const step of strategy.next_steps) html += `<li>${step}</li>`;
        html += `</ol></div>`;
    }

    auditReport.innerHTML = html;
    auditReport.style.display = 'block';
}

// ═══ DOWNLOAD FUNCTIONS ═══

function downloadXrayCsv() {
    if (!window._xrayCsv) return;
    const blob = new Blob([window._xrayCsv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `xray_test_cases_${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
    logConsole('Xray CSV downloaded', 'success');
}
window.downloadXrayCsv = downloadXrayCsv;

function downloadJsonReport() {
    if (!window._lastAuditData) return;
    const clean = { ...window._lastAuditData };
    delete clean.xray_csv;
    const blob = new Blob([JSON.stringify(clean, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `deep_audit_report_${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    logConsole('JSON report downloaded', 'success');
}
window.downloadJsonReport = downloadJsonReport;

// ═══ DEEP AUDIT TRIGGER ═══

function startDeepAudit() {
    if (!ws || !isConnected) return logConsole('Not connected', 'error');

    const auditUrlInput = document.getElementById('auditUrlInput');
    const url = auditUrlInput ? auditUrlInput.value.trim() : '';
    if (!url) return logConsole('Enter a URL for deep audit', 'error');

    const auditLog = document.getElementById('auditLog');
    const auditReport = document.getElementById('auditReport');
    const startAuditBtn = document.getElementById('startAuditBtn');

    if (auditLog) auditLog.innerHTML = '';
    if (auditReport) { auditReport.innerHTML = ''; auditReport.style.display = 'none'; }
    if (startAuditBtn) startAuditBtn.disabled = true;

    logConsole(`Starting Deep Audit: ${url}`, 'info');
    ws.send(JSON.stringify({
        action: 'deep_audit',
        url: url,
        max_depth: 2,
        max_pages: 15
    }));
}
window.startDeepAudit = startDeepAudit;

function handleNavigation(data) {
    if (pageTitle) pageTitle.textContent = data.title || data.url;
    if (data.screenshot && livePreview) {
        livePreview.src = `data:image/png;base64,${data.screenshot}`;
        livePreview.style.display = 'block';
        if (previewPlaceholder) previewPlaceholder.style.display = 'none';
    }
}

// --- Actions ---

function navigate() {
    if (!ws || !isConnected) return logConsole('Not connected', 'error');
    const url = urlInput.value;
    if (!url) return;

    logConsole(`Navigating to ${url}...`, 'info');
    ws.send(JSON.stringify({ action: 'navigate', url: url }));
}

function analyze() {
    if (!ws || !isConnected) return;
    const query = queryInput.value || "Describe this screen";
    logConsole('Requesting AI analysis...', 'info');
    ws.send(JSON.stringify({ action: 'analyze', query: query }));
}

function extractDom() {
    if (!ws || !isConnected) return;
    logConsole('Extracting DOM...', 'info');
    ws.send(JSON.stringify({ action: 'extract_dom' })); // Assuming backend supports this
}

function executeTask() {
    if (!ws || !isConnected) return;
    const task = taskInput.value;
    if (!task) return;
    logConsole(`Executing task: ${task}`, 'info');
    ws.send(JSON.stringify({ action: 'autonomous_task', goal: task }));
}

// --- Mode Switching ---

// Make switchMode global so onclick works
window.switchMode = function (mode) {
    if (mode === 'browser') {
        browserModeBtn?.classList.add('active');
        researchModeBtn?.classList.remove('active');
        if (browserPanelEl) {
            browserPanelEl.style.display = 'grid'; // Ensure Grid for layout
            browserPanelEl.style.opacity = '0';
            setTimeout(() => browserPanelEl.style.opacity = '1', 10); // Fade in
        }
        if (researchPanelEl) researchPanelEl.style.display = 'none';
        logConsole('Switched to Browser Mode', 'info');
    } else {
        browserModeBtn?.classList.remove('active');
        researchModeBtn?.classList.add('active');
        if (browserPanelEl) browserPanelEl.style.display = 'none';
        if (researchPanelEl) researchPanelEl.style.display = 'flex';
        logConsole('Switched to Deep Research Mode', 'info');
    }
};

// --- Initialization ---

// Event Listeners
if (navigateBtn) navigateBtn.addEventListener('click', navigate);
if (urlInput) urlInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') navigate(); });
if (analyzeBtn) analyzeBtn.addEventListener('click', analyze);
if (extractDomBtn) extractDomBtn.addEventListener('click', extractDom);
if (executeBtn) executeBtn.addEventListener('click', executeTask);

// Tabs
tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        tabButtons.forEach(b => b.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        const tabId = btn.dataset.tab;
        document.getElementById(`${tabId}Tab`)?.classList.add('active');
    });
});

// Start
connectWebSocket();
logConsole('Antigravity Client v2.0 Initialized', 'success');

// Mock fetchModels to prevent errors if referenced elsewhere (legacy compatibility)
window.fetchModels = function () { console.log("Models managed by config.py"); };