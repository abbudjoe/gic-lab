#!/usr/bin/env python3
"""Collect only allowlisted Gate L2M host facts with bounded, shell-free calls."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
from pathlib import Path


class HostFactError(RuntimeError):
    pass


def _read_bounded_no_follow(path: Path, *, maximum_bytes: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        identity = os.fstat(descriptor)
        if not stat.S_ISREG(identity.st_mode) or identity.st_size > maximum_bytes:
            raise HostFactError("runtime residue evidence file is unsafe")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise HostFactError("runtime residue evidence exceeds its cap")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def scan_owned_runtime_residue(
    container_id: str,
    *,
    proc_root: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
) -> dict[str, object]:
    """Bounded in-process scan for a removed container's process/cgroup identity."""

    if re.fullmatch(r"[a-f0-9]{64}", container_id) is None:
        raise HostFactError("runtime residue scan identity is invalid")
    identity = container_id.encode()
    scanned_processes = 0
    matched_processes = 0
    scanned_bytes = 0
    try:
        process_entries = sorted(proc_root.iterdir(), key=lambda item: item.name)
    except OSError:
        raise HostFactError("process residue root is unavailable") from None
    for entry in process_entries:
        if not entry.name.isdecimal():
            continue
        scanned_processes += 1
        if scanned_processes > 131_072:
            raise HostFactError("process residue scan entry cap exceeded")
        matched = False
        for name in ("cmdline", "cgroup"):
            try:
                encoded = _read_bounded_no_follow(entry / name, maximum_bytes=65_536)
            except FileNotFoundError:
                continue
            except (OSError, HostFactError):
                raise HostFactError("process residue evidence is unreadable") from None
            scanned_bytes += len(encoded)
            if scanned_bytes > 8_388_608:
                raise HostFactError("process residue scan byte cap exceeded")
            matched = matched or identity in encoded
        matched_processes += int(matched)

    scanned_cgroup_entries = 0
    matched_cgroups = 0

    def fail_walk(error: OSError) -> None:
        del error
        raise HostFactError("cgroup residue evidence is unreadable")

    try:
        for current, directories, files in os.walk(
            cgroup_root,
            followlinks=False,
            onerror=fail_walk,
        ):
            del files
            current_path = Path(current)
            for name in directories:
                scanned_cgroup_entries += 1
                if scanned_cgroup_entries > 262_144:
                    raise HostFactError("cgroup residue scan entry cap exceeded")
                if container_id in str(current_path / name):
                    matched_cgroups += 1
    except OSError:
        raise HostFactError("cgroup residue root is unavailable") from None
    summary = {
        "matched_cgroup_count": matched_cgroups,
        "matched_process_count": matched_processes,
        "scanned_cgroup_entries": scanned_cgroup_entries,
        "scanned_process_count": scanned_processes,
    }
    return {
        **summary,
        "scan_sha256": hashlib.sha256(
            json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def _os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    encoded = path.read_bytes()
    if len(encoded) > 65_536:
        raise HostFactError("os-release exceeds its cap")
    values: dict[str, str] = {}
    for raw_line in encoded.decode("utf-8", "strict").splitlines():
        if not raw_line or raw_line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def _cgroup_mode() -> str:
    controllers = Path("/sys/fs/cgroup/cgroup.controllers")
    legacy = Path("/proc/cgroups")
    if controllers.is_file():
        text = Path("/proc/1/cgroup").read_text(encoding="utf-8")
        return "hybrid" if any(line.split(":", 2)[1] for line in text.splitlines()) else "v2"
    if legacy.is_file():
        return "v1"
    raise HostFactError("cgroup mode is unavailable")


def collect_host_facts() -> dict[str, object]:
    release = _os_release()
    root = os.statvfs("/")
    return {
        "os_id": release.get("ID", ""),
        "os_version_id": release.get("VERSION_ID", ""),
        "kernel_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "cgroup_mode": _cgroup_mode(),
        "root_total_bytes": root.f_blocks * root.f_frsize,
        "root_free_bytes": root.f_bavail * root.f_frsize,
    }


def validate_host_facts(document: dict[str, object]) -> None:
    """Fail before Docker activity when the selected image contract is not present."""

    root_total_bytes = document.get("root_total_bytes")
    root_free_bytes = document.get("root_free_bytes")
    if (
        document.get("os_id") != "ubuntu"
        or not str(document.get("os_version_id", "")).startswith("22.04")
        or document.get("architecture") != "x86_64"
        or not str(document.get("python_version", "")).startswith("3.10.")
        or document.get("cgroup_mode") not in {"v1", "v2", "hybrid"}
        or not isinstance(root_total_bytes, int)
        or isinstance(root_total_bytes, bool)
        or root_total_bytes < 107_374_182_400
        or not isinstance(root_free_bytes, int)
        or isinstance(root_free_bytes, bool)
        or root_free_bytes < 10_737_418_240
    ):
        raise HostFactError("host does not satisfy the pinned Lambda Stack contract")
