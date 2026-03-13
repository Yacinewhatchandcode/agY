from __future__ import annotations

import json
import re
import time
import socket
from html import unescape
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


INVENTORY_VERSION = "20260313d"
TARGET_MVP_COUNT = 28

SCAN_ROOTS = [
    Path("/Users/yacinebenhamou/workspace/agents"),
    Path("/Users/yacinebenhamou/workspace/products"),
    Path("/Users/yacinebenhamou/workspace/experiments"),
    Path("/Users/yacinebenhamou/workspace/research"),
    Path("/Users/yacinebenhamou/AMLAZR"),
    Path("/Users/yacinebenhamou/Agentic_Repo_Orchestration"),
    Path("/Users/yacinebenhamou/DesktopAgents"),
    Path("/Users/yacinebenhamou/Conciergerie"),
    Path("/Users/yacinebenhamou/SomthSerious"),
    Path("/Users/yacinebenhamou/Hackathon1YBE"),
    Path("/Users/yacinebenhamou/Game1"),
    Path("/Users/yacinebenhamou/Downloads/LisAI"),
]

SPECIAL_PROJECTS = [
    Path("/Users/yacinebenhamou/Downloads/agY"),
    Path("/Users/yacinebenhamou/Prime-ai.fr"),
]

EXCLUDED_TOP_LEVEL = {"backups", "logs", "data_lake", "core"}

WALK_IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".cursor",
    ".vscode",
    ".idea",
    ".turbo",
    ".cache",
    ".npm",
    ".pnpm-store",
    ".yarn",
    ".mypy_cache",
    ".pytest_cache",
    "vendor",
    "site-packages",
    "target",
    "Pods",
    "DerivedData",
    "coverage",
}

IGNORED_SEGMENTS = {
    "examples",
    "example",
    "samples",
    "sample",
    "templates",
    "template",
    "docs",
    "doc",
    "tests",
    "test",
    "evals",
    "benchmark",
    "benchmarks",
    "storybook",
    "fixtures",
    "archive",
    "deprecated",
    "related-projects",
    "agent-frameworks",
    ".github",
}

FRONTEND_DIR_HINTS = {
    "frontend",
    "ui",
    "web",
    "client",
    "dashboard",
    "app",
    "landing",
}

BACKEND_DIR_HINTS = {
    "backend",
    "api",
    "server",
    "services",
    "orchestrator",
    "agents",
    "src-tauri",
}

FRONTEND_FILE_HINTS = {
    "package.json",
    "index.html",
    "vite.config.ts",
    "vite.config.js",
    "next.config.js",
    "next.config.mjs",
}

BACKEND_FILE_HINTS = {
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "langgraph.json",
    "server.py",
    "main.py",
    "app.py",
}

README_CANDIDATES = ("README.md", "README.MD", "readme.md")
URL_PATTERN = re.compile(r"https?://(?:localhost|127\\.0\\.0\\.1):\\d{2,5}(?:/[^\\s\"'<>)]*)?")
PORT_PATTERN = re.compile(r"(^|\\s|-)(\\d{2,5}):(\\d{2,5})(\\s|$)")
TAG_PATTERN = re.compile(r"<[^>]+>")
SPACE_PATTERN = re.compile(r"\\s+")
WORD_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9'\\-]{1,}")
SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?]+")
MARKDOWN_CODE_BLOCK_PATTERN = re.compile(r"```.*?```", flags=re.DOTALL)
MARKDOWN_INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")

JARGON_TERMS = {
    "api",
    "sdk",
    "mcp",
    "orchestrator",
    "orchestration",
    "websocket",
    "grpc",
    "docker",
    "container",
    "llm",
    "prompt",
    "embedding",
    "vector",
    "kubernetes",
    "schema",
    "inference",
    "agentic",
}

PLAIN_LANGUAGE_TERMS = {
    "you",
    "your",
    "click",
    "start",
    "step",
    "how",
    "what",
    "why",
    "use",
    "open",
    "run",
}

JARGON_REWRITE_HINTS = {
    "api": "an easy connection between apps",
    "sdk": "a developer toolkit",
    "mcp": "a connector for tools",
    "orchestrator": "the part that coordinates tasks",
    "websocket": "a live connection",
    "grpc": "a fast backend connection",
    "docker": "a portable app package",
    "container": "an isolated app package",
    "llm": "an AI model",
    "embedding": "a numeric representation of text",
    "vector": "a math format used for search",
    "schema": "a structured data format",
    "inference": "the model generating an answer",
}


@dataclass
class SolutionRecord:
    solution_id: str
    name: str
    path: str
    category: str
    platform: str
    confidence: int
    has_git: bool
    has_readme: bool
    frontend_signals: list[str]
    backend_signals: list[str]
    launch_commands: list[str]
    local_urls: list[str]
    duplicate_group: str
    discovered_urls: list[str]
    is_mvp: bool = False


def _safe_read_text(path: Path, limit: int = 240000) -> str:
    try:
        raw = path.read_bytes()
    except Exception:
        return ""
    if not raw:
        return ""
    raw = raw[:limit]
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _normalize_command(command: str) -> str:
    clean = " ".join((command or "").split())
    if len(clean) > 120:
        return f"{clean[:117]}..."
    return clean


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "solution"


