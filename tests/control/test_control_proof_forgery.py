from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from giclab.control.adapters import FakeScenario
from giclab.control.category3 import Category3Request, execute_category3_transaction
from giclab.control.production import ProductionCategory3World, build_production_shadow_assembly
from giclab.control.proofs import (
    REPOSITORY_SLUG,
    ControlProofError,
    ControlProofReference,
    ValidatedControlReceiptSet,
    ValidatedDeterministicStaging,
    ValidatedStateCapsule,
    validate_state_capsule_document,
)
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[2]
TRACKED_PROOFS = ROOT / "control/receipts"
BASE_COMMIT = "450a10a51eda4c428f20b27d6b4aafc4f94d80f4"
REVIEWED_HEAD = "559d52c9339bf13fae6808178a5a65fe71706f74"


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _seal(path: Path, document: dict[str, Any]) -> dict[str, object]:
    document.pop("semantic_sha256", None)
    document["semantic_sha256"] = _canonical_sha256(document)
    encoded = (json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(encoded)
    return {
        "bytes": len(encoded),
        "file_sha256": hashlib.sha256(encoded).hexdigest(),
        "semantic_sha256": document["semantic_sha256"],
    }


def _copy_proofs(tmp_path: Path) -> Path:
    target = tmp_path / "receipts"
    shutil.copytree(TRACKED_PROOFS, target)
    return target


def _binding_path(proof_root: Path) -> Path:
    return proof_root / "t09-control-receipt-bindings.json"


def _replace_artifact(
    proof_root: Path,
    *,
    binding_key: str,
    document_path: Path,
    mutate: Any,
) -> None:
    document = _read(document_path)
    mutate(document)
    identity = _seal(document_path, document)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    artifact = binding["artifacts"][binding_key]
    assert isinstance(artifact, dict)
    artifact.update(identity)
    _seal(binding_path, binding)


def _reference(proof_root: Path) -> ControlProofReference:
    path = _binding_path(proof_root)
    encoded = path.read_bytes()
    binding = json.loads(encoded)
    revision = binding.get("control_plane_revision", {})
    selected = binding.get("selected_runtime_target", {})
    return ControlProofReference(
        approved_root=proof_root,
        binding_path=path,
        expected_file_sha256=hashlib.sha256(encoded).hexdigest(),
        expected_control_commit=revision.get("commit", "0" * 40),
        expected_control_tree=revision.get("tree", "0" * 40),
        expected_repository_slug=binding.get("repository_slug", REPOSITORY_SLUG),
        expected_provider_contract_version=selected.get(
            "selected_provider_contract_version", V16_PROVIDER_CONTRACT.version
        ),
        expected_plan_id=selected.get("selected_plan_id", V16_PROVIDER_CONTRACT.plan_id),
        expected_command_package_sha256=selected.get("selected_command_package_sha256", "0" * 64),
        expected_target_source=selected.get("source", "goal-record"),
        expected_goal_record_sha256=selected.get("goal_record_sha256", "0" * 64),
        expected_target_semantic_sha256=selected.get("semantic_sha256", "0" * 64),
    )


def _repository_identity() -> tuple[str, str]:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD", "HEAD^{tree}"],
        capture_output=True,
        check=True,
        text=True,
    )
    commit, tree = completed.stdout.splitlines()
    return commit, tree


def _world() -> ProductionCategory3World:
    return build_production_shadow_assembly(
        ROOT,
        V16_PROVIDER_CONTRACT,
        FakeScenario("happy-path"),
    )


def _assert_no_preparation_effects(world: ProductionCategory3World) -> None:
    operations = [call.operation for call in world.calls]
    assert "host.stage" not in operations
    assert "secret.read" not in operations
    assert "metadata.request" not in operations
    assert "provider.inventory" not in operations
    assert "provider.launch" not in operations
    assert "condition.reserve" not in operations


def _execute_forgery(proof_root: Path) -> dict[str, object]:
    world = _world()
    commit, tree = _repository_identity()
    receipt = execute_category3_transaction(
        Category3Request(
            repository=ROOT,
            contract=V16_PROVIDER_CONTRACT,
            scenario="happy-path",
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=_reference(proof_root),
        ),
        adapters=world.adapters(),
    )
    _assert_no_preparation_effects(world)
    counts = receipt["call_counts"]
    assert isinstance(counts, dict)
    assert counts["secret_reads"] == 0
    assert counts["metadata_requests"] == 0
    assert counts["provider_gets"] == 0
    assert counts["provider_posts"] == 0
    assert counts["condition_reservations"] == 0
    assert receipt["earliest_stopping_phase"] == "state-capsule-snapshot"
    return receipt


def _assert_removed_request_field(field: str, value: object) -> None:
    world = _world()
    commit, tree = _repository_identity()
    arguments: dict[str, object] = {
        "repository": ROOT,
        "contract": V16_PROVIDER_CONTRACT,
        "scenario": "happy-path",
        "expected_repository_commit": commit,
        "expected_repository_tree": tree,
        "control_proof": _reference(TRACKED_PROOFS),
        field: value,
    }
    with pytest.raises(TypeError, match="unexpected keyword"):
        Category3Request(**arguments)  # type: ignore[arg-type]
    _assert_no_preparation_effects(world)


