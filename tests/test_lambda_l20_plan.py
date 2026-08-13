from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from harness_test_support import T07_FROZEN_EXECUTION_COMMIT, git_blob_sha256

from giclab.harness.lambda_cloud import BUSYBOX_REFERENCE
from giclab.harness.lambda_l20_plan import (
    AUTHORIZATION_PLACEHOLDER,
    BRANCH,
    CONTAINMENT_FIXTURE_PATH,
    CONTAINMENT_FIXTURE_SHA256,
    MAX_PROVIDER_API_CALLS,
    PLAN_ID,
    RUN_ID,
    GateL2Event,
    GateL2Phase,
    GateL2State,
    L20ContractError,
    PrivateBindingSeal,
    canonical_bytes,
    ed25519_fingerprint,
    exact_limits,
    load_human_decision,
    prepare_host_key_checkpoint_wait,
    provider_operations,
    render_container_create_argv,
    render_global_restore_body,
    render_launch_body,
    render_public_plan,
    render_ssh_argv,
    render_terminate_body,
    require_unique_agent_match,
    resolve_owned_instance_id,
    resolve_owned_regional_ruleset_id,
    transition_gate_l2,
    validate_fresh_prelaunch_responses,
    validate_host_key_checkpoint,
    validate_human_decision_document,
    validate_public_plan,
    verified_known_hosts_line,
)

ROOT = Path(__file__).resolve().parents[1]
DUMMY_FINGERPRINT = "SHA256:" + "A" * 43


def decision_document(*, nonce: str = "ab" * 32, cidr: str = "8.8.8.8/32") -> dict[str, object]:
    return {
        "schema_version": "0.1.0",
        "decision_id": "T07-L2-HUMAN-DECISION-TEST",
        "decision_nonce": nonce,
        "selected_instance_type": "gpu_1x_a10",
        "selected_region": "us-east-1",
        "selected_image_alias": "img-0111",
        "expected_image_version": "22.4.5-2141",
        "selected_ssh_key_name": "fractal-lambda-codex",
        "ssh_private_access_mode": "preloaded-ssh-agent",
        "firewall_strategy": "temporary-global-ssh-only-plus-regional-ssh-only",
        "source_ipv4_cidr": cidr,
        (
            "attest_no_other_workspace_resource_depends_on_current_global_inbound_rules_"
            "during_window"
        ): True,
        "host_key_trust_method": "lambda-jupyter-independent-ed25519-fingerprint",
        "max_provider_wall_seconds": 3600,
        "max_provider_cost_usd": 2.0,
        "max_host_key_checkpoint_seconds": 600,
        "persistent_filesystem": None,
        "approve_unique_ssh_key_match": True,
        "approve_no_persistent_filesystem": True,
        "notes": "synthetic fixture",
    }


def private_binding() -> PrivateBindingSeal:
    return PrivateBindingSeal(
        root=ROOT / "artifacts/t07/lambda/gate-l2-0" / RUN_ID / "parameters-v2",
        decision_alias="l2-decision-0123456789ab",
        decision_sha256="1" * 64,
        decision_seal_sha256="2" * 64,
        parameters_sha256="3" * 64,
        parameters_seal_sha256="4" * 64,
        bundle_seal_sha256="5" * 64,
        total_bytes=4096,
        external_archive_path=(
            "/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts/"
            "RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001-PRIVATE-PARAMETERS-V2"
        ),
        external_archive_seal_sha256="6" * 64,
        external_copy_record_sha256="7" * 64,
    )


def render_plan() -> dict[str, object]:
    return render_public_plan(
        ROOT,
        implementation_commit="a" * 40,
        binding=private_binding(),
        implementation_hashes={"src/giclab/harness/lambda_l20_plan.py": "b" * 64},
    )


def _ed25519_line(host: str = "8.8.8.8") -> tuple[str, str]:
    algorithm = b"ssh-ed25519"
    key = bytes(range(32))
    blob = len(algorithm).to_bytes(4, "big") + algorithm + len(key).to_bytes(4, "big") + key
    body = base64.b64encode(blob).decode()
    line = f"{host} ssh-ed25519 {body}"
    return line, ed25519_fingerprint(line)


