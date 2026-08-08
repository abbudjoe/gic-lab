"""Source-grounded adapter for the pinned SiRA command and session-JSON contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, cast

from giclab.registry import DuplicateKeyError, load_json, loads_json

from ..models import (
    AdapterEventType,
    CommandSpec,
    EventInputValue,
    EventProvenance,
    IncrementalLimitEnforcement,
    NonWallResource,
    NonWallResourceAccounting,
    NormalizedEvent,
    OwnedOutputRoot,
    ResourceProjection,
    RunPlan,
    RunProfile,
    command_document,
    input_tree_binding,
)
from ..regulation import (
    REGULATION_FIELD_NAMES,
    RegulationDecision,
    RegulationFallback,
    RegulationOverride,
    RegulationSourceKind,
    regulation_decision_payload,
)
from .base import (
    AdapterNotice,
    AdapterNoticeSeverity,
    NormalizationResult,
)

SIRA_SOURCE_ID = "SRC-SIRA-REPOSITORY"
SIRA_UPSTREAM_COMMIT = "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
SIRA_RUNNER = PurePosixPath("scripts/run_web_agent.py")
SIRA_SECRET_NAME = "SIRA_API_KEY"
SIRA_EVENT_SOURCE = "sira-session-json"
SIRA_REGULATION_EVENT_SOURCE = "sira-adapter-resolved-configuration"
SIRA_REGULATION_POLICY_ID = "SIRA-REACTIVE-SIMULATIVE-EXPERIMENT-ASSIGNMENT"
SIRA_REGULATION_DECISION_ID = "REG-SIRA-MODE-ASSIGNMENT"
SIRA_MODEL = "gpt-4o"
SIRA_SMOKE_QUERY = "go to google flights"

SIRA_DATASET_REVISIONS: Mapping[str, str] = {
    "fanout": "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288",
    "flightqa": "2550a58636abeddad8ac25b3b5e79048b2e732aa150a7e3b5557454b17aa303b",
}
SIRA_FANOUT_PILOT_TASKS: Mapping[int, str] = {
    0: "What is the batting hand of each of the first five picks in the 1998 MLB draft?",
    1: ("What were box office values of the Star Wars films in the prequel and sequel trilogies?"),
}

_JOB_NAME = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,127}$")
_SESSION_TIMESTAMP = r"[0-9]{4}(?:-[0-9]{2}){5}"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SOURCE_LOG_PATTERNS = (
    PurePosixPath("src/sira/web/logs/*.log"),
    PurePosixPath("logs/sira_*.log"),
)


class SiRAContractError(ValueError):
    """Raised when a plan or command does not match the audited SiRA contract."""


class SiRATraceError(ValueError):
    """Raised when upstream output is ambiguous, malformed, or escapes its owner."""


class SiRAPairMismatch(ValueError):
    """Raised when a reactive/simulative pair has undeclared drift."""


class SiRAMode(StrEnum):
    """Audited SiRA planning modes."""

    REACTIVE = "reactive"
    SIMULATIVE = "simulative"

    @property
    def condition(self) -> str:
        return f"SIRA-{self.value.upper()}"


class SiRADataset(StrEnum):
    """Dataset identifiers accepted by the pinned SiRA CLI."""

    FANOUT = "fanout"
    FLIGHTQA = "flightqa"
    WEBARENA = "webarena"


@dataclass(frozen=True, slots=True)
class SiRATask:
    """Exactly one trace-reconcilable query or dataset slice."""

    query: str | None = None
    dataset: SiRADataset | None = None
    data_root: PurePosixPath | None = None
    start_idx: int | None = None
    end_idx: int | None = None
    expected_goal: str | None = None
    dataset_revision: str | None = None
    expected_instance_id: str | None = None

    def __post_init__(self) -> None:
        has_query = self.query is not None
        has_dataset = self.dataset is not None
        if has_query == has_dataset:
            raise SiRAContractError("SiRA task must select exactly one query or dataset")
        if has_query:
            if not isinstance(self.query, str) or not self.query.strip():
                raise SiRAContractError("SiRA query must be a nonempty string")
            if "\0" in self.query:
                raise SiRAContractError("SiRA query must not contain NUL bytes")
            if self.expected_goal != self.query:
                raise SiRAContractError("query task expected_goal must equal its exact query")
            if any(
                value is not None
                for value in (
                    self.data_root,
                    self.start_idx,
                    self.end_idx,
                    self.dataset_revision,
                    self.expected_instance_id,
                )
            ):
                raise SiRAContractError("query tasks cannot contain dataset identity fields")
            return

        if not isinstance(self.dataset, SiRADataset):
            raise SiRAContractError("SiRA dataset must use the audited dataset vocabulary")
        if type(self.start_idx) is not int or type(self.end_idx) is not int:
            raise SiRAContractError("dataset tasks require integer start_idx and end_idx")
        if self.start_idx < 0 or self.end_idx <= self.start_idx:
            raise SiRAContractError("dataset task slice must be nonempty and end-exclusive")
        if not isinstance(self.expected_goal, str) or not self.expected_goal.strip():
            raise SiRAContractError("dataset tasks require the exact expected trace goal")
        if "\0" in self.expected_goal:
            raise SiRAContractError("SiRA expected_goal must not contain NUL bytes")
        if not isinstance(self.dataset_revision, str) or not self.dataset_revision.strip():
            raise SiRAContractError("dataset tasks require an explicit dataset revision")
        known_revision = SIRA_DATASET_REVISIONS.get(self.dataset.value)
        if known_revision is not None and self.dataset_revision != known_revision:
            raise SiRAContractError("dataset task does not pin the audited dataset revision")
        if known_revision is None and _SHA256.fullmatch(self.dataset_revision) is None:
            raise SiRAContractError("external dataset revisions must be SHA-256 digests")
        if self.dataset in {SiRADataset.FANOUT, SiRADataset.FLIGHTQA}:
            if self.data_root != PurePosixPath("data"):
                raise SiRAContractError(
                    "FanOut/FlightQA tasks require the audited data_root 'data'"
                )
            if self.expected_instance_id is not None:
                raise SiRAContractError("FanOut/FlightQA traces must have a null instance_id")
            if self.dataset is SiRADataset.FANOUT:
                expected_pilot_goal = SIRA_FANOUT_PILOT_TASKS.get(self.start_idx)
                if (
                    expected_pilot_goal is None
                    or self.end_idx != self.start_idx + 1
                    or self.expected_goal != expected_pilot_goal
                ):
                    raise SiRAContractError(
                        "T04 supports only the two exact reviewed FanOut pilot rows"
                    )
        else:
            if self.data_root is not None:
                raise SiRAContractError("WebArena tasks do not accept a local data_root")
            if not isinstance(self.expected_instance_id, str) or not self.expected_instance_id:
                raise SiRAContractError("WebArena tasks require an exact instance_id")

    @classmethod
    def open_query(cls, query: str) -> SiRATask:
        return cls(query=query, expected_goal=query)

    @classmethod
    def dataset_slice(
        cls,
        dataset: SiRADataset,
        *,
        start_idx: int,
        end_idx: int,
        expected_goal: str,
        dataset_revision: str,
        data_root: PurePosixPath | None = None,
        expected_instance_id: str | None = None,
    ) -> SiRATask:
        return cls(
            dataset=dataset,
            data_root=data_root,
            start_idx=start_idx,
            end_idx=end_idx,
            expected_goal=expected_goal,
            dataset_revision=dataset_revision,
            expected_instance_id=expected_instance_id,
        )


@dataclass(frozen=True, slots=True)
class SiRACommandConfig:
    """Audited source-specific fields intentionally absent from the generic plan."""

    profile: RunProfile
    job_name: str
    mode: SiRAMode
    task: SiRATask
    model: str = SIRA_MODEL
    agent: str = "sira"
    max_steps: int = 1
    action_timeout_seconds: int = 30
    max_retry: int = 0
    seed: int = 42
    output_subdirectory: PurePosixPath = dataclass_field(
        default_factory=lambda: PurePosixPath("sira-output")
    )

    def __post_init__(self) -> None:
        if not isinstance(self.profile, RunProfile):
            raise SiRAContractError("SiRA profile must use the typed run-profile vocabulary")
        if self.profile is RunProfile.CONFIRMATORY:
            raise SiRAContractError("T01 defines no confirmatory SiRA command contract")
        if _JOB_NAME.fullmatch(self.job_name) is None:
            raise SiRAContractError("SiRA job_name must be a stable path-free identifier")
        if not isinstance(self.mode, SiRAMode):
            raise SiRAContractError("SiRA mode must be reactive or simulative")
        if not self.job_name.endswith(f"-{self.mode.value.upper()}"):
            raise SiRAContractError("SiRA job_name must end with its planning-mode label")
        if not isinstance(self.task, SiRATask):
            raise SiRAContractError("SiRA task must use the typed task contract")
        if self.model != SIRA_MODEL:
            raise SiRAContractError("the audited matched contract fixes model alias gpt-4o")
        if self.agent != "sira":
            raise SiRAContractError("T04 supports only the audited SiRA agent pair")
        expected_steps = 1 if self.profile is RunProfile.SMOKE else 30
        if self.max_steps != expected_steps:
            raise SiRAContractError(
                f"the audited {self.profile.value} contract fixes max_steps at {expected_steps}"
            )
        if self.profile is RunProfile.SMOKE and self.task != SiRATask.open_query(SIRA_SMOKE_QUERY):
            raise SiRAContractError("the audited smoke contract fixes the README query exactly")
        if self.profile is RunProfile.PILOT:
            if self.task.dataset is None:
                raise SiRAContractError("the audited pilot contract requires a dataset slice")
            start_idx = self.task.start_idx
            end_idx = self.task.end_idx
            if start_idx is None or end_idx is None:
                raise AssertionError("dataset task lost its validated slice")
            if end_idx - start_idx != 1:
                raise SiRAContractError("paired pilot commands must contain one task each")
        if self.action_timeout_seconds != 30:
            raise SiRAContractError("the audited action timeout is exactly 30 seconds")
        if self.max_retry != 0:
            raise SiRAContractError("the audited matched contract fixes outer max_retry at zero")
        if self.seed != 42:
            raise SiRAContractError("the audited dataset-order seed is exactly 42")
        _validate_relative_path(self.output_subdirectory, "SiRA output_subdirectory")


@dataclass(frozen=True, slots=True)
class SiRAFieldRule:
    """One runtime/report field-mapping contract."""

    direct_source_path: str | None
    normalization_rule: str
    provenance: EventProvenance
    status: str


_STEP_INDEX = SiRAFieldRule(
    None,
    "enumerate session history in source order from zero",
    EventProvenance.DERIVED,
    "derived",
)

SIRA_FIELD_RULES: Mapping[str, Mapping[str, SiRAFieldRule]] = {
    "observation": {
        "step_index": _STEP_INDEX,
        "raw_observation": SiRAFieldRule(
            "history[*][0]",
            "copy the complete structured observation mapping without semantic inference",
            EventProvenance.OBSERVED,
            "available",
        ),
        "processed_observation": SiRAFieldRule(
            "history[*][2].obs",
            "copy source text without parsing",
            EventProvenance.OBSERVED,
            "conditional",
        ),
        "observation_info": SiRAFieldRule(
            "history[*][2].obs_info",
            "copy the complete structured mapping without semantic inference",
            EventProvenance.OBSERVED,
            "conditional",
        ),
    },
    "belief_state": {
        "step_index": _STEP_INDEX,
        "upstream_state": SiRAFieldRule(
            "history[*][2].state",
            "copy source-named natural-language state without relabeling it as GIC state",
            EventProvenance.OBSERVED,
            "conditional",
        ),
        "semantic_caveat": SiRAFieldRule(
            None,
            "attach the T01 semantic boundary for source-named state",
            EventProvenance.DERIVED,
            "derived",
        ),
    },
    "plan": {
        "step_index": _STEP_INDEX,
        "selected_plan_text": SiRAFieldRule(
            "history[*][2].plan",
            "copy the source-selected plan without candidate expansion",
            EventProvenance.OBSERVED,
            "conditional",
        ),
        "upstream_policy_output_alias": SiRAFieldRule(
            "history[*][2].intent",
            "copy only after exact equality with the selected plan is verified",
            EventProvenance.OBSERVED,
            "conditional",
        ),
    },
    "executed_action": {
        "step_index": _STEP_INDEX,
        "requested_action": SiRAFieldRule(
            "history[*][1]",
            "copy as requested action only; never claim a structured execution result",
            EventProvenance.OBSERVED,
            "available",
        ),
        "duplicate_step_action": SiRAFieldRule(
            "history[*][2].action",
            "copy only after exact equality with the requested action is verified",
            EventProvenance.OBSERVED,
            "available",
        ),
    },
    "outcome": {
        "source_is_complete": SiRAFieldRule(
            "is_complete",
            "copy after reconciling the source heuristic with the final requested action",
            EventProvenance.OBSERVED,
            "available",
        ),
        "source_error": SiRAFieldRule(
            "error",
            "copy source error text including the observed empty string",
            EventProvenance.OBSERVED,
            "available",
        ),
        "webarena_rewards": SiRAFieldRule(
            "rewards",
            "copy the WebArena reward list without aggregation",
            EventProvenance.OBSERVED,
            "conditional-webarena",
        ),
        "webarena_test_result": SiRAFieldRule(
            "test_result",
            "copy after exact reconciliation with float(max(rewards) > 0) and output.jsonl",
            EventProvenance.OBSERVED,
            "conditional-webarena",
        ),
    },
    "metric": {
        "webarena_rewards": SiRAFieldRule(
            "rewards",
            "copy the WebArena reward list without aggregation",
            EventProvenance.OBSERVED,
            "conditional-webarena",
        ),
        "webarena_test_result": SiRAFieldRule(
            "test_result",
            "copy after exact reconciliation with float(max(rewards) > 0) and output.jsonl",
            EventProvenance.OBSERVED,
            "conditional-webarena",
        ),
    },
}

SIRA_REGULATION_FIELD_RULES: Mapping[str, SiRAFieldRule] = {
    "decision_id": SiRAFieldRule(
        None,
        "use the stable adapter decision identity within each run attempt",
        EventProvenance.DERIVED,
        "derived",
    ),
    "source_kind": SiRAFieldRule(
        "command.json argv planning-mode assignment",
        "classify the fixed reactive/simulative command choice as experiment_assignment",
        EventProvenance.DERIVED,
        "derived",
    ),
    "policy_id": SiRAFieldRule(
        None,
        "use the source-neutral SiRA experiment-assignment policy identity",
        EventProvenance.DERIVED,
        "derived",
    ),
    "policy_revision": SiRAFieldRule(
        "run-plan.json.sources.protocol_sha256",
        "copy the bound protocol digest when known; otherwise retain null/unavailable",
        EventProvenance.DERIVED,
        "conditional",
    ),
    "available_modes": SiRAFieldRule(
        "scripts/run_web_agent.py --mode choices via the reviewed T01 contract",
        "copy the audited reactive/simulative vocabulary without adding latent categories",
        EventProvenance.DERIVED,
        "derived",
    ),
    "selected_mode": SiRAFieldRule(
        "command.json argv value after --mode",
        "derive from the exact config digest and resolved command-bound mode",
        EventProvenance.DERIVED,
        "derived",
    ),
    "confidence": SiRAFieldRule(
        None,
        "retain null because the pinned assignment emits no confidence",
        EventProvenance.UNAVAILABLE,
        "unavailable",
    ),
    "override": SiRAFieldRule(
        None,
        "retain an all-null unavailable record; do not infer from trace prose",
        EventProvenance.UNAVAILABLE,
        "unavailable",
    ),
    "fallback": SiRAFieldRule(
        None,
        "retain an all-null unavailable record; do not infer from trace prose",
        EventProvenance.UNAVAILABLE,
        "unavailable",
    ),
    "input_event_sequences": SiRAFieldRule(
        None,
        "leave empty because adapter drafts do not own harness event sequence numbers",
        EventProvenance.UNAVAILABLE,
        "unavailable",
    ),
    "raw_artifact_refs": SiRAFieldRule(
        "selected structured session artifact path",
        "reference the retained session bytes without claiming that they encode the assignment",
        EventProvenance.OBSERVED,
        "available",
    ),
    "resolved_configuration_refs": SiRAFieldRule(
        "run-plan.json and command.json",
        "reference harness-retained records that bind the config digest and exact --mode value",
        EventProvenance.DERIVED,
        "derived",
    ),
}


@dataclass(frozen=True, slots=True)
class SiRAPairDifference:
    """One approved difference observed by the pair assertion."""

    surface: str
    field: str
    owner: str
    reactive: str
    simulative: str


@dataclass(frozen=True, slots=True)
class SiRAPairReport:
    """Auditable result of a matched command/configuration assertion."""

    config_differences: tuple[SiRAPairDifference, ...]
    command_differences: tuple[SiRAPairDifference, ...]


def _validate_relative_path(path: PurePosixPath, label: str) -> None:
    if path.is_absolute() or not path.parts:
        raise SiRAContractError(f"{label} must be a nonempty relative POSIX path")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise SiRAContractError(f"{label} must not contain dot or parent components")


def _safe_existing_directory(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise SiRAContractError(f"{label} must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SiRAContractError(f"{label} must resolve to an existing directory") from exc
    if resolved != path.absolute() or not resolved.is_dir():
        raise SiRAContractError(f"{label} must be an existing canonical directory")
    return resolved


def _safe_future_root(path: Path) -> Path:
    if not path.is_absolute() or "\0" in str(path) or any(part == ".." for part in path.parts):
        raise SiRAContractError("SiRA output root must be an absolute traversal-free path")
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise SiRAContractError("SiRA output root cannot be resolved safely") from exc
    if resolved != path:
        raise SiRAContractError("SiRA output root must not traverse symlinks")
    return resolved


def _verify_pinned_git_checkout(root: Path, expected_commit: str) -> None:
    """Require the exact clean Git root used to build the command."""

    git = shutil.which("git")
    if git is None:
        raise SiRAContractError("git is required to verify the pinned SiRA checkout")

    def run(*args: str) -> str:
        try:
            completed = subprocess.run(
                (git, "-C", str(root), *args),
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise SiRAContractError("cannot inspect the pinned SiRA Git checkout") from exc
        if completed.returncode != 0:
            raise SiRAContractError("SiRA upstream root is not a valid Git checkout")
        return completed.stdout.strip()

    top_level = run("rev-parse", "--show-toplevel")
    try:
        resolved_top_level = Path(top_level).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SiRAContractError("SiRA Git top-level path cannot be resolved") from exc
    if resolved_top_level != root:
        raise SiRAContractError("SiRA upstream root must be the exact Git top level")
    if run("rev-parse", "HEAD") != expected_commit:
        raise SiRAContractError("SiRA Git checkout does not match the audited commit")
    status = run(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignored=matching",
    )
    if status:
        raise SiRAContractError(
            "SiRA Git checkout must be clean, with no untracked or ignored runtime inputs"
        )


def sira_config_document(config: SiRACommandConfig) -> dict[str, object]:
    """Return the canonical source-specific configuration bound by the run plan."""

    task = config.task
    return {
        "schema_version": "0.1.0",
        "source_id": SIRA_SOURCE_ID,
        "upstream_commit": SIRA_UPSTREAM_COMMIT,
        "profile": config.profile.value,
        "job_name": config.job_name,
        "mode": config.mode.value,
        "task": {
            "query": task.query,
            "dataset": task.dataset.value if task.dataset is not None else None,
            "data_root": str(task.data_root) if task.data_root is not None else None,
            "start_idx": task.start_idx,
            "end_idx": task.end_idx,
            "expected_goal": task.expected_goal,
            "dataset_revision": task.dataset_revision,
            "expected_instance_id": task.expected_instance_id,
        },
        "model": config.model,
        "agent": config.agent,
        "max_steps": config.max_steps,
        "action_timeout_seconds": config.action_timeout_seconds,
        "max_retry": config.max_retry,
        "seed": config.seed,
        "output_subdirectory": str(config.output_subdirectory),
    }


def sira_config_sha256(config: SiRACommandConfig) -> str:
    """Hash the canonical source-specific configuration."""

    encoded = json.dumps(
        sira_config_document(config),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _flag_value_index(argv: tuple[str, ...], flag: str) -> int:
    indexes = [index for index, value in enumerate(argv) if value == flag]
    if len(indexes) != 1 or indexes[0] + 1 >= len(argv):
        raise SiRAPairMismatch(f"paired command must contain exactly one {flag} value")
    return indexes[0] + 1


def _assert_command_matches_adapter(
    adapter: SiRAAdapter,
    plan: RunPlan,
    command: CommandSpec,
    upstream_root: Path,
    upstream_output_root: Path,
) -> None:
    try:
        expected = adapter.build_command(
            plan,
            upstream_root,
            upstream_output_root,
        )
    except SiRAContractError as exc:
        raise SiRAPairMismatch(f"paired command fails its own adapter contract: {exc}") from exc
    if command_document(command) != command_document(expected):
        raise SiRAPairMismatch(
            "paired command does not exactly match its plan, configuration, and source binding"
        )


def assert_sira_matched_pair(
    reactive_adapter: SiRAAdapter,
    reactive_plan: RunPlan,
    reactive_command: CommandSpec,
    simulative_adapter: SiRAAdapter,
    simulative_plan: RunPlan,
    simulative_command: CommandSpec,
    *,
    reactive_upstream_root: Path,
    reactive_output_root: Path,
    simulative_upstream_root: Path,
    simulative_output_root: Path,
) -> SiRAPairReport:
    """Prove both commands individually, then compare only approved pair differences."""

    reactive_config = reactive_adapter.config
    simulative_config = simulative_adapter.config
    if reactive_config.mode is not SiRAMode.REACTIVE:
        raise SiRAPairMismatch("first paired configuration must be reactive")
    if simulative_config.mode is not SiRAMode.SIMULATIVE:
        raise SiRAPairMismatch("second paired configuration must be simulative")
    _assert_command_matches_adapter(
        reactive_adapter,
        reactive_plan,
        reactive_command,
        reactive_upstream_root,
        reactive_output_root,
    )
    _assert_command_matches_adapter(
        simulative_adapter,
        simulative_plan,
        simulative_command,
        simulative_upstream_root,
        simulative_output_root,
    )

    reactive_config_data = sira_config_document(reactive_config)
    simulative_config_data = sira_config_document(simulative_config)
    config_differences = {
        key
        for key in reactive_config_data
        if reactive_config_data[key] != simulative_config_data[key]
    }
    expected_config_differences = {"job_name", "mode"}
    if config_differences != expected_config_differences:
        unexpected = sorted(config_differences - expected_config_differences)
        missing = sorted(expected_config_differences - config_differences)
        raise SiRAPairMismatch(
            "paired SiRA configurations violate declared differences; "
            f"unexpected={unexpected}, missing={missing}"
        )

    reactive_regulation_metadata = sira_regulation_policy_metadata(reactive_plan)
    simulative_regulation_metadata = sira_regulation_policy_metadata(simulative_plan)
    if reactive_regulation_metadata != simulative_regulation_metadata:
        raise SiRAPairMismatch("paired SiRA regulation policy/source metadata differ")

    reactive_document = command_document(reactive_command)
    simulative_document = command_document(simulative_command)
    for field in reactive_document:
        if field in {"argv", "owned_output_roots"}:
            continue
        if reactive_document[field] != simulative_document[field]:
            raise SiRAPairMismatch(f"paired command drift outside argv: {field}")

    reactive_argv = reactive_command.argv
    simulative_argv = simulative_command.argv
    if len(reactive_argv) != len(simulative_argv):
        raise SiRAPairMismatch("paired command argument counts differ")
    if len(reactive_argv) <= 5:
        raise SiRAPairMismatch("paired SiRA commands omit the positional job_name")
    reactive_mode_index = _flag_value_index(reactive_argv, "--mode")
    simulative_mode_index = _flag_value_index(simulative_argv, "--mode")
    reactive_output_index = _flag_value_index(reactive_argv, "--output_dir")
    simulative_output_index = _flag_value_index(simulative_argv, "--output_dir")
    if reactive_mode_index != simulative_mode_index:
        raise SiRAPairMismatch("paired --mode fields occur at different positions")
    if reactive_output_index != simulative_output_index:
        raise SiRAPairMismatch("paired --output_dir fields occur at different positions")
    approved_indexes = {5, reactive_mode_index, reactive_output_index}
    actual_indexes = {
        index
        for index, values in enumerate(zip(reactive_argv, simulative_argv, strict=True))
        if values[0] != values[1]
    }
    if actual_indexes != approved_indexes:
        unexpected_indexes = sorted(actual_indexes - approved_indexes)
        missing_indexes = sorted(approved_indexes - actual_indexes)
        raise SiRAPairMismatch(
            "paired SiRA commands violate declared differences; "
            f"unexpected argv indexes={unexpected_indexes}, missing={missing_indexes}"
        )

    return SiRAPairReport(
        config_differences=(
            SiRAPairDifference(
                "config",
                "job_name",
                "source-contract",
                reactive_config.job_name,
                simulative_config.job_name,
            ),
            SiRAPairDifference(
                "config",
                "mode",
                "source-contract",
                reactive_config.mode.value,
                simulative_config.mode.value,
            ),
        ),
        command_differences=(
            SiRAPairDifference(
                "command",
                "argv[5]:job_name",
                "source-contract",
                reactive_argv[5],
                simulative_argv[5],
            ),
            SiRAPairDifference(
                "command",
                f"argv[{reactive_mode_index}]:mode",
                "source-contract",
                reactive_argv[reactive_mode_index],
                simulative_argv[simulative_mode_index],
            ),
            SiRAPairDifference(
                "command",
                f"argv[{reactive_output_index}]:artifact_output_root",
                "harness-evidence-isolation",
                reactive_argv[reactive_output_index],
                simulative_argv[simulative_output_index],
            ),
            SiRAPairDifference(
                "command",
                "owned_output_roots[0]",
                "harness-evidence-isolation",
                str(reactive_command.owned_output_roots[0].root),
                str(simulative_command.owned_output_roots[0].root),
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class SiRAAdapter:
    """Build and normalize only the audited pinned SiRA source surface."""

    config: SiRACommandConfig
    uv_executable: Path
    source_id: ClassVar[str] = SIRA_SOURCE_ID

    def __post_init__(self) -> None:
        if not isinstance(self.config, SiRACommandConfig):
            raise SiRAContractError("SiRA adapter requires a typed command configuration")
        try:
            executable = self.uv_executable.resolve(strict=True)
        except OSError as exc:
            raise SiRAContractError("SiRA uv executable must resolve to a regular file") from exc
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise SiRAContractError("SiRA uv executable must be an executable regular file")
        object.__setattr__(self, "uv_executable", executable)

    def _assert_plan_contract(self, plan: RunPlan) -> None:
        if plan.sources.upstream_source_id != SIRA_SOURCE_ID:
            raise SiRAContractError("run plan does not name the audited SiRA source")
        if plan.sources.upstream_commit != SIRA_UPSTREAM_COMMIT:
            raise SiRAContractError("run plan does not pin the audited SiRA commit")
        if plan.sources.config_sha256 != sira_config_sha256(self.config):
            raise SiRAContractError("run-plan config_sha256 does not bind this SiRA configuration")
        if plan.sources.model_revision is not None:
            raise SiRAContractError(
                "SiRA's mutable provider alias has no verifiable immutable model revision"
            )
        if plan.sources.dataset_revision != self.config.task.dataset_revision:
            raise SiRAContractError("run-plan dataset revision does not match the SiRA task")
        if plan.identity.condition != self.config.mode.condition:
            raise SiRAContractError("run-plan condition does not match the SiRA mode")
        if plan.profile is not self.config.profile:
            raise SiRAContractError("run-plan profile does not match the SiRA configuration")
        if plan.identity.seed != self.config.seed:
            raise SiRAContractError("run-plan seed does not match the SiRA configuration")
        if plan.budget.max_tool_calls != self.config.max_steps:
            raise SiRAContractError("run-plan tool-call limit does not match SiRA max_steps")

    def build_command(
        self,
        plan: RunPlan,
        upstream_root: Path,
        upstream_output_root: Path,
    ) -> CommandSpec:
        """Build the pinned shell-free CLI command without launching any process."""

        self._assert_plan_contract(plan)
        if self.config.task.dataset in {SiRADataset.FLIGHTQA, SiRADataset.WEBARENA}:
            unsupported_dataset = self.config.task.dataset
            raise SiRAContractError(
                f"T01 defines no reviewed {unsupported_dataset.value} pilot command"
            )
        source_root = _safe_existing_directory(upstream_root, "SiRA upstream root")
        _verify_pinned_git_checkout(source_root, SIRA_UPSTREAM_COMMIT)
        runner = source_root / SIRA_RUNNER
        if runner.is_symlink():
            raise SiRAContractError("SiRA runner must not be a symlink")
        try:
            runner_resolved = runner.resolve(strict=True)
        except OSError as exc:
            raise SiRAContractError("SiRA runner is missing from the pinned source root") from exc
        if source_root not in runner_resolved.parents or not runner_resolved.is_file():
            raise SiRAContractError("SiRA runner escapes the pinned source root")

        output_root = _safe_future_root(upstream_output_root)
        if (
            output_root == source_root
            or source_root in output_root.parents
            or output_root in source_root.parents
        ):
            raise SiRAContractError("SiRA source and attempt-output roots must not overlap")
        output_directory = output_root / self.config.output_subdirectory
        argv: list[str] = [
            str(self.uv_executable),
            "run",
            "--frozen",
            "python",
            str(SIRA_RUNNER),
            self.config.job_name,
        ]
        task = self.config.task
        if task.query is not None:
            argv.extend(("--query", task.query))
        else:
            dataset = task.dataset
            if dataset is None:
                raise AssertionError("dataset task lost its typed dataset")
            argv.extend(("--dataset", dataset.value))
        argv.extend(
            (
                "--mode",
                self.config.mode.value,
                "--agent",
                self.config.agent,
                "--model",
                self.config.model,
                "--max_steps",
                str(self.config.max_steps),
                "--timeout",
                str(self.config.action_timeout_seconds),
                "--max_retry",
                str(self.config.max_retry),
            )
        )
        if task.data_root is not None:
            argv.extend(("--data_root", str(task.data_root)))
        argv.extend(("--output_dir", str(output_directory)))
        if task.dataset is not None:
            if task.start_idx is None or task.end_idx is None:
                raise AssertionError("dataset task lost its typed slice")
            argv.extend(("--start_idx", str(task.start_idx), "--end_idx", str(task.end_idx)))
        argv.extend(("--seed", str(self.config.seed)))

        return CommandSpec(
            argv=tuple(argv),
            cwd=source_root,
            timeout_seconds=plan.budget.max_wall_seconds,
            secret_environment=(SIRA_SECRET_NAME,),
            input_trees=(
                input_tree_binding(
                    source_root,
                    excluded_roots=(PurePosixPath(".git"),),
                    git_commit=SIRA_UPSTREAM_COMMIT,
                ),
            ),
            owned_output_roots=(OwnedOutputRoot(output_directory),),
            unowned_output_patterns=_SOURCE_LOG_PATTERNS,
            resource_projection=ResourceProjection(
                tool_calls=self.config.max_steps,
                enforcement=IncrementalLimitEnforcement.ADAPTER_COMMAND,
                unbounded_applicable=(
                    NonWallResource.COST_USD,
                    NonWallResource.MODEL_TOKENS,
                ),
            ),
        )

    def normalize(self, plan: RunPlan, upstream_output_root: Path) -> NormalizationResult:
        """Normalize one unambiguous structured session trace and retain every owned file."""

        self._assert_plan_contract(plan)
        root = _trace_root(upstream_output_root)
        output_directory = _owned_output_directory(root, self.config.output_subdirectory)
        raw_artifacts = _raw_artifacts(output_directory)
        session_path = _select_session_artifact(
            output_directory,
            raw_artifacts,
            self.config.job_name,
        )
        session = _load_session(session_path)
        _reconcile_session(self.config, session)
        _reconcile_webarena_output_jsonl(
            self.config,
            session,
            output_directory,
            raw_artifacts,
        )
        events, unavailable = _normalize_session(
            session,
            webarena=self.config.task.dataset is SiRADataset.WEBARENA,
        )
        regulation_event = _regulation_assignment_event(
            self.config,
            plan,
            session_path=session_path,
            attempt_root=root,
        )
        return NormalizationResult(
            events=(regulation_event, *events),
            raw_artifacts=raw_artifacts,
            unavailable_fields=unavailable,
            notices=_source_notices(session),
            accounting=NonWallResourceAccounting(
                cost_usd=None,
                gpu_hours=0.0,
                model_tokens=None,
                tool_calls=None,
            ),
        )


def sira_regulation_policy_metadata(plan: RunPlan) -> dict[str, EventInputValue]:
    """Return pair-invariant source/policy metadata for SiRA mode assignment."""

    return {
        "source_kind": RegulationSourceKind.EXPERIMENT_ASSIGNMENT.value,
        "policy_id": SIRA_REGULATION_POLICY_ID,
        "policy_revision": (
            None if plan.sources.protocol_sha256 == "unknown" else plan.sources.protocol_sha256
        ),
        "available_modes": [mode.value for mode in SiRAMode],
        "upstream_source_id": plan.sources.upstream_source_id,
        "upstream_commit": plan.sources.upstream_commit,
    }


def _regulation_assignment_event(
    config: SiRACommandConfig,
    plan: RunPlan,
    *,
    session_path: Path,
    attempt_root: Path,
) -> NormalizedEvent:
    """Represent the command-bound SiRA condition without an internalization claim."""

    raw_ref = session_path.relative_to(attempt_root).as_posix()
    policy_revision = (
        None if plan.sources.protocol_sha256 == "unknown" else plan.sources.protocol_sha256
    )
    provenance: dict[str, EventProvenance] = {
        "decision_id": EventProvenance.DERIVED,
        "source_kind": EventProvenance.DERIVED,
        "policy_id": EventProvenance.DERIVED,
        "policy_revision": (
            EventProvenance.UNAVAILABLE if policy_revision is None else EventProvenance.DERIVED
        ),
        "available_modes": EventProvenance.DERIVED,
        "selected_mode": EventProvenance.DERIVED,
        "confidence": EventProvenance.UNAVAILABLE,
        "override": EventProvenance.UNAVAILABLE,
        "fallback": EventProvenance.UNAVAILABLE,
        "input_event_sequences": EventProvenance.UNAVAILABLE,
        "raw_artifact_refs": EventProvenance.OBSERVED,
        "resolved_configuration_refs": EventProvenance.DERIVED,
    }
    if set(provenance) != set(REGULATION_FIELD_NAMES):
        raise AssertionError("SiRA regulation provenance coverage drifted")
    decision = RegulationDecision(
        decision_id=SIRA_REGULATION_DECISION_ID,
        source_kind=RegulationSourceKind.EXPERIMENT_ASSIGNMENT,
        selected_mode=config.mode.value,
        policy_id=SIRA_REGULATION_POLICY_ID,
        policy_revision=policy_revision,
        available_modes=tuple(mode.value for mode in SiRAMode),
        confidence=None,
        override=RegulationOverride(),
        fallback=RegulationFallback(),
        input_event_sequences=(),
        raw_artifact_refs=(raw_ref,),
        resolved_configuration_refs=("run-plan.json", "command.json"),
        field_provenance=provenance,
    )
    return NormalizedEvent(
        event_type=AdapterEventType.REGULATION_DECISION,
        source=SIRA_REGULATION_EVENT_SOURCE,
        provenance=EventProvenance.DERIVED,
        payload=regulation_decision_payload(decision),
    )


def _trace_root(path: Path) -> Path:
    if path.is_symlink():
        raise SiRATraceError("SiRA attempt output root must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SiRATraceError("SiRA attempt output root is missing") from exc
    if resolved != path.absolute() or not resolved.is_dir():
        raise SiRATraceError("SiRA attempt output root is not a canonical directory")
    return resolved


def _owned_output_directory(root: Path, relative: PurePosixPath) -> Path:
    candidate = root.joinpath(*relative.parts)
    if candidate.is_symlink():
        raise SiRATraceError("SiRA output directory must not traverse a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SiRATraceError("SiRA output directory is missing") from exc
    if root not in resolved.parents or not resolved.is_dir():
        raise SiRATraceError("SiRA output directory escapes its run attempt")
    return resolved


def _raw_artifacts(output_directory: Path) -> tuple[Path, ...]:
    raw: list[Path] = []
    for path in sorted(output_directory.rglob("*")):
        if path.is_symlink():
            raise SiRATraceError("SiRA raw output contains a symlink")
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SiRATraceError("SiRA raw output contains an unresolved path") from exc
        if output_directory not in resolved.parents:
            raise SiRATraceError("SiRA raw output escapes its owned directory")
        if resolved.is_dir():
            continue
        if not resolved.is_file():
            raise SiRATraceError("SiRA raw output contains a non-regular entry")
        raw.append(resolved)
    return tuple(raw)


def _select_session_artifact(
    output_directory: Path,
    raw_artifacts: tuple[Path, ...],
    job_name: str,
) -> Path:
    session_pattern = re.compile(rf"^{re.escape(job_name)}_{_SESSION_TIMESTAMP}\.json$")
    direct_json = [
        path for path in raw_artifacts if path.parent == output_directory and path.suffix == ".json"
    ]
    matching = [path for path in direct_json if session_pattern.fullmatch(path.name)]
    if len(matching) > 1:
        raise SiRATraceError("multiple SiRA session artifacts indicate repeated attempts")
    if not matching:
        if direct_json:
            raise SiRATraceError("SiRA session artifact does not match configured condition/job")
        raise SiRATraceError("SiRA session artifact is missing")
    if len(direct_json) != 1:
        raise SiRATraceError("SiRA output contains an undeclared additional session artifact")
    return matching[0]


def _load_session(path: Path) -> dict[str, Any]:
    try:
        value = load_json(path)
        return _validate_session(value)
    except (
        DuplicateKeyError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        if isinstance(exc, SiRATraceError):
            raise
        raise SiRATraceError("malformed SiRA session trace") from exc


def _load_webarena_output_jsonl(path: Path) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) != 1 or not lines[0].strip():
            raise SiRATraceError("SiRA WebArena output.jsonl must contain exactly one row")
        value = loads_json(lines[0])
    except (
        DuplicateKeyError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        if isinstance(exc, SiRATraceError):
            raise
        raise SiRATraceError("malformed SiRA WebArena output.jsonl") from exc
    if not isinstance(value, dict) or value.keys() != {"instance_id", "goal", "test_result"}:
        raise SiRATraceError("malformed SiRA WebArena output.jsonl fields")
    if (
        not isinstance(value["instance_id"], str)
        or not value["instance_id"]
        or not isinstance(value["goal"], str)
        or not value["goal"]
        or type(value["test_result"]) is not float
    ):
        raise SiRATraceError("malformed SiRA WebArena output.jsonl values")
    return cast(dict[str, Any], value)


def _reconcile_webarena_output_jsonl(
    config: SiRACommandConfig,
    session: dict[str, Any],
    output_directory: Path,
    raw_artifacts: tuple[Path, ...],
) -> None:
    path = output_directory / "output.jsonl"
    present = path in raw_artifacts
    if config.task.dataset is not SiRADataset.WEBARENA:
        if present:
            raise SiRATraceError("non-WebArena SiRA output contains WebArena output.jsonl")
        return
    if not present:
        raise SiRATraceError("SiRA WebArena output.jsonl is missing")
    summary = _load_webarena_output_jsonl(path)
    for field in ("instance_id", "goal", "test_result"):
        if summary[field] != session[field]:
            raise SiRATraceError(
                f"SiRA WebArena output.jsonl {field} contradicts the session trace"
            )


def _validate_session(value: dict[str, Any]) -> dict[str, Any]:
    required = {
        "goal": str,
        "history": list,
        "is_complete": bool,
        "error": str,
    }
    for field, expected in required.items():
        if type(value.get(field)) is not expected:
            raise SiRATraceError(f"malformed SiRA session trace: invalid {field}")
    if not cast(str, value["goal"]).strip():
        raise SiRATraceError("malformed SiRA session trace: empty goal")
    if "instance_id" not in value:
        raise SiRATraceError("malformed SiRA session trace: missing instance_id")
    instance_id = value.get("instance_id")
    if instance_id is not None and not isinstance(instance_id, str):
        raise SiRATraceError("malformed SiRA session trace: invalid instance_id")
    history = cast(list[object], value["history"])
    for index, item in enumerate(history):
        if not isinstance(item, list) or len(item) != 3:
            raise SiRATraceError(f"malformed SiRA session trace: history item {index}")
        observation, requested_action, step_info = item
        if not _is_string_mapping(observation):
            raise SiRATraceError(f"malformed SiRA observation at history item {index}")
        if not isinstance(requested_action, str):
            raise SiRATraceError(f"malformed SiRA action at history item {index}")
        if not _is_string_mapping(step_info):
            raise SiRATraceError(f"malformed SiRA step_info at history item {index}")
        for field in ("obs", "state", "plan", "intent", "action", "memory_update"):
            if (
                field in step_info
                and step_info[field] is not None
                and not isinstance(step_info[field], str)
            ):
                raise SiRATraceError(f"malformed SiRA step_info.{field} at history item {index}")
        if "action" not in step_info:
            raise SiRATraceError(
                f"malformed SiRA step_info.action at history item {index}: missing"
            )
        if "obs_info" in step_info:
            obs_info = step_info["obs_info"]
            if not _is_string_mapping(obs_info):
                raise SiRATraceError(f"malformed SiRA step_info.obs_info at history item {index}")
            for field in ("goal", "error_prefix", "return_action"):
                if field in obs_info and not isinstance(obs_info[field], str):
                    raise SiRATraceError(
                        f"malformed SiRA step_info.obs_info.{field} at history item {index}"
                    )
    if "rewards" in value:
        rewards = value["rewards"]
        if not isinstance(rewards, list) or any(
            isinstance(item, bool) or not isinstance(item, int | float) for item in rewards
        ):
            raise SiRATraceError("malformed SiRA session trace: invalid rewards")
    if "test_result" in value:
        test_result = value["test_result"]
        if isinstance(test_result, bool) or not isinstance(test_result, int | float):
            raise SiRATraceError("malformed SiRA session trace: invalid test_result")
    return value


def _is_string_mapping(value: object) -> bool:
    return isinstance(value, Mapping) and all(isinstance(key, str) for key in value)


def _reconcile_session(config: SiRACommandConfig, session: dict[str, Any]) -> None:
    expected_goal = config.task.expected_goal
    if session["goal"] != expected_goal:
        raise SiRATraceError("SiRA trace goal does not match the configured task")
    history = cast(list[list[Any]], session["history"])
    if len(history) > config.max_steps:
        raise SiRATraceError("SiRA trace history exceeds the configured max_steps")
    previous_action: str | None = None
    for index, item in enumerate(history):
        observation = cast(dict[str, Any], item[0])
        requested_action = cast(str, item[1])
        step_info = cast(dict[str, Any], item[2])
        observation_goal = observation.get("goal")
        if observation_goal is not None and observation_goal != expected_goal:
            raise SiRATraceError(f"SiRA observation goal mismatch at history item {index}")
        obs_info = step_info.get("obs_info")
        if isinstance(obs_info, Mapping):
            info_goal = obs_info.get("goal")
            if info_goal is not None and info_goal != expected_goal:
                raise SiRATraceError(f"SiRA obs_info goal mismatch at history item {index}")
        duplicate_action = step_info["action"]
        if duplicate_action != requested_action:
            raise SiRATraceError(f"SiRA duplicate action mismatch at history item {index}")
        plan_text = step_info.get("plan")
        intent = step_info.get("intent")
        if (plan_text is None) != (intent is None):
            raise SiRATraceError(f"SiRA plan/intent presence mismatch at history item {index}")
        if plan_text is not None and plan_text != intent:
            raise SiRATraceError(f"SiRA plan/intent mismatch at history item {index}")
        adjacent_action = observation.get("last_action")
        if index == 0:
            if adjacent_action not in {None, ""}:
                raise SiRATraceError("SiRA first observation contains an undeclared prior action")
        elif adjacent_action is not None and adjacent_action != previous_action:
            raise SiRATraceError(f"SiRA prior action mismatch at history item {index}")
        previous_action = requested_action

    expected_complete = bool(history) and cast(str, history[-1][1]).startswith("send_msg_to_user")
    if session["is_complete"] is not expected_complete:
        raise SiRATraceError("SiRA is_complete contradicts the final requested action")

    dataset = config.task.dataset
    instance_id = session["instance_id"]
    if dataset is SiRADataset.WEBARENA:
        expected_instance_id = config.task.expected_instance_id
        if expected_instance_id is None:
            raise AssertionError("WebArena task lost its instance identity")
        _reconcile_webarena_outcome(session, expected_instance_id)
    else:
        if instance_id is not None:
            raise SiRATraceError("non-WebArena SiRA trace must have a null instance_id")
        if "rewards" in session or "test_result" in session:
            raise SiRATraceError("WebArena-only fields appear in a non-WebArena trace")


def _reconcile_webarena_outcome(
    session: dict[str, Any],
    expected_instance_id: str,
) -> None:
    if session["instance_id"] != expected_instance_id:
        raise SiRATraceError("SiRA WebArena instance_id does not match the configured task")
    if ("rewards" in session) != ("test_result" in session):
        raise SiRATraceError("SiRA WebArena rewards and test_result must appear together")
    if "rewards" not in session:
        raise SiRATraceError("SiRA WebArena trace is missing its outcome fields")
    rewards = cast(list[float | int], session["rewards"])
    if not rewards:
        raise SiRATraceError("SiRA WebArena rewards must be nonempty")
    test_result = session["test_result"]
    expected_test_result = float(max(rewards) > 0)
    if type(test_result) is not float or test_result != expected_test_result:
        raise SiRATraceError("SiRA WebArena test_result contradicts the source reward derivation")


_BASE_UNAVAILABLE_FIELDS = (
    "observation.timestamp_utc",
    "observation.observation_after_action",
    "candidate_action.stable_candidate_action_ids",
    "candidate_action.structured_candidate_action_set",
    "predicted_future.stable_prediction_ids",
    "predicted_future.structured_action_conditioned_futures",
    "predicted_future.confidence",
    "critic_evaluation.structured_per_candidate_scores",
    "plan.plan_id",
    "plan.candidate_action_ids",
    "executed_action.action_result",
    "executed_action.candidate_action_id",
    "outcome.generic_environment_result",
    "outcome.scientific_outcome",
    "outcome.fanout_evaluator_outcome",
    "outcome.flight_evaluator_outcome",
    "metric.fanout_record_accuracy",
    "metric.flight_grounded",
    "metric.flight_relevant",
    "metric.fanout_aggregate_scores",
    "metric.flight_aggregate_scores",
    "metric.webarena_helper_aggregates",
    "immutable_provider_model_revision",
    "per_step_timestamp_utc",
    "model_seed",
    "model_call_count",
    "model_input_tokens",
    "model_output_tokens",
    "model_latency",
    "generic_tool_call_count",
    "generic_action_execution_result",
    "gic_configurator_decision",
    "gic_state",
    "belief_uncertainty",
    "world_model_calibration",
)


def _payload_with_contracts(
    event_name: str,
    values: Mapping[str, EventInputValue],
    *,
    step_index: int | None = None,
) -> dict[str, EventInputValue]:
    rules = SIRA_FIELD_RULES[event_name]
    if not values.keys() <= rules.keys():
        raise AssertionError(
            f"unmapped {event_name} payload fields: {values.keys() - rules.keys()}"
        )
    field_contracts: dict[str, EventInputValue] = {}
    for field in values:
        rule = rules[field]
        source_path = rule.direct_source_path
        if source_path is not None and step_index is not None:
            source_path = source_path.replace("[*]", f"[{step_index}]")
        field_contracts[field] = {
            "direct_source_path": source_path,
            "normalization_rule": rule.normalization_rule,
            "provenance": rule.provenance.value,
            "status": "available" if rule.status != "derived" else "derived",
        }
    return {**values, "field_contracts": cast(EventInputValue, field_contracts)}


def _normalize_session(
    session: dict[str, Any],
    *,
    webarena: bool,
) -> tuple[tuple[NormalizedEvent, ...], tuple[str, ...]]:
    events: list[NormalizedEvent] = []
    unavailable = list(_BASE_UNAVAILABLE_FIELDS)
    history = cast(list[list[Any]], session["history"])
    for step_index, item in enumerate(history):
        observation = cast(dict[str, Any], item[0])
        requested_action = cast(str, item[1])
        step_info = cast(dict[str, Any], item[2])
        observation_values: dict[str, EventInputValue] = {
            "step_index": step_index,
            "raw_observation": observation,
        }
        if isinstance(step_info.get("obs"), str):
            observation_values["processed_observation"] = cast(str, step_info["obs"])
        else:
            unavailable.append(f"observation[{step_index}].processed_observation")
        if isinstance(step_info.get("obs_info"), Mapping):
            observation_values["observation_info"] = cast(dict[str, Any], step_info["obs_info"])
        else:
            unavailable.append(f"observation[{step_index}].observation_info")
        events.append(
            NormalizedEvent(
                event_type=AdapterEventType.OBSERVATION,
                source=SIRA_EVENT_SOURCE,
                provenance=EventProvenance.OBSERVED,
                payload=_payload_with_contracts(
                    "observation",
                    observation_values,
                    step_index=step_index,
                ),
            )
        )

        state = step_info.get("state")
        if isinstance(state, str):
            events.append(
                NormalizedEvent(
                    event_type=AdapterEventType.BELIEF_STATE,
                    source=SIRA_EVENT_SOURCE,
                    provenance=EventProvenance.OBSERVED,
                    payload=_payload_with_contracts(
                        "belief_state",
                        {
                            "step_index": step_index,
                            "upstream_state": state,
                            "semantic_caveat": (
                                "upstream natural-language encoder state; not calibrated belief, "
                                "uncertainty, world-model accuracy, or GIC state"
                            ),
                        },
                        step_index=step_index,
                    ),
                )
            )
        else:
            unavailable.append(f"belief_state[{step_index}].upstream_state")

        plan_text = step_info.get("plan")
        intent = step_info.get("intent")
        if isinstance(plan_text, str) or isinstance(intent, str):
            plan_values: dict[str, EventInputValue] = {"step_index": step_index}
            if isinstance(plan_text, str):
                plan_values["selected_plan_text"] = plan_text
            else:
                unavailable.append(f"plan[{step_index}].selected_plan_text")
            if isinstance(intent, str):
                plan_values["upstream_policy_output_alias"] = intent
            else:
                unavailable.append(f"plan[{step_index}].upstream_policy_output_alias")
            events.append(
                NormalizedEvent(
                    event_type=AdapterEventType.PLAN,
                    source=SIRA_EVENT_SOURCE,
                    provenance=EventProvenance.OBSERVED,
                    payload=_payload_with_contracts(
                        "plan",
                        plan_values,
                        step_index=step_index,
                    ),
                )
            )
        else:
            unavailable.extend(
                (
                    f"plan[{step_index}].selected_plan_text",
                    f"plan[{step_index}].upstream_policy_output_alias",
                )
            )

        action_values: dict[str, EventInputValue] = {
            "step_index": step_index,
            "requested_action": requested_action,
        }
        action_values["duplicate_step_action"] = cast(str, step_info["action"])
        events.append(
            NormalizedEvent(
                event_type=AdapterEventType.EXECUTED_ACTION,
                source=SIRA_EVENT_SOURCE,
                provenance=EventProvenance.OBSERVED,
                payload=_payload_with_contracts(
                    "executed_action",
                    action_values,
                    step_index=step_index,
                ),
            )
        )

    outcome_values: dict[str, EventInputValue] = {
        "source_is_complete": cast(bool, session["is_complete"]),
        "source_error": cast(str, session["error"]),
    }
    if webarena:
        outcome_values["webarena_rewards"] = cast(EventInputValue, session["rewards"])
        outcome_values["webarena_test_result"] = cast(EventInputValue, session["test_result"])
    else:
        unavailable.extend(
            (
                "outcome.webarena_rewards",
                "outcome.webarena_test_result",
                "metric.webarena_rewards",
                "metric.webarena_test_result",
            )
        )
    events.append(
        NormalizedEvent(
            event_type=AdapterEventType.OUTCOME,
            source=SIRA_EVENT_SOURCE,
            provenance=EventProvenance.OBSERVED,
            payload=_payload_with_contracts("outcome", outcome_values),
        )
    )
    if webarena:
        for field in ("webarena_rewards", "webarena_test_result"):
            source_field = field.removeprefix("webarena_")
            events.append(
                NormalizedEvent(
                    event_type=AdapterEventType.METRIC,
                    source=SIRA_EVENT_SOURCE,
                    provenance=EventProvenance.OBSERVED,
                    payload=_payload_with_contracts(
                        "metric",
                        {field: cast(EventInputValue, session[source_field])},
                    ),
                )
            )
    return tuple(events), tuple(dict.fromkeys(unavailable))


def _source_notices(session: dict[str, Any]) -> tuple[AdapterNotice, ...]:
    notices: list[AdapterNotice] = []
    history = cast(list[list[Any]], session["history"])
    for index, item in enumerate(history):
        observation = cast(dict[str, Any], item[0])
        step_info = cast(dict[str, Any], item[2])
        last_action_error = observation.get("last_action_error")
        if isinstance(last_action_error, str) and last_action_error.strip():
            notices.append(
                AdapterNotice(
                    severity=AdapterNoticeSeverity.WARNING,
                    kind="source-action-warning",
                    message=last_action_error,
                    source=SIRA_EVENT_SOURCE,
                    source_paths=(f"history[{index}][0].last_action_error",),
                    provenance=EventProvenance.DERIVED,
                )
            )
        obs_info = step_info.get("obs_info")
        if isinstance(obs_info, Mapping):
            error_prefix = obs_info.get("error_prefix")
            if isinstance(error_prefix, str) and error_prefix.strip():
                notices.append(
                    AdapterNotice(
                        severity=AdapterNoticeSeverity.WARNING,
                        kind="source-observation-warning",
                        message=error_prefix,
                        source=SIRA_EVENT_SOURCE,
                        source_paths=(f"history[{index}][2].obs_info.error_prefix",),
                        provenance=EventProvenance.DERIVED,
                    )
                )
            return_action = obs_info.get("return_action")
            if isinstance(return_action, str) and return_action.strip():
                notices.append(
                    AdapterNotice(
                        severity=AdapterNoticeSeverity.ERROR,
                        kind="source-terminal-return-action",
                        message=return_action,
                        source=SIRA_EVENT_SOURCE,
                        source_paths=(f"history[{index}][2].obs_info.return_action",),
                        provenance=EventProvenance.OBSERVED,
                    )
                )
    source_error = cast(str, session["error"])
    if source_error.strip():
        notices.append(
            AdapterNotice(
                severity=AdapterNoticeSeverity.ERROR,
                kind="source-session-error",
                message=source_error,
                source=SIRA_EVENT_SOURCE,
                source_paths=("error",),
                provenance=EventProvenance.OBSERVED,
            )
        )
    return tuple(notices)


__all__ = [
    "SIRA_DATASET_REVISIONS",
    "SIRA_EVENT_SOURCE",
    "SIRA_FANOUT_PILOT_TASKS",
    "SIRA_FIELD_RULES",
    "SIRA_MODEL",
    "SIRA_REGULATION_DECISION_ID",
    "SIRA_REGULATION_EVENT_SOURCE",
    "SIRA_REGULATION_FIELD_RULES",
    "SIRA_REGULATION_POLICY_ID",
    "SIRA_RUNNER",
    "SIRA_SECRET_NAME",
    "SIRA_SMOKE_QUERY",
    "SIRA_SOURCE_ID",
    "SIRA_UPSTREAM_COMMIT",
    "SiRAAdapter",
    "SiRACommandConfig",
    "SiRAContractError",
    "SiRADataset",
    "SiRAFieldRule",
    "SiRAMode",
    "SiRAPairDifference",
    "SiRAPairMismatch",
    "SiRAPairReport",
    "SiRATask",
    "SiRATraceError",
    "assert_sira_matched_pair",
    "sira_config_document",
    "sira_config_sha256",
    "sira_regulation_policy_metadata",
]
