"""Bounded local evidence writer and one-way Gate L2 archive implementation.

Import is inert. A future authorized supervisor writes each bounded SSH/provider/
container record exclusively, verifies its transport hash after fsync, seals a flat
manifest, then copies that immutable bundle to the approved external APFS archive.
"""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator

from .lambda_archive import (
    DiskutilVolumeObserver,
    InventoryArchiveError,
    _HeldDirectory,
    _open_or_create_archive_root,
    _same_identity,
    _validate_external,
    _validate_system,
)
from .lambda_l20_plan import (
    EXTERNAL_ARCHIVE_ROOT,
    MAX_ARCHIVE_BYTES,
    MAX_MAC_ACTIVE_EVIDENCE_BYTES,
    MAX_REMOTE_EVIDENCE_BYTES,
    MIN_LOCAL_PREWRITE_FREE_BYTES,
    MIN_LOCAL_RETAINED_FREE_BYTES,
    RUN_ID,
    canonical_bytes,
    sha256_bytes,
)
from .sira_storage import VolumeObservation

LOCAL_EVIDENCE_ROOT_RELATIVE: Final = Path("artifacts/t07/lambda/gate-l2") / RUN_ID
EXTERNAL_EVIDENCE_ARCHIVE_ID: Final = f"{RUN_ID}-HOST-EVIDENCE"
MANIFEST_NAME: Final = "EVIDENCE_MANIFEST.json"
LOCAL_SEAL_NAME: Final = "LOCAL_EVIDENCE_SEAL.json"
EXTERNAL_COPY_RECORD_NAME: Final = "COPY_RECORD.json"
EXTERNAL_SEAL_NAME: Final = "EXTERNAL_EVIDENCE_SEAL.json"
MAX_RECORD_BYTES: Final = 1_048_576
MAX_RECORD_COUNT: Final = 96
_RECORD_NAME = re.compile(r"^[0-9]{4}-[a-z0-9][a-z0-9._-]{0,94}\.(?:json|jsonl|txt|bin)$")


class L2EvidenceError(ValueError):
    """A Gate L2 evidence write, seal, or copy violated its exact contract."""


def validate_evidence_document(
    repository_root: Path,
    document: dict[str, object],
    *,
    incident: bool,
) -> None:
    """Validate a success or incident document against the coherent L2 schema."""

    relative = (
        "schemas/t07-lambda-l2-incident.schema.json"
        if incident
        else "schemas/t07-lambda-l2-host-evidence.schema.json"
    )
    try:
        schema = json.loads((repository_root / relative).read_bytes())
    except (OSError, json.JSONDecodeError):
        raise L2EvidenceError("Gate L2 evidence schema is unavailable") from None
    if list(Draft202012Validator(schema).iter_errors(document)):
        raise L2EvidenceError("Gate L2 evidence document failed its exact schema")


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    name: str
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class SealedEvidenceBundle:
    root: Path
    records: tuple[EvidenceRecord, ...]
    manifest_sha256: str
    local_seal_sha256: str
    total_bytes: int


@dataclass(frozen=True, slots=True)
class ArchivedEvidenceBundle:
    destination: Path
    bundle_sha256: str
    total_bytes: int
    external_seal_sha256: str
    copy_record_sha256: str
    source_retained: bool


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _write_exclusive(directory_fd: int, name: str, encoded: bytes) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory_fd,
    )
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written < 1:
                raise OSError
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
    finally:
        os.close(descriptor)


def _read_regular(directory_fd: int, name: str, *, max_bytes: int) -> bytes:
    descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory_fd)
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1:
            raise L2EvidenceError("evidence member is not one regular file")
        output = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > max_bytes:
                raise L2EvidenceError("evidence member exceeds its byte cap")
        return bytes(output)
    finally:
        os.close(descriptor)


