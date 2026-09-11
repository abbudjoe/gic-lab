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
    condition_call_id,
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
    require_journal_admission: bool = False,
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
    try:
        port = DuplexSupervisorPort(
            client_endpoint,
            remote_journal_path=tmp_path / "remote-event-journal.json",
            require_journal_admission=require_journal_admission,
        )
    except BaseException:
        for channel in (left, right):
            with contextlib.suppress(OSError):
                channel.shutdown(socket.SHUT_RDWR)
        for stream in (server_reader, server_writer, client_reader, client_writer):
            stream.close()
        left.close()
        right.close()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
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
            call_id = session.port.call_identity(index)

            def send(request: ProviderRequest, *, marker: str = call_id):
                sends.append(marker)
                return {"content": marker}, _usage(input_tokens=request.input_tokens)

            assert session.port.model_call(
                _request(role),
                send,
                before_send=None,
                call_id=call_id,
                logical_call_id=call_id,
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
        assert sends == [session.port.call_identity(1), session.port.call_identity(2)]
        assert actions == ["ACTION-0000", "ACTION-0001"]
        assert session.boundary.condition_usage.model_call_attempts == 2
        assert session.boundary.condition_usage.browser_actions == 2
        assert session.boundary.condition_usage.output_bytes == 240
        assert session.observer.call_order == [
            session.port.call_identity(1),
            session.port.call_identity(2),
        ]
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
            call_id=session.port.call_identity(1),
            logical_call_id=session.port.call_identity(1),
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
                    call_id=session.port.call_identity(1),
                    logical_call_id=session.port.call_identity(1),
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
                call_id=session.port.call_identity(1),
                logical_call_id=session.port.call_identity(1),
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
                call_id=session.port.call_identity(1),
                logical_call_id=session.port.call_identity(1),
                classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
            )
        assert session.boundary.unknown_outcomes == 1
        assert session.port.terminal_call_state(session.port.call_identity(1)).terminal_state == (
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


def test_private_unix_socket_channel_is_identity_held_and_destroyed(short_tmp_path: Path) -> None:
    _assert_private_unix_socket_channel(short_tmp_path)


def test_long_private_unix_socket_preserves_the_owned_evidence_location(
    short_tmp_path: Path,
) -> None:
    deep = short_tmp_path / ("evidence-" + "a" * 90)
    deep.mkdir(mode=0o700)
    if not Path("/proc/self/fd").is_dir():
        # The deployment path is Linux; unsupported hosts fail before binding.
        with pytest.raises(RemoteBridgeError, match="held-directory addressing"):
            _assert_private_unix_socket_channel(deep)
        assert not (deep / "attempt/.giclab-supervisor/condition-admission.sock").exists()
    else:
        _assert_private_unix_socket_channel(deep)


def _assert_private_unix_socket_channel(short_tmp_path: Path) -> None:
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
            call_id=port.call_identity(1),
            logical_call_id=port.call_identity(1),
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


def _complete_bridge_evidence(tmp_path: Path, *, output_case: str | None = None):
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
            call_id=port.call_identity(1),
            logical_call_id=port.call_identity(1),
            classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
        )
        port.browser_action(action_id="ACTION-EVIDENCE", perform=lambda: None)
        if output_case == "allowance-denied":
            with pytest.raises(RemoteBridgeError, match="rejected output allowance"):
                port.reserve_output_bytes(total_bytes=_caps().max_output_bytes + 1)
        elif output_case == "observed-denied":
            port.reserve_output_bytes(total_bytes=255)
            with pytest.raises(RemoteBridgeError, match="rejected output growth"):
                port.output_bytes(total_bytes=256)
        else:
            if output_case == "granted":
                port.reserve_output_bytes(total_bytes=256)
            port.output_bytes(total_bytes=256)
        detached = port.detach_runtime()
        prefix = relay_future.result(timeout=5)
        _write_private_json(evidence.runtime_detachment_path, detached)
        _write_private_json(evidence.relay_prefix_path, prefix)
        final = relay.finish_host_evidence(
            exit_code=1 if output_case in {"allowance-denied", "observed-denied"} else 0,
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


@pytest.mark.parametrize(
    "mutation", ["wrong-run", "wrong-session", "duplicate-sequence", "reused-logical"]
)
@pytest.mark.parametrize("peer", ["client", "supervisor"])
def test_remote_call_scope_is_checked_at_each_peer_before_send(tmp_path, mutation, peer):
    session = _open_session(tmp_path)
    try:
        binding = session.client_endpoint.binding
        call_id = condition_call_id(binding, 1)
        logical_id = call_id
        if mutation == "wrong-run":
            call_id = condition_call_id(_binding(run_id=V16_PROVIDER_CONTRACT.run_ids[1]), 1)
            logical_id = call_id
        elif mutation == "wrong-session":
            call_id = condition_call_id(replace(binding, session_id="SESSION-ANOTHER"), 1)
            logical_id = call_id
        elif mutation == "duplicate-sequence":
            call_id = condition_call_id(binding, 2)
            logical_id = call_id
        else:
            logical_id = condition_call_id(binding, 2)
        sends = []
        if peer == "client":
            count = len(session.client_endpoint.entries)
            with pytest.raises(RemoteBridgeReplay, match="session or sequence"):
                session.port.model_call(
                    _request(ModelRole.DEFAULT),
                    lambda request: (sends.append("sent") or "answer", _usage()),
                    before_send=None,
                    call_id=call_id,
                    logical_call_id=logical_id,
                    classify_failure=lambda exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
                )
            assert len(session.client_endpoint.entries) == count
        else:
            from giclab.control.remote_bridge import provider_request_document

            session.client_endpoint.write_event(
                event_id="invalid.reserve",
                event_type="model-call-reserve",
                payload={
                    "call_id": call_id,
                    "logical_call_id": logical_id,
                    "request": provider_request_document(_request(ModelRole.DEFAULT)),
                },
            )
            with pytest.raises(RemoteBridgeReplay, match="session or sequence"):
                session.future.result(timeout=2)
            assert not any(
                e.frame.event_type == "model-call-admitted" for e in session.server_endpoint.entries
            )
        assert sends == []
        assert session.boundary.condition_usage.model_call_attempts == 0
    finally:
        session.close()


def test_output_allowance_is_shared_and_distinct_from_observed_usage(tmp_path: Path) -> None:
    session = _open_session(tmp_path, caps=_caps(max_output_bytes=1024))
    try:
        session.port.reserve_output_bytes(total_bytes=1024)
        assert session.boundary.condition_usage.output_bytes == 0
        accounting = session.boundary.accounting_document()
        assert accounting["reserved_upper_bound"]["condition"]["output_bytes"] == 1024
        assert accounting["observed_lower_bound"]["condition"]["output_bytes"] == 0
        # Reconciliation of a model reservation cannot erase the output allowance.
        session.port.model_call(
            _request(ModelRole.ENCODER),
            lambda request: ("fixture answer", _usage(input_tokens=request.input_tokens)),
            before_send=None,
            call_id=session.port.call_identity(1),
            logical_call_id=session.port.call_identity(1),
            classify_failure=lambda _exc: ProviderFailureDisposition.OUTCOME_UNKNOWN,
        )
        assert (
            session.boundary.accounting_document()["outstanding_reservation_projection"][
                "condition"
            ]["output_bytes"]
            == 1024
        )
        session.port.output_bytes(total_bytes=1024)
        accounting = session.boundary.accounting_document()
        assert accounting["reserved_upper_bound"]["condition"]["output_bytes"] == 1024
        assert accounting["observed_lower_bound"]["condition"]["output_bytes"] == 1024
        assert accounting["outstanding_reservation_projection"]["condition"]["output_bytes"] == 0
        with pytest.raises(RemoteBridgeError, match="rejected output allowance"):
            session.port.reserve_output_bytes(total_bytes=1025)
        assert session.boundary.condition_usage.output_bytes == 1024
    finally:
        session.close()

    # A denial is terminal: use a separate session to test a forged mirror,
    # instead of resuming effects after the first session's terminal denial.
    other = tmp_path / "forged-mirror"
    other.mkdir(mode=0o700)
    session = _open_session(other, caps=_caps(max_output_bytes=1024))
    try:
        session.port.reserve_output_bytes(total_bytes=1024)
        session.port._output_allowance_total = 1025
        with pytest.raises(RemoteBridgeError, match="rejected output growth"):
            session.port.output_bytes(total_bytes=1025)
        assert session.boundary.condition_usage.output_bytes == 0
        assert (
            session.boundary.accounting_document()["reserved_upper_bound"]["condition"][
                "output_bytes"
            ]
            == 1024
        )
    finally:
        session.close()


def test_actual_event_writer_reconciles_exact_bytes_after_shared_grant(tmp_path: Path) -> None:
    from giclab.harness.t09_sira_pilot import EventWriter

    session = _open_session(tmp_path)
    path = tmp_path / "runtime-events.jsonl"
    writer = EventWriter(path, require_output_admission=True)
    observations = []

    def reserve(count):
        previous = session.port.condition_usage.output_bytes
        session.port.reserve_output_bytes(total_bytes=previous + count)
        observations.append((path.stat().st_size if path.exists() else 0, previous, count))
        assert session.boundary.condition_usage.output_bytes == previous

    writer.bind_output_admission(
        reserve_growth=reserve,
        observe_growth=lambda count: session.port.output_bytes(
            total_bytes=session.port.condition_usage.output_bytes + count
        ),
    )
    try:
        first = writer.append("fixture-answer", {"answer": "first"})
        second = writer.append("fixture-answer", {"answer": "different"}, parent_event_id=first)
        assert first != second
        assert len(observations) == 2
        assert all(before == previous for before, previous, _ in observations)
        size = path.stat().st_size
        assert size == sum(count for _, _, count in observations)
        assert session.port.condition_usage.output_bytes == size
        assert session.boundary.condition_observed_usage.output_bytes == size
        assert (
            session.boundary.accounting_document()["outstanding_reservation_projection"][
                "condition"
            ]["output_bytes"]
            == 0
        )
    finally:
        session.close()


def test_retained_bridge_releases_endpoint_before_raw_seal(short_tmp_path, monkeypatch):
    """Actual host bridge detaches its IPC before the strict raw inventory."""
    from types import SimpleNamespace

    from giclab.control.production import _host_module

    host = _host_module(Path.cwd())
    binding = _binding()
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        condition_caps=_caps(),
        aggregate_caps=aggregate_caps(),
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
    left, right = socket.socketpair()
    streams = tuple(
        channel.makefile(mode, buffering=0) for channel in (left, right) for mode in ("rb", "wb")
    )
    endpoint = FramedDuplexEndpoint(
        reader=streams[0],
        writer=streams[1],
        binding=binding,
        deadline_monotonic=time.monotonic() + 30,
    )
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(
        ConditionSessionSupervisor(
            endpoint, observer, accounting_document=boundary.accounting_document
        ).serve
    )
    raw = short_tmp_path / "attempt" / "raw"
    raw.mkdir(parents=True, mode=0o700)
    (raw / ".giclab-supervisor").mkdir(mode=0o700)
    monkeypatch.setattr(
        host,
        "sys",
        SimpleNamespace(
            stdin=SimpleNamespace(buffer=streams[2]),
            stdout=SimpleNamespace(buffer=streams[3]),
        ),
    )
    bridge = host._ConditionSessionBridge(
        request=SimpleNamespace(deadline_monotonic=time.monotonic() + 10),
        binding=binding,
        transaction_root_identity="b" * 64,
    )
    port = None
    try:
        bridge.prepare(raw)
        socket_path = bridge.listener.socket_path
        locator_path = bridge.listener.manifest_path
        port = build_private_socket_supervisor_port(
            manifest_path=locator_path,
            attempt_root=raw,
            expected_binding=binding,
            expected_transaction_root_identity="b" * 64,
        )
        port.output_bytes(total_bytes=0)
        detached = port.detach_runtime()
        _write_private_json(raw / "duplex-runtime-detached.json", dict(detached))
        port.close()
        assert bridge.quiesce_runtime() is True
        assert not socket_path.exists() and not locator_path.exists()
        files, total = host._raw_attempt_files(raw)
        assert files and total > 0
        manifest = raw.parent / "raw-attempt-manifest.json"
        receipt = raw.parent / "raw-attempt-complete.json"
        _write_private_json(manifest, {"files": files, "total_bytes": total})
        _write_private_json(
            receipt, {"manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}
        )
        bridge.finish(
            attempt_root=raw.parent,
            exit_code=0,
            completed=False,
            answer=None,
            error="",
            manifest_path=manifest,
            receipt_path=receipt,
        )
        assert future.result(timeout=5).terminal_acknowledged is True
        assert observer.completion_state == (False, None, "")
        assert host._raw_attempt_files(raw) == (files, total)
    finally:
        if port is not None:
            port.close()
        bridge.close()
        for channel in (left, right):
            with contextlib.suppress(OSError):
                channel.shutdown(socket.SHUT_RDWR)
        for stream in streams:
            stream.close()
        left.close()
        right.close()
        pool.shutdown(wait=True)


def test_retained_bridge_missing_runtime_cancels_before_raw_inventory(short_tmp_path):
    from types import SimpleNamespace

    from giclab.control.production import _host_module

    host = _host_module(Path.cwd())
    raw = short_tmp_path / "raw"
    raw.mkdir(mode=0o700)
    (raw / ".giclab-supervisor").mkdir(mode=0o700)
    bridge = host._ConditionSessionBridge(
        request=SimpleNamespace(deadline_monotonic=time.monotonic() + 30),
        binding=_binding(),
        transaction_root_identity="b" * 64,
    )
    start = time.monotonic()
    try:
        bridge.prepare(raw)
        assert bridge.quiesce_runtime() is False
        assert time.monotonic() - start < 3
        assert host._raw_attempt_files(raw) == ([], 0)
    finally:
        bridge.close()


@pytest.mark.parametrize("role", ["socket", "manifest", "parent"])
def test_private_listener_cleanup_preserves_replacement_evidence(short_tmp_path, role):
    attempt = short_tmp_path / "raw"
    root = attempt / ".giclab-supervisor"
    root.mkdir(parents=True, mode=0o700)
    listener = PrivateConditionListener.create(
        supervisor_root=root,
        attempt_root=attempt,
        binding=_binding(),
        transaction_root_identity="b" * 64,
        deadline_monotonic=time.monotonic() + 10,
        remote_journal_relative_path="duplex-remote-event-journal.json",
    )
    if role == "parent":
        root.rename(attempt / "original-supervisor")
        root.mkdir(mode=0o700)
        replacement = root / listener.socket_path.name
    else:
        replacement = listener.socket_path if role == "socket" else listener.manifest_path
        replacement.rename(replacement.with_name(replacement.name + ".original"))
    replacement.write_bytes(b"unrelated replacement evidence")
    replacement.chmod(0o600)
    with pytest.raises(RemoteBridgeError, match="replaced"):
        listener.close()
    assert replacement.read_bytes() == b"unrelated replacement evidence"
    assert listener.listener.fileno() == -1


@pytest.mark.parametrize("replaced_role", [None, "socket", "manifest", "parent"])
def test_private_listener_failed_creation_preserves_replacement_evidence(
    short_tmp_path, monkeypatch, replaced_role
):
    import os

    attempt = short_tmp_path / "raw"
    root = attempt / ".giclab-supervisor"
    root.mkdir(parents=True, mode=0o700)
    manifest = root / "condition-admission-binding.json"
    socket_path = root / "condition-admission.sock"
    replacement = None
    created_sockets = []
    original_socket = socket.socket

    def tracked_socket(*args, **kwargs):
        value = original_socket(*args, **kwargs)
        created_sockets.append(value)
        return value

    def fail_manifest_write(_fd, _body):
        nonlocal replacement
        if replaced_role == "parent":
            root.rename(attempt / "preserved-original-root")
            root.mkdir(mode=0o700)
            replacement = manifest
        elif replaced_role is not None:
            replacement = manifest if replaced_role == "manifest" else socket_path
            replacement.rename(replacement.with_suffix(".preserved-original"))
        if replacement is not None:
            replacement.write_bytes(b"unrelated replacement evidence")
            replacement.chmod(0o600)
        raise OSError("injected binding publication interruption")

    monkeypatch.setattr(socket, "socket", tracked_socket)
    monkeypatch.setattr(os, "write", fail_manifest_write)
    with pytest.raises((OSError, RemoteBridgeError)):
        PrivateConditionListener.create(
            supervisor_root=root,
            attempt_root=attempt,
            binding=_binding(),
            transaction_root_identity="b" * 64,
            deadline_monotonic=time.monotonic() + 10,
            remote_journal_relative_path="duplex-remote-event-journal.json",
        )
    assert created_sockets and all(value.fileno() == -1 for value in created_sockets)
    if replacement is not None:
        assert replacement.exists(), "failed creation deleted unrelated replacement evidence"
        assert replacement.read_bytes() == b"unrelated replacement evidence"
    else:
        assert not os.path.lexists(manifest) and not os.path.lexists(socket_path)


@pytest.mark.parametrize("output_case", ["granted", "allowance-denied", "observed-denied"])
def test_output_admission_transcript_preserves_grant_or_terminal_denial(tmp_path, output_case):
    _, binding, evidence, accounting, manifest_sha, receipt_sha = _complete_bridge_evidence(
        tmp_path, output_case=output_case
    )
    validated = validate_condition_bridge_evidence(
        Path.cwd(),
        evidence,
        expected_binding=binding,
        raw_manifest_sha256=manifest_sha,
        raw_receipt_sha256=receipt_sha,
        shared_accounting=accounting,
    )
    assert validated.frame_count > validated.runtime_prefix_frame_count
    document = json.loads(evidence.shared_transcript_path.read_bytes())
    kinds = [entry["frame"]["event_type"] for entry in document["frames"]]
    assert "output-allowance-request" in kinds
    if output_case == "granted":
        assert "output-allowance-granted" in kinds and "output-bytes-admitted" in kinds
    else:
        assert (
            "output-allowance-rejected"
            if output_case == "allowance-denied"
            else "output-bytes-rejected"
        ) in kinds
        exits = [
            entry["frame"]["payload"]["exit_code"]
            for entry in document["frames"]
            if entry["frame"]["event_type"] == "process-exit"
        ]
        assert exits == [1]


@pytest.mark.parametrize(
    "later_type",
    [
        "model-call-reserve",
        "browser-action-reserve",
        "output-allowance-request",
        "output-bytes-update",
    ],
)
def test_output_denial_blocks_later_activity_before_shared_reservation(tmp_path, later_type):
    from giclab.control.remote_bridge import provider_request_document

    session = _open_session(tmp_path, caps=_caps(max_output_bytes=10))
    try:
        with pytest.raises(RemoteBridgeError, match="rejected output allowance"):
            session.port.reserve_output_bytes(total_bytes=11)
        payload = {"total_bytes": 1}
        if later_type == "model-call-reserve":
            call_id = session.port.call_identity(1)
            payload = {
                "call_id": call_id,
                "logical_call_id": call_id,
                "request": provider_request_document(_request(ModelRole.DEFAULT)),
            }
        elif later_type == "browser-action-reserve":
            payload = {"action_id": "ACTION-LATE"}
        session.client_endpoint.write_event(
            event_id="late-request", event_type=later_type, payload=payload
        )
        with pytest.raises(RemoteBridgeError, match="activity after denied output"):
            session.future.result(timeout=2)
        assert session.observer.call_ids == set()
        assert session.observer.action_ids == set()
        assert session.observer.output_total_bytes is None
        assert session.boundary.condition_usage.model_call_attempts == 0
        assert session.boundary.condition_usage.browser_actions == 0
    finally:
        session.close()


def test_r6_runtime_json_and_event_reservations_do_not_reuse_unobserved_capacity(tmp_path):
    from giclab.harness.sira_gate_a_runtime import _write_json_evidence
    from giclab.harness.t09_sira_pilot import EventWriter

    session = _open_session(tmp_path)
    try:
        document = tmp_path / "runtime-evidence.json"
        _write_json_evidence(
            document,
            {"answer": "actual fixture value"},
            reserve_temporary_bytes=session.port.reserve_output_growth,
            require_output_admission=True,
        )
        first_size = document.stat().st_size
        assert session.observer.output_total_bytes is None
        first = session.boundary.accounting_document()["reserved_upper_bound"]["condition"]
        assert first["output_bytes"] == first_size
        writer = EventWriter(tmp_path / "events.jsonl", require_output_admission=True)
        writer.bind_output_admission(
            reserve_growth=session.port.reserve_output_growth,
            observe_growth=lambda count: session.port.output_bytes(total_bytes=count),
        )
        writer.append("actual-event", {"source": "writer"})
        event_size = writer.path.stat().st_size
        assert session.observer.output_total_bytes == event_size
        reserved = session.boundary.accounting_document()["reserved_upper_bound"]["condition"]
        assert reserved["output_bytes"] == first_size + event_size
        # Replacing with fewer bytes still requires a separate full temporary
        # allocation; neither the old grant nor the event observation supplies it.
        _write_json_evidence(
            document,
            {},
            reserve_temporary_bytes=session.port.reserve_output_growth,
            require_output_admission=True,
        )
        assert document.read_bytes() == b"{}\n"
        reserved = session.boundary.accounting_document()["reserved_upper_bound"]["condition"]
        assert reserved["output_bytes"] == first_size + event_size + 3
        assert session.observer.output_total_bytes == event_size
    finally:
        session.close()


def test_r6_runtime_json_denied_shared_increment_does_not_create_file(tmp_path):
    from giclab.harness.sira_gate_a_runtime import _write_json_evidence

    session = _open_session(tmp_path, caps=_caps(max_output_bytes=100))
    try:
        session.port.reserve_output_growth(100)
        destination = tmp_path / "denied.json"
        with pytest.raises(RemoteBridgeError, match="rejected output allowance"):
            _write_json_evidence(
                destination,
                {"denied": "not written"},
                reserve_temporary_bytes=session.port.reserve_output_growth,
                require_output_admission=True,
            )
        assert not destination.exists()
        assert not list(tmp_path.glob("denied.*.tmp"))
        assert session.observer.output_total_bytes is None
        assert (
            session.boundary.accounting_document()["reserved_upper_bound"]["condition"][
                "output_bytes"
            ]
            == 100
        )
    finally:
        session.close()


def test_r6_terminal_json_consumes_prefunded_bytes_after_shared_denial(tmp_path):
    from giclab.harness.sira_gate_a import GateAContractError
    from giclab.harness.sira_gate_a_runtime import (
        _reserve_terminal_publications,
        _write_json_evidence,
    )

    session = _open_session(tmp_path, caps=_caps(max_output_bytes=100))
    try:
        consume = _reserve_terminal_publications(session.port, capacity=100)
        with pytest.raises(RemoteBridgeError, match="rejected output allowance"):
            session.port.reserve_output_growth(1)
        frame_count = len(session.client_endpoint.entries)
        path = tmp_path / "terminal.json"
        _write_json_evidence(
            path,
            {"terminal": "bounded"},
            reserve_temporary_bytes=consume,
            require_output_admission=True,
        )
        first_size = path.stat().st_size
        assert 0 < first_size < 100
        # No new protocol grant after denial, and no local allowance extension.
        assert len(session.client_endpoint.entries) == frame_count
        with pytest.raises(GateAContractError, match="allowance exhausted"):
            _write_json_evidence(
                tmp_path / "excess.json",
                {"denied": "x" * 100},
                reserve_temporary_bytes=consume,
                require_output_admission=True,
            )
        assert not (tmp_path / "excess.json").exists()
        assert not list(tmp_path.glob("excess.*.tmp"))
        assert path.stat().st_size == first_size
        assert session.observer.output_total_bytes is None
        assert (
            session.boundary.accounting_document()["reserved_upper_bound"]["condition"][
                "output_bytes"
            ]
            == 100
        )
        assert len(session.client_endpoint.entries) == frame_count
    finally:
        session.close()


def test_r6_shared_census_cannot_consume_unspent_terminal_allocation(tmp_path):
    from giclab.harness.sira_gate_a_runtime import _reserve_terminal_publications

    session = _open_session(tmp_path, caps=_caps(max_output_bytes=200))
    try:
        terminal = _reserve_terminal_publications(session.port, capacity=100)
        session.port.reserve_output_growth(20)
        assert terminal.remaining == 100
        with pytest.raises(RemoteBridgeError, match="rejected output growth"):
            session.port.output_bytes(total_bytes=21, retained_output_bytes=terminal.remaining)
        assert session.observer.output_total_bytes is None
        assert session.boundary.condition_observed_usage.output_bytes == 0
        assert terminal.remaining == 100
        assert (
            session.boundary.accounting_document()["reserved_upper_bound"]["condition"][
                "output_bytes"
            ]
            == 120
        )
    finally:
        session.close()


def test_r6_shared_census_accepts_only_consumed_terminal_capacity(tmp_path):
    from giclab.harness.sira_gate_a_runtime import (
        _reserve_terminal_publications,
        _write_json_evidence,
    )

    session = _open_session(tmp_path, caps=_caps(max_output_bytes=200))
    try:
        terminal = _reserve_terminal_publications(session.port, capacity=100)
        path = tmp_path / "terminal.json"
        _write_json_evidence(
            path, {}, reserve_temporary_bytes=terminal, require_output_admission=True
        )
        assert path.read_bytes() == b"{}\n"
        assert terminal.remaining == 97
        session.port.output_bytes(total_bytes=3, retained_output_bytes=terminal.remaining)
        assert session.observer.output_total_bytes == 3
        assert session.boundary.condition_observed_usage.output_bytes == 3
        assert (
            session.boundary.accounting_document()["reserved_upper_bound"]["condition"][
                "output_bytes"
            ]
            == 100
        )
    finally:
        session.close()


def test_r6_journal_bootstrap_denial_creates_no_output(tmp_path):
    with pytest.raises(RemoteBridgeError, match="rejected output allowance"):
        _open_session(tmp_path, caps=_caps(max_output_bytes=100), require_journal_admission=True)
    assert list(tmp_path.iterdir()) == []


def test_r6_journal_allocates_before_first_write_and_retains_unused_capacity(tmp_path):
    session = _open_session(tmp_path, require_journal_admission=True)
    try:
        path = session.port.remote_journal_path
        document = json.loads(path.read_bytes())
        kinds = [row["frame"]["event_type"] for row in document["frames"]]
        assert kinds == [
            "condition-session-hello",
            "condition-session-accepted",
            "output-allowance-request",
            "output-allowance-granted",
        ]
        allocated = session.boundary.accounting_document()["reserved_upper_bound"]["condition"][
            "output_bytes"
        ]
        assert allocated == path.stat().st_size + session.port.retained_journal_bytes
        assert session.observer.output_total_bytes is None
        old_size = path.stat().st_size
        session.port.output_bytes(total_bytes=old_size)
        assert session.observer.output_total_bytes == old_size
        assert (
            session.boundary.accounting_document()["reserved_upper_bound"]["condition"][
                "output_bytes"
            ]
            == allocated
        )
        assert path.stat().st_size > old_size
    finally:
        session.close()


def test_r6_journal_overgrowth_cannot_extend_its_allocation(tmp_path):
    session = _open_session(tmp_path, require_journal_admission=True)
    try:
        path = session.port.remote_journal_path
        before = path.read_bytes()
        frames = len(session.client_endpoint.entries)
        allocated = session.boundary.accounting_document()["reserved_upper_bound"]["condition"][
            "output_bytes"
        ]
        oversized = {"untrusted_member": "x" * allocated}
        with pytest.raises(RemoteBridgeError, match="preadmitted temporary capacity"):
            session.port._persist_journal(oversized)
        assert path.read_bytes() == before
        assert not (tmp_path / ("." + path.name + ".tmp")).exists()
        assert len(session.client_endpoint.entries) == frames
        assert (
            session.boundary.accounting_document()["reserved_upper_bound"]["condition"][
                "output_bytes"
            ]
            == allocated
        )
    finally:
        session.close()


@pytest.mark.parametrize("peer", ["client", "supervisor"])
def test_same_session_completed_call_cannot_reenter_either_peer(tmp_path, peer):
    """Replay an actually completed call; keep its authoritative history intact."""
    from giclab.control.remote_bridge import provider_request_document

    session = _open_session(tmp_path)
    sends = []
    try:
        call_id = session.port.call_identity(1)
        request = _request(ModelRole.DEFAULT)
        answer = session.port.model_call(
            request,
            lambda _: (sends.append("one actual fixture send") or "answer", _usage()),
            before_send=None,
            call_id=call_id,
            logical_call_id=call_id,
            classify_failure=lambda _: ProviderFailureDisposition.OUTCOME_UNKNOWN,
        )
        assert answer == "answer" and session.boundary.condition_usage.model_call_attempts == 1
        before = session.boundary.accounting_document()
        admitted = sum(
            e.frame.event_type == "model-call-admitted" for e in session.server_endpoint.entries
        )
        if peer == "client":
            frames = len(session.client_endpoint.entries)
            with pytest.raises(RemoteBridgeError, match="reused"):
                session.port.model_call(
                    request,
                    lambda _: (sends.append("forbidden replay") or "wrong", _usage()),
                    before_send=None,
                    call_id=call_id,
                    logical_call_id=call_id,
                    classify_failure=lambda _: ProviderFailureDisposition.OUTCOME_UNKNOWN,
                )
            assert len(session.client_endpoint.entries) == frames
        else:
            session.client_endpoint.write_event(
                event_id="negative.completed-call-replay",
                event_type="model-call-reserve",
                payload={
                    "call_id": call_id,
                    "logical_call_id": call_id,
                    "request": provider_request_document(request),
                },
            )
            with pytest.raises(RemoteBridgeReplay):
                session.future.result(timeout=2)
        assert sends == ["one actual fixture send"]
        assert session.boundary.accounting_document() == before
        assert (
            sum(
                e.frame.event_type == "model-call-admitted" for e in session.server_endpoint.entries
            )
            == admitted
            == 1
        )
    finally:
        session.close()
