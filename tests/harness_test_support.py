from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from giclab.harness.models import (
    CommandSpec,
    ExecutionAuthorization,
    ExecutionContract,
    RunPlan,
    command_sha256,
)
from giclab.harness.plan import run_plan_authorization_sha256, run_plan_from_mapping
from giclab.harness.policy import AuthorizedRunProfile, ProjectExecutionState

SYNTHETIC_PROFILE_SHA256 = "9" * 64
SYNTHETIC_PRIMARY_PLAN = "plans/synthetic.json"
SYNTHETIC_COMPANION_PLAN = "plans/synthetic-companion.json"


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
    experiment_id: str = "EXP-9000",
    run_id: str = "RUN-SYNTHETIC-001",
    profile: str = "smoke",
    condition: str = "synthetic",
    profile_plan_id: str | None = "PLAN-SYNTHETIC-SMOKE",
    profile_sha256_value: str | None = SYNTHETIC_PROFILE_SHA256,
    paired_order: int | None = None,
) -> dict[str, Any]:
    binding = command_sha256_value or ("f" * 64 if authorized else None)
    document = {
        "schema_version": "0.1.0",
        "experiment_id": experiment_id,
        "run_id": run_id,
        "profile": profile,
        "condition": condition,
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
    if profile_plan_id is not None and profile_sha256_value is not None:
        document["profile_plan_id"] = profile_plan_id
        document["profile_sha256"] = profile_sha256_value
    if paired_order is not None:
        document["task"] = {
            "task_id": "TASK-SYNTHETIC-001",
            "source_kind": "open-ended-query",
            "query": "synthetic policy fixture",
            "dataset_id": None,
            "dataset_revision": None,
            "start_idx": None,
            "end_idx": None,
        }
        document["pairing"] = {
            "pair_id": "PAIR-SYNTHETIC-001",
            "order_index": paired_order,
        }
    return document


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(valid_plan_data(**kwargs)), encoding="utf-8")
    return path


def project_state(
    *,
    prototype: bool = True,
    paid: bool = False,
    cloud: bool = False,
    phase_status: str = "in-progress",
    allowed_plan: RunPlan | None = None,
) -> ProjectExecutionState:
    member = allowed_plan or typed_plan(authorized=True)
    return ProjectExecutionState(
        phase="1",
        phase_status=phase_status,
        paid_compute_allowed=paid,
        prototype_execution_allowed=prototype,
        benchmark_execution_allowed=False,
        training_allowed=False,
        cloud_mutation_allowed=cloud,
        authorized_run_profile=AuthorizedRunProfile(
            plan_id="PLAN-SYNTHETIC-SMOKE",
            profile_sha256=SYNTHETIC_PROFILE_SHA256,
            authorization_reference="AUTH-TEST-ONLY",
            condition_plan_sha256s=frozenset({run_plan_authorization_sha256(member)}),
        ),
    )


