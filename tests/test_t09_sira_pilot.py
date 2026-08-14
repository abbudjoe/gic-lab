from __future__ import annotations

import ast
import copy
import importlib.util
import inspect
import io
import json
import stat
import time
from dataclasses import replace
from pathlib import Path
from shutil import copytree
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest

from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness.lambda_campaign_lifecycle import ObserverLifecycleLimits
from giclab.harness.lambda_l2m_observer import ObserverRequest
from giclab.harness.sira_gate_a import (
    ImmutableModelRouting,
    ModelRole,
    ProviderBudgetBoundary,
    ProviderBudgetExceeded,
    ProviderBudgetUsage,
    ProviderRequest,
    ProviderResponseUsage,
)
from giclab.harness.t09_sira_pilot import (
    ATTEMPT_ORDER,
    CampaignLifecycleLimits,
    EvaluatorIdentity,
    EventWriter,
    PairCheckpointInput,
    ResourceGuard,
    RuntimeLimits,
    RuntimeQualification,
    T09BudgetExceeded,
    diff_pair_manifests,
    evaluate_retained_session,
    file_sha256,
    first_pair_decision,
    initialize_pilot_state,
    load_execution_contract,
    mark_attempt_completed,
    mark_empirical_entry,
    mark_raw_attempt_complete,
    outcome_contract,
    record_first_pair_checkpoint,
    render_command_manifest,
    structurally_redact,
)
from giclab.registry import load_json
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_ROOT = ROOT / "tests/fixtures/t09/pinned-evaluator"
DATASET_FIXTURE = ROOT / "tests/fixtures/t09/fanout-two-task-fixture.json"
TASK_A = "What is the batting hand of each of the first five picks in the 1998 MLB draft?"
TASK_B = "What were box office values of the Star Wars films in the prequel and sequel trilogies?"
EXECUTION_CONTRACT = (
    ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
    "T09_PILOT_EXECUTION_CONTRACT.json"
)
RUNTIME_IDENTITY = (
    ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
    "T09_PILOT_RUNTIME_IDENTITY.json"
)


def _rendered_v5_manifests() -> list[dict[str, object]]:
    """Render the active source contract without relying on generated package bytes."""

    contract = load_execution_contract(
        EXECUTION_CONTRACT,
        expected_sha256=file_sha256(EXECUTION_CONTRACT),
    )
    return [
        render_command_manifest(
            contract,
            attempt,
            execution_contract_runtime_path="/opt/giclab-contracts/execution.json",
            runtime_adaptation_path="/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
            runtime_adaptation_sha256=file_sha256(
                ROOT / "src/giclab/harness/sira_gate_a_runtime.py"
            ),
            pilot_library_sha256=file_sha256(ROOT / "src/giclab/harness/t09_sira_pilot.py"),
            aggregate_ledger_path="/opt/giclab-artifacts/pilot-v5/aggregate-budget.json",
            pilot_state_path="/opt/giclab-artifacts/pilot-v5/pilot-state.json",
        )
        for attempt in contract.attempts
    ]


def _seal_and_finalize_state(path: Path, *, digest: str, run_id: str) -> None:
    """Supply one exact raw seal and one uniform downstream selection to state tests."""

    index = ATTEMPT_ORDER.index(run_id) + 1
    mark_raw_attempt_complete(
        path,
        execution_contract_sha256=digest,
        run_id=run_id,
        raw_manifest_sha256=f"{index:x}" * 64,
        raw_receipt_sha256=f"{index + 4:x}" * 64,
    )
    mark_attempt_completed(
        path,
        execution_contract_sha256=digest,
        run_id=run_id,
        finalizer_execution_mode="qualified-image",
        finalizer_runtime_qualification_sha256="0" * 64,
        finalizer_source_sha256="a" * 64,
        finalizer_projection_source_sha256="9" * 64,
        finalizer_commit="b" * 40,
        finalizer_dependency_manifest_sha256="c" * 64,
        evaluator_contract_sha256="d" * 64,
        interpreter="/opt/sira/.venv/bin/python",
        interpreter_sha256="e" * 64,
        semantic_projection_sha256="f" * 64,
        finalized_output_root=f"finalized/{run_id}/v1",
        finalization_complete_sha256=f"{index + 8:x}" * 64,
    )


