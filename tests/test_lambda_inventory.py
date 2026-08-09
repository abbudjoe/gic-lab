from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import ssl
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_lambda_cloud import PLAN_PATH, PLAN_SHA256, _responses

from giclab.harness import lambda_archive as archive
from giclab.harness import lambda_inventory as runner
from giclab.harness import sira_storage as storage
from giclab.harness.lambda_archive import ArchivedInventoryArtifact
from giclab.harness.lambda_cloud import (
    InventoryRunBinding,
    LambdaCloudContractError,
    load_inventory_plan,
)
from giclab.harness.sira_storage import (
    APPROVED_MOUNT,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_VOLUME_UUID,
    VolumeObservation,
)


class FakeInventoryTransport:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.request_ids: list[str] = []
        self.secret_retained = False

    def fetch(
        self,
        request,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> runner.InventoryHttpResponse:
        assert credential == "DUMMY-LAMBDA-SECRET-CANARY"
        assert 0 < timeout_seconds <= 60
        self.request_ids.append(request.request_id)
        return runner.InventoryHttpResponse(200, self.responses[request.request_id])


class FakePreparedArchive:
    def __init__(self, root: Path, record: bytes) -> None:
        self.root = root
        self.record = record
        self.closed = False
        self.calls = 0

    def archive(
        self,
        artifact_path: Path,
        *,
        artifact_sha256: str,
        artifact_bytes: int,
    ) -> ArchivedInventoryArtifact:
        self.calls += 1
        assert artifact_path.read_bytes()
        assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == artifact_sha256
        return ArchivedInventoryArtifact(
            destination=Path(
                "/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts/"
                "RUN-T07-L1-LAMBDA-INVENTORY-0001"
            ),
            artifact_sha256=artifact_sha256,
            artifact_bytes=artifact_bytes,
            seal_sha256="3" * 64,
            external_copy_record_sha256="4" * 64,
            local_verification_record=self.record,
        )

    def close(self) -> None:
        self.closed = True


class FakeArchiver:
    def __init__(self, record: bytes = b'{"archive":"verified"}\n') -> None:
        self.record = record
        self.prepared: FakePreparedArchive | None = None

    def prepare(self, repository_root, *, plan, plan_sha256, run_binding):
        self.prepared = FakePreparedArchive(repository_root, self.record)
        return self.prepared


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


def _binding() -> InventoryRunBinding:
    return InventoryRunBinding(
        run_id="RUN-T07-L1-LAMBDA-INVENTORY-0001",
        repository_commit="1" * 40,
        authorization_reference="AUTH-T07-L1-TEST",
        authorization_sha256="2" * 64,
    )


def _temporary_repository(tmp_path: Path) -> Path:
    schema_directory = tmp_path / "schemas"
    schema_directory.mkdir()
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / "schemas/t07-lambda-inventory.schema.json",
        schema_directory / "t07-lambda-inventory.schema.json",
    )
    return tmp_path


def test_l1_supervisor_uses_exact_get_set_and_seals_only_redacted_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _temporary_repository(tmp_path)
    monkeypatch.setattr(
        runner,
        "inspect_repository_state",
        lambda repository_root, expected_commit: runner.RepositoryState(
            branch="phase-1/sira-smoke-lambda",
            commit=expected_commit,
            clean=True,
        ),
    )
    transport = FakeInventoryTransport(_responses())
    archiver = FakeArchiver()
    deadlines = FakeDeadlineFactory()
    result = runner.execute_authorized_inventory(
        repository_root=root,
        plan_path=PLAN_PATH,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
        credential="DUMMY-LAMBDA-SECRET-CANARY",
        transport=transport,
        archiver=archiver,
        watchdog_factory=deadlines,
        clock=lambda: 0.0,
        sleeper=lambda _: None,
        utc_now=lambda: datetime(2026, 8, 9, 21, 0, tzinfo=UTC),
    )
    plan = load_inventory_plan(PLAN_PATH, expected_sha256=PLAN_SHA256)
    assert transport.request_ids == [request.request_id for request in plan.requests]
    assert result.provider_calls == 8
    assert result.selection_state == "selected"
    assert result.artifact.path == root / plan.output_relative_path
    encoded = result.artifact.path.read_bytes()
    assert b"DUMMY-LAMBDA-SECRET-CANARY" not in encoded
    document = json.loads(encoded)
    assert document["run_identity"]["repository_commit"] == "1" * 40
    assert document["authorization_binding"] == {
        "authorization_reference": "AUTH-T07-L1-TEST",
        "authorization_sha256": "2" * 64,
        "authorized": True,
    }
    assert document["limits"]["cloud_mutations"] == 0
    assert result.artifact.bytes == len(encoded)
    assert result.archive.artifact_sha256 == result.artifact.sha256
    assert result.copy_record.path == root / plan.copy_record_relative_path
    assert b"DUMMY-LAMBDA-SECRET-CANARY" not in result.copy_record.path.read_bytes()
    assert archiver.prepared is not None and archiver.prepared.closed
    assert [item.seconds for item in deadlines.deadlines] == [180, 60]
    assert all(item.closed for item in deadlines.deadlines)

    with pytest.raises(LambdaCloudContractError, match="already exists"):
        runner.seal_inventory_artifact(
            root,
            relative_path=plan.output_relative_path,
            encoded=encoded,
            max_bytes=plan.max_retained_output_bytes,
        )


