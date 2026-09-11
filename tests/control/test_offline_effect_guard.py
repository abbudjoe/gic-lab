"""Real local subprocess/IPC checks for the explicitly installed CI guard."""

import json
import os
import socket
import subprocess
import sys

import pytest


@pytest.mark.parametrize("argv", [["docker", "info"], ["sudo", "-n", "docker", "info"]])
def test_environmental_process_denied_before_creation(argv):
    from offline_guard import EffectDenied, expected_denial

    with (
        expected_denial("standalone-process-boundary", f"process:{argv[0]}"),
        pytest.raises(EffectDenied, match="offline guard denied"),
    ):
        subprocess.run(argv, check=False, timeout=1)


def test_child_keeps_guard_with_replaced_environment():
    script = """
import sys, subprocess
from offline_guard import EffectDenied, expected_denial
assert "sitecustomize" in sys.modules
with expected_denial("child-runtime-boundary", "process:docker"):
    try:
        subprocess.run(["docker", "info"], timeout=1)
    except EffectDenied:
        print("rejected-before-dispatch")
    else:
        raise AssertionError("child escaped")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={"PATH": os.defpath},
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    assert result.stdout.strip() == "rejected-before-dispatch"


def test_guard_precedes_import_and_preserves_denial_evidence(tmp_path):
    from offline_guard import EffectDenied, expected_denial

    source = tmp_path / "unsafe_fixture.py"
    source.write_text('import subprocess\nsubprocess.run(["docker", "info"], timeout=1)\n')
    with (
        expected_denial("module-setup-boundary", "process:docker"),
        pytest.raises(EffectDenied),
    ):
        exec(compile(source.read_bytes(), str(source), "exec"), {})
    records = []
    from pathlib import Path

    for path in Path(os.environ["GICLAB_CI_GUARD_JOURNAL"]).glob("*.jsonl"):
        records.extend(json.loads(line) for line in path.read_text().splitlines())
    assert any(record["expected_by"] == "module-setup-boundary" for record in records)


def test_authorized_python_pipe_and_private_socket_work(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"],
        input=b"exact-local-pipe",
        capture_output=True,
        timeout=5,
        check=True,
    )
    assert result.stdout == b"exact-local-pipe"
    # socketpair exercises actual private IPC without a host listener or network.
    left, right = socket.socketpair()
    with left, right:
        left.sendall(b"exact-unix-frame")
        assert right.recv(32) == b"exact-unix-frame"


def test_external_network_denied_before_connect():
    from offline_guard import EffectDenied, expected_denial

    with (
        socket.socket() as connection,
        expected_denial("external-network-boundary", "socket.connect"),
        pytest.raises(EffectDenied),
    ):
        connection.connect(("192.0.2.1", 443))


@pytest.fixture
def bound_bulk_guard(tmp_path, monkeypatch):
    """Explicit narrower filesystem input for the same guard on Mac and Linux."""
    import tempfile

    import offline_guard

    for name in ("tmp", "guard", "uv"):
        (tmp_path / name).mkdir()
    meta = tmp_path.stat()
    values = {
        "GICLAB_CI_BULK_ROOT": str(tmp_path),
        "GICLAB_CI_BULK_DEVICE": str(meta.st_dev),
        "GICLAB_CI_BULK_INODE": str(meta.st_ino),
        "GICLAB_CI_GUARD_JOURNAL": str(tmp_path / "guard"),
        "TMPDIR": str(tmp_path / "tmp"),
        "TMP": str(tmp_path / "tmp"),
        "TEMP": str(tmp_path / "tmp"),
        "UV_CACHE_DIR": str(tmp_path / "uv"),
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(offline_guard, "_journal", tmp_path / "guard")
    monkeypatch.setattr(offline_guard, "_bulk_root", tmp_path)
    monkeypatch.setattr(offline_guard, "_bulk_identity", (meta.st_dev, meta.st_ino))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))


def test_child_preserves_explicit_bulk_temp_when_environment_is_replaced(bound_bulk_guard):
    from offline_guard import STORAGE_ENV_KEYS

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import tempfile,os; print(tempfile.gettempdir()); print(os.environ['UV_CACHE_DIR'])",
        ],
        env={"PATH": os.defpath},
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    assert result.stdout.splitlines() == [os.environ["TMPDIR"], os.environ["UV_CACHE_DIR"]]
    assert "TMPDIR" in STORAGE_ENV_KEYS


def test_internal_temp_fallback_is_rejected_before_creation(bound_bulk_guard):
    import tempfile

    from offline_guard import EffectDenied, expected_denial

    with (
        expected_denial("explicit-internal-temp-denial", "storage:outside-bound-root"),
        pytest.raises(EffectDenied, match="storage:outside-bound-root"),
    ):
        tempfile.mkdtemp(prefix="t09-forbidden-bulk-", dir="/tmp")


def test_mount_loss_cannot_be_caught_and_reported_as_success(tmp_path, bound_bulk_guard):
    output = tmp_path / "never-written"
    script = """
