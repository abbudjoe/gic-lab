from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from shutil import copytree

import pytest
import yaml
from harness_test_support import project_state, typed_plan, write_project_state

from giclab.harness.models import (
    ExecutionAuthorization,
    ExecutionBackend,
    ExecutionContract,
    RunProfile,
)
from giclab.harness.plan import load_run_plan, run_plan_authorization_sha256
from giclab.harness.policy import (
    ExecutionDisallowed,
    assert_execution_allowed,
    execution_blockers,
    load_project_execution_state,
)
from giclab.registry import load_yaml
from giclab.validation import ROOT


def test_run_authorization_and_project_permission_are_independent_gates() -> None:
    unauthorized = typed_plan()
    assert "run plan is not authorized" in execution_blockers(unauthorized, project_state())

    authorized = typed_plan(authorized=True)
    blockers = execution_blockers(authorized, project_state(prototype=False))
    assert any("disallows prototype" in blocker for blocker in blockers)
    with pytest.raises(ExecutionDisallowed, match="prototype"):
        assert_execution_allowed(authorized, project_state(prototype=False))


def test_authorized_plan_is_allowed_only_when_project_gate_matches() -> None:
    assert_execution_allowed(typed_plan(authorized=True), project_state())


def test_unknown_source_provenance_blocks_live_execution() -> None:
    plan = typed_plan(authorized=True)
    plan = replace(
        plan,
        sources=replace(plan.sources, upstream_commit="unknown"),
    )
    blockers = execution_blockers(plan, project_state(allowed_plan=plan))
    assert any("not fully pinned: upstream_commit" in blocker for blocker in blockers)
    with pytest.raises(ExecutionDisallowed, match="not fully pinned"):
        assert_execution_allowed(plan, project_state(allowed_plan=plan))


def test_nonzero_cost_requires_paid_compute_permission() -> None:
    plan = typed_plan(authorized=True, max_cost_usd=0.01)
    assert any(
        "paid compute" in blocker
        for blocker in execution_blockers(plan, project_state(allowed_plan=plan))
    )
    assert_execution_allowed(plan, project_state(paid=True, allowed_plan=plan))


def test_cloud_backend_requires_cloud_permission() -> None:
    plan = typed_plan(authorized=True)
    plan = replace(
        plan,
        execution=ExecutionContract(
            backend=ExecutionBackend.CLOUD,
            workload=plan.execution.workload,
            authorization=ExecutionAuthorization(True, "AUTH-TEST-ONLY", "f" * 64),
        ),
    )
    assert any(
        "cloud mutation" in blocker
        for blocker in execution_blockers(plan, project_state(allowed_plan=plan))
    )


def test_non_in_progress_project_state_is_not_executable() -> None:
    blockers = execution_blockers(
        typed_plan(authorized=True), project_state(phase_status="blocked-user-action")
    )
    assert any("not executable" in blocker for blocker in blockers)


def test_parent_profile_identity_and_hash_are_runtime_gates() -> None:
    plan = typed_plan(authorized=True)
    wrong_id = replace(plan, profile_plan_id="PLAN-SYNTHETIC-PILOT")
    assert any(
        "parent profile does not match" in blocker
        for blocker in execution_blockers(wrong_id, project_state())
    )
    wrong_hash = replace(plan, profile_sha256="0" * 64)
    assert any(
        "parent profile hash does not match" in blocker
        for blocker in execution_blockers(wrong_hash, project_state())
    )


def test_undeclared_plan_cannot_replay_a_valid_parent_binding() -> None:
    declared = typed_plan(authorized=True)
    masquerader = replace(
        declared,
        identity=replace(
            declared.identity,
            experiment_id="EXP-9999",
            run_id="RUN-SYNTHETIC-UNDECLARED",
            condition="undeclared",
        ),
        profile=RunProfile.PILOT,
    )
    blockers = execution_blockers(masquerader, project_state(allowed_plan=declared))
    assert "run plan is not a declared child of the authorized profile" in blockers


