from __future__ import annotations

import contextlib
import hashlib
import json
import socket
import tempfile
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import BinaryIO, cast

import pytest

from giclab.control.production import _AccountingObserver, _ValidatedRuntimeClock
from giclab.control.remote_bridge import (
    AcceptedPrivateConditionChannel,
    CanonicalFrameRelay,
    ConditionBridgeFrame,
    ConditionSessionBinding,
    ConditionSessionSupervisor,
    ConditionSessionTerminalReceipt,
    FramedDuplexEndpoint,
    PrivateConditionListener,
    RemoteBridgeDisconnected,
    RemoteBridgeError,
    RemoteBridgeReplay,
    canonical_bytes,
    expected_condition_bridge_evidence,
    semantic_sha256,
    validate_condition_bridge_evidence,
)
from giclab.harness.sira_gate_a import (
    SIRA_MODEL_REVISION,
    SIRA_SERVICE_TIER,
    ImmutableModelRouting,
    ModelRole,
    ProviderBudgetBoundary,
    ProviderBudgetCaps,
    ProviderBudgetExceeded,
    ProviderFailureDisposition,
    ProviderRequest,
    ProviderResponseReceiptError,
    ProviderResponseUsage,
    aggregate_caps,
    condition_caps,
)
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT
from giclab.harness.t09_runtime_admission import (
    DuplexSupervisorPort,
    build_private_socket_supervisor_port,
)


@pytest.fixture
def short_tmp_path() -> Iterator[Path]:
    # Darwin's filesystem-backed AF_UNIX path cap is shorter than pytest's
    # descriptive per-test path. The runtime contract deliberately keeps its
    # socket inside the attempt root, so use a short isolated attempt root.
    with tempfile.TemporaryDirectory(prefix="t09-bridge-", dir="/tmp") as value:
        yield Path(value)


class _ClockSource:
    def monotonic(self) -> float:
        return time.monotonic()

    def wall_time(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass
class _Session:
    port: DuplexSupervisorPort
    boundary: ProviderBudgetBoundary
    observer: _AccountingObserver
    server_endpoint: FramedDuplexEndpoint
    client_endpoint: FramedDuplexEndpoint
    future: Future[ConditionSessionTerminalReceipt]
    pool: ThreadPoolExecutor
    streams: tuple[BinaryIO, ...]
    sockets: tuple[socket.socket, ...]

    def close(self) -> None:
        for channel in self.sockets:
            with contextlib.suppress(OSError):
                channel.shutdown(socket.SHUT_RDWR)
        for stream in self.streams:
            stream.close()
        for channel in self.sockets:
            channel.close()
        self.pool.shutdown(wait=True, cancel_futures=True)


def _binding(*, run_id: str | None = None) -> ConditionSessionBinding:
    selected_run = run_id or V16_PROVIDER_CONTRACT.run_ids[0]
    return ConditionSessionBinding(
        session_id=f"SESSION-{selected_run}",
        provider_contract_version=V16_PROVIDER_CONTRACT.version,
        plan_id=V16_PROVIDER_CONTRACT.plan_id,
        host_run_id=V16_PROVIDER_CONTRACT.host_run_id,
        condition_run_id=selected_run,
        evaluator_run_id=V16_PROVIDER_CONTRACT.evaluator_run_ids[
            V16_PROVIDER_CONTRACT.run_ids.index(selected_run)
        ],
        frozen_manifest_sha256="a" * 64,
    )


def _caps(**changes: int | float) -> ProviderBudgetCaps:
    values: dict[str, int | float] = {
        "max_model_call_attempts": 8,
        "max_browser_actions": 8,
        **changes,
    }
    return replace(condition_caps("simulative"), **values)


def _open_session(
    tmp_path: Path,
    *,
    binding: ConditionSessionBinding | None = None,
    caps: ProviderBudgetCaps | None = None,
) -> _Session:
    selected_binding = binding or _binding()
    selected_caps = caps or _caps()
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=replace(
            aggregate_caps(),
            max_model_call_attempts=64,
            max_browser_actions=64,
        ),
        condition_caps=selected_caps,
    )
    clock = _ValidatedRuntimeClock(_ClockSource())
    observer = _AccountingObserver(
        run_id=selected_binding.condition_run_id,
        model_revision=SIRA_MODEL_REVISION,
        service_tier=SIRA_SERVICE_TIER,
        boundary=boundary,
        prior_call_ids=frozenset(),
        prior_logical_call_ids=frozenset(),
        clock=clock,
        campaign_deadline_monotonic=time.monotonic() + 30.0,
    )
    left, right = socket.socketpair()
    server_reader = left.makefile("rb", buffering=0)
    server_writer = left.makefile("wb", buffering=0)
    client_reader = right.makefile("rb", buffering=0)
    client_writer = right.makefile("wb", buffering=0)
    deadline = time.monotonic() + 30.0
    server_endpoint = FramedDuplexEndpoint(
        reader=server_reader,
        writer=server_writer,
        binding=selected_binding,
        deadline_monotonic=deadline,
    )
    client_endpoint = FramedDuplexEndpoint(
        reader=client_reader,
        writer=client_writer,
        binding=selected_binding,
        deadline_monotonic=deadline,
    )
    supervisor = ConditionSessionSupervisor(
        server_endpoint,
        observer,
        accounting_document=boundary.accounting_document,
    )
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(supervisor.serve)
    port = DuplexSupervisorPort(
        client_endpoint,
        remote_journal_path=tmp_path / "remote-event-journal.json",
    )
    return _Session(
        port=port,
        boundary=boundary,
        observer=observer,
        server_endpoint=server_endpoint,
        client_endpoint=client_endpoint,
        future=future,
        pool=pool,
        streams=(server_reader, server_writer, client_reader, client_writer),
        sockets=(left, right),
    )


