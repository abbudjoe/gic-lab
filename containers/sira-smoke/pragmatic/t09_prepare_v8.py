#!/usr/bin/env python3
"""Mechanically prepare the one V8 candidate package from frozen V7 science."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

PLAN_V7 = "PLAN-EXP0001-PILOT-V7"
PLAN_V8 = "PLAN-EXP0001-PILOT-V8"
HOST_V8 = "RUN-T09-PILOT-HOST-AUTONOMOUS-0001"
QUAL_V8 = "QUAL-T09-PILOT-V8-IMAGE-AUTONOMOUS-0001"
MANIFEST_V8 = "RUN-MANIFEST-EXP0001-PILOT-V8-AUTONOMOUS-0001"
AUTHORIZATION = "AUTH-T09-AUTONOMOUS-PREFLIGHT-TO-PILOT-2026-08-27"
AUTHORIZATION_SOURCE_SHA256 = "80ded0e246b4f070c3992ae872111c19c64d1ef30115d65a8641709f06e1a484"
AUTHORIZATION_REFERENCE = f"{AUTHORIZATION}:sha256:{AUTHORIZATION_SOURCE_SHA256}"
ATTEMPT_IDS = {
    "RUN-T09-TASK-A-REACTIVE-0005": "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0001",
    "RUN-T09-TASK-A-SIMULATIVE-0005": "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0001",
    "RUN-T09-TASK-B-SIMULATIVE-0005": "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0001",
    "RUN-T09-TASK-B-REACTIVE-0005": "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0001",
}
EVALUATOR_IDS = {
    key.replace("RUN-T09-TASK", "RUN-T09-EVAL-TASK"): value.replace(
        "RUN-T09-TASK", "RUN-T09-EVAL-TASK"
    )
    for key, value in ATTEMPT_IDS.items()
}
CONDITION_NAMES = (
    "pilot-v7-task-0000-reactive.yaml",
    "pilot-v7-task-0000-simulative.yaml",
    "pilot-v7-task-0001-simulative.yaml",
    "pilot-v7-task-0001-reactive.yaml",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def transformed_text(value: str) -> str:
    replacements = {
        **ATTEMPT_IDS,
        **EVALUATOR_IDS,
        "RUN-T09-PILOT-HOST-0005": HOST_V8,
        "QUAL-T09-PILOT-V7-IMAGE-0001": QUAL_V8,
        "QUAL-T09-PILOT-V7-LOCAL-FINALIZER-0001": (
            "QUAL-T09-PILOT-V8-LOCAL-FINALIZER-AUTONOMOUS-0001"
        ),
        "RUN-MANIFEST-EXP0001-PILOT-V7-0005": MANIFEST_V8,
        "ARCHIVE-EXP0001-PILOT-V7-0005": "ARCHIVE-EXP0001-PILOT-V8-AUTONOMOUS-0001",
        "STAGE-EXP0001-PILOT-V7-0005": "STAGE-EXP0001-PILOT-V8-AUTONOMOUS-0001",
        "PAIR-EXP0001-PILOT-V7-TASK-A": "PAIR-EXP0001-PILOT-V8-TASK-A",
        "PAIR-EXP0001-PILOT-V7-TASK-B": "PAIR-EXP0001-PILOT-V8-TASK-B",
        PLAN_V7: PLAN_V8,
        "pilot-v7-task-": "pilot-v8-task-",
        "EXP-0001-PILOT-V7-": "EXP-0001-PILOT-V8-",
        "artifacts/EXP-0001/pilot-v7/": "artifacts/EXP-0001/pilot-v8/",
        "attempt-0005": "attempt-autonomous-0001",
        "excluded_from_v7_pairing": "excluded_from_v8_pairing",
        "fresh V7": "fresh V8",
        "frozen V7": "frozen V8",
        "for V7": "for V8",
        "V7 source-plan": "V8 source-plan",
        "V7 policy": "V8 policy",
        "V7 pairs": "V8 pairs",
        "V7 identities": "V8 identities",
        "67108864-byte": "536870912-byte",
        "16777216-byte": "67108864-byte",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def transform(value: Any) -> Any:
    if isinstance(value, str):
        return transformed_text(value)
    if isinstance(value, list):
        return [transform(item) for item in value]
    if isinstance(value, dict):
        return {key: transform(item) for key, item in value.items()}
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def scientific_contract(document: dict[str, Any]) -> dict[str, Any]:
    """Project the immutable science while excluding fresh identity/output ownership."""

    attempts: list[dict[str, Any]] = []
    for item in document["attempts"]:
        argv = list(item["upstream_argv"])
        argv[0] = "<FRESH-UPSTREAM-RUN-ID>"
        output_index = argv.index("--output_dir") + 1
        argv[output_index] = "<FRESH-OUTPUT-ROOT>"
        attempts.append(
            {
                "task_id": item["task_id"],
                "task_index": item["task_index"],
                "condition": item["condition"],
                "order_index": item["order_index"],
                "protocol_sha256": item["protocol_sha256"],
                "config_sha256": item["config_sha256"],
                "upstream_argv": argv,
            }
        )
    return {
        "experiment_id": document["experiment_id"],
        "sira_commit": document["sira_commit"],
        "model_revision": document["model_revision"],
        "service_tier": document["service_tier"],
        "randomization_seed": document["randomization_seed"],
        "dataset_binding": document["contract_bindings"]["dataset"],
        "evaluator_binding": document["contract_bindings"]["evaluator"],
        "attempts": attempts,
    }


def prepare(root: Path, reviewed_ancestor: str) -> None:
    if re.fullmatch(r"[a-f0-9]{40}", reviewed_ancestor) is None:
        raise ValueError("reviewed ancestor must be a full commit")
    experiment = root / "experiments/EXP-0001-sira-simulative-vs-reactive"
    plan_path = experiment / "run-plans/pilot.yaml"
    runtime_path = experiment / "contracts/T09_PILOT_RUNTIME_IDENTITY.json"
    execution_path = experiment / "contracts/T09_PILOT_EXECUTION_CONTRACT.json"
    commands_path = experiment / "contracts/T09_PILOT_COMMAND_MANIFESTS.json"
    condition_root = experiment / "run-plans/conditions"
    source_condition_root = experiment / "run-plans/proposals/conditions"

    plan = transform(yaml.safe_load(plan_path.read_text(encoding="utf-8")))
    plan["plan_id"] = PLAN_V8
    plan["budget"].update(
        {
            "max_total_cost_usd": 68.0,
            "max_preflight_provider_compute_cost_usd": 20.0,
            "prior_t09_cost_usd": 6.813138735,
            "cumulative_t09_cost_cap_usd": 75.0,
        }
    )
    plan["failure_evidence_policy"].update(
        {
            "full_attempt_cap_bytes": 536_870_912,
            "stdout_stderr_per_stream_cap_bytes": 536_870_912,
            "essential_failure_cap_bytes": 67_108_864,
        }
    )
    plan["evidence_cap_calibration"].update(
        {
            "retained_attempt_cap_bytes": 536_870_912,
            "remaining_cap_headroom_bytes": 486_539_264,
            "noncore_headroom_ratio": 258.5206712176,
            "conclusion": (
                "the symmetric 512 MiB cap preserves ordinary scientific evidence with "
                "more than 486 MiB beyond the conservative projection; prohibited core "
                "dumps and unrelated runtime state remain excluded"
            ),
        }
    )
    plan["execution"] = {
        "authorized": True,
        "authorization_reference": AUTHORIZATION_REFERENCE,
    }
    lifecycle = plan["provider_lifecycle"]
    for stale in (
        "preflight_wall_seconds",
        "maximum_successful_host_active_seconds",
        "maximum_cumulative_active_seconds",
        "max_launch_count",
    ):
        lifecycle.pop(stale, None)
    lifecycle.update(
        {
            "preflight_iteration_wall_seconds": 3_600,
            "maximum_preflight_instance_active_seconds": 21_600,
            "maximum_cumulative_preflight_active_seconds": 43_200,
            "maximum_preflight_provider_cost_usd": 20.0,
            "max_preflight_launch_count": 8,
            "maximum_empirical_provider_cost_usd": 8.0,
            "max_empirical_launch_count": 1,
            "control_plane": (
                "autonomous-v8-separated-preflight-engineering-and-empirical-authority"
            ),
        }
    )
    plan["replacement_image_policy"]["fallback_build_second_launch_policy"] = (
        "prefer the retained verified archive; rebuild from frozen inputs when loading is "
        "unavailable, corrupt, or slower; keep one accepted image unchanged across all "
        "four empirical attempts and never delay provider cleanup for image export"
    )
    plan["readiness"] = {
        "execution_eligibility": "eligible-after-authorization",
        "approval_changes_required": [],
        "unresolved_execution_blockers": [],
        "pre_execution_requirements": [
            (
                "Bind the exact clean package commit, final plan SHA-256, fresh V8 "
                "identities, and current autonomous authorization."
            ),
            "Pass all sixteen exact-runtime preflight checks before the scientific freeze.",
            "Freeze one accepted image and all commands only after end-to-end preflight succeeds.",
            (
                "Start no attempt unless its hard wall and the 900-second cleanup reserve "
                "fit in actual remaining empirical time."
            ),
            (
                "Keep raw scientific evidence private and access controlled; public "
                "release remains blocked pending review."
            ),
        ],
    }
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")
    plan_sha = sha256(plan_path)

    runtime = transform(json.loads(runtime_path.read_text(encoding="utf-8")))
    runtime["plan_id"] = PLAN_V8
    runtime["identity_id"] = "RUNTIME-EXP0001-PILOT-V8-AUTONOMOUS-0001"
    runtime["repository_instrumentation"]["reviewed_implementation_ancestor"] = reviewed_ancestor
    scope = runtime["repository_instrumentation"]["scope"]
    scope.extend(
        item
        for item in (
            "typed-nested-preempirical-and-normalized-authority-tree-bindings",
            "provider-owned-preflight-cleanup-state-before-staging",
            "pilot-state-before-retained-authority-copy",
            "512MiB-symmetric-attempt-and-64MiB-essential-failure-caps",
        )
        if item not in scope
    )
    for item in runtime["repository_instrumentation"]["files"]:
        item["sha256"] = sha256(root / item["path"])
    runtime["replacement_image_policy"]["qualification_id"] = QUAL_V8
    runtime["replacement_image_policy"]["frozen_run_manifest_id"] = MANIFEST_V8
    runtime_path.write_text(
        json.dumps(runtime, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    runtime_sha = sha256(runtime_path)
    source_execution = json.loads(execution_path.read_text(encoding="utf-8"))
    source_science = scientific_contract(source_execution)
    transformed_attempts = {
        transformed["run_id"]: transformed
        for raw in source_execution["attempts"]
        for transformed in (transform(raw),)
    }

    condition_paths: dict[str, Path] = {}
    source_documents: list[tuple[str, dict[str, Any]]] = []
    for name in CONDITION_NAMES:
        source = source_condition_root / name
        document = transform(yaml.safe_load(source.read_text(encoding="utf-8")))
        document["profile_plan_id"] = PLAN_V8
        document["profile_sha256"] = plan_sha
        document["sources"]["giclab_commit"] = reviewed_ancestor
        document["sources"]["environment_sha256"] = runtime_sha
        document["budget"]["max_output_bytes"] = 536_870_912
        document["execution"]["authorization"] = {
            "authorized": True,
            "authorization_reference": AUTHORIZATION_REFERENCE,
            "command_sha256": canonical_sha256(
                transformed_attempts[document["run_id"]]["upstream_argv"]
            ),
        }
        target_name = name.replace("pilot-v7", "pilot-v8")
        target = condition_root / target_name
        target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        condition_paths[document["run_id"]] = target
        source_documents.append((document["run_id"], document))

    execution = transform(source_execution)
    execution["schema_version"] = "0.4.0"
    execution["plan_id"] = PLAN_V8
    execution["contract_id"] = "EXECUTION-CONTRACT-EXP0001-PILOT-V8"
    execution["authorization_reference"] = AUTHORIZATION_REFERENCE
    execution["authorized"] = True
    execution["execution_eligibility"] = "current-turn-authorized-after-dynamic-preflight"
    execution["terminal_state"] = "current-turn-authorized-autonomous-pending-dynamic-preflight"
    execution["runtime_limits"].update(
        {
            "max_output_bytes_per_attempt": 536_870_912,
            "max_stdout_stderr_bytes_per_stream": 536_870_912,
            "max_essential_failure_bytes": 67_108_864,
            "max_disk_bytes": 2_147_483_648,
            "max_lambda_duration_seconds": 14_400,
        }
    )
    execution_lifecycle = execution["provider_lifecycle"]
    for stale in (
        "preflight_wall_seconds",
        "maximum_successful_host_active_seconds",
        "maximum_cumulative_active_seconds",
        "max_launch_count",
    ):
        execution_lifecycle.pop(stale, None)
    execution_lifecycle.update(
        {
            "preflight_iteration_wall_seconds": 3_600,
            "maximum_preflight_instance_active_seconds": 21_600,
            "maximum_cumulative_preflight_active_seconds": 43_200,
            "maximum_preflight_provider_cost_usd": 20.0,
            "max_preflight_launch_count": 8,
            "maximum_empirical_provider_cost_usd": 8.0,
            "max_empirical_launch_count": 1,
            "provider_control_plane": (
                "autonomous-v8-separated-preflight-engineering-and-empirical-authority"
            ),
        }
    )
    execution["runtime_limits"]["expected_full_attempt_evidence_basis"][
        "remaining_cap_headroom_bytes"
    ] = 486_539_264
    execution["evidence"]["failure_authority"] = (
        "when the full tree breaches 536870912 bytes, either attach stream reaches its "
        "explicit 536870912-byte limit, or another host-runner infrastructure stop prevents "
        "a raw seal, retain one independently capped 67108864-byte allowlisted essential "
        "bundle; mark the condition identity consumed, retain empirical-entry status "
        "separately, classify it infrastructure-invalid and unscored, prohibit retry, and "
        "exclude it from paired analysis"
    )
    execution["evidence"]["stream_capture_policy"] = (
        "stdout and stderr each have an explicit 536870912-byte RLIMIT_FSIZE ceiling; "
        "reaching either bound or receiving unattributable SIGXFSZ is a consumed "
        "infrastructure stop and can never silently produce a valid raw seal"
    )
    hard_budget = execution["budget_calibration"]["hard"]
    hard_budget.update(
        {
            "preflight_lambda_cost_usd": 20.0,
            "aggregate_total_cost_usd": 68.0,
            "prior_t09_cost_usd": 6.813138735,
            "cumulative_t09_cost_cap_usd": 75.0,
            "maximum_new_cost_under_cumulative_cap_usd": 68.186861265,
        }
    )
    execution["budget_calibration"].update(
        {
            "retained_attempt_cap_bytes": 536_870_912,
            "remaining_cap_headroom_bytes": 486_539_264,
            "noncore_headroom_ratio": 258.5206712176,
        }
    )
    execution["runtime"]["runtime_qualification_id"] = QUAL_V8
    execution["runtime"]["frozen_run_manifest_id"] = MANIFEST_V8
    execution["runtime"]["local_finalizer_qualification_id"] = (
        "QUAL-T09-PILOT-V8-LOCAL-FINALIZER-AUTONOMOUS-0001"
    )
    execution["identities"]["local_finalizer_qualification_id"] = (
        "QUAL-T09-PILOT-V8-LOCAL-FINALIZER-AUTONOMOUS-0001"
    )
    for attempt in execution["attempts"]:
        attempt["giclab_commit"] = reviewed_ancestor
        attempt["environment_sha256"] = runtime_sha
        condition_path = condition_paths[attempt["run_id"]]
        attempt["condition_plan_path"] = condition_path.relative_to(root).as_posix()
        attempt["condition_plan_sha256"] = sha256(condition_path)
    execution["contract_bindings"]["plan"] = {
        "path": plan_path.relative_to(root).as_posix(),
        "sha256": plan_sha,
        "size_bytes": plan_path.stat().st_size,
    }
    execution["contract_bindings"]["runtime"] = {
        "path": runtime_path.relative_to(root).as_posix(),
        "sha256": runtime_sha,
    }
    for binding_name, binding in execution["contract_bindings"].items():
        if binding_name in {"plan", "runtime"}:
            continue
        binding_path = root / binding["path"]
        binding["sha256"] = sha256(binding_path)
        if "size_bytes" in binding:
            binding["size_bytes"] = binding_path.stat().st_size
    if scientific_contract(execution) != source_science:
        raise ValueError("V8 preparation changed the immutable scientific contract")
    execution_path.write_text(
        json.dumps(execution, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if commands_path.exists():
        commands_path.unlink()

    # Persist the same typed projection used for the science-invariance gate.
    # Removing isolated argv tokens is unsafe because it can orphan a flag and
    # silently change how every following token is parsed.
    scientific_projection = scientific_contract(execution)
    write_json(experiment / "contracts/T09_PILOT_V8_SCIENCE_PROJECTION.json", scientific_projection)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--repository", type=Path, required=True)
    result.add_argument("--reviewed-ancestor", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    prepare(args.repository.resolve(strict=True), args.reviewed_ancestor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
