from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from giclab.harness.t09_cleanup_state import (
    CleanupTargetState,
    EarlyCleanupJournal,
)

ROOT = Path(__file__).resolve().parents[1]
VALID_ID = "a" * 64
OTHER_ID = "b" * 64


def _load_host_runner() -> ModuleType:
    path = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
    spec = importlib.util.spec_from_file_location("giclab_t09_v11_cidfile_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_cidfile(path: Path, content: bytes = b"") -> None:
    path.write_bytes(content)
    path.chmod(0o600)


def _journal(tmp_path: Path, host: ModuleType) -> EarlyCleanupJournal:
    return EarlyCleanupJournal.initialize(
        tmp_path / "early-cleanup-state",
        plan_id=host.PLAN_ID,
        host_run_id=host.HOST_RUN_ID,
        package_commit="a" * 40,
        plan_sha256="b" * 64,
        provider_instance_id="instance-owned-cidfile-fixture",
        provider_instance_identity_sha256="c" * 64,
        provider_started_at_epoch=1.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="d" * 64,
    )


def _legacy_v10_read(host: ModuleType, path: Path, *, prefix: list[str]) -> str | None:
    if not os.path.lexists(path):
        return None
    metadata = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != host._docker_cidfile_owner_uid(prefix)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) & 0o022
        or not 0 < metadata.st_size <= 65
    ):
        raise host.T09HostError("owned Docker container-ID file is unsafe")
    container_id = path.read_text(encoding="ascii").strip()
    if host.re.fullmatch(r"[a-f0-9]{64}", container_id) is None:
        raise host.T09HostError("owned Docker container-ID file is malformed")
    return container_id


def test_missing_and_safe_zero_length_cidfiles_are_publication_pending(tmp_path: Path) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "container.cid"

    assert host._read_owned_docker_cidfile(cidfile, prefix=["docker"]) is None
    _write_cidfile(cidfile)
    assert host._read_owned_docker_cidfile(cidfile, prefix=["docker"]) is None


def test_safe_zero_length_simulated_root_owned_cidfile_is_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "root-owned.cid"
    _write_cidfile(cidfile)
    monkeypatch.setattr(host, "_docker_cidfile_owner_uid", lambda _prefix: os.getuid())

    assert (
        host._read_owned_docker_cidfile(
            cidfile,
            prefix=["sudo", "-n", "docker"],
        )
        is None
    )


def test_zero_length_symlink_is_rejected(tmp_path: Path) -> None:
    host = _load_host_runner()
    target = tmp_path / "target.cid"
    cidfile = tmp_path / "container.cid"
    _write_cidfile(target)
    cidfile.symlink_to(target)

    with pytest.raises(host.T09HostError, match="container-ID file is unsafe"):
        host._read_owned_docker_cidfile(cidfile, prefix=["docker"])


def test_zero_length_nonregular_path_is_rejected(tmp_path: Path) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "container.cid"
    cidfile.mkdir()

    with pytest.raises(host.T09HostError, match="container-ID file is unsafe"):
        host._read_owned_docker_cidfile(cidfile, prefix=["docker"])


def test_zero_length_fifo_is_rejected_without_blocking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "container.cid"
    os.mkfifo(cidfile, 0o600)
    real_open = os.open

    def guarded_open(path: Path, flags: int) -> int:
        assert flags & os.O_NONBLOCK
        return real_open(path, flags)

    monkeypatch.setattr(host.os, "open", guarded_open)
    with pytest.raises(host.T09HostError, match="container-ID file is unsafe"):
        host._read_owned_docker_cidfile(cidfile, prefix=["docker"])


def test_zero_length_wrong_owner_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "container.cid"
    _write_cidfile(cidfile)
    monkeypatch.setattr(host, "_docker_cidfile_owner_uid", lambda _prefix: os.getuid() + 1)

    with pytest.raises(host.T09HostError, match="container-ID file is unsafe"):
        host._read_owned_docker_cidfile(cidfile, prefix=["docker"])


def test_zero_length_multiple_links_are_rejected(tmp_path: Path) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "container.cid"
    alias = tmp_path / "alias.cid"
    _write_cidfile(cidfile)
    os.link(cidfile, alias)

    with pytest.raises(host.T09HostError, match="container-ID file is unsafe"):
        host._read_owned_docker_cidfile(cidfile, prefix=["docker"])


@pytest.mark.parametrize("mode", [0o620, 0o602])
def test_zero_length_group_or_world_writable_file_is_rejected(
    tmp_path: Path,
    mode: int,
) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "container.cid"
    _write_cidfile(cidfile)
    cidfile.chmod(mode)

    with pytest.raises(host.T09HostError, match="container-ID file is unsafe"):
        host._read_owned_docker_cidfile(cidfile, prefix=["docker"])


