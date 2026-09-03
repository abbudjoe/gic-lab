from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from _category3_test_support import execute_shadow_plan

from giclab.control import production
from giclab.control.adapters import AdapterFailure
from giclab.control.effects import (
    ProviderCostObservationRequest,
    ProviderCostReceipt,
    ProviderHandle,
    ProviderLifecycleCostProof,
    ProviderLifecycleInterval,
)
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


@pytest.mark.parametrize("missing", ["valid_scored_attempt", "finalizer_closure_valid"])
def test_pair_checkpoint_requires_explicit_scored_and_finalizer_evidence(
    missing: str,
) -> None:
    values = {
        field: getattr(_passing_input(), field)
        for field in _passing_input().__dataclass_fields__
        if field != missing
    }
    with pytest.raises(TypeError, match="required positional argument"):
        pilot.PairCheckpointInput(**values)


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
        "privacy_clean": case != "missing-raw",
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


def test_provider_cost_receipt_reconciles_shared_derived_lifecycle_proof(
    checkpoint_receipts: dict[str, dict[str, object]],
) -> None:
    evidence = checkpoint_receipts["zero-score"]["production_control_evidence"]
    assert isinstance(evidence, dict)
    receipt = evidence["provider_cost_receipt"]
    assert isinstance(receipt, dict)
    assert isinstance(receipt["owned_instance_identity"], str)
    assert len(receipt["owned_instance_identity"]) == 64
    assert receipt["launch_ordinal"] == 1
    assert receipt["hourly_price_usd"] == 1.29
    assert receipt["prior_preflight_cost_usd"] == 0.0
    assert receipt["current_empirical_cost_usd"] == 0.0
    assert receipt["cumulative_provider_cost_usd"] == 0.0
    assert receipt["real_provider_effects"] is False
    proof = evidence["provider_lifecycle_cost_proof"]
    assert isinstance(proof, dict)
    assert proof["provider_profile_sha256"] == receipt["provider_profile_sha256"]
    assert proof["provider_price_source_sha256"] == receipt["provider_price_source_sha256"]
    assert proof["cumulative_provider_cost_usd"] == "0"
    assert proof["real_provider_effects"] is False
    assert (
        _checkpoint(checkpoint_receipts["zero-score"])["provider_cost_receipt_sha256"]
        == proof["receipt_sha256"]
    )


def _live_cost_documents() -> tuple[
    ProviderCostObservationRequest,
    ProviderLifecycleCostProof,
    ProviderCostReceipt,
]:
    handle = ProviderHandle("opaque-provider-owner", 2)
    request = ProviderCostObservationRequest(
        provider_handle=handle,
        observed_wall_time=30.0,
        observed_monotonic=20.0,
        campaign_started_wall_time=20.0,
        campaign_started_monotonic=10.0,
        provider_profile_sha256="1" * 64,
        provider_price_source_sha256="2" * 64,
        active_entry_receipt_sha256="3" * 64,
        closed_slot_receipt_sha256s=("4" * 64,),
        frozen_hourly_price_usd=1.29,
        active_started_wall_time=10.0,
        prior_preflight_cost_usd=0.01,
        current_empirical_cost_usd=0.02,
        cumulative_provider_cost_usd=0.03,
    )
    proof = ProviderLifecycleCostProof(
        provider_contract_version=V16_PROVIDER_CONTRACT.version,
        plan_id=V16_PROVIDER_CONTRACT.plan_id,
        provider_profile_sha256=request.provider_profile_sha256,
        provider_price_source_sha256=request.provider_price_source_sha256,
        active_entry_receipt_sha256=request.active_entry_receipt_sha256,
        closed_slot_source_binding_sha256s=request.closed_slot_receipt_sha256s,
        intervals=(
            ProviderLifecycleInterval(
                launch_ordinal=1,
                owned_instance_identity="closed-owner",
                entry_or_owner_receipt_sha256="5" * 64,
                closeout_receipt_sha256="6" * 64,
                active_started_wall_time=1.0,
                active_ended_wall_time=9.0,
                hourly_price_usd="1.29",
                billed_cost_usd="0.002866666666666666666666666667",
                billable_real_effect=True,
            ),
            ProviderLifecycleInterval(
                launch_ordinal=2,
                owned_instance_identity=handle.opaque_identity,
                entry_or_owner_receipt_sha256=request.active_entry_receipt_sha256,
                closeout_receipt_sha256=None,
                active_started_wall_time=request.active_started_wall_time,
                active_ended_wall_time=None,
                hourly_price_usd="1.29",
                billed_cost_usd="0.03",
                billable_real_effect=True,
            ),
        ),
        prior_preflight_cost_usd="0.01",
        current_empirical_cost_usd="0.02",
        cumulative_provider_cost_usd="0.03",
        observed_wall_time=request.observed_wall_time,
        observed_monotonic=request.observed_monotonic,
        real_provider_effects=True,
        receipt_sha256="7" * 64,
    )
    provisional = ProviderCostReceipt(
        provider_contract_version=V16_PROVIDER_CONTRACT.version,
        plan_id=V16_PROVIDER_CONTRACT.plan_id,
        owned_instance_identity=handle.opaque_identity,
        launch_ordinal=handle.launch_ordinal,
        provider_profile_sha256=request.provider_profile_sha256,
        provider_price_source_sha256=request.provider_price_source_sha256,
        active_entry_receipt_sha256=request.active_entry_receipt_sha256,
        closed_slot_receipt_sha256s=request.closed_slot_receipt_sha256s,
        hourly_price_usd=request.frozen_hourly_price_usd,
        active_started_wall_time=request.active_started_wall_time,
        active_ended_wall_time=None,
        observed_wall_time=request.observed_wall_time,
        observed_monotonic=request.observed_monotonic,
        prior_preflight_cost_usd=request.prior_preflight_cost_usd,
        current_empirical_cost_usd=request.current_empirical_cost_usd,
        cumulative_provider_cost_usd=request.cumulative_provider_cost_usd,
        real_provider_effects=True,
        receipt_sha256="0" * 64,
    )
    receipt = replace(
        provisional,
        receipt_sha256=production.ProductionCategory3World._provider_cost_receipt_identity(
            provisional
        ),
    )
    return request, proof, receipt


