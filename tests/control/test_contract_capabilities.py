from __future__ import annotations

from pathlib import Path

import pytest

from giclab.harness import t09_provider_contracts as contracts_module
from giclab.harness.t09_pragmatic_provider import load_campaign_lifecycle
from giclab.harness.t09_provider_contracts import (
    PROVIDER_CONTRACTS,
    AuthorizationPolicy,
    CleanupFamily,
    CommandPackageFamily,
    ControlRootPolicy,
    LifecycleFamily,
    MetadataPolicy,
    PackageTransitionPolicy,
    ProviderSelectorPolicy,
    ReplacementPolicy,
    StageIdentityPolicy,
    T09ContractCapabilities,
    T09ProviderContractError,
)

ROOT = Path(__file__).resolve().parents[2]


EXPECTED = {
    "V3": ("historical-observer", "none", "historical"),
    "V4": ("historical-observer", "none", "historical"),
    "V5": ("historical-observer", "none", "historical"),
    "V6": ("retry4", "none", "historical"),
    "V7": ("retry4", "none", "historical"),
    "V8": ("autonomous-campaign", "none", "historical"),
    "V9": ("autonomous-campaign", "none", "historical"),
    "V10": ("autonomous-campaign", "none", "early-journal"),
    "V11": ("autonomous-campaign", "none", "early-journal"),
    "V12": ("autonomous-campaign", "local-prelaunch-receipt", "early-journal"),
    "V13": ("autonomous-campaign", "local-prelaunch-receipt", "early-journal"),
    "V14": ("autonomous-campaign", "local-prelaunch-receipt", "empirical-prefix"),
    "V15": ("autonomous-campaign", "local-prelaunch-receipt", "empirical-prefix"),
    "V16": ("autonomous-campaign", "local-prelaunch-receipt", "empirical-prefix"),
}


def test_every_registered_contract_has_explicit_capabilities() -> None:
    assert set(PROVIDER_CONTRACTS) == set(EXPECTED)
    for contract in PROVIDER_CONTRACTS.values():
        assert isinstance(contract.capabilities, T09ContractCapabilities)


def test_v3_through_v16_capability_mapping_matches_retained_behavior() -> None:
    observed = {
        version: (
            contract.capabilities.lifecycle_family.value,
            contract.capabilities.metadata_policy.value,
            contract.capabilities.cleanup_family.value,
        )
        for version, contract in PROVIDER_CONTRACTS.items()
    }
    assert observed == EXPECTED


def test_no_default_current_or_latest_contract_exists() -> None:
    for name in (
        "DEFAULT_PROVIDER_CONTRACT",
        "CURRENT_PROVIDER_CONTRACT",
        "LATEST_PROVIDER_CONTRACT",
    ):
        assert not hasattr(contracts_module, name)


def test_every_registered_autonomous_contract_loads_campaign_lifecycle() -> None:
    for contract in PROVIDER_CONTRACTS.values():
        if contract.capabilities.lifecycle_family is LifecycleFamily.AUTONOMOUS_CAMPAIGN:
            lifecycle = load_campaign_lifecycle(ROOT, contract=contract)
            assert lifecycle.contract == contract


def test_every_metadata_contract_resolves_through_metadata_policy() -> None:
    versions = {
        contract.version
        for contract in PROVIDER_CONTRACTS.values()
        if contract.capabilities.metadata_policy is MetadataPolicy.LOCAL_PRELAUNCH_RECEIPT
    }
    assert versions == {"V12", "V13", "V14", "V15", "V16"}


def test_replacement_cleanup_and_command_capabilities_are_explicit() -> None:
    for contract in PROVIDER_CONTRACTS.values():
        assert (
            contract.capabilities.replacement_policy is ReplacementPolicy.BOUNDED_PREFLIGHT
        ) == (contract.max_launch_count > 1)
        assert isinstance(contract.capabilities.cleanup_family, CleanupFamily)
        assert (
            contract.capabilities.command_package_family is CommandPackageFamily.AUTONOMOUS
        ) == (contract.execution_contract_path is not None)


def test_cross_capability_contradictions_fail_at_construction() -> None:
    with pytest.raises(T09ProviderContractError, match="lifecycle and command-package"):
        T09ContractCapabilities(
            lifecycle_family=LifecycleFamily.HISTORICAL_OBSERVER,
            metadata_policy=MetadataPolicy.NONE,
            replacement_policy=ReplacementPolicy.NONE,
            cleanup_family=CleanupFamily.HISTORICAL,
            command_package_family=CommandPackageFamily.AUTONOMOUS,
            control_root_policy=ControlRootPolicy.LEGACY_SHARED,
            authorization_policy=AuthorizationPolicy.FROZEN_HISTORICAL,
            package_transition_policy=PackageTransitionPolicy.NONE,
            provider_selector_policy=ProviderSelectorPolicy.NONE,
            stage_identity_policy=StageIdentityPolicy.LEGACY,
            shadow_scenario="invalid",
        )

    with pytest.raises(T09ProviderContractError, match="metadata receipt"):
        T09ContractCapabilities(
            lifecycle_family=LifecycleFamily.AUTONOMOUS_CAMPAIGN,
            metadata_policy=MetadataPolicy.LOCAL_PRELAUNCH_RECEIPT,
            replacement_policy=ReplacementPolicy.BOUNDED_PREFLIGHT,
            cleanup_family=CleanupFamily.EARLY_JOURNAL,
            command_package_family=CommandPackageFamily.AUTONOMOUS,
            control_root_policy=ControlRootPolicy.LEGACY_SHARED,
            authorization_policy=AuthorizationPolicy.FROZEN_HISTORICAL,
            package_transition_policy=PackageTransitionPolicy.NONE,
            provider_selector_policy=ProviderSelectorPolicy.NONE,
            stage_identity_policy=StageIdentityPolicy.LEGACY,
            shadow_scenario="invalid",
        )
