from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
import yaml
from jsonschema import Draft202012Validator

from giclab.harness import t09_model_metadata_receipt as metadata
from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness import t09_sira_pilot as pilot
from giclab.harness.t09_provider_contracts import (
    V13_PROVIDER_CONTRACT,
    V14_PROVIDER_CONTRACT,
)
from giclab.validation import validate_t09_v14_plan

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
PLAN = EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V14.yaml"
V13_PLAN = EXP / "run-plans/proposals/PLAN-EXP0001-PILOT-V13.yaml"
PROFILE = EXP / "run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V14.yaml"
EXECUTION = EXP / "contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V14.json"
COMMANDS = EXP / "contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V14.json"
RUNTIME_IDENTITY = EXP / "contracts/proposals/T09_PILOT_RUNTIME_IDENTITY_V14.json"
STOPPED = EXP / "T09_V13_STOPPED_DISPOSITION.json"
RECEIPT_SCHEMA = ROOT / "schemas/t09-v14-model-metadata-receipt.schema.json"
BASE_COMMIT = "12a6c4fba0972d3b6f9f16dcfae048dbb770d78a"
BASE_TREE = "c933d14fa32fac2b48c217fb65ebfbcfbaa2a08a"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def _private_json(path: Path, value: object) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))
    path.chmod(0o600)


def _load_plan(path: Path = PLAN) -> dict[str, object]:
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict)
    return value


class _Clock:
    def __init__(self, *values: float) -> None:
        self._values: Iterator[float] = iter(values)

    def __call__(self) -> float:
        return next(self._values)


class _MetadataTransport:
    def __init__(self, completed_at: float) -> None:
        self.completed_at = completed_at
        self.calls: list[str] = []

    def get_model_metadata(
        self,
        model_id: str,
        *,
        credential: bytearray,
    ) -> metadata.ModelMetadataResponse:
        assert credential == bytearray(b"fixture-openai-metadata-value-v14")
        self.calls.append(model_id)
        return metadata.ModelMetadataResponse(
            status=200,
            body=_canonical({"id": model_id}),
            response_completed_at=self.completed_at,
        )


