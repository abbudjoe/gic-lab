from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from giclab.harness.events import (
    EventStreamError,
    JsonlEventWriter,
    event_document,
    read_events,
    validate_event_stream,
)
from giclab.harness.models import (
    LEGACY_HARNESS_EVENT_SCHEMA_VERSION,
    EventProvenance,
    EventType,
    HarnessEvent,
    RunIdentity,
)
from giclab.harness.regulation import (
    REGULATION_FIELD_NAMES,
    RegulationDecision,
    RegulationFallback,
    RegulationOverride,
    RegulationSourceKind,
    regulation_decision_from_mapping,
    regulation_decision_payload,
)
from giclab.validation import ROOT, validate_instance

LEGACY_FIXTURE = ROOT / "tests/fixtures/harness/legacy-events-v0.1.0.jsonl"


def _assignment_provenance() -> dict[str, EventProvenance]:
    return {
        "decision_id": EventProvenance.DERIVED,
        "source_kind": EventProvenance.DERIVED,
        "policy_id": EventProvenance.DERIVED,
        "policy_revision": EventProvenance.DERIVED,
        "available_modes": EventProvenance.DERIVED,
        "selected_mode": EventProvenance.DERIVED,
        "confidence": EventProvenance.UNAVAILABLE,
        "override": EventProvenance.UNAVAILABLE,
        "fallback": EventProvenance.UNAVAILABLE,
        "input_event_sequences": EventProvenance.UNAVAILABLE,
        "raw_artifact_refs": EventProvenance.OBSERVED,
        "resolved_configuration_refs": EventProvenance.DERIVED,
    }


def _assignment() -> RegulationDecision:
    return RegulationDecision(
        decision_id="REG-SYNTHETIC-ASSIGNMENT",
        source_kind=RegulationSourceKind.EXPERIMENT_ASSIGNMENT,
        selected_mode="simulative",
        policy_id="SYNTHETIC-PAIR-ASSIGNMENT",
        policy_revision="a" * 64,
        available_modes=("reactive", "simulative"),
        raw_artifact_refs=("raw/session.json",),
        resolved_configuration_refs=("run-plan.json", "command.json"),
        field_provenance=_assignment_provenance(),
    )


def _event(decision: RegulationDecision) -> HarnessEvent:
    return HarnessEvent(
        run_id="RUN-SYNTHETIC-001",
        attempt=1,
        sequence=3,
        timestamp_utc="2026-08-08T12:00:00Z",
        event_type=EventType.REGULATION_DECISION,
        source="synthetic-regulation-adapter",
        provenance=EventProvenance.DERIVED,
        payload=regulation_decision_payload(decision),
    )


def test_valid_experiment_assignment_event_is_typed_and_schema_valid() -> None:
    decision = _assignment()
    document = event_document(_event(decision))
    assert set(decision.field_provenance) == set(REGULATION_FIELD_NAMES)
    assert document["schema_version"] == "0.2.0"
    assert validate_instance(document, ROOT / "schemas/harness-event.schema.json") == []
    assert regulation_decision_from_mapping(document["payload"]) == decision


def test_valid_explicit_model_output_records_only_an_explicit_control_record() -> None:
    provenance = {name: EventProvenance.OBSERVED for name in REGULATION_FIELD_NAMES}
    provenance["resolved_configuration_refs"] = EventProvenance.UNAVAILABLE
    decision = RegulationDecision(
        decision_id="REG-SYNTHETIC-MODEL-OUTPUT",
        source_kind=RegulationSourceKind.MODEL_EXPLICIT_OUTPUT,
        selected_mode="plan",
        policy_id="SYNTHETIC-EXPLICIT-CONTROL-HEAD",
        policy_revision="model-output-contract-v1",
        available_modes=("react", "plan", "abstain"),
        confidence=0.75,
        override=RegulationOverride(applied=False),
        fallback=RegulationFallback(triggered=False),
        input_event_sequences=(1, 2),
        raw_artifact_refs=("raw/model-response.json",),
        resolved_configuration_refs=(),
        field_provenance=provenance,
    )
    document = event_document(_event(decision))
    assert document["payload"]["source_kind"] == "model_explicit_output"
    assert validate_instance(document, ROOT / "schemas/harness-event.schema.json") == []


