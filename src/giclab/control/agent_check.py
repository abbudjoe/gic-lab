"""Aggregate every deterministic agent/control gate into one receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator

from giclab.control.anti_shadow_lint import validate_anti_shadow_lint
from giclab.control.category3 import repository_identity
from giclab.control.composition import compose_control_plane
from giclab.control.incidents import validate_incidents
from giclab.control.live_conformance import run_live_effect_conformance
from giclab.control.proofs import generate_source_binding_receipt
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.scenarios import HAPPY_PATH
from giclab.control.shadow import run_required_shadow_matrix
from giclab.control.state_capsule import generate_state_capsule
from giclab.control.target import (
    SelectedRuntimeTarget,
    resolve_selected_runtime_target,
    validate_selected_runtime_target,
)
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness import t09_provider_contracts as provider_contracts
from giclab.registry import load_json

AGENT_CHECK_SCHEMA_VERSION: Final = "3.0.0"


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _schema_valid(repository: Path, schema_path: str, document: object) -> bool:
    schema = load_json(repository / schema_path)
    return not list(Draft202012Validator(schema).iter_errors(document))


def _semantic_valid(document: dict[str, object]) -> bool:
    projected = dict(document)
    observed = projected.pop("semantic_sha256", None)
    return observed == _canonical_sha256(projected)


def run_agent_check(
    repository: Path,
    *,
    target: SelectedRuntimeTarget | None = None,
    execute_incident_regressions: bool = True,
    anti_shadow_lint_receipt: dict[str, object] | None = None,
    live_effect_conformance_receipt: dict[str, object] | None = None,
) -> dict[str, object]:
    """Run all pre-authority checks without reading secrets or using a network."""

    root = repository.resolve(strict=True)
    selected_target = (
        resolve_selected_runtime_target(root)
        if target is None
        else validate_selected_runtime_target(root, target)
    )
    commit, tree = repository_identity(root)
    lint = validate_active_version_dispatch(root)
    registry = validate_registry_completeness(root)
    incidents = validate_incidents(
        root,
        execute_regressions=execute_incident_regressions,
    )
    source_binding = generate_source_binding_receipt(
        root,
        source_commit=commit,
        source_tree=tree,
    )
    source_binding_files = source_binding.get("files")
    if not isinstance(source_binding_files, list):
        raise ValueError("source-binding receipt files must be a list")
    anti_shadow = (
        validate_anti_shadow_lint(root)
        if anti_shadow_lint_receipt is None
        else dict(anti_shadow_lint_receipt)
    )
    live_conformance = (
        run_live_effect_conformance(root)
        if live_effect_conformance_receipt is None
        else dict(live_effect_conformance_receipt)
    )
    anti_shadow_valid = (
        _schema_valid(
            root,
            "schemas/t09-anti-shadow-lint-receipt.schema.json",
            anti_shadow,
        )
        and anti_shadow.get("repository_commit") == commit
        and anti_shadow.get("repository_tree") == tree
        and anti_shadow.get("complete") is True
        and _semantic_valid(anti_shadow)
    )
    live_conformance_valid = (
        _schema_valid(
            root,
            "schemas/t09-live-effect-conformance-receipt.schema.json",
            live_conformance,
        )
        and live_conformance.get("control_implementation_commit") == commit
        and live_conformance.get("control_implementation_tree") == tree
        and live_conformance.get("complete") is True
        and live_conformance.get("network_provider_cloud_browser_science_effects") == 0
        and live_conformance.get("scientific_interpretation_allowed") is False
        and _semantic_valid(live_conformance)
    )
    anti_shadow_findings = anti_shadow.get("findings")
    compositions: list[dict[str, object]] = []
    all_compositions_valid = True
    selected_composition: dict[str, object] | None = None
    for contract in provider_contracts.PROVIDER_CONTRACTS.values():
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
            if contract.version == selected_target.selected_contract.version:
                selected_composition = receipt
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
        target=selected_target,
        deterministic=True,
    )
    if selected_composition is None:
        raise ValueError("selected production composition is unavailable")
    shadow_receipts = run_required_shadow_matrix(
        root,
        contract=selected_target.selected_contract,
        state_capsule=bootstrap_capsule,
        registry_receipt=registry,
        version_lint_receipt=lint,
        composition_receipt=selected_composition,
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
        anti_shadow_lint_valid=anti_shadow_valid,
        live_effect_conformance_valid=live_conformance_valid,
        target=selected_target,
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
            source_binding.get("live_execution_performed") is False,
            anti_shadow_valid,
            live_conformance_valid,
        )
    )
    aggregate: dict[str, object] = {
        "schema_version": AGENT_CHECK_SCHEMA_VERSION,
        "repository_commit": commit,
        "repository_tree": tree,
        "selected_runtime_target": selected_target.to_document(),
        "selected_composition_semantic_sha256": selected_composition.get("semantic_sha256"),
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
                "selected_provider_contract_version": (selected_target.selected_contract.version),
                "selected_semantic_sha256": selected_composition.get("semantic_sha256"),
                "contracts": compositions,
            },
            "category3_shadow": {
                "complete": failure_matrix_valid,
                "selected_provider_contract_version": (selected_target.selected_contract.version),
                "selected_command_package_sha256": (
                    selected_target.selected_command_package_sha256
                ),
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
            "source_binding": {
                "complete": True,
                "file_count": len(source_binding_files),
                "semantic_sha256": source_binding["semantic_sha256"],
            },
            "anti_shadow_lint": {
                "complete": anti_shadow_valid,
                "finding_count": (
                    len(anti_shadow_findings) if isinstance(anti_shadow_findings, list) else -1
                ),
                "semantic_sha256": anti_shadow.get("semantic_sha256"),
            },
            "live_effect_conformance": {
                "complete": live_conformance_valid,
                "shared_controller_entry_point": live_conformance.get(
                    "shared_controller_entry_point"
                ),
                "production_assembly_entry_point": live_conformance.get(
                    "production_assembly_entry_point"
                ),
                "zero_real_effects": (
                    live_conformance.get("network_provider_cloud_browser_science_effects") == 0
                ),
                "semantic_sha256": live_conformance.get("semantic_sha256"),
            },
        },
        "complete": complete,
    }
    aggregate["semantic_sha256"] = _canonical_sha256(aggregate)
    return aggregate
