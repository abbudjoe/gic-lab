from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from _category3_test_support import execute_shadow_plan, validated_rehearsal
from _live_effect_fixture import RuntimePackage, materialize_runtime_package

from giclab.control.adapters import AdapterFailure
from giclab.control.category3 import (
    Category3Request,
    execute_category3_transaction,
    repository_identity,
)
from giclab.control.effects import hold_transaction_root
from giclab.control.production import build_production_adapter_assembly
from giclab.control.shadow_effects import ShadowFaultPlan, build_production_shadow_assembly
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[2]

BASE_EFFECT_SOURCE = b'''"""Temporary exact-byte package effect."""

from giclab.control.shadow_effects import build_live_shaped_no_network_effects


def build_package_effects(
    *, repository, contract, authorization_context, authority, held_transaction_root
):
    return build_live_shaped_no_network_effects(
        repository=repository,
        contract=contract,
        implementation_identity=authorization_context.effect_implementation,
        authorization_context=authorization_context,
        authority=authority,
        held_transaction_root=held_transaction_root,
    )
'''

EXECUTION_MUTATION_SOURCE = b'''"""Replace this source during exact-byte module execution."""

import os
from pathlib import Path
from giclab.control.shadow_effects import build_live_shaped_no_network_effects

_source = Path(__file__)
_replacement = _source.with_name(_source.name + ".replacement")
_replacement.write_bytes(_source.read_bytes())
_replacement.chmod(0o644)
os.replace(_replacement, _source)


def build_package_effects(
    *, repository, contract, authorization_context, authority, held_transaction_root
):
    return build_live_shaped_no_network_effects(
        repository=repository,
        contract=contract,
        implementation_identity=authorization_context.effect_implementation,
        authorization_context=authorization_context,
        authority=authority,
        held_transaction_root=held_transaction_root,
    )
'''

FACTORY_MUTATION_SOURCE = b'''"""Replace source during factory construction."""

import os
from pathlib import Path
from giclab.control.shadow_effects import build_live_shaped_no_network_effects


def build_package_effects(
    *, repository, contract, authorization_context, authority, held_transaction_root
):
    source = Path(__file__)
    replacement = source.with_name(source.name + ".replacement")
    replacement.write_bytes(source.read_bytes())
    replacement.chmod(0o644)
    os.replace(replacement, source)
    return build_live_shaped_no_network_effects(
        repository=repository,
        contract=contract,
        implementation_identity=authorization_context.effect_implementation,
        authorization_context=authorization_context,
        authority=authority,
        held_transaction_root=held_transaction_root,
    )
'''

ROOT_REPLACEMENT_SOURCE = b'''"""Exercise held-root terminal cleanup."""

from giclab.control.shadow_effects import ShadowFaultPlan, build_live_shaped_no_network_effects


def build_package_effects(
    *, repository, contract, authorization_context, authority, held_transaction_root
):
    return build_live_shaped_no_network_effects(
        repository=repository,
        contract=contract,
        implementation_identity=authorization_context.effect_implementation,
        authorization_context=authorization_context,
        authority=authority,
        held_transaction_root=held_transaction_root,
        fault_plan=ShadowFaultPlan(
            "live-root-replacement-terminalization",
            root_replacement_before_cleanup=True,
        ),
    )
'''

PRIVACY_FAILURE_SOURCE = b'''"""Exercise guaranteed terminalization after privacy failure."""

from giclab.control.shadow_effects import ShadowFaultPlan, build_live_shaped_no_network_effects


def build_package_effects(
    *, repository, contract, authorization_context, authority, held_transaction_root
):
    return build_live_shaped_no_network_effects(
        repository=repository,
        contract=contract,
        implementation_identity=authorization_context.effect_implementation,
        authorization_context=authorization_context,
        authority=authority,
        held_transaction_root=held_transaction_root,
        fault_plan=ShadowFaultPlan(
            "live-terminal-privacy-failure",
            fail_operation="evidence.scan_privacy",
        ),
    )
'''