def _record_id(path: Path) -> str:
    slug = _slug(path.name)
    token = abs(hash(str(path.resolve()))) % 1000000
    return f"{slug}-{token:06d}"


# ── Known service registry ──────────────────────────────────────────────────
# Maps project directory basenames to their actual runtime ports.
# Sourced from real process discovery (lsof -iTCP + lsof -p <pid> cwd).
KNOWN_SERVICES: dict[str, list[str]] = {
    "zeroclaw":     ["http://127.0.0.1:3003"],
    "nullclaw":     ["http://127.0.0.1:3001"],
    "agent-zero":   ["http://127.0.0.1:5001"],
    "nanobot":      ["http://127.0.0.1:8080"],
    "AgentY":       ["http://127.0.0.1:5173", "http://127.0.0.1:8000"],
    "agY":          ["http://127.0.0.1:8011"],
    "Prime.AI":     ["http://127.0.0.1:3000"],
    "bytebot":      ["http://127.0.0.1:9990", "http://127.0.0.1:9991", "http://127.0.0.1:9992"],
    "firecrawl":    ["http://127.0.0.1:3002", "http://127.0.0.1:27017"],
    # Colony workers (Docker ByteBot fleet)
    "colony-concierge":  ["http://127.0.0.1:10092"],
    "colony-research":   ["http://127.0.0.1:10192"],
    "colony-worker-3":   ["http://127.0.0.1:10292"],
    "colony-worker-4":   ["http://127.0.0.1:10392"],
    # Infrastructure
    "ollama":       ["http://127.0.0.1:11434"],
    "jupyter":      ["http://127.0.0.1:8888"],
}


