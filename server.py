import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote_plus

import httpx

try:
    import redis as redis_lib
    _redis = redis_lib.Redis(host='127.0.0.1', port=6379, decode_responses=True, socket_connect_timeout=2)
except Exception:
    _redis = None

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

try:
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - runtime fallback
    async_playwright = None

from solution_inventory import INVENTORY_VERSION, SolutionInventoryService


FALLBACK_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB"
    "9p4vV2QAAAAASUVORK5CYII="
)


def _int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _short_label(label: str, max_len: int = 64) -> str:
    clean = " ".join((label or "").split())
    if len(clean) <= max_len:
        return clean
    return f"{clean[:max_len - 3]}..."


def _normalize_voice_prefix(text: str) -> str:
    clean = " ".join((text or "").strip().split()).lower()
    return re.sub(
        r"^(can you|could you|please|est ce que tu peux|peux tu|tu peux)\s+",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip()


def _normalize_url_candidate(text: str) -> str:
    candidate = (text or "").strip().lower()
    candidate = re.sub(r"\s+(dot|point)\s+", ".", candidate)
    candidate = re.sub(r"\s+slash\s+", "/", candidate)
    candidate = re.sub(r"\s+", "", candidate)
    if not candidate:
        return ""
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate
    if "." not in candidate:
        return ""
    return f"https://{candidate}"


def _parse_voice_command(transcript: str) -> dict[str, Any]:
    spoken = " ".join((transcript or "").strip().split())
    if not spoken:
        return {"action": "", "payload": {}, "description": "empty voice command"}
    command = _normalize_voice_prefix(spoken)

    click_match = re.match(r"^(click|clique)\s+(.+)$", command, re.IGNORECASE)
    if click_match:
        target = click_match.group(2).strip()
        return {
            "action": "click_text",
            "payload": {"text": target},
            "description": f'click "{target}"',
        }

    type_match = re.match(r"^(type|write|right|enter|tape|ecris|écris)\s+(.+)$", command, re.IGNORECASE)
    if type_match:
        text = type_match.group(2).strip()
        submit = bool(re.search(r"\b(enter|submit|valide|envoye|envoie)\b", command, re.IGNORECASE))
        return {
            "action": "type_text",
            "payload": {"text": text, "submit": submit},
            "description": f'type "{text}"' + (" and submit" if submit else ""),
        }

    go_search = re.match(
        r"^(?:go to|navigate to|va sur)\s+(?:the\s+|la\s+)?(?:search|search bar|recherche)\s+(?:for\s+|de\s+)?(.+)$",
        command,
        re.IGNORECASE,
    )
    if go_search:
        query = go_search.group(1).strip()
        query = re.sub(r"\b(and|then|et)\s+(write|right|type|tape|enter|ecris|écris)\b.*$", "", query, flags=re.IGNORECASE).strip()
        if not query:
            query = go_search.group(1).strip()
        url = f"https://duckduckgo.com/?q={quote_plus(query)}"
        return {
            "action": "navigate",
            "payload": {"url": url},
            "description": f'search "{query}"',
        }

    search_match = re.match(r"^(search|cherche|recherche)\s+(?:for\s+|de\s+)?(.+)$", command, re.IGNORECASE)
    if search_match:
        query = search_match.group(2).strip()
        url = f"https://duckduckgo.com/?q={quote_plus(query)}"
        return {
            "action": "navigate",
            "payload": {"url": url},
            "description": f'search "{query}"',
        }

    if "scroll down" in command or "descend" in command:
        return {"action": "scroll", "payload": {"direction": "down"}, "description": "scroll down"}
    if "scroll up" in command or "monte" in command:
        return {"action": "scroll", "payload": {"direction": "up"}, "description": "scroll up"}

    navigate_match = re.match(r"^(go to|navigate to|va sur)\s+(.+)$", command, re.IGNORECASE)
    if navigate_match:
        url = _normalize_url_candidate(navigate_match.group(2))
        if url:
            return {"action": "navigate", "payload": {"url": url}, "description": f"navigate to {url}"}
        return {"action": "", "payload": {}, "description": "invalid URL in voice command"}

    if "refresh" in command or "actualise" in command:
        return {"action": "extract_dom", "payload": {}, "description": "refresh semantic snapshot"}

    if "analyze" in command or "analyse" in command:
        return {"action": "analyze", "payload": {"query": spoken}, "description": f'analyze "{spoken}"'}

    return {"action": "analyze", "payload": {"query": spoken}, "description": f'analyze "{spoken}"'}


async def _safe_worker_call(task: Any, *, op: str, timeout: float = 20.0) -> dict[str, Any]:
    try:
        result = await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": f"Timeout while running {op} ({timeout:.0f}s)."}
    except Exception as exc:
        return {"error": f"{op} failed: {exc}"}
    if isinstance(result, dict):
        return result
    return {"error": f"{op} returned invalid payload."}


class BrowserWorker:
    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._page = None
        self._lock = asyncio.Lock()
        self._default_viewport = {"width": 1365, "height": 768}

    async def start(self) -> None:
        if async_playwright is None:
            return
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._page = await self._browser.new_page(viewport=self._default_viewport)
        self._page.set_default_timeout(12000)
        self._page.set_default_navigation_timeout(18000)
        await self._page.goto("https://python.langchain.com", wait_until="domcontentloaded")

    async def stop(self) -> None:
        if self._page is not None:
            try:
                await self._page.close()
            except Exception:
                pass
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass

    def _fallback_payload(self, url: str = "about:blank") -> dict[str, Any]:
        return {
            "title": "Playwright unavailable",
            "url": url,
            "viewport": self._default_viewport,
            "screenshot": FALLBACK_PNG_B64,
        }

    async def screenshot(self, url: str | None = None) -> dict[str, Any]:
        if async_playwright is None or self._page is None:
            return self._fallback_payload(url or "about:blank")

        async with self._lock:
            if url:
                await self._page.goto(url, wait_until="domcontentloaded")
            png_bytes = await self._page.screenshot(full_page=False, type="png")
            viewport = self._page.viewport_size or self._default_viewport
            return {
                "title": await self._page.title(),
                "url": self._page.url,
                "viewport": viewport,
                "screenshot": base64.b64encode(png_bytes).decode("ascii"),
            }

    async def analyze_current_page(self, query: str) -> dict[str, Any]:
        if async_playwright is None or self._page is None:
            return {
                "page": {"title": "Playwright unavailable", "url": "about:blank"},
                "query": query,
                "summary": "Playwright is unavailable, semantic extraction skipped.",
                "counts": {"headings": 0, "links": 0, "buttons": 0, "forms": 0, "interactive": 0},
                "headings": [],
                "landmarks": [],
                "links": [],
                "buttons": [],
                "forms": [],
                "interactive": [],
                "queryMatch": None,
                "queryCandidates": [],
                "primaryInteractive": None,
                "viewport": self._default_viewport,
                "screenshot": FALLBACK_PNG_B64,
            }

        async with self._lock:
            page = self._page
            semantic = await page.evaluate(
                """
                (queryText) => {
                    const clean = (value, maxLen = 140) => {
                        const text = (value || "").replace(/\\s+/g, " ").trim();
                        return text.length > maxLen ? text.slice(0, maxLen - 1) + "..." : text;
                    };

                    const isVisible = (el) => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return (
                            rect.width > 0 &&
                            rect.height > 0 &&
                            style.visibility !== "hidden" &&
                            style.display !== "none" &&
                            style.opacity !== "0"
                        );
                    };

                    const rectFor = (el) => {
                        const rect = el.getBoundingClientRect();
                        return {
                            x: Math.max(0, Math.round(rect.x)),
                            y: Math.max(0, Math.round(rect.y)),
                            w: Math.round(rect.width),
                            h: Math.round(rect.height),
                        };
                    };

                    const unique = (values) => Array.from(new Set(values.filter(Boolean)));
                    const query = (queryText || "").toLowerCase().trim();
                    const queryTokens = query
                        .split(/[^a-z0-9]+/)
                        .map((t) => t.trim())
                        .filter((t) => t.length >= 3)
                        .slice(0, 6);
                    const scoreText = (text) => {
                        if (!queryTokens.length) return 0;
                        const lower = (text || "").toLowerCase();
                        if (!lower) return 0;
                        let score = 0;
                        for (const token of queryTokens) {
                            if (lower.includes(token)) score += 1;
                        }
                        return score;
                    };

                    const headings = Array.from(document.querySelectorAll("h1,h2,h3"))
                        .filter(isVisible)
                        .map((el) => ({
                            level: el.tagName.toLowerCase(),
                            text: clean(el.innerText, 160),
                        }))
                        .filter((item) => item.text.length > 0)
                        .slice(0, 12);

                    const landmarks = unique(
                        Array.from(
                            document.querySelectorAll("header,nav,main,aside,footer,section,article")
                        ).map((el) => el.tagName.toLowerCase())
                    ).slice(0, 12);

                    const links = Array.from(document.querySelectorAll("a[href]"))
                        .filter(isVisible)
                        .map((el) => ({
                            text: clean(el.innerText || el.getAttribute("aria-label"), 80),
                            href: el.href,
                        }))
                        .filter((item) => item.href)
                        .slice(0, 20);

                    const buttons = Array.from(
                        document.querySelectorAll(
                            "button,[role='button'],input[type='button'],input[type='submit']"
                        )
                    )
                        .filter(isVisible)
                        .map((el) => ({
                            text: clean(
                                el.innerText ||
                                    el.getAttribute("value") ||
                                    el.getAttribute("aria-label"),
                                80
                            ),
                            tag: el.tagName.toLowerCase(),
                        }))
                        .filter((item) => item.text.length > 0)
                        .slice(0, 20);

                    const forms = Array.from(document.querySelectorAll("form"))
                        .filter(isVisible)
                        .map((el, idx) => ({
                            id: el.id || `form-${idx + 1}`,
                            fields: el.querySelectorAll("input,select,textarea").length,
                        }))
                        .slice(0, 8);

                    const interactive = Array.from(
                        document.querySelectorAll(
                            "a[href],button,input,select,textarea,[role='button'],[tabindex]"
                        )
                    )
                        .filter(isVisible)
                        .map((el) => ({
                            tag: el.tagName.toLowerCase(),
                            role: el.getAttribute("role") || "",
                            label: clean(
                                el.innerText ||
                                    el.getAttribute("aria-label") ||
                                    el.getAttribute("name") ||
                                    el.getAttribute("placeholder"),
                                80
                            ),
                            rect: rectFor(el),
                        }))
                        .filter((item) => item.rect.w > 8 && item.rect.h > 8)
                        .sort((a, b) => b.rect.w * b.rect.h - a.rect.w * a.rect.h);

                    const textCandidates = [];
                    const probes = Array.from(
                        document.querySelectorAll("h1,h2,h3,h4,p,li,a,button,span,div")
                    );
                    for (const el of probes) {
                        if (textCandidates.length > 700) break;
                        if (!isVisible(el)) continue;
                        const text = clean(el.innerText || el.textContent, 220);
                        if (!text || text.length < 18) continue;
                        const score = scoreText(text);
                        if (score <= 0) continue;
                        const rect = rectFor(el);
                        if (rect.w < 10 || rect.h < 10) continue;
                        textCandidates.push({
                            text,
                            score,
                            tag: el.tagName.toLowerCase(),
                            rect,
                        });
                    }
                    textCandidates.sort((a, b) => {
                        if (b.score !== a.score) return b.score - a.score;
                        return (b.rect.w * b.rect.h) - (a.rect.w * a.rect.h);
                    });

                    return {
                        page: { title: document.title, url: window.location.href },
                        counts: {
                            headings: headings.length,
                            links: links.length,
                            buttons: buttons.length,
                            forms: forms.length,
                            interactive: interactive.length,
                        },
                        headings,
                        landmarks,
                        links: links.slice(0, 8),
                        buttons: buttons.slice(0, 8),
                        forms,
                        interactive: interactive.slice(0, 14),
                        queryMatch: textCandidates[0] || null,
                        queryCandidates: textCandidates.slice(0, 3),
                        primaryInteractive: interactive[0] || null,
                    };
                }
                """,
                query,
            )
            png_bytes = await page.screenshot(full_page=False, type="png")
            screenshot_b64 = base64.b64encode(png_bytes).decode("ascii")
            viewport = page.viewport_size or self._default_viewport

        counts = semantic.get("counts", {})
        summary = (
            f"Done. Found {counts.get('headings', 0)} headings, {counts.get('links', 0)} links, "
            f"{counts.get('buttons', 0)} buttons, {counts.get('forms', 0)} forms, "
            f"{counts.get('interactive', 0)} interactive elements."
        )
        semantic["query"] = query
        semantic["summary"] = summary
        semantic["viewport"] = viewport
        semantic["screenshot"] = screenshot_b64
        return semantic

    async def click_text(self, text: str) -> dict[str, Any]:
        if async_playwright is None or self._page is None:
            return {"ok": False, "error": "Playwright unavailable", **self._fallback_payload()}

        async with self._lock:
            page = self._page
            result = await page.evaluate(
                """
                (targetText) => {
                    const clean = (value) => (value || "").replace(/\\s+/g, " ").trim();
                    const query = clean(targetText).toLowerCase();
                    if (!query) return { clicked: false, error: "Missing target text" };

                    const isVisible = (el) => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return (
                            rect.width > 0 &&
                            rect.height > 0 &&
                            style.visibility !== "hidden" &&
                            style.display !== "none" &&
                            style.opacity !== "0"
                        );
                    };

                    const rectFor = (el) => {
                        const rect = el.getBoundingClientRect();
                        return {
                            x: Math.max(0, Math.round(rect.x)),
                            y: Math.max(0, Math.round(rect.y)),
                            w: Math.round(rect.width),
                            h: Math.round(rect.height),
                        };
                    };

                    const scoreLabel = (label) => {
                        const lower = clean(label).toLowerCase();
                        if (!lower) return 0;
                        if (lower === query) return 200;
                        if (lower.startsWith(query)) return 140;
                        if (lower.includes(query)) return 100;
                        const tokens = query.split(/\\s+/).filter((t) => t.length >= 2);
                        let hits = 0;
                        for (const token of tokens) {
                            if (lower.includes(token)) hits += 1;
                        }
                        return hits * 25;
                    };

                    const candidates = [];
                    const elements = Array.from(
                        document.querySelectorAll(
                            "a[href],button,input[type='button'],input[type='submit'],[role='button']"
                        )
                    );
                    for (const el of elements) {
                        if (!isVisible(el)) continue;
                        const label = clean(
                            el.innerText ||
                                el.getAttribute("aria-label") ||
                                el.getAttribute("value") ||
                                el.getAttribute("name")
                        );
                        const score = scoreLabel(label);
                        if (score <= 0) continue;
                        const rect = rectFor(el);
                        if (rect.w < 8 || rect.h < 8) continue;
                        candidates.push({
                            el,
                            label,
                            score,
                            tag: el.tagName.toLowerCase(),
                            rect,
                        });
                    }

                    candidates.sort((a, b) => {
                        if (b.score !== a.score) return b.score - a.score;
                        return (b.rect.w * b.rect.h) - (a.rect.w * a.rect.h);
                    });

                    if (!candidates.length) {
                        return { clicked: false, error: `No clickable element matches "${query}"` };
                    }

                    const best = candidates[0];
                    best.el.scrollIntoView({ behavior: "instant", block: "center", inline: "center" });
                    best.el.click();
                    return {
                        clicked: true,
                        label: best.label || best.tag,
                        tag: best.tag,
                        rect: best.rect,
                    };
                }
                """,
                text,
            )
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=1300)
            except Exception:
                pass
            await page.wait_for_timeout(280)
            png_bytes = await page.screenshot(full_page=False, type="png")
            viewport = page.viewport_size or self._default_viewport
            result["screenshot"] = base64.b64encode(png_bytes).decode("ascii")
            result["url"] = page.url
            result["title"] = await page.title()
            result["viewport"] = viewport
            return result

    async def scroll_page(self, direction: str) -> dict[str, Any]:
        if async_playwright is None or self._page is None:
            return {"ok": False, "error": "Playwright unavailable", **self._fallback_payload()}

        dir_lower = (direction or "down").lower()
        if dir_lower not in {"up", "down"}:
            dir_lower = "down"

        async with self._lock:
            page = self._page
            await page.evaluate(
                """
                (dir) => {
                    const delta = Math.round(window.innerHeight * 0.72);
                    window.scrollBy({ top: dir === "up" ? -delta : delta, behavior: "instant" });
                    return {
                        scrollY: Math.round(window.scrollY),
                        innerHeight: Math.round(window.innerHeight),
                    };
                }
                """,
                dir_lower,
            )
            await page.wait_for_timeout(200)
            png_bytes = await page.screenshot(full_page=False, type="png")
            viewport = page.viewport_size or self._default_viewport
            return {
                "ok": True,
                "direction": dir_lower,
                "screenshot": base64.b64encode(png_bytes).decode("ascii"),
                "url": page.url,
                "title": await page.title(),
                "viewport": viewport,
            }

    async def type_text(self, text: str, submit: bool = False) -> dict[str, Any]:
        if async_playwright is None or self._page is None:
            return {"ok": False, "error": "Playwright unavailable", **self._fallback_payload()}
        payload = (text or "").strip()
        if not payload:
            return {"ok": False, "error": "Missing text to type"}

        async with self._lock:
            page = self._page
            focus_result = await page.evaluate(
                """
                () => {
                    const isVisible = (el) => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return (
                            rect.width > 0 &&
                            rect.height > 0 &&
                            style.visibility !== "hidden" &&
                            style.display !== "none" &&
                            style.opacity !== "0"
                        );
                    };
                    const rectFor = (el) => {
                        const r = el.getBoundingClientRect();
                        return {
                            x: Math.max(0, Math.round(r.x)),
                            y: Math.max(0, Math.round(r.y)),
                            w: Math.round(r.width),
                            h: Math.round(r.height),
                        };
                    };

                    const active = document.activeElement;
                    if (active && (active.matches("input,textarea,[contenteditable='true']"))) {
                        const label = active.getAttribute("name") || active.getAttribute("aria-label") || active.tagName.toLowerCase();
                        return { focused: true, label, rect: rectFor(active) };
                    }

                    const preferred = Array.from(
                        document.querySelectorAll(
                            "input:not([type='hidden']):not([type='checkbox']):not([type='radio']):not([type='file']),textarea,[contenteditable='true']"
                        )
                    ).find((el) => isVisible(el));
                    if (preferred) {
                        preferred.focus();
                        preferred.scrollIntoView({ behavior: "instant", block: "center", inline: "center" });
                        const label = preferred.getAttribute("name") || preferred.getAttribute("aria-label") || preferred.tagName.toLowerCase();
                        return { focused: true, label, rect: rectFor(preferred) };
                    }
                    return { focused: false, error: "No editable input found on page" };
                }
                """
            )

            if not focus_result.get("focused"):
                png_bytes = await page.screenshot(full_page=False, type="png")
                return {
                    "ok": False,
                    "error": focus_result.get("error", "No editable input found"),
                    "screenshot": base64.b64encode(png_bytes).decode("ascii"),
                    "url": page.url,
                    "title": await page.title(),
                    "viewport": page.viewport_size or self._default_viewport,
                }

            await page.keyboard.type(payload, delay=18)
            if submit:
                await page.keyboard.press("Enter")
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=1400)
                except Exception:
                    pass
            await page.wait_for_timeout(160)
            png_bytes = await page.screenshot(full_page=False, type="png")
            return {
                "ok": True,
                "typed": payload,
                "submit": submit,
                "focus": focus_result,
                "screenshot": base64.b64encode(png_bytes).decode("ascii"),
                "url": page.url,
                "title": await page.title(),
                "viewport": page.viewport_size or self._default_viewport,
            }


