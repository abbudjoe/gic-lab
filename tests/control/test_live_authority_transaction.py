from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from _live_effect_fixture import RuntimePackage, canonical_bytes, materialize_runtime_package
from _synthetic_successor import install_synthetic_registry

from giclab.control import effects as effect_contracts
from giclab.control.adapters import AdapterFailure
from giclab.control.effects import (
    EffectExecutionMode,
    LiveAuthorityState,
    ValidatedLiveEffectAuthority,
    hold_transaction_root,
    project_live_authority_overlay,
    validate_external_live_effect_authority,
)
from giclab.control.production import build_production_adapter_assembly

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def package(tmp_path: Path) -> RuntimePackage:
    return materialize_runtime_package(ROOT, tmp_path)


def _world(package: RuntimePackage) -> tuple[object, object]:
    loaded = package.load()
    world = build_production_adapter_assembly(
        package.repository,
        package.contract,
        low_level_effects=loaded.effects,
        authorization_context=package.context,
        authority=package.authority,
        held_transaction_root=package.held_root,
        held_effect_source=loaded.held_source,
    )
    return world, loaded.effects


def _fresh_overlay(
    package: RuntimePackage,
    tmp_path: Path,
    *,
    label: str,
    reference: str | None = None,
) -> tuple[Path, object, dict[str, object]]:
    root = tmp_path / f"private-root-{label}"
    root.mkdir(mode=0o700)
    held_root = hold_transaction_root(root.resolve(strict=True))
    resolved_reference = reference
    if resolved_reference is None:
        prefix = package.contract.authorization_prefix
        assert isinstance(prefix, str)
        resolved_reference = prefix + label.upper().replace("_", "-")
    document = project_live_authority_overlay(
        package.repository,
        package.contract,
        held_transaction_root=held_root,
        effect_implementation=package.held_source.identity,
        control_binding_semantic_sha256="b" * 64,
        external_authorization_reference=resolved_reference,
        current_turn_scope="T09-PR14-AUTHORITY-TEST",
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
    )
    path = tmp_path / f"private-overlay-{label}.json"
    path.write_bytes(canonical_bytes(document))
    path.chmod(0o600)
    return path, held_root, document


def _validate_fresh(
    package: RuntimePackage,
    path: Path,
    held_root: object,
) -> tuple[object, ValidatedLiveEffectAuthority]:
    return validate_external_live_effect_authority(
        package.repository,
        package.contract,
        overlay_path=path,
        held_transaction_root=held_root,  # type: ignore[arg-type]
        effect_implementation=package.held_source.identity,
        control_binding_semantic_sha256="b" * 64,
        current_turn_scope="T09-PR14-AUTHORITY-TEST",
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
    )


def test_first_valid_private_overlay_mints_one_opaque_single_use_proof(
    package: RuntimePackage,
) -> None:
    authority = package.authority
    assert isinstance(authority, ValidatedLiveEffectAuthority)
    assert authority.state is LiveAuthorityState.VALIDATED_UNCONSUMED
    assert package.context.external_authorization_reference is not None
    assert package.context.external_authorization_reference.startswith("AUTH-T09-V17-")
    assert (
        package.context.external_authorization_source_sha256
        == hashlib.sha256(package.overlay_path.read_bytes()).hexdigest()
    )
    authority.reserve_before_secret()
    authority.mark_metadata_send_attempted()
    authority.mark_metadata_bound()
    authority.consume_provider_launch()
    authority.terminal_complete()
    receipt = authority.consumption_receipt()
    assert receipt["terminal_state"] == "terminal-complete"
    assert receipt["single_use"] is True
    assert receipt["replay_permitted"] is False
    assert receipt["contains_private_overlay_contents"] is False


def test_validator_rejects_wrong_contract_prefix(
    package: RuntimePackage,
    tmp_path: Path,
) -> None:
    path, held_root, _document = _fresh_overlay(
        package,
        tmp_path,
        label="wrong_prefix",
        reference="AUTH-T09-V16-WRONG-CONTRACT",
    )
    with pytest.raises(ValueError, match="another version"):
        _validate_fresh(package, path, held_root)


