from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

import giclab.harness.lambda_inventory as v1_runner
import giclab.harness.lambda_inventory_v3 as runner
from giclab.harness.lambda_archive_v3 import ArchivedInventoryArtifactV3
from giclab.harness.lambda_cloud import (
    InventoryResponseFailureKind,
    InventoryResponseValidationError,
    LambdaCloudContractError,
)
from giclab.harness.lambda_cloud_v3 import (
    ENDPOINT_SCHEMA_PATHS,
    INVENTORY_PLAN_V3_ID,
    INVENTORY_RUN_V3_ID,
    EndpointOutcomeV3,
    EndpointSchemaBinding,
    IncrementalInventoryParserV3,
    audit_structural_report,
    canonical_inventory_v3_bytes,
    inventory_document_v3,
    select_compute_candidate_v3,
)
from giclab.harness.lambda_inventory_plan_v3 import (
    AUDIT_STRUCTURAL_SCHEMA_RELATIVE_PATH,
    IMPLEMENTATION_ARTIFACT_PATHS_V3,
    SCHEMA_FILES_V3,
    ImplementationArtifactBindingV3,
    InventoryRunBindingV3,
    ReadOnlyInventoryPlanV3,
    inventory_ledger_contract_document_v3,
    inventory_limits_document_v3,
    load_inventory_plan_v3,
    verify_inventory_implementation_v3,
)
from giclab.harness.lambda_request_ledger_v3 import validate_request_ledger_bytes
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
DUMMY_CREDENTIAL = "PUBLIC-DUMMY-LAMBDA-TOKEN-FOR-LOCAL-TESTS"
UNKNOWN_VALUE_CANARY = "UNKNOWN-SCALAR-CANARY-MUST-NOT-SURVIVE"
SSH_PUBLIC_KEY_CANARY = "ssh-ed25519 PUBLIC-DUMMY-KEY"
INSTANCE_PUBLIC_IP_CANARY = "203.0.113.42"
INSTANCE_PRIVATE_IP_CANARY = "10.0.0.42"
JUPYTER_TOKEN_CANARY = "PUBLIC-DUMMY-JUPYTER-TOKEN"
JUPYTER_URL_CANARY = "https://example.invalid/jupyter?token=PUBLIC-DUMMY-JUPYTER-TOKEN"
TAG_KEY_CANARY = "unrelated-sensitive-tag-key"
TAG_VALUE_CANARY = "unrelated-sensitive-tag-value"
PLAN_SHA256 = "1" * 64
COMMITTED_PLAN_SHA256 = "b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331"


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _region(name: str = "us-test-1") -> dict[str, object]:
    return {"name": name, "description": "Synthetic test region"}


def _instance_type(name: str, *, price: int = 69) -> dict[str, object]:
    return {
        "name": name,
        "description": "Synthetic type",
        "gpu_description": "Synthetic accelerator",
        "price_cents_per_hour": price,
        "specs": {"vcpus": 14, "memory_gib": 46, "storage_gib": 512, "gpus": 1},
        "architecture": "x86_64",
    }


def _running_instance() -> dict[str, object]:
    actions = {
        name: {"available": True}
        for name in ("migrate", "rebuild", "restart", "cold_reboot", "terminate")
    }
    return {
        "id": "instance-synthetic",
        "name": "unrelated-synthetic-running-instance",
        "status": "active",
        "ssh_key_names": ["synthetic-key"],
        "file_system_names": [],
        "region": _region(),
        "instance_type": _instance_type("gpu_1x_synthetic"),
        "actions": actions,
        "ip": INSTANCE_PUBLIC_IP_CANARY,
        "private_ip": INSTANCE_PRIVATE_IP_CANARY,
        "jupyter_token": JUPYTER_TOKEN_CANARY,
        "jupyter_url": JUPYTER_URL_CANARY,
        "tags": [{"key": TAG_KEY_CANARY, "value": TAG_VALUE_CANARY}],
    }


def _responses() -> dict[str, bytes]:
    instance_name = "gpu_1x_synthetic"
    ssh_rule = {
        "protocol": "tcp",
        "port_range": [22, 22],
        "source_network": "192.0.2.0/24",
        "description": "Synthetic SSH rule",
    }
    return {
        "instance-types": _encoded(
            {
                "data": {
                    instance_name: {
                        "instance_type": _instance_type(instance_name),
                        "regions_with_capacity_available": [_region()],
                    }
                }
            }
        ),
        "images": _encoded(
            {
                "data": [
                    {
                        "id": "image-synthetic",
                        "created_time": "2026-08-01T00:00:00Z",
                        "updated_time": "2026-08-01T00:00:00Z",
                        "name": "Synthetic image",
                        "description": "Synthetic image fixture",
                        "family": "gpu-base-22-04",
                        "version": "synthetic-v1",
                        "architecture": "x86_64",
                        "region": _region(),
                    }
                ]
            }
        ),
        "regions": _encoded({"data": [_region()]}),
        "ssh-keys": _encoded(
            {
                "data": [
                    {
                        "id": "ssh-key-synthetic",
                        "name": "synthetic-key",
                        "public_key": SSH_PUBLIC_KEY_CANARY,
                    }
                ]
            }
        ),
        "firewall-rulesets": _encoded(
            {
                "data": [
                    {
                        "id": "firewall-synthetic",
                        "name": "Synthetic SSH",
                        "region": _region(),
                        "rules": [ssh_rule],
                        "created": "2026-08-01T00:00:00Z",
                        "instance_ids": [],
                    }
                ]
            }
        ),
        "global-firewall-ruleset": _encoded(
            {"data": {"id": "global", "name": "Global SSH", "rules": [ssh_rule]}}
        ),
        "running-instances": _encoded({"data": [_running_instance()]}),
    }