def _session(
    path: Path,
    *,
    goal: str,
    action: str,
    history: bool = True,
    complete: bool | None = None,
) -> Path:
    value = {
        "goal": goal,
        "instance_id": None,
        "history": [[{"url": "about:blank"}, action, {"thought": "fixture"}]] if history else [],
        "is_complete": (action.startswith("send_msg_to_user") if complete is None else complete),
        "error": "",
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _identity(task_index: int = 0) -> EvaluatorIdentity:
    return EvaluatorIdentity(
        root=EVALUATOR_ROOT,
        dataset_path=DATASET_FIXTURE,
        task_index=task_index,
        fixture_subset=True,
    )


def test_exact_upstream_evaluator_files_and_fixture_rows_are_hash_locked() -> None:
    _identity(0).verify()
    _identity(1).verify()


@pytest.mark.parametrize(
    ("name", "action", "expected_score", "answer_produced", "task_completed"),
    [
        (
            "clearly-correct",
            "send_msg_to_user('Pat Burrell Right; Mark Mulder Left; Corey Patterson Left; "
            "Jeff Austin Right; JD Drew Left')",
            0.9,
            True,
            True,
        ),
        ("clearly-incorrect", "send_msg_to_user('No relevant answer.')", 0.0, True, True),
        ("partial", "send_msg_to_user('Pat Burrell bats Right.')", 0.3, True, True),
        ("missing-answer", "click('body')", 0.0, False, False),
        (
            "normalization-edge",
            "send_msg_to_user('PAT BURRELL: RIGHT! MARK MULDER, LEFT; COREY PATTERSON "
            "LEFT. JEFF AUSTIN RIGHT? JD DREW LEFT.')",
            1.0,
            True,
            True,
        ),
    ],
)
def test_offline_evaluator_answer_fixtures(
    tmp_path: Path,
    name: str,
    action: str,
    expected_score: float,
    answer_produced: bool,
    task_completed: bool,
) -> None:
    session = _session(tmp_path / f"{name}.json", goal=TASK_A, action=action)
    result = evaluate_retained_session(_identity(), [session])
    assert result["evaluator_valid"] is True
    assert result["score"] == pytest.approx(expected_score)
    assert result["answer_produced"] is answer_produced
    assert result["task_completed"] is task_completed


def test_offline_evaluator_malformed_output_is_scored_but_not_completed(tmp_path: Path) -> None:
    session = _session(
        tmp_path / "malformed.json",
        goal=TASK_A,
        action="send_msg_to_user('Pat Burrell Right'",
    )
    result = evaluate_retained_session(_identity(), [session])
    assert result["evaluator_valid"] is True
    assert result["answer_produced"] is False
    assert result["task_completed"] is False
    assert result["score"] == pytest.approx(0.3)


def test_offline_evaluator_requires_exact_retained_session_completion_state(
    tmp_path: Path,
) -> None:
    session = _session(
        tmp_path / "not-complete.json",
        goal=TASK_A,
        action="send_msg_to_user('Pat Burrell bats Right.')",
        complete=False,
    )
    result = evaluate_retained_session(_identity(), [session])
    assert result["evaluator_valid"] is True
    assert result["answer_produced"] is True
    assert result["task_completed"] is False


def test_offline_evaluator_exception_is_explicit_and_unscored(tmp_path: Path) -> None:
    session = _session(
        tmp_path / "exception.json",
        goal=TASK_A,
        action="",
        history=False,
    )
    result = evaluate_retained_session(_identity(), [session])
    assert result["evaluator_valid"] is False
    assert result["failure_code"] == "evaluator_exception"
    assert result["score"] is None


def test_offline_evaluator_duplicate_evidence_fails_closed(tmp_path: Path) -> None:
    session = _session(
        tmp_path / "duplicate.json",
        goal=TASK_A,
        action="send_msg_to_user('No relevant answer.')",
    )
    result = evaluate_retained_session(_identity(), [session, session])
    assert result == {
        "schema_version": "0.1.0",
        "evaluator_valid": False,
        "failure_code": "duplicate_evidence",
        "score": None,
        "upstream_output": None,
    }


def test_second_frozen_task_scores_with_same_exact_evaluator(tmp_path: Path) -> None:
    session = _session(
        tmp_path / "task-b.json",
        goal=TASK_B,
        action=(
            "send_msg_to_user('The Phantom Menace $1.027 billion; Attack of the Clones "
            "$653.8 million; Revenge of the Sith $868.4 million; The Force Awakens "
            "$2.071 billion; The Last Jedi $1.334 billion; The Rise of Skywalker "
            "$1.077 billion')"
        ),
    )
    result = evaluate_retained_session(_identity(1), [session])
    assert result["evaluator_valid"] is True
    # This exact ordinary fully-correct fixture scores 0.5 under the pinned code.
    # It does not prove a mathematical upper bound over every possible answer.
    assert result["score"] == 0.5


def test_second_frozen_task_normalization_edge_can_score_one(tmp_path: Path) -> None:
    session = _session(
        tmp_path / "task-b-normalization-edge.json",
        goal=TASK_B,
        action=(
            "send_msg_to_user('The Phantom Menace x$ 1.027 billion; Attack of the Clones "
            "x$ 653.8 million; Revenge of the Sith x$ 868.4 million; The Force Awakens "
            "x$ 2.071 billion; The Last Jedi x$ 1.334 billion; The Rise of Skywalker "
            "x$ 1.077 billion')"
        ),
    )
    result = evaluate_retained_session(_identity(1), [session])
    assert result["evaluator_valid"] is True
    assert result["score"] == 1.0


def _limits() -> RuntimeLimits:
    return RuntimeLimits(
        expected_browser_actions_per_attempt=18,
        max_browser_actions_per_attempt=30,
        max_model_calls_per_attempt=1_155,
        max_model_tokens_per_attempt=1_000_000,
        max_openai_cost_usd_per_attempt=10.0,
        max_condition_wall_seconds=3_600,
        max_pair_wall_seconds=7_200,
        max_total_wall_seconds=14_400,
        max_output_bytes_per_attempt=1_073_741_824,
        max_disk_bytes=12_884_901_888,
        max_lambda_duration_seconds=14_400,
        max_lambda_cost_usd=5.16,
        max_attempts=4,
        max_retries_after_empirical_entry=0,
    )


def test_runtime_caps_are_pair_equal_and_sum_to_candidate_ceilings() -> None:
    limits = _limits()
    condition = limits.condition_provider_caps()
    aggregate = limits.aggregate_provider_caps()
    assert condition.max_model_call_attempts == 1_155
    assert aggregate.max_model_call_attempts == 4_620
    assert aggregate.max_total_tokens == 4_000_000
    assert aggregate.max_browser_actions == 120
    assert aggregate.max_cost_usd == 40.0


def test_provider_boundary_enforces_prior_attempt_aggregate_before_send() -> None:
    limits = _limits()
    persisted: list[ProviderBudgetUsage] = []
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=limits.aggregate_provider_caps(),
        condition_caps=limits.condition_provider_caps(),
        initial_aggregate_usage=ProviderBudgetUsage(
            model_call_attempts=4_619,
            default_service_tier_responses=4_619,
        ),
        persist_aggregate=lambda usage, _: persisted.append(usage),
    )
    request = ProviderRequest(
        role=ModelRole.ACTOR,
        model="gpt-4o-2024-11-20",
        input_tokens=1,
        max_output_tokens=1,
    )

    def send(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        return "ok", ProviderResponseUsage(1, 0, 1, "default")

    assert boundary.invoke(request, send) == "ok"
    with pytest.raises(ProviderBudgetExceeded, match="aggregate"):
        boundary.invoke(request, send)
    assert persisted[-1].model_call_attempts == 4_620


def test_frozen_execution_contract_and_all_pair_command_diffs() -> None:
    manifests = _rendered_v5_manifests()
    assert diff_pair_manifests(manifests[0], manifests[1])["valid"] is True
    assert diff_pair_manifests(manifests[2], manifests[3])["valid"] is True
    assert (
        manifests[0]["equality_surface"]["config_sha256"]
        == manifests[1]["equality_surface"]["config_sha256"]
    )
    assert (
        manifests[2]["equality_surface"]["protocol_sha256"]
        == manifests[3]["equality_surface"]["protocol_sha256"]
    )
    assert [manifest["run_id"] for manifest in manifests] == list(ATTEMPT_ORDER)

    drifted = copy.deepcopy(manifests[1])
    seed_index = drifted["argv"].index("--seed") + 1
    drifted["argv"][seed_index] = "999"
    assert diff_pair_manifests(manifests[0], drifted)["valid"] is False


def test_resource_guard_stops_before_wall_output_disk_or_lambda_overrun(tmp_path: Path) -> None:
    clock = iter([1.0, 20_000.0])
    guard = ResourceGuard(
        _limits(),
        attempt_root=tmp_path / "attempt",
        pilot_root=tmp_path,
        condition_started=0.0,
        pair_started=0.0,
        pilot_started=0.0,
        lambda_started=0.0,
        monotonic=lambda: next(clock),
    )
    assert guard.check().condition_elapsed_seconds == 1.0
    with pytest.raises(T09BudgetExceeded, match="hard resource cap exceeded"):
        guard.check()


def test_first_pair_checkpoint_passes_only_strictly_below_every_threshold() -> None:
    passing = PairCheckpointInput(
        attempt_run_ids=(ATTEMPT_ORDER[0], ATTEMPT_ORDER[1]),
        valid_evidence=(True, True),
        evaluator_succeeded=(True, True),
        pair_match_valid=True,
        credential_issue=False,
        cleanup_issue=False,
        severe_floor_or_ceiling_failure=False,
        actual_usage=ProviderBudgetUsage(
            cost_usd=0.72,
            input_tokens=100_000,
            output_tokens=10_000,
            total_tokens=110_000,
            model_call_attempts=162,
            default_service_tier_responses=162,
            browser_actions=36,
        ),
        actual_pair_wall_seconds=1_440.0,
        projected_aggregate_cost_usd=2.49,
        actual_lambda_cost_usd=0.52,
        remaining_campaign_seconds=10_000.0,
    )
    assert first_pair_decision(passing)["decision"] == "continue-to-task-b"
    stopping = replace(passing, cleanup_issue=True)
    decision = first_pair_decision(stopping)
    assert decision["decision"] == "stop-before-task-b"
    reasons = decision["reasons"]
    assert isinstance(reasons, list)
    assert "cleanup_issue" in reasons
    no_time = replace(passing, remaining_campaign_seconds=4_499.999)
    no_time_decision = first_pair_decision(no_time)
    assert no_time_decision["decision"] == "stop-before-task-b"
    assert "insufficient_campaign_time_for_next_attempt_and_cleanup" in no_time_decision["reasons"]
    exact_time = replace(passing, remaining_campaign_seconds=4_500.0)
    exact_time_decision = first_pair_decision(exact_time)
    assert exact_time_decision["decision"] == "continue-to-task-b"
    assert exact_time_decision["required_campaign_seconds_for_next_attempt"] == 4_500
    cumulative_overflow = replace(
        passing,
        projected_aggregate_cost_usd=45.0,
        prior_t09_cost_usd=3.01,
    )
    assert (
        "projected_cumulative_t09_cost_exceeds_hard_cap"
        in first_pair_decision(cumulative_overflow)["reasons"]
    )


def test_attempt_state_enforces_order_cap_checkpoint_and_zero_retry(tmp_path: Path) -> None:
    path = tmp_path / "pilot-state.json"
    digest = "a" * 64
    initialize_pilot_state(
        path,
        execution_contract_sha256=digest,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    with pytest.raises(T09BudgetExceeded, match="order"):
        mark_empirical_entry(
            path,
            execution_contract_sha256=digest,
            run_id=ATTEMPT_ORDER[1],
        )
    mark_empirical_entry(
        path,
        execution_contract_sha256=digest,
        run_id=ATTEMPT_ORDER[0],
    )
    with pytest.raises(T09BudgetExceeded, match="zero-retry"):
        mark_empirical_entry(
            path,
            execution_contract_sha256=digest,
            run_id=ATTEMPT_ORDER[0],
        )
    _seal_and_finalize_state(path, digest=digest, run_id=ATTEMPT_ORDER[0])
    mark_empirical_entry(
        path,
        execution_contract_sha256=digest,
        run_id=ATTEMPT_ORDER[1],
    )
    _seal_and_finalize_state(path, digest=digest, run_id=ATTEMPT_ORDER[1])
    with pytest.raises(T09BudgetExceeded, match="checkpoint"):
        mark_empirical_entry(
            path,
            execution_contract_sha256=digest,
            run_id=ATTEMPT_ORDER[2],
        )
    record_first_pair_checkpoint(
        path,
        execution_contract_sha256=digest,
        decision={"decision": "continue-to-task-b"},
        decided_at_epoch=2.0,
    )
    mark_empirical_entry(
        path,
        execution_contract_sha256=digest,
        run_id=ATTEMPT_ORDER[2],
    )


def test_exit_zero_does_not_imply_completion_or_valid_score() -> None:
    result = outcome_contract(
        process_exit_code=0,
        artifact_executed=True,
        task_completed=False,
        answer_produced=False,
        evaluator_valid=True,
        score=0.0,
        infrastructure_failure=False,
        missing_required_evidence=False,
    )
    assert result["process_exit"] == {"observed": True, "code": 0, "zero": True}
    assert result["task_completion"] == "incomplete"
    assert result["condition_failure"] is True
    assert result["valid_scored_attempt"] is True


def test_evidence_redaction_is_structural_and_event_lineage_is_explicit(tmp_path: Path) -> None:
    redacted = structurally_redact(
        {
            "jupyter_url": "value-must-not-survive",
            "nested": {"api_key": "value-must-not-survive", "safe": "retained"},
        }
    )
    assert redacted == {
        "jupyter_url": {"redacted": True, "reason": "structural-sensitive-field"},
        "nested": {
            "api_key": {"redacted": True, "reason": "structural-sensitive-field"},
            "safe": "retained",
        },
    }
    writer = EventWriter(tmp_path / "events.jsonl")
    parent = writer.append("agent-step", {"safe": True})
    child = writer.append(
        "provider-receipt",
        {"provider_account_id": "hidden"},
        parent_event_id=parent,
    )
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert child == events[1]["event_id"]
    assert events[1]["parent_event_id"] == parent
    assert "hidden" not in json.dumps(events)


def test_execution_schema_and_all_static_file_bindings_resolve() -> None:
    document = load_json(EXECUTION_CONTRACT)
    assert document["authorized"] is False
    assert document["terminal_state"] == (
        "current-turn-authorized-retry3-pending-dynamic-preflight"
    )
    assert (
        document["execution_eligibility"]
        == "current-turn-authorized-after-replacement-image-qualification"
    )
    assert document["material_blockers"] == []
    hard = document["budget_calibration"]["hard"]
    assert hard["maximum_new_cost_under_cumulative_cap_usd"] == pytest.approx(
        hard["cumulative_t09_cost_cap_usd"] - hard["prior_t09_cost_usd"],
        abs=1e-12,
    )
    assert (
        validate_instance(
            document,
            ROOT / "schemas/t09-sira-pilot-execution.schema.json",
        )
        == []
    )
    bindings = document["contract_bindings"]
    assert isinstance(bindings, dict)
    for raw in bindings.values():
        assert isinstance(raw, dict)
        path = ROOT / raw["path"]
        assert file_sha256(path) == raw["sha256"]
        if "size_bytes" in raw:
            assert path.stat().st_size == raw["size_bytes"]


def test_runtime_identity_binds_every_selected_executable_file() -> None:
    document = load_json(RUNTIME_IDENTITY)
    instrumentation = document["repository_instrumentation"]
    assert isinstance(instrumentation, dict)
    files = instrumentation["files"]
    assert isinstance(files, list)
    expected = {
        "src/giclab/harness/sira_gate_a.py",
        "src/giclab/harness/safety.py",
        "src/giclab/harness/sira_gate_a_runtime.py",
        "src/giclab/harness/t09_sira_pilot.py",
        "src/giclab/harness/lambda_campaign_lifecycle.py",
        "src/giclab/harness/lambda_l2m_observer.py",
        "src/giclab/harness/t09_pragmatic_provider.py",
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py",
        "containers/sira-smoke/pragmatic/t09_preflight.py",
        "containers/sira-smoke/pragmatic/t09_freeze_commands.py",
        "containers/sira-smoke/pragmatic/t09_secret_preflight.py",
        "containers/sira-smoke/pragmatic/materialize_openai_secret.py",
        "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py",
        "containers/sira-smoke/pragmatic/t09_finalizer_projection.py",
        "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py",
    }
    assert {item["path"] for item in files} == expected
    for item in files:
        assert file_sha256(ROOT / item["path"]) == item["sha256"]


def test_runtime_and_execution_bind_the_same_current_evaluator_contract() -> None:
    runtime = load_json(RUNTIME_IDENTITY)
    execution = load_json(EXECUTION_CONTRACT)
    evaluator_binding = execution["contract_bindings"]["evaluator"]
    evaluator_path = ROOT / evaluator_binding["path"]
    observed_sha256 = file_sha256(evaluator_path)
    assert evaluator_binding["sha256"] == observed_sha256
    assert runtime["evaluator_overlay"]["contract_sha256"] == observed_sha256


def test_retry2_preserves_and_supersedes_the_zero_use_v3_failure() -> None:
    experiment = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
    disposition = experiment / "T09_PRAGMATIC_PREFLIGHT_DISPOSITION.json"
    supersession = load_json(experiment / "T09_PRAGMATIC_RETRY2_SUPERSESSION.json")
    assert file_sha256(disposition) == (
        "cb6ba0b003b61aec83a2a42188ee784c93ee08ae7e504f5a15a7287af83ac709"
    )
    historical = supersession["historical_disposition"]
    assert historical["classification"] == (
        "preflight_blocked_by_overstrict_cross_run_image_digest_requirement"
    )
    assert {
        key: historical[key] for key in ("model_calls", "browser_actions", "condition_attempts")
    } == {"model_calls": 0, "browser_actions": 0, "condition_attempts": 0}
    assert historical["empirical_boundary_crossed"] is False
    assert supersession["successor_plan_id"] == "PLAN-EXP0001-PILOT-V4"


def test_runtime_qualification_is_typed_single_build_preentry_and_digest_agnostic() -> None:
    document = {
        "schema_version": "0.1.0",
        "plan_id": "PLAN-EXP0001-PILOT-V5",
        "manifest_id": "RUN-MANIFEST-EXP0001-PILOT-V5-0003",
        "qualification_id": "QUAL-T09-PILOT-V5-IMAGE-0001",
        "clean_package_commit": "a" * 40,
        "replacement_image_id": "sha256:" + "e" * 64,
        "historical_image_id": (
            "sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c"
        ),
        "build_context_manifest_sha256": "b" * 64,
        "package_manifest_sha256": "c" * 64,
        "chromium_executable_sha256": "d" * 64,
        "patched_upstream_runner_sha256": "f" * 64,
        "python_interpreter_path": "/opt/sira/.venv/bin/python",
        "python_interpreter_sha256": "4" * 64,
        "evaluator_overlay_manifest_sha256": "1" * 64,
        "evaluator_overlay_entries_sha256": "2" * 64,
        "evaluator_overlay_packages_sha256": "3" * 64,
        "qualified_real_evidence_regression_sha256": "5" * 64,
        "local_finalizer_qualification_sha256": "6" * 64,
        "local_finalizer_interpreter_dependency_manifest_sha256": "7" * 64,
        "local_finalizer_interpreter_dependency_tree_sha256": "8" * 64,
        "local_finalizer_evaluator_dependency_tree_sha256": "9" * 64,
        "model_metadata_request_count": 1,
        "model_task_request_count": 0,
        "task_browser_action_count": 0,
        "build_count": 1,
        "qualification_count": 1,
        "empirical_entry_crossed": False,
        "post_entry_code_science_image_freeze": True,
        "preflight_transition_mode": "fresh",
        "preflight_resume_source_sha256": None,
        "preflight_resume_argv_sha256": None,
        "preflight_resume_transition_sha256": None,
        "preflight_failure_prefix_manifest_sha256": None,
        "preflight_prior_package_commit": None,
        "preflight_prior_plan_sha256": None,
        "preflight_prior_state_sha256": None,
        "preflight_transition_state_sha256": None,
        "preflight_prior_aggregate_sha256": None,
        "preflight_transition_aggregate_sha256": None,
        "preflight_retained_materialization_sha256": None,
    }
    qualification = RuntimeQualification.from_document(document)
    assert qualification.replacement_image_id != qualification.historical_image_id
    for field, value in (
        ("build_count", 2),
        ("model_metadata_request_count", 0),
        ("model_task_request_count", 1),
        ("task_browser_action_count", 1),
        ("empirical_entry_crossed", True),
    ):
        drifted = {**document, field: value}
        with pytest.raises(ValueError, match="qualification contract drifted"):
            RuntimeQualification.from_document(drifted)
    recovered = {
        **document,
        "preflight_transition_mode": "same-host-resume",
        "preflight_resume_source_sha256": "a" * 64,
        "preflight_resume_argv_sha256": "b" * 64,
        "preflight_resume_transition_sha256": "c" * 64,
        "preflight_failure_prefix_manifest_sha256": "d" * 64,
        "preflight_prior_package_commit": "3640f061ea6c0f0f3d24bf2a346d4beda1a400cf",
        "preflight_prior_plan_sha256": (
            "e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c"
        ),
        "preflight_prior_state_sha256": "e" * 64,
        "preflight_transition_state_sha256": "f" * 64,
        "preflight_prior_aggregate_sha256": "1" * 64,
        "preflight_transition_aggregate_sha256": "2" * 64,
        "preflight_retained_materialization_sha256": "3" * 64,
    }
    assert (
        RuntimeQualification.from_document(recovered).preflight_transition_mode
        == "same-host-resume"
    )
    recovered["preflight_resume_argv_sha256"] = None
    with pytest.raises(ValueError, match="resume binding drifted"):
        RuntimeQualification.from_document(recovered)


def test_retry2_excludes_only_the_exact_pinned_names_only_env_example(
    tmp_path: Path,
) -> None:
    host = _load_host_runner()
    upstream = tmp_path / "upstream"
    materialization = tmp_path / "qualification"
    upstream.mkdir()
    materialization.mkdir()
    example = upstream / ".env.example"
    example.write_bytes(host.PINNED_ENV_EXAMPLE_CONTENT)
    receipt = host._exclude_pinned_nonruntime_env_example(
        upstream,
        materialization=materialization,
    )
    assert not example.exists()
    assert receipt["sha256"] == host.PINNED_ENV_EXAMPLE_SHA256
    assert receipt["contained_credential_value"] is False
    assert receipt["runtime_input"] is False
    assert receipt["scientific_input"] is False
    assert (materialization / "build-context-exclusions.json").stat().st_mode & 0o777 == 0o600

    unsafe_upstream = tmp_path / "unsafe-upstream"
    unsafe_materialization = tmp_path / "unsafe-qualification"
    unsafe_upstream.mkdir()
    unsafe_materialization.mkdir()
    (unsafe_upstream / ".env.example").write_bytes(
        host.PINNED_ENV_EXAMPLE_CONTENT.replace(b"OPENAI_API_KEY=", b"OPENAI_API_KEY=value")
    )
    with pytest.raises(host.T09HostError, match="identity or content drifted"):
        host._exclude_pinned_nonruntime_env_example(
            unsafe_upstream,
            materialization=unsafe_materialization,
        )


def test_retry3_builds_one_fresh_v5_image_and_uses_the_pinned_interpreter() -> None:
    host = _load_host_runner()
    assert host.PLAN_ID == "PLAN-EXP0001-PILOT-V5"
    assert host.QUALIFICATION_ID == "QUAL-T09-PILOT-V5-IMAGE-0001"
    assert host.REPLACEMENT_IMAGE_TAG.startswith("giclab/t09-pilot-v5:")
    materializer = inspect.getsource(host.materialize_replacement_image)
    assert "exactly one build is allowed" in materializer
    assert '"build_count": 1' in materializer
    assert "carry_forward_replacement_image" not in materializer
    offline = inspect.getsource(host.offline_runtime_preflight)
    assert "/opt/sira/.venv/bin/python" in offline
    assert "PYTHONPATH=/opt/evaluator/.venv/lib/python3.11/site-packages:/opt/giclab-src" in offline
    assert '"/opt/evaluator/.venv/bin/python"' not in offline
    finalizer = inspect.getsource(host.evaluator_argv)
    assert '"interpreter_sha256"' in finalizer
    assert 'frozen_manifest["python_interpreter_sha256"]' in finalizer


def test_v5_runtime_corrects_historical_package_browser_and_patched_runner_identities() -> None:
    runtime = load_json(RUNTIME_IDENTITY)
    execution = load_json(EXECUTION_CONTRACT)
    assert runtime["base_runtime"]["installed_package_manifest_sha256"] == (
        "4ff2603fa5e0f7033ba773decdcb86abf648dcce22e469d26bc48214e390e104"
    )
    assert runtime["base_runtime"]["chromium_sha256"] == (
        "0498f208c25339f386413ada7b3c35293b0b6250e67d85446ba9541d7fd636f7"
    )
    assert runtime["scientific_runtime"]["runner_sha256"] == (
        "b06793ad1b366a934b798f9f3272fc80a7104a220cb3304ab3bda2eb2a78b331"
    )
    assert execution["runtime"]["container_image_digest"] is None
    assert runtime["replacement_image_policy"]["exact_historical_digest_equality_required"] is (
        False
    )


def _load_host_runner() -> ModuleType:
    path = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
    spec = importlib.util.spec_from_file_location("giclab_t09_host_runner_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_attempt_finalizer() -> ModuleType:
    path = ROOT / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
    spec = importlib.util.spec_from_file_location("giclab_t09_attempt_finalizer_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_openai_secret_materializer() -> ModuleType:
    path = ROOT / "containers/sira-smoke/pragmatic/materialize_openai_secret.py"
    spec = importlib.util.spec_from_file_location("giclab_t09_openai_secret_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_t09_openai_secret_materializer_is_exact_single_assignment_and_exclusive(
    tmp_path: Path,
) -> None:
    materializer = _load_openai_secret_materializer()
    raw = b"LAMBDA_API_KEY=lambda-canary\nOPENAI_API_KEY=openai-canary_123\n"
    assert materializer.parse_openai_api_key(raw) == b"openai-canary_123"
    with pytest.raises(RuntimeError, match="exactly one"):
        materializer.parse_openai_api_key(raw + b"OPENAI_API_KEY=second\n")
    with pytest.raises(RuntimeError, match="single-token"):
        materializer.parse_openai_api_key(b"OPENAI_API_KEY=unsafe value\n")
    dotenv = tmp_path / "private.env"
    dotenv.write_bytes(raw)
    dotenv.chmod(0o600)
    assert materializer._read_regular_nofollow(dotenv, max_bytes=65_536) == raw
    destination = tmp_path / "sira_api_key"
    materializer.write_secret_exclusive(destination, b"openai-canary_123")
    assert destination.read_bytes() == b"openai-canary_123"
    assert destination.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        materializer.write_secret_exclusive(destination, b"replacement")
    dotenv.chmod(0o644)
    with pytest.raises(RuntimeError, match="metadata is unsafe"):
        materializer._read_regular_nofollow(dotenv, max_bytes=65_536)


def test_evaluator_overlay_package_records_match_all_reviewed_versions() -> None:
    host = _load_host_runner()
    expected = host.expected_evaluator_packages(ROOT)
    assert len(expected) == 51
    assert "en-core-web-sm==3.8.0" in expected
    realized = "\n".join(
        host.EVALUATOR_DIRECT_URL_RECORD if package == "en-core-web-sm==3.8.0" else package
        for package in expected
    )
    assert (
        host.normalize_evaluator_package_records(
            realized,
            expected_packages=expected,
        )
        == expected
    )
    with pytest.raises(host.T09HostError, match="unsafe or ambiguous"):
        host.normalize_evaluator_package_records(
            realized.replace(host.EVALUATOR_DIRECT_URL_RECORD, "en-core-web-sm @ file:///tmp/x"),
            expected_packages=expected,
        )
    with pytest.raises(host.T09HostError, match="differs from the reviewed contract"):
        host.normalize_evaluator_package_records(
            "\n".join(realized.splitlines()[:-1]),
            expected_packages=expected,
        )


def test_evaluator_overlay_inventory_detects_any_realized_byte_drift(tmp_path: Path) -> None:
    host = _load_host_runner()
    overlay = tmp_path / "overlay"
    overlay.mkdir(mode=0o700)
    package = overlay / "package"
    package.mkdir(mode=0o755)
    module = package / "module.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    (overlay / "python").symlink_to("package/module.py")
    retained = host.evaluator_overlay_inventory(overlay)
    assert {entry["type"] for entry in retained["entries"]} == {
        "directory",
        "file",
        "symlink",
    }
    host._validate_evaluator_overlay_inventory(overlay=overlay, retained=retained)
    module.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(host.T09HostError, match="changed after qualification"):
        host._validate_evaluator_overlay_inventory(overlay=overlay, retained=retained)


def test_first_pair_gross_ceiling_stops_task_b() -> None:
    host = _load_host_runner()
    ceiling = [
        {
            "valid_scored_attempt": True,
            "task_completion": "completed",
            "task_score": 1.0,
        },
        {
            "valid_scored_attempt": True,
            "task_completion": "completed",
            "task_score": 1.0,
        },
    ]
    assert host._severe_floor_or_ceiling(ceiling) is True
    ceiling[1]["task_score"] = 0.5
    assert host._severe_floor_or_ceiling(ceiling) is False


def test_preentry_condition_prefix_is_bound_preserved_and_retryable(tmp_path: Path) -> None:
    host = _load_host_runner()
    manifest = _rendered_v5_manifests()[0]
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / manifest["permitted_condition_owned"]["output_root"]
    attempt_root.mkdir(parents=True, mode=0o700)
    (attempt_root / "container-command.json").write_text("{}\n", encoding="utf-8")
    prefix_entries = host.preentry_prefix_inventory(attempt_root)
    execution_sha256 = "a" * 64
    frozen_sha256 = "b" * 64
    package_commit = "c" * 40
    receipt = {
        "schema_version": "0.1.0",
        "plan_id": host.PLAN_ID,
        "host_run_id": host.HOST_RUN_ID,
        "run_id": manifest["run_id"],
        "clean_package_commit": package_commit,
        "execution_contract_sha256": execution_sha256,
        "frozen_run_manifest_sha256": frozen_sha256,
        "condition_plan_sha256": manifest["condition_plan_sha256"],
        "condition_argv_sha256": manifest["argv_sha256"],
        "empirical_entry_crossed": False,
        "attempt_identity_consumed": False,
        "container_absent": True,
        "remaining_exact_secret_matches": [],
        "structural_privacy_violations": [],
        "failure_prefix_entries": prefix_entries,
        "failure_prefix_entries_sha256": host.canonical_sha256(prefix_entries),
        "retry_same_frozen_condition_permitted": True,
    }
    (attempt_root / "preentry-condition-failure.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    state = {
        "execution_contract_sha256": execution_sha256,
        "empirical_attempts_entered": [],
        "attempts_completed": [],
    }
    fresh, raw = host.prepare_condition_attempt_root(
        artifact_root=artifact_root,
        manifest=manifest,
        pilot_state=state,
        package_commit=package_commit,
        frozen_run_manifest_sha256=frozen_sha256,
    )
    preserved = (
        artifact_root / "pilot-v5/preentry-condition-repairs" / manifest["run_id"] / "repair-01"
    )
    assert fresh == attempt_root and fresh.is_dir() and list(fresh.iterdir()) == [raw]
    assert raw == fresh / "raw"
    assert (preserved / "preentry-condition-failure.json").is_file()
    assert (preserved / "container-command.json").is_file()


def test_preentry_condition_prefix_tamper_cannot_authorize_retry(tmp_path: Path) -> None:
    host = _load_host_runner()
    command_document = load_json(
        ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json"
    )
    manifest = command_document["manifests"][0]
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / manifest["permitted_condition_owned"]["output_root"]
    attempt_root.mkdir(parents=True, mode=0o700)
    source = attempt_root / "container-command.json"
    source.write_text("{}\n", encoding="utf-8")
    prefix_entries = host.preentry_prefix_inventory(attempt_root)
    receipt = {
        "schema_version": "0.1.0",
        "plan_id": host.PLAN_ID,
        "host_run_id": host.HOST_RUN_ID,
        "run_id": manifest["run_id"],
        "clean_package_commit": "c" * 40,
        "execution_contract_sha256": "a" * 64,
        "frozen_run_manifest_sha256": "b" * 64,
        "condition_plan_sha256": manifest["condition_plan_sha256"],
        "condition_argv_sha256": manifest["argv_sha256"],
        "empirical_entry_crossed": False,
        "attempt_identity_consumed": False,
        "container_absent": True,
        "remaining_exact_secret_matches": [],
        "structural_privacy_violations": [],
        "failure_prefix_entries": prefix_entries,
        "failure_prefix_entries_sha256": host.canonical_sha256(prefix_entries),
        "retry_same_frozen_condition_permitted": True,
    }
    (attempt_root / "preentry-condition-failure.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )
    source.write_text('{"tampered": true}\n', encoding="utf-8")
    with pytest.raises(host.T09HostError, match="not a repairable pre-entry prefix"):
        host.prepare_condition_attempt_root(
            artifact_root=artifact_root,
            manifest=manifest,
            pilot_state={
                "execution_contract_sha256": "a" * 64,
                "empirical_attempts_entered": [],
                "attempts_completed": [],
            },
            package_commit="c" * 40,
            frozen_run_manifest_sha256="b" * 64,
        )


def test_pragmatic_provider_entry_and_closeout_receipts_are_exact_and_source_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    now = [2_000_000_000.0]

    def clock() -> float:
        now[0] += 1.0
        return now[0]

    def sleeper(seconds: float) -> None:
        now[0] += seconds

    class FakeTransport:
        def __init__(
            self,
            responses: list[object],
        ) -> None:
            self.responses = responses
            self.calls: list[tuple[str, str, bytes | None]] = []

        def send(
            self,
            method: str,
            path: str,
            *,
            body: bytes | None,
            credential: bytearray,
        ) -> provider.ProviderResponse:
            assert method in {"GET", "POST"}
            assert path in provider.ALLOWED_PATHS
            assert credential == bytearray(b"lambda-fixture-credential")
            assert self.responses
            self.calls.append((method, path, body))
            value = self.responses.pop(0)
            if isinstance(value, BaseException):
                raise value
            status = 200
            if isinstance(value, tuple):
                status, value = value
                assert isinstance(status, int)
            return provider.ProviderResponse(
                status,
                "application/json",
                value if isinstance(value, bytes) else json.dumps(value).encode(),
                clock(),
            )

    public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixture t09-fixture"
    public_ipv4 = "203.0.113.7"
    global_firewall = {
        "data": {
            "id": "global",
            "name": "global",
            "workspace_id": "workspace-fixture",
            "rules": [
                {
                    "protocol": "tcp",
                    "port_range": [22, 22],
                    "source_network": f"{public_ipv4}/32",
                    "description": "fixture",
                }
            ],
        }
    }
    instance = {
        "id": "instance-fixture-0001",
        "name": provider.INSTANCE_NAME,
        "hostname": provider.INSTANCE_NAME,
        "instance_type": {"name": provider.INSTANCE_TYPE},
        "region": {"name": provider.REGION},
        "status": "active",
        "ip": "198.51.100.9",
        "file_system_names": [],
    }
    launch_responses = [
        {
            "data": {
                provider.INSTANCE_TYPE: {
                    "instance_type": {
                        "name": provider.INSTANCE_TYPE,
                        "price_cents_per_hour": 129,
                    },
                    "regions_with_capacity_available": [{"name": provider.REGION}],
                }
            }
        },
        {
            "data": [
                {
                    "id": provider.IMAGE_ID,
                    "region": {"name": "us-west-2"},
                    "family": "lambda-stack-22-04",
                },
                {
                    "id": provider.IMAGE_ID,
                    "region": {"name": provider.REGION},
                    "family": "lambda-stack-22-04",
                },
            ]
        },
        {"data": [{"name": provider.SSH_KEY_NAME, "public_key": public_key}]},
        global_firewall,
        {"data": []},
        {"data": []},
        {"data": {"instance_ids": ["instance-fixture-0001"]}},
        {"data": [instance]},
    ]
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "OPENAI_API_KEY=openai-fixture-credential\nLAMBDA_API_KEY=lambda-fixture-credential\n",
        encoding="utf-8",
    )
    dotenv.chmod(0o600)
    public_ip_path = tmp_path / "public-ip.private"
    public_ip_path.write_text(public_ipv4, encoding="utf-8")
    key_path = tmp_path / "key.pub"
    key_path.write_text(public_key, encoding="utf-8")
    package_commit = "a" * 40
    plan_path = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml"
    authorization = tmp_path / "authorization.json"
    authorization.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "authorization_source_sha256": provider.AUTHORIZATION_SOURCE_SHA256,
                "authorization_reference": "AUTH-T09-PRAGMATIC-RETRY3-2026-08-13",
                "authorized": True,
                "single_use": True,
                "clean_package_commit": package_commit,
                "plan_id": provider.PLAN_ID,
                "plan_sha256": provider.file_sha256(plan_path),
                "max_lambda_instances": 1,
                "max_launch_count": 2,
                "persistent_filesystems": 0,
                "lambda_cost_cap_usd": 5.16,
                "openai_cost_cap_usd": 40.0,
                "aggregate_cost_cap_usd": 45.16,
                "prior_t09_cost_usd": 2.5308164556905757,
                "cumulative_t09_cost_cap_usd": 48.0,
                "replacement_image_policy": ("one-build-one-qualification-preentry-bound-v1"),
                "artifact_destination": (
                    "/Volumes/Macintosh HD - Data/GIC-Lab/t09/sealed-artifacts"
                ),
            }
        ),
        encoding="utf-8",
    )
    authorization.chmod(0o600)
    monkeypatch.setattr(provider, "_verify_clean_package", lambda *_args, **_kwargs: None)
    capability = {
        1: tmp_path / "launch-capabilities/malformed.json",
        2: tmp_path / "launch-capabilities/slot-2.json",
    }
    monkeypatch.setattr(provider, "launch_capability_path", lambda slot: capability[slot])

    malformed_launch_root = tmp_path / "provider-malformed-launch"
    with pytest.raises(provider.T09ProviderError, match="launch outcome is unknown"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=malformed_launch_root,
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=FakeTransport([*copy.deepcopy(launch_responses[:6]), b"not-json"]),
            clock=clock,
            sleeper=sleeper,
        )
    assert (
        load_json(malformed_launch_root / "LAUNCH_OUTCOME_UNKNOWN.json")["second_launch_forbidden"]
        is True
    )

    # A one-ID launch owns billable compute before an entry receipt exists.  A
    # failed active poll must therefore close from the provisional source
    # binding; an ambiguous termination response is reconciled by fresh GET.
    capability[1] = tmp_path / "launch-capabilities/active-poll-failure.json"
    active_failure_root = tmp_path / "provider-active-poll-failure"
    with pytest.raises(provider.T09ProviderError, match="exact launched instance was closed"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=active_failure_root,
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=FakeTransport(
                [
                    *copy.deepcopy(launch_responses[:7]),
                    RuntimeError("active poll transport ambiguity"),
                    RuntimeError("termination response ambiguity"),
                    {"data": []},
                    global_firewall,
                    {"data": []},
                ]
            ),
            clock=clock,
            sleeper=sleeper,
        )
    provisional = load_json(active_failure_root / "provisional-owned-state.json")
    assert provisional["private_instance_id"] == "instance-fixture-0001"
    assert provisional["launch_capability_state"] == ("consumed-cleanup-only-until-entry-receipt")
    assert provider._HEX64.fullmatch(str(provisional["launch_journal_prefix_sha256"]))
    provisional_closed = load_json(active_failure_root / "PROVISIONAL_OWNER_CLOSED.json")
    assert provisional_closed["provider_disposition"] == "absent"
    assert provisional_closed["replacement_launch_eligibility_pending"] is True
    assert provisional_closed["security_restored"] is True
    assert (active_failure_root / "replacement-launch-eligibility.json").is_file()
    provider.validate_source_manifest(active_failure_root / "provisional-closeout-source")
    already_closed_transport = FakeTransport([])
    assert (
        provider.closeout_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=active_failure_root,
            transport=already_closed_transport,
            clock=clock,
            sleeper=sleeper,
        )
        == active_failure_root / "PROVISIONAL_OWNER_CLOSED.json"
    )
    assert already_closed_transport.calls == []

    # A cleanup poll ambiguity cannot be converted into a false closeout.  It
    # preserves the exact private target and a no-relaunch console action.
    capability[1] = tmp_path / "launch-capabilities/cleanup-poll-failure.json"
    cleanup_failure_root = tmp_path / "provider-cleanup-poll-failure"
    with pytest.raises(provider.T09ProviderError, match="durable console action"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=cleanup_failure_root,
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=FakeTransport(
                [
                    *copy.deepcopy(launch_responses[:7]),
                    RuntimeError("active poll transport ambiguity"),
                    RuntimeError("termination response ambiguity"),
                    RuntimeError("cleanup inventory ambiguity"),
                ]
            ),
            clock=clock,
            sleeper=sleeper,
        )
    provisional_console = load_json(
        cleanup_failure_root / "PROVISIONAL_OWNER_CLEANUP_REQUIRES_CONSOLE.json"
    )
    assert provisional_console["private_instance_id"] == "instance-fixture-0001"
    assert provisional_console["second_launch_forbidden"] is True

    # Exhausting the bounded active window also enters provisional cleanup.
    capability[1] = tmp_path / "launch-capabilities/active-timeout.json"
    timeout_root = tmp_path / "provider-active-timeout"
    booting = {**copy.deepcopy(instance), "status": "booting"}
    with pytest.raises(provider.T09ProviderError, match="exact launched instance was closed"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=timeout_root,
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=FakeTransport(
                [
                    *copy.deepcopy(launch_responses[:7]),
                    *({"data": [copy.deepcopy(booting)]} for _ in range(provider.MAX_ENTRY_POLLS)),
                    RuntimeError("termination response ambiguity"),
                    {"data": []},
                    global_firewall,
                    {"data": []},
                ]
            ),
            clock=clock,
            sleeper=sleeper,
        )
    assert (
        load_json(timeout_root / "PROVISIONAL_OWNER_CLOSED.json")["provider_disposition"]
        == "absent"
    )

    original_seal = provider.seal_source_bundle
    entry_seal_failures = 0

    def fail_entry_seal(root: Path) -> dict[str, object]:
        nonlocal entry_seal_failures
        if root.name == "entry-source" and entry_seal_failures == 0:
            entry_seal_failures += 1
            raise provider.T09ProviderError("fixture entry seal failure")
        return original_seal(root)

    capability[1] = tmp_path / "launch-capabilities/entry-seal-failure.json"
    seal_failure_root = tmp_path / "provider-entry-seal-failure"
    monkeypatch.setattr(provider, "seal_source_bundle", fail_entry_seal)
    with pytest.raises(provider.T09ProviderError, match="exact launched instance was closed"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=seal_failure_root,
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=FakeTransport(
                [
                    *copy.deepcopy(launch_responses),
                    RuntimeError("termination response ambiguity"),
                    {"data": []},
                    global_firewall,
                    {"data": []},
                ]
            ),
            clock=clock,
            sleeper=sleeper,
        )
    assert (seal_failure_root / "PROVISIONAL_OWNER_CLOSED.json").is_file()
    monkeypatch.setattr(provider, "seal_source_bundle", original_seal)

    original_receipt = provider.create_entry_receipt

    def fail_entry_receipt(*_args: object, **_kwargs: object) -> Path:
        raise provider.T09ProviderError("fixture entry receipt failure")

    capability[1] = tmp_path / "launch-capabilities/entry-receipt-failure.json"
    receipt_failure_root = tmp_path / "provider-entry-receipt-failure"
    monkeypatch.setattr(provider, "create_entry_receipt", fail_entry_receipt)
    with pytest.raises(provider.T09ProviderError, match="exact launched instance was closed"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=receipt_failure_root,
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=FakeTransport(
                [
                    *copy.deepcopy(launch_responses),
                    RuntimeError("termination response ambiguity"),
                    {"data": []},
                    global_firewall,
                    {"data": []},
                ]
            ),
            clock=clock,
            sleeper=sleeper,
        )
    assert (receipt_failure_root / "PROVISIONAL_OWNER_CLOSED.json").is_file()
    monkeypatch.setattr(provider, "create_entry_receipt", original_receipt)

    original_write = provider.write_exclusive

    def fail_provisional_owner_write(
        path: Path,
        value: object,
        *,
        mode: int = 0o600,
    ) -> None:
        if path.name == "provisional-owned-state.json":
            raise OSError("fixture provisional owner write failure")
        original_write(path, value, mode=mode)

    capability[1] = tmp_path / "launch-capabilities/provisional-write-failure.json"
    write_failure_root = tmp_path / "provider-provisional-write-failure"
    monkeypatch.setattr(provider, "write_exclusive", fail_provisional_owner_write)
    with pytest.raises(provider.T09ProviderError, match="exact launched instance was closed"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=write_failure_root,
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=FakeTransport(
                [
                    *copy.deepcopy(launch_responses[:7]),
                    RuntimeError("termination response ambiguity"),
                    {"data": []},
                    global_firewall,
                    {"data": []},
                ]
            ),
            clock=clock,
            sleeper=sleeper,
        )
    assert (write_failure_root / "PROVISIONAL_OWNER_CLOSED.json").is_file()
    monkeypatch.setattr(provider, "write_exclusive", original_write)

    capability[1] = tmp_path / "launch-capabilities/duplicate-cleanup-failure.json"
    duplicate_root = tmp_path / "provider-duplicate-launch"
    duplicate_ids = [
        "instance-fixture-duplicate-1",
        "instance-fixture-duplicate-1",
        "instance-fixture-duplicate-2",
    ]
    duplicate_transport = FakeTransport(
        [
            *copy.deepcopy(launch_responses[:6]),
            {"data": {"instance_ids": duplicate_ids}},
            (503, {"error": "termination rejected"}),
            RuntimeError("fresh inventory ambiguity"),
        ]
    )
    with pytest.raises(provider.T09ProviderError, match="lost fresh inventory"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=duplicate_root,
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=duplicate_transport,
            clock=clock,
            sleeper=sleeper,
        )
    duplicate_incident = load_json(duplicate_root / "MULTI_INSTANCE_LAUNCH_INCIDENT.json")
    assert duplicate_incident["private_instance_ids_as_returned"] == duplicate_ids
    assert duplicate_incident["private_unique_instance_ids"] == list(dict.fromkeys(duplicate_ids))
    duplicate_console = load_json(duplicate_root / "MULTI_INSTANCE_CLEANUP_REQUIRES_CONSOLE.json")
    assert duplicate_console["private_unique_instance_ids"] == list(dict.fromkeys(duplicate_ids))
    termination_body = next(
        body
        for method, path, body in duplicate_transport.calls
        if method == "POST" and path.endswith("/terminate")
    )
    assert json.loads(termination_body or b"{}")["instance_ids"] == list(
        dict.fromkeys(duplicate_ids)
    )

    capability[1] = tmp_path / "launch-capabilities/multi-cleanup.json"
    multi_root = tmp_path / "provider-multi-launch"
    multi_ids = ["instance-fixture-incident-1", "instance-fixture-incident-2"]
    with pytest.raises(provider.T09ProviderError, match="every returned identity was closed"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=multi_root,
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=FakeTransport(
                [
                    *copy.deepcopy(launch_responses[:6]),
                    {"data": {"instance_ids": multi_ids}},
                    RuntimeError("termination response ambiguity"),
                    {"data": []},
                ]
            ),
            clock=clock,
            sleeper=sleeper,
        )
    incident = load_json(multi_root / "MULTI_INSTANCE_LAUNCH_INCIDENT.json")
    assert incident["second_launch_forbidden"] is True
    assert len(incident["unique_instance_identity_sha256s"]) == 2

    capability[1] = tmp_path / "launch-capabilities/success.json"
    private_root = tmp_path / "provider-private"
    entry_path = provider.launch_campaign(
        repository=ROOT,
        package_commit=package_commit,
        authorization_ledger=authorization,
        dotenv=dotenv,
        private_root=private_root,
        public_ipv4_file=public_ip_path,
        ssh_public_key_file=key_path,
        transport=FakeTransport(copy.deepcopy(launch_responses)),
        clock=clock,
        sleeper=sleeper,
    )
    consumed = load_json(capability[1])
    assert consumed["launch_capability_state"] == "consumed-cleanup-only-after-this-point"
    assert consumed["launch_capability_limit"] == 2
    no_second_launch = FakeTransport([])
    with pytest.raises(provider.T09ProviderError, match="already consumed"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=tmp_path / "different-caller-selected-root",
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=no_second_launch,
            clock=clock,
            sleeper=sleeper,
        )
    assert no_second_launch.calls == []
    monkeypatch.setattr(host.time, "time", lambda: now[0])
    validated = host.validate_dynamic_receipt(
        entry_path,
        expected_package_commit=package_commit,
        repository_root=ROOT,
        source_root=private_root / "entry-source",
    )
    assert validated["receipt_sha256"] == host.file_sha256(entry_path)
    assert validated["provider_projection_retained_private"] is True
    assert validated["raw_response_identity_retained"] is True
    assert validated["raw_provider_payload_retained"] is False
    assert "workspace-fixture" not in json.dumps(validated)

    owned_state_path = private_root / "owned-state.json"
    owned_state_original = owned_state_path.read_bytes()
    tampered_state = json.loads(owned_state_original)
    tampered_state["instance_id"] = "unrelated-instance"
    owned_state_path.write_text(json.dumps(tampered_state), encoding="utf-8")
    no_send = FakeTransport([])
    with pytest.raises(provider.T09ProviderError, match="not source-bound"):
        provider.closeout_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=private_root,
            transport=no_send,
            clock=clock,
            sleeper=sleeper,
        )
    assert no_send.responses == []
    owned_state_path.write_bytes(owned_state_original)

    failed_closeout_root = tmp_path / "provider-failed-closeout"
    copytree(private_root, failed_closeout_root)
    with pytest.raises(provider.ProviderOutcomeUnknown):
        provider.closeout_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=failed_closeout_root,
            transport=FakeTransport(
                [
                    RuntimeError("termination response ambiguity"),
                    RuntimeError("poll transport outage"),
                ]
            ),
            clock=clock,
            sleeper=sleeper,
        )
    manual = load_json(failed_closeout_root / "CLOSEOUT_REQUIRES_CONSOLE.json")
    assert manual["private_instance_id"] == "instance-fixture-0001"
    assert manual["private_operational_state_not_for_archive"] is True

    closeout_responses = [
        RuntimeError("termination response fixture ambiguity"),
        {"data": [{**copy.deepcopy(instance), "status": "active"}]},
        {"data": [{**copy.deepcopy(instance), "status": "terminating"}]},
        {"data": [{**copy.deepcopy(instance), "status": "terminated"}]},
        {"data": []},
        global_firewall,
        {"data": []},
    ]
    preempirical_source = tmp_path / "host-preempirical-source"
    preempirical_source.mkdir(mode=0o700)
    host.write_exclusive(
        preempirical_source / "pilot-state.json",
        {
            "plan_id": provider.PLAN_ID,
            "empirical_attempts_entered": [],
            "raw_attempts_complete": [],
            "attempts_completed": [],
        },
    )
    host.write_exclusive(
        preempirical_source / "host-cleanup.json",
        {
            "owned_container_residue": [],
            "global_secret_scan_passed": True,
            "remote_secret_removed": True,
        },
    )
    host.write_exclusive(
        preempirical_source / "preempirical-disposition.json",
        {
            "schema_version": "0.1.0",
            "plan_id": provider.PLAN_ID,
            "host_run_id": provider.HOST_RUN_ID,
            "package_commit": package_commit,
            "provider_entry_receipt_sha256": provider.file_sha256(entry_path),
            "pilot_state_sha256": host.file_sha256(preempirical_source / "pilot-state.json"),
            "host_cleanup_sha256": host.file_sha256(preempirical_source / "host-cleanup.json"),
            "empirical_attempts_entered": 0,
            "model_task_requests": 0,
            "task_browser_actions": 0,
            "replacement_image_build_count": 0,
            "credentials_removed": True,
            "owned_containers_absent": True,
            "replacement_launch_evidence_only": True,
        },
    )
    preempirical_files = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": host.file_sha256(path),
        }
        for path in sorted(preempirical_source.iterdir())
    ]
    host.write_exclusive(
        preempirical_source / "source-manifest.json",
        {
            "schema_version": "0.1.0",
            "plan_id": provider.PLAN_ID,
            "host_run_id": provider.HOST_RUN_ID,
            "files": preempirical_files,
            "total_bytes": sum(int(item["bytes"]) for item in preempirical_files),
        },
    )
    closeout_path = provider.closeout_campaign(
        repository=ROOT,
        package_commit=package_commit,
        authorization_ledger=authorization,
        dotenv=dotenv,
        private_root=private_root,
        transport=FakeTransport(closeout_responses),
        preempirical_receipt=preempirical_source / "preempirical-disposition.json",
        preempirical_source_root=preempirical_source,
        clock=clock,
        sleeper=sleeper,
    )
    monkeypatch.setattr(host.time, "time", lambda: now[0])
    closeout = host.validate_provider_closeout_receipt(
        closeout_path,
        expected_lambda_started_at_epoch=float(validated["lambda_started_at_epoch"]),
        expected_owned_instance_identity_sha256=str(validated["owned_instance_identity_sha256"]),
        expected_entry_receipt_sha256=host.file_sha256(entry_path),
        expected_package_commit=package_commit,
        repository_root=ROOT,
        source_root=private_root / "closeout-source",
        entry_receipt_path=entry_path,
        entry_source_root=private_root / "entry-source",
    )
    assert closeout["receipt_sha256"] == host.file_sha256(closeout_path)
    assert closeout["raw_provider_payload_retained"] is False
    termination_polls = [
        event
        for event in provider._journal_events(private_root / "closeout-source")
        if event.get("operation") == "termination-instances"
        and event.get("event") == "response-complete"
    ]
    assert len(termination_polls) == 4
    assert closeout["zero_t09_instances"] is True
    closeout_documents = provider._response_documents(private_root / "closeout-source")
    last_inventory = closeout_documents["termination-instances"][-1][1]
    assert last_inventory == {"data": []}
    eligibility = load_json(private_root / "replacement-launch-eligibility.json")
    assert eligibility["host_preempirical_receipt_sha256"] == provider.file_sha256(
        private_root / "preempirical-source/preempirical-disposition.json"
    )

    tampered_prior = tmp_path / "provider-private-tampered-zero-use"
    copytree(private_root, tampered_prior)
    tampered_state = tampered_prior / "preempirical-source/pilot-state.json"
    tampered_state.write_text('{"empirical_attempts_entered":["forged"]}\n', encoding="utf-8")
    capability[2] = tmp_path / "launch-capabilities/slot-2-tampered.json"
    tampered_transport = FakeTransport([])
    with pytest.raises(provider.T09ProviderError, match="pre-empirical source manifest drifted"):
        provider.launch_campaign(
            repository=ROOT,
            package_commit=package_commit,
            authorization_ledger=authorization,
            dotenv=dotenv,
            private_root=tmp_path / "provider-slot-2-tampered",
            public_ipv4_file=public_ip_path,
            ssh_public_key_file=key_path,
            transport=tampered_transport,
            launch_slot=2,
            prior_private_root=tampered_prior,
            clock=clock,
            sleeper=sleeper,
        )
    assert tampered_transport.calls == []

    capability[2] = tmp_path / "launch-capabilities/slot-2-success.json"
    slot_2_instance = {
        **copy.deepcopy(instance),
        "id": "instance-fixture-0002",
        "ip": "198.51.100.10",
    }
    slot_2_root = tmp_path / "provider-private-slot-2"
    slot_2_entry = provider.launch_campaign(
        repository=ROOT,
        package_commit=package_commit,
        authorization_ledger=authorization,
        dotenv=dotenv,
        private_root=slot_2_root,
        public_ipv4_file=public_ip_path,
        ssh_public_key_file=key_path,
        transport=FakeTransport(
            [
                *copy.deepcopy(launch_responses[:6]),
                {"data": {"instance_ids": ["instance-fixture-0002"]}},
                {"data": [slot_2_instance]},
            ]
        ),
        launch_slot=2,
        prior_private_root=private_root,
        clock=clock,
        sleeper=sleeper,
    )
    assert load_json(slot_2_entry)["launch_slot"] == 2
    assert load_json(slot_2_entry)["prior_retry3_lambda_cost_usd"] == pytest.approx(
        eligibility["prior_lambda_cost_usd"]
    )
    provider.closeout_campaign(
        repository=ROOT,
        package_commit=package_commit,
        authorization_ledger=authorization,
        dotenv=dotenv,
        private_root=slot_2_root,
        transport=FakeTransport(
            [
                RuntimeError("termination response fixture ambiguity"),
                {"data": []},
                global_firewall,
                {"data": []},
            ]
        ),
        clock=clock,
        sleeper=sleeper,
    )

    forged = dict(load_json(entry_path))
    forged["launch_count"] = 2
    forged_path = tmp_path / "forged-entry.json"
    forged_path.write_text(json.dumps(forged), encoding="utf-8")
    with pytest.raises(host.T09HostError, match="not source-bound"):
        host.validate_dynamic_receipt(
            forged_path,
            expected_package_commit=package_commit,
            repository_root=ROOT,
            source_root=private_root / "entry-source",
        )

    late_root = tmp_path / "late-closeout-source"
    copytree(private_root / "closeout-source", late_root)
    (late_root / "source-manifest.json").unlink()
    (late_root / "closeout-receipt.json").unlink()
    journal_lines = (late_root / "request-journal.jsonl").read_text().splitlines()
    events = [json.loads(line) for line in journal_lines]
    late_base = float(validated["lambda_started_at_epoch"]) + 14_000
    for index, event in enumerate(events):
        event["send_started_at_epoch"] = late_base + index
        if "response_received_at_epoch" in event:
            event["response_received_at_epoch"] = late_base + index + 0.5
    (late_root / "request-journal.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    provider.seal_source_bundle(late_root)
    late_receipt = provider.create_closeout_receipt(
        late_root,
        entry_receipt_path=entry_path,
        entry_source_root=private_root / "entry-source",
        package_commit=package_commit,
        plan_sha256=provider.file_sha256(plan_path),
        lifecycle=provider.load_campaign_lifecycle(ROOT),
    )
    with pytest.raises(host.T09HostError, match="not source-bound"):
        host.validate_provider_closeout_receipt(
            late_receipt,
            expected_lambda_started_at_epoch=float(validated["lambda_started_at_epoch"]),
            expected_owned_instance_identity_sha256=str(
                validated["owned_instance_identity_sha256"]
            ),
            expected_entry_receipt_sha256=host.file_sha256(entry_path),
            expected_package_commit=package_commit,
            repository_root=ROOT,
            source_root=late_root,
            entry_receipt_path=entry_path,
            entry_source_root=private_root / "entry-source",
        )


def test_closeout_rejects_termination_after_campaign_cutoff() -> None:
    lifecycle = provider.CampaignLifecycle(
        observer_limits=ObserverLifecycleLimits.t09_pragmatic_v5(),
        max_instances=1,
        max_launches=2,
        persistent_filesystems=0,
    )
    assert lifecycle.termination_due(
        started_at_epoch=100.0,
        now_epoch=13_600.0,
    )
    observer = ObserverLifecycleLimits.t09_pragmatic_v5()
    assert (
        lifecycle.wall_seconds,
        lifecycle.cleanup_reserve_seconds,
        lifecycle.termination_cutoff_seconds,
    ) == (
        observer.campaign_provider_wall_seconds,
        observer.cleanup_reserve_seconds,
        observer.normal_termination_cutoff_seconds,
    )


def test_provider_send_ambiguity_is_durably_unknown_and_never_retried(tmp_path: Path) -> None:
    class UnknownTransport:
        calls = 0

        def send(
            self,
            method: str,
            path: str,
            *,
            body: bytes | None,
            credential: bytearray,
        ) -> provider.ProviderResponse:
            del method, path, body, credential
            self.calls += 1
            raise RuntimeError("fixture transport ambiguity")

    root = tmp_path / "provider-source"
    root.mkdir()
    transport = UnknownTransport()
    recorder = provider.RequestRecorder(
        root,
        transport,
        bytearray(b"lambda-fixture-credential"),
        lambda: 100.0,
    )
    with pytest.raises(provider.ProviderOutcomeUnknown, match="outcome is unknown"):
        recorder.request(
            "launch",
            "POST",
            "/api/v1/instance-operations/launch",
            body=provider._launch_body(),
        )

    events = [
        json.loads(line) for line in (root / "request-journal.jsonl").read_text().splitlines()
    ]
    assert transport.calls == 1
    assert [event["event"] for event in events] == ["send-started", "response-unknown"]
    assert provider._response_documents(root) == {}

    class MalformedSuccessTransport:
        calls = 0

        def send(
            self,
            method: str,
            path: str,
            *,
            body: bytes | None,
            credential: bytearray,
        ) -> provider.ProviderResponse:
            del method, path, body, credential
            self.calls += 1
            return provider.ProviderResponse(200, "application/json", b"not-json", 101.0)

    malformed_root = tmp_path / "provider-malformed-success"
    malformed_root.mkdir()
    malformed = MalformedSuccessTransport()
    malformed_recorder = provider.RequestRecorder(
        malformed_root,
        malformed,
        bytearray(b"lambda-fixture-credential"),
        lambda: 100.0,
    )
    with pytest.raises(provider.ProviderOutcomeUnknown, match="outcome is unknown"):
        malformed_recorder.request(
            "launch",
            "POST",
            "/api/v1/instance-operations/launch",
            body=provider._launch_body(),
        )
    malformed_events = [
        json.loads(line)
        for line in (malformed_root / "request-journal.jsonl").read_text().splitlines()
    ]
    assert malformed.calls == 1
    assert [event["event"] for event in malformed_events] == [
        "send-started",
        "response-unknown",
    ]
    assert malformed_events[-1]["classification"] == "untrusted-response-semantics"
    assert "not-json" not in json.dumps(malformed_events)
    assert provider._response_documents(malformed_root) == {}


def test_removed_provider_receipt_schemas_cannot_be_mistaken_for_execution_contracts() -> None:
    assert not (ROOT / "schemas/t09-sira-pilot-dynamic-preflight.schema.json").exists()
    assert not (ROOT / "schemas/t09-sira-pilot-provider-closeout.schema.json").exists()


def test_t09_provider_is_a_narrow_adapter_over_the_retained_t07_pragmatic_path() -> None:
    historical_launch = load_json(
        ROOT / "artifacts/t07/pragmatic/RUN-T07-PRAGMATIC-HOST-0001/launch-request.json"
    )
    current_launch = provider._launch_body()
    assert set(current_launch) == set(historical_launch)
    for key in (
        "region_name",
        "instance_type_name",
        "ssh_key_names",
        "file_system_names",
        "file_system_mounts",
        "image",
    ):
        assert current_launch[key] == historical_launch[key]
    assert current_launch["name"] == current_launch["hostname"] == provider.INSTANCE_NAME

    calls: list[tuple[object, dict[str, object]]] = []

    class ExistingObserverFixture:
        def send(self, request: object, **kwargs: object) -> SimpleNamespace:
            calls.append((request, kwargs))
            return SimpleNamespace(
                status=200,
                content_type="application/json",
                body=b'{"data":[]}',
            )

    transport = provider.LambdaTransport()
    transport._observer = ExistingObserverFixture()  # type: ignore[assignment]
    response = transport.send(
        "GET",
        "/api/v1/instances",
        body=None,
        credential=bytearray(b"lambda-fixture-credential"),
    )
    assert response.status == 200
    assert len(calls) == 1
    request = cast(ObserverRequest, calls[0][0])
    assert request.operation.value == "list_instances"


def test_provider_projection_allowlists_selected_operational_fields() -> None:
    projected_types = json.loads(
        provider._project_provider_response(
            "instance-types",
            json.dumps(
                {
                    "data": {
                        provider.INSTANCE_TYPE: {
                            "instance_type": {
                                "name": provider.INSTANCE_TYPE,
                                "price_cents_per_hour": 129,
                                "provider_account_id": "must-not-survive",
                            },
                            "regions_with_capacity_available": [
                                {"name": provider.REGION, "private_cidr": "must-not-survive"}
                            ],
                            "workspace_id": "must-not-survive",
                        },
                        "unselected-shape": {"account_id": "must-not-survive"},
                    }
                }
            ).encode(),
        )
    )
    serialized = json.dumps(projected_types)
    assert provider.INSTANCE_TYPE in serialized
    assert "must-not-survive" not in serialized
    with pytest.raises(provider.T09ProviderError, match="unsupported provider projection"):
        provider._project_provider_response("invented-operation", b'{"data":{}}')


def test_campaign_lifecycle_uses_actual_elapsed_time_and_preserves_cleanup_reserve() -> None:
    campaign = CampaignLifecycleLimits(
        campaign_provider_wall_seconds=14_400,
        normal_cleanup_reserve_seconds=900,
        provider_termination_cutoff_seconds=13_500,
        post_condition_evaluator_evidence_seconds=600,
        termination_dispatch_margin_seconds=60,
        max_lambda_instances=1,
        max_launch_count=2,
        persistent_filesystems=0,
    )
    assert campaign.elapsed_seconds(billable_started_at=100.0, now=700.0) == 600.0
    assert (
        campaign.admit_attempt(
            billable_started_at=100.0,
            now=10_000.0,
            attempt_hard_wall_seconds=3_600,
        )
        is True
    )
    assert (
        campaign.admit_attempt(
            billable_started_at=100.0,
            now=10_000.1,
            attempt_hard_wall_seconds=3_600,
        )
        is False
    )
    assert campaign.termination_due(billable_started_at=100.0, now=13_600.0) is True


def test_host_campaign_admission_counts_setup_and_attempt_actual_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    now = time.time()
    state = tmp_path / "pilot-v5/pilot-state.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps(
            {
                "pilot_started_at_epoch": now,
                "lambda_started_at_epoch": now,
            }
        ),
        encoding="utf-8",
    )
    assert host.provider_seconds_remaining(tmp_path, reserve_seconds=900) == pytest.approx(
        13_500,
        abs=1,
    )
    assert host.scientific_seconds_remaining(tmp_path) == pytest.approx(14_400, abs=1)
    # Downstream finalization and evidence packaging cannot shorten condition
    # execution.  Admission requires exactly one 3,600-second condition wall
    # plus the 900-second billable-resource closeout reserve.
    monkeypatch.setattr(host.time, "time", lambda: now + 9_900)
    assert host.admit_next_attempt(tmp_path) == pytest.approx(3_600)
    monkeypatch.setattr(host.time, "time", lambda: now + 9_901)
    with pytest.raises(host.T09HostError, match="next attempt hard wall"):
        host.admit_next_attempt(tmp_path)
    monkeypatch.setattr(host.time, "time", lambda: now + 13_500)
    assert host.provider_seconds_remaining(tmp_path, reserve_seconds=900) == 0
    assert host.provider_termination_due(tmp_path) is True