def write_project_state(
    root: Path,
    *,
    prototype: bool,
    authorize_profile: bool = True,
    eligibility: str = "eligible-after-authorization",
    blockers: tuple[str, ...] = (),
    primary_plan_data: dict[str, Any] | None = None,
    profile_budget_overrides: dict[str, int | float] | None = None,
    companion_source_overrides: dict[str, str | None] | None = None,
    child_model_revision: str = "synthetic-v1",
    task_source: str = "query=synthetic policy fixture",
    second_condition: str = "synthetic-companion",
    child_query: str = "synthetic policy fixture",
    duplicate_pair_row: bool = False,
) -> str | None:
    docs = root / "docs"
    docs.mkdir(parents=True)
    digest: str | None = None
    if authorize_profile:
        profiles = root / "run-profiles"
        profiles.mkdir(parents=True)
        primary = json.loads(
            json.dumps(
                primary_plan_data
                or valid_plan_data(
                    authorized=True,
                    profile_sha256_value="0" * 64,
                    paired_order=1,
                )
            )
        )
        companion = valid_plan_data(
            authorized=True,
            run_id="RUN-SYNTHETIC-COMPANION",
            condition="synthetic-companion",
            profile_sha256_value="0" * 64,
            paired_order=2,
        )
        companion["budget"] = json.loads(json.dumps(primary["budget"]))
        primary_task = primary["task"]
        companion_task = companion["task"]
        assert isinstance(primary_task, dict)
        assert isinstance(companion_task, dict)
        primary_task["query"] = child_query
        companion_task["query"] = child_query
        primary_sources = primary["sources"]
        companion_sources = companion["sources"]
        assert isinstance(primary_sources, dict)
        assert isinstance(companion_sources, dict)
        primary_sources["model_revision"] = child_model_revision
        companion_sources["model_revision"] = child_model_revision
        companion_sources["config_sha256"] = "1" * 64
        if companion_source_overrides:
            companion_sources.update(companion_source_overrides)
        companion_authorization = companion["execution"]["authorization"]
        assert isinstance(companion_authorization, dict)
        companion_authorization["command_sha256"] = "2" * 64
        primary_fingerprint = run_plan_authorization_sha256(run_plan_from_mapping(primary))
        companion_fingerprint = run_plan_authorization_sha256(run_plan_from_mapping(companion))
        primary_budget = primary["budget"]
        companion_budget = companion["budget"]
        assert isinstance(primary_budget, dict)
        assert isinstance(companion_budget, dict)
        profile = {
            "schema_version": "0.1.0",
            "experiment_id": "EXP-9000",
            "plan_id": "PLAN-SYNTHETIC-SMOKE",
            "profile": "smoke",
            "study_stage": "exploratory",
            "purpose": "Exercise the exact parent-profile runtime authorization gate.",
            "sample_rationale": "One synthetic pair is sufficient for deterministic policy tests.",
            "interpretation_allowed": False,
            "execution": {
                "authorized": True,
                "authorization_reference": "AUTH-TEST-ONLY",
            },
            "model": {
                "provider": "synthetic",
                "manifest_id": "MODEL-SYNTHETIC",
                "api": "https://example.invalid/v1/",
                "upstream_alias": "synthetic",
                "proposed_immutable_revision": "synthetic-v1",
                "historical_revision_known": True,
                "reproduction_level": "artifact-execution",
                "substitution": None,
            },
            "sampling": {
                "pair_count": 1,
                "conditions": [primary["condition"], companion["condition"]],
                "task_family": "synthetic",
                "dataset_ids": [],
                "counterbalancing": [
                    {
                        "pair_id": "PAIR-SYNTHETIC-001",
                        "task_id": "TASK-SYNTHETIC-001",
                        "task_source": task_source,
                        "first": primary["condition"],
                        "second": second_condition,
                        "plans": [
                            {
                                "condition": primary["condition"],
                                "path": SYNTHETIC_PRIMARY_PLAN,
                            },
                            {
                                "condition": "synthetic-companion",
                                "path": SYNTHETIC_COMPANION_PLAN,
                            },
                        ],
                    }
                ],
            },
            "budget": {
                "pricing_record": "synthetic-pricing.yaml",
                "max_cost_usd": (primary_budget["max_cost_usd"] + companion_budget["max_cost_usd"]),
                "max_model_tokens": (
                    primary_budget["max_model_tokens"] + companion_budget["max_model_tokens"]
                ),
                "max_wall_seconds": (
                    primary_budget["max_wall_seconds"] + companion_budget["max_wall_seconds"]
                ),
            },
            "artifacts": {
                "root": "synthetic",
                "retain_raw": True,
                "public_release": "blocked-pending-review",
            },
            "condition_plan_paths": [SYNTHETIC_PRIMARY_PLAN, SYNTHETIC_COMPANION_PLAN],
            "readiness": {
                "execution_eligibility": eligibility,
                "approval_changes_required": ["synthetic authorization fixture"],
                "unresolved_execution_blockers": list(blockers),
            },
        }
        if profile_budget_overrides:
            profile["budget"].update(profile_budget_overrides)
        if duplicate_pair_row:
            sampling = profile["sampling"]
            assert isinstance(sampling, dict)
            counterbalancing = sampling["counterbalancing"]
            assert isinstance(counterbalancing, list)
            counterbalancing.append(json.loads(json.dumps(counterbalancing[0])))
        profile_text = yaml.safe_dump(profile, sort_keys=False)
        digest = hashlib.sha256(profile_text.encode()).hexdigest()
        (profiles / "synthetic-smoke.yaml").write_text(profile_text, encoding="utf-8")
        primary["profile_sha256"] = digest
        companion["profile_sha256"] = digest
        primary_path = root / SYNTHETIC_PRIMARY_PLAN
        primary_path.parent.mkdir(parents=True)
        primary_path.write_text(json.dumps(primary), encoding="utf-8")
        companion_path = root / SYNTHETIC_COMPANION_PLAN
        companion_path.write_text(json.dumps(companion), encoding="utf-8")
    state = docs / "PROJECT_STATE.yaml"
    if digest is None:
        profile_lines = (
            "authorized_run_profile:",
            "  plan_id: null",
            "  profile_path: null",
            "  profile_sha256: null",
            "  condition_plan_sha256s: []",
        )
    else:
        profile_lines = (
            "authorized_run_profile:",
            "  plan_id: PLAN-SYNTHETIC-SMOKE",
            "  profile_path: run-profiles/synthetic-smoke.yaml",
            f"  profile_sha256: {digest}",
            "  condition_plan_sha256s:",
            f"    - {primary_fingerprint}",
            f"    - {companion_fingerprint}",
        )
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
                *profile_lines,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return digest


def write_authorized_project_plan(
    root: Path,
    command: CommandSpec,
    *,
    prototype: bool,
    **kwargs: Any,
) -> tuple[Path, str]:
    primary = valid_plan_data(
        authorized=True,
        command_sha256_value=command_sha256(command),
        profile_sha256_value="0" * 64,
        paired_order=1,
        **kwargs,
    )
    digest = write_project_state(
        root,
        prototype=prototype,
        primary_plan_data=primary,
    )
    assert digest is not None
    return root / SYNTHETIC_PRIMARY_PLAN, digest
