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
    EffectMode,
    MetadataEnvelope,
    ProviderHandle,
    StructuralPrivacyFinding,
    TerminationUnavailable,
)
from giclab.control.composition import CompositionError, compose_control_plane
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
    LOCAL_STAGING = "local-staging"
    SECRET_CHANNEL = "secret-channel-qualification"
    METADATA_RECEIPT = "metadata-receipt"
    PROVIDER_PREFLIGHT = "provider-read-only-preflight"
    FINAL_METADATA_FRESHNESS = "final-metadata-freshness"
    LAUNCH = "launch"
    PROVIDER_ENTRY = "provider-entry"
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


class ShadowPrerequisitePolicy(StrEnum):
    """How prerequisite shadow evidence is satisfied before an effect boundary."""

    SELF_REHEARSAL = "self-rehearsal"
    VALIDATED_RECEIPTS = "validated-receipts"


@dataclass(frozen=True, slots=True)
class Category3Request:
    repository: Path
    contract: T09ProviderContract
    scenario: str
    expected_repository_commit: str
    expected_repository_tree: str
    state_capsule_sha256: str
    state_capsule_valid: bool
    shadow_prerequisite_policy: ShadowPrerequisitePolicy
    required_shadow_receipt_sha256s: tuple[str, ...] = ()
    deterministic_paths_valid: bool = True
    deterministic_storage_valid: bool = True


@dataclass(frozen=True, slots=True)
class PreparedCategory3:
    """Proof that every deterministic gate preceding fake effects has passed."""

    contract_version: str
    composition_sha256: str
    state_capsule_sha256: str
    stage_sha256: str
    shadow_prerequisite_policy: str
    shadow_receipt_sha256s: tuple[str, ...]
    shadow_effects_permitted: bool
    live_effects_permitted: bool
    _proof: object = field(repr=False, compare=False)


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
    if adapters.mode is not EffectMode.SHADOW_FAKE:
        _transition(
            transitions,
            Category3Phase.VERIFY_IDENTITY,
            "failed",
            detail="live adapters are unavailable in the stabilization package",
        )
        return PreparationOutcome(
            None,
            None,
            tuple(transitions),
            Category3Phase.VERIFY_IDENTITY.value,
            "live adapters are unavailable",
        )
    commit, tree = repository_identity(request.repository)
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

    if not request.state_capsule_valid or len(request.state_capsule_sha256) != 64:
        _transition(transitions, Category3Phase.STATE_CAPSULE, "failed")
        return PreparationOutcome(
            None,
            composition,
            tuple(transitions),
            Category3Phase.STATE_CAPSULE.value,
            "state capsule is invalid",
        )
    _transition(transitions, Category3Phase.STATE_CAPSULE, "passed")

    if request.shadow_prerequisite_policy is ShadowPrerequisitePolicy.VALIDATED_RECEIPTS:
        valid_receipts = bool(request.required_shadow_receipt_sha256s) and all(
            len(value) == 64 for value in request.required_shadow_receipt_sha256s
        )
    else:
        valid_receipts = request.scenario != ""
    if not valid_receipts:
        _transition(transitions, Category3Phase.SHADOW_RECEIPTS, "failed")
        return PreparationOutcome(
            None,
            composition,
            tuple(transitions),
            Category3Phase.SHADOW_RECEIPTS.value,
            "required shadow evidence is incomplete",
        )
    _transition(
        transitions,
        Category3Phase.SHADOW_RECEIPTS,
        "passed",
        detail=request.shadow_prerequisite_policy.value,
    )

    if not request.deterministic_paths_valid or not request.deterministic_storage_valid:
        _transition(
            transitions,
            Category3Phase.LOCAL_STAGING,
            "failed",
            detail="deterministic path or storage check failed",
        )
        return PreparationOutcome(
            None,
            composition,
            tuple(transitions),
            Category3Phase.LOCAL_STAGING.value,
            "deterministic staging gate failed",
        )
    try:
        stage_sha256 = adapters.host_runtime.stage()
    except AdapterFailure as exc:
        _transition(
            transitions,
            Category3Phase.LOCAL_STAGING,
            "failed",
            detail=str(exc),
        )
        return PreparationOutcome(
            None,
            composition,
            tuple(transitions),
            Category3Phase.LOCAL_STAGING.value,
            str(exc),
        )
    _transition(transitions, Category3Phase.LOCAL_STAGING, "passed")
    prepared = PreparedCategory3(
        contract_version=request.contract.version,
        composition_sha256=str(composition["semantic_sha256"]),
        state_capsule_sha256=request.state_capsule_sha256,
        stage_sha256=stage_sha256,
        shadow_prerequisite_policy=request.shadow_prerequisite_policy.value,
        shadow_receipt_sha256s=request.required_shadow_receipt_sha256s,
        shadow_effects_permitted=True,
        live_effects_permitted=False,
        _proof=_PREPARED_PROOF,
    )
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
    fake_evidence: list[dict[str, object]] = field(default_factory=list)
    raw_evidence: list[str] = field(default_factory=list)
    finalized_evidence: list[str] = field(default_factory=list)
    evaluator_outputs: list[str] = field(default_factory=list)
    pair_checkpoint_sha256: str | None = None
    cleanup_state: str = "not-started"
    cleanup_resumed: bool = False
    provider_resources_zero: bool | None = None
    privacy_clean: bool = True
    security_restored: bool = False

    def stop(self, phase: Category3Phase, reason: str) -> None:
        if self.stopping_phase is None:
            self.stopping_phase = phase.value
            self.stop_reason = reason