def _audit_event() -> dict[str, object]:
    return {
        "service_name": "synthetic",
        "resource_name": "synthetic",
        "action": "synthetic",
        "catalog_version": "synthetic",
        "event_id": "synthetic",
        "event_time": "2026-08-10T00:00:00Z",
        "actor_lrn": None,
        "resource_lrns": [],
        "resource_owner_lrn": None,
        "request_api_key_lrn": None,
        "additional_details": {},
    }


def _implementation_bindings() -> tuple[ImplementationArtifactBindingV3, ...]:
    return tuple(
        ImplementationArtifactBindingV3(
            path,
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
        )
        for path in IMPLEMENTATION_ARTIFACT_PATHS_V3
    )


def _endpoint_bindings(root: Path) -> dict[str, EndpointSchemaBinding]:
    return {
        request_id: EndpointSchemaBinding(
            request_id,
            path,
            hashlib.sha256((root / path).read_bytes()).hexdigest(),
        )
        for request_id, path in ENDPOINT_SCHEMA_PATHS.items()
    }


def _plan(root: Path = ROOT) -> ReadOnlyInventoryPlanV3:
    return ReadOnlyInventoryPlanV3(
        implementation_commit="7" * 40,
        implementation_artifacts=_implementation_bindings(),
        ledger_schema_sha256=hashlib.sha256(
            (root / "schemas/t07-lambda-request-ledger-v3.schema.json").read_bytes()
        ).hexdigest(),
        inventory_schema_sha256=hashlib.sha256(
            (root / "schemas/t07-lambda-inventory-v3.schema.json").read_bytes()
        ).hexdigest(),
        extension_schema_sha256=hashlib.sha256(
            (root / "schemas/t07-lambda-schema-extension-report.schema.json").read_bytes()
        ).hexdigest(),
        endpoint_schema_bindings=_endpoint_bindings(root),
    )


def _copy_runtime_schemas(root: Path) -> None:
    (root / "schemas").mkdir(parents=True)
    for name in (
        "t07-lambda-request-ledger-v3.schema.json",
        "t07-lambda-inventory-v3.schema.json",
        "t07-lambda-schema-extension-report.schema.json",
    ):
        shutil.copyfile(ROOT / "schemas" / name, root / "schemas" / name)
    endpoint_root = root / "containers/sira-smoke/lambda/endpoint-schemas-v3"
    endpoint_root.mkdir(parents=True)
    for relative in ENDPOINT_SCHEMA_PATHS.values():
        source = ROOT / relative
        shutil.copyfile(source, root / relative)


def _parsed(root: Path = ROOT) -> tuple[IncrementalInventoryParserV3, object]:
    plan = _plan(root)
    parser = IncrementalInventoryParserV3(root, plan)
    responses = _responses()
    for request in plan.requests:
        parser.accept(request, responses[request.request_id])
    return parser, parser.finish()


def _binding() -> InventoryRunBindingV3:
    return InventoryRunBindingV3(
        run_id=INVENTORY_RUN_V3_ID,
        repository_commit="7" * 40,
        implementation_commit="7" * 40,
        authorization_reference="AUTH-T07-GATE-L1-LOCAL-V4-TEST",
        authorization_sha256="8" * 64,
    )


def _outcomes(
    parser: IncrementalInventoryParserV3, plan: ReadOnlyInventoryPlanV3
) -> tuple[EndpointOutcomeV3, ...]:
    return tuple(
        EndpointOutcomeV3(
            request_id=request.request_id,
            method="GET",
            path=request.path,
            http_status=200,
            response_bytes=parser.response_bytes[request.request_id],
            schema_path=plan.endpoint_schema_bindings[request.request_id].path,
            schema_sha256=plan.endpoint_schema_bindings[request.request_id].sha256,
            validation_state=str(parser.observations[index]["validation_state"]),
        )
        for index, request in enumerate(plan.requests)
    )


def test_audit_structural_analyzer_accepts_official_null_page_shape() -> None:
    report = audit_structural_report(_encoded({"data": [_audit_event()], "page_token": None}))
    assert report["page_token_state"] == "null"
    assert report["required_key_omissions"] == []
    assert report["type_mismatches"] == []
    assert report["sensitive_scalar_values_retained"] is False
    assert (
        validate_instance(report, ROOT / "schemas/t07-lambda-audit-structural-report.schema.json")
        == []
    )


def test_audit_structural_analyzer_distinguishes_pagination_and_additive_keys() -> None:
    event = _audit_event()
    event["future_event_field"] = UNKNOWN_VALUE_CANARY
    report = audit_structural_report(
        _encoded(
            {
                "data": [event],
                "page_token": "synthetic-continuation",
                "future_top_field": UNKNOWN_VALUE_CANARY,
            }
        )
    )
    encoded = _encoded(report)
    assert report["page_token_state"] == "non_null"
    assert report["unknown_key_names"] == ["future_event_field", "future_top_field"]
    assert UNKNOWN_VALUE_CANARY.encode() not in encoded


