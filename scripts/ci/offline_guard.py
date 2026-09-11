"""Fail-closed Python test dispatch guard; container isolation is a separate layer.

Loaded by the explicit guarded launcher before collection, and propagated into
Python children. This is not a sandbox against arbitrary native code.
"""

from __future__ import annotations

import atexit
import configparser
import contextlib
import fcntl
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

_installed = False
_local = threading.local()
_unexpected = False
_count = 0
_lock = threading.Lock()
_journal: Path | None = None
_ipc_roots: set[Path] = set()
_bulk_root: Path | None = None
_bulk_identity: tuple[int, int] | None = None
_git_fixture_root: Path | None = None
_parity_repository: Path | None = None
_parity_base: str | None = None
_GIT_FIXTURE_PREFIX = (
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "init.templateDir=",
    "-c",
    "protocol.allow=never",
    "-c",
    "gc.auto=0",
    "-c",
    "maintenance.auto=false",
)
STORAGE_ENV_KEYS = (
    "UV_PROJECT_ENVIRONMENT",
    "COVERAGE_FILE",
    "QUARTO_LOG",
    "TMPDIR",
    "TMP",
    "TEMP",
    "UV_CACHE_DIR",
    "UV_PYTHON_INSTALL_DIR",
    "PIP_CACHE_DIR",
    "XDG_CACHE_HOME",
    "DENO_DIR",
    "RUFF_CACHE_DIR",
    "MYPY_CACHE_DIR",
    "UV_OFFLINE",
    "UV_PYTHON_DOWNLOADS",
    "GICLAB_CI_BULK_ROOT",
    "GICLAB_CI_BULK_DEVICE",
    "GICLAB_CI_BULK_INODE",
)


class EffectDenied(RuntimeError):
    """An environmental operation was rejected before dispatch."""


@contextlib.contextmanager
def expected_denial(name: str, operation: str):
    """Expect exactly one named denial; never remove or clear journal records."""
    if not name or not operation or getattr(_local, "expected", None) is not None:
        raise ValueError("a denial expectation must be named, exact, and unnested")
    scope = {"name": name, "operation": operation, "count": 0}
    _local.expected = scope
    try:
        yield
    finally:
        _local.expected = None
        if scope["count"] != 1:
            raise AssertionError("expected exactly one intercepted operation")


