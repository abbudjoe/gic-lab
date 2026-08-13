from __future__ import annotations

import base64
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest
from harness_test_support import materialize_git_blob

from giclab.harness.lambda_cloud import InventoryRequest
from giclab.harness.lambda_inventory import RepositoryState
from giclab.harness.lambda_inventory_v3 import (
    InventoryHttpResponseV3,
    InventoryTransportObserver,
    ObservableInventoryTransport,
)
from giclab.harness.lambda_request_ledger_v3 import (
    FailureClass,
    FailureStage,
    InventoryObservedFailure,
    RequestLedgerSnapshot,
    SanitizedFailure,
)
from giclab.harness.lambda_ssh_key_archive import (
    ArchivedSSHKeyEvidence,
    InventoryArchiveError,
)
from giclab.harness.lambda_ssh_key_executor import (
    SSHKeyRunResult,
    execute_authorized_ssh_key_fingerprint,
)
from giclab.harness.lambda_ssh_key_fingerprint import (
    LOCAL_VERIFICATION_RELATIVE_PATH,
    PLAN_RELATIVE_PATH,
    RUN_ID,
    RUN_ROOT_RELATIVE_PATH,
    SSHKeyFingerprintPlan,
    SSHKeyRunBinding,
)
from giclab.harness.lambda_ssh_key_match import (
    LocalEvidenceBundle,
    discover_local_public_keys,
)
from giclab.harness.lambda_ssh_key_request_ledger import SSHKeyRequestLedgerError
from giclab.validation import ROOT

ACCOUNT_NAMES = (
    "aic-codex-lambda",
    "codex-fawx-20260527",
    "fractal-lambda-codex",
)
CANARY = "DUMMY-LAMBDA-L1A-CANARY"


