from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from _category3_test_support import execute_shadow_plan

from giclab.control import production
from giclab.control.shadow_effects import ShadowFaultPlan
from giclab.harness import t09_sira_pilot as pilot
from giclab.harness.sira_gate_a import ProviderBudgetUsage
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[2]


def _passing_input() -> pilot.PairCheckpointInput:
    contract = V16_PROVIDER_CONTRACT
    return pilot.PairCheckpointInput(
        plan_id=contract.plan_id,
        attempt_run_ids=(contract.run_ids[0], contract.run_ids[1]),
        valid_evidence=(True, True),
        evaluator_succeeded=(True, True),
        valid_scored_attempt=(True, True),
        finalizer_closure_valid=True,
        pair_match_valid=True,
        credential_issue=False,
        cleanup_issue=False,
        severe_floor_or_ceiling_failure=False,
        actual_usage=ProviderBudgetUsage(
            cost_usd=0.5,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            model_call_attempts=8,
            default_service_tier_responses=8,
            browser_actions=4,
        ),
        actual_pair_wall_seconds=120.0,
        projected_aggregate_cost_usd=2.0,
        actual_lambda_cost_usd=0.0,
        remaining_campaign_seconds=10_000.0,
        next_attempt_hard_wall_seconds=3_600,
        prior_t09_cost_usd=contract.prior_t09_cost_usd,
        cumulative_t09_cost_cap_usd=contract.cumulative_t09_cost_cap_usd,
    )


@pytest.fixture(scope="module")
def checkpoint_receipts() -> dict[str, dict[str, object]]:
    plans = {
        "zero-score": ShadowFaultPlan("checkpoint-zero-score", task_a_zero_scores=True),
        "unscored": ShadowFaultPlan(
            "checkpoint-unscored",
            evaluator_unscored_run_index=1,
        ),
        "invalid": ShadowFaultPlan(
            "checkpoint-invalid-evaluator",
            evaluator_invalid_run_index=1,
        ),
        "missing-raw": ShadowFaultPlan(
            "checkpoint-missing-raw",
            checkpoint_missing_raw_after_task_a=True,
        ),
    }
    return {
        name: execute_shadow_plan(ROOT, V16_PROVIDER_CONTRACT, plan) for name, plan in plans.items()
    }


def _counts(receipt: dict[str, object]) -> dict[str, object]:
    value = receipt["call_counts"]
    assert isinstance(value, dict)
    return value


def _checkpoint(receipt: dict[str, object]) -> dict[str, object]:
    production_evidence = receipt["production_control_evidence"]
    assert isinstance(production_evidence, dict)
    value = production_evidence["first_pair_checkpoint"]
    assert isinstance(value, dict)
    return value


def test_both_task_a_attempts_scored_zero_may_continue(
    checkpoint_receipts: dict[str, dict[str, object]],
) -> None:
    receipt = checkpoint_receipts["zero-score"]
    checkpoint = _checkpoint(receipt)
    assert checkpoint["decision"] == "continue-to-task-b"
    assert checkpoint["reasons"] == []
    assert _counts(receipt)["condition_entries"] == 4


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("unscored", "task_a_valid_scored_attempt_missing"),
        ("invalid", "task_a_evaluator_failed"),
        ("missing-raw", "task_a_valid_evidence_missing"),
    ],
)
def test_task_a_invalid_evidence_stops_before_task_b(
    checkpoint_receipts: dict[str, dict[str, object]],
    case: str,
    reason: str,
) -> None:
    receipt = checkpoint_receipts[case]
    checkpoint = _checkpoint(receipt)
    assert checkpoint["decision"] == "stop-before-task-b"
    assert reason in checkpoint["reasons"]
    assert _counts(receipt)["condition_reservations"] == 2
    assert _counts(receipt)["condition_entries"] == 2
    assert receipt["cleanup"] == {
        "state": "complete",
        "resumed": False,
        "provider_resources_zero": True,
        "security_restored": True,
        "privacy_clean": True,
    }
    assert receipt["scientific_interpretation_allowed"] is False


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"valid_evidence": (True, False)}, "task_a_valid_evidence_missing"),
        ({"pair_match_valid": False}, "task_a_pair_match_invalid"),
        ({"finalizer_closure_valid": False}, "task_a_finalizer_closure_invalid"),
        (
            {"actual_usage": replace(_passing_input().actual_usage, model_call_attempts=2_310)},
            "first_pair_model_call_threshold_reached",
        ),
        (
            {
                "actual_usage": replace(
                    _passing_input().actual_usage,
                    input_tokens=1_999_950,
                    total_tokens=2_000_000,
                )
            },
            "first_pair_token_threshold_reached",
        ),
        (
            {"actual_usage": replace(_passing_input().actual_usage, browser_actions=60)},
            "first_pair_browser_action_threshold_reached",
        ),
        (
            {"actual_usage": replace(_passing_input().actual_usage, cost_usd=20.0)},
            "first_pair_openai_cost_threshold_reached",
        ),
        ({"actual_lambda_cost_usd": 4.0}, "first_pair_lambda_cost_threshold_reached"),
        (
            {
                "actual_usage": replace(_passing_input().actual_usage, cost_usd=20.0),
                "actual_lambda_cost_usd": 4.0,
            },
            "first_pair_total_cost_threshold_reached",
        ),
        (
            {"projected_aggregate_cost_usd": 64.0},
            "projected_cumulative_t09_cost_exceeds_hard_cap",
        ),
        (
            {"remaining_campaign_seconds": 5_159.999},
            "insufficient_campaign_time_for_next_attempt_and_cleanup",
        ),
        ({"credential_issue": True}, "credential_issue"),
        ({"cleanup_issue": True}, "cleanup_issue"),
    ],
)
def test_retained_first_pair_decision_enforces_every_stop_gate(
    changes: dict[str, object],
    reason: str,
) -> None:
    decision = pilot.first_pair_decision(replace(_passing_input(), **changes))
    assert decision["decision"] == "stop-before-task-b"
    assert reason in decision["reasons"]
    evidence = decision["checkpoint_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["actual_usage"] == pilot.usage_to_document(
        replace(_passing_input(), **changes).actual_usage
    )


