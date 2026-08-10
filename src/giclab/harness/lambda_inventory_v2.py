"""Observable, fail-closed supervisor for a future authorized Gate L1 V2 run.

This module is inert on import.  Its concrete transport is an in-process HTTPS
client with a closed error taxonomy; tests use only fake transports and synthetic
credentials.  The request ledger is created and capacity-reserved before the
credential provider is called.
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import os
import socket
import ssl
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TypeAlias, cast

from giclab.validation import validate_instance

from .lambda_archive import InventoryArchiveError
from .lambda_archive_v2 import (
    ArchivedInventoryArtifactV2,
    DurableInventoryArchiverV2,
    InventoryArchiverV2,
)
from .lambda_cloud import (
    INVENTORY_PLAN_V2_ID,
    MAX_INVENTORY_TOTAL_WALL_SECONDS,
    MAX_INVENTORY_WALL_SECONDS,
    ComputeCandidate,
    IncrementalInventoryParser,
    InstanceSelectionError,
    InventoryRequest,
    InventoryResponseFailureKind,
    InventoryResponseValidationError,
    LambdaCloudContractError,
    canonical_inventory_bytes,
    inventory_document,
    select_compute_candidate,
)
from .lambda_inventory import (
    ProcessDeadlineFactory,
    RepositoryState,
    SealedInventoryArtifact,
    SubprocessDeadlineWatchdog,
    _armed_process_deadline,
    inspect_repository_state,
    seal_inventory_artifact,
)
from .lambda_inventory_plan import (
    InventoryRunBindingV2,
    ReadOnlyInventoryPlanV2,
    inventory_ledger_contract_document_v2,
    inventory_limits_document_v2,
    load_inventory_plan_v2,
    verify_inventory_implementation_v2,
)
from .lambda_request_ledger import (
    OUTCOME_UNKNOWN_FAILURE,
    FailureClass,
    FailureStage,
    FsyncRequestLedger,
    InventoryObservedFailure,
    LedgerEventType,
    RequestContext,
    RequestLedgerError,
    RequestLedgerSnapshot,
    SanitizedFailure,
    contains_forbidden_material,
    write_preflight_disposition,
)

SocketAddress: TypeAlias = tuple[str, int] | tuple[str, int, int, int]
AddressInfo: TypeAlias = tuple[int, int, int, str, SocketAddress]
CredentialProvider: TypeAlias = Callable[[], str | None]
FaultInjector: TypeAlias = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class InventoryHttpResponseV2:
    status_code: int
    content_type: str
    body: bytes
    elapsed_ms: int


class InventoryTransportObserver(Protocol):
    def response_headers_received(
        self,
        *,
        status_code: int,
        content_type: str,
        elapsed_ms: int,
    ) -> None: ...

    def response_body_progress(
        self,
        *,
        bytes_received: int,
        status_code: int,
        content_type: str,
        elapsed_ms: int,
    ) -> None: ...


class ObservableInventoryTransport(Protocol):
    def fetch(
        self,
        request: InventoryRequest,
        *,
        credential: str,
        timeout_seconds: float,
        observer: InventoryTransportObserver,
    ) -> InventoryHttpResponseV2: ...


@dataclass(frozen=True, slots=True)
class InventoryRunResultV2:
    run_id: str
    authorization_reference: str
    artifact: SealedInventoryArtifact
    ledger: RequestLedgerSnapshot
    archive: ArchivedInventoryArtifactV2
    copy_record: SealedInventoryArtifact
    selection_state: str
    candidate: ComputeCandidate | None
    blocked_reason: str | None
    provider_calls: int


def _failure(
    stage: FailureStage,
    classification: FailureClass,
    code: str,
) -> SanitizedFailure:
    return SanitizedFailure(stage, classification, code)


PREFLIGHT_FAILURE = _failure(
    FailureStage.UNKNOWN,
    FailureClass.INTERNAL_FAILURE,
    "L1_PREFLIGHT_FAILED",
)
SECRET_MISSING_FAILURE = _failure(
    FailureStage.SECRET_SOURCE,
    FailureClass.SECRET_MISSING,
    "L1_SECRET_MISSING",
)
SECRET_MALFORMED_FAILURE = _failure(
    FailureStage.SECRET_SOURCE,
    FailureClass.SECRET_MALFORMED,
    "L1_SECRET_MALFORMED",
)
PRESEND_INTERNAL_FAILURE = _failure(
    FailureStage.UNKNOWN,
    FailureClass.INTERNAL_FAILURE,
    "L1_PRESEND_INTERNAL_FAILURE",
)
VALIDATION_INTERNAL_FAILURE = _failure(
    FailureStage.SCHEMA_VALIDATION,
    FailureClass.INTERNAL_FAILURE,
    "L1_INVENTORY_VALIDATION_FAILED",
)
ARCHIVE_FAILURE = _failure(
    FailureStage.ARCHIVE_IO,
    FailureClass.ARCHIVE_FAILED,
    "L1_ARCHIVE_FAILED",
)
DEADLINE_FAILURE = _failure(
    FailureStage.UNKNOWN,
    FailureClass.DEADLINE_EXCEEDED,
    "L1_DEADLINE_EXCEEDED",
)


def _observed_failure(
    stage: FailureStage,
    classification: FailureClass,
    code: str,
    *,
    http_status: int | None = None,
    content_type: str | None = None,
    bytes_received: int = 0,
    elapsed_ms: int | None = None,
) -> InventoryObservedFailure:
    return InventoryObservedFailure(
        _failure(stage, classification, code),
        http_status=http_status,
        content_type=content_type,
        bytes_received=bytes_received,
        elapsed_ms=elapsed_ms,
    )


def _bounded_resolve_v2(
    *,
    deadline: float,
    clock: Callable[[], float],
) -> tuple[AddressInfo, ...]:
    values: list[AddressInfo] = []
    failed = False
    complete = threading.Event()

    def resolve() -> None:
        nonlocal failed
        try:
            raw = socket.getaddrinfo("cloud.lambda.ai", 443, type=socket.SOCK_STREAM)
            values.extend(cast(list[AddressInfo], raw))
        except OSError:
            failed = True
        finally:
            complete.set()

    worker = threading.Thread(target=resolve, name="t07-l1-v2-dns", daemon=True)
    worker.start()
    remaining = deadline - clock()
    if remaining <= 0 or not complete.wait(remaining):
        raise _observed_failure(
            FailureStage.DNS,
            FailureClass.DEADLINE_EXCEEDED,
            "L1_DNS_DEADLINE_EXCEEDED",
        )
    if failed or not values:
        raise _observed_failure(
            FailureStage.DNS,
            FailureClass.DNS_FAILURE,
            "L1_DNS_FAILURE",
        )
    return tuple(values)


class _ResolvedHTTPSConnectionV2(http.client.HTTPSConnection):
    def __init__(
        self,
        addresses: Sequence[AddressInfo],
        *,
        deadline: float,
        clock: Callable[[], float],
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(
            "cloud.lambda.ai",
            443,
            timeout=max(deadline - clock(), 0.001),
            context=context,
        )
        self._addresses = tuple(addresses)
        self._deadline = deadline
        self._clock = clock
        self._t07_context = context

    def connect(self) -> None:
        tcp_failed = False
        tls_failed = False
        for family, socket_type, protocol, _, socket_address in self._addresses:
            remaining = self._deadline - self._clock()
            if remaining <= 0:
                raise _observed_failure(
                    FailureStage.TCP_CONNECT,
                    FailureClass.DEADLINE_EXCEEDED,
                    "L1_TCP_DEADLINE_EXCEEDED",
                )
            raw_socket = socket.socket(family, socket_type, protocol)
            self.sock = raw_socket
            try:
                raw_socket.settimeout(remaining)
                raw_socket.connect(socket_address)
            except OSError:
                tcp_failed = True
                raw_socket.close()
                self.sock = None
                continue
            remaining = self._deadline - self._clock()
            if remaining <= 0:
                raw_socket.close()
                self.sock = None
                raise _observed_failure(
                    FailureStage.TLS_HANDSHAKE,
                    FailureClass.DEADLINE_EXCEEDED,
                    "L1_TLS_DEADLINE_EXCEEDED",
                )
            try:
                raw_socket.settimeout(remaining)
                self.sock = self._t07_context.wrap_socket(
                    raw_socket,
                    server_hostname="cloud.lambda.ai",
                )
                return
            except (OSError, ssl.SSLError):
                tls_failed = True
                raw_socket.close()
                self.sock = None
        if tls_failed:
            raise _observed_failure(
                FailureStage.TLS_HANDSHAKE,
                FailureClass.TLS_FAILURE,
                "L1_TLS_FAILURE",
            )
        if tcp_failed:
            raise _observed_failure(
                FailureStage.TCP_CONNECT,
                FailureClass.TCP_CONNECT_FAILURE,
                "L1_TCP_CONNECT_FAILURE",
            )
        raise _observed_failure(
            FailureStage.TCP_CONNECT,
            FailureClass.TCP_CONNECT_FAILURE,
            "L1_TCP_ADDRESS_SET_EMPTY",
        )


class LambdaHttpsInventoryTransportV2:
    """Exact-host, non-redirecting, in-process HTTPS transport."""

    def __init__(
        self,
        *,
        ssl_context: ssl.SSLContext | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ssl_context = ssl_context or ssl.create_default_context()
        self._clock = clock

    def fetch(
        self,
        request: InventoryRequest,
        *,
        credential: str,
        timeout_seconds: float,
        observer: InventoryTransportObserver,
    ) -> InventoryHttpResponseV2:
        if (
            not credential
            or len(credential) > 4096
            or any(marker in credential for marker in ("\r", "\n", "\x00"))
        ):
            raise _observed_failure(
                FailureStage.SECRET_SOURCE,
                FailureClass.SECRET_MALFORMED,
                "L1_SECRET_MALFORMED",
            )
        if timeout_seconds <= 0 or timeout_seconds > MAX_INVENTORY_WALL_SECONDS:
            raise _observed_failure(
                FailureStage.UNKNOWN,
                FailureClass.DEADLINE_EXCEEDED,
                "L1_REQUEST_DEADLINE_INVALID",
            )
        started = self._clock()
        deadline = started + timeout_seconds
        addresses = _bounded_resolve_v2(deadline=deadline, clock=self._clock)
        connection = _ResolvedHTTPSConnectionV2(
            addresses,
            deadline=deadline,
            clock=self._clock,
            context=self._ssl_context,
        )

        def elapsed_ms() -> int:
            return max(0, min(60_000, int((self._clock() - started) * 1000)))

        def expire_connection() -> None:
            active_socket = connection.sock
            if active_socket is not None:
                with contextlib.suppress(OSError):
                    active_socket.shutdown(socket.SHUT_RDWR)
            connection.close()

        watchdog = threading.Timer(max(deadline - self._clock(), 0.001), expire_connection)
        watchdog.daemon = True
        watchdog.start()
        status_code: int | None = None
        content_type: str | None = None
        observed_bytes = 0
        try:
            try:
                connection.request(
                    "GET",
                    request.path,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {credential}",
                        "User-Agent": "giclab-t07-gate-l1-v2/1",
                    },
                )
            except InventoryObservedFailure:
                raise
            except (OSError, http.client.HTTPException, ssl.SSLError):
                raise _observed_failure(
                    FailureStage.REQUEST_WRITE,
                    FailureClass.REQUEST_WRITE_FAILURE,
                    "L1_REQUEST_WRITE_FAILURE",
                    elapsed_ms=elapsed_ms(),
                ) from None
            try:
                response = connection.getresponse()
            except InventoryObservedFailure:
                raise
            except (OSError, http.client.HTTPException, ssl.SSLError):
                raise _observed_failure(
                    FailureStage.RESPONSE_HEADERS,
                    FailureClass.RESPONSE_HEADERS_FAILURE,
                    "L1_RESPONSE_HEADERS_FAILURE",
                    elapsed_ms=elapsed_ms(),
                ) from None
            status_code = response.status
            raw_content_type = response.getheader("Content-Type", "")
            normalized = raw_content_type.split(";", 1)[0].strip().casefold()
            content_type = "application/json" if normalized == "application/json" else "unexpected"
            observer.response_headers_received(
                status_code=status_code,
                content_type=content_type,
                elapsed_ms=elapsed_ms(),
            )
            if 300 <= status_code <= 399:
                raise _observed_failure(
                    FailureStage.REDIRECT,
                    FailureClass.HTTP_REDIRECT,
                    "L1_HTTP_REDIRECT",
                    http_status=status_code,
                    content_type=content_type,
                    elapsed_ms=elapsed_ms(),
                )
            status_failures = {
                401: (FailureClass.HTTP_UNAUTHORIZED, "L1_HTTP_401"),
                403: (FailureClass.HTTP_FORBIDDEN, "L1_HTTP_403"),
                429: (FailureClass.HTTP_RATE_LIMITED, "L1_HTTP_429"),
            }
            if status_code in status_failures:
                classification, code = status_failures[status_code]
                stage = FailureStage.RATE_LIMIT if status_code == 429 else FailureStage.HTTP_STATUS
                raise _observed_failure(
                    stage,
                    classification,
                    code,
                    http_status=status_code,
                    content_type=content_type,
                    elapsed_ms=elapsed_ms(),
                )
            if status_code != 200:
                raise _observed_failure(
                    FailureStage.HTTP_STATUS,
                    FailureClass.HTTP_UNEXPECTED_STATUS,
                    "L1_HTTP_STATUS_UNEXPECTED",
                    http_status=status_code,
                    content_type=content_type,
                    elapsed_ms=elapsed_ms(),
                )
            if content_type != "application/json":
                raise _observed_failure(
                    FailureStage.CONTENT_TYPE,
                    FailureClass.UNEXPECTED_CONTENT_TYPE,
                    "L1_CONTENT_TYPE_UNEXPECTED",
                    http_status=status_code,
                    content_type=content_type,
                    elapsed_ms=elapsed_ms(),
                )
            chunks: list[bytes] = []
            while True:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    raise _observed_failure(
                        FailureStage.RESPONSE_BODY,
                        FailureClass.DEADLINE_EXCEEDED,
                        "L1_RESPONSE_BODY_DEADLINE_EXCEEDED",
                        http_status=status_code,
                        content_type=content_type,
                        bytes_received=observed_bytes,
                        elapsed_ms=elapsed_ms(),
                    )
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                try:
                    chunk = response.read(
                        min(65_536, request.max_response_bytes + 1 - observed_bytes)
                    )
                except (OSError, http.client.HTTPException, ssl.SSLError):
                    raise _observed_failure(
                        FailureStage.RESPONSE_BODY,
                        FailureClass.RESPONSE_BODY_FAILURE,
                        "L1_RESPONSE_BODY_FAILURE",
                        http_status=status_code,
                        content_type=content_type,
                        bytes_received=observed_bytes,
                        elapsed_ms=elapsed_ms(),
                    ) from None
                if not chunk:
                    break
                chunks.append(chunk)
                observed_bytes += len(chunk)
                if observed_bytes > request.max_response_bytes:
                    raise _observed_failure(
                        FailureStage.RESPONSE_SIZE,
                        FailureClass.RESPONSE_TOO_LARGE,
                        "L1_RESPONSE_TOO_LARGE",
                        http_status=status_code,
                        content_type=content_type,
                        bytes_received=observed_bytes,
                        elapsed_ms=elapsed_ms(),
                    )
                observer.response_body_progress(
                    bytes_received=observed_bytes,
                    status_code=status_code,
                    content_type=content_type,
                    elapsed_ms=elapsed_ms(),
                )
            return InventoryHttpResponseV2(
                status_code=status_code,
                content_type=content_type,
                body=b"".join(chunks),
                elapsed_ms=elapsed_ms(),
            )
        except RequestLedgerError:
            raise
        except InventoryObservedFailure:
            raise
        finally:
            watchdog.cancel()
            connection.close()


@dataclass(slots=True)
class _LedgerTransportObserver:
    ledger: FsyncRequestLedger
    request: RequestContext
    next_progress_threshold: int = 65_536
    progress_events: int = 0
    headers_seen: bool = False
    status_code: int | None = None
    content_type: str | None = None
    elapsed_ms: int | None = None
    bytes_received: int = 0

    def response_headers_received(
        self,
        *,
        status_code: int,
        content_type: str,
        elapsed_ms: int,
    ) -> None:
        if self.headers_seen:
            raise RequestLedgerError(self.ledger_write_failure)
        self.ledger.append(
            LedgerEventType.RESPONSE_HEADERS_RECEIVED,
            request=self.request,
            http_status=status_code,
            content_type=content_type,
            elapsed_ms=elapsed_ms,
        )
        self.headers_seen = True
        self.status_code = status_code
        self.content_type = content_type
        self.elapsed_ms = elapsed_ms

    @property
    def ledger_write_failure(self) -> SanitizedFailure:
        return _failure(
            FailureStage.LEDGER_IO,
            FailureClass.LEDGER_WRITE_FAILED,
            "L1_LEDGER_WRITE_FAILED",
        )

    def response_body_progress(
        self,
        *,
        bytes_received: int,
        status_code: int,
        content_type: str,
        elapsed_ms: int,
    ) -> None:
        if (
            not self.headers_seen
            or status_code != self.status_code
            or content_type != self.content_type
            or bytes_received < self.bytes_received
        ):
            raise RequestLedgerError(self.ledger_write_failure)
        self.bytes_received = bytes_received
        self.elapsed_ms = elapsed_ms
        if bytes_received >= self.next_progress_threshold and self.progress_events < 4:
            self.ledger.append(
                LedgerEventType.RESPONSE_BODY_PROGRESS,
                request=self.request,
                bytes_received=bytes_received,
                http_status=status_code,
                content_type=content_type,
                elapsed_ms=elapsed_ms,
            )
            self.progress_events += 1
            self.next_progress_threshold += 65_536


def _validation_failure(error: InventoryResponseValidationError) -> SanitizedFailure:
    mapping = {
        InventoryResponseFailureKind.JSON_DECODE: (
            FailureStage.JSON_DECODE,
            FailureClass.MALFORMED_JSON,
        ),
        InventoryResponseFailureKind.SCHEMA_VALIDATION: (
            FailureStage.SCHEMA_VALIDATION,
            FailureClass.SCHEMA_DRIFT,
        ),
        InventoryResponseFailureKind.PAGINATION: (
            FailureStage.PAGINATION,
            FailureClass.PAGINATION_PRESENT,
        ),
    }
    stage, classification = mapping[error.kind]
    return _failure(stage, classification, error.stable_code)


def _append_run_stopped(
    ledger: FsyncRequestLedger,
    *,
    failure: SanitizedFailure | None,
) -> None:
    ledger.append(LedgerEventType.RUN_STOPPED, failure=failure)


def _bounded_elapsed_ms(
    clock: Callable[[], float],
    started: float | None,
) -> int | None:
    if started is None:
        return None
    return max(0, min(60_000, int((clock() - started) * 1000)))


def _terminate_ledger_after_failure(
    ledger: FsyncRequestLedger,
    *,
    request: RequestContext | None,
    failure: SanitizedFailure,
    network_outcome_unknown: bool,
    fallback_elapsed_ms: int | None,
) -> None:
    if ledger.closed or ledger.tainted:
        ledger.close_preserving_incomplete()
        return
    try:
        phase = ledger.state.request_phase
        if request is not None and phase in {
            "intent",
            "send",
            "headers",
            "progress",
            "body_completed",
        }:
            elapsed_ms = (
                ledger.state.last_elapsed_ms
                if ledger.state.last_elapsed_ms is not None
                else fallback_elapsed_ms
            )
            if network_outcome_unknown and phase in {"send", "headers", "progress"}:
                ledger.append(
                    LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND,
                    request=request,
                    bytes_received=ledger.state.last_response_bytes,
                    http_status=ledger.state.response_status,
                    content_type=ledger.state.response_content_type,
                    elapsed_ms=elapsed_ms,
                    failure=OUTCOME_UNKNOWN_FAILURE,
                )
                failure = OUTCOME_UNKNOWN_FAILURE
            else:
                request_failure = (
                    VALIDATION_INTERNAL_FAILURE if phase == "body_completed" else failure
                )
                ledger.append(
                    LedgerEventType.REQUEST_FAILED,
                    request=request,
                    bytes_received=ledger.state.last_response_bytes,
                    http_status=ledger.state.response_status,
                    content_type=ledger.state.response_content_type,
                    elapsed_ms=elapsed_ms,
                    failure=request_failure,
                )
                failure = request_failure
        elif not ledger.state.preflight_passed and not ledger.state.preflight_failed:
            ledger.append(LedgerEventType.RUN_PREFLIGHT_FAILED, failure=failure)
        elif (
            ledger.state.completed_requests == ledger.plan.max_calls
            and ledger.state.validation_phase is None
        ):
            ledger.append(LedgerEventType.INVENTORY_VALIDATION_STARTED)
            ledger.append(LedgerEventType.INVENTORY_VALIDATION_FAILED, failure=failure)
        elif ledger.state.validation_phase == "started":
            ledger.append(LedgerEventType.INVENTORY_VALIDATION_FAILED, failure=failure)
        elif ledger.state.validation_phase == "passed" and ledger.state.archive_phase is None:
            ledger.append(LedgerEventType.ARCHIVE_STARTED)
            ledger.append(LedgerEventType.ARCHIVE_FAILED, failure=failure)
        elif ledger.state.archive_phase == "started":
            ledger.append(LedgerEventType.ARCHIVE_FAILED, failure=failure)
        if ledger.state.archive_phase == "passed" and not ledger.state.terminal_failure:
            _append_run_stopped(ledger, failure=None)
            ledger.seal(require_terminal_success=True)
        else:
            _append_run_stopped(ledger, failure=failure)
            ledger.seal(require_terminal_success=False)
    except RequestLedgerError:
        ledger.close_preserving_incomplete()


def execute_authorized_inventory_v2(
    *,
    repository_root: Path,
    plan_path: Path,
    plan_sha256: str,
    run_binding: InventoryRunBindingV2,
    credential_provider: CredentialProvider,
    transport: ObservableInventoryTransport,
    archiver: InventoryArchiverV2,
    watchdog_factory: ProcessDeadlineFactory = SubprocessDeadlineWatchdog.arm,
    repository_inspector: Callable[..., RepositoryState] = inspect_repository_state,
    implementation_verifier: Callable[
        [Path, ReadOnlyInventoryPlanV2], None
    ] = verify_inventory_implementation_v2,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
    fault_injector: FaultInjector | None = None,
) -> InventoryRunResultV2:
    """Execute exactly one fresh V2 identity after separate user authorization."""

    result: InventoryRunResultV2 | None = None
    terminal_kind: str | None = None
    terminal_failure: SanitizedFailure | None = None
    terminal_http_status: int | None = None
    terminal_content_type: str | None = None
    terminal_bytes_received = 0
    terminal_elapsed_ms: int | None = None
    try:
        with _armed_process_deadline(watchdog_factory, MAX_INVENTORY_TOTAL_WALL_SECONDS):
            result = _execute_within_total_deadline(
                repository_root=repository_root,
                plan_path=plan_path,
                plan_sha256=plan_sha256,
                run_binding=run_binding,
                credential_provider=credential_provider,
                transport=transport,
                archiver=archiver,
                watchdog_factory=watchdog_factory,
                repository_inspector=repository_inspector,
                implementation_verifier=implementation_verifier,
                clock=clock,
                sleeper=sleeper,
                monotonic_ns=monotonic_ns,
                utc_now=utc_now,
                fault_injector=fault_injector,
            )
    except RequestLedgerError as error:
        terminal_kind = "ledger"
        terminal_failure = error.failure
    except InventoryObservedFailure as error:
        terminal_kind = "observed"
        terminal_failure = error.failure
        terminal_http_status = error.http_status
        terminal_content_type = error.content_type
        terminal_bytes_received = error.bytes_received
        terminal_elapsed_ms = error.elapsed_ms
    except BaseException:
        terminal_kind = "observed"
        terminal_failure = PRESEND_INTERNAL_FAILURE
    finally:
        del credential_provider
        del transport
        del archiver

    if terminal_kind == "ledger" and terminal_failure is not None:
        raise RequestLedgerError(terminal_failure) from None
    if terminal_kind == "observed" and terminal_failure is not None:
        raise InventoryObservedFailure(
            terminal_failure,
            http_status=terminal_http_status,
            content_type=terminal_content_type,
            bytes_received=terminal_bytes_received,
            elapsed_ms=terminal_elapsed_ms,
        ) from None
    if result is None:
        raise InventoryObservedFailure(PRESEND_INTERNAL_FAILURE) from None
    return result


def _execute_within_total_deadline(
    *,
    repository_root: Path,
    plan_path: Path,
    plan_sha256: str,
    run_binding: InventoryRunBindingV2,
    credential_provider: CredentialProvider,
    transport: ObservableInventoryTransport,
    archiver: InventoryArchiverV2,
    watchdog_factory: ProcessDeadlineFactory,
    repository_inspector: Callable[..., RepositoryState],
    implementation_verifier: Callable[[Path, ReadOnlyInventoryPlanV2], None],
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
    monotonic_ns: Callable[[], int],
    utc_now: Callable[[], datetime],
    fault_injector: FaultInjector | None,
) -> InventoryRunResultV2:
    root = repository_root.resolve(strict=True)
    plan = load_inventory_plan_v2(plan_path, expected_sha256=plan_sha256)
    if run_binding.run_id != plan.run_id:
        raise LambdaCloudContractError("Gate L1 V2 run binding drifted")
    total_started = clock()

    def check_total_wall() -> None:
        if clock() - total_started > plan.max_total_wall_seconds:
            raise InventoryObservedFailure(DEADLINE_FAILURE)

    ledger: FsyncRequestLedger | None = None
    prepared_archive = None
    request_context: RequestContext | None = None
    credential: str | None = None
    response: InventoryHttpResponseV2 | None = None
    encoded: bytes | None = None
    document: dict[str, object] | None = None
    result: InventoryRunResultV2 | None = None
    terminal_kind: str | None = None
    terminal_failure: SanitizedFailure | None = None
    terminal_http_status: int | None = None
    terminal_content_type: str | None = None
    terminal_bytes_received = 0
    terminal_elapsed_ms: int | None = None
    previous_request_started: float | None = None
    current_request_started: float | None = None
    try:
        try:
            ledger = FsyncRequestLedger.create(
                root,
                plan=plan,
                plan_sha256=plan_sha256,
                run_binding=run_binding,
                monotonic_ns=monotonic_ns,
                utc_now=utc_now,
            )
        except RequestLedgerError:
            write_preflight_disposition(
                root,
                plan=plan,
                run_binding=run_binding,
                utc_now=utc_now,
            )
            raise
        ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
        try:
            ledger.reserve_capacity()
            implementation_verifier(root, plan)
            repository_inspector(root, expected_commit=run_binding.repository_commit)
            check_total_wall()
            prepared_archive = archiver.prepare(
                root,
                plan=plan,
                plan_sha256=plan_sha256,
                run_binding=run_binding,
            )
            credential = credential_provider()
            if credential is None or credential == "":
                ledger.append(
                    LedgerEventType.SECRET_PRESENCE_CHECK_FAILED,
                    failure=SECRET_MISSING_FAILURE,
                )
                ledger.append(
                    LedgerEventType.RUN_PREFLIGHT_FAILED,
                    failure=SECRET_MISSING_FAILURE,
                )
                _append_run_stopped(ledger, failure=SECRET_MISSING_FAILURE)
                ledger.seal(require_terminal_success=False)
                raise InventoryObservedFailure(SECRET_MISSING_FAILURE)
            if len(credential) > 4096 or any(
                marker in credential for marker in ("\r", "\n", "\x00")
            ):
                ledger.append(
                    LedgerEventType.SECRET_PRESENCE_CHECK_FAILED,
                    failure=SECRET_MALFORMED_FAILURE,
                )
                ledger.append(
                    LedgerEventType.RUN_PREFLIGHT_FAILED,
                    failure=SECRET_MALFORMED_FAILURE,
                )
                _append_run_stopped(ledger, failure=SECRET_MALFORMED_FAILURE)
                ledger.seal(require_terminal_success=False)
                raise InventoryObservedFailure(SECRET_MALFORMED_FAILURE)
            ledger.append(LedgerEventType.SECRET_PRESENCE_CHECK_PASSED)
            ledger.append(LedgerEventType.RUN_PREFLIGHT_PASSED)
        except (RequestLedgerError, InventoryObservedFailure):
            raise
        except Exception:
            ledger.append(LedgerEventType.RUN_PREFLIGHT_FAILED, failure=PREFLIGHT_FAILURE)
            _append_run_stopped(ledger, failure=PREFLIGHT_FAILURE)
            ledger.seal(require_terminal_success=False)
            raise InventoryObservedFailure(PREFLIGHT_FAILURE) from None

        parser = IncrementalInventoryParser(plan)
        provider_started = clock()
        for ordinal, request in enumerate(plan.requests, start=1):
            current_request_started = None
            check_total_wall()
            if previous_request_started is not None:
                spacing = plan.request_start_spacing_seconds - (clock() - previous_request_started)
                if spacing > 0:
                    if clock() - provider_started + spacing > plan.max_wall_seconds:
                        raise InventoryObservedFailure(DEADLINE_FAILURE)
                    sleeper(spacing)
            remaining = plan.max_wall_seconds - (clock() - provider_started)
            if remaining <= 0:
                raise InventoryObservedFailure(DEADLINE_FAILURE)
            if fault_injector is not None:
                fault_injector("before_intent")
            request_context = RequestContext.from_request(ordinal, request)
            ledger.append(
                LedgerEventType.REQUEST_INTENT_COMMITTED,
                request=request_context,
            )
            if fault_injector is not None:
                fault_injector("after_intent_before_send")
            ledger.append(
                LedgerEventType.REQUEST_SEND_STARTED,
                request=request_context,
            )
            current_request_started = clock()
            previous_request_started = current_request_started
            if fault_injector is not None:
                fault_injector("after_send_started")
            observer = _LedgerTransportObserver(ledger, request_context)
            try:
                response = transport.fetch(
                    request,
                    credential=credential,
                    timeout_seconds=remaining,
                    observer=observer,
                )
                if (
                    not observer.headers_seen
                    or response.status_code != observer.status_code
                    or response.content_type != observer.content_type
                    or len(response.body) > request.max_response_bytes
                ):
                    raise _observed_failure(
                        FailureStage.SCHEMA_VALIDATION,
                        FailureClass.SCHEMA_DRIFT,
                        "L1_TRANSPORT_OBSERVER_DRIFT",
                        http_status=response.status_code,
                        content_type=response.content_type,
                        bytes_received=len(response.body),
                        elapsed_ms=response.elapsed_ms,
                    )
                ledger.append(
                    LedgerEventType.RESPONSE_BODY_COMPLETED,
                    request=request_context,
                    bytes_received=len(response.body),
                    http_status=response.status_code,
                    content_type=response.content_type,
                    elapsed_ms=response.elapsed_ms,
                )
                try:
                    parser.accept(request, response.body)
                except InventoryResponseValidationError as error:
                    raise InventoryObservedFailure(
                        _validation_failure(error),
                        http_status=response.status_code,
                        content_type=response.content_type,
                        bytes_received=len(response.body),
                        elapsed_ms=response.elapsed_ms,
                    ) from None
                ledger.append(
                    LedgerEventType.RESPONSE_VALIDATION_PASSED,
                    request=request_context,
                    bytes_received=len(response.body),
                    http_status=response.status_code,
                    content_type=response.content_type,
                    elapsed_ms=response.elapsed_ms,
                )
            except InventoryObservedFailure as error:
                observed_elapsed_ms = (
                    error.elapsed_ms
                    if error.elapsed_ms is not None
                    else _bounded_elapsed_ms(clock, current_request_started)
                )
                ledger.append(
                    LedgerEventType.REQUEST_FAILED,
                    request=request_context,
                    bytes_received=min(error.bytes_received, request.max_response_bytes),
                    http_status=error.http_status,
                    content_type=error.content_type,
                    elapsed_ms=observed_elapsed_ms,
                    failure=error.failure,
                )
                _append_run_stopped(ledger, failure=error.failure)
                ledger.seal(require_terminal_success=False)
                raise InventoryObservedFailure(
                    error.failure,
                    http_status=error.http_status,
                    content_type=error.content_type,
                    bytes_received=error.bytes_received,
                    elapsed_ms=observed_elapsed_ms,
                ) from None
            request_context = None
            current_request_started = None
        if clock() - provider_started > plan.max_wall_seconds:
            raise InventoryObservedFailure(DEADLINE_FAILURE)
        check_total_wall()
        ledger.append(LedgerEventType.INVENTORY_VALIDATION_STARTED)
        try:
            inventory = parser.finish()
            candidate: ComputeCandidate | None = None
            selection_failure: InstanceSelectionError | None = None
            try:
                candidate = select_compute_candidate(inventory)
            except InstanceSelectionError as error:
                selection_failure = error
            observed_at = utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z")
            document = inventory_document(
                inventory,
                candidate,
                observed_at_utc=observed_at,
                inventory_plan_sha256=plan_sha256,
                run_binding=run_binding,
                selection_failure=selection_failure,
                plan_id=INVENTORY_PLAN_V2_ID,
                run_attempt=plan.attempt,
                limits_document=inventory_limits_document_v2(plan),
                request_ledger_contract=inventory_ledger_contract_document_v2(plan),
            )
            schema_path = root / plan.inventory_schema_relative_path
            if validate_instance(document, schema_path):
                raise LambdaCloudContractError("Gate L1 V2 artifact schema validation failed")
            encoded = canonical_inventory_bytes(document)
            if contains_forbidden_material((encoded,), canary=credential.encode()):
                raise LambdaCloudContractError("Gate L1 V2 secret canary reached artifact")
            artifact = seal_inventory_artifact(
                root,
                relative_path=plan.output_relative_path,
                encoded=encoded,
                max_bytes=plan.max_retained_output_bytes,
            )
        except Exception:
            ledger.append(
                LedgerEventType.INVENTORY_VALIDATION_FAILED,
                failure=VALIDATION_INTERNAL_FAILURE,
            )
            _append_run_stopped(ledger, failure=VALIDATION_INTERNAL_FAILURE)
            ledger.seal(require_terminal_success=False)
            raise InventoryObservedFailure(VALIDATION_INTERNAL_FAILURE) from None
        ledger.append(LedgerEventType.INVENTORY_VALIDATION_PASSED)
        check_total_wall()
        with _armed_process_deadline(watchdog_factory, plan.max_archive_wall_seconds):
            ledger.append(LedgerEventType.ARCHIVE_STARTED)
            try:
                assert prepared_archive is not None
                prepared_archive.stage_inventory(
                    artifact.path,
                    artifact_sha256=artifact.sha256,
                    artifact_bytes=artifact.bytes,
                )
            except Exception:
                ledger.append(LedgerEventType.ARCHIVE_FAILED, failure=ARCHIVE_FAILURE)
                _append_run_stopped(ledger, failure=ARCHIVE_FAILURE)
                ledger.seal(require_terminal_success=False)
                raise InventoryObservedFailure(ARCHIVE_FAILURE) from None
            ledger.append(LedgerEventType.ARCHIVE_PASSED)
            _append_run_stopped(ledger, failure=None)
            terminal_ledger = ledger.seal(require_terminal_success=True)
            try:
                archived = prepared_archive.finalize(
                    artifact.path,
                    artifact_sha256=artifact.sha256,
                    artifact_bytes=artifact.bytes,
                    ledger=terminal_ledger,
                )
            except Exception:
                raise InventoryObservedFailure(ARCHIVE_FAILURE) from None
        if contains_forbidden_material(
            (
                terminal_ledger.path.read_bytes(),
                archived.local_verification_record,
            ),
            canary=credential.encode(),
        ):
            raise InventoryObservedFailure(ARCHIVE_FAILURE)
        copy_record = seal_inventory_artifact(
            root,
            relative_path=plan.copy_record_relative_path,
            encoded=archived.local_verification_record,
            max_bytes=plan.max_local_record_bytes,
        )
        free_status = os.statvfs(root)
        if free_status.f_bavail * free_status.f_frsize < plan.local_retained_floor_bytes:
            raise InventoryObservedFailure(ARCHIVE_FAILURE)
        check_total_wall()
        result = InventoryRunResultV2(
            run_id=run_binding.run_id,
            authorization_reference=run_binding.authorization_reference,
            artifact=artifact,
            ledger=terminal_ledger,
            archive=archived,
            copy_record=copy_record,
            selection_state="selected" if candidate is not None else "blocked",
            candidate=candidate,
            blocked_reason=(
                selection_failure.code.value if selection_failure is not None else None
            ),
            provider_calls=parser.accepted_requests,
        )
    except RequestLedgerError as error:
        if ledger is not None:
            no_durable_event = ledger.events_written == 0
            if ledger.tainted:
                ledger.close_preserving_incomplete()
            else:
                _terminate_ledger_after_failure(
                    ledger,
                    request=request_context,
                    failure=error.failure,
                    network_outcome_unknown=True,
                    fallback_elapsed_ms=_bounded_elapsed_ms(
                        clock,
                        current_request_started,
                    ),
                )
            if no_durable_event:
                with contextlib.suppress(RequestLedgerError):
                    write_preflight_disposition(
                        root,
                        plan=plan,
                        run_binding=run_binding,
                        utc_now=utc_now,
                    )
        terminal_kind = "ledger"
        terminal_failure = error.failure
    except InventoryObservedFailure as error:
        if ledger is not None and not ledger.closed:
            _terminate_ledger_after_failure(
                ledger,
                request=request_context,
                failure=error.failure,
                network_outcome_unknown=False,
                fallback_elapsed_ms=_bounded_elapsed_ms(
                    clock,
                    current_request_started,
                ),
            )
        terminal_kind = "observed"
        terminal_failure = error.failure
        terminal_http_status = error.http_status
        terminal_content_type = error.content_type
        terminal_bytes_received = error.bytes_received
        terminal_elapsed_ms = error.elapsed_ms
    except BaseException:
        if ledger is not None:
            _terminate_ledger_after_failure(
                ledger,
                request=request_context,
                failure=PRESEND_INTERNAL_FAILURE,
                network_outcome_unknown=True,
                fallback_elapsed_ms=_bounded_elapsed_ms(
                    clock,
                    current_request_started,
                ),
            )
        terminal_kind = "observed"
        terminal_failure = PRESEND_INTERNAL_FAILURE
        terminal_elapsed_ms = _bounded_elapsed_ms(clock, current_request_started)
    finally:
        credential = None
        response = None
        encoded = None
        document = None
        request_context = None
        current_request_started = None
        if prepared_archive is not None:
            try:
                prepared_archive.close()
            except BaseException:
                if terminal_kind is None:
                    result = None
                    terminal_kind = "observed"
                    terminal_failure = ARCHIVE_FAILURE
        if ledger is not None and not ledger.closed:
            try:
                ledger.close_preserving_incomplete()
            except BaseException:
                if terminal_kind is None:
                    result = None
                    terminal_kind = "observed"
                    terminal_failure = (
                        ARCHIVE_FAILURE
                        if ledger.state.archive_phase is not None
                        else PRESEND_INTERNAL_FAILURE
                    )

    if terminal_kind == "ledger" and terminal_failure is not None:
        raise RequestLedgerError(terminal_failure) from None
    if terminal_kind == "observed" and terminal_failure is not None:
        raise InventoryObservedFailure(
            terminal_failure,
            http_status=terminal_http_status,
            content_type=terminal_content_type,
            bytes_received=terminal_bytes_received,
            elapsed_ms=terminal_elapsed_ms,
        ) from None
    if result is None:
        raise InventoryObservedFailure(PRESEND_INTERNAL_FAILURE) from None
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--authorization-reference", required=True)
    parser.add_argument("--authorization-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Future V2 entry point; the committed plan remains unauthorized."""

    args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    binding = InventoryRunBindingV2(
        run_id="RUN-T07-L1-LAMBDA-INVENTORY-0002",
        repository_commit=args.expected_commit,
        authorization_reference=args.authorization_reference,
        authorization_sha256=args.authorization_sha256,
    )
    try:
        result = execute_authorized_inventory_v2(
            repository_root=args.repository_root,
            plan_path=args.plan,
            plan_sha256=args.plan_sha256,
            run_binding=binding,
            credential_provider=lambda: os.environ.get("LAMBDA_API_KEY"),
            transport=LambdaHttpsInventoryTransportV2(),
            archiver=DurableInventoryArchiverV2(),
        )
    except (LambdaCloudContractError, InventoryArchiveError, OSError, ValueError):
        print(
            "giclab-lambda-inventory-v2: stopped; inspect the secret-free request ledger",
            file=sys.stderr,
        )
        return 1
    output: dict[str, object] = {
        "run_id": result.run_id,
        "authorization_reference": result.authorization_reference,
        "artifact_path": str(result.artifact.path),
        "artifact_sha256": result.artifact.sha256,
        "ledger_path": str(result.ledger.path),
        "ledger_sha256": result.ledger.sha256,
        "archive_path": str(result.archive.destination),
        "archive_seal_sha256": result.archive.seal_sha256,
        "local_copy_record_path": str(result.copy_record.path),
        "local_copy_record_sha256": result.copy_record.sha256,
        "provider_calls": result.provider_calls,
        "selection_state": result.selection_state,
        "blocked_reason": result.blocked_reason,
    }
    if result.candidate is not None:
        output["selected_tuple"] = {
            "instance_type_name": result.candidate.instance_type_name,
            "region_name": result.candidate.region_name,
            "image_id": result.candidate.image_id,
            "price_cents_per_hour": result.candidate.price_cents_per_hour,
            "gpus": result.candidate.gpus,
        }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
