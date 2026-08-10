from __future__ import annotations

import json
from pathlib import Path

import pytest

from giclab.harness.lambda_l2_execution import (
    FsyncL2ProviderLedger,
    L2ExecutionError,
    ProviderRequest,
    ProviderResponse,
    TransportFailure,
    execute_observed_request,
    render_provider_request,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = "AUTH-T07-L2-TEST-0001"


def private_requests() -> dict[str, object]:
    strict_rule = {
        "protocol": "tcp",
        "source_network": "8.8.8.8/32",
        "port_range": [22, 22],
        "description": "synthetic strict rule",
    }
    return {
        "strict_global_patch_body": {"rules": [strict_rule]},
        "regional_create_body": {
            "name": "giclab-t07-l2-rs-0123456789ab",
            "region": "us-east-1",
            "rules": [strict_rule],
        },
        "launch_body_template": {
            "region_name": "us-east-1",
            "instance_type_name": "gpu_1x_a10",
            "ssh_key_names": ["fractal-lambda-codex"],
            "file_system_names": [],
            "file_system_mounts": [],
            "name": "giclab-t07-l2-0123456789ab",
            "hostname": "giclab-t07-l2-0123456789ab",
            "image": {"id": "image-a"},
            "tags": [
                {"key": "giclab-experiment", "value": "EXP-0001"},
                {"key": "giclab-gate", "value": "T07-L2"},
                {"key": "giclab-run", "value": "RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0001"},
                {"key": "giclab-owner", "value": "0123456789ab"},
                {
                    "key": "giclab-plan",
                    "value": "PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V1",
                },
            ],
            "authorization_tag_runtime_binding": "authorization_reference",
            "firewall_rulesets_runtime_binding": "owned_regional_ruleset_id",
        },
        "terminate_body_template": {"instance_ids_runtime_binding": "owned_instance_id"},
    }


def bindings() -> dict[str, object]:
    return {
        "owned_regional_ruleset_id": "ruleset-a",
        "owned_instance_id": "instance-a",
        "sealed_original_global_response": {
            "data": {
                "rules": [
                    {
                        "protocol": "tcp",
                        "source_network": "8.8.4.4/32",
                        "port_range": [22, 22],
                        "description": "synthetic original",
                    }
                ]
            }
        },
    }


@pytest.mark.parametrize(
    ("operation", "expected_body_key"),
    [(8, "rules"), (10, "rules"), (13, "firewall_rulesets"), (16, "instance_ids"), (20, "rules")],
)
def test_mutation_request_rendering_is_typed(operation: int, expected_body_key: str) -> None:
    request = render_provider_request(
        call_ordinal=operation,
        operation_ordinal=operation,
        private_requests=private_requests(),
        runtime_bindings=bindings(),
        authorization_reference=AUTHORIZATION,
    )
    assert request.body is not None
    assert expected_body_key in request.body
    assert b"runtime_binding" not in (request.body_bytes or b"")


def test_pending_authorization_cannot_render_request() -> None:
    with pytest.raises(L2ExecutionError):
        render_provider_request(
            call_ordinal=1,
            operation_ordinal=1,
            private_requests=private_requests(),
            runtime_bindings=bindings(),
            authorization_reference="AUTH-T07-L2-PENDING",
        )


class FakeTransport:
    def send(
        self,
        request: ProviderRequest,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> ProviderResponse:
        assert credential == "public-dummy-canary"
        assert timeout_seconds == 10
        return ProviderResponse(200, "application/json", b'{"data":[]}\n', 5)


class UnknownTransport:
    def send(
        self,
        request: ProviderRequest,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> ProviderResponse:
        raise RuntimeError("synthetic unknown")


class ClosedFailureTransport:
    def send(
        self,
        request: ProviderRequest,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> ProviderResponse:
        raise TransportFailure("tls_handshake", "tls_failure")


def _ledger(tmp_path: Path) -> FsyncL2ProviderLedger:
    schema_root = tmp_path / "schemas"
    schema_root.mkdir(mode=0o700, exist_ok=True)
    (schema_root / "t07-lambda-l2-provider-ledger.schema.json").write_bytes(
        (ROOT / "schemas/t07-lambda-l2-provider-ledger.schema.json").read_bytes()
    )
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700, exist_ok=True)
    ledger = FsyncL2ProviderLedger.create(
        tmp_path,
        path=run_root / "provider-request-ledger.jsonl",
        authorization_reference=AUTHORIZATION,
    )
    ledger.reserve_capacity()
    return ledger


def _request() -> ProviderRequest:
    return render_provider_request(
        call_ordinal=1,
        operation_ordinal=1,
        private_requests=private_requests(),
        runtime_bindings=bindings(),
        authorization_reference=AUTHORIZATION,
    )


def test_fake_request_has_fsync_terminal_ledger(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    response = execute_observed_request(
        ledger=ledger,
        transport=FakeTransport(),
        request=_request(),
        credential="public-dummy-canary",
        timeout_seconds=10,
    )
    assert response.status == 200
    snapshot = ledger.close()
    events = [json.loads(line) for line in snapshot.path.read_text().splitlines()]
    assert [event["event_type"] for event in events] == [
        "request_intent_committed",
        "request_send_started",
        "response_headers_received",
        "response_body_completed",
    ]
    assert all("public-dummy-canary" not in json.dumps(event) for event in events)


@pytest.mark.parametrize(
    ("transport", "terminal"),
    [
        (UnknownTransport(), "request_outcome_unknown_after_send"),
        (ClosedFailureTransport(), "request_failed"),
    ],
)
def test_failures_commit_terminal_sanitized_event(
    tmp_path: Path,
    transport: object,
    terminal: str,
) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(L2ExecutionError):
        execute_observed_request(
            ledger=ledger,
            transport=transport,  # type: ignore[arg-type]
            request=_request(),
            credential="public-dummy-canary",
            timeout_seconds=10,
        )
    snapshot = ledger.close()
    final = json.loads(snapshot.path.read_text().splitlines()[-1])
    assert final["event_type"] == terminal
    assert "public-dummy-canary" not in snapshot.path.read_text()


def test_ledger_is_exclusive_and_ordered(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(L2ExecutionError):
        ledger.append("request_send_started", request=_request())
    ledger.close()
    with pytest.raises(L2ExecutionError):
        _ledger(tmp_path)