def test_private_decision_document_accepts_exact_contract() -> None:
    validate_human_decision_document(decision_document())


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("selected_instance_type", "gpu_2x_a10"),
        ("selected_ssh_key_name", "another-key"),
        ("max_provider_wall_seconds", 3601),
        ("max_provider_cost_usd", 2.01),
        ("persistent_filesystem", "some-filesystem"),
        ("approve_unique_ssh_key_match", False),
    ],
)
def test_private_decision_mismatch_stops(key: str, value: object) -> None:
    document = decision_document()
    document[key] = value
    with pytest.raises(L20ContractError):
        validate_human_decision_document(document)


@pytest.mark.parametrize(
    "cidr",
    ["8.8.8.8/24", "127.0.0.1/32", "10.0.0.1/32", "192.0.2.1/32", "not-an-ip"],
)
def test_private_decision_requires_global_ipv4_32(cidr: str) -> None:
    with pytest.raises(L20ContractError):
        validate_human_decision_document(decision_document(cidr=cidr))


def test_private_decision_hash_is_nonce_protected_and_fixture_dictionary_cannot_recover() -> None:
    first = canonical_bytes(decision_document(nonce="11" * 32))
    second = canonical_bytes(decision_document(nonce="22" * 32))
    assert hashlib.sha256(first).digest() != hashlib.sha256(second).digest()
    private_nonce = hashlib.sha256(b"synthetic-nonce-not-in-public-fixture").hexdigest()
    target = hashlib.sha256(canonical_bytes(decision_document(nonce=private_nonce))).hexdigest()
    guesses = (
        hashlib.sha256(canonical_bytes(decision_document(nonce=f"{value:04x}" * 16))).hexdigest()
        for value in range(4096)
    )
    assert target not in guesses


def test_private_decision_file_mode_owner_and_nofollow(tmp_path: Path) -> None:
    path = tmp_path / "decision.json"
    path.write_bytes(canonical_bytes(decision_document()))
    path.chmod(0o600)
    loaded = load_human_decision(ROOT, path=path)
    assert loaded.bytes == path.stat().st_size
    assert loaded.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()

    path.chmod(0o644)
    with pytest.raises(L20ContractError):
        load_human_decision(ROOT, path=path)


def test_private_decision_symlink_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(canonical_bytes(decision_document()))
    target.chmod(0o600)
    alias = tmp_path / "alias.json"
    alias.symlink_to(target)
    with pytest.raises(L20ContractError):
        load_human_decision(ROOT, path=alias)


@pytest.mark.parametrize("observed", [[], [DUMMY_FINGERPRINT, DUMMY_FINGERPRINT]])
def test_agent_zero_or_multiple_match_stops(observed: list[str]) -> None:
    with pytest.raises(L20ContractError):
        require_unique_agent_match(observed, DUMMY_FINGERPRINT)


def test_agent_one_match_passes_without_private_key_material() -> None:
    assert (
        require_unique_agent_match(["SHA256:" + "B" * 43, DUMMY_FINGERPRINT], DUMMY_FINGERPRINT)
        == DUMMY_FINGERPRINT
    )


def test_launch_send_is_single_use_and_unknown_outcome_not_replayable() -> None:
    state = GateL2State()
    state = transition_gate_l2(state, GateL2Event.GLOBAL_PATCH_SEND_STARTED)
    state = transition_gate_l2(state, GateL2Event.GLOBAL_REPLACEMENT_VERIFIED)
    state = transition_gate_l2(state, GateL2Event.REGIONAL_CREATE_SEND_STARTED)
    state = transition_gate_l2(
        state,
        GateL2Event.REGIONAL_ID_OBSERVED,
        ruleset_id="ruleset-a",
    )
    state = transition_gate_l2(state, GateL2Event.REGIONAL_RULESET_VERIFIED)
    state = transition_gate_l2(state, GateL2Event.LAUNCH_SEND_STARTED)
    assert state.phase is GateL2Phase.LAUNCH_OUTCOME_UNKNOWN
    with pytest.raises(L20ContractError):
        transition_gate_l2(state, GateL2Event.LAUNCH_SEND_STARTED)


