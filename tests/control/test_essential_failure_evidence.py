from __future__ import annotations

from pathlib import Path

import pytest
from _category3_test_support import execute_shadow_plan

from giclab.control import production
from giclab.control.effects import MAX_ESSENTIAL_FAILURE_BYTES
from giclab.control.shadow_effects import ShadowFaultPlan
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[2]


FAILURE_PLANS = {
    "known-provider": ShadowFaultPlan("known-provider-exception"),
    "known-transport": ShadowFaultPlan("known-transport-failure"),
    "ambiguous-send": ShadowFaultPlan("ambiguous-task-model-send"),
    "response-accounting": ShadowFaultPlan("response-accounting-incomplete"),
    "token-admission": ShadowFaultPlan(
        "essential-token-admission",
        model_input_tokens_over_cap=True,
    ),
    "cost-admission": ShadowFaultPlan(
        "essential-cost-admission",
        model_cost_over_cap=True,
    ),
    "browser-admission": ShadowFaultPlan(
        "essential-browser-admission",
        browser_actions_over_cap=True,
    ),
    "output-admission": ShadowFaultPlan(
        "essential-output-admission",
        output_bytes_over_cap=True,
    ),
    "wall-admission": ShadowFaultPlan(
        "essential-wall-admission",
        condition_wall_over_cap=True,
    ),
    "crash-before-answer": ShadowFaultPlan("process-crash-before-answer"),
    "crash-after-answer": ShadowFaultPlan("process-crash-after-answer"),
    "nonzero-completed": ShadowFaultPlan("process-exit-nonzero-completed"),
    "raw-publication": ShadowFaultPlan("raw-publication-failure"),
}


@pytest.fixture(scope="module")
def failure_receipts() -> dict[str, dict[str, object]]:
    return {
        name: execute_shadow_plan(ROOT, V16_PROVIDER_CONTRACT, plan)
        for name, plan in FAILURE_PLANS.items()
    }


def _counts(receipt: dict[str, object]) -> dict[str, object]:
    counts = receipt["call_counts"]
    assert isinstance(counts, dict)
    return counts


def _essential(receipt: dict[str, object]) -> dict[str, object]:
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    failures = evidence["essential_failures"]
    assert isinstance(failures, dict) and len(failures) == 1
    value = next(iter(failures.values()))
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize("case", tuple(FAILURE_PLANS))
def test_every_post_entry_failure_is_sealed_exported_unscored_and_zero_retry(
    failure_receipts: dict[str, dict[str, object]],
    case: str,
) -> None:
    receipt = failure_receipts[case]
    essential = _essential(receipt)
    counts = _counts(receipt)
    assert receipt["earliest_stopping_phase"] == "condition-execution"
    assert counts["condition_reservations"] == 1
    assert counts["condition_entries"] == 1
    assert essential["file_count"] >= 4
    assert 0 < essential["total_bytes"] <= MAX_ESSENTIAL_FAILURE_BYTES
    assert len(essential["manifest_sha256"]) == 64
    assert len(essential["receipt_sha256"]) == 64
    assert len(essential["export_receipt_sha256"]) == 64
    assert len(essential["held_artifact_binding_sha256"]) == 64
    assert essential["unscored"] is True
    assert essential["retry_count"] == 0
    retained = receipt["evidence_retained"]
    assert isinstance(retained, dict)
    assert retained["raw"] == []
    assert retained["finalized"] == []
    assert retained["evaluator"] == []
    assert receipt["cleanup"] == {
        "state": "complete",
        "resumed": False,
        "provider_resources_zero": True,
        "security_restored": True,
        "privacy_clean": True,
    }
    assert receipt["scientific_interpretation_allowed"] is False


def test_known_and_unknown_provider_failures_preserve_exact_accounting_bounds(
    failure_receipts: dict[str, dict[str, object]],
) -> None:
    expected = {
        "known-provider": ("sent_provider_error_reconciled", 0),
        "known-transport": ("sent_transport_error_known", 0),
        "ambiguous-send": ("sent_outcome_unknown", 1),
        "response-accounting": ("sent_outcome_unknown", 1),
    }
    for case, (terminal, unknown) in expected.items():
        production_evidence = failure_receipts[case]["production_control_evidence"]
        assert isinstance(production_evidence, dict)
        accounting = production_evidence["accounting"]
        assert isinstance(accounting, dict)
        conditions = accounting["conditions"]
        assert isinstance(conditions, dict) and len(conditions) == 1
        condition = next(iter(conditions.values()))
        assert isinstance(condition, dict)
        terminal_counts = condition["terminal_counts"]
        assert isinstance(terminal_counts, dict)
        assert terminal_counts[terminal] == 1
        assert condition["unknown_outcomes"] == unknown
        assert accounting["zero_retries"] is True