def test_audit_structural_analyzer_reports_missing_types_and_documented_nullability() -> None:
    event = _audit_event()
    event.pop("event_id")
    event["resource_lrns"] = [1]
    report = audit_structural_report(_encoded({"data": [event], "page_token": None}))
    assert report["required_key_omissions"] == ["event_id"]
    assert report["nullability_observations"]["actor_lrn"] == "always_null"
    assert report["type_mismatches"]


def test_v3_plan_is_exactly_seven_gets_and_has_no_audit_or_account_lrn() -> None:
    plan = _plan()
    assert plan.plan_id == INVENTORY_PLAN_V3_ID
    assert [request.request_id for request in plan.requests] == [
        "instance-types",
        "images",
        "regions",
        "ssh-keys",
        "firewall-rulesets",
        "global-firewall-ruleset",
        "running-instances",
    ]
    assert all("audit-events" not in request.path for request in plan.requests)
    assert plan.max_calls == 7
    assert plan.max_total_response_bytes == 1_835_008
    assert plan.limits.max_bytes == 172_032
    assert plan.limits.max_events == 84
    assert plan.max_aggregate_retained_bytes == 1_826_816
    assert plan.max_local_command_calls == 15
    assert plan.max_local_command_output_bytes == 37_879_810


def test_committed_v3_plan_loads_and_binds_the_frozen_implementation() -> None:
    path = ROOT / "containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == COMMITTED_PLAN_SHA256
    plan = load_inventory_plan_v3(path, expected_sha256=COMMITTED_PLAN_SHA256)
    assert plan.implementation_commit == "718c75c694b3033fa7ef2ed5e7c4696fd8c389f3"
    verify_inventory_implementation_v3(ROOT, plan)


def test_schema_bindings_must_match_the_implementation_manifest() -> None:
    plan = _plan()
    drifted = dict(plan.endpoint_schema_bindings)
    original = drifted["images"]
    drifted["images"] = EndpointSchemaBinding(
        original.request_id,
        original.path,
        "0" * 64,
    )
    with pytest.raises(LambdaCloudContractError, match="cross-bound"):
        replace(plan, endpoint_schema_bindings=drifted)


def test_v3_schema_registry_is_versioned_without_drifting_v2_validation() -> None:
    assert (
        AUDIT_STRUCTURAL_SCHEMA_RELATIVE_PATH,
        "schemas/t07-lambda-schema-extension-report.schema.json",
        "schemas/t07-lambda-inventory-v3.schema.json",
        "schemas/t07-lambda-request-ledger-v3.schema.json",
        *tuple(ENDPOINT_SCHEMA_PATHS.values()),
    ) == SCHEMA_FILES_V3
    assert all((ROOT / relative).is_file() for relative in SCHEMA_FILES_V3)