def _deny(operation: str) -> None:
    global _unexpected, _count
    scope = getattr(_local, "expected", None)
    expected = scope is not None and scope["operation"] == operation and scope["count"] == 0
    if expected:
        scope["count"] += 1
    else:
        _unexpected = True
    record = {"operation": operation, "expected_by": scope["name"] if expected else None}
    assert _journal is not None
    with _lock:
        _count += 1
        if _count > 4096:
            os._exit(91)
        fd = os.open(
            _journal / f"{os.getpid()}.jsonl",
            os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
        try:
            os.write(fd, (json.dumps(record, sort_keys=True) + "\n").encode())
        finally:
            os.close(fd)
    raise EffectDenied(f"offline guard denied {operation}")


def _python(argv: list[str]) -> bool:
    return bool(argv) and Path(argv[0]).resolve() == Path(sys.executable).resolve()


def child_environment(environment=None):
    """Preserve the guard even when a retained bootstrap selects its own imports."""
    result = dict(os.environ if environment is None else environment)
    result["GICLAB_CI_GUARD_JOURNAL"] = os.environ["GICLAB_CI_GUARD_JOURNAL"]
    guard_root = str(Path(__file__).resolve().parent)
    paths = result.get("PYTHONPATH", "").split(os.pathsep)
    result["PYTHONPATH"] = os.pathsep.join(
        [guard_root, *[p for p in paths if p and p != guard_root]]
    )
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    result["GICLAB_CI_GUARD_IPC_ROOTS"] = json.dumps(sorted(map(str, _ipc_roots)))
    if _git_fixture_root is not None:
        result["GICLAB_CI_GIT_FIXTURE_ROOT"] = str(_git_fixture_root)
        result["PYTEST_DEBUG_TEMPROOT"] = str(_git_fixture_root)
    for name in (
        "GICLAB_CI_SOURCE_OBJECTS",
        "GICLAB_CI_PARITY_REPOSITORY",
        "GICLAB_CI_PARITY_BASE",
    ):
        if name in os.environ:
            result[name] = os.environ[name]
    result.update({key: os.environ[key] for key in STORAGE_ENV_KEYS if key in os.environ})
    return result


def _argv_paths(raw):
    if not isinstance(raw, (list, tuple)) or not all(
        isinstance(v, (str, bytes, os.PathLike)) for v in raw
    ):
        return None
    return [os.fsdecode(v) for v in raw]


def _fixture_git_allowed(argv, cwd):
    try:
        return _inspect_fixture_git(argv, cwd)
    except (OSError, ValueError, configparser.Error):
        _deny("process:git")


def _inside_git_fixture_scope(path):
    if (
        _git_fixture_root is not None
        and path != _git_fixture_root
        and path.is_relative_to(_git_fixture_root)
    ):
        return True
    # The immutable base conformance uses this specific tempfile allocation.
    # Admit only a recorded allocation under the launcher's private temporary
    # root, never a directory inferred from its name alone.
    temporary = os.environ.get("TMPDIR")
    if temporary is None:
        return False
    for root in _ipc_roots:
        if (
            root.name.startswith("giclab-t09-live-conformance-")
            and root.parent == Path(temporary).resolve()
            and path != root
            and path.is_relative_to(root)
        ):
            meta = root.lstat()
            return (
                stat.S_ISDIR(meta.st_mode)
                and meta.st_uid == os.getuid()
                and stat.S_IMODE(meta.st_mode) == 0o700
            )
    return False


def _inspect_fixture_git(argv, cwd):
    """Only local fixture construction in the launcher's isolated pytest scratch.

    These are real local repository fixtures, with native hooks, signing,
    templates, protocols and automatic maintenance disabled before dispatch.
    This is neither product Git authority nor arbitrary native-code containment.
    """
    if _git_fixture_root is None:
        return False
    command = argv[1:]
    repository = Path(cwd or os.getcwd()).absolute()
    if command[:1] == ["-C"] and len(command) >= 3:
        repository = (repository / command[1]).absolute()
        command = command[2:]
    while command[:1] == ["-c"]:
        if len(command) < 3:
            return False
        key, equal, value = command[1].partition("=")
        if (
            key not in {"user.name", "user.email"}
            or not equal
            or not value
            or len(value) > 256
            or "\n" in value
        ):
            return False
        command = command[2:]
    if not command or command[0] not in {"init", "config", "add", "commit", "switch"}:
        return False
    operation, arguments = command[0], command[1:]
    if operation == "init":
        targets = [v for v in arguments if v not in {"-q", "--quiet"}]
        if len(targets) > 1 or any(v.startswith("-") for v in targets):
            return False
        if targets:
            repository = (repository / targets[0]).absolute()
    if (
        not _inside_git_fixture_scope(repository)
        or ".." in repository.parts
        or any(p.is_symlink() for p in (repository, *repository.parents))
        or not repository.is_dir()
        or repository.stat().st_uid != os.getuid()
    ):
        return False
    dotgit = repository / ".git"
    if os.path.lexists(dotgit):
        meta = dotgit.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.getuid():
            return False
        if os.path.lexists(dotgit / "commondir"):
            return False
        alternates = dotgit / "objects/info/alternates"
        if any(p.is_symlink() for p in (dotgit / "objects", alternates.parent)):
            return False
        if os.path.lexists(alternates):
            bound = os.environ.get("GICLAB_CI_SOURCE_OBJECTS")
            if (
                bound is None
                or alternates.is_symlink()
                or not alternates.is_file()
                or alternates.stat().st_size > 4096
                or not _safe_source_objects(alternates.read_text().removesuffix("\n"))
            ):
                return False
        config = dotgit / "config"
        metadata = config.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > 16384
            or metadata.st_nlink != 1
            or metadata.st_uid != os.getuid()
        ):
            return False
        parser = configparser.RawConfigParser(strict=True)
        parser.read_string(config.read_text())
        allowed = {
            "core": {
                "repositoryformatversion",
                "filemode",
                "bare",
                "logallrefupdates",
                "ignorecase",
                "precomposeunicode",
            },
            "user": {"name", "email"},
        }
        for section in parser.sections():
            if section == 'remote "origin"':
                if (
                    set(parser[section]) != {"url", "fetch"}
                    or parser[section]["fetch"] != "+refs/heads/*:refs/remotes/origin/*"
                ):
                    return False
                if not _safe_source_objects(str(Path(parser[section]["url"]) / ".git/objects")):
                    return False
            elif section.startswith('branch "'):
                if (
                    set(parser[section]) != {"remote", "merge"}
                    or parser[section]["remote"] != "origin"
                    or not parser[section]["merge"].startswith("refs/heads/")
                ):
                    return False
            elif section not in allowed or not set(parser[section]) <= allowed[section]:
                return False
    elif operation != "init":
        return False
    if operation == "init":
        return True
    if operation == "config":
        return (
            len(arguments) == 2
            and arguments[0] in {"user.name", "user.email"}
            and len(arguments[1]) <= 256
            and "\n" not in arguments[1]
        )
    if operation == "switch":
        values = [value for value in arguments if value not in {"-q", "--quiet"}]
        return (
            len(values) == 2
            and values[0] == "--detach"
            and len(values[1]) == 40
            and all(character in "0123456789abcdef" for character in values[1])
        )
    if operation == "add":
        return bool(arguments) and all(
            value in {"--", "--all", "-A"}
            or (
                not value.startswith("-")
                and ".." not in Path(value).parts
                and (repository / value).resolve().is_relative_to(repository)
            )
            for value in arguments
        )
    messages = 0
    while arguments:
        value, *arguments = arguments
        if value in {"-q", "--quiet", "--allow-empty"}:
            continue
        if value == "-am":
            value = "-m"  # Native tracked-file fixture update; hooks remain disabled.
        if value != "-m" or not arguments or len(arguments[0]) > 4096:
            return False
        _, *arguments = arguments
        messages += 1
    return messages == 1


