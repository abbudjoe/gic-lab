from __future__ import annotations

import ast
import datetime as dt
import hashlib
import importlib
import json
import os
import signal
import sys
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

import giclab.harness.lambda_l2m_observer as l2m_observer
from giclab.harness.lambda_l2m_checkpoints import (
    CheckpointBinding,
    CheckpointConsumptionEvidence,
    CheckpointConsumptionOutcomeUnknown,
    ValidatedHumanDecision,
    VerifiedCheckpoint,
    validate_human_decision,
)
from giclab.harness.lambda_l2m_observer import (
    BUNDLE_MANIFEST_SHA256,
    BUSYBOX_CONFIG_DIGEST,
    BUSYBOX_LAYER_DIGEST,
    BUSYBOX_REFERENCE,
    MAX_AGGREGATE_RESPONSE_BYTES,
    MAX_OBSERVER_GETS,
    MAX_OBSERVER_WALL_SECONDS,
    OBSERVER_PHASE_GET_LIMITS,
    RECOMMENDED_IMAGE_ALIAS,
    RECOMMENDED_IMAGE_VERSION,
    TERMINAL_DECISION,
    InstanceMatchState,
    L2MContractError,
    L2MDiskutilVolumeObserver,
    L2MObserverEvidenceStore,
    L2MReadOnlyObserverEngine,
    ManualLifecycle,
    ManualPhase,
    ObservedDocument,
    ObserverBudget,
    ObserverJournal,
    ObserverOperation,
    ObserverPhase,
    ObserverRequest,
    ObserverResponse,
    ObserverTransportFailure,
    QualificationEvidenceBinding,
    RulesetMatchState,
    TransitionProof,
    TransitionVerificationKind,
    _copy_sealed_observer_evidence,
    _copy_sealed_observer_evidence_held,
    billed_list_cost_cents,
    classify_instances_for_ruleset,
    classify_ruleset,
    derive_private_ruleset_marker,
    exact_l2m_caps,
    firewall_semantic_sha256,
    launch_configuration_sha256,
    observer_request,
    require_zero_prelaunch_instances,
    seal_observer_evidence,
    select_manual_console_images,
    validate_qualification_archive,
    validate_qualification_failure_archive,
    validate_strict_firewall_rules,
    verify_bundle_manifest,
    verify_global_firewall_restoration,
)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "containers/sira-smoke/lambda/manual-console"
SCHEMA = ROOT / "schemas/t07-lambda-l2m-host-evidence.schema.json"
DECISION_SCHEMA = ROOT / "schemas/t07-lambda-l2m-human-decision.schema.json"
DECISION_TEMPLATE = BUNDLE / "T07_L2M_HUMAN_DECISION_TEMPLATE.json"


def validated_decision(
    *,
    decision_alias: str = "l2m-decision-0123456789ab",
    source_ipv4_cidr: str = "8.8.8.8/32",
) -> ValidatedHumanDecision:
    document = json.loads(DECISION_TEMPLATE.read_bytes())
    document.update(
        {
            "decision_id": "T07-L2M-FIXTURE-DECISION",
            "decision_nonce": "a" * 64,
            "source_ipv4_cidr": source_ipv4_cidr,
        }
    )
    for key in list(document):
        if key.startswith(("approve_", "attest_", "acknowledge_")):
            document[key] = True
    return validate_human_decision(
        document,
        schema=json.loads(DECISION_SCHEMA.read_bytes()),
        schema_path=DECISION_SCHEMA,
        decision_alias=decision_alias,
    )


@dataclass
class FakeClock:
    nanoseconds: int = 0

    def monotonic_ns(self) -> int:
        return self.nanoseconds

    def sleep(self, seconds: float) -> None:
        self.nanoseconds += int(seconds * 1_000_000_000)


@dataclass
class DeadlineBeforeSendClock(FakeClock):
    calls: int = 0

    def monotonic_ns(self) -> int:
        self.calls += 1
        if self.calls >= 5:
            self.nanoseconds = 1_201 * 1_000_000_000
        return self.nanoseconds


@dataclass
class FakeObserverTransport:
    responses: list[ObserverResponse | ObserverTransportFailure]
    requests: list[ObserverRequest] = field(default_factory=list)
    clock: FakeClock | None = None
    transport_entry_ns: list[int] = field(default_factory=list)

    def send(
        self,
        request: ObserverRequest,
        *,
        credential: str,
        timeout_seconds: float,
        absolute_deadline_monotonic_ns: int,
        max_response_bytes: int,
    ) -> ObserverResponse:
        assert credential == "dummy-canary-not-a-secret"
        assert 0 < timeout_seconds <= 60
        assert absolute_deadline_monotonic_ns > 0
        assert 0 < max_response_bytes <= 1_048_576
        self.requests.append(request)
        if self.clock is not None:
            self.transport_entry_ns.append(self.clock.monotonic_ns())
        outcome = self.responses.pop(0)
        if isinstance(outcome, ObserverTransportFailure):
            raise outcome
        return outcome


