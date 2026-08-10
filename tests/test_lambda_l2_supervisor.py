from __future__ import annotations

import json
from collections import deque
from collections.abc import Mapping
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.harness.lambda_l2_ownership import (
    DiscoveryKind,
    DiscoveryResult,
    ExpectedOwnedInstance,
    OwnershipBinding,
    classify_discovery,
    derive_owned_launch_marker,
)
from giclab.harness.lambda_l2_supervisor import (
    ABSOLUTE_INCIDENT_SECONDS,
    MAX_PROVIDER_CALLS,
    RESIDUAL_RISK_STATEMENT,
    TERMINAL_DECISION,
    Actor,
    CompletionEvidence,
    ExecutionBinding,
    FsyncTransactionJournal,
    GateL2Supervisor,
    InProcessLambdaBoundary,
    L21SupervisorError,
    ProcessCall,
    ProcessOperation,
    ProcessResult,
    ProviderCall,
    ProviderFailure,
    ProviderOperation,
    ProviderResult,
    SharedBudget,
    ShellFreeProcessBoundary,
    SupervisorPhase,
    exact_l21_limits,
    incident_requires_manual_console,
    projected_list_cost_cents,
    validate_launch_body,
    validate_process_call,
    validate_provider_call,
    validate_recovery_decision,
)

ROOT = Path(__file__).resolve().parents[1]
DUMMY_CREDENTIAL = "DUMMY-LAMBDA-SECRET-CANARY-L21"


def execution_binding() -> ExecutionBinding:
    return ExecutionBinding(
        plan_id="PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V2",
        plan_sha256="1" * 64,
        run_id="RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0002",
        authorization_reference="AUTH-T07-GATE-L2-LAMBDA-TEST-0001",
        repository_commit="a" * 40,
        reviewed_implementation_commit="b" * 40,
        human_decision_seal_sha256="2" * 64,
        launch_recovery_decision_seal_sha256="3" * 64,
        private_parameter_seal_reference="private-seal-test",
    )


def expected() -> ExpectedOwnedInstance:
    binding = OwnershipBinding(
        plan_id="PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V2",
        plan_sha256="1" * 64,
        authorization_reference="AUTH-T07-GATE-L2-LAMBDA-TEST-0001",
        instance_type_name="gpu_1x_a10",
        region_name="us-east-1",
        image_identity_sha256="4" * 64,
        ssh_key_identity_sha256="5" * 64,
        regional_ruleset_identity_sha256="6" * 64,
        human_decision_seal_sha256="2" * 64,
        launch_recovery_decision_seal_sha256="3" * 64,
    )
    return ExpectedOwnedInstance(
        derive_owned_launch_marker(bytes(range(32)), binding),
        "us-east-1",
        "gpu_1x_a10",
        ("fractal-lambda-codex",),
        ("ruleset-test",),
    )


def launch_body() -> dict[str, object]:
    contract = expected()
    return {
        "region_name": "us-east-1",
        "instance_type_name": "gpu_1x_a10",
        "ssh_key_names": ["fractal-lambda-codex"],
        "file_system_names": [],
        "file_system_mounts": [],
        "name": contract.marker.name,
        "hostname": contract.marker.hostname,
        "image": {"id": "raw-image-test"},
        "tags": contract.marker.provider_tags(),
        "firewall_rulesets": [{"id": "ruleset-test"}],
    }


def instance(
    *,
    instance_id: str = "instance-test",
    hostname: str | None = None,
    region: str = "us-east-1",
) -> dict[str, object]:
    contract = expected()
    return {
        "id": instance_id,
        "name": contract.marker.name,
        "hostname": contract.marker.hostname if hostname is None else hostname,
        "tags": contract.marker.provider_tags(),
        "region": {"name": region},
        "instance_type": {"name": "gpu_1x_a10"},
        "ssh_key_names": ["fractal-lambda-codex"],
        "firewall_rulesets": [{"id": "ruleset-test"}],
        "file_system_names": [],
        "actions": {},
        "status": "booting",
    }


