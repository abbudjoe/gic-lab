"""Protocol implemented later by source-specific artifact adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..models import CommandSpec, NonWallResourceAccounting, NormalizedEvent, RunPlan


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Normalized evidence plus explicit source gaps."""

    events: tuple[NormalizedEvent, ...]
    raw_artifacts: tuple[Path, ...]
    unavailable_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    accounting: NonWallResourceAccounting


class ArtifactAdapter(Protocol):
    """Translate a plan to and from one pinned upstream artifact."""

    source_id: str

    def build_command(self, plan: RunPlan, upstream_root: Path) -> CommandSpec:
        """Build a shell-free command without executing it."""

    def normalize(self, plan: RunPlan, upstream_output_root: Path) -> NormalizationResult:
        """Map only source-supported evidence into canonical events."""