CLEANUP_RECEIPT_FAILURE_SOURCE = b'''"""Exercise terminalization after bad cleanup evidence."""

from giclab.control.shadow_effects import ShadowFaultPlan, build_live_shaped_no_network_effects


def build_package_effects(
    *, repository, contract, authorization_context, authority, held_transaction_root
):
    return build_live_shaped_no_network_effects(
        repository=repository,
        contract=contract,
        implementation_identity=authorization_context.effect_implementation,
        authorization_context=authorization_context,
        authority=authority,
        held_transaction_root=held_transaction_root,
        fault_plan=ShadowFaultPlan(
            "live-terminal-cleanup-receipt-failure",
            cleanup_receipt_fault="wrong-handoff",
        ),
    )
'''


@pytest.fixture()
def package(tmp_path: Path) -> RuntimePackage:
    return materialize_runtime_package(ROOT, tmp_path, effect_source=BASE_EFFECT_SOURCE)


def test_same_size_effect_source_replacement_before_load_is_rejected(
    package: RuntimePackage,
) -> None:
    source = package.held_source.path
    encoded = source.read_bytes()
    displaced = source.with_name(source.name + ".displaced")
    source.rename(displaced)
    source.write_bytes(encoded)
    source.chmod(0o644)
    with pytest.raises(ValueError, match="inode identity changed"):
        package.load()


def test_effect_source_replacement_during_module_execution_is_rejected(
    tmp_path: Path,
) -> None:
    package = materialize_runtime_package(
        ROOT,
        tmp_path,
        effect_source=EXECUTION_MUTATION_SOURCE,
    )
    module_name = "giclab_package_effect_" + package.held_source.semantic_sha256
    with pytest.raises(ValueError, match="inode identity changed"):
        package.load()
    assert module_name not in sys.modules


def test_effect_source_replacement_during_factory_is_rejected(
    tmp_path: Path,
) -> None:
    package = materialize_runtime_package(
        ROOT,
        tmp_path,
        effect_source=FACTORY_MUTATION_SOURCE,
    )
    module_name = "giclab_package_effect_" + package.held_source.semantic_sha256
    with pytest.raises(ValueError, match="inode identity changed"):
        package.load()
    assert module_name not in sys.modules


def test_stale_or_malicious_pyc_is_never_consulted(package: RuntimePackage) -> None:
    pycache = package.held_source.path.parent / "__pycache__"
    pycache.mkdir()
    (pycache / "t09_package_effects_v17.cpython-311.pyc").write_bytes(b"malicious-untrusted-pyc")
    loaded = package.load()
    assert loaded.identity.sha256 == package.held_source.identity.sha256
    assert loaded.module.__spec__ is None
    assert loaded.module.__loader__ is None


def test_effect_module_parent_retarget_is_rejected(package: RuntimePackage) -> None:
    parent = package.held_source.path.parent
    displaced = parent.with_name(parent.name + "-displaced")
    parent.rename(displaced)
    parent.mkdir(mode=0o755)
    replacement = parent / package.held_source.path.name
    shutil.copyfile(displaced / package.held_source.path.name, replacement)
    replacement.chmod(0o644)
    with pytest.raises(ValueError, match="inode identity changed"):
        package.load()


def test_effect_module_hardlink_is_rejected(package: RuntimePackage) -> None:
    os.link(
        package.held_source.path,
        package.held_source.path.with_name("effect-hardlink.py"),
    )
    with pytest.raises(ValueError, match="inode identity changed"):
        package.load()


