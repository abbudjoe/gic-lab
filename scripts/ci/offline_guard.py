"""Fail-closed Python test dispatch guard; container isolation is a separate layer.

Loaded by the explicit guarded launcher before collection, and propagated into
Python children. This is not a sandbox against arbitrary native code.
"""

from __future__ import annotations

import atexit
import contextlib
import fcntl
import json
import os
import socket
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
    if _bulk_root is not None:
        result.update({key: os.environ[key] for key in STORAGE_ENV_KEYS if key in os.environ})
    return result


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
        if not isinstance(raw, (list, tuple)) or not all(isinstance(v, str) for v in raw):
            _deny("process:unstructured")
        argv = list(raw)
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
    global _installed, _journal, _bulk_root, _bulk_identity
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
    native = subprocess.Popen

    class GuardedPopen(native):
        def __init__(self, args, *positional, **kwargs):
            if isinstance(args, (list, tuple)) and _python(list(args)):
                kwargs["env"] = child_environment(kwargs.get("env"))
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
