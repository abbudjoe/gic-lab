#!/usr/bin/env python3
"""Render the four exact T09 commands and pair diffs without executing them."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from giclab.harness.t09_sira_pilot import (
    diff_pair_manifests,
    file_sha256,
    load_execution_contract,
    render_command_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def render(repository: Path) -> dict[str, object]:
    root = repository.resolve(strict=True)
    experiment = root / "experiments/EXP-0001-sira-simulative-vs-reactive"
    execution_path = experiment / "contracts/T09_PILOT_EXECUTION_CONTRACT.json"
    plan_path = experiment / "run-plans/pilot.yaml"
    runtime_path = root / "src/giclab/harness/sira_gate_a_runtime.py"
    library_path = root / "src/giclab/harness/t09_sira_pilot.py"
    generator_path = Path(__file__).resolve(strict=True)
    execution_sha256 = file_sha256(execution_path)
    contract = load_execution_contract(
        execution_path,
        expected_sha256=execution_sha256,
    )
    commits = {attempt.giclab_commit for attempt in contract.attempts}
    if len(commits) != 1 or "unknown" in commits:
        raise ValueError("one reviewed implementation ancestor must be bound before rendering")
    runtime_sha256 = file_sha256(runtime_path)
    library_sha256 = file_sha256(library_path)
    manifests = [
        render_command_manifest(
            contract,
            attempt,
            execution_contract_runtime_path="/opt/giclab-contracts/execution.json",
            runtime_adaptation_path="/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
            runtime_adaptation_sha256=runtime_sha256,
            pilot_library_sha256=library_sha256,
            aggregate_ledger_path="/opt/giclab-artifacts/pilot-v7/aggregate-budget.json",
            pilot_state_path="/opt/giclab-artifacts/pilot-v7/pilot-state.json",
        )
        for attempt in contract.attempts
    ]
    pair_diffs = [
        diff_pair_manifests(manifests[0], manifests[1]),
        diff_pair_manifests(manifests[2], manifests[3]),
    ]
    if any(item.get("valid") is not True for item in pair_diffs):
        raise ValueError("one or more T09 command pairs are not matched")
    return {
        "schema_version": "0.1.0",
        "plan_id": "PLAN-EXP0001-PILOT-V7",
        "reviewed_implementation_ancestor": next(iter(commits)),
        "plan_path": plan_path.relative_to(root).as_posix(),
        "plan_sha256": file_sha256(plan_path),
        "plan_size_bytes": plan_path.stat().st_size,
        "execution_contract_path": execution_path.relative_to(root).as_posix(),
        "execution_contract_sha256": execution_sha256,
        "runtime_adaptation_sha256": runtime_sha256,
        "pilot_library_sha256": library_sha256,
        "generator_path": generator_path.relative_to(root).as_posix(),
        "generator_sha256": file_sha256(generator_path),
        "manifests": manifests,
        "pair_diffs": pair_diffs,
    }


def write_exclusive(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
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
                raise RuntimeError("command package write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    args = _parser().parse_args()
    write_exclusive(args.output.resolve(strict=False), render(args.repository))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
