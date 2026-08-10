from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.harness.lambda_l2_ownership import DiscoveryKind, DiscoveryResult
from giclab.harness.lambda_l2_supervisor import (
    ExecutionBinding,
    ProviderCall,
    ProviderOperation,
    SharedBudget,
)
from giclab.harness.lambda_l2_watchdog import (
    FsyncHeartbeatWriter,
    FsyncWatchdogJournal,
    GateL2Watchdog,
    MutationLease,
    WatchdogContractError,
    WatchdogHandle,
    WatchdogPhase,
    read_last_heartbeat,
    read_watchdog_credential,
    spawn_separate_session_watchdog,
    watchdog_bootstrap_contract,
    zero_secret_buffer,
)

ROOT = Path(__file__).resolve().parents[1]
DUMMY_CREDENTIAL = b"DUMMY-LAMBDA-SECRET-CANARY-WATCHDOG"


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


def make_journal(tmp_path: Path) -> FsyncWatchdogJournal:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas/t07-lambda-l2-watchdog-journal.schema.json").write_bytes(
        (ROOT / "schemas/t07-lambda-l2-watchdog-journal.schema.json").read_bytes()
    )
    run_root = tmp_path / "run"
    run_root.mkdir()
    return FsyncWatchdogJournal.create(
        tmp_path,
        path=run_root / "watchdog-journal.jsonl",
        binding=execution_binding(),
    )


def make_watchdog(tmp_path: Path) -> GateL2Watchdog:
    return GateL2Watchdog(
        binding=execution_binding(),
        journal=make_journal(tmp_path),
        budget=SharedBudget(),
    )


class FakePrimary:
    def __init__(self, *, exits_on_term: bool = True, exits_on_kill: bool = True) -> None:
        self.exited = False
        self.exits_on_term = exits_on_term
        self.exits_on_kill = exits_on_kill
        self.term_calls = 0
        self.kill_calls = 0

    def has_exited(self) -> bool:
        return self.exited

    def terminate(self) -> None:
        self.term_calls += 1
        if self.exits_on_term:
            self.exited = True

    def kill(self) -> None:
        self.kill_calls += 1
        if self.exits_on_kill:
            self.exited = True


def ready_stale_watchdog(tmp_path: Path) -> GateL2Watchdog:
    watchdog = make_watchdog(tmp_path)
    watchdog.mark_ready()
    watchdog.observe_heartbeat(1_000_000_000)
    watchdog.mark_stale(now_monotonic_ns=11_000_000_000)
    return watchdog


def test_watchdog_bootstrap_is_separate_session_and_secret_nonpersistent() -> None:
    contract = watchdog_bootstrap_contract()
    assert contract["mechanism"] == "darwin-separate-session-double-fork"
    assert contract["setsid"] is contract["double_fork"] is True
    assert contract["secret_in_argv"] is False
    assert contract["secret_in_environment"] is False
    assert contract["secret_on_disk"] is False
    assert contract["launchd_selected"] is False


def test_watchdog_anonymous_credential_frame_zeroes_primary_buffer() -> None:
    credential_read, credential_write = os.pipe()
    liveness_read, liveness_write = os.pipe()
    readiness_read, readiness_write = os.pipe()
    os.close(liveness_read)
    os.close(readiness_write)
    handle = WatchdogHandle(12345, credential_write, liveness_write, readiness_read)
    value = bytearray(DUMMY_CREDENTIAL)
    handle.deliver_credential(value)
    observed = read_watchdog_credential(credential_read)
    assert bytes(observed) == DUMMY_CREDENTIAL
    assert set(value) == {0}
    zero_secret_buffer(observed)
    assert set(observed) == {0}
    os.close(credential_read)
    handle.close_liveness()
    os.close(readiness_read)


def test_heartbeat_is_append_only_fsync_ordered_and_bounded(tmp_path: Path) -> None:
    path = tmp_path / "heartbeat.jsonl"
    writer = FsyncHeartbeatWriter.create(path)
    writer.beat(1_000)
    writer.beat(2_000)
    assert read_last_heartbeat(path) == (2, 2_000)
    writer.close()
    lines = path.read_text().splitlines()
    assert [json.loads(line)["sequence"] for line in lines] == [1, 2]


def test_heartbeat_reorder_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "heartbeat.jsonl"
    writer = FsyncHeartbeatWriter.create(path)
    writer.beat(2_000)
    writer.beat(1_000)
    writer.close()
    with pytest.raises(WatchdogContractError):
        read_last_heartbeat(path)


