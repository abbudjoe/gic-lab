"""Deterministic Category 3 shadow scenarios over the shared controller."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from giclab.control.adapters import ImplementationFlavor
from giclab.control.category3 import (
    Category3Phase,
    Category3Request,
    CompositionBuilder,
    execute_category3_transaction,
    repository_identity,
)
from giclab.control.composition import compose_control_plane
from giclab.control.proofs import ValidatedShadowRehearsal, validate_shadow_rehearsal
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.scenarios import (
    ALL_REQUIRED_SCENARIOS,
    HAPPY_PATH,
)
from giclab.control.shadow_effects import (
    ShadowFaultPlan,
    build_production_shadow_assembly,
)
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness.t09_pragmatic_provider import T09ProviderError
from giclab.harness.t09_provider_contracts import T09ProviderContract


class ShadowValidationError(ValueError):
    """A shadow receipt contradicted its declared scenario contract."""


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _fault_plan(name: str) -> ShadowFaultPlan:
    scenarios = {
        HAPPY_PATH: ShadowFaultPlan(HAPPY_PATH),
        "lifecycle-unsupported": ShadowFaultPlan("lifecycle-unsupported"),
        "metadata-expired": ShadowFaultPlan(
            "metadata-expired",
            metadata_expires_before_launch=True,
        ),
        "provider-entry-replacement": ShadowFaultPlan(
            "provider-entry-replacement",
            fail_operation="provider.enter",
        ),
        "host-preflight-replacement": ShadowFaultPlan(
            "host-preflight-replacement",
            fail_operation="host.preflight",
        ),
        "condition-failure": ShadowFaultPlan(
            "condition-failure",
            fail_operation="condition.run",
        ),
        "raw-export-failure": ShadowFaultPlan(
            "raw-export-failure",
            fail_operation="condition.export_raw",
        ),
        "finalizer-failure": ShadowFaultPlan(
            "finalizer-failure",
            fail_operation="condition.finalize",
        ),
        "cleanup-interrupted-resumed": ShadowFaultPlan(
            "cleanup-interrupted-resumed",
            cleanup_interruption_count=1,
        ),
        "provider-termination-unavailable": ShadowFaultPlan(
            "provider-termination-unavailable",
            termination_failure_count=2,
        ),
        "structural-privacy-finding": ShadowFaultPlan(
            "structural-privacy-finding",
            fail_operation="evidence.scan_privacy",
        ),
        "ambiguous-provider-call-outcome": ShadowFaultPlan(
            "ambiguous-provider-call-outcome",
            fail_operation="provider.launch",
            ambiguous_inventory_after_launch=True,
        ),
        "known-provider-exception": ShadowFaultPlan("known-provider-exception"),
        "response-accounting-incomplete": ShadowFaultPlan("response-accounting-incomplete"),
        "ambiguous-task-model-send": ShadowFaultPlan("ambiguous-task-model-send"),
        "cost-token-admission-stop": ShadowFaultPlan(
            "cost-token-admission-stop",
            model_input_tokens_over_cap=True,
        ),
    }
    try:
        return scenarios[name]
    except KeyError as exc:
        raise ShadowValidationError(f"unknown Category 3 shadow scenario: {name}") from exc


def _unsupported_lifecycle_builder(
    repository: Path,
    contract: T09ProviderContract,
) -> dict[str, object]:
    def omitted_lifecycle(*_args: object, **_kwargs: object) -> object:
        raise T09ProviderError("registered contract lifecycle is unsupported")

    return compose_control_plane(
        repository,
        contract=contract,
        lifecycle_loader=omitted_lifecycle,  # type: ignore[arg-type]
    )


def _scenario_composition_builder(name: str) -> CompositionBuilder:
    if name == "lifecycle-unsupported":
        return _unsupported_lifecycle_builder

    def build(repository: Path, contract: T09ProviderContract) -> dict[str, object]:
        return compose_control_plane(repository, contract=contract)

    return build


def _expect(value: bool, message: str) -> None:
    if not value:
        raise ShadowValidationError(message)


def validate_shadow_receipt(receipt: Mapping[str, object]) -> None:
    """Validate scenario-specific authority, evidence, and cleanup semantics."""

    scenario = receipt.get("scenario")
    _expect(isinstance(scenario, str) and scenario in ALL_REQUIRED_SCENARIOS, "bad scenario")
    _expect(receipt.get("shadow_only") is True, "shadow receipt is not shadow-only")
    _expect(
        receipt.get("implementation_flavor") == ImplementationFlavor.PRODUCTION_WRAPPER.value,
        "tracked shadow did not use production wrappers",
    )
    _expect(
        receipt.get("scientific_interpretation_allowed") is False,
        "shadow receipt permits scientific interpretation",
    )
    _expect(receipt.get("zero_undeclared_calls") is True, "undeclared adapter call observed")
    counts = receipt.get("call_counts")
    authority = receipt.get("authority_consumed")
    cleanup = receipt.get("cleanup")
    evidence = receipt.get("evidence_retained")
    _expect(isinstance(counts, dict), "call counts missing")
    _expect(isinstance(authority, dict), "authority state missing")
    _expect(isinstance(cleanup, dict), "cleanup state missing")
    _expect(isinstance(evidence, dict), "evidence state missing")
    assert isinstance(scenario, str)
    assert isinstance(counts, dict)
    assert isinstance(authority, dict)
    assert isinstance(cleanup, dict)
    assert isinstance(evidence, dict)

    if scenario == "lifecycle-unsupported":
        _expect(
            receipt.get("earliest_stopping_phase") == Category3Phase.OFFLINE_COMPOSITION.value,
            "lifecycle omission did not stop at composition",
        )
        _expect(
            counts.get("secret_reads") == counts.get("metadata_requests") == 0,
            "lifecycle omission crossed the secret boundary",
        )
        _expect(
            counts.get("provider_gets") == counts.get("provider_posts") == 0,
            "lifecycle omission crossed the provider boundary",
        )
        return

    _expect(counts.get("secret_reads") == 1, "prepared shadow did not qualify secret channel")
    _expect(counts.get("metadata_requests") == 1, "metadata allowance count drifted")

    if scenario == "metadata-expired":
        _expect(
            receipt.get("earliest_stopping_phase") == Category3Phase.FINAL_METADATA_FRESHNESS.value,
            "expired metadata did not stop at final freshness",
        )
        _expect(counts.get("launch_calls") == 0, "expired metadata reached provider launch")
    elif scenario in {"provider-entry-replacement", "host-preflight-replacement"}:
        _expect(authority.get("launch_count") == 2, "bounded replacement launch count drifted")
        _expect(authority.get("replacement_count") == 1, "replacement was not recorded")
        _expect(
            receipt.get("earliest_stopping_phase") is None,
            "replacement did not recover: " + str(receipt.get("stop_reason")),
        )
    elif scenario == "condition-failure":
        _expect(
            receipt.get("earliest_stopping_phase") == Category3Phase.CONDITION_EXECUTION.value,
            "condition failure stopped at the wrong phase",
        )
        _expect(
            counts.get("condition_entries") == 1,
            "condition failure consumed an incorrect attempt prefix",
        )
    elif scenario == "raw-export-failure":
        _expect(
            receipt.get("earliest_stopping_phase") == Category3Phase.CONDITION_EXECUTION.value,
            "raw export failure stopped at the wrong phase",
        )
        _expect(len(evidence.get("raw", [])) == 0, "failed raw export was retained as complete")
        _expect(
            len(evidence.get("essential_failures", [])) == 1,
            "malformed raw publication lacked reconstructable failure evidence",
        )
    elif scenario == "finalizer-failure":
        _expect(
            receipt.get("earliest_stopping_phase") == Category3Phase.FINALIZATION.value,
            "finalizer failure stopped at the wrong phase",
        )
        _expect(len(evidence.get("raw", [])) == 1, "raw evidence was not preserved")
        _expect(len(evidence.get("evaluator", [])) == 0, "a failed finalizer produced evaluation")
    elif scenario == "cleanup-interrupted-resumed":
        _expect(cleanup.get("resumed") is True, "cleanup did not resume")
        _expect(cleanup.get("state") == "complete", "resumed cleanup did not finish")
        _expect(receipt.get("earliest_stopping_phase") is None, "resumed cleanup stopped campaign")
    elif scenario == "provider-termination-unavailable":
        _expect(cleanup.get("state") == "unresolved", "termination outage was hidden")
        _expect(
            cleanup.get("provider_resources_zero") is False,
            "termination outage was recorded as zero resources",
        )
        _expect(counts.get("termination_calls") == 2, "termination retry bound drifted")
    elif scenario == "structural-privacy-finding":
        _expect(cleanup.get("privacy_clean") is False, "privacy finding was hidden")
        _expect(
            receipt.get("terminal_state") == "category3-shadow-stopped-privacy-blocked",
            "privacy finding did not block publication",
        )
    elif scenario == "ambiguous-provider-call-outcome":
        _expect(
            authority.get("provider_launch") == "ambiguous-consumed",
            "ambiguous launch was recorded as unconsumed",
        )
        _expect(
            cleanup.get("provider_resources_zero") is None,
            "ambiguous launch was recorded as zero resources",
        )
    elif scenario in {
        "known-provider-exception",
        "response-accounting-incomplete",
        "ambiguous-task-model-send",
        "cost-token-admission-stop",
    }:
        _expect(
            receipt.get("earliest_stopping_phase") == Category3Phase.CONDITION_EXECUTION.value,
            "model accounting scenario stopped at the wrong phase",
        )
        production = receipt.get("production_control_evidence")
        accounting = production.get("accounting") if isinstance(production, dict) else None
        conditions = accounting.get("conditions") if isinstance(accounting, dict) else None
        _expect(isinstance(conditions, dict) and len(conditions) == 1, "accounting receipt missing")
        assert isinstance(conditions, dict)
        call_receipt = next(iter(conditions.values()))
        _expect(isinstance(call_receipt, dict), "accounting receipt malformed")
        assert isinstance(call_receipt, dict)
        terminals = call_receipt.get("terminal_counts")
        _expect(isinstance(terminals, dict), "terminal accounting is missing")
        assert isinstance(terminals, dict)
        if scenario == "known-provider-exception":
            _expect(
                terminals.get("sent_provider_error_reconciled") == 1,
                "known provider exception was not terminally reconciled",
            )
            _expect(call_receipt.get("unknown_outcomes") == 0, "known error became ambiguous")
        elif scenario in {"response-accounting-incomplete", "ambiguous-task-model-send"}:
            _expect(
                terminals.get("sent_outcome_unknown") == 1,
                "ambiguous model call was not charged unknown",
            )
            _expect(call_receipt.get("unknown_outcomes") == 1, "unknown outcome count drifted")
        else:
            _expect(
                counts.get("model_call_attempts") == 0,
                "admission stop crossed the model send boundary",
            )
    elif scenario == HAPPY_PATH:
        _expect(
            receipt.get("earliest_stopping_phase") is None,
            "happy path stopped: " + str(receipt.get("stop_reason")),
        )
        _expect(
            receipt.get("terminal_state") == "category3-shadow-complete-clean",
            "happy path did not close cleanly",
        )
        _expect(counts.get("condition_entries") == 4, "happy path attempt count drifted")
        _expect(counts.get("model_call_attempts") == 16, "happy model-call count drifted")
        _expect(counts.get("browser_actions") == 8, "happy browser-action count drifted")
        _expect(counts.get("unknown_model_outcomes") == 0, "happy path has unknown calls")
        _expect(cleanup.get("provider_resources_zero") is True, "happy cleanup left resources")


def run_shadow_scenario(
    repository: Path,
    *,
    contract: T09ProviderContract,
    scenario: str,
    state_capsule: Mapping[str, object] | None = None,
    rehearsal: ValidatedShadowRehearsal | None = None,
    fixed_tick: int = 1000,
) -> dict[str, object]:
    """Run one production-wrapper scenario over deterministic low-level effects."""

    commit, tree = repository_identity(repository)
    if rehearsal is None:
        if state_capsule is None:
            raise ShadowValidationError("shadow rehearsal requires the actual state capsule")
        lint = validate_active_version_dispatch(repository)
        registry = validate_registry_completeness(repository)
        composition = compose_control_plane(
            repository,
            contract=contract,
            registry_receipt=registry,
            version_lint_receipt=lint,
        )
        rehearsal = validate_shadow_rehearsal(
            repository,
            contract,
            registry_receipt=registry,
            version_lint_receipt=lint,
            composition_receipt=composition,
            state_capsule=state_capsule,
        )
    world = build_production_shadow_assembly(
        repository,
        contract,
        _fault_plan(scenario),
        rehearsal=rehearsal,
        fixed_tick=fixed_tick,
    )
    request = Category3Request(
        repository=repository,
        contract=contract,
        scenario=scenario,
        expected_repository_commit=commit,
        expected_repository_tree=tree,
        control_proof=rehearsal,
    )
    receipt = execute_category3_transaction(
        request,
        adapters=world.adapters(),
        composition_builder=_scenario_composition_builder(scenario),
    )
    validate_shadow_receipt(receipt)
    receipt["scenario_valid"] = True
    receipt.pop("semantic_sha256", None)
    receipt["semantic_sha256"] = _canonical_sha256(receipt)
    return receipt


def run_required_shadow_matrix(
    repository: Path,
    *,
    contract: T09ProviderContract,
    state_capsule: Mapping[str, object],
    registry_receipt: Mapping[str, object] | None = None,
    version_lint_receipt: Mapping[str, object] | None = None,
    composition_receipt: Mapping[str, object] | None = None,
    fixed_tick: int = 1000,
) -> dict[str, dict[str, object]]:
    """Run the production-coupled happy path and mandatory failure matrix."""

    lint = (
        dict(version_lint_receipt)
        if version_lint_receipt is not None
        else validate_active_version_dispatch(repository)
    )
    registry = (
        dict(registry_receipt)
        if registry_receipt is not None
        else validate_registry_completeness(repository)
    )
    composition = (
        dict(composition_receipt)
        if composition_receipt is not None
        else compose_control_plane(
            repository,
            contract=contract,
            registry_receipt=registry,
            version_lint_receipt=lint,
        )
    )
    rehearsal = validate_shadow_rehearsal(
        repository,
        contract,
        registry_receipt=registry,
        version_lint_receipt=lint,
        composition_receipt=composition,
        state_capsule=state_capsule,
    )

    return {
        scenario: run_shadow_scenario(
            repository,
            contract=contract,
            scenario=scenario,
            rehearsal=rehearsal,
            fixed_tick=fixed_tick,
        )
        for scenario in ALL_REQUIRED_SCENARIOS
    }
