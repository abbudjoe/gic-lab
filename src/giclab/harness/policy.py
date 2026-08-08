"""Typed project-state authorization for harness execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from giclab.registry import DuplicateKeyError, load_yaml

from .models import ExecutionBackend, RunPlan, WorkloadKind


class ExecutionDisallowed(PermissionError):
    """Raised before process creation when a control plane disallows execution."""


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


def load_project_execution_state(project_root: Path) -> ProjectExecutionState:
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
    return ProjectExecutionState(
        phase=str(data["phase"]),
        phase_status=str(data["phase_status"]),
        paid_compute_allowed=bool(data["paid_compute_allowed"]),
        prototype_execution_allowed=bool(data["prototype_execution_allowed"]),
        benchmark_execution_allowed=bool(data["benchmark_execution_allowed"]),
        training_allowed=bool(data["training_allowed"]),
        cloud_mutation_allowed=bool(data["cloud_mutation_allowed"]),
    )


def execution_blockers(plan: RunPlan, state: ProjectExecutionState) -> tuple[str, ...]:
    """Return deterministic reasons why live execution is currently disallowed."""

    blockers: list[str] = []
    if state.phase_status != "in-progress":
        blockers.append(f"project phase status {state.phase_status!r} is not executable")
    if not plan.execution.authorization.authorized:
        blockers.append("run plan is not authorized")
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
