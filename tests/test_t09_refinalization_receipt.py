from __future__ import annotations

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_PATH = ROOT / "containers/sira-smoke/pragmatic/t09_finalizer_projection.py"
SCHEMA_PATH = ROOT / "schemas/t09-offline-refinalization-receipt.schema.json"


def _load_projection() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "giclab_t09_refinalization_projection_test",
        PROJECTION_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _closure() -> dict[str, str]:
    return {
        "finalizer_execution_mode": "qualified-local",
        "finalizer_runtime_qualification_sha256": "0" * 64,
        "finalizer_commit": "1" * 40,
        "finalizer_source_sha256": "2" * 64,
        "finalizer_projection_source_sha256": "3" * 64,
        "selector_source_sha256": "4" * 64,
        "scientific_package_commit": "5" * 40,
        "pilot_library_sha256": "6" * 64,
        "interpreter": "/opt/qualified/python3.11",
        "interpreter_sha256": "7" * 64,
        "python_version": "3.11.14",
        "interpreter_dependency_manifest_sha256": "8" * 64,
        "replacement_image_id": "sha256:" + "9" * 64,
        "execution_contract_sha256": "a" * 64,
        "command_manifests_sha256": "b" * 64,
        "dataset_contract_sha256": "c" * 64,
        "evaluator_contract_sha256": "d" * 64,
        "evaluator_commit": "93fb8d72de71f9a4a13419670adeb34d93cf7acd",
        "score_schema_sha256": "e" * 64,
        "evidence_schema_sha256": "f" * 64,
        "refinalization_receipt_schema_sha256": hashlib.sha256(
            SCHEMA_PATH.read_bytes()
        ).hexdigest(),
        "evaluator_overlay_entries_sha256": "1" * 64,
        "evaluator_overlay_packages_sha256": "2" * 64,
    }


def _arguments(*, closure: dict[str, str] | None = None) -> dict[str, Any]:
    resolved_closure = closure or _closure()
    return {
        "plan_id": "PLAN-EXP0001-PILOT-V10",
        "host_run_id": "RUN-T09-PILOT-HOST-AUTONOMOUS-0003",
        "run_id": "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0003",
        "raw_manifest_sha256_before": "3" * 64,
        "raw_manifest_sha256_after": "3" * 64,
        "raw_receipt_sha256": "4" * 64,
        "raw_manifest_payload_sha256": "5" * 64,
        "raw_receipt_payload_sha256": "6" * 64,
        "output_files": [
            {"path": "attempt-outcome.json", "bytes": 101, "sha256": "7" * 64},
            {"path": "evidence-index.json", "bytes": 202, "sha256": "8" * 64},
            {"path": "semantic-projection.json", "bytes": 303, "sha256": "9" * 64},
        ],
        "output_files_sha256": "a" * 64,
        "outcome_sha256": "b" * 64,
        "evidence_index_sha256": "c" * 64,
        "semantic_projection_file_sha256": "d" * 64,
        "semantic_projection_sha256": "e" * 64,
        "finalizer_closure": resolved_closure,
        "finalizer_dependency_manifest_sha256": _canonical_sha256(resolved_closure),
        "network": "socket-construction-denied",
        "raw_attempt_manifest_public_alias": (
            "attempts/RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0003/raw-attempt-manifest.json"
        ),
        "frozen_run_manifest_sha256": "f" * 64,
        "task_id": "7dcbbbdc7f1120cd",
        "task_sha256": "1" * 64,
        "condition": "reactive",
        "receipt_schema_sha256": resolved_closure["refinalization_receipt_schema_sha256"],
    }


def _build(**overrides: object) -> dict[str, Any]:
    projection = _load_projection()
    arguments = _arguments()
    arguments.update(overrides)
    return projection.build_completion_projection(**arguments)


