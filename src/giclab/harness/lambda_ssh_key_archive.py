"""Held-descriptor, one-way archive driver for T07 Gate L1A.

The driver is inert on import.  A future authorized supervisor prepares it before
secret access, stages the four already-sealed local evidence files, then finalizes
only after the one-request ledger has reached a durable successful terminal state.
No partial directory is eligible evidence and no cleanup broadly prunes state.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from jsonschema import Draft202012Validator, FormatChecker

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
from .lambda_request_ledger_v3 import RequestLedgerSnapshot
from .lambda_ssh_key_fingerprint import (
    ARCHIVE_ROOT,
    LEDGER_RELATIVE_PATH,
    LOCAL_VERIFICATION_RELATIVE_PATH,
    MAX_ARCHIVE_WALL_SECONDS,
    MAX_EXTERNAL_ARCHIVE_BYTES,
    MAX_LEDGER_BYTES,
    MAX_LOCAL_RAW_PRIVATE_EVIDENCE_BYTES,
    MAX_LOCAL_VERIFICATION_BYTES,
    MAX_RESPONSE_BYTES,
    MAX_SANITIZED_MATCH_REPORT_BYTES,
    PLAN_ID,
    RUN_ID,
    SSHKeyFingerprintPlan,
    SSHKeyRunBinding,
)
from .lambda_ssh_key_match import EvidenceFileIdentity, LocalEvidenceBundle
from .lambda_ssh_key_request_ledger import validate_ssh_key_request_ledger
from .sira_storage import APPROVED_MOUNT, SYSTEM_DATA_MOUNT, VolumeObservation

ARCHIVE_ACTION_ID = "t07-l1a-ssh-key-seal-copy"
LEDGER_ARCHIVE_NAME = "request-ledger.jsonl"
COPY_RECORD_NAME = "COPY_RECORD.json"
SEAL_NAME = "SEAL.json"
ARCHIVE_FINALIZATION_SCHEMA_VERSION = "0.1.0"
ARCHIVE_FINALIZATION_STARTED = "archive_finalization_started"
ARCHIVE_FINALIZATION_PASSED = "archive_finalization_passed"
ARCHIVE_FINALIZATION_FAILED = "archive_finalization_failed"
ARCHIVE_FINALIZATION_FAILURE_CODES = frozenset(
    {
        "L1A_ARCHIVE_FINALIZATION_FAILED",
        "L1A_ARCHIVE_DISPOSITION_FAILED",
        "L1A_TERMINAL_LEDGER_FAILED",
    }
)


@dataclass(frozen=True, slots=True)
class ArchivedSSHKeyEvidence:
    destination: Path
    seal_sha256: str
    copy_record_sha256: str
    ledger_sha256: str
    local_verification_record: bytes


@dataclass(frozen=True, slots=True)
class ArchiveFinalizationEvidence:
    """Authoritative post-ledger disposition for the complete L1A archive."""

    path: Path
    sha256: str
    bytes: int
    events: int
    state: str
    gate_l1a_evidence_complete: bool

    def __post_init__(self) -> None:
        if (
            self.events != 2
            or self.state not in {"passed", "failed"}
            or self.gate_l1a_evidence_complete != (self.state == "passed")
            or len(self.sha256) != 64
            or self.bytes <= 0
            or self.bytes > MAX_LOCAL_VERIFICATION_BYTES
        ):
            raise InventoryArchiveError("Gate L1A archive disposition is inconsistent")


def _finalization_common(
    plan: SSHKeyFingerprintPlan,
    run_binding: SSHKeyRunBinding,
    *,
    sequence: int,
    event_type: str,
    state: str,
    monotonic_ns: int,
    wall_timestamp_utc: str,
) -> dict[str, object]:
    return {
        "schema_version": ARCHIVE_FINALIZATION_SCHEMA_VERSION,
        "event_type": event_type,
        "event_sequence": sequence,
        "plan_id": PLAN_ID,
        "plan_sha256": plan.plan_sha256,
        "run_id": RUN_ID,
        "repository_commit": run_binding.repository_commit,
        "implementation_commit": run_binding.implementation_commit,
        "authorization_reference": run_binding.authorization_reference,
        "authorization_sha256": run_binding.authorization_sha256,
        "monotonic_timestamp_ns": monotonic_ns,
        "wall_timestamp_utc": wall_timestamp_utc,
        "archive_finalization_state": state,
        "terminal_request_ledger_sha256": None,
        "destination_path": None,
        "destination_copy_record_sha256": None,
        "destination_seal_sha256": None,
        "archive_verification_record_sha256": None,
        "archive_verification": None,
        "sanitized_failure_stage": None,
        "sanitized_failure_class": None,
        "stable_error_code": None,
        "source_destination_sha256_equal": False,
        "gate_l1a_evidence_complete": False,
        "selection_authorized": False,
        "gate_l2_authorized": False,
    }


def _validate_verification_document(
    encoded: bytes,
    *,
    archived: ArchivedSSHKeyEvidence,
    ledger: RequestLedgerSnapshot,
) -> dict[str, object]:
    if not encoded.endswith(b"\n") or len(encoded) > MAX_LOCAL_VERIFICATION_BYTES:
        raise InventoryArchiveError("Gate L1A archive verification envelope is invalid")
    try:
        document = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise InventoryArchiveError("Gate L1A archive verification is not JSON") from None
    if (
        not isinstance(document, dict)
        or any(not isinstance(key, str) for key in document)
        or document.get("run_id") != RUN_ID
        or document.get("plan_id") != PLAN_ID
        or document.get("destination_path") != str(archived.destination)
        or document.get("destination_copy_record_sha256") != archived.copy_record_sha256
        or document.get("destination_seal_sha256") != archived.seal_sha256
        or archived.ledger_sha256 != ledger.sha256
        or document.get("terminal_ledger_validated") is not True
        or document.get("source_destination_sha256_equal") is not True
        or document.get("source_retained_until_independent_verification") is not True
        or document.get("private_key_bytes_accessed") is not False
    ):
        raise InventoryArchiveError("Gate L1A archive verification contract drifted")
    return document


@dataclass(slots=True)
class FsyncArchiveFinalizationDisposition:
    """Append-only authority for post-ledger archive completion or failure.

    The request ledger can prove only that its evidence was staged before the
    ledger was sealed.  This separate file is created and fsynced before the
    external archive is finalized.  A complete L1A evidence set therefore
    requires a terminal ``passed`` event here; a terminal request ledger alone
    is never sufficient.
    """

    repository_root: Path
    path: Path
    descriptor: int
    plan: SSHKeyFingerprintPlan
    run_binding: SSHKeyRunBinding
    monotonic_ns: Callable[[], int]
    utc_now: Callable[[], datetime]
    next_sequence: int = 1
    bytes_written: int = 0
    closed: bool = False
    tainted: bool = False

    @classmethod
    def create(
        cls,
        repository_root: Path,
        *,
        plan: SSHKeyFingerprintPlan,
        run_binding: SSHKeyRunBinding,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> FsyncArchiveFinalizationDisposition:
        root = repository_root.resolve(strict=True)
        path = root / LOCAL_VERIFICATION_RELATIVE_PATH
        if (
            root != repository_root.absolute()
            or plan.plan_id != PLAN_ID
            or plan.run_id != RUN_ID
            or run_binding.plan_id != PLAN_ID
            or run_binding.run_id != RUN_ID
        ):
            raise InventoryArchiveError("Gate L1A archive disposition binding drifted")
        directory_descriptor = _open_directory_no_symlinks(path.parent)
        descriptor = -1
        try:
            descriptor = os.open(
                path.name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_APPEND
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=directory_descriptor,
            )
            os.fsync(directory_descriptor)
        except OSError:
            if descriptor >= 0:
                os.close(descriptor)
            raise InventoryArchiveError("Gate L1A archive disposition creation failed") from None
        finally:
            os.close(directory_descriptor)
        writer = cls(root, path, descriptor, plan, run_binding, monotonic_ns, utc_now)
        try:
            writer._append(
                _finalization_common(
                    plan,
                    run_binding,
                    sequence=1,
                    event_type=ARCHIVE_FINALIZATION_STARTED,
                    state="started",
                    monotonic_ns=monotonic_ns(),
                    wall_timestamp_utc=utc_now()
                    .astimezone(UTC)
                    .isoformat()
                    .replace("+00:00", "Z"),
                )
            )
        except Exception:
            writer.close_preserving_incomplete()
            raise
        return writer

    def _append(self, document: dict[str, object]) -> None:
        if self.closed or self.tainted or document.get("event_sequence") != self.next_sequence:
            raise InventoryArchiveError("Gate L1A archive disposition state is invalid")
        encoded = _canonical_bytes(document)
        if self.bytes_written + len(encoded) > MAX_LOCAL_VERIFICATION_BYTES:
            raise InventoryArchiveError("Gate L1A archive disposition exceeds its byte cap")
        offset = 0
        try:
            while offset < len(encoded):
                written = os.write(self.descriptor, encoded[offset:])
                if written < 1:
                    raise OSError
                offset += written
            os.fsync(self.descriptor)
        except OSError:
            self.tainted = bool(offset)
            raise InventoryArchiveError("Gate L1A archive disposition append failed") from None
        self.next_sequence += 1
        self.bytes_written += len(encoded)

    def record_passed(
        self,
        *,
        archived: ArchivedSSHKeyEvidence,
        ledger: RequestLedgerSnapshot,
    ) -> ArchiveFinalizationEvidence:
        verification = _validate_verification_document(
            archived.local_verification_record,
            archived=archived,
            ledger=ledger,
        )
        document = _finalization_common(
            self.plan,
            self.run_binding,
            sequence=2,
            event_type=ARCHIVE_FINALIZATION_PASSED,
            state="passed",
            monotonic_ns=self.monotonic_ns(),
            wall_timestamp_utc=self.utc_now()
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
        )
        document.update(
            {
                "terminal_request_ledger_sha256": ledger.sha256,
                "destination_path": str(archived.destination),
                "destination_copy_record_sha256": archived.copy_record_sha256,
                "destination_seal_sha256": archived.seal_sha256,
                "archive_verification_record_sha256": hashlib.sha256(
                    archived.local_verification_record
                ).hexdigest(),
                "archive_verification": verification,
                "source_destination_sha256_equal": True,
                "gate_l1a_evidence_complete": True,
            }
        )
        self._append(document)
        return self._seal(expected_state="passed", archived=archived, ledger=ledger)

    def record_failed(
        self,
        *,
        stable_error_code: str,
        ledger: RequestLedgerSnapshot | None,
        archived: ArchivedSSHKeyEvidence | None = None,
    ) -> ArchiveFinalizationEvidence:
        if stable_error_code not in ARCHIVE_FINALIZATION_FAILURE_CODES:
            raise InventoryArchiveError("Gate L1A archive failure code is not allowlisted")
        document = _finalization_common(
            self.plan,
            self.run_binding,
            sequence=2,
            event_type=ARCHIVE_FINALIZATION_FAILED,
            state="failed",
            monotonic_ns=self.monotonic_ns(),
            wall_timestamp_utc=self.utc_now()
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
        )
        document.update(
            {
                "terminal_request_ledger_sha256": ledger.sha256 if ledger is not None else None,
                "destination_path": str(archived.destination) if archived is not None else None,
                "destination_copy_record_sha256": (
                    archived.copy_record_sha256 if archived is not None else None
                ),
                "destination_seal_sha256": archived.seal_sha256 if archived is not None else None,
                "sanitized_failure_stage": "archive_io",
                "sanitized_failure_class": "archive_failed",
                "stable_error_code": stable_error_code,
            }
        )
        self._append(document)
        return self._seal(expected_state="failed", archived=archived, ledger=ledger)

    def _seal(
        self,
        *,
        expected_state: str,
        archived: ArchivedSSHKeyEvidence | None,
        ledger: RequestLedgerSnapshot | None,
    ) -> ArchiveFinalizationEvidence:
        if self.closed or self.tainted or self.next_sequence != 3:
            raise InventoryArchiveError("Gate L1A archive disposition cannot be sealed")
        try:
            os.fchmod(self.descriptor, 0o400)
            os.fsync(self.descriptor)
            os.close(self.descriptor)
        except OSError:
            self.closed = True
            raise InventoryArchiveError("Gate L1A archive disposition seal failed") from None
        self.closed = True
        return validate_gate_l1a_archive_disposition(
            self.repository_root,
            plan=self.plan,
            run_binding=self.run_binding,
            expected_state=expected_state,
            archived=archived,
            ledger=ledger,
        )

    def close_preserving_incomplete(self) -> None:
        if self.closed:
            return
        with suppress(OSError):
            os.fsync(self.descriptor)
        with suppress(OSError):
            os.close(self.descriptor)
        self.closed = True


def validate_gate_l1a_archive_disposition(
    repository_root: Path,
    *,
    plan: SSHKeyFingerprintPlan,
    run_binding: SSHKeyRunBinding,
    expected_state: str,
    archived: ArchivedSSHKeyEvidence | None,
    ledger: RequestLedgerSnapshot | None,
) -> ArchiveFinalizationEvidence:
    """Require the post-ledger disposition; a request ledger alone is ineligible."""

    if expected_state not in {"passed", "failed"}:
        raise InventoryArchiveError("Gate L1A archive disposition expectation is invalid")
    root = repository_root.resolve(strict=True)
    path = root / LOCAL_VERIFICATION_RELATIVE_PATH
    descriptor = _open_directory_no_symlinks(path.parent)
    try:
        encoded = _read_regular_at(
            descriptor,
            path.name,
            max_bytes=MAX_LOCAL_VERIFICATION_BYTES,
        )
        observed = os.stat(path.name, dir_fd=descriptor, follow_symlinks=False)
    finally:
        os.close(descriptor)
    if (
        not encoded.endswith(b"\n")
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or observed.st_uid != os.getuid()
        or stat.S_IMODE(observed.st_mode) != 0o400
    ):
        raise InventoryArchiveError("Gate L1A archive disposition identity is invalid")
    try:
        events = [json.loads(line) for line in encoded.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise InventoryArchiveError("Gate L1A archive disposition is not JSONL") from None
    if len(events) != 2 or any(not isinstance(event, dict) for event in events):
        raise InventoryArchiveError("Gate L1A archive disposition is incomplete")
    common = {
        "schema_version": ARCHIVE_FINALIZATION_SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "plan_sha256": plan.plan_sha256,
        "run_id": RUN_ID,
        "repository_commit": run_binding.repository_commit,
        "implementation_commit": run_binding.implementation_commit,
        "authorization_reference": run_binding.authorization_reference,
        "authorization_sha256": run_binding.authorization_sha256,
        "selection_authorized": False,
        "gate_l2_authorized": False,
    }
    required_keys = set(_finalization_common(
        plan,
        run_binding,
        sequence=1,
        event_type=ARCHIVE_FINALIZATION_STARTED,
        state="started",
        monotonic_ns=0,
        wall_timestamp_utc="2026-01-01T00:00:00Z",
    ))
    for sequence, event in enumerate(events, start=1):
        if (
            set(event) != required_keys
            or event.get("event_sequence") != sequence
            or any(event.get(key) != value for key, value in common.items())
            or type(event.get("monotonic_timestamp_ns")) is not int
            or int(event["monotonic_timestamp_ns"]) < 0
            or not isinstance(event.get("wall_timestamp_utc"), str)
        ):
            raise InventoryArchiveError("Gate L1A archive disposition fields drifted")
    first, terminal = events
    if (
        first.get("event_type") != ARCHIVE_FINALIZATION_STARTED
        or first.get("archive_finalization_state") != "started"
        or first.get("gate_l1a_evidence_complete") is not False
        or any(
            first.get(field) is not None
            for field in (
                "terminal_request_ledger_sha256",
                "destination_path",
                "destination_copy_record_sha256",
                "destination_seal_sha256",
                "archive_verification_record_sha256",
                "archive_verification",
                "sanitized_failure_stage",
                "sanitized_failure_class",
                "stable_error_code",
            )
        )
    ):
        raise InventoryArchiveError("Gate L1A archive start disposition drifted")
    if expected_state == "passed":
        if archived is None or ledger is None:
            raise InventoryArchiveError("Gate L1A passed disposition lacks bound evidence")
        verification = _validate_verification_document(
            archived.local_verification_record,
            archived=archived,
            ledger=ledger,
        )
        if (
            terminal.get("event_type") != ARCHIVE_FINALIZATION_PASSED
            or terminal.get("archive_finalization_state") != "passed"
            or terminal.get("terminal_request_ledger_sha256") != ledger.sha256
            or terminal.get("destination_path") != str(archived.destination)
            or terminal.get("destination_copy_record_sha256") != archived.copy_record_sha256
            or terminal.get("destination_seal_sha256") != archived.seal_sha256
            or terminal.get("archive_verification_record_sha256")
            != hashlib.sha256(archived.local_verification_record).hexdigest()
            or terminal.get("archive_verification") != verification
            or terminal.get("source_destination_sha256_equal") is not True
            or terminal.get("gate_l1a_evidence_complete") is not True
            or any(
                terminal.get(field) is not None
                for field in (
                    "sanitized_failure_stage",
                    "sanitized_failure_class",
                    "stable_error_code",
                )
            )
        ):
            raise InventoryArchiveError("Gate L1A passed archive disposition drifted")
    else:
        if (
            terminal.get("event_type") != ARCHIVE_FINALIZATION_FAILED
            or terminal.get("archive_finalization_state") != "failed"
            or terminal.get("gate_l1a_evidence_complete") is not False
            or terminal.get("source_destination_sha256_equal") is not False
            or terminal.get("sanitized_failure_stage") != "archive_io"
            or terminal.get("sanitized_failure_class") != "archive_failed"
            or terminal.get("stable_error_code") not in ARCHIVE_FINALIZATION_FAILURE_CODES
            or terminal.get("archive_verification_record_sha256") is not None
            or terminal.get("archive_verification") is not None
            or terminal.get("terminal_request_ledger_sha256")
            != (ledger.sha256 if ledger is not None else None)
        ):
            raise InventoryArchiveError("Gate L1A failed archive disposition drifted")
    return ArchiveFinalizationEvidence(
        path=path,
        sha256=hashlib.sha256(encoded).hexdigest(),
        bytes=len(encoded),
        events=len(events),
        state=expected_state,
        gate_l1a_evidence_complete=expected_state == "passed",
    )


class PreparedSSHKeyArchive(Protocol):
    """Single-use capability held from preflight through terminal sealing."""

    def stage(self, bundle: LocalEvidenceBundle) -> None: ...

    def finalize(
        self,
        bundle: LocalEvidenceBundle,
        *,
        ledger: RequestLedgerSnapshot,
    ) -> ArchivedSSHKeyEvidence: ...

    def close(self) -> None: ...


class SSHKeyArchiver(Protocol):
    def prepare(
        self,
        repository_root: Path,
        *,
        plan: SSHKeyFingerprintPlan,
        run_binding: SSHKeyRunBinding,
    ) -> PreparedSSHKeyArchive: ...


def _bundle_identities(bundle: LocalEvidenceBundle) -> tuple[EvidenceFileIdentity, ...]:
    values = (
        bundle.raw_response,
        bundle.private_manifest,
        bundle.sanitized_report,
        bundle.private_seal,
    )
    if bundle.total_bytes != sum(value.bytes for value in values):
        raise InventoryArchiveError("Gate L1A local bundle arithmetic drifted")
    return values


def _source_cap(identity: EvidenceFileIdentity) -> int:
    if identity.relative_path.endswith("ssh-keys-response.json"):
        return MAX_RESPONSE_BYTES
    if identity.relative_path.endswith("private-evidence.json"):
        return MAX_LOCAL_RAW_PRIVATE_EVIDENCE_BYTES
    if identity.relative_path.endswith("match-report.json"):
        return MAX_SANITIZED_MATCH_REPORT_BYTES
    if identity.relative_path.endswith("PRIVATE_EVIDENCE_SEAL.json"):
        return MAX_LOCAL_VERIFICATION_BYTES
    raise InventoryArchiveError("Gate L1A archive source path is not allowlisted")


def _read_source(
    repository_root: Path,
    identity: EvidenceFileIdentity,
    *,
    expected_device: int,
) -> bytes:
    relative = Path(identity.relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise InventoryArchiveError("Gate L1A archive source escaped the repository")
    path = repository_root / relative
    descriptor = _open_directory_no_symlinks(path.parent)
    try:
        encoded = _read_regular_at(descriptor, path.name, max_bytes=_source_cap(identity))
        observed = os.stat(path.name, dir_fd=descriptor, follow_symlinks=False)
    finally:
        os.close(descriptor)
    if (
        len(encoded) != identity.bytes
        or hashlib.sha256(encoded).hexdigest() != identity.sha256
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or observed.st_uid != os.getuid()
        or observed.st_dev != expected_device
    ):
        raise InventoryArchiveError("Gate L1A archive source identity drifted")
    return encoded


def _read_ledger(
    repository_root: Path,
    *,
    plan: SSHKeyFingerprintPlan,
    run_binding: SSHKeyRunBinding,
    snapshot: RequestLedgerSnapshot,
    expected_device: int,
) -> bytes:
    expected = repository_root / LEDGER_RELATIVE_PATH
    if snapshot.path != expected:
        raise InventoryArchiveError("Gate L1A ledger source path drifted")
    descriptor = _open_directory_no_symlinks(expected.parent)
    try:
        encoded = _read_regular_at(descriptor, expected.name, max_bytes=MAX_LEDGER_BYTES)
        observed = os.stat(expected.name, dir_fd=descriptor, follow_symlinks=False)
    finally:
        os.close(descriptor)
    if (
        len(encoded) != snapshot.bytes
        or hashlib.sha256(encoded).hexdigest() != snapshot.sha256
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or observed.st_uid != os.getuid()
        or observed.st_dev != expected_device
    ):
        raise InventoryArchiveError("Gate L1A terminal ledger identity drifted")
    schema_path = repository_root / plan.ledger_schema_relative_path
    try:
        schema_bytes = schema_path.read_bytes()
        if hashlib.sha256(schema_bytes).hexdigest() != plan.ledger_schema_sha256:
            raise ValueError
        validator = Draft202012Validator(
            json.loads(schema_bytes),
            format_checker=FormatChecker(),
        )
    except Exception:
        raise InventoryArchiveError("Gate L1A ledger schema binding drifted") from None
    try:
        events = validate_ssh_key_request_ledger(
            encoded,
            plan=plan,
            run_binding=run_binding,
            validator=validator,
            require_success=True,
        )
    except ValueError:
        raise InventoryArchiveError("Gate L1A terminal ledger is not successful") from None
    if len(events) != snapshot.events:
        raise InventoryArchiveError("Gate L1A terminal ledger count drifted")
    return encoded


@dataclass(slots=True)
class _PreparedDurableSSHKeyArchive:
    repository_root: Path
    plan: SSHKeyFingerprintPlan
    run_binding: SSHKeyRunBinding
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
    staged_identities: tuple[EvidenceFileIdentity, ...] = ()
    external_floor: int | None = None
    archive_started: float | None = None
    finalized: bool = False
    closed: bool = False

    def _check_wall(self) -> None:
        if (
            self.archive_started is None
            or self.clock() - self.archive_started > MAX_ARCHIVE_WALL_SECONDS
        ):
            raise InventoryArchiveError("Gate L1A archive wall budget expired")

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
            raise InventoryArchiveError("storage identity drifted during Gate L1A")
        floor = _validate_external(external, incremental_bytes=incremental)
        _validate_system(system, floor_bytes=self.plan.local_prewrite_floor_bytes)
        for handle in (
            self.external_mount,
            self.system_mount,
            self.repository,
            self.archive_root,
        ):
            handle.revalidate()
        return floor

    def stage(self, bundle: LocalEvidenceBundle) -> None:
        if self.closed or self.staging_name is not None or self.finalized:
            raise InventoryArchiveError("Gate L1A archive capability is stale or reused")
        identities = _bundle_identities(bundle)
        if (
            bundle.total_bytes + MAX_LEDGER_BYTES + (2 * MAX_LOCAL_VERIFICATION_BYTES)
            > MAX_EXTERNAL_ARCHIVE_BYTES
        ):
            raise InventoryArchiveError("Gate L1A archive capacity was not reserved")
        self.archive_started = self.clock()
        external, system = self.observer()
        self.external_floor = self._revalidate(
            external,
            system,
            incremental=MAX_EXTERNAL_ARCHIVE_BYTES,
        )
        self._check_wall()
        sources = [
            _read_source(
                self.repository_root,
                identity,
                expected_device=self.system_mount.device,
            )
            for identity in identities
        ]
        destination = self.run_binding.run_id
        try:
            os.stat(destination, dir_fd=self.archive_root.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise InventoryArchiveError("Gate L1A archive identity already exists")
        staging_name = f".{destination}.{uuid.uuid4().hex}.partial"
        staging_descriptor = -1
        try:
            os.mkdir(staging_name, mode=0o700, dir_fd=self.archive_root.descriptor)
            staging_descriptor = os.open(
                staging_name,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=self.archive_root.descriptor,
            )
            for identity, encoded in zip(identities, sources, strict=True):
                _write_exclusive_at(
                    staging_descriptor,
                    Path(identity.relative_path).name,
                    encoded,
                )
            os.fsync(staging_descriptor)
            os.fsync(self.archive_root.descriptor)
        except (InventoryArchiveError, OSError):
            if staging_descriptor >= 0:
                os.close(staging_descriptor)
            raise InventoryArchiveError("Gate L1A archive staging failed") from None
        self.staging_name = staging_name
        self.staging_descriptor = staging_descriptor
        self.staged_identities = identities
        self._check_wall()

    def finalize(
        self,
        bundle: LocalEvidenceBundle,
        *,
        ledger: RequestLedgerSnapshot,
    ) -> ArchivedSSHKeyEvidence:
        identities = _bundle_identities(bundle)
        if (
            self.closed
            or self.finalized
            or self.staging_name is None
            or self.staging_descriptor < 0
            or identities != self.staged_identities
            or self.external_floor is None
        ):
            raise InventoryArchiveError("Gate L1A evidence was not durably staged")
        self._check_wall()
        sources = [
            _read_source(
                self.repository_root,
                identity,
                expected_device=self.system_mount.device,
            )
            for identity in identities
        ]
        ledger_encoded = _read_ledger(
            self.repository_root,
            plan=self.plan,
            run_binding=self.run_binding,
            snapshot=ledger,
            expected_device=self.system_mount.device,
        )
        for identity, encoded in zip(identities, sources, strict=True):
            if (
                _read_regular_at(
                    self.staging_descriptor,
                    Path(identity.relative_path).name,
                    max_bytes=_source_cap(identity),
                )
                != encoded
            ):
                raise InventoryArchiveError("Gate L1A staged source verification failed")
        copied_at = self.utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z")
        source_files = [
            {
                "relative_path": identity.relative_path,
                "bytes": identity.bytes,
                "sha256": identity.sha256,
            }
            for identity in identities
        ]
        source_files.append(
            {
                "relative_path": LEDGER_RELATIVE_PATH,
                "bytes": ledger.bytes,
                "sha256": ledger.sha256,
            }
        )
        record = _canonical_bytes(
            {
                "schema_version": "0.1.0",
                "action_id": ARCHIVE_ACTION_ID,
                "plan_id": PLAN_ID,
                "plan_sha256": self.plan.plan_sha256,
                "run_id": RUN_ID,
                "implementation_commit": self.run_binding.implementation_commit,
                "repository_commit": self.run_binding.repository_commit,
                "authorization_reference": self.run_binding.authorization_reference,
                "authorization_sha256": self.run_binding.authorization_sha256,
                "source_files": source_files,
                "source_retained": True,
                "destination_path": str(Path(ARCHIVE_ROOT) / RUN_ID),
                "copied_at_utc": copied_at,
                "external_volume_uuid": self.external_at_prepare.volume_uuid.upper(),
                "external_physical_store_uuid": (
                    self.external_at_prepare.physical_store_uuid or ""
                ).upper(),
                "external_retained_floor_bytes": self.external_floor,
                "held_descriptor_guard": True,
                "terminal_ledger_validated": True,
                "atomic_finalization": True,
                "fsync_required": True,
                "no_internal_fallback": True,
            }
        )
        if len(record) > MAX_LOCAL_VERIFICATION_BYTES:
            raise InventoryArchiveError("Gate L1A copy record exceeds its byte cap")
        _write_exclusive_at(self.staging_descriptor, LEDGER_ARCHIVE_NAME, ledger_encoded)
        _write_exclusive_at(self.staging_descriptor, COPY_RECORD_NAME, record)
        sealed_files = [
            {
                "path": Path(identity.relative_path).name,
                "bytes": identity.bytes,
                "sha256": identity.sha256,
            }
            for identity in identities
        ]
        sealed_files.extend(
            (
                {
                    "path": LEDGER_ARCHIVE_NAME,
                    "bytes": ledger.bytes,
                    "sha256": ledger.sha256,
                },
                {
                    "path": COPY_RECORD_NAME,
                    "bytes": len(record),
                    "sha256": hashlib.sha256(record).hexdigest(),
                },
            )
        )
        seal = _canonical_bytes(
            {
                "schema_version": "0.1.0",
                "run_id": RUN_ID,
                "terminal_ledger_validated": True,
                "files": sealed_files,
            }
        )
        total = sum(len(value) for value in sources) + len(ledger_encoded) + len(record) + len(seal)
        if len(seal) > MAX_LOCAL_VERIFICATION_BYTES or total > MAX_EXTERNAL_ARCHIVE_BYTES:
            raise InventoryArchiveError("Gate L1A sealed archive exceeds its byte cap")
        _write_exclusive_at(self.staging_descriptor, SEAL_NAME, seal)
        os.fsync(self.staging_descriptor)
        os.fchmod(self.staging_descriptor, 0o500)
        os.rename(
            self.staging_name,
            RUN_ID,
            src_dir_fd=self.archive_root.descriptor,
            dst_dir_fd=self.archive_root.descriptor,
        )
        self.staging_name = None
        os.fsync(self.archive_root.descriptor)
        self.finalized = True
        destination_descriptor = os.open(
            RUN_ID,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=self.archive_root.descriptor,
        )
        try:
            for identity, encoded in zip(identities, sources, strict=True):
                if (
                    _read_regular_at(
                        destination_descriptor,
                        Path(identity.relative_path).name,
                        max_bytes=_source_cap(identity),
                    )
                    != encoded
                ):
                    raise InventoryArchiveError("Gate L1A final source verification failed")
            if (
                _read_regular_at(
                    destination_descriptor,
                    LEDGER_ARCHIVE_NAME,
                    max_bytes=MAX_LEDGER_BYTES,
                )
                != ledger_encoded
            ):
                raise InventoryArchiveError("Gate L1A final ledger verification failed")
            if (
                _read_regular_at(
                    destination_descriptor,
                    COPY_RECORD_NAME,
                    max_bytes=MAX_LOCAL_VERIFICATION_BYTES,
                )
                != record
                or _read_regular_at(
                    destination_descriptor,
                    SEAL_NAME,
                    max_bytes=MAX_LOCAL_VERIFICATION_BYTES,
                )
                != seal
            ):
                raise InventoryArchiveError("Gate L1A final seal verification failed")
        finally:
            os.close(destination_descriptor)
        external_post, system_post = self.observer()
        self._revalidate(external_post, system_post, incremental=0)
        if external_post.free_bytes < self.external_floor:
            raise InventoryArchiveError("Gate L1A retained external floor failed")
        _validate_system(system_post, floor_bytes=self.plan.local_prewrite_floor_bytes)
        self._check_wall()
        copy_hash = hashlib.sha256(record).hexdigest()
        seal_hash = hashlib.sha256(seal).hexdigest()
        local_verification = _canonical_bytes(
            {
                "schema_version": "0.1.0",
                "action_id": ARCHIVE_ACTION_ID,
                "plan_id": PLAN_ID,
                "plan_sha256": self.plan.plan_sha256,
                "run_id": RUN_ID,
                "repository_commit": self.run_binding.repository_commit,
                "implementation_commit": self.run_binding.implementation_commit,
                "authorization_reference": self.run_binding.authorization_reference,
                "authorization_sha256": self.run_binding.authorization_sha256,
                "source_files": source_files,
                "destination_path": str(Path(ARCHIVE_ROOT) / RUN_ID),
                "destination_copy_record_sha256": copy_hash,
                "destination_seal_sha256": seal_hash,
                "external_volume_uuid": external_post.volume_uuid.upper(),
                "external_physical_store_uuid": (external_post.physical_store_uuid or "").upper(),
                "external_postcopy_free_bytes": external_post.free_bytes,
                "external_retained_floor_bytes": self.external_floor,
                "system_postcopy_free_bytes": system_post.free_bytes,
                "held_descriptor_guard": True,
                "terminal_ledger_validated": True,
                "source_destination_sha256_equal": True,
                "source_retained_until_independent_verification": True,
                "private_key_bytes_accessed": False,
            }
        )
        if len(local_verification) > MAX_LOCAL_VERIFICATION_BYTES:
            raise InventoryArchiveError("Gate L1A local verification exceeds its byte cap")
        return ArchivedSSHKeyEvidence(
            destination=Path(ARCHIVE_ROOT) / RUN_ID,
            seal_sha256=seal_hash,
            copy_record_sha256=copy_hash,
            ledger_sha256=ledger.sha256,
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
class DurableSSHKeyArchiver:
    """Concrete future archiver; construction and import perform no I/O."""

    observer_factory: Callable[[], DiskutilVolumeObserver] = DiskutilVolumeObserver
    clock: Callable[[], float] = time.monotonic
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC)

    def prepare(
        self,
        repository_root: Path,
        *,
        plan: SSHKeyFingerprintPlan,
        run_binding: SSHKeyRunBinding,
    ) -> PreparedSSHKeyArchive:
        root = repository_root.resolve(strict=True)
        if (
            root != repository_root.absolute()
            or plan.plan_id != PLAN_ID
            or plan.run_id != RUN_ID
            or run_binding.plan_id != PLAN_ID
            or run_binding.run_id != RUN_ID
        ):
            raise InventoryArchiveError("Gate L1A archive binding drifted")
        observer = self.observer_factory()
        external, system = observer()
        _validate_external(external, incremental_bytes=MAX_EXTERNAL_ARCHIVE_BYTES)
        _validate_system(system, floor_bytes=plan.local_prewrite_floor_bytes)
        external_handle = _HeldDirectory.open(APPROVED_MOUNT)
        system_handle: _HeldDirectory | None = None
        repository_handle: _HeldDirectory | None = None
        archive_handle: _HeldDirectory | None = None
        try:
            system_handle = _HeldDirectory.open(SYSTEM_DATA_MOUNT)
            if external_handle.device == system_handle.device:
                raise InventoryArchiveError("Gate L1A source and destination share a filesystem")
            repository_handle = _HeldDirectory.open(root)
            if repository_handle.device != system_handle.device:
                raise InventoryArchiveError("Gate L1A active root is not on the Mac mini volume")
            archive_handle = _open_or_create_archive_root(external_handle, Path(ARCHIVE_ROOT))
            if archive_handle.device != external_handle.device:
                raise InventoryArchiveError("Gate L1A archive used an internal fallback")
            return _PreparedDurableSSHKeyArchive(
                repository_root=root,
                plan=plan,
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
            for handle in (archive_handle, repository_handle, system_handle, external_handle):
                if handle is not None:
                    handle.close()
            raise