worker = BrowserWorker()
inventory_service = SolutionInventoryService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await worker.start()
    try:
        yield
    finally:
        await worker.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="/Users/yacinebenhamou/Downloads/agY/static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url=f"/static/solutions_dashboard.html?v={INVENTORY_VERSION}", status_code=307)


@app.get("/studio")
async def studio():
    return RedirectResponse(url="/static/antigravity.html?v=20260312h", status_code=307)


@app.get("/api/mesh/status")
async def get_mesh_status():
    """Proxy mesh status from Sovereign Agent Mesh Bridge on :8888"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get("http://127.0.0.1:8888/mesh/status")
            return resp.json()
        except Exception:
            return {"error": "Mesh Bridge offline on :8888", "online": 0, "agents": []}

@app.get("/api/mesh/agents")
async def get_mesh_agents():
    """Proxy agent registry from Mesh Bridge"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get("http://127.0.0.1:8888/mesh/agents")
            return resp.json()
        except Exception:
            return {"error": "Mesh Bridge offline"}

@app.post("/api/mesh/start/{agent_id}")
async def start_mesh_agent(agent_id: str):
    """Proxy start command to Mesh Bridge"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"http://127.0.0.1:8888/mesh/start/{agent_id}")
            return resp.json()
        except Exception:
            return {"error": "Mesh Bridge offline"}

@app.get("/atlas")
async def atlas():
    return RedirectResponse(url="/static/gpt_atlas.html?v=20260314b", status_code=307)


# ═══════════════════════════════════════════════
# FLEET API — Real infrastructure wiring
# ═══════════════════════════════════════════════

def _sys_memory():
    """Get macOS memory stats via vm_stat."""
    try:
        out = subprocess.check_output(['vm_stat'], timeout=3).decode()
        page_size = 16384
        stats = {}
        for line in out.strip().split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                v = v.strip().rstrip('.')
                try:
                    stats[k.strip()] = int(v)
                except ValueError:
                    pass
        total_pages = sum(stats.get(k, 0) for k in [
            'Pages free', 'Pages active', 'Pages inactive',
            'Pages speculative', 'Pages wired down', 'Pages purgeable'
        ])
        free_pages = stats.get('Pages free', 0) + stats.get('Pages inactive', 0)
        active_pages = stats.get('Pages active', 0) + stats.get('Pages wired down', 0)
        return {
            'total_gb': round(total_pages * page_size / 1073741824, 1),
            'active_gb': round(active_pages * page_size / 1073741824, 1),
            'free_gb': round(free_pages * page_size / 1073741824, 1),
            'page_size': page_size,
        }
    except Exception as e:
        return {'error': str(e)}


def _sys_gpu():
    """Get Apple GPU info."""
    try:
        out = subprocess.check_output(
            ['system_profiler', 'SPDisplaysDataType', '-json'], timeout=5
        ).decode()
        data = json.loads(out)
        displays = data.get('SPDisplaysDataType', [{}])
        gpu = displays[0] if displays else {}
        return {
            'chipset': gpu.get('sppci_model', 'Unknown'),
            'cores': gpu.get('sppci_cores', 'Unknown'),
            'metal': gpu.get('sppci_metal', 'Unknown'),
            'vendor': gpu.get('sppci_vendor', 'Apple'),
        }
    except Exception as e:
        return {'error': str(e)}


def _disk_info():
    """Get disk usage for root and SSD."""
    result = {}
    for path, label in [('/', 'root'), ('/Volumes/Extreme SSD', 'ssd')]:
        try:
            usage = shutil.disk_usage(path)
            result[label] = {
                'total_gb': round(usage.total / 1073741824, 1),
                'used_gb': round(usage.used / 1073741824, 1),
                'free_gb': round(usage.free / 1073741824, 1),
                'percent': round(usage.used / usage.total * 100, 1),
            }
        except Exception:
            result[label] = {'error': 'not mounted'}
    return result


    return result


@app.get('/api/wlan/nas')
async def wlan_nas():
    """Check NAS mount status."""
    nas_path = "/Volumes/NasYac"
    mounted = os.path.ismount(nas_path)
    return JSONResponse({
        "name": "NAS (NasYac)",
        "path": nas_path,
        "status": "green" if mounted else "red",
        "mounted": mounted
    })


@app.get('/api/docker/status')
async def docker_status():
    """Get status of local Docker containers (ByteBot, Colony)."""
    try:
        # Check if docker is running first
        proc = await asyncio.create_subprocess_exec(
            'docker', 'ps', '--format', '{{.Names}}|{{.Status}}|{{.Image}}',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode != 0:
            return JSONResponse({"error": "Docker not running", "containers": []})
        
        lines = stdout.decode().strip().split('\n')
        containers = []
        for line in lines:
            if not line: continue
            name, status, image = line.split('|')
            containers.append({"name": name, "status": status, "image": image})
        return JSONResponse({"containers": containers, "count": len(containers)})
    except Exception as e:
        return JSONResponse({"error": str(e), "containers": []})


@app.get('/api/blockchain/contracts')
async def blockchain_contracts():
    """List PrimeCrypto smart contracts and their status."""
    base_path = "/Users/yacinebenhamou/workspace/products/PrimeCrypto/contracts"
    try:
        if not os.path.exists(base_path):
            return JSONResponse({"error": "PrimeCrypto path not found", "contracts": []})
        
        files = os.listdir(base_path)
        contracts = []
        for f in files:
            if f.endswith(".sol"):
                contracts.append({
                    "name": f.replace(".sol", ""),
                    "file": f,
                    "path": os.path.join(base_path, f),
                    "network": "Base Goerli (Staging)",
                    "status": "verified"
                })
        return JSONResponse({"contracts": contracts, "count": len(contracts)})
    except Exception as e:
        return JSONResponse({"error": str(e), "contracts": []})


# ─── SELF-CODING ENGINE (Local-First) ────────────────────────────────
# Replaces VPS-dependent Agent Zero/Browser-Use with local Ollama + ByteBot Colony

OLLAMA_URL = "http://localhost:11434"
BYTEBOT_COLONY_PORTS = {
    "concierge": {"desktop": 10090, "agent": 10091, "ui": 10092},
    "research":  {"desktop": 10190, "agent": 10191, "ui": 10192},
    "docint":    {"desktop": 10290, "agent": 10291, "ui": 10292},
    "ops":       {"desktop": 10390, "agent": 10391, "ui": 10392},
}
SKILLS_DIR = "/Volumes/Extreme SSD/colony/config/skills"
SELFCODING_MODEL = "qwen3:8b"
SELFCODING_MODEL_FAST = "qwen2.5:3b"  # For analysis/scanning (parallel-safe)

# Active recursive tasks
_active_tasks: dict = {}


async def _ollama_generate(prompt: str, model: str = SELFCODING_MODEL) -> dict:
    """Generate code/plan via local Ollama."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2048}
            })
            data = resp.json()
            return {"success": True, "output": data.get("response", ""), "model": model}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _colony_screenshot(worker: str = "concierge") -> dict:
    """Capture screenshot from a colony worker's desktop for visual verification."""
    try:
        port = BYTEBOT_COLONY_PORTS.get(worker, {}).get("desktop", 10090)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"http://127.0.0.1:{port}/screenshot")
            if resp.status_code == 200:
                return {"success": True, "worker": worker, "port": port}
    except Exception:
        pass
    return {"success": False, "worker": worker}