@pytest.mark.parametrize(
    "content",
    [
        b"a" * 63,
        b"A" * 64,
        b"g" * 64,
        b" " + b"a" * 64,
        b"a" * 64 + b" ",
        b"a" * 64 + b"\n\n",
        b"a" * 64 + b"\n" + b"b" * 64,
    ],
    ids=[
        "partial",
        "uppercase",
        "nonhex",
        "whitespace-prefix",
        "whitespace-suffix",
        "extra-newline",
        "multiple-lines",
    ],
)
def test_nonzero_malformed_or_oversized_cidfile_is_rejected(
    tmp_path: Path,
    content: bytes,
) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "container.cid"
    _write_cidfile(cidfile, content)

    with pytest.raises(host.T09HostError, match="container-ID file is malformed"):
        host._read_owned_docker_cidfile(cidfile, prefix=["docker"])


@pytest.mark.parametrize("content", [VALID_ID.encode(), f"{VALID_ID}\n".encode()])
def test_exact_lowercase_id_and_optional_single_newline_are_accepted(
    tmp_path: Path,
    content: bytes,
) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "container.cid"
    _write_cidfile(cidfile, content)

    assert host._read_owned_docker_cidfile(cidfile, prefix=["docker"]) == VALID_ID


def test_opened_descriptor_does_not_follow_a_replaced_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "container.cid"
    original = tmp_path / "opened-original.cid"
    replacement = tmp_path / "replacement.cid"
    _write_cidfile(cidfile, VALID_ID.encode())
    _write_cidfile(replacement, OTHER_ID.encode())
    real_fstat = host.os.fstat
    replaced = False

    def replace_after_open(descriptor: int) -> os.stat_result:
        nonlocal replaced
        metadata = real_fstat(descriptor)
        if not replaced:
            cidfile.rename(original)
            cidfile.symlink_to(replacement)
            replaced = True
        return metadata

    monkeypatch.setattr(host.os, "fstat", replace_after_open)

    assert host._read_owned_docker_cidfile(cidfile, prefix=["docker"]) == VALID_ID
    assert cidfile.is_symlink()


def test_category3_zero_length_sequence_is_pending_then_authoritative(tmp_path: Path) -> None:
    host = _load_host_runner()
    cidfile = tmp_path / "category3.cid"
    _write_cidfile(cidfile)

    with pytest.raises(host.T09HostError, match="container-ID file is unsafe"):
        _legacy_v10_read(host, cidfile, prefix=["docker"])
    assert host._read_owned_docker_cidfile(cidfile, prefix=["docker"]) is None

    cidfile.write_text(VALID_ID, encoding="ascii")
    assert host._read_owned_docker_cidfile(cidfile, prefix=["docker"]) == VALID_ID


def test_delayed_publication_registers_exact_identity_before_completion_and_cleans_by_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    journal = _journal(tmp_path, host)
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir(mode=0o700)
    role = "utility-cidfile-publication"
    name = f"{host.CONTAINER_PREFIX}{role}"
    registration_observations: list[tuple[str, str, dict[str, str]]] = []
    removal_ids: list[str] = []
    original_register = host.register_owned_container_cleanup

    def capture_registration(
        cleanup_journal: EarlyCleanupJournal,
        identity: object,
        *,
        role: str,
    ) -> None:
        registration_observations.append((identity.container_id, identity.name, identity.labels))
        original_register(cleanup_journal, identity, role=role)

    class DelayedPopen:
        returncode: int | None = None

        def __init__(self, argv: list[str], **_kwargs: object) -> None:
            self.argv = argv
            self.cidfile = Path(argv[argv.index("--cidfile") + 1])
            _write_cidfile(self.cidfile)
            self.iteration = 0

        def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
            if timeout is None:
                return b"", b""
            if self.iteration == 0:
                assert not any(
                    target.target_id.startswith("owned-container-")
                    for target in journal.load().targets
                )
                self.cidfile.write_text(VALID_ID, encoding="ascii")
                self.iteration += 1
                raise subprocess.TimeoutExpired(self.argv, timeout)
            target = next(
                item
                for item in journal.load().targets
                if item.target_id == f"owned-container-{VALID_ID}"
            )
            assert target.state is CleanupTargetState.OWNED
            self.returncode = 0
            return b"", b""

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    identity = host.OwnedContainerIdentity(
        VALID_ID,
        name,
        {
            "giclab.t09.plan": host.PLAN_ID,
            "giclab.t09.host_run": host.HOST_RUN_ID,
            "giclab.t09.role": role,
        },
    )
    monkeypatch.setattr(host.subprocess, "Popen", DelayedPopen)
    monkeypatch.setattr(host, "register_owned_container_cleanup", capture_registration)
    monkeypatch.setattr(host, "_container_id_by_exact_name", lambda *_args: None)
    monkeypatch.setattr(host, "inspect_owned_container", lambda *_args, **_kwargs: identity)
    monkeypatch.setattr(
        host,
        "remove_container",
        lambda *_args, expected_container_id, **_kwargs: (
            removal_ids.append(expected_container_id) is None
        ),
    )

    result = host.run_owned_docker(
        ["docker", "run", "fixture-image"],
        prefix=["docker"],
        label="cidfile-publication",
        owned_role=role,
        evidence_root=evidence_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        cleanup_journal=journal,
    )

    assert result.returncode == 0
    assert registration_observations == [
        (
            VALID_ID,
            name,
            {
                "giclab.t09.plan": host.PLAN_ID,
                "giclab.t09.host_run": host.HOST_RUN_ID,
                "giclab.t09.role": role,
            },
        )
    ]
    assert removal_ids == [VALID_ID]
    target = next(
        item for item in journal.load().targets if item.target_id == f"owned-container-{VALID_ID}"
    )
    assert target.state is CleanupTargetState.REMOVED


