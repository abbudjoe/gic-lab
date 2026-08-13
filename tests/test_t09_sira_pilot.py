from __future__ import annotations

import ast
import copy
import importlib.util
import inspect
import io
import json
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
    no_time = replace(passing, remaining_campaign_seconds=5_159.999)
    no_time_decision = first_pair_decision(no_time)
    assert no_time_decision["decision"] == "stop-before-task-b"
    assert "insufficient_campaign_time_for_next_attempt_and_cleanup" in no_time_decision["reasons"]
    exact_time = replace(passing, remaining_campaign_seconds=5_160.0)
    exact_time_decision = first_pair_decision(exact_time)
    assert exact_time_decision["decision"] == "continue-to-task-b"
    assert exact_time_decision["required_campaign_seconds_for_next_attempt"] == 5_160


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
                    "region": {"name": provider.REGION},
                    "family": "lambda-stack-22-04",
                }
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
                "authorization_reference": "AUTH-T09-PRAGMATIC-PILOT-2026-08-13",
                "authorized": True,
                "single_use": True,
                "clean_package_commit": package_commit,
                "plan_id": provider.PLAN_ID,
                "plan_sha256": provider.file_sha256(plan_path),
                "max_lambda_instances": 1,
                "max_launch_count": 1,
                "persistent_filesystems": 0,
                "lambda_cost_cap_usd": 5.16,
                "openai_cost_cap_usd": 40.0,
                "aggregate_cost_cap_usd": 45.16,
                "artifact_destination": (
                    "/Volumes/Macintosh HD - Data/GIC-Lab/t09/sealed-artifacts"
                ),
            }
        ),
        encoding="utf-8",
    )
    authorization.chmod(0o600)
    monkeypatch.setattr(provider, "_verify_clean_package", lambda *_args, **_kwargs: None)
    capability = [tmp_path / "launch-capabilities/malformed.json"]
    monkeypatch.setattr(provider, "launch_capability_path", lambda: capability[0])

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

    capability[0] = tmp_path / "launch-capabilities/duplicate-cleanup-failure.json"
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

    capability[0] = tmp_path / "launch-capabilities/multi-cleanup.json"
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

    capability[0] = tmp_path / "launch-capabilities/success.json"
    private_root = tmp_path / "provider-private"
    entry_path = provider.launch_campaign(
        repository=ROOT,
        package_commit=package_commit,
        authorization_ledger=authorization,
        dotenv=dotenv,
        private_root=private_root,
        public_ipv4_file=public_ip_path,
        ssh_public_key_file=key_path,
        transport=FakeTransport(launch_responses),
        clock=clock,
        sleeper=sleeper,
    )
    consumed = load_json(capability[0])
    assert consumed["launch_capability_state"] == "consumed-cleanup-only-after-this-point"
    assert consumed["launch_capability_limit"] == 1
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
    closeout_path = provider.closeout_campaign(
        repository=ROOT,
        package_commit=package_commit,
        authorization_ledger=authorization,
        dotenv=dotenv,
        private_root=private_root,
        transport=FakeTransport(closeout_responses),
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
        observer_limits=ObserverLifecycleLimits.t09_pragmatic_v3(),
        max_instances=1,
        max_launches=1,
        persistent_filesystems=0,
    )
    assert lifecycle.termination_due(
        started_at_epoch=100.0,
        now_epoch=13_600.0,
    )
    observer = ObserverLifecycleLimits.t09_pragmatic_v3()
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
        max_launch_count=1,
        persistent_filesystems=0,
    )
    assert campaign.elapsed_seconds(billable_started_at=100.0, now=700.0) == 600.0
    assert (
        campaign.admit_attempt(
            billable_started_at=100.0,
            now=9_340.0,
            attempt_hard_wall_seconds=3_600,
        )
        is True
    )
    assert (
        campaign.admit_attempt(
            billable_started_at=100.0,
            now=9_340.1,
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
    # 3,600 condition + 600 evaluator/export + 60 termination handoff +
    # 900 cleanup must all remain on the one actual campaign clock.
    monkeypatch.setattr(host.time, "time", lambda: now + 9_240)
    assert host.admit_next_attempt(tmp_path) == pytest.approx(3_600)
    monkeypatch.setattr(host.time, "time", lambda: now + 9_241)
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


def test_finalized_attempt_streams_before_cutoff_without_aggregate_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    now = time.time()
    monkeypatch.setattr(host.time, "time", lambda: now)
    command_document = load_json(
        ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json"
    )
    manifest = next(
        item for item in command_document["manifests"] if item["run_id"] == ATTEMPT_ORDER[0]
    )
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / manifest["permitted_condition_owned"]["output_root"]
    attempt_root.mkdir(parents=True)
    pilot_root = artifact_root / "pilot-v3"
    pilot_root.mkdir(exist_ok=True)
    (pilot_root / "pilot-state.json").write_text(
        json.dumps(
            {
                "lambda_started_at_epoch": now - 100,
                "attempts_completed": [ATTEMPT_ORDER[0]],
            }
        ),
        encoding="utf-8",
    )
    for name in ("attempt-outcome.json", "evidence-index.json", "host-cleanup-receipt.json"):
        (attempt_root / name).write_text("{}\n", encoding="utf-8")
    (attempt_root / "normalized-events.jsonl").write_text("{}\n", encoding="utf-8")
    (attempt_root / "attempt-wall.json").write_text(
        json.dumps({"evidence_handoff_deadline_epoch": now + 60}),
        encoding="utf-8",
    )
    arguments = SimpleNamespace(
        repository=ROOT,
        artifact_root=artifact_root,
        run_id=ATTEMPT_ORDER[0],
        package_commit="a" * 40,
    )
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
    host.verify_attempt_export(
        SimpleNamespace(
            inbound_root=inbound,
            attempt_export=inbound_archive,
            run_id=ATTEMPT_ORDER[0],
            package_commit="a" * 40,
            provider_entry_receipt=provider_entry,
        )
    )
    verification = inbound / f"{ATTEMPT_ORDER[0]}-export-verification.json"
    assert verification.is_file()
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
