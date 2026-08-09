"""Durable, guarded archive writer for a future authorized T07 Gate L1 run.

Importing this module performs no I/O.  The concrete implementation is invoked only
by the separately authorized inventory supervisor.  It keeps the Mac mini source,
copies only redacted evidence to the approved UTDM-exported APFS volume, verifies the
copy, and records the fresh volume identity and retained-free-space checks.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .lambda_cloud import (
    InventoryRunBinding,
    ReadOnlyInventoryPlan,
    secret_free_child_environment,
)
from .sira_storage import (
    APPROVED_MOUNT,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    SYSTEM_DATA_MOUNT,
    StorageContractError,
    VolumeObservation,
    retained_free_floor,
    volume_observation_from_diskutil,
)

ARCHIVE_ACTION_ID = "t07-l1-seal-copy"
DISKUTIL_OUTPUT_CAP_BYTES = 4 * 1024 * 1024
DISKUTIL_TIMEOUT_SECONDS = 10
MAX_DISKUTIL_CALLS = 9


class InventoryArchiveError(ValueError):
    """A future L1 archive action violated its storage or evidence contract."""


@dataclass(frozen=True, slots=True)
class ArchivedInventoryArtifact:
    destination: Path
    artifact_sha256: str
    artifact_bytes: int
    seal_sha256: str
    external_copy_record_sha256: str
    local_verification_record: bytes


class PreparedInventoryArchive(Protocol):
    """Single-use held-descriptor capability prepared before any provider call."""

    def archive(
        self,
        artifact_path: Path,
        *,
        artifact_sha256: str,
        artifact_bytes: int,
    ) -> ArchivedInventoryArtifact: ...

    def close(self) -> None: ...


class InventoryArchiver(Protocol):
    """Injectable factory; tests use a fake and never inspect a real volume."""

    def prepare(
        self,
        repository_root: Path,
        *,
        plan: ReadOnlyInventoryPlan,
        plan_sha256: str,
        run_binding: InventoryRunBinding,
    ) -> PreparedInventoryArchive: ...


def _canonical_bytes(document: dict[str, object]) -> bytes:
    return (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def _run_diskutil(argv: tuple[str, ...]) -> bytes:
    try:
        completed = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            timeout=DISKUTIL_TIMEOUT_SECONDS,
            env=secret_free_child_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        raise InventoryArchiveError("read-only storage observation failed") from None
    output_bytes = len(completed.stdout) + len(completed.stderr)
    if output_bytes > DISKUTIL_OUTPUT_CAP_BYTES:
        raise InventoryArchiveError("read-only storage observation exceeded its output cap")
    if completed.returncode != 0:
        raise InventoryArchiveError("read-only storage observation returned failure")
    return completed.stdout


@dataclass(slots=True)
class DiskutilVolumeObserver:
    """Fresh three-command observation of the exact external and system volumes."""

    calls: int = 0
    output_bytes: int = 0

    def __call__(self) -> tuple[VolumeObservation, VolumeObservation]:
        if self.calls + 3 > MAX_DISKUTIL_CALLS:
            raise InventoryArchiveError("storage observation call cap exhausted")
        external_info = _run_diskutil(("/usr/sbin/diskutil", "info", "-plist", str(APPROVED_MOUNT)))
        system_info = _run_diskutil(
            ("/usr/sbin/diskutil", "info", "-plist", str(SYSTEM_DATA_MOUNT))
        )
        apfs_list = _run_diskutil(("/usr/sbin/diskutil", "apfs", "list", "-plist"))
        self.calls += 3
        self.output_bytes += len(external_info) + len(system_info) + len(apfs_list)
        try:
            return (
                volume_observation_from_diskutil(external_info, apfs_list),
                volume_observation_from_diskutil(system_info, apfs_list),
            )
        except StorageContractError:
            raise InventoryArchiveError("storage identity evidence failed validation") from None


def _validate_external(observation: VolumeObservation, *, incremental_bytes: int) -> int:
    if observation.mount_path != APPROVED_MOUNT:
        raise InventoryArchiveError("approved archive mount path drifted")
    if observation.filesystem.casefold() != "apfs" or not observation.writable:
        raise InventoryArchiveError("approved archive volume is not writable APFS")
    if observation.volume_uuid.upper() != APPROVED_VOLUME_UUID:
        raise InventoryArchiveError("approved archive volume UUID drifted")
    if (observation.physical_store_uuid or "").upper() != APPROVED_PHYSICAL_STORE_UUID:
        raise InventoryArchiveError("approved archive physical-store UUID drifted")
    if observation.internal:
        raise InventoryArchiveError("approved archive volume resolved internally")
    if observation.bus_protocol != "Thunderbolt" or "UTDM" not in (
        observation.device_tree_path or ""
    ):
        raise InventoryArchiveError("approved archive is not the reviewed UTDM export")
    if not observation.unlocked or observation.total_bytes <= 0:
        raise InventoryArchiveError("approved archive is locked or lacks capacity evidence")
    floor = retained_free_floor(observation.total_bytes)
    if observation.free_bytes < floor + incremental_bytes:
        raise InventoryArchiveError("approved archive is below its pre-copy free-space floor")
    return floor


def _validate_system(observation: VolumeObservation, *, floor_bytes: int) -> None:
    try:
        observation.validate_system_floor(floor_bytes)
    except StorageContractError:
        raise InventoryArchiveError("Mac mini active-evidence floor or identity failed") from None


def _same_identity(first: VolumeObservation, second: VolumeObservation) -> bool:
    return (
        first.mount_path == second.mount_path
        and first.filesystem.casefold() == second.filesystem.casefold()
        and first.writable == second.writable
        and first.volume_uuid.upper() == second.volume_uuid.upper()
        and (first.physical_store_uuid or "").upper() == (second.physical_store_uuid or "").upper()
        and first.total_bytes == second.total_bytes
        and first.internal == second.internal
        and first.owners_enabled == second.owners_enabled
        and first.encrypted == second.encrypted
        and first.unlocked == second.unlocked
        and first.device_identifier == second.device_identifier
        and first.bus_protocol == second.bus_protocol
        and first.device_tree_path == second.device_tree_path
    )


@dataclass(slots=True)
class _HeldDirectory:
    path: Path
    descriptor: int
    device: int
    inode: int
    closed: bool = False

    @classmethod
    def open(cls, path: Path) -> _HeldDirectory:
        descriptor = _open_directory_no_symlinks(path)
        observed = os.fstat(descriptor)
        return cls(path, descriptor, observed.st_dev, observed.st_ino)

    def revalidate(self) -> None:
        if self.closed:
            raise InventoryArchiveError("held archive descriptor closed early")
        observed = os.fstat(self.descriptor)
        try:
            linked = self.path.stat(follow_symlinks=False)
        except OSError:
            raise InventoryArchiveError("held archive path disappeared") from None
        if (
            not stat.S_ISDIR(observed.st_mode)
            or not stat.S_ISDIR(linked.st_mode)
            or (observed.st_dev, observed.st_ino) != (self.device, self.inode)
            or (linked.st_dev, linked.st_ino) != (self.device, self.inode)
        ):
            raise InventoryArchiveError("held archive path identity changed")

    def close(self) -> None:
        if not self.closed:
            os.close(self.descriptor)
            self.closed = True


def _open_directory_no_symlinks(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise InventoryArchiveError("archive directory path is not absolute and confined")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open("/", flags)
    try:
        for component in path.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
    except OSError:
        os.close(descriptor)
        raise InventoryArchiveError("archive directory chain is missing or unsafe") from None
    return descriptor


def _open_or_create_archive_root(external: _HeldDirectory, archive_root: Path) -> _HeldDirectory:
    expected = APPROVED_MOUNT / "GIC-Lab/t07/sealed-artifacts"
    if archive_root != expected:
        raise InventoryArchiveError("archive root differs from the approved exact path")
    relative = archive_root.relative_to(APPROVED_MOUNT)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.dup(external.descriptor)
    path = APPROVED_MOUNT
    try:
        for component in relative.parts:
            with suppress(FileExistsError):
                os.mkdir(component, mode=0o700, dir_fd=descriptor)
            child = os.open(component, flags, dir_fd=descriptor)
            observed = os.fstat(child)
            if (
                not stat.S_ISDIR(observed.st_mode)
                or observed.st_dev != external.device
                or observed.st_uid != os.getuid()
            ):
                os.close(child)
                raise InventoryArchiveError("archive hierarchy escaped or is not user-owned")
            os.close(descriptor)
            descriptor = child
            path /= component
        observed = os.fstat(descriptor)
        return _HeldDirectory(path, descriptor, observed.st_dev, observed.st_ino)
    except Exception:
        os.close(descriptor)
        raise


def _write_exclusive_at(directory_fd: int, name: str, encoded: bytes) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory_fd,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written < 1:
                raise InventoryArchiveError("archive write made no progress")
            offset += written
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
    finally:
        os.close(descriptor)


def _read_regular_at(directory_fd: int, name: str, *, max_bytes: int) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_fd,
    )
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            raise InventoryArchiveError("archive evidence is not one regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise InventoryArchiveError("archive evidence exceeds its byte cap")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


@dataclass(slots=True)
class _PreparedDurableInventoryArchive:
    repository_root: Path
    plan: ReadOnlyInventoryPlan
    plan_sha256: str
    run_binding: InventoryRunBinding
    observer: DiskutilVolumeObserver
    external_at_prepare: VolumeObservation
    system_at_prepare: VolumeObservation
    external_mount: _HeldDirectory
    system_mount: _HeldDirectory
    repository: _HeldDirectory
    archive_root: _HeldDirectory
    clock: Callable[[], float]
    utc_now: Callable[[], datetime]
    used: bool = False
    closed: bool = False

    def _revalidate(
        self, external: VolumeObservation, system: VolumeObservation, *, incremental: int
    ) -> int:
        if not _same_identity(self.external_at_prepare, external) or not _same_identity(
            self.system_at_prepare, system
        ):
            raise InventoryArchiveError("storage identity drifted during Gate L1")
        floor = _validate_external(external, incremental_bytes=incremental)
        _validate_system(system, floor_bytes=self.plan.local_retained_floor_bytes)
        for handle in (
            self.external_mount,
            self.system_mount,
            self.repository,
            self.archive_root,
        ):
            handle.revalidate()
        return floor

    def archive(
        self,
        artifact_path: Path,
        *,
        artifact_sha256: str,
        artifact_bytes: int,
    ) -> ArchivedInventoryArtifact:
        if self.used or self.closed:
            raise InventoryArchiveError("prepared inventory archive is stale or already used")
        self.used = True
        started = self.clock()
        staging_name = f".{self.run_binding.run_id}.{uuid.uuid4().hex}.partial"
        destination_name = self.run_binding.run_id
        staging_fd = -1
        try:
            expected_source = self.repository_root / self.plan.output_relative_path
            if artifact_path != expected_source:
                raise InventoryArchiveError("inventory source path drifted")
            if self.clock() - started > self.plan.max_archive_wall_seconds:
                raise InventoryArchiveError("inventory archive wall budget expired")
            external_pre, system_pre = self.observer()
            external_floor = self._revalidate(
                external_pre,
                system_pre,
                incremental=self.plan.max_archive_bytes,
            )
            if self.clock() - started > self.plan.max_archive_wall_seconds:
                raise InventoryArchiveError("inventory archive wall budget expired")
            source_parent_fd = _open_directory_no_symlinks(artifact_path.parent)
            try:
                source_encoded = _read_regular_at(
                    source_parent_fd,
                    artifact_path.name,
                    max_bytes=self.plan.max_retained_output_bytes,
                )
                source_status = os.stat(
                    artifact_path.name,
                    dir_fd=source_parent_fd,
                    follow_symlinks=False,
                )
            finally:
                os.close(source_parent_fd)
            if (
                len(source_encoded) != artifact_bytes
                or len(source_encoded) > self.plan.max_retained_output_bytes
                or hashlib.sha256(source_encoded).hexdigest() != artifact_sha256
                or not stat.S_ISREG(source_status.st_mode)
                or source_status.st_nlink != 1
                or source_status.st_dev != self.system_mount.device
            ):
                raise InventoryArchiveError("inventory source identity or hash drifted")
            try:
                os.stat(
                    destination_name, dir_fd=self.archive_root.descriptor, follow_symlinks=False
                )
            except FileNotFoundError:
                pass
            else:
                raise InventoryArchiveError("inventory archive run identity already exists")
            os.mkdir(staging_name, mode=0o700, dir_fd=self.archive_root.descriptor)
            staging_fd = os.open(
                staging_name,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=self.archive_root.descriptor,
            )
            _write_exclusive_at(staging_fd, "inventory-redacted.json", source_encoded)
            copied_at = self.utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z")
            external_record = _canonical_bytes(
                {
                    "schema_version": "0.1.0",
                    "action_id": ARCHIVE_ACTION_ID,
                    "plan_id": self.plan.plan_id,
                    "plan_sha256": self.plan_sha256,
                    "run_id": self.run_binding.run_id,
                    "repository_commit": self.run_binding.repository_commit,
                    "authorization_reference": self.run_binding.authorization_reference,
                    "authorization_sha256": self.run_binding.authorization_sha256,
                    "source_path": str(artifact_path),
                    "source_sha256": artifact_sha256,
                    "source_bytes": artifact_bytes,
                    "source_retained": True,
                    "destination_path": str(
                        Path(self.plan.archive_root)
                        / self.run_binding.run_id
                        / "inventory-redacted.json"
                    ),
                    "destination_sha256": artifact_sha256,
                    "copied_at_utc": copied_at,
                    "external_mount": str(external_pre.mount_path),
                    "external_volume_uuid": external_pre.volume_uuid.upper(),
                    "external_physical_store_uuid": (
                        external_pre.physical_store_uuid or ""
                    ).upper(),
                    "external_capacity_bytes": external_pre.total_bytes,
                    "external_precopy_free_bytes": external_pre.free_bytes,
                    "external_retained_floor_bytes": external_floor,
                    "external_precopy_floor_bytes": (external_floor + self.plan.max_archive_bytes),
                    "held_descriptor_guard": True,
                    "atomic_finalization": True,
                    "fsync_required": True,
                    "no_internal_fallback": True,
                    "postcopy_check_recorded_locally": True,
                }
            )
            if len(external_record) > self.plan.max_local_record_bytes:
                raise InventoryArchiveError("external copy record exceeds its byte cap")
            _write_exclusive_at(staging_fd, "COPY_RECORD.json", external_record)
            seal = _canonical_bytes(
                {
                    "schema_version": "0.1.0",
                    "run_id": self.run_binding.run_id,
                    "files": [
                        {
                            "path": "inventory-redacted.json",
                            "bytes": len(source_encoded),
                            "sha256": artifact_sha256,
                        },
                        {
                            "path": "COPY_RECORD.json",
                            "bytes": len(external_record),
                            "sha256": hashlib.sha256(external_record).hexdigest(),
                        },
                    ],
                }
            )
            total_archive_bytes = len(source_encoded) + len(external_record) + len(seal)
            if total_archive_bytes > self.plan.max_archive_bytes:
                raise InventoryArchiveError("sealed inventory archive exceeds its byte cap")
            _write_exclusive_at(staging_fd, "SEAL.json", seal)
            os.fsync(staging_fd)
            os.fchmod(staging_fd, 0o500)
            os.rename(
                staging_name,
                destination_name,
                src_dir_fd=self.archive_root.descriptor,
                dst_dir_fd=self.archive_root.descriptor,
            )
            os.fsync(self.archive_root.descriptor)
            destination_fd = os.open(
                destination_name,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=self.archive_root.descriptor,
            )
            try:
                copied = _read_regular_at(
                    destination_fd,
                    "inventory-redacted.json",
                    max_bytes=self.plan.max_retained_output_bytes,
                )
                copied_record = _read_regular_at(
                    destination_fd,
                    "COPY_RECORD.json",
                    max_bytes=self.plan.max_local_record_bytes,
                )
                copied_seal = _read_regular_at(
                    destination_fd,
                    "SEAL.json",
                    max_bytes=self.plan.max_local_record_bytes,
                )
            finally:
                os.close(destination_fd)
            if copied != source_encoded or copied_record != external_record or copied_seal != seal:
                raise InventoryArchiveError("final archive verification failed")
            external_post, system_post = self.observer()
            self._revalidate(external_post, system_post, incremental=0)
            if external_post.free_bytes < external_floor:
                raise InventoryArchiveError("external retained-free floor failed after copy")
            _validate_system(system_post, floor_bytes=self.plan.local_retained_floor_bytes)
            if self.clock() - started > self.plan.max_archive_wall_seconds:
                raise InventoryArchiveError("inventory archive wall budget expired")
            external_record_hash = hashlib.sha256(external_record).hexdigest()
            seal_hash = hashlib.sha256(seal).hexdigest()
            local_verification = _canonical_bytes(
                {
                    "schema_version": "0.1.0",
                    "action_id": ARCHIVE_ACTION_ID,
                    "plan_id": self.plan.plan_id,
                    "plan_sha256": self.plan_sha256,
                    "run_id": self.run_binding.run_id,
                    "repository_commit": self.run_binding.repository_commit,
                    "authorization_reference": self.run_binding.authorization_reference,
                    "authorization_sha256": self.run_binding.authorization_sha256,
                    "source_path": str(artifact_path),
                    "source_sha256": artifact_sha256,
                    "source_bytes": artifact_bytes,
                    "source_retained": True,
                    "destination_path": str(Path(self.plan.archive_root) / self.run_binding.run_id),
                    "destination_artifact_sha256": hashlib.sha256(copied).hexdigest(),
                    "destination_copy_record_sha256": external_record_hash,
                    "destination_seal_sha256": seal_hash,
                    "external_volume_uuid": external_post.volume_uuid.upper(),
                    "external_physical_store_uuid": (
                        external_post.physical_store_uuid or ""
                    ).upper(),
                    "external_capacity_bytes": external_post.total_bytes,
                    "external_postcopy_free_bytes": external_post.free_bytes,
                    "external_retained_floor_bytes": external_floor,
                    "system_postcopy_free_bytes": system_post.free_bytes,
                    "system_retained_floor_bytes": self.plan.local_retained_floor_bytes,
                    "held_descriptor_guard": True,
                    "source_destination_sha256_equal": True,
                    "source_retained_until_independent_verification": True,
                }
            )
            if len(local_verification) > self.plan.max_local_record_bytes:
                raise InventoryArchiveError("local archive verification exceeds its byte cap")
            return ArchivedInventoryArtifact(
                destination=Path(self.plan.archive_root) / self.run_binding.run_id,
                artifact_sha256=artifact_sha256,
                artifact_bytes=artifact_bytes,
                seal_sha256=seal_hash,
                external_copy_record_sha256=external_record_hash,
                local_verification_record=local_verification,
            )
        except OSError:
            raise InventoryArchiveError("inventory archive filesystem action failed") from None
        finally:
            if staging_fd >= 0:
                os.close(staging_fd)
            self.close()

    def close(self) -> None:
        if self.closed:
            return
        for handle in (
            self.archive_root,
            self.repository,
            self.system_mount,
            self.external_mount,
        ):
            handle.close()
        self.closed = True


@dataclass(slots=True)
class DurableInventoryArchiver:
    """Concrete future archiver; construction and import remain network/file inert."""

    observer_factory: Callable[[], DiskutilVolumeObserver] = DiskutilVolumeObserver
    clock: Callable[[], float] = time.monotonic
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC)

    def prepare(
        self,
        repository_root: Path,
        *,
        plan: ReadOnlyInventoryPlan,
        plan_sha256: str,
        run_binding: InventoryRunBinding,
    ) -> PreparedInventoryArchive:
        root = repository_root.resolve(strict=True)
        if root != repository_root.absolute():
            raise InventoryArchiveError("repository root contains a symlink")
        observer = self.observer_factory()
        external, system = observer()
        _validate_external(external, incremental_bytes=plan.max_archive_bytes)
        _validate_system(system, floor_bytes=plan.local_prewrite_floor_bytes)
        external_handle = _HeldDirectory.open(APPROVED_MOUNT)
        system_handle: _HeldDirectory | None = None
        repository_handle: _HeldDirectory | None = None
        archive_handle: _HeldDirectory | None = None
        try:
            system_handle = _HeldDirectory.open(SYSTEM_DATA_MOUNT)
            if external_handle.device == system_handle.device:
                raise InventoryArchiveError("archive source and destination are one filesystem")
            repository_handle = _HeldDirectory.open(root)
            if repository_handle.device != system_handle.device:
                raise InventoryArchiveError("active inventory root is not on the Mac mini volume")
            archive_handle = _open_or_create_archive_root(
                external_handle,
                Path(plan.archive_root),
            )
            if archive_handle.device != external_handle.device:
                raise InventoryArchiveError("archive root fell back to another volume")
            return _PreparedDurableInventoryArchive(
                repository_root=root,
                plan=plan,
                plan_sha256=plan_sha256,
                run_binding=run_binding,
                observer=observer,
                external_at_prepare=external,
                system_at_prepare=system,
                external_mount=external_handle,
                system_mount=system_handle,
                repository=repository_handle,
                archive_root=archive_handle,
                clock=self.clock,
                utc_now=self.utc_now,
            )
        except Exception:
            for handle in (archive_handle, repository_handle, system_handle, external_handle):
                if handle is not None:
                    handle.close()
            raise
