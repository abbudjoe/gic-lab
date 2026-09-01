from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from giclab.control import production
from giclab.control.category3 import (
    Category3Phase,
    Category3Request,
    execute_category3_transaction,
    repository_identity,
)
from giclab.control.composition import compose_control_plane
from giclab.control.effects import (
    EffectAuthority,
    EffectAuthorityKind,
)
from giclab.control.production import probe_production_adapter_assembly
from giclab.control.proofs import ValidatedShadowRehearsal, validate_shadow_rehearsal
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.shadow_effects import (
    DeterministicLowLevelEffects,
    ShadowFaultPlan,
    build_production_shadow_assembly,
)
from giclab.control.state_capsule import generate_state_capsule
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def rehearsal() -> ValidatedShadowRehearsal:
    lint = validate_active_version_dispatch(ROOT)
    registry = validate_registry_completeness(ROOT)
    composition = compose_control_plane(
        ROOT,
        contract=V16_PROVIDER_CONTRACT,
        registry_receipt=registry,
        version_lint_receipt=lint,
    )
    capsule = generate_state_capsule(
        ROOT,
        registry_complete=True,
        composition_valid=True,
        version_lint_valid=True,
        shadow_happy_path=False,
        failure_matrix_valid=False,
    )
    return validate_shadow_rehearsal(
        ROOT,
        V16_PROVIDER_CONTRACT,
        registry_receipt=registry,
        version_lint_receipt=lint,
        composition_receipt=composition,
        state_capsule=capsule,
    )


def _execute(
    rehearsal: ValidatedShadowRehearsal,
    scenario: ShadowFaultPlan | None = None,
) -> dict[str, object]:
    selected = scenario or ShadowFaultPlan("happy-path")
    world = build_production_shadow_assembly(
        ROOT,
        V16_PROVIDER_CONTRACT,
        selected,
        rehearsal=rehearsal,
    )
    commit, tree = repository_identity(ROOT)
    return execute_category3_transaction(
        Category3Request(
            repository=ROOT,
            contract=V16_PROVIDER_CONTRACT,
            scenario=selected.name,
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=rehearsal,
        ),
        adapters=world.adapters(),
    )


def _counts(receipt: dict[str, object]) -> dict[str, object]:
    counts = receipt["call_counts"]
    assert isinstance(counts, dict)
    return counts


def test_registered_active_contract_reaches_production_adapter_assembly() -> None:
    resolution = probe_production_adapter_assembly(ROOT, V16_PROVIDER_CONTRACT)
    assert resolution["implementation_flavor"] == "production-wrapper"
    assert resolution["controller_bypass"] is False
    assert resolution["controller_entrypoint"] == (
        "giclab.control.category3:execute_category3_transaction"
    )
    assert resolution["future_live_source_changes_required"] is False
    assert resolution["live_authority_factory_present"] is False
    assert "lifecycle_resolver" in resolution["resolved_consumers"]


