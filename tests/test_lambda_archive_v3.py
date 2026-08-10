from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_lambda_inventory_v3 import (
    PLAN_SHA256,
    _binding,
    _copy_runtime_schemas,
    _outcomes,
    _plan,
    _responses,
)

from giclab.harness import lambda_archive as archive_base
from giclab.harness import lambda_archive_v3 as archive
from giclab.harness import sira_storage as storage
from giclab.harness.lambda_cloud_v3 import (
    IncrementalInventoryParserV3,
    canonical_inventory_v3_bytes,
    inventory_document_v3,
    select_compute_candidate_v3,
)
from giclab.harness.lambda_inventory import seal_inventory_artifact
from giclab.harness.lambda_inventory_plan_v3 import (
    IMPLEMENTATION_ARTIFACT_PATHS_V3,
    ReadOnlyInventoryPlanV3,
    inventory_ledger_contract_document_v3,
    inventory_limits_document_v3,
)
from giclab.harness.lambda_request_ledger_v3 import (
    FsyncRequestLedger,
    LedgerEventType,
    RequestContext,
    RequestLedgerSnapshot,
)
from giclab.harness.sira_storage import (
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_VOLUME_UUID,
    VolumeObservation,
)

ROOT = Path(__file__).resolve().parents[1]


def _valid_inventory(repository: Path, plan: ReadOnlyInventoryPlanV3) -> bytes:
    parser = IncrementalInventoryParserV3(repository, plan)
    responses = _responses()
    for request in plan.requests:
        parser.accept(request, responses[request.request_id])
    inventory = parser.finish()
    candidate = select_compute_candidate_v3(inventory)
    return canonical_inventory_v3_bytes(
        inventory_document_v3(
            inventory,
            candidate,
            observed_at_utc="2026-08-10T12:00:00Z",
            inventory_plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            endpoint_outcomes=_outcomes(parser, plan),
            extension_report=parser.extension_report(),
            extension_schema_sha256=plan.extension_schema_sha256,
            limits_document=inventory_limits_document_v3(plan),
            request_ledger_contract=inventory_ledger_contract_document_v3(plan),
        )
    )


def _terminal_success(
    ledger: FsyncRequestLedger,
    plan: ReadOnlyInventoryPlanV3,
) -> RequestLedgerSnapshot:
    response_sizes = {request_id: len(encoded) for request_id, encoded in _responses().items()}
    ledger.append(LedgerEventType.SECRET_PRESENCE_CHECK_PASSED)
    ledger.append(LedgerEventType.RUN_PREFLIGHT_PASSED)
    for ordinal, request in enumerate(plan.requests, start=1):
        context = RequestContext.from_request(ordinal, request)
        ledger.append(LedgerEventType.REQUEST_INTENT_COMMITTED, request=context)
        ledger.append(LedgerEventType.REQUEST_SEND_STARTED, request=context)
        ledger.append(
            LedgerEventType.RESPONSE_HEADERS_RECEIVED,
            request=context,
            http_status=200,
            content_type="application/json",
            elapsed_ms=1,
        )
        ledger.append(
            LedgerEventType.RESPONSE_BODY_COMPLETED,
            request=context,
            bytes_received=response_sizes[request.request_id],
            http_status=200,
            content_type="application/json",
            elapsed_ms=2,
        )
        ledger.append(
            LedgerEventType.RESPONSE_VALIDATION_PASSED,
            request=context,
            bytes_received=response_sizes[request.request_id],
            http_status=200,
            content_type="application/json",
            elapsed_ms=2,
        )
    ledger.append(LedgerEventType.INVENTORY_VALIDATION_STARTED)
    ledger.append(LedgerEventType.INVENTORY_VALIDATION_PASSED)
    ledger.append(LedgerEventType.ARCHIVE_STARTED)
    ledger.append(LedgerEventType.ARCHIVE_PASSED)
    ledger.append(LedgerEventType.RUN_STOPPED)
    return ledger.seal(require_terminal_success=True)


