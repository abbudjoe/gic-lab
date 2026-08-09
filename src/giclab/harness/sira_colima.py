"""Fail-closed Colima/Lima qualification primitives for T07 Gate B1.7.

The module is deliberately incapable of installing a runtime or starting a VM on its
own.  It validates the source-lock decision, binds a sensitive action to freshly
observed volumes through held directory descriptors, and executes only caller-supplied
typed rollback operations.  Gate B1.7 tests use fakes for every command operation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TypeVar

from giclab.harness.sira_storage import (
    ACTIVE_ATTEMPT_ROOT,
    APPROVED_MOUNT,
    B2A_EVIDENCE_ROOT,
    B2A_WORK_ROOT,
    EXTERNAL_RETAINED_FREE_FLOOR_BYTES,
    SYSTEM_DATA_MOUNT,
    StorageContractError,
    VolumeObservation,
)


class ColimaContractError(StorageContractError):
    """A Colima candidate, storage guard, or rollback violates Gate B1.7."""


_LeaseResult = TypeVar("_LeaseResult")


COLIMA_PROFILE = "giclab-t07"
COLIMA_INSTANCE = "colima-giclab-t07"
COLIMA_HOME = APPROVED_MOUNT / "GIC-Lab/t07/colima-home"
COLIMA_CACHE_HOME = APPROVED_MOUNT / "GIC-Lab/t07/colima-cache"
LIMA_HOME = COLIMA_HOME / "_lima"
LIMA_PRIVATE_KEY = LIMA_HOME / "_config/user"
LIMA_SSH_SOCKET_PROBE = LIMA_HOME / COLIMA_INSTANCE / "ssh.sock.1234567890123456"
LIMA_UNIX_PATH_MAX = 104
RUNTIME_ROLLBACK_ROOT = B2A_WORK_ROOT / "colima-runtime"
ROLLBACK_EVIDENCE_ROOTS = (B2A_EVIDENCE_ROOT, ACTIVE_ATTEMPT_ROOT)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SHA512 = re.compile(r"^[a-f0-9]{128}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_PLAN_ID = re.compile(r"^PLAN-[A-Z0-9][A-Z0-9._-]{2,127}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_HELD_STORAGE_LEASE_ISSUER = object()
_ROLLBACK_OWNERSHIP_RECEIPT_ISSUER = object()


def _rollback_mutable_exact_paths() -> tuple[Path, ...]:
    """Return dedicated roots that an exclusive create may make rollback-owned."""

    return (RUNTIME_ROLLBACK_ROOT, COLIMA_CACHE_HOME)


class RuntimeDecisionState(StrEnum):
    READY = "ready-for-B2a-authorization"
    REJECTED = "runtime-candidate-rejected"


@dataclass(frozen=True, slots=True)
class RuntimeArtifact:
    component: str
    version: str
    source_tag: str
    source_commit: str
    asset_url: str
    byte_size: int | None
    sha256: str | None
    sha512: str | None
    license: str
    macos_arm64_compatible: bool
    minimum_macos: str | None
    transitive_requirements: tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> RuntimeArtifact:
        expected = {
            "component",
            "version",
            "source_tag",
            "source_commit",
            "asset_url",
            "byte_size",
            "sha256",
            "sha512",
            "license",
            "macos_arm64_compatible",
            "minimum_macos",
            "transitive_requirements",
        }
        if set(raw) != expected:
            raise ColimaContractError("runtime artifact fields differ from the locked schema")
        requirements = raw["transitive_requirements"]
        if not isinstance(requirements, list) or any(
            not isinstance(value, str) or not value for value in requirements
        ):
            raise ColimaContractError("runtime artifact requirements must be exact strings")
        byte_size = raw["byte_size"]
        if byte_size is not None and (
            not isinstance(byte_size, int) or isinstance(byte_size, bool) or byte_size <= 0
        ):
            raise ColimaContractError("runtime artifact byte size must be positive or null")
        sha256 = raw["sha256"]
        sha512 = raw["sha512"]
        if sha256 is not None and (
            not isinstance(sha256, str) or _SHA256.fullmatch(sha256) is None
        ):
            raise ColimaContractError("runtime artifact SHA-256 is malformed")
        if sha512 is not None and (
            not isinstance(sha512, str) or _SHA512.fullmatch(sha512) is None
        ):
            raise ColimaContractError("runtime artifact SHA-512 is malformed")
        strings: dict[str, str] = {}
        for name in ("component", "version", "source_tag", "source_commit", "asset_url", "license"):
            value = raw[name]
            if not isinstance(value, str) or not value:
                raise ColimaContractError(f"runtime artifact {name} must be a nonempty string")
            strings[name] = value
        if _COMMIT.fullmatch(strings["source_commit"]) is None:
            raise ColimaContractError("runtime artifact source commit is not immutable")
        compatible = raw["macos_arm64_compatible"]
        if not isinstance(compatible, bool):
            raise ColimaContractError("runtime artifact compatibility must be boolean")
        minimum = raw["minimum_macos"]
        if minimum is not None and (not isinstance(minimum, str) or not minimum):
            raise ColimaContractError("runtime artifact minimum macOS is malformed")
        return cls(
            component=strings["component"],
            version=strings["version"],
            source_tag=strings["source_tag"],
            source_commit=strings["source_commit"],
            asset_url=strings["asset_url"],
            byte_size=byte_size,
            sha256=sha256,
            sha512=sha512,
            license=strings["license"],
            macos_arm64_compatible=compatible,
            minimum_macos=minimum,
            transitive_requirements=tuple(requirements),
        )

    def is_immutable_and_bounded(self) -> bool:
        return (
            self.byte_size is not None and self.sha256 is not None and self.macos_arm64_compatible
        )


@dataclass(frozen=True, slots=True)
class ColimaCandidateDecision:
    schema_version: str
    candidate_id: str
    state: RuntimeDecisionState
    profile: str
    colima_home: Path
    colima_cache_home: Path
    lima_home: Path
    external_owners_enabled: bool
    external_retained_floor_bytes: int
    system_floor_bytes: int | None
    selected_install_method: str | None
    configuration: Mapping[str, object]
    artifacts: tuple[RuntimeArtifact, ...]
    blockers: tuple[str, ...]
    executable_plan_id: str | None
    executable_plan_path: Path | None
    executable_plan_sha256: str | None
    document_sha256: str

    def validate(self) -> None:
        if self.schema_version != "0.1.0" or _SAFE_ID.fullmatch(self.candidate_id) is None:
            raise ColimaContractError("Colima decision identity is malformed")
        if self.profile != COLIMA_PROFILE:
            raise ColimaContractError("Colima profile differs from the reviewed candidate")
        if (
            self.colima_home != COLIMA_HOME
            or self.colima_cache_home != COLIMA_CACHE_HOME
            or self.lima_home != LIMA_HOME
        ):
            raise ColimaContractError("Colima/Lima state roots differ from the reviewed topology")
        if self.external_retained_floor_bytes != EXTERNAL_RETAINED_FREE_FLOOR_BYTES:
            raise ColimaContractError("external retained-free floor drifted")
        expected_configuration = {
            "runtime": "docker",
            "vm_type": "vz",
            "arch": "host",
            "resolved_arch": "arm64",
            "kubernetes": False,
            "network_address": False,
            "port_forwarder": "none",
            "auto_activate": False,
            "ssh_config": False,
            "template": False,
            "mounts": "none",
            "binfmt": False,
            "rosetta": False,
            "force_disk_image": False,
            "cpu": 2,
            "memory_gib": self.configuration.get("memory_gib"),
            "disk_gib": self.configuration.get("disk_gib"),
        }
        if dict(self.configuration) != expected_configuration:
            raise ColimaContractError("Colima candidate configuration drifted")
        for name in ("memory_gib", "disk_gib"):
            value = self.configuration[name]
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value <= 0
            ):
                raise ColimaContractError(f"Colima {name} must be positive or null")
        if not self.artifacts or len({artifact.component for artifact in self.artifacts}) != len(
            self.artifacts
        ):
            raise ColimaContractError("runtime artifacts must be nonempty and component-unique")
        private_key_blocker = "LIMA_PRIVATE_KEY_ON_NOOWNERS_EXTERNAL_VOLUME"
        if not self.external_owners_enabled and private_key_blocker not in self.blockers:
            raise ColimaContractError("noowners topology omits the mandatory Lima-key blocker")
        if len(os.fsencode(LIMA_SSH_SOCKET_PROBE)) >= LIMA_UNIX_PATH_MAX:
            socket_blocker = "LIMA_UNIX_SOCKET_PATH_TOO_LONG"
            if socket_blocker not in self.blockers:
                raise ColimaContractError("overlong Lima socket path is not represented")
        if self.state is RuntimeDecisionState.READY:
            if self.blockers:
                raise ColimaContractError("ready Colima decision still contains blockers")
            if self.external_owners_enabled is not True:
                raise ColimaContractError("ready Colima decision lacks authoritative ownership")
            if self.system_floor_bytes is None or self.system_floor_bytes <= 0:
                raise ColimaContractError("ready Colima decision lacks a numeric system floor")
            if not self.selected_install_method:
                raise ColimaContractError("ready Colima decision lacks an install method")
            if any(self.configuration[name] is None for name in ("memory_gib", "disk_gib")):
                raise ColimaContractError("ready Colima decision lacks numeric VM resources")
            if not all(artifact.is_immutable_and_bounded() for artifact in self.artifacts):
                raise ColimaContractError("ready Colima decision has unresolved artifacts")
            if (
                self.executable_plan_id is None
                or _PLAN_ID.fullmatch(self.executable_plan_id) is None
                or self.executable_plan_path is None
                or self.executable_plan_sha256 is None
                or _SHA256.fullmatch(self.executable_plan_sha256) is None
            ):
                raise ColimaContractError("ready Colima decision lacks an immutable plan")
        else:
            if not self.blockers:
                raise ColimaContractError("rejected Colima decision must name material blockers")
            if any(
                value is not None
                for value in (
                    self.executable_plan_id,
                    self.executable_plan_path,
                    self.executable_plan_sha256,
                )
            ):
                raise ColimaContractError("rejected Colima decision must not expose a plan")
        if _SHA256.fullmatch(self.document_sha256) is None:
            raise ColimaContractError("Colima decision document SHA-256 is malformed")


def _nullable_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ColimaContractError(f"{label} must be a nonempty string or null")
    return value


def load_colima_candidate_decision(path: Path, *, expected_sha256: str) -> ColimaCandidateDecision:
    """Load and semantically validate a non-executable candidate decision."""

    encoded = path.read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    if digest != expected_sha256:
        raise ColimaContractError("Colima candidate decision SHA-256 mismatch")
    try:
        raw = json.loads(encoded)
    except json.JSONDecodeError as error:
        raise ColimaContractError("Colima candidate decision is not valid JSON") from error
    if not isinstance(raw, dict):
        raise ColimaContractError("Colima candidate decision must be an object")
    expected = {
        "schema_version",
        "candidate_id",
        "decision_state",
        "profile",
        "colima_home",
        "colima_cache_home",
        "lima_home",
        "external_owners_enabled",
        "external_retained_floor_bytes",
        "system_floor_bytes",
        "selected_install_method",
        "configuration",
        "artifacts",
        "blockers",
        "executable_plan",
    }
    if set(raw) != expected:
        raise ColimaContractError("Colima candidate decision fields differ from the schema")
    artifacts_raw = raw["artifacts"]
    blockers_raw = raw["blockers"]
    configuration_raw = raw["configuration"]
    if not isinstance(artifacts_raw, list) or any(
        not isinstance(value, dict) for value in artifacts_raw
    ):
        raise ColimaContractError("Colima artifacts must be objects")
    if not isinstance(blockers_raw, list) or any(
        not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None for value in blockers_raw
    ):
        raise ColimaContractError("Colima blockers must be stable identifiers")
    if not isinstance(configuration_raw, dict):
        raise ColimaContractError("Colima configuration must be an object")
    executable = raw["executable_plan"]
    plan_id: str | None = None
    plan_path: Path | None = None
    plan_sha256: str | None = None
    if executable is not None:
        if not isinstance(executable, dict) or set(executable) != {"plan_id", "path", "sha256"}:
            raise ColimaContractError("Colima executable plan binding is malformed")
        plan_id = _nullable_string(executable["plan_id"], "Colima plan ID")
        plan_path_raw = _nullable_string(executable["path"], "Colima plan path")
        plan_path = Path(plan_path_raw) if plan_path_raw is not None else None
        plan_sha256 = _nullable_string(executable["sha256"], "Colima plan SHA-256")
    system_floor = raw["system_floor_bytes"]
    if system_floor is not None and (
        not isinstance(system_floor, int) or isinstance(system_floor, bool) or system_floor <= 0
    ):
        raise ColimaContractError("system floor must be positive or null")
    external_floor = raw["external_retained_floor_bytes"]
    if not isinstance(external_floor, int) or isinstance(external_floor, bool):
        raise ColimaContractError("external floor must be an integer")
    owners = raw["external_owners_enabled"]
    if not isinstance(owners, bool):
        raise ColimaContractError("external ownership state must be boolean")
    try:
        state = RuntimeDecisionState(raw["decision_state"])
    except (TypeError, ValueError) as error:
        raise ColimaContractError("Colima decision state is invalid") from error
    strings: dict[str, str] = {}
    for name in (
        "schema_version",
        "candidate_id",
        "profile",
        "colima_home",
        "colima_cache_home",
        "lima_home",
    ):
        value = raw[name]
        if not isinstance(value, str) or not value:
            raise ColimaContractError(f"Colima {name} must be a nonempty string")
        strings[name] = value
    decision = ColimaCandidateDecision(
        schema_version=strings["schema_version"],
        candidate_id=strings["candidate_id"],
        state=state,
        profile=strings["profile"],
        colima_home=Path(strings["colima_home"]),
        colima_cache_home=Path(strings["colima_cache_home"]),
        lima_home=Path(strings["lima_home"]),
        external_owners_enabled=owners,
        external_retained_floor_bytes=external_floor,
        system_floor_bytes=system_floor,
        selected_install_method=_nullable_string(
            raw["selected_install_method"], "selected install method"
        ),
        configuration=configuration_raw,
        artifacts=tuple(RuntimeArtifact.from_mapping(value) for value in artifacts_raw),
        blockers=tuple(blockers_raw),
        executable_plan_id=plan_id,
        executable_plan_path=plan_path,
        executable_plan_sha256=plan_sha256,
        document_sha256=digest,
    )
    decision.validate()
    return decision


def _open_directory_no_follow(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise ColimaContractError("held mount path must be absolute and traversal-free")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open("/", flags)
    try:
        for component in path.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


@dataclass(slots=True)
class HeldDirectoryIdentity:
    """A no-follow directory identity held across exactly one sensitive action."""

    path: Path
    descriptor: int
    device: int
    inode: int
    closed: bool = False

    @classmethod
    def open(cls, path: Path) -> HeldDirectoryIdentity:
        descriptor = _open_directory_no_follow(path)
        observed = os.fstat(descriptor)
        if not stat.S_ISDIR(observed.st_mode):
            os.close(descriptor)
            raise ColimaContractError("held identity is not a directory")
        linked = path.stat(follow_symlinks=False)
        if (observed.st_dev, observed.st_ino) != (linked.st_dev, linked.st_ino):
            os.close(descriptor)
            raise ColimaContractError("held directory differs from its path identity")
        return cls(path, descriptor, observed.st_dev, observed.st_ino)

    def revalidate(self) -> None:
        if self.closed:
            raise ColimaContractError("held directory identity is closed")
        observed = os.fstat(self.descriptor)
        linked = self.path.stat(follow_symlinks=False)
        expected = (self.device, self.inode)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or not stat.S_ISDIR(linked.st_mode)
            or (observed.st_dev, observed.st_ino) != expected
            or (linked.st_dev, linked.st_ino) != expected
        ):
            raise ColimaContractError("held mount identity changed during guarded action")

    def close(self) -> None:
        if not self.closed:
            os.close(self.descriptor)
            self.closed = True


VolumePairObserver = Callable[[], tuple[VolumeObservation, VolumeObservation]]


def _same_volume_identity(first: VolumeObservation, second: VolumeObservation) -> bool:
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
class HeldStorageActionLease:
    """Consumed guard whose descriptors remain open until post-action verification."""

    action_id: str
    external_at_issue: VolumeObservation
    system_at_issue: VolumeObservation
    external_handle: HeldDirectoryIdentity
    system_handle: HeldDirectoryIdentity
    bound_handles: tuple[HeldDirectoryIdentity, ...]
    system_floor_bytes: int
    issued_monotonic_ns: int
    consumed_monotonic_ns: int
    maximum_age_ns: int
    maximum_run_delay_ns: int
    _issuer: object = field(repr=False)
    finished: bool = False
    pre_action_verified: bool = False
    post_action_verified: bool = False

    def validate_binding(self, *, action_id: str, exact_paths: tuple[Path, ...]) -> None:
        if self._issuer is not _HELD_STORAGE_LEASE_ISSUER:
            raise ColimaContractError("held storage lease issuer is not trusted")
        if self.finished:
            raise ColimaContractError("held storage action lease was already used")
        if self.action_id != action_id:
            raise ColimaContractError("held storage lease is bound to another action")
        if tuple(handle.path for handle in self.bound_handles) != exact_paths:
            raise ColimaContractError("held storage lease paths differ from the sensitive action")

    def _verify_post_action(self, fresh_observer: VolumePairObserver) -> None:
        external, system = fresh_observer()
        if not _same_volume_identity(self.external_at_issue, external) or not _same_volume_identity(
            self.system_at_issue, system
        ):
            raise ColimaContractError("storage identity drifted during sensitive action")
        external.validate_external(reserve_incremental=True)
        system.validate_system_floor(self.system_floor_bytes)
        self.external_handle.revalidate()
        self.system_handle.revalidate()
        for handle in self.bound_handles:
            handle.revalidate()
        self.post_action_verified = True

    def _verify_pre_action(
        self,
        fresh_observer: VolumePairObserver,
        *,
        now_monotonic_ns: int,
    ) -> None:
        if (
            now_monotonic_ns < self.consumed_monotonic_ns
            or now_monotonic_ns - self.consumed_monotonic_ns > self.maximum_run_delay_ns
            or now_monotonic_ns - self.issued_monotonic_ns > self.maximum_age_ns
        ):
            raise ColimaContractError("held storage action lease is stale before execution")
        external, system = fresh_observer()
        if not _same_volume_identity(self.external_at_issue, external) or not _same_volume_identity(
            self.system_at_issue, system
        ):
            raise ColimaContractError("storage identity drifted before sensitive action")
        external.validate_external(reserve_incremental=True)
        system.validate_system_floor(self.system_floor_bytes)
        self.external_handle.revalidate()
        self.system_handle.revalidate()
        for handle in self.bound_handles:
            handle.revalidate()
        self.pre_action_verified = True

    def _close_handles(self) -> None:
        for handle in self.bound_handles:
            handle.close()
        self.external_handle.close()
        self.system_handle.close()

    def run(
        self,
        operation: Callable[[], _LeaseResult],
        *,
        fresh_observer: VolumePairObserver,
        now_monotonic_ns: int | None = None,
    ) -> _LeaseResult:
        if self.finished:
            raise ColimaContractError("held storage action lease was already used")
        if self._issuer is not _HELD_STORAGE_LEASE_ISSUER:
            raise ColimaContractError("held storage lease issuer is not trusted")
        self.finished = True
        try:
            current = time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
            self._verify_pre_action(fresh_observer, now_monotonic_ns=current)
            try:
                result = operation()
            except BaseException:
                self._verify_post_action(fresh_observer)
                raise
            self._verify_post_action(fresh_observer)
            return result
        finally:
            self._close_handles()


@dataclass(slots=True)
class HeldStorageActionGuard:
    """Single-use, time-bounded, fresh-observation storage guard."""

    action_id: str
    external_at_issue: VolumeObservation
    system_at_issue: VolumeObservation
    external_handle: HeldDirectoryIdentity | None
    system_handle: HeldDirectoryIdentity | None
    bound_handles: tuple[HeldDirectoryIdentity, ...]
    system_floor_bytes: int
    issued_monotonic_ns: int
    maximum_age_ns: int = 5_000_000_000
    maximum_run_delay_ns: int = 1_000_000_000
    consumed: bool = False
    closed: bool = False

    def consume(
        self,
        *,
        fresh_observer: VolumePairObserver,
        now_monotonic_ns: int | None = None,
    ) -> HeldStorageActionLease:
        try:
            if self.consumed or self.closed:
                raise ColimaContractError("held storage action guard was already consumed")
            if self.external_handle is None or self.system_handle is None:
                raise ColimaContractError("held storage action guard lost its descriptors")
            current = time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
            if (
                current < self.issued_monotonic_ns
                or current - self.issued_monotonic_ns > self.maximum_age_ns
            ):
                raise ColimaContractError("held storage action guard is stale")
            external, system = fresh_observer()
            if not _same_volume_identity(
                self.external_at_issue, external
            ) or not _same_volume_identity(self.system_at_issue, system):
                raise ColimaContractError("storage identity changed before sensitive action")
            external.validate_external(reserve_incremental=True)
            system.validate_system_floor(self.system_floor_bytes)
            self.external_handle.revalidate()
            self.system_handle.revalidate()
            for handle in self.bound_handles:
                handle.revalidate()
            self.consumed = True
            lease = HeldStorageActionLease(
                action_id=self.action_id,
                external_at_issue=external,
                system_at_issue=system,
                external_handle=self.external_handle,
                system_handle=self.system_handle,
                bound_handles=self.bound_handles,
                system_floor_bytes=self.system_floor_bytes,
                issued_monotonic_ns=self.issued_monotonic_ns,
                consumed_monotonic_ns=current,
                maximum_age_ns=self.maximum_age_ns,
                maximum_run_delay_ns=self.maximum_run_delay_ns,
                _issuer=_HELD_STORAGE_LEASE_ISSUER,
            )
            self.external_handle = None
            self.system_handle = None
            self.bound_handles = ()
            return lease
        except Exception:
            for handle in self.bound_handles:
                handle.close()
            if self.external_handle is not None:
                self.external_handle.close()
            if self.system_handle is not None:
                self.system_handle.close()
            self.closed = True
            raise

    def close_without_consuming(self) -> None:
        if self.consumed:
            raise ColimaContractError("consumed guard no longer owns the lease descriptors")
        if self.closed:
            return
        for handle in self.bound_handles:
            handle.close()
        if self.external_handle is not None:
            self.external_handle.close()
        if self.system_handle is not None:
            self.system_handle.close()
        self.closed = True


def issue_held_storage_action_guard(
    action_id: str,
    *,
    fresh_observer: VolumePairObserver,
    system_floor_bytes: int,
    held_paths: tuple[Path, ...] = (),
    issued_monotonic_ns: int | None = None,
) -> HeldStorageActionGuard:
    """Observe both volumes, open exact mount descriptors, and mint one guard."""

    if _SAFE_ID.fullmatch(action_id) is None:
        raise ColimaContractError("guard action identity is malformed")
    external, system = fresh_observer()
    external.validate_external(reserve_incremental=True)
    system.validate_system_floor(system_floor_bytes)
    external_handle = HeldDirectoryIdentity.open(APPROVED_MOUNT)
    try:
        system_handle = HeldDirectoryIdentity.open(SYSTEM_DATA_MOUNT)
    except Exception:
        external_handle.close()
        raise
    bound_handles: list[HeldDirectoryIdentity] = []
    try:
        if len(set(held_paths)) != len(held_paths):
            raise ColimaContractError("held storage paths must be unique")
        for path in held_paths:
            bound_handles.append(HeldDirectoryIdentity.open(path))
    except Exception:
        for handle in bound_handles:
            handle.close()
        external_handle.close()
        system_handle.close()
        raise
    issued = time.monotonic_ns() if issued_monotonic_ns is None else issued_monotonic_ns
    if issued <= 0:
        for handle in bound_handles:
            handle.close()
        external_handle.close()
        system_handle.close()
        raise ColimaContractError("guard timestamp must be positive")
    return HeldStorageActionGuard(
        action_id=action_id,
        external_at_issue=external,
        system_at_issue=system,
        external_handle=external_handle,
        system_handle=system_handle,
        bound_handles=tuple(bound_handles),
        system_floor_bytes=system_floor_bytes,
        issued_monotonic_ns=issued,
    )


class RollbackTrigger(StrEnum):
    PARTIAL_BINARY_INSTALL = "partial-binary-install"
    FAILED_VM_CREATION = "failed-vm-creation"
    FAILED_RUNTIME_STARTUP = "failed-runtime-startup"
    EXTERNAL_VOLUME_MISSING = "external-volume-missing"
    WRONG_REMOUNT_IDENTITY = "wrong-remount-identity"
    PROFILE_STATE_DRIFT = "profile-state-drift"
    RESIDUAL_RUNTIME_RESOURCE = "residual-runtime-resource"
    EVIDENCE_COPY_FAILURE = "evidence-copy-failure"


class RollbackOperation(StrEnum):
    STOP_COLIMA_PROFILE = "stop-colima-profile"
    REMOVE_OWNED_PATH = "remove-fresh-owned-path"
    PRESERVE_EVIDENCE = "preserve-evidence"


class RollbackResourceKind(StrEnum):
    COLIMA_PROFILE = "colima-profile"
    OWNED_PATH = "owned-path"
    EVIDENCE_PATH = "evidence-path"


def _strict_child_of_any(path: Path, roots: tuple[Path, ...]) -> bool:
    if not path.is_absolute() or ".." in path.parts:
        return False
    return any(path != root and path.is_relative_to(root) for root in roots)


@dataclass(frozen=True, slots=True)
class RollbackOwnershipReceipt:
    """Issuer-bound ownership/protection evidence accepted by rollback."""

    resource_id: str
    attempt_id: str
    kind: RollbackResourceKind
    path: Path
    observed_device: int
    observed_inode: int
    freshly_owned: bool
    runtime_identity: str | None = None
    executable_path: Path | None = None
    executable_sha256: str | None = None
    _issuer: object | None = field(default=None, repr=False, compare=False)

    def validate(self, *, plan_attempt_id: str) -> None:
        if (
            _SAFE_ID.fullmatch(self.resource_id) is None
            or _SAFE_ID.fullmatch(self.attempt_id) is None
            or self.attempt_id != plan_attempt_id
        ):
            raise ColimaContractError("rollback ownership receipt identity is malformed")
        if self._issuer is not _ROLLBACK_OWNERSHIP_RECEIPT_ISSUER:
            raise ColimaContractError("rollback ownership receipt issuer is not trusted")
        if self.observed_device <= 0 or self.observed_inode <= 0:
            raise ColimaContractError("rollback ownership receipt lacks device/inode identity")
        if self.kind is RollbackResourceKind.COLIMA_PROFILE:
            if (
                self.path != COLIMA_HOME
                or self.runtime_identity != COLIMA_PROFILE
                or not self.freshly_owned
                or self.executable_path is None
                or self.executable_path.name != "colima"
                or not _strict_child_of_any(self.executable_path, (RUNTIME_ROLLBACK_ROOT,))
                or self.executable_sha256 is None
                or _SHA256.fullmatch(self.executable_sha256) is None
            ):
                raise ColimaContractError("Colima rollback receipt differs from the exact profile")
        elif self.kind is RollbackResourceKind.OWNED_PATH:
            if (
                not self.freshly_owned
                or self.path not in _rollback_mutable_exact_paths()
                or self.runtime_identity is not None
                or self.executable_path is not None
                or self.executable_sha256 is not None
            ):
                raise ColimaContractError("rollback path is not one exact fresh owned root")
        elif (
            self.freshly_owned
            or not _strict_child_of_any(self.path, ROLLBACK_EVIDENCE_ROOTS)
            or self.runtime_identity is not None
            or self.executable_path is not None
            or self.executable_sha256 is not None
        ):
            raise ColimaContractError("rollback evidence receipt is outside protected roots")

    def verify_current_identity(self) -> None:
        try:
            observed = self.path.lstat()
        except OSError as error:
            raise ColimaContractError("rollback resource identity is no longer present") from error
        if (
            stat.S_ISLNK(observed.st_mode)
            or observed.st_dev != self.observed_device
            or observed.st_ino != self.observed_inode
        ):
            raise ColimaContractError("rollback resource identity is stale or unsafe")
        if self.kind is RollbackResourceKind.COLIMA_PROFILE:
            assert self.executable_path is not None
            assert self.executable_sha256 is not None
            try:
                digest = _regular_file_sha256_no_follow(self.executable_path)
            except OSError as error:
                raise ColimaContractError("rollback executable identity is unavailable") from error
            if digest != self.executable_sha256:
                raise ColimaContractError("rollback executable SHA-256 drifted")


def _regular_file_sha256_no_follow(path: Path) -> str:
    if not path.is_absolute() or ".." in path.parts:
        raise ColimaContractError("rollback executable path is unsafe")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise ColimaContractError("rollback executable is not one regular file")
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def create_fresh_rollback_directory_receipt(
    *,
    resource_id: str,
    attempt_id: str,
    kind: RollbackResourceKind,
    path: Path,
    executable_path: Path | None = None,
) -> RollbackOwnershipReceipt:
    """Exclusively create one allowlisted directory and mint its rollback capability."""

    if kind is RollbackResourceKind.COLIMA_PROFILE:
        if path != COLIMA_HOME or executable_path is None:
            raise ColimaContractError("fresh profile receipt differs from the exact candidate")
        if not _strict_child_of_any(executable_path, (RUNTIME_ROLLBACK_ROOT,)):
            raise ColimaContractError("fresh profile executable escaped the runtime root")
        executable_sha256 = _regular_file_sha256_no_follow(executable_path)
        runtime_identity: str | None = COLIMA_PROFILE
    elif kind is RollbackResourceKind.OWNED_PATH:
        if path not in _rollback_mutable_exact_paths() or executable_path is not None:
            raise ColimaContractError("fresh rollback directory is not an exact mutable root")
        executable_sha256 = None
        runtime_identity = None
    else:
        raise ColimaContractError("evidence paths cannot be minted as fresh-owned directories")
    if not path.is_absolute() or ".." in path.parts or not path.name:
        raise ColimaContractError("fresh rollback directory path is unsafe")
    parent = HeldDirectoryIdentity.open(path.parent)
    descriptor = -1
    try:
        try:
            os.mkdir(path.name, mode=0o700, dir_fd=parent.descriptor)
        except FileExistsError as error:
            raise ColimaContractError("fresh rollback directory already exists") from error
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path.name, flags, dir_fd=parent.descriptor)
        observed = os.fstat(descriptor)
        linked = path.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or not stat.S_ISDIR(linked.st_mode)
            or (observed.st_dev, observed.st_ino) != (linked.st_dev, linked.st_ino)
        ):
            raise ColimaContractError("fresh rollback directory identity is unsafe")
        receipt = RollbackOwnershipReceipt(
            resource_id=resource_id,
            attempt_id=attempt_id,
            kind=kind,
            path=path,
            observed_device=observed.st_dev,
            observed_inode=observed.st_ino,
            freshly_owned=True,
            runtime_identity=runtime_identity,
            executable_path=executable_path,
            executable_sha256=executable_sha256,
            _issuer=_ROLLBACK_OWNERSHIP_RECEIPT_ISSUER,
        )
        receipt.validate(plan_attempt_id=attempt_id)
        return receipt
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        parent.close()


def issue_existing_rollback_evidence_receipt(
    *,
    resource_id: str,
    attempt_id: str,
    path: Path,
) -> RollbackOwnershipReceipt:
    """Bind a preserve-only receipt to one existing evidence identity."""

    if not _strict_child_of_any(path, ROLLBACK_EVIDENCE_ROOTS):
        raise ColimaContractError("rollback evidence path is outside protected roots")
    try:
        observed = path.lstat()
    except OSError as error:
        raise ColimaContractError("rollback evidence identity is unavailable") from error
    if stat.S_ISLNK(observed.st_mode):
        raise ColimaContractError("rollback evidence identity is a symlink")
    receipt = RollbackOwnershipReceipt(
        resource_id=resource_id,
        attempt_id=attempt_id,
        kind=RollbackResourceKind.EVIDENCE_PATH,
        path=path,
        observed_device=observed.st_dev,
        observed_inode=observed.st_ino,
        freshly_owned=False,
        _issuer=_ROLLBACK_OWNERSHIP_RECEIPT_ISSUER,
    )
    receipt.validate(plan_attempt_id=attempt_id)
    return receipt


@dataclass(frozen=True, slots=True)
class RollbackAction:
    action_id: str
    operation: RollbackOperation
    resource_id: str
    argv: tuple[str, ...] | None
    path: Path | None
    timeout_seconds: int
    output_limit_bytes: int

    def validate(self) -> None:
        if (
            _SAFE_ID.fullmatch(self.action_id) is None
            or _SAFE_ID.fullmatch(self.resource_id) is None
        ):
            raise ColimaContractError("rollback action/resource identity is malformed")
        if self.timeout_seconds <= 0 or self.output_limit_bytes <= 0:
            raise ColimaContractError("rollback action limits must be finite and positive")
        if self.operation is RollbackOperation.STOP_COLIMA_PROFILE:
            if self.path is not None or not self.argv:
                raise ColimaContractError("rollback command must be an argv array only")
            if not Path(self.argv[0]).is_absolute() or any(
                not value or "\x00" in value for value in self.argv
            ):
                raise ColimaContractError("rollback command argv is unsafe")
        elif self.argv is not None or self.path is None or not self.path.is_absolute():
            raise ColimaContractError("rollback path action is malformed")


@dataclass(frozen=True, slots=True)
class RollbackPlan:
    plan_id: str
    attempt_id: str
    trigger: RollbackTrigger
    ownership_receipts: tuple[RollbackOwnershipReceipt, ...]
    actions: tuple[RollbackAction, ...]

    def validate(self) -> None:
        if _PLAN_ID.fullmatch(self.plan_id) is None or _SAFE_ID.fullmatch(self.attempt_id) is None:
            raise ColimaContractError("rollback plan identity is malformed")
        if not self.actions or len({action.action_id for action in self.actions}) != len(
            self.actions
        ):
            raise ColimaContractError("rollback actions must be nonempty and unique")
        receipts = {receipt.resource_id: receipt for receipt in self.ownership_receipts}
        if not receipts or len(receipts) != len(self.ownership_receipts):
            raise ColimaContractError("rollback ownership receipts must be nonempty and unique")
        for receipt in receipts.values():
            receipt.validate(plan_attempt_id=self.attempt_id)
        for action in self.actions:
            action.validate()
            if action.resource_id not in receipts:
                raise ColimaContractError("rollback action is not bound to an owned resource")
            receipt = receipts[action.resource_id]
            if action.operation is RollbackOperation.STOP_COLIMA_PROFILE:
                expected = (
                    str(receipt.executable_path),
                    "--profile",
                    str(receipt.runtime_identity),
                    "stop",
                    "--force",
                )
                if (
                    receipt.kind is not RollbackResourceKind.COLIMA_PROFILE
                    or action.argv != expected
                ):
                    raise ColimaContractError(
                        "rollback command differs from its allowlisted template"
                    )
            elif action.operation is RollbackOperation.REMOVE_OWNED_PATH:
                if (
                    receipt.kind is not RollbackResourceKind.OWNED_PATH
                    or action.path != receipt.path
                ):
                    raise ColimaContractError("rollback removal lacks a fresh owned-path receipt")
            elif (
                receipt.kind is not RollbackResourceKind.EVIDENCE_PATH
                or action.path != receipt.path
            ):
                raise ColimaContractError("preserve action lacks a protected evidence receipt")

    def receipt_for(self, resource_id: str) -> RollbackOwnershipReceipt:
        return next(
            receipt for receipt in self.ownership_receipts if receipt.resource_id == resource_id
        )


@dataclass(frozen=True, slots=True)
class RollbackCommandResult:
    exit_code: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True, slots=True)
class RollbackActionEvidence:
    action_id: str
    operation: RollbackOperation
    outcome: str
    exit_code: int | None
    output_bytes: int


@dataclass(frozen=True, slots=True)
class RollbackEvidence:
    schema_version: str
    plan_id: str
    attempt_id: str
    trigger: RollbackTrigger
    actions: tuple[RollbackActionEvidence, ...]
    complete: bool
    automatic_retries: int = 0

    def document(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "attempt_id": self.attempt_id,
            "trigger": self.trigger.value,
            "actions": [
                {
                    "action_id": action.action_id,
                    "operation": action.operation.value,
                    "outcome": action.outcome,
                    "exit_code": action.exit_code,
                    "output_bytes": action.output_bytes,
                }
                for action in self.actions
            ],
            "complete": self.complete,
            "automatic_retries": self.automatic_retries,
        }


CommandRollbackRunner = Callable[[RollbackAction], RollbackCommandResult]
PathRollbackRunner = Callable[[RollbackAction], None]


@dataclass(slots=True)
class TypedRollbackExecutor:
    """Execute an exact typed rollback plan once, stopping at the first failure."""

    plan: RollbackPlan
    command_runner: CommandRollbackRunner
    path_runner: PathRollbackRunner
    _used: bool = field(default=False, init=False)

    def execute(self) -> RollbackEvidence:
        if self._used:
            raise ColimaContractError("rollback plan was already executed")
        self.plan.validate()
        self._used = True
        evidence: list[RollbackActionEvidence] = []
        complete = True
        for action in self.plan.actions:
            try:
                receipt = self.plan.receipt_for(action.resource_id)
                receipt.verify_current_identity()
                if action.operation is RollbackOperation.STOP_COLIMA_PROFILE:
                    result = self.command_runner(action)
                    output_bytes = len(result.stdout) + len(result.stderr)
                    if output_bytes > action.output_limit_bytes:
                        raise ColimaContractError("rollback command output cap exceeded")
                    if result.exit_code != 0:
                        evidence.append(
                            RollbackActionEvidence(
                                action.action_id,
                                action.operation,
                                "failed",
                                result.exit_code,
                                output_bytes,
                            )
                        )
                        complete = False
                        break
                    evidence.append(
                        RollbackActionEvidence(
                            action.action_id,
                            action.operation,
                            "succeeded",
                            0,
                            output_bytes,
                        )
                    )
                else:
                    self.path_runner(action)
                    evidence.append(
                        RollbackActionEvidence(
                            action.action_id,
                            action.operation,
                            "succeeded",
                            None,
                            0,
                        )
                    )
            except Exception:
                evidence.append(
                    RollbackActionEvidence(
                        action.action_id,
                        action.operation,
                        "failed",
                        None,
                        0,
                    )
                )
                complete = False
                break
        return RollbackEvidence(
            schema_version="0.1.0",
            plan_id=self.plan.plan_id,
            attempt_id=self.plan.attempt_id,
            trigger=self.plan.trigger,
            actions=tuple(evidence),
            complete=complete and len(evidence) == len(self.plan.actions),
        )