def test_regional_create_unknown_requires_single_owned_name_recovery() -> None:
    state = GateL2State()
    state = transition_gate_l2(state, GateL2Event.GLOBAL_PATCH_SEND_STARTED)
    state = transition_gate_l2(state, GateL2Event.GLOBAL_REPLACEMENT_VERIFIED)
    state = transition_gate_l2(state, GateL2Event.REGIONAL_CREATE_SEND_STARTED)
    assert state.phase is GateL2Phase.REGIONAL_CREATE_OUTCOME_UNKNOWN
    aborted = transition_gate_l2(state, GateL2Event.ABORT)
    assert aborted.phase is GateL2Phase.INCIDENT
    state = transition_gate_l2(
        state,
        GateL2Event.REGIONAL_RECOVERY_OBSERVED,
        ruleset_id="ruleset-a",
    )
    assert state.regional_recovery_requests == 1
    assert state.owned_regional_ruleset_id == "ruleset-a"
    with pytest.raises(L20ContractError):
        transition_gate_l2(
            replace(state, phase=GateL2Phase.REGIONAL_CREATE_OUTCOME_UNKNOWN),
            GateL2Event.REGIONAL_RECOVERY_OBSERVED,
            ruleset_id="ruleset-a",
        )


def test_launch_one_response_one_identity_and_active_poll() -> None:
    state = GateL2State()
    for event in (
        GateL2Event.GLOBAL_PATCH_SEND_STARTED,
        GateL2Event.GLOBAL_REPLACEMENT_VERIFIED,
        GateL2Event.REGIONAL_CREATE_SEND_STARTED,
    ):
        state = transition_gate_l2(state, event)
    state = transition_gate_l2(
        state,
        GateL2Event.REGIONAL_ID_OBSERVED,
        ruleset_id="ruleset-a",
    )
    for event in (
        GateL2Event.REGIONAL_RULESET_VERIFIED,
        GateL2Event.LAUNCH_SEND_STARTED,
    ):
        state = transition_gate_l2(state, event)
    state = transition_gate_l2(state, GateL2Event.INSTANCE_ID_OBSERVED, instance_id="instance-a")
    state = transition_gate_l2(state, GateL2Event.ACTIVE_OBSERVED)
    assert state.phase is GateL2Phase.INSTANCE_ACTIVE
    assert state.owned_instance_id == "instance-a"


@pytest.mark.parametrize(
    "event",
    [GateL2Event.ACTIVE_ERROR_OBSERVED, GateL2Event.ACTIVE_POLL_TIMEOUT],
)
def test_active_error_or_timeout_requires_termination(event: GateL2Event) -> None:
    state = GateL2State(
        phase=GateL2Phase.INSTANCE_OWNED,
        launch_requests=1,
        owned_instance_id="instance-a",
        global_mutated=True,
        regional_created=True,
        owned_regional_ruleset_id="ruleset-a",
    )
    state = transition_gate_l2(state, event)
    assert state.phase is GateL2Phase.TERMINATION_REQUIRED


def test_ambiguity_recovery_is_single_use() -> None:
    state = GateL2State(
        phase=GateL2Phase.LAUNCH_OUTCOME_UNKNOWN,
        launch_requests=1,
    )
    state = transition_gate_l2(
        state,
        GateL2Event.AMBIGUITY_RECOVERY_OBSERVED,
        instance_id="instance-a",
    )
    assert state.ambiguity_recovery_requests == 1
    with pytest.raises(L20ContractError):
        transition_gate_l2(
            replace(state, phase=GateL2Phase.LAUNCH_OUTCOME_UNKNOWN),
            GateL2Event.AMBIGUITY_RECOVERY_OBSERVED,
            instance_id="instance-a",
        )


def test_termination_precedes_regional_delete_and_global_restore() -> None:
    state = GateL2State(
        phase=GateL2Phase.INSTANCE_ACTIVE,
        launch_requests=1,
        owned_instance_id="instance-a",
        global_mutated=True,
        regional_created=True,
    )
    with pytest.raises(L20ContractError):
        transition_gate_l2(state, GateL2Event.REGIONAL_DELETE_VERIFIED)
    state = transition_gate_l2(state, GateL2Event.TERMINATION_SENT)
    state = transition_gate_l2(
        state,
        GateL2Event.TERMINAL_OBSERVED,
        instance_id="instance-a",
        terminal_status="terminated",
    )
    state = transition_gate_l2(state, GateL2Event.REGIONAL_DELETE_VERIFIED)
    state = transition_gate_l2(state, GateL2Event.GLOBAL_RESTORE_VERIFIED)
    state = transition_gate_l2(state, GateL2Event.ZERO_OWNED_INSTANCES_VERIFIED)
    assert state.phase is GateL2Phase.CLOSED
    assert not state.global_mutated


def test_termination_failure_preserves_strict_firewall() -> None:
    state = GateL2State(
        phase=GateL2Phase.TERMINATING,
        launch_requests=1,
        owned_instance_id="instance-a",
        termination_requests=1,
        global_mutated=True,
        regional_created=True,
    )
    state = transition_gate_l2(state, GateL2Event.CLEANUP_FAILED)
    assert state.phase is GateL2Phase.INCIDENT
    assert state.global_mutated
    assert state.regional_created