def _call_counts(adapters: Category3Adapters) -> dict[str, int]:
    counts = Counter(call.operation for call in adapters.audit.calls)
    return {
        "secret_reads": counts["secret.read"],
        "metadata_requests": counts["metadata.request"],
        "provider_gets": counts["provider.inventory"],
        "provider_posts": counts["provider.launch"] + counts["provider.terminate"],
        "launch_calls": counts["provider.launch"],
        "termination_calls": counts["provider.terminate"],
        "condition_reservations": counts["condition.reserve"],
        "condition_entries": counts["condition.enter"],
    }


def _result_document(
    request: Category3Request,
    adapters: Category3Adapters,
    preparation: PreparationOutcome,
    state: _TransactionState,
) -> dict[str, object]:
    counts = _call_counts(adapters)
    if state.provider_resources_zero is not True or state.cleanup_state == "unresolved":
        terminal_state = "category3-shadow-stopped-cleanup-unresolved"
    elif not state.privacy_clean:
        terminal_state = "category3-shadow-stopped-privacy-blocked"
    elif state.stopping_phase is None:
        terminal_state = "category3-shadow-complete-clean"
    else:
        terminal_state = "category3-shadow-stopped-cleanup-verified"
    composition = preparation.composition or {}
    document: dict[str, object] = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "scenario": request.scenario,
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
        "fake_evidence_outputs": state.fake_evidence,
        "evidence_retained": {
            "raw": state.raw_evidence,
            "finalized": state.finalized_evidence,
            "evaluator": state.evaluator_outputs,
            "pair_checkpoint_sha256": state.pair_checkpoint_sha256,
            "classification": "shadow-control-plane-output",
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
        "projected_cost_usd": "0.00",
        "undeclared_adapter_calls": list(adapters.audit.undeclared_calls),
        "zero_undeclared_calls": not adapters.audit.undeclared_calls,
        "shadow_only": True,
        "scientific_interpretation_allowed": False,
    }
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
        try:
            adapters.provider_transport.provider_entry(handle)
            _transition(state.transitions, Category3Phase.PROVIDER_ENTRY, "passed")
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
                adapters.host_runtime.preflight(handle)
                _transition(state.transitions, Category3Phase.HOST_PREFLIGHT, "passed")
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
        replacement_allowed = (
            request.contract.capabilities.replacement_policy is ReplacementPolicy.BOUNDED_PREFLIGHT
            and launch_ordinal < max_launches
        )
        if not replacement_allowed:
            state.stop(failed_phase, failed_reason)
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
            adapters.condition_runtime.reserve(run_id)
            state.condition_reserved.append(run_id)
            _transition(
                state.transitions,
                Category3Phase.CONDITION_RESERVATION,
                "passed",
                detail=run_id,
            )
            adapters.condition_runtime.enter(run_id)
            state.condition_consumed.append(run_id)
            _transition(
                state.transitions,
                Category3Phase.EMPIRICAL_ENTRY,
                "passed",
                detail=run_id,
            )
            run_output = adapters.condition_runtime.run(run_id)
            _transition(
                state.transitions,
                Category3Phase.CONDITION_EXECUTION,
                "passed",
                detail=run_id,
            )
            raw = adapters.condition_runtime.export_raw(run_id)
            state.raw_evidence.append(run_id)
            state.fake_evidence.append(
                {"run_id": run_id, "kind": "raw", "sha256": raw, "shadow_only": True}
            )
            adapters.evidence_store.record(kind="raw", identity=raw)
            _transition(
                state.transitions,
                Category3Phase.RAW_EXPORT,
                "passed",
                detail=run_id,
            )
            finalized = adapters.condition_runtime.finalize(run_id)
            state.finalized_evidence.append(run_id)
            state.fake_evidence.append(
                {
                    "run_id": run_id,
                    "kind": "finalized",
                    "sha256": finalized,
                    "shadow_only": True,
                }
            )
            adapters.evidence_store.record(kind="finalized", identity=finalized)
            _transition(
                state.transitions,
                Category3Phase.FINALIZATION,
                "passed",
                detail=run_id,
            )
            evaluated = adapters.condition_runtime.evaluate(run_id)
            state.evaluator_outputs.append(run_id)
            state.fake_evidence.append(
                {
                    "run_id": run_id,
                    "kind": "evaluator-control-output",
                    "sha256": evaluated,
                    "shadow_only": True,
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
        except AdapterFailure as exc:
            operation = adapters.audit.calls[-1].operation if adapters.audit.calls else ""
            phase = {
                "condition.reserve": Category3Phase.CONDITION_RESERVATION,
                "condition.enter": Category3Phase.EMPIRICAL_ENTRY,
                "condition.run": Category3Phase.CONDITION_EXECUTION,
                "condition.export_raw": Category3Phase.RAW_EXPORT,
                "condition.finalize": Category3Phase.FINALIZATION,
                "condition.evaluate": Category3Phase.EVALUATION,
                "evidence.record": Category3Phase.FINALIZATION,
            }.get(operation, Category3Phase.CONDITION_EXECUTION)
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
            state.pair_checkpoint_sha256 = checkpoint
            _transition(state.transitions, Category3Phase.PAIR_CHECKPOINT, "passed")


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


def execute_category3_transaction(
    request: Category3Request,
    *,
    adapters: Category3Adapters,
    composition_builder: CompositionBuilder = _default_composition_builder,
) -> dict[str, object]:
    """Execute the shared transaction with injected, fake-only effects."""

    preparation = prepare_category3(
        request,
        adapters=adapters,
        composition_builder=composition_builder,
    )
    if preparation.prepared is None:
        return _early_result(request, adapters, preparation)
    prepared = preparation.prepared
    if prepared._proof is not _PREPARED_PROOF or not prepared.shadow_effects_permitted:
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
