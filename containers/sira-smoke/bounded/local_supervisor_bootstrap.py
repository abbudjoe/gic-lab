"""Hash-first loader for the local T07 bounded-smoke supervisor.

This file imports only the standard library until it has read and verified the exact
contract and supervisor modules named by the immutable plan.  Import is inert.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

MAX_MODULE_BYTES: Final = 2_097_152
_BOOTSTRAP_OPTIONS: Final = ("--supervisor-file", "--supervisor-sha256")
_CLEANUP_OPERATIONS: Final = frozenset({"cleanup-openai-secret", "abort-openai-secret"})


class LocalSupervisorBootstrapError(RuntimeError):
    """The local hash-first capability could not be established."""


def _option(argv: list[str], name: str) -> str:
    positions = [index for index, value in enumerate(argv) if value == name]
    if len(positions) != 1 or positions[0] + 1 >= len(argv):
        raise LocalSupervisorBootstrapError(f"{name} must occur exactly once")
    value = argv[positions[0] + 1]
    if not value or value.startswith("--") or "\x00" in value:
        raise LocalSupervisorBootstrapError(f"{name} has an invalid value")
    return value


def _read_exact(path: Path) -> bytes:
    try:
        linked = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise LocalSupervisorBootstrapError("bound module is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(linked.st_mode)
            or stat.S_ISLNK(linked.st_mode)
            or linked.st_nlink != 1
            or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
            or not 0 < opened.st_size <= MAX_MODULE_BYTES
        ):
            raise LocalSupervisorBootstrapError("bound module identity is unsafe")
        encoded = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, MAX_MODULE_BYTES + 1 - len(encoded)))
            if not chunk:
                break
            encoded.extend(chunk)
            if len(encoded) > MAX_MODULE_BYTES:
                raise LocalSupervisorBootstrapError("bound module exceeds its byte cap")
        if len(encoded) != opened.st_size:
            raise LocalSupervisorBootstrapError("bound module changed while held")
        return bytes(encoded)
    finally:
        os.close(descriptor)


def _verified(path: Path, expected_sha256: str) -> bytes:
    if len(expected_sha256) != 64 or any(
        value not in "0123456789abcdef" for value in expected_sha256
    ):
        raise LocalSupervisorBootstrapError("bound module digest is malformed")
    encoded = _read_exact(path)
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise LocalSupervisorBootstrapError("bound module digest drifted")
    return encoded


def _load_verified_bytes(path: Path, encoded: bytes, name: str) -> ModuleType:
    """Execute only the exact bytes already read and hash-verified."""

    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = name.rpartition(".")[0]
    sys.modules[name] = module
    try:
        code = compile(encoded, str(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _verify_clean_repository(repository_root: Path, expected_commit: str) -> None:
    if len(expected_commit) != 40 or any(
        value not in "0123456789abcdef" for value in expected_commit
    ):
        raise LocalSupervisorBootstrapError("expected repository commit is malformed")
    commands = (
        ("/usr/bin/git", "-C", str(repository_root), "rev-parse", "HEAD"),
        (
            "/usr/bin/git",
            "-C",
            str(repository_root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ),
    )
    outputs: list[bytes] = []
    environment = {
        "HOME": str(repository_root),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    }
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            raise LocalSupervisorBootstrapError("repository identity check failed") from None
        if completed.returncode != 0 or completed.stderr:
            raise LocalSupervisorBootstrapError("repository identity check failed")
        outputs.append(completed.stdout)
    if outputs[0].decode("ascii", "strict").strip() != expected_commit or outputs[1]:
        raise LocalSupervisorBootstrapError("repository is not the exact clean commit")


def _install_inert_package_surface(repository_root: Path) -> None:
    package_root = repository_root / "src/giclab"
    harness_root = package_root / "harness"
    giclab = ModuleType("giclab")
    giclab.__path__ = [str(package_root)]
    harness = ModuleType("giclab.harness")
    harness.__path__ = [str(harness_root)]
    sys.modules["giclab"] = giclab
    sys.modules["giclab.harness"] = harness


def _without_bootstrap_options(argv: list[str]) -> list[str]:
    result: list[str] = []
    skip = False
    for value in argv:
        if skip:
            skip = False
            continue
        if value in _BOOTSTRAP_OPTIONS:
            skip = True
            continue
        result.append(value)
    if skip:
        raise LocalSupervisorBootstrapError("bootstrap option lacks a value")
    return result


def _operation(argv: list[str]) -> str:
    candidates = [value for value in argv if value in _CLEANUP_OPERATIONS]
    if len(candidates) > 1:
        raise LocalSupervisorBootstrapError("cleanup operation is ambiguous")
    return candidates[0] if candidates else ""


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    repository_root = Path(_option(arguments, "--repository-root")).resolve(strict=True)
    contract_path = Path(_option(arguments, "--contract-file")).resolve(strict=True)
    supervisor_path = Path(_option(arguments, "--supervisor-file")).resolve(strict=True)
    expected_contract = repository_root / "src/giclab/harness/t07_bounded_smoke.py"
    expected_supervisor = repository_root / "src/giclab/harness/t07_bounded_supervisor.py"
    if contract_path != expected_contract or supervisor_path != expected_supervisor:
        raise LocalSupervisorBootstrapError("bound module path escaped the repository contract")
    contract_bytes = _verified(contract_path, _option(arguments, "--contract-sha256"))
    supervisor_bytes = _verified(supervisor_path, _option(arguments, "--supervisor-sha256"))
    if _operation(arguments) not in _CLEANUP_OPERATIONS:
        _verify_clean_repository(repository_root, _option(arguments, "--expected-commit"))
    sys.path.insert(0, str(repository_root / "src"))
    _install_inert_package_surface(repository_root)
    contract = _load_verified_bytes(contract_path, contract_bytes, "t07_bounded_contract")
    supervisor = _load_verified_bytes(
        supervisor_path, supervisor_bytes, "giclab.harness.t07_bounded_supervisor"
    )
    result = supervisor.main(_without_bootstrap_options(arguments), contract=contract)
    if type(result) is not int:
        raise LocalSupervisorBootstrapError("supervisor returned an invalid status")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
