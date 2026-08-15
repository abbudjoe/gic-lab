"""No-network Chromium lifecycle fixture for the future bounded smoke."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import resource
import time
from pathlib import Path

from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]

ATTEMPT_ROOT = Path("/giclab/attempt")
STATIC_PAGE = Path("/opt/giclab/fixtures/static.html")
PACKAGE_MANIFEST = Path("/opt/giclab/installed-packages.txt")


def _enforce_zero_core_limit() -> tuple[int, int]:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    limits = resource.getrlimit(resource.RLIMIT_CORE)
    if limits != (0, 0):
        raise RuntimeError("browser process-tree core limit is not exactly zero")
    return limits


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def _write_exclusive(path: Path, encoded: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise RuntimeError("browser evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> None:
    core_limits = _enforce_zero_core_limit()
    if "SIRA_API_KEY" in os.environ or "OPENAI_API_KEY" in os.environ:
        raise RuntimeError("browser preflight inherited a forbidden model credential")
    if not ATTEMPT_ROOT.is_dir() or ATTEMPT_ROOT.is_symlink():
        raise RuntimeError("browser preflight attempt root is unsafe")
    screenshot = ATTEMPT_ROOT / "browser-preflight.png"
    page_uri = STATIC_PAGE.resolve(strict=True).as_uri()
    with sync_playwright() as playwright:
        executable = Path(playwright.chromium.executable_path).resolve(strict=True)
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.goto(page_uri)
        page.screenshot(path=str(screenshot))
        title = page.title()
        browser_version = browser.version
        package_bytes = PACKAGE_MANIFEST.read_bytes()
        _write_exclusive(ATTEMPT_ROOT / "installed-packages.txt", package_bytes)
        record = {
            "schema_version": "0.1.0",
            "source": "local-static-file",
            "network_mode": "none",
            "browser_actions": 1,
            "screenshot_captures": 1,
            "title": title,
            "screenshot": screenshot.name,
            "browser_running_before_container_stop": True,
            "browser_closed_by_fixture": False,
            "runtime_uid": os.getuid(),
            "runtime_gid": os.getgid(),
            "playwright_version": importlib.metadata.version("playwright"),
            "chromium_revision": executable.parent.parent.name.removeprefix("chromium-"),
            "chromium_browser_version": browser_version,
            "chromium_executable_sha256": _sha256(executable),
            "installed_package_manifest_sha256": hashlib.sha256(package_bytes).hexdigest(),
            "core_soft_limit": core_limits[0],
            "core_hard_limit": core_limits[1],
        }
        _write_exclusive(
            ATTEMPT_ROOT / "browser-preflight.json",
            json.dumps(record, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n",
        )
        while True:
            time.sleep(10)


if __name__ == "__main__":
    main()
