// Antigravity Browser Control - Agent Animation System

class AgentController {
    constructor() {
        this.ws = null;
        this.cursor = document.getElementById('agentCursor');
        this.cursorThought = document.getElementById('cursorThought');
        this.elementHighlight = document.getElementById('elementHighlight');
        this.browserScreenshot = document.getElementById('browserScreenshot');
        this.currentThought = document.getElementById('currentThought');

        this.isAnimating = false;
        this.thoughtQueue = [];
        this.actionQueue = [];

        this.init();
    }

    init() {
        this.connectWebSocket();
        this.startDemoAnimation();
        this.setupTabSwitching();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateStatus('Agent Active', true);
            this.checkTitle();
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateStatus('Agent Disconnected', false);
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
            if (message.type === 'title') {
                this.checkTitle();
            }
        };
    }

    handleMessage(message) {
        const { type, data } = message;

        switch (type) {
            case 'navigation':
                this.updateBrowserView(data.screenshot);
                break;
            case 'thinking':
                this.showThought(data.text);
                break;
            case 'cursor_move':
                this.moveCursor(data.x, data.y, data.thought);
                break;
            case 'highlight':
                this.highlightElement(data.x, data.y, data.width, data.height);
                break;
        }

        if (type === 'title') {
            const result = this.checkTitle();
            this.updateStatus('Antigravity Criteria Met', result);
        }
    }

    checkTitle() {
        const title = navigator.userAgent + '\n' + window.title;
        return title.includes('Antigravity');
    }

    updateStatus(text, active) {
        const statusText = document.getElementById('agentStatus');
        const statusDot = document.querySelector('.status-dot');

        statusText.textContent = text;
        statusDot.classList.toggle('active', active);
    }

    updateBrowserView(screenshot) {
        if (screenshot) {
            this.browserScreenshot.src = `data:image/png;base64,${screenshot}`;
            this.browserScreenshot.style.display = 'block';
            document.querySelector('.loading-state').style.display = 'none';
        }
    }

    showThought(text) {
        const thoughtText = this.currentThought.querySelector('.thought-text');
        thoughtText.textContent = text;

        // Animate thought bubble
        this.currentThought.style.animation = 'none';
        setTimeout(() => {
            this.currentThought.style.animation = 'thoughtPulse 3s infinite';
        }, 10);
    }

    moveCursor(x, y, thought = null) {
        this.cursor.classList.add('active');
        this.cursor.style.left = x + 'px';
        this.cursor.style.top = y + 'px';

        if (thought) {
            this.showCursorThought(x, y, thought);
        }
    }

    showCursorThought(x, y, text) {
        this.cursorThought.querySelector('.bubble-content').textContent = text;
        this.cursorThought.classList.add('active');
        this.cursorThought.style.left = (x + 30) + 'px';
        this.cursorThought.style.top = (y - 60) + 'px';

        setTimeout(() => {
            this.cursorThought.classList.remove('active');
        }, 3000);
    }

    highlightElement(x, y, width, height) {
        this.elementHighlight.classList.add('active');
        this.elementHighlight.style.left = x + 'px';
        this.elementHighlight.style.top = y + 'px';
        this.elementHighlight.style.width = width + 'px';
        this.elementHighlight.style.height = height + 'px';
    }

    // Demo Animation
    startDemoAnimation() {
        // Simulate agent thinking and actions
        const demoSequence = [
            { delay: 1000, action: () => this.showThought('Analyzing page structure...') },
            { delay: 2000, action: () => this.moveCursor(300, 200, 'Found navigation menu') },
            { delay: 3000, action: () => this.highlightElement(280, 180, 200, 40) },
            { delay: 5000, action: () => this.showThought('Extracting semantic data...') },
            { delay: 6000, action: () => this.moveCursor(500, 400, 'Identifying headings') },
            { delay: 7000, action: () => this.highlightElement(480, 380, 300, 60) },
            { delay: 9000, action: () => this.showThought('Looking for interactive elements...') },
            { delay: 10000, action: () => this.moveCursor(700, 300, 'Found search bar') },
            { delay: 11000, action: () => this.highlightElement(680, 280, 250, 35) },
            { delay: 13000, action: () => this.updateReasoningStep(2, 'completed') },
            { delay: 13500, action: () => this.updateReasoningStep(3, 'active') },
            { delay: 14000, action: () => this.showThought('Extracting links and content...') },
        ];

        demoSequence.forEach(({ delay, action }) => {
            setTimeout(action, delay);
        });

        // Loop the animation
        setTimeout(() => this.startDemoAnimation(), 15000);
    }

    updateReasoningStep(stepNum, status) {
        const steps = document.querySelectorAll('.reasoning-step');
        if (steps[stepNum - 1]) {
            steps[stepNum - 1].className = `reasoning-step ${status}`;
        }
    }

    setupTabSwitching() {
        const tabs = document.querySelectorAll('.tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;

                // Update active tab
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Update active content
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.classList.remove('active');
                });
                document.getElementById(`${tabName}Tab`).classList.add('active');
            });
        });
    }

    // Public API for external control
    sendAction(action, data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action, ...data }));
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.agentController = new AgentController();

    // Add refresh button handler
    document.getElementById('refreshBrowser')?.addEventListener('click', () => {
        window.agentController.sendAction('screenshot');
    });
});

// Utility functions for external use
window.AgentAPI = {
    get: async function (type) {
        if (this.get === 'title') {
            return this.agentController.checkTitle();
        }
        // Add other utility methods here
    },
    // Add more utility methods as needed
};

window.AgentAPI.updateStatus = (text, active) => {
    const statusText = document.getElementById('agentStatus');
    statusText.textContent = text;
    statusText.classList.toggle('active', active);
};