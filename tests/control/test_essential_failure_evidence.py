from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from _category3_test_support import execute_shadow_plan

from giclab.control import production
from giclab.control.effects import (
    MAX_ESSENTIAL_FAILURE_BYTES,
    MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES,
    HeldArtifact,
    hold_sealed_artifact,
    hold_transaction_root,
)
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


def _canonical_sha256(value: object) -> str:
    encoded = (
        json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _execute_with_post_enumeration_mutation(
    monkeypatch: pytest.MonkeyPatch,
    *,
    plan: ShadowFaultPlan,
    mutation: Callable[[Path], None],
) -> dict[str, object]:
    """Mutate once after candidate-name enumeration and before held admission."""

    original = production.ProductionCategory3World._enumerate_essential_envelope
    mutated = False

    def enumerate_then_mutate(
        world: production.ProductionCategory3World,
        root: Path,
    ) -> tuple[Path, ...]:
        nonlocal mutated
        paths = original(world, root)
        if not mutated and any(path.name == "export-acknowledgement.json" for path in paths):
            mutation(root)
            mutated = True
        return paths

    monkeypatch.setattr(
        production.ProductionCategory3World,
        "_enumerate_essential_envelope",
        enumerate_then_mutate,
    )
    receipt = execute_shadow_plan(ROOT, V16_PROVIDER_CONTRACT, plan)
    assert mutated is True
    return receipt


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
    assert essential["file_count"] >= 7
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


@pytest.mark.parametrize(
    "mutation_name",
    [
        "grow-export-acknowledgement",
        "grow-payload-json",
        "replace-export-acknowledgement-with-larger-inode",
    ],
)
def test_complete_envelope_mutation_after_enumeration_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    mutation_name: str,
) -> None:
    def mutation(root: Path) -> None:
        target = (
            root / "payload/completion-state.json"
            if mutation_name == "grow-payload-json"
            else root / "export-acknowledgement.json"
        )
        encoded = target.read_bytes()
        if mutation_name == "replace-export-acknowledgement-with-larger-inode":
            displaced = target.with_name(target.name + ".enumerated-inode")
            target.rename(displaced)
            target.write_bytes(encoded + b" ")
            target.chmod(0o400)
            displaced.unlink()
        else:
            target.chmod(0o600)
            target.write_bytes(encoded + b" ")
            target.chmod(0o400)

    receipt = _execute_with_post_enumeration_mutation(
        monkeypatch,
        plan=ShadowFaultPlan(
            f"essential-post-enumeration-{mutation_name}",
            fail_operation="condition.run",
        ),
        mutation=mutation,
    )
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}
    retained = receipt["evidence_retained"]
    assert isinstance(retained, dict)
    assert retained["essential_failures"] == []
    assert "could not be sealed and exported" in str(receipt["stop_reason"])
    assert receipt["cleanup"]["state"] == "complete"  # type: ignore[index]
    assert receipt["scientific_interpretation_allowed"] is False


def test_non_json_member_growth_after_enumeration_uses_held_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mutation(root: Path) -> None:
        padding = root / "envelope-padding.bin"
        padding.chmod(0o600)
        os.truncate(padding, padding.stat(follow_symlinks=False).st_size + 1)
        padding.chmod(0o400)

    receipt = _execute_with_post_enumeration_mutation(
        monkeypatch,
        plan=ShadowFaultPlan(
            "essential-post-enumeration-non-json-growth",
            fail_operation="condition.run",
            essential_target_bytes=MAX_ESSENTIAL_FAILURE_BYTES,
        ),
        mutation=mutation,
    )
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}
    retained = receipt["evidence_retained"]
    assert isinstance(retained, dict)
    assert retained["essential_failures"] == []
    assert "could not be sealed and exported" in str(receipt["stop_reason"])
    assert receipt["cleanup"]["state"] == "complete"  # type: ignore[index]
    assert receipt["scientific_interpretation_allowed"] is False


def test_held_json_member_cap_is_applied_before_read(tmp_path: Path) -> None:
    root = tmp_path / "held-json-cap"
    root.mkdir(mode=0o700)
    member = root / "member.json"
    exact = b'"' + b"x" * (MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES - 3) + b'"\n'
    assert len(exact) == MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES
    member.write_bytes(exact)
    member.chmod(0o400)
    held_root = hold_transaction_root(root)
    artifact: HeldArtifact | None = None
    try:
        artifact = hold_sealed_artifact(
            held_root,
            member,
            max_bytes=MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES,
        )
        assert artifact.bytes == MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES
        artifact.close()
        artifact = None
        member.chmod(0o600)
        member.write_bytes(exact + b" ")
        member.chmod(0o400)
        with pytest.raises(ValueError, match="pre-read byte cap"):
            hold_sealed_artifact(
                held_root,
                member,
                max_bytes=MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES,
            )
    finally:
        if artifact is not None:
            artifact.close()
        held_root.close()


