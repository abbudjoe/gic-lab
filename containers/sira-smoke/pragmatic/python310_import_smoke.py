#!/usr/bin/env python3
"""Import the pragmatic host-side layer under the Lambda host's Python 3.10."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if sys.version_info[:2] != (3, 10):
        raise RuntimeError(f"expected Python 3.10, observed {sys.version}")
    repository = Path(__file__).resolve().parents[3]
    modules = {
        "t07_pragmatic_remote_runner_py310": (
            repository / "containers/sira-smoke/pragmatic/remote_runner.py"
        ),
        "t07_pragmatic_secret_py310": (
            repository / "containers/sira-smoke/pragmatic/materialize_openai_secret.py"
        ),
        "t07_container_entrypoint_py310": (
            repository / "containers/sira-smoke/container_entrypoint.py"
        ),
        "t07_model_preflight_py310": (
            repository / "containers/sira-smoke/bounded/model_preflight.py"
        ),
        "t07_runtime_preflight_loader_py310": (
            repository / "containers/sira-smoke/pragmatic/runtime_preflight.py"
        ),
    }
    loaded = {name: _load(name, path) for name, path in modules.items()}
    timestamp = loaded["t07_pragmatic_remote_runner_py310"].utc_now()
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise RuntimeError("Python 3.10 host UTC timestamp semantics drifted")
    print(f"python={sys.version.split()[0]} modules={len(loaded)} utc={timestamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
