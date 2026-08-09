from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

import giclab.harness.sira_colima as colima_module
import giclab.harness.sira_storage as storage_module
from giclab.harness.sira_colima import (
    COLIMA_HOME,
    COLIMA_PROFILE,
    LIMA_PRIVATE_KEY,
    LIMA_SSH_SOCKET_PROBE,
    LIMA_UNIX_PATH_MAX,
    ColimaContractError,
    RollbackAction,
    RollbackCommandResult,
    RollbackOperation,
    RollbackOwnershipReceipt,
    RollbackPlan,
    RollbackResourceKind,
    RollbackTrigger,
    RuntimeDecisionState,
    TypedRollbackExecutor,
    create_fresh_rollback_directory_receipt,
    issue_existing_rollback_evidence_receipt,
    issue_held_storage_action_guard,
    load_colima_candidate_decision,
)
from giclab.harness.sira_storage import (
    APPROVED_EXTERNAL_CAPACITY_BYTES,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES,
    SEALED_ARTIFACT_ROOT,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_VOLUME_UUID,
    StorageContractError,
    VolumeObservation,
    WriterProbeProcessResult,
    lsof_writer_probe_argv,
    parse_lsof_open_writer_count,
    probe_open_writer_count,
)
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = ROOT / "containers/sira-smoke/colima/candidate-decision.json"
CANDIDATE_SHA256 = "45632a34ac609b321facc14393336c3455caab646dd3ecf716e989e90046f4e0"
SOURCE_OBSERVATIONS_PATH = ROOT / "containers/sira-smoke/colima/source-observations.json"
SOURCE_OBSERVATIONS_SHA256 = "cbf9d975eccf86b90993206e50f483d04f1a0aa8357a42a59a826ed6965f2e75"


def _external_observation(mount: Path, *, device_identifier: str = "disk99s5") -> VolumeObservation:
    return VolumeObservation(
        mount_path=mount,
        filesystem="apfs",
        writable=True,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        total_bytes=APPROVED_EXTERNAL_CAPACITY_BYTES,
        free_bytes=EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES,
        internal=False,
        owners_enabled=False,
        encrypted=True,
        unlocked=True,
        device_identifier=device_identifier,
        bus_protocol="Thunderbolt",
        device_tree_path="IODeviceTree:/UTDM@0",
    )


def _system_observation(mount: Path) -> VolumeObservation:
    return VolumeObservation(
        mount_path=mount,
        filesystem="apfs",
        writable=True,
        volume_uuid=SYSTEM_DATA_VOLUME_UUID,
        physical_store_uuid=None,
        total_bytes=SYSTEM_CAPACITY_BYTES,
        free_bytes=SYSTEM_CAPACITY_BYTES,
        internal=True,
        owners_enabled=True,
        encrypted=True,
        unlocked=True,
        device_identifier="disk3s1",
    )


def _bind_test_mounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, VolumeObservation, VolumeObservation]:
    external = tmp_path / "external"
    system = tmp_path / "system"
    external.mkdir()
    system.mkdir()
    monkeypatch.setattr(colima_module, "APPROVED_MOUNT", external)
    monkeypatch.setattr(colima_module, "SYSTEM_DATA_MOUNT", system)
    monkeypatch.setattr(storage_module, "APPROVED_MOUNT", external)
    monkeypatch.setattr(storage_module, "SYSTEM_DATA_MOUNT", system)
    return external, system, _external_observation(external), _system_observation(system)


def test_committed_colima_candidate_is_hash_bound_rejected_and_nonexecutable() -> None:
    assert hashlib.sha256(CANDIDATE_PATH.read_bytes()).hexdigest() == CANDIDATE_SHA256
    decision = load_colima_candidate_decision(
        CANDIDATE_PATH,
        expected_sha256=CANDIDATE_SHA256,
    )
    assert decision.state is RuntimeDecisionState.REJECTED
    assert decision.profile == COLIMA_PROFILE
    assert decision.colima_home == COLIMA_HOME
    assert decision.configuration["resolved_arch"] == "arm64"
    assert decision.configuration["memory_gib"] is None
    assert decision.configuration["disk_gib"] is None
    assert decision.executable_plan_id is None
    assert "LIMA_PRIVATE_KEY_ON_NOOWNERS_EXTERNAL_VOLUME" in decision.blockers
    assert (
        validate_instance(
            json.loads(CANDIDATE_PATH.read_text()),
            ROOT / "schemas/runtime-candidate-decision.schema.json",
        )
        == []
    )
    assert not list((CANDIDATE_PATH.parent).glob("*plan*"))