def test_transaction_root_itself_or_parent_symlink_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real-root"
    real.mkdir(mode=0o700)
    direct = tmp_path / "root-link"
    direct.symlink_to(real.name, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        hold_transaction_root(direct)

    parent = tmp_path / "real-parent"
    parent.mkdir(mode=0o700)
    nested = parent / "nested-root"
    nested.mkdir(mode=0o700)
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(parent.name, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        hold_transaction_root(parent_link / "nested-root")


def test_transaction_root_replacement_after_grant_validation_stops_activation(
    package: RuntimePackage,
) -> None:
    root = package.held_root.path
    displaced = root.with_name(root.name + "-displaced")
    root.rename(displaced)
    root.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="root identity changed"):
        package.load()


def test_effect_returning_another_root_after_factory_stops_shared_assembly(
    package: RuntimePackage,
) -> None:
    loaded = package.load()
    alternate = package.held_root.path.parent / "alternate-root"
    alternate.mkdir(mode=0o700)
    loaded.effects._delegate._root = alternate
    with pytest.raises(ValueError, match="transaction root is not"):
        build_production_adapter_assembly(
            package.repository,
            package.contract,
            low_level_effects=loaded.effects,
            authorization_context=package.context,
            authority=package.authority,
            held_transaction_root=package.held_root,
            held_effect_source=loaded.held_source,
        )


@pytest.mark.parametrize(
    ("fault", "phase"),
    [
        ("raw-root-symlink", "condition-execution"),
        ("finalized-root-symlink", "finalization"),
        ("raw-manifest-hardlink", "condition-execution"),
        ("raw-receipt-hardlink", "condition-execution"),
        ("raw-same-size-swap-before-finalizer", "finalization"),
        ("raw-mutation-during-finalizer", "finalization"),
        ("session-swap-before-evaluator", "evaluation"),
    ],
)
def test_symlink_hardlink_swap_or_mutation_never_reaches_scientific_acceptance(
    fault: str,
    phase: str,
) -> None:
    receipt = execute_shadow_plan(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(f"held-identity-{fault}", held_identity_fault=fault),
    )
    assert receipt["earliest_stopping_phase"] == phase
    assert receipt["scientific_interpretation_allowed"] is False
    retained = receipt["evidence_retained"]
    assert isinstance(retained, dict)
    assert retained["evaluator"] == []
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    failures = evidence["essential_failures"]
    assert isinstance(failures, dict) and len(failures) == 1
    failure = next(iter(failures.values()))
    assert failure["unscored"] is True


def test_cleanup_uses_held_owned_root_after_original_path_replacement(
    package: RuntimePackage,
) -> None:
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
    original = package.held_root.path
    displaced = original.with_name(original.name + "-owned-displaced")
    original.rename(displaced)
    original.mkdir(mode=0o700)
    receipt_sha256 = world.cleanup(None)
    assert len(receipt_sha256) == 64
    evidence = world.control_evidence()
    assert evidence["cleanup_used_held_root_after_path_mismatch"] is True
    assert evidence["cleanup_receipt_sha256"] == receipt_sha256
    assert package.held_root.descriptor >= 0


def test_held_artifact_public_binding_excludes_unstable_inode_values() -> None:
    source = (ROOT / "src/giclab/control/effects.py").read_text(encoding="utf-8")
    assert '"held_runtime_identity_validated": True' in source
    assert "spec_from_file_location" not in source


def test_public_shadow_receipt_is_stable_across_fresh_transaction_roots(
    tmp_path: Path,
) -> None:
    plan = ShadowFaultPlan("public-held-root-projection-stability")
    rehearsal = validated_rehearsal(ROOT.as_posix(), V16_PROVIDER_CONTRACT)

    def execute_at(root: Path) -> dict[str, object]:
        root.mkdir(mode=0o700)
        world = build_production_shadow_assembly(
            ROOT,
            V16_PROVIDER_CONTRACT,
            plan,
            rehearsal=rehearsal,
            transaction_root=root,
        )
        commit, tree = repository_identity(ROOT)
        return execute_category3_transaction(
            Category3Request(
                repository=ROOT,
                contract=V16_PROVIDER_CONTRACT,
                scenario=plan.name,
                expected_repository_commit=commit,
                expected_repository_tree=tree,
                control_proof=rehearsal,
            ),
            adapters=world.adapters(),
        )

    first = execute_at(tmp_path / "root-a")
    second = execute_at(tmp_path / "root-b")
    first_evidence = first["production_control_evidence"]
    second_evidence = second["production_control_evidence"]
    assert isinstance(first_evidence, dict) and isinstance(second_evidence, dict)
    expected = {
        "identity_derived_by_shared_code": True,
        "descriptor_held_through_cleanup": True,
        "no_symlink_path_components_validated": True,
        "current_user_owned": True,
        "group_world_write_absent": True,
        "device_inode_mode_mount_revalidated": True,
        "runtime_identity_values_retained": False,
    }
    public_root = first_evidence["held_transaction_root"]
    assert isinstance(public_root, dict)
    attestation = dict(public_root)
    semantic = attestation.pop("public_attestation_semantic_sha256")
    assert attestation == expected
    assert isinstance(semantic, str) and len(semantic) == 64
    assert first_evidence["held_transaction_root"] == second_evidence["held_transaction_root"]
    assert first["semantic_sha256"] == second["semantic_sha256"]


def test_controller_releases_held_descriptors_only_after_terminal_result() -> None:
    rehearsal = validated_rehearsal(ROOT.as_posix(), V16_PROVIDER_CONTRACT)
    world = build_production_shadow_assembly(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan("held-resource-lifetime"),
        rehearsal=rehearsal,
    )
    commit, tree = repository_identity(ROOT)
    receipt = execute_category3_transaction(
        Category3Request(
            repository=ROOT,
            contract=V16_PROVIDER_CONTRACT,
            scenario="held-resource-lifetime",
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=rehearsal,
        ),
        adapters=world.adapters(),
    )
    assert receipt["terminal_state"] == "category3-shadow-complete-clean"
    assert receipt["cleanup"]["state"] == "complete"
    with pytest.raises(ValueError, match="closed"):
        world.held_transaction_root.revalidate_descriptor()


def test_full_live_shaped_controller_terminalizes_after_root_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = materialize_runtime_package(
        ROOT,
        tmp_path,
        effect_source=ROOT_REPLACEMENT_SOURCE,
        prepare_execution=True,
        registry_monkeypatch=monkeypatch,
    )
    assert package.rehearsal is not None
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
    commit, tree = repository_identity(package.repository)
    original = package.held_root.path
    receipt = execute_category3_transaction(
        Category3Request(
            repository=package.repository,
            contract=package.contract,
            scenario="live-root-replacement-terminalization",
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=package.rehearsal,
        ),
        adapters=world.adapters(),
    )
    replacement = original / "replacement-sentinel.bin"
    assert replacement.read_bytes() == b"replacement-directory-must-remain-unchanged\n"
    assert tuple(original.iterdir()) == (replacement,)
    assert receipt["terminal_state"] == "category3-live-stopped-privacy-blocked"
    assert receipt["cleanup"] == {
        "state": "complete",
        "resumed": False,
        "provider_resources_zero": True,
        "security_restored": True,
        "privacy_clean": False,
    }
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    assert evidence["cleanup_used_held_root_after_path_mismatch"] is True
    authority = evidence["authority_consumption"]
    assert isinstance(authority, dict)
    assert authority["terminal_state"] == "terminal-failed-nonreplayable"
    assert authority["replay_permitted"] is False
    assert "original path identity changed" in str(receipt["stop_reason"])
    with pytest.raises(ValueError, match="closed"):
        package.held_root.revalidate_descriptor()
    with pytest.raises(ValueError, match="closed"):
        package.held_source.revalidate(package.repository)


def _assert_live_package_terminally_released(package: RuntimePackage) -> None:
    state = json.loads((package.held_root.path / ".live-authority-state.json").read_bytes())
    assert state["state"] == "terminal-failed-nonreplayable"
    assert state["replay_permitted"] is False
    with pytest.raises(ValueError, match="closed"):
        package.held_root.revalidate_descriptor()
    with pytest.raises(ValueError, match="closed"):
        package.held_source.revalidate(package.repository)
    with pytest.raises(ValueError, match="closed"):
        _ = package.authority.state


@pytest.mark.parametrize(
    ("source", "expected_cleanup_state"),
    [
        (PRIVACY_FAILURE_SOURCE, "complete"),
        (CLEANUP_RECEIPT_FAILURE_SOURCE, "unresolved"),
    ],
)
def test_full_controller_terminalizes_and_releases_after_terminal_validation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: bytes,
    expected_cleanup_state: str,
) -> None:
    package = materialize_runtime_package(
        ROOT,
        tmp_path,
        effect_source=source,
        prepare_execution=True,
        registry_monkeypatch=monkeypatch,
    )
    assert package.rehearsal is not None
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
    commit, tree = repository_identity(package.repository)
    receipt = execute_category3_transaction(
        Category3Request(
            repository=package.repository,
            contract=package.contract,
            scenario="live-terminal-validation-failure",
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=package.rehearsal,
        ),
        adapters=world.adapters(),
    )
    assert receipt["cleanup"]["state"] == expected_cleanup_state  # type: ignore[index]
    assert receipt["cleanup"]["privacy_clean"] is False  # type: ignore[index]
    evidence = receipt["production_control_evidence"]
    assert isinstance(evidence, dict)
    authority = evidence["authority_consumption"]
    assert isinstance(authority, dict)
    assert authority["terminal_state"] == "terminal-failed-nonreplayable"
    _assert_live_package_terminally_released(package)


