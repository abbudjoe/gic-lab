"""Network-inert-on-import, non-authoritative Gate L2 draft primitives.

The module contains a mutation-capable in-process HTTPS transport, typed request
rendering, and an append-only fsync request ledger. It does not implement the required
end-to-end supervisor and must not be treated as executable authority. Tests inject a
fake transport; importing or constructing these objects performs no account request.
"""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import json
import os
import re
import ssl
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

from jsonschema import Draft202012Validator

from .lambda_l20_plan import (
    MAX_PROVIDER_API_CALLS,
    MAX_PROVIDER_LEDGER_BYTES,
    MAX_PROVIDER_LEDGER_EVENT_BYTES,
    MAX_PROVIDER_LEDGER_EVENTS,
    MAX_PROVIDER_REQUEST_BODY_BYTES,
    MAX_PROVIDER_RESPONSE_BYTES_PER_CALL,
    PLAN_ID,
    RUN_ID,
    canonical_bytes,
    provider_operations,
    render_global_restore_body,
    render_launch_body,
    render_terminate_body,
)

LEDGER_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-provider-ledger.schema.json"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class L2ExecutionError(ValueError):
    """A closed Gate L2 request, ledger, or transport contract failure."""


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    call_ordinal: int
    operation_ordinal: int
    operation_id: str
    method: str
    path: str
    expected_status: int
    body: Mapping[str, object] | None = field(default=None, repr=False)

    @property
    def body_bytes(self) -> bytes | None:
        return None if self.body is None else canonical_bytes(self.body)

    @property
    def body_sha256(self) -> str | None:
        encoded = self.body_bytes
        return None if encoded is None else hashlib.sha256(encoded).hexdigest()


