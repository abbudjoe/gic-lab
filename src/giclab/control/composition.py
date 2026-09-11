"""Typed offline composition of one exact T09 provider contract."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from giclab.control.registry_validation import (
    LifecycleLoader,
    resolve_registered_command_package,
    validate_registry_completeness,
)
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness import t09_pragmatic_provider as pragmatic_provider
from giclab.harness.t09_candidate_inputs import CandidateSourceSnapshot
from giclab.harness.t09_provider_contracts import (
    CleanupFamily,
    CommandPackageFamily,
    MetadataPolicy,
    ProviderSelectorPolicy,
    T09ProviderContract,
    load_provider_profile,
)

COMPOSITION_SCHEMA_VERSION: Final = "1.0.0"
_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_PRIVACY_SOURCES: Final = (
    "containers/sira-smoke/pragmatic/t09_preflight.py",
    "containers/sira-smoke/pragmatic/t09_remote_runner.py",
    "containers/sira-smoke/pragmatic/t09_finalizer_projection.py",
)
_DOWNSTREAM_SOURCES: Final = (
    "src/giclab/harness/t09_sira_pilot.py",
    "containers/sira-smoke/pragmatic/t09_freeze_commands.py",
    "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py",
)
_AUTHORIZATION_SCHEMA: Final = "schemas/t09-model-metadata-receipt.schema.json"
_CONTROL_BINDING_SCHEMA: Final = "schemas/t09-control-receipt-bindings.schema.json"
_TARGET_SCHEMA: Final = "schemas/t09-control-target.schema.json"


class CompositionError(ValueError):
    """The deterministic control plane could not be composed."""


@dataclass(frozen=True, slots=True)
class CompositionReceipt:
    schema_version: str
    repository_commit: str
    repository_tree: str
    provider_contract_version: str
    provider_contract_sha256: str
    provider_profile_sha256: str
    lifecycle_sha256: str
    execution_contract_sha256: str | None
    command_package_sha256: str | None
    pair_diff_sha256s: tuple[str, ...]
    metadata_policy: str
    replacement_policy: str
    cleanup_family: str
    command_package_family: str
    downstream_source_contract_sha256: str
    privacy_contract_sha256: str
    budget_envelope_sha256: str
    evidence_identity_sha256: str
    authorization_schema_sha256: str
    control_binding_schema_sha256: str
    target_schema_sha256: str
    registry_receipt_sha256: str
    version_lint_receipt_sha256: str
    blockers: tuple[str, ...]
    static_composition_valid: bool
    ready_for_shadow: bool
    ready_for_authenticated_preflight: bool

    def to_document(self) -> dict[str, object]:
        document = asdict(self)
        document["pair_diff_sha256s"] = list(self.pair_diff_sha256s)
        document["blockers"] = list(self.blockers)
        document["semantic_sha256"] = _canonical_sha256(document)
        return document


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


def _hash_source_map(repository: Path, paths: tuple[str, ...]) -> str:
    values: dict[str, str] = {}
    for relative in paths:
        path = repository / relative
        if not path.is_file() or path.is_symlink():
            raise CompositionError(f"required composition source is unavailable: {relative}")
        values[relative] = _file_sha256(path)
    return _canonical_sha256(values)


def _registry_entry(
    registry_receipt: Mapping[str, object],
    *,
    version: str,
) -> Mapping[str, object]:
    contracts = registry_receipt.get("contracts")
    if not isinstance(contracts, list):
        raise CompositionError("registry receipt contract matrix is malformed")
    matches = [
        entry for entry in contracts if isinstance(entry, dict) and entry.get("version") == version
    ]
    if len(matches) != 1 or matches[0].get("complete") is not True:
        raise CompositionError("selected contract is incomplete in the registry receipt")
    return matches[0]


def _validate_cleanup_profile(
    profile: Mapping[str, object],
    *,
    contract: T09ProviderContract,
) -> None:
    if contract.capabilities.cleanup_family is not CleanupFamily.EMPIRICAL_PREFIX:
        return
    reconciliation = profile.get("cleanup_export_reconciliation")
    if not isinstance(reconciliation, dict) or reconciliation.get("phases") != [
        "prefreeze-zero-attempt",
        "postfreeze-zero-attempt",
        "empirical-prefix",
    ]:
        raise CompositionError("empirical-prefix cleanup contract is incomplete")
    if reconciliation.get("handoff_policy") != "immutable-terminal-receipt-reused-on-resume":
        raise CompositionError("cleanup resume contract drifted")


def _validate_command_package(
    command_package: Mapping[str, object],
    *,
    contract: T09ProviderContract,
) -> tuple[str, tuple[str, ...]]:
    execution_sha256 = command_package.get("execution_contract_sha256")
    if not isinstance(execution_sha256, str) or _HEX64.fullmatch(execution_sha256) is None:
        raise CompositionError("command package lacks an execution-contract hash")
    manifests = command_package.get("manifests")
    if not isinstance(manifests, list) or len(manifests) != len(contract.run_ids):
        raise CompositionError("command package attempt matrix is incomplete")
    if (
        tuple(item.get("run_id") if isinstance(item, dict) else None for item in manifests)
        != contract.run_ids
    ):
        raise CompositionError("command package attempt order drifted")
    pair_diffs = command_package.get("pair_diffs")
    if not isinstance(pair_diffs, list) or len(pair_diffs) != 2:
        raise CompositionError("command package pair-diff matrix is incomplete")
    pair_hashes: list[str] = []
    for pair_diff in pair_diffs:
        if not isinstance(pair_diff, dict) or pair_diff.get("valid") is not True:
            raise CompositionError("command package contains an invalid pair diff")
        pair_hashes.append(_canonical_sha256(pair_diff))
    selector = command_package.get("local_finalizer_qualification_selector")
    explicit_selector = (
        contract.capabilities.provider_selector_policy is ProviderSelectorPolicy.EXPLICIT
    )
    expected_selector = {"argument": "--provider-contract", "value": contract.version}
    if explicit_selector and selector != expected_selector:
        raise CompositionError("local-finalizer selector contract is incomplete")
    if not explicit_selector and selector is not None:
        raise CompositionError("legacy command package unexpectedly declares a selector")
    metadata_required = (
        contract.capabilities.metadata_policy is MetadataPolicy.LOCAL_PRELAUNCH_RECEIPT
    )
    if metadata_required and (
        command_package.get("model_metadata_receipt_required") is not True
        or command_package.get("model_metadata_receipt_replay_allowed") is not False
        or command_package.get("model_metadata_request_count_total") != 1
    ):
        raise CompositionError("command package metadata policy drifted")
    return execution_sha256, tuple(pair_hashes)


def compose_control_plane(
    repository: Path,
    *,
    contract: T09ProviderContract,
    registry_receipt: Mapping[str, object] | None = None,
    version_lint_receipt: Mapping[str, object] | None = None,
    lifecycle_loader: LifecycleLoader | None = None,
    source_inputs: CandidateSourceSnapshot | None = None,
) -> dict[str, object]:
    """Compose every deterministic dependency without accepting an effect adapter."""

    root = repository.resolve(strict=True)
    selected_lifecycle_loader = lifecycle_loader or pragmatic_provider.load_campaign_lifecycle
    lint = (
        dict(version_lint_receipt)
        if version_lint_receipt is not None
        else validate_active_version_dispatch(root, source_inputs=source_inputs)
    )
    if lint.get("complete") is not True:
        raise CompositionError("active-version dispatch lint is incomplete")
    registry = (
        dict(registry_receipt)
        if registry_receipt is not None
        else validate_registry_completeness(
            root,
            lifecycle_loader=selected_lifecycle_loader,
            source_inputs=source_inputs,
        )
    )
    if registry.get("complete") is not True:
        raise CompositionError("provider registry completeness failed")
    _registry_entry(registry, version=contract.version)
    try:
        profile = load_provider_profile(root, contract)
        lifecycle = selected_lifecycle_loader(root, contract=contract)
    except Exception as exc:
        raise CompositionError(f"campaign lifecycle composition failed: {exc}") from exc
    if lifecycle.contract != contract:
        raise CompositionError("campaign lifecycle resolved a different contract")
    _validate_cleanup_profile(profile, contract=contract)

    execution_sha256: str | None = None
    command_sha256: str | None = None
    pair_hashes: tuple[str, ...] = ()
    if contract.capabilities.command_package_family is CommandPackageFamily.AUTONOMOUS:
        try:
            command_package, command_sha256, _source = resolve_registered_command_package(
                root, contract, source_inputs=source_inputs
            )
        except Exception as exc:
            raise CompositionError(f"command package composition failed: {exc}") from exc
        execution_sha256, pair_hashes = _validate_command_package(
            command_package,
            contract=contract,
        )
        if contract.execution_contract_path is None:
            raise CompositionError("autonomous contract lacks an execution-contract path")
        execution_path = root / contract.execution_contract_path
        if execution_path.is_file() and _file_sha256(execution_path) == execution_sha256:
            pass
        elif contract.version not in {"V8"}:  # giclab-version-lint: historical-identity
            raise CompositionError("execution-contract bytes drifted")

    commit, tree = (
        _git_identity(root) if source_inputs is None else source_inputs.package_identity(root)
    )
    contract_document = asdict(contract)
    lifecycle_document = {
        "family": contract.capabilities.lifecycle_family.value,
        "limits": asdict(lifecycle.limits),
        "max_instances": lifecycle.max_instances,
        "max_launches": lifecycle.max_launches,
        "persistent_filesystems": lifecycle.persistent_filesystems,
    }
    budget_document = {
        "prior_t09_cost_usd": contract.prior_t09_cost_usd,
        "preflight_lambda_cost_cap_usd": contract.preflight_lambda_cost_cap_usd,
        "campaign_lambda_cost_cap_usd": contract.campaign_lambda_cost_cap_usd,
        "campaign_openai_cost_cap_usd": contract.campaign_openai_cost_cap_usd,
        "campaign_aggregate_cost_cap_usd": contract.campaign_aggregate_cost_cap_usd,
        "cumulative_t09_cost_cap_usd": contract.cumulative_t09_cost_cap_usd,
        "lifecycle": lifecycle_document,
    }
    evidence_document = {
        "archive_id": contract.evidence_archive_id,
        "stage_id": contract.evidence_stage_id,
        "control_root": contract.control_root_name,
        "host_run_id": contract.host_run_id,
        "run_ids": contract.run_ids,
        "evaluator_run_ids": contract.evaluator_run_ids,
        "image_qualification_ids": contract.image_qualification_ids,
        "local_finalizer_qualification_id": contract.local_finalizer_qualification_id,
    }
    blockers = ["current-turn-live-authority-is-external-and-not-present"]
    if contract.version == "V16":  # giclab-version-lint: historical-identity
        blockers.append("historical-v16-prelaunch-authority-is-consumed")
    receipt = CompositionReceipt(
        schema_version=COMPOSITION_SCHEMA_VERSION,
        repository_commit=commit,
        repository_tree=tree,
        provider_contract_version=contract.version,
        provider_contract_sha256=_canonical_sha256(contract_document),
        provider_profile_sha256=contract.expected_provider_profile_sha256,
        lifecycle_sha256=_canonical_sha256(lifecycle_document),
        execution_contract_sha256=execution_sha256,
        command_package_sha256=command_sha256,
        pair_diff_sha256s=pair_hashes,
        metadata_policy=contract.capabilities.metadata_policy.value,
        replacement_policy=contract.capabilities.replacement_policy.value,
        cleanup_family=contract.capabilities.cleanup_family.value,
        command_package_family=contract.capabilities.command_package_family.value,
        downstream_source_contract_sha256=_hash_source_map(root, _DOWNSTREAM_SOURCES),
        privacy_contract_sha256=_hash_source_map(root, _PRIVACY_SOURCES),
        budget_envelope_sha256=_canonical_sha256(budget_document),
        evidence_identity_sha256=_canonical_sha256(evidence_document),
        authorization_schema_sha256=_file_sha256(root / _AUTHORIZATION_SCHEMA),
        control_binding_schema_sha256=_file_sha256(root / _CONTROL_BINDING_SCHEMA),
        target_schema_sha256=_file_sha256(root / _TARGET_SCHEMA),
        registry_receipt_sha256=str(registry["semantic_sha256"]),
        version_lint_receipt_sha256=str(lint["semantic_sha256"]),
        blockers=tuple(blockers),
        static_composition_valid=True,
        ready_for_shadow=(
            contract.capabilities.command_package_family is CommandPackageFamily.AUTONOMOUS
        ),
        ready_for_authenticated_preflight=False,
    )
    return receipt.to_document()
