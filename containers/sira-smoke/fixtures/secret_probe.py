"""Dummy-secret presence probe; it records names and booleans, never values."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path


def main() -> None:
    if not os.environ.get("SIRA_API_KEY"):
        raise RuntimeError("SIRA_API_KEY was not exported to the child")
    if "OPENAI_API_KEY" in os.environ:
        raise RuntimeError("OPENAI_API_KEY fallback reached the child")
    Path("/giclab/attempt/dummy-secret-probe.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "required_secret_name": "SIRA_API_KEY",
                "required_secret_present": True,
                "forbidden_fallback_present": False,
                "runtime_uid": os.getuid(),
                "runtime_gid": os.getgid(),
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
