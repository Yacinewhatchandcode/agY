"""
Complete Visual Browser Agent Demo with AI Vision Analysis
Shows real-time browser control, semantic extraction, and vision-based understanding
"""

import asyncio
from playwright.async_api import async_playwright
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
import base64
from config import MODEL_LLM_VISION

async def complete_demo():
    """Complete demo with browser automation and AI vision analysis"""
    
    print("\n" + "=" * 80)
    print("🎬 VISUAL BROWSER AGENT - COMPLETE DEMO WITH AI VISION")
    print("=" * 80)
    print("\n📺 WATCH THE BROWSER WINDOW!")
    print("   You'll see:")
    print("   • Real-time navigation")
    print("   • Element highlighting (colored outlines)")
    print("   • AI banner showing agent status")
    print("   • Vision AI analyzing each page\n")
    
    playwright = None
    browser = None
    llm = ChatOllama(model=MODEL_LLM_VISION, temperature=0)
    
    try:
        # Start browser
        print("🚀 Starting browser with visual feedback...")
        playwright = await async_playwright().start()
        
        browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=800,  # Slow motion for visibility
            args=['--start-maximized']
        )
        
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        # Inject visual feedback
        await page.add_init_script("""
            document.addEventListener('DOMContentLoaded', () => {
                // Status banner
                const banner = document.createElement('div');
                banner.id = 'ai-banner';
                banner.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                    padding: 20px 30px;
                    border-radius: 15px;
                    font-family: -apple-system, sans-serif;
                    font-size: 18px;
                    font-weight: bold;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                    z-index: 999999;
                    animation: pulse 2s infinite;
                `;
                banner.textContent = '🤖 AI Agent Active';
                document.body.appendChild(banner);
                
                // Pulse animation
                const style = document.createElement('style');
                style.textContent = `
                    @keyframes pulse {
                        0%, 100% { transform: scale(1); }
                        50% { transform: scale(1.05); }
                    }
                `;
                document.head.appendChild(style);
            });
            
            window.updateBanner = function(text) {
                const banner = document.getElementById('ai-banner');
                if (banner) banner.textContent = text;
            };
            
            window.highlightElement = function(selector, color) {
                const els = document.querySelectorAll(selector);
                els.forEach(el => {
                    el.style.outline = `5px solid ${color}`;
                    el.style.outlineOffset = '5px';
                    el.style.transition = 'all 0.3s ease';
                });
            };
        """)
        
        print("✅ Browser ready!\n")
        await asyncio.sleep(2)
        
        # ========== DEMO 1: Python.org ==========
        print("=" * 80)
        print("📍 DEMO 1: Analyzing Python.org")
        print("=" * 80)
        
        await page.goto("https://www.python.org", wait_until="networkidle")
        print("✅ Page loaded: Python.org")
        await page.evaluate("window.updateBanner('🔍 Analyzing Python.org...')")
        await asyncio.sleep(2)
        
        # Highlight elements
        print("   🎯 Highlighting navigation...")
        await page.evaluate("window.highlightElement('nav', '#667eea')")
        await asyncio.sleep(2)
        
        print("   🎯 Highlighting headings...")
        await page.evaluate("window.highlightElement('h1, h2', '#10b981')")
        await asyncio.sleep(2)
        
        print("   🎯 Highlighting download buttons...")
        await page.evaluate("window.highlightElement('.download-link', '#f59e0b')")
        await asyncio.sleep(2)
        
        # AI Vision Analysis
        print("\n   🧠 Running AI Vision Analysis...")
        await page.evaluate("window.updateBanner('🧠 AI Vision Analyzing...')")
        
        screenshot = await page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": "Describe this website's purpose and main sections in 2-3 sentences."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
            ]
        )
        
        analysis = await llm.ainvoke([message])
        print(f"\n   💡 AI Analysis:")
        print(f"   {analysis.content}\n")
        await asyncio.sleep(3)
        
        # ========== DEMO 2: GitHub ==========
        print("=" * 80)
        print("📍 DEMO 2: Analyzing GitHub Repository")
        print("=" * 80)
        
        await page.goto("https://github.com/langchain-ai/langchain", wait_until="networkidle")
        print("✅ Page loaded: GitHub - LangChain")
        await page.evaluate("window.updateBanner('🔍 Analyzing GitHub...')")
        await asyncio.sleep(2)
        
        # Highlight elements
        print("   🎯 Highlighting repository name...")
        await page.evaluate("window.highlightElement('h1', '#667eea')")
        await asyncio.sleep(2)
        
        print("   🎯 Highlighting stats...")
        await page.evaluate("window.highlightElement('[href*=\"stargazers\"]', '#10b981')")
        await asyncio.sleep(2)
        
        print("   🎯 Highlighting README...")
        await page.evaluate("window.highlightElement('article h2', '#f59e0b')")
        await asyncio.sleep(2)
        
        # AI Vision Analysis
        print("\n   🧠 Running AI Vision Analysis...")
        await page.evaluate("window.updateBanner('🧠 AI Vision Analyzing...')")
        
        screenshot = await page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": "What is this GitHub repository about? What key information is visible?"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
            ]
        )
        
        analysis = await llm.ainvoke([message])
        print(f"\n   💡 AI Analysis:")
        print(f"   {analysis.content}\n")
        await asyncio.sleep(3)
        
        # ========== DEMO 3: Documentation ==========
        print("=" * 80)
        print("📍 DEMO 3: Analyzing Documentation Structure")
        print("=" * 80)
        
        await page.goto("https://python.langchain.com/docs/introduction/", wait_until="networkidle")
        print("✅ Page loaded: LangChain Documentation")
        await page.evaluate("window.updateBanner('🔍 Analyzing Docs...')")
        await asyncio.sleep(2)
        
        # Highlight elements
        print("   🎯 Highlighting sidebar...")
        await page.evaluate("window.highlightElement('nav, aside', '#667eea')")
        await asyncio.sleep(2)
        
        print("   🎯 Highlighting main content...")
        await page.evaluate("window.highlightElement('main', '#10b981')")
        await asyncio.sleep(2)
        
        print("   🎯 Highlighting code blocks...")
        await page.evaluate("window.highlightElement('pre', '#f59e0b')")
        await asyncio.sleep(2)
        
        # AI Vision Analysis
        print("\n   🧠 Running AI Vision Analysis...")
        await page.evaluate("window.updateBanner('🧠 AI Vision Analyzing...')")
        
        screenshot = await page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": "How is this documentation organized? What navigation options are available?"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
            ]
        )
        
        analysis = await llm.ainvoke([message])
        print(f"\n   💡 AI Analysis:")
        print(f"   {analysis.content}\n")
        await asyncio.sleep(3)
        
        # Complete
        await page.evaluate("window.updateBanner('✅ Demo Complete!')")
        
        print("\n" + "=" * 80)
        print("✅ DEMO COMPLETE!")
        print("=" * 80)
        print("\n📊 Summary:")
        print("   • Navigated to 3 different websites")
        print("   • Highlighted key elements on each page")
        print("   • Ran AI vision analysis on each page")
        print("   • Demonstrated real-time semantic understanding")
        print("\nBrowser will stay open for 10 seconds...\n")
        await asyncio.sleep(10)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n🔄 Closing browser...")
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()
        print("✅ Demo finished!\n")


if __name__ == "__main__":
    print("\n🎬 Starting Complete Visual Browser Agent Demo...")
    print("=" * 80)
    asyncio.run(complete_demo())
