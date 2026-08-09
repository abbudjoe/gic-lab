"""Gate B1.6 storage qualification control plane for T07.

This module is intentionally local and deterministic.  It does not download or
install Docker, start an engine, invoke a browser, inspect credentials, or call a
network API.  Runtime observations are supplied as typed values by a later,
separately authorized Gate B2a driver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
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
SYSTEM_GICLAB_ROOT = Path("/Users/joseph/.local/share/gic-lab")
ACTIVE_ATTEMPT_ROOT = SYSTEM_GICLAB_ROOT / "t07-gate-b2a/attempts"
B2A_WORK_ROOT = SYSTEM_GICLAB_ROOT / "t07-gate-b2a"
B2A_DOWNLOAD_ROOT = B2A_WORK_ROOT / "downloads"
B2A_EVIDENCE_ROOT = B2A_WORK_ROOT / "evidence"
B2A_SCRIPT_PATH = Path(
    "/Users/joseph/.codex/worktrees/84b1/gic-lab/src/giclab/harness/sira_storage.py"
)
B2A_PYTHON_PATH = Path("/Users/joseph/.codex/worktrees/84b1/gic-lab/.venv/bin/python")
B2A_APPCAST_PATH = B2A_DOWNLOAD_ROOT / "appcast.xml"
B2A_CHECKSUMS_PATH = B2A_DOWNLOAD_ROOT / "checksums.txt"
B2A_DMG_PATH = B2A_DOWNLOAD_ROOT / "Docker-4.85.0-arm64-235549.dmg"
B2A_EVIDENCE_SESSION_ROOT = B2A_EVIDENCE_ROOT / "session"
B2A_CLOSE_EVIDENCE_PATH = B2A_EVIDENCE_SESSION_ROOT / "ATTEMPT_CLOSED.json"
B2A_COPY_RECORD_PATH = B2A_EVIDENCE_ROOT / "copy-records/T07-GATE-B2A-EVIDENCE-001.json"
B2A_IMPLEMENTATION_BOUND_PATHS = (
    "src/giclab/harness/sira_container.py",
    "src/giclab/harness/sira_storage.py",
    "src/giclab/validation.py",
    "schemas/docker-storage-qualification-plan.schema.json",
    "schemas/docker-storage-placement-evidence.schema.json",
    "schemas/sealed-artifact-copy.schema.json",
    "schemas/attempt-close-evidence.schema.json",
)
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
B2A_AGGREGATE_WALL_SECONDS = 7200
B2A_AGGREGATE_OUTPUT_CAP_BYTES = 16 * MIB

DOCKER_DMG_URL = "https://desktop.docker.com/mac/main/arm64/235549/Docker.dmg"
DOCKER_DMG_BYTES = 573_592_444
OFFICIAL_METADATA_DOWNLOAD_CAP_BYTES = 4 * MIB
B2A_AGGREGATE_DOWNLOAD_CAP_BYTES = DOCKER_DMG_BYTES + OFFICIAL_METADATA_DOWNLOAD_CAP_BYTES
DOCKER_DMG_SHA256 = "84b1224c93456fe261955ebc91f3cd88ce19778ffdb6d0a0d423ce37246f7c2b"
DOCKER_PRODUCT_VERSION = "4.85.0"
DOCKER_BUILD = "235549"
DOCKER_MINIMUM_MACOS = "14.0.0"

B2A_PLAN_ID = "PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V1"
B2A_AUTHORIZATION_PLACEHOLDER = "AUTH-T07-GATE-B2A-PENDING"
SUPERSEDED_PLAN_ID = "PLAN-T07-GATE-B2-MATERIALIZATION"
SUPERSEDED_PLAN_SHA256 = "10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25"

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_PLAN_ID = re.compile(r"^PLAN-[A-Z0-9][A-Z0-9._-]{2,127}$")
_ACTION_ID = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
_AUTHORIZATION_REFERENCE = re.compile(r"^AUTH-[A-Z0-9][A-Z0-9._-]{2,127}$")
_B2A_EXECUTABLE_PLAN_ID = re.compile(
    r"^PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V(?:[2-9]|[1-9][0-9]+)[A-Z0-9._-]*$"
)
_ARCHIVE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_UUID = re.compile(r"^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$")
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_SUPERVISOR_CLOSE_ISSUER = object()


def retained_free_floor(total_bytes: int) -> int:
    """Return max(150 GiB, ceil(20% of capacity))."""

    if total_bytes <= 0:
        raise StorageContractError("volume capacity must be positive")
    percent_floor = (total_bytes * PROJECT_FREE_PERCENT + 99) // 100
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
        self.validate_system_floor(floor_inputs.resolved_floor_bytes())

    def validate_system_floor(self, floor_bytes: int) -> None:
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
        if floor_bytes <= 0:
            raise StorageContractError("Mac mini system floor must be positive")
        if self.free_bytes < floor_bytes:
            raise StorageContractError(
                f"system free bytes {self.free_bytes} are below required {floor_bytes}"
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
    locked = raw.get("Locked")
    if not isinstance(locked, bool):
        raise StorageContractError("diskutil lock-state evidence is incomplete")
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
        unlocked=not locked,
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
    device_resolver: Callable[[Path], int] | None = None,
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
            device_resolver=device_resolver,
        )
    else:
        validate_bounded_path(
            path,
            approved_root=SYSTEM_GICLAB_ROOT,
            expected_device=system_mount_device,
            prohibited_device=external_mount_device,
            allow_missing_leaf=allow_missing_leaf,
            device_resolver=device_resolver,
        )


def validate_bounded_path(
    path: Path,
    *,
    approved_root: Path,
    expected_device: int,
    prohibited_device: int,
    allow_missing_leaf: bool,
    device_resolver: Callable[[Path], int] | None = None,
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
    observed_device = observed.st_dev if device_resolver is None else device_resolver(existing)
    if observed_device != expected_device:
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
    system_floor_bytes: int
    external_volume: bool
    allow_missing_leaf: bool
    guard_id: str
    issued_monotonic_ns: int
    maximum_age_ns: int = 5_000_000_000
    consumed: bool = False

    def consume(
        self,
        *,
        observation: VolumeObservation,
        now_monotonic_ns: int | None = None,
        device_resolver: Callable[[Path], int] | None = None,
    ) -> None:
        if self.consumed:
            raise StorageContractError("storage guard token was already consumed")
        current_ns = time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
        if current_ns < self.issued_monotonic_ns or (
            current_ns - self.issued_monotonic_ns > self.maximum_age_ns
        ):
            raise StorageContractError("storage guard token is stale")
        if observation.volume_uuid.upper() != self.volume_uuid.upper():
            raise StorageContractError("storage identity changed after guard issuance")
        if self.external_volume:
            if (observation.physical_store_uuid or "").upper() != self.physical_store_uuid.upper():
                raise StorageContractError("storage identity changed after guard issuance")
            observation.validate_external(reserve_incremental=True)
        else:
            observation.validate_system_floor(self.system_floor_bytes)
        validate_path_contract(
            self.path,
            purpose=self.purpose,
            external_mount_device=self.external_device,
            system_mount_device=self.system_device,
            allow_missing_leaf=self.allow_missing_leaf,
            device_resolver=device_resolver,
        )
        self.consumed = True


@dataclass(slots=True)
class StorageGuardBundle:
    """Typed, fresh storage evidence consumed by exactly one planned action."""

    guard_id: str
    external: VolumeObservation
    system: VolumeObservation
    external_device: int
    system_device: int
    system_floor_bytes: int
    issued_monotonic_ns: int
    tokens: dict[RootPurpose, StorageGuardToken]

    def consume(
        self,
        purposes: Sequence[RootPurpose],
        *,
        now_monotonic_ns: int | None = None,
        device_resolver: Callable[[Path], int] | None = None,
    ) -> None:
        requested = tuple(purposes)
        if not requested or len(set(requested)) != len(requested):
            raise StorageContractError("storage guard purposes must be unique and nonempty")
        for purpose in requested:
            guard_capability = self.tokens.get(purpose)
            if guard_capability is None:
                raise StorageContractError("storage guard does not cover the requested purpose")
            observation = self.external if guard_capability.external_volume else self.system
            guard_capability.consume(
                observation=observation,
                now_monotonic_ns=now_monotonic_ns,
                device_resolver=device_resolver,
            )

    def all_consumed(self, purposes: Sequence[RootPurpose]) -> bool:
        return all(purpose in self.tokens and self.tokens[purpose].consumed for purpose in purposes)

    def document(self) -> dict[str, object]:
        return {
            "guard_id": self.guard_id,
            "issued_monotonic_ns": self.issued_monotonic_ns,
            "external_volume_uuid": self.external.volume_uuid,
            "external_physical_store_uuid": self.external.physical_store_uuid,
            "external_free_bytes": self.external.free_bytes,
            "system_volume_uuid": self.system.volume_uuid,
            "system_free_bytes": self.system.free_bytes,
            "system_floor_bytes": self.system_floor_bytes,
            "purposes": sorted(purpose.value for purpose in self.tokens),
        }


def issue_storage_guard(
    *,
    external: VolumeObservation,
    system: VolumeObservation,
    external_device: int,
    system_device: int,
    system_floor_bytes: int,
    purposes: Sequence[RootPurpose],
    require_existing: bool,
    issued_monotonic_ns: int | None = None,
    device_resolver: Callable[[Path], int] | None = None,
) -> StorageGuardBundle:
    """Validate current observations and mint one-shot path-bound guard tokens."""

    external.validate_external(reserve_incremental=True)
    system.validate_system_floor(system_floor_bytes)
    requested = tuple(purposes)
    if not requested or len(set(requested)) != len(requested):
        raise StorageContractError("storage guard purposes must be unique and nonempty")
    issued = time.monotonic_ns() if issued_monotonic_ns is None else issued_monotonic_ns
    if issued <= 0:
        raise StorageContractError("storage guard monotonic timestamp must be positive")
    guard_material = json.dumps(
        {
            "external_uuid": external.volume_uuid.upper(),
            "physical_uuid": (external.physical_store_uuid or "").upper(),
            "system_uuid": system.volume_uuid.upper(),
            "external_device": external_device,
            "system_device": system_device,
            "system_floor_bytes": system_floor_bytes,
            "purposes": sorted(purpose.value for purpose in requested),
            "issued_monotonic_ns": issued,
        },
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    guard_id = hashlib.sha256(guard_material).hexdigest()
    tokens: dict[RootPurpose, StorageGuardToken] = {}
    paths = {
        RootPurpose.DOCKER_DISK: DOCKER_DISK_IMAGE_ROOT,
        RootPurpose.BUILD_STAGING: BUILD_STAGING_ROOT,
        RootPurpose.SEALED_ARCHIVE: SEALED_ARTIFACT_ROOT,
        RootPurpose.ACTIVE_ATTEMPT: ACTIVE_ATTEMPT_ROOT,
        RootPurpose.B2A_WORK: B2A_WORK_ROOT,
    }
    for purpose in requested:
        path = paths[purpose]
        validate_path_contract(
            path,
            purpose=purpose,
            external_mount_device=external_device,
            system_mount_device=system_device,
            allow_missing_leaf=not require_existing,
            device_resolver=device_resolver,
        )
        external_volume = purpose in {
            RootPurpose.DOCKER_DISK,
            RootPurpose.BUILD_STAGING,
            RootPurpose.SEALED_ARCHIVE,
        }
        observation = external if external_volume else system
        tokens[purpose] = StorageGuardToken(
            purpose=purpose,
            path=path,
            volume_uuid=observation.volume_uuid,
            physical_store_uuid=(observation.physical_store_uuid or ""),
            external_device=external_device,
            system_device=system_device,
            system_floor_bytes=system_floor_bytes,
            external_volume=external_volume,
            allow_missing_leaf=not require_existing,
            guard_id=guard_id,
            issued_monotonic_ns=issued,
        )
    return StorageGuardBundle(
        guard_id=guard_id,
        external=external,
        system=system,
        external_device=external_device,
        system_device=system_device,
        system_floor_bytes=system_floor_bytes,
        issued_monotonic_ns=issued,
        tokens=tokens,
    )


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
class DockerDiskIdentity:
    path: Path
    inode: int
    logical_bytes: int
    birthtime_ns: int

    def validate(self) -> None:
        if not self.path.is_relative_to(DOCKER_DISK_IMAGE_ROOT):
            raise StorageContractError("Docker disk identity escaped the approved root")
        if self.inode <= 0 or self.logical_bytes <= 0 or self.birthtime_ns <= 0:
            raise StorageContractError("Docker disk identity fields must be positive")


@dataclass(slots=True)
class DockerEngineIdentity:
    engine_id: str
    context: str
    server_os: str
    architecture: str
    healthy: bool
    default_internal_active: bool

    def validate(self) -> None:
        if not self.engine_id or not self.context:
            raise StorageContractError("Docker engine/context identity is missing")
        if self.server_os.casefold() != "linux" or self.architecture != "aarch64":
            raise StorageContractError("Docker engine platform is not Linux aarch64")
        if not self.healthy or self.default_internal_active:
            raise StorageContractError("Docker engine is unhealthy or uses internal storage")


@dataclass(slots=True)
class ReconnectQualification:
    expected_volume_uuid: str
    expected_physical_store_uuid: str
    expected_disk_identity: DockerDiskIdentity
    expected_engine_identity: DockerEngineIdentity
    state: ReconnectState = ReconnectState.INITIAL
    _qualified_guard: StorageGuardBundle | None = field(default=None, init=False, repr=False)

    def advance(
        self,
        state: ReconnectState,
        *,
        volume_observation: VolumeObservation | None = None,
        storage_guard: StorageGuardBundle | None = None,
        disk_identity: DockerDiskIdentity | None = None,
        engine_identity: DockerEngineIdentity | None = None,
        now_monotonic_ns: int | None = None,
        device_resolver: Callable[[Path], int] | None = None,
    ) -> None:
        current_index = (
            -1 if self.state is ReconnectState.INITIAL else _RECONNECT_SEQUENCE.index(self.state)
        )
        if (
            current_index + 1 >= len(_RECONNECT_SEQUENCE)
            or _RECONNECT_SEQUENCE[current_index + 1] is not state
        ):
            raise StorageContractError("reconnect evidence is stale, duplicated, or out of order")
        if state is ReconnectState.VOLUME_REQUALIFIED:
            if volume_observation is None:
                raise StorageContractError("reconnected volume evidence is missing")
            volume_observation.validate_external(reserve_incremental=True)
            if volume_observation.volume_uuid.upper() != self.expected_volume_uuid.upper():
                raise StorageContractError("reconnected data-volume UUID mismatch")
            if (
                volume_observation.physical_store_uuid or ""
            ).upper() != self.expected_physical_store_uuid.upper():
                raise StorageContractError("reconnected physical-store UUID mismatch")
        if state is ReconnectState.PATHS_REQUALIFIED:
            if storage_guard is None:
                raise StorageContractError("reconnected path guard evidence is missing")
            purposes = (
                RootPurpose.DOCKER_DISK,
                RootPurpose.BUILD_STAGING,
                RootPurpose.SEALED_ARCHIVE,
            )
            storage_guard.consume(
                purposes,
                now_monotonic_ns=now_monotonic_ns,
                device_resolver=device_resolver,
            )
            self._qualified_guard = storage_guard
        if state is ReconnectState.USER_ENGINE_RESTARTED:
            purposes = (
                RootPurpose.DOCKER_DISK,
                RootPurpose.BUILD_STAGING,
                RootPurpose.SEALED_ARCHIVE,
            )
            if (
                storage_guard is None
                or storage_guard is not self._qualified_guard
                or not storage_guard.all_consumed(purposes)
            ):
                raise StorageContractError(
                    "Docker restart is not bound to the consumed reconnect guard"
                )
        if (
            state is ReconnectState.SAME_DISK_REOPENED
            and disk_identity != self.expected_disk_identity
        ):
            raise StorageContractError("Docker reopened a different disk-image identity")
        if state is ReconnectState.SAME_DISK_REOPENED:
            assert disk_identity is not None
            disk_identity.validate()
        if (
            state is ReconnectState.ENGINE_HEALTHY
            and engine_identity != self.expected_engine_identity
        ):
            raise StorageContractError("Docker engine identity changed after reconnect")
        if state is ReconnectState.ENGINE_HEALTHY:
            assert engine_identity is not None
            engine_identity.validate()
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

    def validate(
        self,
        *,
        external_device: int,
        sanitized_settings: Mapping[str, object],
        observed_stat: os.stat_result | None = None,
    ) -> None:
        if sanitized_settings.get("dataFolder") != str(DOCKER_DISK_IMAGE_ROOT):
            raise StorageContractError(
                "sanitized Docker settings do not bind the approved data folder"
            )
        if self.configured_data_folder != DOCKER_DISK_IMAGE_ROOT:
            raise StorageContractError("Docker configured data folder is not the approved root")
        if (
            ".." in self.disk_path.parts
            or self.disk_path.parent != DOCKER_DISK_IMAGE_ROOT
            or not self.disk_path.name
        ):
            raise StorageContractError("Docker disk image escaped the approved root")
        if observed_stat is None:
            try:
                observed_stat = self.disk_path.lstat()
            except OSError as error:
                raise StorageContractError(
                    "Docker disk image stat evidence is unavailable"
                ) from error
        if stat.S_ISLNK(observed_stat.st_mode) or not stat.S_ISREG(observed_stat.st_mode):
            raise StorageContractError("Docker disk image is not one regular non-symlink file")
        if self.disk_device != external_device or observed_stat.st_dev != external_device:
            raise StorageContractError("Docker disk image is not on the approved external device")
        if (
            self.disk_inode <= 0
            or self.disk_logical_bytes <= 0
            or self.disk_allocated_bytes < 0
            or observed_stat.st_ino != self.disk_inode
            or observed_stat.st_size != self.disk_logical_bytes
        ):
            raise StorageContractError("Docker disk-image stat evidence is invalid")
        observed_blocks = getattr(observed_stat, "st_blocks", None)
        if (
            not isinstance(observed_blocks, int)
            or self.disk_allocated_bytes != observed_blocks * 512
        ):
            raise StorageContractError("Docker allocated-byte stat evidence is invalid")
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


def _write_json_exclusive_at(
    directory_descriptor: int,
    filename: str,
    value: Mapping[str, object],
) -> None:
    if not filename or filename in {".", ".."} or "/" in filename:
        raise StorageContractError("evidence filename is unsafe")
    encoded = json.dumps(value, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n"
    descriptor = os.open(
        filename,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory_descriptor,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


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
    if not entries:
        raise StorageContractError("archive source contains no evidence files")
    return entries, total


def _device_for_path(path: Path) -> int:
    return path.stat(follow_symlinks=False).st_dev


@dataclass(slots=True)
class ArchivePlacementToken:
    """Fresh, single-use proof that an archive copy crosses the approved volumes."""

    source: Path
    archive_parent: Path
    source_device: int
    destination_device: int
    source_volume_uuid: str
    destination_volume_uuid: str
    system_floor_bytes: int
    issued_monotonic_ns: int
    maximum_age_ns: int = 5_000_000_000
    consumed: bool = False

    def consume(
        self,
        *,
        source_observation: VolumeObservation,
        destination_observation: VolumeObservation,
        now_monotonic_ns: int | None = None,
        device_resolver: Callable[[Path], int] = _device_for_path,
    ) -> None:
        if self.consumed:
            raise StorageContractError("archive placement token was already consumed")
        current_ns = time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
        if current_ns < self.issued_monotonic_ns or (
            current_ns - self.issued_monotonic_ns > self.maximum_age_ns
        ):
            raise StorageContractError("archive placement token is stale")
        source_observation.validate_system_floor(self.system_floor_bytes)
        destination_observation.validate_external(reserve_incremental=True)
        if source_observation.volume_uuid.upper() != self.source_volume_uuid:
            raise StorageContractError("archive source volume identity changed")
        if destination_observation.volume_uuid.upper() != self.destination_volume_uuid:
            raise StorageContractError("archive destination volume identity changed")
        _validate_archive_roots(
            self.source,
            self.archive_parent,
            source_device=self.source_device,
            destination_device=self.destination_device,
            device_resolver=device_resolver,
        )
        self.consumed = True


def _validate_archive_roots(
    source: Path,
    archive_parent: Path,
    *,
    source_device: int,
    destination_device: int,
    device_resolver: Callable[[Path], int],
) -> None:
    if source_device == destination_device:
        raise StorageContractError("archive source and destination must be different volumes")
    if source == B2A_EVIDENCE_SESSION_ROOT:
        approved_source_root = B2A_EVIDENCE_ROOT
    elif source.parent == ACTIVE_ATTEMPT_ROOT and _ARCHIVE_ID.fullmatch(source.name):
        approved_source_root = ACTIVE_ATTEMPT_ROOT
    else:
        raise StorageContractError("archive source is outside the approved active roots")
    if archive_parent != SEALED_ARTIFACT_ROOT:
        raise StorageContractError("archive destination is not the approved sealed root")
    validate_bounded_path(
        source,
        approved_root=approved_source_root,
        expected_device=source_device,
        prohibited_device=destination_device,
        allow_missing_leaf=False,
        device_resolver=device_resolver,
    )
    validate_bounded_path(
        archive_parent,
        approved_root=APPROVED_EXTERNAL_ROOT,
        expected_device=destination_device,
        prohibited_device=source_device,
        allow_missing_leaf=False,
        device_resolver=device_resolver,
    )


def qualify_archive_placement(
    source: Path,
    *,
    archive_parent: Path,
    source_observation: VolumeObservation,
    destination_observation: VolumeObservation,
    system_floor_bytes: int,
    issued_monotonic_ns: int | None = None,
    device_resolver: Callable[[Path], int] = _device_for_path,
) -> ArchivePlacementToken:
    source_observation.validate_system_floor(system_floor_bytes)
    destination_observation.validate_external(reserve_incremental=True)
    source_device = device_resolver(SYSTEM_DATA_MOUNT)
    destination_device = device_resolver(APPROVED_MOUNT)
    _validate_archive_roots(
        source,
        archive_parent,
        source_device=source_device,
        destination_device=destination_device,
        device_resolver=device_resolver,
    )
    issued = time.monotonic_ns() if issued_monotonic_ns is None else issued_monotonic_ns
    if issued <= 0:
        raise StorageContractError("archive placement timestamp must be positive")
    return ArchivePlacementToken(
        source=source,
        archive_parent=archive_parent,
        source_device=source_device,
        destination_device=destination_device,
        source_volume_uuid=source_observation.volume_uuid.upper(),
        destination_volume_uuid=destination_observation.volume_uuid.upper(),
        system_floor_bytes=system_floor_bytes,
        issued_monotonic_ns=issued,
    )


def _copy_file_exclusive(source: Path, target: Path) -> None:
    descriptor = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_handle:
            shutil.copyfileobj(input_handle, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        with suppress(OSError):
            os.close(descriptor)
        raise


@dataclass(slots=True)
class AttemptCloseEvidence:
    attempt_id: str
    source_path: Path
    supervisor_plan_id: str
    supervisor_plan_sha256: str
    authorization_reference: str
    all_actions_before_seal_complete: bool
    open_writer_count: int
    closed_at_utc: str
    _issuer: object = field(repr=False, compare=False)
    _consumed: bool = field(default=False, init=False, repr=False, compare=False)

    def validate(self, *, source: Path, attempt_id: str) -> None:
        if self._issuer is not _SUPERVISOR_CLOSE_ISSUER or self._consumed:
            raise StorageContractError("attempt close capability is untrusted or already consumed")
        if (
            _ARCHIVE_ID.fullmatch(self.attempt_id) is None
            or self.attempt_id != attempt_id
            or self.source_path != source
        ):
            raise StorageContractError("attempt close evidence identity/path mismatch")
        if (
            _B2A_EXECUTABLE_PLAN_ID.fullmatch(self.supervisor_plan_id) is None
            or _SHA256.fullmatch(self.supervisor_plan_sha256) is None
            or _AUTHORIZATION_REFERENCE.fullmatch(self.authorization_reference) is None
            or self.authorization_reference == B2A_AUTHORIZATION_PLACEHOLDER
        ):
            raise StorageContractError("attempt close evidence lacks executable authority")
        if (
            not self.all_actions_before_seal_complete
            or type(self.open_writer_count) is not int
            or self.open_writer_count != 0
        ):
            raise StorageContractError("attempt close evidence does not prove writer closure")
        if _UTC_TIMESTAMP.fullmatch(self.closed_at_utc) is None:
            raise StorageContractError("attempt close timestamp must be exact UTC")

    def consume(self, *, source: Path, attempt_id: str) -> None:
        self.validate(source=source, attempt_id=attempt_id)
        self._consumed = True

    def document(self) -> dict[str, object]:
        return {
            "schema_version": "0.1.0",
            "attempt_id": self.attempt_id,
            "source_path": str(self.source_path),
            "supervisor_plan_id": self.supervisor_plan_id,
            "supervisor_plan_sha256": self.supervisor_plan_sha256,
            "authorization_reference": self.authorization_reference,
            "all_actions_before_seal_complete": self.all_actions_before_seal_complete,
            "open_writer_count": self.open_writer_count,
            "closed_at_utc": self.closed_at_utc,
        }


def _set_user_immutable(path: Path) -> None:
    immutable_flag = getattr(stat, "UF_IMMUTABLE", None)
    change_flags = getattr(os, "chflags", None)
    current_flags = getattr(path.stat(follow_symlinks=False), "st_flags", None)
    if (
        not isinstance(immutable_flag, int)
        or change_flags is None
        or not isinstance(current_flags, int)
    ):
        raise StorageContractError("filesystem user-immutable flags are unavailable")
    change_flags(path, current_flags | immutable_flag, follow_symlinks=False)
    if not _is_user_immutable(path):
        raise StorageContractError("filesystem user-immutable flag did not persist")


def _is_user_immutable(path: Path) -> bool:
    immutable_flag = getattr(stat, "UF_IMMUTABLE", None)
    current_flags = getattr(path.stat(follow_symlinks=False), "st_flags", None)
    return (
        isinstance(immutable_flag, int)
        and isinstance(current_flags, int)
        and bool(current_flags & immutable_flag)
    )


def _validate_copy_record_parent(
    copy_record_path: Path,
    *,
    source_device: int,
    destination_device: int,
    device_resolver: Callable[[Path], int],
) -> None:
    expected_parent = B2A_EVIDENCE_ROOT / "copy-records"
    if copy_record_path.parent != expected_parent:
        raise StorageContractError("archive copy record escaped its approved root")
    validate_bounded_path(
        expected_parent,
        approved_root=B2A_EVIDENCE_ROOT,
        expected_device=source_device,
        prohibited_device=destination_device,
        allow_missing_leaf=True,
        device_resolver=device_resolver,
    )


def _write_copy_record_safely(
    copy_record_path: Path,
    record: Mapping[str, object],
    *,
    source_device: int,
    destination_device: int,
    device_resolver: Callable[[Path], int],
) -> None:
    """Create and write the exact record directory through held no-follow handles."""

    _validate_copy_record_parent(
        copy_record_path,
        source_device=source_device,
        destination_device=destination_device,
        device_resolver=device_resolver,
    )
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    root_descriptor = -1
    record_descriptor = -1
    try:
        root_descriptor = os.open(B2A_EVIDENCE_ROOT, directory_flags)
        with suppress(FileExistsError):
            os.mkdir("copy-records", mode=0o700, dir_fd=root_descriptor)
        try:
            record_descriptor = os.open(
                "copy-records",
                directory_flags,
                dir_fd=root_descriptor,
            )
        except OSError as error:
            raise StorageContractError(
                "archive copy-record directory is a symlink or non-directory"
            ) from error
        record_stat = os.fstat(record_descriptor)
        linked_stat = os.stat(
            "copy-records",
            dir_fd=root_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(record_stat.st_mode)
            or not stat.S_ISDIR(linked_stat.st_mode)
            or (record_stat.st_dev, record_stat.st_ino) != (linked_stat.st_dev, linked_stat.st_ino)
            or device_resolver(copy_record_path.parent) != source_device
        ):
            raise StorageContractError("archive copy-record directory identity changed")
        _write_json_exclusive_at(record_descriptor, copy_record_path.name, record)
        os.fsync(record_descriptor)
        written = os.stat(
            copy_record_path.name,
            dir_fd=record_descriptor,
            follow_symlinks=False,
        )
        if not stat.S_ISREG(written.st_mode) or written.st_nlink != 1:
            raise StorageContractError("archive copy record is not one regular file")
    finally:
        if record_descriptor >= 0:
            os.close(record_descriptor)
        if root_descriptor >= 0:
            os.close(root_descriptor)


def seal_attempt(
    source: Path,
    *,
    attempt_id: str,
    max_bytes: int,
    close_evidence: AttemptCloseEvidence,
    immutable_setter: Callable[[Path], None] = _set_user_immutable,
) -> Mapping[str, object]:
    """Require typed writer closure, then fsync, hash, and flag the tree immutable."""

    if _ARCHIVE_ID.fullmatch(attempt_id) is None:
        raise StorageContractError("attempt identity is unsafe")
    close_evidence.consume(source=source, attempt_id=attempt_id)
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
    for entry in entries:
        with (source / str(entry["path"])).open("rb") as handle:
            os.fsync(handle.fileno())
    with (source / "SEAL.json").open("rb") as handle:
        os.fsync(handle.fileno())
    _fsync_directory(source.parent)
    immutable_paths = [
        *(source / str(entry["path"]) for entry in entries),
        source / "SEAL.json",
        *sorted(
            (candidate for candidate in source.rglob("*") if candidate.is_dir()),
            key=lambda item: len(item.parts),
            reverse=True,
        ),
        source,
    ]
    for candidate in immutable_paths:
        immutable_setter(candidate)
    return seal


def copy_sealed_attempt(
    source: Path,
    *,
    archive_parent: Path,
    archive_id: str,
    copy_record_path: Path,
    max_bytes: int,
    placement: ArchivePlacementToken,
    source_observation: VolumeObservation,
    destination_observation: VolumeObservation,
    copied_at_utc: str,
    now_monotonic_ns: int | None = None,
    device_resolver: Callable[[Path], int] = _device_for_path,
    immutability_probe: Callable[[Path], bool] = _is_user_immutable,
) -> Mapping[str, object]:
    """Copy an immutable source to a fresh staging tree and verify before rename.

    The source is deliberately retained.  No cleanup or deletion is performed.
    """

    if _ARCHIVE_ID.fullmatch(archive_id) is None:
        raise StorageContractError("archive identity is unsafe")
    expected_copy_record = B2A_EVIDENCE_ROOT / "copy-records" / f"{archive_id}.json"
    if copy_record_path != expected_copy_record or ".." in copy_record_path.parts:
        raise StorageContractError("archive copy record escaped its approved root")
    if _UTC_TIMESTAMP.fullmatch(copied_at_utc) is None:
        raise StorageContractError("archive copy timestamp must be an exact UTC value")
    if placement.source != source or placement.archive_parent != archive_parent:
        raise StorageContractError("archive placement token paths do not match the copy")
    _validate_copy_record_parent(
        copy_record_path,
        source_device=placement.source_device,
        destination_device=placement.destination_device,
        device_resolver=device_resolver,
    )
    placement.consume(
        source_observation=source_observation,
        destination_observation=destination_observation,
        now_monotonic_ns=now_monotonic_ns,
        device_resolver=device_resolver,
    )
    seal_path = source / "SEAL.json"
    if not seal_path.is_file() or stat.S_IMODE(source.stat().st_mode) & 0o222:
        raise StorageContractError("source attempt is not sealed and immutable")
    seal = json.loads(seal_path.read_text())
    if not isinstance(seal, dict) or not isinstance(seal.get("files"), list):
        raise StorageContractError("source seal is malformed")
    if seal.get("attempt_id") != archive_id:
        raise StorageContractError("source seal identity differs from the archive identity")
    total = seal.get("total_payload_bytes")
    if not isinstance(total, int) or isinstance(total, bool) or total > max_bytes:
        raise StorageContractError("source seal exceeds the archive cap")
    immutable_paths = [source, seal_path]
    immutable_paths.extend(candidate for candidate in source.rglob("*") if candidate != seal_path)
    if not all(immutability_probe(candidate) for candidate in immutable_paths):
        raise StorageContractError("source attempt lacks filesystem immutability")
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
            _copy_file_exclusive(source_file, target)
            expected_size = raw_entry.get("bytes")
            expected_hash = raw_entry.get("sha256")
            if target.stat().st_size != expected_size or file_sha256(target) != expected_hash:
                raise StorageContractError("destination archive verification failed")
        _copy_file_exclusive(seal_path, staging / "SEAL.json")
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
    for candidate in (path for path in destination.rglob("*") if path.is_file()):
        os.chmod(candidate, 0o400)
        with candidate.open("rb") as handle:
            os.fsync(handle.fileno())
    for directory in sorted(
        (candidate for candidate in destination.rglob("*") if candidate.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        os.chmod(directory, 0o500)
        _fsync_directory(directory)
    os.chmod(destination, 0o500)
    _fsync_directory(archive_parent)
    record: dict[str, object] = {
        "schema_version": "0.1.0",
        "archive_id": archive_id,
        "source_path": str(source),
        "destination_path": str(destination),
        "source_device": placement.source_device,
        "destination_device": placement.destination_device,
        "source_volume_uuid": source_observation.volume_uuid.upper(),
        "destination_volume_uuid": destination_observation.volume_uuid.upper(),
        "source_mount_path": str(source_observation.mount_path),
        "destination_mount_path": str(destination_observation.mount_path),
        "destination_physical_store_uuid": (
            destination_observation.physical_store_uuid or ""
        ).upper(),
        "copied_at_utc": copied_at_utc,
        "seal_sha256": file_sha256(seal_path),
        "destination_seal_sha256": file_sha256(destination / "SEAL.json"),
        "files_verified": len(seal["files"]),
        "total_payload_bytes": total,
        "source_retained": True,
        "source_immutable": True,
        "destination_read_only": True,
    }
    if record["seal_sha256"] != record["destination_seal_sha256"]:
        raise StorageContractError("destination seal hash mismatch")
    _write_copy_record_safely(
        copy_record_path,
        record,
        source_device=placement.source_device,
        destination_device=placement.destination_device,
        device_resolver=device_resolver,
    )
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
    download_limit_bytes: int
    internal_disk_limit_bytes: int | None
    external_disk_limit_bytes: int
    argv: tuple[str, ...] | None
    instruction: str | None
    stop_on_failure: bool
    retry_limit: int
    expected_stdout: str | None = None
    guard_for_action: str | None = None
    guard_purposes: tuple[RootPurpose, ...] = ()

    def validate(self, *, system_floor_bytes: int | None = None) -> None:
        if _ACTION_ID.fullmatch(self.action_id) is None:
            raise StorageContractError("invalid Gate B2a action ID")
        if (
            self.timeout_seconds <= 0
            or self.output_limit_bytes < 0
            or self.download_limit_bytes < 0
            or self.external_disk_limit_bytes < 0
            or (self.internal_disk_limit_bytes is not None and self.internal_disk_limit_bytes < 0)
        ):
            raise StorageContractError("Gate B2a action limits must be finite")
        if self.retry_limit != 0 or not self.stop_on_failure:
            raise StorageContractError("Gate B2a requires zero retry and stop-on-failure")
        if self.kind is B2AStepKind.AUTOMATABLE:
            if not self.argv or self.instruction is not None:
                raise StorageContractError("automatable actions require only an argv array")
            _validate_b2a_argv(self.argv, system_floor_bytes=system_floor_bytes)
        elif self.argv is not None or not self.instruction:
            raise StorageContractError("user-only actions require an instruction and no argv")
        if self.kind is B2AStepKind.USER_ONLY and self.expected_stdout is not None:
            raise StorageContractError("user-only actions cannot declare expected stdout")
        if self.guard_for_action is None:
            if self.guard_purposes:
                raise StorageContractError("only guard actions may declare guard purposes")
        else:
            expected_scope = _B2A_GUARD_SCOPES.get(self.guard_for_action)
            expected_floor = "unresolved" if system_floor_bytes is None else str(system_floor_bytes)
            if (
                self.kind is not B2AStepKind.AUTOMATABLE
                or _ACTION_ID.fullmatch(self.guard_for_action) is None
                or not self.guard_purposes
                or len(set(self.guard_purposes)) != len(self.guard_purposes)
                or self.argv is None
                or "guard-storage" not in self.argv
                or expected_scope is None
                or self.guard_purposes != expected_scope[0]
                or self.argv
                != _guard_argv(
                    self.guard_for_action,
                    expected_scope[0],
                    require_existing=expected_scope[1],
                    system_floor_bytes=expected_floor,
                )
            ):
                raise StorageContractError("Gate B2a guard action metadata is malformed")

    def requires_storage_guard(self) -> bool:
        if self.guard_for_action is not None:
            return False
        if (
            self.download_limit_bytes > 0
            or self.external_disk_limit_bytes > 0
            or self.internal_disk_limit_bytes is None
            or (self.internal_disk_limit_bytes or 0) > 0
        ):
            return True
        if self.argv is not None and self.argv[0] in {
            "/bin/mkdir",
            "/usr/bin/ditto",
            "/usr/bin/hdiutil",
            "/usr/bin/open",
        }:
            return True
        return self.action_id in {
            "select-external-disk-location",
            "apply-storage-binding-restart",
            "restart-after-remount-guard",
            "seal-and-copy-b2a-evidence",
        }


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
        "/Users/joseph/.codex/worktrees/84b1/gic-lab/.venv/bin/python",
        "/bin/mkdir",
        "/usr/libexec/PlistBuddy",
        "/usr/bin/open",
    }
)
_FORBIDDEN_ARG_FRAGMENTS = (
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

_B2A_GUARD_SCOPES: Mapping[str, tuple[tuple[RootPurpose, ...], bool]] = {
    "create-external-project-root": (
        (RootPurpose.DOCKER_DISK, RootPurpose.BUILD_STAGING, RootPurpose.SEALED_ARCHIVE),
        False,
    ),
    "create-external-t07-root": (
        (RootPurpose.DOCKER_DISK, RootPurpose.BUILD_STAGING, RootPurpose.SEALED_ARCHIVE),
        False,
    ),
    "create-external-docker-parent": ((RootPurpose.DOCKER_DISK,), False),
    "create-external-docker-disk-root": ((RootPurpose.DOCKER_DISK,), False),
    "create-external-build-staging": ((RootPurpose.BUILD_STAGING,), False),
    "create-external-sealed-artifacts": ((RootPurpose.SEALED_ARCHIVE,), False),
    "create-b2a-work-root": ((RootPurpose.B2A_WORK,), False),
    "create-b2a-download-root": ((RootPurpose.B2A_WORK,), False),
    "create-b2a-evidence-root": ((RootPurpose.B2A_WORK,), False),
    "create-b2a-evidence-session": ((RootPurpose.B2A_WORK,), False),
    "fetch-current-appcast": ((RootPurpose.B2A_WORK,), True),
    "fetch-current-checksums": ((RootPurpose.B2A_WORK,), True),
    "download-selected-dmg": ((RootPurpose.B2A_WORK,), True),
    "attach-selected-dmg": ((RootPurpose.B2A_WORK,), True),
    "install-selected-application": ((RootPurpose.B2A_WORK,), True),
    "detach-selected-dmg": ((RootPurpose.B2A_WORK,), True),
    "accept-terms-personally": ((RootPurpose.B2A_WORK,), True),
    "disable-automatic-update": ((RootPurpose.B2A_WORK,), True),
    "initial-start-after-guard": (
        (RootPurpose.DOCKER_DISK, RootPurpose.BUILD_STAGING, RootPurpose.B2A_WORK),
        True,
    ),
    "select-external-disk-location": (
        (RootPurpose.DOCKER_DISK, RootPurpose.BUILD_STAGING, RootPurpose.B2A_WORK),
        True,
    ),
    "apply-storage-binding-restart": (
        (RootPurpose.DOCKER_DISK, RootPurpose.BUILD_STAGING, RootPurpose.B2A_WORK),
        True,
    ),
    "capture-location-only-screenshot": ((RootPurpose.B2A_WORK,), True),
    "restart-after-remount-guard": (
        (
            RootPurpose.DOCKER_DISK,
            RootPurpose.BUILD_STAGING,
            RootPurpose.SEALED_ARCHIVE,
            RootPurpose.B2A_WORK,
        ),
        True,
    ),
    "seal-and-copy-b2a-evidence": (
        (RootPurpose.SEALED_ARCHIVE, RootPurpose.B2A_WORK),
        True,
    ),
}


def _validate_b2a_argv(argv: Sequence[str], *, system_floor_bytes: int | None = None) -> None:
    if not argv or argv[0] not in _ALLOWED_EXECUTABLES:
        raise StorageContractError("Gate B2a executable is not allowlisted")
    joined = " " + " ".join(argv).casefold()
    if any(fragment in joined for fragment in _FORBIDDEN_ARG_FRAGMENTS):
        raise StorageContractError("Gate B2a action contains a prohibited workload operation")
    exact = tuple(argv)
    if (
        len(exact) == 5
        and exact[:3] == ("/usr/bin/git", "merge-base", "--is-ancestor")
        and _COMMIT.fullmatch(exact[3]) is not None
        and exact[4] == "HEAD"
    ):
        return
    if (
        len(exact) == 5 + len(B2A_IMPLEMENTATION_BOUND_PATHS)
        and exact[:3] == ("/usr/bin/git", "diff", "--quiet")
        and _COMMIT.fullmatch(exact[3]) is not None
        and exact[4] == "--"
        and exact[5:] == B2A_IMPLEMENTATION_BOUND_PATHS
    ):
        return
    is_guard_action = "guard-storage" in exact
    is_seal_action = "seal-and-copy" in exact
    if exact in _allowed_b2a_argv() and not (
        (is_guard_action or is_seal_action) and system_floor_bytes is not None
    ):
        return
    guard_floor = "unresolved" if system_floor_bytes is None else str(system_floor_bytes)
    if exact == _seal_and_copy_argv(system_floor_bytes=guard_floor):
        return
    for action_id, (purposes, require_existing) in _B2A_GUARD_SCOPES.items():
        if exact == _guard_argv(
            action_id,
            purposes,
            require_existing=require_existing,
            system_floor_bytes=guard_floor,
        ):
            return
    raise StorageContractError("Gate B2a argument array is not an exact rendered action")


def _curl_argv(*, url: str, output: Path, max_seconds: int, max_bytes: int) -> tuple[str, ...]:
    return (
        "/usr/bin/curl",
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--proto",
        "=https",
        "--tlsv1.2",
        "--max-time",
        str(max_seconds),
        "--max-filesize",
        str(max_bytes),
        "--output",
        str(output),
        url,
    )


def _guard_argv(
    action_id: str,
    purposes: Sequence[RootPurpose],
    *,
    require_existing: bool,
    system_floor_bytes: str = "unresolved",
) -> tuple[str, ...]:
    argv = (
        str(B2A_PYTHON_PATH),
        str(B2A_SCRIPT_PATH),
        "guard-storage",
        "--system-floor-bytes",
        system_floor_bytes,
        "--next-action",
        action_id,
        "--purposes",
        ",".join(purpose.value for purpose in purposes),
    )
    return argv + (("--require-existing",) if require_existing else ())


def _seal_and_copy_argv(*, system_floor_bytes: str) -> tuple[str, ...]:
    return (
        str(B2A_PYTHON_PATH),
        str(B2A_SCRIPT_PATH),
        "seal-and-copy",
        "--source",
        str(B2A_EVIDENCE_SESSION_ROOT),
        "--archive-parent",
        str(SEALED_ARTIFACT_ROOT),
        "--archive-id",
        "T07-GATE-B2A-EVIDENCE-001",
        "--copy-record",
        str(B2A_COPY_RECORD_PATH),
        "--max-bytes",
        str(B2A_EVIDENCE_CAP_BYTES),
        "--system-floor-bytes",
        system_floor_bytes,
    )


def _allowed_b2a_argv() -> frozenset[tuple[str, ...]]:
    python_prefix = (str(B2A_PYTHON_PATH), str(B2A_SCRIPT_PATH))
    docker = "/Applications/Docker.app/Contents/Resources/bin/docker"
    directories = {
        APPROVED_EXTERNAL_ROOT,
        APPROVED_EXTERNAL_ROOT / "t07",
        APPROVED_EXTERNAL_ROOT / "t07/docker-desktop",
        DOCKER_DISK_IMAGE_ROOT,
        BUILD_STAGING_ROOT,
        SEALED_ARTIFACT_ROOT,
        B2A_WORK_ROOT,
        B2A_DOWNLOAD_ROOT,
        B2A_EVIDENCE_ROOT,
        B2A_EVIDENCE_SESSION_ROOT,
    }
    commands: set[tuple[str, ...]] = {
        ("/usr/bin/git", "status", "--short"),
        ("/usr/bin/git", "branch", "--show-current"),
        diskutil_info_argv(APPROVED_MOUNT),
        diskutil_info_argv(SYSTEM_DATA_MOUNT),
        ("/usr/sbin/diskutil", "apfs", "list", "-plist"),
        _curl_argv(
            url="https://desktop.docker.com/mac/main/arm64/appcast.xml",
            output=B2A_APPCAST_PATH,
            max_seconds=60,
            max_bytes=2 * MIB,
        ),
        _curl_argv(
            url="https://desktop.docker.com/mac/main/arm64/235549/checksums.txt",
            output=B2A_CHECKSUMS_PATH,
            max_seconds=60,
            max_bytes=2 * MIB,
        ),
        _curl_argv(
            url=DOCKER_DMG_URL,
            output=B2A_DMG_PATH,
            max_seconds=600,
            max_bytes=DOCKER_DMG_BYTES,
        ),
        (
            *python_prefix,
            "verify-official-metadata",
            "--appcast",
            str(B2A_APPCAST_PATH),
            "--checksums",
            str(B2A_CHECKSUMS_PATH),
        ),
        (*python_prefix, "verify-dmg", "--path", str(B2A_DMG_PATH)),
        (*python_prefix, "assert-path-absent", "--path", "/Applications/Docker.app"),
        _seal_and_copy_argv(system_floor_bytes="unresolved"),
        (
            "/usr/bin/hdiutil",
            "attach",
            "-readonly",
            "-nobrowse",
            str(B2A_DMG_PATH),
        ),
        ("/usr/bin/hdiutil", "detach", "/Volumes/Docker"),
        (
            "/usr/bin/ditto",
            "/Volumes/Docker/Docker.app",
            "/Applications/Docker.app",
        ),
        (
            "/usr/libexec/PlistBuddy",
            "-c",
            "Print :CFBundleShortVersionString",
            "/Applications/Docker.app/Contents/Info.plist",
        ),
        (
            "/usr/libexec/PlistBuddy",
            "-c",
            "Print :CFBundleVersion",
            "/Applications/Docker.app/Contents/Info.plist",
        ),
        (docker, "version", "--format", "{{json .}}"),
        (docker, "info", "--format", "{{json .}}"),
        (docker, "context", "show"),
        ("/usr/bin/open", "-na", "/Applications/Docker.app"),
    }
    commands.update(("/bin/mkdir", "-m", "0700", str(path)) for path in directories)
    commands.update(
        _guard_argv(action_id, purposes, require_existing=require_existing)
        for action_id, (purposes, require_existing) in _B2A_GUARD_SCOPES.items()
    )
    return frozenset(commands)


def inspect_and_guard_current_storage(
    *,
    system_floor_bytes: int,
    purposes: Sequence[RootPurpose],
    require_existing: bool,
) -> StorageGuardBundle:
    """Inspect both volumes and enforce every path/floor predicate in one process."""

    commands = (
        diskutil_info_argv(APPROVED_MOUNT),
        ("/usr/sbin/diskutil", "apfs", "list", "-plist"),
        diskutil_info_argv(SYSTEM_DATA_MOUNT),
    )
    outputs: list[bytes] = []
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise StorageContractError("read-only diskutil storage inspection failed") from error
        if completed.stderr or len(completed.stdout) > MIB:
            raise StorageContractError("diskutil storage evidence exceeded its clean output cap")
        outputs.append(completed.stdout)
    external = volume_observation_from_diskutil(outputs[0], outputs[1])
    system = volume_observation_from_diskutil(outputs[2], outputs[1])
    external_device = APPROVED_MOUNT.stat().st_dev
    system_device = SYSTEM_DATA_MOUNT.stat().st_dev
    return issue_storage_guard(
        external=external,
        system=system,
        external_device=external_device,
        system_device=system_device,
        system_floor_bytes=system_floor_bytes,
        purposes=purposes,
        require_existing=require_existing,
    )


@dataclass(frozen=True, slots=True)
class B2APlan:
    schema_version: str
    plan_id: str
    status: str
    blocking_requirements: tuple[str, ...]
    authorization_reference: str
    authorized: bool
    implementation_commit: str
    aggregate_wall_seconds: int
    aggregate_output_bytes: int
    aggregate_download_bytes: int
    system_incremental_disk_bytes: int | None
    system_floor_inputs: SystemFloorInputs
    external_incremental_disk_bytes: int
    active_attempt_bytes: int
    steps: tuple[B2AStep, ...]
    superseded_plan_id: str
    superseded_plan_sha256: str
    aggregate_automatable_calls: int | None = None
    document_sha256: str | None = None

    def validate(self) -> None:
        if self.schema_version != "0.1.0":
            raise StorageContractError("unsupported Gate B2a plan schema version")
        if _PLAN_ID.fullmatch(self.plan_id) is None:
            raise StorageContractError("Gate B2a plan ID is malformed")
        if self.authorized:
            if (
                self.plan_id == B2A_PLAN_ID
                or _B2A_EXECUTABLE_PLAN_ID.fullmatch(self.plan_id) is None
                or self.status != "authorized-executable"
            ):
                raise StorageContractError(
                    "authorized Gate B2a requires a new executable plan identity"
                )
            if self.blocking_requirements:
                raise StorageContractError("authorized Gate B2a cannot retain blockers")
            if (
                self.authorization_reference == B2A_AUTHORIZATION_PLACEHOLDER
                or _AUTHORIZATION_REFERENCE.fullmatch(self.authorization_reference) is None
            ):
                raise StorageContractError("authorized Gate B2a plan lacks fresh authority")
        elif (
            self.plan_id != B2A_PLAN_ID
            or self.status != "blocked-design-only"
            or self.authorization_reference != B2A_AUTHORIZATION_PLACEHOLDER
        ):
            raise StorageContractError(
                "blocked Gate B2a plan must retain its V1 identity and placeholder"
            )
        elif not self.blocking_requirements:
            raise StorageContractError("blocked Gate B2a plan must enumerate blockers")
        if _COMMIT.fullmatch(self.implementation_commit) is None:
            raise StorageContractError("Gate B2a implementation commit is not exact")
        if self.document_sha256 is not None and _SHA256.fullmatch(self.document_sha256) is None:
            raise StorageContractError("Gate B2a loaded document hash is malformed")
        if self.aggregate_wall_seconds != B2A_AGGREGATE_WALL_SECONDS:
            raise StorageContractError("Gate B2a aggregate wall cap changed")
        if self.aggregate_output_bytes != B2A_AGGREGATE_OUTPUT_CAP_BYTES:
            raise StorageContractError("Gate B2a aggregate output cap changed")
        if self.aggregate_download_bytes != B2A_AGGREGATE_DOWNLOAD_CAP_BYTES:
            raise StorageContractError("Gate B2a download cap changed")
        resolved_system_floor: int | None = None
        try:
            resolved_system_floor = self.system_floor_inputs.resolved_floor_bytes()
        except StorageContractError:
            # B1.6 is a blocked, unauthorized design plan.  A later executable plan
            # must replace every unknown term and acquire a new hash/authorization.
            if self.authorized:
                raise
        if self.authorized:
            if (
                self.system_incremental_disk_bytes is None
                or self.system_incremental_disk_bytes <= 0
            ):
                raise StorageContractError("authorized Gate B2a system disk cap is unresolved")
        elif self.system_incremental_disk_bytes is not None:
            raise StorageContractError("blocked B1.6 plan must not invent a Mac mini disk cap")
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
        download = 0
        steps_by_id: dict[str, B2AStep] = {}
        for step in self.steps:
            step.validate(system_floor_bytes=(resolved_system_floor if self.authorized else None))
            if step.action_id in seen:
                raise StorageContractError("Gate B2a action IDs must be unique")
            seen.add(step.action_id)
            steps_by_id[step.action_id] = step
            wall += step.timeout_seconds
            output += step.output_limit_bytes
            download += step.download_limit_bytes
        automatable_calls = sum(step.kind is B2AStepKind.AUTOMATABLE for step in self.steps)
        if self.aggregate_automatable_calls != automatable_calls:
            raise StorageContractError("Gate B2a automatable-call cap must equal the exact plan")
        if wall > self.aggregate_wall_seconds:
            raise StorageContractError("per-action walls exceed the aggregate wall cap")
        if output > self.aggregate_output_bytes:
            raise StorageContractError("per-action outputs exceed the aggregate output cap")
        if download > self.aggregate_download_bytes:
            raise StorageContractError("per-action downloads exceed the aggregate download cap")
        expected_repository_steps = {
            "repository-status": (
                ("/usr/bin/git", "status", "--short"),
                "",
            ),
            "repository-branch": (
                ("/usr/bin/git", "branch", "--show-current"),
                "phase-1/sira-smoke\n",
            ),
            "repository-implementation-ancestor": (
                (
                    "/usr/bin/git",
                    "merge-base",
                    "--is-ancestor",
                    self.implementation_commit,
                    "HEAD",
                ),
                "",
            ),
            "repository-implementation-tree": (
                (
                    "/usr/bin/git",
                    "diff",
                    "--quiet",
                    self.implementation_commit,
                    "--",
                    *B2A_IMPLEMENTATION_BOUND_PATHS,
                ),
                "",
            ),
        }
        for action_id, (argv, expected_stdout) in expected_repository_steps.items():
            bound_step = steps_by_id.get(action_id)
            if (
                bound_step is None
                or bound_step.kind is not B2AStepKind.AUTOMATABLE
                or bound_step.argv != argv
                or bound_step.expected_stdout != expected_stdout
            ):
                raise StorageContractError(
                    "Gate B2a repository/implementation binding is incomplete"
                )
        for index, step in enumerate(self.steps):
            if not step.requires_storage_guard():
                continue
            if index == 0:
                raise StorageContractError("sensitive Gate B2a action lacks a preceding guard")
            guard = self.steps[index - 1]
            if guard.guard_for_action != step.action_id:
                raise StorageContractError("sensitive Gate B2a action lacks an adjacent guard")
            if self.authorized and step.internal_disk_limit_bytes is None:
                raise StorageContractError("authorized Gate B2a action has an unresolved disk cap")
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


def _read_plan_bytes_once(path: Path) -> bytes:
    if not path.is_absolute() or path.resolve(strict=False) != path or path.is_symlink():
        raise StorageContractError("Gate B2a plan path must be absolute and canonical")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise StorageContractError("Gate B2a plan is unreadable") from error
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_size > 4 * MIB:
            raise StorageContractError("Gate B2a plan must be one bounded regular file")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            return handle.read(4 * MIB + 1)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _strict_int(value: object, label: str, *, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if type(value) is not int:
        raise StorageContractError(f"{label} must be an exact integer")
    return value


def _strict_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise StorageContractError(f"{label} must be a string")
    return value


def _strict_string_list(value: object, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise StorageContractError(f"{label} must be a nonempty string array")
    return value


def _require_exact_keys(value: object, expected: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise StorageContractError(f"{label} fields are incomplete or unexpected")
    return value


def load_b2a_plan(path: Path, *, expected_sha256: str) -> B2APlan:
    """Hash and parse the same canonical bytes, then enforce executable authority fields."""

    if _SHA256.fullmatch(expected_sha256) is None:
        raise StorageContractError("expected Gate B2a plan hash is invalid")
    encoded = _read_plan_bytes_once(path)
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise StorageContractError("Gate B2a plan hash mismatch")
    try:
        parsed = json.loads(encoded)
    except json.JSONDecodeError as error:
        raise StorageContractError("Gate B2a plan is not JSON") from error
    root_keys = {
        "schema_version",
        "plan_id",
        "authorization_reference",
        "authorized",
        "status",
        "implementation_commit",
        "artifact",
        "paths",
        "limits",
        "steps",
        "stop_conditions",
        "rollback_cleanup",
        "blocking_requirements",
        "superseded_plan",
    }
    raw = _require_exact_keys(parsed, root_keys, "Gate B2a plan")
    authorized_raw = raw["authorized"]
    if type(authorized_raw) is not bool:
        raise StorageContractError("Gate B2a authorized field must be boolean")
    authorized = authorized_raw
    plan_id = _strict_string(raw["plan_id"], "Gate B2a plan ID")
    if plan_id == SUPERSEDED_PLAN_ID:
        raise StorageContractError("historical combined Gate B2 plan is superseded")

    expected_artifact = {
        "product": "Docker Desktop",
        "version": DOCKER_PRODUCT_VERSION,
        "build": DOCKER_BUILD,
        "platform": "macos/arm64",
        "url": DOCKER_DMG_URL,
        "bytes": DOCKER_DMG_BYTES,
        "sha256": DOCKER_DMG_SHA256,
        "verification_status": (
            "current-verified"
            if authorized
            else "historically-verified-current-reverification-required"
        ),
    }
    artifact = _require_exact_keys(raw["artifact"], set(expected_artifact), "Gate B2a artifact")
    if any(
        type(artifact[key]) is not type(value) or artifact[key] != value
        for key, value in expected_artifact.items()
    ):
        raise StorageContractError("Gate B2a artifact identity/status changed")
    expected_paths = {
        "external_root": str(APPROVED_EXTERNAL_ROOT),
        "docker_disk_image": str(DOCKER_DISK_IMAGE_ROOT),
        "build_staging": str(BUILD_STAGING_ROOT),
        "sealed_artifacts": str(SEALED_ARTIFACT_ROOT),
        "active_attempts": str(ACTIVE_ATTEMPT_ROOT),
        "b2a_work": str(B2A_WORK_ROOT),
        "downloads": str(B2A_DOWNLOAD_ROOT),
        "evidence": str(B2A_EVIDENCE_ROOT),
    }
    paths = _require_exact_keys(raw["paths"], set(expected_paths), "Gate B2a paths")
    if paths != expected_paths:
        raise StorageContractError("Gate B2a exact path contract changed")

    limit_keys = {
        "aggregate_wall_seconds",
        "aggregate_output_bytes",
        "aggregate_download_bytes",
        "aggregate_automatable_calls",
        "system_incremental_disk_bytes",
        "external_incremental_disk_bytes",
        "active_attempt_bytes",
        "evidence_bytes",
        "retry_limit",
        "external_retained_free_floor_bytes",
        "external_pre_action_free_floor_bytes",
        "system_floor",
    }
    limits = _require_exact_keys(raw["limits"], limit_keys, "Gate B2a limits")
    floor_keys = {
        "status",
        "os_operating_headroom_bytes",
        "dmg_download_peak_bytes",
        "installed_app_bytes",
        "support_files_bytes",
        "update_rollback_bytes",
        "active_evidence_bytes",
        "failure_cleanup_bytes",
        "first_start_internal_bytes",
    }
    floor = _require_exact_keys(limits["system_floor"], floor_keys, "Gate B2a system floor")
    expected_floor_status = "resolved" if authorized else "unresolved-blocking"
    if floor["status"] != expected_floor_status:
        raise StorageContractError("Gate B2a system-floor status contradicts authority")
    if (
        floor["dmg_download_peak_bytes"] != DOCKER_DMG_BYTES
        or floor["active_evidence_bytes"] != ACTIVE_ATTEMPT_CAP_BYTES
    ):
        raise StorageContractError("Gate B2a fixed system-floor inputs changed")
    floor_inputs = SystemFloorInputs(
        os_operating_headroom_bytes=_strict_int(
            floor["os_operating_headroom_bytes"], "system os headroom", nullable=True
        ),
        dmg_download_peak_bytes=_strict_int(
            floor["dmg_download_peak_bytes"], "system DMG peak", nullable=True
        ),
        installed_app_bytes=_strict_int(
            floor["installed_app_bytes"], "installed app bytes", nullable=True
        ),
        support_files_bytes=_strict_int(
            floor["support_files_bytes"], "support files bytes", nullable=True
        ),
        update_rollback_bytes=_strict_int(
            floor["update_rollback_bytes"], "update rollback bytes", nullable=True
        ),
        active_evidence_bytes=_strict_int(
            floor["active_evidence_bytes"], "active evidence bytes", nullable=True
        ),
        failure_cleanup_bytes=_strict_int(
            floor["failure_cleanup_bytes"], "failure cleanup bytes", nullable=True
        ),
        first_start_internal_bytes=_strict_int(
            floor["first_start_internal_bytes"], "first-start internal bytes", nullable=True
        ),
    )
    if (
        _strict_int(limits["evidence_bytes"], "evidence cap") != B2A_EVIDENCE_CAP_BYTES
        or _strict_int(limits["retry_limit"], "retry cap") != 0
        or _strict_int(limits["external_retained_free_floor_bytes"], "external floor")
        != EXTERNAL_RETAINED_FREE_FLOOR_BYTES
        or _strict_int(limits["external_pre_action_free_floor_bytes"], "external pre-floor")
        != EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES
    ):
        raise StorageContractError("Gate B2a fixed evidence/retry/floor limits changed")

    steps_raw = raw["steps"]
    if not isinstance(steps_raw, list) or not steps_raw:
        raise StorageContractError("Gate B2a steps must be a nonempty array")
    base_step_keys = {
        "action_id",
        "kind",
        "timeout_seconds",
        "output_limit_bytes",
        "download_limit_bytes",
        "internal_disk_limit_bytes",
        "external_disk_limit_bytes",
        "stop_on_failure",
        "retry_limit",
    }
    optional_step_keys = {
        "argv",
        "instruction",
        "expected_stdout",
        "guard_for_action",
        "guard_purposes",
    }
    steps: list[B2AStep] = []
    try:
        for item_raw in steps_raw:
            if (
                not isinstance(item_raw, dict)
                or not base_step_keys.issubset(item_raw)
                or not set(item_raw).issubset(base_step_keys | optional_step_keys)
            ):
                raise StorageContractError("Gate B2a step fields are incomplete or unexpected")
            if item_raw["stop_on_failure"] is not True:
                raise StorageContractError("Gate B2a step must stop on failure")
            argv_raw = item_raw.get("argv")
            if argv_raw is not None and (
                not isinstance(argv_raw, list)
                or not argv_raw
                or any(not isinstance(value, str) for value in argv_raw)
            ):
                raise StorageContractError("Gate B2a argv must be a nonempty string array")
            guard_raw = item_raw.get("guard_purposes", [])
            if not isinstance(guard_raw, list) or any(
                not isinstance(value, str) for value in guard_raw
            ):
                raise StorageContractError("Gate B2a guard purposes must be a string array")
            instruction = item_raw.get("instruction")
            expected_stdout = item_raw.get("expected_stdout")
            guard_target = item_raw.get("guard_for_action")
            if instruction is not None and not isinstance(instruction, str):
                raise StorageContractError("Gate B2a instruction must be a string")
            if expected_stdout is not None and not isinstance(expected_stdout, str):
                raise StorageContractError("Gate B2a expected stdout must be a string")
            if guard_target is not None and not isinstance(guard_target, str):
                raise StorageContractError("Gate B2a guard target must be a string")
            internal_limit = _strict_int(
                item_raw["internal_disk_limit_bytes"],
                "per-action internal disk cap",
                nullable=True,
            )
            steps.append(
                B2AStep(
                    action_id=_strict_string(item_raw["action_id"], "Gate B2a action ID"),
                    kind=B2AStepKind(_strict_string(item_raw["kind"], "Gate B2a action kind")),
                    timeout_seconds=_strict_int(item_raw["timeout_seconds"], "action timeout") or 0,
                    output_limit_bytes=_strict_int(
                        item_raw["output_limit_bytes"], "action output cap"
                    )
                    or 0,
                    download_limit_bytes=_strict_int(
                        item_raw["download_limit_bytes"], "action download cap"
                    )
                    or 0,
                    internal_disk_limit_bytes=internal_limit,
                    external_disk_limit_bytes=_strict_int(
                        item_raw["external_disk_limit_bytes"], "action external disk cap"
                    )
                    or 0,
                    argv=None if argv_raw is None else tuple(argv_raw),
                    instruction=instruction,
                    stop_on_failure=True,
                    retry_limit=_strict_int(item_raw["retry_limit"], "action retry cap") or 0,
                    expected_stdout=expected_stdout,
                    guard_for_action=guard_target,
                    guard_purposes=tuple(RootPurpose(value) for value in guard_raw),
                )
            )
    except ValueError as error:
        raise StorageContractError("Gate B2a step enum value is invalid") from error

    superseded = _require_exact_keys(
        raw["superseded_plan"], {"plan_id", "sha256"}, "superseded plan"
    )
    if superseded != {"plan_id": SUPERSEDED_PLAN_ID, "sha256": SUPERSEDED_PLAN_SHA256}:
        raise StorageContractError("historical Gate B2 supersession identity changed")
    for label in ("stop_conditions", "rollback_cleanup"):
        _strict_string_list(raw[label], f"Gate B2a {label}")
    blockers_raw = raw["blocking_requirements"]
    if not isinstance(blockers_raw, list) or any(
        not isinstance(value, str) or not value for value in blockers_raw
    ):
        raise StorageContractError("Gate B2a blockers must be a string array")
    if (authorized and blockers_raw) or (not authorized and not blockers_raw):
        raise StorageContractError("Gate B2a blockers contradict authorization state")
    plan = B2APlan(
        schema_version=_strict_string(raw["schema_version"], "Gate B2a schema version"),
        plan_id=plan_id,
        status=_strict_string(raw["status"], "Gate B2a status"),
        blocking_requirements=tuple(blockers_raw),
        authorization_reference=_strict_string(
            raw["authorization_reference"], "authorization reference"
        ),
        authorized=authorized,
        implementation_commit=_strict_string(raw["implementation_commit"], "implementation commit"),
        aggregate_wall_seconds=_strict_int(limits["aggregate_wall_seconds"], "aggregate wall") or 0,
        aggregate_output_bytes=_strict_int(limits["aggregate_output_bytes"], "aggregate output")
        or 0,
        aggregate_download_bytes=_strict_int(
            limits["aggregate_download_bytes"], "aggregate download"
        )
        or 0,
        system_incremental_disk_bytes=_strict_int(
            limits["system_incremental_disk_bytes"], "system disk cap", nullable=True
        ),
        system_floor_inputs=floor_inputs,
        external_incremental_disk_bytes=_strict_int(
            limits["external_incremental_disk_bytes"], "external disk cap"
        )
        or 0,
        active_attempt_bytes=_strict_int(limits["active_attempt_bytes"], "active attempt cap") or 0,
        steps=tuple(steps),
        superseded_plan_id=_strict_string(superseded["plan_id"], "superseded plan ID"),
        superseded_plan_sha256=_strict_string(superseded["sha256"], "superseded plan SHA"),
        aggregate_automatable_calls=_strict_int(
            limits["aggregate_automatable_calls"], "automatable call cap"
        ),
        document_sha256=expected_sha256,
    )
    plan.validate()
    return plan


@dataclass(frozen=True, slots=True)
class B2AResourceSnapshot:
    system_free_bytes: int
    external_free_bytes: int
    active_attempt_bytes: int

    def validate(self) -> None:
        if (
            min(
                self.system_free_bytes,
                self.external_free_bytes,
                self.active_attempt_bytes,
            )
            < 0
        ):
            raise StorageContractError("Gate B2a resource snapshot contains negative bytes")


@dataclass(frozen=True, slots=True)
class B2AActionResult:
    exit_code: int
    stdout: bytes
    stderr: bytes
    downloaded_bytes: int
    resources_after: B2AResourceSnapshot


class B2AExecutionSupervisor:
    """Stateful cap/order/guard control plane for a future authorized B2a driver.

    The supervisor deliberately does not spawn processes.  A separately authorized
    driver must feed it observations immediately before and after each exact argv or
    user action.  This keeps the B1.6 implementation deterministic and testable.
    """

    def __init__(
        self,
        plan: B2APlan,
        *,
        expected_plan_id: str,
        expected_plan_sha256: str,
        expected_authorization_reference: str,
    ) -> None:
        plan.validate()
        if (
            plan.plan_id != expected_plan_id
            or plan.document_sha256 != expected_plan_sha256
            or plan.authorization_reference != expected_authorization_reference
            or _SHA256.fullmatch(expected_plan_sha256) is None
        ):
            raise StorageContractError(
                "Gate B2a execution boundary does not match external authority"
            )
        if not plan.authorized:
            raise StorageContractError("Gate B2a plan is unauthorized; execution is blocked")
        self.plan = plan
        self.system_floor_bytes = plan.system_floor_inputs.resolved_floor_bytes()
        assert plan.system_incremental_disk_bytes is not None
        self._index = 0
        self._started_ns: int | None = None
        self._action_started_ns: int | None = None
        self._before: B2AResourceSnapshot | None = None
        self._active_step: B2AStep | None = None
        self._pending_guard: StorageGuardBundle | None = None
        self._pending_guard_target: str | None = None
        self._close_capability: AttemptCloseEvidence | None = None
        self._output_bytes = 0
        self._download_bytes = 0
        self._internal_growth_bytes = 0
        self._external_growth_bytes = 0
        self._automatable_calls = 0

    def start(self, resources: B2AResourceSnapshot, *, now_monotonic_ns: int) -> None:
        if self._started_ns is not None or now_monotonic_ns <= 0:
            raise StorageContractError("Gate B2a supervisor start is stale or duplicated")
        self._validate_snapshot(resources, pre_action=True, external_mutation=False)
        self._started_ns = now_monotonic_ns

    def begin_action(
        self,
        action_id: str,
        resources: B2AResourceSnapshot,
        *,
        now_monotonic_ns: int,
        device_resolver: Callable[[Path], int] | None = None,
    ) -> B2AStep:
        if self._started_ns is None or self._active_step is not None:
            raise StorageContractError("Gate B2a action begin is out of state")
        if self._index >= len(self.plan.steps):
            raise StorageContractError("Gate B2a has no remaining action")
        step = self.plan.steps[self._index]
        if step.action_id != action_id:
            raise StorageContractError("Gate B2a action is stale or out of order")
        if step.action_id == "seal-and-copy-b2a-evidence" and self._close_capability is None:
            raise StorageContractError(
                "Gate B2a sealing lacks supervisor-owned writer-closure evidence"
            )
        if now_monotonic_ns < self._started_ns:
            raise StorageContractError("Gate B2a monotonic clock moved backwards")
        self._validate_aggregate_wall(now_monotonic_ns)
        self._validate_snapshot(
            resources,
            pre_action=True,
            external_mutation=step.external_disk_limit_bytes > 0,
        )
        if step.requires_storage_guard():
            if self._pending_guard is None or self._pending_guard_target != step.action_id:
                raise StorageContractError("sensitive Gate B2a action lacks a fresh guard")
            guard_step = self.plan.steps[self._index - 1]
            self._pending_guard.consume(
                guard_step.guard_purposes,
                now_monotonic_ns=now_monotonic_ns,
                device_resolver=device_resolver,
            )
            self._pending_guard = None
            self._pending_guard_target = None
        if step.kind is B2AStepKind.AUTOMATABLE:
            self._automatable_calls += 1
            assert self.plan.aggregate_automatable_calls is not None
            if self._automatable_calls > self.plan.aggregate_automatable_calls:
                raise StorageContractError("Gate B2a automatable-call cap exceeded")
        self._active_step = step
        self._action_started_ns = now_monotonic_ns
        self._before = resources
        return step

    def finish_action(
        self,
        result: B2AActionResult,
        *,
        now_monotonic_ns: int,
        guard_bundle: StorageGuardBundle | None = None,
        close_evidence: AttemptCloseEvidence | None = None,
    ) -> None:
        step = self._active_step
        before = self._before
        if step is None or before is None or self._action_started_ns is None:
            raise StorageContractError("Gate B2a action finish is out of state")
        if now_monotonic_ns < self._action_started_ns:
            raise StorageContractError("Gate B2a monotonic clock moved backwards")
        elapsed_ns = now_monotonic_ns - self._action_started_ns
        if elapsed_ns > step.timeout_seconds * 1_000_000_000:
            raise StorageContractError("Gate B2a per-action wall cap exceeded")
        self._validate_aggregate_wall(now_monotonic_ns)
        output_bytes = len(result.stdout) + len(result.stderr)
        if output_bytes > step.output_limit_bytes:
            raise StorageContractError("Gate B2a per-action output cap exceeded")
        if result.downloaded_bytes < 0 or result.downloaded_bytes > step.download_limit_bytes:
            raise StorageContractError("Gate B2a per-action download cap exceeded")
        if result.exit_code != 0:
            raise StorageContractError("Gate B2a action failed; retry is prohibited")
        if step.action_id == "seal-and-copy-b2a-evidence":
            if (
                close_evidence is not self._close_capability
                or close_evidence is None
                or not close_evidence._consumed
            ):
                raise StorageContractError(
                    "Gate B2a seal did not consume the supervisor close capability"
                )
        elif close_evidence is not None:
            raise StorageContractError("non-seal action returned close evidence")
        if step.expected_stdout is not None:
            try:
                stdout = result.stdout.decode("utf-8")
            except UnicodeDecodeError as error:
                raise StorageContractError("Gate B2a expected stdout is not UTF-8") from error
            if stdout != step.expected_stdout:
                raise StorageContractError("Gate B2a expected stdout drifted")
        result.resources_after.validate()
        internal_growth = max(
            0, before.system_free_bytes - result.resources_after.system_free_bytes
        )
        external_growth = max(
            0, before.external_free_bytes - result.resources_after.external_free_bytes
        )
        if step.internal_disk_limit_bytes is None:
            raise StorageContractError("Gate B2a per-action system disk cap is unresolved")
        if internal_growth > step.internal_disk_limit_bytes:
            raise StorageContractError("Gate B2a per-action system disk cap exceeded")
        if external_growth > step.external_disk_limit_bytes:
            raise StorageContractError("Gate B2a per-action external disk cap exceeded")
        self._output_bytes += output_bytes
        self._download_bytes += result.downloaded_bytes
        self._internal_growth_bytes += internal_growth
        self._external_growth_bytes += external_growth
        assert self.plan.system_incremental_disk_bytes is not None
        if self._output_bytes > self.plan.aggregate_output_bytes:
            raise StorageContractError("Gate B2a aggregate output cap exceeded")
        if self._download_bytes > self.plan.aggregate_download_bytes:
            raise StorageContractError("Gate B2a aggregate download cap exceeded")
        if self._internal_growth_bytes > self.plan.system_incremental_disk_bytes:
            raise StorageContractError("Gate B2a aggregate system disk cap exceeded")
        if self._external_growth_bytes > self.plan.external_incremental_disk_bytes:
            raise StorageContractError("Gate B2a aggregate external disk cap exceeded")
        self._validate_snapshot(
            result.resources_after,
            pre_action=False,
            external_mutation=False,
        )
        if step.guard_for_action is not None:
            if guard_bundle is None:
                raise StorageContractError("Gate B2a guard action produced no typed guard")
            if guard_bundle.system_floor_bytes != self.system_floor_bytes:
                raise StorageContractError("Gate B2a guard used a different system floor")
            if set(step.guard_purposes) != set(guard_bundle.tokens):
                raise StorageContractError("Gate B2a guard scope differs from the plan")
            self._pending_guard = guard_bundle
            self._pending_guard_target = step.guard_for_action
        elif guard_bundle is not None:
            raise StorageContractError("non-guard Gate B2a action returned guard evidence")
        self._index += 1
        self._active_step = None
        self._action_started_ns = None
        self._before = None
        if step.action_id == "seal-and-copy-b2a-evidence":
            self._close_capability = None

    def prepare_seal(
        self,
        *,
        source: Path,
        attempt_id: str,
        closed_at_utc: str,
        now_monotonic_ns: int,
        writer_probe: Callable[[Path], int],
    ) -> AttemptCloseEvidence:
        """Mint one in-memory, single-use close capability immediately before sealing."""

        if (
            self._started_ns is None
            or self._active_step is not None
            or self._index >= len(self.plan.steps)
            or self.plan.steps[self._index].action_id != "seal-and-copy-b2a-evidence"
            or self._pending_guard_target != "seal-and-copy-b2a-evidence"
            or self._pending_guard is None
            or self._close_capability is not None
        ):
            raise StorageContractError(
                "Gate B2a writer closure is out of state or lacks its adjacent guard"
            )
        self._validate_aggregate_wall(now_monotonic_ns)
        open_writer_count = writer_probe(source)
        if type(open_writer_count) is not int or open_writer_count != 0:
            raise StorageContractError("Gate B2a evidence source still has open writers")
        assert self.plan.document_sha256 is not None
        close_evidence = AttemptCloseEvidence(
            attempt_id=attempt_id,
            source_path=source,
            supervisor_plan_id=self.plan.plan_id,
            supervisor_plan_sha256=self.plan.document_sha256,
            authorization_reference=self.plan.authorization_reference,
            all_actions_before_seal_complete=True,
            open_writer_count=open_writer_count,
            closed_at_utc=closed_at_utc,
            _issuer=_SUPERVISOR_CLOSE_ISSUER,
        )
        close_evidence.validate(source=source, attempt_id=attempt_id)
        self._close_capability = close_evidence
        return close_evidence

    def complete(self, *, now_monotonic_ns: int) -> None:
        if (
            self._started_ns is None
            or self._active_step is not None
            or self._index != len(self.plan.steps)
            or self._pending_guard is not None
        ):
            raise StorageContractError("Gate B2a supervisor cannot seal an incomplete plan")
        self._validate_aggregate_wall(now_monotonic_ns)
        assert self.plan.aggregate_automatable_calls is not None
        if self._automatable_calls != self.plan.aggregate_automatable_calls:
            raise StorageContractError("Gate B2a automatable-call count is incomplete")

    def _validate_aggregate_wall(self, now_monotonic_ns: int) -> None:
        assert self._started_ns is not None
        if now_monotonic_ns - self._started_ns > self.plan.aggregate_wall_seconds * 1_000_000_000:
            raise StorageContractError("Gate B2a aggregate wall cap exceeded")

    def _validate_snapshot(
        self,
        resources: B2AResourceSnapshot,
        *,
        pre_action: bool,
        external_mutation: bool,
    ) -> None:
        resources.validate()
        if resources.system_free_bytes < self.system_floor_bytes:
            raise StorageContractError("Gate B2a system free-space floor failed")
        external_floor = (
            EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES
            if pre_action and external_mutation
            else EXTERNAL_RETAINED_FREE_FLOOR_BYTES
        )
        if resources.external_free_bytes < external_floor:
            raise StorageContractError("Gate B2a external free-space floor failed")
        if resources.active_attempt_bytes > self.plan.active_attempt_bytes:
            raise StorageContractError("Gate B2a active-attempt byte cap exceeded")


def verify_official_docker_metadata(
    appcast_path: Path, checksums_path: Path
) -> Mapping[str, object]:
    """Verify a bounded current metadata capture against the selected immutable DMG."""

    if appcast_path.stat().st_size > 2 * MIB or checksums_path.stat().st_size > 2 * MIB:
        raise StorageContractError("official Docker metadata exceeds its byte cap")
    appcast = appcast_path.read_bytes()
    if b"<!DOCTYPE" in appcast.upper() or b"<!ENTITY" in appcast.upper():
        raise StorageContractError("Docker appcast contains a prohibited XML declaration")
    try:
        root = ET.fromstring(appcast)
    except ET.ParseError as error:
        raise StorageContractError("Docker appcast XML is malformed") from error
    matching_items: list[ET.Element] = []
    for item in root.findall("./channel/item"):
        enclosure = item.find("./enclosure")
        if enclosure is None:
            continue
        attributes = enclosure.attrib
        version = next(
            (value for key, value in attributes.items() if key.endswith("}version")), None
        )
        short_version = next(
            (value for key, value in attributes.items() if key.endswith("}shortVersionString")),
            None,
        )
        if (
            attributes.get("url") == DOCKER_DMG_URL
            and attributes.get("length") == str(DOCKER_DMG_BYTES)
            and version == DOCKER_BUILD
            and short_version == DOCKER_PRODUCT_VERSION
        ):
            matching_items.append(item)
    if len(matching_items) != 1:
        raise StorageContractError("selected Docker enclosure did not match exactly once")
    item = matching_items[0]
    minimum = next(
        (child.text for child in item if child.tag.endswith("}minimumSystemVersion")),
        None,
    )
    if minimum != DOCKER_MINIMUM_MACOS:
        raise StorageContractError("selected Docker minimum macOS version changed")
    checksum_lines = [line.strip() for line in checksums_path.read_text().splitlines()]
    expected_checksum = f"{DOCKER_DMG_SHA256} *Docker.dmg"
    if checksum_lines != [expected_checksum]:
        raise StorageContractError("selected Docker checksum metadata changed")
    return {
        "product": "Docker Desktop",
        "version": DOCKER_PRODUCT_VERSION,
        "build": DOCKER_BUILD,
        "minimum_macos": DOCKER_MINIMUM_MACOS,
        "url": DOCKER_DMG_URL,
        "bytes": DOCKER_DMG_BYTES,
        "sha256": DOCKER_DMG_SHA256,
        "appcast_sha256": file_sha256(appcast_path),
        "checksums_sha256": file_sha256(checksums_path),
    }


def verify_docker_dmg(path: Path) -> Mapping[str, object]:
    if path.stat().st_size != DOCKER_DMG_BYTES:
        raise StorageContractError("Docker DMG byte size mismatch")
    digest = file_sha256(path)
    if digest != DOCKER_DMG_SHA256:
        raise StorageContractError("Docker DMG SHA-256 mismatch")
    return {"path": str(path), "bytes": DOCKER_DMG_BYTES, "sha256": digest}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    metadata = subparsers.add_parser("verify-official-metadata")
    metadata.add_argument("--appcast", type=Path, required=True)
    metadata.add_argument("--checksums", type=Path, required=True)
    dmg = subparsers.add_parser("verify-dmg")
    dmg.add_argument("--path", type=Path, required=True)
    plan = subparsers.add_parser("validate-plan")
    plan.add_argument("--path", type=Path, required=True)
    plan.add_argument("--sha256", required=True)
    absent = subparsers.add_parser("assert-path-absent")
    absent.add_argument("--path", type=Path, required=True)
    archive = subparsers.add_parser("seal-and-copy")
    archive.add_argument("--source", type=Path, required=True)
    archive.add_argument("--archive-parent", type=Path, required=True)
    archive.add_argument("--archive-id", required=True)
    archive.add_argument("--copy-record", type=Path, required=True)
    archive.add_argument("--max-bytes", type=int, required=True)
    archive.add_argument("--system-floor-bytes", required=True)
    guard = subparsers.add_parser("guard-storage")
    guard.add_argument("--system-floor-bytes", required=True)
    guard.add_argument("--next-action", required=True)
    guard.add_argument("--purposes", required=True)
    guard.add_argument("--require-existing", action="store_true")
    return parser


def _parse_system_floor(value: str) -> int:
    if value == "unresolved":
        raise StorageContractError("Mac mini system floor is unresolved; stop")
    try:
        floor = int(value)
    except ValueError as error:
        raise StorageContractError("Mac mini system floor is not an integer") from error
    if floor <= 0:
        raise StorageContractError("Mac mini system floor must be positive")
    return floor


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.command == "verify-official-metadata":
        evidence = verify_official_docker_metadata(arguments.appcast, arguments.checksums)
    elif arguments.command == "verify-dmg":
        evidence = verify_docker_dmg(arguments.path)
    elif arguments.command == "validate-plan":
        plan = load_b2a_plan(arguments.path, expected_sha256=arguments.sha256)
        evidence = {"plan_id": plan.plan_id, "authorized": plan.authorized}
    elif arguments.command == "assert-path-absent":
        if arguments.path.exists() or arguments.path.is_symlink():
            raise StorageContractError("path required to be absent already exists")
        evidence = {"path": str(arguments.path), "absent": True}
    elif arguments.command == "guard-storage":
        expected_scope = _B2A_GUARD_SCOPES.get(arguments.next_action)
        if expected_scope is None:
            raise StorageContractError("Gate B2a guard target is not approved")
        try:
            purposes = tuple(RootPurpose(value) for value in arguments.purposes.split(","))
        except ValueError as error:
            raise StorageContractError("Gate B2a guard purpose is not approved") from error
        if expected_scope != (purposes, arguments.require_existing):
            raise StorageContractError("Gate B2a guard scope differs from the exact plan")
        bundle = inspect_and_guard_current_storage(
            system_floor_bytes=_parse_system_floor(arguments.system_floor_bytes),
            purposes=purposes,
            require_existing=arguments.require_existing,
        )
        evidence = bundle.document() | {"next_action": arguments.next_action}
    else:
        raise StorageContractError(
            "standalone seal-and-copy is disabled until an authorized driver mints "
            "supervisor-owned writer-closure evidence"
        )
    print(json.dumps(evidence, allow_nan=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the public functions
    raise SystemExit(main())