class FakeProvider:
    def __init__(self, outcomes: list[ProviderResult | ProviderFailure]) -> None:
        self.outcomes = deque(outcomes)
        self.calls: list[ProviderCall] = []

    def send(
        self,
        call: ProviderCall,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> ProviderResult:
        assert credential == DUMMY_CREDENTIAL
        assert timeout_seconds == 30
        self.calls.append(call)
        if not self.outcomes:
            raise AssertionError("fake provider outcome missing")
        outcome = self.outcomes.popleft()
        if isinstance(outcome, ProviderFailure):
            raise outcome
        return outcome


class FakeProcess:
    def __init__(self, result: ProcessResult | None = None) -> None:
        self.result = result or ProcessResult(0, b"ok", b"", 5)
        self.calls: list[ProcessCall] = []

    def run(self, call: ProcessCall) -> ProcessResult:
        self.calls.append(call)
        return self.result


def response(status: int, document: Mapping[str, object]) -> ProviderResult:
    return ProviderResult(
        status,
        "application/json",
        json.dumps(document, sort_keys=True).encode(),
        12,
    )


def completion_evidence(**changes: object) -> CompletionEvidence:
    values: dict[str, object] = {
        "authorization_sha256": "1" * 64,
        "plan_sha256": "2" * 64,
        "transaction_journal_sha256": "3" * 64,
        "watchdog_journal_sha256": "4" * 64,
        "private_parameter_seal_sha256": "5" * 64,
        "host_evidence_manifest_sha256": "6" * 64,
        "containment_evidence_sha256": "7" * 64,
        "transfer_verification_sha256": "8" * 64,
        "provider_terminal_proven": True,
        "regional_ruleset_absent": True,
        "global_firewall_exactly_restored": True,
        "zero_owned_residue_proven": True,
        "secret_scan_passed": True,
        "local_source_retained": True,
        "destination_hashes_verified": True,
        "archive_fsynced_and_atomically_finalized": True,
        "watchdog_terminal_state": "all_clean",
    }
    values.update(changes)
    return CompletionEvidence(**values)  # type: ignore[arg-type]


def make_journal(tmp_path: Path) -> FsyncTransactionJournal:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas/t07-lambda-l2-transaction-journal.schema.json").write_bytes(
        (ROOT / "schemas/t07-lambda-l2-transaction-journal.schema.json").read_bytes()
    )
    run_root = tmp_path / "run"
    run_root.mkdir()
    return FsyncTransactionJournal.create(
        tmp_path,
        path=run_root / "transaction-journal.jsonl",
        binding=execution_binding(),
    )


def make_supervisor(
    tmp_path: Path,
    provider: FakeProvider,
    *,
    process: FakeProcess | None = None,
) -> GateL2Supervisor:
    return GateL2Supervisor(
        binding=execution_binding(),
        expected=expected(),
        journal=make_journal(tmp_path),
        provider=provider,
        process=process or FakeProcess(),
        credential=DUMMY_CREDENTIAL,
    )


def prepare_launch(supervisor: GateL2Supervisor) -> None:
    supervisor.mark_preflight_verified(DiscoveryResult(DiscoveryKind.ZERO_MATCHES))
    supervisor.mark_watchdog_ready()
    supervisor.mark_firewall_strict()
    supervisor.seal_launch_body(launch_body())


def bind_for_cleanup(supervisor: GateL2Supervisor) -> None:
    supervisor.bind_candidate_detail(
        candidate_id="instance-test",
        detail=instance(),
    )
    supervisor.require_cleanup()


def test_launch_success_with_one_id_then_exact_detail_binding(tmp_path: Path) -> None:
    provider = FakeProvider([response(200, {"data": {"instance_ids": ["instance-test"]}})])
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    assert supervisor.execute_launch(launch_body()) == ("instance-test",)
    supervisor.bind_candidate_detail(candidate_id="instance-test", detail=instance())
    assert supervisor.state.phase is SupervisorPhase.INSTANCE_BOUND
    assert supervisor.state.owned_instance_ids == ("instance-test",)
    assert supervisor.state.launch_send_count == 1


@pytest.mark.parametrize("status", [400, 401, 403, 409, 500, 503])
def test_launch_known_4xx_or_5xx_still_enters_bounded_discovery(
    tmp_path: Path, status: int
) -> None:
    provider = FakeProvider([response(status, {"error": {"code": "synthetic"}})])
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    assert supervisor.execute_launch(launch_body()) is None
    assert supervisor.state.phase is SupervisorPhase.DISCOVERY
    assert supervisor.state.launch_send_count == 1


def test_failure_before_send_does_not_call_provider_or_burn_marker(tmp_path: Path) -> None:
    provider = FakeProvider([])
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    invalid = launch_body()
    del invalid["hostname"]
    with pytest.raises(L21SupervisorError):
        supervisor.execute_launch(invalid)
    assert provider.calls == []
    assert supervisor.state.launch_send_count == 0
    assert supervisor.state.marker_burned is False


