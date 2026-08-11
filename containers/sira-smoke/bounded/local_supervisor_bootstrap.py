"""Hash-first loader for the local T07 bounded-smoke supervisor.

This file imports only the standard library until it has read and verified the exact
contract and supervisor modules named by the immutable plan.  Import is inert.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import stat
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

MAX_MODULE_BYTES: Final = 2_097_152
_BOOTSTRAP_OPTIONS: Final = ("--supervisor-file", "--supervisor-sha256")


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


def _verified(path: Path, expected_sha256: str) -> None:
    if len(expected_sha256) != 64 or any(
        value not in "0123456789abcdef" for value in expected_sha256
    ):
        raise LocalSupervisorBootstrapError("bound module digest is malformed")
    if hashlib.sha256(_read_exact(path)).hexdigest() != expected_sha256:
        raise LocalSupervisorBootstrapError("bound module digest drifted")


def _load(path: Path, name: str) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise LocalSupervisorBootstrapError("bound module loader is unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


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


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    repository_root = Path(_option(arguments, "--repository-root")).resolve(strict=True)
    contract_path = Path(_option(arguments, "--contract-file")).resolve(strict=True)
    supervisor_path = Path(_option(arguments, "--supervisor-file")).resolve(strict=True)
    expected_contract = repository_root / "src/giclab/harness/t07_bounded_smoke.py"
    expected_supervisor = repository_root / "src/giclab/harness/t07_bounded_supervisor.py"
    if contract_path != expected_contract or supervisor_path != expected_supervisor:
        raise LocalSupervisorBootstrapError("bound module path escaped the repository contract")
    _verified(contract_path, _option(arguments, "--contract-sha256"))
    _verified(supervisor_path, _option(arguments, "--supervisor-sha256"))
    sys.path.insert(0, str(repository_root / "src"))
    importlib.import_module("giclab.harness")
    contract = _load(contract_path, "t07_bounded_contract")
    supervisor = _load(supervisor_path, "giclab.harness.t07_bounded_supervisor")
    result = supervisor.main(_without_bootstrap_options(arguments), contract=contract)
    if type(result) is not int:
        raise LocalSupervisorBootstrapError("supervisor returned an invalid status")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