def test_preparation_failure_after_live_authority_validation_is_nonreplayable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = materialize_runtime_package(
        ROOT,
        tmp_path,
        effect_source=BASE_EFFECT_SOURCE,
        prepare_execution=True,
        registry_monkeypatch=monkeypatch,
    )
    assert package.rehearsal is not None
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
    commit, tree = repository_identity(package.repository)

    def fail_composition(_repository: Path, _contract: object) -> dict[str, object]:
        raise RuntimeError("deterministic preparation failure")

    receipt = execute_category3_transaction(
        Category3Request(
            repository=package.repository,
            contract=package.contract,
            scenario="live-preparation-failure",
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=package.rehearsal,
        ),
        adapters=world.adapters(),
        composition_builder=fail_composition,  # type: ignore[arg-type]
    )
    assert receipt["earliest_stopping_phase"] == "offline-composition"
    assert receipt["call_counts"] == {
        "secret_reads": 0,
        "metadata_requests": 0,
        "provider_gets": 0,
        "provider_posts": 0,
        "launch_calls": 0,
        "termination_calls": 0,
        "condition_reservations": 0,
        "condition_entries": 0,
        "model_call_attempts": 0,
        "browser_actions": 0,
        "unknown_model_outcomes": 0,
    }
    _assert_live_package_terminally_released(package)


def test_terminal_result_construction_failure_still_closes_every_held_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = materialize_runtime_package(
        ROOT,
        tmp_path,
        effect_source=BASE_EFFECT_SOURCE,
        prepare_execution=True,
        registry_monkeypatch=monkeypatch,
    )
    assert package.rehearsal is not None
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
    commit, tree = repository_identity(package.repository)

    def fail_control_evidence() -> dict[str, object]:
        raise AdapterFailure("terminal result construction failure")

    monkeypatch.setattr(world, "control_evidence", fail_control_evidence)

    def fail_composition(_repository: Path, _contract: object) -> dict[str, object]:
        raise RuntimeError("deterministic preparation failure")

    with pytest.raises(AdapterFailure, match="terminal result construction failure"):
        execute_category3_transaction(
            Category3Request(
                repository=package.repository,
                contract=package.contract,
                scenario="live-terminal-result-failure",
                expected_repository_commit=commit,
                expected_repository_tree=tree,
                control_proof=package.rehearsal,
            ),
            adapters=world.adapters(),
            composition_builder=fail_composition,  # type: ignore[arg-type]
        )
    _assert_live_package_terminally_released(package)