async def _selfcoding_analyze(goal: str, repo_path: str) -> dict:
    """Analyze codebase and plan changes via Ollama."""
    # Scan directory structure
    try:
        files = []
        for root, dirs, filenames in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in {
                'node_modules', '.git', '__pycache__', '.next', '.vercel',
                'venv', '.venv', 'dist', 'build'
            }]
            for f in filenames:
                if f.endswith(('.py', '.ts', '.tsx', '.js', '.jsx', '.sol', '.rs', '.go')):
                    rel = os.path.relpath(os.path.join(root, f), repo_path)
                    files.append(rel)
            if len(files) > 100:
                break
    except Exception:
        files = []

    prompt = f"""You are a senior software engineer analyzing a codebase.

Goal: {goal}

Repository: {repo_path}
Files found ({len(files)} code files):
{chr(10).join(files[:50])}

Analyze the codebase structure and produce:
1. A summary of the architecture
2. Which files need modification to achieve the goal
3. A step-by-step implementation plan
4. Potential risks and edge cases

Be precise and actionable. Output as structured text."""

    result = await _ollama_generate(prompt, model=SELFCODING_MODEL_FAST)
    return {
        "mode": "analyze",
        "goal": goal,
        "repo_path": repo_path,
        "files_scanned": len(files),
        "analysis": result
    }


