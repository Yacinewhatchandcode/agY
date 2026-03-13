"""
Deep Audit Pipeline — Sovereign Orchestrator
Chains: Crawler → Semantic → Workflows → Tests → Strategy
Emits real-time progress via WebSocket callback.
"""

import json
from typing import Callable, Optional

from agents.site_crawler import SiteCrawler
from agents.semantic_analyzer import SemanticAnalyzer
from agents.workflow_detector import WorkflowDetector
from agents.strategy_agent import StrategyAgent


class DeepAuditPipeline:
    def __init__(self, max_depth: int = 2, max_pages: int = 15):
        self.crawler = SiteCrawler(max_depth=max_depth, max_pages=max_pages)
        self.semantic = SemanticAnalyzer()
        self.workflow = WorkflowDetector()
        self.strategy = StrategyAgent()
        self.emit: Optional[Callable] = None

    async def run(self, url: str, emit: Optional[Callable] = None) -> dict:
        """Execute the full 5-phase deep audit pipeline."""
        self.emit = emit

        # ═══════════════════════════════════════════
        #  PHASE 1 : SITE CRAWL
        # ═══════════════════════════════════════════
        await self._emit("═══ PHASE 1/5 : SITE CRAWL ═══", "phase")
        sitemap = await self.crawler.crawl(url, emit=self._emit)

        sitemap_summary = self._build_summary(sitemap)
        await self._emit(
            f"Crawl: {len(sitemap.pages)} pages | "
            f"{sitemap.total_links} links | "
            f"{sitemap.total_buttons} buttons | "
            f"{sitemap.total_forms} forms | "
            f"{sitemap.total_images} images | "
            f"{sitemap.crawl_time:.1f}s",
            "info",
        )

        # ═══════════════════════════════════════════
        #  PHASE 2 : SEMANTIC ANALYSIS
        # ═══════════════════════════════════════════
        await self._emit("═══ PHASE 2/5 : SEMANTIC ANALYSIS ═══", "phase")
        semantic_results = []

        for i, page in enumerate(sitemap.pages):
            await self._emit(
                f"🔬 [{i+1}/{len(sitemap.pages)}] Analyzing: {page.title or page.url}"
            )
            try:
                analysis = await self.semantic.analyze_page(
                    page.screenshot_b64, page.text_content, page.meta
                )
                semantic_results.append(
                    {"url": page.url, "title": page.title, **analysis}
                )
            except Exception as e:
                await self._emit(
                    f"⚠️ Semantic error on {page.url}: {str(e)[:100]}", "warning"
                )
                semantic_results.append(
                    {
                        "url": page.url,
                        "title": page.title,
                        "visual": f"Error: {str(e)[:80]}",
                        "textual": "Analysis failed",
                    }
                )

        await self._emit(
            f"Semantic: {len(semantic_results)} pages analyzed", "info"
        )

        # ═══════════════════════════════════════════
        #  PHASE 3 : E2E WORKFLOW DETECTION
        # ═══════════════════════════════════════════
        await self._emit("═══ PHASE 3/5 : E2E WORKFLOW DETECTION ═══", "phase")
        workflows = await self.workflow.detect_workflows(sitemap_summary)
        wf_count = len(workflows.get("workflows", []))
        await self._emit(f"Workflows: {wf_count} user journeys detected", "info")

        for wf in workflows.get("workflows", []):
            await self._emit(
                f"  → [{wf.get('priority','?').upper()}] {wf.get('name','?')} "
                f"({len(wf.get('steps',[]))} steps)",
                "info",
            )

        # ═══════════════════════════════════════════
        #  PHASE 4 : TEST PLAN GENERATION
        # ═══════════════════════════════════════════
        await self._emit("═══ PHASE 4/5 : TEST PLAN GENERATION ═══", "phase")
        test_plan = await self.workflow.generate_test_plan(
            sitemap_summary, semantic_results, workflows
        )
        tp = test_plan.get("test_plan", {})
        total_tests = tp.get("total_tests", 0)
        await self._emit(f"Tests: {total_tests} functional tests generated", "info")

        for cat in tp.get("categories", []):
            await self._emit(
                f"  → {cat.get('name','?')}: {len(cat.get('tests',[]))} tests",
                "info",
            )

        # Plan metadata
        await self._emit(f"Scope: {len(tp.get('scope',{}).get('in_scope',[]))} in-scope areas", "info")
        await self._emit(f"Entry criteria: {len(tp.get('entry_criteria',[]))} conditions", "info")
        await self._emit(f"Exit criteria: {len(tp.get('exit_criteria',[]))} conditions", "info")
        await self._emit(f"Risks: {len(tp.get('risks',[]))} identified", "info")

        # Generate Xray CSV
        xray_csv = self.workflow.export_xray_csv(test_plan)
        await self._emit(f"📄 Xray CSV export: {len(xray_csv)} bytes ready", "info")

        # ═══════════════════════════════════════════
        #  PHASE 5 : PHASE 2 STRATEGY
        # ═══════════════════════════════════════════
        await self._emit("═══ PHASE 5/5 : STRATEGIC DIRECTION ═══", "phase")

        audit_data = {
            "pages_crawled": len(sitemap.pages),
            "total_links": sitemap.total_links,
            "total_forms": sitemap.total_forms,
            "total_buttons": sitemap.total_buttons,
            "workflows": workflows.get("workflows", []),
            "total_tests": total_tests,
            "semantic_highlights": [
                {
                    "url": s["url"],
                    "visual_summary": str(s.get("visual", ""))[:200],
                    "text_summary": str(s.get("textual", ""))[:200],
                }
                for s in semantic_results
            ],
        }

        strategy_report = await self.strategy.generate_strategy(audit_data)

        await self._emit(
            f"Strategy: {strategy_report.get('executive_summary', 'Complete')}",
            "info",
        )

        # ═══════════════════════════════════════════
        #  FINAL REPORT
        # ═══════════════════════════════════════════
        await self._emit("✅ DEEP AUDIT COMPLETE", "completed")

        return {
            "sitemap": sitemap_summary,
            "semantic": semantic_results,
            "workflows": workflows,
            "test_plan": test_plan,
            "strategy": strategy_report,
            "xray_csv": xray_csv,
        }

    def _build_summary(self, sitemap) -> dict:
        """Build JSON-serializable summary (no screenshots)."""
        return {
            "root_url": sitemap.root_url,
            "domain": sitemap.domain,
            "pages_crawled": len(sitemap.pages),
            "total_links": sitemap.total_links,
            "total_buttons": sitemap.total_buttons,
            "total_forms": sitemap.total_forms,
            "total_images": sitemap.total_images,
            "crawl_time": sitemap.crawl_time,
            "pages": [
                {
                    "url": p.url,
                    "title": p.title,
                    "depth": p.depth,
                    "headings": p.headings[:10],
                    "links_count": len(p.links),
                    "buttons_count": len(p.buttons),
                    "forms_count": len(p.forms),
                    "images_count": len(p.images),
                    "links": [
                        {"text": l.get("text", ""), "href": l.get("href", "")}
                        for l in p.links[:20]
                    ],
                    "buttons": [
                        {"text": b.get("text", ""), "type": b.get("type", "")}
                        for b in p.buttons[:10]
                    ],
                    "forms": p.forms[:5],
                    "images": [
                        {"src": img.get("src", ""), "alt": img.get("alt", "")}
                        for img in p.images[:15]
                    ],
                    "meta": p.meta,
                }
                for p in sitemap.pages
            ],
        }

    async def _emit(self, text: str, status: str = "active"):
        if self.emit:
            await self.emit(text, status)
        print(f"🔬 [{status.upper()}] {text}")