def test_preflight_meta_validates_every_endpoint_schema(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    for relative in IMPLEMENTATION_ARTIFACT_PATHS_V3:
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    invalid_schema_path = repository / ENDPOINT_SCHEMA_PATHS["images"]
    invalid_schema_path.write_text('{"type":"not-a-json-schema-type"}\n', encoding="utf-8")
    artifacts = tuple(
        ImplementationArtifactBindingV3(
            relative,
            hashlib.sha256((repository / relative).read_bytes()).hexdigest(),
        )
        for relative in IMPLEMENTATION_ARTIFACT_PATHS_V3
    )
    endpoint_bindings = _endpoint_bindings(repository)
    plan = ReadOnlyInventoryPlanV3(
        implementation_commit="7" * 40,
        implementation_artifacts=artifacts,
        ledger_schema_sha256=hashlib.sha256(
            (repository / "schemas/t07-lambda-request-ledger-v3.schema.json").read_bytes()
        ).hexdigest(),
        inventory_schema_sha256=hashlib.sha256(
            (repository / "schemas/t07-lambda-inventory-v3.schema.json").read_bytes()
        ).hexdigest(),
        extension_schema_sha256=hashlib.sha256(
            (repository / "schemas/t07-lambda-schema-extension-report.schema.json").read_bytes()
        ).hexdigest(),
        endpoint_schema_bindings=endpoint_bindings,
    )
    with pytest.raises(LambdaCloudContractError, match="schema binding failed"):
        verify_inventory_implementation_v3(repository, plan)


def test_all_seven_responses_complete_inventory_gate_without_account_history() -> None:
    parser, inventory = _parsed()
    plan = _plan()
    candidate = select_compute_candidate_v3(inventory)
    report = parser.extension_report()
    document = inventory_document_v3(
        inventory,
        candidate,
        observed_at_utc="2026-08-10T00:00:00Z",
        inventory_plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
        endpoint_outcomes=_outcomes(parser, plan),
        extension_report=report,
        extension_schema_sha256=plan.extension_schema_sha256,
        limits_document=inventory_limits_document_v3(plan),
        request_ledger_contract=inventory_ledger_contract_document_v3(plan),
    )
    encoded = canonical_inventory_v3_bytes(document)
    assert b"account_lrn" not in encoded
    assert b"workspace_lrn" not in encoded
    assert document["account_identity"]["state"] == "unavailable_not_required"
    assert validate_instance(document, ROOT / "schemas/t07-lambda-inventory-v3.schema.json") == []


def test_redacted_inventory_drops_known_sensitive_account_fields() -> None:
    responses = _responses()
    raw = b"".join(responses.values())
    sensitive_values = (
        SSH_PUBLIC_KEY_CANARY,
        INSTANCE_PUBLIC_IP_CANARY,
        INSTANCE_PRIVATE_IP_CANARY,
        JUPYTER_TOKEN_CANARY,
        JUPYTER_URL_CANARY,
        TAG_KEY_CANARY,
        TAG_VALUE_CANARY,
    )
    assert all(value.encode() in raw for value in sensitive_values)

    parser, inventory = _parsed()
    plan = _plan()
    document = inventory_document_v3(
        inventory,
        select_compute_candidate_v3(inventory),
        observed_at_utc="2026-08-10T00:00:00Z",
        inventory_plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
        endpoint_outcomes=_outcomes(parser, plan),
        extension_report=parser.extension_report(),
        extension_schema_sha256=plan.extension_schema_sha256,
        limits_document=inventory_limits_document_v3(plan),
        request_ledger_contract=inventory_ledger_contract_document_v3(plan),
    )
    retained = canonical_inventory_v3_bytes(document)
    assert all(value.encode() not in retained for value in sensitive_values)
    assert all(
        field not in retained
        for field in (
            b'"public_key"',
            b'"ip"',
            b'"private_ip"',
            b'"jupyter_token"',
            b'"jupyter_url"',
            b'"tags"',
        )
    )
    assert document["redaction"] == {
        "raw_responses_retained": False,
        "api_key_retained": False,
        "ssh_public_keys_retained": False,
        "instance_ip_addresses_retained": False,
        "firewall_source_cidrs_retained": True,
        "jupyter_credentials_retained": False,
        "audit_history_requested": False,
        "unknown_scalar_values_retained": False,
    }


def test_additive_top_and_item_fields_are_accepted_reported_and_values_discarded() -> None:
    plan = _plan()
    responses = _responses()
    images = json.loads(responses["images"])
    images["future_top_field"] = UNKNOWN_VALUE_CANARY
    images["data"][0]["future_item_field"] = UNKNOWN_VALUE_CANARY
    responses["images"] = _encoded(images)
    parser = IncrementalInventoryParserV3(ROOT, plan)
    for request in plan.requests:
        parser.accept(request, responses[request.request_id])
    parser.finish()
    report = parser.extension_report()
    encoded = _encoded(report)
    image_observation = report["observations"][1]
    assert image_observation["validation_state"] == "compatible_extension_observed"
    assert UNKNOWN_VALUE_CANARY.encode() not in encoded
    assert b"future_top_field" in encoded
    assert b"future_item_field" in encoded


@pytest.mark.parametrize(
    ("mutation", "kind"),
    [
        ("missing", InventoryResponseFailureKind.SCHEMA_VALIDATION),
        ("wrong_type", InventoryResponseFailureKind.SCHEMA_VALIDATION),
        ("pagination", InventoryResponseFailureKind.PAGINATION),
    ],
)
def test_incompatible_or_paginated_response_stops_without_completion(
    mutation: str, kind: InventoryResponseFailureKind
) -> None:
    plan = _plan()
    responses = _responses()
    images = json.loads(responses["images"])
    if mutation == "missing":
        images["data"][0].pop("id")
    elif mutation == "wrong_type":
        images["data"][0]["architecture"] = 3
    else:
        images["page_token"] = "synthetic-next"
    responses["images"] = _encoded(images)
    parser = IncrementalInventoryParserV3(ROOT, plan)
    parser.accept(plan.requests[0], responses["instance-types"])
    with pytest.raises(InventoryResponseValidationError) as raised:
        parser.accept(plan.requests[1], responses["images"])
    assert raised.value.kind is kind
    assert parser.accepted_requests == 1


@pytest.mark.parametrize("continuation", ["", 0, [], {}])
def test_every_non_null_continuation_value_is_pagination(continuation: object) -> None:
    plan = _plan()
    responses = _responses()
    first = json.loads(responses["instance-types"])
    first["page_token"] = continuation
    parser = IncrementalInventoryParserV3(ROOT, plan)
    with pytest.raises(InventoryResponseValidationError) as raised:
        parser.accept(plan.requests[0], _encoded(first))
    assert raised.value.kind is InventoryResponseFailureKind.PAGINATION
    assert parser.accepted_requests == 0


def test_extension_report_limits_are_enforced_before_accepting_a_response() -> None:
    plan = _plan()
    responses = _responses()
    first = json.loads(responses["instance-types"])
    first.update({f"future_{index:03d}": index for index in range(129)})
    parser = IncrementalInventoryParserV3(ROOT, plan)
    with pytest.raises(InventoryResponseValidationError, match="EXTENSION_REPORT_INELIGIBLE"):
        parser.accept(plan.requests[0], _encoded(first))
    assert parser.accepted_requests == 0
    assert parser.observations == []


def _mutated_endpoint_response(request_id: str, mutation: str) -> bytes:
    document = json.loads(_responses()[request_id])
    if request_id == "instance-types":
        record = next(iter(document["data"].values()))
        if mutation == "missing":
            record.pop("regions_with_capacity_available")
        else:
            record["regions_with_capacity_available"] = {}
    elif request_id == "images":
        if mutation == "missing":
            document["data"][0].pop("id")
        else:
            document["data"][0]["architecture"] = 3
    elif request_id == "regions":
        if mutation == "missing":
            document["data"][0].pop("name")
        else:
            document["data"][0]["description"] = 3
    elif request_id == "ssh-keys":
        if mutation == "missing":
            document["data"][0].pop("public_key")
        else:
            document["data"][0]["public_key"] = 3
    elif request_id == "firewall-rulesets":
        if mutation == "missing":
            document["data"][0].pop("created")
        else:
            document["data"][0]["rules"] = "not-an-array"
    elif request_id == "global-firewall-ruleset":
        if mutation == "missing":
            document["data"].pop("name")
        else:
            document["data"]["rules"] = "not-an-array"
    else:
        document["data"] = [_running_instance()]
        if mutation == "missing":
            document["data"][0].pop("status")
        else:
            document["data"][0]["actions"]["terminate"]["available"] = "yes"
    return _encoded(document)


@pytest.mark.parametrize("request_id", list(ENDPOINT_SCHEMA_PATHS))
@pytest.mark.parametrize("mutation", ["missing", "wrong_type"])
def test_each_endpoint_rejects_required_field_or_type_drift(
    request_id: str,
    mutation: str,
) -> None:
    plan = _plan()
    responses = _responses()
    responses[request_id] = _mutated_endpoint_response(request_id, mutation)
    parser = IncrementalInventoryParserV3(ROOT, plan)
    for request in plan.requests:
        if request.request_id == request_id:
            with pytest.raises(InventoryResponseValidationError) as raised:
                parser.accept(request, responses[request_id])
            assert raised.value.kind is InventoryResponseFailureKind.SCHEMA_VALIDATION
            assert parser.accepted_requests == plan.requests.index(request)
            break
        parser.accept(request, responses[request.request_id])


@pytest.mark.parametrize("request_id", list(ENDPOINT_SCHEMA_PATHS))
def test_each_open_official_endpoint_accepts_and_sanitizes_additive_keys(
    request_id: str,
) -> None:
    plan = _plan()
    responses = _responses()
    document = json.loads(responses[request_id])
    document["future_top_level_field"] = UNKNOWN_VALUE_CANARY
    responses[request_id] = _encoded(document)
    parser = IncrementalInventoryParserV3(ROOT, plan)
    for request in plan.requests:
        parser.accept(request, responses[request.request_id])
    parser.finish()
    report = parser.extension_report()
    observation = next(item for item in report["observations"] if item["request_id"] == request_id)
    assert observation["validation_state"] == "compatible_extension_observed"
    assert UNKNOWN_VALUE_CANARY.encode() not in _encoded(report)


def test_retained_inventory_and_extension_schemas_are_closed_to_additive_keys() -> None:
    parser, inventory = _parsed()
    plan = _plan()
    candidate = select_compute_candidate_v3(inventory)
    report = parser.extension_report()
    drifted_report = dict(report)
    drifted_report["future"] = False
    assert validate_instance(
        drifted_report,
        ROOT / "schemas/t07-lambda-schema-extension-report.schema.json",
    )
    document = inventory_document_v3(
        inventory,
        candidate,
        observed_at_utc="2026-08-10T00:00:00Z",
        inventory_plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
        endpoint_outcomes=_outcomes(parser, plan),
        extension_report=report,
        extension_schema_sha256=plan.extension_schema_sha256,
        limits_document=inventory_limits_document_v3(plan),
        request_ledger_contract=inventory_ledger_contract_document_v3(plan),
    )
    document["future"] = False
    assert validate_instance(document, ROOT / "schemas/t07-lambda-inventory-v3.schema.json")


def test_incomplete_v3_response_set_cannot_satisfy_inventory_gate() -> None:
    plan = _plan()
    parser = IncrementalInventoryParserV3(ROOT, plan)
    parser.accept(plan.requests[0], _responses()["instance-types"])
    with pytest.raises(InventoryResponseValidationError, match="INCOMPLETE"):
        parser.finish()


def test_v1_v2_plans_and_run_0002_ledger_remain_byte_identical() -> None:
    assert (
        hashlib.sha256(
            (
                ROOT / "containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan.json"
            ).read_bytes()
        ).hexdigest()
        == "c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69"
    )
    assert (
        hashlib.sha256(
            (
                ROOT / "containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v2.json"
            ).read_bytes()
        ).hexdigest()
        == "02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e"
    )
    ledger = (
        ROOT / "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0002/request-ledger.jsonl"
    )
    assert hashlib.sha256(ledger.read_bytes()).hexdigest() == (
        "a1cb81ce286881c33d879ce73787e755eed8ecd1f64ca2b9eaca7d39824a2c94"
    )
    run3 = ROOT / "artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003"
    assert hashlib.sha256((run3 / "inventory-redacted.json").read_bytes()).hexdigest() == (
        "022835438165e7e6e70dc992d6904f4e8b9448dc933d1d4c3e39ebdcc8914933"
    )
    assert hashlib.sha256((run3 / "request-ledger.jsonl").read_bytes()).hexdigest() == (
        "1f94068bdb1d1d2af0075d50c1a0c06eb1c077d4128f90bdc16fd571fa6af707"
    )


def test_historical_adjudication_is_additive_and_never_makes_run_0002_eligible() -> None:
    record = json.loads(
        (
            ROOT / "docs/harness/evidence/T07_RUN_0002_HISTORICAL_SCHEMA_ADJUDICATION.json"
        ).read_bytes()
    )
    assert record["historical_run_id"] == "RUN-T07-L1-LAMBDA-INVENTORY-0002"
    assert record["adjudicated_classification"] == "unadjudicated_raw_body_absent"
    assert record["raw_response_body"]["state"] == "absent"
    assert record["sanitized_structural_report"]["sha256"] is None
    assert record["historical_run_complete"] is False
    assert record["gate_l2_eligible"] is False
    assert record["no_replay"] is True


def test_public_openapi_observation_binds_the_official_contract_without_account_access() -> None:
    observation = json.loads(
        (ROOT / "containers/sira-smoke/lambda/public-openapi-observation-v3.json").read_bytes()
    )
    assert observation["specification"] == {
        "url": "https://docs.lambda.ai/api/cloud/spec.json",
        "documentation_url": "https://docs-api.lambda.ai/api/cloud",
        "declared_version": "1.10.0",
        "bytes": 239_644,
        "sha256": "365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded",
        "retrieved_at_utc": "2026-08-09T20:36:01Z",
        "revalidated_at_utc": "2026-08-10T11:35:38Z",
        "revalidation_observation": (
            "The first-party public documentation still advertises Download OpenAPI spec "
            "1.10.0. The byte count and SHA-256 remain bound to the prior first-party spec "
            "retrieval; they were not inferred from the rendered documentation page."
        ),
    }
    assert observation["relevant_read_only_endpoints"] == [
        "/api/v1/instance-types",
        "/api/v1/images",
        "/api/v1/regions",
        "/api/v1/ssh-keys",
        "/api/v1/firewall-rulesets",
        "/api/v1/firewall-rulesets/global",
        "/api/v1/instances",
    ]
    assert observation["audit_contract_observation"]["page_token_required"] is True
    assert observation["audit_contract_observation"]["page_token_type"] == ["string", "null"]
    assert observation["launch_contract_requires_account_lrn"] is False
    assert observation["account_api_called"] is False
    assert observation["authenticated_request_made"] is False
    assert observation["real_secret_accessed"] is False
    assert observation["payload_downloaded"] is False


def test_v3_run_binding_rejects_burned_run_0002() -> None:
    with pytest.raises(LambdaCloudContractError, match="identity drifted"):
        InventoryRunBindingV3(
            run_id="RUN-T07-L1-LAMBDA-INVENTORY-0002",
            repository_commit="7" * 40,
            implementation_commit="7" * 40,
            authorization_reference="AUTH-T07-GATE-L1-LOCAL-V4-TEST",
            authorization_sha256="8" * 64,
        )


@dataclass(slots=True)
class MutableClock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class FakeDeadline:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeTransport:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.request_ids: list[str] = []

    def fetch(self, request, *, credential, timeout_seconds, observer):
        assert credential == DUMMY_CREDENTIAL
        assert timeout_seconds > 0
        self.request_ids.append(request.request_id)
        body = self.responses[request.request_id]
        observer.response_headers_received(
            status_code=200,
            content_type="application/json",
            elapsed_ms=1,
        )
        observer.response_body_progress(
            bytes_received=len(body),
            status_code=200,
            content_type="application/json",
            elapsed_ms=2,
        )
        return runner.InventoryHttpResponseV3(200, "application/json", body, 2)


class FakePreparedArchiveV3:
    def __init__(self, root: Path, plan: ReadOnlyInventoryPlanV3, binding: InventoryRunBindingV3):
        self.root = root
        self.plan = plan
        self.binding = binding
        self.staged = False
        self.closed = False

    def stage_inventory(self, artifact_path, *, artifact_sha256, artifact_bytes) -> None:
        encoded = artifact_path.read_bytes()
        assert len(encoded) == artifact_bytes
        assert hashlib.sha256(encoded).hexdigest() == artifact_sha256
        self.staged = True

    def finalize(self, artifact_path, *, artifact_sha256, artifact_bytes, ledger):
        assert self.staged
        encoded = ledger.path.read_bytes()
        schema = json.loads((self.root / self.plan.ledger_schema_relative_path).read_bytes())
        events = validate_request_ledger_bytes(
            encoded,
            plan=self.plan,
            run_binding=self.binding,
            validator=Draft202012Validator(schema, format_checker=FormatChecker()),
            require_terminal_success=True,
        )
        assert len(events) == ledger.events
        local_record = _encoded(
            {
                "archive": "verified",
                "inventory_sha256": artifact_sha256,
                "ledger_sha256": ledger.sha256,
            }
        )
        return ArchivedInventoryArtifactV3(
            destination=Path("/synthetic-external/RUN-T07-L1-LAMBDA-INVENTORY-0003"),
            artifact_sha256=artifact_sha256,
            artifact_bytes=artifact_bytes,
            ledger_sha256=ledger.sha256,
            ledger_bytes=ledger.bytes,
            seal_sha256="3" * 64,
            external_copy_record_sha256="4" * 64,
            local_verification_record=local_record,
        )

    def close(self) -> None:
        self.closed = True


class FakeArchiverV3:
    def prepare(self, repository_root, *, plan, plan_sha256, run_binding):
        return FakePreparedArchiveV3(repository_root, plan, run_binding)


def test_fake_in_process_supervisor_runs_seven_gets_without_http_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_runtime_schemas(tmp_path)
    plan = _plan(tmp_path)
    monkeypatch.setattr(runner, "load_inventory_plan_v3", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        v1_runner.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("no subprocess may run in fake transport test")
        ),
    )
    monkeypatch.setattr(
        v1_runner.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("no subprocess may run in fake transport test")
        ),
    )
    clock = MutableClock()
    transport = FakeTransport(_responses())
    result = runner.execute_authorized_inventory_v3(
        repository_root=tmp_path,
        plan_path=tmp_path / "synthetic-plan.json",
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
        credential_provider=lambda: DUMMY_CREDENTIAL,
        transport=transport,
        archiver=FakeArchiverV3(),
        watchdog_factory=lambda seconds: FakeDeadline(),
        repository_inspector=lambda repository_root, expected_commit: runner.RepositoryState(
            branch="phase-1/sira-smoke-lambda",
            commit=expected_commit,
            clean=True,
        ),
        implementation_verifier=lambda repository_root, bound_plan: None,
        ancestry_verifier=lambda repository_root, **kwargs: None,
        clock=clock,
        sleeper=clock.sleep,
        monotonic_ns=iter(range(1, 1000)).__next__,
        utc_now=lambda: datetime(2026, 8, 10, tzinfo=UTC),
    )
    assert transport.request_ids == [request.request_id for request in plan.requests]
    assert result.provider_calls == 7
    retained = (
        result.artifact.path.read_bytes(),
        result.ledger.path.read_bytes(),
        result.copy_record.path.read_bytes(),
    )
    assert all(DUMMY_CREDENTIAL.encode() not in value for value in retained)
    assert [
        json.loads(line)["event_type"] for line in result.ledger.path.read_bytes().splitlines()
    ].count("response_validation_passed") == 7


