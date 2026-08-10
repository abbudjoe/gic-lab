from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from giclab.harness import lambda_archive as archive_base
from giclab.harness import lambda_ssh_key_archive as archive
from giclab.harness import sira_storage as storage
from giclab.harness.lambda_request_ledger_v3 import LedgerEventType, RequestLedgerSnapshot
from giclab.harness.lambda_ssh_key_fingerprint import (
    LEDGER_RELATIVE_PATH,
    PLAN_RELATIVE_PATH,
    RUN_ID,
    RUN_ROOT_RELATIVE_PATH,
    SSHKeyFingerprintPlan,
    SSHKeyRunBinding,
    load_ssh_key_fingerprint_plan,
)
from giclab.harness.lambda_ssh_key_match import EvidenceFileIdentity, LocalEvidenceBundle
from giclab.harness.lambda_ssh_key_request_ledger import (
    FsyncSSHKeyRequestLedger,
    SSHKeyRequestContext,
)
from giclab.harness.sira_storage import (
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_VOLUME_UUID,
    VolumeObservation,
)
from giclab.validation import ROOT


def _copy_bound_repository(tmp_path: Path) -> tuple[Path, SSHKeyFingerprintPlan, str]:
    repository = tmp_path / "repository"
    repository.mkdir()
    plan_document = json.loads((ROOT / PLAN_RELATIVE_PATH).read_bytes())
    implementation = plan_document["implementation_binding"]
    paths = [PLAN_RELATIVE_PATH]
    paths.extend(item["path"] for item in implementation["implementation_artifacts"])
    paths.extend(
        (
            plan_document["requests"][0]["response_schema_path"],
            plan_document["ledger_contract"]["schema_path"],
            plan_document["schema_contract"]["fingerprint_schema_path"],
            plan_document["schema_contract"]["match_schema_path"],
        )
    )
    for relative in set(paths):
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    plan_path = repository / PLAN_RELATIVE_PATH
    plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    plan = load_ssh_key_fingerprint_plan(repository, plan_path, expected_sha256=plan_sha)
    return repository, plan, plan_sha


def _binding(plan: SSHKeyFingerprintPlan) -> SSHKeyRunBinding:
    return SSHKeyRunBinding(
        repository_commit="9" * 40,
        implementation_commit=plan.implementation_commit,
        authorization_reference="AUTH-T07-L1A-ARCHIVE-UNIT-TEST",
        authorization_sha256="8" * 64,
    )


def _bundle(repository: Path) -> LocalEvidenceBundle:
    files = (
        ("ssh-keys-response.json", b'{"data":[]}\n'),
        ("private-evidence.json", b'{"private":"synthetic"}\n'),
        ("match-report.json", b'{"sanitized":"synthetic"}\n'),
        ("PRIVATE_EVIDENCE_SEAL.json", b'{"sealed":true}\n'),
    )
    identities: list[EvidenceFileIdentity] = []
    for name, encoded in files:
        path = repository / RUN_ROOT_RELATIVE_PATH / name
        path.write_bytes(encoded)
        path.chmod(0o400)
        identities.append(
            EvidenceFileIdentity(
                relative_path=f"{RUN_ROOT_RELATIVE_PATH}/{name}",
                bytes=len(encoded),
                sha256=hashlib.sha256(encoded).hexdigest(),
            )
        )
    return LocalEvidenceBundle(*identities, total_bytes=sum(item.bytes for item in identities))


def _terminal_ledger(
    ledger: FsyncSSHKeyRequestLedger,
    *,
    body_bytes: int,
) -> RequestLedgerSnapshot:
    request = SSHKeyRequestContext()
    ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
    ledger.reserve_capacity()
    ledger.append(LedgerEventType.SECRET_PRESENCE_CHECK_PASSED)
    ledger.append(LedgerEventType.RUN_PREFLIGHT_PASSED)
    ledger.append(LedgerEventType.REQUEST_INTENT_COMMITTED, request=request)
    ledger.append(LedgerEventType.REQUEST_SEND_STARTED, request=request)
    ledger.append(
        LedgerEventType.RESPONSE_HEADERS_RECEIVED,
        request=request,
        http_status=200,
        content_type="application/json",
        elapsed_ms=1,
    )
    ledger.append(
        LedgerEventType.RESPONSE_BODY_COMPLETED,
        request=request,
        bytes_received=body_bytes,
        http_status=200,
        content_type="application/json",
        elapsed_ms=2,
    )
    ledger.append(
        LedgerEventType.RESPONSE_VALIDATION_PASSED,
        request=request,
        bytes_received=body_bytes,
        http_status=200,
        content_type="application/json",
        elapsed_ms=2,
    )
    ledger.append(LedgerEventType.INVENTORY_VALIDATION_STARTED)
    ledger.append(LedgerEventType.INVENTORY_VALIDATION_PASSED)
    ledger.append(LedgerEventType.ARCHIVE_STARTED)
    ledger.append(LedgerEventType.ARCHIVE_PASSED)
    ledger.append(LedgerEventType.RUN_STOPPED)
    return ledger.seal(require_success=True)


