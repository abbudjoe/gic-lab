from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from giclab.harness.lambda_cloud import EXPECTED_INVENTORY_REQUESTS
from giclab.harness.lambda_inventory_plan import (
    IMPLEMENTATION_ARTIFACT_PATHS,
    ImplementationArtifactBinding,
    InventoryRunBindingV2,
    ReadOnlyInventoryPlanV2,
)
from giclab.harness.lambda_request_ledger import (
    FailureClass,
    FailureStage,
    FsyncRequestLedger,
    LedgerEventType,
    RequestContext,
    RequestLedgerError,
    SanitizedFailure,
    contains_forbidden_material,
    validate_request_ledger_bytes,
    write_preflight_disposition,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_SHA256 = "9" * 64
AUTHORIZATION_SHA256 = "8" * 64
CANARY = b"DUMMY-LAMBDA-SECRET-CANARY"


def _implementation_bindings() -> tuple[ImplementationArtifactBinding, ...]:
    return tuple(
        ImplementationArtifactBinding(
            path=relative,
            sha256=hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
        )
        for relative in IMPLEMENTATION_ARTIFACT_PATHS
    )


def _repository(tmp_path: Path) -> tuple[Path, ReadOnlyInventoryPlanV2]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    schema_root = tmp_path / "schemas"
    schema_root.mkdir()
    ledger_source = ROOT / "schemas/t07-lambda-request-ledger.schema.json"
    inventory_source = ROOT / "schemas/t07-lambda-inventory-v2.schema.json"
    ledger_target = schema_root / ledger_source.name
    inventory_target = schema_root / inventory_source.name
    shutil.copyfile(ledger_source, ledger_target)
    shutil.copyfile(inventory_source, inventory_target)
    plan = ReadOnlyInventoryPlanV2(
        implementation_commit="7" * 40,
        implementation_artifacts=_implementation_bindings(),
        ledger_schema_sha256=hashlib.sha256(ledger_target.read_bytes()).hexdigest(),
        inventory_schema_sha256=hashlib.sha256(inventory_target.read_bytes()).hexdigest(),
        requests=EXPECTED_INVENTORY_REQUESTS,
    )
    return tmp_path, plan


def _binding() -> InventoryRunBindingV2:
    return InventoryRunBindingV2(
        run_id="RUN-T07-L1-LAMBDA-INVENTORY-0002",
        repository_commit="7" * 40,
        authorization_reference="AUTH-T07-GATE-L1-TEST-V3",
        authorization_sha256=AUTHORIZATION_SHA256,
    )


def _ledger(
    root: Path,
    plan: ReadOnlyInventoryPlanV2,
    *,
    fault_injector=None,
) -> FsyncRequestLedger:
    ledger = FsyncRequestLedger.create(
        root,
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
        monotonic_ns=iter(range(1, 1000)).__next__,
        utc_now=lambda: datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        fault_injector=fault_injector,
    )
    ledger.append(LedgerEventType.RUN_PREFLIGHT_STARTED)
    ledger.reserve_capacity()
    return ledger


def _pass_preflight(ledger: FsyncRequestLedger) -> None:
    ledger.append(LedgerEventType.SECRET_PRESENCE_CHECK_PASSED)
    ledger.append(LedgerEventType.RUN_PREFLIGHT_PASSED)


def _append_successful_requests(
    ledger: FsyncRequestLedger,
    plan: ReadOnlyInventoryPlanV2,
) -> None:
    for ordinal, request in enumerate(plan.requests, start=1):
        context = RequestContext.from_request(ordinal, request)
        ledger.append(LedgerEventType.REQUEST_INTENT_COMMITTED, request=context)
        ledger.append(LedgerEventType.REQUEST_SEND_STARTED, request=context)
        ledger.append(
            LedgerEventType.RESPONSE_HEADERS_RECEIVED,
            request=context,
            http_status=200,
            content_type="application/json",
            elapsed_ms=1,
        )
        ledger.append(
            LedgerEventType.RESPONSE_BODY_COMPLETED,
            request=context,
            bytes_received=2,
            http_status=200,
            content_type="application/json",
            elapsed_ms=2,
        )
        ledger.append(
            LedgerEventType.RESPONSE_VALIDATION_PASSED,
            request=context,
            bytes_received=2,
            http_status=200,
            content_type="application/json",
            elapsed_ms=2,
        )


def _terminal_success(
    ledger: FsyncRequestLedger,
    plan: ReadOnlyInventoryPlanV2,
):
    _pass_preflight(ledger)
    _append_successful_requests(ledger, plan)
    ledger.append(LedgerEventType.INVENTORY_VALIDATION_STARTED)
    ledger.append(LedgerEventType.INVENTORY_VALIDATION_PASSED)
    ledger.append(LedgerEventType.ARCHIVE_STARTED)
    ledger.append(LedgerEventType.ARCHIVE_PASSED)
    ledger.append(LedgerEventType.RUN_STOPPED)
    return ledger.seal(require_terminal_success=True)


def test_request_ledger_is_exclusive_fsync_bounded_and_terminally_valid(
    tmp_path: Path,
) -> None:
    root, plan = _repository(tmp_path)
    ledger = _ledger(root, plan)
    reservation = ledger.path.parent / ".request-ledger.capacity"
    assert reservation.stat().st_size == plan.limits.max_bytes
    snapshot = _terminal_success(ledger, plan)
    assert not reservation.exists()
    assert snapshot.events == 48
    assert snapshot.bytes <= plan.limits.max_bytes
    assert snapshot.sha256 == hashlib.sha256(snapshot.path.read_bytes()).hexdigest()
    assert snapshot.path.stat().st_mode & 0o222 == 0
    with pytest.raises(RequestLedgerError):
        FsyncRequestLedger.create(
            root,
            plan=plan,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
        )


def test_request_ledger_rejects_sequence_gaps_reordering_and_duplicate_keys(
    tmp_path: Path,
) -> None:
    root, plan = _repository(tmp_path)
    snapshot = _terminal_success(_ledger(root, plan), plan)
    encoded = snapshot.path.read_bytes()
    schema = json.loads((root / plan.ledger_schema_relative_path).read_bytes())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    lines = encoded.splitlines()
    second = json.loads(lines[1])
    second["event_sequence"] = 7
    lines[1] = json.dumps(second, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(RequestLedgerError):
        validate_request_ledger_bytes(
            b"\n".join(lines) + b"\n",
            plan=plan,
            run_binding=_binding(),
            validator=validator,
            require_terminal_success=True,
        )
    duplicate = encoded.replace(
        b'"event_sequence":1',
        b'"event_sequence":1,"event_sequence":1',
        1,
    )
    with pytest.raises(RequestLedgerError):
        validate_request_ledger_bytes(
            duplicate,
            plan=plan,
            run_binding=_binding(),
            validator=validator,
        )

    wrong_path_lines = encoded.splitlines()
    intent_index = next(
        index
        for index, line in enumerate(wrong_path_lines)
        if json.loads(line)["event_type"] == "request_intent_committed"
    )
    wrong_path = json.loads(wrong_path_lines[intent_index])
    wrong_path["path"] = "/api/v1/regions"
    wrong_path_lines[intent_index] = json.dumps(
        wrong_path, sort_keys=True, separators=(",", ":")
    ).encode()
    with pytest.raises(RequestLedgerError):
        validate_request_ledger_bytes(
            b"\n".join(wrong_path_lines) + b"\n",
            plan=plan,
            run_binding=_binding(),
            validator=validator,
        )

    backwards_time_lines = encoded.splitlines()
    second = json.loads(backwards_time_lines[1])
    second["monotonic_timestamp_ns"] = 0
    backwards_time_lines[1] = json.dumps(second, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(RequestLedgerError):
        validate_request_ledger_bytes(
            b"\n".join(backwards_time_lines) + b"\n",
            plan=plan,
            run_binding=_binding(),
            validator=validator,
        )


def test_intent_without_send_and_send_without_terminal_are_distinguishable(
    tmp_path: Path,
) -> None:
    root, plan = _repository(tmp_path)
    ledger = _ledger(root, plan)
    _pass_preflight(ledger)
    context = RequestContext.from_request(1, plan.requests[0])
    ledger.append(LedgerEventType.REQUEST_INTENT_COMMITTED, request=context)
    before_send = SanitizedFailure(
        FailureStage.UNKNOWN,
        FailureClass.INTERNAL_FAILURE,
        "L1_TEST_BEFORE_SEND",
    )
    ledger.append(
        LedgerEventType.REQUEST_FAILED,
        request=context,
        failure=before_send,
    )
    ledger.append(LedgerEventType.RUN_STOPPED, failure=before_send)
    snapshot = ledger.seal(require_terminal_success=False)
    assert b'"request_intent_committed"' in snapshot.path.read_bytes()
    assert b'"request_send_started"' not in snapshot.path.read_bytes()

    second_root, second_plan = _repository(tmp_path / "second")
    ledger = _ledger(second_root, second_plan)
    _pass_preflight(ledger)
    context = RequestContext.from_request(1, second_plan.requests[0])
    ledger.append(LedgerEventType.REQUEST_INTENT_COMMITTED, request=context)
    ledger.append(LedgerEventType.REQUEST_SEND_STARTED, request=context)
    unknown = SanitizedFailure(
        FailureStage.UNKNOWN,
        FailureClass.OUTCOME_UNKNOWN,
        "L1_TEST_OUTCOME_UNKNOWN",
    )
    ledger.append(
        LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND,
        request=context,
        failure=unknown,
    )
    ledger.append(LedgerEventType.RUN_STOPPED, failure=unknown)
    snapshot = ledger.seal(require_terminal_success=False)
    assert b'"request_outcome_unknown_after_send"' in snapshot.path.read_bytes()


def test_fsync_failure_taints_ledger_preserves_prefix_and_rejects_progression(
    tmp_path: Path,
) -> None:
    root, plan = _repository(tmp_path)

    def fail(event: str, phase: str) -> None:
        if event == "request_send_started" and phase == "before_fsync":
            raise OSError

    ledger = _ledger(root, plan, fault_injector=fail)
    _pass_preflight(ledger)
    context = RequestContext.from_request(1, plan.requests[0])
    ledger.append(LedgerEventType.REQUEST_INTENT_COMMITTED, request=context)
    with pytest.raises(RequestLedgerError):
        ledger.append(LedgerEventType.REQUEST_SEND_STARTED, request=context)
    assert ledger.tainted
    ledger.close_preserving_incomplete()
    encoded = ledger.path.read_bytes()
    assert b'"request_intent_committed"' in encoded
    assert b'"request_send_started"' in encoded
    with pytest.raises(RequestLedgerError):
        ledger.append(LedgerEventType.REQUEST_SEND_STARTED, request=context)


def test_incomplete_or_unknown_ledgers_are_not_gate_l2_eligible(tmp_path: Path) -> None:
    root, plan = _repository(tmp_path)
    ledger = _ledger(root, plan)
    _pass_preflight(ledger)
    ledger.close_preserving_incomplete()
    schema = json.loads((root / plan.ledger_schema_relative_path).read_bytes())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    with pytest.raises(RequestLedgerError):
        validate_request_ledger_bytes(
            ledger.path.read_bytes(),
            plan=plan,
            run_binding=_binding(),
            validator=validator,
            require_terminal_success=True,
        )


def test_offline_validation_rejects_contradictory_event_field_bundles(
    tmp_path: Path,
) -> None:
    root, plan = _repository(tmp_path)
    snapshot = _terminal_success(_ledger(root, plan), plan)
    schema = json.loads((root / plan.ledger_schema_relative_path).read_bytes())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    original = snapshot.path.read_bytes().splitlines()

    def rejected(index: int, changes: dict[str, object]) -> None:
        lines = list(original)
        event = json.loads(lines[index])
        event.update(changes)
        lines[index] = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
        with pytest.raises(RequestLedgerError):
            validate_request_ledger_bytes(
                b"\n".join(lines) + b"\n",
                plan=plan,
                run_binding=_binding(),
                validator=validator,
                require_terminal_success=True,
            )

    rejected(
        -1,
        {
            "sanitized_failure_class": "internal_failure",
            "stable_error_code": "L1_CONTRADICTORY_SUCCESS",
        },
    )
    rejected(
        0,
        {
            "request_ordinal": 1,
            "method": "GET",
            "scheme": "https",
            "host": "cloud.lambda.ai",
            "path": "/api/v1/audit-events",
            "query_key_names": ["resource_type"],
        },
    )
    intent_index = next(
        index
        for index, line in enumerate(original)
        if json.loads(line)["event_type"] == "request_intent_committed"
    )
    rejected(intent_index, {"http_status": 200, "content_type": "application/json"})
    headers_index = next(
        index
        for index, line in enumerate(original)
        if json.loads(line)["event_type"] == "response_headers_received"
    )
    rejected(headers_index, {"http_status": 401})


def test_offline_validation_rejects_terminal_progress_regression(tmp_path: Path) -> None:
    root, plan = _repository(tmp_path)
    ledger = _ledger(root, plan)
    _pass_preflight(ledger)
    context = RequestContext.from_request(1, plan.requests[0])
    ledger.append(LedgerEventType.REQUEST_INTENT_COMMITTED, request=context)
    ledger.append(LedgerEventType.REQUEST_SEND_STARTED, request=context)
    ledger.append(
        LedgerEventType.RESPONSE_HEADERS_RECEIVED,
        request=context,
        http_status=200,
        content_type="application/json",
        elapsed_ms=1,
    )
    ledger.append(
        LedgerEventType.RESPONSE_BODY_PROGRESS,
        request=context,
        bytes_received=65_536,
        http_status=200,
        content_type="application/json",
        elapsed_ms=2,
    )
    failure = SanitizedFailure(
        FailureStage.UNKNOWN,
        FailureClass.OUTCOME_UNKNOWN,
        "L1_TEST_OUTCOME_UNKNOWN",
    )
    ledger.append(
        LedgerEventType.REQUEST_OUTCOME_UNKNOWN_AFTER_SEND,
        request=context,
        bytes_received=65_536,
        http_status=200,
        content_type="application/json",
        elapsed_ms=2,
        failure=failure,
    )
    ledger.append(LedgerEventType.RUN_STOPPED, failure=failure)
    snapshot = ledger.seal(require_terminal_success=False)
    lines = snapshot.path.read_bytes().splitlines()
    terminal = json.loads(lines[-2])
    terminal["bytes_received_so_far"] = 0
    lines[-2] = json.dumps(terminal, sort_keys=True, separators=(",", ":")).encode()
    schema = json.loads((root / plan.ledger_schema_relative_path).read_bytes())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    with pytest.raises(RequestLedgerError):
        validate_request_ledger_bytes(
            b"\n".join(lines) + b"\n",
            plan=plan,
            run_binding=_binding(),
            validator=validator,
        )


def test_secret_canary_scan_covers_ledger_errors_artifacts_and_output() -> None:
    safe_surfaces = (
        b'{"event":"request_failed","class":"dns_failure"}',
        b'{"artifact":"redacted"}',
        b'{"output":"stopped"}',
    )
    assert not contains_forbidden_material(safe_surfaces, canary=CANARY)
    assert contains_forbidden_material((*safe_surfaces, CANARY), canary=CANARY)


def test_schema_failure_burns_identity_and_fixed_disposition_cannot_multiply(
    tmp_path: Path,
) -> None:
    root, plan = _repository(tmp_path)
    schema_drift = replace(plan, ledger_schema_sha256="0" * 64)
    with pytest.raises(RequestLedgerError):
        FsyncRequestLedger.create(
            root,
            plan=schema_drift,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
        )
    assert (root / plan.run_root_relative_path).is_dir()
    disposition = write_preflight_disposition(
        root,
        plan=plan,
        run_binding=_binding(),
    )
    assert disposition.path.name == f"{plan.run_id}.json"
    with pytest.raises(RequestLedgerError):
        FsyncRequestLedger.create(
            root,
            plan=plan,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
        )
    with pytest.raises(RequestLedgerError):
        write_preflight_disposition(
            root,
            plan=plan,
            run_binding=_binding(),
        )
    assert len(list(disposition.path.parent.iterdir())) == 1


def test_ancestor_parent_fsync_failure_stops_and_is_durably_tombstoned(
    tmp_path: Path,
) -> None:
    root, plan = _repository(tmp_path)
    failed = False

    def fail_once(event: str, phase: str) -> None:
        nonlocal failed
        if event == "ledger_directory" and phase == "before_parent_fsync" and not failed:
            failed = True
            raise OSError

    with pytest.raises(RequestLedgerError):
        FsyncRequestLedger.create(
            root,
            plan=plan,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            fault_injector=fail_once,
        )
    disposition = write_preflight_disposition(
        root,
        plan=plan,
        run_binding=_binding(),
    )
    assert json.loads(disposition.path.read_bytes())["run_identity_reusable"] is False
    with pytest.raises(RequestLedgerError):
        FsyncRequestLedger.create(
            root,
            plan=plan,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
        )
