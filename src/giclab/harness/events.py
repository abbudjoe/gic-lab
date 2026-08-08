"""Append-only JSONL event storage with sequence and schema validation."""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from giclab.registry import load_json, loads_json

from .models import (
    SCHEMA_VERSION,
    AdapterEventType,
    EventProvenance,
    EventType,
    HarnessEvent,
    JsonValue,
    RunIdentity,
    thaw_json,
)

EVENT_SCHEMA = "schemas/harness-event.schema.json"
CONTROL_SOURCE = "giclab-harness"
_ADAPTER_EVENT_TYPES = frozenset(EventType(item.value) for item in AdapterEventType)


class EventStreamError(ValueError):
    """Raised when an event stream is malformed or violates append-only identity."""


def event_document(event: HarnessEvent) -> dict[str, Any]:
    """Return the stable JSON representation of one event."""

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": event.run_id,
        "attempt": event.attempt,
        "sequence": event.sequence,
        "timestamp_utc": event.timestamp_utc,
        "event_type": event.event_type.value,
        "source": event.source,
        "provenance": event.provenance.value,
        "payload": {key: thaw_json(value) for key, value in event.payload.items()},
    }


def _event_from_document(value: Mapping[str, Any], line_number: int) -> HarnessEvent:
    expected = {
        "schema_version",
        "run_id",
        "attempt",
        "sequence",
        "timestamp_utc",
        "event_type",
        "source",
        "provenance",
        "payload",
    }
    unknown = value.keys() - expected
    missing = expected - value.keys()
    if unknown or missing:
        raise EventStreamError(
            f"event line {line_number} has missing={sorted(missing)} unknown={sorted(unknown)}"
        )
    if value["schema_version"] != SCHEMA_VERSION:
        raise EventStreamError(f"event line {line_number} has unsupported schema_version")
    for key in ("run_id", "timestamp_utc", "event_type", "source", "provenance"):
        if not isinstance(value[key], str):
            raise EventStreamError(f"event line {line_number} {key} must be a string")
    for key in ("attempt", "sequence"):
        if type(value[key]) is not int:
            raise EventStreamError(f"event line {line_number} {key} must be an integer")
    payload = value.get("payload")
    if not isinstance(payload, dict) or any(not isinstance(key, str) for key in payload):
        raise EventStreamError(f"event line {line_number} payload must be an object")
    try:
        return HarnessEvent(
            run_id=value["run_id"],
            attempt=value["attempt"],
            sequence=value["sequence"],
            timestamp_utc=value["timestamp_utc"],
            event_type=EventType(value["event_type"]),
            source=value["source"],
            provenance=EventProvenance(value["provenance"]),
            payload=cast(dict[str, JsonValue], payload),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EventStreamError(f"invalid event line {line_number}: {exc}") from exc


def _decode_documents(content: bytes, *, path: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        if not raw_line.strip():
            raise EventStreamError(f"{path}: blank event line {line_number} is forbidden")
        try:
            value = loads_json(raw_line)
        except ValueError as exc:
            raise EventStreamError(f"{path}: invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise EventStreamError(f"{path}: event line {line_number} must be an object")
        documents.append(cast(dict[str, Any], value))
    return documents


def _typed_events(documents: list[dict[str, Any]], *, path: Path) -> tuple[HarnessEvent, ...]:
    events = tuple(
        _event_from_document(document, line_number)
        for line_number, document in enumerate(documents, start=1)
    )
    if not events:
        return events
    identity = (events[0].run_id, events[0].attempt)
    previous = 0
    for event in events:
        if (event.run_id, event.attempt) != identity:
            raise EventStreamError(f"{path}: event stream mixes run attempts")
        if event.sequence <= previous:
            raise EventStreamError(f"{path}: event sequences must increase strictly")
        previous = event.sequence
    return events


def _completed_stream_errors(events: tuple[HarnessEvent, ...], *, path: Path) -> list[str]:
    """Validate ownership and the lifecycle of a sealed event stream."""

    errors: list[str] = []
    for event in events:
        if event.event_type in _ADAPTER_EVENT_TYPES:
            if event.source == CONTROL_SOURCE:
                errors.append(
                    f"{path}: scientific event {event.event_type.value} uses the reserved "
                    "harness source"
                )
        elif event.source != CONTROL_SOURCE:
            errors.append(
                f"{path}: control event {event.event_type.value} must be owned by {CONTROL_SOURCE}"
            )
    if not events:
        return errors

    positions: dict[EventType, list[int]] = {event_type: [] for event_type in EventType}
    for index, event in enumerate(events):
        positions[event.event_type].append(index)

    started = positions[EventType.RUN_STARTED]
    preflight = positions[EventType.PREFLIGHT_COMPLETED]
    stopped = positions[EventType.RUN_STOPPED]
    if len(started) != 1 or started[0] != 0:
        errors.append(f"{path}: completed stream requires one initial run_started event")
    if len(preflight) != 1:
        errors.append(f"{path}: completed stream requires exactly one preflight_completed event")
    if len(stopped) != 1 or stopped[0] != len(events) - 1:
        errors.append(f"{path}: completed stream requires one final run_stopped event")

    command_started = positions[EventType.COMMAND_STARTED]
    command_completed = positions[EventType.COMMAND_COMPLETED]
    if len(command_started) > 1:
        errors.append(f"{path}: command_started may appear at most once")
    if len(command_completed) > 1:
        errors.append(f"{path}: command_completed may appear at most once")
    if bool(command_started) != bool(command_completed):
        errors.append(
            f"{path}: command_started and command_completed must either both appear "
            "or both be absent"
        )
    if command_started and command_completed and command_started[0] >= command_completed[0]:
        errors.append(f"{path}: command_completed must follow command_started")
    if preflight:
        if started and preflight[0] <= started[0]:
            errors.append(f"{path}: preflight_completed must follow run_started")
        if command_started and preflight[0] >= command_started[0]:
            errors.append(f"{path}: command_started must follow preflight_completed")
        if stopped and preflight[0] >= stopped[-1]:
            errors.append(f"{path}: run_stopped must follow preflight_completed")

    if len(stopped) == 1:
        terminal = stopped[0]
        payload = events[terminal].payload
        status = payload.get("status")
        return_code = payload.get("return_code")
        if not isinstance(status, str) or not status.strip():
            errors.append(f"{path}: run_stopped status must be a nonempty string")
        if type(return_code) is not int:
            errors.append(f"{path}: run_stopped return_code must be an integer")
    return errors


def read_events(path: Path) -> tuple[HarnessEvent, ...]:
    """Read and semantically validate an event stream without mutating it."""

    if not path.exists():
        return ()
    if path.is_symlink() or not path.is_file():
        raise EventStreamError(f"{path}: event stream must be a regular non-symlink file")
    return _typed_events(_decode_documents(path.read_bytes(), path=path), path=path)


def validate_event_stream(path: Path, *, schema_root: Path) -> list[str]:
    """Validate JSON Schema plus one-run monotonic sequence semantics."""

    try:
        documents = _decode_documents(path.read_bytes(), path=path)
    except (OSError, EventStreamError) as exc:
        return [str(exc)]
    schema = load_json(schema_root / EVENT_SCHEMA)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for line_number, document in enumerate(documents, start=1):
        for error in validator.iter_errors(document):
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            errors.append(f"{path}: line {line_number} {location}: {error.message}")
    if errors:
        return errors
    try:
        events = _typed_events(documents, path=path)
    except EventStreamError as exc:
        errors.append(str(exc))
    else:
        errors.extend(_completed_stream_errors(events, path=path))
    if not documents:
        errors.append(f"{path}: event stream must not be empty")
    return errors


class JsonlEventWriter:
    """Append events atomically without replacing prior evidence."""

    __slots__ = ("_identity", "_path")

    def __setattr__(self, name: str, value: object) -> None:
        if name in self.__slots__ and hasattr(self, name):
            raise AttributeError(f"event writer state is write-owned: {name}")
        object.__setattr__(self, name, value)

    def __init__(self, path: Path, identity: RunIdentity) -> None:
        self._path = path
        self._identity = identity
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.is_symlink():
            raise EventStreamError(f"{self._path}: refusing symlink event stream")

    @property
    def path(self) -> Path:
        return self._path

    @property
    def identity(self) -> RunIdentity:
        return self._identity

    def append(self, event: HarnessEvent) -> None:
        if (event.run_id, event.attempt) != (
            self._identity.run_id,
            self._identity.attempt,
        ):
            raise EventStreamError("event identity does not match its writer")
        flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self._path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "r+b", buffering=0) as handle:
                descriptor = -1
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                handle.seek(0)
                existing = _typed_events(
                    _decode_documents(handle.read(), path=self._path), path=self._path
                )
                if existing and (existing[0].run_id, existing[0].attempt) != (
                    self._identity.run_id,
                    self._identity.attempt,
                ):
                    raise EventStreamError("existing event stream belongs to another run attempt")
                if existing and event.sequence <= existing[-1].sequence:
                    raise EventStreamError("event sequence must increase strictly")
                encoded = json.dumps(
                    event_document(event),
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                handle.seek(0, os.SEEK_END)
                handle.write(encoded + b"\n")
                os.fsync(handle.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)
