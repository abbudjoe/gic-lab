"""Private, single-use checkpoint validation for T07 Gate L2M.

The reader is local-only and never accesses a credential, provider, browser, Jupyter,
SSH, or cloud mutation boundary.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final

from jsonschema import Draft202012Validator

CHECKPOINT_TYPES: Final = (
    "launch_wizard_image_offered",
    "global_firewall_restricted",
    "regional_ruleset_created",
    "launch_configuration_selected",
    "launch_clicked_once",
    "instance_bound",
    "cloud_ide_opened",
    "qualification_bundle_uploaded",
    "qualification_command_started",
    "qualification_command_completed",
    "qualification_bundle_downloaded",
    "termination_confirmed_by_user",
    "instance_terminal_verified",
    "regional_ruleset_deleted",
    "global_firewall_restored",
)
USER_CHECKPOINT_TYPES: Final = tuple(
    checkpoint_type
    for checkpoint_type in CHECKPOINT_TYPES
    if checkpoint_type not in {"instance_bound", "instance_terminal_verified"}
)
MAX_CHECKPOINT_BYTES: Final = 16_384
MAX_CHECKPOINT_WINDOW_SECONDS: Final = 300
MAX_CONSUMPTION_LEDGER_BYTES: Final = 262_144
MAX_BOUND_SCHEMA_BYTES: Final = 65_536
_BOUND_CHECKPOINT_SCHEMA_RELATIVE_PATH: Final = Path(
    "schemas/t07-lambda-l2m-checkpoint.schema.json"
)
_BOUND_CHECKPOINT_SCHEMA_SHA256: Final = (
    "a55f9023f8cc8f530acebe31bbe7b50c57d1e1a01b959ced38876e43e0f108ff"
)
_BOUND_HUMAN_DECISION_SCHEMA_RELATIVE_PATH: Final = Path(
    "schemas/t07-lambda-l2m-human-decision.schema.json"
)
_BOUND_HUMAN_DECISION_SCHEMA_SHA256: Final = (
    "7054b83d9aa56683b24ba3c1057ca6f9aeb9ae1ee38fc3d2f37179514d4f1d79"
)
_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_DECISION_ALIAS: Final = re.compile(r"^l2m-decision-[a-f0-9]{12}$")
_HUMAN_DECISION_ISSUER: Final = object()
_CONSUMPTION_KEYS: Final = {
    "schema_version",
    "sequence",
    "run_id",
    "decision_alias",
    "marker_alias",
    "checkpoint_type",
    "checkpoint_nonce",
    "checkpoint_sha256",
}


class CheckpointContractError(ValueError):
    """Raised for an unsafe, stale, reused, or invalid private checkpoint."""


@dataclass(frozen=True, slots=True)
class CheckpointBinding:
    run_id: str
    decision_alias: str
    marker_alias: str


@dataclass(frozen=True, slots=True)
class VerifiedCheckpoint:
    checkpoint_type: str
    observed_at_utc: dt.datetime
    encoded_sha256: str
    launch_clicked_once: bool
    details: Mapping[str, object] = field(repr=False)


class CheckpointConsumptionOutcomeUnknown(CheckpointContractError):
    """A validated checkpoint was burned but its ledger write was not fully durable."""

    def __init__(
        self,
        checkpoint: VerifiedCheckpoint,
        *,
        content_complete: bool,
        interruption: BaseException | None = None,
    ) -> None:
        super().__init__("checkpoint consumption outcome is unknown")
        self.checkpoint = checkpoint
        self.content_complete = content_complete
        self.interruption = interruption


class _ConsumptionAppendFailure(CheckpointContractError):
    def __init__(
        self,
        *,
        content_complete: bool,
        record_start: int,
        expected_record: bytes,
    ) -> None:
        super().__init__("checkpoint consumption record durability is unknown")
        self.content_complete = content_complete
        self.record_start = record_start
        self.expected_record = expected_record


@dataclass(frozen=True, slots=True)
class CheckpointConsumptionEvidence:
    path: Path
    device: int
    inode: int
    byte_count: int
    sha256: str
    encoded: bytes = field(repr=False)
    complete: bool = True


@dataclass(frozen=True, slots=True)
class ValidatedHumanDecision:
    """Opaque capability binding one schema-valid private decision to the engine."""

    decision_alias: str
    source_ipv4_cidr: str = field(repr=False)
    decision_sha256: str
    repository_root: Path = field(repr=False, compare=False)
    _issuer: object = field(repr=False, compare=False)


def is_validated_human_decision(value: ValidatedHumanDecision) -> bool:
    return (
        value._issuer is _HUMAN_DECISION_ISSUER
        and _DECISION_ALIAS.fullmatch(value.decision_alias) is not None
        and _HEX64.fullmatch(value.decision_sha256) is not None
        and value.repository_root.is_absolute()
    )


def _strict_json(encoded: bytes) -> Mapping[str, object]:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise CheckpointContractError("checkpoint contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(encoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CheckpointContractError("checkpoint is not strict JSON") from None
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise CheckpointContractError("checkpoint must be an object")
    return value


def _strict_details(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise CheckpointContractError("checkpoint details must be an object")
    if any(not isinstance(item, (bool, str)) for item in value.values()):
        raise CheckpointContractError("checkpoint details contain an unsupported value")
    return value


def _repository_root_for_bound_schema(
    path: Path,
    *,
    relative_path: Path,
    context: str,
) -> Path:
    absolute = path.absolute()
    if tuple(absolute.parts[-len(relative_path.parts) :]) != relative_path.parts:
        raise CheckpointContractError(f"{context} path is not repository-bound")
    root = absolute
    for _ in relative_path.parts:
        root = root.parent
    try:
        resolved = root.resolve(strict=True)
        identity = root.lstat()
    except OSError:
        raise CheckpointContractError(f"{context} repository root is unavailable") from None
    if resolved != root or not stat.S_ISDIR(identity.st_mode):
        raise CheckpointContractError(f"{context} repository root is unsafe")
    return root


def _load_bound_schema(path: Path, *, expected_sha256: str) -> Mapping[str, object]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        identity = os.fstat(descriptor)
        encoded = os.read(descriptor, MAX_BOUND_SCHEMA_BYTES + 1)
    finally:
        os.close(descriptor)
    if (
        not stat.S_ISREG(identity.st_mode)
        or identity.st_nlink != 1
        or len(encoded) != identity.st_size
        or len(encoded) > MAX_BOUND_SCHEMA_BYTES
        or hashlib.sha256(encoded).hexdigest() != expected_sha256
    ):
        raise CheckpointContractError("bound schema identity drifted")
    return _strict_json(encoded)


def _parse_utc(value: object) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CheckpointContractError("checkpoint timestamp must be UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise CheckpointContractError("checkpoint timestamp is invalid") from None
    return parsed


def _open_consumption_ledger(
    path: Path, *, expected_uid: int, binding: CheckpointBinding
) -> tuple[int, tuple[Mapping[str, object], ...]]:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = path.parent.lstat()
    if (
        not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != expected_uid
        or stat.S_IMODE(parent.st_mode) & 0o077
    ):
        raise CheckpointContractError("checkpoint consumption parent is unsafe")
    flags = os.O_RDWR | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    created = False
    try:
        descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
    except FileExistsError:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != expected_uid
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size > MAX_CONSUMPTION_LEDGER_BYTES
        ):
            raise CheckpointContractError("checkpoint consumption ledger is unsafe") from None
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            os.close(descriptor)
            raise CheckpointContractError(
                "checkpoint consumption ledger identity changed"
            ) from None
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CheckpointContractError(
                "checkpoint consumption ledger is already owned"
            ) from None
        opened = os.fstat(descriptor)
        encoded = os.pread(descriptor, MAX_CONSUMPTION_LEDGER_BYTES + 1, 0)
        if len(encoded) > MAX_CONSUMPTION_LEDGER_BYTES or len(encoded) != opened.st_size:
            raise CheckpointContractError("checkpoint consumption ledger size drifted")
        records: list[Mapping[str, object]] = []
        seen_types: set[str] = set()
        seen_nonces: set[str] = set()
        seen_sha256s: set[str] = set()
        for sequence, line in enumerate(encoded.splitlines(), start=1):
            record = _strict_json(line)
            checkpoint_type = record.get("checkpoint_type")
            checkpoint_nonce = record.get("checkpoint_nonce")
            checkpoint_sha256 = record.get("checkpoint_sha256")
            if (
                set(record) != _CONSUMPTION_KEYS
                or record.get("schema_version") != "0.1.0"
                or record.get("sequence") != sequence
                or record.get("run_id") != binding.run_id
                or record.get("decision_alias") != binding.decision_alias
                or record.get("marker_alias") != binding.marker_alias
                or checkpoint_type not in CHECKPOINT_TYPES
                or not isinstance(checkpoint_nonce, str)
                or _HEX64.fullmatch(checkpoint_nonce) is None
                or not isinstance(checkpoint_sha256, str)
                or _HEX64.fullmatch(checkpoint_sha256) is None
                or checkpoint_type in seen_types
                or checkpoint_nonce in seen_nonces
                or checkpoint_sha256 in seen_sha256s
            ):
                raise CheckpointContractError("checkpoint consumption ledger drifted")
            seen_types.add(str(checkpoint_type))
            seen_nonces.add(checkpoint_nonce)
            seen_sha256s.add(checkpoint_sha256)
            records.append(record)
        if len(records) > len(CHECKPOINT_TYPES):
            raise CheckpointContractError("checkpoint consumption ledger has too many records")
        if created:
            os.fsync(descriptor)
        return descriptor, tuple(records)
    except Exception:
        with contextlib.suppress(OSError):
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
        raise


@dataclass(slots=True)
class PrivateCheckpointReader:
    schema: Mapping[str, object]
    repository_root: Path
    expected_uid: int
    binding: CheckpointBinding
    consumption_descriptor: int
    consumption_path: Path
    consumption_device: int
    consumption_inode: int
    checkpoint_root_descriptor: int | None = field(default=None, repr=False)
    checkpoint_root_path: Path | None = field(default=None, repr=False)
    checkpoint_root_device: int | None = field(default=None, repr=False)
    checkpoint_root_inode: int | None = field(default=None, repr=False)
    utc_now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC)
    consumed_types: set[str] = field(default_factory=set)
    consumed_nonces: set[str] = field(default_factory=set)
    consumed_sha256s: set[str] = field(default_factory=set)
    _closed: bool = False
    _final_evidence: CheckpointConsumptionEvidence | None = field(
        default=None, init=False, repr=False
    )
    _outcome_unknown: bool = field(default=False, init=False, repr=False)
    _ledger_unavailable: bool = field(default=False, init=False, repr=False)
    _unknown_record_start: int | None = field(default=None, init=False, repr=False)
    _unknown_record_encoded: bytes | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_schema_path(
        cls,
        schema_path: Path,
        *,
        binding: CheckpointBinding,
        consumption_path: Path,
        expected_uid: int | None = None,
        utc_now: Callable[[], dt.datetime] | None = None,
        checkpoint_root_descriptor: int | None = None,
        checkpoint_root_path: Path | None = None,
    ) -> PrivateCheckpointReader:
        repository_root = _repository_root_for_bound_schema(
            schema_path,
            relative_path=_BOUND_CHECKPOINT_SCHEMA_RELATIVE_PATH,
            context="checkpoint schema",
        )
        bound_path = repository_root / _BOUND_CHECKPOINT_SCHEMA_RELATIVE_PATH
        if schema_path.absolute() != bound_path:
            raise CheckpointContractError("checkpoint schema path is not repository-bound")
        value = _load_bound_schema(
            bound_path,
            expected_sha256=_BOUND_CHECKPOINT_SCHEMA_SHA256,
        )
        uid = os.getuid() if expected_uid is None else expected_uid
        descriptor, records = _open_consumption_ledger(
            consumption_path, expected_uid=uid, binding=binding
        )
        identity = os.fstat(descriptor)
        checkpoint_device: int | None = None
        checkpoint_inode: int | None = None
        if (checkpoint_root_descriptor is None) != (checkpoint_root_path is None):
            os.close(descriptor)
            raise CheckpointContractError("checkpoint root capability is incomplete")
        if checkpoint_root_descriptor is not None:
            checkpoint_identity = os.fstat(checkpoint_root_descriptor)
            linked = checkpoint_root_path.lstat()  # type: ignore[union-attr]
            if (
                not stat.S_ISDIR(checkpoint_identity.st_mode)
                or checkpoint_identity.st_uid != uid
                or stat.S_ISLNK(linked.st_mode)
                or (linked.st_dev, linked.st_ino)
                != (checkpoint_identity.st_dev, checkpoint_identity.st_ino)
            ):
                os.close(descriptor)
                raise CheckpointContractError("checkpoint root capability is unsafe")
            checkpoint_device = checkpoint_identity.st_dev
            checkpoint_inode = checkpoint_identity.st_ino
        return cls(
            schema=value,
            repository_root=repository_root,
            expected_uid=uid,
            binding=binding,
            consumption_descriptor=descriptor,
            consumption_path=consumption_path.absolute(),
            consumption_device=identity.st_dev,
            consumption_inode=identity.st_ino,
            checkpoint_root_descriptor=checkpoint_root_descriptor,
            checkpoint_root_path=(
                None if checkpoint_root_path is None else checkpoint_root_path.absolute()
            ),
            checkpoint_root_device=checkpoint_device,
            checkpoint_root_inode=checkpoint_inode,
            utc_now=(lambda: dt.datetime.now(dt.UTC)) if utc_now is None else utc_now,
            consumed_types={str(record["checkpoint_type"]) for record in records},
            consumed_nonces={str(record["checkpoint_nonce"]) for record in records},
            consumed_sha256s={str(record["checkpoint_sha256"]) for record in records},
        )

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
        if self._closed or self._ledger_unavailable:
            raise CheckpointContractError("checkpoint reader is closed")
        if expected_type not in CHECKPOINT_TYPES or expected_type in self.consumed_types:
            raise CheckpointContractError("checkpoint type is invalid or already consumed")
        if _HEX64.fullmatch(expected_nonce) is None:
            raise CheckpointContractError("checkpoint nonce identity is invalid")
        if expected_nonce in self.consumed_nonces:
            raise CheckpointContractError("checkpoint nonce was already consumed")
        now = self.utc_now()
        if (
            not_before.tzinfo is None
            or not_after.tzinfo is None
            or now.tzinfo is None
            or not_before > not_after
            or (not_after - not_before).total_seconds() > MAX_CHECKPOINT_WINDOW_SECONDS
            or not not_before <= now <= not_after
        ):
            raise CheckpointContractError("checkpoint time window is invalid")
        directory_descriptor = self.checkpoint_root_descriptor
        if directory_descriptor is not None:
            if (
                self.checkpoint_root_path is None
                or path.parent.absolute() != self.checkpoint_root_path
                or "/" in path.name
            ):
                raise CheckpointContractError("checkpoint escaped its held root")
            root_opened = os.fstat(directory_descriptor)
            root_linked = self.checkpoint_root_path.lstat()
            if (root_opened.st_dev, root_opened.st_ino) != (
                self.checkpoint_root_device,
                self.checkpoint_root_inode,
            ) or (root_linked.st_dev, root_linked.st_ino) != (
                self.checkpoint_root_device,
                self.checkpoint_root_inode,
            ):
                raise CheckpointContractError("checkpoint root identity changed")
            before = os.stat(path.name, dir_fd=directory_descriptor, follow_symlinks=False)
        else:
            before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != self.expected_uid
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size > MAX_CHECKPOINT_BYTES
        ):
            raise CheckpointContractError(
                "checkpoint identity, owner, mode, link, or size is unsafe"
            )
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(
            path.name if directory_descriptor is not None else path,
            flags,
            dir_fd=directory_descriptor,
        )
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise CheckpointContractError("checkpoint identity changed before open")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(
                    descriptor,
                    min(65_536, MAX_CHECKPOINT_BYTES + 1 - total),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_CHECKPOINT_BYTES:
                    raise CheckpointContractError("checkpoint exceeds its byte cap")
            encoded = b"".join(chunks)
            after = os.fstat(descriptor)
            linked = (
                os.stat(path.name, dir_fd=directory_descriptor, follow_symlinks=False)
                if directory_descriptor is not None
                else path.lstat()
            )
            if (
                len(encoded) != opened.st_size
                or (
                    after.st_dev,
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                )
                != (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_size,
                    opened.st_mtime_ns,
                    opened.st_ctime_ns,
                )
                or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                raise CheckpointContractError("checkpoint changed while held")
        finally:
            os.close(descriptor)
        document = _strict_json(encoded)
        errors = tuple(Draft202012Validator(self.schema).iter_errors(document))
        if errors:
            raise CheckpointContractError("checkpoint failed schema validation")
        if (
            document.get("checkpoint_type") != expected_type
            or document.get("checkpoint_nonce") != expected_nonce
            or document.get("run_id") != self.binding.run_id
            or document.get("decision_alias") != self.binding.decision_alias
            or document.get("marker_alias") != self.binding.marker_alias
        ):
            raise CheckpointContractError("checkpoint binding drifted")
        observed = _parse_utc(document.get("observed_at_utc"))
        if not (not_before <= observed <= now <= not_after):
            raise CheckpointContractError("checkpoint is outside its fresh time window")
        details = document.get("details")
        launch_clicked = isinstance(details, Mapping) and details.get("launch_clicked_once") is True
        if expected_type == "launch_clicked_once" and not launch_clicked:
            raise CheckpointContractError("launch checkpoint lacks the one-click attestation")
        encoded_sha256 = hashlib.sha256(encoded).hexdigest()
        if encoded_sha256 in self.consumed_sha256s:
            raise CheckpointContractError("checkpoint bytes were already consumed")
        verified = VerifiedCheckpoint(
            checkpoint_type=expected_type,
            observed_at_utc=observed,
            encoded_sha256=encoded_sha256,
            launch_clicked_once=launch_clicked,
            details=MappingProxyType(dict(_strict_details(details))),
        )
        if detail_validator is not None:
            detail_validator(verified)
        try:
            try:
                self._append_consumption(
                    checkpoint_type=expected_type,
                    checkpoint_nonce=expected_nonce,
                    checkpoint_sha256=encoded_sha256,
                )
            except _ConsumptionAppendFailure as failure:
                self.consumed_types.add(expected_type)
                self.consumed_nonces.add(expected_nonce)
                self.consumed_sha256s.add(encoded_sha256)
                self._outcome_unknown = True
                if not failure.content_complete:
                    self._ledger_unavailable = True
                    self._unknown_record_start = failure.record_start
                    self._unknown_record_encoded = failure.expected_record
                raise CheckpointConsumptionOutcomeUnknown(
                    verified,
                    content_complete=failure.content_complete,
                ) from None
            self.consumed_types.add(expected_type)
            self.consumed_nonces.add(expected_nonce)
            self.consumed_sha256s.add(encoded_sha256)
            if on_consumed is not None:
                on_consumed(verified)
        except CheckpointConsumptionOutcomeUnknown:
            raise
        except BaseException as interruption:
            # The consumption append has completed, but the caller may not have
            # received the return value.  Carry the verified checkpoint across the
            # boundary so cleanup can advance without replaying a burned identity,
            # then preserve the original interrupt after recovery.
            self.consumed_types.add(expected_type)
            self.consumed_nonces.add(expected_nonce)
            self.consumed_sha256s.add(encoded_sha256)
            self._outcome_unknown = True
            raise CheckpointConsumptionOutcomeUnknown(
                verified,
                content_complete=True,
                interruption=interruption,
            ) from None
        return verified

    def _append_consumption(
        self, *, checkpoint_type: str, checkpoint_nonce: str, checkpoint_sha256: str
    ) -> None:
        record = {
            "schema_version": "0.1.0",
            "sequence": len(self.consumed_types) + 1,
            "run_id": self.binding.run_id,
            "decision_alias": self.binding.decision_alias,
            "marker_alias": self.binding.marker_alias,
            "checkpoint_type": checkpoint_type,
            "checkpoint_nonce": checkpoint_nonce,
            "checkpoint_sha256": checkpoint_sha256,
        }
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        current_size = os.fstat(self.consumption_descriptor).st_size
        if current_size + len(encoded) > MAX_CONSUMPTION_LEDGER_BYTES:
            raise CheckpointContractError("checkpoint consumption ledger cap exceeded")
        view = memoryview(encoded)
        try:
            while view:
                written = os.write(self.consumption_descriptor, view)
                if written <= 0:
                    raise OSError
                view = view[written:]
            os.fsync(self.consumption_descriptor)
        except BaseException:
            # Preserve append-only semantics.  If a one-shot write/fsync fault left
            # an exact prefix, finish only that exact record and then re-inspect it.
            # The run remains evidence-incomplete even when the bytes are recovered.
            try:
                observed_size = os.fstat(self.consumption_descriptor).st_size
                observed_length = observed_size - current_size
                if not 0 <= observed_length <= len(encoded):
                    raise OSError
                observed = os.pread(
                    self.consumption_descriptor,
                    observed_length,
                    current_size,
                )
                if observed != encoded[:observed_length]:
                    raise OSError
                remaining = memoryview(encoded)[observed_length:]
                while remaining:
                    written = os.write(self.consumption_descriptor, remaining)
                    if written <= 0:
                        raise OSError
                    remaining = remaining[written:]
                with contextlib.suppress(OSError):
                    os.fsync(self.consumption_descriptor)
                final = os.pread(
                    self.consumption_descriptor,
                    len(encoded),
                    current_size,
                )
                content_complete = final == encoded
            except BaseException:
                content_complete = False
            raise _ConsumptionAppendFailure(
                content_complete=content_complete,
                record_start=current_size,
                expected_record=encoded,
            ) from None

    def _capture_final_evidence(self) -> CheckpointConsumptionEvidence:
        os.fsync(self.consumption_descriptor)
        identity = os.fstat(self.consumption_descriptor)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_nlink != 1
            or identity.st_uid != self.expected_uid
            or (identity.st_dev, identity.st_ino)
            != (self.consumption_device, self.consumption_inode)
            or identity.st_size > MAX_CONSUMPTION_LEDGER_BYTES
        ):
            raise CheckpointContractError("checkpoint consumption final identity drifted")
        encoded = os.pread(
            self.consumption_descriptor,
            MAX_CONSUMPTION_LEDGER_BYTES + 1,
            0,
        )
        linked = self.consumption_path.lstat()
        if len(encoded) != identity.st_size or (linked.st_dev, linked.st_ino) != (
            self.consumption_device,
            self.consumption_inode,
        ):
            raise CheckpointContractError("checkpoint consumption final path drifted")
        validated_encoded = encoded
        if self._ledger_unavailable:
            if self._unknown_record_start is None or self._unknown_record_encoded is None:
                raise CheckpointContractError("checkpoint consumption failure state drifted")
            suffix = encoded[self._unknown_record_start :]
            if not self._unknown_record_encoded.startswith(suffix):
                raise CheckpointContractError("checkpoint consumption partial record drifted")
            validated_encoded = encoded[: self._unknown_record_start]
        records = [_strict_json(line) for line in validated_encoded.splitlines()]
        expected_record_count = len(self.consumed_types) - int(self._ledger_unavailable)
        if len(records) != expected_record_count or any(
            set(record) != _CONSUMPTION_KEYS
            or record.get("sequence") != sequence
            or record.get("run_id") != self.binding.run_id
            or record.get("decision_alias") != self.binding.decision_alias
            or record.get("marker_alias") != self.binding.marker_alias
            for sequence, record in enumerate(records, start=1)
        ):
            raise CheckpointContractError("checkpoint consumption final records drifted")
        return CheckpointConsumptionEvidence(
            self.consumption_path,
            identity.st_dev,
            identity.st_ino,
            len(encoded),
            hashlib.sha256(encoded).hexdigest(),
            encoded,
            not self._outcome_unknown,
        )

    @property
    def final_evidence(self) -> CheckpointConsumptionEvidence:
        if not self._closed or self._final_evidence is None:
            raise CheckpointContractError("checkpoint consumption evidence is not final")
        return self._final_evidence

    def close(self) -> None:
        if not self._closed:
            try:
                self._final_evidence = self._capture_final_evidence()
            finally:
                with contextlib.suppress(OSError):
                    fcntl.flock(self.consumption_descriptor, fcntl.LOCK_UN)
                os.close(self.consumption_descriptor)
                self._closed = True

    def __enter__(self) -> PrivateCheckpointReader:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def launch_checkpoint_proves_provider_launch(checkpoint: VerifiedCheckpoint) -> bool:
    """A human click attestation never substitutes for read-only provider evidence."""

    if checkpoint.checkpoint_type != "launch_clicked_once":
        raise CheckpointContractError("checkpoint is not the launch-click checkpoint")
    return False


def validate_human_decision(
    document: Mapping[str, object],
    *,
    schema: Mapping[str, object],
    schema_path: Path,
    decision_alias: str | None = None,
) -> ValidatedHumanDecision:
    """Validate the private decision, including public-/32 semantics absent from JSON Schema."""

    repository_root = _repository_root_for_bound_schema(
        schema_path,
        relative_path=_BOUND_HUMAN_DECISION_SCHEMA_RELATIVE_PATH,
        context="manual-console decision schema",
    )
    bound_path = repository_root / _BOUND_HUMAN_DECISION_SCHEMA_RELATIVE_PATH
    if schema_path.absolute() != bound_path:
        raise CheckpointContractError("manual-console decision schema is not repository-bound")
    bound_schema = _load_bound_schema(
        bound_path,
        expected_sha256=_BOUND_HUMAN_DECISION_SCHEMA_SHA256,
    )
    if schema != bound_schema:
        raise CheckpointContractError("manual-console decision schema is not repository-bound")
    errors = tuple(Draft202012Validator(bound_schema).iter_errors(document))
    if errors:
        raise CheckpointContractError("manual-console decision failed schema validation")
    value = document.get("source_ipv4_cidr")
    if not isinstance(value, str):
        raise CheckpointContractError("manual-console source network is unavailable")
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError:
        raise CheckpointContractError("manual-console source network is invalid") from None
    if network.version != 4 or network.prefixlen != 32 or not network.network_address.is_global:
        raise CheckpointContractError("manual-console source network must be a public IPv4 /32")
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    decision_sha256 = hashlib.sha256(canonical).hexdigest()
    alias = decision_alias or f"l2m-decision-{decision_sha256[:12]}"
    if _DECISION_ALIAS.fullmatch(alias) is None:
        raise CheckpointContractError("manual-console decision alias is invalid")
    return ValidatedHumanDecision(
        alias,
        value,
        decision_sha256,
        repository_root,
        _HUMAN_DECISION_ISSUER,
    )
