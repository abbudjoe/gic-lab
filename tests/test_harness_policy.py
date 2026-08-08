from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from harness_test_support import project_state, typed_plan, write_project_state

from giclab.harness.models import (
    ExecutionAuthorization,
    ExecutionBackend,
    ExecutionContract,
    RunProfile,
)
from giclab.harness.plan import load_run_plan
from giclab.harness.policy import (
    ExecutionDisallowed,
    assert_execution_allowed,
    execution_blockers,
    load_project_execution_state,
)
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


def test_sealed_children_must_match_parent_aggregate_budget(tmp_path: Path) -> None:
    write_project_state(
        tmp_path,
        prototype=True,
        profile_budget_overrides={"max_model_tokens": 1},
    )
    with pytest.raises(ExecutionDisallowed, match="aggregate child hard caps"):
        load_project_execution_state(tmp_path, schema_root=ROOT)


def test_pair_allows_condition_owned_config_and_command_hashes(tmp_path: Path) -> None:
    write_project_state(tmp_path, prototype=True)
    state = load_project_execution_state(tmp_path, schema_root=ROOT)
    assert state.authorized_run_profile is not None


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
