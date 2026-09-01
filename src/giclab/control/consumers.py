"""Executable provider-contract consumers shared by validation and assembly.

The central provider-contract declaration is useful only when every runtime boundary
can resolve it.  This module owns that resolution surface.  Registry completeness
invokes these consumers, and the production adapter assembly consumes the same typed
results; a receipt cannot therefore pass by echoing a capability enum.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from giclab.harness import t09_model_metadata_receipt as model_metadata
from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness import t09_sira_pilot as pilot
from giclab.harness.t09_provider_contracts import (
    AuthorizationPolicy,
    CleanupFamily,
    CommandPackageFamily,
    ControlRootPolicy,
    MetadataPolicy,
    PackageTransitionPolicy,
    ProviderSelectorPolicy,
    ReplacementPolicy,
    StageIdentityPolicy,
    T09ProviderContract,
    render_provider_entry_command,
)


class ConsumerResolutionError(ValueError):
    """A declared contract could not resolve one executable consumer."""


@dataclass(frozen=True, slots=True)
class ConsumerResolution:
    """One typed, executable resolution for a contract consumer."""

    consumer: str
    handler_id: str
    implementation: Callable[..., object]
    details: Mapping[str, object]

    def receipt_document(self) -> dict[str, object]:
        return {
            "status": "passed",
            "handler_id": self.handler_id,
            **dict(self.details),
        }


ConsumerResolver = Callable[[Path, T09ProviderContract], ConsumerResolution | None]


@dataclass(frozen=True, slots=True)
class ContractConsumer:
    """One named resolver used by completeness validation and adapter assembly."""

    name: str
    resolve: ConsumerResolver


def _resolution(
    name: str,
    handler_id: str,
    implementation: Callable[..., object],
    **details: object,
) -> ConsumerResolution:
    if not callable(implementation):
        raise ConsumerResolutionError(f"{name} resolved a non-callable implementation")
    return ConsumerResolution(
        consumer=name,
        handler_id=handler_id,
        implementation=implementation,
        details=MappingProxyType(dict(details)),
    )


def _lifecycle(repository: Path, contract: T09ProviderContract) -> ConsumerResolution:
    lifecycle = provider.load_campaign_lifecycle(repository, contract=contract)
    if lifecycle.contract != contract:
        raise ConsumerResolutionError("lifecycle resolver returned another contract")
    return _resolution(
        "lifecycle_resolver",
        f"campaign-lifecycle:{contract.capabilities.lifecycle_family.value}",
        provider.load_campaign_lifecycle,
        family=contract.capabilities.lifecycle_family.value,
        max_launches=lifecycle.max_launches,
    )


def _metadata(repository: Path, contract: T09ProviderContract) -> ConsumerResolution | None:
    del repository
    if contract.capabilities.metadata_policy is MetadataPolicy.NONE:
        return None
    if contract.capabilities.metadata_policy is not MetadataPolicy.LOCAL_PRELAUNCH_RECEIPT:
        raise ConsumerResolutionError("metadata policy has no production controller")
    return _resolution(
        "metadata_controller",
        "model-metadata-receipt:strict-local-prelaunch-v1",
        model_metadata.validate_model_metadata_receipt,
        policy=contract.capabilities.metadata_policy.value,
        final_boundary_handler=(
            model_metadata.admit_model_metadata_receipt_at_prelaunch_boundary.__name__
        ),
        dotenv_selector=model_metadata.load_openai_dotenv_assignment.__name__,
    )


def _replacement(repository: Path, contract: T09ProviderContract) -> ConsumerResolution | None:
    del repository
    if contract.capabilities.replacement_policy is ReplacementPolicy.NONE:
        return None
    if (
        contract.capabilities.replacement_policy is not ReplacementPolicy.BOUNDED_PREFLIGHT
        or contract.max_launch_count < 2
    ):
        raise ConsumerResolutionError("replacement policy has no bounded retained handler")
    return _resolution(
        "replacement_authority_handler",
        "provider-entry-authority:normalized-history-v1",
        provider._normalize_provider_entry_replacement_authority,
        policy=contract.capabilities.replacement_policy.value,
        eligibility_validator=provider._validate_replacement_launch_eligibility.__name__,
        retention_handler=provider._retain_replacement_launch_authority.__name__,
    )


def _cleanup(repository: Path, contract: T09ProviderContract) -> ConsumerResolution:
    del repository
    handlers: dict[CleanupFamily, tuple[str, Callable[..., object]]] = {
        CleanupFamily.HISTORICAL: (
            "cleanup:historical-provider-owner-v1",
            provider.validate_cleanup_authority_ledger,
        ),
        CleanupFamily.EARLY_JOURNAL: (
            "cleanup:early-journal-v1",
            provider.validate_cleanup_authority_ledger,
        ),
        CleanupFamily.EMPIRICAL_PREFIX: (
            "cleanup:empirical-prefix-v1",
            pilot.load_validated_pilot_state,
        ),
    }
    try:
        handler_id, implementation = handlers[contract.capabilities.cleanup_family]
    except KeyError as exc:  # pragma: no cover - enum exhaustiveness guard
        raise ConsumerResolutionError("cleanup family has no retained handler") from exc
    return _resolution(
        "cleanup_handler",
        handler_id,
        implementation,
        family=contract.capabilities.cleanup_family.value,
    )


def _command_package(repository: Path, contract: T09ProviderContract) -> ConsumerResolution | None:
    if contract.capabilities.command_package_family is CommandPackageFamily.HISTORICAL:
        return None
    if contract.capabilities.command_package_family is not CommandPackageFamily.AUTONOMOUS:
        raise ConsumerResolutionError("command-package family has no loader")
    # Imported lazily to keep the package byte resolver in its established module
    # without creating a module-initialization cycle.
    from giclab.control.registry_validation import resolve_registered_command_package

    document, sha256, source = resolve_registered_command_package(repository, contract)
    if document.get("plan_id") != contract.plan_id:
        raise ConsumerResolutionError("command package resolved another contract")
    return _resolution(
        "command_package_loader",
        "command-package:registered-autonomous-v1",
        resolve_registered_command_package,
        family=contract.capabilities.command_package_family.value,
        sha256=sha256,
        source=source,
        attempt_count=len(contract.run_ids),
    )


def _control_root(repository: Path, contract: T09ProviderContract) -> ConsumerResolution:
    del repository
    expected = (
        f"pilot-{contract.version.lower()}"
        if contract.capabilities.control_root_policy is ControlRootPolicy.VERSIONED
        else "pilot-v7"
    )
    if contract.control_root_name != expected:
        raise ConsumerResolutionError("control-root resolver disagrees with contract identity")
    return _resolution(
        "control_root_resolver",
        f"control-root:{contract.capabilities.control_root_policy.value}",
        render_provider_entry_command,
        policy=contract.capabilities.control_root_policy.value,
        control_root=expected,
    )


def _authorization(repository: Path, contract: T09ProviderContract) -> ConsumerResolution:
    del repository
    handler_ids = {
        AuthorizationPolicy.FROZEN_HISTORICAL: "authority:frozen-historical-v1",
        AuthorizationPolicy.LEGACY_LOCAL_SINGLE_USE: "authority:local-single-use-v1",
        AuthorizationPolicy.METADATA_BOUND_SINGLE_USE: "authority:metadata-bound-single-use-v1",
    }
    try:
        handler_id = handler_ids[contract.capabilities.authorization_policy]
    except KeyError as exc:  # pragma: no cover - enum exhaustiveness guard
        raise ConsumerResolutionError("authorization policy has no validator") from exc
    return _resolution(
        "authorization_policy_resolver",
        handler_id,
        provider.validate_authorization_ledger,
        policy=contract.capabilities.authorization_policy.value,
        repository_grants_authority=False,
    )


def _package_transition(
    repository: Path,
    contract: T09ProviderContract,
) -> ConsumerResolution | None:
    del repository
    if contract.capabilities.package_transition_policy is PackageTransitionPolicy.NONE:
        return None
    if (
        contract.capabilities.package_transition_policy
        is not PackageTransitionPolicy.PREEMPIRICAL_DESCENDANT
    ):
        raise ConsumerResolutionError("package-transition policy has no validator")
    return _resolution(
        "package_transition_resolver",
        "package-transition:preempirical-descendant-v1",
        provider.autonomous_preflight_package_transition,
        policy=contract.capabilities.package_transition_policy.value,
    )


def _provider_selector(
    repository: Path,
    contract: T09ProviderContract,
) -> ConsumerResolution | None:
    if contract.capabilities.provider_selector_policy is ProviderSelectorPolicy.NONE:
        return None
    if contract.capabilities.provider_selector_policy is not ProviderSelectorPolicy.EXPLICIT:
        raise ConsumerResolutionError("provider-selector policy has no resolver")
    command = _command_package(repository, contract)
    if command is None:
        raise ConsumerResolutionError("explicit provider selector lacks a command package")
    return _resolution(
        "provider_selector_resolver",
        "provider-selector:explicit-contract-argument-v1",
        render_provider_entry_command,
        policy=contract.capabilities.provider_selector_policy.value,
        argument="--provider-contract",
        value=contract.version,
    )


def _stage_identity(repository: Path, contract: T09ProviderContract) -> ConsumerResolution:
    del repository
    contract.validate_owner(
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        instance_name=contract.instance_name,
    )
    handler_ids = {
        StageIdentityPolicy.LEGACY: "stage-identity:legacy-v1",
        StageIdentityPolicy.TYPED_PROVIDER: "stage-identity:typed-provider-v1",
    }
    try:
        handler_id = handler_ids[contract.capabilities.stage_identity_policy]
    except KeyError as exc:  # pragma: no cover - enum exhaustiveness guard
        raise ConsumerResolutionError("stage identity policy has no resolver") from exc
    return _resolution(
        "stage_identity_resolver",
        handler_id,
        contract.validate_owner,
        policy=contract.capabilities.stage_identity_policy.value,
        archive_id=contract.evidence_archive_id,
        stage_id=contract.evidence_stage_id,
        owner_bound=True,
    )


def _production_assembly(
    repository: Path,
    contract: T09ProviderContract,
) -> ConsumerResolution | None:
    if contract.capabilities.command_package_family is not CommandPackageFamily.AUTONOMOUS:
        return None
    from giclab.control.production import probe_production_adapter_assembly

    details = probe_production_adapter_assembly(repository, contract)
    return _resolution(
        "production_adapter_assembly",
        "category3-production-wrapper:v1",
        probe_production_adapter_assembly,
        **details,
    )


def _package_effect_loader(
    repository: Path,
    contract: T09ProviderContract,
) -> ConsumerResolution | None:
    if contract.effect_registration is None:
        return None
    from giclab.control.effects import (
        load_registered_package_effects,
        validate_package_effect_registration,
    )

    identity = validate_package_effect_registration(repository, contract)
    if identity is None:  # pragma: no cover - guarded by the declaration above
        raise ConsumerResolutionError("declared package effect identity is unavailable")
    return _resolution(
        "package_effect_loader",
        "package-effects:exact-hash-bound-factory-v1",
        load_registered_package_effects,
        **identity.to_document(),
        repository_grants_authority=False,
    )


CONTROL_CONSUMERS: Final[Mapping[str, ContractConsumer]] = MappingProxyType(
    {
        consumer.name: consumer
        for consumer in (
            ContractConsumer("lifecycle_resolver", _lifecycle),
            ContractConsumer("metadata_controller", _metadata),
            ContractConsumer("replacement_authority_handler", _replacement),
            ContractConsumer("cleanup_handler", _cleanup),
            ContractConsumer("command_package_loader", _command_package),
            ContractConsumer("control_root_resolver", _control_root),
            ContractConsumer("authorization_policy_resolver", _authorization),
            ContractConsumer("package_transition_resolver", _package_transition),
            ContractConsumer("provider_selector_resolver", _provider_selector),
            ContractConsumer("stage_identity_resolver", _stage_identity),
            ContractConsumer("package_effect_loader", _package_effect_loader),
            ContractConsumer("production_adapter_assembly", _production_assembly),
        )
    }
)


def resolve_control_consumers(
    repository: Path,
    contract: T09ProviderContract,
    *,
    consumers: Mapping[str, ContractConsumer] = CONTROL_CONSUMERS,
) -> dict[str, ConsumerResolution | None]:
    """Resolve every registered consumer for one exact contract."""

    root = repository.resolve(strict=True)
    return {name: consumer.resolve(root, contract) for name, consumer in consumers.items()}


def expected_consumer_handler_id(
    name: str,
    contract: T09ProviderContract,
) -> str | None:
    """Return the handler identity required by one semantic contract declaration."""

    capabilities = contract.capabilities
    if name == "lifecycle_resolver":
        return f"campaign-lifecycle:{capabilities.lifecycle_family.value}"
    if name == "metadata_controller":
        return (
            None
            if capabilities.metadata_policy is MetadataPolicy.NONE
            else "model-metadata-receipt:strict-local-prelaunch-v1"
        )
    if name == "replacement_authority_handler":
        return (
            None
            if capabilities.replacement_policy is ReplacementPolicy.NONE
            else "provider-entry-authority:normalized-history-v1"
        )
    if name == "cleanup_handler":
        return {
            CleanupFamily.HISTORICAL: "cleanup:historical-provider-owner-v1",
            CleanupFamily.EARLY_JOURNAL: "cleanup:early-journal-v1",
            CleanupFamily.EMPIRICAL_PREFIX: "cleanup:empirical-prefix-v1",
        }[capabilities.cleanup_family]
    if name == "command_package_loader":
        return (
            None
            if capabilities.command_package_family is CommandPackageFamily.HISTORICAL
            else "command-package:registered-autonomous-v1"
        )
    if name == "control_root_resolver":
        return f"control-root:{capabilities.control_root_policy.value}"
    if name == "authorization_policy_resolver":
        return {
            AuthorizationPolicy.FROZEN_HISTORICAL: "authority:frozen-historical-v1",
            AuthorizationPolicy.LEGACY_LOCAL_SINGLE_USE: "authority:local-single-use-v1",
            AuthorizationPolicy.METADATA_BOUND_SINGLE_USE: (
                "authority:metadata-bound-single-use-v1"
            ),
        }[capabilities.authorization_policy]
    if name == "package_transition_resolver":
        return (
            None
            if capabilities.package_transition_policy is PackageTransitionPolicy.NONE
            else "package-transition:preempirical-descendant-v1"
        )
    if name == "provider_selector_resolver":
        return (
            None
            if capabilities.provider_selector_policy is ProviderSelectorPolicy.NONE
            else "provider-selector:explicit-contract-argument-v1"
        )
    if name == "stage_identity_resolver":
        return {
            StageIdentityPolicy.LEGACY: "stage-identity:legacy-v1",
            StageIdentityPolicy.TYPED_PROVIDER: "stage-identity:typed-provider-v1",
        }[capabilities.stage_identity_policy]
    if name == "production_adapter_assembly":
        return (
            None
            if capabilities.command_package_family is CommandPackageFamily.HISTORICAL
            else "category3-production-wrapper:v1"
        )
    if name == "package_effect_loader":
        return (
            None
            if contract.effect_registration is None
            else "package-effects:exact-hash-bound-factory-v1"
        )
    raise ConsumerResolutionError(f"unknown control consumer: {name}")