def test_decisive_source_observations_are_commit_or_signed_tag_bound() -> None:
    encoded = SOURCE_OBSERVATIONS_PATH.read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == SOURCE_OBSERVATIONS_SHA256
    document = json.loads(encoded)
    records = {record["record_id"]: record for record in document["records"]}
    assert records["LIMA-PRIVATE-KEY-CREATION"]["source_commit"] == (
        "de0816ea4bdc5267b428ab21025889b8dd785526"
    )
    assert "#L275-L390" in records["LIMA-PRIVATE-KEY-CREATION"]["immutable_url"]
    assert records["DOCKER-ENGINE-29-7-2-CURRENT"]["tag_object"] == (
        "d681cdaead9340bd36c513c7f5413a21bc679cfa"
    )
    for record_id in (
        "COLIMA-HOME-CACHE-ROOTS",
        "COLIMA-INITIAL-TEMP-YAML",
        "COLIMA-CONFIG-HOST-MOUNT-DISK-DEFAULTS",
        "COLIMA-EMPTY-MOUNTS-MEANS-HOME",
        "COLIMA-MOUNT-NONE-CLI",
        "COLIMA-DOCKER-CONTEXT-CREATION",
        "COLIMA-DOCKER-RUNTIME-UPDATE-PACKAGES",
        "COLIMA-DEB-RUNTIME-UPDATE",
        "LIMA-HARDCODED-CACHE",
    ):
        assert records[record_id]["source_commit"] in {
            "00f6c297e92a82c04a4ab507db0a61435650d7e8",
            "de0816ea4bdc5267b428ab21025889b8dd785526",
        }
        assert len(records[record_id]["source_blob_sha256"]) == 64
    assert document["payload_downloaded"] is False


def test_colima_candidate_cannot_hide_noowners_key_or_claim_ready(tmp_path: Path) -> None:
    raw = json.loads(CANDIDATE_PATH.read_text())
    raw["blockers"].remove("LIMA_PRIVATE_KEY_ON_NOOWNERS_EXTERNAL_VOLUME")
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(raw))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ColimaContractError, match="mandatory Lima-key blocker"):
        load_colima_candidate_decision(path, expected_sha256=digest)

    raw = json.loads(CANDIDATE_PATH.read_text())
    raw["decision_state"] = "ready-for-B2a-authorization"
    path.write_text(json.dumps(raw))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ColimaContractError, match="still contains blockers"):
        load_colima_candidate_decision(path, expected_sha256=digest)

    schema_errors = validate_instance(
        raw,
        ROOT / "schemas/runtime-candidate-decision.schema.json",
    )
    assert schema_errors


def test_gate_b17_documents_are_terminal_and_old_docker_plan_is_only_provenance() -> None:
    decision = (ROOT / "docs/harness/T07_GATE_B1_7_RUNTIME_DECISION.md").read_text()
    packet = (ROOT / "docs/harness/T07_GATE_B2A_COLIMA_AUTHORIZATION_PACKET.md").read_text()
    requirements = (ROOT / "docs/harness/T07_GATE_B2B_REQUIREMENTS.md").read_text()
    old_packet = (ROOT / "docs/harness/T07_GATE_B2A_INSTALL_AUTHORIZATION_PACKET.md").read_text()
    assert "runtime-candidate-rejected" in decision
    assert "no executable Gate B2a plan" in decision
    assert "Executable replacement plan ID: **none**" in packet
    assert "There is no ready-to-copy Gate B2a authorization block" in packet
    assert "requirements only" in requirements
    assert "no plan ID" in requirements
    assert "superseded, blocked provenance" in old_packet
    assert "I authorize" not in packet


def test_lima_private_key_and_socket_paths_are_explicit() -> None:
    assert LIMA_PRIVATE_KEY == COLIMA_HOME / "_lima/_config/user"
    assert len(bytes(LIMA_SSH_SOCKET_PROBE)) < LIMA_UNIX_PATH_MAX
    assert len(bytes(LIMA_SSH_SOCKET_PROBE)) == 102


