"""Effect-neutral low-level contracts for the shared Category 3 production assembly.

This module defines capability surfaces; it performs no provider, host, browser,
scientific, or credential-bearing operation.  A package-specific module may
implement these protocols only after an external grant validates one exact
``EffectAuthorizationContext``.  The shared package can mint shadow authority only.
"""

from __future__ import annotations

import builtins
import hashlib
import inspect
import json
import math
import os
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import TYPE_CHECKING, Final, Protocol, TypeVar, cast, runtime_checkable

from giclab.harness.sira_gate_a import (
    ProviderBudgetCaps,
    ProviderRequest,
    ProviderResponseUsage,
)
from giclab.harness.t09_model_metadata_receipt import ModelMetadataResponse

if TYPE_CHECKING:
    from giclab.harness import t09_pragmatic_provider as provider
    from giclab.harness.t09_provider_contracts import T09ProviderContract


EFFECT_PROTOCOL_VERSION: Final = "1.0.0"
EFFECT_AUTHORITY_SCHEMA_VERSION: Final = "1.0.0"
MAX_PACKAGE_EFFECT_BYTES: Final = 2_000_000
MAX_ESSENTIAL_FAILURE_BYTES: Final = 67_108_864
MAX_ESSENTIAL_FAILURE_FILES: Final = 4096
_HEX40: Final = re.compile(r"^[a-f0-9]{40}$")
_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SAFE_EXTERNAL_REFERENCE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,511}$")


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _safe_relative(value: str, *, label: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError(f"{label} is not an exact repository-relative path")
    return value


def _git_identity(repository: Path) -> tuple[str, str]:
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD", "HEAD^{tree}"],
        env={
            "PATH": os.defpath,
            "LANG": "C",
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    values = completed.stdout.splitlines()
    if completed.returncode != 0 or len(values) != 2:
        raise ValueError("effect repository identity is unavailable")
    return values[0], values[1]


def _tracked_blob(repository: Path, relative: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository), "show", f"HEAD:{relative}"],
        env={
            "PATH": os.defpath,
            "LANG": "C",
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        raise ValueError("declared effect module is not tracked by the exact package")
    return completed.stdout


def _read_held_bytes(fd: int, *, byte_cap: int | None = None) -> bytes:
    """Read one held regular file without consulting its pathname."""

    chunks: list[bytes] = []
    offset = 0
    while True:
        chunk = os.pread(fd, 1024 * 1024, offset)
        if not chunk:
            break
        chunks.append(chunk)
        offset += len(chunk)
        if byte_cap is not None and offset > byte_cap:
            raise ValueError("held file exceeds its byte cap")
    return b"".join(chunks)


def _open_absolute_no_symlinks(path: Path, *, flags: int) -> int:
    """Open an absolute path while refusing a symlink in every component."""

    candidate = Path(os.path.abspath(path))
    if not candidate.is_absolute() or candidate != path:
        raise ValueError("held path must be canonical and absolute")
    parts = candidate.parts
    parent_fd = os.open(
        parts[0],
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
    )
    try:
        for component in parts[1:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            os.close(parent_fd)
            parent_fd = next_fd
        return os.open(
            parts[-1],
            flags | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ValueError("held path contains a symlink or unavailable component") from exc
    finally:
        os.close(parent_fd)


def _open_relative_no_symlinks(root_fd: int, relative: str, *, flags: int) -> int:
    """Open one root-relative path through no-follow directory descriptors."""

    exact = _safe_relative(relative, label="held artifact path")
    parts = PurePosixPath(exact).parts
    parent_fd = os.dup(root_fd)
    try:
        for component in parts[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            metadata = os.fstat(next_fd)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o022
            ):
                os.close(next_fd)
                raise ValueError("held artifact parent is not a directory")
            os.close(parent_fd)
            parent_fd = next_fd
        return os.open(
            parts[-1],
            flags | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ValueError("held artifact path is unavailable or symlinked") from exc
    finally:
        os.close(parent_fd)


@dataclass(slots=True)
class HeldTransactionRoot:
    """A private transaction directory held by shared code for its full lifetime."""

    path: Path
    device: int
    inode: int
    uid: int
    mode: int
    mount_identity: str
    semantic_sha256: str
    _fd: int = field(repr=False, compare=False)
    _closed: bool = field(default=False, repr=False, compare=False)

    @property
    def descriptor(self) -> int:
        if self._closed:
            raise ValueError("held transaction root is closed")
        return self._fd

    def revalidate(self) -> None:
        """Require the held descriptor and original path to retain one identity."""

        if self._closed:
            raise ValueError("held transaction root is closed")
        self.revalidate_descriptor()
        reopened = _open_absolute_no_symlinks(
            self.path,
            flags=os.O_RDONLY | os.O_DIRECTORY,
        )
        try:
            named = os.fstat(reopened)
        finally:
            os.close(reopened)
        expected = (self.device, self.inode, self.uid, self.mode)
        if (
            named.st_dev,
            named.st_ino,
            named.st_uid,
            stat.S_IMODE(named.st_mode),
        ) != expected or not stat.S_ISDIR(named.st_mode):
            raise ValueError("held transaction root identity changed")

    def revalidate_descriptor(self) -> None:
        """Validate the held owner even when its original pathname was replaced."""

        if self._closed:
            raise ValueError("held transaction root is closed")
        held = os.fstat(self._fd)
        expected = (self.device, self.inode, self.uid, self.mode)
        if (
            (held.st_dev, held.st_ino, held.st_uid, stat.S_IMODE(held.st_mode)) != expected
            or not stat.S_ISDIR(held.st_mode)
            or f"device:{held.st_dev}" != self.mount_identity
        ):
            raise ValueError("held transaction root descriptor identity changed")

    def close(self) -> None:
        if not self._closed:
            os.close(self._fd)
            self._closed = True

    def to_document(self) -> dict[str, object]:
        return {
            "path": self.path.as_posix(),
            "device": self.device,
            "inode": self.inode,
            "uid": self.uid,
            "mode": self.mode,
            "mount_identity": self.mount_identity,
            "semantic_sha256": self.semantic_sha256,
        }

    def to_public_document(self) -> dict[str, object]:
        """Return a reproducible attestation without runtime inode or path values."""

        document: dict[str, object] = {
            "identity_derived_by_shared_code": True,
            "descriptor_held_through_cleanup": True,
            "no_symlink_path_components_validated": True,
            "current_user_owned": True,
            "group_world_write_absent": True,
            "device_inode_mode_mount_revalidated": True,
            "runtime_identity_values_retained": False,
        }
        document["public_attestation_semantic_sha256"] = _sha256(document)
        return document


def hold_transaction_root(path: Path) -> HeldTransactionRoot:
    """Open and validate one exact private root without following symlinks."""

    canonical = Path(os.path.abspath(path))
    fd = _open_absolute_no_symlinks(
        canonical,
        flags=os.O_RDONLY | os.O_DIRECTORY,
    )
    try:
        metadata = os.fstat(fd)
        mode = stat.S_IMODE(metadata.st_mode)
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or mode & 0o022:
            raise ValueError("transaction root is not an exact private owned directory")
        document = {
            "path": canonical.as_posix(),
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "uid": metadata.st_uid,
            "mode": mode,
            "mount_identity": f"device:{metadata.st_dev}",
        }
        held = HeldTransactionRoot(
            path=canonical,
            device=metadata.st_dev,
            inode=metadata.st_ino,
            uid=metadata.st_uid,
            mode=mode,
            mount_identity=f"device:{metadata.st_dev}",
            semantic_sha256=_sha256(document),
            _fd=fd,
        )
        held.revalidate()
        return held
    except BaseException:
        os.close(fd)
        raise


@dataclass(slots=True)
class HeldArtifact:
    """One sealed regular artifact held across its downstream consumer."""

    relative_path: str
    device: int
    inode: int
    uid: int
    mode: int
    bytes: int
    sha256: str
    semantic_sha256: str
    runtime_identity_sha256: str
    _root: HeldTransactionRoot = field(repr=False, compare=False)
    _fd: int = field(repr=False, compare=False)
    _closed: bool = field(default=False, repr=False, compare=False)

    @property
    def descriptor(self) -> int:
        if self._closed:
            raise ValueError("held artifact is closed")
        return self._fd

    @property
    def descriptor_path(self) -> Path:
        return Path(f"/dev/fd/{self.descriptor}")

    @property
    def path(self) -> Path:
        return self._root.path / self.relative_path

    def read_bytes(self) -> builtins.bytes:
        return _read_held_bytes(self.descriptor)

    def revalidate(self) -> None:
        if self._closed:
            raise ValueError("held artifact is closed")
        self._root.revalidate()
        reopened = _open_relative_no_symlinks(
            self._root.descriptor,
            self.relative_path,
            flags=os.O_RDONLY,
        )
        try:
            held = os.fstat(self._fd)
            named = os.fstat(reopened)
            expected = (
                self.device,
                self.inode,
                self.uid,
                self.mode,
                self.bytes,
            )
            if (
                (
                    held.st_dev,
                    held.st_ino,
                    held.st_uid,
                    stat.S_IMODE(held.st_mode),
                    held.st_size,
                )
                != expected
                or (
                    named.st_dev,
                    named.st_ino,
                    named.st_uid,
                    stat.S_IMODE(named.st_mode),
                    named.st_size,
                )
                != expected
                or hashlib.sha256(_read_held_bytes(self._fd)).hexdigest() != self.sha256
                or hashlib.sha256(_read_held_bytes(reopened)).hexdigest() != self.sha256
            ):
                raise ValueError("held artifact identity changed")
        finally:
            os.close(reopened)

    def close(self) -> None:
        if not self._closed:
            os.close(self._fd)
            self._closed = True

    def to_document(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "device": self.device,
            "inode": self.inode,
            "uid": self.uid,
            "mode": self.mode,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "semantic_sha256": self.semantic_sha256,
            "runtime_identity_sha256": self.runtime_identity_sha256,
        }

    def to_public_document(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "mode": self.mode,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "semantic_sha256": self.semantic_sha256,
            "held_runtime_identity_validated": True,
        }


def hold_sealed_artifact(
    root: HeldTransactionRoot,
    path: Path,
    *,
    seal: bool = True,
) -> HeldArtifact:
    """Hold one exact root-relative regular file and remove write permission."""

    root.revalidate()
    try:
        relative = path.relative_to(root.path).as_posix()
    except ValueError as exc:
        raise ValueError("artifact is outside the held transaction root") from exc
    fd = _open_relative_no_symlinks(root.descriptor, relative, flags=os.O_RDONLY)
    try:
        metadata = os.fstat(fd)
        mode = stat.S_IMODE(metadata.st_mode)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or mode & 0o022
        ):
            raise ValueError("artifact is not a safe current-user regular file")
        if seal and mode & 0o222:
            mode &= ~0o222
            os.fchmod(fd, mode)
            os.fsync(fd)
            metadata = os.fstat(fd)
        encoded = _read_held_bytes(fd)
        sha256 = hashlib.sha256(encoded).hexdigest()
        public_document = {
            "relative_path": relative,
            "mode": stat.S_IMODE(metadata.st_mode),
            "bytes": metadata.st_size,
            "sha256": sha256,
        }
        runtime_document = {
            "relative_path": relative,
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "uid": metadata.st_uid,
            "mode": stat.S_IMODE(metadata.st_mode),
            "bytes": metadata.st_size,
            "sha256": sha256,
        }
        held = HeldArtifact(
            relative_path=relative,
            device=metadata.st_dev,
            inode=metadata.st_ino,
            uid=metadata.st_uid,
            mode=stat.S_IMODE(metadata.st_mode),
            bytes=metadata.st_size,
            sha256=sha256,
            semantic_sha256=_sha256(public_document),
            runtime_identity_sha256=_sha256(runtime_document),
            _root=root,
            _fd=fd,
        )
        held.revalidate()
        return held
    except BaseException:
        os.close(fd)
        raise


class EffectAuthorityKind(StrEnum):
    """Authority classification kept independent from implementation flavor."""

    SHADOW_ONLY = "shadow-only"
    LIVE_AUTHORIZED = "live-authorized"


class EffectExecutionMode(StrEnum):
    """Externally bound effect envelope, independent from grant kind."""

    DETERMINISTIC_NO_NETWORK = "deterministic-no-network"
    EXTERNAL_LIVE = "external-live"


@dataclass(frozen=True, slots=True)
class EffectImplementationIdentity:
    """Exact source identity of one injected effect implementation."""

    path: str
    bytes: int
    sha256: str
    factory_entry_point: str
    protocol_version: str

    def __post_init__(self) -> None:
        _safe_relative(self.path, label="effect implementation path")
        if type(self.bytes) is not int or not 0 < self.bytes <= MAX_PACKAGE_EFFECT_BYTES:
            raise ValueError("effect implementation byte identity is invalid")
        if _HEX64.fullmatch(self.sha256) is None:
            raise ValueError("effect implementation SHA-256 is invalid")
        if _SAFE_ID.fullmatch(self.factory_entry_point) is None:
            raise ValueError("effect factory entry point is invalid")
        if self.protocol_version != EFFECT_PROTOCOL_VERSION:
            raise ValueError("effect protocol version is unsupported")

    def to_document(self) -> dict[str, object]:
        return {
            "path": self.path,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "factory_entry_point": self.factory_entry_point,
            "protocol_version": self.protocol_version,
        }


@dataclass(frozen=True, slots=True)
class EffectAuthorizationLimits:
    """Exact cost and retry policy bound into one external authorization."""

    preflight_provider_cost_usd: float
    campaign_provider_cost_usd: float
    campaign_openai_cost_usd: float
    campaign_aggregate_cost_usd: float
    prior_t09_cost_usd: float
    cumulative_t09_cost_usd: float

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or float(value) < 0
            for value in (
                self.preflight_provider_cost_usd,
                self.campaign_provider_cost_usd,
                self.campaign_openai_cost_usd,
                self.campaign_aggregate_cost_usd,
                self.prior_t09_cost_usd,
                self.cumulative_t09_cost_usd,
            )
        ):
            raise ValueError("effect authorization cost limits are malformed")

    def to_document(self) -> dict[str, float]:
        return {
            "preflight_provider_cost_usd": float(self.preflight_provider_cost_usd),
            "campaign_provider_cost_usd": float(self.campaign_provider_cost_usd),
            "campaign_openai_cost_usd": float(self.campaign_openai_cost_usd),
            "campaign_aggregate_cost_usd": float(self.campaign_aggregate_cost_usd),
            "prior_t09_cost_usd": float(self.prior_t09_cost_usd),
            "cumulative_t09_cost_usd": float(self.cumulative_t09_cost_usd),
        }


@dataclass(frozen=True, slots=True)
class EffectAuthorizationContext:
    """One fully bound transaction context presented to an external grant."""

    authority_kind: EffectAuthorityKind
    execution_mode: EffectExecutionMode
    control_commit: str
    control_tree: str
    provider_contract_version: str
    plan_id: str
    plan_path: str
    plan_bytes: int
    plan_sha256: str
    command_package_sha256: str
    control_binding_semantic_sha256: str
    effect_implementation: EffectImplementationIdentity
    transaction_root_identity: str
    external_authorization_reference: str | None
    external_authorization_source_sha256: str | None
    cost_limits: EffectAuthorizationLimits
    zero_retry: bool
    interpretation: str
    current_turn_scope: str
    campaign_count: int
    schema_version: str = EFFECT_AUTHORITY_SCHEMA_VERSION
    effect_protocol_version: str = EFFECT_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EFFECT_AUTHORITY_SCHEMA_VERSION:
            raise ValueError("effect authority schema version is unsupported")
        if self.effect_protocol_version != EFFECT_PROTOCOL_VERSION:
            raise ValueError("effect authorization protocol version is unsupported")
        if (
            _HEX40.fullmatch(self.control_commit) is None
            or _HEX40.fullmatch(self.control_tree) is None
        ):
            raise ValueError("effect authorization control identity is malformed")
        if (
            _SAFE_ID.fullmatch(self.provider_contract_version) is None
            or _SAFE_ID.fullmatch(self.plan_id) is None
        ):
            raise ValueError("effect authorization package identity is malformed")
        _safe_relative(self.plan_path, label="effect authorization plan path")
        if type(self.plan_bytes) is not int or self.plan_bytes <= 0:
            raise ValueError("effect authorization plan byte identity is malformed")
        if (
            self.zero_retry is not True
            or self.interpretation != "descriptive-calibration-only"
            or _SAFE_ID.fullmatch(self.current_turn_scope) is None
            or self.campaign_count != 1
        ):
            raise ValueError("effect authorization execution policy is malformed")
        for label, value in (
            ("plan", self.plan_sha256),
            ("command package", self.command_package_sha256),
            ("control binding", self.control_binding_semantic_sha256),
            ("transaction root", self.transaction_root_identity),
        ):
            if _HEX64.fullmatch(value) is None:
                raise ValueError(f"effect authorization {label} identity is malformed")
        reference = self.external_authorization_reference
        source = self.external_authorization_source_sha256
        if self.authority_kind is EffectAuthorityKind.SHADOW_ONLY:
            if (
                self.execution_mode is not EffectExecutionMode.DETERMINISTIC_NO_NETWORK
                or reference is not None
                or source is not None
            ):
                raise ValueError("shadow effect context cannot contain live authorization")
        elif (
            not isinstance(reference, str)
            or _SAFE_EXTERNAL_REFERENCE.fullmatch(reference) is None
            or not isinstance(source, str)
            or _HEX64.fullmatch(source) is None
        ):
            raise ValueError("live effect context lacks exact external authorization")

    def to_document(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "effect_protocol_version": self.effect_protocol_version,
            "authority_kind": self.authority_kind.value,
            "execution_mode": self.execution_mode.value,
            "control_commit": self.control_commit,
            "control_tree": self.control_tree,
            "provider_contract_version": self.provider_contract_version,
            "plan_id": self.plan_id,
            "plan_path": self.plan_path,
            "plan_bytes": self.plan_bytes,
            "plan_sha256": self.plan_sha256,
            "command_package_sha256": self.command_package_sha256,
            "control_binding_semantic_sha256": self.control_binding_semantic_sha256,
            "effect_implementation": self.effect_implementation.to_document(),
            "transaction_root_identity": self.transaction_root_identity,
            "external_authorization_reference": self.external_authorization_reference,
            "external_authorization_source_sha256": (self.external_authorization_source_sha256),
            "cost_limits": self.cost_limits.to_document(),
            "zero_retry": self.zero_retry,
            "interpretation": self.interpretation,
            "current_turn_scope": self.current_turn_scope,
            "campaign_count": self.campaign_count,
        }

    @property
    def semantic_sha256(self) -> str:
        return _sha256(self.to_document())


_SHADOW_AUTHORITY_PROOF = object()


@dataclass(frozen=True, slots=True, init=False)
class EffectAuthority:
    """Opaque exact-context grant whose public constructor is unavailable."""

    kind: EffectAuthorityKind
    source: str
    context_semantic_sha256: str
    _context: EffectAuthorizationContext = field(repr=False, compare=False)
    _proof: object = field(repr=False, compare=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("effect authority is minted only by reviewed validators")

    @classmethod
    def _mint_shadow(
        cls,
        *,
        source: str,
        context: EffectAuthorizationContext,
    ) -> EffectAuthority:
        if context.authority_kind is not EffectAuthorityKind.SHADOW_ONLY:
            raise ValueError("shared authority factory can mint shadow contexts only")
        value = object.__new__(cls)
        object.__setattr__(value, "kind", EffectAuthorityKind.SHADOW_ONLY)
        object.__setattr__(value, "source", source)
        object.__setattr__(value, "context_semantic_sha256", context.semantic_sha256)
        object.__setattr__(value, "_context", context)
        object.__setattr__(value, "_proof", _SHADOW_AUTHORITY_PROOF)
        return value

    def is_valid_shadow(self) -> bool:
        return (
            self.kind is EffectAuthorityKind.SHADOW_ONLY
            and self._proof is _SHADOW_AUTHORITY_PROOF
            and self._context.authority_kind is EffectAuthorityKind.SHADOW_ONLY
            and self.context_semantic_sha256 == self._context.semantic_sha256
        )

    def authorizes(self, context: EffectAuthorizationContext) -> bool:
        return self.is_valid_shadow() and context == self._context


def mint_shadow_effect_authority(
    *,
    source: str,
    context: EffectAuthorizationContext,
) -> EffectAuthority:
    """Mint the only authority kind available from shared source."""

    return EffectAuthority._mint_shadow(source=source, context=context)


class LiveAuthorityState(StrEnum):
    """Durable, non-replayable phases of one external authorization."""

    VALIDATED_UNCONSUMED = "validated-unconsumed"
    RESERVED_BEFORE_SECRET = "reserved-before-secret"
    METADATA_SEND_ATTEMPTED = "metadata-send-attempted"
    METADATA_BOUND = "metadata-bound"
    PROVIDER_LAUNCH_CONSUMED = "provider-launch-consumed"
    TERMINAL_COMPLETE = "terminal-complete"
    TERMINAL_FAILED_NONREPLAYABLE = "terminal-failed-nonreplayable"


_LIVE_VALIDATOR_PROOF = object()


@dataclass(slots=True)
class _HeldExternalAuthoritySource:
    """Private overlay bytes held from validation through terminal consumption."""

    path: Path
    device: int
    inode: int
    uid: int
    mode: int
    bytes: int
    sha256: str
    source_bytes: builtins.bytes = field(repr=False)
    _fd: int = field(repr=False, compare=False)
    _closed: bool = field(default=False, repr=False, compare=False)

    def revalidate(self) -> None:
        if self._closed:
            raise ValueError("external authorization source is closed")
        named_fd = _open_absolute_no_symlinks(self.path, flags=os.O_RDONLY)
        try:
            held = os.fstat(self._fd)
            named = os.fstat(named_fd)
            expected = (self.device, self.inode, self.uid, self.mode, self.bytes)
            for metadata in (held, named):
                if (
                    (
                        metadata.st_dev,
                        metadata.st_ino,
                        metadata.st_uid,
                        stat.S_IMODE(metadata.st_mode),
                        metadata.st_size,
                    )
                    != expected
                    or not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_nlink != 1
                ):
                    raise ValueError("external authorization source identity changed")
            if (
                _read_held_bytes(self._fd, byte_cap=256_000) != self.source_bytes
                or _read_held_bytes(named_fd, byte_cap=256_000) != self.source_bytes
                or hashlib.sha256(self.source_bytes).hexdigest() != self.sha256
            ):
                raise ValueError("external authorization source bytes changed")
        finally:
            os.close(named_fd)

    def close(self) -> None:
        if not self._closed:
            os.close(self._fd)
            self._closed = True


def _strict_json_object(encoded: bytes, *, label: str) -> dict[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        document: dict[str, object] = {}
        for key, value in pairs:
            if key in document:
                raise ValueError(f"{label} contains a duplicate key")
            document[key] = value
        return document

    try:
        parsed = json.loads(encoded, object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not strict JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} is not a JSON object")
    return parsed


def _authorization_limits(contract: T09ProviderContract) -> EffectAuthorizationLimits:
    return EffectAuthorizationLimits(
        preflight_provider_cost_usd=contract.preflight_lambda_cost_cap_usd,
        campaign_provider_cost_usd=contract.campaign_lambda_cost_cap_usd,
        campaign_openai_cost_usd=contract.campaign_openai_cost_cap_usd,
        campaign_aggregate_cost_usd=contract.campaign_aggregate_cost_cap_usd,
        prior_t09_cost_usd=contract.prior_t09_cost_usd,
        cumulative_t09_cost_usd=contract.cumulative_t09_cost_cap_usd,
    )


def project_live_authority_overlay(
    repository: Path,
    contract: T09ProviderContract,
    *,
    held_transaction_root: HeldTransactionRoot,
    effect_implementation: EffectImplementationIdentity,
    control_binding_semantic_sha256: str,
    external_authorization_reference: str,
    current_turn_scope: str,
    execution_mode: EffectExecutionMode,
) -> dict[str, object]:
    """Project the exact external overlay bytes without granting authority."""

    root = repository.resolve(strict=True)
    commit, tree = _git_identity(root)
    plan_path = root / contract.plan_path
    plan_fd = _open_absolute_no_symlinks(plan_path, flags=os.O_RDONLY)
    try:
        plan_metadata = os.fstat(plan_fd)
        plan_bytes = _read_held_bytes(plan_fd, byte_cap=MAX_PACKAGE_EFFECT_BYTES)
    finally:
        os.close(plan_fd)
    command_sha = contract.expected_command_manifest_sha256
    if (
        not stat.S_ISREG(plan_metadata.st_mode)
        or plan_metadata.st_uid != os.getuid()
        or plan_metadata.st_nlink != 1
        or stat.S_IMODE(plan_metadata.st_mode) & 0o022
        or plan_metadata.st_size != contract.expected_plan_bytes
        or hashlib.sha256(plan_bytes).hexdigest() != contract.expected_plan_sha256
        or _tracked_blob(root, contract.plan_path) != plan_bytes
        or command_sha is None
        or _HEX64.fullmatch(control_binding_semantic_sha256) is None
        or _SAFE_EXTERNAL_REFERENCE.fullmatch(external_authorization_reference) is None
        or _SAFE_ID.fullmatch(current_turn_scope) is None
    ):
        raise ValueError("external authorization projection lacks exact package identity")
    held_transaction_root.revalidate()
    return {
        "schema_version": EFFECT_AUTHORITY_SCHEMA_VERSION,
        "effect_protocol_version": EFFECT_PROTOCOL_VERSION,
        "authorization_reference": external_authorization_reference,
        "authority_kind": EffectAuthorityKind.LIVE_AUTHORIZED.value,
        "execution_mode": execution_mode.value,
        "control_commit": commit,
        "control_tree": tree,
        "provider_contract_version": contract.version,
        "plan_id": contract.plan_id,
        "plan_path": contract.plan_path,
        "plan_bytes": plan_metadata.st_size,
        "plan_sha256": contract.expected_plan_sha256,
        "command_package_sha256": command_sha,
        "control_binding_semantic_sha256": control_binding_semantic_sha256,
        "effect_implementation": effect_implementation.to_document(),
        "transaction_root_identity": held_transaction_root.semantic_sha256,
        "cost_limits": _authorization_limits(contract).to_document(),
        "zero_retry": True,
        "interpretation": "descriptive-calibration-only",
        "current_turn_scope": current_turn_scope,
        "campaign_count": 1,
        "contains_secret_material": False,
    }


@dataclass(slots=True, init=False)
class ValidatedLiveEffectAuthority:
    """Opaque proof and durable single-use state minted only by the validator."""

    kind: EffectAuthorityKind
    source: str
    context_semantic_sha256: str
    external_authorization_reference: str
    external_authorization_source_sha256: str
    _context: EffectAuthorizationContext = field(repr=False, compare=False)
    _held_root: HeldTransactionRoot = field(repr=False, compare=False)
    _held_source: _HeldExternalAuthoritySource = field(repr=False, compare=False)
    _state_relative: str = field(repr=False, compare=False)
    _state_fd: int = field(repr=False, compare=False)
    _state_device: int = field(repr=False, compare=False)
    _state_inode: int = field(repr=False, compare=False)
    _proof: object = field(repr=False, compare=False)
    _state: LiveAuthorityState = field(repr=False, compare=False)
    _ordinal: int = field(repr=False, compare=False)
    _closed: bool = field(default=False, repr=False, compare=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("live effect authority is created only by the external validator")

    def _document(self, state: LiveAuthorityState, ordinal: int) -> dict[str, object]:
        return {
            "schema_version": EFFECT_AUTHORITY_SCHEMA_VERSION,
            "authorization_reference": self.external_authorization_reference,
            "authorization_source_sha256": self.external_authorization_source_sha256,
            "authorization_context_semantic_sha256": self.context_semantic_sha256,
            "transaction_root_identity": self._held_root.semantic_sha256,
            "state": state.value,
            "transition_ordinal": ordinal,
            "single_campaign": True,
            "replay_permitted": False,
            "contains_secret_material": False,
        }

    def _revalidate_state(self, *, allow_root_path_mismatch: bool = False) -> None:
        if self._closed:
            raise ValueError("live authority state is closed")
        self._held_source.revalidate()
        if allow_root_path_mismatch:
            self._held_root.revalidate_descriptor()
        else:
            self._held_root.revalidate()
        named_fd = _open_relative_no_symlinks(
            self._held_root.descriptor,
            self._state_relative,
            flags=os.O_RDONLY,
        )
        try:
            held = os.fstat(self._state_fd)
            named = os.fstat(named_fd)
            expected = (self._state_device, self._state_inode)
            for metadata in (held, named):
                if (
                    (metadata.st_dev, metadata.st_ino) != expected
                    or not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_uid != os.getuid()
                    or metadata.st_nlink != 1
                    or stat.S_IMODE(metadata.st_mode) != 0o600
                ):
                    raise ValueError("live authority state-file identity changed")
            document = _strict_json_object(
                _read_held_bytes(self._state_fd),
                label="live authority state",
            )
            if document != self._document(self._state, self._ordinal):
                raise ValueError("live authority durable state is ambiguous or truncated")
        finally:
            os.close(named_fd)

    def _transition(
        self,
        *,
        expected: tuple[LiveAuthorityState, ...],
        target: LiveAuthorityState,
    ) -> None:
        self._revalidate_state()
        if self._state not in expected:
            raise ValueError("live authority transition is replayed or out of order")
        ordinal = self._ordinal + 1
        encoded = _canonical_bytes(self._document(target, ordinal))
        os.ftruncate(self._state_fd, 0)
        os.pwrite(self._state_fd, encoded, 0)
        os.fsync(self._state_fd)
        os.fsync(self._held_root.descriptor)
        self._state = target
        self._ordinal = ordinal
        self._revalidate_state()

    @property
    def held_transaction_root(self) -> HeldTransactionRoot:
        self._held_root.revalidate()
        return self._held_root

    @property
    def state(self) -> LiveAuthorityState:
        self._revalidate_state()
        return self._state

    def is_valid_for(self, context: EffectAuthorizationContext) -> bool:
        try:
            self._revalidate_state()
        except ValueError:
            return False
        return (
            self._proof is _LIVE_VALIDATOR_PROOF
            and self.kind is EffectAuthorityKind.LIVE_AUTHORIZED
            and context == self._context
            and context.semantic_sha256 == self.context_semantic_sha256
            and context.transaction_root_identity == self._held_root.semantic_sha256
            and context.external_authorization_reference == self.external_authorization_reference
            and context.external_authorization_source_sha256
            == self.external_authorization_source_sha256
            and self._state is LiveAuthorityState.VALIDATED_UNCONSUMED
        )

    def authorizes(self, context: EffectAuthorizationContext) -> bool:
        return self.is_valid_for(context)

    def assert_phase_binding(
        self,
        *,
        reference: str,
        source_sha256: str,
        allow_root_path_mismatch: bool = False,
    ) -> None:
        self._revalidate_state(allow_root_path_mismatch=allow_root_path_mismatch)
        if (
            reference != self.external_authorization_reference
            or source_sha256 != self.external_authorization_source_sha256
        ):
            raise ValueError("live effect and provider authorization identities differ")

    def reserve_before_secret(self) -> None:
        self._transition(
            expected=(LiveAuthorityState.VALIDATED_UNCONSUMED,),
            target=LiveAuthorityState.RESERVED_BEFORE_SECRET,
        )

    def mark_metadata_send_attempted(self) -> None:
        self._transition(
            expected=(LiveAuthorityState.RESERVED_BEFORE_SECRET,),
            target=LiveAuthorityState.METADATA_SEND_ATTEMPTED,
        )

    def mark_metadata_bound(self) -> None:
        self._transition(
            expected=(LiveAuthorityState.METADATA_SEND_ATTEMPTED,),
            target=LiveAuthorityState.METADATA_BOUND,
        )

    def consume_provider_launch(self) -> None:
        self._transition(
            expected=(LiveAuthorityState.METADATA_BOUND,),
            target=LiveAuthorityState.PROVIDER_LAUNCH_CONSUMED,
        )

    def terminal_complete(self) -> None:
        self._transition(
            expected=(LiveAuthorityState.PROVIDER_LAUNCH_CONSUMED,),
            target=LiveAuthorityState.TERMINAL_COMPLETE,
        )

    def terminal_failed_nonreplayable(self) -> None:
        if self.state in {
            LiveAuthorityState.TERMINAL_COMPLETE,
            LiveAuthorityState.TERMINAL_FAILED_NONREPLAYABLE,
        }:
            return
        self._transition(
            expected=(
                LiveAuthorityState.RESERVED_BEFORE_SECRET,
                LiveAuthorityState.METADATA_SEND_ATTEMPTED,
                LiveAuthorityState.METADATA_BOUND,
                LiveAuthorityState.PROVIDER_LAUNCH_CONSUMED,
            ),
            target=LiveAuthorityState.TERMINAL_FAILED_NONREPLAYABLE,
        )

    def consumption_receipt(
        self,
        *,
        allow_root_path_mismatch: bool = False,
    ) -> dict[str, object]:
        self._revalidate_state(allow_root_path_mismatch=allow_root_path_mismatch)
        document = self._document(self._state, self._ordinal)
        return {
            "authorization_reference": self.external_authorization_reference,
            "authorization_source_sha256": self.external_authorization_source_sha256,
            "authorization_context_semantic_sha256": self.context_semantic_sha256,
            "transaction_root_identity": self._held_root.semantic_sha256,
            "terminal_state": self._state.value,
            "single_use": True,
            "replay_permitted": False,
            "contains_private_overlay_contents": False,
            "receipt_sha256": _sha256(document),
        }

    def close(self) -> None:
        if not self._closed:
            os.close(self._state_fd)
            self._held_source.close()
            self._closed = True


EffectAuthorityGrant = EffectAuthority | ValidatedLiveEffectAuthority


def validate_external_live_effect_authority(
    repository: Path,
    contract: T09ProviderContract,
    *,
    overlay_path: Path,
    held_transaction_root: HeldTransactionRoot,
    effect_implementation: EffectImplementationIdentity,
    control_binding_semantic_sha256: str,
    current_turn_scope: str,
    execution_mode: EffectExecutionMode,
) -> tuple[EffectAuthorizationContext, ValidatedLiveEffectAuthority]:
    """Validate one private overlay and reserve an exclusive durable state file."""

    root = repository.resolve(strict=True)
    try:
        overlay_path.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValueError("repository state cannot provide external live authority")
    overlay_fd = _open_absolute_no_symlinks(overlay_path, flags=os.O_RDONLY)
    try:
        metadata = os.fstat(overlay_fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise ValueError("external authorization overlay is not private and exact")
        encoded = _read_held_bytes(overlay_fd, byte_cap=256_000)
        overlay = _strict_json_object(encoded, label="external authorization overlay")
        source_sha256 = hashlib.sha256(encoded).hexdigest()
        held_source = _HeldExternalAuthoritySource(
            path=Path(os.path.abspath(overlay_path)),
            device=metadata.st_dev,
            inode=metadata.st_ino,
            uid=metadata.st_uid,
            mode=stat.S_IMODE(metadata.st_mode),
            bytes=metadata.st_size,
            sha256=source_sha256,
            source_bytes=encoded,
            _fd=overlay_fd,
        )
        held_source.revalidate()
    except BaseException:
        os.close(overlay_fd)
        raise
    reference = overlay.get("authorization_reference")
    if not isinstance(reference, str):
        held_source.close()
        raise ValueError("external authorization reference is missing")
    try:
        contract.validate_authority(reference, source_sha256)
        expected = project_live_authority_overlay(
            root,
            contract,
            held_transaction_root=held_transaction_root,
            effect_implementation=effect_implementation,
            control_binding_semantic_sha256=control_binding_semantic_sha256,
            external_authorization_reference=reference,
            current_turn_scope=current_turn_scope,
            execution_mode=execution_mode,
        )
        if overlay != expected:
            raise ValueError("external authorization overlay contradicts its exact context")
    except BaseException:
        held_source.close()
        raise
    commit, tree = _git_identity(root)
    context = EffectAuthorizationContext(
        authority_kind=EffectAuthorityKind.LIVE_AUTHORIZED,
        execution_mode=execution_mode,
        control_commit=commit,
        control_tree=tree,
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        plan_path=contract.plan_path,
        plan_bytes=contract.expected_plan_bytes,
        plan_sha256=contract.expected_plan_sha256,
        command_package_sha256=cast(str, contract.expected_command_manifest_sha256),
        control_binding_semantic_sha256=control_binding_semantic_sha256,
        effect_implementation=effect_implementation,
        transaction_root_identity=held_transaction_root.semantic_sha256,
        external_authorization_reference=reference,
        external_authorization_source_sha256=source_sha256,
        cost_limits=_authorization_limits(contract),
        zero_retry=True,
        interpretation="descriptive-calibration-only",
        current_turn_scope=current_turn_scope,
        campaign_count=1,
    )
    state_relative = ".live-authority-state.json"
    try:
        state_fd = os.open(
            state_relative,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=held_transaction_root.descriptor,
        )
    except OSError as exc:
        held_source.close()
        raise ValueError("live authority was already created or cannot be reserved") from exc
    try:
        state_metadata = os.fstat(state_fd)
        value = object.__new__(ValidatedLiveEffectAuthority)
        object.__setattr__(value, "kind", EffectAuthorityKind.LIVE_AUTHORIZED)
        object.__setattr__(value, "source", "validated-external-private-overlay")
        object.__setattr__(value, "context_semantic_sha256", context.semantic_sha256)
        object.__setattr__(value, "external_authorization_reference", reference)
        object.__setattr__(value, "external_authorization_source_sha256", source_sha256)
        object.__setattr__(value, "_context", context)
        object.__setattr__(value, "_held_root", held_transaction_root)
        object.__setattr__(value, "_held_source", held_source)
        object.__setattr__(value, "_state_relative", state_relative)
        object.__setattr__(value, "_state_fd", state_fd)
        object.__setattr__(value, "_state_device", state_metadata.st_dev)
        object.__setattr__(value, "_state_inode", state_metadata.st_ino)
        object.__setattr__(value, "_proof", _LIVE_VALIDATOR_PROOF)
        object.__setattr__(value, "_state", LiveAuthorityState.VALIDATED_UNCONSUMED)
        object.__setattr__(value, "_ordinal", 0)
        object.__setattr__(value, "_closed", False)
        os.pwrite(state_fd, _canonical_bytes(value._document(value._state, 0)), 0)
        os.fsync(state_fd)
        os.fsync(held_transaction_root.descriptor)
        value._revalidate_state()
        return context, value
    except BaseException:
        os.close(state_fd)
        held_source.close()
        try:
            os.unlink(state_relative, dir_fd=held_transaction_root.descriptor)
            os.fsync(held_transaction_root.descriptor)
        except OSError:
            pass
        raise


@dataclass(frozen=True, slots=True)
class ProviderHandle:
    opaque_identity: str
    launch_ordinal: int

    def __post_init__(self) -> None:
        if _SAFE_ID.fullmatch(self.opaque_identity) is None or self.launch_ordinal <= 0:
            raise ValueError("provider handle is malformed")


@dataclass(frozen=True, slots=True)
class ProviderCostObservationRequest:
    """Exact provider lifecycle identity observed at a control checkpoint."""

    provider_handle: ProviderHandle
    observed_wall_time: float
    observed_monotonic: float
    campaign_started_wall_time: float
    campaign_started_monotonic: float


@dataclass(frozen=True, slots=True)
class ProviderCostReceipt:
    """Effect-produced provider billing facts validated by shared policy.

    The effect reports lifecycle facts; it does not decide whether a checkpoint
    may continue.  A deterministic no-network effect reports a zero hourly rate
    and zero costs while retaining the same receipt shape.
    """

    owned_instance_identity: str
    launch_ordinal: int
    hourly_price_usd: float
    active_started_wall_time: float
    active_ended_wall_time: float | None
    observed_wall_time: float
    prior_preflight_cost_usd: float
    current_empirical_cost_usd: float
    cumulative_provider_cost_usd: float
    real_provider_effects: bool
    receipt_sha256: str


@runtime_checkable
class RuntimeClock(Protocol):
    """Separate monotonic, wall-time, and sleeping domains."""

    def monotonic(self) -> float: ...

    def wall_time(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class ModelMetadataChannel(Protocol):
    """The sole authenticated metadata send boundary."""

    def get_model_metadata(
        self,
        *,
        model_id: str,
        credential: bytearray,
        started_at: float,
    ) -> ModelMetadataResponse: ...


@dataclass(frozen=True, slots=True)
class TrackedPackageMember:
    path: str
    bytes: int
    sha256: str

    def __post_init__(self) -> None:
        _safe_relative(self.path, label="tracked package member")
        if type(self.bytes) is not int or self.bytes < 0 or _HEX64.fullmatch(self.sha256) is None:
            raise ValueError("tracked package member identity is malformed")

    def to_document(self) -> dict[str, object]:
        return {"path": self.path, "bytes": self.bytes, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class PackageStageRequest:
    repository: Path
    control_commit: str
    control_tree: str
    provider_contract_version: str
    plan_id: str
    plan_sha256: str
    command_package_sha256: str
    execution_contract_sha256: str
    evidence_stage_id: str
    host_run_id: str
    members: tuple[TrackedPackageMember, ...]
    max_archive_bytes: int
    max_member_bytes: int
    max_members: int


@dataclass(frozen=True, slots=True)
class PackageStageReceipt:
    provider_contract_version: str
    plan_id: str
    plan_sha256: str
    command_package_sha256: str
    execution_contract_sha256: str
    evidence_stage_id: str
    host_run_id: str
    archive_path: Path
    archive_sha256: str
    archive_bytes: int
    members: tuple[TrackedPackageMember, ...]
    source_commit: str
    source_tree: str
    host_acknowledgement_sha256: str
    host_rehash_sha256: str
    uploaded: bool
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class HostPreflightRequest:
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    provider_handle: ProviderHandle
    campaign_private_root: Path
    provider_entry_receipt_path: Path
    provider_entry_receipt_sha256: str
    metadata_receipt_path: Path
    metadata_receipt_sha256: str
    stage_receipt_sha256: str
    remote_root: str
    requested_wall_time: float
    requested_monotonic: float


@dataclass(frozen=True, slots=True)
class HostPreflightReceipt:
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    provider_handle_identity: str
    provider_launch_ordinal: int
    provider_entry_receipt_sha256: str
    metadata_receipt_sha256: str
    stage_receipt_sha256: str
    remote_path_qualification_sha256: str
    started_wall_time: float
    completed_wall_time: float
    started_monotonic: float
    completed_monotonic: float
    receipt_sha256: str


class HostPreflightRejected(RuntimeError):
    """Typed pre-empirical host rejection with exact closeout evidence."""

    def __init__(
        self,
        message: str,
        *,
        disposition_path: Path,
        source_root: Path,
        remote_cleanup_journal: Path,
    ) -> None:
        super().__init__(message)
        self.disposition_path = disposition_path
        self.source_root = source_root
        self.remote_cleanup_journal = remote_cleanup_journal


@dataclass(frozen=True, slots=True)
class HostQualificationRequest:
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    provider_handle: ProviderHandle
    provider_entry_receipt_sha256: str
    stage_receipt_sha256: str
    replacement_image_tag: str
    image_materialization_policy: str
    active_image_qualification_id: str
    local_finalizer_qualification_id: str


@dataclass(frozen=True, slots=True)
class HostQualificationReceipt:
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    provider_handle_identity: str
    provider_launch_ordinal: int
    provider_entry_receipt_sha256: str
    stage_receipt_sha256: str
    replacement_image_tag: str
    image_materialization_policy: str
    qualification_id: str
    local_finalizer_qualification_id: str
    image_materialization_receipt_sha256: str
    image_digest: str
    python_interpreter: str
    python_interpreter_sha256: str
    dependency_manifest_sha256: str
    dependency_tree_sha256: str
    browser_qualification_sha256: str
    downstream_source_roles_sha256: str
    finalizer_source_sha256: str
    finalizer_projection_source_sha256: str
    finalizer_selector_sha256: str
    finalizer_schema_sha256: str
    local_finalizer_qualification_sha256: str
    local_finalizer_interpreter: str
    local_finalizer_interpreter_sha256: str
    local_finalizer_dependency_manifest_sha256: str
    local_finalizer_dependency_tree_sha256: str
    local_evaluator_dependency_tree_sha256: str
    cleanup_readiness_sha256: str
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class ScientificFreezeRequest:
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    frozen_manifest_id: str
    provider_entry_receipt_sha256: str
    stage_receipt_sha256: str
    command_package_sha256: str
    execution_contract_sha256: str
    qualification_receipt_sha256: str
    image_digest: str
    manifest_root: Path
    started_wall_time: float
    started_monotonic: float


@dataclass(frozen=True, slots=True)
class ScientificFreezeReceipt:
    manifest_path: Path
    manifest_sha256: str
    postfreeze_validation_path: Path
    postfreeze_validation_sha256: str
    started_wall_time: float
    completed_wall_time: float
    started_monotonic: float
    completed_monotonic: float
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class PackageRuntimeBudget:
    aggregate_caps: ProviderBudgetCaps
    condition_caps: Mapping[str, ProviderBudgetCaps]
    attempt_order: tuple[str, ...]
    model_revision: str
    service_tier: str
    zero_retry: bool
    command_package_sha256: str
    execution_contract_sha256: str
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class ConditionExecutionRequest:
    run_id: str
    evaluator_run_id: str
    command_argv: tuple[str, ...]
    command_sha256: str
    condition_plan_path: str
    condition_plan_sha256: str
    raw_output_root: str
    finalized_output_root: str
    model_revision: str
    service_tier: str
    zero_retry: bool
    caps: ProviderBudgetCaps
    execution_contract_sha256: str
    frozen_manifest_sha256: str
    provider_contract_version: str
    plan_id: str
    package_commit: str
    transaction_root: Path
    condition_started_wall_time: float
    condition_started_monotonic: float
    campaign_deadline_monotonic: float


@dataclass(frozen=True, slots=True)
class ConditionModelCall:
    call_id: str
    logical_call_id: str
    request: ProviderRequest


@dataclass(frozen=True, slots=True)
class ConditionModelResponse:
    content: str
    usage: ProviderResponseUsage


class ConditionKnownProviderError(RuntimeError):
    """Provider rejected a known send and its reservation can be released."""


class ConditionKnownTransportError(RuntimeError):
    """Transport proved no provider acceptance."""


class ConditionAmbiguousSend(RuntimeError):
    """A send started but its provider outcome is unknown."""


class ConditionResponseAccountingIncomplete(RuntimeError):
    """A response arrived without an acceptable usage receipt."""


class ConditionFailureClass(StrEnum):
    """Shared classification for a consumed infrastructure-invalid attempt."""

    KNOWN_PROVIDER = "known-provider-error"
    KNOWN_TRANSPORT = "known-transport-error-no-provider-acceptance"
    AMBIGUOUS_SEND = "ambiguous-send"
    RESPONSE_ACCOUNTING_INCOMPLETE = "response-accounting-incomplete"
    BUDGET_ADMISSION = "budget-admission-stop"
    PROCESS_CRASH = "process-crash"
    PROCESS_EXIT_NONZERO = "process-exit-nonzero"
    RAW_PUBLICATION = "raw-publication-failure"
    RAW_EXPORT = "raw-export-failure"
    FINALIZER = "finalizer-failure"
    EVALUATOR = "evaluator-failure"
    OUTCOME_VALIDATION = "outcome-validation-failure"


@dataclass(frozen=True, slots=True)
class ConditionFailurePreservationRequest:
    """Shared-accounted facts an effect must preserve after empirical entry."""

    execution: ConditionExecutionRequest
    failure_class: ConditionFailureClass
    process_exit_code: int | None
    completed: bool
    answer: str | None
    error: str
    partial_raw_root: Path
    accounting_document: Mapping[str, object]
    call_ids: tuple[str, ...]
    logical_call_ids: tuple[str, ...]
    browser_actions: tuple[tuple[str, str], ...]
    unknown_call_ids: tuple[str, ...]
    output_bytes: int
    retry_count: int
    essential_failure_cap_bytes: int = MAX_ESSENTIAL_FAILURE_BYTES
    essential_failure_file_cap: int = MAX_ESSENTIAL_FAILURE_FILES


@dataclass(frozen=True, slots=True)
class ConditionInfrastructureFailureOutcome:
    """Immutable effect-produced evidence for one consumed failed attempt."""

    run_id: str
    evaluator_run_id: str
    failure_class: ConditionFailureClass
    process_exit_code: int | None
    completed: bool
    answer: str | None
    error: str
    essential_root: Path
    essential_manifest_path: Path
    essential_receipt_path: Path
    call_ledger_path: Path
    browser_ledger_path: Path
    process_outcome_path: Path
    completion_path: Path
    stdout_path: Path | None
    stderr_path: Path | None
    essential_file_count: int
    essential_total_bytes: int
    output_bytes: int
    unknown_call_ids: tuple[str, ...]
    writers_closed: bool
    browser_descendants_closed: bool
    credential_cleanup_clean: bool
    core_dump_present: bool
    structural_privacy_findings: tuple[str, ...]
    cleanup_ready: bool
    retry_count: int


@dataclass(frozen=True, slots=True)
class ConditionFailureExportRequest:
    run_id: str
    essential_root: Path
    essential_manifest_path: Path
    essential_receipt_path: Path
    essential_manifest_sha256: str
    essential_receipt_sha256: str
    essential_file_count: int
    essential_total_bytes: int
    export_identity: str


@dataclass(frozen=True, slots=True)
class ConditionFailureExportReceipt:
    run_id: str
    export_identity: str
    destination_identity: str
    essential_manifest_sha256: str
    essential_receipt_sha256: str
    essential_file_count: int
    essential_total_bytes: int
    export_complete: bool
    resumed: bool
    receipt_sha256: str


class ConditionFailureExportInterrupted(RuntimeError):
    """A bounded failure export can resume from its immutable source identity."""


ConditionSend = Callable[[], ConditionModelResponse]
ConditionAction = Callable[[], None]
T = TypeVar("T")


class ConditionEventObserver(Protocol):
    """Sole authoritative real-time accounting observer for one condition."""

    def model_call(self, event: ConditionModelCall, send: ConditionSend) -> str: ...

    def browser_action(self, *, action_id: str, perform: ConditionAction) -> None: ...

    def output_bytes(self, *, total_bytes: int) -> None: ...

    def process_exit(self, *, exit_code: int) -> None: ...

    def completion(self, *, completed: bool, answer: str | None, error: str) -> None: ...

    def raw_artifact_published(
        self,
        *,
        manifest_sha256: str,
        receipt_sha256: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ConditionProcessOutcome:
    run_id: str
    evaluator_run_id: str
    exit_code: int
    completed: bool
    answer: str | None
    error: str
    raw_root: Path
    raw_manifest_path: Path
    raw_receipt_path: Path
    raw_file_count: int
    raw_total_bytes: int
    output_bytes: int
    call_ledger_path: Path
    browser_ledger_path: Path
    completion_path: Path
    process_outcome_path: Path
    retry_count: int


ConditionExecutionResult = ConditionProcessOutcome | ConditionInfrastructureFailureOutcome


@dataclass(frozen=True, slots=True)
class FinalizerExecutionRequest:
    run_id: str
    evaluator_run_id: str
    execution_mode: str
    runtime_qualification_id: str
    runtime_qualification_sha256: str
    raw_root: Path
    raw_manifest_path: Path
    raw_receipt_path: Path
    raw_manifest_sha256: str
    raw_receipt_sha256: str
    raw_completion_path: Path
    raw_completion_sha256: str
    raw_artifacts: tuple[HeldArtifact, ...]
    raw_artifact_binding_sha256: str
    answer_artifact: HeldArtifact
    process_outcome_path: Path
    process_outcome_sha256: str
    raw_output_root: str
    finalized_root: Path
    finalized_output_root: str
    finalizer_source_sha256: str
    finalizer_projection_source_sha256: str
    finalizer_selector_sha256: str
    finalizer_schema_sha256: str
    interpreter: str
    interpreter_sha256: str
    dependency_manifest_sha256: str
    dependency_tree_sha256: str
    evaluator_dependency_tree_sha256: str
    evaluator_contract_sha256: str
    package_commit: str


@dataclass(frozen=True, slots=True)
class FinalizerExecutionOutcome:
    run_id: str
    finalized_root: Path
    completion_receipt_path: Path
    completion_receipt_sha256: str
    semantic_projection_sha256: str
    session_paths: tuple[Path, ...]
    consumed_raw_manifest_sha256: str
    consumed_raw_receipt_sha256: str
    consumed_raw_artifact_binding_sha256: str
    infrastructure_valid: bool


@dataclass(frozen=True, slots=True)
class EvaluatorExecutionRequest:
    run_id: str
    evaluator_run_id: str
    task_id: str
    task_index: int
    finalized_root: Path
    session_paths: tuple[Path, ...]
    finalized_artifacts: tuple[HeldArtifact, ...]
    finalized_artifact_binding_sha256: str
    evaluator_contract_path: str
    evaluator_contract_sha256: str
    package_commit: str


@dataclass(frozen=True, slots=True)
class EvaluatorExecutionOutcome:
    run_id: str
    evaluator_run_id: str
    consumed_finalized_root: Path
    consumed_session_sha256s: tuple[str, ...]
    consumed_finalized_artifact_binding_sha256: str
    evaluator_contract_sha256: str
    evaluator_valid: bool
    task_completed: bool
    answer_produced: bool
    score: float | None
    infrastructure_failure: bool
    missing_required_evidence: bool
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class CleanupExecutionRequest:
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    provider_handle: ProviderHandle | None
    transaction_root: Path
    held_transaction_root: HeldTransactionRoot
    authorization_reference: str | None
    authorization_source_sha256: str | None
    immutable_handoff_sha256: str
    empirical_prefix: tuple[str, ...]
    raw_prefix: tuple[str, ...]
    owned_instance_name: str
    owned_container_prefix: str
    started_wall_time: float
    started_monotonic: float
    cleanup_deadline_monotonic: float


@dataclass(frozen=True, slots=True)
class CleanupExecutionReceipt:
    immutable_handoff_sha256: str
    owned_containers_absent: bool
    exact_secret_matches: int
    structural_privacy_findings: tuple[str, ...]
    remote_secret_removed: bool
    firewall_restored: bool
    rulesets_restored: bool
    started_wall_time: float
    completed_wall_time: float
    started_monotonic: float
    completed_monotonic: float
    receipt_sha256: str


class LowLevelEffects(Protocol):
    """All environmental effects beneath the shared production policy wrapper."""

    @property
    def effect_protocol_version(self) -> str: ...

    @property
    def provider_contract_version(self) -> str: ...

    def implementation_identity(self) -> EffectImplementationIdentity: ...

    def runtime_clock(self) -> RuntimeClock: ...

    def transaction_root(self) -> Path: ...

    def read_model_secret(self) -> bytearray: ...

    def read_provider_secret(self) -> bytearray: ...

    def public_ipv4(self) -> str: ...

    def ssh_public_key(self) -> str: ...

    def metadata_channel(self) -> ModelMetadataChannel: ...

    def metadata_authorization_binding(
        self,
        *,
        contract: T09ProviderContract,
    ) -> Mapping[str, object]: ...

    def provider_inventory(self) -> tuple[str, ...] | None: ...

    def provider_launch(self, *, launch_ordinal: int) -> ProviderHandle: ...

    def provider_entry(self, handle: ProviderHandle) -> None: ...

    def provider_cost_receipt(
        self,
        request: ProviderCostObservationRequest,
    ) -> ProviderCostReceipt: ...

    def provider_terminate(self, handle: ProviderHandle) -> None: ...

    def campaign_transport(
        self,
        *,
        contract: T09ProviderContract,
        launch_ordinal: int,
        clock: RuntimeClock,
    ) -> provider.ProviderTransport: ...

    def campaign_scope(self) -> AbstractContextManager[None]: ...

    def campaign_low_level_controls(
        self,
    ) -> provider.ShadowCampaignLowLevelControls | None: ...

    def campaign_closeout_transport(
        self,
        *,
        contract: T09ProviderContract,
        launch_ordinal: int,
        handle: ProviderHandle,
        clock: RuntimeClock,
    ) -> provider.ProviderTransport: ...

    def retained_image_archive(self, *, launch_ordinal: int) -> Path | None: ...

    def stage_package(self, request: PackageStageRequest) -> PackageStageReceipt: ...

    def preflight_host(self, request: HostPreflightRequest) -> HostPreflightReceipt: ...

    def qualify_host(
        self,
        request: HostQualificationRequest,
    ) -> HostQualificationReceipt: ...

    def freeze_science(
        self,
        request: ScientificFreezeRequest,
    ) -> ScientificFreezeReceipt: ...

    def execute_condition(
        self,
        request: ConditionExecutionRequest,
        *,
        observer: ConditionEventObserver,
    ) -> ConditionExecutionResult: ...

    def preserve_condition_failure(
        self,
        request: ConditionFailurePreservationRequest,
    ) -> ConditionInfrastructureFailureOutcome: ...

    def export_condition_failure(
        self,
        request: ConditionFailureExportRequest,
    ) -> ConditionFailureExportReceipt: ...

    def finalize_condition(
        self,
        request: FinalizerExecutionRequest,
    ) -> FinalizerExecutionOutcome: ...

    def evaluate_condition(
        self,
        request: EvaluatorExecutionRequest,
    ) -> EvaluatorExecutionOutcome: ...

    def cleanup_transaction(
        self,
        request: CleanupExecutionRequest,
    ) -> CleanupExecutionReceipt: ...


@dataclass(slots=True)
class HeldEffectSource:
    """Exact tracked effect bytes held from registration through construction."""

    path: Path
    identity: EffectImplementationIdentity
    source_bytes: bytes = field(repr=False)
    device: int
    inode: int
    uid: int
    mode: int
    semantic_sha256: str
    _fd: int = field(repr=False, compare=False)
    _closed: bool = field(default=False, repr=False, compare=False)

    def revalidate(self, repository: Path) -> None:
        if self._closed:
            raise ValueError("held effect source is closed")
        named_fd = _open_absolute_no_symlinks(self.path, flags=os.O_RDONLY)
        try:
            held = os.fstat(self._fd)
            named = os.fstat(named_fd)
            expected = (
                self.device,
                self.inode,
                self.uid,
                self.mode,
                self.identity.bytes,
            )
            for metadata in (held, named):
                if (
                    (
                        metadata.st_dev,
                        metadata.st_ino,
                        metadata.st_uid,
                        stat.S_IMODE(metadata.st_mode),
                        metadata.st_size,
                    )
                    != expected
                    or not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_nlink != 1
                ):
                    raise ValueError("held effect source inode identity changed")
            held_bytes = _read_held_bytes(self._fd, byte_cap=MAX_PACKAGE_EFFECT_BYTES)
            named_bytes = _read_held_bytes(named_fd, byte_cap=MAX_PACKAGE_EFFECT_BYTES)
            tracked = _tracked_blob(repository, self.identity.path)
            if (
                held_bytes != self.source_bytes
                or named_bytes != self.source_bytes
                or tracked != self.source_bytes
                or hashlib.sha256(self.source_bytes).hexdigest() != self.identity.sha256
            ):
                raise ValueError("held effect source bytes changed")
        finally:
            os.close(named_fd)

    def close(self) -> None:
        if not self._closed:
            os.close(self._fd)
            self._closed = True

    def to_document(self) -> dict[str, object]:
        return {
            **self.identity.to_document(),
            "device": self.device,
            "inode": self.inode,
            "uid": self.uid,
            "mode": self.mode,
            "semantic_sha256": self.semantic_sha256,
            "compiled_from_held_bytes": True,
        }

    def to_public_document(self) -> dict[str, object]:
        """Return stable proof facts while keeping inode identity runtime-private."""

        document = {
            **self.identity.to_document(),
            "compiled_from_held_bytes": True,
            "git_blob_bytes_matched": True,
            "regular_current_user_single_link_safe_mode": True,
            "path_revalidated_after_execution_and_factory": True,
            "runtime_identity_values_retained": False,
        }
        document["public_attestation_semantic_sha256"] = _sha256(document)
        return document


@dataclass(slots=True)
class LoadedPackageEffects:
    effects: LowLevelEffects
    module: ModuleType
    identity: EffectImplementationIdentity
    held_source: HeldEffectSource
    held_transaction_root: HeldTransactionRoot

    def close(self) -> None:
        self.held_source.close()


def validate_package_effect_registration(
    repository: Path,
    contract: T09ProviderContract,
) -> EffectImplementationIdentity | None:
    """Validate a declaration without importing or instantiating its module."""

    held = hold_package_effect_registration(repository, contract)
    if held is None:
        return None
    try:
        return held.identity
    finally:
        held.close()


def hold_package_effect_registration(
    repository: Path,
    contract: T09ProviderContract,
) -> HeldEffectSource | None:
    """Hold the registered source descriptor before any authority or execution."""

    registration = contract.effect_registration
    if registration is None:
        return None
    root = repository.resolve(strict=True)
    relative = _safe_relative(registration.implementation_path, label="effect module path")
    path = root / relative
    fd = _open_absolute_no_symlinks(path, flags=os.O_RDONLY)
    try:
        metadata = os.fstat(fd)
        mode = stat.S_IMODE(metadata.st_mode)
        encoded = _read_held_bytes(fd, byte_cap=MAX_PACKAGE_EFFECT_BYTES)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or mode & 0o022
            or len(encoded) != registration.implementation_bytes
            or hashlib.sha256(encoded).hexdigest() != registration.implementation_sha256
            or _tracked_blob(root, relative) != encoded
            or registration.authority_grant_schema_version != EFFECT_AUTHORITY_SCHEMA_VERSION
        ):
            raise ValueError("declared effect module byte or filesystem identity drifted")
        identity = EffectImplementationIdentity(
            path=relative,
            bytes=len(encoded),
            sha256=registration.implementation_sha256,
            factory_entry_point=registration.factory_entry_point,
            protocol_version=registration.effect_protocol_version,
        )
        document = {
            **identity.to_document(),
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "uid": metadata.st_uid,
            "mode": mode,
        }
        held = HeldEffectSource(
            path=path,
            identity=identity,
            source_bytes=encoded,
            device=metadata.st_dev,
            inode=metadata.st_ino,
            uid=metadata.st_uid,
            mode=mode,
            semantic_sha256=_sha256(document),
            _fd=fd,
        )
        held.revalidate(root)
        return held
    except BaseException:
        os.close(fd)
        raise


def _load_exact_module(repository: Path, held: HeldEffectSource) -> ModuleType:
    """Compile and execute only bytes read from the already-held descriptor."""

    held.revalidate(repository)
    module_name = "giclab_package_effect_" + held.semantic_sha256
    module = ModuleType(module_name)
    module.__file__ = held.path.as_posix()
    module.__package__ = ""
    module.__loader__ = None
    module.__spec__ = None
    sys.modules.pop(module_name, None)
    sys.modules[module_name] = module
    try:
        code = compile(
            held.source_bytes,
            held.path.as_posix(),
            "exec",
            dont_inherit=True,
        )
        exec(code, module.__dict__)
        held.revalidate(repository)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def load_registered_package_effects(
    repository: Path,
    contract: T09ProviderContract,
    *,
    authorization_context: EffectAuthorizationContext,
    authority: EffectAuthorityGrant,
    held_source: HeldEffectSource,
) -> LoadedPackageEffects:
    """Load only the exact declared factory after external authority validation."""

    if not isinstance(authority, ValidatedLiveEffectAuthority):
        raise ValueError("only opaque validated authority can instantiate live effects")
    identity = held_source.identity
    registration = contract.effect_registration
    if registration is None or (
        identity.path,
        identity.bytes,
        identity.sha256,
        identity.factory_entry_point,
        identity.protocol_version,
    ) != (
        registration.implementation_path,
        registration.implementation_bytes,
        registration.implementation_sha256,
        registration.factory_entry_point,
        registration.effect_protocol_version,
    ):
        raise ValueError("held source does not match the selected package registration")
    root = repository.resolve(strict=True)
    held_source.revalidate(root)
    held_transaction_root = authority.held_transaction_root
    if (
        authorization_context.authority_kind is not EffectAuthorityKind.LIVE_AUTHORIZED
        or (authorization_context.control_commit, authorization_context.control_tree)
        != _git_identity(repository.resolve(strict=True))
        or authorization_context.provider_contract_version != contract.version
        or authorization_context.plan_id != contract.plan_id
        or authorization_context.plan_sha256 != contract.expected_plan_sha256
        or authorization_context.command_package_sha256 != contract.expected_command_manifest_sha256
        or authorization_context.effect_implementation != identity
        or not authority.is_valid_for(authorization_context)
        or authorization_context.transaction_root_identity != held_transaction_root.semantic_sha256
    ):
        raise ValueError("external effect authority does not bind the declared package")
    module = _load_exact_module(root, held_source)
    try:
        factory = getattr(module, identity.factory_entry_point, None)
        if not inspect.isfunction(factory) or factory.__module__ != module.__name__:
            raise ValueError("declared effect factory is absent or belongs to another module")
        signature = inspect.signature(factory)
        expected_parameters = (
            "repository",
            "contract",
            "authorization_context",
            "authority",
            "held_transaction_root",
        )
        if tuple(signature.parameters) != expected_parameters or any(
            parameter.kind is not inspect.Parameter.KEYWORD_ONLY
            or parameter.default is not inspect.Parameter.empty
            for parameter in signature.parameters.values()
        ):
            raise ValueError("declared effect factory signature is not exact")
        effects = factory(
            repository=repository.resolve(strict=True),
            contract=contract,
            authorization_context=authorization_context,
            authority=authority,
            held_transaction_root=held_transaction_root,
        )
        required_methods = (
            "implementation_identity",
            "runtime_clock",
            "transaction_root",
            "read_model_secret",
            "read_provider_secret",
            "public_ipv4",
            "ssh_public_key",
            "metadata_channel",
            "metadata_authorization_binding",
            "provider_inventory",
            "provider_launch",
            "provider_entry",
            "provider_cost_receipt",
            "provider_terminate",
            "campaign_transport",
            "campaign_scope",
            "campaign_low_level_controls",
            "campaign_closeout_transport",
            "retained_image_archive",
            "stage_package",
            "preflight_host",
            "qualify_host",
            "freeze_science",
            "execute_condition",
            "preserve_condition_failure",
            "export_condition_failure",
            "finalize_condition",
            "evaluate_condition",
            "cleanup_transaction",
        )
        if any(not callable(getattr(effects, name, None)) for name in required_methods):
            raise ValueError("declared effect factory returned an incomplete implementation")
        if (
            getattr(effects, "effect_protocol_version", None) != EFFECT_PROTOCOL_VERSION
            or getattr(effects, "provider_contract_version", None) != contract.version
            or effects.implementation_identity() != identity
            or effects.transaction_root() != held_transaction_root.path
        ):
            raise ValueError("loaded package effects contradict their exact declaration")
        clock = effects.runtime_clock()
        if not isinstance(clock, RuntimeClock):
            raise ValueError("loaded package effects lack the runtime clock protocol")
        held_source.revalidate(root)
        held_transaction_root.revalidate()
    except BaseException:
        sys.modules.pop(module.__name__, None)
        raise
    return LoadedPackageEffects(
        effects=effects,
        module=module,
        identity=identity,
        held_source=held_source,
        held_transaction_root=held_transaction_root,
    )


def finite_time(value: object, *, label: str) -> float:
    """Validate one time-domain sample without changing domains."""

    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise ValueError(f"{label} must be finite and non-negative")
    return float(value)


def checked_deadline(start: float, seconds: float, *, label: str) -> float:
    """Create one finite same-domain deadline and fail closed on overflow."""

    origin = finite_time(start, label=f"{label} start")
    duration = finite_time(seconds, label=f"{label} duration")
    deadline = origin + duration
    if not math.isfinite(deadline) or deadline < origin:
        raise ValueError(f"{label} deadline overflowed")
    return deadline


def repository_effect_identity(
    path: Path,
    *,
    repository: Path,
    factory: str,
) -> EffectImplementationIdentity:
    """Return an exact identity for a tracked deterministic effect module."""

    root = repository.resolve(strict=True)
    canonical = Path(os.path.abspath(path))
    try:
        relative = canonical.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("effect implementation is outside the repository") from exc
    fd = _open_absolute_no_symlinks(canonical, flags=os.O_RDONLY)
    try:
        metadata = os.fstat(fd)
        mode = stat.S_IMODE(metadata.st_mode)
        encoded = _read_held_bytes(fd, byte_cap=MAX_PACKAGE_EFFECT_BYTES)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or mode & 0o022
        ):
            raise ValueError("deterministic effect implementation identity is not exact")
        return EffectImplementationIdentity(
            path=relative,
            bytes=len(encoded),
            sha256=hashlib.sha256(encoded).hexdigest(),
            factory_entry_point=factory,
            protocol_version=EFFECT_PROTOCOL_VERSION,
        )
    finally:
        os.close(fd)