def test_later_different_published_id_is_terminal_and_cleanup_keeps_original_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    journal = _journal(tmp_path, host)
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir(mode=0o700)
    role = "utility-cidfile-change"
    name = f"{host.CONTAINER_PREFIX}{role}"
    removal_ids: list[str] = []

    class ChangedPopen:
        returncode: int | None = None

        def __init__(self, argv: list[str], **_kwargs: object) -> None:
            self.argv = argv
            self.cidfile = Path(argv[argv.index("--cidfile") + 1])
            _write_cidfile(self.cidfile, VALID_ID.encode())
            self.changed = False

        def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
            if timeout is not None and not self.changed:
                self.cidfile.write_text(OTHER_ID, encoding="ascii")
                self.changed = True
                raise subprocess.TimeoutExpired(self.argv, timeout)
            return b"", b""

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    identity = host.OwnedContainerIdentity(
        VALID_ID,
        name,
        {
            "giclab.t09.plan": host.PLAN_ID,
            "giclab.t09.host_run": host.HOST_RUN_ID,
            "giclab.t09.role": role,
        },
    )
    monkeypatch.setattr(host.subprocess, "Popen", ChangedPopen)
    monkeypatch.setattr(host, "_container_id_by_exact_name", lambda *_args: None)
    monkeypatch.setattr(host, "inspect_owned_container", lambda *_args, **_kwargs: identity)
    monkeypatch.setattr(
        host,
        "remove_container",
        lambda *_args, expected_container_id, **_kwargs: (
            removal_ids.append(expected_container_id) is None
        ),
    )

    with pytest.raises(host.T09HostError, match="container-ID changed after publication"):
        host.run_owned_docker(
            ["docker", "run", "fixture-image"],
            prefix=["docker"],
            label="cidfile-change",
            owned_role=role,
            evidence_root=evidence_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            cleanup_journal=journal,
        )

    assert removal_ids == [VALID_ID]
    assert not any(
        target.target_id == f"owned-container-{OTHER_ID}" for target in journal.load().targets
    )


def test_zero_length_until_deadline_never_gains_cleanup_authority_or_name_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _load_host_runner()
    journal = _journal(tmp_path, host)
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir(mode=0o700)
    name_lookups: list[str] = []
    monotonic_values = iter((100.0, 101.0))

    class PendingPopen:
        returncode: int | None = None

        def __init__(self, argv: list[str], **_kwargs: object) -> None:
            self.argv = argv
            self.cidfile = Path(argv[argv.index("--cidfile") + 1])
            _write_cidfile(self.cidfile)

        def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
            assert timeout is None
            return b"", b""

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    def exact_name_absence(_prefix: list[str], name: str) -> None:
        name_lookups.append(name)
        return None

    monkeypatch.setattr(host.subprocess, "Popen", PendingPopen)
    monkeypatch.setattr(host.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(host, "_container_id_by_exact_name", exact_name_absence)
    monkeypatch.setattr(
        host,
        "inspect_owned_container",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("no exact ID means no inspect authority")
        ),
    )
    monkeypatch.setattr(
        host,
        "remove_container",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("no exact ID means no removal authority")
        ),
    )

    with pytest.raises(subprocess.TimeoutExpired) as raised:
        host.run_owned_docker(
            ["docker", "run", "fixture-image"],
            prefix=["docker"],
            label="cidfile-timeout",
            evidence_root=evidence_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1,
            cleanup_journal=journal,
        )

    assert raised.value.timeout == 1
    assert len(name_lookups) == 2
    assert not any(
        target.target_id.startswith("owned-container-") for target in journal.load().targets
    )
    receipt = json.loads(
        (evidence_root / "cidfile-timeout.container-cleanup.json").read_text(encoding="utf-8")
    )
    assert receipt["container_id"] is None
    assert receipt["cleanup_authority_registered"] is False
    assert receipt["container_absent_after_run"] is True