def test_l1_supervisor_stops_on_status_or_wall_cap_without_leaking_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _temporary_repository(tmp_path)
    monkeypatch.setattr(
        runner,
        "inspect_repository_state",
        lambda repository_root, expected_commit: runner.RepositoryState(
            branch="phase-1/sira-smoke-lambda",
            commit=expected_commit,
            clean=True,
        ),
    )

    class StatusTransport(FakeInventoryTransport):
        def fetch(self, request, *, credential: str, timeout_seconds: float):
            return runner.InventoryHttpResponse(302, credential.encode())

    canary = "DUMMY-LAMBDA-SECRET-CANARY"
    with pytest.raises(LambdaCloudContractError) as captured:
        runner.execute_authorized_inventory(
            repository_root=root,
            plan_path=PLAN_PATH,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            credential=canary,
            transport=StatusTransport(_responses()),
            archiver=FakeArchiver(),
            watchdog_factory=FakeDeadlineFactory(),
            clock=lambda: 0.0,
            sleeper=lambda _: None,
        )
    assert canary not in str(captured.value)

    ticks = iter([0.0, 0.0, 181.0])
    with pytest.raises(LambdaCloudContractError, match="wall budget"):
        runner.execute_authorized_inventory(
            repository_root=root,
            plan_path=PLAN_PATH,
            plan_sha256=PLAN_SHA256,
            run_binding=_binding(),
            credential=canary,
            transport=FakeInventoryTransport(_responses()),
            archiver=FakeArchiver(),
            watchdog_factory=FakeDeadlineFactory(),
            clock=lambda: next(ticks),
            sleeper=lambda _: None,
        )


def test_l1_supervisor_paces_request_starts_inside_provider_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _temporary_repository(tmp_path)
    monkeypatch.setattr(
        runner,
        "inspect_repository_state",
        lambda repository_root, expected_commit: runner.RepositoryState(
            branch="phase-1/sira-smoke-lambda", commit=expected_commit, clean=True
        ),
    )
    now = [0.0]
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    runner.execute_authorized_inventory(
        repository_root=root,
        plan_path=PLAN_PATH,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
        credential="DUMMY-LAMBDA-SECRET-CANARY",
        transport=FakeInventoryTransport(_responses()),
        archiver=FakeArchiver(),
        watchdog_factory=FakeDeadlineFactory(),
        clock=lambda: now[0],
        sleeper=sleep,
        utc_now=lambda: datetime(2026, 8, 9, 21, 0, tzinfo=UTC),
    )
    assert sleeps == [1.0] * 7
    assert now[0] == 7.0


