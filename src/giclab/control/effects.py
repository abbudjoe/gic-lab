"""Effect-neutral low-level contracts for the shared Category 3 production assembly.

This module defines capability surfaces; it performs no provider, host, browser,
scientific, or credential-bearing operation.  A package-specific module may
implement these protocols only after an external grant validates one exact
``EffectAuthorizationContext``.  The shared package can mint shadow authority only.
"""

from __future__ import annotations

import hashlib
import importlib.util
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
from typing import TYPE_CHECKING, Final, Protocol, TypeVar, runtime_checkable

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
        timeout=10,
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
class EffectAuthorizationContext:
    """One fully bound transaction context presented to an external grant."""

    authority_kind: EffectAuthorityKind
    execution_mode: EffectExecutionMode
    control_commit: str
    control_tree: str
    provider_contract_version: str
    plan_id: str
    plan_sha256: str
    command_package_sha256: str
    control_binding_semantic_sha256: str
    effect_implementation: EffectImplementationIdentity
    transaction_root_identity: str
    external_authorization_reference: str | None
    external_authorization_source_sha256: str | None
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
            "plan_sha256": self.plan_sha256,
            "command_package_sha256": self.command_package_sha256,
            "control_binding_semantic_sha256": self.control_binding_semantic_sha256,
            "effect_implementation": self.effect_implementation.to_document(),
            "transaction_root_identity": self.transaction_root_identity,
            "external_authorization_reference": self.external_authorization_reference,
            "external_authorization_source_sha256": (self.external_authorization_source_sha256),
        }

    @property
    def semantic_sha256(self) -> str:
        return _sha256(self.to_document())


class EffectAuthorityGrant(Protocol):
    """Externally validated authority interface; shared code has no live factory."""

    @property
    def kind(self) -> EffectAuthorityKind: ...

    @property
    def source(self) -> str: ...

    def authorizes(self, context: EffectAuthorizationContext) -> bool: ...


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


@dataclass(frozen=True, slots=True)
class ProviderHandle:
    opaque_identity: str
    launch_ordinal: int

    def __post_init__(self) -> None:
        if _SAFE_ID.fullmatch(self.opaque_identity) is None or self.launch_ordinal <= 0:
            raise ValueError("provider handle is malformed")


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
    infrastructure_valid: bool


@dataclass(frozen=True, slots=True)
class EvaluatorExecutionRequest:
    run_id: str
    evaluator_run_id: str
    task_id: str
    task_index: int
    finalized_root: Path
    session_paths: tuple[Path, ...]
    evaluator_contract_path: str
    evaluator_contract_sha256: str
    package_commit: str


@dataclass(frozen=True, slots=True)
class EvaluatorExecutionOutcome:
    run_id: str
    evaluator_run_id: str
    consumed_finalized_root: Path
    consumed_session_sha256s: tuple[str, ...]
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

    def transaction_root_identity(self) -> str: ...

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
    ) -> ConditionProcessOutcome: ...

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


@dataclass(frozen=True, slots=True)
class LoadedPackageEffects:
    effects: LowLevelEffects
    module: ModuleType
    identity: EffectImplementationIdentity


def validate_package_effect_registration(
    repository: Path,
    contract: T09ProviderContract,
) -> EffectImplementationIdentity | None:
    """Validate a declaration without importing or instantiating its module."""

    registration = contract.effect_registration
    if registration is None:
        return None
    root = repository.resolve(strict=True)
    relative = _safe_relative(registration.implementation_path, label="effect module path")
    path = root / relative
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ValueError("declared effect module is unavailable") from exc
    resolved = path.resolve(strict=True)
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or root not in resolved.parents
        or resolved != path.absolute()
    ):
        raise ValueError("declared effect module path is unsafe")
    encoded = path.read_bytes()
    if (
        len(encoded) != registration.implementation_bytes
        or len(encoded) > MAX_PACKAGE_EFFECT_BYTES
        or hashlib.sha256(encoded).hexdigest() != registration.implementation_sha256
        or _tracked_blob(root, relative) != encoded
    ):
        raise ValueError("declared effect module byte identity drifted")
    identity = EffectImplementationIdentity(
        path=relative,
        bytes=len(encoded),
        sha256=registration.implementation_sha256,
        factory_entry_point=registration.factory_entry_point,
        protocol_version=registration.effect_protocol_version,
    )
    if registration.authority_grant_schema_version != EFFECT_AUTHORITY_SCHEMA_VERSION:
        raise ValueError("declared authority-grant schema version is unsupported")
    return identity


def _load_exact_module(path: Path, identity: EffectImplementationIdentity) -> ModuleType:
    module_name = "giclab_package_effect_" + identity.sha256
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        raise ValueError("declared effect module cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    try:
        specification.loader.exec_module(module)
        origin = Path(str(getattr(module.__spec__, "origin", ""))).resolve(strict=True)
        if origin != path.resolve(strict=True):
            raise ValueError("loaded effect module origin drifted")
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
) -> LoadedPackageEffects:
    """Load only the exact declared factory after external authority validation."""

    if authority.kind is not EffectAuthorityKind.LIVE_AUTHORIZED:
        raise ValueError("shadow authority cannot instantiate package live effects")
    identity = validate_package_effect_registration(repository, contract)
    if identity is None:
        raise ValueError("selected package declares no live effect implementation")
    if (
        authorization_context.authority_kind is not EffectAuthorityKind.LIVE_AUTHORIZED
        or (authorization_context.control_commit, authorization_context.control_tree)
        != _git_identity(repository.resolve(strict=True))
        or authorization_context.provider_contract_version != contract.version
        or authorization_context.plan_id != contract.plan_id
        or authorization_context.plan_sha256 != contract.expected_plan_sha256
        or authorization_context.command_package_sha256 != contract.expected_command_manifest_sha256
        or authorization_context.effect_implementation != identity
        or not authority.authorizes(authorization_context)
    ):
        raise ValueError("external effect authority does not bind the declared package")
    path = repository.resolve(strict=True) / identity.path
    module = _load_exact_module(path, identity)
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
        )
        required_methods = (
            "implementation_identity",
            "runtime_clock",
            "transaction_root",
            "transaction_root_identity",
            "read_model_secret",
            "read_provider_secret",
            "public_ipv4",
            "ssh_public_key",
            "metadata_channel",
            "metadata_authorization_binding",
            "provider_inventory",
            "provider_launch",
            "provider_entry",
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
            or effects.transaction_root_identity()
            != authorization_context.transaction_root_identity
        ):
            raise ValueError("loaded package effects contradict their exact declaration")
        clock = effects.runtime_clock()
        if not isinstance(clock, RuntimeClock):
            raise ValueError("loaded package effects lack the runtime clock protocol")
        root = effects.transaction_root().resolve(strict=True)
        if not root.is_dir() or root.is_symlink() or stat.S_IMODE(root.stat().st_mode) & 0o022:
            raise ValueError("loaded package effects expose an unsafe transaction root")
    except BaseException:
        sys.modules.pop(module.__name__, None)
        raise
    return LoadedPackageEffects(effects=effects, module=module, identity=identity)


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
    resolved = path.resolve(strict=True)
    if root not in resolved.parents or resolved.is_symlink() or not resolved.is_file():
        raise ValueError("effect implementation is outside the repository")
    relative = resolved.relative_to(root).as_posix()
    encoded = resolved.read_bytes()
    return EffectImplementationIdentity(
        path=relative,
        bytes=len(encoded),
        sha256=hashlib.sha256(encoded).hexdigest(),
        factory_entry_point=factory,
        protocol_version=EFFECT_PROTOCOL_VERSION,
    )
