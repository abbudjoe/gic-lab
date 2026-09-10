"""Shared, typed Category 3 transaction controller.

The controller owns ordering and state.  Adapters own effects.  This module contains
no live adapter, secret source, dotenv loader, network client, provider SDK, or
scientific runtime.  The deterministic shadow uses this exact control flow.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

from giclab.control.adapters import (
    AdapterFailure,
    AmbiguousProviderOutcome,
    Category3Adapters,
    CleanupInterrupted,
    ConsumedConditionFailure,
    EffectAuthorityKind,
    FirstPairCheckpointDisposition,
    MetadataEnvelope,
    PrivacyUnresolved,
    ProviderHandle,
    ReplacementEligibleFailure,
    StructuralPrivacyFinding,
    TerminationUnavailable,
)
from giclab.control.composition import CompositionError, compose_control_plane
from giclab.control.proofs import (
    ControlProofError,
    ControlProofReference,
    ValidatedControlReceiptSet,
    ValidatedDeterministicStaging,
    ValidatedShadowRehearsal,
    validate_current_control_receipt_set,
    validate_deterministic_staging,
)
from giclab.harness.t09_candidate_inputs import CandidateSourceSnapshot
from giclab.harness.t09_provider_contracts import (
    MetadataPolicy,
    ReplacementPolicy,
    T09ProviderContract,
)

SHADOW_SCHEMA_VERSION: Final = "1.0.0"
_PREPARED_PROOF: Final = object()


class Category3Phase(StrEnum):
    VERIFY_IDENTITY = "verify-exact-repository-package-identity"
    OFFLINE_COMPOSITION = "offline-composition"
    STATE_CAPSULE = "state-capsule-snapshot"
    SHADOW_RECEIPTS = "shadow-rehearsal-receipt-validation"
    LOCAL_PACKAGE_ASSEMBLY = "local-package-assembly"
    SECRET_CHANNEL = "secret-channel-qualification"
    METADATA_RECEIPT = "metadata-receipt"
    PROVIDER_PREFLIGHT = "provider-read-only-preflight"
    FINAL_METADATA_FRESHNESS = "final-metadata-freshness"
    LAUNCH = "launch"
    PROVIDER_ENTRY = "provider-entry"
    HOST_PACKAGE_TRANSFER = "host-package-transfer"
    HOST_PREFLIGHT = "host-preflight"
    QUALIFICATION = "image-finalizer-qualification"
    SCIENTIFIC_FREEZE = "scientific-freeze"
    CONDITION_RESERVATION = "condition-reservation"
    EMPIRICAL_ENTRY = "empirical-entry"
    CONDITION_EXECUTION = "condition-execution"
    RAW_EXPORT = "raw-export"
    FINALIZATION = "finalization"
    EVALUATION = "evaluation"
    PAIR_CHECKPOINT = "first-pair-checkpoint"
    REMAINING_CONDITIONS = "remaining-conditions"
    CLEANUP = "cleanup"
    TERMINAL_VERIFICATION = "terminal-provider-security-verification"


@dataclass(frozen=True, slots=True)
class Category3Request:
    repository: Path
    contract: T09ProviderContract
    scenario: str
    expected_repository_commit: str
    expected_repository_tree: str
    control_proof: ControlProofReference | ValidatedShadowRehearsal
    source_inputs: CandidateSourceSnapshot | None = None


@dataclass(frozen=True, slots=True, init=False)
class PreparedCategory3:
    """Proof that every deterministic gate preceding fake effects has passed."""

    contract_version: str
    composition_sha256: str
    state_capsule_sha256: str
    local_assembly_sha256: str
    effect_authorization_context_sha256: str
    shadow_prerequisite_policy: str
    shadow_receipt_sha256s: tuple[str, ...]
    validated_receipts: ValidatedControlReceiptSet | None
    validated_staging: ValidatedDeterministicStaging
    shadow_effects_permitted: bool
    live_effects_permitted: bool
    _proof: object = field(repr=False, compare=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("PreparedCategory3 is minted only by exact validators")


@dataclass(frozen=True, slots=True)
class PreparationOutcome:
    prepared: PreparedCategory3 | None
    composition: Mapping[str, object] | None
    transitions: tuple[dict[str, object], ...]
    stopping_phase: str | None
    error: str | None


CompositionBuilder = Callable[[Path, T09ProviderContract], dict[str, object]]


def _default_composition_builder(
    repository: Path,
    contract: T09ProviderContract,
) -> dict[str, object]:
    return compose_control_plane(repository, contract=contract)


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def repository_identity(repository: Path) -> tuple[str, str]:
    """Return the exact local commit/tree identity without consulting a remote."""

    environment = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    values: list[str] = []
    for revision in ("HEAD", "HEAD^{tree}"):
        completed = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", revision],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=10,
        )
        values.append(completed.stdout.decode("ascii", "ignore").strip())
    return values[0], values[1]


def _transition(
    transitions: list[dict[str, object]],
    phase: Category3Phase,
    outcome: str,
    *,
    detail: str | None = None,
) -> None:
    entry: dict[str, object] = {
        "index": len(transitions) + 1,
        "phase": phase.value,
        "outcome": outcome,
    }
    if detail is not None:
        entry["detail"] = detail
    transitions.append(entry)


def prepare_category3(
    request: Category3Request,
    *,
    adapters: Category3Adapters,
    composition_builder: CompositionBuilder = _default_composition_builder,
) -> PreparationOutcome:
    """Run every deterministic prerequisite and mint the sole effect token."""

    transitions: list[dict[str, object]] = []
    context = adapters.authorization_context
    command_package_sha256 = request.contract.expected_command_manifest_sha256
    if request.source_inputs is not None:
        if adapters.authority.kind is not EffectAuthorityKind.SHADOW_ONLY:
            raise ValueError("candidate transaction cannot use live authority")
        command_package_sha256 = request.source_inputs.command_package_sha256(request.repository)
    if (
        adapters.authority.kind
        not in {
            EffectAuthorityKind.SHADOW_ONLY,
            EffectAuthorityKind.LIVE_AUTHORIZED,
        }
        or context.authority_kind is not adapters.authority.kind
        or context.provider_contract_version != request.contract.version
        or context.plan_id != request.contract.plan_id
        or context.plan_sha256 != request.contract.expected_plan_sha256
        or context.command_package_sha256 != command_package_sha256
        or context.control_commit != request.expected_repository_commit
        or context.control_tree != request.expected_repository_tree
        or context.candidate_source_binding_sha256
        != (None if request.source_inputs is None else request.source_inputs.digest)
        or not adapters.authority.authorizes(context)
    ):
        _transition(
            transitions,
            Category3Phase.VERIFY_IDENTITY,
            "failed",
            detail="effect authority does not bind this transaction",
        )
        return PreparationOutcome(
            None,
            None,
            tuple(transitions),
            Category3Phase.VERIFY_IDENTITY.value,
            "effect authority is unavailable",
        )
    commit, tree = (
        repository_identity(request.repository)
        if request.source_inputs is None
        else request.source_inputs.package_identity(request.repository)
    )
    if (commit, tree) != (
        request.expected_repository_commit,
        request.expected_repository_tree,
    ):
        _transition(
            transitions,
            Category3Phase.VERIFY_IDENTITY,
            "failed",
            detail="repository commit/tree differs from the exact request",
        )
        return PreparationOutcome(
            None,
            None,
            tuple(transitions),
            Category3Phase.VERIFY_IDENTITY.value,
            "exact repository identity mismatch",
        )
    _transition(transitions, Category3Phase.VERIFY_IDENTITY, "passed")

    try:
        if (
            request.source_inputs is not None
            and composition_builder is _default_composition_builder
        ):
            composition = compose_control_plane(
                request.repository, contract=request.contract, source_inputs=request.source_inputs
            )
        else:
            composition = composition_builder(request.repository, request.contract)
    except Exception as exc:
        _transition(
            transitions,
            Category3Phase.OFFLINE_COMPOSITION,
            "failed",
            detail=f"{type(exc).__name__}: {exc}",
        )
        return PreparationOutcome(
            None,
            None,
            tuple(transitions),
            Category3Phase.OFFLINE_COMPOSITION.value,
            f"offline composition failed: {exc}",
        )
    if composition.get("static_composition_valid") is not True:
        _transition(transitions, Category3Phase.OFFLINE_COMPOSITION, "failed")
        return PreparationOutcome(
            None,
            composition,
            tuple(transitions),
            Category3Phase.OFFLINE_COMPOSITION.value,
            "offline composition is incomplete",
        )
    _transition(transitions, Category3Phase.OFFLINE_COMPOSITION, "passed")

    validated_receipts: ValidatedControlReceiptSet | None = None
    proof = request.control_proof
    try:
        if isinstance(proof, ControlProofReference):
            validated_receipts = validate_current_control_receipt_set(
                request.repository,
                request.contract,
                proof,
            )
            state_capsule_sha256 = validated_receipts.state_capsule.semantic_sha256
            receipt_hashes = tuple(
                [
                    validated_receipts.receipt_semantic_sha256s["shadow_happy_path"],
                    *(
                        validated_receipts.failure_semantic_sha256s[name]
                        for name in sorted(validated_receipts.failure_semantic_sha256s)
                    ),
                ]
            )
            proof_policy = "validated-control-receipt-binding"
            command_package_sha256 = validated_receipts.command_package_sha256
            control_binding_semantic_sha256 = validated_receipts.binding_semantic_sha256
        elif isinstance(proof, ValidatedShadowRehearsal):
            if (
                not proof.is_valid()
                or proof.control_commit != request.expected_repository_commit
                or proof.control_tree != request.expected_repository_tree
                or proof.provider_contract_version != request.contract.version
                or proof.composition_sha256 != composition.get("semantic_sha256")
            ):
                raise ControlProofError("shadow rehearsal proof identity drifted")
            state_capsule_sha256 = proof.state_capsule.semantic_sha256
            receipt_hashes = ()
            proof_policy = "validated-static-shadow-rehearsal"
            command_package_sha256 = proof.staging.command_package_sha256
            control_binding_semantic_sha256 = proof.staging.semantic_sha256
        else:  # pragma: no cover - typed request exhaustiveness guard
            raise ControlProofError("control proof type is unsupported")
    except (ControlProofError, OSError, ValueError) as exc:
        _transition(
            transitions,
            Category3Phase.STATE_CAPSULE,
            "failed",
            detail=str(exc),
        )
        return PreparationOutcome(
            None,
            composition,
            tuple(transitions),
            Category3Phase.STATE_CAPSULE.value,
            f"control proof validation failed: {exc}",
        )
    _transition(transitions, Category3Phase.STATE_CAPSULE, "passed")
    if (
        command_package_sha256 != context.command_package_sha256
        or control_binding_semantic_sha256 != context.control_binding_semantic_sha256
    ):
        _transition(
            transitions,
            Category3Phase.SHADOW_RECEIPTS,
            "failed",
            detail="effect authority does not bind the validated control proof",
        )
        return PreparationOutcome(
            None,
            composition,
            tuple(transitions),
            Category3Phase.SHADOW_RECEIPTS.value,
            "effect authorization context drifted from the validated proof",
        )
    _transition(
        transitions,
        Category3Phase.SHADOW_RECEIPTS,
        "passed",
        detail=proof_policy,
    )

    try:
        if isinstance(proof, ValidatedShadowRehearsal):
            validated_staging = proof.staging
        else:
            validated_staging = validate_deterministic_staging(
                request.repository,
                request.contract,
                command_package_sha256=command_package_sha256,
            )
    except (ControlProofError, OSError, ValueError) as exc:
        _transition(
            transitions,
            Category3Phase.LOCAL_PACKAGE_ASSEMBLY,
            "failed",
            detail=str(exc),
        )
        return PreparationOutcome(
            None,
            composition,
            tuple(transitions),
            Category3Phase.LOCAL_PACKAGE_ASSEMBLY.value,
            f"deterministic staging validation failed: {exc}",
        )
    try:
        local_assembly_sha256 = adapters.host_runtime.assemble_local_package()
    except AdapterFailure as exc:
        _transition(
            transitions,
            Category3Phase.LOCAL_PACKAGE_ASSEMBLY,
            "failed",
            detail=str(exc),
        )
        return PreparationOutcome(
            None,
            composition,
            tuple(transitions),
            Category3Phase.LOCAL_PACKAGE_ASSEMBLY.value,
            str(exc),
        )
    _transition(transitions, Category3Phase.LOCAL_PACKAGE_ASSEMBLY, "passed")
    prepared = object.__new__(PreparedCategory3)
    object.__setattr__(prepared, "contract_version", request.contract.version)
    object.__setattr__(prepared, "composition_sha256", str(composition["semantic_sha256"]))
    object.__setattr__(prepared, "state_capsule_sha256", state_capsule_sha256)
    object.__setattr__(prepared, "local_assembly_sha256", local_assembly_sha256)
    object.__setattr__(
        prepared,
        "effect_authorization_context_sha256",
        context.semantic_sha256,
    )
    object.__setattr__(prepared, "shadow_prerequisite_policy", proof_policy)
    object.__setattr__(prepared, "shadow_receipt_sha256s", receipt_hashes)
    object.__setattr__(prepared, "validated_receipts", validated_receipts)
    object.__setattr__(prepared, "validated_staging", validated_staging)
    object.__setattr__(
        prepared,
        "shadow_effects_permitted",
        adapters.authority.kind is EffectAuthorityKind.SHADOW_ONLY,
    )
    object.__setattr__(
        prepared,
        "live_effects_permitted",
        adapters.authority.kind is EffectAuthorityKind.LIVE_AUTHORIZED,
    )
    object.__setattr__(prepared, "_proof", _PREPARED_PROOF)
    return PreparationOutcome(prepared, composition, tuple(transitions), None, None)


@dataclass(slots=True)
class _TransactionState:
    transitions: list[dict[str, object]]
    stopping_phase: str | None = None
    stop_reason: str | None = None
    metadata_consumed: bool = False
    provider_launch_outcome: str = "not-consumed"
    launch_count: int = 0
    replacement_count: int = 0
    handle: ProviderHandle | None = None
    condition_reserved: list[str] = field(default_factory=list)
    condition_consumed: list[str] = field(default_factory=list)
    effect_evidence: list[dict[str, object]] = field(default_factory=list)
    raw_evidence: list[str] = field(default_factory=list)
    finalized_evidence: list[str] = field(default_factory=list)
    evaluator_outputs: list[str] = field(default_factory=list)
    essential_failures: list[dict[str, object]] = field(default_factory=list)
    pair_checkpoint_sha256: str | None = None
    pair_checkpoint_decision: str | None = None
    pair_checkpoint_reasons: tuple[str, ...] = ()
    cleanup_state: str = "not-started"
    cleanup_resumed: bool = False
    provider_resources_zero: bool | None = None
    privacy_clean: bool = True
    security_restored: bool = False
    scientific_interpretation_allowed: bool = False

    def stop(self, phase: Category3Phase, reason: str) -> None:
        if self.stopping_phase is None:
            self.stopping_phase = phase.value
            self.stop_reason = reason


def _call_counts(adapters: Category3Adapters) -> dict[str, int]:
    counts = Counter(call.operation for call in adapters.audit.calls)
    diagnostics = adapters.diagnostics.control_evidence()
    accounting = diagnostics.get("accounting")
    conditions = accounting.get("conditions") if isinstance(accounting, dict) else None
    model_attempts = 0
    browser_actions = 0
    unknown_outcomes = 0
    if isinstance(conditions, dict):
        for document in conditions.values():
            if not isinstance(document, dict):
                continue
            lower = document.get("observed_lower_bound")
            condition = lower.get("condition") if isinstance(lower, dict) else None
            if isinstance(condition, dict):
                attempts = condition.get("model_call_attempts")
                actions = condition.get("browser_actions")
                model_attempts += attempts if type(attempts) is int else 0
                browser_actions += actions if type(actions) is int else 0
            unknown = document.get("unknown_outcomes")
            unknown_outcomes += unknown if type(unknown) is int else 0
    return {
        "secret_reads": counts["secret.read"],
        "metadata_requests": counts["metadata.request"],
        "provider_gets": counts["provider.inventory"],
        "provider_posts": counts["provider.launch"] + counts["provider.terminate"],
        "launch_calls": counts["provider.launch"],
        "termination_calls": counts["provider.terminate"],
        "condition_reservations": counts["condition.reserve"],
        "condition_entries": counts["condition.enter"],
        "model_call_attempts": model_attempts,
        "browser_actions": browser_actions,
        "unknown_model_outcomes": unknown_outcomes,
    }


def _result_document(
    request: Category3Request,
    adapters: Category3Adapters,
    preparation: PreparationOutcome,
    state: _TransactionState,
) -> dict[str, object]:
    counts = _call_counts(adapters)
    shadow_only = adapters.authority.kind is EffectAuthorityKind.SHADOW_ONLY
    terminal_prefix = "category3-shadow" if shadow_only else "category3-live"
    if state.provider_resources_zero is not True or state.cleanup_state == "unresolved":
        terminal_state = f"{terminal_prefix}-stopped-cleanup-unresolved"
    elif not state.privacy_clean:
        terminal_state = f"{terminal_prefix}-stopped-privacy-blocked"
    elif state.stopping_phase is None:
        terminal_state = f"{terminal_prefix}-complete-clean"
    else:
        terminal_state = f"{terminal_prefix}-stopped-cleanup-verified"
    composition = preparation.composition or {}
    production_evidence = dict(adapters.diagnostics.control_evidence())
    accounting = production_evidence.get("accounting")
    projected = accounting.get("projected_real_cost_usd") if isinstance(accounting, dict) else 0
    projected_cost = f"{float(projected):.2f}" if isinstance(projected, (int, float)) else "unknown"
    document: dict[str, object] = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "scenario": request.scenario,
        "implementation_flavor": adapters.implementation_flavor.value,
        "effect_authority": adapters.authority.kind.value,
        "effect_authorization_context_sha256": (
            adapters.authorization_context.public_semantic_sha256
        ),
        "provider_contract_version": request.contract.version,
        "repository_commit": request.expected_repository_commit,
        "repository_tree": request.expected_repository_tree,
        "composition_sha256": composition.get("semantic_sha256"),
        "command_package_sha256": composition.get("command_package_sha256"),
        "ordered_state_transitions": state.transitions,
        "adapter_call_ledger": [call.to_document() for call in adapters.audit.calls],
        "call_counts": counts,
        "authority_consumed": {
            "model_metadata": state.metadata_consumed,
            "provider_launch": state.provider_launch_outcome,
            "launch_count": state.launch_count,
            "replacement_count": state.replacement_count,
        },
        "condition_identities_reserved": state.condition_reserved,
        "condition_identities_consumed": state.condition_consumed,
        "scientific_attempt_consumption": {
            "count": len(state.condition_consumed),
            "run_ids": state.condition_consumed,
        },
        "evidence_retained": {
            "raw": state.raw_evidence,
            "finalized": state.finalized_evidence,
            "evaluator": state.evaluator_outputs,
            "pair_checkpoint_sha256": state.pair_checkpoint_sha256,
            "pair_checkpoint_decision": state.pair_checkpoint_decision,
            "pair_checkpoint_reasons": list(state.pair_checkpoint_reasons),
            "essential_failures": state.essential_failures,
            "classification": (
                "shadow-control-plane-output" if shadow_only else "live-control-plane-output"
            ),
        },
        "cleanup": {
            "state": state.cleanup_state,
            "resumed": state.cleanup_resumed,
            "provider_resources_zero": state.provider_resources_zero,
            "security_restored": state.security_restored,
            "privacy_clean": state.privacy_clean,
        },
        "earliest_stopping_phase": state.stopping_phase,
        "stop_reason": state.stop_reason,
        "terminal_state": terminal_state,
        "projected_cost_usd": projected_cost,
        "undeclared_adapter_calls": list(adapters.audit.undeclared_calls),
        "zero_undeclared_calls": not adapters.audit.undeclared_calls,
        "shadow_only": shadow_only,
        "scientific_interpretation_allowed": state.scientific_interpretation_allowed,
        "production_control_evidence": production_evidence,
    }
    document["fake_evidence_outputs" if shadow_only else "effect_evidence_outputs"] = (
        state.effect_evidence
    )
    # Validate serialization before irreversibly terminalizing the single-use grant.
    _canonical_sha256(document)
    authority_consumption = adapters.diagnostics.terminalize_authority(
        complete=(
            state.cleanup_state in {"complete", "not-required"}
            and state.provider_resources_zero is True
            and state.privacy_clean
            and state.security_restored
        )
    )
    production_evidence["authority_consumption"] = dict(authority_consumption)
    document["production_control_evidence"] = production_evidence
    document["semantic_sha256"] = _canonical_sha256(document)
    return document


def _early_result(
    request: Category3Request,
    adapters: Category3Adapters,
    preparation: PreparationOutcome,
) -> dict[str, object]:
    state = _TransactionState(
        transitions=list(preparation.transitions),
        stopping_phase=preparation.stopping_phase,
        stop_reason=preparation.error,
        cleanup_state="not-required",
        provider_resources_zero=True,
        security_restored=True,
    )
    return _result_document(request, adapters, preparation, state)


def _establish_provider(
    request: Category3Request,
    adapters: Category3Adapters,
    state: _TransactionState,
    envelope: MetadataEnvelope | None,
) -> None:
    if envelope is not None and not adapters.metadata_transport.is_fresh(envelope):
        _transition(state.transitions, Category3Phase.FINAL_METADATA_FRESHNESS, "failed")
        state.stop(Category3Phase.FINAL_METADATA_FRESHNESS, "metadata receipt expired")
        return
    _transition(state.transitions, Category3Phase.FINAL_METADATA_FRESHNESS, "passed")

    max_launches = request.contract.max_launch_count
    for launch_ordinal in range(1, max_launches + 1):
        try:
            handle = adapters.provider_transport.launch(launch_ordinal=launch_ordinal)
        except AmbiguousProviderOutcome as exc:
            state.launch_count += 1
            state.provider_launch_outcome = "ambiguous-consumed"
            _transition(
                state.transitions,
                Category3Phase.LAUNCH,
                "ambiguous",
                detail=str(exc),
            )
            state.stop(Category3Phase.LAUNCH, str(exc))
            return
        except AdapterFailure as exc:
            _transition(
                state.transitions,
                Category3Phase.LAUNCH,
                "failed",
                detail=str(exc),
            )
            state.stop(Category3Phase.LAUNCH, str(exc))
            return
        state.launch_count += 1
        state.provider_launch_outcome = "consumed"
        state.handle = handle
        _transition(
            state.transitions,
            Category3Phase.LAUNCH,
            "passed",
            detail=f"ordinal-{launch_ordinal}",
        )
        failed_phase: Category3Phase | None = None
        failed_reason = ""
        replacement_eligible = False
        try:
            adapters.provider_transport.provider_entry(handle)
            _transition(state.transitions, Category3Phase.PROVIDER_ENTRY, "passed")
        except ReplacementEligibleFailure as exc:
            failed_phase = Category3Phase.PROVIDER_ENTRY
            failed_reason = str(exc)
            replacement_eligible = True
            _transition(
                state.transitions,
                Category3Phase.PROVIDER_ENTRY,
                "failed",
                detail=failed_reason,
            )
        except AdapterFailure as exc:
            failed_phase = Category3Phase.PROVIDER_ENTRY
            failed_reason = str(exc)
            _transition(
                state.transitions,
                Category3Phase.PROVIDER_ENTRY,
                "failed",
                detail=failed_reason,
            )
        if failed_phase is None:
            try:
                adapters.host_runtime.transfer_package(handle)
                _transition(
                    state.transitions,
                    Category3Phase.HOST_PACKAGE_TRANSFER,
                    "passed",
                )
            except ReplacementEligibleFailure as exc:
                failed_phase = Category3Phase.HOST_PACKAGE_TRANSFER
                failed_reason = str(exc)
                replacement_eligible = True
                _transition(
                    state.transitions,
                    Category3Phase.HOST_PACKAGE_TRANSFER,
                    "failed",
                    detail=failed_reason,
                )
            except AdapterFailure as exc:
                failed_phase = Category3Phase.HOST_PACKAGE_TRANSFER
                failed_reason = str(exc)
                _transition(
                    state.transitions,
                    Category3Phase.HOST_PACKAGE_TRANSFER,
                    "failed",
                    detail=failed_reason,
                )
        if failed_phase is None:
            try:
                adapters.host_runtime.preflight(handle)
                _transition(state.transitions, Category3Phase.HOST_PREFLIGHT, "passed")
            except ReplacementEligibleFailure as exc:
                failed_phase = Category3Phase.HOST_PREFLIGHT
                failed_reason = str(exc)
                replacement_eligible = True
                _transition(
                    state.transitions,
                    Category3Phase.HOST_PREFLIGHT,
                    "failed",
                    detail=failed_reason,
                )
            except AdapterFailure as exc:
                failed_phase = Category3Phase.HOST_PREFLIGHT
                failed_reason = str(exc)
                _transition(
                    state.transitions,
                    Category3Phase.HOST_PREFLIGHT,
                    "failed",
                    detail=failed_reason,
                )
        if failed_phase is None:
            return
        replacement_allowed = (
            replacement_eligible
            and request.contract.capabilities.replacement_policy
            is ReplacementPolicy.BOUNDED_PREFLIGHT
            and launch_ordinal < max_launches
        )
        if not replacement_allowed:
            # Preserve the exact handle for the ordinary terminal cleanup path.
            # Remote cleanup must finish before that path terminates the host.
            state.stop(failed_phase, failed_reason)
            return
        try:
            adapters.provider_transport.terminate(handle)
        except TerminationUnavailable as exc:
            state.stop(failed_phase, f"{failed_reason}; replacement cleanup failed: {exc}")
            return
        state.handle = None
        inventory = adapters.provider_transport.inventory()
        if inventory != ():
            state.stop(failed_phase, f"{failed_reason}; replacement absence is unverified")
            return
        state.replacement_count += 1
    state.stop(Category3Phase.LAUNCH, "provider launch envelope exhausted")


def _run_conditions(
    request: Category3Request,
    adapters: Category3Adapters,
    state: _TransactionState,
) -> None:
    for index, run_id in enumerate(request.contract.run_ids):
        if index == 2:
            _transition(state.transitions, Category3Phase.REMAINING_CONDITIONS, "entered")
        try:
            active_phase = Category3Phase.CONDITION_RESERVATION
            adapters.condition_runtime.reserve(run_id)
            state.condition_reserved.append(run_id)
            _transition(
                state.transitions,
                Category3Phase.CONDITION_RESERVATION,
                "passed",
                detail=run_id,
            )
            active_phase = Category3Phase.EMPIRICAL_ENTRY
            adapters.condition_runtime.enter(run_id)
            state.condition_consumed.append(run_id)
            _transition(
                state.transitions,
                Category3Phase.EMPIRICAL_ENTRY,
                "passed",
                detail=run_id,
            )
            active_phase = Category3Phase.CONDITION_EXECUTION
            run_output = adapters.condition_runtime.run(run_id)
            _transition(
                state.transitions,
                Category3Phase.CONDITION_EXECUTION,
                "passed",
                detail=run_id,
            )
            active_phase = Category3Phase.RAW_EXPORT
            raw = adapters.condition_runtime.export_raw(run_id)
            state.raw_evidence.append(run_id)
            state.effect_evidence.append(
                {
                    "run_id": run_id,
                    "kind": "raw",
                    "sha256": raw,
                    "shadow_only": adapters.authority.kind is EffectAuthorityKind.SHADOW_ONLY,
                }
            )
            adapters.evidence_store.record(kind="raw", identity=raw)
            _transition(
                state.transitions,
                Category3Phase.RAW_EXPORT,
                "passed",
                detail=run_id,
            )
            active_phase = Category3Phase.FINALIZATION
            finalized = adapters.condition_runtime.finalize(run_id)
            state.finalized_evidence.append(run_id)
            state.effect_evidence.append(
                {
                    "run_id": run_id,
                    "kind": "finalized",
                    "sha256": finalized,
                    "shadow_only": adapters.authority.kind is EffectAuthorityKind.SHADOW_ONLY,
                }
            )
            adapters.evidence_store.record(kind="finalized", identity=finalized)
            _transition(
                state.transitions,
                Category3Phase.FINALIZATION,
                "passed",
                detail=run_id,
            )
            active_phase = Category3Phase.EVALUATION
            evaluated = adapters.condition_runtime.evaluate(run_id)
            state.evaluator_outputs.append(run_id)
            state.effect_evidence.append(
                {
                    "run_id": run_id,
                    "kind": "evaluator-control-output",
                    "sha256": evaluated,
                    "shadow_only": adapters.authority.kind is EffectAuthorityKind.SHADOW_ONLY,
                }
            )
            adapters.evidence_store.record(kind="evaluator", identity=evaluated)
            _transition(
                state.transitions,
                Category3Phase.EVALUATION,
                "passed",
                detail=run_id,
            )
            if not run_output:
                raise AdapterFailure("empty fake condition output")
        except ConsumedConditionFailure as exc:
            record = exc.record
            state.essential_failures.append(
                {
                    "run_id": record.run_id,
                    "stopping_phase": record.stopping_phase,
                    "failure_class": record.failure_class,
                    "manifest_sha256": record.manifest_sha256,
                    "receipt_sha256": record.receipt_sha256,
                    "export_receipt_sha256": record.export_receipt_sha256,
                    "essential_file_count": record.essential_file_count,
                    "essential_total_bytes": record.essential_total_bytes,
                    "evidence_binding_sha256": record.evidence_binding_sha256,
                    "infrastructure_invalid": True,
                    "unscored": True,
                }
            )
            state.effect_evidence.append(
                {
                    "run_id": record.run_id,
                    "kind": "essential-infrastructure-failure",
                    "sha256": record.evidence_binding_sha256,
                    "shadow_only": adapters.authority.kind is EffectAuthorityKind.SHADOW_ONLY,
                }
            )
            failure_phase = Category3Phase(record.stopping_phase)
            _transition(
                state.transitions,
                failure_phase,
                "essential-failure-sealed",
                detail=f"{run_id}: {record.failure_class}",
            )
            state.stop(failure_phase, str(exc))
            return
        except AdapterFailure as exc:
            # The operation selected by this controller is authoritative even
            # when admission fails before an adapter emits its audit event.
            phase = active_phase
            _transition(state.transitions, phase, "failed", detail=f"{run_id}: {exc}")
            state.stop(phase, str(exc))
            return
        if index == 1:
            try:
                checkpoint = adapters.evidence_store.checkpoint(name="task-a-pair")
            except AdapterFailure as exc:
                _transition(
                    state.transitions,
                    Category3Phase.PAIR_CHECKPOINT,
                    "failed",
                    detail=str(exc),
                )
                state.stop(Category3Phase.PAIR_CHECKPOINT, str(exc))
                return
            state.pair_checkpoint_sha256 = checkpoint.decision_sha256
            state.pair_checkpoint_decision = checkpoint.disposition.value
            state.pair_checkpoint_reasons = checkpoint.reasons
            if checkpoint.disposition is FirstPairCheckpointDisposition.STOP:
                detail = ", ".join(checkpoint.reasons) or "retained checkpoint stopped"
                _transition(
                    state.transitions,
                    Category3Phase.PAIR_CHECKPOINT,
                    FirstPairCheckpointDisposition.STOP.value,
                    detail=detail,
                )
                state.stop(Category3Phase.PAIR_CHECKPOINT, detail)
                return
            _transition(
                state.transitions,
                Category3Phase.PAIR_CHECKPOINT,
                FirstPairCheckpointDisposition.CONTINUE.value,
            )


def _cleanup(
    adapters: Category3Adapters,
    state: _TransactionState,
) -> None:
    state.cleanup_state = "in-progress"
    try:
        adapters.host_runtime.cleanup(state.handle)
    except CleanupInterrupted:
        state.cleanup_state = "resumable"
        state.cleanup_resumed = True
        _transition(state.transitions, Category3Phase.CLEANUP, "interrupted-resumable")
        try:
            adapters.host_runtime.cleanup(state.handle)
        except AdapterFailure as exc:
            state.cleanup_state = "unresolved"
            _transition(
                state.transitions,
                Category3Phase.CLEANUP,
                "failed",
                detail=str(exc),
            )
            state.stop(Category3Phase.CLEANUP, str(exc))
        else:
            state.cleanup_state = "complete"
            _transition(state.transitions, Category3Phase.CLEANUP, "resumed-complete")
    except AdapterFailure as exc:
        state.cleanup_state = "unresolved"
        _transition(state.transitions, Category3Phase.CLEANUP, "failed", detail=str(exc))
        state.stop(Category3Phase.CLEANUP, str(exc))
    else:
        state.cleanup_state = "complete"
        _transition(state.transitions, Category3Phase.CLEANUP, "passed")

    try:
        adapters.evidence_store.scan_privacy()
    except StructuralPrivacyFinding as exc:
        state.privacy_clean = False
        _transition(state.transitions, Category3Phase.CLEANUP, "privacy-blocked", detail=str(exc))
        state.stop(Category3Phase.CLEANUP, str(exc))
    except PrivacyUnresolved as exc:
        state.privacy_clean = False
        _transition(
            state.transitions,
            Category3Phase.CLEANUP,
            "privacy-unresolved-path-identity-changed",
            detail=str(exc),
        )
        state.stop(Category3Phase.CLEANUP, str(exc))
    except AdapterFailure as exc:
        state.privacy_clean = False
        _transition(
            state.transitions,
            Category3Phase.CLEANUP,
            "privacy-unresolved",
            detail=str(exc),
        )
        state.stop(Category3Phase.CLEANUP, str(exc))

    if state.handle is not None:
        terminated = False
        for _attempt in range(2):
            try:
                adapters.provider_transport.terminate(state.handle)
            except TerminationUnavailable as exc:
                _transition(
                    state.transitions,
                    Category3Phase.CLEANUP,
                    "termination-unavailable",
                    detail=str(exc),
                )
            else:
                terminated = True
                state.handle = None
                break
        if not terminated:
            state.cleanup_state = "unresolved"
            state.stop(Category3Phase.CLEANUP, "provider termination unavailable after retries")

    try:
        inventory = adapters.provider_transport.inventory()
    except AdapterFailure as exc:
        inventory = None
        _transition(
            state.transitions,
            Category3Phase.TERMINAL_VERIFICATION,
            "ambiguous",
            detail=str(exc),
        )
    state.provider_resources_zero = None if inventory is None else not inventory
    state.security_restored = state.cleanup_state == "complete" and (
        state.provider_resources_zero is True
    )
    _transition(
        state.transitions,
        Category3Phase.TERMINAL_VERIFICATION,
        "passed" if state.security_restored else "unresolved",
    )


def _execute_category3_transaction_body(
    request: Category3Request,
    *,
    adapters: Category3Adapters,
    composition_builder: CompositionBuilder = _default_composition_builder,
) -> dict[str, object]:
    """Execute the state machine while the public wrapper owns final release."""

    preparation = prepare_category3(
        request,
        adapters=adapters,
        composition_builder=composition_builder,
    )
    if preparation.prepared is None:
        return _early_result(request, adapters, preparation)
    prepared = preparation.prepared
    permission_valid = (
        adapters.authority.kind is EffectAuthorityKind.SHADOW_ONLY
        and prepared.shadow_effects_permitted
        and not prepared.live_effects_permitted
    ) or (
        adapters.authority.kind is EffectAuthorityKind.LIVE_AUTHORIZED
        and prepared.live_effects_permitted
        and not prepared.shadow_effects_permitted
    )
    if prepared._proof is not _PREPARED_PROOF or not permission_valid:
        raise CompositionError("Category 3 preparation token is invalid")
    state = _TransactionState(transitions=list(preparation.transitions))

    try:
        adapters.secret_channel.read()
    except AdapterFailure as exc:
        _transition(
            state.transitions,
            Category3Phase.SECRET_CHANNEL,
            "failed",
            detail=str(exc),
        )
        state.stop(Category3Phase.SECRET_CHANNEL, str(exc))
        _cleanup(adapters, state)
        return _result_document(request, adapters, preparation, state)
    _transition(state.transitions, Category3Phase.SECRET_CHANNEL, "passed")

    envelope: MetadataEnvelope | None = None
    if request.contract.capabilities.metadata_policy is MetadataPolicy.LOCAL_PRELAUNCH_RECEIPT:
        try:
            envelope = adapters.metadata_transport.request(
                contract_version=request.contract.version
            )
        except AdapterFailure as exc:
            _transition(
                state.transitions,
                Category3Phase.METADATA_RECEIPT,
                "failed",
                detail=str(exc),
            )
            state.stop(Category3Phase.METADATA_RECEIPT, str(exc))
            _cleanup(adapters, state)
            return _result_document(request, adapters, preparation, state)
        state.metadata_consumed = True
        _transition(state.transitions, Category3Phase.METADATA_RECEIPT, "passed")
    else:
        _transition(state.transitions, Category3Phase.METADATA_RECEIPT, "not-applicable")

    try:
        initial_inventory = adapters.provider_transport.inventory()
    except AdapterFailure as exc:
        _transition(
            state.transitions,
            Category3Phase.PROVIDER_PREFLIGHT,
            "failed",
            detail=str(exc),
        )
        state.stop(Category3Phase.PROVIDER_PREFLIGHT, str(exc))
        _cleanup(adapters, state)
        return _result_document(request, adapters, preparation, state)
    if initial_inventory != ():
        _transition(state.transitions, Category3Phase.PROVIDER_PREFLIGHT, "failed")
        state.stop(Category3Phase.PROVIDER_PREFLIGHT, "provider inventory is not clean")
        _cleanup(adapters, state)
        return _result_document(request, adapters, preparation, state)
    _transition(state.transitions, Category3Phase.PROVIDER_PREFLIGHT, "passed")

    _establish_provider(request, adapters, state, envelope)
    if state.stopping_phase is None and state.handle is not None:
        try:
            qualification = adapters.host_runtime.qualify(state.handle)
            adapters.evidence_store.record(kind="qualification", identity=qualification)
            _transition(state.transitions, Category3Phase.QUALIFICATION, "passed")
            freeze = adapters.host_runtime.freeze(state.handle)
            adapters.evidence_store.record(kind="scientific-freeze", identity=freeze)
            _transition(state.transitions, Category3Phase.SCIENTIFIC_FREEZE, "passed")
        except AdapterFailure as exc:
            phase = (
                Category3Phase.QUALIFICATION
                if not any(
                    transition["phase"] == Category3Phase.QUALIFICATION.value
                    and transition["outcome"] == "passed"
                    for transition in state.transitions
                )
                else Category3Phase.SCIENTIFIC_FREEZE
            )
            _transition(state.transitions, phase, "failed", detail=str(exc))
            state.stop(phase, str(exc))
    if state.stopping_phase is None:
        _run_conditions(request, adapters, state)

    _cleanup(adapters, state)
    return _result_document(request, adapters, preparation, state)


def execute_category3_transaction(
    request: Category3Request,
    *,
    adapters: Category3Adapters,
    composition_builder: CompositionBuilder = _default_composition_builder,
) -> dict[str, object]:
    """Execute one transaction and terminalize/release every held resource on exit."""

    try:
        return _execute_category3_transaction_body(
            request,
            adapters=adapters,
            composition_builder=composition_builder,
        )
    finally:
        try:
            adapters.diagnostics.terminalize_authority(complete=False)
        except (AdapterFailure, OSError, ValueError):
            # A damaged durable authority state remains non-replayable by validation.
            pass
        finally:
            adapters.diagnostics.release_resources()
