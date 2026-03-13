"""
Module 5: Phase 2 Strategy Agent
Synthesizes all audit data into actionable strategic direction.
"""

import json
from typing import Dict

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama


def _clean_llm_json(content: str) -> str:
    if "<think>" in content:
        content = content.split("</think>")[-1]
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        parts = content.split("```")
        if len(parts) >= 3:
            content = parts[1]
    return content.strip()


class StrategyAgent:
    def __init__(self):
        self.llm = ChatOllama(model="deepseek-r1:7b", temperature=0)

    async def generate_strategy(self, audit_data: Dict) -> Dict:
        """Phase 2: Synthesize everything into strategic direction."""

        prompt = f"""You are a Senior Product Strategist reviewing a complete website audit.

Audit Summary:
- Pages crawled: {audit_data.get('pages_crawled', 0)}
- Total links: {audit_data.get('total_links', 0)}
- Total forms: {audit_data.get('total_forms', 0)}
- Total buttons: {audit_data.get('total_buttons', 0)}
- Workflows detected: {len(audit_data.get('workflows', []))}
- Tests generated: {audit_data.get('total_tests', 0)}

Key Semantic Findings:
{json.dumps(audit_data.get('semantic_highlights', [])[:5], indent=2)[:3000]}

Detected User Workflows:
{json.dumps(audit_data.get('workflows', [])[:5], indent=2)[:2000]}

Generate a Phase 2 Strategic Report:
1. Executive Summary (3 sentences max)
2. Critical Issues (bugs, UX problems, accessibility)
3. Opportunities (missing features, improvements)
4. Priority Recommendations (ranked by impact)
5. Concrete Next Steps

Return ONLY valid JSON:
{{
    "executive_summary": "...",
    "critical_issues": ["issue 1", "issue 2"],
    "opportunities": ["opportunity 1", "opportunity 2"],
    "recommendations": [
        {{"priority": 1, "action": "...", "impact": "high", "effort": "low"}}
    ],
    "next_steps": ["step 1", "step 2"]
}}"""

        message = HumanMessage(content=prompt)
        response = await self.llm.ainvoke([message])
        cleaned = _clean_llm_json(response.content)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "executive_summary": "Audit complete. Manual review recommended.",
                "critical_issues": [],
                "opportunities": [],
                "recommendations": [],
                "next_steps": ["Review raw audit data manually"],
            }
