"""Aggregate every deterministic agent/control gate into one receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator

from giclab.control.category3 import repository_identity
from giclab.control.composition import compose_control_plane
from giclab.control.incidents import validate_incidents
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.shadow import HAPPY_PATH, run_required_shadow_matrix
from giclab.control.state_capsule import generate_state_capsule
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness.t09_provider_contracts import PROVIDER_CONTRACTS, V16_PROVIDER_CONTRACT
from giclab.registry import load_json

AGENT_CHECK_SCHEMA_VERSION: Final = "1.0.0"


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _schema_valid(repository: Path, schema_path: str, document: object) -> bool:
    schema = load_json(repository / schema_path)
    return not list(Draft202012Validator(schema).iter_errors(document))


def run_agent_check(
    repository: Path,
    *,
    execute_incident_regressions: bool = True,
) -> dict[str, object]:
    """Run all pre-authority checks without reading secrets or using a network."""

    root = repository.resolve(strict=True)
    commit, tree = repository_identity(root)
    lint = validate_active_version_dispatch(root)
    registry = validate_registry_completeness(root)
    incidents = validate_incidents(
        root,
        execute_regressions=execute_incident_regressions,
    )
    compositions: list[dict[str, object]] = []
    all_compositions_valid = True
    for contract in PROVIDER_CONTRACTS.values():
        try:
            receipt = compose_control_plane(
                root,
                contract=contract,
                registry_receipt=registry,
                version_lint_receipt=lint,
            )
            valid = _schema_valid(
                root,
                "schemas/t09-control-composition-receipt.schema.json",
                receipt,
            )
            error = None
        except Exception as exc:
            receipt = {}
            valid = False
            error = f"{type(exc).__name__}: {exc}"
        all_compositions_valid = all_compositions_valid and valid
        compositions.append(
            {
                "version": contract.version,
                "valid": valid,
                "semantic_sha256": receipt.get("semantic_sha256"),
                "ready_for_shadow": receipt.get("ready_for_shadow", False),
                "error": error,
            }
        )

    bootstrap_capsule = generate_state_capsule(
        root,
        registry_complete=registry.get("complete") is True,
        composition_valid=all_compositions_valid,
        version_lint_valid=lint.get("complete") is True,
        shadow_happy_path=False,
        failure_matrix_valid=False,
        deterministic=True,
    )
    shadow_receipts = run_required_shadow_matrix(
        root,
        contract=V16_PROVIDER_CONTRACT,
        state_capsule_sha256=str(bootstrap_capsule["semantic_sha256"]),
    )
    shadow_schema_valid = all(
        _schema_valid(root, "schemas/t09-category3-shadow-receipt.schema.json", receipt)
        for receipt in shadow_receipts.values()
    )
    happy_valid = (
        shadow_schema_valid
        and shadow_receipts[HAPPY_PATH].get("terminal_state") == "category3-shadow-complete-clean"
    )
    failure_matrix_valid = shadow_schema_valid and all(
        receipt.get("scenario_valid") is True for receipt in shadow_receipts.values()
    )
    capsule = generate_state_capsule(
        root,
        registry_complete=registry.get("complete") is True,
        composition_valid=all_compositions_valid,
        version_lint_valid=lint.get("complete") is True,
        shadow_happy_path=happy_valid,
        failure_matrix_valid=failure_matrix_valid,
        deterministic=True,
    )
    capsule_valid = _schema_valid(root, "schemas/agent-state-capsule.schema.json", capsule)
    complete = all(
        (
            lint.get("complete") is True,
            registry.get("complete") is True,
            incidents.get("complete") is True,
            all_compositions_valid,
            shadow_schema_valid,
            happy_valid,
            failure_matrix_valid,
            capsule_valid,
        )
    )
    aggregate: dict[str, object] = {
        "schema_version": AGENT_CHECK_SCHEMA_VERSION,
        "repository_commit": commit,
        "repository_tree": tree,
        "checks": {
            "active_version_lint": {
                "complete": lint.get("complete") is True,
                "semantic_sha256": lint.get("semantic_sha256"),
            },
            "registry_completeness": {
                "complete": registry.get("complete") is True,
                "contract_count": registry.get("contract_count"),
                "semantic_sha256": registry.get("semantic_sha256"),
            },
            "incident_completeness": {
                "complete": incidents.get("complete") is True,
                "incident_count": incidents.get("incident_count"),
                "semantic_sha256": incidents.get("semantic_sha256"),
            },
            "offline_composition": {
                "complete": all_compositions_valid,
                "contracts": compositions,
            },
            "category3_shadow": {
                "complete": failure_matrix_valid,
                "scenarios": [
                    {
                        "scenario": scenario,
                        "semantic_sha256": shadow_receipt["semantic_sha256"],
                        "terminal_state": shadow_receipt["terminal_state"],
                        "earliest_stopping_phase": shadow_receipt["earliest_stopping_phase"],
                    }
                    for scenario, shadow_receipt in shadow_receipts.items()
                ],
            },
            "state_capsule": {
                "complete": capsule_valid,
                "semantic_sha256": capsule["semantic_sha256"],
            },
        },
        "complete": complete,
    }
    aggregate["semantic_sha256"] = _canonical_sha256(aggregate)
    return aggregate
