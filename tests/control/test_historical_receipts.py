from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from _synthetic_successor import (
    commit_repository,
    copy_working_repository,
    install_synthetic_registry,
    materialize_synthetic_successor,
    synthetic_contract,
)

from giclab import validation
from giclab.control import agent_check as agent_check_module
from giclab.control import cli
from giclab.control.anti_shadow_lint import (
    public_receipt_topology_findings,
    validate_anti_shadow_lint,
)
from giclab.control.incidents import validate_incidents as validate_incidents_without_adapter
from giclab.control.proofs import (
    REPOSITORY_SLUG,
    ControlProofError,
    ControlProofReference,
    validate_control_receipt_set,
    validate_current_control_receipt_set,
)
from giclab.control.target import resolve_selected_runtime_target
from giclab.harness import t09_provider_contracts

ROOT = Path(__file__).resolve().parents[2]


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _seal(path: Path, document: dict[str, object]) -> None:
    document.pop("semantic_sha256", None)
    document["semantic_sha256"] = _canonical_sha256(document)
    path.write_text(
        json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _reference(receipt_root: Path) -> ControlProofReference:
    binding_path = receipt_root / "t09-control-receipt-bindings.json"
    encoded = binding_path.read_bytes()
    binding = json.loads(encoded)
    revision = binding["control_plane_revision"]
    selected = binding["selected_runtime_target"]
    return ControlProofReference(
        approved_root=receipt_root,
        binding_path=binding_path,
        expected_file_sha256=hashlib.sha256(encoded).hexdigest(),
        expected_control_commit=revision["commit"],
        expected_control_tree=revision["tree"],
        expected_repository_slug=binding.get("repository_slug", REPOSITORY_SLUG),
        expected_provider_contract_version=selected["selected_provider_contract_version"],
        expected_plan_id=selected["selected_plan_id"],
        expected_command_package_sha256=selected["selected_command_package_sha256"],
        expected_target_source=selected["source"],
        expected_goal_record_sha256=selected["goal_record_sha256"],
        expected_target_semantic_sha256=selected["semantic_sha256"],
    )


@pytest.fixture(scope="module")
def successor_receipt_repository(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[Path, object]]:
    monkeypatch = pytest.MonkeyPatch()
    repository = tmp_path_factory.mktemp("historical-receipts") / "repository"
    copy_working_repository(ROOT, repository)
    identities = materialize_synthetic_successor(ROOT, repository)
    commit, _tree = commit_repository(repository)
    contract = synthetic_contract(identities, source_commit=commit)
    install_synthetic_registry(monkeypatch, contract)

    def validate_without_execution(
        selected_repository: Path,
        *,
        execute_regressions: bool = False,
    ) -> dict[str, object]:
        del execute_regressions
        return validate_incidents_without_adapter(
            selected_repository,
            execute_regressions=False,
        )

    monkeypatch.setattr(cli, "validate_incidents", validate_without_execution)
    monkeypatch.setattr(agent_check_module, "validate_incidents", validate_without_execution)
    result, complete = cli._command_refresh_receipts(
        argparse.Namespace(
            repository=repository,
            output_root=Path("control/receipts/packages/v17"),
            provider_contract=None,
        )
    )
    assert complete is True
    assert result["complete"] is True
    yield repository, contract
    monkeypatch.undo()


def test_synthetic_v17_and_retained_v16_roots_validate_simultaneously(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, v17_contract = successor_receipt_repository
    v16_contract = t09_provider_contracts.PROVIDER_CONTRACTS["V16"]
    v16_root = repository / "control/receipts"
    v17_root = repository / "control/receipts/packages/v17"
    historical = validate_control_receipt_set(
        repository,
        v16_contract,
        _reference(v16_root),
    )
    current = validate_current_control_receipt_set(
        repository,
        v17_contract,
        _reference(v17_root),
    )
    assert historical.provider_contract_version == "V16"
    assert current.provider_contract_version == "V17"
    assert validation.validate_tracked_control_receipts(repository) == []


def test_selected_v17_topology_receipt_names_exact_selected_root_and_retained_roots(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    receipt = json.loads(
        (repository / "control/receipts/packages/v17/anti-shadow-lint.json").read_bytes()
    )
    topology = receipt["public_receipt_topology_scan"]
    assert receipt["schema_version"] == "3.0.0"
    assert topology["selected_provider_contract_version"] == "V17"
    assert topology["selected_receipt_root"] == "control/receipts/packages/v17"
    assert topology["selected_root_matches_version"] is True
    assert topology["complete"] is True
    assert topology["findings"] == 0
    assert "control/receipts" in topology["sealed_roots_scanned"]
    assert "control/receipts/packages/v16" in topology["sealed_roots_scanned"]
    assert "control/receipts/packages/v17" in topology["sealed_roots_scanned"]
    assert all(
        topology["member_count_by_root"][root] > 0 for root in topology["sealed_roots_scanned"]
    )


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("runtime_path", "/tmp/selected-v17-runtime", "T09S023"),
        ("device", 17, "T09S024"),
        ("inode", 19, "T09S024"),
        ("uid", 23, "T09S024"),
    ],
)
def test_selected_v17_receipt_runtime_topology_is_rejected(
    successor_receipt_repository: tuple[Path, object],
    field: str,
    value: object,
    expected_code: str,
) -> None:
    repository, _v17_contract = successor_receipt_repository
    path = repository / "control/receipts/packages/v17/state-capsule.json"
    original = path.read_bytes()
    document = json.loads(original)
    document["third_rereview_topology_probe"] = {field: value}
    try:
        path.write_text(
            json.dumps(document, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        findings = public_receipt_topology_findings(repository)
    finally:
        path.write_bytes(original)
    assert expected_code in {finding.code for finding in findings}


def test_selected_v17_bound_goal_record_is_topology_scanned(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    path = repository / "control/receipts/packages/v17/bound-goal-record.yaml"
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"third_rereview_runtime_path: /tmp/private-root\n")
        findings = public_receipt_topology_findings(repository)
    finally:
        path.write_bytes(original)
    assert "T09S023" in {finding.code for finding in findings}
    assert any(finding.path.endswith("bound-goal-record.yaml") for finding in findings)


def test_anti_shadow_declared_marker_exception_does_not_hide_another_field(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    path = repository / "control/receipts/packages/v17/anti-shadow-lint.json"
    original = path.read_bytes()
    document = json.loads(original)
    document["third_rereview_runtime_path_probe"] = "/tmp/selected-v17-runtime"
    try:
        path.write_text(
            json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        findings = public_receipt_topology_findings(repository)
    finally:
        path.write_bytes(original)
    assert any(
        finding.code == "T09S023" and finding.path.endswith("anti-shadow-lint.json")
        for finding in findings
    )


def test_selected_v17_scan_rejects_bound_omission_and_unbound_extra(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    root = repository / "control/receipts/packages/v17"
    bound = root / "state-capsule.json"
    omitted = repository / ".third-rereview-state-capsule.omitted"
    bound.rename(omitted)
    try:
        omission_findings = public_receipt_topology_findings(repository)
    finally:
        omitted.rename(bound)
    assert any(
        finding.code == "T09S027"
        and finding.path.endswith("state-capsule.json")
        and "omitted" in finding.message
        for finding in omission_findings
    )

    extra = root / "third-rereview-unbound.txt"
    try:
        extra.write_text("no runtime topology\n", encoding="utf-8")
        extra_findings = public_receipt_topology_findings(repository)
    finally:
        extra.unlink(missing_ok=True)
    assert any(
        finding.code == "T09S027"
        and finding.path.endswith("third-rereview-unbound.txt")
        and "unbound" in finding.message
        for finding in extra_findings
    )


def test_restored_selected_v17_and_retained_v16_topology_both_validate(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    target = resolve_selected_runtime_target(repository)
    receipt = validate_anti_shadow_lint(repository, target=target)
    assert receipt["complete"] is True
    topology = receipt["public_receipt_topology_scan"]
    assert topology["selected_provider_contract_version"] == "V17"
    assert topology["selected_receipt_root"] == "control/receipts/packages/v17"
    assert topology["findings"] == 0


def test_direct_historical_v16_validation_ignores_current_v17_goal_selection(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    v16_contract = t09_provider_contracts.PROVIDER_CONTRACTS["V16"]
    receipt = validate_control_receipt_set(
        repository,
        v16_contract,
        _reference(repository / "control/receipts"),
    )
    assert receipt.provider_contract_version == "V16"


def test_historical_v16_root_is_rejected_as_the_current_v17_root(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    v16_contract = t09_provider_contracts.PROVIDER_CONTRACTS["V16"]
    with pytest.raises(ControlProofError, match="current goal"):
        validate_current_control_receipt_set(
            repository,
            v16_contract,
            _reference(repository / "control/receipts"),
        )


def test_changed_historical_goal_snapshot_fails(
    successor_receipt_repository: tuple[Path, object],
    tmp_path: Path,
) -> None:
    repository, _v17_contract = successor_receipt_repository
    proof_root = tmp_path / "v16-goal-drift"
    shutil.copytree(
        repository / "control/receipts",
        proof_root,
        ignore=shutil.ignore_patterns("packages"),
    )
    goal = proof_root / "bound-goal-record.yaml"
    goal.write_bytes(goal.read_bytes() + b"\n")
    binding_path = proof_root / "t09-control-receipt-bindings.json"
    binding = json.loads(binding_path.read_bytes())
    encoded_goal = goal.read_bytes()
    binding["artifacts"]["goal_record"] = {
        "path": "bound-goal-record.yaml",
        "bytes": len(encoded_goal),
        "file_sha256": hashlib.sha256(encoded_goal).hexdigest(),
    }
    selected = binding["selected_runtime_target"]
    selected["goal_record_sha256"] = hashlib.sha256(encoded_goal).hexdigest()
    selected["semantic_sha256"] = _canonical_sha256(
        {key: value for key, value in selected.items() if key != "semantic_sha256"}
    )
    _seal(binding_path, binding)
    with pytest.raises(ControlProofError, match="differs from its control commit"):
        validate_control_receipt_set(
            repository,
            t09_provider_contracts.PROVIDER_CONTRACTS["V16"],
            _reference(proof_root),
        )


def test_changed_historical_target_document_fails(
    successor_receipt_repository: tuple[Path, object],
    tmp_path: Path,
) -> None:
    repository, _v17_contract = successor_receipt_repository
    proof_root = tmp_path / "v16-target-drift"
    shutil.copytree(
        repository / "control/receipts",
        proof_root,
        ignore=shutil.ignore_patterns("packages"),
    )
    binding_path = proof_root / "t09-control-receipt-bindings.json"
    binding = json.loads(binding_path.read_bytes())
    selected = binding["selected_runtime_target"]
    selected["selected_plan_id"] = "PLAN-EXP0001-PILOT-V15"
    selected["semantic_sha256"] = _canonical_sha256(
        {key: value for key, value in selected.items() if key != "semantic_sha256"}
    )
    _seal(binding_path, binding)
    with pytest.raises(
        ControlProofError,
        match=r"bound goal/package state|another runtime target",
    ):
        validate_control_receipt_set(
            repository,
            t09_provider_contracts.PROVIDER_CONTRACTS["V16"],
            _reference(proof_root),
        )


def test_changed_v16_artifact_fails_while_v17_remains_valid(
    successor_receipt_repository: tuple[Path, object],
    tmp_path: Path,
) -> None:
    repository, v17_contract = successor_receipt_repository
    proof_root = tmp_path / "v16-artifact-drift"
    shutil.copytree(
        repository / "control/receipts",
        proof_root,
        ignore=shutil.ignore_patterns("packages"),
    )
    agent = proof_root / "agent-check.json"
    agent.write_bytes(agent.read_bytes() + b" ")
    with pytest.raises(ControlProofError, match="bound file bytes changed"):
        validate_control_receipt_set(
            repository,
            t09_provider_contracts.PROVIDER_CONTRACTS["V16"],
            _reference(proof_root),
        )
    validate_current_control_receipt_set(
        repository,
        v17_contract,
        _reference(repository / "control/receipts/packages/v17"),
    )


def test_added_conflicting_v16_artifact_fails_exact_root_inventory(
    successor_receipt_repository: tuple[Path, object],
    tmp_path: Path,
) -> None:
    repository, _v17_contract = successor_receipt_repository
    proof_root = tmp_path / "v16-added-conflict"
    shutil.copytree(
        repository / "control/receipts",
        proof_root,
        ignore=shutil.ignore_patterns("packages"),
    )
    (proof_root / "conflicting-receipt.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ControlProofError, match=r"conflicting=.*conflicting-receipt"):
        validate_control_receipt_set(
            repository,
            t09_provider_contracts.PROVIDER_CONTRACTS["V16"],
            _reference(proof_root),
        )


def test_removed_historical_v16_root_fails_root_inventory(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    binding = repository / "control/receipts/t09-control-receipt-bindings.json"
    removed = repository / "control/t09-control-receipt-bindings.removed"
    binding.rename(removed)
    try:
        errors = validation.validate_tracked_control_receipts(repository)
    finally:
        removed.rename(binding)
    assert any("historical legacy V16 receipt root is missing" in error for error in errors)


def test_duplicate_cross_root_v16_seal_fails_inventory(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    duplicate = repository / "control/receipts/packages/v16"
    retained_current = repository / "control/current-v16-receipt-root"
    had_current = duplicate.exists()
    if had_current:
        duplicate.rename(retained_current)
    shutil.copytree(
        repository / "control/receipts",
        duplicate,
        ignore=shutil.ignore_patterns("packages"),
    )
    try:
        errors = validation.validate_tracked_control_receipts(repository)
    finally:
        shutil.rmtree(duplicate)
        if had_current:
            retained_current.rename(duplicate)
    assert any("duplicate sealed roots select V16" in error for error in errors)


def test_v17_root_with_substituted_historical_v16_target_fails(
    successor_receipt_repository: tuple[Path, object],
    tmp_path: Path,
) -> None:
    repository, v17_contract = successor_receipt_repository
    proof_root = tmp_path / "v17-with-v16-target"
    shutil.copytree(repository / "control/receipts/packages/v17", proof_root)
    binding_path = proof_root / "t09-control-receipt-bindings.json"
    binding = json.loads(binding_path.read_bytes())
    historical_binding = json.loads(
        (repository / "control/receipts/t09-control-receipt-bindings.json").read_bytes()
    )
    binding["selected_runtime_target"] = historical_binding["selected_runtime_target"]
    _seal(binding_path, binding)
    with pytest.raises(ControlProofError, match="bound goal/package state"):
        validate_current_control_receipt_set(
            repository,
            v17_contract,
            _reference(proof_root),
        )


def test_historical_and_current_roots_never_grant_authority_or_science(
    successor_receipt_repository: tuple[Path, object],
) -> None:
    repository, _v17_contract = successor_receipt_repository
    for receipt_root in (
        repository / "control/receipts",
        repository / "control/receipts/packages/v17",
    ):
        binding = json.loads((receipt_root / "t09-control-receipt-bindings.json").read_bytes())
        assert set(binding["authority"].values()) == {False}
        assert set(binding["selected_runtime_target"]["authority"].values()) == {False}
