#!/usr/bin/env python3
"""Render the four exact T09 commands and pair diffs without executing them."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import cast

from giclab.harness.t09_candidate_inputs import CandidateSourceSnapshot
from giclab.harness.t09_provider_contracts import (
    MetadataPolicy,
    ProviderSelectorPolicy,
    provider_contract,
)
from giclab.harness.t09_sira_pilot import (
    T09PilotError,
    command_argv_sha256,
    diff_pair_manifests,
    file_sha256,
    git_file_sha256,
    load_execution_contract,
    render_command_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--provider-contract",
        required=True,
        help="exact versioned T09 provider package to render",
    )
    return parser


def render(
    repository: Path,
    *,
    provider_version: str,
    source_inputs: CandidateSourceSnapshot | None = None,
) -> dict[str, object]:
    root = repository.resolve(strict=True)
    contract_identity = provider_contract(provider_version)
    if contract_identity.execution_contract_path is None:
        raise ValueError("selected T09 provider contract has no execution package")
    execution_path = root / contract_identity.execution_contract_path
    plan_path = root / contract_identity.provider_profile_path
    runtime_path = root / "src/giclab/harness/sira_gate_a_runtime.py"
    library_path = root / "src/giclab/harness/t09_sira_pilot.py"
    generator_path = Path(__file__).resolve(strict=True)
    execution_sha256 = file_sha256(execution_path)
    contract = load_execution_contract(
        execution_path,
        expected_sha256=execution_sha256,
    )
    control_root = contract_identity.control_root_name
    commits = {attempt.giclab_commit for attempt in contract.attempts}
    if len(commits) != 1 or "unknown" in commits:
        raise ValueError("one reviewed implementation ancestor must be bound before rendering")
    implementation_commit = next(iter(commits))

    def source_hash(relative: str) -> str:
        if source_inputs is not None:
            return source_inputs.source_sha256(root, relative)
        return git_file_sha256(root, implementation_commit, relative)

    runtime_sha256 = source_hash(runtime_path.relative_to(root).as_posix())
    library_sha256 = source_hash(library_path.relative_to(root).as_posix())
    manifests = [
        render_command_manifest(
            contract,
            attempt,
            execution_contract_runtime_path="/opt/giclab-contracts/execution.json",
            runtime_adaptation_path="/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
            runtime_adaptation_sha256=runtime_sha256,
            pilot_library_sha256=library_sha256,
            aggregate_ledger_path=(
                f"/opt/giclab-artifacts/{control_root}/runtime-budget/aggregate-budget.json"
            ),
            pilot_state_path=f"/opt/giclab-artifacts/{control_root}/pilot-state.json",
        )
        for attempt in contract.attempts
    ]
    for index, manifest in enumerate(manifests):
        argv = manifest.get("argv")
        if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
            raise ValueError(f"rendered command {index} has invalid argv")
        try:
            canonical_hash = command_argv_sha256(cast(list[str], argv))
        except (T09PilotError, TypeError):
            raise ValueError(f"rendered command {index} has invalid argv") from None
        if manifest.get("argv_sha256") != canonical_hash:
            raise ValueError(f"rendered command {index} has an inconsistent argv hash")
    pair_diffs = [
        diff_pair_manifests(manifests[0], manifests[1]),
        diff_pair_manifests(manifests[2], manifests[3]),
    ]
    if any(item.get("valid") is not True for item in pair_diffs):
        raise ValueError("one or more T09 command pairs are not matched")
    rendered: dict[str, object] = {
        **(
            {
                "model_metadata_request_count_total": 1,
                "model_metadata_request_location": "local-control-plane-before-lambda-launch",
                "provider_launch_model_metadata_request_count": 0,
                "host_runtime_model_metadata_request_count": 0,
                "model_metadata_receipt_required": True,
                "model_metadata_receipt_replay_allowed": False,
            }
            if contract_identity.capabilities.metadata_policy
            is MetadataPolicy.LOCAL_PRELAUNCH_RECEIPT
            else {}
        ),
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "reviewed_implementation_ancestor": next(iter(commits)),
        "plan_path": plan_path.relative_to(root).as_posix(),
        "plan_sha256": file_sha256(plan_path),
        "plan_size_bytes": plan_path.stat().st_size,
        "execution_contract_path": execution_path.relative_to(root).as_posix(),
        "execution_contract_sha256": execution_sha256,
        "runtime_adaptation_sha256": runtime_sha256,
        "pilot_library_sha256": library_sha256,
        "generator_path": generator_path.relative_to(root).as_posix(),
        "generator_sha256": source_hash(generator_path.relative_to(root).as_posix()),
        "manifests": manifests,
        "pair_diffs": pair_diffs,
    }
    if contract_identity.capabilities.provider_selector_policy is ProviderSelectorPolicy.EXPLICIT:
        rendered["local_finalizer_qualification_selector"] = {
            "argument": "--provider-contract",
            "value": contract_identity.version,
        }
    return rendered


def encode_command_manifest_document(document: object) -> bytes:
    """Encode a generated command-manifest document deterministically."""

    return (json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_exclusive(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = encode_command_manifest_document(document)
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
    write_exclusive(
        args.output.resolve(strict=False),
        render(args.repository, provider_version=args.provider_contract),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
