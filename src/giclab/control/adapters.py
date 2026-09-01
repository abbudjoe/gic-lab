"""Typed effect surfaces for the shared Category 3 controller.

Implementation flavor and effect authority are intentionally separate. Public CI
uses production wrappers over deterministic low-level fakes. A pure fake fixture is
retained only for narrow controller tests. This package has no live-authority
factory: constructing an enum value cannot mint effect authority.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ImplementationFlavor(StrEnum):
    """Whether adapters wrap retained production primitives or a unit fixture."""

    PRODUCTION_WRAPPER = "production-wrapper"
    PURE_FAKE_FIXTURE = "pure-fake-fixture"


class EffectAuthorityKind(StrEnum):
    """Authority classification; this package can mint only shadow authority."""

    SHADOW_ONLY = "shadow-only"
    LIVE_AUTHORIZED = "live-authorized"


_SHADOW_AUTHORITY_PROOF = object()


@dataclass(frozen=True, slots=True, init=False)
class EffectAuthority:
    """Opaque effect grant whose public constructor is intentionally unavailable."""

    kind: EffectAuthorityKind
    source: str
    _proof: object = field(repr=False, compare=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("effect authority is minted only by reviewed validators")

    @classmethod
    def _mint_shadow(cls, *, source: str) -> EffectAuthority:
        value = object.__new__(cls)
        object.__setattr__(value, "kind", EffectAuthorityKind.SHADOW_ONLY)
        object.__setattr__(value, "source", source)
        object.__setattr__(value, "_proof", _SHADOW_AUTHORITY_PROOF)
        return value

    def is_valid_shadow(self) -> bool:
        return self.kind is EffectAuthorityKind.SHADOW_ONLY and (
            self._proof is _SHADOW_AUTHORITY_PROOF
        )

    def authorizes(
        self,
        *,
        contract_version: str,
        control_revision: str,
    ) -> bool:
        del contract_version, control_revision
        return self.is_valid_shadow()


def mint_shadow_effect_authority(*, source: str) -> EffectAuthority:
    """Mint the only authority kind available in this package."""

    return EffectAuthority._mint_shadow(source=source)


class EffectAuthorityGrant(Protocol):
    """Interface a separately reviewed package may implement for live authority."""

    @property
    def kind(self) -> EffectAuthorityKind:
        """Return the typed authority kind."""

    @property
    def source(self) -> str:
        """Return the exact externally reviewed authority source identity."""

    def authorizes(
        self,
        *,
        contract_version: str,
        control_revision: str,
    ) -> bool:
        """Validate the external grant against exact package/control identity."""


class AdapterFailure(RuntimeError):
    """A declared fake effect failed with a known outcome."""


class AmbiguousProviderOutcome(AdapterFailure):
    """The provider may have accepted a call; zero resources cannot be inferred."""


class CleanupInterrupted(AdapterFailure):
    """Local cleanup stopped after persisting resumable state."""


class TerminationUnavailable(AdapterFailure):
    """Provider termination could not be confirmed within the bounded window."""


class StructuralPrivacyFinding(AdapterFailure):
    """A structural privacy scan found material that cannot be published."""


class UndeclaredAdapterCall(AdapterFailure):
    """The controller issued an effect outside the scenario's declared envelope."""


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
    receipt_sha256: str
    issued_tick: int
    expires_tick: int


@dataclass(frozen=True, slots=True)
class ProviderHandle:
    opaque_identity: str
    launch_ordinal: int


class Clock(Protocol):
    def tick(self) -> int:
        """Return a monotonic deterministic tick."""


class SecretChannel(Protocol):
    def read(self) -> str:
        """Qualify the secret channel without exposing secret material."""


class MetadataTransport(Protocol):
    def request(self, *, contract_version: str) -> MetadataEnvelope:
        """Consume one metadata allowance and return a sanitized envelope."""

    def is_fresh(self, envelope: MetadataEnvelope) -> bool:
        """Evaluate final freshness immediately before provider launch."""


class ProviderTransport(Protocol):
    def inventory(self) -> tuple[str, ...] | None:
        """Return sanitized owned resources, or None when the outcome is ambiguous."""

    def launch(self, *, launch_ordinal: int) -> ProviderHandle:
        """Consume a launch capability."""

    def provider_entry(self, handle: ProviderHandle) -> None:
        """Reach the provider entry boundary for a launched instance."""

    def terminate(self, handle: ProviderHandle) -> None:
        """Request termination of one exact owned instance."""


