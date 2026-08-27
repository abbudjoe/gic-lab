#!/usr/bin/env python3
"""Prepare the fresh V9 package while proving V8 scientific equivalence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from giclab.harness.policy import load_run_plan, run_plan_authorization_sha256

PLAN = "PLAN-EXP0001-PILOT-V9"
AUTHORIZATION = (
    "AUTH-T09-AUTONOMOUS-RETRY2-2026-08-27:sha256:"
    "aea63a42cf0270ad0a41a929b4b8eb19dd1c3af73abfe97163c1d90e6077d3da"
)
HOST = "RUN-T09-PILOT-HOST-AUTONOMOUS-0002"
QUALIFICATION = "QUAL-T09-PILOT-V9-IMAGE-AUTONOMOUS-0002"
LOCAL_QUALIFICATION = "QUAL-T09-PILOT-V9-LOCAL-FINALIZER-AUTONOMOUS-0002"
FROZEN_MANIFEST = "RUN-MANIFEST-EXP0001-PILOT-V9-AUTONOMOUS-0002"
V8_SOURCE_COMMIT = "f6d175f3464ceef11e3f6c02d6aba30fe4ceb9f6"
ATTEMPT_REPLACEMENTS = {
    "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0001": ("RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0002"),
    "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0001": ("RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0002"),
    "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0001": ("RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0002"),
    "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0001": ("RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0002"),
}
EVALUATOR_REPLACEMENTS = {
    old.replace("RUN-T09-TASK", "RUN-T09-EVAL-TASK"): new.replace(
        "RUN-T09-TASK", "RUN-T09-EVAL-TASK"
    )
    for old, new in ATTEMPT_REPLACEMENTS.items()
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def transformed_text(value: str) -> str:
    replacements = {
        **ATTEMPT_REPLACEMENTS,
        **EVALUATOR_REPLACEMENTS,
        "PLAN-EXP0001-PILOT-V8": PLAN,
        "RUN-T09-PILOT-HOST-AUTONOMOUS-0001": HOST,
        "QUAL-T09-PILOT-V8-IMAGE-AUTONOMOUS-0001": QUALIFICATION,
        "QUAL-T09-PILOT-V8-LOCAL-FINALIZER-AUTONOMOUS-0001": LOCAL_QUALIFICATION,
        "RUN-MANIFEST-EXP0001-PILOT-V8-AUTONOMOUS-0001": FROZEN_MANIFEST,
        "ARCHIVE-EXP0001-PILOT-V8-AUTONOMOUS-0001": ("ARCHIVE-EXP0001-PILOT-V9-AUTONOMOUS-0002"),
        "STAGE-EXP0001-PILOT-V8-AUTONOMOUS-0001": ("STAGE-EXP0001-PILOT-V9-AUTONOMOUS-0002"),
        "RUNTIME-EXP0001-PILOT-V8-AUTONOMOUS-0001": ("RUNTIME-EXP0001-PILOT-V9-AUTONOMOUS-0002"),
        "PAIR-EXP0001-PILOT-V8-TASK-A": "PAIR-EXP0001-PILOT-V9-TASK-A",
        "PAIR-EXP0001-PILOT-V8-TASK-B": "PAIR-EXP0001-PILOT-V9-TASK-B",
        "EXECUTION-CONTRACT-EXP0001-PILOT-V8": "EXECUTION-CONTRACT-EXP0001-PILOT-V9",
        "pilot-v8-task-": "pilot-v9-task-",
        "EXP-0001-PILOT-V8-": "EXP-0001-PILOT-V9-",
        "artifacts/EXP-0001/pilot-v8/": "artifacts/EXP-0001/pilot-v9/",
        "attempt-autonomous-0001": "attempt-autonomous-0002",
        "autonomous-v8": "autonomous-v9",
        "fresh V8": "fresh V9",
        "frozen V8": "frozen V9",
        "for V8": "for V9",
        "V8 identities": "V9 identities",
        "V8 pairs": "V9 pairs",
        "V8 policy": "V9 policy",
        "excluded from V8 pairs": "excluded from V9 pairs",
        (
            "AUTH-T09-AUTONOMOUS-PREFLIGHT-TO-PILOT-2026-08-27:sha256:"
            "80ded0e246b4f070c3992ae872111c19c64d1ef30115d65a8641709f06e1a484"
        ): AUTHORIZATION,
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


def scientific_projection(document: dict[str, Any]) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for item in document["attempts"]:
        argv = list(item["upstream_argv"])
        argv[0] = "<FRESH-UPSTREAM-RUN-ID>"
        argv[argv.index("--output_dir") + 1] = "<FRESH-OUTPUT-ROOT>"
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


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def git_blob(root: Path, relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{V8_SOURCE_COMMIT}:{relative}"],
        check=True,
        capture_output=True,
    ).stdout


def prepare(root: Path, reviewed_ancestor: str) -> None:
    if re.fullmatch(r"[a-f0-9]{40}", reviewed_ancestor) is None:
        raise ValueError("reviewed ancestor must be a full commit")
    experiment = root / "experiments/EXP-0001-sira-simulative-vs-reactive"
    plan_path = experiment / "run-plans/pilot.yaml"
    runtime_path = experiment / "contracts/T09_PILOT_RUNTIME_IDENTITY.json"
    execution_path = experiment / "contracts/T09_PILOT_EXECUTION_CONTRACT.json"
    commands_path = experiment / "contracts/T09_PILOT_COMMAND_MANIFESTS.json"

    execution_relative = execution_path.relative_to(root).as_posix()
    runtime_relative = runtime_path.relative_to(root).as_posix()
    plan_relative = plan_path.relative_to(root).as_posix()
    source_execution = json.loads(git_blob(root, execution_relative))
    source_science = scientific_projection(source_execution)
    source_plan_bytes = git_blob(root, plan_relative)
    proposal_plan = experiment / "run-plans/proposals/PLAN-EXP0001-PILOT-V8.yaml"
    proposal_plan.write_bytes(source_plan_bytes)
    plan = transform(yaml.safe_load(source_plan_bytes))
    plan["plan_id"] = PLAN
    plan["execution"] = {"authorized": True, "authorization_reference": AUTHORIZATION}
    plan["budget"].update(
        {
            "max_total_cost_usd": 58.0,
            "max_preflight_provider_compute_cost_usd": 10.0,
            "prior_t09_cost_usd": 29.3502995579,
            "cumulative_t09_cost_cap_usd": 90.0,
        }
    )
    plan["provider_lifecycle"].update(
        {
            "maximum_preflight_provider_cost_usd": 10.0,
            "control_plane": "autonomous-v9-provider-call-accounting-repair",
        }
    )
    plan["readiness"]["pre_execution_requirements"][0] = (
        "Bind the exact clean package commit, final plan SHA-256, fresh V9 identities, "
        "and current Retry 2 authorization."
    )
    plan["readiness"]["pre_execution_requirements"][1] = (
        "Pass the established exact-runtime checks plus the exact-container provider-call "
        "accounting regression before the scientific freeze."
    )
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")
    plan_sha = sha256(plan_path)

    runtime = transform(json.loads(git_blob(root, runtime_relative)))
    runtime["plan_id"] = PLAN
    runtime["identity_id"] = "RUNTIME-EXP0001-PILOT-V9-AUTONOMOUS-0002"
    instrumentation = runtime["repository_instrumentation"]
    instrumentation["reviewed_implementation_ancestor"] = reviewed_ancestor
    accounting_path = "containers/sira-smoke/pragmatic/t09_provider_accounting_preflight.py"
    if accounting_path not in {item["path"] for item in instrumentation["files"]}:
        instrumentation["files"].append({"path": accounting_path, "sha256": ""})
    for item in instrumentation["files"]:
        item["sha256"] = sha256(root / item["path"])
    runtime["replacement_image_policy"]["qualification_id"] = QUALIFICATION
    runtime["replacement_image_policy"]["frozen_run_manifest_id"] = FROZEN_MANIFEST
    write_json(runtime_path, runtime)
    runtime_sha = sha256(runtime_path)

    execution = transform(source_execution)
    execution["plan_id"] = PLAN
    execution["contract_id"] = "EXECUTION-CONTRACT-EXP0001-PILOT-V9"
    execution["authorization_reference"] = AUTHORIZATION
    execution["authorized"] = True
    execution["execution_eligibility"] = "current-turn-authorized-after-dynamic-preflight"
    execution["terminal_state"] = "current-turn-authorized-retry2-pending-dynamic-preflight"
    execution["provider_lifecycle"].update(
        {
            "maximum_preflight_provider_cost_usd": 10.0,
            "provider_control_plane": "autonomous-v9-provider-call-accounting-repair",
        }
    )
    execution["budget_calibration"]["hard"].update(
        {
            "preflight_lambda_cost_usd": 10.0,
            "aggregate_total_cost_usd": 58.0,
            "prior_t09_cost_usd": 29.3502995579,
            "cumulative_t09_cost_cap_usd": 90.0,
            "maximum_new_cost_under_cumulative_cap_usd": 58.0,
        }
    )
    execution["runtime"].update(
        {
            "runtime_qualification_id": QUALIFICATION,
            "local_finalizer_qualification_id": LOCAL_QUALIFICATION,
            "frozen_run_manifest_id": FROZEN_MANIFEST,
        }
    )
    execution["identities"].update(
        {
            "host_run_id": HOST,
            "runtime_qualification_id": QUALIFICATION,
            "local_finalizer_qualification_id": LOCAL_QUALIFICATION,
            "frozen_run_manifest_id": FROZEN_MANIFEST,
            "evidence_archive_id": "ARCHIVE-EXP0001-PILOT-V9-AUTONOMOUS-0002",
            "evidence_stage_id": "STAGE-EXP0001-PILOT-V9-AUTONOMOUS-0002",
        }
    )
    condition_root = experiment / "run-plans/conditions"
    condition_paths: dict[str, Path] = {}
    source_condition_names = (
        "pilot-v8-task-0000-reactive.yaml",
        "pilot-v8-task-0000-simulative.yaml",
        "pilot-v8-task-0001-simulative.yaml",
        "pilot-v8-task-0001-reactive.yaml",
    )
    proposal_condition_root = experiment / "run-plans/proposals/conditions"
    for name in source_condition_names:
        source_relative = (condition_root / name).relative_to(root).as_posix()
        source_bytes = git_blob(root, source_relative)
        (proposal_condition_root / name).write_bytes(source_bytes)
        (condition_root / name).write_bytes(source_bytes)
        document = transform(yaml.safe_load(source_bytes))
        document["profile_plan_id"] = PLAN
        document["profile_sha256"] = plan_sha
        document["sources"]["giclab_commit"] = reviewed_ancestor
        document["sources"]["environment_sha256"] = runtime_sha
        document["execution"]["authorization"]["authorization_reference"] = AUTHORIZATION
        target = condition_root / name.replace("pilot-v8", "pilot-v9")
        target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        condition_paths[document["run_id"]] = target
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
    for name, binding in execution["contract_bindings"].items():
        if name in {"plan", "runtime"}:
            continue
        binding_path = root / binding["path"]
        binding["sha256"] = sha256(binding_path)
        if "size_bytes" in binding:
            binding["size_bytes"] = binding_path.stat().st_size
    if scientific_projection(execution) != source_science:
        raise ValueError("V9 preparation changed the immutable scientific contract")
    write_json(execution_path, execution)
    commands_path.unlink(missing_ok=True)
    write_json(
        experiment / "contracts/T09_PILOT_V9_SCIENCE_PROJECTION.json",
        scientific_projection(execution),
    )

    project_state_path = root / "docs/PROJECT_STATE.yaml"
    project_state = yaml.safe_load(project_state_path.read_text(encoding="utf-8"))
    project_state.update(
        {
            "paid_compute_allowed": True,
            "benchmark_execution_allowed": True,
            "cloud_mutation_allowed": True,
            "current_execution_control": None,
            "authorized_run_profile": {
                "plan_id": PLAN,
                "profile_path": plan_path.relative_to(root).as_posix(),
                "profile_sha256": plan_sha,
                "condition_plan_sha256s": [
                    run_plan_authorization_sha256(load_run_plan(path, schema_root=root))
                    for path in condition_paths.values()
                ],
            },
        }
    )
    project_state_path.write_text(yaml.safe_dump(project_state, sort_keys=False), encoding="utf-8")
    registry_path = root / "experiments/registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    experiment_entry = next(
        item for item in registry["experiments"] if item["experiment_id"] == "EXP-0001"
    )
    experiment_entry.pop("current_execution_control", None)
    proposal_relative = proposal_plan.relative_to(root).as_posix()
    if proposal_relative not in experiment_entry["run_profiles"]:
        experiment_entry["run_profiles"].append(proposal_relative)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--reviewed-ancestor", required=True)
    args = parser.parse_args()
    prepare(args.repository.resolve(strict=True), args.reviewed_ancestor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