def test_repository_ancestry_failure_stops_before_secret_or_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_runtime_schemas(tmp_path)
    plan = _plan(tmp_path)
    monkeypatch.setattr(runner, "load_inventory_plan_v3", lambda *args, **kwargs: plan)
    transport = FakeTransport(_responses())
    secret_calls = 0
    ancestry_calls: list[dict[str, str]] = []

    def secret_source() -> str:
        nonlocal secret_calls
        secret_calls += 1
        return DUMMY_CREDENTIAL

    def ancestry_failure(repository_root: Path, **kwargs: str) -> None:
        ancestry_calls.append(kwargs)
        raise LambdaCloudContractError("synthetic ancestry failure")

    with pytest.raises(runner.InventoryObservedFailure):
        runner.execute_authorized_inventory_v3(
            repository_root=tmp_path,
            plan_path=tmp_path / "synthetic-plan.json",
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            credential_provider=secret_source,
            transport=transport,
            archiver=FakeArchiverV3(),
            watchdog_factory=lambda seconds: FakeDeadline(),
            repository_inspector=lambda repository_root, expected_commit: runner.RepositoryState(
                branch="phase-1/sira-smoke-lambda",
                commit=expected_commit,
                clean=True,
            ),
            implementation_verifier=lambda repository_root, bound_plan: None,
            ancestry_verifier=ancestry_failure,
            clock=lambda: 0.0,
            monotonic_ns=iter(range(1, 1000)).__next__,
            utc_now=lambda: datetime(2026, 8, 10, tzinfo=UTC),
        )
    assert secret_calls == 0
    assert transport.request_ids == []
    assert ancestry_calls == [{"implementation_commit": "7" * 40, "execution_commit": "7" * 40}]
    events = [
        json.loads(line)
        for line in (tmp_path / plan.ledger_relative_path).read_bytes().splitlines()
    ]
    assert events[0]["event_type"] == "run_preflight_started"
    assert events[-1]["event_type"] == "run_stopped"