def test_held_guard_reobserves_and_holds_mount_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    external, _, external_observation, system_observation = _bind_test_mounts(tmp_path, monkeypatch)

    def observations() -> tuple[VolumeObservation, VolumeObservation]:
        return external_observation, system_observation

    guard = issue_held_storage_action_guard(
        "start-colima-profile",
        fresh_observer=observations,
        system_floor_bytes=1,
        issued_monotonic_ns=100,
    )
    lease = guard.consume(fresh_observer=observations, now_monotonic_ns=101)
    assert guard.external_handle is None and guard.system_handle is None
    with pytest.raises(ColimaContractError, match="no longer owns"):
        guard.close_without_consuming()
    assert (
        lease.run(
            lambda: "bounded",
            fresh_observer=observations,
            now_monotonic_ns=102,
        )
        == "bounded"
    )
    assert lease.pre_action_verified
    assert lease.external_handle.closed and lease.system_handle.closed

    second = issue_held_storage_action_guard(
        "restart-colima-profile",
        fresh_observer=observations,
        system_floor_bytes=1,
        issued_monotonic_ns=200,
    )
    second_lease = second.consume(fresh_observer=observations, now_monotonic_ns=201)

    def replace_mount_path() -> None:
        external.rename(tmp_path / "external-original")
        external.mkdir()

    with pytest.raises(ColimaContractError, match="held mount identity"):
        second_lease.run(
            replace_mount_path,
            fresh_observer=observations,
            now_monotonic_ns=202,
        )
    assert second_lease.external_handle.closed and second_lease.system_handle.closed


def test_held_lease_is_consumed_and_postchecked_when_operation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, external, system = _bind_test_mounts(tmp_path, monkeypatch)
    observer_calls = 0

    def observations() -> tuple[VolumeObservation, VolumeObservation]:
        nonlocal observer_calls
        observer_calls += 1
        return external, system

    guard = issue_held_storage_action_guard(
        "start-colima-profile",
        fresh_observer=observations,
        system_floor_bytes=1,
        issued_monotonic_ns=100,
    )
    lease = guard.consume(fresh_observer=observations, now_monotonic_ns=101)
    operation_calls = 0

    def fail() -> None:
        nonlocal operation_calls
        operation_calls += 1
        raise RuntimeError("synthetic failure")

    with pytest.raises(RuntimeError, match="synthetic failure"):
        lease.run(fail, fresh_observer=observations, now_monotonic_ns=102)
    assert lease.finished and lease.pre_action_verified and lease.post_action_verified
    assert observer_calls == 4
    with pytest.raises(ColimaContractError, match="already used"):
        lease.run(fail, fresh_observer=observations, now_monotonic_ns=103)
    assert operation_calls == 1


def test_held_lease_revalidates_before_operation_and_has_a_start_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, external, system = _bind_test_mounts(tmp_path, monkeypatch)
    guard = issue_held_storage_action_guard(
        "start-colima-profile",
        fresh_observer=lambda: (external, system),
        system_floor_bytes=1,
        issued_monotonic_ns=100,
    )
    lease = guard.consume(
        fresh_observer=lambda: (external, system),
        now_monotonic_ns=101,
    )
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1

    with pytest.raises(ColimaContractError, match="stale before execution"):
        lease.run(
            operation,
            fresh_observer=lambda: (external, system),
            now_monotonic_ns=1_000_000_102,
        )
    assert calls == 0
    assert lease.external_handle.closed and lease.system_handle.closed


def test_held_guard_rejects_fresh_identity_drift_and_staleness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, external, system = _bind_test_mounts(tmp_path, monkeypatch)
    guard = issue_held_storage_action_guard(
        "create-colima-profile",
        fresh_observer=lambda: (external, system),
        system_floor_bytes=1,
        issued_monotonic_ns=100,
    )
    drifted = replace(external, device_identifier="disk100s5")
    with pytest.raises(ColimaContractError, match="changed before"):
        guard.consume(fresh_observer=lambda: (drifted, system), now_monotonic_ns=101)
    assert guard.external_handle.closed and guard.system_handle.closed

    stale = issue_held_storage_action_guard(
        "stop-colima-profile",
        fresh_observer=lambda: (external, system),
        system_floor_bytes=1,
        issued_monotonic_ns=100,
    )
    with pytest.raises(ColimaContractError, match="stale"):
        stale.consume(fresh_observer=lambda: (external, system), now_monotonic_ns=5_000_000_101)
    assert stale.external_handle.closed and stale.system_handle.closed


