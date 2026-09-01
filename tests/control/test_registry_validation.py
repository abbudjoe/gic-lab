from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.control.consumers import (
    CONTROL_CONSUMERS,
    ConsumerResolution,
    ContractConsumer,
    expected_consumer_handler_id,
    resolve_control_consumers,
)
from giclab.control.registry_validation import validate_registry_completeness
from giclab.harness.t09_pragmatic_provider import T09ProviderError, load_campaign_lifecycle
from giclab.harness.t09_provider_contracts import (
    PROVIDER_CONTRACTS,
    V16_PROVIDER_CONTRACT,
    LifecycleFamily,
    PackageEffectRegistration,
)
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]
_CURRENTLY_APPLICABLE_CONSUMERS = tuple(
    name
    for name in CONTROL_CONSUMERS
    if any(
        expected_consumer_handler_id(name, contract) is not None
        for contract in PROVIDER_CONTRACTS.values()
    )
)


def _first_applicable_contract(consumer_name: str):  # type: ignore[no-untyped-def]
    return next(
        contract
        for contract in reversed(tuple(PROVIDER_CONTRACTS.values()))
        if expected_consumer_handler_id(consumer_name, contract) is not None
    )


def test_every_registered_autonomous_contract_loads_campaign_lifecycle() -> None:
    for contract in PROVIDER_CONTRACTS.values():
        if contract.capabilities.lifecycle_family is LifecycleFamily.AUTONOMOUS_CAMPAIGN:
            lifecycle = load_campaign_lifecycle(ROOT, contract=contract)
            assert lifecycle.contract == contract


def test_every_registered_contract_produces_complete_real_consumer_matrix() -> None:
    receipt = validate_registry_completeness(ROOT)
    assert receipt["complete"] is True
    assert receipt["contract_count"] == len(PROVIDER_CONTRACTS)
    assert all(entry["complete"] is True for entry in receipt["contracts"])
    v16 = next(entry for entry in receipt["contracts"] if entry["version"] == "V16")
    consumers = v16["consumers"]
    assert isinstance(consumers, dict)
    assert consumers["production_adapter_assembly"]["handler_id"] == (  # type: ignore[index]
        "category3-production-wrapper:v1"
    )


def test_removing_v16_lifecycle_support_fails_registry_completeness() -> None:
    def mutant_loader(repository: Path, *, contract: object) -> object:
        if getattr(contract, "version", None) == "V16":
            raise T09ProviderError("mutant lifecycle omitted V16")
        return load_campaign_lifecycle(repository, contract=contract)  # type: ignore[arg-type]

    receipt = validate_registry_completeness(ROOT, lifecycle_loader=mutant_loader)
    assert receipt["complete"] is False
    v16 = next(entry for entry in receipt["contracts"] if entry["version"] == "V16")
    assert v16["consumers"]["campaign_lifecycle_loading"]["status"] == "failed"  # type: ignore[index]


@pytest.mark.parametrize("consumer_name", _CURRENTLY_APPLICABLE_CONSUMERS)
def test_disabling_each_applicable_real_consumer_fails_completeness(
    consumer_name: str,
) -> None:
    contract = _first_applicable_contract(consumer_name)
    receipt = validate_registry_completeness(
        ROOT,
        contracts={contract.version: contract},
        disabled_consumers=frozenset({consumer_name}),
    )
    assert receipt["complete"] is False
    entry = receipt["contracts"][0]
    assert entry["consumers"][consumer_name]["status"] == "failed"  # type: ignore[index]


@pytest.mark.parametrize(
    "consumer_name",
    tuple(
        name
        for name in CONTROL_CONSUMERS
        if expected_consumer_handler_id(name, V16_PROVIDER_CONTRACT) is not None
    ),
)
def test_each_applicable_consumer_rejecting_v16_fails_completeness(
    consumer_name: str,
) -> None:
    original = CONTROL_CONSUMERS[consumer_name]

    def reject_v16(repository: Path, contract: object) -> ConsumerResolution | None:
        if getattr(contract, "version", None) == "V16":
            raise ValueError("mutant rejected V16")
        return original.resolve(repository, contract)  # type: ignore[arg-type]

    consumers = dict(CONTROL_CONSUMERS)
    consumers[consumer_name] = ContractConsumer(consumer_name, reject_v16)  # type: ignore[arg-type]
    receipt = validate_registry_completeness(
        ROOT,
        contracts={"V16": V16_PROVIDER_CONTRACT},
        control_consumers=consumers,
    )
    assert receipt["complete"] is False
    assert receipt["contracts"][0]["consumers"][consumer_name]["status"] == "failed"  # type: ignore[index]


@pytest.mark.parametrize("consumer_name", _CURRENTLY_APPLICABLE_CONSUMERS)
def test_each_applicable_consumer_returning_wrong_handler_fails_completeness(
    consumer_name: str,
) -> None:
    contract = _first_applicable_contract(consumer_name)
    original = CONTROL_CONSUMERS[consumer_name]

    def wrong_handler(
        repository: Path,
        selected: object,
    ) -> ConsumerResolution | None:
        result = original.resolve(repository, selected)  # type: ignore[arg-type]
        assert result is not None
        return replace(result, handler_id="mutant:wrong-handler")

    consumers = dict(CONTROL_CONSUMERS)
    consumers[consumer_name] = ContractConsumer(consumer_name, wrong_handler)  # type: ignore[arg-type]
    receipt = validate_registry_completeness(
        ROOT,
        contracts={contract.version: contract},
        control_consumers=consumers,
    )
    assert receipt["complete"] is False
    assert receipt["contracts"][0]["consumers"][consumer_name]["status"] == "failed"  # type: ignore[index]


def test_future_autonomous_contract_declaration_resolves_all_real_consumers() -> None:
    future = replace(
        V16_PROVIDER_CONTRACT,
        version="V99",
        control_root_name="pilot-v99",
    )
    resolutions = resolve_control_consumers(ROOT, future)
    for name, resolution in resolutions.items():
        expected = expected_consumer_handler_id(name, future)
        if expected is None:
            assert resolution is None
        else:
            assert resolution is not None
            assert resolution.handler_id == expected


def test_declared_package_effect_consumer_is_exact_and_required() -> None:
    # This node proves registry completeness only. The package-loader suite covers
    # exact factory import/instantiation with a committed temporary package module.
    relative = "src/giclab/control/scenarios.py"
    encoded = (ROOT / relative).read_bytes()
    contract = replace(
        V16_PROVIDER_CONTRACT,
        effect_registration=PackageEffectRegistration(
            implementation_path=relative,
            implementation_bytes=len(encoded),
            implementation_sha256=hashlib.sha256(encoded).hexdigest(),
            factory_entry_point="build_deterministic_effects",
            authority_grant_schema_version="1.0.0",
            effect_protocol_version="1.0.0",
        ),
    )
    resolution = resolve_control_consumers(ROOT, contract)["package_effect_loader"]
    assert resolution is not None
    assert resolution.handler_id == "package-effects:exact-hash-bound-factory-v1"
    receipt = validate_registry_completeness(
        ROOT,
        contracts={contract.version: contract},
        disabled_consumers=frozenset({"package_effect_loader"}),
    )
    assert receipt["complete"] is False


def test_registry_receipt_is_deterministic_and_schema_valid() -> None:
    first = validate_registry_completeness(ROOT)
    second = validate_registry_completeness(ROOT)
    assert first == second
    schema = load_json(ROOT / "schemas/t09-control-registry-receipt.schema.json")
    Draft202012Validator(schema).validate(first)
