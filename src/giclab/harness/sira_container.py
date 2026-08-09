"""Kernel-containment control plane for future T07 SiRA attempts.

Gate B1 only constructs and validates an OCI-container control plane.  The module
contains no provider client and does not pull, build, or launch an image on import.
Runtime operations require an explicitly supplied command runner; tests use a fake.
The container ID, not host PID discovery, is the authoritative attempt handle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Protocol

from .safety import ExactCredentialScrubber, assert_no_secret_literals, looks_secret_name
from .sira_gate_a import SIRA_UPSTREAM_COMMIT, file_sha256

CONTAINER_SCHEMA_VERSION = "0.1.0"
CONTAINER_LABEL_PREFIX = "org.giclab.t07"
CONTAINER_SECRET_TARGET = PurePosixPath("/run/secrets/sira_api_key")
CONTAINER_ATTEMPT_TARGET = PurePosixPath("/giclab/attempt")
CONTAINER_SOURCE_TARGET = PurePosixPath("/opt/sira")
CONTAINER_CONFIGURATION_TARGET = PurePosixPath("/opt/giclab/configuration")
PLAYWRIGHT_VERSION = "1.39.0"
CHROMIUM_REVISION = "1084"
UV_VERSION = "0.11.7"
UV_WHEEL_FILENAME = (
    "uv-0.11.7-py3-none-manylinux_2_17_aarch64.manylinux2014_aarch64.musllinux_1_1_aarch64.whl"
)
UV_WHEEL_SHA256 = "5985a15a92bd9a170fc1947abb1fbc3e9828c5a430ad85b5bed8356c20b67a71"
UV_WHEEL_BYTES = 23_609_640
DUMMY_SECRET_CANARY = "T07_GATE_B2_DUMMY_CANARY_PUBLIC_NOT_A_CREDENTIAL"
UPSTREAM_UV_LOCK_SHA256 = "138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e"
BASE_IMAGE_REFERENCE = (
    "mcr.microsoft.com/playwright/python:v1.39.0-jammy@"
    "sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c"
)
BASE_IMAGE_INDEX_DIGEST = "sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c"
BASE_IMAGE_ARM64_MANIFEST_DIGEST = (
    "sha256:f8fca31a4730afa691e73ed99b4a6ebf28b2a9bd65a7038bb6da4bd223bb237b"
)
BASE_IMAGE_AMD64_MANIFEST_DIGEST = (
    "sha256:8f7d4d5ef52dbe4af81db537258ae6d15c71b86c6984dd6030dac8f34c86ebcd"
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_CONTAINER_ID = re.compile(r"^[a-f0-9]{64}$")
_ATTEMPT_UUID = re.compile(r"^[a-f0-9]{32}$")
_AUTHORIZATION_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}$")
_SAFE_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,127}$")
_REPO_DIGEST_REFERENCE = re.compile(
    r"^[a-z0-9][a-z0-9._:/-]*(?::[A-Za-z0-9._-]+)?@sha256:[a-f0-9]{64}$"
)
_LOCAL_IMAGE_ID = re.compile(r"^sha256:[a-f0-9]{64}$")
_RUNTIME_USER = re.compile(r"^[1-9][0-9]*:[0-9]+$")
_CONTROL_OPERATION_TIMEOUT_SECONDS = 10
_CLEANUP_SEAL_RESERVE_BYTES = 128 * 1024
MAX_DOCKER_LIFECYCLE_OPERATIONS_PER_ATTEMPT = 32


class ContainerContractError(ValueError):
    """A planned attempt violates the Gate B1 containment contract."""


class ContainerLifecycleError(RuntimeError):
    """A runtime lifecycle operation failed or returned contradictory evidence."""


class ContainerPlatform(StrEnum):
    LINUX_ARM64 = "linux/arm64"
    LINUX_AMD64 = "linux/amd64"


class MountPurpose(StrEnum):
    ATTEMPT_ROOT = "attempt-root"
    SOURCE_INPUT = "source-input"
    CONFIGURATION_INPUT = "configuration-input"
    SECRET_FILE = "secret-file"


class ContainerFixture(StrEnum):
    ADVERSARIAL_CONTAINMENT = "adversarial-containment"
    BROWSER_PREFLIGHT = "browser-preflight"
    DUMMY_SECRET_PREFLIGHT = "dummy-secret-preflight"
    SIRA = "sira"


class LifecycleState(StrEnum):
    PLANNED = "planned"
    CREATED = "created"
    STARTED = "started"
    PROCESS_EVIDENCE_CAPTURED = "process-evidence-captured"
    STOP_REQUESTED = "stop-requested"
    KILL_REQUESTED = "kill-requested"
    TERMINAL_VERIFIED = "terminal-verified"
    EVIDENCE_CAPTURED = "evidence-captured"
    REMOVED = "removed"
    CLEANUP_VERIFIED = "cleanup-verified"
    SEALED = "sealed"


def _require_sha256(value: str, label: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise ContainerContractError(f"{label} must be a lowercase SHA-256 digest")


def _require_commit(value: str, label: str) -> None:
    if _COMMIT.fullmatch(value) is None:
        raise ContainerContractError(f"{label} must be an exact lowercase Git commit")


def _require_safe_id(value: str, label: str) -> None:
    if _SAFE_ID.fullmatch(value) is None:
        raise ContainerContractError(f"{label} is not a safe immutable identifier")


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _write_json_exclusive(path: Path, value: Mapping[str, object]) -> None:
    encoded = _json_bytes(value)
    _write_bytes_exclusive(path, encoded)


def _write_bytes_exclusive(path: Path, encoded: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        with suppress(OSError):
            os.close(descriptor)
        raise


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class ImmutableImageReference:
    """A registry digest or observed local image ID; tags alone are forbidden."""

    value: str

    def __post_init__(self) -> None:
        if not (
            _REPO_DIGEST_REFERENCE.fullmatch(self.value) is not None
            or _LOCAL_IMAGE_ID.fullmatch(self.value) is not None
        ):
            raise ContainerContractError(
                "image reference must be a repository@sha256 digest or observed sha256 image ID"
            )

    @property
    def digest(self) -> str:
        return self.value.rsplit("@", 1)[-1]


@dataclass(frozen=True, slots=True)
class ContainerResourceLimits:
    """Finite container and harness-owned resource limits."""

    cpu_millis: int | None
    memory_bytes: int | None
    pids: int | None
    wall_seconds: int | None
    output_bytes: int | None
    shm_bytes: int | None
    tmpfs_bytes: int | None
    stop_grace_seconds: int | None = 1

    def validate(self) -> None:
        for name in (
            "cpu_millis",
            "memory_bytes",
            "pids",
            "wall_seconds",
            "output_bytes",
            "shm_bytes",
            "tmpfs_bytes",
            "stop_grace_seconds",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ContainerContractError(f"{name} must be a finite positive integer")
        assert self.cpu_millis is not None
        assert self.memory_bytes is not None
        assert self.pids is not None
        if self.cpu_millis > 16_000:
            raise ContainerContractError("cpu_millis exceeds the Gate B1 policy maximum")
        if self.memory_bytes > 16 * 1024**3:
            raise ContainerContractError("memory_bytes exceeds the Gate B1 policy maximum")
        if self.pids > 1_024:
            raise ContainerContractError("pids exceeds the Gate B1 policy maximum")
        assert self.output_bytes is not None
        if self.output_bytes < 1024 * 1024:
            raise ContainerContractError("output_bytes must reserve at least one MiB")
        if self.output_bytes % (8 * 1024) != 0:
            raise ContainerContractError(
                "output_bytes must permit an exact Docker log allocation in KiB"
            )

    @property
    def payload_output_bytes(self) -> int:
        assert self.output_bytes is not None
        return self.output_bytes // 2

    @property
    def log_output_bytes(self) -> int:
        assert self.output_bytes is not None
        return self.output_bytes // 8

    @property
    def evidence_output_bytes(self) -> int:
        assert self.output_bytes is not None
        return self.output_bytes - self.payload_output_bytes - self.log_output_bytes

    def document(self) -> dict[str, int]:
        self.validate()
        values = {
            "cpu_millis": self.cpu_millis,
            "memory_bytes": self.memory_bytes,
            "pids": self.pids,
            "wall_seconds": self.wall_seconds,
            "output_bytes": self.output_bytes,
            "shm_bytes": self.shm_bytes,
            "tmpfs_bytes": self.tmpfs_bytes,
            "stop_grace_seconds": self.stop_grace_seconds,
            "payload_output_bytes": self.payload_output_bytes,
            "log_output_bytes": self.log_output_bytes,
            "evidence_output_bytes": self.evidence_output_bytes,
        }
        return {name: int(value) for name, value in values.items() if value is not None}


@dataclass(frozen=True, slots=True)
class ContainerRuntimeOptions:
    """Explicit security surface, including values used by negative tests."""

    privileged: bool = False
    pid_mode: str = "private"
    cgroupns_mode: str = "private"
    network_mode: str = "none"
    ipc_mode: str = "private"
    cap_drop: tuple[str, ...] = ("ALL",)
    cap_add: tuple[str, ...] = ()
    no_new_privileges: bool = True
    init: bool = True
    read_only_root: bool = True
    restart_policy: str = "no"
    pull_policy: str = "never"
    user: str = f"{os.getuid()}:{os.getgid()}"
    environment: tuple[tuple[str, str], ...] = (
        ("HOME", "/tmp"),
        ("XDG_CACHE_HOME", "/tmp/.cache"),
        ("XDG_CONFIG_HOME", "/tmp/.config"),
    )


@dataclass(frozen=True, slots=True)
class BindMount:
    source: Path
    target: PurePosixPath
    purpose: MountPurpose
    read_only: bool

    def __post_init__(self) -> None:
        if not self.source.is_absolute() or self.source.resolve(strict=False) != self.source:
            raise ContainerContractError("bind-mount source must be an absolute canonical path")
        if not self.target.is_absolute() or ".." in self.target.parts:
            raise ContainerContractError("bind-mount target must be absolute and traversal-free")
        if any(character in str(self.source) for character in (",", "\n", "\r")):
            raise ContainerContractError("bind-mount source cannot be rendered safely")
        if any(character in str(self.target) for character in (",", "\n", "\r")):
            raise ContainerContractError("bind-mount target cannot be rendered safely")


@dataclass(frozen=True, slots=True)
class ApprovedReadOnlyInput:
    """One exact repository-owned file approved for a read-only runtime bind."""

    source: Path
    target: PurePosixPath
    purpose: MountPurpose

    def __post_init__(self) -> None:
        if self.purpose not in {
            MountPurpose.SOURCE_INPUT,
            MountPurpose.CONFIGURATION_INPUT,
        }:
            raise ContainerContractError(
                "read-only input approvals are limited to source/configuration files"
            )
        if not self.source.is_absolute() or self.source.resolve(strict=False) != self.source:
            raise ContainerContractError("approved read-only input must be canonical")
        if not self.target.is_absolute() or ".." in self.target.parts:
            raise ContainerContractError("approved read-only target must be absolute")
        expected_target = {
            MountPurpose.SOURCE_INPUT: CONTAINER_SOURCE_TARGET,
            MountPurpose.CONFIGURATION_INPUT: CONTAINER_CONFIGURATION_TARGET,
        }[self.purpose]
        if self.target != expected_target:
            raise ContainerContractError("approved read-only input target is not exact")
        if self.source.is_symlink() or not self.source.exists():
            raise ContainerContractError("approved read-only input must already exist")
        if not stat.S_ISREG(self.source.lstat().st_mode):
            raise ContainerContractError("approved read-only inputs must be regular files")


@dataclass(frozen=True, slots=True)
class ContainerAttemptIdentity:
    experiment_id: str
    profile_plan_id: str
    condition: str
    attempt: int
    attempt_uuid: str
    repository_commit: str
    source_commit: str
    authorization_reference: str

    def __post_init__(self) -> None:
        _require_safe_id(self.experiment_id, "experiment_id")
        _require_safe_id(self.profile_plan_id, "profile_plan_id")
        _require_safe_id(self.condition, "condition")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ContainerContractError("attempt must be an integer >= 1")
        if _ATTEMPT_UUID.fullmatch(self.attempt_uuid) is None:
            raise ContainerContractError("attempt_uuid must be a fresh 128-bit lowercase identity")
        _require_commit(self.repository_commit, "repository_commit")
        _require_commit(self.source_commit, "source_commit")
        if self.source_commit != SIRA_UPSTREAM_COMMIT:
            raise ContainerContractError("source_commit must remain the pinned SiRA commit")
        if _AUTHORIZATION_REFERENCE.fullmatch(self.authorization_reference) is None:
            raise ContainerContractError("authorization_reference is not a safe reference")

    @property
    def container_name(self) -> str:
        condition = self.condition.lower().replace("_", "-")
        return f"giclab-t07-{condition}-{self.attempt}-{self.attempt_uuid}"

    def labels(self, image_digest: str) -> Mapping[str, str]:
        labels = {
            f"{CONTAINER_LABEL_PREFIX}.owner": "gic-lab",
            f"{CONTAINER_LABEL_PREFIX}.experiment": self.experiment_id,
            f"{CONTAINER_LABEL_PREFIX}.profile": self.profile_plan_id,
            f"{CONTAINER_LABEL_PREFIX}.condition": self.condition,
            f"{CONTAINER_LABEL_PREFIX}.attempt": str(self.attempt),
            f"{CONTAINER_LABEL_PREFIX}.attempt-uuid": self.attempt_uuid,
            f"{CONTAINER_LABEL_PREFIX}.repository-commit": self.repository_commit,
            f"{CONTAINER_LABEL_PREFIX}.source-commit": self.source_commit,
            f"{CONTAINER_LABEL_PREFIX}.image-digest": image_digest,
            f"{CONTAINER_LABEL_PREFIX}.authorization": self.authorization_reference,
        }
        return MappingProxyType(labels)


@dataclass(frozen=True, slots=True)
class AttemptRootContract:
    """One fresh harness-owned root, allocated before container creation."""

    owned_base: Path
    attempt_root: Path

    def validate_planned(self) -> None:
        for label, path in (("owned_base", self.owned_base), ("attempt_root", self.attempt_root)):
            if not path.is_absolute() or path.resolve(strict=False) != path:
                raise ContainerContractError(f"{label} must be absolute and canonical")
        if self.attempt_root == self.owned_base or self.owned_base not in self.attempt_root.parents:
            raise ContainerContractError("attempt_root must be below the harness-owned base")
        if self.attempt_root.parent != self.owned_base:
            raise ContainerContractError("attempt_root must be a direct immutable child")
        if self.attempt_root.exists() or self.attempt_root.is_symlink():
            raise ContainerContractError("attempt_root must not already exist")
        if not self.owned_base.is_dir() or self.owned_base.is_symlink():
            raise ContainerContractError("owned_base must be an existing ordinary directory")
        base_metadata = self.owned_base.stat()
        if base_metadata.st_uid != os.getuid():
            raise ContainerContractError("owned_base must be owned by the harness user")
        if stat.S_IMODE(base_metadata.st_mode) != 0o700:
            raise ContainerContractError("owned_base must have exact mode 0700")

    def allocate(self) -> None:
        self.validate_planned()
        self.attempt_root.mkdir(mode=0o700, exist_ok=False)
        actual = self.attempt_root.lstat()
        if actual.st_uid != os.getuid() or not stat.S_ISDIR(actual.st_mode):
            raise ContainerContractError("allocated attempt_root ownership is invalid")
        if stat.S_IMODE(actual.st_mode) & 0o077:
            raise ContainerContractError("allocated attempt_root permissions are too broad")


@dataclass(frozen=True, slots=True)
class ContainerAttemptSpec:
    identity: ContainerAttemptIdentity
    image: ImmutableImageReference
    platform: ContainerPlatform
    fixture: ContainerFixture
    resources: ContainerResourceLimits
    mounts: tuple[BindMount, ...]
    command: tuple[str, ...]
    ready_artifact: str
    runtime: ContainerRuntimeOptions = ContainerRuntimeOptions()


def _is_socket_mount(mount: BindMount) -> bool:
    rendered = f"{mount.source}:{mount.target}".lower()
    return any(
        marker in rendered
        for marker in (
            "docker.sock",
            "podman.sock",
            "containerd.sock",
            "/run/user/",
        )
    )


def validate_container_attempt(
    spec: ContainerAttemptSpec,
    root: AttemptRootContract,
    *,
    repository_root: Path,
    approved_read_only_inputs: tuple[ApprovedReadOnlyInput, ...] = (),
) -> None:
    """Fail closed unless every authoritative containment field is explicit."""

    options = spec.runtime
    if options.privileged:
        raise ContainerContractError("privileged containers are forbidden")
    if options.pid_mode != "private":
        raise ContainerContractError("the PID namespace must be exactly private")
    if options.cgroupns_mode != "private":
        raise ContainerContractError("the cgroup namespace must be exactly private")
    if options.network_mode != "none":
        raise ContainerContractError("attempt networking must be exactly none")
    if options.ipc_mode != "private":
        raise ContainerContractError("the IPC namespace must be exactly private")
    if options.cap_drop != ("ALL",) or options.cap_add:
        raise ContainerContractError("all Linux capabilities must be dropped")
    if not options.no_new_privileges:
        raise ContainerContractError("no-new-privileges must be enabled")
    if not options.init:
        raise ContainerContractError("a container init process is required")
    if not options.read_only_root:
        raise ContainerContractError("the root filesystem must be read-only")
    if options.restart_policy != "no":
        raise ContainerContractError("restart policy must be exactly no")
    if options.pull_policy != "never":
        raise ContainerContractError("attempt execution must never pull implicitly")
    expected_runtime_user = f"{os.getuid()}:{os.getgid()}"
    if _RUNTIME_USER.fullmatch(options.user) is None or options.user != expected_runtime_user:
        raise ContainerContractError(
            "attempt execution must use the exact non-root host UID:GID for bind ownership"
        )
    if options.environment != (
        ("HOME", "/tmp"),
        ("XDG_CACHE_HOME", "/tmp/.cache"),
        ("XDG_CONFIG_HOME", "/tmp/.config"),
    ):
        raise ContainerContractError("container environment must remain the exact non-secret set")
    assert_no_secret_literals((), options.environment)
    spec.resources.validate()
    if not spec.command or any(
        not isinstance(argument, str) or not argument or "\x00" in argument
        for argument in spec.command
    ):
        raise ContainerContractError("container command must be a nonempty argument array")
    if (
        not spec.ready_artifact
        or Path(spec.ready_artifact).name != spec.ready_artifact
        or spec.ready_artifact in {".", ".."}
    ):
        raise ContainerContractError("ready_artifact must be one safe attempt-root filename")
    assert_no_secret_literals(spec.command, ())
    if (
        not repository_root.is_absolute()
        or repository_root.resolve(strict=False) != repository_root
    ):
        raise ContainerContractError("repository_root must be absolute and canonical")

    approved_mounts: set[tuple[Path, PurePosixPath, MountPurpose]] = set()
    for approved in approved_read_only_inputs:
        if repository_root not in approved.source.parents:
            raise ContainerContractError(
                "approved read-only inputs must be exact repository-owned files"
            )
        key = (approved.source, approved.target, approved.purpose)
        if key in approved_mounts:
            raise ContainerContractError("read-only input allowlist entries must be unique")
        approved_mounts.add(key)

    attempt_mounts = [mount for mount in spec.mounts if mount.purpose is MountPurpose.ATTEMPT_ROOT]
    if len(attempt_mounts) != 1:
        raise ContainerContractError("exactly one attempt-root bind mount is required")
    attempt_mount = attempt_mounts[0]
    if (
        attempt_mount.source != root.attempt_root
        or attempt_mount.target != CONTAINER_ATTEMPT_TARGET
        or attempt_mount.read_only
    ):
        raise ContainerContractError("the sole writable bind must be the exact attempt root")

    home = Path.home().resolve(strict=False)
    seen_targets: set[PurePosixPath] = set()
    seen_purposes: set[MountPurpose] = set()
    for mount in spec.mounts:
        if mount.target in seen_targets:
            raise ContainerContractError("bind-mount targets must be unique")
        seen_targets.add(mount.target)
        if mount.purpose in seen_purposes:
            raise ContainerContractError("bind-mount purposes must be unique")
        seen_purposes.add(mount.purpose)
        if _is_socket_mount(mount):
            raise ContainerContractError("container-runtime socket mounts are forbidden")
        if (
            mount.source == Path("/")
            or mount.source == home
            or mount.source in home.parents
            or mount.source == repository_root
            or mount.source in repository_root.parents
        ):
            raise ContainerContractError("broad host mounts are forbidden")
        if mount.purpose is not MountPurpose.ATTEMPT_ROOT and not mount.read_only:
            raise ContainerContractError("only the attempt root may be writable")
        if mount.purpose is not MountPurpose.ATTEMPT_ROOT:
            if mount.source.is_symlink() or not mount.source.exists():
                raise ContainerContractError("read-only input mounts must already exist")
            metadata = mount.source.lstat()
            if mount.purpose in {
                MountPurpose.SOURCE_INPUT,
                MountPurpose.CONFIGURATION_INPUT,
            } and not stat.S_ISREG(metadata.st_mode):
                raise ContainerContractError(
                    "source/configuration input mounts must be exact regular files"
                )
            if not stat.S_ISREG(metadata.st_mode):
                raise ContainerContractError("read-only input mounts must be regular files")
        if mount.purpose is MountPurpose.SOURCE_INPUT and mount.target != CONTAINER_SOURCE_TARGET:
            raise ContainerContractError("source input must use the approved container target")
        if (
            mount.purpose is MountPurpose.CONFIGURATION_INPUT
            and mount.target != CONTAINER_CONFIGURATION_TARGET
        ):
            raise ContainerContractError("configuration input must use the approved target")
        if mount.purpose in {
            MountPurpose.SOURCE_INPUT,
            MountPurpose.CONFIGURATION_INPUT,
        }:
            key = (mount.source, mount.target, mount.purpose)
            if key not in approved_mounts:
                raise ContainerContractError(
                    "read-only input mount is absent from the exact approved-file allowlist"
                )
        if mount.purpose is MountPurpose.SECRET_FILE:
            if mount.target != CONTAINER_SECRET_TARGET or not mount.read_only:
                raise ContainerContractError(
                    "secret must be a read-only file at the approved target"
                )
            if repository_root == mount.source or repository_root in mount.source.parents:
                raise ContainerContractError("secret files must remain outside the repository")
            if root.attempt_root == mount.source or root.attempt_root in mount.source.parents:
                raise ContainerContractError("secret files must remain outside retained evidence")
            metadata = mount.source.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise ContainerContractError("secret mount must be a regular file")
            if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
                raise ContainerContractError(
                    "secret mount must be host-user-owned with exact mode 0600"
                )
            secret_parent = mount.source.parent
            parent_metadata = secret_parent.lstat()
            if (
                secret_parent.is_symlink()
                or not stat.S_ISDIR(parent_metadata.st_mode)
                or parent_metadata.st_uid != os.getuid()
                or stat.S_IMODE(parent_metadata.st_mode) != 0o700
            ):
                raise ContainerContractError(
                    "secret parent must be host-user-owned with exact mode 0700"
                )
    secret_mounts = [m for m in spec.mounts if m.purpose is MountPurpose.SECRET_FILE]
    if spec.fixture in {ContainerFixture.SIRA, ContainerFixture.DUMMY_SECRET_PREFLIGHT}:
        if len(secret_mounts) != 1:
            raise ContainerContractError("this attempt requires exactly one secret-file mount")
    elif secret_mounts:
        raise ContainerContractError("secret mounts are forbidden for non-secret fixtures")
    observed_approved_mounts = {
        (mount.source, mount.target, mount.purpose)
        for mount in spec.mounts
        if mount.purpose in {MountPurpose.SOURCE_INPUT, MountPurpose.CONFIGURATION_INPUT}
    }
    if observed_approved_mounts != approved_mounts:
        raise ContainerContractError(
            "read-only input allowlist must exactly equal the mounted input files"
        )


@dataclass(frozen=True, slots=True)
class DockerCommandRenderer:
    executable: Path

    def __post_init__(self) -> None:
        if not self.executable.is_absolute():
            raise ContainerContractError("container runtime executable must be absolute")

    def create(self, spec: ContainerAttemptSpec) -> tuple[str, ...]:
        spec.resources.validate()
        resources = spec.resources
        assert resources.cpu_millis is not None
        assert resources.memory_bytes is not None
        assert resources.pids is not None
        assert resources.shm_bytes is not None
        assert resources.tmpfs_bytes is not None
        assert resources.output_bytes is not None
        runtime_uid, runtime_gid = spec.runtime.user.split(":", 1)
        argv: list[str] = [
            str(self.executable),
            "container",
            "create",
            "--name",
            spec.identity.container_name,
            "--platform",
            spec.platform.value,
            "--pull",
            spec.runtime.pull_policy,
            "--network",
            spec.runtime.network_mode,
            # Docker represents a private PID namespace by leaving --pid unset.
            # Rendering the string "private" is invalid Moby syntax.
            "--cgroupns",
            spec.runtime.cgroupns_mode,
            "--ipc",
            spec.runtime.ipc_mode,
            "--restart",
            spec.runtime.restart_policy,
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges=true",
            "--init",
            "--pids-limit",
            str(resources.pids),
            "--memory",
            str(resources.memory_bytes),
            "--memory-swap",
            str(resources.memory_bytes),
            "--cpus",
            f"{resources.cpu_millis / 1000:.3f}",
            "--shm-size",
            str(resources.shm_bytes),
            "--read-only",
            "--user",
            spec.runtime.user,
            "--tmpfs",
            (
                f"/tmp:rw,noexec,nosuid,nodev,size={resources.tmpfs_bytes},"
                f"mode=1777,uid={runtime_uid},gid={runtime_gid}"
            ),
            "--tmpfs",
            (
                f"/run/secrets:rw,noexec,nosuid,nodev,size={resources.tmpfs_bytes},"
                f"mode=0700,uid={runtime_uid},gid={runtime_gid}"
            ),
            "--log-driver",
            "local",
            "--log-opt",
            f"max-size={_docker_size(resources.log_output_bytes)}",
            "--log-opt",
            "max-file=1",
        ]
        for name, value in spec.runtime.environment:
            argv.extend(("--env", f"{name}={value}"))
        for key, value in sorted(spec.identity.labels(spec.image.digest).items()):
            argv.extend(("--label", f"{key}={value}"))
        for mount in spec.mounts:
            access = "ro" if mount.read_only else "rw"
            argv.extend(
                (
                    "--mount",
                    f"type=bind,src={mount.source},dst={mount.target},{access}",
                )
            )
        argv.append(spec.image.value)
        argv.extend(spec.command)
        return tuple(argv)

    def start(self, container_id: str) -> tuple[str, ...]:
        return (str(self.executable), "container", "start", container_id)

    def inspect(self, container_id: str) -> tuple[str, ...]:
        return (str(self.executable), "container", "inspect", container_id)

    def inspect_image(self, image_reference: str) -> tuple[str, ...]:
        return (str(self.executable), "image", "inspect", image_reference)

    def top(self, container_id: str) -> tuple[str, ...]:
        return (
            str(self.executable),
            "container",
            "top",
            container_id,
            "-eo",
            "pid,ppid,pgid,sid,stat,comm,args",
        )

    def wait(self, container_id: str) -> tuple[str, ...]:
        return (str(self.executable), "container", "wait", container_id)

    def logs(self, container_id: str) -> tuple[str, ...]:
        return (str(self.executable), "container", "logs", "--timestamps", container_id)

    def stop(self, container_id: str, grace_seconds: int) -> tuple[str, ...]:
        return (
            str(self.executable),
            "container",
            "stop",
            "--time",
            str(grace_seconds),
            container_id,
        )

    def kill(self, container_id: str) -> tuple[str, ...]:
        return (
            str(self.executable),
            "container",
            "kill",
            "--signal",
            "KILL",
            container_id,
        )

    def remove(self, container_id: str) -> tuple[str, ...]:
        return (str(self.executable), "container", "rm", container_id)

    def list_containers(self, attempt_uuid: str) -> tuple[str, ...]:
        return (
            str(self.executable),
            "container",
            "ls",
            "--all",
            "--filter",
            f"label={CONTAINER_LABEL_PREFIX}.attempt-uuid={attempt_uuid}",
            "--format",
            "{{json .}}",
        )

    def list_networks(self, attempt_uuid: str) -> tuple[str, ...]:
        return (
            str(self.executable),
            "network",
            "ls",
            "--filter",
            f"label={CONTAINER_LABEL_PREFIX}.attempt-uuid={attempt_uuid}",
            "--format",
            "{{json .}}",
        )

    def list_volumes(self, attempt_uuid: str) -> tuple[str, ...]:
        return (
            str(self.executable),
            "volume",
            "ls",
            "--filter",
            f"label={CONTAINER_LABEL_PREFIX}.attempt-uuid={attempt_uuid}",
            "--format",
            "{{json .}}",
        )


@dataclass(frozen=True, slots=True)
class CommandResult:
    argv: tuple[str, ...]
    return_code: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True, slots=True)
class MaterializationAction:
    """One shell-free, single-attempt action under the Gate B2 build deadline."""

    action_id: str
    argv: tuple[str, ...]
    timeout_seconds: int
    expected_stdout: str | None = None

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z][a-z0-9-]{2,63}", self.action_id) is None:
            raise ContainerContractError("materialization action ID is invalid")
        if (
            not self.argv
            or not Path(self.argv[0]).is_absolute()
            or any(
                not isinstance(value, str) or not value or "\x00" in value for value in self.argv
            )
        ):
            raise ContainerContractError(
                "materialization action must be an exact shell-free absolute argument array"
            )
        if type(self.timeout_seconds) is not int or self.timeout_seconds <= 0:
            raise ContainerContractError("materialization action timeout must be positive")
        assert_no_secret_literals(self.argv, ())


@dataclass(frozen=True, slots=True)
class MaterializationPlan:
    plan_id: str
    authorization_reference: str
    aggregate_wall_seconds: int
    aggregate_output_bytes: int
    transfer_reservation_bytes: int
    incremental_disk_limit_bytes: int
    actions: tuple[MaterializationAction, ...]

    def __post_init__(self) -> None:
        if self.plan_id != "PLAN-T07-GATE-B2-MATERIALIZATION":
            raise ContainerContractError("materialization plan ID changed")
        if _AUTHORIZATION_REFERENCE.fullmatch(self.authorization_reference) is None:
            raise ContainerContractError("materialization authorization reference is invalid")
        if self.aggregate_wall_seconds != 3_600:
            raise ContainerContractError("materialization wall cap must be exactly 3600 seconds")
        if self.aggregate_output_bytes != 16 * 1024**2:
            raise ContainerContractError("materialization output cap must be exactly 16 MiB")
        if self.transfer_reservation_bytes != 2 * 1024**3:
            raise ContainerContractError("materialization transfer reservation must be 2 GiB")
        if self.incremental_disk_limit_bytes != 12 * 1024**3:
            raise ContainerContractError("materialization disk cap must be 12 GiB")
        if not self.actions:
            raise ContainerContractError("materialization plan requires actions")
        action_ids = [action.action_id for action in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ContainerContractError("materialization action IDs must be unique")

    @property
    def max_command_calls(self) -> int:
        return len(self.actions)


def load_materialization_plan(path: Path, *, expected_sha256: str) -> MaterializationPlan:
    """Load one immutable action plan; the supplied packet hash is authoritative."""

    _require_sha256(expected_sha256, "materialization plan SHA-256")
    if (
        not path.is_absolute()
        or path.resolve(strict=False) != path
        or path.is_symlink()
        or not path.is_file()
    ):
        raise ContainerContractError("materialization plan must be one canonical regular file")
    encoded = path.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise ContainerContractError("materialization plan hash does not match authorization")
    try:
        value = json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise ContainerContractError("materialization plan is not JSON") from exc
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "plan_id",
        "authorization_reference",
        "aggregate_wall_seconds",
        "aggregate_output_bytes",
        "transfer_reservation_bytes",
        "incremental_disk_limit_bytes",
        "actions",
    }:
        raise ContainerContractError("materialization plan fields changed")
    if value.get("schema_version") != CONTAINER_SCHEMA_VERSION:
        raise ContainerContractError("materialization plan schema version changed")
    raw_actions = value.get("actions")
    if not isinstance(raw_actions, list):
        raise ContainerContractError("materialization actions must be a list")
    actions: list[MaterializationAction] = []
    for raw in raw_actions:
        if (
            not isinstance(raw, Mapping)
            or not set(raw).issubset({"action_id", "argv", "timeout_seconds", "expected_stdout"})
            or not {"action_id", "argv", "timeout_seconds"}.issubset(raw)
        ):
            raise ContainerContractError("materialization action fields changed")
        argv = raw.get("argv")
        if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
            raise ContainerContractError("materialization action argv must be a string list")
        expected_stdout = raw.get("expected_stdout")
        if expected_stdout is not None and not isinstance(expected_stdout, str):
            raise ContainerContractError("expected materialization stdout must be a string")
        timeout_seconds = raw.get("timeout_seconds")
        if type(timeout_seconds) is not int:
            raise ContainerContractError("materialization action timeout must be an integer")
        actions.append(
            MaterializationAction(
                action_id=str(raw.get("action_id")),
                argv=tuple(argv),
                timeout_seconds=timeout_seconds,
                expected_stdout=expected_stdout,
            )
        )
    try:
        return MaterializationPlan(
            plan_id=str(value["plan_id"]),
            authorization_reference=str(value["authorization_reference"]),
            aggregate_wall_seconds=value["aggregate_wall_seconds"],
            aggregate_output_bytes=value["aggregate_output_bytes"],
            transfer_reservation_bytes=value["transfer_reservation_bytes"],
            incremental_disk_limit_bytes=value["incremental_disk_limit_bytes"],
            actions=tuple(actions),
        )
    except KeyError as exc:
        raise ContainerContractError("materialization plan is incomplete") from exc


def _replace_json_file(path: Path, value: Mapping[str, object]) -> None:
    temporary = path.with_name(path.name + ".next")
    if temporary.exists() or temporary.is_symlink():
        raise ContainerContractError("materialization ledger temporary path is not fresh")
    _write_json_exclusive(temporary, value)
    os.replace(temporary, path)


class BoundedMaterializationExecutor:
    """Run an immutable plan once under one monotonic aggregate deadline."""

    def __init__(
        self,
        *,
        runner: MaterializationCommandRunner,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.runner = runner
        self.clock = clock

    def execute(self, plan: MaterializationPlan, *, ledger_path: Path) -> Mapping[str, object]:
        if (
            not ledger_path.is_absolute()
            or ledger_path.resolve(strict=False) != ledger_path
            or ledger_path.exists()
            or ledger_path.is_symlink()
            or ledger_path.parent.resolve(strict=True) != ledger_path.parent
        ):
            raise ContainerContractError("materialization ledger path must be fresh and canonical")
        started = self.clock()
        deadline = started + plan.aggregate_wall_seconds
        records: list[dict[str, object]] = []
        observed_output_bytes = 0
        ledger: dict[str, object] = {
            "schema_version": CONTAINER_SCHEMA_VERSION,
            "plan_id": plan.plan_id,
            "authorization_reference": plan.authorization_reference,
            "aggregate_wall_seconds": plan.aggregate_wall_seconds,
            "aggregate_output_bytes": plan.aggregate_output_bytes,
            "max_command_calls": plan.max_command_calls,
            "attempts_per_action": 1,
            "status": "running",
            "records": records,
        }
        _write_json_exclusive(ledger_path, ledger)
        try:
            for action in plan.actions:
                action_started = self.clock()
                remaining = deadline - action_started
                if remaining <= 0:
                    raise ContainerLifecycleError("materialization aggregate wall cap expired")
                executable = Path(action.argv[0])
                if not executable.is_file() or not os.access(executable, os.X_OK):
                    raise ContainerLifecycleError(
                        f"materialization executable unavailable for {action.action_id}"
                    )
                timeout = min(float(action.timeout_seconds), remaining)
                result = self.runner.run(
                    action.argv,
                    deadline=action_started + timeout,
                    output_limit_bytes=(plan.aggregate_output_bytes - observed_output_bytes),
                )
                if self.clock() > deadline:
                    raise ContainerLifecycleError("materialization aggregate wall cap expired")
                stdout_bytes = result.stdout.encode("utf-8")
                stderr_bytes = result.stderr.encode("utf-8")
                observed_output_bytes += len(stdout_bytes) + len(stderr_bytes)
                record = {
                    "action_id": action.action_id,
                    "argv": list(action.argv),
                    "timeout_seconds": timeout,
                    "return_code": result.return_code,
                    "stdout_bytes": len(stdout_bytes),
                    "stdout_sha256": hashlib.sha256(stdout_bytes).hexdigest(),
                    "stderr_bytes": len(stderr_bytes),
                    "stderr_sha256": hashlib.sha256(stderr_bytes).hexdigest(),
                }
                records.append(record)
                if observed_output_bytes > plan.aggregate_output_bytes:
                    raise ContainerLifecycleError("materialization output cap exceeded")
                if result.return_code != 0:
                    raise ContainerLifecycleError(
                        f"materialization action failed: {action.action_id}"
                    )
                if action.expected_stdout is not None and result.stdout != action.expected_stdout:
                    raise ContainerLifecycleError(
                        f"materialization stdout drifted: {action.action_id}"
                    )
                ledger["observed_output_bytes"] = observed_output_bytes
                _replace_json_file(ledger_path, ledger)
            finished = self.clock()
            if finished > deadline:
                raise ContainerLifecycleError("materialization aggregate wall cap expired")
            ledger["status"] = "complete"
            ledger["command_calls"] = len(records)
            ledger["elapsed_seconds"] = finished - started
            _replace_json_file(ledger_path, ledger)
            return ledger
        except BaseException as failure:
            ledger["status"] = "failed"
            ledger["failure_type"] = type(failure).__name__
            ledger["command_calls"] = len(records)
            ledger["observed_output_bytes"] = observed_output_bytes
            ledger["elapsed_seconds"] = self.clock() - started
            with suppress(BaseException):
                _replace_json_file(ledger_path, ledger)
            raise


class MaterializationCommandRunner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        deadline: float,
        output_limit_bytes: int,
    ) -> CommandResult: ...


class SubprocessMaterializationCommandRunner:
    """Stream bounded output and kill the client at an exact monotonic deadline."""

    def run(
        self,
        argv: Sequence[str],
        *,
        deadline: float,
        output_limit_bytes: int,
    ) -> CommandResult:
        if output_limit_bytes <= 0:
            raise ContainerLifecycleError("materialization output cap is exhausted")
        process = subprocess.Popen(
            tuple(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        if process.stdout is None or process.stderr is None:
            process.kill()
            raise ContainerLifecycleError("materialization output pipes are unavailable")
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        captured = {"stdout": bytearray(), "stderr": bytearray()}
        try:
            while selector.get_map():
                remaining_seconds = deadline - time.monotonic()
                if remaining_seconds <= 0:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise ContainerLifecycleError("materialization action deadline expired")
                events = selector.select(timeout=min(0.05, remaining_seconds))
                if not events and process.poll() is not None:
                    continue
                for key, _mask in events:
                    stream = key.fileobj
                    already = len(captured["stdout"]) + len(captured["stderr"])
                    permitted = output_limit_bytes - already
                    chunk = os.read(key.fd, min(65_536, permitted + 1))
                    if not chunk:
                        selector.unregister(stream)
                        continue
                    if len(chunk) > permitted:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise ContainerLifecycleError("materialization output cap exceeded")
                    captured[str(key.data)].extend(chunk)
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise ContainerLifecycleError("materialization action deadline expired")
            return_code = process.wait(timeout=remaining_seconds)
        finally:
            selector.close()
            process.stdout.close()
            process.stderr.close()
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        try:
            stdout = bytes(captured["stdout"]).decode("utf-8")
            stderr = bytes(captured["stderr"]).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContainerLifecycleError("materialization output is not UTF-8") from exc
        return CommandResult(tuple(argv), return_code, stdout, stderr)


@dataclass(frozen=True, slots=True)
class WaitResult:
    result: CommandResult | None
    fixture_ready: bool
    wall_timed_out: bool
    output_limit_exceeded: bool
    observed_output_bytes: int


class DockerCommandRunner(Protocol):
    def run(self, argv: Sequence[str], *, timeout_seconds: float) -> CommandResult: ...

    def wait(
        self,
        argv: Sequence[str],
        *,
        wall_seconds: float,
        output_root: Path,
        output_limit_bytes: int,
        ready_path: Path,
    ) -> WaitResult: ...


def _directory_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ContainerLifecycleError("attempt output contains a forbidden symlink")
        if path.is_file():
            total += path.stat().st_size
    return total


def _enforce_directory_quota(root: Path, maximum: int) -> tuple[int, bool]:
    """Truncate retained fixture files deterministically after the container stops."""

    remaining = maximum
    exceeded = False
    retained = 0
    for path in sorted(root.rglob("*"), key=str):
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ContainerLifecycleError("attempt output contains a forbidden symlink")
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ContainerLifecycleError("attempt output contains a non-regular entry")
        keep = min(metadata.st_size, remaining)
        if keep < metadata.st_size:
            with path.open("r+b") as handle:
                handle.truncate(keep)
                handle.flush()
                os.fsync(handle.fileno())
            exceeded = True
        retained += keep
        remaining -= keep
    return retained, exceeded


def _ready_file_exists(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ContainerLifecycleError("fixture readiness artifact is not a regular file")
    return True


class SubprocessDockerCommandRunner:
    """Shell-free Docker CLI runner; construction and import perform no operation."""

    def run(self, argv: Sequence[str], *, timeout_seconds: float) -> CommandResult:
        completed = subprocess.run(
            tuple(argv),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return CommandResult(
            argv=tuple(argv),
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def wait(
        self,
        argv: Sequence[str],
        *,
        wall_seconds: float,
        output_root: Path,
        output_limit_bytes: int,
        ready_path: Path,
    ) -> WaitResult:
        process = subprocess.Popen(
            tuple(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        started = time.monotonic()
        observed = _directory_bytes(output_root)
        timed_out = False
        output_exceeded = observed > output_limit_bytes
        fixture_ready = _ready_file_exists(ready_path)
        while (
            process.poll() is None and not fixture_ready and not timed_out and not output_exceeded
        ):
            time.sleep(0.05)
            observed = _directory_bytes(output_root)
            output_exceeded = observed > output_limit_bytes
            timed_out = time.monotonic() - started >= wall_seconds
            fixture_ready = _ready_file_exists(ready_path)
        if process.poll() is None:
            process.terminate()  # stops only the waiting client, never the container
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
        result = None
        if not fixture_ready and not timed_out and not output_exceeded:
            result = CommandResult(tuple(argv), process.returncode, stdout, stderr)
        return WaitResult(
            result=result,
            fixture_ready=fixture_ready,
            wall_timed_out=timed_out,
            output_limit_exceeded=output_exceeded,
            observed_output_bytes=observed,
        )


def _require_success(result: CommandResult, operation: str) -> None:
    if result.return_code != 0:
        raise ContainerLifecycleError(f"container {operation} failed")


def _docker_size(value: int) -> str:
    """Render an exact Docker size using the local driver's supported k/m/g units."""

    for suffix, unit in (("g", 1024**3), ("m", 1024**2), ("k", 1024)):
        if value % unit == 0:
            return f"{value // unit}{suffix}"
    raise ContainerContractError("Docker local-log allocation must be whole KiB")


