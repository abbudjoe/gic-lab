from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from giclab.control.scenarios import REQUIRED_FAILURE_SCENARIOS
from giclab.control.state_capsule import (
    StateCapsuleError,
    generate_state_capsule,
    validate_goal_incident_consistency,
)
from giclab.control.target import resolve_selected_runtime_target
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[2]


def test_state_capsule_rejects_goal_changed_since_target_selection() -> None:
    from giclab.control.state_capsule import repository_identity
    from giclab.control.target import (
        TargetSelectionError,
        resolve_selected_runtime_target_from_goal_bytes,
    )
    from giclab.harness.t09_provider_contracts import PROVIDER_CONTRACTS

    goal = (ROOT / "control/goals/EXP-0001.yaml").read_bytes()
    commit, _ = repository_identity(ROOT)
    # Even a semantically neutral edit after selection changes the bound input.
    selected_before_edit = resolve_selected_runtime_target_from_goal_bytes(
        ROOT,
        goal + b"\n# previously selected goal snapshot\n",
        bound_package_commit=commit,
        bound_registered_contract_versions=frozenset(PROVIDER_CONTRACTS),
    )
    current = resolve_selected_runtime_target(ROOT)
    assert selected_before_edit.selected_contract == current.selected_contract
    assert (
        selected_before_edit.selected_command_package_sha256
        == current.selected_command_package_sha256
    )
    assert selected_before_edit.goal_record_sha256 != current.goal_record_sha256
    with pytest.raises(TargetSelectionError, match=r"state: goal_record_sha256$"):
        generate_state_capsule(
            ROOT,
            registry_complete=False,
            composition_valid=False,
            version_lint_valid=False,
            shadow_happy_path=False,
            failure_matrix_valid=False,
            target=selected_before_edit,
        )


def _capsule() -> dict[str, object]:
    return generate_state_capsule(
        ROOT,
        registry_complete=True,
        composition_valid=True,
        version_lint_valid=True,
        shadow_happy_path=True,
        failure_matrix_valid=True,
        anti_shadow_lint_valid=True,
        live_effect_conformance_valid=True,
        live_method_viability_valid=True,
        remote_execution_bridge_conformance_valid=True,
        deterministic=True,
    )