@dataclass
class FakeCheckpointReader:
    details: dict[str, dict[str, object]]
    binding: CheckpointBinding
    consumption_path: Path
    repository_root: Path = ROOT
    consumed: list[str] = field(default_factory=list)
    _final_evidence: CheckpointConsumptionEvidence | None = None

    def __post_init__(self) -> None:
        self.consumption_path.write_bytes(b"")
        self.consumption_path.chmod(0o600)

    def read_once(
        self,
        path: Path,
        *,
        expected_type: str,
        expected_nonce: str,
        not_before: dt.datetime,
        not_after: dt.datetime,
        detail_validator: Callable[[VerifiedCheckpoint], None] | None = None,
        on_consumed: Callable[[VerifiedCheckpoint], None] | None = None,
    ) -> VerifiedCheckpoint:
        assert path.name == f"{expected_type}.json"
        assert expected_nonce == "1" * 64
        assert not_before <= not_after
        if expected_type in self.consumed:
            raise AssertionError("fake checkpoint reused")
        verified = VerifiedCheckpoint(
            checkpoint_type=expected_type,
            observed_at_utc=not_before,
            encoded_sha256=hashlib.sha256(expected_type.encode()).hexdigest(),
            launch_clicked_once=expected_type == "launch_clicked_once",
            details=dict(self.details[expected_type]),
        )
        if detail_validator is not None:
            detail_validator(verified)
        record = (
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "sequence": len(self.consumed) + 1,
                    "run_id": self.binding.run_id,
                    "decision_alias": self.binding.decision_alias,
                    "marker_alias": self.binding.marker_alias,
                    "checkpoint_type": expected_type,
                    "checkpoint_nonce": expected_nonce,
                    "checkpoint_sha256": verified.encoded_sha256,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        with self.consumption_path.open("ab") as handle:
            handle.write(record)
            handle.flush()
            os.fsync(handle.fileno())
        self.consumed.append(expected_type)
        if on_consumed is not None:
            on_consumed(verified)
        return verified

    @property
    def final_evidence(self) -> CheckpointConsumptionEvidence:
        if self._final_evidence is None:
            raise L2MContractError("fake consumption evidence is not final")
        return self._final_evidence

    def close(self) -> None:
        if self._final_evidence is None:
            encoded = self.consumption_path.read_bytes()
            identity = self.consumption_path.lstat()
            self._final_evidence = CheckpointConsumptionEvidence(
                self.consumption_path.absolute(),
                identity.st_dev,
                identity.st_ino,
                len(encoded),
                hashlib.sha256(encoded).hexdigest(),
                encoded,
            )


def response(
    data: object, *, status: int = 200, content_type: str = "application/json"
) -> ObserverResponse:
    body = json.dumps({"data": data}, sort_keys=True, separators=(",", ":")).encode()
    return ObserverResponse(status, content_type, body, 5)


def complete_preflight(engine: L2MReadOnlyObserverEngine) -> None:
    for operation in (
        ObserverOperation.LIST_IMAGES,
        ObserverOperation.LIST_INSTANCE_TYPES,
        ObserverOperation.LIST_SSH_KEYS,
        ObserverOperation.LIST_INSTANCES,
        ObserverOperation.LIST_RULESETS,
        ObserverOperation.GET_GLOBAL_FIREWALL,
    ):
        engine.observe(
            operation,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )


def make_observer_engine(
    tmp_path: Path,
    *,
    suffix: str,
    transport: FakeObserverTransport,
    clock: FakeClock,
    checkpoint_reader: FakeCheckpointReader | None = None,
    source_ipv4_cidr: str = "8.8.8.8/32",
    human_decision: ValidatedHumanDecision | None = None,
    require_l23_auxiliary_checkpoints: bool = False,
) -> L2MReadOnlyObserverEngine:
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    binding = CheckpointBinding(
        run_id=f"RUN-T07-L2M-FIXTURE-{suffix}",
        decision_alias="l2m-decision-0123456789ab",
        marker_alias=marker.marker_alias,
    )
    journal = ObserverJournal.create(
        tmp_path / f"observer-{suffix}.jsonl",
        schema_path=ROOT / "schemas/t07-lambda-l2m-observer-journal.schema.json",
    )
    return L2MReadOnlyObserverEngine(
        run_id=f"RUN-T07-L2M-FIXTURE-{suffix}",
        authorization_reference=f"AUTH-T07-L2M-FIXTURE-{suffix}",
        authorization_sha256="0" * 64,
        journal=journal,
        checkpoint_reader=checkpoint_reader
        or FakeCheckpointReader({}, binding, tmp_path / f"consumption-{suffix}.jsonl"),
        transport=transport,
        private_marker_name=marker.name,
        source_ipv4_cidr=source_ipv4_cidr,
        human_decision=(
            validated_decision(decision_alias=binding.decision_alias)
            if human_decision is None
            else human_decision
        ),
        sealed_original_global_sha256=firewall_semantic_sha256(original_rules),
        image_selection_checkpoint_sha256="2" * 64,
        private_selected_image_id="raw-b",
        private_selected_ssh_key_id="ssh-key-private",
        private_selected_ssh_key_fingerprint=("SHA256:ZkAslGjFiUHdGf/WUL8rQvkib4PTvQatUV0OUQSncCA"),
        selected_image_alias=RECOMMENDED_IMAGE_ALIAS,
        selected_image_version=RECOMMENDED_IMAGE_VERSION,
        require_l23_auxiliary_checkpoints=require_l23_auxiliary_checkpoints,
        clock_ns=clock.monotonic_ns,
        sleeper=clock.sleep,
        utc_now=lambda: dt.datetime(2026, 8, 10, tzinfo=dt.UTC),
    )


def preflight_responses() -> list[ObserverResponse]:
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    return [
        response([image("raw-b", family="lambda-stack-22-04", version="22.4.5-2141")]),
        response(
            {
                "gpu_1x_a10": {
                    "instance_type": instance_type_record(),
                    "regions_with_capacity_available": [
                        {"name": "us-east-1", "description": "fixture"}
                    ],
                }
            }
        ),
        response(
            [
                {
                    "id": "ssh-key-private",
                    "name": "fractal-lambda-codex",
                    "public_key": (
                        "ssh-ed25519 "
                        "AAAAC3NzaC1lZDI1NTE5AAAAIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f"
                    ),
                }
            ]
        ),
        response([]),
        response([]),
        response({"id": "global", "name": "global", "rules": original_rules}),
    ]


def evidence_binding() -> QualificationEvidenceBinding:
    return QualificationEvidenceBinding(
        run_id="RUN-T07-L2M-HOST-QUALIFICATION-0001",
        decision_alias="l2m-decision-0123456789ab",
        marker_alias="l2m-marker-0123456789ab",
        instance_binding_sha256="1" * 64,
        authorization_reference="AUTH-T07-L2M-FIXTURE-0001",
        authorization_sha256="0" * 64,
    )


def image(
    raw_id: str,
    *,
    family: str,
    version: str,
    architecture: str = "x86_64",
    region: str = "us-east-1",
) -> dict[str, object]:
    return {
        "id": raw_id,
        "created_time": "2026-08-01T00:00:00Z",
        "updated_time": "2026-08-01T00:00:00Z",
        "name": family.replace("-", " ").title(),
        "description": "fixture",
        "family": family,
        "version": version,
        "architecture": architecture,
        "region": {"name": region, "description": "fixture"},
    }


def inventory() -> dict[str, object]:
    return {
        "instance_types": [
            {
                "name": "gpu_1x_a10",
                "architecture": "x86_64",
                "price_cents_per_hour": 129,
                "capacity_regions": [{"name": "us-east-1"}],
                "specs": {"vcpus": 30, "memory_gib": 200, "storage_gib": 1400, "gpus": 1},
            }
        ],
        "images": [
            image("raw-a", family="lambda-stack-22-04", version="22.4.5-1459"),
            image("raw-b", family="lambda-stack-22-04", version="22.4.5-2141"),
            image("raw-c", family="lambda-stack-22-04", version="22.4.5-1722"),
            image("raw-d", family="gpu-base-22-04", version="22.4.5-9999"),
            image(
                "raw-e",
                family="lambda-stack-22-04",
                version="22.4.5-9999",
                architecture="arm64",
            ),
            image(
                "raw-f",
                family="lambda-stack-22-04",
                version="22.4.5-9999",
                region="us-west-1",
            ),
        ],
    }


def strict_rule() -> dict[str, object]:
    return {
        "protocol": "tcp",
        "port_range": [22, 22],
        "source_network": "8.8.8.8/32",
        "description": "T07 private SSH fallback",
    }


def prepare_bound_engine(
    tmp_path: Path,
    *,
    suffix: str,
    cleanup_responses: list[ObserverResponse],
    clock: FakeClock | None = None,
) -> tuple[L2MReadOnlyObserverEngine, FakeCheckpointReader, FakeClock, list[dict[str, object]]]:
    """Drive one fake-only observer through exact instance binding."""

    observed_clock = FakeClock() if clock is None else clock
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    original_sha256 = firewall_semantic_sha256(original_rules)
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    image_checkpoint_sha256 = "2" * 64
    launch_sha256 = launch_configuration_sha256(
        private_image_id="raw-b",
        image_selection_checkpoint_sha256=image_checkpoint_sha256,
        image_alias=RECOMMENDED_IMAGE_ALIAS,
        image_version=RECOMMENDED_IMAGE_VERSION,
        private_ruleset_id="ruleset-private",
        private_marker_name=marker.name,
        price_cents_per_hour=129,
    )
    binding_sha256 = hashlib.sha256(
        json.dumps(
            {
                "image_selection_checkpoint_sha256": image_checkpoint_sha256,
                "instance_id": "instance-private",
                "launch_configuration_sha256": launch_sha256,
                "ruleset_id": "ruleset-private",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    reader = FakeCheckpointReader(
        {
            "global_firewall_restricted": {"global_firewall_restricted": True},
            "regional_ruleset_created": {"regional_ruleset_created": True},
            "launch_clicked_once": {
                "launch_clicked_once": True,
                "approved_image_offered_for_selected_type_region": True,
                "launch_configuration_sha256": launch_sha256,
            },
            "instance_bound": {
                "instance_bound": True,
                "instance_binding_sha256": binding_sha256,
            },
            "cloud_ide_opened": {"cloud_ide_opened": True},
            "qualification_command_started": {"qualification_command_started": True},
            "qualification_command_completed": {"qualification_command_completed": True},
            "qualification_bundle_downloaded": {
                "qualification_bundle_downloaded": True,
                "qualification_archive_sha256": "3" * 64,
            },
            "termination_confirmed_by_user": {"termination_confirmed_by_user": True},
            "instance_terminal_verified": {
                "instance_terminal_verified": True,
                "terminal_or_absent": True,
                "launch_identity_state": "exact_one_bound",
            },
            "regional_ruleset_deleted": {
                "regional_ruleset_deleted": True,
                "regional_ruleset_absent": True,
            },
            "global_firewall_restored": {
                "global_firewall_restored": True,
                "global_firewall_semantic_sha256": original_sha256,
            },
        },
        CheckpointBinding(
            f"RUN-T07-L2M-FIXTURE-{suffix}",
            "l2m-decision-0123456789ab",
            marker.marker_alias,
        ),
        tmp_path / f"consumption-{suffix}.jsonl",
    )
    transport = FakeObserverTransport(
        [
            *preflight_responses(),
            response({"id": "global", "name": "global", "rules": [strict_rule()]}),
            response([ruleset(name=marker.name)]),
            response([instance()]),
            *cleanup_responses,
        ]
    )
    engine = make_observer_engine(
        tmp_path,
        suffix=suffix,
        transport=transport,
        clock=observed_clock,
        checkpoint_reader=reader,
    )
    engine.begin()
    complete_preflight(engine)
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)

    def consume(kind: str, *, observation: object = None) -> None:
        engine.consume_checkpoint(
            tmp_path / f"{kind}.json",
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
            observation=observation,  # type: ignore[arg-type]
        )

    global_observation = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    consume("global_firewall_restricted", observation=global_observation)
    ruleset_observation = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_BIND,
        credential="dummy-canary-not-a-secret",
    )
    consume("regional_ruleset_created", observation=ruleset_observation)
    engine.arm_launch_window()
    consume("launch_clicked_once")
    instance_observation = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.INSTANCE_BIND,
        credential="dummy-canary-not-a-secret",
    )
    consume("instance_bound", observation=instance_observation)
    return engine, reader, observed_clock, original_rules


def prepare_qualification_completed_engine(
    tmp_path: Path,
    *,
    suffix: str,
    archive_kind: str,
) -> tuple[
    L2MReadOnlyObserverEngine,
    FakeCheckpointReader,
    QualificationEvidenceBinding,
    str,
    Path,
]:
    engine, reader, _clock, _ = prepare_bound_engine(
        tmp_path,
        suffix=suffix,
        cleanup_responses=[],
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    for checkpoint_type in (
        "cloud_ide_opened",
        "qualification_command_started",
        "qualification_command_completed",
    ):
        engine.consume_checkpoint(
            tmp_path / f"{checkpoint_type}.json",
            expected_type=checkpoint_type,
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
        )
    assert engine.instance_binding_sha256 is not None
    binding = QualificationEvidenceBinding(
        run_id=engine.run_id,
        decision_alias=reader.binding.decision_alias,
        marker_alias=reader.binding.marker_alias,
        instance_binding_sha256=engine.instance_binding_sha256,
        authorization_reference=engine.authorization_reference,
        authorization_sha256=engine.authorization_sha256,
    )
    bundle_sha256 = hashlib.sha256((BUNDLE / "manifest.json").read_bytes()).hexdigest()
    archive_path = tmp_path / f"qualification-{archive_kind}.zip"
    if archive_kind == "success":
        write_success_qualification_archive(
            archive_path,
            binding=binding,
            bundle_sha256=bundle_sha256,
        )
    else:
        assert archive_kind == "failure"
        write_failure_qualification_archive(
            archive_path,
            binding=binding,
            bundle_sha256=bundle_sha256,
        )
    return engine, reader, binding, bundle_sha256, archive_path


def instance_type_record() -> dict[str, object]:
    return {
        "name": "gpu_1x_a10",
        "description": "fixture",
        "gpu_description": "A10",
        "price_cents_per_hour": 129,
        "specs": {"vcpus": 30, "memory_gib": 200, "storage_gib": 1400, "gpus": 1},
        "architecture": "x86_64",
    }


def ruleset(*, name: str, ruleset_id: str = "ruleset-private") -> dict[str, object]:
    return {
        "id": ruleset_id,
        "name": name,
        "region": {"name": "us-east-1", "description": "fixture"},
        "rules": [strict_rule()],
        "created": "2026-08-01T00:00:00Z",
        "instance_ids": [],
    }


def instance(
    *,
    ruleset_id: str = "ruleset-private",
    status: str = "active",
    instance_id: str = "instance-private",
) -> dict[str, object]:
    return {
        "id": instance_id,
        "status": status,
        "region": {"name": "us-east-1", "description": "fixture"},
        "instance_type": {
            "name": "gpu_1x_a10",
            "description": "fixture",
            "gpu_description": "A10",
            "price_cents_per_hour": 129,
            "specs": {"vcpus": 30, "memory_gib": 200, "storage_gib": 1400, "gpus": 1},
            "architecture": "x86_64",
        },
        "ssh_key_names": ["fractal-lambda-codex"],
        "firewall_rulesets": [{"id": ruleset_id}],
        "file_system_names": [],
        "file_system_mounts": [],
        "actions": {
            name: {"available": True}
            for name in ("migrate", "rebuild", "restart", "cold_reboot", "terminate")
        },
    }


def private_process_evidence() -> tuple[
    dict[str, object], dict[str, object], dict[str, object], dict[str, object]
]:
    pre_stop = {
        "process_count": 60,
        "max_parent_depth": 3,
        "distinct_sid_count": 2,
        "reparented_session_leader_count": 1,
        "structural_sha256": "5" * 64,
    }
    post_term = {
        "process_count": 60,
        "max_parent_depth": 3,
        "distinct_sid_count": 2,
        "reparented_session_leader_count": 1,
        "structural_sha256": "6" * 64,
    }
    markers = {
        "applets_verified": True,
        "pid_limit_observed": True,
        "pid_limit_marker_count": 1,
        "log_sha256": "7" * 64,
    }
    image = {
        "id": BUSYBOX_CONFIG_DIGEST,
        "repo_digests": [BUSYBOX_REFERENCE],
        "os": "linux",
        "architecture": "amd64",
    }
    return pre_stop, post_term, markers, image


def host_evidence(bundle_sha256: str) -> dict[str, object]:
    container_id = "a" * 64
    pre_stop, post_term, markers, image = private_process_evidence()
    process_structure_sha256 = hashlib.sha256(
        json.dumps(
            {
                "fixture_markers": markers,
                "post_term": post_term,
                "pre_stop": pre_stop,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    residue_summary = {
        "matched_cgroup_count": 0,
        "matched_process_count": 0,
        "scanned_cgroup_entries": 1,
        "scanned_process_count": 1,
    }
    residue_sha256 = hashlib.sha256(
        json.dumps(residue_summary, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": "0.1.0",
        "run_id": "RUN-T07-L2M-HOST-QUALIFICATION-0001",
        "authorization_reference": "AUTH-T07-L2M-FIXTURE-0001",
        "authorization_sha256": "0" * 64,
        "decision_alias": "l2m-decision-0123456789ab",
        "marker_alias": "l2m-marker-0123456789ab",
        "instance_binding_sha256": "1" * 64,
        "bundle_manifest_sha256": bundle_sha256,
        "host": {
            "os_id": "ubuntu",
            "os_version_id": "22.04",
            "kernel_release": "6.8.0-fixture",
            "architecture": "x86_64",
            "python_version": "3.10.12",
            "cgroup_mode": "v2",
            "root_total_bytes": 1_503_238_553_600,
            "root_free_bytes": 1_073_741_824_000,
        },
        "runtime": {
            "docker_client_version": "29.0.0",
            "docker_server_version": "29.0.0",
            "containerd_version": "2.1.0",
            "runc_version": "1.3.0",
            "buildx_version": "v0.30.0",
            "buildkit_version": None,
            "docker_service_active": True,
            "docker_endpoint_kind": "local-unix-socket",
            "initial_container_count": 0,
            "initial_image_count": 0,
            "initial_state_sha256": "2" * 64,
        },
        "busybox": {
            "image_reference": BUSYBOX_REFERENCE,
            "manifest_digest": BUSYBOX_REFERENCE.split("@", 1)[1],
            "config_digest": BUSYBOX_CONFIG_DIGEST,
            "layer_digest": BUSYBOX_LAYER_DIGEST,
            "layer_bytes": 2211507,
            "platform": "linux/amd64",
            "config_metadata_platform_proven": True,
            "public_metadata_observation_sha256": (
                "56a1ba759d4fc5ac6eba2ee85c5bff2a08d0d71f538793f3de5732bb80d0b1a5"
            ),
            "public_registry_metadata_reverified_at_utc": "2026-08-11T06:15:19.646016Z",
            "public_registry_metadata_reverified_before_qualification": True,
            "public_metadata_binding_validated_during_qualification": True,
            "public_metadata_age_seconds": 60,
            "public_registry_metadata_request_during_qualification": False,
            "pull_count": 1,
            "image_record_sha256": hashlib.sha256(
                json.dumps(image, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        "containment": {
            "container_id_sha256": hashlib.sha256(container_id.encode()).hexdigest(),
            "create_argv_sha256": "4" * 64,
            "fixture_sha256": "8" * 64,
            "fixture_identity_sha256": "9" * 64,
            "network_none": True,
            "private_pid_namespace": True,
            "private_cgroup_namespace": True,
            "private_ipc_namespace": True,
            "privileged": False,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "read_only_root": True,
            "restart_policy": "no",
            "cpu_limit_millis": 1000,
            "memory_bytes": 536870912,
            "memory_swap_bytes": 536870912,
            "pid_limit": 64,
            "tmpfs_bytes_each": 16777216,
            "shm_bytes": 16777216,
            "workload_wall_seconds": 4,
            "term_sent": True,
            "kill_escalated": True,
            "terminal_proven": True,
            "removed": True,
            "owned_container_residue_count": 0,
            "owned_network_residue_count": 0,
            "owned_volume_residue_count": 0,
            "background_process_residue_count": 0,
            "owned_cgroup_residue_count": 0,
            "residue_scan_sha256": residue_sha256,
            "residue_scanned_process_count": 1,
            "residue_scanned_cgroup_entries": 1,
            "pre_stop_process_count": 60,
            "pre_stop_max_parent_depth": 3,
            "pre_stop_distinct_sid_count": 2,
            "pre_stop_reparented_session_leader_count": 1,
            "post_term_process_count": 60,
            "post_term_max_parent_depth": 3,
            "post_term_distinct_sid_count": 2,
            "pid_limit_observed": True,
            "term_ignoring_descendants_proven": True,
            "process_structure_sha256": process_structure_sha256,
        },
        "prohibitions": {
            "ssh_operations": 0,
            "model_calls": 0,
            "browser_actions": 0,
            "sira_executions": 0,
            "scientific_executions": 0,
            "apt_operations": 0,
            "runtime_updates": 0,
            "secrets_accessed": 0,
        },
    }


def private_container_inspect() -> dict[str, object]:
    container_id = "a" * 64
    pre_stop, post_term, markers, image = private_process_evidence()
    base = {
        "Id": container_id,
        "Image": BUSYBOX_CONFIG_DIGEST,
        "HostConfig": {
            "NetworkMode": "none",
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "Privileged": False,
            "ReadonlyRootfs": True,
            "PidsLimit": 64,
            "NanoCpus": 1_000_000_000,
            "Memory": 536_870_912,
            "MemorySwap": 536_870_912,
            "ShmSize": 16_777_216,
            "Init": True,
            "PidMode": "",
            "RestartPolicy": {"Name": "no"},
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges=true"],
            "Tmpfs": {
                "/tmp": "rw,noexec,nosuid,nodev,size=16777216",
                "/run": "rw,noexec,nosuid,nodev,size=16777216",
            },
            "LogConfig": {"Type": "local", "Config": {"max-file": "1", "max-size": "1m"}},
        },
        "Config": {
            "Image": BUSYBOX_REFERENCE,
            "Labels": {
                "giclab.t07.run": "RUN-T07-L2M-HOST-QUALIFICATION-0001",
                "giclab.t07.marker": "l2m-marker-0123456789ab",
            },
        },
        "Mounts": [
            {
                "Type": "bind",
                "Source": "/private/jupyter/bundle/adversarial-containment.sh",
                "Destination": "/opt/t07/adversarial-containment.sh",
                "RW": False,
            }
        ],
    }
    documents = []
    for running in (False, True, False):
        row = json.loads(json.dumps(base))
        row["State"] = {"Running": running}
        documents.append(row)
    residue_summary = {
        "matched_cgroup_count": 0,
        "matched_process_count": 0,
        "scanned_cgroup_entries": 1,
        "scanned_process_count": 1,
    }
    return {
        "documents": documents,
        "fixture": {"bytes": 100, "identity_sha256": "9" * 64, "sha256": "8" * 64},
        "fixture_markers": markers,
        "image": image,
        "post_term_process": post_term,
        "pre_stop_process": pre_stop,
        "residue_scan": {
            **residue_summary,
            "scan_sha256": hashlib.sha256(
                json.dumps(residue_summary, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        "runtime": {"fixture": "private"},
    }


def qualification_log(evidence: dict[str, object]) -> bytes:
    containment = evidence["containment"]
    assert isinstance(containment, dict)
    container_sha = containment["container_id_sha256"]
    events = [
        {
            "sequence": 1,
            "event": "container_created",
            "container_id_sha256": container_sha,
            "create_argv_sha256": containment["create_argv_sha256"],
        },
        {
            "sequence": 2,
            "event": "pre_stop_process_evidence",
            "process_count": containment["pre_stop_process_count"],
            "report_sha256": "5" * 64,
            "pid_limit_observed": True,
        },
        {
            "sequence": 3,
            "event": "term_survived",
            "container_id_sha256": container_sha,
            "process_count": containment["post_term_process_count"],
            "report_sha256": "6" * 64,
        },
        {"sequence": 4, "event": "kill_terminal", "container_id_sha256": container_sha},
        {"sequence": 5, "event": "container_removed", "container_id_sha256": container_sha},
        {
            "sequence": 6,
            "event": "residue_verified",
            "container": 0,
            "network": 0,
            "volume": 0,
        },
        {"sequence": 7, "event": "qualification_passed", "elapsed_seconds": 8},
    ]
    return b"".join(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for event in events
    )


def write_success_qualification_archive(
    path: Path,
    *,
    binding: QualificationEvidenceBinding,
    bundle_sha256: str,
) -> Path:
    evidence = host_evidence(bundle_sha256)
    evidence.update(
        {
            "run_id": binding.run_id,
            "authorization_reference": binding.authorization_reference,
            "authorization_sha256": binding.authorization_sha256,
            "decision_alias": binding.decision_alias,
            "marker_alias": binding.marker_alias,
            "instance_binding_sha256": binding.instance_binding_sha256,
        }
    )
    inspect = private_container_inspect()
    documents = inspect["documents"]
    assert isinstance(documents, list)
    for document in documents:
        assert isinstance(document, dict)
        config = document["Config"]
        assert isinstance(config, dict)
        labels = config["Labels"]
        assert isinstance(labels, dict)
        labels["giclab.t07.run"] = binding.run_id
        labels["giclab.t07.marker"] = binding.marker_alias
    payloads = {
        "host-evidence.json": json.dumps(evidence, sort_keys=True).encode(),
        "qualification-log.jsonl": qualification_log(evidence),
        "container-inspect.json": json.dumps(inspect, sort_keys=True).encode(),
    }
    manifest = {
        "schema_version": "0.1.0",
        "files": [
            {
                "path": name,
                "bytes": len(value),
                "sha256": hashlib.sha256(value).hexdigest(),
            }
            for name, value in sorted(payloads.items())
        ],
    }
    with zipfile.ZipFile(path, "w") as handle:
        for name, value in payloads.items():
            handle.writestr(name, value)
        handle.writestr("EVIDENCE_MANIFEST.json", json.dumps(manifest).encode())
    return path


def write_failure_qualification_archive(
    path: Path,
    *,
    binding: QualificationEvidenceBinding,
    bundle_sha256: str,
) -> Path:
    cleanup = {
        "container_id_sha256": None,
        "kill_attempted": False,
        "kill_succeeded": True,
        "remove_attempted": False,
        "remove_succeeded": True,
        "container_residue_count": 0,
        "network_residue_count": 0,
        "volume_residue_count": 0,
        "process_residue_count": 0,
        "cgroup_residue_count": 0,
        "residue_scan_sha256": None,
        "residue_scanned_process_count": None,
        "residue_scanned_cgroup_entries": None,
        "docker_config_removed": True,
        "fixture_removed": True,
        "create_outcome_unknown": False,
        "create_outcome_observations": 0,
        "create_outcome_resolution": "not_applicable",
        "create_outcome_quiescence_proven": True,
    }
    disposition = {
        "schema_version": "0.1.0",
        "run_id": binding.run_id,
        "authorization_reference": binding.authorization_reference,
        "authorization_sha256": binding.authorization_sha256,
        "decision_alias": binding.decision_alias,
        "marker_alias": binding.marker_alias,
        "instance_binding_sha256": binding.instance_binding_sha256,
        "bundle_manifest_sha256": bundle_sha256,
        "sanitized_failure_stage": "host_contract",
        "cleanup": cleanup,
        "cleanup_complete": True,
        "provider_termination_required": True,
    }
    log = b"".join(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for event in (
            {"sequence": 1, "event": "qualification_failed", "failure_stage": "host_contract"},
            {
                "sequence": 2,
                "event": "emergency_cleanup_observed",
                "cleanup_complete": True,
                "cleanup": cleanup,
            },
        )
    )
    payloads = {
        "qualification-failure.json": json.dumps(disposition, sort_keys=True).encode(),
        "qualification-log.jsonl": log,
        "container-inspect.json": b'{"documents":[],"residue_scan":null,"runtime":{}}',
    }
    manifest = {
        "schema_version": "0.1.0",
        "files": [
            {
                "path": name,
                "bytes": len(value),
                "sha256": hashlib.sha256(value).hexdigest(),
            }
            for name, value in sorted(payloads.items())
        ],
    }
    with zipfile.ZipFile(path, "w") as handle:
        for name, value in payloads.items():
            handle.writestr(name, value)
        handle.writestr("EVIDENCE_MANIFEST.json", json.dumps(manifest).encode())
    return path


def test_lambda_stack_candidate_ranking_rejects_gpu_base_without_claiming_offeredness() -> None:
    selection = select_manual_console_images(inventory())
    assert selection.recommended.version == "22.4.5-2141"
    assert [item.version for item in selection.alternates] == ["22.4.5-1722", "22.4.5-1459"]
    assert selection.existing_gpu_base_documented_jupyter is False
    assert selection.human_approval_required is True
    assert all(
        item.family == "lambda-stack-22-04"
        for item in (selection.recommended, *selection.alternates)
    )


def test_sealed_public_image_decision_is_bound_to_recommended_alias() -> None:
    decision = json.loads((BUNDLE / "image-candidate-decision.json").read_bytes())
    assert decision["terminal_decision"] == TERMINAL_DECISION
    assert decision["recommended"]["alias"] == RECOMMENDED_IMAGE_ALIAS
    assert decision["recommended"]["version"] == RECOMMENDED_IMAGE_VERSION
    assert decision["existing_selection"]["documented_jupyterlab"] is False
    assert decision["type_specific_image_compatibility_source_available"] is False
    assert decision["launch_wizard_offeredness_required_before_launch"] is True


def test_private_ruleset_marker_requires_entropy_and_classifies_cardinality() -> None:
    with pytest.raises(L2MContractError, match="160 bits"):
        derive_private_ruleset_marker(b"short", decision_alias="l2m-decision-0123456789ab")
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    assert marker.entropy_bits == 256
    assert marker.name.startswith("t07-l2m-") and len(marker.name) == 48
    assert (
        classify_ruleset([], private_marker_name=marker.name, source_ipv4_cidr="8.8.8.8/32").state
        is RulesetMatchState.ZERO
    )
    exact = classify_ruleset(
        [ruleset(name=marker.name)],
        private_marker_name=marker.name,
        source_ipv4_cidr="8.8.8.8/32",
    )
    assert exact.state is RulesetMatchState.EXACT_ONE and exact.ruleset_id == "ruleset-private"
    multiple = classify_ruleset(
        [ruleset(name=marker.name), ruleset(name=marker.name, ruleset_id="ruleset-other")],
        private_marker_name=marker.name,
        source_ipv4_cidr="8.8.8.8/32",
    )
    assert multiple.state is RulesetMatchState.MULTIPLE


def test_strict_firewall_rejects_extra_ports_and_ruleset_drift() -> None:
    validate_strict_firewall_rules([strict_rule()], source_ipv4_cidr="8.8.8.8/32")
    with pytest.raises(L2MContractError, match="exactly one"):
        validate_strict_firewall_rules(
            [strict_rule(), {**strict_rule(), "port_range": [8888, 8888]}],
            source_ipv4_cidr="8.8.8.8/32",
        )


@pytest.mark.parametrize(
    "unsafe_source",
    ["0.0.0.0/0", "10.0.0.1/32", "not-a-cidr"],
)
def test_engine_requires_source_network_from_validated_public_32_decision(
    tmp_path: Path,
    unsafe_source: str,
) -> None:
    with pytest.raises(L2MContractError, match="binding"):
        make_observer_engine(
            tmp_path,
            suffix="UNSAFECIDR" + str(len(unsafe_source)),
            transport=FakeObserverTransport([]),
            clock=FakeClock(),
            source_ipv4_cidr=unsafe_source,
            human_decision=validated_decision(),
        )
    with pytest.raises(L2MContractError):
        validate_strict_firewall_rules(
            [{**strict_rule(), "source_network": unsafe_source}],
            source_ipv4_cidr="8.8.8.8/32",
        )


def test_engine_rejects_caller_fabricated_human_decision_capability(tmp_path: Path) -> None:
    fabricated = ValidatedHumanDecision(
        "l2m-decision-0123456789ab",
        "8.8.8.8/32",
        "a" * 64,
        ROOT,
        object(),
    )
    with pytest.raises(L2MContractError, match="binding"):
        make_observer_engine(
            tmp_path,
            suffix="FAKEDECISION",
            transport=FakeObserverTransport([]),
            clock=FakeClock(),
            human_decision=fabricated,
        )

    wrong_repository = replace(validated_decision(), repository_root=tmp_path)
    with pytest.raises(L2MContractError, match="binding"):
        make_observer_engine(
            tmp_path,
            suffix="MIXEDREPOSITORY",
            transport=FakeObserverTransport([]),
            clock=FakeClock(),
            human_decision=wrong_repository,
        )


def test_instance_ruleset_conjunction_zero_one_multiple_and_drift() -> None:
    empty = classify_instances_for_ruleset(
        [], private_ruleset_id="ruleset-private", image_selection_checkpoint_sha256="1" * 64
    )
    assert empty.state is InstanceMatchState.ZERO
    exact = classify_instances_for_ruleset(
        [instance()],
        private_ruleset_id="ruleset-private",
        image_selection_checkpoint_sha256="1" * 64,
    )
    assert exact.state is InstanceMatchState.EXACT_ONE
    assert exact.image_selection_checkpoint_sha256 == "1" * 64
    multiple = classify_instances_for_ruleset(
        [instance(), {**instance(), "id": "instance-other"}],
        private_ruleset_id="ruleset-private",
        image_selection_checkpoint_sha256="1" * 64,
    )
    assert multiple.state is InstanceMatchState.MULTIPLE
    drift = classify_instances_for_ruleset(
        [{**instance(), "ssh_key_names": ["wrong"]}],
        private_ruleset_id="ruleset-private",
        image_selection_checkpoint_sha256="1" * 64,
    )
    assert drift.state is InstanceMatchState.DRIFT
    extra_ruleset = instance()
    extra_ruleset["firewall_rulesets"] = [
        {"id": "ruleset-private"},
        {"id": "ruleset-unowned"},
    ]
    widened = classify_instances_for_ruleset(
        [extra_ruleset],
        private_ruleset_id="ruleset-private",
        image_selection_checkpoint_sha256="1" * 64,
    )
    assert widened.state is InstanceMatchState.DRIFT
    unattached = instance()
    unattached["firewall_rulesets"] = []
    missing_attachment = classify_instances_for_ruleset(
        [unattached],
        private_ruleset_id="ruleset-private",
        image_selection_checkpoint_sha256="1" * 64,
    )
    assert missing_attachment.state is InstanceMatchState.DRIFT
    assert missing_attachment.instance_ids == ()
    extra_unattached = {**instance(instance_id="instance-unattached"), "firewall_rulesets": []}
    account_ambiguous = classify_instances_for_ruleset(
        [instance(), extra_unattached],
        private_ruleset_id="ruleset-private",
        image_selection_checkpoint_sha256="1" * 64,
    )
    assert account_ambiguous.state is InstanceMatchState.DRIFT
    assert account_ambiguous.instance_ids == ("instance-private",)


def test_engine_derives_proofs_and_drives_verified_failure_cleanup(tmp_path: Path) -> None:
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    original_sha256 = firewall_semantic_sha256(original_rules)
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    image_checkpoint_sha256 = "1" * 64
    launch_sha256 = launch_configuration_sha256(
        private_image_id="raw-b",
        image_selection_checkpoint_sha256=image_checkpoint_sha256,
        image_alias=RECOMMENDED_IMAGE_ALIAS,
        image_version=RECOMMENDED_IMAGE_VERSION,
        private_ruleset_id="ruleset-private",
        private_marker_name=marker.name,
        price_cents_per_hour=129,
    )
    binding_sha256 = hashlib.sha256(
        json.dumps(
            {
                "image_selection_checkpoint_sha256": image_checkpoint_sha256,
                "instance_id": "instance-private",
                "launch_configuration_sha256": launch_sha256,
                "ruleset_id": "ruleset-private",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    jupyter_token_canary = "T07-L2M-SYNTHETIC-JUPYTER-TOKEN-CANARY"
    jupyter_url_canary = "https://fixture.invalid/T07-L2M-JUPYTER-URL-CANARY"
    unknown_scalar_canary = "T07-L2M-UNKNOWN-PROVIDER-SCALAR-CANARY"
    bound_instance = instance()
    bound_instance.update(
        {
            "jupyter_token": jupyter_token_canary,
            "jupyter_url": jupyter_url_canary,
            "provider_extension": unknown_scalar_canary,
        }
    )
    bound_instance_response = response([bound_instance])
    reader = FakeCheckpointReader(
        {
            "global_firewall_restricted": {"global_firewall_restricted": True},
            "regional_ruleset_created": {"regional_ruleset_created": True},
            "launch_clicked_once": {
                "launch_clicked_once": True,
                "approved_image_offered_for_selected_type_region": True,
                "launch_configuration_sha256": launch_sha256,
            },
            "instance_bound": {
                "instance_bound": True,
                "instance_binding_sha256": binding_sha256,
            },
            "termination_confirmed_by_user": {"termination_confirmed_by_user": True},
            "instance_terminal_verified": {
                "instance_terminal_verified": True,
                "terminal_or_absent": True,
                "launch_identity_state": "exact_one_bound",
            },
            "regional_ruleset_deleted": {
                "regional_ruleset_deleted": True,
                "regional_ruleset_absent": True,
            },
            "global_firewall_restored": {
                "global_firewall_restored": True,
                "global_firewall_semantic_sha256": original_sha256,
            },
        },
        CheckpointBinding(
            "RUN-T07-L2M-FIXTURE-0001",
            "l2m-decision-0123456789ab",
            marker.marker_alias,
        ),
        tmp_path / "consumption-0001.jsonl",
    )
    transport = FakeObserverTransport(
        [
            *preflight_responses(),
            response({"id": "global", "name": "global", "rules": [strict_rule()]}),
            response([ruleset(name=marker.name)]),
            bound_instance_response,
            response([]),
            response([]),
            response({"id": "global", "name": "global", "rules": original_rules}),
        ]
    )
    clock = FakeClock()
    journal = ObserverJournal.create(
        tmp_path / "observer.jsonl",
        schema_path=ROOT / "schemas/t07-lambda-l2m-observer-journal.schema.json",
    )
    engine = L2MReadOnlyObserverEngine(
        run_id="RUN-T07-L2M-FIXTURE-0001",
        authorization_reference="AUTH-T07-L2M-FIXTURE-0001",
        authorization_sha256="0" * 64,
        journal=journal,
        checkpoint_reader=reader,
        transport=transport,
        private_marker_name=marker.name,
        source_ipv4_cidr="8.8.8.8/32",
        human_decision=validated_decision(decision_alias="l2m-decision-0123456789ab"),
        sealed_original_global_sha256=original_sha256,
        image_selection_checkpoint_sha256=image_checkpoint_sha256,
        private_selected_image_id="raw-b",
        private_selected_ssh_key_id="ssh-key-private",
        private_selected_ssh_key_fingerprint=("SHA256:ZkAslGjFiUHdGf/WUL8rQvkib4PTvQatUV0OUQSncCA"),
        selected_image_alias=RECOMMENDED_IMAGE_ALIAS,
        selected_image_version=RECOMMENDED_IMAGE_VERSION,
        clock_ns=clock.monotonic_ns,
        sleeper=clock.sleep,
        utc_now=lambda: dt.datetime(2026, 8, 10, tzinfo=dt.UTC),
    )
    engine.begin()
    complete_preflight(engine)
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)

    def consume(kind: str, *, observation: object = None) -> None:
        engine.consume_checkpoint(
            tmp_path / f"{kind}.json",
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
            observation=observation,  # type: ignore[arg-type]
        )

    global_observation = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    consume("global_firewall_restricted", observation=global_observation)
    ruleset_observation = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_BIND,
        credential="dummy-canary-not-a-secret",
    )
    consume("regional_ruleset_created", observation=ruleset_observation)
    engine.arm_launch_window()
    consume("launch_clicked_once")
    instance_observation = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.INSTANCE_BIND,
        credential="dummy-canary-not-a-secret",
    )
    assert (
        instance_observation.response_sha256
        == hashlib.sha256(bound_instance_response.body).hexdigest()
    )
    consume("instance_bound", observation=instance_observation)

    engine.lifecycle = engine.lifecycle.incident()
    with pytest.raises(L2MContractError, match="resumed"):
        consume("termination_confirmed_by_user")
    engine.lifecycle = engine.lifecycle.resume_cleanup()
    consume("termination_confirmed_by_user")
    terminal_observation = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.TERMINATION_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    consume("instance_terminal_verified", observation=terminal_observation)
    absent_observation = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_ABSENCE,
        credential="dummy-canary-not-a-secret",
    )
    consume("regional_ruleset_deleted", observation=absent_observation)
    restored_observation = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTORE,
        credential="dummy-canary-not-a-secret",
    )
    consume("global_firewall_restored", observation=restored_observation)
    assert engine.lifecycle.phase is ManualPhase.COMPLETE
    assert not engine.lifecycle.strict_firewall_preserved
    assert len(transport.requests) == 12
    engine.stop()
    journal.close()
    retained = journal.path.read_text(encoding="utf-8")
    assert "dummy-canary-not-a-secret" not in retained
    assert "instance-private" not in retained and "ruleset-private" not in retained
    repository = tmp_path / "repository"
    destination = tmp_path / "external"
    repository.mkdir()
    destination.mkdir()
    sealed = seal_observer_evidence(
        engine,
        repository_root=repository,
    )
    archived = _copy_sealed_observer_evidence(
        sealed,
        destination_parent=destination,
        archive_id="RUN-T07-L2M-FIXTURE-0001-EVIDENCE",
        require_distinct_device=False,
    )
    assert sealed.root.is_dir() and archived.destination.is_dir()
    assert archived.destination_hashes_verified and archived.source_retained
    assert (sealed.root / "observer-journal.jsonl").read_text(encoding="utf-8") == retained
    terminal_summary = json.loads((sealed.root / "terminal-summary.json").read_bytes())
    assert terminal_summary["observer_journal_complete"] is True
    assert terminal_summary["receipt_integrity_complete"] is True
    assert terminal_summary["evidence_complete"] is True
    forbidden_provider_bytes = tuple(
        value.encode()
        for value in (
            jupyter_token_canary,
            jupyter_url_canary,
            unknown_scalar_canary,
        )
    )
    private_projection_bytes = b"".join(
        record.encoded for record in engine.private_observation_store.final_evidence.records
    )
    local_sealed_bytes = b"".join(
        path.read_bytes() for path in sealed.root.iterdir() if path.is_file()
    )
    external_sealed_bytes = b"".join(
        path.read_bytes() for path in archived.destination.iterdir() if path.is_file()
    )
    for forbidden in forbidden_provider_bytes:
        assert forbidden not in private_projection_bytes
        assert forbidden not in local_sealed_bytes
        assert forbidden not in external_sealed_bytes
    assert b'"jupyter_token"' not in private_projection_bytes
    assert b'"jupyter_url"' not in private_projection_bytes
    assert b'"provider_extension"' not in private_projection_bytes
    tampered = sealed.root / sealed.records[0].name
    tampered.chmod(0o600)
    tampered.write_bytes(b"post-seal mutation")
    tampered.chmod(0o400)
    second_destination = tmp_path / "external-second"
    second_destination.mkdir()
    with pytest.raises(L2MContractError, match="changed after sealing"):
        _copy_sealed_observer_evidence(
            sealed,
            destination_parent=second_destination,
            archive_id="RUN-T07-L2M-FIXTURE-0001-EVIDENCE-SECOND",
            require_distinct_device=False,
        )


def test_cleanup_checkpoints_advance_after_terminal_receipt_failure_and_seal_incomplete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    engine, reader, _clock, _ = prepare_bound_engine(
        tmp_path,
        suffix="RECEIPTFAIL",
        cleanup_responses=[
            response([]),
            response([]),
            response({"id": "global", "name": "global", "rules": original_rules}),
        ],
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    cleanup_types = {
        "termination_confirmed_by_user",
        "instance_terminal_verified",
        "regional_ruleset_deleted",
        "global_firewall_restored",
    }
    original_append = L2MReadOnlyObserverEngine._append_event

    def fail_cleanup_receipt(
        target: L2MReadOnlyObserverEngine,
        event_type: str,
        **kwargs: object,
    ) -> None:
        if (
            target is engine
            and event_type == "checkpoint_validated"
            and kwargs.get("checkpoint_type") in cleanup_types
        ):
            raise L2MContractError("synthetic checkpoint receipt fsync failure")
        original_append(target, event_type, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(L2MReadOnlyObserverEngine, "_append_event", fail_cleanup_receipt)

    def consume(kind: str, *, observation: object = None) -> None:
        with pytest.raises(L2MContractError, match="receipt could not be committed"):
            engine.consume_checkpoint(
                tmp_path / f"{kind}.json",
                expected_type=kind,
                expected_nonce="1" * 64,
                not_before=now,
                not_after=now + dt.timedelta(seconds=1),
                observation=observation,  # type: ignore[arg-type]
            )
        assert kind in reader.consumed

    consume("termination_confirmed_by_user")
    assert engine.lifecycle.phase is ManualPhase.TERMINATION_CONFIRMED
    terminal = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.TERMINATION_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    consume("instance_terminal_verified", observation=terminal)
    assert engine.lifecycle.phase is ManualPhase.INSTANCE_TERMINAL
    absent = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_ABSENCE,
        credential="dummy-canary-not-a-secret",
    )
    consume("regional_ruleset_deleted", observation=absent)
    assert engine.lifecycle.phase is ManualPhase.RULESET_DELETED
    restored = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTORE,
        credential="dummy-canary-not-a-secret",
    )
    consume("global_firewall_restored", observation=restored)
    assert engine.lifecycle.phase is ManualPhase.COMPLETE
    engine.stop(outcome="cleanup_complete_evidence_incomplete")
    assert not engine.receipt_integrity_complete()
    repository = tmp_path / "receipt-failure-repository"
    repository.mkdir()
    sealed = seal_observer_evidence(engine, repository_root=repository)
    summary = json.loads((sealed.root / "terminal-summary.json").read_bytes())
    assert summary["lifecycle_phase"] == "complete"
    assert summary["evidence_complete"] is False


@pytest.mark.parametrize("stage", ["prepare", "read", "advance", "apply", "receipt"])
def test_cleanup_checkpoint_transaction_preserves_authority_across_interrupts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stage: str,
) -> None:
    engine, reader, _clock, _ = prepare_bound_engine(
        tmp_path,
        suffix=f"INTERRUPT{stage.upper()}",
        cleanup_responses=[],
    )
    fired = False

    if stage == "prepare":
        original_prepare = L2MReadOnlyObserverEngine._prepare_transition

        def interrupted_prepare(
            target: L2MReadOnlyObserverEngine,
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal fired
            prepared = original_prepare(target, *args, **kwargs)  # type: ignore[arg-type]
            if target is engine and not fired:
                fired = True
                raise KeyboardInterrupt
            return prepared

        monkeypatch.setattr(
            L2MReadOnlyObserverEngine,
            "_prepare_transition",
            interrupted_prepare,
        )
    elif stage == "read":
        original_read = reader.read_once

        def interrupted_read(*args: object, **kwargs: object) -> VerifiedCheckpoint:
            nonlocal fired
            if not fired:
                fired = True
                transaction_callback = kwargs.get("on_consumed")
                assert callable(transaction_callback)

                def interrupt_after_consumption(checkpoint: VerifiedCheckpoint) -> None:
                    transaction_callback(checkpoint)
                    raise KeyboardInterrupt

                kwargs["on_consumed"] = interrupt_after_consumption
            return original_read(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(reader, "read_once", interrupted_read)
    elif stage == "advance":
        original_advance = ManualLifecycle.advance

        def interrupted_advance(
            lifecycle: ManualLifecycle,
            *args: object,
            **kwargs: object,
        ) -> ManualLifecycle:
            nonlocal fired
            advanced = original_advance(lifecycle, *args, **kwargs)  # type: ignore[arg-type]
            if not fired:
                fired = True
                raise KeyboardInterrupt
            return advanced

        monkeypatch.setattr(ManualLifecycle, "advance", interrupted_advance)
    elif stage == "apply":
        original_prepare = L2MReadOnlyObserverEngine._prepare_transition

        def apply_interrupted_prepare(
            target: L2MReadOnlyObserverEngine,
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal fired
            prepared = original_prepare(target, *args, **kwargs)  # type: ignore[arg-type]
            if target is not engine:
                return prepared
            original_apply = prepared.apply

            def interrupted_apply(checkpoint: VerifiedCheckpoint) -> None:
                nonlocal fired
                original_apply(checkpoint)
                if not fired:
                    fired = True
                    raise KeyboardInterrupt

            return replace(prepared, apply=interrupted_apply)

        monkeypatch.setattr(
            L2MReadOnlyObserverEngine,
            "_prepare_transition",
            apply_interrupted_prepare,
        )
    else:
        original_append = L2MReadOnlyObserverEngine._append_event

        def interrupted_receipt(
            target: L2MReadOnlyObserverEngine,
            event_type: str,
            **kwargs: object,
        ) -> None:
            nonlocal fired
            original_append(target, event_type, **kwargs)  # type: ignore[arg-type]
            if target is engine and event_type == "checkpoint_validated" and not fired:
                fired = True
                raise KeyboardInterrupt

        monkeypatch.setattr(L2MReadOnlyObserverEngine, "_append_event", interrupted_receipt)

    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    with pytest.raises(KeyboardInterrupt):
        engine.consume_checkpoint(
            tmp_path / "termination_confirmed_by_user.json",
            expected_type="termination_confirmed_by_user",
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
        )
    assert fired is True
    assert engine._evidence_incomplete is True
    assert engine._incident_cleanup_only is True
    events = [json.loads(line) for line in engine.journal.path.read_bytes().splitlines()]
    failures = [
        event for event in events if event["event_type"] == "checkpoint_verification_failed"
    ]
    assert failures[-1]["sanitized_outcome"] == "outcome_unknown"
    if stage == "prepare":
        assert engine.lifecycle.incident_active
        assert "termination_confirmed_by_user" not in reader.consumed
    else:
        assert engine.lifecycle.phase is ManualPhase.TERMINATION_CONFIRMED
        assert "termination_confirmed_by_user" in reader.consumed


def test_cleanup_recovery_recognizes_observation_consumed_before_transaction_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine, reader, _clock, _ = prepare_bound_engine(
        tmp_path,
        suffix="INTERRUPTAFTEROBSERVATIONCONSUMPTION",
        cleanup_responses=[response([])],
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    engine.consume_checkpoint(
        tmp_path / "termination_confirmed_by_user.json",
        expected_type="termination_confirmed_by_user",
        expected_nonce="1" * 64,
        not_before=now,
        not_after=now + dt.timedelta(seconds=1),
    )
    terminal = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.TERMINATION_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    original_consume = L2MReadOnlyObserverEngine._consume_trusted_observation
    interrupted = False

    def interrupt_after_consumption(
        target: L2MReadOnlyObserverEngine,
        observation: ObservedDocument | None,
    ) -> None:
        nonlocal interrupted
        original_consume(target, observation)
        if target is engine and observation is terminal and not interrupted:
            interrupted = True
            raise KeyboardInterrupt

    monkeypatch.setattr(
        L2MReadOnlyObserverEngine,
        "_consume_trusted_observation",
        interrupt_after_consumption,
    )
    with pytest.raises(KeyboardInterrupt):
        engine.consume_checkpoint(
            tmp_path / "instance_terminal_verified.json",
            expected_type="instance_terminal_verified",
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
            observation=terminal,
        )

    assert interrupted is True
    assert "instance_terminal_verified" in reader.consumed
    assert terminal.request_ordinal in engine._consumed_observation_ordinals
    assert engine.lifecycle.phase is ManualPhase.INSTANCE_TERMINAL
    assert engine._evidence_incomplete is True
    assert engine._incident_cleanup_only is True
    events = [json.loads(line) for line in engine.journal.path.read_bytes().splitlines()]
    assert events[-1]["event_type"] == "checkpoint_verification_failed"
    assert events[-1]["sanitized_outcome"] == "outcome_unknown"


def test_each_cleanup_transition_advances_after_private_consumption_outcome_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    engine, reader, _clock, _ = prepare_bound_engine(
        tmp_path,
        suffix="PRIVATEUNKNOWN",
        cleanup_responses=[
            response([]),
            response([]),
            response({"id": "global", "name": "global", "rules": original_rules}),
        ],
    )
    original_read = reader.read_once
    cleanup_types = {
        "termination_confirmed_by_user",
        "instance_terminal_verified",
        "regional_ruleset_deleted",
        "global_firewall_restored",
    }

    def outcome_unknown(*args: object, **kwargs: object) -> VerifiedCheckpoint:
        verified = original_read(*args, **kwargs)  # type: ignore[arg-type]
        if verified.checkpoint_type in cleanup_types:
            raise CheckpointConsumptionOutcomeUnknown(verified, content_complete=True)
        return verified

    monkeypatch.setattr(reader, "read_once", outcome_unknown)
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)

    def consume(kind: str, *, observation: object = None) -> None:
        with pytest.raises(L2MContractError, match="cleanup transition advanced"):
            engine.consume_checkpoint(
                tmp_path / f"{kind}.json",
                expected_type=kind,
                expected_nonce="1" * 64,
                not_before=now,
                not_after=now + dt.timedelta(seconds=1),
                observation=observation,  # type: ignore[arg-type]
            )

    consume("termination_confirmed_by_user")
    assert engine.lifecycle.phase is ManualPhase.TERMINATION_CONFIRMED
    terminal = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.TERMINATION_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    consume("instance_terminal_verified", observation=terminal)
    assert engine.lifecycle.phase is ManualPhase.INSTANCE_TERMINAL
    absent = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_ABSENCE,
        credential="dummy-canary-not-a-secret",
    )
    consume("regional_ruleset_deleted", observation=absent)
    assert engine.lifecycle.phase is ManualPhase.RULESET_DELETED
    restored = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTORE,
        credential="dummy-canary-not-a-secret",
    )
    consume("global_firewall_restored", observation=restored)
    assert engine.lifecycle.phase is ManualPhase.COMPLETE
    engine.stop(outcome="cleanup_complete_evidence_incomplete")
    repository = tmp_path / "private-unknown-repository"
    repository.mkdir()
    sealed = seal_observer_evidence(engine, repository_root=repository)
    summary = json.loads((sealed.root / "terminal-summary.json").read_bytes())
    assert summary["evidence_complete"] is False
    assert summary["source_integrity_verified"] is True
    assert summary["receipt_integrity_complete"] is False


def test_qualification_has_separate_command_and_download_deadlines_and_normal_path(
    tmp_path: Path,
) -> None:
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    engine, reader, clock, _ = prepare_bound_engine(
        tmp_path,
        suffix="QUALWINDOWS",
        cleanup_responses=[
            response([]),
            response([]),
            response({"id": "global", "name": "global", "rules": original_rules}),
        ],
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)

    def consume(
        kind: str,
        *,
        observation: object = None,
        qualification: object = None,
    ) -> None:
        engine.consume_checkpoint(
            tmp_path / f"{kind}.json",
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
            observation=observation,  # type: ignore[arg-type]
            qualification=qualification,  # type: ignore[arg-type]
        )

    consume("cloud_ide_opened")
    consume("qualification_command_started")
    clock.sleep(299)
    consume("qualification_command_completed")
    assert engine.lifecycle.phase is ManualPhase.QUALIFICATION_COMPLETED
    bundle_sha256 = hashlib.sha256((BUNDLE / "manifest.json").read_bytes()).hexdigest()
    assert engine.instance_binding_sha256 is not None
    binding = QualificationEvidenceBinding(
        run_id=engine.run_id,
        decision_alias=reader.binding.decision_alias,
        marker_alias=reader.binding.marker_alias,
        instance_binding_sha256=engine.instance_binding_sha256,
        authorization_reference=engine.authorization_reference,
        authorization_sha256=engine.authorization_sha256,
    )
    archive = write_success_qualification_archive(
        tmp_path / "qualification-success.zip",
        binding=binding,
        bundle_sha256=bundle_sha256,
    )
    clock.sleep(299)
    qualification = engine.validate_qualification(
        archive,
        schema_path=SCHEMA,
        expected_bundle_manifest_sha256=bundle_sha256,
        expected_binding=binding,
    )
    reader.details["qualification_bundle_downloaded"]["qualification_archive_sha256"] = (
        qualification.archive_sha256
    )
    consume("qualification_bundle_downloaded", qualification=qualification)
    assert engine.lifecycle.phase is ManualPhase.BUNDLE_DOWNLOADED

    consume("termination_confirmed_by_user")
    terminal = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.TERMINATION_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    consume("instance_terminal_verified", observation=terminal)
    absent = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_ABSENCE,
        credential="dummy-canary-not-a-secret",
    )
    consume("regional_ruleset_deleted", observation=absent)
    restored = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTORE,
        credential="dummy-canary-not-a-secret",
    )
    consume("global_firewall_restored", observation=restored)
    engine.stop()
    assert engine.lifecycle.phase is ManualPhase.COMPLETE


@pytest.mark.parametrize("late_window", ["command", "download"])
def test_each_qualification_window_rejects_elapsed_time_over_three_hundred_seconds(
    tmp_path: Path,
    late_window: str,
) -> None:
    suffix = "QUALCMDLATE" if late_window == "command" else "QUALDOWNLATE"
    engine, _reader, clock, _ = prepare_bound_engine(
        tmp_path,
        suffix=suffix,
        cleanup_responses=[],
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)

    def consume(kind: str) -> None:
        engine.consume_checkpoint(
            tmp_path / f"{kind}.json",
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
        )

    consume("cloud_ide_opened")
    consume("qualification_command_started")
    if late_window == "command":
        clock.sleep(301)
        with pytest.raises(L2MContractError, match="qualification command deadline"):
            consume("qualification_command_completed")
    else:
        consume("qualification_command_completed")
        clock.sleep(301)
        with pytest.raises(L2MContractError, match="download/validation deadline"):
            engine.validate_qualification(
                tmp_path / "not-read-after-deadline.zip",
                schema_path=SCHEMA,
                expected_bundle_manifest_sha256="a" * 64,
                expected_binding=QualificationEvidenceBinding(
                    run_id=engine.run_id,
                    decision_alias=engine.checkpoint_reader.binding.decision_alias,
                    marker_alias=engine.checkpoint_reader.binding.marker_alias,
                    instance_binding_sha256=engine.instance_binding_sha256 or "0" * 64,
                    authorization_reference=engine.authorization_reference,
                    authorization_sha256=engine.authorization_sha256,
                ),
            )
    assert engine.lifecycle.incident_active
    engine._evidence_incomplete = True
    engine._finalize_stopped_run()


def test_engine_retains_failure_archive_through_external_seal_but_never_qualifies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    engine, reader, _clock, _ = prepare_bound_engine(
        tmp_path,
        suffix="QUALFAILSEAL",
        cleanup_responses=[
            response([]),
            response([]),
            response({"id": "global", "name": "global", "rules": original_rules}),
        ],
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)

    def consume(kind: str, *, observation: object = None) -> None:
        engine.consume_checkpoint(
            tmp_path / f"{kind}.json",
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
            observation=observation,  # type: ignore[arg-type]
        )

    consume("cloud_ide_opened")
    consume("qualification_command_started")
    consume("qualification_command_completed")
    assert engine.instance_binding_sha256 is not None
    binding = QualificationEvidenceBinding(
        run_id=engine.run_id,
        decision_alias=reader.binding.decision_alias,
        marker_alias=reader.binding.marker_alias,
        instance_binding_sha256=engine.instance_binding_sha256,
        authorization_reference=engine.authorization_reference,
        authorization_sha256=engine.authorization_sha256,
    )
    bundle_sha256 = hashlib.sha256((BUNDLE / "manifest.json").read_bytes()).hexdigest()
    failure_archive = write_failure_qualification_archive(
        tmp_path / "qualification-failure.zip",
        binding=binding,
        bundle_sha256=bundle_sha256,
    )
    original_failure_validator = l2m_observer.validate_qualification_failure_archive

    def validate_held_failure_bytes(path: Path, **kwargs: object) -> dict[str, object]:
        held = kwargs.get("_encoded_archive")
        assert isinstance(held, bytes) and held == path.read_bytes()
        path.write_bytes(b"synthetic same-path replacement during validation")
        try:
            return original_failure_validator(path, **kwargs)  # type: ignore[arg-type]
        finally:
            path.write_bytes(held)

    monkeypatch.setattr(
        l2m_observer,
        "validate_qualification_failure_archive",
        validate_held_failure_bytes,
    )
    failure = engine.validate_qualification_failure(
        failure_archive,
        expected_bundle_manifest_sha256=bundle_sha256,
        expected_binding=binding,
    )
    assert failure.cleanup_complete
    assert engine._validated_qualification is None
    assert engine.lifecycle.incident_active
    engine.resume_incident_cleanup()
    consume("termination_confirmed_by_user")
    terminal = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.TERMINATION_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    consume("instance_terminal_verified", observation=terminal)
    absent = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_ABSENCE,
        credential="dummy-canary-not-a-secret",
    )
    consume("regional_ruleset_deleted", observation=absent)
    restored = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTORE,
        credential="dummy-canary-not-a-secret",
    )
    consume("global_firewall_restored", observation=restored)
    engine.stop(outcome="qualification_failed_cleanup_complete")
    repository = tmp_path / "failure-seal-repository"
    destination = tmp_path / "failure-seal-external"
    repository.mkdir()
    destination.mkdir()
    sealed = seal_observer_evidence(engine, repository_root=repository)
    assert (sealed.root / "qualification-failure-evidence.zip").read_bytes() == (
        failure_archive.read_bytes()
    )
    assert not (sealed.root / "qualification-evidence.zip").exists()
    summary = json.loads((sealed.root / "terminal-summary.json").read_bytes())
    assert summary["qualification_validated"] is False
    assert summary["qualification_failure_validated"] is True
    archived = _copy_sealed_observer_evidence(
        sealed,
        destination_parent=destination,
        archive_id="RUN-T07-L2M-FIXTURE-QUALFAILSEAL-EVIDENCE",
        require_distinct_device=False,
    )
    assert (
        archived.destination / "qualification-failure-evidence.zip"
    ).read_bytes() == failure_archive.read_bytes()


def test_failure_archive_requires_completed_command_checkpoint(tmp_path: Path) -> None:
    engine, reader, _clock, _ = prepare_bound_engine(
        tmp_path,
        suffix="FAILURENOTCOMPLETED",
        cleanup_responses=[],
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    for checkpoint_type in ("cloud_ide_opened", "qualification_command_started"):
        engine.consume_checkpoint(
            tmp_path / f"{checkpoint_type}.json",
            expected_type=checkpoint_type,
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
        )
    assert engine.instance_binding_sha256 is not None
    binding = QualificationEvidenceBinding(
        run_id=engine.run_id,
        decision_alias=reader.binding.decision_alias,
        marker_alias=reader.binding.marker_alias,
        instance_binding_sha256=engine.instance_binding_sha256,
        authorization_reference=engine.authorization_reference,
        authorization_sha256=engine.authorization_sha256,
    )
    bundle_sha256 = hashlib.sha256((BUNDLE / "manifest.json").read_bytes()).hexdigest()
    archive = write_failure_qualification_archive(
        tmp_path / "failure-before-completed-checkpoint.zip",
        binding=binding,
        bundle_sha256=bundle_sha256,
    )
    with pytest.raises(L2MContractError, match="out of order"):
        engine.validate_qualification_failure(
            archive,
            expected_bundle_manifest_sha256=bundle_sha256,
            expected_binding=binding,
        )
    assert b"evidence_validation_intent_committed" not in engine.journal.path.read_bytes()


@pytest.mark.parametrize("archive_kind", ["success", "failure"])
@pytest.mark.parametrize("interruption", ["hard_deadline", "keyboard_interrupt"])
def test_qualification_archive_validation_is_hard_bounded_and_interrupt_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    archive_kind: str,
    interruption: str,
) -> None:
    suffix = f"{archive_kind.upper()}{interruption.upper()}"
    engine, _reader, binding, bundle_sha256, archive = prepare_qualification_completed_engine(
        tmp_path,
        suffix=suffix,
        archive_kind=archive_kind,
    )
    validator_name = (
        "validate_qualification_archive"
        if archive_kind == "success"
        else "validate_qualification_failure_archive"
    )

    def interrupted_validation(*args: object, **kwargs: object) -> dict[str, object]:
        del args, kwargs
        if interruption == "keyboard_interrupt":
            raise KeyboardInterrupt
        handler = signal.getsignal(signal.SIGALRM)
        assert callable(handler)
        handler(signal.SIGALRM, None)
        raise AssertionError("hard alarm returned")

    monkeypatch.setattr(l2m_observer, validator_name, interrupted_validation)
    if interruption == "keyboard_interrupt":
        with pytest.raises(KeyboardInterrupt):
            if archive_kind == "success":
                engine.validate_qualification(
                    archive,
                    schema_path=SCHEMA,
                    expected_bundle_manifest_sha256=bundle_sha256,
                    expected_binding=binding,
                )
            else:
                engine.validate_qualification_failure(
                    archive,
                    expected_bundle_manifest_sha256=bundle_sha256,
                    expected_binding=binding,
                )
        expected_outcome = "outcome_unknown"
    else:
        with pytest.raises(L2MContractError, match="evidence validation failed"):
            if archive_kind == "success":
                engine.validate_qualification(
                    archive,
                    schema_path=SCHEMA,
                    expected_bundle_manifest_sha256=bundle_sha256,
                    expected_binding=binding,
                )
            else:
                engine.validate_qualification_failure(
                    archive,
                    expected_bundle_manifest_sha256=bundle_sha256,
                    expected_binding=binding,
                )
        expected_outcome = "timeout"
    events = [json.loads(line) for line in engine.journal.path.read_bytes().splitlines()]
    failures = [event for event in events if event["event_type"] == "evidence_validation_failed"]
    assert failures[-1]["sanitized_outcome"] == expected_outcome
    assert engine._evidence_incomplete is True
    assert engine.lifecycle.incident_active
    assert engine._incident_cleanup_only is True
    assert engine._validated_qualification is None
    assert engine._validated_qualification_failure is None


@pytest.mark.parametrize("archive_kind", ["success", "failure"])
def test_qualification_validation_receipt_is_inside_hard_alarm_and_interrupt_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    archive_kind: str,
) -> None:
    engine, _reader, binding, bundle_sha256, archive = prepare_qualification_completed_engine(
        tmp_path,
        suffix=f"{archive_kind.upper()}RECEIPTINTERRUPT",
        archive_kind=archive_kind,
    )
    original_append = L2MReadOnlyObserverEngine._append_event
    interrupted = False

    def interrupt_validated_receipt(
        target: L2MReadOnlyObserverEngine,
        event_type: str,
        **kwargs: object,
    ) -> None:
        nonlocal interrupted
        original_append(target, event_type, **kwargs)  # type: ignore[arg-type]
        if target is engine and event_type == "evidence_validated" and not interrupted:
            interrupted = True
            assert callable(signal.getsignal(signal.SIGALRM))
            raise KeyboardInterrupt

    monkeypatch.setattr(
        L2MReadOnlyObserverEngine,
        "_append_event",
        interrupt_validated_receipt,
    )
    with pytest.raises(KeyboardInterrupt):
        if archive_kind == "success":
            engine.validate_qualification(
                archive,
                schema_path=SCHEMA,
                expected_bundle_manifest_sha256=bundle_sha256,
                expected_binding=binding,
            )
        else:
            engine.validate_qualification_failure(
                archive,
                expected_bundle_manifest_sha256=bundle_sha256,
                expected_binding=binding,
            )

    events = [json.loads(line) for line in engine.journal.path.read_bytes().splitlines()]
    assert interrupted is True
    assert [event["event_type"] for event in events[-2:]] == [
        "evidence_validated",
        "evidence_validation_failed",
    ]
    assert events[-1]["sanitized_outcome"] == "outcome_unknown"
    assert engine._evidence_incomplete is True
    assert engine._incident_cleanup_only is True
    assert engine._validated_qualification is None
    assert engine._validated_qualification_failure is None


@pytest.mark.parametrize(
    ("launch_state", "launch_rows", "terminal_rows"),
    [
        (InstanceMatchState.ZERO, [], [[]]),
        (
            InstanceMatchState.MULTIPLE,
            [
                instance(instance_id="instance-private-a"),
                instance(instance_id="instance-private-b"),
            ],
            [[], []],
        ),
    ],
)
def test_unbound_or_ambiguous_launch_requires_fresh_terminal_and_attachment_absence(
    tmp_path: Path,
    launch_state: InstanceMatchState,
    launch_rows: list[dict[str, object]],
    terminal_rows: list[list[dict[str, object]]],
) -> None:
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    original_sha256 = firewall_semantic_sha256(original_rules)
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    suffix = launch_state.name
    launch_sha256 = launch_configuration_sha256(
        private_image_id="raw-b",
        image_selection_checkpoint_sha256="2" * 64,
        image_alias=RECOMMENDED_IMAGE_ALIAS,
        image_version=RECOMMENDED_IMAGE_VERSION,
        private_ruleset_id="ruleset-private",
        private_marker_name=marker.name,
        price_cents_per_hour=129,
    )
    reader = FakeCheckpointReader(
        {
            "global_firewall_restricted": {"global_firewall_restricted": True},
            "regional_ruleset_created": {"regional_ruleset_created": True},
            "launch_clicked_once": {
                "launch_clicked_once": True,
                "approved_image_offered_for_selected_type_region": True,
                "launch_configuration_sha256": launch_sha256,
            },
            "instance_bound": {
                "instance_bound": True,
                "instance_binding_sha256": "9" * 64,
            },
            "termination_confirmed_by_user": {"termination_confirmed_by_user": True},
            "instance_terminal_verified": {
                "instance_terminal_verified": True,
                "terminal_or_absent": True,
                "launch_identity_state": launch_state.value,
            },
            "regional_ruleset_deleted": {
                "regional_ruleset_deleted": True,
                "regional_ruleset_absent": True,
            },
            "global_firewall_restored": {
                "global_firewall_restored": True,
                "global_firewall_semantic_sha256": original_sha256,
            },
        },
        CheckpointBinding(
            f"RUN-T07-L2M-FIXTURE-{suffix}",
            "l2m-decision-0123456789ab",
            marker.marker_alias,
        ),
        tmp_path / f"consumption-{suffix}.jsonl",
    )
    transport = FakeObserverTransport(
        [
            *preflight_responses(),
            response({"id": "global", "name": "global", "rules": [strict_rule()]}),
            response([ruleset(name=marker.name)]),
            response(launch_rows),
            *(response(rows) for rows in terminal_rows),
            response([]),
            response({"id": "global", "name": "global", "rules": original_rules}),
        ]
    )
    clock = FakeClock()
    engine = make_observer_engine(
        tmp_path,
        suffix=suffix,
        transport=transport,
        clock=clock,
        checkpoint_reader=reader,
    )
    engine.begin()
    complete_preflight(engine)
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)

    def consume(kind: str, *, observation: object = None) -> None:
        engine.consume_checkpoint(
            tmp_path / f"{kind}.json",
            expected_type=kind,
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
            observation=observation,  # type: ignore[arg-type]
        )

    global_observation = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    consume("global_firewall_restricted", observation=global_observation)
    ruleset_observation = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_BIND,
        credential="dummy-canary-not-a-secret",
    )
    consume("regional_ruleset_created", observation=ruleset_observation)
    engine.arm_launch_window()
    consume("launch_clicked_once")
    launch_observation = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.INSTANCE_BIND,
        credential="dummy-canary-not-a-secret",
    )
    with pytest.raises(L2MContractError, match="evidence verification failed"):
        consume("instance_bound", observation=launch_observation)
    assert engine.lifecycle.incident_active
    assert engine._launch_match_state is launch_state
    assert "instance_bound" not in reader.consumed
    if launch_state is InstanceMatchState.MULTIPLE:
        assert len(engine._ambiguous_instance_ids) == 2
    engine.resume_incident_cleanup()
    terminal_observation = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.TERMINATION_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    if launch_state is InstanceMatchState.ZERO:
        consume("instance_terminal_verified", observation=terminal_observation)
        assert "termination_confirmed_by_user" not in reader.consumed
    else:
        with pytest.raises(L2MContractError, match="evidence verification failed"):
            consume("instance_terminal_verified", observation=terminal_observation)
        assert engine.lifecycle.incident_active
        assert "instance_terminal_verified" not in reader.consumed
        engine.resume_incident_cleanup()
        consume("termination_confirmed_by_user")
        terminal_observation = engine.observe(
            ObserverOperation.LIST_INSTANCES,
            phase=ObserverPhase.TERMINATION_VERIFY,
            credential="dummy-canary-not-a-secret",
        )
        consume("instance_terminal_verified", observation=terminal_observation)
    absent_observation = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_ABSENCE,
        credential="dummy-canary-not-a-secret",
    )
    consume("regional_ruleset_deleted", observation=absent_observation)
    restored_observation = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTORE,
        credential="dummy-canary-not-a-secret",
    )
    consume("global_firewall_restored", observation=restored_observation)
    assert engine.lifecycle.phase is ManualPhase.COMPLETE
    engine._evidence_incomplete = True
    engine._finalize_stopped_run()


