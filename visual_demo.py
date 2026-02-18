"""
Interactive demo with visual mouse movements and element highlighting
"""

import asyncio
from playwright.async_api import async_playwright
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
import base64
from config import MODEL_LLM_VISION

class VisualDemoAgent:
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None
        self.llm = ChatOllama(model=MODEL_LLM_VISION, temperature=0)
        
    async def start(self):
        """Start browser with maximum visibility"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            slow_mo=800,  # Slow down for better visibility
            args=[
                '--start-maximized',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        self.page = await context.new_page()
        
        # Inject visual feedback CSS and JS
        await self.page.add_init_script("""
            // Create agent indicator overlay
            const overlay = document.createElement('div');
            overlay.id = 'agent-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                z-index: 999999;
            `;
            
            // Create status banner
            const banner = document.createElement('div');
            banner.id = 'agent-banner';
            banner.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 15px 25px;
                border-radius: 12px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 600;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                z-index: 9999999;
                pointer-events: none;
                display: none;
            `;
            banner.innerHTML = '🤖 AI Agent Analyzing...';
            
            // Create mouse cursor
            const cursor = document.createElement('div');
            cursor.id = 'agent-cursor';
            cursor.style.cssText = `
                position: fixed;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                background: rgba(102, 126, 234, 0.6);
                border: 3px solid #667eea;
                pointer-events: none;
                z-index: 9999998;
                display: none;
                box-shadow: 0 0 20px rgba(102, 126, 234, 0.8);
                transition: all 0.1s ease;
            `;
            
            // Add to page when DOM loads
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => {
                    document.body.appendChild(overlay);
                    document.body.appendChild(banner);
                    document.body.appendChild(cursor);
                });
            } else {
                document.body.appendChild(overlay);
                document.body.appendChild(banner);
                document.body.appendChild(cursor);
            }
            
            // Helper functions
            window.agentShowBanner = function(text) {
                const b = document.getElementById('agent-banner');
                if (b) {
                    b.innerHTML = text;
                    b.style.display = 'block';
                }
            };
            
            window.agentHideBanner = function() {
                const b = document.getElementById('agent-banner');
                if (b) b.style.display = 'none';
            };
            
            window.agentHighlight = function(selector, color = '#667eea') {
                const elements = typeof selector === 'string' 
                    ? document.querySelectorAll(selector) 
                    : [selector];
                    
                elements.forEach(el => {
                    if (!el) return;
                    el.style.outline = `4px solid ${color}`;
                    el.style.outlineOffset = '4px';
                    el.style.transition = 'all 0.3s ease';
                    
                    setTimeout(() => {
                        el.style.outline = '';
                        el.style.outlineOffset = '';
                    }, 3000);
                });
            };
            
            window.agentMoveCursor = function(x, y) {
                const c = document.getElementById('agent-cursor');
                if (c) {
                    c.style.display = 'block';
                    c.style.left = x + 'px';
                    c.style.top = y + 'px';
                }
            };
            
            window.agentHideCursor = function() {
                const c = document.getElementById('agent-cursor');
                if (c) c.style.display = 'none';
            };
        """)
        
    async def show_banner(self, text):
        """Show status banner"""
        try:
            await self.page.wait_for_load_state("domcontentloaded")
            await self.page.evaluate(f"""
                if (typeof window.agentShowBanner === 'function') {{
                    window.agentShowBanner('{text}');
                }}
            """)
        except:
            pass
        
    async def hide_banner(self):
        """Hide status banner"""
        try:
            await self.page.evaluate("""
                if (typeof window.agentHideBanner === 'function') {
                    window.agentHideBanner();
                }
            """)
        except:
            pass
        
    async def highlight_elements(self, selector, color='#667eea'):
        """Highlight elements on page"""
        try:
            await self.page.evaluate(f"""
                if (typeof window.agentHighlight === 'function') {{
                    window.agentHighlight('{selector}', '{color}');
                }}
            """)
        except:
            pass
        
    async def move_cursor_to_element(self, selector):
        """Move visual cursor to element"""
        try:
            box = await self.page.locator(selector).first.bounding_box()
            if box:
                x = box['x'] + box['width'] / 2
                y = box['y'] + box['height'] / 2
                await self.page.evaluate(f"""
                    if (typeof window.agentMoveCursor === 'function') {{
                        window.agentMoveCursor({x}, {y});
                    }}
                """)
        except:
            pass
            
    async def analyze_with_vision(self, query):
        """Analyze current page with vision model"""
        screenshot_bytes = await self.page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": query},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                },
            ]
        )
        
        response = await self.llm.ainvoke([message])
        return response.content
        
    async def stop(self):
        """Cleanup"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


