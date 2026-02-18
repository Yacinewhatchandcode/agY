import asyncio
import os
import base64
from typing import Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.tools import tool
from langchain.agents import AgentExecutor, create_json_chat_agent
from config import MODEL_LLM_VISION

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

@tool
def google_search(query: str):
    """Searches the web for the given query."""
    return f"Searching for {query}... (Mock result: VideoGenAPI is a powerful video generation API)"

async def screen_capture(url: str = "https://www.google.com"):
    """Captures a screenshot of the specified URL and saves it as screenshot.png."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            # Get initial content to check for Antigravity in the visible context
            initial_content = (await page.content()).strip()
            
            if "App Name" in initial_content or "App Name" in page.title():
                path = "screenshot.png"
                await page.screenshot(path=path)
                await browser.close()
                return path
            
            # Retry if App Name not found in visible context
            for _ in range(3):
                try:
                    # Get more detailed content before checking
                    content = (await page.content()).strip()
                    if "App Name" in content or "App Name" in page.title():
                        path = "screenshot.png"
                        await page.screenshot(path=path)
                        await browser.close()
                        return path
                except Exception as e:
                    print(f"Error retrying: {e}")
                    await asyncio.sleep(1)
        finally:
            await browser.close()

class VisionAgent:
    def __init__(self):
        self.llm = ChatOllama(model=MODEL_LLM_VISION, temperature=0)
        self.tools = [google_search, screen_capture]
        
    async def analyze_image(self, image_path: str, query: str):
        """Analyzes an image and decides on next steps."""
        b64_image = encode_image(image_path)
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": f"You are a visual agent. Analyze this image and answer: {query}. If you need more information, suggest using a tool."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                },
            ]
        )
        
        response = await self.llm.ainvoke([message])
        return response.content

async def main():
    agent = VisionAgent()
    print(f"--- Visual Agent Started ({MODEL_LLM_VISION}) ---")
    
    # Example flow:
    target_url = "https://python.langchain.com/docs/introduction/"
    print(f"Action: Capturing screen of {target_url}...")
    
    # Use the tool directly for the first step
    path = await screen_capture.ainvoke({"url": target_url})
    print(f"Outcome: Screenshot saved to {path}")
    
    print("Action: Analyzing visual data...")
    query = "What is shown in this screenshot? Describe the main sections of the website."
    result = await agent.analyze_image(path, query)
    
    print("\n--- Agent Analysis Result ---")
    print(result)
    print("----------------------------")

if __name__ == "__main__":
    asyncio.run(main())