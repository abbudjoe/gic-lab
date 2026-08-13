"""Finalize one retained T09 attempt with the exact offline FanOutQA evaluator.

This program runs in a network-disabled container after the condition container is
removed. It cannot call a model or browser. It validates the frozen command and
condition plan, evaluates the one retained session, emits the reconstructable evidence
index, completes the attempt ledger, and seals the automatic Task-A checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from giclab.harness.t09_sira_pilot import (
    ATTEMPT_ORDER,
    DATASET_REVISION,
    EVALUATOR_RUN_IDS,
    EVALUATOR_SHA256,
    MODEL_REVISION,
    PLAN_ID,
    SIRA_COMMIT,
    TASK_REFERENCE_SHA256S,
    TASK_TEXT_SHA256S,
    EvaluatorIdentity,
    PairCheckpointInput,
    PilotExecutionContract,
    T09PilotError,
    evaluate_retained_session,
    file_sha256,
    first_pair_decision,
    load_aggregate_usage,
    load_execution_contract,
    mark_attempt_completed,
    outcome_contract,
    record_first_pair_checkpoint,
)

CONTAINER_IMAGE_DIGEST = "sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-contract", type=Path, required=True)
    parser.add_argument("--execution-contract-sha256", required=True)
    parser.add_argument("--command-manifests", type=Path, required=True)
    parser.add_argument("--command-manifests-sha256", required=True)
    parser.add_argument("--condition-plan", type=Path, required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--package-commit", required=True)
    parser.add_argument("--aggregate-ledger", type=Path, required=True)
    parser.add_argument("--pilot-state", type=Path, required=True)
    parser.add_argument("--host-cleanup-receipt", type=Path, required=True)
    parser.add_argument("--evaluator-root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--score-schema", type=Path, required=True)
    parser.add_argument("--evidence-schema", type=Path, required=True)
    return parser


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise T09PilotError(f"{label} must be a string-keyed JSON object")
    return cast(dict[str, Any], value)


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise T09PilotError("evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _events(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value: object = json.loads(line)
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise T09PilotError("normalized event record is malformed")
        result.append(cast(dict[str, Any], value))
    return result


def _dynamic_object(
    path: Path,
    *,
    label: str,
    failure_reasons: list[str],
) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        failure_reasons.append(f"missing-{label}")
        return {}
    try:
        return _load_object(path, label=label)
    except (OSError, UnicodeError, json.JSONDecodeError, T09PilotError):
        failure_reasons.append(f"malformed-{label}")
        return {}


def _dynamic_events(path: Path, *, failure_reasons: list[str]) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        failure_reasons.append("missing-normalized-events")
        return []
    try:
        return _events(path)
    except (OSError, UnicodeError, json.JSONDecodeError, T09PilotError):
        failure_reasons.append("malformed-normalized-events")
        return []


def _schema_errors(document: object, schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return sorted(
        f"{'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in validator.iter_errors(document)
    )


def _validate_output_documents(
    *,
    outcome: dict[str, object],
    evidence: dict[str, object],
    score_schema_path: Path,
    evidence_schema_path: Path,
) -> None:
    score_schema = _load_object(score_schema_path.resolve(strict=True), label="score schema")
    evidence_schema = _load_object(
        evidence_schema_path.resolve(strict=True), label="evidence schema"
    )
    properties = evidence_schema.get("properties")
    if not isinstance(properties, dict) or "outcome" not in properties:
        raise T09PilotError("evidence schema outcome reference is unavailable")
    properties["outcome"] = score_schema
    score_errors = _schema_errors(outcome, score_schema)
    evidence_errors = _schema_errors(evidence, evidence_schema)
    if score_errors or evidence_errors:
        raise T09PilotError(
            "finalized attempt documents violate their schemas: "
            + "; ".join([*score_errors, *evidence_errors])
        )


def _session_paths(attempt_root: Path) -> list[Path]:
    output = attempt_root / "sira-output"
    if not output.is_dir() or output.is_symlink():
        return []
    return sorted(
        path
        for path in output.glob("*.json")
        if path.name != "output.jsonl" and path.is_file() and not path.is_symlink()
    )


def _screenshot_sha256(payload: Mapping[str, object]) -> str | None:
    observation = payload.get("observation")
    if not isinstance(observation, Mapping):
        return None
    screenshot = observation.get("screenshot")
    if not isinstance(screenshot, str):
        return None
    return hashlib.sha256(screenshot.encode()).hexdigest()


def _provider_records(events: list[dict[str, Any]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for event in events:
        if event.get("kind") != "provider-call-receipt":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict) or not isinstance(payload.get("usage"), dict):
            raise T09PilotError("provider call receipt is malformed")
        records.append(
            {
                "event_id": event.get("event_id"),
                "parent_event_id": event.get("parent_event_id"),
                "role": payload.get("role"),
                "request_model": payload.get("model"),
                "requested_service_tier": payload.get("requested_service_tier"),
                "returned_service_tier": payload.get("returned_service_tier"),
                "usage": payload["usage"],
                "receipt": {
                    "provider_response_id": payload.get("provider_response_id"),
                    "system_fingerprint": payload.get("system_fingerprint"),
                    "retry": payload.get("retry"),
                },
            }
        )
    return records


def _browser_records(events: list[dict[str, Any]]) -> list[dict[str, object]]:
    requested = {
        str(event.get("event_id")): event
        for event in events
        if event.get("kind") == "requested-browser-action"
    }
    records: list[dict[str, object]] = []
    for result in events:
        if result.get("kind") != "post-action-result":
            continue
        parent = str(result.get("parent_event_id"))
        action = requested.get(parent)
        action_payload = action.get("payload") if isinstance(action, dict) else None
        result_payload = result.get("payload")
        if (
            not isinstance(action, dict)
            or not isinstance(action_payload, dict)
            or not isinstance(result_payload, dict)
        ):
            raise T09PilotError("browser action/result causal evidence is incomplete")
        requested_action = action_payload.get("requested_action")
        if not isinstance(requested_action, str):
            raise T09PilotError("requested browser action is missing")
        records.append(
            {
                "action_event_id": parent,
                "parent_event_id": action.get("parent_event_id"),
                "requested_action": requested_action,
                "result_event_id": result.get("event_id"),
                "post_action_result": result_payload,
                "screenshot_sha256": _screenshot_sha256(result_payload),
            }
        )
    return records


def _manifest_for_run(document: Mapping[str, object], run_id: str) -> dict[str, Any]:
    raw = document.get("manifests")
    if not isinstance(raw, list):
        raise T09PilotError("command manifest set is malformed")
    matches = [item for item in raw if isinstance(item, dict) and item.get("run_id") == run_id]
    if len(matches) != 1:
        raise T09PilotError("command manifest is missing or duplicated")
    return cast(dict[str, Any], matches[0])


def _validate_pair_diff(document: Mapping[str, object], pair_index: int) -> bool:
    raw = document.get("pair_diffs")
    return (
        isinstance(raw, list)
        and len(raw) == 2
        and isinstance(raw[pair_index], dict)
        and raw[pair_index].get("valid") is True
    )


def _first_pair_checkpoint(
    *,
    contract: PilotExecutionContract,
    command_document: Mapping[str, object],
    artifact_base: Path,
    aggregate_ledger: Path,
    pilot_state: Path,
) -> dict[str, object]:
    evidence = [
        _load_object(
            artifact_base / contract.attempt(run_id).output_root / "evidence-index.json",
            label="Task A evidence index",
        )
        for run_id in ATTEMPT_ORDER[:2]
    ]
    outcomes = [cast(dict[str, Any], document["outcome"]) for document in evidence]
    usage = load_aggregate_usage(aggregate_ledger, contract_sha256=contract.sha256)
    state = _load_object(pilot_state, label="pilot state")
    now = time.time()
    pair_started = state.get("first_pair_started_at_epoch")
    lambda_started = state.get("lambda_started_at_epoch")
    if (
        not isinstance(pair_started, (int, float))
        or isinstance(pair_started, bool)
        or not isinstance(lambda_started, (int, float))
        or isinstance(lambda_started, bool)
    ):
        raise T09PilotError("pilot timing origins are unavailable")
    pair_wall = now - float(pair_started)
    lambda_wall = now - float(lambda_started)
    if (
        not math.isfinite(pair_wall)
        or pair_wall < 0
        or not math.isfinite(lambda_wall)
        or lambda_wall < 0
    ):
        raise T09PilotError("pilot timing origins are invalid")
    lambda_cost = lambda_wall * 1.29 / 3600.0
    actual_total = usage.cost_usd + lambda_cost
    severe_floor_or_ceiling = all(
        outcome.get("task_completion") == "incomplete" and outcome.get("task_score") == 0.0
        for outcome in outcomes
    )
    decision = first_pair_decision(
        PairCheckpointInput(
            attempt_run_ids=(ATTEMPT_ORDER[0], ATTEMPT_ORDER[1]),
            valid_evidence=cast(
                tuple[bool, bool],
                tuple(outcome.get("valid_scored_attempt") is True for outcome in outcomes),
            ),
            evaluator_succeeded=cast(
                tuple[bool, bool],
                tuple(outcome.get("evaluator_validity") is True for outcome in outcomes),
            ),
            pair_match_valid=_validate_pair_diff(command_document, 0),
            credential_issue=any(
                document.get("cleanup", {}).get("secret_removed") is not True
                for document in evidence
            ),
            cleanup_issue=any(
                document.get("cleanup", {}).get("browser_closed") is not True
                or document.get("cleanup", {}).get("container_removed") is not True
                for document in evidence
            ),
            severe_floor_or_ceiling_failure=severe_floor_or_ceiling,
            actual_usage=usage,
            actual_pair_wall_seconds=pair_wall,
            projected_aggregate_cost_usd=actual_total * 2.0,
            actual_lambda_cost_usd=lambda_cost,
        )
    )
    checkpoint_path = artifact_base / "artifacts/EXP-0001/pilot-v2/first-pair-checkpoint.json"
    _write_exclusive(checkpoint_path, decision)
    record_first_pair_checkpoint(
        pilot_state,
        execution_contract_sha256=contract.sha256,
        decision=decision,
        decided_at_epoch=now,
    )
    return decision


def finalize(args: argparse.Namespace) -> dict[str, object]:
    if len(args.package_commit) != 40 or any(
        character not in "0123456789abcdef" for character in args.package_commit
    ):
        raise T09PilotError("clean package commit is not a full Git object ID")
    contract = load_execution_contract(
        args.execution_contract.resolve(strict=True),
        expected_sha256=args.execution_contract_sha256,
    )
    attempt = contract.attempt(args.run_id)
    attempt_root = args.attempt_root.resolve(strict=True)
    condition_plan_path = args.condition_plan.resolve(strict=True)
    if (
        condition_plan_path.name != Path(attempt.condition_plan_path).name
        or file_sha256(condition_plan_path) != attempt.condition_plan_sha256
    ):
        raise T09PilotError("condition plan changed from its frozen binding")
    if attempt.giclab_commit == "unknown":
        raise T09PilotError("attempt GIC Lab commit was not bound before execution")
    command_path = args.command_manifests.resolve(strict=True)
    if file_sha256(command_path) != args.command_manifests_sha256:
        raise T09PilotError("command manifest set hash changed")
    command_document = _load_object(command_path, label="command manifests")
    command_manifest = _manifest_for_run(command_document, attempt.run_id)
    if command_manifest.get("condition_plan_sha256") != attempt.condition_plan_sha256:
        raise T09PilotError("command/condition binding drifted")

    infrastructure_failure_reasons: list[str] = []
    host_cleanup_path = args.host_cleanup_receipt.resolve(strict=True)
    host_cleanup = _dynamic_object(
        host_cleanup_path,
        label="host-cleanup-receipt",
        failure_reasons=infrastructure_failure_reasons,
    )
    runtime_cleanup_path = attempt_root / "runtime-cleanup.json"
    runtime_cleanup = (
        _dynamic_object(
            runtime_cleanup_path,
            label="runtime-cleanup-receipt",
            failure_reasons=infrastructure_failure_reasons,
        )
        if runtime_cleanup_path.is_file()
        else {}
    )
    runtime_environment_path = attempt_root / "runtime-environment.json"
    runtime_environment = _dynamic_object(
        runtime_environment_path,
        label="runtime-environment",
        failure_reasons=infrastructure_failure_reasons,
    )
    event_path = attempt_root / "normalized-events.jsonl"
    event_records = _dynamic_events(
        event_path,
        failure_reasons=infrastructure_failure_reasons,
    )
    try:
        provider_records = _provider_records(event_records)
    except T09PilotError:
        infrastructure_failure_reasons.append("malformed-provider-call-evidence")
        provider_records = []
    try:
        browser_records = _browser_records(event_records)
    except T09PilotError:
        infrastructure_failure_reasons.append("malformed-browser-action-evidence")
        browser_records = []
    budget_path = attempt_root / "provider-budget.json"
    budget = _dynamic_object(
        budget_path,
        label="provider-budget",
        failure_reasons=infrastructure_failure_reasons,
    )
    if budget and budget.get("unreconciled_provider_attempts") != 0:
        infrastructure_failure_reasons.append("unreconciled-provider-attempt")
    if budget and len(browser_records) != budget.get("browser_actions"):
        infrastructure_failure_reasons.append("browser-action-count-mismatch")
    if budget and len(provider_records) != budget.get("default_service_tier_response_count"):
        infrastructure_failure_reasons.append("provider-receipt-count-mismatch")

    session_paths = _session_paths(attempt_root)
    evaluator_run_id = EVALUATOR_RUN_IDS[ATTEMPT_ORDER.index(attempt.run_id)]
    evaluator_input = {
        "schema_version": "0.1.0",
        "evaluator_run_id": evaluator_run_id,
        "task_id": attempt.task_id,
        "session_paths": [path.relative_to(attempt_root).as_posix() for path in session_paths],
        "session_sha256s": [file_sha256(path) for path in session_paths],
    }
    evaluator_dir = attempt_root / "evaluator"
    evaluator_input_path = evaluator_dir / "input.json"
    evaluator_output_path = evaluator_dir / "output.json"
    _write_exclusive(evaluator_input_path, evaluator_input)
    evaluator_result = evaluate_retained_session(
        EvaluatorIdentity(
            root=args.evaluator_root.resolve(strict=True),
            dataset_path=args.dataset.resolve(strict=True),
            task_index=attempt.task_index,
        ),
        session_paths,
    )
    _write_exclusive(evaluator_output_path, evaluator_result)
    evaluator_valid = evaluator_result.get("evaluator_valid") is True
    raw_score = evaluator_result.get("score")
    score = (
        float(raw_score)
        if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool)
        else None
    )

    required_paths = {
        "provider-budget": budget_path,
        "normalized-events": event_path,
        "host-cleanup-receipt": host_cleanup_path,
        "evaluator-input": evaluator_input_path,
        "evaluator-output": evaluator_output_path,
        "runtime-environment": runtime_environment_path,
        "condition-stdout": attempt_root / "condition.stdout",
        "condition-stderr": attempt_root / "condition.stderr",
    }
    for label, path in required_paths.items():
        if not path.is_file() or path.is_symlink():
            infrastructure_failure_reasons.append(f"missing-{label}")
    if len(session_paths) != 1:
        infrastructure_failure_reasons.append(
            "missing-session-json" if not session_paths else "duplicate-session-json"
        )
    pilot_state = _load_object(args.pilot_state, label="pilot state")
    entered = pilot_state.get("empirical_attempts_entered")
    empirical_entered = isinstance(entered, list) and attempt.run_id in entered
    source_grounded_event = any(
        event.get("kind")
        in {
            "provider-call-failed",
            "provider-call-receipt",
            "requested-browser-action",
            "post-action-result",
        }
        for event in event_records
    )
    artifact_executed = empirical_entered and source_grounded_event
    if empirical_entered and not source_grounded_event:
        infrastructure_failure_reasons.append("missing-source-grounded-empirical-event")
    credential_cleanup = runtime_cleanup.get("secret_cleanup", {})
    runtime_cleanup_present = runtime_cleanup_path.is_file()
    host_state_path = attempt_root / "container-state.json"
    host_state = (
        _dynamic_object(
            host_state_path,
            label="container-state",
            failure_reasons=infrastructure_failure_reasons,
        )
        if host_state_path.is_file()
        else {}
    )
    host_teardown_proves_browser_closed = (
        host_cleanup.get("container_removed") is True
        and host_cleanup.get("owned_container_residue") == []
        and host_state.get("running") is False
    )
    browser_closed = (
        runtime_cleanup_present
        and runtime_cleanup.get("all_environment_closes_succeeded") is True
    ) or host_teardown_proves_browser_closed
    secret_removed = (
        isinstance(credential_cleanup, dict)
        and (
            not runtime_cleanup_present
            or (
                credential_cleanup.get("credential_removed_from_environment") is True
                and credential_cleanup.get("remaining_exact_credential_matches") == 0
            )
        )
        and host_cleanup.get("secret_scan_passed") is True
    )
    container_removed = (
        host_cleanup.get("container_removed") is True
        and host_cleanup.get("owned_container_residue") == []
    )
    timing = host_cleanup.get("timing")
    if not isinstance(timing, dict):
        infrastructure_failure_reasons.append("missing-host-cleanup-timing")
        timing = {"started_at": None, "stopped_at": None, "wall_seconds": None}
    hard_cap_breached = host_cleanup.get("hard_cap_breached") is True
    if not browser_closed:
        infrastructure_failure_reasons.append("browser-cleanup-failed-or-missing")
    if not secret_removed:
        infrastructure_failure_reasons.append("credential-cleanup-failed-or-missing")
    if not container_removed:
        infrastructure_failure_reasons.append("container-cleanup-failed-or-missing")
    if hard_cap_breached:
        infrastructure_failure_reasons.append("runtime-cap-violation")
    infrastructure_failure_reasons = sorted(set(infrastructure_failure_reasons))
    missing_required = any(
        reason.startswith(("missing-", "malformed-"))
        or reason
        in {
            "browser-action-count-mismatch",
            "duplicate-session-json",
            "provider-receipt-count-mismatch",
            "unreconciled-provider-attempt",
        }
        for reason in infrastructure_failure_reasons
    )
    infrastructure_failure = bool(infrastructure_failure_reasons)
    process_exit_code = host_cleanup.get("returncode")
    if type(process_exit_code) is not int:
        process_exit_code = None
    outcome = outcome_contract(
        process_exit_code=process_exit_code,
        artifact_executed=artifact_executed,
        task_completed=evaluator_result.get("task_completed") is True,
        answer_produced=evaluator_result.get("answer_produced") is True,
        evaluator_valid=evaluator_valid,
        score=score,
        infrastructure_failure=infrastructure_failure,
        missing_required_evidence=missing_required,
        infrastructure_failure_reasons=infrastructure_failure_reasons,
    )
    outcome.update(
        {
            "plan_id": PLAN_ID,
            "run_id": attempt.run_id,
            "task_id": attempt.task_id,
            "pair_id": attempt.pair_id,
            "condition": f"SIRA-{attempt.condition.upper()}",
            "score_provenance": {
                "evaluator_revision": SIRA_COMMIT,
                "evaluator_sha256": EVALUATOR_SHA256,
                "dataset_revision": DATASET_REVISION,
                "raw_evaluator_output_sha256": file_sha256(evaluator_output_path),
                "normalization": "exact-upstream-no-renormalization",
            },
        }
    )
    outcome_path = attempt_root / "attempt-outcome.json"

    gpu_accounting_path = attempt_root / "gpu-accounting.json"
    gpu_accounting = (
        _load_object(gpu_accounting_path, label="GPU accounting")
        if gpu_accounting_path.is_file()
        else {
            "visibility": runtime_environment.get("gpu_accounting", {}).get("cuda_visible_devices"),
            "process_use": "unavailable",
            "acceleration_claim": False,
        }
    )
    session_relative = (
        session_paths[0].relative_to(attempt_root).as_posix() if len(session_paths) == 1 else None
    )
    evidence_index = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "execution_contract_sha256": contract.sha256,
        "identity": {
            "run_id": attempt.run_id,
            "task_id": attempt.task_id,
            "task_text_sha256": TASK_TEXT_SHA256S[attempt.task_index],
            "reference_sha256": TASK_REFERENCE_SHA256S[attempt.task_index],
            "pair_id": attempt.pair_id,
            "order_index": attempt.order_index,
            "condition": f"SIRA-{attempt.condition.upper()}",
            "attempt": 1,
        },
        "runtime": {
            "giclab_commit": args.package_commit,
            "reviewed_implementation_ancestor": attempt.giclab_commit,
            "sira_commit": SIRA_COMMIT,
            "python_version": runtime_environment.get("python_version"),
            "container_image_digest": CONTAINER_IMAGE_DIGEST,
            "model_revision": MODEL_REVISION,
            "requested_service_tier": "default",
            "returned_service_tiers": (
                ["default"] if budget.get("default_service_tier_response_count", 0) else []
            ),
            "browser_identity": {"playwright": "1.39.0", "chromium_revision": "1084"},
            "gpu_accounting": gpu_accounting,
        },
        "timing": {
            "started_at": timing.get("started_at"),
            "stopped_at": timing.get("stopped_at"),
            "wall_seconds": timing.get("wall_seconds"),
        },
        "command": {
            "argv": command_manifest["argv"],
            "argv_sha256": command_manifest["argv_sha256"],
            "condition_config_sha256": attempt.condition_plan_sha256,
        },
        "provider_calls": provider_records,
        "browser_actions": browser_records,
        "retained_artifacts": {
            "session_json": session_relative,
            "raw_answer": session_relative,
            "stdout": "condition.stdout",
            "stderr": "condition.stderr",
            "screenshots": "normalized-events.jsonl#/post-action-result/observation/screenshot",
            "normalized_events": "normalized-events.jsonl",
            "regulation_decisions": "normalized-events.jsonl#/regulation-decision-assignment",
            "provider_ledger": "provider-budget.json",
            "evaluator_input": "evaluator/input.json",
            "evaluator_output": "evaluator/output.json",
        },
        "outcome": outcome,
        "evaluator": {
            "run_id": evaluator_run_id,
            "input_sha256": file_sha256(evaluator_input_path),
            "output_sha256": file_sha256(evaluator_output_path),
            "valid": evaluator_valid,
        },
        "cleanup": {
            "browser_closed": browser_closed,
            "container_removed": container_removed,
            "secret_removed": secret_removed,
            "stop_reason": host_cleanup.get("stop_reason"),
            "hard_cap_breached": hard_cap_breached,
            "receipt_sha256": file_sha256(args.host_cleanup_receipt),
        },
        "h2k_optional_fields": {
            "availability": "unavailable-explicitly-null",
            "unsupported_fields": {
                "candidate_actions": None,
                "predicted_futures": None,
                "critic_evaluations": None,
                "selected_plan": None,
                "learned_regulation": None,
                "internalization": None,
            },
            "reason": "not-exposed-by-the-selected-pinned-runner-and-not-required-for-calibration",
            "scientific_effect_on_exp0001": "none",
        },
        "redaction": {
            "structural_policy": "t09-structural-sensitive-field-v1",
            "secret_values_retained": False,
            "private_network_values_public": False,
        },
    }
    evidence_path = attempt_root / "evidence-index.json"
    _validate_output_documents(
        outcome=outcome,
        evidence=evidence_index,
        score_schema_path=args.score_schema,
        evidence_schema_path=args.evidence_schema,
    )
    _write_exclusive(outcome_path, outcome)
    _write_exclusive(evidence_path, evidence_index)
    retained_outcome = _load_object(outcome_path, label="retained attempt outcome")
    retained_evidence = _load_object(evidence_path, label="retained evidence index")
    _validate_output_documents(
        outcome=cast(dict[str, object], retained_outcome),
        evidence=cast(dict[str, object], retained_evidence),
        score_schema_path=args.score_schema,
        evidence_schema_path=args.evidence_schema,
    )
    mark_attempt_completed(
        args.pilot_state,
        execution_contract_sha256=contract.sha256,
        run_id=attempt.run_id,
    )

    decision: dict[str, object] | None = None
    if attempt.run_id == ATTEMPT_ORDER[1]:
        suffix = Path(attempt.output_root).parts
        artifact_base = Path(*attempt_root.parts[: -len(suffix)])
        decision = _first_pair_checkpoint(
            contract=contract,
            command_document=command_document,
            artifact_base=artifact_base,
            aggregate_ledger=args.aggregate_ledger,
            pilot_state=args.pilot_state,
        )
    return {
        "run_id": attempt.run_id,
        "evaluator_valid": evaluator_valid,
        "valid_scored_attempt": outcome["valid_scored_attempt"],
        "first_pair_decision": decision,
    }


def main() -> int:
    result = finalize(_parser().parse_args())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