def _request(role: ModelRole, *, input_tokens: int = 11) -> ProviderRequest:
    return ProviderRequest(
        role=role,
        model=SIRA_MODEL_REVISION,
        input_tokens=input_tokens,
        max_output_tokens=17,
        service_tier=SIRA_SERVICE_TIER,
        implicit_transport_retries=0,
    )


def _usage(*, input_tokens: int = 11) -> ProviderResponseUsage:
    return ProviderResponseUsage(
        input_tokens=input_tokens,
        cached_input_tokens=2,
        output_tokens=7,
        service_tier=SIRA_SERVICE_TIER,
    )


@pytest.mark.parametrize(
    ("run_id", "roles"),
    [
        (V16_PROVIDER_CONTRACT.run_ids[0], (ModelRole.DEFAULT, ModelRole.ACTOR)),
        (V16_PROVIDER_CONTRACT.run_ids[1], (ModelRole.WORLD_MODEL, ModelRole.CRITIC)),
    ],
)
def test_duplex_session_is_multicall_multirole_and_shared_accounted(
    tmp_path: Path,
    run_id: str,
    roles: tuple[ModelRole, ...],
) -> None:
    session = _open_session(tmp_path, binding=_binding(run_id=run_id))
    try:
        sends: list[str] = []
        for index, role in enumerate(roles, start=1):
            call_id = f"CALL-{index:04d}"

            def send(request: ProviderRequest, *, marker: str = call_id):
                sends.append(marker)
                return {"content": marker}, _usage(input_tokens=request.input_tokens)

            assert session.port.model_call(
                _request(role),
                send,
                before_send=None,
                call_id=call_id,
                logical_call_id=f"LOGICAL-{index:04d}",
                classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
            ) == {"content": call_id}
        actions: list[str] = []
        for index in range(2):
            action_id = f"ACTION-{index:04d}"
            session.port.browser_action(
                action_id=action_id,
                perform=lambda marker=action_id: actions.append(marker),
            )
        session.port.output_bytes(total_bytes=100)
        session.port.output_bytes(total_bytes=240)
        session.port.process_exit(exit_code=0)
        session.port.completion(completed=True, answer="retained answer", error="")
        session.port.raw_published(manifest_sha256="b" * 64, receipt_sha256="c" * 64)
        client_terminal = session.port.terminalize()
        server_terminal = session.future.result(timeout=5)
        assert sends == ["CALL-0001", "CALL-0002"]
        assert actions == ["ACTION-0000", "ACTION-0001"]
        assert session.boundary.condition_usage.model_call_attempts == 2
        assert session.boundary.condition_usage.browser_actions == 2
        assert session.boundary.condition_usage.output_bytes == 240
        assert session.observer.call_order == ["CALL-0001", "CALL-0002"]
        assert session.observer.action_order == actions
        assert client_terminal["authoritative_accounting"] is False
        assert (
            client_terminal["final_frame_chain_sha256"]
            == server_terminal.transcript_sha256
            == session.server_endpoint.frame_chain_sha256()
            == session.client_endpoint.frame_chain_sha256()
        )
        remote = json.loads((tmp_path / "remote-event-journal.json").read_text())
        assert remote["side"] == "remote-mirror"
        assert remote["frame_chain_sha256"] == server_terminal.remote_frame_chain_sha256
        assert remote["transcript_sha256"] == server_terminal.remote_journal_sha256
        assert [entry.frame.frame_sha256 for entry in session.server_endpoint.entries] == [
            entry.frame.frame_sha256 for entry in session.client_endpoint.entries
        ]
    finally:
        session.close()