def test_state_capsule_validates_and_contains_agent_orientation_surface() -> None:
    capsule = _capsule()
    schema = load_json(ROOT / "schemas/agent-state-capsule.schema.json")
    Draft202012Validator(schema).validate(capsule)
    required = {
        "terminal_goal",
        "current_subgoal",
        "next_technical_subgoal",
        "science",
        "control_plane",
        "runtime_package",
        "selected_runtime_target",
        "authority",
        "resources",
        "evidence",
        "cost",
        "blocking_incident",
        "external_governance_gate",
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
    assert capsule["blocking_incident"] == "INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW"
    assert capsule["external_governance_gate"] == {
        "kind": "independent-exact-head-review-and-explicit-merge-authorization",
        "state": "consult-external-state",
        "repository_state_grants_authority": False,
    }
    assert (
        capsule["next_technical_subgoal"] == "validate-exact-commit-v16-before-independent-review"
    )
    assert capsule["current_subgoal"].startswith(
        "finalize the independently accepted R1-R6 development matrix"
    )
    assert "remove fixed target selection" not in str(capsule["recommended_action"])
    assert "before any product push" in str(capsule["recommended_action"])
    assert control["status"] == "remote-execution-bridge-final-validation-pending"
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
    assert control["anti_shadow_lint_valid"] is True
    assert control["live_effect_conformance_valid"] is True
    assert control["live_method_viability_valid"] is True
    assert control["remote_execution_bridge_conformance_valid"] is True


def _goal() -> dict[str, object]:
    loaded = yaml.safe_load((ROOT / "control/goals/EXP-0001.yaml").read_text())
    assert isinstance(loaded, dict)
    return loaded


def test_resolved_incident_cannot_be_the_current_blocker() -> None:
    goal = _goal()
    goal["blocking_incident"] = "INC-T09-CONTROL-FIXED-TARGET-SELECTION"
    with pytest.raises(StateCapsuleError, match="resolved incident"):
        validate_goal_incident_consistency(ROOT, goal)


def test_declared_missing_blocking_incident_fails() -> None:
    goal = _goal()
    goal["blocking_incident"] = "INC-T09-MISSING"
    with pytest.raises(StateCapsuleError, match="unavailable"):
        validate_goal_incident_consistency(ROOT, goal)


def test_unresolved_current_incident_is_allowed(
    tmp_path: Path,
) -> None:
    goal = _goal()
    blocker = "INC-T09-CONTROL-FIXED-TARGET-SELECTION"
    goal["blocking_incident"] = blocker
    incident = load_json(ROOT / f"control/incidents/{blocker}.json")
    incident = deepcopy(incident)
    incident["status"] = "open"
    path = tmp_path / "control/incidents" / f"{blocker}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(incident), encoding="utf-8")
    schema = tmp_path / "schemas/agent-incident.schema.json"
    schema.parent.mkdir(parents=True)
    schema.write_bytes((ROOT / "schemas/agent-incident.schema.json").read_bytes())
    for relative in (
        "tests/control/test_target_selection.py",
        "tests/control/test_version_lint.py",
    ):
        copied = tmp_path / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((ROOT / relative).read_bytes())
    validate_goal_incident_consistency(tmp_path, goal)


def test_capsule_remains_truthful_after_merge_pending_goal_transition() -> None:
    capsule = _capsule()
    assert capsule["external_governance_gate"]["state"] == "consult-external-state"
    assert capsule["external_governance_gate"]["repository_state_grants_authority"] is False
    assert "independent exact-head review" in capsule["recommended_action"]
    assert "before any product push" in capsule["recommended_action"]
    assert capsule["control_plane"]["status"] == "remote-execution-bridge-final-validation-pending"
    assert "control/incidents/INC-T09-CONTROL-FIXED-TARGET-SELECTION.json" in capsule["provenance"]
    assert (
        "control/incidents/INC-T09-CONTROL-SHADOW-SHAPED-LIVE-BOUNDARY.json"
        in capsule["provenance"]
    )
    assert (
        "control/incidents/INC-T09-CONTROL-LIVE-BOUNDARY-EXACT-HEAD-REVIEW.json"
        in capsule["provenance"]
    )
    assert (
        "control/incidents/INC-T09-V17-PACKAGE-VIABILITY-SHARED-BRIDGE.json"
        in capsule["provenance"]
    )


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

    def artifact(path: str) -> dict[str, object]:
        return {
            "path": path,
            "bytes": 2,
            "file_sha256": "a" * 64,
            "semantic_sha256": "b" * 64,
        }

    binding = {
        "schema_version": "6.0.0",
        "repository_slug": "abbudjoe/gic-lab",
        "base_commit": "4" * 40,
        "control_plane_revision": {"commit": "5" * 40, "tree": "6" * 40},
        "selected_runtime_target": resolve_selected_runtime_target(ROOT).to_document(),
        "package_effect_registration": None,
        "artifacts": {
            "goal_record": {
                "path": "bound-goal-record.yaml",
                "bytes": 2,
                "file_sha256": "a" * 64,
            },
            "registry_receipt": artifact("registry.json"),
            "active_version_lint_receipt": artifact("lint.json"),
            "composition_receipt": artifact("composition.json"),
            "state_capsule": artifact("capsule.json"),
            "shadow_happy_path": artifact("category3-shadow/happy-path.json"),
            "shadow_failures": {
                scenario: artifact(f"category3-shadow/{scenario}.json")
                for scenario in REQUIRED_FAILURE_SCENARIOS
            },
            "agent_check_receipt": artifact("agent.json"),
            "source_binding_receipt": artifact("source.json"),
            "incident_receipt": artifact("incidents.json"),
            "anti_shadow_lint_receipt": artifact("anti-shadow.json"),
            "live_effect_conformance_receipt": artifact("live-conformance.json"),
            "live_method_viability_receipt": artifact("viability.json"),
            "remote_execution_bridge_conformance_receipt": artifact("remote-bridge.json"),
        },
        "authority": {
            "live_authorization": False,
            "scientific_interpretation_allowed": False,
            "repository_state_grants_authority": False,
        },
        "semantic_sha256": "8" * 64,
    }
    validator = Draft202012Validator(schema)
    validator.validate(binding)
    del binding["artifacts"]["composition_receipt"]  # type: ignore[index]
    with pytest.raises(ValidationError):
        validator.validate(binding)


@pytest.mark.parametrize(
    "receipt_name",
    ("live_method_viability_receipt", "remote_execution_bridge_conformance_receipt"),
)
def test_generation_six_binding_requires_remote_bridge_receipts(receipt_name: str) -> None:
    schema = load_json(ROOT / "schemas/t09-control-receipt-bindings.schema.json")
    required = Draft202012Validator(schema).schema["allOf"][1]["then"]["properties"]["artifacts"][
        "required"
    ]
    assert receipt_name in required
