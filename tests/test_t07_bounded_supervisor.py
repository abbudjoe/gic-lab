from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import giclab.harness.t07_bounded_supervisor as supervisor
from giclab.harness import lambda_archive
from giclab.harness import t07_bounded_smoke as contract
from giclab.harness.sira_storage import (
    APPROVED_EXTERNAL_CAPACITY_BYTES,
    APPROVED_MOUNT,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_MOUNT,
    SYSTEM_DATA_VOLUME_UUID,
    VolumeObservation,
)
from giclab.validation import ROOT

NOW = datetime(2026, 8, 11, 20, 0, 0, tzinfo=UTC)
AFTER_NOW = NOW + timedelta(seconds=1)
COMMIT = "1" * 40
AUTHORIZATION_REFERENCE = "AUTH-T07-BOUNDED-SIRA-SMOKE-V1-TEST-0001"
PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f"


class FakeTransport:
    def __init__(self, documents: Mapping[str, object]) -> None:
        self.documents = documents
        self.paths: list[str] = []

    def fetch(
        self,
        path: str,
        *,
        credential: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> supervisor.HttpResponse:
        assert credential == "public-dummy-lambda-canary-never-retained"
        assert timeout_seconds == 60
        encoded = supervisor.canonical_json_bytes(self.documents[path])
        assert len(encoded) <= max_response_bytes
        self.paths.append(path)
        return supervisor.HttpResponse(200, "application/json", encoded, 5)


def _rule(description: str, source: str = "203.0.113.7/32") -> dict[str, object]:
    return {
        "protocol": "tcp",
        "port_range": [22, 22],
        "source_network": source,
        "description": description,
    }


def _region() -> dict[str, object]:
    return {"name": "us-east-1", "description": "synthetic local fixture"}


def _instance_type() -> dict[str, object]:
    return {
        "name": "gpu_1x_a10",
        "description": "synthetic local fixture",
        "gpu_description": "one A10",
        "price_cents_per_hour": 129,
        "specs": {"vcpus": 30, "memory_gib": 200, "storage_gib": 1400, "gpus": 1},
        "architecture": "x86_64",
    }


def _actions() -> dict[str, object]:
    return {
        name: {"available": True}
        for name in ("migrate", "rebuild", "restart", "cold_reboot", "terminate")
    }


def _instance(status: str, ruleset_id: str) -> dict[str, object]:
    return {
        "id": "synthetic-instance-private",
        "status": status,
        "ssh_key_names": ["fractal-lambda-codex"],
        "file_system_names": [],
        "region": _region(),
        "instance_type": _instance_type(),
        "actions": _actions(),
        "firewall_rulesets": [{"id": ruleset_id}],
    }


def _external_observation(mount: Path = APPROVED_MOUNT) -> VolumeObservation:
    return VolumeObservation(
        mount_path=mount,
        filesystem="apfs",
        writable=True,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        total_bytes=APPROVED_EXTERNAL_CAPACITY_BYTES,
        free_bytes=800_000_000_000,
        internal=False,
        owners_enabled=False,
        encrypted=True,
        unlocked=True,
        device_identifier="disk99s1",
        bus_protocol="Thunderbolt",
        device_tree_path="IOService:/synthetic/AppleThunderbolt/UTDM",
    )


def _system_observation() -> VolumeObservation:
    return VolumeObservation(
        mount_path=SYSTEM_DATA_MOUNT,
        filesystem="apfs",
        writable=True,
        volume_uuid=SYSTEM_DATA_VOLUME_UUID,
        physical_store_uuid=None,
        total_bytes=SYSTEM_CAPACITY_BYTES,
        free_bytes=20_000_000_000,
        internal=True,
        owners_enabled=True,
        encrypted=True,
        unlocked=True,
        device_identifier="disk3s1",
    )


def _copy_schemas(root: Path) -> None:
    for relative in (
        supervisor.AUTHORIZATION_SCHEMA_RELATIVE,
        supervisor.PRIVATE_BINDING_SCHEMA_RELATIVE,
        supervisor.LEDGER_SCHEMA_RELATIVE,
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    shutil.copytree(ROOT / supervisor.ENDPOINT_SCHEMA_ROOT, root / supervisor.ENDPOINT_SCHEMA_ROOT)


def _materialize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, object], str, str]:
    _copy_schemas(tmp_path)
    baseline = [_rule("synthetic sealed baseline", source="198.51.100.0/24")]
    baseline_sha256 = supervisor._firewall_semantic_sha256(baseline)
    monkeypatch.setattr(supervisor, "BASELINE_SEMANTIC_SHA256", baseline_sha256)
    source = {
        "source_ipv4_cidr": "203.0.113.7/32",
        "strict_firewall_rule": _rule("source strict rule"),
        "owned_regional_ruleset": {"rules": [_rule("source owned rule")]},
        "selected_resource": {
            "instance_type": "gpu_1x_a10",
            "region": "us-east-1",
            "architecture": "x86_64",
            "image_alias": "img-0032",
            "image_family": "lambda-stack-22-04",
            "image_version": "22.4.5-2141",
            "raw_image_id": "synthetic-image-private",
            "ssh_key_name": "fractal-lambda-codex",
            "raw_ssh_key_id": "synthetic-key-private",
            "local_public_key_fingerprint": supervisor._fingerprint(PUBLIC_KEY),
            "price_cents_per_hour": 129,
        },
    }
    restoration = {"rules": baseline}
    source_path = tmp_path / supervisor.SOURCE_PARAMETERS_RELATIVE
    restoration_path = tmp_path / supervisor.RESTORATION_RELATIVE
    source_path.parent.mkdir(parents=True, exist_ok=True)
    restoration_path.parent.mkdir(parents=True, exist_ok=True)
    source_encoded = supervisor.canonical_json_bytes(source)
    restoration_encoded = supervisor.canonical_json_bytes(restoration)
    source_path.write_bytes(source_encoded)
    restoration_path.write_bytes(restoration_encoded)
    source_sha256 = supervisor.sha256_bytes(source_encoded)
    restoration_sha256 = supervisor.sha256_bytes(restoration_encoded)
    monkeypatch.setattr(supervisor, "SOURCE_PARAMETERS_SHA256", source_sha256)
    monkeypatch.setattr(supervisor, "RESTORATION_SHA256", restoration_sha256)
    monkeypatch.setattr(supervisor, "verify_repository_identity", lambda *_: None)
    monkeypatch.setattr(supervisor, "_validate_base_authority", lambda *_: None)
    plan = {"limits": dict(contract.LIMITS)}
    plan_sha256 = "2" * 64
    summary = supervisor.materialize_authority(
        tmp_path,
        plan=plan,
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
        authorization_reference=AUTHORIZATION_REFERENCE,
        source_parameters_path=source_path,
        source_parameters_sha256=source_sha256,
        restoration_path=restoration_path,
        restoration_sha256=restoration_sha256,
        volume_observer=lambda: (_external_observation(), _system_observation()),
        utc_now=lambda: NOW,
    )
    return summary, plan_sha256, baseline_sha256


