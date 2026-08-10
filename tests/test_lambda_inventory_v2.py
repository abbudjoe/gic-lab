from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from test_lambda_cloud import _responses
from test_lambda_request_ledger import _implementation_bindings

from giclab.harness import lambda_inventory as v1_runner
from giclab.harness import lambda_inventory_v2 as runner
from giclab.harness.lambda_archive import InventoryArchiveError
from giclab.harness.lambda_archive_v2 import ArchivedInventoryArtifactV2
from giclab.harness.lambda_cloud import EXPECTED_INVENTORY_REQUESTS
from giclab.harness.lambda_inventory_plan import (
    ImplementationArtifactBinding,
    InventoryRunBindingV2,
    ReadOnlyInventoryPlanV2,
    load_inventory_plan_v2,
    verify_inventory_implementation_v2,
)
from giclab.harness.lambda_request_ledger import (
    FailureClass,
    FailureStage,
    FsyncRequestLedger,
    InventoryObservedFailure,
    RequestLedgerError,
    SanitizedFailure,
    validate_request_ledger_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_SHA256 = "9" * 64
CANARY = "DUMMY-LAMBDA-SECRET-CANARY"
RAW_ONLY_CANARY = "DUMMY-RAW-RESPONSE-CANARY"
COMMITTED_PLAN_V2_SHA256 = "02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e"
IMPLEMENTATION_COMMIT = "0b900213801315f4312105297774b8ea5a6d9f04"


def _assert_closed_exception_has_no_canary(
    error: BaseException,
    *canaries: str,
) -> None:
    pending = [error]
    seen_exceptions: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen_exceptions:
            continue
        seen_exceptions.add(id(current))
        surfaces = [str(current), repr(current)]
        surfaces.extend(
            value.decode(errors="replace") if isinstance(value, bytes) else value
            for value in current.args
            if isinstance(value, (str, bytes))
        )
        assert all(canary not in surface for canary in canaries for surface in surfaces)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
        traceback = current.__traceback__
        while traceback is not None:
            for value in traceback.tb_frame.f_locals.values():
                if isinstance(value, bytes):
                    local_surface = value.decode(errors="replace")
                elif isinstance(value, str):
                    local_surface = value
                elif isinstance(value, BaseException):
                    pending.append(value)
                    continue
                else:
                    continue
                assert all(canary not in local_surface for canary in canaries)
            traceback = traceback.tb_next


class FakeDeadline:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeDeadlineFactory:
    def __init__(self) -> None:
        self.deadlines: list[FakeDeadline] = []

    def __call__(self, seconds: int) -> FakeDeadline:
        deadline = FakeDeadline(seconds)
        self.deadlines.append(deadline)
        return deadline


@dataclass(slots=True)
class MutableClock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class FakePreparedArchiveV2:
    def __init__(
        self,
        root: Path,
        plan: ReadOnlyInventoryPlanV2,
        binding: InventoryRunBindingV2,
        *,
        fail_stage: bool = False,
        fail_finalize: bool = False,
    ) -> None:
        self.root = root
        self.plan = plan
        self.binding = binding
        self.fail_stage = fail_stage
        self.fail_finalize = fail_finalize
        self.staged = False
        self.closed = False
        self.terminal_ledger: bytes | None = None

    def stage_inventory(
        self,
        artifact_path: Path,
        *,
        artifact_sha256: str,
        artifact_bytes: int,
    ) -> None:
        if self.fail_stage:
            raise InventoryArchiveError("synthetic stage failure")
        encoded = artifact_path.read_bytes()
        assert len(encoded) == artifact_bytes
        assert hashlib.sha256(encoded).hexdigest() == artifact_sha256
        self.staged = True

    def finalize(
        self,
        artifact_path: Path,
        *,
        artifact_sha256: str,
        artifact_bytes: int,
        ledger,
    ) -> ArchivedInventoryArtifactV2:
        if self.fail_finalize:
            raise InventoryArchiveError("synthetic finalization failure")
        assert self.staged
        encoded = ledger.path.read_bytes()
        schema = json.loads((self.root / self.plan.ledger_schema_relative_path).read_bytes())
        events = validate_request_ledger_bytes(
            encoded,
            plan=self.plan,
            run_binding=self.binding,
            validator=Draft202012Validator(schema, format_checker=FormatChecker()),
            require_terminal_success=True,
        )
        assert len(events) == ledger.events
        self.terminal_ledger = encoded
        local_record = (
            json.dumps(
                {
                    "archive": "verified",
                    "inventory_sha256": artifact_sha256,
                    "ledger_sha256": ledger.sha256,
                    "terminal_ledger_validated": True,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        return ArchivedInventoryArtifactV2(
            destination=Path(
                "/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts/"
                "RUN-T07-L1-LAMBDA-INVENTORY-0002"
            ),
            artifact_sha256=artifact_sha256,
            artifact_bytes=artifact_bytes,
            ledger_sha256=ledger.sha256,
            ledger_bytes=ledger.bytes,
            seal_sha256="3" * 64,
            external_copy_record_sha256="4" * 64,
            local_verification_record=local_record,
        )

    def close(self) -> None:
        self.closed = True


class FakeArchiverV2:
    def __init__(self, *, fail_stage: bool = False, fail_finalize: bool = False) -> None:
        self.fail_stage = fail_stage
        self.fail_finalize = fail_finalize
        self.prepared: FakePreparedArchiveV2 | None = None

    def prepare(self, repository_root, *, plan, plan_sha256, run_binding):
        self.prepared = FakePreparedArchiveV2(
            repository_root,
            plan,
            run_binding,
            fail_stage=self.fail_stage,
            fail_finalize=self.fail_finalize,
        )
        return self.prepared


class FakeTransport:
    def __init__(
        self,
        responses: dict[str, bytes],
        *,
        failure: SanitizedFailure | None = None,
        failure_status: int | None = None,
        failure_content_type: str | None = None,
        crash: bool = False,
        crash_after_progress: bool = False,
    ) -> None:
        self.responses = responses
        self.failure = failure
        self.failure_status = failure_status
        self.failure_content_type = failure_content_type
        self.crash = crash
        self.crash_after_progress = crash_after_progress
        self.request_ids: list[str] = []

    def fetch(
        self,
        request,
        *,
        credential: str,
        timeout_seconds: float,
        observer,
    ) -> runner.InventoryHttpResponseV2:
        assert credential == CANARY
        assert 0 < timeout_seconds <= 60
        self.request_ids.append(request.request_id)
        if self.crash:
            raise RuntimeError(f"synthetic crash carrying {credential}")
        if self.crash_after_progress:
            observer.response_headers_received(
                status_code=200,
                content_type="application/json",
                elapsed_ms=1,
            )
            observer.response_body_progress(
                bytes_received=65_536,
                status_code=200,
                content_type="application/json",
                elapsed_ms=2,
            )
            raise RuntimeError(f"synthetic post-progress crash carrying {credential}")
        if self.failure is not None:
            if self.failure_status is not None:
                observer.response_headers_received(
                    status_code=self.failure_status,
                    content_type=self.failure_content_type or "application/json",
                    elapsed_ms=1,
                )
            raise InventoryObservedFailure(
                self.failure,
                http_status=self.failure_status,
                content_type=self.failure_content_type,
                elapsed_ms=1,
            )
        body = self.responses[request.request_id]
        observer.response_headers_received(
            status_code=200,
            content_type="application/json",
            elapsed_ms=1,
        )
        observer.response_body_progress(
            bytes_received=len(body),
            status_code=200,
            content_type="application/json",
            elapsed_ms=2,
        )
        return runner.InventoryHttpResponseV2(200, "application/json", body, 2)


def _repository(tmp_path: Path) -> tuple[Path, ReadOnlyInventoryPlanV2]:
    schemas = tmp_path / "schemas"
    schemas.mkdir(parents=True)
    for name in (
        "t07-lambda-request-ledger.schema.json",
        "t07-lambda-inventory-v2.schema.json",
    ):
        shutil.copyfile(ROOT / "schemas" / name, schemas / name)
    plan = ReadOnlyInventoryPlanV2(
        implementation_commit="7" * 40,
        implementation_artifacts=_implementation_bindings(),
        ledger_schema_sha256=hashlib.sha256(
            (schemas / "t07-lambda-request-ledger.schema.json").read_bytes()
        ).hexdigest(),
        inventory_schema_sha256=hashlib.sha256(
            (schemas / "t07-lambda-inventory-v2.schema.json").read_bytes()
        ).hexdigest(),
        requests=EXPECTED_INVENTORY_REQUESTS,
    )
    return tmp_path, plan


def _binding() -> InventoryRunBindingV2:
    return InventoryRunBindingV2(
        run_id="RUN-T07-L1-LAMBDA-INVENTORY-0002",
        repository_commit="7" * 40,
        authorization_reference="AUTH-T07-GATE-L1-TEST-V3",
        authorization_sha256="8" * 64,
    )


def _events(root: Path, plan: ReadOnlyInventoryPlanV2) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in (root / plan.ledger_relative_path).read_bytes().splitlines()
    ]


def _execute(
    root: Path,
    plan: ReadOnlyInventoryPlanV2,
    monkeypatch: pytest.MonkeyPatch,
    *,
    transport: FakeTransport | None = None,
    archiver: FakeArchiverV2 | None = None,
    credential_provider=None,
    fault_injector=None,
):
    monkeypatch.setattr(runner, "load_inventory_plan_v2", lambda *args, **kwargs: plan)
    clock = MutableClock()
    deadlines = FakeDeadlineFactory()
    result = runner.execute_authorized_inventory_v2(
        repository_root=root,
        plan_path=root / "synthetic-plan.json",
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
        credential_provider=credential_provider or (lambda: CANARY),
        transport=transport or FakeTransport(_responses()),
        archiver=archiver or FakeArchiverV2(),
        watchdog_factory=deadlines,
        repository_inspector=lambda repository_root, expected_commit: runner.RepositoryState(
            branch="phase-1/sira-smoke-lambda",
            commit=expected_commit,
            clean=True,
        ),
        implementation_verifier=lambda repository_root, bound_plan: None,
        clock=clock,
        sleeper=clock.sleep,
        monotonic_ns=iter(range(1, 1000)).__next__,
        utc_now=lambda: datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        fault_injector=fault_injector,
    )
    return result, deadlines


def test_v2_success_records_all_eight_requests_and_seals_terminal_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    transport = FakeTransport(_responses())
    archiver = FakeArchiverV2()
    result, deadlines = _execute(
        root,
        plan,
        monkeypatch,
        transport=transport,
        archiver=archiver,
    )
    assert transport.request_ids == [request.request_id for request in plan.requests]
    assert result.provider_calls == 8
    assert result.selection_state == "selected"
    assert archiver.prepared is not None
    assert archiver.prepared.terminal_ledger == result.ledger.path.read_bytes()
    assert archiver.prepared.closed
    events = _events(root, plan)
    assert [event["event_sequence"] for event in events] == list(range(1, len(events) + 1))
    assert events[-2]["event_type"] == "archive_passed"
    assert events[-1]["event_type"] == "run_stopped"
    assert [event["event_type"] for event in events].count("request_intent_committed") == 8
    assert [event["event_type"] for event in events].count("request_send_started") == 8
    retained = (
        result.artifact.path.read_bytes(),
        result.ledger.path.read_bytes(),
        result.copy_record.path.read_bytes(),
        archiver.prepared.terminal_ledger,
    )
    assert all(CANARY.encode() not in surface for surface in retained)
    assert [deadline.seconds for deadline in deadlines.deadlines] == [180, 60]
    assert all(deadline.closed for deadline in deadlines.deadlines)


@pytest.mark.parametrize(
    ("stage", "expected", "forbidden"),
    [
        ("before_intent", "run_stopped", "request_intent_committed"),
        ("after_intent_before_send", "request_failed", "request_send_started"),
        ("after_send_started", "request_outcome_unknown_after_send", "request_failed"),
    ],
)
def test_v2_generic_failure_boundaries_are_observable_and_never_replayed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected: str,
    forbidden: str,
) -> None:
    root, plan = _repository(tmp_path)
    transport = FakeTransport(_responses())

    def inject(point: str) -> None:
        if point == stage:
            raise RuntimeError("synthetic boundary failure")

    with pytest.raises(InventoryObservedFailure):
        _execute(
            root,
            plan,
            monkeypatch,
            transport=transport,
            fault_injector=inject,
        )
    event_types = [event["event_type"] for event in _events(root, plan)]
    assert expected in event_types
    assert forbidden not in event_types
    assert len(transport.request_ids) == 0


def test_v2_second_intent_failure_never_reuses_first_request_elapsed_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    transport = FakeTransport(_responses())
    intent_boundaries = 0

    def inject(point: str) -> None:
        nonlocal intent_boundaries
        if point == "after_intent_before_send":
            intent_boundaries += 1
            if intent_boundaries == 2:
                raise RuntimeError("synthetic second-intent failure")

    with pytest.raises(InventoryObservedFailure):
        _execute(
            root,
            plan,
            monkeypatch,
            transport=transport,
            fault_injector=inject,
        )
    failed = next(event for event in _events(root, plan) if event["event_type"] == "request_failed")
    assert failed["request_ordinal"] == 2
    assert failed["elapsed_ms"] is None
    assert transport.request_ids == [plan.requests[0].request_id]


def test_v2_inside_transport_crash_records_unknown_outcome_and_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    transport = FakeTransport(_responses(), crash=True)
    with pytest.raises(InventoryObservedFailure) as raised:
        _execute(root, plan, monkeypatch, transport=transport)
    assert str(raised.value) == "L1_PRESEND_INTERNAL_FAILURE"
    assert transport.request_ids == [plan.requests[0].request_id]
    events = _events(root, plan)
    assert [event["event_type"] for event in events][-2:] == [
        "request_outcome_unknown_after_send",
        "run_stopped",
    ]
    assert not (root / plan.output_relative_path).exists()


def test_v2_post_progress_crash_retains_all_observed_terminal_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    transport = FakeTransport(_responses(), crash_after_progress=True)
    with pytest.raises(InventoryObservedFailure):
        _execute(root, plan, monkeypatch, transport=transport)
    unknown = next(
        event
        for event in _events(root, plan)
        if event["event_type"] == "request_outcome_unknown_after_send"
    )
    assert unknown["http_status"] == 200
    assert unknown["content_type"] == "application/json"
    assert unknown["elapsed_ms"] == 2
    assert unknown["bytes_received_so_far"] == 65_536


def test_v2_raw_secret_bearing_exception_never_reaches_any_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, plan = _repository(tmp_path)
    transport = FakeTransport(_responses(), crash=True)
    with pytest.raises(InventoryObservedFailure) as raised:
        _execute(root, plan, monkeypatch, transport=transport)
    _assert_closed_exception_has_no_canary(raised.value, CANARY)
    captured = capsys.readouterr()
    surfaces = [
        str(raised.value).encode(),
        captured.out.encode(),
        captured.err.encode(),
    ]
    surfaces.extend(
        path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.stat().st_size <= 5 * 1024 * 1024
    )
    assert all(CANARY.encode() not in surface for surface in surfaces)


def test_v2_observer_ledger_error_drops_secret_bearing_transport_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    original = FsyncRequestLedger.create.__func__

    def create(cls, *args, **kwargs):
        def fail(event: str, phase: str) -> None:
            if event == "response_headers_received" and phase == "before_fsync":
                raise OSError(f"synthetic ledger error carrying {CANARY}")

        kwargs["fault_injector"] = fail
        return original(cls, *args, **kwargs)

    monkeypatch.setattr(FsyncRequestLedger, "create", classmethod(create))
    with pytest.raises(RequestLedgerError) as raised:
        _execute(root, plan, monkeypatch)
    _assert_closed_exception_has_no_canary(raised.value, CANARY)


def test_v2_archive_failure_traceback_retains_no_raw_response_only_material(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    responses = _responses()
    audit = json.loads(responses[plan.requests[0].request_id])
    audit["data"][0]["actor_display_name"] = RAW_ONLY_CANARY
    responses[plan.requests[0].request_id] = json.dumps(audit).encode()
    transport = FakeTransport(responses)
    with pytest.raises(InventoryObservedFailure) as raised:
        _execute(
            root,
            plan,
            monkeypatch,
            transport=transport,
            archiver=FakeArchiverV2(fail_stage=True),
        )
    _assert_closed_exception_has_no_canary(raised.value, CANARY, RAW_ONLY_CANARY)


@pytest.mark.parametrize(
    ("failure", "status", "content_type"),
    [
        (
            SanitizedFailure(
                FailureStage.DNS,
                FailureClass.DNS_FAILURE,
                "L1_DNS_FAILURE",
            ),
            None,
            None,
        ),
        (
            SanitizedFailure(
                FailureStage.TLS_HANDSHAKE,
                FailureClass.TLS_FAILURE,
                "L1_TLS_FAILURE",
            ),
            None,
            None,
        ),
        (
            SanitizedFailure(
                FailureStage.HTTP_STATUS,
                FailureClass.HTTP_UNAUTHORIZED,
                "L1_HTTP_401",
            ),
            401,
            "application/json",
        ),
        (
            SanitizedFailure(
                FailureStage.HTTP_STATUS,
                FailureClass.HTTP_FORBIDDEN,
                "L1_HTTP_403",
            ),
            403,
            "application/json",
        ),
        (
            SanitizedFailure(
                FailureStage.RATE_LIMIT,
                FailureClass.HTTP_RATE_LIMITED,
                "L1_HTTP_429",
            ),
            429,
            "application/json",
        ),
        (
            SanitizedFailure(
                FailureStage.REDIRECT,
                FailureClass.HTTP_REDIRECT,
                "L1_HTTP_REDIRECT",
            ),
            302,
            "application/json",
        ),
        (
            SanitizedFailure(
                FailureStage.CONTENT_TYPE,
                FailureClass.UNEXPECTED_CONTENT_TYPE,
                "L1_CONTENT_TYPE_UNEXPECTED",
            ),
            200,
            "unexpected",
        ),
        (
            SanitizedFailure(
                FailureStage.RESPONSE_SIZE,
                FailureClass.RESPONSE_TOO_LARGE,
                "L1_RESPONSE_TOO_LARGE",
            ),
            200,
            "application/json",
        ),
    ],
)
def test_v2_transport_failures_have_closed_ledger_categories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: SanitizedFailure,
    status: int | None,
    content_type: str | None,
) -> None:
    root, plan = _repository(tmp_path)
    transport = FakeTransport(
        _responses(),
        failure=failure,
        failure_status=status,
        failure_content_type=content_type,
    )
    with pytest.raises(InventoryObservedFailure):
        _execute(root, plan, monkeypatch, transport=transport)
    events = _events(root, plan)
    failed = [event for event in events if event["event_type"] == "request_failed"]
    assert len(failed) == 1
    assert failed[0]["sanitized_failure_stage"] == failure.stage.value
    assert failed[0]["sanitized_failure_class"] == failure.classification.value
    assert failed[0]["stable_error_code"] == failure.stable_error_code
    assert len(transport.request_ids) == 1


@pytest.mark.parametrize(
    ("response_override", "classification"),
    [
        (b"{not-json", "malformed_json"),
        (b'{"data":[{"unexpected":true}]}', "schema_drift"),
    ],
)
def test_v2_malformed_json_and_schema_drift_stop_before_second_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    response_override: bytes,
    classification: str,
) -> None:
    root, plan = _repository(tmp_path)
    responses = _responses()
    responses[plan.requests[0].request_id] = response_override
    transport = FakeTransport(responses)
    with pytest.raises(InventoryObservedFailure):
        _execute(root, plan, monkeypatch, transport=transport)
    failed = [event for event in _events(root, plan) if event["event_type"] == "request_failed"]
    assert failed[0]["sanitized_failure_class"] == classification
    assert transport.request_ids == [plan.requests[0].request_id]


def test_v2_pagination_token_stops_without_an_additional_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    responses = _responses()
    audit = json.loads(responses[plan.requests[0].request_id])
    audit["page_token"] = "synthetic-continuation"
    responses[plan.requests[0].request_id] = json.dumps(audit).encode()
    transport = FakeTransport(responses)
    with pytest.raises(InventoryObservedFailure):
        _execute(root, plan, monkeypatch, transport=transport)
    failed = [event for event in _events(root, plan) if event["event_type"] == "request_failed"]
    assert failed[0]["sanitized_failure_stage"] == "pagination"
    assert transport.request_ids == [plan.requests[0].request_id]


def test_v2_ledger_creation_failure_blocks_before_secret_and_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    (root / plan.run_root_relative_path).mkdir(parents=True)
    secret_accessed = False

    def credential_provider() -> str:
        nonlocal secret_accessed
        secret_accessed = True
        return CANARY

    transport = FakeTransport(_responses())
    with pytest.raises(RequestLedgerError):
        _execute(
            root,
            plan,
            monkeypatch,
            transport=transport,
            credential_provider=credential_provider,
        )
    assert not secret_accessed
    assert not transport.request_ids
    dispositions = list((root / plan.preflight_disposition_root_relative_path).glob("*.json"))
    assert len(dispositions) == 1
    disposition = json.loads(dispositions[0].read_bytes())
    assert disposition["account_request_attempted"] is False
    assert disposition["real_secret_accessed"] is False


def test_v2_ledger_fsync_failure_after_send_preserves_prefix_and_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    original = FsyncRequestLedger.create.__func__

    def create(cls, *args, **kwargs):
        def fail(event: str, phase: str) -> None:
            if event == "request_failed" and phase == "before_fsync":
                raise OSError

        kwargs["fault_injector"] = fail
        return original(cls, *args, **kwargs)

    monkeypatch.setattr(FsyncRequestLedger, "create", classmethod(create))
    failure = SanitizedFailure(
        FailureStage.DNS,
        FailureClass.DNS_FAILURE,
        "L1_DNS_FAILURE",
    )
    transport = FakeTransport(_responses(), failure=failure)
    with pytest.raises(RequestLedgerError):
        _execute(root, plan, monkeypatch, transport=transport)
    encoded = (root / plan.ledger_relative_path).read_bytes()
    assert b'"request_send_started"' in encoded
    assert len(transport.request_ids) == 1
    assert not (root / plan.output_relative_path).exists()


def test_v2_archive_failure_cannot_produce_an_eligible_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    archiver = FakeArchiverV2(fail_stage=True)
    with pytest.raises(InventoryObservedFailure):
        _execute(root, plan, monkeypatch, archiver=archiver)
    events = _events(root, plan)
    assert events[-2]["event_type"] == "archive_failed"
    assert events[-1]["event_type"] == "run_stopped"
    assert not (root / plan.copy_record_relative_path).exists()


def test_v2_finalize_failure_preserves_terminal_ledger_but_no_gate_l2_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)
    archiver = FakeArchiverV2(fail_finalize=True)
    with pytest.raises(InventoryObservedFailure) as raised:
        _execute(root, plan, monkeypatch, archiver=archiver)
    assert str(raised.value) == "L1_ARCHIVE_FAILED"
    events = _events(root, plan)
    assert events[-2]["event_type"] == "archive_passed"
    assert events[-1]["event_type"] == "run_stopped"
    assert not (root / plan.copy_record_relative_path).exists()


