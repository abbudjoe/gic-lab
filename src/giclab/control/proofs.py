"""Exact, document-backed proofs for the Category 3 preparation boundary."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final

from jsonschema import Draft202012Validator

from giclab.control.scenarios import HAPPY_PATH, REQUIRED_FAILURE_SCENARIOS
from giclab.control.target import (
    GOAL_RECORD,
    SelectedRuntimeTarget,
    TargetSelectionError,
    validate_bound_selected_runtime_target_document,
    validate_selected_runtime_target,
    validate_selected_runtime_target_document,
)
from giclab.harness.t09_provider_contracts import T09ProviderContract
from giclab.harness.t09_sira_pilot import load_execution_contract
from giclab.registry import load_json, loads_json, local_schema_registry

CONTROL_BINDING_SCHEMA: Final = "schemas/t09-control-receipt-bindings.schema.json"
STATE_CAPSULE_SCHEMA: Final = "schemas/agent-state-capsule.schema.json"
BASE_COMMIT: Final = "d0aff8a47e92013773d9d05b2cd90fb741658b03"
REPOSITORY_SLUG: Final = "abbudjoe/gic-lab"
BOUND_GOAL_RECORD: Final = "bound-goal-record.yaml"
_HEX40: Final = re.compile(r"^[a-f0-9]{40}$")
_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_PRIVATE_MARKERS: Final = (
    "/Users/",
    "/private/",
    "/var/folders/",
    "/tmp/",
    "BEGIN PRIVATE KEY",
    "OPENAI_API_KEY",
    "LAMBDA_API_KEY",
    "sk-",
    "api_key",
    "credential",
    "password",
    "cookie",
)
_PACKAGE_RECEIPT_ROOT: Final = re.compile(r"^v[1-9][0-9]*$")

LEGACY_REQUIRED_SHARED_SOURCES: Final = frozenset(
    {
        "containers/sira-smoke/pragmatic/t09_freeze_commands.py",
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        "src/giclab/control/__init__.py",
        "src/giclab/control/adapters.py",
        "src/giclab/control/agent_check.py",
        "src/giclab/control/category3.py",
        "src/giclab/control/cli.py",
        "src/giclab/control/composition.py",
        "src/giclab/control/consumers.py",
        "src/giclab/control/contracts.py",
        "src/giclab/control/incidents.py",
        "src/giclab/control/proofs.py",
        "src/giclab/control/production.py",
        "src/giclab/control/registry_validation.py",
        "src/giclab/control/scenarios.py",
        "src/giclab/control/shadow.py",
        "src/giclab/control/state_capsule.py",
        "src/giclab/control/target.py",
        "src/giclab/control/version_lint.py",
        "src/giclab/harness/lambda_campaign_lifecycle.py",
        "src/giclab/harness/lambda_l13_security.py",
        "src/giclab/harness/lambda_l2m_checkpoints.py",
        "src/giclab/harness/lambda_l2m_observer.py",
        "src/giclab/harness/lambda_ssh_key_fingerprint.py",
        "src/giclab/harness/sira_gate_a.py",
        "src/giclab/harness/t09_cleanup_state.py",
        "src/giclab/harness/t09_model_metadata_receipt.py",
        "src/giclab/harness/t09_pragmatic_provider.py",
        "src/giclab/harness/t09_provider_contracts.py",
        "src/giclab/harness/t09_sira_pilot.py",
        "src/giclab/registry.py",
        "src/giclab/validation.py",
    }
)
V2_REQUIRED_SHARED_SOURCES: Final = LEGACY_REQUIRED_SHARED_SOURCES | frozenset(
    {
        "src/giclab/control/anti_shadow_lint.py",
        "src/giclab/control/effects.py",
        "src/giclab/control/live_conformance.py",
        "src/giclab/control/shadow_effects.py",
    }
)
REQUIRED_SHARED_SOURCES: Final = V2_REQUIRED_SHARED_SOURCES | frozenset(
    {
        "containers/sira-smoke/pragmatic/t09_preflight.py",
        "src/giclab/control/live_method_viability.py",
        "src/giclab/control/remote_bridge.py",
        "src/giclab/control/remote_execution_conformance.py",
        "src/giclab/harness/sira_gate_a_runtime.py",
        "src/giclab/harness/t09_remote_host_phases.py",
        "src/giclab/harness/t09_runtime_admission.py",
    }
)


class ControlProofError(ValueError):
    """A control proof failed before any effect boundary."""


@dataclass(frozen=True, slots=True)
class ControlProofReference:
    """An untrusted locator plus exact identity expectations."""

    approved_root: Path
    binding_path: Path
    expected_file_sha256: str
    expected_control_commit: str
    expected_control_tree: str
    expected_repository_slug: str
    expected_provider_contract_version: str
    expected_plan_id: str
    expected_command_package_sha256: str
    expected_target_source: str
    expected_goal_record_sha256: str
    expected_target_semantic_sha256: str


_VALIDATED_CAPSULE = object()
_VALIDATED_RECEIPTS = object()
_VALIDATED_STAGING = object()
_VALIDATED_REHEARSAL = object()


@dataclass(frozen=True, slots=True, init=False)
class ValidatedStateCapsule:
    semantic_sha256: str
    repository_commit: str
    repository_tree: str
    runtime_package: Mapping[str, object]
    selected_runtime_target: Mapping[str, object]
    provenance: tuple[str, ...]
    _proof: object = field(repr=False, compare=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("validated capsules are minted only by exact validators")


@dataclass(frozen=True, slots=True, init=False)
class ValidatedControlReceiptSet:
    binding_semantic_sha256: str
    binding_file_sha256: str
    control_commit: str
    control_tree: str
    provider_contract_version: str
    plan_id: str
    command_package_sha256: str
    state_capsule: ValidatedStateCapsule
    receipt_semantic_sha256s: Mapping[str, str]
    failure_semantic_sha256s: Mapping[str, str]
    _proof: object = field(repr=False, compare=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("validated receipt sets are minted only by exact validators")


@dataclass(frozen=True, slots=True, init=False)
class ValidatedDeterministicStaging:
    semantic_sha256: str
    command_package_sha256: str
    execution_contract_sha256: str
    checked_paths: tuple[str, ...]
    _proof: object = field(repr=False, compare=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("validated staging is minted only by exact validators")


@dataclass(frozen=True, slots=True, init=False)
class ValidatedShadowRehearsal:
    """Internal non-live bootstrap for producing the shadow matrix itself."""

    control_commit: str
    control_tree: str
    provider_contract_version: str
    composition_sha256: str
    state_capsule: ValidatedStateCapsule
    staging: ValidatedDeterministicStaging
    _proof: object = field(repr=False, compare=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("shadow rehearsal proofs are minted only by exact validators")

    def is_valid(self) -> bool:
        return self._proof is _VALIDATED_REHEARSAL


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _semantic_sha256(document: Mapping[str, object]) -> str:
    projected = dict(document)
    observed = projected.pop("semantic_sha256", None)
    expected = _canonical_sha256(projected)
    if observed != expected:
        raise ControlProofError("receipt semantic SHA-256 does not recompute")
    return expected


def _validate_schema(repository: Path, relative: str, document: object) -> None:
    schema = load_json(repository / relative)
    errors = sorted(
        Draft202012Validator(
            schema,
            registry=local_schema_registry(repository / "schemas"),
        ).iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise ControlProofError(f"{relative} validation failed: {errors[0].message}")


def _within(root: Path, path: Path) -> Path:
    approved = root.resolve(strict=True)
    try:
        candidate = path.resolve(strict=True)
    except OSError as exc:
        raise ControlProofError("proof file is unavailable") from exc
    if candidate == approved or approved not in candidate.parents:
        raise ControlProofError("proof file escapes the approved root")
    return candidate


def _regular_no_follow(root: Path, path: Path) -> Path:
    candidate = _within(root, path)
    approved = root.resolve(strict=True)
    try:
        relative = candidate.relative_to(approved)
    except ValueError as exc:  # pragma: no cover - guarded by _within
        raise ControlProofError("proof file escapes the approved root") from exc
    cursor = approved
    for part in relative.parts:
        cursor = cursor / part
        try:
            component = cursor.stat(follow_symlinks=False)
        except OSError as exc:
            raise ControlProofError("proof path component is unavailable") from exc
        if stat.S_ISLNK(component.st_mode):
            raise ControlProofError("proof path contains a symbolic link")
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ControlProofError("proof file metadata is unavailable") from exc
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ControlProofError("proof file is not a single-link regular no-follow file")
    return candidate


def _load_bound_json(
    approved_root: Path,
    reference: Mapping[str, object],
) -> tuple[Path, dict[str, object], str]:
    relative = reference.get("path")
    expected_bytes = reference.get("bytes")
    expected_file_sha = reference.get("file_sha256")
    expected_semantic = reference.get("semantic_sha256")
    if (
        not isinstance(relative, str)
        or PurePosixPath(relative).is_absolute()
        or ".." in PurePosixPath(relative).parts
        or type(expected_bytes) is not int
        or not isinstance(expected_file_sha, str)
        or _HEX64.fullmatch(expected_file_sha) is None
        or not isinstance(expected_semantic, str)
        or _HEX64.fullmatch(expected_semantic) is None
    ):
        raise ControlProofError("artifact binding is malformed")
    path = approved_root / relative
    resolved = _regular_no_follow(approved_root, path)
    encoded = resolved.read_bytes()
    if len(encoded) != expected_bytes or hashlib.sha256(encoded).hexdigest() != expected_file_sha:
        raise ControlProofError(f"bound file bytes changed: {relative}")
    try:
        value = loads_json(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ControlProofError(f"bound file is not strict JSON: {relative}") from exc
    if not isinstance(value, dict):
        raise ControlProofError(f"bound file is not an object: {relative}")
    semantic = _semantic_sha256(value)
    if semantic != expected_semantic:
        raise ControlProofError(f"bound semantic identity changed: {relative}")
    return resolved, value, semantic


def _load_bound_bytes(
    approved_root: Path,
    reference: Mapping[str, object],
) -> tuple[Path, bytes]:
    relative = reference.get("path")
    expected_bytes = reference.get("bytes")
    expected_file_sha = reference.get("file_sha256")
    if (
        not isinstance(relative, str)
        or PurePosixPath(relative).is_absolute()
        or ".." in PurePosixPath(relative).parts
        or type(expected_bytes) is not int
        or not isinstance(expected_file_sha, str)
        or _HEX64.fullmatch(expected_file_sha) is None
    ):
        raise ControlProofError("byte-artifact binding is malformed")
    path = _regular_no_follow(approved_root, approved_root / relative)
    encoded = path.read_bytes()
    if len(encoded) != expected_bytes or hashlib.sha256(encoded).hexdigest() != expected_file_sha:
        raise ControlProofError(f"bound file bytes changed: {relative}")
    return path, encoded


def _bound_registry_versions(document: Mapping[str, object]) -> frozenset[str]:
    """Recover the exact registered version set witnessed by one sealed receipt."""

    entries = document.get("contracts")
    expected_count = document.get("contract_count")
    if (
        document.get("complete") is not True
        or not isinstance(entries, list)
        or type(expected_count) is not int
        or expected_count != len(entries)
    ):
        raise ControlProofError("bound registry receipt is incomplete")
    versions: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("complete") is not True:
            raise ControlProofError("bound registry receipt has an incomplete contract")
        version = entry.get("version")
        if not isinstance(version, str) or re.fullmatch(r"V[1-9][0-9]*", version) is None:
            raise ControlProofError("bound registry receipt has a malformed contract version")
        versions.append(version)
    if len(set(versions)) != len(versions):
        raise ControlProofError("bound registry receipt repeats a contract version")
    return frozenset(versions)


def _git_tree(repository: Path, commit: str) -> str:
    if _HEX40.fullmatch(commit) is None:
        raise ControlProofError("control commit is malformed")
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", f"{commit}^{{tree}}"],
        env={
            "PATH": os.defpath,
            "LANG": "C",
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        raise ControlProofError("control commit does not resolve")
    return completed.stdout.decode("ascii", "ignore").strip()


def _git_blob(repository: Path, commit: str, relative: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository), "show", f"{commit}:{relative}"],
        env={
            "PATH": os.defpath,
            "LANG": "C",
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ControlProofError(f"shared source is absent from control commit: {relative}")
    return completed.stdout


def _public_safe(
    value: object,
    *,
    repository: Path,
    parent_key: str | None = None,
) -> None:
    repository_marker = str(repository.resolve())
    if isinstance(value, str):
        lowered = value.casefold()
        declared_topology_policy = parent_key == "forbidden_path_markers"
        if repository_marker in value or (
            not declared_topology_policy
            and any(marker.casefold() in lowered for marker in _PRIVATE_MARKERS)
        ):
            raise ControlProofError("control proof contains a private path or secret marker")
    elif isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in {"device", "inode", "uid"}:
                raise ControlProofError("control proof contains runtime filesystem topology")
            if any(marker.casefold() in normalized_key for marker in _PRIVATE_MARKERS[8:]):
                raise ControlProofError("control proof contains a secret-like field")
            _public_safe(child, repository=repository, parent_key=str(key))
    elif isinstance(value, list):
        for child in value:
            _public_safe(child, repository=repository, parent_key=parent_key)


def _public_topology_safe(
    value: object,
    *,
    repository: Path,
    parent_key: str | None = None,
) -> None:
    """Reject runtime filesystem identities while permitting explicit lint policy text."""

    repository_marker = str(repository.resolve())
    if isinstance(value, str):
        if repository_marker in value or (
            parent_key != "forbidden_path_markers"
            and any(marker in value for marker in _PRIVATE_MARKERS[:4])
        ):
            raise ControlProofError("control proof contains private runtime topology")
    elif isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in {"device", "inode", "uid"}:
                raise ControlProofError("control proof contains runtime filesystem topology")
            _public_topology_safe(child, repository=repository, parent_key=str(key))
    elif isinstance(value, list):
        for child in value:
            _public_topology_safe(child, repository=repository, parent_key=parent_key)


def discover_sealed_control_receipt_roots(repository: Path) -> tuple[Path, ...]:
    """Enumerate every tracked sealed root without selecting only the current package."""

    root = repository.resolve(strict=True)
    legacy = root / "control/receipts"
    legacy_binding = legacy / "t09-control-receipt-bindings.json"
    if not legacy_binding.is_file() or legacy_binding.is_symlink():
        raise ControlProofError("historical legacy V16 receipt root is missing or unsealed")
    roots = [legacy]
    package_parent = legacy / "packages"
    if not os.path.lexists(package_parent):
        return tuple(roots)
    metadata = package_parent.stat(follow_symlinks=False)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ControlProofError("package receipt-root parent is unsafe")
    for candidate in sorted(package_parent.iterdir(), key=lambda path: path.name):
        if candidate.name.startswith("."):
            continue
        candidate_metadata = candidate.stat(follow_symlinks=False)
        if (
            stat.S_ISLNK(candidate_metadata.st_mode)
            or not stat.S_ISDIR(candidate_metadata.st_mode)
            or _PACKAGE_RECEIPT_ROOT.fullmatch(candidate.name) is None
        ):
            raise ControlProofError("package receipt-root inventory contains an unsafe entry")
        binding = candidate / "t09-control-receipt-bindings.json"
        if not binding.is_file() or binding.is_symlink():
            raise ControlProofError(f"package receipt root is unsealed: {candidate.name}")
        roots.append(candidate)
    return tuple(roots)


def validate_state_capsule_document(
    repository: Path,
    document: Mapping[str, object],
    *,
    expected_commit: str,
    expected_tree: str,
    selected_provider_contract_version: str,
    bound_target: SelectedRuntimeTarget | None = None,
) -> ValidatedStateCapsule:
    """Validate the actual state capsule and mint an opaque proof."""

    root = repository.resolve(strict=True)
    _validate_schema(root, STATE_CAPSULE_SCHEMA, document)
    semantic = _semantic_sha256(document)
    identity = document.get("repository")
    science = document.get("science")
    authority = document.get("authority")
    flags = document.get("machine_readable_flags")
    provenance = document.get("provenance")
    runtime_package = document.get("runtime_package")
    selected_target_document = document.get("selected_runtime_target")
    if identity != {"commit": expected_commit, "tree": expected_tree}:
        raise ControlProofError("state capsule repository identity drifted")
    if not isinstance(science, dict) or (
        science.get("scientific_contract_id") != "EXP-0001"
        or science.get("status") != "unchanged"
        or science.get("interpretation_allowed") is not False
    ):
        raise ControlProofError("state capsule science boundary drifted")
    if not isinstance(authority, dict) or (
        authority.get("category_3") is not False
        or authority.get("inferable_from_repository") is not False
        or authority.get("current_turn_authority") != "external-and-not-present"
    ):
        raise ControlProofError("state capsule inferred live authority")
    if not isinstance(flags, dict) or (
        flags.get("live_authorization") is not False
        or flags.get("scientific_interpretation") is not False
        or flags.get("live_resources_observed_in_this_work") is not False
    ):
        raise ControlProofError("state capsule machine authority/science flags drifted")
    if not isinstance(runtime_package, dict) or not isinstance(selected_target_document, dict):
        raise ControlProofError("state capsule runtime target is malformed")
    try:
        if bound_target is None:
            selected_target = validate_selected_runtime_target_document(
                root,
                selected_target_document,
            )
        else:
            selected_target = bound_target
            if selected_target.to_document() != dict(selected_target_document):
                raise TargetSelectionError(
                    "state capsule target differs from the receipt-bound target"
                )
    except TargetSelectionError as exc:
        raise ControlProofError(f"state capsule runtime target is invalid: {exc}") from exc
    if selected_target.selected_contract.version != selected_provider_contract_version:
        raise ControlProofError("state capsule runtime target selects another contract")
    if (
        runtime_package.get("historical_package") != selected_target.historical_contract_version
        or runtime_package.get("next_package") != selected_target.successor_contract_version
        or runtime_package.get("next_status") != selected_target.successor_status
    ):
        raise ControlProofError("state capsule runtime projection contradicts its target")
    if (
        not isinstance(provenance, list)
        or not provenance
        or not all(isinstance(item, str) for item in provenance)
    ):
        raise ControlProofError("state capsule provenance is incomplete")
    checked_provenance: list[str] = []
    for relative in provenance:
        assert isinstance(relative, str)
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise ControlProofError("state capsule provenance path is unsafe")
        path = root / relative
        metadata = path.stat(follow_symlinks=False)
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise ControlProofError("state capsule provenance does not exist as a regular file")
        checked_provenance.append(relative)
    _public_safe(document, repository=root)
    value = object.__new__(ValidatedStateCapsule)
    object.__setattr__(value, "semantic_sha256", semantic)
    object.__setattr__(value, "repository_commit", expected_commit)
    object.__setattr__(value, "repository_tree", expected_tree)
    object.__setattr__(value, "runtime_package", dict(runtime_package))
    object.__setattr__(
        value,
        "selected_runtime_target",
        dict(selected_target_document),
    )
    object.__setattr__(value, "provenance", tuple(checked_provenance))
    object.__setattr__(value, "_proof", _VALIDATED_CAPSULE)
    return value


def validate_deterministic_staging(
    repository: Path,
    contract: T09ProviderContract,
    *,
    command_package_sha256: str,
) -> ValidatedDeterministicStaging:
    """Run path, storage, archive, package, and execution checks without booleans."""

    root = repository.resolve(strict=True)
    if contract.command_manifest_path is None or contract.execution_contract_path is None:
        raise ControlProofError("selected contract lacks deterministic package paths")
    paths = (
        contract.command_manifest_path,
        contract.execution_contract_path,
        contract.provider_profile_path,
        contract.plan_path,
    )
    checked: list[str] = []
    for relative in paths:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise ControlProofError("deterministic package path is unsafe")
        path = root / relative
        metadata_value = path.stat(follow_symlinks=False)
        if path.is_symlink() or not stat.S_ISREG(metadata_value.st_mode):
            raise ControlProofError("deterministic package path is not a regular no-follow file")
        checked.append(relative)
    command_path = root / contract.command_manifest_path
    if hashlib.sha256(command_path.read_bytes()).hexdigest() != command_package_sha256:
        raise ControlProofError("deterministic command package bytes drifted")
    package = load_json(command_path)
    execution_sha = package.get("execution_contract_sha256")
    if not isinstance(execution_sha, str) or _HEX64.fullmatch(execution_sha) is None:
        raise ControlProofError("deterministic command package lacks execution identity")
    execution = load_execution_contract(
        root / contract.execution_contract_path,
        expected_sha256=execution_sha,
    )
    if execution.provider_contract_version != contract.version or (
        tuple(attempt.run_id for attempt in execution.attempts) != contract.run_ids
    ):
        raise ControlProofError("deterministic execution contract binds another contract")
    probe = _canonical_sha256(
        {
            "contract": contract.version,
            "command_package_sha256": command_package_sha256,
            "execution_contract_sha256": execution_sha,
            "paths": checked,
        }
    )
    with tempfile.TemporaryDirectory(prefix="giclab-t09-staging-proof-") as directory:
        target = Path(directory) / "roundtrip.bin"
        target.write_bytes(probe.encode("ascii"))
        if target.read_bytes() != probe.encode("ascii"):
            raise ControlProofError("deterministic storage roundtrip failed")
    value = object.__new__(ValidatedDeterministicStaging)
    object.__setattr__(value, "semantic_sha256", probe)
    object.__setattr__(value, "command_package_sha256", command_package_sha256)
    object.__setattr__(value, "execution_contract_sha256", execution_sha)
    object.__setattr__(value, "checked_paths", tuple(checked))
    object.__setattr__(value, "_proof", _VALIDATED_STAGING)
    return value


def validate_shadow_rehearsal(
    repository: Path,
    contract: T09ProviderContract,
    *,
    registry_receipt: Mapping[str, object],
    version_lint_receipt: Mapping[str, object],
    composition_receipt: Mapping[str, object],
    state_capsule: Mapping[str, object],
) -> ValidatedShadowRehearsal:
    """Validate the non-circular inputs used only to produce shadow receipts."""

    root = repository.resolve(strict=True)
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD", "HEAD^{tree}"],
        capture_output=True,
        check=True,
        text=True,
    )
    commit, tree = completed.stdout.splitlines()
    for receipt in (registry_receipt, version_lint_receipt, composition_receipt):
        _semantic_sha256(receipt)
        if receipt.get("repository_commit") != commit or receipt.get("repository_tree") != tree:
            raise ControlProofError("shadow rehearsal receipt identity drifted")
    if (
        registry_receipt.get("complete") is not True
        or version_lint_receipt.get("complete") is not True
    ):
        raise ControlProofError("shadow rehearsal registry/lint proof is incomplete")
    if (
        composition_receipt.get("provider_contract_version") != contract.version
        or composition_receipt.get("static_composition_valid") is not True
        or composition_receipt.get("ready_for_shadow") is not True
    ):
        raise ControlProofError("shadow rehearsal composition is incompatible")
    command_sha = composition_receipt.get("command_package_sha256")
    if not isinstance(command_sha, str):
        raise ControlProofError("shadow rehearsal command package identity is missing")
    capsule = validate_state_capsule_document(
        root,
        state_capsule,
        expected_commit=commit,
        expected_tree=tree,
        selected_provider_contract_version=contract.version,
    )
    staging = validate_deterministic_staging(
        root,
        contract,
        command_package_sha256=command_sha,
    )
    value = object.__new__(ValidatedShadowRehearsal)
    object.__setattr__(value, "control_commit", commit)
    object.__setattr__(value, "control_tree", tree)
    object.__setattr__(value, "provider_contract_version", contract.version)
    object.__setattr__(value, "composition_sha256", composition_receipt["semantic_sha256"])
    object.__setattr__(value, "state_capsule", capsule)
    object.__setattr__(value, "staging", staging)
    object.__setattr__(value, "_proof", _VALIDATED_REHEARSAL)
    return value


def _identity_from_receipt(document: Mapping[str, object]) -> tuple[object, object]:
    repository = document.get("repository")
    if isinstance(repository, dict):
        return repository.get("commit"), repository.get("tree")
    if "source_commit" in document or "source_tree" in document:
        return document.get("source_commit"), document.get("source_tree")
    if "control_implementation_commit" in document:
        return (
            document.get("control_implementation_commit"),
            document.get("control_implementation_tree"),
        )
    return document.get("repository_commit"), document.get("repository_tree")


def generate_source_binding_receipt(
    repository: Path,
    *,
    source_commit: str,
    source_tree: str,
) -> dict[str, object]:
    """Hash the complete shared source set for one immutable implementation revision."""

    root = repository.resolve(strict=True)
    if _git_tree(root, source_commit) != source_tree:
        raise ControlProofError("source-binding commit/tree does not resolve")
    files: list[dict[str, object]] = []
    for relative in sorted(REQUIRED_SHARED_SOURCES):
        path = root / relative
        metadata_value = path.stat(follow_symlinks=False)
        if path.is_symlink() or not stat.S_ISREG(metadata_value.st_mode):
            raise ControlProofError("shared source is not a regular no-follow file")
        encoded = path.read_bytes()
        files.append(
            {
                "path": relative,
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    document: dict[str, object] = {
        "schema_version": "3.0.0",
        "base_commit": BASE_COMMIT,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "scope": "shared-control-plane-only",
        "scientific_contract_changed": False,
        "historical_package_changed": False,
        "live_execution_performed": False,
        "files": files,
    }
    document["semantic_sha256"] = _canonical_sha256(document)
    _validate_schema(root, "schemas/t09-control-plane-source-binding.schema.json", document)
    return document


def _artifact_binding(approved_root: Path, path: Path) -> dict[str, object]:
    resolved = _regular_no_follow(approved_root, path)
    encoded = resolved.read_bytes()
    value = loads_json(encoded)
    if not isinstance(value, dict):
        raise ControlProofError("bound artifact is not an object")
    semantic = _semantic_sha256(value)
    return {
        "path": resolved.relative_to(approved_root.resolve(strict=True)).as_posix(),
        "bytes": len(encoded),
        "file_sha256": hashlib.sha256(encoded).hexdigest(),
        "semantic_sha256": semantic,
    }


def _byte_artifact_binding(approved_root: Path, path: Path) -> dict[str, object]:
    resolved = _regular_no_follow(approved_root, path)
    encoded = resolved.read_bytes()
    return {
        "path": resolved.relative_to(approved_root.resolve(strict=True)).as_posix(),
        "bytes": len(encoded),
        "file_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def generate_control_binding_document(
    repository: Path,
    approved_root: Path,
    *,
    control_commit: str,
    control_tree: str,
    target: SelectedRuntimeTarget,
    goal_record_snapshot: Path,
    registry_receipt: Path,
    active_version_lint_receipt: Path,
    composition_receipt: Path,
    state_capsule: Path,
    shadow_happy_path: Path,
    shadow_failures: Mapping[str, Path],
    agent_check_receipt: Path,
    source_binding_receipt: Path,
    incident_receipt: Path,
    anti_shadow_lint_receipt: Path,
    live_effect_conformance_receipt: Path,
    live_method_viability_receipt: Path,
    remote_execution_bridge_conformance_receipt: Path,
) -> dict[str, object]:
    """Build the exact binding document after every constituent is sealed."""

    root = repository.resolve(strict=True)
    approved = approved_root.resolve(strict=True)
    selected_target = validate_selected_runtime_target(root, target)
    if _git_tree(root, control_commit) != control_tree:
        raise ControlProofError("control binding commit/tree does not resolve")
    if set(shadow_failures) != set(REQUIRED_FAILURE_SCENARIOS):
        raise ControlProofError("control binding failure matrix is incomplete")
    registration = selected_target.selected_contract.effect_registration
    document: dict[str, object] = {
        "schema_version": "6.0.0",
        "repository_slug": REPOSITORY_SLUG,
        "base_commit": BASE_COMMIT,
        "control_plane_revision": {"commit": control_commit, "tree": control_tree},
        "selected_runtime_target": selected_target.to_document(),
        "package_effect_registration": (
            None
            if registration is None
            else {
                "implementation_path": registration.implementation_path,
                "implementation_bytes": registration.implementation_bytes,
                "implementation_sha256": registration.implementation_sha256,
                "factory_entry_point": registration.factory_entry_point,
                "authority_grant_schema_version": (registration.authority_grant_schema_version),
                "effect_protocol_version": registration.effect_protocol_version,
            }
        ),
        "artifacts": {
            "goal_record": _byte_artifact_binding(approved, goal_record_snapshot),
            "registry_receipt": _artifact_binding(approved, registry_receipt),
            "active_version_lint_receipt": _artifact_binding(
                approved,
                active_version_lint_receipt,
            ),
            "composition_receipt": _artifact_binding(approved, composition_receipt),
            "state_capsule": _artifact_binding(approved, state_capsule),
            "shadow_happy_path": _artifact_binding(approved, shadow_happy_path),
            "shadow_failures": {
                scenario: _artifact_binding(approved, shadow_failures[scenario])
                for scenario in REQUIRED_FAILURE_SCENARIOS
            },
            "agent_check_receipt": _artifact_binding(approved, agent_check_receipt),
            "source_binding_receipt": _artifact_binding(approved, source_binding_receipt),
            "incident_receipt": _artifact_binding(approved, incident_receipt),
            "anti_shadow_lint_receipt": _artifact_binding(
                approved,
                anti_shadow_lint_receipt,
            ),
            "live_effect_conformance_receipt": _artifact_binding(
                approved,
                live_effect_conformance_receipt,
            ),
            "live_method_viability_receipt": _artifact_binding(
                approved,
                live_method_viability_receipt,
            ),
            "remote_execution_bridge_conformance_receipt": _artifact_binding(
                approved,
                remote_execution_bridge_conformance_receipt,
            ),
        },
        "authority": {
            "live_authorization": False,
            "scientific_interpretation_allowed": False,
            "repository_state_grants_authority": False,
        },
    }
    document["semantic_sha256"] = _canonical_sha256(document)
    _validate_schema(root, CONTROL_BINDING_SCHEMA, document)
    return document


def _validate_control_receipt_set(
    repository: Path,
    contract: T09ProviderContract,
    reference: ControlProofReference,
    *,
    require_current_target_compatibility: bool,
) -> ValidatedControlReceiptSet:
    """Validate one historical proof; optionally require current-goal compatibility."""

    root = repository.resolve(strict=True)
    approved = reference.approved_root.resolve(strict=True)
    binding_path = _regular_no_follow(approved, reference.binding_path)
    encoded = binding_path.read_bytes()
    observed_file_sha = hashlib.sha256(encoded).hexdigest()
    if observed_file_sha != reference.expected_file_sha256:
        raise ControlProofError("binding document file SHA-256 differs from the request")
    try:
        binding = loads_json(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ControlProofError("binding document is not strict JSON") from exc
    if not isinstance(binding, dict):
        raise ControlProofError("binding document is not an object")
    _validate_schema(root, CONTROL_BINDING_SCHEMA, binding)
    binding_semantic = _semantic_sha256(binding)
    binding_version = binding.get("schema_version")
    if binding_version not in {"4.0.0", "5.0.0", "6.0.0"}:
        raise ControlProofError("control binding schema version is unsupported")
    if (
        reference.expected_repository_slug != REPOSITORY_SLUG
        or binding.get("repository_slug") != reference.expected_repository_slug
        or binding.get("base_commit") != BASE_COMMIT
    ):
        raise ControlProofError("binding document repository identity drifted")
    revision = binding.get("control_plane_revision")
    selected = binding.get("selected_runtime_target")
    artifacts = binding.get("artifacts")
    authority = binding.get("authority")
    if not all(isinstance(value, dict) for value in (revision, selected, artifacts, authority)):
        raise ControlProofError("binding document sections are malformed")
    assert isinstance(revision, dict)
    assert isinstance(selected, dict)
    assert isinstance(artifacts, dict)
    assert isinstance(authority, dict)
    commit = revision.get("commit")
    tree = revision.get("tree")
    if (
        (commit, tree)
        != (
            reference.expected_control_commit,
            reference.expected_control_tree,
        )
        or not isinstance(commit, str)
        or not isinstance(tree, str)
    ):
        raise ControlProofError("binding control revision differs from the exact request")
    if _git_tree(root, commit) != tree:
        raise ControlProofError("binding control commit/tree does not resolve")
    goal_reference = artifacts.get("goal_record")
    if not isinstance(goal_reference, dict):
        raise ControlProofError("binding lacks artifact: goal_record")
    goal_path, goal_bytes = _load_bound_bytes(approved, goal_reference)
    if goal_path.name != BOUND_GOAL_RECORD:
        raise ControlProofError("binding goal snapshot path drifted")
    if _git_blob(root, commit, GOAL_RECORD) != goal_bytes:
        raise ControlProofError("binding goal snapshot differs from its control commit")
    registry_reference = artifacts.get("registry_receipt")
    if not isinstance(registry_reference, dict):
        raise ControlProofError("binding lacks artifact: registry_receipt")
    _registry_path, bound_registry, _registry_semantic = _load_bound_json(
        approved,
        registry_reference,
    )
    bound_registered_contract_versions = _bound_registry_versions(bound_registry)
    try:
        selected_target = validate_bound_selected_runtime_target_document(
            root,
            selected,
            goal_bytes=goal_bytes,
            bound_package_commit=commit,
            bound_registered_contract_versions=bound_registered_contract_versions,
        )
    except TargetSelectionError as exc:
        raise ControlProofError(f"binding selected-runtime target is invalid: {exc}") from exc
    if require_current_target_compatibility:
        try:
            current_target = validate_selected_runtime_target_document(root, selected)
        except TargetSelectionError as exc:
            raise ControlProofError(
                f"binding target is incompatible with the current goal: {exc}"
            ) from exc
        if current_target != selected_target:
            raise ControlProofError("binding historical target differs from the current target")
    selected_document = selected_target.to_document()
    if (
        selected_target.selected_contract.version != reference.expected_provider_contract_version
        or selected_target.selected_plan_id != reference.expected_plan_id
        or selected_target.selected_command_package_sha256
        != reference.expected_command_package_sha256
        or selected_target.source != reference.expected_target_source
        or selected_target.goal_record_sha256 != reference.expected_goal_record_sha256
        or selected_document.get("semantic_sha256") != reference.expected_target_semantic_sha256
        or contract != selected_target.selected_contract
        or reference.expected_provider_contract_version != contract.version
        or reference.expected_plan_id != contract.plan_id
    ):
        raise ControlProofError("binding selected another runtime target")
    if binding_version in {"5.0.0", "6.0.0"}:
        registration = contract.effect_registration
        expected_registration: dict[str, object] | None = (
            None
            if registration is None
            else {
                "implementation_path": registration.implementation_path,
                "implementation_bytes": registration.implementation_bytes,
                "implementation_sha256": registration.implementation_sha256,
                "factory_entry_point": registration.factory_entry_point,
                "authority_grant_schema_version": (registration.authority_grant_schema_version),
                "effect_protocol_version": registration.effect_protocol_version,
            }
        )
        if binding.get("package_effect_registration") != expected_registration:
            raise ControlProofError("binding package-effect registration drifted")
        if registration is not None:
            encoded_effect = _git_blob(root, commit, registration.implementation_path)
            if (
                len(encoded_effect) != registration.implementation_bytes
                or hashlib.sha256(encoded_effect).hexdigest() != registration.implementation_sha256
            ):
                raise ControlProofError("binding package-effect source differs from Git")
    if authority != {
        "live_authorization": False,
        "scientific_interpretation_allowed": False,
        "repository_state_grants_authority": False,
    }:
        raise ControlProofError("binding document claims live or scientific authority")

    names: tuple[str, ...] = (
        "registry_receipt",
        "active_version_lint_receipt",
        "composition_receipt",
        "state_capsule",
        "shadow_happy_path",
        "agent_check_receipt",
        "source_binding_receipt",
        "incident_receipt",
    )
    if binding_version in {"5.0.0", "6.0.0"}:
        names = (
            *names,
            "anti_shadow_lint_receipt",
            "live_effect_conformance_receipt",
        )
    if binding_version == "6.0.0":
        names = (
            *names,
            "live_method_viability_receipt",
            "remote_execution_bridge_conformance_receipt",
        )
    documents: dict[str, dict[str, object]] = {}
    semantics: dict[str, str] = {}
    for name in names:
        raw_reference = artifacts.get(name)
        if not isinstance(raw_reference, dict):
            raise ControlProofError(f"binding lacks artifact: {name}")
        _path, document, semantic = _load_bound_json(approved, raw_reference)
        documents[name] = document
        semantics[name] = semantic
    failure_references = artifacts.get("shadow_failures")
    if not isinstance(failure_references, dict) or set(failure_references) != set(
        REQUIRED_FAILURE_SCENARIOS
    ):
        raise ControlProofError("binding failure scenario set is incomplete or substituted")
    failures: dict[str, dict[str, object]] = {}
    failure_semantics: dict[str, str] = {}
    failure_paths: set[str] = set()
    for scenario in REQUIRED_FAILURE_SCENARIOS:
        raw_reference = failure_references.get(scenario)
        if not isinstance(raw_reference, dict):
            raise ControlProofError(f"binding lacks failure scenario: {scenario}")
        path, document, semantic = _load_bound_json(approved, raw_reference)
        if path.name != f"{scenario}.json" or document.get("scenario") != scenario:
            raise ControlProofError("shadow failure filename/document scenario was swapped")
        if str(path) in failure_paths:
            raise ControlProofError("one shadow receipt was duplicated under another scenario")
        failure_paths.add(str(path))
        failures[scenario] = document
        failure_semantics[scenario] = semantic

    expected_files = {
        binding_path.relative_to(approved).as_posix(),
        goal_path.relative_to(approved).as_posix(),
    }
    for name in names:
        raw_reference = artifacts[name]
        assert isinstance(raw_reference, dict)
        relative = raw_reference.get("path")
        if isinstance(relative, str):
            expected_files.add(relative)
    for raw_reference in failure_references.values():
        assert isinstance(raw_reference, dict)
        relative = raw_reference.get("path")
        if isinstance(relative, str):
            expected_files.add(relative)
    observed_files: set[str] = set()
    legacy_root = root / "control/receipts"
    for path in approved.rglob("*"):
        relative_path = path.relative_to(approved)
        if approved == legacy_root and relative_path.parts[:1] == ("packages",):
            continue
        metadata = path.stat(follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode):
            raise ControlProofError("receipt root contains a symbolic link")
        if stat.S_ISREG(metadata.st_mode):
            observed_files.add(relative_path.as_posix())
    if observed_files != expected_files:
        missing = sorted(expected_files - observed_files)
        conflicting = sorted(observed_files - expected_files)
        raise ControlProofError(
            f"receipt root artifact inventory drifted: missing={missing}, conflicting={conflicting}"
        )

    schema_map = {
        "active_version_lint_receipt": "schemas/t09-active-version-lint-receipt.schema.json",
        "registry_receipt": "schemas/t09-control-registry-receipt.schema.json",
        "composition_receipt": "schemas/t09-control-composition-receipt.schema.json",
        "state_capsule": STATE_CAPSULE_SCHEMA,
        "shadow_happy_path": "schemas/t09-category3-shadow-receipt.schema.json",
        "agent_check_receipt": "schemas/t09-agent-check-receipt.schema.json",
        "source_binding_receipt": "schemas/t09-control-plane-source-binding.schema.json",
        "incident_receipt": "schemas/t09-incident-completeness-receipt.schema.json",
    }
    if binding_version in {"5.0.0", "6.0.0"}:
        schema_map.update(
            {
                "anti_shadow_lint_receipt": ("schemas/t09-anti-shadow-lint-receipt.schema.json"),
                "live_effect_conformance_receipt": (
                    "schemas/t09-live-effect-conformance-receipt.schema.json"
                ),
            }
        )
    if binding_version == "6.0.0":
        schema_map.update(
            {
                "live_method_viability_receipt": ("schemas/t09-live-method-viability.schema.json"),
                "remote_execution_bridge_conformance_receipt": (
                    "schemas/t09-remote-execution-bridge-conformance.schema.json"
                ),
            }
        )
    for name, schema_path in schema_map.items():
        _validate_schema(root, schema_path, documents[name])
    for failure in failures.values():
        _validate_schema(root, "schemas/t09-category3-shadow-receipt.schema.json", failure)

    all_documents = [*documents.values(), *failures.values()]
    for document in all_documents:
        _public_topology_safe(document, repository=root)
        identity = _identity_from_receipt(document)
        if identity != (commit, tree):
            raise ControlProofError("bound receipts do not share the exact control revision")
    registry = documents["registry_receipt"]
    lint = documents["active_version_lint_receipt"]
    composition = documents["composition_receipt"]
    incident_receipt = documents["incident_receipt"]
    if (
        registry.get("complete") is not True
        or registry.get("contract_count") is None
        or lint.get("complete") is not True
        or lint.get("findings") != []
    ):
        raise ControlProofError("registry or active-version lint receipt is incomplete")
    registry_entries = registry.get("contracts")
    if not isinstance(registry_entries, list) or not all(
        isinstance(entry, dict) and entry.get("complete") is True for entry in registry_entries
    ):
        raise ControlProofError("registry receipt lacks a complete per-contract matrix")
    if not any(
        isinstance(entry, dict)
        and entry.get("version") == contract.version
        and entry.get("plan_id") == contract.plan_id
        for entry in registry_entries
    ):
        raise ControlProofError("registry receipt lacks the selected runtime target")
    if (
        composition.get("provider_contract_version") != contract.version
        or composition.get("command_package_sha256") != reference.expected_command_package_sha256
        or composition.get("static_composition_valid") is not True
        or composition.get("ready_for_shadow") is not True
        or composition.get("registry_receipt_sha256") != semantics["registry_receipt"]
        or composition.get("version_lint_receipt_sha256")
        != semantics["active_version_lint_receipt"]
        or composition.get("target_schema_sha256")
        != hashlib.sha256(
            (root / "schemas/t09-control-target.schema.json").read_bytes()
        ).hexdigest()
    ):
        raise ControlProofError("composition receipt cross-binding drifted")

    capsule_document = documents["state_capsule"]
    blocker = capsule_document.get("blocking_incident")
    governance = capsule_document.get("external_governance_gate")
    incident_entries = incident_receipt.get("incidents")
    if governance != {
        "kind": "independent-exact-head-review-and-explicit-merge-authorization",
        "state": "consult-external-state",
        "repository_state_grants_authority": False,
    }:
        raise ControlProofError("state capsule governance gate drifted")
    if blocker is not None:
        matched_incidents = (
            [
                entry
                for entry in incident_entries
                if isinstance(entry, dict) and entry.get("incident_id") == blocker
            ]
            if isinstance(incident_entries, list)
            else []
        )
        if len(matched_incidents) != 1:
            raise ControlProofError("state capsule blocking incident is absent from history")
        if matched_incidents[0].get("status") == "resolved":
            raise ControlProofError("state capsule names a resolved incident as blocker")

    capsule = validate_state_capsule_document(
        root,
        capsule_document,
        expected_commit=commit,
        expected_tree=tree,
        selected_provider_contract_version=contract.version,
        bound_target=selected_target,
    )
    if documents["state_capsule"].get("selected_runtime_target") != selected:
        raise ControlProofError("state capsule does not bind the selected runtime target")
    capsule_control = documents["state_capsule"].get("control_plane")
    capsule_required_fields: tuple[str, ...] = (
        "registry_complete",
        "composition_valid",
        "active_version_lint_valid",
        "shadow_happy_path",
        "failure_matrix_valid",
    )
    if binding_version in {"5.0.0", "6.0.0"}:
        capsule_required_fields = (
            *capsule_required_fields,
            "anti_shadow_lint_valid",
            "live_effect_conformance_valid",
        )
    if binding_version == "6.0.0":
        capsule_required_fields = (
            *capsule_required_fields,
            "live_method_viability_valid",
            "remote_execution_bridge_conformance_valid",
        )
    if not isinstance(capsule_control, dict) or any(
        capsule_control.get(field) is not True for field in capsule_required_fields
    ):
        raise ControlProofError("state capsule does not claim the complete bound control proof")

    if binding_version in {"5.0.0", "6.0.0"}:
        anti_shadow = documents["anti_shadow_lint_receipt"]
        anti_counts = anti_shadow.get("classification_counts")
        anti_topology = anti_shadow.get("public_receipt_topology_scan")
        conformance = documents["live_effect_conformance_receipt"]
        temporary_package = conformance.get("temporary_package")
        base_inventory = anti_shadow.get("base_assumption_inventory")
        if (
            anti_shadow.get("complete") is not True
            or anti_shadow.get("findings") != []
            or not isinstance(anti_counts, dict)
            or anti_counts.get("shared production-wrapper defect") != 0
            or not isinstance(base_inventory, list)
            or [item.get("assumption_id") for item in base_inventory if isinstance(item, dict)]
            != [f"SA-{index:02d}" for index in range(1, 13)]
        ):
            raise ControlProofError("anti-shadow source lint receipt is incomplete")
        if anti_shadow.get("schema_version") in {"3.0.0", "4.0.0"}:
            expected_receipt_root = f"control/receipts/packages/{contract.version.lower()}"
            sealed_roots = (
                anti_topology.get("sealed_roots_scanned")
                if isinstance(anti_topology, dict)
                else None
            )
            if (
                not isinstance(anti_topology, dict)
                or anti_topology.get("selected_provider_contract_version") != contract.version
                or anti_topology.get("selected_receipt_root") != expected_receipt_root
                or anti_topology.get("selected_root_matches_version") is not True
                or not isinstance(sealed_roots, list)
                or expected_receipt_root not in sealed_roots
            ):
                raise ControlProofError(
                    "anti-shadow topology receipt does not bind the selected package root"
                )
        if (
            conformance.get("complete") is not True
            or conformance.get("shared_source_byte_map_unchanged") is not True
            or conformance.get("actual_v17_artifacts_created") is not False
            or conformance.get("network_provider_cloud_browser_science_effects") != 0
            or conformance.get("live_authority_created") is not False
            or conformance.get("scientific_interpretation_allowed") is not False
            or not isinstance(temporary_package, dict)
            or temporary_package.get("provider_contract_version") != contract.version
            or temporary_package.get("controller_terminal_state") != "category3-live-complete-clean"
            or temporary_package.get("zero_real_effects") is not True
            or temporary_package.get("repository_state_grants_authority") is not False
        ):
            raise ControlProofError("live-effect conformance receipt is incomplete")
        assert isinstance(temporary_package, dict)
        conformance_metadata = temporary_package.get("metadata")
        conformance_clock = temporary_package.get("clock")
        conformance_traces = temporary_package.get("condition_traces")
        model_accounting = temporary_package.get("model_call_accounting")
        browser_accounting = temporary_package.get("browser_accounting")
        host_transaction = temporary_package.get("host_transaction")
        evidence_chain = temporary_package.get("raw_finalizer_evaluator_chain")
        cleanup = temporary_package.get("cleanup")
        if (
            conformance_metadata
            != {
                "noncanonical_runtime_credential_reached_channel": True,
                "request_count": 1,
                "zero_retry": True,
                "zero_redirect": True,
                "zero_pagination": True,
                "credential_material_retained": False,
            }
            or not isinstance(conformance_clock, dict)
            or conformance_clock.get("injected") is not True
            or conformance_clock.get("domains_separate") is not True
            or 0.25 not in conformance_clock.get("sleep_calls", [])
            or not isinstance(conformance_traces, dict)
            or set(conformance_traces) != set(contract.run_ids)
            or not isinstance(model_accounting, dict)
            or not isinstance(browser_accounting, dict)
            or host_transaction
            != {
                "tracked_package_staged_and_acknowledged": True,
                "retained_provider_entry_consumed": True,
                "preflight_qualification_freeze_receipts_validated": True,
                "dynamic_frozen_manifest": True,
            }
            or evidence_chain
            != {
                "attempt_count": len(contract.run_ids),
                "raw_files_hash_validated": True,
                "finalizer_consumed_raw_manifests": True,
                "effect_answer_reached_finalized_session": True,
                "evaluator_consumed_finalized_sessions": True,
            }
            or cleanup
            != {
                "state": "complete",
                "resumed": False,
                "provider_resources_zero": True,
                "security_restored": True,
                "privacy_clean": True,
            }
        ):
            raise ControlProofError("live-effect conformance subproofs are incomplete")
        total_calls = 0
        total_actions = 0
        for run_id, raw_trace in conformance_traces.items():
            if not isinstance(raw_trace, dict):
                raise ControlProofError("live-effect condition trace is malformed")
            call_count = raw_trace.get("model_call_count")
            roles = raw_trace.get("model_roles")
            action_count = raw_trace.get("browser_action_count")
            minimum_calls = 5 if "SIMULATIVE" in run_id else 3
            minimum_roles = 3 if "SIMULATIVE" in run_id else 2
            if (
                not isinstance(call_count, int)
                or isinstance(call_count, bool)
                or call_count < minimum_calls
                or not isinstance(roles, list)
                or len(set(roles)) < minimum_roles
                or not isinstance(action_count, int)
                or isinstance(action_count, bool)
                or action_count < 2
                or raw_trace.get("stable_unique_call_ids") is not True
                or raw_trace.get("terminal_states_complete") is not True
            ):
                raise ControlProofError("live-effect condition trace shape drifted")
            total_calls += call_count
            total_actions += action_count
        if (
            model_accounting.get("total_calls") != total_calls
            or model_accounting.get("stable_unique_call_ids") is not True
            or model_accounting.get("terminal_states_complete") is not True
            or model_accounting.get("roles_are_multi_role") is not True
            or model_accounting.get("zero_retries") is not True
            or browser_accounting.get("total_actions") != total_actions
            or browser_accounting.get("multiple_actions_per_condition") is not True
        ):
            raise ControlProofError("live-effect accounting aggregate drifted")
        if (
            selected_target.successor_status == "not-created"
            and conformance.get("actual_v17_artifacts_present") is not False
        ):
            raise ControlProofError("live-effect conformance observed an undeclared successor")
    if binding_version == "6.0.0":
        viability = documents["live_method_viability_receipt"]
        viability_checks = viability.get("checks")
        viability_methods = viability.get("methods")
        map_bytes = _git_blob(root, commit, "control/live-method-map.json")
        try:
            map_document = loads_json(map_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ControlProofError("bound live-method map is not strict JSON") from exc
        if (
            viability.get("schema_version") != "1.0.0"
            or viability.get("effect_protocol_version") != "2.0.0"
            or viability.get("method_map_path") != "control/live-method-map.json"
            or viability.get("method_map_bytes") != len(map_bytes)
            or viability.get("method_map_file_sha256") != hashlib.sha256(map_bytes).hexdigest()
            or viability.get("method_map_semantic_sha256") != _canonical_sha256(map_document)
            or not isinstance(viability_checks, dict)
            or not viability_checks
            or any(value is not True for value in viability_checks.values())
            or not isinstance(viability_methods, list)
            or not viability_methods
            or any(
                not isinstance(method, dict) or method.get("live_mapping_complete") is not True
                for method in viability_methods
            )
            or viability.get("unresolved_methods") != []
            or viability.get("findings") != []
            or viability.get("live_environment_required") is not False
            or viability.get("real_effects_performed") != 0
            or viability.get("complete") is not True
        ):
            raise ControlProofError("live-method viability receipt is incomplete")

        bridge = documents["remote_execution_bridge_conformance_receipt"]
        bridge_controller = bridge.get("controller_conformance")
        bridge_host = bridge.get("host_phase_entrypoints")
        bridge_duplex = bridge.get("duplex_condition_sessions")
        bridge_accountant = bridge.get("sole_accountant")
        bridge_evidence = bridge.get("evidence")
        bridge_failures = bridge.get("failure_probes")
        bridge_zero = bridge.get("zero_real_effects")
        if (
            bridge.get("schema_version") != "1.0.0"
            or bridge.get("provider_contract_version") != selected_target.selected_contract.version
            or bridge.get("effect_protocol_version") != "2.0.0"
            or bridge.get("bridge_protocol_version") != "1.0.0"
            or bridge.get("shared_controller_entry_point")
            != "giclab.control.category3.execute_category3_transaction"
            or bridge.get("production_assembly_entry_point")
            != "giclab.control.production.build_production_adapter_assembly"
            or not isinstance(bridge_controller, dict)
            or bridge_controller.get("receipt_semantic_sha256")
            != semantics["live_effect_conformance_receipt"]
            or bridge_controller.get("terminal_state") != "category3-live-complete-clean"
            or bridge_controller.get("condition_session_count") != 4
            or bridge_controller.get("first_pair_checkpoint_retained") is not True
            or bridge_controller.get("raw_finalizer_evaluator_chain") is not True
            or bridge_controller.get("cleanup_to_zero") is not True
            or bridge_controller.get("shared_controller_used") is not True
            or bridge_controller.get("shared_production_assembly_used") is not True
            or not isinstance(bridge_host, dict)
            or bridge_host.get("provider_entry_precedes_transfer") is not True
            or bridge_host.get("transfer_rehashed") is not True
            or bridge_host.get("full_manifest_validated") is not True
            or bridge_host.get("network_effects") != 0
            or not isinstance(bridge_duplex, dict)
            or bridge_duplex.get("session_count") != 4
            or bridge_duplex.get("all_terminal_acknowledged") is not True
            or bridge_duplex.get("all_remote_boundaries_nonauthoritative") is not True
            or bridge_duplex.get("all_effects_admitted_before_execution") is not True
            or bridge_duplex.get("all_processes_reaped") is not True
            or bridge_duplex.get("all_private_endpoints_removed") is not True
            or bridge_accountant
            != {
                "owner": "ConditionEventObserver",
                "remote_boundary_authoritative": False,
                "independent_remote_budget_boundary": False,
                "coupling_probe_passed": True,
            }
            or not isinstance(bridge_evidence, dict)
            or any(value is not True for value in bridge_evidence.values())
            or not isinstance(bridge_failures, dict)
            or any(value is not True for value in bridge_failures.values())
            or not isinstance(bridge_zero, dict)
            or any(
                bridge_zero.get(field) != 0
                for field in (
                    "secret_reads",
                    "authenticated_metadata_requests",
                    "provider_requests",
                    "cloud_mutations",
                    "live_ssh",
                    "docker",
                    "browser",
                    "scientific_actions",
                    "condition_reservations",
                )
            )
            or bridge_zero.get("new_cost_usd") != "0.00"
            or bridge.get("actual_v17_artifacts_created") is not False
            or bridge.get("live_authority_created") is not False
            or bridge.get("scientific_interpretation_allowed") is not False
            or bridge.get("projected_real_cost_usd") != "0.00"
            or bridge.get("complete") is not True
        ):
            raise ControlProofError("remote-execution bridge conformance is incomplete")
    happy = documents["shadow_happy_path"]
    if (
        happy.get("scenario") != HAPPY_PATH
        or happy.get("scenario_valid") is not True
        or happy.get("terminal_state") != "category3-shadow-complete-clean"
        or happy.get("implementation_flavor") != "production-wrapper"
        or happy.get("effect_authority") != "shadow-only"
        or happy.get("shadow_only") is not True
        or happy.get("scientific_interpretation_allowed") is not False
        or happy.get("zero_undeclared_calls") is not True
        or happy.get("provider_contract_version") != contract.version
        or happy.get("command_package_sha256") != reference.expected_command_package_sha256
    ):
        raise ControlProofError("happy-path shadow receipt is not complete-clean production shadow")
    happy_counts = happy.get("call_counts")
    happy_production = happy.get("production_control_evidence")
    happy_accounting = (
        happy_production.get("accounting") if isinstance(happy_production, dict) else None
    )
    if (
        not isinstance(happy_counts, dict)
        or not isinstance(happy_accounting, dict)
        or not isinstance(happy_counts.get("model_call_attempts"), int)
        or happy_counts["model_call_attempts"] <= 0
        or not isinstance(happy_counts.get("browser_actions"), int)
        or happy_counts["browser_actions"] <= 0
        or happy_accounting.get("fake_usage") is not True
        or happy_accounting.get("zero_retries") is not True
        or happy_accounting.get("projected_real_cost_usd") != 0.0
        or not isinstance(happy_accounting.get("aggregate_observed_cost_usd"), (int, float))
        or happy_accounting["aggregate_observed_cost_usd"] <= 0
        or not isinstance(happy_accounting.get("aggregate_charged_upper_cost_usd"), (int, float))
        or happy_accounting["aggregate_charged_upper_cost_usd"] <= 0
    ):
        raise ControlProofError("happy-path shadow accounting proof is incomplete")
    if binding_version in {"5.0.0", "6.0.0"}:
        conformance_package = documents["live_effect_conformance_receipt"].get("temporary_package")
        if (
            not isinstance(conformance_package, dict)
            or not isinstance(happy_production, dict)
            or conformance_package.get("package_budget") != happy_production.get("package_budget")
        ):
            raise ControlProofError(
                "live-effect conformance package budget differs from the shared shadow"
            )
    for scenario, document in failures.items():
        command_package_matches = (
            document.get("command_package_sha256") is None
            if scenario == "lifecycle-unsupported"
            else document.get("command_package_sha256") == reference.expected_command_package_sha256
        )
        if (
            document.get("scenario") != scenario
            or document.get("scenario_valid") is not True
            or document.get("implementation_flavor") != "production-wrapper"
            or document.get("shadow_only") is not True
            or document.get("scientific_interpretation_allowed") is not False
            or document.get("zero_undeclared_calls") is not True
            or document.get("provider_contract_version") != contract.version
            or not command_package_matches
        ):
            raise ControlProofError(f"failure shadow receipt is incompatible: {scenario}")

    agent = documents["agent_check_receipt"]
    checks = agent.get("checks")
    if (
        agent.get("complete") is not True
        or not isinstance(checks, dict)
        or agent.get("selected_runtime_target") != selected
        or agent.get("selected_composition_semantic_sha256") != semantics["composition_receipt"]
    ):
        raise ControlProofError("aggregate agent-check receipt is incomplete")
    scalar_bindings = {
        "active_version_lint": semantics["active_version_lint_receipt"],
        "registry_completeness": semantics["registry_receipt"],
        "incident_completeness": semantics["incident_receipt"],
        "state_capsule": semantics["state_capsule"],
        "source_binding": semantics["source_binding_receipt"],
    }
    if binding_version in {"5.0.0", "6.0.0"}:
        scalar_bindings.update(
            {
                "anti_shadow_lint": semantics["anti_shadow_lint_receipt"],
                "live_effect_conformance": semantics["live_effect_conformance_receipt"],
            }
        )
    if binding_version == "6.0.0":
        scalar_bindings.update(
            {
                "live_method_viability": semantics["live_method_viability_receipt"],
                "remote_execution_bridge_conformance": semantics[
                    "remote_execution_bridge_conformance_receipt"
                ],
            }
        )
    for check_name, expected in scalar_bindings.items():
        check = checks.get(check_name)
        if not isinstance(check, dict) or check.get("semantic_sha256") != expected:
            raise ControlProofError(f"agent-check does not bind constituent: {check_name}")
    composition_check = checks.get("offline_composition")
    entries = composition_check.get("contracts") if isinstance(composition_check, dict) else None
    if (
        not isinstance(composition_check, dict)
        or composition_check.get("selected_provider_contract_version") != contract.version
        or composition_check.get("selected_semantic_sha256") != semantics["composition_receipt"]
        or not isinstance(entries, list)
        or not any(
            isinstance(entry, dict)
            and entry.get("version") == contract.version
            and entry.get("semantic_sha256") == semantics["composition_receipt"]
            for entry in entries
        )
    ):
        raise ControlProofError("agent-check does not bind selected composition")
    shadow_check = checks.get("category3_shadow")
    shadow_entries = shadow_check.get("scenarios") if isinstance(shadow_check, dict) else None
    if (
        not isinstance(shadow_check, dict)
        or shadow_check.get("selected_provider_contract_version") != contract.version
        or shadow_check.get("selected_command_package_sha256")
        != reference.expected_command_package_sha256
    ):
        raise ControlProofError("agent-check shadow target drifted")
    observed_shadow = (
        {
            entry.get("scenario"): entry.get("semantic_sha256")
            for entry in shadow_entries
            if isinstance(entry, dict)
        }
        if isinstance(shadow_entries, list)
        else {}
    )
    expected_shadow = {HAPPY_PATH: semantics["shadow_happy_path"], **failure_semantics}
    if observed_shadow != expected_shadow:
        raise ControlProofError("agent-check does not cross-bind the exact shadow matrix")

    source = documents["source_binding_receipt"]
    if (
        source.get("source_commit") != commit
        or source.get("source_tree") != tree
        or source.get("scientific_contract_changed") is not False
        or source.get("historical_package_changed") is not False
        or source.get("live_execution_performed") is not False
    ):
        raise ControlProofError("source-binding receipt identity or authority drifted")
    source_files = source.get("files")
    observed_sources = (
        {item.get("path") for item in source_files if isinstance(item, dict)}
        if isinstance(source_files, list)
        else set()
    )
    expected_sources = (
        LEGACY_REQUIRED_SHARED_SOURCES
        if source.get("schema_version") == "1.0.0"
        else V2_REQUIRED_SHARED_SOURCES
        if source.get("schema_version") == "2.0.0"
        else REQUIRED_SHARED_SOURCES
        if source.get("schema_version") == "3.0.0"
        else frozenset()
    )
    expected_source_version = {
        "4.0.0": "1.0.0",
        "5.0.0": "2.0.0",
        "6.0.0": "3.0.0",
    }[binding_version]
    if source.get("schema_version") != expected_source_version:
        raise ControlProofError("source-binding schema does not match the binding generation")
    if observed_sources != expected_sources:
        raise ControlProofError("source-binding receipt lacks the exact shared source set")
    assert isinstance(source_files, list)
    for item in source_files:
        assert isinstance(item, dict)
        relative = item.get("path")
        expected_bytes = item.get("bytes")
        expected_sha = item.get("sha256")
        if not isinstance(relative, str):
            raise ControlProofError("source-binding member path is malformed")
        retained = _git_blob(root, commit, relative)
        if len(retained) != expected_bytes or hashlib.sha256(retained).hexdigest() != expected_sha:
            raise ControlProofError(f"source-binding member differs from Git: {relative}")
        if require_current_target_compatibility:
            current = root / relative
            current_metadata = current.stat(follow_symlinks=False)
            if current.is_symlink() or not stat.S_ISREG(current_metadata.st_mode):
                raise ControlProofError(
                    f"shared source is not a regular no-follow file: {relative}"
                )
            if current.read_bytes() != retained:
                raise ControlProofError(
                    f"shared source changed after the control revision: {relative}"
                )

    value = object.__new__(ValidatedControlReceiptSet)
    object.__setattr__(value, "binding_semantic_sha256", binding_semantic)
    object.__setattr__(value, "binding_file_sha256", observed_file_sha)
    object.__setattr__(value, "control_commit", commit)
    object.__setattr__(value, "control_tree", tree)
    object.__setattr__(value, "provider_contract_version", contract.version)
    object.__setattr__(value, "plan_id", contract.plan_id)
    object.__setattr__(
        value,
        "command_package_sha256",
        reference.expected_command_package_sha256,
    )
    object.__setattr__(value, "state_capsule", capsule)
    object.__setattr__(value, "receipt_semantic_sha256s", dict(semantics))
    object.__setattr__(value, "failure_semantic_sha256s", dict(failure_semantics))
    object.__setattr__(value, "_proof", _VALIDATED_RECEIPTS)
    return value


def validate_control_receipt_set(
    repository: Path,
    contract: T09ProviderContract,
    reference: ControlProofReference,
) -> ValidatedControlReceiptSet:
    """Validate a sealed root solely against its immutable bound historical state."""

    return _validate_control_receipt_set(
        repository,
        contract,
        reference,
        require_current_target_compatibility=False,
    )


def validate_current_control_receipt_set(
    repository: Path,
    contract: T09ProviderContract,
    reference: ControlProofReference,
) -> ValidatedControlReceiptSet:
    """Validate a sealed historical proof and its equality with the current target."""

    return _validate_control_receipt_set(
        repository,
        contract,
        reference,
        require_current_target_compatibility=True,
    )