def test_process_deadline_watchdog_is_shell_free_and_secret_scrubbed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Process:
        returncode = 0

        def poll(self) -> None:
            return None

        def wait(self, *, timeout: int) -> int:
            assert timeout == 2
            return 0

        def kill(self) -> None:
            raise AssertionError("orderly watchdog must not be killed")

    def popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        os.write(kwargs["pass_fds"][1], b"R")
        return Process()

    monkeypatch.setenv("LAMBDA_API_KEY", "DUMMY-LAMBDA-SECRET-CANARY")
    monkeypatch.setenv("SIRA_API_KEY", "DUMMY-SIRA-SECRET-CANARY")
    monkeypatch.setenv("OPENAI_API_KEY", "DUMMY-OPENAI-SECRET-CANARY")
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    watchdog = runner.SubprocessDeadlineWatchdog.arm(180)
    watchdog.close()
    command = captured["command"]
    kwargs = captured["kwargs"]
    assert isinstance(command, list)
    assert command[1:4] == ["-m", "giclab.harness.lambda_inventory", "_deadline-watchdog"]
    assert command[-1] == "180"
    assert "shell" not in kwargs
    assert kwargs["env"] == runner.secret_free_child_environment()
    serialized = repr(captured)
    assert "DUMMY-LAMBDA-SECRET-CANARY" not in serialized
    assert "DUMMY-SIRA-SECRET-CANARY" not in serialized
    assert "DUMMY-OPENAI-SECRET-CANARY" not in serialized


def test_process_deadline_watchdog_real_helper_arms_and_disarms() -> None:
    watchdog = runner.SubprocessDeadlineWatchdog.arm(60)
    assert watchdog.process.poll() is None
    watchdog.close()
    assert watchdog.process.returncode == 0


