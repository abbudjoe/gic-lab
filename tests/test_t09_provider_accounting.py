from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import math
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from giclab.harness.sira_gate_a import (
    SIRA_MODEL_REVISION,
    GateAContractError,
    ImmutableModelRouting,
    ModelRole,
    ProviderBudgetBoundary,
    ProviderBudgetExceeded,
    ProviderBudgetUsage,
    ProviderCallPhase,
    ProviderCallTerminalState,
    ProviderFailureDisposition,
    ProviderRequest,
    ProviderResponseReceiptError,
    ProviderResponseUsage,
    aggregate_caps,
    condition_caps,
)
from giclab.harness.sira_gate_a_runtime import _install_locked_llm_factory
from giclab.harness.t09_pragmatic_provider import (
    AUTONOMOUS_V9_LAUNCH_PACKAGE_COMMIT,
    AUTONOMOUS_V9_STALE_COMMAND_AUTHORIZATION_SHA256S,
    T09ProviderError,
    _autonomous_package_science_state,
)
from giclab.harness.t09_provider_contracts import V8_PROVIDER_CONTRACT, V9_PROVIDER_CONTRACT
from giclab.registry import load_json

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
ADJUDICATION = EXP / "T09_AUTONOMOUS_V8_PROVIDER_CALL_ADJUDICATION.json"
V8_DISPOSITION = EXP / "T09_AUTONOMOUS_PILOT_DISPOSITION.json"


class RateLimitError(RuntimeError):
    pass


def _boundary(**condition_overrides: int | float) -> ProviderBudgetBoundary:
    condition = replace(condition_caps("simulative"), **condition_overrides)
    aggregate = replace(aggregate_caps(), **condition_overrides)
    return ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        condition_caps=condition,
        aggregate_caps=aggregate,
    )


def _request(*, input_tokens: int = 10, output_tokens: int = 20) -> ProviderRequest:
    return ProviderRequest(
        role=ModelRole.CRITIC,
        model=SIRA_MODEL_REVISION,
        input_tokens=input_tokens,
        max_output_tokens=output_tokens,
    )