def test_exact_shared_derived_live_provider_reconciliation_passes() -> None:
    request, proof, receipt = _live_cost_documents()
    production.ProductionCategory3World._validate_provider_cost_reconciliation(
        receipt=receipt,
        request=request,
        proof=proof,
        contract=V16_PROVIDER_CONTRACT,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"hourly_price_usd": 0.0},
        {"hourly_price_usd": 2.0},
        {"active_started_wall_time": 30.0},
        {"active_started_wall_time": 9.0},
        {"active_ended_wall_time": 8.0},
        {"active_ended_wall_time": 31.0},
        {"closed_slot_receipt_sha256s": ()},
        {"owned_instance_identity": "wrong-owner"},
        {"launch_ordinal": 1},
        {"provider_profile_sha256": "8" * 64},
        {"provider_price_source_sha256": "9" * 64},
        {"active_entry_receipt_sha256": "a" * 64},
        {"prior_preflight_cost_usd": 0.0},
        {"current_empirical_cost_usd": 0.01, "cumulative_provider_cost_usd": 0.02},
        {"observed_wall_time": 29.0},
        {"observed_monotonic": 30.0},
    ],
)
def test_self_consistent_effect_receipt_cannot_understate_or_rewrite_lifecycle_truth(
    changes: dict[str, object],
) -> None:
    request, proof, receipt = _live_cost_documents()
    mutated = replace(receipt, **changes)
    mutated = replace(
        mutated,
        receipt_sha256=production.ProductionCategory3World._provider_cost_receipt_identity(mutated),
    )
    with pytest.raises(AdapterFailure, match="shared-derived lifecycle evidence"):
        production.ProductionCategory3World._validate_provider_cost_reconciliation(
            receipt=mutated,
            request=request,
            proof=proof,
            contract=V16_PROVIDER_CONTRACT,
        )


def test_retained_provider_source_mutation_stops_before_task_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_retained_price(*_args: object, **_kwargs: object) -> object:
        raise AdapterFailure("retained provider price source receipt changed")

    monkeypatch.setattr(
        production.ProductionCategory3World,
        "_retained_provider_price",
        broken_retained_price,
    )
    receipt = execute_shadow_plan(ROOT, V16_PROVIDER_CONTRACT, ShadowFaultPlan("source-break"))
    assert receipt["earliest_stopping_phase"] == "first-pair-checkpoint"
    assert _counts(receipt)["condition_entries"] == 2


def test_checkpoint_receives_only_the_exact_shared_derived_provider_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retained = production.pilot.first_pair_decision
    captured: list[pilot.PairCheckpointInput] = []

    def capture(value: pilot.PairCheckpointInput) -> dict[str, object]:
        captured.append(value)
        return retained(value)

    monkeypatch.setattr(production.pilot, "first_pair_decision", capture)
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan("checkpoint-provider-cost-coupling"),
    )
    assert len(captured) == 1
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    proof = evidence["provider_lifecycle_cost_proof"]
    assert isinstance(proof, dict)
    assert captured[0].actual_lambda_cost_usd == float(proof["cumulative_provider_cost_usd"])
    assert _counts(receipt)["condition_entries"] == 4


def test_omitted_closed_replacement_slot_stops_before_task_b() -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            "provider-entry-replacement",
            provider_cost_receipt_fault="omitted-closed-slot",
        ),
    )
    assert receipt["earliest_stopping_phase"] == "first-pair-checkpoint"
    assert _counts(receipt)["condition_entries"] == 2


def test_source_bound_replacement_slot_is_included_once() -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan("provider-entry-replacement"),
    )
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    proof = evidence["provider_lifecycle_cost_proof"]
    assert isinstance(proof, dict)
    assert len(proof["intervals"]) == 2  # type: ignore[arg-type]
    assert len(proof["closed_slot_source_binding_sha256s"]) == 1  # type: ignore[arg-type]
    assert _counts(receipt)["condition_entries"] == 4


@pytest.mark.parametrize(
    "fault",
    [
        "zero-price",
        "wrong-price",
        "shifted-active-start",
        "active-end-before-start",
        "active-end-after-observation",
        "wrong-owner",
        "wrong-ordinal",
        "wrong-profile-hash",
        "wrong-price-source-hash",
        "wrong-entry-hash",
        "stale-observation",
        "cross-domain-observation",
    ],
)
def test_production_checkpoint_rejects_effect_provider_cost_drift(fault: str) -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            f"provider-cost-reconciliation-{fault}",
            provider_cost_receipt_fault=fault,
        ),
    )
    assert receipt["earliest_stopping_phase"] == "first-pair-checkpoint"
    assert _counts(receipt)["condition_entries"] == 2
