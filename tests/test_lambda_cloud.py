from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from giclab.harness.lambda_cloud import (
    API_SPEC_SHA256,
    EXPECTED_INVENTORY_REQUESTS,
    INVENTORY_PLAN_ID,
    MAX_INVENTORY_RETAINED_BYTES,
    FirewallRule,
    HttpMethod,
    InstanceSelectionError,
    Inventory,
    InventoryRunBinding,
    LambdaCloudContractError,
    QualificationLifecycleContract,
    QualificationPhase,
    RunningInstance,
    SelectionFailureCode,
    bind_selected_infrastructure,
    canonical_inventory_bytes,
    inventory_document,
    load_inventory_plan,
    parse_inventory_responses,
    qualification_lifecycle_contract,
    qualification_list_price_cap_cents,
    render_no_filesystem_launch_request,
    select_compute_candidate,
    validate_no_filesystem_launch_request,
    validate_termination_request,
)
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan.json"
PLAN_SHA256 = "c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69"
SOURCE_PATH = ROOT / "containers/sira-smoke/lambda/public-source-observations.json"
SOURCE_SHA256 = "462cf84e08020a89707c55deb6e2a048c53b51241df4ffebf86dec95ae246e82"
FIXTURE_PATH = ROOT / "containers/sira-smoke/lambda/adversarial-containment.sh"
FIXTURE_SHA256 = "09838913b14d23da939225cb89411619e91cb9ee023a2721b5b7c3890ac90aea"
CANARY_PUBLIC_KEY = "ssh-ed25519 PUBLIC-KEY-CANARY-MUST-NOT-SURVIVE"
ACCOUNT_LRN = "lrn:cloud:account:synthetic-account"
WORKSPACE_LRN = "lrn:cloud:workspace:synthetic-workspace"
BUSYBOX_REFERENCE = (
    "busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0"
)
BUSYBOX_CONFIG = "sha256:db287cb6be81219cd18c1d82b70908f5d33eb028568b456f78eedff2ff2930e4"
BUSYBOX_LAYER = "sha256:436a1b1fd078ee8e117111472724c2827077657189af7a781829d0825d48d2ab"


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _region(name: str = "us-test-1") -> dict[str, object]:
    return {"name": name, "description": f"Synthetic {name}"}


def _instance_type(
    name: str,
    *,
    price: int,
    architecture: str = "x86_64",
    vcpus: int = 14,
    memory_gib: int = 46,
    storage_gib: int = 512,
) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Synthetic {name}",
        "gpu_description": "Synthetic GPU",
        "price_cents_per_hour": price,
        "specs": {
            "vcpus": vcpus,
            "memory_gib": memory_gib,
            "storage_gib": storage_gib,
            "gpus": 1,
        },
        "architecture": architecture,
    }


def _audit_event() -> dict[str, object]:
    return {
        "service_name": "cloud",
        "resource_name": "api_key",
        "action": "created",
        "catalog_version": "2025-09-06",
        "event_id": "event-synthetic",
        "event_time": "2026-08-09T00:00:00Z",
        "actor_lrn": "lrn:cloud:identity:synthetic",
        "actor_email": "sensitive@example.invalid",
        "actor_display_name": "Sensitive Actor",
        "resource_lrns": ["lrn:cloud:api_key:synthetic"],
        "resource_owner_lrn": ACCOUNT_LRN,
        "request_api_key_lrn": "lrn:cloud:api_key:synthetic",
        "workspace_lrn": WORKSPACE_LRN,
        "client_ip": "192.0.2.1",
        "client_user_agent": "sensitive-agent",
        "surface": "api",
        "result": {"status": "success", "status_code": 200},
        "additional_details": {"sensitive": "discard-me"},
    }


def _responses() -> dict[str, bytes]:
    types = {
        "gpu_arm_cheap": {
            "instance_type": _instance_type("gpu_arm_cheap", price=50, architecture="arm64"),
            "regions_with_capacity_available": [_region()],
        },
        "gpu_x86_too_small": {
            "instance_type": _instance_type(
                "gpu_x86_too_small", price=60, vcpus=4, memory_gib=8, storage_gib=50
            ),
            "regions_with_capacity_available": [_region()],
        },
        "gpu_1x_a10": {
            "instance_type": _instance_type("gpu_1x_a10", price=129, memory_gib=226),
            "regions_with_capacity_available": [_region()],
        },
        "gpu_1x_rtx6000": {
            "instance_type": _instance_type("gpu_1x_rtx6000", price=69),
            "regions_with_capacity_available": [_region()],
        },
    }
    image = {
        "id": "image-gpu-base-22-04-x86-test",
        "created_time": "2026-08-01T00:00:00Z",
        "updated_time": "2026-08-01T00:00:00Z",
        "name": "GPU Base 22.04 x86 synthetic",
        "description": "Synthetic exact image",
        "family": "gpu-base-22-04",
        "version": "2026.08.01",
        "architecture": "x86_64",
        "region": _region(),
    }
    ssh_rule = {
        "protocol": "tcp",
        "port_range": [22, 22],
        "source_network": "192.0.2.0/24",
        "description": "Synthetic approved SSH",
    }
    regional_ruleset = {
        "id": "firewall-ssh-test",
        "name": "Synthetic SSH only",
        "region": _region(),
        "rules": [ssh_rule],
        "created": "2026-08-01T00:00:00Z",
        "instance_ids": [],
    }
    return {
        "account-workspace-identity": _encoded({"data": [_audit_event()], "page_token": None}),
        "instance-types": _encoded({"data": types}),
        "images": _encoded({"data": [image]}),
        "regions": _encoded({"data": [_region()]}),
        "ssh-keys": _encoded(
            {
                "data": [
                    {
                        "id": "ssh-key-test",
                        "name": "existing-test-key",
                        "public_key": CANARY_PUBLIC_KEY,
                    }
                ]
            }
        ),
        "firewall-rulesets": _encoded({"data": [regional_ruleset]}),
        "global-firewall-ruleset": _encoded(
            {"data": {"id": "global", "name": "Global SSH only", "rules": [ssh_rule]}}
        ),
        "running-instances": _encoded({"data": []}),
    }


def _plan():
    return load_inventory_plan(PLAN_PATH, expected_sha256=PLAN_SHA256)


def _parsed_inventory() -> Inventory:
    return parse_inventory_responses(_responses(), _plan())


