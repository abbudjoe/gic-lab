"""Protocol implemented later by source-specific artifact adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from ..models import (
    CommandSpec,
    EventProvenance,
    NonWallResourceAccounting,
    NormalizedEvent,
    RunPlan,
)


class AdapterNoticeSeverity(StrEnum):
    """Harness-owned control-event severity requested by an adapter."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AdapterNotice:
    """Source-grounded notice emitted through the harness control plane."""

    severity: AdapterNoticeSeverity
    kind: str
    message: str
    source: str
    source_paths: tuple[str, ...]
    provenance: EventProvenance

    def __post_init__(self) -> None:
        if not isinstance(self.severity, AdapterNoticeSeverity):
            raise ValueError("adapter notice severity must be typed")
        if not self.kind.strip() or not self.message.strip() or not self.source.strip():
            raise ValueError("adapter notice kind, message, and source must be nonempty")
        if not self.source_paths or any(not path.strip() for path in self.source_paths):
            raise ValueError("adapter notice source_paths must contain nonempty paths")
        if len(set(self.source_paths)) != len(self.source_paths):
            raise ValueError("adapter notice source_paths must be unique")
        if not isinstance(self.provenance, EventProvenance):
            raise ValueError("adapter notice provenance must be typed")


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Normalized evidence plus explicit source gaps."""

    events: tuple[NormalizedEvent, ...]
    raw_artifacts: tuple[Path, ...]
    unavailable_fields: tuple[str, ...]
    notices: tuple[AdapterNotice, ...]
    accounting: NonWallResourceAccounting


class ArtifactAdapter(Protocol):
    """Translate a plan to and from one pinned upstream artifact."""

    source_id: str

    def build_command(
        self,
        plan: RunPlan,
        upstream_root: Path,
        upstream_output_root: Path,
    ) -> CommandSpec:
        """Build a shell-free command with explicit source and output roots."""

    def normalize(self, plan: RunPlan, upstream_output_root: Path) -> NormalizationResult:
        """Map only source-supported evidence into canonical events."""