def test_model_send_and_browser_action_wait_for_exact_shared_admission(tmp_path: Path) -> None:
    session = _open_session(tmp_path)
    try:
        order: list[str] = []
        session.port.model_call(
            _request(ModelRole.ENCODER),
            lambda request: (
                order.append("send") or "ok",
                _usage(input_tokens=request.input_tokens),
            ),
            before_send=lambda: order.append("remote-pre-send"),
            call_id="CALL-ADMISSION",
            logical_call_id="LOGICAL-ADMISSION",
            classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
        )
        session.port.browser_action(
            action_id="ACTION-ADMISSION",
            perform=lambda: order.append("browser"),
        )
        session.port.process_exit(exit_code=0)
        session.port.completion(completed=True, answer="ok", error="")
        session.port.raw_published(manifest_sha256="d" * 64, receipt_sha256="e" * 64)
        session.port.terminalize()
        session.future.result(timeout=5)
        event_types = [entry.frame.event_type for entry in session.client_endpoint.entries]
        assert event_types.index("model-call-admitted") < event_types.index("model-send-start")
        assert event_types.index("model-send-start") < event_types.index("model-response")
        assert event_types.index("browser-action-admitted") < event_types.index(
            "browser-action-complete"
        )
        assert order == ["remote-pre-send", "send", "browser"]
    finally:
        session.close()


@pytest.mark.parametrize(
    ("cap_change", "operation", "expected_effects"),
    [
        ({"max_model_call_attempts": 0}, "model", 0),
        ({"max_browser_actions": 0}, "browser", 0),
        ({"max_output_bytes": 10}, "output", 0),
        ({"max_total_tokens": 1}, "tokens", 0),
        ({"max_cost_usd": 0.0}, "cost", 0),
    ],
)
def test_shared_admission_rejects_before_remote_effect(
    tmp_path: Path,
    cap_change: dict[str, int | float],
    operation: str,
    expected_effects: int,
) -> None:
    session = _open_session(tmp_path, caps=_caps(**cap_change))
    effects: list[str] = []
    try:
        with pytest.raises((ProviderBudgetExceeded, RemoteBridgeError)):
            if operation in {"model", "tokens", "cost"}:
                session.port.model_call(
                    _request(ModelRole.DEFAULT),
                    lambda _request: (effects.append("model") or "never", _usage()),
                    before_send=None,
                    call_id=f"CALL-{operation.upper()}",
                    logical_call_id=f"LOGICAL-{operation.upper()}",
                    classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
                )
            elif operation == "browser":
                session.port.browser_action(
                    action_id="ACTION-REJECT",
                    perform=lambda: effects.append("browser"),
                )
            else:
                session.port.output_bytes(total_bytes=11)
        assert len(effects) == expected_effects
    finally:
        session.close()


@pytest.mark.parametrize(
    "disposition",
    [
        ProviderFailureDisposition.PROVIDER_ERROR,
        ProviderFailureDisposition.TRANSPORT_ERROR_KNOWN,
        ProviderFailureDisposition.OUTCOME_UNKNOWN,
    ],
)
def test_failure_dispositions_have_one_send_and_zero_retry(
    tmp_path: Path,
    disposition: ProviderFailureDisposition,
) -> None:
    session = _open_session(tmp_path)
    calls = 0

    class SendFailure(RuntimeError):
        pass

    def fail(_request: ProviderRequest):
        nonlocal calls
        calls += 1
        raise SendFailure("synthetic no-network failure")

    try:
        with pytest.raises((SendFailure, RemoteBridgeDisconnected)):
            session.port.model_call(
                _request(ModelRole.POLICY),
                fail,
                before_send=None,
                call_id=f"CALL-{disposition.value}",
                logical_call_id=f"LOGICAL-{disposition.value}",
                classify_failure=lambda _exc: disposition,
            )
        assert calls == 1
        assert session.boundary.condition_usage.model_call_attempts == 1
        if disposition is ProviderFailureDisposition.OUTCOME_UNKNOWN:
            assert session.boundary.unknown_outcomes == 1
        else:
            session.port.process_exit(exit_code=1)
            session.port.completion(completed=False, answer=None, error="typed failure")
            session.port.raw_published(manifest_sha256="f" * 64, receipt_sha256="1" * 64)
            session.port.terminalize()
            session.future.result(timeout=5)
    finally:
        session.close()


