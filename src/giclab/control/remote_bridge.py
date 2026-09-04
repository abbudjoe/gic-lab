"""Typed, bounded bridge between the shared accountant and a remote condition client.

The shared process owns policy and accounting.  The remote side can request
admission and mirror the resulting journal, but it cannot admit a model send,
browser action, or output growth by itself.  This module contains no SSH, provider,
browser, container, secret, or scientific implementation.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import select
import socket
import stat
import struct
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Final, NoReturn, cast

from jsonschema import Draft202012Validator

from giclab.control.adapters import AdapterFailure
from giclab.control.effects import (
    ConditionAmbiguousSend,
    ConditionBridgeEvidence,
    ConditionEventObserver,
    ConditionKnownProviderError,
    ConditionKnownTransportError,
    ConditionModelCall,
    ConditionModelResponse,
    ConditionResponseAccountingIncomplete,
)
from giclab.harness.sira_gate_a import (
    ModelRole,
    ProviderBudgetExceeded,
    ProviderRequest,
    ProviderResponseUsage,
)
from giclab.harness.t09_provider_contracts import T09ProviderContract
from giclab.registry import local_schema_registry

BRIDGE_PROTOCOL_VERSION: Final = "1.0.0"
RETAINED_FROZEN_MANIFEST_SCHEMA_VERSION: Final = "0.1.0"
MAX_BRIDGE_FRAME_BYTES: Final = 1_048_576
MAX_BRIDGE_FRAMES: Final = 20_000
MAX_BRIDGE_TRANSCRIPT_BYTES: Final = 67_108_864
MAX_FROZEN_MANIFEST_BYTES: Final = 4_194_304
_ZERO_HASH: Final = "0" * 64
_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_HEADER: Final = struct.Struct("!I")


class RemoteBridgeError(RuntimeError):
    """A canonical bridge frame, ordering rule, or terminal handshake failed."""


class RemoteBridgeDisconnected(RemoteBridgeError):
    """The duplex channel closed before its required terminal acknowledgement."""


class RemoteBridgeReplay(RemoteBridgeError):
    """A sequence, event, or frame identity was replayed."""


def canonical_bytes(value: object) -> bytes:
    """Encode duplicate-free bridge material in one reproducible form."""

    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def semantic_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def strict_json_object(encoded: bytes, *, label: str) -> dict[str, object]:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains a duplicate key")
            result[key] = value
        return result

    try:
        document = json.loads(
            encoded,
            object_pairs_hook=no_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not strict JSON") from exc
    if not isinstance(document, dict):
        raise ValueError(f"{label} is not a JSON object")
    return document


@dataclass(frozen=True, slots=True)
class ConditionSessionBinding:
    session_id: str
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    condition_run_id: str
    evaluator_run_id: str
    frozen_manifest_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "session_id",
            "provider_contract_version",
            "plan_id",
            "host_run_id",
            "condition_run_id",
            "evaluator_run_id",
        ):
            if _SAFE_ID.fullmatch(cast(str, getattr(self, name))) is None:
                raise ValueError(f"condition session {name} is malformed")
        if _HEX64.fullmatch(self.frozen_manifest_sha256) is None:
            raise ValueError("condition session frozen-manifest identity is malformed")

    def to_document(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "provider_contract_version": self.provider_contract_version,
            "plan_id": self.plan_id,
            "host_run_id": self.host_run_id,
            "condition_run_id": self.condition_run_id,
            "evaluator_run_id": self.evaluator_run_id,
            "frozen_manifest_sha256": self.frozen_manifest_sha256,
        }


@dataclass(frozen=True, slots=True)
class ConditionBridgeFrame:
    protocol_version: str
    session_id: str
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    condition_run_id: str
    evaluator_run_id: str
    frozen_manifest_sha256: str
    sequence_number: int
    previous_frame_sha256: str
    event_id: str
    event_type: str
    payload: Mapping[str, object]
    payload_sha256: str
    frame_sha256: str

    @classmethod
    def create(
        cls,
        binding: ConditionSessionBinding,
        *,
        sequence_number: int,
        previous_frame_sha256: str,
        event_id: str,
        event_type: str,
        payload: Mapping[str, object],
    ) -> ConditionBridgeFrame:
        if type(sequence_number) is not int or not 1 <= sequence_number <= MAX_BRIDGE_FRAMES:
            raise RemoteBridgeError("bridge frame sequence is outside its finite envelope")
        if _HEX64.fullmatch(previous_frame_sha256) is None:
            raise RemoteBridgeError("bridge previous-frame hash is malformed")
        if _SAFE_ID.fullmatch(event_id) is None or _SAFE_ID.fullmatch(event_type) is None:
            raise RemoteBridgeError("bridge event identity or type is malformed")
        payload_document = dict(payload)
        payload_sha = semantic_sha256(payload_document)
        unsigned = {
            "protocol_version": BRIDGE_PROTOCOL_VERSION,
            **binding.to_document(),
            "sequence_number": sequence_number,
            "previous_frame_sha256": previous_frame_sha256,
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload_document,
            "payload_sha256": payload_sha,
        }
        return cls(
            protocol_version=BRIDGE_PROTOCOL_VERSION,
            session_id=binding.session_id,
            provider_contract_version=binding.provider_contract_version,
            plan_id=binding.plan_id,
            host_run_id=binding.host_run_id,
            condition_run_id=binding.condition_run_id,
            evaluator_run_id=binding.evaluator_run_id,
            frozen_manifest_sha256=binding.frozen_manifest_sha256,
            sequence_number=sequence_number,
            previous_frame_sha256=previous_frame_sha256,
            event_id=event_id,
            event_type=event_type,
            payload=payload_document,
            payload_sha256=payload_sha,
            frame_sha256=semantic_sha256(unsigned),
        )

    @classmethod
    def from_document(cls, raw: Mapping[str, object]) -> ConditionBridgeFrame:
        required = {
            "protocol_version",
            "session_id",
            "provider_contract_version",
            "plan_id",
            "host_run_id",
            "condition_run_id",
            "evaluator_run_id",
            "frozen_manifest_sha256",
            "sequence_number",
            "previous_frame_sha256",
            "event_id",
            "event_type",
            "payload",
            "payload_sha256",
            "frame_sha256",
        }
        if set(raw) != required or not isinstance(raw.get("payload"), dict):
            raise RemoteBridgeError("bridge frame fields are incomplete or unbound")
        try:
            binding = ConditionSessionBinding(
                session_id=cast(str, raw["session_id"]),
                provider_contract_version=cast(str, raw["provider_contract_version"]),
                plan_id=cast(str, raw["plan_id"]),
                host_run_id=cast(str, raw["host_run_id"]),
                condition_run_id=cast(str, raw["condition_run_id"]),
                evaluator_run_id=cast(str, raw["evaluator_run_id"]),
                frozen_manifest_sha256=cast(str, raw["frozen_manifest_sha256"]),
            )
            frame = cls.create(
                binding,
                sequence_number=cast(int, raw["sequence_number"]),
                previous_frame_sha256=cast(str, raw["previous_frame_sha256"]),
                event_id=cast(str, raw["event_id"]),
                event_type=cast(str, raw["event_type"]),
                payload=cast(dict[str, object], raw["payload"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RemoteBridgeError("bridge frame types are malformed") from exc
        if (
            raw["protocol_version"] != BRIDGE_PROTOCOL_VERSION
            or raw["payload_sha256"] != frame.payload_sha256
            or raw["frame_sha256"] != frame.frame_sha256
        ):
            raise RemoteBridgeError("bridge frame or payload hash changed")
        return frame

    def to_document(self) -> dict[str, object]:
        return {
            "protocol_version": self.protocol_version,
            "session_id": self.session_id,
            "provider_contract_version": self.provider_contract_version,
            "plan_id": self.plan_id,
            "host_run_id": self.host_run_id,
            "condition_run_id": self.condition_run_id,
            "evaluator_run_id": self.evaluator_run_id,
            "frozen_manifest_sha256": self.frozen_manifest_sha256,
            "sequence_number": self.sequence_number,
            "previous_frame_sha256": self.previous_frame_sha256,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "payload_sha256": self.payload_sha256,
            "frame_sha256": self.frame_sha256,
        }


@dataclass(frozen=True, slots=True)
class TranscriptEntry:
    direction: str
    frame: ConditionBridgeFrame

    def to_document(self) -> dict[str, object]:
        return {"direction": self.direction, "frame": self.frame.to_document()}


class FramedDuplexEndpoint:
    """One length-prefixed canonical stream with a single global hash chain."""

    def __init__(
        self,
        *,
        reader: BinaryIO,
        writer: BinaryIO,
        binding: ConditionSessionBinding,
        deadline_monotonic: float,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not math.isfinite(deadline_monotonic) or deadline_monotonic < monotonic():
            raise ValueError("bridge deadline is unavailable or already expired")
        self.reader = reader
        self.writer = writer
        self.binding = binding
        self.deadline_monotonic = deadline_monotonic
        self.monotonic = monotonic
        self._next_sequence = 1
        self._previous_hash = _ZERO_HASH
        self._event_ids: set[str] = set()
        self._entries: list[TranscriptEntry] = []
        self._transcript_bytes = 0
        self._write_closed = False

    @property
    def entries(self) -> tuple[TranscriptEntry, ...]:
        return tuple(self._entries)

    @property
    def previous_frame_sha256(self) -> str:
        return self._previous_hash

    @property
    def next_sequence(self) -> int:
        return self._next_sequence

    def _remaining(self) -> float:
        remaining = self.deadline_monotonic - self.monotonic()
        if remaining <= 0:
            raise RemoteBridgeDisconnected("bridge monotonic deadline expired")
        return remaining

    def _read_exact(self, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        fd = self.reader.fileno()
        while remaining:
            readable, _, _ = select.select([fd], [], [], self._remaining())
            if not readable:
                raise RemoteBridgeDisconnected("bridge read deadline expired")
            chunk = os.read(fd, remaining)
            if not chunk:
                raise RemoteBridgeDisconnected("bridge channel half-closed before terminal ack")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _record(self, direction: str, frame: ConditionBridgeFrame, encoded_bytes: int) -> None:
        if frame.sequence_number != self._next_sequence:
            raise RemoteBridgeReplay("bridge sequence was duplicated or out of order")
        if frame.previous_frame_sha256 != self._previous_hash:
            raise RemoteBridgeReplay("bridge frame hash chain diverged")
        if frame.event_id in self._event_ids:
            raise RemoteBridgeReplay("bridge event ID was replayed")
        if frame.session_id != self.binding.session_id or {
            "provider_contract_version": frame.provider_contract_version,
            "plan_id": frame.plan_id,
            "host_run_id": frame.host_run_id,
            "condition_run_id": frame.condition_run_id,
            "evaluator_run_id": frame.evaluator_run_id,
            "frozen_manifest_sha256": frame.frozen_manifest_sha256,
        } != {
            key: value for key, value in self.binding.to_document().items() if key != "session_id"
        }:
            raise RemoteBridgeError("bridge frame belongs to another condition session")
        projected_bytes = self._transcript_bytes + encoded_bytes
        if projected_bytes > MAX_BRIDGE_TRANSCRIPT_BYTES:
            raise RemoteBridgeError("bridge transcript exceeded its complete evidence cap")
        self._entries.append(TranscriptEntry(direction, frame))
        self._event_ids.add(frame.event_id)
        self._next_sequence += 1
        self._previous_hash = frame.frame_sha256
        self._transcript_bytes = projected_bytes

    def write_event(
        self,
        *,
        event_id: str,
        event_type: str,
        payload: Mapping[str, object],
    ) -> ConditionBridgeFrame:
        if self._write_closed:
            raise RemoteBridgeDisconnected("bridge write side is already closed")
        self._remaining()
        frame = ConditionBridgeFrame.create(
            self.binding,
            sequence_number=self._next_sequence,
            previous_frame_sha256=self._previous_hash,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        encoded = canonical_bytes(frame.to_document())
        if len(encoded) > MAX_BRIDGE_FRAME_BYTES:
            raise RemoteBridgeError("bridge frame exceeds its finite byte cap")
        packet = _HEADER.pack(len(encoded)) + encoded
        fd = self.writer.fileno()
        offset = 0
        while offset < len(packet):
            _, writable, _ = select.select([], [fd], [], self._remaining())
            if not writable:
                raise RemoteBridgeDisconnected("bridge write deadline expired")
            try:
                written = os.write(fd, packet[offset:])
            except BrokenPipeError as exc:
                raise RemoteBridgeDisconnected("bridge peer closed before admission") from exc
            if written <= 0:
                raise RemoteBridgeDisconnected("bridge write made no progress")
            offset += written
        self.writer.flush()
        self._record("sent", frame, len(packet))
        return frame

    def read_event(self, *, expected: set[str] | None = None) -> ConditionBridgeFrame:
        header = self._read_exact(_HEADER.size)
        (size,) = _HEADER.unpack(header)
        if not 0 < size <= MAX_BRIDGE_FRAME_BYTES:
            raise RemoteBridgeError("bridge frame length is outside its finite cap")
        encoded = self._read_exact(size)
        try:
            raw = strict_json_object(encoded, label="bridge frame")
            frame = ConditionBridgeFrame.from_document(raw)
        except ValueError as exc:
            raise RemoteBridgeError(str(exc)) from exc
        if expected is not None and frame.event_type not in expected:
            raise RemoteBridgeError("bridge event arrived in the wrong phase")
        self._record("received", frame, _HEADER.size + size)
        return frame

    def transcript_document(self, *, side: str) -> dict[str, object]:
        frames = [entry.to_document() for entry in self._entries]
        document: dict[str, object] = {
            "schema_version": BRIDGE_PROTOCOL_VERSION,
            "side": side,
            "binding": self.binding.to_document(),
            "frame_count": len(frames),
            "terminal_sequence": self._next_sequence - 1,
            "terminal_frame_sha256": self._previous_hash,
            "frame_chain_sha256": self.frame_chain_sha256(),
            "frames": frames,
        }
        document["transcript_sha256"] = semantic_sha256(document)
        return document

    def frame_chain_sha256(self, *, exclude_tail: int = 0) -> str:
        """Return the direction-independent identity shared by both peers.

        A local transcript records frames as ``sent`` or ``received``.  Those
        labels necessarily invert at the other peer, so they are evidence about
        the local transport but cannot establish cross-peer equality.  The
        ordered canonical frame documents are identical on both sides and form
        the authority-neutral transcript identity.
        """

        if type(exclude_tail) is not int or not 0 <= exclude_tail <= len(self._entries):
            raise ValueError("bridge transcript exclusion is malformed")
        stop = len(self._entries) - exclude_tail
        retained = self._entries[:stop] if stop else []
        frames = [entry.frame.to_document() for entry in retained]
        return semantic_sha256(
            {
                "schema_version": BRIDGE_PROTOCOL_VERSION,
                "binding": self.binding.to_document(),
                "frame_count": len(frames),
                "frames": frames,
            }
        )

    def half_close_write(self) -> None:
        if self._write_closed:
            return
        try:
            self.writer.flush()
        finally:
            self._write_closed = True


class CanonicalFrameRelay:
    """Validate and forward one duplex session without owning its policy.

    The relay is transport only. It cannot synthesize an admission response and has
    no observer or budget boundary. Every byte sent by the runtime is forwarded to
    the shared supervisor, and every response must come back from that supervisor.
    """

    _REMOTE_EVENTS: Final = frozenset(
        {
            "condition-session-hello",
            "model-call-reserve",
            "model-send-start",
            "model-response",
            "known-provider-error",
            "known-transport-error-no-provider-acceptance",
            "ambiguous-send",
            "response-known-accounting-incomplete",
            "browser-action-reserve",
            "browser-action-complete",
            "output-bytes-update",
            "process-exit",
            "completion",
            "raw-artifact-published",
            "runtime-client-complete",
            "condition-session-terminal",
        }
    )
    _SHARED_EVENTS: Final = frozenset(
        {
            "condition-session-accepted",
            "model-call-admitted",
            "model-call-rejected",
            "model-call-terminal",
            "browser-action-admitted",
            "browser-action-rejected",
            "browser-action-terminal",
            "output-bytes-admitted",
            "output-bytes-rejected",
            "process-exit-accepted",
            "completion-accepted",
            "raw-artifact-accepted",
            "runtime-client-complete-accepted",
            "condition-session-terminal-ack",
        }
    )

    def __init__(
        self,
        *,
        remote_reader: BinaryIO,
        remote_writer: BinaryIO,
        shared_reader: BinaryIO,
        shared_writer: BinaryIO,
        binding: ConditionSessionBinding,
        deadline_monotonic: float,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not math.isfinite(deadline_monotonic) or deadline_monotonic <= monotonic():
            raise ValueError("relay deadline is unavailable or expired")
        self.remote_reader = remote_reader
        self.remote_writer = remote_writer
        self.shared_reader = shared_reader
        self.shared_writer = shared_writer
        self.binding = binding
        self.deadline_monotonic = deadline_monotonic
        self.monotonic = monotonic
        self._next_sequence = 1
        self._previous_hash = _ZERO_HASH
        self._event_ids: set[str] = set()
        self._frames: list[dict[str, object]] = []
        self._bytes = 0
        self._terminal_acknowledged = False
        self._runtime_detached = False

    def _remaining(self) -> float:
        remaining = self.deadline_monotonic - self.monotonic()
        if remaining <= 0:
            raise RemoteBridgeDisconnected("condition relay deadline expired")
        return remaining

    def _read_exact(self, reader: BinaryIO, size: int) -> bytes:
        result = bytearray()
        while len(result) < size:
            readable, _, _ = select.select([reader.fileno()], [], [], self._remaining())
            if not readable:
                raise RemoteBridgeDisconnected("condition relay read deadline expired")
            chunk = os.read(reader.fileno(), size - len(result))
            if not chunk:
                raise RemoteBridgeDisconnected("condition relay half-closed before terminal ack")
            result.extend(chunk)
        return bytes(result)

    def _read_packet(self, reader: BinaryIO) -> tuple[bytes, ConditionBridgeFrame]:
        header = self._read_exact(reader, _HEADER.size)
        (size,) = _HEADER.unpack(header)
        if not 0 < size <= MAX_BRIDGE_FRAME_BYTES:
            raise RemoteBridgeError("condition relay frame length exceeds its finite cap")
        encoded = self._read_exact(reader, size)
        try:
            frame = ConditionBridgeFrame.from_document(
                strict_json_object(encoded, label="relayed condition frame")
            )
        except ValueError as exc:
            raise RemoteBridgeError(str(exc)) from exc
        return header + encoded, frame

    def _write_packet(self, writer: BinaryIO, packet: bytes) -> None:
        offset = 0
        while offset < len(packet):
            _, writable, _ = select.select([], [writer.fileno()], [], self._remaining())
            if not writable:
                raise RemoteBridgeDisconnected("condition relay write deadline expired")
            try:
                written = os.write(writer.fileno(), packet[offset:])
            except BrokenPipeError as exc:
                raise RemoteBridgeDisconnected(
                    "condition relay peer closed before terminal acknowledgement"
                ) from exc
            if written <= 0:
                raise RemoteBridgeDisconnected("condition relay write made no progress")
            offset += written
        writer.flush()

    def _validate(self, frame: ConditionBridgeFrame, *, direction: str) -> None:
        expected_events = (
            self._REMOTE_EVENTS if direction == "remote-to-shared" else self._SHARED_EVENTS
        )
        if frame.event_type not in expected_events:
            raise RemoteBridgeError("condition relay event arrived from the wrong authority")
        if (
            frame.sequence_number != self._next_sequence
            or frame.previous_frame_sha256 != self._previous_hash
        ):
            raise RemoteBridgeReplay("condition relay sequence/hash chain was replayed")
        if frame.event_id in self._event_ids:
            raise RemoteBridgeReplay("condition relay event identity was replayed")
        if {
            "session_id": frame.session_id,
            "provider_contract_version": frame.provider_contract_version,
            "plan_id": frame.plan_id,
            "host_run_id": frame.host_run_id,
            "condition_run_id": frame.condition_run_id,
            "evaluator_run_id": frame.evaluator_run_id,
            "frozen_manifest_sha256": frame.frozen_manifest_sha256,
        } != self.binding.to_document():
            raise RemoteBridgeError("condition relay frame belongs to another session")
        projected = self._bytes + _HEADER.size + len(canonical_bytes(frame.to_document()))
        if projected > MAX_BRIDGE_TRANSCRIPT_BYTES:
            raise RemoteBridgeError("condition relay transcript exceeded its bounded cap")
        self._frames.append({"direction": direction, "frame": frame.to_document()})
        self._event_ids.add(frame.event_id)
        self._next_sequence += 1
        self._previous_hash = frame.frame_sha256
        self._bytes = projected
        if frame.event_type == "condition-session-terminal-ack":
            self._terminal_acknowledged = True
        if frame.event_type == "runtime-client-complete-accepted":
            self._runtime_detached = True

    def serve(self, *, stop_after_runtime_detach: bool = False) -> dict[str, object]:
        """Relay until runtime detachment or the exact terminal acknowledgement."""

        while not self._terminal_acknowledged and not (
            stop_after_runtime_detach and self._runtime_detached
        ):
            readable, _, _ = select.select(
                [self.remote_reader.fileno(), self.shared_reader.fileno()],
                [],
                [],
                self._remaining(),
            )
            if not readable:
                raise RemoteBridgeDisconnected("condition relay deadline expired")
            if len(readable) != 1:
                raise RemoteBridgeError("condition relay observed simultaneous ambiguous frames")
            if readable[0] == self.remote_reader.fileno():
                packet, frame = self._read_packet(self.remote_reader)
                self._validate(frame, direction="remote-to-shared")
                self._write_packet(self.shared_writer, packet)
            else:
                packet, frame = self._read_packet(self.shared_reader)
                self._validate(frame, direction="shared-to-remote")
                self._write_packet(self.remote_writer, packet)
        return self.transcript_document()

    def transcript_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "schema_version": BRIDGE_PROTOCOL_VERSION,
            "side": "host-transparent-relay",
            "binding": self.binding.to_document(),
            "authoritative_accounting": False,
            "admission_decisions_synthesized": 0,
            "frame_count": len(self._frames),
            "terminal_sequence": self._next_sequence - 1,
            "terminal_frame_sha256": self._previous_hash,
            "frame_chain_sha256": semantic_sha256(
                {
                    "schema_version": BRIDGE_PROTOCOL_VERSION,
                    "binding": self.binding.to_document(),
                    "frame_count": len(self._frames),
                    "frames": [entry["frame"] for entry in self._frames],
                }
            ),
            "runtime_detached": self._runtime_detached,
            "terminal_acknowledged": self._terminal_acknowledged,
            "frames": self._frames,
        }
        document["transcript_sha256"] = semantic_sha256(document)
        return document

    def persist_transcript(self, path: Path) -> None:
        """Atomically retain the bounded relay journal at one exact private path."""

        encoded = canonical_bytes(self.transcript_document())
        if len(encoded) > MAX_BRIDGE_TRANSCRIPT_BYTES:
            raise RemoteBridgeError("condition relay journal exceeded its evidence cap")
        parent = path.parent.resolve(strict=True)
        candidate = path.resolve(strict=False)
        if candidate.parent != parent or path.is_symlink():
            raise RemoteBridgeError("condition relay journal path is unsafe")
        temporary = parent / f".{path.name}.tmp"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
        )
        try:
            offset = 0
            while offset < len(encoded):
                offset += os.write(descriptor, encoded[offset:])
            os.fsync(descriptor)
        except BaseException:
            with contextlib.suppress(OSError):
                temporary.unlink()
            raise
        finally:
            os.close(descriptor)
        os.replace(temporary, candidate)
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _host_round_trip(
        self,
        *,
        event_id: str,
        event_type: str,
        payload: Mapping[str, object],
        expected_response: str,
    ) -> ConditionBridgeFrame:
        if not self._runtime_detached or self._terminal_acknowledged:
            raise RemoteBridgeError("host evidence continuation is outside its exact phase")
        frame = ConditionBridgeFrame.create(
            self.binding,
            sequence_number=self._next_sequence,
            previous_frame_sha256=self._previous_hash,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        packet = _HEADER.pack(len(canonical_bytes(frame.to_document()))) + canonical_bytes(
            frame.to_document()
        )
        self._validate(frame, direction="remote-to-shared")
        self._write_packet(self.shared_writer, packet)
        response_packet, response = self._read_packet(self.shared_reader)
        self._validate(response, direction="shared-to-remote")
        if response.event_type != expected_response:
            raise RemoteBridgeError("shared supervisor returned the wrong host continuation reply")
        # The response has no remaining remote process to receive it, but retaining
        # the exact packet in the relay transcript proves what shared control sent.
        del response_packet
        return response

    def finish_host_evidence(
        self,
        *,
        exit_code: int,
        completed: bool,
        answer: str | None,
        error: str,
        raw_manifest_sha256: str,
        raw_receipt_sha256: str,
        remote_journal_bytes: int,
        remote_journal_file_sha256: str,
        remote_journal_sha256: str,
        remote_terminal_sequence: int,
        remote_terminal_frame_sha256: str,
        remote_frame_chain_sha256: str,
    ) -> dict[str, object]:
        """Publish host-derived terminal evidence, then perform one terminal handshake."""

        if type(exit_code) is not int or type(completed) is not bool:
            raise RemoteBridgeError("host terminal process evidence is malformed")
        if answer is not None and not isinstance(answer, str):
            raise RemoteBridgeError("host terminal answer is malformed")
        if (
            not isinstance(error, str)
            or type(remote_journal_bytes) is not int
            or not 0 < remote_journal_bytes <= MAX_BRIDGE_TRANSCRIPT_BYTES
            or type(remote_terminal_sequence) is not int
            or remote_terminal_sequence < 1
            or not all(
                _HEX64.fullmatch(value) is not None
                for value in (
                    raw_manifest_sha256,
                    raw_receipt_sha256,
                    remote_journal_file_sha256,
                    remote_journal_sha256,
                    remote_terminal_frame_sha256,
                    remote_frame_chain_sha256,
                )
            )
        ):
            raise RemoteBridgeError("host terminal raw evidence is malformed")
        self._host_round_trip(
            event_id="host.process.exit",
            event_type="process-exit",
            payload={"exit_code": exit_code},
            expected_response="process-exit-accepted",
        )
        self._host_round_trip(
            event_id="host.session.completion",
            event_type="completion",
            payload={"completed": completed, "answer": answer, "error": error},
            expected_response="completion-accepted",
        )
        self._host_round_trip(
            event_id="host.raw.published",
            event_type="raw-artifact-published",
            payload={
                "manifest_sha256": raw_manifest_sha256,
                "receipt_sha256": raw_receipt_sha256,
            },
            expected_response="raw-artifact-accepted",
        )
        prior_hash = self._previous_hash
        prior_count = self._next_sequence - 1
        prior_chain_sha = semantic_sha256(
            {
                "schema_version": BRIDGE_PROTOCOL_VERSION,
                "binding": self.binding.to_document(),
                "frame_count": len(self._frames),
                "frames": [entry["frame"] for entry in self._frames],
            }
        )
        terminal = self._host_round_trip(
            event_id="host.session.terminal",
            event_type="condition-session-terminal",
            payload={
                "prior_frame_sha256": prior_hash,
                "prior_frame_count": prior_count,
                "remote_journal_sha256": remote_journal_sha256,
                "remote_journal_file_sha256": remote_journal_file_sha256,
                "remote_journal_bytes": remote_journal_bytes,
                "remote_terminal_sequence": remote_terminal_sequence,
                "remote_terminal_frame_sha256": remote_terminal_frame_sha256,
                "remote_frame_chain_sha256": remote_frame_chain_sha256,
                "prior_frame_chain_sha256": prior_chain_sha,
            },
            expected_response="condition-session-terminal-ack",
        )
        if terminal.payload.get("accepted") is not True or not self._terminal_acknowledged:
            raise RemoteBridgeError("shared supervisor did not terminalize the host relay")
        return self.transcript_document()


@dataclass(slots=True)
class AcceptedPrivateConditionChannel:
    """One accepted private IPC connection and its held stream objects."""

    endpoint: FramedDuplexEndpoint
    connection: socket.socket
    reader: BinaryIO
    writer: BinaryIO

    def close(self) -> None:
        for value in (self.reader, self.writer, self.connection):
            with contextlib.suppress(OSError):
                value.close()


@dataclass(slots=True)
class PrivateConditionListener:
    """Host-owned Unix-socket admission relay under one exact attempt root."""

    listener: socket.socket
    socket_path: Path
    manifest_path: Path
    binding: ConditionSessionBinding
    deadline_monotonic: float
    expected_peer_uid: int

    @classmethod
    def create(
        cls,
        *,
        supervisor_root: Path,
        attempt_root: Path,
        binding: ConditionSessionBinding,
        transaction_root_identity: str,
        deadline_monotonic: float,
        remote_journal_relative_path: str,
        expected_peer_uid: int | None = None,
    ) -> PrivateConditionListener:
        root = supervisor_root.resolve(strict=True)
        attempt = attempt_root.resolve(strict=True)
        metadata = root.stat(follow_symlinks=False)
        if (
            supervisor_root.is_symlink()
            or root.parent != attempt
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise RemoteBridgeError("private condition supervisor root is unsafe")
        if _HEX64.fullmatch(transaction_root_identity) is None:
            raise RemoteBridgeError("private condition transaction identity is malformed")
        if not math.isfinite(deadline_monotonic) or deadline_monotonic <= time.monotonic():
            raise RemoteBridgeError("private condition deadline is unavailable")
        journal_relative = Path(remote_journal_relative_path)
        if journal_relative.is_absolute() or ".." in journal_relative.parts:
            raise RemoteBridgeError("private remote journal path escaped its attempt")
        socket_path = root / "condition-admission.sock"
        manifest_path = root / "condition-admission-binding.json"
        if os.path.lexists(socket_path) or os.path.lexists(manifest_path):
            raise RemoteBridgeError("private condition channel identity already exists")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(socket_path.as_posix())
            os.chmod(socket_path, 0o600, follow_symlinks=False)
            listener.listen(1)
            socket_metadata = socket_path.stat(follow_symlinks=False)
            document = {
                "schema_version": "1.0.0",
                "protocol_version": BRIDGE_PROTOCOL_VERSION,
                "binding": binding.to_document(),
                "transaction_root_identity": transaction_root_identity,
                "socket_relative_path": socket_path.name,
                "socket_device": socket_metadata.st_dev,
                "socket_inode": socket_metadata.st_ino,
                "socket_uid": socket_metadata.st_uid,
                "socket_mode": stat.S_IMODE(socket_metadata.st_mode),
                "socket_link_count": socket_metadata.st_nlink,
                "deadline_monotonic": deadline_monotonic,
                "remote_journal_relative_path": remote_journal_relative_path,
            }
            encoded = canonical_bytes(document)
            descriptor = os.open(
                manifest_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                offset = 0
                while offset < len(encoded):
                    written = os.write(descriptor, encoded[offset:])
                    if written <= 0:
                        raise RemoteBridgeError("private condition binding write made no progress")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except BaseException:
            listener.close()
            for path in (manifest_path, socket_path):
                with contextlib.suppress(FileNotFoundError):
                    path.unlink()
            raise
        return cls(
            listener=listener,
            socket_path=socket_path,
            manifest_path=manifest_path,
            binding=binding,
            deadline_monotonic=deadline_monotonic,
            expected_peer_uid=(os.getuid() if expected_peer_uid is None else expected_peer_uid),
        )

    def _remaining(self) -> float:
        remaining = self.deadline_monotonic - time.monotonic()
        if remaining <= 0:
            raise RemoteBridgeDisconnected("private condition accept deadline expired")
        return remaining

    def accept(self) -> AcceptedPrivateConditionChannel:
        readable, _, _ = select.select([self.listener], [], [], self._remaining())
        if not readable:
            raise RemoteBridgeDisconnected("private condition client never connected")
        connection, _ = self.listener.accept()
        try:
            peer_uid: int | None = None
            getpeereid = getattr(connection, "getpeereid", None)
            if callable(getpeereid):
                peer_uid = cast(tuple[int, int], getpeereid())[0]
            elif hasattr(socket, "SO_PEERCRED"):
                credentials = connection.getsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_PEERCRED,
                    struct.calcsize("3i"),
                )
                _pid, peer_uid, _gid = struct.unpack("3i", credentials)
            if peer_uid is not None and peer_uid != self.expected_peer_uid:
                raise RemoteBridgeError("private condition peer ownership changed")
            reader = cast(BinaryIO, connection.makefile("rb", buffering=0))
            writer = cast(BinaryIO, connection.makefile("wb", buffering=0))
            return AcceptedPrivateConditionChannel(
                endpoint=FramedDuplexEndpoint(
                    reader=reader,
                    writer=writer,
                    binding=self.binding,
                    deadline_monotonic=self.deadline_monotonic,
                ),
                connection=connection,
                reader=reader,
                writer=writer,
            )
        except BaseException:
            connection.close()
            raise

    def close(self, *, destroy_private_binding: bool = True) -> None:
        self.listener.close()
        with contextlib.suppress(FileNotFoundError):
            self.socket_path.unlink()
        if destroy_private_binding:
            with contextlib.suppress(FileNotFoundError):
                self.manifest_path.unlink()


def _string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise RemoteBridgeError(f"bridge payload {key} is not a string")
    return value


def _integer(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if type(value) is not int or value < 0:
        raise RemoteBridgeError(f"bridge payload {key} is not a non-negative integer")
    return value


def provider_request_document(request: ProviderRequest) -> dict[str, object]:
    return {
        "role": request.role.value,
        "model": request.model,
        "input_tokens": request.input_tokens,
        "max_output_tokens": request.max_output_tokens,
        "service_tier": request.service_tier,
        "implicit_transport_retries": request.implicit_transport_retries,
        "retry_kind": request.retry_kind,
    }


def provider_request_from_document(payload: Mapping[str, object]) -> ProviderRequest:
    try:
        return ProviderRequest(
            role=ModelRole(_string(payload, "role")),
            model=_string(payload, "model"),
            input_tokens=_integer(payload, "input_tokens"),
            max_output_tokens=_integer(payload, "max_output_tokens"),
            service_tier=_string(payload, "service_tier"),
            implicit_transport_retries=_integer(payload, "implicit_transport_retries"),
            retry_kind=_string(payload, "retry_kind"),
        )
    except ValueError as exc:
        raise RemoteBridgeError("bridge provider request is invalid") from exc


def usage_document(usage: ProviderResponseUsage) -> dict[str, object]:
    return {
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "service_tier": usage.service_tier,
    }


def usage_from_document(payload: Mapping[str, object]) -> ProviderResponseUsage:
    try:
        return ProviderResponseUsage(
            input_tokens=_integer(payload, "input_tokens"),
            cached_input_tokens=_integer(payload, "cached_input_tokens"),
            output_tokens=_integer(payload, "output_tokens"),
            service_tier=_string(payload, "service_tier"),
        )
    except ValueError as exc:
        raise RemoteBridgeError("bridge provider usage is invalid") from exc


@dataclass(frozen=True, slots=True)
class ConditionSessionTerminalReceipt:
    binding: ConditionSessionBinding
    terminal_sequence: int
    terminal_frame_sha256: str
    transcript_sha256: str
    shared_accounting_sha256: str
    remote_journal_bytes: int
    remote_journal_file_sha256: str
    remote_journal_sha256: str
    remote_terminal_sequence: int
    remote_terminal_frame_sha256: str
    remote_frame_chain_sha256: str
    raw_manifest_sha256: str
    raw_receipt_sha256: str
    terminal_acknowledged: bool
    receipt_sha256: str

    def to_document(self) -> dict[str, object]:
        return {
            "schema_version": BRIDGE_PROTOCOL_VERSION,
            "binding": self.binding.to_document(),
            "terminal_sequence": self.terminal_sequence,
            "terminal_frame_sha256": self.terminal_frame_sha256,
            "transcript_sha256": self.transcript_sha256,
            "shared_accounting_sha256": self.shared_accounting_sha256,
            "remote_journal_bytes": self.remote_journal_bytes,
            "remote_journal_file_sha256": self.remote_journal_file_sha256,
            "remote_journal_sha256": self.remote_journal_sha256,
            "remote_terminal_sequence": self.remote_terminal_sequence,
            "remote_terminal_frame_sha256": self.remote_terminal_frame_sha256,
            "remote_frame_chain_sha256": self.remote_frame_chain_sha256,
            "raw_manifest_sha256": self.raw_manifest_sha256,
            "raw_receipt_sha256": self.raw_receipt_sha256,
            "terminal_acknowledged": self.terminal_acknowledged,
            "receipt_sha256": self.receipt_sha256,
        }


class ConditionSessionSupervisor:
    """Serve one remote event client through the shared authoritative observer."""

    def __init__(
        self,
        endpoint: FramedDuplexEndpoint,
        observer: ConditionEventObserver,
        *,
        accounting_document: Callable[[], Mapping[str, object]],
    ) -> None:
        self.endpoint = endpoint
        self.observer = observer
        self.accounting_document = accounting_document
        self._terminal = False
        self._remote_journal_sha256: str | None = None
        self._remote_journal_bytes: int | None = None
        self._remote_journal_file_sha256: str | None = None
        self._remote_terminal_sequence: int | None = None
        self._remote_terminal_frame_sha256: str | None = None
        self._remote_frame_chain_sha256: str | None = None
        self._raw_manifest_sha256: str | None = None
        self._raw_receipt_sha256: str | None = None

    def _write(
        self,
        request: ConditionBridgeFrame,
        event_type: str,
        payload: Mapping[str, object],
    ) -> ConditionBridgeFrame:
        return self.endpoint.write_event(
            event_id=f"{request.event_id}.reply",
            event_type=event_type,
            payload=payload,
        )

    def _read_model_outcome(self, call_id: str) -> ConditionModelResponse:
        started = self.endpoint.read_event(expected={"model-send-start"})
        if _string(started.payload, "call_id") != call_id:
            raise RemoteBridgeError("model send-start belongs to another call")
        outcome = self.endpoint.read_event(
            expected={
                "model-response",
                "known-provider-error",
                "known-transport-error-no-provider-acceptance",
                "ambiguous-send",
                "response-known-accounting-incomplete",
            }
        )
        if _string(outcome.payload, "call_id") != call_id:
            raise RemoteBridgeError("model reconciliation belongs to another call")
        if outcome.event_type == "model-response":
            usage_raw = outcome.payload.get("usage")
            if not isinstance(usage_raw, dict):
                raise ConditionResponseAccountingIncomplete(
                    "remote response lacks a typed usage receipt"
                )
            return ConditionModelResponse(
                content=_string(outcome.payload, "content"),
                usage=usage_from_document(usage_raw),
            )
        message = _string(outcome.payload, "error_type")
        if outcome.event_type == "known-provider-error":
            raise ConditionKnownProviderError(message)
        if outcome.event_type == "known-transport-error-no-provider-acceptance":
            raise ConditionKnownTransportError(message)
        if outcome.event_type == "response-known-accounting-incomplete":
            raise ConditionResponseAccountingIncomplete(message)
        raise ConditionAmbiguousSend(message)

    def _model_call(self, frame: ConditionBridgeFrame) -> None:
        call_id = _string(frame.payload, "call_id")
        logical_call_id = _string(frame.payload, "logical_call_id")
        request_raw = frame.payload.get("request")
        if not isinstance(request_raw, dict):
            raise RemoteBridgeError("model admission lacks a typed request")
        event = ConditionModelCall(
            call_id=call_id,
            logical_call_id=logical_call_id,
            request=provider_request_from_document(request_raw),
        )

        def admit() -> None:
            self._write(
                frame,
                "model-call-admitted",
                {"call_id": call_id, "logical_call_id": logical_call_id},
            )

        try:
            self.observer.model_call(
                event,
                lambda: self._read_model_outcome(call_id),
                before_send=admit,
            )
        except ProviderBudgetExceeded as exc:
            # A pre-admission rejection has not emitted an admit frame.
            if not any(
                entry.frame.event_id == f"{frame.event_id}.reply" for entry in self.endpoint.entries
            ):
                self._write(
                    frame,
                    "model-call-rejected",
                    {"call_id": call_id, "reason": type(exc).__name__},
                )
                return
            self.endpoint.write_event(
                event_id=f"{frame.event_id}.terminal",
                event_type="model-call-terminal",
                payload={"call_id": call_id, "status": "budget-failed-after-send"},
            )
        except ConditionKnownProviderError:
            self.endpoint.write_event(
                event_id=f"{frame.event_id}.terminal",
                event_type="model-call-terminal",
                payload={"call_id": call_id, "status": "known-provider-error"},
            )
        except ConditionKnownTransportError:
            self.endpoint.write_event(
                event_id=f"{frame.event_id}.terminal",
                event_type="model-call-terminal",
                payload={"call_id": call_id, "status": "known-transport-no-acceptance"},
            )
        except ConditionResponseAccountingIncomplete:
            self.endpoint.write_event(
                event_id=f"{frame.event_id}.terminal",
                event_type="model-call-terminal",
                payload={"call_id": call_id, "status": "response-accounting-incomplete"},
            )
        except ConditionAmbiguousSend:
            self.endpoint.write_event(
                event_id=f"{frame.event_id}.terminal",
                event_type="model-call-terminal",
                payload={"call_id": call_id, "status": "ambiguous-send"},
            )
        except RemoteBridgeDisconnected:
            # A lost channel after admission is deliberately not rewritten as zero activity.
            raise
        else:
            self.endpoint.write_event(
                event_id=f"{frame.event_id}.terminal",
                event_type="model-call-terminal",
                payload={"call_id": call_id, "status": "response-reconciled"},
            )

    def _browser_action(self, frame: ConditionBridgeFrame) -> None:
        action_id = _string(frame.payload, "action_id")

        def perform() -> None:
            self._write(frame, "browser-action-admitted", {"action_id": action_id})
            completed = self.endpoint.read_event(expected={"browser-action-complete"})
            if _string(completed.payload, "action_id") != action_id:
                raise RemoteBridgeError("browser reconciliation belongs to another action")
            if completed.payload.get("completed") is not True:
                raise RemoteBridgeError("remote browser action did not complete")

        try:
            self.observer.browser_action(action_id=action_id, perform=perform)
        except ProviderBudgetExceeded as exc:
            if not any(
                entry.frame.event_id == f"{frame.event_id}.reply" for entry in self.endpoint.entries
            ):
                self._write(
                    frame,
                    "browser-action-rejected",
                    {"action_id": action_id, "reason": type(exc).__name__},
                )
                return
            raise
        self.endpoint.write_event(
            event_id=f"{frame.event_id}.terminal",
            event_type="browser-action-terminal",
            payload={"action_id": action_id, "status": "completed"},
        )

    def _simple_event(self, frame: ConditionBridgeFrame) -> None:
        if frame.event_type == "output-bytes-update":
            total = _integer(frame.payload, "total_bytes")
            try:
                self.observer.output_bytes(total_bytes=total)
            except ProviderBudgetExceeded as exc:
                self._write(
                    frame,
                    "output-bytes-rejected",
                    {"accepted": False, "reason": type(exc).__name__},
                )
                return
            reply = "output-bytes-admitted"
        elif frame.event_type == "process-exit":
            exit_code = frame.payload.get("exit_code")
            if type(exit_code) is not int:
                raise RemoteBridgeError("process exit code is not an integer")
            self.observer.process_exit(exit_code=exit_code)
            reply = "process-exit-accepted"
        elif frame.event_type == "completion":
            completed = frame.payload.get("completed")
            answer = frame.payload.get("answer")
            error = frame.payload.get("error")
            if (
                type(completed) is not bool
                or (answer is not None and not isinstance(answer, str))
                or not isinstance(error, str)
            ):
                raise RemoteBridgeError("completion payload is malformed")
            self.observer.completion(completed=completed, answer=answer, error=error)
            reply = "completion-accepted"
        elif frame.event_type == "raw-artifact-published":
            manifest_sha = _string(frame.payload, "manifest_sha256")
            receipt_sha = _string(frame.payload, "receipt_sha256")
            self.observer.raw_artifact_published(
                manifest_sha256=manifest_sha,
                receipt_sha256=receipt_sha,
            )
            self._raw_manifest_sha256 = manifest_sha
            self._raw_receipt_sha256 = receipt_sha
            reply = "raw-artifact-accepted"
        elif frame.event_type == "runtime-client-complete":
            prefix_sequence = _integer(frame.payload, "prefix_sequence")
            prefix_frame_sha = _string(frame.payload, "prefix_frame_sha256")
            prefix_chain_sha = _string(frame.payload, "prefix_frame_chain_sha256")
            prefix_journal_sha = _string(frame.payload, "prefix_journal_sha256")
            if (
                set(frame.payload)
                != {
                    "host_evidence_pending",
                    "remote_authoritative_boundary",
                    "prefix_sequence",
                    "prefix_frame_sha256",
                    "prefix_frame_chain_sha256",
                    "prefix_journal_sha256",
                }
                or frame.payload.get("host_evidence_pending") is not True
                or frame.payload.get("remote_authoritative_boundary") is not False
                or prefix_sequence != frame.sequence_number - 1
                or prefix_frame_sha != frame.previous_frame_sha256
                or prefix_chain_sha != self.endpoint.frame_chain_sha256(exclude_tail=1)
                or _HEX64.fullmatch(prefix_journal_sha) is None
            ):
                raise RemoteBridgeError("runtime detachment contradicts host evidence ownership")
            reply = "runtime-client-complete-accepted"
        else:  # pragma: no cover - caller controls the exact dispatch set
            raise RemoteBridgeError("unsupported simple bridge event")
        self._write(frame, reply, {"accepted": True})
        if frame.event_type == "runtime-client-complete":
            self._remote_terminal_sequence = self.endpoint.next_sequence - 1
            self._remote_terminal_frame_sha256 = self.endpoint.previous_frame_sha256
            self._remote_frame_chain_sha256 = self.endpoint.frame_chain_sha256()

    def serve(self) -> ConditionSessionTerminalReceipt:
        hello = self.endpoint.read_event(expected={"condition-session-hello"})
        if hello.payload != {
            "accounting_owner": "shared-condition-event-observer",
            "remote_authoritative_boundary": False,
            "zero_retry": True,
        }:
            raise RemoteBridgeError("condition session hello contradicts accounting ownership")
        self._write(hello, "condition-session-accepted", {"accepted": True})
        while not self._terminal:
            frame = self.endpoint.read_event()
            if frame.event_type == "model-call-reserve":
                self._model_call(frame)
            elif frame.event_type == "browser-action-reserve":
                self._browser_action(frame)
            elif frame.event_type in {
                "output-bytes-update",
                "process-exit",
                "completion",
                "raw-artifact-published",
                "runtime-client-complete",
            }:
                self._simple_event(frame)
            elif frame.event_type == "condition-session-terminal":
                prior_hash = _string(frame.payload, "prior_frame_sha256")
                prior_count = _integer(frame.payload, "prior_frame_count")
                journal_sha = _string(frame.payload, "remote_journal_sha256")
                journal_file_sha = _string(frame.payload, "remote_journal_file_sha256")
                journal_bytes = _integer(frame.payload, "remote_journal_bytes")
                remote_sequence = _integer(frame.payload, "remote_terminal_sequence")
                remote_frame_sha = _string(frame.payload, "remote_terminal_frame_sha256")
                remote_chain_sha = _string(frame.payload, "remote_frame_chain_sha256")
                prior_chain_sha = _string(frame.payload, "prior_frame_chain_sha256")
                expected_remote_sequence = (
                    self._remote_terminal_sequence
                    if self._remote_terminal_sequence is not None
                    else frame.sequence_number - 1
                )
                expected_remote_frame_sha = (
                    self._remote_terminal_frame_sha256
                    if self._remote_terminal_frame_sha256 is not None
                    else frame.previous_frame_sha256
                )
                expected_remote_chain_sha = (
                    self._remote_frame_chain_sha256
                    if self._remote_frame_chain_sha256 is not None
                    else self.endpoint.frame_chain_sha256(exclude_tail=1)
                )
                if (
                    prior_hash != frame.previous_frame_sha256
                    or prior_count != frame.sequence_number - 1
                    or _HEX64.fullmatch(journal_sha) is None
                    or _HEX64.fullmatch(journal_file_sha) is None
                    or not 0 < journal_bytes <= MAX_BRIDGE_TRANSCRIPT_BYTES
                    or remote_sequence != expected_remote_sequence
                    or remote_frame_sha != expected_remote_frame_sha
                    or remote_chain_sha != expected_remote_chain_sha
                    or prior_chain_sha != self.endpoint.frame_chain_sha256(exclude_tail=1)
                ):
                    raise RemoteBridgeError("remote terminal journal identity drifted")
                self._remote_journal_sha256 = journal_sha
                self._remote_journal_file_sha256 = journal_file_sha
                self._remote_journal_bytes = journal_bytes
                self._remote_terminal_sequence = remote_sequence
                self._remote_terminal_frame_sha256 = remote_frame_sha
                self._remote_frame_chain_sha256 = remote_chain_sha
                self._write(
                    frame,
                    "condition-session-terminal-ack",
                    {
                        "accepted": True,
                        "terminal_request_chain_sha256": self.endpoint.frame_chain_sha256(),
                    },
                )
                self._terminal = True
            else:
                raise RemoteBridgeError("condition session event is unsupported or out of order")
        accounting_sha = semantic_sha256(dict(self.accounting_document()))
        transcript_sha = self.endpoint.frame_chain_sha256()
        assert self._remote_journal_sha256 is not None
        assert self._remote_journal_bytes is not None
        assert self._remote_journal_file_sha256 is not None
        assert self._remote_terminal_sequence is not None
        assert self._remote_terminal_frame_sha256 is not None
        assert self._remote_frame_chain_sha256 is not None
        assert self._raw_manifest_sha256 is not None
        assert self._raw_receipt_sha256 is not None
        receipt_values = {
            "schema_version": BRIDGE_PROTOCOL_VERSION,
            "binding": self.endpoint.binding.to_document(),
            "terminal_sequence": self.endpoint.next_sequence - 1,
            "terminal_frame_sha256": self.endpoint.previous_frame_sha256,
            "transcript_sha256": transcript_sha,
            "shared_accounting_sha256": accounting_sha,
            "remote_journal_bytes": self._remote_journal_bytes,
            "remote_journal_file_sha256": self._remote_journal_file_sha256,
            "remote_journal_sha256": self._remote_journal_sha256,
            "remote_terminal_sequence": self._remote_terminal_sequence,
            "remote_terminal_frame_sha256": self._remote_terminal_frame_sha256,
            "remote_frame_chain_sha256": self._remote_frame_chain_sha256,
            "raw_manifest_sha256": self._raw_manifest_sha256,
            "raw_receipt_sha256": self._raw_receipt_sha256,
            "terminal_acknowledged": True,
        }
        return ConditionSessionTerminalReceipt(
            binding=self.endpoint.binding,
            terminal_sequence=self.endpoint.next_sequence - 1,
            terminal_frame_sha256=self.endpoint.previous_frame_sha256,
            transcript_sha256=transcript_sha,
            shared_accounting_sha256=accounting_sha,
            remote_journal_bytes=self._remote_journal_bytes,
            remote_journal_file_sha256=self._remote_journal_file_sha256,
            remote_journal_sha256=self._remote_journal_sha256,
            remote_terminal_sequence=self._remote_terminal_sequence,
            remote_terminal_frame_sha256=self._remote_terminal_frame_sha256,
            remote_frame_chain_sha256=self._remote_frame_chain_sha256,
            raw_manifest_sha256=self._raw_manifest_sha256,
            raw_receipt_sha256=self._raw_receipt_sha256,
            terminal_acknowledged=True,
            receipt_sha256=semantic_sha256(receipt_values),
        )


@dataclass(frozen=True, slots=True)
class ValidatedConditionBridgeEvidence:
    """Cross-peer identity of one fully acknowledged duplex condition session."""

    binding: ConditionSessionBinding
    frame_count: int
    runtime_prefix_frame_count: int
    shared_transcript_file_sha256: str
    shared_transcript_sha256: str
    shared_frame_chain_sha256: str
    remote_journal_file_sha256: str
    remote_journal_sha256: str
    relay_prefix_file_sha256: str
    relay_prefix_sha256: str
    relay_transcript_file_sha256: str
    relay_transcript_sha256: str
    runtime_detachment_file_sha256: str
    host_terminal_receipt_file_sha256: str
    host_terminal_receipt_sha256: str
    shared_terminal_receipt_file_sha256: str
    shared_terminal_receipt_sha256: str
    evidence_binding_sha256: str


def condition_session_id(run_id: str) -> str:
    """Derive the one stable duplex identity for an immutable condition run."""

    if _SAFE_ID.fullmatch(run_id) is None:
        raise ValueError("condition run identity is malformed")
    value = f"SESSION-{run_id}"
    if _SAFE_ID.fullmatch(value) is None:
        raise ValueError("derived condition session identity is malformed")
    return value


def expected_condition_bridge_evidence(
    *,
    transaction_root: Path,
    raw_root: Path,
    run_id: str,
) -> ConditionBridgeEvidence:
    """Return the exact shared/host evidence layout for one remote session."""

    root = transaction_root.resolve(strict=True)
    raw = raw_root.resolve(strict=True)
    try:
        raw.relative_to(root)
    except ValueError as exc:
        raise ValueError("condition raw root escaped its transaction") from exc
    attempt_root = raw.parent
    shared_root = root / "control-private" / "condition-bridges" / run_id
    return ConditionBridgeEvidence(
        protocol_version=BRIDGE_PROTOCOL_VERSION,
        session_id=condition_session_id(run_id),
        shared_transcript_path=shared_root / "shared-authoritative-transcript.json",
        remote_journal_path=raw / "duplex-remote-event-journal.json",
        relay_prefix_path=raw / "duplex-transcript-prefix.json",
        relay_transcript_path=attempt_root / "duplex-transcript-manifest.json",
        runtime_detachment_path=raw / "duplex-runtime-detached.json",
        host_terminal_receipt_path=(attempt_root / "condition-session-terminal-receipt.json"),
        shared_terminal_receipt_path=shared_root / "shared-terminal-receipt.json",
    )


def _read_bounded_bridge_file(path: Path) -> bytes:
    """Read one current-user evidence file without following its final link."""

    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RemoteBridgeError("condition bridge evidence is unavailable") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) & 0o022
            or not 0 < before.st_size <= MAX_BRIDGE_TRANSCRIPT_BYTES
        ):
            raise RemoteBridgeError("condition bridge evidence identity is unsafe")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise RemoteBridgeError("condition bridge evidence was truncated")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise RemoteBridgeError("condition bridge evidence exceeded its admitted size")
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_uid,
            stat.S_IMODE(after.st_mode),
            after.st_nlink,
            after.st_size,
        ) != (
            before.st_dev,
            before.st_ino,
            before.st_uid,
            stat.S_IMODE(before.st_mode),
            before.st_nlink,
            before.st_size,
        ):
            raise RemoteBridgeError("condition bridge evidence changed while held")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _load_bridge_document(
    path: Path,
    *,
    label: str,
    reader: Callable[[Path], bytes],
) -> tuple[dict[str, object], bytes, str]:
    encoded = reader(path)
    if not 0 < len(encoded) <= MAX_BRIDGE_TRANSCRIPT_BYTES:
        raise RemoteBridgeError(f"{label} exceeds its bounded evidence envelope")
    try:
        document = strict_json_object(encoded, label=label)
    except ValueError as exc:
        raise RemoteBridgeError(str(exc)) from exc
    return document, encoded, hashlib.sha256(encoded).hexdigest()


def _load_bridge_schema(repository: Path, name: str) -> dict[str, object]:
    path = repository / "schemas" / name
    try:
        return strict_json_object(path.read_bytes(), label=f"{name} schema")
    except (OSError, ValueError) as exc:
        raise RemoteBridgeError(f"{name} schema is unavailable or malformed") from exc


def _validate_schema(
    repository: Path,
    name: str,
    document: Mapping[str, object],
    *,
    label: str,
) -> None:
    schema = _load_bridge_schema(repository, name)
    errors = sorted(
        Draft202012Validator(
            schema,
            registry=local_schema_registry(repository / "schemas"),
        ).iter_errors(document),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    if errors:
        raise RemoteBridgeError(f"{label} failed its exact schema: {errors[0].message}")


def _frame_chain_identity(
    binding: ConditionSessionBinding,
    frames: list[dict[str, object]],
) -> str:
    return semantic_sha256(
        {
            "schema_version": BRIDGE_PROTOCOL_VERSION,
            "binding": binding.to_document(),
            "frame_count": len(frames),
            "frames": frames,
        }
    )


def _remote_prefix_document(
    binding: ConditionSessionBinding,
    entries: list[dict[str, object]],
) -> dict[str, object]:
    frames: list[dict[str, object]] = []
    for entry in entries:
        direction = cast(str, entry["direction"])
        frames.append(
            {
                "direction": "sent" if direction == "received" else "received",
                "frame": entry["frame"],
            }
        )
    frame_documents = [cast(dict[str, object], entry["frame"]) for entry in frames]
    document: dict[str, object] = {
        "schema_version": BRIDGE_PROTOCOL_VERSION,
        "side": "remote-mirror",
        "binding": binding.to_document(),
        "frame_count": len(frames),
        "terminal_sequence": len(frames),
        "terminal_frame_sha256": cast(dict[str, object], frames[-1]["frame"])["frame_sha256"],
        "frame_chain_sha256": _frame_chain_identity(binding, frame_documents),
        "frames": frames,
    }
    document["transcript_sha256"] = semantic_sha256(document)
    return document


def _validate_transcript_document(
    repository: Path,
    document: Mapping[str, object],
    *,
    expected_side: str,
    expected_binding: ConditionSessionBinding,
    terminal_acknowledged: bool | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    _validate_schema(
        repository,
        "t09-condition-duplex-transcript.schema.json",
        document,
        label=f"{expected_side} condition transcript",
    )
    common = {
        "schema_version",
        "side",
        "binding",
        "frame_count",
        "terminal_sequence",
        "terminal_frame_sha256",
        "frame_chain_sha256",
        "frames",
        "transcript_sha256",
    }
    relay_only = {
        "authoritative_accounting",
        "admission_decisions_synthesized",
        "runtime_detached",
        "terminal_acknowledged",
    }
    expected_fields = common | relay_only if expected_side == "host-transparent-relay" else common
    if (
        set(document) != expected_fields
        or document.get("schema_version") != BRIDGE_PROTOCOL_VERSION
        or document.get("side") != expected_side
        or document.get("binding") != expected_binding.to_document()
    ):
        raise RemoteBridgeError(f"{expected_side} condition transcript identity drifted")
    if expected_side == "host-transparent-relay" and (
        document.get("authoritative_accounting") is not False
        or document.get("admission_decisions_synthesized") != 0
        or document.get("runtime_detached") is not True
        or document.get("terminal_acknowledged") is not terminal_acknowledged
    ):
        raise RemoteBridgeError("host relay claimed policy, admission, or the wrong phase")
    raw_entries = document.get("frames")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise RemoteBridgeError("condition transcript has no retained frames")
    entries = cast(list[dict[str, object]], raw_entries)
    frame_documents: list[dict[str, object]] = []
    prior = _ZERO_HASH
    event_ids: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or set(entry) != {"direction", "frame"}:
            raise RemoteBridgeError("condition transcript frame envelope is malformed")
        raw_frame = entry.get("frame")
        if not isinstance(raw_frame, dict):
            raise RemoteBridgeError("condition transcript frame is malformed")
        frame = ConditionBridgeFrame.from_document(raw_frame)
        if (
            frame.sequence_number != index
            or frame.previous_frame_sha256 != prior
            or frame.event_id in event_ids
        ):
            raise RemoteBridgeReplay("condition transcript sequence, chain, or event replayed")
        frame_binding = {
            "session_id": frame.session_id,
            "provider_contract_version": frame.provider_contract_version,
            "plan_id": frame.plan_id,
            "host_run_id": frame.host_run_id,
            "condition_run_id": frame.condition_run_id,
            "evaluator_run_id": frame.evaluator_run_id,
            "frozen_manifest_sha256": frame.frozen_manifest_sha256,
        }
        if frame_binding != expected_binding.to_document():
            raise RemoteBridgeError("condition transcript contains a cross-session frame")
        remote_event = frame.event_type in CanonicalFrameRelay._REMOTE_EVENTS
        shared_event = frame.event_type in CanonicalFrameRelay._SHARED_EVENTS
        direction = entry.get("direction")
        expected_direction = {
            "shared-authoritative": "received" if remote_event else "sent",
            "remote-mirror": "sent" if remote_event else "received",
            "host-transparent-relay": ("remote-to-shared" if remote_event else "shared-to-remote"),
        }[expected_side]
        if remote_event == shared_event or direction != expected_direction:
            raise RemoteBridgeError("condition transcript reverses an authority direction")
        event_ids.add(frame.event_id)
        prior = frame.frame_sha256
        frame_documents.append(frame.to_document())
    unsigned = dict(document)
    transcript_sha = unsigned.pop("transcript_sha256", None)
    if (
        document.get("frame_count") != len(entries)
        or document.get("terminal_sequence") != len(entries)
        or document.get("terminal_frame_sha256") != prior
        or document.get("frame_chain_sha256")
        != _frame_chain_identity(expected_binding, frame_documents)
        or transcript_sha != semantic_sha256(unsigned)
    ):
        raise RemoteBridgeError("condition transcript aggregate identity drifted")
    return entries, frame_documents


def _require_reply(
    frames: list[ConditionBridgeFrame],
    index: int,
    request: ConditionBridgeFrame,
    expected_type: str,
) -> ConditionBridgeFrame:
    if index >= len(frames):
        raise RemoteBridgeError("condition transcript ended before an admission response")
    response = frames[index]
    if response.event_type != expected_type or response.event_id != f"{request.event_id}.reply":
        raise RemoteBridgeError("condition transcript response does not bind its request")
    return response


def _validate_complete_session_order(
    entries: list[dict[str, object]],
    *,
    binding: ConditionSessionBinding,
    raw_manifest_sha256: str,
    raw_receipt_sha256: str,
) -> int:
    frames = [
        ConditionBridgeFrame.from_document(cast(dict[str, object], entry["frame"]))
        for entry in entries
    ]
    if len(frames) < 12:
        raise RemoteBridgeError("complete condition session transcript is too small")
    hello, accepted = frames[:2]
    if (
        hello.event_type != "condition-session-hello"
        or hello.payload
        != {
            "accounting_owner": "shared-condition-event-observer",
            "remote_authoritative_boundary": False,
            "zero_retry": True,
        }
        or accepted.event_type != "condition-session-accepted"
        or accepted.event_id != f"{hello.event_id}.reply"
        or accepted.payload != {"accepted": True}
    ):
        raise RemoteBridgeError("condition session handshake contradicts sole accounting")
    call_ids: set[str] = set()
    logical_ids: set[str] = set()
    action_ids: set[str] = set()
    index = 2
    detach_index = -1
    while index < len(frames):
        frame = frames[index]
        if frame.event_type == "model-call-reserve":
            call_id = _string(frame.payload, "call_id")
            logical_id = _string(frame.payload, "logical_call_id")
            request = frame.payload.get("request")
            if call_id in call_ids or logical_id in logical_ids or not isinstance(request, dict):
                raise RemoteBridgeReplay("condition model identity was replayed")
            provider_request_from_document(request)
            admitted = _require_reply(frames, index + 1, frame, "model-call-admitted")
            if admitted.payload != {"call_id": call_id, "logical_call_id": logical_id}:
                raise RemoteBridgeError("model admission response identity drifted")
            started = frames[index + 2]
            outcome = frames[index + 3]
            terminal = frames[index + 4]
            allowed_outcomes = {
                "model-response",
                "known-provider-error",
                "known-transport-error-no-provider-acceptance",
                "ambiguous-send",
                "response-known-accounting-incomplete",
            }
            if (
                started.event_type != "model-send-start"
                or started.payload != {"call_id": call_id}
                or outcome.event_type not in allowed_outcomes
                or outcome.payload.get("call_id") != call_id
                or terminal.event_type != "model-call-terminal"
                or terminal.event_id != f"{frame.event_id}.terminal"
                or terminal.payload.get("call_id") != call_id
            ):
                raise RemoteBridgeError("model effect did not follow exact shared admission")
            if outcome.event_type == "model-response":
                usage = outcome.payload.get("usage")
                if not isinstance(usage, dict):
                    raise RemoteBridgeError("model response lacks typed usage")
                usage_from_document(usage)
            call_ids.add(call_id)
            logical_ids.add(logical_id)
            index += 5
            continue
        if frame.event_type == "browser-action-reserve":
            action_id = _string(frame.payload, "action_id")
            if action_id in action_ids:
                raise RemoteBridgeReplay("condition browser identity was replayed")
            admitted = _require_reply(frames, index + 1, frame, "browser-action-admitted")
            completed = frames[index + 2]
            terminal = frames[index + 3]
            if (
                admitted.payload != {"action_id": action_id}
                or completed.event_type != "browser-action-complete"
                or completed.payload != {"action_id": action_id, "completed": True}
                or terminal.event_type != "browser-action-terminal"
                or terminal.event_id != f"{frame.event_id}.terminal"
                or terminal.payload != {"action_id": action_id, "status": "completed"}
            ):
                raise RemoteBridgeError("browser effect did not follow exact shared admission")
            action_ids.add(action_id)
            index += 4
            continue
        if frame.event_type == "output-bytes-update":
            _integer(frame.payload, "total_bytes")
            response = _require_reply(frames, index + 1, frame, "output-bytes-admitted")
            if response.payload != {"accepted": True}:
                raise RemoteBridgeError("output growth lacks exact shared admission")
            index += 2
            continue
        if frame.event_type == "runtime-client-complete":
            response = _require_reply(
                frames,
                index + 1,
                frame,
                "runtime-client-complete-accepted",
            )
            preceding = frames[:index]
            preceding_documents = [item.to_document() for item in preceding]
            remote_prefix = _remote_prefix_document(binding, entries[:index])
            if frame.payload != {
                "host_evidence_pending": True,
                "remote_authoritative_boundary": False,
                "prefix_sequence": index,
                "prefix_frame_sha256": preceding[-1].frame_sha256,
                "prefix_frame_chain_sha256": _frame_chain_identity(
                    binding,
                    preceding_documents,
                ),
                "prefix_journal_sha256": remote_prefix["transcript_sha256"],
            } or response.payload != {"accepted": True}:
                raise RemoteBridgeError("runtime detachment prefix identity drifted")
            detach_index = index + 1
            index += 2
            break
        raise RemoteBridgeError("runtime transcript contains an unadmitted effect or phase")
    if detach_index < 0:
        raise RemoteBridgeError("condition session lacks runtime detachment")
    expected_tail = (
        "process-exit",
        "process-exit-accepted",
        "completion",
        "completion-accepted",
        "raw-artifact-published",
        "raw-artifact-accepted",
        "condition-session-terminal",
        "condition-session-terminal-ack",
    )
    tail = frames[index:]
    if tuple(frame.event_type for frame in tail) != expected_tail:
        raise RemoteBridgeError("host-derived terminal evidence is incomplete or reordered")
    for request_index in (0, 2, 4, 6):
        request = tail[request_index]
        response = tail[request_index + 1]
        if response.event_id != f"{request.event_id}.reply":
            raise RemoteBridgeError("host terminal response does not bind its request")
    raw = tail[4]
    if raw.payload != {
        "manifest_sha256": raw_manifest_sha256,
        "receipt_sha256": raw_receipt_sha256,
    }:
        raise RemoteBridgeError("duplex transcript does not bind accepted raw evidence")
    terminal = tail[6]
    terminal_ack = tail[7]
    preceding_terminal = frames[: len(frames) - 2]
    if (
        terminal.payload.get("prior_frame_sha256") != preceding_terminal[-1].frame_sha256
        or terminal.payload.get("prior_frame_count") != len(preceding_terminal)
        or terminal.payload.get("prior_frame_chain_sha256")
        != _frame_chain_identity(
            binding,
            [item.to_document() for item in preceding_terminal],
        )
        or terminal_ack.payload
        != {
            "accepted": True,
            "terminal_request_chain_sha256": _frame_chain_identity(
                binding,
                [item.to_document() for item in frames[:-1]],
            ),
        }
    ):
        raise RemoteBridgeError("condition terminal hash chain or acknowledgement drifted")
    return detach_index + 1


def validate_condition_bridge_evidence(
    repository: Path,
    evidence: ConditionBridgeEvidence,
    *,
    expected_binding: ConditionSessionBinding,
    raw_manifest_sha256: str,
    raw_receipt_sha256: str,
    shared_accounting: Mapping[str, object],
    reader: Callable[[Path], bytes] | None = None,
) -> ValidatedConditionBridgeEvidence:
    """Validate and cross-bind every side of one completed remote condition stream."""

    if (
        evidence.protocol_version != BRIDGE_PROTOCOL_VERSION
        or evidence.session_id != expected_binding.session_id
        or _HEX64.fullmatch(raw_manifest_sha256) is None
        or _HEX64.fullmatch(raw_receipt_sha256) is None
    ):
        raise RemoteBridgeError("condition bridge evidence selector is malformed")
    paths = {
        "shared transcript": evidence.shared_transcript_path,
        "remote journal": evidence.remote_journal_path,
        "relay prefix": evidence.relay_prefix_path,
        "relay transcript": evidence.relay_transcript_path,
        "runtime detachment": evidence.runtime_detachment_path,
        "host terminal receipt": evidence.host_terminal_receipt_path,
        "shared terminal receipt": evidence.shared_terminal_receipt_path,
    }
    if len(set(paths.values())) != len(paths):
        raise RemoteBridgeError("condition bridge evidence roles reuse one path")
    selected_reader = reader or _read_bounded_bridge_file
    documents: dict[str, dict[str, object]] = {}
    encoded: dict[str, bytes] = {}
    file_hashes: dict[str, str] = {}
    for label, path in paths.items():
        document, data, digest = _load_bridge_document(
            path,
            label=label,
            reader=selected_reader,
        )
        documents[label] = document
        encoded[label] = data
        file_hashes[label] = digest

    shared_entries, shared_frames = _validate_transcript_document(
        repository,
        documents["shared transcript"],
        expected_side="shared-authoritative",
        expected_binding=expected_binding,
        terminal_acknowledged=None,
    )
    remote_entries, remote_frames = _validate_transcript_document(
        repository,
        documents["remote journal"],
        expected_side="remote-mirror",
        expected_binding=expected_binding,
        terminal_acknowledged=None,
    )
    prefix_entries, prefix_frames = _validate_transcript_document(
        repository,
        documents["relay prefix"],
        expected_side="host-transparent-relay",
        expected_binding=expected_binding,
        terminal_acknowledged=False,
    )
    relay_entries, relay_frames = _validate_transcript_document(
        repository,
        documents["relay transcript"],
        expected_side="host-transparent-relay",
        expected_binding=expected_binding,
        terminal_acknowledged=True,
    )
    runtime_prefix_count = _validate_complete_session_order(
        shared_entries,
        binding=expected_binding,
        raw_manifest_sha256=raw_manifest_sha256,
        raw_receipt_sha256=raw_receipt_sha256,
    )
    if (
        relay_frames != shared_frames
        or remote_frames != shared_frames[:runtime_prefix_count]
        or prefix_frames != shared_frames[:runtime_prefix_count]
        or relay_entries[:runtime_prefix_count] != prefix_entries
        or [entry["frame"] for entry in remote_entries]
        != [entry["frame"] for entry in prefix_entries]
    ):
        raise RemoteBridgeError("shared, remote, and relay transcript frames diverged")

    detachment = documents["runtime detachment"]
    _validate_schema(
        repository,
        "t09-condition-runtime-detachment.schema.json",
        detachment,
        label="runtime detachment",
    )
    remote = documents["remote journal"]
    if (
        detachment.get("terminal_sequence") != remote.get("terminal_sequence")
        or detachment.get("terminal_frame_sha256") != remote.get("terminal_frame_sha256")
        or detachment.get("frame_chain_sha256") != remote.get("frame_chain_sha256")
        or detachment.get("remote_journal_bytes") != len(encoded["remote journal"])
        or detachment.get("remote_journal_file_sha256") != file_hashes["remote journal"]
        or detachment.get("remote_journal_sha256") != remote.get("transcript_sha256")
    ):
        raise RemoteBridgeError("runtime detachment does not bind its remote journal")

    shared_terminal = documents["shared terminal receipt"]
    host_terminal = documents["host terminal receipt"]
    _validate_schema(
        repository,
        "t09-condition-session-terminal-receipt.schema.json",
        shared_terminal,
        label="shared condition terminal receipt",
    )
    _validate_schema(
        repository,
        "t09-condition-host-terminal-receipt.schema.json",
        host_terminal,
        label="host condition terminal receipt",
    )
    shared_unsigned = dict(shared_terminal)
    shared_receipt_sha = shared_unsigned.pop("receipt_sha256", None)
    host_unsigned = dict(host_terminal)
    host_receipt_sha = host_unsigned.pop("receipt_sha256", None)
    shared_transcript = documents["shared transcript"]
    relay_transcript = documents["relay transcript"]
    relay_prefix = documents["relay prefix"]
    if (
        shared_receipt_sha != semantic_sha256(shared_unsigned)
        or host_receipt_sha != semantic_sha256(host_unsigned)
        or shared_terminal.get("binding") != expected_binding.to_document()
        or host_terminal.get("binding") != expected_binding.to_document()
        or shared_terminal.get("terminal_sequence") != shared_transcript.get("terminal_sequence")
        or shared_terminal.get("terminal_frame_sha256")
        != shared_transcript.get("terminal_frame_sha256")
        or shared_terminal.get("transcript_sha256") != shared_transcript.get("frame_chain_sha256")
        or shared_terminal.get("shared_accounting_sha256")
        != semantic_sha256(dict(shared_accounting))
        or shared_terminal.get("remote_journal_bytes") != len(encoded["remote journal"])
        or shared_terminal.get("remote_journal_file_sha256") != file_hashes["remote journal"]
        or shared_terminal.get("remote_journal_sha256") != remote.get("transcript_sha256")
        or shared_terminal.get("remote_terminal_sequence") != remote.get("terminal_sequence")
        or shared_terminal.get("remote_terminal_frame_sha256")
        != remote.get("terminal_frame_sha256")
        or shared_terminal.get("remote_frame_chain_sha256") != remote.get("frame_chain_sha256")
        or shared_terminal.get("raw_manifest_sha256") != raw_manifest_sha256
        or shared_terminal.get("raw_receipt_sha256") != raw_receipt_sha256
        or shared_terminal.get("terminal_acknowledged") is not True
        or host_terminal.get("runtime_prefix_transcript_sha256")
        != relay_prefix.get("transcript_sha256")
        or host_terminal.get("remote_event_journal_file_sha256") != file_hashes["remote journal"]
        or host_terminal.get("remote_event_journal_semantic_sha256")
        != remote.get("transcript_sha256")
        or host_terminal.get("relay_transcript_sha256") != relay_transcript.get("transcript_sha256")
        or host_terminal.get("terminal_sequence") != relay_transcript.get("terminal_sequence")
        or host_terminal.get("terminal_frame_sha256")
        != relay_transcript.get("terminal_frame_sha256")
        or host_terminal.get("raw_manifest_sha256") != raw_manifest_sha256
        or host_terminal.get("raw_receipt_sha256") != raw_receipt_sha256
        or host_terminal.get("shared_accounting_owner") != "ConditionEventObserver"
        or host_terminal.get("remote_authoritative_boundary") is not False
        or host_terminal.get("terminal_acknowledged") is not True
    ):
        raise RemoteBridgeError("condition bridge terminal evidence is not cross-bound")
    binding_document = {
        "protocol_version": BRIDGE_PROTOCOL_VERSION,
        "binding": expected_binding.to_document(),
        "frame_count": len(shared_frames),
        "runtime_prefix_frame_count": runtime_prefix_count,
        "shared_transcript_file_sha256": file_hashes["shared transcript"],
        "shared_transcript_sha256": shared_transcript["transcript_sha256"],
        "shared_frame_chain_sha256": shared_transcript["frame_chain_sha256"],
        "remote_journal_file_sha256": file_hashes["remote journal"],
        "remote_journal_sha256": remote["transcript_sha256"],
        "relay_prefix_file_sha256": file_hashes["relay prefix"],
        "relay_prefix_sha256": relay_prefix["transcript_sha256"],
        "relay_transcript_file_sha256": file_hashes["relay transcript"],
        "relay_transcript_sha256": relay_transcript["transcript_sha256"],
        "runtime_detachment_file_sha256": file_hashes["runtime detachment"],
        "host_terminal_receipt_file_sha256": file_hashes["host terminal receipt"],
        "host_terminal_receipt_sha256": host_receipt_sha,
        "shared_terminal_receipt_file_sha256": file_hashes["shared terminal receipt"],
        "shared_terminal_receipt_sha256": shared_receipt_sha,
    }
    return ValidatedConditionBridgeEvidence(
        binding=expected_binding,
        frame_count=len(shared_frames),
        runtime_prefix_frame_count=runtime_prefix_count,
        shared_transcript_file_sha256=file_hashes["shared transcript"],
        shared_transcript_sha256=cast(str, shared_transcript["transcript_sha256"]),
        shared_frame_chain_sha256=cast(str, shared_transcript["frame_chain_sha256"]),
        remote_journal_file_sha256=file_hashes["remote journal"],
        remote_journal_sha256=cast(str, remote["transcript_sha256"]),
        relay_prefix_file_sha256=file_hashes["relay prefix"],
        relay_prefix_sha256=cast(str, relay_prefix["transcript_sha256"]),
        relay_transcript_file_sha256=file_hashes["relay transcript"],
        relay_transcript_sha256=cast(str, relay_transcript["transcript_sha256"]),
        runtime_detachment_file_sha256=file_hashes["runtime detachment"],
        host_terminal_receipt_file_sha256=file_hashes["host terminal receipt"],
        host_terminal_receipt_sha256=host_receipt_sha,
        shared_terminal_receipt_file_sha256=file_hashes["shared terminal receipt"],
        shared_terminal_receipt_sha256=shared_receipt_sha,
        evidence_binding_sha256=semantic_sha256(binding_document),
    )


_RETAINED_REQUIRED_MANIFEST_FIELDS: Final = frozenset(
    {
        "schema_version",
        "manifest_id",
        "plan_id",
        "host_run_id",
        "qualification_id",
        "qualification_count",
        "build_count",
        "image_materialization_policy",
        "source_contract_sha256",
        "clean_package_commit",
        "plan_sha256",
        "execution_contract_sha256",
        "runtime_contract_sha256",
        "command_manifests_sha256",
        "provider_entry_receipt_sha256",
        "owned_instance_identity_sha256",
        "provider_preflight_started_at_epoch",
        "owned_lambda_started_at_epoch",
        "first_pair_started_at_epoch",
        "launch_slot",
        "launch_count",
        "replacement_image_id",
        "python_interpreter_path",
        "python_interpreter_sha256",
        "runtime_preflight_sha256",
        "offline_preflight_sha256",
        "core_suppression_preflight_sha256",
        "sealing_primitives_preflight_sha256",
        "browser_preflight_sha256",
        "evaluator_materialization_sha256",
        "final_image_file_hashes_sha256",
        "model_metadata_receipt_sha256",
        "model_metadata_credential_scan_sha256",
        "model_metadata_request_count",
        "model_task_request_count",
        "task_browser_action_count",
        "actual_credential_exposure_detected",
        "credential_safety_stop_detected",
        "core_safety_stop_detected",
        "local_finalizer_qualification_sha256",
        "local_finalizer_interpreter_sha256",
        "local_finalizer_interpreter_dependency_manifest_sha256",
        "local_finalizer_interpreter_dependency_tree_sha256",
        "local_finalizer_evaluator_dependency_tree_sha256",
        "command_argv_sha256s",
        "pair_diffs",
        "attempt_order",
        "empirical_entry_crossed",
        "post_entry_code_science_image_freeze",
        "source_receipts",
    }
)


@dataclass(frozen=True, slots=True)
class ValidatedFullFrozenManifest:
    schema_version: str
    file_sha256: str
    projection: Mapping[str, object]
    projection_sha256: str
    full_field_count: int


def load_full_frozen_manifest(path: Path) -> tuple[dict[str, object], str]:
    metadata = path.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or not path.is_file()
        or metadata.st_nlink != 1
        or metadata.st_size > MAX_FROZEN_MANIFEST_BYTES
    ):
        raise AdapterFailure("full frozen manifest is unsafe or oversized")
    encoded = path.read_bytes()
    try:
        document = strict_json_object(encoded, label="full frozen manifest")
    except ValueError as exc:
        raise AdapterFailure(str(exc)) from exc
    return document, hashlib.sha256(encoded).hexdigest()


def validate_full_dynamic_frozen_manifest(
    repository: Path,
    path: Path,
    *,
    contract: T09ProviderContract,
    expected_projection: Mapping[str, object],
) -> ValidatedFullFrozenManifest:
    """Validate the retained full manifest through an explicit schema handler."""

    document, file_sha = load_full_frozen_manifest(path)
    version = document.get("schema_version")
    handlers = {RETAINED_FROZEN_MANIFEST_SCHEMA_VERSION: _validate_retained_manifest_v0_1}
    handler = handlers.get(version) if isinstance(version, str) else None
    if handler is None:
        raise AdapterFailure("full frozen manifest schema version has no explicit handler")
    schema_path = repository / "schemas/t09-full-dynamic-frozen-manifest.schema.json"
    try:
        schema = strict_json_object(schema_path.read_bytes(), label="frozen manifest schema")
        Draft202012Validator(
            schema,
            registry=local_schema_registry(repository / "schemas"),
        ).validate(document)
    except Exception as exc:
        raise AdapterFailure("full frozen manifest failed its exact schema") from exc
    projection = handler(document, contract=contract, expected_projection=expected_projection)
    return ValidatedFullFrozenManifest(
        schema_version=cast(str, version),
        file_sha256=file_sha,
        projection=projection,
        projection_sha256=semantic_sha256(projection),
        full_field_count=len(document),
    )


def _validate_retained_manifest_v0_1(
    document: Mapping[str, object],
    *,
    contract: T09ProviderContract,
    expected_projection: Mapping[str, object],
) -> dict[str, object]:
    missing = sorted(_RETAINED_REQUIRED_MANIFEST_FIELDS - set(document))
    if missing:
        raise AdapterFailure("full frozen manifest omitted retained fields: " + ", ".join(missing))
    if (
        document.get("manifest_id") != contract.frozen_run_manifest_id
        or document.get("plan_id") != contract.plan_id
        or document.get("host_run_id") != contract.host_run_id
        or document.get("qualification_id") != contract.active_image_qualification_id
        or document.get("qualification_count") != 1
        or document.get("attempt_order") != list(contract.run_ids)
        or document.get("empirical_entry_crossed") is not False
        or document.get("post_entry_code_science_image_freeze") is not True
        or document.get("model_task_request_count") != 0
        or document.get("task_browser_action_count") != 0
        or document.get("actual_credential_exposure_detected") is not False
        or document.get("credential_safety_stop_detected") is not False
        or document.get("core_safety_stop_detected") is not False
    ):
        raise AdapterFailure("full frozen manifest contradicts its selected package or phase")
    argv_hashes = document.get("command_argv_sha256s")
    pair_diffs = document.get("pair_diffs")
    source_receipts = document.get("source_receipts")
    if (
        not isinstance(argv_hashes, list)
        or len(argv_hashes) != len(contract.run_ids)
        or any(
            not isinstance(value, str) or _HEX64.fullmatch(value) is None for value in argv_hashes
        )
        or not isinstance(pair_diffs, list)
        or not pair_diffs
        or any(
            not isinstance(value, dict) or value.get("valid") is not True for value in pair_diffs
        )
        or not isinstance(source_receipts, dict)
        or len(source_receipts) < 8
    ):
        raise AdapterFailure("full frozen manifest lacks retained command/pair/source evidence")
    projection = dict(expected_projection)
    for key, expected in projection.items():
        if document.get(key) != expected:
            raise AdapterFailure(f"full frozen manifest projection drifted at {key}")
    projection["schema_version"] = RETAINED_FROZEN_MANIFEST_SCHEMA_VERSION
    projection["full_manifest_validated"] = True
    projection["full_field_count"] = len(document)
    return projection


def validate_postfreeze_receipt(
    path: Path,
    *,
    contract: T09ProviderContract,
    manifest_sha256: str,
) -> dict[str, object]:
    try:
        document = strict_json_object(path.read_bytes(), label="post-freeze receipt")
    except (OSError, ValueError) as exc:
        raise AdapterFailure("post-freeze receipt is unavailable or malformed") from exc
    if document.get("schema_version") != RETAINED_FROZEN_MANIFEST_SCHEMA_VERSION:
        raise AdapterFailure("post-freeze receipt schema has no explicit handler")
    if (
        document.get("plan_id") != contract.plan_id
        or document.get("host_run_id") != contract.host_run_id
        or document.get("frozen_run_manifest_sha256") != manifest_sha256
        or document.get("frozen_manifest_published_before_empirical_clock") is not True
        or document.get("model_task_request_count") != 0
        or document.get("task_browser_action_count") != 0
    ):
        raise AdapterFailure("post-freeze receipt does not bind the full manifest")
    return document


__all__ = [
    "BRIDGE_PROTOCOL_VERSION",
    "MAX_BRIDGE_FRAMES",
    "MAX_BRIDGE_FRAME_BYTES",
    "MAX_BRIDGE_TRANSCRIPT_BYTES",
    "RETAINED_FROZEN_MANIFEST_SCHEMA_VERSION",
    "AcceptedPrivateConditionChannel",
    "CanonicalFrameRelay",
    "ConditionBridgeFrame",
    "ConditionSessionBinding",
    "ConditionSessionSupervisor",
    "ConditionSessionTerminalReceipt",
    "FramedDuplexEndpoint",
    "PrivateConditionListener",
    "RemoteBridgeDisconnected",
    "RemoteBridgeError",
    "RemoteBridgeReplay",
    "ValidatedConditionBridgeEvidence",
    "ValidatedFullFrozenManifest",
    "canonical_bytes",
    "condition_session_id",
    "expected_condition_bridge_evidence",
    "load_full_frozen_manifest",
    "provider_request_document",
    "provider_request_from_document",
    "semantic_sha256",
    "strict_json_object",
    "usage_document",
    "usage_from_document",
    "validate_condition_bridge_evidence",
    "validate_full_dynamic_frozen_manifest",
    "validate_postfreeze_receipt",
]
