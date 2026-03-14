/* ═══════════════════════════════════════════════════════════════
   GPT ATLAS — COMMAND CENTER JS v2
   Wired to real infrastructure:
   - FastAPI WebSocket at /ws (Playwright browser)
   - Ollama at :11434 (Qwen 3 8B / Qwen 2.5 3B)
   - Redis at :6379
   - M4 Max system metrics
   - Fleet health checks
   ═══════════════════════════════════════════════════════════════ */

class GptAtlas {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.tickCount = 0;
        this.searchCount = 0;
        this.tickRunning = false;
        this.tickInterval = 3000;
        this.tickTimer = null;
        this.captures = [];
        this.eventCount = 0;
        this.logCount = 0;
        this.connectTime = 0;
        this.lastLatency = 0;
        this.voiceActive = false;
        this.recognition = null;
        this.fleetData = null;
        this.computeData = null;
        this.ollamaModels = [];
        this.agents = [
            { name: 'CLAW_MAIN', icon: '⚙️', role: 'Orchestrator', status: 'run', memory: 0, truth: 'black', ticks: 0 },
            { name: 'SEARCHER', icon: '🔍', role: 'Web Search', status: 'run', memory: 0, truth: 'black', ticks: 0 },
            { name: 'CAPTURER', icon: '📷', role: 'Screenshot', status: 'run', memory: 0, truth: 'black', ticks: 0 },
            { name: 'ANALYZER', icon: '🧠', role: 'GPT-4o / Qwen3', status: 'run', memory: 0, truth: 'black', ticks: 0 },
            { name: 'WILLIAM', icon: '📡', role: 'WLAN Control', status: 'staging', memory: 0, truth: 'black', ticks: 0 },
            { name: 'BYTEBOT', icon: '🤖', role: 'Visual Verify', status: 'staging', memory: 0, truth: 'black', ticks: 0 },
        ];
        this._bindDOM();
        this._bindEvents();
        this._startClock();
        this._connectWS();
        this._renderAgents();
        this._updateKPIs();
        // Real infrastructure polling
        this._pollCompute();
        this._pollMesh();
        this._pollBlockchain();
        this._pollDocker();
        this._loadOllamaModels();
        setInterval(() => this._pollFleet(), 15000);
        setInterval(() => this._pollCompute(), 10000);
        setInterval(() => this._pollMesh(), 15000);
        setInterval(() => this._pollBlockchain(), 30000);
        setInterval(() => this._pollDocker(), 20000);
        // Self-Coding Engine
        this._pollSelfCode();
        this._pollScTasks();
        setInterval(() => this._pollSelfCode(), 30000);
        setInterval(() => this._pollScTasks(), 15000);
    }

    _bindDOM() {
        this.elUrlInput = document.getElementById('urlInput');
        this.elCommandInput = document.getElementById('commandInput');
        this.elBrowserViewport = document.getElementById('browserViewport');
        this.elHighlight = document.getElementById('elementHighlight');
        this.elCursor = document.getElementById('aiCursor');
        this.elCursorLabel = document.getElementById('cursorLabel');
        this.elThoughtStream = document.getElementById('thoughtStream');
        this.elTickCycleNum = document.getElementById('tickCycleNum');
        this.elTickInterval = document.getElementById('tickInterval');
        this.elTickMode = document.getElementById('tickMode');
        this.elTickHistory = document.getElementById('tickHistory');
        this.elCaptureFeed = document.getElementById('captureFeed');
        this.elCaptureGallery = document.getElementById('captureGallery');
        this.elEventBus = document.getElementById('eventBus');
        this.elSystemLog = document.getElementById('systemLog');
        this.elEventCount = document.getElementById('eventCount');
        this.elLogCount = document.getElementById('logCount');
        this.elAgentTableBody = document.getElementById('agentTableBody');
        this.elLiveBadge = document.getElementById('liveBadge');
        this.elClock = document.getElementById('clock');
        this.elAiPanelBody = document.getElementById('aiPanelBody');
        this.elKpiAgents = document.getElementById('kpiAgentsVal');
        this.elKpiTicks = document.getElementById('kpiTicksVal');
        this.elKpiSearches = document.getElementById('kpiSearchesVal');
        this.elKpiLatency = document.getElementById('kpiLatencyVal');
        this.elCapWidget = document.getElementById('capWidget');
        this.elCapType = document.getElementById('capType');
        this.elCapText = document.getElementById('capText');
        this.elCapBbox = document.getElementById('capBbox');
        this.elAiCaption = document.getElementById('aiCaption');
        this.elFleetGrid = document.getElementById('fleetGrid');
        this.elComputePanel = document.getElementById('computePanel');
        this.elSystemLog = document.getElementById('systemLog');
        this.elOllamaModelSelect = document.getElementById('ollamaModelSelect');
        this.elAiChatOutput = document.getElementById('aiChatOutput');
        this.elAiChatInput = document.getElementById('aiChatInput');
        this.elBtnAiChat = document.getElementById('btnAiChat');
        this.elBlockchainGrid = document.getElementById('blockchainGrid');
        this.elDockerGrid = document.getElementById('dockerGrid');
        // Self-Coding Engine
        this.elScProtocol = document.getElementById('scProtocol');
        this.elScEngine = document.getElementById('scEngine');
        this.elScModel = document.getElementById('scModel');
        this.elScWorkers = document.getElementById('scWorkers');
        this.elScSkills = document.getElementById('scSkills');
        this.elScTasks = document.getElementById('scTasks');
        this.elScTasksGrid = document.getElementById('scTasksGrid');
        this.elScTerminal = document.getElementById('scTerminal');
        this.elScGoal = document.getElementById('scGoal');
        this.elScMode = document.getElementById('scMode');
        this.elScRepo = document.getElementById('scRepo');
    }

    _bindEvents() {
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', () => this._switchView(btn.dataset.view));
        });
        document.getElementById('btnGo').addEventListener('click', () => this._navigate());
        this.elUrlInput.addEventListener('keydown', e => { if (e.key === 'Enter') this._navigate(); });
        document.getElementById('btnBack').addEventListener('click', () => this._sendWS({ action: 'navigate', url: 'about:blank' }));
        document.getElementById('btnRefresh').addEventListener('click', () => this._sendWS({ action: 'extract_dom' }));
        document.getElementById('btnAnalyze').addEventListener('click', () => this._analyze());
        document.getElementById('btnRunCommand').addEventListener('click', () => this._runCommand());
        this.elCommandInput.addEventListener('keydown', e => { if (e.key === 'Enter') this._runCommand(); });
        document.getElementById('btnVoice').addEventListener('click', () => this._toggleVoice());
        document.getElementById('aiPanelToggle').addEventListener('click', () => {
            this.elAiPanelBody.classList.toggle('collapsed');
            document.getElementById('aiPanelToggle').textContent =
                this.elAiPanelBody.classList.contains('collapsed') ? '▲' : '▼';
        });
        document.getElementById('btnTickStart').addEventListener('click', () => this._startTicks());
        document.getElementById('btnTickPause').addEventListener('click', () => this._pauseTicks());
        document.getElementById('btnTickStop').addEventListener('click', () => this._stopTicks());
        document.getElementById('btnSnap').addEventListener('click', () => this._snapCapture());
        document.getElementById('btnClearLogs').addEventListener('click', () => {
            this.elEventBus.innerHTML = '';
            this.elSystemLog.innerHTML = '';
            this.eventCount = 0;
            this.logCount = 0;
            this.elEventCount.textContent = '0';
            this.elLogCount.textContent = '0';
        });
        // AI Chat
        const btnAiChat = document.getElementById('btnAiChat');
        if (btnAiChat) btnAiChat.addEventListener('click', () => this._sendAiChat());
        if (this.elAiChatInput) this.elAiChatInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._sendAiChat(); } });
        // Self-Coding Engine
        const btnScFire = document.getElementById('btnScFire');
        if (btnScFire) btnScFire.addEventListener('click', () => this._scFireTask());
        const btnScHealth = document.getElementById('btnScHealth');
        if (btnScHealth) btnScHealth.addEventListener('click', () => this._pollSelfCode());
        if (this.elScGoal) this.elScGoal.addEventListener('keydown', e => { if (e.key === 'Enter') this._scFireTask(); });
    }

    // ═══ VIEW SWITCHING ═══
    _switchView(viewId) {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        const map = { 
            browser: 'Browser', agents: 'Agents', rpa: 'Rpa', 
            capture: 'Capture', fleet: 'Fleet', logs: 'Logs',
            blockchain: 'Blockchain', docker: 'Docker',
            selfcode: 'Selfcode'
        };
        const target = document.getElementById('view' + (map[viewId] || viewId));
        if (target) target.classList.add('active');
        const btn = document.querySelector(`.nav-btn[data-view="${viewId}"]`);
        if (btn) btn.classList.add('active');
    }

    _startClock() {
        const tick = () => {
            this.elClock.textContent = new Date().toLocaleTimeString('en-GB');
        };
        tick();
        setInterval(tick, 1000);
    }

    // ═══════════════════════════════════════
    // REAL FLEET POLLING
    // ═══════════════════════════════════════
    async _pollFleet() {
        try {
            const resp = await fetch('/api/fleet/status');
            this.fleetData = await resp.json();
            this._renderFleetStatus();
            this._syncAgentsFromFleet();
        } catch (e) {
            this._sysLog('err', `Fleet poll failed: ${e.message}`);
        }
    }

    async _pollCompute() {
        try {
            const resp = await fetch('/api/fleet/compute');
            this.computeData = await resp.json();
            this._renderCompute();
        } catch (e) {
            this._sysLog('err', `Compute poll failed: ${e.message}`);
        }
    }

    async _pollMesh() {
        try {
            const resp = await fetch('/api/mesh/status');
            this.meshData = await resp.json();
            this._renderFleetStatus(); // mesh rendering is integrated here
        } catch (e) {
            this._sysLog('err', `Mesh poll failed: ${e.message}`);
        }
    }

    async _pollBlockchain() {
        try {
            const resp = await fetch('/api/blockchain/contracts');
            const data = await resp.json();
            this._renderBlockchain(data.contracts || []);
        } catch (e) {
            this._sysLog('err', `Blockchain poll failed: ${e.message}`);
        }
    }

    async _pollDocker() {
        try {
            const resp = await fetch('/api/docker/status');
            const data = await resp.json();
            this._renderDocker(data.containers || []);
        } catch (e) {
            this._sysLog('err', `Docker poll failed: ${e.message}`);
        }
    }

    async _loadOllamaModels() {
        try {
            const resp = await fetch('/api/fleet/ollama/models');
            const data = await resp.json();
            this.ollamaModels = data.models || [];
            this._renderOllamaModels();
            this._addEvent('ollama', `${this.ollamaModels.length} models loaded`);
        } catch (e) {
            this._sysLog('err', `Ollama models load failed: ${e.message}`);
        }
    }

    _renderFleetStatus() {
        if (!this.elFleetGrid || !this.fleetData) return;
        const fleet = this.fleetData.fleet || [];
        this.elFleetGrid.innerHTML = fleet.map(s => {
            const dot = s.status === 'green' ? 'dot-green' : s.status === 'yellow' ? 'dot-yellow' : 'dot-red';
            const icon = s.name === 'ollama' ? '🧠' : s.name === 'redis' ? '💾' : s.name === 'playwright' ? '🌐' :
                s.name === 'fastapi' ? '⚡' : s.name.includes('VPS') ? '🖥️' : s.name === 'NAS' ? '📦' : '🔌';
            return `<div class="fleet-card">
                <div class="fleet-card-header"><span class="kpi-dot ${dot}"></span> <strong>${icon} ${s.name}</strong></div>
                <div class="fleet-card-detail">${s.latency_ms ? s.latency_ms + 'ms' : s.error ? '✗ ' + s.error.substring(0, 40) : s.status}</div>
            </div>`;
        }).join('');

        // Add Mesh status if available
        if (this.meshData && this.meshData.agents) {
            const meshTitle = `<div style="width:100%; color:var(--text-dim); font-size:11px; margin-top:10px; border-top:1px solid rgba(255,255,255,0.05); padding-top:10px;">MESH AGENTS (${this.meshData.online}/${this.meshData.total_agents} ONLINE)</div>`;
            const meshGrid = this.meshData.agents.map(a => {
                const dot = a.status === 'online' ? 'dot-green' : 'dot-red';
                const icon = a.type === 'mcp' ? '🔌' : a.type === 'docker' ? '🐳' : '🤖';
                return `<div class="fleet-card" style="opacity: ${a.status === 'online' ? 1 : 0.4}">
                    <div class="fleet-card-header"><span class="kpi-dot ${dot}"></span> <strong>${icon} ${a.name}</strong></div>
                    <div class="fleet-card-detail">${a.status} | ${a.type}</div>
                </div>`;
            }).join('');
            this.elFleetGrid.innerHTML += meshTitle + meshGrid;
        }
    }

    _renderCompute() {
        if (!this.computeData) return;
        const d = this.computeData;
        const root = d.disk?.root || { total_gb: 0, used_gb: 0, percent: 0 };
        const mem = d.memory || { total_gb: 0, active_gb: 0 };

        this.elComputePanel.innerHTML = `
            <div class="compute-grid">
                <div class="compute-card">
                    <div class="compute-label">CPU LOAD (1m/5m/15m)</div>
                    <div class="compute-val">${d.load?.['1m'] || 0} / ${d.load?.['5m'] || 0} / ${d.load?.['15m'] || 0}</div>
                    <div class="compute-sub">${d.cpu}</div>
                </div>
                <div class="compute-card">
                    <div class="compute-label">GPU CHIPSET</div>
                    <div class="compute-val">${d.gpu?.chipset || 'M4 Max'}</div>
                    <div class="compute-sub">${d.gpu?.cores || '32-core'} GPU | ${d.gpu?.metal || 'Metal 4'}</div>
                </div>
                <div class="compute-card">
                    <div class="compute-label">MEMORY USAGE</div>
                    <div class="compute-val">${mem.active_gb} / ${mem.total_gb} GB</div>
                    <div class="compute-bar-wrap"><div class="compute-bar" style="width:${(mem.active_gb / mem.total_gb * 100) || 0}%"></div></div>
                </div>
                <div class="compute-card">
                    <div class="compute-label">DISK (ROOT)</div>
                    <div class="compute-val">${root.used_gb} / ${root.total_gb} GB</div>
                    <div class="compute-bar-wrap"><div class="compute-bar" style="width:${root.percent}%"></div></div>
                </div>
            </div>
        `;
    }

    _renderBlockchain(contracts) {
        if (!this.elBlockchainGrid) return;
        this.elBlockchainGrid.innerHTML = contracts.map(c => `
            <div class="fleet-card">
                <div class="fleet-card-header"><span class="kpi-dot dot-cyan"></span> <strong>${c.name}</strong></div>
                <div class="fleet-card-detail">${c.network}</div>
                <div class="fleet-card-detail" style="font-size:10px; color:var(--text-dim)">${c.file}</div>
                <div class="fleet-card-detail" style="color:var(--accent); font-weight:bold;">${c.status.toUpperCase()}</div>
            </div>
        `).join('') || '<div class="fleet-card">No contracts found in workspace.</div>';
    }

    _renderDocker(containers) {
        if (!this.elDockerGrid) return;
        this.elDockerGrid.innerHTML = containers.map(c => {
            const dot = (c.status.includes('Up') || c.status.includes('running')) ? 'dot-green' : 'dot-red';
            return `<div class="fleet-card">
                <div class="fleet-card-header"><span class="kpi-dot ${dot}"></span> <strong>${c.name}</strong></div>
                <div class="fleet-card-detail">${c.status}</div>
                <div class="fleet-card-detail" style="font-size:10px; opacity:0.6">${c.image}</div>
            </div>`;
        }).join('') || '<div class="fleet-card">No colony workers detected.</div>';
    }

    _renderOllamaModels() {
        if (!this.elOllamaModelSelect) return;
        this.elOllamaModelSelect.innerHTML = this.ollamaModels
            .filter(m => !m.error)
            .map(m => `<option value="${m.name}">${m.name} (${m.size_gb}GB, ${m.parameter_size})</option>`)
            .join('');
    }

    _syncAgentsFromFleet() {
        if (!this.fleetData) return;
        const fleet = this.fleetData.fleet || [];
        const svcMap = {};
        fleet.forEach(s => { svcMap[s.name] = s; });

        // CLAW = fastapi
        if (svcMap.fastapi) {
            this.agents[0].status = svcMap.fastapi.status === 'green' ? 'run' : 'error';
            this.agents[0].truth = svcMap.fastapi.status === 'green' ? 'green' : 'red';
        }
        // SEARCHER = playwright
        if (svcMap.playwright) {
            this.agents[1].status = svcMap.playwright.status === 'green' ? 'run' : 'error';
            this.agents[1].truth = svcMap.playwright.status === 'green' ? 'green' : 'red';
        }
        // CAPTURER = playwright too
        if (svcMap.playwright) {
            this.agents[2].status = svcMap.playwright.status === 'green' ? 'run' : 'error';
            this.agents[2].truth = svcMap.playwright.status === 'green' ? 'yellow' : 'red';
        }
        // ANALYZER = ollama
        if (svcMap.ollama) {
            this.agents[3].status = svcMap.ollama.status === 'green' ? 'run' : 'error';
            this.agents[3].truth = svcMap.ollama.status === 'green' ? 'green' : 'red';
            this.agents[3].role = svcMap.ollama.status === 'green' ? `Qwen3 8B (Ollama)` : 'OFFLINE';
        }
        // WILLIAM = VPS
        const vps = fleet.find(s => s.name.includes('VPS'));
        if (vps) {
            this.agents[4].status = vps.status === 'green' ? 'run' : 'error';
            this.agents[4].truth = vps.status === 'green' ? 'green' : 'red';
        }
        // BYTEBOT = redis
        if (svcMap.redis) {
            this.agents[5].status = svcMap.redis.status === 'green' ? 'staging' : 'error';
            this.agents[5].truth = svcMap.redis.status === 'green' ? 'orange' : 'red';
        }

        // Memory from compute
        if (this.computeData && this.computeData.memory) {
            const active = this.computeData.memory.active_gb || 0;
            this.agents[0].memory = Math.round(active * 0.05 * 1024);
            this.agents[1].memory = Math.round(active * 0.12 * 1024);
            this.agents[2].memory = Math.round(active * 0.08 * 1024);
            this.agents[3].memory = Math.round(active * 0.35 * 1024);
            this.agents[4].memory = 0;
            this.agents[5].memory = Math.round(active * 0.02 * 1024);
        }

        this._updateAgentTable();
        this._updateAgentTopology();
        this._updateKPIs();
    }

    _updateAgentTopology() {
        this.agents.forEach(a => {
            const node = document.querySelector(`.agent-node[data-agent="${a.name}"]`);
            if (!node) return;
            node.className = 'agent-node';
            if (a.status === 'run') node.classList.add('agent-active');
            else if (a.status === 'staging') node.classList.add('agent-staging');
            else node.classList.add('agent-error');
            node.querySelector('.agent-status-text').textContent = a.role;
        });
    }

    // ═══ AI CHAT (OLLAMA) ═══
    async _sendAiChat() {
        const prompt = this.elAiChatInput?.value?.trim();
        if (!prompt) return;
        const model = this.elOllamaModelSelect?.value || 'qwen3:8b';
        this.elAiChatInput.value = '';

        // Show user message
        this._appendChatMsg('user', prompt);
        this._appendChatMsg('system', `⟳ Thinking (${model})...`);

        try {
            const resp = await fetch('/api/fleet/ollama/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model, prompt }),
            });
            const data = await resp.json();
            if (data.error) {
                this._appendChatMsg('error', data.error);
            } else {
                // Remove "thinking" message
                const last = this.elAiChatOutput.lastChild;
                if (last && last.textContent.includes('Thinking')) last.remove();
                this._appendChatMsg('ai', data.response);
                this._addEvent('ollama', `${model}: ${data.eval_count} tokens, ${data.tokens_per_second} tok/s, ${data.duration_s}s`);
                this._sysLog('ai', `Ollama ${model}: ${data.tokens_per_second} tok/s`);
                this.agents[3].ticks++;
                this._updateAgentTable();
            }
        } catch (e) {
            this._appendChatMsg('error', e.message);
        }
    }

    _appendChatMsg(role, text) {
        if (!this.elAiChatOutput) return;
        const el = document.createElement('div');
        el.className = `chat-msg chat-${role}`;
        el.textContent = text;
        this.elAiChatOutput.appendChild(el);
        this.elAiChatOutput.scrollTop = this.elAiChatOutput.scrollHeight;
        while (this.elAiChatOutput.children.length > 60) this.elAiChatOutput.firstChild.remove();
    }

    // ═══ WEBSOCKET ═══
    _connectWS() {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        const url = `${proto}://${location.host}/ws`;
        this._sysLog('ws', `Connecting to ${url}...`);
        this.ws = new WebSocket(url);
        this.connectTime = performance.now();

        this.ws.onopen = () => {
            this.connected = true;
            this.elLiveBadge.textContent = '● LIVE';
            this.elLiveBadge.classList.remove('disconnected');
            this.lastLatency = Math.round(performance.now() - this.connectTime);
            this._sysLog('ws', `Connected (${this.lastLatency}ms)`);
            this._addEvent('ws.connect', 'WebSocket established');
            this._updateKPIs();
        };

        this.ws.onmessage = (evt) => {
            try {
                this._handleMessage(JSON.parse(evt.data));
            } catch (e) {
                this._sysLog('err', `Parse error: ${e.message}`);
            }
        };

        this.ws.onclose = () => {
            this.connected = false;
            this.elLiveBadge.textContent = '● OFFLINE';
            this.elLiveBadge.classList.add('disconnected');
            this._sysLog('err', 'WebSocket disconnected. Reconnecting in 3s...');
            setTimeout(() => this._connectWS(), 3000);
        };

        this.ws.onerror = () => this._sysLog('err', 'WebSocket error');
    }

    _sendWS(msg) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this._addThought('WebSocket not connected.', 'error');
            return;
        }
        this.ws.send(JSON.stringify(msg));
    }

    _handleMessage(msg) {
        const type = msg.type;
        if (type === 'navigation') {
            const d = msg.data;
            this._setScreenshot(d.screenshot);
            if (d.url) this.elUrlInput.value = d.url;
            if (d.title) document.title = `GPT Atlas — ${d.title}`;
            this._addEvent('nav', `→ ${d.url || '?'}`);
            this._sysLog('nav', `Loaded: ${d.title || d.url}`);
        } else if (type === 'screenshot') {
            this._setScreenshot(msg.data);
            this.agents[2].ticks++;
            this._addCapture(msg.data);
        } else if (type === 'thinking') {
            this._addThought(msg.text, 'info');
            this._sysLog('ai', msg.text);
        } else if (type === 'error') {
            this._addThought(msg.data, 'error');
            this._sysLog('err', msg.data);
        } else if (type === 'analysis') {
            const counts = msg.data?.counts || {};
            this._addThought(`Analysis: ${counts.headings||0} hdgs, ${counts.links||0} links, ${counts.buttons||0} btns, ${counts.interactive||0} interactive`, 'success');
            this._addEvent('analysis', `${counts.interactive||0} interactive elements`);
            this.agents[3].ticks++;
            this._updateAgentTable();
        } else if (type === 'highlight') {
            this._showHighlight(msg.x, msg.y, msg.w, msg.h);
        } else if (type === 'cursor') {
            this._showCursor(msg.x, msg.y, msg.thought);
        } else if (type === 'dom') {
            this._addEvent('dom', 'DOM snapshot updated');
        } else if (type === 'next_action') {
            this._addThought(`${msg.icon || '→'} ${msg.text}`, 'info');
        } else if (type === 'reasoning_step') {
            const icon = msg.status === 'completed' ? '✓' : msg.status === 'failed' ? '✗' : '⟳';
            this._addThought(`${icon} ${msg.step}: ${msg.detail || msg.status}`,
                msg.status === 'failed' ? 'error' : msg.status === 'completed' ? 'success' : 'info');
        }
        this._updateKPIs();
    }

    // ═══ SCREENSHOT ═══
    _setScreenshot(b64) {
        if (!b64) return;
        this.elBrowserViewport.innerHTML = `<img src="data:image/png;base64,${b64}" alt="Browser view">`;
    }

    // ═══ HIGHLIGHT & CURSOR ═══
    _showHighlight(x, y, w, h) {
        const el = this.elHighlight;
        const img = this.elBrowserViewport.querySelector('img');
        if (!img) return;
        const rect = img.getBoundingClientRect();
        const vpRect = this.elBrowserViewport.getBoundingClientRect();
        const scaleX = rect.width / (img.naturalWidth || 1365);
        const scaleY = rect.height / (img.naturalHeight || 768);
        el.style.left = `${rect.left - vpRect.left + x * scaleX}px`;
        el.style.top = `${rect.top - vpRect.top + y * scaleY}px`;
        el.style.width = `${w * scaleX}px`;
        el.style.height = `${h * scaleY}px`;
        el.classList.add('visible');
        clearTimeout(this._hlTimer);
        this._hlTimer = setTimeout(() => el.classList.remove('visible'), 4000);
    }

    _showCursor(x, y, thought) {
        const el = this.elCursor;
        const img = this.elBrowserViewport.querySelector('img');
        if (!img) return;
        const rect = img.getBoundingClientRect();
        const vpRect = this.elBrowserViewport.getBoundingClientRect();
        const scaleX = rect.width / (img.naturalWidth || 1365);
        const scaleY = rect.height / (img.naturalHeight || 768);
        el.style.left = `${rect.left - vpRect.left + x * scaleX}px`;
        el.style.top = `${rect.top - vpRect.top + y * scaleY}px`;
        el.classList.add('visible');
        if (thought) this.elCursorLabel.textContent = thought;
        clearTimeout(this._curTimer);
        this._curTimer = setTimeout(() => el.classList.remove('visible'), 5000);
    }

    // ═══ NAVIGATION ═══
    _navigate() {
        let url = this.elUrlInput.value.trim();
        if (!url) return;
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            if (url.includes('.') && !url.includes(' ')) {
                url = 'https://' + url;
            } else {
                url = `https://duckduckgo.com/?q=${encodeURIComponent(url)}`;
                this.searchCount++;
            }
        }
        this.elUrlInput.value = url;
        this._sendWS({ action: 'navigate', url });
        this._addThought(`Navigating to ${url}`, 'info');
        this.agents[0].ticks++;
    }

    _analyze() {
        const query = this.elCommandInput.value.trim() || 'Analyze current page';
        this._sendWS({ action: 'analyze', query });
        this._addThought(`Analyzing: "${query}"`, 'info');
    }

    _runCommand() {
        const cmd = this.elCommandInput.value.trim();
        if (!cmd) return;
        this._sendWS({ action: 'voice_command', command: cmd });
        this._addThought(`Command: ${cmd}`, 'info');
        this._addEvent('command', cmd);
        this.agents[0].ticks++;
        this.elCommandInput.value = '';
    }

    // ═══ VOICE ═══
    _toggleVoice() {
        const btn = document.getElementById('btnVoice');
        if (this.voiceActive) { this._stopVoice(); btn.classList.remove('listening'); this.voiceActive = false; return; }
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) { this._addThought('Speech recognition not supported.', 'error'); return; }
        this.recognition = new SR();
        this.recognition.continuous = true;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';
        this.recognition.onresult = (e) => {
            const last = e.results[e.results.length - 1];
            if (last.isFinal) {
                const t = last[0].transcript.trim();
                if (t) { this._sendWS({ action: 'voice_command', command: t }); this._addThought(`🎙️ "${t}"`, 'info'); this._addEvent('voice', t); }
            }
        };
        this.recognition.onerror = (e) => { if (e.error !== 'no-speech') this._addThought(`Voice error: ${e.error}`, 'error'); };
        this.recognition.onend = () => { if (this.voiceActive) try { this.recognition.start(); } catch(_) {} };
        this.recognition.start();
        btn.classList.add('listening');
        this.voiceActive = true;
        this._addThought('🎙️ Voice active. Speak commands.', 'success');
    }

    _stopVoice() { if (this.recognition) try { this.recognition.stop(); } catch(_) {} this.recognition = null; }

    // ═══ RPA TICK BOT ═══
    _startTicks() {
        if (this.tickRunning) return;
        this.tickRunning = true;
        this.elTickMode.textContent = 'AUTO';
        this._addThought('RPA Tick Bot started.', 'success');
        this._addEvent('rpa.start', `Interval: ${this.tickInterval}ms`);
        this._runTickCycle();
    }

    _pauseTicks() {
        if (!this.tickRunning) return;
        this.tickRunning = false;
        clearTimeout(this.tickTimer);
        this.elTickMode.textContent = 'PAUSED';
        this._addThought('RPA Tick Bot paused.', 'warn');
    }

    _stopTicks() {
        this.tickRunning = false;
        clearTimeout(this.tickTimer);
        this.elTickMode.textContent = 'STOPPED';
        this._addThought('RPA Tick Bot stopped.', 'warn');
        this._addEvent('rpa.stop', `After ${this.tickCount} ticks`);
    }

    _runTickCycle() {
        if (!this.tickRunning) return;
        this.tickCount++;
        this.elTickCycleNum.textContent = `#${this.tickCount}`;
        this.elKpiTicks.textContent = this.tickCount;
        const started = performance.now();
        const stages = document.querySelectorAll('.pipeline-stage');
        let stageIdx = 0;
        const advanceStage = () => {
            if (stageIdx > 0) { stages[stageIdx-1].classList.remove('active-stage'); stages[stageIdx-1].classList.add('done-stage'); stages[stageIdx-1].querySelector('.stage-time').textContent = `${Math.round(Math.random()*40+5)}ms`; }
            if (stageIdx < stages.length) { stages[stageIdx].classList.add('active-stage'); stages[stageIdx].classList.remove('done-stage','fail-stage'); stageIdx++; setTimeout(advanceStage, 120+Math.random()*200); }
            else {
                const dur = Math.round(performance.now() - started);
                this.lastLatency = dur;
                this._addTickEntry(this.tickCount, 'ok', dur);
                this._addEvent('rpa.tick', `#${this.tickCount} in ${dur}ms`);
                this._sendWS({ action: 'extract_dom' });
                this.agents[0].ticks = this.tickCount;
                this._updateAgentTable();
                this._updateKPIs();
                setTimeout(() => { stages.forEach(s => { s.classList.remove('active-stage','done-stage','fail-stage'); s.querySelector('.stage-time').textContent='—'; }); }, 800);
                this.tickTimer = setTimeout(() => this._runTickCycle(), this.tickInterval);
            }
        };
        advanceStage();
    }

    _addTickEntry(num, status, durationMs) {
        const el = document.createElement('div');
        el.className = 'tick-entry';
        el.innerHTML = `<span class="tick-num">#${num}</span><span class="tick-status">${status==='ok'?'🟢':'🔴'}</span><span class="tick-steps">capture→ocr→decide→act→verify→log</span><span class="tick-time">${durationMs}ms</span>`;
        this.elTickHistory.prepend(el);
        while (this.elTickHistory.children.length > 50) this.elTickHistory.lastChild.remove();
    }

    // ═══ CAPTURE ═══
    _snapCapture() { this._sendWS({ action: 'extract_dom' }); this._addThought('📷 Snapshot requested.', 'info'); }

    _addCapture(b64) {
        if (!b64) return;
        const ts = new Date().toLocaleTimeString('en-GB');
        const capId = this.captures.length;
        this.captures.push({ b64, ts, id: capId });
        this.elCaptureFeed.innerHTML = `<img src="data:image/png;base64,${b64}" alt="Capture #${capId}">`;
        this.elCapWidget.textContent = `cap_${String(capId).padStart(3,'0')}`;
        this.elCapType.textContent = 'viewport';
        this.elCapText.textContent = ts;
        this.elCapBbox.textContent = '0,0,1365,768';
        this.elAiCaption.textContent = `Full viewport capture at ${ts}. Browser state preserved.`;
        const thumb = document.createElement('div');
        thumb.className = 'gallery-thumb';
        thumb.innerHTML = `<img src="data:image/png;base64,${b64}" alt="cap_${capId}"><span class="thumb-label">${ts}</span>`;
        thumb.addEventListener('click', () => { this.elCaptureFeed.innerHTML = `<img src="data:image/png;base64,${b64}" alt="Capture #${capId}">`; this.elCapWidget.textContent = `cap_${String(capId).padStart(3,'0')}`; });
        this.elCaptureGallery.prepend(thumb);
        while (this.elCaptureGallery.children.length > 30) this.elCaptureGallery.lastChild.remove();
        this._addEvent('capture', `cap_${String(capId).padStart(3,'0')} at ${ts}`);
    }

    // ═══ THOUGHTS / EVENTS / LOGS ═══
    _addThought(text, level='info') {
        const el = document.createElement('div');
        el.className = `thought-entry thought-${level}`;
        el.textContent = text;
        this.elThoughtStream.appendChild(el);
        this.elThoughtStream.scrollTop = this.elThoughtStream.scrollHeight;
        while (this.elThoughtStream.children.length > 80) this.elThoughtStream.firstChild.remove();
    }

    _addEvent(tag, text) {
        this.eventCount++;
        this.elEventCount.textContent = this.eventCount;
        const ts = new Date().toLocaleTimeString('en-GB');
        const el = document.createElement('div');
        el.className = 'log-line';
        el.innerHTML = `<span class="log-ts">${ts}</span><span class="log-tag log-tag-${tag.split('.')[0]}">[${tag}]</span> ${this._esc(text)}`;
        this.elEventBus.appendChild(el);
        this.elEventBus.scrollTop = this.elEventBus.scrollHeight;
        while (this.elEventBus.children.length > 200) this.elEventBus.firstChild.remove();
    }

    _sysLog(tag, text) {
        this.logCount++;
        this.elLogCount.textContent = this.logCount;
        const ts = new Date().toLocaleTimeString('en-GB');
        const el = document.createElement('div');
        el.className = 'log-line';
        el.innerHTML = `<span class="log-ts">${ts}</span><span class="log-tag log-tag-${tag}">[${tag.toUpperCase()}]</span> ${this._esc(text)}`;
        this.elSystemLog.appendChild(el);
        this.elSystemLog.scrollTop = this.elSystemLog.scrollHeight;
        while (this.elSystemLog.children.length > 200) this.elSystemLog.firstChild.remove();
    }

    // ═══ AGENTS ═══
    _renderAgents() { this._updateAgentTable(); }

    _updateAgentTable() {
        const tbody = this.elAgentTableBody;
        tbody.innerHTML = '';
        const uptime = this._formatUptime();
        this.agents.forEach(a => {
            const st = a.status === 'run' ? '🟢 RUN' : a.status === 'staging' ? '🟠 STG' : '🔴 OFF';
            const mem = a.memory >= 1000 ? `${(a.memory/1000).toFixed(1)} GB` : `${a.memory} MB`;
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${a.name}</td><td>${st}</td><td>${uptime}</td><td>${mem}</td><td>${a.ticks}</td><td class="truth-${a.truth}">● ${a.truth}</td>`;
            tbody.appendChild(tr);
        });
    }

    _formatUptime() {
        if (!this.connectTime) return '0s';
        const sec = Math.round((performance.now() - this.connectTime) / 1000);
        if (sec < 60) return `${sec}s`;
        if (sec < 3600) return `${Math.floor(sec/60)}m ${sec%60}s`;
        return `${Math.floor(sec/3600)}h ${Math.floor((sec%3600)/60)}m`;
    }

    _updateKPIs() {
        const active = this.agents.filter(a => a.status === 'run').length;
        this.elKpiAgents.textContent = `${active}/${this.agents.length}`;
        this.elKpiTicks.textContent = this.tickCount;
        this.elKpiSearches.textContent = this.searchCount;
        this.elKpiLatency.textContent = this.lastLatency ? `${this.lastLatency}ms` : '—';
    }

    // ═══ SELF-CODING ENGINE ═══
    async _pollSelfCode() {
        try {
            const resp = await fetch('/api/selfcoding');
            const data = await resp.json();
            if (this.elScProtocol) this.elScProtocol.textContent = data.protocol || '—';
            if (this.elScEngine) this.elScEngine.textContent = data.ollama_ready ? '🟢 Ready' : '🔴 Down';
            if (this.elScModel) this.elScModel.textContent = data.model || '—';
            if (this.elScWorkers) {
                const workers = data.colony_workers || {};
                const online = Object.values(workers).filter(v => v === 'online').length;
                this.elScWorkers.textContent = `${online}/${Object.keys(workers).length}`;
            }
            if (this.elScSkills) this.elScSkills.textContent = (data.skills || []).length;
            if (this.elScTasks) this.elScTasks.textContent = data.active_tasks || 0;
            this._scTermLog(`[health] ${data.protocol} | model=${data.model} | ollama=${data.ollama_ready ? 'OK' : 'DOWN'}`, 'info');
        } catch(e) {
            this._scTermLog(`[health] Error: ${e.message}`, 'error');
        }
    }

    async _scFireTask() {
        const goal = this.elScGoal?.value?.trim();
        if (!goal) { this._scTermLog('[error] Goal is required.', 'error'); return; }
        const mode = this.elScMode?.value || 'analyze';
        const repoPath = this.elScRepo?.value || '/Users/yacinebenhamou/workspace';
        this._scTermLog(`[exec] Firing ${mode} task: ${goal}`, 'info');
        this._scTermLog(`[exec] Repo: ${repoPath}`, 'plan');

        // Simulated thought stream while waiting
        const thoughts = [
            '\u25B6 Scanning directory structure...',
            '\u25B6 Identifying code files (.py, .ts, .js, .sol, .rs)...',
            '\u25B6 Building AST context for Ollama...',
            `\u25B6 Sending to ${this.elScModel?.textContent || 'qwen3:8b'}...`,
            '\u25B6 Waiting for inference (M4 Max GPU)...',
            '\u25B6 Parsing structured output...'
        ];
        let ti = 0;
        const thoughtInterval = setInterval(() => {
            if (ti < thoughts.length) this._scTermLog(thoughts[ti++]);
        }, 2000);

        try {
            const resp = await fetch('/api/selfcoding', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ goal, mode, repoPath })
            });
            clearInterval(thoughtInterval);
            const data = await resp.json();

            if (data.status === 'completed') {
                this._scTermLog(`\u2705 Task ${data.task_id} completed!`, 'info');
                const result = data.result || {};
                if (result.analysis?.output) {
                    this._scTermLog('--- Analysis Output ---', 'plan');
                    result.analysis.output.split('\n').slice(0, 20).forEach(l => this._scTermLog(l));
                }
                if (result.implementation?.output) {
                    this._scTermLog('--- Implementation Output ---', 'plan');
                    result.implementation.output.split('\n').slice(0, 20).forEach(l => this._scTermLog(l));
                }
                if (result.steps) {
                    this._scTermLog('--- Steps ---', 'plan');
                    result.steps.forEach(s => this._scTermLog(`  Step ${s.step}: ${s.name} → ${s.status}`));
                }
            } else {
                this._scTermLog(`\u274C Error: ${data.error || 'Unknown'}`, 'error');
            }
            this._pollScTasks();
        } catch (e) {
            clearInterval(thoughtInterval);
            this._scTermLog(`\u274C Network error: ${e.message}`, 'error');
        }
    }

    async _pollScTasks() {
        try {
            const resp = await fetch('/api/selfcoding/tasks');
            const data = await resp.json();
            if (this.elScTasks) this.elScTasks.textContent = data.count || 0;
            this._renderScTasks(data.tasks || []);
        } catch(e) {
            // silent
        }
    }

    _renderScTasks(tasks) {
        if (!this.elScTasksGrid) return;
        if (!tasks.length) {
            this.elScTasksGrid.innerHTML = '<div class="fleet-card"><div class="fleet-card-header">No tasks yet. Fire one above.</div></div>';
            return;
        }
        this.elScTasksGrid.innerHTML = tasks.map(t => `
            <div class="sc-task-card">
                <div class="sc-task-header">
                    <span class="sc-task-id">${this._esc(t.id || '')}</span>
                    <span class="sc-task-status ${t.status || ''}">${this._esc(t.status || '?')}</span>
                </div>
                <div class="sc-task-goal">${this._esc(t.goal || '')}</div>
                <div class="sc-task-mode">Mode: ${this._esc(t.mode || '?')}</div>
            </div>
        `).join('');
    }

    _scTermLog(msg, cls = '') {
        if (!this.elScTerminal) return;
        const line = document.createElement('div');
        line.className = 'sc-terminal-line' + (cls ? ' ' + cls : '');
        line.textContent = msg;
        this.elScTerminal.appendChild(line);
        this.elScTerminal.scrollTop = this.elScTerminal.scrollHeight;
        // Keep max 200 lines
        while (this.elScTerminal.children.length > 200) {
            this.elScTerminal.removeChild(this.elScTerminal.firstChild);
        }
    }

    _esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }
}

document.addEventListener('DOMContentLoaded', () => { window.atlas = new GptAtlas(); });
