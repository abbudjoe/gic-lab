#!/usr/bin/env python3
"""Qualify one absolute local Retry 3 downstream-finalizer runtime.

This is an offline, prelaunch control.  It binds the current clean package, the
absolute Python binary, the complete pinned evaluator overlay, and the accepted
real-evidence regression.  It has no empirical, provider, budget, selection, or
checkpoint authority.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import socket
import stat
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Any


class LocalQualificationError(RuntimeError):
    """The prelaunch local finalizer qualification failed closed."""


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


def _object(path: Path, *, label: str) -> dict[str, Any]:
    metadata = path.stat(follow_symlinks=False)
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise LocalQualificationError(f"{label} metadata is unsafe")
    try:
        value: object = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise LocalQualificationError(f"{label} is malformed") from exc
    if not isinstance(value, dict):
        raise LocalQualificationError(f"{label} is not an object")
    return value


def _expected_packages(evaluator_contract: dict[str, Any]) -> list[str]:
    materialization = evaluator_contract.get("materialization")
    if not isinstance(materialization, dict):
        raise LocalQualificationError("evaluator materialization contract is unavailable")
    inventory = materialization.get("dependency_license_inventory")
    if not isinstance(inventory, list):
        raise LocalQualificationError("evaluator dependency inventory is unavailable")
    result: list[str] = []
    for record in inventory:
        if not isinstance(record, str) or "==" not in record or "|" not in record:
            raise LocalQualificationError("evaluator dependency record is malformed")
        package, remainder = record.split("==", 1)
        version, _license = remainder.split("|", 1)
        normalized = re.sub(r"[-_.]+", "-", package).lower()
        result.append(f"{normalized}=={version}")
    if len(result) != 51:
        raise LocalQualificationError("evaluator dependency inventory count drifted")
    return sorted(result)


def _realized_packages(site_packages: Path) -> list[str]:
    site = site_packages.resolve(strict=True)
    if not site.is_dir() or site.is_symlink():
        raise LocalQualificationError("local evaluator site-packages is unsafe")
    result: list[str] = []
    for distribution in importlib.metadata.distributions(path=[str(site)]):
        name = distribution.metadata["Name"]
        version = distribution.version
        if not isinstance(name, str) or not isinstance(version, str):
            raise LocalQualificationError("local evaluator distribution metadata is malformed")
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        result.append(f"{normalized}=={version}")
    normalized_result = sorted(result)
    if len(normalized_result) != len(set(normalized_result)):
        raise LocalQualificationError("local evaluator has duplicate package identities")
    return normalized_result


def _local_base_packages(execution_contract: dict[str, Any]) -> tuple[Path, list[str]]:
    runtime = execution_contract.get("runtime")
    expected = runtime.get("local_finalizer_base_packages") if isinstance(runtime, dict) else None
    site_value = sysconfig.get_paths().get("purelib")
    if (
        not isinstance(expected, list)
        or not expected
        or not all(isinstance(item, str) for item in expected)
        or expected != sorted(expected)
        or len(expected) != len(set(expected))
        or not isinstance(site_value, str)
    ):
        raise LocalQualificationError("local finalizer base dependency contract is malformed")
    site_packages = Path(site_value).resolve(strict=True)
    realized = _realized_packages(site_packages)
    if realized != expected:
        raise LocalQualificationError("local finalizer base package closure drifted")
    return site_packages, realized


def _write_exclusive(path: Path, value: object) -> None:
    encoded = (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
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
                raise LocalQualificationError("local qualification write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _disable_network() -> None:
    def denied(*_args: object, **_kwargs: object) -> object:
        raise LocalQualificationError("network is disabled during local qualification")

    socket.socket = denied  # type: ignore[misc,assignment]
    socket.create_connection = denied  # type: ignore[assignment]


def qualify(args: argparse.Namespace) -> dict[str, object]:
    repository = args.repository.resolve(strict=True)
    interpreter = args.interpreter.resolve(strict=True)
    if Path(sys.executable).resolve(strict=True) != interpreter:
        raise LocalQualificationError("qualification did not use the declared absolute Python")
    if sys.version_info[:3] != (3, 11, 14):
        raise LocalQualificationError("local finalizer Python must be exactly 3.11.14")
    head = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(repository), "status", "--porcelain"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout
    if head != args.package_commit or dirty:
        raise LocalQualificationError("local qualification requires the exact clean package")
    _disable_network()
    execution_path = args.execution_contract.resolve(strict=True)
    execution_contract = _object(execution_path, label="execution contract")
    if execution_contract.get("plan_id") != "PLAN-EXP0001-PILOT-V5":
        raise LocalQualificationError("local finalizer execution contract drifted")
    base_site_packages, base_packages = _local_base_packages(execution_contract)
    evaluator_path = args.evaluator_contract.resolve(strict=True)
    evaluator = _object(evaluator_path, label="evaluator contract")
    evaluator_identity = evaluator.get("identity")
    evaluator_files_raw = (
        evaluator_identity.get("files") if isinstance(evaluator_identity, dict) else None
    )
    if not isinstance(evaluator_files_raw, list):
        raise LocalQualificationError("evaluator source inventory is unavailable")
    evaluator_root = args.evaluator_root.resolve(strict=True)
    evaluator_files: list[dict[str, str]] = []
    for raw in evaluator_files_raw:
        if not isinstance(raw, dict):
            raise LocalQualificationError("evaluator source binding is malformed")
        source_path = raw.get("path")
        expected_sha256 = raw.get("sha256")
        prefix = "evaluation/fanout/"
        if (
            not isinstance(source_path, str)
            or not source_path.startswith(prefix)
            or not isinstance(expected_sha256, str)
        ):
            raise LocalQualificationError("evaluator source identity is malformed")
        path = (evaluator_root / source_path.removeprefix(prefix)).resolve(strict=True)
        try:
            path.relative_to(evaluator_root)
        except ValueError:
            raise LocalQualificationError("evaluator source escaped its root") from None
        if path.is_symlink() or file_sha256(path) != expected_sha256:
            raise LocalQualificationError("local evaluator source bytes drifted")
        evaluator_files.append({"path": source_path, "sha256": expected_sha256})
    expected_packages = _expected_packages(evaluator)
    realized_packages = _realized_packages(args.dependency_site_packages)
    if realized_packages != expected_packages:
        raise LocalQualificationError("local evaluator package closure drifted")
    dataset = args.dataset.resolve(strict=True)
    if (
        dataset.stat().st_size != 1_177_174
        or file_sha256(dataset)
        != "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
    ):
        raise LocalQualificationError("local finalizer dataset identity drifted")
    regression_path = args.real_evidence_regression.resolve(strict=True)
    regression = _object(regression_path, label="real-evidence regression")
    if (
        regression.get("accepted_scientific_and_evaluator_fields_equal") is not True
        or regression.get("network_disabled") is not True
        or regression.get("additional_model_requests") != 0
        or regression.get("additional_browser_actions") != 0
        or regression.get("dataset_sha256") != file_sha256(dataset)
        or regression.get("evaluator_closure", {}).get("evaluator_contract_sha256")
        != file_sha256(evaluator_path)
        or regression.get("evaluator_closure", {}).get("dependency_package_manifest_sha256")
        != canonical_sha256(expected_packages)
    ):
        raise LocalQualificationError("real-evidence regression closure drifted")
    sources = {
        "finalizer": args.finalizer_source.resolve(strict=True),
        "projection": args.finalizer_projection_source.resolve(strict=True),
        "qualification": Path(__file__).resolve(strict=True),
    }
    receipt: dict[str, object] = {
        "schema_version": "0.1.0",
        "qualification_id": "QUAL-T09-PILOT-V5-LOCAL-FINALIZER-0001",
        "plan_id": "PLAN-EXP0001-PILOT-V5",
        "package_commit": args.package_commit,
        "interpreter": interpreter.as_posix(),
        "interpreter_sha256": file_sha256(interpreter),
        "python_version": "3.11.14",
        "execution_contract_sha256": file_sha256(execution_path),
        "interpreter_site_packages": base_site_packages.as_posix(),
        "interpreter_dependency_manifest": base_packages,
        "interpreter_dependency_manifest_sha256": canonical_sha256(base_packages),
        "dependency_site_packages": args.dependency_site_packages.resolve(strict=True).as_posix(),
        "dependency_package_manifest": expected_packages,
        "dependency_package_manifest_sha256": canonical_sha256(expected_packages),
        "evaluator_contract_sha256": file_sha256(evaluator_path),
        "evaluator_root": evaluator_root.as_posix(),
        "evaluator_files": evaluator_files,
        "evaluator_files_sha256": canonical_sha256(evaluator_files),
        "dataset": dataset.as_posix(),
        "dataset_sha256": file_sha256(dataset),
        "real_evidence_regression_sha256": file_sha256(regression_path),
        "real_evidence_semantic_projection_sha256": regression.get("semantic_projection_sha256"),
        "real_evidence_regression_passed": True,
        "source_sha256s": {name: file_sha256(path) for name, path in sources.items()},
        "network_policy": "socket-construction-denied",
        "model_requests": 0,
        "browser_actions": 0,
    }
    _write_exclusive(args.output.resolve(strict=False), receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--package-commit", required=True)
    parser.add_argument("--interpreter", type=Path, required=True)
    parser.add_argument("--dependency-site-packages", type=Path, required=True)
    parser.add_argument("--execution-contract", type=Path, required=True)
    parser.add_argument("--evaluator-contract", type=Path, required=True)
    parser.add_argument("--evaluator-root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--real-evidence-regression", type=Path, required=True)
    parser.add_argument("--finalizer-source", type=Path, required=True)
    parser.add_argument("--finalizer-projection-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    print(json.dumps(qualify(_parser().parse_args()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
