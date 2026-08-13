from __future__ import annotations

import ast
import copy
import importlib.util
import json
import time
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

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
    T09BudgetExceeded,
    diff_pair_manifests,
    evaluate_retained_session,
    file_sha256,
    first_pair_decision,
    initialize_pilot_state,
    load_execution_contract,
    mark_attempt_completed,
    mark_empirical_entry,
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
    contract = load_execution_contract(
        EXECUTION_CONTRACT,
        expected_sha256=file_sha256(EXECUTION_CONTRACT),
    )
    manifests = [
        render_command_manifest(
            contract,
            attempt,
            execution_contract_runtime_path="/opt/giclab-contracts/execution.json",
            runtime_adaptation_path="/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
            runtime_adaptation_sha256="a" * 64,
            pilot_library_sha256="b" * 64,
            aggregate_ledger_path="/opt/giclab-artifacts/pilot-v3/aggregate-budget.json",
            pilot_state_path="/opt/giclab-artifacts/pilot-v3/pilot-state.json",
        )
        for attempt in contract.attempts
    ]
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
    assert (
        "insufficient_campaign_time_for_next_attempt_and_cleanup"
        in no_time_decision["reasons"]
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
    mark_attempt_completed(
        path,
        execution_contract_sha256=digest,
        run_id=ATTEMPT_ORDER[0],
    )
    mark_empirical_entry(
        path,
        execution_contract_sha256=digest,
        run_id=ATTEMPT_ORDER[1],
    )
    mark_attempt_completed(
        path,
        execution_contract_sha256=digest,
        run_id=ATTEMPT_ORDER[1],
    )
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
    assert document["terminal_state"] == "ready-for-t09-pilot-authorization"
    assert (
        document["execution_eligibility"]
        == "ready-after-current-turn-overlay-and-dynamic-preflight"
    )
    assert document["material_blockers"] == []
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
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py",
        "containers/sira-smoke/pragmatic/t09_preflight.py",
        "containers/sira-smoke/pragmatic/t09_freeze_commands.py",
        "containers/sira-smoke/pragmatic/t09_secret_preflight.py",
    }
    assert {item["path"] for item in files} == expected
    for item in files:
        assert file_sha256(ROOT / item["path"]) == item["sha256"]


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


def test_pragmatic_provider_entry_and_closeout_receipts_are_exact_and_source_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    now = 2_000_000_000.0
    monkeypatch.setattr(host.time, "time", lambda: now)
    entry_path = tmp_path / "provider-entry.json"
    entry = {
        "schema_version": "0.1.0",
        "receipt_type": "t09-pragmatic-provider-entry",
        "plan_id": "PLAN-EXP0001-PILOT-V3",
        "host_run_id": "RUN-T09-PILOT-HOST-0001",
        "package_commit": "a" * 40,
        "captured_at_epoch": now - 10,
        "lambda_started_at_epoch": now - 20,
        "owned_instance_identity_sha256": "b" * 64,
        "source_bundle_sha256": "c" * 64,
        "source_bundle_bytes": 4096,
        "source_observer": "t07-pragmatic-lambda-api-receipts-v1",
        "zero_prior_nonterminal_instances": True,
        "launch_count": 1,
        "max_instances": 1,
        "instance_type": "gpu_1x_a10",
        "region": "us-east-1",
        "persistent_filesystems": 0,
        "hourly_price_usd": 1.29,
        "billable_clock_source": "provider-launch-response-received",
        "raw_source_retained_private": True,
        "structural_redaction_passed": True,
    }
    entry_path.write_text(json.dumps(entry), encoding="utf-8")
    validated = host.validate_dynamic_receipt(
        entry_path,
        expected_package_commit="a" * 40,
    )
    assert validated["receipt_sha256"] == host.file_sha256(entry_path)
    drifted = dict(entry)
    drifted["launch_count"] = 2
    entry_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(host.T09HostError, match="entry receipt drifted"):
        host.validate_dynamic_receipt(entry_path, expected_package_commit="a" * 40)

    entry_path.write_text(json.dumps(entry), encoding="utf-8")
    entry_sha = host.file_sha256(entry_path)
    closeout_path = tmp_path / "provider-closeout.json"
    closeout = {
        "schema_version": "0.1.0",
        "receipt_type": "t09-pragmatic-provider-closeout",
        "plan_id": "PLAN-EXP0001-PILOT-V3",
        "host_run_id": "RUN-T09-PILOT-HOST-0001",
        "package_commit": "a" * 40,
        "captured_at_epoch": now,
        "lambda_started_at_epoch": now - 20,
        "termination_started_at_epoch": now - 8,
        "terminal_observed_at_epoch": now - 4,
        "zero_instance_observed_at_epoch": now - 2,
        "owned_instance_identity_sha256": "b" * 64,
        "termination_target_identity_sha256": "b" * 64,
        "entry_receipt_sha256": entry_sha,
        "source_bundle_sha256": "d" * 64,
        "source_bundle_bytes": 8192,
        "source_observer": "t07-pragmatic-lambda-api-receipts-v1",
        "termination_request_count": 1,
        "terminal_or_absent": True,
        "zero_t09_instances": True,
        "security_restored": True,
        "raw_source_retained_private": True,
        "structural_redaction_passed": True,
        "campaign_wall_exception": "none",
    }
    closeout_path.write_text(json.dumps(closeout), encoding="utf-8")
    assert host.validate_provider_closeout_receipt(
        closeout_path,
        expected_lambda_started_at_epoch=now - 20,
        expected_owned_instance_identity_sha256="b" * 64,
        expected_entry_receipt_sha256=entry_sha,
        expected_package_commit="a" * 40,
    )["receipt_sha256"] == host.file_sha256(closeout_path)