@pytest.mark.parametrize(
    "failure",
    [
        ProviderFailure("dns", "dns_failure", False),
        ProviderFailure("tls", "tls_failure", False),
        ProviderFailure("response_headers", "timeout_after_send", True),
    ],
)
def test_unknown_after_send_burns_marker_and_never_retries(
    tmp_path: Path, failure: ProviderFailure
) -> None:
    provider = FakeProvider([failure])
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    assert supervisor.execute_launch(launch_body()) is None
    assert supervisor.state.phase is SupervisorPhase.DISCOVERY
    assert supervisor.state.marker_burned is True
    with pytest.raises(L21SupervisorError):
        supervisor.execute_launch(launch_body())
    assert len(provider.calls) == 1


def test_discovery_one_full_match_requires_detail_revalidation(tmp_path: Path) -> None:
    provider = FakeProvider(
        [
            ProviderFailure("response_headers", "timeout_after_send", True),
            response(200, {"data": [instance()]}),
        ]
    )
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    supervisor.execute_launch(launch_body())
    result = supervisor.execute_discovery_list()
    assert result.kind is DiscoveryKind.ONE_FULL_MATCH
    supervisor.apply_discovery(result, approve_duplicates=False)
    assert supervisor.state.phase is SupervisorPhase.DISCOVERY
    supervisor.bind_candidate_detail(candidate_id="instance-test", detail=instance())
    assert supervisor.state.phase is SupervisorPhase.INSTANCE_BOUND


def test_partial_marker_collision_is_never_selected_or_terminated(tmp_path: Path) -> None:
    supervisor = make_supervisor(tmp_path, FakeProvider([]))
    prepare_launch(supervisor)
    supervisor.launch_send_started(launch_body())
    supervisor.record_launch_unknown(failure_class="synthetic")
    result = classify_discovery([instance(hostname="unrelated")], expected())
    supervisor.apply_discovery(result, approve_duplicates=True)
    assert supervisor.state.phase is SupervisorPhase.INCIDENT
    assert supervisor.state.owned_instance_ids == ()


def test_two_full_marker_duplicates_require_separate_approval(tmp_path: Path) -> None:
    supervisor = make_supervisor(tmp_path, FakeProvider([]))
    prepare_launch(supervisor)
    supervisor.launch_send_started(launch_body())
    supervisor.record_launch_unknown(failure_class="synthetic")
    result = classify_discovery(
        [instance(instance_id="instance-one"), instance(instance_id="instance-two")],
        expected(),
    )
    supervisor.apply_discovery(result, approve_duplicates=False)
    assert supervisor.state.phase is SupervisorPhase.INCIDENT
    assert supervisor.state.owned_instance_ids == ()


def test_conflicting_detail_is_a_hard_incident(tmp_path: Path) -> None:
    provider = FakeProvider([response(200, {"data": {"instance_ids": ["instance-test"]}})])
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    supervisor.execute_launch(launch_body())
    with pytest.raises(L21SupervisorError):
        supervisor.bind_candidate_detail(
            candidate_id="instance-test",
            detail=instance(region="us-west-1"),
        )
    assert supervisor.state.phase is SupervisorPhase.INCIDENT


def test_exact_id_only_termination_and_no_resend(tmp_path: Path) -> None:
    provider = FakeProvider(
        [
            response(200, {"data": {"instance_ids": ["instance-test"]}}),
            ProviderFailure("response_headers", "timeout_after_send", True),
        ]
    )
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    supervisor.execute_launch(launch_body())
    bind_for_cleanup(supervisor)
    with pytest.raises(L21SupervisorError):
        supervisor.execute_termination("unrelated-instance")
    assert supervisor.execute_termination("instance-test") is None
    with pytest.raises(L21SupervisorError):
        supervisor.execute_termination("instance-test")
    assert [call.operation for call in provider.calls].count(
        ProviderOperation.TERMINATE_INSTANCE
    ) == 1


def test_unknown_termination_then_terminal_poll_proof_allows_restore(tmp_path: Path) -> None:
    provider = FakeProvider(
        [
            response(200, {"data": {"instance_ids": ["instance-test"]}}),
            ProviderFailure("response_headers", "timeout_after_send", True),
        ]
    )
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    supervisor.execute_launch(launch_body())
    bind_for_cleanup(supervisor)
    supervisor.execute_termination("instance-test")
    supervisor.record_terminal("instance-test", "terminated")
    supervisor.record_firewall_restored()
    assert supervisor.state.global_firewall_restored is True


def test_unresolved_termination_preserves_strict_firewall(tmp_path: Path) -> None:
    provider = FakeProvider([response(200, {"data": {"instance_ids": ["instance-test"]}})])
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    supervisor.execute_launch(launch_body())
    bind_for_cleanup(supervisor)
    with pytest.raises(L21SupervisorError):
        supervisor.record_firewall_restored()
    assert supervisor.state.global_firewall_restored is False