def test_response_without_usage_is_accounting_incomplete_and_unknown(tmp_path: Path) -> None:
    session = _open_session(tmp_path)
    try:
        with pytest.raises(ProviderResponseReceiptError):
            session.port.model_call(
                _request(ModelRole.MEMORY),
                lambda _request: ("response-known", cast(ProviderResponseUsage, object())),
                before_send=None,
                call_id="CALL-INCOMPLETE",
                logical_call_id="LOGICAL-INCOMPLETE",
                classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
            )
        assert session.boundary.unknown_outcomes == 1
        assert session.port.terminal_call_state("CALL-INCOMPLETE").terminal_state == (
            "response-accounting-incomplete"
        )
        session.port.process_exit(exit_code=1)
        session.port.completion(completed=False, answer=None, error="accounting incomplete")
        session.port.raw_published(manifest_sha256="2" * 64, receipt_sha256="3" * 64)
        session.port.terminalize()
        session.future.result(timeout=5)
    finally:
        session.close()


def test_frame_hash_payload_sequence_replay_and_cross_identity_are_rejected(
    tmp_path: Path,
) -> None:
    stream = (tmp_path / "empty").open("w+b")
    try:
        endpoint = FramedDuplexEndpoint(
            reader=stream,
            writer=stream,
            binding=_binding(),
            deadline_monotonic=time.monotonic() + 5,
        )
        first = ConditionBridgeFrame.create(
            _binding(),
            sequence_number=1,
            previous_frame_sha256="0" * 64,
            event_id="EVENT-1",
            event_type="condition-session-hello",
            payload={"value": 1},
        )
        endpoint._record("received", first, 1)
        with pytest.raises(RemoteBridgeReplay, match="sequence"):
            endpoint._record("received", first, 1)
        out_of_order = ConditionBridgeFrame.create(
            _binding(),
            sequence_number=3,
            previous_frame_sha256=first.frame_sha256,
            event_id="EVENT-3",
            event_type="completion",
            payload={"value": 3},
        )
        with pytest.raises(RemoteBridgeReplay, match="sequence"):
            endpoint._record("received", out_of_order, 1)
        wrong = ConditionBridgeFrame.create(
            replace(_binding(), evaluator_run_id="EVAL-WRONG"),
            sequence_number=2,
            previous_frame_sha256=first.frame_sha256,
            event_id="EVENT-2",
            event_type="completion",
            payload={"value": 2},
        )
        with pytest.raises(RemoteBridgeError, match="another condition"):
            endpoint._record("received", wrong, 1)

        raw = first.to_document()
        raw["payload"] = {"value": 2}
        with pytest.raises(RemoteBridgeError, match="hash changed"):
            ConditionBridgeFrame.from_document(raw)
        raw = first.to_document()
        raw["frame_sha256"] = "9" * 64
        with pytest.raises(RemoteBridgeError, match="hash changed"):
            ConditionBridgeFrame.from_document(raw)
    finally:
        stream.close()


def test_missing_shared_observer_cannot_admit_a_remote_provider_send(tmp_path: Path) -> None:
    left, right = socket.socketpair()
    client_reader = right.makefile("rb", buffering=0)
    client_writer = right.makefile("wb", buffering=0)
    endpoint = FramedDuplexEndpoint(
        reader=client_reader,
        writer=client_writer,
        binding=_binding(),
        deadline_monotonic=time.monotonic() + 0.1,
    )
    sends: list[str] = []
    try:
        with pytest.raises(RemoteBridgeDisconnected):
            DuplexSupervisorPort(
                endpoint,
                remote_journal_path=tmp_path / "unadmitted-journal.json",
            )
        assert sends == []
    finally:
        client_reader.close()
        client_writer.close()
        left.close()
        right.close()


