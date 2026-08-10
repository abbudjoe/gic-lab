"""Offline separate-session watchdog primitives for T07 Lambda Gate L2.1.

The draft bootstrap uses anonymous pipes for credential/liveness/readiness and models
a double-fork into a new session. It has no integrated live entrypoint or authoritative
provider-cleanup runner. Tests exercise only deterministic primitives with fakes;
importing this module starts no process and makes no request.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import signal
import stat
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol

from jsonschema import Draft202012Validator

from .lambda_l2_ownership import DiscoveryKind, DiscoveryResult
from .lambda_l2_supervisor import (
    MAX_HEARTBEAT_BYTES,
    MAX_HEARTBEAT_EVENTS,
    MAX_WATCHDOG_BYTES,
    MAX_WATCHDOG_EVENT_BYTES,
    MAX_WATCHDOG_EVENTS,
    TERMINAL_DECISION,
    WATCHDOG_HEARTBEAT_SECONDS,
    WATCHDOG_PROVIDER_ALLOWLIST,
    WATCHDOG_STALE_SECONDS,
    Actor,
    BudgetState,
    ExecutionBinding,
    ProviderCall,
    ProviderResult,
    SharedBudget,
    canonical_bytes,
    sha256_bytes,
    validate_provider_call,
)


class WatchdogContractError(ValueError):
    """The watchdog cannot prove a safe cleanup transition."""


WATCHDOG_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-watchdog-journal.schema.json"
MAX_CREDENTIAL_BYTES: Final = 4_096
PRIMARY_TERM_GRACE_SECONDS: Final = 5
PRIMARY_KILL_GRACE_SECONDS: Final = 5
MUTATION_LEASE_WAIT_SECONDS: Final = 15
READINESS_MESSAGE: Final = b"T07-WATCHDOG-READY\n"
_SAFE_ALIAS = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def watchdog_bootstrap_contract() -> dict[str, object]:
    """Return the exact source-grounded no-persistence bootstrap contract."""

    return {
        "mechanism": "darwin-separate-session-double-fork",
        "credential_channel": "anonymous-length-prefixed-pipe",
        "liveness_channel": "anonymous-pipe-eof",
        "readiness_channel": "anonymous-pipe",
        "secret_in_argv": False,
        "secret_in_environment": False,
        "secret_on_disk": False,
        "setsid": True,
        "double_fork": True,
        "launchd_selected": False,
        "launchd_rejection_reason": (
            "a restartable transient job cannot reacquire the nonpersisted provider "
            "credential after simultaneous primary/watchdog failure"
        ),
        "watchdog_launch_allowed": False,
        "watchdog_ssh_allowed": False,
        "watchdog_workload_allowed": False,
        "heartbeat_seconds": WATCHDOG_HEARTBEAT_SECONDS,
        "stale_seconds": WATCHDOG_STALE_SECONDS,
        "primary_term_grace_seconds": PRIMARY_TERM_GRACE_SECONDS,
        "primary_kill_grace_seconds": PRIMARY_KILL_GRACE_SECONDS,
        "mutation_lease_wait_seconds": MUTATION_LEASE_WAIT_SECONDS,
        "known_limits": [
            "mac_power_loss",
            "local_network_loss",
            "lambda_api_outage",
            "lambda_console_outage",
            "simultaneous_primary_watchdog_failure",
        ],
    }


class WatchdogEvent(StrEnum):
    BOOTSTRAP_STARTED = "watchdog_bootstrap_started"
    CREDENTIAL_RECEIVED = "watchdog_credential_received"
    READY = "watchdog_ready"
    HEARTBEAT_OBSERVED = "primary_heartbeat_observed"
    HEARTBEAT_STALE = "primary_heartbeat_stale"
    PRIMARY_TERM_SENT = "primary_term_sent"
    PRIMARY_KILL_SENT = "primary_kill_sent"
    PRIMARY_EXIT_OBSERVED = "primary_exit_observed"
    MUTATION_LEASE_ACQUIRED = "mutation_lease_acquired"
    DISCOVERY_STARTED = "watchdog_discovery_started"
    OWNED_MATCHES_FOUND = "watchdog_owned_matches_found"
    PROVIDER_INTENT = "watchdog_provider_intent"
    PROVIDER_SEND_STARTED = "watchdog_provider_send_started"
    PROVIDER_RESPONSE_RECEIVED = "watchdog_provider_response_received"
    PROVIDER_FAILED = "watchdog_provider_failed"
    INSTANCE_TERMINAL = "watchdog_instance_terminal"
    REGIONAL_RULESET_DELETED = "watchdog_regional_ruleset_deleted"
    GLOBAL_FIREWALL_RESTORED = "watchdog_global_firewall_restored"
    ALL_CLEAN = "watchdog_all_clean"
    INCIDENT_SEALED = "watchdog_incident_sealed"
    STOPPED = "watchdog_stopped"


class WatchdogPhase(StrEnum):
    NEW = "new"
    READY = "ready"
    MONITORING = "monitoring"
    PRIMARY_STALE = "primary_stale"
    TAKEOVER = "takeover"
    DISCOVERY = "discovery"
    TERMINATING = "terminating"
    TERMINAL = "terminal"
    FIREWALL_RESTORED = "firewall_restored"
    CLOSED = "closed"
    INCIDENT = "incident"


@dataclass(frozen=True, slots=True)
class WatchdogState:
    phase: WatchdogPhase = WatchdogPhase.NEW
    last_heartbeat_monotonic_ns: int | None = None
    primary_exit_observed: bool = False
    mutation_lease_acquired: bool = False
    owned_instance_ids: tuple[str, ...] = ()
    terminal_instance_ids: tuple[str, ...] = ()
    regional_ruleset_deleted: bool = False
    global_firewall_restored: bool = False
    incident_class: str | None = None


@dataclass(frozen=True, slots=True)
class WatchdogJournalSnapshot:
    path: Path
    bytes: int
    events: int
    sha256: str


class FsyncWatchdogJournal:
    """Exclusive, append-only, schema-validated watchdog evidence stream."""

    def __init__(
        self,
        *,
        path: Path,
        descriptor: int,
        binding: ExecutionBinding,
        validator: Draft202012Validator,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.path = path
        self.descriptor = descriptor
        self.binding = binding
        self.validator = validator
        self.monotonic_ns = monotonic_ns
        self.utc_now = utc_now
        self.sequence = 1
        self.events = 0
        self.bytes_written = 0
        self.closed = False

    @classmethod
    def create(
        cls,
        repository_root: Path,
        *,
        path: Path,
        binding: ExecutionBinding,
    ) -> FsyncWatchdogJournal:
        root = repository_root.resolve(strict=True)
        target = path.absolute()
        try:
            target.relative_to(root)
        except ValueError:
            raise WatchdogContractError("watchdog journal escaped the repository") from None
        if not target.parent.is_dir() or target.is_symlink():
            raise WatchdogContractError("watchdog journal parent is unsafe")
        try:
            schema = json.loads((root / WATCHDOG_SCHEMA_PATH).read_bytes())
            validator = Draft202012Validator(schema)
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            parent = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except (OSError, json.JSONDecodeError):
            raise WatchdogContractError("watchdog journal creation failed") from None
        return cls(
            path=target,
            descriptor=descriptor,
            binding=binding,
            validator=validator,
        )

    def append(
        self,
        event: WatchdogEvent,
        *,
        resource_alias: str,
        terminal_status: str,
        budget: BudgetState,
        request_ordinal: int | None = None,
        elapsed_ms: int = 0,
        response_bytes: int = 0,
        failure_class: str | None = None,
    ) -> None:
        if self.closed or _SAFE_ALIAS.fullmatch(resource_alias) is None:
            raise WatchdogContractError("watchdog journal is closed or alias is unsafe")
        document = {
            "schema_version": "0.1.0",
            "run_id": self.binding.run_id,
            "plan_id": self.binding.plan_id,
            "authorization_reference": self.binding.authorization_reference,
            "actor": Actor.WATCHDOG.value,
            "event_sequence": self.sequence,
            "event_type": event.value,
            "request_ordinal": request_ordinal,
            "resource_alias": resource_alias,
            "private_parameter_seal_reference": (self.binding.private_parameter_seal_reference),
            "monotonic_timestamp_ns": self.monotonic_ns(),
            "wall_timestamp_utc": self.utc_now().isoformat().replace("+00:00", "Z"),
            "elapsed_ms": elapsed_ms,
            "response_bytes": response_bytes,
            "provider_calls_used": budget.provider_calls,
            "process_calls_used": budget.process_calls,
            "output_bytes_used": (budget.provider_response_bytes + budget.process_output_bytes),
            "terminal_status": terminal_status,
            "sanitized_failure_class": failure_class,
        }
        if list(self.validator.iter_errors(document)):
            raise WatchdogContractError("watchdog event failed schema validation")
        encoded = canonical_bytes(document)
        if (
            len(encoded) > MAX_WATCHDOG_EVENT_BYTES
            or self.events + 1 > MAX_WATCHDOG_EVENTS
            or self.bytes_written + len(encoded) > MAX_WATCHDOG_BYTES
        ):
            raise WatchdogContractError("watchdog journal capacity exceeded")
        try:
            if os.write(self.descriptor, encoded) != len(encoded):
                raise OSError("short write")
            os.fsync(self.descriptor)
        except OSError:
            raise WatchdogContractError("watchdog journal fsync failed") from None
        self.sequence += 1
        self.events += 1
        self.bytes_written += len(encoded)

    def snapshot(self) -> WatchdogJournalSnapshot:
        os.fsync(self.descriptor)
        encoded = self.path.read_bytes()
        if len(encoded) != self.bytes_written:
            raise WatchdogContractError("watchdog journal byte count drifted")
        return WatchdogJournalSnapshot(
            self.path,
            len(encoded),
            self.events,
            sha256_bytes(encoded),
        )

    def close(self) -> None:
        if self.descriptor >= 0:
            os.fsync(self.descriptor)
            os.close(self.descriptor)
            self.descriptor = -1
        self.closed = True


class FsyncHeartbeatWriter:
    """Separate bounded append-only primary heartbeat record."""

    def __init__(self, path: Path, descriptor: int) -> None:
        self.path = path
        self.descriptor = descriptor
        self.sequence = 1
        self.bytes_written = 0

    @classmethod
    def create(cls, path: Path) -> FsyncHeartbeatWriter:
        if not path.parent.is_dir() or path.is_symlink():
            raise WatchdogContractError("heartbeat path is unsafe")
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except OSError:
            raise WatchdogContractError("heartbeat creation failed") from None
        return cls(path, descriptor)

    def beat(self, monotonic_timestamp_ns: int) -> None:
        if self.sequence > MAX_HEARTBEAT_EVENTS or monotonic_timestamp_ns < 0:
            raise WatchdogContractError("heartbeat event cap or timestamp failed")
        encoded = canonical_bytes(
            {
                "schema_version": "0.1.0",
                "sequence": self.sequence,
                "monotonic_timestamp_ns": monotonic_timestamp_ns,
            }
        )
        if self.bytes_written + len(encoded) > MAX_HEARTBEAT_BYTES:
            raise WatchdogContractError("heartbeat byte cap exceeded")
        try:
            if os.write(self.descriptor, encoded) != len(encoded):
                raise OSError("short write")
            os.fsync(self.descriptor)
        except OSError:
            raise WatchdogContractError("heartbeat fsync failed") from None
        self.sequence += 1
        self.bytes_written += len(encoded)

    def close(self) -> None:
        if self.descriptor >= 0:
            os.fsync(self.descriptor)
            os.close(self.descriptor)
            self.descriptor = -1


def read_last_heartbeat(path: Path) -> tuple[int, int]:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            status = os.fstat(descriptor)
            if not stat.S_ISREG(status.st_mode) or status.st_size > MAX_HEARTBEAT_BYTES:
                raise WatchdogContractError("heartbeat record is unsafe")
            encoded = os.read(descriptor, MAX_HEARTBEAT_BYTES + 1)
        finally:
            os.close(descriptor)
        lines = encoded.splitlines()
        if not lines or len(lines) > MAX_HEARTBEAT_EVENTS:
            raise WatchdogContractError("heartbeat record is empty or over cap")
        expected = 1
        last_timestamp = -1
        for line in lines:
            document = json.loads(line)
            if (
                not isinstance(document, dict)
                or set(document) != {"schema_version", "sequence", "monotonic_timestamp_ns"}
                or document.get("schema_version") != "0.1.0"
                or document.get("sequence") != expected
                or type(document.get("monotonic_timestamp_ns")) is not int
                or int(document["monotonic_timestamp_ns"]) <= last_timestamp
            ):
                raise WatchdogContractError("heartbeat order or shape drifted")
            last_timestamp = int(document["monotonic_timestamp_ns"])
            expected += 1
        return expected - 1, last_timestamp
    except (OSError, json.JSONDecodeError):
        raise WatchdogContractError("heartbeat record is unreadable") from None


class MutationLease:
    """Kernel-released flock that excludes primary/watchdog cloud mutation races."""

    def __init__(self, path: Path, descriptor: int) -> None:
        self.path = path
        self.descriptor = descriptor
        self.held = False

    @classmethod
    def create_primary(cls, path: Path) -> MutationLease:
        try:
            descriptor = os.open(
                path,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except OSError:
            raise WatchdogContractError("mutation lease creation failed") from None
        lease = cls(path, descriptor)
        lease.acquire(blocking=False)
        return lease

    @classmethod
    def open_watchdog(cls, path: Path) -> MutationLease:
        try:
            descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        except OSError:
            raise WatchdogContractError("watchdog mutation lease open failed") from None
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            os.close(descriptor)
            raise WatchdogContractError("mutation lease is not a regular file")
        return cls(path, descriptor)

    def acquire(self, *, blocking: bool) -> bool:
        operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(self.descriptor, operation)
        except BlockingIOError:
            return False
        self.held = True
        return True

    def release(self) -> None:
        if self.held:
            fcntl.flock(self.descriptor, fcntl.LOCK_UN)
            self.held = False

    def close(self) -> None:
        self.release()
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1


class PrimaryControl(Protocol):
    def has_exited(self) -> bool: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


class PipePrimaryControl:
    """Track the original primary by inherited EOF and signal it only while alive."""

    def __init__(self, *, primary_pid: int, liveness_read_fd: int) -> None:
        if primary_pid <= 1:
            raise WatchdogContractError("primary PID is invalid")
        self.primary_pid = primary_pid
        self.liveness_read_fd = liveness_read_fd
        os.set_blocking(liveness_read_fd, False)

    def has_exited(self) -> bool:
        try:
            return os.read(self.liveness_read_fd, 1) == b""
        except BlockingIOError:
            return False

    def terminate(self) -> None:
        if not self.has_exited():
            os.kill(self.primary_pid, signal.SIGTERM)

    def kill(self) -> None:
        if not self.has_exited():
            os.kill(self.primary_pid, signal.SIGKILL)


@dataclass(slots=True)
class WatchdogHandle:
    """Primary-side anonymous handles; credential bytes never enter repr."""

    watchdog_pid: int
    credential_write_fd: int = field(repr=False)
    liveness_write_fd: int = field(repr=False)
    readiness_read_fd: int = field(repr=False)

    def deliver_credential(self, credential: bytearray) -> None:
        if not 0 < len(credential) <= MAX_CREDENTIAL_BYTES:
            raise WatchdogContractError("watchdog credential length is invalid")
        frame = len(credential).to_bytes(4, "big") + bytes(credential)
        try:
            if os.write(self.credential_write_fd, frame) != len(frame):
                raise OSError("short write")
        except OSError:
            raise WatchdogContractError("watchdog credential pipe write failed") from None
        finally:
            os.close(self.credential_write_fd)
            self.credential_write_fd = -1
            for index in range(len(credential)):
                credential[index] = 0

    def wait_ready(self, *, timeout_seconds: float = 15) -> None:
        deadline = time.monotonic() + timeout_seconds
        os.set_blocking(self.readiness_read_fd, False)
        received = bytearray()
        while time.monotonic() < deadline:
            try:
                chunk = os.read(self.readiness_read_fd, 64)
            except BlockingIOError:
                time.sleep(0.01)
                continue
            if not chunk:
                break
            received.extend(chunk)
            if bytes(received) == READINESS_MESSAGE:
                return
        raise WatchdogContractError("watchdog readiness proof timed out")

    def close_liveness(self) -> None:
        if self.liveness_write_fd >= 0:
            os.close(self.liveness_write_fd)
            self.liveness_write_fd = -1


@dataclass(frozen=True, slots=True)
class WatchdogChildBootstrap:
    credential_read_fd: int = field(repr=False)
    liveness_read_fd: int = field(repr=False)
    readiness_write_fd: int = field(repr=False)
    primary_pid: int


WatchdogEntrypoint = Callable[[WatchdogChildBootstrap], int]


def spawn_separate_session_watchdog(entrypoint: WatchdogEntrypoint) -> WatchdogHandle:
    """Retired concrete bootstrap; fake-only watchdog policy remains inspectable."""

    raise WatchdogContractError(f"{TERMINAL_DECISION} blocks the concrete Gate L2 watchdog spawn")

    credential_read, credential_write = os.pipe()
    liveness_read, liveness_write = os.pipe()
    readiness_read, readiness_write = os.pipe()
    pid_read, pid_write = os.pipe()
    primary_pid = os.getpid()
    first_pid = os.fork()
    if first_pid == 0:  # pragma: no cover - exercised only by a future authorized run
        try:
            os.close(credential_write)
            os.close(liveness_write)
            os.close(readiness_read)
            os.close(pid_read)
            os.setsid()
            second_pid = os.fork()
            if second_pid > 0:
                os.write(pid_write, f"{second_pid}\n".encode("ascii"))
                os._exit(0)
            os.close(pid_write)
            code = entrypoint(
                WatchdogChildBootstrap(
                    credential_read,
                    liveness_read,
                    readiness_write,
                    primary_pid,
                )
            )
            os._exit(code)
        except BaseException:
            os._exit(111)
    os.close(credential_read)
    os.close(liveness_read)
    os.close(readiness_write)
    os.close(pid_write)
    try:
        encoded_pid = os.read(pid_read, 32)
        os.waitpid(first_pid, 0)
        watchdog_pid = int(encoded_pid.strip())
    except (OSError, ValueError):
        raise WatchdogContractError("watchdog double-fork bootstrap failed") from None
    finally:
        os.close(pid_read)
    return WatchdogHandle(watchdog_pid, credential_write, liveness_write, readiness_read)


def read_watchdog_credential(descriptor: int) -> bytearray:
    """Read exactly one length-prefixed credential from the anonymous pipe."""

    header = os.read(descriptor, 4)
    if len(header) != 4:
        raise WatchdogContractError("watchdog credential frame header is incomplete")
    length = int.from_bytes(header, "big")
    if not 0 < length <= MAX_CREDENTIAL_BYTES:
        raise WatchdogContractError("watchdog credential frame length is invalid")
    value = bytearray()
    while len(value) < length:
        chunk = os.read(descriptor, length - len(value))
        if not chunk:
            raise WatchdogContractError("watchdog credential frame is truncated")
        value.extend(chunk)
    if os.read(descriptor, 1) != b"":
        raise WatchdogContractError("watchdog credential pipe contains trailing bytes")
    return value


class WatchdogProviderBoundary(Protocol):
    def send(
        self,
        call: ProviderCall,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> ProviderResult: ...


class GateL2Watchdog:
    """Cleanup-only state machine activated after durable stale-primary proof."""

    def __init__(
        self,
        *,
        binding: ExecutionBinding,
        journal: FsyncWatchdogJournal,
        budget: SharedBudget,
    ) -> None:
        if journal.binding != binding:
            raise WatchdogContractError("watchdog binding differs from its journal")
        self.binding = binding
        self.journal = journal
        self.budget = budget
        self.state = WatchdogState()
        self.request_ordinal = 0
        self._event(
            WatchdogEvent.BOOTSTRAP_STARTED,
            alias="cleanup-watchdog",
            status="starting",
        )

    def _event(
        self,
        event: WatchdogEvent,
        *,
        alias: str,
        status: str,
        request_ordinal: int | None = None,
        elapsed_ms: int = 0,
        response_bytes: int = 0,
        failure: str | None = None,
    ) -> None:
        self.journal.append(
            event,
            resource_alias=alias,
            terminal_status=status,
            budget=self.budget.state,
            request_ordinal=request_ordinal,
            elapsed_ms=elapsed_ms,
            response_bytes=response_bytes,
            failure_class=failure,
        )

    def mark_ready(self) -> None:
        if self.state.phase is not WatchdogPhase.NEW:
            raise WatchdogContractError("watchdog readiness may occur exactly once")
        self.state = replace(self.state, phase=WatchdogPhase.READY)
        self._event(WatchdogEvent.READY, alias="cleanup-watchdog", status="ready")

    def observe_heartbeat(self, monotonic_timestamp_ns: int) -> None:
        if self.state.phase not in {WatchdogPhase.READY, WatchdogPhase.MONITORING}:
            raise WatchdogContractError("heartbeat observation order drifted")
        if monotonic_timestamp_ns < 0 or (
            self.state.last_heartbeat_monotonic_ns is not None
            and monotonic_timestamp_ns <= self.state.last_heartbeat_monotonic_ns
        ):
            raise WatchdogContractError("heartbeat timestamp is stale or reordered")
        self.state = replace(
            self.state,
            phase=WatchdogPhase.MONITORING,
            last_heartbeat_monotonic_ns=monotonic_timestamp_ns,
        )
        self._event(
            WatchdogEvent.HEARTBEAT_OBSERVED,
            alias="primary-supervisor",
            status="alive",
        )

    def mark_stale(self, *, now_monotonic_ns: int) -> None:
        last = self.state.last_heartbeat_monotonic_ns
        if (
            self.state.phase is not WatchdogPhase.MONITORING
            or last is None
            or now_monotonic_ns - last < WATCHDOG_STALE_SECONDS * 1_000_000_000
        ):
            raise WatchdogContractError("primary heartbeat is not durably stale")
        self.state = replace(self.state, phase=WatchdogPhase.PRIMARY_STALE)
        self._event(
            WatchdogEvent.HEARTBEAT_STALE,
            alias="primary-supervisor",
            status="stale",
        )

    def take_over(self, *, primary: PrimaryControl, lease: MutationLease) -> None:
        if self.state.phase is not WatchdogPhase.PRIMARY_STALE:
            raise WatchdogContractError("watchdog takeover lacks stale-heartbeat proof")
        if not primary.has_exited():
            primary.terminate()
            self._event(
                WatchdogEvent.PRIMARY_TERM_SENT,
                alias="primary-supervisor",
                status="term_sent",
            )
        if not primary.has_exited():
            primary.kill()
            self._event(
                WatchdogEvent.PRIMARY_KILL_SENT,
                alias="primary-supervisor",
                status="kill_sent",
            )
        if not primary.has_exited():
            self.raise_incident("primary_exit_not_observed")
            raise WatchdogContractError("primary did not exit before watchdog mutation")
        self._event(
            WatchdogEvent.PRIMARY_EXIT_OBSERVED,
            alias="primary-supervisor",
            status="exited",
        )
        if not lease.acquire(blocking=False):
            self.raise_incident("mutation_lease_unavailable")
            raise WatchdogContractError("primary/watchdog mutation exclusion is unresolved")
        self.state = replace(
            self.state,
            phase=WatchdogPhase.TAKEOVER,
            primary_exit_observed=True,
            mutation_lease_acquired=True,
        )
        self._event(
            WatchdogEvent.MUTATION_LEASE_ACQUIRED,
            alias="mutation-lease",
            status="watchdog_owned",
        )

    def begin_discovery(self) -> None:
        if self.state.phase is not WatchdogPhase.TAKEOVER or not self.state.mutation_lease_acquired:
            raise WatchdogContractError("watchdog discovery lacks exclusive takeover")
        self.state = replace(self.state, phase=WatchdogPhase.DISCOVERY)
        self._event(
            WatchdogEvent.DISCOVERY_STARTED,
            alias="owned-launch",
            status="discovery_only",
        )

    def apply_discovery(self, result: DiscoveryResult, *, approve_duplicates: bool) -> None:
        if self.state.phase is not WatchdogPhase.DISCOVERY:
            raise WatchdogContractError("watchdog discovery result order drifted")
        if result.kind is DiscoveryKind.ZERO_MATCHES:
            return
        if result.kind in {DiscoveryKind.PARTIAL_MARKER, DiscoveryKind.CONFLICTING_DETAILS}:
            self.raise_incident(result.kind.value)
            return
        if result.kind is DiscoveryKind.MULTIPLE_FULL_MATCHES and not approve_duplicates:
            self.raise_incident("duplicate_termination_not_approved")
            return
        if not result.full_match_ids or len(result.full_match_ids) > 4:
            self.raise_incident("owned_match_count_outside_cap")
            return
        self.state = replace(
            self.state,
            phase=WatchdogPhase.TERMINATING,
            owned_instance_ids=result.full_match_ids,
        )
        self._event(
            WatchdogEvent.OWNED_MATCHES_FOUND,
            alias="owned-instances",
            status="detail_revalidation_required",
        )

    def reserve_provider_call(self, call: ProviderCall) -> None:
        validate_provider_call(call)
        if call.operation not in WATCHDOG_PROVIDER_ALLOWLIST:
            raise WatchdogContractError("watchdog cannot launch, preflight, or widen access")
        self.request_ordinal += 1
        self.budget.reserve_provider(call.operation, actor=Actor.WATCHDOG)
        self._event(
            WatchdogEvent.PROVIDER_INTENT,
            alias="cleanup-provider-call",
            status="committed",
            request_ordinal=self.request_ordinal,
        )
        self._event(
            WatchdogEvent.PROVIDER_SEND_STARTED,
            alias="cleanup-provider-call",
            status="outcome_unknown",
            request_ordinal=self.request_ordinal,
        )

    def record_terminal(self, instance_id: str, status: str) -> None:
        if self.state.phase is not WatchdogPhase.TERMINATING:
            raise WatchdogContractError("watchdog terminal proof order drifted")
        if instance_id not in self.state.owned_instance_ids or status not in {
            "terminated",
            "absent_after_termination",
        }:
            raise WatchdogContractError("watchdog terminal proof is not exact")
        terminal = tuple(dict.fromkeys((*self.state.terminal_instance_ids, instance_id)))
        phase = (
            WatchdogPhase.TERMINAL
            if set(terminal) == set(self.state.owned_instance_ids)
            else WatchdogPhase.TERMINATING
        )
        self.state = replace(self.state, phase=phase, terminal_instance_ids=terminal)
        self._event(
            WatchdogEvent.INSTANCE_TERMINAL,
            alias="owned-instance",
            status=status,
        )

    def restore_firewall(self) -> None:
        if self.state.phase is not WatchdogPhase.TERMINAL or set(
            self.state.terminal_instance_ids
        ) != set(self.state.owned_instance_ids):
            raise WatchdogContractError("watchdog firewall restore lacks terminal proof")
        self.state = replace(
            self.state,
            phase=WatchdogPhase.FIREWALL_RESTORED,
            regional_ruleset_deleted=True,
            global_firewall_restored=True,
        )
        self._event(
            WatchdogEvent.REGIONAL_RULESET_DELETED,
            alias="owned-regional-ruleset",
            status="absent",
        )
        self._event(
            WatchdogEvent.GLOBAL_FIREWALL_RESTORED,
            alias="global-firewall",
            status="exactly_restored",
        )

    def close_clean(self) -> None:
        if (
            self.state.phase is not WatchdogPhase.FIREWALL_RESTORED
            or not self.state.regional_ruleset_deleted
            or not self.state.global_firewall_restored
        ):
            raise WatchdogContractError("watchdog all-clean evidence is incomplete")
        self.state = replace(self.state, phase=WatchdogPhase.CLOSED)
        self._event(
            WatchdogEvent.ALL_CLEAN,
            alias="gate-l2-run",
            status="all_clean",
        )
        self._event(
            WatchdogEvent.STOPPED,
            alias="cleanup-watchdog",
            status="closed",
        )

    def raise_incident(self, incident_class: str) -> None:
        if not incident_class or len(incident_class) > 96:
            raise WatchdogContractError("watchdog incident class is invalid")
        self.state = replace(
            self.state,
            phase=WatchdogPhase.INCIDENT,
            incident_class=incident_class,
        )
        self._event(
            WatchdogEvent.INCIDENT_SEALED,
            alias="gate-l2-run",
            status="possible_orphaned_launch",
            failure=incident_class,
        )


def zero_secret_buffer(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


def close_watchdog_descriptors(*descriptors: int) -> None:
    for descriptor in descriptors:
        if descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(descriptor)