def _safe_source_objects(value, seen=frozenset()):
    """Read-only alternate object storage inside the bound input or fixture roots."""
    path = Path(value)
    bound = os.environ.get("GICLAB_CI_SOURCE_OBJECTS")
    if value in seen or len(seen) >= 4:
        return False
    valid = (
        path.is_absolute()
        and ".." not in path.parts
        and path.name == "objects"
        and path.parent.name == ".git"
        and (value == bound or _inside_git_fixture_scope(path))
        and not any(p.is_symlink() for p in (path, *path.parents))
        and path.is_dir()
        and path.stat().st_uid == os.getuid()
    )
    if not valid:
        return False
    alternate = path / "info/alternates"
    if alternate.parent.is_symlink():
        return False
    if os.path.lexists(alternate):
        if alternate.is_symlink() or not alternate.is_file() or alternate.stat().st_size > 4096:
            return False
        lines = alternate.read_text().splitlines()
        return len(lines) == 1 and _safe_source_objects(lines[0], seen | {value})
    return True


def _local_clone_allowed(argv, cwd):
    del cwd
    if len(argv) != 6 or argv[1:4] != ["clone", "--shared", "--quiet"]:
        return False
    source, destination = Path(argv[4]), Path(argv[5])
    return (
        _safe_source_objects(str(source / ".git/objects"))
        and _git_fixture_root is not None
        and destination.is_absolute()
        and _inside_git_fixture_scope(destination)
        and ".." not in destination.parts
        and not os.path.lexists(destination)
        and not any(p.is_symlink() for p in (destination, *destination.parents))
        and destination.parent.is_dir()
        and destination.parent.stat().st_uid == os.getuid()
    )


def _parity_git_allowed(argv, cwd):
    """Exact local detached-base lifecycle; never general Git mutation authority."""
    command = argv[1:]
    repository = Path(cwd or os.getcwd()).absolute()
    if command[:1] == ["-C"] and len(command) >= 3:
        repository = (repository / command[1]).absolute()
        command = command[2:]
    if not command or command[0] != "worktree":
        return False
    if command == ["worktree", "list", "--porcelain", "-z"]:
        return True  # A read-only registration query.
    if any(p.is_symlink() for p in (repository, *repository.parents)):
        return False
    actual = repository == _parity_repository
    if actual:
        if not (repository / ".git").is_dir():
            return False
    elif not _fixture_git_allowed([argv[0], "-C", str(repository), "add", "--", "fixture"], cwd):
        return False
    if len(command) == 5 and command[1:3] == ["add", "--detach"]:
        target, commit = Path(command[3]), command[4]
        if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
            return False
        if actual and commit != _parity_base:
            return False
        if os.path.lexists(target):
            return False
    elif len(command) == 4 and command[1:3] == ["remove", "--force"]:
        target = Path(command[3])
        if not target.is_dir() or target.is_symlink():
            return False
        metadata = target / ".git"
        if metadata.is_symlink() or not metadata.is_file() or metadata.stat().st_size > 4096:
            return False
        text = metadata.read_text()
        expected = repository / ".git/worktrees"
        if not text.startswith("gitdir: "):
            return False
        linked = Path(text.removeprefix("gitdir: ").strip())
        if not linked.is_relative_to(expected) or any(
            p.is_symlink() for p in (linked, *linked.parents)
        ):
            return False
    else:
        return False
    if not target.is_absolute() or target.name != "base" or ".." in target.parts:
        return False
    if target.is_relative_to(repository) or repository.is_relative_to(target):
        return False
    if any(p.is_symlink() for p in (target, *target.parents)):
        return False
    parent = target.parent
    if not parent.is_dir() or parent.stat().st_uid != os.getuid():
        return False
    return (_git_fixture_root is not None and parent.is_relative_to(_git_fixture_root)) or (
        parent in _ipc_roots and parent.name.startswith("giclab-pytest-parity-")
    )


