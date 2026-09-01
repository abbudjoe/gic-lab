from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from _synthetic_successor import (
    commit_repository,
    copy_working_repository,
    install_synthetic_registry,
    materialize_synthetic_successor,
    synthetic_contract,
)

from giclab.control import agent_check as agent_check_module
from giclab.control import cli
from giclab.control.agent_check import run_agent_check
from giclab.control.composition import compose_control_plane
from giclab.control.incidents import validate_incidents as validate_incidents_without_adapter
from giclab.control.proofs import REQUIRED_SHARED_SOURCES
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.scenarios import ALL_REQUIRED_SCENARIOS, HAPPY_PATH
from giclab.control.shadow import run_required_shadow_matrix
from giclab.control.state_capsule import generate_state_capsule
from giclab.control.target import (
    EXPLICIT_SOURCE,
    GOAL_SOURCE,
    TargetSelectionError,
    resolve_selected_runtime_target,
)
from giclab.harness import t09_provider_contracts

ROOT = Path(__file__).resolve().parents[2]
V17_PLAN = (
    "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/"
    "T09_PILOT_RUNTIME_PROFILE_V17.yaml"
)


def _goal(repository: Path) -> dict[str, object]:
    value = yaml.safe_load((repository / "control/goals/EXP-0001.yaml").read_text())
    assert isinstance(value, dict)
    return value


def _write_goal(repository: Path, value: dict[str, object]) -> None:
    (repository / "control/goals/EXP-0001.yaml").write_text(
        yaml.safe_dump(value, sort_keys=False),
        encoding="utf-8",
    )


def _light_successor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, object]:
    repository = tmp_path / "successor"
    repository.mkdir()
    identities = materialize_synthetic_successor(ROOT, repository)
    commit, _tree = commit_repository(repository)
    contract = synthetic_contract(identities, source_commit=commit)
    install_synthetic_registry(monkeypatch, contract)
    return repository, contract


