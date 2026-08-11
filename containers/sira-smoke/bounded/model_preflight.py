"""One-shot, secret-safe availability check for the bound OpenAI model snapshot."""

from __future__ import annotations

import http.client
import json
import os
import ssl
from pathlib import Path

HOST = "api.openai.com"
MODEL = "gpt-4o-2024-11-20"
PATH = f"/v1/models/{MODEL}"
OUTPUT = Path("/giclab/attempt/model-availability.json")
MAX_RESPONSE_BYTES = 65_536


def _write_exclusive(path: Path, encoded: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    if "OPENAI_API_KEY" in os.environ:
        raise RuntimeError("OPENAI_API_KEY fallback is forbidden")
    credential = os.environ.pop("SIRA_API_KEY", None)
    if not credential:
        raise RuntimeError("SIRA_API_KEY is unavailable")
    connection = http.client.HTTPSConnection(
        HOST,
        timeout=15,
        context=ssl.create_default_context(),
    )
    try:
        connection.request(
            "GET",
            PATH,
            headers={
                "Authorization": f"Bearer {credential}",
                "Accept": "application/json",
                "User-Agent": "gic-lab-t07-bounded-smoke/1",
            },
        )
        response = connection.getresponse()
        body = response.read(MAX_RESPONSE_BYTES + 1)
    finally:
        credential = ""
        connection.close()
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("model-availability response exceeded its cap")
    if response.status != 200 or response.getheader("Location") is not None:
        raise RuntimeError("model snapshot was not authoritatively available")
    if response.getheader("Content-Type", "").split(";", 1)[0].strip() != "application/json":
        raise RuntimeError("model-availability response content type drifted")
    try:
        document = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("model-availability response was not JSON") from None
    if not isinstance(document, dict) or document.get("id") != MODEL:
        raise RuntimeError("model-availability response identity drifted")
    if not OUTPUT.parent.is_dir() or OUTPUT.parent.is_symlink():
        raise RuntimeError("model-availability evidence root is unsafe")
    _write_exclusive(
        OUTPUT,
        (
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "method": "GET",
                    "scheme": "https",
                    "host": HOST,
                    "path": PATH,
                    "http_status": response.status,
                    "response_bytes": len(body),
                    "model": MODEL,
                    "available": True,
                    "retry_count": 0,
                    "redirect_follow_count": 0,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
