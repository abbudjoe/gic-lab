"""Authorized, shell-free, evidence-preserving local subprocess execution."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, BinaryIO

from .adapters.base import NormalizationResult
from .artifacts import (
    ARTIFACT_RECORDS,
    COMMAND_RECORD,
    EVENT_STREAM,
    RUN_PLAN_RECORD,
    ArtifactRecordWriter,
    ArtifactWorkspace,
    artifact_document,
    artifact_record,
    sha256_file,
)
from .budget import BudgetExceeded, BudgetGuard
from .events import JsonlEventWriter, event_document
from .models import (
    BudgetUsage,
    CommandSpec,
    EventProvenance,
    EventType,
    ExecutionBackend,
    HarnessEvent,
    JsonValue,
    NonWallResourceAccounting,
    NormalizedEvent,
    RunPlan,
    command_document,
    command_sha256,
    thaw_json,
)
from .plan import run_plan_document
from .policy import (
    ExecutionDisallowed,
    ProjectExecutionState,
    assert_execution_allowed,
    execution_blockers,
)
from .safety import CredentialExposureError, ExactCredentialScrubber


class LocalExecutionError(RuntimeError):
    """Raised after preserving available evidence for an operational run failure."""

    def __init__(self, message: str, *, session: RunSession | None = None) -> None:
        super().__init__(message)
        self.session = session


class ResourceProjectionExceeded(RuntimeError):
    """Raised when observed adapter use violates its authorized preflight projection."""


@dataclass(frozen=True, slots=True)
class DryRunReport:
    """Non-executing preflight output."""

    command: Mapping[str, Any]
    command_sha256: str
    prospective_artifact_directory: Path
    execution_allowed: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    """Observed process result and sealed evidence locations."""

    return_code: int
    wall_seconds: float
    timed_out: bool
    output_budget_exceeded: bool
    stdout_path: Path
    stderr_path: Path
    events_path: Path
    run_plan_path: Path
    command_path: Path
    artifact_records_path: Path
    stdout_redactions: int
    stderr_redactions: int
    usage: BudgetUsage
    status: str


@dataclass(frozen=True, slots=True)
class _ProcessResult:
    return_code: int
    wall_seconds: float
    timed_out: bool
    output_budget_exceeded: bool
    stdout_redactions: int
    stderr_redactions: int
    output_bytes: int
    launch_error: OSError | ValueError | None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def render_command(command: CommandSpec) -> dict[str, JsonValue]:
    """Render only serializable, non-secret, authorization-bound command material."""

    return command_document(command)


def _open_exclusive(path: Path) -> BinaryIO:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        handle = os.fdopen(descriptor, "wb", buffering=0)
    except Exception:
        os.close(descriptor)
        raise
    return handle


def _write_json_exclusive(
    path: Path,
    value: Mapping[str, Any],
    *,
    scrubber: ExactCredentialScrubber,
    label: str,
) -> None:
    encoded = (
        json.dumps(
            value,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    scrubber.assert_bytes(encoded, label=label)
    with _open_exclusive(path) as handle:
        handle.write(encoded)
        os.fsync(handle.fileno())


class _OutputQuota:
    def __init__(self, maximum: int) -> None:
        self.maximum = maximum
        self.used = 0
        self.exceeded = False
        self._lock = threading.Lock()

    def take(self, chunk: bytes) -> bytes:
        with self._lock:
            remaining = max(0, self.maximum - self.used)
            accepted = chunk[:remaining]
            self.used += len(accepted)
            if len(accepted) != len(chunk):
                self.exceeded = True
            return accepted


class _StreamingRedactor:
    """Redact exact secret values across arbitrary pipe chunk boundaries."""

    def __init__(self, secrets: tuple[bytes, ...], replacement: bytes = b"[REDACTED]") -> None:
        self.secrets = tuple(sorted(set(filter(None, secrets)), key=len, reverse=True))
        if any(secret in replacement for secret in self.secrets):
            raise ValueError("redaction replacement must not contain a configured credential")
        self.replacement = replacement
        self.maximum_secret_length = max((len(secret) for secret in self.secrets), default=1)
        self.buffer = b""
        self.redactions = 0

    def feed(self, chunk: bytes) -> bytes:
        self.buffer += chunk
        return self._drain(final=False)

    def finish(self) -> bytes:
        return self._drain(final=True)

    def _next_match(self) -> tuple[int, bytes] | None:
        matches = (
            (index, secret) for secret in self.secrets if (index := self.buffer.find(secret)) >= 0
        )
        return min(matches, key=lambda item: (item[0], -len(item[1])), default=None)

    def _drain(self, *, final: bool) -> bytes:
        output = bytearray()
        while match := self._next_match():
            index, secret = match
            output.extend(self.buffer[:index])
            output.extend(self.replacement)
            self.redactions += 1
            self.buffer = self.buffer[index + len(secret) :]
        if final:
            output.extend(self.buffer)
            self.buffer = b""
            return bytes(output)
        retained = self.maximum_secret_length - 1
        safe_length = max(0, len(self.buffer) - retained)
        if safe_length:
            output.extend(self.buffer[:safe_length])
            self.buffer = self.buffer[safe_length:]
        return bytes(output)


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        if process.poll() is None:
            raise


class _ProcessGroupTerminator:
    """Issue at most one process-group kill across owner and capture threads."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process
        self._lock = threading.Lock()
        self._terminated = False

    def __call__(self) -> None:
        with self._lock:
            if self._terminated:
                return
            _kill_process_group(self.process)
            self._terminated = True


