from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from _synthetic_successor import (
    commit_repository,
    materialize_synthetic_successor,
    synthetic_contract,
)

from giclab.control.effects import (
    EFFECT_PROTOCOL_VERSION,
    EffectAuthorityGrant,
    EffectAuthorityKind,
    EffectAuthorizationContext,
    EffectExecutionMode,
    EffectImplementationIdentity,
    load_registered_package_effects,
    mint_shadow_effect_authority,
    validate_package_effect_registration,
)
from giclab.control.live_conformance import _copy_working_repository
from giclab.control.production import build_production_adapter_assembly
from giclab.control.shadow_effects import DeterministicLowLevelEffects, ShadowFaultPlan
from giclab.harness.t09_provider_contracts import (
    PackageEffectRegistration,
    T09ProviderContract,
    T09ProviderContractError,
)

ROOT = Path(__file__).resolve().parents[2]


def _load_grant_module(path: Path, identity: EffectImplementationIdentity) -> ModuleType:
    name = "giclab_test_package_grant_" + identity.sha256
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def package_fixture(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[
    Path,
    T09ProviderContract,
    EffectImplementationIdentity,
    EffectAuthorizationContext,
    EffectAuthorityGrant,
]:
    repository = tmp_path_factory.mktemp("package-effect-loader") / "repository"
    _copy_working_repository(ROOT, repository)
    identities = materialize_synthetic_successor(ROOT, repository)
    commit, tree = commit_repository(repository)
    contract = synthetic_contract(identities, source_commit=commit)
    identity = validate_package_effect_registration(repository, contract)
    assert identity is not None
    probe = DeterministicLowLevelEffects(
        repository=repository,
        contract=contract,
        fault_plan=ShadowFaultPlan("live-shaped-conformance"),
        fixed_tick=2000,
    )
    context = EffectAuthorizationContext(
        authority_kind=EffectAuthorityKind.LIVE_AUTHORIZED,
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
        control_commit=commit,
        control_tree=tree,
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        plan_sha256=contract.expected_plan_sha256,
        command_package_sha256=cast(str, contract.expected_command_manifest_sha256),
        control_binding_semantic_sha256="a" * 64,
        effect_implementation=identity,
        transaction_root_identity=probe.transaction_root_identity(),
        external_authorization_reference="AUTH-TEST-EXTERNAL-VALIDATOR",
        external_authorization_source_sha256=hashlib.sha256(
            b"runtime-created-external-test-authorization"
        ).hexdigest(),
    )
    module = _load_grant_module(repository / identity.path, identity)
    grant_type = module.PackageEffectGrant
    grant = cast(EffectAuthorityGrant, grant_type(context))
    return repository, contract, identity, context, grant


def test_exact_package_effect_factory_loads_and_builds_production_assembly(
    package_fixture: tuple[
        Path,
        T09ProviderContract,
        EffectImplementationIdentity,
        EffectAuthorizationContext,
        EffectAuthorityGrant,
    ],
) -> None:
    repository, contract, identity, context, grant = package_fixture
    loaded = load_registered_package_effects(
        repository,
        contract,
        authorization_context=context,
        authority=grant,
    )
    assert loaded.identity == identity
    assert loaded.effects.implementation_identity() == identity
    assert loaded.effects.provider_contract_version == contract.version
    world = build_production_adapter_assembly(
        repository,
        contract,
        low_level_effects=loaded.effects,
        authorization_context=context,
        authority=grant,
    )
    assert world.contract == contract
    assert type(world).__name__ == "ProductionCategory3World"


def test_shadow_grant_cannot_instantiate_package_live_effects(
    package_fixture: tuple[
        Path,
        T09ProviderContract,
        EffectImplementationIdentity,
        EffectAuthorizationContext,
        EffectAuthorityGrant,
    ],
) -> None:
    repository, contract, identity, context, _grant = package_fixture
    shadow_context = EffectAuthorizationContext(
        authority_kind=EffectAuthorityKind.SHADOW_ONLY,
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
        control_commit=context.control_commit,
        control_tree=context.control_tree,
        provider_contract_version=context.provider_contract_version,
        plan_id=context.plan_id,
        plan_sha256=context.plan_sha256,
        command_package_sha256=context.command_package_sha256,
        control_binding_semantic_sha256=context.control_binding_semantic_sha256,
        effect_implementation=identity,
        transaction_root_identity=context.transaction_root_identity,
        external_authorization_reference=None,
        external_authorization_source_sha256=None,
    )
    shadow = mint_shadow_effect_authority(source="test-shadow-only", context=shadow_context)
    with pytest.raises(ValueError, match="shadow authority"):
        load_registered_package_effects(
            repository,
            contract,
            authorization_context=shadow_context,
            authority=shadow,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("control_commit", "1" * 40),
        ("control_tree", "2" * 40),
        ("provider_contract_version", "V18"),
        ("plan_id", "PLAN-EXP0001-PILOT-V18"),
        ("plan_sha256", "3" * 64),
        ("command_package_sha256", "4" * 64),
        ("control_binding_semantic_sha256", "5" * 64),
        ("transaction_root_identity", "6" * 64),
        ("external_authorization_reference", "AUTH-CHANGED-EXTERNAL"),
        ("external_authorization_source_sha256", "7" * 64),
    ],
)
def test_live_grant_rejects_every_changed_authorization_binding(
    package_fixture: tuple[
        Path,
        T09ProviderContract,
        EffectImplementationIdentity,
        EffectAuthorizationContext,
        EffectAuthorityGrant,
    ],
    field: str,
    replacement: str,
) -> None:
    repository, contract, _identity, context, grant = package_fixture
    changed = replace(context, **{field: replacement})
    with pytest.raises(ValueError, match="authority"):
        load_registered_package_effects(
            repository,
            contract,
            authorization_context=changed,
            authority=grant,
        )


