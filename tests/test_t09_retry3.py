from __future__ import annotations

import importlib.util
import json
import shutil
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness import t09_sira_pilot as pilot_state
from giclab.harness.t09_sira_pilot import (
    ATTEMPT_ORDER,
    T09BudgetExceeded,
    T09PilotError,
    canonical_sha256,
    initialize_pilot_state,
    mark_attempt_completed,
    mark_empirical_entry,
    mark_raw_attempt_complete,
    record_first_pair_checkpoint,
)
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
FINALIZER_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
REGRESSION_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py"
PROJECTION_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_finalizer_projection.py"
LOCAL_QUALIFICATION_SOURCE = (
    ROOT / "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py"
)
REAL_REGRESSION_RECEIPT = (
    ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/"
    "T09_PRAGMATIC_RETRY3_FINALIZER_REGRESSION.json"
)
RAW_FIXTURE = ROOT / "tests/fixtures/t09/finalizer-raw-shape"


def test_retry3_plan_has_a_typed_two_slot_raw_first_contract() -> None:
    plan_path = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml"
    plan = yaml.safe_load(plan_path.read_bytes())
    assert validate_instance(plan, ROOT / "schemas/run-profile.schema.json") == []
    assert plan["provider_lifecycle"]["max_launch_count"] == 2
    assert plan["provider_lifecycle"]["replacement_launch_rule"] == {
        "allowed_only_before_empirical_entry": True,
        "prior_instance_terminal_and_absent_required": True,
        "prior_host_empirical_attempts_required": 0,
        "prior_host_model_requests_required": 0,
        "prior_host_browser_actions_required": 0,
        "ownership_outcome_unknown_forbidden": True,
        "cumulative_lambda_cap_required": True,
    }


def _load(path: Path, name: str) -> object:
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _select(
    state: Path,
    run_id: str,
    *,
    source: str = "1" * 64,
    commit: str = "a" * 40,
    dependencies: str = "2" * 64,
    evaluator: str = "3" * 64,
    semantic: str = "6" * 64,
    receipt: str = "4" * 64,
) -> None:
    mark_attempt_completed(
        state,
        execution_contract_sha256="f" * 64,
        run_id=run_id,
        finalizer_execution_mode="qualified-image",
        finalizer_runtime_qualification_sha256="0" * 64,
        finalizer_source_sha256=source,
        finalizer_projection_source_sha256="5" * 64,
        finalizer_commit=commit,
        finalizer_dependency_manifest_sha256=dependencies,
        evaluator_contract_sha256=evaluator,
        interpreter="/opt/sira/.venv/bin/python",
        interpreter_sha256="e" * 64,
        semantic_projection_sha256=semantic,
        finalized_output_root=f"finalized/{run_id}/{receipt}",
        finalization_complete_sha256=receipt,
    )


