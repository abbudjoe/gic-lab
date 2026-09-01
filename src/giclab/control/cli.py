"""Stable, network-disabled CLI for the agent/control foundation."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

import yaml

from giclab.control.agent_check import run_agent_check
from giclab.control.anti_shadow_lint import validate_anti_shadow_lint
from giclab.control.composition import compose_control_plane
from giclab.control.incidents import validate_incidents
from giclab.control.live_conformance import run_live_effect_conformance
from giclab.control.proofs import (
    BOUND_GOAL_RECORD,
    REPOSITORY_SLUG,
    ControlProofReference,
    generate_control_binding_document,
    generate_source_binding_receipt,
    validate_current_control_receipt_set,
)
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.scenarios import HAPPY_PATH, REQUIRED_FAILURE_SCENARIOS
from giclab.control.shadow import run_required_shadow_matrix, run_shadow_scenario
from giclab.control.state_capsule import generate_state_capsule
from giclab.control.target import (
    GOAL_RECORD,
    SelectedRuntimeTarget,
    resolve_selected_runtime_target,
)
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness import t09_provider_contracts as provider_contracts


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()


def _semantic_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write_receipts(output: Path, receipts: Mapping[str, object]) -> list[dict[str, object]]:
    output.mkdir(parents=True, exist_ok=True)
    identities: list[dict[str, object]] = []
    for name, receipt in receipts.items():
        path = output / f"{name}.json"
        encoded = _json_bytes(receipt)
        path.write_bytes(encoded)
        identities.append(
            {
                "scenario": name,
                "path": path.name,
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    return identities


def _write_json(approved_root: Path, path: Path, document: object) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _json_bytes(document)
    path.write_bytes(encoded)
    semantic = document.get("semantic_sha256") if isinstance(document, dict) else None
    return {
        "path": path.relative_to(approved_root).as_posix(),
        "bytes": len(encoded),
        "file_sha256": hashlib.sha256(encoded).hexdigest(),
        "semantic_sha256": semantic,
    }


def _write_bytes(approved_root: Path, path: Path, encoded: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return {
        "path": path.relative_to(approved_root).as_posix(),
        "bytes": len(encoded),
        "file_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _clean_git_identity(repository: Path) -> tuple[str, str]:
    status = subprocess.run(
        ["git", "-C", str(repository), "status", "--porcelain=v1", "--untracked-files=all"],
        capture_output=True,
        check=True,
        text=True,
    )
    dirty_paths = []
    for line in status.stdout.splitlines():
        relative = line[3:]
        if " -> " in relative:
            relative = relative.split(" -> ", maxsplit=1)[1]
        if not relative.startswith("control/receipts/"):
            dirty_paths.append(relative)
    if dirty_paths:
        raise ValueError(
            "receipt refresh requires an immutable implementation ancestor; "
            "non-receipt paths are dirty: " + ", ".join(dirty_paths)
        )
    identity = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD", "HEAD^{tree}"],
        capture_output=True,
        check=True,
        text=True,
    )
    commit, tree = identity.stdout.splitlines()
    return commit, tree


def _target_from_args(args: argparse.Namespace) -> SelectedRuntimeTarget:
    explicit = getattr(args, "provider_contract", None)
    return resolve_selected_runtime_target(
        args.repository,
        explicit_provider_contract=explicit,
    )


def _bootstrap_capsule(
    repository: Path,
    *,
    target: SelectedRuntimeTarget,
    registry_complete: bool,
    composition_valid: bool,
    lint_valid: bool,
) -> dict[str, object]:
    return generate_state_capsule(
        repository,
        registry_complete=registry_complete,
        composition_valid=composition_valid,
        version_lint_valid=lint_valid,
        shadow_happy_path=False,
        failure_matrix_valid=False,
        target=target,
        deterministic=True,
    )


def _verified_capsule(
    repository: Path,
    *,
    target: SelectedRuntimeTarget,
    deterministic: bool,
) -> dict[str, object]:
    lint = validate_active_version_dispatch(repository)
    registry = validate_registry_completeness(repository)
    composition = compose_control_plane(
        repository,
        contract=target.selected_contract,
        registry_receipt=registry,
        version_lint_receipt=lint,
    )
    bootstrap = _bootstrap_capsule(
        repository,
        target=target,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        lint_valid=lint.get("complete") is True,
    )
    shadows = run_required_shadow_matrix(
        repository,
        contract=target.selected_contract,
        state_capsule=bootstrap,
        registry_receipt=registry,
        version_lint_receipt=lint,
        composition_receipt=composition,
    )
    shadow_valid = all(receipt.get("scenario_valid") is True for receipt in shadows.values())
    anti_shadow = validate_anti_shadow_lint(repository)
    live_conformance = run_live_effect_conformance(repository)
    return generate_state_capsule(
        repository,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        version_lint_valid=lint.get("complete") is True,
        shadow_happy_path=(
            shadows["happy-path"].get("terminal_state") == "category3-shadow-complete-clean"
        ),
        failure_matrix_valid=shadow_valid,
        anti_shadow_lint_valid=anti_shadow.get("complete") is True,
        live_effect_conformance_valid=live_conformance.get("complete") is True,
        target=target,
        deterministic=deterministic,
    )


def _command_state_capsule(args: argparse.Namespace) -> tuple[object, bool]:
    target = _target_from_args(args)
    capsule = _verified_capsule(
        args.repository,
        target=target,
        deterministic=args.deterministic,
    )
    return capsule, True


def _command_registry(args: argparse.Namespace) -> tuple[object, bool]:
    receipt = validate_registry_completeness(args.repository)
    return receipt, receipt.get("complete") is True


def _command_version_lint(args: argparse.Namespace) -> tuple[object, bool]:
    receipt = validate_active_version_dispatch(args.repository)
    return receipt, receipt.get("complete") is True


def _command_compose(args: argparse.Namespace) -> tuple[object, bool]:
    target = _target_from_args(args)
    lint = validate_active_version_dispatch(args.repository)
    registry = validate_registry_completeness(args.repository)
    contracts = (
        tuple(provider_contracts.PROVIDER_CONTRACTS.values())
        if args.all_registered
        else (target.selected_contract,)
    )
    receipts = {
        contract.version: compose_control_plane(
            args.repository,
            contract=contract,
            registry_receipt=registry,
            version_lint_receipt=lint,
        )
        for contract in contracts
    }
    complete = all(receipt.get("static_composition_valid") is True for receipt in receipts.values())
    aggregate: dict[str, object] = {
        "schema_version": "2.0.0",
        "selected_runtime_target": target.to_document(),
        "scope": "all-registered" if args.all_registered else "selected-runtime-target",
        "contract_count": len(receipts),
        "receipts": receipts,
        "complete": complete,
    }
    aggregate["semantic_sha256"] = _semantic_sha256(aggregate)
    return aggregate, complete


def _command_shadow(args: argparse.Namespace) -> tuple[object, bool]:
    target = _target_from_args(args)
    contract = target.selected_contract
    lint = validate_active_version_dispatch(args.repository)
    registry = validate_registry_completeness(args.repository)
    composition = compose_control_plane(
        args.repository,
        contract=contract,
        registry_receipt=registry,
        version_lint_receipt=lint,
    )
    bootstrap = _bootstrap_capsule(
        args.repository,
        target=target,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        lint_valid=lint.get("complete") is True,
    )
    if args.all_required:
        receipts = run_required_shadow_matrix(
            args.repository,
            contract=contract,
            state_capsule=bootstrap,
            registry_receipt=registry,
            version_lint_receipt=lint,
            composition_receipt=composition,
            fixed_tick=args.fixed_tick,
        )
    else:
        receipt = run_shadow_scenario(
            args.repository,
            contract=contract,
            scenario=args.scenario,
            state_capsule=bootstrap,
            fixed_tick=args.fixed_tick,
        )
        receipts = {args.scenario: receipt}
    written = _write_receipts(args.output, receipts) if args.output is not None else []
    complete = all(receipt.get("scenario_valid") is True for receipt in receipts.values())
    aggregate: dict[str, object] = {
        "schema_version": "1.0.0",
        "selected_runtime_target": target.to_document(),
        "provider_contract_version": contract.version,
        "scenario_count": len(receipts),
        "receipts": receipts,
        "written_receipts": written,
        "complete": complete,
    }
    aggregate["semantic_sha256"] = _semantic_sha256(aggregate)
    return aggregate, complete


def _command_incidents(args: argparse.Namespace) -> tuple[object, bool]:
    receipt = validate_incidents(args.repository, execute_regressions=True)
    return receipt, receipt.get("complete") is True


def _command_agent_check(args: argparse.Namespace) -> tuple[object, bool]:
    target = _target_from_args(args)
    receipt = run_agent_check(
        args.repository,
        target=target,
        execute_incident_regressions=True,
    )
    return receipt, receipt.get("complete") is True


def _receipt_reference(
    output: Path,
    *,
    target: SelectedRuntimeTarget,
    binding_sha256: str,
    commit: str,
    tree: str,
) -> ControlProofReference:
    target_document = target.to_document()
    target_semantic = target_document.get("semantic_sha256")
    if not isinstance(target_semantic, str):  # pragma: no cover - local constructor invariant
        raise TypeError("selected target lacks a semantic identity")
    return ControlProofReference(
        approved_root=output,
        binding_path=output / "t09-control-receipt-bindings.json",
        expected_file_sha256=binding_sha256,
        expected_control_commit=commit,
        expected_control_tree=tree,
        expected_repository_slug=REPOSITORY_SLUG,
        expected_provider_contract_version=target.selected_contract.version,
        expected_plan_id=target.selected_plan_id,
        expected_command_package_sha256=target.selected_command_package_sha256,
        expected_target_source=target.source,
        expected_goal_record_sha256=target.goal_record_sha256,
        expected_target_semantic_sha256=target_semantic,
    )


def _generate_receipt_tree(
    repository: Path,
    output: Path,
    *,
    target: SelectedRuntimeTarget,
    commit: str,
    tree: str,
) -> dict[str, object]:
    """Generate and validate one complete tree beneath an already private staging root."""

    contract = target.selected_contract
    lint = validate_active_version_dispatch(repository)
    registry = validate_registry_completeness(repository)
    composition = compose_control_plane(
        repository,
        contract=contract,
        registry_receipt=registry,
        version_lint_receipt=lint,
    )
    bootstrap_capsule = _bootstrap_capsule(
        repository,
        target=target,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        lint_valid=lint.get("complete") is True,
    )
    shadows = run_required_shadow_matrix(
        repository,
        contract=contract,
        state_capsule=bootstrap_capsule,
        registry_receipt=registry,
        version_lint_receipt=lint,
        composition_receipt=composition,
    )
    shadow_complete = all(receipt.get("scenario_valid") is True for receipt in shadows.values())
    anti_shadow = validate_anti_shadow_lint(repository)
    live_conformance = run_live_effect_conformance(repository)
    capsule = generate_state_capsule(
        repository,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        version_lint_valid=lint.get("complete") is True,
        shadow_happy_path=(
            shadows[HAPPY_PATH].get("terminal_state") == "category3-shadow-complete-clean"
        ),
        failure_matrix_valid=shadow_complete,
        anti_shadow_lint_valid=anti_shadow.get("complete") is True,
        live_effect_conformance_valid=live_conformance.get("complete") is True,
        target=target,
        deterministic=True,
    )
    incidents = validate_incidents(repository, execute_regressions=True)
    source_binding = generate_source_binding_receipt(
        repository,
        source_commit=commit,
        source_tree=tree,
    )
    agent_check = run_agent_check(
        repository,
        target=target,
        execute_incident_regressions=True,
        anti_shadow_lint_receipt=anti_shadow,
        live_effect_conformance_receipt=live_conformance,
    )

    composition_name = f"{contract.version.lower()}-composition.json"
    goal_bytes = (repository / GOAL_RECORD).read_bytes()
    if hashlib.sha256(goal_bytes).hexdigest() != target.goal_record_sha256:
        raise ValueError("goal bytes changed after target selection")
    written = [
        _write_bytes(output, output / BOUND_GOAL_RECORD, goal_bytes),
        _write_json(output, output / "active-version-lint.json", lint),
        _write_json(output, output / "registry-completeness.json", registry),
        _write_json(output, output / composition_name, composition),
        _write_json(output, output / "state-capsule.json", capsule),
        _write_json(output, output / "incidents.json", incidents),
        _write_json(output, output / "anti-shadow-lint.json", anti_shadow),
        _write_json(
            output,
            output / "live-effect-conformance.json",
            live_conformance,
        ),
        _write_json(
            output,
            output / "t09-control-plane-source-binding.json",
            source_binding,
        ),
    ]
    shadow_root = output / "category3-shadow"
    for scenario, receipt in shadows.items():
        written.append(_write_json(output, shadow_root / f"{scenario}.json", receipt))
    written.append(_write_json(output, output / "agent-check.json", agent_check))

    command_sha = composition.get("command_package_sha256")
    if command_sha != target.selected_command_package_sha256:
        raise ValueError("composition differs from the selected command package")
    binding = generate_control_binding_document(
        repository,
        output,
        control_commit=commit,
        control_tree=tree,
        target=target,
        goal_record_snapshot=output / BOUND_GOAL_RECORD,
        registry_receipt=output / "registry-completeness.json",
        active_version_lint_receipt=output / "active-version-lint.json",
        composition_receipt=output / composition_name,
        state_capsule=output / "state-capsule.json",
        shadow_happy_path=shadow_root / f"{HAPPY_PATH}.json",
        shadow_failures={
            scenario: shadow_root / f"{scenario}.json" for scenario in REQUIRED_FAILURE_SCENARIOS
        },
        agent_check_receipt=output / "agent-check.json",
        source_binding_receipt=output / "t09-control-plane-source-binding.json",
        incident_receipt=output / "incidents.json",
        anti_shadow_lint_receipt=output / "anti-shadow-lint.json",
        live_effect_conformance_receipt=output / "live-effect-conformance.json",
    )
    binding_identity = _write_json(
        output,
        output / "t09-control-receipt-bindings.json",
        binding,
    )
    binding_sha = binding_identity["file_sha256"]
    assert isinstance(binding_sha, str)
    validate_current_control_receipt_set(
        repository,
        contract,
        _receipt_reference(
            output,
            target=target,
            binding_sha256=binding_sha,
            commit=commit,
            tree=tree,
        ),
    )
    written.append(binding_identity)
    complete = all(
        (
            lint.get("complete") is True,
            registry.get("complete") is True,
            composition.get("static_composition_valid") is True,
            shadow_complete,
            incidents.get("complete") is True,
            agent_check.get("complete") is True,
            anti_shadow.get("complete") is True,
            live_conformance.get("complete") is True,
        )
    )
    result: dict[str, object] = {
        "schema_version": "2.0.0",
        "control_commit": commit,
        "control_tree": tree,
        "selected_runtime_target": target.to_document(),
        "binding_file_sha256": binding_sha,
        "receipt_count": len(written),
        "receipts": written,
        "complete": complete,
    }
    result["semantic_sha256"] = _semantic_sha256(result)
    return result


def _new_receipt_output_path(
    repository: Path,
    requested: Path,
    *,
    target: SelectedRuntimeTarget,
) -> Path:
    pure = PurePosixPath(requested.as_posix())
    expected = PurePosixPath(
        f"control/receipts/packages/{target.selected_contract.version.lower()}"
    )
    if requested.is_absolute() or pure != expected or ".." in pure.parts:
        raise ValueError(
            "receipt output root must be the exact repository-relative package path "
            f"{expected.as_posix()}"
        )
    cursor = repository
    for part in pure.parts:
        cursor = cursor / part
        if not os.path.lexists(cursor):
            continue
        metadata = cursor.stat(follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("receipt output root contains a symbolic link")
        if cursor == repository / Path(*pure.parts):
            binding = cursor / "t09-control-receipt-bindings.json"
            if binding.is_file() and not binding.is_symlink():
                raise ValueError("sealed receipt output root cannot be overwritten")
            return cursor
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("receipt output root parent is not a directory")
    return repository / Path(*pure.parts)


def _ensure_output_parent(repository: Path, output: Path) -> None:
    relative_parent = output.parent.relative_to(repository)
    cursor = repository
    for part in relative_parent.parts:
        cursor = cursor / part
        if os.path.lexists(cursor):
            metadata = cursor.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("receipt output parent is not a regular directory")
        else:
            cursor.mkdir()


def _commit_path_no_replace(source: Path, destination: Path) -> None:
    """Rename one complete same-parent path without replacing a concurrent winner."""

    if source.parent != destination.parent:
        raise ValueError("atomic receipt commit requires one shared parent")
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
        rename.restype = ctypes.c_int
        result = rename(source_bytes, destination_bytes, 0x00000004)
    elif sys.platform.startswith("linux"):
        rename = libc.renameat2
        rename.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int
        result = rename(-100, source_bytes, -100, destination_bytes, 0x00000001)
    else:  # pragma: no cover - repository CI supports macOS and Linux
        raise OSError(errno.ENOTSUP, "atomic no-replace directory commit is unsupported")
    if result != 0:
        error = ctypes.get_errno()
        if error in {errno.EEXIST, errno.ENOTEMPTY}:
            raise FileExistsError(error, os.strerror(error), destination)
        raise OSError(error, os.strerror(error), destination)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sync_receipt_tree(staging: Path) -> None:
    """Durably prepare every regular file and directory before publication."""

    directories = [staging]
    for path in sorted(staging.rglob("*"), key=lambda item: item.as_posix()):
        metadata = path.stat(follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("receipt staging tree contains a symbolic link")
        if stat.S_ISDIR(metadata.st_mode):
            directories.append(path)
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("receipt staging tree contains a non-regular artifact")
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        _fsync_directory(directory)


def _recovery_path(output: Path) -> Path:
    return output.parent / f".{output.name}-unowned-partial-recovery"


def _recover_unsealed_receipt_root(output: Path) -> Path | None:
    """Atomically quarantine an exact unsealed root so normal generation can resume."""

    if not os.path.lexists(output):
        return None
    metadata = output.stat(follow_symlinks=False)
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError("receipt output root contains a symbolic link")
    binding = output / "t09-control-receipt-bindings.json"
    if stat.S_ISDIR(metadata.st_mode) and binding.is_file() and not binding.is_symlink():
        raise ValueError("sealed receipt output root cannot be overwritten")
    recovery = _recovery_path(output)
    if os.path.lexists(recovery):
        raise ValueError(f"unsealed receipt recovery path already exists: {recovery.name}")
    _commit_path_no_replace(output, recovery)
    _fsync_directory(output.parent)
    return recovery


def _receipt_trees_identical(first: Path, second: Path) -> bool:
    def identities(root: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            metadata = path.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode) or (
                not stat.S_ISDIR(metadata.st_mode) and not stat.S_ISREG(metadata.st_mode)
            ):
                return {}
            if stat.S_ISREG(metadata.st_mode):
                result[path.relative_to(root).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        return result

    first_identities = identities(first)
    return bool(first_identities) and first_identities == identities(second)


def _publish_receipt_tree(staging: Path, output: Path) -> Path | None:
    """Publish one prevalidated complete tree through one atomic no-replace commit."""

    _sync_receipt_tree(staging)
    _fsync_directory(output.parent)
    try:
        _commit_path_no_replace(staging, output)
    except FileExistsError:
        binding = output / "t09-control-receipt-bindings.json"
        if binding.is_file() and not binding.is_symlink():
            if _receipt_trees_identical(staging, output):
                shutil.rmtree(staging)
                _fsync_directory(output.parent)
                return None
            raise
        recovered = _recover_unsealed_receipt_root(output)
        _commit_path_no_replace(staging, output)
    else:
        recovered = None
    _fsync_directory(output.parent)
    return recovered


def _command_refresh_receipts(args: argparse.Namespace) -> tuple[object, bool]:
    """Generate one new, sealed, package-specific receipt root from clean HEAD."""

    repository = args.repository.resolve(strict=True)
    target = _target_from_args(args)
    output = _new_receipt_output_path(
        repository,
        args.output_root,
        target=target,
    )
    commit, tree = _clean_git_identity(repository)
    _ensure_output_parent(repository, output)
    recovered = _recover_unsealed_receipt_root(output)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{target.selected_contract.version.lower()}-receipt-staging-",
            dir=output.parent,
        )
    )
    try:
        result = _generate_receipt_tree(
            repository,
            staging,
            target=target,
            commit=commit,
            tree=tree,
        )
        publication_recovery = _publish_receipt_tree(staging, output)
        if recovered is None:
            recovered = publication_recovery
        binding_sha = result.get("binding_file_sha256")
        if not isinstance(binding_sha, str):
            raise ValueError("generated binding identity is unavailable")
        validate_current_control_receipt_set(
            repository,
            target.selected_contract,
            _receipt_reference(
                output,
                target=target,
                binding_sha256=binding_sha,
                commit=commit,
                tree=tree,
            ),
        )
    except Exception:
        if staging.exists() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    result["output_root"] = args.output_root.as_posix()
    result["recovered_unsealed_root"] = (
        recovered.relative_to(repository).as_posix() if recovered is not None else None
    )
    result.pop("semantic_sha256", None)
    result["semantic_sha256"] = _semantic_sha256(result)
    return result, result.get("complete") is True


def _repository_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="explicit repository root (default: current directory)",
    )


def _output_file_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-file",
        type=Path,
        help="also write the emitted structured receipt to this explicit path",
    )


def _selection_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider-contract",
        help="exact contract accepted only when compatible with goal/package state",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="giclab-control")
    subcommands = parser.add_subparsers(dest="command", required=True)

    capsule = subcommands.add_parser("state-capsule")
    _repository_argument(capsule)
    _output_file_argument(capsule)
    _selection_argument(capsule)
    capsule.add_argument("--deterministic", action="store_true")
    capsule.add_argument("--format", choices=("json", "yaml"), default="json")
    capsule.set_defaults(handler=_command_state_capsule)

    registry = subcommands.add_parser("registry-check")
    _repository_argument(registry)
    _output_file_argument(registry)
    registry.set_defaults(handler=_command_registry)

    lint = subcommands.add_parser("version-lint")
    _repository_argument(lint)
    _output_file_argument(lint)
    lint.set_defaults(handler=_command_version_lint)

    compose = subcommands.add_parser("compose")
    _repository_argument(compose)
    _output_file_argument(compose)
    compose_selection = compose.add_mutually_exclusive_group()
    compose_selection.add_argument("--provider-contract")
    compose_selection.add_argument("--all-registered", action="store_true")
    compose.set_defaults(handler=_command_compose)

    shadow = subcommands.add_parser("shadow")
    _repository_argument(shadow)
    _selection_argument(shadow)
    shadow_selection = shadow.add_mutually_exclusive_group(required=True)
    shadow_selection.add_argument("--scenario")
    shadow_selection.add_argument("--all-required", action="store_true")
    shadow.add_argument("--fixed-tick", type=int, default=1000)
    shadow.add_argument("--output", type=Path)
    shadow.set_defaults(handler=_command_shadow)

    incidents = subcommands.add_parser("incident-check")
    _repository_argument(incidents)
    _output_file_argument(incidents)
    incidents.set_defaults(handler=_command_incidents)

    agent = subcommands.add_parser("agent-check")
    _repository_argument(agent)
    _output_file_argument(agent)
    _selection_argument(agent)
    agent.set_defaults(handler=_command_agent_check)

    refresh = subcommands.add_parser("refresh-receipts")
    _repository_argument(refresh)
    _selection_argument(refresh)
    refresh.add_argument("--output-root", type=Path, required=True)
    refresh.set_defaults(handler=_command_refresh_receipts)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result, success = args.handler(args)
    except Exception as exc:
        print(f"giclab-control: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(json.dumps({"complete": False, "error": str(exc)}, sort_keys=True))
        return 1
    output_file = getattr(args, "output_file", None)
    if isinstance(output_file, Path):
        output_file.parent.mkdir(parents=True, exist_ok=True)
        if args.command == "state-capsule" and args.format == "yaml":
            output_file.write_text(yaml.safe_dump(result, sort_keys=True), encoding="utf-8")
        else:
            output_file.write_bytes(_json_bytes(result))
    if args.command == "state-capsule" and args.format == "yaml":
        print(yaml.safe_dump(result, sort_keys=True), end="")
    else:
        sys.stdout.buffer.write(_json_bytes(result))
    print(
        f"giclab-control {args.command}: {'passed' if success else 'failed'}",
        file=sys.stderr,
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