def test_implementation_commit_mismatch_stops_before_secret_transport_and_ancestry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_runtime_schemas(tmp_path)
    plan = _plan(tmp_path)
    monkeypatch.setattr(runner, "load_inventory_plan_v3", lambda *args, **kwargs: plan)
    transport = FakeTransport(_responses())
    secret_calls = 0
    ancestry_calls = 0

    def secret_source() -> str:
        nonlocal secret_calls
        secret_calls += 1
        return DUMMY_CREDENTIAL

    def ancestry_must_not_run(repository_root: Path, **kwargs: str) -> None:
        del repository_root, kwargs
        nonlocal ancestry_calls
        ancestry_calls += 1

    drifted_binding = replace(_binding(), implementation_commit="6" * 40)
    with pytest.raises(runner.InventoryObservedFailure):
        runner.execute_authorized_inventory_v3(
            repository_root=tmp_path,
            plan_path=tmp_path / "synthetic-plan.json",
            plan_sha256=PLAN_SHA256,
            run_binding=drifted_binding,
            credential_provider=secret_source,
            transport=transport,
            archiver=FakeArchiverV3(),
            watchdog_factory=lambda seconds: FakeDeadline(),
            repository_inspector=lambda repository_root, expected_commit: runner.RepositoryState(
                branch="phase-1/sira-smoke-lambda",
                commit=expected_commit,
                clean=True,
            ),
            implementation_verifier=lambda repository_root, bound_plan: None,
            ancestry_verifier=ancestry_must_not_run,
            clock=lambda: 0.0,
            monotonic_ns=iter(range(1, 1000)).__next__,
            utc_now=lambda: datetime(2026, 8, 10, tzinfo=UTC),
        )
    assert secret_calls == 0
    assert transport.request_ids == []
    assert ancestry_calls == 0