import offline_guard, pathlib, sys
offline_guard._bulk_identity = (-1, -1)
try:
    pathlib.Path(sys.argv[1]).write_text('denied')
except offline_guard.EffectDenied as error:
    print(str(error), flush=True)
else:
    raise AssertionError('mount loss escaped')
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(output)],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 90
    assert result.stdout.strip() == "bound bulk mount unavailable; no internal fallback"
    assert not output.exists()


def test_real_scratch_git_fixture_and_pathlike_arguments_keep_hooks_disabled(tmp_path):
    from pathlib import Path

    import offline_guard

    assert tmp_path.is_relative_to(offline_guard._git_fixture_root)
    repo = tmp_path / "repository"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", repo], check=True, timeout=5)
    for key, value in (("user.name", "Guard Test"), ("user.email", "guard@example.invalid")):
        subprocess.run(["git", "-C", repo, "config", key, value], check=True, timeout=5)
    sentinel = tmp_path / "hook-executed"
    hooks = repo / ".git/hooks"
    hooks.mkdir()
    hook = hooks / "post-commit"
    hook.write_text("#!/bin/sh\nprintf escaped > '" + str(sentinel) + "'\n")
    hook.chmod(0o700)
    (repo / "source.txt").write_text("actual local fixture bytes\n")
    subprocess.run(["git", "-C", repo, "add", repo / "source.txt"], check=True, timeout=5)
    environment = dict(os.environ)
    environment["GIT_INDEX_FILE"] = str(tmp_path / "foreign-index")
    subprocess.run(
        ["git", "-C", repo, "commit", "-q", "-m", "fixture"], env=environment, check=True, timeout=5
    )
    observed = subprocess.run(
        ["git", "-C", repo, "show", "HEAD:source.txt"], capture_output=True, check=True, timeout=5
    )
    assert observed.stdout == b"actual local fixture bytes\n"
    snapshot = subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    ).stdout.strip()
    checkout_hook = hooks / "post-checkout"
    checkout_hook.write_bytes(hook.read_bytes())
    checkout_hook.chmod(0o700)
    subprocess.run(
        ["git", "-C", repo, "switch", "--quiet", "--detach", snapshot], check=True, timeout=5
    )
    assert not sentinel.exists() and not Path(environment["GIT_INDEX_FILE"]).exists()


@pytest.mark.parametrize(
    "operation", ["fetch", "config-hook", "alternate-gitdir", "outside-root", "branch-switch"]
)
def test_scratch_git_guard_rejects_unbound_mutation_before_dispatch(tmp_path, operation):
    from pathlib import Path

    import offline_guard
    from offline_guard import EffectDenied, expected_denial

    repo = tmp_path / "repository"
    repo.mkdir()
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True, timeout=5)
    commands = {
        "fetch": ["git", "-C", repo, "fetch", "https://example.invalid/never"],
        "config-hook": ["git", "-C", repo, "config", "core.hooksPath", str(tmp_path)],
        "alternate-gitdir": ["git", "--git-dir=" + str(repo / ".git"), "commit", "-m", "never"],
        "outside-root": ["git", "-C", offline_guard._git_fixture_root.parent, "init", "-q"],
        "branch-switch": ["git", "-C", repo, "switch", "--quiet", "main"],
    }
    with expected_denial("scratch-git-" + operation, "process:git"), pytest.raises(EffectDenied):
        subprocess.run(commands[operation], check=False, timeout=5)
    assert not (repo / ".git/FETCH_HEAD").exists()
    assert not (repo / ".git/refs/heads/master").exists()
    assert not (repo / ".git/refs/heads/main").exists()
    assert Path(repo / ".git/config").read_text().find("hooksPath") == -1


