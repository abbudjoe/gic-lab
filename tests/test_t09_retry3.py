from __future__ import annotations

import importlib.util
import json
import shutil
import stat
from pathlib import Path

import pytest

from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness.t09_sira_pilot import (
    ATTEMPT_ORDER,
    T09PilotError,
    canonical_sha256,
    initialize_pilot_state,
    mark_attempt_completed,
    mark_empirical_entry,
    mark_raw_attempt_complete,
    record_first_pair_checkpoint,
)

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
FINALIZER_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
REGRESSION_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py"
RAW_FIXTURE = ROOT / "tests/fixtures/t09/finalizer-raw-shape"


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
    receipt: str = "4" * 64,
) -> None:
    mark_attempt_completed(
        state,
        execution_contract_sha256="f" * 64,
        run_id=run_id,
        finalizer_source_sha256=source,
        finalizer_commit=commit,
        finalizer_dependency_manifest_sha256=dependencies,
        evaluator_contract_sha256=evaluator,
        interpreter="/opt/sira/.venv/bin/python",
        interpreter_sha256="e" * 64,
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
    retained = json.loads(state.read_text(encoding="utf-8"))
    assert retained["raw_attempts_complete"] == list(ATTEMPT_ORDER[:2])
    assert retained["attempts_completed"] == list(ATTEMPT_ORDER[:2])
    assert len(retained["attempt_finalization_history"][ATTEMPT_ORDER[0]]) == 2


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
    assert 'frozen_manifest.get("python_interpreter_sha256") != interpreter_sha256' in source
    completion_write = host_source.index("write_exclusive(completion_path, completion)")
    state_selection = host_source.index("mark_attempt_completed(", completion_write)
    assert completion_write < state_selection


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