async def interactive_demo():
    """Run interactive demo with visual feedback"""
    agent = VisualDemoAgent()
    
    print("\n" + "=" * 70)
    print("🎬 VISUAL BROWSER AGENT - INTERACTIVE DEMO")
    print("=" * 70)
    print("\n👀 WATCH THE BROWSER WINDOW - You'll see:")
    print("   • Visual cursor movements")
    print("   • Element highlighting")
    print("   • Real-time AI analysis")
    print("   • Status banners\n")
    
    try:
        # Start browser
        print("🚀 Starting browser...")
        await agent.start()
        await asyncio.sleep(2)
        
        # Demo 1: Python.org
        print("\n📍 DEMO 1: Analyzing Python.org")
        print("-" * 70)
        
        await agent.show_banner("🤖 Navigating to Python.org...")
        await agent.page.goto("https://www.python.org", wait_until="networkidle")
        await asyncio.sleep(2)
        
        await agent.show_banner("🔍 Analyzing page structure...")
        await asyncio.sleep(1)
        
        # Highlight main sections
        print("   • Highlighting navigation...")
        await agent.highlight_elements("nav", "#667eea")
        await asyncio.sleep(2)
        
        print("   • Highlighting headings...")
        await agent.highlight_elements("h1, h2", "#10b981")
        await asyncio.sleep(2)
        
        print("   • Highlighting links...")
        await agent.highlight_elements("a.button, .download-link", "#f59e0b")
        await asyncio.sleep(2)
        
        # AI Analysis
        await agent.show_banner("🧠 AI Vision Analysis in progress...")
        print("\n   🤖 Running AI vision analysis...")
        analysis = await agent.analyze_with_vision(
            "Describe this website's layout, main sections, and purpose in 2-3 sentences."
        )
        print(f"\n   💡 AI Says: {analysis}\n")
        await asyncio.sleep(3)
        
        # Demo 2: GitHub
        print("\n📍 DEMO 2: Analyzing GitHub Repository")
        print("-" * 70)
        
        await agent.show_banner("🤖 Navigating to GitHub...")
        await agent.page.goto("https://github.com/langchain-ai/langchain", wait_until="networkidle")
        await asyncio.sleep(2)
        
        await agent.show_banner("🔍 Extracting repository info...")
        
        # Highlight repository elements
        print("   • Highlighting repository header...")
        await agent.highlight_elements("h1", "#667eea")
        await asyncio.sleep(2)
        
        print("   • Highlighting stats...")
        await agent.highlight_elements("[href*='stargazers'], [href*='forks']", "#10b981")
        await asyncio.sleep(2)
        
        print("   • Highlighting README sections...")
        await agent.highlight_elements("article h2, article h3", "#f59e0b")
        await asyncio.sleep(2)
        
        # AI Analysis
        await agent.show_banner("🧠 AI analyzing repository...")
        print("\n   🤖 Running AI vision analysis...")
        analysis = await agent.analyze_with_vision(
            "What is this GitHub repository about? What are the key features or sections visible?"
        )
        print(f"\n   💡 AI Says: {analysis}\n")
        await asyncio.sleep(3)
        
        # Demo 3: Documentation
        print("\n📍 DEMO 3: Analyzing Documentation Structure")
        print("-" * 70)
        
        await agent.show_banner("🤖 Loading documentation...")
        await agent.page.goto("https://python.langchain.com/docs/introduction/", wait_until="networkidle")
        await asyncio.sleep(2)
        
        await agent.show_banner("📚 Analyzing documentation structure...")
        
        # Highlight doc elements
        print("   • Highlighting sidebar navigation...")
        await agent.highlight_elements("nav, aside", "#667eea")
        await asyncio.sleep(2)
        
        print("   • Highlighting main content...")
        await agent.highlight_elements("main article", "#10b981")
        await asyncio.sleep(2)
        
        print("   • Highlighting code blocks...")
        await agent.highlight_elements("pre, code", "#f59e0b")
        await asyncio.sleep(2)
        
        # Final AI Analysis
        await agent.show_banner("🧠 Final AI analysis...")
        print("\n   🤖 Running final AI vision analysis...")
        analysis = await agent.analyze_with_vision(
            "How is this documentation organized? What navigation options are available?"
        )
        print(f"\n   💡 AI Says: {analysis}\n")
        await asyncio.sleep(3)
        
        await agent.hide_banner()
        
        print("\n" + "=" * 70)
        print("✅ DEMO COMPLETE!")
        print("=" * 70)
        print("\nThe browser will stay open for 10 seconds so you can review...")
        await asyncio.sleep(10)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n🔄 Closing browser...")
        await agent.stop()
        print("✅ Demo finished!\n")


if __name__ == "__main__":
    asyncio.run(interactive_demo())
