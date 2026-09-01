"""Stable control-plane projections over the central provider-contract registry."""

from __future__ import annotations

from typing import Any

from giclab.harness.t09_provider_contracts import T09ProviderContract


def project_contract_capabilities(contract: T09ProviderContract) -> dict[str, Any]:
    """Return the public semantic behavior surface for one exact contract."""

    capabilities = contract.capabilities
    return {
        "version": contract.version,
        "plan_id": contract.plan_id,
        "lifecycle_family": capabilities.lifecycle_family.value,
        "metadata_policy": capabilities.metadata_policy.value,
        "replacement_policy": capabilities.replacement_policy.value,
        "cleanup_family": capabilities.cleanup_family.value,
        "command_package_family": capabilities.command_package_family.value,
        "control_root_policy": capabilities.control_root_policy.value,
        "authorization_policy": capabilities.authorization_policy.value,
        "package_transition_policy": capabilities.package_transition_policy.value,
        "provider_selector_policy": capabilities.provider_selector_policy.value,
        "stage_identity_policy": capabilities.stage_identity_policy.value,
        "shadow_scenario": capabilities.shadow_scenario,
    }