def _check_bulk_write(path, dir_fd=None):
    global _unexpected
    if _bulk_root is None or isinstance(path, int):
        return
    try:
        meta = _bulk_root.lstat()
        valid = not _bulk_root.is_symlink() and (meta.st_dev, meta.st_ino) == _bulk_identity
    except OSError:
        valid = False
    if not valid:
        # The journal is on the missing volume too. Do not recurse into a new
        # journal write or fall back internally; caught errors still fail exit.
        _unexpected = True
        raise EffectDenied("bound bulk mount unavailable; no internal fallback")
    value = Path(os.fsdecode(path)).absolute()
    if dir_fd is not None and dir_fd != -1 and not Path(os.fsdecode(path)).is_absolute():
        if sys.platform == "darwin":
            parent = os.fsdecode(fcntl.fcntl(dir_fd, fcntl.F_GETPATH, b"\0" * 1024).split(b"\0")[0])
        else:
            parent = os.readlink(f"/proc/self/fd/{dir_fd}")
        value = Path(parent) / os.fsdecode(path)
    if str(value) == os.devnull:
        return
    if not value.is_relative_to(_bulk_root) or not value.resolve().is_relative_to(_bulk_root):
        _deny("storage:outside-bound-root")


def _audit(event, args):
    if event in {"tempfile.mkdtemp", "tempfile.mkstemp", "os.mkdir"}:
        _check_bulk_write(args[0], args[2] if event == "os.mkdir" else None)
    if event == "open":
        path, _mode, flags = args
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            _check_bulk_write(path)
    if event == "tempfile.mkdtemp":
        # Track concrete test-owned allocations, not arbitrary socket filenames.
        _ipc_roots.add(Path(args[0]).resolve())
    if event in {"os.system", "os.exec", "os.posix_spawn"}:
        _deny(event)
    if event == "subprocess.Popen":
        executable, raw, _cwd, env = args
        argv = _argv_paths(raw)
        if argv is None:
            _deny("process:unstructured")
        assert argv is not None
        name = Path(executable).name
        if _python(argv):
            if any(v in {"-I", "-E", "-S"} for v in argv[1:]):
                _deny("process:unguarded-python")
            selected = os.environ if env is None else env
            if selected.get("GICLAB_CI_GUARD_JOURNAL") != str(_journal) or str(
                Path(__file__).resolve().parent
            ) not in selected.get("PYTHONPATH", "").split(os.pathsep):
                _deny("process:unguarded-python")
            return
        if name == "git":
            command = argv[1:]
            if tuple(command[: len(_GIT_FIXTURE_PREFIX)]) == _GIT_FIXTURE_PREFIX:
                selected = os.environ if env is None else env
                required = {
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_SYSTEM": os.devnull,
                    "GIT_TERMINAL_PROMPT": "0",
                }
                for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
                    if selected.get(name) == "2026-09-01T00:00:00+00:00":
                        required[name] = selected[name]
                if {k: v for k, v in selected.items() if k.startswith("GIT_")} != required:
                    _deny("process:git")
                admitted = command[len(_GIT_FIXTURE_PREFIX) :]
                if admitted[:2] == ["-c", "protocol.file.allow=always"]:
                    if _local_clone_allowed([argv[0], *admitted[2:]], _cwd):
                        return
                    _deny("process:git")
                if (
                    _fixture_git_allowed([argv[0], *command[len(_GIT_FIXTURE_PREFIX) :]], _cwd)
                    or _local_clone_allowed([argv[0], *command[len(_GIT_FIXTURE_PREFIX) :]], _cwd)
                    or _parity_git_allowed([argv[0], *command[len(_GIT_FIXTURE_PREFIX) :]], _cwd)
                ):
                    return
                _deny("process:git")
            if command[:1] == ["-C"]:
                command = command[2:]
            if command and command[0] in {
                "show",
                "rev-parse",
                "merge-base",
                "ls-tree",
                "cat-file",
                "diff",
                "status",
                "archive",
                "log",
                "ls-files",
            }:
                return
        _deny(f"process:{name}")
    if event in {"socket.bind", "socket.connect"}:
        sock, address = args
        if sock.family == socket.AF_UNIX:
            value = Path(os.fsdecode(address)).resolve()
            if any(value.is_relative_to(root) for root in _ipc_roots):
                return
        # Explicit numeric loopback only. Container --network=none is independent.
        elif isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return
        _deny(event)
    if event == "socket.getaddrinfo" and args[0] not in {"127.0.0.1", "::1", "localhost"}:
        _deny(event)