def test_held_destination_descriptor_prevents_path_swap_redirection(tmp_path: Path) -> None:
    repository = tmp_path / "repository-held"
    repository.mkdir()
    store = L2MObserverEvidenceStore.create(
        repository,
        run_id="RUN-T07-L2M-FIXTURE-0010",
        authorization_reference="AUTH-T07-L2M-FIXTURE-0010",
        authorization_sha256="0" * 64,
    )
    try:
        store.write_record("fixture.json", b'{"fixture":true}')
        sealed = store.seal()
    finally:
        store.close()
    destination = tmp_path / "external-held"
    destination.mkdir()
    destination_fd = os.open(destination, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    destination_identity = os.fstat(destination_fd)
    source_fd = os.open(sealed.root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    held_path = tmp_path / "external-held-original"
    destination.rename(held_path)
    destination.mkdir()
    try:
        _copy_sealed_observer_evidence_held(
            sealed,
            source_fd=source_fd,
            destination_fd=destination_fd,
            destination_parent=destination,
            destination_device=destination_identity.st_dev,
            destination_inode=destination_identity.st_ino,
            archive_id="RUN-T07-L2M-FIXTURE-0010-EVIDENCE",
            require_distinct_device=False,
        )
    finally:
        os.close(source_fd)
        os.close(destination_fd)
    assert (held_path / "RUN-T07-L2M-FIXTURE-0010-EVIDENCE").is_dir()
    assert not (destination / "RUN-T07-L2M-FIXTURE-0010-EVIDENCE").exists()


def test_archive_phase_has_independent_three_hundred_second_deadline(tmp_path: Path) -> None:
    clock = FakeClock()
    engine = make_observer_engine(
        tmp_path,
        suffix="0011",
        transport=FakeObserverTransport([]),
        clock=clock,
    )
    engine.begin()
    engine.stop()
    engine.journal.close()
    clock.sleep(301)
    repository = tmp_path / "repository-late"
    repository.mkdir()
    with pytest.raises(L2MContractError, match="archive wall cap"):
        seal_observer_evidence(
            engine,
            repository_root=repository,
        )


@pytest.mark.parametrize("source_kind", ["journal", "checkpoint"])
def test_sealing_rejects_swapped_engine_owned_evidence_source(
    tmp_path: Path,
    source_kind: str,
) -> None:
    engine = make_observer_engine(
        tmp_path,
        suffix="0013" if source_kind == "journal" else "0014",
        transport=FakeObserverTransport([]),
        clock=FakeClock(),
    )
    engine.begin()
    engine.stop()
    source = (
        engine.journal.final_evidence.path
        if source_kind == "journal"
        else engine.checkpoint_reader.final_evidence.path
    )
    source.rename(source.with_suffix(source.suffix + ".original"))
    source.write_bytes(b"substituted evidence\n")
    source.chmod(0o600)
    repository = tmp_path / f"repository-swap-{source_kind}"
    repository.mkdir()
    with pytest.raises(L2MContractError, match="source changed"):
        seal_observer_evidence(engine, repository_root=repository)


def test_manual_lifecycle_rejects_caller_fabricated_transition_proof() -> None:
    checkpoint = VerifiedCheckpoint(
        checkpoint_type="global_firewall_restricted",
        observed_at_utc=dt.datetime(2026, 8, 10, tzinfo=dt.UTC),
        encoded_sha256="1" * 64,
        launch_clicked_once=False,
        details={"global_firewall_restricted": True},
    )
    fabricated = TransitionProof(
        checkpoint_type=checkpoint.checkpoint_type,
        checkpoint_sha256=checkpoint.encoded_sha256,
        verification_kind=TransitionVerificationKind.GLOBAL_FIREWALL_EXACT,
        evidence_sha256="2" * 64,
        _issuer=object(),
    )
    with pytest.raises(L2MContractError, match="proof"):
        ManualLifecycle().advance(checkpoint, fabricated)


def test_global_firewall_restoration_and_zero_prelaunch_are_observed() -> None:
    original = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    semantic_hash = firewall_semantic_sha256(original)
    verify_global_firewall_restoration(
        list(reversed(original)), sealed_original_semantic_sha256=semantic_hash
    )
    with pytest.raises(L2MContractError, match="not exactly restored"):
        verify_global_firewall_restoration(
            [strict_rule()], sealed_original_semantic_sha256=semantic_hash
        )
    require_zero_prelaunch_instances([])
    with pytest.raises(L2MContractError, match="not instance-empty"):
        require_zero_prelaunch_instances([instance()])


def test_observer_surface_is_get_only_and_finitely_budgeted() -> None:
    requests = [
        observer_request(operation)
        for operation in ObserverOperation
        if "get_" not in operation.value or operation is ObserverOperation.GET_GLOBAL_FIREWALL
    ]
    requests.extend(
        [
            observer_request(
                ObserverOperation.GET_INSTANCE, private_resource_id="instance-private"
            ),
            observer_request(ObserverOperation.GET_RULESET, private_resource_id="ruleset-private"),
        ]
    )
    assert all(
        request.method == "GET" and request.host == "cloud.lambda.ai" for request in requests
    )
    budget = ObserverBudget()
    request = observer_request(ObserverOperation.LIST_INSTANCES)
    for ordinal in range(OBSERVER_PHASE_GET_LIMITS[ObserverPhase.INSTANCE_BIND]):
        started = ordinal * 1_000_000_000
        budget = budget.consume(
            request,
            phase=ObserverPhase.INSTANCE_BIND,
            response_bytes=1,
            started_monotonic_ns=started,
            finished_monotonic_ns=started + 1_000_000,
        )
    with pytest.raises(L2MContractError, match="GET cap"):
        budget.consume(
            request,
            phase=ObserverPhase.INSTANCE_BIND,
            response_bytes=1,
            started_monotonic_ns=20_000_000_000,
            finished_monotonic_ns=20_001_000_000,
        )
    assert sum(OBSERVER_PHASE_GET_LIMITS.values()) == MAX_OBSERVER_GETS
    journal_schema = json.loads(
        (ROOT / "schemas/t07-lambda-l2m-observer-journal.schema.json").read_bytes()
    )
    assert journal_schema["properties"]["request_ordinal"]["maximum"] == MAX_OBSERVER_GETS
    assert journal_schema["properties"]["source_request_ordinal"]["maximum"] == (MAX_OBSERVER_GETS)
    with pytest.raises(L2MContractError, match="not allowed"):
        ObserverBudget().consume(
            request,
            phase=ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
            response_bytes=1,
            started_monotonic_ns=0,
            finished_monotonic_ns=1_000_000,
        )
    first = ObserverBudget().consume(
        request,
        phase=ObserverPhase.INSTANCE_BIND,
        response_bytes=1,
        started_monotonic_ns=0,
        finished_monotonic_ns=1_000_000,
    )
    with pytest.raises(L2MContractError, match="spacing"):
        first.consume(
            request,
            phase=ObserverPhase.INSTANCE_BIND,
            response_bytes=1,
            started_monotonic_ns=999_999_999,
            finished_monotonic_ns=1_000_999_999,
        )
    late_cleanup = first.consume(
        request,
        phase=ObserverPhase.TERMINATION_VERIFY,
        response_bytes=1,
        started_monotonic_ns=6_000_000_000_000,
        finished_monotonic_ns=6_000_001_000_000,
    )
    assert late_cleanup.elapsed_ms == 6_000_001
    assert MAX_OBSERVER_WALL_SECONDS == 6_300
    with pytest.raises(L2MContractError, match="wall cap"):
        late_cleanup.consume(
            observer_request(ObserverOperation.GET_GLOBAL_FIREWALL),
            phase=ObserverPhase.INCIDENT,
            response_bytes=1,
            started_monotonic_ns=6_301_000_000_000,
            finished_monotonic_ns=6_301_001_000_000,
        )


def test_documented_gate_authorization_reference_is_accepted() -> None:
    reference = "AUTH-T07-GATE-L2M-CURRENT-TURN-2026-08-11"
    assert l2m_observer._AUTHORIZATION_REFERENCE.fullmatch(reference) is not None


def test_engine_rejects_wrong_phase_and_exhausted_caps_before_transport(
    tmp_path: Path,
) -> None:
    wrong_phase_transport = FakeObserverTransport([preflight_responses()[0]])
    wrong_phase = make_observer_engine(
        tmp_path,
        suffix="0003",
        transport=wrong_phase_transport,
        clock=FakeClock(),
    )
    wrong_phase.begin()
    with pytest.raises(L2MContractError, match="preflight must complete"):
        wrong_phase.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.INSTANCE_BIND,
            credential="dummy-canary-not-a-secret",
        )
    assert wrong_phase_transport.requests == []
    wrong_phase.stop()
    wrong_phase.journal.close()

    for suffix, budget, message in (
        ("0004", ObserverBudget(request_count=MAX_OBSERVER_GETS), "GET cap"),
        (
            "0005",
            ObserverBudget(response_bytes=MAX_AGGREGATE_RESPONSE_BYTES),
            "aggregate response cap",
        ),
    ):
        transport = FakeObserverTransport([preflight_responses()[0]])
        engine = make_observer_engine(
            tmp_path,
            suffix=suffix,
            transport=transport,
            clock=FakeClock(),
        )
        engine.begin()
        engine.budget = budget
        with pytest.raises(L2MContractError, match=message):
            engine.observe(
                ObserverOperation.LIST_IMAGES,
                phase=ObserverPhase.PREFLIGHT,
                credential="dummy-canary-not-a-secret",
            )
        assert transport.requests == []
        engine._evidence_incomplete = True
        engine._finalize_stopped_run()
        engine.journal.close()


def test_preflight_passes_only_after_six_exact_observations(tmp_path: Path) -> None:
    transport = FakeObserverTransport(preflight_responses())
    engine = make_observer_engine(
        tmp_path,
        suffix="0006",
        transport=transport,
        clock=FakeClock(),
    )
    engine.begin()
    assert "preflight_passed" not in engine.journal.path.read_text()
    for operation in (
        ObserverOperation.LIST_IMAGES,
        ObserverOperation.LIST_INSTANCE_TYPES,
        ObserverOperation.LIST_SSH_KEYS,
        ObserverOperation.LIST_INSTANCES,
        ObserverOperation.LIST_RULESETS,
    ):
        engine.observe(
            operation,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )
        assert "preflight_passed" not in engine.journal.path.read_text()
    engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.PREFLIGHT,
        credential="dummy-canary-not-a-secret",
    )
    assert "preflight_passed" in engine.journal.path.read_text()
    engine._evidence_incomplete = True
    engine._finalize_stopped_run()
    engine.journal.close()