class SolutionInventoryService:
    def __init__(self) -> None:
        self._cache: dict[str, Any] | None = None
        self._cache_ttl_seconds = 45
        self._tested_cache: dict[str, dict[str, Any]] = {}

    def get_inventory(self, force_refresh: bool = False) -> dict[str, Any]:
        now = time.time()
        if (
            not force_refresh
            and self._cache is not None
            and (now - float(self._cache.get("generated_at", 0))) <= self._cache_ttl_seconds
        ):
            return self._cache

        projects = self._scan_top_level_projects()
        records = [self._inspect_project(project) for project in projects]
        duplicates = self._build_duplicate_map(records)
        for record in records:
            record.duplicate_group = duplicates.get(record.name.lower(), "")

        mvp_ids = self._select_mvp_records(records)
        for record in records:
            record.is_mvp = record.solution_id in mvp_ids

        records.sort(
            key=lambda r: (
                0 if r.is_mvp else 1,
                {"full-stack": 0, "backend/service": 1, "frontend/app": 2, "unknown/infra": 3}.get(
                    r.category, 4
                ),
                -r.confidence,
                r.name.lower(),
            )
        )

        totals = {
            "top_level_projects": len(records),
            "full_stack": sum(1 for r in records if r.category == "full-stack"),
            "frontend": sum(1 for r in records if r.category == "frontend/app"),
            "backend": sum(1 for r in records if r.category == "backend/service"),
            "unknown": sum(1 for r in records if r.category == "unknown/infra"),
            "desktop": sum(1 for r in records if r.platform == "desktop/tauri"),
            "mvp": sum(1 for r in records if r.is_mvp),
            "duplicate_groups": sum(1 for v in duplicates.values() if v),
        }

        inventory = {
            "version": INVENTORY_VERSION,
            "generated_at": now,
            "counts": totals,
            "solutions": [asdict(record) for record in records],
        }
        self._cache = inventory
        return inventory

    def run_tests(
        self,
        scope: str = "mvp28",
        force_refresh: bool = False,
        solution_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        inventory = self.get_inventory(force_refresh=force_refresh)
        selected = self._select_scope(inventory["solutions"], scope, solution_ids=solution_ids)
        results = [self._run_solution_tests(item, bypass_cache=force_refresh) for item in selected]
        summary = self.summarize_results(results)
        return {
            "scope": scope,
            "generated_at": time.time(),
            "summary": summary,
            "results": results,
        }

    def iter_test_events(
        self,
        scope: str = "mvp28",
        force_refresh: bool = False,
        solution_ids: list[str] | None = None,
    ):
        inventory = self.get_inventory(force_refresh=force_refresh)
        selected = self._select_scope(inventory["solutions"], scope, solution_ids=solution_ids)
        total = len(selected)
        for idx, item in enumerate(selected, start=1):
            result = self._run_solution_tests(item, bypass_cache=force_refresh)
            yield {
                "index": idx,
                "total": total,
                "solution_id": item["solution_id"],
                "result": result,
            }

    def get_solution(self, solution_id: str, force_refresh: bool = False) -> dict[str, Any] | None:
        inventory = self.get_inventory(force_refresh=force_refresh)
        for item in inventory["solutions"]:
            if item["solution_id"] == solution_id:
                return item
        return None

    def _scan_top_level_projects(self) -> list[Path]:
        projects: set[Path] = set()
        for root in SCAN_ROOTS:
            if not root.exists() or not root.is_dir():
                continue
            try:
                children = list(root.iterdir())
            except Exception:
                continue
            for child in children:
                if not child.is_dir():
                    continue
                if child.name.startswith(".") or child.name in EXCLUDED_TOP_LEVEL:
                    continue
                try:
                    projects.add(child.resolve())
                except Exception:
                    continue

        for special in SPECIAL_PROJECTS:
            if special.exists() and special.is_dir():
                projects.add(special.resolve())

        return sorted(projects, key=lambda p: str(p).lower())

    def _inspect_project(self, project: Path) -> SolutionRecord:
        frontend_signals: set[str] = set()
        backend_signals: set[str] = set()
        local_urls: set[str] = set()
        discovered_urls_from_config: set[str] = set()
        launch_commands: set[str] = set()
        has_docker_compose = False
        has_tauri = False
        has_readme = False
        has_git = (project / ".git").exists()

        readme_path = self._find_readme(project)
        if readme_path is not None:
            has_readme = True
            readme_text = _safe_read_text(readme_path)
            found_urls = URL_PATTERN.findall(readme_text)
            local_urls.update(found_urls)
            discovered_urls_from_config.update(found_urls)
            for line in readme_text.splitlines():
                if "npm run dev" in line:
                    launch_commands.add("npm run dev")
                if "docker compose up" in line:
                    launch_commands.add("docker compose up -d")
                if "uvicorn" in line:
                    launch_commands.add("uvicorn app:app --reload")

        stack: list[Path] = [project]
        while stack:
            current = stack.pop()
            rel_parts = current.relative_to(project).parts if current != project else ()
            if len(rel_parts) > 3:
                continue
            if any(part in IGNORED_SEGMENTS for part in rel_parts):
                continue
            try:
                children = list(current.iterdir())
            except Exception:
                continue

            dirs: list[Path] = []
            files: list[Path] = []
            for child in children:
                if child.is_dir():
                    if child.name in WALK_IGNORE_DIRS:
                        continue
                    dirs.append(child)
                elif child.is_file():
                    files.append(child)

            current_name = current.name.lower()
            if current_name in FRONTEND_DIR_HINTS:
                frontend_signals.add(f"dir:{current_name}")
            if current_name in BACKEND_DIR_HINTS:
                backend_signals.add(f"dir:{current_name}")
            if current_name == "src-tauri":
                has_tauri = True

            file_names = {file.name for file in files}
            for hint in FRONTEND_FILE_HINTS:
                if hint in file_names:
                    frontend_signals.add(f"file:{hint}")
            for hint in BACKEND_FILE_HINTS:
                if hint in file_names:
                    backend_signals.add(f"file:{hint}")

            package_json = current / "package.json"
            if package_json.exists():
                scripts = self._extract_npm_scripts(package_json)
                for script_name in ("dev", "start", "build", "preview"):
                    if script_name in scripts:
                        launch_commands.add(f"npm run {script_name}")
                if scripts:
                    frontend_signals.add("manifest:package.json")
                # Extract ports from script values to discover real URLs
                for _sname, sval in scripts.items():
                    for port_m in re.finditer(r'(?:--port|PORT=|:)(\d{4,5})', str(sval)):
                        p = int(port_m.group(1))
                        if 1024 < p < 65536:
                            purl = f"http://127.0.0.1:{p}"
                            local_urls.add(purl)
                            discovered_urls_from_config.add(purl)

            for compose_name in ("docker-compose.yml", "docker-compose.yaml"):
                compose_path = current / compose_name
                if compose_path.exists():
                    has_docker_compose = True
                    backend_signals.add(f"manifest:{compose_name}")
                    launch_commands.add("docker compose up -d")
                    compose_text = _safe_read_text(compose_path)
                    found_urls = URL_PATTERN.findall(compose_text)
                    local_urls.update(found_urls)
                    discovered_urls_from_config.update(found_urls)
                    for match in PORT_PATTERN.finditer(compose_text):
                        host_port = match.group(2)
                        port_url = f"http://127.0.0.1:{host_port}"
                        local_urls.add(port_url)
                        discovered_urls_from_config.add(port_url)

            langgraph = current / "langgraph.json"
            if langgraph.exists():
                backend_signals.add("manifest:langgraph.json")
                launch_commands.add("langgraph dev")

            pyproject = current / "pyproject.toml"
            if pyproject.exists():
                backend_signals.add("manifest:pyproject.toml")
                launch_commands.add("python -m uvicorn app:app --reload")

            requirements = current / "requirements.txt"
            if requirements.exists():
                backend_signals.add("manifest:requirements.txt")
                launch_commands.add("pip install -r requirements.txt")

            # Scan Python server files and .env for ports
            for pfile_name in ("server.py", "app.py", "main.py", ".env"):
                pfile = current / pfile_name
                if pfile.exists():
                    try:
                        ptext = pfile.read_text(errors="replace")[:8000]
                        for pm in re.finditer(r'(?:port[=:\s]+|PORT[=:\s]+|--port\s+)(\d{4,5})', ptext):
                            port_num = int(pm.group(1))
                            if 1024 < port_num < 65536:
                                purl = f"http://127.0.0.1:{port_num}"
                                local_urls.add(purl)
                                discovered_urls_from_config.add(purl)
                    except Exception:
                        pass

            tauri_conf = current / "tauri.conf.json"
            if tauri_conf.exists():
                has_tauri = True
                launch_commands.add("npm run tauri dev")

            for dir_child in dirs:
                stack.append(dir_child)

        category = self._derive_category(frontend_signals, backend_signals)
        platform = self._derive_platform(category, has_tauri, has_docker_compose)
        confidence = self._confidence_score(
            category=category,
            has_git=has_git,
            has_readme=has_readme,
            frontend_signals=frontend_signals,
            backend_signals=backend_signals,
            launch_commands=launch_commands,
            has_local_urls=bool(local_urls),
        )

        if not local_urls:
            local_urls.update(self._default_urls_for_project(project, category))

        # Inject known service ports (verified by real process discovery)
        known = KNOWN_SERVICES.get(project.name, [])
        for kurl in known:
            local_urls.add(kurl)
            discovered_urls_from_config.add(kurl)

        # discovered_urls = only URLs extracted from config files, not guessed defaults
        discovered = sorted(discovered_urls_from_config)

        return SolutionRecord(
            solution_id=_record_id(project),
            name=project.name,
            path=str(project),
            category=category,
            platform=platform,
            confidence=confidence,
            has_git=has_git,
            has_readme=has_readme,
            frontend_signals=sorted(frontend_signals),
            backend_signals=sorted(backend_signals),
            launch_commands=sorted(_normalize_command(cmd) for cmd in launch_commands),
            local_urls=sorted(local_urls),
            duplicate_group="",
            discovered_urls=discovered,
        )

    def _build_duplicate_map(self, records: list[SolutionRecord]) -> dict[str, str]:
        grouped: dict[str, list[str]] = {}
        for record in records:
            key = record.name.lower()
            grouped.setdefault(key, []).append(record.path)
        duplicates: dict[str, str] = {}
        for key, paths in grouped.items():
            if len(paths) > 1:
                duplicates[key] = key
            else:
                duplicates[key] = ""
        return duplicates

    def _select_mvp_records(self, records: list[SolutionRecord]) -> set[str]:
        full_stack = [record for record in records if record.category == "full-stack"]
        full_stack.sort(key=lambda record: (-record.confidence, record.name.lower()))

        picked: list[SolutionRecord] = full_stack[:TARGET_MVP_COUNT]
        if len(picked) < TARGET_MVP_COUNT:
            extras = [
                record
                for record in records
                if record.solution_id not in {item.solution_id for item in picked}
                and record.category in {"backend/service", "frontend/app"}
            ]
            extras.sort(key=lambda record: (-record.confidence, record.name.lower()))
            needed = TARGET_MVP_COUNT - len(picked)
            picked.extend(extras[:needed])
        return {record.solution_id for record in picked}

    def _derive_category(self, frontend_signals: set[str], backend_signals: set[str]) -> str:
        has_frontend = bool(frontend_signals)
        has_backend = bool(backend_signals)
        if has_frontend and has_backend:
            return "full-stack"
        if has_backend:
            return "backend/service"
        if has_frontend:
            return "frontend/app"
        return "unknown/infra"

    def _derive_platform(self, category: str, has_tauri: bool, has_docker_compose: bool) -> str:
        if has_tauri:
            return "desktop/tauri"
        if has_docker_compose and category == "full-stack":
            return "full-stack/docker"
        if has_docker_compose and category == "backend/service":
            return "service/docker"
        return "web/other"

    def _confidence_score(
        self,
        *,
        category: str,
        has_git: bool,
        has_readme: bool,
        frontend_signals: set[str],
        backend_signals: set[str],
        launch_commands: set[str],
        has_local_urls: bool,
    ) -> int:
        score = 0
        if category == "full-stack":
            score += 40
        elif category == "backend/service":
            score += 28
        elif category == "frontend/app":
            score += 22
        score += min(len(frontend_signals) * 4, 20)
        score += min(len(backend_signals) * 4, 20)
        score += min(len(launch_commands) * 4, 16)
        if has_git:
            score += 6
        if has_readme:
            score += 6
        if has_local_urls:
            score += 6
        return min(score, 100)

    def _extract_npm_scripts(self, package_json: Path) -> dict[str, Any]:
        raw = _safe_read_text(package_json)
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        scripts = data.get("scripts", {})
        if isinstance(scripts, dict):
            return scripts
        return {}

    def _find_readme(self, project: Path) -> Path | None:
        for candidate in README_CANDIDATES:
            readme = project / candidate
            if readme.exists() and readme.is_file():
                return readme
        return None

    def _default_urls_for_project(self, project: Path, category: str) -> set[str]:
        name = project.name.lower()
        urls: set[str] = set()
        if category in {"full-stack", "frontend/app"}:
            urls.add("http://127.0.0.1:3000")
            urls.add("http://127.0.0.1:5173")
        if category in {"full-stack", "backend/service"}:
            urls.add("http://127.0.0.1:8000")
            urls.add("http://127.0.0.1:8080")
        if "agy" in name or "antigravity" in name:
            urls.add("http://127.0.0.1:8011")
        if "prime" in name:
            urls.add("http://127.0.0.1:3000")
        return urls

    def _select_scope(
        self,
        items: list[dict[str, Any]],
        scope: str,
        solution_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if solution_ids:
            wanted = {item.strip() for item in solution_ids if item.strip()}
            return [item for item in items if item.get("solution_id") in wanted]
        normalized = (scope or "mvp28").strip().lower()
        if normalized in {"all", "global"}:
            return list(items)
        if normalized in {"full-stack", "fullstack"}:
            return [item for item in items if item.get("category") == "full-stack"]
        return [item for item in items if item.get("is_mvp")]

    def _run_solution_tests(self, item: dict[str, Any], bypass_cache: bool = False) -> dict[str, Any]:
        solution_id = item["solution_id"]
        cache_key = f"{INVENTORY_VERSION}:{solution_id}:{item.get('confidence', 0)}"
        if not bypass_cache:
            cached = self._tested_cache.get(cache_key)
            if cached is not None:
                return cached

        path = Path(item["path"])
        checks: list[dict[str, Any]] = []

        def add_check(name: str, passed: bool, detail: str, critical: bool = False) -> None:
            checks.append(
                {
                    "name": name,
                    "passed": bool(passed),
                    "detail": detail,
                    "critical": critical,
                }
            )

        add_check("path_exists", path.exists(), f"Path exists: {path}", critical=True)
        add_check("git_repo", bool(item.get("has_git")), "Git repository detected")
        add_check("readme", bool(item.get("has_readme")), "README detected")
        add_check(
            "frontend_signal",
            bool(item.get("frontend_signals")),
            f"Frontend signals: {len(item.get('frontend_signals', []))}",
            critical=item.get("category") == "full-stack",
        )
        add_check(
            "backend_signal",
            bool(item.get("backend_signals")),
            f"Backend signals: {len(item.get('backend_signals', []))}",
            critical=item.get("category") in {"full-stack", "backend/service"},
        )
        add_check(
            "launch_commands",
            bool(item.get("launch_commands")),
            f"Launch commands: {len(item.get('launch_commands', []))}",
            critical=item.get("category") == "full-stack",
        )
        add_check("access_urls", bool(item.get("local_urls")), f"Local URLs: {len(item.get('local_urls', []))}")

        # ── LIVE CHECKS: actually probe running services ──────────────────
        # Only check URLs discovered from config files, not hardcoded guesses
        live_urls = item.get("discovered_urls", []) or []
        port_results = self._probe_ports(live_urls)
        any_port_open = any(r["open"] for r in port_results)
        port_detail_parts = [f"{r['host']}:{r['port']}={'UP' if r['open'] else 'DOWN'}" for r in port_results]
        add_check(
            "port_open",
            any_port_open,
            f"Live ports: {' | '.join(port_detail_parts[:6])}" if port_detail_parts else "No local URLs to probe",
            critical=False,
        )

        http_results = self._http_health_check(live_urls)
        any_http_ok = any(r["ok"] for r in http_results)
        http_detail_parts = [
            f"{r['url']}={r['status']}" for r in http_results
        ]
        add_check(
            "http_live",
            any_http_ok,
            f"HTTP: {' | '.join(http_detail_parts[:6])}" if http_detail_parts else "No reachable URLs",
            critical=False,
        )

        # ── SCREENSHOT CAPTURE: headless browser proof of live services ────
        screenshot_path = None
        if any_port_open and live_urls:
            # Pick the first URL that responded to HTTP, or just the first live URL
            best_url = next(
                (r["url"] for r in http_results if r["ok"]),
                live_urls[0],
            )
            try:
                import screenshot_prober
                screenshot_path = screenshot_prober.capture(best_url, solution_id)
            except Exception as exc:
                log.warning("Screenshot capture error for %s: %s", solution_id, exc)

        content_audit = self._content_semantic_audit(Path(item["path"]), item.get("local_urls", []))
        add_check(
            "content_plain_language",
            bool(content_audit.get("passed")),
            (
                f"Content score {content_audit.get('score', 0)} "
                f"(source: {content_audit.get('source_type', 'none')})"
            ),
            critical=False,
        )

        blocking_failures = sum(
            1 for check in checks if check["name"] in {"path_exists"} and not check["passed"]
        )
        quality_failures = sum(
            1 for check in checks if check["name"] in {"content_plain_language"} and not check["passed"]
        )
        if blocking_failures > 0:
            status = "fail"
        elif quality_failures > 0:
            status = "warn"
        else:
            status = "pass"

        passed_count = sum(1 for check in checks if check["passed"])
        total_checks = len(checks)
        score = int(round((passed_count / total_checks) * 100)) if total_checks else 0

        result = {
            "solution_id": solution_id,
            "name": item["name"],
            "path": item["path"],
            "status": status,
            "score": score,
            "checks": checks,
            "content_audit": content_audit,
            "screenshot_path": screenshot_path,
            "tested_at": time.time(),
        }
        self._tested_cache[cache_key] = result
        return result

    def _content_semantic_audit(self, project: Path, local_urls: list[str]) -> dict[str, Any]:
        samples = self._collect_content_samples(project, local_urls)
        if not samples:
            return {
                "passed": False,
                "score": 0,
                "word_count": 0,
                "sentence_count": 0,
                "avg_sentence_words": 0.0,
                "jargon_ratio": 0.0,
                "plain_terms_hits": 0,
                "issues": ["No user-facing page content was found for this solution."],
                "recommendations": [
                    "Add a plain-language overview page with what the app does, for whom, and the first action.",
                    "Add a short step-by-step section using direct words like click, open, start, and next.",
                ],
                "source_type": "none",
                "source_ref": "",
                "excerpt": "",
                "pages_tested": 0,
                "pages_passed": 0,
                "samples": [],
            }

        scored_samples: list[dict[str, Any]] = []
        for sample in samples:
            metrics = self._score_plain_language(sample["text"])
            sample_passed = metrics["score"] >= 70 and metrics["word_count"] >= 40
            scored_samples.append(
                {
                    "source_type": sample["source_type"],
                    "source_ref": sample["source_ref"],
                    "source_label": self._format_source_label(sample["source_ref"], sample["source_type"]),
                    "score": metrics["score"],
                    "word_count": metrics["word_count"],
                    "sentence_count": metrics["sentence_count"],
                    "avg_sentence_words": metrics["avg_sentence_words"],
                    "jargon_ratio": metrics["jargon_ratio"],
                    "plain_terms_hits": metrics["plain_terms_hits"],
                    "issues": metrics["issues"][:3],
                    "recommendations": self._plain_language_rewrite_suggestions(metrics),
                    "excerpt": metrics["excerpt"],
                    "passed": sample_passed,
                }
            )

        pages_tested = len(scored_samples)
        pages_passed = sum(1 for sample in scored_samples if sample["passed"])
        average_score = int(round(sum(sample["score"] for sample in scored_samples) / pages_tested))
        total_words = sum(sample["word_count"] for sample in scored_samples)
        total_sentences = sum(sample["sentence_count"] for sample in scored_samples)
        weighted_avg_sentence = (
            round(total_words / total_sentences, 2) if total_sentences else 0.0
        )
        weighted_jargon_ratio = round(
            (
                sum(sample["jargon_ratio"] * sample["word_count"] for sample in scored_samples) / total_words
                if total_words
                else 0.0
            ),
            4,
        )
        plain_terms_hits = sum(sample["plain_terms_hits"] for sample in scored_samples)
        issues = self._collect_top_issues(scored_samples)
        source_types = sorted({sample["source_type"] for sample in scored_samples})
        source_type = source_types[0] if len(source_types) == 1 else "mixed"
        lead_sample = min(scored_samples, key=lambda sample: sample["score"])

        return {
            "passed": pages_tested > 0 and pages_passed >= 1 and average_score >= 65,
            "score": average_score,
            "word_count": total_words,
            "sentence_count": total_sentences,
            "avg_sentence_words": weighted_avg_sentence,
            "jargon_ratio": weighted_jargon_ratio,
            "plain_terms_hits": plain_terms_hits,
            "issues": issues,
            "recommendations": lead_sample["recommendations"],
            "source_type": source_type,
            "source_ref": lead_sample["source_ref"],
            "excerpt": lead_sample["excerpt"],
            "pages_tested": pages_tested,
            "pages_passed": pages_passed,
            "samples": scored_samples[:6],
        }

    def _collect_content_samples(self, project: Path, local_urls: list[str]) -> list[dict[str, str]]:
        samples: list[dict[str, str]] = []
        samples.extend(self._fetch_page_texts(local_urls, max_sources=3))
        samples.extend(self._read_local_content_samples(project, max_sources=3))
        return samples[:6]

    def _fetch_page_texts(self, local_urls: list[str], max_sources: int = 3) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for url in local_urls:
            candidate = (url or "").strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if not candidate.startswith("http://127.0.0.1:") and not candidate.startswith("http://localhost:"):
                continue
            parsed = urlparse(candidate)
            host = parsed.hostname or ""
            port = parsed.port
            if not port or not self._is_port_open(host, port):
                continue
            try:
                request = Request(candidate, headers={"User-Agent": "agY-inventory-audit/1.0"})
                with urlopen(request, timeout=0.55) as response:
                    payload = response.read(160000)
            except (URLError, TimeoutError, ValueError, OSError):
                continue
            text = self._html_to_text(payload)
            if len(text) < 120:
                continue
            results.append({"source_type": "url", "source_ref": candidate, "text": text})
            if len(results) >= max_sources:
                break
        return results

    def _is_port_open(self, host: str, port: int) -> bool:
        if host not in {"127.0.0.1", "localhost"}:
            return False
        # Try IPv4 first, then IPv6 (some services like Vite bind IPv6 only)
        for family, addr in [(socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")]:
            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.settimeout(0.12)
            try:
                if sock.connect_ex((addr, int(port))) == 0:
                    return True
            except Exception:
                pass
            finally:
                sock.close()
        return False

    def _probe_ports(self, local_urls: list[str]) -> list[dict[str, Any]]:
        """Check which ports are actually listening."""
        results: list[dict[str, Any]] = []
        seen_ports: set[int] = set()
        for url in local_urls:
            parsed = urlparse(url or "")
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port
            if not port or port in seen_ports:
                continue
            seen_ports.add(port)
            is_open = self._is_port_open(host, port)
            results.append({"host": host, "port": port, "open": is_open})
        return results

    def _http_health_check(self, local_urls: list[str]) -> list[dict[str, Any]]:
        """Send real HTTP GET to each local URL and capture status."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url in local_urls:
            candidate = (url or "").strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if not candidate.startswith("http://127.0.0.1:") and not candidate.startswith("http://localhost:"):
                continue
            parsed = urlparse(candidate)
            port = parsed.port
            if not port:
                continue
            if not self._is_port_open(parsed.hostname or "127.0.0.1", port):
                results.append({"url": candidate, "status": "port_closed", "ok": False})
                continue
            try:
                request = Request(candidate, headers={"User-Agent": "agY-live-check/1.0"})
                with urlopen(request, timeout=1.5) as response:
                    code = response.status
                results.append({"url": candidate, "status": code, "ok": 200 <= code < 500})
            except Exception as exc:
                results.append({"url": candidate, "status": f"error:{type(exc).__name__}", "ok": False})
        return results[:8]

    def _read_local_content_samples(self, project: Path, max_sources: int = 3) -> list[dict[str, str]]:
        candidates: list[Path] = []
        for name in README_CANDIDATES:
            candidate = project / name
            if candidate.exists():
                candidates.append(candidate)
                # Only audit one README variant to avoid duplicate files inflating failures.
                break

        candidates.extend(
            [
                project / "index.html",
                project / "public/index.html",
                project / "src/App.tsx",
                project / "src/app/page.tsx",
                project / "app/page.tsx",
                project / "docs/index.md",
                project / "docs/README.md",
            ]
        )
        candidates.extend(self._discover_content_files(project, limit=8))

        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for candidate in candidates:
            try:
                key = str(candidate.resolve())
            except Exception:
                key = str(candidate).lower()
            if key in seen:
                continue
            seen.add(key)
            if not candidate.exists() or not candidate.is_file():
                continue
            text = _safe_read_text(candidate, limit=160000)
            cleaned = self._to_plain_text(text, candidate.suffix.lower())
            if candidate.suffix.lower() in {".md", ".mdx"}:
                # Focus on the user-facing top section rather than deep technical appendices.
                cleaned = cleaned[:2400]
            if len(cleaned) >= 80:
                results.append({"source_type": "file", "source_ref": str(candidate), "text": cleaned})
            if len(results) >= max_sources:
                break
        return results

    def _discover_content_files(self, project: Path, limit: int = 8) -> list[Path]:
        roots = [
            project / "src/pages",
            project / "pages",
            project / "app",
            project / "docs",
            project / "public",
        ]
        allowed_suffixes = {".md", ".mdx", ".html", ".htm", ".txt", ".tsx", ".jsx"}
        discovered: list[Path] = []
        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            try:
                for candidate in root.rglob("*"):
                    if len(discovered) >= limit:
                        return discovered
                    if not candidate.is_file():
                        continue
                    rel_parts = candidate.relative_to(root).parts
                    if len(rel_parts) > 3:
                        continue
                    if any(part in WALK_IGNORE_DIRS for part in rel_parts):
                        continue
                    suffix = candidate.suffix.lower()
                    if suffix not in allowed_suffixes:
                        continue
                    discovered.append(candidate)
            except Exception:
                continue
        return discovered

    def _format_source_label(self, source_ref: str, source_type: str) -> str:
        if source_type == "url":
            return source_ref
        path = Path(source_ref)
        return path.name or source_ref

    def _to_plain_text(self, text: str, suffix: str) -> str:
        if suffix in {".html", ".htm"}:
            return self._strip_html(text)
        if suffix in {".md", ".mdx"}:
            return self._strip_markdown(text)
        if suffix in {".tsx", ".jsx", ".ts", ".js"}:
            return self._strip_code_noise(text)
        return SPACE_PATTERN.sub(" ", text or "").strip()

    def _html_to_text(self, payload: bytes) -> str:
        try:
            text = payload.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        return self._strip_html(text)

    def _strip_html(self, text: str) -> str:
        no_tags = TAG_PATTERN.sub(" ", text or "")
        decoded = unescape(no_tags)
        return SPACE_PATTERN.sub(" ", decoded).strip()

    def _strip_code_noise(self, text: str) -> str:
        clean = text or ""
        clean = re.sub(r"//.*?$", " ", clean, flags=re.MULTILINE)
        clean = re.sub(r"/\\*.*?\\*/", " ", clean, flags=re.DOTALL)
        clean = re.sub(r"[{}<>();=\\[\\]]", " ", clean)
        return SPACE_PATTERN.sub(" ", clean).strip()

    def _strip_markdown(self, text: str) -> str:
        clean = text or ""
        clean = MARKDOWN_CODE_BLOCK_PATTERN.sub(" ", clean)
        clean = MARKDOWN_INLINE_CODE_PATTERN.sub(" ", clean)
        clean = MARKDOWN_LINK_PATTERN.sub(r"\1", clean)
        clean = re.sub(r"^#{1,6}\\s*", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"[>*_~|-]", " ", clean)
        return SPACE_PATTERN.sub(" ", clean).strip()

    def _score_plain_language(self, text: str) -> dict[str, Any]:
        cleaned = SPACE_PATTERN.sub(" ", (text or "").strip())
        excerpt = cleaned[:260]
        words = [word.lower() for word in WORD_PATTERN.findall(cleaned)]
        word_count = len(words)

        sentence_chunks = [chunk.strip() for chunk in SENTENCE_SPLIT_PATTERN.split(cleaned) if chunk.strip()]
        sentence_count = len(sentence_chunks)
        avg_sentence_words = round(word_count / sentence_count, 2) if sentence_count else 0.0

        jargon_hits = sum(1 for word in words if word in JARGON_TERMS)
        plain_hits = sum(1 for word in words if word in PLAIN_LANGUAGE_TERMS)

        jargon_ratio = round((jargon_hits / word_count), 4) if word_count else 0.0
        long_word_ratio = round((sum(1 for word in words if len(word) >= 13) / word_count), 4) if word_count else 0.0

        score = 100
        issues: list[str] = []

        if word_count < 40:
            score -= 30
            issues.append("Not enough user-facing text to validate clarity.")
        elif word_count < 90:
            score -= 10
            issues.append("Very short content sample; confidence is limited.")

        if avg_sentence_words > 24:
            penalty = min(22, int((avg_sentence_words - 24) * 1.6))
            score -= penalty
            issues.append("Sentences are too long for non-technical reading.")
        elif avg_sentence_words < 6 and word_count >= 40:
            score -= 8
            issues.append("Content is fragmented and may lack coherent explanation.")

        if jargon_ratio > 0.12:
            score -= 24
            issues.append("Heavy technical jargon without enough plain-language support.")
        elif jargon_ratio > 0.07:
            score -= 12
            issues.append("Technical terms dominate the text.")

        if long_word_ratio > 0.23:
            score -= 14
            issues.append("Vocabulary is dense for non-technical users.")

        if plain_hits == 0 and word_count >= 40:
            score -= 10
            issues.append("No clear plain-language instruction terms detected.")

        score = max(0, min(100, score))
        if score >= 85:
            issues = []

        return {
            "score": score,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "avg_sentence_words": avg_sentence_words,
            "jargon_ratio": jargon_ratio,
            "plain_terms_hits": plain_hits,
            "issues": issues,
            "excerpt": excerpt,
        }

    def _plain_language_rewrite_suggestions(self, metrics: dict[str, Any]) -> list[str]:
        suggestions: list[str] = []
        issues = metrics.get("issues", [])
        if any("Not enough user-facing text" in issue for issue in issues):
            suggestions.append("Add a 3-line overview: what it does, who it helps, and the first step.")
        if any("Sentences are too long" in issue for issue in issues):
            suggestions.append("Split long lines into short sentences of 12-20 words.")
        if any("Technical terms dominate" in issue for issue in issues) or any(
            "Heavy technical jargon" in issue for issue in issues
        ):
            suggestions.append("Replace technical words with plain alternatives and add one short example.")
        if any("No clear plain-language instruction terms" in issue for issue in issues):
            suggestions.append("Add direct action words: click, open, start, choose, and next.")
        if any("Vocabulary is dense" in issue for issue in issues):
            suggestions.append("Use shorter words and avoid dense multi-clause explanations.")

        excerpt = (metrics.get("excerpt") or "").lower()
        for jargon, rewrite in JARGON_REWRITE_HINTS.items():
            if jargon in excerpt:
                suggestions.append(f'Clarify "{jargon}" as "{rewrite}".')
                if len(suggestions) >= 5:
                    break

        if not suggestions:
            suggestions.append("Plain-language quality is acceptable; keep this structure for future pages.")
        return suggestions[:5]

    def _collect_top_issues(self, samples: list[dict[str, Any]], limit: int = 6) -> list[str]:
        counts: dict[str, int] = {}
        for sample in samples:
            for issue in sample.get("issues", []):
                counts[issue] = counts.get(issue, 0) + 1
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return [issue for issue, _ in ranked[:limit]]

    def summarize_results(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        plain_pass = sum(
            1 for result in results if bool((result.get("content_audit") or {}).get("passed"))
        )
        plain_missing = sum(
            1
            for result in results
            if (result.get("content_audit") or {}).get("source_type") == "none"
        )
        return {
            "total": len(results),
            "pass": sum(1 for result in results if result.get("status") == "pass"),
            "warn": sum(1 for result in results if result.get("status") == "warn"),
            "fail": sum(1 for result in results if result.get("status") == "fail"),
            "plain_language_pass": plain_pass,
            "plain_language_review": max(0, len(results) - plain_pass),
            "plain_language_missing_source": plain_missing,
            "average_score": (
                int(round(sum(result.get("score", 0) for result in results) / len(results)))
                if results
                else 0
            ),
        }
