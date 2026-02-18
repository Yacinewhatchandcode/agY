// WebSocket connection
let ws = null;
let isConnected = false;

// DOM elements
const urlInput = document.getElementById('urlInput');
const navigateBtn = document.getElementById('navigateBtn');
const queryInput = document.getElementById('queryInput');
const analyzeBtn = document.getElementById('analyzeBtn');
const extractDomBtn = document.getElementById('extractDomBtn');
const screenshotBtn = document.getElementById('screenshotBtn');
const clearBtn = document.getElementById('clearBtn');
const refreshPreview = document.getElementById('refreshPreview');
const goalInput = document.getElementById('goalInput');
const autoBtn = document.getElementById('autoBtn');

const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const pageTitle = document.getElementById('pageTitle');
const pageUrl = document.getElementById('pageUrl');
const lastUpdated = document.getElementById('lastUpdated');

// DOM elements
const previewPlaceholder = document.getElementById('previewPlaceholder');
const previewImage = document.getElementById('previewImage');
const analysisResult = document.getElementById('analysisResult');

const headings = document.getElementById('headings');
const links = document.getElementById('links');
const images = document.getElementById('images');
const forms = document.getElementById('forms');
const domTree = document.getElementById('domTree');
const consoleOutput = document.getElementById('consoleOutput');

// Initialize WebSocket connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        isConnected = true;
        statusDot.classList.add('connected');
        statusText.textContent = 'Connected';
        logConsole('WebSocket connected', 'success');
    };

    ws.onclose = () => {
        isConnected = false;
        statusDot.classList.remove('connected');
        statusText.textContent = 'Disconnected';
        logConsole('WebSocket disconnected', 'warning');

        // Attempt to reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
        logConsole(`WebSocket error: ${error}`, 'error');
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleMessage(message);
    };
}

// Handle incoming messages
function handleMessage(message) {
    const { type, data } = message;

    switch (type) {
        case 'navigation':
            handleNavigation(data);
            break;
        case 'dom':
            handleDOM(data);
            break;
        case 'analysis':
            handleAnalysis(data);
            break;
        case 'screenshot':
            updatePreview(data.screenshot);
            break;
        case 'error':
            logConsole(`Error: ${data}`, 'error');
            break;
        case 'status':
            // Visual pulse for the autonomous agent
            if (data.status === 'Thinking...') {
                logConsole(`[AGENT] ${data.message}`, 'info');
                statusText.textContent = data.message;
                statusDot.style.animation = 'pulse 1s infinite';
            } else {
                statusDot.style.animation = 'none';
            }
            break;
        default:
            logConsole(`Unknown message type: ${type}`, 'warning');
    }
}

// Handle navigation response
function handleNavigation(data) {
    pageTitle.textContent = data.title || '-';
    pageUrl.textContent = data.url || '-';
    lastUpdated.textContent = new Date(data.timestamp).toLocaleTimeString();

    if (data.screenshot) {
        updatePreview(data.screenshot);
    }

    // Check for title element and display it
    const titleElement = document.querySelector('title');
    if (titleElement) {
        const title = createSemanticTitle(titleElement.textContent);
        headings.push(title);
    }
}

// Helper function to create semantic title item
function createSemanticTitle(text) {
    return document.createElementNS('http://www.w3.org/1999/xhtml', 'title')
        .textContent = text;
}

// DOM handling
function handleDOM(data) {
    const { headings, links, images, forms } = data;

    // Create basic semantic HTML elements for each element type
    createBasicSemanticHTML(headings, 'headings');
    createBasicSemanticHTML(links, 'links');
    createBasicSemanticHTML(images, 'images');
    createBasicSemanticHTML(forms, 'forms');

    // Handle specific title if present
    handleTitleElement(headings, data.title);

    // Create custom semantic HTML elements for each type of element
    createCustomSemanticHTML(headings);
    createCustomSemanticHTML(links);
    createCustomSemanticHTML(images);
    createCustomSemanticHTML(forms);
}