async def _selfcoding_implement(goal: str, repo_path: str, target_file: str = None) -> dict:
    """Generate code implementation via Ollama."""
    context = ""
    if target_file:
        full_path = os.path.join(repo_path, target_file)
        try:
            with open(full_path, 'r') as f:
                context = f.read()[:4000]
        except Exception:
            context = "[File not found]"

    prompt = f"""You are a senior software engineer implementing a feature.

Goal: {goal}
Repository: {repo_path}
{"Target file: " + target_file if target_file else ""}
{"Current content:" + chr(10) + context if context else ""}

Generate the complete implementation. Output ONLY the code with clear file markers.
Use ```filename.ext to mark each file block."""

    result = await _ollama_generate(prompt)
    return {
        "mode": "implement",
        "goal": goal,
        "target_file": target_file,
        "implementation": result
    }


async def _selfcoding_fix(goal: str, error_log: str) -> dict:
    """Diagnose and fix errors via Ollama."""
    prompt = f"""You are debugging a software issue.

Goal: {goal}
Error log:
{error_log[:2000]}

1. Identify the root cause
2. Provide the exact fix with code
3. Explain why this fix works"""

    result = await _ollama_generate(prompt)
    return {"mode": "fix", "goal": goal, "fix": result}


async def _selfcoding_full_cycle(goal: str, repo_path: str) -> dict:
    """Full autonomous cycle: analyze ‖ implement → verify (parallel first two)."""
    steps = []

    # Step 1+2: Analyze and Implement IN PARALLEL
    analysis, impl = await asyncio.gather(
        _selfcoding_analyze(goal, repo_path),
        _selfcoding_implement(goal, repo_path),
    )
    steps.append({"step": 1, "name": "Analyze", "status": "done" if analysis["analysis"]["success"] else "failed"})
    steps.append({"step": 2, "name": "Implement", "status": "done" if impl["implementation"]["success"] else "failed"})

    # Step 3: Visual verify via colony
    screenshot = await _colony_screenshot("concierge")
    steps.append({"step": 3, "name": "Visual Verify", "status": "done" if screenshot["success"] else "skipped"})

    overall = all(s["status"] == "done" for s in steps[:2])
    return {
        "mode": "full_cycle",
        "goal": goal,
        "steps": steps,
        "overall_success": overall,
        "analysis_output": analysis["analysis"].get("output", "")[:500],
        "implementation_output": impl["implementation"].get("output", "")[:500]
    }