def test_browser_admission_failure_does_not_claim_rejected_action_completed(
    failure_receipts: dict[str, dict[str, object]],
) -> None:
    receipt = failure_receipts["browser-admission"]
    essential = _essential(receipt)
    assert essential["failure_class"] == "budget-admission-stop"
    production_evidence = receipt["production_control_evidence"]
    assert isinstance(production_evidence, dict)
    accounting = production_evidence["accounting"]
    assert isinstance(accounting, dict)
    condition = next(iter(accounting["conditions"].values()))  # type: ignore[union-attr]
    assert condition["observed_lower_bound"]["condition"]["browser_actions"] == 30


def test_nonzero_exit_with_completed_answer_is_infrastructure_invalid(
    failure_receipts: dict[str, dict[str, object]],
) -> None:
    essential = _essential(failure_receipts["nonzero-completed"])
    assert essential["failure_class"] == "process-exit-nonzero"
    assert essential["process_exit_code"] == 23
    assert essential["completed"] is True
    assert essential["unscored"] is True


def test_process_crash_after_answer_never_reaches_finalizer_or_evaluator(
    failure_receipts: dict[str, dict[str, object]],
) -> None:
    essential = _essential(failure_receipts["crash-after-answer"])
    assert essential["failure_class"] == "process-crash"
    assert essential["completed"] is True
    counts = _counts(failure_receipts["crash-after-answer"])
    assert counts["condition_reservations"] == 1
    assert counts["condition_entries"] == 1


def test_essential_bundle_exact_cap_is_accepted() -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            "essential-exact-cap",
            fail_operation="condition.run",
            essential_target_bytes=MAX_ESSENTIAL_FAILURE_BYTES,
        ),
    )
    essential = _essential(receipt)
    assert essential["total_bytes"] == MAX_ESSENTIAL_FAILURE_BYTES
    assert essential["unscored"] is True


def test_essential_bundle_one_byte_over_cap_fails_closed() -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            "essential-over-cap",
            fail_operation="condition.run",
            essential_target_bytes=MAX_ESSENTIAL_FAILURE_BYTES + 1,
        ),
    )
    assert receipt["earliest_stopping_phase"] == "condition-execution"
    assert "could not be sealed and exported" in str(receipt["stop_reason"])
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}
    assert receipt["scientific_interpretation_allowed"] is False


@pytest.mark.parametrize("fault", ["symlink", "nonregular", "hardlink"])
def test_unsafe_essential_bundle_artifacts_fail_closed(fault: str) -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            f"essential-unsafe-{fault}",
            fail_operation="condition.run",
            essential_artifact_fault=fault,
        ),
    )
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}
    assert "could not be sealed and exported" in str(receipt["stop_reason"])


def test_essential_file_mutation_during_export_fails_closed() -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            "essential-mutation-during-export",
            fail_operation="condition.run",
            mutate_essential_during_export=True,
        ),
    )
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}
    assert "could not be sealed and exported" in str(receipt["stop_reason"])


def test_interrupted_failure_export_resumes_from_identical_sealed_source() -> None:
    plan = ShadowFaultPlan(
        "essential-export-resume",
        fail_operation="condition.run",
        failure_export_interruption_count=1,
    )
    first = execute_shadow_plan(ROOT, V16_PROVIDER_CONTRACT, plan)
    second = execute_shadow_plan(ROOT, V16_PROVIDER_CONTRACT, plan)
    first_essential = _essential(first)
    second_essential = _essential(second)
    assert first_essential["export_resumed"] is True
    assert second_essential["export_resumed"] is True
    assert first_essential["manifest_sha256"] == second_essential["manifest_sha256"]
    assert first_essential["receipt_sha256"] == second_essential["receipt_sha256"]


def test_breaking_retained_essential_seal_prevents_clean_evidence_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_seal(*_args: object, **_kwargs: object) -> None:
        raise pilot_error("retained essential seal deliberately unavailable")

    pilot_error = production.pilot.T09PilotError
    monkeypatch.setattr(production.pilot, "mark_essential_failure_sealed", broken_seal)
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan("essential-seal-coupling", fail_operation="condition.run"),
    )
    assert "could not be sealed and exported" in str(receipt["stop_reason"])
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}


def test_task_b_is_never_reserved_after_any_task_a_infrastructure_failure(
    failure_receipts: dict[str, dict[str, object]],
) -> None:
    for receipt in failure_receipts.values():
        counts = _counts(receipt)
        assert counts["condition_reservations"] == 1
        assert counts["condition_entries"] == 1
        consumption = receipt["scientific_attempt_consumption"]
        assert isinstance(consumption, dict)
        assert consumption["run_ids"] == [V16_PROVIDER_CONTRACT.run_ids[0]]
