"""Runtime-side admission ports for historical and supervised remote conditions.

`InProcessBoundaryPort` preserves the historically bound local path.
`DuplexSupervisorPort` is only a client: every model send, browser action, and
output-growth operation waits for the shared supervisor.  It never constructs or
owns a :class:`ProviderBudgetBoundary`.
"""

from __future__ import annotations

import contextlib
import hashlib
import math
import os
import socket
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import BinaryIO, Protocol, TypeVar, cast

from giclab.control.remote_bridge import (
    BRIDGE_PROTOCOL_VERSION,
    ConditionBridgeFrame,
    ConditionSessionBinding,
    FramedDuplexEndpoint,
    RemoteBridgeError,
    canonical_bytes,
    provider_request_document,
    semantic_sha256,
    strict_json_object,
    usage_document,
)
from giclab.harness.sira_gate_a import (
    ProviderBudgetBoundary,
    ProviderBudgetUsage,
    ProviderFailureDisposition,
    ProviderRequest,
    ProviderResponseReceiptError,
    ProviderResponseUsage,
)

T = TypeVar("T")
MAX_PRIVATE_SOCKET_BINDING_BYTES = 65_536
PRIVATE_SOCKET_BINDING_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class RuntimeCallState:
    call_id: str
    terminal_state: str
    actual_usage: ProviderResponseUsage | None


class RuntimeAdmissionPort(Protocol):
    """All before-effect admissions required by the SiRA runtime adaptation."""

    @property
    def condition_usage(self) -> ProviderBudgetUsage: ...

    @property
    def unreconciled_provider_attempts(self) -> int: ...

    def model_call(
        self,
        request: ProviderRequest,
        send: Callable[[ProviderRequest], tuple[T, ProviderResponseUsage]],
        *,
        before_send: Callable[[], None] | None,
        call_id: str,
        logical_call_id: str,
        classify_failure: Callable[[BaseException], ProviderFailureDisposition],
    ) -> T: ...

    def browser_action(self, *, action_id: str, perform: Callable[[], T]) -> T: ...

    def output_bytes(self, *, total_bytes: int) -> None: ...

    def process_exit(self, *, exit_code: int) -> None: ...

    def completion(self, *, completed: bool, answer: str | None, error: str) -> None: ...

    def raw_published(self, *, manifest_sha256: str, receipt_sha256: str) -> None: ...

    def close_in_flight(
        self,
        *,
        grace_seconds: float,
        sleeper: Callable[[float], None],
    ) -> None: ...

    def accounting_document(self) -> Mapping[str, object]: ...

    def terminal_call_state(self, call_id: str) -> RuntimeCallState: ...

    def detach_runtime(self) -> Mapping[str, object]: ...

    def terminalize(self) -> Mapping[str, object]: ...

    def close(self) -> None: ...


