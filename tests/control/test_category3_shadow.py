from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.control.adapters import DeterministicFakeWorld, FakeScenario
from giclab.control.category3 import (
    Category3Phase,
    Category3Request,
    ShadowPrerequisitePolicy,
    execute_category3_transaction,
    prepare_category3,
    repository_identity,
)
from giclab.control.shadow import (
    ALL_REQUIRED_SCENARIOS,
    run_required_shadow_matrix,
    run_shadow_scenario,
)
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def shadow_matrix() -> dict[str, dict[str, object]]:
    return run_required_shadow_matrix(
        ROOT,
        contract=V16_PROVIDER_CONTRACT,
        state_capsule_sha256="a" * 64,
    )


def _request(
    *,
    state_capsule_valid: bool = True,
    shadow_policy: ShadowPrerequisitePolicy = ShadowPrerequisitePolicy.SELF_REHEARSAL,
    receipts: tuple[str, ...] = (),
    paths_valid: bool = True,
) -> Category3Request:
    commit, tree = repository_identity(ROOT)
    return Category3Request(
        repository=ROOT,
        contract=V16_PROVIDER_CONTRACT,
        scenario="ordering-fixture",
        expected_repository_commit=commit,
        expected_repository_tree=tree,
        state_capsule_sha256="b" * 64,
        state_capsule_valid=state_capsule_valid,
        shadow_prerequisite_policy=shadow_policy,
        required_shadow_receipt_sha256s=receipts,
        deterministic_paths_valid=paths_valid,
    )