def _prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    archive.PreparedSSHKeyArchive,
    Path,
    SSHKeyFingerprintPlan,
    SSHKeyRunBinding,
    list[archive_base._HeldDirectory],
    archive_base.DiskutilVolumeObserver,
]:
    repository, plan, _ = _copy_bound_repository(tmp_path)
    external_mount = tmp_path / "external"
    system_mount = tmp_path / "system"
    external_mount.mkdir()
    system_mount.mkdir()
    archive_root = external_mount / "GIC-Lab/t07/sealed-artifacts"
    archive_root.mkdir(parents=True)

    monkeypatch.setattr(archive, "APPROVED_MOUNT", external_mount)
    monkeypatch.setattr(archive, "SYSTEM_DATA_MOUNT", system_mount)
    monkeypatch.setattr(archive, "ARCHIVE_ROOT", str(archive_root))
    monkeypatch.setattr(archive_base, "APPROVED_MOUNT", external_mount)
    monkeypatch.setattr(archive_base, "SYSTEM_DATA_MOUNT", system_mount)
    monkeypatch.setattr(storage, "SYSTEM_DATA_MOUNT", system_mount)

    source_device = repository.stat().st_dev
    external_contract_device = source_device + 1_000_000
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
            return held(path, device=external_contract_device)
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
        postcopy_free_bytes: int = external_observation.free_bytes

        def __call__(self):
            if self.calls + 3 > archive_base.MAX_DISKUTIL_CALLS:
                raise archive_base.InventoryArchiveError("storage observation cap exhausted")
            self.calls += 3
            external = (
                external_observation
                if self.calls < 9
                else replace(external_observation, free_bytes=self.postcopy_free_bytes)
            )
            return external, system_observation

    observer = Observer()
    binding = _binding(plan)
    prepared = archive.DurableSSHKeyArchiver(
        observer_factory=lambda: observer,
        clock=lambda: 0.0,
        utc_now=lambda: datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    ).prepare(repository, plan=plan, run_binding=binding)
    return prepared, repository, plan, binding, opened, observer


def test_concrete_ssh_key_archive_stages_finalizes_and_reverifies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, repository, plan, binding, handles, observer = _prepare(tmp_path, monkeypatch)
    ledger = FsyncSSHKeyRequestLedger.create(
        repository,
        plan=plan,
        run_binding=binding,
    )
    bundle = _bundle(repository)
    prepared.stage(bundle)
    terminal = _terminal_ledger(ledger, body_bytes=bundle.raw_response.bytes)
    result = prepared.finalize(bundle, ledger=terminal)
    prepared.close()

    assert result.destination.is_dir()
    assert {path.name for path in result.destination.iterdir()} == {
        "ssh-keys-response.json",
        "private-evidence.json",
        "match-report.json",
        "PRIVATE_EVIDENCE_SEAL.json",
        "request-ledger.jsonl",
        "COPY_RECORD.json",
        "SEAL.json",
    }
    assert (result.destination / "request-ledger.jsonl").read_bytes() == (
        repository / LEDGER_RELATIVE_PATH
    ).read_bytes()
    verification = json.loads(result.local_verification_record)
    assert verification["source_destination_sha256_equal"] is True
    assert verification["terminal_ledger_validated"] is True
    assert result.ledger_sha256 == terminal.sha256
    assert observer.calls == 9
    assert all(handle.closed for handle in handles)
    assert not list(result.destination.parent.glob("*.partial"))


def test_concrete_ssh_key_archive_postcopy_floor_failure_is_not_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, repository, plan, binding, handles, observer = _prepare(tmp_path, monkeypatch)
    observer.postcopy_free_bytes = 1
    ledger = FsyncSSHKeyRequestLedger.create(
        repository,
        plan=plan,
        run_binding=binding,
    )
    bundle = _bundle(repository)
    prepared.stage(bundle)
    terminal = _terminal_ledger(ledger, body_bytes=bundle.raw_response.bytes)
    with pytest.raises(archive.InventoryArchiveError):
        prepared.finalize(bundle, ledger=terminal)
    prepared.close()

    assert (Path(archive.ARCHIVE_ROOT) / RUN_ID).is_dir()
    assert all(handle.closed for handle in handles)
    assert observer.calls == 9