def install() -> None:
    global _installed, _journal, _bulk_root, _bulk_identity, _git_fixture_root
    global _parity_repository, _parity_base
    if _installed:
        return
    _journal = Path(os.environ["GICLAB_CI_GUARD_JOURNAL"])
    if not _journal.is_absolute() or _journal.is_symlink() or not _journal.is_dir():
        raise RuntimeError("guard requires an existing private journal directory")
    if "GICLAB_CI_BULK_ROOT" in os.environ:
        _bulk_root = Path(os.environ["GICLAB_CI_BULK_ROOT"])
        _bulk_identity = (
            int(os.environ["GICLAB_CI_BULK_DEVICE"]),
            int(os.environ["GICLAB_CI_BULK_INODE"]),
        )
        _check_bulk_write(os.environ["TMPDIR"])
        # tempfile's normal missing-directory fallback must not choose /tmp.
        tempfile.tempdir = os.environ["TMPDIR"]
    _ipc_roots.update(
        Path(p) for p in json.loads(os.environ.get("GICLAB_CI_GUARD_IPC_ROOTS", "[]"))
    )
    if "GICLAB_CI_GIT_FIXTURE_ROOT" in os.environ:
        _git_fixture_root = Path(os.environ["GICLAB_CI_GIT_FIXTURE_ROOT"])
        if not _git_fixture_root.is_absolute() or any(
            p.is_symlink() for p in (_git_fixture_root, *_git_fixture_root.parents)
        ):
            raise RuntimeError("Git fixture root is not an explicit safe scratch path")
    if "GICLAB_CI_PARITY_REPOSITORY" in os.environ:
        _parity_repository = Path(os.environ["GICLAB_CI_PARITY_REPOSITORY"])
        _parity_base = os.environ["GICLAB_CI_PARITY_BASE"]
        if (
            not _parity_repository.is_absolute()
            or any(p.is_symlink() for p in (_parity_repository, *_parity_repository.parents))
            or len(_parity_base) != 40
            or any(c not in "0123456789abcdef" for c in _parity_base)
        ):
            raise RuntimeError("invalid exact parity source binding")
    native = subprocess.Popen

    class GuardedPopen(native):
        def __init__(self, args, *positional, **kwargs):
            normalized = _argv_paths(args)
            if normalized is not None and _python(normalized):
                kwargs["env"] = child_environment(kwargs.get("env"))
            elif (
                normalized
                and Path(normalized[0]).name == "git"
                and (
                    _fixture_git_allowed(normalized, kwargs.get("cwd"))
                    or _parity_git_allowed(normalized, kwargs.get("cwd"))
                    or _local_clone_allowed(normalized, kwargs.get("cwd"))
                )
            ):
                extra = (
                    ["-c", "protocol.file.allow=always"]
                    if _local_clone_allowed(normalized, kwargs.get("cwd"))
                    else []
                )
                args = [normalized[0], *_GIT_FIXTURE_PREFIX, *extra, *normalized[1:]]
                environment = os.environ if kwargs.get("env") is None else kwargs["env"]
                kwargs["env"] = {k: v for k, v in environment.items() if not k.startswith("GIT_")}
                for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
                    if environment.get(name) == "2026-09-01T00:00:00+00:00":
                        kwargs["env"][name] = environment[name]
                kwargs["env"].update(
                    GIT_CONFIG_NOSYSTEM="1",
                    GIT_CONFIG_SYSTEM=os.devnull,
                    GIT_CONFIG_GLOBAL=os.devnull,
                    GIT_TERMINAL_PROMPT="0",
                )
            super().__init__(args, *positional, **kwargs)

    subprocess.Popen = GuardedPopen
    sys.addaudithook(_audit)
    _installed = True

    def finish():
        if _unexpected:
            os._exit(90)

    atexit.register(finish)


def pytest_sessionfinish(session, exitstatus):
    """A caught violation in this process or a child still fails the gate."""
    assert _journal is not None
    for path in _journal.glob("*.jsonl"):
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            session.exitstatus = 1
            return
        for line in path.read_text().splitlines():
            if json.loads(line)["expected_by"] is None:
                session.exitstatus = 1