def test_preflight_rejects_same_named_ssh_key_with_different_public_fingerprint(
    tmp_path: Path,
) -> None:
    responses = preflight_responses()
    responses[2] = response(
        [
            {
                "id": "ssh-key-private",
                "name": "fractal-lambda-codex",
                "public_key": (
                    "ssh-ed25519 "
                    "AAAAC3NzaC1lZDI1NTE5AAAAIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4e"
                ),
            }
        ]
    )
    engine = make_observer_engine(
        tmp_path,
        suffix="SSH-FINGERPRINT-DRIFT",
        transport=FakeObserverTransport(responses),
        clock=FakeClock(),
    )
    engine.begin()
    with pytest.raises(L2MContractError, match="SSH key identity"):
        complete_preflight(engine)
    assert engine.stopped
    assert b"public_key" not in engine.journal.path.read_bytes()


def test_l23_fresh_original_global_seal_is_required_and_durable(
    tmp_path: Path,
) -> None:
    original_rules = [
        {
            "protocol": "tcp",
            "port_range": [443, 443],
            "source_network": "0.0.0.0/0",
            "description": "original fixture",
        }
    ]
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    reader = FakeCheckpointReader(
        {
            "launch_wizard_image_offered": {
                "launch_wizard_image_offered": True,
                "selected_instance_type": "gpu_1x_a10",
                "selected_region": "us-east-1",
                "selected_image_alias": "img-0032",
                "selected_image_version": "22.4.5-2141",
            },
            "global_firewall_restricted": {"global_firewall_restricted": True},
        },
        CheckpointBinding(
            "RUN-T07-L2M-FIXTURE-FRESH-GLOBAL-SEAL",
            "l2m-decision-0123456789ab",
            marker.marker_alias,
        ),
        tmp_path / "consumption-fresh-global-seal.jsonl",
    )
    transport = FakeObserverTransport(
        [
            *preflight_responses(),
            response({"id": "global", "name": "global", "rules": original_rules}),
            response({"id": "global", "name": "global", "rules": [strict_rule()]}),
        ]
    )
    engine = make_observer_engine(
        tmp_path,
        suffix="FRESH-GLOBAL-SEAL",
        transport=transport,
        clock=FakeClock(),
        checkpoint_reader=reader,
        require_l23_auxiliary_checkpoints=True,
    )
    engine.begin()
    complete_preflight(engine)
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    engine.consume_auxiliary_checkpoint(
        tmp_path / "launch_wizard_image_offered.json",
        expected_type="launch_wizard_image_offered",
        expected_nonce="1" * 64,
        not_before=now,
        not_after=now + dt.timedelta(seconds=1),
    )
    fresh = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.ORIGINAL_GLOBAL_SEAL,
        credential="dummy-canary-not-a-secret",
    )
    engine.seal_original_global_firewall(fresh)
    restricted = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    engine.consume_checkpoint(
        tmp_path / "global_firewall_restricted.json",
        expected_type="global_firewall_restricted",
        expected_nonce="1" * 64,
        not_before=now,
        not_after=now + dt.timedelta(seconds=1),
        observation=restricted,
    )
    assert engine.lifecycle.phase is ManualPhase.GLOBAL_RESTRICTED
    events = [json.loads(line) for line in engine.journal.path.read_bytes().splitlines()]
    assert any(
        event["observer_phase"] == "original_global_seal"
        and event["semantic_outcome"] == "original_global_firewall_sealed"
        for event in events
    )
    engine.abort_for_separately_authorized_manual_cleanup()