def _capture_pipe(
    pipe: BinaryIO,
    output: BinaryIO,
    redactor: _StreamingRedactor,
    quota: _OutputQuota,
    kill: Callable[[], None],
    errors: list[BaseException],
) -> None:
    def write(chunk: bytes) -> None:
        accepted = quota.take(chunk)
        if accepted:
            output.write(accepted)
        if len(accepted) != len(chunk):
            kill()

    try:
        while chunk := os.read(pipe.fileno(), 64 * 1024):
            write(redactor.feed(chunk))
        write(redactor.finish())
        output.flush()
        os.fsync(output.fileno())
    except BaseException as exc:  # preserve the error for the owner thread
        errors.append(exc)
        kill()
    finally:
        pipe.close()


class RunSession:
    """Own one run from process completion through normalization and final sealing."""

    __slots__ = (
        "_accounting_attested",
        "_attempt_directory",
        "_command",
        "_command_path",
        "_normalization_applied",
        "_outcome",
        "_plan",
        "_process_result",
        "_retained",
        "_run_plan_path",
        "_scrubber",
        "_sealed",
        "_sequence",
        "_status",
        "_stderr_path",
        "_stdout_path",
        "_usage",
    )

    def __setattr__(self, name: str, value: object) -> None:
        if name in self.__slots__ and hasattr(self, name):
            raise AttributeError(f"run session state is write-owned: {name}")
        object.__setattr__(self, name, value)

    def __init__(
        self,
        *,
        plan: RunPlan,
        command: CommandSpec,
        attempt_directory: Path,
        usage: BudgetUsage,
        process_result: _ProcessResult,
        stdout_path: Path,
        stderr_path: Path,
        run_plan_path: Path,
        command_path: Path,
        scrubber: ExactCredentialScrubber,
        sequence: int,
        status: str,
    ) -> None:
        self._plan = plan
        self._command = command
        self._attempt_directory = attempt_directory
        self._usage = usage
        self._process_result = process_result
        self._stdout_path = stdout_path
        self._stderr_path = stderr_path
        self._run_plan_path = run_plan_path
        self._command_path = command_path
        self._scrubber = scrubber
        self._sequence = sequence
        self._status = status
        self._sealed = False
        self._outcome: ExecutionOutcome | None = None
        self._accounting_attested = False
        self._normalization_applied = False
        self._retained: Mapping[Path, str] = MappingProxyType(
            {
                stdout_path: "raw-log",
                stderr_path: "raw-log",
                run_plan_path: "run-plan",
                command_path: "command",
            }
        )

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def attempt_directory(self) -> Path:
        return self._attempt_directory

    def apply_normalization(self, result: NormalizationResult) -> None:
        """Commit exactly one adapter result and close its non-wall accounting."""

        self._assert_open()
        self._assert_authority_owned()
        if self._normalization_applied:
            raise RuntimeError("adapter normalization has already been applied")
        validated_artifacts: list[Path] = []
        root = self._attempt_directory.resolve(strict=True)
        for index, path in enumerate(result.raw_artifacts):
            if not isinstance(path, Path):
                raise ValueError(f"adapter artifact {index} must be a path")
            try:
                self._scrubber.assert_bytes(
                    os.fsencode(path),
                    label="adapter raw artifact path",
                )
            except CredentialExposureError:
                object.__setattr__(self, "_status", "credential-artifact-refused")
                raise
            try:
                resolved = path.resolve(strict=True)
            except (OSError, RuntimeError):
                raise ValueError(f"adapter artifact {index} cannot be resolved") from None
            if (
                resolved == root
                or root not in resolved.parents
                or path.is_symlink()
                or not resolved.is_file()
            ):
                raise ValueError(
                    f"adapter artifact {index} is not a regular file inside the run attempt"
                )
            if resolved in self._retained or resolved in validated_artifacts:
                raise ValueError(f"adapter artifact {index} duplicates existing ownership")
            try:
                relative = resolved.relative_to(root).as_posix().encode("utf-8")
                self._scrubber.assert_bytes(relative, label="adapter raw artifact path")
                self._scrubber.assert_file(resolved, label="adapter raw artifact")
            except CredentialExposureError:
                object.__setattr__(self, "_status", "credential-artifact-refused")
                self._remove_attempt_entries((resolved,))
                raise
            validated_artifacts.append(resolved)
        retained = dict(self._retained)
        for resolved in validated_artifacts:
            retained[resolved] = "upstream-raw"
        object.__setattr__(self, "_retained", MappingProxyType(retained))
        try:
            for event in result.events:
                self._emit_normalized(event)
            for field in result.unavailable_fields:
                self._emit(
                    EventType.WARNING,
                    {"kind": "unavailable-field", "field": field},
                    provenance=EventProvenance.UNAVAILABLE,
                )
            for warning in result.warnings:
                self._emit(
                    EventType.WARNING,
                    {"kind": "adapter-warning", "message": warning},
                    provenance=EventProvenance.OBSERVED,
                )
        except CredentialExposureError:
            object.__setattr__(self, "_status", "credential-evidence-refused")
            raise
        object.__setattr__(self, "_normalization_applied", True)
        self._attest_accounting(result.accounting)

    def _attest_accounting(self, accounting: NonWallResourceAccounting) -> None:
        """Close one command's non-wall accounting with observed or unavailable values."""

        self._assert_open()
        self._assert_authority_owned()
        if self._accounting_attested:
            raise RuntimeError("non-wall resource accounting is already closed")
        projection = self._command.resource_projection
        observed = BudgetUsage(
            cost_usd=accounting.cost_usd or 0.0,
            gpu_hours=accounting.gpu_hours or 0.0,
            model_tokens=accounting.model_tokens or 0,
            tool_calls=accounting.tool_calls or 0,
        )

        def accounting_state(value: float | int | None, projected: float | int) -> str:
            if value is not None:
                return "observed"
            return "unavailable-reserved" if projected > 0 else "not-applicable"

        accounting_status: dict[str, JsonValue] = {
            "cost_usd": accounting_state(accounting.cost_usd, projection.cost_usd),
            "gpu_hours": accounting_state(accounting.gpu_hours, projection.gpu_hours),
            "model_tokens": accounting_state(accounting.model_tokens, projection.model_tokens),
            "tool_calls": accounting_state(accounting.tool_calls, projection.tool_calls),
        }
        projection_violations = projection.observed_violations(observed)
        object.__setattr__(self, "_accounting_attested", True)
        if projection_violations:
            projection_error = ResourceProjectionExceeded(
                "observed usage exceeded the authorized preflight projection: "
                + ", ".join(projection_violations)
            )
            object.__setattr__(self, "_status", "resource-projection-exceeded")
            violation_usage = BudgetUsage(
                wall_seconds=self._process_result.wall_seconds,
                cost_usd=(
                    projection.cost_usd if accounting.cost_usd is None else accounting.cost_usd
                ),
                gpu_hours=(
                    projection.gpu_hours if accounting.gpu_hours is None else accounting.gpu_hours
                ),
                model_tokens=(
                    projection.model_tokens
                    if accounting.model_tokens is None
                    else accounting.model_tokens
                ),
                tool_calls=(
                    projection.tool_calls
                    if accounting.tool_calls is None
                    else accounting.tool_calls
                ),
                output_bytes=self._process_result.output_bytes,
            )
            object.__setattr__(self, "_usage", violation_usage)
            self._emit_budget(violation_usage, accounting_status=accounting_status)
            self._emit(
                EventType.ERROR,
                {
                    "error_type": type(projection_error).__name__,
                    "message": str(projection_error),
                    "observed_nonwall_usage": {
                        "cost_usd": observed.cost_usd,
                        "gpu_hours": observed.gpu_hours,
                        "model_tokens": observed.model_tokens,
                        "tool_calls": observed.tool_calls,
                    },
                },
            )
            self.seal()
            raise LocalExecutionError(
                "observed resource use violated its preflight enforcement contract; "
                f"evidence: {self._attempt_directory}"
            ) from projection_error

        charged = BudgetUsage(
            cost_usd=(projection.cost_usd if accounting.cost_usd is None else accounting.cost_usd),
            gpu_hours=(
                projection.gpu_hours if accounting.gpu_hours is None else accounting.gpu_hours
            ),
            model_tokens=(
                projection.model_tokens
                if accounting.model_tokens is None
                else accounting.model_tokens
            ),
            tool_calls=(
                projection.tool_calls if accounting.tool_calls is None else accounting.tool_calls
            ),
        )

        current = BudgetUsage(
            wall_seconds=self._usage.wall_seconds,
            cost_usd=self._usage.cost_usd + charged.cost_usd,
            gpu_hours=self._usage.gpu_hours + charged.gpu_hours,
            model_tokens=self._usage.model_tokens + charged.model_tokens,
            tool_calls=self._usage.tool_calls + charged.tool_calls,
            output_bytes=self._usage.output_bytes,
        )
        object.__setattr__(self, "_usage", current)
        try:
            BudgetGuard(self._plan.budget).assert_within(current)
        except (BudgetExceeded, ValueError) as exc:
            object.__setattr__(self, "_status", "budget-exceeded")
            self._emit_budget(current, accounting_status=accounting_status)
            self._emit(
                EventType.ERROR,
                {"error_type": type(exc).__name__, "message": str(exc)},
            )
            self.seal()
            raise LocalExecutionError(
                f"run accounting exceeded its hard budget; evidence: {self._attempt_directory}"
            ) from exc
        unavailable = [
            unit
            for unit, value, projected in (
                ("cost_usd", accounting.cost_usd, projection.cost_usd),
                ("gpu_hours", accounting.gpu_hours, projection.gpu_hours),
                ("model_tokens", accounting.model_tokens, projection.model_tokens),
                ("tool_calls", accounting.tool_calls, projection.tool_calls),
            )
            if value is None and projected > 0
        ]
        if unavailable:
            unavailable_values: list[JsonValue] = [unit for unit in unavailable]
            self._emit(
                EventType.WARNING,
                {
                    "kind": "resource-accounting-unavailable",
                    "units": unavailable_values,
                    "charged_at_authorized_projection": True,
                },
                provenance=EventProvenance.UNAVAILABLE,
            )
        reported = BudgetUsage(
            wall_seconds=max(current.wall_seconds, self._process_result.wall_seconds),
            cost_usd=current.cost_usd,
            gpu_hours=current.gpu_hours,
            model_tokens=current.model_tokens,
            tool_calls=current.tool_calls,
            output_bytes=max(current.output_bytes, self._process_result.output_bytes),
        )
        self._emit_budget(reported, accounting_status=accounting_status)

    def seal(self) -> ExecutionOutcome:
        """Append terminal events, hash every retained file, and make the run immutable."""

        if self._outcome is not None:
            return self._outcome
        self._assert_open()
        self._assert_authority_owned()
        self._assert_attempt_entries_owned_and_safe()
        if self._command.resource_projection.has_usage and not self._accounting_attested:
            raise LocalExecutionError(
                "non-wall resource accounting must be observed or explicitly unavailable "
                "before sealing"
            )
        records = []
        for path, kind in sorted(self._retained.items(), key=lambda item: str(item[0])):
            self._scrubber.assert_file(path, label=f"retained {kind}")
            record = artifact_record(path, kind=kind, relative_to=self._attempt_directory)
            self._scrubber.assert_json(artifact_document(record), label="artifact record")
            records.append(record)
        for record in records:
            self._emit(
                EventType.ARTIFACT_RECORDED,
                artifact_document(record),
                provenance=EventProvenance.DERIVED,
            )
        self._emit(
            EventType.RUN_STOPPED,
            {"status": self._status, "return_code": self._process_result.return_code},
        )
        events_path = self._attempt_directory / EVENT_STREAM
        self._scrubber.assert_file(events_path, label="retained event stream")
        event_record = artifact_record(
            events_path, kind="event-stream", relative_to=self._attempt_directory
        )
        self._scrubber.assert_json(artifact_document(event_record), label="artifact record")
        records.append(event_record)
        manifest = ArtifactRecordWriter(self._attempt_directory)
        for record in records:
            manifest.append(record)
        self._scrubber.assert_file(manifest.path, label="artifact manifest")
        outcome = ExecutionOutcome(
            return_code=self._process_result.return_code,
            wall_seconds=self._process_result.wall_seconds,
            timed_out=self._process_result.timed_out,
            output_budget_exceeded=self._process_result.output_budget_exceeded,
            stdout_path=self._stdout_path,
            stderr_path=self._stderr_path,
            events_path=events_path,
            run_plan_path=self._run_plan_path,
            command_path=self._command_path,
            artifact_records_path=manifest.path,
            stdout_redactions=self._process_result.stdout_redactions,
            stderr_redactions=self._process_result.stderr_redactions,
            usage=self._usage,
            status=self._status,
        )
        object.__setattr__(self, "_outcome", outcome)
        object.__setattr__(self, "_sealed", True)
        return outcome

    def _assert_open(self) -> None:
        if self._sealed:
            raise RuntimeError("run session is already sealed")

    def _assert_authority_owned(self) -> None:
        try:
            BudgetGuard(self._plan.budget).assert_within(self._usage)
        except BudgetExceeded:
            if self._status not in {"budget-exceeded", "resource-projection-exceeded"}:
                raise
        expected = self._plan.execution.authorization.command_sha256
        if expected is None or command_sha256(self._command) != expected:
            raise RuntimeError("run session authority no longer matches its retained contracts")

    def _assert_attempt_entries_owned_and_safe(self) -> None:
        events_path = (self._attempt_directory / EVENT_STREAM).resolve(strict=True)
        owned = {*self._retained, events_path}
        unowned: list[Path] = []
        unsafe: list[Path] = []
        for path in sorted(self._attempt_directory.rglob("*")):
            relative = path.relative_to(self._attempt_directory).as_posix()
            try:
                self._scrubber.assert_bytes(
                    relative.encode("utf-8"),
                    label="attempt entry path",
                )
                if path.is_file() and not path.is_symlink():
                    self._scrubber.assert_file(path, label="attempt entry")
            except CredentialExposureError:
                unsafe.append(path)
                continue
            if path.is_symlink():
                raise LocalExecutionError("symlink entries are forbidden in a run attempt")
            if not path.is_dir() and not path.is_file():
                raise LocalExecutionError("non-regular entries are forbidden in a run attempt")
            if path.is_file() and path.resolve(strict=True) not in owned:
                unowned.append(path)
        if unsafe:
            object.__setattr__(self, "_status", "credential-artifact-refused")
            self._remove_attempt_entries(tuple(unsafe))
            raise CredentialExposureError(
                "credential-bearing attempt entries were refused and removed"
            )
        if unowned:
            raise LocalExecutionError(
                "all attempt files must be declared by the session before sealing"
            )

    def _remove_attempt_entries(self, paths: tuple[Path, ...]) -> None:
        for path in sorted(paths, key=lambda item: len(item.parts), reverse=True):
            if path == self._attempt_directory or self._attempt_directory not in path.parents:
                raise RuntimeError("refused artifact removal escaped the run attempt")
            if path.is_symlink() or not path.is_dir():
                path.unlink(missing_ok=True)
            else:
                try:
                    path.rmdir()
                except OSError:
                    continue
            parent = path.parent
            while parent != self._attempt_directory:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

    def _emit_normalized(self, event: NormalizedEvent) -> None:
        self._emit(
            EventType(event.event_type.value),
            {key: thaw_json(value) for key, value in event.payload.items()},
            source=event.source,
            provenance=event.provenance,
        )

    def _emit_budget(
        self,
        usage: BudgetUsage,
        *,
        accounting_status: Mapping[str, JsonValue] | None = None,
    ) -> None:
        payload: dict[str, JsonValue] = {
            "wall_seconds": usage.wall_seconds,
            "cost_usd": usage.cost_usd,
            "gpu_hours": usage.gpu_hours,
            "model_tokens": usage.model_tokens,
            "tool_calls": usage.tool_calls,
            "output_bytes": usage.output_bytes,
        }
        if accounting_status is not None:
            payload["nonwall_accounting"] = dict(accounting_status)
        self._emit(
            EventType.BUDGET_UPDATE,
            payload,
        )

    def _emit(
        self,
        event_type: EventType,
        payload: Mapping[str, JsonValue],
        *,
        source: str = "giclab-harness",
        provenance: EventProvenance = EventProvenance.OBSERVED,
    ) -> None:
        event = HarnessEvent(
            run_id=self._plan.identity.run_id,
            attempt=self._plan.identity.attempt,
            sequence=self._sequence + 1,
            timestamp_utc=_utc_now(),
            event_type=event_type,
            source=source,
            provenance=provenance,
            payload=payload,
        )
        self._scrubber.assert_json(event_document(event), label="harness event")
        JsonlEventWriter(
            self._attempt_directory / EVENT_STREAM,
            self._plan.identity,
        ).append(event)
        object.__setattr__(self, "_sequence", event.sequence)


