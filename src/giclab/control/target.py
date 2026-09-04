"""Resolve one exact, goal-compatible runtime package before any effect boundary."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

import yaml
from jsonschema import Draft202012Validator

from giclab.control.effects import validate_package_effect_registration
from giclab.control.registry_validation import resolve_registered_command_package
from giclab.harness import t09_provider_contracts as provider_contracts
from giclab.harness.t09_provider_contracts import (
    T09ProviderContract,
    load_provider_plan,
    load_provider_profile,
)
from giclab.registry import load_json

GOAL_RECORD: Final = "control/goals/EXP-0001.yaml"
TARGET_SCHEMA: Final = "schemas/t09-control-target.schema.json"
TARGET_SCHEMA_VERSION: Final = "1.0.0"
GOAL_SOURCE: Final = "goal-record"
EXPLICIT_SOURCE: Final = "explicit-provider-contract"
_VERSION: Final = re.compile(r"^V([1-9][0-9]*)$")
_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_MAX_GOAL_BYTES: Final = 128 * 1024
_PRIVATE_VALUE_MARKERS: Final = (
    "/Users/",
    "BEGIN PRIVATE KEY",
    "OPENAI_API_KEY",
    "LAMBDA_API_KEY",
    "sk-",
)
_PRIVATE_KEY_MARKERS: Final = (
    "api_key",
    "credential",
    "password",
    "cookie",
    "secret_value",
    "access_token",
)


class TargetSelectionError(ValueError):
    """The goal/package state cannot select one safe runtime target."""


@dataclass(frozen=True, slots=True)
class SelectedRuntimeTarget:
    """One exact package identity selected without granting live authority."""

    source: str
    historical_contract_version: str
    successor_contract_version: str
    successor_status: str
    selected_contract: T09ProviderContract
    selected_plan_id: str
    selected_command_package_sha256: str
    selected_package_status: str
    goal_record_sha256: str

    def to_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "schema_version": TARGET_SCHEMA_VERSION,
            "source": self.source,
            "goal_record_path": GOAL_RECORD,
            "goal_record_sha256": self.goal_record_sha256,
            "historical_contract_version": self.historical_contract_version,
            "successor_contract_version": self.successor_contract_version,
            "successor_status": self.successor_status,
            "selected_provider_contract_version": self.selected_contract.version,
            "selected_plan_id": self.selected_plan_id,
            "selected_command_package_sha256": self.selected_command_package_sha256,
            "selected_package_status": self.selected_package_status,
            "authority": {
                "live_authorization": False,
                "scientific_interpretation_allowed": False,
                "repository_state_grants_authority": False,
            },
        }
        document["semantic_sha256"] = _canonical_sha256(document)
        return document


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _required_mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    selected = value.get(key)
    if not isinstance(selected, dict):
        raise TargetSelectionError(f"goal record lacks {key}")
    return selected


def _version_number(value: object, *, field: str) -> int:
    if not isinstance(value, str):
        raise TargetSelectionError(f"goal {field} is malformed")
    matched = _VERSION.fullmatch(value)
    if matched is None:
        raise TargetSelectionError(f"goal {field} is malformed")
    return int(matched.group(1))


def _public_safe(value: object, *, repository: Path) -> None:
    repository_marker = str(repository.resolve())
    if isinstance(value, str):
        lowered = value.casefold()
        if repository_marker in value or any(
            marker.casefold() in lowered for marker in _PRIVATE_VALUE_MARKERS
        ):
            raise TargetSelectionError("goal record contains a private or secret-like value")
    elif isinstance(value, dict):
        for key, child in value.items():
            lowered_key = str(key).casefold()
            if any(marker in lowered_key for marker in _PRIVATE_KEY_MARKERS):
                raise TargetSelectionError("goal record contains a secret-like field")
            _public_safe(child, repository=repository)
    elif isinstance(value, list):
        for child in value:
            _public_safe(child, repository=repository)


def _load_goal(repository: Path) -> tuple[dict[str, object], str]:
    path = _regular_relative_file(repository, GOAL_RECORD, role="goal record")
    try:
        encoded = path.read_bytes()
    except OSError as exc:
        raise TargetSelectionError(f"goal record is unavailable: {exc}") from exc
    return _parse_goal_bytes(repository, encoded)


def _parse_goal_bytes(
    repository: Path,
    encoded: bytes,
) -> tuple[dict[str, object], str]:
    """Parse exact goal bytes without substituting the working-tree record."""

    if not encoded or len(encoded) > _MAX_GOAL_BYTES:
        raise TargetSelectionError("goal record byte size is unsafe")
    try:
        loaded = yaml.safe_load(encoded)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise TargetSelectionError("goal record is not valid YAML") from exc
    if not isinstance(loaded, dict):
        raise TargetSelectionError("goal record is not an object")
    _public_safe(loaded, repository=repository)
    return loaded, hashlib.sha256(encoded).hexdigest()


def _git_blob(repository: Path, commit: str, relative: str) -> bytes:
    if re.fullmatch(r"[a-f0-9]{40}", commit) is None:
        raise TargetSelectionError("bound control commit is malformed")
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
        raise TargetSelectionError(f"bound package artifact is unavailable: {relative}")
    return completed.stdout


def _regular_relative_file(repository: Path, relative: str, *, role: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise TargetSelectionError(f"{role} path is unsafe")
    cursor = repository
    metadata: os.stat_result | None = None
    for part in pure.parts:
        cursor = cursor / part
        try:
            metadata = cursor.stat(follow_symlinks=False)
        except OSError as exc:
            raise TargetSelectionError(f"{role} is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise TargetSelectionError(f"{role} path contains a symbolic link")
    if metadata is None or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise TargetSelectionError(f"{role} is not a single-link regular no-follow file")
    return cursor


def _regular_package_file(repository: Path, relative: str | None, *, role: str) -> Path:
    if relative is None:
        raise TargetSelectionError(f"selected contract lacks {role}")
    return _regular_relative_file(repository, relative, role=f"selected contract {role}")


def _declared_artifact_identities(value: object) -> dict[str, str]:
    """Collect package-owned plan, execution, command, and condition identities."""

    identities: dict[str, str] = {}

    def visit(current: object) -> None:
        if isinstance(current, dict):
            for key, child in current.items():
                if isinstance(child, str):
                    sha_key = None
                    if key in {
                        "plan_path",
                        "provider_profile_path",
                        "execution_contract_path",
                        "command_manifest_path",
                        "condition_plan_path",
                    }:
                        sha_key = f"{key[:-5]}_sha256"
                    expected = current.get(sha_key) if sha_key is not None else None
                    if isinstance(expected, str) and _HEX64.fullmatch(expected):
                        previous = identities.setdefault(child, expected)
                        if previous != expected:
                            raise TargetSelectionError(
                                "selected package declares conflicting artifact identities"
                            )
                visit(child)
        elif isinstance(current, list):
            for child in current:
                visit(child)

    visit(value)
    return identities


def _structured_package_document(path: Path) -> Mapping[str, object]:
    try:
        value = yaml.safe_load(path.read_bytes())
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise TargetSelectionError("selected package document is malformed") from exc
    if not isinstance(value, dict):
        raise TargetSelectionError("selected package document is not an object")
    return value


def _validate_bound_package_bytes(
    repository: Path,
    contract: T09ProviderContract,
    *,
    bound_commit: str,
) -> None:
    """Prove package bytes used by a historical target existed in its bound commit."""

    primary: dict[str, str] = {}
    for relative, expected in (
        (contract.plan_path, contract.expected_plan_sha256),
        (contract.provider_profile_path, contract.expected_provider_profile_sha256),
        (contract.command_manifest_path, contract.expected_command_manifest_sha256),
    ):
        if relative is None or expected is None:
            raise TargetSelectionError("selected contract lacks a bound package identity")
        previous = primary.setdefault(relative, expected)
        if previous != expected:
            raise TargetSelectionError("selected contract package identities conflict")

    documents: list[Mapping[str, object]] = []
    for relative in (
        contract.plan_path,
        contract.provider_profile_path,
        contract.execution_contract_path,
        contract.command_manifest_path,
    ):
        if relative is None:
            raise TargetSelectionError("selected contract lacks a required package artifact")
        path = _regular_relative_file(repository, relative, role="bound package artifact")
        documents.append(_structured_package_document(path))

    declared = dict(primary)
    for document in documents:
        for relative, expected in _declared_artifact_identities(document).items():
            previous = declared.setdefault(relative, expected)
            if previous != expected:
                raise TargetSelectionError("selected package artifact identities conflict")

    for relative, expected in sorted(declared.items()):
        path = _regular_relative_file(repository, relative, role="bound package artifact")
        current = path.read_bytes()
        if hashlib.sha256(current).hexdigest() != expected:
            raise TargetSelectionError(f"bound package artifact identity drifted: {relative}")
        if _git_blob(repository, bound_commit, relative) != current:
            raise TargetSelectionError(f"bound package artifact differs from Git: {relative}")


def _selected_package_identity(
    repository: Path,
    contract: T09ProviderContract,
    *,
    bound_commit: str | None = None,
) -> str:
    expected_plan_id = f"PLAN-EXP0001-PILOT-{contract.version}"
    if contract.plan_id != expected_plan_id or contract.provider_profile_id != expected_plan_id:
        raise TargetSelectionError("selected contract plan identity is inconsistent")
    _regular_package_file(repository, contract.plan_path, role="plan")
    _regular_package_file(repository, contract.provider_profile_path, role="runtime profile")
    execution_path = _regular_package_file(
        repository,
        contract.execution_contract_path,
        role="execution contract",
    )
    command_path = _regular_package_file(
        repository,
        contract.command_manifest_path,
        role="command package",
    )
    if contract.expected_command_manifest_sha256 is None or (
        _HEX64.fullmatch(contract.expected_command_manifest_sha256) is None
    ):
        raise TargetSelectionError("selected contract lacks an exact command-package identity")
    if (
        hashlib.sha256(command_path.read_bytes()).hexdigest()
        != contract.expected_command_manifest_sha256
    ):
        raise TargetSelectionError("selected command-package artifact identity drifted")
    try:
        plan = load_provider_plan(repository, contract)
        profile = load_provider_profile(repository, contract)
        package, command_sha256, _source = resolve_registered_command_package(
            repository,
            contract,
        )
    except Exception as exc:
        raise TargetSelectionError(f"selected package artifact identity drifted: {exc}") from exc
    if plan.get("plan_id") != contract.plan_id or profile.get("plan_id") != contract.plan_id:
        raise TargetSelectionError("selected package plan identity drifted")
    if (
        package.get("plan_id") != contract.plan_id
        or command_sha256 != contract.expected_command_manifest_sha256
    ):
        raise TargetSelectionError("selected command-package identity drifted")
    execution_sha256 = package.get("execution_contract_sha256")
    if not isinstance(execution_sha256, str) or _HEX64.fullmatch(execution_sha256) is None:
        raise TargetSelectionError("selected command package lacks execution identity")
    if hashlib.sha256(execution_path.read_bytes()).hexdigest() != execution_sha256:
        raise TargetSelectionError("selected execution-contract identity drifted")
    if bound_commit is not None:
        _validate_bound_package_bytes(
            repository,
            contract,
            bound_commit=bound_commit,
        )
    return command_sha256


def _target_schema_errors(repository: Path, document: Mapping[str, object]) -> list[str]:
    schema = load_json(repository / TARGET_SCHEMA)
    return [
        error.message
        for error in sorted(
            Draft202012Validator(schema).iter_errors(document),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    ]


def resolve_selected_runtime_target(
    repository: Path,
    *,
    explicit_provider_contract: str | None = None,
) -> SelectedRuntimeTarget:
    """Resolve the only active package allowed by exact goal/package state."""

    root = repository.resolve(strict=True)
    goal, goal_sha256 = _load_goal(root)
    return _resolve_selected_runtime_target(
        root,
        goal=goal,
        goal_sha256=goal_sha256,
        explicit_provider_contract=explicit_provider_contract,
        bound_package_commit=None,
        bound_registered_contract_versions=None,
    )


def resolve_selected_runtime_target_from_goal_bytes(
    repository: Path,
    goal_bytes: bytes,
    *,
    explicit_provider_contract: str | None = None,
    bound_package_commit: str,
    bound_registered_contract_versions: frozenset[str],
) -> SelectedRuntimeTarget:
    """Resolve a historical target from exact bound goal and package bytes."""

    root = repository.resolve(strict=True)
    goal, goal_sha256 = _parse_goal_bytes(root, goal_bytes)
    return _resolve_selected_runtime_target(
        root,
        goal=goal,
        goal_sha256=goal_sha256,
        explicit_provider_contract=explicit_provider_contract,
        bound_package_commit=bound_package_commit,
        bound_registered_contract_versions=bound_registered_contract_versions,
    )


def _resolve_selected_runtime_target(
    root: Path,
    *,
    goal: Mapping[str, object],
    goal_sha256: str,
    explicit_provider_contract: str | None,
    bound_package_commit: str | None,
    bound_registered_contract_versions: frozenset[str] | None,
) -> SelectedRuntimeTarget:
    runtime = _required_mapping(goal, "runtime_package")
    science = _required_mapping(goal, "science")
    authority = _required_mapping(goal, "authority")
    if science.get("interpretation_allowed") is not False:
        raise TargetSelectionError("goal record permits scientific interpretation")
    if authority != {
        "repository_permissions": False,
        "category_3": False,
        "current_turn_authority": "external-and-not-present",
        "inferable_from_repository": False,
    }:
        raise TargetSelectionError("goal record contains current or inferable live authority")

    historical = runtime.get("historical_package")
    successor = runtime.get("next_package")
    historical_number = _version_number(historical, field="historical_package")
    successor_number = _version_number(successor, field="next_package")
    assert isinstance(historical, str) and isinstance(successor, str)
    if successor_number != historical_number + 1:
        raise TargetSelectionError("goal next_package is not the exact numerical successor")
    status = runtime.get("next_status")
    if status not in {"not-created", "package-bound-not-authorized"}:
        raise TargetSelectionError("goal next_status is unsupported")
    historical_status = runtime.get("historical_status")
    if not isinstance(historical_status, str) or not historical_status:
        raise TargetSelectionError("goal historical_status is malformed")

    registry = provider_contracts.PROVIDER_CONTRACTS
    if bound_registered_contract_versions is None:
        registered_contract_versions = frozenset(registry)
    else:
        if not bound_registered_contract_versions or any(
            _VERSION.fullmatch(version) is None for version in bound_registered_contract_versions
        ):
            raise TargetSelectionError("bound provider-contract registry is malformed")
        registered_contract_versions = bound_registered_contract_versions
    historical_contract = registry.get(historical)
    if (
        historical not in registered_contract_versions
        or historical_contract is None
        or historical_contract.version != historical
    ):
        raise TargetSelectionError("goal historical_package is not exactly registered")
    successor_contract = registry.get(successor)
    if status == "not-created":
        if successor in registered_contract_versions:
            raise TargetSelectionError("goal says successor is not-created but it is registered")
        selected_contract = historical_contract
        selected_status = historical_status
    else:
        if (
            successor not in registered_contract_versions
            or successor_contract is None
            or successor_contract.version != successor
        ):
            raise TargetSelectionError("package-bound successor is not exactly registered")
        try:
            effect_identity = validate_package_effect_registration(root, successor_contract)
        except ValueError as exc:
            raise TargetSelectionError(
                "package-bound successor effect declaration is invalid"
            ) from exc
        if effect_identity is None:
            raise TargetSelectionError(
                "package-bound successor lacks its package-specific effect declaration"
            )
        selected_contract = successor_contract
        selected_status = status

    if explicit_provider_contract is not None:
        _version_number(explicit_provider_contract, field="explicit provider contract")
        if explicit_provider_contract != selected_contract.version:
            raise TargetSelectionError(
                "explicit provider contract is incompatible with goal-derived package state"
            )
        source = EXPLICIT_SOURCE
    else:
        source = GOAL_SOURCE

    command_sha256 = _selected_package_identity(
        root,
        selected_contract,
        bound_commit=bound_package_commit,
    )
    target = SelectedRuntimeTarget(
        source=source,
        historical_contract_version=historical,
        successor_contract_version=successor,
        successor_status=status,
        selected_contract=selected_contract,
        selected_plan_id=selected_contract.plan_id,
        selected_command_package_sha256=command_sha256,
        selected_package_status=selected_status,
        goal_record_sha256=goal_sha256,
    )
    errors = _target_schema_errors(root, target.to_document())
    if errors:
        raise TargetSelectionError(f"selected-runtime target schema failed: {errors[0]}")
    return target


def validate_selected_runtime_target(
    repository: Path,
    target: SelectedRuntimeTarget,
) -> SelectedRuntimeTarget:
    """Re-resolve and compare a caller-supplied target instead of trusting it."""

    explicit = target.selected_contract.version if target.source == EXPLICIT_SOURCE else None
    if target.source not in {GOAL_SOURCE, EXPLICIT_SOURCE}:
        raise TargetSelectionError("selected-runtime target source is unsupported")
    expected = resolve_selected_runtime_target(
        repository,
        explicit_provider_contract=explicit,
    )
    if expected != target:
        raise TargetSelectionError("selected-runtime target differs from goal/package state")
    return expected


def validate_selected_runtime_target_document(
    repository: Path,
    document: Mapping[str, object],
) -> SelectedRuntimeTarget:
    """Validate a serialized target and return the exact re-resolved typed value."""

    root = repository.resolve(strict=True)
    errors = _target_schema_errors(root, document)
    if errors:
        raise TargetSelectionError(f"selected-runtime target schema failed: {errors[0]}")
    source = document.get("source")
    version = document.get("selected_provider_contract_version")
    explicit = version if source == EXPLICIT_SOURCE and isinstance(version, str) else None
    target = resolve_selected_runtime_target(root, explicit_provider_contract=explicit)
    if target.to_document() != dict(document):
        raise TargetSelectionError("serialized target differs from goal/package state")
    return target


def validate_bound_selected_runtime_target_document(
    repository: Path,
    document: Mapping[str, object],
    *,
    goal_bytes: bytes,
    bound_package_commit: str,
    bound_registered_contract_versions: frozenset[str],
) -> SelectedRuntimeTarget:
    """Validate a serialized target against its receipt-bound historical goal."""

    root = repository.resolve(strict=True)
    errors = _target_schema_errors(root, document)
    if errors:
        raise TargetSelectionError(f"selected-runtime target schema failed: {errors[0]}")
    source = document.get("source")
    version = document.get("selected_provider_contract_version")
    explicit = version if source == EXPLICIT_SOURCE and isinstance(version, str) else None
    if source not in {GOAL_SOURCE, EXPLICIT_SOURCE}:
        raise TargetSelectionError("selected-runtime target source is unsupported")
    target = resolve_selected_runtime_target_from_goal_bytes(
        root,
        goal_bytes,
        explicit_provider_contract=explicit,
        bound_package_commit=bound_package_commit,
        bound_registered_contract_versions=bound_registered_contract_versions,
    )
    if target.to_document() != dict(document):
        raise TargetSelectionError("serialized target differs from bound goal/package state")
    return target
