#!/usr/bin/env python3
"""Qualify one explicitly selected T09 downstream-finalizer runtime.

This is an offline, prelaunch control.  It binds the selected clean package, the
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

from giclab.harness.t09_candidate_inputs import (
    CandidateSourceSnapshot,
    reject_candidate_source,
    validate_candidate_package,
)
from giclab.harness.t09_provider_contracts import (
    T09ProviderContract,
    T09ProviderContractError,
    load_provider_profile,
    provider_contract,
    provider_contract_for_plan_id,
)
from giclab.harness.t09_qualification_fixture import (
    DATASET_PATH,
    EVALUATOR_ROOT,
    DeterministicQualificationArchive,
    validate_fixture_regression_receipt,
)

MAX_DEPENDENCY_TREE_ENTRIES = 100_000
MAX_DEPENDENCY_TREE_BYTES = 1_073_741_824


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


def _interpreter_launcher_identity(path: Path) -> dict[str, object]:
    """Bind a venv launcher separately from its resolved executable target."""

    if not path.is_absolute():
        raise LocalQualificationError("local finalizer interpreter must be absolute")
    launcher = Path(os.path.abspath(path))
    launcher_metadata = launcher.lstat()
    if launcher_metadata.st_uid != os.getuid() or launcher_metadata.st_nlink != 1:
        raise LocalQualificationError("local finalizer interpreter launcher metadata is unsafe")
    if stat.S_ISLNK(launcher_metadata.st_mode):
        launcher_type = "symlink"
        link_target: str | None = os.readlink(launcher)
        if not link_target or len(os.fsencode(link_target)) > 4_096 or "\0" in link_target:
            raise LocalQualificationError("local finalizer interpreter link target is unsafe")
    elif stat.S_ISREG(launcher_metadata.st_mode):
        launcher_type = "regular"
        link_target = None
        if launcher_metadata.st_mode & 0o022:
            raise LocalQualificationError("local finalizer interpreter launcher is writable")
    else:
        raise LocalQualificationError("local finalizer interpreter launcher is unsafe")
    resolved_target = launcher.resolve(strict=True)
    target_metadata = resolved_target.stat(follow_symlinks=False)
    if (
        resolved_target.is_symlink()
        or not stat.S_ISREG(target_metadata.st_mode)
        or target_metadata.st_uid != os.getuid()
        or target_metadata.st_nlink != 1
        or target_metadata.st_mode & 0o022
    ):
        raise LocalQualificationError("local finalizer interpreter target metadata is unsafe")
    return {
        "interpreter": launcher.as_posix(),
        "interpreter_sha256": file_sha256(launcher),
        "interpreter_launcher_type": launcher_type,
        "interpreter_launcher_mode": f"{stat.S_IMODE(launcher_metadata.st_mode):04o}",
        "interpreter_launcher_link_target": link_target,
        "interpreter_resolved_target": resolved_target.as_posix(),
        "interpreter_resolved_target_sha256": file_sha256(resolved_target),
    }


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


def _dependency_tree_inventory(root: Path, *, label: str) -> dict[str, object]:
    """Hash every dependency directory and regular file without following links."""

    resolved = root.resolve(strict=True)
    root_metadata = resolved.stat(follow_symlinks=False)
    if (
        resolved.is_symlink()
        or not stat.S_ISDIR(root_metadata.st_mode)
        or root_metadata.st_uid != os.getuid()
        or root_metadata.st_mode & 0o022
    ):
        raise LocalQualificationError(f"{label} root metadata is unsafe")
    entries: list[dict[str, object]] = []
    total_regular_bytes = 0
    for current, raw_directories, raw_files in os.walk(
        resolved,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current)
        raw_directories.sort()
        raw_files.sort()
        retained_directories: list[str] = []
        for name in [*raw_directories, *raw_files]:
            path = current_path / name
            metadata = path.lstat()
            relative = path.relative_to(resolved).as_posix()
            record: dict[str, object] = {
                "path": relative,
                "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
            }
            if stat.S_ISDIR(metadata.st_mode):
                if metadata.st_mode & 0o022:
                    raise LocalQualificationError(f"{label} directory is writable")
                record["type"] = "directory"
                retained_directories.append(name)
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1 or metadata.st_mode & 0o022:
                    raise LocalQualificationError(f"{label} file metadata is unsafe")
                record.update(
                    {
                        "type": "file",
                        "bytes": metadata.st_size,
                        "sha256": file_sha256(path),
                    }
                )
                total_regular_bytes += metadata.st_size
            else:
                raise LocalQualificationError(f"{label} contains a link or special file")
            entries.append(record)
            if (
                len(entries) > MAX_DEPENDENCY_TREE_ENTRIES
                or total_regular_bytes > MAX_DEPENDENCY_TREE_BYTES
            ):
                raise LocalQualificationError(f"{label} exceeds its manifest bound")
        raw_directories[:] = retained_directories
    return {
        "root_mode": f"{stat.S_IMODE(root_metadata.st_mode):04o}",
        "entries": entries,
        "entry_count": len(entries),
        "total_regular_bytes": total_regular_bytes,
        "entries_sha256": canonical_sha256(entries),
    }


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


def _selected_contract(args: argparse.Namespace) -> T09ProviderContract:
    """Resolve exactly one required selector without a current/latest fallback."""

    version = getattr(args, "provider_contract", None)
    plan_id = getattr(args, "plan_id", None)
    if (isinstance(version, str)) == (isinstance(plan_id, str)):
        raise LocalQualificationError(
            "exactly one provider-contract version or plan identity is required"
        )
    try:
        if isinstance(version, str):
            return provider_contract(version)
        assert isinstance(plan_id, str)
        return provider_contract_for_plan_id(plan_id)
    except T09ProviderContractError as exc:
        raise LocalQualificationError("local finalizer contract selector is unsupported") from exc


def _validate_selected_package(
    repository: Path,
    contract: T09ProviderContract,
    execution_path: Path,
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    """Bind the qualifier to the selected contract's exact package paths and plan."""

    if contract.execution_contract_path is None or contract.command_manifest_path is None:
        raise LocalQualificationError("selected provider contract has no qualification package")
    expected_execution = (repository / contract.execution_contract_path).resolve(strict=True)
    if execution_path != expected_execution:
        raise LocalQualificationError("execution contract path crosses provider versions")
    execution = _object(execution_path, label="execution contract")
    if execution.get("plan_id") != contract.plan_id:
        raise LocalQualificationError("local finalizer execution contract drifted")
    identities = execution.get("identities")
    if not isinstance(identities, dict) or any(
        identities.get(field) != expected
        for field, expected in {
            "host_run_id": contract.host_run_id,
            "evaluator_run_ids": list(contract.evaluator_run_ids),
            "runtime_qualification_id": contract.active_image_qualification_id,
            "local_finalizer_qualification_id": contract.local_finalizer_qualification_id,
            "frozen_run_manifest_id": contract.frozen_run_manifest_id,
            "evidence_archive_id": contract.evidence_archive_id,
            "evidence_stage_id": contract.evidence_stage_id,
        }.items()
    ):
        raise LocalQualificationError("execution contract pilot identities drifted")
    profile = load_provider_profile(repository, contract)
    bindings = execution.get("contract_bindings")
    plan_binding = bindings.get("plan") if isinstance(bindings, dict) else None
    if not isinstance(plan_binding, dict) or plan_binding != {
        "path": contract.provider_profile_path,
        "sha256": contract.expected_provider_profile_sha256,
        "size_bytes": contract.expected_provider_profile_bytes,
    }:
        raise LocalQualificationError("execution contract plan binding drifted")
    command_path = (repository / contract.command_manifest_path).resolve(strict=True)
    commands = _object(command_path, label="command manifest set")
    if (
        commands.get("plan_id") != contract.plan_id
        or commands.get("plan_path") != contract.provider_profile_path
        or commands.get("plan_sha256") != contract.expected_provider_profile_sha256
        or commands.get("plan_size_bytes") != contract.expected_provider_profile_bytes
        or commands.get("execution_contract_path") != contract.execution_contract_path
        or commands.get("execution_contract_sha256") != file_sha256(execution_path)
    ):
        raise LocalQualificationError("command manifest package binding drifted")
    return execution, command_path, dict(profile)


