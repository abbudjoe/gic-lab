from __future__ import annotations

import importlib.util
import json
import shutil
import stat
import subprocess
import venv
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness import t09_sira_pilot as pilot_state
from giclab.harness.t09_provider_contracts import (
    V7_PROVIDER_CONTRACT,
    V11_PROVIDER_CONTRACT,
    V16_PROVIDER_CONTRACT,
    load_provider_plan,
)
from giclab.harness.t09_sira_pilot import (
    T09BudgetExceeded,
    T09PilotError,
    canonical_sha256,
    initialize_pilot_state,
    mark_attempt_completed,
    mark_empirical_entry,
    mark_raw_attempt_complete,
    record_first_pair_checkpoint,
    transition_zero_usage_preflight_state,
    usage_to_document,
)
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[1]
ATTEMPT_ORDER = V7_PROVIDER_CONTRACT.run_ids
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
FINALIZER_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
REGRESSION_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py"
PROJECTION_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_finalizer_projection.py"
LOCAL_QUALIFICATION_SOURCE = (
    ROOT / "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py"
)
RUNTIME_ADAPTATION_SOURCE = ROOT / "src/giclab/harness/sira_gate_a_runtime.py"
REAL_REGRESSION_RECEIPT = (
    ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/"
    "T09_PRAGMATIC_RETRY4_FINALIZER_REGRESSION.json"
)
RAW_FIXTURE = ROOT / "tests/fixtures/t09/finalizer-raw-shape"


def _mark_empirical_entry(
    path: Path,
    *,
    execution_contract_sha256: str,
    run_id: str,
) -> None:
    """Advance legacy state fixtures through the current supervised-release contract."""

    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("condition_start_reservation") is None:
        pilot_state.reserve_condition_start(
            path,
            execution_contract_sha256=execution_contract_sha256,
            run_id=run_id,
            start_intent_sha256=canonical_sha256({"fixture": "condition-start", "run_id": run_id}),
        )
    mark_empirical_entry(
        path,
        execution_contract_sha256=execution_contract_sha256,
        run_id=run_id,
        supervised_release_receipt_sha256=canonical_sha256(
            {"fixture": "supervised-release", "run_id": run_id}
        ),
    )


def test_retry3_preflight_resume_transitions_only_exact_zero_use_state() -> None:
    old_execution = "1" * 64
    new_execution = "2" * 64
    state: dict[str, object] = {
        "schema_version": "0.2.0",
        "plan_id": V7_PROVIDER_CONTRACT.plan_id,
        "execution_contract_sha256": old_execution,
        "pilot_started_at_epoch": 100.0,
        "lambda_started_at_epoch": 100.0,
        "first_pair_started_at_epoch": None,
        "second_pair_started_at_epoch": None,
        "empirical_attempts_entered": [],
        "raw_attempts_complete": [],
        "raw_attempt_bindings": {},
        "attempts_completed": [],
        "attempt_finalizations": {},
        "attempt_finalization_history": {},
        "first_pair_decision": None,
        "first_pair_checkpoint_binding": None,
        "first_pair_selection_drift_detected": False,
    }
    aggregate: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": V7_PROVIDER_CONTRACT.plan_id,
        "execution_contract_sha256": old_execution,
        "unreconciled_provider_attempts": 0,
        "usage": usage_to_document(pilot_state.ProviderBudgetUsage()),
    }
    transitioned_state, transitioned_aggregate = transition_zero_usage_preflight_state(
        state,
        aggregate,
        prior_execution_contract_sha256=old_execution,
        next_execution_contract_sha256=new_execution,
    )
    assert transitioned_state["execution_contract_sha256"] == new_execution
    assert transitioned_state["pilot_started_at_epoch"] == 100.0
    assert transitioned_state["lambda_started_at_epoch"] == 100.0
    assert transitioned_state["first_pair_started_at_epoch"] is None
    assert transitioned_aggregate["execution_contract_sha256"] == new_execution
    assert state["execution_contract_sha256"] == old_execution
    consumed = {**state, "empirical_attempts_entered": [ATTEMPT_ORDER[0]]}
    with pytest.raises(T09PilotError, match="zero-use"):
        transition_zero_usage_preflight_state(
            consumed,
            aggregate,
            prior_execution_contract_sha256=old_execution,
            next_execution_contract_sha256=new_execution,
        )
    unreconciled = {**aggregate, "unreconciled_provider_attempts": 1}
    with pytest.raises(T09PilotError, match="zero usage"):
        transition_zero_usage_preflight_state(
            state,
            unreconciled,
            prior_execution_contract_sha256=old_execution,
            next_execution_contract_sha256=new_execution,
        )