def test_missing_optional_assignment_fields_remain_null_and_unavailable() -> None:
    payload = regulation_decision_payload(_assignment())
    assert payload["confidence"] is None
    assert payload["override"] == {"applied": None, "source": None, "reason": None}
    assert payload["fallback"] == {"triggered": None, "target": None, "reason": None}
    provenance = payload["field_provenance"]
    assert isinstance(provenance, dict)
    for field in ("confidence", "override", "fallback"):
        assert provenance[field] == "unavailable"

    provenance["confidence"] = "derived"
    with pytest.raises(ValueError, match="missing regulation field confidence"):
        regulation_decision_from_mapping(payload)


@pytest.mark.parametrize(
    ("field", "value", "bad_provenance", "parser_match"),
    [
        (
            "decision_id",
            "REG-SYNTHETIC-ASSIGNMENT",
            "unavailable",
            "available regulation field decision_id",
        ),
        (
            "source_kind",
            "experiment_assignment",
            "unavailable",
            "available regulation field source_kind",
        ),
        (
            "source_kind",
            "unknown",
            "observed",
            "unknown source_kind must have unavailable provenance",
        ),
        ("policy_id", None, "derived", "missing regulation field policy_id"),
        (
            "policy_id",
            "SYNTHETIC-PAIR-ASSIGNMENT",
            "unavailable",
            "available regulation field policy_id",
        ),
        (
            "policy_revision",
            None,
            "derived",
            "missing regulation field policy_revision",
        ),
        (
            "policy_revision",
            "a" * 64,
            "unavailable",
            "available regulation field policy_revision",
        ),
        (
            "available_modes",
            None,
            "derived",
            "missing regulation field available_modes",
        ),
        (
            "available_modes",
            ["reactive", "simulative"],
            "unavailable",
            "available regulation field available_modes",
        ),
        (
            "selected_mode",
            "simulative",
            "unavailable",
            "available regulation field selected_mode",
        ),
        ("confidence", None, "derived", "missing regulation field confidence"),
        (
            "confidence",
            0.5,
            "unavailable",
            "available regulation field confidence",
        ),
        (
            "override",
            {"applied": None, "source": None, "reason": None},
            "derived",
            "missing regulation field override",
        ),
        (
            "override",
            {"applied": False, "source": None, "reason": None},
            "unavailable",
            "available regulation field override",
        ),
        (
            "fallback",
            {"triggered": None, "target": None, "reason": None},
            "derived",
            "missing regulation field fallback",
        ),
        (
            "fallback",
            {"triggered": False, "target": None, "reason": None},
            "unavailable",
            "available regulation field fallback",
        ),
        (
            "input_event_sequences",
            [],
            "derived",
            "missing regulation field input_event_sequences",
        ),
        (
            "input_event_sequences",
            [1],
            "unavailable",
            "available regulation field input_event_sequences",
        ),
        (
            "raw_artifact_refs",
            [],
            "derived",
            "missing regulation field raw_artifact_refs",
        ),
        (
            "raw_artifact_refs",
            ["raw/session.json"],
            "unavailable",
            "available regulation field raw_artifact_refs",
        ),
        (
            "resolved_configuration_refs",
            [],
            "derived",
            "missing regulation field resolved_configuration_refs",
        ),
        (
            "resolved_configuration_refs",
            ["run-plan.json", "command.json"],
            "unavailable",
            "available regulation field resolved_configuration_refs",
        ),
    ],
)
def test_schema_and_parser_reject_field_provenance_contradictions(
    field: str,
    value: Any,
    bad_provenance: str,
    parser_match: str,
) -> None:
    payload = regulation_decision_payload(_assignment())
    payload[field] = value
    provenance = payload["field_provenance"]
    assert isinstance(provenance, dict)
    provenance[field] = bad_provenance
    document = event_document(_event(_assignment()))
    document["payload"] = payload

    assert validate_instance(document, ROOT / "schemas/harness-event.schema.json")
    with pytest.raises(ValueError, match=parser_match):
        regulation_decision_from_mapping(payload)