def test_retry3_state_separates_raw_progress_from_reselectable_finalization(
    tmp_path: Path,
) -> None:
    state = tmp_path / "pilot-state.json"
    initialize_pilot_state(
        state,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    mark_empirical_entry(state, execution_contract_sha256="f" * 64, run_id=ATTEMPT_ORDER[0])
    mark_raw_attempt_complete(
        state,
        execution_contract_sha256="f" * 64,
        run_id=ATTEMPT_ORDER[0],
        raw_manifest_sha256="5" * 64,
        raw_receipt_sha256="6" * 64,
    )
    # Downstream finalization may lag without reopening the consumed condition.
    mark_empirical_entry(state, execution_contract_sha256="f" * 64, run_id=ATTEMPT_ORDER[1])
    mark_raw_attempt_complete(
        state,
        execution_contract_sha256="f" * 64,
        run_id=ATTEMPT_ORDER[1],
        raw_manifest_sha256="7" * 64,
        raw_receipt_sha256="8" * 64,
    )
    _select(state, ATTEMPT_ORDER[1])
    _select(state, ATTEMPT_ORDER[0], source="9" * 64)
    with pytest.raises(T09PilotError, match="uniform"):
        record_first_pair_checkpoint(
            state,
            execution_contract_sha256="f" * 64,
            decision={"decision": "continue-to-task-b"},
            decided_at_epoch=2.0,
        )
    # A repaired downstream version may be selected for an already finalized attempt.
    _select(state, ATTEMPT_ORDER[0])
    record_first_pair_checkpoint(
        state,
        execution_contract_sha256="f" * 64,
        decision={"decision": "continue-to-task-b"},
        decided_at_epoch=2.0,
    )
    with pytest.raises(T09PilotError, match="semantic projection"):
        _select(state, ATTEMPT_ORDER[0], source="7" * 64, semantic="8" * 64)
    blocked = json.loads(state.read_text(encoding="utf-8"))
    assert blocked["first_pair_selection_drift_detected"] is True
    assert blocked["first_pair_decision"] == "stop-before-task-b"
    with pytest.raises(T09BudgetExceeded, match="checkpoint"):
        mark_empirical_entry(
            state,
            execution_contract_sha256="f" * 64,
            run_id=ATTEMPT_ORDER[2],
        )
    retained = json.loads(state.read_text(encoding="utf-8"))
    assert retained["raw_attempts_complete"] == list(ATTEMPT_ORDER[:2])
    assert retained["attempts_completed"] == list(ATTEMPT_ORDER[:2])
    assert len(retained["attempt_finalization_history"][ATTEMPT_ORDER[0]]) == 2
    selection_root = state.parent / "finalization-selections" / ATTEMPT_ORDER[0]
    receipts = sorted(selection_root.glob("selection-*.json"))
    assert len(receipts) == 2
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in receipts)
    checkpoint = retained["first_pair_checkpoint_binding"]
    assert (
        checkpoint["selection_receipt_sha256s"][ATTEMPT_ORDER[0]]
        == (retained["attempt_finalization_history"][ATTEMPT_ORDER[0]][-1])
    )