def _execute_observer(
    tmp_path: Path,
    summary: Mapping[str, object],
    plan_sha256: str,
    *,
    phase: str,
    transport: supervisor.ReadOnlyTransport,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> dict[str, object]:
    return supervisor.execute_observer_phase(
        tmp_path,
        plan={"limits": dict(contract.LIMITS)},
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
        phase=phase,
        authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
        authorization_sha256=str(summary["authorization_sha256"]),
        private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
        private_binding_sha256=str(summary["private_binding_sha256"]),
        transport=transport,
        credential_provider=lambda: "public-dummy-lambda-canary-never-retained",
        monotonic_ns=monotonic_ns,
        utc_now=lambda: AFTER_NOW,
        sleeper=lambda _: None,
    )


def test_exact_observer_phase_order_and_shell_free_commands() -> None:
    assert supervisor.PHASE_REQUESTS == {
        "prelaunch": (
            "/api/v1/instance-types",
            "/api/v1/images",
            "/api/v1/regions",
            "/api/v1/ssh-keys",
            "/api/v1/firewall-rulesets",
            "/api/v1/firewall-rulesets/global",
            "/api/v1/instances",
        ),
        "security": (
            "/api/v1/firewall-rulesets",
            "/api/v1/firewall-rulesets/global",
        ),
        "post_launch": ("/api/v1/instances",),
        "termination": ("/api/v1/instances",),
        "terminal": (
            "/api/v1/firewall-rulesets",
            "/api/v1/firewall-rulesets/global",
        ),
    }
    assert sum(map(len, supervisor.PHASE_REQUESTS.values())) == 13
    commands = contract.local_supervisor_argv_templates()
    assert set(commands) == {
        "materialize",
        "observe_prelaunch",
        "observe_security",
        "observe_post_launch",
        "observe_termination",
        "observe_terminal",
        "archive_complete",
        "archive_failed",
    }
    for argv in commands.values():
        assert argv[0:2] == ["/usr/bin/python3", "-I"]
        assert all(value not in argv for value in ("sh", "bash", "-c", "curl", "wget"))


def test_materialization_and_all_observer_phases_are_durable_and_secret_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, baseline_sha256 = _materialize(tmp_path, monkeypatch)
    authorization = tmp_path / supervisor.AUTHORIZATION_RELATIVE
    private_path = tmp_path / supervisor.PRIVATE_BINDING_RELATIVE
    assert authorization.stat().st_mode & 0o777 == 0o600
    assert private_path.stat().st_mode & 0o777 == 0o600
    private = json.loads(private_path.read_text(encoding="utf-8"))
    common = {
        "instance-types": {
            "data": {
                "gpu_1x_a10": {
                    "instance_type": _instance_type(),
                    "regions_with_capacity_available": [_region()],
                }
            }
        },
        "images": {
            "data": [
                {
                    "id": "synthetic-image-private",
                    "created_time": "2026-08-01T00:00:00Z",
                    "updated_time": "2026-08-01T00:00:00Z",
                    "name": "Synthetic image",
                    "description": "fixture",
                    "family": "lambda-stack-22-04",
                    "version": "22.4.5-2141",
                    "architecture": "x86_64",
                    "region": _region(),
                }
            ]
        },
        "regions": {"data": [_region()]},
        "ssh-keys": {
            "data": [
                {
                    "id": "synthetic-key-private",
                    "name": "fractal-lambda-codex",
                    "public_key": PUBLIC_KEY,
                }
            ]
        },
    }
    baseline_response = {
        "data": {
            "id": "global",
            "name": "global",
            "rules": [_rule("synthetic sealed baseline", source="198.51.100.0/24")],
        }
    }
    phases: list[tuple[str, dict[str, object]]] = [
        (
            "prelaunch",
            {
                "/api/v1/instance-types": common["instance-types"],
                "/api/v1/images": common["images"],
                "/api/v1/regions": common["regions"],
                "/api/v1/ssh-keys": common["ssh-keys"],
                "/api/v1/firewall-rulesets": {"data": []},
                "/api/v1/firewall-rulesets/global": baseline_response,
                "/api/v1/instances": {"data": []},
            },
        ),
        (
            "security",
            {
                "/api/v1/firewall-rulesets": {
                    "data": [
                        {
                            "id": "synthetic-ruleset-private",
                            "name": private["owned_ruleset_name"],
                            "region": _region(),
                            "rules": [private["owned_ruleset_rule"]],
                            "created": "2026-08-11T20:00:00Z",
                            "instance_ids": [],
                        }
                    ]
                },
                "/api/v1/firewall-rulesets/global": {
                    "data": {
                        "id": "global",
                        "name": "global",
                        "rules": [private["strict_firewall_rule"]],
                    }
                },
            },
        ),
        (
            "post_launch",
            {"/api/v1/instances": {"data": [_instance("active", "synthetic-ruleset-private")]}},
        ),
        (
            "termination",
            {"/api/v1/instances": {"data": [_instance("terminated", "synthetic-ruleset-private")]}},
        ),
        (
            "terminal",
            {
                "/api/v1/firewall-rulesets": {"data": []},
                "/api/v1/firewall-rulesets/global": baseline_response,
            },
        ),
    ]
    clock_value = 0

    def monotonic_ns() -> int:
        nonlocal clock_value
        clock_value += 1_000_000_000
        return clock_value

    for phase, documents in phases:
        transport = FakeTransport(documents)
        report = _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase=phase,
            transport=transport,
            monotonic_ns=monotonic_ns,
        )
        assert transport.paths == list(supervisor.PHASE_REQUESTS[phase])
        assert report["phase"] == phase
    state = json.loads((tmp_path / supervisor.STATE_RELATIVE).read_text(encoding="utf-8"))
    ledger = (tmp_path / supervisor.LEDGER_RELATIVE).read_bytes()
    assert state["status"] == "complete"
    assert state["request_count"] == 13
    assert state["event_count"] == 51
    assert len(ledger.splitlines()) == 51
    assert b"public-dummy-lambda-canary-never-retained" not in ledger
    assert baseline_sha256 in (
        tmp_path / supervisor.RUN_ROOT_RELATIVE / "terminal-report.json"
    ).read_text(encoding="utf-8")