def test_selected_mode_membership_is_an_explicit_semantic_parser_boundary() -> None:
    payload = regulation_decision_payload(_assignment())
    payload["available_modes"] = ["reactive"]
    document = event_document(_event(_assignment()))
    document["payload"] = payload

    assert validate_instance(document, ROOT / "schemas/harness-event.schema.json") == []
    with pytest.raises(ValueError, match="selected_mode must be one of the available_modes"):
        regulation_decision_from_mapping(payload)


def test_regulation_decision_rejects_missing_raw_and_resolved_evidence() -> None:
    with pytest.raises(ValueError, match="raw artifact or resolved configuration evidence"):
        RegulationDecision(
            decision_id="REG-WITHOUT-EVIDENCE",
            source_kind=RegulationSourceKind.EXTERNAL_RULE,
            selected_mode="react",
            field_provenance={
                **_assignment_provenance(),
                "policy_id": EventProvenance.UNAVAILABLE,
                "policy_revision": EventProvenance.UNAVAILABLE,
                "available_modes": EventProvenance.UNAVAILABLE,
                "raw_artifact_refs": EventProvenance.UNAVAILABLE,
                "resolved_configuration_refs": EventProvenance.UNAVAILABLE,
            },
        )


def test_unsupported_source_kind_and_internalization_assertion_are_rejected() -> None:
    document = event_document(_event(_assignment()))
    payload = document["payload"]
    payload["source_kind"] = "latent_internalization"
    with pytest.raises(ValueError, match="unsupported regulation source_kind"):
        regulation_decision_from_mapping(payload)
    assert validate_instance(document, ROOT / "schemas/harness-event.schema.json")

    payload = regulation_decision_payload(_assignment())
    payload["internalized"] = True
    with pytest.raises(ValueError, match=r"unknown=\['internalized'\]"):
        regulation_decision_from_mapping(payload)
    document = event_document(_event(_assignment()))
    document["payload"]["internalized"] = True
    assert validate_instance(document, ROOT / "schemas/harness-event.schema.json")


def test_legacy_v0_1_event_fixture_remains_readable_and_valid() -> None:
    events = read_events(LEGACY_FIXTURE)
    assert [event.schema_version for event in events] == ["0.1.0"] * 3
    assert validate_event_stream(LEGACY_FIXTURE, schema_root=ROOT) == []


def test_event_stream_refuses_mixed_versions_and_legacy_regulation(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    shutil.copyfile(LEGACY_FIXTURE, path)
    writer = JsonlEventWriter(
        path,
        RunIdentity("EXP-9000", "RUN-LEGACY-001", "legacy"),
    )
    current = HarnessEvent(
        run_id="RUN-LEGACY-001",
        attempt=1,
        sequence=4,
        timestamp_utc="2026-08-08T12:00:00Z",
        event_type=EventType.WARNING,
        source="giclab-harness",
        provenance=EventProvenance.OBSERVED,
        payload={"kind": "synthetic"},
    )
    with pytest.raises(EventStreamError, match="cannot mix schema versions"):
        writer.append(current)

    with pytest.raises(ValueError, match=r"requires harness event schema_version 0\.2\.0"):
        HarnessEvent(
            run_id="RUN-LEGACY-001",
            attempt=1,
            sequence=4,
            timestamp_utc="2026-08-08T12:00:00Z",
            event_type=EventType.REGULATION_DECISION,
            source="synthetic-adapter",
            provenance=EventProvenance.DERIVED,
            payload=regulation_decision_payload(_assignment()),
            schema_version=LEGACY_HARNESS_EVENT_SCHEMA_VERSION,
        )
