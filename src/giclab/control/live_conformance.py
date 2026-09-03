"""Run the package-effect boundary with a temporary, network-disabled adapter.

The generated package module and its stand-in external grant exist only inside a
temporary Git repository.  The run uses the public controller and production
assembly without subclassing or patching either of them.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import MISSING, replace
from pathlib import Path
from types import MappingProxyType
from typing import Final, cast

from giclab.control.anti_shadow_lint import (
    public_receipt_topology_findings,
    validate_anti_shadow_lint,
)
from giclab.control.category3 import (
    Category3Request,
    execute_category3_transaction,
    repository_identity,
)
from giclab.control.composition import compose_control_plane
from giclab.control.effects import (
    EFFECT_AUTHORITY_SCHEMA_VERSION,
    EFFECT_PROTOCOL_VERSION,
    EffectExecutionMode,
    LoadedPackageEffects,
    hold_package_effect_registration,
    hold_transaction_root,
    load_registered_package_effects,
    project_live_authority_overlay,
    validate_external_live_effect_authority,
)
from giclab.control.production import build_production_adapter_assembly
from giclab.control.proofs import (
    REQUIRED_SHARED_SOURCES,
    ValidatedShadowRehearsal,
    validate_shadow_rehearsal,
)
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.shadow import run_shadow_scenario
from giclab.control.shadow_effects import (
    ShadowFaultPlan,
    build_production_shadow_assembly,
)
from giclab.control.state_capsule import generate_state_capsule
from giclab.control.target import resolve_selected_runtime_target
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness import (
    t09_pragmatic_provider,
    t09_provider_contracts,
    t09_sira_pilot,
)
from giclab.harness.t09_provider_contracts import (
    PackageEffectRegistration,
    T09ProviderContract,
)
from giclab.registry import load_json

LIVE_EFFECT_CONFORMANCE_SCHEMA_VERSION: Final = "3.0.0"
TEMPORARY_EFFECT_PATH: Final = (
    "experiments/EXP-0001-sira-simulative-vs-reactive/runtime/temporary_live_effect_conformance.py"
)
TEMPORARY_EFFECT_FACTORY: Final = "build_package_effects"
SHARED_CONTROLLER_ENTRY_POINT: Final = "giclab.control.category3.execute_category3_transaction"
PRODUCTION_ASSEMBLY_ENTRY_POINT: Final = (
    "giclab.control.production.build_production_adapter_assembly"
)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _package_effect_source() -> bytes:
    return b'''"""Temporary package effect for the zero-real-effect conformance gate."""

from giclab.control.shadow_effects import ShadowFaultPlan, build_live_shaped_no_network_effects


def build_package_effects(
    *, repository, contract, authorization_context, authority, held_transaction_root
):
    fault_plan = None
    if authorization_context.current_turn_scope == "T09-PR14-ROOT-MISMATCH-CONFORMANCE":
        fault_plan = ShadowFaultPlan(
            "live-root-replacement-terminalization",
            root_replacement_before_cleanup=True,
        )
    return build_live_shaped_no_network_effects(
        repository=repository,
        contract=contract,
        implementation_identity=authorization_context.effect_implementation,
        authorization_context=authorization_context,
        authority=authority,
        held_transaction_root=held_transaction_root,
        fault_plan=fault_plan,
    )
'''


def _copy_working_repository(source: Path, destination: Path) -> None:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=30,
    )
    destination.mkdir(mode=0o700)
    subprocess.run(
        ["git", "init", "-q", str(destination)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=10,
    )
    common = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    alternates = destination / ".git/objects/info/alternates"
    alternates.parent.mkdir(parents=True, exist_ok=True)
    alternates.write_text(str(Path(common) / "objects") + "\n", encoding="utf-8")
    for encoded_relative in completed.stdout.split(b"\0"):
        if not encoded_relative:
            continue
        relative = encoded_relative.decode("utf-8")
        source_path = source / relative
        destination_path = destination / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path, follow_symlinks=False)


def _commit_temporary_package(repository: Path) -> tuple[str, str]:
    environment = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_DATE": "2026-09-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-09-01T00:00:00+00:00",
    }
    subprocess.run(
        ["git", "-C", str(repository), "add", "--all"],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=30,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=GIC Lab Conformance",
            "-c",
            "user.email=gic-lab-conformance@example.invalid",
            "commit",
            "-q",
            "-m",
            "temporary package effect conformance",
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=30,
    )
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD", "HEAD^{tree}"],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    )
    commit, tree = completed.stdout.splitlines()
    return commit, tree


def _shared_byte_map(repository: Path) -> dict[str, str]:
    return {
        relative: hashlib.sha256((repository / relative).read_bytes()).hexdigest()
        for relative in sorted(REQUIRED_SHARED_SOURCES)
    }


@contextmanager
def _temporary_contract_registry(
    contract: T09ProviderContract,
) -> Iterator[None]:
    original_contracts = t09_provider_contracts.PROVIDER_CONTRACTS
    original_by_plan = t09_provider_contracts.PROVIDER_CONTRACTS_BY_PLAN_ID
    original_pilot_contracts = t09_sira_pilot.PROVIDER_CONTRACTS  # type: ignore[attr-defined]
    original_attempt_ids = t09_sira_pilot._AUTONOMOUS_ATTEMPT_IDS
    original_provider_contracts = (
        t09_pragmatic_provider.PROVIDER_CONTRACTS  # type: ignore[attr-defined]
    )
    contracts = MappingProxyType({**original_contracts, contract.version: contract})
    by_plan = MappingProxyType({item.plan_id: item for item in contracts.values()})
    try:
        t09_provider_contracts.PROVIDER_CONTRACTS = contracts  # type: ignore[misc]
        t09_provider_contracts.PROVIDER_CONTRACTS_BY_PLAN_ID = by_plan  # type: ignore[misc]
        t09_sira_pilot.PROVIDER_CONTRACTS = contracts  # type: ignore[attr-defined]
        t09_sira_pilot._AUTONOMOUS_ATTEMPT_IDS = frozenset(  # type: ignore[misc]
            run_id
            for item in contracts.values()
            if item.execution_contract_path is not None
            for run_id in item.run_ids
        )
        t09_pragmatic_provider.PROVIDER_CONTRACTS = contracts  # type: ignore[attr-defined]
        yield
    finally:
        t09_provider_contracts.PROVIDER_CONTRACTS = original_contracts  # type: ignore[misc]
        t09_provider_contracts.PROVIDER_CONTRACTS_BY_PLAN_ID = (  # type: ignore[misc]
            original_by_plan
        )
        t09_sira_pilot.PROVIDER_CONTRACTS = original_pilot_contracts  # type: ignore[attr-defined]
        t09_sira_pilot._AUTONOMOUS_ATTEMPT_IDS = original_attempt_ids  # type: ignore[misc]
        t09_pragmatic_provider.PROVIDER_CONTRACTS = (  # type: ignore[attr-defined]
            original_provider_contracts
        )


def _condition_traces(transaction_root: Path) -> dict[str, dict[str, object]]:
    traces: dict[str, dict[str, object]] = {}
    for call_path in sorted(transaction_root.rglob("provider-call-ledger.json")):
        call_document = load_json(call_path)
        run_id = call_document.get("run_id")
        calls = call_document.get("calls")
        browser_path = call_path.with_name("browser-action-ledger.json")
        browser_document = load_json(browser_path)
        actions = browser_document.get("actions")
        if (
            not isinstance(run_id, str)
            or not isinstance(calls, list)
            or not isinstance(actions, list)
        ):
            raise ValueError("conformance condition ledgers are malformed")
        call_ids = [item.get("call_id") for item in calls if isinstance(item, dict)]
        roles = [item.get("role") for item in calls if isinstance(item, dict)]
        terminal_states = [item.get("terminal_state") for item in calls if isinstance(item, dict)]
        if (
            len(call_ids) != len(calls)
            or not all(isinstance(item, str) for item in call_ids)
            or len(set(call_ids)) != len(call_ids)
            or not all(isinstance(item, str) for item in roles)
            or terminal_states != ["sent_response_reconciled"] * len(calls)
        ):
            raise ValueError("conformance call identities or terminal states drifted")
        traces[run_id] = {
            "model_call_count": len(calls),
            "model_roles": sorted(set(cast(list[str], roles))),
            "browser_action_count": len(actions),
            "stable_unique_call_ids": True,
            "terminal_states_complete": True,
        }
    return traces


def _raw_chain(
    transaction_root: Path,
    evaluations: object,
) -> dict[str, object]:
    manifests = sorted(transaction_root.rglob("raw-attempt-manifest.json"))
    receipts = sorted(transaction_root.rglob("raw-attempt-complete.json"))
    finalizations = sorted(transaction_root.rglob("finalization-complete.json"))
    sessions = sorted(transaction_root.rglob("session.json"))
    if not manifests or not (
        len(manifests) == len(receipts) == len(finalizations) == len(sessions)
    ):
        raise ValueError("conformance raw/finalizer chain is incomplete")
    manifest_by_run = {cast(str, load_json(path)["run_id"]): path for path in manifests}
    receipt_by_run = {cast(str, load_json(path)["run_id"]): path for path in receipts}
    finalization_by_run = {cast(str, load_json(path)["run_id"]): path for path in finalizations}
    run_ids = set(manifest_by_run)
    exact_consumption = run_ids == set(receipt_by_run) == set(finalization_by_run)
    answer_chain_valid = exact_consumption
    evaluator_chain_valid = isinstance(evaluations, dict) and set(evaluations) == run_ids
    if exact_consumption:
        for run_id in sorted(run_ids):
            manifest = manifest_by_run[run_id]
            raw_receipt = receipt_by_run[run_id]
            finalization_path = finalization_by_run[run_id]
            finalization = load_json(finalization_path)
            completion_path = manifest.parent / "raw/condition-answer.json"
            process_path = manifest.parent / "raw/process-outcome.json"
            answer = load_json(completion_path).get("answer")
            session = finalization_path.with_name("session.json")
            exact_sha_fields = (
                "runtime_qualification_sha256",
                "finalizer_source_sha256",
                "finalizer_projection_source_sha256",
                "finalizer_selector_sha256",
                "finalizer_schema_sha256",
                "interpreter_sha256",
                "dependency_manifest_sha256",
                "dependency_tree_sha256",
                "evaluator_dependency_tree_sha256",
                "evaluator_contract_sha256",
            )
            if (
                finalization.get("consumed_raw_manifest_sha256")
                != hashlib.sha256(manifest.read_bytes()).hexdigest()
                or finalization.get("consumed_raw_receipt_sha256")
                != hashlib.sha256(raw_receipt.read_bytes()).hexdigest()
                or finalization.get("consumed_raw_completion_sha256")
                != hashlib.sha256(completion_path.read_bytes()).hexdigest()
                or finalization.get("consumed_process_outcome_sha256")
                != hashlib.sha256(process_path.read_bytes()).hexdigest()
                or finalization.get("execution_mode") != "qualified-local"
                or not isinstance(finalization.get("runtime_qualification_id"), str)
                or not isinstance(finalization.get("raw_output_root"), str)
                or not isinstance(finalization.get("finalized_output_root"), str)
                or not isinstance(finalization.get("interpreter"), str)
                or not cast(str, finalization["interpreter"]).startswith("/")
                or any(
                    not isinstance(finalization.get(field), str)
                    or len(cast(str, finalization[field])) != 64
                    for field in exact_sha_fields
                )
                or not isinstance(answer, str)
                or not session.is_file()
                or answer not in session.read_text(encoding="utf-8")
            ):
                exact_consumption = False
                answer_chain_valid = False
                break
            evaluation = evaluations.get(run_id) if isinstance(evaluations, dict) else None
            if (
                not isinstance(evaluation, dict)
                or evaluation.get("evaluator_valid") is not True
                or evaluation.get("task_completed") is not True
                or evaluation.get("answer_produced") is not True
                or not isinstance(evaluation.get("receipt_sha256"), str)
                or len(cast(str, evaluation["receipt_sha256"])) != 64
            ):
                evaluator_chain_valid = False
    return {
        "attempt_count": len(manifests),
        "raw_files_hash_validated": True,
        "finalizer_consumed_raw_manifests": exact_consumption,
        "effect_answer_reached_finalized_session": answer_chain_valid,
        "evaluator_consumed_finalized_sessions": evaluator_chain_valid,
    }


def _typed_failure_accounting(
    repository: Path,
    contract: T09ProviderContract,
    rehearsal: ValidatedShadowRehearsal,
) -> dict[str, object]:
    expected = {
        "known-provider-exception": ("sent_provider_error_reconciled", 0),
        "ambiguous-task-model-send": ("sent_outcome_unknown", 1),
        "response-accounting-incomplete": ("sent_outcome_unknown", 1),
    }
    result: dict[str, object] = {}
    for scenario, (terminal, unknown) in expected.items():
        receipt = run_shadow_scenario(
            repository,
            contract=contract,
            scenario=scenario,
            rehearsal=rehearsal,
        )
        production = receipt.get("production_control_evidence")
        accounting = production.get("accounting") if isinstance(production, dict) else None
        conditions = accounting.get("conditions") if isinstance(accounting, dict) else None
        if not isinstance(conditions, dict) or len(conditions) != 1:
            raise ValueError("typed failure conformance lacks one condition ledger")
        condition = next(iter(conditions.values()))
        if not isinstance(condition, dict):
            raise ValueError("typed failure conformance ledger is malformed")
        terminals = condition.get("terminal_counts")
        if (
            not isinstance(terminals, dict)
            or terminals.get(terminal) != 1
            or condition.get("unknown_outcomes") != unknown
            or not isinstance(accounting, dict)
            or accounting.get("zero_retries") is not True
        ):
            raise ValueError("typed failure conformance disposition drifted")
        call_counts = receipt.get("call_counts")
        if not isinstance(call_counts, dict):
            raise ValueError("typed failure conformance call counts are absent")
        result[scenario] = {
            "terminal_state": terminal,
            "unknown_outcomes": unknown,
            "model_call_attempts": call_counts.get("model_call_attempts"),
            "zero_retries": True,
        }
    return result


def _execute_review_fault(
    repository: Path,
    contract: T09ProviderContract,
    rehearsal: ValidatedShadowRehearsal,
    fault_plan: ShadowFaultPlan,
) -> dict[str, object]:
    """Exercise one review-only deterministic failure through the shared controller."""

    commit, tree = repository_identity(repository)
    world = build_production_shadow_assembly(
        repository,
        contract,
        fault_plan,
        rehearsal=rehearsal,
    )
    return execute_category3_transaction(
        Category3Request(
            repository=repository,
            contract=contract,
            scenario=fault_plan.name,
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=rehearsal,
        ),
        adapters=world.adapters(),
    )


def _root_replacement_terminalization_subreceipt(
    repository: Path,
    contract: T09ProviderContract,
    rehearsal: ValidatedShadowRehearsal,
) -> dict[str, object]:
    """Exercise the full live-shaped controller after its root pathname is replaced."""

    held_source = hold_package_effect_registration(repository, contract)
    if held_source is None:
        raise ValueError("root-replacement probe lacks its held package source")
    external_root = repository.parent.resolve(strict=True)
    transaction_root = external_root / "private-root-mismatch-transaction"
    transaction_root.mkdir(mode=0o700)
    held_root = hold_transaction_root(transaction_root)
    prefix = contract.authorization_prefix
    if not isinstance(prefix, str):
        raise ValueError("root-replacement probe lacks its contract authorization prefix")
    reference = prefix + "CONFORMANCE-ROOT-MISMATCH-" + contract.source_commit[:12]
    turn_scope = "T09-PR14-ROOT-MISMATCH-CONFORMANCE"
    overlay_document = project_live_authority_overlay(
        repository,
        contract,
        held_transaction_root=held_root,
        effect_implementation=held_source.identity,
        control_binding_semantic_sha256=rehearsal.staging.semantic_sha256,
        external_authorization_reference=reference,
        current_turn_scope=turn_scope,
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
    )
    overlay_path = external_root / "private-root-mismatch-overlay.json"
    overlay_path.write_bytes(_canonical_bytes(overlay_document))
    overlay_path.chmod(0o600)
    context, authority = validate_external_live_effect_authority(
        repository,
        contract,
        overlay_path=overlay_path,
        held_transaction_root=held_root,
        effect_implementation=held_source.identity,
        control_binding_semantic_sha256=rehearsal.staging.semantic_sha256,
        current_turn_scope=turn_scope,
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
    )
    loaded = load_registered_package_effects(
        repository,
        contract,
        authorization_context=context,
        authority=authority,
        held_source=held_source,
    )
    world = build_production_adapter_assembly(
        repository,
        contract,
        low_level_effects=loaded.effects,
        authorization_context=context,
        authority=authority,
        held_transaction_root=held_root,
        held_effect_source=loaded.held_source,
    )
    commit, tree = repository_identity(repository)
    result = execute_category3_transaction(
        Category3Request(
            repository=repository,
            contract=contract,
            scenario="live-root-replacement-terminalization",
            expected_repository_commit=commit,
            expected_repository_tree=tree,
            control_proof=rehearsal,
        ),
        adapters=world.adapters(),
    )
    evidence = result.get("production_control_evidence")
    consumption = evidence.get("authority_consumption") if isinstance(evidence, dict) else None
    cleanup = result.get("cleanup")
    replacement = transaction_root / "replacement-sentinel.bin"
    descriptor_released = False
    try:
        held_root.revalidate_descriptor()
    except ValueError:
        descriptor_released = True
    if (
        result.get("terminal_state") != "category3-live-stopped-privacy-blocked"
        or not isinstance(evidence, dict)
        or evidence.get("cleanup_used_held_root_after_path_mismatch") is not True
        or not isinstance(consumption, dict)
        or consumption.get("terminal_state") != "terminal-failed-nonreplayable"
        or not replacement.is_file()
        or replacement.read_bytes() != b"replacement-directory-must-remain-unchanged\n"
        or tuple(transaction_root.iterdir()) != (replacement,)
        or not descriptor_released
    ):
        raise ValueError("root-replacement controller probe did not terminalize cleanly")
    return {
        "terminal_result_returned": True,
        "held_root_cleanup_used": True,
        "replacement_directory_unchanged": True,
        "privacy_path_identity_unresolved": True,
        "authority_terminal_state": "terminal-failed-nonreplayable",
        "held_descriptors_released": True,
        "provider_resources_zero": cleanup.get("provider_resources_zero")
        if isinstance(cleanup, dict)
        else False,
        "scientific_interpretation_allowed": False,
    }


def _review_failure_subreceipts(
    repository: Path,
    contract: T09ProviderContract,
    rehearsal: ValidatedShadowRehearsal,
) -> dict[str, object]:
    """Return bounded public facts from the mandatory review failure probes."""

    unscored = _execute_review_fault(
        repository,
        contract,
        rehearsal,
        ShadowFaultPlan(
            "review-unscored-task-a-checkpoint",
            evaluator_unscored_run_index=1,
        ),
    )
    ambiguous = _execute_review_fault(
        repository,
        contract,
        rehearsal,
        ShadowFaultPlan("ambiguous-task-model-send"),
    )
    nonzero = _execute_review_fault(
        repository,
        contract,
        rehearsal,
        ShadowFaultPlan("process-exit-nonzero-completed"),
    )
    raw_replacement = _execute_review_fault(
        repository,
        contract,
        rehearsal,
        ShadowFaultPlan(
            "review-raw-replacement",
            held_identity_fault="raw-same-size-swap-before-finalizer",
        ),
    )
    understated_provider_cost = _execute_review_fault(
        repository,
        contract,
        rehearsal,
        ShadowFaultPlan(
            "review-understated-provider-cost",
            provider_cost_receipt_fault="zero-price",
        ),
    )
    omitted_provider_slot = _execute_review_fault(
        repository,
        contract,
        rehearsal,
        ShadowFaultPlan(
            "provider-entry-replacement",
            provider_cost_receipt_fault="omitted-closed-slot",
        ),
    )
    oversized_manifest = _execute_review_fault(
        repository,
        contract,
        rehearsal,
        ShadowFaultPlan(
            "review-oversized-essential-manifest",
            fail_operation="condition.run",
            essential_envelope_fault="oversized-manifest",
        ),
    )
    sensitive_receipt = _execute_review_fault(
        repository,
        contract,
        rehearsal,
        ShadowFaultPlan(
            "review-sensitive-essential-receipt",
            fail_operation="condition.run",
            essential_envelope_fault="header-completion-field",
        ),
    )

    def counts(receipt: dict[str, object]) -> dict[str, object]:
        value = receipt.get("call_counts")
        if not isinstance(value, dict):
            raise ValueError("review conformance call counts are absent")
        return value

    def production(receipt: dict[str, object]) -> dict[str, object]:
        value = receipt.get("production_control_evidence")
        if not isinstance(value, dict):
            raise ValueError("review conformance production evidence is absent")
        return value

    unscored_evidence = production(unscored)
    checkpoint = unscored_evidence.get("first_pair_checkpoint")
    if not isinstance(checkpoint, dict):
        raise ValueError("unscored checkpoint did not retain its exact decision")
    checkpoint_reasons = checkpoint.get("reasons")
    checkpoint_counts = counts(unscored)
    if (
        checkpoint.get("decision") != "stop-before-task-b"
        or not isinstance(checkpoint_reasons, list)
        or "task_a_valid_scored_attempt_missing" not in checkpoint_reasons
        or checkpoint_counts.get("condition_entries") != 2
        or checkpoint_counts.get("condition_reservations") != 2
    ):
        raise ValueError("unscored Task A checkpoint did not stop before Task B")

    failure_documents: dict[str, dict[str, object]] = {}
    for name, receipt, expected_class in (
        ("ambiguous-send-essential-failure", ambiguous, "ambiguous-send"),
        ("nonzero-process-exit-essential-failure", nonzero, "process-exit-nonzero"),
    ):
        evidence = production(receipt)
        failures = evidence.get("essential_failures")
        if not isinstance(failures, dict) or len(failures) != 1:
            raise ValueError(f"{name} did not preserve one essential failure")
        failure = next(iter(failures.values()))
        retained = receipt.get("evidence_retained")
        if (
            not isinstance(failure, dict)
            or failure.get("failure_class") != expected_class
            or failure.get("unscored") is not True
            or failure.get("retry_count") != 0
            or not isinstance(failure.get("manifest_sha256"), str)
            or not isinstance(failure.get("receipt_sha256"), str)
            or not isinstance(failure.get("export_receipt_sha256"), str)
            or not isinstance(retained, dict)
            or retained.get("finalized") != []
            or retained.get("evaluator") != []
        ):
            raise ValueError(f"{name} essential evidence is incomplete")
        failure_documents[name] = {
            "failure_class": expected_class,
            "sealed": True,
            "exported_and_acknowledged": True,
            "unscored": True,
            "zero_retry": True,
            "cleanup_complete": receipt.get("cleanup")
            == {
                "state": "complete",
                "resumed": False,
                "provider_resources_zero": True,
                "security_restored": True,
                "privacy_clean": True,
            },
            "complete_envelope_file_count": failure.get("file_count"),
            "complete_envelope_total_bytes": failure.get("total_bytes"),
            "manifest_receipt_export_scanned": True,
        }

    raw_evidence = production(raw_replacement)
    raw_held = raw_evidence.get("held_evidence")
    raw_counts = counts(raw_replacement)
    raw_retained = raw_replacement.get("evidence_retained")
    if (
        raw_replacement.get("earliest_stopping_phase") != "finalization"
        or raw_counts.get("condition_entries") != 1
        or raw_counts.get("condition_reservations") != 1
        or not isinstance(raw_held, dict)
        or raw_held.get("revalidated_across_consumers") is not True
        or not isinstance(raw_retained, dict)
        or raw_retained.get("evaluator") != []
        or not isinstance(raw_replacement.get("stop_reason"), str)
    ):
        raise ValueError("same-size raw replacement was not rejected at finalization")

    understated_counts = counts(understated_provider_cost)
    omitted_counts = counts(omitted_provider_slot)
    if (
        understated_provider_cost.get("earliest_stopping_phase") != "first-pair-checkpoint"
        or understated_counts.get("condition_entries") != 2
        or omitted_provider_slot.get("earliest_stopping_phase") != "first-pair-checkpoint"
        or omitted_counts.get("condition_entries") != 2
        or "could not be sealed and exported" not in str(oversized_manifest.get("stop_reason"))
        or "could not be sealed and exported" not in str(sensitive_receipt.get("stop_reason"))
    ):
        raise ValueError("residual cost or essential-envelope probes did not fail closed")

    with tempfile.TemporaryDirectory(prefix="giclab-public-topology-negative-") as directory:
        probe_root = Path(directory)
        receipt_root = probe_root / "control/receipts/packages/v16"
        receipt_root.mkdir(parents=True)
        (receipt_root / "injected.json").write_bytes(
            _canonical_bytes({"held_transaction_root": {"path": "/tmp/private-root", "inode": 7}})
        )
        topology_codes = sorted(
            {finding.code for finding in public_receipt_topology_findings(probe_root)}
        )
    if topology_codes != ["T09S023", "T09S024"]:
        raise ValueError("public runtime-topology injection was not rejected")

    return {
        "unscored-task-a-checkpoint-stop": {
            "decision": "stop-before-task-b",
            "reason": "task_a_valid_scored_attempt_missing",
            "task_b_condition_reservations": 0,
            "task_b_condition_entries": 0,
            "cleanup_complete": unscored.get("cleanup")
            == {
                "state": "complete",
                "resumed": False,
                "provider_resources_zero": True,
                "security_restored": True,
                "privacy_clean": True,
            },
        },
        **failure_documents,
        "raw-replacement-rejection": {
            "same_size_replacement_rejected": True,
            "stopping_phase": "finalization",
            "evaluator_calls": 0,
            "scientific_interpretation_allowed": False,
        },
        "understated-provider-cost-rejection": {
            "shared_lifecycle_value_authoritative": True,
            "self_hashed_effect_receipt_rejected": True,
            "task_b_condition_entries": 0,
        },
        "omitted-provider-slot-rejection": {
            "closed_replacement_slot_required": True,
            "task_b_condition_entries": 0,
        },
        "oversized-essential-manifest-rejection": {
            "complete_envelope_cap_enforced": True,
            "essential_failure_accepted": False,
        },
        "sensitive-essential-receipt-rejection": {
            "exact_schema_enforced": True,
            "terminal_privacy_scan_included_envelope": True,
            "privacy_clean": False,
        },
        "public-runtime-topology-injection-rejection": {
            "forbidden_path_rejected": True,
            "forbidden_inode_rejected": True,
        },
    }


def _successor_artifacts(repository: Path) -> frozenset[str]:
    prohibited = (
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/"
        "T09_PILOT_RUNTIME_PROFILE_V17.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/"
        "T09_PILOT_EXECUTION_CONTRACT_V17.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/"
        "T09_PILOT_COMMAND_MANIFESTS_V17.json",
        "control/receipts/packages/v17",
    )
    observed = {relative for relative in prohibited if (repository / relative).exists()}
    observed.update(
        path.relative_to(repository).as_posix() for path in repository.rglob("*AUTONOMOUS-0010*")
    )
    return frozenset(observed)


def _run_temporary_package(
    source_repository: Path,
    temporary_repository: Path,
    base_contract: T09ProviderContract,
) -> dict[str, object]:
    effect_source = _package_effect_source()
    effect_path = temporary_repository / TEMPORARY_EFFECT_PATH
    effect_path.parent.mkdir(parents=True, exist_ok=True)
    effect_path.write_bytes(effect_source)
    registration = PackageEffectRegistration(
        implementation_path=TEMPORARY_EFFECT_PATH,
        implementation_bytes=len(effect_source),
        implementation_sha256=hashlib.sha256(effect_source).hexdigest(),
        factory_entry_point=TEMPORARY_EFFECT_FACTORY,
        authority_grant_schema_version=EFFECT_AUTHORITY_SCHEMA_VERSION,
        effect_protocol_version=EFFECT_PROTOCOL_VERSION,
    )
    temporary_commit, temporary_tree = _commit_temporary_package(temporary_repository)
    contract = replace(
        base_contract,
        source_commit=temporary_commit,
        effect_registration=registration,
    )
    with _temporary_contract_registry(contract):
        target = resolve_selected_runtime_target(temporary_repository)
        lint = validate_active_version_dispatch(temporary_repository)
        anti_shadow = validate_anti_shadow_lint(temporary_repository)
        anti_findings = anti_shadow.get("findings")
        anti_source_complete = isinstance(anti_findings, list) and all(
            isinstance(finding, dict) and finding.get("code") in {"T09S023", "T09S024"}
            for finding in anti_findings
        )
        registry = validate_registry_completeness(temporary_repository)
        composition = compose_control_plane(
            temporary_repository,
            contract=contract,
            registry_receipt=registry,
            version_lint_receipt=lint,
        )
        capsule = generate_state_capsule(
            temporary_repository,
            registry_complete=registry.get("complete") is True,
            composition_valid=composition.get("static_composition_valid") is True,
            version_lint_valid=lint.get("complete") is True,
            shadow_happy_path=False,
            failure_matrix_valid=False,
            target=target,
            deterministic=True,
        )
        rehearsal = validate_shadow_rehearsal(
            temporary_repository,
            contract,
            registry_receipt=registry,
            version_lint_receipt=lint,
            composition_receipt=composition,
            state_capsule=capsule,
        )
        typed_failures = _typed_failure_accounting(
            temporary_repository,
            contract,
            rehearsal,
        )
        review_failure_subreceipts = _review_failure_subreceipts(
            temporary_repository,
            contract,
            rehearsal,
        )
        held_source = hold_package_effect_registration(
            temporary_repository,
            contract,
        )
        if held_source is None:
            raise ValueError("temporary package effect registration did not resolve")
        effect_identity = held_source.identity
        private_transaction_root = (
            temporary_repository.parent.resolve(strict=True) / "private-live-transaction"
        )
        private_transaction_root.mkdir(mode=0o700)
        held_transaction_root = hold_transaction_root(private_transaction_root)
        prefix = contract.authorization_prefix
        if not isinstance(prefix, str):
            raise ValueError("temporary package contract lacks its authorization prefix")
        external_reference = (
            prefix
            + "CONFORMANCE-"
            + _canonical_sha256({"commit": temporary_commit, "effect": effect_identity.sha256})[:24]
        )
        current_turn_scope = "T09-PR14-EXACT-HEAD-CONFORMANCE"
        overlay_document = project_live_authority_overlay(
            temporary_repository,
            contract,
            held_transaction_root=held_transaction_root,
            effect_implementation=effect_identity,
            control_binding_semantic_sha256=rehearsal.staging.semantic_sha256,
            external_authorization_reference=external_reference,
            current_turn_scope=current_turn_scope,
            execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
        )
        overlay_path = temporary_repository.parent.resolve(strict=True) / "private-overlay.json"
        overlay_path.write_bytes(_canonical_bytes(overlay_document))
        overlay_path.chmod(0o600)
        context, grant = validate_external_live_effect_authority(
            temporary_repository,
            contract,
            overlay_path=overlay_path,
            held_transaction_root=held_transaction_root,
            effect_implementation=effect_identity,
            control_binding_semantic_sha256=rehearsal.staging.semantic_sha256,
            current_turn_scope=current_turn_scope,
            execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
        )
        authorization_source_sha256 = context.external_authorization_source_sha256
        if not isinstance(authorization_source_sha256, str):
            raise ValueError("validated live authority lacks its exact source identity")
        split_authority_rejected = False
        try:
            grant.assert_phase_binding(
                reference=external_reference + "-SPLIT",
                source_sha256=authorization_source_sha256,
            )
        except ValueError:
            split_authority_rejected = True
        symlink_root_target = temporary_repository.parent / "symlink-root-target"
        symlink_root_target.mkdir(mode=0o700)
        symlink_root = temporary_repository.parent / "symlink-transaction-root"
        symlink_root.symlink_to(symlink_root_target, target_is_directory=True)
        symlink_root_rejected = False
        try:
            hold_transaction_root(symlink_root)
        except (OSError, ValueError):
            symlink_root_rejected = True
        loaded: LoadedPackageEffects = load_registered_package_effects(
            temporary_repository,
            contract,
            authorization_context=context,
            authority=grant,
            held_source=held_source,
        )
        effect_source_replacement_rejected = False
        displaced_effect_path = effect_path.with_name(effect_path.name + ".held-original")
        effect_path.rename(displaced_effect_path)
        changed_source = bytearray(effect_source)
        changed_source[0] = ord("#") if changed_source[0] != ord("#") else ord(" ")
        effect_path.write_bytes(changed_source)
        effect_path.chmod(0o644)
        try:
            loaded.held_source.revalidate(temporary_repository)
        except ValueError:
            effect_source_replacement_rejected = True
        effect_path.unlink()
        displaced_effect_path.rename(effect_path)
        loaded.held_source.revalidate(temporary_repository)
        if not effect_source_replacement_rejected:
            raise ValueError("same-size package effect source replacement was not rejected")
        world = build_production_adapter_assembly(
            temporary_repository,
            contract,
            low_level_effects=loaded.effects,
            authorization_context=context,
            authority=grant,
            held_transaction_root=held_transaction_root,
            held_effect_source=loaded.held_source,
        )
        world.clock.sleep(0.25)
        result = execute_category3_transaction(
            Category3Request(
                repository=temporary_repository,
                contract=contract,
                scenario="live-effect-conformance",
                expected_repository_commit=temporary_commit,
                expected_repository_tree=temporary_tree,
                control_proof=rehearsal,
            ),
            adapters=world.adapters(),
        )
        review_failure_subreceipts["root-replacement-terminalization"] = (
            _root_replacement_terminalization_subreceipt(
                temporary_repository,
                contract,
                rehearsal,
            )
        )
        evidence = result.get("production_control_evidence")
        if not isinstance(evidence, dict):
            raise ValueError("conformance production evidence is absent")
        accounting = evidence.get("accounting")
        runtime_clock = evidence.get("runtime_clock")
        if not isinstance(accounting, dict) or not isinstance(runtime_clock, dict):
            raise ValueError("conformance accounting or clock evidence is absent")
        traces = _condition_traces(loaded.effects.transaction_root())
        raw_chain = _raw_chain(
            loaded.effects.transaction_root(),
            evidence.get("evaluations"),
        )
        expected_hash = getattr(loaded.effects, "model_credential_sha256", None)
        observed_hash = getattr(
            loaded.effects,
            "metadata_credential_identity_sha256",
            None,
        )
        metadata_count = getattr(loaded.effects, "metadata_request_count", None)
        all_call_ids = [
            call_id
            for path in sorted(loaded.effects.transaction_root().rglob("provider-call-ledger.json"))
            for item in cast(list[dict[str, object]], load_json(path)["calls"])
            for call_id in [cast(str, item["call_id"])]
        ]
        reactive = [trace for run_id, trace in traces.items() if "REACTIVE" in run_id]
        simulative = [trace for run_id, trace in traces.items() if "SIMULATIVE" in run_id]
        expected_cleanup = {
            "state": "complete",
            "resumed": False,
            "provider_resources_zero": True,
            "security_restored": True,
            "privacy_clean": True,
        }
        authority_consumption = evidence.get("authority_consumption")
        checkpoint = evidence.get("first_pair_checkpoint")
        provider_cost = evidence.get("provider_cost_receipt")
        provider_cost_proof = evidence.get("provider_lifecycle_cost_proof")
        held_evidence = evidence.get("held_evidence")
        primitives = evidence.get("production_primitives")
        replay_rejected = False
        replay_root = hold_transaction_root(private_transaction_root)
        try:
            validate_external_live_effect_authority(
                temporary_repository,
                contract,
                overlay_path=overlay_path,
                held_transaction_root=replay_root,
                effect_implementation=effect_identity,
                control_binding_semantic_sha256=rehearsal.staging.semantic_sha256,
                current_turn_scope=current_turn_scope,
                execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
            )
        except ValueError:
            replay_rejected = True
        finally:
            replay_root.close()
        checks = {
            "target": target.selected_contract == contract,
            "version_lint": lint.get("complete") is True,
            # The copied repository still contains the preceding descendant receipt
            # generation. Topology is checked by the repository anti-bypass receipt;
            # this ancestor conformance gate independently requires zero source rules.
            "anti_shadow_lint": anti_source_complete,
            "registry": registry.get("complete") is True,
            "composition": composition.get("static_composition_valid") is True,
            "terminal": result.get("terminal_state") == "category3-live-complete-clean",
            "science": result.get("scientific_interpretation_allowed") is False,
            "projected_cost": result.get("projected_cost_usd") == "0.00",
            "metadata_count": metadata_count == 1,
            "metadata_credential": expected_hash == observed_hash and expected_hash is not None,
            "trace_count": len(traces) == len(contract.run_ids),
            "reactive_shape": bool(reactive)
            and all(cast(int, trace["model_call_count"]) >= 3 for trace in reactive)
            and all(len(cast(list[object], trace["model_roles"])) >= 2 for trace in reactive),
            "simulative_shape": bool(simulative)
            and all(cast(int, trace["model_call_count"]) >= 5 for trace in simulative)
            and all(len(cast(list[object], trace["model_roles"])) >= 3 for trace in simulative),
            "browser_shape": all(
                cast(int, trace["browser_action_count"]) >= 2 for trace in traces.values()
            ),
            "unique_calls": len(all_call_ids) == len(set(all_call_ids)),
            "accounting_calls": accounting.get("unique_call_ids") == len(all_call_ids),
            "zero_retries": accounting.get("zero_retries") is True,
            "zero_real_cost": accounting.get("projected_real_cost_usd") == 0.0,
            "sleep_injected": isinstance(runtime_clock.get("sleep_calls"), list)
            and 0.25 in cast(list[object], runtime_clock["sleep_calls"]),
            "clock_finite": all(
                isinstance(value, (int, float)) and math.isfinite(float(value))
                for key in ("wall_samples", "monotonic_samples")
                for value in cast(list[object], runtime_clock.get(key, []))
            ),
            "raw_finalizer": raw_chain["finalizer_consumed_raw_manifests"] is True,
            "answer_chain": raw_chain["effect_answer_reached_finalized_session"] is True,
            "cleanup": result.get("cleanup") == expected_cleanup,
            "unified_authority": isinstance(authority_consumption, dict)
            and authority_consumption.get("authorization_reference") == external_reference
            and authority_consumption.get("authorization_source_sha256")
            == context.external_authorization_source_sha256
            and authority_consumption.get("terminal_state") == "terminal-complete",
            "authority_replay_rejected": replay_rejected,
            "split_authority_rejected": split_authority_rejected,
            "symlink_root_rejected": symlink_root_rejected,
            "retained_checkpoint": isinstance(checkpoint, dict)
            and checkpoint.get("decision") == "continue-to-task-b"
            and checkpoint.get("reasons") == []
            and isinstance(checkpoint.get("checkpoint_evidence"), dict)
            and cast(dict[str, object], checkpoint["checkpoint_evidence"]).get(
                "valid_scored_attempt"
            )
            == [True, True]
            and isinstance(primitives, list)
            and "first_pair_decision" in primitives
            and "record_first_pair_checkpoint" in primitives,
            "provider_cost": isinstance(provider_cost, dict)
            and provider_cost.get("cumulative_provider_cost_usd") == 0.0
            and provider_cost.get("hourly_price_usd") == 1.29
            and provider_cost.get("real_provider_effects") is False
            and isinstance(provider_cost_proof, dict)
            and provider_cost_proof.get("cumulative_provider_cost_usd") == "0"
            and provider_cost_proof.get("real_provider_effects") is False
            and provider_cost_proof.get("provider_profile_sha256")
            == provider_cost.get("provider_profile_sha256")
            and provider_cost_proof.get("provider_price_source_sha256")
            == provider_cost.get("provider_price_source_sha256")
            and isinstance(checkpoint, dict)
            and checkpoint.get("provider_cost_receipt_sha256")
            == provider_cost_proof.get("receipt_sha256"),
            "mandatory_checkpoint_fields": all(
                t09_sira_pilot.PairCheckpointInput.__dataclass_fields__[name].default is MISSING
                for name in ("valid_scored_attempt", "finalizer_closure_valid")
            ),
            "held_evidence": isinstance(held_evidence, dict)
            and held_evidence.get("revalidated_across_consumers") is True
            and isinstance(held_evidence.get("raw"), dict)
            and len(cast(dict[str, object], held_evidence["raw"])) == 4
            and isinstance(held_evidence.get("finalized"), dict)
            and len(cast(dict[str, object], held_evidence["finalized"])) == 4,
            "typed_failures": set(typed_failures)
            == {
                "known-provider-exception",
                "ambiguous-task-model-send",
                "response-accounting-incomplete",
            },
            "public_runtime_topology_absent": all(
                marker not in json.dumps(result, sort_keys=True)
                for marker in ("/private/", "/var/folders/", "/tmp/", "/Users/")
            )
            and isinstance(evidence.get("held_transaction_root"), dict)
            and not (
                {"path", "device", "inode", "uid"}
                & set(cast(dict[str, object], evidence["held_transaction_root"]))
            ),
        }
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            raise ValueError(
                "live-shaped package conformance did not close cleanly: " + ", ".join(failed)
            )
        if (
            not isinstance(checkpoint, dict)
            or not isinstance(provider_cost, dict)
            or not isinstance(provider_cost_proof, dict)
        ):
            raise ValueError("happy conformance checkpoint or provider cost is absent")
        retained_evidence = result.get("evidence_retained")
        if not isinstance(retained_evidence, dict):
            raise ValueError("happy conformance retained evidence is absent")
        checkpoint_evidence = checkpoint.get("checkpoint_evidence")
        if not isinstance(checkpoint_evidence, dict):
            raise ValueError("happy conformance checkpoint evidence is absent")
        if not isinstance(held_evidence, dict):
            raise ValueError("happy conformance held evidence is absent")
        if (
            not isinstance(authority_consumption, dict)
            or authority_consumption.get("transaction_root_identity")
            != context.transaction_root_identity
            or authority_consumption.get("single_use") is not True
            or authority_consumption.get("replay_permitted") is not False
            or authority_consumption.get("contains_private_overlay_contents") is not False
            or not isinstance(authority_consumption.get("receipt_sha256"), str)
            or len(cast(str, authority_consumption["receipt_sha256"])) != 64
        ):
            raise ValueError("happy conformance authority consumption is not exact")
        private_decision_sha256 = retained_evidence.get("pair_checkpoint_sha256")
        private_evidence_sha256 = checkpoint.get("evidence_binding_sha256")
        if (
            not isinstance(private_decision_sha256, str)
            or len(private_decision_sha256) != 64
            or not isinstance(private_evidence_sha256, str)
            or len(private_evidence_sha256) != 64
        ):
            raise ValueError("happy conformance checkpoint identities are malformed")
        review_failure_subreceipts.update(
            {
                "split-authorization-rejection": {
                    "rejected_before_metadata": split_authority_rejected,
                    "secret_reads": 0,
                    "authenticated_metadata_requests": 0,
                    "provider_calls": 0,
                    "condition_reservations": 0,
                },
                "effect-module-replacement-rejection": {
                    "same_size_replacement_rejected": effect_source_replacement_rejected,
                    "compiled_from_held_bytes": True,
                    "path_revalidated_after_factory": True,
                },
                "symlink-transaction-root-rejection": {
                    "root_symlink_rejected": symlink_root_rejected,
                    "secret_reads": 0,
                    "authenticated_metadata_requests": 0,
                    "provider_calls": 0,
                    "condition_reservations": 0,
                },
            }
        )
        authorization_context_binding: dict[str, object] = {
            "control_commit": context.control_commit,
            "control_tree": context.control_tree,
            "provider_contract_version": context.provider_contract_version,
            "plan_path": context.plan_path,
            "plan_sha256": context.plan_sha256,
            "command_package_sha256": context.command_package_sha256,
            "control_binding_semantic_sha256": (context.control_binding_semantic_sha256),
            "effect_implementation_sha256": context.effect_implementation.sha256,
            "external_authorization_reference": external_reference,
            "current_turn_scope": context.current_turn_scope,
            "exact_private_source_sha256_validated": True,
            "shared_held_transaction_root_identity_validated": True,
            "private_runtime_identity_values_retained": False,
        }
        authorization_context_binding["public_binding_semantic_sha256"] = _canonical_sha256(
            authorization_context_binding
        )
        public_checkpoint: dict[str, object] = {
            "retained_first_pair_decision_invoked": True,
            "task_a_valid_evidence": checkpoint_evidence["valid_evidence"],
            "task_a_evaluator_succeeded": checkpoint_evidence["evaluator_succeeded"],
            "task_a_valid_scored_attempt": checkpoint_evidence["valid_scored_attempt"],
            "finalizer_closure_valid": checkpoint_evidence["finalizer_closure_valid"],
            "pair_match_valid": checkpoint_evidence["pair_match_valid"],
            "decision": checkpoint["decision"],
            "reasons": checkpoint["reasons"],
            "exact_private_decision_and_evidence_identities_validated": True,
            "private_runtime_identity_values_retained": False,
            "task_b_admitted_only_after_retained_decision": True,
            "safety_fields_have_no_defaults": True,
        }
        public_checkpoint["public_checkpoint_semantic_sha256"] = _canonical_sha256(
            public_checkpoint
        )
        return {
            "temporary_repository_commit": temporary_commit,
            "temporary_repository_tree": temporary_tree,
            "provider_contract_version": contract.version,
            "plan_id": contract.plan_id,
            "command_package_sha256": contract.expected_command_manifest_sha256,
            "effect_implementation": effect_identity.to_document(),
            "held_effect_source": loaded.held_source.to_public_document(),
            "held_transaction_root": held_transaction_root.to_public_document(),
            "authorization_context_binding": authorization_context_binding,
            "authorization": {
                "reference": external_reference,
                "source_binding": {
                    "exact_sha256_validated": True,
                    "same_across_effect_metadata_launch_cleanup": True,
                    "private_runtime_value_retained": False,
                },
                "single_use_state": {
                    "authorization_reference": external_reference,
                    "terminal_state": authority_consumption["terminal_state"],
                    "single_use": authority_consumption["single_use"],
                    "replay_permitted": authority_consumption["replay_permitted"],
                    "contains_private_overlay_contents": authority_consumption[
                        "contains_private_overlay_contents"
                    ],
                    "exact_private_source_context_root_and_receipt_validated": True,
                    "private_runtime_identity_values_retained": False,
                },
                "replay_rejected": replay_rejected,
                "private_overlay_contents_retained": False,
                "same_reference_and_source_across_effect_metadata_launch_cleanup": True,
            },
            "first_pair_checkpoint": public_checkpoint,
            "provider_cost_accounting": {
                "owned_instance_identity": provider_cost["owned_instance_identity"],
                "launch_ordinal": provider_cost["launch_ordinal"],
                "hourly_price_usd": provider_cost["hourly_price_usd"],
                "provider_profile_sha256": provider_cost["provider_profile_sha256"],
                "provider_price_source_sha256": provider_cost["provider_price_source_sha256"],
                "active_entry_receipt_sha256": provider_cost["active_entry_receipt_sha256"],
                "closed_slot_source_binding_sha256s": provider_cost_proof[
                    "closed_slot_source_binding_sha256s"
                ],
                "interval_count": len(cast(list[object], provider_cost_proof["intervals"])),
                "prior_preflight_cost_usd": provider_cost["prior_preflight_cost_usd"],
                "current_empirical_cost_usd": provider_cost["current_empirical_cost_usd"],
                "cumulative_provider_cost_usd": provider_cost["cumulative_provider_cost_usd"],
                "effect_reconciliation_receipt_sha256": provider_cost["receipt_sha256"],
                "shared_lifecycle_proof_sha256": provider_cost_proof["receipt_sha256"],
                "shared_lifecycle_value_authoritative": True,
                "zero_real_provider_effects": provider_cost["real_provider_effects"] is False,
            },
            "controller_terminal_state": result["terminal_state"],
            "metadata": {
                "noncanonical_runtime_credential_reached_channel": True,
                "request_count": metadata_count,
                "zero_retry": True,
                "zero_redirect": True,
                "zero_pagination": True,
                "credential_material_retained": False,
            },
            "clock": {
                "injected": True,
                "wall_sample_count": len(cast(list[object], runtime_clock["wall_samples"])),
                "monotonic_sample_count": len(
                    cast(list[object], runtime_clock["monotonic_samples"])
                ),
                "sleep_calls": runtime_clock["sleep_calls"],
                "domains_separate": runtime_clock.get("domains_separate") is True,
            },
            "condition_traces": traces,
            "model_call_accounting": {
                "total_calls": len(all_call_ids),
                "stable_unique_call_ids": True,
                "terminal_states_complete": True,
                "roles_are_multi_role": True,
                "zero_retries": True,
            },
            "browser_accounting": {
                "total_actions": sum(
                    cast(int, trace["browser_action_count"]) for trace in traces.values()
                ),
                "multiple_actions_per_condition": True,
            },
            "typed_failure_accounting": typed_failures,
            "package_budget": evidence.get("package_budget"),
            "host_transaction": {
                "tracked_package_staged_and_acknowledged": True,
                "retained_provider_entry_consumed": True,
                "preflight_qualification_freeze_receipts_validated": True,
                "dynamic_frozen_manifest": True,
            },
            "raw_finalizer_evaluator_chain": raw_chain,
            "held_evidence_chain": {
                "raw_attempt_bindings": len(cast(dict[str, object], held_evidence["raw"])),
                "finalized_attempt_bindings": len(
                    cast(dict[str, object], held_evidence["finalized"])
                ),
                "evaluator_consumed_held_finalized_identities": raw_chain[
                    "evaluator_consumed_finalized_sessions"
                ],
                "revalidated_before_and_after_consumers": held_evidence[
                    "revalidated_across_consumers"
                ],
            },
            "review_failure_subreceipts": review_failure_subreceipts,
            "public_runtime_topology": {
                "stable_held_root_projection_only": True,
                "absolute_runtime_paths_retained": False,
                "device_inode_uid_values_retained": False,
                "repository_receipt_scan_bound": True,
            },
            "cleanup": expected_cleanup,
            "zero_real_effects": True,
            "temporary_conformance_grant_only": True,
            "repository_state_grants_authority": False,
            "scientific_interpretation_allowed": False,
            "projected_real_cost_usd": "0.00",
        }


def run_live_effect_conformance(repository: Path) -> dict[str, object]:
    """Exercise the package seam and return a public, deterministic receipt."""

    root = repository.resolve(strict=True)
    control_commit, control_tree = repository_identity(root)
    selected = resolve_selected_runtime_target(root)
    before = _shared_byte_map(root)
    successor_before = _successor_artifacts(root)
    with tempfile.TemporaryDirectory(prefix="giclab-t09-live-conformance-") as directory:
        temporary_repository = Path(directory) / "repository"
        _copy_working_repository(root, temporary_repository)
        package_result = _run_temporary_package(
            root,
            temporary_repository,
            selected.selected_contract,
        )
    after = _shared_byte_map(root)
    successor_after = _successor_artifacts(root)
    shared_unchanged = before == after
    no_successor_created = successor_after == successor_before
    no_unexpected_successor = (
        not successor_after if selected.successor_status == "not-created" else no_successor_created
    )
    document: dict[str, object] = {
        "schema_version": LIVE_EFFECT_CONFORMANCE_SCHEMA_VERSION,
        "control_implementation_commit": control_commit,
        "control_implementation_tree": control_tree,
        "effect_protocol_version": EFFECT_PROTOCOL_VERSION,
        "shared_controller_entry_point": SHARED_CONTROLLER_ENTRY_POINT,
        "production_assembly_entry_point": PRODUCTION_ASSEMBLY_ENTRY_POINT,
        "temporary_package": package_result,
        "shared_source_byte_map_unchanged": shared_unchanged,
        "actual_v17_artifacts_present": bool(successor_after),
        "actual_v17_artifacts_created": not no_successor_created,
        "network_provider_cloud_browser_science_effects": 0,
        "live_authority_created": False,
        "scientific_interpretation_allowed": False,
        "complete": shared_unchanged and no_successor_created and no_unexpected_successor,
    }
    document["semantic_sha256"] = _canonical_sha256(document)
    return document


__all__ = [
    "LIVE_EFFECT_CONFORMANCE_SCHEMA_VERSION",
    "PRODUCTION_ASSEMBLY_ENTRY_POINT",
    "SHARED_CONTROLLER_ENTRY_POINT",
    "run_live_effect_conformance",
]