def _run_binding() -> InventoryRunBinding:
    return InventoryRunBinding(
        run_id="RUN-T07-L1-LAMBDA-INVENTORY-0001",
        repository_commit="1" * 40,
        authorization_reference="AUTH-T07-L1-TEST",
        authorization_sha256="2" * 64,
    )


def test_committed_l1_plan_is_hash_bound_exact_get_only_and_unauthorized() -> None:
    assert hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest() == PLAN_SHA256
    plan = _plan()
    assert plan.plan_id == INVENTORY_PLAN_ID
    assert plan.run_id == "RUN-T07-L1-LAMBDA-INVENTORY-0001"
    assert plan.api_spec_sha256 == API_SPEC_SHA256
    assert plan.requests == EXPECTED_INVENTORY_REQUESTS
    assert len(plan.requests) == 8
    assert all(request.method is HttpMethod.GET for request in plan.requests)
    assert plan.max_calls == 8
    assert plan.max_total_response_bytes == 2_097_152
    assert plan.max_retained_output_bytes == MAX_INVENTORY_RETAINED_BYTES
    assert plan.max_wall_seconds == 60
    assert plan.automatic_retries == 0
    assert not plan.authorized


def test_public_source_and_fixture_records_are_hash_bound_and_unexecuted() -> None:
    assert hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest() == SOURCE_SHA256
    assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
    source = json.loads(SOURCE_PATH.read_text())
    assert source["account_api_called"] is False
    assert source["payload_downloaded"] is False
    records = {record["record_id"]: record for record in source["records"]}
    busybox = records["BUSYBOX-1.37.0-GLIBC-AMD64"]
    assert busybox["execution_reference"] == BUSYBOX_REFERENCE
    assert busybox["linux_amd64_manifest"]["digest"] == BUSYBOX_REFERENCE.removeprefix("busybox@")
    assert busybox["layers"] == [{"digest": BUSYBOX_LAYER, "compressed_bytes": 2211507}]
    assert records["T07-L2-ADVERSARIAL-FIXTURE"]["executed"] is False


def test_l1_plan_rejects_mutation_extra_endpoint_and_authority(tmp_path: Path) -> None:
    document = json.loads(PLAN_PATH.read_text())
    document["requests"][0]["method"] = "POST"
    document["requests"].append(
        {
            "request_id": "launch",
            "method": "GET",
            "path": "/api/v1/instance-operations/launch",
            "max_response_bytes": 262144,
        }
    )
    document["authorization"]["authorized"] = True
    document["authorization"]["authorization_reference"] = "AUTH-FORGED"
    path = tmp_path / "unsafe.json"
    path.write_text(json.dumps(document))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(LambdaCloudContractError):
        load_inventory_plan(path, expected_sha256=digest)


def test_inventory_parser_redacts_account_audit_ssh_and_instance_secrets() -> None:
    inventory = _parsed_inventory()
    candidate = select_compute_candidate(inventory)
    document = inventory_document(
        inventory,
        candidate,
        observed_at_utc="2026-08-09T21:00:00Z",
        inventory_plan_sha256=PLAN_SHA256,
        run_binding=_run_binding(),
    )
    encoded = canonical_inventory_bytes(document)
    assert len(encoded) <= MAX_INVENTORY_RETAINED_BYTES
    for forbidden in (
        CANARY_PUBLIC_KEY,
        ACCOUNT_LRN,
        WORKSPACE_LRN,
        "sensitive@example.invalid",
        "192.0.2.1",
        "sensitive-agent",
        "discard-me",
        "jupyter_token",
        "Synthetic GPU",
        "Synthetic us-test-1",
        "Synthetic gpu_1x_rtx6000",
    ):
        assert forbidden.encode() not in encoded
    assert b'"public_key":' not in encoded
    assert document["ssh_keys"] == [{"id": "ssh-key-test", "name": "existing-test-key"}]
    assert "description" not in document["firewall_rulesets"][0]["rules"][0]
    assert document["redaction"]["instance_ip_addresses_retained"] is False
    assert document["redaction"]["firewall_source_cidrs_retained"] is True
    assert validate_instance(document, ROOT / "schemas/t07-lambda-inventory.schema.json") == []


def test_inventory_parser_rejects_schema_drift_missing_response_and_oversize() -> None:
    responses = _responses()
    instance_types = json.loads(responses["instance-types"])
    instance_types["unexpected"] = True
    responses["instance-types"] = _encoded(instance_types)
    with pytest.raises(LambdaCloudContractError, match="schema drift"):
        parse_inventory_responses(responses, _plan())

    responses = _responses()
    responses.pop("regions")
    with pytest.raises(LambdaCloudContractError, match="response set"):
        parse_inventory_responses(responses, _plan())

    responses = _responses()
    responses["images"] = b" " * 262_145
    with pytest.raises(LambdaCloudContractError, match="byte cap"):
        parse_inventory_responses(responses, _plan())


