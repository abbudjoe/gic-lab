#!/usr/bin/env python3
"""No-provider, no-task preflight for the locked T09 calibration pilot."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
from typing import Any, cast

import spacy

from giclab.harness.sira_gate_a import ProviderBudgetUsage
from giclab.harness.t09_sira_pilot import (
    ATTEMPT_ORDER,
    EvaluatorIdentity,
    evaluate_retained_session,
    file_sha256,
    load_aggregate_usage,
    load_execution_contract,
    render_command_manifest,
    write_aggregate_usage,
)

EXPECTED_PYTHON = "3.11.14"
RUNTIME_MODULES = (
    "giclab.harness.sira_gate_a",
    "giclab.harness.sira_gate_a_runtime",
    "giclab.harness.t09_sira_pilot",
)


class PreflightError(RuntimeError):
    """The exact offline T09 preflight contract failed."""


TASK_A = "What is the batting hand of each of the first five picks in the 1998 MLB draft?"
TASK_B = "What were box office values of the Star Wars films in the prequel and sequel trilogies?"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-contract", type=Path, required=True)
    parser.add_argument("--execution-contract-sha256", required=True)
    parser.add_argument("--command-manifests", type=Path, required=True)
    parser.add_argument("--command-manifests-sha256", required=True)
    parser.add_argument("--runtime-adaptation-sha256", required=True)
    parser.add_argument("--pilot-library-sha256", required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--aggregate-ledger", type=Path, required=True)
    parser.add_argument("--pilot-state", type=Path, required=True)
    parser.add_argument("--evaluator-root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    return parser


def _write_exclusive(path: Path, document: object) -> None:
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
                raise PreflightError("preflight evidence write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PreflightError("command manifest document is malformed")
    return cast(dict[str, Any], value)


def _fixture_session(
    path: Path,
    *,
    goal: str,
    action: str,
    complete: bool,
    history: bool = True,
) -> Path:
    _write_exclusive(
        path,
        {
            "goal": goal,
            "instance_id": None,
            "history": (
                [[{"url": "about:blank"}, action, {"thought": "offline fixture"}]]
                if history
                else []
            ),
            "is_complete": complete,
            "error": "",
        },
    )
    return path


def _run_evaluator_fixtures(
    *,
    attempt_root: Path,
    evaluator_root: Path,
    dataset: Path,
) -> list[dict[str, object]]:
    fixture_root = attempt_root / "evaluator-fixtures"
    fixture_root.mkdir(mode=0o700)
    task_a = EvaluatorIdentity(root=evaluator_root, dataset_path=dataset, task_index=0)
    task_b = EvaluatorIdentity(root=evaluator_root, dataset_path=dataset, task_index=1)
    cases = [
        (
            "correct",
            task_a,
            _fixture_session(
                fixture_root / "correct.json",
                goal=TASK_A,
                action=(
                    "send_msg_to_user('Pat Burrell Right; Mark Mulder Left; Corey Patterson "
                    "Left; Jeff Austin Right; JD Drew Left')"
                ),
                complete=True,
            ),
            0.9,
            True,
        ),
        (
            "incorrect",
            task_a,
            _fixture_session(
                fixture_root / "incorrect.json",
                goal=TASK_A,
                action="send_msg_to_user('No relevant answer.')",
                complete=True,
            ),
            0.0,
            True,
        ),
        (
            "partial",
            task_a,
            _fixture_session(
                fixture_root / "partial.json",
                goal=TASK_A,
                action="send_msg_to_user('Pat Burrell bats Right.')",
                complete=True,
            ),
            0.3,
            True,
        ),
        (
            "malformed",
            task_a,
            _fixture_session(
                fixture_root / "malformed.json",
                goal=TASK_A,
                action="send_msg_to_user('Pat Burrell Right'",
                complete=False,
            ),
            0.3,
            True,
        ),
        (
            "missing",
            task_a,
            _fixture_session(
                fixture_root / "missing.json",
                goal=TASK_A,
                action="click('body')",
                complete=False,
            ),
            0.0,
            True,
        ),
        (
            "normalization",
            task_a,
            _fixture_session(
                fixture_root / "normalization.json",
                goal=TASK_A,
                action=(
                    "send_msg_to_user('PAT BURRELL: RIGHT! MARK MULDER, LEFT; COREY "
                    "PATTERSON LEFT. JEFF AUSTIN RIGHT? JD DREW LEFT.')"
                ),
                complete=True,
            ),
            1.0,
            True,
        ),
        (
            "task-b-ordinary",
            task_b,
            _fixture_session(
                fixture_root / "task-b-ordinary.json",
                goal=TASK_B,
                action=(
                    "send_msg_to_user('The Phantom Menace $1.027 billion; Attack of the "
                    "Clones $653.8 million; Revenge of the Sith $868.4 million; The Force "
                    "Awakens $2.071 billion; The Last Jedi $1.334 billion; The Rise of "
                    "Skywalker $1.077 billion')"
                ),
                complete=True,
            ),
            0.5,
            True,
        ),
        (
            "task-b-normalization-edge",
            task_b,
            _fixture_session(
                fixture_root / "task-b-normalization-edge.json",
                goal=TASK_B,
                action=(
                    "send_msg_to_user('The Phantom Menace x$ 1.027 billion; Attack of the "
                    "Clones x$ 653.8 million; Revenge of the Sith x$ 868.4 million; The Force "
                    "Awakens x$ 2.071 billion; The Last Jedi x$ 1.334 billion; The Rise of "
                    "Skywalker x$ 1.077 billion')"
                ),
                complete=True,
            ),
            1.0,
            True,
        ),
    ]
    results: list[dict[str, object]] = []
    for name, identity, session, expected_score, expected_valid in cases:
        observed = evaluate_retained_session(identity, [session])
        score = observed.get("score")
        if (
            observed.get("evaluator_valid") is not expected_valid
            or not isinstance(score, (int, float))
            or isinstance(score, bool)
            or abs(float(score) - expected_score) > 1e-12
        ):
            raise PreflightError(f"offline evaluator fixture drifted: {name}")
        results.append(
            {
                "name": name,
                "score": float(score),
                "evaluator_valid": True,
                "session_sha256": file_sha256(session),
            }
        )
    exception_session = _fixture_session(
        fixture_root / "exception.json",
        goal=TASK_A,
        action="",
        complete=False,
        history=False,
    )
    exception_result = evaluate_retained_session(task_a, [exception_session])
    if (
        exception_result.get("evaluator_valid") is not False
        or exception_result.get("failure_code") != "evaluator_exception"
        or exception_result.get("score") is not None
    ):
        raise PreflightError("offline evaluator exception fixture drifted")
    duplicate_result = evaluate_retained_session(task_a, [cases[0][2], cases[0][2]])
    if (
        duplicate_result.get("evaluator_valid") is not False
        or duplicate_result.get("failure_code") != "duplicate_evidence"
        or duplicate_result.get("score") is not None
    ):
        raise PreflightError("offline evaluator duplicate fixture drifted")
    results.extend(
        [
            {"name": "exception", "score": None, "evaluator_valid": False},
            {"name": "duplicate", "score": None, "evaluator_valid": False},
        ]
    )
    return results


def run(args: argparse.Namespace) -> dict[str, object]:
    if platform.python_version() != EXPECTED_PYTHON:
        raise PreflightError(
            f"preflight Python must be {EXPECTED_PYTHON}; observed {platform.python_version()}"
        )
    if any(name in os.environ for name in ("SIRA_API_KEY", "OPENAI_API_KEY", "LAMBDA_API_KEY")):
        raise PreflightError("offline preflight inherited a provider credential")

    imported = []
    for name in RUNTIME_MODULES:
        importlib.import_module(name)
        imported.append(name)

    execution_path = args.execution_contract.resolve(strict=True)
    if file_sha256(execution_path) != args.execution_contract_sha256:
        raise PreflightError("execution contract hash drifted")
    contract = load_execution_contract(
        execution_path,
        expected_sha256=args.execution_contract_sha256,
    )
    if any(attempt.giclab_commit == "unknown" for attempt in contract.attempts):
        raise PreflightError("reviewed GIC Lab commit is not bound")

    command_path = args.command_manifests.resolve(strict=True)
    if file_sha256(command_path) != args.command_manifests_sha256:
        raise PreflightError("command manifest set hash drifted")
    command_document = _load_object(command_path)
    observed = command_document.get("manifests")
    if not isinstance(observed, list) or len(observed) != 4:
        raise PreflightError("exactly four command manifests are required")
    rendered = [
        render_command_manifest(
            contract,
            attempt,
            execution_contract_runtime_path="/opt/giclab-contracts/execution.json",
            runtime_adaptation_path="/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
            runtime_adaptation_sha256=args.runtime_adaptation_sha256,
            pilot_library_sha256=args.pilot_library_sha256,
            aggregate_ledger_path=str(args.aggregate_ledger),
            pilot_state_path=str(args.pilot_state),
        )
        for attempt in contract.attempts
    ]
    if rendered != observed:
        raise PreflightError("stored commands do not equal a fresh exact render")
    if [item.get("run_id") for item in observed if isinstance(item, dict)] != list(ATTEMPT_ORDER):
        raise PreflightError("command order drifted")
    pair_diffs = command_document.get("pair_diffs")
    if (
        not isinstance(pair_diffs, list)
        or len(pair_diffs) != 2
        or any(not isinstance(item, dict) or item.get("valid") is not True for item in pair_diffs)
    ):
        raise PreflightError("command pair equality failed")

    attempt_root = args.attempt_root.resolve(strict=True)
    probe = attempt_root / "evidence-write-probe.txt"
    payload = b"T09 preflight evidence probe\n"
    descriptor = os.open(
        probe,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        if os.write(descriptor, payload) != len(payload):
            raise PreflightError("preflight evidence probe write was short")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if probe.read_bytes() != payload:
        raise PreflightError("preflight evidence probe readback failed")

    aggregate_path = args.aggregate_ledger.resolve(strict=False)
    if aggregate_path.exists():
        raise PreflightError("aggregate budget ledger must be fresh")
    write_aggregate_usage(
        aggregate_path,
        contract_sha256=contract.sha256,
        usage=ProviderBudgetUsage(),
        unreconciled_provider_attempts=0,
    )
    observed_usage = load_aggregate_usage(aggregate_path, contract_sha256=contract.sha256)
    if observed_usage != ProviderBudgetUsage():
        raise PreflightError("zero aggregate budget ledger did not round-trip")

    evaluator = EvaluatorIdentity(
        root=args.evaluator_root.resolve(strict=True),
        dataset_path=args.dataset.resolve(strict=True),
        task_index=0,
    )
    evaluator.verify()
    EvaluatorIdentity(
        root=evaluator.root,
        dataset_path=evaluator.dataset_path,
        task_index=1,
    ).verify()
    spacy.load("en_core_web_sm")
    expected_versions = {
        "en-core-web-sm": "3.8.0",
        "ftfy": "6.3.1",
        "rouge-score": "0.1.2",
        "spacy": "3.8.11",
        "tqdm": "4.67.3",
    }
    observed_versions = {
        package: importlib.metadata.version(package) for package in expected_versions
    }
    if observed_versions != expected_versions:
        raise PreflightError("evaluator package version identity drifted")
    fixture_results = _run_evaluator_fixtures(
        attempt_root=attempt_root,
        evaluator_root=evaluator.root,
        dataset=evaluator.dataset_path,
    )

    result = {
        "schema_version": "0.1.0",
        "python_version": platform.python_version(),
        "runtime_modules": imported,
        "evidence_write_fsync_readback": "passed",
        "aggregate_budget_ledger": "passed-zero-state",
        "command_rendering": "passed-four-exact-pair-valid",
        "evaluator_loading": "passed-exact-network-none",
        "evaluator_package_versions": observed_versions,
        "offline_evaluator_fixtures": "passed-approved-exact-results",
        "offline_evaluator_fixture_results": fixture_results,
        "task_loading": "passed-two-exact-rows",
        "provider_or_task_request": False,
        "browser_action": False,
        "execution_contract_sha256": contract.sha256,
        "command_manifests_sha256": args.command_manifests_sha256,
    }
    _write_exclusive(attempt_root / "offline-runtime-preflight.json", result)
    return result


def main() -> int:
    print(json.dumps(run(_parser().parse_args()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