def test_every_required_shadow_scenario_is_present_and_schema_valid(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    assert tuple(shadow_matrix) == ALL_REQUIRED_SCENARIOS
    schema = load_json(ROOT / "schemas/t09-category3-shadow-receipt.schema.json")
    validator = Draft202012Validator(schema)
    for receipt in shadow_matrix.values():
        validator.validate(receipt)
        assert receipt["scenario_valid"] is True


def test_happy_path_traverses_exact_condition_order_and_checkpoint(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["happy-path"]
    assert receipt["condition_identities_consumed"] == list(V16_PROVIDER_CONTRACT.run_ids)
    transitions = receipt["ordered_state_transitions"]
    assert isinstance(transitions, list)
    pair_index = next(
        item["index"]
        for item in transitions
        if item["phase"] == Category3Phase.PAIR_CHECKPOINT.value
    )
    entries = [
        item for item in transitions if item["phase"] == Category3Phase.EMPIRICAL_ENTRY.value
    ]
    assert entries[1]["index"] < pair_index < entries[2]["index"]


def test_happy_path_finalizes_evaluates_and_cleans_every_attempt(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["happy-path"]
    evidence = receipt["evidence_retained"]
    cleanup = receipt["cleanup"]
    assert isinstance(evidence, dict) and isinstance(cleanup, dict)
    assert evidence["raw"] == list(V16_PROVIDER_CONTRACT.run_ids)
    assert evidence["finalized"] == list(V16_PROVIDER_CONTRACT.run_ids)
    assert evidence["evaluator"] == list(V16_PROVIDER_CONTRACT.run_ids)
    assert evidence["classification"] == "shadow-control-plane-output"
    assert cleanup == {
        "state": "complete",
        "resumed": False,
        "provider_resources_zero": True,
        "security_restored": True,
        "privacy_clean": True,
    }
    assert receipt["scientific_interpretation_allowed"] is False


def test_happy_path_is_byte_deterministic() -> None:
    first = run_shadow_scenario(
        ROOT,
        contract=V16_PROVIDER_CONTRACT,
        scenario="happy-path",
        state_capsule_sha256="c" * 64,
        fixed_tick=44,
    )
    second = run_shadow_scenario(
        ROOT,
        contract=V16_PROVIDER_CONTRACT,
        scenario="happy-path",
        state_capsule_sha256="c" * 64,
        fixed_tick=44,
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_lifecycle_omission_stops_before_every_external_boundary(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["lifecycle-unsupported"]
    assert receipt["earliest_stopping_phase"] == Category3Phase.OFFLINE_COMPOSITION.value
    assert receipt["call_counts"] == {
        "secret_reads": 0,
        "metadata_requests": 0,
        "provider_gets": 0,
        "provider_posts": 0,
        "launch_calls": 0,
        "termination_calls": 0,
        "condition_reservations": 0,
        "condition_entries": 0,
    }


@pytest.mark.parametrize(
    ("scenario", "phase", "consumed"),
    [
        ("condition-failure", Category3Phase.CONDITION_EXECUTION.value, 1),
        ("raw-export-failure", Category3Phase.RAW_EXPORT.value, 1),
        ("finalizer-failure", Category3Phase.FINALIZATION.value, 1),
    ],
)
def test_attempt_failures_preserve_exact_consumed_prefix(
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
def test_preflight_failures_use_exactly_one_bounded_replacement(
    shadow_matrix: dict[str, dict[str, object]],
    scenario: str,
) -> None:
    authority = shadow_matrix[scenario]["authority_consumed"]
    assert isinstance(authority, dict)
    assert authority["launch_count"] == 2
    assert authority["replacement_count"] == 1
    assert shadow_matrix[scenario]["terminal_state"] == "category3-shadow-complete-clean"


def test_cleanup_interruption_resumes_idempotently(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    cleanup = shadow_matrix["cleanup-interrupted-resumed"]["cleanup"]
    assert isinstance(cleanup, dict)
    assert cleanup["resumed"] is True
    assert cleanup["state"] == "complete"
    ledger = shadow_matrix["cleanup-interrupted-resumed"]["adapter_call_ledger"]
    assert isinstance(ledger, list)
    assert [item["outcome"] for item in ledger if item["operation"] == "host.cleanup"] == [
        "interrupted-resumable",
        "passed",
    ]


def test_termination_outage_and_ambiguous_launch_never_claim_zero(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    outage = shadow_matrix["provider-termination-unavailable"]
    ambiguous = shadow_matrix["ambiguous-provider-call-outcome"]
    assert outage["cleanup"]["provider_resources_zero"] is False  # type: ignore[index]
    assert outage["call_counts"]["termination_calls"] == 2  # type: ignore[index]
    assert ambiguous["cleanup"]["provider_resources_zero"] is None  # type: ignore[index]
    assert ambiguous["authority_consumed"]["provider_launch"] == (  # type: ignore[index]
        "ambiguous-consumed"
    )


def test_privacy_finding_blocks_publication_but_still_closes_provider(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["structural-privacy-finding"]
    assert receipt["terminal_state"] == "category3-shadow-stopped-privacy-blocked"
    assert receipt["cleanup"]["provider_resources_zero"] is True  # type: ignore[index]
    assert receipt["cleanup"]["privacy_clean"] is False  # type: ignore[index]


def test_invalid_capsule_and_paths_stop_before_secret_metadata_or_provider() -> None:
    for request in (_request(state_capsule_valid=False), _request(paths_valid=False)):
        world = DeterministicFakeWorld(FakeScenario("deterministic-gate-failure"))
        receipt = execute_category3_transaction(request, adapters=world.adapters())
        counts = receipt["call_counts"]
        assert isinstance(counts, dict)
        assert counts["secret_reads"] == 0
        assert counts["metadata_requests"] == 0
        assert counts["provider_gets"] == 0
        assert counts["provider_posts"] == 0


def test_validated_shadow_policy_requires_receipt_hashes_before_staging() -> None:
    world = DeterministicFakeWorld(FakeScenario("validated-shadow-policy"))
    outcome = prepare_category3(
        _request(shadow_policy=ShadowPrerequisitePolicy.VALIDATED_RECEIPTS),
        adapters=world.adapters(),
    )
    assert outcome.prepared is None
    assert outcome.stopping_phase == Category3Phase.SHADOW_RECEIPTS.value
    assert world.calls == ()


def test_prepared_token_exists_before_secret_or_metadata_calls() -> None:
    world = DeterministicFakeWorld(FakeScenario("prepared-token"))
    outcome = prepare_category3(_request(), adapters=world.adapters())
    assert outcome.prepared is not None
    assert outcome.prepared.shadow_effects_permitted is True
    assert outcome.prepared.live_effects_permitted is False
    assert [call.operation for call in world.calls] == ["host.stage"]


def test_metadata_freshness_precedes_and_blocks_launch(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    receipt = shadow_matrix["metadata-expired"]
    assert receipt["earliest_stopping_phase"] == Category3Phase.FINAL_METADATA_FRESHNESS.value
    assert receipt["call_counts"]["launch_calls"] == 0  # type: ignore[index]


def test_every_scenario_has_zero_undeclared_calls(
    shadow_matrix: dict[str, dict[str, object]],
) -> None:
    assert all(receipt["zero_undeclared_calls"] is True for receipt in shadow_matrix.values())
    assert all(receipt["undeclared_adapter_calls"] == [] for receipt in shadow_matrix.values())