def test_stale_threshold_must_be_reached_before_takeover(tmp_path: Path) -> None:
    watchdog = make_watchdog(tmp_path)
    watchdog.mark_ready()
    watchdog.observe_heartbeat(1_000_000_000)
    with pytest.raises(WatchdogContractError):
        watchdog.mark_stale(now_monotonic_ns=10_999_999_999)
    assert watchdog.state.phase is WatchdogPhase.MONITORING


def test_stale_primary_term_then_mutation_lease_takeover(tmp_path: Path) -> None:
    watchdog = ready_stale_watchdog(tmp_path)
    lease_path = tmp_path / "run/mutation.lock"
    primary_lease = MutationLease.create_primary(lease_path)
    primary_lease.release()
    watchdog_lease = MutationLease.open_watchdog(lease_path)
    primary = FakePrimary(exits_on_term=True)
    watchdog.take_over(primary=primary, lease=watchdog_lease)
    assert primary.term_calls == 1
    assert primary.kill_calls == 0
    assert watchdog.state.phase is WatchdogPhase.TAKEOVER
    assert watchdog.state.mutation_lease_acquired is True
    watchdog_lease.close()
    primary_lease.close()


def test_failed_term_escalates_to_kill_before_takeover(tmp_path: Path) -> None:
    watchdog = ready_stale_watchdog(tmp_path)
    lease_path = tmp_path / "run/mutation.lock"
    primary_lease = MutationLease.create_primary(lease_path)
    primary_lease.release()
    watchdog_lease = MutationLease.open_watchdog(lease_path)
    primary = FakePrimary(exits_on_term=False, exits_on_kill=True)
    watchdog.take_over(primary=primary, lease=watchdog_lease)
    assert primary.term_calls == primary.kill_calls == 1
    watchdog_lease.close()
    primary_lease.close()


def test_primary_and_watchdog_cannot_hold_mutation_lease_together(tmp_path: Path) -> None:
    lease_path = tmp_path / "mutation.lock"
    primary = MutationLease.create_primary(lease_path)
    watchdog = MutationLease.open_watchdog(lease_path)
    assert primary.held is True
    assert watchdog.acquire(blocking=False) is False
    primary.release()
    assert watchdog.acquire(blocking=False) is True
    watchdog.close()
    primary.close()


def test_takeover_fails_closed_if_primary_survives_term_and_kill(tmp_path: Path) -> None:
    watchdog = ready_stale_watchdog(tmp_path)
    lease_path = tmp_path / "run/mutation.lock"
    primary_lease = MutationLease.create_primary(lease_path)
    primary_lease.release()
    watchdog_lease = MutationLease.open_watchdog(lease_path)
    primary = FakePrimary(exits_on_term=False, exits_on_kill=False)
    with pytest.raises(WatchdogContractError):
        watchdog.take_over(primary=primary, lease=watchdog_lease)
    assert watchdog.state.phase is WatchdogPhase.INCIDENT
    assert watchdog.state.mutation_lease_acquired is False
    watchdog_lease.close()
    primary_lease.close()


def test_watchdog_provider_allowlist_forbids_launch_and_preflight(tmp_path: Path) -> None:
    watchdog = make_watchdog(tmp_path)
    for operation, method, path, body in (
        (
            ProviderOperation.LAUNCH_INSTANCE,
            "POST",
            "/api/v1/instance-operations/launch",
            {"synthetic": True},
        ),
        (
            ProviderOperation.LIST_IMAGES,
            "GET",
            "/api/v1/images",
            None,
        ),
    ):
        with pytest.raises(WatchdogContractError):
            watchdog.reserve_provider_call(ProviderCall(operation, method, path, body))
    assert watchdog.budget.state.launch_calls == 0


def test_watchdog_cleanup_handles_one_exact_full_match(tmp_path: Path) -> None:
    watchdog = ready_stale_watchdog(tmp_path)
    lease_path = tmp_path / "run/mutation.lock"
    primary_lease = MutationLease.create_primary(lease_path)
    primary_lease.release()
    watchdog_lease = MutationLease.open_watchdog(lease_path)
    watchdog.take_over(primary=FakePrimary(exits_on_term=True), lease=watchdog_lease)
    watchdog.begin_discovery()
    watchdog.apply_discovery(
        DiscoveryResult(DiscoveryKind.ONE_FULL_MATCH, ("instance-test",)),
        approve_duplicates=False,
    )
    assert watchdog.state.phase is WatchdogPhase.TERMINATING
    watchdog.record_terminal("instance-test", "terminated")
    watchdog.restore_firewall()
    watchdog.close_clean()
    assert watchdog.state.phase is WatchdogPhase.CLOSED
    watchdog_lease.close()
    primary_lease.close()


