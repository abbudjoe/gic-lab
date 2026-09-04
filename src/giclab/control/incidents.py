"""Validate append-only control incidents and their executable regressions."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator

from giclab.control.category3 import repository_identity
from giclab.registry import load_json

INCIDENT_SCHEMA_VERSION: Final = "1.0.0"
INCIDENT_ROOT: Final = "control/incidents"
INCIDENT_SCHEMA: Final = "schemas/agent-incident.schema.json"
INCIDENT_REGRESSION_TIMEOUT_SECONDS: Final = 600


class IncidentValidationError(ValueError):
    """An incident record lost its facts, coverage, or regression."""


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_incident_document(
    repository: Path,
    document: Mapping[str, object],
) -> tuple[str, ...]:
    """Validate one incident's schema, immutable facts, and local references."""

    errors: list[str] = []
    schema = load_json(repository / INCIDENT_SCHEMA)
    for error in Draft202012Validator(schema).iter_errors(document):
        errors.append(f"schema: {error.message}")
    facts = document.get("immutable_facts")
    if isinstance(facts, dict) and document.get("immutable_facts_sha256") != _canonical_sha256(
        facts
    ):
        errors.append("immutable facts hash drifted")
    regressions = document.get("regressions")
    if document.get("status") == "resolved" and not isinstance(regressions, list):
        errors.append("resolved incident lacks regressions")
    if isinstance(regressions, list):
        for regression in regressions:
            if not isinstance(regression, dict):
                continue
            reference = regression.get("reference")
            kind = regression.get("kind")
            if not isinstance(reference, str):
                continue
            path_text = reference.split("::", maxsplit=1)[0]
            path = repository / path_text
            if not path.is_file() or path.is_symlink():
                errors.append(f"regression reference is unavailable: {reference}")
            if kind == "test-node" and "::" not in reference:
                errors.append(f"test regression lacks a node id: {reference}")
    coverage = document.get("coverage")
    if document.get("live_environment_required") is False and (
        not isinstance(coverage, list)
        or not {"offline-composition", "shadow-execution"}.intersection(coverage)
    ):
        errors.append("offline incident lacks composition/shadow coverage")
    expected_scientific_result = (
        "none"
        if document.get("incident_id") == "INC-T09-V17-PACKAGE-VIABILITY-SHARED-BRIDGE"
        else "not-run"
    )
    if (
        document.get("scientific_result") != expected_scientific_result
        or document.get("scientific_interpretation_allowed") is not False
    ):
        errors.append("incident claims a scientific result")
    return tuple(errors)


def _run_regressions(repository: Path, nodes: Sequence[str]) -> tuple[bool, str]:
    if not nodes:
        return False, "no test regression nodes"
    environment = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONPATH": str(repository / "src"),
    }
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *nodes],
        cwd=repository,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=INCIDENT_REGRESSION_TIMEOUT_SECONDS,
    )
    output = (completed.stdout + completed.stderr).decode("utf-8", "replace").strip()
    return completed.returncode == 0, output[-2000:]


def validate_incidents(
    repository: Path,
    *,
    execute_regressions: bool = False,
) -> dict[str, object]:
    """Validate every tracked incident and optionally execute its exact test nodes."""

    root = repository.resolve(strict=True)
    entries: list[dict[str, object]] = []
    all_complete = True
    for path in sorted((root / INCIDENT_ROOT).glob("*.json")):
        document = load_json(path)
        errors = list(validate_incident_document(root, document))
        nodes = [
            str(regression["reference"])
            for regression in document.get("regressions", [])
            if isinstance(regression, dict) and regression.get("kind") == "test-node"
        ]
        regressions_passed: bool | None = None
        regression_output = "not-executed"
        if execute_regressions:
            regressions_passed, regression_output = _run_regressions(root, nodes)
            if not regressions_passed:
                errors.append("named regression nodes did not pass")
        complete = not errors
        all_complete = all_complete and complete
        entries.append(
            {
                "incident_id": document.get("incident_id"),
                "path": path.relative_to(root).as_posix(),
                "status": document.get("status"),
                "regression_nodes": nodes,
                "regressions_passed": regressions_passed,
                "regression_output": regression_output,
                "errors": errors,
                "complete": complete,
            }
        )
    if not entries:
        all_complete = False
    commit, tree = repository_identity(root)
    receipt: dict[str, object] = {
        "schema_version": INCIDENT_SCHEMA_VERSION,
        "repository_commit": commit,
        "repository_tree": tree,
        "incident_count": len(entries),
        "incidents": entries,
        "complete": all_complete,
    }
    receipt["semantic_sha256"] = _canonical_sha256(receipt)
    return receipt
