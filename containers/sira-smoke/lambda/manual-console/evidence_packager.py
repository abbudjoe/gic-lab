#!/usr/bin/env python3
"""Create one deterministic, bounded L2M evidence archive without a shell."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

MAX_SOURCE_BYTES = 16_777_216
MAX_ARCHIVE_BYTES = 16_777_216
MAX_STAGED_FIXTURE_BYTES = 1_048_576
MAX_SUCCESS_SOURCE_TREE_BYTES = MAX_SOURCE_BYTES + MAX_STAGED_FIXTURE_BYTES
MAX_FAILURE_SOURCE_TREE_BYTES = MAX_SOURCE_BYTES
MAX_REMOTE_SOURCE_RETAINED_BYTES = MAX_SUCCESS_SOURCE_TREE_BYTES + MAX_FAILURE_SOURCE_TREE_BYTES
MAX_REMOTE_ARCHIVE_RETAINED_BYTES = 2 * MAX_ARCHIVE_BYTES
MAX_REMOTE_RETAINED_BYTES = MAX_REMOTE_SOURCE_RETAINED_BYTES + MAX_REMOTE_ARCHIVE_RETAINED_BYTES
SUCCESS_SOURCE_NAMES = (
    "host-evidence.json",
    "qualification-log.jsonl",
    "container-inspect.json",
)
FAILURE_SOURCE_NAMES = (
    "qualification-failure.json",
    "qualification-log.jsonl",
    "container-inspect.json",
)


class EvidencePackagingError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _bounded_tree_bytes(root: Path, *, maximum_bytes: int) -> int:
    """Measure one harness-owned evidence tree without following links."""

    try:
        root_identity = root.lstat()
    except FileNotFoundError:
        return 0
    if not stat.S_ISDIR(root_identity.st_mode):
        raise EvidencePackagingError("evidence source root identity is unsafe")
    total = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        for child in directory.iterdir():
            identity = child.lstat()
            if stat.S_ISDIR(identity.st_mode):
                pending.append(child)
                continue
            if not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1:
                raise EvidencePackagingError("retained evidence identity is unsafe")
            total += identity.st_size
            if total > maximum_bytes:
                raise EvidencePackagingError("retained evidence source exceeds its cap")
    return total


def _bounded_archive_bytes(path: Path) -> int:
    try:
        identity = path.lstat()
    except FileNotFoundError:
        return 0
    if (
        not stat.S_ISREG(identity.st_mode)
        or identity.st_nlink != 1
        or identity.st_size > MAX_ARCHIVE_BYTES
    ):
        raise EvidencePackagingError("retained evidence archive identity is unsafe")
    return identity.st_size


def validate_remote_retention(
    *,
    success_root: Path,
    success_archive: Path,
    failure_root: Path,
    failure_archive: Path,
) -> dict[str, int]:
    """Enforce the worst-case same-attempt remote retained-evidence budget."""

    roots = (success_root, failure_root, success_archive, failure_archive)
    existing = [path for path in roots if path.exists()]
    if existing:
        devices = {path.lstat().st_dev for path in existing}
        if len(devices) != 1:
            raise EvidencePackagingError("retained evidence crossed filesystem identities")
    success_source_bytes = _bounded_tree_bytes(
        success_root,
        maximum_bytes=MAX_SUCCESS_SOURCE_TREE_BYTES,
    )
    failure_source_bytes = _bounded_tree_bytes(
        failure_root,
        maximum_bytes=MAX_FAILURE_SOURCE_TREE_BYTES,
    )
    source_bytes = success_source_bytes + failure_source_bytes
    if source_bytes > MAX_REMOTE_SOURCE_RETAINED_BYTES:
        raise EvidencePackagingError("retained evidence sources exceed their aggregate cap")
    success_archive_bytes = _bounded_archive_bytes(success_archive)
    failure_archive_bytes = _bounded_archive_bytes(failure_archive)
    archive_bytes = success_archive_bytes + failure_archive_bytes
    if archive_bytes > MAX_REMOTE_ARCHIVE_RETAINED_BYTES:
        raise EvidencePackagingError("retained evidence archives exceed their aggregate cap")
    aggregate_bytes = source_bytes + archive_bytes
    if aggregate_bytes > MAX_REMOTE_RETAINED_BYTES:
        raise EvidencePackagingError("remote retained evidence exceeds its aggregate cap")
    return {
        "success_source_bytes": success_source_bytes,
        "failure_source_bytes": failure_source_bytes,
        "source_bytes": source_bytes,
        "success_archive_bytes": success_archive_bytes,
        "failure_archive_bytes": failure_archive_bytes,
        "archive_bytes": archive_bytes,
        "aggregate_bytes": aggregate_bytes,
    }


def require_remote_capacity(path: Path) -> None:
    """Reserve the full evidence envelope before any future qualification writes."""

    identity = path.lstat()
    if not stat.S_ISDIR(identity.st_mode):
        raise EvidencePackagingError("evidence parent identity is unsafe")
    filesystem = os.statvfs(path)
    available = filesystem.f_bavail * filesystem.f_frsize
    if available < MAX_REMOTE_RETAINED_BYTES:
        raise EvidencePackagingError("remote evidence retained-space floor is unavailable")


def _open_held_directory(path: Path, *, context: str) -> tuple[int, int, int]:
    descriptor = -1
    try:
        before = path.lstat()
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        linked = path.lstat()
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        raise EvidencePackagingError(f"{context} directory is unavailable") from None
    if (
        not stat.S_ISDIR(opened.st_mode)
        or opened.st_uid != os.getuid()
        or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
    ):
        os.close(descriptor)
        raise EvidencePackagingError(f"{context} directory identity is unsafe")
    return descriptor, opened.st_dev, opened.st_ino


def _read_held_source(root_descriptor: int, name: str) -> bytes:
    if Path(name).parts != (name,):
        raise EvidencePackagingError("evidence source name is unsafe")
    descriptor = -1
    try:
        before = os.stat(name, dir_fd=root_descriptor, follow_symlinks=False)
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_descriptor,
        )
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_uid != os.getuid()
            or opened.st_size > MAX_SOURCE_BYTES
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise EvidencePackagingError("evidence source identity is unsafe")
        chunks: list[bytes] = []
        total = 0
        while total <= MAX_SOURCE_BYTES:
            chunk = os.read(descriptor, min(65_536, MAX_SOURCE_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        encoded = b"".join(chunks)
        after = os.fstat(descriptor)
        linked = os.stat(name, dir_fd=root_descriptor, follow_symlinks=False)
        if (
            len(encoded) != opened.st_size
            or (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            != (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
                opened.st_ctime_ns,
            )
            or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise EvidencePackagingError("evidence source changed while held")
        return encoded
    except OSError:
        raise EvidencePackagingError("evidence source could not be read safely") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _package(
    source_root: Path,
    archive_path: Path,
    *,
    source_names: tuple[str, ...],
    absolute_deadline_monotonic: float | None = None,
    clock: Callable[[], float] | None = None,
) -> tuple[int, str]:
    active_clock = time.monotonic if clock is None else clock

    def check_deadline() -> None:
        if (
            absolute_deadline_monotonic is not None
            and active_clock() >= absolute_deadline_monotonic
        ):
            raise EvidencePackagingError("evidence packaging deadline exceeded")

    source_descriptor = -1
    parent_descriptor = -1
    archive_descriptor = -1
    staging_created = False
    finalized = False
    completed = False
    final_name = archive_path.name
    staging_name = f".{final_name}.partial"
    try:
        source_descriptor, source_device, source_inode = _open_held_directory(
            source_root,
            context="evidence source",
        )
        parent_descriptor, parent_device, parent_inode = _open_held_directory(
            archive_path.parent,
            context="evidence archive parent",
        )
        if final_name in {"", ".", ".."} or Path(final_name).parts != (final_name,):
            raise EvidencePackagingError("evidence archive name is unsafe")
        for name in (final_name, staging_name):
            try:
                os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise EvidencePackagingError("evidence archive identity is not fresh")

        payloads: dict[str, bytes] = {}
        total = 0
        for name in source_names:
            check_deadline()
            encoded = _read_held_source(source_descriptor, name)
            total += len(encoded)
            if total > MAX_SOURCE_BYTES:
                raise EvidencePackagingError("evidence sources exceed their cap")
            payloads[name] = encoded
            check_deadline()
        source_linked = source_root.lstat()
        if (source_linked.st_dev, source_linked.st_ino) != (source_device, source_inode):
            raise EvidencePackagingError("evidence source root changed while held")
        manifest = _canonical(
            {
                "schema_version": "0.1.0",
                "files": [
                    {
                        "path": name,
                        "bytes": len(payloads[name]),
                        "sha256": hashlib.sha256(payloads[name]).hexdigest(),
                    }
                    for name in sorted(payloads)
                ],
            }
        )
        payloads["EVIDENCE_MANIFEST.json"] = manifest

        archive_descriptor = os.open(
            staging_name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        staging_created = True
        os.fsync(parent_descriptor)
        check_deadline()
        with os.fdopen(os.dup(archive_descriptor), "w+b") as archive_file:
            with zipfile.ZipFile(
                archive_file,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for name in sorted(payloads):
                    check_deadline()
                    member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    member.compress_type = zipfile.ZIP_DEFLATED
                    member.external_attr = 0o100600 << 16
                    archive.writestr(member, payloads[name])
                    check_deadline()
            archive_file.flush()
        os.fsync(archive_descriptor)
        archive_identity = os.fstat(archive_descriptor)
        if archive_identity.st_size > MAX_ARCHIVE_BYTES:
            raise EvidencePackagingError("evidence archive exceeds its cap")
        encoded = os.pread(archive_descriptor, MAX_ARCHIVE_BYTES + 1, 0)
        staged_link = os.stat(staging_name, dir_fd=parent_descriptor, follow_symlinks=False)
        if (
            len(encoded) != archive_identity.st_size
            or not stat.S_ISREG(archive_identity.st_mode)
            or archive_identity.st_nlink != 1
            or archive_identity.st_uid != os.getuid()
            or (staged_link.st_dev, staged_link.st_ino)
            != (archive_identity.st_dev, archive_identity.st_ino)
        ):
            raise EvidencePackagingError("evidence archive staging identity drifted")
        check_deadline()
        os.rename(
            staging_name,
            final_name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        finalized = True
        os.fsync(parent_descriptor)
        final_link = os.stat(final_name, dir_fd=parent_descriptor, follow_symlinks=False)
        parent_linked = archive_path.parent.lstat()
        if (final_link.st_dev, final_link.st_ino) != (
            archive_identity.st_dev,
            archive_identity.st_ino,
        ) or (parent_linked.st_dev, parent_linked.st_ino) != (parent_device, parent_inode):
            raise EvidencePackagingError("evidence archive final identity drifted")
        check_deadline()
        completed = True
        return archive_identity.st_size, hashlib.sha256(encoded).hexdigest()
    except OSError:
        raise EvidencePackagingError("evidence archive filesystem operation failed") from None
    finally:
        if parent_descriptor >= 0 and staging_created and not completed:
            cleanup_name = final_name if finalized else staging_name
            try:
                os.unlink(cleanup_name, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)
            except OSError:
                pass
        if archive_descriptor >= 0:
            os.close(archive_descriptor)
        if parent_descriptor >= 0:
            os.close(parent_descriptor)
        if source_descriptor >= 0:
            os.close(source_descriptor)


def package_evidence(
    source_root: Path,
    archive_path: Path,
    *,
    absolute_deadline_monotonic: float | None = None,
    clock: Callable[[], float] | None = None,
) -> tuple[int, str]:
    return _package(
        source_root,
        archive_path,
        source_names=SUCCESS_SOURCE_NAMES,
        absolute_deadline_monotonic=absolute_deadline_monotonic,
        clock=clock,
    )


def package_failure_evidence(
    source_root: Path,
    archive_path: Path,
    *,
    absolute_deadline_monotonic: float | None = None,
    clock: Callable[[], float] | None = None,
) -> tuple[int, str]:
    return _package(
        source_root,
        archive_path,
        source_names=FAILURE_SOURCE_NAMES,
        absolute_deadline_monotonic=absolute_deadline_monotonic,
        clock=clock,
    )