def test_l23_offeredness_mismatch_blocks_before_any_mutation_state(tmp_path: Path) -> None:
    clock = FakeClock()
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    reader = FakeCheckpointReader(
        {
            "launch_wizard_image_offered": {
                "launch_wizard_image_offered": True,
                "selected_instance_type": "gpu_1x_a10",
                "selected_region": "us-east-1",
                "selected_image_alias": "img-0032",
                "selected_image_version": "wrong-version",
            }
        },
        CheckpointBinding(
            "RUN-T07-L2M-FIXTURE-L23-OFFER-MISMATCH",
            "l2m-decision-0123456789ab",
            marker.marker_alias,
        ),
        tmp_path / "consumption-l23-offer-mismatch.jsonl",
    )
    engine = make_observer_engine(
        tmp_path,
        suffix="L23-OFFER-MISMATCH",
        transport=FakeObserverTransport(preflight_responses(), clock=clock),
        clock=clock,
        checkpoint_reader=reader,
        require_l23_auxiliary_checkpoints=True,
    )
    engine.begin()
    complete_preflight(engine)
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    with pytest.raises(L2MContractError, match="auxiliary checkpoint validation"):
        engine.consume_auxiliary_checkpoint(
            tmp_path / "launch_wizard_image_offered.json",
            expected_type="launch_wizard_image_offered",
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
        )
    assert engine.lifecycle.phase is ManualPhase.PREFLIGHT
    assert not engine.lifecycle.incident_active
    assert reader.consumed == []
    engine.stop()


