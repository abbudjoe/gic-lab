from __future__ import annotations

import json
from pathlib import Path

import pytest

from giclab.harness.events import (
    EventStreamError,
    JsonlEventWriter,
    event_document,
    read_events,
    validate_event_stream,
)
from giclab.harness.models import EventProvenance, EventType, HarnessEvent, JsonValue, RunIdentity
from giclab.validation import ROOT


def _identity(attempt: int = 1) -> RunIdentity:
    return RunIdentity("EXP-9000", "RUN-SYNTHETIC-001", "synthetic", attempt=attempt)


def _event(
    sequence: int,
    attempt: int = 1,
    event_type: EventType = EventType.RUN_STARTED,
    *,
    source: str = "giclab-harness",
) -> HarnessEvent:
    payload: dict[str, JsonValue] = {"sequence": sequence}
    if event_type is EventType.RUN_STOPPED:
        payload = {"status": "completed", "return_code": 0}
    return HarnessEvent(
        run_id="RUN-SYNTHETIC-001",
        attempt=attempt,
        sequence=sequence,
        timestamp_utc="2026-08-07T12:00:00+00:00",
        event_type=event_type,
        source=source,
        provenance=EventProvenance.OBSERVED,
        payload=payload,
    )


def test_event_stream_is_append_only_schema_valid_and_ordered(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = JsonlEventWriter(path, _identity())
    writer.append(_event(1))
    writer.append(_event(2, event_type=EventType.PREFLIGHT_COMPLETED))
    writer.append(_event(3, event_type=EventType.COMMAND_STARTED))
    writer.append(_event(4, event_type=EventType.COMMAND_COMPLETED))
    writer.append(_event(5, event_type=EventType.RUN_STOPPED))
    assert [event.sequence for event in read_events(path)] == [1, 2, 3, 4, 5]
    assert validate_event_stream(path, schema_root=ROOT) == []


def test_completed_event_stream_requires_a_unique_final_stop(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = JsonlEventWriter(path, _identity())
    writer.append(_event(1))
    writer.append(_event(2, event_type=EventType.PREFLIGHT_COMPLETED))
    errors = validate_event_stream(path, schema_root=ROOT)
    assert any("final run_stopped" in error for error in errors)


def test_event_stream_enforces_control_and_adapter_source_ownership(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = JsonlEventWriter(path, _identity())
    writer.append(_event(1, source="synthetic-adapter"))
    writer.append(_event(2, event_type=EventType.PREFLIGHT_COMPLETED))
    writer.append(_event(3, event_type=EventType.RUN_STOPPED))
    errors = validate_event_stream(path, schema_root=ROOT)
    assert any("control event run_started" in error for error in errors)

    adapter_path = tmp_path / "adapter-events.jsonl"
    adapter_writer = JsonlEventWriter(adapter_path, _identity())
    adapter_writer.append(_event(1))
    adapter_writer.append(_event(2, event_type=EventType.PREFLIGHT_COMPLETED))
    adapter_writer.append(_event(3, event_type=EventType.METRIC))
    adapter_writer.append(_event(4, event_type=EventType.RUN_STOPPED))
    adapter_errors = validate_event_stream(adapter_path, schema_root=ROOT)
    assert any("reserved harness source" in error for error in adapter_errors)


def test_event_writer_path_and_identity_are_write_owned(tmp_path: Path) -> None:
    writer = JsonlEventWriter(tmp_path / "events.jsonl", _identity())
    for field, value in (
        ("path", tmp_path / "other.jsonl"),
        ("_path", tmp_path / "other.jsonl"),
        ("identity", _identity(attempt=2)),
        ("_identity", _identity(attempt=2)),
    ):
        with pytest.raises(AttributeError):
            setattr(writer, field, value)


def test_event_writer_rejects_nonmonotonic_append(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = JsonlEventWriter(path, _identity())
    writer.append(_event(2))
    with pytest.raises(EventStreamError, match="increase"):
        writer.append(_event(1))


def test_event_writer_rejects_mixed_attempts(tmp_path: Path) -> None:
    writer = JsonlEventWriter(tmp_path / "events.jsonl", _identity())
    with pytest.raises(EventStreamError, match="identity"):
        writer.append(_event(1, attempt=2))


def test_event_validation_rejects_corrupt_history(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    first = event_document(_event(2))
    second = event_document(_event(1))
    path.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8")
    assert any("increase" in error for error in validate_event_stream(path, schema_root=ROOT))


def test_event_validation_rejects_wrong_json_types(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    document = event_document(_event(1))
    document["sequence"] = "1"
    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    assert any(
        "not of type 'integer'" in error for error in validate_event_stream(path, schema_root=ROOT)
    )


def test_event_writer_refuses_existing_malformed_stream(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(EventStreamError, match="invalid JSON"):
        JsonlEventWriter(path, _identity()).append(_event(1))


def test_event_writer_refuses_schema_invalid_existing_history(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    document = event_document(_event(1))
    document["unexpected"] = True
    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    with pytest.raises(EventStreamError, match="unknown"):
        JsonlEventWriter(path, _identity()).append(_event(2))


def test_event_writer_refuses_existing_stream_owned_by_another_attempt(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    JsonlEventWriter(path, _identity()).append(_event(1))
    with pytest.raises(EventStreamError, match="belongs to another run attempt"):
        JsonlEventWriter(path, _identity(attempt=2)).append(_event(2, attempt=2))
    assert read_events(path) == (_event(1),)


def test_event_stream_rejects_duplicate_nested_payload_keys(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    document = event_document(_event(1))
    document["payload"] = {"nested": {"value": 1}}
    encoded = json.dumps(document).replace('"value": 1', '"value": 1, "value": 2')
    path.write_text(encoded + "\n", encoding="utf-8")
    errors = validate_event_stream(path, schema_root=ROOT)
    assert any("duplicate JSON key" in error for error in errors)