def test_global_restoration_failure_is_incident_and_never_claims_closed() -> None:
    state = GateL2State(
        phase=GateL2Phase.REGIONAL_DELETED,
        launch_requests=1,
        owned_instance_id="instance-a",
        termination_requests=1,
        global_mutated=True,
        regional_created=False,
        instance_terminal=True,
    )
    state = transition_gate_l2(state, GateL2Event.CLEANUP_FAILED)
    assert state.phase is GateL2Phase.INCIDENT
    assert state.global_mutated


def test_terminal_proof_requires_exact_terminated_state() -> None:
    state = GateL2State(
        phase=GateL2Phase.TERMINATING,
        launch_requests=1,
        owned_instance_id="instance-a",
        termination_requests=1,
        global_mutated=True,
        regional_created=True,
    )
    for status in (None, "terminating", "preempted", "error"):
        with pytest.raises(L20ContractError):
            transition_gate_l2(
                state,
                GateL2Event.TERMINAL_OBSERVED,
                instance_id="instance-a",
                terminal_status=status,
            )


def test_launch_unknown_abort_preserves_strict_firewall_incident() -> None:
    state = GateL2State(
        phase=GateL2Phase.LAUNCH_OUTCOME_UNKNOWN,
        launch_requests=1,
        global_mutated=True,
        regional_created=True,
        owned_regional_ruleset_id="ruleset-a",
    )
    state = transition_gate_l2(state, GateL2Event.ABORT)
    assert state.phase is GateL2Phase.INCIDENT
    assert state.global_mutated
    assert state.regional_created


def test_launch_recovery_zero_allows_cleanup_but_requires_final_zero_proof() -> None:
    state = GateL2State(
        phase=GateL2Phase.LAUNCH_OUTCOME_UNKNOWN,
        launch_requests=1,
        global_mutated=True,
        regional_created=True,
        owned_regional_ruleset_id="ruleset-a",
    )
    state = transition_gate_l2(state, GateL2Event.AMBIGUITY_RECOVERY_ZERO_OWNED)
    state = transition_gate_l2(state, GateL2Event.REGIONAL_DELETE_VERIFIED)
    state = transition_gate_l2(state, GateL2Event.GLOBAL_RESTORE_VERIFIED)
    assert state.phase is GateL2Phase.GLOBAL_RESTORED
    state = transition_gate_l2(state, GateL2Event.ZERO_OWNED_INSTANCES_VERIFIED)
    assert state.phase is GateL2Phase.CLOSED


def test_restore_body_uses_complete_fresh_response_not_redacted_baseline() -> None:
    fresh_rules = [
        {
            "protocol": "tcp",
            "source_network": "8.8.8.8/32",
            "port_range": [22, 22],
            "description": "synthetic original",
        }
    ]
    assert render_global_restore_body({"data": {"rules": fresh_rules}}) == {"rules": fresh_rules}
    redacted_rules = [
        {
            "protocol": "tcp",
            "source_network": "8.8.8.8/32",
            "port_range": [22, 22],
        }
    ]
    with pytest.raises(L20ContractError):
        render_global_restore_body({"data": {"rules": redacted_rules}})


def test_runtime_body_renderers_are_exact_and_placeholder_free() -> None:
    template = {
        "region_name": "us-east-1",
        "instance_type_name": "gpu_1x_a10",
        "ssh_key_names": ["fractal-lambda-codex"],
        "file_system_names": [],
        "file_system_mounts": [],
        "name": "giclab-t07-l2-0123456789ab",
        "hostname": "giclab-t07-l2-0123456789ab",
        "image": {"id": "image-a"},
        "tags": [
            {"key": "giclab-experiment", "value": "EXP-0001"},
            {"key": "giclab-gate", "value": "T07-L2"},
            {"key": "giclab-run", "value": RUN_ID},
            {"key": "giclab-owner", "value": "0123456789ab"},
            {"key": "giclab-plan", "value": PLAN_ID},
        ],
        "authorization_tag_runtime_binding": "authorization_reference",
        "firewall_rulesets_runtime_binding": "owned_regional_ruleset_id",
    }
    body = render_launch_body(
        template,
        owned_regional_ruleset_id="ruleset-a",
        authorization_reference="AUTH-T07-L2-TEST-0001",
    )
    assert body["firewall_rulesets"] == [{"id": "ruleset-a"}]
    assert body["file_system_names"] == []
    assert body["file_system_mounts"] == []
    assert all("runtime_binding" not in key for key in body)
    assert render_terminate_body("instance-a") == {"instance_ids": ["instance-a"]}