def test_l23_offeredness_is_required_before_global_transition(tmp_path: Path) -> None:
    clock = FakeClock()
    engine = make_observer_engine(
        tmp_path,
        suffix="L23-OFFER-REQUIRED",
        transport=FakeObserverTransport(
            [
                *preflight_responses(),
                response({"id": "global", "name": "global", "rules": [strict_rule()]}),
            ],
            clock=clock,
        ),
        clock=clock,
        require_l23_auxiliary_checkpoints=True,
    )
    engine.begin()
    complete_preflight(engine)
    observed = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    with pytest.raises(L2MContractError, match="preparation failed"):
        engine.consume_checkpoint(
            tmp_path / "global_firewall_restricted.json",
            expected_type="global_firewall_restricted",
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
            observation=observed,
        )
    assert engine.lifecycle.phase is ManualPhase.GLOBAL_MUTATION_UNVERIFIED
    assert engine.lifecycle.incident_active
    engine.abort_for_separately_authorized_manual_cleanup(
        possible_user_mutation_phase=ObserverPhase.GLOBAL_RESTRICTED_VERIFY
    )
    assert engine.stopped and not engine.receipt_integrity_complete()


def test_l23_launch_and_qualification_require_auxiliary_attestations(tmp_path: Path) -> None:
    clock = FakeClock()
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    launch_hash = launch_configuration_sha256(
        private_image_id="raw-b",
        image_selection_checkpoint_sha256="2" * 64,
        image_alias=RECOMMENDED_IMAGE_ALIAS,
        image_version=RECOMMENDED_IMAGE_VERSION,
        private_ruleset_id="ruleset-private",
        private_marker_name=marker.name,
        price_cents_per_hour=129,
    )
    reader = FakeCheckpointReader(
        {
            "launch_configuration_selected": {
                "launch_configuration_selected": True,
                "launch_configuration_sha256": launch_hash,
            },
            "qualification_bundle_uploaded": {
                "qualification_bundle_uploaded": True,
                "qualification_bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256,
            },
            "qualification_command_started": {"qualification_command_started": True},
        },
        CheckpointBinding(
            "RUN-T07-L2M-FIXTURE-L23-AUXILIARY",
            "l2m-decision-0123456789ab",
            marker.marker_alias,
        ),
        tmp_path / "consumption-l23-auxiliary.jsonl",
    )
    engine = make_observer_engine(
        tmp_path,
        suffix="L23-AUXILIARY",
        transport=FakeObserverTransport([], clock=clock),
        clock=clock,
        checkpoint_reader=reader,
        require_l23_auxiliary_checkpoints=True,
    )
    engine.begin()
    engine._preflight_complete = True
    engine._preflight_price_cents_per_hour = 129
    engine.private_ruleset_id = "ruleset-private"
    engine.lifecycle = ManualLifecycle(
        ManualPhase.RULESET_CREATED,
        True,
        False,
        engine._proof_issuer,
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    with pytest.raises(L2MContractError, match="cannot be armed"):
        engine.arm_launch_window()
    engine.consume_auxiliary_checkpoint(
        tmp_path / "launch_configuration_selected.json",
        expected_type="launch_configuration_selected",
        expected_nonce="1" * 64,
        not_before=now,
        not_after=now + dt.timedelta(seconds=1),
    )
    engine.arm_launch_window()
    assert engine.lifecycle.phase is ManualPhase.LAUNCH_OUTCOME_UNVERIFIED

    engine.lifecycle = ManualLifecycle(
        ManualPhase.CLOUD_IDE_OPENED,
        True,
        False,
        engine._proof_issuer,
    )
    engine.consume_auxiliary_checkpoint(
        tmp_path / "qualification_bundle_uploaded.json",
        expected_type="qualification_bundle_uploaded",
        expected_nonce="1" * 64,
        not_before=now,
        not_after=now + dt.timedelta(seconds=1),
    )
    engine.consume_checkpoint(
        tmp_path / "qualification_command_started.json",
        expected_type="qualification_command_started",
        expected_nonce="1" * 64,
        not_before=now,
        not_after=now + dt.timedelta(seconds=1),
    )
    assert engine.lifecycle.phase is ManualPhase.QUALIFICATION_STARTED
    engine.abort_for_separately_authorized_manual_cleanup()


def test_preflight_allows_unrelated_instance_types_but_binds_selected_fields(
    tmp_path: Path,
) -> None:
    outcomes = preflight_responses()
    unrelated = instance_type_record()
    unrelated["name"] = "gpu_8x_unrelated"
    unrelated["price_cents_per_hour"] = 9_999
    outcomes[1] = response(
        {
            "gpu_1x_a10": {
                "instance_type": instance_type_record(),
                "regions_with_capacity_available": [
                    {"name": "us-east-1", "description": "fixture"}
                ],
            },
            "gpu_8x_unrelated": {
                "instance_type": unrelated,
                "regions_with_capacity_available": [
                    {"name": "us-west-1", "description": "fixture"}
                ],
            },
        }
    )
    engine = make_observer_engine(
        tmp_path,
        suffix="0040",
        transport=FakeObserverTransport(outcomes),
        clock=FakeClock(),
    )
    engine.begin()
    complete_preflight(engine)
    assert engine._preflight_complete
    assert engine._preflight_price_cents_per_hour == 129
    engine._evidence_incomplete = True
    engine._finalize_stopped_run()


def test_deadline_failure_after_intent_never_commits_send_started(tmp_path: Path) -> None:
    transport = FakeObserverTransport([preflight_responses()[0]])
    engine = make_observer_engine(
        tmp_path,
        suffix="0012",
        transport=transport,
        clock=DeadlineBeforeSendClock(),
    )
    engine.begin()
    with pytest.raises(L2MContractError, match="before transport entry"):
        engine.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )
    assert transport.requests == [] and engine.stopped
    events = [json.loads(line) for line in engine.journal.path.read_text().splitlines()]
    assert [event["event_type"] for event in events] == [
        "preflight_started",
        "observation_intent_committed",
        "run_stopped",
    ]
    engine.journal.close()