def test_removed_provider_receipt_schemas_cannot_be_mistaken_for_execution_contracts() -> None:
    assert not (ROOT / "schemas/t09-sira-pilot-dynamic-preflight.schema.json").exists()
    assert not (ROOT / "schemas/t09-sira-pilot-provider-closeout.schema.json").exists()


def test_campaign_lifecycle_uses_actual_elapsed_time_and_preserves_cleanup_reserve() -> None:
    campaign = CampaignLifecycleLimits(
        campaign_provider_wall_seconds=14_400,
        normal_cleanup_reserve_seconds=900,
        provider_termination_cutoff_seconds=13_500,
        max_lambda_instances=1,
        max_launch_count=1,
        persistent_filesystems=0,
    )
    assert campaign.elapsed_seconds(billable_started_at=100.0, now=700.0) == 600.0
    assert campaign.admit_attempt(
        billable_started_at=100.0,
        now=10_000.0,
        attempt_hard_wall_seconds=3_600,
    ) is True
    assert campaign.admit_attempt(
        billable_started_at=100.0,
        now=10_000.1,
        attempt_hard_wall_seconds=3_600,
    ) is False
    assert campaign.termination_due(billable_started_at=100.0, now=13_600.0) is True


def test_host_campaign_admission_counts_setup_and_attempt_actual_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    now = time.time()
    state = tmp_path / "pilot-v3/pilot-state.json"
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
    monkeypatch.setattr(host.time, "time", lambda: now + 9_900)
    assert host.admit_next_attempt(tmp_path) == pytest.approx(3_600)
    monkeypatch.setattr(host.time, "time", lambda: now + 9_901)
    with pytest.raises(host.T09HostError, match="next attempt hard wall"):
        host.admit_next_attempt(tmp_path)
    monkeypatch.setattr(host.time, "time", lambda: now + 13_500)
    assert host.provider_termination_due(tmp_path) is True


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
                "provider_account_id": "unrelated-account",
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
                "provider_account_id": {
                    "redacted": True,
                    "reason": "structural-sensitive-field",
                }
            }
        ),
        encoding="utf-8",
    )
    assert host.privacy_violations(tmp_path) == []


def test_entered_partial_attempt_emits_schema_valid_invalid_evidence_and_is_consumed(
    tmp_path: Path,
) -> None:
    finalizer = _load_attempt_finalizer()
    contract = load_execution_contract(
        EXECUTION_CONTRACT,
        expected_sha256=file_sha256(EXECUTION_CONTRACT),
    )
    attempt = contract.attempt(ATTEMPT_ORDER[0])
    attempt_root = tmp_path / "attempt"
    attempt_root.mkdir()
    state_path = tmp_path / "pilot-state.json"
    initialize_pilot_state(
        state_path,
        execution_contract_sha256=contract.sha256,
        pilot_started_at_epoch=time.time() - 10,
        lambda_started_at_epoch=time.time() - 20,
    )
    mark_empirical_entry(
        state_path,
        execution_contract_sha256=contract.sha256,
        run_id=attempt.run_id,
    )
    (attempt_root / "normalized-events.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "event_id": "event-provider-failed",
                "parent_event_id": None,
                "kind": "provider-call-failed",
                "payload": {"exception_type": "FixtureFailure"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (attempt_root / "condition.stdout").write_text("", encoding="utf-8")
    (attempt_root / "condition.stderr").write_text("fixture failure\n", encoding="utf-8")
    cleanup_path = attempt_root / "host-cleanup-receipt.json"
    cleanup_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "run_id": attempt.run_id,
                "returncode": 1,
                "container_removed": True,
                "owned_container_residue": [],
                "secret_scan_passed": True,
                "cap_violation": None,
                "timing": {
                    "started_at": "2026-08-13T12:00:00Z",
                    "stopped_at": "2026-08-13T12:00:01Z",
                    "wall_seconds": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )
    command_path = (
        ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json"
    )
    result = finalizer.finalize(
        SimpleNamespace(
            execution_contract=EXECUTION_CONTRACT,
            execution_contract_sha256=contract.sha256,
            command_manifests=command_path,
            command_manifests_sha256=file_sha256(command_path),
            condition_plan=ROOT / attempt.condition_plan_path,
            attempt_root=attempt_root,
            run_id=attempt.run_id,
            package_commit="a" * 40,
            aggregate_ledger=tmp_path / "aggregate-budget.json",
            pilot_state=state_path,
            host_cleanup_receipt=cleanup_path,
            evaluator_root=EVALUATOR_ROOT,
            dataset=DATASET_FIXTURE,
            score_schema=ROOT / "schemas/t09-sira-pilot-score.schema.json",
            evidence_schema=ROOT / "schemas/t09-sira-pilot-evidence.schema.json",
        )
    )
    outcome = json.loads((attempt_root / "attempt-outcome.json").read_text())
    evidence = json.loads((attempt_root / "evidence-index.json").read_text())
    assert result["valid_scored_attempt"] is False
    assert outcome["artifact_execution"] is True
    assert outcome["invalid_infrastructure_attempt"] is True
    assert outcome["condition_failure"] is False
    assert evidence["outcome"] == outcome
    state = json.loads(state_path.read_text())
    assert state["attempts_completed"] == [attempt.run_id]


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
