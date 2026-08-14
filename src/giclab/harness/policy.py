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
class RegisteredSuccessorProfile:
    """Registry-bound successor that may replace consumed historical profiles."""

    plan_id: str
    profile_path: str
    profile_sha256: str

    def __post_init__(self) -> None:
        if _PLAN_ID.fullmatch(self.plan_id) is None:
            raise ValueError("registered successor plan_id must be canonical")
        if not self.profile_path.strip():
            raise ValueError("registered successor path must not be empty")
        if _SHA256.fullmatch(self.profile_sha256) is None:
            raise ValueError("registered successor hash must be SHA-256")


@dataclass(frozen=True, slots=True)
class TerminalExecutionControl:
    """Authoritative terminal overlay for consumed, immutable run profiles."""

    control_id: str
    experiment_id: str
    terminal_state: str
    execution_eligibility: str
    superseded_plan_ids: frozenset[str]
    registered_successor: RegisteredSuccessorProfile | None
    blockers: tuple[str, ...]
    source_path: str
    source_sha256: str

    def __post_init__(self) -> None:
        if not self.control_id.strip() or not self.experiment_id.strip():
            raise ValueError("terminal execution control identities must not be empty")
        if self.terminal_state != "t09-pilot-blocked-material-risk":
            raise ValueError("terminal execution control state is not blocked material risk")
        if self.execution_eligibility != "blocked-pending-prerequisites":
            raise ValueError("terminal execution control must remain execution-ineligible")
        if not self.superseded_plan_ids or any(
            _PLAN_ID.fullmatch(plan_id) is None for plan_id in self.superseded_plan_ids
        ):
            raise ValueError("terminal execution control requires canonical superseded plan IDs")
        if (
            self.registered_successor is not None
            and self.registered_successor.plan_id in self.superseded_plan_ids
        ):
            raise ValueError("registered successor cannot reuse a superseded plan ID")
        if not self.blockers or any(not blocker.strip() for blocker in self.blockers):
            raise ValueError("terminal execution control requires explicit blockers")
        if _SHA256.fullmatch(self.source_sha256) is None:
            raise ValueError("terminal execution control source hash must be SHA-256")


@dataclass(frozen=True, slots=True)
class PlannedExecutionSubstrate:
    """Non-authorizing binding for a reviewed future execution substrate."""

    decision_state: str
    provider: str
    architecture: str
    persistent_filesystem: bool
    gate_l1_authorized: bool
    gate_l1_evidence_state: str
    gate_l2_authorized: bool
    gate_l2_decision_state: str
    gate_l3_state: str
    gate_l4_authorized: bool
    local_alternatives: str
    decision_document: str
    security_decision_document: str

    def __post_init__(self) -> None:
        profile_fields = {
            "high-assurance-infrastructure-frozen": {
                "gate_l2_decision_state": "high-assurance-track-frozen",
                "gate_l3_state": "deferred-for-bounded-smoke",
                "decision_document": "docs/harness/T07_GATE_L0_LAMBDA_HOST_DECISION.md",
                "security_decision_document": (
                    "docs/harness/T07_HIGH_ASSURANCE_INFRASTRUCTURE_CLOSEOUT.md"
                ),
            },
            "bounded-smoke-v1-ready-unauthorized": {
                "gate_l2_decision_state": "bounded-manual-console-plan-ready-unauthorized",
                "gate_l3_state": "folded-into-bounded-preflight-unauthorized",
                "decision_document": "docs/harness/T07_BOUNDED_SMOKE_GOVERNANCE.md",
                "security_decision_document": "docs/harness/T07_BOUNDED_SMOKE_EXECUTION_PLAN.md",
            },
            "bounded-smoke-v2-ready-unauthorized": {
                "gate_l2_decision_state": "bounded-manual-console-plan-ready-unauthorized",
                "gate_l3_state": "folded-into-bounded-preflight-unauthorized",
                "decision_document": "docs/harness/T07_BOUNDED_SMOKE_GOVERNANCE.md",
                "security_decision_document": (
                    "docs/harness/T07_BOUNDED_SMOKE_SECURITY_BINDING_REPAIR.md"
                ),
            },
            "bounded-smoke-v3-ready-unauthorized": {
                "gate_l2_decision_state": "bounded-manual-console-plan-ready-unauthorized",
                "gate_l3_state": "folded-into-bounded-preflight-unauthorized",
                "decision_document": "docs/harness/T07_BOUNDED_SMOKE_GOVERNANCE.md",
                "security_decision_document": (
                    "docs/harness/T07_BOUNDED_SMOKE_SECURITY_BINDING_REPAIR.md"
                ),
            },
        }
        selected_profile = profile_fields.get(self.decision_state)
        if selected_profile is None:
            raise ValueError(
                "planned substrate decision_state must name a reviewed substrate profile"
            )
        expected = {
            "provider": (self.provider, "lambda-on-demand-cloud"),
            "architecture": (self.architecture, "x86_64"),
            "gate_l1_evidence_state": (
                self.gate_l1_evidence_state,
                "complete-externally-sealed",
            ),
            "gate_l2_decision_state": (
                self.gate_l2_decision_state,
                selected_profile["gate_l2_decision_state"],
            ),
            "gate_l3_state": (self.gate_l3_state, selected_profile["gate_l3_state"]),
            "local_alternatives": (self.local_alternatives, "terminal-rejected"),
            "decision_document": (
                self.decision_document,
                selected_profile["decision_document"],
            ),
            "security_decision_document": (
                self.security_decision_document,
                selected_profile["security_decision_document"],
            ),
        }
        for field, (observed, required) in expected.items():
            if observed != required:
                raise ValueError(f"planned substrate {field} must be {required!r}")
        for field in (
            "persistent_filesystem",
            "gate_l1_authorized",
            "gate_l2_authorized",
            "gate_l4_authorized",
        ):
            if getattr(self, field) is not False:
                raise ValueError(f"planned substrate {field} must remain false")


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
    terminal_execution_control: TerminalExecutionControl | None = None
    planned_execution_substrate: PlannedExecutionSubstrate | None = None

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