def _safe_identity(value: object, *, context: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise L2ExecutionError(f"{context} is not one safe immutable identity")
    return value


def render_provider_request(
    *,
    call_ordinal: int,
    operation_ordinal: int,
    private_requests: Mapping[str, object],
    runtime_bindings: Mapping[str, object],
    authorization_reference: str,
) -> ProviderRequest:
    """Render one exact provider request from typed private/runtime bindings."""

    operations = provider_operations()
    if (
        not 1 <= operation_ordinal <= len(operations)
        or not 1 <= call_ordinal <= MAX_PROVIDER_API_CALLS
    ):
        raise L2ExecutionError("provider request ordinal is outside the exact plan")
    operation = operations[operation_ordinal - 1]
    path = str(operation["path"])
    owned_ruleset = runtime_bindings.get("owned_regional_ruleset_id")
    owned_instance = runtime_bindings.get("owned_instance_id")
    if "{owned_ruleset_id}" in path:
        path = path.replace(
            "{owned_ruleset_id}",
            _safe_identity(owned_ruleset, context="owned ruleset ID"),
        )
    if "{owned_instance_id}" in path:
        path = path.replace(
            "{owned_instance_id}",
            _safe_identity(owned_instance, context="owned instance ID"),
        )
    if "{" in path or not path.startswith("/api/v1/") or "?" in path or "#" in path:
        raise L2ExecutionError("provider request path is unresolved or outside the allowlist")

    body: Mapping[str, object] | None = None
    body_name = operation.get("private_body")
    if body_name == "strict_global_patch_body":
        body = _mapping(private_requests.get("strict_global_patch_body"), "strict body")
    elif body_name == "regional_create_body":
        body = _mapping(private_requests.get("regional_create_body"), "regional body")
    elif body_name == "launch_body_rendered":
        body = render_launch_body(
            _mapping(private_requests.get("launch_body_template"), "launch template"),
            owned_regional_ruleset_id=_safe_identity(
                owned_ruleset,
                context="owned ruleset ID",
            ),
            authorization_reference=authorization_reference,
        )
    elif body_name == "terminate_body_rendered":
        body = render_terminate_body(_safe_identity(owned_instance, context="owned instance ID"))
    elif body_name == "restore_global_patch_body_from_sealed_runtime_binding":
        body = render_global_restore_body(
            _mapping(
                runtime_bindings.get("sealed_original_global_response"),
                "sealed original global response",
            )
        )
    elif body_name is not None:
        raise L2ExecutionError("provider operation has an unknown private body renderer")

    method = str(operation["method"])
    if method in {"POST", "PATCH"} and body is None:
        raise L2ExecutionError("provider mutation request lacks an exact body")
    if method in {"GET", "DELETE"} and body is not None:
        raise L2ExecutionError("bodyless provider method unexpectedly has a body")
    encoded = None if body is None else canonical_bytes(body)
    if encoded is not None and len(encoded) > MAX_PROVIDER_REQUEST_BODY_BYTES:
        raise L2ExecutionError("provider request body exceeds its cap")
    _safe_identity(authorization_reference, context="authorization reference")
    if authorization_reference.endswith("-PENDING"):
        raise L2ExecutionError("pending authorization cannot render a provider request")
    expected_status = operation["expected_status"]
    if type(expected_status) is not int:
        raise L2ExecutionError("provider expected status is not an integer")
    return ProviderRequest(
        call_ordinal=call_ordinal,
        operation_ordinal=operation_ordinal,
        operation_id=str(operation["id"]),
        method=method,
        path=path,
        expected_status=expected_status,
        body=body,
    )


def _mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise L2ExecutionError(f"{context} is not an object")
    return value


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    status: int
    content_type: str
    body: bytes = field(repr=False)
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class TransportFailure(Exception):
    stage: str
    classification: str


class ProviderTransport(Protocol):
    def send(
        self,
        request: ProviderRequest,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> ProviderResponse: ...


class LambdaHttpsL2Transport:
    """Exact-host, no-redirect, in-process HTTPS transport for authorized L2 use."""

    def __init__(
        self,
        *,
        ssl_context: ssl.SSLContext | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ssl_context = ssl_context or ssl.create_default_context()
        self._clock = clock

    def send(
        self,
        request: ProviderRequest,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> ProviderResponse:
        if (
            not credential
            or len(credential) > 4_096
            or any(marker in credential for marker in ("\r", "\n", "\x00"))
        ):
            raise TransportFailure("secret_source", "secret_malformed")
        if not 0 < timeout_seconds <= 60:
            raise TransportFailure("deadline", "deadline_exceeded")
        started = self._clock()
        connection = http.client.HTTPSConnection(
            "cloud.lambda.ai",
            443,
            timeout=timeout_seconds,
            context=self._ssl_context,
        )
        encoded = request.body_bytes
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {credential}",
            "User-Agent": "giclab-t07-gate-l2-v1/1",
        }
        if encoded is not None:
            headers["Content-Type"] = "application/json"
        try:
            try:
                connection.request(request.method, request.path, body=encoded, headers=headers)
            except (OSError, ssl.SSLError, http.client.HTTPException):
                raise TransportFailure("request_write", "request_write_failure") from None
            try:
                response = connection.getresponse()
            except (OSError, ssl.SSLError, http.client.HTTPException):
                raise TransportFailure("response_headers", "response_headers_failure") from None
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].casefold()
            if 300 <= response.status <= 399:
                raise TransportFailure("redirect", "http_redirect")
            if content_type != "application/json":
                raise TransportFailure("content_type", "unexpected_content_type")
            body = bytearray()
            while True:
                try:
                    chunk = response.read(65_536)
                except (OSError, ssl.SSLError, http.client.HTTPException):
                    raise TransportFailure("response_body", "response_body_failure") from None
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > MAX_PROVIDER_RESPONSE_BYTES_PER_CALL:
                    raise TransportFailure("response_size", "response_too_large")
            elapsed = max(0, min(60_000, int((self._clock() - started) * 1_000)))
            return ProviderResponse(response.status, content_type, bytes(body), elapsed)
        finally:
            with contextlib.suppress(OSError):
                connection.close()


@dataclass(frozen=True, slots=True)
class LedgerSnapshot:
    path: Path
    sha256: str
    bytes: int
    events: int


@dataclass(slots=True)
class FsyncL2ProviderLedger:
    path: Path
    descriptor: int
    authorization_reference: str
    validator: Draft202012Validator
    monotonic_ns: Callable[[], int] = time.monotonic_ns
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC)
    sequence: int = 1
    bytes_written: int = 0
    events_written: int = 0
    active_call: int | None = None
    active_phase: str | None = None
    capacity_path: Path | None = None
    capacity_descriptor: int = -1
    closed: bool = False

    @classmethod
    def create(
        cls,
        repository_root: Path,
        *,
        path: Path,
        authorization_reference: str,
    ) -> FsyncL2ProviderLedger:
        root = repository_root.resolve(strict=True)
        target = path.absolute()
        try:
            target.relative_to(root)
        except ValueError:
            raise L2ExecutionError("provider ledger escaped the repository attempt root") from None
        if not target.parent.is_dir() or target.name != "provider-request-ledger.jsonl":
            raise L2ExecutionError("provider ledger path is not the exact run-owned path")
        schema_bytes = (root / LEDGER_SCHEMA_PATH).read_bytes()
        schema = json.loads(schema_bytes)
        validator = Draft202012Validator(schema)
        try:
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            parent_descriptor = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(parent_descriptor)
            finally:
                os.close(parent_descriptor)
        except OSError:
            raise L2ExecutionError("provider ledger exclusive creation failed") from None
        return cls(target, descriptor, authorization_reference, validator)

    def reserve_capacity(self) -> None:
        """Durably reserve the complete ledger cap before any request intent."""

        if self.closed or self.capacity_path is not None or self.events_written:
            raise L2ExecutionError("provider ledger capacity reservation order drifted")
        reservation = self.path.parent / ".provider-ledger.capacity"
        descriptor = -1
        try:
            descriptor = os.open(
                reservation,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            block = bytes(65_536)
            remaining = MAX_PROVIDER_LEDGER_BYTES
            while remaining:
                written = os.write(descriptor, block[:remaining])
                if written < 1:
                    raise OSError
                remaining -= written
            os.fsync(descriptor)
            parent = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except OSError:
            if descriptor >= 0:
                with contextlib.suppress(OSError):
                    os.close(descriptor)
            with contextlib.suppress(OSError):
                reservation.unlink()
            raise L2ExecutionError("provider ledger capacity reservation failed") from None
        self.capacity_path = reservation
        self.capacity_descriptor = descriptor

    def append(
        self,
        event_type: str,
        *,
        request: ProviderRequest | None = None,
        status: int | None = None,
        content_type: str | None = None,
        response_bytes: int = 0,
        elapsed_ms: int | None = None,
        failure_stage: str | None = None,
        failure_class: str | None = None,
    ) -> None:
        if self.closed or self.events_written >= MAX_PROVIDER_LEDGER_EVENTS:
            raise L2ExecutionError("provider ledger is closed or exhausted")
        call = None if request is None else request.call_ordinal
        if event_type == "request_intent_committed":
            if self.capacity_path is None or self.active_call is not None or request is None:
                raise L2ExecutionError("provider ledger request intent order drifted")
            self.active_call, self.active_phase = call, "intent"
        elif event_type == "request_send_started":
            if call != self.active_call or self.active_phase != "intent":
                raise L2ExecutionError("provider ledger send order drifted")
            self.active_phase = "sent"
        elif event_type == "response_headers_received":
            if call != self.active_call or self.active_phase != "sent":
                raise L2ExecutionError("provider ledger response-header order drifted")
            self.active_phase = "headers"
        elif event_type in {
            "response_body_completed",
            "request_failed",
            "request_outcome_unknown_after_send",
        }:
            if call != self.active_call or self.active_phase not in {"sent", "headers"}:
                raise L2ExecutionError("provider ledger terminal event order drifted")
            self.active_call = None
            self.active_phase = None
        event: dict[str, object] = {
            "schema_version": "0.1.0",
            "run_id": RUN_ID,
            "plan_id": PLAN_ID,
            "authorization_reference": self.authorization_reference,
            "event_sequence": self.sequence,
            "event_type": event_type,
            "monotonic_timestamp_ns": self.monotonic_ns(),
            "wall_timestamp_utc": self.utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "retry_count": 0,
            "response_bytes": response_bytes,
        }
        if request is not None:
            event.update(
                {
                    "call_ordinal": request.call_ordinal,
                    "operation_ordinal": request.operation_ordinal,
                    "operation_id": request.operation_id,
                    "method": request.method,
                    "scheme": "https",
                    "host": "cloud.lambda.ai",
                    "path": request.path,
                }
            )
            if request.body_sha256 is not None:
                event["request_body_sha256"] = request.body_sha256
        for key, value in (
            ("http_status", status),
            ("content_type", content_type),
            ("elapsed_ms", elapsed_ms),
            ("sanitized_failure_stage", failure_stage),
            ("sanitized_failure_class", failure_class),
        ):
            if value is not None:
                event[key] = value
        errors = list(self.validator.iter_errors(event))
        encoded = canonical_bytes(event)
        if errors or len(encoded) > MAX_PROVIDER_LEDGER_EVENT_BYTES:
            raise L2ExecutionError("provider ledger event schema or byte cap failed")
        if self.bytes_written + len(encoded) > MAX_PROVIDER_LEDGER_BYTES:
            raise L2ExecutionError("provider ledger aggregate byte cap failed")
        try:
            written = os.write(self.descriptor, encoded)
            if written != len(encoded):
                raise OSError
            os.fsync(self.descriptor)
        except OSError:
            raise L2ExecutionError("provider ledger append/fsync failed") from None
        self.sequence += 1
        self.bytes_written += len(encoded)
        self.events_written += 1

    def close(self) -> LedgerSnapshot:
        if self.closed or self.active_call is not None:
            raise L2ExecutionError("provider ledger cannot close with an active request")
        os.fsync(self.descriptor)
        os.close(self.descriptor)
        if self.capacity_descriptor >= 0:
            os.close(self.capacity_descriptor)
            self.capacity_descriptor = -1
        if self.capacity_path is not None:
            self.capacity_path.unlink()
            parent = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
            self.capacity_path = None
        self.closed = True
        encoded = self.path.read_bytes()
        status = self.path.stat(follow_symlinks=False)
        if not stat.S_ISREG(status.st_mode) or len(encoded) != self.bytes_written:
            raise L2ExecutionError("provider ledger final identity drifted")
        return LedgerSnapshot(
            self.path,
            hashlib.sha256(encoded).hexdigest(),
            len(encoded),
            self.events_written,
        )


def execute_observed_request(
    *,
    ledger: FsyncL2ProviderLedger,
    transport: ProviderTransport,
    request: ProviderRequest,
    credential: str,
    timeout_seconds: float,
) -> ProviderResponse:
    """Execute one future request with durable intent/send/terminal observability."""

    ledger.append("request_intent_committed", request=request)
    ledger.append("request_send_started", request=request)
    try:
        response = transport.send(
            request,
            credential=credential,
            timeout_seconds=timeout_seconds,
        )
    except TransportFailure as failure:
        ledger.append(
            "request_failed",
            request=request,
            failure_stage=failure.stage,
            failure_class=failure.classification,
        )
        raise L2ExecutionError(
            "provider request failed with one sanitized transport class"
        ) from None
    except Exception:
        ledger.append(
            "request_outcome_unknown_after_send",
            request=request,
            failure_stage="unknown",
            failure_class="outcome_unknown",
        )
        raise L2ExecutionError("provider request outcome is unknown after send") from None
    ledger.append(
        "response_headers_received",
        request=request,
        status=response.status,
        content_type=response.content_type,
        elapsed_ms=response.elapsed_ms,
    )
    if response.status != request.expected_status:
        failure_class = {
            401: "http_unauthorized",
            403: "http_forbidden",
            429: "http_rate_limited",
        }.get(response.status, "http_unexpected_status")
        ledger.append(
            "request_failed",
            request=request,
            status=response.status,
            content_type=response.content_type,
            response_bytes=len(response.body),
            elapsed_ms=response.elapsed_ms,
            failure_stage="http_status",
            failure_class=failure_class,
        )
        raise L2ExecutionError("provider response status differs from the exact operation")
    ledger.append(
        "response_body_completed",
        request=request,
        status=response.status,
        content_type=response.content_type,
        response_bytes=len(response.body),
        elapsed_ms=response.elapsed_ms,
    )
    return response
