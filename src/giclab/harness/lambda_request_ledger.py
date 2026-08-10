"""Durable, secret-free request observability for T07 Gate L1 V2.

Each JSONL event is schema checked, appended to an exclusively created run ledger,
flushed, and fsynced before the in-memory state machine advances.  The ledger never
accepts arbitrary exception text, headers, cookies, query values, or environment
content.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final
from urllib.parse import parse_qsl, urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from .lambda_cloud import (
    MAX_INVENTORY_RESPONSE_BYTES,
    InventoryRequest,
    LambdaCloudContractError,
)
from .lambda_inventory_plan import (
    FAILURE_CLASSES,
    FAILURE_STAGES,
    LEDGER_EVENT_TYPES,
    InventoryRunBindingV2,
    ReadOnlyInventoryPlanV2,
)

LEDGER_SCHEMA_VERSION: Final = "0.1.0"
APPROVED_LEDGER_HOST: Final = "cloud.lambda.ai"
APPROVED_LEDGER_SCHEME: Final = "https"
PROGRESS_CHUNK_BYTES: Final = 65_536


class LedgerEventType(StrEnum):
    RUN_PREFLIGHT_STARTED = "run_preflight_started"
    RUN_PREFLIGHT_PASSED = "run_preflight_passed"
    RUN_PREFLIGHT_FAILED = "run_preflight_failed"
    SECRET_PRESENCE_CHECK_PASSED = "secret_presence_check_passed"
    SECRET_PRESENCE_CHECK_FAILED = "secret_presence_check_failed"
    REQUEST_INTENT_COMMITTED = "request_intent_committed"
    REQUEST_SEND_STARTED = "request_send_started"
    RESPONSE_HEADERS_RECEIVED = "response_headers_received"
    RESPONSE_BODY_PROGRESS = "response_body_progress"
    RESPONSE_BODY_COMPLETED = "response_body_completed"
    RESPONSE_VALIDATION_PASSED = "response_validation_passed"
    REQUEST_FAILED = "request_failed"
    REQUEST_OUTCOME_UNKNOWN_AFTER_SEND = "request_outcome_unknown_after_send"
    RUN_STOPPED = "run_stopped"
    INVENTORY_VALIDATION_STARTED = "inventory_validation_started"
    INVENTORY_VALIDATION_PASSED = "inventory_validation_passed"
    INVENTORY_VALIDATION_FAILED = "inventory_validation_failed"
    ARCHIVE_STARTED = "archive_started"
    ARCHIVE_PASSED = "archive_passed"
    ARCHIVE_FAILED = "archive_failed"


class FailureStage(StrEnum):
    SECRET_SOURCE = "secret_source"
    DNS = "dns"
    TCP_CONNECT = "tcp_connect"
    TLS_HANDSHAKE = "tls_handshake"
    REQUEST_WRITE = "request_write"
    RESPONSE_HEADERS = "response_headers"
    RESPONSE_BODY = "response_body"
    HTTP_STATUS = "http_status"
    REDIRECT = "redirect"
    RATE_LIMIT = "rate_limit"
    CONTENT_TYPE = "content_type"
    RESPONSE_SIZE = "response_size"
    JSON_DECODE = "json_decode"
    SCHEMA_VALIDATION = "schema_validation"
    PAGINATION = "pagination"
    LEDGER_IO = "ledger_io"
    ARCHIVE_IO = "archive_io"
    UNKNOWN = "unknown"


class FailureClass(StrEnum):
    SECRET_MISSING = "secret_missing"
    SECRET_MALFORMED = "secret_malformed"
    DNS_FAILURE = "dns_failure"
    TCP_CONNECT_FAILURE = "tcp_connect_failure"
    TLS_FAILURE = "tls_failure"
    REQUEST_WRITE_FAILURE = "request_write_failure"
    RESPONSE_HEADERS_FAILURE = "response_headers_failure"
    RESPONSE_BODY_FAILURE = "response_body_failure"
    HTTP_UNAUTHORIZED = "http_unauthorized"
    HTTP_FORBIDDEN = "http_forbidden"
    HTTP_RATE_LIMITED = "http_rate_limited"
    HTTP_REDIRECT = "http_redirect"
    HTTP_UNEXPECTED_STATUS = "http_unexpected_status"
    UNEXPECTED_CONTENT_TYPE = "unexpected_content_type"
    RESPONSE_TOO_LARGE = "response_too_large"
    MALFORMED_JSON = "malformed_json"
    SCHEMA_DRIFT = "schema_drift"
    PAGINATION_PRESENT = "pagination_present"
    LEDGER_CREATE_FAILED = "ledger_create_failed"
    LEDGER_WRITE_FAILED = "ledger_write_failed"
    ARCHIVE_FAILED = "archive_failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    INTERNAL_FAILURE = "internal_failure"


@dataclass(frozen=True, slots=True)
class SanitizedFailure:
    stage: FailureStage
    classification: FailureClass
    stable_error_code: str

    def __post_init__(self) -> None:
        if self.stage.value not in FAILURE_STAGES:
            raise ValueError("failure stage is not allowlisted")
        if self.classification.value not in FAILURE_CLASSES:
            raise ValueError("failure class is not allowlisted")
        if (
            not 3 <= len(self.stable_error_code) <= 64
            or not self.stable_error_code[0].isalpha()
            or not all(
                character.isupper() or character.isdigit() or character == "_"
                for character in self.stable_error_code
            )
        ):
            raise ValueError("stable error code is not canonical")


class InventoryObservedFailure(LambdaCloudContractError):
    """A provider/transport failure containing only closed, secret-safe categories."""

    def __init__(
        self,
        failure: SanitizedFailure,
        *,
        http_status: int | None = None,
        content_type: str | None = None,
        bytes_received: int = 0,
        elapsed_ms: int | None = None,
    ) -> None:
        super().__init__(failure.stable_error_code)
        self.failure = failure
        self.http_status = http_status
        self.content_type = content_type
        self.bytes_received = bytes_received
        self.elapsed_ms = elapsed_ms


class RequestLedgerError(LambdaCloudContractError):
    """A closed ledger error; no OS or schema exception text is retained."""

    def __init__(self, failure: SanitizedFailure) -> None:
        super().__init__(failure.stable_error_code)
        self.failure = failure


def _event_integer(value: object) -> int:
    if type(value) is not int:
        raise RequestLedgerError(LEDGER_WRITE_FAILURE)
    return value


LEDGER_CREATE_FAILURE: Final = SanitizedFailure(
    FailureStage.LEDGER_IO,
    FailureClass.LEDGER_CREATE_FAILED,
    "L1_LEDGER_CREATE_FAILED",
)
LEDGER_WRITE_FAILURE: Final = SanitizedFailure(
    FailureStage.LEDGER_IO,
    FailureClass.LEDGER_WRITE_FAILED,
    "L1_LEDGER_WRITE_FAILED",
)
OUTCOME_UNKNOWN_FAILURE: Final = SanitizedFailure(
    FailureStage.UNKNOWN,
    FailureClass.OUTCOME_UNKNOWN,
    "L1_REQUEST_OUTCOME_UNKNOWN",
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    ordinal: int
    request_id: str
    method: str
    path: str
    query_key_names: tuple[str, ...]

    @classmethod
    def from_request(cls, ordinal: int, request: InventoryRequest) -> RequestContext:
        split = urlsplit(request.path)
        query_pairs = parse_qsl(split.query, keep_blank_values=True, strict_parsing=True)
        query_names = tuple(name for name, _ in query_pairs)
        if (
            not 1 <= ordinal <= 8
            or split.scheme
            or split.netloc
            or split.fragment
            or request.method.value != "GET"
            or len(query_names) != len(set(query_names))
            or any(name != "resource_type" for name in query_names)
        ):
            raise LambdaCloudContractError("request context is outside the V2 ledger allowlist")
        return cls(
            ordinal=ordinal,
            request_id=request.request_id,
            method=request.method.value,
            path=split.path,
            query_key_names=query_names,
        )


@dataclass(frozen=True, slots=True)
class RequestLedgerSnapshot:
    path: Path
    sha256: str
    bytes: int
    events: int


@dataclass(slots=True)
class _LedgerStateMachine:
    preflight_started: bool = False
    secret_passed: bool = False
    secret_failed: bool = False
    preflight_passed: bool = False
    preflight_failed: bool = False
    completed_requests: int = 0
    current_ordinal: int | None = None
    request_phase: str | None = None
    last_response_bytes: int = 0
    response_status: int | None = None
    response_content_type: str | None = None
    last_elapsed_ms: int | None = None
    terminal_failure: bool = False
    validation_phase: str | None = None
    archive_phase: str | None = None
    stopped: bool = False

    def validate(self, event: Mapping[str, object]) -> None:
        event_type = str(event["event_type"])
        ordinal = event["request_ordinal"]
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
        required_failure_events = {
            LedgerEventType.RUN_PREFLIGHT_FAILED,
            LedgerEventType.SECRET_PRESENCE_CHECK_FAILED,
            LedgerEventType.REQUEST_FAILED,
            LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND,
            LedgerEventType.INVENTORY_VALIDATION_FAILED,
            LedgerEventType.ARCHIVE_FAILED,
        }
        failure_bundle = (
            event["sanitized_failure_stage"],
            event["sanitized_failure_class"],
            event["stable_error_code"],
        )
        has_failure = all(value is not None for value in failure_bundle)
        if has_failure != any(value is not None for value in failure_bundle):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if event_type in required_failure_events and not has_failure:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if (
            event_type not in required_failure_events
            and event_type != LedgerEventType.RUN_STOPPED
            and has_failure
        ):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)

        if event_type in request_events:
            if (
                type(ordinal) is not int
                or event["method"] != "GET"
                or event["scheme"] != APPROVED_LEDGER_SCHEME
                or event["host"] != APPROVED_LEDGER_HOST
                or not isinstance(event["path"], str)
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        elif (
            ordinal is not None
            or event["method"] is not None
            or event["scheme"] is not None
            or event["host"] is not None
            or event["path"] is not None
            or event["query_key_names"] != []
            or event["bytes_received_so_far"] != 0
            or event["http_status"] is not None
            or event["content_type"] is not None
            or event["elapsed_ms"] is not None
        ):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)

        if event_type in {
            LedgerEventType.REQUEST_INTENT_COMMITTED,
            LedgerEventType.REQUEST_SEND_STARTED,
        } and (
            event["bytes_received_so_far"] != 0
            or event["http_status"] is not None
            or event["content_type"] is not None
            or event["elapsed_ms"] is not None
        ):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if (
            event_type == LedgerEventType.RESPONSE_HEADERS_RECEIVED
            and event["bytes_received_so_far"] != 0
        ):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if self.stopped:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if event_type == LedgerEventType.RUN_PREFLIGHT_STARTED:
            if self.preflight_started:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if not self.preflight_started:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if event_type == LedgerEventType.SECRET_PRESENCE_CHECK_PASSED:
            if self.secret_passed or self.secret_failed or self.preflight_passed:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.SECRET_PRESENCE_CHECK_FAILED:
            if self.secret_passed or self.secret_failed or self.preflight_passed:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.RUN_PREFLIGHT_PASSED:
            if not self.secret_passed or self.preflight_passed or self.preflight_failed:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.RUN_PREFLIGHT_FAILED:
            if self.preflight_passed or self.preflight_failed or self.current_ordinal is not None:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.REQUEST_INTENT_COMMITTED:
            if (
                not self.preflight_passed
                or self.terminal_failure
                or self.current_ordinal is not None
                or ordinal != self.completed_requests + 1
                or self.validation_phase is not None
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.REQUEST_SEND_STARTED:
            if ordinal != self.current_ordinal or self.request_phase != "intent":
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.RESPONSE_HEADERS_RECEIVED:
            if ordinal != self.current_ordinal or self.request_phase != "send":
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.RESPONSE_BODY_PROGRESS:
            if (
                ordinal != self.current_ordinal
                or self.request_phase not in {"headers", "progress"}
                or _event_integer(event["bytes_received_so_far"]) <= self.last_response_bytes
                or event["http_status"] != self.response_status
                or event["content_type"] != self.response_content_type
                or (
                    self.last_elapsed_ms is not None
                    and _event_integer(event["elapsed_ms"]) < self.last_elapsed_ms
                )
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.RESPONSE_BODY_COMPLETED:
            if (
                ordinal != self.current_ordinal
                or self.request_phase not in {"headers", "progress"}
                or _event_integer(event["bytes_received_so_far"]) < self.last_response_bytes
                or event["http_status"] != 200
                or event["content_type"] != "application/json"
                or event["http_status"] != self.response_status
                or event["content_type"] != self.response_content_type
                or (
                    self.last_elapsed_ms is not None
                    and _event_integer(event["elapsed_ms"]) < self.last_elapsed_ms
                )
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.RESPONSE_VALIDATION_PASSED:
            if (
                ordinal != self.current_ordinal
                or self.request_phase != "body_completed"
                or _event_integer(event["bytes_received_so_far"]) != self.last_response_bytes
                or event["http_status"] != 200
                or event["content_type"] != "application/json"
                or event["http_status"] != self.response_status
                or event["content_type"] != self.response_content_type
                or (
                    self.last_elapsed_ms is not None
                    and _event_integer(event["elapsed_ms"]) < self.last_elapsed_ms
                )
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.REQUEST_FAILED:
            if ordinal != self.current_ordinal or self.request_phase not in {
                "intent",
                "send",
                "headers",
                "progress",
                "body_completed",
            }:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            if _event_integer(event["bytes_received_so_far"]) < self.last_response_bytes:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            if self.response_status is not None and (
                event["http_status"] != self.response_status
                or event["content_type"] != self.response_content_type
                or event["elapsed_ms"] is None
                or (
                    self.last_elapsed_ms is not None
                    and _event_integer(event["elapsed_ms"]) < self.last_elapsed_ms
                )
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            if self.response_status is None and (
                event["http_status"] is not None or event["content_type"] is not None
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND:
            if ordinal != self.current_ordinal or self.request_phase not in {
                "send",
                "headers",
                "progress",
            }:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            if _event_integer(event["bytes_received_so_far"]) < self.last_response_bytes:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            if self.response_status is not None and (
                event["http_status"] != self.response_status
                or event["content_type"] != self.response_content_type
                or event["elapsed_ms"] is None
                or (
                    self.last_elapsed_ms is not None
                    and _event_integer(event["elapsed_ms"]) < self.last_elapsed_ms
                )
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            if self.response_status is None and (
                event["http_status"] is not None or event["content_type"] is not None
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.INVENTORY_VALIDATION_STARTED:
            if (
                self.completed_requests != 8
                or self.current_ordinal is not None
                or self.validation_phase is not None
                or self.terminal_failure
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type in {
            LedgerEventType.INVENTORY_VALIDATION_PASSED,
            LedgerEventType.INVENTORY_VALIDATION_FAILED,
        }:
            if self.validation_phase != "started":
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.ARCHIVE_STARTED:
            if self.validation_phase != "passed" or self.archive_phase is not None:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type in {LedgerEventType.ARCHIVE_PASSED, LedgerEventType.ARCHIVE_FAILED}:
            if self.archive_phase != "started":
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        if event_type == LedgerEventType.RUN_STOPPED:
            successful = self.archive_phase == "passed"
            failed = (
                self.preflight_failed
                or self.terminal_failure
                or self.validation_phase == "failed"
                or self.archive_phase == "failed"
            )
            direct_presend_stop = (
                self.preflight_passed
                and self.current_ordinal is None
                and self.completed_requests < 8
                and event["sanitized_failure_stage"] is not None
            )
            if successful and event["sanitized_failure_stage"] is not None:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            if failed and event["sanitized_failure_stage"] is None:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            if not (successful or failed or direct_presend_stop):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            return
        raise RequestLedgerError(LEDGER_WRITE_FAILURE)

    def apply(self, event: Mapping[str, object]) -> None:
        event_type = str(event["event_type"])
        if event_type == LedgerEventType.RUN_PREFLIGHT_STARTED:
            self.preflight_started = True
        elif event_type == LedgerEventType.SECRET_PRESENCE_CHECK_PASSED:
            self.secret_passed = True
        elif event_type == LedgerEventType.SECRET_PRESENCE_CHECK_FAILED:
            self.secret_failed = True
        elif event_type == LedgerEventType.RUN_PREFLIGHT_PASSED:
            self.preflight_passed = True
        elif event_type == LedgerEventType.RUN_PREFLIGHT_FAILED:
            self.preflight_failed = True
            self.terminal_failure = True
        elif event_type == LedgerEventType.REQUEST_INTENT_COMMITTED:
            self.current_ordinal = _event_integer(event["request_ordinal"])
            self.request_phase = "intent"
            self.last_response_bytes = 0
            self.response_status = None
            self.response_content_type = None
            self.last_elapsed_ms = None
        elif event_type == LedgerEventType.REQUEST_SEND_STARTED:
            self.request_phase = "send"
        elif event_type == LedgerEventType.RESPONSE_HEADERS_RECEIVED:
            self.request_phase = "headers"
            self.response_status = _event_integer(event["http_status"])
            self.response_content_type = str(event["content_type"])
            self.last_elapsed_ms = _event_integer(event["elapsed_ms"])
        elif event_type == LedgerEventType.RESPONSE_BODY_PROGRESS:
            self.request_phase = "progress"
            self.last_response_bytes = _event_integer(event["bytes_received_so_far"])
            self.last_elapsed_ms = _event_integer(event["elapsed_ms"])
        elif event_type == LedgerEventType.RESPONSE_BODY_COMPLETED:
            self.request_phase = "body_completed"
            self.last_response_bytes = _event_integer(event["bytes_received_so_far"])
            self.last_elapsed_ms = _event_integer(event["elapsed_ms"])
        elif event_type == LedgerEventType.RESPONSE_VALIDATION_PASSED:
            self.completed_requests += 1
            self.current_ordinal = None
            self.request_phase = None
            self.last_response_bytes = 0
            self.response_status = None
            self.response_content_type = None
            self.last_elapsed_ms = None
        elif event_type in {
            LedgerEventType.REQUEST_FAILED,
            LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND,
        }:
            self.current_ordinal = None
            self.request_phase = None
            self.terminal_failure = True
            self.response_status = None
            self.response_content_type = None
            self.last_elapsed_ms = None
        elif event_type == LedgerEventType.INVENTORY_VALIDATION_STARTED:
            self.validation_phase = "started"
        elif event_type == LedgerEventType.INVENTORY_VALIDATION_PASSED:
            self.validation_phase = "passed"
        elif event_type == LedgerEventType.INVENTORY_VALIDATION_FAILED:
            self.validation_phase = "failed"
            self.terminal_failure = True
        elif event_type == LedgerEventType.ARCHIVE_STARTED:
            self.archive_phase = "started"
        elif event_type == LedgerEventType.ARCHIVE_PASSED:
            self.archive_phase = "passed"
        elif event_type == LedgerEventType.ARCHIVE_FAILED:
            self.archive_phase = "failed"
            self.terminal_failure = True
        elif event_type == LedgerEventType.RUN_STOPPED:
            self.stopped = True


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _open_or_create_directory_chain(
    root: Path,
    relative: Path,
    *,
    fault_injector: Callable[[str, str], None] | None = None,
) -> tuple[Path, int]:
    """Create a no-follow hierarchy and durably link every new component.

    The returned descriptor pins the final directory identity until the caller
    closes it.  A parent directory is fsynced immediately after each ``mkdirat``;
    therefore a ledger event cannot be considered durable while an unfynced
    ancestor entry is still pending.
    """

    if relative.is_absolute() or ".." in relative.parts:
        raise RequestLedgerError(LEDGER_CREATE_FAILURE)
    descriptor = -1
    current_path = root
    try:
        descriptor = os.open(root, _directory_flags())
        root_status = os.fstat(descriptor)
        if not stat.S_ISDIR(root_status.st_mode) or root_status.st_uid != os.getuid():
            raise OSError
        for component in relative.parts:
            created = False
            try:
                os.mkdir(component, mode=0o700, dir_fd=descriptor)
                created = True
            except FileExistsError:
                pass
            if created:
                if fault_injector is not None:
                    fault_injector("ledger_directory", "before_parent_fsync")
                os.fsync(descriptor)
            child = os.open(component, _directory_flags(), dir_fd=descriptor)
            child_status = os.fstat(child)
            if not stat.S_ISDIR(child_status.st_mode) or child_status.st_uid != os.getuid():
                os.close(child)
                raise OSError
            os.close(descriptor)
            descriptor = child
            current_path /= component
        return current_path, descriptor
    except Exception:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        raise RequestLedgerError(LEDGER_CREATE_FAILURE) from None


def _disposition_name(run_binding: InventoryRunBindingV2) -> str:
    return f"{run_binding.run_id}.json"


def _existing_disposition_blocks_run(
    root: Path,
    *,
    plan: ReadOnlyInventoryPlanV2,
    run_binding: InventoryRunBindingV2,
) -> bool:
    """Check the single bounded tombstone without creating its directory."""

    relative = Path(plan.preflight_disposition_root_relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise RequestLedgerError(LEDGER_CREATE_FAILURE)
    descriptor = -1
    try:
        descriptor = os.open(root, _directory_flags())
        for component in relative.parts:
            try:
                child = os.open(component, _directory_flags(), dir_fd=descriptor)
            except FileNotFoundError:
                return False
            os.close(descriptor)
            descriptor = child
        try:
            os.stat(
                _disposition_name(run_binding),
                dir_fd=descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return False
        # Any object at the fixed tombstone name burns the identity.  A malformed
        # object is not permission to create another run with the same identity.
        return True
    except OSError:
        raise RequestLedgerError(LEDGER_CREATE_FAILURE) from None
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)


def load_request_ledger_validator(
    repository_root: Path, plan: ReadOnlyInventoryPlanV2
) -> Draft202012Validator:
    schema_path = repository_root / plan.ledger_schema_relative_path
    try:
        encoded = schema_path.read_bytes()
    except OSError:
        raise RequestLedgerError(LEDGER_CREATE_FAILURE) from None
    if hashlib.sha256(encoded).hexdigest() != plan.ledger_schema_sha256:
        raise RequestLedgerError(LEDGER_CREATE_FAILURE)
    try:
        schema = json.loads(encoded)
        Draft202012Validator.check_schema(schema)
    except Exception:
        raise RequestLedgerError(LEDGER_CREATE_FAILURE) from None
    return Draft202012Validator(schema, format_checker=FormatChecker())


@dataclass(slots=True)
class FsyncRequestLedger:
    path: Path
    descriptor: int
    plan: ReadOnlyInventoryPlanV2
    plan_sha256: str
    run_binding: InventoryRunBindingV2
    validator: Draft202012Validator
    monotonic_ns: Callable[[], int]
    utc_now: Callable[[], datetime]
    fault_injector: Callable[[str, str], None] | None = None
    state: _LedgerStateMachine = field(default_factory=_LedgerStateMachine)
    next_sequence: int = 1
    bytes_written: int = 0
    events_written: int = 0
    per_request_events: dict[int, int] | None = None
    capacity_reserved: bool = False
    reservation_path: Path | None = None
    reservation_descriptor: int = -1
    tainted: bool = False
    closed: bool = False

    def __post_init__(self) -> None:
        if self.per_request_events is None:
            self.per_request_events = {}

    @classmethod
    def create(
        cls,
        repository_root: Path,
        *,
        plan: ReadOnlyInventoryPlanV2,
        plan_sha256: str,
        run_binding: InventoryRunBindingV2,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
        fault_injector: Callable[[str, str], None] | None = None,
    ) -> FsyncRequestLedger:
        root = repository_root.resolve(strict=True)
        if root != repository_root.absolute() or run_binding.run_id != plan.run_id:
            raise RequestLedgerError(LEDGER_CREATE_FAILURE)
        run_relative = Path(plan.run_root_relative_path)
        ledger_relative = Path(plan.ledger_relative_path)
        if (
            run_relative.is_absolute()
            or ledger_relative.is_absolute()
            or ".." in run_relative.parts
            or ledger_relative.parent != run_relative
            or ledger_relative.name != "request-ledger.jsonl"
        ):
            raise RequestLedgerError(LEDGER_CREATE_FAILURE)
        if _existing_disposition_blocks_run(
            root,
            plan=plan,
            run_binding=run_binding,
        ):
            raise RequestLedgerError(LEDGER_CREATE_FAILURE)

        parent_descriptor = -1
        run_descriptor = -1
        descriptor = -1
        try:
            _, parent_descriptor = _open_or_create_directory_chain(
                root,
                run_relative.parent,
                fault_injector=fault_injector,
            )
            os.mkdir(run_relative.name, mode=0o700, dir_fd=parent_descriptor)
            if fault_injector is not None:
                fault_injector("run_identity", "before_parent_fsync")
            os.fsync(parent_descriptor)
            run_descriptor = os.open(
                run_relative.name,
                _directory_flags(),
                dir_fd=parent_descriptor,
            )
            run_status = os.fstat(run_descriptor)
            if not stat.S_ISDIR(run_status.st_mode) or run_status.st_uid != os.getuid():
                raise OSError
            os.fsync(run_descriptor)

            # The exclusive, durable run root is the identity tombstone.  Load
            # fallible schema material only after that identity is burned.
            validator = load_request_ledger_validator(root, plan)
            flags = (
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptor = os.open(
                ledger_relative.name,
                flags,
                0o600,
                dir_fd=run_descriptor,
            )
            os.fsync(run_descriptor)
        except Exception:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            raise RequestLedgerError(LEDGER_CREATE_FAILURE) from None
        finally:
            if run_descriptor >= 0:
                with suppress(OSError):
                    os.close(run_descriptor)
            if parent_descriptor >= 0:
                with suppress(OSError):
                    os.close(parent_descriptor)
        return cls(
            path=root / ledger_relative,
            descriptor=descriptor,
            plan=plan,
            plan_sha256=plan_sha256,
            run_binding=run_binding,
            validator=validator,
            monotonic_ns=monotonic_ns,
            utc_now=utc_now,
            fault_injector=fault_injector,
        )

    def reserve_capacity(self) -> None:
        if self.closed or self.tainted or self.capacity_reserved:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if (
            self.plan.limits.max_events * self.plan.limits.max_event_bytes
            > self.plan.limits.max_bytes
        ):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        try:
            status = os.statvfs(self.path.parent)
        except OSError:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE) from None
        free_bytes = status.f_bavail * status.f_frsize
        if free_bytes < self.plan.local_prewrite_floor_bytes:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        reservation_path = self.path.parent / ".request-ledger.capacity"
        descriptor = -1
        directory_descriptor = -1
        try:
            descriptor = os.open(
                reservation_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            block = bytes(65_536)
            remaining = self.plan.limits.max_bytes
            while remaining:
                written = os.write(descriptor, block[:remaining])
                if written < 1:
                    raise OSError
                remaining -= written
            os.fsync(descriptor)
            observed = os.fstat(descriptor)
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_nlink != 1
                or observed.st_size != self.plan.limits.max_bytes
            ):
                raise OSError
            directory_descriptor = os.open(self.path.parent, _directory_flags())
            if self.fault_injector is not None:
                self.fault_injector("capacity_reservation", "before_parent_fsync")
            os.fsync(directory_descriptor)
        except Exception:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            with suppress(OSError):
                reservation_path.unlink()
            with suppress(OSError):
                if directory_descriptor < 0:
                    directory_descriptor = os.open(self.path.parent, _directory_flags())
                os.fsync(directory_descriptor)
            raise RequestLedgerError(LEDGER_WRITE_FAILURE) from None
        finally:
            if directory_descriptor >= 0:
                with suppress(OSError):
                    os.close(directory_descriptor)
        self.reservation_path = reservation_path
        self.reservation_descriptor = descriptor
        self.capacity_reserved = True

    def _release_capacity_reservation(self, *, strict: bool) -> None:
        failed = False
        if self.reservation_descriptor >= 0:
            try:
                os.close(self.reservation_descriptor)
            except OSError:
                failed = True
            self.reservation_descriptor = -1
        if self.reservation_path is not None:
            try:
                self.reservation_path.unlink()
            except OSError:
                failed = True
            try:
                directory_descriptor = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
            except OSError:
                failed = True
            self.reservation_path = None
        self.capacity_reserved = False
        if strict and failed:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)

    def append(
        self,
        event_type: LedgerEventType,
        *,
        request: RequestContext | None = None,
        bytes_received: int = 0,
        http_status: int | None = None,
        content_type: str | None = None,
        elapsed_ms: int | None = None,
        failure: SanitizedFailure | None = None,
    ) -> None:
        if self.closed or self.tainted or event_type.value not in LEDGER_EVENT_TYPES:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if request is not None and not self.capacity_reserved:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if bytes_received < 0 or (
            request is not None and bytes_received > MAX_INVENTORY_RESPONSE_BYTES
        ):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if content_type not in {None, "application/json", "unexpected"}:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        failure_events = {
            LedgerEventType.RUN_PREFLIGHT_FAILED,
            LedgerEventType.SECRET_PRESENCE_CHECK_FAILED,
            LedgerEventType.REQUEST_FAILED,
            LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND,
            LedgerEventType.INVENTORY_VALIDATION_FAILED,
            LedgerEventType.ARCHIVE_FAILED,
        }
        if event_type in failure_events and failure is None:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if failure is not None and event_type not in {
            *failure_events,
            LedgerEventType.RUN_STOPPED,
        }:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        now = self.utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z")
        document: dict[str, object] = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "event_type": event_type.value,
            "run_id": self.run_binding.run_id,
            "plan_id": self.run_binding.plan_id,
            "authorization_reference": self.run_binding.authorization_reference,
            "event_sequence": self.next_sequence,
            "request_ordinal": request.ordinal if request is not None else None,
            "method": request.method if request is not None else None,
            "scheme": APPROVED_LEDGER_SCHEME if request is not None else None,
            "host": APPROVED_LEDGER_HOST if request is not None else None,
            "path": request.path if request is not None else None,
            "query_key_names": list(request.query_key_names) if request is not None else [],
            "transport_kind": self.plan.transport_kind,
            "monotonic_timestamp_ns": self.monotonic_ns(),
            "wall_timestamp_utc": now,
            "bytes_received_so_far": bytes_received,
            "http_status": http_status,
            "content_type": content_type,
            "elapsed_ms": elapsed_ms,
            "sanitized_failure_stage": failure.stage.value if failure is not None else None,
            "sanitized_failure_class": (
                failure.classification.value if failure is not None else None
            ),
            "stable_error_code": failure.stable_error_code if failure is not None else None,
            "retry_count": 0,
            "pagination_request": False,
        }
        if list(self.validator.iter_errors(document)):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        self.state.validate(document)
        encoded = (
            json.dumps(
                document,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        request_count = 0
        if request is not None:
            assert self.per_request_events is not None
            request_count = self.per_request_events.get(request.ordinal, 0) + 1
            if request_count > self.plan.limits.max_events_per_request:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        if (
            len(encoded) > self.plan.limits.max_event_bytes
            or self.events_written + 1 > self.plan.limits.max_events
            or self.bytes_written + len(encoded) > self.plan.limits.max_bytes
        ):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        offset = 0
        try:
            if self.fault_injector is not None:
                self.fault_injector(event_type.value, "before_write")
            while offset < len(encoded):
                written = os.write(self.descriptor, encoded[offset:])
                if written < 1:
                    raise OSError
                offset += written
            if self.fault_injector is not None:
                self.fault_injector(event_type.value, "before_fsync")
            os.fsync(self.descriptor)
        except RequestLedgerError:
            if offset:
                self.tainted = True
            raise
        except OSError:
            self.tainted = True
            raise RequestLedgerError(LEDGER_WRITE_FAILURE) from None
        self.state.apply(document)
        self.next_sequence += 1
        self.bytes_written += len(encoded)
        self.events_written += 1
        if request is not None:
            assert self.per_request_events is not None
            self.per_request_events[request.ordinal] = request_count

    def snapshot_for_archive(self) -> RequestLedgerSnapshot:
        if (
            self.closed
            or self.tainted
            or self.state.validation_phase != "passed"
            or self.state.archive_phase != "started"
            or self.state.completed_requests != self.plan.max_calls
        ):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        try:
            os.fsync(self.descriptor)
            encoded = self.path.read_bytes()
        except OSError:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE) from None
        events = validate_request_ledger_bytes(
            encoded,
            plan=self.plan,
            run_binding=self.run_binding,
            validator=self.validator,
            require_archive_eligible=True,
        )
        return RequestLedgerSnapshot(
            path=self.path,
            sha256=hashlib.sha256(encoded).hexdigest(),
            bytes=len(encoded),
            events=len(events),
        )

    def seal(self, *, require_terminal_success: bool) -> RequestLedgerSnapshot:
        if self.closed or self.tainted:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        try:
            os.fsync(self.descriptor)
            os.fchmod(self.descriptor, 0o400)
            os.close(self.descriptor)
        except OSError:
            self.closed = True
            raise RequestLedgerError(LEDGER_WRITE_FAILURE) from None
        self.closed = True
        self._release_capacity_reservation(strict=True)
        try:
            encoded = self.path.read_bytes()
        except OSError:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE) from None
        events = validate_request_ledger_bytes(
            encoded,
            plan=self.plan,
            run_binding=self.run_binding,
            validator=self.validator,
            require_terminal_success=require_terminal_success,
        )
        return RequestLedgerSnapshot(
            path=self.path,
            sha256=hashlib.sha256(encoded).hexdigest(),
            bytes=len(encoded),
            events=len(events),
        )

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
        with suppress(RequestLedgerError):
            self._release_capacity_reservation(strict=False)


def validate_request_ledger_bytes(
    encoded: bytes,
    *,
    plan: ReadOnlyInventoryPlanV2,
    run_binding: InventoryRunBindingV2,
    validator: Draft202012Validator,
    require_archive_eligible: bool = False,
    require_terminal_success: bool = False,
) -> tuple[dict[str, object], ...]:
    if len(encoded) > plan.limits.max_bytes or not encoded.endswith(b"\n"):
        raise RequestLedgerError(LEDGER_WRITE_FAILURE)
    machine = _LedgerStateMachine()
    events: list[dict[str, object]] = []
    per_request: dict[int, int] = {}
    last_monotonic_timestamp = -1
    for sequence, line in enumerate(encoded.splitlines(), start=1):
        if not line or len(line) + 1 > plan.limits.max_event_bytes:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        try:
            pairs: list[tuple[str, object]] = json.loads(
                line,
                object_pairs_hook=lambda values: list(values),
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE) from None
        event: dict[str, object] = {}
        for key, value in pairs:
            if not isinstance(key, str) or key in event:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            event[key] = value
        if (
            event.get("event_sequence") != sequence
            or event.get("run_id") != run_binding.run_id
            or event.get("plan_id") != run_binding.plan_id
            or event.get("authorization_reference") != run_binding.authorization_reference
            or list(validator.iter_errors(event))
        ):
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        ordinal = event.get("request_ordinal")
        if isinstance(ordinal, int) and not isinstance(ordinal, bool):
            if not 1 <= ordinal <= len(plan.requests):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            expected_context = RequestContext.from_request(
                ordinal,
                plan.requests[ordinal - 1],
            )
            if (
                event.get("method") != expected_context.method
                or event.get("scheme") != APPROVED_LEDGER_SCHEME
                or event.get("host") != APPROVED_LEDGER_HOST
                or event.get("path") != expected_context.path
                or event.get("query_key_names") != list(expected_context.query_key_names)
                or _event_integer(event.get("bytes_received_so_far"))
                > plan.requests[ordinal - 1].max_response_bytes
            ):
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
            per_request[ordinal] = per_request.get(ordinal, 0) + 1
            if per_request[ordinal] > plan.limits.max_events_per_request:
                raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        monotonic_timestamp = _event_integer(event.get("monotonic_timestamp_ns"))
        if monotonic_timestamp < last_monotonic_timestamp:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
        last_monotonic_timestamp = monotonic_timestamp
        machine.validate(event)
        machine.apply(event)
        events.append(event)
        if len(events) > plan.limits.max_events:
            raise RequestLedgerError(LEDGER_WRITE_FAILURE)
    if require_archive_eligible and not (
        machine.completed_requests == plan.max_calls
        and machine.validation_phase == "passed"
        and machine.archive_phase == "started"
        and not machine.terminal_failure
    ):
        raise RequestLedgerError(LEDGER_WRITE_FAILURE)
    if require_terminal_success and not (
        machine.completed_requests == plan.max_calls
        and machine.validation_phase == "passed"
        and machine.archive_phase == "passed"
        and machine.stopped
        and not machine.terminal_failure
    ):
        raise RequestLedgerError(LEDGER_WRITE_FAILURE)
    return tuple(events)


def write_preflight_disposition(
    repository_root: Path,
    *,
    plan: ReadOnlyInventoryPlanV2,
    run_binding: InventoryRunBindingV2,
    failure: SanitizedFailure = LEDGER_CREATE_FAILURE,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> RequestLedgerSnapshot:
    """Write the one bounded run-identity tombstone without consulting a secret."""

    root = repository_root.resolve(strict=True)
    relative_root = Path(plan.preflight_disposition_root_relative_path)
    parent, parent_descriptor = _open_or_create_directory_chain(root, relative_root)
    target_name = _disposition_name(run_binding)
    target = parent / target_name
    document = {
        "schema_version": "0.1.0",
        "run_id": run_binding.run_id,
        "plan_id": run_binding.plan_id,
        "authorization_reference": run_binding.authorization_reference,
        "wall_timestamp_utc": utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "disposition": "preflight-blocked",
        "sanitized_failure_stage": failure.stage.value,
        "sanitized_failure_class": failure.classification.value,
        "stable_error_code": failure.stable_error_code,
        "real_secret_accessed": False,
        "account_request_attempted": False,
        "run_identity_reusable": False,
    }
    encoded = (
        json.dumps(document, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
        + b"\n"
    )
    if len(encoded) > plan.limits.max_preflight_disposition_bytes:
        with suppress(OSError):
            os.close(parent_descriptor)
        raise RequestLedgerError(LEDGER_CREATE_FAILURE)
    descriptor = -1
    try:
        descriptor = os.open(
            target_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written < 1:
                raise OSError
            offset += written
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
        os.close(descriptor)
        descriptor = -1
        os.fsync(parent_descriptor)
    except OSError:
        with suppress(OSError):
            os.close(parent_descriptor)
        raise RequestLedgerError(LEDGER_CREATE_FAILURE) from None
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
    observed_descriptor = -1
    try:
        observed_descriptor = os.open(
            target_name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_descriptor,
        )
        observed_status = os.fstat(observed_descriptor)
        if (
            not stat.S_ISREG(observed_status.st_mode)
            or observed_status.st_nlink != 1
            or observed_status.st_size != len(encoded)
        ):
            raise OSError
        observed = b""
        while len(observed) < len(encoded):
            block = os.read(observed_descriptor, len(encoded) - len(observed))
            if not block:
                break
            observed += block
    except OSError:
        raise RequestLedgerError(LEDGER_CREATE_FAILURE) from None
    finally:
        if observed_descriptor >= 0:
            with suppress(OSError):
                os.close(observed_descriptor)
        with suppress(OSError):
            os.close(parent_descriptor)
    if observed != encoded:
        raise RequestLedgerError(LEDGER_CREATE_FAILURE)
    return RequestLedgerSnapshot(
        path=target,
        sha256=hashlib.sha256(observed).hexdigest(),
        bytes=len(observed),
        events=1,
    )


def contains_forbidden_material(encoded_surfaces: Sequence[bytes], *, canary: bytes) -> bool:
    """Return true only when the exact synthetic canary survives a retained surface."""

    return bool(canary) and any(canary in surface for surface in encoded_surfaces)