def test_wrong_authorization_source_hash_is_rejected(package: RuntimePackage) -> None:
    with pytest.raises(ValueError, match="identities differ"):
        package.authority.assert_phase_binding(
            reference=str(package.context.external_authorization_reference),
            source_sha256="f" * 64,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("control_commit", "1" * 40),
        ("control_tree", "2" * 40),
        ("plan_sha256", "3" * 64),
        ("command_package_sha256", "4" * 64),
        ("control_binding_semantic_sha256", "5" * 64),
        ("transaction_root_identity", "6" * 64),
        ("current_turn_scope", "T09-PR14-DIFFERENT-TURN"),
    ],
)
def test_opaque_proof_rejects_control_package_plan_receipt_root_or_turn_drift(
    package: RuntimePackage,
    field: str,
    replacement: object,
) -> None:
    assert package.authority.is_valid_for(replace(package.context, **{field: replacement})) is False


@pytest.mark.parametrize("field", ["reference", "source"])
def test_effect_and_metadata_authority_split_stops_before_metadata_send(
    package: RuntimePackage,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    world, low_level = _world(package)
    original: Callable[..., dict[str, object]] = low_level.metadata_authorization_binding

    def split_binding(*, contract: object) -> dict[str, object]:
        binding = dict(original(contract=contract))
        if field == "reference":
            binding["authorization_reference"] = "AUTH-T09-V17-SPLIT"
        else:
            binding["authorization_source_sha256"] = "e" * 64
        return binding

    monkeypatch.setattr(low_level, "metadata_authorization_binding", split_binding)
    world.read()
    with pytest.raises(AdapterFailure, match="not one transaction"):
        world.request(contract_version=package.contract.version)
    assert low_level.metadata_request_count == 0
    package.authority.terminal_failed_nonreplayable()
    assert package.authority.state is LiveAuthorityState.TERMINAL_FAILED_NONREPLAYABLE


def test_provider_launch_authority_split_stops_before_post(
    package: RuntimePackage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_synthetic_registry(monkeypatch, package.contract)
    world, low_level = _world(package)
    original: Callable[..., dict[str, object]] = low_level.metadata_authorization_binding
    calls = 0

    def split_on_launch(*, contract: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        binding = dict(original(contract=contract))
        if calls >= 2:
            binding["authorization_reference"] = "AUTH-T09-V17-SPLIT-LAUNCH"
        return binding

    monkeypatch.setattr(low_level, "metadata_authorization_binding", split_on_launch)
    world.read()
    envelope = world.request(contract_version=package.contract.version)
    assert world.is_fresh(envelope) is True
    assert world.inventory() == ()
    with pytest.raises(AdapterFailure, match="production launch preparation failed"):
        world.launch(launch_ordinal=1)
    assert low_level._delegate._active == {}
    assert package.authority.state is LiveAuthorityState.METADATA_BOUND
    package.authority.terminal_failed_nonreplayable()


def test_repository_state_cannot_mint_live_authority(
    package: RuntimePackage,
) -> None:
    repository_overlay = package.repository / "runtime-only-authority.json"
    repository_overlay.write_bytes(package.overlay_path.read_bytes())
    repository_overlay.chmod(0o600)
    with pytest.raises(ValueError, match="repository state"):
        validate_external_live_effect_authority(
            package.repository,
            package.contract,
            overlay_path=repository_overlay,
            held_transaction_root=package.held_root,
            effect_implementation=package.held_source.identity,
            control_binding_semantic_sha256="a" * 64,
            current_turn_scope="T09-PR14-TEST-AUTHORITY",
            execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
        )


@pytest.mark.parametrize("fault", ["symlink", "hardlink", "wrong-mode"])
def test_private_overlay_symlink_hardlink_or_wrong_mode_is_rejected(
    package: RuntimePackage,
    tmp_path: Path,
    fault: str,
) -> None:
    path, held_root, _document = _fresh_overlay(package, tmp_path, label=fault)
    if fault == "symlink":
        target = path.with_name(path.name + ".target")
        path.rename(target)
        path.symlink_to(target.name)
    elif fault == "hardlink":
        os.link(path, path.with_name(path.name + ".link"))
    else:
        path.chmod(0o644)
    with pytest.raises(ValueError, match=r"symlink|private and exact"):
        _validate_fresh(package, path, held_root)


def test_duplicate_key_overlay_is_rejected(
    package: RuntimePackage,
    tmp_path: Path,
) -> None:
    path, held_root, _document = _fresh_overlay(package, tmp_path, label="duplicate")
    path.write_bytes(b'{"authorization_reference":"A","authorization_reference":"B"}\n')
    with pytest.raises(ValueError, match="duplicate key"):
        _validate_fresh(package, path, held_root)


@pytest.mark.parametrize(
    "fault",
    ["state-symlink", "state-hardlink", "state-mode", "state-owner", "replacement", "truncated"],
)
def test_authority_state_file_identity_faults_fail_closed(
    package: RuntimePackage,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    authority = package.authority
    state_path = package.held_root.path / ".live-authority-state.json"
    if fault == "state-symlink":
        target = state_path.with_name("state-target.json")
        state_path.rename(target)
        state_path.symlink_to(target.name)
    elif fault == "state-hardlink":
        os.link(state_path, state_path.with_name("state-hardlink.json"))
    elif fault == "state-mode":
        state_path.chmod(0o640)
    elif fault == "state-owner":
        actual_uid = os.getuid()
        monkeypatch.setattr(effect_contracts.os, "getuid", lambda: actual_uid + 1)
    elif fault == "replacement":
        encoded = state_path.read_bytes()
        state_path.unlink()
        state_path.write_bytes(encoded)
        state_path.chmod(0o600)
    else:
        state_path.write_bytes(b'{"state":')
    with pytest.raises(ValueError, match=r"authority|held artifact"):
        _ = authority.state


def test_ambiguous_or_duplicate_durable_state_fails_closed(package: RuntimePackage) -> None:
    state_path = package.held_root.path / ".live-authority-state.json"
    state_path.write_bytes(b'{"schema_version":"1.0.0","schema_version":"1.0.0"}\n')
    with pytest.raises(ValueError, match="duplicate key"):
        _ = package.authority.state


def test_external_overlay_replacement_after_validation_invalidates_proof(
    package: RuntimePackage,
) -> None:
    encoded = package.overlay_path.read_bytes()
    package.overlay_path.unlink()
    package.overlay_path.write_bytes(encoded)
    package.overlay_path.chmod(0o600)
    with pytest.raises(ValueError, match="source identity changed"):
        _ = package.authority.state


def test_validator_replay_and_second_campaign_fail(
    package: RuntimePackage,
) -> None:
    with pytest.raises(ValueError, match="already created"):
        validate_external_live_effect_authority(
            package.repository,
            package.contract,
            overlay_path=package.overlay_path,
            held_transaction_root=package.held_root,
            effect_implementation=package.held_source.identity,
            control_binding_semantic_sha256="a" * 64,
            current_turn_scope="T09-PR14-TEST-AUTHORITY",
            execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
        )
    package.authority.reserve_before_secret()
    package.authority.terminal_failed_nonreplayable()
    with pytest.raises(ValueError, match=r"replayed|out of order"):
        package.authority.reserve_before_secret()


def test_failure_after_secret_reservation_is_consumed_and_nonreplayable(
    package: RuntimePackage,
) -> None:
    package.authority.reserve_before_secret()
    package.authority.terminal_failed_nonreplayable()
    receipt = package.authority.consumption_receipt()
    assert receipt["terminal_state"] == "terminal-failed-nonreplayable"
    assert receipt["replay_permitted"] is False
    assert package.authority.is_valid_for(package.context) is False


def test_shared_source_has_no_live_authority_mint_or_public_grant() -> None:
    source = (ROOT / "src/giclab/control/effects.py").read_text(encoding="utf-8")
    assert "def mint_live" not in source
    assert "def _mint_live" not in source
    assert "class PackageEffectGrant" not in source
    with pytest.raises(TypeError, match="external validator"):
        ValidatedLiveEffectAuthority()
