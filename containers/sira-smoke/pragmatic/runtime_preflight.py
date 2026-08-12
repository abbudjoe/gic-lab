#!/usr/bin/env python3
"""No-network exact-runtime preflight for the pragmatic T07 container."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_PYTHON = (3, 11, 14)
UPSTREAM_RUNNER = Path("/opt/sira/scripts/run_web_agent.py")
UPSTREAM_RUNNER_SHA256 = "b06793ad1b366a934b798f9f3272fc80a7104a220cb3304ab3bda2eb2a78b331"
RUNTIME_MODULES = (
    "giclab.registry",
    "giclab.harness.artifacts",
    "giclab.harness.budget",
    "giclab.harness.events",
    "giclab.harness.executor",
    "giclab.harness.models",
    "giclab.harness.plan",
    "giclab.harness.policy",
    "giclab.harness.regulation",
    "giclab.harness.safety",
    "giclab.harness.sira_container",
    "giclab.harness.sira_gate_a",
    "giclab.harness.sira_gate_a_runtime",
)


def _write_json_exclusive(path: Path, document: object) -> None:
    encoded = json.dumps(document, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n"
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise RuntimeError("runtime-preflight evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def load_pinned_upstream_runner(
    runner_path: Path,
    import_cwd: Path,
    *,
    expected_sha256: str,
) -> dict[str, object]:
    """Load the pinned entry module without invoking its main/browser/provider paths."""

    path = runner_path.resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("pinned upstream runner path is unsafe")
    observed_sha256 = _sha256_file(path)
    if observed_sha256 != expected_sha256:
        raise RuntimeError("pinned upstream runner digest drifted")
    if any(name in os.environ for name in ("LAMBDA_API_KEY", "OPENAI_API_KEY", "SIRA_API_KEY")):
        raise RuntimeError("upstream import probe inherited a forbidden credential")
    controlled_cwd = import_cwd.resolve(strict=True)
    if not controlled_cwd.is_dir() or controlled_cwd.is_symlink():
        raise RuntimeError("upstream import working directory is unsafe")

    module_name = "giclab_t07_pragmatic_pinned_runner_preflight"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("pinned upstream runner import spec is unavailable")
    module = importlib.util.module_from_spec(spec)
    previous_cwd = Path.cwd()
    sys.modules[module_name] = module
    try:
        os.chdir(controlled_cwd)
        spec.loader.exec_module(module)
    finally:
        os.chdir(previous_cwd)
        sys.modules.pop(module_name, None)
    required_callables = ("main", "make_agent", "make_llm", "run_episode")
    if any(not callable(getattr(module, name, None)) for name in required_callables):
        raise RuntimeError("pinned upstream runner entry surface is incomplete")
    if any(controlled_cwd.iterdir()):
        raise RuntimeError("pinned upstream runner import wrote unexpected files")
    return {
        "path": str(path),
        "sha256": observed_sha256,
        "module": module_name,
        "required_callables": list(required_callables),
        "status": "passed",
        "network_mode": "none",
        "browser_or_model_action": False,
    }


def run(attempt_root: Path) -> dict[str, object]:
    root = attempt_root.resolve(strict=True)
    if sys.version_info[:3] != EXPECTED_PYTHON:
        raise RuntimeError(
            f"runtime Python must be exactly {'.'.join(map(str, EXPECTED_PYTHON))}; "
            f"observed {platform.python_version()}"
        )

    imported = []
    for name in RUNTIME_MODULES:
        importlib.import_module(name)
        imported.append(name)

    upstream_import_cwd = root / "upstream-import-cwd"
    upstream_import_cwd.mkdir(mode=0o700)
    upstream_runner = load_pinned_upstream_runner(
        UPSTREAM_RUNNER,
        upstream_import_cwd,
        expected_sha256=UPSTREAM_RUNNER_SHA256,
    )
    upstream_import_cwd.rmdir()

    from giclab.harness.artifacts import (
        ArtifactRecordWriter,
        artifact_record,
    )
    from giclab.harness.executor import render_command
    from giclab.harness.models import CommandSpec
    from giclab.harness.sira_gate_a import (
        ImmutableModelRouting,
        ProviderBudgetBoundary,
        aggregate_caps,
        condition_caps,
    )
    from giclab.harness.sira_gate_a_runtime import _write_usage_ledger

    timestamp = datetime.now(timezone.utc)  # noqa: UP017 -- Python 3.10 import-smoke parses this file.
    offset = timestamp.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise RuntimeError("runtime timestamp is not UTC aware")
    timestamp_text = timestamp.isoformat().replace("+00:00", "Z")
    python_executable = Path(sys.executable).resolve(strict=True)
    python_digest = hashlib.sha256(python_executable.read_bytes()).hexdigest()

    probe = root / "evidence-writer-probe.txt"
    payload = b"T07 runtime evidence probe\n"
    descriptor = os.open(
        probe,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        if os.write(descriptor, payload) != len(payload):
            raise RuntimeError("short evidence probe write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if probe.read_bytes() != payload:
        raise RuntimeError("evidence probe readback failed")
    record = artifact_record(probe, kind="runtime-preflight", relative_to=root)
    ArtifactRecordWriter(root).append(record)

    budget_path = root / "budget-ledger-probe.json"
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=condition_caps("reactive"),
        persist=lambda usage, unreconciled: _write_usage_ledger(budget_path, usage, unreconciled),
    )
    boundary.record_output_bytes(len(payload))
    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    if budget.get("model_call_attempts") != 0 or budget.get("output_bytes") != len(payload):
        raise RuntimeError("budget-ledger probe did not reconcile")

    command_input = json.loads((root / "condition-commands-input.json").read_text(encoding="utf-8"))
    commands = command_input.get("commands") if isinstance(command_input, dict) else None
    if not isinstance(commands, dict) or set(commands) != {"reactive", "simulative"}:
        raise RuntimeError("both condition commands are required for runtime rendering")
    rendered_hashes: dict[str, str] = {}
    for mode in ("reactive", "simulative"):
        argv = commands.get(mode)
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(part, str) or not part for part in argv)
        ):
            raise RuntimeError(f"{mode} command input is invalid")
        rendered = render_command(CommandSpec(argv=tuple(argv), cwd=root, timeout_seconds=150))
        rendered_argv = rendered.get("argv")
        if (
            not isinstance(rendered_argv, list)
            or rendered_argv[1:] != argv[1:]
            or rendered_argv[0] != str(Path(argv[0]).resolve(strict=True))
        ):
            raise RuntimeError(f"{mode} command renderer probe drifted")
        rendered_hashes[mode] = hashlib.sha256(
            (json.dumps(rendered, allow_nan=False, sort_keys=True) + "\n").encode()
        ).hexdigest()

    cleanup_root = root / "cleanup-probe"
    cleanup_root.mkdir(mode=0o700)
    cleanup_file = cleanup_root / "owned.tmp"
    cleanup_file.write_bytes(b"owned\n")
    cleanup_file.unlink()
    cleanup_root.rmdir()
    if cleanup_root.exists():
        raise RuntimeError("cleanup probe left owned residue")

    document: dict[str, object] = {
        "schema_version": "0.1.0",
        "python_executable": sys.executable,
        "python_executable_sha256": python_digest,
        "python_version": platform.python_version(),
        "python_contract": ">=3.11",
        "utc_timestamp": timestamp_text,
        "utc_offset_seconds": 0,
        "runtime_modules_imported": imported,
        "upstream_runner_import": upstream_runner,
        "artifact_writer": "passed",
        "artifact_record_path": record.path,
        "budget_ledger": "passed",
        "condition_command_renderer": "passed",
        "rendered_condition_command_sha256": rendered_hashes,
        "owned_cleanup": "passed",
    }
    _write_json_exclusive(root / "runtime-preflight.json", document)
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-root", type=Path, required=True)
    args = parser.parse_args()
    document = run(args.attempt_root)
    print(json.dumps(document, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
