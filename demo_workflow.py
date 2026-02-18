"""
Demo workflow to showcase the Visual Browser Agent's capabilities:
1. Navigate to a website
2. Extract semantic information in real-time
3. Use vision model to analyze the page
4. Interact with elements
"""

import asyncio
import sys
from app import BrowserAgent

async def demo_workflow():
    """Run a complete demo of the browser agent"""
    agent = BrowserAgent()
    
    print("=" * 60)
    print("🤖 VISUAL BROWSER AGENT - DEMO WORKFLOW")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Initialize browser (visible window)
        print("📌 Step 1: Starting browser (you should see a window open)...")
        await agent.start()
        await asyncio.sleep(2)
        print("✅ Browser started!\n")
        
        # Step 2: Navigate to a website
        print("📌 Step 2: Navigating to Python.org...")
        result = await agent.navigate("https://www.python.org")
        print(f"✅ Loaded: {result['title']}")
        print(f"   URL: {result['url']}\n")
        await asyncio.sleep(3)
        
        # Step 3: Extract DOM and semantic info
        print("📌 Step 3: Extracting semantic information...")
        dom_data = await agent.extract_dom()
        
        print(f"✅ Found:")
        print(f"   - {len(dom_data.get('headings', []))} headings")
        print(f"   - {len(dom_data.get('links', []))} links")
        print(f"   - {len(dom_data.get('images', []))} images")
        print(f"   - {len(dom_data.get('forms', []))} forms")
        
        if dom_data.get('headings'):
            print(f"\n   📝 Main headings:")
            for h in dom_data['headings'][:5]:
                print(f"      {h['level']}: {h['text'][:60]}")
        
        print()
        await asyncio.sleep(3)
        
        # Step 4: AI Vision Analysis
        print("📌 Step 4: Analyzing page with Vision AI (llama3.2-vision)...")
        print("   Query: 'What is this website about? Describe the main sections.'")
        analysis = await agent.analyze_page(
            "What is this website about? Describe the main sections and purpose."
        )
        print(f"\n🤖 AI Analysis:\n")
        print(f"{analysis}\n")
        await asyncio.sleep(3)
        
        # Step 5: Navigate to another page
        print("📌 Step 5: Navigating to LangChain documentation...")
        result = await agent.navigate("https://python.langchain.com/docs/introduction/")
        print(f"✅ Loaded: {result['title']}\n")
        await asyncio.sleep(3)
        
        # Step 6: Extract and analyze
        print("📌 Step 6: Extracting semantic data from LangChain docs...")
        dom_data = await agent.extract_dom()
        
        if dom_data.get('links'):
            print(f"\n   🔗 Key navigation links:")
            for link in dom_data['links'][:8]:
                if link['text'].strip():
                    print(f"      • {link['text'][:50]}")
        
        print()
        await asyncio.sleep(3)
        
        # Step 7: Final AI analysis
        print("📌 Step 7: Final AI analysis of documentation structure...")
        analysis = await agent.analyze_page(
            "Analyze this documentation page. What are the main topics covered? How is the information organized?"
        )
        print(f"\n🤖 AI Analysis:\n")
        print(f"{analysis}\n")
        await asyncio.sleep(3)
        
        # Step 8: Navigate to a complex site
        print("📌 Step 8: Testing on a more complex site (GitHub)...")
        result = await agent.navigate("https://github.com/langchain-ai/langchain")
        print(f"✅ Loaded: {result['title']}\n")
        await asyncio.sleep(3)
        
        print("📌 Step 9: Extracting repository information...")
        dom_data = await agent.extract_dom()
        
        if dom_data.get('headings'):
            print(f"\n   📋 Repository sections:")
            for h in dom_data['headings'][:6]:
                print(f"      {h['level']}: {h['text'][:60]}")
        
        print()
        await asyncio.sleep(3)
        
        print("=" * 60)
        print("✅ DEMO COMPLETE!")
        print("=" * 60)
        print("\nThe browser window will stay open for 10 seconds...")
        print("You can see all the pages we visited and analyzed.")
        await asyncio.sleep(10)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n🔄 Cleaning up...")
        await agent.stop()
        print("✅ Browser closed. Demo finished!")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Starting Visual Browser Agent Demo...")
    print("Watch the browser window that opens!")
    print("=" * 60 + "\n")
    
    asyncio.run(demo_workflow())
