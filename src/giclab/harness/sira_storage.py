"""Gate B1.6 storage qualification control plane for T07.

This module is intentionally local and deterministic.  It does not download or
install Docker, start an engine, invoke a browser, inspect credentials, or call a
network API.  Runtime observations are supplied as typed values by a later,
separately authorized Gate B2a driver.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import plistlib
import re
import shutil
import stat
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class StorageContractError(ValueError):
    """A storage observation or Gate B2a plan violates the locked contract."""


GIB = 1024**3
MIB = 1024**2

APPROVED_MOUNT = Path("/Volumes/Macintosh HD - Data")
APPROVED_VOLUME_UUID = "8478609D-FA37-4ED5-875D-47AE912B9151"
APPROVED_PHYSICAL_STORE_UUID = "7904A6F1-F483-4ED7-9E34-BFECAB31C63E"
APPROVED_EXTERNAL_CAPACITY_BYTES = 1_000_240_963_584
APPROVED_EXTERNAL_ROOT = APPROVED_MOUNT / "GIC-Lab"
DOCKER_DISK_IMAGE_ROOT = APPROVED_EXTERNAL_ROOT / "t07/docker-desktop/disk-image"
BUILD_STAGING_ROOT = APPROVED_EXTERNAL_ROOT / "t07/docker-build-staging"
SEALED_ARTIFACT_ROOT = APPROVED_EXTERNAL_ROOT / "t07/sealed-artifacts"

SYSTEM_DATA_MOUNT = Path("/System/Volumes/Data")
SYSTEM_DATA_VOLUME_UUID = "285BFF35-A72D-452D-82A9-BD1ED7223CDE"
SYSTEM_CAPACITY_BYTES = 245_107_195_904
ACTIVE_ATTEMPT_ROOT = Path("/Users/joseph/.local/share/gic-lab/t07-gate-b2a/attempts")
B2A_WORK_ROOT = Path("/Users/joseph/.local/share/gic-lab/t07-gate-b2a")
CANDIDATE_DEFAULT_INTERNAL_DOCKER_RAW = Path(
    "/Users/joseph/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"
)
CANDIDATE_DOCKER_SETTINGS_STORE = Path(
    "/Users/joseph/Library/Group Containers/group.com.docker/settings-store.json"
)

PROJECT_MINIMUM_FREE_BYTES = 150 * GIB
PROJECT_FREE_PERCENT = 20
EXTERNAL_INCREMENTAL_RESERVATION_BYTES = 12 * GIB
ACTIVE_ATTEMPT_CAP_BYTES = 64 * MIB
B2A_EVIDENCE_CAP_BYTES = 16 * MIB

DOCKER_DMG_URL = "https://desktop.docker.com/mac/main/arm64/235549/Docker.dmg"
DOCKER_DMG_BYTES = 573_592_444
DOCKER_DMG_SHA256 = "84b1224c93456fe261955ebc91f3cd88ce19778ffdb6d0a0d423ce37246f7c2b"
DOCKER_PRODUCT_VERSION = "4.85.0"
DOCKER_BUILD = "235549"

B2A_PLAN_ID = "PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V1"
B2A_AUTHORIZATION_PLACEHOLDER = "AUTH-T07-GATE-B2A-PENDING"
SUPERSEDED_PLAN_ID = "PLAN-T07-GATE-B2-MATERIALIZATION"
SUPERSEDED_PLAN_SHA256 = "10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25"

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_PLAN_ID = re.compile(r"^PLAN-[A-Z0-9][A-Z0-9._-]{2,127}$")
_ACTION_ID = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
_UUID = re.compile(r"^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$")
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


def retained_free_floor(total_bytes: int) -> int:
    """Return max(150 GiB, ceil(20% of capacity))."""

    if total_bytes <= 0:
        raise StorageContractError("volume capacity must be positive")
    percent_floor = math.ceil(total_bytes * PROJECT_FREE_PERCENT / 100)
    return max(PROJECT_MINIMUM_FREE_BYTES, percent_floor)


EXTERNAL_RETAINED_FREE_FLOOR_BYTES = retained_free_floor(APPROVED_EXTERNAL_CAPACITY_BYTES)
EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES = (
    EXTERNAL_RETAINED_FREE_FLOOR_BYTES + EXTERNAL_INCREMENTAL_RESERVATION_BYTES
)


@dataclass(frozen=True, slots=True)
class SystemFloorInputs:
    """Evidence terms required before a numeric Mac mini floor may be approved."""

    os_operating_headroom_bytes: int | None
    dmg_download_peak_bytes: int | None = DOCKER_DMG_BYTES
    installed_app_bytes: int | None = None
    support_files_bytes: int | None = None
    update_rollback_bytes: int | None = None
    active_evidence_bytes: int | None = ACTIVE_ATTEMPT_CAP_BYTES
    failure_cleanup_bytes: int | None = None
    first_start_internal_bytes: int | None = None

    def resolved_floor_bytes(self) -> int:
        values = (
            self.os_operating_headroom_bytes,
            self.dmg_download_peak_bytes,
            self.installed_app_bytes,
            self.support_files_bytes,
            self.update_rollback_bytes,
            self.active_evidence_bytes,
            self.failure_cleanup_bytes,
            self.first_start_internal_bytes,
        )
        if any(value is None for value in values):
            raise StorageContractError("Mac mini operational floor has unresolved evidence terms")
        if any(value < 0 for value in values if value is not None):
            raise StorageContractError("Mac mini operational floor terms must be nonnegative")
        return sum(value for value in values if value is not None)


class RootPurpose(StrEnum):
    DOCKER_DISK = "docker-disk-image"
    BUILD_STAGING = "build-staging"
    SEALED_ARCHIVE = "sealed-artifact-archive"
    ACTIVE_ATTEMPT = "active-attempt"
    B2A_WORK = "b2a-work"


@dataclass(frozen=True, slots=True)
class VolumeObservation:
    mount_path: Path
    filesystem: str
    writable: bool
    volume_uuid: str
    physical_store_uuid: str | None
    total_bytes: int
    free_bytes: int
    internal: bool
    owners_enabled: bool
    encrypted: bool
    unlocked: bool
    device_identifier: str
    bus_protocol: str | None = None
    device_tree_path: str | None = None

    def validate_external(self, *, reserve_incremental: bool) -> None:
        if self.mount_path != APPROVED_MOUNT:
            raise StorageContractError("approved volume is missing or mounted under another name")
        if self.filesystem.casefold() != "apfs":
            raise StorageContractError("approved project/runtime volume must be APFS")
        if not self.writable:
            raise StorageContractError("approved project/runtime volume is not writable")
        if self.volume_uuid.upper() != APPROVED_VOLUME_UUID:
            raise StorageContractError("data-volume UUID mismatch")
        if (self.physical_store_uuid or "").upper() != APPROVED_PHYSICAL_STORE_UUID:
            raise StorageContractError("physical-store partition UUID mismatch")
        if self.internal:
            raise StorageContractError("approved project/runtime volume resolved internally")
        if self.bus_protocol != "Thunderbolt" or "UTDM" not in (self.device_tree_path or ""):
            raise StorageContractError(
                "approved volume is not the reviewed Thunderbolt UTDM export"
            )
        if not self.unlocked:
            raise StorageContractError("approved project/runtime volume is locked")
        if self.total_bytes != APPROVED_EXTERNAL_CAPACITY_BYTES:
            raise StorageContractError("approved APFS container capacity changed")
        floor = (
            EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES
            if reserve_incremental
            else EXTERNAL_RETAINED_FREE_FLOOR_BYTES
        )
        if self.free_bytes < floor:
            raise StorageContractError(
                f"external free bytes {self.free_bytes} are below required {floor}"
            )

    def validate_system(self, *, floor_inputs: SystemFloorInputs) -> None:
        if self.mount_path != SYSTEM_DATA_MOUNT:
            raise StorageContractError("Mac mini system Data volume mount mismatch")
        if self.filesystem.casefold() != "apfs" or not self.writable:
            raise StorageContractError("Mac mini system Data volume must be writable APFS")
        if self.volume_uuid.upper() != SYSTEM_DATA_VOLUME_UUID:
            raise StorageContractError("Mac mini system Data volume UUID mismatch")
        if not self.internal:
            raise StorageContractError("Mac mini system Data volume resolved externally")
        if self.total_bytes != SYSTEM_CAPACITY_BYTES:
            raise StorageContractError("Mac mini system Data capacity changed")
        floor = floor_inputs.resolved_floor_bytes()
        if self.free_bytes < floor:
            raise StorageContractError(
                f"system free bytes {self.free_bytes} are below required {floor}"
            )


def volume_observation_from_diskutil(
    volume_plist: bytes,
    apfs_list_plist: bytes,
) -> VolumeObservation:
    """Parse only the diskutil fields used by the storage guard.

    Free capacity and physical-store identity come from the unique APFS container
    matched by volume UUID.  The misleading per-volume ``FreeSpace`` field is never
    used.  Device numbers are evidence, never stable authorization identities.
    """

    try:
        raw = plistlib.loads(volume_plist)
        apfs_list = plistlib.loads(apfs_list_plist)
    except (plistlib.InvalidFileException, ValueError) as error:
        raise StorageContractError("invalid diskutil plist evidence") from error
    if not isinstance(raw, dict) or not isinstance(apfs_list, dict):
        raise StorageContractError("diskutil evidence must be a dictionary")
    mount = raw.get("MountPoint")
    filesystem = raw.get("FilesystemType") or raw.get("FilesystemName")
    uuid = raw.get("VolumeUUID") or raw.get("APFSVolumeUUID")
    device = raw.get("DeviceIdentifier")
    if not isinstance(mount, str):
        raise StorageContractError("diskutil mount-point evidence is incomplete")
    if not isinstance(filesystem, str):
        raise StorageContractError("diskutil filesystem evidence is incomplete")
    if not isinstance(uuid, str):
        raise StorageContractError("diskutil volume UUID evidence is incomplete")
    if not isinstance(device, str):
        raise StorageContractError("diskutil volume evidence is incomplete")
    container = _match_apfs_container(apfs_list, volume_uuid=uuid)
    total = container["total_bytes"]
    free = container["free_bytes"]
    physical_uuid = container["physical_store_uuid"]
    assert isinstance(total, int)
    assert isinstance(free, int)
    assert isinstance(physical_uuid, str)
    writable = raw.get("Writable") is True and raw.get("WritableVolume") is True
    return VolumeObservation(
        mount_path=Path(mount),
        filesystem=filesystem,
        writable=writable,
        volume_uuid=uuid,
        physical_store_uuid=physical_uuid,
        total_bytes=total,
        free_bytes=free,
        internal=bool(raw.get("Internal", True)) or bool(raw.get("OSInternalMedia", True)),
        owners_enabled=bool(raw.get("GlobalPermissionsEnabled", raw.get("Owners", False))),
        encrypted=bool(raw.get("Encryption", raw.get("Encrypted", False))),
        unlocked=not bool(raw.get("Locked", False)),
        device_identifier=device,
        bus_protocol=raw.get("BusProtocol") if isinstance(raw.get("BusProtocol"), str) else None,
        device_tree_path=(
            raw.get("DeviceTreePath") if isinstance(raw.get("DeviceTreePath"), str) else None
        ),
    )


def _match_apfs_container(raw: Mapping[str, object], *, volume_uuid: str) -> Mapping[str, object]:
    containers = raw.get("Containers")
    if not isinstance(containers, list):
        raise StorageContractError("APFS container evidence is incomplete")
    matches: list[Mapping[str, object]] = []
    for candidate in containers:
        if not isinstance(candidate, dict):
            raise StorageContractError("APFS container entry is malformed")
        volumes = candidate.get("Volumes")
        if not isinstance(volumes, list):
            raise StorageContractError("APFS volume list is malformed")
        for volume in volumes:
            if not isinstance(volume, dict):
                raise StorageContractError("APFS volume entry is malformed")
            observed_uuid = volume.get("APFSVolumeUUID")
            if isinstance(observed_uuid, str) and observed_uuid.upper() == volume_uuid.upper():
                matches.append(candidate)
    if len(matches) != 1:
        raise StorageContractError("volume UUID did not match exactly one APFS container")
    match = matches[0]
    total = match.get("CapacityCeiling")
    free = match.get("CapacityFree")
    stores = match.get("PhysicalStores")
    if (
        not isinstance(total, int)
        or isinstance(total, bool)
        or not isinstance(free, int)
        or isinstance(free, bool)
        or not isinstance(stores, list)
        or len(stores) != 1
        or not isinstance(stores[0], dict)
        or not isinstance(stores[0].get("DiskUUID"), str)
    ):
        raise StorageContractError("matched APFS container identity/capacity is incomplete")
    return {
        "total_bytes": total,
        "free_bytes": free,
        "physical_store_uuid": stores[0]["DiskUUID"],
    }


def diskutil_info_argv(target: Path) -> tuple[str, ...]:
    return ("/usr/sbin/diskutil", "info", "-plist", str(target))


def _assert_no_symlink_components(path: Path, *, allow_missing_leaf: bool) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise StorageContractError("path must be absolute and traversal-free")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open("/", flags)
    current = Path("/")
    try:
        for component in path.parts[1:]:
            current /= component
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if allow_missing_leaf:
                    return
                raise StorageContractError(f"required path is missing: {current}") from None
            except OSError as error:
                raise StorageContractError(
                    f"symlink or non-directory path component rejected: {current}"
                ) from error
            os.close(descriptor)
            descriptor = child
    finally:
        os.close(descriptor)


def validate_path_contract(
    path: Path,
    *,
    purpose: RootPurpose,
    external_mount_device: int,
    system_mount_device: int,
    allow_missing_leaf: bool = True,
) -> None:
    """Reject path escape, symlinks, role confusion, and internal fallback."""

    expected = {
        RootPurpose.DOCKER_DISK: DOCKER_DISK_IMAGE_ROOT,
        RootPurpose.BUILD_STAGING: BUILD_STAGING_ROOT,
        RootPurpose.SEALED_ARCHIVE: SEALED_ARTIFACT_ROOT,
        RootPurpose.ACTIVE_ATTEMPT: ACTIVE_ATTEMPT_ROOT,
        RootPurpose.B2A_WORK: B2A_WORK_ROOT,
    }[purpose]
    if path != expected:
        raise StorageContractError(f"{purpose.value} path differs from the approved exact path")

    if purpose in {
        RootPurpose.DOCKER_DISK,
        RootPurpose.BUILD_STAGING,
        RootPurpose.SEALED_ARCHIVE,
    }:
        validate_bounded_path(
            path,
            approved_root=APPROVED_EXTERNAL_ROOT,
            expected_device=external_mount_device,
            prohibited_device=system_mount_device,
            allow_missing_leaf=allow_missing_leaf,
        )
    else:
        validate_bounded_path(
            path,
            approved_root=Path("/Users/joseph/.local/share/gic-lab"),
            expected_device=system_mount_device,
            prohibited_device=external_mount_device,
            allow_missing_leaf=allow_missing_leaf,
        )


def validate_bounded_path(
    path: Path,
    *,
    approved_root: Path,
    expected_device: int,
    prohibited_device: int,
    allow_missing_leaf: bool,
) -> None:
    """Validate a path role without resolving through symlink components.

    Gate B2a must call this immediately before each storage-affecting or engine-start
    action.  Tests use temporary roots; production callers additionally bind exact
    path constants through :func:`validate_path_contract`.
    """

    if expected_device == prohibited_device:
        raise StorageContractError("approved path resolved to the prohibited volume")
    if not path.is_absolute() or not approved_root.is_absolute():
        raise StorageContractError("storage paths must be absolute")
    if not path.is_relative_to(approved_root):
        raise StorageContractError("storage path escaped its approved root")
    _assert_no_symlink_components(path, allow_missing_leaf=allow_missing_leaf)
    existing = path
    while True:
        try:
            observed = existing.stat(follow_symlinks=False)
            break
        except FileNotFoundError:
            if existing == existing.parent:
                raise StorageContractError("no existing ancestor for approved path") from None
            existing = existing.parent
    if observed.st_dev != expected_device:
        raise StorageContractError("storage path ancestor resolved to an unexpected device")


@dataclass(slots=True)
class StorageGuardToken:
    """Single-use evidence that a guard passed immediately before a sensitive action."""

    purpose: RootPurpose
    path: Path
    volume_uuid: str
    physical_store_uuid: str
    external_device: int
    system_device: int
    issued_monotonic_ns: int
    maximum_age_ns: int = 5_000_000_000
    consumed: bool = False

    def consume(
        self,
        *,
        observation: VolumeObservation,
        now_monotonic_ns: int | None = None,
    ) -> None:
        if self.consumed:
            raise StorageContractError("storage guard token was already consumed")
        current_ns = time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
        if current_ns < self.issued_monotonic_ns or (
            current_ns - self.issued_monotonic_ns > self.maximum_age_ns
        ):
            raise StorageContractError("storage guard token is stale")
        if (
            observation.volume_uuid.upper() != self.volume_uuid.upper()
            or (observation.physical_store_uuid or "").upper() != self.physical_store_uuid.upper()
        ):
            raise StorageContractError("storage identity changed after guard issuance")
        observation.validate_external(reserve_incremental=True)
        validate_path_contract(
            self.path,
            purpose=self.purpose,
            external_mount_device=self.external_device,
            system_mount_device=self.system_device,
            allow_missing_leaf=True,
        )
        self.consumed = True


class ReconnectState(StrEnum):
    INITIAL = "initial"
    PRE_EJECT_ENGINE_STOPPED = "pre-eject-engine-stopped"
    USER_EJECTED = "user-ejected"
    USER_DISCONNECTED = "user-disconnected"
    USER_RECONNECTED = "user-reconnected"
    VOLUME_REQUALIFIED = "volume-requalified"
    PATHS_REQUALIFIED = "paths-requalified"
    USER_ENGINE_RESTARTED = "user-engine-restarted"
    SAME_DISK_REOPENED = "same-disk-reopened"
    ENGINE_HEALTHY = "engine-healthy"
    FINAL_ENGINE_STOPPED = "final-engine-stopped"
    EVIDENCE_SEALED = "evidence-sealed"


_RECONNECT_SEQUENCE = (
    ReconnectState.PRE_EJECT_ENGINE_STOPPED,
    ReconnectState.USER_EJECTED,
    ReconnectState.USER_DISCONNECTED,
    ReconnectState.USER_RECONNECTED,
    ReconnectState.VOLUME_REQUALIFIED,
    ReconnectState.PATHS_REQUALIFIED,
    ReconnectState.USER_ENGINE_RESTARTED,
    ReconnectState.SAME_DISK_REOPENED,
    ReconnectState.ENGINE_HEALTHY,
    ReconnectState.FINAL_ENGINE_STOPPED,
    ReconnectState.EVIDENCE_SEALED,
)


@dataclass(slots=True)
class ReconnectQualification:
    expected_volume_uuid: str
    expected_physical_store_uuid: str
    expected_disk_identity: str
    expected_engine_identity: str
    state: ReconnectState = ReconnectState.INITIAL

    def advance(
        self,
        state: ReconnectState,
        *,
        volume_uuid: str | None = None,
        physical_store_uuid: str | None = None,
        disk_identity: str | None = None,
        engine_identity: str | None = None,
    ) -> None:
        current_index = (
            -1 if self.state is ReconnectState.INITIAL else _RECONNECT_SEQUENCE.index(self.state)
        )
        if (
            current_index + 1 >= len(_RECONNECT_SEQUENCE)
            or _RECONNECT_SEQUENCE[current_index + 1] is not state
        ):
            raise StorageContractError("reconnect evidence is stale, duplicated, or out of order")
        if state in {ReconnectState.VOLUME_REQUALIFIED, ReconnectState.PATHS_REQUALIFIED}:
            if (volume_uuid or "").upper() != self.expected_volume_uuid.upper():
                raise StorageContractError("reconnected data-volume UUID mismatch")
            if (physical_store_uuid or "").upper() != self.expected_physical_store_uuid.upper():
                raise StorageContractError("reconnected physical-store UUID mismatch")
        if (
            state is ReconnectState.SAME_DISK_REOPENED
            and disk_identity != self.expected_disk_identity
        ):
            raise StorageContractError("Docker reopened a different disk-image identity")
        if (
            state is ReconnectState.ENGINE_HEALTHY
            and engine_identity != self.expected_engine_identity
        ):
            raise StorageContractError("Docker engine identity changed after reconnect")
        self.state = state


_SETTINGS_ALLOWLIST = frozenset(
    {
        "dataFolder",
        "diskSizeMiB",
        "autoDownloadUpdates",
        "checkForUpdates",
        "useVirtualizationFramework",
    }
)


def sanitize_docker_settings(settings: Mapping[str, object]) -> dict[str, object]:
    """Retain only nonsecret fields needed for placement/version evidence."""

    sanitized = {key: settings[key] for key in sorted(_SETTINGS_ALLOWLIST & settings.keys())}
    for key, value in sanitized.items():
        if not isinstance(value, (str, int, bool)) or isinstance(value, float):
            raise StorageContractError(f"Docker setting {key} has an unsupported evidence type")
    return sanitized


@dataclass(frozen=True, slots=True)
class DockerPlacementEvidence:
    configured_data_folder: Path
    disk_path: Path
    disk_device: int
    disk_inode: int
    disk_logical_bytes: int
    disk_allocated_bytes: int
    engine_identity: str
    settings_sha256: str
    default_internal_exists: bool
    default_internal_active: bool

    def validate(self, *, external_device: int, sanitized_settings: Mapping[str, object]) -> None:
        if self.configured_data_folder != DOCKER_DISK_IMAGE_ROOT:
            raise StorageContractError("Docker configured data folder is not the approved root")
        if not self.disk_path.is_relative_to(DOCKER_DISK_IMAGE_ROOT):
            raise StorageContractError("Docker disk image escaped the approved root")
        if self.disk_device != external_device:
            raise StorageContractError("Docker disk image is not on the approved external device")
        if min(self.disk_inode, self.disk_logical_bytes, self.disk_allocated_bytes) < 0:
            raise StorageContractError("Docker disk-image stat evidence is invalid")
        if not self.engine_identity:
            raise StorageContractError("Docker engine identity is missing")
        encoded = json.dumps(
            dict(sanitized_settings), allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode()
        observed_hash = hashlib.sha256(encoded).hexdigest()
        if self.settings_sha256 != observed_hash:
            raise StorageContractError("sanitized Docker settings hash mismatch")
        if self.default_internal_active:
            raise StorageContractError("default internal Docker disk image is active")
        if self.default_internal_exists:
            raise StorageContractError(
                "default internal Docker disk image still exists; "
                "stop for user-reviewed disposition"
            )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_exclusive(path: Path, value: Mapping[str, object]) -> None:
    encoded = json.dumps(value, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n"
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        with suppress(OSError):
            os.close(descriptor)
        raise


def _regular_file_manifest(root: Path, *, max_bytes: int) -> tuple[list[dict[str, object]], int]:
    if max_bytes <= 0:
        raise StorageContractError("archive byte cap must be positive")
    _assert_no_symlink_components(root, allow_missing_leaf=False)
    if not root.is_dir():
        raise StorageContractError("archive source must be a directory")
    entries: list[dict[str, object]] = []
    casefold_paths: set[str] = set()
    total = 0
    for candidate in sorted(root.rglob("*")):
        mode = candidate.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise StorageContractError("archive source contains a symlink")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise StorageContractError("archive source contains a special file")
        relative = candidate.relative_to(root).as_posix()
        folded = relative.casefold()
        if folded in casefold_paths:
            raise StorageContractError("archive source contains a case-fold path collision")
        casefold_paths.add(folded)
        if candidate.stat().st_nlink != 1:
            raise StorageContractError("archive source contains a hard-linked file")
        if relative in {"SEAL.json", "COPY_RECORD.json"}:
            raise StorageContractError("archive source contains a reserved evidence filename")
        size = candidate.stat().st_size
        total += size
        if total > max_bytes:
            raise StorageContractError("archive source exceeds its byte cap")
        entries.append({"path": relative, "bytes": size, "sha256": file_sha256(candidate)})
    return entries, total


def seal_attempt(source: Path, *, attempt_id: str, max_bytes: int) -> Mapping[str, object]:
    """Fsync, hash, and make a closed attempt tree read-only."""

    entries, total = _regular_file_manifest(source, max_bytes=max_bytes)
    for entry in entries:
        candidate = source / str(entry["path"])
        with candidate.open("rb") as handle:
            os.fsync(handle.fileno())
    for directory in sorted(
        (candidate for candidate in source.rglob("*") if candidate.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        _fsync_directory(directory)
    seal: dict[str, object] = {
        "schema_version": "0.1.0",
        "attempt_id": attempt_id,
        "total_payload_bytes": total,
        "files": entries,
    }
    _write_json_exclusive(source / "SEAL.json", seal)
    _fsync_directory(source)
    for entry in entries:
        os.chmod(source / str(entry["path"]), 0o400)
    os.chmod(source / "SEAL.json", 0o400)
    for directory in sorted(
        (candidate for candidate in source.rglob("*") if candidate.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        os.chmod(directory, 0o500)
    os.chmod(source, 0o500)
    return seal


def copy_sealed_attempt(
    source: Path,
    *,
    archive_parent: Path,
    archive_id: str,
    copy_record_path: Path,
    max_bytes: int,
    source_volume_uuid: str,
    destination_volume_uuid: str,
    copied_at_utc: str,
) -> Mapping[str, object]:
    """Copy an immutable source to a fresh staging tree and verify before rename.

    The source is deliberately retained.  No cleanup or deletion is performed.
    """

    if (
        _UUID.fullmatch(source_volume_uuid.upper()) is None
        or _UUID.fullmatch(destination_volume_uuid.upper()) is None
    ):
        raise StorageContractError("archive copy volume UUID is invalid")
    if _UTC_TIMESTAMP.fullmatch(copied_at_utc) is None:
        raise StorageContractError("archive copy timestamp must be an exact UTC value")
    seal_path = source / "SEAL.json"
    if not seal_path.is_file() or stat.S_IMODE(source.stat().st_mode) & 0o222:
        raise StorageContractError("source attempt is not sealed and immutable")
    seal = json.loads(seal_path.read_text())
    if not isinstance(seal, dict) or not isinstance(seal.get("files"), list):
        raise StorageContractError("source seal is malformed")
    total = seal.get("total_payload_bytes")
    if not isinstance(total, int) or isinstance(total, bool) or total > max_bytes:
        raise StorageContractError("source seal exceeds the archive cap")
    _assert_no_symlink_components(archive_parent, allow_missing_leaf=False)
    if not archive_parent.is_dir():
        raise StorageContractError("archive parent must exist")
    staging = archive_parent / f".{archive_id}.partial"
    destination = archive_parent / archive_id
    if staging.exists() or destination.exists():
        raise StorageContractError("archive identity is not fresh")
    staging.mkdir(mode=0o700)
    try:
        for raw_entry in seal["files"]:
            if not isinstance(raw_entry, dict):
                raise StorageContractError("source seal entry is malformed")
            relative = Path(str(raw_entry.get("path", "")))
            if relative.is_absolute() or ".." in relative.parts:
                raise StorageContractError("source seal contains a path escape")
            source_file = source / relative
            if not source_file.is_file() or source_file.is_symlink():
                raise StorageContractError("sealed source file is missing or unsafe")
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "wb") as output, source_file.open("rb") as input_handle:
                shutil.copyfileobj(input_handle, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            expected_size = raw_entry.get("bytes")
            expected_hash = raw_entry.get("sha256")
            if target.stat().st_size != expected_size or file_sha256(target) != expected_hash:
                raise StorageContractError("destination archive verification failed")
        shutil.copyfile(seal_path, staging / "SEAL.json")
        with (staging / "SEAL.json").open("rb") as handle:
            os.fsync(handle.fileno())
        for directory in sorted(
            (candidate for candidate in staging.rglob("*") if candidate.is_dir()),
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            _fsync_directory(directory)
        _fsync_directory(staging)
        staging.rename(destination)
        _fsync_directory(archive_parent)
    except Exception:
        # A failed staging tree is evidence owned by the caller.  Never delete it here.
        raise
    expected_paths = {str(entry["path"]) for entry in seal["files"] if isinstance(entry, dict)} | {
        "SEAL.json"
    }
    actual_paths = {
        candidate.relative_to(destination).as_posix()
        for candidate in destination.rglob("*")
        if candidate.is_file()
    }
    if actual_paths != expected_paths:
        raise StorageContractError("final archive path set differs from the source seal")
    for raw_entry in seal["files"]:
        assert isinstance(raw_entry, dict)
        final_relative = raw_entry.get("path")
        expected_hash = raw_entry.get("sha256")
        if not isinstance(final_relative, str) or not isinstance(expected_hash, str):
            raise StorageContractError("source seal entry identity is malformed")
        if file_sha256(source / final_relative) != expected_hash:
            raise StorageContractError("sealed source mutated during archival copy")
        if file_sha256(destination / final_relative) != expected_hash:
            raise StorageContractError("final archive file hash mismatch")
    record: dict[str, object] = {
        "schema_version": "0.1.0",
        "archive_id": archive_id,
        "source_path": str(source),
        "destination_path": str(destination),
        "source_device": source.stat().st_dev,
        "destination_device": destination.stat().st_dev,
        "source_volume_uuid": source_volume_uuid.upper(),
        "destination_volume_uuid": destination_volume_uuid.upper(),
        "copied_at_utc": copied_at_utc,
        "seal_sha256": file_sha256(seal_path),
        "destination_seal_sha256": file_sha256(destination / "SEAL.json"),
        "files_verified": len(seal["files"]),
        "total_payload_bytes": total,
        "source_retained": True,
    }
    if record["seal_sha256"] != record["destination_seal_sha256"]:
        raise StorageContractError("destination seal hash mismatch")
    copy_record_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_json_exclusive(copy_record_path, record)
    _fsync_directory(copy_record_path.parent)
    return record


class B2AStepKind(StrEnum):
    AUTOMATABLE = "automatable"
    USER_ONLY = "user-only"


@dataclass(frozen=True, slots=True)
class B2AStep:
    action_id: str
    kind: B2AStepKind
    timeout_seconds: int
    output_limit_bytes: int
    argv: tuple[str, ...] | None
    instruction: str | None
    stop_on_failure: bool
    retry_limit: int

    def validate(self) -> None:
        if _ACTION_ID.fullmatch(self.action_id) is None:
            raise StorageContractError("invalid Gate B2a action ID")
        if self.timeout_seconds <= 0 or self.output_limit_bytes < 0:
            raise StorageContractError("Gate B2a action limits must be finite")
        if self.retry_limit != 0 or not self.stop_on_failure:
            raise StorageContractError("Gate B2a requires zero retry and stop-on-failure")
        if self.kind is B2AStepKind.AUTOMATABLE:
            if not self.argv or self.instruction is not None:
                raise StorageContractError("automatable actions require only an argv array")
            _validate_b2a_argv(self.argv)
        elif self.argv is not None or not self.instruction:
            raise StorageContractError("user-only actions require an instruction and no argv")


_ALLOWED_EXECUTABLES = frozenset(
    {
        "/usr/bin/git",
        "/usr/bin/curl",
        "/usr/bin/hdiutil",
        "/usr/bin/ditto",
        "/usr/bin/stat",
        "/usr/bin/python3",
        "/usr/sbin/diskutil",
        "/Applications/Docker.app/Contents/Resources/bin/docker",
    }
)
_FORBIDDEN_ARG_FRAGMENTS = (
    " pull",
    " build",
    " run",
    " create",
    " playwright",
    " chromium",
    "openai",
    "api.openai",
    "sira_api_key",
    "openai_api_key",
    "--secret",
    "execute-fixture",
    "execute-condition",
)


def _validate_b2a_argv(argv: Sequence[str]) -> None:
    if not argv or argv[0] not in _ALLOWED_EXECUTABLES:
        raise StorageContractError("Gate B2a executable is not allowlisted")
    joined = " " + " ".join(argv).casefold()
    if any(fragment in joined for fragment in _FORBIDDEN_ARG_FRAGMENTS):
        raise StorageContractError("Gate B2a action contains a prohibited workload operation")
    if argv[0].endswith("/docker"):
        if len(argv) < 2 or argv[1] not in {"version", "info", "context", "system"}:
            raise StorageContractError("Gate B2a Docker command is not read-only or stop-only")
        if argv[1] == "system" and tuple(argv[2:]) != ("dial-stdio",):
            raise StorageContractError("unrecognized Docker system action")


@dataclass(frozen=True, slots=True)
class B2APlan:
    schema_version: str
    plan_id: str
    authorization_reference: str
    authorized: bool
    implementation_commit: str
    aggregate_wall_seconds: int
    aggregate_output_bytes: int
    aggregate_download_bytes: int
    system_floor_inputs: SystemFloorInputs
    external_incremental_disk_bytes: int
    active_attempt_bytes: int
    steps: tuple[B2AStep, ...]
    superseded_plan_id: str
    superseded_plan_sha256: str

    def validate(self) -> None:
        if self.schema_version != "0.1.0":
            raise StorageContractError("unsupported Gate B2a plan schema version")
        if self.plan_id != B2A_PLAN_ID or _PLAN_ID.fullmatch(self.plan_id) is None:
            raise StorageContractError("Gate B2a plan ID is stale or unexpected")
        if self.authorization_reference != B2A_AUTHORIZATION_PLACEHOLDER or self.authorized:
            raise StorageContractError(
                "Gate B2a plan must remain unauthorized with its placeholder"
            )
        if _COMMIT.fullmatch(self.implementation_commit) is None:
            raise StorageContractError("Gate B2a implementation commit is not exact")
        if self.aggregate_wall_seconds <= 0 or self.aggregate_output_bytes <= 0:
            raise StorageContractError("Gate B2a aggregate limits must be finite")
        if self.aggregate_download_bytes != DOCKER_DMG_BYTES:
            raise StorageContractError("Gate B2a download cap must equal the one selected DMG")
        try:
            self.system_floor_inputs.resolved_floor_bytes()
        except StorageContractError:
            # B1.6 is a blocked, unauthorized design plan.  A later executable plan
            # must replace every unknown term and acquire a new hash/authorization.
            if self.authorized:
                raise
        if self.external_incremental_disk_bytes != EXTERNAL_INCREMENTAL_RESERVATION_BYTES:
            raise StorageContractError("Gate B2a external disk cap changed")
        if self.active_attempt_bytes != ACTIVE_ATTEMPT_CAP_BYTES:
            raise StorageContractError("Gate B2a active-attempt cap changed")
        if self.superseded_plan_id != SUPERSEDED_PLAN_ID:
            raise StorageContractError("historical Gate B2 plan supersession is missing")
        if self.superseded_plan_sha256 != SUPERSEDED_PLAN_SHA256:
            raise StorageContractError("historical Gate B2 plan hash changed")
        if not self.steps:
            raise StorageContractError("Gate B2a plan has no ordered actions")
        seen: set[str] = set()
        wall = 0
        output = 0
        for step in self.steps:
            step.validate()
            if step.action_id in seen:
                raise StorageContractError("Gate B2a action IDs must be unique")
            seen.add(step.action_id)
            wall += step.timeout_seconds
            output += step.output_limit_bytes
        if wall > self.aggregate_wall_seconds:
            raise StorageContractError("per-action walls exceed the aggregate wall cap")
        if output > self.aggregate_output_bytes:
            raise StorageContractError("per-action outputs exceed the aggregate output cap")
        required_user_actions = {
            "accept-terms-personally",
            "disable-automatic-update",
            "select-external-disk-location",
            "eject-disconnect",
            "reconnect-remount-unlock",
        }
        observed_user_actions = {
            step.action_id for step in self.steps if step.kind is B2AStepKind.USER_ONLY
        }
        if not required_user_actions.issubset(observed_user_actions):
            raise StorageContractError("Gate B2a user-only action separation is incomplete")


def load_b2a_plan(path: Path, *, expected_sha256: str) -> B2APlan:
    if _SHA256.fullmatch(expected_sha256) is None:
        raise StorageContractError("expected Gate B2a plan hash is invalid")
    if file_sha256(path) != expected_sha256:
        raise StorageContractError("Gate B2a plan hash mismatch")
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise StorageContractError("Gate B2a plan is unreadable") from error
    if not isinstance(raw, dict):
        raise StorageContractError("Gate B2a plan must be a JSON object")
    if raw.get("plan_id") == SUPERSEDED_PLAN_ID:
        raise StorageContractError("historical combined Gate B2 plan is superseded")
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list):
        raise StorageContractError("Gate B2a steps must be an array")
    steps: list[B2AStep] = []
    try:
        for item in steps_raw:
            if not isinstance(item, dict):
                raise StorageContractError("Gate B2a step must be an object")
            argv_raw = item.get("argv")
            argv = None
            if argv_raw is not None:
                if not isinstance(argv_raw, list) or not all(isinstance(v, str) for v in argv_raw):
                    raise StorageContractError("Gate B2a argv must be a string array")
                argv = tuple(argv_raw)
            instruction_raw = item.get("instruction")
            if instruction_raw is not None and not isinstance(instruction_raw, str):
                raise StorageContractError("Gate B2a user instruction must be a string")
            steps.append(
                B2AStep(
                    action_id=str(item["action_id"]),
                    kind=B2AStepKind(str(item["kind"])),
                    timeout_seconds=int(item["timeout_seconds"]),
                    output_limit_bytes=int(item["output_limit_bytes"]),
                    argv=argv,
                    instruction=instruction_raw,
                    stop_on_failure=bool(item["stop_on_failure"]),
                    retry_limit=int(item["retry_limit"]),
                )
            )
        limits = raw["limits"]
        superseded = raw["superseded_plan"]
        if not isinstance(limits, dict) or not isinstance(superseded, dict):
            raise StorageContractError("Gate B2a plan limits/supersession are malformed")
        plan = B2APlan(
            schema_version=str(raw["schema_version"]),
            plan_id=str(raw["plan_id"]),
            authorization_reference=str(raw["authorization_reference"]),
            authorized=bool(raw["authorized"]),
            implementation_commit=str(raw["implementation_commit"]),
            aggregate_wall_seconds=int(limits["aggregate_wall_seconds"]),
            aggregate_output_bytes=int(limits["aggregate_output_bytes"]),
            aggregate_download_bytes=int(limits["aggregate_download_bytes"]),
            system_floor_inputs=SystemFloorInputs(
                os_operating_headroom_bytes=limits["system_floor"]["os_operating_headroom_bytes"],
                dmg_download_peak_bytes=limits["system_floor"]["dmg_download_peak_bytes"],
                installed_app_bytes=limits["system_floor"]["installed_app_bytes"],
                support_files_bytes=limits["system_floor"]["support_files_bytes"],
                update_rollback_bytes=limits["system_floor"]["update_rollback_bytes"],
                active_evidence_bytes=limits["system_floor"]["active_evidence_bytes"],
                failure_cleanup_bytes=limits["system_floor"]["failure_cleanup_bytes"],
                first_start_internal_bytes=limits["system_floor"]["first_start_internal_bytes"],
            ),
            external_incremental_disk_bytes=int(limits["external_incremental_disk_bytes"]),
            active_attempt_bytes=int(limits["active_attempt_bytes"]),
            steps=tuple(steps),
            superseded_plan_id=str(superseded["plan_id"]),
            superseded_plan_sha256=str(superseded["sha256"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, StorageContractError):
            raise
        raise StorageContractError("Gate B2a plan is malformed") from error
    plan.validate()
    return plan
