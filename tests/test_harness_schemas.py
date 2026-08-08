from __future__ import annotations

from copy import deepcopy

from harness_test_support import valid_plan_data

from giclab.harness.plan import load_run_plan, run_plan_document
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
    for name in ("run-plan", "run-profile", "pricing", "harness-event", "cloud-run"):
        assert "$id" in load_json(ROOT / f"schemas/{name}.schema.json")


def test_run_plan_schema_accepts_source_neutral_plan() -> None:
    assert validate_instance(valid_plan_data(), ROOT / "schemas/run-plan.schema.json") == []


def test_committed_synthetic_dry_run_fixture_is_valid() -> None:
    path = ROOT / "tests/fixtures/harness/synthetic-unauthorized-run-plan.json"
    fixture = load_json(path)
    assert "profile_plan_id" not in fixture
    assert "profile_sha256" not in fixture
    assert validate_instance(fixture, ROOT / "schemas/run-plan.schema.json") == []
    plan = load_run_plan(path, schema_root=ROOT)
    assert plan.profile_plan_id is None
    assert plan.profile_sha256 is None
    assert run_plan_document(plan) == fixture


def test_legacy_authorized_v01_plan_remains_schema_readable_without_parent_binding() -> None:
    data = valid_plan_data(
        authorized=True,
        profile_plan_id=None,
        profile_sha256_value=None,
    )
    assert validate_instance(data, ROOT / "schemas/run-plan.schema.json") == []


def test_committed_legacy_v01_authorized_plan_and_profile_remain_readable() -> None:
    plan_path = ROOT / "tests/fixtures/harness/legacy-authorized-run-plan-v0.1.json"
    plan_data = load_json(plan_path)
    assert validate_instance(plan_data, ROOT / "schemas/run-plan.schema.json") == []
    plan = load_run_plan(plan_path, schema_root=ROOT)
    assert plan.execution.authorization.authorized
    assert plan.profile_plan_id is None
    assert plan.profile_sha256 is None

    profile = load_json(ROOT / "tests/fixtures/harness/legacy-run-profile-v0.1.json")
    assert validate_instance(profile, ROOT / "schemas/run-profile.schema.json") == []


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
