from __future__ import annotations

from dataclasses import replace

import pytest
from harness_test_support import project_state, typed_plan

from giclab.harness.models import (
    ExecutionAuthorization,
    ExecutionBackend,
    ExecutionContract,
)
from giclab.harness.policy import ExecutionDisallowed, assert_execution_allowed, execution_blockers


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
    blockers = execution_blockers(plan, project_state())
    assert any("not fully pinned: upstream_commit" in blocker for blocker in blockers)
    with pytest.raises(ExecutionDisallowed, match="not fully pinned"):
        assert_execution_allowed(plan, project_state())


def test_nonzero_cost_requires_paid_compute_permission() -> None:
    plan = typed_plan(authorized=True, max_cost_usd=0.01)
    assert any("paid compute" in blocker for blocker in execution_blockers(plan, project_state()))
    assert_execution_allowed(plan, project_state(paid=True))


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
    assert any("cloud mutation" in blocker for blocker in execution_blockers(plan, project_state()))


def test_non_in_progress_project_state_is_not_executable() -> None:
    blockers = execution_blockers(
        typed_plan(authorized=True), project_state(phase_status="blocked-user-action")
    )
    assert any("not executable" in blocker for blocker in blockers)