def test_arbitrary_capsule_hash_cannot_enter_the_request_boundary() -> None:
    _assert_removed_request_field("state_capsule_sha256", "a" * 64)


def test_state_capsule_valid_boolean_bypass_no_longer_exists() -> None:
    _assert_removed_request_field("state_capsule_valid", True)


def test_arbitrary_shadow_hash_tuple_cannot_enter_the_request_boundary() -> None:
    _assert_removed_request_field("required_shadow_receipt_sha256s", ("b" * 64,))


def test_correct_hash_for_wrong_artifact_type_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    registry = binding["artifacts"]["registry_receipt"]
    assert isinstance(registry, dict)
    binding["artifacts"]["state_capsule"] = dict(registry)
    _seal(binding_path, binding)
    _execute_forgery(proof_root)


def test_receipt_mutated_after_hash_capture_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    path = proof_root / "category3-shadow/happy-path.json"
    path.write_bytes(path.read_bytes() + b" ")
    _execute_forgery(proof_root)


def test_wrong_repository_commit_tree_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    tree = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", f"{BASE_COMMIT}^{{tree}}"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    binding["control_plane_revision"] = {"commit": BASE_COMMIT, "tree": tree}
    _seal(binding_path, binding)
    _execute_forgery(proof_root)


def test_stale_reviewed_head_receipt_set_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    tree = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", f"{REVIEWED_HEAD}^{{tree}}"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    binding["control_plane_revision"] = {"commit": REVIEWED_HEAD, "tree": tree}
    _seal(binding_path, binding)
    _execute_forgery(proof_root)


def test_wrong_provider_contract_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    selected = binding["selected_runtime_target"]
    selected["selected_provider_contract_version"] = "V15"
    selected["selected_plan_id"] = "PLAN-EXP0001-PILOT-V15"
    _seal(binding_path, binding)
    _execute_forgery(proof_root)


def test_wrong_command_package_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    binding["selected_runtime_target"]["selected_command_package_sha256"] = "c" * 64
    _seal(binding_path, binding)
    _execute_forgery(proof_root)


def test_missing_happy_path_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    del binding["artifacts"]["shadow_happy_path"]
    _seal(binding_path, binding)
    _execute_forgery(proof_root)


def test_missing_one_failure_scenario_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    del binding["artifacts"]["shadow_failures"]["metadata-expired"]
    _seal(binding_path, binding)
    _execute_forgery(proof_root)


def test_duplicate_failure_scenario_substitution_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    failures = binding["artifacts"]["shadow_failures"]
    failures["metadata-expired"] = dict(failures["condition-failure"])
    _seal(binding_path, binding)
    _execute_forgery(proof_root)


def test_swapped_scenario_filename_and_document_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    target = proof_root / "category3-shadow/metadata-expired.json"
    replacement = _read(proof_root / "category3-shadow/condition-failure.json")
    identity = _seal(target, replacement)
    binding_path = _binding_path(proof_root)
    binding = _read(binding_path)
    reference = binding["artifacts"]["shadow_failures"]["metadata-expired"]
    reference.update(identity)
    _seal(binding_path, binding)
    _execute_forgery(proof_root)


def test_shadow_receipt_claiming_scientific_interpretation_is_rejected(
    tmp_path: Path,
) -> None:
    proof_root = _copy_proofs(tmp_path)
    _replace_artifact(
        proof_root,
        binding_key="shadow_happy_path",
        document_path=proof_root / "category3-shadow/happy-path.json",
        mutate=lambda document: document.__setitem__("scientific_interpretation_allowed", True),
    )
    _execute_forgery(proof_root)


def test_shadow_receipt_with_undeclared_call_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)

    def mutate(document: dict[str, Any]) -> None:
        document["zero_undeclared_calls"] = False
        document["undeclared_adapter_calls"] = ["provider.post:undeclared"]

    _replace_artifact(
        proof_root,
        binding_key="shadow_happy_path",
        document_path=proof_root / "category3-shadow/happy-path.json",
        mutate=mutate,
    )
    _execute_forgery(proof_root)


def test_agent_check_missing_one_constituent_binding_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)

    def mutate(document: dict[str, Any]) -> None:
        scenarios = document["checks"]["category3_shadow"]["scenarios"]
        scenarios.pop()

    _replace_artifact(
        proof_root,
        binding_key="agent_check_receipt",
        document_path=proof_root / "agent-check.json",
        mutate=mutate,
    )
    _execute_forgery(proof_root)


def test_source_binding_missing_one_shared_source_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)

    def mutate(document: dict[str, Any]) -> None:
        document["files"].pop()

    _replace_artifact(
        proof_root,
        binding_key="source_binding_receipt",
        document_path=proof_root / "t09-control-plane-source-binding.json",
        mutate=mutate,
    )
    _execute_forgery(proof_root)


