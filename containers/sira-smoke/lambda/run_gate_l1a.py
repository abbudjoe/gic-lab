"""Repository-source launcher for the reviewed T07 Gate L1A supervisor."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if not SOURCE_ROOT.is_dir() or REPOSITORY_ROOT != Path(
    "/Users/joseph/.codex/worktrees/84b1/gic-lab"
):
    raise SystemExit("Gate L1A launcher repository identity drifted")
sys.path.insert(0, str(SOURCE_ROOT))

from giclab.harness.lambda_ssh_key_executor import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
