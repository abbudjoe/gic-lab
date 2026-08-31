"""Prove that every central provider contract resolves through every consumer."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

from giclab.control.contracts import project_contract_capabilities
from giclab.harness.t09_pragmatic_provider import CampaignLifecycle, load_campaign_lifecycle
from giclab.harness.t09_provider_contracts import (
    PROVIDER_CONTRACTS,
    CommandPackageFamily,
    ControlRootPolicy,
    MetadataPolicy,
    ProviderSelectorPolicy,
    T09ProviderContract,
    load_provider_plan,
    load_provider_profile,
)
from giclab.harness.t09_sira_pilot import (
    command_argv_sha256,
    load_execution_contract,
)

REGISTRY_SCHEMA_VERSION: Final = "1.0.0"
REGISTRY_SOURCE: Final = "src/giclab/harness/t09_provider_contracts.py"
_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")

LifecycleLoader = Callable[..., CampaignLifecycle]


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_identity(repository: Path) -> tuple[str, str]:
    environment = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    identities: list[str] = []
    for revision in ("HEAD", "HEAD^{tree}"):
        completed = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", revision],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=10,
        )
        value = completed.stdout.decode("ascii", "ignore").strip()
        identities.append(value if completed.returncode == 0 and len(value) == 40 else "unknown")
    return identities[0], identities[1]


def _git_blob(repository: Path, commit: str, relative_path: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository), "show", f"{commit}:{relative_path}"],
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
    if completed.returncode != 0 or not completed.stdout:
        raise ValueError("registered historical source blob is unavailable")
    return completed.stdout


def _json_document(encoded: bytes, *, context: str) -> dict[str, object]:
    try:
        value = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{context} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{context} is not an object")
    return value


def _registered_document_bytes(
    repository: Path,
    contract: T09ProviderContract,
    relative_path: str,
    *,
    expected_plan_id: str,
    expected_sha256: str | None = None,
) -> tuple[bytes, str]:
    current = (repository / relative_path).read_bytes()
    current_document = _json_document(current, context="registered document")
    current_matches = current_document.get("plan_id") == expected_plan_id and (
        expected_sha256 is None or hashlib.sha256(current).hexdigest() == expected_sha256
    )
    if current_matches:
        return current, "working-tree"
    historical = _git_blob(repository, contract.source_commit, relative_path)
    historical_document = _json_document(historical, context="historical registered document")
    if historical_document.get("plan_id") != expected_plan_id or (
        expected_sha256 is not None and hashlib.sha256(historical).hexdigest() != expected_sha256
    ):
        raise ValueError("registered document cannot be resolved from its source identity")
    return historical, contract.source_commit


def _consumer_pass(**details: object) -> dict[str, object]:
    return {"status": "passed", **details}


def _consumer_na(*, reason: str) -> dict[str, object]:
    return {"status": "not-applicable", "reason": reason}


def resolve_registered_command_package(
    repository: Path,
    contract: T09ProviderContract,
) -> tuple[dict[str, object], str, str]:
    if contract.command_manifest_path is None:
        raise ValueError("autonomous contract lacks command manifest path")
    encoded, source = _registered_document_bytes(
        repository,
        contract,
        contract.command_manifest_path,
        expected_plan_id=contract.plan_id,
    )
    document = _json_document(encoded, context="registered command manifest")
    manifests = document.get("manifests")
    if not isinstance(manifests, list) or len(manifests) != len(contract.run_ids):
        raise ValueError("command manifest attempt count drifted")
    observed_run_ids: list[str] = []
    for manifest in manifests:
        if not isinstance(manifest, dict):
            raise ValueError("command manifest entry is malformed")
        run_id = manifest.get("run_id")
        argv = manifest.get("argv")
        if (
            not isinstance(run_id, str)
            or not isinstance(argv, list)
            or not all(isinstance(item, str) for item in argv)
        ):
            raise ValueError("command manifest identity or argv is malformed")
        if manifest.get("argv_sha256") != command_argv_sha256(argv):
            raise ValueError("command manifest argv hash drifted")
        observed_run_ids.append(run_id)
    if tuple(observed_run_ids) != contract.run_ids:
        raise ValueError("command manifest order differs from the provider contract")
    pair_diffs = document.get("pair_diffs")
    if (
        not isinstance(pair_diffs, list)
        or len(pair_diffs) != 2
        or any(not isinstance(item, dict) or item.get("valid") is not True for item in pair_diffs)
    ):
        raise ValueError("command manifest pair diffs are invalid")
    return document, hashlib.sha256(encoded).hexdigest(), source


def _validate_one_contract(
    repository: Path,
    contract: T09ProviderContract,
    *,
    lifecycle_loader: LifecycleLoader,
    disabled_consumers: frozenset[str],
) -> dict[str, object]:
    consumers: dict[str, dict[str, object]] = {}
    errors: list[str] = []

    def run(
        name: str,
        callback: Callable[[], dict[str, object]],
        *,
        applicable: bool = True,
        not_applicable_reason: str = "capability not declared",
    ) -> None:
        if not applicable:
            consumers[name] = _consumer_na(reason=not_applicable_reason)
            return
        if name in disabled_consumers:
            message = f"{name}: applicable consumer is unavailable"
            consumers[name] = {"status": "failed", "error": message}
            errors.append(message)
            return
        try:
            consumers[name] = callback()
        except Exception as exc:
            message = f"{name}: {type(exc).__name__}: {exc}"
            consumers[name] = {"status": "failed", "error": message}
            errors.append(message)

    run(
        "provider_profile_loading",
        lambda: _consumer_pass(
            plan_id=load_provider_profile(repository, contract)["plan_id"],
            sha256=contract.expected_provider_profile_sha256,
        ),
    )
    run(
        "provider_plan_loading",
        lambda: _consumer_pass(
            plan_id=load_provider_plan(repository, contract)["plan_id"],
            sha256=contract.expected_plan_sha256,
        ),
    )

    def lifecycle() -> dict[str, object]:
        loaded = lifecycle_loader(repository, contract=contract)
        if loaded.contract != contract:
            raise ValueError("lifecycle returned a different provider contract")
        return _consumer_pass(family=contract.capabilities.lifecycle_family.value)

    run("campaign_lifecycle_loading", lifecycle)
    run(
        "metadata_policy_resolution",
        lambda: _consumer_pass(policy=contract.capabilities.metadata_policy.value),
        applicable=contract.capabilities.metadata_policy is not MetadataPolicy.NONE,
    )
    run(
        "replacement_policy_resolution",
        lambda: _consumer_pass(policy=contract.capabilities.replacement_policy.value),
        applicable=contract.max_launch_count > 1,
    )
    run(
        "cleanup_family_resolution",
        lambda: _consumer_pass(family=contract.capabilities.cleanup_family.value),
    )
    run(
        "command_package_family_resolution",
        lambda: _consumer_pass(family=contract.capabilities.command_package_family.value),
    )

    package: dict[str, object] | None = None

    def command_manifest() -> dict[str, object]:
        nonlocal package
        package, sha256, source = resolve_registered_command_package(repository, contract)
        return _consumer_pass(
            sha256=sha256,
            attempt_count=len(contract.run_ids),
            source=source,
        )

    autonomous = contract.capabilities.command_package_family is CommandPackageFamily.AUTONOMOUS
    run(
        "command_manifest_loading",
        command_manifest,
        applicable=autonomous,
    )

    def execution_contract() -> dict[str, object]:
        nonlocal package
        if package is None:
            package, _sha256, _source = resolve_registered_command_package(repository, contract)
        expected = package.get("execution_contract_sha256")
        if not isinstance(expected, str) or _HEX64.fullmatch(expected) is None:
            raise ValueError("command package lacks execution-contract hash")
        if contract.execution_contract_path is None:
            raise ValueError("autonomous contract lacks execution-contract path")
        encoded, source = _registered_document_bytes(
            repository,
            contract,
            contract.execution_contract_path,
            expected_plan_id=contract.plan_id,
            expected_sha256=expected,
        )
        document = _json_document(encoded, context="registered execution contract")
        if document.get("schema_version") == "0.4.0":
            attempts = document.get("attempts")
            if (
                not isinstance(attempts, list)
                or tuple(
                    item.get("run_id") if isinstance(item, dict) else None for item in attempts
                )
                != contract.run_ids
            ):
                raise ValueError("historical execution contract attempt identities drifted")
            return _consumer_pass(
                sha256=expected,
                attempt_count=len(attempts),
                loader="historical-0.4",
                source=source,
            )
        if source != "working-tree":
            raise ValueError("typed execution contract unexpectedly requires historical source")
        loaded = load_execution_contract(
            repository / contract.execution_contract_path,
            expected_sha256=expected,
        )
        if (
            loaded.plan_id != contract.plan_id
            or loaded.provider_contract_version != contract.version
        ):
            raise ValueError("execution contract resolves to another provider contract")
        return _consumer_pass(
            sha256=expected,
            attempt_count=len(loaded.attempts),
            loader="typed-current",
            source=source,
        )

    run("execution_contract_loading", execution_contract, applicable=autonomous)

    def finalizer_selector() -> dict[str, object]:
        nonlocal package
        if contract.local_finalizer_qualification_id is None:
            raise ValueError("local finalizer identity is unavailable")
        if package is None and autonomous:
            package, _sha256, _source = resolve_registered_command_package(repository, contract)
        selector = package.get("local_finalizer_qualification_selector") if package else None
        explicit = contract.capabilities.provider_selector_policy is ProviderSelectorPolicy.EXPLICIT
        if explicit and selector != {
            "argument": "--provider-contract",
            "value": contract.version,
        }:
            raise ValueError("explicit local-finalizer selector is missing")
        if not explicit and selector is not None:
            raise ValueError("legacy command package unexpectedly declares a selector")
        return _consumer_pass(
            qualification_id=contract.local_finalizer_qualification_id,
            selector_policy=contract.capabilities.provider_selector_policy.value,
        )

    run(
        "local_finalizer_selector_resolution",
        finalizer_selector,
        applicable=contract.local_finalizer_qualification_id is not None,
    )

    def image_qualification() -> dict[str, object]:
        qualification = contract.active_image_qualification_id
        if qualification is None:
            raise ValueError("active image qualification is unavailable")
        contract.validate_image_qualification(
            plan_id=contract.plan_id,
            host_run_id=contract.host_run_id,
            qualification_id=qualification,
        )
        return _consumer_pass(qualification_id=qualification)

    run(
        "image_qualification_identity",
        image_qualification,
        applicable=contract.active_image_qualification_id is not None,
    )

    def owner_cleanup() -> dict[str, object]:
        contract.validate_owner(
            plan_id=contract.plan_id,
            host_run_id=contract.host_run_id,
            instance_name=contract.instance_name,
        )
        return _consumer_pass(owner_bound=True)

    run("provider_owner_cleanup_identity", owner_cleanup)
    run(
        "evidence_archive_stage_identity",
        lambda: _consumer_pass(
            archive_id=contract.evidence_archive_id,
            stage_id=contract.evidence_stage_id,
        ),
    )

    def control_root() -> dict[str, object]:
        expected = (
            f"pilot-{contract.version.lower()}"
            if contract.capabilities.control_root_policy is ControlRootPolicy.VERSIONED
            else "pilot-v7"
        )
        if contract.control_root_name != expected:
            raise ValueError("control-root projection drifted")
        return _consumer_pass(control_root=expected)

    run("control_root_identity", control_root)
    run(
        "state_capsule_projection",
        lambda: _consumer_pass(projection=project_contract_capabilities(contract)),
    )
    return {
        "version": contract.version,
        "plan_id": contract.plan_id,
        "declared_capabilities": project_contract_capabilities(contract),
        "consumers": consumers,
        "errors": errors,
        "complete": not errors,
    }


def validate_registry_completeness(
    repository: Path,
    *,
    contracts: Mapping[str, T09ProviderContract] = PROVIDER_CONTRACTS,
    lifecycle_loader: LifecycleLoader = load_campaign_lifecycle,
    disabled_consumers: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """Return one deterministic, public-safe per-contract consumer matrix."""

    root = repository.resolve(strict=True)
    entries = [
        _validate_one_contract(
            root,
            contract,
            lifecycle_loader=lifecycle_loader,
            disabled_consumers=disabled_consumers,
        )
        for _version, contract in sorted(contracts.items(), key=lambda item: int(item[0][1:]))
    ]
    errors: list[str] = []
    for entry in entries:
        entry_errors = entry["errors"]
        if not isinstance(entry_errors, list):  # pragma: no cover - local constructor invariant
            raise TypeError("registry entry errors are malformed")
        errors.extend(
            f"{entry['version']}: {error}" for error in entry_errors if isinstance(error, str)
        )
    commit, tree = _git_identity(root)
    receipt: dict[str, object] = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "repository_commit": commit,
        "repository_tree": tree,
        "registry_source_sha256": _file_sha256(root / REGISTRY_SOURCE),
        "contract_count": len(entries),
        "contracts": entries,
        "errors": errors,
        "complete": not errors and len(entries) == len(contracts),
    }
    receipt["semantic_sha256"] = _canonical_sha256(receipt)
    return receipt