def _success(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
    return "ok", ProviderResponseUsage(10, 2, 4, "default")


def _known_provider(_: BaseException) -> ProviderFailureDisposition:
    return ProviderFailureDisposition.PROVIDER_ERROR


def test_01_thirty_responses_and_three_provider_errors_are_terminal() -> None:
    boundary = _boundary()
    sends: list[str] = []

    def successful_send(request: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        sends.append("success")
        return _success(request)

    for index in range(30):
        boundary.invoke(
            _request(),
            successful_send,
            call_id=f"CALL-{index:04d}",
            logical_call_id=f"LOGICAL-{index:04d}",
        )
    for index in range(30, 33):

        def rate_limited(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
            sends.append("provider-error")
            raise RateLimitError("synthetic")

        with pytest.raises(RateLimitError):
            boundary.invoke(
                _request(),
                rate_limited,
                call_id=f"CALL-{index:04d}",
                logical_call_id=f"LOGICAL-{index:04d}",
                classify_failure=_known_provider,
            )
    document = boundary.accounting_document()
    assert document["unreconciled_provider_attempts"] == 0
    assert document["unknown_outcomes"] == 0
    assert document["terminal_counts"] == {
        "admitted_not_sent": 0,
        "sent_response_reconciled": 30,
        "sent_provider_error_reconciled": 3,
        "sent_transport_error_known": 0,
        "sent_outcome_unknown": 0,
    }
    assert sends == [*(["success"] * 30), *(["provider-error"] * 3)]
    assert len(boundary.call_records) == 33
    assert len({record.call_id for record in boundary.call_records}) == 33
    assert len({record.logical_call_id for record in boundary.call_records}) == 33
    assert all(record.terminal_state is not None for record in boundary.call_records)
    assert all(
        record.history.count(ProviderCallPhase.SEND_STARTED.value) == 1
        for record in boundary.call_records
    )
    assert all(
        record.history.count(ProviderCallPhase.RESERVATION_RELEASED.value) == 1
        for record in boundary.call_records
    )
    assert all(
        record.history.count(ProviderCallPhase.CALL_TERMINAL.value) == 1
        for record in boundary.call_records
    )


def test_02_thirty_responses_and_three_unknowns_retain_upper_bounds() -> None:
    boundary = _boundary()
    for index in range(30):
        boundary.invoke(_request(), _success, call_id=f"CALL-{index:04d}")
    for index in range(30, 33):
        with pytest.raises(TimeoutError):
            boundary.invoke(
                _request(),
                lambda _: (_ for _ in ()).throw(TimeoutError("synthetic")),
                call_id=f"CALL-{index:04d}",
            )
    document = boundary.accounting_document()
    lower = document["observed_lower_bound"]["condition"]
    upper = document["reserved_upper_bound"]["condition"]
    assert document["unknown_outcomes"] == 3
    assert lower["total_tokens"] == 420
    assert upper["total_tokens"] == 510


def test_03_received_response_with_usage_failure_is_typed_unknown() -> None:
    boundary = _boundary()
    error = ProviderResponseReceiptError("synthetic receipt failure")
    with pytest.raises(ProviderResponseReceiptError):
        boundary.invoke(_request(), lambda _: (_ for _ in ()).throw(error))
    record = boundary.call_records[0]
    assert ProviderCallPhase.RESPONSE_RECEIVED.value in record.history
    assert record.terminal_state is ProviderCallTerminalState.OUTCOME_UNKNOWN


def test_04_process_stop_terminalizes_in_flight_send() -> None:
    boundary = _boundary()
    entered = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []

    def send(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        entered.set()
        release.wait(timeout=2)
        return _success(_request())

    def worker() -> None:
        try:
            boundary.invoke(_request(), send)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(timeout=2)
    boundary.close_in_flight(grace_seconds=0)
    assert boundary.call_records[0].terminal_state is ProviderCallTerminalState.OUTCOME_UNKNOWN
    release.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert len(errors) == 1


def test_05_concurrent_reservations_are_atomic() -> None:
    boundary = _boundary(max_total_tokens=50, max_input_tokens=25, max_output_tokens=25)
    entered = threading.Event()
    release = threading.Event()

    def slow(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        entered.set()
        release.wait(timeout=2)
        return "ok", ProviderResponseUsage(10, 0, 1, "default")

    thread = threading.Thread(target=lambda: boundary.invoke(_request(), slow))
    thread.start()
    assert entered.wait(timeout=2)
    with pytest.raises(ProviderBudgetExceeded):
        boundary.invoke(_request(input_tokens=16, output_tokens=6), _success)
    release.set()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_06_call_cap_admission_is_atomic() -> None:
    boundary = _boundary(max_model_call_attempts=1)
    boundary.invoke(_request(), _success)
    with pytest.raises(ProviderBudgetExceeded, match="model_call_attempts"):
        boundary.invoke(_request(), _success)


def test_07_token_cap_admission_counts_proposed_reservation() -> None:
    boundary = _boundary(max_total_tokens=29, max_input_tokens=20, max_output_tokens=20)
    with pytest.raises(ProviderBudgetExceeded, match="total_tokens"):
        boundary.invoke(_request(), _success)
    assert boundary.call_records == ()


def test_08_cost_cap_admission_prices_full_reservation() -> None:
    boundary = _boundary(max_cost_usd=0.00001)
    with pytest.raises(ProviderBudgetExceeded, match="cost_usd"):
        boundary.invoke(_request(), _success)


def test_09_actual_usage_replaces_the_reservation() -> None:
    boundary = _boundary()
    boundary.invoke(_request(input_tokens=100, output_tokens=100), _success)
    document = boundary.accounting_document()
    assert document["outstanding_reservations"] == 0
    assert document["observed_lower_bound"] == document["reserved_upper_bound"]
    assert document["observed_lower_bound"]["condition"]["total_tokens"] == 14


def test_10_unknown_outcome_retains_conservative_reservation() -> None:
    boundary = _boundary()
    with pytest.raises(TimeoutError):
        boundary.invoke(
            _request(),
            lambda _: (_ for _ in ()).throw(TimeoutError("synthetic")),
        )
    document = boundary.accounting_document()
    assert document["observed_lower_bound"]["condition"]["total_tokens"] == 0
    assert document["reserved_upper_bound"]["condition"]["total_tokens"] == 30


def test_11_presend_failure_releases_without_counting_a_send() -> None:
    boundary = _boundary()
    sent = False

    def send(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        nonlocal sent
        sent = True
        return _success(_request())

    with pytest.raises(RuntimeError, match="presend"):
        boundary.invoke(
            _request(),
            send,
            before_send=lambda: (_ for _ in ()).throw(RuntimeError("presend")),
        )
    assert sent is False
    assert boundary.condition_usage.model_call_attempts == 0
    assert boundary.accounting_document()["outstanding_reservations"] == 0


def test_12_reservations_never_become_negative() -> None:
    boundary = _boundary()
    boundary.invoke(_request(), _success)
    document = boundary.accounting_document()
    for scope in ("condition", "aggregate"):
        assert all(value >= 0 for value in document["reserved_upper_bound"][scope].values())


def test_13_terminal_closeout_cannot_double_release() -> None:
    boundary = _boundary()
    boundary.invoke(_request(), _success)
    before = boundary.accounting_document()
    boundary.close_in_flight(grace_seconds=0)
    assert boundary.accounting_document() == before


def test_14_runtime_constructor_disables_sdk_retries() -> None:
    source = inspect.getsource(_install_locked_llm_factory)
    assert "num_retries=0" in source
    assert "implicit_transport_retries=0" in source


def test_15_second_send_for_one_logical_call_is_rejected() -> None:
    boundary = _boundary()
    boundary.invoke(_request(), _success, call_id="CALL-1", logical_call_id="LOGICAL-1")
    with pytest.raises(GateAContractError, match="second network send"):
        boundary.invoke(_request(), _success, call_id="CALL-2", logical_call_id="LOGICAL-1")


def test_16_bounded_flush_returns_after_completed_calls() -> None:
    boundary = _boundary()
    boundary.invoke(_request(), _success)
    boundary.close_in_flight(grace_seconds=0.1)
    assert boundary.unknown_outcomes == 0


def test_17_flush_timeout_produces_typed_unknown_state() -> None:
    boundary = _boundary()
    entered = threading.Event()
    release = threading.Event()

    def blocked(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        entered.set()
        release.wait(timeout=2)
        return _success(_request())

    thread = threading.Thread(target=lambda: pytest.raises(GateAContractError).__enter__())
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            boundary.invoke(_request(), blocked)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(timeout=2)
    boundary.close_in_flight(grace_seconds=0)
    assert boundary.call_records[0].terminal_state is ProviderCallTerminalState.OUTCOME_UNKNOWN
    release.set()
    thread.join(timeout=2)
    assert errors


def test_18_lower_and_upper_bounds_diverge_only_for_unknowns() -> None:
    boundary = _boundary()
    boundary.invoke(_request(), _success)
    with pytest.raises(TimeoutError):
        boundary.invoke(
            _request(),
            lambda _: (_ for _ in ()).throw(TimeoutError("synthetic")),
        )
    document = boundary.accounting_document()
    lower = document["observed_lower_bound"]["condition"]
    upper = document["reserved_upper_bound"]["condition"]
    assert lower["model_call_attempts"] == upper["model_call_attempts"] == 2
    assert lower["total_tokens"] == 14
    assert upper["total_tokens"] == 44


def test_19_essential_failure_allowlist_preserves_call_lifecycle() -> None:
    source = (ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py").read_text(
        encoding="utf-8"
    )
    assert source.count('"provider-call-lifecycle.json"') >= 2


def test_20_accounting_evidence_contains_no_exception_message_or_secret() -> None:
    boundary = _boundary()
    marker = "synthetic-private-marker"
    with pytest.raises(TimeoutError):
        boundary.invoke(
            _request(),
            lambda _: (_ for _ in ()).throw(TimeoutError(marker)),
        )
    encoded = json.dumps(boundary.accounting_document(), sort_keys=True)
    assert marker not in encoded
    assert "api_key" not in encoded.lower()


def test_21_v8_evidence_remains_immutable_and_invalid() -> None:
    assert hashlib.sha256(V8_DISPOSITION.read_bytes()).hexdigest() == (
        "af80ad17feac4f15dee690f9e6f3aa77de8d5d5ad533416603719e03f7700f7a"
    )
    adjudication = load_json(ADJUDICATION)
    assert adjudication["source_evidence"]["raw_evidence_mutated"] is False
    assert adjudication["historical_classification"] == ("consumed-infrastructure-invalid-unscored")


def test_22_scientific_freeze_and_pair_commands_are_unchanged() -> None:
    v8 = load_json(EXP / "contracts/T09_PILOT_V8_SCIENCE_PROJECTION.json")
    v9 = load_json(EXP / "contracts/T09_PILOT_V9_SCIENCE_PROJECTION.json")
    commands = load_json(EXP / "contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V10.json")
    assert v9 == v8
    assert [pair["valid"] for pair in commands["pair_diffs"]] == [True, True]


def test_23_condition_retries_remain_zero() -> None:
    contract = load_json(EXP / "contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V10.json")
    assert contract["runtime_limits"]["max_retries_after_empirical_entry"] == 0


def _run_v9_release_order_regression() -> dict[str, object]:
    requests = (
        (1_075, 4_096, 78),
        (1_191, 81_920, 1_393),
        (905, 4_096, 126),
        (1_164, 4_096, 50),
        (1_156, 4_096, 74),
        (1_155, 4_096, 65),
        (1_238, 4_096, 189),
        (1_248, 4_096, 145),
        (1_232, 4_096, 232),
        (1_303, 81_920, 2_777),
        (1_337, 81_920, 2_022),
        (1_374, 81_920, 3_301),
    )
    caps = replace(
        condition_caps("simulative"),
        max_cost_usd=10.0,
        max_input_tokens=1_000_000,
        max_output_tokens=1_000_000,
        max_total_tokens=1_000_000,
        max_model_call_attempts=100,
    )
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=caps,
        condition_caps=caps,
    )
    entered = [threading.Event() for _ in requests]
    release = [threading.Event() for _ in requests]
    errors: list[BaseException] = []

    def invoke(index: int) -> None:
        input_tokens, max_output_tokens, output_tokens = requests[index]

        def send(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
            entered[index].set()
            release[index].wait()
            return "ok", ProviderResponseUsage(input_tokens, 0, output_tokens, "default")

        try:
            boundary.invoke(
                _request(input_tokens=input_tokens, output_tokens=max_output_tokens),
                send,
                call_id=f"CALL-{index:02d}",
            )
        except BaseException as exc:
            errors.append(exc)

    threads: list[threading.Thread] = []
    try:
        for index in range(len(requests)):
            thread = threading.Thread(target=invoke, args=(index,))
            thread.start()
            threads.append(thread)
            assert entered[index].wait(timeout=2)
        for index in (0, 1, 2, 5, 4, 3, 7, 6, 8, 9, 10, 11):
            release[index].set()
            threads[index].join(timeout=2)
    finally:
        for event in release:
            event.set()
        for thread in threads:
            thread.join(timeout=2)

    assert errors == []
    document = boundary.accounting_document()
    assert document["outstanding_reservations"] == 0
    assert document["unreconciled_provider_attempts"] == 0
    assert document["reserved_upper_bound"] == document["observed_lower_bound"]
    assert document["terminal_counts"]["sent_response_reconciled"] == 12
    assert all(
        record.terminal_state is ProviderCallTerminalState.RESPONSE_RECONCILED
        for record in boundary.call_records
    )
    assert all(
        record.history.count(ProviderCallPhase.SEND_STARTED.value) == 1
        for record in boundary.call_records
    )
    assert all(
        record.history.count(ProviderCallPhase.CALL_TERMINAL.value) == 1
        for record in boundary.call_records
    )
    return document


def test_24_concurrent_reservation_release_recomputes_exact_empty_projection() -> None:
    zero_projection = ProviderBudgetBoundary._usage_document(ProviderBudgetUsage())
    for _consecutive_run in range(3):
        document = _run_v9_release_order_regression()
        projections = document["outstanding_reservation_projection"]
        assert projections == {
            "condition": zero_projection,
            "aggregate": zero_projection,
        }
        assert math.copysign(1.0, projections["condition"]["cost_usd"]) == 1.0
        assert math.copysign(1.0, projections["aggregate"]["cost_usd"]) == 1.0


def test_25_finalizer_keeps_v9_and_historical_receipt_contracts_disjoint() -> None:
    path = ROOT / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
    specification = importlib.util.spec_from_file_location("t09_accounting_finalizer", path)
    assert specification is not None and specification.loader is not None
    finalizer = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(finalizer)
    base_payload = {
        "usage": {
            "input_tokens": 10,
            "cached_input_tokens": 0,
            "output_tokens": 5,
            "total_tokens": 15,
        },
        "role": "critic",
        "model": SIRA_MODEL_REVISION,
        "requested_service_tier": "default",
        "returned_service_tier": "default",
        "provider_response_id": "redacted-test-id",
        "system_fingerprint": None,
        "retry": {"sdk": 0, "transport": 0},
    }
    historical = [
        {
            "kind": "provider-call-receipt",
            "event_id": "event-1",
            "parent_event_id": None,
            "payload": base_payload,
        }
    ]
    assert (
        len(
            finalizer._provider_records(
                historical,
                contract=finalizer.ProviderReceiptContract.HISTORICAL_V4_REGRESSION,
            )
        )
        == 1
    )
    with pytest.raises(finalizer.T09PilotError, match="stable call identity"):
        finalizer._provider_records(
            historical,
            contract=finalizer.ProviderReceiptContract.V9_LIFECYCLE,
        )
    v9 = [
        {
            **historical[0],
            "payload": {
                **base_payload,
                "call_id": "CALL-0001",
                "terminal_accounting_state": "sent_response_reconciled",
            },
        }
    ]
    assert (
        len(
            finalizer._provider_records(
                v9,
                contract=finalizer.ProviderReceiptContract.V9_LIFECYCLE,
            )
        )
        == 1
    )
    with pytest.raises(finalizer.T09PilotError, match="unexpectedly uses the V9 schema"):
        finalizer._provider_records(
            v9,
            contract=finalizer.ProviderReceiptContract.HISTORICAL_V4_REGRESSION,
        )


def test_26_launch_package_command_hash_exception_is_exact_and_source_bound() -> None:
    with pytest.raises(T09ProviderError, match="execution package"):
        _autonomous_package_science_state(
            ROOT,
            AUTONOMOUS_V9_LAUNCH_PACKAGE_COMMIT,
            contract=V8_PROVIDER_CONTRACT,
            stale_command_authorization_sha256s=(AUTONOMOUS_V9_STALE_COMMAND_AUTHORIZATION_SHA256S),
        )
    with pytest.raises(T09ProviderError, match="condition does not match"):
        _autonomous_package_science_state(
            ROOT,
            AUTONOMOUS_V9_LAUNCH_PACKAGE_COMMIT,
            contract=V9_PROVIDER_CONTRACT,
        )
    projection = _autonomous_package_science_state(
        ROOT,
        AUTONOMOUS_V9_LAUNCH_PACKAGE_COMMIT,
        contract=V9_PROVIDER_CONTRACT,
        stale_command_authorization_sha256s=(AUTONOMOUS_V9_STALE_COMMAND_AUTHORIZATION_SHA256S),
    )
    assert len(projection["condition_science_sha256s"]) == 4
    altered = dict(AUTONOMOUS_V9_STALE_COMMAND_AUTHORIZATION_SHA256S)
    altered["RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0002"] = "0" * 64
    with pytest.raises(T09ProviderError, match="condition does not match"):
        _autonomous_package_science_state(
            ROOT,
            AUTONOMOUS_V9_LAUNCH_PACKAGE_COMMIT,
            contract=V9_PROVIDER_CONTRACT,
            stale_command_authorization_sha256s=altered,
        )
