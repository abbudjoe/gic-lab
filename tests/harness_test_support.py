from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from giclab.harness.models import (
    CommandSpec,
    ExecutionAuthorization,
    ExecutionContract,
    RunPlan,
    command_sha256,
)
from giclab.harness.plan import run_plan_from_mapping
from giclab.harness.policy import ProjectExecutionState


def valid_plan_data(
    *,
    authorized: bool = False,
    interpretation_allowed: bool = False,
    artifact_root: str = "synthetic",
    max_cost_usd: float = 0.0,
    max_gpu_hours: float = 0.0,
    max_model_tokens: int = 0,
    max_tool_calls: int = 0,
    max_output_bytes: int = 1024 * 1024,
    max_wall_seconds: int = 10,
    command_sha256_value: str | None = None,
) -> dict[str, Any]:
    binding = command_sha256_value or ("f" * 64 if authorized else None)
    return {
        "schema_version": "0.1.0",
        "experiment_id": "EXP-9000",
        "run_id": "RUN-SYNTHETIC-001",
        "profile": "smoke",
        "condition": "synthetic",
        "attempt": 1,
        "seed": 7,
        "interpretation_allowed": interpretation_allowed,
        "execution": {
            "backend": "local-subprocess",
            "workload": "prototype",
            "authorization": {
                "authorized": authorized,
                "authorization_reference": "AUTH-TEST-ONLY" if authorized else None,
                "command_sha256": binding,
            },
        },
        "sources": {
            "giclab_commit": "a" * 40,
            "upstream_source_id": "synthetic-source",
            "upstream_commit": "b" * 40,
            "protocol_sha256": "c" * 64,
            "config_sha256": "d" * 64,
            "model_revision": None,
            "dataset_revision": None,
            "environment_sha256": "e" * 64,
        },
        "budget": {
            "max_wall_seconds": max_wall_seconds,
            "max_cost_usd": max_cost_usd,
            "max_gpu_hours": max_gpu_hours,
            "max_model_tokens": max_model_tokens,
            "max_tool_calls": max_tool_calls,
            "max_output_bytes": max_output_bytes,
        },
        "artifacts": {"root": artifact_root, "retain_raw": True},
    }


def typed_plan(**kwargs: Any) -> RunPlan:
    return run_plan_from_mapping(valid_plan_data(**kwargs))


def bind_plan(plan: RunPlan, command: CommandSpec) -> RunPlan:
    return replace(
        plan,
        execution=ExecutionContract(
            backend=plan.execution.backend,
            workload=plan.execution.workload,
            authorization=ExecutionAuthorization(
                authorized=True,
                authorization_reference="AUTH-TEST-ONLY",
                command_sha256=command_sha256(command),
            ),
        ),
    )


def write_plan(path: Path, *, command: CommandSpec | None = None, **kwargs: Any) -> Path:
    if command is not None:
        kwargs["command_sha256_value"] = command_sha256(command)
    path.write_text(json.dumps(valid_plan_data(**kwargs)), encoding="utf-8")
    return path


def project_state(
    *,
    prototype: bool = True,
    paid: bool = False,
    cloud: bool = False,
    phase_status: str = "in-progress",
) -> ProjectExecutionState:
    return ProjectExecutionState(
        phase="1",
        phase_status=phase_status,
        paid_compute_allowed=paid,
        prototype_execution_allowed=prototype,
        benchmark_execution_allowed=False,
        training_allowed=False,
        cloud_mutation_allowed=cloud,
    )


def write_project_state(root: Path, *, prototype: bool) -> Path:
    docs = root / "docs"
    docs.mkdir(parents=True)
    state = docs / "PROJECT_STATE.yaml"
    state.write_text(
        "\n".join(
            (
                'phase: "1"',
                "phase_status: in-progress",
                "paid_compute_allowed: false",
                f"prototype_execution_allowed: {str(prototype).lower()}",
                "benchmark_execution_allowed: false",
                "training_allowed: false",
                "cloud_mutation_allowed: false",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return state
