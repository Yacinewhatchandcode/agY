class MinimalAgentController {
    constructor() {
        this.ws = null;
        this.cursor = document.getElementById('agentCursor');
        this.thinkingBubble = document.getElementById('thinkingBubble');
        this.elementHighlight = document.getElementById('elementHighlight');
        this.currentThought = document.getElementById('currentThought');
        this.reasoningOverlay = document.getElementById('reasoningOverlay');
        this.nextAction = document.getElementById('nextAction');
        this.nextActionText = document.getElementById('nextActionText');
        this.nextActionIcon = this.nextAction?.querySelector('.action-icon') || null;
        this.urlInput = document.getElementById('urlInput');
        this.navigateBtn = document.getElementById('navigateBtn');
        this.commandInput = document.getElementById('commandInput');
        this.runCommandBtn = document.getElementById('runCommandBtn');
        this.analyzeBtn = document.getElementById('analyzeBtn');
        this.browserContent = document.getElementById('browserContent');
        this.thoughtLog = document.getElementById('thoughtLog');
        this.voiceOrb = document.getElementById('voiceOrb');
        this.voiceStatus = document.getElementById('voiceStatus');
        this.voiceTranscript = document.getElementById('voiceTranscript');
        this.reasoningSteps = new Map();
        this.remoteViewport = { width: 1365, height: 768 };
        this.voiceEnabled = false;
        this.voiceSupported = false;
        this.pendingVoiceResponse = false;
        this.isListening = false;
        this.isSpeaking = false;
        this.lastInterimTranscript = '';
        this.recognition = null;
        this.voiceLang = (navigator.language || 'en-US').toLowerCase().startsWith('fr') ? 'fr-FR' : 'en-US';
        this.voicePermissionGranted = false;
        this.lastThoughtText = '';
        this.lastThoughtAt = 0;

        this.init();
    }

    init() {
        this.installBrowserNoiseGuards();
        this.cacheReasoningSteps();
        this.resetReasoning();
        this.setupVoiceRecognition();
        this.connectWebSocket();
        this.setupControls();
    }

    installBrowserNoiseGuards() {
        const noisyAsyncMessage =
            'A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received';

        window.addEventListener('unhandledrejection', (event) => {
            const reason = event?.reason;
            const message = typeof reason === 'string'
                ? reason
                : (reason && typeof reason.message === 'string' ? reason.message : '');
            if (message.includes(noisyAsyncMessage)) {
                event.preventDefault();
            }
        });

        window.addEventListener('error', (event) => {
            const message = event?.message || '';
            if (String(message).includes(noisyAsyncMessage)) {
                event.preventDefault();
            }
        });
    }

    cacheReasoningSteps() {
        const items = document.querySelectorAll('.reasoning-content .step[data-step]');
        items.forEach((item) => {
            const key = item.getAttribute('data-step');
            if (key) this.reasoningSteps.set(key, item);
        });
    }

    setupVoiceRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const secure = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        this.voiceSupported = Boolean(SpeechRecognition && window.speechSynthesis && secure);

        if (!this.voiceSupported) {
            if (!secure) {
                this.setVoiceStatus('Voice: unavailable (requires localhost/HTTPS)');
                this.setVoiceTranscript('Open this app on localhost or HTTPS to enable speech recognition.');
            } else {
                this.setVoiceStatus('Voice: unavailable in this browser');
            }
            if (this.voiceOrb) this.voiceOrb.disabled = true;
            return;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.lang = this.voiceLang;
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.maxAlternatives = 1;

        this.recognition.onstart = () => {
            this.isListening = true;
            this.setOrbState('listening');
            this.setVoiceStatus('Voice: listening...');
            this.setVoiceTranscript('Listening...');
        };

        this.recognition.onresult = (event) => {
            let finalText = '';
            let interimText = '';
            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                const text = event.results[i][0].transcript.trim();
                if (event.results[i].isFinal) {
                    finalText += `${text} `;
                } else {
                    interimText += `${text} `;
                }
            }
            if (interimText.trim()) {
                this.lastInterimTranscript = interimText.trim();
                this.setVoiceTranscript(`Listening: ${this.lastInterimTranscript}`);
            }
            if (finalText.trim()) {
                const transcript = finalText.trim();
                this.lastInterimTranscript = '';
                this.setVoiceTranscript(`You said: "${transcript}"`);
                this.addThought(`Voice heard: "${transcript}"`, 'reasoning');
                this.handleVoiceCommand(transcript);
            }
        };

        this.recognition.onerror = (event) => {
            this.isListening = false;
            if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                this.voiceEnabled = false;
                this.setOrbState('idle');
                this.setVoiceStatus('Voice: microphone permission denied');
                this.addThought('Voice permission denied by browser.', 'error');
                return;
            }
            if (event.error === 'audio-capture') {
                this.setOrbState('idle');
                this.setVoiceStatus('Voice error: no microphone detected');
                this.addThought('No microphone detected by browser.', 'error');
                return;
            }
            if (event.error === 'no-speech') {
                this.setVoiceStatus('Voice: no speech detected, listening again...');
                if (this.voiceEnabled) {
                    setTimeout(() => this.startListening(), 450);
                }
                return;
            }
            this.setOrbState('idle');
            this.setVoiceStatus(`Voice error: ${event.error}`);
        };

        this.recognition.onend = () => {
            this.isListening = false;
            if (this.voiceEnabled && !this.isSpeaking) {
                setTimeout(() => this.startListening(), 350);
            } else if (!this.isSpeaking) {
                this.setOrbState('idle');
                this.setVoiceStatus('Voice: idle');
            }
        };
    }

    async ensureMicrophonePermission() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.voicePermissionGranted = true;
            return true;
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach((track) => track.stop());
            this.voicePermissionGranted = true;
            this.addThought('Microphone permission granted.', 'reasoning');
            return true;
        } catch (err) {
            this.voicePermissionGranted = false;
            const msg = err && err.name ? err.name : 'mic access failed';
            this.setVoiceStatus(`Voice: mic access denied (${msg})`);
            this.setVoiceTranscript('Allow microphone access for this site, then click the orb again.');
            this.addThought(`Mic access denied: ${msg}`, 'error');
            return false;
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            const dot = document.querySelector('.status-dot');
            if (dot) dot.style.background = '#ef4444';
            this.clearThoughtLog();
            this.updateThought('Connected to Agent. Ready.');
            this.addThought('WebSocket connected.', 'reasoning');
            this.showNextAction('Connected. You can navigate or analyze now.', '🟢');
        };

        this.ws.onclose = () => {
            const dot = document.querySelector('.status-dot');
            if (dot) dot.style.background = '#737373';
            this.updateThought('Disconnected. Reconnecting...');
            this.addThought('Connection dropped, reconnecting...', 'error');
            this.setAnalyzeBusy(false);
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.ws.onerror = () => {
            this.updateThought('Connection Error');
            this.addThought('Socket error.', 'error');
            this.setAnalyzeBusy(false);
        };

        this.ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                this.handleMessage(msg);
            } catch (_) {
                this.updateThought('Bad message from backend.');
            }
        };
    }

    handleMessage(msg) {
        switch (msg.type) {
            case 'navigation':
                this.updateThought('Navigation: ' + (msg.data.title || 'Loaded'));
                if (msg.data.url) this.urlInput.value = msg.data.url;
                if (msg.data.viewport) this.remoteViewport = msg.data.viewport;
                if (msg.data.screenshot) this.updateBrowser(msg.data.screenshot);
                this.showNextAction('Next: click Analyze for semantic extraction.', '🧠');
                this.addThought(`Loaded page: ${msg.data.url || 'unknown'}`);
                this.setAnalyzeBusy(false);
                this.resetReasoning();
                this.setOrbState(this.voiceEnabled ? 'listening' : 'idle');
                break;
            case 'screenshot':
                this.updateBrowser(msg.data);
                break;
            case 'dom':
                this.handleDomPayload(msg.data);
                break;
            case 'analysis':
                this.handleAnalysisPayload(msg.data);
                break;
            case 'reasoning_reset':
                this.resetReasoning();
                break;
            case 'reasoning_step':
                this.setReasoningState(msg.step, msg.status);
                if (msg.detail && (msg.status === 'active' || msg.status === 'failed')) {
                    this.updateThought(msg.detail);
                    this.addThought(msg.detail, 'reasoning');
                }
                break;
            case 'next_action':
                this.showNextAction(msg.text, msg.icon || '🖱️');
                if (this.pendingVoiceResponse && this.voiceEnabled) {
                    this.speak(msg.text);
                    this.pendingVoiceResponse = false;
                }
                break;
            case 'error':
                this.updateThought('Error: ' + msg.data);
                this.showNextAction('Fix the error and retry.', '⚠️');
                this.addThought(`Error: ${msg.data}`, 'error');
                if (this.pendingVoiceResponse && this.voiceEnabled) {
                    this.speak(`Error. ${msg.data}`);
                    this.pendingVoiceResponse = false;
                }
                this.setAnalyzeBusy(false);
                break;
            case 'cursor':
                this.moveCursor(msg.x, msg.y, msg.thought);
                if (msg.thought) this.updateThought(msg.thought);
                break;
            case 'highlight':
                this.highlightElement(msg.x, msg.y, msg.w, msg.h);
                break;
            case 'thinking':
                this.updateThought(msg.text);
                this.addThought(msg.text);
                break;
            default:
                break;
        }
    }

    handleDomPayload(data) {
        if (!data || typeof data !== 'object') return;
        const summary = data.summary || 'DOM snapshot refreshed.';
        this.updateThought(summary);
        const counts = data.counts || {};
        this.showNextAction(
            `Snapshot: ${counts.interactive || 0} interactive, ${counts.links || 0} links.`,
            '🔎'
        );
        this.setAnalyzeBusy(false);
    }

    handleAnalysisPayload(data) {
        if (typeof data === 'string') {
            this.updateThought(data);
            this.addThought(data);
            if (this.pendingVoiceResponse && this.voiceEnabled) this.speak(data);
            this.pendingVoiceResponse = false;
            this.setAnalyzeBusy(false);
            return;
        }
        if (!data || typeof data !== 'object') {
            this.updateThought('Analysis finished, but payload is empty.');
            this.addThought('Analysis payload empty.', 'error');
            this.pendingVoiceResponse = false;
            this.setAnalyzeBusy(false);
            return;
        }

        const summary = data.summary || 'Analysis complete.';
        this.updateThought(summary);

        if (data.queryMatch?.text) {
            const text = data.queryMatch.text;
            this.showNextAction(`Matched sentence: "${text}"`, '🎯');
            this.addThought(`Query match: ${text}`, 'reasoning');
        } else {
            const target = data.primaryInteractive;
            if (target && target.label) {
                this.showNextAction(`Next: interact with "${target.label}".`, '🖱️');
            } else {
                this.showNextAction('Analysis complete. Choose an element to inspect.', '🖱️');
            }
        }

        if (this.pendingVoiceResponse && this.voiceEnabled) {
            this.speak(summary);
        }
        this.pendingVoiceResponse = false;
        this.setAnalyzeBusy(false);
        this.setOrbState(this.voiceEnabled ? 'listening' : 'idle');
    }

    updateBrowser(screenshot) {
        if (!screenshot || !this.browserContent) return;
        this.browserContent.innerHTML = '';
        const img = document.createElement('img');
        img.src = 'data:image/png;base64,' + screenshot;
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'contain';
        img.style.display = 'block';
        img.id = 'activeScreenshot';
        this.browserContent.appendChild(img);
    }

    getRenderFrame() {
        const remoteW = this.remoteViewport.width || 1365;
        const remoteH = this.remoteViewport.height || 768;
        const contW = this.browserContent.clientWidth || remoteW;
        const contH = this.browserContent.clientHeight || remoteH;
        const scale = Math.min(contW / remoteW, contH / remoteH);
        const drawW = remoteW * scale;
        const drawH = remoteH * scale;
        const offsetX = (contW - drawW) / 2;
        const offsetY = (contH - drawH) / 2;
        return { scale, offsetX, offsetY };
    }

    mapPoint(x, y) {
        const frame = this.getRenderFrame();
        return {
            x: frame.offsetX + x * frame.scale,
            y: frame.offsetY + y * frame.scale,
        };
    }

    mapRect(x, y, w, h) {
        const frame = this.getRenderFrame();
        return {
            x: frame.offsetX + x * frame.scale,
            y: frame.offsetY + y * frame.scale,
            w: w * frame.scale,
            h: h * frame.scale,
        };
    }

    moveCursor(x, y, thought = null) {
        if (!this.cursor) return;
        const mapped = this.mapPoint(x, y);
        this.cursor.classList.add('active');
        this.cursor.style.left = `${mapped.x}px`;
        this.cursor.style.top = `${mapped.y}px`;

        if (thought) this.showThinkingBubble(mapped.x, mapped.y, thought);
    }

    showThinkingBubble(x, y, text) {
        if (!this.thinkingBubble) return;
        const textEl = this.thinkingBubble.querySelector('.bubble-text');
        if (textEl) textEl.textContent = text;

        this.thinkingBubble.classList.add('active');
        this.thinkingBubble.style.left = `${Math.min(x + 40, window.innerWidth - 320)}px`;
        this.thinkingBubble.style.top = `${Math.max(y - 70, 70)}px`;

        setTimeout(() => {
            if (this.thinkingBubble) this.thinkingBubble.classList.remove('active');
        }, 4200);
    }

    highlightElement(x, y, w, h) {
        if (!this.elementHighlight) return;
        const mapped = this.mapRect(x, y, w, h);
        this.elementHighlight.classList.add('active');
        this.elementHighlight.style.left = `${mapped.x}px`;
        this.elementHighlight.style.top = `${mapped.y}px`;
        this.elementHighlight.style.width = `${mapped.w}px`;
        this.elementHighlight.style.height = `${mapped.h}px`;

        setTimeout(() => {
            if (this.elementHighlight) this.elementHighlight.classList.remove('active');
        }, 3000);
    }

    updateThought(text) {
        if (this.currentThought) this.currentThought.textContent = text;
    }

    addThought(text, kind = 'info') {
        if (!this.thoughtLog || !text) return;
        const now = Date.now();
        const normalized = String(text).trim();
        if (!normalized) return;

        // Collapse rapid duplicate messages instead of flooding the panel.
        const last = this.thoughtLog.lastElementChild;
        if (last && this.lastThoughtText === normalized && now - this.lastThoughtAt < 8000) {
            const currentCount = Number(last.getAttribute('data-count') || '1') + 1;
            last.setAttribute('data-count', String(currentCount));
            last.textContent = `${normalized} (${currentCount}x)`;
            this.lastThoughtAt = now;
            return;
        }

        const line = document.createElement('div');
        line.className = `thought-line ${kind}`;
        line.textContent = normalized;
        line.setAttribute('data-count', '1');
        this.thoughtLog.appendChild(line);
        while (this.thoughtLog.children.length > 14) {
            this.thoughtLog.removeChild(this.thoughtLog.firstChild);
        }
        this.thoughtLog.scrollTop = this.thoughtLog.scrollHeight;
        this.lastThoughtText = normalized;
        this.lastThoughtAt = now;
    }

    clearThoughtLog() {
        if (!this.thoughtLog) return;
        this.thoughtLog.innerHTML = '';
        this.lastThoughtText = '';
        this.lastThoughtAt = 0;
    }

    showNextAction(text, icon = '🖱️') {
        if (!this.nextAction) return;
        if (this.nextActionText) this.nextActionText.textContent = text;
        if (this.nextActionIcon) this.nextActionIcon.textContent = icon;
        this.nextAction.classList.add('active');
    }

    resetReasoning() {
        this.reasoningSteps.forEach((stepElement) => {
            this.applyStepState(stepElement, 'pending');
        });
    }

    setReasoningState(step, status) {
        const stepElement = this.reasoningSteps.get(step);
        if (!stepElement) return;
        this.applyStepState(stepElement, status);
    }

    applyStepState(stepElement, status) {
        const icon = stepElement.querySelector('.step-icon');
        stepElement.classList.remove('pending', 'active', 'completed', 'failed');

        if (status === 'active') {
            stepElement.classList.add('active');
            if (icon) icon.textContent = '⟳';
            return;
        }

        if (status === 'completed') {
            stepElement.classList.add('completed');
            if (icon) icon.textContent = '✓';
            return;
        }

        if (status === 'failed') {
            stepElement.classList.add('failed');
            if (icon) icon.textContent = '!';
            return;
        }

        stepElement.classList.add('pending');
        if (icon) icon.textContent = '○';
    }

    setAnalyzeBusy(busy) {
        if (!this.analyzeBtn) return;
        this.analyzeBtn.disabled = busy;
        this.analyzeBtn.style.opacity = busy ? '0.5' : '1';
        this.analyzeBtn.style.cursor = busy ? 'not-allowed' : 'pointer';
    }

    setOrbState(state) {
        if (!this.voiceOrb) return;
        this.voiceOrb.classList.remove('idle', 'listening', 'thinking', 'speaking');
        this.voiceOrb.classList.add(state);
    }

    setVoiceStatus(text) {
        if (this.voiceStatus) {
            this.voiceStatus.textContent = text;
            return;
        }
        this.updateThought(text);
    }

    setVoiceTranscript(text) {
        if (this.voiceTranscript) this.voiceTranscript.textContent = text;
    }

    startListening() {
        if (!this.voiceSupported || !this.voiceEnabled || this.isListening || this.isSpeaking) return;
        try {
            this.recognition.lang = this.voiceLang;
            this.recognition.start();
        } catch (_) {
            this.setVoiceStatus('Voice: failed to start');
        }
    }

    stopListening() {
        if (!this.recognition || !this.isListening) return;
        this.recognition.stop();
    }

    async toggleVoiceMode() {
        if (!this.voiceSupported) return;
        this.voiceEnabled = !this.voiceEnabled;
        if (this.voiceEnabled) {
            const ok = await this.ensureMicrophonePermission();
            if (!ok) {
                this.voiceEnabled = false;
                this.setOrbState('idle');
                return;
            }
            this.setVoiceStatus(`Voice: enabled (${this.voiceLang})`);
            this.setVoiceTranscript('Listening for commands...');
            this.addThought('Voice mode enabled.');
            this.startListening();
        } else {
            this.setVoiceStatus('Voice: idle');
            this.setVoiceTranscript('Voice mode disabled.');
            this.stopListening();
            this.setOrbState('idle');
            this.addThought('Voice mode disabled.');
            window.speechSynthesis.cancel();
            this.isSpeaking = false;
        }
    }

    speak(text) {
        if (!this.voiceSupported || !text) return;
        const sentence = String(text).trim();
        if (!sentence) return;
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(sentence);
        utter.lang = 'en-US';
        utter.rate = 1.0;
        utter.pitch = 1.0;
        utter.onstart = () => {
            this.isSpeaking = true;
            this.setOrbState('speaking');
            this.setVoiceStatus('Voice: speaking');
        };
        utter.onend = () => {
            this.isSpeaking = false;
            if (this.voiceEnabled) {
                this.setVoiceStatus('Voice: listening...');
                this.startListening();
            } else {
                this.setVoiceStatus('Voice: idle');
                this.setOrbState('idle');
            }
        };
        utter.onerror = () => {
            this.isSpeaking = false;
            this.setOrbState(this.voiceEnabled ? 'listening' : 'idle');
        };
        window.speechSynthesis.speak(utter);
    }

    normalizeUrl(text) {
        const candidate = text
            .trim()
            .replace(/\s+dot\s+/gi, '.')
            .replace(/\s+point\s+/gi, '.')
            .replace(/\s+slash\s+/gi, '/')
            .replace(/\s+/g, '');
        if (!candidate) return '';
        if (!candidate.includes('.') && !candidate.startsWith('http://') && !candidate.startsWith('https://')) {
            return '';
        }
        if (candidate.startsWith('http://') || candidate.startsWith('https://')) return candidate;
        return `https://${candidate}`;
    }

    handleVoiceCommand(rawText) {
        const spoken = rawText.trim();
        if (!spoken) return;
        this.clearThoughtLog();
        this.pendingVoiceResponse = true;
        this.setOrbState('thinking');
        this.setVoiceStatus('Voice: processing command');
        this.sendAction('voice_command', { command: spoken });
        this.addThought(`Voice command sent to backend: "${spoken}"`);
    }

    runTextCommand() {
        const command = (this.commandInput?.value || '').trim();
        if (!command) return;
        this.clearThoughtLog();
        this.pendingVoiceResponse = false;
        this.updateThought(`Running command: ${command}`);
        this.sendAction('voice_command', { command });
        this.addThought(`Command sent: "${command}"`, 'reasoning');
    }

    async runMicCheck() {
        if (!this.voiceSupported) {
            this.setVoiceStatus('Voice: unsupported in this browser/context');
            return;
        }
        this.setVoiceStatus('Voice: running microphone check...');
        const ok = await this.ensureMicrophonePermission();
        if (!ok) return;
        this.setVoiceStatus('Voice: microphone OK');
        this.setVoiceTranscript('Mic ready. Voice mode enabled, listening now.');
        this.addThought('Mic check succeeded. Enabling voice mode.', 'reasoning');
        if (!this.voiceEnabled) {
            this.voiceEnabled = true;
        }
        this.speak('Microphone is ready.');
        // Start listening after TTS ends.
        this.startListening();
    }

    showVoiceHelp() {
        const help = [
            'go to docs.langchain.com',
            'search langchain agents',
            'analyze this page',
            'click github',
            'scroll down',
            'scroll up',
        ].join(' | ');
        this.setVoiceTranscript(help);
        this.addThought('Displayed voice command help.', 'reasoning');
    }

    sendAction(action, data = {}) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action, ...data }));
        }
    }

    setupControls() {
        if (this.navigateBtn) {
            this.navigateBtn.addEventListener('click', () => {
                const url = this.urlInput.value;
                if (url) {
                    this.clearThoughtLog();
                    this.updateThought('Navigating to ' + url + '...');
                    this.sendAction('navigate', { url });
                }
            });
        }

        if (this.urlInput) {
            this.urlInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.navigateBtn.click();
            });
        }

        this.runCommandBtn?.addEventListener('click', () => {
            this.runTextCommand();
        });

        this.commandInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.runTextCommand();
        });

        document.getElementById('refreshBtn')?.addEventListener('click', () => {
            this.clearThoughtLog();
            this.updateThought('Refreshing view...');
            this.sendAction('extract_dom');
        });

        this.analyzeBtn?.addEventListener('click', () => {
            this.clearThoughtLog();
            this.setAnalyzeBusy(true);
            this.resetReasoning();
            this.showNextAction('Analyzing page now...', '🧠');
            this.updateThought('AI analysis starting...');
            this.sendAction('analyze', { query: 'Analyze current page and return semantic structure.' });
        });

        document.getElementById('minimizeReasoning')?.addEventListener('click', () => {
            if (this.reasoningOverlay) this.reasoningOverlay.classList.toggle('minimized');
        });

        document.getElementById('pauseBtn')?.addEventListener('click', () => {
            this.toggleVoiceMode();
        });

        this.voiceOrb?.addEventListener('click', () => {
            this.toggleVoiceMode();
        });

        document.getElementById('micCheckBtn')?.addEventListener('click', () => {
            this.runMicCheck();
        });

        document.getElementById('voiceHelpBtn')?.addEventListener('click', () => {
            this.showVoiceHelp();
        });
    }
}

window.addEventListener('load', () => {
    window.agentController = new MinimalAgentController();
});