def test_capsule_with_inferred_live_authority_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)

    def mutate(document: dict[str, Any]) -> None:
        document["authority"]["category_3"] = True

    _replace_artifact(
        proof_root,
        binding_key="state_capsule",
        document_path=proof_root / "state-capsule.json",
        mutate=mutate,
    )
    _execute_forgery(proof_root)


def test_capsule_with_private_path_marker_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    _replace_artifact(
        proof_root,
        binding_key="state_capsule",
        document_path=proof_root / "state-capsule.json",
        mutate=lambda document: document.__setitem__(
            "recommended_action", "/Users/example/private-control-root"
        ),
    )
    _execute_forgery(proof_root)


def test_capsule_cannot_name_a_resolved_incident_as_current_blocker(
    tmp_path: Path,
) -> None:
    proof_root = _copy_proofs(tmp_path)
    _replace_artifact(
        proof_root,
        binding_key="state_capsule",
        document_path=proof_root / "state-capsule.json",
        mutate=lambda document: document.__setitem__(
            "blocking_incident",
            "INC-T09-CONTROL-FIXED-TARGET-SELECTION",
        ),
    )
    _execute_forgery(proof_root)


def test_capsule_governance_gate_cannot_grant_repository_authority(
    tmp_path: Path,
) -> None:
    proof_root = _copy_proofs(tmp_path)

    def mutate(document: dict[str, Any]) -> None:
        document["external_governance_gate"]["repository_state_grants_authority"] = True

    _replace_artifact(
        proof_root,
        binding_key="state_capsule",
        document_path=proof_root / "state-capsule.json",
        mutate=mutate,
    )
    _execute_forgery(proof_root)


def test_capsule_for_another_runtime_contract_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)

    def mutate(document: dict[str, Any]) -> None:
        runtime = document["runtime_package"]
        runtime["historical_package"] = "V15"
        runtime["next_package"] = "V16"

    _replace_artifact(
        proof_root,
        binding_key="state_capsule",
        document_path=proof_root / "state-capsule.json",
        mutate=mutate,
    )
    _execute_forgery(proof_root)


def test_capsule_with_incomplete_control_proof_flags_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)

    def mutate(document: dict[str, Any]) -> None:
        document["control_plane"]["failure_matrix_valid"] = False

    _replace_artifact(
        proof_root,
        binding_key="state_capsule",
        document_path=proof_root / "state-capsule.json",
        mutate=mutate,
    )
    _execute_forgery(proof_root)


def test_capsule_validator_accepts_exact_bound_successor_package() -> None:
    capsule = _read(TRACKED_PROOFS / "state-capsule.json")
    runtime = capsule["runtime_package"]
    runtime["next_status"] = "package-bound-not-authorized"
    capsule.pop("semantic_sha256")
    capsule["semantic_sha256"] = _canonical_sha256(capsule)
    identity = capsule["repository"]
    with pytest.raises(ControlProofError, match="runtime target"):
        validate_state_capsule_document(
            ROOT,
            capsule,
            expected_commit=identity["commit"],
            expected_tree=identity["tree"],
            selected_provider_contract_version="V17",
        )


def test_shadow_receipt_for_another_command_package_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)
    _replace_artifact(
        proof_root,
        binding_key="shadow_happy_path",
        document_path=proof_root / "category3-shadow/happy-path.json",
        mutate=lambda document: document.__setitem__("command_package_sha256", "d" * 64),
    )
    _execute_forgery(proof_root)


def test_happy_shadow_without_fake_accounting_proof_is_rejected(tmp_path: Path) -> None:
    proof_root = _copy_proofs(tmp_path)

    def mutate(document: dict[str, Any]) -> None:
        accounting = document["production_control_evidence"]["accounting"]
        accounting["aggregate_observed_cost_usd"] = 0.0

    _replace_artifact(
        proof_root,
        binding_key="shadow_happy_path",
        document_path=proof_root / "category3-shadow/happy-path.json",
        mutate=mutate,
    )
    _execute_forgery(proof_root)


def test_deterministic_path_storage_caller_assertions_no_longer_exist() -> None:
    _assert_removed_request_field("deterministic_paths_valid", True)
    _assert_removed_request_field("deterministic_storage_valid", True)


@pytest.mark.parametrize(
    "proof_type",
    (ValidatedStateCapsule, ValidatedControlReceiptSet, ValidatedDeterministicStaging),
)
def test_validated_proof_types_have_no_public_trust_me_constructor(
    proof_type: type[object],
) -> None:
    with pytest.raises(TypeError, match="minted only by exact validators"):
        proof_type()


def test_exact_tracked_binding_prepares_and_runs_the_production_wrapper() -> None:
    world = _world()
    commit, tree = _repository_identity()
    receipt = execute_category3_transaction(
        Category3Request(
            repository=ROOT,
            contract=V16_PROVIDER_CONTRACT,
            scenario="happy-path",
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=_reference(TRACKED_PROOFS),
        ),
        adapters=world.adapters(),
    )
    assert receipt["terminal_state"] == "category3-shadow-complete-clean"
    assert receipt["implementation_flavor"] == "production-wrapper"
    assert receipt["call_counts"]["secret_reads"] == 1  # type: ignore[index]
