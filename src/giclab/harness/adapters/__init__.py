"""Source-neutral adapter contracts; source-specific adapters are added later."""

from .base import ArtifactAdapter, NormalizationResult

__all__ = ["ArtifactAdapter", "NormalizationResult"]