def _selected_identity_projection(
    contract: T09ProviderContract,
    *,
    command_path: Path,
    provider_profile: dict[str, Any],
) -> dict[str, object]:
    """Render only identities owned by the explicitly selected contract."""

    return {
        "qualification_id": contract.local_finalizer_qualification_id,
        "plan_id": contract.plan_id,
        "provider_contract_version": contract.version,
        "host_run_id": contract.host_run_id,
        "attempt_order": list(contract.attempt_order),
        "evaluator_run_ids": list(contract.evaluator_run_ids),
        "runtime_qualification_id": contract.active_image_qualification_id,
        "frozen_run_manifest_id": contract.frozen_run_manifest_id,
        "execution_contract_path": contract.execution_contract_path,
        "command_manifest_path": contract.command_manifest_path,
        "command_manifest_sha256": file_sha256(command_path),
        "provider_profile_path": contract.provider_profile_path,
        "provider_profile_sha256": contract.expected_provider_profile_sha256,
        "provider_profile_semantic_sha256": canonical_sha256(provider_profile),
    }


def qualify(
    args: argparse.Namespace,
    *,
    source_inputs: CandidateSourceSnapshot | None = None,
    fixture_binding: DeterministicQualificationArchive | None = None,
) -> dict[str, object]:
    repository = args.repository.resolve(strict=True)
    if source_inputs is None:
        # No CLI argument, environment variable or receipt selects candidate mode.
        reject_candidate_source(repository)
        if fixture_binding is not None:
            raise LocalQualificationError("archive fixture requires explicit candidate sources")
    else:
        validate_candidate_package(source_inputs, repository)
        if (
            source_inputs.package_identity(repository)[0] != args.package_commit
            or fixture_binding is None
            or fixture_binding.document() != source_inputs.document()["qualification_fixture"]
        ):
            raise LocalQualificationError("offline qualifier candidate/archive binding drifted")
        fixture_binding.validate(repository)
    contract = _selected_contract(args)
    interpreter_identity = _interpreter_launcher_identity(args.interpreter)
    interpreter = Path(str(interpreter_identity["interpreter"]))
    if (
        not Path(sys.executable).is_absolute()
        or Path(os.path.abspath(sys.executable)) != interpreter
    ):
        raise LocalQualificationError("qualification did not use the declared absolute Python")
    if sys.version_info[:3] != (3, 11, 14):
        raise LocalQualificationError("local finalizer Python must be exactly 3.11.14")
    if source_inputs is None:
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
    execution_contract, command_path, provider_profile = _validate_selected_package(
        repository,
        contract,
        execution_path,
    )
    base_site_packages, base_packages = _local_base_packages(execution_contract)
    base_dependency_tree = _dependency_tree_inventory(
        base_site_packages,
        label="local finalizer base dependency tree",
    )
    evaluator_path = args.evaluator_contract.resolve(strict=True)
    evaluator = _object(evaluator_path, label="evaluator contract")
    evaluator_identity = evaluator.get("identity")
    evaluator_files_raw = (
        evaluator_identity.get("files") if isinstance(evaluator_identity, dict) else None
    )
    if fixture_binding is not None:
        if args.evaluator_root.resolve(strict=True) != repository / EVALUATOR_ROOT:
            raise LocalQualificationError("offline evaluator path differs from its fixture")
        evaluator_files_raw = fixture_binding.evaluator_files()
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
    evaluator_dependency_tree = _dependency_tree_inventory(
        args.dependency_site_packages,
        label="local evaluator dependency tree",
    )
    dataset = args.dataset.resolve(strict=True)
    dataset_bytes = 1_177_174
    dataset_sha256 = "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
    if fixture_binding is not None:
        if dataset != repository / DATASET_PATH:
            raise LocalQualificationError("offline dataset path differs from its fixture")
        member = next(item for item in fixture_binding.sources if item.path == DATASET_PATH)
        dataset_bytes, dataset_sha256 = member.bytes, member.sha256
    if dataset.stat().st_size != dataset_bytes or file_sha256(dataset) != dataset_sha256:
        raise LocalQualificationError("local finalizer dataset identity drifted")
    regression_path = args.real_evidence_regression.resolve(strict=True)
    regression = _object(regression_path, label="real-evidence regression")
    if fixture_binding is not None:
        assert source_inputs is not None
        validate_fixture_regression_receipt(repository, fixture_binding, regression)
        if regression.get("finalizer_source_sha256") != source_inputs.source_sha256(
            repository, "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
        ) or regression.get("regression_source_sha256") != source_inputs.source_sha256(
            repository, "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py"
        ):
            raise LocalQualificationError("offline regression used another candidate source")
    elif (
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
        **_selected_identity_projection(
            contract,
            command_path=command_path,
            provider_profile=provider_profile,
        ),
        "package_commit": args.package_commit,
        **interpreter_identity,
        "python_version": "3.11.14",
        "execution_contract_sha256": file_sha256(execution_path),
        "interpreter_site_packages": base_site_packages.as_posix(),
        "interpreter_dependency_manifest": base_packages,
        "interpreter_dependency_manifest_sha256": canonical_sha256(base_packages),
        "interpreter_dependency_tree": base_dependency_tree,
        "interpreter_dependency_tree_sha256": canonical_sha256(base_dependency_tree),
        "dependency_site_packages": args.dependency_site_packages.resolve(strict=True).as_posix(),
        "dependency_package_manifest": expected_packages,
        "dependency_package_manifest_sha256": canonical_sha256(expected_packages),
        "dependency_tree": evaluator_dependency_tree,
        "dependency_tree_sha256": canonical_sha256(evaluator_dependency_tree),
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
    if source_inputs is not None:
        assert fixture_binding is not None
        # These inputs qualify only the offline instrumentation test. The
        # unchanged experiment package remains a template, not new V16 evidence.
        receipt["offline_candidate_inputs"] = {
            "candidate_binding_sha256": source_inputs.digest,
            "template_contract": contract.version,
            "qualification_fixture": fixture_binding.document(),
            "classification": "non-scientific-no-network-non-live",
            "historical_replay": False,
            "live_qualification": False,
            "template_dataset_sha256": (
                "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
            ),
        }
        validate_candidate_package(source_inputs, repository)
        fixture_binding.validate(repository)
    _write_exclusive(args.output.resolve(strict=False), receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--provider-contract")
    selector.add_argument("--plan-id")
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
