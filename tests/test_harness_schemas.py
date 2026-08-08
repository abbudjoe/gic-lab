from __future__ import annotations

from copy import deepcopy

from harness_test_support import valid_plan_data

from giclab.registry import load_json
from giclab.validation import ROOT, validate_instance


def _valid_cloud_contract() -> dict[str, object]:
    return {
        "schema_version": "0.1.0",
        "provider": "synthetic-cloud",
        "run_id": "RUN-SYNTHETIC-001",
        "attempt": 1,
        "instance": {
            "resource_type": "synthetic-type",
            "region": "synthetic-region",
            "image": "synthetic-image@sha256:unknown",
            "architecture": "x86_64",
            "accelerator_count": 1,
        },
        "pricing": {
            "price_per_accelerator_hour_usd": 1.0,
            "verified_at_utc": "2026-08-07T12:00:00Z",
            "source": "versioned-price-record",
        },
        "limits": {
            "max_wall_seconds": 60,
            "max_cost_usd": 1.0,
            "max_gpu_hours": 1.0,
            "max_output_bytes": 1048576,
            "hard_termination_utc": "2026-08-07T13:00:00Z",
        },
        "storage": {
            "filesystem_action": "none",
            "artifact_destination": "s3://synthetic-bucket/prefix",
        },
        "authorization": {
            "authorized": False,
            "authorization_reference": None,
        },
        "termination": {
            "authorized": False,
            "method": "provider-api",
            "verify_terminal_state": True,
        },
    }


def test_harness_schema_documents_are_registered() -> None:
    for name in ("run-plan", "harness-event", "cloud-run"):
        assert "$id" in load_json(ROOT / f"schemas/{name}.schema.json")


def test_run_plan_schema_accepts_source_neutral_plan() -> None:
    assert validate_instance(valid_plan_data(), ROOT / "schemas/run-plan.schema.json") == []


def test_committed_synthetic_dry_run_fixture_is_valid() -> None:
    fixture = load_json(ROOT / "tests/fixtures/harness/synthetic-unauthorized-run-plan.json")
    assert validate_instance(fixture, ROOT / "schemas/run-plan.schema.json") == []


def test_run_plan_schema_rejects_authorized_plan_without_reference() -> None:
    data = valid_plan_data(authorized=True)
    data["execution"]["authorization"]["authorization_reference"] = None
    assert any(
        "not of type 'string'" in error
        for error in validate_instance(data, ROOT / "schemas/run-plan.schema.json")
    )


def test_run_plan_schema_rejects_credential_shaped_authorization_reference() -> None:
    data = valid_plan_data(authorized=True)
    data["execution"]["authorization"]["authorization_reference"] = (
        "https://example.invalid/?signature=value"
    )
    assert any(
        "does not match" in error
        for error in validate_instance(data, ROOT / "schemas/run-plan.schema.json")
    )


def test_cloud_contract_defaults_to_unauthorized_and_validates() -> None:
    contract = _valid_cloud_contract()
    assert validate_instance(contract, ROOT / "schemas/cloud-run.schema.json") == []


def test_cloud_contract_rejects_authority_without_reference() -> None:
    contract = deepcopy(_valid_cloud_contract())
    authorization = contract["authorization"]
    assert isinstance(authorization, dict)
    authorization["authorized"] = True
    assert any(
        "not of type 'string'" in error
        for error in validate_instance(contract, ROOT / "schemas/cloud-run.schema.json")
    )


def test_cloud_contract_requires_separately_authorized_termination() -> None:
    contract = deepcopy(_valid_cloud_contract())
    authorization = contract["authorization"]
    assert isinstance(authorization, dict)
    authorization["authorized"] = True
    authorization["authorization_reference"] = "AUTH-CLOUD-TEST"
    assert any(
        "True was expected" in error
        for error in validate_instance(contract, ROOT / "schemas/cloud-run.schema.json")
    )


def test_cloud_contract_rejects_signed_artifact_destination() -> None:
    contract = deepcopy(_valid_cloud_contract())
    storage = contract["storage"]
    assert isinstance(storage, dict)
    storage["artifact_destination"] = "https://example.invalid/path?signature=secret"
    assert any(
        "does not match" in error
        for error in validate_instance(contract, ROOT / "schemas/cloud-run.schema.json")
    )