def test_complete_success_requires_cleanup_then_verified_archive(tmp_path: Path) -> None:
    provider = FakeProvider(
        [
            response(200, {"data": {"instance_ids": ["instance-test"]}}),
            response(200, {"data": {"terminated_instances": ["instance-test"]}}),
        ]
    )
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    supervisor.execute_launch(launch_body())
    bind_for_cleanup(supervisor)
    supervisor.execute_termination("instance-test")
    supervisor.record_terminal("instance-test", "terminated")
    supervisor.record_firewall_restored()
    supervisor.record_archive_finalized(4096)
    supervisor.close_success(completion_evidence())
    assert supervisor.state.phase is SupervisorPhase.CLOSED
    assert supervisor.journal.snapshot().events > 10


def test_incomplete_evidence_cannot_be_sealed_as_success(tmp_path: Path) -> None:
    provider = FakeProvider(
        [
            response(200, {"data": {"instance_ids": ["instance-test"]}}),
            response(200, {"data": {"terminated_instances": ["instance-test"]}}),
        ]
    )
    supervisor = make_supervisor(tmp_path, provider)
    prepare_launch(supervisor)
    supervisor.execute_launch(launch_body())
    bind_for_cleanup(supervisor)
    supervisor.execute_termination("instance-test")
    supervisor.record_terminal("instance-test", "terminated")
    supervisor.record_firewall_restored()
    supervisor.record_archive_finalized(4096)
    with pytest.raises(L21SupervisorError):
        supervisor.close_success(completion_evidence(secret_scan_passed=False))
    assert supervisor.state.phase is SupervisorPhase.ARCHIVING


def test_shell_free_process_policy_and_shared_counter(tmp_path: Path) -> None:
    provider = FakeProvider([response(200, {"data": {"instance_ids": ["instance-test"]}})])
    process = FakeProcess(ProcessResult(0, b"host-ok", b"", 3))
    supervisor = make_supervisor(tmp_path, provider, process=process)
    prepare_launch(supervisor)
    supervisor.execute_launch(launch_body())
    supervisor.bind_candidate_detail(candidate_id="instance-test", detail=instance())
    supervisor.begin_qualification()
    call = ProcessCall(
        ProcessOperation.SSH_HOST_INSPECTION,
        ("/usr/bin/ssh", "synthetic-host", "--", "uname", "-a"),
        30,
        1024,
        {"PATH": "/usr/bin"},
    )
    validate_process_call(call)
    result = supervisor.run_process(call, alias="host-inspection")
    assert result.stdout == b"host-ok"
    assert supervisor.budget.state.process_calls == 1


def test_provider_policy_rejects_wrong_method_query_and_watchdog_launch() -> None:
    with pytest.raises(L21SupervisorError):
        validate_provider_call(
            ProviderCall(
                ProviderOperation.LIST_INSTANCES,
                "POST",
                "/api/v1/instances",
                {},
            )
        )
    with pytest.raises(L21SupervisorError):
        validate_provider_call(
            ProviderCall(
                ProviderOperation.LIST_INSTANCES,
                "GET",
                "/api/v1/instances?page=2",
            )
        )
    budget = SharedBudget()
    with pytest.raises(L21SupervisorError):
        budget.reserve_provider(ProviderOperation.LAUNCH_INSTANCE, actor=Actor.WATCHDOG)


def test_aggregate_budget_blocks_second_launch_and_provider_overrun() -> None:
    budget = SharedBudget()
    budget.reserve_provider(ProviderOperation.LAUNCH_INSTANCE, actor=Actor.PRIMARY)
    with pytest.raises(L21SupervisorError):
        budget.reserve_provider(ProviderOperation.LAUNCH_INSTANCE, actor=Actor.PRIMARY)
    read_budget = SharedBudget()
    for _index in range(MAX_PROVIDER_CALLS):
        read_budget.reserve_provider(ProviderOperation.LIST_INSTANCES, actor=Actor.PRIMARY)
    with pytest.raises(L21SupervisorError):
        read_budget.reserve_provider(ProviderOperation.LIST_INSTANCES, actor=Actor.PRIMARY)


