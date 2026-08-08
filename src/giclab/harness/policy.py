"""Typed project-state authorization for harness execution."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from giclab.registry import DuplicateKeyError, load_json, load_yaml, resolve_repo_path

from .models import ExecutionBackend, RunPlan, WorkloadKind
from .plan import RunPlanError, load_run_plan, run_plan_authorization_sha256
from .task_source import dataset_slice_task_source, open_query_task_source_matches


class ExecutionDisallowed(PermissionError):
    """Raised before process creation when a control plane disallows execution."""


_PLAN_ID = re.compile(r"^PLAN-[A-Z0-9][A-Z0-9._-]{5,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_AUTHORIZATION_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}$")


@dataclass(frozen=True, slots=True)
class AuthorizedRunProfile:
    """Verified project binding to one authorization-eligible parent profile."""

    plan_id: str
    profile_sha256: str
    authorization_reference: str
    condition_plan_sha256s: frozenset[str]

    def __post_init__(self) -> None:
        if _PLAN_ID.fullmatch(self.plan_id) is None:
            raise ValueError("authorized profile plan_id must be canonical")
        if _SHA256.fullmatch(self.profile_sha256) is None:
            raise ValueError("authorized profile hash must be a lowercase SHA-256 digest")
        if _AUTHORIZATION_REFERENCE.fullmatch(self.authorization_reference) is None:
            raise ValueError("authorized profile reference must be a secret-safe identifier")
        if not self.condition_plan_sha256s or any(
            _SHA256.fullmatch(digest) is None for digest in self.condition_plan_sha256s
        ):
            raise ValueError("authorized profile requires canonical child-plan fingerprints")


@dataclass(frozen=True, slots=True)
class ProjectExecutionState:
    """The project-level half of the execution authorization contract."""

    phase: str
    phase_status: str
    paid_compute_allowed: bool
    prototype_execution_allowed: bool
    benchmark_execution_allowed: bool
    training_allowed: bool
    cloud_mutation_allowed: bool
    authorized_run_profile: AuthorizedRunProfile | None = None

    def __post_init__(self) -> None:
        if not self.phase.strip():
            raise ValueError("project phase must not be empty")
        if not self.phase_status.strip():
            raise ValueError("project phase_status must not be empty")
        for label in (
            "paid_compute_allowed",
            "prototype_execution_allowed",
            "benchmark_execution_allowed",
            "training_allowed",
            "cloud_mutation_allowed",
        ):
            if type(getattr(self, label)) is not bool:
                raise ValueError(f"project {label} must be a boolean")


def _assert_profile_children_coherent(
    profile: dict[str, object],
    condition_records: dict[str, RunPlan],
) -> None:
    """Reject a sealed child set that contradicts its parent profile contract."""

    sampling = profile.get("sampling")
    profile_budget = profile.get("budget")
    profile_model = profile.get("model")
    assert isinstance(sampling, dict)
    assert isinstance(profile_budget, dict)
    assert isinstance(profile_model, dict)
    expected_conditions = sampling.get("conditions")
    dataset_ids = sampling.get("dataset_ids")
    pair_count = sampling.get("pair_count")
    counterbalancing = sampling.get("counterbalancing")
    assert isinstance(expected_conditions, list)
    assert isinstance(dataset_ids, list)
    assert isinstance(pair_count, int)
    assert isinstance(counterbalancing, list)
    expected_model_revision = profile_model.get("proposed_immutable_revision")
    assert isinstance(expected_model_revision, str)
    expected_count = pair_count * len(expected_conditions)
    if len(condition_records) != expected_count:
        raise ExecutionDisallowed("parent sampling count does not match declared child plans")
    observed_conditions = Counter(plan.identity.condition for plan in condition_records.values())
    if any(observed_conditions.get(condition) != pair_count for condition in expected_conditions):
        raise ExecutionDisallowed("parent sampling conditions do not match declared child plans")

    bound_paths: list[str] = []
    pair_ids: set[str] = set()
    task_ids: set[str] = set()
    for pair in counterbalancing:
        assert isinstance(pair, dict)
        pair_id = pair.get("pair_id")
        task_id = pair.get("task_id")
        task_source = pair.get("task_source")
        first = pair.get("first")
        second = pair.get("second")
        bindings = pair.get("plans")
        assert isinstance(pair_id, str)
        assert isinstance(task_id, str)
        assert isinstance(task_source, str)
        assert isinstance(first, str)
        assert isinstance(second, str)
        assert isinstance(bindings, list)
        if pair_id in pair_ids or task_id in task_ids:
            raise ExecutionDisallowed("parent sampling pair and task IDs must be unique")
        pair_ids.add(pair_id)
        task_ids.add(task_id)
        if {first, second} != set(expected_conditions):
            raise ExecutionDisallowed(
                "parent sampling order must contain each expected condition once"
            )
        pair_plans: list[RunPlan] = []
        for binding in bindings:
            assert isinstance(binding, dict)
            relative = binding.get("path")
            condition_name = binding.get("condition")
            assert isinstance(relative, str)
            assert isinstance(condition_name, str)
            bound_paths.append(relative)
            child = condition_records.get(relative)
            if child is None:
                raise ExecutionDisallowed("parent sampling references an undeclared child plan")
            if child.identity.condition != condition_name:
                raise ExecutionDisallowed("parent sampling condition does not match child plan")
            if child.task is None or child.task.task_id != task_id:
                raise ExecutionDisallowed("parent sampling task does not match child plan")
            if child.sources.model_revision != expected_model_revision:
                raise ExecutionDisallowed("parent model revision does not match child plan")
            assert child.task is not None
            if child.sources.dataset_revision != child.task.dataset_revision:
                raise ExecutionDisallowed("child task/source dataset revision does not match")
            if child.task.source_kind.value == "dataset-slice":
                if child.task.dataset_id not in dataset_ids:
                    raise ExecutionDisallowed(
                        "parent dataset list does not contain the child task dataset"
                    )
                assert child.task.dataset_id is not None
                assert child.task.start_idx is not None
                assert child.task.end_idx is not None
                expected_task_source = dataset_slice_task_source(
                    child.task.dataset_id,
                    child.task.start_idx,
                    child.task.end_idx,
                )
                if task_source != expected_task_source:
                    raise ExecutionDisallowed(
                        "parent dataset task source does not match child slice"
                    )
            else:
                assert child.task.query is not None
                if not open_query_task_source_matches(task_source, child.task.query):
                    raise ExecutionDisallowed("parent query task source does not match child query")
            expected_order = 1 if condition_name == first else 2
            if (
                child.pairing is None
                or child.pairing.pair_id != pair_id
                or child.pairing.order_index != expected_order
            ):
                raise ExecutionDisallowed("parent sampling pair identity does not match child plan")
            pair_plans.append(child)
        if len(pair_plans) == 2:
            left, right = pair_plans
            fixed_source_fields = (
                "giclab_commit",
                "upstream_source_id",
                "upstream_commit",
                "protocol_sha256",
                "model_revision",
                "dataset_revision",
                "environment_sha256",
            )
            if (
                left.task != right.task
                or left.budget != right.budget
                or left.identity.seed != right.identity.seed
                or left.identity.attempt != right.identity.attempt
                or left.execution.backend != right.execution.backend
                or left.execution.workload != right.execution.workload
            ):
                raise ExecutionDisallowed("declared matched pair drifts outside its condition")
            if any(
                getattr(left.sources, field) != getattr(right.sources, field)
                for field in fixed_source_fields
            ):
                raise ExecutionDisallowed("declared matched pair fixed source identity drifts")
    if len(bound_paths) != len(set(bound_paths)) or set(bound_paths) != set(condition_records):
        raise ExecutionDisallowed("parent sampling paths are not bijective with child plans")

    aggregate_cost = sum(
        (Decimal(str(plan.budget.max_cost_usd)) for plan in condition_records.values()),
        start=Decimal(0),
    )
    aggregate_tokens = sum(plan.budget.max_model_tokens or 0 for plan in condition_records.values())
    aggregate_wall = sum(plan.budget.max_wall_seconds for plan in condition_records.values())
    if (
        aggregate_cost != Decimal(str(profile_budget.get("max_cost_usd")))
        or aggregate_tokens != profile_budget.get("max_model_tokens")
        or aggregate_wall != profile_budget.get("max_wall_seconds")
    ):
        raise ExecutionDisallowed("parent budget does not equal aggregate child hard caps")


def _load_authorized_run_profile(
    project_root: Path,
    schema_root: Path,
    value: object,
) -> AuthorizedRunProfile | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ExecutionDisallowed("project state authorized_run_profile must be a mapping")
    expected_keys = {
        "plan_id",
        "profile_path",
        "profile_sha256",
        "condition_plan_sha256s",
    }
    if set(value) != expected_keys:
        raise ExecutionDisallowed(
            "project state authorized_run_profile must contain exactly "
            "plan_id, profile_path, profile_sha256, and condition_plan_sha256s"
        )
    plan_id = value.get("plan_id")
    profile_relative = value.get("profile_path")
    recorded_sha256 = value.get("profile_sha256")
    sealed_condition_sha256s = value.get("condition_plan_sha256s")
    if not isinstance(sealed_condition_sha256s, list) or any(
        not isinstance(item, str) or _SHA256.fullmatch(item) is None
        for item in sealed_condition_sha256s
    ):
        raise ExecutionDisallowed(
            "project state condition_plan_sha256s must contain lowercase SHA-256 digests"
        )
    if len(sealed_condition_sha256s) != len(set(sealed_condition_sha256s)):
        raise ExecutionDisallowed("project state condition_plan_sha256s must be unique")
    bindings = (plan_id, profile_relative, recorded_sha256)
    if all(item is None for item in bindings):
        if sealed_condition_sha256s:
            raise ExecutionDisallowed(
                "null authorized profile cannot retain child-plan fingerprints"
            )
        return None
    if not all(isinstance(item, str) for item in bindings):
        raise ExecutionDisallowed(
            "project state authorized_run_profile bindings must be all strings or all null"
        )
    if not sealed_condition_sha256s:
        raise ExecutionDisallowed("authorized run profile requires sealed child fingerprints")
    assert isinstance(plan_id, str)
    assert isinstance(profile_relative, str)
    assert isinstance(recorded_sha256, str)
    if _PLAN_ID.fullmatch(plan_id) is None:
        raise ExecutionDisallowed("authorized run profile plan_id is invalid")
    if _SHA256.fullmatch(recorded_sha256) is None:
        raise ExecutionDisallowed("authorized run profile profile_sha256 is invalid")
    try:
        profile_path = resolve_repo_path(project_root, profile_relative)
    except ValueError as exc:
        raise ExecutionDisallowed(f"authorized run profile path is invalid: {exc}") from exc
    if not profile_path.is_file():
        raise ExecutionDisallowed("authorized run profile path does not resolve to a file")
    observed_sha256 = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    if observed_sha256 != recorded_sha256:
        raise ExecutionDisallowed("authorized run profile hash does not match its file")
    try:
        profile = load_yaml(profile_path)
    except (OSError, TypeError, DuplicateKeyError, yaml.YAMLError) as exc:
        raise ExecutionDisallowed(f"cannot load authorized run profile: {exc}") from exc
    try:
        profile_schema = load_json(schema_root / "schemas/run-profile.schema.json")
    except (OSError, TypeError, ValueError) as exc:
        raise ExecutionDisallowed(f"cannot load run-profile schema: {exc}") from exc
    profile_errors = sorted(
        Draft202012Validator(
            profile_schema,
            format_checker=FormatChecker(),
        ).iter_errors(profile),
        key=lambda item: list(item.absolute_path),
    )
    if profile_errors:
        first = profile_errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise ExecutionDisallowed(
            f"authorized run profile is schema-invalid at {location}: {first.message}"
        )
    if profile.get("plan_id") != plan_id:
        raise ExecutionDisallowed("authorized run profile plan_id does not match its file")
    readiness = profile.get("readiness")
    if (
        not isinstance(readiness, dict)
        or readiness.get("execution_eligibility") != "eligible-after-authorization"
    ):
        raise ExecutionDisallowed("authorized run profile is not execution-eligible")
    if readiness.get("unresolved_execution_blockers") != []:
        raise ExecutionDisallowed("authorized run profile retains unresolved execution blockers")
    execution = profile.get("execution")
    reference = execution.get("authorization_reference") if isinstance(execution, dict) else None
    if not isinstance(execution, dict) or execution.get("authorized") is not True:
        raise ExecutionDisallowed("authorized run profile file is not authorized")
    if not isinstance(reference, str) or _AUTHORIZATION_REFERENCE.fullmatch(reference) is None:
        raise ExecutionDisallowed("authorized run profile reference is not secret-safe")
    condition_relatives = profile.get("condition_plan_paths")
    assert isinstance(condition_relatives, list)
    condition_plan_sha256s: list[str] = []
    condition_records: dict[str, RunPlan] = {}
    for condition_relative in condition_relatives:
        assert isinstance(condition_relative, str)
        try:
            condition_path = resolve_repo_path(project_root, condition_relative)
            condition = load_run_plan(condition_path, schema_root=schema_root)
        except (OSError, RunPlanError, ValueError) as exc:
            raise ExecutionDisallowed(
                f"cannot load authorized profile condition plan {condition_relative}: {exc}"
            ) from exc
        if condition.identity.experiment_id != profile.get("experiment_id"):
            raise ExecutionDisallowed("declared condition plan experiment does not match parent")
        if condition.profile.value != profile.get("profile"):
            raise ExecutionDisallowed("declared condition plan profile does not match parent")
        if condition.profile_plan_id != plan_id or condition.profile_sha256 != recorded_sha256:
            raise ExecutionDisallowed("declared condition plan parent binding does not match")
        condition_authorization = condition.execution.authorization
        if (
            not condition_authorization.authorized
            or condition_authorization.authorization_reference != reference
        ):
            raise ExecutionDisallowed("declared condition plan authorization does not match parent")
        condition_records[condition_relative] = condition
        condition_plan_sha256s.append(run_plan_authorization_sha256(condition))
    _assert_profile_children_coherent(profile, condition_records)
    if len(condition_plan_sha256s) != len(set(condition_plan_sha256s)):
        raise ExecutionDisallowed("authorized profile declares duplicate child documents")
    if len(condition_plan_sha256s) != len(sealed_condition_sha256s) or set(
        condition_plan_sha256s
    ) != set(sealed_condition_sha256s):
        raise ExecutionDisallowed(
            "declared condition plans do not match sealed authorization fingerprints"
        )
    return AuthorizedRunProfile(
        plan_id=plan_id,
        profile_sha256=recorded_sha256,
        authorization_reference=reference,
        condition_plan_sha256s=frozenset(sealed_condition_sha256s),
    )


def load_project_execution_state(
    project_root: Path,
    *,
    schema_root: Path | None = None,
) -> ProjectExecutionState:
    """Load only the project-state fields that control execution."""

    path = project_root / "docs/PROJECT_STATE.yaml"
    try:
        data = load_yaml(path)
    except (OSError, TypeError, DuplicateKeyError, yaml.YAMLError) as exc:
        raise ExecutionDisallowed(f"cannot load project execution state: {exc}") from exc
    required = {
        "phase": str,
        "phase_status": str,
        "paid_compute_allowed": bool,
        "prototype_execution_allowed": bool,
        "benchmark_execution_allowed": bool,
        "training_allowed": bool,
        "cloud_mutation_allowed": bool,
    }
    for key, expected in required.items():
        if type(data.get(key)) is not expected:
            raise ExecutionDisallowed(f"project state {key} must be {expected.__name__}")
    authorized_run_profile = _load_authorized_run_profile(
        project_root,
        (schema_root or project_root).resolve(),
        data.get("authorized_run_profile"),
    )
    return ProjectExecutionState(
        phase=str(data["phase"]),
        phase_status=str(data["phase_status"]),
        paid_compute_allowed=bool(data["paid_compute_allowed"]),
        prototype_execution_allowed=bool(data["prototype_execution_allowed"]),
        benchmark_execution_allowed=bool(data["benchmark_execution_allowed"]),
        training_allowed=bool(data["training_allowed"]),
        cloud_mutation_allowed=bool(data["cloud_mutation_allowed"]),
        authorized_run_profile=authorized_run_profile,
    )


def execution_blockers(plan: RunPlan, state: ProjectExecutionState) -> tuple[str, ...]:
    """Return deterministic reasons why live execution is currently disallowed."""

    blockers: list[str] = []
    if state.phase_status != "in-progress":
        blockers.append(f"project phase status {state.phase_status!r} is not executable")
    if not plan.execution.authorization.authorized:
        blockers.append("run plan is not authorized")
    profile = state.authorized_run_profile
    if profile is None:
        blockers.append("project state has no authorized run profile")
    else:
        if plan.profile_plan_id != profile.plan_id:
            blockers.append("run plan parent profile does not match project authorization")
        if plan.profile_sha256 != profile.profile_sha256:
            blockers.append("run plan parent profile hash does not match project authorization")
        if (
            plan.execution.authorization.authorized
            and plan.execution.authorization.authorization_reference
            != profile.authorization_reference
        ):
            blockers.append("run authorization reference does not match parent profile")
        if run_plan_authorization_sha256(plan) not in profile.condition_plan_sha256s:
            blockers.append("run plan is not a declared child of the authorized profile")
    if plan.sources.unknown_fields:
        blockers.append(
            "run source provenance is not fully pinned: " + ", ".join(plan.sources.unknown_fields)
        )
    permission = {
        WorkloadKind.PROTOTYPE: state.prototype_execution_allowed,
        WorkloadKind.BENCHMARK: state.benchmark_execution_allowed,
        WorkloadKind.TRAINING: state.training_allowed,
    }[plan.execution.workload]
    if not permission:
        blockers.append(f"project state disallows {plan.execution.workload.value} execution")
    if (plan.budget.max_cost_usd > 0 or plan.budget.max_gpu_hours > 0) and not (
        state.paid_compute_allowed
    ):
        blockers.append("project state disallows paid compute for this nonzero budget")
    if plan.execution.backend is ExecutionBackend.CLOUD and not state.cloud_mutation_allowed:
        blockers.append("project state disallows cloud mutation")
    return tuple(blockers)


def assert_execution_allowed(plan: RunPlan, state: ProjectExecutionState) -> None:
    blockers = execution_blockers(plan, state)
    if blockers:
        raise ExecutionDisallowed("; ".join(blockers))
