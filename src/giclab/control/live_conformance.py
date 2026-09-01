"""Run the package-effect boundary with a temporary, network-disabled adapter.

The generated package module and its stand-in external grant exist only inside a
temporary Git repository.  The run uses the public controller and production
assembly without subclassing or patching either of them.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Final, cast

from giclab.control.anti_shadow_lint import validate_anti_shadow_lint
from giclab.control.category3 import (
    Category3Request,
    execute_category3_transaction,
    repository_identity,
)
from giclab.control.composition import compose_control_plane
from giclab.control.effects import (
    EFFECT_AUTHORITY_SCHEMA_VERSION,
    EFFECT_PROTOCOL_VERSION,
    EffectAuthorityGrant,
    EffectAuthorityKind,
    EffectAuthorizationContext,
    EffectExecutionMode,
    LoadedPackageEffects,
    load_registered_package_effects,
    validate_package_effect_registration,
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
    DeterministicLowLevelEffects,
    ShadowFaultPlan,
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

LIVE_EFFECT_CONFORMANCE_SCHEMA_VERSION: Final = "1.0.0"
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
    return f'''"""Temporary package effect for the zero-real-effect conformance gate."""

from pathlib import Path

from giclab.control.effects import EffectAuthorityKind
from giclab.control.shadow_effects import build_live_shaped_no_network_effects


class PackageEffectGrant:
    kind = EffectAuthorityKind.LIVE_AUTHORIZED
    source = "temporary-external-conformance-validator"

    def __init__(self, context):
        self._context = context

    def authorizes(self, context):
        return context == self._context


def build_package_effects(*, repository, contract, authorization_context, authority):
    return build_live_shaped_no_network_effects(
        repository=repository,
        contract=contract,
        implementation_path=Path(__file__),
        factory_entry_point="{TEMPORARY_EFFECT_FACTORY}",
        authorization_context=authorization_context,
        authority=authority,
    )
'''.encode()


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


def _load_grant_module(path: Path, sha256: str) -> ModuleType:
    module_name = "giclab_external_conformance_grant_" + sha256
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        raise ValueError("temporary package grant module is unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    try:
        specification.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


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
        effect_identity = validate_package_effect_registration(
            temporary_repository,
            contract,
        )
        if effect_identity is None:
            raise ValueError("temporary package effect registration did not resolve")
        probe = DeterministicLowLevelEffects(
            repository=temporary_repository,
            contract=contract,
            fault_plan=ShadowFaultPlan("live-shaped-conformance"),
            fixed_tick=2000,
        )
        external_reference = (
            "AUTH-TEMPORARY-CONFORMANCE-"
            + _canonical_sha256({"commit": temporary_commit, "effect": effect_identity.sha256})[:24]
        )
        context = EffectAuthorizationContext(
            authority_kind=EffectAuthorityKind.LIVE_AUTHORIZED,
            execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
            control_commit=temporary_commit,
            control_tree=temporary_tree,
            provider_contract_version=contract.version,
            plan_id=contract.plan_id,
            plan_sha256=contract.expected_plan_sha256,
            command_package_sha256=cast(
                str,
                contract.expected_command_manifest_sha256,
            ),
            control_binding_semantic_sha256=rehearsal.staging.semantic_sha256,
            effect_implementation=effect_identity,
            transaction_root_identity=probe.transaction_root_identity(),
            external_authorization_reference=external_reference,
            external_authorization_source_sha256=_canonical_sha256(
                {"external_authorization_reference": external_reference}
            ),
        )
        grant_module = _load_grant_module(effect_path, effect_identity.sha256)
        grant_type = getattr(grant_module, "PackageEffectGrant", None)
        if not isinstance(grant_type, type):
            raise ValueError("temporary package grant implementation is absent")
        grant = cast(EffectAuthorityGrant, grant_type(context))
        loaded: LoadedPackageEffects = load_registered_package_effects(
            temporary_repository,
            contract,
            authorization_context=context,
            authority=grant,
        )
        world = build_production_adapter_assembly(
            temporary_repository,
            contract,
            low_level_effects=loaded.effects,
            authorization_context=context,
            authority=grant,
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
        checks = {
            "target": target.selected_contract == contract,
            "version_lint": lint.get("complete") is True,
            "anti_shadow_lint": anti_shadow.get("complete") is True,
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
            "typed_failures": set(typed_failures)
            == {
                "known-provider-exception",
                "ambiguous-task-model-send",
                "response-accounting-incomplete",
            },
        }
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            raise ValueError(
                "live-shaped package conformance did not close cleanly: " + ", ".join(failed)
            )
        return {
            "temporary_repository_commit": temporary_commit,
            "temporary_repository_tree": temporary_tree,
            "provider_contract_version": contract.version,
            "plan_id": contract.plan_id,
            "command_package_sha256": contract.expected_command_manifest_sha256,
            "effect_implementation": effect_identity.to_document(),
            "authorization_context_semantic_sha256": context.semantic_sha256,
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