@pytest.mark.parametrize(
    ("eligibility", "blockers", "message"),
    (
        (
            "blocked-pending-prerequisites",
            ("Smoke evidence is not complete.",),
            "not execution-eligible",
        ),
        (
            "eligible-after-authorization",
            ("A blocker cannot coexist with eligibility.",),
            "retains unresolved execution blockers",
        ),
    ),
)
def test_invalid_profile_readiness_cannot_materialize_runtime_authorization(
    tmp_path: Path,
    eligibility: str,
    blockers: tuple[str, ...],
    message: str,
) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        eligibility=eligibility,
        blockers=blockers,
    )
    with pytest.raises(ExecutionDisallowed, match=message):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_terminal_control_prevents_authorizing_a_consumed_registered_profile(
    tmp_path: Path,
) -> None:
    copytree(ROOT / "experiments", tmp_path / "experiments")
    copytree(ROOT / "schemas", tmp_path / "schemas")
    (tmp_path / "docs").mkdir()
    state = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")
    smoke_path = "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml"
    state["authorized_run_profile"] = {
        "plan_id": "PLAN-EXP0001-SMOKE",
        "profile_path": smoke_path,
        "profile_sha256": hashlib.sha256((tmp_path / smoke_path).read_bytes()).hexdigest(),
        "condition_plan_sha256s": ["0" * 64],
    }
    (tmp_path / "docs/PROJECT_STATE.yaml").write_text(
        yaml.safe_dump(state, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(ExecutionDisallowed, match="consumed and nonreplayable"):
        load_project_execution_state(tmp_path, schema_root=tmp_path)


def test_project_state_cannot_drop_a_registered_terminal_control(tmp_path: Path) -> None:
    copytree(ROOT / "experiments", tmp_path / "experiments")
    copytree(ROOT / "schemas", tmp_path / "schemas")
    (tmp_path / "docs").mkdir()
    state = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")
    state.pop("current_execution_control")
    (tmp_path / "docs/PROJECT_STATE.yaml").write_text(
        yaml.safe_dump(state, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(ExecutionDisallowed, match="must bind the registry terminal"):
        load_project_execution_state(tmp_path, schema_root=tmp_path)


def test_unregistered_coherent_exp0001_successor_cannot_bypass_terminal_control(
    tmp_path: Path,
) -> None:
    write_project_state(tmp_path, prototype=True)
    copytree(ROOT / "experiments", tmp_path / "experiments")
    copytree(ROOT / "schemas", tmp_path / "schemas")

    profile_relative = "run-profiles/synthetic-smoke.yaml"
    profile_path = tmp_path / profile_relative
    profile = load_yaml(profile_path)
    profile["experiment_id"] = "EXP-0001"
    profile_text = yaml.safe_dump(profile, sort_keys=False)
    profile_path.write_text(profile_text, encoding="utf-8")
    profile_sha256 = hashlib.sha256(profile_text.encode()).hexdigest()

    condition_sha256s: list[str] = []
    for relative in profile["condition_plan_paths"]:
        condition_path = tmp_path / relative
        condition = json.loads(condition_path.read_text(encoding="utf-8"))
        condition["experiment_id"] = "EXP-0001"
        condition["profile_sha256"] = profile_sha256
        condition_path.write_text(json.dumps(condition), encoding="utf-8")
        condition_sha256s.append(
            run_plan_authorization_sha256(load_run_plan(condition_path, schema_root=tmp_path))
        )

    state_path = tmp_path / "docs/PROJECT_STATE.yaml"
    state = load_yaml(state_path)
    state["current_execution_control"] = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")[
        "current_execution_control"
    ]
    state["authorized_run_profile"] = {
        "plan_id": profile["plan_id"],
        "profile_path": profile_relative,
        "profile_sha256": profile_sha256,
        "condition_plan_sha256s": condition_sha256s,
    }
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")

    with pytest.raises(ExecutionDisallowed, match="names no registered successor"):
        load_project_execution_state(tmp_path, schema_root=tmp_path)


def test_registry_cannot_add_a_successor_without_terminal_control_update(tmp_path: Path) -> None:
    copytree(ROOT / "experiments", tmp_path / "experiments")
    copytree(ROOT / "schemas", tmp_path / "schemas")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/PROJECT_STATE.yaml").write_bytes(
        (ROOT / "docs/PROJECT_STATE.yaml").read_bytes()
    )
    registry_path = tmp_path / "experiments/registry.yaml"
    registry = load_yaml(registry_path)
    registry["experiments"][0]["run_profiles"].append("run-profiles/unbound-successor.yaml")
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    with pytest.raises(ExecutionDisallowed, match="terminal control names no successor"):
        load_project_execution_state(tmp_path, schema_root=tmp_path)


def test_terminal_control_cannot_name_a_successor_absent_from_registry(tmp_path: Path) -> None:
    copytree(ROOT / "experiments", tmp_path / "experiments")
    copytree(ROOT / "schemas", tmp_path / "schemas")
    (tmp_path / "docs").mkdir()
    state_path = tmp_path / "docs/PROJECT_STATE.yaml"
    state = load_yaml(ROOT / "docs/PROJECT_STATE.yaml")
    control_relative = state["current_execution_control"]["path"]
    control_path = tmp_path / control_relative
    control = json.loads(control_path.read_text(encoding="utf-8"))
    control["successor"].update(
        {
            "plan_id": "PLAN-EXP0001-PILOT-V6",
            "profile_path": "run-profiles/unregistered-successor.yaml",
            "profile_sha256": "0" * 64,
        }
    )
    control_path.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")
    control_sha256 = hashlib.sha256(control_path.read_bytes()).hexdigest()
    state["current_execution_control"]["sha256"] = control_sha256
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")
    registry_path = tmp_path / "experiments/registry.yaml"
    registry = load_yaml(registry_path)
    registry["experiments"][0]["current_execution_control"]["sha256"] = control_sha256
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    with pytest.raises(ExecutionDisallowed, match="sole fresh registered profile"):
        load_project_execution_state(tmp_path, schema_root=tmp_path)


def test_sealed_children_must_match_parent_aggregate_budget(tmp_path: Path) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        profile_budget_overrides={"max_model_tokens": 1},
    )
    with pytest.raises(ExecutionDisallowed, match="aggregate child hard caps"):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_pair_allows_only_condition_owned_command_hashes(tmp_path: Path) -> None:
    write_project_state(tmp_path, prototype=True)
    state = load_project_execution_state(tmp_path, schema_root=ROOT)
    assert state.authorized_run_profile is not None


def test_pair_rejects_config_hash_drift(tmp_path: Path) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        companion_source_overrides={"config_sha256": "1" * 64},
    )
    with pytest.raises(ExecutionDisallowed, match="fixed source identity drifts"):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_pair_rejects_fixed_source_identity_drift(tmp_path: Path) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        companion_source_overrides={"upstream_commit": "0" * 40},
    )
    with pytest.raises(ExecutionDisallowed, match="fixed source identity drifts"):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_children_must_match_parent_authorized_model_revision(tmp_path: Path) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        child_model_revision="MODEL-NOT-PARENT",
    )
    with pytest.raises(ExecutionDisallowed, match="parent model revision"):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_children_must_match_parent_task_source(tmp_path: Path) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        task_source="query=a different task",
    )
    with pytest.raises(ExecutionDisallowed, match="parent query task source"):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_child_query_prefix_cannot_match_a_longer_parent_query(tmp_path: Path) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        child_query="synthetic",
    )
    with pytest.raises(ExecutionDisallowed, match="parent query task source"):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_parent_pair_order_must_name_each_expected_condition_once(tmp_path: Path) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        second_condition="synthetic",
    )
    with pytest.raises(ExecutionDisallowed, match="each expected condition once"):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_parent_pair_and_task_identities_must_be_unique(tmp_path: Path) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        duplicate_pair_row=True,
    )
    with pytest.raises(ExecutionDisallowed, match="pair and task IDs must be unique"):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_legacy_authorized_v01_plan_is_readable_but_not_executable() -> None:
    plan = load_run_plan(
        ROOT / "tests/fixtures/harness/legacy-authorized-run-plan-v0.1.json",
        schema_root=ROOT,
    )
    blockers = execution_blockers(plan, project_state())
    assert "run plan parent profile does not match project authorization" in blockers
    assert "run plan is not a declared child of the authorized profile" in blockers