@dataclass(slots=True)
class GateL2EvidenceWriter:
    root: Path
    descriptor: int
    records: list[EvidenceRecord] = field(default_factory=list)
    bytes_written: int = 0
    sealed: bool = False

    @classmethod
    def create(cls, repository_root: Path) -> GateL2EvidenceWriter:
        root = repository_root.resolve(strict=True)
        relative = LOCAL_EVIDENCE_ROOT_RELATIVE
        descriptor = os.open(root, _directory_flags())
        try:
            for index, component in enumerate(relative.parts):
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                    os.fsync(descriptor)
                except FileExistsError:
                    if index == len(relative.parts) - 1:
                        raise L2EvidenceError("Gate L2 evidence run root already exists") from None
                child = os.open(component, _directory_flags(), dir_fd=descriptor)
                status = os.fstat(child)
                if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid():
                    os.close(child)
                    raise L2EvidenceError("Gate L2 evidence hierarchy is unsafe")
                os.close(descriptor)
                descriptor = child
            return cls(root / relative, descriptor)
        except Exception:
            with suppress(OSError):
                os.close(descriptor)
            raise

    def write_transferred_record(
        self,
        *,
        name: str,
        encoded: bytes,
        source_transport_sha256: str,
    ) -> EvidenceRecord:
        """Write one streamed record and verify source-vs-fsynced destination SHA-256."""

        if (
            self.sealed
            or _RECORD_NAME.fullmatch(name) is None
            or len(encoded) > MAX_RECORD_BYTES
            or len(self.records) >= MAX_RECORD_COUNT
        ):
            raise L2EvidenceError("evidence record identity or cap failed")
        if self.bytes_written + len(encoded) > MAX_REMOTE_EVIDENCE_BYTES:
            raise L2EvidenceError("aggregate remote evidence cap failed")
        if sha256_bytes(encoded) != source_transport_sha256:
            raise L2EvidenceError("source transport hash does not match received bytes")
        try:
            _write_exclusive(self.descriptor, name, encoded)
            observed = _read_regular(self.descriptor, name, max_bytes=MAX_RECORD_BYTES)
            if sha256_bytes(observed) != source_transport_sha256:
                raise L2EvidenceError("fsynced local evidence hash differs from source")
            os.fsync(self.descriptor)
        except OSError:
            raise L2EvidenceError("evidence record filesystem action failed") from None
        record = EvidenceRecord(name, len(encoded), source_transport_sha256)
        self.records.append(record)
        self.bytes_written += len(encoded)
        return record

    def seal(self) -> SealedEvidenceBundle:
        if self.sealed or not self.records:
            raise L2EvidenceError("empty or already sealed Gate L2 evidence")
        manifest = canonical_bytes(
            {
                "schema_version": "0.1.0",
                "plan_id": "PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V1",
                "run_id": RUN_ID,
                "records": [
                    {"name": record.name, "bytes": record.bytes, "sha256": record.sha256}
                    for record in self.records
                ],
            }
        )
        manifest_sha = sha256_bytes(manifest)
        seal = canonical_bytes(
            {
                "schema_version": "0.1.0",
                "run_id": RUN_ID,
                "manifest_sha256": manifest_sha,
                "record_count": len(self.records),
                "record_bytes": self.bytes_written,
                "source_retained": True,
            }
        )
        if self.bytes_written + len(manifest) + len(seal) > MAX_MAC_ACTIVE_EVIDENCE_BYTES:
            raise L2EvidenceError("sealed local evidence exceeds its cap")
        try:
            _write_exclusive(self.descriptor, MANIFEST_NAME, manifest)
            _write_exclusive(self.descriptor, LOCAL_SEAL_NAME, seal)
            os.fsync(self.descriptor)
        except OSError:
            raise L2EvidenceError("local evidence seal write failed") from None
        self.sealed = True
        return SealedEvidenceBundle(
            self.root,
            tuple(self.records),
            manifest_sha,
            sha256_bytes(seal),
            self.bytes_written + len(manifest) + len(seal),
        )

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1


