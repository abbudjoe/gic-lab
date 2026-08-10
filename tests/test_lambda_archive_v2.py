from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_lambda_cloud import _responses
from test_lambda_request_ledger import (
    PLAN_SHA256,
    _binding,
    _repository,
    _terminal_success,
)

from giclab.harness import lambda_archive as archive_base
from giclab.harness import lambda_archive_v2 as archive
from giclab.harness import sira_storage as storage
from giclab.harness.lambda_cloud import (
    IncrementalInventoryParser,
    canonical_inventory_bytes,
    inventory_document,
    select_compute_candidate,
)
from giclab.harness.lambda_inventory import seal_inventory_artifact
from giclab.harness.lambda_inventory_plan import (
    ReadOnlyInventoryPlanV2,
    inventory_ledger_contract_document_v2,
    inventory_limits_document_v2,
)
from giclab.harness.lambda_request_ledger import FsyncRequestLedger, LedgerEventType
from giclab.harness.sira_storage import (
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_VOLUME_UUID,
    VolumeObservation,
)

ROOT = Path(__file__).resolve().parents[1]


def _valid_inventory(plan: ReadOnlyInventoryPlanV2) -> bytes:
    parser = IncrementalInventoryParser(plan)
    responses = _responses()
    for request in plan.requests:
        parser.accept(request, responses[request.request_id])
    inventory = parser.finish()
    candidate = select_compute_candidate(inventory)
    return canonical_inventory_bytes(
        inventory_document(
            inventory,
            candidate,
            observed_at_utc="2026-08-09T12:00:00Z",
            inventory_plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            plan_id=plan.plan_id,
            run_attempt=plan.attempt,
            limits_document=inventory_limits_document_v2(plan),
            request_ledger_contract=inventory_ledger_contract_document_v2(plan),
        )
    )


def _prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    archive.PreparedInventoryArchiveV2,
    ReadOnlyInventoryPlanV2,
    Path,
    list[archive_base._HeldDirectory],
    archive_base.DiskutilVolumeObserver,
]:
    repository, plan = _repository(tmp_path / "repository")
    for binding in plan.implementation_artifacts:
        target = repository / binding.path
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / binding.path, target)
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
    archiver = archive.DurableInventoryArchiverV2(
        observer_factory=lambda: observer,
        clock=lambda: 0.0,
        utc_now=lambda: datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    )
    prepared = archiver.prepare(
        repository,
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
    )
    return prepared, plan, source, opened, observer


def test_concrete_v2_archive_stages_terminal_ledger_seals_and_verifies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, plan, source, handles, observer = _prepare(tmp_path, monkeypatch)
    ledger = FsyncRequestLedger.create(
        tmp_path / "repository",
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
    )
    ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
    ledger.reserve_capacity()
    source.write_bytes(_valid_inventory(plan))
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
        tmp_path / "repository",
        relative_path=plan.copy_record_relative_path,
        encoded=result.local_verification_record,
        max_bytes=plan.max_local_record_bytes,
    )
    eligibility = archive.validate_gate_l2_evidence_v2(
        tmp_path / "repository",
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
    )
    prepared.close()

    assert (result.destination / "inventory-redacted.json").read_bytes() == source_bytes
    assert (result.destination / "request-ledger.jsonl").read_bytes() == terminal.path.read_bytes()
    record = json.loads((result.destination / "COPY_RECORD.json").read_bytes())
    seal = json.loads((result.destination / "SEAL.json").read_bytes())
    assert record["terminal_ledger_validated"] is True
    assert record["source_ledger_sha256"] == terminal.sha256
    assert seal["terminal_ledger_validated"] is True
    assert {item["path"] for item in seal["files"]} == {
        "inventory-redacted.json",
        "request-ledger.jsonl",
        "COPY_RECORD.json",
    }
    assert source.read_bytes() == source_bytes
    assert terminal.path.read_bytes()
    assert local_record.sha256 == eligibility.local_verification_sha256
    assert eligibility.eligible
    assert eligibility.selection_state == "selected"
    assert eligibility.inventory_sha256 == source_hash
    assert eligibility.ledger_sha256 == terminal.sha256
    assert observer.calls == 9
    assert all(handle.closed for handle in handles)


def test_v2_archive_rejects_storage_identity_drift_and_keeps_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, _, source, _, observer = _prepare(tmp_path, monkeypatch)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b'{"redacted":"inventory-v2"}\n')
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    original_call = observer.__class__.__call__
    calls = 0

    def drift(self):
        nonlocal calls
        calls += 1
        external, system = original_call(self)
        if calls >= 1:
            external = replace(
                external,
                volume_uuid="00000000-0000-0000-0000-000000000000",
            )
        return external, system

    monkeypatch.setattr(observer.__class__, "__call__", drift)
    with pytest.raises(archive_base.InventoryArchiveError, match="identity drifted"):
        prepared.stage_inventory(
            source,
            artifact_sha256=source_hash,
            artifact_bytes=len(source_bytes),
        )
    prepared.close()


def test_finalize_failure_cannot_pass_complete_gate_l2_evidence_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, plan, source, _, _ = _prepare(tmp_path, monkeypatch)
    ledger = FsyncRequestLedger.create(
        tmp_path / "repository",
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
    )
    ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
    ledger.reserve_capacity()
    source.write_bytes(_valid_inventory(plan))
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
        archive.validate_gate_l2_evidence_v2(
            tmp_path / "repository",
            plan=plan,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
        )
    assert not (tmp_path / "repository" / plan.copy_record_relative_path).exists()
