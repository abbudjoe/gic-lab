"""Load the Gate L2M supervisor from the exact reviewed repository source tree.

This bootstrap is inert on import.  It exists because ``python -I`` deliberately
removes the working directory from ``sys.path``; invoking the installed package in
that mode could otherwise select stale site-packages code.  The executable path is
bound to a canonical repository working directory, inserts only that repository's
``src`` directory, verifies the imported supervisor origin, and delegates without
reading a credential or performing network I/O itself.
"""

from __future__ import annotations

import argparse
import importlib
import os
import stat
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Final

SUPERVISOR_RELATIVE: Final = Path("src/giclab/harness/lambda_l23_manual_supervisor.py")


class BootstrapError(ValueError):
    """The exact-source supervisor bootstrap contract was not satisfied."""


def _bootstrap_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repository-root", type=Path, required=True)
    return parser


def _regular_owned_no_follow(path: Path) -> None:
    try:
        before = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise BootstrapError("reviewed supervisor source is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_uid != os.getuid()
        ):
            raise BootstrapError("reviewed supervisor source identity is unsafe")
    finally:
        os.close(descriptor)


def load_exact_supervisor(argv: Sequence[str]) -> ModuleType:
    """Load only the supervisor located under the canonical current repository."""

    parsed, _ = _bootstrap_parser().parse_known_args(list(argv))
    repository_root = parsed.repository_root.resolve(strict=True)
    if repository_root != Path.cwd().resolve(strict=True):
        raise BootstrapError("supervisor must start in the canonical repository root")
    source_root = repository_root / "src"
    supervisor_path = repository_root / SUPERVISOR_RELATIVE
    _regular_owned_no_follow(supervisor_path)
    sys.path.insert(0, str(source_root))
    module = importlib.import_module("giclab.harness.lambda_l23_manual_supervisor")
    loaded = Path(str(module.__file__)).resolve(strict=True)
    if loaded != supervisor_path:
        raise BootstrapError("loaded supervisor differs from reviewed repository source")
    return module


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        module = load_exact_supervisor(arguments)
        entrypoint = getattr(module, "main", None)
        if not callable(entrypoint):
            raise BootstrapError("reviewed supervisor entry point is unavailable")
        return int(entrypoint(arguments))
    except BootstrapError:
        print("giclab-l2m-bootstrap: stopped before supervisor execution", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
