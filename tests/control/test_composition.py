from __future__ import annotations

import copy
import inspect
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.control import composition
from giclab.control.composition import CompositionError, compose_control_plane
from giclab.control.registry_validation import (
    resolve_registered_command_package,
    validate_registry_completeness,
)
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness.t09_pragmatic_provider import T09ProviderError, load_campaign_lifecycle
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def deterministic_inputs() -> tuple[dict[str, object], dict[str, object]]:
    return validate_registry_completeness(ROOT), validate_active_version_dispatch(ROOT)


def _compose(inputs: tuple[dict[str, object], dict[str, object]]) -> dict[str, object]:
    registry, lint = inputs
    return compose_control_plane(
        ROOT,
        contract=V16_PROVIDER_CONTRACT,
        registry_receipt=registry,
        version_lint_receipt=lint,
    )


def test_exact_v16_static_composition_succeeds(
    deterministic_inputs: tuple[dict[str, object], dict[str, object]],
) -> None:
    receipt = _compose(deterministic_inputs)
    assert receipt["provider_contract_version"] == "V16"
    assert receipt["static_composition_valid"] is True
    assert receipt["ready_for_shadow"] is True
    assert receipt["ready_for_authenticated_preflight"] is False
    assert len(receipt["control_binding_schema_sha256"]) == 64
    assert receipt["pair_diff_sha256s"] and len(receipt["pair_diff_sha256s"]) == 2
    assert "historical-v16-prelaunch-authority-is-consumed" in receipt["blockers"]


def test_historical_v16_lifecycle_omission_fails_before_secret_access(
    deterministic_inputs: tuple[dict[str, object], dict[str, object]],
) -> None:
    registry, lint = deterministic_inputs

    def pre_repair_loader(repository: Path, *, contract: object) -> object:
        if getattr(contract, "version", None) == "V16":
            raise T09ProviderError("provider lifecycle contract is unsupported")
        return load_campaign_lifecycle(repository, contract=contract)  # type: ignore[arg-type]

    with pytest.raises(CompositionError, match="lifecycle composition failed"):
        compose_control_plane(
            ROOT,
            contract=V16_PROVIDER_CONTRACT,
            registry_receipt=registry,
            version_lint_receipt=lint,
            lifecycle_loader=pre_repair_loader,
        )


def test_invalid_command_package_fails(
    monkeypatch: pytest.MonkeyPatch,
    deterministic_inputs: tuple[dict[str, object], dict[str, object]],
) -> None:
    document, sha256, source = resolve_registered_command_package(ROOT, V16_PROVIDER_CONTRACT)
    mutant = copy.deepcopy(document)
    mutant["manifests"] = []
    monkeypatch.setattr(
        composition,
        "resolve_registered_command_package",
        lambda _root, _contract: (mutant, sha256, source),
    )
    with pytest.raises(CompositionError, match="attempt matrix"):
        _compose(deterministic_inputs)


def test_invalid_pair_diff_fails(
    monkeypatch: pytest.MonkeyPatch,
    deterministic_inputs: tuple[dict[str, object], dict[str, object]],
) -> None:
    document, sha256, source = resolve_registered_command_package(ROOT, V16_PROVIDER_CONTRACT)
    mutant = copy.deepcopy(document)
    pair_diffs = mutant["pair_diffs"]
    assert isinstance(pair_diffs, list) and isinstance(pair_diffs[0], dict)
    pair_diffs[0]["valid"] = False
    monkeypatch.setattr(
        composition,
        "resolve_registered_command_package",
        lambda _root, _contract: (mutant, sha256, source),
    )
    with pytest.raises(CompositionError, match="invalid pair diff"):
        _compose(deterministic_inputs)


def test_invalid_cleanup_contract_fails(
    monkeypatch: pytest.MonkeyPatch,
    deterministic_inputs: tuple[dict[str, object], dict[str, object]],
) -> None:
    profile = copy.deepcopy(composition.load_provider_profile(ROOT, V16_PROVIDER_CONTRACT))
    reconciliation = profile["cleanup_export_reconciliation"]
    assert isinstance(reconciliation, dict)
    reconciliation["phases"] = ["prefreeze-zero-attempt"]
    monkeypatch.setattr(composition, "load_provider_profile", lambda _root, _contract: profile)
    with pytest.raises(CompositionError, match="cleanup contract"):
        _compose(deterministic_inputs)


def test_invalid_finalizer_source_contract_fails(
    monkeypatch: pytest.MonkeyPatch,
    deterministic_inputs: tuple[dict[str, object], dict[str, object]],
) -> None:
    document, sha256, source = resolve_registered_command_package(ROOT, V16_PROVIDER_CONTRACT)
    mutant = copy.deepcopy(document)
    mutant["local_finalizer_qualification_selector"] = {
        "argument": "--provider-contract",
        "value": "wrong",
    }
    monkeypatch.setattr(
        composition,
        "resolve_registered_command_package",
        lambda _root, _contract: (mutant, sha256, source),
    )
    with pytest.raises(CompositionError, match="finalizer selector"):
        _compose(deterministic_inputs)


def test_composition_receipt_is_deterministic_and_schema_valid(
    deterministic_inputs: tuple[dict[str, object], dict[str, object]],
) -> None:
    first = _compose(deterministic_inputs)
    second = _compose(deterministic_inputs)
    assert first == second
    schema = load_json(ROOT / "schemas/t09-control-composition-receipt.schema.json")
    Draft202012Validator(schema).validate(first)


def test_static_composition_has_no_effect_adapter_surface(
    deterministic_inputs: tuple[dict[str, object], dict[str, object]],
) -> None:
    parameters = inspect.signature(compose_control_plane).parameters
    forbidden = {"secret", "metadata_transport", "provider_transport", "adapters"}
    assert forbidden.isdisjoint(parameters)
    assert _compose(deterministic_inputs)["static_composition_valid"] is True