def test_clean_checkpoint_persists_exact_retained_decision_then_admits_task_b(
    checkpoint_receipts: dict[str, dict[str, object]],
) -> None:
    receipt = checkpoint_receipts["zero-score"]
    checkpoint = _checkpoint(receipt)
    production_evidence = receipt["production_control_evidence"]
    assert isinstance(production_evidence, dict)
    primitives = production_evidence["production_primitives"]
    assert isinstance(primitives, list)
    assert "first_pair_decision" in primitives
    assert "record_first_pair_checkpoint" in primitives
    assert checkpoint["decision"] == "continue-to-task-b"
    assert isinstance(checkpoint["evidence_binding_sha256"], str)
    assert isinstance(checkpoint["provider_cost_receipt_sha256"], str)
    assert _counts(receipt)["condition_entries"] == 4


def test_shared_checkpoint_cannot_continue_without_retained_first_pair_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_value: pilot.PairCheckpointInput) -> dict[str, object]:
        raise pilot.T09PilotError("retained checkpoint deliberately unavailable")

    monkeypatch.setattr(production.pilot, "first_pair_decision", unavailable)
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan("checkpoint-retained-decision-coupling"),
    )
    assert receipt["earliest_stopping_phase"] == "first-pair-checkpoint"
    assert _counts(receipt)["condition_reservations"] == 2
    assert _counts(receipt)["condition_entries"] == 2


def test_mutated_persisted_checkpoint_decision_or_evidence_binding_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retained = production.pilot.record_first_pair_checkpoint

    def mutate_after_persistence(*args: object, **kwargs: object) -> None:
        retained(*args, **kwargs)
        state_path = Path(args[0])
        decision_path = state_path.parent / "first-pair-checkpoint-decision.json"
        document = json.loads(decision_path.read_bytes())
        document["evidence_binding_sha256"] = "f" * 64
        decision_path.write_text(
            json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        production.pilot,
        "record_first_pair_checkpoint",
        mutate_after_persistence,
    )
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan("checkpoint-persisted-decision-mutation"),
    )
    assert receipt["earliest_stopping_phase"] == "first-pair-checkpoint"
    assert _counts(receipt)["condition_entries"] == 2


def test_provider_cost_receipt_is_effect_produced_and_exactly_bound(
    checkpoint_receipts: dict[str, dict[str, object]],
) -> None:
    evidence = checkpoint_receipts["zero-score"]["production_control_evidence"]
    assert isinstance(evidence, dict)
    receipt = evidence["provider_cost_receipt"]
    assert isinstance(receipt, dict)
    assert isinstance(receipt["owned_instance_identity"], str)
    assert len(receipt["owned_instance_identity"]) == 64
    assert receipt["launch_ordinal"] == 1
    assert receipt["hourly_price_usd"] == 0.0
    assert receipt["prior_preflight_cost_usd"] == 0.0
    assert receipt["current_empirical_cost_usd"] == 0.0
    assert receipt["cumulative_provider_cost_usd"] == 0.0
    assert receipt["real_provider_effects"] is False
    assert (
        _checkpoint(checkpoint_receipts["zero-score"])["provider_cost_receipt_sha256"]
        == receipt["receipt_sha256"]
    )