def _inspect_object(result: CommandResult) -> Mapping[str, Any]:
    _require_success(result, "inspect")
    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ContainerLifecycleError("container inspect did not return JSON") from exc
    if not isinstance(decoded, list) or len(decoded) != 1 or not isinstance(decoded[0], Mapping):
        raise ContainerLifecycleError("container inspect must identify exactly one container")
    return decoded[0]


def _inspect_state(value: Mapping[str, Any]) -> str:
    state = value.get("State")
    if not isinstance(state, Mapping) or not isinstance(state.get("Status"), str):
        raise ContainerLifecycleError("container inspect omitted State.Status")
    status = state["Status"]
    assert isinstance(status, str)
    return status


def _inspect_exit_code(value: Mapping[str, Any]) -> int:
    state = value.get("State")
    if not isinstance(state, Mapping) or type(state.get("ExitCode")) is not int:
        raise ContainerLifecycleError("container inspect omitted State.ExitCode")
    exit_code = state["ExitCode"]
    assert isinstance(exit_code, int)
    if exit_code < 0 or exit_code > 255:
        raise ContainerLifecycleError("container inspect returned an invalid exit code")
    return exit_code


def _wait_exit_code(result: CommandResult) -> int:
    _require_success(result, "terminal wait")
    rendered = result.stdout.strip()
    if re.fullmatch(r"[0-9]{1,3}", rendered) is None:
        raise ContainerLifecycleError("container wait omitted its exact exit code")
    exit_code = int(rendered)
    if exit_code > 255:
        raise ContainerLifecycleError("container wait returned an invalid exit code")
    return exit_code


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_fixture_record(spec: ContainerAttemptSpec, path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContainerLifecycleError("fixture readiness record is unreadable") from exc
    if not isinstance(value, Mapping) or value.get("schema_version") != CONTAINER_SCHEMA_VERSION:
        raise ContainerLifecycleError("fixture readiness record has an invalid schema")
    expected_uid, expected_gid = (int(part) for part in spec.runtime.user.split(":", 1))
    if value.get("runtime_uid") != expected_uid or value.get("runtime_gid") != expected_gid:
        raise ContainerLifecycleError("fixture runtime UID:GID did not match bind ownership")
    if spec.fixture is ContainerFixture.ADVERSARIAL_CONTAINMENT:
        if (
            value.get("role") != "reparented-session-spawner"
            or type(value.get("spawned_before_limit")) is not int
            or value["spawned_before_limit"] < 2
            or value.get("term_ignored") is not True
        ):
            raise ContainerLifecycleError("adversarial fixture did not reach its escape condition")
    elif spec.fixture is ContainerFixture.BROWSER_PREFLIGHT:
        if (
            value.get("source") != "local-static-file"
            or value.get("page_uri") != "file:///opt/giclab/fixtures/static.html"
            or value.get("browser_actions") != 1
            or value.get("screenshot_captures") != 1
            or value.get("browser_closed") is not True
            or value.get("playwright_version") != PLAYWRIGHT_VERSION
            or value.get("chromium_revision") != CHROMIUM_REVISION
        ):
            raise ContainerLifecycleError("browser fixture did not prove local-only shutdown")
        for field in (
            "installed_package_manifest_sha256",
            "chromium_executable_sha256",
        ):
            raw = value.get(field)
            if not isinstance(raw, str):
                raise ContainerLifecycleError("browser fixture omitted image provenance")
            _require_sha256(raw, field)
    elif spec.fixture is ContainerFixture.DUMMY_SECRET_PREFLIGHT:
        if (
            value.get("required_secret_name") != "SIRA_API_KEY"
            or value.get("required_secret_present") is not True
            or value.get("forbidden_fallback_present") is not False
        ):
            raise ContainerLifecycleError("dummy-secret fixture did not prove its channel")
    else:
        raise ContainerLifecycleError("unsupported fixture readiness record")
    return value


def _validate_inspect_identity(
    value: Mapping[str, Any],
    *,
    container_id: str,
    spec: ContainerAttemptSpec,
) -> None:
    if value.get("Id") != container_id:
        raise ContainerLifecycleError("stale or substituted container identity")
    name = value.get("Name")
    if not isinstance(name, str) or name.lstrip("/") != spec.identity.container_name:
        raise ContainerLifecycleError("container name does not match the immutable attempt")
    config = value.get("Config")
    host = value.get("HostConfig")
    if not isinstance(config, Mapping) or not isinstance(host, Mapping):
        raise ContainerLifecycleError("container inspect omitted policy state")
    labels = config.get("Labels")
    if not isinstance(labels, Mapping):
        raise ContainerLifecycleError("container labels are missing")
    expected_labels = spec.identity.labels(spec.image.digest)
    if any(labels.get(key) != expected for key, expected in expected_labels.items()):
        raise ContainerLifecycleError("container labels do not bind the planned identity")
    if value.get("Image") != spec.image.value:
        raise ContainerLifecycleError("container image ID does not match the immutable plan")
    command = config.get("Cmd")
    if not isinstance(command, list) or tuple(command) != spec.command:
        raise ContainerLifecycleError("container command does not match the immutable plan")
    if config.get("User") != spec.runtime.user:
        raise ContainerLifecycleError("container user does not match the non-root plan")
    environment = config.get("Env", [])
    if not isinstance(environment, list) or any(
        isinstance(item, str)
        and (item.startswith("SIRA_API_KEY=") or item.startswith("OPENAI_API_KEY="))
        for item in environment
    ):
        raise ContainerLifecycleError("container configuration leaked a secret environment field")
    if any(f"{name}={expected}" not in environment for name, expected in spec.runtime.environment):
        raise ContainerLifecycleError("container configuration environment changed")
    restart = host.get("RestartPolicy")
    restart_name = restart.get("Name") if isinstance(restart, Mapping) else None
    security_options = host.get("SecurityOpt")
    cap_drop = host.get("CapDrop")
    cap_add = host.get("CapAdd")
    log_config = host.get("LogConfig")
    log_options = log_config.get("Config") if isinstance(log_config, Mapping) else None
    tmpfs = host.get("Tmpfs")
    expected_tmpfs_size = str(spec.resources.tmpfs_bytes)
    runtime_uid, runtime_gid = spec.runtime.user.split(":", 1)
    assert spec.resources.cpu_millis is not None
    checks = (
        host.get("Privileged") is False,
        host.get("NetworkMode") == "none",
        host.get("PidMode") == "",
        host.get("CgroupnsMode") == "private",
        host.get("IpcMode") in ("", "private"),
        restart_name in ("", "no"),
        host.get("ReadonlyRootfs") is True,
        isinstance(cap_drop, list) and "ALL" in cap_drop,
        cap_add in (None, []),
        isinstance(security_options, list)
        and any("no-new-privileges" in str(item) for item in security_options),
        host.get("PidsLimit") == spec.resources.pids,
        host.get("Memory") == spec.resources.memory_bytes,
        host.get("MemorySwap") == spec.resources.memory_bytes,
        host.get("NanoCpus") == spec.resources.cpu_millis * 1_000_000,
        host.get("ShmSize") == spec.resources.shm_bytes,
        host.get("Init") is True,
        host.get("AutoRemove") is False,
        isinstance(tmpfs, Mapping)
        and set(tmpfs) == {"/tmp", "/run/secrets"}
        and all(expected_tmpfs_size in str(options) for options in tmpfs.values()),
        isinstance(tmpfs, Mapping)
        and all(
            f"uid={runtime_uid}" in str(options) and f"gid={runtime_gid}" in str(options)
            for options in tmpfs.values()
        ),
        isinstance(tmpfs, Mapping)
        and "mode=1777" in str(tmpfs.get("/tmp"))
        and any(mode in str(tmpfs.get("/run/secrets")) for mode in ("mode=0700", "mode=700")),
        isinstance(log_config, Mapping) and log_config.get("Type") == "local",
        isinstance(log_options, Mapping)
        and log_options.get("max-size") == _docker_size(spec.resources.log_output_bytes)
        and log_options.get("max-file") == "1",
    )
    if not all(checks):
        raise ContainerLifecycleError("container inspect contradicts the planned runtime policy")
    raw_mounts = value.get("Mounts")
    if not isinstance(raw_mounts, list):
        raise ContainerLifecycleError("container inspect mount evidence is malformed")
    observed_mounts: dict[str, Mapping[str, Any]] = {}
    observed_tmpfs: set[str] = set()
    for mount in raw_mounts:
        if not isinstance(mount, Mapping) or not isinstance(mount.get("Destination"), str):
            raise ContainerLifecycleError("container inspect mount evidence is malformed")
        destination = str(mount["Destination"])
        if mount.get("Type") == "bind":
            observed_mounts[destination] = mount
        elif mount.get("Type") == "tmpfs":
            if destination not in {"/tmp", "/run/secrets"} or mount.get("RW") is not True:
                raise ContainerLifecycleError("container inspect added an unapproved tmpfs mount")
            observed_tmpfs.add(destination)
        else:
            raise ContainerLifecycleError("container inspect added an unapproved mount type")
    if len(observed_mounts) != len(spec.mounts) or not observed_tmpfs.issubset(
        {"/tmp", "/run/secrets"}
    ):
        raise ContainerLifecycleError("container inspect mount count changed")
    for planned in spec.mounts:
        observed = observed_mounts.get(str(planned.target))
        if (
            observed is None
            or observed.get("Type") != "bind"
            or observed.get("Source") != str(planned.source)
            or observed.get("RW") is planned.read_only
        ):
            raise ContainerLifecycleError("container inspect mount policy changed")


def _bounded_pre_removal_evidence(
    *,
    maximum_bytes: int,
    log_maximum_bytes: int,
    container_id: str,
    process_evidence: str,
    logs: CommandResult,
    initial_inspect: Mapping[str, Any],
    final_inspect: Mapping[str, Any],
    fixture_record: Mapping[str, Any],
    operations: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], bool, int, int]:
    """Fit raw evidence under its retained allocation or seal a hashed failure record."""

    stdout_bytes = logs.stdout.encode("utf-8")
    stderr_bytes = logs.stderr.encode("utf-8")

    def document(stdout: str, stderr: str, *, complete: bool) -> dict[str, object]:
        return {
            "schema_version": CONTAINER_SCHEMA_VERSION,
            "captured_at_utc": _utc_now(),
            "container_id": container_id,
            "evidence_complete": complete,
            "process_evidence": process_evidence,
            "container_logs": {
                "stdout": stdout,
                "stderr": stderr,
                "stdout_bytes": len(stdout_bytes),
                "stderr_bytes": len(stderr_bytes),
                "stdout_sha256": hashlib.sha256(stdout_bytes).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr_bytes).hexdigest(),
                "truncated": not complete,
            },
            "fixture_record": dict(fixture_record),
            "inspect_created": dict(initial_inspect),
            "inspect_before_removal": dict(final_inspect),
            "operations": [dict(operation) for operation in operations],
        }

    full = document(logs.stdout, logs.stderr, complete=True)
    full_size = len(_json_bytes(full))
    if len(stdout_bytes) + len(stderr_bytes) <= log_maximum_bytes and full_size <= maximum_bytes:
        return full, True, full_size, full_size

    combined = stdout_bytes + stderr_bytes
    low = 0
    high = min(len(combined), maximum_bytes, log_maximum_bytes)
    best: Mapping[str, object] | None = None
    best_size = 0
    while low <= high:
        retained = (low + high) // 2
        retained_stdout = stdout_bytes[: min(len(stdout_bytes), retained)]
        retained_stderr = stderr_bytes[: max(0, retained - len(retained_stdout))]
        candidate = document(
            retained_stdout.decode("utf-8", errors="ignore"),
            retained_stderr.decode("utf-8", errors="ignore"),
            complete=False,
        )
        size = len(_json_bytes(candidate))
        if size <= maximum_bytes:
            best = candidate
            best_size = size
            low = retained + 1
        else:
            high = retained - 1
    if best is not None:
        return best, False, best_size, full_size

    compact = {
        "schema_version": CONTAINER_SCHEMA_VERSION,
        "captured_at_utc": _utc_now(),
        "container_id": container_id,
        "evidence_complete": False,
        "process_evidence_bytes": len(process_evidence.encode("utf-8")),
        "process_evidence_sha256": _sha256_text(process_evidence),
        "container_logs_stdout_bytes": len(stdout_bytes),
        "container_logs_stdout_sha256": hashlib.sha256(stdout_bytes).hexdigest(),
        "container_logs_stderr_bytes": len(stderr_bytes),
        "container_logs_stderr_sha256": hashlib.sha256(stderr_bytes).hexdigest(),
        "fixture_record_sha256": hashlib.sha256(_json_bytes(fixture_record)).hexdigest(),
        "inspect_created_sha256": hashlib.sha256(_json_bytes(initial_inspect)).hexdigest(),
        "inspect_before_removal_sha256": hashlib.sha256(_json_bytes(final_inspect)).hexdigest(),
        "operations_sha256": hashlib.sha256(
            _json_bytes({"operations": list(operations)})
        ).hexdigest(),
    }
    compact_size = len(_json_bytes(compact))
    if compact_size > maximum_bytes:
        raise ContainerLifecycleError("evidence allocation cannot fit its compact failure record")
    return compact, False, compact_size, full_size


