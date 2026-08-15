"""No-network Chromium lifecycle fixture for the future bounded smoke."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import resource
import stat
from pathlib import Path

from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]

ATTEMPT_ROOT = Path("/giclab/attempt")
WRITABLE_CORE_SCAN_ROOTS = (ATTEMPT_ROOT, Path("/tmp"), Path("/dev/shm"))
STATIC_PAGE = Path("/opt/giclab/fixtures/static.html")
PACKAGE_MANIFEST = Path("/opt/giclab/installed-packages.txt")
MAX_SCAN_ENTRIES = 100_000


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


def _elf_type(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    with path.open("rb") as handle:
        header = handle.read(18)
    if len(header) < 18 or header[:4] != b"\x7fELF":
        return None
    byteorder = "little" if header[5] == 1 else "big" if header[5] == 2 else None
    if byteorder is None:
        return None
    return "ET_CORE" if int.from_bytes(header[16:18], byteorder) == 4 else None


def _core_scan() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    observed = 0
    for root in WRITABLE_CORE_SCAN_ROOTS:
        if not root.is_dir() or root.is_symlink():
            raise RuntimeError("browser writable-root core scan root is unsafe")
        for path in sorted(root.rglob("*")):
            observed += 1
            if observed > MAX_SCAN_ENTRIES:
                raise RuntimeError("browser writable-root core scan exceeded its entry cap")
            metadata = path.lstat()
            lowered_name = path.name.lower()
            named = lowered_name == "core" or lowered_name.startswith("core.")
            elf_core = stat.S_ISREG(metadata.st_mode) and _elf_type(path) == "ET_CORE"
            if not named and not elf_core:
                continue
            records.append(
                {
                    "artifact": f"<browser-core-artifact-{len(records) + 1:04d}>",
                    "writable_root": str(root),
                    "bytes": metadata.st_size,
                    "known_core_filename": named,
                    "elf_et_core": elf_core,
                    "content_or_hash_retained": False,
                }
            )
    return records


def _chromium_process_count() -> int:
    count = 0
    proc = Path("/proc")
    if not proc.is_dir():
        raise RuntimeError("browser process accounting requires procfs")
    for process in proc.iterdir():
        if not process.name.isdigit():
            continue
        try:
            command = (process / "comm").read_text(encoding="utf-8").strip().lower()
        except (FileNotFoundError, PermissionError, UnicodeError):
            continue
        if "chrom" in command:
            count += 1
    return count


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
        page.close()
        context.close()
        browser.close()
        chromium_process_count = _chromium_process_count()
        core_records = _core_scan()
        _write_exclusive(
            ATTEMPT_ROOT / "browser-writable-root-core-scan.json",
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "scan_roots": [str(root) for root in WRITABLE_CORE_SCAN_ROOTS],
                    "core_artifact_count": len(core_records),
                    "core_artifacts": core_records,
                    "core_content_or_hash_retained": False,
                },
                allow_nan=False,
                indent=2,
                sort_keys=True,
            ).encode()
            + b"\n",
        )
        record = {
            "schema_version": "0.1.0",
            "source": "local-static-file",
            "network_mode": "none",
            "browser_actions": 1,
            "screenshot_captures": 1,
            "title": title,
            "screenshot": screenshot.name,
            "browser_running_before_container_stop": False,
            "browser_closed_by_fixture": True,
            "chromium_process_count_after_close": chromium_process_count,
            "writable_root_core_artifact_count": len(core_records),
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
        if chromium_process_count or core_records:
            raise RuntimeError("browser teardown left a process or prohibited core artifact")


if __name__ == "__main__":
    main()