def _rollback_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RollbackPlan:
    runtime_root = tmp_path / "runtime"
    executable = runtime_root / "bin/colima"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic pinned colima\n")
    profile_path = tmp_path / "external/t07/colima-home"
    profile_path.parent.mkdir(parents=True)
    evidence_root = tmp_path / "evidence-root"
    evidence = evidence_root / "evidence"
    evidence.mkdir(parents=True)
    monkeypatch.setattr(colima_module, "RUNTIME_ROLLBACK_ROOT", runtime_root)
    monkeypatch.setattr(colima_module, "COLIMA_HOME", profile_path)
    monkeypatch.setattr(colima_module, "ROLLBACK_EVIDENCE_ROOTS", (evidence_root,))
    profile_receipt = create_fresh_rollback_directory_receipt(
        resource_id="colima-profile",
        attempt_id="t07-b2a-test",
        kind=RollbackResourceKind.COLIMA_PROFILE,
        path=profile_path,
        executable_path=executable,
    )
    evidence_receipt = issue_existing_rollback_evidence_receipt(
        resource_id="local-evidence",
        attempt_id="t07-b2a-test",
        path=evidence,
    )
    return RollbackPlan(
        plan_id="PLAN-T07-ROLLBACK-TEST",
        attempt_id="t07-b2a-test",
        trigger=RollbackTrigger.FAILED_RUNTIME_STARTUP,
        ownership_receipts=(profile_receipt, evidence_receipt),
        actions=(
            RollbackAction(
                action_id="stop-exact-profile",
                operation=RollbackOperation.STOP_COLIMA_PROFILE,
                resource_id="colima-profile",
                argv=(
                    str(executable),
                    "--profile",
                    COLIMA_PROFILE,
                    "stop",
                    "--force",
                ),
                path=None,
                timeout_seconds=60,
                output_limit_bytes=4096,
            ),
            RollbackAction(
                action_id="preserve-local-evidence",
                operation=RollbackOperation.PRESERVE_EVIDENCE,
                resource_id="local-evidence",
                argv=None,
                path=evidence,
                timeout_seconds=5,
                output_limit_bytes=1024,
            ),
        ),
    )


def test_typed_rollback_is_exact_single_use_zero_retry_and_schema_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[RollbackAction] = []
    paths: list[RollbackAction] = []
    executor = TypedRollbackExecutor(
        _rollback_plan(tmp_path, monkeypatch),
        command_runner=lambda action: (
            commands.append(action) or RollbackCommandResult(0, b"stopped\n", b"")
        ),
        path_runner=paths.append,
    )
    evidence = executor.execute()
    assert evidence.complete
    assert evidence.automatic_retries == 0
    assert len(commands) == 1 and len(paths) == 1
    assert (
        validate_instance(
            evidence.document(),
            ROOT / "schemas/runtime-rollback-evidence.schema.json",
        )
        == []
    )
    with pytest.raises(ColimaContractError, match="already executed"):
        executor.execute()


def test_typed_rollback_rejects_broad_or_wrong_identity_and_never_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _rollback_plan(tmp_path, monkeypatch)
    broad_action = replace(
        plan.actions[0],
        argv=("/bin/rm", "-rf", "/", COLIMA_PROFILE),
    )
    with pytest.raises(ColimaContractError, match="allowlisted template"):
        replace(plan, actions=(broad_action,)).validate()
    wrong_profile = replace(
        plan.actions[0],
        argv=("/opt/giclab/bin/colima", "--profile", "not-t07", "stop"),
    )
    with pytest.raises(ColimaContractError, match="allowlisted template"):
        replace(plan, actions=(wrong_profile,)).validate()

    root_receipt = RollbackOwnershipReceipt(
        resource_id="root-path",
        attempt_id=plan.attempt_id,
        kind=RollbackResourceKind.OWNED_PATH,
        path=Path("/"),
        observed_device=1,
        observed_inode=1,
        freshly_owned=True,
    )
    root_action = RollbackAction(
        action_id="remove-root",
        operation=RollbackOperation.REMOVE_OWNED_PATH,
        resource_id="root-path",
        argv=None,
        path=Path("/"),
        timeout_seconds=5,
        output_limit_bytes=1024,
    )
    with pytest.raises(ColimaContractError, match="issuer is not trusted"):
        replace(plan, ownership_receipts=(root_receipt,), actions=(root_action,)).validate()
    with pytest.raises(ColimaContractError, match="not an exact mutable root"):
        create_fresh_rollback_directory_receipt(
            resource_id="sealed-archive",
            attempt_id=plan.attempt_id,
            kind=RollbackResourceKind.OWNED_PATH,
            path=SEALED_ARTIFACT_ROOT,
        )

    calls = 0

    def fail_once(_: RollbackAction) -> RollbackCommandResult:
        nonlocal calls
        calls += 1
        return RollbackCommandResult(1, b"", b"failed")

    executor = TypedRollbackExecutor(plan, command_runner=fail_once, path_runner=lambda _: None)
    result = executor.execute()
    assert not result.complete
    assert calls == 1
    assert len(result.actions) == 1
    assert result.automatic_retries == 0


