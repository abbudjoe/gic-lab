"""Typed execution-plan headers and lifecycle discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PLAN_HEADING = re.compile(r"\A# Phase (?P<phase>[0-9]+(?:\.[0-9]+)?)(?: — (?P<title>[^\n]+))?\n")
PLAN_STATUS = re.compile(r"^Status: \*\*(?P<status>[^*]+)\*\*$", flags=re.MULTILINE)


@dataclass(frozen=True)
class PlanHeader:
    """Machine-readable fields declared by one execution plan."""

    phase: str
    title: str
    status: str


class PlanContractError(ValueError):
    """Raised when an execution plan omits its explicit machine-readable header."""


def load_plan_header(path: Path) -> PlanHeader:
    """Read the explicit phase, title, and status contract from one plan."""

    text = path.read_text(encoding="utf-8")
    heading_match = PLAN_HEADING.search(text)
    status_match = PLAN_STATUS.search(text)
    missing: list[str] = []
    if heading_match is None:
        missing.append("a leading '# Phase <number> — <title>' heading")
    if status_match is None:
        missing.append("an explicit 'Status: **<status>**' field")
    if missing:
        raise PlanContractError(f"plan must declare {' and '.join(missing)}")
    assert heading_match is not None
    assert status_match is not None
    return PlanHeader(
        phase=heading_match.group("phase"),
        title=heading_match.group("title") or "",
        status=status_match.group("status"),
    )


def discover_plan_paths(root: Path) -> tuple[Path, ...]:
    """Return every versioned execution plan without naming historical files."""

    plans_root = root / "docs/exec-plans"
    if not plans_root.is_dir():
        return ()
    return tuple(sorted(plans_root.rglob("*.md")))
