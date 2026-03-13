"""
Module 1: Sovereign Site Crawler
Recursive depth-limited crawler using Playwright.
Discovers all pages, extracts all interactive elements.
"""

import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright


@dataclass
class PageData:
    url: str
    title: str = ""
    screenshot_b64: str = ""
    text_content: str = ""
    headings: List[Dict] = field(default_factory=list)
    links: List[Dict] = field(default_factory=list)
    buttons: List[Dict] = field(default_factory=list)
    forms: List[Dict] = field(default_factory=list)
    images: List[Dict] = field(default_factory=list)
    videos: List[Dict] = field(default_factory=list)
    meta: Dict = field(default_factory=dict)
    depth: int = 0


@dataclass
class SiteMap:
    root_url: str
    domain: str
    pages: List[PageData] = field(default_factory=list)
    total_links: int = 0
    total_buttons: int = 0
    total_forms: int = 0
    total_images: int = 0
    crawl_time: float = 0.0


EXTRACTION_JS = """() => {
    const getText = (el) => (el.innerText || el.textContent || '').trim().substring(0, 200);
    const getAttr = (el, attr) => el.getAttribute(attr) || '';

    const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => ({
        level: h.tagName, text: getText(h)
    })).slice(0, 50);

    const links = [...document.querySelectorAll('a[href]')].map(a => ({
        text: getText(a), href: getAttr(a, 'href'), target: getAttr(a, 'target')
    })).slice(0, 100);

    const buttons = [...document.querySelectorAll(
        'button, [role="button"], input[type="submit"], input[type="button"]'
    )].map(b => ({
        text: getText(b) || getAttr(b, 'value') || getAttr(b, 'aria-label'),
        type: getAttr(b, 'type'), id: getAttr(b, 'id'), classes: b.className
    })).slice(0, 50);

    const forms = [...document.querySelectorAll('form')].map(f => ({
        action: getAttr(f, 'action'), method: getAttr(f, 'method') || 'GET',
        inputs: [...f.querySelectorAll('input, select, textarea')].map(i => ({
            type: getAttr(i, 'type') || i.tagName.toLowerCase(),
            name: getAttr(i, 'name'), placeholder: getAttr(i, 'placeholder')
        }))
    })).slice(0, 20);

    const images = [...document.querySelectorAll('img')].map(img => ({
        src: getAttr(img, 'src'), alt: getAttr(img, 'alt'),
        width: img.naturalWidth, height: img.naturalHeight
    })).slice(0, 50);

    const videos = [...document.querySelectorAll(
        'video, iframe[src*="youtube"], iframe[src*="vimeo"]'
    )].map(v => ({
        src: getAttr(v, 'src'), poster: getAttr(v, 'poster') || '', type: v.tagName
    })).slice(0, 20);

    const meta = {
        title: document.title || '',
        description: document.querySelector('meta[name="description"]')?.content || '',
        ogTitle: document.querySelector('meta[property="og:title"]')?.content || '',
        ogDescription: document.querySelector('meta[property="og:description"]')?.content || '',
        ogImage: document.querySelector('meta[property="og:image"]')?.content || '',
        canonical: document.querySelector('link[rel="canonical"]')?.href || '',
        viewport: document.querySelector('meta[name="viewport"]')?.content || ''
    };

    const textContent = (document.body?.innerText || '').substring(0, 5000);

    return { headings, links, buttons, forms, images, videos, meta, textContent };
}"""

SKIP_EXTENSIONS = {
    ".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".mp4", ".mp3", ".css", ".js", ".woff", ".woff2", ".ttf",
}
SKIP_SCHEMES = {"mailto:", "tel:", "javascript:", "#", "data:"}


class SiteCrawler:
    def __init__(self, max_depth: int = 2, max_pages: int = 15):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.visited: Set[str] = set()
        self.pages: List[PageData] = []
        self.emit: Optional[Callable] = None

    def _normalize(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def _same_domain(self, url: str, domain: str) -> bool:
        try:
            return urlparse(url).netloc == domain
        except Exception:
            return False

    def _valid_url(self, url: str) -> bool:
        if any(url.startswith(s) for s in SKIP_SCHEMES):
            return False
        if any(url.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
            return False
        return url.startswith("http")

    async def crawl(self, url: str, emit: Optional[Callable] = None) -> SiteMap:
        self.emit = emit
        self.visited = set()
        self.pages = []
        start = datetime.now()

        # Auto-prepend https:// if no scheme provided
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        parsed = urlparse(url)
        domain = parsed.netloc

        if self.emit:
            await self.emit(
                f"🕷️ Crawl started: {url} | depth={self.max_depth} max_pages={self.max_pages}"
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )
            await self._crawl_page(ctx, url, domain, 0)
            await ctx.close()
            await browser.close()

        elapsed = (datetime.now() - start).total_seconds()

        sitemap = SiteMap(
            root_url=url,
            domain=domain,
            pages=self.pages,
            total_links=sum(len(pg.links) for pg in self.pages),
            total_buttons=sum(len(pg.buttons) for pg in self.pages),
            total_forms=sum(len(pg.forms) for pg in self.pages),
            total_images=sum(len(pg.images) for pg in self.pages),
            crawl_time=elapsed,
        )

        if self.emit:
            await self.emit(
                f"✅ Crawl complete: {len(self.pages)} pages in {elapsed:.1f}s"
            )
        return sitemap

    async def _crawl_page(self, ctx, url: str, domain: str, depth: int):
        norm = self._normalize(url)
        if norm in self.visited or len(self.pages) >= self.max_pages or depth > self.max_depth:
            return
        self.visited.add(norm)

        if self.emit:
            await self.emit(f"📄 [{depth}] Crawling: {url}")

        try:
            page = await ctx.new_page()
            await page.goto(url, wait_until="networkidle", timeout=15000)
            await asyncio.sleep(1)

            page_data = await self._extract(page, url, depth)
            self.pages.append(page_data)
            await page.close()

            # Recurse into child links
            if depth < self.max_depth:
                child_urls = []
                for link in page_data.links:
                    href = link.get("href", "")
                    if not href:
                        continue
                    full = urljoin(url, href)
                    if (
                        self._same_domain(full, domain)
                        and self._valid_url(full)
                        and self._normalize(full) not in self.visited
                    ):
                        child_urls.append(full)

                for child in child_urls[:10]:
                    if len(self.pages) >= self.max_pages:
                        break
                    await self._crawl_page(ctx, child, domain, depth + 1)

        except Exception as e:
            if self.emit:
                await self.emit(f"⚠️ Error crawling {url}: {str(e)[:120]}")

    async def _extract(self, page, url: str, depth: int) -> PageData:
        screenshot_bytes = await page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        extraction = await page.evaluate(EXTRACTION_JS)
        title = await page.title()

        return PageData(
            url=url,
            title=title,
            screenshot_b64=screenshot_b64,
            text_content=extraction.get("textContent", ""),
            headings=extraction.get("headings", []),
            links=extraction.get("links", []),
            buttons=extraction.get("buttons", []),
            forms=extraction.get("forms", []),
            images=extraction.get("images", []),
            videos=extraction.get("videos", []),
            meta=extraction.get("meta", {}),
            depth=depth,
        )