def test_remote_client_source_has_no_authoritative_budget_boundary_construction() -> None:
    source = Path("src/giclab/harness/t09_runtime_admission.py").read_text(encoding="utf-8")
    duplex_source = source.split("class DuplexSupervisorPort", maxsplit=1)[1]
    assert "ProviderBudgetBoundary(" not in duplex_source
    assert '"authoritative_accounting": False' in duplex_source


def test_private_unix_socket_channel_is_identity_held_and_destroyed(
    short_tmp_path: Path,
) -> None:
    attempt = short_tmp_path / "attempt"
    attempt.mkdir(mode=0o700)
    supervisor_root = attempt / ".giclab-supervisor"
    supervisor_root.mkdir(mode=0o700)
    binding = _binding()
    transaction_identity = "4" * 64
    listener = PrivateConditionListener.create(
        supervisor_root=supervisor_root,
        attempt_root=attempt,
        binding=binding,
        transaction_root_identity=transaction_identity,
        deadline_monotonic=time.monotonic() + 10,
        remote_journal_relative_path="remote-mirror.json",
    )
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=condition_caps("reactive"),
    )
    observer = _AccountingObserver(
        run_id=binding.condition_run_id,
        model_revision=SIRA_MODEL_REVISION,
        service_tier=SIRA_SERVICE_TIER,
        boundary=boundary,
        prior_call_ids=frozenset(),
        prior_logical_call_ids=frozenset(),
        clock=_ValidatedRuntimeClock(_ClockSource()),
        campaign_deadline_monotonic=time.monotonic() + 10,
    )
    pool = ThreadPoolExecutor(max_workers=1)

    def serve() -> tuple[ConditionSessionTerminalReceipt, AcceptedPrivateConditionChannel]:
        channel = listener.accept()
        try:
            receipt = ConditionSessionSupervisor(
                channel.endpoint,
                observer,
                accounting_document=boundary.accounting_document,
            ).serve()
            return receipt, channel
        except BaseException:
            channel.close()
            raise

    future = pool.submit(serve)
    port = build_private_socket_supervisor_port(
        manifest_path=listener.manifest_path,
        attempt_root=attempt,
        expected_binding=binding,
        expected_transaction_root_identity=transaction_identity,
    )
    channel: AcceptedPrivateConditionChannel | None = None
    try:
        port.process_exit(exit_code=0)
        port.completion(completed=True, answer="local IPC answer", error="")
        port.raw_published(manifest_sha256="5" * 64, receipt_sha256="6" * 64)
        terminal = port.terminalize()
        receipt, channel = future.result(timeout=5)
        assert terminal["final_frame_chain_sha256"] == receipt.transcript_sha256
        assert listener.socket_path.stat().st_mode & 0o777 == 0o600
        assert listener.manifest_path.stat().st_mode & 0o777 == 0o600
        assert (attempt / "remote-mirror.json").is_file()
    finally:
        port.close()
        if channel is not None:
            channel.close()
        listener.close()
        pool.shutdown(wait=True, cancel_futures=True)
    assert not listener.socket_path.exists()
    assert not listener.manifest_path.exists()


def test_private_socket_binding_rejects_identity_mutation_before_connect(
    short_tmp_path: Path,
) -> None:
    attempt = short_tmp_path / "attempt"
    attempt.mkdir(mode=0o700)
    supervisor_root = attempt / ".giclab-supervisor"
    supervisor_root.mkdir(mode=0o700)
    listener = PrivateConditionListener.create(
        supervisor_root=supervisor_root,
        attempt_root=attempt,
        binding=_binding(),
        transaction_root_identity="7" * 64,
        deadline_monotonic=time.monotonic() + 10,
        remote_journal_relative_path="remote-mirror.json",
    )
    try:
        with pytest.raises(RemoteBridgeError, match="identity"):
            build_private_socket_supervisor_port(
                manifest_path=listener.manifest_path,
                attempt_root=attempt,
                expected_binding=replace(_binding(), evaluator_run_id="EVAL-MUTATED"),
                expected_transaction_root_identity="7" * 64,
            )
        with pytest.raises(RemoteBridgeError, match="identity"):
            build_private_socket_supervisor_port(
                manifest_path=listener.manifest_path,
                attempt_root=attempt,
                expected_binding=_binding(),
                expected_transaction_root_identity="8" * 64,
            )
    finally:
        listener.close()