def test_non_null_pagination_stops_fake_supervisor_without_follow_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_runtime_schemas(tmp_path)
    plan = _plan(tmp_path)
    monkeypatch.setattr(runner, "load_inventory_plan_v3", lambda *args, **kwargs: plan)
    responses = _responses()
    images = json.loads(responses["images"])
    images["page_token"] = "synthetic-next"
    responses["images"] = _encoded(images)
    clock = MutableClock()
    transport = FakeTransport(responses)
    with pytest.raises(LambdaCloudContractError, match="PAGINATION_PRESENT"):
        runner.execute_authorized_inventory_v3(
            repository_root=tmp_path,
            plan_path=tmp_path / "synthetic-plan.json",
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            credential_provider=lambda: DUMMY_CREDENTIAL,
            transport=transport,
            archiver=FakeArchiverV3(),
            watchdog_factory=lambda seconds: FakeDeadline(),
            repository_inspector=lambda repository_root, expected_commit: runner.RepositoryState(
                branch="phase-1/sira-smoke-lambda",
                commit=expected_commit,
                clean=True,
            ),
            implementation_verifier=lambda repository_root, bound_plan: None,
            ancestry_verifier=lambda repository_root, **kwargs: None,
            clock=clock,
            sleeper=clock.sleep,
            monotonic_ns=iter(range(1, 1000)).__next__,
            utc_now=lambda: datetime(2026, 8, 10, tzinfo=UTC),
        )
    assert transport.request_ids == ["instance-types", "images"]
    events = [
        json.loads(line)
        for line in (tmp_path / plan.ledger_relative_path).read_bytes().splitlines()
    ]
    assert events[-2]["event_type"] == "request_failed"
    assert events[-2]["sanitized_failure_class"] == "pagination_present"
    assert events[-1]["event_type"] == "run_stopped"