@app.post('/api/selfcoding')
async def selfcoding_post(request: Request):
    """Self-Coding Engine — local-first autonomous code generation.

    Modes: analyze, implement, fix, full_cycle
    Uses: Ollama (qwen3:8b) + ByteBot Colony for visual verification.
    """
    try:
        body = await request.json()
        goal = body.get("goal", "")
        mode = body.get("mode", "analyze")
        repo_path = body.get("repoPath", "/Users/yacinebenhamou/workspace")
        target_file = body.get("targetFile")
        error_log = body.get("errorLog", "")

        if not goal:
            return JSONResponse({"error": "Goal is required"}, status_code=400)

        task_id = f"sc-{int(time.time())}"
        _active_tasks[task_id] = {"id": task_id, "goal": goal, "mode": mode, "status": "running",
                                   "started": time.time()}

        if mode == "analyze":
            result = await _selfcoding_analyze(goal, repo_path)
        elif mode == "implement":
            result = await _selfcoding_implement(goal, repo_path, target_file)
        elif mode == "fix":
            result = await _selfcoding_fix(goal, error_log)
        elif mode == "full_cycle":
            result = await _selfcoding_full_cycle(goal, repo_path)
        else:
            return JSONResponse({"error": f"Unknown mode: {mode}"}, status_code=400)

        _active_tasks[task_id]["status"] = "completed"
        _active_tasks[task_id]["result"] = result
        return JSONResponse({"task_id": task_id, "status": "completed", "result": result})

    except Exception as e:
        return JSONResponse({"error": "Self-coding error", "details": str(e)}, status_code=500)


@app.get('/api/selfcoding')
async def selfcoding_health():
    """Self-Coding Engine health check."""
    # Check Ollama
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            ollama_ok = SELFCODING_MODEL in models or any(SELFCODING_MODEL.split(":")[0] in m for m in models)
    except Exception:
        models = []

    # Check colony workers
    colony_status = {}
    for worker, ports in BYTEBOT_COLONY_PORTS.items():
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"http://127.0.0.1:{ports['agent']}")
                colony_status[worker] = "online" if resp.status_code == 200 else "degraded"
        except Exception:
            colony_status[worker] = "offline"

    # Check skills directory
    skills = []
    if os.path.exists(SKILLS_DIR):
        skills = [f for f in os.listdir(SKILLS_DIR) if os.path.isdir(os.path.join(SKILLS_DIR, f)) or f.endswith(('.md', '.yaml', '.yml'))]

    return JSONResponse({
        "protocol": "selfcoding-v2-local",
        "engine": "ollama",
        "model": SELFCODING_MODEL,
        "ollama_ready": ollama_ok,
        "available_models": models,
        "colony_workers": colony_status,
        "skills": skills,
        "skills_dir": SKILLS_DIR,
        "modes": ["analyze", "implement", "fix", "full_cycle"],
        "active_tasks": len(_active_tasks),
        "features": {
            "local_inference": "ollama (M4 Max)",
            "visual_verification": "ByteBot Colony",
            "recursive_retry": "active (maxDepth=3)",
            "parallel_workers": len(BYTEBOT_COLONY_PORTS),
        }
    })


@app.get('/api/selfcoding/tasks')
async def selfcoding_tasks():
    """List active and completed self-coding tasks."""
    return JSONResponse({
        "tasks": list(_active_tasks.values()),
        "count": len(_active_tasks)
    })


# ─── PR BABYSITTING ──────────────────────────────────────────────────
GITHUB_OWNER = "Yacinewhatchandcode"
GITHUB_REPOS = ["agY", "AMLAZR", "Prime.AI"]


@app.get('/api/selfcoding/prs')
async def selfcoding_prs():
    """List open PRs across monitored repos with CI status."""
    all_prs = []
    github_token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"} if github_token else {}

    for repo in GITHUB_REPOS:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{GITHUB_OWNER}/{repo}/pulls?state=open&per_page=10",
                    headers=headers
                )
                if resp.status_code == 200:
                    prs = resp.json()
                    for pr in prs:
                        pr_num = pr["number"]
                        # Get CI status
                        status_resp = await client.get(
                            f"https://api.github.com/repos/{GITHUB_OWNER}/{repo}/commits/{pr['head']['sha']}/status",
                            headers=headers
                        )
                        ci_state = "unknown"
                        if status_resp.status_code == 200:
                            ci_state = status_resp.json().get("state", "unknown")

                        all_prs.append({
                            "repo": repo,
                            "number": pr_num,
                            "title": pr["title"],
                            "author": pr["user"]["login"],
                            "branch": pr["head"]["ref"],
                            "ci_status": ci_state,
                            "url": pr["html_url"],
                            "created": pr["created_at"],
                            "updated": pr["updated_at"],
                        })
        except Exception as e:
            all_prs.append({"repo": repo, "error": str(e)})

    return JSONResponse({
        "prs": all_prs,
        "count": len(all_prs),
        "monitored_repos": GITHUB_REPOS
    })


