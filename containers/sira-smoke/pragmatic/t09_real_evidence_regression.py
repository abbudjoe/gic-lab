#!/usr/bin/env python3
"""Re-run the current finalizer semantic primitive on the sealed V4 raw fixture.

The fixed archive is read-only input.  Only an allowlisted raw subset is extracted
into a temporary private directory; accepted V4 derived output is read solely as the
comparison oracle.  This program has no provider, model, browser, or network client.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import socket
import stat
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, cast
from unittest import mock

ARCHIVE_SHA256 = "63ed19b35bcb4cb62c3796a80a48004937340eb3826f9657a1006e251772255d"
DISPOSITION_SHA256 = "ecc0e135695e16f68d52b7aa85b70d42b1f1e945f7dd119fb7c7ff0e42fc8231"
PRIOR_RUN_ID = "RUN-T09-TASK-A-REACTIVE-0002"
TASK_ID = "7dcbbbdc7f1120cd"
DATASET_SHA256 = "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
DATASET_BYTES = 1_177_174
EVALUATOR_CONTRACT_SHA256 = "c28a802a45fc8d1e719f8c1bcb22315c2841df831c4ae161f12ab0f2fd08b321"
MAX_ARCHIVE_BYTES = 100_663_296
MAX_MEMBER_BYTES = 67_108_864
MAX_SELECTED_BYTES = 67_108_864
MAX_MEMBERS = 2_048
RAW_EXACT_MEMBERS = frozenset(
    {
        "attempt-wall.json",
        "condition.stderr",
        "condition.stdout",
        "container-command.json",
        "container-state.json",
        "gpu-accounting.json",
        "host-cleanup-receipt.json",
        "normalized-events.jsonl",
        "provider-budget.json",
        "runtime-cleanup.json",
        "runtime-environment.json",
    }
)
RAW_PREFIXES = ("sira-output/",)
COMPARISON_MEMBERS = frozenset({"attempt-outcome.json", "evidence-index.json"})


class RegressionError(RuntimeError):
    """The retained real-evidence regression failed closed."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--public-disposition", type=Path, required=True)
    parser.add_argument("--finalizer-source", type=Path, required=True)
    parser.add_argument("--finalizer-source-sha256", required=True)
    parser.add_argument("--evaluator-root", type=Path, required=True)
    parser.add_argument("--evaluator-contract", type=Path, required=True)
    parser.add_argument("--dependency-site-packages", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument(
        "--receipt-id",
        choices=(
            "T09-PRAGMATIC-RETRY3-REAL-EVIDENCE-REGRESSION-0001",
            "T09-PRAGMATIC-RETRY3-QUALIFIED-IMAGE-REGRESSION-0001",
            "T09-PRAGMATIC-RETRY4-REAL-EVIDENCE-REGRESSION-0001",
            "T09-PRAGMATIC-RETRY4-QUALIFIED-IMAGE-REGRESSION-0001",
            "T09-PRAGMATIC-RETRY5-QUALIFIED-IMAGE-REGRESSION-0001",
        ),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _load_json_bytes(value: bytes, *, label: str) -> dict[str, Any]:
    try:
        document: object = json.loads(value)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RegressionError(f"{label} is malformed JSON") from exc
    if not isinstance(document, dict) or not all(isinstance(key, str) for key in document):
        raise RegressionError(f"{label} is not a string-keyed object")
    return cast(dict[str, Any], document)


def _safe_members(handle: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    members = handle.getmembers()
    if not 1 <= len(members) <= MAX_MEMBERS:
        raise RegressionError("retained archive member count is invalid")
    result: dict[str, tarfile.TarInfo] = {}
    for member in members:
        name = PurePosixPath(member.name)
        if (
            not member.isfile()
            or name.is_absolute()
            or ".." in name.parts
            or member.name in result
            or member.size < 0
            or member.size > MAX_MEMBER_BYTES
        ):
            raise RegressionError("retained archive contains an unsafe member")
        result[member.name] = member
    return result


def _selected_raw(name: str) -> bool:
    return name in RAW_EXACT_MEMBERS or any(name.startswith(prefix) for prefix in RAW_PREFIXES)


def _extract_selected_raw(
    handle: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    destination: Path,
) -> list[dict[str, object]]:
    selected = sorted(name for name in members if _selected_raw(name))
    if not RAW_EXACT_MEMBERS.issubset(selected):
        raise RegressionError("retained archive lacks a required raw member")
    if len([name for name in selected if name.startswith("sira-output/")]) != 1:
        raise RegressionError("retained archive does not contain exactly one raw session")
    manifest: list[dict[str, object]] = []
    total = 0
    for name in selected:
        member = members[name]
        total += member.size
        if total > MAX_SELECTED_BYTES:
            raise RegressionError("selected raw fixture exceeds its byte cap")
        source = handle.extractfile(member)
        if source is None:
            raise RegressionError("selected raw member cannot be read")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o400,
        )
        digest = hashlib.sha256()
        observed = 0
        try:
            while chunk := source.read(1_048_576):
                digest.update(chunk)
                observed += len(chunk)
                if observed > member.size or os.write(descriptor, chunk) != len(chunk):
                    raise RegressionError("selected raw member write drifted")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if observed != member.size:
            raise RegressionError("selected raw member size drifted")
        manifest.append(
            {
                "path": name,
                "bytes": observed,
                "sha256": digest.hexdigest(),
            }
        )
    return manifest


def _member_json(
    handle: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    name: str,
) -> dict[str, Any]:
    member = members.get(name)
    source = handle.extractfile(member) if member is not None else None
    if source is None:
        raise RegressionError(f"retained archive lacks {name}")
    return _load_json_bytes(source.read(), label=name)


def _load_finalizer(path: Path, expected_sha256: str) -> ModuleType:
    source = path.resolve(strict=True)
    metadata = source.stat(follow_symlinks=False)
    if (
        source.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or file_sha256(source) != expected_sha256
    ):
        raise RegressionError("finalizer source identity drifted")
    specification = importlib.util.spec_from_file_location("giclab_t09_real_finalizer", source)
    if specification is None or specification.loader is None:
        raise RegressionError("finalizer source cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _write_exclusive(path: Path, value: object) -> None:
    encoded = (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        if os.write(descriptor, encoded) != len(encoded):
            raise RegressionError("regression receipt write was short")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _evaluator_closure(
    *,
    evaluator_root: Path,
    evaluator_contract: Path,
    dependency_site_packages: Path,
) -> dict[str, object]:
    """Bind evaluator source and the exact realized reviewed package set."""

    contract_path = evaluator_contract.resolve(strict=True)
    if file_sha256(contract_path) != EVALUATOR_CONTRACT_SHA256:
        raise RegressionError("evaluator contract identity drifted")
    contract = _load_json_bytes(contract_path.read_bytes(), label="evaluator contract")
    identity = contract.get("identity")
    materialization = contract.get("materialization")
    if not isinstance(identity, dict) or not isinstance(materialization, dict):
        raise RegressionError("evaluator contract closure is malformed")
    raw_files = identity.get("files")
    inventory = materialization.get("dependency_license_inventory")
    if not isinstance(raw_files, list) or not isinstance(inventory, list):
        raise RegressionError("evaluator file or dependency inventory is unavailable")
    root = evaluator_root.resolve(strict=True)
    files: list[dict[str, object]] = []
    for raw in raw_files:
        if not isinstance(raw, dict):
            raise RegressionError("evaluator file binding is malformed")
        source_path = raw.get("path")
        expected_sha256 = raw.get("sha256")
        prefix = "evaluation/fanout/"
        if (
            not isinstance(source_path, str)
            or not source_path.startswith(prefix)
            or not isinstance(expected_sha256, str)
        ):
            raise RegressionError("evaluator file identity is malformed")
        relative = source_path.removeprefix(prefix)
        path = (root / relative).resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError:
            raise RegressionError("evaluator file escaped its root") from None
        if path.is_symlink() or file_sha256(path) != expected_sha256:
            raise RegressionError("evaluator source file identity drifted")
        files.append({"path": source_path, "sha256": expected_sha256})
    expected_packages: list[str] = []
    for raw in inventory:
        if not isinstance(raw, str) or raw.count("|") != 1:
            raise RegressionError("evaluator dependency inventory is malformed")
        package, license_identity = raw.split("|", 1)
        if "==" not in package or not license_identity:
            raise RegressionError("evaluator dependency identity is malformed")
        name, version = package.split("==", 1)
        expected_packages.append(f"{re.sub(r'[-_.]+', '-', name).lower()}=={version}")
    site_packages = dependency_site_packages.resolve(strict=True)
    if site_packages.is_symlink() or not site_packages.is_dir():
        raise RegressionError("evaluator dependency root is unsafe")
    realized_packages: list[str] = []
    for distribution in importlib.metadata.distributions(path=[str(site_packages)]):
        name = distribution.metadata["Name"]
        version = distribution.version
        if not isinstance(name, str) or not name or not version:
            raise RegressionError("realized evaluator package identity is malformed")
        realized_packages.append(f"{re.sub(r'[-_.]+', '-', name).lower()}=={version}")
    expected_packages.sort()
    realized_packages.sort()
    if (
        len(realized_packages) != len(set(realized_packages))
        or realized_packages != expected_packages
    ):
        raise RegressionError("realized evaluator package set differs from the contract")
    return {
        "evaluator_contract_sha256": EVALUATOR_CONTRACT_SHA256,
        "evaluator_revision": identity.get("revision"),
        "evaluator_files": files,
        "evaluator_files_sha256": canonical_sha256(files),
        "dependency_package_records": realized_packages,
        "dependency_package_manifest_sha256": canonical_sha256(realized_packages),
        "evaluator_lock_sha256": materialization.get("lock_sha256"),
    }


def run(args: argparse.Namespace) -> dict[str, object]:
    archive = args.archive.resolve(strict=True)
    disposition = args.public_disposition.resolve(strict=True)
    if (
        archive.is_symlink()
        or not archive.is_file()
        or not 0 < archive.stat().st_size <= MAX_ARCHIVE_BYTES
        or file_sha256(archive) != ARCHIVE_SHA256
        or file_sha256(disposition) != DISPOSITION_SHA256
    ):
        raise RegressionError("retained V4 archive or public disposition identity drifted")
    finalizer = _load_finalizer(args.finalizer_source, args.finalizer_source_sha256)
    reconstruct = getattr(finalizer, "reconstruct_semantic_projection", None)
    if not callable(reconstruct):
        raise RegressionError("repaired finalizer semantic primitive is unavailable")
    public = _load_json_bytes(disposition.read_bytes(), label="public V4 disposition")
    public_attempt = public.get("attempts", {}).get("task_a_reactive")
    if not isinstance(public_attempt, dict):
        raise RegressionError("public V4 accepted attempt projection is unavailable")
    dataset = args.dataset.resolve(strict=True)
    if (
        dataset.is_symlink()
        or dataset.stat().st_size != DATASET_BYTES
        or file_sha256(dataset) != DATASET_SHA256
    ):
        raise RegressionError("full pinned FanOutQA dataset identity drifted")
    evaluator_closure = _evaluator_closure(
        evaluator_root=args.evaluator_root,
        evaluator_contract=args.evaluator_contract,
        dependency_site_packages=args.dependency_site_packages,
    )
    with tempfile.TemporaryDirectory(prefix="giclab-t09-v4-regression-") as temporary:
        raw_root = Path(temporary) / "raw"
        raw_root.mkdir(mode=0o700)
        with tarfile.open(archive, "r:gz") as handle:
            members = _safe_members(handle)
            selected_manifest = _extract_selected_raw(handle, members, raw_root)
            accepted_outcome = _member_json(handle, members, "attempt-outcome.json")
            accepted_evidence = _member_json(handle, members, "evidence-index.json")

        def denied(*_args: object, **_kwargs: object) -> Any:
            raise RegressionError("network access is forbidden during real-evidence regression")

        with (
            mock.patch.object(socket, "socket", side_effect=denied),
            mock.patch.object(socket, "create_connection", side_effect=denied),
        ):
            projection: object = reconstruct(
                raw_root=raw_root,
                evaluator_root=args.evaluator_root.resolve(strict=True),
                dataset_path=dataset,
                task_index=0,
                task_id=TASK_ID,
                condition="SIRA-REACTIVE",
                evaluator_fixture_subset=False,
            )
            repeated_projection: object = reconstruct(
                raw_root=raw_root,
                evaluator_root=args.evaluator_root.resolve(strict=True),
                dataset_path=dataset,
                task_index=0,
                task_id=TASK_ID,
                condition="SIRA-REACTIVE",
                evaluator_fixture_subset=False,
            )
        if not isinstance(projection, dict):
            raise RegressionError("real-evidence semantic projection is not an object")
        if repeated_projection != projection:
            raise RegressionError("same raw evidence produced a different semantic projection")
        repeat_files: list[dict[str, object]] = []
        for ordinal, value in enumerate((projection, repeated_projection), start=1):
            repeat_root = Path(temporary) / f"finalization-{ordinal:04d}"
            repeat_root.mkdir(mode=0o700)
            repeat_path = repeat_root / "semantic-projection.json"
            _write_exclusive(repeat_path, value)
            repeat_files.append(
                {
                    "root": repeat_root.name,
                    "semantic_projection_file_sha256": file_sha256(repeat_path),
                    "semantic_projection_sha256": canonical_sha256(value),
                }
            )
        if (
            repeat_files[0]["root"] == repeat_files[1]["root"]
            or repeat_files[0]["semantic_projection_sha256"]
            != repeat_files[1]["semantic_projection_sha256"]
        ):
            raise RegressionError("distinct finalization roots changed semantic output")
        expected = {
            "task_id": TASK_ID,
            "condition": "SIRA-REACTIVE",
            "model_revision": "gpt-4o-2024-11-20",
            "sira_commit": "93fb8d72de71f9a4a13419670adeb34d93cf7acd",
            "task_completed": True,
            "answer_produced": True,
            "evaluator_valid": True,
            "score": 0.0,
            "provider_call_count": 52,
            "browser_action_count": 13,
            "usage": {
                "model_call_attempts": 52,
                "input_tokens": 114181,
                "cached_input_tokens": 0,
                "output_tokens": 7719,
                "total_tokens": 121900,
                "browser_actions": 13,
                "cost_usd": 0.3626425,
            },
            "timing": {
                "started_at": "2026-08-13T22:39:09.293373Z",
                "stopped_at": "2026-08-13T22:42:27.665407Z",
                "wall_seconds": 199.19638025899985,
            },
        }
        if any(projection.get(key) != value for key, value in expected.items()):
            raise RegressionError("repaired finalizer changed an accepted semantic field")
        accepted_identity = accepted_evidence.get("identity")
        accepted_runtime = accepted_evidence.get("runtime")
        expected_usage = cast(dict[str, object], expected["usage"])
        public_usage = {
            "model_call_attempts": public_attempt.get("model_calls"),
            "input_tokens": public_attempt.get("input_tokens"),
            "cached_input_tokens": public_attempt.get("cached_input_tokens"),
            "output_tokens": public_attempt.get("output_tokens"),
            "total_tokens": public_attempt.get("total_tokens"),
            "browser_actions": public_attempt.get("browser_actions"),
            "cost_usd": public_attempt.get("openai_cost_usd"),
        }
        if (
            accepted_outcome.get("run_id") != PRIOR_RUN_ID
            or accepted_outcome.get("task_id") != TASK_ID
            or accepted_outcome.get("condition") != "SIRA-REACTIVE"
            or accepted_outcome.get("task_completion") != "completed"
            or accepted_outcome.get("answer_production") is not True
            or accepted_outcome.get("evaluator_validity") is not True
            or accepted_outcome.get("task_score") != 0.0
            or not isinstance(accepted_identity, dict)
            or accepted_identity.get("task_id") != projection.get("task_id")
            or not isinstance(accepted_runtime, dict)
            or accepted_runtime.get("model_revision") != projection.get("model_revision")
            or accepted_runtime.get("sira_commit") != projection.get("sira_commit")
            or public_usage != expected_usage
        ):
            raise RegressionError("accepted V4 comparison oracle is inconsistent")
        interpreter = Path(os.path.realpath(sys.executable))
        if file_sha256(archive) != ARCHIVE_SHA256 or file_sha256(disposition) != DISPOSITION_SHA256:
            raise RegressionError("retained V4 source changed during reconstruction")
        receipt: dict[str, object] = {
            "schema_version": "0.1.0",
            "receipt_id": args.receipt_id,
            "source_plan_id": "PLAN-EXP0001-PILOT-V4",
            "source_run_id": PRIOR_RUN_ID,
            "source_archive_sha256": ARCHIVE_SHA256,
            "source_public_disposition_sha256": DISPOSITION_SHA256,
            "finalizer_source_sha256": args.finalizer_source_sha256,
            "dataset_sha256": DATASET_SHA256,
            "dataset_bytes": DATASET_BYTES,
            "evaluator_closure": evaluator_closure,
            "interpreter": {
                "implementation": sys.implementation.name,
                "version": sys.version.split()[0],
                "executable_name": interpreter.name,
                "executable_sha256": file_sha256(interpreter),
            },
            "selected_raw_members": selected_manifest,
            "selected_raw_members_sha256": canonical_sha256(selected_manifest),
            "semantic_projection": projection,
            "semantic_projection_sha256": canonical_sha256(projection),
            "deterministic_repeat_projection_sha256": canonical_sha256(repeated_projection),
            "deterministic_distinct_finalization_roots": repeat_files,
            "accepted_scientific_and_evaluator_fields_equal": True,
            "network_disabled": True,
            "additional_model_requests": 0,
            "additional_browser_actions": 0,
            "source_raw_mutated": False,
            "source_archive_rehashed_after": True,
            "source_public_disposition_rehashed_after": True,
            "prior_attempt_excluded_from_v5_campaign": True,
            "prior_attempt_excluded_from_v7_campaign": True,
            "private_source_path_retained": False,
        }
    _write_exclusive(args.output.resolve(strict=False), receipt)
    return receipt


def main() -> int:
    result = run(_parser().parse_args())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
