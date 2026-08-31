from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from giclab.control.state_capsule import generate_state_capsule
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]


def _capsule() -> dict[str, object]:
    return generate_state_capsule(
        ROOT,
        registry_complete=True,
        composition_valid=True,
        version_lint_valid=True,
        shadow_happy_path=True,
        failure_matrix_valid=True,
        deterministic=True,
    )


def test_state_capsule_validates_and_contains_agent_orientation_surface() -> None:
    capsule = _capsule()
    schema = load_json(ROOT / "schemas/agent-state-capsule.schema.json")
    Draft202012Validator(schema).validate(capsule)
    required = {
        "terminal_goal",
        "current_subgoal",
        "science",
        "control_plane",
        "runtime_package",
        "authority",
        "resources",
        "evidence",
        "cost",
        "blocking_incident",
        "available_actions",
        "recommended_action",
        "provenance",
        "uncertainties",
    }
    assert required <= capsule.keys()


def test_state_capsule_is_deterministic_and_public_safe() -> None:
    first = _capsule()
    second = _capsule()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    encoded = json.dumps(first, sort_keys=True)
    assert str(ROOT) not in encoded
    assert "/Users/" not in encoded
    assert "BEGIN PRIVATE KEY" not in encoded
    assert "sk-" not in encoded


def test_state_capsule_does_not_infer_current_turn_authority() -> None:
    capsule = _capsule()
    authority = capsule["authority"]
    flags = capsule["machine_readable_flags"]
    assert isinstance(authority, dict) and isinstance(flags, dict)
    assert authority["category_3"] is False
    assert authority["inferable_from_repository"] is False
    assert authority["current_turn_authority"] == "external-and-not-present"
    assert flags["live_authorization"] is False


def test_state_capsule_represents_v16_incident_and_v17_absence() -> None:
    capsule = _capsule()
    runtime = capsule["runtime_package"]
    control = capsule["control_plane"]
    assert isinstance(runtime, dict) and isinstance(control, dict)
    assert capsule["blocking_incident"] == "INC-T09-V16-LIFECYCLE-REGISTRY"
    assert runtime == {
        "historical_package": "V16",
        "historical_status": "consumed-prelaunch-failure",
        "next_package": "V17",
        "next_status": "not-created",
    }
    assert control["registry_complete"] is True
    assert control["composition_valid"] is True
    assert control["shadow_happy_path"] is True
    assert control["failure_matrix_valid"] is True


def test_state_capsule_timestamp_is_explicitly_isolated() -> None:
    capsule = generate_state_capsule(
        ROOT,
        registry_complete=True,
        composition_valid=True,
        version_lint_valid=True,
        shadow_happy_path=False,
        failure_matrix_valid=False,
        deterministic=False,
        generated_at="2026-08-31T12:00:00Z",
    )
    assert capsule["generated_at_policy"] == "caller-supplied-or-wall-clock"
    assert capsule["generated_at"] == "2026-08-31T12:00:00Z"


def test_future_live_package_binding_requires_every_control_receipt() -> None:
    schema = load_json(ROOT / "schemas/t09-control-receipt-bindings.schema.json")
    hashes = {
        scenario: "a" * 64
        for scenario in (
            "lifecycle-unsupported",
            "metadata-expired",
            "provider-entry-replacement",
            "host-preflight-replacement",
            "condition-failure",
            "raw-export-failure",
            "finalizer-failure",
            "cleanup-interrupted-resumed",
            "provider-termination-unavailable",
            "structural-privacy-finding",
            "ambiguous-provider-call-outcome",
        )
    }
    binding = {
        "control_plane_revision_commit": "b" * 40,
        "control_plane_revision_tree": "c" * 40,
        "registry_receipt_sha256": "d" * 64,
        "active_version_lint_receipt_sha256": "e" * 64,
        "composition_receipt_sha256": "f" * 64,
        "state_capsule_sha256": "1" * 64,
        "shadow_happy_path_sha256": "2" * 64,
        "shadow_failure_matrix_sha256s": hashes,
        "agent_check_receipt_sha256": "3" * 64,
    }
    validator = Draft202012Validator(schema)
    validator.validate(binding)
    del binding["composition_receipt_sha256"]
    with pytest.raises(ValidationError):
        validator.validate(binding)