// Create basic semantic HTML elements based on the element types
function createBasicSemanticHTML(elements, type) {
    if (elements) {
        const semanticElement = createBasicSemanticElement(type);
        Array.from(elements).forEach(element => addElementToDOM(semanticElement, element));
    }
}

// Create custom semantic HTML elements for each type of element
function createCustomSemanticHTML(type) {
    switch (type) {
        case 'headings':
            handleHeadings(type);
            break;
        case 'links':
            handleLinks(type);
            break;
        case 'images':
            handleImages(type);
            break;
        case 'forms':
            handleForms(type);
            break;
    }
}

// Handle specific title if present
function handleTitleElement(headings, titleText) {
    if (titleText) {
        const title = createSemanticTitle(titleText);
        headings.push(title);
    }
}

// Create semantic HTML elements for headings
function handleHeadings(type) {
    if (type.title) {
        // Add a heading level 1 element as the root of the semantic hierarchy
        const heading1 = document.createElementNS('http://www.w3.org/1999/xhtml', 'heading');
        heading1.className = type.titleLevel;
        headings.push(heading1);
    }

    // Create semantic heading elements for each heading
    createCustomSemanticHeadings(type, typeheadings);
}

// Custom handling logic for different element types
function handleLinks(type) {
    if (type.title) {
        const link = document.createElementNS('http://www.w3.org/1999/xhtml', 'title');
        link.href = type.url;
        link.className = type.titleLevel;
        links.push(link);
    }

    // Create semantic link elements for each link
    createCustomSemanticLinks(type, type.links);
}

function handleImages(type) {
    if (type.title) {
        const image = document.createElementNS('http://www.w3.org/1999/xhtml', 'title');
        image.className = type.titleLevel;
        images.push(image);
    }

    // Create semantic image elements for each image
    createCustomSemanticImages(type, type.images);
}

function handleForms(type) {
    if (type.title) {
        const form = document.createElementNS('http://www.w3.org/1999/xhtml', 'title');
        form.className = type.titleLevel;
        forms.push(form);
    }

    // Create semantic form elements for each form
    createCustomSemanticForms(type, type.forms);
}

// Helper functions to create custom semantic HTML elements
function createCustomSemanticHeadings(type, headings) {
    // Implementation for creating heading semantic elements
}

function createCustomSemanticLinks(type, links) {
    // Implementation for creating link semantic elements
}

function createCustomSemanticImages(type, images) {
    // Implementation for creating image semantic elements
}

function createCustomSemanticForms(type, forms) {
    // Implementation for creating form semantic elements
}

// Make functions globally available
window.fetchModels = fetchModels;
window.refreshModels = refreshModels;
window.getAvailableModels = () => availableModels;
window.getSelectedModel = () => selectedModel;

// Initialize
connectWebSocket();
logConsole('Visual Browser Agent initialized', 'info');

// Auto-load models on startup
fetchModels();

// --- Mode Switching Logic ---
const browserModeBtn = document.getElementById('browserModeBtn');
const researchModeBtn = document.getElementById('researchModeBtn');
const browserPanelEl = document.getElementById('browserPanel');
const researchPanelEl = document.getElementById('researchPanel');

function switchMode(mode) {
    if (mode === 'browser') {
        browserModeBtn?.classList.add('active');
        researchModeBtn?.classList.remove('active');
        if (browserPanelEl) browserPanelEl.style.display = 'grid';
        if (researchPanelEl) researchPanelEl.style.display = 'none';
        logConsole('Switched to Browser Mode', 'info');
    } else {
        browserModeBtn?.classList.remove('active');
        researchModeBtn?.classList.add('active');
        if (browserPanelEl) browserPanelEl.style.display = 'none';
        if (researchPanelEl) researchPanelEl.style.display = 'flex';
        logConsole('Switched to Deep Research Mode', 'info');
    }
}

if (browserModeBtn) browserModeBtn.addEventListener('click', () => switchMode('browser'));
if (researchModeBtn) researchModeBtn.addEventListener('click', () => switchMode('research'));