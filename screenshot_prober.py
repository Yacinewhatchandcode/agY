"""
Screenshot prober — captures browser screenshots of live services using Playwright.
Runs Playwright in a subprocess to avoid sync/async conflicts with uvicorn.
Screenshots saved to static/screenshots/.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import json
from pathlib import Path

log = logging.getLogger(__name__)

SCREENSHOT_DIR = Path(__file__).parent / "static" / "screenshots"

# Inline script executed by subprocess
_CAPTURE_SCRIPT = '''
import sys, json
from playwright.sync_api import sync_playwright

url = sys.argv[1]
output_path = sys.argv[2]

try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(url, timeout=4000, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        page.screenshot(path=output_path, full_page=False)
        browser.close()
    print(json.dumps({"ok": True, "path": output_path}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
'''


def capture(url: str, solution_id: str, timeout_s: int = 12) -> str | None:
    """
    Spawn a subprocess to capture a screenshot via Playwright.
    Returns the relative URL path for serving (e.g. /static/screenshots/abc.png)
    or None on failure.
    """
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in solution_id)
    filename = f"{safe_id}.png"
    filepath = SCREENSHOT_DIR / filename

    try:
        result = subprocess.run(
            [sys.executable, "-c", _CAPTURE_SCRIPT, url, str(filepath)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if data.get("ok") and filepath.exists():
                log.info("Screenshot captured: %s -> %s", url, filepath)
                return f"/static/screenshots/{filename}"
            else:
                log.warning("Screenshot subprocess reported failure: %s", data.get("error", "unknown"))
        else:
            log.warning("Screenshot subprocess failed (rc=%d): %s", result.returncode, result.stderr[:200])
    except subprocess.TimeoutExpired:
        log.warning("Screenshot timed out for %s after %ds", url, timeout_s)
    except Exception as exc:
        log.warning("Screenshot capture error for %s: %s", url, exc)

    # Clean up partial file
    if filepath.exists():
        try:
            filepath.unlink()
        except OSError:
            pass
    return None
