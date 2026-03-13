"""
Module 4: E2E Workflow Detector + Exhaustive Test Plan Generator
- Detects all user journeys across multi-page flows
- Generates industry-standard test plans (IEEE 829 / GfG aligned)
- Exports Xray-compatible CSV for Jira Test Case Importer
"""

import csv
import io
import json
from datetime import datetime
from typing import Dict, List

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama


def _clean_llm_json(content: str) -> str:
    """Strip <think> tags and markdown fences from LLM output."""
    if "<think>" in content:
        content = content.split("</think>")[-1]
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        parts = content.split("```")
        if len(parts) >= 3:
            content = parts[1]
    return content.strip()


class WorkflowDetector:
    def __init__(self):
        self.llm = ChatOllama(model="deepseek-r1:7b", temperature=0)

    async def detect_workflows(self, sitemap_summary: Dict) -> Dict:
        """Detect all E2E user workflows from the sitemap structure."""

        prompt = f"""You are a Senior QA Engineer analyzing a website to identify ALL End-to-End user workflows.

Site Structure:
{json.dumps(sitemap_summary, indent=2)[:4000]}

Identify every possible user journey. For each workflow:
1. Name (e.g., "User Registration Flow")
2. Steps (page-by-page sequence with actions)
3. Priority (critical/high/medium/low)
4. Entry point (URL or button)
5. Expected final outcome
6. Pre-conditions required
7. Post-conditions to verify

Return ONLY valid JSON:
{{
    "workflows": [
        {{
            "name": "...",
            "priority": "high",
            "entry_point": "url or button",
            "pre_conditions": ["user must be on homepage"],
            "steps": [
                {{"page": "url", "action": "description", "data": "test data if any", "assertion": "expected result"}}
            ],
            "expected_outcome": "...",
            "post_conditions": ["state after completion"]
        }}
    ]
}}"""

        message = HumanMessage(content=prompt)
        response = await self.llm.ainvoke([message])
        cleaned = _clean_llm_json(response.content)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "workflows": [
                    {
                        "name": "Full Site Navigation",
                        "priority": "high",
                        "entry_point": sitemap_summary.get("root_url", "/"),
                        "pre_conditions": ["Browser open", "Internet connection"],
                        "steps": [
                            {
                                "page": p.get("url", ""),
                                "action": "Load and verify page renders",
                                "data": "",
                                "assertion": f"Page title: {p.get('title', 'loads')}",
                            }
                            for p in sitemap_summary.get("pages", [])[:10]
                        ],
                        "expected_outcome": "All pages load correctly",
                        "post_conditions": ["All pages accessible"],
                    }
                ]
            }

    async def generate_test_plan(
        self, sitemap_summary: Dict, semantic_data: List[Dict], workflows: Dict
    ) -> Dict:
        """Generate exhaustive functional test plan aligned with IEEE 829 / industry standards."""

        pages = sitemap_summary.get("pages", [])
        page_count = len(pages)

        # Build semantic highlights outside f-string
        semantic_highlights = json.dumps(
            [
                {
                    "url": s.get("url", ""),
                    "visual": str(s.get("visual", ""))[:150],
                    "textual": str(s.get("textual", ""))[:150],
                }
                for s in semantic_data[:5]
            ],
            indent=2,
        )[:2000]

        workflow_summary = json.dumps(
            [
                {
                    "name": w.get("name", ""),
                    "priority": w.get("priority", ""),
                    "steps_count": len(w.get("steps", [])),
                }
                for w in workflows.get("workflows", [])
            ],
            indent=2,
        )[:1000]

        prompt = f"""You are a Senior QA Lead creating an EXHAUSTIVE functional test plan following industry standards (IEEE 829).

Site: {sitemap_summary.get('root_url', 'unknown')} ({page_count} pages)

Site Map:
{json.dumps(sitemap_summary, indent=2)[:2500]}

Semantic Analysis:
{semantic_highlights}

Detected Workflows:
{workflow_summary}

Generate a COMPREHENSIVE test plan. For EACH page, generate AT MINIMUM:
- 1 page load test
- 1 navigation test per outbound link
- 1 test per form (if any)
- 1 test per button (if any)
- 1 visual/layout test  
- 1 content test
- 1 accessibility test

Also generate cross-page flow tests for each workflow.

Each test MUST have:
- id: unique ID like "TC-PL-001" (PL=Page Load, NV=Navigation, FM=Form, BT=Button, VL=Visual, CT=Content, AX=Accessibility, XP=Cross-Page)
- summary: one-line description
- description: detailed test description
- page: the URL being tested  
- pre_conditions: what must be true before test
- steps: array of step objects with action, data, expected_result
- priority: critical/high/medium/low
- severity: blocker/critical/major/minor/trivial
- test_type: functional/visual/performance/accessibility/security
- expected_result: overall expected outcome
- labels: array of tags

Return ONLY valid JSON:
{{
    "test_plan": {{
        "name": "Functional Test Plan",
        "version": "1.0",
        "created": "{datetime.now().strftime('%Y-%m-%d')}",
        "objective": "...",
        "scope": {{
            "in_scope": ["..."],
            "out_of_scope": ["..."]
        }},
        "testing_methodology": ["Functional", "Visual", "Accessibility"],
        "entry_criteria": ["..."],
        "exit_criteria": ["..."],
        "risks": [
            {{"risk": "...", "impact": "high", "mitigation": "..."}}
        ],
        "test_environment": {{
            "browsers": ["Chrome", "Firefox", "Safari"],
            "devices": ["Desktop 1920x1080", "Mobile 375x812"],
            "tools": ["Playwright", "Lighthouse"]
        }},
        "total_tests": 0,
        "categories": [
            {{
                "name": "Page Load",
                "tests": [
                    {{
                        "id": "TC-PL-001",
                        "summary": "Verify homepage loads",
                        "description": "Navigate to homepage and verify it loads within 3 seconds",
                        "page": "https://example.com",
                        "pre_conditions": ["Browser is open", "Network is available"],
                        "steps": [
                            {{"action": "Navigate to URL", "data": "https://example.com", "expected_result": "Page loads successfully"}}
                        ],
                        "priority": "critical",
                        "severity": "blocker",
                        "test_type": "functional",
                        "expected_result": "Page loads within 3s with HTTP 200",
                        "labels": ["smoke", "regression"]
                    }}
                ]
            }}
        ]
    }}
}}"""

        message = HumanMessage(content=prompt)
        response = await self.llm.ainvoke([message])
        cleaned = _clean_llm_json(response.content)

        try:
            result = json.loads(cleaned)
            if "test_plan" in result:
                total = sum(
                    len(cat.get("tests", []))
                    for cat in result["test_plan"].get("categories", [])
                )
                result["test_plan"]["total_tests"] = total

                # Ensure all required fields exist
                tp = result["test_plan"]
                tp.setdefault("name", f"Test Plan - {sitemap_summary.get('root_url', 'Site')}")
                tp.setdefault("version", "1.0")
                tp.setdefault("created", datetime.now().strftime("%Y-%m-%d"))
                tp.setdefault("objective", "Verify all functional and visual aspects of the site")
                tp.setdefault("scope", {"in_scope": [], "out_of_scope": []})
                tp.setdefault("testing_methodology", ["Functional", "Visual", "Accessibility"])
                tp.setdefault("entry_criteria", [
                    "Application deployed and accessible",
                    "Test environment configured",
                    "Test data prepared",
                ])
                tp.setdefault("exit_criteria", [
                    "All critical/high priority tests pass",
                    "No blocker/critical defects remain open",
                    "Test coverage >= 90%",
                    "All P1 workflows verified",
                ])
                tp.setdefault("risks", [])
                tp.setdefault("test_environment", {
                    "browsers": ["Chrome", "Firefox", "Safari"],
                    "devices": ["Desktop 1920x1080", "Tablet 768x1024", "Mobile 375x812"],
                    "tools": ["Playwright", "Lighthouse", "axe-core"],
                })
            return result
        except json.JSONDecodeError:
            # Fallback: generate structured tests programmatically
            return self._generate_fallback_plan(sitemap_summary, workflows)

    def _generate_fallback_plan(self, sitemap_summary: Dict, workflows: Dict) -> Dict:
        """Generate a structured test plan programmatically when LLM fails."""
        pages = sitemap_summary.get("pages", [])
        root_url = sitemap_summary.get("root_url", "unknown")
        categories = []
        test_id = 1

        # ── Page Load Tests ──
        pl_tests = []
        for pg in pages:
            pl_tests.append({
                "id": f"TC-PL-{test_id:03d}",
                "summary": f"Verify page loads: {pg.get('title', pg.get('url', ''))}",
                "description": f"Navigate to {pg.get('url', '')} and verify HTTP 200, page renders, title matches",
                "page": pg.get("url", ""),
                "pre_conditions": ["Browser open", "Network available"],
                "steps": [
                    {"action": "Navigate to URL", "data": pg.get("url", ""), "expected_result": "Page loads with HTTP 200"},
                    {"action": "Verify page title", "data": "", "expected_result": f"Title is '{pg.get('title', '')}'"},
                    {"action": "Check for console errors", "data": "", "expected_result": "No JS errors in console"},
                ],
                "priority": "critical",
                "severity": "blocker",
                "test_type": "functional",
                "expected_result": "Page loads correctly within 3 seconds",
                "labels": ["smoke", "regression", "page-load"],
            })
            test_id += 1
        categories.append({"name": "Page Load", "tests": pl_tests})

        # ── Navigation Tests ──
        nv_tests = []
        for pg in pages:
            for link in pg.get("links", [])[:10]:
                href = link.get("href", "")
                if not href or href.startswith("#") or href.startswith("javascript"):
                    continue
                nv_tests.append({
                    "id": f"TC-NV-{test_id:03d}",
                    "summary": f"Verify link: {link.get('text', href)[:50]}",
                    "description": f"Click link '{link.get('text', '')}' on {pg.get('url', '')} and verify destination loads",
                    "page": pg.get("url", ""),
                    "pre_conditions": [f"User is on {pg.get('url', '')}"],
                    "steps": [
                        {"action": f"Click link '{link.get('text', 'Link')}'", "data": href, "expected_result": "Navigation occurs"},
                        {"action": "Verify destination page loads", "data": "", "expected_result": "No 404 error"},
                    ],
                    "priority": "high",
                    "severity": "major",
                    "test_type": "functional",
                    "expected_result": f"Navigates to {href} successfully",
                    "labels": ["navigation", "regression"],
                })
                test_id += 1
        categories.append({"name": "Navigation", "tests": nv_tests})

        # ── Form Tests ──
        fm_tests = []
        for pg in pages:
            for form in pg.get("forms", []):
                inputs = form.get("inputs", [])
                steps = [{"action": f"Navigate to {pg.get('url', '')}", "data": "", "expected_result": "Page loads"}]
                for inp in inputs:
                    steps.append({
                        "action": f"Fill {inp.get('type', 'input')} field '{inp.get('name', '')}'",
                        "data": f"Test data for {inp.get('name', 'field')}",
                        "expected_result": "Field accepts input",
                    })
                steps.append({"action": "Submit form", "data": "", "expected_result": "Form submits successfully"})

                fm_tests.append({
                    "id": f"TC-FM-{test_id:03d}",
                    "summary": f"Verify form submission on {pg.get('title', pg.get('url', ''))}",
                    "description": f"Fill and submit form (action={form.get('action', '')}, method={form.get('method', 'GET')})",
                    "page": pg.get("url", ""),
                    "pre_conditions": [f"User is on {pg.get('url', '')}"],
                    "steps": steps,
                    "priority": "critical",
                    "severity": "critical",
                    "test_type": "functional",
                    "expected_result": "Form submits with success confirmation",
                    "labels": ["form", "regression", "critical-path"],
                })
                test_id += 1

                # Validation test
                fm_tests.append({
                    "id": f"TC-FM-{test_id:03d}",
                    "summary": f"Verify form validation on {pg.get('title', pg.get('url', ''))}",
                    "description": "Submit form with empty/invalid data and verify validation messages",
                    "page": pg.get("url", ""),
                    "pre_conditions": [f"User is on {pg.get('url', '')}"],
                    "steps": [
                        {"action": "Leave all required fields empty", "data": "", "expected_result": "Fields remain empty"},
                        {"action": "Click submit", "data": "", "expected_result": "Validation errors shown"},
                    ],
                    "priority": "high",
                    "severity": "major",
                    "test_type": "functional",
                    "expected_result": "Appropriate validation messages displayed",
                    "labels": ["form", "validation", "negative"],
                })
                test_id += 1
        categories.append({"name": "Form", "tests": fm_tests})

        # ── Button Tests ──
        bt_tests = []
        for pg in pages:
            for btn in pg.get("buttons", []):
                bt_tests.append({
                    "id": f"TC-BT-{test_id:03d}",
                    "summary": f"Verify button: {btn.get('text', 'Button')[:40]}",
                    "description": f"Click button '{btn.get('text', '')}' on {pg.get('url', '')} and verify action",
                    "page": pg.get("url", ""),
                    "pre_conditions": [f"User is on {pg.get('url', '')}"],
                    "steps": [
                        {"action": f"Locate button '{btn.get('text', 'Button')}'", "data": "", "expected_result": "Button is visible"},
                        {"action": "Click button", "data": "", "expected_result": "Expected action triggered"},
                    ],
                    "priority": "high",
                    "severity": "major",
                    "test_type": "functional",
                    "expected_result": "Button triggers expected behavior",
                    "labels": ["button", "interaction"],
                })
                test_id += 1
        categories.append({"name": "Button", "tests": bt_tests})

        # ── Visual Tests ──
        vl_tests = []
        for pg in pages:
            vl_tests.append({
                "id": f"TC-VL-{test_id:03d}",
                "summary": f"Visual regression: {pg.get('title', pg.get('url', ''))}",
                "description": f"Verify layout, fonts, colors, images render correctly on {pg.get('url', '')}",
                "page": pg.get("url", ""),
                "pre_conditions": ["Browser at 1920x1080"],
                "steps": [
                    {"action": "Navigate to page", "data": pg.get("url", ""), "expected_result": "Page renders"},
                    {"action": "Verify all images load", "data": "", "expected_result": "No broken images"},
                    {"action": "Verify text is readable", "data": "", "expected_result": "Fonts render correctly"},
                    {"action": "Check responsive at 375px", "data": "", "expected_result": "No horizontal scroll"},
                ],
                "priority": "medium",
                "severity": "minor",
                "test_type": "visual",
                "expected_result": "Page matches design specifications",
                "labels": ["visual", "responsive", "regression"],
            })
            test_id += 1
        categories.append({"name": "Visual", "tests": vl_tests})

        # ── Content Tests ──
        ct_tests = []
        for pg in pages:
            ct_tests.append({
                "id": f"TC-CT-{test_id:03d}",
                "summary": f"Content verification: {pg.get('title', pg.get('url', ''))}",
                "description": f"Verify text content, meta tags, SEO elements on {pg.get('url', '')}",
                "page": pg.get("url", ""),
                "pre_conditions": [f"User is on {pg.get('url', '')}"],
                "steps": [
                    {"action": "Check page title tag", "data": "", "expected_result": "Title is set and descriptive"},
                    {"action": "Check meta description", "data": "", "expected_result": "Meta description present"},
                    {"action": "Check H1 heading", "data": "", "expected_result": "Single H1 present"},
                    {"action": "Verify OG tags", "data": "", "expected_result": "og:title, og:description, og:image set"},
                    {"action": "Check for broken images", "data": "", "expected_result": "All images have valid src and alt"},
                ],
                "priority": "medium",
                "severity": "minor",
                "test_type": "functional",
                "expected_result": "Content is accurate and SEO-optimized",
                "labels": ["content", "seo"],
            })
            test_id += 1
        categories.append({"name": "Content", "tests": ct_tests})

        # ── Accessibility Tests ──
        ax_tests = []
        for pg in pages:
            ax_tests.append({
                "id": f"TC-AX-{test_id:03d}",
                "summary": f"Accessibility audit: {pg.get('title', pg.get('url', ''))}",
                "description": f"Run accessibility audit on {pg.get('url', '')} (WCAG 2.1 AA)",
                "page": pg.get("url", ""),
                "pre_conditions": ["axe-core or Lighthouse available"],
                "steps": [
                    {"action": "Run Lighthouse accessibility audit", "data": pg.get("url", ""), "expected_result": "Score >= 80"},
                    {"action": "Check color contrast ratios", "data": "", "expected_result": "Meets WCAG AA (4.5:1)"},
                    {"action": "Verify keyboard navigation", "data": "", "expected_result": "All interactive elements focusable"},
                    {"action": "Check ARIA labels", "data": "", "expected_result": "All buttons/links have accessible names"},
                    {"action": "Verify alt text on images", "data": "", "expected_result": "All images have alt attributes"},
                ],
                "priority": "medium",
                "severity": "major",
                "test_type": "accessibility",
                "expected_result": "Page meets WCAG 2.1 AA standards",
                "labels": ["accessibility", "wcag", "a11y"],
            })
            test_id += 1
        categories.append({"name": "Accessibility", "tests": ax_tests})

        # ── Cross-Page / Workflow Tests ──
        xp_tests = []
        for wf in workflows.get("workflows", []):
            steps = []
            for step in wf.get("steps", []):
                steps.append({
                    "action": step.get("action", "Perform action"),
                    "data": step.get("data", ""),
                    "expected_result": step.get("assertion", "Step completes"),
                })
            xp_tests.append({
                "id": f"TC-XP-{test_id:03d}",
                "summary": f"E2E Flow: {wf.get('name', 'Workflow')}",
                "description": f"Execute complete workflow: {wf.get('name', '')}",
                "page": wf.get("entry_point", root_url),
                "pre_conditions": wf.get("pre_conditions", ["User on homepage"]),
                "steps": steps,
                "priority": wf.get("priority", "high"),
                "severity": "critical" if wf.get("priority") == "critical" else "major",
                "test_type": "functional",
                "expected_result": wf.get("expected_outcome", "Workflow completes successfully"),
                "labels": ["e2e", "workflow", "cross-page"],
            })
            test_id += 1
        categories.append({"name": "Cross-Page", "tests": xp_tests})

        total = sum(len(cat["tests"]) for cat in categories)

        return {
            "test_plan": {
                "name": f"Functional Test Plan - {root_url}",
                "version": "1.0",
                "created": datetime.now().strftime("%Y-%m-%d"),
                "objective": f"Verify all functional, visual, and accessibility aspects of {root_url}",
                "scope": {
                    "in_scope": [
                        f"All {len(pages)} discovered pages",
                        "All forms and interactive elements",
                        "Navigation and link integrity",
                        "Visual regression across viewports",
                        "Content and SEO verification",
                        "WCAG 2.1 AA accessibility",
                        "Cross-page user workflows",
                    ],
                    "out_of_scope": [
                        "Server-side performance testing",
                        "Database integrity testing",
                        "Third-party API availability",
                        "Load/stress testing",
                    ],
                },
                "testing_methodology": [
                    "Functional Testing",
                    "Visual Regression Testing",
                    "Accessibility Testing (WCAG 2.1 AA)",
                    "Smoke Testing",
                    "End-to-End Testing",
                ],
                "entry_criteria": [
                    "Application deployed and accessible via URL",
                    "Test environment configured (Playwright + Chromium)",
                    "All pages reachable (no deployment errors)",
                    "Test data prepared",
                ],
                "exit_criteria": [
                    "All critical/high priority tests pass (100%)",
                    "Medium priority tests pass (>= 90%)",
                    "No blocker/critical defects remain open",
                    "All P1 workflows verified end-to-end",
                    "Accessibility score >= 80 on all pages",
                ],
                "risks": [
                    {"risk": "Dynamic content changes between test runs", "impact": "medium", "mitigation": "Use stable selectors and data-testid attributes"},
                    {"risk": "Third-party widgets blocking page load", "impact": "high", "mitigation": "Set timeout thresholds and retry logic"},
                    {"risk": "Responsive layout breaks on specific viewports", "impact": "medium", "mitigation": "Test across 3 viewport sizes minimum"},
                ],
                "test_environment": {
                    "browsers": ["Chrome (latest)", "Firefox (latest)", "Safari (latest)"],
                    "devices": ["Desktop 1920x1080", "Tablet 768x1024", "Mobile 375x812"],
                    "tools": ["Playwright", "Lighthouse", "axe-core"],
                },
                "total_tests": total,
                "categories": categories,
            }
        }

    def export_xray_csv(self, test_plan: Dict) -> str:
        """Export test plan as Xray-compatible CSV for Jira Test Case Importer."""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)

        # Xray CSV headers
        writer.writerow([
            "TCID", "Test Summary", "Description", "Priority",
            "Action", "Data", "Expected Result",
            "Labels", "Test Repository Path",
        ])

        tp = test_plan.get("test_plan", {})
        for category in tp.get("categories", []):
            cat_name = category.get("name", "General")
            for test in category.get("tests", []):
                tc_id = test.get("id", "TC-000")
                summary = test.get("summary", "")
                description = test.get("description", "")
                priority = test.get("priority", "medium").capitalize()
                labels = " ".join(test.get("labels", []))
                repo_path = f"Deep Audit/{cat_name}"

                steps = test.get("steps", [])
                if not steps:
                    # Single row with no steps
                    writer.writerow([
                        tc_id, summary, description, priority,
                        "", "", test.get("expected_result", ""),
                        labels, repo_path,
                    ])
                else:
                    for i, step in enumerate(steps):
                        writer.writerow([
                            tc_id,
                            summary if i == 0 else "",
                            description if i == 0 else "",
                            priority if i == 0 else "",
                            step.get("action", ""),
                            step.get("data", ""),
                            step.get("expected_result", ""),
                            labels if i == 0 else "",
                            repo_path if i == 0 else "",
                        ])

        return output.getvalue()