def test_create_and_launch_response_shapes_have_distinct_typed_recovery() -> None:
    assert (
        resolve_owned_regional_ruleset_id(
            expected_name="owned",
            expected_region="us-east-1",
            create_response={"data": {"id": "ruleset-a"}},
        )
        == "ruleset-a"
    )
    assert (
        resolve_owned_regional_ruleset_id(
            expected_name="owned",
            expected_region="us-east-1",
            recovery_response={
                "data": [
                    {"id": "unrelated", "name": "other", "region": {"name": "us-east-1"}},
                    {"id": "ruleset-a", "name": "owned", "region": {"name": "us-east-1"}},
                ]
            },
        )
        == "ruleset-a"
    )
    tags = [{"key": "owner", "value": "nonce"}]
    assert (
        resolve_owned_instance_id(
            expected_name="owned",
            expected_tags=tags,
            launch_response={"data": {"instance_ids": ["instance-a"]}},
        )
        == "instance-a"
    )
    assert (
        resolve_owned_instance_id(
            expected_name="owned",
            expected_tags=tags,
            recovery_response={
                "data": [
                    {"id": "instance-a", "name": "owned", "tags": tags},
                ]
            },
        )
        == "instance-a"
    )
    assert (
        resolve_owned_instance_id(
            expected_name="owned",
            expected_tags=tags,
            recovery_response={"data": []},
        )
        is None
    )


def test_fresh_prelaunch_revalidates_price_capacity_image_key_firewall_and_zero_instances() -> None:
    region = {"name": "us-east-1", "description": "synthetic"}
    instance_type = {
        "name": "gpu_1x_a10",
        "description": "synthetic",
        "gpu_description": "synthetic",
        "price_cents_per_hour": 129,
        "specs": {"vcpus": 30, "memory_gib": 200, "storage_gib": 1400, "gpus": 1},
        "architecture": "x86_64",
    }
    rule = {
        "protocol": "tcp",
        "port_range": [22, 22],
        "source_network": "8.8.4.4/32",
        "description": "synthetic original",
    }
    responses = {
        "instance-types": {
            "data": {
                "gpu_1x_a10": {
                    "instance_type": instance_type,
                    "regions_with_capacity_available": [region],
                }
            }
        },
        "images": {
            "data": [
                {
                    "id": "image-a",
                    "created_time": "2026-08-01T00:00:00Z",
                    "updated_time": "2026-08-01T00:00:00Z",
                    "name": "synthetic",
                    "description": "synthetic",
                    "family": "gpu-base-22-04",
                    "version": "22.4.5-2141",
                    "architecture": "x86_64",
                    "region": region,
                }
            ]
        },
        "regions": {"data": [region]},
        "ssh-keys": {
            "data": [{"id": "key-a", "name": "fractal-lambda-codex", "public_key": "dummy"}]
        },
        "firewall-rulesets": {"data": []},
        "global-firewall-ruleset": {"data": {"id": "global", "name": "global", "rules": [rule]}},
        "instances": {"data": []},
    }
    private = {
        "selected_resource": {"raw_image_id": "image-a", "raw_ssh_key_id": "key-a"},
        "owned_names": {"regional_ruleset_name": "owned-ruleset"},
        "original_global_firewall": {
            "rules": [
                {
                    "protocol": "tcp",
                    "port_range": [22, 22],
                    "source_network": "8.8.4.4/32",
                }
            ]
        },
    }
    assert (
        validate_fresh_prelaunch_responses(
            ROOT,
            responses=responses,
            private_parameters=private,
        )
        is responses["global-firewall-ruleset"]
    )
    responses["instance-types"]["data"]["gpu_1x_a10"]["instance_type"][  # type: ignore[index]
        "price_cents_per_hour"
    ] = 130
    with pytest.raises(L20ContractError):
        validate_fresh_prelaunch_responses(
            ROOT,
            responses=responses,
            private_parameters=private,
        )