def test_extension_report_limit_stops_fake_supervisor_before_request_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_runtime_schemas(tmp_path)
    plan = _plan(tmp_path)
    monkeypatch.setattr(runner, "load_inventory_plan_v3", lambda *args, **kwargs: plan)
    responses = _responses()
    first = json.loads(responses["instance-types"])
    first.update({f"future_{index:03d}": index for index in range(129)})
    responses["instance-types"] = _encoded(first)
    clock = MutableClock()
    transport = FakeTransport(responses)
    with pytest.raises(LambdaCloudContractError, match="EXTENSION_REPORT_INELIGIBLE"):
        runner.execute_authorized_inventory_v3(
            repository_root=tmp_path,
            plan_path=tmp_path / "synthetic-plan.json",
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            credential_provider=lambda: DUMMY_CREDENTIAL,
            transport=transport,
            archiver=FakeArchiverV3(),
            watchdog_factory=lambda seconds: FakeDeadline(),
            repository_inspector=lambda repository_root, expected_commit: runner.RepositoryState(
                branch="phase-1/sira-smoke-lambda",
                commit=expected_commit,
                clean=True,
            ),
            implementation_verifier=lambda repository_root, bound_plan: None,
            ancestry_verifier=lambda repository_root, **kwargs: None,
            clock=clock,
            sleeper=clock.sleep,
            monotonic_ns=iter(range(1, 1000)).__next__,
            utc_now=lambda: datetime(2026, 8, 10, tzinfo=UTC),
        )
    assert transport.request_ids == ["instance-types"]
    events = [
        json.loads(line)
        for line in (tmp_path / plan.ledger_relative_path).read_bytes().splitlines()
    ]
    assert events[-2]["event_type"] == "request_failed"
    assert events[-2]["sanitized_failure_class"] == "schema_drift"
    assert events[-1]["event_type"] == "run_stopped"


def test_live_transport_is_not_invoked_by_parser_or_plan_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("external account transport is forbidden in Gate L1.2")

    monkeypatch.setattr(runner.LambdaHttpsInventoryTransportV3, "fetch", forbidden)
    parser, _ = _parsed()
    assert len(parser.observations) == 7


def test_unknown_scalar_canary_is_absent_from_tracked_outputs() -> None:
    for path in (
        ROOT / "docs",
        ROOT / "notebook",
        ROOT / "src",
        ROOT / "schemas",
        ROOT / "containers",
    ):
        for candidate in path.rglob("*"):
            if candidate.is_file() and candidate.stat().st_size <= 5 * 1024 * 1024:
                assert UNKNOWN_VALUE_CANARY.encode() not in candidate.read_bytes()