def test_condition_keeps_full_3600_seconds_and_separates_evidence_handoff() -> None:
    host = _load_host_runner()
    assert host.MAX_CONDITION_WALL_SECONDS == 3_600
    assert host.ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS == 600
    assert host.PROVIDER_TERMINATION_HANDOFF_SECONDS == 60
    source = inspect.getsource(host.run_attached_with_caps)
    assert "elapsed > MAX_CONDITION_WALL_SECONDS" in source
    assert "MAX_CONDITION_WALL_SECONDS - ATTEMPT_EVIDENCE_EXPORT_RESERVE_SECONDS" not in source


def test_raw_attempt_streams_before_cutoff_without_aggregate_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    replacement_image_id = "sha256:" + "e" * 64
    now = time.time()
    monkeypatch.setattr(host.time, "time", lambda: now)
    manifest = next(item for item in _rendered_v5_manifests() if item["run_id"] == ATTEMPT_ORDER[0])
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / manifest["permitted_condition_owned"]["output_root"]
    raw_root = artifact_root / manifest["permitted_condition_owned"]["raw_output_root"]
    copytree(ROOT / "tests/fixtures/t09/finalizer-raw-shape", raw_root)
    pilot_root = artifact_root / "pilot-v5"
    pilot_root.mkdir(exist_ok=True)
    initialize_pilot_state(
        pilot_root / "pilot-state.json",
        execution_contract_sha256="a" * 64,
        pilot_started_at_epoch=now - 100,
        lambda_started_at_epoch=now - 100,
    )
    mark_empirical_entry(
        pilot_root / "pilot-state.json",
        execution_contract_sha256="a" * 64,
        run_id=ATTEMPT_ORDER[0],
    )
    provider_entry = tmp_path / "provider-entry.json"
    provider_entry.write_text(
        json.dumps(
            {
                "owned_instance_identity_sha256": "b" * 64,
                "lambda_started_at_epoch": now - 100,
            }
        ),
        encoding="utf-8",
    )
    (pilot_root / "provider-entry.json").write_text(
        json.dumps(
            {
                "receipt_sha256": host.file_sha256(provider_entry),
                "owned_instance_identity_sha256": "b" * 64,
                "lambda_started_at_epoch": now - 100,
            }
        ),
        encoding="utf-8",
    )
    local_qualification = pilot_root / "local-finalizer-qualification.json"
    local_qualification.write_text(
        json.dumps(
            {
                "qualification_id": "QUAL-T09-PILOT-V5-LOCAL-FINALIZER-0001",
                "package_commit": "a" * 40,
            }
        ),
        encoding="utf-8",
    )
    frozen_document = {
        "manifest_id": "RUN-MANIFEST-EXP0001-PILOT-V5-0003",
        "plan_id": "PLAN-EXP0001-PILOT-V5",
        "clean_package_commit": "a" * 40,
        "replacement_image_id": replacement_image_id,
        "local_finalizer_qualification_sha256": host.file_sha256(local_qualification),
    }
    frozen_path = pilot_root / "frozen-run-manifest.json"
    frozen_path.write_text(json.dumps(frozen_document), encoding="utf-8")
    frozen_sha256 = host.file_sha256(frozen_path)
    for relative in (
        "final-image-file-hashes/receipt.json",
        "qualified-real-evidence-regression/receipt.json",
        "replacement-image-qualification/build-context-exclusions.json",
    ):
        path = pilot_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fixture": relative}), encoding="utf-8")
    monkeypatch.setattr(
        host,
        "load_frozen_run_manifest",
        lambda *_args, **_kwargs: (frozen_document, frozen_sha256),
    )
    monkeypatch.setattr(
        host,
        "manifest_for_run",
        lambda _document, run_id: (
            manifest if run_id == ATTEMPT_ORDER[0] else (_ for _ in ()).throw(KeyError(run_id))
        ),
    )
    cleanup_path = raw_root / "host-cleanup-receipt.json"
    cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
    cleanup["run_id"] = ATTEMPT_ORDER[0]
    cleanup_path.write_text(json.dumps(cleanup), encoding="utf-8")
    for name, value in {
        "container-command.json": {"run_id": ATTEMPT_ORDER[0]},
        "container-state.json": {"running": False},
        "gpu-accounting.json": {"run_id": ATTEMPT_ORDER[0]},
    }.items():
        (raw_root / name).write_text(json.dumps(value), encoding="utf-8")
    (raw_root / "condition.stdout").write_text("", encoding="utf-8")
    (raw_root / "condition.stderr").write_text("", encoding="utf-8")
    (raw_root / "attempt-wall.json").write_text(
        json.dumps({"evidence_handoff_deadline_epoch": now + 60}),
        encoding="utf-8",
    )
    (raw_root / "evaluator-overlay-binding.json").write_text(
        json.dumps(
            {
                "run_id": ATTEMPT_ORDER[0],
                "frozen_run_manifest_sha256": frozen_sha256,
                "condition_mount_policy": "read-only",
            }
        ),
        encoding="utf-8",
    )
    (raw_root / "runtime-reconstruction-binding.json").write_text(
        json.dumps(
            {
                "run_id": ATTEMPT_ORDER[0],
                "runtime_cleanup_present": False,
                "runtime_cleanup_sha256": None,
                "host_cleanup_receipt_sha256": host.file_sha256(cleanup_path),
                "container_state_sha256": host.file_sha256(raw_root / "container-state.json"),
                "host_teardown_is_source_grounded_fallback": True,
            }
        ),
        encoding="utf-8",
    )
    host.seal_raw_attempt(
        artifact_root=artifact_root,
        attempt_root=attempt_root,
        raw_root=raw_root,
        manifest=manifest,
        package_commit="a" * 40,
        frozen_run_manifest_sha256=frozen_sha256,
        execution_contract_sha256="a" * 64,
    )
    with pytest.raises(host.T09HostError, match="off-host verification acknowledgement"):
        host.require_attempt_export_acknowledgement(
            artifact_root,
            run_id=ATTEMPT_ORDER[0],
            package_commit="a" * 40,
        )
    arguments = SimpleNamespace(
        repository=ROOT,
        artifact_root=artifact_root,
        run_id=ATTEMPT_ORDER[0],
        package_commit="a" * 40,
        secret_file=tmp_path / "fixture-openai-secret",
    )
    arguments.secret_file.write_bytes(b"fixture-openai-secret-value")
    arguments.secret_file.chmod(0o600)
    exports = pilot_root / "attempt-exports"
    exports.mkdir()
    archive = exports / f"{ATTEMPT_ORDER[0]}.tar.gz"
    archive.write_bytes(b"interrupted-archive-prefix")

    class InterruptedDestination(io.BytesIO):
        def write(self, value: bytes) -> int:
            super().write(value[: max(1, len(value) // 2)])
            raise OSError("operator transfer interrupted")

    interrupted = InterruptedDestination()
    with pytest.raises(OSError, match="operator transfer interrupted"):
        host.export_attempt(arguments, interrupted)
    quarantined = list(exports.glob("*.tar.gz.partial"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == b"interrupted-archive-prefix"
    complete_bytes = archive.read_bytes()
    complete_sha256 = host.file_sha256(archive)

    class ShortWriteDestination(io.BytesIO):
        def write(self, value: bytes) -> int:
            return super().write(value[: max(1, len(value) // 2)])

    destination = ShortWriteDestination()
    result = host.export_attempt(arguments, destination)
    assert result["run_id"] == ATTEMPT_ORDER[0]
    assert result["bytes"] == len(destination.getvalue())
    assert result["bytes"] > 0
    assert destination.getvalue() == complete_bytes
    assert result["sha256"] == complete_sha256
    assert (attempt_root / "attempt-export-manifest.json").is_file()
    inbound = tmp_path / "inbound"
    inbound.mkdir()
    inbound_archive = inbound / f"{ATTEMPT_ORDER[0]}.tar.gz"
    inbound_archive.write_bytes(destination.getvalue())
    host.verify_attempt_export(
        SimpleNamespace(
            inbound_root=inbound,
            attempt_export=inbound_archive,
            run_id=ATTEMPT_ORDER[0],
            package_commit="a" * 40,
            provider_entry_receipt=provider_entry,
            restore_artifact_root=None,
        )
    )
    verification = inbound / f"{ATTEMPT_ORDER[0]}-export-verification.json"
    assert verification.is_file()
    attempt_binding = SimpleNamespace(
        output_root=manifest["permitted_condition_owned"]["output_root"],
        raw_output_root=manifest["permitted_condition_owned"]["raw_output_root"],
    )
    restored_contract = SimpleNamespace(
        sha256="a" * 64,
        attempt=lambda run_id: (
            attempt_binding
            if run_id == ATTEMPT_ORDER[0]
            else (_ for _ in ()).throw(KeyError(run_id))
        ),
    )
    monkeypatch.setattr(host, "verify_package", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        host,
        "load_execution_contract",
        lambda *_args, **_kwargs: restored_contract,
    )
    restored_root = tmp_path / "restored-offhost"
    host.restore_verified_attempt_export(
        repository=ROOT,
        package_commit="a" * 40,
        current_commit=None,
        archive=inbound_archive,
        verification_path=verification,
        restoration_root=restored_root,
        run_id=ATTEMPT_ORDER[0],
    )
    restored_attempt = restored_root / attempt_binding.output_root
    assert (restored_attempt / "raw-attempt-manifest.json").is_file()
    assert (restored_attempt / "offhost-restore-complete.json").is_file()
    assert (
        restored_root / "pilot-v5/attempt-exports" / f"{ATTEMPT_ORDER[0]}.tar.gz"
    ).read_bytes() == inbound_archive.read_bytes()
    assert json.loads((restored_root / "pilot-v5/pilot-state.json").read_text(encoding="utf-8"))[
        "raw_attempts_complete"
    ] == [ATTEMPT_ORDER[0]]
    assert (
        stat.S_IMODE((restored_attempt / "offhost-restore-complete.json").stat().st_mode) == 0o600
    )
    uploaded_ack = tmp_path / "uploaded-export-ack.json"
    uploaded_ack.write_bytes(verification.read_bytes())
    host.acknowledge_attempt_export(
        SimpleNamespace(
            artifact_root=artifact_root,
            acknowledgement_file=uploaded_ack,
            run_id=ATTEMPT_ORDER[0],
            package_commit="a" * 40,
        )
    )
    host.require_prior_export_acknowledgements(
        artifact_root,
        next_attempt_index=1,
        package_commit="a" * 40,
    )
    host.require_attempt_export_acknowledgement(
        artifact_root,
        run_id=ATTEMPT_ORDER[0],
        package_commit="a" * 40,
    )
    acknowledgement = host._received_export_ack_path(artifact_root, ATTEMPT_ORDER[0])
    assert acknowledgement.is_file()
    acknowledgement.unlink()
    with pytest.raises(host.T09HostError):
        host.require_prior_export_acknowledgements(
            artifact_root,
            next_attempt_index=1,
            package_commit="a" * 40,
        )

    # Logical size, including sparse files, is the hard disk accounting
    # surface.  An already-complete archive must not bypass that guard.
    sparse = pilot_root / "sparse-headroom-fixture.bin"
    with sparse.open("wb") as handle:
        handle.truncate(host.MAX_PILOT_DISK_BYTES)
    bytes_before_refusal = host.tree_bytes(artifact_root)
    with pytest.raises(host.T09HostError, match="aggregate pilot disk headroom"):
        host.export_attempt(arguments, io.BytesIO())
    assert host.tree_bytes(artifact_root) == bytes_before_refusal
    assert archive.read_bytes() == complete_bytes
    sparse.unlink()

    # Only one quarantined source prefix may exist.  A subsequently corrupted
    # active archive fails without a second rename or replacement write.
    archive.write_bytes(b"second-corrupt-archive-prefix")
    bytes_before_repeat = host.tree_bytes(artifact_root)
    with pytest.raises(host.T09HostError, match="one bounded partial archive"):
        host.export_attempt(arguments, io.BytesIO())
    assert host.tree_bytes(artifact_root) == bytes_before_repeat
    assert archive.read_bytes() == b"second-corrupt-archive-prefix"
    assert list(exports.glob("*.tar.gz.partial")) == quarantined


def test_host_secret_cleanup_finds_cross_chunk_match_and_destroys_exact_file(
    tmp_path: Path,
) -> None:
    host = _load_host_runner()
    credential_bytes = b"fixture-secret-value-with-cross-chunk-boundary"
    evidence = tmp_path / "evidence.bin"
    evidence.write_bytes(b"x" * (1_048_576 - 5) + credential_bytes + b"tail")
    assert host.secret_hits(tmp_path, credential_bytes) == ["evidence.bin"]
    secret_path = tmp_path / "secret"
    secret_path.write_bytes(credential_bytes)
    secret_path.chmod(0o600)
    assert host.destroy_secret(secret_path) is True
    assert not secret_path.exists()


def test_archive_privacy_scan_rejects_private_network_and_unredacted_account_fields(
    tmp_path: Path,
) -> None:
    host = _load_host_runner()
    (tmp_path / "unsafe.json").write_text(
        json.dumps(
            {
                "network": "10.4.2.9/24",
                "provider_account_identifier": "unrelated-account",
            }
        ),
        encoding="utf-8",
    )
    hits = host.privacy_violations(tmp_path)
    assert "unsafe.json:private-network" in hits
    assert "unsafe.json:sensitive-json-field" in hits
    (tmp_path / "unsafe.json").write_text(
        json.dumps(
            {
                "provider_account_identifier": {
                    "redacted": True,
                    "reason": "structural-sensitive-field",
                }
            }
        ),
        encoding="utf-8",
    )
    assert host.privacy_violations(tmp_path) == []


def test_entered_partial_attempt_is_deterministically_reconstructable_without_retry(
    tmp_path: Path,
) -> None:
    finalizer = _load_attempt_finalizer()
    missing_root = tmp_path / "missing-session"
    copytree(ROOT / "tests/fixtures/t09/finalizer-raw-shape", missing_root)
    session = next((missing_root / "sira-output").glob("*.json"))
    session.unlink()
    missing = finalizer.reconstruct_semantic_projection(
        raw_root=missing_root,
        evaluator_root=EVALUATOR_ROOT,
        dataset_path=DATASET_FIXTURE,
        task_index=0,
        task_id="7dcbbbdc7f1120cd",
        condition="SIRA-REACTIVE",
        evaluator_fixture_subset=True,
    )
    assert missing["evaluator_valid"] is False
    assert missing["score"] is None
    assert missing["session_sha256"] is None
    assert missing["session_sha256s"] == []
    assert missing["raw_consistency"]["one_session"] is False

    duplicate_root = tmp_path / "duplicate-session"
    copytree(ROOT / "tests/fixtures/t09/finalizer-raw-shape", duplicate_root)
    retained_session = next((duplicate_root / "sira-output").glob("*.json"))
    duplicate = retained_session.with_name("duplicate.json")
    duplicate.write_bytes(retained_session.read_bytes())
    duplicated = finalizer.reconstruct_semantic_projection(
        raw_root=duplicate_root,
        evaluator_root=EVALUATOR_ROOT,
        dataset_path=DATASET_FIXTURE,
        task_index=0,
        task_id="7dcbbbdc7f1120cd",
        condition="SIRA-REACTIVE",
        evaluator_fixture_subset=True,
    )
    assert duplicated["evaluator_valid"] is False
    assert duplicated["score"] is None
    assert len(duplicated["session_sha256s"]) == 2
    assert duplicated["raw_consistency"]["one_session"] is False


@pytest.mark.parametrize(
    "relative",
    [
        "src/giclab/harness/sira_gate_a.py",
        "src/giclab/harness/safety.py",
        "src/giclab/harness/t09_sira_pilot.py",
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py",
        "containers/sira-smoke/pragmatic/t09_preflight.py",
        "containers/sira-smoke/pragmatic/t09_freeze_commands.py",
        "containers/sira-smoke/pragmatic/materialize_openai_secret.py",
    ],
)
def test_selected_t09_control_code_imports_no_provider_cloud_or_browser_client(
    relative: str,
) -> None:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    forbidden = {"boto3", "openai", "playwright", "browsergym", "requests", "httpx"}
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert imports.isdisjoint(forbidden)