@dataclass(frozen=True, slots=True)
class ContainerLifecycleEvidence:
    container_id: str
    container_name: str
    attempt_uuid: str
    fixture: ContainerFixture
    platform: ContainerPlatform
    image_reference: str
    image_digest: str
    runtime_user: str
    resources: ContainerResourceLimits
    states: tuple[LifecycleState, ...]
    fixture_ready: bool
    stop_sent: bool
    kill_sent: bool
    wall_timed_out: bool
    output_limit_exceeded: bool
    observed_output_bytes: int
    retained_output_bytes: int
    evidence_complete: bool
    probe_succeeded: bool
    container_exit_code: int
    terminal_state: str
    removed: bool
    residual_containers: tuple[str, ...]
    residual_networks: tuple[str, ...]
    residual_volumes: tuple[str, ...]
    sealed: bool

    def __post_init__(self) -> None:
        expected = [
            LifecycleState.PLANNED,
            LifecycleState.CREATED,
            LifecycleState.STARTED,
            LifecycleState.PROCESS_EVIDENCE_CAPTURED,
            LifecycleState.STOP_REQUESTED,
        ]
        if self.kill_sent:
            expected.append(LifecycleState.KILL_REQUESTED)
        expected.extend(
            (
                LifecycleState.TERMINAL_VERIFIED,
                LifecycleState.EVIDENCE_CAPTURED,
                LifecycleState.REMOVED,
                LifecycleState.CLEANUP_VERIFIED,
                LifecycleState.SEALED,
            )
        )
        if self.states != tuple(expected):
            raise ContainerLifecycleError("lifecycle evidence states are incomplete or reordered")
        if not self.stop_sent or (LifecycleState.KILL_REQUESTED in self.states) != self.kill_sent:
            raise ContainerLifecycleError("lifecycle flags contradict the ordered states")
        self.resources.validate()
        assert self.resources.output_bytes is not None
        if (
            self.retained_output_bytes < 0
            or self.retained_output_bytes > self.resources.output_bytes
        ):
            raise ContainerLifecycleError("retained output exceeds the exact attempt cap")
        if self.observed_output_bytes < self.retained_output_bytes:
            raise ContainerLifecycleError("observed output cannot be below retained output")
        if (
            not self.output_limit_exceeded
            and self.observed_output_bytes > self.resources.output_bytes
        ):
            raise ContainerLifecycleError("unflagged output observation exceeds the attempt cap")
        expected_success = (
            self.fixture_ready
            and not self.wall_timed_out
            and not self.output_limit_exceeded
            and self.evidence_complete
            and self.removed
            and not self.residual_containers
            and not self.residual_networks
            and not self.residual_volumes
            and self.sealed
        )
        if self.probe_succeeded is not expected_success:
            raise ContainerLifecycleError("probe success contradicts evidence and cleanup state")

    def document(self) -> dict[str, object]:
        return {
            "schema_version": CONTAINER_SCHEMA_VERSION,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "attempt_uuid": self.attempt_uuid,
            "fixture": self.fixture.value,
            "platform": self.platform.value,
            "image_reference": self.image_reference,
            "image_digest": self.image_digest,
            "runtime_user": self.runtime_user,
            "resource_limits": self.resources.document(),
            "lifecycle_states": [state.value for state in self.states],
            "fixture_ready": self.fixture_ready,
            "stop_sent": self.stop_sent,
            "kill_sent": self.kill_sent,
            "wall_timed_out": self.wall_timed_out,
            "output_limit_exceeded": self.output_limit_exceeded,
            "observed_output_bytes": self.observed_output_bytes,
            "retained_output_bytes": self.retained_output_bytes,
            "evidence_complete": self.evidence_complete,
            "probe_succeeded": self.probe_succeeded,
            "container_exit_code": self.container_exit_code,
            "terminal_state": self.terminal_state,
            "removed": self.removed,
            "residual_containers": list(self.residual_containers),
            "residual_networks": list(self.residual_networks),
            "residual_volumes": list(self.residual_volumes),
            "sealed": self.sealed,
        }