def test_inventory_parser_errors_never_echo_provider_controlled_keys() -> None:
    responses = _responses()
    canary = "PROVIDER-KEY-CANARY-MUST-NOT-SURVIVE"
    responses["images"] = f'{{"data":[],"{canary}":1,"{canary}":2}}'.encode()
    with pytest.raises(LambdaCloudContractError) as captured:
        parse_inventory_responses(responses, _plan())
    assert canary not in str(captured.value)

    responses = _responses()
    responses["images"] = f'{{"data":["{canary}"],'.encode()
    with pytest.raises(LambdaCloudContractError) as captured:
        parse_inventory_responses(responses, _plan())
    assert canary not in str(captured.value)
    assert canary not in repr(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None

    responses = _responses()
    responses["instance-types"] = _encoded({"data": {canary: {"invalid": True}}})
    with pytest.raises(LambdaCloudContractError) as captured:
        parse_inventory_responses(responses, _plan())
    assert canary not in str(captured.value)

    responses = _responses()
    responses["images"] = _encoded({"data": [], canary: True})
    with pytest.raises(LambdaCloudContractError) as captured:
        parse_inventory_responses(responses, _plan())
    assert canary not in str(captured.value)


@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
def test_inventory_parser_rejects_nonstandard_json_constants(constant: bytes) -> None:
    responses = _responses()
    responses["images"] = b'{"data":' + constant + b"}"
    with pytest.raises(LambdaCloudContractError, match="strict UTF-8 JSON"):
        parse_inventory_responses(responses, _plan())


def test_inventory_parser_bounds_deep_malformed_json_categorically() -> None:
    responses = _responses()
    responses["images"] = b'{"data":' + b"[" * 20_000 + b"]" * 20_000 + b"}"
    with pytest.raises(LambdaCloudContractError, match="strict UTF-8 JSON"):
        parse_inventory_responses(responses, _plan())


def test_firewall_parser_accepts_known_all_enum_as_unsafe_and_rejects_invalid_cidr() -> None:
    responses = _responses()
    global_document = json.loads(responses["global-firewall-ruleset"])
    global_document["data"]["rules"][0]["protocol"] = "all"
    responses["global-firewall-ruleset"] = _encoded(global_document)
    inventory = parse_inventory_responses(responses, _plan())
    with pytest.raises(InstanceSelectionError) as captured:
        select_compute_candidate(inventory)
    assert captured.value.code is SelectionFailureCode.GLOBAL_FIREWALL_NOT_SSH_ONLY

    responses = _responses()
    regional_document = json.loads(responses["firewall-rulesets"])
    regional_document["data"][0]["rules"][0]["source_network"] = "not-an-ip-network"
    responses["firewall-rulesets"] = _encoded(regional_document)
    with pytest.raises(LambdaCloudContractError, match="valid IPv4 CIDR"):
        parse_inventory_responses(responses, _plan())


def test_account_binding_rejects_missing_or_ambiguous_identity() -> None:
    responses = _responses()
    first = _audit_event()
    second = _audit_event()
    second["workspace_lrn"] = "lrn:cloud:workspace:other"
    responses["account-workspace-identity"] = _encoded(
        {"data": [first, second], "page_token": None}
    )
    with pytest.raises(LambdaCloudContractError, match="exactly one account/workspace"):
        parse_inventory_responses(responses, _plan())


def test_selection_uses_price_then_stable_ties_and_enforces_all_numeric_bounds() -> None:
    inventory = _parsed_inventory()
    candidate = select_compute_candidate(inventory)
    assert candidate.instance_type_name == "gpu_1x_rtx6000"
    assert candidate.architecture == "x86_64"
    assert candidate.price_cents_per_hour == 69
    assert candidate.vcpus >= 8
    assert candidate.memory_gib >= 16
    assert candidate.storage_gib >= 100
    assert candidate.gpus == 1
    assert candidate.image_family == "gpu-base-22-04"
    assert candidate.qualification_list_price_cap_cents == 69
    assert candidate.provider_compute_hard_cap_cents == 200

    tied = replace(
        next(item for item in inventory.instance_types if item.name == "gpu_1x_rtx6000"),
        name="gpu_0_stable_tie",
        price_cents_per_hour=69,
    )
    inventory = replace(inventory, instance_types=(*inventory.instance_types, tied))
    assert select_compute_candidate(inventory).instance_type_name == "gpu_0_stable_tie"


def test_selection_allows_cpu_only_rejects_multi_gpu_and_firewall_unenforced_region() -> None:
    inventory = _parsed_inventory()
    one_offer = next(item for item in inventory.instance_types if item.name == "gpu_1x_rtx6000")
    multi_gpu = replace(one_offer, specs=replace(one_offer.specs, gpus=2))
    with pytest.raises(InstanceSelectionError) as captured:
        select_compute_candidate(replace(inventory, instance_types=(multi_gpu,)))
    assert captured.value.code is SelectionFailureCode.NO_QUALIFYING_CANDIDATE

    cpu_only = replace(
        one_offer,
        name="cpu_x86_qualified",
        price_cents_per_hour=10,
        specs=replace(one_offer.specs, gpus=0),
    )
    selected = select_compute_candidate(replace(inventory, instance_types=(cpu_only,)))
    assert selected.instance_type_name == "cpu_x86_qualified"
    assert selected.gpus == 0

    forbidden_region = replace(inventory.regions[0], name="us-south-1")
    offer = replace(one_offer, capacity_regions=(forbidden_region,))
    image = replace(inventory.images[0], region=forbidden_region)
    rulesets = tuple(
        replace(item, region=forbidden_region) if item.scope == "regional" else item
        for item in inventory.firewall_rulesets
    )
    forbidden_inventory = replace(
        inventory,
        instance_types=(offer,),
        images=(image,),
        regions=(forbidden_region,),
        firewall_rulesets=rulesets,
    )
    with pytest.raises(InstanceSelectionError) as captured:
        select_compute_candidate(forbidden_inventory)
    assert captured.value.code is SelectionFailureCode.NO_QUALIFYING_CANDIDATE


@pytest.mark.parametrize(
    ("field", "value"),
    [("architecture", "arm64"), ("price_cents_per_hour", 151)],
)
def test_selection_stops_when_only_nonqualifying_types_remain(field: str, value: object) -> None:
    inventory = _parsed_inventory()
    only = inventory.instance_types[-1]
    if field == "architecture":
        only = replace(only, architecture=str(value))
    else:
        only = replace(only, price_cents_per_hour=int(value))
    inventory = replace(inventory, instance_types=(only,))
    with pytest.raises(LambdaCloudContractError, match="no currently available"):
        select_compute_candidate(inventory)


def test_selection_rejects_non_ssh_firewall_and_duplicate_t07_instance() -> None:
    inventory = _parsed_inventory()
    global_ruleset = next(item for item in inventory.firewall_rulesets if item.scope == "global")
    unsafe_rule = FirewallRule("tcp", (22, 23), "0.0.0.0/0", "too broad")
    unsafe_global = replace(global_ruleset, rules=(unsafe_rule,))
    inventory = replace(
        inventory,
        firewall_rulesets=tuple(
            unsafe_global if item.scope == "global" else item
            for item in inventory.firewall_rulesets
        ),
    )
    with pytest.raises(LambdaCloudContractError, match="global firewall"):
        select_compute_candidate(inventory)

    inventory = _parsed_inventory()
    duplicate = RunningInstance(
        instance_id="instance-existing-t07",
        name="other-name",
        status="active",
        region_name="us-test-1",
        instance_type_name="gpu_1x_rtx6000",
        file_system_count=0,
        firewall_ruleset_ids=("firewall-ssh-test",),
        t07_owned=True,
    )
    with pytest.raises(LambdaCloudContractError, match="existing T07"):
        select_compute_candidate(replace(inventory, running_instances=(duplicate,)))


def test_typed_selection_failure_still_produces_redacted_hashable_inventory() -> None:
    inventory = _parsed_inventory()
    inventory = replace(
        inventory,
        instance_types=tuple(
            replace(item, price_cents_per_hour=151) for item in inventory.instance_types
        ),
    )
    with pytest.raises(InstanceSelectionError) as captured:
        select_compute_candidate(inventory)
    assert captured.value.code is SelectionFailureCode.NO_QUALIFYING_CANDIDATE
    document = inventory_document(
        inventory,
        None,
        observed_at_utc="2026-08-09T21:00:00Z",
        inventory_plan_sha256=PLAN_SHA256,
        run_binding=_run_binding(),
        selection_failure=captured.value,
    )
    assert document["selection"] == {
        "state": "blocked",
        "reason_code": "no-qualifying-candidate",
        "ssh_key_binding": None,
        "firewall_ruleset_binding": None,
    }
    assert canonical_inventory_bytes(document)
    assert validate_instance(document, ROOT / "schemas/t07-lambda-inventory.schema.json") == []


def test_cost_cap_uses_provider_minute_rounding_without_float_math() -> None:
    assert qualification_list_price_cap_cents(69, 3600) == 69
    assert qualification_list_price_cap_cents(129, 60) == 3
    assert qualification_list_price_cap_cents(129, 61) == 5
    with pytest.raises(LambdaCloudContractError):
        qualification_list_price_cap_cents(69, 0)


def test_exact_binding_launch_and_termination_never_touch_unrelated_resources() -> None:
    inventory = _parsed_inventory()
    candidate = select_compute_candidate(inventory)
    selected = bind_selected_infrastructure(
        inventory,
        candidate,
        approved_ssh_key_id="ssh-key-test",
        approved_ssh_key_name="existing-test-key",
        approved_firewall_ruleset_id="firewall-ssh-test",
    )
    body = render_no_filesystem_launch_request(selected, authorization_reference="AUTH-T07-L2-TEST")
    assert body["file_system_names"] == []
    assert body["file_system_mounts"] == []
    assert "user_data" not in body
    assert "quantity" not in body

    unsafe = dict(body)
    unsafe["file_system_names"] = ["unrelated-filesystem"]
    with pytest.raises(LambdaCloudContractError, match="no filesystem"):
        validate_no_filesystem_launch_request(unsafe, selected)

    forged_candidate = replace(candidate, instance_type_name="invented_type")
    with pytest.raises(LambdaCloudContractError, match="exact inventory selection"):
        bind_selected_infrastructure(
            inventory,
            forged_candidate,
            approved_ssh_key_id="ssh-key-test",
            approved_ssh_key_name="existing-test-key",
            approved_firewall_ruleset_id="firewall-ssh-test",
        )

    unsafe = dict(body)
    unsafe["tags"] = [
        {"key": "giclab.experiment", "value": "EXP-0001"},
        {"key": "giclab.gate", "value": "T07-L2"},
        {"key": "giclab.unreviewed", "value": "forged"},
    ]
    with pytest.raises(LambdaCloudContractError, match="authorization tag"):
        validate_no_filesystem_launch_request(unsafe, selected)

    validate_termination_request(
        {"instance_ids": ["minted-instance"]},
        minted_instance_id="minted-instance",
        unrelated_instance_ids=["unrelated-instance"],
    )
    with pytest.raises(LambdaCloudContractError, match="only the minted"):
        validate_termination_request(
            {"instance_ids": ["unrelated-instance"]},
            minted_instance_id="minted-instance",
            unrelated_instance_ids=["unrelated-instance"],
        )


def test_qualification_lifecycle_requires_termination_on_every_exit() -> None:
    contract = qualification_lifecycle_contract()
    assert contract.phases[-1] is QualificationPhase.TERMINAL_CONFIRMED
    unsafe = QualificationLifecycleContract(
        phases=tuple(QualificationPhase),
        max_launch_requests=1,
        max_termination_targets=1,
        max_termination_requests=3,
        launch_retries=0,
        terminate_by_provider_api=True,
        immutable_instance_id_required=True,
        terminate_on_every_post_launch_exit=False,
        require_terminal_nonbillable_state=True,
    )
    with pytest.raises(LambdaCloudContractError, match="termination coverage"):
        unsafe.validate()


def _valid_host_qualification_evidence() -> dict[str, object]:
    digest = "a" * 64
    request_body = {
        "region_name": "us-test-1",
        "instance_type_name": "gpu_1x_rtx6000",
        "ssh_key_names": ["ssh-name"],
        "file_system_names": [],
        "file_system_mounts": [],
        "name": "giclab-t07-l2-qualification",
        "image": {"id": "image-exact"},
        "tags": [
            {"key": "giclab.experiment", "value": "EXP-0001"},
            {"key": "giclab.gate", "value": "T07-L2"},
            {"key": "giclab.authorization", "value": "AUTH-T07-L2-TEST"},
        ],
        "firewall_rulesets": [{"id": "firewall-id"}],
    }
    request_sha256 = hashlib.sha256(
        json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": "0.1.0",
        "plan_id": "PLAN-T07-GATE-L2-SYNTHETIC",
        "plan_sha256": digest,
        "run_identity": {
            "run_id": "RUN-T07-L2-SYNTHETIC",
            "attempt": 1,
            "experiment_id": "EXP-0001",
            "profile_plan_id": "PLAN-EXP0001-SMOKE",
            "gate": "T07-L2",
            "branch": "phase-1/sira-smoke-lambda",
            "repository_commit": "1" * 40,
        },
        "lifecycle_state": "terminal-confirmed",
        "authorization": {
            "authorized": True,
            "authorization_reference": "AUTH-T07-L2-TEST",
            "authorization_sha256": digest,
        },
        "secret_contract": {
            "variable": "LAMBDA_API_KEY",
            "channel": "supervisor-secret-channel",
            "held_in_memory_through_terminal_confirmation": True,
            "forbidden_locations": ["argv", "url", "log", "evidence", "hash", "filesystem"],
            "forbidden_fallbacks": ["SIRA_API_KEY", "OPENAI_API_KEY"],
            "unavailable_after_launch_action": (
                "stop-workload-open-billing-incident-request-secret-restoration"
            ),
            "leak_scan_clean": True,
        },
        "inventory_binding": {
            "artifact_sha256": digest,
            "account_lrn_sha256": digest,
            "workspace_lrn_sha256": digest,
        },
        "provider_identity": {
            "instance_id": "minted-instance",
            "instance_type_name": "gpu_1x_rtx6000",
            "region_name": "us-test-1",
            "image_id": "image-exact",
            "image_name": "GPU Base 22.04",
            "image_family": "gpu-base-22-04",
            "image_version": "2026.08.01",
            "architecture": "x86_64",
            "ssh_key_id": "ssh-id",
            "ssh_key_name": "ssh-name",
            "firewall_ruleset_id": "firewall-id",
            "accelerator_count": 1,
            "price_cents_per_hour": 69,
        },
        "budget": {
            "max_wall_seconds": 3600,
            "max_provider_compute_cents": 200,
            "max_list_price_cents": 69,
            "persistent_filesystem_cost_cents": 0,
            "model_api_cost_cents": 0,
            "model_tokens": 0,
            "model_calls": 0,
            "browser_actions": 0,
            "sira_executions": 0,
            "automatic_launch_retries": 0,
            "max_retained_evidence_bytes": 67108864,
            "max_accelerator_hours": 1,
            "max_provider_api_calls": 134,
            "minimum_provider_request_start_spacing_seconds": 1,
            "automatic_provider_request_retries": 0,
            "max_provider_api_response_bytes_per_call": 1048576,
            "max_provider_api_response_bytes_aggregate": 16777216,
            "max_ssh_readiness_attempts": 30,
            "max_ssh_sessions": 2,
            "max_remote_commands": 48,
            "max_ssh_command_output_bytes_per_call": 1048576,
            "max_ssh_command_output_bytes_aggregate": 16777216,
            "max_docker_calls": 32,
            "max_docker_output_bytes_per_call": 1048576,
            "max_docker_output_bytes_aggregate": 16777216,
            "max_registry_response_bytes": 8388608,
            "max_docker_disk_delta_bytes": 67108864,
            "minimum_root_free_bytes": 10737418240,
            "minimum_docker_root_free_bytes": 10737418240,
            "max_remote_evidence_bytes": 67108864,
            "max_transfer_bytes": 67108864,
            "max_mac_active_evidence_bytes": 67108864,
            "max_sealed_copy_bytes": 67108864,
            "max_ssh_transfer_calls": 1,
            "max_archive_copy_calls": 1,
            "minimum_mac_active_prewrite_free_bytes": 8725200896,
            "minimum_mac_active_retained_free_bytes": 8589934592,
            "max_mac_active_incremental_bytes": 135266304,
        },
        "provider_request_pacing": {
            "clock": "monotonic",
            "minimum_start_spacing_seconds": 1,
            "request_start_count": 20,
            "minimum_observed_start_spacing_milliseconds": 1000,
            "spacing_violations": 0,
            "aggregate_deadline_minted_before_first_request": True,
            "launch_deadline_did_not_extend_aggregate": True,
            "all_spacing_delay_counted_inside_aggregate_deadline": True,
        },
        "launch": {
            "request_sha256": request_sha256,
            "request_body": request_body,
            "minted_instance_id": "minted-instance",
            "file_system_names": [],
            "file_system_mounts": [],
            "launch_count": 1,
            "instance_id_captured_immediately": True,
            "deadline_minted_before_launch_post": True,
            "launch_request_started_monotonic_ns": 1000000,
            "provider_active_observed_at_utc": "2026-08-09T21:01:00Z",
        },
        "ssh_trust": {
            "attempt_known_hosts_path": (
                "artifacts/t07/lambda/gate-l2/RUN-T07-L2-SYNTHETIC/known_hosts"
            ),
            "global_known_hosts_mutated": False,
            "host_key_algorithm": "ssh-ed25519",
            "host_key_sha256": "SHA256:" + "A" * 43,
            "trust_bootstrap_method": "separately-authorized-provider-attested-fingerprint",
            "provider_attested_or_separately_authorized": True,
            "ssh_keyscan_only": False,
        },
        "host_observation": {
            "os_release": "Ubuntu 22.04",
            "kernel": "synthetic",
            "architecture": "x86_64",
            "cgroup_version": "v2",
            "cgroup_driver": "systemd",
            "docker_client": "synthetic",
            "docker_server": "synthetic",
            "containerd": "synthetic",
            "runc": "synthetic",
            "buildkit_or_buildx": None,
            "root_filesystem_capacity_bytes": 107374182400,
            "root_filesystem_free_bytes": 100000000000,
            "docker_root_capacity_bytes": 107374182400,
            "docker_root_free_bytes": 100000000000,
            "preexisting_container_ids": [],
            "preexisting_image_ids": [],
            "preexisting_network_ids": ["bridge", "host", "none"],
            "preexisting_volume_names": [],
            "docker_service_state": "active",
            "docker_cgroupns_default": "private",
            "docker_init_supported": True,
            "host_mutation_performed": False,
        },
        "containment_probe": {
            "image_reference": BUSYBOX_REFERENCE,
            "image_id": BUSYBOX_CONFIG,
            "config_digest": BUSYBOX_CONFIG,
            "layer_digest": BUSYBOX_LAYER,
            "container_id": "container-exact",
            "network_mode": "none",
            "pid_mode": "private",
            "cgroupns_mode": "private",
            "ipc_mode": "private",
            "privileged": False,
            "cap_drop": ["ALL"],
            "no_new_privileges": True,
            "read_only_root": True,
            "writable_layer_bytes": 0,
            "runtime_socket_mounted": False,
            "cap_add": [],
            "devices": [],
            "host_bind_mounts": [],
            "init_enabled": True,
            "cpu_limit": 1.0,
            "memory_bytes": 134217728,
            "memory_swap_bytes": 134217728,
            "pid_limit": 64,
            "tmpfs_bytes": 20971520,
            "shm_bytes": 16777216,
            "wall_seconds": 30,
            "output_bytes": 1048576,
            "restart_policy": "no",
            "log_driver": "local",
            "log_max_size_bytes": 1048576,
            "log_max_files": 1,
            "labels": {
                "experiment": "EXP-0001",
                "gate": "T07-L2",
                "attempt": "RUN-T07-L2-SYNTHETIC",
                "authorization": "AUTH-T07-L2-TEST",
                "image_manifest": BUSYBOX_REFERENCE.removeprefix("busybox@"),
                "repository_commit": "1" * 40,
                "provider_instance_id": "minted-instance",
                "fixture_sha256": FIXTURE_SHA256,
            },
            "pre_stop_process_evidence": {
                "sha256": digest,
                "capture_method": "docker-top-plus-fixture-log-no-exec",
                "docker_top_sha256": digest,
                "fixture_log_sha256": digest,
                "container_exec_calls": 0,
                "process_count": 64,
                "child_observed": True,
                "grandchild_observed": True,
                "setsid_observed": True,
                "reparent_observed": True,
                "term_ignored_observed": True,
                "pid_limit_observed": True,
                "container_init_pid_1_observed": True,
            },
            "post_kill_inspect_sha256": digest,
            "owned_resource_scan_sha256": digest,
            "applet_verification": {
                "command": ["/bin/busybox", "--list"],
                "required_applets": ["sh", "setsid", "sleep", "ps", "kill"],
                "all_required_present": True,
                "verification_marker": "T07_APPLETS_VERIFIED=sh,setsid,sleep,ps,kill",
                "fixture_source_sha256": FIXTURE_SHA256,
            },
            "stop_timeout_seconds": 5,
            "stop_attempted": True,
            "kill_escalated": True,
            "terminal_or_removed": True,
            "residual_owned_resources": 0,
        },
        "local_active_storage": {
            "relative_root": "artifacts/t07/lambda/gate-l2/RUN-T07-L2-SYNTHETIC",
            "filesystem_type": "apfs",
            "fresh_preflight_utc": "2026-08-09T21:00:00Z",
            "writable": True,
            "user_owned": True,
            "no_symlink_traversal": True,
            "runtime_state_present": False,
            "operational_headroom_bytes": 8589934592,
            "max_incremental_bytes": 135266304,
            "required_prewrite_free_bytes": 8725200896,
            "observed_prewrite_free_bytes": 12000000000,
            "retained_free_floor_bytes": 8589934592,
            "observed_postseal_free_bytes": 11800000000,
        },
        "evidence_copy": {
            "source_retained_until_verified": True,
            "source_sha256": digest,
            "destination_sha256": digest,
            "hashes_match": True,
            "bytes": 1024,
            "max_bytes": 67108864,
        },
        "archive_copy": {
            "mount_path": "/Volumes/Macintosh HD - Data",
            "apfs_data_uuid": "8478609D-FA37-4ED5-875D-47AE912B9151",
            "physical_store_uuid": "7904A6F1-F483-4ED7-9E34-BFECAB31C63E",
            "fresh_identity_guard": True,
            "fresh_observation_utc": "2026-08-09T21:30:00Z",
            "held_descriptor_guard": True,
            "writable_unlocked": True,
            "no_symlink_traversal": True,
            "one_way_copy": True,
            "source_retained_until_verified": True,
            "source_sha256": digest,
            "destination_sha256": digest,
            "container_capacity_bytes": 1000240963584,
            "retained_free_floor_bytes": 200048192717,
            "required_pre_copy_free_bytes": 200115301581,
            "observed_pre_copy_free_bytes": 854038691840,
            "observed_post_copy_free_bytes": 853000000000,
            "bytes": 1024,
            "fsync_complete": True,
            "atomic_finalize": True,
        },
        "termination": {
            "method": "provider-api",
            "instance_ids": ["minted-instance"],
            "request_count": 1,
            "terminal_state": "terminated",
            "provider_nonbillable_confirmed": True,
            "unrelated_instance_ids_touched": [],
        },
        "actual_usage": {
            "provider_wall_seconds": 600,
            "billed_minutes": 10,
            "estimated_list_cost_cents": 12,
            "provider_api_calls": 20,
            "provider_api_response_bytes": 100000,
            "ssh_readiness_attempts": 1,
            "ssh_sessions": 2,
            "remote_commands": 20,
            "ssh_command_output_bytes": 100000,
            "docker_calls": 12,
            "docker_output_bytes": 100000,
            "registry_response_bytes": 2212576,
            "docker_disk_delta_bytes": 4194304,
            "fixture_output_bytes": 65536,
            "remote_evidence_bytes": 1024,
            "transfer_bytes": 1024,
            "mac_active_evidence_bytes": 1024,
            "sealed_copy_bytes": 1024,
            "ssh_transfer_calls": 1,
            "archive_copy_calls": 1,
            "allocated_accelerator_seconds": 600,
            "allocated_accelerator_hours": {"numerator": 600, "denominator": 3600},
        },
        "compute_ledger": {
            "path": "manifests/compute.yaml",
            "record_id": "COMPUTE-T07-L2-SYNTHETIC",
            "run_id": "RUN-T07-L2-SYNTHETIC",
            "append_only": True,
            "terminal_reconciled": True,
            "estimated_list_cost_cents": 12,
            "allocated_accelerator_hours": {"numerator": 600, "denominator": 3600},
            "manifest_sha256": digest,
        },
    }


def test_host_qualification_schema_requires_no_filesystem_and_terminal_cleanup() -> None:
    evidence = _valid_host_qualification_evidence()
    schema = ROOT / "schemas/t07-lambda-host-qualification.schema.json"
    assert validate_instance(evidence, schema) == []

    evidence["launch"]["file_system_names"] = ["forbidden"]
    evidence["termination"]["provider_nonbillable_confirmed"] = False
    errors = validate_instance(evidence, schema)
    assert any("forbidden" in error for error in errors)
    assert any("True was expected" in error for error in errors)


@pytest.mark.parametrize(
    ("path", "value", "expected"),
    [
        (("authorization", "authorized"), False, "True was expected"),
        (("termination", "instance_ids"), ["different-instance"], "minted instance ID"),
        (("evidence_copy", "destination_sha256"), "b" * 64, "SHA-256 values differ"),
        (("containment_probe", "kill_escalated"), False, "True was expected"),
        (("actual_usage", "estimated_list_cost_cents"), 13, "does not match list price"),
        (
            ("provider_request_pacing", "minimum_observed_start_spacing_milliseconds"),
            999,
            "less than the minimum of 1000",
        ),
    ],
)
def test_host_qualification_success_semantics_reject_contradictory_evidence(
    path: tuple[str, str], value: object, expected: str
) -> None:
    evidence = _valid_host_qualification_evidence()
    section = evidence[path[0]]
    assert isinstance(section, dict)
    section[path[1]] = value
    errors = validate_instance(evidence, ROOT / "schemas/t07-lambda-host-qualification.schema.json")
    assert any(expected in error for error in errors)


def test_host_qualification_success_cross_links_run_archive_and_compute() -> None:
    schema = ROOT / "schemas/t07-lambda-host-qualification.schema.json"
    evidence = _valid_host_qualification_evidence()
    evidence["containment_probe"]["labels"]["attempt"] = "RUN-T07-L2-DIFFERENT"
    evidence["archive_copy"]["destination_sha256"] = "b" * 64
    evidence["compute_ledger"]["run_id"] = "RUN-T07-L2-DIFFERENT"
    errors = validate_instance(evidence, schema)
    assert any("labels.attempt" in error for error in errors)
    assert any("archive_copy" in error for error in errors)
    assert any("compute_ledger.run_id" in error for error in errors)


def test_host_qualification_success_rejects_raw_output_counter_overrun() -> None:
    evidence = _valid_host_qualification_evidence()
    evidence["actual_usage"]["provider_api_response_bytes"] = 16_777_217
    errors = validate_instance(evidence, ROOT / "schemas/t07-lambda-host-qualification.schema.json")
    assert any("provider_api_response_bytes" in error for error in errors)


def _valid_host_qualification_incident() -> dict[str, object]:
    digest = "a" * 64
    rational = {"numerator": 600, "denominator": 3600}
    return {
        "schema_version": "0.1.0",
        "plan_id": "PLAN-T07-GATE-L2-SYNTHETIC",
        "plan_sha256": digest,
        "run_identity": {
            "run_id": "RUN-T07-L2-SYNTHETIC",
            "attempt": 1,
            "experiment_id": "EXP-0001",
            "profile_plan_id": "PLAN-EXP0001-SMOKE",
            "gate": "T07-L2",
            "branch": "phase-1/sira-smoke-lambda",
            "repository_commit": "1" * 40,
        },
        "outcome": "failed",
        "authorization": {
            "authorized": True,
            "authorization_reference": "AUTH-T07-L2-TEST",
            "authorization_sha256": digest,
        },
        "secret_contract": {
            "variable": "LAMBDA_API_KEY",
            "channel": "supervisor-secret-channel",
            "forbidden_locations": ["argv", "url", "log", "evidence", "hash", "filesystem"],
            "forbidden_fallbacks": ["SIRA_API_KEY", "OPENAI_API_KEY"],
            "available_through_terminal_confirmation": True,
            "loss_response": "not-applicable",
            "leak_scan_clean": True,
        },
        "inventory_binding": {
            "artifact_sha256": digest,
            "account_lrn_sha256": digest,
            "workspace_lrn_sha256": digest,
        },
        "failure": {
            "phase": "containment",
            "category": "containment-failed",
            "safe_detail_code": "PID-LIMIT-NOT-OBSERVED",
        },
        "resource_contract": {
            "wall_seconds": 3600,
            "compute_cents": 200,
            "provider_api_calls": 134,
            "minimum_provider_request_start_spacing_seconds": 1,
            "automatic_provider_request_retries": 0,
            "provider_api_response_bytes_per_call": 1048576,
            "provider_api_response_bytes_aggregate": 16777216,
            "ssh_readiness_attempts": 30,
            "ssh_sessions": 2,
            "remote_commands": 48,
            "ssh_command_output_bytes_per_call": 1048576,
            "ssh_command_output_bytes_aggregate": 16777216,
            "docker_calls": 32,
            "docker_output_bytes_per_call": 1048576,
            "docker_output_bytes_aggregate": 16777216,
            "registry_response_bytes": 8388608,
            "docker_disk_delta_bytes": 67108864,
            "retained_evidence_bytes": 67108864,
            "mac_active_prewrite_free_bytes": 8725200896,
            "mac_active_retained_free_bytes": 8589934592,
            "mac_active_incremental_bytes": 135266304,
            "external_archive_copy_bytes": 67108864,
            "automatic_launch_retries": 0,
            "model_calls": 0,
            "browser_actions": 0,
            "sira_executions": 0,
        },
        "provider_request_pacing": {
            "clock": "monotonic",
            "minimum_start_spacing_seconds": 1,
            "request_start_count": 20,
            "minimum_observed_start_spacing_milliseconds": 1000,
            "spacing_violations": 0,
            "state": "compliant",
            "aggregate_deadline_minted_before_first_request": True,
            "launch_deadline_did_not_extend_aggregate": True,
            "all_spacing_delay_counted_inside_aggregate_deadline": True,
        },
        "lifecycle": {
            "launch_requests": 1,
            "launch_outcome": "response-with-id",
            "deadline_minted_before_launch_post": True,
            "minted_instance_id": "minted-instance",
            "recovery_lookup_attempted": False,
            "recovery_match_instance_ids": [],
            "termination_required": True,
            "termination_target_ids": ["minted-instance"],
            "termination_requests": 1,
            "terminal_state": "terminated",
            "provider_nonbillable_confirmed": True,
            "billing_incident_open": False,
            "evidence_copy_state": "failed",
            "remote_source_retained": True,
            "local_source_retained": False,
            "cleanup_state": "complete",
            "unrelated_instance_ids_touched": [],
        },
        "actual_usage": {
            "provider_wall_seconds": 600,
            "estimated_list_cost_cents": 12,
            "provider_api_calls": 20,
            "provider_api_response_bytes": 100000,
            "ssh_readiness_attempts": 1,
            "ssh_sessions": 1,
            "remote_commands": 10,
            "ssh_command_output_bytes": 100000,
            "docker_calls": 8,
            "docker_output_bytes": 100000,
            "registry_response_bytes": 2212576,
            "docker_disk_delta_bytes": 4194304,
            "retained_evidence_bytes": 512,
            "transfer_bytes": 0,
            "accelerator_count": 1,
            "allocated_accelerator_seconds": 600,
            "allocated_accelerator_hours": rational,
        },
        "storage_observation": {
            "mac_active": {
                "operational_headroom_bytes": 8589934592,
                "max_incremental_bytes": 135266304,
                "required_prewrite_free_bytes": 8725200896,
                "observed_prewrite_free_bytes": 12000000000,
                "preflight_passed": True,
                "retained_free_floor_bytes": 8589934592,
                "observed_postseal_free_bytes": 11800000000,
            },
            "external_archive": {
                "state": "not-attempted",
                "container_capacity_bytes": None,
                "retained_free_floor_bytes": None,
                "required_pre_copy_free_bytes": None,
                "observed_pre_copy_free_bytes": None,
                "observed_post_copy_free_bytes": None,
                "bytes": 0,
            },
        },
        "retained_evidence": {
            "failure_detail_artifact_sha256": digest,
            "remote_manifest_sha256": digest,
            "source_sha256": digest,
            "destination_sha256": None,
            "files": 1,
            "bytes": 512,
        },
        "compute_ledger": {
            "path": "manifests/compute.yaml",
            "record_id": "COMPUTE-T07-L2-SYNTHETIC",
            "run_id": "RUN-T07-L2-SYNTHETIC",
            "append_only": True,
            "disposition": "terminal-reconciled-failure",
            "estimated_list_cost_cents": 12,
            "allocated_accelerator_hours": rational,
            "manifest_sha256": digest,
        },
        "redaction": {
            "api_keys_retained": False,
            "ssh_private_material_retained": False,
            "raw_authorization_headers_retained": False,
        },
    }


def test_host_qualification_incident_schema_preserves_partial_failure_truth() -> None:
    schema = ROOT / "schemas/t07-lambda-host-qualification-incident.schema.json"
    evidence = _valid_host_qualification_incident()
    assert validate_instance(evidence, schema) == []

    pacing_incident = deepcopy(evidence)
    pacing_incident["provider_request_pacing"]["minimum_observed_start_spacing_milliseconds"] = 900
    pacing_incident["provider_request_pacing"]["spacing_violations"] = 1
    pacing_incident["provider_request_pacing"]["state"] = "violated"
    assert validate_instance(pacing_incident, schema) == []

    unsafe = deepcopy(evidence)
    unsafe["provider_request_pacing"]["minimum_observed_start_spacing_milliseconds"] = 900
    unsafe["provider_request_pacing"]["state"] = "violated"
    assert any(
        "minimum spacing contradicts violation count" in error
        for error in validate_instance(unsafe, schema)
    )

    unsafe = deepcopy(evidence)
    unsafe["provider_request_pacing"]["spacing_violations"] = 1
    unsafe["provider_request_pacing"]["state"] = "violated"
    assert any(
        "minimum spacing contradicts violation count" in error
        for error in validate_instance(unsafe, schema)
    )

    unsafe = deepcopy(evidence)
    unsafe["actual_usage"]["provider_api_calls"] = 2
    unsafe["provider_request_pacing"]["request_start_count"] = 2
    unsafe["provider_request_pacing"]["spacing_violations"] = 2
    unsafe["provider_request_pacing"]["state"] = "violated"
    assert any("exceeds interval count" in error for error in validate_instance(unsafe, schema))

    unsafe = deepcopy(evidence)
    unsafe["provider_request_pacing"]["request_start_count"] = 19
    assert any("does not match API usage" in error for error in validate_instance(unsafe, schema))

    unsafe = deepcopy(evidence)
    unsafe["provider_request_pacing"]["aggregate_deadline_minted_before_first_request"] = False
    assert any("armed too late" in error for error in validate_instance(unsafe, schema))

    unsafe = deepcopy(evidence)
    unsafe["lifecycle"]["termination_target_ids"] = ["unrelated-instance"]
    assert any("minted instance" in error for error in validate_instance(unsafe, schema))

    unsafe = deepcopy(evidence)
    unsafe["lifecycle"]["terminal_state"] = "unknown"
    unsafe["lifecycle"]["provider_nonbillable_confirmed"] = False
    assert any("open billing incident" in error for error in validate_instance(unsafe, schema))

    open_incident = deepcopy(evidence)
    open_incident["failure"] = {
        "phase": "terminal-verification",
        "category": "terminal-state-unconfirmed",
        "safe_detail_code": "PROVIDER-TERMINAL-STATE-UNCONFIRMED",
    }
    open_incident["lifecycle"]["terminal_state"] = "unknown"
    open_incident["lifecycle"]["provider_nonbillable_confirmed"] = False
    open_incident["lifecycle"]["billing_incident_open"] = True
    open_incident["lifecycle"]["termination_requests"] = 3
    open_incident["actual_usage"]["provider_wall_seconds"] = 4000
    open_incident["actual_usage"]["estimated_list_cost_cents"] = None
    open_incident["actual_usage"]["allocated_accelerator_seconds"] = 4000
    open_incident["actual_usage"]["allocated_accelerator_hours"] = {
        "numerator": 4000,
        "denominator": 3600,
    }
    open_incident["compute_ledger"]["disposition"] = "billing-incident-open"
    open_incident["compute_ledger"]["estimated_list_cost_cents"] = None
    open_incident["compute_ledger"]["allocated_accelerator_hours"] = {
        "numerator": 4000,
        "denominator": 3600,
    }
    assert validate_instance(open_incident, schema) == []

    secret_loss = deepcopy(open_incident)
    secret_loss["failure"] = {
        "phase": "control-plane",
        "category": "unexpected-control-plane-failure",
        "safe_detail_code": "LAMBDA-CONTROL-SECRET-UNAVAILABLE",
    }
    secret_loss["secret_contract"]["available_through_terminal_confirmation"] = False
    secret_loss["secret_contract"]["loss_response"] = (
        "stop-workload-open-billing-incident-request-secret-restoration"
    )
    assert validate_instance(secret_loss, schema) == []

    ambiguous = deepcopy(open_incident)
    ambiguous["failure"] = {
        "phase": "instance-id-capture",
        "category": "instance-id-missing",
        "safe_detail_code": "LAUNCH-RESPONSE-AMBIGUOUS",
    }
    ambiguous["lifecycle"]["launch_outcome"] = "response-ambiguous"
    ambiguous["lifecycle"]["minted_instance_id"] = None
    ambiguous["lifecycle"]["recovery_lookup_attempted"] = True
    ambiguous["lifecycle"]["recovery_match_instance_ids"] = []
    ambiguous["lifecycle"]["termination_required"] = True
    ambiguous["lifecycle"]["termination_target_ids"] = []
    ambiguous["lifecycle"]["termination_requests"] = 0
    assert validate_instance(ambiguous, schema) == []