def test_transparent_host_relay_defers_terminal_evidence_to_host(tmp_path: Path) -> None:
    binding = _binding()
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=_caps(),
    )
    observer = _AccountingObserver(
        run_id=binding.condition_run_id,
        model_revision=SIRA_MODEL_REVISION,
        service_tier=SIRA_SERVICE_TIER,
        boundary=boundary,
        prior_call_ids=frozenset(),
        prior_logical_call_ids=frozenset(),
        clock=_ValidatedRuntimeClock(_ClockSource()),
        campaign_deadline_monotonic=time.monotonic() + 30,
    )
    shared_server, relay_upstream = socket.socketpair()
    relay_downstream, runtime_client = socket.socketpair()
    shared_reader = shared_server.makefile("rb", buffering=0)
    shared_writer = shared_server.makefile("wb", buffering=0)
    relay_shared_reader = relay_upstream.makefile("rb", buffering=0)
    relay_shared_writer = relay_upstream.makefile("wb", buffering=0)
    relay_remote_reader = relay_downstream.makefile("rb", buffering=0)
    relay_remote_writer = relay_downstream.makefile("wb", buffering=0)
    runtime_reader = runtime_client.makefile("rb", buffering=0)
    runtime_writer = runtime_client.makefile("wb", buffering=0)
    deadline = time.monotonic() + 30
    shared_endpoint = FramedDuplexEndpoint(
        reader=shared_reader,
        writer=shared_writer,
        binding=binding,
        deadline_monotonic=deadline,
    )
    relay = CanonicalFrameRelay(
        remote_reader=relay_remote_reader,
        remote_writer=relay_remote_writer,
        shared_reader=relay_shared_reader,
        shared_writer=relay_shared_writer,
        binding=binding,
        deadline_monotonic=deadline,
    )
    pool = ThreadPoolExecutor(max_workers=2)
    supervisor_future = pool.submit(
        ConditionSessionSupervisor(
            shared_endpoint,
            observer,
            accounting_document=boundary.accounting_document,
        ).serve
    )
    relay_future = pool.submit(relay.serve, stop_after_runtime_detach=True)
    port = DuplexSupervisorPort(
        FramedDuplexEndpoint(
            reader=runtime_reader,
            writer=runtime_writer,
            binding=binding,
            deadline_monotonic=deadline,
        ),
        remote_journal_path=tmp_path / "container-event-journal.json",
    )
    try:
        sends: list[str] = []
        port.model_call(
            _request(ModelRole.ACTOR),
            lambda request: (
                sends.append("sent") or {"content": "relay response"},
                _usage(input_tokens=request.input_tokens),
            ),
            before_send=None,
            call_id="CALL-RELAY",
            logical_call_id="LOGICAL-RELAY",
            classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
        )
        detached = port.detach_runtime()
        prefix = relay_future.result(timeout=5)
        assert detached["host_evidence_pending"] is True
        assert prefix["runtime_detached"] is True
        assert observer.exit_code is None
        assert observer.completion_state is None
        assert observer.raw_publication is None
        relay_receipt = relay.finish_host_evidence(
            exit_code=0,
            completed=True,
            answer="host-derived answer",
            error="",
            raw_manifest_sha256="a" * 64,
            raw_receipt_sha256="b" * 64,
            remote_journal_bytes=cast(int, detached["remote_journal_bytes"]),
            remote_journal_file_sha256=cast(str, detached["remote_journal_file_sha256"]),
            remote_journal_sha256=cast(str, detached["remote_journal_sha256"]),
            remote_terminal_sequence=cast(int, detached["terminal_sequence"]),
            remote_terminal_frame_sha256=cast(str, detached["terminal_frame_sha256"]),
            remote_frame_chain_sha256=cast(str, detached["frame_chain_sha256"]),
        )
        terminal = supervisor_future.result(timeout=5)
        assert sends == ["sent"]
        assert observer.exit_code == 0
        assert observer.completion_state == (True, "host-derived answer", "")
        assert observer.raw_publication == ("a" * 64, "b" * 64)
        assert relay_receipt["terminal_acknowledged"] is True
        assert relay_receipt["admission_decisions_synthesized"] == 0
        assert terminal.transcript_sha256 == shared_endpoint.frame_chain_sha256()
        assert terminal.remote_journal_file_sha256 == detached["remote_journal_file_sha256"]
        assert terminal.remote_frame_chain_sha256 == detached["frame_chain_sha256"]
        shared_frames = [entry.frame.to_document() for entry in shared_endpoint.entries]
        relay_frames = [
            entry["frame"] for entry in cast(list[dict[str, object]], relay_receipt["frames"])
        ]
        assert relay_frames == shared_frames
    finally:
        port.close()
        for channel in (
            shared_server,
            relay_upstream,
            relay_downstream,
            runtime_client,
        ):
            with contextlib.suppress(OSError):
                channel.shutdown(socket.SHUT_RDWR)
        for stream in (
            shared_reader,
            shared_writer,
            relay_shared_reader,
            relay_shared_writer,
            relay_remote_reader,
            relay_remote_writer,
            runtime_reader,
            runtime_writer,
        ):
            stream.close()
        for channel in (
            shared_server,
            relay_upstream,
            relay_downstream,
            runtime_client,
        ):
            channel.close()
        pool.shutdown(wait=True, cancel_futures=True)