def test_retry3_selection_receipt_crash_is_reconciled_without_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "pilot-state.json"
    initialize_pilot_state(
        state,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    mark_empirical_entry(state, execution_contract_sha256="f" * 64, run_id=ATTEMPT_ORDER[0])
    mark_raw_attempt_complete(
        state,
        execution_contract_sha256="f" * 64,
        run_id=ATTEMPT_ORDER[0],
        raw_manifest_sha256="1" * 64,
        raw_receipt_sha256="2" * 64,
    )
    original = pilot_state._write_json_atomic

    def crash_before_projection(_path: Path, _document: object) -> None:
        raise OSError("fixture state projection crash")

    monkeypatch.setattr(pilot_state, "_write_json_atomic", crash_before_projection)
    with pytest.raises(OSError, match="projection crash"):
        _select(state, ATTEMPT_ORDER[0])
    receipt = state.parent / "finalization-selections" / ATTEMPT_ORDER[0] / "selection-0001.json"
    assert receipt.is_file()
    retained_before = receipt.read_bytes()
    monkeypatch.setattr(pilot_state, "_write_json_atomic", original)
    _select(state, ATTEMPT_ORDER[0])
    assert receipt.read_bytes() == retained_before
    projected = json.loads(state.read_text(encoding="utf-8"))
    assert projected["attempt_finalization_history"][ATTEMPT_ORDER[0]] == [
        pilot_state.file_sha256(receipt)
    ]
    projected["attempts_completed"] = []
    projected["attempt_finalizations"] = {}
    state.write_text(json.dumps(projected), encoding="utf-8")
    with pytest.raises(T09PilotError, match="projection of its selection history"):
        _select(state, ATTEMPT_ORDER[0])


def test_retry3_finalizer_is_pure_and_host_mounts_only_one_derived_root_rw() -> None:
    source = FINALIZER_SOURCE.read_text(encoding="utf-8")
    assert "mark_attempt_completed" not in source
    assert "record_first_pair_checkpoint" not in source
    assert '"--pilot-state"' not in source
    assert '"--aggregate-ledger"' not in source
    assert '"/opt/giclab-raw"' in source
    assert '"/opt/giclab-finalized"' in source
    host_source = HOST_SOURCE.read_text(encoding="utf-8")
    assert "type=bind,src={raw_root},dst=/opt/giclab-raw,readonly" in host_source
    assert "type=bind,src={finalized_root},dst=/opt/giclab-finalized" in host_source
    assert "type=bind,src={control_root},dst=/opt/giclab-control,readonly" in host_source
    assert '"--entrypoint",\n            "/opt/sira/.venv/bin/python"' in host_source
    assert '"--network",\n            "none"' in host_source
    assert '"interpreter_sha256"' in host_source
    assert 'frozen_manifest["python_interpreter_sha256"]' in host_source
    assert "interpreter_path = Path(sys.executable)" in source
    assert 'interpreter_path.as_posix() != "/opt/sira/.venv/bin/python"' in source
    assert 'local_qualification.get("interpreter_sha256") != interpreter_sha256' in source
    completion_write = host_source.index("write_exclusive(completion_path, completion)")
    state_selection = host_source.index("mark_attempt_completed(", completion_write)
    assert completion_write < state_selection
    finalizer_entry = host_source.index("def finalize_attempt(")
    acknowledgement_gate = host_source.index(
        "require_attempt_export_acknowledgement(", finalizer_entry
    )
    finalization_allocation = host_source.index(
        'finalization_log_base = attempt_root / "finalizer-invocations"', finalizer_entry
    )
    assert acknowledgement_gate < finalization_allocation


def test_retry3_privacy_safe_fixture_uses_production_semantic_primitive() -> None:
    finalizer = _load(FINALIZER_SOURCE, "giclab_t09_retry3_finalizer_fixture")
    projection = finalizer.reconstruct_semantic_projection(  # type: ignore[attr-defined]
        raw_root=RAW_FIXTURE,
        evaluator_root=ROOT / "tests/fixtures/t09/pinned-evaluator",
        dataset_path=ROOT / "tests/fixtures/t09/fanout-two-task-fixture.json",
        task_index=0,
        task_id="7dcbbbdc7f1120cd",
        condition="SIRA-REACTIVE",
        evaluator_fixture_subset=True,
    )
    repeated = finalizer.reconstruct_semantic_projection(  # type: ignore[attr-defined]
        raw_root=RAW_FIXTURE,
        evaluator_root=ROOT / "tests/fixtures/t09/pinned-evaluator",
        dataset_path=ROOT / "tests/fixtures/t09/fanout-two-task-fixture.json",
        task_index=0,
        task_id="7dcbbbdc7f1120cd",
        condition="SIRA-REACTIVE",
        evaluator_fixture_subset=True,
    )
    assert repeated == projection
    assert canonical_sha256(repeated) == canonical_sha256(projection)
    assert projection["task_completed"] is True
    assert projection["answer_produced"] is True
    assert projection["evaluator_valid"] is True
    assert projection["score"] == 0.0
    assert projection["provider_call_count"] == 1
    assert projection["browser_action_count"] == 1


def test_retry3_real_regression_has_bounded_safe_archive_surface() -> None:
    regression = _load(REGRESSION_SOURCE, "giclab_t09_retry3_regression_contract")
    assert regression.MAX_ARCHIVE_BYTES == 100_663_296  # type: ignore[attr-defined]
    assert regression.MAX_MEMBERS == 2_048  # type: ignore[attr-defined]
    assert {  # type: ignore[attr-defined]
        "attempt-outcome.json",
        "evidence-index.json",
    } == regression.COMPARISON_MEMBERS
    assert "../escape" not in regression.RAW_EXACT_MEMBERS  # type: ignore[attr-defined]


def test_retry3_real_regression_receipt_binds_full_evaluator_and_repeat() -> None:
    receipt = json.loads(REAL_REGRESSION_RECEIPT.read_text(encoding="utf-8"))
    assert receipt["dataset_sha256"] == (
        "359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288"
    )
    assert receipt["dataset_bytes"] == 1_177_174
    assert receipt["finalizer_source_sha256"] == pilot_state.file_sha256(FINALIZER_SOURCE)
    closure = receipt["evaluator_closure"]
    assert closure["evaluator_contract_sha256"] == (
        "c28a802a45fc8d1e719f8c1bcb22315c2841df831c4ae161f12ab0f2fd08b321"
    )
    assert len(closure["dependency_package_records"]) == 51
    repeats = receipt["deterministic_distinct_finalization_roots"]
    assert [item["root"] for item in repeats] == ["finalization-0001", "finalization-0002"]
    assert {item["semantic_projection_sha256"] for item in repeats} == {
        receipt["semantic_projection_sha256"]
    }
    assert receipt["additional_model_requests"] == 0
    assert receipt["additional_browser_actions"] == 0


def test_retry3_frozen_regression_remains_package_bound_during_finalizer_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_frozen_regression_binding")
    receipt = json.loads(REAL_REGRESSION_RECEIPT.read_text(encoding="utf-8"))
    expected_source = receipt["finalizer_source_sha256"]
    original_file_sha256 = host.file_sha256  # type: ignore[attr-defined]

    def changed_worktree_finalizer(path: Path) -> str:
        if path.resolve() == FINALIZER_SOURCE.resolve():
            return "f" * 64
        return original_file_sha256(path)

    monkeypatch.setattr(host, "file_sha256", changed_worktree_finalizer)
    accepted = host.validate_real_evidence_regression(  # type: ignore[attr-defined]
        ROOT,
        expected_finalizer_source_sha256=expected_source,
    )
    assert accepted["finalizer_source_sha256"] == expected_source
    with pytest.raises(host.T09HostError, match="real-evidence finalizer regression"):
        host.validate_real_evidence_regression(ROOT)  # type: ignore[attr-defined]


def test_retry3_local_finalizer_projection_is_explicit_and_provider_independent() -> None:
    projection = _load(PROJECTION_SOURCE, "giclab_t09_retry3_local_projection")
    invocation = projection.build_local_finalizer_invocation(  # type: ignore[attr-defined]
        interpreter="/qualified/python3.11",
        dependency_site_packages="/qualified/evaluator-site",
        repository_source_root="/package/src",
        finalizer_source="/package/t09_evaluate_attempt.py",
        execution_contract="/package/execution.json",
        execution_contract_sha256="1" * 64,
        command_manifests="/package/commands.json",
        command_manifests_sha256="2" * 64,
        condition_plan="/package/condition.yaml",
        raw_root="/verified/raw",
        raw_output_relative="artifacts/raw",
        finalized_root="/derived/finalization-0001",
        finalized_output_relative="artifacts/finalized/finalization-0001",
        artifact_root="/verified",
        raw_attempt_manifest="/verified/raw-attempt-manifest.json",
        raw_attempt_receipt="/verified/raw-attempt-complete.json",
        run_id=ATTEMPT_ORDER[0],
        package_commit="a" * 40,
        finalizer_commit="b" * 40,
        finalizer_source_sha256="3" * 64,
        finalizer_projection_source_sha256="4" * 64,
        finalizer_dependency_manifest_sha256="5" * 64,
        frozen_run_manifest="/verified/frozen-run-manifest.json",
        frozen_run_manifest_sha256="6" * 64,
        replacement_image_id="sha256:" + "7" * 64,
        host_cleanup_receipt="/verified/raw/host-cleanup-receipt.json",
        evaluator_root="/qualified/evaluator",
        evaluator_overlay_revalidation="/derived/overlay.json",
        dataset="/qualified/fanout-final-dev.json",
        score_schema="/package/score.schema.json",
        evidence_schema="/package/evidence.schema.json",
        runtime_qualification="/qualified/local-finalizer.json",
        runtime_qualification_sha256="8" * 64,
    )
    assert invocation["argv"][:2] == [
        "/qualified/python3.11",
        "/package/t09_evaluate_attempt.py",
    ]
    assert invocation["environment"] == {
        "PYTHONPATH": "/qualified/evaluator-site:/package/src",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "CUDA_VISIBLE_DEVICES": "",
    }
    assert invocation["network"] == "socket-construction-denied"
    assert all("provider" not in token.lower() for token in invocation["argv"])
    local_source = LOCAL_QUALIFICATION_SOURCE.read_text(encoding="utf-8")
    assert "local_finalizer_base_packages" in local_source
    assert "socket.socket = denied" in local_source
    host_source = HOST_SOURCE.read_text(encoding="utf-8")
    assert "require_local_runtime=True" in host_source
    assert "if local_mode\n        else scientific_seconds_remaining" in host_source
    assert "MAX_FINALIZER_INVOCATIONS_PER_ATTEMPT" not in host_source
    assert 'network="socket-construction-denied" if local_mode else "none"' in host_source
    assert "def restore_verified_attempt_export(" in host_source
    assert "require_attempt_export_acknowledgement(" in host_source


def test_retry3_selected_local_completion_reconstructs_and_opens_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_selected_local")
    run_id = ATTEMPT_ORDER[0]
    package_commit = "a" * 40
    artifact_root = tmp_path / "artifacts"
    attempt = SimpleNamespace(
        output_root="attempt",
        raw_output_root="attempt/raw",
        finalized_output_root="attempt/finalized",
    )
    attempt_root = artifact_root / attempt.output_root
    raw_root = artifact_root / attempt.raw_output_root
    finalized_root = artifact_root / attempt.finalized_output_root / "local-invocation-0001"
    raw_root.mkdir(parents=True)
    finalized_root.mkdir(parents=True)
    raw_manifest = {"raw": "manifest"}
    raw_receipt = {"raw": "receipt"}
    host.write_exclusive(attempt_root / "raw-attempt-manifest.json", raw_manifest)
    host.write_exclusive(attempt_root / "raw-attempt-complete.json", raw_receipt)
    outcome = {"valid_scored_attempt": True, "task_score": 0.0}
    evidence = {"identity": {"run_id": run_id}}
    semantic = {"run_id": run_id, "score": 0.0}
    for name, value in (
        ("attempt-outcome.json", outcome),
        ("evidence-index.json", evidence),
        ("semantic-projection.json", semantic),
    ):
        host.write_exclusive(finalized_root / name, value)
    output_files = [
        {
            "path": name,
            "bytes": (finalized_root / name).stat().st_size,
            "sha256": host.file_sha256(finalized_root / name),
        }
        for name in (
            "attempt-outcome.json",
            "evidence-index.json",
            "semantic-projection.json",
        )
    ]
    closure = {
        "finalizer_execution_mode": "qualified-local",
        "finalizer_runtime_qualification_sha256": "0" * 64,
        "finalizer_commit": "b" * 40,
        "finalizer_source_sha256": "1" * 64,
        "finalizer_projection_source_sha256": "2" * 64,
        "scientific_package_commit": package_commit,
        "pilot_library_sha256": "3" * 64,
        "interpreter": "/qualified/python3.11",
        "interpreter_sha256": "4" * 64,
        "replacement_image_id": "sha256:" + "5" * 64,
        "execution_contract_sha256": "6" * 64,
        "command_manifests_sha256": "7" * 64,
        "dataset_contract_sha256": "8" * 64,
        "evaluator_contract_sha256": "9" * 64,
        "score_schema_sha256": "c" * 64,
        "evidence_schema_sha256": "d" * 64,
        "evaluator_overlay_entries_sha256": "e" * 64,
        "evaluator_overlay_packages_sha256": "f" * 64,
    }
    completion = {
        "schema_version": "0.1.0",
        "plan_id": host.PLAN_ID,
        "host_run_id": host.HOST_RUN_ID,
        "run_id": run_id,
        "raw_manifest_sha256_before": host.file_sha256(attempt_root / "raw-attempt-manifest.json"),
        "raw_manifest_sha256_after": host.file_sha256(attempt_root / "raw-attempt-manifest.json"),
        "raw_receipt_sha256": host.file_sha256(attempt_root / "raw-attempt-complete.json"),
        "raw_manifest_payload_sha256": host.canonical_sha256(raw_manifest),
        "raw_receipt_payload_sha256": host.canonical_sha256(raw_receipt),
        "output_files": output_files,
        "output_files_sha256": host.canonical_sha256(output_files),
        "outcome_sha256": host.file_sha256(finalized_root / "attempt-outcome.json"),
        "evidence_index_sha256": host.file_sha256(finalized_root / "evidence-index.json"),
        "semantic_projection_file_sha256": host.file_sha256(
            finalized_root / "semantic-projection.json"
        ),
        "semantic_projection_sha256": host.canonical_sha256(semantic),
        "finalizer_closure": closure,
        "finalizer_dependency_manifest_sha256": host.canonical_sha256(closure),
        "interpreter": closure["interpreter"],
        "interpreter_sha256": closure["interpreter_sha256"],
        "network": "socket-construction-denied",
        "additional_model_calls": 0,
        "additional_browser_actions": 0,
        "raw_source_mutated": False,
        "output_schema_valid": True,
    }
    completion_path = finalized_root / "finalization-complete.json"
    host.write_exclusive(completion_path, completion)
    selection = {
        "finalizer_execution_mode": closure["finalizer_execution_mode"],
        "finalizer_runtime_qualification_sha256": closure["finalizer_runtime_qualification_sha256"],
        "finalizer_source_sha256": closure["finalizer_source_sha256"],
        "finalizer_projection_source_sha256": closure["finalizer_projection_source_sha256"],
        "finalizer_commit": closure["finalizer_commit"],
        "finalizer_dependency_manifest_sha256": host.canonical_sha256(closure),
        "evaluator_contract_sha256": closure["evaluator_contract_sha256"],
        "interpreter": closure["interpreter"],
        "interpreter_sha256": closure["interpreter_sha256"],
        "semantic_projection_sha256": host.canonical_sha256(semantic),
        "finalized_output_root": finalized_root.relative_to(artifact_root).as_posix(),
        "finalization_complete_sha256": host.file_sha256(completion_path),
    }
    monkeypatch.setattr(
        host,
        "validate_raw_attempt_seal",
        lambda **_kwargs: (raw_manifest, raw_receipt),
    )
    monkeypatch.setattr(
        host,
        "validate_finalized_attempt",
        lambda **_kwargs: (outcome, evidence, semantic, output_files),
    )
    reconstructed = host.validate_selected_finalization(
        repository=ROOT,
        artifact_root=artifact_root,
        contract=SimpleNamespace(attempt=lambda _run_id: attempt),
        run_id=run_id,
        package_commit=package_commit,
        selection=selection,
    )
    assert reconstructed == (outcome, evidence)

    state = tmp_path / "checkpoint" / "pilot-state.json"
    initialize_pilot_state(
        state,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    for index, task_a_run_id in enumerate(ATTEMPT_ORDER[:2], start=1):
        mark_empirical_entry(
            state,
            execution_contract_sha256="f" * 64,
            run_id=task_a_run_id,
        )
        mark_raw_attempt_complete(
            state,
            execution_contract_sha256="f" * 64,
            run_id=task_a_run_id,
            raw_manifest_sha256=f"{index}" * 64,
            raw_receipt_sha256=f"{index + 2}" * 64,
        )
        mark_attempt_completed(
            state,
            execution_contract_sha256="f" * 64,
            run_id=task_a_run_id,
            finalizer_execution_mode="qualified-local",
            finalizer_runtime_qualification_sha256="0" * 64,
            finalizer_source_sha256="1" * 64,
            finalizer_projection_source_sha256="2" * 64,
            finalizer_commit="b" * 40,
            finalizer_dependency_manifest_sha256="3" * 64,
            evaluator_contract_sha256="4" * 64,
            interpreter="/qualified/python3.11",
            interpreter_sha256="5" * 64,
            semantic_projection_sha256=f"{index + 5}" * 64,
            finalized_output_root=f"finalized/{task_a_run_id}/local",
            finalization_complete_sha256=f"{index + 7}" * 64,
        )
    record_first_pair_checkpoint(
        state,
        execution_contract_sha256="f" * 64,
        decision={"decision": "continue-to-task-b"},
        decided_at_epoch=2.0,
    )
    mark_empirical_entry(
        state,
        execution_contract_sha256="f" * 64,
        run_id=ATTEMPT_ORDER[2],
    )


def test_retry3_provider_has_two_distinct_single_use_slots_and_cumulative_caps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    password_record = type("P", (), {"pw_dir": str(tmp_path)})()
    monkeypatch.setattr(provider.pwd, "getpwuid", lambda _uid: password_record)
    first = provider.launch_capability_path(1)
    second = provider.launch_capability_path(2)
    assert first != second
    assert first.name.endswith("launch-slot-01-consumed.json")
    assert second.name.endswith("launch-slot-02-consumed.json")
    assert provider.PRIOR_T09_COST_USD == 2.5308164556905757
    assert provider.NEW_CAMPAIGN_LAMBDA_CAP_USD == 5.16
    assert provider.NEW_CAMPAIGN_AGGREGATE_CAP_USD == 45.16
    assert provider.CUMULATIVE_T09_CAP_USD == 48.0
    with pytest.raises(provider.T09ProviderError, match="outside"):
        provider.launch_capability_path(3)


def test_retry3_receipt_writer_is_private_exclusive(tmp_path: Path) -> None:
    regression = _load(REGRESSION_SOURCE, "giclab_t09_retry3_receipt_writer")
    destination = tmp_path / "receipt.json"
    regression._write_exclusive(destination, {"safe": True})  # type: ignore[attr-defined]
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        regression._write_exclusive(destination, {"safe": True})  # type: ignore[attr-defined]
    assert canonical_sha256({"safe": True}) == (
        "13f513fe32a8991557ebf28941b75597641e94717c08569b7723d998c7428423"
    )


def test_retry3_raw_seal_is_immediate_and_resumes_after_state_write_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_raw_seal")
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / "attempt"
    raw_root = attempt_root / "raw"
    shutil.copytree(RAW_FIXTURE, raw_root)
    retained_session = next((raw_root / "sira-output").glob("*.json"))
    (retained_session.parent / "duplicate.json").write_bytes(retained_session.read_bytes())
    run_id = ATTEMPT_ORDER[0]
    cleanup_path = raw_root / "host-cleanup-receipt.json"
    cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
    cleanup["run_id"] = run_id
    cleanup_path.write_text(json.dumps(cleanup), encoding="utf-8")
    for name, value in {
        "attempt-wall.json": {"run_id": run_id},
        "container-command.json": {"run_id": run_id},
        "container-state.json": {"running": False},
        "gpu-accounting.json": {"run_id": run_id},
    }.items():
        (raw_root / name).write_text(json.dumps(value), encoding="utf-8")
    (raw_root / "condition.stdout").write_text("", encoding="utf-8")
    (raw_root / "condition.stderr").write_text("", encoding="utf-8")
    frozen_sha256 = "a" * 64
    (raw_root / "evaluator-overlay-binding.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "frozen_run_manifest_sha256": frozen_sha256,
                "condition_mount_policy": "read-only",
            }
        ),
        encoding="utf-8",
    )
    (raw_root / "runtime-reconstruction-binding.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "runtime_cleanup_present": False,
                "runtime_cleanup_sha256": None,
                "host_cleanup_receipt_sha256": host.file_sha256(cleanup_path),
                "container_state_sha256": host.file_sha256(raw_root / "container-state.json"),
                "host_teardown_is_source_grounded_fallback": True,
            }
        ),
        encoding="utf-8",
    )
    state = artifact_root / "pilot-v5/pilot-state.json"
    initialize_pilot_state(
        state,
        execution_contract_sha256="b" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    mark_empirical_entry(state, execution_contract_sha256="b" * 64, run_id=run_id)
    manifest = {
        "run_id": run_id,
        "condition_plan_sha256": "c" * 64,
        "argv_sha256": "d" * 64,
    }
    original_mark = host.mark_raw_attempt_complete
    calls = 0

    def crash_once(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("fixture state-write crash")
        original_mark(*args, **kwargs)

    monkeypatch.setattr(host, "mark_raw_attempt_complete", crash_once)
    with pytest.raises(RuntimeError, match="state-write crash"):
        host.seal_raw_attempt(
            artifact_root=artifact_root,
            attempt_root=attempt_root,
            raw_root=raw_root,
            manifest=manifest,
            package_commit="e" * 40,
            frozen_run_manifest_sha256=frozen_sha256,
            execution_contract_sha256="b" * 64,
        )
    raw_manifest = attempt_root / "raw-attempt-manifest.json"
    raw_receipt = attempt_root / "raw-attempt-complete.json"
    retained_hashes = (host.file_sha256(raw_manifest), host.file_sha256(raw_receipt))
    retained_manifest = json.loads(raw_manifest.read_text(encoding="utf-8"))
    assert retained_manifest["retained_session_count"] == 2
    assert retained_manifest["reconstructable_disposition"] == (
        "deterministic-invalid-infrastructure-duplicate-session"
    )
    host.seal_raw_attempt(
        artifact_root=artifact_root,
        attempt_root=attempt_root,
        raw_root=raw_root,
        manifest=manifest,
        package_commit="e" * 40,
        frozen_run_manifest_sha256=frozen_sha256,
        execution_contract_sha256="b" * 64,
    )
    assert retained_hashes == (
        host.file_sha256(raw_manifest),
        host.file_sha256(raw_receipt),
    )
    retained_state = json.loads(state.read_text(encoding="utf-8"))
    assert retained_state["raw_attempts_complete"] == [run_id]
    execute_source = HOST_SOURCE.read_text(encoding="utf-8").split("def execute_condition", 1)[1]
    execute_source = execute_source.split("def validate_finalizer_source", 1)[0]
    assert "seal_raw_attempt(" in execute_source
    assert "verify_packages=True" not in execute_source