def test_parity_worktree_admission_rejects_other_targets_and_revisions(tmp_path, monkeypatch):
    import offline_guard

    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / ".git").mkdir()
    scratch = tmp_path / "parity"
    scratch.mkdir()
    monkeypatch.setattr(offline_guard, "_parity_repository", repository)
    monkeypatch.setattr(offline_guard, "_parity_base", "a" * 40)
    target = scratch / "base"
    command = ["git", "-C", str(repository), "worktree", "add", "--detach", str(target), "a" * 40]
    assert offline_guard._parity_git_allowed(command, None)
    for replacement in (str(repository / "base"), str(tmp_path / "other"), "/outside/base"):
        wrong = [*command[:-2], replacement, command[-1]]
        assert not offline_guard._parity_git_allowed(wrong, None)
    assert not offline_guard._parity_git_allowed([*command[:-1], "b" * 40], None)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    alias = scratch / "alias"
    alias.symlink_to(foreign, target_is_directory=True)
    assert not offline_guard._parity_git_allowed(
        [*command[:-2], str(alias / "base"), command[-1]], None
    )
    assert not target.exists()


def test_local_shared_fixture_clone_retains_history_and_fixed_commit_clock(tmp_path):
    from pathlib import Path

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True, timeout=5)
    (source / "member").write_text("bounded fixture\n")
    subprocess.run(["git", "-C", str(source), "add", "--all"], check=True, timeout=5)
    environment = dict(os.environ)
    environment.update(
        GIT_AUTHOR_DATE="2026-09-01T00:00:00+00:00", GIT_COMMITTER_DATE="2026-09-01T00:00:00+00:00"
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        env=environment,
        check=True,
        timeout=5,
    )
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--shared", "--quiet", str(source), str(clone)], check=True, timeout=5
    )
    result = subprocess.run(
        ["git", "-C", str(clone), "show", "-s", "--format=%aI%n%cI", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
        timeout=5,
    )
    assert result.stdout.splitlines() == ["2026-09-01T00:00:00+00:00"] * 2
    assert (clone / "member").read_text() == "bounded fixture\n"
    assert (
        Path((clone / ".git/objects/info/alternates").read_text().strip())
        == source / ".git/objects"
    )


def test_shared_clone_cannot_select_url_or_symlink_or_foreign_destination(tmp_path):
    import offline_guard
    from offline_guard import EffectDenied, expected_denial

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True, timeout=5)
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    for name, origin, target in (
        ("url", "https://example.invalid/never", str(tmp_path / "url")),
        ("alias", str(alias), str(tmp_path / "via-alias")),
        ("foreign", str(source), str(offline_guard._git_fixture_root.parent / "foreign-clone")),
    ):
        with expected_denial("clone-" + name, "process:git"), pytest.raises(EffectDenied):
            subprocess.run(
                ["git", "clone", "--shared", "--quiet", origin, target], check=False, timeout=5
            )


def test_shared_clone_rejects_linked_alternate_metadata_before_dispatch(tmp_path):
    import offline_guard
    from offline_guard import EffectDenied, expected_denial

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True, timeout=5)
    info = source / ".git/objects/info"
    info.rename(source / ".git/objects/retained-info")
    info.symlink_to(tmp_path / "absent-foreign-target", target_is_directory=True)
    assert not offline_guard._safe_source_objects(str(source / ".git/objects"))
    with expected_denial("linked-alternate", "process:git"), pytest.raises(EffectDenied):
        subprocess.run(
            ["git", "clone", "--shared", "--quiet", str(source), str(tmp_path / "clone")],
            check=False,
            timeout=5,
        )
    assert not (tmp_path / "clone").exists()
