"""Local-only Playwright shutdown preflight for a future Gate B2 probe."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    attempt_root = Path("/giclab/attempt")
    page_uri = Path("/opt/giclab/fixtures/static.html").as_uri()
    screenshot = attempt_root / "browser-preflight.png"
    record = attempt_root / "browser-preflight.json"
    package_manifest = Path("/opt/giclab/installed-packages.txt")
    with sync_playwright() as playwright:
        executable = Path(playwright.chromium.executable_path).resolve(strict=True)
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.goto(page_uri)
        page.screenshot(path=str(screenshot))
        title = page.title()
        browser_version = browser.version
        context.close()
        browser.close()
    chromium_digest = hashlib.sha256()
    with executable.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            chromium_digest.update(chunk)
    record.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "source": "local-static-file",
                "page_uri": page_uri,
                "browser_actions": 1,
                "screenshot_captures": 1,
                "title": title,
                "screenshot": screenshot.name,
                "browser_closed": True,
                "runtime_uid": os.getuid(),
                "runtime_gid": os.getgid(),
                "playwright_version": importlib.metadata.version("playwright"),
                "chromium_revision": executable.parent.parent.name.removeprefix("chromium-"),
                "chromium_browser_version": browser_version,
                "chromium_executable_sha256": chromium_digest.hexdigest(),
                "installed_package_manifest_sha256": hashlib.sha256(
                    package_manifest.read_bytes()
                ).hexdigest(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    while True:
        time.sleep(10)


if __name__ == "__main__":
    main()
