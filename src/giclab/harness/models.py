"""Typed records shared by local and future cloud experiment execution."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import TypeAlias, cast

from .safety import (
    assert_no_secret_literals,
    contains_recognizable_secret,
    looks_secret_name,
    validate_environment_name,
)

SCHEMA_VERSION = "0.1.0"
LEGACY_HARNESS_EVENT_SCHEMA_VERSION = "0.1.0"
HARNESS_EVENT_SCHEMA_VERSION = "0.2.0"
SUPPORTED_HARNESS_EVENT_SCHEMA_VERSIONS = frozenset(
    {LEGACY_HARNESS_EVENT_SCHEMA_VERSION, HARNESS_EVENT_SCHEMA_VERSION}
)

_EXPERIMENT_ID = re.compile(r"^EXP-[0-9]{4}$")
_RUN_ID = re.compile(r"^RUN-[A-Z0-9][A-Z0-9._-]{5,127}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_AUTHORIZATION_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}$")

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
FrozenJsonValue: TypeAlias = (
    JsonScalar | tuple["FrozenJsonValue", ...] | Mapping[str, "FrozenJsonValue"]
)
EventInputValue: TypeAlias = JsonValue | FrozenJsonValue


class RunProfile(StrEnum):
    """Evidence profile for one execution."""

    SMOKE = "smoke"
    PILOT = "pilot"
    CONFIRMATORY = "confirmatory"


class WorkloadKind(StrEnum):
    """Project-state permission needed by one run."""

    PROTOTYPE = "prototype"
    BENCHMARK = "benchmark"
    TRAINING = "training"


class ExecutionBackend(StrEnum):
    """Execution control plane selected by a run plan."""

    LOCAL_SUBPROCESS = "local-subprocess"
    CLOUD = "cloud"


class IncrementalLimitEnforcement(StrEnum):
    """How non-wall resource maxima are enforced inside an adapter command."""

    NOT_APPLICABLE = "not-applicable"
    ADAPTER_COMMAND = "adapter-command"


class NonWallResource(StrEnum):
    """Non-wall units that a subprocess may consume."""

    COST_USD = "cost_usd"
    GPU_HOURS = "gpu_hours"
    MODEL_TOKENS = "model_tokens"
    TOOL_CALLS = "tool_calls"


class EventProvenance(StrEnum):
    """How a normalized event field was obtained."""

    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"
    UNAVAILABLE = "unavailable"


class EventType(StrEnum):
    """Canonical append-only harness event types."""

    RUN_STARTED = "run_started"
    PREFLIGHT_COMPLETED = "preflight_completed"
    COMMAND_STARTED = "command_started"
    COMMAND_COMPLETED = "command_completed"
    REGULATION_DECISION = "regulation_decision"
    OBSERVATION = "observation"
    BELIEF_STATE = "belief_state"
    CANDIDATE_ACTION = "candidate_action"
    PREDICTED_FUTURE = "predicted_future"
    CRITIC_EVALUATION = "critic_evaluation"
    PLAN = "plan"
    EXECUTED_ACTION = "executed_action"
    OUTCOME = "outcome"
    METRIC = "metric"
    BUDGET_UPDATE = "budget_update"
    ARTIFACT_RECORDED = "artifact_recorded"
    WARNING = "warning"
    ERROR = "error"
    RUN_STOPPED = "run_stopped"
    CLOUD_INSTANCE_LAUNCHED = "cloud_instance_launched"
    CLOUD_INSTANCE_TERMINATED = "cloud_instance_terminated"


class AdapterEventType(StrEnum):
    """Canonical scientific event types that a source adapter may emit."""

    REGULATION_DECISION = "regulation_decision"
    OBSERVATION = "observation"
    BELIEF_STATE = "belief_state"
    CANDIDATE_ACTION = "candidate_action"
    PREDICTED_FUTURE = "predicted_future"
    CRITIC_EVALUATION = "critic_evaluation"
    PLAN = "plan"
    EXECUTED_ACTION = "executed_action"
    OUTCOME = "outcome"
    METRIC = "metric"


def _require_nonempty(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must not be empty")


def _require_secret_safe(value: str, label: str) -> None:
    if contains_recognizable_secret(value):
        raise ValueError(f"{label} contains recognizable credential material")


def _require_nonnegative_finite(value: float, label: str) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and non-negative")


def _validate_utc_timestamp(value: str, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO 8601 date-time") from exc
    offset = parsed.utcoffset()
    if parsed.tzinfo is None or offset is None:
        raise ValueError(f"{label} must include a UTC offset")
    if offset.total_seconds() != 0:
        raise ValueError(f"{label} must be UTC")


def _freeze_json(value: JsonValue) -> FrozenJsonValue:
    if isinstance(value, str):
        _require_secret_safe(value, "event payload")
        return value
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})


def _validate_json_keys(value: EventInputValue | Mapping[str, EventInputValue]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("event payload object keys must be strings")
            _require_secret_safe(key, "event payload key")
            _validate_json_keys(item)
    elif isinstance(value, list | tuple):
        for item in value:
            _validate_json_keys(item)


def thaw_json(value: EventInputValue) -> JsonValue:
    """Return ordinary JSON containers from recursively immutable event data."""

    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    if isinstance(value, list):
        return [thaw_json(item) for item in value]
    return value


def _copy_json_mapping(
    payload: Mapping[str, EventInputValue],
) -> Mapping[str, FrozenJsonValue]:
    _validate_json_keys(payload)
    try:
        serializable = {key: thaw_json(value) for key, value in payload.items()}
        encoded = json.dumps(serializable, allow_nan=False, sort_keys=True)
        copied = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError("event payload must contain finite JSON values") from exc
    if not isinstance(copied, dict):  # pragma: no cover - Mapping always encodes as an object
        raise ValueError("event payload must be an object")
    copied_mapping = cast(dict[str, JsonValue], copied)
    return MappingProxyType({key: _freeze_json(value) for key, value in copied_mapping.items()})


@dataclass(frozen=True, slots=True)
class RunIdentity:
    """Immutable identity for one execution attempt."""

    experiment_id: str
    run_id: str
    condition: str
    attempt: int = 1
    seed: int | None = None

    def __post_init__(self) -> None:
        if _EXPERIMENT_ID.fullmatch(self.experiment_id) is None:
            raise ValueError(f"invalid experiment id: {self.experiment_id}")
        if _RUN_ID.fullmatch(self.run_id) is None:
            raise ValueError(f"invalid run id: {self.run_id}")
        _require_nonempty(self.condition, "condition")
        _require_secret_safe(self.condition, "condition")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("attempt must be an integer >= 1")
        if self.seed is not None and (type(self.seed) is not int or self.seed < 0):
            raise ValueError("seed must be a non-negative integer or null")


@dataclass(frozen=True, slots=True)
class SourceVersions:
    """Pinned source and environment identity for a run."""

    giclab_commit: str
    upstream_source_id: str
    upstream_commit: str
    protocol_sha256: str
    config_sha256: str
    model_revision: str | None
    dataset_revision: str | None
    environment_sha256: str

    def __post_init__(self) -> None:
        if self.giclab_commit != "unknown" and _COMMIT.fullmatch(self.giclab_commit) is None:
            raise ValueError(
                "giclab_commit must be a 40-character lowercase Git commit or 'unknown'"
            )
        _require_nonempty(self.upstream_source_id, "upstream_source_id")
        _require_secret_safe(self.upstream_source_id, "upstream_source_id")
        if self.upstream_commit != "unknown" and _COMMIT.fullmatch(self.upstream_commit) is None:
            raise ValueError(
                "upstream_commit must be a 40-character lowercase Git commit or 'unknown'"
            )
        for label, digest in (
            ("protocol_sha256", self.protocol_sha256),
            ("config_sha256", self.config_sha256),
            ("environment_sha256", self.environment_sha256),
        ):
            if digest != "unknown" and _SHA256.fullmatch(digest) is None:
                raise ValueError(f"{label} must be a lowercase SHA-256 digest or 'unknown'")
        for label, revision in (
            ("model_revision", self.model_revision),
            ("dataset_revision", self.dataset_revision),
        ):
            if revision is not None:
                _require_nonempty(revision, label)
                _require_secret_safe(revision, label)

    @property
    def unknown_fields(self) -> tuple[str, ...]:
        """Return source identities that were explicitly recorded as unavailable."""

        return tuple(
            label
            for label, value in (
                ("giclab_commit", self.giclab_commit),
                ("upstream_commit", self.upstream_commit),
                ("protocol_sha256", self.protocol_sha256),
                ("config_sha256", self.config_sha256),
                ("environment_sha256", self.environment_sha256),
            )
            if value == "unknown"
        )


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    """Explicit human authorization attached to one run plan."""

    authorized: bool = False
    authorization_reference: str | None = None
    command_sha256: str | None = None

    def __post_init__(self) -> None:
        if type(self.authorized) is not bool:
            raise ValueError("authorized must be a boolean")
        if self.authorized:
            if self.authorization_reference is None:
                raise ValueError("authorized runs require an authorization reference")
            _require_nonempty(self.authorization_reference, "authorization_reference")
            if _AUTHORIZATION_REFERENCE.fullmatch(self.authorization_reference) is None:
                raise ValueError("authorization_reference must be a secret-safe stable identifier")
            _require_secret_safe(self.authorization_reference, "authorization_reference")
            if self.command_sha256 is None or _SHA256.fullmatch(self.command_sha256) is None:
                raise ValueError("authorized runs require a command_sha256 binding")
        elif self.authorization_reference is not None or self.command_sha256 is not None:
            raise ValueError("unauthorized runs cannot contain authorization bindings")


@dataclass(frozen=True, slots=True)
class ExecutionContract:
    """Typed mapping from a run to repository execution permissions."""

    backend: ExecutionBackend
    workload: WorkloadKind
    authorization: ExecutionAuthorization = field(default_factory=ExecutionAuthorization)


@dataclass(frozen=True, slots=True)
class RunBudget:
    """Immutable hard maximums for one run."""

    max_wall_seconds: int
    max_cost_usd: float
    max_gpu_hours: float = 0.0
    max_model_tokens: int | None = None
    max_tool_calls: int | None = None
    max_output_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        if type(self.max_wall_seconds) is not int or self.max_wall_seconds <= 0:
            raise ValueError("max_wall_seconds must be an integer > 0")
        _require_nonnegative_finite(self.max_cost_usd, "max_cost_usd")
        _require_nonnegative_finite(self.max_gpu_hours, "max_gpu_hours")
        if self.max_model_tokens is not None and (
            type(self.max_model_tokens) is not int or self.max_model_tokens < 0
        ):
            raise ValueError("max_model_tokens must be a non-negative integer or null")
        if self.max_tool_calls is not None and (
            type(self.max_tool_calls) is not int or self.max_tool_calls < 0
        ):
            raise ValueError("max_tool_calls must be a non-negative integer or null")
        if type(self.max_output_bytes) is not int or self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be an integer > 0")


@dataclass(frozen=True, slots=True)
class BudgetUsage:
    """Observed resource use for one run."""

    wall_seconds: float = 0.0
    cost_usd: float = 0.0
    gpu_hours: float = 0.0
    model_tokens: int = 0
    tool_calls: int = 0
    output_bytes: int = 0

    def __post_init__(self) -> None:
        for label, value in (
            ("wall_seconds", self.wall_seconds),
            ("cost_usd", self.cost_usd),
            ("gpu_hours", self.gpu_hours),
        ):
            _require_nonnegative_finite(value, label)
        for label, value in (
            ("model_tokens", self.model_tokens),
            ("tool_calls", self.tool_calls),
            ("output_bytes", self.output_bytes),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class NonWallResourceAccounting:
    """Explicit observed values or ``None`` attestations when a unit is unavailable."""

    cost_usd: float | None
    gpu_hours: float | None
    model_tokens: int | None
    tool_calls: int | None

    def __post_init__(self) -> None:
        for label, value in (
            ("accounted cost_usd", self.cost_usd),
            ("accounted gpu_hours", self.gpu_hours),
        ):
            if value is not None:
                _require_nonnegative_finite(value, label)
        for label, value in (
            ("accounted model_tokens", self.model_tokens),
            ("accounted tool_calls", self.tool_calls),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{label} must be a non-negative integer or unavailable")


@dataclass(frozen=True, slots=True)
class ResourceProjection:
    """Before-action upper bounds for resources the local runner cannot meter inline."""

    cost_usd: float = 0.0
    gpu_hours: float = 0.0
    model_tokens: int = 0
    tool_calls: int = 0
    enforcement: IncrementalLimitEnforcement = IncrementalLimitEnforcement.NOT_APPLICABLE
    unbounded_applicable: tuple[NonWallResource, ...] = ()

    def __post_init__(self) -> None:
        _require_nonnegative_finite(self.cost_usd, "projected cost_usd")
        _require_nonnegative_finite(self.gpu_hours, "projected gpu_hours")
        for label, value in (
            ("projected model_tokens", self.model_tokens),
            ("projected tool_calls", self.tool_calls),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        if not isinstance(self.enforcement, IncrementalLimitEnforcement):
            raise ValueError("resource projection enforcement must be typed")
        if any(not isinstance(unit, NonWallResource) for unit in self.unbounded_applicable):
            raise ValueError("unbounded applicable resources must be typed")
        unbounded = tuple(sorted(set(self.unbounded_applicable), key=lambda unit: unit.value))
        if len(unbounded) != len(self.unbounded_applicable):
            raise ValueError("unbounded applicable resources must be unique")
        projected_by_unit: Mapping[NonWallResource, float | int] = {
            NonWallResource.COST_USD: self.cost_usd,
            NonWallResource.GPU_HOURS: self.gpu_hours,
            NonWallResource.MODEL_TOKENS: self.model_tokens,
            NonWallResource.TOOL_CALLS: self.tool_calls,
        }
        contradictory = [unit.value for unit in unbounded if projected_by_unit[unit] != 0]
        if contradictory:
            raise ValueError(
                "resources cannot be both finitely projected and applicable-unbounded: "
                + ", ".join(contradictory)
            )
        if self.has_usage and self.enforcement is not IncrementalLimitEnforcement.ADAPTER_COMMAND:
            raise ValueError(
                "nonzero resource projections require adapter-command hard-limit enforcement"
            )
        object.__setattr__(self, "unbounded_applicable", unbounded)

    @property
    def has_usage(self) -> bool:
        return any(
            (
                self.cost_usd > 0,
                self.gpu_hours > 0,
                self.model_tokens > 0,
                self.tool_calls > 0,
            )
        )

    @property
    def has_unbounded_applicable(self) -> bool:
        """Return whether an applicable unit lacks a finite command-level upper bound."""

        return bool(self.unbounded_applicable)

    def observed_violations(self, usage: BudgetUsage) -> tuple[str, ...]:
        violations: list[str] = []
        if usage.cost_usd > self.cost_usd:
            violations.append("cost_usd")
        if usage.gpu_hours > self.gpu_hours:
            violations.append("gpu_hours")
        if usage.model_tokens > self.model_tokens:
            violations.append("model_tokens")
        if usage.tool_calls > self.tool_calls:
            violations.append("tool_calls")
        return tuple(violations)


@dataclass(frozen=True, slots=True)
class InheritedEnvironmentBinding:
    """Digest-bound non-secret host environment input."""

    name: str
    value_sha256: str

    def __post_init__(self) -> None:
        validate_environment_name(self.name)
        _require_secret_safe(self.name, "inherited environment variable name")
        if looks_secret_name(self.name):
            raise ValueError(
                f"inherited environment variable {self.name!r} is secret-bearing; "
                "use secret_environment"
            )
        if _SHA256.fullmatch(self.value_sha256) is None:
            raise ValueError("inherited environment value_sha256 must be a SHA-256 digest")


def inherited_environment_binding(name: str, value: str) -> InheritedEnvironmentBinding:
    """Bind a non-secret inherited value without serializing the value itself."""

    if "\0" in value:
        raise ValueError("inherited environment values must not contain NUL bytes")
    return InheritedEnvironmentBinding(
        name=name,
        value_sha256=hashlib.sha256(value.encode("utf-8")).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class InputTreeBinding:
    """Content identity for one command input tree, rechecked before launch."""

    root: Path
    sha256: str
    excluded_roots: tuple[PurePosixPath, ...] = ()
    git_commit: str | None = None

    def __post_init__(self) -> None:
        root = self.root
        if not root.is_absolute():
            raise ValueError("input tree root must be an absolute path")
        try:
            resolved = root.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise ValueError("input tree root must resolve safely") from exc
        if resolved != root:
            raise ValueError("input tree root must be a canonical path")
        if root.exists() and (root.is_symlink() or not root.is_dir()):
            raise ValueError("input tree root must remain a non-symlink directory")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("input tree sha256 must be a lowercase SHA-256 digest")
        if self.git_commit is not None and _COMMIT.fullmatch(self.git_commit) is None:
            raise ValueError("input tree git_commit must be a lowercase 40-character commit")
        exclusions = tuple(sorted(set(self.excluded_roots), key=lambda item: item.as_posix()))
        if len(exclusions) != len(self.excluded_roots):
            raise ValueError("input tree excluded roots must be unique")
        for exclusion in exclusions:
            if (
                exclusion.is_absolute()
                or not exclusion.parts
                or any(part in {"", ".", ".."} for part in exclusion.parts)
            ):
                raise ValueError("input tree exclusions must be traversal-free relative paths")
            _require_secret_safe(exclusion.as_posix(), "input tree exclusion")
        _require_secret_safe(str(root), "input tree root")
        object.__setattr__(self, "excluded_roots", exclusions)


def _is_excluded_tree_path(
    relative: PurePosixPath,
    excluded_roots: tuple[PurePosixPath, ...],
) -> bool:
    return any(relative == excluded or excluded in relative.parents for excluded in excluded_roots)


def input_tree_sha256(
    root: Path,
    excluded_roots: tuple[PurePosixPath, ...] = (),
) -> str:
    """Hash path names, entry types, and bytes without following links."""

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if _is_excluded_tree_path(relative, excluded_roots):
            continue
        encoded_path = relative.as_posix().encode("utf-8")
        if path.is_symlink():
            raise ValueError("input tree must not contain symlinks")
        if path.is_dir():
            digest.update(b"D\0" + encoded_path + b"\0")
            continue
        if not path.is_file():
            raise ValueError("input tree must contain only directories and regular files")
        digest.update(b"F\0" + encoded_path + b"\0")
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def input_tree_binding(
    root: Path,
    *,
    excluded_roots: tuple[PurePosixPath, ...] = (),
    git_commit: str | None = None,
) -> InputTreeBinding:
    """Capture one canonical input tree for authorization and prelaunch recheck."""

    if root.is_symlink():
        raise ValueError("input tree root must not be a symlink")
    try:
        resolved = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("input tree root must resolve to an existing directory") from exc
    return InputTreeBinding(
        root=resolved,
        sha256=input_tree_sha256(resolved, excluded_roots),
        excluded_roots=excluded_roots,
        git_commit=git_commit,
    )


@dataclass(frozen=True, slots=True)
class OwnedOutputRoot:
    """Canonical command output root that must belong to the exact run attempt."""

    root: Path

    def __post_init__(self) -> None:
        root = self.root
        if not root.is_absolute() or "\0" in str(root):
            raise ValueError("owned output root must be an absolute path without NUL bytes")
        try:
            resolved = root.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise ValueError("owned output root must resolve safely") from exc
        if resolved != root:
            raise ValueError("owned output root must be a canonical path")
        if root.exists() and (root.is_symlink() or not root.is_dir()):
            raise ValueError("owned output root must remain a non-symlink directory")
        _require_secret_safe(str(root), "owned output root")


@dataclass(frozen=True, slots=True)
class WorkingDirectoryIdentity:
    """Filesystem identity of the authorization-bound effective working directory."""

    device: int
    inode: int

    def __post_init__(self) -> None:
        for label, value in (("device", self.device), ("inode", self.inode)):
            if type(value) is not int or value < 0:
                raise ValueError(f"working-directory {label} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ArtifactPolicy:
    """Run-plan artifact location relative to an operator-configured workspace."""

    root: Path
    retain_raw: bool = True

    def __post_init__(self) -> None:
        if self.root.is_absolute() or not self.root.parts:
            raise ValueError("artifact root must be a nonempty relative path")
        if any(part in {"", ".", ".."} for part in self.root.parts):
            raise ValueError("artifact root must not contain empty, dot, or parent components")
        _require_secret_safe(self.root.as_posix(), "artifact root")
        if self.retain_raw is not True:
            raise ValueError("retain_raw must be true")


@dataclass(frozen=True, slots=True)
class RunPlan:
    """Validated execution contract for one run."""

    identity: RunIdentity
    profile: RunProfile
    interpretation_allowed: bool
    execution: ExecutionContract
    sources: SourceVersions
    budget: RunBudget
    artifacts: ArtifactPolicy

    def __post_init__(self) -> None:
        if type(self.interpretation_allowed) is not bool:
            raise ValueError("interpretation_allowed must be a boolean")
        if self.profile is RunProfile.SMOKE and self.interpretation_allowed:
            raise ValueError("smoke runs cannot permit scientific interpretation")


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Shell-free subprocess contract with named credential injection."""

    argv: tuple[str, ...]
    cwd: Path
    timeout_seconds: int
    cwd_identity: WorkingDirectoryIdentity | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    inherit_environment: tuple[InheritedEnvironmentBinding, ...] = ()
    secret_environment: tuple[str, ...] = ()
    input_trees: tuple[InputTreeBinding, ...] = ()
    owned_output_roots: tuple[OwnedOutputRoot, ...] = ()
    unowned_output_patterns: tuple[PurePosixPath, ...] = ()
    resource_projection: ResourceProjection = field(default_factory=ResourceProjection)
    executable_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.argv or any(not isinstance(part, str) or not part for part in self.argv):
            raise ValueError("argv must contain nonempty string arguments")
        if any("\0" in part for part in self.argv):
            raise ValueError("argv must not contain NUL bytes")
        if type(self.timeout_seconds) is not int or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be an integer > 0")
        assert_no_secret_literals(self.argv, self.environment.items())
        copied_environment = dict(self.environment)
        if any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in copied_environment.items()
        ):
            raise ValueError("literal environment entries must map strings to strings")
        if any("\0" in value for value in copied_environment.values()):
            raise ValueError("literal environment values must not contain NUL bytes")
        cwd = self.cwd
        if "\0" in str(cwd):
            raise ValueError("command cwd must not contain NUL bytes")
        expected_cwd_identity = self.cwd_identity
        if expected_cwd_identity is None:
            if cwd.is_symlink():
                raise ValueError("command cwd must not be a symlink")
            try:
                cwd = cwd.resolve(strict=True)
            except (OSError, ValueError) as exc:
                raise ValueError(f"cannot resolve command cwd: {cwd}") from exc
            if not cwd.is_dir():
                raise ValueError("command cwd must resolve to an existing directory")
            metadata = cwd.stat()
            expected_cwd_identity = WorkingDirectoryIdentity(
                device=metadata.st_dev,
                inode=metadata.st_ino,
            )
        elif not isinstance(expected_cwd_identity, WorkingDirectoryIdentity):
            raise ValueError("cwd_identity must be a typed working-directory identity")
        elif not cwd.is_absolute():
            raise ValueError("retained command cwd must be an absolute path")
        object.__setattr__(self, "cwd", cwd)
        object.__setattr__(self, "cwd_identity", expected_cwd_identity)
        _require_secret_safe(str(cwd), "command cwd")
        if any(
            not isinstance(item, InheritedEnvironmentBinding) for item in self.inherit_environment
        ):
            raise ValueError("inherit_environment must contain typed value bindings")
        inherited = tuple(sorted(self.inherit_environment, key=lambda item: item.name))
        if any(not isinstance(item, InputTreeBinding) for item in self.input_trees):
            raise ValueError("input_trees must contain typed tree bindings")
        input_trees = tuple(sorted(self.input_trees, key=lambda item: str(item.root)))
        if len({item.root for item in input_trees}) != len(input_trees):
            raise ValueError("input tree roots must be unique")
        if any(not isinstance(item, OwnedOutputRoot) for item in self.owned_output_roots):
            raise ValueError("owned_output_roots must contain typed output-root bindings")
        output_roots = tuple(sorted(self.owned_output_roots, key=lambda item: str(item.root)))
        if len({item.root for item in output_roots}) != len(output_roots):
            raise ValueError("owned output roots must be unique")
        output_patterns = tuple(
            sorted(set(self.unowned_output_patterns), key=lambda item: item.as_posix())
        )
        if len(output_patterns) != len(self.unowned_output_patterns):
            raise ValueError("unowned output patterns must be unique")
        for pattern in output_patterns:
            if (
                pattern.is_absolute()
                or not pattern.parts
                or any(part in {"", ".", ".."} for part in pattern.parts)
            ):
                raise ValueError(
                    "unowned output patterns must be traversal-free relative POSIX paths"
                )
            _require_secret_safe(pattern.as_posix(), "unowned output pattern")
        credential_names = tuple(sorted(self.secret_environment))
        for name in (
            *copied_environment,
            *(item.name for item in inherited),
            *credential_names,
        ):
            validate_environment_name(name)
            _require_secret_safe(name, "environment variable name")
        all_names = (
            *copied_environment.keys(),
            *(item.name for item in inherited),
            *credential_names,
        )
        if len(all_names) != len(set(all_names)):
            raise ValueError("environment variable names must be unique across command sources")
        executable = Path(self.argv[0])
        if not executable.is_absolute():
            raise ValueError("argv[0] must be an absolute resolved executable path")
        expected_executable = self.executable_sha256
        if expected_executable is None:
            try:
                resolved_executable = executable.resolve(strict=True)
            except OSError as exc:
                raise ValueError(f"cannot resolve command executable: {executable}") from exc
            if not resolved_executable.is_file():
                raise ValueError("argv[0] must resolve to a regular executable file")
            executable = resolved_executable
            expected_executable = _sha256_path(executable)
        elif _SHA256.fullmatch(expected_executable) is None:
            raise ValueError("executable_sha256 must be a lowercase SHA-256 digest")
        object.__setattr__(self, "argv", (str(executable), *self.argv[1:]))
        object.__setattr__(self, "environment", MappingProxyType(copied_environment))
        object.__setattr__(self, "inherit_environment", inherited)
        object.__setattr__(self, "secret_environment", credential_names)
        object.__setattr__(self, "input_trees", input_trees)
        object.__setattr__(self, "owned_output_roots", output_roots)
        object.__setattr__(self, "unowned_output_patterns", output_patterns)
        object.__setattr__(self, "executable_sha256", expected_executable)