class LocalRunExecutor:
    """Run one local command only after both authorization planes pass."""

    def __init__(
        self,
        workspace: ArtifactWorkspace,
        *,
        host_environment: Mapping[str, str] | None = None,
    ) -> None:
        self.workspace = workspace
        self._host_environment = host_environment if host_environment is not None else os.environ

    def dry_run(
        self,
        plan: RunPlan,
        command: CommandSpec,
        state: ProjectExecutionState,
    ) -> DryRunReport:
        """Return deterministic preflight data without creating files or a process."""

        structural = self._structural_blockers(plan, command)
        blockers = (*execution_blockers(plan, state), *structural)
        prospective = self.workspace.attempt_directory(plan.artifacts, plan.identity, create=False)
        return DryRunReport(
            command=render_command(command),
            command_sha256=command_sha256(command),
            prospective_artifact_directory=prospective,
            execution_allowed=not blockers,
            blockers=blockers,
        )

    def execute(
        self,
        plan: RunPlan,
        command: CommandSpec,
        state: ProjectExecutionState,
    ) -> RunSession:
        """Execute with ``shell=False`` and return an open normalization session."""

        assert_execution_allowed(plan, state)
        structural = self._structural_blockers(plan, command)
        if structural:
            raise ExecutionDisallowed("; ".join(structural))
        guard = BudgetGuard(plan.budget)
        guard.assert_limits_unchanged(plan.budget)
        projection = command.resource_projection
        guard.assert_projected(
            wall_seconds=float(command.timeout_seconds),
            cost_usd=projection.cost_usd,
            gpu_hours=projection.gpu_hours,
            model_tokens=projection.model_tokens,
            tool_calls=projection.tool_calls,
        )
        environment, private_values = self._build_environment(command)
        scrubber = ExactCredentialScrubber(private_values)
        plan_data = run_plan_document(plan)
        command_data = command_document(command)
        scrubber.assert_json(plan_data, label="retained run plan")
        scrubber.assert_json(command_data, label="retained command")
        scrubber.assert_bytes(b"\n", label="JSONL evidence framing")
        for owned_name in (
            RUN_PLAN_RECORD,
            COMMAND_RECORD,
            EVENT_STREAM,
            ARTIFACT_RECORDS,
            "stdout.log",
            "stderr.log",
        ):
            scrubber.assert_bytes(
                owned_name.encode("utf-8"),
                label="harness-owned artifact path",
            )
        prospective_attempt = self.workspace.attempt_directory(
            plan.artifacts,
            plan.identity,
            create=False,
        )
        scrubber.assert_bytes(
            prospective_attempt.relative_to(self.workspace.root).as_posix().encode("utf-8"),
            label="run attempt path",
        )
        attempt_dir = self.workspace.attempt_directory(plan.artifacts, plan.identity, create=True)
        events_path = attempt_dir / EVENT_STREAM
        stdout_path = attempt_dir / "stdout.log"
        stderr_path = attempt_dir / "stderr.log"
        run_plan_path = attempt_dir / RUN_PLAN_RECORD
        command_path = attempt_dir / COMMAND_RECORD
        _write_json_exclusive(
            run_plan_path,
            plan_data,
            scrubber=scrubber,
            label="retained run plan",
        )
        _write_json_exclusive(
            command_path,
            command_data,
            scrubber=scrubber,
            label="retained command",
        )
        writer = JsonlEventWriter(events_path, plan.identity)
        sequence = 0

        def emit(
            event_type: EventType,
            payload: Mapping[str, JsonValue],
            *,
            provenance: EventProvenance = EventProvenance.OBSERVED,
        ) -> None:
            nonlocal sequence
            event = HarnessEvent(
                run_id=plan.identity.run_id,
                attempt=plan.identity.attempt,
                sequence=sequence + 1,
                timestamp_utc=_utc_now(),
                event_type=event_type,
                source="giclab-harness",
                provenance=provenance,
                payload=payload,
            )
            scrubber.assert_json(event_document(event), label="harness event")
            writer.append(event)
            sequence = event.sequence

        emit(
            EventType.RUN_STARTED,
            {
                "experiment_id": plan.identity.experiment_id,
                "condition": plan.identity.condition,
                "profile": plan.profile.value,
                "giclab_commit": plan.sources.giclab_commit,
                "upstream_source_id": plan.sources.upstream_source_id,
                "upstream_commit": plan.sources.upstream_commit,
                "protocol_sha256": plan.sources.protocol_sha256,
                "config_sha256": plan.sources.config_sha256,
                "model_revision": plan.sources.model_revision,
                "dataset_revision": plan.sources.dataset_revision,
                "environment_sha256": plan.sources.environment_sha256,
            },
        )
        authorization_reference = plan.execution.authorization.authorization_reference
        if authorization_reference is None:  # execution gate makes this unreachable
            raise AssertionError("authorized execution has no reference")
        emit(
            EventType.PREFLIGHT_COMPLETED,
            {
                "authorization_reference_sha256": hashlib.sha256(
                    authorization_reference.encode("utf-8")
                ).hexdigest(),
                "command_sha256": command_sha256(command),
                "artifact_directory": attempt_dir.relative_to(self.workspace.root).as_posix(),
                "max_wall_seconds": plan.budget.max_wall_seconds,
                "max_output_bytes": plan.budget.max_output_bytes,
                "projected_cost_usd": projection.cost_usd,
                "projected_gpu_hours": projection.gpu_hours,
                "projected_model_tokens": projection.model_tokens,
                "projected_tool_calls": projection.tool_calls,
                "incremental_limit_enforcement": projection.enforcement.value,
            },
            provenance=EventProvenance.DERIVED,
        )

        process_result = self._run_process(
            command,
            environment,
            scrubber,
            stdout_path,
            stderr_path,
            plan.budget.max_output_bytes,
            lambda: emit(EventType.COMMAND_STARTED, render_command(command)),
        )
        if process_result.launch_error is not None:
            emit(
                EventType.ERROR,
                {
                    "error_type": type(process_result.launch_error).__name__,
                    "message": str(process_result.launch_error),
                },
            )
            status = "launch-error"
        else:
            emit(
                EventType.COMMAND_COMPLETED,
                {
                    "return_code": process_result.return_code,
                    "timed_out": process_result.timed_out,
                    "wall_seconds": process_result.wall_seconds,
                    "output_budget_exceeded": process_result.output_budget_exceeded,
                    "stdout_redactions": process_result.stdout_redactions,
                    "stderr_redactions": process_result.stderr_redactions,
                },
            )
            status = (
                "output-budget-exceeded"
                if process_result.output_budget_exceeded
                else "timed-out"
                if process_result.timed_out
                else "completed"
                if process_result.return_code == 0
                else "command-failed"
            )
        budget_error: BudgetExceeded | None = None
        try:
            guard.record(
                wall_seconds=process_result.wall_seconds,
                output_bytes=process_result.output_bytes,
            )
        except BudgetExceeded as exc:
            budget_error = exc
            status = "budget-exceeded"
            emit(EventType.ERROR, {"error_type": type(exc).__name__, "message": str(exc)})
        emit(
            EventType.BUDGET_UPDATE,
            {
                "wall_seconds": process_result.wall_seconds,
                "output_bytes": process_result.output_bytes,
                "within_budget": budget_error is None and not process_result.output_budget_exceeded,
            },
        )
        session = RunSession(
            plan=plan,
            command=command,
            attempt_directory=attempt_dir,
            usage=BudgetUsage(
                wall_seconds=process_result.wall_seconds,
                output_bytes=process_result.output_bytes,
            ),
            process_result=process_result,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            run_plan_path=run_plan_path,
            command_path=command_path,
            scrubber=scrubber,
            sequence=sequence,
            status=status,
        )
        if process_result.launch_error is not None:
            if projection.has_usage:
                session._attest_accounting(
                    NonWallResourceAccounting(
                        cost_usd=0.0,
                        gpu_hours=0.0,
                        model_tokens=0,
                        tool_calls=0,
                    )
                )
            session.seal()
            raise LocalExecutionError(
                f"local command could not be started; evidence: {attempt_dir}"
            ) from process_result.launch_error
        if budget_error is not None or process_result.output_budget_exceeded:
            raise LocalExecutionError(
                "local command exceeded its hard budget; normalize and seal the attached "
                f"failure session to preserve evidence: {attempt_dir}",
                session=session,
            ) from budget_error
        return session

    def _run_process(
        self,
        command: CommandSpec,
        environment: Mapping[str, str],
        scrubber: ExactCredentialScrubber,
        stdout_path: Path,
        stderr_path: Path,
        max_output_bytes: int,
        started_callback: Callable[[], None],
    ) -> _ProcessResult:
        stdout_handle = _open_exclusive(stdout_path)
        stderr_handle = _open_exclusive(stderr_path)
        started = time.monotonic()
        process: subprocess.Popen[bytes] | None = None
        terminate_group: _ProcessGroupTerminator | None = None
        try:
            try:
                runtime_blockers = self._runtime_path_blockers(command)
                if runtime_blockers:
                    raise OSError(
                        "command identity changed immediately before launch: "
                        + "; ".join(runtime_blockers)
                    )
                process = subprocess.Popen(
                    list(command.argv),
                    cwd=command.cwd,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=False,
                    start_new_session=True,
                )
            except (OSError, ValueError) as exc:
                return _ProcessResult(
                    return_code=127,
                    wall_seconds=time.monotonic() - started,
                    timed_out=False,
                    output_budget_exceeded=False,
                    stdout_redactions=0,
                    stderr_redactions=0,
                    output_bytes=0,
                    launch_error=exc,
                )
            terminate_group = _ProcessGroupTerminator(process)
            started_callback()
            if process.stdout is None or process.stderr is None:  # pragma: no cover
                raise RuntimeError("subprocess pipes were not created")
            quota = _OutputQuota(max_output_bytes)
            stdout_redactor = _StreamingRedactor(
                scrubber.private_bytes,
                replacement=scrubber.replacement,
            )
            stderr_redactor = _StreamingRedactor(
                scrubber.private_bytes,
                replacement=scrubber.replacement,
            )
            capture_errors: list[BaseException] = []

            threads = (
                threading.Thread(
                    target=_capture_pipe,
                    args=(
                        process.stdout,
                        stdout_handle,
                        stdout_redactor,
                        quota,
                        terminate_group,
                        capture_errors,
                    ),
                    daemon=True,
                ),
                threading.Thread(
                    target=_capture_pipe,
                    args=(
                        process.stderr,
                        stderr_handle,
                        stderr_redactor,
                        quota,
                        terminate_group,
                        capture_errors,
                    ),
                    daemon=True,
                ),
            )
            for thread in threads:
                thread.start()
            timed_out = False
            try:
                process.wait(timeout=command.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_group()
                process.wait()
            finally:
                terminate_group()
            for thread in threads:
                thread.join(timeout=5)
            if any(thread.is_alive() for thread in threads):
                raise RuntimeError("output capture did not terminate after process-group kill")
            if capture_errors:
                raise RuntimeError("output capture failed") from capture_errors[0]
            return _ProcessResult(
                return_code=process.returncode,
                wall_seconds=time.monotonic() - started,
                timed_out=timed_out,
                output_budget_exceeded=quota.exceeded,
                stdout_redactions=stdout_redactor.redactions,
                stderr_redactions=stderr_redactor.redactions,
                output_bytes=quota.used,
                launch_error=None,
            )
        finally:
            if process is not None:
                if terminate_group is not None:
                    terminate_group()
                elif process.poll() is None:  # pragma: no cover - Popen returned incompletely
                    _kill_process_group(process)
                if process.poll() is None:
                    process.wait()
            stdout_handle.close()
            stderr_handle.close()

    def _structural_blockers(self, plan: RunPlan, command: CommandSpec) -> tuple[str, ...]:
        blockers: list[str] = []
        if plan.execution.backend is not ExecutionBackend.LOCAL_SUBPROCESS:
            blockers.append("local runner requires the local-subprocess backend")
        expected_command = plan.execution.authorization.command_sha256
        if expected_command is not None and command_sha256(command) != expected_command:
            blockers.append("command does not match the run plan authorization binding")
        if command.timeout_seconds > plan.budget.max_wall_seconds:
            blockers.append("command timeout exceeds the immutable wall-time budget")
        blockers.extend(self._runtime_path_blockers(command))
        for binding in command.inherit_environment:
            value = self._host_environment.get(binding.name)
            if value is None:
                blockers.append(
                    f"required inherited environment variable is missing: {binding.name}"
                )
            elif "\0" in value:
                blockers.append(
                    f"inherited environment variable contains a NUL byte: {binding.name}"
                )
            elif hashlib.sha256(value.encode("utf-8")).hexdigest() != binding.value_sha256:
                blockers.append(f"inherited environment binding changed: {binding.name}")
        projection = command.resource_projection
        try:
            BudgetGuard(plan.budget).assert_projected(
                wall_seconds=float(command.timeout_seconds),
                cost_usd=projection.cost_usd,
                gpu_hours=projection.gpu_hours,
                model_tokens=projection.model_tokens,
                tool_calls=projection.tool_calls,
            )
        except BudgetExceeded as exc:
            blockers.append(str(exc))
        return tuple(blockers)

    @staticmethod
    def _runtime_path_blockers(command: CommandSpec) -> tuple[str, ...]:
        blockers: list[str] = []
        cwd_identity = command.cwd_identity
        if cwd_identity is None:
            blockers.append("command cwd has no authorization-bound filesystem identity")
        else:
            try:
                resolved_cwd = command.cwd.resolve(strict=True)
                metadata = command.cwd.stat()
                if command.cwd.is_symlink() or resolved_cwd != command.cwd:
                    blockers.append("command cwd resolution changed after authorization")
                elif not command.cwd.is_dir():
                    blockers.append("command cwd must remain an existing directory")
                elif (metadata.st_dev, metadata.st_ino) != (
                    cwd_identity.device,
                    cwd_identity.inode,
                ):
                    blockers.append("command cwd filesystem identity changed after authorization")
            except (OSError, ValueError) as exc:
                blockers.append(f"cannot verify command cwd identity: {exc}")
        executable = Path(command.argv[0])
        try:
            resolved_executable = executable.resolve(strict=True)
            if resolved_executable != executable or not executable.is_file():
                blockers.append("argv[0] must remain an absolute resolved executable file")
            elif sha256_file(executable) != command.executable_sha256:
                blockers.append("resolved executable content no longer matches its binding")
        except (OSError, ValueError) as exc:
            blockers.append(f"cannot verify resolved executable identity: {exc}")
        return tuple(blockers)

    def _build_environment(self, command: CommandSpec) -> tuple[dict[str, str], tuple[str, ...]]:
        environment = dict(command.environment)
        for binding in command.inherit_environment:
            value = self._host_environment.get(binding.name)
            if value is None:
                raise ExecutionDisallowed(
                    f"required inherited environment variable is missing: {binding.name}"
                )
            if hashlib.sha256(value.encode("utf-8")).hexdigest() != binding.value_sha256:
                raise ExecutionDisallowed(f"inherited environment binding changed: {binding.name}")
            if "\0" in value:
                raise ExecutionDisallowed(
                    f"inherited environment variable contains a NUL byte: {binding.name}"
                )
            environment[binding.name] = value
        private_values: list[str] = []
        for name in command.secret_environment:
            value = self._host_environment.get(name)
            if value is None or not value:
                raise ExecutionDisallowed(
                    f"required secret environment variable is missing: {name}"
                )
            if "\0" in value:
                raise ExecutionDisallowed(
                    f"secret environment variable contains a NUL byte: {name}"
                )
            environment[name] = value
            private_values.append(value)
        return environment, tuple(private_values)
