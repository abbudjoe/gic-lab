#!/usr/bin/env python3
"""No-network proof that the exact pilot process tree cannot create core dumps."""

from __future__ import annotations

import argparse
import json
import os
import resource
import signal
import stat
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ATTEMPT_ROOT = Path("/giclab/attempt")
TMP_ROOT = Path("/tmp")
SHM_ROOT = Path("/dev/shm")
RECEIPT_PATH = ATTEMPT_ROOT / "core-suppression-preflight.json"
MAX_CHILD_OUTPUT_BYTES = 16_384
MAX_SCAN_ENTRIES = 100_000


def enforce_zero_core_limit() -> tuple[int, int]:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    limits = resource.getrlimit(resource.RLIMIT_CORE)
    if limits != (0, 0):
        raise RuntimeError("RLIMIT_CORE is not exactly (0, 0)")
    return limits


def _write_exclusive(path: Path, value: object) -> None:
    encoded = (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
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
                raise RuntimeError("core-preflight receipt write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _child(depth: int) -> int:
    # Do not repair the limit in the descendant: this branch is the inheritance
    # proof.  The exact container boundary and entrypoint must already have made
    # the zero limit irrevocable for the process tree.
    limits = resource.getrlimit(resource.RLIMIT_CORE)
    if limits != (0, 0):
        raise RuntimeError("core-limit inheritance child did not inherit zero")
    child: dict[str, object] | None = None
    if depth < 2:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--inheritance-child", str(depth + 1)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
        if result.returncode != 0 or len(result.stdout) > MAX_CHILD_OUTPUT_BYTES:
            raise RuntimeError("core-limit inheritance child failed")
        decoded: object = json.loads(result.stdout)
        if not isinstance(decoded, dict):
            raise RuntimeError("core-limit inheritance receipt is malformed")
        child = decoded
    sys.stdout.write(
        json.dumps(
            {
                "depth": depth,
                "core_soft_limit": limits[0],
                "core_hard_limit": limits[1],
                "child": child,
            },
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


def _abort_child() -> int:
    if resource.getrlimit(resource.RLIMIT_CORE) != (0, 0):
        raise RuntimeError("synthetic abort child did not inherit the zero core limit")
    os.abort()
    raise AssertionError("os.abort returned")


def _elf_type(path: Path) -> str | None:
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            return None
        header = os.read(descriptor, 18)
    finally:
        os.close(descriptor)
    if len(header) < 18 or header[:4] != b"\x7fELF":
        return None
    byteorder = "little" if header[5] == 1 else "big" if header[5] == 2 else None
    if byteorder is None:
        return None
    return "ET_CORE" if int.from_bytes(header[16:18], byteorder) == 4 else None


def _core_scan() -> list[dict[str, object]]:
    """Inspect every writable container root without retaining path or content values."""

    records: list[dict[str, object]] = []
    observed = 0
    for root in (ATTEMPT_ROOT, TMP_ROOT, SHM_ROOT):
        if not root.is_dir() or root.is_symlink():
            raise RuntimeError("core-preflight writable root is unavailable or unsafe")
        for path in sorted(root.rglob("*")):
            observed += 1
            if observed > MAX_SCAN_ENTRIES:
                raise RuntimeError("core-preflight writable-root scan exceeded its entry cap")
            metadata = path.lstat()
            lowered_name = path.name.lower()
            named = lowered_name == "core" or lowered_name.startswith("core.")
            elf_core = stat.S_ISREG(metadata.st_mode) and _elf_type(path) == "ET_CORE"
            if not named and not elf_core:
                continue
            records.append(
                {
                    "artifact": f"<core-preflight-artifact-{len(records) + 1:04d}>",
                    "writable_root": str(root),
                    "bytes": metadata.st_size,
                    "known_core_filename": named,
                    "elf_et_core": elf_core,
                    "content_or_hash_retained": False,
                }
            )
    return records


def _run_suite() -> int:
    if not ATTEMPT_ROOT.is_dir() or ATTEMPT_ROOT.is_symlink():
        raise RuntimeError("core-preflight output root is unsafe")
    limits = enforce_zero_core_limit()
    inherited = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--inheritance-child", "1"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if inherited.returncode != 0 or len(inherited.stdout) > MAX_CHILD_OUTPUT_BYTES:
        raise RuntimeError("core-limit inheritance test failed")
    inheritance: object = json.loads(inherited.stdout)
    if not isinstance(inheritance, dict):
        raise RuntimeError("core-limit inheritance evidence is malformed")
    abort = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--abort-child"],
        cwd=ATTEMPT_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if abort.returncode == 0:
        raise RuntimeError("synthetic SIGABRT unexpectedly succeeded")
    signal_number = -abort.returncode if abort.returncode < 0 else None
    if signal_number not in {signal.SIGABRT, None}:
        raise RuntimeError("synthetic abort returned an unexpected signal")
    core_records = _core_scan()
    scan_path = ATTEMPT_ROOT / "core-suppression-writable-root-core-scan.json"
    _write_exclusive(
        scan_path,
        {
            "schema_version": "0.1.0",
            "scan_roots": [str(ATTEMPT_ROOT), str(TMP_ROOT), str(SHM_ROOT)],
            "core_artifact_count": len(core_records),
            "core_artifacts": core_records,
            "core_content_or_hash_retained": False,
        },
    )
    _write_exclusive(
        RECEIPT_PATH,
        {
            "schema_version": "0.1.0",
            "core_limit_contract": "process-tree-rlimit-core-zero-v1",
            "core_soft_limit": limits[0],
            "core_hard_limit": limits[1],
            "inheritance": inheritance,
            "synthetic_abort_returncode": abort.returncode,
            "synthetic_abort_nonzero": True,
            "synthetic_abort_signal": "SIGABRT" if signal_number == signal.SIGABRT else None,
            "writable_root_core_artifact_count": len(core_records),
            "writable_root_core_scan": scan_path.name,
            "network_required": False,
            "credential_required": False,
        },
    )
    if core_records:
        raise RuntimeError("synthetic abort produced a prohibited core artifact")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--inheritance-child", type=int)
    modes.add_argument("--abort-child", action="store_true")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.abort_child:
        return _abort_child()
    if args.inheritance_child is not None:
        if args.inheritance_child not in {1, 2}:
            raise RuntimeError("inheritance depth is outside the test contract")
        return _child(args.inheritance_child)
    return _run_suite()


if __name__ == "__main__":
    raise SystemExit(run())