def test_duplicate_full_matches_need_explicit_approval(tmp_path: Path) -> None:
    watchdog = ready_stale_watchdog(tmp_path)
    lease_path = tmp_path / "run/mutation.lock"
    primary_lease = MutationLease.create_primary(lease_path)
    primary_lease.release()
    watchdog_lease = MutationLease.open_watchdog(lease_path)
    watchdog.take_over(primary=FakePrimary(), lease=watchdog_lease)
    watchdog.begin_discovery()
    watchdog.apply_discovery(
        DiscoveryResult(
            DiscoveryKind.MULTIPLE_FULL_MATCHES,
            ("instance-one", "instance-two"),
        ),
        approve_duplicates=False,
    )
    assert watchdog.state.phase is WatchdogPhase.INCIDENT
    assert watchdog.state.owned_instance_ids == ()
    watchdog_lease.close()
    primary_lease.close()


def test_partial_match_never_becomes_a_termination_target(tmp_path: Path) -> None:
    watchdog = ready_stale_watchdog(tmp_path)
    lease_path = tmp_path / "run/mutation.lock"
    primary_lease = MutationLease.create_primary(lease_path)
    primary_lease.release()
    watchdog_lease = MutationLease.open_watchdog(lease_path)
    watchdog.take_over(primary=FakePrimary(), lease=watchdog_lease)
    watchdog.begin_discovery()
    watchdog.apply_discovery(
        DiscoveryResult(DiscoveryKind.PARTIAL_MARKER, (), 1, 0),
        approve_duplicates=True,
    )
    assert watchdog.state.phase is WatchdogPhase.INCIDENT
    assert watchdog.state.owned_instance_ids == ()
    watchdog_lease.close()
    primary_lease.close()


def test_global_restore_is_blocked_until_every_owned_id_is_terminal(tmp_path: Path) -> None:
    watchdog = ready_stale_watchdog(tmp_path)
    lease_path = tmp_path / "run/mutation.lock"
    primary_lease = MutationLease.create_primary(lease_path)
    primary_lease.release()
    watchdog_lease = MutationLease.open_watchdog(lease_path)
    watchdog.take_over(primary=FakePrimary(), lease=watchdog_lease)
    watchdog.begin_discovery()
    watchdog.apply_discovery(
        DiscoveryResult(
            DiscoveryKind.MULTIPLE_FULL_MATCHES,
            ("instance-one", "instance-two"),
        ),
        approve_duplicates=True,
    )
    watchdog.record_terminal("instance-one", "terminated")
    with pytest.raises(WatchdogContractError):
        watchdog.restore_firewall()
    assert watchdog.state.global_firewall_restored is False
    watchdog_lease.close()
    primary_lease.close()


def test_network_or_api_outage_can_be_sealed_only_as_incident(tmp_path: Path) -> None:
    watchdog = make_watchdog(tmp_path)
    watchdog.raise_incident("lambda_api_and_console_unavailable")
    assert watchdog.state.phase is WatchdogPhase.INCIDENT
    assert watchdog.state.incident_class == "lambda_api_and_console_unavailable"


def test_watchdog_journal_is_schema_valid_and_secret_free(tmp_path: Path) -> None:
    watchdog = make_watchdog(tmp_path)
    watchdog.mark_ready()
    snapshot = watchdog.journal.snapshot()
    schema = json.loads((ROOT / "schemas/t07-lambda-l2-watchdog-journal.schema.json").read_text())
    for line in snapshot.path.read_text().splitlines():
        assert not list(Draft202012Validator(schema).iter_errors(json.loads(line)))
    assert DUMMY_CREDENTIAL not in snapshot.path.read_bytes()
    assert snapshot.events == 2


def test_watchdog_contract_names_honest_failure_limits() -> None:
    limits = set(watchdog_bootstrap_contract()["known_limits"])
    assert {
        "mac_power_loss",
        "local_network_loss",
        "lambda_api_outage",
        "lambda_console_outage",
        "simultaneous_primary_watchdog_failure",
    } == limits


def test_terminal_decision_blocks_concrete_watchdog_spawn_before_fork(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def pipe_must_not_open() -> tuple[int, int]:
        raise AssertionError("pipe opened under terminal decision")

    monkeypatch.setattr("giclab.harness.lambda_l2_watchdog.os.pipe", pipe_must_not_open)
    with pytest.raises(WatchdogContractError, match="manual-console-launch-required"):
        spawn_separate_session_watchdog(lambda _bootstrap: 0)
