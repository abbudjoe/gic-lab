"""Fail-closed future executor for the T07 Gate L1A one-request plan.

Importing this module is inert.  The CLI is the only production composition: it
binds the reviewed V3 in-process HTTPS transport to the fresh L1A ledger, strict
public-key parser, current-user ``~/.ssh/*.pub`` matcher, private/public evidence
split, and dedicated two-phase external archiver.  Tests inject only synthetic
credentials, fake transports, fake archivers, and fixture home directories.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import select
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeAlias, cast

from .lambda_archive import InventoryArchiveError
from .lambda_cloud import (
    HttpMethod,
    InventoryRequest,
    LambdaCloudContractError,
    secret_free_child_environment,
)
from .lambda_inventory import (
    ProcessDeadline,
    RepositoryState,
    inspect_repository_state,
)
from .lambda_inventory_plan_v3 import verify_repository_commit_ancestry_v3
from .lambda_inventory_v3 import (
    InventoryTransportObserver,
    LambdaHttpsInventoryTransportV3,
    ObservableInventoryTransport,
)
from .lambda_request_ledger_v3 import (
    FailureClass,
    FailureStage,
    InventoryObservedFailure,
    LedgerEventType,
    RequestLedgerSnapshot,
    SanitizedFailure,
)
from .lambda_ssh_key_archive import (
    ArchivedSSHKeyEvidence,
    ArchiveFinalizationEvidence,
    DurableSSHKeyArchiver,
    FsyncArchiveFinalizationDisposition,
    PreparedSSHKeyArchive,
    SSHKeyArchiver,
)
from .lambda_ssh_key_fingerprint import (
    EXECUTION_WRAPPER,
    MAX_PROVIDER_WALL_SECONDS,
    MAX_RESPONSE_BYTES,
    MAX_TOTAL_WALL_SECONDS,
    RUN_ID,
    SSH_KEYS_PATH,
    AccountKeyProjection,
    SSHKeyFingerprintError,
    SSHKeyRunBinding,
    load_ssh_key_fingerprint_plan,
    project_account_ssh_keys,
)
from .lambda_ssh_key_match import (
    LocalEvidenceBundle,
    LocalPublicKeyRecord,
    MatchResult,
    discover_local_public_keys,
    match_account_to_local_keys,
    validate_sanitized_report,
    write_local_evidence_bundle,
)
from .lambda_ssh_key_request_ledger import (
    FsyncSSHKeyRequestLedger,
    SSHKeyRequestContext,
    SSHKeyRequestLedgerError,
    write_ssh_key_preflight_disposition,
)

CredentialProvider: TypeAlias = Callable[[], str | None]
LocalKeyDiscoverer: TypeAlias = Callable[[], tuple[LocalPublicKeyRecord, ...]]
RepositoryInspector: TypeAlias = Callable[..., RepositoryState]
AncestryVerifier: TypeAlias = Callable[..., None]
DeadlineFactory: TypeAlias = Callable[[int], ProcessDeadline]


def _failure(
    stage: FailureStage,
    classification: FailureClass,
    code: str,
) -> SanitizedFailure:
    return SanitizedFailure(stage, classification, code)


PREFLIGHT_FAILURE = _failure(
    FailureStage.UNKNOWN,
    FailureClass.INTERNAL_FAILURE,
    "L1A_PREFLIGHT_FAILED",
)
SECRET_MISSING_FAILURE = _failure(
    FailureStage.SECRET_SOURCE,
    FailureClass.SECRET_MISSING,
    "L1A_SECRET_MISSING",
)
SECRET_MALFORMED_FAILURE = _failure(
    FailureStage.SECRET_SOURCE,
    FailureClass.SECRET_MALFORMED,
    "L1A_SECRET_MALFORMED",
)
SCHEMA_FAILURE = _failure(
    FailureStage.SCHEMA_VALIDATION,
    FailureClass.SCHEMA_DRIFT,
    "L1A_SSH_KEY_SCHEMA_INVALID",
)
MATCH_FAILURE = _failure(
    FailureStage.SCHEMA_VALIDATION,
    FailureClass.SCHEMA_DRIFT,
    "L1A_LOCAL_KEY_EVIDENCE_INVALID",
)
ARCHIVE_FAILURE = _failure(
    FailureStage.ARCHIVE_IO,
    FailureClass.ARCHIVE_FAILED,
    "L1A_ARCHIVE_FAILED",
)
PRESEND_FAILURE = _failure(
    FailureStage.UNKNOWN,
    FailureClass.INTERNAL_FAILURE,
    "L1A_PRESEND_FAILED",
)
OUTCOME_UNKNOWN_FAILURE = _failure(
    FailureStage.UNKNOWN,
    FailureClass.OUTCOME_UNKNOWN,
    "L1A_REQUEST_OUTCOME_UNKNOWN_AFTER_SEND",
)
DEADLINE_FAILURE = _failure(
    FailureStage.UNKNOWN,
    FailureClass.DEADLINE_EXCEEDED,
    "L1A_TOTAL_DEADLINE_EXCEEDED",
)


@dataclass(frozen=True, slots=True)
class _TransportRequest:
    request_id: str = "ssh-key-fingerprints"
    method: HttpMethod = HttpMethod.GET
    path: str = SSH_KEYS_PATH
    max_response_bytes: int = MAX_RESPONSE_BYTES


@dataclass(frozen=True, slots=True)
class SSHKeyRunResult:
    run_id: str
    authorization_reference: str
    provider_calls: int
    projection: AccountKeyProjection
    match: MatchResult
    bundle: LocalEvidenceBundle
    ledger: RequestLedgerSnapshot
    archive: ArchivedSSHKeyEvidence
    archive_finalization: ArchiveFinalizationEvidence


@dataclass(slots=True)
class SSHKeyDeadlineWatchdog:
    """Secret-free subprocess enforcing the exact 150-second hard wall."""

    process: subprocess.Popen[bytes]
    control_descriptor: int
    closed: bool = False

    @classmethod
    def arm(cls, seconds: int) -> SSHKeyDeadlineWatchdog:
        if seconds != MAX_TOTAL_WALL_SECONDS:
            raise SSHKeyFingerprintError("Gate L1A hard deadline drifted")
        read_descriptor, write_descriptor = os.pipe()
        ready_read_descriptor, ready_write_descriptor = os.pipe()
        command = [
            sys.executable,
            EXECUTION_WRAPPER,
            "_deadline-watchdog",
            str(read_descriptor),
            str(ready_write_descriptor),
            str(os.getpid()),
            str(seconds),
        ]
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                pass_fds=(read_descriptor, ready_write_descriptor),
                env=secret_free_child_environment(),
            )
        except (OSError, subprocess.SubprocessError):
            for descriptor in (
                read_descriptor,
                write_descriptor,
                ready_read_descriptor,
                ready_write_descriptor,
            ):
                with contextlib.suppress(OSError):
                    os.close(descriptor)
            raise SSHKeyFingerprintError("Gate L1A hard deadline failed to arm") from None
        os.close(read_descriptor)
        os.close(ready_write_descriptor)
        try:
            readable, _, _ = select.select((ready_read_descriptor,), (), (), 2)
            ready = os.read(ready_read_descriptor, 1) if readable else b""
        finally:
            os.close(ready_read_descriptor)
        if ready != b"R" or process.poll() is not None:
            process.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2)
            os.close(write_descriptor)
            raise SSHKeyFingerprintError("Gate L1A hard deadline failed readiness")
        return cls(process=process, control_descriptor=write_descriptor)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        with contextlib.suppress(OSError):
            os.write(self.control_descriptor, b"\x00")
        os.close(self.control_descriptor)
        try:
            return_code = self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.process.wait(timeout=2)
            raise SSHKeyFingerprintError("Gate L1A hard deadline cleanup failed") from None
        if return_code != 0:
            raise SSHKeyFingerprintError("Gate L1A hard deadline process failed")


def _deadline_watchdog_main(arguments: Sequence[str]) -> int:
    if len(arguments) != 4:
        return 2
    try:
        read_descriptor, ready_descriptor, target_pid, seconds = (int(value) for value in arguments)
    except ValueError:
        return 2
    if (
        read_descriptor < 0
        or ready_descriptor < 0
        or target_pid != os.getppid()
        or seconds != MAX_TOTAL_WALL_SECONDS
    ):
        return 2
    deadline = time.monotonic() + seconds
    try:
        if os.write(ready_descriptor, b"R") != 1:
            return 2
        os.close(ready_descriptor)
        ready_descriptor = -1
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                os.kill(target_pid, signal.SIGKILL)
                return 124
            readable, _, _ = select.select((read_descriptor,), (), (), remaining)
            if readable:
                os.read(read_descriptor, 1)
                return 0
    except (OSError, ValueError):
        return 2
    finally:
        with contextlib.suppress(OSError):
            os.close(read_descriptor)
        if ready_descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(ready_descriptor)


@contextlib.contextmanager
def _armed_deadline(factory: DeadlineFactory) -> Iterator[None]:
    watchdog = factory(MAX_TOTAL_WALL_SECONDS)
    try:
        yield
    finally:
        watchdog.close()


@dataclass(slots=True)
class _LedgerObserver(InventoryTransportObserver):
    ledger: FsyncSSHKeyRequestLedger
    request: SSHKeyRequestContext
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
            raise SSHKeyRequestLedgerError("duplicate response headers")
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
            raise SSHKeyRequestLedgerError("response progress identity drifted")
        self.bytes_received = bytes_received
        self.elapsed_ms = elapsed_ms
        if bytes_received >= self.next_progress_threshold and self.progress_events < 2:
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


def _append_stopped(
    ledger: FsyncSSHKeyRequestLedger,
    *,
    failure: SanitizedFailure | None,
) -> None:
    ledger.append(LedgerEventType.RUN_STOPPED, failure=failure)


def _terminate_after_failure(
    ledger: FsyncSSHKeyRequestLedger,
    *,
    request: SSHKeyRequestContext | None,
    failure: SanitizedFailure,
    possible_send: bool,
    fallback_elapsed_ms: int | None,
    observed_bytes: int | None = None,
    observed_http_status: int | None = None,
    observed_content_type: str | None = None,
    observed_elapsed_ms: int | None = None,
) -> None:
    if ledger.closed or ledger.tainted:
        ledger.close_preserving_incomplete()
        return
    try:
        phase = ledger.state.phase
        if request is not None and phase in {
            "intent",
            "send-started",
            "headers",
            "progress",
            "body-complete",
        }:
            if observed_bytes is not None and (
                observed_bytes < ledger.state.response_bytes or observed_bytes > MAX_RESPONSE_BYTES
            ):
                raise SSHKeyRequestLedgerError("typed failure response bytes are invalid")
            if ledger.state.response_status is None:
                if (
                    observed_http_status is not None
                    or observed_content_type is not None
                    or (observed_bytes or 0) != 0
                ):
                    raise SSHKeyRequestLedgerError(
                        "typed failure bypassed durable response headers"
                    )
            elif observed_http_status not in {
                None,
                ledger.state.response_status,
            } or observed_content_type not in {None, ledger.state.response_content_type}:
                raise SSHKeyRequestLedgerError("typed failure response identity drifted")
            if observed_elapsed_ms is not None and (
                observed_elapsed_ms < 0
                or observed_elapsed_ms > 150_000
                or (
                    ledger.state.last_elapsed_ms is not None
                    and observed_elapsed_ms < ledger.state.last_elapsed_ms
                )
            ):
                raise SSHKeyRequestLedgerError("typed failure elapsed time is invalid")
            terminal_bytes = (
                ledger.state.response_bytes if observed_bytes is None else observed_bytes
            )
            terminal_elapsed_ms = (
                observed_elapsed_ms
                if observed_elapsed_ms is not None
                else ledger.state.last_elapsed_ms or fallback_elapsed_ms
            )
            if possible_send and phase in {"send-started", "headers", "progress"}:
                ledger.append(
                    LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND,
                    request=request,
                    bytes_received=ledger.state.response_bytes,
                    http_status=ledger.state.response_status,
                    content_type=ledger.state.response_content_type,
                    elapsed_ms=terminal_elapsed_ms,
                    failure=OUTCOME_UNKNOWN_FAILURE,
                )
                failure = OUTCOME_UNKNOWN_FAILURE
            else:
                ledger.append(
                    LedgerEventType.REQUEST_FAILED,
                    request=request,
                    bytes_received=terminal_bytes,
                    http_status=ledger.state.response_status,
                    content_type=ledger.state.response_content_type,
                    elapsed_ms=terminal_elapsed_ms,
                    failure=failure,
                )
        elif phase in {"preflight-started", "secret-failed"}:
            ledger.append(LedgerEventType.RUN_PREFLIGHT_FAILED, failure=failure)
        elif phase == "response-valid":
            ledger.append(LedgerEventType.INVENTORY_VALIDATION_STARTED)
            ledger.append(LedgerEventType.INVENTORY_VALIDATION_FAILED, failure=failure)
        elif phase == "validation-started":
            ledger.append(LedgerEventType.INVENTORY_VALIDATION_FAILED, failure=failure)
        elif phase == "validation-passed":
            ledger.append(LedgerEventType.ARCHIVE_STARTED)
            ledger.append(LedgerEventType.ARCHIVE_FAILED, failure=failure)
        elif phase == "archive-started":
            ledger.append(LedgerEventType.ARCHIVE_FAILED, failure=failure)
        else:
            ledger.close_preserving_incomplete()
            return
        _append_stopped(ledger, failure=failure)
        ledger.seal(require_success=False)
    except SSHKeyRequestLedgerError:
        ledger.close_preserving_incomplete()


def execute_authorized_ssh_key_fingerprint(
    *,
    repository_root: Path,
    plan_path: Path,
    plan_sha256: str,
    run_binding: SSHKeyRunBinding,
    credential_provider: CredentialProvider,
    transport: ObservableInventoryTransport,
    archiver: SSHKeyArchiver,
    deadline_factory: DeadlineFactory = SSHKeyDeadlineWatchdog.arm,
    repository_inspector: RepositoryInspector = inspect_repository_state,
    ancestry_verifier: AncestryVerifier = verify_repository_commit_ancestry_v3,
    local_key_discoverer: LocalKeyDiscoverer = discover_local_public_keys,
    clock: Callable[[], float] = time.monotonic,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> SSHKeyRunResult:
    """Execute the exact future-authorized L1A plan once and stop before Gate L2."""

    with _armed_deadline(deadline_factory):
        return _execute_within_deadline(
            repository_root=repository_root,
            plan_path=plan_path,
            plan_sha256=plan_sha256,
            run_binding=run_binding,
            credential_provider=credential_provider,
            transport=transport,
            archiver=archiver,
            repository_inspector=repository_inspector,
            ancestry_verifier=ancestry_verifier,
            local_key_discoverer=local_key_discoverer,
            clock=clock,
            monotonic_ns=monotonic_ns,
            utc_now=utc_now,
        )


def _execute_within_deadline(
    *,
    repository_root: Path,
    plan_path: Path,
    plan_sha256: str,
    run_binding: SSHKeyRunBinding,
    credential_provider: CredentialProvider,
    transport: ObservableInventoryTransport,
    archiver: SSHKeyArchiver,
    repository_inspector: RepositoryInspector,
    ancestry_verifier: AncestryVerifier,
    local_key_discoverer: LocalKeyDiscoverer,
    clock: Callable[[], float],
    monotonic_ns: Callable[[], int],
    utc_now: Callable[[], datetime],
) -> SSHKeyRunResult:
    root = repository_root.resolve(strict=True)
    plan = load_ssh_key_fingerprint_plan(root, plan_path, expected_sha256=plan_sha256)
    if (
        run_binding.run_id != plan.run_id
        or run_binding.plan_id != plan.plan_id
        or run_binding.implementation_commit != plan.implementation_commit
    ):
        raise SSHKeyFingerprintError("Gate L1A execution binding drifted")
    started = clock()

    def check_wall() -> None:
        if clock() - started > MAX_TOTAL_WALL_SECONDS:
            raise InventoryObservedFailure(DEADLINE_FAILURE)

    ledger: FsyncSSHKeyRequestLedger | None = None
    prepared: PreparedSSHKeyArchive | None = None
    finalization: FsyncArchiveFinalizationDisposition | None = None
    snapshot: RequestLedgerSnapshot | None = None
    archived: ArchivedSSHKeyEvidence | None = None
    request_context: SSHKeyRequestContext | None = None
    request_started: float | None = None
    credential: str | None = None
    possible_send = False
    try:
        try:
            ledger = FsyncSSHKeyRequestLedger.create(
                root,
                plan=plan,
                run_binding=run_binding,
                monotonic_ns=monotonic_ns,
                utc_now=utc_now,
            )
        except SSHKeyRequestLedgerError:
            write_ssh_key_preflight_disposition(
                root,
                plan=plan,
                run_binding=run_binding,
                utc_now=utc_now,
            )
            raise
        ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
        try:
            ledger.reserve_capacity()
            repository_inspector(root, expected_commit=run_binding.repository_commit)
            ancestry_verifier(
                root,
                implementation_commit=plan.implementation_commit,
                execution_commit=run_binding.repository_commit,
            )
            check_wall()
            prepared = archiver.prepare(root, plan=plan, run_binding=run_binding)
            credential = credential_provider()
            if credential is None or credential == "":
                ledger.append(
                    LedgerEventType.SECRET_PRESENCE_CHECK_FAILED,
                    failure=SECRET_MISSING_FAILURE,
                )
                raise InventoryObservedFailure(SECRET_MISSING_FAILURE)
            if len(credential) > 4096 or any(
                marker in credential for marker in ("\r", "\n", "\x00")
            ):
                ledger.append(
                    LedgerEventType.SECRET_PRESENCE_CHECK_FAILED,
                    failure=SECRET_MALFORMED_FAILURE,
                )
                raise InventoryObservedFailure(SECRET_MALFORMED_FAILURE)
            ledger.append(LedgerEventType.SECRET_PRESENCE_CHECK_PASSED)
            ledger.append(LedgerEventType.RUN_PREFLIGHT_PASSED)
        except (SSHKeyRequestLedgerError, InventoryObservedFailure):
            raise
        except Exception:
            raise InventoryObservedFailure(PREFLIGHT_FAILURE) from None

        request_context = SSHKeyRequestContext()
        request_started = clock()
        ledger.append(LedgerEventType.REQUEST_INTENT_COMMITTED, request=request_context)
        ledger.append(LedgerEventType.REQUEST_SEND_STARTED, request=request_context)
        possible_send = True
        observer = _LedgerObserver(ledger, request_context)
        transport_request = cast(InventoryRequest, _TransportRequest())
        response = transport.fetch(
            transport_request,
            credential=credential,
            timeout_seconds=MAX_PROVIDER_WALL_SECONDS,
            observer=observer,
        )
        credential = None
        if (
            not observer.headers_seen
            or response.status_code != 200
            or response.content_type != "application/json"
            or response.status_code != observer.status_code
            or response.content_type != observer.content_type
            or len(response.body) > MAX_RESPONSE_BYTES
        ):
            raise InventoryObservedFailure(
                SCHEMA_FAILURE,
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
            projection = project_account_ssh_keys(response.body)
        except SSHKeyFingerprintError:
            raise InventoryObservedFailure(
                SCHEMA_FAILURE,
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
        possible_send = False
        ledger.append(LedgerEventType.INVENTORY_VALIDATION_STARTED)
        try:
            match = match_account_to_local_keys(projection, local_key_discoverer())
            validate_sanitized_report(match.sanitized_report, repository_root=root)
            bundle = write_local_evidence_bundle(
                root,
                raw_response=response.body,
                result=match,
            )
        except SSHKeyFingerprintError:
            raise InventoryObservedFailure(MATCH_FAILURE) from None
        ledger.append(LedgerEventType.INVENTORY_VALIDATION_PASSED)
        ledger.append(LedgerEventType.ARCHIVE_STARTED)
        try:
            prepared.stage(bundle)
        except (InventoryArchiveError, OSError):
            raise InventoryObservedFailure(ARCHIVE_FAILURE) from None
        try:
            finalization_writer = FsyncArchiveFinalizationDisposition.create(
                root,
                plan=plan,
                run_binding=run_binding,
                monotonic_ns=monotonic_ns,
                utc_now=utc_now,
            )
            finalization = finalization_writer
        except (InventoryArchiveError, OSError):
            raise InventoryObservedFailure(ARCHIVE_FAILURE) from None
        # In this request ledger, archive_passed means that all source evidence
        # was durably staged and the separate post-ledger finalization journal
        # exists.  Only that journal can attest overall archive completion.
        ledger.append(LedgerEventType.ARCHIVE_PASSED)
        _append_stopped(ledger, failure=None)
        terminal_snapshot = ledger.seal(require_success=True)
        snapshot = terminal_snapshot
        check_wall()
        try:
            archived_result = prepared.finalize(bundle, ledger=terminal_snapshot)
            archived = archived_result
            completion = finalization_writer.record_passed(
                archived=archived_result,
                ledger=terminal_snapshot,
            )
        except (InventoryArchiveError, SSHKeyFingerprintError, OSError):
            if not finalization_writer.closed:
                with contextlib.suppress(InventoryArchiveError):
                    finalization_writer.record_failed(
                        stable_error_code="L1A_ARCHIVE_FINALIZATION_FAILED",
                        ledger=terminal_snapshot,
                        archived=archived,
                    )
            raise InventoryObservedFailure(ARCHIVE_FAILURE) from None
        check_wall()
        return SSHKeyRunResult(
            run_id=RUN_ID,
            authorization_reference=run_binding.authorization_reference,
            provider_calls=1,
            projection=projection,
            match=match,
            bundle=bundle,
            ledger=terminal_snapshot,
            archive=archived_result,
            archive_finalization=completion,
        )
    except SSHKeyRequestLedgerError:
        if finalization is not None and not finalization.closed:
            with contextlib.suppress(InventoryArchiveError):
                finalization.record_failed(
                    stable_error_code="L1A_TERMINAL_LEDGER_FAILED",
                    ledger=snapshot,
                    archived=archived,
                )
        if ledger is not None:
            ledger.close_preserving_incomplete()
        raise
    except InventoryObservedFailure as error:
        if finalization is not None and not finalization.closed:
            with contextlib.suppress(InventoryArchiveError):
                finalization.record_failed(
                    stable_error_code="L1A_ARCHIVE_FINALIZATION_FAILED",
                    ledger=snapshot,
                    archived=archived,
                )
        if ledger is not None:
            elapsed_ms = (
                None
                if request_started is None
                else max(0, min(30_000, int((clock() - request_started) * 1000)))
            )
            _terminate_after_failure(
                ledger,
                request=request_context,
                failure=error.failure,
                # A typed InventoryObservedFailure is itself the durable,
                # closed-category observation of the network outcome.  Only
                # an unexpected exception after send has unknown outcome.
                possible_send=False,
                fallback_elapsed_ms=elapsed_ms,
                observed_bytes=error.bytes_received,
                observed_http_status=error.http_status,
                observed_content_type=error.content_type,
                observed_elapsed_ms=error.elapsed_ms,
            )
        raise
    except BaseException:
        if finalization is not None and not finalization.closed:
            with contextlib.suppress(InventoryArchiveError):
                finalization.record_failed(
                    stable_error_code="L1A_ARCHIVE_DISPOSITION_FAILED",
                    ledger=snapshot,
                    archived=archived,
                )
        if ledger is not None:
            elapsed_ms = (
                None
                if request_started is None
                else max(0, min(30_000, int((clock() - request_started) * 1000)))
            )
            _terminate_after_failure(
                ledger,
                request=request_context,
                failure=PRESEND_FAILURE,
                possible_send=possible_send,
                fallback_elapsed_ms=elapsed_ms,
            )
        raise InventoryObservedFailure(PRESEND_FAILURE) from None
    finally:
        credential = None
        if prepared is not None:
            with contextlib.suppress(Exception):
                prepared.close()
        if finalization is not None:
            finalization.close_preserving_incomplete()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--authorization-reference", required=True)
    parser.add_argument("--authorization-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] == "_deadline-watchdog":
        return _deadline_watchdog_main(raw[1:])
    args = _parser().parse_args(raw)
    binding = SSHKeyRunBinding(
        repository_commit=args.expected_commit,
        implementation_commit=args.implementation_commit,
        authorization_reference=args.authorization_reference,
        authorization_sha256=args.authorization_sha256,
    )
    try:
        result = execute_authorized_ssh_key_fingerprint(
            repository_root=args.repository_root,
            plan_path=args.plan,
            plan_sha256=args.plan_sha256,
            run_binding=binding,
            credential_provider=lambda: os.environ.get("LAMBDA_API_KEY"),
            transport=LambdaHttpsInventoryTransportV3(),
            archiver=DurableSSHKeyArchiver(),
        )
    except (
        InventoryArchiveError,
        InventoryObservedFailure,
        LambdaCloudContractError,
        SSHKeyFingerprintError,
        OSError,
        ValueError,
    ):
        print(
            "giclab-lambda-ssh-key: stopped; inspect the secret-safe L1A ledger",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "authorization_reference": result.authorization_reference,
                "provider_calls": result.provider_calls,
                "ledger_path": str(result.ledger.path),
                "ledger_sha256": result.ledger.sha256,
                "sanitized_report_path": result.bundle.sanitized_report.relative_path,
                "sanitized_report_sha256": result.bundle.sanitized_report.sha256,
                "archive_path": str(result.archive.destination),
                "archive_seal_sha256": result.archive.seal_sha256,
                "archive_copy_record_sha256": result.archive.copy_record_sha256,
                "archive_finalization_path": str(result.archive_finalization.path),
                "archive_finalization_sha256": result.archive_finalization.sha256,
                "archive_finalization_state": result.archive_finalization.state,
                "gate_l1a_evidence_complete": (
                    result.archive_finalization.gate_l1a_evidence_complete
                ),
                "selection_state": result.match.sanitized_report["selection_state"],
                "recommended_account_key_name": result.match.sanitized_report[
                    "recommended_account_key_name"
                ],
                "selection_authorized": False,
                "gate_l2_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