def test_retry3_same_host_resume_is_disabled_and_slot2_is_source_bound() -> None:
    source = HOST_SOURCE.read_text(encoding="utf-8")
    parser_source = source.split("def parser()", 1)[1]
    assert 'operations.add_parser("resume-preflight")' not in parser_source
    prepare = source.split("def prepare_preflight_resume", 1)[1].split("def resume_preflight", 1)[0]
    assert "historical transition-specific resume path is retired" in prepare
    preflight = source.split("def preflight(", 1)[1].split("def container_create_argv", 1)[0]
    assert "retain_slot2_authority(" in preflight
    assert "materialize_retained_or_build_image(" in preflight
    assert "qualified_real_evidence_regression(" in preflight
    assert preflight.index("qualified_real_evidence_regression(") < preflight.index(
        "browser_lifecycle_preflight("
    )
    assert preflight.index("preflight_seconds_remaining(") < preflight.index(
        "model_metadata_preflight("
    )
    assert preflight.index("provider_seconds_remaining(") < preflight.index(
        "model_metadata_preflight("
    )
    assert preflight.index("model_metadata_preflight(") < preflight.index(
        "write_frozen_run_manifest("
    )
    assert preflight.index("load_frozen_run_manifest(") < preflight.index(
        "admit_scheduled_first_attempt_before_empirical_origin("
    )
    assert preflight.index(
        "admit_scheduled_first_attempt_before_empirical_origin("
    ) < preflight.index("postfreeze-validation.json")
    assert preflight.index("postfreeze-validation.json") < preflight.index(
        'preflight_path = _pilot_root(artifact_root) / "preflight.json"'
    )
    checkpoint = source.split("def first_pair_checkpoint", 1)[1].split(
        "def campaign_evidence_disposition", 1
    )[0]
    assert checkpoint.index("load_frozen_run_manifest(") < checkpoint.index(
        "validate_live_frozen_state_binding(state, frozen_manifest)"
    )
    disposition = source.split("def campaign_evidence_disposition", 1)[1].split(
        "def _received_export_ack_path", 1
    )[0]
    assert "require_image=False" in disposition
    assert "validate_live_frozen_state_binding(state, frozen_manifest)" in disposition
    runtime_source = RUNTIME_ADAPTATION_SOURCE.read_text(encoding="utf-8")
    assert "pilot_root = pilot_control_root.parent" in runtime_source
    assert "pilot_root=attempt_root.parents[2]" not in runtime_source