def copy_sealed_evidence_bundle(
    bundle: SealedEvidenceBundle,
    *,
    destination_parent: Path,
    archive_id: str,
    require_distinct_device: bool,
) -> ArchivedEvidenceBundle:
    """Copy one immutable flat bundle with no overwrite and verified hashes."""

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", archive_id):
        raise L2EvidenceError("external archive identity is unsafe")
    source = _HeldDirectory.open(bundle.root)
    destination = _HeldDirectory.open(destination_parent)
    staging: _HeldDirectory | None = None
    finalized: _HeldDirectory | None = None
    try:
        if require_distinct_device and source.device == destination.device:
            raise L2EvidenceError("Gate L2 archive fell back to the source filesystem")
        staging_name = f".{archive_id}.partial"
        for name in (archive_id, staging_name):
            try:
                os.stat(name, dir_fd=destination.descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise L2EvidenceError("Gate L2 archive identity already exists")
        os.mkdir(staging_name, 0o700, dir_fd=destination.descriptor)
        os.fsync(destination.descriptor)
        staging = _HeldDirectory.open(destination_parent / staging_name)
        members = [
            *bundle.records,
            EvidenceRecord(MANIFEST_NAME, 0, bundle.manifest_sha256),
            EvidenceRecord(LOCAL_SEAL_NAME, 0, bundle.local_seal_sha256),
        ]
        copied: list[dict[str, object]] = []
        total = 0
        for member in members:
            encoded = _read_regular(source.descriptor, member.name, max_bytes=MAX_RECORD_BYTES)
            digest = sha256_bytes(encoded)
            if digest != member.sha256:
                raise L2EvidenceError("sealed source member hash drifted")
            _write_exclusive(staging.descriptor, member.name, encoded)
            destination_bytes = _read_regular(
                staging.descriptor,
                member.name,
                max_bytes=MAX_RECORD_BYTES,
            )
            if destination_bytes != encoded:
                raise L2EvidenceError("external evidence member verification failed")
            copied.append({"name": member.name, "bytes": len(encoded), "sha256": digest})
            total += len(encoded)
        copy_record = canonical_bytes(
            {
                "schema_version": "0.1.0",
                "run_id": RUN_ID,
                "archive_id": archive_id,
                "members": copied,
                "source_retained": True,
                "destination_hashes_verified": True,
            }
        )
        copy_sha = sha256_bytes(copy_record)
        external_seal = canonical_bytes(
            {
                "schema_version": "0.1.0",
                "run_id": RUN_ID,
                "archive_id": archive_id,
                "copy_record_sha256": copy_sha,
                "source_manifest_sha256": bundle.manifest_sha256,
                "destination_hashes_verified": True,
                "source_retained": True,
            }
        )
        total += len(copy_record) + len(external_seal)
        if total > MAX_ARCHIVE_BYTES:
            raise L2EvidenceError("external evidence archive exceeds its cap")
        _write_exclusive(staging.descriptor, EXTERNAL_COPY_RECORD_NAME, copy_record)
        _write_exclusive(staging.descriptor, EXTERNAL_SEAL_NAME, external_seal)
        os.fsync(staging.descriptor)
        os.rename(
            staging_name,
            archive_id,
            src_dir_fd=destination.descriptor,
            dst_dir_fd=destination.descriptor,
        )
        os.fsync(destination.descriptor)
        final = destination_parent / archive_id
        finalized = _HeldDirectory.open(final)
        for item in copied:
            encoded = _read_regular(
                finalized.descriptor,
                str(item["name"]),
                max_bytes=MAX_RECORD_BYTES,
            )
            if sha256_bytes(encoded) != item["sha256"] or len(encoded) != item["bytes"]:
                raise L2EvidenceError("finalized external member verification failed")
        if (
            sha256_bytes(
                _read_regular(
                    finalized.descriptor,
                    EXTERNAL_COPY_RECORD_NAME,
                    max_bytes=MAX_RECORD_BYTES,
                )
            )
            != copy_sha
            or sha256_bytes(
                _read_regular(
                    finalized.descriptor,
                    EXTERNAL_SEAL_NAME,
                    max_bytes=MAX_RECORD_BYTES,
                )
            )
            != sha256_bytes(external_seal)
        ):
            raise L2EvidenceError("finalized external control-record verification failed")
        bundle_hash = sha256_bytes(
            canonical_bytes({"members": copied, "copy_record_sha256": copy_sha})
        )
        return ArchivedEvidenceBundle(
            final,
            bundle_hash,
            total,
            sha256_bytes(external_seal),
            copy_sha,
            True,
        )
    except (OSError, InventoryArchiveError):
        raise L2EvidenceError("Gate L2 archive filesystem contract failed") from None
    finally:
        if finalized is not None:
            finalized.close()
        if staging is not None:
            staging.close()
        destination.close()
        source.close()


def archive_to_approved_external(
    bundle: SealedEvidenceBundle,
    *,
    observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] | None = None,
) -> ArchivedEvidenceBundle:
    """Revalidate UTDM identity/floors around the exact one-way archive copy."""

    observe = observer or DiskutilVolumeObserver()
    try:
        external_before, system_before = observe()
        _validate_external(external_before, incremental_bytes=MAX_ARCHIVE_BYTES)
        _validate_system(system_before, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
    except (InventoryArchiveError, TypeError):
        raise L2EvidenceError("Gate L2 archive preflight failed") from None
    external = _HeldDirectory.open(Path("/Volumes/Macintosh HD - Data"))
    archive_root: _HeldDirectory | None = None
    try:
        archive_root = _open_or_create_archive_root(external, EXTERNAL_ARCHIVE_ROOT)
        result = copy_sealed_evidence_bundle(
            bundle,
            destination_parent=EXTERNAL_ARCHIVE_ROOT,
            archive_id=EXTERNAL_EVIDENCE_ARCHIVE_ID,
            require_distinct_device=True,
        )
        external_after, system_after = observe()
        if not _same_identity(external_before, external_after) or not _same_identity(
            system_before,
            system_after,
        ):
            raise L2EvidenceError("storage identity changed during Gate L2 archive")
        _validate_external(external_after, incremental_bytes=0)
        _validate_system(system_after, floor_bytes=MIN_LOCAL_RETAINED_FREE_BYTES)
        return result
    except InventoryArchiveError:
        raise L2EvidenceError("Gate L2 archive postflight failed") from None
    finally:
        if archive_root is not None:
            archive_root.close()
        external.close()
