import asyncio
import base64
import os
from datetime import datetime
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config import MODEL_LLM_VISION


def encode_image(image_path: str) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def web_browse(url: str) -> str:
    """Browses a URL and returns the page title and content."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        title = await page.title()
        content = await page.content()
        await browser.close()
        return f"Title: {title}\nContent snippet: {content[:1000]}..."


async def web_click(url: str, selector: str) -> str:
    """Clicks an element on a webpage."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        await page.click(selector)
        await asyncio.sleep(1)
        new_url = page.url
        await browser.close()
        return f"Clicked {selector}. New URL: {new_url}"


async def take_screenshot(url: str, output_path: str = "screenshot.png") -> str:
    """Takes a screenshot of a webpage."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        await page.screenshot(path=output_path, full_page=True)
        await browser.close()
        return f"Screenshot saved to {output_path}"


def search_web(query: str) -> str:
    """Searches the web for information."""
    # Mock implementation - in production, use a real search API
    return (
        f"Search results for '{query}': [Mock results - integrate with real search API]"
    )


def execute_python(code: str) -> str:
    """Executes Python code and returns the result."""
    try:
        local_vars = {}
        exec(code, {"__builtins__": __builtins__}, local_vars)
        return str(local_vars.get("result", "Code executed successfully"))
    except Exception as e:
        return f"Error: {str(e)}"


class VisualMultiAgent:
    """
    Visual Multi-Agent System using LangChain + Ollama
    Workflow: Visual Input → LLM (Vision) → Tools (Browser, Scripts, Files)
    """

    def __init__(self):
        self.llm = ChatOllama(model=MODEL_LLM_VISION, temperature=0)
        self.tools = {
            "web_browse": web_browse,
            "web_click": web_click,
            "take_screenshot": take_screenshot,
            "search_web": search_web,
            "execute_python": execute_python,
        }
        self.conversation_history = []

    async def analyze_image(self, image_path: str, query: str) -> str:
        """Analyzes an image with vision model."""
        b64_image = encode_image(image_path)

        message = HumanMessage(
            content=[
                {"type": "text", "text": query},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                },
            ]
        )

        self.conversation_history.append(message)
        response = self.llm.invoke(self.conversation_history)
        self.conversation_history.append(AIMessage(content=response.content))

        return response.content

    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Executes a tool by name."""
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not found"

        tool_func = self.tools[tool_name]

        # Handle async tools
        if asyncio.iscoroutinefunction(tool_func):
            result = await tool_func(**kwargs)
        else:
            result = tool_func(**kwargs)

        return result

    async def get_state(self, url: Optional[str] = None) -> dict:
        """Perceived state - Sense the world"""
        if url:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle")
                screenshot_bytes = await page.screenshot()
                url = page.url
                await browser.close()
        else:
            # Fallback for current view
            if not os.path.exists("current_view.png"):
                # Mock if no navigation happened
                return {"screenshot": "", "url": "None", "title": "No state"}
            with open("current_view.png", "rb") as f:
                screenshot_bytes = f.read()
            url = "Last known URL"

        return {
            "screenshot": base64.b64encode(screenshot_bytes).decode("utf-8"),
            "url": url,
            "timestamp": datetime.now().isoformat(),
        }

    async def run_workflow(self, image_path: str, task: str) -> dict:
        """
        Main workflow: Visual Input → LLM → Tools
        """
        print(f"\n{'=' * 60}")
        print(f"🚀 Starting Visual Agent Workflow")
        print(f"{'=' * 60}\n")

        # Step 1: Analyze visual input
        print(f"📸 Step 1: Analyzing visual input...")
        analysis = await self.analyze_image(
            image_path,
            f"Analyze this image and help me with this task: {task}. "
            f"Available tools: {', '.join(self.tools.keys())}. "
            f"Suggest which tool to use and how.",
        )
        print(f"✅ Analysis: {analysis}\n")

        # Step 2: Parse and execute suggested actions
        # (In a full implementation, you'd parse the LLM's response to extract tool calls)
        print(f"🔧 Step 2: Ready to execute tools based on analysis")

        return {
            "analysis": analysis,
            "tools_available": list(self.tools.keys()),
            "status": "ready",
        }


async def demo():
    """Demo workflow."""
    agent = VisualMultiAgent()

    print(f"\n{'=' * 60}")
    print(f"🎯 Visual Multi-Agent System Demo")
    print(f"{'=' * 60}")
    print(f"Model: {MODEL_LLM_VISION}")
    print(f"Tools: Browser, Scripts, Files")
    print(f"{'=' * 60}\n")

    # Demo 1: Take a screenshot and analyze it
    print("Demo 1: Screenshot Analysis Workflow")
    print("-" * 60)

    url = "https://videogenapi.com/docs/"
    screenshot_path = "demo_screenshot.png"

    print(f"📸 Taking screenshot of {url}...")
    result = await agent.execute_tool(
        "take_screenshot", url=url, output_path=screenshot_path
    )
    print(f"✅ {result}\n")

    print(f"🔍 Analyzing screenshot...")
    if os.path.exists(screenshot_path):
        analysis = await agent.run_workflow(
            screenshot_path, "What is this website about? What are the main sections?"
        )
        print(f"\n📊 Results:")
        print(f"  - Analysis: {analysis['analysis'][:200]}...")
        print(f"  - Status: {analysis['status']}")
    else:
        print("⚠️  Screenshot not found, skipping analysis")

    print(f"\n{'=' * 60}")
    print(f"✅ Demo Complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(demo())
