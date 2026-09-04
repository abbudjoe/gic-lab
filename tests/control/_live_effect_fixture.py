from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _synthetic_successor import (
    commit_repository,
    install_synthetic_registry,
    materialize_synthetic_successor,
    synthetic_contract,
)

from giclab.control.effects import (
    EffectAuthorizationContext,
    EffectExecutionMode,
    HeldEffectSource,
    HeldTransactionRoot,
    LoadedPackageEffects,
    ValidatedLiveEffectAuthority,
    hold_package_effect_registration,
    hold_transaction_root,
    load_registered_package_effects,
    project_live_authority_overlay,
    validate_external_live_effect_authority,
)
from giclab.control.live_conformance import _copy_working_repository
from giclab.control.proofs import ValidatedShadowRehearsal
from giclab.harness.t09_provider_contracts import T09ProviderContract


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


@dataclass(slots=True)
class RuntimePackage:
    repository: Path
    contract: T09ProviderContract
    held_source: HeldEffectSource
    held_root: HeldTransactionRoot
    context: EffectAuthorizationContext
    authority: ValidatedLiveEffectAuthority
    overlay_path: Path
    rehearsal: ValidatedShadowRehearsal | None = None

    def load(self) -> LoadedPackageEffects:
        return load_registered_package_effects(
            self.repository,
            self.contract,
            authorization_context=self.context,
            authority=self.authority,
            held_source=self.held_source,
        )


def materialize_runtime_package(
    source: Path,
    root: Path,
    *,
    effect_source: bytes | None = None,
    prepare_execution: bool = False,
    registry_monkeypatch: Any | None = None,
) -> RuntimePackage:
    external_root = root.resolve(strict=True)
    repository = external_root / "repository"
    _copy_working_repository(source, repository)
    identities = materialize_synthetic_successor(source, repository)
    if effect_source is not None:
        effect_path = repository / str(identities["effect_path"])
        effect_path.write_bytes(effect_source)
        identities["effect_bytes"] = len(effect_source)
        identities["effect_sha256"] = hashlib.sha256(effect_source).hexdigest()
    commit, _tree = commit_repository(repository)
    contract = synthetic_contract(identities, source_commit=commit)
    rehearsal = None
    control_binding_semantic_sha256 = "a" * 64
    if prepare_execution:
        if registry_monkeypatch is None:
            raise ValueError("prepared synthetic execution requires an isolated registry patch")
        install_synthetic_registry(registry_monkeypatch, contract)
        from _category3_test_support import validated_rehearsal

        rehearsal = validated_rehearsal(repository.as_posix(), contract)
        control_binding_semantic_sha256 = rehearsal.staging.semantic_sha256
    held_source = hold_package_effect_registration(repository, contract)
    assert held_source is not None
    transaction_root = external_root / "private-transaction"
    transaction_root.mkdir(mode=0o700)
    held_root = hold_transaction_root(transaction_root)
    prefix = contract.authorization_prefix
    assert isinstance(prefix, str)
    reference = prefix + "TEST-" + hashlib.sha256(commit.encode()).hexdigest()[:24]
    current_turn_scope = "T09-PR14-TEST-AUTHORITY"
    overlay = project_live_authority_overlay(
        repository,
        contract,
        held_transaction_root=held_root,
        effect_implementation=held_source.identity,
        control_binding_semantic_sha256=control_binding_semantic_sha256,
        external_authorization_reference=reference,
        current_turn_scope=current_turn_scope,
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
    )
    overlay_path = external_root / "private-authorization-overlay.json"
    overlay_path.write_bytes(canonical_bytes(overlay))
    overlay_path.chmod(0o600)
    context, authority = validate_external_live_effect_authority(
        repository,
        contract,
        overlay_path=overlay_path,
        held_transaction_root=held_root,
        effect_implementation=held_source.identity,
        control_binding_semantic_sha256=control_binding_semantic_sha256,
        current_turn_scope=current_turn_scope,
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
    )
    return RuntimePackage(
        repository=repository,
        contract=contract,
        held_source=held_source,
        held_root=held_root,
        context=context,
        authority=authority,
        overlay_path=overlay_path,
        rehearsal=rehearsal,
    )