def test_sensitive_projection_drops_jupyter_tokens_and_public_ids(tmp_path: Path) -> None:
    supervisor = make_supervisor(tmp_path, FakeProvider([]))
    sensitive = instance()
    sensitive.update(
        {
            "jupyter_token": "DUMMY-JUPYTER-SECRET-CANARY",
            "jupyter_url": "https://example.invalid/?token=DUMMY-JUPYTER-SECRET-CANARY",
        }
    )
    private = supervisor.project_private_provider_evidence(sensitive)
    assert "jupyter_token" not in private and "jupyter_url" not in private
    public = json.dumps(supervisor.public_evidence_projection(), sort_keys=True)
    assert "instance-test" not in public
    assert DUMMY_CREDENTIAL not in public


def test_residual_decision_is_all_explicit_and_absence_blocks() -> None:
    complete = {
        "schema_version": "0.1.0",
        "decision_id": "T07-L2-LAUNCH-RECOVERY-DECISION-V1",
        "approve_unique_marker_discovery": True,
        "approve_terminate_all_exact_full_marker_matches": True,
        "approve_no_launch_retry_after_possible_send": True,
        "approve_manual_console_fallback": True,
        "acknowledge_provider_control_plane_outage_residual_risk": True,
        "residual_risk_statement": RESIDUAL_RISK_STATEMENT,
        "manual_console_fallback_operator": "user",
        "manual_console_response_window_seconds": 900,
        "decision_nonce": "a" * 64,
    }
    validate_recovery_decision(complete)
    complete["approve_manual_console_fallback"] = False
    with pytest.raises(L21SupervisorError):
        validate_recovery_decision(complete)


def test_repository_decision_template_is_deliberately_fail_closed() -> None:
    template = json.loads(
        (
            ROOT / "containers/sira-smoke/lambda/T07_L2_LAUNCH_RECOVERY_DECISION_TEMPLATE.json"
        ).read_text()
    )
    schema = json.loads(
        (ROOT / "schemas/t07-lambda-l2-launch-recovery-decision.schema.json").read_text()
    )
    assert list(Draft202012Validator(schema).iter_errors(template))
    template["decision_nonce"] = "a" * 64
    assert not list(Draft202012Validator(schema).iter_errors(template))
    with pytest.raises(L21SupervisorError):
        validate_recovery_decision(template)


def test_numeric_caps_are_complete_and_cost_math_is_conservative() -> None:
    limits = exact_l21_limits()
    assert limits and all(value is not None for value in limits.values())
    assert limits["launch_calls"] == 1
    assert limits["persistent_filesystem_count"] == 0
    assert limits["model_calls"] == limits["browser_actions"] == 0
    assert projected_list_cost_cents(3600) == 129
    assert projected_list_cost_cents(ABSOLUTE_INCIDENT_SECONDS) == 194
    with pytest.raises(L21SupervisorError):
        projected_list_cost_cents(ABSOLUTE_INCIDENT_SECONDS + 1)


def test_manual_console_trigger_is_only_for_possible_unresolved_launch() -> None:
    assert incident_requires_manual_console(
        launch_may_have_been_sent=True,
        owned_instance_resolved=False,
        terminal_proof_observed=False,
    )
    assert not incident_requires_manual_console(
        launch_may_have_been_sent=False,
        owned_instance_resolved=False,
        terminal_proof_observed=False,
    )


def test_launch_body_has_no_filesystem_or_user_data_and_is_frozen() -> None:
    body = launch_body()
    encoded = validate_launch_body(body, expected())
    assert b"user_data" not in encoded
    assert body["file_system_names"] == body["file_system_mounts"] == []
    changed = dict(body)
    changed["file_system_names"] = ["forbidden"]
    with pytest.raises(L21SupervisorError):
        validate_launch_body(changed, expected())


def test_terminal_decision_blocks_concrete_https_and_process_effectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def connection_must_not_open(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("HTTPS connection opened under terminal decision")

    def process_must_not_start(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("process started under terminal decision")

    monkeypatch.setattr(
        "giclab.harness.lambda_l2_supervisor.http.client.HTTPSConnection",
        connection_must_not_open,
    )
    monkeypatch.setattr(
        "giclab.harness.lambda_l2_supervisor.subprocess.Popen",
        process_must_not_start,
    )
    with pytest.raises(L21SupervisorError, match=TERMINAL_DECISION):
        InProcessLambdaBoundary().send(
            ProviderCall(
                ProviderOperation.LIST_INSTANCES,
                "GET",
                "/api/v1/instances",
            ),
            credential="PUBLIC-DUMMY-NOT-A-SECRET",
            timeout_seconds=1,
        )
    with pytest.raises(L21SupervisorError, match=TERMINAL_DECISION):
        ShellFreeProcessBoundary().run(
            ProcessCall(
                ProcessOperation.TCP_READINESS,
                ("/usr/bin/nc", "-z", "127.0.0.1", "22"),
                1,
                1_024,
            )
        )
