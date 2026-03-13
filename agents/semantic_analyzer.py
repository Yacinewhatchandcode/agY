"""
Module 3: Semantic Analyzer
Uses llama3.2-vision for visual analysis and deepseek-r1 for text reasoning.
Understands the MEANING of every page element.
"""

from typing import Dict

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from config import MODEL_LLM_VISION


class SemanticAnalyzer:
    def __init__(self):
        self.vision = ChatOllama(model=MODEL_LLM_VISION, temperature=0)
        self.reasoning = ChatOllama(model="deepseek-r1:7b", temperature=0)

    async def analyze_page(
        self, screenshot_b64: str, text_content: str, meta: Dict
    ) -> Dict:
        """Full semantic analysis: visual + textual."""
        visual = await self._analyze_visual(screenshot_b64)
        textual = await self._analyze_text(text_content, meta)
        return {"visual": visual, "textual": textual}

    async def _analyze_visual(self, screenshot_b64: str) -> str:
        """What does the page LOOK like?"""
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "Analyze this webpage screenshot comprehensively:\n"
                        "1. Layout structure (header, sidebar, main, footer)\n"
                        "2. Color scheme and design quality\n"
                        "3. Key visual elements (logos, hero images, CTAs)\n"
                        "4. Navigation structure\n"
                        "5. Accessibility concerns (contrast, text size)\n"
                        "Be precise, factual, and concise."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{screenshot_b64}"
                    },
                },
            ]
        )
        response = await self.vision.ainvoke([message])
        return response.content

    async def _analyze_text(self, text_content: str, meta: Dict) -> str:
        """What does the page SAY?"""
        prompt = (
            f"Analyze this webpage content semantically:\n"
            f"Title: {meta.get('title', 'N/A')}\n"
            f"Description: {meta.get('description', 'N/A')}\n"
            f"Page Text (first 3000 chars):\n{text_content[:3000]}\n\n"
            f"Provide:\n"
            f"1. Main topic/purpose of the page\n"
            f"2. Target audience\n"
            f"3. Key messages\n"
            f"4. Content quality assessment\n"
            f"5. SEO observations\n"
            f"Be concise and factual."
        )
        message = HumanMessage(content=prompt)
        response = await self.reasoning.ainvoke([message])
        content = response.content
        if "<think>" in content:
            content = content.split("</think>")[-1].strip()
        return content

    async def analyze_media(self, image_b64: str) -> str:
        """Analyze a single image/media element."""
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "What does this image show? Describe its purpose, "
                        "quality, and relevance in a website context."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
            ]
        )
        response = await self.vision.ainvoke([message])
        return response.content