def test_v14_plan_schema_package_and_false_flags_are_exact() -> None:
    plan = _load_plan()
    schema = json.loads((ROOT / "schemas/t09-v14-plan.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(plan)
    assert PLAN.stat().st_size == 19_232
    assert _sha256(PLAN) == "62252dbbde6ff7e28268ed3f3d3b94255227cc3d4e1c435f5f0374f95167c0ea"
    assert validate_t09_v14_plan(ROOT) == []
    assert plan["plan_id"] == V14_PROVIDER_CONTRACT.plan_id
    status = cast(dict[str, object], plan["status"])
    for field in (
        "authorized",
        "execution_allowed",
        "cloud_mutation_allowed",
        "paid_compute_allowed",
        "live_qualification_performed",
        "pilot_executed",
    ):
        assert status[field] is False
    identities = cast(dict[str, object], plan["identities"])
    assert identities["empirical_run_roots_materialized"] is False
    profile = yaml.safe_load(PROFILE.read_text())
    assert profile["execution"] == {
        "authorized": False,
        "authorization_reference": None,
    }
    assert not (ROOT / "artifacts/EXP-0001/pilot-v14").exists()
    budget = cast(dict[str, object], plan["budget_contract"])
    assert budget["prior_through_stopped_v12_conservative_usd_decimal"] == ("33.5284750827347920")
    assert budget["v13_stopped_lambda_cost_usd_decimal"] == "1.2454567425131797"
    assert budget["prior_t09_conservative_upper_bound_usd_decimal"] == ("34.7739318252479717")
    assert budget["effective_maximum_new_total_cost_under_cumulative_cap_usd_decimal"] == (
        "55.2260681747520283"
    )
    execution = json.loads(EXECUTION.read_text())
    assert execution["authorized"] is False
    assert execution["authorization_reference"] is None
    assert execution["execution_eligibility"] == ("blocked-until-fresh-category-3-authorization")


def test_v14_science_is_semantically_unchanged_from_v13() -> None:
    v14 = _load_plan()
    v13 = _load_plan(V13_PLAN)
    assert v14["scientific_contract"] == v13["scientific_contract"]
    science = cast(dict[str, object], v14["scientific_contract"])
    assert science["sira_commit"] == "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
    assert science["model_revision_for_every_role"] == "gpt-4o-2024-11-20"
    assert science["protocol_sha256"] == _sha256(EXP / "protocol.yaml")
    assert science["config_sha256"] == _sha256(EXP / "config.yaml")
    assert science["condition_retries_after_empirical_entry"] == 0


def test_v14_explicit_identity_bundle_and_cross_version_separation_are_exact() -> None:
    execution = json.loads(EXECUTION.read_text())
    loaded = pilot.load_execution_contract(EXECUTION, expected_sha256=_sha256(EXECUTION))
    assert loaded.provider_contract_version == "V14"
    assert tuple(attempt.run_id for attempt in loaded.attempts) == (
        V14_PROVIDER_CONTRACT.attempt_order
    )
    assert execution["identities"] == {
        "evaluator_run_ids": list(V14_PROVIDER_CONTRACT.evaluator_run_ids),
        "evidence_archive_id": V14_PROVIDER_CONTRACT.evidence_archive_id,
        "evidence_stage_id": V14_PROVIDER_CONTRACT.evidence_stage_id,
        "frozen_run_manifest_id": V14_PROVIDER_CONTRACT.frozen_run_manifest_id,
        "host_run_id": V14_PROVIDER_CONTRACT.host_run_id,
        "local_finalizer_qualification_id": (
            V14_PROVIDER_CONTRACT.local_finalizer_qualification_id
        ),
        "runtime_qualification_id": V14_PROVIDER_CONTRACT.active_image_qualification_id,
    }
    assert execution["runtime"]["local_finalizer_qualification_selector"] == [
        "--provider-contract",
        "V14",
    ]
    assert set(V14_PROVIDER_CONTRACT.attempt_order).isdisjoint(V13_PROVIDER_CONTRACT.attempt_order)
    assert set(V14_PROVIDER_CONTRACT.evaluator_run_ids).isdisjoint(
        V13_PROVIDER_CONTRACT.evaluator_run_ids
    )


def test_v14_commands_bind_selector_and_both_pair_diffs_are_valid() -> None:
    commands = json.loads(COMMANDS.read_text())
    selector = {"argument": "--provider-contract", "value": "V14"}
    assert commands["local_finalizer_qualification_selector"] == selector
    assert all(
        manifest["equality_surface"]["provider_contract_selector"] == selector
        for manifest in commands["manifests"]
    )
    assert all(pair["valid"] is True for pair in commands["pair_diffs"])
    assert all(pair["required_equality_surface_equal"] is True for pair in commands["pair_diffs"])


def test_v14_plan_binds_current_sources_artifacts_and_stopped_v13_record() -> None:
    bindings = cast(dict[str, object], _load_plan()["implementation_bindings"])
    specifications = {
        "provider_accounting": (("path", "sha256"), ("regression_path", "regression_sha256")),
        "offline_refinalization": (
            ("finalizer_projection_path", "finalizer_projection_sha256"),
            ("evaluator_driver_path", "evaluator_driver_sha256"),
            ("selector_path", "selector_sha256"),
            ("receipt_schema_path", "receipt_schema_sha256"),
        ),
        "early_cleanup": (
            ("implementation_path", "implementation_sha256"),
            ("provider_integration_path", "provider_integration_sha256"),
            ("schema_path", "schema_sha256"),
            ("export_handoff_schema_path", "export_handoff_schema_sha256"),
        ),
        "owned_container_publication": (
            ("reader_path", "reader_sha256"),
            ("regression_path", "regression_sha256"),
        ),
        "model_metadata_receipt": (
            ("implementation_path", "implementation_sha256"),
            ("schema_path", "schema_sha256"),
            ("public_price_contract_path", "public_price_contract_sha256"),
            ("public_deprecation_observation_path", "public_deprecation_observation_sha256"),
        ),
        "execution_plane": (
            ("pilot_library_path", "pilot_library_sha256"),
            ("campaign_lifecycle_path", "campaign_lifecycle_sha256"),
            ("provider_path", "provider_sha256"),
            ("provider_contracts_path", "provider_contracts_sha256"),
            ("remote_runner_path", "remote_runner_sha256"),
            ("preflight_path", "preflight_sha256"),
            (
                "local_finalizer_qualification_path",
                "local_finalizer_qualification_sha256",
            ),
            ("command_generator_path", "command_generator_sha256"),
            ("runtime_profile_path", "runtime_profile_sha256"),
            ("execution_contract_path", "execution_contract_sha256"),
            ("command_manifests_path", "command_manifests_sha256"),
            ("runtime_identity_path", "runtime_identity_sha256"),
            ("runtime_adaptation_path", "runtime_adaptation_sha256"),
            ("execution_schema_path", "execution_schema_sha256"),
        ),
    }
    for group_name, fields in specifications.items():
        group = cast(dict[str, object], bindings[group_name])
        for path_field, hash_field in fields:
            relative = str(group[path_field])
            assert _sha256(ROOT / relative) == group[hash_field]
    stopped = cast(dict[str, object], bindings["v13_stopped_disposition"])
    assert stopped == {
        "path": STOPPED.relative_to(ROOT).as_posix(),
        "size_bytes": 3541,
        "sha256": "5299095b595c3fa481f722e63091e3f8bef9fbc6a49b624b2066a78faa76eb66",
    }


def test_v13_stopped_disposition_is_sanitized_exact_and_nonreplayable() -> None:
    assert STOPPED.stat().st_size == 3541
    assert _sha256(STOPPED) == "5299095b595c3fa481f722e63091e3f8bef9fbc6a49b624b2066a78faa76eb66"
    stopped = json.loads(STOPPED.read_text())
    assert stopped["provider_contract_version"] == "V13"
    assert stopped["execution_boundary"]["empirical_entry_crossed"] is False
    assert stopped["execution_boundary"]["empirical_attempts_entered"] == 0
    assert stopped["execution_boundary"]["raw_attempts_complete"] == 0
    assert stopped["execution_boundary"]["attempts_completed"] == 0
    assert stopped["execution_boundary"]["dynamic_frozen_manifests"] == 0
    assert stopped["execution_boundary"]["retained_export_chronology_entries"] == 0
    assert stopped["request_accounting"]["task_model_calls"] == 0
    assert stopped["request_accounting"]["browser_actions"] == 0
    assert stopped["authority_disposition"]["replay_allowed"] is False
    assert stopped["cleanup"]["provider_terminal_or_absent"] is True
    assert stopped["cleanup"]["zero_running_t09_instances"] is True
    assert stopped["cleanup"]["remote_security_restored"] is True
    assert stopped["timing_and_cost"]["lambda_cost_usd"] == "1.2454567425131797"
    encoded = STOPPED.read_text().casefold()
    assert "/users/" not in encoded
    assert "private_instance" not in encoded
    assert "api_key" not in encoded


def test_v14_fake_metadata_receipt_is_fresh_and_rejects_v13_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan_sha256 = _sha256(PROFILE)
    overlay = tmp_path / "authorization-overlay.json"
    overlay_document = {
        "schema_version": metadata.MODEL_METADATA_SCHEMA_VERSION,
        "authorization_reference": "AUTH-T09-V14-CATEGORY3-FIXTURE-0001",
        "authorization_source_sha256": "1" * 64,
        "provider_contract_version": "V14",
        "repository_commit": BASE_COMMIT,
        "repository_tree": BASE_TREE,
        "plan_id": V14_PROVIDER_CONTRACT.plan_id,
        "plan_sha256": plan_sha256,
        "host_run_id": V14_PROVIDER_CONTRACT.host_run_id,
        "public_price_contract_sha256": "2" * 64,
        "public_deprecation_observation_sha256": "3" * 64,
        "model_metadata_receipt_sha256": None,
        "authorized": True,
        "single_use": True,
    }
    _private_json(overlay, overlay_document)
    dotenv = tmp_path / "mixed.env"
    dotenv.write_bytes(
        b"OPENAI_API_KEY=fixture-openai-metadata-value-v14\n"
        b"LAMBDA_API_KEY=fixture-lambda-provider-value-v14\n"
    )
    dotenv.chmod(0o644)
    output = tmp_path / metadata.MODEL_METADATA_RECEIPT_FILENAME
    transport = _MetadataTransport(1_700_000_000.25)
    monkeypatch.setattr(provider, "_verify_clean_package", lambda repository, commit: None)
    provider.model_metadata_preflight(
        contract=V14_PROVIDER_CONTRACT,
        repository=ROOT,
        package_commit=BASE_COMMIT,
        authorization_overlay=overlay,
        openai_dotenv=dotenv,
        output=output,
        transport=transport,
        clock=_Clock(1_700_000_000.0, 1_700_000_000.5),
    )
    receipt = json.loads(output.read_text())
    Draft202012Validator(json.loads(RECEIPT_SCHEMA.read_text())).validate(receipt)
    assert transport.calls == [metadata.MODEL_METADATA_MODEL_ID]
    assert receipt["plan_id"] == V14_PROVIDER_CONTRACT.plan_id
    assert receipt["provider_contract_version"] == "V14"
    assert receipt["host_run_id"] == V14_PROVIDER_CONTRACT.host_run_id
    metadata.validate_model_metadata_receipt(
        output,
        contract=V14_PROVIDER_CONTRACT,
        package_commit=BASE_COMMIT,
        package_tree=BASE_TREE,
        plan_sha256=plan_sha256,
        authorization_overlay=overlay,
        validation_policy=metadata.ModelMetadataReceiptValidationPolicy.DURABLE_OFFLINE,
    )
    with pytest.raises(metadata.ModelMetadataReceiptError, match="fixed semantics"):
        metadata.validate_model_metadata_receipt(
            output,
            contract=V13_PROVIDER_CONTRACT,
            package_commit=BASE_COMMIT,
            package_tree=BASE_TREE,
            plan_sha256=plan_sha256,
            validation_policy=metadata.ModelMetadataReceiptValidationPolicy.DURABLE_OFFLINE,
        )

    wrong_overlay = tmp_path / "wrong-authorization-overlay.json"
    _private_json(
        wrong_overlay,
        {
            **overlay_document,
            "authorization_reference": "AUTH-T09-V13-CATEGORY3-FIXTURE-0001",
        },
    )
    with pytest.raises(metadata.ModelMetadataReceiptError, match="selected-contract authority"):
        metadata.validate_model_metadata_authorization_overlay(
            wrong_overlay,
            contract=V14_PROVIDER_CONTRACT,
            package_commit=BASE_COMMIT,
            package_tree=BASE_TREE,
            plan_sha256=plan_sha256,
        )
