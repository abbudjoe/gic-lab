"""Finalize one retained T09 attempt with the exact offline FanOutQA evaluator.

This program runs in a network-disabled container after the condition container is
removed. It cannot call a model or browser. It validates the frozen command and
condition plan, evaluates the retained session, and emits reconstructable derived output
only into one fresh supervisor-owned finalization directory. The frozen supervisor—not
this downstream process—owns campaign sequencing, selection, and checkpoint state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import socket
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from giclab.harness import t09_sira_pilot as pilot_contract
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
    T09PilotError,
    canonical_sha256,
    evaluate_retained_session,
    file_sha256,
    load_execution_contract,
    outcome_contract,
    scientific_attempt_projection,
)

HISTORICAL_V4_REGRESSION_RUN_ID = "RUN-T09-TASK-A-REACTIVE-0002"


def _enforce_zero_core_limit() -> tuple[int, int]:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    limits = resource.getrlimit(resource.RLIMIT_CORE)
    if limits != (0, 0):
        raise T09PilotError("finalizer process-tree core limit is not exactly zero")
    return limits


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-contract", type=Path, required=True)
    parser.add_argument("--execution-contract-sha256", required=True)
    parser.add_argument("--command-manifests", type=Path, required=True)
    parser.add_argument("--command-manifests-sha256", required=True)
    parser.add_argument("--condition-plan", type=Path, required=True)
    parser.add_argument("--raw-attempt-root", type=Path, required=True)
    parser.add_argument("--raw-output-relative", required=True)
    parser.add_argument("--finalized-attempt-root", type=Path, required=True)
    parser.add_argument("--finalized-output-relative", required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--raw-attempt-manifest", type=Path, required=True)
    parser.add_argument("--raw-attempt-receipt", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--package-commit", required=True)
    parser.add_argument("--finalizer-commit", required=True)
    parser.add_argument(
        "--finalizer-execution-mode",
        choices=("qualified-image", "qualified-local"),
        required=True,
    )
    parser.add_argument("--finalizer-source-sha256", required=True)
    parser.add_argument("--finalizer-projection-source-sha256", required=True)
    parser.add_argument("--finalizer-dependency-manifest-sha256", required=True)
    parser.add_argument("--finalizer-runtime-qualification", type=Path, required=True)
    parser.add_argument("--finalizer-runtime-qualification-sha256", required=True)
    parser.add_argument("--frozen-run-manifest", type=Path, required=True)
    parser.add_argument("--frozen-run-manifest-sha256", required=True)
    parser.add_argument("--replacement-image-id", required=True)
    parser.add_argument("--host-cleanup-receipt", type=Path, required=True)
    parser.add_argument("--evaluator-root", type=Path, required=True)
    parser.add_argument("--evaluator-overlay-revalidation", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--score-schema", type=Path, required=True)
    parser.add_argument("--evidence-schema", type=Path, required=True)
    return parser


def _disable_local_network() -> None:
    """Deny every socket construction before local evaluator imports execute."""

    def denied(*_args: object, **_kwargs: object) -> object:
        raise T09PilotError("network is disabled for qualified local finalization")

    socket.socket = denied  # type: ignore[misc,assignment]
    socket.create_connection = denied  # type: ignore[assignment]


def _interpreter_launcher_identity(path: Path) -> dict[str, object]:
    """Revalidate the local venv launcher without collapsing it to its target."""

    if not path.is_absolute():
        raise T09PilotError("qualified local interpreter launcher is not absolute")
    launcher = Path(os.path.abspath(path))
    launcher_metadata = launcher.lstat()
    if launcher_metadata.st_uid != os.getuid() or launcher_metadata.st_nlink != 1:
        raise T09PilotError("qualified local interpreter launcher metadata is unsafe")
    if stat.S_ISLNK(launcher_metadata.st_mode):
        launcher_type = "symlink"
        link_target: str | None = os.readlink(launcher)
        if not link_target or len(os.fsencode(link_target)) > 4_096 or "\0" in link_target:
            raise T09PilotError("qualified local interpreter link target is unsafe")
    elif stat.S_ISREG(launcher_metadata.st_mode):
        launcher_type = "regular"
        link_target = None
        if launcher_metadata.st_mode & 0o022:
            raise T09PilotError("qualified local interpreter launcher is writable")
    else:
        raise T09PilotError("qualified local interpreter launcher is unsafe")
    resolved_target = launcher.resolve(strict=True)
    target_metadata = resolved_target.stat(follow_symlinks=False)
    if (
        resolved_target.is_symlink()
        or not stat.S_ISREG(target_metadata.st_mode)
        or target_metadata.st_uid != os.getuid()
        or target_metadata.st_nlink != 1
        or target_metadata.st_mode & 0o022
    ):
        raise T09PilotError("qualified local interpreter target metadata is unsafe")
    return {
        "interpreter": launcher.as_posix(),
        "interpreter_sha256": file_sha256(launcher),
        "interpreter_launcher_type": launcher_type,
        "interpreter_launcher_mode": f"{stat.S_IMODE(launcher_metadata.st_mode):04o}",
        "interpreter_launcher_link_target": link_target,
        "interpreter_resolved_target": resolved_target.as_posix(),
        "interpreter_resolved_target_sha256": file_sha256(resolved_target),
    }


def _validate_raw_attempt(
    *,
    raw_root: Path,
    manifest_path: Path,
    receipt_path: Path,
    run_id: str,
    package_commit: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Re-hash the complete immutable condition source before downstream work."""

    manifest = _load_object(manifest_path.resolve(strict=True), label="raw-attempt manifest")
    receipt = _load_object(receipt_path.resolve(strict=True), label="raw-attempt receipt")
    files = manifest.get("files")
    if (
        manifest.get("schema_version") != "0.1.0"
        or manifest.get("plan_id") != PLAN_ID
        or manifest.get("run_id") != run_id
        or manifest.get("package_commit") != package_commit
        or manifest.get("raw_attempt_root") != raw_root.name
        or not isinstance(files, list)
        or receipt.get("schema_version") != "0.1.0"
        or receipt.get("plan_id") != PLAN_ID
        or receipt.get("run_id") != run_id
        or receipt.get("raw_manifest_sha256") != file_sha256(manifest_path)
        or receipt.get("raw_attempt_complete") is not True
        or receipt.get("empirical_attempt_consumed") is not True
        or receipt.get("container_and_browser_cleanup_clean") is not True
        or receipt.get("credential_cleanup_clean") is not True
        or receipt.get("source_grounded_empirical_event_count")
        != manifest.get("source_grounded_empirical_event_count")
        or receipt.get("retained_session_count") != manifest.get("retained_session_count")
        or receipt.get("reconstructable_disposition") != manifest.get("reconstructable_disposition")
    ):
        raise T09PilotError("raw-attempt receipt/manifest identity drifted")
    observed_paths: set[str] = set()
    observed_total = 0
    for raw in files:
        if not isinstance(raw, dict):
            raise T09PilotError("raw-attempt manifest file record is malformed")
        relative = raw.get("path")
        size = raw.get("bytes")
        digest = raw.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or type(size) is not int
            or not isinstance(digest, str)
            or len(digest) != 64
            or relative in observed_paths
        ):
            raise T09PilotError("raw-attempt manifest file identity is unsafe")
        path = raw_root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != size
            or file_sha256(path) != digest
        ):
            raise T09PilotError(f"raw-attempt artifact changed or is absent: {relative}")
        observed_paths.add(relative)
        observed_total += size
    actual_paths = {
        path.relative_to(raw_root).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    if actual_paths != observed_paths or observed_total != manifest.get("total_bytes"):
        raise T09PilotError("raw-attempt member set or byte total drifted")
    return manifest, receipt


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


def _host_cleanup_proves_no_credential_exposure(cleanup: Mapping[str, object]) -> bool:
    """Accept explicit V5 proof or the one exact retained V4 regression shape."""

    if cleanup.get("actual_credential_exposure_detected") is False:
        return True
    return (
        "actual_credential_exposure_detected" not in cleanup
        and cleanup.get("run_id") == HISTORICAL_V4_REGRESSION_RUN_ID
        and cleanup.get("secret_bearing_artifacts_removed") == []
        and cleanup.get("secret_matching_paths") == []
    )


def reconstruct_semantic_projection(
    *,
    raw_root: Path,
    evaluator_root: Path,
    dataset_path: Path,
    task_index: int,
    task_id: str,
    condition: str,
    evaluator_result: Mapping[str, object] | None = None,
    session_paths: Sequence[Path] | None = None,
    event_records: Sequence[Mapping[str, object]] | None = None,
    budget_record: Mapping[str, object] | None = None,
    cleanup_record: Mapping[str, object] | None = None,
    runtime_record: Mapping[str, object] | None = None,
    evaluator_fixture_subset: bool = False,
) -> dict[str, object]:
    """Derive the deterministic scientific/evaluator projection from raw bytes only.

    This is shared by the live finalizer and the retained V4 archive regression.  It
    has no provider, model, browser, or network client and performs no writes.
    """

    root = raw_root.resolve(strict=True)
    if root.is_symlink() or not root.is_dir():
        raise T09PilotError("semantic projection raw root is unsafe")
    if task_index not in (0, 1) or task_id not in {
        "7dcbbbdc7f1120cd",
        "2120afba8009bad3",
    }:
        raise T09PilotError("semantic projection task identity is not frozen")
    if condition not in {"SIRA-REACTIVE", "SIRA-SIMULATIVE"}:
        raise T09PilotError("semantic projection condition is not frozen")
    events = (
        [dict(event) for event in event_records]
        if event_records is not None
        else _events(root / "normalized-events.jsonl")
    )
    try:
        provider_records = _provider_records(events)
    except T09PilotError:
        provider_records = []
    try:
        browser_records = _browser_records(events)
    except T09PilotError:
        browser_records = []
    budget = (
        dict(budget_record)
        if budget_record is not None
        else _load_object(root / "provider-budget.json", label="provider budget")
    )
    default_cleanup_path = root / ".giclab-supervisor/host-cleanup-receipt.json"
    if not default_cleanup_path.is_file():
        default_cleanup_path = root / "host-cleanup-receipt.json"
    cleanup = (
        dict(cleanup_record)
        if cleanup_record is not None
        else _load_object(default_cleanup_path, label="host cleanup")
    )
    runtime = (
        dict(runtime_record)
        if runtime_record is not None
        else _load_object(root / "runtime-environment.json", label="runtime environment")
    )
    sessions = list(session_paths) if session_paths is not None else _session_paths(root)
    evaluator = (
        dict(evaluator_result)
        if evaluator_result is not None
        else evaluate_retained_session(
            EvaluatorIdentity(
                root=evaluator_root.resolve(strict=True),
                dataset_path=dataset_path.resolve(strict=True),
                task_index=task_index,
                fixture_subset=evaluator_fixture_subset,
            ),
            sessions,
        )
    )
    timing = cleanup.get("timing")
    timing_record: Mapping[str, object] = timing if isinstance(timing, Mapping) else {}
    raw_consistency = {
        "one_session": len(sessions) == 1,
        "provider_reconciled": budget.get("unreconciled_provider_attempts") == 0,
        "model_revision_matched": budget.get("model_revision") == MODEL_REVISION,
        "provider_receipt_count_matched": (
            budget.get("model_call_attempts") == len(provider_records)
            and budget.get("default_service_tier_response_count") == len(provider_records)
        ),
        "browser_action_count_matched": budget.get("browser_actions") == len(browser_records),
        "python_version_matched": runtime.get("python_version") == "3.11.14",
        "cleanup_complete": (
            isinstance(timing, dict)
            and cleanup.get("container_removed") is True
            and cleanup.get("owned_container_residue") == []
            and cleanup.get("secret_scan_passed") is True
            and cleanup.get("secret_matching_paths") == []
            and _host_cleanup_proves_no_credential_exposure(cleanup)
        ),
    }
    usage = {
        field: budget.get(field)
        for field in (
            "model_call_attempts",
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "total_tokens",
            "browser_actions",
            "cost_usd",
        )
    }
    return {
        "task_id": task_id,
        "condition": condition,
        "model_revision": MODEL_REVISION,
        "sira_commit": SIRA_COMMIT,
        "task_completed": evaluator.get("task_completed") is True,
        "answer_produced": evaluator.get("answer_produced") is True,
        "evaluator_valid": evaluator.get("evaluator_valid") is True,
        "score": evaluator.get("score"),
        "provider_call_count": len(provider_records),
        "browser_action_count": len(browser_records),
        "usage": usage,
        "timing": {
            "started_at": timing_record.get("started_at"),
            "stopped_at": timing_record.get("stopped_at"),
            "wall_seconds": timing_record.get("wall_seconds"),
        },
        "session_sha256": file_sha256(sessions[0]) if len(sessions) == 1 else None,
        "session_sha256s": [file_sha256(path) for path in sessions],
        "raw_consistency": raw_consistency,
        "evaluator_output_semantic_sha256": hashlib.sha256(
            json.dumps(
                evaluator,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest(),
    }


def finalize(args: argparse.Namespace) -> dict[str, object]:
    if len(args.package_commit) != 40 or any(
        character not in "0123456789abcdef" for character in args.package_commit
    ):
        raise T09PilotError("clean package commit is not a full Git object ID")
    if len(args.finalizer_commit) != 40 or any(
        character not in "0123456789abcdef" for character in args.finalizer_commit
    ):
        raise T09PilotError("finalizer commit is not a full Git object ID")
    if file_sha256(Path(__file__).resolve(strict=True)) != args.finalizer_source_sha256:
        raise T09PilotError("executed finalizer bytes do not match their explicit binding")
    if len(args.finalizer_dependency_manifest_sha256) != 64 or any(
        character not in "0123456789abcdef"
        for character in args.finalizer_dependency_manifest_sha256
    ):
        raise T09PilotError("finalizer dependency manifest binding is malformed")
    contract = load_execution_contract(
        args.execution_contract.resolve(strict=True),
        expected_sha256=args.execution_contract_sha256,
    )
    frozen_manifest_path = args.frozen_run_manifest.resolve(strict=True)
    if file_sha256(frozen_manifest_path) != args.frozen_run_manifest_sha256:
        raise T09PilotError("frozen run manifest hash changed")
    frozen_manifest = _load_object(frozen_manifest_path, label="frozen run manifest")
    evaluator_overlay_hashes = tuple(
        frozen_manifest.get(field)
        for field in (
            "evaluator_overlay_manifest_sha256",
            "evaluator_overlay_entries_sha256",
            "evaluator_overlay_packages_sha256",
        )
    )
    interpreter_path = Path(sys.executable)
    interpreter_sha256 = file_sha256(interpreter_path)
    runtime_qualification_path = args.finalizer_runtime_qualification.resolve(strict=True)
    local_qualification: dict[str, Any] | None = None
    if file_sha256(runtime_qualification_path) != args.finalizer_runtime_qualification_sha256:
        raise T09PilotError("finalizer runtime qualification hash changed")
    if args.finalizer_execution_mode == "qualified-image":
        if (
            runtime_qualification_path != frozen_manifest_path
            or args.finalizer_runtime_qualification_sha256 != args.frozen_run_manifest_sha256
            or interpreter_path.as_posix() != "/opt/sira/.venv/bin/python"
        ):
            raise T09PilotError("image finalizer did not use its frozen runtime qualification")
    else:
        local_qualification = _load_object(
            runtime_qualification_path,
            label="qualified local finalizer runtime",
        )
        local_base_packages = local_qualification.get("interpreter_dependency_manifest")
        local_base_tree = local_qualification.get("interpreter_dependency_tree")
        local_evaluator_tree = local_qualification.get("dependency_tree")
        observed_interpreter_identity = _interpreter_launcher_identity(interpreter_path)
        if (
            local_qualification.get("schema_version") != "0.1.0"
            or local_qualification.get("qualification_id")
            != "QUAL-T09-PILOT-V7-LOCAL-FINALIZER-0001"
            or local_qualification.get("package_commit") != args.package_commit
            or local_qualification.get("execution_contract_sha256") != contract.sha256
            or any(
                local_qualification.get(field) != value
                for field, value in observed_interpreter_identity.items()
            )
            or local_qualification.get("python_version") != "3.11.14"
            or local_qualification.get("evaluator_contract_sha256")
            != contract.evaluator_contract_sha256
            or local_qualification.get("dataset_sha256")
            != "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
            or local_qualification.get("network_policy") != "socket-construction-denied"
            or local_qualification.get("real_evidence_regression_passed") is not True
            or not isinstance(local_base_packages, list)
            or not local_base_packages
            or local_base_packages != sorted(local_base_packages)
            or local_qualification.get("interpreter_dependency_manifest_sha256")
            != canonical_sha256(local_base_packages)
            or not isinstance(local_base_tree, dict)
            or local_qualification.get("interpreter_dependency_tree_sha256")
            != canonical_sha256(local_base_tree)
            or not isinstance(local_evaluator_tree, dict)
            or local_qualification.get("dependency_tree_sha256")
            != canonical_sha256(local_evaluator_tree)
            or frozen_manifest.get("local_finalizer_qualification_sha256")
            != args.finalizer_runtime_qualification_sha256
            or frozen_manifest.get("local_finalizer_interpreter_dependency_tree_sha256")
            != local_qualification.get("interpreter_dependency_tree_sha256")
            or frozen_manifest.get("local_finalizer_evaluator_dependency_tree_sha256")
            != local_qualification.get("dependency_tree_sha256")
        ):
            raise T09PilotError("qualified local finalizer runtime drifted")
        _disable_local_network()
    if (
        frozen_manifest.get("plan_id") != PLAN_ID
        or frozen_manifest.get("clean_package_commit") != args.package_commit
        or frozen_manifest.get("execution_contract_sha256") != contract.sha256
        or frozen_manifest.get("replacement_image_id") != args.replacement_image_id
        or frozen_manifest.get("package_manifest_sha256")
        != "4ff2603fa5e0f7033ba773decdcb86abf648dcce22e469d26bc48214e390e104"
        or frozen_manifest.get("chromium_executable_sha256")
        != "0498f208c25339f386413ada7b3c35293b0b6250e67d85446ba9541d7fd636f7"
        or frozen_manifest.get("patched_upstream_runner_sha256")
        != "b06793ad1b366a934b798f9f3272fc80a7104a220cb3304ab3bda2eb2a78b331"
        or frozen_manifest.get("python_interpreter_path") != "/opt/sira/.venv/bin/python"
        or not isinstance(frozen_manifest.get("python_interpreter_sha256"), str)
        or any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in evaluator_overlay_hashes
        )
        or frozen_manifest.get("empirical_entry_crossed") is not False
        or frozen_manifest.get("post_entry_code_science_image_freeze") is not True
    ):
        raise T09PilotError("frozen replacement runtime binding drifted")
    attempt = contract.attempt(args.run_id)
    raw_root = args.raw_attempt_root.resolve(strict=True)
    finalized_root = args.finalized_attempt_root.resolve(strict=False)
    artifact_root = args.artifact_root.resolve(strict=True)
    if args.finalizer_execution_mode == "qualified-image" and (
        raw_root.as_posix() != "/opt/giclab-raw"
        or finalized_root.as_posix() != "/opt/giclab-finalized"
    ):
        raise T09PilotError("container raw/finalized mount points drifted")
    finalized_metadata = finalized_root.stat(follow_symlinks=False)
    if (
        finalized_root.is_symlink()
        or not finalized_root.is_dir()
        or finalized_metadata.st_nlink < 1
        or stat.S_IMODE(finalized_metadata.st_mode) != 0o700
        or any(finalized_root.iterdir())
    ):
        raise T09PilotError("supervisor-owned finalized attempt root is not fresh and empty")
    if args.raw_output_relative != attempt.raw_output_root:
        raise T09PilotError("canonical raw attempt root drifted from the execution contract")
    finalized_relative = Path(args.finalized_output_relative)
    if (
        finalized_relative.is_absolute()
        or ".." in finalized_relative.parts
        or finalized_relative.parent.as_posix() != attempt.finalized_output_root
        or not finalized_relative.name.startswith(args.finalizer_source_sha256 + "-invocation-")
    ):
        raise T09PilotError("versioned finalized attempt root drifted from the contract")
    expected_attempt_root = artifact_root / attempt.output_root
    if args.raw_attempt_manifest.resolve(strict=True) != (
        expected_attempt_root / "raw-attempt-manifest.json"
    ).resolve(strict=True) or args.raw_attempt_receipt.resolve(strict=True) != (
        expected_attempt_root / "raw-attempt-complete.json"
    ).resolve(strict=True):
        raise T09PilotError("raw seal paths drifted from the condition-owned contract")
    raw_manifest, raw_receipt = _validate_raw_attempt(
        raw_root=raw_root,
        manifest_path=args.raw_attempt_manifest,
        receipt_path=args.raw_attempt_receipt,
        run_id=attempt.run_id,
        package_commit=args.package_commit,
    )
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
    if local_qualification is None:
        interpreter_dependency_manifest_sha256 = frozen_manifest["package_manifest_sha256"]
        analysis_evaluator_entries_sha256 = frozen_manifest["evaluator_overlay_entries_sha256"]
        analysis_evaluator_packages_sha256 = frozen_manifest["evaluator_overlay_packages_sha256"]
    else:
        local_dependency_tree = local_qualification.get("dependency_tree")
        if not isinstance(local_dependency_tree, dict):
            raise T09PilotError("qualified local evaluator dependency tree is unavailable")
        interpreter_dependency_manifest_sha256 = local_qualification.get(
            "interpreter_dependency_tree_sha256"
        )
        analysis_evaluator_entries_sha256 = local_dependency_tree.get("entries_sha256")
        analysis_evaluator_packages_sha256 = local_qualification.get(
            "dependency_package_manifest_sha256"
        )
    finalizer_closure = {
        "finalizer_execution_mode": args.finalizer_execution_mode,
        "finalizer_runtime_qualification_sha256": (args.finalizer_runtime_qualification_sha256),
        "finalizer_commit": args.finalizer_commit,
        "finalizer_source_sha256": args.finalizer_source_sha256,
        "finalizer_projection_source_sha256": args.finalizer_projection_source_sha256,
        "scientific_package_commit": args.package_commit,
        "pilot_library_sha256": file_sha256(Path(pilot_contract.__file__).resolve(strict=True)),
        "interpreter": interpreter_path.as_posix(),
        "interpreter_sha256": interpreter_sha256,
        "interpreter_dependency_manifest_sha256": interpreter_dependency_manifest_sha256,
        "replacement_image_id": args.replacement_image_id,
        "execution_contract_sha256": contract.sha256,
        "command_manifests_sha256": args.command_manifests_sha256,
        "dataset_contract_sha256": contract.dataset_contract_sha256,
        "evaluator_contract_sha256": contract.evaluator_contract_sha256,
        "score_schema_sha256": file_sha256(args.score_schema.resolve(strict=True)),
        "evidence_schema_sha256": file_sha256(args.evidence_schema.resolve(strict=True)),
        "evaluator_overlay_entries_sha256": analysis_evaluator_entries_sha256,
        "evaluator_overlay_packages_sha256": analysis_evaluator_packages_sha256,
    }
    if canonical_sha256(finalizer_closure) != args.finalizer_dependency_manifest_sha256:
        raise T09PilotError("finalizer dependency closure drifted from the host binding")

    infrastructure_failure_reasons: list[str] = []
    host_cleanup_path = args.host_cleanup_receipt.resolve(strict=True)
    supervisor_root = host_cleanup_path.parent
    host_cleanup = _dynamic_object(
        host_cleanup_path,
        label="host-cleanup-receipt",
        failure_reasons=infrastructure_failure_reasons,
    )
    runtime_cleanup_path = raw_root / "runtime-cleanup.json"
    runtime_cleanup = (
        _dynamic_object(
            runtime_cleanup_path,
            label="runtime-cleanup-receipt",
            failure_reasons=infrastructure_failure_reasons,
        )
        if runtime_cleanup_path.is_file()
        else {}
    )
    runtime_environment_path = raw_root / "runtime-environment.json"
    runtime_environment = _dynamic_object(
        runtime_environment_path,
        label="runtime-environment",
        failure_reasons=infrastructure_failure_reasons,
    )
    event_path = raw_root / "normalized-events.jsonl"
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
    budget_path = raw_root / "provider-budget.json"
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

    session_paths = _session_paths(raw_root)
    evaluator_run_id = EVALUATOR_RUN_IDS[ATTEMPT_ORDER.index(attempt.run_id)]
    evaluator_input = {
        "schema_version": "0.2.0",
        "evaluator_run_id": evaluator_run_id,
        "task_id": attempt.task_id,
        "session_paths": [path.relative_to(raw_root).as_posix() for path in session_paths],
        "session_sha256s": [file_sha256(path) for path in session_paths],
    }
    evaluator_dir = finalized_root / "evaluator"
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
    semantic_projection = reconstruct_semantic_projection(
        raw_root=raw_root,
        evaluator_root=args.evaluator_root,
        dataset_path=args.dataset,
        task_index=attempt.task_index,
        task_id=attempt.task_id,
        condition=f"SIRA-{attempt.condition.upper()}",
        evaluator_result=evaluator_result,
        session_paths=session_paths,
        event_records=event_records,
        budget_record=budget,
        cleanup_record=host_cleanup,
        runtime_record=runtime_environment,
    )
    raw_consistency = semantic_projection.get("raw_consistency")
    if not isinstance(raw_consistency, dict):
        raise T09PilotError("semantic projection omitted its raw-consistency disposition")
    infrastructure_failure_reasons.extend(
        f"raw-consistency-{name}" for name, passed in raw_consistency.items() if passed is not True
    )
    evaluator_valid = semantic_projection["evaluator_valid"] is True
    raw_score = semantic_projection.get("score")
    score = (
        float(raw_score)
        if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool)
        else None
    )

    evaluator_overlay_revalidation_path = args.evaluator_overlay_revalidation.resolve(strict=True)
    evaluator_overlay_revalidation = _dynamic_object(
        evaluator_overlay_revalidation_path,
        label="evaluator-overlay-revalidation",
        failure_reasons=infrastructure_failure_reasons,
    )
    if local_qualification is None:
        expected_overlay_manifest_sha256 = frozen_manifest.get("evaluator_overlay_manifest_sha256")
        expected_overlay_entries_sha256 = frozen_manifest.get("evaluator_overlay_entries_sha256")
        expected_overlay_packages_sha256 = frozen_manifest.get("evaluator_overlay_packages_sha256")
        expected_dependency_bytes_recomputed: object = None
    else:
        local_evaluator_tree = local_qualification["dependency_tree"]
        assert isinstance(local_evaluator_tree, dict)
        expected_overlay_manifest_sha256 = args.finalizer_runtime_qualification_sha256
        expected_overlay_entries_sha256 = local_evaluator_tree.get("entries_sha256")
        expected_overlay_packages_sha256 = local_qualification.get(
            "dependency_package_manifest_sha256"
        )
        expected_dependency_bytes_recomputed = True
    if (
        evaluator_overlay_revalidation.get("overlay_manifest_sha256")
        != expected_overlay_manifest_sha256
        or evaluator_overlay_revalidation.get("overlay_entries_sha256")
        != expected_overlay_entries_sha256
        or evaluator_overlay_revalidation.get("overlay_packages_sha256")
        != expected_overlay_packages_sha256
        or evaluator_overlay_revalidation.get("packages_recomputed") is not True
        or (
            local_qualification is not None
            and evaluator_overlay_revalidation.get("dependency_bytes_recomputed")
            is not expected_dependency_bytes_recomputed
        )
    ):
        infrastructure_failure_reasons.append("evaluator-overlay-revalidation-mismatch")

    required_paths = {
        "provider-budget": budget_path,
        "normalized-events": event_path,
        "host-cleanup-receipt": host_cleanup_path,
        "evaluator-input": evaluator_input_path,
        "evaluator-output": evaluator_output_path,
        "runtime-environment": runtime_environment_path,
        "evaluator-overlay-revalidation": evaluator_overlay_revalidation_path,
        "condition-stdout": raw_root / "condition.stdout",
        "condition-stderr": raw_root / "condition.stderr",
    }
    for label, path in required_paths.items():
        if not path.is_file() or path.is_symlink():
            infrastructure_failure_reasons.append(f"missing-{label}")
    if len(session_paths) != 1:
        infrastructure_failure_reasons.append(
            "missing-session-json" if not session_paths else "duplicate-session-json"
        )
    empirical_entered = raw_receipt.get("empirical_attempt_consumed") is True
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
    host_state_path = supervisor_root / "container-state.json"
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
        runtime_cleanup_present and runtime_cleanup.get("all_environment_closes_succeeded") is True
    ) or host_teardown_proves_browser_closed
    secret_removed = (
        isinstance(credential_cleanup, dict)
        and (
            not runtime_cleanup_present
            or (
                credential_cleanup.get("credential_removed_from_environment") is True
                and credential_cleanup.get("remaining_exact_credential_matches") == 0
                and credential_cleanup.get("secret_bearing_artifacts_removed") == []
            )
        )
        and host_cleanup.get("secret_scan_passed") is True
        and _host_cleanup_proves_no_credential_exposure(host_cleanup)
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
        task_completed=semantic_projection["task_completed"] is True,
        answer_produced=semantic_projection["answer_produced"] is True,
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
    outcome_path = finalized_root / "attempt-outcome.json"

    gpu_accounting_path = supervisor_root / "gpu-accounting.json"
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
        session_paths[0].relative_to(raw_root).as_posix() if len(session_paths) == 1 else None
    )
    evidence_index: dict[str, object] = {
        "schema_version": "0.3.0",
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
            "finalizer_commit": args.finalizer_commit,
            "finalizer_source_sha256": args.finalizer_source_sha256,
            "finalizer_projection_source_sha256": args.finalizer_projection_source_sha256,
            "finalizer_execution_mode": args.finalizer_execution_mode,
            "finalizer_runtime_qualification_sha256": (args.finalizer_runtime_qualification_sha256),
            "finalizer_dependency_manifest_sha256": (args.finalizer_dependency_manifest_sha256),
            "reviewed_implementation_ancestor": attempt.giclab_commit,
            "sira_commit": SIRA_COMMIT,
            "python_version": runtime_environment.get("python_version"),
            "python_interpreter_path": frozen_manifest.get("python_interpreter_path"),
            "python_interpreter_sha256": frozen_manifest.get("python_interpreter_sha256"),
            "container_image_digest": args.replacement_image_id,
            "frozen_run_manifest_sha256": args.frozen_run_manifest_sha256,
            "qualification_id": frozen_manifest.get("qualification_id"),
            "build_context_manifest_sha256": frozen_manifest.get("build_context_manifest_sha256"),
            "installed_package_manifest_sha256": frozen_manifest.get("package_manifest_sha256"),
            "chromium_executable_sha256": frozen_manifest.get("chromium_executable_sha256"),
            "patched_upstream_runner_sha256": frozen_manifest.get("patched_upstream_runner_sha256"),
            "evaluator_overlay_manifest_sha256": frozen_manifest.get(
                "evaluator_overlay_manifest_sha256"
            ),
            "evaluator_overlay_entries_sha256": frozen_manifest.get(
                "evaluator_overlay_entries_sha256"
            ),
            "evaluator_overlay_packages_sha256": frozen_manifest.get(
                "evaluator_overlay_packages_sha256"
            ),
            "model_revision": MODEL_REVISION,
            "requested_service_tier": "default",
            "returned_service_tiers": (
                ["default"] if budget.get("default_service_tier_response_count", 0) else []
            ),
            "browser_identity": {"playwright": "1.39.0", "chromium_revision": "1084"},
            "gpu_accounting": gpu_accounting,
            "analysis_runtime": {
                "execution_mode": args.finalizer_execution_mode,
                "interpreter": interpreter_path.as_posix(),
                "interpreter_sha256": interpreter_sha256,
                "qualification_sha256": args.finalizer_runtime_qualification_sha256,
                "interpreter_dependency_manifest_sha256": (
                    finalizer_closure["interpreter_dependency_manifest_sha256"]
                ),
                "evaluator_dependency_entries_sha256": finalizer_closure[
                    "evaluator_overlay_entries_sha256"
                ],
                "evaluator_dependency_packages_sha256": finalizer_closure[
                    "evaluator_overlay_packages_sha256"
                ],
                "network": (
                    "socket-construction-denied"
                    if args.finalizer_execution_mode == "qualified-local"
                    else "none"
                ),
            },
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
            "session_json": f"raw/{session_relative}" if session_relative else None,
            "raw_answer": f"raw/{session_relative}" if session_relative else None,
            "stdout": "raw/condition.stdout",
            "stderr": "raw/condition.stderr",
            "screenshots": "raw/normalized-events.jsonl#/post-action-result/observation/screenshot",
            "normalized_events": "raw/normalized-events.jsonl",
            "regulation_decisions": "raw/normalized-events.jsonl#/regulation-decision-assignment",
            "provider_ledger": "raw/provider-budget.json",
            "raw_attempt_manifest": "raw-attempt-manifest.json",
            "raw_attempt_receipt": "raw-attempt-complete.json",
            "evaluator_input": "finalized/evaluator/input.json",
            "evaluator_output": "finalized/evaluator/output.json",
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
    evidence_path = finalized_root / "evidence-index.json"
    _validate_output_documents(
        outcome=outcome,
        evidence=evidence_index,
        score_schema_path=args.score_schema,
        evidence_schema_path=args.evidence_schema,
    )
    _write_exclusive(outcome_path, outcome)
    _write_exclusive(evidence_path, evidence_index)
    attempt_projection = scientific_attempt_projection(evidence_index)
    semantic_projection_path = finalized_root / "semantic-projection.json"
    _write_exclusive(semantic_projection_path, attempt_projection)
    retained_manifest, retained_receipt = _validate_raw_attempt(
        raw_root=raw_root,
        manifest_path=args.raw_attempt_manifest,
        receipt_path=args.raw_attempt_receipt,
        run_id=attempt.run_id,
        package_commit=args.package_commit,
    )
    if retained_manifest != raw_manifest or retained_receipt != raw_receipt:
        raise T09PilotError("raw attempt changed during downstream finalization")
    retained_outcome = _load_object(outcome_path, label="retained attempt outcome")
    retained_evidence = _load_object(evidence_path, label="retained evidence index")
    _validate_output_documents(
        outcome=cast(dict[str, object], retained_outcome),
        evidence=cast(dict[str, object], retained_evidence),
        score_schema_path=args.score_schema,
        evidence_schema_path=args.evidence_schema,
    )
    return {
        "run_id": attempt.run_id,
        "evaluator_valid": evaluator_valid,
        "valid_scored_attempt": outcome["valid_scored_attempt"],
        "finalizer_source_sha256": args.finalizer_source_sha256,
        "finalizer_commit": args.finalizer_commit,
        "finalizer_dependency_manifest_sha256": args.finalizer_dependency_manifest_sha256,
        "finalized_output_root": finalized_relative.as_posix(),
        "semantic_projection_sha256": canonical_sha256(attempt_projection),
        "raw_source_revalidated_after_finalization": True,
    }


def main() -> int:
    core_limits = _enforce_zero_core_limit()
    result = finalize(_parser().parse_args())
    result["core_soft_limit"] = core_limits[0]
    result["core_hard_limit"] = core_limits[1]
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