def test_v2_uses_no_shell_curl_wget_or_http_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, plan = _repository(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("no subprocess is permitted in the fake-transport test")

    monkeypatch.setattr(v1_runner.subprocess, "run", forbidden)
    monkeypatch.setattr(v1_runner.subprocess, "Popen", forbidden)
    result, _ = _execute(root, plan, monkeypatch)
    assert result.provider_calls == 8


def test_v2_process_and_retention_caps_are_exact_and_finite(tmp_path: Path) -> None:
    _, plan = _repository(tmp_path)
    assert plan.max_calls == 8
    assert plan.max_total_response_bytes == 2_097_152
    assert plan.limits.max_bytes == 262_144
    assert plan.limits.max_events == 96
    assert plan.limits.max_events_per_request == 9
    assert plan.limits.max_event_bytes == 2_048
    assert plan.max_total_wall_seconds == 180
    assert plan.max_archive_bytes == 1_048_576
    assert plan.max_aggregate_retained_bytes == 1_916_928
    assert plan.max_local_file_creates == 4
    assert plan.automatic_retries == 0


def test_v2_implementation_and_inventory_schema_hashes_fail_closed(
    tmp_path: Path,
) -> None:
    _, plan = _repository(tmp_path)
    verify_inventory_implementation_v2(ROOT, plan)
    first = plan.implementation_artifacts[0]
    drifted_artifact = ImplementationArtifactBinding(
        path=first.path,
        sha256="0" * 64,
    )
    with pytest.raises(Exception, match="artifact hash drifted"):
        verify_inventory_implementation_v2(
            ROOT,
            replace(
                plan,
                implementation_artifacts=(
                    drifted_artifact,
                    *plan.implementation_artifacts[1:],
                ),
            ),
        )
    with pytest.raises(Exception, match="inventory schema binding failed"):
        verify_inventory_implementation_v2(
            ROOT,
            replace(plan, inventory_schema_sha256="0" * 64),
        )


def test_v1_run_identity_is_burned_and_cannot_bind_v2() -> None:
    with pytest.raises(Exception, match="identity drifted"):
        InventoryRunBindingV2(
            run_id="RUN-T07-L1-LAMBDA-INVENTORY-0001",
            repository_commit="7" * 40,
            authorization_reference="AUTH-T07-GATE-L1-TEST-V3",
            authorization_sha256="8" * 64,
        )


def test_committed_v2_plan_binds_frozen_implementation_and_remains_unauthorized() -> None:
    plan_path = ROOT / "containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v2.json"
    encoded = plan_path.read_bytes()
    assert len(encoded) == 8_856
    assert hashlib.sha256(encoded).hexdigest() == COMMITTED_PLAN_V2_SHA256
    plan = load_inventory_plan_v2(
        plan_path,
        expected_sha256=COMMITTED_PLAN_V2_SHA256,
    )
    assert plan.implementation_commit == IMPLEMENTATION_COMMIT
    assert not plan.authorized
    verify_inventory_implementation_v2(ROOT, plan)