class InProcessBoundaryPort:
    """Historical adapter over the retained in-process budget boundary."""

    def __init__(self, boundary: ProviderBudgetBoundary) -> None:
        self.boundary = boundary
        self._output_total = 0
        self._action_sequence = 0

    @property
    def condition_usage(self) -> ProviderBudgetUsage:
        return self.boundary.condition_usage

    @property
    def unreconciled_provider_attempts(self) -> int:
        return self.boundary.unreconciled_provider_attempts

    def model_call(
        self,
        request: ProviderRequest,
        send: Callable[[ProviderRequest], tuple[T, ProviderResponseUsage]],
        *,
        before_send: Callable[[], None] | None,
        call_id: str,
        logical_call_id: str,
        classify_failure: Callable[[BaseException], ProviderFailureDisposition],
    ) -> T:
        return self.boundary.invoke(
            request,
            send,
            before_send=before_send,
            call_id=call_id,
            logical_call_id=logical_call_id,
            classify_failure=classify_failure,
        )

    def browser_action(self, *, action_id: str, perform: Callable[[], T]) -> T:
        del action_id
        result: list[T] = []

        def operation() -> None:
            result.append(perform())

        self.boundary.record_browser_action(before_action=operation)
        if not result:
            raise RuntimeError("in-process browser operation returned no result")
        return result[0]

    def output_bytes(self, *, total_bytes: int) -> None:
        if type(total_bytes) is not int or total_bytes < self._output_total:
            raise ValueError("runtime output-byte total moved backward")
        self.boundary.record_output_bytes(total_bytes - self._output_total)
        self._output_total = total_bytes

    def process_exit(self, *, exit_code: int) -> None:
        if type(exit_code) is not int:
            raise ValueError("runtime process exit must be an integer")

    def completion(self, *, completed: bool, answer: str | None, error: str) -> None:
        if type(completed) is not bool or not isinstance(error, str):
            raise ValueError("runtime completion is malformed")
        if answer is not None and not isinstance(answer, str):
            raise ValueError("runtime answer is malformed")

    def raw_published(self, *, manifest_sha256: str, receipt_sha256: str) -> None:
        if len(manifest_sha256) != 64 or len(receipt_sha256) != 64:
            raise ValueError("runtime raw publication identity is malformed")

    def close_in_flight(
        self,
        *,
        grace_seconds: float,
        sleeper: Callable[[float], None],
    ) -> None:
        self.boundary.close_in_flight(grace_seconds=grace_seconds, sleeper=sleeper)

    def accounting_document(self) -> Mapping[str, object]:
        return self.boundary.accounting_document()

    def terminal_call_state(self, call_id: str) -> RuntimeCallState:
        record = next(item for item in self.boundary.call_records if item.call_id == call_id)
        return RuntimeCallState(
            call_id=call_id,
            terminal_state=(
                record.terminal_state.value if record.terminal_state is not None else "open"
            ),
            actual_usage=record.actual_usage,
        )

    def terminalize(self) -> Mapping[str, object]:
        return {
            "mode": "historical-in-process",
            "authoritative_accounting": True,
            "accounting_sha256": semantic_sha256(dict(self.accounting_document())),
        }

    def detach_runtime(self) -> Mapping[str, object]:
        return {
            "mode": "historical-in-process",
            "host_evidence_pending": False,
            "authoritative_accounting": True,
        }

    def close(self) -> None:
        return None


