import asyncio
import base64
import json
import re
import time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
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