def test_public_caller_cannot_mint_live_authority_by_selecting_enum(
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    with pytest.raises(TypeError, match="reviewed validators"):
        EffectAuthority(
            kind=EffectAuthorityKind.LIVE_AUTHORIZED,
            source="caller-assertion",
        )

    shadow = build_production_shadow_assembly(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan("happy-path"),
        rehearsal=rehearsal,
    ).authority
    assert shadow.kind is EffectAuthorityKind.SHADOW_ONLY
    assert shadow.is_valid_shadow() is True


def test_breaking_retained_launch_campaign_stops_at_launch(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    def broken_launch(*_args: object, **_kwargs: object) -> Path:
        raise RuntimeError("mutated retained launch")

    monkeypatch.setattr(production.provider, "launch_campaign", broken_launch)
    receipt = _execute(rehearsal)
    assert receipt["earliest_stopping_phase"] == Category3Phase.LAUNCH.value
    assert _counts(receipt)["condition_reservations"] == 0


def test_breaking_metadata_semantic_validation_stops_before_launch(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    def broken_metadata(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("mutated metadata semantic validator")

    monkeypatch.setattr(production.metadata, "validate_model_metadata_receipt", broken_metadata)
    receipt = _execute(rehearsal)
    assert receipt["earliest_stopping_phase"] == Category3Phase.METADATA_RECEIPT.value
    assert _counts(receipt)["launch_calls"] == 0


def test_breaking_replacement_normalization_stops_replacement_launch(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    def broken_normalization(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("mutated replacement normalizer")

    monkeypatch.setattr(
        production.provider,
        "_normalize_provider_entry_replacement_authority",
        broken_normalization,
    )
    receipt = _execute(
        rehearsal,
        ShadowFaultPlan("provider-entry-replacement", fail_operation="provider.enter"),
    )
    assert receipt["earliest_stopping_phase"] == Category3Phase.LAUNCH.value
    authority = receipt["authority_consumed"]
    assert isinstance(authority, dict) and authority["launch_count"] == 1


def test_breaking_provider_call_accounting_stops_condition(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    def broken_accounting(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("mutated provider-call reservation/reconciliation")

    monkeypatch.setattr(production.ProviderBudgetBoundary, "invoke", broken_accounting)
    receipt = _execute(rehearsal)
    assert receipt["earliest_stopping_phase"] == Category3Phase.CONDITION_EXECUTION.value
    assert _counts(receipt)["condition_reservations"] == 1


def test_breaking_raw_seal_stops_at_raw_export(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    def broken_raw(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("mutated raw seal")

    monkeypatch.setattr(production.pilot, "mark_raw_attempt_complete", broken_raw)
    receipt = _execute(rehearsal)
    assert receipt["earliest_stopping_phase"] == Category3Phase.RAW_EXPORT.value
    evidence = receipt["evidence_retained"]
    assert isinstance(evidence, dict) and evidence["raw"] == []


def test_breaking_finalizer_source_revalidation_stops_at_finalization(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    host = production._host_module(ROOT)
    retained: Callable[..., object] = host.validate_finalizer_source
    calls = 0

    def break_on_use(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("mutated downstream finalizer source")
        return retained(*args, **kwargs)

    monkeypatch.setattr(host, "validate_finalizer_source", break_on_use)
    receipt = _execute(rehearsal)
    assert receipt["earliest_stopping_phase"] == Category3Phase.FINALIZATION.value
    evidence = receipt["evidence_retained"]
    assert isinstance(evidence, dict)
    assert evidence["raw"] == [V16_PROVIDER_CONTRACT.run_ids[0]]


def test_breaking_empirical_prefix_cleanup_handoff_fails_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    retained: Callable[..., object] = production.pilot.load_validated_pilot_state
    calls = 0

    def broken_cleanup(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("mutated empirical-prefix cleanup handoff")
        return retained(*args, **kwargs)

    monkeypatch.setattr(production.pilot, "load_validated_pilot_state", broken_cleanup)
    receipt = _execute(rehearsal)
    assert receipt["earliest_stopping_phase"] == Category3Phase.CLEANUP.value
    cleanup = receipt["cleanup"]
    assert isinstance(cleanup, dict) and cleanup["state"] == "unresolved"


def test_post_export_raw_mutation_stops_before_effect_finalizer(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    retained = production.ProductionCategory3World.finalize
    mutated = False

    def mutate_then_finalize(
        world: production.ProductionCategory3World,
        run_id: str,
    ) -> str:
        nonlocal mutated
        if not mutated:
            outcome = world._condition_outcomes[run_id]
            answer = outcome.raw_root / "condition-answer.json"
            answer.write_bytes(answer.read_bytes() + b"\n")
            mutated = True
        return retained(world, run_id)

    monkeypatch.setattr(
        production.ProductionCategory3World,
        "finalize",
        mutate_then_finalize,
    )
    receipt = _execute(rehearsal, ShadowFaultPlan("post-export-raw-mutation"))
    assert receipt["earliest_stopping_phase"] == Category3Phase.FINALIZATION.value
    evidence = receipt["evidence_retained"]
    assert isinstance(evidence, dict)
    assert evidence["raw"] == [V16_PROVIDER_CONTRACT.run_ids[0]]
    assert evidence["finalized"] == []
    assert evidence["evaluator"] == []


def test_effect_produced_answer_changes_retained_evaluator_output(
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    baseline = _execute(rehearsal, ShadowFaultPlan("effect-answer-baseline"))
    changed = _execute(
        rehearsal,
        ShadowFaultPlan(
            "effect-answer-changed",
            answer_overrides=(
                "runtime-created deliberately incorrect Task A answer",
                "runtime-created deliberately incorrect Task B answer",
            ),
        ),
    )
    baseline_production = baseline["production_control_evidence"]
    changed_production = changed["production_control_evidence"]
    assert isinstance(baseline_production, dict) and isinstance(changed_production, dict)
    baseline_evaluations = baseline_production["evaluations"]
    changed_evaluations = changed_production["evaluations"]
    assert isinstance(baseline_evaluations, dict) and isinstance(changed_evaluations, dict)
    run_id = V16_PROVIDER_CONTRACT.run_ids[0]
    assert baseline_evaluations[run_id]["score"] != changed_evaluations[run_id]["score"]
    assert changed_evaluations[run_id]["answer_produced"] is True
    assert changed_evaluations[run_id]["classification"] == (
        "control-conformance-output-not-science"
    )


def test_effect_outcome_output_bytes_must_match_observed_event(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    retained = DeterministicLowLevelEffects.execute_condition

    def mismatched_output_bytes(
        effects: DeterministicLowLevelEffects,
        *args: object,
        **kwargs: object,
    ) -> object:
        outcome = retained(effects, *args, **kwargs)
        return replace(outcome, output_bytes=outcome.output_bytes + 1)

    monkeypatch.setattr(
        DeterministicLowLevelEffects,
        "execute_condition",
        mismatched_output_bytes,
    )
    receipt = _execute(rehearsal, ShadowFaultPlan("output-byte-event-mismatch"))
    assert receipt["earliest_stopping_phase"] == Category3Phase.CONDITION_EXECUTION.value
    assert receipt["scientific_interpretation_allowed"] is False


@pytest.mark.parametrize(
    ("method_name", "field_name", "phase"),
    [
        ("stage_package", "plan_id", Category3Phase.LOCAL_STAGING),
        ("preflight_host", "stage_receipt_sha256", Category3Phase.HOST_PREFLIGHT),
        (
            "qualify_host",
            "provider_entry_receipt_sha256",
            Category3Phase.QUALIFICATION,
        ),
        ("freeze_science", "manifest_sha256", Category3Phase.SCIENTIFIC_FREEZE),
    ],
)
def test_mutated_host_effect_receipt_stops_before_empirical_entry(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
    method_name: str,
    field_name: str,
    phase: Category3Phase,
) -> None:
    retained = cast(Callable[..., object], getattr(DeterministicLowLevelEffects, method_name))

    def drift_receipt(*args: object, **kwargs: object) -> object:
        receipt = retained(*args, **kwargs)
        return replace(cast(Any, receipt), **{field_name: "f" * 64})

    monkeypatch.setattr(DeterministicLowLevelEffects, method_name, drift_receipt)
    receipt = _execute(rehearsal, ShadowFaultPlan(f"mutated-{method_name}-receipt"))
    assert receipt["earliest_stopping_phase"] == phase.value
    assert _counts(receipt)["condition_reservations"] == 0
    assert receipt["scientific_interpretation_allowed"] is False


def test_mutated_completion_receipt_stops_condition_acceptance(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    retained = DeterministicLowLevelEffects.execute_condition

    def drift_completion_path(
        effects: DeterministicLowLevelEffects,
        *args: object,
        **kwargs: object,
    ) -> object:
        outcome = retained(effects, *args, **kwargs)
        return replace(outcome, completion_path=outcome.process_outcome_path)

    monkeypatch.setattr(
        DeterministicLowLevelEffects,
        "execute_condition",
        drift_completion_path,
    )
    receipt = _execute(rehearsal, ShadowFaultPlan("mutated-completion-receipt"))
    assert receipt["earliest_stopping_phase"] == Category3Phase.CONDITION_EXECUTION.value
    assert receipt["scientific_interpretation_allowed"] is False


def test_mutated_finalizer_consumption_receipt_stops_evaluation(
    monkeypatch: pytest.MonkeyPatch,
    rehearsal: ValidatedShadowRehearsal,
) -> None:
    retained = DeterministicLowLevelEffects.finalize_condition

    def drift_consumed_raw(
        effects: DeterministicLowLevelEffects,
        *args: object,
        **kwargs: object,
    ) -> object:
        outcome = retained(effects, *args, **kwargs)
        return replace(outcome, consumed_raw_manifest_sha256="e" * 64)

    monkeypatch.setattr(
        DeterministicLowLevelEffects,
        "finalize_condition",
        drift_consumed_raw,
    )
    receipt = _execute(rehearsal, ShadowFaultPlan("mutated-finalizer-receipt"))
    assert receipt["earliest_stopping_phase"] == Category3Phase.FINALIZATION.value
    evidence = receipt["evidence_retained"]
    assert isinstance(evidence, dict)
    assert evidence["evaluator"] == []
    assert receipt["scientific_interpretation_allowed"] is False


@pytest.mark.parametrize(
    ("name", "fault_field"),
    [
        ("browser-action-admission-overage", "browser_actions_over_cap"),
        ("output-byte-admission-overage", "output_bytes_over_cap"),
        ("condition-wall-admission-overage", "condition_wall_over_cap"),
    ],
)
def test_effect_events_stop_at_each_nonmodel_condition_cap(
    rehearsal: ValidatedShadowRehearsal,
    name: str,
    fault_field: str,
) -> None:
    plan = ShadowFaultPlan(name, **{fault_field: True})
    receipt = _execute(rehearsal, plan)
    assert receipt["earliest_stopping_phase"] == Category3Phase.CONDITION_EXECUTION.value
    assert receipt["scientific_interpretation_allowed"] is False
    production = receipt["production_control_evidence"]
    assert isinstance(production, dict)
    accounting = production["accounting"]
    assert isinstance(accounting, dict)
    conditions = accounting["conditions"]
    assert isinstance(conditions, dict) and len(conditions) == 1