def test_deadline_watchdog_kills_only_its_exact_parent_at_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    killed: list[tuple[int, int]] = []
    ticks = iter([0.0, 61.0])
    monkeypatch.setattr(runner.os, "getppid", lambda: 1234)
    monkeypatch.setattr(runner.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(runner.select, "select", lambda *args: ([], [], []))
    monkeypatch.setattr(runner.os, "write", lambda descriptor, content: len(content))
    monkeypatch.setattr(runner.os, "close", lambda descriptor: None)
    assert runner._deadline_watchdog_main(["9", "10", "1234", "60"]) == 124
    assert killed == [(1234, runner.signal.SIGKILL)]
    assert runner._deadline_watchdog_main(["9", "10", "9999", "60"]) == 2


def test_repository_guard_requires_exact_branch_commit_and_clean_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = iter(["wrong-branch\n", f"{'1' * 40}\n", ""])

    class Result:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout
            self.stderr = ""

    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return Result(next(outputs))

    monkeypatch.setenv("LAMBDA_API_KEY", "DUMMY-LAMBDA-SECRET-CANARY")
    monkeypatch.setenv("SIRA_API_KEY", "DUMMY-SIRA-SECRET-CANARY")
    monkeypatch.setenv("OPENAI_API_KEY", "DUMMY-OPENAI-SECRET-CANARY")
    monkeypatch.setattr(runner.subprocess, "run", run)
    with pytest.raises(LambdaCloudContractError, match="branch drifted"):
        runner.inspect_repository_state(tmp_path, expected_commit="1" * 40)
    assert len(calls) == 3
    assert all(arguments[0] == "/usr/bin/git" for arguments, _ in calls)
    assert all(kwargs["env"] == runner.secret_free_child_environment() for _, kwargs in calls)
    assert "DUMMY-LAMBDA-SECRET-CANARY" not in repr(calls)
    assert "DUMMY-SIRA-SECRET-CANARY" not in repr(calls)
    assert "DUMMY-OPENAI-SECRET-CANARY" not in repr(calls)


def test_diskutil_observer_scrubs_all_secret_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Result:
        returncode = 0
        stdout = b"synthetic-plist"
        stderr = b""

    def run(arguments, **kwargs):
        captured["arguments"] = arguments
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setenv("LAMBDA_API_KEY", "DUMMY-LAMBDA-SECRET-CANARY")
    monkeypatch.setenv("SIRA_API_KEY", "DUMMY-SIRA-SECRET-CANARY")
    monkeypatch.setenv("OPENAI_API_KEY", "DUMMY-OPENAI-SECRET-CANARY")
    monkeypatch.setattr(archive.subprocess, "run", run)
    assert archive._run_diskutil(("/usr/sbin/diskutil", "info", "-plist", "/synthetic")) == (
        b"synthetic-plist"
    )
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["env"] == runner.secret_free_child_environment()
    serialized = repr(captured)
    assert "DUMMY-LAMBDA-SECRET-CANARY" not in serialized
    assert "DUMMY-SIRA-SECRET-CANARY" not in serialized
    assert "DUMMY-OPENAI-SECRET-CANARY" not in serialized


def test_resolved_connection_does_not_restart_timeout_for_second_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    created = 0

    class FakeSocket:
        def settimeout(self, timeout: float) -> None:
            assert timeout <= 10

        def connect(self, address) -> None:
            now[0] = 11.0
            raise OSError("synthetic connect timeout")

        def close(self) -> None:
            return None

    def make_socket(*args):
        nonlocal created
        created += 1
        return FakeSocket()

    monkeypatch.setattr(runner.socket, "socket", make_socket)
    addresses = (
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.2", 443)),
    )
    connection = runner._ResolvedHTTPSConnection(
        addresses,
        deadline=10.0,
        clock=lambda: now[0],
        context=ssl.create_default_context(),
    )
    with pytest.raises(TimeoutError):
        connection.connect()
    assert created == 1


def test_archive_volume_guard_recomputes_floor_and_rejects_identity_drift() -> None:
    observation = VolumeObservation(
        mount_path=APPROVED_MOUNT,
        filesystem="apfs",
        writable=True,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        total_bytes=1_000_240_963_584,
        free_bytes=854_038_691_840,
        internal=False,
        owners_enabled=False,
        encrypted=True,
        unlocked=True,
        device_identifier="disk7s5",
        bus_protocol="Thunderbolt",
        device_tree_path="IODeviceTree:/UTDM/test",
    )
    assert archive._validate_external(observation, incremental_bytes=1_048_576) == 200_048_192_717
    with pytest.raises(archive.InventoryArchiveError, match="UUID drifted"):
        archive._validate_external(
            replace(observation, volume_uuid="00000000-0000-0000-0000-000000000000"),
            incremental_bytes=1_048_576,
        )
    with pytest.raises(archive.InventoryArchiveError, match="free-space floor"):
        archive._validate_external(
            replace(observation, free_bytes=200_048_192_717),
            incremental_bytes=1_048_576,
        )


def test_archive_root_creation_is_exact_nofollow_and_user_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mount = tmp_path / "external"
    mount.mkdir()
    monkeypatch.setattr(archive, "APPROVED_MOUNT", mount)
    external = archive._HeldDirectory.open(mount)
    root = mount / "GIC-Lab/t07/sealed-artifacts"
    held = archive._open_or_create_archive_root(external, root)
    try:
        assert root.is_dir()
        held.revalidate()
    finally:
        held.close()
        external.close()

    external = archive._HeldDirectory.open(mount)
    try:
        with pytest.raises(archive.InventoryArchiveError, match="approved exact path"):
            archive._open_or_create_archive_root(external, mount / "wrong")
    finally:
        external.close()


def _prepare_concrete_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[
    archive.PreparedInventoryArchive,
    Path,
    list[archive._HeldDirectory],
    archive.DiskutilVolumeObserver,
]:
    repository = tmp_path / "repository"
    external_mount = tmp_path / "external"
    system_mount = tmp_path / "system"
    repository.mkdir()
    external_mount.mkdir()
    system_mount.mkdir()
    archive_root = external_mount / "GIC-Lab/t07/sealed-artifacts"
    archive_root.mkdir(parents=True)
    plan = load_inventory_plan(PLAN_PATH, expected_sha256=PLAN_SHA256)
    object.__setattr__(plan, "archive_root", str(archive_root))
    source = repository / plan.output_relative_path
    source.parent.mkdir(parents=True)
    source.write_bytes(b'{"redacted":"inventory"}\n')

    monkeypatch.setattr(archive, "APPROVED_MOUNT", external_mount)
    monkeypatch.setattr(archive, "SYSTEM_DATA_MOUNT", system_mount)
    monkeypatch.setattr(storage, "SYSTEM_DATA_MOUNT", system_mount)
    source_device = source.stat().st_dev
    external_contract_device = source_device + 1_000_000
    opened: list[archive._HeldDirectory] = []
    original_open = archive._HeldDirectory.open

    def held(path: Path, *, device: int) -> archive._HeldDirectory:
        handle = original_open(path)
        handle.device = device
        opened.append(handle)
        return handle

    def fake_open(cls, path: Path) -> archive._HeldDirectory:
        if path == external_mount:
            return held(path, device=external_contract_device)
        return held(path, device=source_device)

    def fake_archive_root(
        external: archive._HeldDirectory, requested: Path
    ) -> archive._HeldDirectory:
        assert requested == archive_root
        return held(archive_root, device=external.device)

    def fake_revalidate(self: archive._HeldDirectory) -> None:
        if self.closed:
            raise archive.InventoryArchiveError("held archive descriptor closed early")

    monkeypatch.setattr(archive._HeldDirectory, "open", classmethod(fake_open))
    monkeypatch.setattr(archive._HeldDirectory, "revalidate", fake_revalidate)
    monkeypatch.setattr(archive, "_open_or_create_archive_root", fake_archive_root)

    external_observation = VolumeObservation(
        mount_path=external_mount,
        filesystem="apfs",
        writable=True,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        total_bytes=1_000_240_963_584,
        free_bytes=854_038_691_840,
        internal=False,
        owners_enabled=False,
        encrypted=True,
        unlocked=True,
        device_identifier="synthetic-external",
        bus_protocol="Thunderbolt",
        device_tree_path="IODeviceTree:/UTDM/synthetic",
    )
    system_observation = VolumeObservation(
        mount_path=system_mount,
        filesystem="apfs",
        writable=True,
        volume_uuid=SYSTEM_DATA_VOLUME_UUID,
        physical_store_uuid=None,
        total_bytes=SYSTEM_CAPACITY_BYTES,
        free_bytes=32 * 1024**3,
        internal=True,
        owners_enabled=True,
        encrypted=True,
        unlocked=True,
        device_identifier="synthetic-system",
    )

    class Observer(archive.DiskutilVolumeObserver):
        def __call__(self):
            self.calls += 1
            return external_observation, system_observation

    observer = Observer()
    archiver = archive.DurableInventoryArchiver(
        observer_factory=lambda: observer,
        clock=lambda: 0.0,
        utc_now=lambda: datetime(2026, 8, 9, 21, 0, tzinfo=UTC),
    )
    prepared = archiver.prepare(
        repository,
        plan=plan,
        plan_sha256=PLAN_SHA256,
        run_binding=_binding(),
    )
    return prepared, source, opened, observer


def test_concrete_archive_prepare_copy_verify_finalize_and_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, source, handles, observer = _prepare_concrete_archive(tmp_path, monkeypatch)
    encoded = source.read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    result = prepared.archive(source, artifact_sha256=digest, artifact_bytes=len(encoded))

    assert source.read_bytes() == encoded
    assert result.destination.is_dir()
    assert (result.destination / "inventory-redacted.json").read_bytes() == encoded
    external_record = json.loads((result.destination / "COPY_RECORD.json").read_bytes())
    seal = json.loads((result.destination / "SEAL.json").read_bytes())
    local_record = json.loads(result.local_verification_record)
    assert external_record["repository_commit"] == "1" * 40
    assert external_record["source_sha256"] == digest
    assert seal["files"][0]["sha256"] == digest
    assert local_record["destination_artifact_sha256"] == digest
    assert local_record["source_destination_sha256_equal"] is True
    assert (
        result.seal_sha256
        == hashlib.sha256((result.destination / "SEAL.json").read_bytes()).hexdigest()
    )
    assert observer.calls == 3
    assert all(handle.closed for handle in handles)
    assert not list(result.destination.parent.glob("*.partial"))


def test_concrete_archive_failure_retains_partial_evidence_and_closes_descriptors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, source, handles, _ = _prepare_concrete_archive(tmp_path, monkeypatch)
    encoded = source.read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    original_write = archive._write_exclusive_at
    calls = 0

    def fail_after_source(directory_fd: int, name: str, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise archive.InventoryArchiveError("synthetic retained failure")
        original_write(directory_fd, name, content)

    monkeypatch.setattr(archive, "_write_exclusive_at", fail_after_source)
    with pytest.raises(archive.InventoryArchiveError, match="synthetic retained failure"):
        prepared.archive(source, artifact_sha256=digest, artifact_bytes=len(encoded))
    partials = list((Path(prepared.plan.archive_root)).glob(".*.partial"))
    assert len(partials) == 1
    assert (partials[0] / "inventory-redacted.json").read_bytes() == encoded
    assert source.read_bytes() == encoded
    assert all(handle.closed for handle in handles)