def test_canonical_refinalization_receipt_is_deterministic_schema_valid_and_private() -> None:
    first = _build()
    second = _build()
    assert first == second
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(first),
        key=lambda error: list(error.absolute_path),
    )
    assert errors == []
    control = first["canonical_control"]
    assert first["canonical_control_sha256"] == _canonical_sha256(control)
    assert control["network_disabled"] is True
    assert control["model_replay_count"] == 0
    assert control["browser_replay_count"] == 0
    assert control["raw_mutation"] is False
    assert first["nonsemantic_fields"] == []
    encoded = json.dumps(first, sort_keys=True).lower()
    for forbidden in (
        "api_key",
        "jupyter_token",
        "fixture-secret-canary",
        "10.23.45.67",
        "/users/private-operator",
        "prompt_content",
        "answer_content",
    ):
        assert forbidden not in encoded


def test_each_refinalization_closure_identity_changes_the_semantic_receipt() -> None:
    base = _build()
    base_control = base["canonical_control"]
    changed_cases: list[tuple[str, dict[str, str], str]] = [
        (
            "scientific_package_commit",
            {"scientific_package_commit": "6" * 40},
            "frozen_scientific_commit",
        ),
        ("finalizer_commit", {"finalizer_commit": "7" * 40}, "finalizer_source_commit"),
        (
            "finalizer_source_sha256",
            {"finalizer_source_sha256": "8" * 64},
            "finalizer_source_sha256",
        ),
        ("selector_source_sha256", {"selector_source_sha256": "9" * 64}, "selector_source_sha256"),
        (
            "finalizer_projection_source_sha256",
            {"finalizer_projection_source_sha256": "a" * 64},
            "projection_source_sha256",
        ),
        (
            "interpreter",
            {"interpreter": "/opt/qualified/python3.11-v2"},
            "absolute_interpreter_identity",
        ),
        (
            "interpreter_dependency_manifest_sha256",
            {"interpreter_dependency_manifest_sha256": "b" * 64},
            "dependency_closure_identity",
        ),
        (
            "evaluator_contract_sha256",
            {"evaluator_contract_sha256": "c" * 64},
            "scoring_contract_identity",
        ),
    ]
    for _label, updates, control_field in changed_cases:
        closure = {**_closure(), **updates}
        changed = _build(
            finalizer_closure=closure,
            finalizer_dependency_manifest_sha256=_canonical_sha256(closure),
        )
        assert changed["canonical_control_sha256"] != base["canonical_control_sha256"]
        assert changed["canonical_control"][control_field] != base_control[control_field]

    raw_changed = _build(
        raw_manifest_sha256_before="d" * 64,
        raw_manifest_sha256_after="d" * 64,
    )
    assert (
        raw_changed["canonical_control"]["raw_attempt_identity"]
        != base_control["raw_attempt_identity"]
    )


def test_refinalization_receipt_rejects_missing_or_contradictory_identities() -> None:
    projection = _load_projection()

    missing_selector = _closure()
    missing_selector.pop("selector_source_sha256")
    with pytest.raises(ValueError, match="closure is incomplete"):
        projection.build_completion_projection(**_arguments(closure=missing_selector))

    arguments = _arguments()
    arguments["raw_manifest_sha256_after"] = "0" * 64
    with pytest.raises(ValueError, match="manifest changed"):
        projection.build_completion_projection(**arguments)

    arguments = _arguments()
    arguments["raw_attempt_manifest_public_alias"] = "/private/raw-attempt-manifest.json"
    with pytest.raises(ValueError, match="public alias is unsafe"):
        projection.build_completion_projection(**arguments)

    arguments = _arguments()
    arguments["finalizer_dependency_manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="closure identity contradicts"):
        projection.build_completion_projection(**arguments)

    arguments = _arguments()
    arguments["network"] = "bridge"
    with pytest.raises(ValueError, match="network policy is not disabled"):
        projection.build_completion_projection(**arguments)

    changed_evaluator = {**_closure(), "evaluator_commit": "0" * 40}
    with pytest.raises(ValueError, match="evaluator commit drifted"):
        projection.build_completion_projection(**_arguments(closure=changed_evaluator))

    contradictory_schema = deepcopy(_arguments())
    contradictory_schema["receipt_schema_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="schema contradicts"):
        projection.build_completion_projection(**contradictory_schema)