def _ssh_string(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _public_key(seed: int) -> str:
    key = bytes((seed + index) % 256 for index in range(32))
    wire = _ssh_string(b"ssh-ed25519") + _ssh_string(key)
    return f"ssh-ed25519 {base64.b64encode(wire).decode()} fixture-{seed}"


def _response() -> bytes:
    return (
        json.dumps(
            {
                "data": [
                    {
                        "id": f"synthetic-id-{ordinal}",
                        "name": name,
                        "public_key": _public_key(ordinal),
                    }
                    for ordinal, name in enumerate(ACCOUNT_NAMES, start=1)
                ]
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def _copy_bound_repository(tmp_path: Path) -> tuple[Path, Path, dict[str, object], str]:
    repository = tmp_path / "repo"
    repository.mkdir()
    plan_source = ROOT / PLAN_RELATIVE_PATH
    plan_document = json.loads(plan_source.read_bytes())
    assert isinstance(plan_document, dict)
    implementation = plan_document["implementation_binding"]
    assert isinstance(implementation, dict)
    artifacts = implementation["implementation_artifacts"]
    assert isinstance(artifacts, list)
    plan_destination = repository / PLAN_RELATIVE_PATH
    plan_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(plan_source, plan_destination)
    for item in artifacts:
        assert isinstance(item, dict)
        materialize_git_blob(
            ROOT,
            str(implementation["implementation_commit"]),
            str(item["path"]),
            repository,
        )
    requests = plan_document["requests"]
    assert isinstance(requests, list) and len(requests) == 1
    request = requests[0]
    assert isinstance(request, dict)
    supplemental = {str(request["response_schema_path"])}
    ledger = plan_document["ledger_contract"]
    schema = plan_document["schema_contract"]
    assert isinstance(ledger, dict) and isinstance(schema, dict)
    supplemental.update(
        {
            str(ledger["schema_path"]),
            str(schema["fingerprint_schema_path"]),
            str(schema["match_schema_path"]),
        }
    )
    for relative in supplemental:
        if (repository / relative).exists():
            continue
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    plan_path = repository / PLAN_RELATIVE_PATH
    return (
        repository,
        plan_path,
        plan_document,
        hashlib.sha256(plan_path.read_bytes()).hexdigest(),
    )


@dataclass
class _FakeDeadline:
    closed: bool = False

    def close(self) -> None:
        self.closed = True


@dataclass
class _FakeTransport:
    body: bytes
    calls: int = 0

    def fetch(
        self,
        request: InventoryRequest,
        *,
        credential: str,
        timeout_seconds: float,
        observer: InventoryTransportObserver,
    ) -> InventoryHttpResponseV3:
        assert request.path == "/api/v1/ssh-keys"
        assert request.max_response_bytes == 131_072
        assert credential == CANARY
        assert timeout_seconds == 30
        self.calls += 1
        observer.response_headers_received(
            status_code=200,
            content_type="application/json",
            elapsed_ms=3,
        )
        observer.response_body_progress(
            bytes_received=len(self.body),
            status_code=200,
            content_type="application/json",
            elapsed_ms=4,
        )
        return InventoryHttpResponseV3(200, "application/json", self.body, 5)


@dataclass
class _FailAfterHeadersTransport:
    def fetch(
        self,
        request: InventoryRequest,
        *,
        credential: str,
        timeout_seconds: float,
        observer: InventoryTransportObserver,
    ) -> InventoryHttpResponseV3:
        del request, credential, timeout_seconds
        observer.response_headers_received(
            status_code=200,
            content_type="application/json",
            elapsed_ms=2,
        )
        raise InventoryObservedFailure(
            SanitizedFailure(
                FailureStage.RESPONSE_BODY,
                FailureClass.RESPONSE_BODY_FAILURE,
                "L1A_TEST_BODY_FAILURE",
            ),
            http_status=200,
            content_type="application/json",
            bytes_received=123,
            elapsed_ms=3,
        )


@dataclass
class _CrashAfterHeadersTransport:
    def fetch(
        self,
        request: InventoryRequest,
        *,
        credential: str,
        timeout_seconds: float,
        observer: InventoryTransportObserver,
    ) -> InventoryHttpResponseV3:
        del request, credential, timeout_seconds
        observer.response_headers_received(
            status_code=200,
            content_type="application/json",
            elapsed_ms=2,
        )
        raise RuntimeError("synthetic untyped post-send crash")


@dataclass
class _FakePreparedArchive:
    destination: Path
    staged: LocalEvidenceBundle | None = None
    closed: bool = False
    fail_finalize: bool = False

    def stage(self, bundle: LocalEvidenceBundle) -> None:
        assert self.staged is None
        self.staged = bundle

    def finalize(
        self,
        bundle: LocalEvidenceBundle,
        *,
        ledger: RequestLedgerSnapshot,
    ) -> ArchivedSSHKeyEvidence:
        assert bundle == self.staged
        if self.fail_finalize:
            raise InventoryArchiveError("synthetic finalization failure")
        ledger_sha = str(ledger.sha256)
        copy_sha = "b" * 64
        seal_sha = "a" * 64
        verification = (
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "plan_id": "PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1",
                    "run_id": RUN_ID,
                    "destination_path": str(self.destination),
                    "destination_copy_record_sha256": copy_sha,
                    "destination_seal_sha256": seal_sha,
                    "terminal_ledger_validated": True,
                    "source_destination_sha256_equal": True,
                    "source_retained_until_independent_verification": True,
                    "private_key_bytes_accessed": False,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        return ArchivedSSHKeyEvidence(
            destination=self.destination,
            seal_sha256=seal_sha,
            copy_record_sha256=copy_sha,
            ledger_sha256=ledger_sha,
            local_verification_record=verification,
        )

    def close(self) -> None:
        self.closed = True


@dataclass
class _FakeArchiver:
    prepared: _FakePreparedArchive

    def prepare(
        self,
        repository_root: Path,
        *,
        plan: SSHKeyFingerprintPlan,
        run_binding: SSHKeyRunBinding,
    ) -> _FakePreparedArchive:
        del repository_root, plan, run_binding
        return self.prepared


def _run_binding(plan: dict[str, object]) -> SSHKeyRunBinding:
    implementation = plan["implementation_binding"]
    assert isinstance(implementation, dict)
    return SSHKeyRunBinding(
        repository_commit="9" * 40,
        implementation_commit=str(implementation["implementation_commit"]),
        authorization_reference="AUTH-T07-L1A-UNIT-TEST",
        authorization_sha256="8" * 64,
    )


def _execute(
    tmp_path: Path,
    *,
    transport: ObservableInventoryTransport,
    prepared: _FakePreparedArchive | None = None,
) -> tuple[SSHKeyRunResult, Path, _FakePreparedArchive]:
    repository, plan_path, plan, plan_sha = _copy_bound_repository(tmp_path)
    home = tmp_path / "home"
    ssh_root = home / ".ssh"
    ssh_root.mkdir(parents=True)
    (ssh_root / "candidate.pub").write_text(_public_key(1), encoding="utf-8")
    (ssh_root / "candidate").write_text("synthetic-private-counterpart", encoding="utf-8")
    prepared = prepared or _FakePreparedArchive(tmp_path / "external" / RUN_ID)
    result = execute_authorized_ssh_key_fingerprint(
        repository_root=repository,
        plan_path=plan_path,
        plan_sha256=plan_sha,
        run_binding=_run_binding(plan),
        credential_provider=lambda: CANARY,
        transport=transport,
        archiver=_FakeArchiver(prepared),
        deadline_factory=lambda seconds: _FakeDeadline(),
        repository_inspector=lambda root, expected_commit: RepositoryState(
            "phase-1/sira-smoke-lambda",
            expected_commit,
            True,
        ),
        ancestry_verifier=lambda *args, **kwargs: None,
        local_key_discoverer=lambda: discover_local_public_keys(home_directory=home),
    )
    return result, repository, prepared


def test_fake_end_to_end_executor_composes_one_request_ledger_match_and_archive(
    tmp_path: Path,
) -> None:
    transport = _FakeTransport(_response())
    result, repository, prepared = _execute(tmp_path, transport=transport)
    assert transport.calls == result.provider_calls == 1
    assert result.match.sanitized_report["selection_state"] == (
        "unique-match-awaiting-user-approval"
    )
    assert result.match.sanitized_report["selection_authorized"] is False
    assert result.ledger.events == 13
    assert prepared.staged == result.bundle and prepared.closed
    assert (repository / LOCAL_VERIFICATION_RELATIVE_PATH).is_file()
    disposition = [
        json.loads(line)
        for line in (repository / LOCAL_VERIFICATION_RELATIVE_PATH).read_text().splitlines()
    ]
    assert [event["event_type"] for event in disposition] == [
        "archive_finalization_started",
        "archive_finalization_passed",
    ]
    assert result.archive_finalization.gate_l1a_evidence_complete
    public = json.dumps(result.match.sanitized_report, sort_keys=True)
    assert CANARY not in public
    assert "synthetic-id" not in public
    assert "SHA256:" not in public

    with pytest.raises(SSHKeyRequestLedgerError):
        execute_authorized_ssh_key_fingerprint(
            repository_root=repository,
            plan_path=repository / PLAN_RELATIVE_PATH,
            plan_sha256=hashlib.sha256((repository / PLAN_RELATIVE_PATH).read_bytes()).hexdigest(),
            run_binding=_run_binding(json.loads((repository / PLAN_RELATIVE_PATH).read_bytes())),
            credential_provider=lambda: (_ for _ in ()).throw(
                AssertionError("fresh run identity was reused")
            ),
            transport=_FakeTransport(_response()),
            archiver=_FakeArchiver(_FakePreparedArchive(tmp_path / "unused")),
            deadline_factory=lambda seconds: _FakeDeadline(),
            repository_inspector=lambda root, expected_commit: RepositoryState(
                "phase-1/sira-smoke-lambda", expected_commit, True
            ),
            ancestry_verifier=lambda *args, **kwargs: None,
            local_key_discoverer=lambda: (),
        )


def test_typed_failure_after_send_remains_exact_and_stops(tmp_path: Path) -> None:
    repository, plan_path, plan, plan_sha = _copy_bound_repository(tmp_path)
    prepared = _FakePreparedArchive(tmp_path / "external" / RUN_ID)
    with pytest.raises(InventoryObservedFailure):
        execute_authorized_ssh_key_fingerprint(
            repository_root=repository,
            plan_path=plan_path,
            plan_sha256=plan_sha,
            run_binding=_run_binding(plan),
            credential_provider=lambda: CANARY,
            transport=_FailAfterHeadersTransport(),
            archiver=_FakeArchiver(prepared),
            deadline_factory=lambda seconds: _FakeDeadline(),
            repository_inspector=lambda root, expected_commit: RepositoryState(
                "phase-1/sira-smoke-lambda", expected_commit, True
            ),
            ancestry_verifier=lambda *args, **kwargs: None,
            local_key_discoverer=lambda: (),
        )
    ledger = repository / RUN_ROOT_RELATIVE_PATH / "request-ledger.jsonl"
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert events[-2]["event_type"] == "request_failed"
    assert events[-2]["sanitized_failure_stage"] == "response_body"
    assert events[-2]["sanitized_failure_class"] == "response_body_failure"
    assert events[-2]["stable_error_code"] == "L1A_TEST_BODY_FAILURE"
    assert events[-2]["bytes_received_so_far"] == 123
    assert events[-2]["http_status"] == 200
    assert events[-2]["content_type"] == "application/json"
    assert events[-2]["elapsed_ms"] == 3
    assert events[-1]["event_type"] == "run_stopped"
    assert prepared.staged is None and prepared.closed
    assert CANARY not in ledger.read_text()


def test_untyped_failure_after_send_is_durably_unknown_and_stops(tmp_path: Path) -> None:
    repository, plan_path, plan, plan_sha = _copy_bound_repository(tmp_path)
    prepared = _FakePreparedArchive(tmp_path / "external" / RUN_ID)
    with pytest.raises(InventoryObservedFailure):
        execute_authorized_ssh_key_fingerprint(
            repository_root=repository,
            plan_path=plan_path,
            plan_sha256=plan_sha,
            run_binding=_run_binding(plan),
            credential_provider=lambda: CANARY,
            transport=_CrashAfterHeadersTransport(),
            archiver=_FakeArchiver(prepared),
            deadline_factory=lambda seconds: _FakeDeadline(),
            repository_inspector=lambda root, expected_commit: RepositoryState(
                "phase-1/sira-smoke-lambda", expected_commit, True
            ),
            ancestry_verifier=lambda *args, **kwargs: None,
            local_key_discoverer=lambda: (),
        )
    ledger = repository / RUN_ROOT_RELATIVE_PATH / "request-ledger.jsonl"
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert events[-2]["event_type"] == "request_outcome_unknown_after_send"
    assert events[-2]["sanitized_failure_class"] == "outcome_unknown"
    assert events[-1]["event_type"] == "run_stopped"
    assert CANARY not in ledger.read_text()


def test_response_schema_failure_preserves_completed_response_metadata(tmp_path: Path) -> None:
    repository, plan_path, plan, plan_sha = _copy_bound_repository(tmp_path)
    body = b'{"data":[]}\n'
    prepared = _FakePreparedArchive(tmp_path / "external" / RUN_ID)
    with pytest.raises(InventoryObservedFailure):
        execute_authorized_ssh_key_fingerprint(
            repository_root=repository,
            plan_path=plan_path,
            plan_sha256=plan_sha,
            run_binding=_run_binding(plan),
            credential_provider=lambda: CANARY,
            transport=_FakeTransport(body),
            archiver=_FakeArchiver(prepared),
            deadline_factory=lambda seconds: _FakeDeadline(),
            repository_inspector=lambda root, expected_commit: RepositoryState(
                "phase-1/sira-smoke-lambda", expected_commit, True
            ),
            ancestry_verifier=lambda *args, **kwargs: None,
            local_key_discoverer=lambda: (),
        )
    ledger = repository / RUN_ROOT_RELATIVE_PATH / "request-ledger.jsonl"
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert events[-2]["event_type"] == "request_failed"
    assert events[-2]["sanitized_failure_class"] == "schema_drift"
    assert events[-2]["bytes_received_so_far"] == len(body)
    assert events[-2]["http_status"] == 200
    assert events[-2]["content_type"] == "application/json"
    assert events[-2]["elapsed_ms"] == 5
    assert events[-1]["event_type"] == "run_stopped"


def test_archive_finalize_failure_has_separate_durable_ineligible_disposition(
    tmp_path: Path,
) -> None:
    repository, plan_path, plan, plan_sha = _copy_bound_repository(tmp_path)
    home = tmp_path / "home"
    ssh_root = home / ".ssh"
    ssh_root.mkdir(parents=True)
    (ssh_root / "candidate.pub").write_text(_public_key(1), encoding="utf-8")
    (ssh_root / "candidate").write_text("synthetic-private-counterpart", encoding="utf-8")
    prepared = _FakePreparedArchive(
        tmp_path / "external" / RUN_ID,
        fail_finalize=True,
    )
    with pytest.raises(InventoryObservedFailure):
        execute_authorized_ssh_key_fingerprint(
            repository_root=repository,
            plan_path=plan_path,
            plan_sha256=plan_sha,
            run_binding=_run_binding(plan),
            credential_provider=lambda: CANARY,
            transport=_FakeTransport(_response()),
            archiver=_FakeArchiver(prepared),
            deadline_factory=lambda seconds: _FakeDeadline(),
            repository_inspector=lambda root, expected_commit: RepositoryState(
                "phase-1/sira-smoke-lambda", expected_commit, True
            ),
            ancestry_verifier=lambda *args, **kwargs: None,
            local_key_discoverer=lambda: discover_local_public_keys(home_directory=home),
        )
    ledger = repository / RUN_ROOT_RELATIVE_PATH / "request-ledger.jsonl"
    request_events = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert request_events[-2]["event_type"] == "archive_passed"
    assert request_events[-1]["event_type"] == "run_stopped"
    disposition_path = repository / LOCAL_VERIFICATION_RELATIVE_PATH
    disposition = [json.loads(line) for line in disposition_path.read_text().splitlines()]
    assert disposition[-1]["event_type"] == "archive_finalization_failed"
    assert disposition[-1]["archive_finalization_state"] == "failed"
    assert disposition[-1]["gate_l1a_evidence_complete"] is False
    assert disposition[-1]["gate_l2_authorized"] is False
    assert disposition[-1]["stable_error_code"] == "L1A_ARCHIVE_FINALIZATION_FAILED"
    assert prepared.closed
    assert CANARY not in disposition_path.read_text()