class HostRuntime(Protocol):
    def stage(self) -> str:
        """Perform deterministic local staging and storage/path checks."""

    def preflight(self, handle: ProviderHandle) -> None:
        """Run the host preflight boundary."""

    def qualify(self, handle: ProviderHandle) -> str:
        """Qualify the image and local finalizer source contract."""

    def freeze(self, handle: ProviderHandle) -> str:
        """Freeze the scientific package after infrastructure qualification."""

    def cleanup(self, handle: ProviderHandle | None) -> str:
        """Clean local/host state, preserving an idempotent journal."""


class ConditionRuntime(Protocol):
    def reserve(self, run_id: str) -> str:
        """Reserve one exact condition identity."""

    def enter(self, run_id: str) -> str:
        """Cross empirical entry, consuming the condition identity."""

    def run(self, run_id: str) -> str:
        """Produce deterministic shadow condition output."""

    def export_raw(self, run_id: str) -> str:
        """Export the fake raw-evidence identity."""

    def finalize(self, run_id: str) -> str:
        """Finalize one fake attempt."""

    def evaluate(self, run_id: str) -> str:
        """Produce a fake evaluator artifact identity, never a scientific score."""


class EvidenceStore(Protocol):
    def record(self, *, kind: str, identity: str) -> None:
        """Record a sanitized shadow-only evidence identity."""

    def checkpoint(self, *, name: str) -> str:
        """Persist a pair checkpoint identity."""

    def scan_privacy(self) -> str:
        """Run the structural publication/privacy gate."""


class AdapterAudit(Protocol):
    @property
    def calls(self) -> tuple[AdapterCall, ...]:
        """Return the ordered, sanitized effect ledger."""

    @property
    def undeclared_calls(self) -> tuple[str, ...]:
        """Return attempted calls outside the declared scenario envelope."""


class AdapterDiagnostics(Protocol):
    def control_evidence(self) -> Mapping[str, object]:
        """Return public-safe coupling, accounting, and staging evidence."""


@dataclass(frozen=True, slots=True)
class Category3Adapters:
    """The complete injected effect surface used by the shared controller."""

    implementation_flavor: ImplementationFlavor
    authority: EffectAuthorityGrant
    clock: Clock
    secret_channel: SecretChannel
    metadata_transport: MetadataTransport
    provider_transport: ProviderTransport
    host_runtime: HostRuntime
    condition_runtime: ConditionRuntime
    evidence_store: EvidenceStore
    audit: AdapterAudit
    diagnostics: AdapterDiagnostics


@dataclass(frozen=True, slots=True)
class FakeScenario:
    """One declared deterministic fault injection and its bounded call envelope."""

    name: str
    fail_operation: str | None = None
    fail_occurrence: int = 1
    metadata_expires_before_launch: bool = False
    ambiguous_inventory_after_launch: bool = False
    termination_failure_count: int = 0
    cleanup_interruption_count: int = 0


