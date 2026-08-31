from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from giclab.control import production
from giclab.control.adapters import (
    EffectAuthority,
    EffectAuthorityKind,
    FakeScenario,
    mint_shadow_effect_authority,
)
from giclab.control.category3 import (
    Category3Phase,
    Category3Request,
    execute_category3_transaction,
    repository_identity,
)
from giclab.control.composition import compose_control_plane
from giclab.control.production import (
    build_production_shadow_assembly,
    probe_production_adapter_assembly,
)
from giclab.control.proofs import ValidatedShadowRehearsal, validate_shadow_rehearsal
from giclab.control.registry_validation import validate_registry_completeness
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
    scenario: FakeScenario | None = None,
) -> dict[str, object]:
    selected = scenario or FakeScenario("happy-path")
    world = build_production_shadow_assembly(ROOT, V16_PROVIDER_CONTRACT, selected)
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


def test_public_caller_cannot_mint_live_authority_by_selecting_enum() -> None:
    with pytest.raises(TypeError, match="reviewed validators"):
        EffectAuthority(
            kind=EffectAuthorityKind.LIVE_AUTHORIZED,
            source="caller-assertion",
        )

    shadow = mint_shadow_effect_authority(source="test-shadow")
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
        FakeScenario("provider-entry-replacement", fail_operation="provider.enter"),
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
    def broken_cleanup(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("mutated empirical-prefix cleanup handoff")

    monkeypatch.setattr(production.pilot, "load_validated_pilot_state", broken_cleanup)
    receipt = _execute(rehearsal)
    assert receipt["earliest_stopping_phase"] == Category3Phase.CLEANUP.value
    cleanup = receipt["cleanup"]
    assert isinstance(cleanup, dict) and cleanup["state"] == "unresolved"