def test_complete_envelope_totals_cross_bind_every_retained_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    original_hold = production.ProductionCategory3World._hold_artifact_set
    original_evidence = production.ProductionCategory3World.control_evidence

    def capture_complete_held(
        world: production.ProductionCategory3World,
        paths: tuple[Path, ...],
        **limits: int | None,
    ) -> tuple[HeldArtifact, ...]:
        held = original_hold(world, paths, **limits)
        if any(path.name == "export-acknowledgement.json" for path in paths):
            observed["file_count"] = len(held)
            observed["total_bytes"] = sum(artifact.bytes for artifact in held)
            acknowledgement = next(
                artifact for artifact in held if artifact.path.name == "export-acknowledgement.json"
            )
            observed["acknowledgement"] = json.loads(acknowledgement.read_bytes())
        return held

    def capture_retained_outcome(
        world: production.ProductionCategory3World,
    ) -> dict[str, object]:
        if world._condition_failures:
            outcome = next(iter(world._condition_failures.values()))
            observed["outcome_file_count"] = outcome.essential_file_count
            observed["outcome_total_bytes"] = outcome.essential_total_bytes
        return original_evidence(world)

    monkeypatch.setattr(
        production.ProductionCategory3World,
        "_hold_artifact_set",
        capture_complete_held,
    )
    monkeypatch.setattr(
        production.ProductionCategory3World,
        "control_evidence",
        capture_retained_outcome,
    )
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan("essential-held-total-cross-binding", fail_operation="condition.run"),
    )
    essential = _essential(receipt)
    retained = receipt["evidence_retained"]
    assert isinstance(retained, dict)
    records = retained["essential_failures"]
    assert isinstance(records, list) and len(records) == 1
    record = records[0]
    assert isinstance(record, dict)
    count = observed["file_count"]
    total = observed["total_bytes"]
    acknowledgement = observed["acknowledgement"]
    assert isinstance(count, int) and isinstance(total, int) and isinstance(acknowledgement, dict)
    assert essential["file_count"] == count
    assert essential["total_bytes"] == total
    assert record["essential_file_count"] == count
    assert record["essential_total_bytes"] == total
    assert acknowledgement["essential_file_count"] == count
    assert acknowledgement["essential_total_bytes"] == total
    assert observed["outcome_file_count"] == count
    assert observed["outcome_total_bytes"] == total
    production_evidence = receipt["production_control_evidence"]
    assert isinstance(production_evidence, dict)
    accounting = production_evidence["accounting"]
    assert isinstance(accounting, dict)
    conditions = accounting["conditions"]
    assert isinstance(conditions, dict)
    run_id = V16_PROVIDER_CONTRACT.run_ids[0]
    assert record["evidence_binding_sha256"] == _canonical_sha256(
        {
            "manifest_sha256": essential["manifest_sha256"],
            "receipt_sha256": essential["receipt_sha256"],
            "export_receipt_sha256": essential["export_receipt_sha256"],
            "essential_file_count": count,
            "essential_total_bytes": total,
            "held_artifact_binding_sha256": essential["held_artifact_binding_sha256"],
            "accounting": conditions[run_id],
        }
    )


@pytest.mark.parametrize(
    "fault",
    [
        "oversized-manifest",
        "oversized-completion-receipt",
        "oversized-export-acknowledgement",
    ],
)
def test_every_essential_envelope_member_has_a_finite_size_cap(fault: str) -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            f"essential-member-cap-{fault}",
            fail_operation="condition.run",
            essential_envelope_fault=fault,
        ),
    )
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}
    assert "could not be sealed and exported" in str(receipt["stop_reason"])


@pytest.mark.parametrize(
    "fault",
    [
        "secret-manifest-field",
        "header-completion-field",
        "private-absolute-path",
        "duplicate-json-key",
        "noncanonical-json",
        "undeclared-field",
        "sensitive-export-acknowledgement",
    ],
)
def test_essential_envelope_rejects_noncanonical_extensions_and_private_fields(
    fault: str,
) -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            f"essential-schema-privacy-{fault}",
            fail_operation="condition.run",
            essential_envelope_fault=fault,
        ),
    )
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}
    assert "could not be sealed and exported" in str(receipt["stop_reason"])
    if fault in {
        "secret-manifest-field",
        "header-completion-field",
        "private-absolute-path",
        "sensitive-export-acknowledgement",
    }:
        assert receipt["cleanup"]["privacy_clean"] is False  # type: ignore[index]


@pytest.mark.parametrize(
    "fault",
    ["manifest-symlink", "receipt-symlink", "manifest-hardlink", "receipt-hardlink"],
)
def test_manifest_and_completion_receipt_require_single_link_regular_identities(
    fault: str,
) -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            f"essential-envelope-identity-{fault}",
            fail_operation="condition.run",
            essential_envelope_fault=fault,
        ),
    )
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}
    assert "could not be sealed and exported" in str(receipt["stop_reason"])


@pytest.mark.parametrize(
    "fault",
    ["mutated-export-acknowledgement", "same-size-manifest-swap-during-export"],
)
def test_export_acknowledgement_or_sealed_member_mutation_fails(fault: str) -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(
            f"essential-envelope-mutation-{fault}",
            fail_operation="condition.run",
            essential_envelope_fault=fault,
        ),
    )
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["essential_failures"] == {}
    assert "could not be sealed and exported" in str(receipt["stop_reason"])


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