@pytest.mark.parametrize(
    ("failure_stage", "failure_mode"),
    [
        ("pre_send", "partial_write_interrupt"),
        ("pre_send", "persistent_partial_interrupt"),
        ("pre_send", "fsync_interrupt"),
        ("post_response", "partial_write_interrupt"),
        ("post_response", "fsync_interrupt"),
    ],
)
def test_observer_journal_interrupt_burns_run_and_retains_exact_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_stage: str,
    failure_mode: str,
) -> None:
    transport = FakeObserverTransport([preflight_responses()[0]])
    engine = make_observer_engine(
        tmp_path,
        suffix=f"JOURNAL{failure_stage.upper()}{failure_mode.upper()}",
        transport=transport,
        clock=FakeClock(),
    )
    engine.begin()
    target = engine.journal._descriptor
    target_event = (
        b'"event_type":"observation_intent_committed"'
        if failure_stage == "pre_send"
        else b'"event_type":"observation_completed"'
    )
    original_write = os.write
    original_fsync = os.fsync
    faulted = False
    fsync_armed = False

    def write_with_interrupt(descriptor: int, value: object) -> int:
        nonlocal faulted, fsync_armed
        encoded = bytes(value)  # type: ignore[arg-type]
        if descriptor == target and failure_mode == "persistent_partial_interrupt":
            if not faulted and target_event in encoded:
                faulted = True
                original_write(descriptor, encoded[: max(1, len(encoded) // 2)])
            if faulted:
                raise KeyboardInterrupt
        if descriptor == target and target_event in encoded and not faulted:
            if failure_mode == "partial_write_interrupt":
                faulted = True
                original_write(descriptor, encoded[: max(1, len(encoded) // 2)])
                raise KeyboardInterrupt
            fsync_armed = True
        return original_write(descriptor, encoded)

    def fsync_with_interrupt(descriptor: int) -> None:
        nonlocal faulted, fsync_armed
        if descriptor == target and fsync_armed and not faulted:
            faulted = True
            fsync_armed = False
            raise SystemExit(23)
        original_fsync(descriptor)

    monkeypatch.setattr(os, "write", write_with_interrupt)
    monkeypatch.setattr(os, "fsync", fsync_with_interrupt)
    with pytest.raises(L2MContractError):
        engine.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )

    assert faulted and engine.stopped
    assert engine.budget.request_count == 1
    assert engine._burned_request_ordinals == {1}
    assert len(transport.requests) == (0 if failure_stage == "pre_send" else 1)
    assert engine.journal.closed and not engine.journal.final_evidence.complete
    retained = engine.journal.final_evidence.encoded
    assert retained == engine.journal.path.read_bytes()
    if failure_mode == "persistent_partial_interrupt":
        record_start = engine.journal._unknown_record_start
        expected_record = engine.journal._unknown_record
        assert record_start is not None and expected_record is not None
        assert retained[record_start:]
        assert retained[record_start:] == expected_record[: len(retained) - record_start]
        assert json.loads(retained[:record_start])["event_type"] == "preflight_started"
    else:
        assert retained.endswith(b"\n")
        events = [json.loads(line) for line in retained.splitlines()]
        assert events[-1]["event_type"] == target_event.decode().split('"')[3]
        assert [event["event_sequence"] for event in events] == list(range(1, len(events) + 1))
    with pytest.raises(L2MContractError, match="active run"):
        engine.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )
    monkeypatch.setattr(os, "write", original_write)
    monkeypatch.setattr(os, "fsync", original_fsync)
    repository = tmp_path / f"journal-prefix-repository-{failure_stage}-{failure_mode}"
    destination = tmp_path / f"journal-prefix-external-{failure_stage}-{failure_mode}"
    repository.mkdir()
    destination.mkdir()
    sealed = seal_observer_evidence(engine, repository_root=repository)
    archived = _copy_sealed_observer_evidence(
        sealed,
        destination_parent=destination,
        archive_id=f"JOURNAL-PREFIX-{failure_stage}-{failure_mode}",
        require_distinct_device=False,
    )
    assert (sealed.root / "observer-journal.jsonl").read_bytes() == retained
    assert (archived.destination / "observer-journal.jsonl").read_bytes() == retained
    terminal_summary = json.loads((sealed.root / "terminal-summary.json").read_bytes())
    assert terminal_summary["observer_journal_complete"] is False
    assert terminal_summary["receipt_integrity_complete"] is False
    assert terminal_summary["evidence_complete"] is False
    assert archived.destination_hashes_verified and archived.source_retained


def test_actual_transport_entries_remain_one_second_apart_after_slow_fsync(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    transport = FakeObserverTransport(preflight_responses()[:2], clock=clock)
    engine = make_observer_engine(
        tmp_path,
        suffix="0013",
        transport=transport,
        clock=clock,
    )
    original_append = engine.journal.append
    delayed = False

    def append_with_one_slow_fsync(event: dict[str, object]) -> None:
        nonlocal delayed
        original_append(event)
        if event["event_type"] == "observation_send_started" and not delayed:
            clock.nanoseconds += 900_000_000
            delayed = True

    monkeypatch.setattr(engine.journal, "append", append_with_one_slow_fsync)
    engine.begin()
    engine.observe(
        ObserverOperation.LIST_IMAGES,
        phase=ObserverPhase.PREFLIGHT,
        credential="dummy-canary-not-a-secret",
    )
    engine.observe(
        ObserverOperation.LIST_INSTANCE_TYPES,
        phase=ObserverPhase.PREFLIGHT,
        credential="dummy-canary-not-a-secret",
    )
    assert transport.transport_entry_ns == [900_000_000, 1_900_000_000]
    completed = [
        json.loads(line)
        for line in engine.journal.path.read_text().splitlines()
        if json.loads(line)["event_type"] == "observation_completed"
    ]
    assert [event["transport_entry_monotonic_ns"] for event in completed] == [
        900_000_000,
        1_900_000_000,
    ]
    engine.stop()


def test_postlaunch_transport_boundary_failure_burns_ordinal_and_keeps_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    transport = FakeObserverTransport([*preflight_responses(), response([])], clock=clock)
    engine = make_observer_engine(
        tmp_path,
        suffix="0014",
        transport=transport,
        clock=clock,
    )
    engine.begin()
    complete_preflight(engine)
    engine._provider_started_ns = clock.monotonic_ns()
    engine.lifecycle = ManualLifecycle(
        ManualPhase.LAUNCH_CLICKED,
        True,
        False,
        engine._proof_issuer,
    )
    original_append = engine.journal.append

    def expire_after_send_started(event: dict[str, object]) -> None:
        original_append(event)
        if event["event_type"] == "observation_send_started" and event["request_ordinal"] == 7:
            clock.nanoseconds += 3_601_000_000_000

    monkeypatch.setattr(engine.journal, "append", expire_after_send_started)
    with pytest.raises(L2MContractError, match="transport boundary"):
        engine.observe(
            ObserverOperation.LIST_INSTANCES,
            phase=ObserverPhase.INSTANCE_BIND,
            credential="dummy-canary-not-a-secret",
        )
    assert not engine.stopped and engine.lifecycle.incident_active
    assert engine.budget.request_count == 7
    assert len(transport.requests) == 6
    recovered = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.INCIDENT,
        credential="dummy-canary-not-a-secret",
    )
    assert recovered.request_ordinal == 8
    assert engine.budget.request_count == 8
    events = [json.loads(line) for line in engine.journal.path.read_text().splitlines()]
    assert any(
        event["event_type"] == "observation_failed" and event["request_ordinal"] == 7
        for event in events
    )
    assert any(
        event["event_type"] == "observation_completed" and event["request_ordinal"] == 8
        for event in events
    )
    engine._evidence_incomplete = True
    engine._finalize_stopped_run()


@pytest.mark.parametrize("name_value", [None, 7])
def test_ruleset_endpoint_schema_rejects_missing_or_wrong_name_before_preflight_claim(
    tmp_path: Path,
    name_value: object,
) -> None:
    bad = ruleset(name="placeholder")
    if name_value is None:
        bad.pop("name")
    else:
        bad["name"] = name_value
    transport = FakeObserverTransport([*preflight_responses()[:4], response([bad])])
    engine = make_observer_engine(
        tmp_path,
        suffix=f"SCHEMA-{len(str(name_value))}",
        transport=transport,
        clock=FakeClock(),
    )
    engine.begin()
    engine.observe(
        ObserverOperation.LIST_IMAGES,
        phase=ObserverPhase.PREFLIGHT,
        credential="dummy-canary-not-a-secret",
    )
    engine.observe(
        ObserverOperation.LIST_INSTANCE_TYPES,
        phase=ObserverPhase.PREFLIGHT,
        credential="dummy-canary-not-a-secret",
    )
    engine.observe(
        ObserverOperation.LIST_SSH_KEYS,
        phase=ObserverPhase.PREFLIGHT,
        credential="dummy-canary-not-a-secret",
    )
    engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.PREFLIGHT,
        credential="dummy-canary-not-a-secret",
    )
    with pytest.raises(L2MContractError, match="endpoint schema"):
        engine.observe(
            ObserverOperation.LIST_RULESETS,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )
    assert engine.stopped and not engine._preflight_complete


def test_ruleset_endpoint_schema_rejects_wrong_name_before_absence_claim(
    tmp_path: Path,
) -> None:
    bad = ruleset(name="placeholder")
    bad["name"] = 7
    transport = FakeObserverTransport([*preflight_responses(), response([bad])])
    clock = FakeClock()
    engine = make_observer_engine(
        tmp_path,
        suffix="SCHEMA-DELETE",
        transport=transport,
        clock=clock,
    )
    engine.begin()
    complete_preflight(engine)
    engine._provider_started_ns = clock.monotonic_ns()
    engine.private_ruleset_id = "ruleset-private"
    engine.lifecycle = ManualLifecycle(
        ManualPhase.INSTANCE_TERMINAL,
        True,
        False,
        engine._proof_issuer,
    )
    with pytest.raises(L2MContractError, match="endpoint schema"):
        engine.observe(
            ObserverOperation.LIST_RULESETS,
            phase=ObserverPhase.RULESET_ABSENCE,
            credential="dummy-canary-not-a-secret",
        )
    assert not engine.stopped and engine.lifecycle.incident_active
    assert len(engine._issued_observations) == 6
    engine._evidence_incomplete = True
    engine._finalize_stopped_run()


def test_observation_capability_is_engine_scoped(tmp_path: Path) -> None:
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    first_transport = FakeObserverTransport(
        [
            *preflight_responses(),
            response({"id": "global", "name": "global", "rules": [strict_rule()]}),
        ]
    )
    second_transport = FakeObserverTransport(preflight_responses())
    first = make_observer_engine(
        tmp_path,
        suffix="0007",
        transport=first_transport,
        clock=FakeClock(),
    )
    second = make_observer_engine(
        tmp_path,
        suffix="0008",
        transport=second_transport,
        clock=FakeClock(),
        checkpoint_reader=FakeCheckpointReader(
            {"global_firewall_restricted": {"global_firewall_restricted": True}},
            CheckpointBinding(
                "RUN-T07-L2M-FIXTURE-0008",
                "l2m-decision-0123456789ab",
                marker.marker_alias,
            ),
            tmp_path / "consumption-0008.jsonl",
        ),
    )
    assert first.private_marker_name == second.private_marker_name == marker.name
    first.begin()
    second.begin()
    complete_preflight(first)
    complete_preflight(second)
    foreign = first.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    forged_clone = replace(foreign, data={"forged": True})
    with pytest.raises(L2MContractError, match="engine-issued observation"):
        first._trusted_observation(
            forged_clone,
            ObserverOperation.GET_GLOBAL_FIREWALL,
            frozenset({ObserverPhase.GLOBAL_RESTRICTED_VERIFY}),
        )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    with pytest.raises(L2MContractError, match="checkpoint evidence preparation failed"):
        second.consume_checkpoint(
            tmp_path / "global_firewall_restricted.json",
            expected_type="global_firewall_restricted",
            expected_nonce="1" * 64,
            not_before=now,
            not_after=now + dt.timedelta(seconds=1),
            observation=foreign,
        )
    assert second.lifecycle.phase is ManualPhase.GLOBAL_MUTATION_UNVERIFIED
    first.stop()
    second._evidence_incomplete = True
    second._finalize_stopped_run()


def test_timeline_blocks_late_work_before_send_but_preserves_cleanup_reserve(
    tmp_path: Path,
) -> None:
    transport = FakeObserverTransport([*preflight_responses(), response([])])
    clock = FakeClock()
    engine = make_observer_engine(
        tmp_path,
        suffix="0009",
        transport=transport,
        clock=clock,
    )
    engine.begin()
    complete_preflight(engine)
    engine._provider_started_ns = clock.monotonic_ns()
    clock.sleep(3_601)
    with pytest.raises(L2MContractError, match="cleanup observations only"):
        engine.observe(
            ObserverOperation.LIST_INSTANCES,
            phase=ObserverPhase.INSTANCE_BIND,
            credential="dummy-canary-not-a-secret",
        )
    assert len(transport.requests) == 6
    engine.resume_incident_cleanup()
    engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.TERMINATION_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    assert len(transport.requests) == 7
    clock.sleep(1_200)
    with pytest.raises(L2MContractError, match=r"active wall cap|reserve exhausted"):
        engine.observe(
            ObserverOperation.LIST_INSTANCES,
            phase=ObserverPhase.TERMINATION_VERIFY,
            credential="dummy-canary-not-a-secret",
        )
    assert len(transport.requests) == 7
    engine._evidence_incomplete = True
    engine._finalize_stopped_run()


@pytest.mark.parametrize(
    ("provider_response", "outcome"),
    [
        (ObserverResponse(401, "application/json", b'{"data":[]}', 5), "http_failure"),
        (ObserverResponse(200, "text/plain", b'{"data":[]}', 5), "schema_failure"),
        (
            ObserverResponse(
                200,
                "application/json",
                b'{"data":[],"page_token":"next"}',
                5,
            ),
            "pagination_stop",
        ),
    ],
)
def test_engine_stops_on_status_content_or_pagination_without_retry(
    tmp_path: Path,
    provider_response: ObserverResponse,
    outcome: str,
) -> None:
    marker = derive_private_ruleset_marker(
        bytes(range(32)), decision_alias="l2m-decision-0123456789ab"
    )
    transport = FakeObserverTransport([provider_response])
    clock = FakeClock()
    journal = ObserverJournal.create(
        tmp_path / "observer.jsonl",
        schema_path=ROOT / "schemas/t07-lambda-l2m-observer-journal.schema.json",
    )
    engine = L2MReadOnlyObserverEngine(
        run_id="RUN-T07-L2M-FIXTURE-0002",
        authorization_reference="AUTH-T07-L2M-FIXTURE-0002",
        authorization_sha256="0" * 64,
        journal=journal,
        checkpoint_reader=FakeCheckpointReader(
            {},
            CheckpointBinding(
                "RUN-T07-L2M-FIXTURE-0002",
                "l2m-decision-0123456789ab",
                marker.marker_alias,
            ),
            tmp_path / "consumption-0002.jsonl",
        ),
        transport=transport,
        private_marker_name=marker.name,
        source_ipv4_cidr="8.8.8.8/32",
        human_decision=validated_decision(),
        sealed_original_global_sha256="1" * 64,
        image_selection_checkpoint_sha256="2" * 64,
        private_selected_image_id="raw-b",
        private_selected_ssh_key_id="ssh-key-private",
        private_selected_ssh_key_fingerprint=("SHA256:ZkAslGjFiUHdGf/WUL8rQvkib4PTvQatUV0OUQSncCA"),
        selected_image_alias=RECOMMENDED_IMAGE_ALIAS,
        selected_image_version=RECOMMENDED_IMAGE_VERSION,
        clock_ns=clock.monotonic_ns,
        sleeper=clock.sleep,
        utc_now=lambda: dt.datetime(2026, 8, 10, tzinfo=dt.UTC),
    )
    engine.begin()
    with pytest.raises(L2MContractError):
        engine.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )
    assert len(transport.requests) == 1
    journal.close()
    events = [json.loads(line) for line in journal.path.read_text().splitlines()]
    assert events[-2]["event_type"] == "observation_failed"
    assert events[-2]["sanitized_outcome"] == outcome
    assert events[-1]["event_type"] == "run_stopped"
    with pytest.raises(L2MContractError, match="active run"):
        engine.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )
    assert "dummy-canary-not-a-secret" not in journal.path.read_text()


def test_observer_transport_is_in_process_get_only_without_shell_or_mutation() -> None:
    source = (ROOT / "src/giclab/harness/lambda_l2m_observer.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert "http" in imported
    assert imported.isdisjoint({"urllib", "requests", "socket"})
    subprocess_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "Popen"
    ]
    assert len(subprocess_calls) == 1  # exact local diskutil observer only
    assert "POST" not in {
        request.method for request in [observer_request(ObserverOperation.LIST_IMAGES)]
    }
    assert 'connection.request(\n                    "GET"' in source
    assert 'connection.request(\n                    "POST"' not in source


def test_bundle_manifest_and_containment_arguments() -> None:
    manifest = verify_bundle_manifest(BUNDLE)
    assert manifest["busybox_reference"] == BUSYBOX_REFERENCE
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(BUNDLE))
    try:
        driver = importlib.import_module("qualification_driver")
        arguments = driver.create_arguments(
            name="t07-l2m-fixture",
            fixture=(BUNDLE / "adversarial-containment.sh").resolve(),
            run_id="RUN-T07-L2M-HOST-QUALIFICATION-0001",
            marker_alias="l2m-marker-0123456789ab",
        )
    finally:
        sys.path.pop(0)
        sys.modules.pop("qualification_driver", None)
        sys.dont_write_bytecode = previous_dont_write_bytecode
    rendered = "\0".join(arguments)
    assert BUSYBOX_REFERENCE in arguments
    assert arguments.count("--pull=never") == 1
    assert "--network\0none" in rendered
    assert "--cap-drop\0ALL" in rendered
    assert "--read-only" in arguments
    assert "\0".join(["--pids-limit", "64"]) in rendered
    assert "--privileged" not in arguments and "host" not in arguments
    assert "docker.sock" not in rendered and "ssh" not in rendered.lower()


