"""
Simple visual demo that shows browser automation with real-time feedback
"""

import asyncio
from playwright.async_api import async_playwright
import sys

async def simple_visual_demo():
    """Simple demo with visible browser and console output"""
    
    print("\n" + "=" * 70)
    print("🎬 VISUAL BROWSER AGENT - SIMPLE DEMO")
    print("=" * 70)
    print("\n📺 A browser window will open - WATCH IT!")
    print("   You'll see the agent navigating and highlighting elements\n")
    
    playwright = None
    browser = None
    
    try:
        # Start Playwright
        print("🚀 Starting browser...")
        playwright = await async_playwright().start()
        
        # Launch browser in VISIBLE mode with slow motion
        browser = await playwright.chromium.launch(
            headless=False,  # VISIBLE!
            slow_mo=1000,    # Slow down by 1 second per action
            args=['--start-maximized']
        )
        
        # Create page
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        # Add visual overlay
        await page.add_init_script("""
            document.addEventListener('DOMContentLoaded', () => {
                // Add banner
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
                    font-family: Arial, sans-serif;
                    font-size: 18px;
                    font-weight: bold;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                    z-index: 999999;
                `;
                banner.textContent = '🤖 AI Agent Active';
                document.body.appendChild(banner);
            });
            
            window.highlightElement = function(selector, color) {
                const els = document.querySelectorAll(selector);
                els.forEach(el => {
                    el.style.outline = `5px solid ${color}`;
                    el.style.outlineOffset = '5px';
                });
            };
        """)
        
        print("✅ Browser opened!\n")
        await asyncio.sleep(2)
        
        # Demo 1: Navigate to Python.org
        print("📍 Step 1: Navigating to Python.org...")
        await page.goto("https://www.python.org", wait_until="networkidle")
        print("✅ Page loaded!")
        await asyncio.sleep(3)
        
        # Highlight navigation
        print("   🎯 Highlighting navigation menu...")
        await page.evaluate("window.highlightElement('nav', '#667eea')")
        await asyncio.sleep(3)
        
        # Highlight headings
        print("   🎯 Highlighting headings...")
        await page.evaluate("window.highlightElement('h1, h2', '#10b981')")
        await asyncio.sleep(3)
        
        # Highlight buttons
        print("   🎯 Highlighting download buttons...")
        await page.evaluate("window.highlightElement('.download-link, a.button', '#f59e0b')")
        await asyncio.sleep(3)
        
        # Demo 2: Navigate to GitHub
        print("\n📍 Step 2: Navigating to GitHub...")
        await page.goto("https://github.com/langchain-ai/langchain", wait_until="networkidle")
        print("✅ Page loaded!")
        await asyncio.sleep(3)
        
        # Highlight repo name
        print("   🎯 Highlighting repository name...")
        await page.evaluate("window.highlightElement('h1', '#667eea')")
        await asyncio.sleep(3)
        
        # Highlight stats
        print("   🎯 Highlighting repository stats...")
        await page.evaluate("window.highlightElement('[href*=\"stargazers\"], [href*=\"forks\"]', '#10b981')")
        await asyncio.sleep(3)
        
        # Highlight README
        print("   🎯 Highlighting README sections...")
        await page.evaluate("window.highlightElement('article h2', '#f59e0b')")
        await asyncio.sleep(3)
        
        # Demo 3: Navigate to LangChain docs
        print("\n📍 Step 3: Navigating to LangChain documentation...")
        await page.goto("https://python.langchain.com/docs/introduction/", wait_until="networkidle")
        print("✅ Page loaded!")
        await asyncio.sleep(3)
        
        # Highlight sidebar
        print("   🎯 Highlighting sidebar navigation...")
        await page.evaluate("window.highlightElement('nav, aside', '#667eea')")
        await asyncio.sleep(3)
        
        # Highlight main content
        print("   🎯 Highlighting main content area...")
        await page.evaluate("window.highlightElement('main', '#10b981')")
        await asyncio.sleep(3)
        
        # Highlight code blocks
        print("   🎯 Highlighting code examples...")
        await page.evaluate("window.highlightElement('pre', '#f59e0b')")
        await asyncio.sleep(3)
        
        print("\n" + "=" * 70)
        print("✅ DEMO COMPLETE!")
        print("=" * 70)
        print("\nThe browser will stay open for 10 more seconds...")
        print("You can see all the highlighted elements!\n")
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
    print("\n🎬 Starting Visual Browser Agent Demo...")
    print("=" * 70)
    asyncio.run(simple_visual_demo())
