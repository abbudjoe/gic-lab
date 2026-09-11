from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.control.adapters import ImplementationFlavor
from giclab.control.composition import compose_control_plane
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.scenarios import ALL_REQUIRED_SCENARIOS
from giclab.control.shadow import run_required_shadow_matrix, run_shadow_scenario
from giclab.control.state_capsule import generate_state_capsule
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def shadow_inputs() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
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
    return lint, registry, composition, capsule


@pytest.fixture(scope="module")
def shadow_matrix(
    shadow_inputs: tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ],
) -> dict[str, dict[str, object]]:
    lint, registry, composition, capsule = shadow_inputs
    return run_required_shadow_matrix(
        ROOT,
        contract=V16_PROVIDER_CONTRACT,
        state_capsule=capsule,
        registry_receipt=registry,
        version_lint_receipt=lint,
        composition_receipt=composition,
    )


def test_every_required_production_shadow_scenario_is_schema_valid(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    assert tuple(shadow_matrix) == ALL_REQUIRED_SCENARIOS
    validator = Draft202012Validator(
        load_json(ROOT / "schemas/t09-category3-shadow-receipt.schema.json")
    )
    for receipt in shadow_matrix.values():
        validator.validate(receipt)
        assert receipt["scenario_valid"] is True
        assert receipt["implementation_flavor"] == ImplementationFlavor.PRODUCTION_WRAPPER.value
        assert receipt["effect_authority"] == "shadow-only"


def test_production_wrapper_happy_path_uses_retained_primitives_and_all_conditions(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["happy-path"]
    assert receipt["condition_identities_consumed"] == list(V16_PROVIDER_CONTRACT.run_ids)
    evidence = receipt["evidence_retained"]
    assert isinstance(evidence, dict)
    assert evidence["raw"] == list(V16_PROVIDER_CONTRACT.run_ids)
    assert evidence["finalized"] == list(V16_PROVIDER_CONTRACT.run_ids)
    assert evidence["evaluator"] == list(V16_PROVIDER_CONTRACT.run_ids)
    production = receipt["production_control_evidence"]
    assert isinstance(production, dict)
    primitives = set(production["production_primitives"])
    assert {
        "load_openai_dotenv_assignment",
        "create_model_metadata_receipt",
        "validate_model_metadata_receipt:durable-offline",
        "validate_model_metadata_receipt_offline",
        "validate_campaign_launch_projection",
        "launch_campaign",
        "validate_entry_receipt_source_bound",
        "initialize_pilot_state",
        "reserve_condition_start",
        "mark_empirical_entry",
        "ProviderBudgetBoundary.invoke",
        "ProviderBudgetBoundary.record_browser_action",
        "mark_raw_attempt_complete",
        "validate_finalizer_source",
        "mark_attempt_completed",
        "evaluate_retained_session",
        "record_first_pair_checkpoint",
        "immutable_cleanup_export_handoff",
        "privacy_violations:held-descriptor",
    }.issubset(primitives)


def test_local_assembly_and_host_transfer_are_ordered_around_provider_entry(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["happy-path"]
    ledger = receipt["adapter_call_ledger"]
    assert isinstance(ledger, list)
    operations = [entry["operation"] for entry in ledger if isinstance(entry, dict)]
    assembly = operations.index("host.assemble_local")
    secret_read = operations.index("secret.read")
    launch = operations.index("provider.launch")
    entry = operations.index("provider.enter")
    transfer = operations.index("host.transfer")
    preflight = operations.index("host.preflight")
    condition = operations.index("condition.reserve")
    assert assembly < secret_read < launch < entry < transfer < preflight < condition
    assert operations.count("host.assemble_local") == 1
    assert operations.count("host.transfer") == 1


def test_lifecycle_omission_stops_before_every_external_boundary(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["lifecycle-unsupported"]
    counts = receipt["call_counts"]
    assert isinstance(counts, dict)
    assert receipt["earliest_stopping_phase"] == "offline-composition"
    assert counts["secret_reads"] == 0
    assert counts["metadata_requests"] == 0
    assert counts["provider_gets"] == 0
    assert counts["provider_posts"] == 0
    assert counts["condition_reservations"] == 0


def test_happy_path_accounting_has_nonzero_fake_usage_and_zero_real_projection(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["happy-path"]
    counts = receipt["call_counts"]
    assert isinstance(counts, dict)
    assert counts["model_call_attempts"] == 16
    assert counts["browser_actions"] == 8
    assert counts["unknown_model_outcomes"] == 0
    production = receipt["production_control_evidence"]
    assert isinstance(production, dict)
    accounting = production["accounting"]
    assert isinstance(accounting, dict)
    assert accounting["aggregate_observed_cost_usd"] > 0
    assert accounting["aggregate_charged_upper_cost_usd"] > 0
    assert accounting["projected_real_cost_usd"] == 0.0
    assert accounting["fake_usage"] is True
    assert accounting["zero_retries"] is True
    assert receipt["projected_cost_usd"] == "0.00"
    assert receipt["scientific_interpretation_allowed"] is False


def test_happy_path_is_byte_deterministic(
    shadow_inputs: tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ],
) -> None:
    _lint, _registry, _composition, capsule = shadow_inputs
    first = run_shadow_scenario(
        ROOT,
        contract=V16_PROVIDER_CONTRACT,
        scenario="happy-path",
        state_capsule=capsule,
        fixed_tick=44,
    )
    second = run_shadow_scenario(
        ROOT,
        contract=V16_PROVIDER_CONTRACT,
        scenario="happy-path",
        state_capsule=capsule,
        fixed_tick=44,
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.parametrize(
    ("scenario", "phase", "consumed"),
    [
        ("condition-failure", "condition-execution", 1),
        pytest.param(
            "raw-export-failure",
            "condition-execution",
            1,
            id="raw-export-failure-raw-export-1",
        ),
        ("finalizer-failure", "finalization", 1),
    ],
)
def test_empirical_failures_preserve_exact_consumed_prefix(
    shadow_matrix: dict[str, dict[str, object]],
    scenario: str,
    phase: str,
    consumed: int,
) -> None:
    receipt = shadow_matrix[scenario]
    attempt_state = receipt["scientific_attempt_consumption"]
    assert isinstance(attempt_state, dict)
    assert receipt["earliest_stopping_phase"] == phase
    assert attempt_state["count"] == consumed
    assert attempt_state["run_ids"] == list(V16_PROVIDER_CONTRACT.run_ids[:consumed])


@pytest.mark.parametrize(
    "scenario",
    ["provider-entry-replacement", "host-preflight-replacement"],
)
def test_preflight_failures_use_retained_bounded_replacement_history(
    shadow_matrix: dict[str, dict[str, object]],
    scenario: str,
) -> None:
    receipt = shadow_matrix[scenario]
    authority = receipt["authority_consumed"]
    production = receipt["production_control_evidence"]
    assert isinstance(authority, dict) and isinstance(production, dict)
    assert authority["launch_count"] == 2
    assert authority["replacement_count"] == 1
    replacement = production["replacement_history"]
    assert isinstance(replacement, dict)
    assert replacement["closed_launch_slots"] == [1, 2]
    assert replacement["normalization_handler"] == (
        "_normalize_provider_entry_replacement_authority"
    )


def test_cleanup_resume_reuses_byte_identical_handoff(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["cleanup-interrupted-resumed"]
    cleanup = receipt["cleanup"]
    production = receipt["production_control_evidence"]
    assert isinstance(cleanup, dict) and isinstance(production, dict)
    assert cleanup["resumed"] is True
    assert cleanup["state"] == "complete"
    assert production["cleanup_resume_byte_identical"] is True
    assert isinstance(production["cleanup_handoff_sha256"], str)


def test_privacy_termination_and_ambiguous_launch_fail_closed(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    privacy = shadow_matrix["structural-privacy-finding"]
    outage = shadow_matrix["provider-termination-unavailable"]
    ambiguous = shadow_matrix["ambiguous-provider-call-outcome"]
    assert privacy["terminal_state"] == "category3-shadow-stopped-privacy-blocked"
    assert privacy["cleanup"]["privacy_clean"] is False  # type: ignore[index]
    assert outage["cleanup"]["provider_resources_zero"] is False  # type: ignore[index]
    assert outage["call_counts"]["termination_calls"] == 2  # type: ignore[index]
    assert ambiguous["cleanup"]["provider_resources_zero"] is None  # type: ignore[index]
    assert ambiguous["authority_consumed"]["provider_launch"] == (  # type: ignore[index]
        "ambiguous-consumed"
    )


@pytest.mark.parametrize(
    ("scenario", "terminal", "unknown", "attempts"),
    [
        ("known-provider-exception", "sent_provider_error_reconciled", 0, 1),
        ("response-accounting-incomplete", "sent_outcome_unknown", 1, 1),
        ("ambiguous-task-model-send", "sent_outcome_unknown", 1, 1),
        ("cost-token-admission-stop", None, 0, 0),
    ],
)
def test_model_call_failure_accounting_is_typed_and_zero_retry(
    shadow_matrix: dict[str, dict[str, object]],
    scenario: str,
    terminal: str | None,
    unknown: int,
    attempts: int,
) -> None:
    receipt = shadow_matrix[scenario]
    production = receipt["production_control_evidence"]
    assert isinstance(production, dict)
    accounting = production["accounting"]
    assert isinstance(accounting, dict)
    conditions = accounting["conditions"]
    assert isinstance(conditions, dict) and len(conditions) == 1
    document = next(iter(conditions.values()))
    assert isinstance(document, dict)
    assert document["unknown_outcomes"] == unknown
    assert receipt["call_counts"]["model_call_attempts"] == attempts  # type: ignore[index]
    if terminal is not None:
        assert document["terminal_counts"][terminal] == 1  # type: ignore[index]
    assert accounting["zero_retries"] is True


def test_every_scenario_has_zero_undeclared_calls_and_false_science(
    shadow_matrix: Mapping[str, Mapping[str, object]],
) -> None:
    assert all(receipt["zero_undeclared_calls"] is True for receipt in shadow_matrix.values())
    assert all(receipt["undeclared_adapter_calls"] == [] for receipt in shadow_matrix.values())
    assert all(receipt["shadow_only"] is True for receipt in shadow_matrix.values())
    assert all(
        receipt["scientific_interpretation_allowed"] is False for receipt in shadow_matrix.values()
    )
