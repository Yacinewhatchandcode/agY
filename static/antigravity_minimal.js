// Minimal Antigravity Browser Control - Robust Version
class MinimalAgentController {
    constructor() {
        this.ws = null;
        this.cursor = document.getElementById('agentCursor');
        this.thinkingBubble = document.getElementById('thinkingBubble');
        this.elementHighlight = document.getElementById('elementHighlight');
        this.currentThought = document.getElementById('currentThought');
        this.reasoningOverlay = document.getElementById('reasoningOverlay');
        this.nextAction = document.getElementById('nextAction');
        this.urlInput = document.getElementById('urlInput');
        this.navigateBtn = document.getElementById('navigateBtn');
        this.browserContent = document.getElementById('browserContent');

        this.init();
    }

    init() {
        this.connectWebSocket();
        this.setupControls();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        console.log('Connecting to WebSocket:', wsUrl);
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket Connected');
            const dot = document.querySelector('.status-dot');
            if (dot) dot.style.background = '#ef4444';
            this.updateThought('Connected to Agent. Ready.');

            // Initial sync
            this.sendAction('screenshot');
        };

        this.ws.onclose = (e) => {
            console.log('WebSocket Closed:', e.code, e.reason);
            const dot = document.querySelector('.status-dot');
            if (dot) dot.style.background = '#737373';
            this.updateThought('Disconnected. Reconnecting...');
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.ws.onerror = (err) => {
            console.error('WebSocket Error:', err);
            this.updateThought('Connection Error');
        };

        this.ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                this.handleMessage(msg);
            } catch (err) {
                console.error('Error parsing message:', err, e.data);
            }
        };
    }

    handleMessage(msg) {
        console.log('Message received:', msg.type);

        switch (msg.type) {
            case 'navigation':
                this.updateThought('Navigation: ' + (msg.data.title || 'Loaded'));
                if (msg.data.url) this.urlInput.value = msg.data.url;
                if (msg.data.screenshot) {
                    this.updateBrowser(msg.data.screenshot);
                }
                break;
            case 'screenshot':
                console.log('Updating screenshot from dedicated message');
                this.updateBrowser(msg.data);
                break;
            case 'dom':
                console.log('DOM arrived');
                if (msg.data.screenshot) {
                    this.updateBrowser(msg.data.screenshot);
                }
                break;
            case 'analysis':
                this.updateThought('Analysis complete.');
                this.moveCursor(window.innerWidth / 2, window.innerHeight / 2, msg.data);
                break;
            case 'error':
                console.error('Agent Error:', msg.data);
                this.updateThought('Error: ' + msg.data);
                break;
            case 'cursor':
                this.moveCursor(msg.x, msg.y, msg.thought);
                break;
            case 'highlight':
                this.highlightElement(msg.x, msg.y, msg.w, msg.h);
                break;
            case 'thinking':
                this.updateThought(msg.text);
                break;
        }
    }

    updateBrowser(screenshot) {
        if (!screenshot) {
            console.warn('Empty screenshot received');
            return;
        }

        if (!this.browserContent) {
            console.error('browserContent element not found');
            return;
        }

        console.log('Updating browser image with length:', screenshot.length);

        // Remove existing content (spinner, etc)
        this.browserContent.innerHTML = '';

        const img = document.createElement('img');
        img.src = 'data:image/png;base64,' + screenshot;
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'contain';
        img.style.display = 'block';
        img.id = 'activeScreenshot';

        img.onload = () => console.log('Screenshot image loaded successfully');
        img.onerror = (e) => console.error('Failed to load screenshot image', e);

        this.browserContent.appendChild(img);
    }

    moveCursor(x, y, thought = null) {
        if (!this.cursor) return;
        this.cursor.classList.add('active');
        this.cursor.style.left = x + 'px';
        this.cursor.style.top = y + 'px';

        if (thought) {
            this.showThinkingBubble(x, y, thought);
        }
    }

    showThinkingBubble(x, y, text) {
        if (!this.thinkingBubble) return;
        const textEl = this.thinkingBubble.querySelector('.bubble-text');
        if (textEl) textEl.textContent = text;

        this.thinkingBubble.classList.add('active');
        this.thinkingBubble.style.left = Math.min(x + 40, window.innerWidth - 300) + 'px';
        this.thinkingBubble.style.top = Math.max(y - 70, 70) + 'px';

        setTimeout(() => {
            if (this.thinkingBubble) this.thinkingBubble.classList.remove('active');
        }, 5000);
    }

    highlightElement(x, y, w, h) {
        if (!this.elementHighlight) return;
        this.elementHighlight.classList.add('active');
        this.elementHighlight.style.left = x + 'px';
        this.elementHighlight.style.top = y + 'px';
        this.elementHighlight.style.width = w + 'px';
        this.elementHighlight.style.height = h + 'px';

        setTimeout(() => {
            if (this.elementHighlight) this.elementHighlight.classList.remove('active');
        }, 3000);
    }

    updateThought(text) {
        if (this.currentThought) {
            this.currentThought.textContent = text;
            console.log('Thought update:', text);
        }
    }

    sendAction(action, data = {}) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('Sending action:', action, data);
            this.ws.send(JSON.stringify({ action, ...data }));
        } else {
            console.warn('Cannot send action, WebSocket not open:', action);
        }
    }

    setupControls() {
        if (this.navigateBtn) {
            this.navigateBtn.addEventListener('click', () => {
                const url = this.urlInput.value;
                if (url) {
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

        document.getElementById('refreshBtn')?.addEventListener('click', () => {
            this.updateThought('Refreshing view...');
            this.sendAction('extract_dom');
        });

        document.getElementById('analyzeBtn')?.addEventListener('click', () => {
            this.updateThought('AI analysis starting...');
            this.sendAction('analyze', { query: "Analyze the current view and describe key sections." });
        });

        document.getElementById('minimizeReasoning')?.addEventListener('click', () => {
            if (this.reasoningOverlay) this.reasoningOverlay.classList.toggle('minimized');
        });
    }
}

// Initialize when DOM ready
window.addEventListener('load', () => {
    console.log('App Loaded - Initializing Agent Controller');
    window.agentController = new MinimalAgentController();
});