def _prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    archive.PreparedInventoryArchiveV3,
    ReadOnlyInventoryPlanV3,
    Path,
    list[archive_base._HeldDirectory],
    archive_base.DiskutilVolumeObserver,
]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _copy_runtime_schemas(repository)
    plan = _plan(repository)
    for relative in IMPLEMENTATION_ARTIFACT_PATHS_V3:
        target = repository / relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    external_mount = tmp_path / "external"
    system_mount = tmp_path / "system"
    external_mount.mkdir()
    system_mount.mkdir()
    archive_root = external_mount / "GIC-Lab/t07/sealed-artifacts"
    archive_root.mkdir(parents=True)
    object.__setattr__(plan, "archive_root", str(archive_root))
    source = repository / plan.output_relative_path

    monkeypatch.setattr(archive, "APPROVED_MOUNT", external_mount)
    monkeypatch.setattr(archive, "SYSTEM_DATA_MOUNT", system_mount)
    monkeypatch.setattr(archive_base, "APPROVED_MOUNT", external_mount)
    monkeypatch.setattr(archive_base, "SYSTEM_DATA_MOUNT", system_mount)
    monkeypatch.setattr(storage, "SYSTEM_DATA_MOUNT", system_mount)

    source_device = repository.stat().st_dev
    external_device = source_device + 1_000_000
    opened: list[archive_base._HeldDirectory] = []
    original_open = archive_base._HeldDirectory.open

    def held(path: Path, *, device: int) -> archive_base._HeldDirectory:
        handle = original_open(path)
        handle.device = device
        opened.append(handle)
        return handle

    def fake_open(cls, path: Path) -> archive_base._HeldDirectory:
        del cls
        if path == external_mount:
            return held(path, device=external_device)
        return held(path, device=source_device)

    def fake_archive_root(
        external: archive_base._HeldDirectory,
        requested: Path,
    ) -> archive_base._HeldDirectory:
        assert requested == archive_root
        return held(archive_root, device=external.device)

    def fake_revalidate(self: archive_base._HeldDirectory) -> None:
        if self.closed:
            raise archive_base.InventoryArchiveError("held descriptor closed early")

    monkeypatch.setattr(archive_base._HeldDirectory, "open", classmethod(fake_open))
    monkeypatch.setattr(archive_base._HeldDirectory, "revalidate", fake_revalidate)
    monkeypatch.setattr(archive, "_open_or_create_archive_root", fake_archive_root)

    external_observation = VolumeObservation(
        mount_path=external_mount,
        filesystem="apfs",
        writable=True,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        total_bytes=1_000_240_963_584,
        free_bytes=854_038_691_840,
        internal=False,
        owners_enabled=False,
        encrypted=True,
        unlocked=True,
        device_identifier="synthetic-external",
        bus_protocol="Thunderbolt",
        device_tree_path="IODeviceTree:/UTDM/synthetic",
    )
    system_observation = VolumeObservation(
        mount_path=system_mount,
        filesystem="apfs",
        writable=True,
        volume_uuid=SYSTEM_DATA_VOLUME_UUID,
        physical_store_uuid=None,
        total_bytes=SYSTEM_CAPACITY_BYTES,
        free_bytes=32 * 1024**3,
        internal=True,
        owners_enabled=True,
        encrypted=True,
        unlocked=True,
        device_identifier="synthetic-system",
    )

    class Observer(archive_base.DiskutilVolumeObserver):
        def __call__(self):
            if self.calls + 3 > archive_base.MAX_DISKUTIL_CALLS:
                raise archive_base.InventoryArchiveError("storage observation call cap exhausted")
            self.calls += 3
            return external_observation, system_observation

    observer = Observer()
    archiver = archive.DurableInventoryArchiverV3(
        observer_factory=lambda: observer,
        clock=lambda: 0.0,
        utc_now=lambda: datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    prepared = archiver.prepare(
        repository,
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
    )
    return prepared, plan, source, opened, observer


def test_concrete_v3_archive_seals_complete_ledger_and_verifies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, plan, source, handles, observer = _prepare(tmp_path, monkeypatch)
    repository = tmp_path / "repository"
    ledger = FsyncRequestLedger.create(
        repository,
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
    )
    ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
    ledger.reserve_capacity()
    source.write_bytes(_valid_inventory(repository, plan))
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    prepared.stage_inventory(
        source,
        artifact_sha256=source_hash,
        artifact_bytes=len(source_bytes),
    )
    terminal = _terminal_success(ledger, plan)
    result = prepared.finalize(
        source,
        artifact_sha256=source_hash,
        artifact_bytes=len(source_bytes),
        ledger=terminal,
    )
    local_record = seal_inventory_artifact(
        repository,
        relative_path=plan.copy_record_relative_path,
        encoded=result.local_verification_record,
        max_bytes=plan.max_local_record_bytes,
    )
    eligibility = archive.validate_gate_l2_evidence_v3(
        repository,
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
        ancestry_verifier=lambda repository_root, **kwargs: None,
    )
    prepared.close()

    assert (result.destination / "inventory-redacted.json").read_bytes() == source_bytes
    assert (result.destination / "request-ledger.jsonl").read_bytes() == terminal.path.read_bytes()
    record = json.loads((result.destination / "COPY_RECORD.json").read_bytes())
    seal = json.loads((result.destination / "SEAL.json").read_bytes())
    assert record["terminal_ledger_validated"] is True
    assert seal["terminal_ledger_validated"] is True
    assert local_record.sha256 == eligibility.local_verification_sha256
    assert eligibility.eligible
    assert eligibility.selection_state == "selected"
    assert eligibility.inventory_sha256 == source_hash
    assert eligibility.ledger_sha256 == terminal.sha256

    def ancestry_must_not_run(repository_root: Path, **kwargs: str) -> None:
        del repository_root, kwargs
        raise AssertionError("implementation equality must fail before ancestry")

    with pytest.raises(archive_base.InventoryArchiveError, match="implementation binding"):
        archive.validate_gate_l2_evidence_v3(
            repository,
            plan=plan,
            plan_sha256=PLAN_SHA256,
            run_binding=replace(_binding(), implementation_commit="6" * 40),
            ancestry_verifier=ancestry_must_not_run,
        )
    assert observer.calls == 9
    assert all(handle.closed for handle in handles)


@pytest.mark.parametrize(
    "mutation",
    [
        "endpoint_schema_hash",
        "extension_schema_hash",
        "extension_report_hash",
        "extension_observation_hash",
        "extension_state_semantics",
        "extension_location_semantics",
        "selection_candidate",
        "firewall_semantics",
        "ledger_response_bytes",
    ],
)
def test_gate_l2_rejects_tampered_request_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    prepared, plan, source, _, _ = _prepare(tmp_path, monkeypatch)
    repository = tmp_path / "repository"
    inventory = json.loads(_valid_inventory(repository, plan))
    if mutation == "endpoint_schema_hash":
        inventory["endpoint_outcomes"][0]["schema_sha256"] = "0" * 64
    elif mutation == "extension_schema_hash":
        inventory["schema_extension_report"]["schema_sha256"] = "0" * 64
    elif mutation == "extension_report_hash":
        inventory["schema_extension_report"]["report"]["report_sha256"] = "0" * 64
    elif mutation == "extension_observation_hash":
        inventory["schema_extension_report"]["report"]["observations"][0][
            "structural_summary_sha256"
        ] = "0" * 64
    elif mutation in {"extension_state_semantics", "extension_location_semantics"}:
        report = inventory["schema_extension_report"]["report"]
        observation = report["observations"][0]
        observation["validation_state"] = "compatible_extension_observed"
        if mutation == "extension_location_semantics":
            observation["unknown_locations"] = [
                {"path": "$", "key_names": ["future"], "value_types": {}}
            ]
            summary = {
                "request_id": observation["request_id"],
                "unknown_locations": observation["unknown_locations"],
            }
            observation["structural_summary_sha256"] = hashlib.sha256(
                json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        unsigned_report = dict(report)
        unsigned_report.pop("report_sha256")
        report["report_sha256"] = hashlib.sha256(
            json.dumps(unsigned_report, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    elif mutation == "selection_candidate":
        inventory["selection"]["image_id"] = "synthetic-tampered-image"
    elif mutation == "firewall_semantics":
        inventory["firewall_rulesets"][0]["ssh_only"] = False
    else:
        inventory["endpoint_outcomes"][0]["response_bytes"] += 1
    ledger = FsyncRequestLedger.create(
        repository,
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
    )
    ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
    ledger.reserve_capacity()
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        json.dumps(
            inventory,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    prepared.stage_inventory(
        source,
        artifact_sha256=source_hash,
        artifact_bytes=len(source_bytes),
    )
    terminal = _terminal_success(ledger, plan)
    result = prepared.finalize(
        source,
        artifact_sha256=source_hash,
        artifact_bytes=len(source_bytes),
        ledger=terminal,
    )
    seal_inventory_artifact(
        repository,
        relative_path=plan.copy_record_relative_path,
        encoded=result.local_verification_record,
        max_bytes=plan.max_local_record_bytes,
    )
    with pytest.raises(archive_base.InventoryArchiveError, match="Gate L2"):
        archive.validate_gate_l2_evidence_v3(
            repository,
            plan=plan,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            ancestry_verifier=lambda repository_root, **kwargs: None,
        )
    prepared.close()


def test_v3_archive_rejects_storage_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, _, source, _, observer = _prepare(tmp_path, monkeypatch)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b'{"redacted":"inventory-v3"}\n')
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    original_call = observer.__class__.__call__

    def drift(self):
        external, system = original_call(self)
        return (
            replace(external, volume_uuid="00000000-0000-0000-0000-000000000000"),
            system,
        )

    monkeypatch.setattr(observer.__class__, "__call__", drift)
    with pytest.raises(archive_base.InventoryArchiveError, match="identity drifted"):
        prepared.stage_inventory(
            source,
            artifact_sha256=source_hash,
            artifact_bytes=len(source_bytes),
        )
    prepared.close()


def test_v3_finalize_failure_cannot_produce_gate_l2_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, plan, source, _, _ = _prepare(tmp_path, monkeypatch)
    repository = tmp_path / "repository"
    ledger = FsyncRequestLedger.create(
        repository,
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
    )
    ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
    ledger.reserve_capacity()
    source.write_bytes(_valid_inventory(repository, plan))
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    prepared.stage_inventory(
        source,
        artifact_sha256=source_hash,
        artifact_bytes=len(source_bytes),
    )
    terminal = _terminal_success(ledger, plan)

    def fail_final_write(*args, **kwargs):
        raise archive_base.InventoryArchiveError("synthetic finalizer failure")

    monkeypatch.setattr(archive, "_write_exclusive_at", fail_final_write)
    with pytest.raises(archive_base.InventoryArchiveError):
        prepared.finalize(
            source,
            artifact_sha256=source_hash,
            artifact_bytes=len(source_bytes),
            ledger=terminal,
        )
    prepared.close()
    with pytest.raises(archive_base.InventoryArchiveError):
        archive.validate_gate_l2_evidence_v3(
            repository,
            plan=plan,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            ancestry_verifier=lambda repository_root, **kwargs: None,
        )
    assert not (repository / plan.copy_record_relative_path).exists()