def test_retry3_slot2_uses_separate_campaign_and_active_lambda_clocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_slot2_clocks")
    now = 20_000.0
    state = tmp_path / "pilot-v7/pilot-state.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps(
            {
                "plan_id": V7_PROVIDER_CONTRACT.plan_id,
                "campaign_started_at_epoch": now - 5_000,
                "owned_lambda_started_at_epoch": now - 100,
                "prior_campaign_lambda_duration_seconds": 3_883.0,
                "prior_campaign_lambda_cost_usd": 3_883.0 * 1.29 / 3_600,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(host.time, "time", lambda: now)
    expected_active = 3_983.0
    expected_cost_remaining_seconds = (8.0 - expected_active * 1.29 / 3_600) * 3_600 / 1.29
    assert expected_cost_remaining_seconds > 9_400
    assert host.provider_seconds_remaining(tmp_path) == pytest.approx(9_400)


def test_retry3_slot2_transition_and_launch_headroom_are_fail_closed() -> None:
    disposition = json.loads(
        (
            ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/"
            "T09_PRAGMATIC_RETRY3_DISPOSITION.json"
        ).read_text(encoding="utf-8")
    )
    package_commit = disposition["frozen_package_commit"]
    assert package_commit == "4a4ecc1e8aa0a00d43301161a90425ae439a2cfd"
    transition = provider._slot2_git_transition(ROOT, package_commit)
    assert transition["from_package_commit"] == provider.SLOT1_PACKAGE_COMMIT
    assert transition["to_package_commit"] == package_commit
    assert transition["scientific_contract_changed"] is False
    assert transition["scientific_projection_sha256"]
    runtime_transition = transition["control_runtime_transition"]
    assert (
        runtime_transition["previous"]["runtime_identity_sha256"]
        != (runtime_transition["current"]["runtime_identity_sha256"])
    )
    assert (
        runtime_transition["current"]["reviewed_implementation_ancestor"]
        == (runtime_transition["current"]["command_giclab_commit"])
    )
    assert transition["control_runtime_transition_sha256"]
    lifecycle = provider.load_campaign_lifecycle(ROOT, contract=V7_PROVIDER_CONTRACT)
    eligibility = {
        "prior_lambda_duration_seconds": 3_600.0,
        "prior_lambda_cost_usd": 1.29,
    }
    exact = provider.validate_slot2_launch_headroom(
        eligibility,
        lifecycle=lifecycle,
        now=1_000.0,
    )
    assert exact["projected_cumulative_active_seconds"] == 21_600
    assert exact["projected_cumulative_lambda_cost_usd"] == pytest.approx(7.74)
    with pytest.raises(provider.T09ProviderError, match="headroom"):
        provider.validate_slot2_launch_headroom(
            {**eligibility, "prior_lambda_duration_seconds": 3_600.001},
            lifecycle=lifecycle,
            now=1_000.0,
        )


def test_retry3_exact_clean_package_is_host_verifiable() -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_package_verification")
    current_commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    stopped = load_json(
        ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/"
        "T09_V16_PREFLIGHT_STOPPED_DISPOSITION.json"
    )
    package_commit = stopped["package"]["merged_package"]
    command_document = host.verify_package(
        ROOT,
        package_commit,
        current_commit=current_commit,
        contract=V16_PROVIDER_CONTRACT,
    )
    assert (
        command_document["reviewed_implementation_ancestor"]
        == (
            json.loads(
                host.contract_paths(ROOT, V16_PROVIDER_CONTRACT)["runtime"].read_text(
                    encoding="utf-8"
                )
            )["repository_instrumentation"]["reviewed_implementation_ancestor"]
        )
    )
    assert len(command_document["manifests"]) == 4
    assert all(item["valid"] is True for item in command_document["pair_diffs"])


def test_retry3_plan_has_a_typed_two_slot_raw_first_contract() -> None:
    plan_path = ROOT / (
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/"
        "PLAN-EXP0001-PILOT-V7.yaml"
    )
    plan = yaml.safe_load(plan_path.read_bytes())
    assert plan["plan_id"] == V7_PROVIDER_CONTRACT.plan_id
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
        provider_contract=V7_PROVIDER_CONTRACT,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    _mark_empirical_entry(state, execution_contract_sha256="f" * 64, run_id=ATTEMPT_ORDER[0])
    mark_raw_attempt_complete(
        state,
        execution_contract_sha256="f" * 64,
        run_id=ATTEMPT_ORDER[0],
        raw_manifest_sha256="5" * 64,
        raw_receipt_sha256="6" * 64,
    )
    # Downstream finalization may lag without reopening the consumed condition.
    _mark_empirical_entry(state, execution_contract_sha256="f" * 64, run_id=ATTEMPT_ORDER[1])
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
            decision={
                "decision": "continue-to-task-b",
                "first_pair_started_at_epoch": 1.0,
                "second_pair_started_at_epoch": 2.0,
                "decided_at_epoch": 2.0,
            },
            decided_at_epoch=2.0,
        )
    # A repaired downstream version may be selected for an already finalized attempt.
    _select(state, ATTEMPT_ORDER[0])
    record_first_pair_checkpoint(
        state,
        execution_contract_sha256="f" * 64,
        decision={
            "decision": "continue-to-task-b",
            "first_pair_started_at_epoch": 1.0,
            "second_pair_started_at_epoch": 2.0,
            "decided_at_epoch": 2.0,
        },
        decided_at_epoch=2.0,
    )
    checkpoint_state_bytes = state.read_bytes()
    for field in ("first_pair_started_at_epoch", "second_pair_started_at_epoch"):
        tampered = json.loads(checkpoint_state_bytes)
        tampered[field] = float(tampered[field]) + 0.5
        state.write_text(json.dumps(tampered), encoding="utf-8")
        with pytest.raises(T09PilotError, match="pair-wall origins"):
            pilot_state._load_pilot_state(state, contract_sha256="f" * 64)
        state.write_bytes(checkpoint_state_bytes)
    with pytest.raises(T09PilotError, match="semantic projection"):
        _select(state, ATTEMPT_ORDER[0], source="7" * 64, semantic="8" * 64)
    blocked = json.loads(state.read_text(encoding="utf-8"))
    assert blocked["first_pair_selection_drift_detected"] is True
    assert blocked["first_pair_decision"] == "stop-before-task-b"
    with pytest.raises(T09BudgetExceeded, match="checkpoint"):
        _mark_empirical_entry(
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


def test_retry3_task_b_requires_uniform_current_task_a_reselection(tmp_path: Path) -> None:
    state = tmp_path / "pilot-state.json"
    initialize_pilot_state(
        state,
        provider_contract=V7_PROVIDER_CONTRACT,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    for index, run_id in enumerate(ATTEMPT_ORDER[:2], start=1):
        _mark_empirical_entry(state, execution_contract_sha256="f" * 64, run_id=run_id)
        mark_raw_attempt_complete(
            state,
            execution_contract_sha256="f" * 64,
            run_id=run_id,
            raw_manifest_sha256=f"{index}" * 64,
            raw_receipt_sha256=f"{index + 2}" * 64,
        )
        _select(state, run_id)
    record_first_pair_checkpoint(
        state,
        execution_contract_sha256="f" * 64,
        decision={
            "decision": "continue-to-task-b",
            "first_pair_started_at_epoch": 1.0,
            "second_pair_started_at_epoch": 2.0,
            "decided_at_epoch": 2.0,
        },
        decided_at_epoch=2.0,
    )

    _select(state, ATTEMPT_ORDER[0], source="9" * 64)
    with pytest.raises(T09BudgetExceeded, match="selections drifted"):
        _mark_empirical_entry(
            state,
            execution_contract_sha256="f" * 64,
            run_id=ATTEMPT_ORDER[2],
        )
    _select(state, ATTEMPT_ORDER[1], source="9" * 64)
    _mark_empirical_entry(
        state,
        execution_contract_sha256="f" * 64,
        run_id=ATTEMPT_ORDER[2],
    )


def test_retry3_selection_receipt_crash_is_reconciled_without_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "pilot-state.json"
    initialize_pilot_state(
        state,
        provider_contract=V7_PROVIDER_CONTRACT,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    _mark_empirical_entry(state, execution_contract_sha256="f" * 64, run_id=ATTEMPT_ORDER[0])
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
    assert "observed_interpreter_identity = _interpreter_launcher_identity" in source
    assert "for field, value in observed_interpreter_identity.items()" in source
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
    assert receipt["finalizer_source_sha256"] == (
        "32937302bddec910eb696c1c513b28e67b5a86b4e300171396504a926232bb5d"
    )
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
        contract=V11_PROVIDER_CONTRACT,
        expected_finalizer_source_sha256=expected_source,
    )
    assert accepted["finalizer_source_sha256"] == expected_source
    with pytest.raises(host.T09HostError, match="real-evidence finalizer regression"):
        host.validate_real_evidence_regression(  # type: ignore[attr-defined]
            ROOT,
            contract=V11_PROVIDER_CONTRACT,
        )


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
        selector_source_sha256="9" * 64,
        finalizer_dependency_manifest_sha256="5" * 64,
        refinalization_receipt_schema_sha256="a" * 64,
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


def test_retry3_provider_preflight_accepts_source_bound_offhost_runtime_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_offhost_qualification")
    execution = tmp_path / "execution.json"
    evaluator = tmp_path / "evaluator.json"
    regression = tmp_path / "regression.json"
    commands = tmp_path / "commands.json"
    execution.write_text(
        json.dumps({"runtime": {"local_finalizer_base_packages": ["base==1"]}}),
        encoding="utf-8",
    )
    evaluator.write_text("{}\n", encoding="utf-8")
    regression.write_text("{}\n", encoding="utf-8")
    commands.write_text("{}\n", encoding="utf-8")
    entry = {
        "path": "package.py",
        "mode": "0644",
        "type": "file",
        "bytes": 1,
        "sha256": "a" * 64,
    }
    tree = {
        "root_mode": "0755",
        "entries": [entry],
        "entry_count": 1,
        "total_regular_bytes": 1,
        "entries_sha256": host.canonical_sha256([entry]),
    }
    qualification_source = ROOT / (
        "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py"
    )
    receipt = {
        "schema_version": "0.1.0",
        "qualification_id": V11_PROVIDER_CONTRACT.local_finalizer_qualification_id,
        "plan_id": V11_PROVIDER_CONTRACT.plan_id,
        "provider_contract_version": V11_PROVIDER_CONTRACT.version,
        "host_run_id": V11_PROVIDER_CONTRACT.host_run_id,
        "attempt_order": list(V11_PROVIDER_CONTRACT.attempt_order),
        "evaluator_run_ids": list(V11_PROVIDER_CONTRACT.evaluator_run_ids),
        "runtime_qualification_id": V11_PROVIDER_CONTRACT.active_image_qualification_id,
        "frozen_run_manifest_id": V11_PROVIDER_CONTRACT.frozen_run_manifest_id,
        "execution_contract_path": V11_PROVIDER_CONTRACT.execution_contract_path,
        "command_manifest_path": V11_PROVIDER_CONTRACT.command_manifest_path,
        "command_manifest_sha256": host.file_sha256(commands),
        "provider_profile_path": V11_PROVIDER_CONTRACT.provider_profile_path,
        "provider_profile_sha256": V11_PROVIDER_CONTRACT.expected_provider_profile_sha256,
        "package_commit": "a" * 40,
        "python_version": "3.11.14",
        "execution_contract_sha256": host.file_sha256(execution),
        "interpreter": "/control/offhost/python3.11",
        "interpreter_sha256": "b" * 64,
        "interpreter_launcher_type": "regular",
        "interpreter_launcher_mode": "0755",
        "interpreter_launcher_link_target": None,
        "interpreter_resolved_target": "/control/offhost/python3.11",
        "interpreter_resolved_target_sha256": "b" * 64,
        "interpreter_site_packages": "/control/offhost/base-site-packages",
        "interpreter_dependency_manifest": ["base==1"],
        "interpreter_dependency_manifest_sha256": host.canonical_sha256(["base==1"]),
        "interpreter_dependency_tree": tree,
        "interpreter_dependency_tree_sha256": host.canonical_sha256(tree),
        "dependency_site_packages": "/control/offhost/evaluator-site-packages",
        "dependency_package_manifest": ["eval==1"],
        "dependency_package_manifest_sha256": host.canonical_sha256(["eval==1"]),
        "dependency_tree": tree,
        "dependency_tree_sha256": host.canonical_sha256(tree),
        "evaluator_contract_sha256": host.file_sha256(evaluator),
        "evaluator_root": "/control/offhost/evaluator",
        "dataset": "/control/offhost/fanout-final-dev.json",
        "dataset_sha256": host.PINNED_DATASET_SHA256,
        "real_evidence_regression_sha256": host.file_sha256(regression),
        "real_evidence_regression_passed": True,
        "network_policy": "socket-construction-denied",
        "model_requests": 0,
        "browser_actions": 0,
        "source_sha256s": {
            "finalizer": "c" * 64,
            "projection": "d" * 64,
            "qualification": host.file_sha256(qualification_source),
        },
    }
    receipt_path = tmp_path / "offhost-qualification.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    receipt_path.chmod(0o600)
    monkeypatch.setattr(
        host,
        "contract_paths",
        lambda _repository, _contract: {
            "execution": execution,
            "commands": commands,
            "evaluator": evaluator,
            "real_regression": regression,
        },
    )
    monkeypatch.setattr(
        host,
        "expected_evaluator_packages",
        lambda _repository, _contract: ["eval==1"],
    )
    monkeypatch.setattr(
        host,
        "git_file_sha256",
        lambda _repository, _commit, relative, **_kwargs: {
            host.FINALIZER_RELATIVE_PATH: "c" * 64,
            host.FINALIZER_PROJECTION_RELATIVE_PATH: "d" * 64,
        }[relative],
    )
    accepted = host.validate_local_finalizer_qualification(
        receipt_path,
        repository=ROOT,
        package_commit="a" * 40,
        require_local_runtime=False,
        contract=V11_PROVIDER_CONTRACT,
    )
    assert accepted["interpreter"] == "/control/offhost/python3.11"
    with pytest.raises((FileNotFoundError, host.T09HostError)):
        host.validate_local_finalizer_qualification(
            receipt_path,
            repository=ROOT,
            package_commit="a" * 40,
            require_local_runtime=True,
            contract=V11_PROVIDER_CONTRACT,
        )
    preflight_source = (
        HOST_SOURCE.read_text(encoding="utf-8")
        .split("def preflight(", 1)[1]
        .split("def container_create_argv", 1)[0]
    )
    assert "require_local_runtime=False" in preflight_source
    assert "args.local_evaluator_root" not in preflight_source
    assert "args.local_dataset" not in preflight_source


def test_retry3_local_qualification_preserves_the_venv_launcher(
    tmp_path: Path,
) -> None:
    qualifier = _load(
        LOCAL_QUALIFICATION_SOURCE,
        "giclab_t09_retry3_launcher_qualifier",
    )
    host = _load(HOST_SOURCE, "giclab_t09_retry3_launcher_host")
    finalizer = _load(FINALIZER_SOURCE, "giclab_t09_retry3_launcher_finalizer")
    venv_root = tmp_path / "qualified-venv"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(venv_root)
    launcher = venv_root / "bin/python"
    assert launcher.is_symlink()
    identities = [
        qualifier._interpreter_launcher_identity(launcher),  # type: ignore[attr-defined]
        host.local_interpreter_launcher_identity(launcher),
        finalizer._interpreter_launcher_identity(launcher),  # type: ignore[attr-defined]
    ]
    assert identities[0] == identities[1] == identities[2]
    identity = identities[0]
    assert identity["interpreter"] == launcher.as_posix()
    assert identity["interpreter_launcher_type"] == "symlink"
    assert identity["interpreter_launcher_link_target"] == launcher.readlink().as_posix()
    assert identity["interpreter_resolved_target"] == launcher.resolve(strict=True).as_posix()
    assert identity["interpreter"] != identity["interpreter_resolved_target"]

    probe_source = (
        "import json,sys,sysconfig;"
        "print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,"
        "'purelib':sysconfig.get_paths()['purelib']},sort_keys=True))"
    )
    launcher_probe = json.loads(
        subprocess.run(
            [launcher.as_posix(), "-I", "-c", probe_source],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    )
    target_probe = json.loads(
        subprocess.run(
            [launcher.resolve(strict=True).as_posix(), "-I", "-c", probe_source],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    )
    assert launcher_probe["executable"] == launcher.as_posix()
    assert launcher_probe["prefix"] == venv_root.as_posix()
    assert Path(launcher_probe["purelib"]).is_relative_to(venv_root)
    assert target_probe["prefix"] != launcher_probe["prefix"]
    assert target_probe["purelib"] != launcher_probe["purelib"]


def test_retry3_local_dependency_tree_detects_same_metadata_byte_drift(
    tmp_path: Path,
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_dependency_bytes")
    qualifier = _load(
        LOCAL_QUALIFICATION_SOURCE,
        "giclab_t09_retry3_dependency_bytes_qualifier",
    )
    site_packages = tmp_path / "site-packages"
    metadata = site_packages / "fixture_pkg-1.0.dist-info" / "METADATA"
    module = site_packages / "fixture_pkg" / "__init__.py"
    metadata.parent.mkdir(parents=True)
    module.parent.mkdir(parents=True)
    metadata.write_text("Name: fixture-pkg\nVersion: 1.0\n", encoding="utf-8")
    module.write_text("VALUE = 1\n", encoding="utf-8")
    before = host.local_dependency_tree_inventory(
        site_packages,
        label="fixture evaluator dependency tree",
    )
    qualified_before = qualifier._dependency_tree_inventory(  # type: ignore[attr-defined]
        site_packages,
        label="fixture evaluator dependency tree",
    )
    retained_metadata = metadata.read_bytes()
    module.write_text("VALUE = 2\n", encoding="utf-8")
    after = host.local_dependency_tree_inventory(
        site_packages,
        label="fixture evaluator dependency tree",
    )
    qualified_after = qualifier._dependency_tree_inventory(  # type: ignore[attr-defined]
        site_packages,
        label="fixture evaluator dependency tree",
    )
    assert metadata.read_bytes() == retained_metadata
    assert qualified_before == before
    assert qualified_after == after
    assert before["entry_count"] == after["entry_count"]
    assert before["entries_sha256"] != after["entries_sha256"]
    assert host._valid_retained_dependency_tree(before) is True
    assert host._valid_retained_dependency_tree(after) is True


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
        task_id="7dcbbbdc7f1120cd",
        task_index=0,
        condition="reactive",
    )
    attempt_root = artifact_root / attempt.output_root
    raw_root = artifact_root / attempt.raw_output_root
    finalized_root = artifact_root / attempt.finalized_output_root / "local-invocation-0001"
    raw_root.mkdir(parents=True)
    finalized_root.mkdir(parents=True)
    frozen_run_manifest_path = artifact_root / "pilot-v7/frozen-run-manifest.json"
    host.write_exclusive(frozen_run_manifest_path, {"fixture": "frozen-run-manifest"})
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
        "selector_source_sha256": host.file_sha256(HOST_SOURCE),
        "scientific_package_commit": package_commit,
        "pilot_library_sha256": "3" * 64,
        "interpreter": "/qualified/python3.11",
        "interpreter_sha256": "4" * 64,
        "python_version": "3.11.14",
        "interpreter_dependency_manifest_sha256": "a" * 64,
        "replacement_image_id": "sha256:" + "5" * 64,
        "execution_contract_sha256": "6" * 64,
        "command_manifests_sha256": "7" * 64,
        "dataset_contract_sha256": "8" * 64,
        "evaluator_contract_sha256": "9" * 64,
        "evaluator_commit": host.SIRA_COMMIT,
        "score_schema_sha256": "c" * 64,
        "evidence_schema_sha256": "d" * 64,
        "refinalization_receipt_schema_sha256": host.file_sha256(
            ROOT / "schemas/t09-offline-refinalization-receipt.schema.json"
        ),
        "evaluator_overlay_entries_sha256": "e" * 64,
        "evaluator_overlay_packages_sha256": "f" * 64,
    }
    projection = _load(PROJECTION_SOURCE, "giclab_t09_retry3_completion_projection")
    completion = projection.build_completion_projection(  # type: ignore[attr-defined]
        plan_id=V7_PROVIDER_CONTRACT.plan_id,
        host_run_id=V7_PROVIDER_CONTRACT.host_run_id,
        run_id=run_id,
        raw_manifest_sha256_before=host.file_sha256(attempt_root / "raw-attempt-manifest.json"),
        raw_manifest_sha256_after=host.file_sha256(attempt_root / "raw-attempt-manifest.json"),
        raw_receipt_sha256=host.file_sha256(attempt_root / "raw-attempt-complete.json"),
        raw_manifest_payload_sha256=host.canonical_sha256(raw_manifest),
        raw_receipt_payload_sha256=host.canonical_sha256(raw_receipt),
        output_files=output_files,
        output_files_sha256=host.canonical_sha256(output_files),
        outcome_sha256=host.file_sha256(finalized_root / "attempt-outcome.json"),
        evidence_index_sha256=host.file_sha256(finalized_root / "evidence-index.json"),
        semantic_projection_file_sha256=host.file_sha256(
            finalized_root / "semantic-projection.json"
        ),
        semantic_projection_sha256=host.canonical_sha256(semantic),
        finalizer_closure=closure,
        finalizer_dependency_manifest_sha256=host.canonical_sha256(closure),
        network="socket-construction-denied",
        raw_attempt_manifest_public_alias="attempt/raw-attempt-manifest.json",
        frozen_run_manifest_sha256=host.file_sha256(frozen_run_manifest_path),
        task_id=attempt.task_id,
        task_sha256=pilot_state.TASK_TEXT_SHA256S[attempt.task_index],
        condition=attempt.condition,
        receipt_schema_sha256=closure["refinalization_receipt_schema_sha256"],
    )
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
        contract=SimpleNamespace(
            plan_id=V7_PROVIDER_CONTRACT.plan_id,
            sha256="f" * 64,
            attempt=lambda _run_id: attempt,
        ),
        run_id=run_id,
        package_commit=package_commit,
        selection=selection,
    )
    assert reconstructed == (outcome, evidence)

    state = tmp_path / "checkpoint" / "pilot-state.json"
    initialize_pilot_state(
        state,
        provider_contract=V7_PROVIDER_CONTRACT,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    for index, task_a_run_id in enumerate(ATTEMPT_ORDER[:2], start=1):
        _mark_empirical_entry(
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
        decision={
            "decision": "continue-to-task-b",
            "first_pair_started_at_epoch": 1.0,
            "second_pair_started_at_epoch": 2.0,
            "decided_at_epoch": 2.0,
        },
        decided_at_epoch=2.0,
    )
    _mark_empirical_entry(
        state,
        execution_contract_sha256="f" * 64,
        run_id=ATTEMPT_ORDER[2],
    )


def test_retry3_provider_has_two_distinct_single_use_slots_and_cumulative_caps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    password_record = type("P", (), {"pw_dir": str(tmp_path)})()
    monkeypatch.setattr(provider.pwd, "getpwuid", lambda _uid: password_record)
    first = provider.launch_capability_path(1, contract=V7_PROVIDER_CONTRACT)
    second = provider.launch_capability_path(2, contract=V7_PROVIDER_CONTRACT)
    assert first != second
    assert first.name.endswith("launch-slot-01-consumed.json")
    assert second.name.endswith("launch-slot-02-consumed.json")
    budget = load_provider_plan(ROOT, V7_PROVIDER_CONTRACT)["budget"]
    assert isinstance(budget, dict)
    assert budget["prior_t09_cost_usd"] == 5.7424506112
    assert budget["max_provider_compute_cost_usd"] == 8.0
    assert budget["max_total_cost_usd"] == 48.0
    assert budget["cumulative_t09_cost_cap_usd"] == 60.0
    with pytest.raises(provider.T09ProviderError, match="outside"):
        provider.launch_capability_path(3, contract=V7_PROVIDER_CONTRACT)


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


def test_retry3_slot2_authority_retention_is_manifest_complete_and_minimal(
    tmp_path: Path,
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_authority_retention")
    source = tmp_path / "provider-private"
    authority = source / "slot2-eligibility-source"
    authority.mkdir(parents=True)
    host.write_exclusive(source / "replacement-launch-eligibility.json", {"eligible": True})
    host.write_exclusive(authority / "transition.json", {"transition": True})
    nested = authority / "slot1-entry-source"
    nested.mkdir()
    host.write_exclusive(nested / "entry-receipt.json", {"entry": True})
    host.write_exclusive(nested / "source-manifest.json", {"entry_source": True})
    closeout = authority / "slot1-closeout-source"
    closeout.mkdir()
    host.write_exclusive(closeout / "closeout-receipt.json", {"closeout": True})
    host.write_exclusive(closeout / "source-manifest.json", {"closeout_source": True})
    source_manifest = provider._slot2_authority_tree_manifest(
        authority, contract=V7_PROVIDER_CONTRACT
    )
    host.write_exclusive(authority / "source-manifest.json", source_manifest)
    host.write_exclusive(source / "unrelated-owned-state.json", {"private": True})

    destination = tmp_path / "retained"
    retained = host.retain_slot2_authority(source, destination)
    assert set(retained) == {
        "replacement-launch-eligibility.json",
        "slot2-eligibility-source/source-manifest.json",
        "slot2-eligibility-source/transition.json",
        "slot2-eligibility-source/slot1-entry-source/entry-receipt.json",
        "slot2-eligibility-source/slot1-entry-source/source-manifest.json",
        "slot2-eligibility-source/slot1-closeout-source/closeout-receipt.json",
        "slot2-eligibility-source/slot1-closeout-source/source-manifest.json",
    }
    assert not (destination / "unrelated-owned-state.json").exists()

    host.write_exclusive(authority / "undeclared-extra.json", {"extra": True})
    with pytest.raises(host.T09HostError, match="member set"):
        host.retain_slot2_authority(source, tmp_path / "rejected")


def test_retry3_preentry_secret_match_is_a_monotonic_campaign_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_preentry_secret_stop")
    artifact_root = tmp_path / "artifacts"
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    initialize_pilot_state(
        state_path,
        provider_contract=V7_PROVIDER_CONTRACT,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    attempt_root = artifact_root / "attempt"
    attempt_root.mkdir(parents=True, mode=0o700)
    credential_file = tmp_path / "secret"
    credential_fixture = b"fixture-secret-that-must-never-be-retained"
    credential_file.write_bytes(credential_fixture)
    credential_file.chmod(0o600)
    leaked = attempt_root / "condition.stderr"
    leaked.write_bytes(credential_fixture)
    monkeypatch.setattr(host, "remove_container", lambda _prefix, _name: True)
    monkeypatch.setattr(host, "owned_containers", lambda _prefix: [])

    with pytest.raises(host.T09HostError, match="security stop or residue"):
        host.record_preentry_condition_failure(
            pilot_state_path=state_path,
            attempt_root=attempt_root,
            secret_file=credential_file,
            prefix=["docker"],
            container_name="fixture-container",
            run_id=ATTEMPT_ORDER[0],
            contract=V7_PROVIDER_CONTRACT,
            reason="fixture-create-failure",
            returncode=125,
            package_commit="a" * 40,
            execution_contract_sha256="f" * 64,
            frozen_run_manifest_sha256="b" * 64,
            condition_plan_sha256="c" * 64,
            condition_argv_sha256="d" * 64,
        )
    assert not leaked.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["actual_credential_exposure_detected"] is True
    assert state["credential_safety_stop_detected"] is True
    receipt = json.loads(
        (attempt_root / "preentry-condition-failure.json").read_text(encoding="utf-8")
    )
    assert receipt["actual_credential_exposure_detected"] is True
    assert receipt["retry_same_frozen_condition_permitted"] is False
    with pytest.raises(T09BudgetExceeded, match="credential safety"):
        _mark_empirical_entry(
            state_path,
            execution_contract_sha256="f" * 64,
            run_id=ATTEMPT_ORDER[0],
        )


def test_retry3_private_regression_archive_requires_private_single_link_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_private_archive")
    archive = tmp_path / "private-v4.tar.gz"
    archive.write_bytes(b"private-regression-fixture")
    archive.chmod(0o600)
    monkeypatch.setattr(host, "PRIVATE_REGRESSION_ARCHIVE_PATH", archive)
    monkeypatch.setattr(host, "PRIVATE_REGRESSION_ARCHIVE_BYTES", archive.stat().st_size)
    monkeypatch.setattr(host, "PRIVATE_REGRESSION_ARCHIVE_SHA256", host.file_sha256(archive))
    assert host.validate_private_regression_archive(archive) == archive

    archive.chmod(0o644)
    with pytest.raises(host.T09HostError, match="identity drifted"):
        host.validate_private_regression_archive(archive)
    archive.chmod(0o600)
    hardlink = tmp_path / "private-v4-hardlink.tar.gz"
    hardlink.hardlink_to(archive)
    with pytest.raises(host.T09HostError, match="identity drifted"):
        host.validate_private_regression_archive(archive)


def test_retry3_metadata_secret_scan_removes_value_and_permanently_stops_admission(
    tmp_path: Path,
) -> None:
    host = _load(HOST_SOURCE, "giclab_t09_retry3_metadata_secret_scan")
    artifact_root = tmp_path / "artifacts"
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    initialize_pilot_state(
        state_path,
        provider_contract=V7_PROVIDER_CONTRACT,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    credential_file = tmp_path / "secret"
    credential_fixture = b"fixture-secret-that-must-never-be-retained"
    credential_file.write_bytes(credential_fixture)
    credential_file.chmod(0o600)
    leaked = artifact_root / "pilot-v7/model-metadata-preflight/leaked.log"
    leaked.parent.mkdir(parents=True)
    leaked.write_bytes(credential_fixture)
    with pytest.raises(host.T09HostError, match="exposed the exact credential"):
        host.record_preflight_credential_scan(
            artifact_root=artifact_root,
            secret_file=credential_file,
            execution_contract_sha256="f" * 64,
        )
    assert not leaked.exists()
    receipt = json.loads(
        (artifact_root / "pilot-v7/model-metadata-credential-scan.json").read_text(encoding="utf-8")
    )
    assert receipt["actual_credential_exposure_detected"] is True
    assert "sha256" not in json.dumps(receipt)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["actual_credential_exposure_detected"] is True
    assert state["credential_safety_stop_detected"] is True
    with pytest.raises(T09BudgetExceeded, match="credential safety"):
        _mark_empirical_entry(
            state_path,
            execution_contract_sha256="f" * 64,
            run_id=ATTEMPT_ORDER[0],
        )


def test_retry3_unreconstructable_credential_cleanup_stops_without_false_exposure(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "pilot-state.json"
    initialize_pilot_state(
        state_path,
        provider_contract=V7_PROVIDER_CONTRACT,
        execution_contract_sha256="f" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    pilot_state.mark_credential_cleanup_integrity_failure(
        state_path,
        execution_contract_sha256="f" * 64,
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["actual_credential_exposure_detected"] is False
    assert state["credential_safety_stop_detected"] is True
    with pytest.raises(T09BudgetExceeded, match="credential safety"):
        _mark_empirical_entry(
            state_path,
            execution_contract_sha256="f" * 64,
            run_id=ATTEMPT_ORDER[0],
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
    supervisor_root = raw_root / host.CONDITION_SUPERVISOR_DIRNAME
    supervisor_root.mkdir(mode=0o700)
    legacy_cleanup_path = raw_root / "host-cleanup-receipt.json"
    cleanup = json.loads(legacy_cleanup_path.read_text(encoding="utf-8"))
    legacy_cleanup_path.unlink()
    cleanup["run_id"] = run_id
    cleanup["actual_credential_exposure_detected"] = False
    cleanup["runtime_secret_cleanup_malformed"] = False
    cleanup.update(
        {
            "core_artifact_count": 0,
            "runtime_core_artifact_count": 0,
            "core_scan_integrity_failure": False,
            "runtime_core_scan_integrity_failure": False,
            "core_safety_stop_detected": False,
            "campaign_continuation_permitted": True,
        }
    )
    cleanup_path = supervisor_root / "host-cleanup-receipt.json"
    cleanup_path.write_text(json.dumps(cleanup), encoding="utf-8")
    for name, value in {
        "attempt-wall.json": {"run_id": run_id},
        "container-command.json": {"run_id": run_id},
        "container-state.json": {"running": False},
        "gpu-accounting.json": {"run_id": run_id},
    }.items():
        (supervisor_root / name).write_text(json.dumps(value), encoding="utf-8")
    (raw_root / "condition.stdout").write_text("", encoding="utf-8")
    (raw_root / "condition.stderr").write_text("", encoding="utf-8")
    runtime_core_detection = raw_root / "runtime-core-detection.json"
    runtime_core_detection.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "scope": "condition-container-writable-roots-before-teardown",
                "core_artifacts_detected": [],
                "core_artifact_count": 0,
                "core_scan_integrity_failure": False,
                "core_content_or_hash_retained": False,
                "destructive_cleanup_not_yet_claimed": True,
            }
        ),
        encoding="utf-8",
    )
    runtime_cleanup = raw_root / "runtime-cleanup.json"
    runtime_cleanup.write_text(
        json.dumps(
            {
                "core_cleanup": {
                    "core_artifacts_detected": [],
                    "core_artifact_count": 0,
                    "core_scan_integrity_failure": False,
                    "destruction_verified": True,
                    "credential_rotation_required_due_to_core_handling": False,
                    "core_content_or_hash_retained": False,
                    "core_detection_receipt_sha256": host.file_sha256(runtime_core_detection),
                }
            }
        ),
        encoding="utf-8",
    )
    core_detection = supervisor_root / "core-artifact-detection.json"
    core_detection.write_text(
        json.dumps(
            {
                "core_artifacts_detected": [],
                "core_artifact_count": 0,
                "core_scan_integrity_failure": False,
                "core_content_or_hash_retained": False,
            }
        ),
        encoding="utf-8",
    )
    (supervisor_root / "core-artifact-cleanup.json").write_text(
        json.dumps(
            {
                "core_artifacts_detected": [],
                "core_artifact_count": 0,
                "core_scan_integrity_failure": False,
                "destruction_verified": True,
                "credential_rotation_required_due_to_core_handling": False,
                "core_content_or_hash_retained": False,
                "core_transferred_outside_remote_host": False,
                "cleanup_error_type": None,
                "core_detection_receipt_sha256": host.file_sha256(core_detection),
            }
        ),
        encoding="utf-8",
    )
    frozen_sha256 = "a" * 64
    (supervisor_root / "evaluator-overlay-binding.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "frozen_run_manifest_sha256": frozen_sha256,
                "condition_mount_policy": "read-only",
            }
        ),
        encoding="utf-8",
    )
    (supervisor_root / "runtime-reconstruction-binding.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "runtime_cleanup_present": True,
                "runtime_cleanup_path_observed": True,
                "runtime_cleanup_content_read_permitted": True,
                "runtime_cleanup_sha256": host.file_sha256(runtime_cleanup),
                "host_cleanup_receipt_sha256": host.file_sha256(cleanup_path),
                "container_state_sha256": host.file_sha256(
                    supervisor_root / "container-state.json"
                ),
                "host_teardown_is_source_grounded_fallback": True,
            }
        ),
        encoding="utf-8",
    )
    state = artifact_root / "pilot-v7/pilot-state.json"
    initialize_pilot_state(
        state,
        provider_contract=V7_PROVIDER_CONTRACT,
        execution_contract_sha256="b" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    _mark_empirical_entry(state, execution_contract_sha256="b" * 64, run_id=run_id)
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
    assert "seal_consumed_raw_or_essential_failure(" in execute_source
    assert "verify_packages=True" not in execute_source
