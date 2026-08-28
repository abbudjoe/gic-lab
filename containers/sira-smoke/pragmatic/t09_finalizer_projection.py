"""Pure downstream invocation and completion projections for the T09 Retry 3 finalizer.

This module owns no empirical, provider, budget, raw-seal, selection, or checkpoint
state.  A frozen supervisor supplies already-validated identities, validates every
returned mount/argument and every output hash, and alone executes or selects results.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

_CLOSURE_FIELDS = {
    "finalizer_execution_mode",
    "finalizer_runtime_qualification_sha256",
    "finalizer_commit",
    "finalizer_source_sha256",
    "finalizer_projection_source_sha256",
    "selector_source_sha256",
    "scientific_package_commit",
    "pilot_library_sha256",
    "interpreter",
    "interpreter_sha256",
    "python_version",
    "interpreter_dependency_manifest_sha256",
    "replacement_image_id",
    "execution_contract_sha256",
    "command_manifests_sha256",
    "dataset_contract_sha256",
    "evaluator_contract_sha256",
    "evaluator_commit",
    "score_schema_sha256",
    "evidence_schema_sha256",
    "refinalization_receipt_schema_sha256",
    "evaluator_overlay_entries_sha256",
    "evaluator_overlay_packages_sha256",
}


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _is_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_safe_identity(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 160
        and all(character.isalnum() or character in "._-" for character in value)
    )


def _validate_relative_alias(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or "\0" in value:
        raise ValueError("raw attempt manifest public alias is malformed")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError("raw attempt manifest public alias is unsafe")
    return value


def _validate_closure(value: Mapping[str, str]) -> dict[str, str]:
    closure = dict(value)
    if set(closure) != _CLOSURE_FIELDS or not all(
        isinstance(item, str) for item in closure.values()
    ):
        raise ValueError("finalizer dependency closure is incomplete")
    for field in _CLOSURE_FIELDS - {
        "finalizer_execution_mode",
        "finalizer_commit",
        "scientific_package_commit",
        "interpreter",
        "python_version",
        "replacement_image_id",
        "evaluator_commit",
    }:
        if not _is_hex(closure[field], 64):
            raise ValueError(f"finalizer dependency closure identity is malformed: {field}")
    if closure["finalizer_execution_mode"] not in {"qualified-image", "qualified-local"}:
        raise ValueError("finalizer execution mode is malformed")
    if not _is_hex(closure["finalizer_commit"], 40) or not _is_hex(
        closure["scientific_package_commit"], 40
    ):
        raise ValueError("finalizer or scientific commit is malformed")
    interpreter = PurePosixPath(closure["interpreter"])
    if not interpreter.is_absolute() or ".." in interpreter.parts:
        raise ValueError("finalizer interpreter identity is not absolute")
    if closure["python_version"] != "3.11.14":
        raise ValueError("finalizer Python version drifted")
    if closure["evaluator_commit"] != "93fb8d72de71f9a4a13419670adeb34d93cf7acd":
        raise ValueError("finalizer evaluator commit drifted")
    if not closure["replacement_image_id"].startswith("sha256:") or not _is_hex(
        closure["replacement_image_id"][7:], 64
    ):
        raise ValueError("finalizer replacement image identity is malformed")
    return closure


def build_finalizer_argv(
    *,
    docker_prefix: list[str],
    container_name: str,
    plan_id: str,
    host_run_id: str,
    artifact_root: str,
    raw_root: str,
    finalized_root: str,
    control_root: str,
    giclab_source_root: str,
    finalizer_source: str,
    evaluator_overlay: str,
    execution_contract: str,
    command_manifests: str,
    condition_plans: str,
    schemas_root: str,
    image_id: str,
    condition_plan_name: str,
    output_root: str,
    raw_output_root: str,
    finalized_output_relative: str,
    run_id: str,
    package_commit: str,
    finalizer_commit: str,
    finalizer_source_sha256: str,
    finalizer_projection_source_sha256: str,
    selector_source_sha256: str,
    finalizer_dependency_manifest_sha256: str,
    refinalization_receipt_schema_sha256: str,
    frozen_run_manifest_sha256: str,
    evaluator_revalidation_relative: str,
    execution_contract_sha256: str,
    command_manifests_sha256: str,
) -> list[str]:
    """Return the declarative network-none Docker invocation for one derived root."""

    return [
        *docker_prefix,
        "run",
        "--name",
        container_name,
        "--label",
        f"giclab.t09.plan={plan_id}",
        "--label",
        f"giclab.t09.host_run={host_run_id}",
        "--label",
        "giclab.t09.role=attempt-finalizer",
        "--label",
        f"giclab.t09.run={run_id}",
        "--rm",
        "--log-driver",
        "none",
        "--ulimit",
        "core=0:0",
        "--network",
        "none",
        "--read-only",
        "--user",
        "1000:1000",
        "--env",
        "PYTHONPATH=/opt/evaluator/.venv/lib/python3.11/site-packages:/opt/giclab-src",
        "--mount",
        f"type=bind,src={artifact_root},dst=/opt/giclab-artifacts,readonly",
        "--mount",
        f"type=bind,src={raw_root},dst=/opt/giclab-raw,readonly",
        "--mount",
        f"type=bind,src={finalized_root},dst=/opt/giclab-finalized",
        "--mount",
        f"type=bind,src={control_root},dst=/opt/giclab-control,readonly",
        "--mount",
        f"type=bind,src={giclab_source_root},dst=/opt/giclab-src/giclab,readonly",
        "--mount",
        f"type=bind,src={finalizer_source},dst=/opt/giclab/t09_evaluate_attempt.py,readonly",
        "--mount",
        f"type=bind,src={evaluator_overlay},dst=/opt/evaluator,readonly",
        "--mount",
        f"type=bind,src={execution_contract},dst=/opt/giclab-contracts/execution.json,readonly",
        "--mount",
        f"type=bind,src={command_manifests},dst=/opt/giclab-contracts/T09_PILOT_COMMAND_MANIFESTS.json,readonly",
        "--mount",
        f"type=bind,src={condition_plans},dst=/opt/giclab-contracts/conditions,readonly",
        "--mount",
        f"type=bind,src={schemas_root},dst=/opt/giclab-schemas,readonly",
        "--entrypoint",
        "/opt/sira/.venv/bin/python",
        image_id,
        "/opt/giclab/t09_evaluate_attempt.py",
        "--execution-contract",
        "/opt/giclab-contracts/execution.json",
        "--execution-contract-sha256",
        execution_contract_sha256,
        "--command-manifests",
        "/opt/giclab-contracts/T09_PILOT_COMMAND_MANIFESTS.json",
        "--command-manifests-sha256",
        command_manifests_sha256,
        "--condition-plan",
        f"/opt/giclab-contracts/conditions/{condition_plan_name}",
        "--raw-attempt-root",
        "/opt/giclab-raw",
        "--raw-output-relative",
        raw_output_root,
        "--finalized-attempt-root",
        "/opt/giclab-finalized",
        "--finalized-output-relative",
        finalized_output_relative,
        "--artifact-root",
        "/opt/giclab-artifacts",
        "--raw-attempt-manifest",
        f"/opt/giclab-artifacts/{output_root}/raw-attempt-manifest.json",
        "--raw-attempt-receipt",
        f"/opt/giclab-artifacts/{output_root}/raw-attempt-complete.json",
        "--run-id",
        run_id,
        "--package-commit",
        package_commit,
        "--finalizer-commit",
        finalizer_commit,
        "--finalizer-execution-mode",
        "qualified-image",
        "--finalizer-source-sha256",
        finalizer_source_sha256,
        "--finalizer-projection-source-sha256",
        finalizer_projection_source_sha256,
        "--selector-source-sha256",
        selector_source_sha256,
        "--finalizer-dependency-manifest-sha256",
        finalizer_dependency_manifest_sha256,
        "--refinalization-receipt-schema-sha256",
        refinalization_receipt_schema_sha256,
        "--finalizer-runtime-qualification",
        "/opt/giclab-control/frozen-run-manifest.json",
        "--finalizer-runtime-qualification-sha256",
        frozen_run_manifest_sha256,
        "--frozen-run-manifest",
        "/opt/giclab-control/frozen-run-manifest.json",
        "--frozen-run-manifest-sha256",
        frozen_run_manifest_sha256,
        "--replacement-image-id",
        image_id,
        "--host-cleanup-receipt",
        "/opt/giclab-raw/.giclab-supervisor/host-cleanup-receipt.json",
        "--evaluator-root",
        "/opt/sira/evaluation/fanout",
        "--evaluator-overlay-revalidation",
        f"/opt/giclab-artifacts/{evaluator_revalidation_relative}",
        "--dataset",
        "/opt/sira/data/fanout-final-dev.json",
        "--score-schema",
        "/opt/giclab-schemas/t09-sira-pilot-score.schema.json",
        "--evidence-schema",
        "/opt/giclab-schemas/t09-sira-pilot-evidence.schema.json",
    ]


def build_completion_projection(
    *,
    plan_id: str,
    host_run_id: str,
    run_id: str,
    raw_manifest_sha256_before: str,
    raw_manifest_sha256_after: str,
    raw_receipt_sha256: str,
    raw_manifest_payload_sha256: str,
    raw_receipt_payload_sha256: str,
    output_files: list[dict[str, object]],
    output_files_sha256: str,
    outcome_sha256: str,
    evidence_index_sha256: str,
    semantic_projection_file_sha256: str,
    semantic_projection_sha256: str,
    finalizer_closure: dict[str, str],
    finalizer_dependency_manifest_sha256: str,
    network: str,
    raw_attempt_manifest_public_alias: str,
    frozen_run_manifest_sha256: str,
    task_id: str,
    task_sha256: str,
    condition: str,
    receipt_schema_sha256: str,
) -> dict[str, Any]:
    """Return the canonical offline-refinalization receipt.

    The caller must have validated the raw manifest before and after downstream
    finalization.  This builder rejects different before/after identities, so a
    completion receipt cannot represent a mutated raw source.
    """

    if not all(_is_safe_identity(value) for value in (plan_id, host_run_id, run_id)):
        raise ValueError("refinalization plan, host, or attempt identity is malformed")
    hashes = {
        "raw manifest before": raw_manifest_sha256_before,
        "raw manifest after": raw_manifest_sha256_after,
        "raw receipt": raw_receipt_sha256,
        "raw manifest payload": raw_manifest_payload_sha256,
        "raw receipt payload": raw_receipt_payload_sha256,
        "output files": output_files_sha256,
        "outcome": outcome_sha256,
        "evidence index": evidence_index_sha256,
        "semantic projection file": semantic_projection_file_sha256,
        "semantic projection": semantic_projection_sha256,
        "finalizer dependency manifest": finalizer_dependency_manifest_sha256,
        "frozen run manifest": frozen_run_manifest_sha256,
        "task": task_sha256,
        "receipt schema": receipt_schema_sha256,
    }
    malformed = [label for label, value in hashes.items() if not _is_hex(value, 64)]
    if malformed:
        raise ValueError("refinalization SHA-256 identity is malformed: " + ", ".join(malformed))
    if raw_manifest_sha256_before != raw_manifest_sha256_after:
        raise ValueError("raw attempt manifest changed during downstream finalization")
    if not _is_hex(task_id, 16) or condition not in {"reactive", "simulative"}:
        raise ValueError("refinalization task identity or condition is malformed")
    raw_alias = _validate_relative_alias(raw_attempt_manifest_public_alias)
    closure = _validate_closure(finalizer_closure)
    closure_sha256 = _canonical_sha256(closure)
    if finalizer_dependency_manifest_sha256 != closure_sha256:
        raise ValueError("finalizer dependency closure identity contradicts its payload")
    if receipt_schema_sha256 != closure["refinalization_receipt_schema_sha256"]:
        raise ValueError("refinalization receipt schema contradicts the finalizer closure")
    if network not in {"none", "socket-construction-denied"}:
        raise ValueError("offline refinalization network policy is not disabled")
    raw_attempt_identity = _canonical_sha256(
        {
            "attempt_id": run_id,
            "manifest_public_alias": raw_alias,
            "manifest_sha256": raw_manifest_sha256_before,
            "manifest_payload_sha256": raw_manifest_payload_sha256,
            "raw_receipt_sha256": raw_receipt_sha256,
        }
    )
    scoring_contract_identity = _canonical_sha256(
        {
            "evaluator_commit": closure["evaluator_commit"],
            "evaluator_contract_sha256": closure["evaluator_contract_sha256"],
            "score_schema_sha256": closure["score_schema_sha256"],
        }
    )
    canonical_control = {
        "receipt_schema_version": "1.0.0",
        "raw_attempt_identity": raw_attempt_identity,
        "raw_attempt_manifest_public_alias": raw_alias,
        "raw_attempt_manifest_sha256": raw_manifest_sha256_before,
        "raw_manifest_validation": "validated-before-and-after-byte-identical",
        "frozen_scientific_commit": closure["scientific_package_commit"],
        "frozen_run_manifest_sha256": frozen_run_manifest_sha256,
        "attempt_id": run_id,
        "task_id": task_id,
        "task_sha256": task_sha256,
        "condition": condition,
        "finalizer_source_commit": closure["finalizer_commit"],
        "finalizer_source_sha256": closure["finalizer_source_sha256"],
        "selector_source_sha256": closure["selector_source_sha256"],
        "projection_source_sha256": closure["finalizer_projection_source_sha256"],
        "absolute_interpreter_identity": {
            "path": closure["interpreter"],
            "sha256": closure["interpreter_sha256"],
        },
        "python_version": closure["python_version"],
        "dependency_closure_identity": closure_sha256,
        "evaluator_commit": closure["evaluator_commit"],
        "scoring_contract_identity": scoring_contract_identity,
        "network_disabled": True,
        "network_policy": network,
        "model_replay_count": 0,
        "browser_replay_count": 0,
        "raw_mutation": False,
        "output_semantic_projection_sha256": semantic_projection_sha256,
        "finalization_terminal_state": "offline-refinalization-complete",
    }
    receipt = {
        "schema_version": "0.2.0",
        "receipt_schema_sha256": receipt_schema_sha256,
        "plan_id": plan_id,
        "host_run_id": host_run_id,
        "run_id": run_id,
        "raw_manifest_sha256_before": raw_manifest_sha256_before,
        "raw_manifest_sha256_after": raw_manifest_sha256_after,
        "raw_receipt_sha256": raw_receipt_sha256,
        "raw_manifest_payload_sha256": raw_manifest_payload_sha256,
        "raw_receipt_payload_sha256": raw_receipt_payload_sha256,
        "output_files": output_files,
        "output_files_sha256": output_files_sha256,
        "outcome_sha256": outcome_sha256,
        "evidence_index_sha256": evidence_index_sha256,
        "semantic_projection_file_sha256": semantic_projection_file_sha256,
        "semantic_projection_sha256": semantic_projection_sha256,
        "finalizer_closure": closure,
        "finalizer_dependency_manifest_sha256": finalizer_dependency_manifest_sha256,
        "interpreter": closure["interpreter"],
        "interpreter_sha256": closure["interpreter_sha256"],
        "network": network,
        "additional_model_calls": 0,
        "additional_browser_actions": 0,
        "raw_source_mutated": False,
        "output_schema_valid": True,
        "canonical_control": canonical_control,
        "canonical_control_sha256": _canonical_sha256(canonical_control),
        "nonsemantic_fields": [],
    }
    validate_completion_projection(receipt)
    return receipt


def validate_completion_projection(receipt: Mapping[str, Any]) -> None:
    """Reject missing or contradictory canonical receipt identities."""

    control = receipt.get("canonical_control")
    closure_value = receipt.get("finalizer_closure")
    if not isinstance(control, Mapping) or not isinstance(closure_value, Mapping):
        raise ValueError("canonical refinalization control or closure is absent")
    closure = _validate_closure(closure_value)
    dependency_identity = _canonical_sha256(closure)
    expected_raw_identity = _canonical_sha256(
        {
            "attempt_id": receipt.get("run_id"),
            "manifest_public_alias": control.get("raw_attempt_manifest_public_alias"),
            "manifest_sha256": receipt.get("raw_manifest_sha256_before"),
            "manifest_payload_sha256": receipt.get("raw_manifest_payload_sha256"),
            "raw_receipt_sha256": receipt.get("raw_receipt_sha256"),
        }
    )
    expected_scoring_identity = _canonical_sha256(
        {
            "evaluator_commit": closure["evaluator_commit"],
            "evaluator_contract_sha256": closure["evaluator_contract_sha256"],
            "score_schema_sha256": closure["score_schema_sha256"],
        }
    )
    if (
        receipt.get("schema_version") != "0.2.0"
        or receipt.get("raw_manifest_sha256_before") != receipt.get("raw_manifest_sha256_after")
        or receipt.get("finalizer_dependency_manifest_sha256") != dependency_identity
        or receipt.get("receipt_schema_sha256") != closure["refinalization_receipt_schema_sha256"]
        or receipt.get("interpreter") != closure["interpreter"]
        or receipt.get("interpreter_sha256") != closure["interpreter_sha256"]
        or receipt.get("network") not in {"none", "socket-construction-denied"}
        or receipt.get("additional_model_calls") != 0
        or receipt.get("additional_browser_actions") != 0
        or receipt.get("raw_source_mutated") is not False
        or receipt.get("output_schema_valid") is not True
        or receipt.get("nonsemantic_fields") != []
        or control.get("receipt_schema_version") != "1.0.0"
        or control.get("raw_attempt_identity") != expected_raw_identity
        or control.get("raw_attempt_manifest_sha256") != receipt.get("raw_manifest_sha256_before")
        or control.get("raw_manifest_validation") != "validated-before-and-after-byte-identical"
        or control.get("frozen_scientific_commit") != closure["scientific_package_commit"]
        or control.get("attempt_id") != receipt.get("run_id")
        or control.get("finalizer_source_commit") != closure["finalizer_commit"]
        or control.get("finalizer_source_sha256") != closure["finalizer_source_sha256"]
        or control.get("selector_source_sha256") != closure["selector_source_sha256"]
        or control.get("projection_source_sha256") != closure["finalizer_projection_source_sha256"]
        or control.get("absolute_interpreter_identity")
        != {"path": closure["interpreter"], "sha256": closure["interpreter_sha256"]}
        or control.get("python_version") != closure["python_version"]
        or control.get("dependency_closure_identity") != dependency_identity
        or control.get("evaluator_commit") != closure["evaluator_commit"]
        or control.get("scoring_contract_identity") != expected_scoring_identity
        or control.get("network_disabled") is not True
        or control.get("network_policy") != receipt.get("network")
        or control.get("model_replay_count") != 0
        or control.get("browser_replay_count") != 0
        or control.get("raw_mutation") is not False
        or control.get("output_semantic_projection_sha256")
        != receipt.get("semantic_projection_sha256")
        or control.get("finalization_terminal_state") != "offline-refinalization-complete"
        or receipt.get("canonical_control_sha256") != _canonical_sha256(dict(control))
    ):
        raise ValueError("canonical offline-refinalization receipt identities contradict")


def build_local_finalizer_invocation(
    *,
    interpreter: str,
    dependency_site_packages: str,
    repository_source_root: str,
    finalizer_source: str,
    execution_contract: str,
    execution_contract_sha256: str,
    command_manifests: str,
    command_manifests_sha256: str,
    condition_plan: str,
    raw_root: str,
    raw_output_relative: str,
    finalized_root: str,
    finalized_output_relative: str,
    artifact_root: str,
    raw_attempt_manifest: str,
    raw_attempt_receipt: str,
    run_id: str,
    package_commit: str,
    finalizer_commit: str,
    finalizer_source_sha256: str,
    finalizer_projection_source_sha256: str,
    selector_source_sha256: str,
    finalizer_dependency_manifest_sha256: str,
    refinalization_receipt_schema_sha256: str,
    frozen_run_manifest: str,
    frozen_run_manifest_sha256: str,
    replacement_image_id: str,
    host_cleanup_receipt: str,
    evaluator_root: str,
    evaluator_overlay_revalidation: str,
    dataset: str,
    score_schema: str,
    evidence_schema: str,
    runtime_qualification: str,
    runtime_qualification_sha256: str,
) -> dict[str, object]:
    """Project one explicit offline post-termination finalizer invocation."""

    return {
        "argv": [
            interpreter,
            finalizer_source,
            "--execution-contract",
            execution_contract,
            "--execution-contract-sha256",
            execution_contract_sha256,
            "--command-manifests",
            command_manifests,
            "--command-manifests-sha256",
            command_manifests_sha256,
            "--condition-plan",
            condition_plan,
            "--raw-attempt-root",
            raw_root,
            "--raw-output-relative",
            raw_output_relative,
            "--finalized-attempt-root",
            finalized_root,
            "--finalized-output-relative",
            finalized_output_relative,
            "--artifact-root",
            artifact_root,
            "--raw-attempt-manifest",
            raw_attempt_manifest,
            "--raw-attempt-receipt",
            raw_attempt_receipt,
            "--run-id",
            run_id,
            "--package-commit",
            package_commit,
            "--finalizer-commit",
            finalizer_commit,
            "--finalizer-execution-mode",
            "qualified-local",
            "--finalizer-source-sha256",
            finalizer_source_sha256,
            "--finalizer-projection-source-sha256",
            finalizer_projection_source_sha256,
            "--selector-source-sha256",
            selector_source_sha256,
            "--finalizer-dependency-manifest-sha256",
            finalizer_dependency_manifest_sha256,
            "--refinalization-receipt-schema-sha256",
            refinalization_receipt_schema_sha256,
            "--finalizer-runtime-qualification",
            runtime_qualification,
            "--finalizer-runtime-qualification-sha256",
            runtime_qualification_sha256,
            "--frozen-run-manifest",
            frozen_run_manifest,
            "--frozen-run-manifest-sha256",
            frozen_run_manifest_sha256,
            "--replacement-image-id",
            replacement_image_id,
            "--host-cleanup-receipt",
            host_cleanup_receipt,
            "--evaluator-root",
            evaluator_root,
            "--evaluator-overlay-revalidation",
            evaluator_overlay_revalidation,
            "--dataset",
            dataset,
            "--score-schema",
            score_schema,
            "--evidence-schema",
            evidence_schema,
        ],
        "environment": {
            "PYTHONPATH": f"{dependency_site_packages}:{repository_source_root}",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "CUDA_VISIBLE_DEVICES": "",
        },
        "network": "socket-construction-denied",
    }
