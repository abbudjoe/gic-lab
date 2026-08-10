"""Two-phase, terminal-ledger-aware archive sealing for Gate L1 V3.

The phase split breaks an unavoidable evidence cycle without weakening it:
``archive_passed`` means that the redacted inventory was durably staged on the
held external-volume identity.  The supervisor can then append ``run_stopped``
and seal the ledger.  Finalization independently validates that terminal ledger,
adds it to the staged bundle, writes the hash manifests, and atomically publishes
the directory.  A staged-only directory is never eligible Gate L2 evidence.

Importing this module performs no I/O.  Tests inject a fake volume boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .lambda_archive import (
    DiskutilVolumeObserver,
    InventoryArchiveError,
    _canonical_bytes,
    _HeldDirectory,
    _open_directory_no_symlinks,
    _open_or_create_archive_root,
    _read_regular_at,
    _same_identity,
    _validate_external,
    _validate_system,
    _write_exclusive_at,
)
from .lambda_cloud import InstanceSelectionError, LambdaCloudContractError
from .lambda_cloud_v3 import (
    EXPECTED_INVENTORY_REQUESTS_V3,
    inventory_v3_from_redacted_document,
    select_compute_candidate_v3,
    selection_document_v3,
    validate_schema_extension_report_integrity,
)
from .lambda_inventory_plan_v3 import (
    InventoryRunBindingV3,
    ReadOnlyInventoryPlanV3,
    inventory_ledger_contract_document_v3,
    inventory_limits_document_v3,
    verify_inventory_implementation_v3,
    verify_repository_commit_ancestry_v3,
)
from .lambda_request_ledger_v3 import (
    RequestLedgerSnapshot,
    load_request_ledger_validator,
    validate_request_ledger_bytes,
)
from .sira_storage import (
    APPROVED_MOUNT,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    SYSTEM_DATA_MOUNT,
    VolumeObservation,
)

ARCHIVE_ACTION_ID_V3 = "t07-l1-v3-seal-copy"
INVENTORY_ARCHIVE_NAME = "inventory-redacted.json"
LEDGER_ARCHIVE_NAME = "request-ledger.jsonl"
COPY_RECORD_NAME = "COPY_RECORD.json"
SEAL_NAME = "SEAL.json"

EXTERNAL_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "action_id",
        "plan_id",
        "plan_sha256",
        "run_id",
        "implementation_commit",
        "repository_commit",
        "authorization_reference",
        "authorization_sha256",
        "source_inventory_path",
        "source_inventory_sha256",
        "source_inventory_bytes",
        "source_ledger_path",
        "source_ledger_sha256",
        "source_ledger_bytes",
        "source_ledger_events",
        "terminal_ledger_validated",
        "source_retained",
        "destination_path",
        "copied_at_utc",
        "external_mount",
        "external_volume_uuid",
        "external_physical_store_uuid",
        "external_capacity_bytes",
        "external_precopy_free_bytes",
        "external_retained_floor_bytes",
        "external_precopy_floor_bytes",
        "held_descriptor_guard",
        "atomic_finalization",
        "fsync_required",
        "no_internal_fallback",
    }
)
LOCAL_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "action_id",
        "plan_id",
        "plan_sha256",
        "run_id",
        "implementation_commit",
        "repository_commit",
        "authorization_reference",
        "authorization_sha256",
        "source_inventory_path",
        "source_inventory_sha256",
        "source_inventory_bytes",
        "source_ledger_path",
        "source_ledger_sha256",
        "source_ledger_bytes",
        "source_ledger_events",
        "destination_path",
        "destination_inventory_sha256",
        "destination_ledger_sha256",
        "destination_copy_record_sha256",
        "destination_seal_sha256",
        "external_volume_uuid",
        "external_physical_store_uuid",
        "external_postcopy_free_bytes",
        "external_retained_floor_bytes",
        "system_postcopy_free_bytes",
        "system_retained_floor_bytes",
        "held_descriptor_guard",
        "terminal_ledger_validated",
        "source_destination_sha256_equal",
        "source_retained_until_independent_verification",
    }
)


def _validate_inventory_request_provenance(
    inventory: Mapping[str, object],
    *,
    plan: ReadOnlyInventoryPlanV3,
    ledger_events: Sequence[dict[str, object]],
) -> None:
    raw_outcomes = inventory.get("endpoint_outcomes")
    raw_extension = inventory.get("schema_extension_report")
    if not isinstance(raw_outcomes, list) or not isinstance(raw_extension, Mapping):
        raise InventoryArchiveError("Gate L2 request provenance is incomplete")
    raw_report = raw_extension.get("report")
    if (
        raw_extension.get("schema_path") != plan.extension_schema_relative_path
        or raw_extension.get("schema_sha256") != plan.extension_schema_sha256
        or not isinstance(raw_report, Mapping)
    ):
        raise InventoryArchiveError("Gate L2 extension-schema binding drifted")
    try:
        validate_schema_extension_report_integrity(raw_report)
    except LambdaCloudContractError:
        raise InventoryArchiveError("Gate L2 extension-report integrity drifted") from None
    raw_observations = raw_report.get("observations")
    if not isinstance(raw_observations, list):
        raise InventoryArchiveError("Gate L2 extension observations are incomplete")
    terminal_events = [
        event for event in ledger_events if event.get("event_type") == "response_validation_passed"
    ]
    if not (
        len(raw_outcomes)
        == len(raw_observations)
        == len(terminal_events)
        == len(EXPECTED_INVENTORY_REQUESTS_V3)
    ):
        raise InventoryArchiveError("Gate L2 request provenance cardinality drifted")
    for ordinal, (request, raw_outcome, raw_observation, terminal) in enumerate(
        zip(
            EXPECTED_INVENTORY_REQUESTS_V3,
            raw_outcomes,
            raw_observations,
            terminal_events,
            strict=True,
        ),
        start=1,
    ):
        if not isinstance(raw_outcome, Mapping) or not isinstance(raw_observation, Mapping):
            raise InventoryArchiveError("Gate L2 request provenance item drifted")
        schema_binding = plan.endpoint_schema_bindings[request.request_id]
        if (
            raw_outcome.get("request_id") != request.request_id
            or raw_outcome.get("method") != "GET"
            or raw_outcome.get("path") != request.path
            or raw_outcome.get("http_status") != 200
            or raw_outcome.get("schema_path") != schema_binding.path
            or raw_outcome.get("schema_sha256") != schema_binding.sha256
            or raw_outcome.get("validation_state") != raw_observation.get("validation_state")
            or raw_observation.get("request_id") != request.request_id
            or terminal.get("request_ordinal") != ordinal
            or terminal.get("method") != "GET"
            or terminal.get("path") != request.path
            or terminal.get("http_status") != raw_outcome.get("http_status")
            or terminal.get("bytes_received_so_far") != raw_outcome.get("response_bytes")
        ):
            raise InventoryArchiveError("Gate L2 ordered request provenance drifted")


def _validate_inventory_selection_provenance(
    inventory: Mapping[str, object],
) -> str:
    try:
        typed_inventory = inventory_v3_from_redacted_document(inventory)
        try:
            candidate = select_compute_candidate_v3(typed_inventory)
        except InstanceSelectionError as failure:
            expected = selection_document_v3(None, failure)
        else:
            expected = selection_document_v3(candidate, None)
    except LambdaCloudContractError:
        raise InventoryArchiveError("Gate L2 typed inventory semantics drifted") from None
    if inventory.get("selection") != expected:
        raise InventoryArchiveError("Gate L2 deterministic selection provenance drifted")
    return str(expected["state"])


@dataclass(frozen=True, slots=True)
class GateL2EvidenceEligibilityV3:
    eligible: bool
    selection_state: str
    inventory_sha256: str
    ledger_sha256: str
    archive_seal_sha256: str
    local_verification_sha256: str


@dataclass(frozen=True, slots=True)
class ArchivedInventoryArtifactV3:
    destination: Path
    artifact_sha256: str
    artifact_bytes: int
    ledger_sha256: str
    ledger_bytes: int
    seal_sha256: str
    external_copy_record_sha256: str
    local_verification_record: bytes


class PreparedInventoryArchiveV3(Protocol):
    """Single-use capability held from preflight through final sealing."""

    def stage_inventory(
        self,
        artifact_path: Path,
        *,
        artifact_sha256: str,
        artifact_bytes: int,
    ) -> None: ...

    def finalize(
        self,
        artifact_path: Path,
        *,
        artifact_sha256: str,
        artifact_bytes: int,
        ledger: RequestLedgerSnapshot,
    ) -> ArchivedInventoryArtifactV3: ...

    def close(self) -> None: ...


class InventoryArchiverV3(Protocol):
    def prepare(
        self,
        repository_root: Path,
        *,
        plan: ReadOnlyInventoryPlanV3,
        plan_sha256: str,
        run_binding: InventoryRunBindingV3,
    ) -> PreparedInventoryArchiveV3: ...


def _strict_object(encoded: bytes, *, context: str) -> dict[str, object]:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        del value
        raise ValueError

    try:
        decoded = json.loads(
            encoded,
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise InventoryArchiveError(f"{context} is not strict JSON") from None
    if not isinstance(decoded, dict) or any(not isinstance(key, str) for key in decoded):
        raise InventoryArchiveError(f"{context} is not an object")
    return decoded


def _integer_value(document: dict[str, object], field: str, *, context: str) -> int:
    value = document.get(field)
    if type(value) is not int:
        raise InventoryArchiveError(f"{context} integer field drifted")
    return value


def _read_source(
    path: Path,
    *,
    expected_sha256: str,
    expected_bytes: int,
    max_bytes: int,
    expected_device: int,
) -> bytes:
    parent_descriptor = _open_directory_no_symlinks(path.parent)
    try:
        encoded = _read_regular_at(parent_descriptor, path.name, max_bytes=max_bytes)
        observed = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
    finally:
        os.close(parent_descriptor)
    if (
        len(encoded) != expected_bytes
        or hashlib.sha256(encoded).hexdigest() != expected_sha256
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or observed.st_dev != expected_device
    ):
        raise InventoryArchiveError("Gate L1 V3 source identity or hash drifted")
    return encoded


@dataclass(slots=True)
class _PreparedDurableInventoryArchiveV3:
    repository_root: Path
    plan: ReadOnlyInventoryPlanV3
    plan_sha256: str
    run_binding: InventoryRunBindingV3
    observer: DiskutilVolumeObserver
    external_at_prepare: VolumeObservation
    system_at_prepare: VolumeObservation
    external_mount: _HeldDirectory
    system_mount: _HeldDirectory
    repository: _HeldDirectory
    archive_root: _HeldDirectory
    clock: Callable[[], float]
    utc_now: Callable[[], datetime]
    staging_name: str | None = None
    staging_descriptor: int = -1
    staged_artifact_sha256: str | None = None
    staged_artifact_bytes: int = 0
    external_at_stage: VolumeObservation | None = None
    external_floor_at_stage: int | None = None
    stage_started: float | None = None
    finalized: bool = False
    closed: bool = False

    def _revalidate(
        self,
        external: VolumeObservation,
        system: VolumeObservation,
        *,
        incremental: int,
    ) -> int:
        if not _same_identity(self.external_at_prepare, external) or not _same_identity(
            self.system_at_prepare, system
        ):
            raise InventoryArchiveError("storage identity drifted during Gate L1 V3")
        floor = _validate_external(external, incremental_bytes=incremental)
        _validate_system(system, floor_bytes=self.plan.local_retained_floor_bytes)
        for handle in (
            self.external_mount,
            self.system_mount,
            self.repository,
            self.archive_root,
        ):
            handle.revalidate()
        return floor

    def _check_wall(self) -> None:
        if (
            self.stage_started is None
            or self.clock() - self.stage_started > self.plan.max_archive_wall_seconds
        ):
            raise InventoryArchiveError("Gate L1 V3 archive wall budget expired")

    def stage_inventory(
        self,
        artifact_path: Path,
        *,
        artifact_sha256: str,
        artifact_bytes: int,
    ) -> None:
        if self.closed or self.staging_name is not None or self.finalized:
            raise InventoryArchiveError("Gate L1 V3 archive capability is stale or reused")
        self.stage_started = self.clock()
        expected_source = self.repository_root / self.plan.output_relative_path
        if artifact_path != expected_source:
            raise InventoryArchiveError("Gate L1 V3 inventory source path drifted")
        external, system = self.observer()
        external_floor = self._revalidate(
            external,
            system,
            incremental=self.plan.max_archive_bytes,
        )
        self._check_wall()
        source = _read_source(
            artifact_path,
            expected_sha256=artifact_sha256,
            expected_bytes=artifact_bytes,
            max_bytes=self.plan.max_retained_output_bytes,
            expected_device=self.system_mount.device,
        )
        destination_name = self.run_binding.run_id
        try:
            os.stat(
                destination_name,
                dir_fd=self.archive_root.descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise InventoryArchiveError("Gate L1 V3 archive run identity already exists")
        staging_name = f".{destination_name}.{uuid.uuid4().hex}.partial"
        staging_descriptor = -1
        try:
            os.mkdir(staging_name, mode=0o700, dir_fd=self.archive_root.descriptor)
            staging_descriptor = os.open(
                staging_name,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=self.archive_root.descriptor,
            )
            _write_exclusive_at(staging_descriptor, INVENTORY_ARCHIVE_NAME, source)
            os.fsync(staging_descriptor)
            os.fsync(self.archive_root.descriptor)
        except (InventoryArchiveError, OSError):
            if staging_descriptor >= 0:
                os.close(staging_descriptor)
            raise InventoryArchiveError("Gate L1 V3 archive staging failed") from None
        self.staging_name = staging_name
        self.staging_descriptor = staging_descriptor
        self.staged_artifact_sha256 = artifact_sha256
        self.staged_artifact_bytes = artifact_bytes
        self.external_at_stage = external
        self.external_floor_at_stage = external_floor
        self._check_wall()

    def finalize(
        self,
        artifact_path: Path,
        *,
        artifact_sha256: str,
        artifact_bytes: int,
        ledger: RequestLedgerSnapshot,
    ) -> ArchivedInventoryArtifactV3:
        if (
            self.closed
            or self.finalized
            or self.staging_name is None
            or self.staging_descriptor < 0
            or self.staged_artifact_sha256 != artifact_sha256
            or self.staged_artifact_bytes != artifact_bytes
            or self.external_at_stage is None
            or self.external_floor_at_stage is None
        ):
            raise InventoryArchiveError("Gate L1 V3 archive was not durably staged")
        self._check_wall()
        if artifact_path != self.repository_root / self.plan.output_relative_path:
            raise InventoryArchiveError("Gate L1 V3 inventory source path drifted")
        source = _read_source(
            artifact_path,
            expected_sha256=artifact_sha256,
            expected_bytes=artifact_bytes,
            max_bytes=self.plan.max_retained_output_bytes,
            expected_device=self.system_mount.device,
        )
        if ledger.path != self.repository_root / self.plan.ledger_relative_path:
            raise InventoryArchiveError("Gate L1 V3 ledger source path drifted")
        ledger_encoded = _read_source(
            ledger.path,
            expected_sha256=ledger.sha256,
            expected_bytes=ledger.bytes,
            max_bytes=self.plan.limits.max_bytes,
            expected_device=self.system_mount.device,
        )
        validator = load_request_ledger_validator(self.repository_root, self.plan)
        events = validate_request_ledger_bytes(
            ledger_encoded,
            plan=self.plan,
            run_binding=self.run_binding,
            validator=validator,
            require_terminal_success=True,
        )
        if len(events) != ledger.events:
            raise InventoryArchiveError("Gate L1 V3 terminal ledger event count drifted")
        staged_source = _read_regular_at(
            self.staging_descriptor,
            INVENTORY_ARCHIVE_NAME,
            max_bytes=self.plan.max_retained_output_bytes,
        )
        if staged_source != source:
            raise InventoryArchiveError("Gate L1 V3 staged inventory verification failed")
        for handle in (
            self.external_mount,
            self.system_mount,
            self.repository,
            self.archive_root,
        ):
            handle.revalidate()
        external_pre = self.external_at_stage
        external_floor = self.external_floor_at_stage
        self._check_wall()
        copied_at = self.utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z")
        record = _canonical_bytes(
            {
                "schema_version": "0.3.0",
                "action_id": ARCHIVE_ACTION_ID_V3,
                "plan_id": self.plan.plan_id,
                "plan_sha256": self.plan_sha256,
                "run_id": self.run_binding.run_id,
                "implementation_commit": self.run_binding.implementation_commit,
                "repository_commit": self.run_binding.repository_commit,
                "authorization_reference": self.run_binding.authorization_reference,
                "authorization_sha256": self.run_binding.authorization_sha256,
                "source_inventory_path": str(artifact_path),
                "source_inventory_sha256": artifact_sha256,
                "source_inventory_bytes": artifact_bytes,
                "source_ledger_path": str(ledger.path),
                "source_ledger_sha256": ledger.sha256,
                "source_ledger_bytes": ledger.bytes,
                "source_ledger_events": ledger.events,
                "terminal_ledger_validated": True,
                "source_retained": True,
                "destination_path": str(Path(self.plan.archive_root) / self.run_binding.run_id),
                "copied_at_utc": copied_at,
                "external_mount": str(external_pre.mount_path),
                "external_volume_uuid": external_pre.volume_uuid.upper(),
                "external_physical_store_uuid": (external_pre.physical_store_uuid or "").upper(),
                "external_capacity_bytes": external_pre.total_bytes,
                "external_precopy_free_bytes": external_pre.free_bytes,
                "external_retained_floor_bytes": external_floor,
                "external_precopy_floor_bytes": external_floor + self.plan.max_archive_bytes,
                "held_descriptor_guard": True,
                "atomic_finalization": True,
                "fsync_required": True,
                "no_internal_fallback": True,
            }
        )
        if len(record) > self.plan.max_local_record_bytes:
            raise InventoryArchiveError("Gate L1 V3 external copy record exceeds its cap")
        _write_exclusive_at(self.staging_descriptor, LEDGER_ARCHIVE_NAME, ledger_encoded)
        _write_exclusive_at(self.staging_descriptor, COPY_RECORD_NAME, record)
        seal = _canonical_bytes(
            {
                "schema_version": "0.3.0",
                "run_id": self.run_binding.run_id,
                "terminal_ledger_validated": True,
                "files": [
                    {
                        "path": INVENTORY_ARCHIVE_NAME,
                        "bytes": len(source),
                        "sha256": artifact_sha256,
                    },
                    {
                        "path": LEDGER_ARCHIVE_NAME,
                        "bytes": len(ledger_encoded),
                        "sha256": ledger.sha256,
                    },
                    {
                        "path": COPY_RECORD_NAME,
                        "bytes": len(record),
                        "sha256": hashlib.sha256(record).hexdigest(),
                    },
                ],
            }
        )
        total_archive_bytes = len(source) + len(ledger_encoded) + len(record) + len(seal)
        if total_archive_bytes > self.plan.max_archive_bytes:
            raise InventoryArchiveError("Gate L1 V3 sealed archive exceeds its byte cap")
        _write_exclusive_at(self.staging_descriptor, SEAL_NAME, seal)
        os.fsync(self.staging_descriptor)
        os.fchmod(self.staging_descriptor, 0o500)
        os.rename(
            self.staging_name,
            self.run_binding.run_id,
            src_dir_fd=self.archive_root.descriptor,
            dst_dir_fd=self.archive_root.descriptor,
        )
        self.staging_name = None
        os.fsync(self.archive_root.descriptor)
        self.finalized = True
        destination_descriptor = os.open(
            self.run_binding.run_id,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=self.archive_root.descriptor,
        )
        try:
            copied_inventory = _read_regular_at(
                destination_descriptor,
                INVENTORY_ARCHIVE_NAME,
                max_bytes=self.plan.max_retained_output_bytes,
            )
            copied_ledger = _read_regular_at(
                destination_descriptor,
                LEDGER_ARCHIVE_NAME,
                max_bytes=self.plan.limits.max_bytes,
            )
            copied_record = _read_regular_at(
                destination_descriptor,
                COPY_RECORD_NAME,
                max_bytes=self.plan.max_local_record_bytes,
            )
            copied_seal = _read_regular_at(
                destination_descriptor,
                SEAL_NAME,
                max_bytes=self.plan.max_local_record_bytes,
            )
        finally:
            os.close(destination_descriptor)
        if (
            copied_inventory != source
            or copied_ledger != ledger_encoded
            or copied_record != record
            or copied_seal != seal
        ):
            raise InventoryArchiveError("Gate L1 V3 final archive verification failed")
        external_post, system_post = self.observer()
        self._revalidate(external_post, system_post, incremental=0)
        if external_post.free_bytes < external_floor:
            raise InventoryArchiveError("Gate L1 V3 retained external floor failed")
        _validate_system(system_post, floor_bytes=self.plan.local_retained_floor_bytes)
        self._check_wall()
        record_sha256 = hashlib.sha256(record).hexdigest()
        seal_sha256 = hashlib.sha256(seal).hexdigest()
        local_verification = _canonical_bytes(
            {
                "schema_version": "0.3.0",
                "action_id": ARCHIVE_ACTION_ID_V3,
                "plan_id": self.plan.plan_id,
                "plan_sha256": self.plan_sha256,
                "run_id": self.run_binding.run_id,
                "implementation_commit": self.run_binding.implementation_commit,
                "repository_commit": self.run_binding.repository_commit,
                "authorization_reference": self.run_binding.authorization_reference,
                "authorization_sha256": self.run_binding.authorization_sha256,
                "source_inventory_path": str(artifact_path),
                "source_inventory_sha256": artifact_sha256,
                "source_inventory_bytes": artifact_bytes,
                "source_ledger_path": str(ledger.path),
                "source_ledger_sha256": ledger.sha256,
                "source_ledger_bytes": ledger.bytes,
                "source_ledger_events": ledger.events,
                "destination_path": str(Path(self.plan.archive_root) / self.run_binding.run_id),
                "destination_inventory_sha256": hashlib.sha256(copied_inventory).hexdigest(),
                "destination_ledger_sha256": hashlib.sha256(copied_ledger).hexdigest(),
                "destination_copy_record_sha256": record_sha256,
                "destination_seal_sha256": seal_sha256,
                "external_volume_uuid": external_post.volume_uuid.upper(),
                "external_physical_store_uuid": (external_post.physical_store_uuid or "").upper(),
                "external_postcopy_free_bytes": external_post.free_bytes,
                "external_retained_floor_bytes": external_floor,
                "system_postcopy_free_bytes": system_post.free_bytes,
                "system_retained_floor_bytes": self.plan.local_retained_floor_bytes,
                "held_descriptor_guard": True,
                "terminal_ledger_validated": True,
                "source_destination_sha256_equal": True,
                "source_retained_until_independent_verification": True,
            }
        )
        if len(local_verification) > self.plan.max_local_record_bytes:
            raise InventoryArchiveError("Gate L1 V3 local verification exceeds its cap")
        return ArchivedInventoryArtifactV3(
            destination=Path(self.plan.archive_root) / self.run_binding.run_id,
            artifact_sha256=artifact_sha256,
            artifact_bytes=artifact_bytes,
            ledger_sha256=ledger.sha256,
            ledger_bytes=ledger.bytes,
            seal_sha256=seal_sha256,
            external_copy_record_sha256=record_sha256,
            local_verification_record=local_verification,
        )

    def close(self) -> None:
        if self.closed:
            return
        if self.staging_descriptor >= 0:
            os.close(self.staging_descriptor)
            self.staging_descriptor = -1
        for handle in (
            self.archive_root,
            self.repository,
            self.system_mount,
            self.external_mount,
        ):
            handle.close()
        self.closed = True


@dataclass(slots=True)
class DurableInventoryArchiverV3:
    """Concrete future V3 archiver; construction is inert."""

    observer_factory: Callable[[], DiskutilVolumeObserver] = DiskutilVolumeObserver
    clock: Callable[[], float] = time.monotonic
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC)

    def prepare(
        self,
        repository_root: Path,
        *,
        plan: ReadOnlyInventoryPlanV3,
        plan_sha256: str,
        run_binding: InventoryRunBindingV3,
    ) -> PreparedInventoryArchiveV3:
        root = repository_root.resolve(strict=True)
        if root != repository_root.absolute():
            raise InventoryArchiveError("Gate L1 V3 repository root contains a symlink")
        if run_binding.implementation_commit != plan.implementation_commit:
            raise InventoryArchiveError("Gate L1 V3 implementation commit drifted")
        observer = self.observer_factory()
        external, system = observer()
        _validate_external(external, incremental_bytes=plan.max_archive_bytes)
        _validate_system(system, floor_bytes=plan.local_prewrite_floor_bytes)
        external_handle = _HeldDirectory.open(APPROVED_MOUNT)
        system_handle: _HeldDirectory | None = None
        repository_handle: _HeldDirectory | None = None
        archive_handle: _HeldDirectory | None = None
        try:
            system_handle = _HeldDirectory.open(SYSTEM_DATA_MOUNT)
            if external_handle.device == system_handle.device:
                raise InventoryArchiveError("Gate L1 V3 source and archive are one filesystem")
            repository_handle = _HeldDirectory.open(root)
            if repository_handle.device != system_handle.device:
                raise InventoryArchiveError("Gate L1 V3 active root is not on the Mac mini")
            archive_handle = _open_or_create_archive_root(
                external_handle,
                Path(plan.archive_root),
            )
            if archive_handle.device != external_handle.device:
                raise InventoryArchiveError("Gate L1 V3 archive used internal fallback")
            return _PreparedDurableInventoryArchiveV3(
                repository_root=root,
                plan=plan,
                plan_sha256=plan_sha256,
                run_binding=run_binding,
                observer=observer,
                external_at_prepare=external,
                system_at_prepare=system,
                external_mount=external_handle,
                system_mount=system_handle,
                repository=repository_handle,
                archive_root=archive_handle,
                clock=self.clock,
                utc_now=self.utc_now,
            )
        except Exception:
            for handle in (
                archive_handle,
                repository_handle,
                system_handle,
                external_handle,
            ):
                if handle is not None:
                    handle.close()
            raise


def validate_gate_l2_evidence_v3(
    repository_root: Path,
    *,
    plan: ReadOnlyInventoryPlanV3,
    plan_sha256: str,
    run_binding: InventoryRunBindingV3,
    ancestry_verifier: Callable[..., None] = verify_repository_commit_ancestry_v3,
) -> GateL2EvidenceEligibilityV3:
    """Validate the complete local/external V3 evidence set for Gate L2 use."""

    from giclab.validation import validate_instance

    root = repository_root.resolve(strict=True)
    if root != repository_root.absolute():
        raise InventoryArchiveError("Gate L2 evidence repository root is unsafe")
    try:
        if run_binding.implementation_commit != plan.implementation_commit:
            raise LambdaCloudContractError("implementation commit drifted")
        ancestry_verifier(
            root,
            implementation_commit=plan.implementation_commit,
            execution_commit=run_binding.repository_commit,
        )
        verify_inventory_implementation_v3(root, plan)
    except Exception:
        raise InventoryArchiveError("Gate L2 implementation binding failed") from None

    def local_evidence(relative: str, *, maximum: int) -> tuple[Path, bytes]:
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise InventoryArchiveError("Gate L2 local evidence path escaped")
        target = root / relative_path
        try:
            parent_descriptor = _open_directory_no_symlinks(target.parent)
            try:
                encoded = _read_regular_at(parent_descriptor, target.name, max_bytes=maximum)
            finally:
                os.close(parent_descriptor)
        except OSError:
            raise InventoryArchiveError("Gate L2 local evidence is incomplete") from None
        return target, encoded

    inventory_path, inventory_encoded = local_evidence(
        plan.output_relative_path,
        maximum=plan.max_retained_output_bytes,
    )
    ledger_path, ledger_encoded = local_evidence(
        plan.ledger_relative_path,
        maximum=plan.limits.max_bytes,
    )
    _, local_record_encoded = local_evidence(
        plan.copy_record_relative_path,
        maximum=plan.max_local_record_bytes,
    )
    validator = load_request_ledger_validator(root, plan)
    events = validate_request_ledger_bytes(
        ledger_encoded,
        plan=plan,
        run_binding=run_binding,
        validator=validator,
        require_terminal_success=True,
    )
    if any(event["event_type"] == "request_outcome_unknown_after_send" for event in events):
        raise InventoryArchiveError("Gate L2 rejects unknown request outcomes")
    inventory = _strict_object(inventory_encoded, context="Gate L2 inventory")
    if validate_instance(inventory, root / plan.inventory_schema_relative_path):
        raise InventoryArchiveError("Gate L2 inventory schema validation failed")
    expected_run_identity = {
        "run_id": run_binding.run_id,
        "attempt": plan.attempt,
        "experiment_id": "EXP-0001",
        "profile_plan_id": "PLAN-EXP0001-SMOKE",
        "gate": "T07-L1",
        "branch": "phase-1/sira-smoke-lambda",
        "implementation_commit": run_binding.implementation_commit,
        "repository_commit": run_binding.repository_commit,
    }
    if (
        inventory.get("inventory_plan") != {"plan_id": plan.plan_id, "sha256": plan_sha256}
        or inventory.get("run_identity") != expected_run_identity
        or inventory.get("authorization_binding")
        != {
            "authorization_reference": run_binding.authorization_reference,
            "authorization_sha256": run_binding.authorization_sha256,
            "authorized": True,
        }
        or inventory.get("request_ledger") != inventory_ledger_contract_document_v3(plan)
        or inventory.get("limits") != inventory_limits_document_v3(plan)
    ):
        raise InventoryArchiveError("Gate L2 inventory provenance binding drifted")
    _validate_inventory_request_provenance(inventory, plan=plan, ledger_events=events)
    selection_state = _validate_inventory_selection_provenance(inventory)

    archive_path = Path(plan.archive_root) / run_binding.run_id
    try:
        archive_descriptor = _open_directory_no_symlinks(archive_path)
        try:
            external_inventory = _read_regular_at(
                archive_descriptor,
                INVENTORY_ARCHIVE_NAME,
                max_bytes=plan.max_retained_output_bytes,
            )
            external_ledger = _read_regular_at(
                archive_descriptor,
                LEDGER_ARCHIVE_NAME,
                max_bytes=plan.limits.max_bytes,
            )
            external_record_encoded = _read_regular_at(
                archive_descriptor,
                COPY_RECORD_NAME,
                max_bytes=plan.max_local_record_bytes,
            )
            seal_encoded = _read_regular_at(
                archive_descriptor,
                SEAL_NAME,
                max_bytes=plan.max_local_record_bytes,
            )
        finally:
            os.close(archive_descriptor)
    except OSError:
        raise InventoryArchiveError("Gate L2 external evidence is incomplete") from None
    if external_inventory != inventory_encoded or external_ledger != ledger_encoded:
        raise InventoryArchiveError("Gate L2 local/external evidence hashes differ")
    inventory_sha256 = hashlib.sha256(inventory_encoded).hexdigest()
    ledger_sha256 = hashlib.sha256(ledger_encoded).hexdigest()
    external_record_sha256 = hashlib.sha256(external_record_encoded).hexdigest()
    seal_sha256 = hashlib.sha256(seal_encoded).hexdigest()
    external_record = _strict_object(
        external_record_encoded,
        context="Gate L2 external copy record",
    )
    seal = _strict_object(seal_encoded, context="Gate L2 seal")
    local_record = _strict_object(
        local_record_encoded,
        context="Gate L2 local verification record",
    )
    if set(external_record) != EXTERNAL_RECORD_FIELDS or set(local_record) != LOCAL_RECORD_FIELDS:
        raise InventoryArchiveError("Gate L2 copy-record field set drifted")
    expected_files = [
        {
            "path": INVENTORY_ARCHIVE_NAME,
            "bytes": len(inventory_encoded),
            "sha256": inventory_sha256,
        },
        {
            "path": LEDGER_ARCHIVE_NAME,
            "bytes": len(ledger_encoded),
            "sha256": ledger_sha256,
        },
        {
            "path": COPY_RECORD_NAME,
            "bytes": len(external_record_encoded),
            "sha256": external_record_sha256,
        },
    ]
    if seal != {
        "schema_version": "0.3.0",
        "run_id": run_binding.run_id,
        "terminal_ledger_validated": True,
        "files": expected_files,
    }:
        raise InventoryArchiveError("Gate L2 external seal binding drifted")
    expected_common = {
        "plan_id": plan.plan_id,
        "plan_sha256": plan_sha256,
        "run_id": run_binding.run_id,
        "implementation_commit": run_binding.implementation_commit,
        "repository_commit": run_binding.repository_commit,
        "authorization_reference": run_binding.authorization_reference,
        "authorization_sha256": run_binding.authorization_sha256,
    }
    if (
        external_record.get("schema_version") != "0.3.0"
        or external_record.get("action_id") != ARCHIVE_ACTION_ID_V3
        or local_record.get("schema_version") != "0.3.0"
        or local_record.get("action_id") != ARCHIVE_ACTION_ID_V3
    ):
        raise InventoryArchiveError("Gate L2 copy-record contract version drifted")
    if any(external_record.get(key) != value for key, value in expected_common.items()):
        raise InventoryArchiveError("Gate L2 external record identity drifted")
    if (
        external_record.get("source_inventory_path") != str(inventory_path)
        or external_record.get("source_inventory_sha256") != inventory_sha256
        or external_record.get("source_inventory_bytes") != len(inventory_encoded)
        or external_record.get("source_ledger_path") != str(ledger_path)
        or external_record.get("source_ledger_sha256") != ledger_sha256
        or external_record.get("source_ledger_bytes") != len(ledger_encoded)
        or external_record.get("source_ledger_events") != len(events)
        or external_record.get("terminal_ledger_validated") is not True
        or external_record.get("source_retained") is not True
        or external_record.get("destination_path") != str(archive_path)
        or external_record.get("held_descriptor_guard") is not True
        or external_record.get("atomic_finalization") is not True
        or external_record.get("fsync_required") is not True
        or external_record.get("no_internal_fallback") is not True
    ):
        raise InventoryArchiveError("Gate L2 external record evidence drifted")
    if any(local_record.get(key) != value for key, value in expected_common.items()):
        raise InventoryArchiveError("Gate L2 local record identity drifted")
    if (
        local_record.get("source_inventory_path") != str(inventory_path)
        or local_record.get("source_inventory_sha256") != inventory_sha256
        or local_record.get("source_inventory_bytes") != len(inventory_encoded)
        or local_record.get("source_ledger_path") != str(ledger_path)
        or local_record.get("source_ledger_sha256") != ledger_sha256
        or local_record.get("source_ledger_bytes") != len(ledger_encoded)
        or local_record.get("source_ledger_events") != len(events)
        or local_record.get("destination_path") != str(archive_path)
        or local_record.get("destination_inventory_sha256") != inventory_sha256
        or local_record.get("destination_ledger_sha256") != ledger_sha256
        or local_record.get("destination_copy_record_sha256") != external_record_sha256
        or local_record.get("destination_seal_sha256") != seal_sha256
        or local_record.get("terminal_ledger_validated") is not True
        or local_record.get("held_descriptor_guard") is not True
        or local_record.get("source_destination_sha256_equal") is not True
        or local_record.get("source_retained_until_independent_verification") is not True
    ):
        raise InventoryArchiveError("Gate L2 local verification evidence drifted")
    external_capacity = _integer_value(
        external_record,
        "external_capacity_bytes",
        context="Gate L2 external record",
    )
    external_precopy_free = _integer_value(
        external_record,
        "external_precopy_free_bytes",
        context="Gate L2 external record",
    )
    external_retained_floor = _integer_value(
        external_record,
        "external_retained_floor_bytes",
        context="Gate L2 external record",
    )
    external_precopy_floor = _integer_value(
        external_record,
        "external_precopy_floor_bytes",
        context="Gate L2 external record",
    )
    external_postcopy_free = _integer_value(
        local_record,
        "external_postcopy_free_bytes",
        context="Gate L2 local record",
    )
    system_postcopy_free = _integer_value(
        local_record,
        "system_postcopy_free_bytes",
        context="Gate L2 local record",
    )
    if (
        external_retained_floor < 0
        or external_capacity <= 0
        or external_precopy_floor != external_retained_floor + plan.max_archive_bytes
        or external_precopy_free < external_precopy_floor
        or local_record.get("external_retained_floor_bytes") != external_retained_floor
        or external_postcopy_free < external_retained_floor
        or local_record.get("system_retained_floor_bytes") != plan.local_retained_floor_bytes
        or system_postcopy_free < plan.local_retained_floor_bytes
        or local_record.get("external_volume_uuid") != external_record.get("external_volume_uuid")
        or local_record.get("external_physical_store_uuid")
        != external_record.get("external_physical_store_uuid")
        or external_record.get("external_volume_uuid") != APPROVED_VOLUME_UUID
        or external_record.get("external_physical_store_uuid") != APPROVED_PHYSICAL_STORE_UUID
        or external_record.get("external_mount") != str(APPROVED_MOUNT)
        or not isinstance(external_record.get("copied_at_utc"), str)
        or not str(external_record["copied_at_utc"]).endswith("Z")
    ):
        raise InventoryArchiveError("Gate L2 storage provenance binding drifted")
    return GateL2EvidenceEligibilityV3(
        eligible=selection_state == "selected",
        selection_state=selection_state,
        inventory_sha256=inventory_sha256,
        ledger_sha256=ledger_sha256,
        archive_seal_sha256=seal_sha256,
        local_verification_sha256=hashlib.sha256(local_record_encoded).hexdigest(),
    )