def test_changed_package_effect_identity_invalidates_external_grant(
    package_fixture: tuple[
        Path,
        T09ProviderContract,
        EffectImplementationIdentity,
        EffectAuthorizationContext,
        EffectAuthorityGrant,
    ],
) -> None:
    repository, contract, identity, context, grant = package_fixture
    changed_identity = replace(identity, sha256="8" * 64)
    changed = replace(context, effect_implementation=changed_identity)
    with pytest.raises(ValueError, match="authority"):
        load_registered_package_effects(
            repository,
            contract,
            authorization_context=changed,
            authority=grant,
        )


def test_package_effect_path_escape_and_unsupported_protocol_are_rejected() -> None:
    with pytest.raises(T09ProviderContractError, match="path is unsafe"):
        PackageEffectRegistration(
            implementation_path="../live.py",
            implementation_bytes=1,
            implementation_sha256="a" * 64,
            factory_entry_point="build_package_effects",
            authority_grant_schema_version="1.0.0",
            effect_protocol_version=EFFECT_PROTOCOL_VERSION,
        )
    with pytest.raises(T09ProviderContractError, match="protocol is unsupported"):
        PackageEffectRegistration(
            implementation_path="runtime/live.py",
            implementation_bytes=1,
            implementation_sha256="a" * 64,
            factory_entry_point="build_package_effects",
            authority_grant_schema_version="1.0.0",
            effect_protocol_version="999.0.0",
        )


def test_symlink_or_mutated_effect_source_is_rejected_before_import(
    package_fixture: tuple[
        Path,
        T09ProviderContract,
        EffectImplementationIdentity,
        EffectAuthorizationContext,
        EffectAuthorityGrant,
    ],
) -> None:
    repository, contract, identity, _context, _grant = package_fixture
    path = repository / identity.path
    original = path.read_bytes()
    target = path.with_name("effect-target.py")
    try:
        path.write_bytes(original + b"\n")
        with pytest.raises(ValueError, match="byte identity drifted"):
            validate_package_effect_registration(repository, contract)
        path.write_bytes(original)
        path.rename(target)
        path.symlink_to(target.name)
        with pytest.raises(ValueError, match="path is unsafe"):
            validate_package_effect_registration(repository, contract)
    finally:
        path.unlink(missing_ok=True)
        target.rename(path)


def test_wrong_factory_is_rejected_after_exact_module_load(
    package_fixture: tuple[
        Path,
        T09ProviderContract,
        EffectImplementationIdentity,
        EffectAuthorizationContext,
        EffectAuthorityGrant,
    ],
) -> None:
    repository, contract, identity, context, _grant = package_fixture
    registration = contract.effect_registration
    assert registration is not None
    wrong_registration = replace(registration, factory_entry_point="wrong_factory")
    wrong_contract = replace(contract, effect_registration=wrong_registration)
    wrong_identity = replace(identity, factory_entry_point="wrong_factory")
    wrong_context = replace(context, effect_implementation=wrong_identity)
    module = _load_grant_module(repository / identity.path, identity)
    grant_type = module.PackageEffectGrant
    wrong_grant = cast(EffectAuthorityGrant, grant_type(wrong_context))
    with pytest.raises(ValueError, match="factory is absent"):
        load_registered_package_effects(
            repository,
            wrong_contract,
            authorization_context=wrong_context,
            authority=wrong_grant,
        )


def test_shared_effect_source_has_no_live_grant_factory() -> None:
    source = (ROOT / "src/giclab/control/effects.py").read_text(encoding="utf-8")
    assert "mint_live" not in source
    assert "_mint_live" not in source
    assert "shared code has no live factory" in source