def test_host_evidence_archive_validates_and_rejects_residue(tmp_path: Path) -> None:
    bundle_sha = hashlib.sha256((BUNDLE / "manifest.json").read_bytes()).hexdigest()
    evidence = host_evidence(bundle_sha)
    source_payloads = {
        "host-evidence.json": json.dumps(evidence, sort_keys=True).encode(),
        "qualification-log.jsonl": qualification_log(evidence),
        "container-inspect.json": json.dumps(private_container_inspect()).encode(),
    }
    evidence_manifest = {
        "schema_version": "0.1.0",
        "files": [
            {"path": name, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
            for name, value in sorted(source_payloads.items())
        ],
    }
    archive = tmp_path / "evidence.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for name, value in source_payloads.items():
            handle.writestr(name, value)
        handle.writestr("EVIDENCE_MANIFEST.json", json.dumps(evidence_manifest).encode())
    validated = validate_qualification_archive(
        archive,
        schema_path=SCHEMA,
        expected_bundle_manifest_sha256=bundle_sha,
        expected_binding=evidence_binding(),
    )
    assert validated["prohibitions"]["scientific_executions"] == 0
    wrong_binding = QualificationEvidenceBinding(
        run_id=evidence_binding().run_id,
        decision_alias=evidence_binding().decision_alias,
        marker_alias=evidence_binding().marker_alias,
        instance_binding_sha256="9" * 64,
        authorization_reference=evidence_binding().authorization_reference,
        authorization_sha256=evidence_binding().authorization_sha256,
    )
    with pytest.raises(L2MContractError, match="identity binding"):
        validate_qualification_archive(
            archive,
            schema_path=SCHEMA,
            expected_bundle_manifest_sha256=bundle_sha,
            expected_binding=wrong_binding,
        )
    fabricated = tmp_path / "fabricated.zip"
    fabricated_payloads = dict(source_payloads)
    fabricated_payloads["container-inspect.json"] = b'{"documents":[],"runtime":{}}'
    with zipfile.ZipFile(fabricated, "w") as handle:
        for name, value in fabricated_payloads.items():
            handle.writestr(name, value)
        fabricated_manifest = {
            "schema_version": "0.1.0",
            "files": [
                {
                    "path": name,
                    "bytes": len(value),
                    "sha256": hashlib.sha256(value).hexdigest(),
                }
                for name, value in sorted(fabricated_payloads.items())
            ],
        }
        handle.writestr("EVIDENCE_MANIFEST.json", json.dumps(fabricated_manifest).encode())
    with pytest.raises(L2MContractError, match="contract drifted"):
        validate_qualification_archive(
            fabricated,
            schema_path=SCHEMA,
            expected_bundle_manifest_sha256=bundle_sha,
            expected_binding=evidence_binding(),
        )
    evidence["containment"]["owned_container_residue_count"] = 1
    source_payloads["host-evidence.json"] = json.dumps(evidence, sort_keys=True).encode()
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as handle:
        for name, value in source_payloads.items():
            handle.writestr(name, value)
        manifest = {
            "schema_version": "0.1.0",
            "files": [
                {"path": name, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
                for name, value in sorted(source_payloads.items())
            ],
        }
        handle.writestr("EVIDENCE_MANIFEST.json", json.dumps(manifest).encode())
    with pytest.raises(L2MContractError, match="schema"):
        validate_qualification_archive(
            bad,
            schema_path=SCHEMA,
            expected_bundle_manifest_sha256=bundle_sha,
            expected_binding=evidence_binding(),
        )


def test_host_evidence_archive_rejects_duplicate_paths(tmp_path: Path) -> None:
    bundle_sha = hashlib.sha256((BUNDLE / "manifest.json").read_bytes()).hexdigest()
    duplicate = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(duplicate, "w") as handle:
        handle.writestr("host-evidence.json", b"{}")
        with pytest.warns(UserWarning, match="Duplicate name"):
            handle.writestr("host-evidence.json", b"{}")
        handle.writestr("qualification-log.jsonl", b"{}\n")
        handle.writestr("container-inspect.json", b"{}")
        handle.writestr("EVIDENCE_MANIFEST.json", b"{}")
    with pytest.raises(L2MContractError, match="duplicate path"):
        validate_qualification_archive(
            duplicate,
            schema_path=SCHEMA,
            expected_bundle_manifest_sha256=bundle_sha,
            expected_binding=evidence_binding(),
        )


def test_failure_archive_is_preserved_but_never_host_qualification_eligible(
    tmp_path: Path,
) -> None:
    bundle_sha = hashlib.sha256((BUNDLE / "manifest.json").read_bytes()).hexdigest()
    binding = evidence_binding()
    disposition = {
        "schema_version": "0.1.0",
        "run_id": binding.run_id,
        "authorization_reference": binding.authorization_reference,
        "authorization_sha256": binding.authorization_sha256,
        "decision_alias": binding.decision_alias,
        "marker_alias": binding.marker_alias,
        "instance_binding_sha256": binding.instance_binding_sha256,
        "bundle_manifest_sha256": bundle_sha,
        "sanitized_failure_stage": "container_start",
        "cleanup": {
            "container_id_sha256": None,
            "kill_attempted": True,
            "kill_succeeded": False,
            "remove_attempted": True,
            "remove_succeeded": False,
            "container_residue_count": None,
            "network_residue_count": None,
            "volume_residue_count": None,
            "process_residue_count": None,
            "cgroup_residue_count": None,
            "residue_scan_sha256": None,
            "residue_scanned_process_count": None,
            "residue_scanned_cgroup_entries": None,
            "docker_config_removed": False,
            "fixture_removed": False,
            "create_outcome_unknown": True,
            "create_outcome_observations": 5,
            "create_outcome_resolution": "unresolved_no_match",
            "create_outcome_quiescence_proven": False,
        },
        "cleanup_complete": False,
        "provider_termination_required": True,
    }
    payloads = {
        "qualification-failure.json": json.dumps(disposition).encode(),
        "qualification-log.jsonl": b"".join(
            json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            for event in (
                {
                    "sequence": 1,
                    "event": "qualification_failed",
                    "failure_stage": "container_start",
                },
                {
                    "sequence": 2,
                    "event": "emergency_cleanup_observed",
                    "cleanup_complete": False,
                    "cleanup": disposition["cleanup"],
                },
            )
        ),
        "container-inspect.json": b'{"documents":[],"residue_scan":null,"runtime":{}}',
    }
    manifest = {
        "schema_version": "0.1.0",
        "files": [
            {
                "path": name,
                "bytes": len(value),
                "sha256": hashlib.sha256(value).hexdigest(),
            }
            for name, value in sorted(payloads.items())
        ],
    }
    archive = tmp_path / "failure.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for name, value in payloads.items():
            handle.writestr(name, value)
        handle.writestr("EVIDENCE_MANIFEST.json", json.dumps(manifest).encode())
    held_archive = archive.read_bytes()
    archive.write_bytes(b"synthetic path-swap replacement")
    held_result = validate_qualification_failure_archive(
        archive,
        expected_bundle_manifest_sha256=bundle_sha,
        expected_binding=binding,
        _encoded_archive=held_archive,
    )
    assert held_result["eligible_for_host_qualification"] is False
    archive.write_bytes(held_archive)
    result = validate_qualification_failure_archive(
        archive,
        expected_bundle_manifest_sha256=bundle_sha,
        expected_binding=binding,
    )
    assert result == {
        "eligible_for_host_qualification": False,
        "cleanup_complete": False,
        "provider_termination_required": True,
        "sanitized_failure_stage": "container_start",
    }


def test_host_evidence_schema_is_repository_bound_and_json_is_strict(
    tmp_path: Path,
) -> None:
    bundle_sha = hashlib.sha256((BUNDLE / "manifest.json").read_bytes()).hexdigest()
    evidence = host_evidence(bundle_sha)
    ordinary = json.dumps(evidence, sort_keys=True).encode()
    duplicate = b'{"schema_version":"0.1.0",' + ordinary.removeprefix(b"{")
    payloads = {
        "host-evidence.json": duplicate,
        "qualification-log.jsonl": qualification_log(evidence),
        "container-inspect.json": json.dumps(private_container_inspect()).encode(),
    }
    manifest = {
        "schema_version": "0.1.0",
        "files": [
            {"path": name, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
            for name, value in sorted(payloads.items())
        ],
    }
    archive = tmp_path / "duplicate-host-key.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for name, value in payloads.items():
            handle.writestr(name, value)
        handle.writestr("EVIDENCE_MANIFEST.json", json.dumps(manifest).encode())
    with pytest.raises(L2MContractError, match="duplicate key"):
        validate_qualification_archive(
            archive,
            schema_path=SCHEMA,
            expected_bundle_manifest_sha256=bundle_sha,
            expected_binding=evidence_binding(),
        )
    permissive = tmp_path / "permissive.schema.json"
    permissive.write_text("{}")
    with pytest.raises(L2MContractError, match="repository-bound"):
        validate_qualification_archive(
            archive,
            schema_path=permissive,
            expected_bundle_manifest_sha256=bundle_sha,
            expected_binding=evidence_binding(),
        )


def test_raw_provider_response_is_hashed_but_only_allowlisted_projection_is_retained(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider_response = preflight_responses()[0]
    engine = make_observer_engine(
        tmp_path,
        suffix="RAWRETENTION",
        transport=FakeObserverTransport([provider_response]),
        clock=FakeClock(),
    )
    monkeypatch.setattr(
        l2m_observer,
        "_load_bound_endpoint_schema",
        lambda operation: (_ for _ in ()).throw(AssertionError(operation)),
    )
    engine.begin()
    observed = engine.observe(
        ObserverOperation.LIST_IMAGES,
        phase=ObserverPhase.PREFLIGHT,
        credential="dummy-canary-not-a-secret",
    )
    assert observed.response_sha256 == hashlib.sha256(provider_response.body).hexdigest()
    engine.stop()
    retained = engine.private_observation_store.final_evidence.records
    assert len(retained) == 1 and retained[0].encoded != provider_response.body
    projection = json.loads(retained[0].encoded)
    assert projection == {
        "data": [
            {
                "architecture": "x86_64",
                "created_time": "2026-08-01T00:00:00Z",
                "family": "lambda-stack-22-04",
                "id": "raw-b",
                "name": "Lambda Stack 22 04",
                "region": {"name": "us-east-1"},
                "updated_time": "2026-08-01T00:00:00Z",
                "version": "22.4.5-2141",
            }
        ],
        "operation": "list_images",
        "raw_response_bytes": len(provider_response.body),
        "raw_response_sha256": hashlib.sha256(provider_response.body).hexdigest(),
        "schema_version": "0.1.0",
    }
    assert "description" not in retained[0].encoded.decode()
    repository = tmp_path / "raw-repository"
    repository.mkdir()
    sealed = seal_observer_evidence(engine, repository_root=repository)
    assert (sealed.root / "provider-observation-0001.json").read_bytes() == retained[0].encoded


def test_credential_echo_and_partial_private_write_never_become_sealed_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    echo_engine = make_observer_engine(
        tmp_path,
        suffix="ECHOREJECT",
        transport=FakeObserverTransport(
            [ObserverResponse(200, "application/json", b'{"data":"dummy-canary-not-a-secret"}', 1)]
        ),
        clock=FakeClock(),
    )
    echo_engine.begin()
    with pytest.raises(L2MContractError, match="secret non-retention"):
        echo_engine.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )
    assert not list(echo_engine.private_observation_store._root.iterdir())
    assert "dummy-canary-not-a-secret" not in echo_engine.journal.path.read_text()

    partial_engine = make_observer_engine(
        tmp_path,
        suffix="PARTIALRAW",
        transport=FakeObserverTransport([preflight_responses()[0]]),
        clock=FakeClock(),
    )
    original_write = l2m_observer._write_exclusive_record

    def partial_write(directory_fd: int, name: str, encoded: bytes) -> None:
        if name.startswith(".observation-"):
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=directory_fd,
            )
            try:
                os.write(descriptor, encoded[:7])
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            raise OSError
        original_write(directory_fd, name, encoded)

    monkeypatch.setattr(l2m_observer, "_write_exclusive_record", partial_write)
    partial_engine.begin()
    with pytest.raises(L2MContractError):
        partial_engine.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )
    assert partial_engine._evidence_incomplete
    assert any(
        path.name.endswith(".partial")
        for path in partial_engine.private_observation_store._root.iterdir()
    )
    with pytest.raises(L2MContractError):
        seal_observer_evidence(
            partial_engine,
            repository_root=tmp_path / "partial-repository",
        )


def test_transport_baseexception_burns_request_and_records_unknown_outcome(
    tmp_path: Path,
) -> None:
    class InterruptingTransport:
        calls = 0

        def send(self, *args: object, **kwargs: object) -> ObserverResponse:
            del args, kwargs
            self.calls += 1
            raise KeyboardInterrupt

    transport = InterruptingTransport()
    engine = make_observer_engine(
        tmp_path,
        suffix="TRANSPORTINTERRUPT",
        transport=transport,  # type: ignore[arg-type]
        clock=FakeClock(),
    )
    engine.begin()
    with pytest.raises(KeyboardInterrupt):
        engine.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )
    assert transport.calls == 1
    assert engine.budget.request_count == 1
    events = [json.loads(line) for line in engine.journal.path.read_text().splitlines()]
    assert [event["event_type"] for event in events[-2:]] == [
        "observation_failed",
        "run_stopped",
    ]
    assert events[-2]["sanitized_outcome"] == "outcome_unknown"
    with pytest.raises(L2MContractError, match="active run"):
        engine.observe(
            ObserverOperation.LIST_IMAGES,
            phase=ObserverPhase.PREFLIGHT,
            credential="dummy-canary-not-a-secret",
        )


def test_cleanup_presend_failure_burns_ordinal_before_continuation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine, _reader, _clock, _ = prepare_bound_engine(
        tmp_path,
        suffix="PRESENDBURN",
        cleanup_responses=[response([])],
    )
    now = dt.datetime(2026, 8, 10, tzinfo=dt.UTC)
    engine.consume_checkpoint(
        tmp_path / "termination_confirmed_by_user.json",
        expected_type="termination_confirmed_by_user",
        expected_nonce="1" * 64,
        not_before=now,
        not_after=now + dt.timedelta(seconds=1),
    )
    before = engine.budget.request_count
    original_append = L2MReadOnlyObserverEngine._append_event
    failed_once = False

    def fail_send_started(
        target: L2MReadOnlyObserverEngine,
        event_type: str,
        **kwargs: object,
    ) -> None:
        nonlocal failed_once
        if target is engine and event_type == "observation_send_started" and not failed_once:
            failed_once = True
            raise L2MContractError("synthetic send-start receipt failure")
        original_append(target, event_type, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(L2MReadOnlyObserverEngine, "_append_event", fail_send_started)
    with pytest.raises(L2MContractError, match="before transport"):
        engine.observe(
            ObserverOperation.LIST_INSTANCES,
            phase=ObserverPhase.TERMINATION_VERIFY,
            credential="dummy-canary-not-a-secret",
        )
    assert engine.budget.request_count == before + 1
    assert before + 1 in engine._burned_request_ordinals
    engine.resume_incident_cleanup()
    observed = engine.observe(
        ObserverOperation.LIST_INSTANCES,
        phase=ObserverPhase.TERMINATION_VERIFY,
        credential="dummy-canary-not-a-secret",
    )
    assert observed.request_ordinal == before + 2
    engine._evidence_incomplete = True
    engine._finalize_stopped_run()


def test_archive_control_records_are_verified_before_atomic_finalize(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository = tmp_path / "control-repository"
    repository.mkdir()
    store = L2MObserverEvidenceStore.create(
        repository,
        run_id="RUN-T07-L2M-FIXTURE-CONTROL",
        authorization_reference="AUTH-T07-L2M-FIXTURE-CONTROL",
        authorization_sha256="0" * 64,
    )
    try:
        store.write_record("fixture.json", b'{"fixture":true}')
        sealed = store.seal()
    finally:
        store.close()
    destination = tmp_path / "control-external"
    destination.mkdir()
    original_write = l2m_observer._write_exclusive_record

    def corrupt_control(directory_fd: int, name: str, encoded: bytes) -> None:
        original_write(
            directory_fd,
            name,
            encoded + (b"corrupt" if name == "COPY_RECORD.json" else b""),
        )

    monkeypatch.setattr(l2m_observer, "_write_exclusive_record", corrupt_control)
    with pytest.raises(L2MContractError, match="staging control record"):
        _copy_sealed_observer_evidence(
            sealed,
            destination_parent=destination,
            archive_id="RUN-T07-L2M-FIXTURE-CONTROL-EVIDENCE",
            require_distinct_device=False,
        )
    assert not (destination / "RUN-T07-L2M-FIXTURE-CONTROL-EVIDENCE").exists()
    assert not any(path.name.endswith(".partial") for path in destination.iterdir())


def test_l2m_diskutil_observer_burns_failed_call_and_rejects_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def fail_once(argv: tuple[str, ...], *, max_output_bytes: int) -> tuple[bytes, int]:
        nonlocal attempts
        del argv, max_output_bytes
        attempts += 1
        raise L2MContractError("synthetic diskutil failure")

    monkeypatch.setattr(l2m_observer, "_run_l2m_diskutil_streaming", fail_once)
    observer = L2MDiskutilVolumeObserver()
    with pytest.raises(L2MContractError, match="synthetic"):
        observer()
    assert observer.calls == 1 and observer.failed
    with pytest.raises(L2MContractError, match="call cap"):
        observer()
    assert attempts == 1


def test_l2m_default_diskutil_driver_uses_six_exact_bounded_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import giclab.harness.sira_storage as storage

    calls: list[tuple[str, ...]] = []

    def observe(argv: tuple[str, ...], *, max_output_bytes: int) -> tuple[bytes, int]:
        assert 0 < max_output_bytes <= 4_194_304
        calls.append(argv)
        return f"observation-{len(calls)}".encode(), 13

    parsed: list[tuple[bytes, bytes]] = []

    def parse(volume: bytes, apfs: bytes) -> object:
        parsed.append((volume, apfs))
        return object()

    monkeypatch.setattr(l2m_observer, "_run_l2m_diskutil_streaming", observe)
    monkeypatch.setattr(storage, "volume_observation_from_diskutil", parse)
    observer = L2MDiskutilVolumeObserver(
        max_calls=16,
        max_output_bytes=4_194_304,
    )
    first = observer()
    second = observer()
    assert all(len(pair) == 2 for pair in (first, second))
    assert observer.calls == 6 and observer.output_bytes == 78
    assert [call[1:3] for call in calls] == [
        ("info", "-plist"),
        ("info", "-plist"),
        ("apfs", "list"),
        ("info", "-plist"),
        ("info", "-plist"),
        ("apfs", "list"),
    ]
    assert len(parsed) == 4


def test_cost_wall_arithmetic_and_rejected_automated_plan_absence() -> None:
    assert billed_list_cost_cents(1_800) == 65
    assert billed_list_cost_cents(2_400) == 86
    assert billed_list_cost_cents(3_600) == 129
    caps = exact_l2m_caps()
    assert caps["provider_cost_cents"] == 200
    assert caps["provider_wall_seconds"] == 3_600
    assert caps["observer_wall_seconds"] == 6_300
    assert caps["observer_active_seconds"] == 6_000
    assert caps["observer_prelaunch_seconds"] == 1_200
    assert caps["observer_post_provider_cleanup_seconds"] == 1_200
    assert caps["observer_archive_seconds"] == 300
    assert caps["automated_cloud_mutations"] == caps["ssh_operations"] == caps["model_calls"] == 0
    assert TERMINAL_DECISION == "blocked-human-image-selection"
    assert not (BUNDLE / "gate-l2-host-qualification-plan.json").exists()
    assert not (BUNDLE / "gate-l2-host-qualification-plan-v2.json").exists()
    assert (BUNDLE / "gate-l2m-host-qualification-plan-v1.json").is_file()


def test_locked_science_and_prior_evidence_hashes_remain_exact() -> None:
    expected = dict(
        [
            (
                "experiments/EXP-0001-sira-simulative-vs-reactive/protocol.yaml",
                "5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c",
            ),
            (
                "experiments/EXP-0001-sira-simulative-vs-reactive/config.yaml",
                "f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d",
            ),
            (
                "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml",
                "ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425",
            ),
            (
                "experiments/EXP-0001-sira-simulative-vs-reactive/"
                "run-plans/conditions/smoke-reactive.yaml",
                "7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018",
            ),
            (
                "experiments/EXP-0001-sira-simulative-vs-reactive/"
                "run-plans/conditions/smoke-simulative.yaml",
                "68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436",
            ),
            (
                "containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json",
                "b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331",
            ),
            (
                "containers/sira-smoke/lambda/gate-l1a-ssh-key-fingerprint-plan-v1.json",
                "23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc",
            ),
        ]
    )
    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