def test_writer_probe_uses_exact_array_and_counts_write_descriptors(tmp_path: Path) -> None:
    source = tmp_path / "attempt"
    source.mkdir()
    first = source / "one.log"
    second = source / "two.log"
    # Actual macOS ``lsof -F0`` framing retains newline record separators after
    # the NUL field terminator.  Directory descriptors with blank access are
    # included to keep the fixture representative.
    payload = (
        f"p123\0\nfcwd\0a \0n{source}\0\nf4\0aw\0n{first}\0"
        f"\nf5\0ar\0n{second}\0\np456\0\nf7\0au\0n{second}\0\n"
    ).encode()
    assert parse_lsof_open_writer_count(source, payload) == 2
    assert lsof_writer_probe_argv(source) == (
        "/usr/sbin/lsof",
        "-n",
        "-P",
        "+w",
        "-V",
        "-F0apfn",
        "+D",
        str(source),
    )

    seen: list[tuple[tuple[str, ...], int, int]] = []

    def runner(argv: tuple[str, ...], timeout: int, cap: int) -> WriterProbeProcessResult:
        seen.append((argv, timeout, cap))
        return WriterProbeProcessResult(0, payload, b"")

    assert probe_open_writer_count(source, runner=runner) == 2
    assert seen == [(lsof_writer_probe_argv(source), 10, 256 * 1024)]


def test_writer_probe_fails_closed_on_outside_path_or_process_error(tmp_path: Path) -> None:
    source = tmp_path / "attempt"
    source.mkdir()
    outside = tmp_path / "outside"
    payload = f"p123\0f4\0aw\0n{outside}\0".encode()
    with pytest.raises(StorageContractError, match="outside"):
        parse_lsof_open_writer_count(source, payload)
    with pytest.raises(StorageContractError, match="failed closed"):
        probe_open_writer_count(
            source,
            runner=lambda _argv, _timeout, _cap: WriterProbeProcessResult(2, b"", b"error"),
        )
    with pytest.raises(StorageContractError, match="failed closed"):
        probe_open_writer_count(
            source,
            runner=lambda _argv, _timeout, _cap: WriterProbeProcessResult(1, b"", b""),
        )
    no_match = (
        f"lsof: no file use located: {source}\n"
        f"lsof: no file use located: {source / 'evidence.txt'}\n"
    ).encode()
    assert (
        probe_open_writer_count(
            source,
            runner=lambda _argv, _timeout, _cap: WriterProbeProcessResult(1, no_match, b""),
        )
        == 0
    )
    assert (
        probe_open_writer_count(
            source,
            runner=lambda _argv, _timeout, _cap: WriterProbeProcessResult(1, b"", no_match),
        )
        == 0
    )
    with pytest.raises(StorageContractError, match="failed closed"):
        probe_open_writer_count(
            source,
            runner=lambda _argv, _timeout, _cap: WriterProbeProcessResult(
                1,
                b"",
                no_match + b"lsof: synthetic inspection error\n",
            ),
        )
    with pytest.raises(StorageContractError, match="failed closed"):
        probe_open_writer_count(
            source,
            runner=lambda _argv, _timeout, _cap: WriterProbeProcessResult(
                1,
                b"",
                no_match + f"lsof: no file use located: {outside}\n".encode(),
            ),
        )
    with pytest.raises(StorageContractError, match="failed closed"):
        probe_open_writer_count(
            source,
            runner=lambda _argv, _timeout, _cap: WriterProbeProcessResult(
                1,
                no_match,
                b"lsof: synthetic warning\n",
            ),
        )