def _identity(*parts: object) -> str:
    encoded = json.dumps(parts, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


class DeterministicFakeWorld:
    """All fake adapters backed by one strict, auditable call ledger."""

    _MAX_CALLS: Mapping[str, int] = {
        "secret.read": 1,
        "metadata.request": 1,
        "metadata.is_fresh": 1,
        "provider.inventory": 4,
        "provider.launch": 2,
        "provider.enter": 2,
        "provider.terminate": 3,
        "host.stage": 1,
        "host.preflight": 2,
        "host.qualify": 1,
        "host.freeze": 1,
        "host.cleanup": 2,
        "condition.reserve": 4,
        "condition.enter": 4,
        "condition.run": 4,
        "condition.export_raw": 4,
        "condition.finalize": 4,
        "condition.evaluate": 4,
        "evidence.record": 16,
        "evidence.checkpoint": 1,
        "evidence.scan_privacy": 1,
    }

    def __init__(self, scenario: FakeScenario, *, fixed_tick: int = 1000) -> None:
        self.scenario = scenario
        self._tick = fixed_tick
        self._calls: list[AdapterCall] = []
        self._counts: Counter[str] = Counter()
        self._undeclared_calls: list[str] = []
        self._active: dict[str, ProviderHandle] = {}
        self._ambiguous_launch = False

    @property
    def calls(self) -> tuple[AdapterCall, ...]:
        return tuple(self._calls)

    @property
    def undeclared_calls(self) -> tuple[str, ...]:
        return tuple(self._undeclared_calls)

    def adapters(self) -> Category3Adapters:
        return Category3Adapters(
            implementation_flavor=ImplementationFlavor.PURE_FAKE_FIXTURE,
            authority=mint_shadow_effect_authority(source="deterministic-unit-fixture"),
            clock=self,
            secret_channel=self,
            metadata_transport=self,
            provider_transport=self,
            host_runtime=self,
            condition_runtime=self,
            evidence_store=self,
            audit=self,
            diagnostics=self,
        )

    def control_evidence(self) -> Mapping[str, object]:
        """The pure fixture intentionally proves no production coupling."""

        return {
            "implementation_flavor": ImplementationFlavor.PURE_FAKE_FIXTURE.value,
            "effect_authority": EffectAuthorityKind.SHADOW_ONLY.value,
            "production_primitives": [],
            "accounting": None,
            "deterministic_staging": None,
        }

    def tick(self) -> int:
        return self._tick

    def _begin(self, operation: str, subject: str) -> int:
        limit = self._MAX_CALLS.get(operation)
        occurrence = self._counts[operation] + 1
        self._counts[operation] = occurrence
        if limit is None or occurrence > limit:
            marker = f"{operation}#{occurrence}"
            self._undeclared_calls.append(marker)
            self._record(operation, subject, "undeclared")
            raise UndeclaredAdapterCall(marker)
        return occurrence

    def _record(self, operation: str, subject: str, outcome: str) -> None:
        adapter, _separator, _method = operation.partition(".")
        self._calls.append(
            AdapterCall(
                index=len(self._calls) + 1,
                adapter=adapter,
                operation=operation,
                subject=subject,
                outcome=outcome,
            )
        )

    def _declared_failure(self, operation: str, occurrence: int) -> bool:
        return (
            self.scenario.fail_operation == operation
            and self.scenario.fail_occurrence == occurrence
        )

    def read(self) -> str:
        operation = "secret.read"
        occurrence = self._begin(operation, "secret-channel")
        if self._declared_failure(operation, occurrence):
            self._record(operation, "secret-channel", "failed")
            raise AdapterFailure("fake secret-channel qualification failed")
        identity = _identity(self.scenario.name, operation)
        self._record(operation, "secret-channel", "passed")
        return identity

    def request(self, *, contract_version: str) -> MetadataEnvelope:
        operation = "metadata.request"
        occurrence = self._begin(operation, contract_version)
        if self._declared_failure(operation, occurrence):
            self._record(operation, contract_version, "failed")
            raise AdapterFailure("fake metadata request failed")
        expires_tick = (
            self._tick if self.scenario.metadata_expires_before_launch else self._tick + 10
        )
        envelope = MetadataEnvelope(
            receipt_sha256=_identity(self.scenario.name, operation, contract_version),
            issued_tick=self._tick,
            expires_tick=expires_tick,
        )
        self._record(operation, contract_version, "passed")
        self._tick += 1
        return envelope

    def is_fresh(self, envelope: MetadataEnvelope) -> bool:
        operation = "metadata.is_fresh"
        occurrence = self._begin(operation, envelope.receipt_sha256)
        fresh = self._tick < envelope.expires_tick and not self._declared_failure(
            operation, occurrence
        )
        self._record(operation, envelope.receipt_sha256, "passed" if fresh else "expired")
        return fresh

    def inventory(self) -> tuple[str, ...] | None:
        operation = "provider.inventory"
        occurrence = self._begin(operation, "owned-resources")
        if self._declared_failure(operation, occurrence):
            self._record(operation, "owned-resources", "failed")
            raise AdapterFailure("fake provider inventory failed")
        if self._ambiguous_launch and self.scenario.ambiguous_inventory_after_launch:
            self._record(operation, "owned-resources", "ambiguous")
            return None
        values = tuple(sorted(self._active))
        self._record(operation, "owned-resources", "zero" if not values else "observed")
        return values

    def launch(self, *, launch_ordinal: int) -> ProviderHandle:
        operation = "provider.launch"
        occurrence = self._begin(operation, f"launch-{launch_ordinal}")
        if self._declared_failure(operation, occurrence):
            self._ambiguous_launch = True
            self._record(operation, f"launch-{launch_ordinal}", "ambiguous")
            raise AmbiguousProviderOutcome("fake launch acknowledgement is ambiguous")
        handle = ProviderHandle(
            opaque_identity=f"shadow-instance-{launch_ordinal}",
            launch_ordinal=launch_ordinal,
        )
        self._active[handle.opaque_identity] = handle
        self._record(operation, handle.opaque_identity, "accepted")
        return handle

    def provider_entry(self, handle: ProviderHandle) -> None:
        operation = "provider.enter"
        occurrence = self._begin(operation, handle.opaque_identity)
        if self._declared_failure(operation, occurrence):
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure("fake provider entry failed")
        self._record(operation, handle.opaque_identity, "passed")

    def terminate(self, handle: ProviderHandle) -> None:
        operation = "provider.terminate"
        occurrence = self._begin(operation, handle.opaque_identity)
        if occurrence <= self.scenario.termination_failure_count or self._declared_failure(
            operation, occurrence
        ):
            self._record(operation, handle.opaque_identity, "unavailable")
            raise TerminationUnavailable("fake termination service unavailable")
        self._active.pop(handle.opaque_identity, None)
        self._record(operation, handle.opaque_identity, "accepted")

    def stage(self) -> str:
        operation = "host.stage"
        occurrence = self._begin(operation, "local-package-and-archive")
        if self._declared_failure(operation, occurrence):
            self._record(operation, "local-package-and-archive", "failed")
            raise AdapterFailure("fake deterministic staging failed")
        identity = _identity(self.scenario.name, operation)
        self._record(operation, "local-package-and-archive", "passed")
        return identity

    def preflight(self, handle: ProviderHandle) -> None:
        operation = "host.preflight"
        occurrence = self._begin(operation, handle.opaque_identity)
        if self._declared_failure(operation, occurrence):
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure("fake host preflight failed")
        self._record(operation, handle.opaque_identity, "passed")

    def qualify(self, handle: ProviderHandle) -> str:
        operation = "host.qualify"
        occurrence = self._begin(operation, handle.opaque_identity)
        if self._declared_failure(operation, occurrence):
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure("fake image/finalizer qualification failed")
        identity = _identity(self.scenario.name, operation)
        self._record(operation, handle.opaque_identity, "passed")
        return identity

    def freeze(self, handle: ProviderHandle) -> str:
        operation = "host.freeze"
        occurrence = self._begin(operation, handle.opaque_identity)
        if self._declared_failure(operation, occurrence):
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure("fake scientific freeze failed")
        identity = _identity(self.scenario.name, operation)
        self._record(operation, handle.opaque_identity, "passed")
        return identity

    def cleanup(self, handle: ProviderHandle | None) -> str:
        operation = "host.cleanup"
        subject = handle.opaque_identity if handle is not None else "no-known-instance"
        occurrence = self._begin(operation, subject)
        if occurrence <= self.scenario.cleanup_interruption_count or self._declared_failure(
            operation, occurrence
        ):
            self._record(operation, subject, "interrupted-resumable")
            raise CleanupInterrupted("fake cleanup interrupted after journal persistence")
        identity = _identity(self.scenario.name, operation, occurrence)
        self._record(operation, subject, "passed")
        return identity

    def reserve(self, run_id: str) -> str:
        return self._condition_operation("condition.reserve", run_id)

    def enter(self, run_id: str) -> str:
        return self._condition_operation("condition.enter", run_id)

    def run(self, run_id: str) -> str:
        return self._condition_operation("condition.run", run_id)

    def export_raw(self, run_id: str) -> str:
        return self._condition_operation("condition.export_raw", run_id)

    def finalize(self, run_id: str) -> str:
        return self._condition_operation("condition.finalize", run_id)

    def evaluate(self, run_id: str) -> str:
        return self._condition_operation("condition.evaluate", run_id)

    def _condition_operation(self, operation: str, run_id: str) -> str:
        occurrence = self._begin(operation, run_id)
        if self._declared_failure(operation, occurrence):
            self._record(operation, run_id, "failed")
            raise AdapterFailure(f"fake {operation} failed")
        identity = _identity(self.scenario.name, operation, run_id)
        self._record(operation, run_id, "passed")
        return identity

    def record(self, *, kind: str, identity: str) -> None:
        operation = "evidence.record"
        occurrence = self._begin(operation, kind)
        if self._declared_failure(operation, occurrence):
            self._record(operation, kind, "failed")
            raise AdapterFailure("fake evidence record failed")
        self._record(operation, kind, f"retained:{identity[:12]}")

    def checkpoint(self, *, name: str) -> str:
        operation = "evidence.checkpoint"
        occurrence = self._begin(operation, name)
        if self._declared_failure(operation, occurrence):
            self._record(operation, name, "failed")
            raise AdapterFailure("fake pair checkpoint failed")
        identity = _identity(self.scenario.name, operation, name)
        self._record(operation, name, "passed")
        return identity

    def scan_privacy(self) -> str:
        operation = "evidence.scan_privacy"
        occurrence = self._begin(operation, "shadow-evidence")
        if self._declared_failure(operation, occurrence):
            self._record(operation, "shadow-evidence", "finding")
            raise StructuralPrivacyFinding("fake structural privacy finding")
        identity = _identity(self.scenario.name, operation)
        self._record(operation, "shadow-evidence", "passed")
        return identity
