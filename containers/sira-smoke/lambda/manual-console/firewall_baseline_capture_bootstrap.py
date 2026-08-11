"""Load the exact reviewed firewall-baseline capture supervisor source.

The future authorized command uses ``python -I``.  This bootstrap therefore adds
only the canonical repository ``src`` directory, verifies that the imported module
came from that tree, and delegates.  Import and validation perform no secret access
or network I/O.
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

SUPERVISOR_RELATIVE: Final = Path("src/giclab/harness/lambda_firewall_baseline.py")


class BootstrapError(ValueError):
    """The exact-source firewall capture bootstrap contract was not satisfied."""


def _bootstrap_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repository-root", type=Path, required=True)
    return parser


def _regular_owned_no_follow(path: Path) -> None:
    try:
        before = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise BootstrapError("reviewed capture supervisor source is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_uid != os.getuid()
        ):
            raise BootstrapError("reviewed capture supervisor source identity is unsafe")
    finally:
        os.close(descriptor)


def load_exact_supervisor(argv: Sequence[str]) -> ModuleType:
    """Load only the capture supervisor under the canonical current repository."""

    parsed, _ = _bootstrap_parser().parse_known_args(list(argv))
    repository_root = parsed.repository_root.resolve(strict=True)
    if repository_root != Path.cwd().resolve(strict=True):
        raise BootstrapError("capture supervisor must start in the repository root")
    source_root = repository_root / "src"
    supervisor_path = repository_root / SUPERVISOR_RELATIVE
    _regular_owned_no_follow(supervisor_path)
    sys.path.insert(0, str(source_root))
    module = importlib.import_module("giclab.harness.lambda_firewall_baseline")
    loaded = Path(str(module.__file__)).resolve(strict=True)
    if loaded != supervisor_path:
        raise BootstrapError("loaded capture supervisor differs from reviewed source")
    return module


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        module = load_exact_supervisor(arguments)
        entrypoint = getattr(module, "main", None)
        if not callable(entrypoint):
            raise BootstrapError("reviewed capture supervisor entry point is unavailable")
        return int(entrypoint(arguments))
    except BootstrapError:
        print("giclab-firewall-capture-bootstrap: stopped before execution", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