def _sha256_path(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def command_document(command: CommandSpec) -> dict[str, JsonValue]:
    """Return the canonical, authorization-bound command representation."""

    cwd_identity = command.cwd_identity
    if cwd_identity is None:  # CommandSpec.__post_init__ always installs one.
        raise AssertionError("command cwd identity is missing")
    return {
        "schema_version": SCHEMA_VERSION,
        "argv": list(command.argv),
        "executable_sha256": command.executable_sha256,
        "cwd": str(command.cwd),
        "cwd_identity": {
            "device": cwd_identity.device,
            "inode": cwd_identity.inode,
        },
        "timeout_seconds": command.timeout_seconds,
        "environment": dict(command.environment),
        "inherit_environment": [
            {"name": item.name, "value_sha256": item.value_sha256}
            for item in command.inherit_environment
        ],
        "secret_environment": list(command.secret_environment),
        "input_trees": [
            {
                "root": str(item.root),
                "sha256": item.sha256,
                "excluded_roots": [path.as_posix() for path in item.excluded_roots],
                "git_commit": item.git_commit,
            }
            for item in command.input_trees
        ],
        "owned_output_roots": [str(item.root) for item in command.owned_output_roots],
        "unowned_output_patterns": [
            pattern.as_posix() for pattern in command.unowned_output_patterns
        ],
        "resource_projection": {
            "cost_usd": command.resource_projection.cost_usd,
            "gpu_hours": command.resource_projection.gpu_hours,
            "model_tokens": command.resource_projection.model_tokens,
            "tool_calls": command.resource_projection.tool_calls,
            "enforcement": command.resource_projection.enforcement.value,
            "unbounded_applicable": [
                unit.value for unit in command.resource_projection.unbounded_applicable
            ],
        },
        "shell": False,
    }


def command_sha256(command: CommandSpec) -> str:
    encoded = json.dumps(
        command_document(command),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def command_from_document(value: Mapping[str, object]) -> CommandSpec:
    """Reconstruct and validate one canonical command document."""

    expected = {
        "schema_version",
        "argv",
        "executable_sha256",
        "cwd",
        "cwd_identity",
        "timeout_seconds",
        "environment",
        "inherit_environment",
        "secret_environment",
        "input_trees",
        "owned_output_roots",
        "unowned_output_patterns",
        "resource_projection",
        "shell",
    }
    if value.keys() != expected:
        raise ValueError(
            f"command document fields must be exactly {sorted(expected)}, "
            f"got {sorted(value.keys())}"
        )
    if value["schema_version"] != SCHEMA_VERSION or value["shell"] is not False:
        raise ValueError("command document schema_version/shell contract is invalid")
    argv = value["argv"]
    environment = value["environment"]
    inherited = value["inherit_environment"]
    credential_names = value["secret_environment"]
    input_trees = value["input_trees"]
    owned_output_roots = value["owned_output_roots"]
    unowned_output_patterns = value["unowned_output_patterns"]
    projection = value["resource_projection"]
    if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
        raise ValueError("command argv must be an array of strings")
    if not isinstance(environment, dict) or any(
        not isinstance(key, str) or not isinstance(item, str) for key, item in environment.items()
    ):
        raise ValueError("command environment must map strings to strings")
    if not isinstance(inherited, list):
        raise ValueError("command inherit_environment must be an array")
    inherited_bindings: list[InheritedEnvironmentBinding] = []
    for index, item in enumerate(inherited):
        if not isinstance(item, dict) or item.keys() != {"name", "value_sha256"}:
            raise ValueError(f"command inherit_environment item {index} is invalid")
        name = item["name"]
        digest = item["value_sha256"]
        if not isinstance(name, str) or not isinstance(digest, str):
            raise ValueError(f"command inherit_environment item {index} must contain strings")
        inherited_bindings.append(InheritedEnvironmentBinding(name, digest))
    if not isinstance(credential_names, list) or any(
        not isinstance(item, str) for item in credential_names
    ):
        raise ValueError("command secret_environment must be an array of strings")
    if not isinstance(input_trees, list):
        raise ValueError("command input_trees must be an array")
    tree_bindings: list[InputTreeBinding] = []
    for index, item in enumerate(input_trees):
        if not isinstance(item, dict) or item.keys() != {
            "root",
            "sha256",
            "excluded_roots",
            "git_commit",
        }:
            raise ValueError(f"command input_trees item {index} is invalid")
        tree_root = item["root"]
        tree_digest = item["sha256"]
        tree_exclusions = item["excluded_roots"]
        tree_commit = item["git_commit"]
        if (
            not isinstance(tree_root, str)
            or not isinstance(tree_digest, str)
            or not isinstance(tree_exclusions, list)
            or any(not isinstance(exclusion, str) for exclusion in tree_exclusions)
            or (tree_commit is not None and not isinstance(tree_commit, str))
        ):
            raise ValueError(f"command input_trees item {index} has invalid types")
        tree_bindings.append(
            InputTreeBinding(
                root=Path(tree_root),
                sha256=tree_digest,
                excluded_roots=tuple(PurePosixPath(value) for value in tree_exclusions),
                git_commit=tree_commit,
            )
        )
    if not isinstance(unowned_output_patterns, list) or any(
        not isinstance(item, str) for item in unowned_output_patterns
    ):
        raise ValueError("command unowned_output_patterns must be an array of strings")
    if not isinstance(owned_output_roots, list) or any(
        not isinstance(item, str) for item in owned_output_roots
    ):
        raise ValueError("command owned_output_roots must be an array of strings")
    projection_fields = {
        "cost_usd",
        "gpu_hours",
        "model_tokens",
        "tool_calls",
        "enforcement",
        "unbounded_applicable",
    }
    if not isinstance(projection, dict) or projection.keys() != projection_fields:
        raise ValueError("command resource_projection fields are invalid")
    cwd = value["cwd"]
    cwd_identity = value["cwd_identity"]
    timeout = value["timeout_seconds"]
    executable_digest = value["executable_sha256"]
    if not isinstance(cwd_identity, dict) or cwd_identity.keys() != {"device", "inode"}:
        raise ValueError("command cwd_identity fields are invalid")
    cwd_device = cwd_identity["device"]
    cwd_inode = cwd_identity["inode"]
    if type(cwd_device) is not int or type(cwd_inode) is not int:
        raise ValueError("command cwd_identity values must be integers")
    if (
        not isinstance(cwd, str)
        or type(timeout) is not int
        or not isinstance(executable_digest, str)
    ):
        raise ValueError("command cwd/timeout/executable identity types are invalid")
    projected_cost = projection["cost_usd"]
    projected_gpu = projection["gpu_hours"]
    projected_tokens = projection["model_tokens"]
    projected_tools = projection["tool_calls"]
    enforcement = projection["enforcement"]
    unbounded_applicable = projection["unbounded_applicable"]
    if (
        isinstance(projected_cost, bool)
        or not isinstance(projected_cost, int | float)
        or isinstance(projected_gpu, bool)
        or not isinstance(projected_gpu, int | float)
        or type(projected_tokens) is not int
        or type(projected_tools) is not int
        or not isinstance(enforcement, str)
        or not isinstance(unbounded_applicable, list)
        or any(not isinstance(item, str) for item in unbounded_applicable)
    ):
        raise ValueError("command resource_projection types are invalid")
    return CommandSpec(
        argv=tuple(argv),
        cwd=Path(cwd),
        timeout_seconds=timeout,
        cwd_identity=WorkingDirectoryIdentity(cwd_device, cwd_inode),
        environment=cast(dict[str, str], environment),
        inherit_environment=tuple(inherited_bindings),
        secret_environment=tuple(cast(list[str], credential_names)),
        input_trees=tuple(tree_bindings),
        owned_output_roots=tuple(
            OwnedOutputRoot(Path(item)) for item in cast(list[str], owned_output_roots)
        ),
        unowned_output_patterns=tuple(
            PurePosixPath(item) for item in cast(list[str], unowned_output_patterns)
        ),
        resource_projection=ResourceProjection(
            cost_usd=float(projected_cost),
            gpu_hours=float(projected_gpu),
            model_tokens=projected_tokens,
            tool_calls=projected_tools,
            enforcement=IncrementalLimitEnforcement(enforcement),
            unbounded_applicable=tuple(NonWallResource(item) for item in unbounded_applicable),
        ),
        executable_sha256=executable_digest,
    )


@dataclass(frozen=True, slots=True)
class HarnessEvent:
    """One append-only normalized event."""

    run_id: str
    attempt: int
    sequence: int
    timestamp_utc: str
    event_type: EventType
    source: str
    provenance: EventProvenance
    payload: Mapping[str, EventInputValue]
    schema_version: str = HARNESS_EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if _RUN_ID.fullmatch(self.run_id) is None:
            raise ValueError(f"invalid run id: {self.run_id}")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("attempt must be an integer >= 1")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be an integer >= 1")
        _validate_utc_timestamp(self.timestamp_utc, "timestamp_utc")
        if not isinstance(self.event_type, EventType):
            raise ValueError("event_type must be a canonical harness event type")
        if self.schema_version not in SUPPORTED_HARNESS_EVENT_SCHEMA_VERSIONS:
            raise ValueError("unsupported harness event schema_version")
        if (
            self.schema_version == LEGACY_HARNESS_EVENT_SCHEMA_VERSION
            and self.event_type is EventType.REGULATION_DECISION
        ):
            raise ValueError("regulation_decision requires harness event schema_version 0.2.0")
        if not isinstance(self.provenance, EventProvenance):
            raise ValueError("provenance must be a canonical event provenance")
        _require_nonempty(self.source, "source")
        _require_secret_safe(self.source, "source")
        object.__setattr__(self, "payload", _copy_json_mapping(self.payload))


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    """Adapter event draft whose run identity and sequence are session-owned."""

    event_type: AdapterEventType
    source: str
    provenance: EventProvenance
    payload: Mapping[str, EventInputValue]
    schema_version: str = HARNESS_EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, AdapterEventType):
            raise ValueError("adapter event_type must be a canonical scientific event type")
        if self.schema_version != HARNESS_EVENT_SCHEMA_VERSION:
            raise ValueError("adapters must emit the current harness event schema_version")
        if not isinstance(self.provenance, EventProvenance):
            raise ValueError("provenance must be a canonical event provenance")
        _require_nonempty(self.source, "source")
        _require_secret_safe(self.source, "source")
        if self.source == "giclab-harness":
            raise ValueError("adapter event source uses the reserved harness identity")
        object.__setattr__(self, "payload", _copy_json_mapping(self.payload))


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """Content identity for one retained file."""

    path: str
    kind: str
    size_bytes: int
    sha256: str
    created_at_utc: str

    def __post_init__(self) -> None:
        pure_path = PurePosixPath(self.path)
        if pure_path.is_absolute() or not pure_path.parts:
            raise ValueError("artifact path must be a nonempty relative POSIX path")
        if any(part in {"", ".", ".."} for part in pure_path.parts):
            raise ValueError("artifact path must not escape its artifact directory")
        _require_secret_safe(self.path, "artifact path")
        _require_nonempty(self.kind, "artifact kind")
        _require_secret_safe(self.kind, "artifact kind")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("size_bytes must be a non-negative integer")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("sha256 must be a lowercase 64-character digest")
        _validate_utc_timestamp(self.created_at_utc, "created_at_utc")