class DuplexSupervisorPort:
    """Remote event client whose every effect waits for the shared supervisor."""

    def __init__(
        self,
        endpoint: FramedDuplexEndpoint,
        *,
        remote_journal_path: Path,
        closeables: tuple[object, ...] = (),
    ) -> None:
        self.endpoint = endpoint
        self.remote_journal_path = remote_journal_path
        self._call_states: dict[str, RuntimeCallState] = {}
        self._in_flight: set[str] = set()
        self._condition_usage = ProviderBudgetUsage()
        self._output_total = 0
        self._terminalized = False
        self._closeables = closeables
        self._closed = False
        self._write_event(
            event_id="session.hello",
            event_type="condition-session-hello",
            payload={
                "accounting_owner": "shared-condition-event-observer",
                "remote_authoritative_boundary": False,
                "zero_retry": True,
            },
        )
        accepted = self._read_event({"condition-session-accepted"})
        if accepted.payload.get("accepted") is not True:
            raise RemoteBridgeError("shared supervisor rejected the condition session")

    @property
    def condition_usage(self) -> ProviderBudgetUsage:
        return self._condition_usage

    @property
    def unreconciled_provider_attempts(self) -> int:
        return len(self._in_flight)

    def _persist_journal(self, document: Mapping[str, object] | None = None) -> None:
        document = (
            self.endpoint.transcript_document(side="remote-mirror")
            if document is None
            else dict(document)
        )
        encoded = canonical_bytes(document)
        parent = self.remote_journal_path.parent
        parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        temporary = parent / f".{self.remote_journal_path.name}.tmp"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
        )
        try:
            offset = 0
            while offset < len(encoded):
                written = os.write(descriptor, encoded[offset:])
                if written <= 0:
                    raise RemoteBridgeError("remote journal write made no progress")
                offset += written
            os.fsync(descriptor)
        except BaseException:
            with contextlib.suppress(OSError):
                temporary.unlink()
            raise
        finally:
            os.close(descriptor)
        os.replace(temporary, self.remote_journal_path)
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _write_event(
        self,
        *,
        event_id: str,
        event_type: str,
        payload: Mapping[str, object],
    ) -> None:
        self.endpoint.write_event(event_id=event_id, event_type=event_type, payload=payload)
        self._persist_journal()

    def _read_event(self, expected: set[str]) -> ConditionBridgeFrame:
        frame = self.endpoint.read_event(expected=expected)
        self._persist_journal()
        return frame

    def model_call(
        self,
        request: ProviderRequest,
        send: Callable[[ProviderRequest], tuple[T, ProviderResponseUsage]],
        *,
        before_send: Callable[[], None] | None,
        call_id: str,
        logical_call_id: str,
        classify_failure: Callable[[BaseException], ProviderFailureDisposition],
    ) -> T:
        if call_id in self._call_states or call_id in self._in_flight:
            raise RemoteBridgeError("remote runtime call identity was reused")
        self._in_flight.add(call_id)
        reserve_id = f"{call_id}.reserve"
        self._write_event(
            event_id=reserve_id,
            event_type="model-call-reserve",
            payload={
                "call_id": call_id,
                "logical_call_id": logical_call_id,
                "request": provider_request_document(request),
            },
        )
        decision = self._read_event({"model-call-admitted", "model-call-rejected"})
        if decision.event_type == "model-call-rejected":
            self._call_states[call_id] = RuntimeCallState(call_id, "admission-rejected", None)
            self._in_flight.discard(call_id)
            raise RemoteBridgeError("shared observer rejected the model call before send")
        try:
            if before_send is not None:
                before_send()
        except BaseException:
            self._write_event(
                event_id=f"{call_id}.send-start",
                event_type="model-send-start",
                payload={"call_id": call_id},
            )
            self._write_event(
                event_id=f"{call_id}.known-no-send",
                event_type="known-transport-error-no-provider-acceptance",
                payload={"call_id": call_id, "error_type": "BeforeSendRejected"},
            )
            self._read_event({"model-call-terminal"})
            self._call_states[call_id] = RuntimeCallState(
                call_id,
                "known-transport-no-acceptance",
                None,
            )
            self._in_flight.discard(call_id)
            raise
        self._write_event(
            event_id=f"{call_id}.send-start",
            event_type="model-send-start",
            payload={"call_id": call_id},
        )
        try:
            result, usage = send(request)
        except BaseException as exc:
            disposition = classify_failure(exc)
            event_type = {
                ProviderFailureDisposition.PROVIDER_ERROR: "known-provider-error",
                ProviderFailureDisposition.TRANSPORT_ERROR_KNOWN: (
                    "known-transport-error-no-provider-acceptance"
                ),
                ProviderFailureDisposition.OUTCOME_UNKNOWN: "ambiguous-send",
            }[disposition]
            self._write_event(
                event_id=f"{call_id}.failure",
                event_type=event_type,
                payload={"call_id": call_id, "error_type": type(exc).__name__},
            )
            terminal = self._read_event({"model-call-terminal"})
            terminal_state = str(terminal.payload.get("status"))
            self._call_states[call_id] = RuntimeCallState(call_id, terminal_state, None)
            self._in_flight.discard(call_id)
            self._condition_usage = replace(
                self._condition_usage,
                model_call_attempts=self._condition_usage.model_call_attempts + 1,
            )
            raise
        try:
            usage_payload = usage_document(usage)
        except (AttributeError, TypeError, ValueError) as exc:
            self._write_event(
                event_id=f"{call_id}.accounting-incomplete",
                event_type="response-known-accounting-incomplete",
                payload={"call_id": call_id, "error_type": type(exc).__name__},
            )
            self._read_event({"model-call-terminal"})
            self._call_states[call_id] = RuntimeCallState(
                call_id,
                "response-accounting-incomplete",
                None,
            )
            self._in_flight.discard(call_id)
            self._condition_usage = replace(
                self._condition_usage,
                model_call_attempts=self._condition_usage.model_call_attempts + 1,
            )
            raise ProviderResponseReceiptError(
                "remote provider response usage is incomplete"
            ) from exc
        self._write_event(
            event_id=f"{call_id}.response",
            event_type="model-response",
            payload={
                "call_id": call_id,
                "content": _response_content(result),
                "usage": usage_payload,
            },
        )
        terminal = self._read_event({"model-call-terminal"})
        if terminal.payload.get("status") != "response-reconciled":
            raise RemoteBridgeError("shared observer did not reconcile the model response")
        self._call_states[call_id] = RuntimeCallState(
            call_id,
            "sent_response_reconciled",
            usage,
        )
        self._in_flight.discard(call_id)
        actual_cost = (
            (usage.input_tokens - usage.cached_input_tokens)
            * ProviderBudgetBoundary.INPUT_RATE_PER_MILLION
            + usage.cached_input_tokens * ProviderBudgetBoundary.CACHED_INPUT_RATE_PER_MILLION
            + usage.output_tokens * ProviderBudgetBoundary.OUTPUT_RATE_PER_MILLION
        ) / 1_000_000
        self._condition_usage = ProviderBudgetUsage(
            cost_usd=self._condition_usage.cost_usd + actual_cost,
            input_tokens=self._condition_usage.input_tokens + usage.input_tokens,
            cached_input_tokens=(
                self._condition_usage.cached_input_tokens + usage.cached_input_tokens
            ),
            output_tokens=self._condition_usage.output_tokens + usage.output_tokens,
            total_tokens=(
                self._condition_usage.total_tokens + usage.input_tokens + usage.output_tokens
            ),
            model_call_attempts=self._condition_usage.model_call_attempts + 1,
            default_service_tier_responses=(
                self._condition_usage.default_service_tier_responses + 1
            ),
            browser_actions=self._condition_usage.browser_actions,
            output_bytes=self._condition_usage.output_bytes,
        )
        return result

    def browser_action(self, *, action_id: str, perform: Callable[[], T]) -> T:
        self._write_event(
            event_id=f"{action_id}.reserve",
            event_type="browser-action-reserve",
            payload={"action_id": action_id},
        )
        decision = self._read_event({"browser-action-admitted", "browser-action-rejected"})
        if decision.event_type == "browser-action-rejected":
            raise RemoteBridgeError("shared observer rejected the browser action")
        result = perform()
        self._write_event(
            event_id=f"{action_id}.complete",
            event_type="browser-action-complete",
            payload={"action_id": action_id, "completed": True},
        )
        terminal = self._read_event({"browser-action-terminal"})
        if terminal.payload.get("status") != "completed":
            raise RemoteBridgeError("shared observer did not reconcile the browser action")
        self._condition_usage = replace(
            self._condition_usage,
            browser_actions=self._condition_usage.browser_actions + 1,
        )
        return result

    def output_bytes(self, *, total_bytes: int) -> None:
        if type(total_bytes) is not int or total_bytes < self._output_total:
            raise ValueError("runtime output-byte total moved backward")
        self._write_event(
            event_id=f"output.{total_bytes}",
            event_type="output-bytes-update",
            payload={"total_bytes": total_bytes},
        )
        decision = self._read_event({"output-bytes-admitted", "output-bytes-rejected"})
        if decision.event_type == "output-bytes-rejected":
            raise RemoteBridgeError("shared observer rejected output growth")
        self._output_total = total_bytes
        self._condition_usage = replace(self._condition_usage, output_bytes=total_bytes)

    def process_exit(self, *, exit_code: int) -> None:
        self._write_event(
            event_id="process.exit",
            event_type="process-exit",
            payload={"exit_code": exit_code},
        )
        self._read_event({"process-exit-accepted"})

    def completion(self, *, completed: bool, answer: str | None, error: str) -> None:
        self._write_event(
            event_id="session.completion",
            event_type="completion",
            payload={"completed": completed, "answer": answer, "error": error},
        )
        self._read_event({"completion-accepted"})

    def raw_published(self, *, manifest_sha256: str, receipt_sha256: str) -> None:
        self._write_event(
            event_id="raw.published",
            event_type="raw-artifact-published",
            payload={
                "manifest_sha256": manifest_sha256,
                "receipt_sha256": receipt_sha256,
            },
        )
        self._read_event({"raw-artifact-accepted"})

    def close_in_flight(
        self,
        *,
        grace_seconds: float,
        sleeper: Callable[[float], None],
    ) -> None:
        del grace_seconds, sleeper

    def accounting_document(self) -> Mapping[str, object]:
        return {
            "schema_version": "remote-mirror-1.0.0",
            "authoritative": False,
            "accounting_owner": "shared-condition-event-observer",
            "unreconciled_provider_attempts": self.unreconciled_provider_attempts,
            "condition_usage_mirror": _usage_values(self._condition_usage),
            "calls": {
                key: {
                    "terminal_state": value.terminal_state,
                    "actual_usage": (
                        usage_document(value.actual_usage)
                        if value.actual_usage is not None
                        else None
                    ),
                }
                for key, value in sorted(self._call_states.items())
            },
        }

    def terminal_call_state(self, call_id: str) -> RuntimeCallState:
        return self._call_states[call_id]

    def detach_runtime(self) -> Mapping[str, object]:
        """End the container client while leaving host-derived evidence pending."""

        if self._terminalized:
            raise RemoteBridgeError("remote runtime already detached or terminalized")
        prefix = self.endpoint.transcript_document(side="remote-mirror")
        self._write_event(
            event_id="runtime.client.complete",
            event_type="runtime-client-complete",
            payload={
                "host_evidence_pending": True,
                "remote_authoritative_boundary": False,
                "prefix_sequence": self.endpoint.next_sequence - 1,
                "prefix_frame_sha256": self.endpoint.previous_frame_sha256,
                "prefix_frame_chain_sha256": self.endpoint.frame_chain_sha256(),
                "prefix_journal_sha256": prefix["transcript_sha256"],
            },
        )
        accepted = self._read_event({"runtime-client-complete-accepted"})
        if accepted.payload.get("accepted") is not True:
            raise RemoteBridgeError("shared supervisor rejected runtime detachment")
        self._terminalized = True
        self._persist_journal()
        journal = self.endpoint.transcript_document(side="remote-mirror")
        encoded = canonical_bytes(journal)
        return {
            "mode": "duplex-supervisor-client",
            "authoritative_accounting": False,
            "host_evidence_pending": True,
            "terminal_sequence": self.endpoint.next_sequence - 1,
            "terminal_frame_sha256": self.endpoint.previous_frame_sha256,
            "frame_chain_sha256": self.endpoint.frame_chain_sha256(),
            "remote_journal_bytes": len(encoded),
            "remote_journal_file_sha256": hashlib.sha256(encoded).hexdigest(),
            "remote_journal_sha256": cast(str, journal["transcript_sha256"]),
        }

    def terminalize(self) -> Mapping[str, object]:
        if self._terminalized:
            raise RemoteBridgeError("remote condition session terminal was replayed")
        prior_hash = self.endpoint.previous_frame_sha256
        prior_count = self.endpoint.next_sequence - 1
        journal = self.endpoint.transcript_document(side="remote-mirror")
        journal_sha = cast(str, journal["transcript_sha256"])
        journal_encoded = canonical_bytes(journal)
        self._persist_journal(journal)
        prior_chain_sha = self.endpoint.frame_chain_sha256()
        self._write_event(
            event_id="session.terminal",
            event_type="condition-session-terminal",
            payload={
                "prior_frame_sha256": prior_hash,
                "prior_frame_count": prior_count,
                "remote_journal_sha256": journal_sha,
                "remote_journal_file_sha256": hashlib.sha256(journal_encoded).hexdigest(),
                "remote_journal_bytes": len(journal_encoded),
                "remote_terminal_sequence": prior_count,
                "remote_terminal_frame_sha256": prior_hash,
                "remote_frame_chain_sha256": prior_chain_sha,
                "prior_frame_chain_sha256": prior_chain_sha,
            },
        )
        acknowledgement = self._read_event({"condition-session-terminal-ack"})
        if acknowledgement.payload.get("accepted") is not True or acknowledgement.payload.get(
            "terminal_request_chain_sha256"
        ) != self.endpoint.frame_chain_sha256(exclude_tail=1):
            raise RemoteBridgeError("shared condition terminal acknowledgement failed")
        # The terminal request binds the exact pre-terminal remote journal.  Keep
        # that immutable document at the advertised path; the terminal request and
        # acknowledgement remain present in the shared and relay transcripts.
        self._persist_journal(journal)
        self._terminalized = True
        final = self.endpoint.transcript_document(side="remote-mirror")
        return {
            "mode": "duplex-supervisor-client",
            "authoritative_accounting": False,
            "remote_journal_sha256": journal_sha,
            "terminal_sequence": self.endpoint.next_sequence - 1,
            "terminal_frame_sha256": self.endpoint.previous_frame_sha256,
            "final_frame_chain_sha256": final.get("frame_chain_sha256"),
            "terminal_acknowledged": True,
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for value in self._closeables:
            close = getattr(value, "close", None)
            if callable(close):
                close()


def _usage_values(usage: ProviderBudgetUsage) -> dict[str, object]:
    return {
        "cost_usd": usage.cost_usd,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "model_call_attempts": usage.model_call_attempts,
        "default_service_tier_responses": usage.default_service_tier_responses,
        "browser_actions": usage.browser_actions,
        "output_bytes": usage.output_bytes,
    }


def _response_content(value: object) -> str:
    if isinstance(value, Mapping):
        content = value.get("content")
        if isinstance(content, str):
            return content
        identifier = value.get("id")
        if isinstance(identifier, str):
            return identifier
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    return type(value).__name__


def build_duplex_supervisor_port(
    *,
    reader: BinaryIO,
    writer: BinaryIO,
    binding: ConditionSessionBinding,
    deadline_monotonic: float,
    remote_journal_path: Path,
) -> DuplexSupervisorPort:
    endpoint = FramedDuplexEndpoint(
        reader=reader,
        writer=writer,
        binding=binding,
        deadline_monotonic=deadline_monotonic,
    )
    return DuplexSupervisorPort(endpoint, remote_journal_path=remote_journal_path)


def build_private_socket_supervisor_port(
    *,
    manifest_path: Path,
    attempt_root: Path,
    expected_binding: ConditionSessionBinding,
    expected_transaction_root_identity: str,
) -> DuplexSupervisorPort:
    """Connect to one host-created, identity-held private condition relay.

    The manifest is a private runtime input.  It is never discovered through an
    environment variable or a home-directory fallback.
    """

    root = attempt_root.resolve(strict=True)
    manifest = manifest_path.resolve(strict=True)
    metadata = manifest.stat(follow_symlinks=False)
    if (
        manifest_path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or not 0 < metadata.st_size <= MAX_PRIVATE_SOCKET_BINDING_BYTES
        or manifest.parent != (root / ".giclab-supervisor").resolve(strict=True)
    ):
        raise RemoteBridgeError("private duplex binding manifest is unsafe")
    encoded = manifest.read_bytes()
    try:
        document = strict_json_object(encoded, label="private duplex socket binding")
    except ValueError as exc:
        raise RemoteBridgeError(str(exc)) from exc
    if encoded != canonical_bytes(document):
        raise RemoteBridgeError("private duplex binding manifest is not canonical JSON")
    expected_fields = {
        "schema_version",
        "protocol_version",
        "binding",
        "transaction_root_identity",
        "socket_relative_path",
        "socket_device",
        "socket_inode",
        "socket_uid",
        "socket_mode",
        "socket_link_count",
        "deadline_monotonic",
        "remote_journal_relative_path",
    }
    binding_document = document.get("binding")
    deadline = document.get("deadline_monotonic")
    if (
        set(document) != expected_fields
        or document.get("schema_version") != PRIVATE_SOCKET_BINDING_SCHEMA_VERSION
        or document.get("protocol_version") != BRIDGE_PROTOCOL_VERSION
        or binding_document != expected_binding.to_document()
        or document.get("transaction_root_identity") != expected_transaction_root_identity
        or not isinstance(deadline, (int, float))
        or isinstance(deadline, bool)
        or not math.isfinite(float(deadline))
        or float(deadline) <= time.monotonic()
    ):
        raise RemoteBridgeError("private duplex binding identity or deadline drifted")
    socket_relative = document.get("socket_relative_path")
    journal_relative = document.get("remote_journal_relative_path")
    if (
        not isinstance(socket_relative, str)
        or Path(socket_relative).name != socket_relative
        or not isinstance(journal_relative, str)
        or Path(journal_relative).is_absolute()
        or ".." in Path(journal_relative).parts
    ):
        raise RemoteBridgeError("private duplex socket or journal path is malformed")
    socket_path = manifest.parent / socket_relative
    socket_metadata = socket_path.stat(follow_symlinks=False)
    if (
        socket_path.is_symlink()
        or not stat.S_ISSOCK(socket_metadata.st_mode)
        or socket_metadata.st_uid != os.getuid()
        or stat.S_IMODE(socket_metadata.st_mode) != 0o600
        or socket_metadata.st_dev != document.get("socket_device")
        or socket_metadata.st_ino != document.get("socket_inode")
        or socket_metadata.st_uid != document.get("socket_uid")
        or stat.S_IMODE(socket_metadata.st_mode) != document.get("socket_mode")
        or socket_metadata.st_nlink != document.get("socket_link_count")
    ):
        raise RemoteBridgeError("private duplex socket identity changed")
    journal_path = (root / journal_relative).resolve(strict=False)
    if root not in journal_path.parents:
        raise RemoteBridgeError("private duplex journal escaped the attempt root")
    channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        channel.connect(socket_path.as_posix())
        reader = cast(BinaryIO, channel.makefile("rb", buffering=0))
        writer = cast(BinaryIO, channel.makefile("wb", buffering=0))
        endpoint = FramedDuplexEndpoint(
            reader=reader,
            writer=writer,
            binding=expected_binding,
            deadline_monotonic=float(deadline),
        )
        return DuplexSupervisorPort(
            endpoint,
            remote_journal_path=journal_path,
            closeables=(reader, writer, channel),
        )
    except BaseException:
        channel.close()
        raise


__all__ = [
    "DuplexSupervisorPort",
    "InProcessBoundaryPort",
    "RuntimeAdmissionPort",
    "RuntimeCallState",
    "build_duplex_supervisor_port",
    "build_private_socket_supervisor_port",
]
