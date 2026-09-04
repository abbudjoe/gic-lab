"""Effect-neutral adapter surfaces for the shared Category 3 controller.

The controller consumes these orchestration-level interfaces. The production
assembly implements them by validating and coordinating the lower-level package
effects declared in :mod:`giclab.control.effects`. Deterministic data and fault
injection deliberately live in ``shadow_effects`` rather than this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from giclab.control.effects import (
    EffectAuthorityGrant,
    EffectAuthorityKind,
    EffectAuthorizationContext,
    ProviderHandle,
    RuntimeClock,
)


class ImplementationFlavor(StrEnum):
    """Whether adapters wrap production primitives or a narrow unit fixture."""

    PRODUCTION_WRAPPER = "production-wrapper"
    PURE_FAKE_FIXTURE = "pure-fake-fixture"


class AdapterFailure(RuntimeError):
    """A typed environmental effect failed with a known outcome."""


class AmbiguousProviderOutcome(AdapterFailure):
    """The provider may have accepted a call; zero resources cannot be inferred."""


class ReplacementEligibleFailure(AdapterFailure):
    """A retained pre-empirical closeout authorizes one bounded replacement."""


class CleanupInterrupted(AdapterFailure):
    """Cleanup stopped after persisting a byte-stable resumable handoff."""


class TerminationUnavailable(AdapterFailure):
    """Provider termination could not be confirmed within the bounded window."""


class StructuralPrivacyFinding(AdapterFailure):
    """A structural privacy scan found material that cannot be published."""


class PrivacyUnresolved(AdapterFailure):
    """Privacy was scanned through held state but path integrity remains unresolved."""


class UndeclaredAdapterCall(AdapterFailure):
    """The controller issued an effect outside the declared package envelope."""


@dataclass(frozen=True, slots=True)
class EssentialFailureRecord:
    """Controller-visible identity of one sealed, exported failed attempt."""

    run_id: str
    stopping_phase: str
    failure_class: str
    manifest_sha256: str
    receipt_sha256: str
    export_receipt_sha256: str
    essential_file_count: int
    essential_total_bytes: int
    evidence_binding_sha256: str


class ConsumedConditionFailure(AdapterFailure):
    """A consumed attempt stopped with reconstructable essential evidence."""

    def __init__(self, message: str, *, record: EssentialFailureRecord) -> None:
        super().__init__(message)
        self.record = record


@dataclass(frozen=True, slots=True)
class AdapterCall:
    index: int
    adapter: str
    operation: str
    subject: str
    outcome: str

    def to_document(self) -> dict[str, object]:
        return {
            "index": self.index,
            "adapter": self.adapter,
            "operation": self.operation,
            "subject": self.subject,
            "outcome": self.outcome,
        }


@dataclass(frozen=True, slots=True)
class MetadataEnvelope:
    """Sanitized timing envelope for one durable metadata receipt.

    Wall time is used only for provider receipt validity. Monotonic time is used
    only for the local age bound, so the two domains cannot be compared directly.
    """

    receipt_sha256: str
    issued_wall_time: float
    expires_wall_time: float
    issued_monotonic: float
    max_monotonic_age_seconds: float


class FirstPairCheckpointDisposition(StrEnum):
    """The three controller-visible outcomes of the Task A checkpoint."""

    CONTINUE = "continue-to-task-b"
    STOP = "stop-before-task-b"


@dataclass(frozen=True, slots=True)
class FirstPairCheckpointResult:
    """Retained policy decision returned by the production evidence store."""

    disposition: FirstPairCheckpointDisposition
    reasons: tuple[str, ...]
    decision_sha256: str
    evidence_binding_sha256: str


class SecretChannel(Protocol):
    def read(self) -> str:
        """Qualify the strict secret channel without retaining secret material."""


class MetadataTransport(Protocol):
    def request(self, *, contract_version: str) -> MetadataEnvelope:
        """Consume one metadata allowance and return a sanitized envelope."""

    def is_fresh(self, envelope: MetadataEnvelope) -> bool:
        """Evaluate final freshness immediately before provider launch."""


class ProviderTransport(Protocol):
    def inventory(self) -> tuple[str, ...] | None:
        """Return sanitized owned resources, or ``None`` when ambiguous."""

    def launch(self, *, launch_ordinal: int) -> ProviderHandle:
        """Consume one package-authorized launch capability."""

    def provider_entry(self, handle: ProviderHandle) -> None:
        """Validate the retained provider-entry receipt for one exact launch."""

    def terminate(self, handle: ProviderHandle) -> None:
        """Request termination of one exact owned instance."""


class HostRuntime(Protocol):
    def stage(self) -> str:
        """Materialize and validate the exact tracked-only package archive."""

    def preflight(self, handle: ProviderHandle) -> None:
        """Validate the effect-produced host preflight receipt."""

    def qualify(self, handle: ProviderHandle) -> str:
        """Validate image, runtime, browser, finalizer, and cleanup qualification."""

    def freeze(self, handle: ProviderHandle) -> str:
        """Publish and validate the dynamic scientific-freeze receipts."""

    def cleanup(self, handle: ProviderHandle | None) -> str:
        """Clean exact owned state using an idempotent immutable handoff."""


class ConditionRuntime(Protocol):
    def reserve(self, run_id: str) -> str:
        """Reserve one exact condition identity."""

    def enter(self, run_id: str) -> str:
        """Cross empirical entry, consuming the condition identity."""

    def run(self, run_id: str) -> str:
        """Execute the exact condition session through its typed effect channel."""

    def export_raw(self, run_id: str) -> str:
        """Validate and retain exact file-backed raw evidence."""

    def finalize(self, run_id: str) -> str:
        """Finalize the exact raw attempt through the offline effect channel."""

    def evaluate(self, run_id: str) -> str:
        """Evaluate the effect-produced finalized output."""


class EvidenceStore(Protocol):
    def record(self, *, kind: str, identity: str) -> None:
        """Record one sanitized evidence identity."""

    def checkpoint(self, *, name: str) -> FirstPairCheckpointResult:
        """Persist and return the retained first-pair policy decision."""

    def scan_privacy(self) -> str:
        """Run structural and exact-secret publication checks."""


class AdapterAudit(Protocol):
    @property
    def calls(self) -> tuple[AdapterCall, ...]: ...

    @property
    def undeclared_calls(self) -> tuple[str, ...]: ...


class AdapterDiagnostics(Protocol):
    def control_evidence(self) -> Mapping[str, object]: ...

    def terminalize_authority(self, *, complete: bool) -> Mapping[str, object]:
        """End a live grant exactly once and return its public consumption receipt."""

    def release_resources(self) -> None:
        """Release identities held through terminal result materialization."""


@dataclass(frozen=True, slots=True)
class Category3Adapters:
    """The complete injected orchestration surface used by the shared controller."""

    implementation_flavor: ImplementationFlavor
    authorization_context: EffectAuthorizationContext
    authority: EffectAuthorityGrant
    clock: RuntimeClock
    secret_channel: SecretChannel
    metadata_transport: MetadataTransport
    provider_transport: ProviderTransport
    host_runtime: HostRuntime
    condition_runtime: ConditionRuntime
    evidence_store: EvidenceStore
    audit: AdapterAudit
    diagnostics: AdapterDiagnostics


__all__ = [
    "AdapterCall",
    "AdapterFailure",
    "AmbiguousProviderOutcome",
    "Category3Adapters",
    "CleanupInterrupted",
    "ConsumedConditionFailure",
    "EffectAuthorityGrant",
    "EffectAuthorityKind",
    "EssentialFailureRecord",
    "FirstPairCheckpointDisposition",
    "FirstPairCheckpointResult",
    "ImplementationFlavor",
    "MetadataEnvelope",
    "PrivacyUnresolved",
    "ProviderHandle",
    "ReplacementEligibleFailure",
    "StructuralPrivacyFinding",
    "TerminationUnavailable",
    "UndeclaredAdapterCall",
]