def _write_private_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(canonical_bytes(value))
    path.chmod(0o600)


def _complete_bridge_evidence(tmp_path: Path):
    transaction = tmp_path / "transaction"
    transaction.mkdir(mode=0o700)
    raw = transaction / "attempt" / "raw"
    raw.mkdir(parents=True, mode=0o700)
    binding = _binding()
    evidence = expected_condition_bridge_evidence(
        transaction_root=transaction,
        raw_root=raw,
        run_id=binding.condition_run_id,
    )
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=_caps(),
    )
    observer = _AccountingObserver(
        run_id=binding.condition_run_id,
        model_revision=SIRA_MODEL_REVISION,
        service_tier=SIRA_SERVICE_TIER,
        boundary=boundary,
        prior_call_ids=frozenset(),
        prior_logical_call_ids=frozenset(),
        clock=_ValidatedRuntimeClock(_ClockSource()),
        campaign_deadline_monotonic=time.monotonic() + 30,
    )
    shared_server, relay_upstream = socket.socketpair()
    relay_downstream, runtime_client = socket.socketpair()
    sockets = (shared_server, relay_upstream, relay_downstream, runtime_client)
    streams = (
        shared_server.makefile("rb", buffering=0),
        shared_server.makefile("wb", buffering=0),
        relay_upstream.makefile("rb", buffering=0),
        relay_upstream.makefile("wb", buffering=0),
        relay_downstream.makefile("rb", buffering=0),
        relay_downstream.makefile("wb", buffering=0),
        runtime_client.makefile("rb", buffering=0),
        runtime_client.makefile("wb", buffering=0),
    )
    deadline = time.monotonic() + 30
    shared_endpoint = FramedDuplexEndpoint(
        reader=streams[0],
        writer=streams[1],
        binding=binding,
        deadline_monotonic=deadline,
    )
    relay = CanonicalFrameRelay(
        remote_reader=streams[4],
        remote_writer=streams[5],
        shared_reader=streams[2],
        shared_writer=streams[3],
        binding=binding,
        deadline_monotonic=deadline,
    )
    pool = ThreadPoolExecutor(max_workers=2)
    supervisor_future = pool.submit(
        ConditionSessionSupervisor(
            shared_endpoint,
            observer,
            accounting_document=boundary.accounting_document,
        ).serve
    )
    relay_future = pool.submit(relay.serve, stop_after_runtime_detach=True)
    port = DuplexSupervisorPort(
        FramedDuplexEndpoint(
            reader=streams[6],
            writer=streams[7],
            binding=binding,
            deadline_monotonic=deadline,
        ),
        remote_journal_path=evidence.remote_journal_path,
    )
    raw_manifest_sha = "a" * 64
    raw_receipt_sha = "b" * 64
    try:
        port.model_call(
            _request(ModelRole.ACTOR),
            lambda request: ("bridge answer", _usage(input_tokens=request.input_tokens)),
            before_send=None,
            call_id="CALL-EVIDENCE",
            logical_call_id="LOGICAL-EVIDENCE",
            classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
        )
        port.browser_action(action_id="ACTION-EVIDENCE", perform=lambda: None)
        port.output_bytes(total_bytes=256)
        detached = port.detach_runtime()
        prefix = relay_future.result(timeout=5)
        _write_private_json(evidence.runtime_detachment_path, detached)
        _write_private_json(evidence.relay_prefix_path, prefix)
        final = relay.finish_host_evidence(
            exit_code=0,
            completed=True,
            answer="bridge answer",
            error="",
            raw_manifest_sha256=raw_manifest_sha,
            raw_receipt_sha256=raw_receipt_sha,
            remote_journal_bytes=cast(int, detached["remote_journal_bytes"]),
            remote_journal_file_sha256=cast(str, detached["remote_journal_file_sha256"]),
            remote_journal_sha256=cast(str, detached["remote_journal_sha256"]),
            remote_terminal_sequence=cast(int, detached["terminal_sequence"]),
            remote_terminal_frame_sha256=cast(str, detached["terminal_frame_sha256"]),
            remote_frame_chain_sha256=cast(str, detached["frame_chain_sha256"]),
        )
        terminal = supervisor_future.result(timeout=5)
        _write_private_json(
            evidence.shared_transcript_path,
            shared_endpoint.transcript_document(side="shared-authoritative"),
        )
        _write_private_json(evidence.relay_transcript_path, final)
        _write_private_json(evidence.shared_terminal_receipt_path, terminal.to_document())
        remote_bytes = evidence.remote_journal_path.read_bytes()
        remote_document = json.loads(remote_bytes)
        host_terminal = {
            "schema_version": "1.0.0",
            "binding": binding.to_document(),
            "runtime_prefix_transcript_sha256": prefix["transcript_sha256"],
            "remote_event_journal_file_sha256": hashlib.sha256(remote_bytes).hexdigest(),
            "remote_event_journal_semantic_sha256": remote_document["transcript_sha256"],
            "relay_transcript_sha256": final["transcript_sha256"],
            "terminal_sequence": final["terminal_sequence"],
            "terminal_frame_sha256": final["terminal_frame_sha256"],
            "raw_manifest_sha256": raw_manifest_sha,
            "raw_receipt_sha256": raw_receipt_sha,
            "shared_accounting_owner": "ConditionEventObserver",
            "remote_authoritative_boundary": False,
            "terminal_acknowledged": True,
        }
        host_terminal["receipt_sha256"] = semantic_sha256(host_terminal)
        _write_private_json(evidence.host_terminal_receipt_path, host_terminal)
        return (
            transaction,
            binding,
            evidence,
            boundary.accounting_document(),
            raw_manifest_sha,
            raw_receipt_sha,
        )
    finally:
        port.close()
        for channel in sockets:
            with contextlib.suppress(OSError):
                channel.shutdown(socket.SHUT_RDWR)
        for stream in streams:
            stream.close()
        for channel in sockets:
            channel.close()
        pool.shutdown(wait=True, cancel_futures=True)


