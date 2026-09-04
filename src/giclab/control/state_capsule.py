"""Generate the concise, public-safe agent orientation capsule."""

from __future__ import annotations

import hashlib
import json
import stat
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml
from jsonschema import Draft202012Validator

from giclab.control.category3 import repository_identity
from giclab.control.incidents import validate_incident_document
from giclab.control.target import (
    GOAL_RECORD,
    SelectedRuntimeTarget,
    resolve_selected_runtime_target,
    validate_selected_runtime_target,
)
from giclab.registry import load_json

STATE_CAPSULE_SCHEMA_VERSION: Final = "5.0.0"
DETERMINISTIC_GENERATED_AT: Final = "1970-01-01T00:00:00Z"
STATE_CAPSULE_SCHEMA: Final = "schemas/agent-state-capsule.schema.json"


class StateCapsuleError(ValueError):
    """The goal record could not produce a safe, valid state capsule."""


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_goal(repository: Path) -> dict[str, object]:
    path = repository / GOAL_RECORD
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise StateCapsuleError(f"goal record is unavailable: {exc}") from exc
    if not isinstance(value, dict):
        raise StateCapsuleError("goal record is not an object")
    return value


def _required_mapping(goal: Mapping[str, object], key: str) -> dict[str, object]:
    value = goal.get(key)
    if not isinstance(value, dict):
        raise StateCapsuleError(f"goal record lacks {key}")
    return value


def _required_strings(goal: Mapping[str, object], key: str) -> list[str]:
    value = goal.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise StateCapsuleError(f"goal record lacks {key}")
    return value


def _public_safe(value: object, *, repository: Path) -> None:
    private_markers = (str(repository.resolve()), "/Users/", "BEGIN PRIVATE KEY", "sk-")
    if isinstance(value, str):
        if any(marker in value for marker in private_markers):
            raise StateCapsuleError("state capsule contains a private path or secret-like value")
    elif isinstance(value, dict):
        for child in value.values():
            _public_safe(child, repository=repository)
    elif isinstance(value, list):
        for child in value:
            _public_safe(child, repository=repository)


def validate_goal_incident_consistency(
    repository: Path,
    goal: Mapping[str, object],
) -> None:
    """Keep technical blockers distinct from external governance state."""

    root = repository.resolve(strict=True)
    blocker = goal.get("blocking_incident")
    if blocker is not None:
        if not isinstance(blocker, str) or not blocker:
            raise StateCapsuleError("goal blocking incident is malformed")
        path = root / "control/incidents" / f"{blocker}.json"
        try:
            metadata = path.stat(follow_symlinks=False)
            document = load_json(path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise StateCapsuleError("declared blocking incident is unavailable") from exc
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise StateCapsuleError("declared blocking incident is not a regular file")
        if document.get("incident_id") != blocker:
            raise StateCapsuleError("declared blocking incident identity drifted")
        errors = validate_incident_document(root, document)
        if errors:
            raise StateCapsuleError(f"declared blocking incident is invalid: {errors[0]}")
        if document.get("status") == "resolved":
            raise StateCapsuleError("resolved incident cannot be the current technical blocker")

    governance = goal.get("external_governance_gate")
    if governance != {
        "kind": "independent-exact-head-review-and-explicit-merge-authorization",
        "state": "consult-external-state",
        "repository_state_grants_authority": False,
    }:
        raise StateCapsuleError("external governance gate is malformed or grants authority")


def generate_state_capsule(
    repository: Path,
    *,
    registry_complete: bool,
    composition_valid: bool,
    version_lint_valid: bool,
    shadow_happy_path: bool,
    failure_matrix_valid: bool,
    anti_shadow_lint_valid: bool = False,
    live_effect_conformance_valid: bool = False,
    live_method_viability_valid: bool = False,
    remote_execution_bridge_conformance_valid: bool = False,
    target: SelectedRuntimeTarget | None = None,
    deterministic: bool = True,
    generated_at: str | None = None,
) -> dict[str, object]:
    """Project machine-readable goal state and current control evidence."""

    root = repository.resolve(strict=True)
    selected_target = (
        resolve_selected_runtime_target(root)
        if target is None
        else validate_selected_runtime_target(root, target)
    )
    goal = _load_goal(root)
    validate_goal_incident_consistency(root, goal)
    commit, tree = repository_identity(root)
    if deterministic:
        timestamp = generated_at or DETERMINISTIC_GENERATED_AT
        generated_at_policy = "deterministic-fixed"
    else:
        timestamp = generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        generated_at_policy = "caller-supplied-or-wall-clock"
    document: dict[str, object] = {
        "schema_version": STATE_CAPSULE_SCHEMA_VERSION,
        "generated_at_policy": generated_at_policy,
        "generated_at": timestamp,
        "repository": {"commit": commit, "tree": tree},
        "terminal_goal": goal.get("terminal_goal"),
        "current_subgoal": goal.get("current_subgoal"),
        "next_technical_subgoal": goal.get("next_technical_subgoal"),
        "science": _required_mapping(goal, "science"),
        "control_plane": {
            **_required_mapping(goal, "control_plane"),
            "registry_complete": registry_complete,
            "composition_valid": composition_valid,
            "active_version_lint_valid": version_lint_valid,
            "shadow_happy_path": shadow_happy_path,
            "failure_matrix_valid": failure_matrix_valid,
            "anti_shadow_lint_valid": anti_shadow_lint_valid,
            "live_effect_conformance_valid": live_effect_conformance_valid,
            "live_method_viability_valid": live_method_viability_valid,
            "remote_execution_bridge_conformance_valid": (
                remote_execution_bridge_conformance_valid
            ),
        },
        "runtime_package": _required_mapping(goal, "runtime_package"),
        "selected_runtime_target": selected_target.to_document(),
        "authority": _required_mapping(goal, "authority"),
        "resources": _required_mapping(goal, "resources"),
        "evidence": _required_mapping(goal, "evidence"),
        "cost": _required_mapping(goal, "cost"),
        "blocking_incident": goal.get("blocking_incident"),
        "external_governance_gate": _required_mapping(goal, "external_governance_gate"),
        "available_actions": _required_strings(goal, "available_actions"),
        "recommended_action": goal.get("recommended_action"),
        "provenance": [GOAL_RECORD, *_required_strings(goal, "provenance")],
        "uncertainties": _required_strings(goal, "uncertainties"),
        "machine_readable_flags": {
            "live_authorization": False,
            "scientific_interpretation": False,
            "live_resources_observed_in_this_work": False,
        },
    }
    _public_safe(document, repository=root)
    document["semantic_sha256"] = _canonical_sha256(document)
    schema = load_json(root / STATE_CAPSULE_SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise StateCapsuleError(f"state capsule schema validation failed: {errors[0].message}")
    return document