def test_possible_send_failure_burns_run_and_preserves_terminal_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)

    class FailedTransport:
        def fetch(self, *args: object, **kwargs: object) -> supervisor.HttpResponse:
            del args, kwargs
            raise supervisor.TransportFailure("response_body", "response_body_failure", 17, 9)

    with pytest.raises(supervisor.BoundedSupervisorError, match="transport failed"):
        _execute_observer(
            tmp_path,
            summary,
            plan_sha256,
            phase="prelaunch",
            transport=FailedTransport(),
        )
    state = json.loads((tmp_path / supervisor.STATE_RELATIVE).read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (tmp_path / supervisor.LEDGER_RELATIVE).read_text(encoding="utf-8").splitlines()
    ]
    assert state["status"] == "burned"
    assert [event["event_type"] for event in events[-2:]] == [
        "request_outcome_unknown_after_send",
        "phase_failed",
    ]
    assert events[-2]["failure_stage"] == "response_body"


def test_complete_archive_reads_back_hashes_and_retains_local_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, plan_sha256, _ = _materialize(tmp_path, monkeypatch)
    run_root = tmp_path / supervisor.RUN_ROOT_RELATIVE
    state_path = run_root / "observer-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["status"] = "complete"
    state_path.write_bytes(supervisor.canonical_json_bytes(state))
    for ordinal in range(1, 14):
        (run_root / "responses" / f"{ordinal:03d}.json").write_text("{}\n", encoding="utf-8")
    for phase in ("prelaunch", "security", "post_launch", "termination", "terminal"):
        (run_root / f"{phase}-report.json").write_text("{}\n", encoding="utf-8")
    inbound = run_root / "inbound"
    inbound.mkdir()
    (inbound / "t07-bounded-evidence.zip").write_bytes(b"synthetic-safe-evidence")
    (inbound / "ARCHIVE_IDENTITY.json").write_text("{}\n", encoding="utf-8")
    (inbound / "TERMINATE_REQUIRED.json").write_text("{}\n", encoding="utf-8")
    external_mount = tmp_path / "external"
    external_mount.mkdir()
    external_parent = external_mount / "GIC-Lab/t07/sealed-artifacts"
    monkeypatch.setattr(supervisor, "EXTERNAL_MOUNT", external_mount)
    monkeypatch.setattr(supervisor, "EXTERNAL_PARENT", external_parent)
    monkeypatch.setattr(supervisor, "EXTERNAL_FINAL", external_parent / supervisor.HOST_RUN_ID)
    monkeypatch.setattr(lambda_archive, "APPROVED_MOUNT", external_mount)
    external = _external_observation(external_mount)
    result = supervisor.archive_evidence(
        tmp_path,
        plan={"limits": dict(contract.LIMITS)},
        plan_sha256=plan_sha256,
        expected_commit=COMMIT,
        authorization_path=tmp_path / supervisor.AUTHORIZATION_RELATIVE,
        authorization_sha256=str(summary["authorization_sha256"]),
        private_binding_path=tmp_path / supervisor.PRIVATE_BINDING_RELATIVE,
        private_binding_sha256=str(summary["private_binding_sha256"]),
        disposition="complete",
        volume_observer=lambda: (external, _system_observation()),
        utc_now=lambda: AFTER_NOW,
    )
    assert result["source_destination_hashes_verified"] is True
    assert result["source_retained"] is True
    destination = external_parent / supervisor.HOST_RUN_ID
    assert destination.is_dir()
    assert (destination / "SEAL.json").is_file()
    assert (inbound / "t07-bounded-evidence.zip").is_file()