def _disable_nested_incident_subprocesses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep synthetic registry injection in-process; incident nodes run separately on V16."""

    def validate_without_execution(
        repository: Path, *, execute_regressions: bool = False
    ) -> dict[str, object]:
        del execute_regressions
        return validate_incidents_without_adapter(repository, execute_regressions=False)

    monkeypatch.setattr(cli, "validate_incidents", validate_without_execution)
    monkeypatch.setattr(agent_check_module, "validate_incidents", validate_without_execution)


def test_current_goal_selects_exact_v16_target() -> None:
    target = resolve_selected_runtime_target(ROOT)
    assert target.source == GOAL_SOURCE
    assert target.historical_contract_version == "V16"
    assert target.successor_contract_version == "V17"
    assert target.successor_status == "not-created"
    assert target.selected_contract.version == "V16"
    assert target.selected_plan_id == "PLAN-EXP0001-PILOT-V16"
    assert target.selected_command_package_sha256 == (
        "377e45728dc53221e42e7910d0f13f14ed219dd947371c48d9730f1f3140507b"
    )
    assert target.to_document()["authority"] == {
        "live_authorization": False,
        "scientific_interpretation_allowed": False,
        "repository_state_grants_authority": False,
    }


def test_current_explicit_selector_accepts_only_v16() -> None:
    explicit = resolve_selected_runtime_target(ROOT, explicit_provider_contract="V16")
    assert explicit.source == EXPLICIT_SOURCE
    assert explicit.selected_contract.version == "V16"
    with pytest.raises(TargetSelectionError, match="incompatible"):
        resolve_selected_runtime_target(ROOT, explicit_provider_contract="V15")


def test_synthetic_package_bound_successor_selects_v17_without_shared_edits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _contract = _light_successor(tmp_path, monkeypatch)
    before = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in REQUIRED_SHARED_SOURCES
    }
    target = resolve_selected_runtime_target(repository)
    after = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in REQUIRED_SHARED_SOURCES
    }
    assert target.source == GOAL_SOURCE
    assert target.successor_status == "package-bound-not-authorized"
    assert target.selected_contract.version == "V17"
    assert target.selected_plan_id == "PLAN-EXP0001-PILOT-V17"
    assert target.selected_package_status == "package-bound-not-authorized"
    assert before == after


def test_successor_explicit_selector_accepts_only_v17(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _contract = _light_successor(tmp_path, monkeypatch)
    explicit = resolve_selected_runtime_target(
        repository,
        explicit_provider_contract="V17",
    )
    assert explicit.source == EXPLICIT_SOURCE
    with pytest.raises(TargetSelectionError, match="incompatible"):
        resolve_selected_runtime_target(repository, explicit_provider_contract="V16")


def test_package_bound_successor_must_be_registered_before_any_effect(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "missing-registration"
    repository.mkdir()
    materialize_synthetic_successor(ROOT, repository)
    effect_counts = {
        "secret_reads": 0,
        "metadata_requests": 0,
        "provider_calls": 0,
        "condition_reservations": 0,
    }
    with pytest.raises(TargetSelectionError, match="not exactly registered"):
        resolve_selected_runtime_target(repository)
    assert set(t09_provider_contracts.PROVIDER_CONTRACTS) == {
        f"V{version}" for version in range(3, 17)
    }
    assert effect_counts == {
        "secret_reads": 0,
        "metadata_requests": 0,
        "provider_calls": 0,
        "condition_reservations": 0,
    }


def test_cli_target_failure_stops_before_every_effect_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "missing-registration-cli"
    repository.mkdir()
    materialize_synthetic_successor(ROOT, repository)
    effect_counts = {
        "secret_reads": 0,
        "metadata_requests": 0,
        "provider_calls": 0,
        "condition_reservations": 0,
    }

    def forbidden_aggregate(*_args: object, **_kwargs: object) -> dict[str, object]:
        effect_counts.update({name: count + 1 for name, count in effect_counts.items()})
        raise AssertionError("aggregate/effect boundary was reached")

    monkeypatch.setattr(cli, "_verified_capsule", forbidden_aggregate)
    assert cli.main(["state-capsule", "--repository", str(repository), "--deterministic"]) == 1
    capsys.readouterr()
    assert effect_counts == {
        "secret_reads": 0,
        "metadata_requests": 0,
        "provider_calls": 0,
        "condition_reservations": 0,
    }


@pytest.mark.parametrize(
    ("relative", "message"),
    (
        (
            "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/"
            "T09_PILOT_RUNTIME_PROFILE_V17.yaml",
            "plan is unavailable",
        ),
        (
            "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/"
            "T09_PILOT_COMMAND_MANIFESTS_V17.json",
            "command package is unavailable",
        ),
    ),
)
def test_missing_successor_package_file_fails_before_any_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
    message: str,
) -> None:
    repository, _contract = _light_successor(tmp_path, monkeypatch)
    (repository / relative).unlink()
    with pytest.raises(TargetSelectionError, match=message):
        resolve_selected_runtime_target(repository)


def test_wrong_successor_plan_id_fails_before_any_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, contract = _light_successor(tmp_path, monkeypatch)
    wrong = replace(contract, plan_id="PLAN-EXP0001-PILOT-V18")
    install_synthetic_registry(monkeypatch, wrong)
    with pytest.raises(TargetSelectionError, match="plan identity is inconsistent"):
        resolve_selected_runtime_target(repository)


def test_wrong_successor_command_sha_fails_before_any_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, contract = _light_successor(tmp_path, monkeypatch)
    wrong = replace(contract, expected_command_manifest_sha256="a" * 64)
    install_synthetic_registry(monkeypatch, wrong)
    with pytest.raises(TargetSelectionError, match="artifact identity drifted"):
        resolve_selected_runtime_target(repository)


def test_successor_command_artifact_drift_fails_before_any_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, contract = _light_successor(tmp_path, monkeypatch)
    assert contract.command_manifest_path is not None
    command_path = repository / contract.command_manifest_path
    command_path.write_bytes(command_path.read_bytes() + b"\n")
    with pytest.raises(TargetSelectionError, match="command-package artifact identity drifted"):
        resolve_selected_runtime_target(repository)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("next_package", "V18", "exact numerical successor"),
        ("next_package", "17", "next_package is malformed"),
        ("next_status", "externally-authorized", "next_status is unsupported"),
    ),
)
def test_malformed_successor_state_fails_before_any_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
    message: str,
) -> None:
    repository, _contract = _light_successor(tmp_path, monkeypatch)
    goal = _goal(repository)
    runtime = goal["runtime_package"]
    assert isinstance(runtime, dict)
    runtime[field] = value
    _write_goal(repository, goal)
    with pytest.raises(TargetSelectionError, match=message):
        resolve_selected_runtime_target(repository)


def test_not_created_status_contradicts_registered_successor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _contract = _light_successor(tmp_path, monkeypatch)
    goal = _goal(repository)
    runtime = goal["runtime_package"]
    assert isinstance(runtime, dict)
    runtime["next_status"] = "not-created"
    _write_goal(repository, goal)
    with pytest.raises(TargetSelectionError, match="it is registered"):
        resolve_selected_runtime_target(repository)


def test_unknown_historical_package_fails_before_any_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _contract = _light_successor(tmp_path, monkeypatch)
    goal = _goal(repository)
    runtime = goal["runtime_package"]
    assert isinstance(runtime, dict)
    runtime.update(
        {
            "historical_package": "V2",
            "next_package": "V3",
            "next_status": "package-bound-not-authorized",
        }
    )
    _write_goal(repository, goal)
    with pytest.raises(TargetSelectionError, match="historical_package is not exactly registered"):
        resolve_selected_runtime_target(repository)


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    (
        ("science", "interpretation_allowed", True, "scientific interpretation"),
        ("authority", "category_3", True, "live authority"),
        ("goal", "current_subgoal", "/Users/private/secret", "private or secret-like"),
    ),
)
def test_goal_never_grants_authority_or_accepts_private_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    section: str,
    field: str,
    value: object,
    message: str,
) -> None:
    repository, _contract = _light_successor(tmp_path, monkeypatch)
    goal = _goal(repository)
    selected = goal if section == "goal" else goal[section]
    assert isinstance(selected, dict)
    selected[field] = value
    _write_goal(repository, goal)
    with pytest.raises(TargetSelectionError, match=message):
        resolve_selected_runtime_target(repository)


def test_all_current_aggregate_surfaces_agree_on_v16() -> None:
    target = resolve_selected_runtime_target(ROOT)
    registry = validate_registry_completeness(ROOT)
    composition = compose_control_plane(
        ROOT,
        contract=target.selected_contract,
        registry_receipt=registry,
    )
    capsule = generate_state_capsule(
        ROOT,
        registry_complete=True,
        composition_valid=True,
        version_lint_valid=True,
        shadow_happy_path=False,
        failure_matrix_valid=False,
        target=target,
        deterministic=True,
    )
    shadow = run_required_shadow_matrix(
        ROOT,
        contract=target.selected_contract,
        state_capsule=capsule,
        registry_receipt=registry,
        composition_receipt=composition,
    )
    agent = run_agent_check(ROOT, target=target, execute_incident_regressions=False)
    assert composition["provider_contract_version"] == "V16"
    assert capsule["selected_runtime_target"]["selected_provider_contract_version"] == "V16"
    assert {receipt["provider_contract_version"] for receipt in shadow.values()} == {"V16"}
    assert agent["selected_runtime_target"]["selected_provider_contract_version"] == "V16"
    assert agent["selected_composition_semantic_sha256"] == composition["semantic_sha256"]


def test_output_root_contract_rejects_escape_symlink_partial_and_sealed(
    tmp_path: Path,
) -> None:
    target = resolve_selected_runtime_target(ROOT)
    repository = tmp_path / "repository"
    (repository / "control/receipts/packages").mkdir(parents=True)
    with pytest.raises(ValueError, match="exact repository-relative"):
        cli._new_receipt_output_path(repository, Path("../v16"), target=target)
    with pytest.raises(ValueError, match="exact repository-relative"):
        cli._new_receipt_output_path(repository, repository / "v16", target=target)

    symlink_root = repository / "control/receipts/packages/v16"
    symlink_root.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="symbolic link"):
        cli._new_receipt_output_path(
            repository,
            Path("control/receipts/packages/v16"),
            target=target,
        )
    symlink_root.unlink()

    linked_parent_repository = tmp_path / "linked-parent-repository"
    (linked_parent_repository / "control/receipts").mkdir(parents=True)
    (linked_parent_repository / "control/receipts/packages").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="symbolic link"):
        cli._new_receipt_output_path(
            linked_parent_repository,
            Path("control/receipts/packages/v16"),
            target=target,
        )

    symlink_root.mkdir()
    (symlink_root / "partial.json").write_text("{}\n", encoding="utf-8")
    assert (
        cli._new_receipt_output_path(
            repository,
            Path("control/receipts/packages/v16"),
            target=target,
        )
        == symlink_root
    )
    recovery = cli._recover_unsealed_receipt_root(symlink_root)
    assert recovery == repository / "control/receipts/packages/.v16-unowned-partial-recovery"
    assert not symlink_root.exists()
    assert recovery is not None and (recovery / "partial.json").is_file()
    shutil.rmtree(recovery)

    symlink_root.mkdir()
    (symlink_root / "t09-control-receipt-bindings.json").write_text("{}\n")
    with pytest.raises(ValueError, match="sealed"):
        cli._new_receipt_output_path(
            repository,
            Path("control/receipts/packages/v16"),
            target=target,
        )


def test_synthetic_successor_full_aggregate_and_receipt_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "synthetic-repository"
    copy_working_repository(ROOT, repository)
    shared_before = {
        relative: hashlib.sha256((repository / relative).read_bytes()).hexdigest()
        for relative in REQUIRED_SHARED_SOURCES
    }
    identities = materialize_synthetic_successor(ROOT, repository)
    commit, tree = commit_repository(repository)
    contract = synthetic_contract(identities, source_commit=commit)
    install_synthetic_registry(monkeypatch, contract)
    _disable_nested_incident_subprocesses(monkeypatch)
    target = resolve_selected_runtime_target(repository)

    registry = validate_registry_completeness(repository)
    assert registry["complete"] is True
    assert registry["contract_count"] == 15
    composition = compose_control_plane(
        repository,
        contract=target.selected_contract,
        registry_receipt=registry,
    )
    assert composition["static_composition_valid"] is True
    assert composition["provider_contract_version"] == "V17"
    capsule = generate_state_capsule(
        repository,
        registry_complete=True,
        composition_valid=True,
        version_lint_valid=True,
        shadow_happy_path=False,
        failure_matrix_valid=False,
        target=target,
        deterministic=True,
    )
    shadow = run_required_shadow_matrix(
        repository,
        contract=target.selected_contract,
        state_capsule=capsule,
        registry_receipt=registry,
        composition_receipt=composition,
    )
    assert set(shadow) == set(ALL_REQUIRED_SCENARIOS)
    assert all(receipt["scenario_valid"] is True for receipt in shadow.values())
    assert shadow[HAPPY_PATH]["terminal_state"] == "category3-shadow-complete-clean"
    for scenario, receipt in shadow.items():
        expected = None if scenario == "lifecycle-unsupported" else identities["command_sha256"]
        assert receipt["command_package_sha256"] == expected

    agent = run_agent_check(
        repository,
        target=target,
        execute_incident_regressions=False,
    )
    assert agent["complete"] is True
    assert agent["selected_runtime_target"]["selected_provider_contract_version"] == "V17"

    assert cli.main(["compose", "--repository", str(repository)]) == 0
    cli_composition = json.loads(capsys.readouterr().out)
    assert cli_composition["selected_runtime_target"]["selected_provider_contract_version"] == "V17"
    assert set(cli_composition["receipts"]) == {"V17"}

    assert cli.main(["state-capsule", "--repository", str(repository), "--deterministic"]) == 0
    cli_capsule = json.loads(capsys.readouterr().out)
    assert cli_capsule["selected_runtime_target"]["selected_provider_contract_version"] == "V17"
    assert (
        cli.main(
            [
                "shadow",
                "--repository",
                str(repository),
                "--scenario",
                "happy-path",
            ]
        )
        == 0
    )
    cli_shadow = json.loads(capsys.readouterr().out)
    assert cli_shadow["provider_contract_version"] == "V17"

    output_relative = Path("control/receipts/packages/v17")
    assert (
        cli.main(
            [
                "refresh-receipts",
                "--repository",
                str(repository),
                "--output-root",
                output_relative.as_posix(),
            ]
        )
        == 0
    )
    refresh = json.loads(capsys.readouterr().out)
    output = repository / output_relative
    assert refresh["complete"] is True
    assert refresh["control_commit"] == commit
    assert refresh["control_tree"] == tree
    assert (output / "v17-composition.json").is_file()
    binding = json.loads((output / "t09-control-receipt-bindings.json").read_bytes())
    selected = binding["selected_runtime_target"]
    assert selected["selected_provider_contract_version"] == "V17"
    assert selected["selected_plan_id"] == "PLAN-EXP0001-PILOT-V17"
    assert selected["selected_command_package_sha256"] == identities["command_sha256"]
    artifact_paths: list[str] = []
    for key, value in binding["artifacts"].items():
        if key == "shadow_failures":
            artifact_paths.extend(item["path"] for item in value.values())
        else:
            artifact_paths.append(value["path"])
    assert artifact_paths
    assert all(
        not Path(path).is_absolute() and ".." not in Path(path).parts for path in artifact_paths
    )
    assert all((output / path).is_file() for path in artifact_paths)

    shared_after = {
        relative: hashlib.sha256((repository / relative).read_bytes()).hexdigest()
        for relative in REQUIRED_SHARED_SOURCES
    }
    assert shared_after == shared_before
    assert not (ROOT / V17_PLAN).exists()
    assert not (ROOT / "control/receipts/packages/v17").exists()
    assert not (
        ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/"
        "T09_PILOT_COMMAND_MANIFESTS_V17.json"
    ).exists()


def test_two_equivalent_successor_receipt_trees_are_byte_identical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = tmp_path / "first"
    copy_working_repository(ROOT, first)
    identities = materialize_synthetic_successor(ROOT, first)
    commit, _tree = commit_repository(first)
    contract = synthetic_contract(identities, source_commit=commit)
    install_synthetic_registry(monkeypatch, contract)
    _disable_nested_incident_subprocesses(monkeypatch)
    second = tmp_path / "second"
    shutil.copytree(first, second, symlinks=True)
    arguments = ["refresh-receipts", "--output-root", "control/receipts/packages/v17"]
    assert cli.main([*arguments, "--repository", str(first)]) == 0
    capsys.readouterr()
    assert cli.main([*arguments, "--repository", str(second)]) == 0
    capsys.readouterr()
    first_root = first / "control/receipts/packages/v17"
    second_root = second / "control/receipts/packages/v17"
    first_files = sorted(path.relative_to(first_root) for path in first_root.rglob("*.json"))
    second_files = sorted(path.relative_to(second_root) for path in second_root.rglob("*.json"))
    assert first_files == second_files
    assert {
        path: hashlib.sha256((first_root / path).read_bytes()).hexdigest() for path in first_files
    } == {
        path: hashlib.sha256((second_root / path).read_bytes()).hexdigest() for path in second_files
    }
