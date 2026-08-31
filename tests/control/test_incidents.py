from __future__ import annotations

import copy
from pathlib import Path

from giclab.control.incidents import validate_incident_document, validate_incidents
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]
INCIDENT_PATH = ROOT / "control/incidents/INC-T09-V16-LIFECYCLE-REGISTRY.json"


def test_v16_incident_validates_and_named_regressions_pass() -> None:
    receipt = validate_incidents(ROOT, execute_regressions=True)
    assert receipt["complete"] is True
    assert receipt["incident_count"] == 1
    incident = receipt["incidents"][0]  # type: ignore[index]
    assert incident["regressions_passed"] is True
    assert len(incident["regression_nodes"]) == 3


def test_resolved_incident_with_missing_regression_fails() -> None:
    document = copy.deepcopy(load_json(INCIDENT_PATH))
    document["regressions"] = [
        {"kind": "test-node", "reference": "tests/control/missing.py::test_missing"}
    ]
    errors = validate_incident_document(ROOT, document)
    assert any("unavailable" in error for error in errors)


def test_offline_incident_without_composition_or_shadow_coverage_fails() -> None:
    document = copy.deepcopy(load_json(INCIDENT_PATH))
    document["coverage"] = []
    errors = validate_incident_document(ROOT, document)
    assert any("offline incident lacks" in error for error in errors)


def test_incident_facts_are_hash_bound_and_cannot_claim_science() -> None:
    document = copy.deepcopy(load_json(INCIDENT_PATH))
    facts = document["immutable_facts"]
    assert isinstance(facts, dict)
    facts["empirical_attempts"] = 1
    document["scientific_result"] = "negative-result"
    document["scientific_interpretation_allowed"] = True
    errors = validate_incident_document(ROOT, document)
    assert "immutable facts hash drifted" in errors
    assert "incident claims a scientific result" in errors