class DockerAttemptExecutor:
    """Execute one future authorized attempt through the container lifecycle API."""

    def __init__(
        self,
        *,
        renderer: DockerCommandRenderer,
        runner: DockerCommandRunner,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.renderer = renderer
        self.runner = runner
        self.clock = clock
        self._used_attempt_uuids: set[str] = set()
        self._used_container_ids: set[str] = set()
        self._attempt_container_ids: dict[str, str] = {}
        self._operation_counts: dict[str, int] = {}

    def _record_operation(self, attempt_uuid: str) -> None:
        count = self._operation_counts.get(attempt_uuid, 0) + 1
        if count > MAX_DOCKER_LIFECYCLE_OPERATIONS_PER_ATTEMPT:
            raise ContainerLifecycleError("Docker lifecycle operation cap exceeded")
        self._operation_counts[attempt_uuid] = count

    def execute(
        self,
        spec: ContainerAttemptSpec,
        root: AttemptRootContract,
        *,
        repository_root: Path,
        approved_read_only_inputs: tuple[ApprovedReadOnlyInput, ...] = (),
    ) -> ContainerLifecycleEvidence:
        """Run once and attempt label-bound cleanup on every post-create failure."""

        try:
            return self._execute_once(
                spec,
                root,
                repository_root=repository_root,
                approved_read_only_inputs=approved_read_only_inputs,
            )
        except BaseException as failure:
            try:
                self._emergency_cleanup(spec, root, failure)
            except BaseException as cleanup_failure:
                failure.add_note("emergency cleanup also failed: " + type(cleanup_failure).__name__)
            raise

    def _emergency_cleanup(
        self,
        spec: ContainerAttemptSpec,
        root: AttemptRootContract,
        failure: BaseException,
    ) -> None:
        if not root.attempt_root.is_dir() or root.attempt_root.is_symlink():
            return
        operations: list[dict[str, object]] = []
        cleanup_errors: list[str] = []
        expected_id = self._attempt_container_ids.get(spec.identity.attempt_uuid)
        container_id: str | None = None
        terminal_state: str | None = None
        removed = False

        def run(
            operation: str,
            argv: tuple[str, ...],
            timeout: float = _CONTROL_OPERATION_TIMEOUT_SECONDS,
            *,
            nonzero_is_error: bool = True,
        ) -> CommandResult | None:
            self._record_operation(spec.identity.attempt_uuid)
            try:
                result = self.runner.run(argv, timeout_seconds=timeout)
            except BaseException as exc:
                cleanup_errors.append(f"{operation}:{type(exc).__name__}")
                return None
            operations.append(
                {
                    "operation": operation,
                    "argv": list(argv),
                    "return_code": result.return_code,
                }
            )
            if result.return_code != 0 and nonzero_is_error:
                cleanup_errors.append(f"{operation}:return-code-{result.return_code}")
            return result

        inspected = run(
            "failure-inspect",
            self.renderer.inspect(expected_id or spec.identity.container_name),
            nonzero_is_error=expected_id is not None,
        )
        if inspected is not None and inspected.return_code == 0:
            try:
                value = _inspect_object(inspected)
                observed_id = value.get("Id")
                if not isinstance(observed_id, str) or _CONTAINER_ID.fullmatch(observed_id) is None:
                    raise ContainerLifecycleError("failure inspect omitted an exact container ID")
                _validate_inspect_identity(
                    value,
                    container_id=expected_id or observed_id,
                    spec=spec,
                )
                container_id = observed_id
                terminal_state = _inspect_state(value)
            except ContainerLifecycleError as exc:
                cleanup_errors.append(f"failure-inspect-validation:{type(exc).__name__}")

        if container_id is not None:
            if terminal_state not in {"exited", "dead"}:
                run("failure-top-before-stop", self.renderer.top(container_id))
                assert spec.resources.stop_grace_seconds is not None
                stopped = run(
                    "failure-stop",
                    self.renderer.stop(container_id, spec.resources.stop_grace_seconds),
                    timeout=spec.resources.stop_grace_seconds + _CONTROL_OPERATION_TIMEOUT_SECONDS,
                )
                after_stop = run("failure-inspect-after-stop", self.renderer.inspect(container_id))
                if after_stop is not None and after_stop.return_code == 0:
                    try:
                        terminal_state = _inspect_state(_inspect_object(after_stop))
                    except ContainerLifecycleError as exc:
                        cleanup_errors.append(f"failure-stop-inspect:{type(exc).__name__}")
                if (
                    stopped is None
                    or stopped.return_code != 0
                    or terminal_state not in {"exited", "dead"}
                ):
                    run("failure-kill", self.renderer.kill(container_id))
                    after_kill = run(
                        "failure-inspect-after-kill",
                        self.renderer.inspect(container_id),
                    )
                    if after_kill is not None and after_kill.return_code == 0:
                        try:
                            terminal_state = _inspect_state(_inspect_object(after_kill))
                        except ContainerLifecycleError as exc:
                            cleanup_errors.append(f"failure-kill-inspect:{type(exc).__name__}")
            logs = run("failure-logs-before-removal", self.renderer.logs(container_id))
            final = run("failure-inspect-before-removal", self.renderer.inspect(container_id))
            if final is not None and final.return_code == 0:
                failure_evidence = {
                    "schema_version": CONTAINER_SCHEMA_VERSION,
                    "container_id": container_id,
                    "inspect_sha256": hashlib.sha256(final.stdout.encode("utf-8")).hexdigest(),
                    "logs_stdout_sha256": hashlib.sha256(
                        ("" if logs is None else logs.stdout).encode("utf-8")
                    ).hexdigest(),
                    "operations": operations,
                }
                encoded = _json_bytes(failure_evidence)
                if len(encoded) <= spec.resources.evidence_output_bytes:
                    _write_bytes_exclusive(
                        root.attempt_root / "container-failure-evidence-before-removal.json",
                        encoded,
                    )
                else:
                    cleanup_errors.append("failure-evidence:output-allocation")
            if terminal_state in {"exited", "dead"}:
                removal = run("failure-remove", self.renderer.remove(container_id))
                removed = removal is not None and removal.return_code == 0

        residuals: dict[str, list[str]] = {}
        for kind, argv in (
            ("containers", self.renderer.list_containers(spec.identity.attempt_uuid)),
            ("networks", self.renderer.list_networks(spec.identity.attempt_uuid)),
            ("volumes", self.renderer.list_volumes(spec.identity.attempt_uuid)),
        ):
            result = run(f"failure-verify-{kind}", argv)
            residuals[kind] = (
                [] if result is None else [line for line in result.stdout.splitlines() if line]
            )
        cleanup_sealed = (
            not any(residuals.values()) and not cleanup_errors and (container_id is None or removed)
        )
        cleanup_path = root.attempt_root / "container-failure-cleanup.json"
        if not cleanup_path.exists():
            assert spec.resources.output_bytes is not None
            output_truncated = False
            while True:
                effective_errors = list(cleanup_errors)
                if output_truncated and "retained-output:truncated" not in effective_errors:
                    effective_errors.append("retained-output:truncated")
                failure_cleanup = {
                    "schema_version": CONTAINER_SCHEMA_VERSION,
                    "captured_at_utc": _utc_now(),
                    "failure_type": type(failure).__name__,
                    "container_id": container_id,
                    "terminal_state": terminal_state,
                    "removed": removed,
                    "residuals": residuals,
                    "cleanup_error_types": effective_errors,
                    "output_limit_exceeded": output_truncated,
                    "cleanup_sealed": cleanup_sealed and not output_truncated,
                    "operations": operations,
                }
                encoded = _json_bytes(failure_cleanup)
                if len(encoded) > spec.resources.evidence_output_bytes:
                    raise ContainerLifecycleError(
                        "failure cleanup record exceeded its evidence allocation"
                    )
                retained_before_seal = _directory_bytes(root.attempt_root)
                allowed_before_seal = spec.resources.output_bytes - len(encoded)
                if allowed_before_seal < 0:
                    raise ContainerLifecycleError(
                        "failure cleanup record cannot fit the attempt output cap"
                    )
                if retained_before_seal <= allowed_before_seal:
                    break
                _retained, truncated = _enforce_directory_quota(
                    root.attempt_root,
                    allowed_before_seal,
                )
                output_truncated = output_truncated or truncated
            _write_bytes_exclusive(cleanup_path, encoded)
            if _directory_bytes(root.attempt_root) > spec.resources.output_bytes:
                raise ContainerLifecycleError("failure cleanup exceeded the attempt output cap")

    def _execute_once(
        self,
        spec: ContainerAttemptSpec,
        root: AttemptRootContract,
        *,
        repository_root: Path,
        approved_read_only_inputs: tuple[ApprovedReadOnlyInput, ...],
    ) -> ContainerLifecycleEvidence:
        validate_container_attempt(
            spec,
            root,
            repository_root=repository_root,
            approved_read_only_inputs=approved_read_only_inputs,
        )
        if spec.identity.attempt_uuid in self._used_attempt_uuids:
            raise ContainerLifecycleError("attempt identity was already consumed")
        self._used_attempt_uuids.add(spec.identity.attempt_uuid)
        self._operation_counts[spec.identity.attempt_uuid] = 0
        attempt_started = self.clock()
        assert spec.resources.wall_seconds is not None
        workload_deadline = attempt_started + spec.resources.wall_seconds
        root.allocate()
        states: list[LifecycleState] = [LifecycleState.PLANNED]
        operations: list[dict[str, object]] = []

        def run(
            operation: str,
            argv: tuple[str, ...],
            timeout: float = _CONTROL_OPERATION_TIMEOUT_SECONDS,
            *,
            workload_bounded: bool = False,
        ) -> CommandResult:
            if workload_bounded:
                remaining = workload_deadline - self.clock()
                if remaining <= 0:
                    raise ContainerLifecycleError(
                        "attempt wall limit expired before readiness wait"
                    )
                # subprocess accepts a float timeout. Never round up past the exact
                # workload deadline, even when only a fraction of a second remains.
                timeout = min(timeout, remaining)
            self._record_operation(spec.identity.attempt_uuid)
            result = self.runner.run(argv, timeout_seconds=timeout)
            operations.append(
                {
                    "operation": operation,
                    "argv": list(argv),
                    "return_code": result.return_code,
                }
            )
            return result

        create = run("create", self.renderer.create(spec), workload_bounded=True)
        _require_success(create, "create")
        container_id = create.stdout.strip()
        if _CONTAINER_ID.fullmatch(container_id) is None:
            raise ContainerLifecycleError("create did not return an exact container ID")
        if container_id in self._used_container_ids:
            raise ContainerLifecycleError("runtime returned a stale container identity")
        self._used_container_ids.add(container_id)
        self._attempt_container_ids[spec.identity.attempt_uuid] = container_id
        states.append(LifecycleState.CREATED)

        initial_inspect_result = run(
            "inspect-created",
            self.renderer.inspect(container_id),
            workload_bounded=True,
        )
        initial_inspect = _inspect_object(initial_inspect_result)
        _validate_inspect_identity(initial_inspect, container_id=container_id, spec=spec)
        start = run("start", self.renderer.start(container_id), workload_bounded=True)
        _require_success(start, "start")
        states.append(LifecycleState.STARTED)

        ready_path = root.attempt_root / spec.ready_artifact
        remaining = workload_deadline - self.clock()
        if remaining <= 0:
            wait = WaitResult(
                result=None,
                fixture_ready=False,
                wall_timed_out=True,
                output_limit_exceeded=False,
                observed_output_bytes=_directory_bytes(root.attempt_root),
            )
        else:
            self._record_operation(spec.identity.attempt_uuid)
            wait = self.runner.wait(
                self.renderer.wait(container_id),
                wall_seconds=remaining,
                output_root=root.attempt_root,
                output_limit_bytes=spec.resources.payload_output_bytes,
                ready_path=ready_path,
            )
        operations.append(
            {
                "operation": "wait",
                "argv": list(self.renderer.wait(container_id)),
                "return_code": wait.result.return_code if wait.result is not None else None,
                "fixture_ready": wait.fixture_ready,
                "wall_timed_out": wait.wall_timed_out,
                "output_limit_exceeded": wait.output_limit_exceeded,
                "observed_output_bytes": wait.observed_output_bytes,
            }
        )

        stop_sent = False
        kill_sent = False
        post_wait_inspect = _inspect_object(
            run("inspect-post-wait", self.renderer.inspect(container_id))
        )
        _validate_inspect_identity(post_wait_inspect, container_id=container_id, spec=spec)
        terminal_state = _inspect_state(post_wait_inspect)
        if terminal_state in {"exited", "dead"}:
            raise ContainerLifecycleError("fixture exited before lifecycle stop ownership")
        fixture_record: Mapping[str, Any] = {}
        if wait.fixture_ready:
            fixture_record = _load_fixture_record(spec, ready_path)

        process_evidence = run("top-before-stop", self.renderer.top(container_id))
        _require_success(process_evidence, "pre-stop process evidence")
        if not process_evidence.stdout.strip():
            raise ContainerLifecycleError("pre-stop process evidence is empty")
        states.append(LifecycleState.PROCESS_EVIDENCE_CAPTURED)

        assert spec.resources.stop_grace_seconds is not None
        stop_sent = True
        states.append(LifecycleState.STOP_REQUESTED)
        stop = run(
            "stop",
            self.renderer.stop(container_id, spec.resources.stop_grace_seconds),
            timeout=spec.resources.stop_grace_seconds + _CONTROL_OPERATION_TIMEOUT_SECONDS,
        )
        after_stop = _inspect_object(run("inspect-after-stop", self.renderer.inspect(container_id)))
        _validate_inspect_identity(after_stop, container_id=container_id, spec=spec)
        terminal_state = _inspect_state(after_stop)
        if stop.return_code != 0 or terminal_state not in {"exited", "dead"}:
            kill_sent = True
            states.append(LifecycleState.KILL_REQUESTED)
            kill = run("kill", self.renderer.kill(container_id))
            _require_success(kill, "kill")
            after_kill = _inspect_object(
                run("inspect-after-kill", self.renderer.inspect(container_id))
            )
            _validate_inspect_identity(after_kill, container_id=container_id, spec=spec)
            terminal_state = _inspect_state(after_kill)

        if terminal_state not in {"exited", "dead"}:
            raise ContainerLifecycleError("container did not reach a terminal state")
        terminal_inspect = after_kill if kill_sent else after_stop
        container_exit_code = _inspect_exit_code(terminal_inspect)
        terminal_wait = run("wait-terminal", self.renderer.wait(container_id))
        if _wait_exit_code(terminal_wait) != container_exit_code:
            raise ContainerLifecycleError("wait and inspect disagree on container exit code")
        states.append(LifecycleState.TERMINAL_VERIFIED)
        logs = run("logs-before-removal", self.renderer.logs(container_id))
        _require_success(logs, "logs evidence")
        final_inspect_result = run("inspect-before-removal", self.renderer.inspect(container_id))
        final_inspect = _inspect_object(final_inspect_result)
        _validate_inspect_identity(final_inspect, container_id=container_id, spec=spec)
        if (
            _inspect_state(final_inspect) != terminal_state
            or _inspect_exit_code(final_inspect) != container_exit_code
        ):
            raise ContainerLifecycleError("final inspect changed terminal state")
        states.append(LifecycleState.EVIDENCE_CAPTURED)

        if spec.fixture is ContainerFixture.DUMMY_SECRET_PREFLIGHT:
            assert_dummy_secret_absent(
                DUMMY_SECRET_CANARY,
                documents=(
                    process_evidence.stdout,
                    logs.stdout,
                    logs.stderr,
                    initial_inspect,
                    final_inspect,
                    operations,
                    fixture_record,
                ),
            )

        payload_peak = max(wait.observed_output_bytes, _directory_bytes(root.attempt_root))
        _payload_retained, payload_truncated = _enforce_directory_quota(
            root.attempt_root,
            spec.resources.payload_output_bytes,
        )
        evidence_allocation = (
            spec.resources.log_output_bytes
            + spec.resources.evidence_output_bytes
            - _CLEANUP_SEAL_RESERVE_BYTES
        )
        pre_removal, evidence_complete, _pre_removal_size, full_evidence_size = (
            _bounded_pre_removal_evidence(
                maximum_bytes=evidence_allocation,
                log_maximum_bytes=spec.resources.log_output_bytes,
                container_id=container_id,
                process_evidence=process_evidence.stdout,
                logs=logs,
                initial_inspect=initial_inspect,
                final_inspect=final_inspect,
                fixture_record=fixture_record,
                operations=operations,
            )
        )
        _write_json_exclusive(
            root.attempt_root / "container-evidence-before-removal.json",
            pre_removal,
        )

        remove = run("remove", self.renderer.remove(container_id))
        _require_success(remove, "remove")
        states.append(LifecycleState.REMOVED)
        container_list = run(
            "verify-containers-absent",
            self.renderer.list_containers(spec.identity.attempt_uuid),
        )
        network_list = run(
            "verify-networks-absent",
            self.renderer.list_networks(spec.identity.attempt_uuid),
        )
        volume_list = run(
            "verify-volumes-absent",
            self.renderer.list_volumes(spec.identity.attempt_uuid),
        )
        for operation, result in (
            ("container residual inspection", container_list),
            ("network residual inspection", network_list),
            ("volume residual inspection", volume_list),
        ):
            _require_success(result, operation)
        residual_containers = tuple(line for line in container_list.stdout.splitlines() if line)
        residual_networks = tuple(line for line in network_list.stdout.splitlines() if line)
        residual_volumes = tuple(line for line in volume_list.stdout.splitlines() if line)
        if residual_containers or residual_networks or residual_volumes:
            raise ContainerLifecycleError("owned container resources remain after cleanup")
        states.extend((LifecycleState.CLEANUP_VERIFIED, LifecycleState.SEALED))
        base_retained = _directory_bytes(root.attempt_root)
        raw_observed = payload_peak + full_evidence_size
        assert spec.resources.output_bytes is not None
        output_limit_exceeded = (
            wait.output_limit_exceeded
            or payload_truncated
            or not evidence_complete
            or raw_observed > spec.resources.output_bytes
        )
        retained = base_retained
        while True:
            observed = max(raw_observed, retained)
            probe_succeeded = (
                wait.fixture_ready
                and not wait.wall_timed_out
                and not output_limit_exceeded
                and evidence_complete
            )
            evidence = ContainerLifecycleEvidence(
                container_id=container_id,
                container_name=spec.identity.container_name,
                attempt_uuid=spec.identity.attempt_uuid,
                fixture=spec.fixture,
                platform=spec.platform,
                image_reference=spec.image.value,
                image_digest=spec.image.digest,
                runtime_user=spec.runtime.user,
                resources=spec.resources,
                states=tuple(states),
                fixture_ready=wait.fixture_ready,
                stop_sent=stop_sent,
                kill_sent=kill_sent,
                wall_timed_out=wait.wall_timed_out,
                output_limit_exceeded=output_limit_exceeded,
                observed_output_bytes=observed,
                retained_output_bytes=retained,
                evidence_complete=evidence_complete,
                probe_succeeded=probe_succeeded,
                container_exit_code=container_exit_code,
                terminal_state=terminal_state,
                removed=True,
                residual_containers=residual_containers,
                residual_networks=residual_networks,
                residual_volumes=residual_volumes,
                sealed=True,
            )
            encoded = _json_bytes(evidence.document())
            next_retained = base_retained + len(encoded)
            if next_retained == retained:
                break
            retained = next_retained
        if len(encoded) > _CLEANUP_SEAL_RESERVE_BYTES:
            raise ContainerLifecycleError("cleanup seal exceeded its retained allocation")
        if retained > spec.resources.output_bytes:
            raise ContainerLifecycleError("retained attempt output exceeded its exact cap")
        _write_bytes_exclusive(root.attempt_root / "container-cleanup-seal.json", encoded)
        if _directory_bytes(root.attempt_root) != retained:
            raise ContainerLifecycleError("retained output changed while sealing cleanup")
        return evidence


@dataclass(frozen=True, slots=True)
class ContainerImageProvenance:
    base_image_reference: str
    base_image_index_digest: str
    base_image_platform_digest: str
    containerfile_sha256: str
    source_commit: str
    source_patch_sha256: str
    runtime_adaptation_sha256: str
    repository_build_assets_sha256: str
    uv_lock_sha256: str
    installed_package_manifest_sha256: str
    playwright_version: str
    chromium_revision: str
    chromium_executable_sha256: str
    browser_attempt_uuid: str
    browser_record_sha256: str
    browser_pre_removal_evidence_sha256: str
    browser_cleanup_seal_sha256: str
    final_image_id: str
    final_repo_digest: str | None
    final_repo_digest_status: str
    platform: ContainerPlatform

    def __post_init__(self) -> None:
        ImmutableImageReference(self.base_image_reference)
        for label, value in (
            ("base_image_index_digest", self.base_image_index_digest.removeprefix("sha256:")),
            ("base_image_platform_digest", self.base_image_platform_digest.removeprefix("sha256:")),
            ("containerfile_sha256", self.containerfile_sha256),
            ("source_patch_sha256", self.source_patch_sha256),
            ("runtime_adaptation_sha256", self.runtime_adaptation_sha256),
            ("repository_build_assets_sha256", self.repository_build_assets_sha256),
            ("uv_lock_sha256", self.uv_lock_sha256),
            ("installed_package_manifest_sha256", self.installed_package_manifest_sha256),
            ("chromium_executable_sha256", self.chromium_executable_sha256),
            ("browser_record_sha256", self.browser_record_sha256),
            (
                "browser_pre_removal_evidence_sha256",
                self.browser_pre_removal_evidence_sha256,
            ),
            ("browser_cleanup_seal_sha256", self.browser_cleanup_seal_sha256),
            ("final_image_id", self.final_image_id.removeprefix("sha256:")),
        ):
            _require_sha256(value, label)
        if _ATTEMPT_UUID.fullmatch(self.browser_attempt_uuid) is None:
            raise ContainerContractError("image provenance browser attempt UUID is invalid")
        _require_commit(self.source_commit, "source_commit")
        if self.source_commit != SIRA_UPSTREAM_COMMIT:
            raise ContainerContractError("image provenance source commit changed")
        if self.base_image_reference != BASE_IMAGE_REFERENCE:
            raise ContainerContractError("image provenance base image changed")
        if self.base_image_index_digest != BASE_IMAGE_INDEX_DIGEST:
            raise ContainerContractError("image provenance base index digest changed")
        if self.platform is not ContainerPlatform.LINUX_ARM64:
            raise ContainerContractError("image provenance platform changed")
        if self.base_image_platform_digest != BASE_IMAGE_ARM64_MANIFEST_DIGEST:
            raise ContainerContractError("image provenance arm64 manifest changed")
        if self.uv_lock_sha256 != UPSTREAM_UV_LOCK_SHA256:
            raise ContainerContractError("image provenance uv.lock hash changed")
        if self.playwright_version != PLAYWRIGHT_VERSION:
            raise ContainerContractError("image provenance Playwright version changed")
        if self.chromium_revision != CHROMIUM_REVISION:
            raise ContainerContractError("image provenance Chromium revision changed")
        if self.final_repo_digest is not None:
            ImmutableImageReference(self.final_repo_digest)
            if self.final_repo_digest_status != "observed":
                raise ContainerContractError("an observed repo digest requires observed status")
        elif self.final_repo_digest_status != "unavailable-local-build-not-pushed":
            raise ContainerContractError("missing local repo digest requires an explicit status")

    def document(self) -> dict[str, object]:
        return {
            "schema_version": CONTAINER_SCHEMA_VERSION,
            "base_image_reference": self.base_image_reference,
            "base_image_index_digest": self.base_image_index_digest,
            "base_image_platform_digest": self.base_image_platform_digest,
            "containerfile_sha256": self.containerfile_sha256,
            "source_commit": self.source_commit,
            "source_patch_sha256": self.source_patch_sha256,
            "runtime_adaptation_sha256": self.runtime_adaptation_sha256,
            "repository_build_assets_sha256": self.repository_build_assets_sha256,
            "uv_lock_sha256": self.uv_lock_sha256,
            "installed_package_manifest_sha256": self.installed_package_manifest_sha256,
            "playwright_version": self.playwright_version,
            "chromium_revision": self.chromium_revision,
            "chromium_executable_sha256": self.chromium_executable_sha256,
            "browser_attempt_uuid": self.browser_attempt_uuid,
            "browser_record_sha256": self.browser_record_sha256,
            "browser_pre_removal_evidence_sha256": (self.browser_pre_removal_evidence_sha256),
            "browser_cleanup_seal_sha256": self.browser_cleanup_seal_sha256,
            "final_image_id": self.final_image_id,
            "final_repo_digest": self.final_repo_digest,
            "final_repo_digest_status": self.final_repo_digest_status,
            "platform": self.platform.value,
        }


@dataclass(frozen=True, slots=True)
class PlatformCompatibility:
    platform: ContainerPlatform
    execution_path: str
    platform_manifest_digest: str
    compressed_base_bytes: int
    python_310_compatible: bool
    uv_frozen_eval_feasible: bool
    playwright_139_compatible: bool
    chromium_revision_1084_compatible: bool
    browsergym_compatible: bool
    expected_dependency_download_bytes: int
    expected_runtime_memory_bytes: int
    reproducibility_risks: tuple[str, ...]
    performance_risks: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha256(
            self.platform_manifest_digest.removeprefix("sha256:"),
            "platform_manifest_digest",
        )
        for name in (
            "compressed_base_bytes",
            "expected_dependency_download_bytes",
            "expected_runtime_memory_bytes",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ContainerContractError(f"{name} must be a positive observed/estimated value")

    def document(self) -> dict[str, object]:
        return {
            "platform": self.platform.value,
            "execution_path": self.execution_path,
            "platform_manifest_digest": self.platform_manifest_digest,
            "compressed_base_bytes": self.compressed_base_bytes,
            "python_310_compatible": self.python_310_compatible,
            "uv_frozen_eval_feasible": self.uv_frozen_eval_feasible,
            "playwright_139_compatible": self.playwright_139_compatible,
            "chromium_revision_1084_compatible": self.chromium_revision_1084_compatible,
            "browsergym_compatible": self.browsergym_compatible,
            "expected_dependency_download_bytes": self.expected_dependency_download_bytes,
            "expected_runtime_memory_bytes": self.expected_runtime_memory_bytes,
            "reproducibility_risks": list(self.reproducibility_risks),
            "performance_risks": list(self.performance_risks),
        }


@dataclass(frozen=True, slots=True)
class PlatformDecision:
    candidates: tuple[PlatformCompatibility, ...]
    chosen_platform: ContainerPlatform | None
    decision_status: str
    rationale: str

    def __post_init__(self) -> None:
        if {candidate.platform for candidate in self.candidates} != {
            ContainerPlatform.LINUX_ARM64,
            ContainerPlatform.LINUX_AMD64,
        }:
            raise ContainerContractError("platform decision must compare arm64 and amd64")
        if self.chosen_platform is None:
            if self.decision_status != "blocked":
                raise ContainerContractError("an unchosen platform must be explicitly blocked")
        elif self.decision_status != "chosen":
            raise ContainerContractError("a selected platform must have chosen status")
        else:
            selected = next(
                candidate
                for candidate in self.candidates
                if candidate.platform is self.chosen_platform
            )
            compatibility = (
                selected.python_310_compatible,
                selected.uv_frozen_eval_feasible,
                selected.playwright_139_compatible,
                selected.chromium_revision_1084_compatible,
                selected.browsergym_compatible,
            )
            if not all(compatibility):
                raise ContainerContractError(
                    "a platform cannot be chosen with unresolved compatibility evidence"
                )
        if not self.rationale.strip():
            raise ContainerContractError("platform decision rationale is required")

    def document(self) -> dict[str, object]:
        return {
            "schema_version": CONTAINER_SCHEMA_VERSION,
            "candidates": [candidate.document() for candidate in self.candidates],
            "chosen_platform": self.chosen_platform.value if self.chosen_platform else None,
            "decision_status": self.decision_status,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class ContainerBuildContract:
    repository_root: Path
    containerfile: Path
    source_patch: Path
    runtime_adaptation: Path
    target_platform: ContainerPlatform = ContainerPlatform.LINUX_ARM64
    base_image: str = BASE_IMAGE_REFERENCE
    source_commit: str = SIRA_UPSTREAM_COMMIT
    uv_lock_sha256: str = UPSTREAM_UV_LOCK_SHA256

    def __post_init__(self) -> None:
        ImmutableImageReference(self.base_image)
        _require_commit(self.source_commit, "source_commit")
        _require_sha256(self.uv_lock_sha256, "uv_lock_sha256")
        if self.target_platform is not ContainerPlatform.LINUX_ARM64:
            raise ContainerContractError("the Gate B2 build target must remain linux/arm64")
        if self.base_image != BASE_IMAGE_REFERENCE:
            raise ContainerContractError("the Gate B2 base image must remain exact")
        if self.source_commit != SIRA_UPSTREAM_COMMIT:
            raise ContainerContractError("the Gate B2 source commit must remain pinned")
        if self.uv_lock_sha256 != UPSTREAM_UV_LOCK_SHA256:
            raise ContainerContractError("the Gate B2 uv.lock hash must remain pinned")
        for label, path in (
            ("repository_root", self.repository_root),
            ("containerfile", self.containerfile),
            ("source_patch", self.source_patch),
            ("runtime_adaptation", self.runtime_adaptation),
        ):
            if not path.is_absolute() or path.resolve(strict=False) != path:
                raise ContainerContractError(f"{label} must be absolute and canonical")
        if any(
            self.repository_root != path and self.repository_root not in path.parents
            for path in (self.containerfile, self.source_patch, self.runtime_adaptation)
        ):
            raise ContainerContractError("build artifacts must be repository-owned")

    def artifact_hashes(self) -> Mapping[str, str]:
        files = {
            destination: file_sha256(source)
            for destination, source in sorted(self.staged_repository_files().items())
        }
        context_sha256 = hashlib.sha256(
            json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return MappingProxyType(
            {
                "containerfile_sha256": files["Containerfile"],
                "source_patch_sha256": files["sira-immutable-model-routing.patch"],
                "runtime_adaptation_sha256": files["sira_gate_a_runtime.py"],
                "repository_build_assets_sha256": context_sha256,
            }
        )

    def source_inspection_argv(
        self,
        git_executable: Path,
        source_checkout: Path,
    ) -> tuple[tuple[str, ...], ...]:
        if not git_executable.is_absolute() or not source_checkout.is_absolute():
            raise ContainerContractError("Git executable and source checkout must be absolute")
        prefix = (str(git_executable), "-C", str(source_checkout))
        return (
            (*prefix, "rev-parse", "HEAD"),
            (
                *prefix,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--ignored=matching",
            ),
        )

    def source_archive_argv(
        self,
        git_executable: Path,
        source_checkout: Path,
        archive_path: Path,
    ) -> tuple[str, ...]:
        if not all(path.is_absolute() for path in (git_executable, source_checkout, archive_path)):
            raise ContainerContractError("source-archive paths must be absolute")
        return (
            str(git_executable),
            "-C",
            str(source_checkout),
            "archive",
            "--format=tar",
            "--output",
            str(archive_path),
            self.source_commit,
        )

    def staged_repository_files(self) -> Mapping[str, Path]:
        """Exact repository-owned files copied into a fresh external build context."""

        container_root = self.containerfile.parent
        return MappingProxyType(
            {
                "Containerfile": self.containerfile,
                ".dockerignore": container_root / ".dockerignore",
                "sira-immutable-model-routing.patch": self.source_patch,
                "sira_gate_a_runtime.py": self.runtime_adaptation,
                "container_entrypoint.py": container_root / "container_entrypoint.py",
                "fixtures/adversarial_containment.py": (
                    container_root / "fixtures/adversarial_containment.py"
                ),
                "fixtures/browser_preflight.py": container_root / "fixtures/browser_preflight.py",
                "fixtures/secret_probe.py": container_root / "fixtures/secret_probe.py",
                "fixtures/static.html": container_root / "fixtures/static.html",
            }
        )

    def build_argv(
        self,
        docker_executable: Path,
        *,
        staged_context: Path,
        local_tag: str,
    ) -> tuple[str, ...]:
        if not docker_executable.is_absolute() or not staged_context.is_absolute():
            raise ContainerContractError("build executable and context must be absolute")
        if not local_tag.startswith("giclab/sira-smoke:t07-gate-b2-"):
            raise ContainerContractError("local build tag must be Gate B2 scoped")
        hashes = self.artifact_hashes()
        return (
            str(docker_executable),
            "buildx",
            "build",
            "--load",
            "--platform",
            self.target_platform.value,
            "--pull=false",
            "--no-cache",
            "--network=default",
            "--provenance=false",
            "--sbom=false",
            "--file",
            str(staged_context / "Containerfile"),
            "--tag",
            local_tag,
            "--label",
            f"{CONTAINER_LABEL_PREFIX}.source-commit={self.source_commit}",
            "--label",
            f"{CONTAINER_LABEL_PREFIX}.source-patch-sha256={hashes['source_patch_sha256']}",
            "--label",
            f"{CONTAINER_LABEL_PREFIX}.containerfile-sha256={hashes['containerfile_sha256']}",
            "--label",
            f"{CONTAINER_LABEL_PREFIX}.runtime-adaptation-sha256={hashes['runtime_adaptation_sha256']}",
            "--label",
            (
                f"{CONTAINER_LABEL_PREFIX}.repository-build-assets-sha256="
                f"{hashes['repository_build_assets_sha256']}"
            ),
            "--label",
            f"{CONTAINER_LABEL_PREFIX}.base-image-index-digest={BASE_IMAGE_INDEX_DIGEST}",
            "--label",
            (
                f"{CONTAINER_LABEL_PREFIX}.base-image-platform-digest="
                f"{BASE_IMAGE_ARM64_MANIFEST_DIGEST}"
            ),
            "--label",
            f"{CONTAINER_LABEL_PREFIX}.uv-lock-sha256={self.uv_lock_sha256}",
            "--label",
            f"{CONTAINER_LABEL_PREFIX}.platform={self.target_platform.value}",
            "--label",
            f"{CONTAINER_LABEL_PREFIX}.playwright-version={PLAYWRIGHT_VERSION}",
            "--label",
            f"{CONTAINER_LABEL_PREFIX}.chromium-revision={CHROMIUM_REVISION}",
            str(staged_context),
        )


@dataclass(frozen=True, slots=True)
class LocalImageIdentity:
    local_tag: str
    final_image_id: str
    repo_digests: tuple[str, ...]
    platform: ContainerPlatform
    source_commit: str
    source_patch_sha256: str
    containerfile_sha256: str
    runtime_adaptation_sha256: str
    repository_build_assets_sha256: str
    base_image_index_digest: str
    base_image_platform_digest: str
    uv_lock_sha256: str
    playwright_version: str
    chromium_revision: str

    def __post_init__(self) -> None:
        ImmutableImageReference(self.final_image_id)
        if not self.local_tag.startswith("giclab/sira-smoke:t07-gate-b2-"):
            raise ContainerContractError("local image tag is outside Gate B2")
        _require_commit(self.source_commit, "source_commit")
        _require_sha256(self.source_patch_sha256, "source_patch_sha256")
        _require_sha256(self.containerfile_sha256, "containerfile_sha256")
        _require_sha256(
            self.repository_build_assets_sha256,
            "repository_build_assets_sha256",
        )
        _require_sha256(self.runtime_adaptation_sha256, "runtime_adaptation_sha256")
        _require_sha256(
            self.base_image_index_digest.removeprefix("sha256:"),
            "base_image_index_digest",
        )
        _require_sha256(
            self.base_image_platform_digest.removeprefix("sha256:"),
            "base_image_platform_digest",
        )
        _require_sha256(self.uv_lock_sha256, "uv_lock_sha256")
        if (
            self.platform is not ContainerPlatform.LINUX_ARM64
            or self.source_commit != SIRA_UPSTREAM_COMMIT
            or self.base_image_index_digest != BASE_IMAGE_INDEX_DIGEST
            or self.base_image_platform_digest != BASE_IMAGE_ARM64_MANIFEST_DIGEST
            or self.uv_lock_sha256 != UPSTREAM_UV_LOCK_SHA256
            or self.playwright_version != PLAYWRIGHT_VERSION
            or self.chromium_revision != CHROMIUM_REVISION
        ):
            raise ContainerContractError("local image identity drifted from the Gate B2 pins")
        for digest in self.repo_digests:
            ImmutableImageReference(digest)

    def document(self) -> dict[str, object]:
        return {
            "schema_version": CONTAINER_SCHEMA_VERSION,
            "local_tag": self.local_tag,
            "final_image_id": self.final_image_id,
            "repo_digests": list(self.repo_digests),
            "platform": self.platform.value,
            "source_commit": self.source_commit,
            "source_patch_sha256": self.source_patch_sha256,
            "containerfile_sha256": self.containerfile_sha256,
            "runtime_adaptation_sha256": self.runtime_adaptation_sha256,
            "repository_build_assets_sha256": self.repository_build_assets_sha256,
            "base_image_index_digest": self.base_image_index_digest,
            "base_image_platform_digest": self.base_image_platform_digest,
            "uv_lock_sha256": self.uv_lock_sha256,
            "playwright_version": self.playwright_version,
            "chromium_revision": self.chromium_revision,
        }


def _default_build_contract(repository_root: Path) -> ContainerBuildContract:
    return ContainerBuildContract(
        repository_root=repository_root,
        containerfile=repository_root / "containers/sira-smoke/Containerfile",
        source_patch=(repository_root / "containers/sira-smoke/sira-immutable-model-routing.patch"),
        runtime_adaptation=repository_root / "src/giclab/harness/sira_gate_a_runtime.py",
    )


def verify_exact_file(path: Path, *, expected_bytes: int, expected_sha256: str) -> None:
    """Fail closed on one authorized artifact's exact size and digest."""

    _require_sha256(expected_sha256, "expected file SHA-256")
    if type(expected_bytes) is not int or expected_bytes <= 0:
        raise ContainerContractError("expected file size must be positive")
    if (
        not path.is_absolute()
        or path.resolve(strict=False) != path
        or path.is_symlink()
        or not path.is_file()
    ):
        raise ContainerContractError("verified artifact must be a canonical regular file")
    if path.stat().st_size != expected_bytes or file_sha256(path) != expected_sha256:
        raise ContainerContractError("authorized artifact size or SHA-256 changed")


def _source_tree_manifest(root: Path, *, exclude_git: bool = False) -> dict[str, str]:
    """Hash a tree without following links so staged source can be equality-checked."""

    manifest: dict[str, str] = {}

    def visit(directory: Path) -> None:
        for entry in sorted(directory.iterdir(), key=lambda value: value.name):
            relative = entry.relative_to(root).as_posix()
            if exclude_git and relative == ".git":
                continue
            metadata = entry.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                manifest[relative] = "symlink:" + os.readlink(entry)
            elif stat.S_ISDIR(metadata.st_mode):
                manifest[relative + "/"] = "directory"
                visit(entry)
            elif stat.S_ISREG(metadata.st_mode):
                manifest[relative] = "sha256:" + file_sha256(entry)
            else:
                raise ContainerContractError("build source tree contains a special file")

    visit(root)
    return manifest


def verify_staged_build_context(
    *,
    build_contract: ContainerBuildContract,
    source_checkout: Path,
    staged_context: Path,
) -> str:
    """Prove the exact copied inputs and pinned source tree consumed by buildx."""

    for label, path in (
        ("source checkout", source_checkout),
        ("staged context", staged_context),
    ):
        if (
            not path.is_absolute()
            or path.resolve(strict=False) != path
            or path.is_symlink()
            or not path.is_dir()
        ):
            raise ContainerContractError(f"{label} must be a canonical ordinary directory")
    staged_files = build_contract.staged_repository_files()
    for relative, source in staged_files.items():
        destination = staged_context / relative
        if destination.is_symlink() or not destination.is_file():
            raise ContainerContractError("staged repository build input is missing")
        if file_sha256(destination) != file_sha256(source):
            raise ContainerContractError("staged repository build input hash changed")
        if stat.S_IMODE(destination.stat().st_mode) != 0o444:
            raise ContainerContractError("staged repository build input must be mode 0444")
    wheel = staged_context / "vendor" / UV_WHEEL_FILENAME
    verify_exact_file(
        wheel,
        expected_bytes=UV_WHEEL_BYTES,
        expected_sha256=UV_WHEEL_SHA256,
    )
    upstream = staged_context / "upstream"
    if upstream.is_symlink() or not upstream.is_dir():
        raise ContainerContractError("staged upstream source tree is missing")
    if _source_tree_manifest(source_checkout, exclude_git=True) != _source_tree_manifest(upstream):
        raise ContainerContractError("staged upstream tree differs from the pinned checkout")
    if file_sha256(upstream / "uv.lock") != UPSTREAM_UV_LOCK_SHA256:
        raise ContainerContractError("staged upstream uv.lock hash changed")
    allowed_top_level = {
        "Containerfile",
        ".dockerignore",
        "sira-immutable-model-routing.patch",
        "sira_gate_a_runtime.py",
        "container_entrypoint.py",
        "fixtures",
        "upstream",
        "vendor",
    }
    if {path.name for path in staged_context.iterdir()} != allowed_top_level:
        raise ContainerContractError("staged build context contains an unapproved top-level input")
    evidence = {
        "schema_version": CONTAINER_SCHEMA_VERSION,
        "artifact_hashes": dict(build_contract.artifact_hashes()),
        "source_commit": build_contract.source_commit,
        "staged_source_equals_checkout": True,
        "uv_wheel_sha256": UV_WHEEL_SHA256,
        "uv_lock_sha256": UPSTREAM_UV_LOCK_SHA256,
    }
    return hashlib.sha256(_json_bytes(evidence)).hexdigest()


def capture_local_image_identity(
    *,
    local_tag: str,
    build_contract: ContainerBuildContract,
    renderer: DockerCommandRenderer,
    runner: DockerCommandRunner,
) -> LocalImageIdentity:
    """Resolve a mutable local build tag once and verify its immutable build labels."""

    result = runner.run(renderer.inspect_image(local_tag), timeout_seconds=30)
    _require_success(result, "image inspect")
    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ContainerLifecycleError("image inspect did not return JSON") from exc
    if not isinstance(decoded, list) or len(decoded) != 1 or not isinstance(decoded[0], Mapping):
        raise ContainerLifecycleError("image inspect must identify exactly one image")
    image = decoded[0]
    image_id = image.get("Id")
    if not isinstance(image_id, str):
        raise ContainerLifecycleError("image inspect omitted Id")
    ImmutableImageReference(image_id)
    if image.get("Os") != "linux" or image.get("Architecture") != "arm64":
        raise ContainerLifecycleError("image platform is not the chosen linux/arm64 target")
    config = image.get("Config")
    labels = config.get("Labels") if isinstance(config, Mapping) else None
    if not isinstance(labels, Mapping):
        raise ContainerLifecycleError("image inspect omitted build labels")
    environment = config.get("Env", []) if isinstance(config, Mapping) else []
    if not isinstance(environment, list) or any(
        not isinstance(item, str) or looks_secret_name(item.partition("=")[0])
        for item in environment
    ):
        raise ContainerLifecycleError("image configuration contains an undeclared credential field")
    hashes = build_contract.artifact_hashes()
    expected_labels = {
        f"{CONTAINER_LABEL_PREFIX}.source-commit": build_contract.source_commit,
        f"{CONTAINER_LABEL_PREFIX}.source-patch-sha256": hashes["source_patch_sha256"],
        f"{CONTAINER_LABEL_PREFIX}.containerfile-sha256": hashes["containerfile_sha256"],
        f"{CONTAINER_LABEL_PREFIX}.runtime-adaptation-sha256": hashes["runtime_adaptation_sha256"],
        f"{CONTAINER_LABEL_PREFIX}.repository-build-assets-sha256": (
            hashes["repository_build_assets_sha256"]
        ),
        f"{CONTAINER_LABEL_PREFIX}.base-image-index-digest": BASE_IMAGE_INDEX_DIGEST,
        f"{CONTAINER_LABEL_PREFIX}.base-image-platform-digest": (BASE_IMAGE_ARM64_MANIFEST_DIGEST),
        f"{CONTAINER_LABEL_PREFIX}.uv-lock-sha256": UPSTREAM_UV_LOCK_SHA256,
        f"{CONTAINER_LABEL_PREFIX}.platform": ContainerPlatform.LINUX_ARM64.value,
        f"{CONTAINER_LABEL_PREFIX}.playwright-version": PLAYWRIGHT_VERSION,
        f"{CONTAINER_LABEL_PREFIX}.chromium-revision": CHROMIUM_REVISION,
    }
    if any(labels.get(key) != value for key, value in expected_labels.items()):
        raise ContainerLifecycleError("image build labels do not match the repository contract")
    raw_repo_digests = image.get("RepoDigests", [])
    if not isinstance(raw_repo_digests, list) or any(
        not isinstance(item, str) for item in raw_repo_digests
    ):
        raise ContainerLifecycleError("image RepoDigests has an invalid shape")
    repo_digests = tuple(str(item) for item in raw_repo_digests)
    return LocalImageIdentity(
        local_tag=local_tag,
        final_image_id=image_id,
        repo_digests=repo_digests,
        platform=ContainerPlatform.LINUX_ARM64,
        source_commit=build_contract.source_commit,
        source_patch_sha256=hashes["source_patch_sha256"],
        containerfile_sha256=hashes["containerfile_sha256"],
        runtime_adaptation_sha256=hashes["runtime_adaptation_sha256"],
        repository_build_assets_sha256=hashes["repository_build_assets_sha256"],
        base_image_index_digest=BASE_IMAGE_INDEX_DIGEST,
        base_image_platform_digest=BASE_IMAGE_ARM64_MANIFEST_DIGEST,
        uv_lock_sha256=UPSTREAM_UV_LOCK_SHA256,
        playwright_version=PLAYWRIGHT_VERSION,
        chromium_revision=CHROMIUM_REVISION,
    )


def load_local_image_identity(
    path: Path,
    *,
    build_contract: ContainerBuildContract,
) -> LocalImageIdentity:
    if path.is_symlink() or not path.is_file():
        raise ContainerContractError("image identity record must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContainerContractError("image identity record is unreadable") from exc
    if not isinstance(value, Mapping):
        raise ContainerContractError("image identity record must be an object")
    repo_digests = value.get("repo_digests")
    if not isinstance(repo_digests, list) or any(
        not isinstance(item, str) for item in repo_digests
    ):
        raise ContainerContractError("image identity repo_digests is invalid")
    try:
        identity = LocalImageIdentity(
            local_tag=str(value["local_tag"]),
            final_image_id=str(value["final_image_id"]),
            repo_digests=tuple(repo_digests),
            platform=ContainerPlatform(str(value["platform"])),
            source_commit=str(value["source_commit"]),
            source_patch_sha256=str(value["source_patch_sha256"]),
            containerfile_sha256=str(value["containerfile_sha256"]),
            runtime_adaptation_sha256=str(value["runtime_adaptation_sha256"]),
            repository_build_assets_sha256=str(value["repository_build_assets_sha256"]),
            base_image_index_digest=str(value["base_image_index_digest"]),
            base_image_platform_digest=str(value["base_image_platform_digest"]),
            uv_lock_sha256=str(value["uv_lock_sha256"]),
            playwright_version=str(value["playwright_version"]),
            chromium_revision=str(value["chromium_revision"]),
        )
    except (KeyError, ValueError) as exc:
        raise ContainerContractError("image identity record is incomplete") from exc
    expected = build_contract.artifact_hashes()
    if (
        identity.source_commit != build_contract.source_commit
        or identity.source_patch_sha256 != expected["source_patch_sha256"]
        or identity.containerfile_sha256 != expected["containerfile_sha256"]
        or identity.runtime_adaptation_sha256 != expected["runtime_adaptation_sha256"]
        or identity.repository_build_assets_sha256 != expected["repository_build_assets_sha256"]
        or identity.platform is not build_contract.target_platform
    ):
        raise ContainerContractError("image identity record drifted from the build contract")
    return identity


def assemble_image_provenance(
    *,
    image: LocalImageIdentity,
    browser_attempt_uuid: str,
    browser_record_path: Path,
    browser_pre_removal_evidence_path: Path,
    browser_cleanup_seal_path: Path,
) -> ContainerImageProvenance:
    """Bind image provenance to one successful, sealed browser preflight attempt."""

    if _ATTEMPT_UUID.fullmatch(browser_attempt_uuid) is None:
        raise ContainerContractError("browser provenance attempt UUID is invalid")
    expected_attempt_root_name = f"browser-preflight-{browser_attempt_uuid}"
    evidence_paths = (
        browser_record_path,
        browser_pre_removal_evidence_path,
        browser_cleanup_seal_path,
    )
    if any(
        path.is_symlink()
        or not path.is_file()
        or not path.is_absolute()
        or path.resolve(strict=True) != path
        for path in evidence_paths
    ):
        raise ContainerContractError("browser provenance inputs must be canonical regular files")
    if (
        browser_record_path.name != "browser-preflight.json"
        or browser_pre_removal_evidence_path.name != "container-evidence-before-removal.json"
        or browser_cleanup_seal_path.name != "container-cleanup-seal.json"
        or len({path.parent for path in evidence_paths}) != 1
        or browser_record_path.parent.name != expected_attempt_root_name
    ):
        raise ContainerContractError(
            "browser provenance inputs must be the exact files from one attempt root"
        )

    decoded: list[Mapping[str, Any]] = []
    encoded_inputs: list[bytes] = []
    for label, path in zip(
        ("browser record", "pre-removal evidence", "cleanup seal"),
        evidence_paths,
        strict=True,
    ):
        try:
            encoded = path.read_bytes()
            value = json.loads(encoded)
        except (OSError, json.JSONDecodeError) as exc:
            raise ContainerContractError(f"{label} is unreadable") from exc
        if not isinstance(value, Mapping):
            raise ContainerContractError(f"{label} must be an object")
        encoded_inputs.append(encoded)
        decoded.append(value)
    browser, pre_removal, cleanup = decoded

    if (
        browser.get("playwright_version") != PLAYWRIGHT_VERSION
        or browser.get("chromium_revision") != CHROMIUM_REVISION
        or browser.get("browser_actions") != 1
        or browser.get("screenshot_captures") != 1
        or browser.get("browser_closed") is not True
    ):
        raise ContainerContractError("browser provenance record changed its pinned identity")
    package_sha = browser.get("installed_package_manifest_sha256")
    chromium_sha = browser.get("chromium_executable_sha256")
    if not isinstance(package_sha, str) or not isinstance(chromium_sha, str):
        raise ContainerContractError("browser provenance record omitted required hashes")
    _require_sha256(package_sha, "installed_package_manifest_sha256")
    _require_sha256(chromium_sha, "chromium_executable_sha256")

    expected_image = image.final_image_id
    expected_container_id = cleanup.get("container_id")
    if (
        cleanup.get("schema_version") != CONTAINER_SCHEMA_VERSION
        or cleanup.get("fixture") != ContainerFixture.BROWSER_PREFLIGHT.value
        or cleanup.get("attempt_uuid") != browser_attempt_uuid
        or cleanup.get("platform") != ContainerPlatform.LINUX_ARM64.value
        or cleanup.get("image_reference") != expected_image
        or cleanup.get("image_digest") != expected_image
        or cleanup.get("fixture_ready") is not True
        or cleanup.get("evidence_complete") is not True
        or cleanup.get("probe_succeeded") is not True
        or cleanup.get("output_limit_exceeded") is not False
        or cleanup.get("removed") is not True
        or cleanup.get("sealed") is not True
        or cleanup.get("residual_containers") != []
        or cleanup.get("residual_networks") != []
        or cleanup.get("residual_volumes") != []
        or not isinstance(expected_container_id, str)
        or _CONTAINER_ID.fullmatch(expected_container_id) is None
    ):
        raise ContainerContractError(
            "browser cleanup seal is not a successful attempt on the exact image"
        )
    lifecycle_states = cleanup.get("lifecycle_states")
    if not isinstance(lifecycle_states, list) or lifecycle_states[-1:] != [
        LifecycleState.SEALED.value
    ]:
        raise ContainerContractError("browser cleanup seal omitted its terminal lifecycle")
    if (
        pre_removal.get("schema_version") != CONTAINER_SCHEMA_VERSION
        or pre_removal.get("evidence_complete") is not True
        or pre_removal.get("container_id") != expected_container_id
        or pre_removal.get("fixture_record") != browser
    ):
        raise ContainerContractError(
            "browser pre-removal evidence does not bind the exact fixture record"
        )
    for field in ("inspect_created", "inspect_before_removal"):
        inspect = pre_removal.get(field)
        if not isinstance(inspect, Mapping):
            raise ContainerContractError("browser pre-removal inspect evidence is missing")
        config = inspect.get("Config")
        labels = config.get("Labels") if isinstance(config, Mapping) else None
        if (
            inspect.get("Id") != expected_container_id
            or inspect.get("Image") != expected_image
            or not isinstance(labels, Mapping)
            or labels.get(f"{CONTAINER_LABEL_PREFIX}.attempt-uuid") != browser_attempt_uuid
            or labels.get(f"{CONTAINER_LABEL_PREFIX}.image-digest") != expected_image
        ):
            raise ContainerContractError(
                "browser pre-removal inspect is not bound to the attempt and image"
            )
    if len(image.repo_digests) > 1:
        raise ContainerContractError("multiple final repo digests require an explicit decision")
    repo_digest = image.repo_digests[0] if image.repo_digests else None
    return ContainerImageProvenance(
        base_image_reference=BASE_IMAGE_REFERENCE,
        base_image_index_digest=image.base_image_index_digest,
        base_image_platform_digest=image.base_image_platform_digest,
        containerfile_sha256=image.containerfile_sha256,
        source_commit=image.source_commit,
        source_patch_sha256=image.source_patch_sha256,
        runtime_adaptation_sha256=image.runtime_adaptation_sha256,
        repository_build_assets_sha256=image.repository_build_assets_sha256,
        uv_lock_sha256=image.uv_lock_sha256,
        installed_package_manifest_sha256=package_sha,
        playwright_version=image.playwright_version,
        chromium_revision=image.chromium_revision,
        chromium_executable_sha256=chromium_sha,
        browser_attempt_uuid=browser_attempt_uuid,
        browser_record_sha256=hashlib.sha256(encoded_inputs[0]).hexdigest(),
        browser_pre_removal_evidence_sha256=hashlib.sha256(encoded_inputs[1]).hexdigest(),
        browser_cleanup_seal_sha256=hashlib.sha256(encoded_inputs[2]).hexdigest(),
        final_image_id=image.final_image_id,
        final_repo_digest=repo_digest,
        final_repo_digest_status=(
            "observed" if repo_digest is not None else "unavailable-local-build-not-pushed"
        ),
        platform=image.platform,
    )


def fixture_attempt_spec(
    *,
    fixture: ContainerFixture,
    image: LocalImageIdentity,
    root: AttemptRootContract,
    repository_commit: str,
    attempt_uuid: str,
    authorization_reference: str,
    secret_file: Path | None = None,
) -> ContainerAttemptSpec:
    commands = {
        ContainerFixture.ADVERSARIAL_CONTAINMENT: (
            "/opt/sira/.venv/bin/python",
            "/opt/giclab/fixtures/adversarial_containment.py",
        ),
        ContainerFixture.BROWSER_PREFLIGHT: (
            "/opt/sira/.venv/bin/python",
            "/opt/giclab/fixtures/browser_preflight.py",
        ),
        ContainerFixture.DUMMY_SECRET_PREFLIGHT: (
            "/opt/sira/.venv/bin/python",
            "/opt/giclab/container_entrypoint.py",
            "--",
            "/opt/sira/.venv/bin/python",
            "/opt/giclab/fixtures/secret_probe.py",
        ),
    }
    if fixture not in commands:
        raise ContainerContractError("the Gate B2 CLI permits only synthetic fixtures")
    mounts = [
        BindMount(
            source=root.attempt_root,
            target=CONTAINER_ATTEMPT_TARGET,
            purpose=MountPurpose.ATTEMPT_ROOT,
            read_only=False,
        )
    ]
    if fixture is ContainerFixture.DUMMY_SECRET_PREFLIGHT:
        if secret_file is None:
            raise ContainerContractError("dummy-secret preflight requires a secret file")
        mounts.append(
            BindMount(
                source=secret_file,
                target=CONTAINER_SECRET_TARGET,
                purpose=MountPurpose.SECRET_FILE,
                read_only=True,
            )
        )
    elif secret_file is not None:
        raise ContainerContractError("secret file is permitted only for the dummy preflight")
    limits = (
        browser_preflight_limits()
        if fixture is ContainerFixture.BROWSER_PREFLIGHT
        else synthetic_limits()
    )
    condition = {
        ContainerFixture.ADVERSARIAL_CONTAINMENT: "T07-B2-CONTAINMENT",
        ContainerFixture.BROWSER_PREFLIGHT: "T07-B2-BROWSER",
        ContainerFixture.DUMMY_SECRET_PREFLIGHT: "T07-B2-SECRET",
    }[fixture]
    ready_artifact = {
        ContainerFixture.ADVERSARIAL_CONTAINMENT: "adversarial-reparented.json",
        ContainerFixture.BROWSER_PREFLIGHT: "browser-preflight.json",
        ContainerFixture.DUMMY_SECRET_PREFLIGHT: "dummy-secret-probe.json",
    }[fixture]
    return ContainerAttemptSpec(
        identity=ContainerAttemptIdentity(
            experiment_id="EXP-0001",
            profile_plan_id="PLAN-EXP0001-SMOKE",
            condition=condition,
            attempt=1,
            attempt_uuid=attempt_uuid,
            repository_commit=repository_commit,
            source_commit=SIRA_UPSTREAM_COMMIT,
            authorization_reference=authorization_reference,
        ),
        image=ImmutableImageReference(image.final_image_id),
        platform=ContainerPlatform.LINUX_ARM64,
        fixture=fixture,
        resources=limits,
        mounts=tuple(mounts),
        command=commands[fixture],
        ready_artifact=ready_artifact,
        runtime=ContainerRuntimeOptions(user=f"{os.getuid()}:{os.getgid()}"),
    )


def assert_dummy_secret_absent(
    dummy_secret: str,
    *,
    documents: Sequence[object] = (),
    retained_paths: Sequence[Path] = (),
) -> None:
    """Test-only canary scan across rendered and retained surfaces."""

    scrubber = ExactCredentialScrubber((dummy_secret,))
    for index, document in enumerate(documents):
        scrubber.assert_json(document, label=f"dummy-secret document {index}")
    for path in retained_paths:
        scrubber.assert_file(path, label=f"dummy-secret retained path {path.name}")


def write_dummy_secret_file(path: Path) -> None:
    """Create the public Gate B2 canary with no value-bearing argv or stdout."""

    if not path.is_absolute() or path.resolve(strict=False) != path:
        raise ContainerContractError("dummy-secret path must be absolute and canonical")
    if path.parent.resolve(strict=True) != path.parent or path.exists() or path.is_symlink():
        raise ContainerContractError("dummy-secret output must be fresh under a canonical parent")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write((DUMMY_SECRET_CANARY + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        with suppress(OSError):
            os.close(descriptor)
        raise


def synthetic_limits() -> ContainerResourceLimits:
    return ContainerResourceLimits(
        cpu_millis=1_000,
        memory_bytes=512 * 1024**2,
        pids=64,
        wall_seconds=30,
        output_bytes=16 * 1024**2,
        shm_bytes=64 * 1024**2,
        tmpfs_bytes=64 * 1024**2,
        stop_grace_seconds=1,
    )


def browser_preflight_limits() -> ContainerResourceLimits:
    return ContainerResourceLimits(
        cpu_millis=2_000,
        memory_bytes=2 * 1024**3,
        pids=256,
        wall_seconds=60,
        output_bytes=32 * 1024**2,
        shm_bytes=1024**3,
        tmpfs_bytes=128 * 1024**2,
        stop_grace_seconds=2,
    )


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="T07 Gate B2 container fixture control plane")
    subparsers = parser.add_subparsers(dest="operation", required=True)

    dummy = subparsers.add_parser("write-dummy-secret")
    dummy.add_argument("--output", type=Path, required=True)

    verify = subparsers.add_parser("verify-file")
    verify.add_argument("--path", type=Path, required=True)
    verify.add_argument("--bytes", type=int, required=True)
    verify.add_argument("--sha256", required=True)

    verify_context = subparsers.add_parser("verify-build-context")
    verify_context.add_argument("--repository-root", type=Path, required=True)
    verify_context.add_argument("--source-checkout", type=Path, required=True)
    verify_context.add_argument("--staged-context", type=Path, required=True)

    materialize = subparsers.add_parser("execute-materialization-plan")
    materialize.add_argument("--plan", type=Path, required=True)
    materialize.add_argument("--plan-sha256", required=True)
    materialize.add_argument("--ledger", type=Path, required=True)

    capture = subparsers.add_parser("capture-image-identity")
    capture.add_argument("--repository-root", type=Path, required=True)
    capture.add_argument("--runtime", type=Path, required=True)
    capture.add_argument("--local-tag", required=True)
    capture.add_argument("--output", type=Path, required=True)

    provenance = subparsers.add_parser("assemble-image-provenance")
    provenance.add_argument("--repository-root", type=Path, required=True)
    provenance.add_argument("--image-identity", type=Path, required=True)
    provenance.add_argument("--browser-attempt-uuid", required=True)
    provenance.add_argument("--browser-record", type=Path, required=True)
    provenance.add_argument("--browser-pre-removal-evidence", type=Path, required=True)
    provenance.add_argument("--browser-cleanup-seal", type=Path, required=True)
    provenance.add_argument("--output", type=Path, required=True)

    execute = subparsers.add_parser("execute-fixture")
    execute.add_argument("--repository-root", type=Path, required=True)
    execute.add_argument("--runtime", type=Path, required=True)
    execute.add_argument("--image-identity", type=Path, required=True)
    execute.add_argument("--owned-base", type=Path, required=True)
    execute.add_argument("--repository-commit", required=True)
    execute.add_argument("--attempt-uuid", required=True)
    execute.add_argument("--authorization-reference", required=True)
    execute.add_argument(
        "--fixture",
        type=ContainerFixture,
        choices=(
            ContainerFixture.ADVERSARIAL_CONTAINMENT,
            ContainerFixture.BROWSER_PREFLIGHT,
            ContainerFixture.DUMMY_SECRET_PREFLIGHT,
        ),
        required=True,
    )
    execute.add_argument("--secret-file", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _cli_parser().parse_args(argv)
    if args.operation == "write-dummy-secret":
        write_dummy_secret_file(args.output.resolve(strict=False))
        return 0
    if args.operation == "verify-file":
        verify_exact_file(
            args.path.resolve(strict=True),
            expected_bytes=args.bytes,
            expected_sha256=args.sha256,
        )
        print("verified")
        return 0
    if args.operation == "execute-materialization-plan":
        plan = load_materialization_plan(
            args.plan.resolve(strict=True),
            expected_sha256=args.plan_sha256,
        )
        ledger = BoundedMaterializationExecutor(
            runner=SubprocessMaterializationCommandRunner()
        ).execute(plan, ledger_path=args.ledger.resolve(strict=False))
        print(json.dumps(ledger, sort_keys=True))
        return 0
    repository_root = args.repository_root.resolve(strict=True)
    build_contract = _default_build_contract(repository_root)
    if args.operation == "verify-build-context":
        digest = verify_staged_build_context(
            build_contract=build_contract,
            source_checkout=args.source_checkout.resolve(strict=True),
            staged_context=args.staged_context.resolve(strict=True),
        )
        print(digest)
        return 0
    if args.operation == "assemble-image-provenance":
        image = load_local_image_identity(
            args.image_identity.resolve(strict=True),
            build_contract=build_contract,
        )
        provenance = assemble_image_provenance(
            image=image,
            browser_attempt_uuid=args.browser_attempt_uuid,
            browser_record_path=args.browser_record.resolve(strict=True),
            browser_pre_removal_evidence_path=(
                args.browser_pre_removal_evidence.resolve(strict=True)
            ),
            browser_cleanup_seal_path=args.browser_cleanup_seal.resolve(strict=True),
        )
        output = args.output.resolve(strict=False)
        if output.parent.resolve(strict=True) != output.parent:
            raise ContainerContractError("image provenance output parent must be canonical")
        _write_json_exclusive(output, provenance.document())
        return 0

    runtime = args.runtime.resolve(strict=True)
    renderer = DockerCommandRenderer(runtime)
    runner = SubprocessDockerCommandRunner()
    if args.operation == "capture-image-identity":
        identity = capture_local_image_identity(
            local_tag=args.local_tag,
            build_contract=build_contract,
            renderer=renderer,
            runner=runner,
        )
        output = args.output.resolve(strict=False)
        if output.parent.resolve(strict=True) != output.parent:
            raise ContainerContractError("image identity output parent must be canonical")
        _write_json_exclusive(output, identity.document())
        return 0

    image = load_local_image_identity(
        args.image_identity.resolve(strict=True),
        build_contract=build_contract,
    )
    owned_base = args.owned_base.resolve(strict=True)
    fixture = args.fixture
    assert isinstance(fixture, ContainerFixture)
    attempt_root = owned_base / f"{fixture.value}-{args.attempt_uuid}"
    root = AttemptRootContract(owned_base=owned_base, attempt_root=attempt_root)
    secret_file = args.secret_file.resolve(strict=True) if args.secret_file is not None else None
    spec = fixture_attempt_spec(
        fixture=fixture,
        image=image,
        root=root,
        repository_commit=args.repository_commit,
        attempt_uuid=args.attempt_uuid,
        authorization_reference=args.authorization_reference,
        secret_file=secret_file,
    )
    executor = DockerAttemptExecutor(renderer=renderer, runner=runner)
    evidence: ContainerLifecycleEvidence | None = None
    try:
        evidence = executor.execute(spec, root, repository_root=repository_root)
    finally:
        if fixture is ContainerFixture.DUMMY_SECRET_PREFLIGHT:
            assert_dummy_secret_absent(
                DUMMY_SECRET_CANARY,
                documents=(
                    renderer.create(spec),
                    dict(spec.identity.labels(spec.image.digest)),
                    image.document(),
                    None if evidence is None else evidence.document(),
                ),
                retained_paths=tuple(path for path in attempt_root.rglob("*") if path.is_file()),
            )
    assert evidence is not None
    print(json.dumps(evidence.document(), sort_keys=True))
    return 0 if evidence.probe_succeeded else 2


if __name__ == "__main__":
    raise SystemExit(main())