def test_host_checkpoint_accepts_exact_private_identity(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    wait = prepare_host_key_checkpoint_wait(
        path=path,
        challenge_nonce="ab" * 32,
        started_monotonic_ns=1_000_000_000,
        started_wall_utc=datetime(2026, 8, 10, 18, 59, tzinfo=UTC),
    )
    document = {
        "schema_version": "0.1.0",
        "checkpoint_id": "CHECKPOINT-T07-L2-0001",
        "checkpoint_challenge_nonce": "ab" * 32,
        "run_id": RUN_ID,
        "provider_instance_id": "instance-a",
        "algorithm": "ssh-ed25519",
        "fingerprint": DUMMY_FINGERPRINT,
        "observed_at_utc": "2026-08-10T19:00:00Z",
        "observation_method": "lambda-authenticated-jupyter-terminal",
    }
    path.write_bytes(canonical_bytes(document))
    path.chmod(0o600)
    assert (
        validate_host_key_checkpoint(
            ROOT,
            wait_binding=wait,
            expected_instance_id="instance-a",
            observed_monotonic_ns=2_000_000_000,
            observed_wall_utc=datetime(2026, 8, 10, 19, 1, tzinfo=UTC),
        )
        == document
    )


@pytest.mark.parametrize("elapsed_seconds", [601, 900])
def test_late_host_checkpoint_stops(tmp_path: Path, elapsed_seconds: int) -> None:
    path = tmp_path / "checkpoint.json"
    wait = prepare_host_key_checkpoint_wait(
        path=path,
        challenge_nonce="ab" * 32,
        started_monotonic_ns=1,
        started_wall_utc=datetime(2026, 8, 10, 18, 59, tzinfo=UTC),
    )
    path.write_bytes(b"{}\n")
    path.chmod(0o600)
    with pytest.raises(L20ContractError):
        validate_host_key_checkpoint(
            ROOT,
            wait_binding=wait,
            expected_instance_id="instance-a",
            observed_monotonic_ns=1 + elapsed_seconds * 1_000_000_000,
            observed_wall_utc=datetime(2026, 8, 10, 19, 20, tzinfo=UTC),
        )


def test_host_checkpoint_mismatch_stops(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    wait = prepare_host_key_checkpoint_wait(
        path=path,
        challenge_nonce="ab" * 32,
        started_monotonic_ns=1,
        started_wall_utc=datetime(2026, 8, 10, 18, 59, tzinfo=UTC),
    )
    document = {
        "schema_version": "0.1.0",
        "checkpoint_id": "CHECKPOINT-T07-L2-0001",
        "checkpoint_challenge_nonce": "ab" * 32,
        "run_id": RUN_ID,
        "provider_instance_id": "instance-other",
        "algorithm": "ssh-ed25519",
        "fingerprint": DUMMY_FINGERPRINT,
        "observed_at_utc": "2026-08-10T19:00:00Z",
        "observation_method": "lambda-authenticated-jupyter-terminal",
    }
    path.write_bytes(canonical_bytes(document))
    path.chmod(0o600)
    with pytest.raises(L20ContractError):
        validate_host_key_checkpoint(
            ROOT,
            wait_binding=wait,
            expected_instance_id="instance-a",
            observed_monotonic_ns=2,
            observed_wall_utc=datetime(2026, 8, 10, 19, 1, tzinfo=UTC),
        )


def test_host_checkpoint_must_be_absent_before_wait(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    path.write_bytes(b"{}\n")
    path.chmod(0o600)
    with pytest.raises(L20ContractError):
        prepare_host_key_checkpoint_wait(
            path=path,
            challenge_nonce="ab" * 32,
            started_monotonic_ns=1,
            started_wall_utc=datetime(2026, 8, 10, 18, 59, tzinfo=UTC),
        )


def test_ed25519_keyscan_equality_builds_known_hosts() -> None:
    line, fingerprint = _ed25519_line()
    assert (
        verified_known_hosts_line(
            instance_ipv4="8.8.8.8",
            keyscan_output=(line + "\n").encode(),
            checkpoint_fingerprint=fingerprint,
        )
        == (line + "\n").encode()
    )


def test_ed25519_keyscan_mismatch_blocks_ssh() -> None:
    line, _ = _ed25519_line()
    with pytest.raises(L20ContractError):
        verified_known_hosts_line(
            instance_ipv4="8.8.8.8",
            keyscan_output=(line + "\n").encode(),
            checkpoint_fingerprint=DUMMY_FINGERPRINT,
        )


def test_ssh_render_is_strict_agent_only_and_no_forwarding() -> None:
    argv = render_ssh_argv(
        agent_socket="/private/tmp/agent.sock",
        public_identity_file="/private/tmp/key.pub",
        known_hosts_file="/private/tmp/known_hosts",
        instance_ipv4="8.8.8.8",
        remote_argv=["/usr/bin/uname", "-srmo"],
    )
    rendered = "\n".join(argv)
    assert "IdentitiesOnly=yes" in rendered
    assert "StrictHostKeyChecking=yes" in rendered
    assert "ForwardAgent=no" in rendered
    assert "PermitLocalCommand=no" in rendered
    assert "BatchMode=yes" in rendered
    assert "-A" not in argv


@pytest.mark.parametrize("command", ["apt", "apt-get", "pip", "uv", "brew"])
def test_ssh_remote_package_mutation_rejected(command: str) -> None:
    with pytest.raises(L20ContractError):
        render_ssh_argv(
            agent_socket="/private/tmp/agent.sock",
            public_identity_file="/private/tmp/key.pub",
            known_hosts_file="/private/tmp/known_hosts",
            instance_ipv4="8.8.8.8",
            remote_argv=[command, "install", "x"],
        )


def test_container_create_is_digest_pinned_no_network_and_bounded() -> None:
    fixture = (ROOT / CONTAINMENT_FIXTURE_PATH).read_text()
    argv = render_container_create_argv(
        container_name="giclab-t07-l2-containment-0123456789ab",
        fixture_script=fixture,
        authorization_reference="AUTH-T07-L2-TEST-0001",
        repository_commit="a" * 40,
        provider_instance_id="instance-a",
    )
    rendered = "\n".join(argv)
    assert BUSYBOX_REFERENCE in argv
    for required in (
        "none",
        "private",
        "ALL",
        "no-new-privileges=true",
        "--read-only",
        "--pids-limit",
        "--memory",
        "--cpus",
        "--restart",
        "--init",
    ):
        assert required in argv or required in rendered
    assert "/var/run/docker.sock" not in rendered
    assert "--privileged" not in argv
    assert "--pid" not in argv
    for label in (
        "giclab.experiment=EXP-0001",
        "giclab.profile=PLAN-EXP0001-SMOKE",
        f"giclab.plan={PLAN_ID}",
        "giclab.authorization=AUTH-T07-L2-TEST-0001",
        f"giclab.repository_commit={'a' * 40}",
        "giclab.attempt=giclab-t07-l2-containment-0123456789ab",
        "giclab.provider_instance_id=instance-a",
    ):
        assert label in argv


def test_container_create_rejects_pending_authorization() -> None:
    fixture = (ROOT / CONTAINMENT_FIXTURE_PATH).read_text()
    with pytest.raises(L20ContractError):
        render_container_create_argv(
            container_name="giclab-t07-l2-containment-0123456789ab",
            fixture_script=fixture,
            authorization_reference=AUTHORIZATION_PLACEHOLDER,
            repository_commit="a" * 40,
            provider_instance_id="instance-a",
        )


def test_fixture_hash_is_locked() -> None:
    encoded = (ROOT / CONTAINMENT_FIXTURE_PATH).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == CONTAINMENT_FIXTURE_SHA256


def test_provider_call_budget_is_exactly_derived() -> None:
    operations = provider_operations()
    assert len(operations) == 22
    assert sum(int(operation["max_calls"]) for operation in operations) == MAX_PROVIDER_API_CALLS
    assert [operation["ordinal"] for operation in operations] == list(range(1, 23))


def test_exact_limits_are_finite_and_scientifically_zero() -> None:
    limits = exact_limits()
    assert all(value >= 0 for value in limits.values() if isinstance(value, int))
    assert limits["provider_api_calls"] == MAX_PROVIDER_API_CALLS
    assert limits["persistent_filesystem_count"] == 0
    assert limits["model_calls"] == 0
    assert limits["model_tokens"] == 0
    assert limits["automated_browser_actions"] == 0
    assert limits["sira_executions"] == 0
    assert limits["scientific_executions"] == 0


def test_public_design_is_blocked_non_executable_and_private_safe() -> None:
    plan = render_plan()
    assert plan["plan_id"] == PLAN_ID
    assert plan["run_id"] == RUN_ID
    assert plan["branch"] == BRANCH
    assert plan["authorization_reference"] == AUTHORIZATION_PLACEHOLDER
    assert plan["authorized"] is False
    assert plan["authorization_state"] == "blocked-source-and-control-plane"
    assert plan["executable_after_exact_authorization"] is False
    assert plan["terminal_state"] == "blocked-human-or-source-decision"
    assert len(plan["runtime_bindings"]) == 6
    encoded = canonical_bytes(plan)
    assert b"source_ipv4_cidr" not in encoded
    assert b"raw_image_id" not in encoded
    assert b"raw_ssh_key_id" not in encoded
    assert b"SHA256:" not in encoded
    assert not (ROOT / "containers/sira-smoke/lambda/gate-l2-host-qualification-plan.json").exists()


def test_public_plan_rejects_private_cidr_and_null_identity() -> None:
    plan = render_plan()
    plan["private_binding"] = dict(plan["private_binding"])
    plan["private_binding"]["source_ipv4_cidr"] = "8.8.8.8/32"  # type: ignore[index]
    with pytest.raises(L20ContractError):
        validate_public_plan(plan, repository_root=ROOT)
    plan = render_plan()
    plan["public_selection"] = dict(plan["public_selection"])
    plan["public_selection"]["image_alias"] = None  # type: ignore[index]
    with pytest.raises(L20ContractError):
        validate_public_plan(plan, repository_root=ROOT)


def test_public_plan_has_one_way_archive_and_termination_first() -> None:
    plan = render_plan()
    cleanup = plan["evidence_and_cleanup"]
    firewall = plan["firewall_transaction"]
    assert isinstance(cleanup, dict) and cleanup["one_way_copy"] is True
    assert isinstance(cleanup, dict) and cleanup["local_source_retained"] is True
    assert (
        isinstance(firewall, dict) and firewall["instance_terminal_before_regional_delete"] is True
    )
    assert isinstance(firewall, dict) and firewall["regional_delete_before_global_restore"] is True


def test_module_has_no_live_transport_or_subprocess_import() -> None:
    source = (ROOT / "src/giclab/harness/lambda_l20_plan.py").read_text()
    for forbidden in ("import http.client", "import urllib", "import subprocess", "requests."):
        assert forbidden not in source


def test_private_key_file_is_never_opened_by_control_plane() -> None:
    source = (ROOT / "src/giclab/harness/lambda_l20_plan.py").read_text()
    assert 'private_key_file_read_allowed": False' in source
    assert "read_private_key" not in source


def test_scientific_locks_remain_exact() -> None:
    base = "experiments/EXP-0001-sira-simulative-vs-reactive/"
    expected = {
        base + "protocol.yaml": (
            "5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c"
        ),
        base + "config.yaml": ("f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d"),
        base + "run-plans/smoke.yaml": (
            "ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425"
        ),
        base + "run-plans/conditions/smoke-reactive.yaml": (
            "7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018"
        ),
        base + "run-plans/conditions/smoke-simulative.yaml": (
            "68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436"
        ),
    }
    for relative, digest in expected.items():
        assert git_blob_sha256(ROOT, T07_FROZEN_EXECUTION_COMMIT, relative) == digest


def test_schema_files_are_valid_json() -> None:
    for relative in (
        "schemas/t07-lambda-l2-human-decision.schema.json",
        "schemas/t07-lambda-l2-private-parameters.schema.json",
        "schemas/t07-lambda-l2-host-key-checkpoint.schema.json",
        "schemas/t07-lambda-l2-plan.schema.json",
        "schemas/t07-lambda-l2-provider-ledger.schema.json",
        "schemas/t07-lambda-l2-host-evidence.schema.json",
        "schemas/t07-lambda-l2-incident.schema.json",
    ):
        schema = json.loads((ROOT / relative).read_text())
        assert isinstance(schema, dict)
        assert "no Gate L2 execution authority" in schema["$comment"] or (
            "no executable plan exists" in schema["$comment"]
        )


def test_bound_public_sources_leave_unknown_launch_recovery_blocked() -> None:
    observation = json.loads(
        (ROOT / "containers/sira-smoke/lambda/public-source-observations-l2-0.json").read_text()
    )
    findings = observation["source_findings"]
    for field in (
        "instance_response_name_required",
        "instance_response_tags_required",
        "launch_idempotency_contract_found_in_bound_sources",
        "running_instance_list_strong_consistency_found_in_bound_sources",
        "bounded_launch_visibility_contract_found_in_bound_sources",
        "unknown_launch_exact_id_recovery_source_complete",
    ):
        assert findings[field] is False


def test_no_external_account_transport_is_invoked(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr(os, "system", forbidden)
    render_plan()
