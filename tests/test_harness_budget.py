from __future__ import annotations

from dataclasses import replace

import pytest

from giclab.harness.budget import BudgetContractChanged, BudgetExceeded, BudgetGuard
from giclab.harness.models import RunBudget


def test_budget_guard_rejects_excess_without_mutating_usage() -> None:
    guard = BudgetGuard(RunBudget(max_wall_seconds=100, max_cost_usd=1.0))
    guard.record(cost_usd=0.75)
    with pytest.raises(BudgetExceeded, match="cost_usd"):
        guard.record(cost_usd=0.30)
    assert guard.usage.cost_usd == 0.75


def test_budget_guard_tracks_all_bounded_units() -> None:
    guard = BudgetGuard(
        RunBudget(
            max_wall_seconds=100,
            max_cost_usd=2.0,
            max_gpu_hours=1.0,
            max_model_tokens=1000,
            max_tool_calls=10,
        )
    )
    usage = guard.record(
        wall_seconds=2.5,
        cost_usd=0.5,
        gpu_hours=0.25,
        model_tokens=250,
        tool_calls=2,
    )
    assert usage.model_tokens == 250
    assert usage.tool_calls == 2
    assert guard.remaining_wall_seconds == 97.5


@pytest.mark.parametrize("value", [-1.0, float("inf"), float("nan")])
def test_budget_guard_rejects_invalid_increments(value: float) -> None:
    guard = BudgetGuard(RunBudget(max_wall_seconds=100, max_cost_usd=1.0))
    with pytest.raises(ValueError, match="finite and non-negative"):
        guard.record(cost_usd=value)


def test_budget_limits_cannot_change_during_run() -> None:
    limits = RunBudget(max_wall_seconds=100, max_cost_usd=1.0)
    guard = BudgetGuard(limits)
    guard.record(wall_seconds=1)
    with pytest.raises(BudgetContractChanged, match="immutable"):
        guard.assert_limits_unchanged(replace(limits, max_cost_usd=2.0))
    with pytest.raises(BudgetContractChanged, match="immutable"):
        guard.assert_limits_unchanged(replace(limits, max_cost_usd=0.5))


def test_budget_guard_state_is_write_owned() -> None:
    guard = BudgetGuard(RunBudget(max_wall_seconds=100, max_cost_usd=1.0))
    with pytest.raises(AttributeError, match="write-owned"):
        guard._usage = guard.usage
    with pytest.raises(AttributeError, match="write-owned"):
        guard._limits = guard.limits