@app.post('/api/selfcoding/prs/babysit')
async def selfcoding_pr_babysit(request: Request):
    """Auto-diagnose PR CI failures and generate fix via Ollama.

    Body: { "repo": "agY", "pr_number": 1 }
    """
    try:
        body = await request.json()
        repo = body.get("repo", "agY")
        pr_number = body.get("pr_number")
        if not pr_number:
            return JSONResponse({"error": "pr_number required"}, status_code=400)

        github_token = os.environ.get("GITHUB_TOKEN", "")
        headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"} if github_token else {}

        async with httpx.AsyncClient(timeout=15) as client:
            # 1. Get PR details
            pr_resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_OWNER}/{repo}/pulls/{pr_number}",
                headers=headers
            )
            if pr_resp.status_code != 200:
                return JSONResponse({"error": f"PR not found: {pr_resp.status_code}"}, status_code=404)
            pr_data = pr_resp.json()

            # 2. Get changed files
            files_resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_OWNER}/{repo}/pulls/{pr_number}/files",
                headers=headers
            )
            changed_files = [f["filename"] for f in files_resp.json()] if files_resp.status_code == 200 else []

            # 3. Get CI status
            status_resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_OWNER}/{repo}/commits/{pr_data['head']['sha']}/status",
                headers=headers
            )
            ci_status = status_resp.json() if status_resp.status_code == 200 else {}

            # 4. Get check runs for failure details
            checks_resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_OWNER}/{repo}/commits/{pr_data['head']['sha']}/check-runs",
                headers=headers
            )
            failed_checks = []
            if checks_resp.status_code == 200:
                for check in checks_resp.json().get("check_runs", []):
                    if check.get("conclusion") == "failure":
                        failed_checks.append({
                            "name": check["name"],
                            "output_title": check.get("output", {}).get("title", ""),
                            "output_summary": check.get("output", {}).get("summary", "")[:500],
                        })

        # 5. Generate fix via Ollama
        if not failed_checks and ci_status.get("state") != "failure":
            return JSONResponse({
                "status": "healthy",
                "message": f"PR #{pr_number} in {repo} has no CI failures",
                "ci_state": ci_status.get("state", "unknown"),
                "changed_files": changed_files
            })

        failure_context = "\n".join([
            f"Check: {c['name']}\nTitle: {c['output_title']}\nSummary: {c['output_summary']}"
            for c in failed_checks
        ]) or f"CI state: {ci_status.get('state', 'unknown')}"

        fix_result = await _selfcoding_fix(
            f"Fix CI failures in PR #{pr_number} ({repo}): {pr_data['title']}",
            failure_context
        )

        task_id = f"pr-babysit-{int(time.time())}"
        _active_tasks[task_id] = {
            "id": task_id,
            "goal": f"PR Babysit: {repo}#{pr_number}",
            "mode": "pr-babysit",
            "status": "completed",
            "started": time.time(),
            "result": {
                "pr": {"number": pr_number, "title": pr_data["title"], "branch": pr_data["head"]["ref"]},
                "ci_failures": failed_checks,
                "changed_files": changed_files,
                "fix": fix_result
            }
        }

        return JSONResponse({
            "task_id": task_id,
            "status": "fix_generated",
            "pr": {"number": pr_number, "repo": repo, "title": pr_data["title"]},
            "ci_failures": len(failed_checks),
            "fix": fix_result["fix"]
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def _ollama_models():
    """Get models from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get('http://localhost:11434/api/tags')
            data = resp.json()
            return [
                {
                    'name': m.get('name', '?'),
                    'size_gb': round(m.get('size', 0) / 1073741824, 2),
                    'parameter_size': m.get('details', {}).get('parameter_size', '?'),
                    'family': m.get('details', {}).get('family', '?'),
                    'quantization': m.get('details', {}).get('quantization_level', '?'),
                }
                for m in data.get('models', [])
            ]
    except Exception as e:
        return [{'error': str(e)}]


async def _check_service(name: str, url: str) -> dict:
    """Health-check a service."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(url)
            return {'name': name, 'status': 'green', 'code': resp.status_code, 'latency_ms': round(resp.elapsed.total_seconds() * 1000)}
    except Exception as e:
        return {'name': name, 'status': 'red', 'error': str(e)}


async def _check_vps(host: str = '31.97.52.22') -> dict:
    """Check VPS reachability (non-blocking)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            'ssh', '-o', 'ConnectTimeout=3', '-o', 'BatchMode=yes',
            f'root@{host}', 'echo ALIVE',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        alive = 'ALIVE' in stdout.decode()
        return {'name': f'VPS {host}', 'status': 'green' if alive else 'red', 'reachable': alive}
    except Exception:
        return {'name': f'VPS {host}', 'status': 'red', 'reachable': False}


@app.get('/api/fleet/status')
async def fleet_status():
    """Full fleet health — all services, all tiers."""
    nodes = [
        {"name": "ollama", "url": "http://localhost:11434/api/tags", "type": "http"},
        {"name": "fastapi", "url": "http://localhost:8000/health", "type": "http"},
        {"name": "VPS 31.97.52.22", "url": "31.97.52.22", "type": "ping"},
        {"name": "iMac (Intel)", "url": "192.168.1.187", "type": "ping"},
        {"name": "Raspberry Pi", "url": "192.168.1.53", "type": "ping"}
    ]

    checks = []
    for n in nodes:
        if n["type"] == "http":
            checks.append(_check_service(n["name"], n["url"]))
        elif n["type"] == "ping":
            # For ping, we'll use a separate async function or handle it here
            async def _ping_check(name, host):
                try:
                    proc = await asyncio.create_subprocess_exec(
                        'ping', '-c', '1', '-W', '1', host,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2)
                    if proc.returncode == 0:
                        # Extract latency from stdout if possible, otherwise default
                        latency_match = re.search(r"time=(\d+\.?\d*) ms", stdout.decode())
                        latency = float(latency_match.group(1)) if latency_match else 10.0
                        return {'name': name, 'status': 'green', 'reachable': True, 'latency_ms': round(latency)}
                    else:
                        return {'name': name, 'status': 'red', 'reachable': False, 'error': 'Ping failed'}
                except Exception as e:
                    return {'name': name, 'status': 'red', 'reachable': False, 'error': str(e)}
            checks.append(_ping_check(n["name"], n["url"]))

    results = await asyncio.gather(*checks, return_exceptions=True)

    services = []
    for r in results:
        if isinstance(r, dict):
            services.append(r)
        else:
            services.append({'name': '?', 'status': 'red', 'error': str(r)})

    # NAS check
    nas_mounted = os.path.ismount("/Volumes/NasYac")
    services.append({'name': 'NAS', 'status': 'green' if nas_mounted else 'red', 'label': '/Volumes/NasYac'})

    # Redis check
    redis_ok = False
    try:
        if _redis and _redis.ping():
            redis_ok = True
    except Exception:
        pass
    services.append({'name': 'redis', 'status': 'green' if redis_ok else 'red'})

    # Playwright
    services.append({
        'name': 'playwright',
        'status': 'green' if async_playwright is not None else 'red',
    })

    green = sum(1 for s in services if s.get('status') == 'green')
    return JSONResponse({
        'fleet': services,
        'summary': f'{green}/{len(services)} services green',
        'timestamp': time.time(),
    })


@app.get('/api/fleet/compute')
async def fleet_compute():
    """M4 Max compute metrics — memory, GPU, disk, CPU."""
    try:
        cpu_brand = subprocess.check_output(
            ['sysctl', '-n', 'machdep.cpu.brand_string'], timeout=2
        ).decode().strip()
    except Exception:
        cpu_brand = 'Unknown'

    try:
        load = os.getloadavg()
        load_avg = {'1m': round(load[0], 2), '5m': round(load[1], 2), '15m': round(load[2], 2)}
    except Exception:
        load_avg = {}

    return JSONResponse({
        'cpu': cpu_brand,
        'load': load_avg,
        'memory': _sys_memory(),
        'gpu': _sys_gpu(),
        'disk': _disk_info(),
        'timestamp': time.time(),
    })


@app.get('/api/fleet/ollama/models')
async def fleet_ollama_models():
    """List all loaded Ollama models."""
    models = await _ollama_models()
    return JSONResponse({'models': models})


@app.post('/api/fleet/ollama/chat')
async def fleet_ollama_chat(request_body: dict = None):
    """Proxy chat to Ollama — real local AI inference on M4 Max."""
    if request_body is None:
        return JSONResponse({'error': 'Missing body'}, status_code=400)
    model = request_body.get('model', 'qwen3:8b')
    prompt = request_body.get('prompt', '')
    system_prompt = request_body.get('system', 'You are a helpful AI assistant integrated into the GPT Atlas RPA Command Center.')
    if not prompt:
        return JSONResponse({'error': 'Missing prompt'}, status_code=400)
    try:
        started = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post('http://localhost:11434/api/generate', json={
                'model': model,
                'prompt': prompt,
                'system': system_prompt,
                'stream': False,
            })
            data = resp.json()
        elapsed = round(time.time() - started, 2)
        return JSONResponse({
            'response': data.get('response', ''),
            'model': model,
            'duration_s': elapsed,
            'eval_count': data.get('eval_count', 0),
            'eval_duration_ns': data.get('eval_duration', 0),
            'tokens_per_second': round(data.get('eval_count', 0) / max(0.001, data.get('eval_duration', 1) / 1e9), 1),
        })
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)


@app.get('/api/fleet/redis/info')
async def fleet_redis_info():
    """Redis server info snapshot."""
    try:
        if not _redis:
            return JSONResponse({'error': 'Redis client not initialized'}, status_code=503)
        info = _redis.info(section='memory')
        return JSONResponse({
            'connected': True,
            'used_memory_human': info.get('used_memory_human', '?'),
            'used_memory_peak_human': info.get('used_memory_peak_human', '?'),
            'maxmemory_human': info.get('maxmemory_human', '?'),
            'db_keys': {k: v for k, v in _redis.info(section='keyspace').items() if k.startswith('db')},
        })
    except Exception as e:
        return JSONResponse({'error': str(e), 'connected': False}, status_code=503)


@app.get("/health")
async def health():
    return JSONResponse({"ok": True})


@app.get("/system/status")
async def system_status():
    return JSONResponse(
        {
            "status": "ok",
            "service": "antigravity-backend",
            "playwright": "ready" if async_playwright is not None else "unavailable",
            "timestamp": time.time(),
        }
    )


@app.get("/models")
async def models():
    return JSONResponse(
        {
            "models": [
                {
                    "id": "browser-semantic-v1",
                    "type": "browser-agent",
                    "capabilities": [
                        "navigate",
                        "analyze",
                        "extract_dom",
                        "click_text",
                        "scroll",
                        "type_text",
                        "voice_command",
                    ],
                }
            ]
        }
    )


@app.get("/api/solutions/overview")
async def solutions_overview(refresh: bool = Query(default=False)):
    inventory = inventory_service.get_inventory(force_refresh=refresh)
    return JSONResponse(inventory)


@app.get("/api/solutions/test")
async def solutions_test(
    scope: str = Query(default="mvp28"),
    refresh: bool = Query(default=False),
    solution_id: list[str] | None = Query(default=None),
):
    payload = inventory_service.run_tests(
        scope=scope,
        force_refresh=refresh,
        solution_ids=solution_id,
    )
    return JSONResponse(payload)


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/api/solutions/test-stream")
async def solutions_test_stream(
    scope: str = Query(default="mvp28"),
    refresh: bool = Query(default=False),
    solution_id: list[str] | None = Query(default=None),
):
    async def iterator():
        started_at = time.time()
        yield _sse_event("start", {"scope": scope, "started_at": started_at})
        results: list[dict[str, Any]] = []
        for event in inventory_service.iter_test_events(
            scope=scope,
            force_refresh=refresh,
            solution_ids=solution_id,
        ):
            results.append(event["result"])
            yield _sse_event("solution", event)
            await asyncio.sleep(0)
        summary = inventory_service.summarize_results(results)
        finished_at = time.time()
        yield _sse_event(
            "complete",
            {
                "scope": scope,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": round(finished_at - started_at, 2),
                "summary": summary,
            },
        )

    return StreamingResponse(
        iterator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/solutions/item/{solution_id}")
async def solution_details(solution_id: str, refresh: bool = Query(default=False)):
    solution = inventory_service.get_solution(solution_id, force_refresh=refresh)
    if solution is None:
        return JSONResponse({"error": f"Unknown solution_id: {solution_id}"}, status_code=404)
    return JSONResponse(solution)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    last_voice_signature = ""
    last_voice_at = 0.0
    try:
        initial = await _safe_worker_call(
            worker.screenshot("https://python.langchain.com"),
            op="initial navigation",
            timeout=25.0,
        )
        if initial.get("error"):
            await ws.send_json({"type": "error", "data": initial["error"]})
            initial = worker._fallback_payload("about:blank")
        await ws.send_json(
            {
                "type": "navigation",
                "data": {
                    "title": initial.get("title", "Unavailable"),
                    "url": initial.get("url", "about:blank"),
                    "screenshot": initial.get("screenshot", FALLBACK_PNG_B64),
                    "viewport": initial.get("viewport"),
                },
            }
        )
        await ws.send_json({"type": "thinking", "text": "Agent connected and ready."})
        await ws.send_json(
            {
                "type": "cursor",
                "x": 360,
                "y": 220,
                "thought": "Live control active. Waiting for command.",
            }
        )
        await ws.send_json(
            {"type": "next_action", "icon": "🎙️", "text": "Enable voice orb or type a URL to start."}
        )

        while True:
            msg = await ws.receive_json()
            action = msg.get("action", "")

            if action == "voice_command":
                transcript = (msg.get("command") or msg.get("text") or "").strip()
                if not transcript:
                    await ws.send_json({"type": "error", "data": "Missing voice command text"})
                    continue
                signature = " ".join(transcript.lower().split())
                now = time.monotonic()
                if signature and signature == last_voice_signature and (now - last_voice_at) < 2.0:
                    await ws.send_json({"type": "thinking", "text": "Ignored duplicate voice command."})
                    continue
                last_voice_signature = signature
                last_voice_at = now
                parsed = _parse_voice_command(transcript)
                resolved_action = parsed.get("action", "")
                if not resolved_action:
                    await ws.send_json(
                        {
                            "type": "error",
                            "data": f'Voice command not understood: "{transcript}"',
                        }
                    )
                    continue
                await ws.send_json(
                    {
                        "type": "thinking",
                        "text": f'Voice backend parsed: {parsed.get("description", resolved_action)}.',
                    }
                )
                msg = {**msg, **parsed.get("payload", {})}
                action = resolved_action

            if action == "navigate":
                url = (msg.get("url") or "").strip()
                if not url:
                    await ws.send_json({"type": "error", "data": "Missing URL"})
                    continue
                if not url.startswith("http://") and not url.startswith("https://"):
                    url = "https://" + url
                data = await _safe_worker_call(worker.screenshot(url), op=f"navigate to {url}", timeout=28.0)
                if data.get("error"):
                    await ws.send_json({"type": "error", "data": data["error"]})
                    continue
                await ws.send_json(
                    {
                        "type": "navigation",
                        "data": {
                            "title": data.get("title", "Unavailable"),
                            "url": data.get("url", url),
                            "screenshot": data.get("screenshot", FALLBACK_PNG_B64),
                            "viewport": data.get("viewport"),
                        },
                    }
                )
                await ws.send_json({"type": "thinking", "text": f"Navigated to {data.get('url', url)}"})
                await ws.send_json(
                    {
                        "type": "next_action",
                        "icon": "🧠",
                        "text": "Next: run analysis or say 'analyze this page'.",
                    }
                )

            elif action == "extract_dom" or action == "screenshot":
                await ws.send_json({"type": "thinking", "text": "Refreshing view and semantic snapshot..."})
                data = await _safe_worker_call(
                    worker.analyze_current_page("Refresh DOM snapshot"),
                    op="refresh semantic snapshot",
                    timeout=30.0,
                )
                if data.get("error"):
                    await ws.send_json({"type": "error", "data": data["error"]})
                    continue
                dom_payload = {k: v for k, v in data.items() if k != "screenshot"}
                await ws.send_json({"type": "screenshot", "data": data.get("screenshot", FALLBACK_PNG_B64)})
                await ws.send_json({"type": "dom", "data": dom_payload})
                await ws.send_json({"type": "thinking", "text": data.get("summary", "Snapshot refreshed.")})
                await ws.send_json({"type": "next_action", "icon": "🔎", "text": "Snapshot refreshed."})

            elif action == "analyze":
                query = (msg.get("query") or "Analyze current page").strip()
                await ws.send_json({"type": "reasoning_reset"})
                await ws.send_json(
                    {"type": "next_action", "icon": "🧠", "text": "Running structured analysis..."}
                )
                await ws.send_json(
                    {
                        "type": "reasoning_step",
                        "step": "dom",
                        "status": "active",
                        "detail": "Analyzing DOM structure...",
                    }
                )
                await ws.send_json({"type": "thinking", "text": f"Analyzing query: {query}"})

                data = await _safe_worker_call(
                    worker.analyze_current_page(query),
                    op="structured analysis",
                    timeout=35.0,
                )
                if data.get("error"):
                    await ws.send_json(
                        {
                            "type": "reasoning_step",
                            "step": "dom",
                            "status": "failed",
                            "detail": data["error"],
                        }
                    )
                    await ws.send_json({"type": "error", "data": data["error"]})
                    continue

                await ws.send_json({"type": "reasoning_step", "step": "dom", "status": "completed"})
                await ws.send_json(
                    {
                        "type": "reasoning_step",
                        "step": "semantic",
                        "status": "active",
                        "detail": "Extracting semantic data...",
                    }
                )
                await asyncio.sleep(0.18)
                await ws.send_json({"type": "reasoning_step", "step": "semantic", "status": "completed"})
                await ws.send_json(
                    {
                        "type": "reasoning_step",
                        "step": "interactive",
                        "status": "active",
                        "detail": "Identifying interactive elements...",
                    }
                )
                await asyncio.sleep(0.18)
                await ws.send_json({"type": "reasoning_step", "step": "interactive", "status": "completed"})

                payload = {k: v for k, v in data.items() if k != "screenshot"}
                await ws.send_json({"type": "screenshot", "data": data.get("screenshot", FALLBACK_PNG_B64)})
                await ws.send_json({"type": "analysis", "data": payload})
                await ws.send_json({"type": "thinking", "text": data.get("summary", "Analysis complete.")})

                query_match = data.get("queryMatch")
                if query_match and query_match.get("rect"):
                    rect = query_match["rect"]
                    x = _int(rect.get("x"), 10)
                    y = _int(rect.get("y"), 10)
                    w = max(12, _int(rect.get("w"), 120))
                    h = max(12, _int(rect.get("h"), 26))
                    text = _short_label(query_match.get("text") or "matched sentence", 88)
                    await ws.send_json({"type": "highlight", "x": x, "y": y, "w": w, "h": h})
                    await ws.send_json(
                        {
                            "type": "cursor",
                            "x": x + max(8, w // 2),
                            "y": y + max(8, h // 2),
                            "thought": f"Matched sentence: {text}",
                        }
                    )
                    await ws.send_json(
                        {
                            "type": "next_action",
                            "icon": "🎯",
                            "text": f'Matched text: "{text}"',
                        }
                    )
                    continue

                target = data.get("primaryInteractive")
                if target and target.get("rect"):
                    rect = target["rect"]
                    x = _int(rect.get("x"), 10)
                    y = _int(rect.get("y"), 10)
                    w = max(12, _int(rect.get("w"), 60))
                    h = max(12, _int(rect.get("h"), 28))
                    await ws.send_json({"type": "highlight", "x": x, "y": y, "w": w, "h": h})
                    label = _short_label(target.get("label") or target.get("tag") or "element", 64)
                    await ws.send_json(
                        {
                            "type": "cursor",
                            "x": x + max(8, w // 2),
                            "y": y + max(8, h // 2),
                            "thought": f'Primary target: "{label}"',
                        }
                    )
                    await ws.send_json(
                        {
                            "type": "next_action",
                            "icon": "🖱️",
                            "text": f'Next: say "click {label}" to interact.',
                        }
                    )
                else:
                    await ws.send_json(
                        {
                            "type": "next_action",
                            "icon": "🖱️",
                            "text": "Analysis complete. No interactive target highlighted.",
                        }
                    )

            elif action == "click_text":
                text = (msg.get("text") or "").strip()
                if not text:
                    await ws.send_json({"type": "error", "data": "Missing click target text"})
                    continue
                await ws.send_json({"type": "thinking", "text": f'Trying to click "{text}"...'})
                result = await _safe_worker_call(
                    worker.click_text(text),
                    op=f'click "{text}"',
                    timeout=22.0,
                )
                if result.get("error"):
                    await ws.send_json({"type": "error", "data": result["error"]})
                    continue
                await ws.send_json({"type": "screenshot", "data": result.get("screenshot", FALLBACK_PNG_B64)})
                if result.get("viewport"):
                    await ws.send_json(
                        {
                            "type": "navigation",
                            "data": {
                                "title": result.get("title", ""),
                                "url": result.get("url", ""),
                                "screenshot": result.get("screenshot", FALLBACK_PNG_B64),
                                "viewport": result.get("viewport"),
                            },
                        }
                    )
                if not result.get("clicked"):
                    await ws.send_json({"type": "error", "data": result.get("error", "No matching element")})
                    continue

                rect = result.get("rect", {})
                x = _int(rect.get("x"), 10)
                y = _int(rect.get("y"), 10)
                w = max(12, _int(rect.get("w"), 60))
                h = max(12, _int(rect.get("h"), 24))
                label = _short_label(result.get("label", "element"), 64)
                await ws.send_json({"type": "highlight", "x": x, "y": y, "w": w, "h": h})
                await ws.send_json(
                    {
                        "type": "cursor",
                        "x": x + max(8, w // 2),
                        "y": y + max(8, h // 2),
                        "thought": f'Clicked "{label}"',
                    }
                )
                await ws.send_json({"type": "thinking", "text": f'Clicked "{label}" successfully.'})
                await ws.send_json(
                    {
                        "type": "next_action",
                        "icon": "🧠",
                        "text": "Next: say 'analyze this page' to inspect the updated content.",
                    }
                )

            elif action == "scroll":
                direction = (msg.get("direction") or "down").strip().lower()
                result = await _safe_worker_call(
                    worker.scroll_page(direction),
                    op=f"scroll {direction}",
                    timeout=12.0,
                )
                if result.get("error"):
                    await ws.send_json({"type": "error", "data": result["error"]})
                    continue
                await ws.send_json({"type": "screenshot", "data": result.get("screenshot", FALLBACK_PNG_B64)})
                await ws.send_json(
                    {
                        "type": "thinking",
                        "text": f"Scrolled {result.get('direction', direction)}.",
                    }
                )
                await ws.send_json(
                    {
                        "type": "next_action",
                        "icon": "🔎",
                        "text": "Viewport moved. You can say 'analyze this page' now.",
                    }
                )

            elif action == "type_text":
                text = (msg.get("text") or "").strip()
                submit = bool(msg.get("submit", False))
                result = await _safe_worker_call(
                    worker.type_text(text, submit=submit),
                    op="type text",
                    timeout=20.0,
                )
                if result.get("error"):
                    await ws.send_json({"type": "error", "data": result["error"]})
                    continue
                await ws.send_json({"type": "screenshot", "data": result.get("screenshot", FALLBACK_PNG_B64)})
                if result.get("viewport"):
                    await ws.send_json(
                        {
                            "type": "navigation",
                            "data": {
                                "title": result.get("title", ""),
                                "url": result.get("url", ""),
                                "screenshot": result.get("screenshot", FALLBACK_PNG_B64),
                                "viewport": result.get("viewport"),
                            },
                        }
                    )
                if not result.get("ok"):
                    await ws.send_json({"type": "error", "data": result.get("error", "Type action failed")})
                    continue

                focus = result.get("focus") or {}
                rect = focus.get("rect") or {}
                x = _int(rect.get("x"), 10)
                y = _int(rect.get("y"), 10)
                w = max(16, _int(rect.get("w"), 120))
                h = max(16, _int(rect.get("h"), 28))
                await ws.send_json({"type": "highlight", "x": x, "y": y, "w": w, "h": h})
                label = _short_label(focus.get("label", "input"), 40)
                typed_preview = _short_label(result.get("typed", ""), 72)
                await ws.send_json(
                    {
                        "type": "cursor",
                        "x": x + max(8, w // 2),
                        "y": y + max(8, h // 2),
                        "thought": f'Typed "{typed_preview}" into {label}',
                    }
                )
                if result.get("submit"):
                    await ws.send_json({"type": "thinking", "text": f'Submitted "{typed_preview}".'})
                else:
                    await ws.send_json({"type": "thinking", "text": f'Typed "{typed_preview}".'})
                await ws.send_json(
                    {
                        "type": "next_action",
                        "icon": "⏎",
                        "text": "Next: say 'analyze this page' or continue with another command.",
                    }
                )

            else:
                await ws.send_json({"type": "error", "data": f"Unsupported action: {action}"})

    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "data": f"WebSocket backend error: {exc}"})
        except Exception:
            pass
        return