def _load_terminal_execution_control(
    project_root: Path,
    schema_root: Path,
    value: object,
) -> TerminalExecutionControl | None:
    """Load and source-bind the terminal overlay that supersedes frozen readiness bytes."""

    registry_path = project_root / "experiments/registry.yaml"
    if not registry_path.is_file():
        if value is None:
            return None
        raise ExecutionDisallowed("terminal execution control requires an experiment registry")
    try:
        registry = load_yaml(registry_path)
    except (OSError, TypeError, DuplicateKeyError, yaml.YAMLError) as exc:
        raise ExecutionDisallowed(f"cannot load registry terminal-control binding: {exc}") from exc
    if not isinstance(registry, dict):
        raise ExecutionDisallowed("experiment registry must be a mapping")
    registry_experiments = registry.get("experiments")
    if not isinstance(registry_experiments, list):
        raise ExecutionDisallowed("experiment registry experiments must be a list")
    registry_control_entries = [
        entry
        for entry in registry_experiments
        if isinstance(entry, dict) and entry.get("current_execution_control") is not None
    ]
    if value is None:
        if registry_control_entries:
            raise ExecutionDisallowed(
                "project state must bind the registry terminal execution control"
            )
        return None
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ExecutionDisallowed(
            "project state current_execution_control must contain exactly path and sha256"
        )
    relative = value.get("path")
    recorded_sha256 = value.get("sha256")
    if not isinstance(relative, str) or not isinstance(recorded_sha256, str):
        raise ExecutionDisallowed("terminal execution-control binding fields must be strings")
    if _SHA256.fullmatch(recorded_sha256) is None:
        raise ExecutionDisallowed("terminal execution-control hash must be lowercase SHA-256")
    try:
        control_path = resolve_repo_path(project_root, relative)
    except ValueError as exc:
        raise ExecutionDisallowed(f"terminal execution-control path is invalid: {exc}") from exc
    if not control_path.is_file():
        raise ExecutionDisallowed("terminal execution-control path does not resolve to a file")
    if hashlib.sha256(control_path.read_bytes()).hexdigest() != recorded_sha256:
        raise ExecutionDisallowed("terminal execution-control hash does not match its file")
    try:
        document = load_json(control_path)
        schema = load_json(schema_root / "schemas/terminal-execution-control.schema.json")
    except (OSError, TypeError, ValueError) as exc:
        raise ExecutionDisallowed(f"cannot load terminal execution control: {exc}") from exc
    schema_errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
        key=lambda item: list(item.absolute_path),
    )
    if schema_errors:
        first = schema_errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise ExecutionDisallowed(
            f"terminal execution control is schema-invalid at {location}: {first.message}"
        )

    def bound_path(relative_path: str, label: str) -> Path:
        try:
            return resolve_repo_path(project_root, relative_path)
        except ValueError as exc:
            raise ExecutionDisallowed(f"{label} path is invalid: {exc}") from exc

    registry_entries = [
        entry
        for entry in registry_experiments
        if isinstance(entry, dict) and entry.get("experiment_id") == document["experiment_id"]
    ]
    if len(registry_entries) != 1:
        raise ExecutionDisallowed("terminal execution control requires one registry experiment")
    if registry_entries[0].get("current_execution_control") != value:
        raise ExecutionDisallowed("project-state and registry terminal-control bindings differ")

    terminal_binding = document["terminal_record"]
    terminal_path = bound_path(terminal_binding["path"], "terminal disposition")
    if (
        not terminal_path.is_file()
        or hashlib.sha256(terminal_path.read_bytes()).hexdigest() != terminal_binding["sha256"]
    ):
        raise ExecutionDisallowed("terminal disposition binding does not match retained bytes")
    try:
        terminal_record = load_json(terminal_path)
    except (OSError, TypeError, ValueError) as exc:
        raise ExecutionDisallowed(f"cannot load terminal disposition: {exc}") from exc
    expected_empirical_entry = document.get("empirical_entry", False)
    if type(expected_empirical_entry) is not bool:
        raise ExecutionDisallowed("terminal execution-control empirical_entry must be boolean")
    terminal_projection = {
        "experiment_id": terminal_record.get("experiment_id"),
        "terminal_state": terminal_record.get("terminal_state"),
        "single_use_authority_exhausted": terminal_record.get("single_use_authority_exhausted"),
        "launch_slots_exhausted": terminal_record.get("launch_slots_exhausted"),
        "empirical_entry": terminal_record.get("empirical_entry"),
    }
    if terminal_projection != {
        "experiment_id": document["experiment_id"],
        "terminal_state": document["terminal_state"],
        "single_use_authority_exhausted": True,
        "launch_slots_exhausted": True,
        "empirical_entry": expected_empirical_entry,
    }:
        raise ExecutionDisallowed(
            "terminal disposition does not prove exhausted zero-use authority"
        )

    superseded_plan_ids: set[str] = set()
    superseded_profile_paths: set[str] = set()
    for binding in document["superseded_registered_profiles"]:
        plan_id = binding["plan_id"]
        profile_relative = binding["path"]
        if plan_id in superseded_plan_ids or profile_relative in superseded_profile_paths:
            raise ExecutionDisallowed("terminal control repeats a superseded profile binding")
        superseded_plan_ids.add(plan_id)
        superseded_profile_paths.add(profile_relative)
        profile_path = bound_path(profile_relative, "superseded profile")
        if (
            not profile_path.is_file()
            or hashlib.sha256(profile_path.read_bytes()).hexdigest() != binding["sha256"]
        ):
            raise ExecutionDisallowed("superseded profile binding does not match frozen bytes")
        try:
            profile = load_yaml(profile_path)
        except (OSError, TypeError, DuplicateKeyError, yaml.YAMLError) as exc:
            raise ExecutionDisallowed(f"cannot load superseded profile: {exc}") from exc
        readiness = profile.get("readiness")
        execution = profile.get("execution")
        if (
            profile.get("plan_id") != plan_id
            or not isinstance(readiness, dict)
            or readiness.get("execution_eligibility") != binding["historical_execution_eligibility"]
            or not isinstance(execution, dict)
            or execution.get("authorized") is not False
        ):
            raise ExecutionDisallowed("superseded profile projection contradicts frozen bytes")
    registered_profiles = registry_entries[0].get("run_profiles")
    if (
        not isinstance(registered_profiles, list)
        or any(not isinstance(item, str) for item in registered_profiles)
        or len(registered_profiles) != len(set(registered_profiles))
    ):
        raise ExecutionDisallowed("registry run profiles must be unique paths")
    registered_profile_paths = set(registered_profiles)
    if not superseded_profile_paths.issubset(registered_profile_paths):
        raise ExecutionDisallowed("registry dropped a terminal-control superseded profile")

    successor = document["successor"]
    successor_fields = (
        successor["plan_id"],
        successor["profile_path"],
        successor["profile_sha256"],
    )
    registered_successor: RegisteredSuccessorProfile | None = None
    if all(item is None for item in successor_fields):
        if registered_profile_paths != superseded_profile_paths:
            raise ExecutionDisallowed(
                "registry declares a successor but terminal control names no successor"
            )
    else:
        if not all(isinstance(item, str) for item in successor_fields):
            raise ExecutionDisallowed("terminal successor bindings must be all strings or null")
        successor_plan_id, successor_relative, successor_sha256 = successor_fields
        assert isinstance(successor_plan_id, str)
        assert isinstance(successor_relative, str)
        assert isinstance(successor_sha256, str)
        if registered_profile_paths != superseded_profile_paths | {successor_relative}:
            raise ExecutionDisallowed(
                "terminal successor must be the sole fresh registered profile"
            )
        successor_path = bound_path(successor_relative, "registered successor profile")
        if (
            not successor_path.is_file()
            or hashlib.sha256(successor_path.read_bytes()).hexdigest() != successor_sha256
        ):
            raise ExecutionDisallowed("registered successor binding does not match profile bytes")
        try:
            successor_profile = load_yaml(successor_path)
        except (OSError, TypeError, DuplicateKeyError, yaml.YAMLError) as exc:
            raise ExecutionDisallowed(f"cannot load registered successor profile: {exc}") from exc
        if (
            successor_profile.get("plan_id") != successor_plan_id
            or successor_profile.get("experiment_id") != document["experiment_id"]
        ):
            raise ExecutionDisallowed("registered successor identity contradicts terminal control")
        registered_successor = RegisteredSuccessorProfile(
            plan_id=successor_plan_id,
            profile_path=successor_relative,
            profile_sha256=successor_sha256,
        )

    for binding in document["superseded_execution_contracts"]:
        contract_path = bound_path(binding["path"], "superseded execution contract")
        if (
            not contract_path.is_file()
            or hashlib.sha256(contract_path.read_bytes()).hexdigest() != binding["sha256"]
        ):
            raise ExecutionDisallowed("superseded execution-contract binding does not match bytes")
        try:
            contract = load_json(contract_path)
        except (OSError, TypeError, ValueError) as exc:
            raise ExecutionDisallowed(f"cannot load superseded execution contract: {exc}") from exc
        if {
            "contract_id": contract.get("contract_id"),
            "plan_id": contract.get("plan_id"),
            "terminal_state": contract.get("terminal_state"),
            "execution_eligibility": contract.get("execution_eligibility"),
            "authorized": contract.get("authorized"),
            "material_blockers": contract.get("material_blockers"),
        } != {
            "contract_id": binding["contract_id"],
            "plan_id": binding["plan_id"],
            "terminal_state": binding["historical_terminal_state"],
            "execution_eligibility": binding["historical_execution_eligibility"],
            "authorized": False,
            "material_blockers": [],
        }:
            raise ExecutionDisallowed(
                "superseded execution-contract projection contradicts frozen bytes"
            )

    return TerminalExecutionControl(
        control_id=document["control_id"],
        experiment_id=document["experiment_id"],
        terminal_state=document["terminal_state"],
        execution_eligibility=document["execution_eligibility"],
        superseded_plan_ids=frozenset(superseded_plan_ids),
        registered_successor=registered_successor,
        blockers=tuple(document["blockers"]),
        source_path=relative,
        source_sha256=recorded_sha256,
    )


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
                "config_sha256",
                "model_revision",
                "dataset_revision",
                "environment_sha256",
            )
            if (
                left.task != right.task
                or (
                    left.budget.max_wall_seconds,
                    left.budget.max_cost_usd,
                    left.budget.max_gpu_hours,
                    left.budget.max_model_calls,
                    left.budget.max_model_tokens,
                    left.budget.max_tool_calls,
                    left.budget.max_output_bytes,
                )
                != (
                    right.budget.max_wall_seconds,
                    right.budget.max_cost_usd,
                    right.budget.max_gpu_hours,
                    right.budget.max_model_calls,
                    right.budget.max_model_tokens,
                    right.budget.max_tool_calls,
                    right.budget.max_output_bytes,
                )
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
    aggregate_model_calls = sum(
        plan.budget.max_model_calls or 0 for plan in condition_records.values()
    )
    aggregate_tokens = sum(plan.budget.max_model_tokens or 0 for plan in condition_records.values())
    aggregate_tool_calls = sum(
        plan.budget.max_tool_calls or 0 for plan in condition_records.values()
    )
    aggregate_wall = sum(plan.budget.max_wall_seconds for plan in condition_records.values())
    aggregate_gpu_hours = sum(
        (Decimal(str(plan.budget.max_gpu_hours)) for plan in condition_records.values()),
        start=Decimal(0),
    )
    if (
        aggregate_cost != Decimal(str(profile_budget.get("max_cost_usd")))
        or (
            "max_model_calls" in profile_budget
            and aggregate_model_calls != profile_budget.get("max_model_calls")
        )
        or aggregate_tokens != profile_budget.get("max_model_tokens")
        or aggregate_wall != profile_budget.get("max_wall_seconds")
    ):
        raise ExecutionDisallowed("parent budget does not equal aggregate child hard caps")
    if "max_browser_actions" in profile_budget and (
        aggregate_tool_calls != profile_budget.get("max_browser_actions")
    ):
        raise ExecutionDisallowed("parent browser-action cap does not equal child hard caps")
    if "max_accelerator_hours" in profile_budget and (
        aggregate_gpu_hours != Decimal(str(profile_budget.get("max_accelerator_hours")))
    ):
        raise ExecutionDisallowed("parent accelerator-hour cap does not equal child hard caps")
    condition_limits = profile_budget.get("condition_limits")
    if isinstance(condition_limits, dict):
        if set(condition_limits) != set(expected_conditions):
            raise ExecutionDisallowed("parent condition-limit names do not match sampling")
        planned_model_calls = 0
        planned_tokens = 0
        planned_browser_actions = 0
        planned_wall = 0
        planned_cost = Decimal(0)
        planned_gpu_hours = Decimal(0)
        for condition_name, raw_limit in condition_limits.items():
            assert isinstance(condition_name, str)
            assert isinstance(raw_limit, dict)
            attempts = raw_limit.get("attempts")
            model_calls = raw_limit.get("max_model_calls_per_attempt")
            tokens = raw_limit.get("max_model_tokens_per_attempt")
            browser_actions = raw_limit.get("max_browser_actions_per_attempt")
            wall = raw_limit.get("max_wall_seconds_per_attempt")
            cost = raw_limit.get("max_openai_cost_usd_per_attempt")
            gpu_hours = raw_limit.get("max_accelerator_hours_per_attempt")
            assert isinstance(attempts, int)
            assert isinstance(model_calls, int)
            assert isinstance(tokens, int)
            assert isinstance(browser_actions, int)
            assert isinstance(wall, int)
            assert isinstance(cost, (int, float))
            assert isinstance(gpu_hours, (int, float))
            plans = [
                plan
                for plan in condition_records.values()
                if plan.identity.condition == condition_name
            ]
            if len(plans) != attempts or any(
                plan.budget.max_model_calls != model_calls
                or plan.budget.max_model_tokens != tokens
                or plan.budget.max_tool_calls != browser_actions
                or plan.budget.max_wall_seconds != wall
                or Decimal(str(plan.budget.max_cost_usd)) != Decimal(str(cost))
                or Decimal(str(plan.budget.max_gpu_hours)) != Decimal(str(gpu_hours))
                for plan in plans
            ):
                raise ExecutionDisallowed("parent condition limits do not match child hard caps")
            planned_model_calls += attempts * model_calls
            planned_tokens += attempts * tokens
            planned_browser_actions += attempts * browser_actions
            planned_wall += attempts * wall
            planned_cost += attempts * Decimal(str(cost))
            planned_gpu_hours += attempts * Decimal(str(gpu_hours))
        expected_aggregates = {
            "max_model_calls": planned_model_calls,
            "max_model_tokens": planned_tokens,
            "max_browser_actions": planned_browser_actions,
            "max_wall_seconds": planned_wall,
        }
        if any(profile_budget.get(field) != value for field, value in expected_aggregates.items()):
            raise ExecutionDisallowed("parent aggregate budget does not sum condition limits")
        if planned_cost != Decimal(str(profile_budget.get("max_cost_usd"))) or (
            planned_gpu_hours != Decimal(str(profile_budget.get("max_accelerator_hours")))
        ):
            raise ExecutionDisallowed("parent condition spend/time units do not reconcile")
        total_cost = Decimal(str(profile_budget.get("max_total_cost_usd")))
        provider_cost = Decimal(str(profile_budget.get("max_provider_compute_cost_usd")))
        if planned_cost + provider_cost != total_cost:
            raise ExecutionDisallowed("parent total spend cap does not reconcile")


def _load_authorized_run_profile(
    project_root: Path,
    schema_root: Path,
    value: object,
    terminal_control: TerminalExecutionControl | None,
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
    if terminal_control is not None:
        if plan_id in terminal_control.superseded_plan_ids:
            raise ExecutionDisallowed(
                "authorized run profile is consumed and nonreplayable under terminal control"
            )
        successor = terminal_control.registered_successor
        if successor is None:
            raise ExecutionDisallowed("terminal control names no registered successor profile")
        if (
            plan_id != successor.plan_id
            or profile_relative != successor.profile_path
            or recorded_sha256 != successor.profile_sha256
        ):
            raise ExecutionDisallowed(
                "authorized run profile does not match the registered terminal successor"
            )
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
    terminal_control = _load_terminal_execution_control(
        project_root,
        (schema_root or project_root).resolve(),
        data.get("current_execution_control"),
    )
    authorized_run_profile = _load_authorized_run_profile(
        project_root,
        (schema_root or project_root).resolve(),
        data.get("authorized_run_profile"),
        terminal_control,
    )
    raw_substrate = data.get("planned_execution_substrate")
    planned_substrate: PlannedExecutionSubstrate | None = None
    if raw_substrate is not None:
        if not isinstance(raw_substrate, dict):
            raise ExecutionDisallowed("planned execution substrate must be a mapping")
        expected_substrate_keys = {
            "decision_state",
            "provider",
            "architecture",
            "persistent_filesystem",
            "gate_l1_authorized",
            "gate_l1_evidence_state",
            "gate_l2_authorized",
            "gate_l2_decision_state",
            "gate_l3_state",
            "gate_l4_authorized",
            "local_alternatives",
            "decision_document",
            "security_decision_document",
        }
        if set(raw_substrate) != expected_substrate_keys:
            raise ExecutionDisallowed("planned execution substrate field set drifted")
        for field in (
            "decision_state",
            "provider",
            "architecture",
            "gate_l1_evidence_state",
            "gate_l2_decision_state",
            "gate_l3_state",
            "local_alternatives",
            "decision_document",
            "security_decision_document",
        ):
            if not isinstance(raw_substrate[field], str):
                raise ExecutionDisallowed(f"planned execution substrate {field} must be a string")
        for field in (
            "persistent_filesystem",
            "gate_l1_authorized",
            "gate_l2_authorized",
            "gate_l4_authorized",
        ):
            if type(raw_substrate[field]) is not bool:
                raise ExecutionDisallowed(f"planned execution substrate {field} must be a boolean")
        try:
            planned_substrate = PlannedExecutionSubstrate(
                decision_state=raw_substrate["decision_state"],
                provider=raw_substrate["provider"],
                architecture=raw_substrate["architecture"],
                persistent_filesystem=raw_substrate["persistent_filesystem"],
                gate_l1_authorized=raw_substrate["gate_l1_authorized"],
                gate_l1_evidence_state=raw_substrate["gate_l1_evidence_state"],
                gate_l2_authorized=raw_substrate["gate_l2_authorized"],
                gate_l2_decision_state=raw_substrate["gate_l2_decision_state"],
                gate_l3_state=raw_substrate["gate_l3_state"],
                gate_l4_authorized=raw_substrate["gate_l4_authorized"],
                local_alternatives=raw_substrate["local_alternatives"],
                decision_document=raw_substrate["decision_document"],
                security_decision_document=raw_substrate["security_decision_document"],
            )
        except (KeyError, ValueError) as exc:
            raise ExecutionDisallowed(f"invalid planned execution substrate: {exc}") from exc
        if any(
            bool(data[field])
            for field in (
                "paid_compute_allowed",
                "prototype_execution_allowed",
                "benchmark_execution_allowed",
                "training_allowed",
                "cloud_mutation_allowed",
            )
        ):
            raise ExecutionDisallowed(
                "design-only planned substrate requires every execution permission false"
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
        terminal_execution_control=terminal_control,
        planned_execution_substrate=planned_substrate,
    )


def execution_blockers(plan: RunPlan, state: ProjectExecutionState) -> tuple[str, ...]:
    """Return deterministic reasons why live execution is currently disallowed."""

    blockers: list[str] = []
    if state.phase_status != "in-progress":
        blockers.append(f"project phase status {state.phase_status!r} is not executable")
    if not plan.execution.authorization.authorized:
        blockers.append("run plan is not authorized")
    terminal_control = state.terminal_execution_control
    if terminal_control is not None:
        if plan.profile_plan_id in terminal_control.superseded_plan_ids:
            blockers.append("run plan parent profile is consumed and nonreplayable")
        else:
            successor = terminal_control.registered_successor
            if successor is None or (
                plan.profile_plan_id != successor.plan_id
                or plan.profile_sha256 != successor.profile_sha256
            ):
                blockers.append("run plan parent profile is not the registered successor")
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
