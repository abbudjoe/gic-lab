"""Fresh one-request, fsync-backed ledger for T07 Gate L1A.

This module intentionally does not reuse or modify the hash-bound Gate L1 V2/V3
ledger implementations.  It gives the new run identity its own exclusive root,
capacity reservation, schema, one-request state machine, and terminal validation.
It contains no transport and performs no secret access.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator, FormatChecker

from .lambda_request_ledger_v3 import (
    FailureClass,
    FailureStage,
    LedgerEventType,
    RequestLedgerSnapshot,
    SanitizedFailure,
)
from .lambda_ssh_key_fingerprint import (
    API_HOST,
    LEDGER_RELATIVE_PATH,
    MAX_RESPONSE_BYTES,
    PLAN_ID,
    RUN_ID,
    RUN_ROOT_RELATIVE_PATH,
    SSH_KEYS_PATH,
    SSHKeyFingerprintError,
    SSHKeyFingerprintPlan,
    SSHKeyRunBinding,
)

LEDGER_SCHEMA_VERSION: Final = "0.1.0"


class SSHKeyRequestLedgerError(SSHKeyFingerprintError):
    """A closed, secret-safe one-request ledger failure."""


LEDGER_CREATE_FAILURE: Final = SanitizedFailure(
    FailureStage.LEDGER_IO,
    FailureClass.LEDGER_CREATE_FAILED,
    "L1A_LEDGER_CREATE_FAILED",
)
LEDGER_WRITE_FAILURE: Final = SanitizedFailure(
    FailureStage.LEDGER_IO,
    FailureClass.LEDGER_WRITE_FAILED,
    "L1A_LEDGER_WRITE_FAILED",
)


@dataclass(frozen=True, slots=True)
class SSHKeyRequestContext:
    ordinal: int = 1
    request_id: str = "ssh-key-fingerprints"
    method: str = "GET"
    path: str = SSH_KEYS_PATH
    query_key_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            self.ordinal != 1
            or self.request_id != "ssh-key-fingerprints"
            or self.method != "GET"
            or self.path != SSH_KEYS_PATH
            or self.query_key_names
        ):
            raise SSHKeyRequestLedgerError("one-request ledger context drifted")


@dataclass(slots=True)
class _State:
    phase: str = "new"
    response_status: int | None = None
    response_content_type: str | None = None
    response_bytes: int = 0
    last_elapsed_ms: int | None = None
    terminal_failure: bool = False
    stopped: bool = False

    def validate(self, event: Mapping[str, object]) -> None:
        kind = LedgerEventType(str(event["event_type"]))
        request_events = {
            LedgerEventType.REQUEST_INTENT_COMMITTED,
            LedgerEventType.REQUEST_SEND_STARTED,
            LedgerEventType.RESPONSE_HEADERS_RECEIVED,
            LedgerEventType.RESPONSE_BODY_PROGRESS,
            LedgerEventType.RESPONSE_BODY_COMPLETED,
            LedgerEventType.RESPONSE_VALIDATION_PASSED,
            LedgerEventType.REQUEST_FAILED,
            LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND,
        }
        failure_events = {
            LedgerEventType.RUN_PREFLIGHT_FAILED,
            LedgerEventType.SECRET_PRESENCE_CHECK_FAILED,
            LedgerEventType.REQUEST_FAILED,
            LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND,
            LedgerEventType.INVENTORY_VALIDATION_FAILED,
            LedgerEventType.ARCHIVE_FAILED,
        }
        failure_values = (
            event["sanitized_failure_stage"],
            event["sanitized_failure_class"],
            event["stable_error_code"],
        )
        has_failure = all(value is not None for value in failure_values)
        if has_failure != any(value is not None for value in failure_values):
            raise SSHKeyRequestLedgerError("one-request failure tuple is incomplete")
        if kind in failure_events and not has_failure:
            raise SSHKeyRequestLedgerError("one-request failure event lacks a category")
        if kind not in failure_events and kind != LedgerEventType.RUN_STOPPED and has_failure:
            raise SSHKeyRequestLedgerError("one-request success event carries a failure")
        if kind in request_events:
            if (
                event["request_ordinal"] != 1
                or event["method"] != "GET"
                or event["scheme"] != "https"
                or event["host"] != API_HOST
                or event["path"] != SSH_KEYS_PATH
                or event["query_key_names"] != []
            ):
                raise SSHKeyRequestLedgerError("one-request event identity drifted")
        elif (
            any(
                event[field] is not None
                for field in (
                    "request_ordinal",
                    "method",
                    "scheme",
                    "host",
                    "path",
                    "http_status",
                    "content_type",
                    "elapsed_ms",
                )
            )
            or event["query_key_names"] != []
            or event["bytes_received_so_far"] != 0
        ):
            raise SSHKeyRequestLedgerError("non-request event contains request data")
        if self.stopped:
            raise SSHKeyRequestLedgerError("one-request ledger is already terminal")
        transitions = {
            LedgerEventType.RUN_PREFLIGHT_STARTED: ("new", "preflight-started"),
            LedgerEventType.SECRET_PRESENCE_CHECK_PASSED: (
                "preflight-started",
                "secret-passed",
            ),
            LedgerEventType.SECRET_PRESENCE_CHECK_FAILED: (
                "preflight-started",
                "secret-failed",
            ),
            LedgerEventType.RUN_PREFLIGHT_PASSED: ("secret-passed", "preflight-passed"),
            LedgerEventType.RUN_PREFLIGHT_FAILED: (
                ("preflight-started", "secret-failed"),
                "failed",
            ),
            LedgerEventType.REQUEST_INTENT_COMMITTED: ("preflight-passed", "intent"),
            LedgerEventType.REQUEST_SEND_STARTED: ("intent", "send-started"),
            LedgerEventType.RESPONSE_HEADERS_RECEIVED: ("send-started", "headers"),
            LedgerEventType.RESPONSE_BODY_PROGRESS: (("headers", "progress"), "progress"),
            LedgerEventType.RESPONSE_BODY_COMPLETED: (
                ("headers", "progress"),
                "body-complete",
            ),
            LedgerEventType.RESPONSE_VALIDATION_PASSED: (
                "body-complete",
                "response-valid",
            ),
            LedgerEventType.REQUEST_FAILED: (
                ("intent", "send-started", "headers", "progress", "body-complete"),
                "failed",
            ),
            LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND: (
                ("send-started", "headers", "progress"),
                "failed",
            ),
            LedgerEventType.INVENTORY_VALIDATION_STARTED: (
                "response-valid",
                "validation-started",
            ),
            LedgerEventType.INVENTORY_VALIDATION_PASSED: (
                "validation-started",
                "validation-passed",
            ),
            LedgerEventType.INVENTORY_VALIDATION_FAILED: (
                "validation-started",
                "failed",
            ),
            LedgerEventType.ARCHIVE_STARTED: ("validation-passed", "archive-started"),
            LedgerEventType.ARCHIVE_PASSED: ("archive-started", "archive-passed"),
            LedgerEventType.ARCHIVE_FAILED: ("archive-started", "failed"),
        }
        if kind == LedgerEventType.RUN_STOPPED:
            if self.phase not in {"archive-passed", "failed"}:
                raise SSHKeyRequestLedgerError("run stopped before a terminal state")
            if (self.phase == "failed") != has_failure:
                raise SSHKeyRequestLedgerError("run-stopped failure state drifted")
            return
        transition = transitions.get(kind)
        if transition is None:
            raise SSHKeyRequestLedgerError("one-request event type is unsupported")
        allowed, _ = transition
        allowed_states = (allowed,) if isinstance(allowed, str) else allowed
        if self.phase not in allowed_states:
            raise SSHKeyRequestLedgerError("one-request event order is invalid")
        if kind in {
            LedgerEventType.REQUEST_INTENT_COMMITTED,
            LedgerEventType.REQUEST_SEND_STARTED,
        } and any(
            event[field] is not None for field in ("http_status", "content_type", "elapsed_ms")
        ):
            raise SSHKeyRequestLedgerError("pre-response event carries response data")
        if (
            kind == LedgerEventType.RESPONSE_HEADERS_RECEIVED
            and event["bytes_received_so_far"] != 0
        ):
            raise SSHKeyRequestLedgerError("response headers carry body bytes")
        if kind in {
            LedgerEventType.RESPONSE_BODY_PROGRESS,
            LedgerEventType.RESPONSE_BODY_COMPLETED,
            LedgerEventType.RESPONSE_VALIDATION_PASSED,
        }:
            received = event["bytes_received_so_far"]
            elapsed = event["elapsed_ms"]
            if (
                type(received) is not int
                or received < self.response_bytes
                or type(elapsed) is not int
                or (self.last_elapsed_ms is not None and elapsed < self.last_elapsed_ms)
                or event["http_status"] != self.response_status
                or event["content_type"] != self.response_content_type
            ):
                raise SSHKeyRequestLedgerError("response progress regressed")
        if kind in {
            LedgerEventType.RESPONSE_BODY_COMPLETED,
            LedgerEventType.RESPONSE_VALIDATION_PASSED,
        } and (event["http_status"] != 200 or event["content_type"] != "application/json"):
            raise SSHKeyRequestLedgerError("validated response is not HTTP 200 JSON")
        if kind == LedgerEventType.RESPONSE_VALIDATION_PASSED and (
            event["bytes_received_so_far"] != self.response_bytes
        ):
            raise SSHKeyRequestLedgerError("response validation byte count drifted")

    def apply(self, event: Mapping[str, object]) -> None:
        kind = LedgerEventType(str(event["event_type"]))
        if kind == LedgerEventType.RUN_STOPPED:
            self.stopped = True
            return
        next_states: dict[str, str] = {
            LedgerEventType.RUN_PREFLIGHT_STARTED: "preflight-started",
            LedgerEventType.SECRET_PRESENCE_CHECK_PASSED: "secret-passed",
            LedgerEventType.SECRET_PRESENCE_CHECK_FAILED: "secret-failed",
            LedgerEventType.RUN_PREFLIGHT_PASSED: "preflight-passed",
            LedgerEventType.RUN_PREFLIGHT_FAILED: "failed",
            LedgerEventType.REQUEST_INTENT_COMMITTED: "intent",
            LedgerEventType.REQUEST_SEND_STARTED: "send-started",
            LedgerEventType.RESPONSE_HEADERS_RECEIVED: "headers",
            LedgerEventType.RESPONSE_BODY_PROGRESS: "progress",
            LedgerEventType.RESPONSE_BODY_COMPLETED: "body-complete",
            LedgerEventType.RESPONSE_VALIDATION_PASSED: "response-valid",
            LedgerEventType.REQUEST_FAILED: "failed",
            LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND: "failed",
            LedgerEventType.INVENTORY_VALIDATION_STARTED: "validation-started",
            LedgerEventType.INVENTORY_VALIDATION_PASSED: "validation-passed",
            LedgerEventType.INVENTORY_VALIDATION_FAILED: "failed",
            LedgerEventType.ARCHIVE_STARTED: "archive-started",
            LedgerEventType.ARCHIVE_PASSED: "archive-passed",
            LedgerEventType.ARCHIVE_FAILED: "failed",
        }
        self.phase = next_states[kind]
        if kind == LedgerEventType.RESPONSE_HEADERS_RECEIVED:
            self.response_status = int(str(event["http_status"]))
            self.response_content_type = str(event["content_type"])
            self.last_elapsed_ms = int(str(event["elapsed_ms"]))
        elif kind in {
            LedgerEventType.RESPONSE_BODY_PROGRESS,
            LedgerEventType.RESPONSE_BODY_COMPLETED,
        }:
            self.response_bytes = int(str(event["bytes_received_so_far"]))
            self.last_elapsed_ms = int(str(event["elapsed_ms"]))
        if self.phase == "failed":
            self.terminal_failure = True


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _create_directory_chain(root: Path, relative: Path) -> tuple[Path, int]:
    if relative.is_absolute() or ".." in relative.parts:
        raise SSHKeyRequestLedgerError("ledger directory escaped the repository")
    descriptor = os.open(root, _directory_flags())
    current = root
    try:
        for component in relative.parts:
            created = False
            try:
                os.mkdir(component, mode=0o700, dir_fd=descriptor)
                created = True
            except FileExistsError:
                pass
            if created:
                os.fsync(descriptor)
            child = os.open(component, _directory_flags(), dir_fd=descriptor)
            observed = os.fstat(child)
            if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != os.getuid():
                os.close(child)
                raise OSError
            os.close(descriptor)
            descriptor = child
            current /= component
        return current, descriptor
    except Exception:
        with suppress(OSError):
            os.close(descriptor)
        raise SSHKeyRequestLedgerError("ledger directory creation failed") from None


def _validator(repository_root: Path, plan: SSHKeyFingerprintPlan) -> Draft202012Validator:
    path = repository_root / plan.ledger_schema_relative_path
    try:
        encoded = path.read_bytes()
        if hashlib.sha256(encoded).hexdigest() != plan.ledger_schema_sha256:
            raise ValueError
        schema = json.loads(encoded)
        Draft202012Validator.check_schema(schema)
    except Exception:
        raise SSHKeyRequestLedgerError("ledger schema binding failed") from None
    return Draft202012Validator(schema, format_checker=FormatChecker())


@dataclass(slots=True)
class FsyncSSHKeyRequestLedger:
    path: Path
    descriptor: int
    plan: SSHKeyFingerprintPlan
    run_binding: SSHKeyRunBinding
    validator: Draft202012Validator
    monotonic_ns: Callable[[], int]
    utc_now: Callable[[], datetime]
    state: _State = field(default_factory=_State)
    next_sequence: int = 1
    bytes_written: int = 0
    events_written: int = 0
    request_events: int = 0
    reservation_path: Path | None = None
    reservation_descriptor: int = -1
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
    ) -> FsyncSSHKeyRequestLedger:
        root = repository_root.resolve(strict=True)
        if (
            root != repository_root.absolute()
            or plan.run_id != RUN_ID
            or run_binding.run_id != RUN_ID
            or plan.plan_id != PLAN_ID
            or run_binding.plan_id != PLAN_ID
            or plan.run_root_relative_path != RUN_ROOT_RELATIVE_PATH
            or plan.ledger_relative_path != LEDGER_RELATIVE_PATH
        ):
            raise SSHKeyRequestLedgerError("ledger creation binding drifted")
        run_relative = Path(RUN_ROOT_RELATIVE_PATH)
        parent_descriptor = -1
        run_descriptor = -1
        descriptor = -1
        try:
            _, parent_descriptor = _create_directory_chain(root, run_relative.parent)
            os.mkdir(run_relative.name, mode=0o700, dir_fd=parent_descriptor)
            os.fsync(parent_descriptor)
            run_descriptor = os.open(
                run_relative.name, _directory_flags(), dir_fd=parent_descriptor
            )
            run_status = os.fstat(run_descriptor)
            if not stat.S_ISDIR(run_status.st_mode) or run_status.st_uid != os.getuid():
                raise OSError
            validator = _validator(root, plan)
            descriptor = os.open(
                Path(LEDGER_RELATIVE_PATH).name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=run_descriptor,
            )
            os.fsync(run_descriptor)
        except Exception:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            raise SSHKeyRequestLedgerError("fresh ledger creation failed") from None
        finally:
            if run_descriptor >= 0:
                with suppress(OSError):
                    os.close(run_descriptor)
            if parent_descriptor >= 0:
                with suppress(OSError):
                    os.close(parent_descriptor)
        return cls(
            path=root / LEDGER_RELATIVE_PATH,
            descriptor=descriptor,
            plan=plan,
            run_binding=run_binding,
            validator=validator,
            monotonic_ns=monotonic_ns,
            utc_now=utc_now,
        )

    def reserve_capacity(self) -> None:
        if self.closed or self.tainted or self.reservation_path is not None:
            raise SSHKeyRequestLedgerError("ledger capacity state is invalid")
        if (
            self.plan.limits.max_events * self.plan.limits.max_event_bytes
            > self.plan.limits.max_bytes
        ):
            raise SSHKeyRequestLedgerError("ledger event reservation exceeds its byte cap")
        observed = os.statvfs(self.path.parent)
        if observed.f_bavail * observed.f_frsize < self.plan.local_prewrite_floor_bytes:
            raise SSHKeyRequestLedgerError("ledger free-space floor failed")
        path = self.path.parent / ".request-ledger.capacity"
        descriptor = -1
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            remaining = self.plan.limits.max_bytes
            block = bytes(min(remaining, 65_536))
            while remaining:
                written = os.write(descriptor, block[:remaining])
                if written < 1:
                    raise OSError
                remaining -= written
            os.fsync(descriptor)
            if os.fstat(descriptor).st_size != self.plan.limits.max_bytes:
                raise OSError
            parent = os.open(self.path.parent, _directory_flags())
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except OSError:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            raise SSHKeyRequestLedgerError("ledger capacity reservation failed") from None
        self.reservation_path = path
        self.reservation_descriptor = descriptor

    def append(
        self,
        event_type: LedgerEventType,
        *,
        request: SSHKeyRequestContext | None = None,
        bytes_received: int = 0,
        http_status: int | None = None,
        content_type: str | None = None,
        elapsed_ms: int | None = None,
        failure: SanitizedFailure | None = None,
    ) -> None:
        if self.closed or self.tainted:
            raise SSHKeyRequestLedgerError("ledger is unavailable")
        if request is not None and self.reservation_path is None:
            raise SSHKeyRequestLedgerError("request event lacks reserved ledger capacity")
        if bytes_received < 0 or bytes_received > MAX_RESPONSE_BYTES:
            raise SSHKeyRequestLedgerError("ledger response-byte count is invalid")
        failure_values = (
            failure.stage.value if failure is not None else None,
            failure.classification.value if failure is not None else None,
            failure.stable_error_code if failure is not None else None,
        )
        event: dict[str, object] = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "event_type": event_type.value,
            "run_id": RUN_ID,
            "plan_id": PLAN_ID,
            "authorization_reference": self.run_binding.authorization_reference,
            "event_sequence": self.next_sequence,
            "request_ordinal": request.ordinal if request is not None else None,
            "method": request.method if request is not None else None,
            "scheme": "https" if request is not None else None,
            "host": API_HOST if request is not None else None,
            "path": request.path if request is not None else None,
            "query_key_names": list(request.query_key_names) if request is not None else [],
            "transport_kind": self.plan.transport_kind,
            "monotonic_timestamp_ns": self.monotonic_ns(),
            "wall_timestamp_utc": self.utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "bytes_received_so_far": bytes_received,
            "http_status": http_status,
            "content_type": content_type,
            "elapsed_ms": elapsed_ms,
            "sanitized_failure_stage": failure_values[0],
            "sanitized_failure_class": failure_values[1],
            "stable_error_code": failure_values[2],
            "retry_count": 0,
            "pagination_request": False,
        }
        if list(self.validator.iter_errors(event)):
            raise SSHKeyRequestLedgerError("ledger event violates its schema")
        self.state.validate(event)
        encoded = (
            json.dumps(event, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
            + b"\n"
        )
        next_request_count = self.request_events + (1 if request is not None else 0)
        if (
            len(encoded) > self.plan.limits.max_event_bytes
            or self.events_written + 1 > self.plan.limits.max_events
            or self.bytes_written + len(encoded) > self.plan.limits.max_bytes
            or next_request_count > self.plan.limits.max_events_per_request
        ):
            raise SSHKeyRequestLedgerError("ledger cap would be exceeded")
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
            raise SSHKeyRequestLedgerError("ledger append or fsync failed") from None
        self.state.apply(event)
        self.next_sequence += 1
        self.events_written += 1
        self.bytes_written += len(encoded)
        self.request_events = next_request_count

    def seal(self, *, require_success: bool) -> RequestLedgerSnapshot:
        if self.closed or self.tainted:
            raise SSHKeyRequestLedgerError("ledger cannot be sealed")
        try:
            os.fsync(self.descriptor)
            os.fchmod(self.descriptor, 0o400)
            os.close(self.descriptor)
        except OSError:
            self.closed = True
            raise SSHKeyRequestLedgerError("ledger close failed") from None
        self.closed = True
        self._release_reservation()
        encoded = self.path.read_bytes()
        events = validate_ssh_key_request_ledger(
            encoded,
            plan=self.plan,
            run_binding=self.run_binding,
            validator=self.validator,
            require_success=require_success,
        )
        return RequestLedgerSnapshot(
            self.path,
            hashlib.sha256(encoded).hexdigest(),
            len(encoded),
            len(events),
        )

    def _release_reservation(self) -> None:
        if self.reservation_descriptor >= 0:
            os.close(self.reservation_descriptor)
            self.reservation_descriptor = -1
        if self.reservation_path is not None:
            self.reservation_path.unlink()
            parent = os.open(self.path.parent, _directory_flags())
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
            self.reservation_path = None

    def close_preserving_incomplete(self) -> None:
        if self.closed:
            return
        with suppress(OSError):
            os.fsync(self.descriptor)
        with suppress(OSError):
            os.fchmod(self.descriptor, 0o400)
        with suppress(OSError):
            os.close(self.descriptor)
        self.closed = True
        with suppress(OSError):
            self._release_reservation()


def validate_ssh_key_request_ledger(
    encoded: bytes,
    *,
    plan: SSHKeyFingerprintPlan,
    run_binding: SSHKeyRunBinding,
    validator: Draft202012Validator,
    require_success: bool,
) -> tuple[dict[str, object], ...]:
    if not encoded.endswith(b"\n") or len(encoded) > plan.limits.max_bytes:
        raise SSHKeyRequestLedgerError("ledger byte envelope is invalid")
    state = _State()
    events: list[dict[str, object]] = []
    request_events = 0
    last_monotonic = -1
    for sequence, line in enumerate(encoded.splitlines(), start=1):
        if not line or len(line) + 1 > plan.limits.max_event_bytes:
            raise SSHKeyRequestLedgerError("ledger line is invalid")
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SSHKeyRequestLedgerError("ledger line is not JSON") from None
        if not isinstance(event, dict) or any(not isinstance(key, str) for key in event):
            raise SSHKeyRequestLedgerError("ledger event is not an object")
        monotonic = event.get("monotonic_timestamp_ns")
        if (
            event.get("event_sequence") != sequence
            or event.get("run_id") != RUN_ID
            or event.get("plan_id") != PLAN_ID
            or event.get("authorization_reference") != run_binding.authorization_reference
            or type(monotonic) is not int
            or monotonic < last_monotonic
            or list(validator.iter_errors(event))
        ):
            raise SSHKeyRequestLedgerError("ledger event identity drifted")
        last_monotonic = monotonic
        if event.get("request_ordinal") is not None:
            request_events += 1
            if request_events > plan.limits.max_events_per_request:
                raise SSHKeyRequestLedgerError("ledger request-event cap exceeded")
        state.validate(event)
        state.apply(event)
        events.append(event)
        if len(events) > plan.limits.max_events:
            raise SSHKeyRequestLedgerError("ledger event cap exceeded")
    if require_success and not (state.phase == "archive-passed" and state.stopped):
        raise SSHKeyRequestLedgerError("ledger lacks a successful terminal state")
    return tuple(events)