def test_complete_bridge_evidence_cross_binds_all_three_transcripts(
    tmp_path: Path,
) -> None:
    (
        _transaction,
        binding,
        evidence,
        accounting,
        raw_manifest_sha,
        raw_receipt_sha,
    ) = _complete_bridge_evidence(tmp_path)
    validated = validate_condition_bridge_evidence(
        Path.cwd(),
        evidence,
        expected_binding=binding,
        raw_manifest_sha256=raw_manifest_sha,
        raw_receipt_sha256=raw_receipt_sha,
        shared_accounting=accounting,
    )
    assert validated.frame_count > validated.runtime_prefix_frame_count
    assert validated.remote_journal_sha256
    assert validated.evidence_binding_sha256


def test_bridge_transcript_mutation_blocks_acceptance(tmp_path: Path) -> None:
    (
        _transaction,
        binding,
        evidence,
        accounting,
        raw_manifest_sha,
        raw_receipt_sha,
    ) = _complete_bridge_evidence(tmp_path)
    relay = json.loads(evidence.relay_transcript_path.read_text())
    relay["frames"][2]["frame"]["payload"]["call_id"] = "CALL-MUTATED"
    _write_private_json(evidence.relay_transcript_path, relay)
    with pytest.raises(RemoteBridgeError):
        validate_condition_bridge_evidence(
            Path.cwd(),
            evidence,
            expected_binding=binding,
            raw_manifest_sha256=raw_manifest_sha,
            raw_receipt_sha256=raw_receipt_sha,
            shared_accounting=accounting,
        )
