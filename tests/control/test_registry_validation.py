from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from giclab.control.registry_validation import validate_registry_completeness
from giclab.harness.t09_pragmatic_provider import T09ProviderError, load_campaign_lifecycle
from giclab.harness.t09_provider_contracts import (
    PROVIDER_CONTRACTS,
    LifecycleFamily,
    MetadataPolicy,
    ReplacementPolicy,
)
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]


def test_every_registered_autonomous_contract_loads_campaign_lifecycle() -> None:
    for contract in PROVIDER_CONTRACTS.values():
        if contract.capabilities.lifecycle_family is LifecycleFamily.AUTONOMOUS_CAMPAIGN:
            lifecycle = load_campaign_lifecycle(ROOT, contract=contract)
            assert lifecycle.contract == contract


def test_every_registered_contract_produces_a_complete_consumer_matrix() -> None:
    receipt = validate_registry_completeness(ROOT)
    assert receipt["complete"] is True
    assert receipt["contract_count"] == len(PROVIDER_CONTRACTS)
    assert all(entry["complete"] is True for entry in receipt["contracts"])


def test_removing_v16_lifecycle_support_fails_registry_completeness() -> None:
    def mutant_loader(repository: Path, *, contract: object) -> object:
        if getattr(contract, "version", None) == "V16":
            raise T09ProviderError("mutant lifecycle omitted V16")
        return load_campaign_lifecycle(repository, contract=contract)  # type: ignore[arg-type]

    receipt = validate_registry_completeness(ROOT, lifecycle_loader=mutant_loader)
    assert receipt["complete"] is False
    v16 = next(entry for entry in receipt["contracts"] if entry["version"] == "V16")
    assert v16["consumers"]["campaign_lifecycle_loading"]["status"] == "failed"


def test_declared_metadata_capability_without_consumer_fails() -> None:
    receipt = validate_registry_completeness(
        ROOT,
        disabled_consumers=frozenset({"metadata_policy_resolution"}),
    )
    assert receipt["complete"] is False
    affected = [
        entry
        for entry in receipt["contracts"]
        if PROVIDER_CONTRACTS[entry["version"]].capabilities.metadata_policy
        is MetadataPolicy.LOCAL_PRELAUNCH_RECEIPT
    ]
    assert affected
    assert all(
        entry["consumers"]["metadata_policy_resolution"]["status"] == "failed" for entry in affected
    )


def test_declared_replacement_capability_without_consumer_fails() -> None:
    receipt = validate_registry_completeness(
        ROOT,
        disabled_consumers=frozenset({"replacement_policy_resolution"}),
    )
    assert receipt["complete"] is False
    affected = [
        entry
        for entry in receipt["contracts"]
        if PROVIDER_CONTRACTS[entry["version"]].capabilities.replacement_policy
        is ReplacementPolicy.BOUNDED_PREFLIGHT
    ]
    assert affected
    assert all(
        entry["consumers"]["replacement_policy_resolution"]["status"] == "failed"
        for entry in affected
    )


def test_registry_receipt_is_deterministic_and_schema_valid() -> None:
    first = validate_registry_completeness(ROOT)
    second = validate_registry_completeness(ROOT)
    assert first == second
    schema = load_json(ROOT / "schemas/t09-control-registry-receipt.schema.json")
    Draft202012Validator(schema).validate(first)
