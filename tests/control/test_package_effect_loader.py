from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from _live_effect_fixture import RuntimePackage, materialize_runtime_package

from giclab.control.effects import (
    EFFECT_PROTOCOL_VERSION,
    EffectAuthorityGrant,
    EffectAuthorityKind,
    EffectExecutionMode,
    ValidatedLiveEffectAuthority,
    load_registered_package_effects,
    mint_shadow_effect_authority,
    validate_package_effect_registration,
)
from giclab.control.production import build_production_adapter_assembly
from giclab.harness.t09_provider_contracts import PackageEffectRegistration

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def package(tmp_path: Path) -> RuntimePackage:
    return materialize_runtime_package(ROOT, tmp_path)


def test_exact_package_effect_factory_loads_and_builds_production_assembly(
    package: RuntimePackage,
) -> None:
    loaded = package.load()
    assert loaded.identity == package.held_source.identity
    assert loaded.held_source is package.held_source
    assert loaded.held_transaction_root is package.held_root
    assert loaded.effects.implementation_identity() == loaded.identity
    world = build_production_adapter_assembly(
        package.repository,
        package.contract,
        low_level_effects=loaded.effects,
        authorization_context=package.context,
        authority=package.authority,
        held_transaction_root=package.held_root,
        held_effect_source=loaded.held_source,
    )
    assert world.contract == package.contract
    assert world.held_transaction_root is package.held_root


def test_shadow_grant_cannot_instantiate_package_live_effects(
    package: RuntimePackage,
) -> None:
    shadow_context = replace(
        package.context,
        authority_kind=EffectAuthorityKind.SHADOW_ONLY,
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
        external_authorization_reference=None,
        external_authorization_source_sha256=None,
        current_turn_scope="test-shadow-only",
    )
    shadow = mint_shadow_effect_authority(source="test-shadow-only", context=shadow_context)
    with pytest.raises(ValueError, match="opaque validated authority"):
        load_registered_package_effects(
            package.repository,
            package.contract,
            authorization_context=shadow_context,
            authority=shadow,
            held_source=package.held_source,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("control_commit", "1" * 40),
        ("control_tree", "2" * 40),
        ("provider_contract_version", "V18"),
        ("plan_id", "PLAN-EXP0001-PILOT-V18"),
        ("plan_path", "plans/changed.yaml"),
        ("plan_bytes", 1),
        ("plan_sha256", "3" * 64),
        ("command_package_sha256", "4" * 64),
        ("control_binding_semantic_sha256", "5" * 64),
        ("transaction_root_identity", "6" * 64),
        ("external_authorization_reference", "AUTH-T09-V17-CHANGED"),
        ("external_authorization_source_sha256", "7" * 64),
        ("current_turn_scope", "T09-PR14-CHANGED"),
    ],
)
def test_live_grant_rejects_every_changed_authorization_binding(
    package: RuntimePackage,
    field: str,
    replacement: object,
) -> None:
    changed = replace(package.context, **{field: replacement})
    with pytest.raises(ValueError, match="authority"):
        load_registered_package_effects(
            package.repository,
            package.contract,
            authorization_context=changed,
            authority=package.authority,
            held_source=package.held_source,
        )


def test_trivial_duck_typed_grants_are_rejected(package: RuntimePackage) -> None:
    class AlwaysTrue:
        kind = EffectAuthorityKind.LIVE_AUTHORIZED
        source = "forged"

        def authorizes(self, _context: object) -> bool:
            return True

    class ContextEquality:
        kind = EffectAuthorityKind.LIVE_AUTHORIZED
        source = "forged"

        def __init__(self, context: object) -> None:
            self.context = context

        def authorizes(self, context: object) -> bool:
            return context == self.context

    for forged in (AlwaysTrue(), ContextEquality(package.context)):
        with pytest.raises(ValueError, match="opaque validated authority"):
            load_registered_package_effects(
                package.repository,
                package.contract,
                authorization_context=package.context,
                authority=cast(EffectAuthorityGrant, forged),
                held_source=package.held_source,
            )


def test_public_live_authority_construction_is_rejected() -> None:
    with pytest.raises(TypeError, match="external validator"):
        ValidatedLiveEffectAuthority()


def test_package_effect_path_escape_and_unsupported_protocol_are_rejected() -> None:
    with pytest.raises(ValueError, match="path is unsafe"):
        PackageEffectRegistration(
            implementation_path="../live.py",
            implementation_bytes=1,
            implementation_sha256="a" * 64,
            factory_entry_point="build_package_effects",
            authority_grant_schema_version="1.0.0",
            effect_protocol_version=EFFECT_PROTOCOL_VERSION,
        )
    with pytest.raises(ValueError, match="protocol is unsupported"):
        PackageEffectRegistration(
            implementation_path="runtime/live.py",
            implementation_bytes=1,
            implementation_sha256="a" * 64,
            factory_entry_point="build_package_effects",
            authority_grant_schema_version="1.0.0",
            effect_protocol_version="999.0.0",
        )


def test_symlink_or_mutated_effect_source_is_rejected_before_load(
    package: RuntimePackage,
) -> None:
    path = package.held_source.path
    original = path.read_bytes()
    target = path.with_name("effect-target.py")
    path.write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="identity drifted"):
        validate_package_effect_registration(package.repository, package.contract)
    path.write_bytes(original)
    path.rename(target)
    path.symlink_to(target.name)
    try:
        with pytest.raises(ValueError, match="symlink"):
            validate_package_effect_registration(package.repository, package.contract)
    finally:
        path.unlink()
        target.rename(path)


def test_wrong_declared_factory_is_rejected_before_execution(
    package: RuntimePackage,
) -> None:
    registration = package.contract.effect_registration
    assert registration is not None
    wrong_contract = replace(
        package.contract,
        effect_registration=replace(registration, factory_entry_point="wrong_factory"),
    )
    with pytest.raises(ValueError, match="held source does not match"):
        load_registered_package_effects(
            package.repository,
            wrong_contract,
            authorization_context=package.context,
            authority=package.authority,
            held_source=package.held_source,
        )


def test_shared_effect_source_has_no_generic_live_grant_factory() -> None:
    source = (ROOT / "src/giclab/control/effects.py").read_text(encoding="utf-8")
    assert "mint_live" not in source
    assert "_mint_live" not in source
    assert "class PackageEffectGrant" not in source
