"""Offline validation for GIC Lab schemas, registries, provenance, and hygiene."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from giclab.harness.policy import ExecutionDisallowed, load_project_execution_state
from giclab.harness.task_source import (
    dataset_slice_task_source,
    open_query_task_source_matches,
)
from giclab.plans import PlanContractError, discover_plan_paths, load_plan_header
from giclab.registry import (
    DuplicateKeyError,
    discover_repo_root,
    load_json,
    load_yaml,
    resolve_repo_path,
)
from giclab.sitegen import build_site_data

ROOT = discover_repo_root()
T09_DOWNSTREAM_FINALIZER_HISTORY_RELATIVE = Path(
    "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
    "T09_V8_DOWNSTREAM_FINALIZER_SOURCE_HISTORY.json"
)
T09_DOWNSTREAM_FINALIZER_HISTORY_SHA256 = (
    "a40506c022d8e16669bf1a0b4c87ff91205677be4e446d00b7f8debef838445c"
)
SCHEMA_FILES = (
    "schemas/experiment.schema.json",
    "schemas/artifact.schema.json",
    "schemas/transition.schema.json",
    "schemas/manifest.schema.json",
    "schemas/compute.schema.json",
    "schemas/run-plan.schema.json",
    "schemas/run-profile.schema.json",
    "schemas/pricing.schema.json",
    "schemas/harness-event.schema.json",
    "schemas/cloud-run.schema.json",
    "schemas/container-materialization-plan.schema.json",
    "schemas/container-attempt.schema.json",
    "schemas/container-image-provenance.schema.json",
    "schemas/container-platform-decision.schema.json",
    "schemas/docker-storage-qualification-plan.schema.json",
    "schemas/docker-storage-placement-evidence.schema.json",
    "schemas/sealed-artifact-copy.schema.json",
    "schemas/attempt-close-evidence.schema.json",
    "schemas/runtime-candidate-decision.schema.json",
    "schemas/runtime-rollback-evidence.schema.json",
    "schemas/t07-lambda-inventory.schema.json",
    "schemas/t07-lambda-inventory-v2.schema.json",
    "schemas/t07-lambda-request-ledger.schema.json",
    "schemas/t07-lambda-host-qualification.schema.json",
    "schemas/t07-lambda-host-qualification-incident.schema.json",
    "schemas/t08-sira-smoke-adjudication.schema.json",
    "schemas/t08-sira-smoke-pair-diff.schema.json",
    "schemas/t09-sira-pilot-score.schema.json",
    "schemas/t09-sira-pilot-evidence.schema.json",
    "schemas/t09-sira-pilot-execution.schema.json",
    "schemas/t09-sira-pilot-v10-execution.schema.json",
    "schemas/t09-sira-pilot-v11-execution.schema.json",
    "schemas/t09-sira-pilot-v12-execution.schema.json",
    "schemas/t09-sira-pilot-v13-execution.schema.json",
    "schemas/t09-sira-pilot-v14-execution.schema.json",
    "schemas/t09-model-metadata-receipt.schema.json",
    "schemas/t09-v13-model-metadata-receipt.schema.json",
    "schemas/t09-v14-model-metadata-receipt.schema.json",
    "schemas/t09-offline-refinalization-receipt.schema.json",
    "schemas/t09-early-cleanup-state.schema.json",
    "schemas/t09-cleanup-export-handoff.schema.json",
    "schemas/t09-v10-plan.schema.json",
    "schemas/t09-v11-plan.schema.json",
    "schemas/t09-v12-plan.schema.json",
    "schemas/t09-v13-plan.schema.json",
    "schemas/t09-v14-plan.schema.json",
    "schemas/terminal-execution-control.schema.json",
)
REQUIRED_PATHS = (
    "AGENTS.md",
    "README.md",
    "docs/PROJECT_CHARTER.md",
    "docs/RESEARCH_QUESTIONS.md",
    "docs/CLAIM_MATRIX.md",
    "docs/FALSIFICATION_NOTES.md",
    "docs/OPEN_QUESTIONS.md",
    "docs/DECISIONS.md",
    "docs/REPRODUCIBILITY.md",
    "docs/COMPUTE_POLICY.md",
    "docs/STORAGE_POLICY.md",
    "docs/SECURITY_AND_SECRETS.md",
    "docs/PLANS.md",
    "docs/PROJECT_STATE.yaml",
    "docs/harness/T09_SIRA_EXPLORATORY_PILOT_PLAN.md",
    "docs/harness/T09_SIRA_PILOT_PREAUTHORIZATION_PACKET.md",
    "docs/harness/T09_SIRA_PILOT_IMPLEMENTATION_LEDGER.md",
    "docs/harness/T09_SIRA_PILOT_EVALUATOR_CONTRACT.md",
    "docs/harness/T09_SIRA_PILOT_DATASET_CONTRACT.md",
    "docs/exec-plans/active",
    "docs/exec-plans/completed",
    "docs/handoffs/INITIAL_CONVERSATION_SUMMARY.md",
    "docs/reading/GIC_HUMAN_READING_TEMPLATE.md",
    "docs/reading/GIC_AGENT_EXTRACTION_DRAFT.md",
    "docs/reading/SOURCE_MANIFEST.md",
    "experiments/registry.yaml",
    "experiments/EXP-0000-template/protocol.yaml",
    "experiments/EXP-0000-template/config.yaml",
    "experiments/EXP-0000-template/results-summary.json",
    "manifests/models.yaml",
    "manifests/datasets.yaml",
    "manifests/sources.yaml",
    "manifests/artifacts.yaml",
    "manifests/compute.yaml",
    "schemas/manifest.schema.json",
    "schemas/compute.schema.json",
    "notebook/_quarto.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/publish-notebook.yml",
)
MANIFEST_REQUIRED_FIELDS = frozenset(
    {
        "id",
        "name",
        "kind",
        "version",
        "revision",
        "commit",
        "sha256",
        "license",
        "provenance",
        "storage_uri",
        "retrieved_at",
        "verification_status",
    }
)
MANIFEST_FILES = (
    "manifests/models.yaml",
    "manifests/datasets.yaml",
    "manifests/sources.yaml",
)
FORBIDDEN_SUFFIXES = frozenset(
    {".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".parquet", ".zip", ".tar"}
)
MAX_TRACKED_SOURCE_BYTES = 5 * 1024 * 1024
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("OpenAI-style token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "assigned API token",
        re.compile(
            r"(?im)^[ \t]*[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET)[ \t]*="
            r"[ \t]*[^\s#][^\r\n]*$"
        ),
    ),
)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
ACTION_PIN = re.compile(r"^[^./][^@\s]*@([0-9a-f]{40})$")


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"a", "link", "script", "img"}:
            return
        for key, value in attrs:
            if value is not None and key in {"href", "src"}:
                self.targets.append(value)


def _format_validation_errors(
    validator: Draft202012Validator,
    instance: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def validate_instance(
    instance: Mapping[str, Any],
    schema_path: Path,
) -> list[str]:
    """Validate a mapping with a repository JSON Schema."""

    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = _format_validation_errors(validator, instance)
    if schema_path.name == "container-attempt.schema.json":
        errors.extend(_validate_container_attempt_semantics(instance))
    if schema_path.name == "t07-lambda-host-qualification.schema.json":
        from giclab.harness.lambda_cloud import (
            validate_host_qualification_evidence_semantics,
        )

        errors.extend(validate_host_qualification_evidence_semantics(instance))
    if schema_path.name == "t07-lambda-host-qualification-incident.schema.json":
        from giclab.harness.lambda_cloud import (
            validate_host_qualification_incident_semantics,
        )

        errors.extend(validate_host_qualification_incident_semantics(instance))
    return errors


def _t09_successor_implementation_binding_map(plan: Mapping[str, Any]) -> dict[str, str]:
    """Project the active successor's reviewed source and schema byte identities."""

    bindings = plan.get("implementation_bindings")
    if not isinstance(bindings, dict):
        return {}
    specifications: tuple[tuple[str, str, str], ...] = (
        ("provider_accounting", "path", "sha256"),
        ("provider_accounting", "regression_path", "regression_sha256"),
        (
            "offline_refinalization",
            "finalizer_projection_path",
            "finalizer_projection_sha256",
        ),
        ("offline_refinalization", "evaluator_driver_path", "evaluator_driver_sha256"),
        ("offline_refinalization", "selector_path", "selector_sha256"),
        ("offline_refinalization", "receipt_schema_path", "receipt_schema_sha256"),
        ("early_cleanup", "implementation_path", "implementation_sha256"),
        ("early_cleanup", "provider_integration_path", "provider_integration_sha256"),
        ("early_cleanup", "schema_path", "schema_sha256"),
        ("owned_container_publication", "reader_path", "reader_sha256"),
        ("owned_container_publication", "regression_path", "regression_sha256"),
        ("execution_plane", "pilot_library_path", "pilot_library_sha256"),
        (
            "execution_plane",
            "campaign_lifecycle_path",
            "campaign_lifecycle_sha256",
        ),
        ("execution_plane", "provider_path", "provider_sha256"),
        (
            "execution_plane",
            "provider_contracts_path",
            "provider_contracts_sha256",
        ),
        ("execution_plane", "remote_runner_path", "remote_runner_sha256"),
        ("execution_plane", "command_generator_path", "command_generator_sha256"),
        ("execution_plane", "runtime_profile_path", "runtime_profile_sha256"),
        ("execution_plane", "execution_contract_path", "execution_contract_sha256"),
        ("execution_plane", "command_manifests_path", "command_manifests_sha256"),
        ("execution_plane", "runtime_identity_path", "runtime_identity_sha256"),
        ("execution_plane", "execution_schema_path", "execution_schema_sha256"),
    )
    if plan.get("plan_id") in {
        "PLAN-EXP0001-PILOT-V12",
        "PLAN-EXP0001-PILOT-V13",
        "PLAN-EXP0001-PILOT-V14",
    }:
        specifications += (
            ("execution_plane", "runtime_adaptation_path", "runtime_adaptation_sha256"),
        )
    if plan.get("plan_id") in {
        "PLAN-EXP0001-PILOT-V13",
        "PLAN-EXP0001-PILOT-V14",
    }:
        specifications += (
            ("execution_plane", "preflight_path", "preflight_sha256"),
            (
                "execution_plane",
                "local_finalizer_qualification_path",
                "local_finalizer_qualification_sha256",
            ),
        )
    result: dict[str, str] = {}
    for group_name, path_field, hash_field in specifications:
        group = bindings.get(group_name)
        if not isinstance(group, dict):
            continue
        path = group.get(path_field)
        digest = group.get(hash_field)
        if isinstance(path, str) and isinstance(digest, str):
            result[path] = digest
    return result


def _validate_container_attempt_semantics(instance: Mapping[str, Any]) -> list[str]:
    """Enforce cross-field quota relations that standard JSON Schema cannot express."""

    errors: list[str] = []
    resources = instance.get("resource_limits")
    if not isinstance(resources, Mapping):
        return errors
    total = resources.get("output_bytes")
    payload = resources.get("payload_output_bytes")
    logs = resources.get("log_output_bytes")
    evidence = resources.get("evidence_output_bytes")
    if type(total) is int and type(payload) is int and type(logs) is int and type(evidence) is int:
        components = payload + logs + evidence
        if components != total:
            errors.append("resource_limits: output sublimits must sum to output_bytes")
        if payload != total // 2 or logs != total // 8 or evidence != total - payload - logs:
            errors.append("resource_limits: output sublimits do not match the fixed allocation")
        retained = instance.get("retained_output_bytes")
        observed = instance.get("observed_output_bytes")
        exceeded = instance.get("output_limit_exceeded")
        if type(retained) is int and retained > total:
            errors.append("retained_output_bytes: exceeds resource_limits.output_bytes")
        if type(retained) is int and type(observed) is int and observed < retained:
            errors.append("observed_output_bytes: cannot be below retained_output_bytes")
        if type(observed) is int and exceeded is False and observed > total:
            errors.append("observed_output_bytes: exceeds an unflagged output limit")
    success_fields = (
        instance.get("fixture_ready") is True,
        instance.get("wall_timed_out") is False,
        instance.get("output_limit_exceeded") is False,
        instance.get("evidence_complete") is True,
        instance.get("removed") is True,
        instance.get("residual_containers") == [],
        instance.get("residual_networks") == [],
        instance.get("residual_volumes") == [],
        instance.get("sealed") is True,
    )
    probe_succeeded = instance.get("probe_succeeded")
    if type(probe_succeeded) is bool and probe_succeeded != all(success_fields):
        errors.append("probe_succeeded: contradicts the lifecycle and cleanup evidence")
    return errors


def validate_schema_documents(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative in SCHEMA_FILES:
        path = root / relative
        try:
            Draft202012Validator.check_schema(load_json(path))
        except Exception as exc:  # jsonschema exposes several schema error types
            errors.append(f"{relative}: invalid Draft 2020-12 schema: {exc}")
    return errors


def validate_required_paths(root: Path = ROOT) -> list[str]:
    return [
        f"missing required path: {relative}"
        for relative in REQUIRED_PATHS
        if not (root / relative).exists()
    ]


def validate_plan_lifecycle(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    plans_root = root / "docs/exec-plans"
    active_root = plans_root / "active"
    completed_root = plans_root / "completed"
    plan_paths = discover_plan_paths(root)
    active_paths = tuple(path for path in plan_paths if path.parent == active_root)
    if len(active_paths) != 1:
        errors.append(
            "docs/exec-plans/active: exactly one active execution plan is required; "
            f"found {len(active_paths)}"
        )
    for path in plan_paths:
        try:
            plan = load_plan_header(path)
        except (OSError, PlanContractError) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
            continue
        if path.parent == active_root and plan.status == "successful":
            errors.append(f"{path.relative_to(root)}: active plan cannot be successful")
        elif plan.status == "successful" and path.parent != completed_root:
            errors.append(
                f"{path.relative_to(root)}: successful plan must be under "
                "docs/exec-plans/completed/"
            )
        elif path.parent == completed_root and plan.status != "successful":
            errors.append(f"{path.relative_to(root)}: completed plan must be successful")
    return errors


def validate_project_state(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        state = load_yaml(root / "docs/PROJECT_STATE.yaml")
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        return [f"docs/PROJECT_STATE.yaml: {exc}"]
    phase = state.get("phase")
    try:
        phase_number = Decimal(phase) if isinstance(phase, str) else None
    except InvalidOperation:
        phase_number = None
    if phase_number is None or not phase_number.is_finite() or phase_number < 0:
        errors.append("docs/PROJECT_STATE.yaml: phase must be a nonnegative decimal string")

    phase_name = state.get("phase_name")
    if not isinstance(phase_name, str) or not phase_name.strip():
        errors.append("docs/PROJECT_STATE.yaml: phase_name must be a nonempty string")

    allowed_statuses = {
        "in-progress",
        "smoke-failed",
        "review-failed",
        "spec-failed",
        "scout-pending",
        "scout-failed",
        "successful",
        "blocked-user-action",
    }
    phase_status = state.get("phase_status")
    if phase_status not in allowed_statuses:
        errors.append("docs/PROJECT_STATE.yaml: phase_status must be an assembly status")

    authorization_fields = (
        "paid_compute_allowed",
        "prototype_execution_allowed",
        "benchmark_execution_allowed",
        "training_allowed",
        "cloud_mutation_allowed",
    )
    for key in authorization_fields:
        if not isinstance(state.get(key), bool):
            errors.append(f"docs/PROJECT_STATE.yaml: {key} must be a boolean")
    if (
        phase_number is not None
        and phase_number.is_finite()
        and phase_number >= 1
        and "authorized_run_profile" not in state
    ):
        errors.append(
            "docs/PROJECT_STATE.yaml: Phase 1+ requires an explicit authorized_run_profile binding"
        )
    try:
        execution_state = load_project_execution_state(root, schema_root=root)
    except ExecutionDisallowed as exc:
        errors.append(f"docs/PROJECT_STATE.yaml: {exc}")
        execution_state = None
    if (
        execution_state is not None
        and (
            execution_state.prototype_execution_allowed
            or execution_state.benchmark_execution_allowed
            or execution_state.training_allowed
        )
        and execution_state.authorized_run_profile is None
    ):
        errors.append(
            "docs/PROJECT_STATE.yaml: executable workload permission requires an exact "
            "authorized_run_profile binding"
        )
    if phase_number is not None and phase_number.is_finite() and phase_number < 1:
        for key in authorization_fields:
            if state.get(key) is not False:
                errors.append(f"docs/PROJECT_STATE.yaml: {key} must be false before Phase 1")

    autonomous = state.get("t09_autonomous_pilot_checkpoint")
    if isinstance(autonomous, dict):
        ambiguous_usage_fields = {
            "total_tokens",
            "openai_cost_usd",
            "new_total_cost_usd",
            "cumulative_t09_cost_usd",
        }
        present_ambiguous = sorted(ambiguous_usage_fields.intersection(autonomous))
        if present_ambiguous:
            errors.append(
                "docs/PROJECT_STATE.yaml: autonomous T09 lower-bound usage uses ambiguous "
                "exact labels: " + ", ".join(present_ambiguous)
            )
        disposition_path = (
            root / "experiments/EXP-0001-sira-simulative-vs-reactive/"
            "T09_AUTONOMOUS_PILOT_DISPOSITION.json"
        )
        if disposition_path.is_file():
            disposition = load_json(disposition_path)
            usage = disposition.get("usage")
            costs = disposition.get("cost_reconciliation")
            expected = {
                "task_model_call_attempts": (
                    usage.get("task_model_call_attempts") if isinstance(usage, dict) else None
                ),
                "provider_response_receipts": (
                    usage.get("task_model_call_attempts", 0)
                    - usage.get("unreconciled_provider_attempts", 0)
                    if isinstance(usage, dict)
                    and isinstance(usage.get("task_model_call_attempts"), int)
                    and isinstance(usage.get("unreconciled_provider_attempts"), int)
                    else None
                ),
                "observed_reconciled_total_tokens": (
                    usage.get("observed_reconciled_total_tokens")
                    if isinstance(usage, dict)
                    else None
                ),
                "openai_cost_usd_observed_lower_bound": (
                    costs.get("new_openai_cost_usd_observed_lower_bound")
                    if isinstance(costs, dict)
                    else None
                ),
                "openai_cost_usd_reserved_upper_bound": (
                    costs.get("new_openai_cost_usd_reserved_upper_bound")
                    if isinstance(costs, dict)
                    else None
                ),
                "new_total_cost_usd_observed_lower_bound": (
                    costs.get("new_total_cost_usd_observed_lower_bound")
                    if isinstance(costs, dict)
                    else None
                ),
                "new_total_cost_usd_reserved_upper_bound": (
                    costs.get("new_total_cost_usd_reserved_upper_bound")
                    if isinstance(costs, dict)
                    else None
                ),
                "cumulative_t09_cost_usd_observed_lower_bound": (
                    costs.get("cumulative_t09_cost_usd_observed_lower_bound")
                    if isinstance(costs, dict)
                    else None
                ),
                "cumulative_t09_cost_usd_reserved_upper_bound": (
                    costs.get("cumulative_t09_cost_usd_reserved_upper_bound")
                    if isinstance(costs, dict)
                    else None
                ),
            }
            for field, value in expected.items():
                if autonomous.get(field) != value:
                    errors.append(
                        "docs/PROJECT_STATE.yaml: autonomous T09 disposition binding "
                        f"drifted for {field}"
                    )

    plan = state.get("authoritative_plan")
    if not isinstance(plan, str):
        errors.append("docs/PROJECT_STATE.yaml: authoritative_plan must resolve to a file")
        return errors
    try:
        plan_path = resolve_repo_path(root, plan)
    except ValueError as exc:
        errors.append(f"docs/PROJECT_STATE.yaml: authoritative_plan is invalid: {exc}")
        return errors
    if not plan_path.is_file():
        errors.append("docs/PROJECT_STATE.yaml: authoritative_plan must resolve to a file")
        return errors
    try:
        plan_header = load_plan_header(plan_path)
    except (OSError, PlanContractError) as exc:
        errors.append(f"docs/PROJECT_STATE.yaml: authoritative_plan is invalid: {exc}")
        return errors
    if isinstance(phase, str) and plan_header.phase != phase:
        errors.append("docs/PROJECT_STATE.yaml: phase must match authoritative plan heading")
    if plan_header.status != phase_status:
        errors.append("docs/PROJECT_STATE.yaml: phase_status must match authoritative plan")
    expected_plan_root = (
        root / "docs/exec-plans/completed"
        if phase_status == "successful"
        else root / "docs/exec-plans/active"
    )
    if plan_path.parent != expected_plan_root.resolve():
        location = "completed" if phase_status == "successful" else "active"
        errors.append(
            "docs/PROJECT_STATE.yaml: authoritative_plan must be under "
            f"docs/exec-plans/{location}/ for phase_status {phase_status}"
        )
    return errors


def validate_experiment_protocol(protocol: Mapping[str, Any], root: Path = ROOT) -> list[str]:
    errors = validate_instance(protocol, root / "schemas/experiment.schema.json")
    evidence = protocol.get("evidence_status")
    outcome = protocol.get("outcome_status")
    lifecycle = protocol.get("lifecycle_status")
    execution = protocol.get("execution")
    if evidence == "not-evaluated" and outcome != "pending":
        errors.append("not-evaluated evidence requires a pending outcome")
    if (
        lifecycle == "planned"
        and isinstance(execution, dict)
        and execution.get("authorized") is True
    ):
        errors.append("planned experiments cannot already be execution-authorized")
    for relative in protocol.get("source_contracts", []):
        if isinstance(relative, str) and not resolve_repo_path(root, relative).is_file():
            errors.append(f"source contract does not resolve: {relative}")
    paths = protocol.get("paths")
    if isinstance(paths, dict):
        for label, relative in paths.items():
            if isinstance(relative, str) and not resolve_repo_path(root, relative).is_file():
                errors.append(f"{label} path does not resolve: {relative}")
    return errors


def validate_experiment_registry(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    registry_path = root / "experiments/registry.yaml"
    try:
        registry = load_yaml(registry_path)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        return [f"experiments/registry.yaml: {exc}"]
    entries = registry.get("experiments")
    if not isinstance(entries, list):
        return ["experiments/registry.yaml: experiments must be a list"]
    seen: set[str] = set()
    registered_directories: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"registry entry {index} must be a mapping")
            continue
        experiment_id = entry.get("experiment_id")
        if not isinstance(experiment_id, str):
            errors.append(f"registry entry {index} has no experiment_id")
            continue
        if experiment_id == "EXP-0000":
            errors.append("EXP-0000 is a template and must never be registered")
        if experiment_id in seen:
            errors.append(f"duplicate experiment ID: {experiment_id}")
        seen.add(experiment_id)
        protocol_path = entry.get("protocol")
        if not isinstance(protocol_path, str):
            errors.append(f"{experiment_id}: protocol must be a path")
            continue
        protocol_file = resolve_repo_path(root, protocol_path)
        if not protocol_file.is_file():
            errors.append(f"{experiment_id}: protocol not found: {protocol_path}")
            continue
        registered_directories.add(protocol_file.parent.name)
        try:
            protocol = load_yaml(protocol_file)
        except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{protocol_path}: {exc}")
            continue
        if protocol.get("experiment_id") != experiment_id:
            errors.append(f"{experiment_id}: registry/protocol ID mismatch")
        errors.extend(
            f"{experiment_id}: {error}" for error in validate_experiment_protocol(protocol, root)
        )
    experiment_directory = re.compile(r"^EXP-[0-9]{4}(?:-[a-z0-9][a-z0-9-]*)?$")
    actual_directories = {
        path.name
        for path in (root / "experiments").iterdir()
        if path.is_dir()
        and path.name != "EXP-0000-template"
        and experiment_directory.fullmatch(path.name) is not None
    }
    if registered_directories != actual_directories:
        errors.append(
            "experiment directory/registry mismatch: "
            f"registered={sorted(registered_directories)}, actual={sorted(actual_directories)}"
        )
    template = root / "experiments/EXP-0000-template/protocol.yaml"
    try:
        template_protocol = load_yaml(template)
        errors.extend(
            f"template: {error}" for error in validate_experiment_protocol(template_protocol, root)
        )
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"template protocol: {exc}")
    try:
        summary = load_json(root / "experiments/EXP-0000-template/results-summary.json")
        if summary.get("run_status") != "not-run" or summary.get("measurements") != []:
            errors.append("EXP-0000 results must remain explicitly not-run with no measurements")
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"EXP-0000 results: {exc}")
    return errors


def validate_run_profile_readiness(profile: Mapping[str, Any]) -> list[str]:
    """Enforce current authorization readiness without rewriting v0.1 record syntax."""

    errors: list[str] = []
    execution = profile.get("execution")
    readiness = profile.get("readiness")
    if not isinstance(execution, dict) or not isinstance(readiness, dict):
        return errors
    eligibility = readiness.get("execution_eligibility")
    blockers = readiness.get("unresolved_execution_blockers")
    if eligibility == "eligible-after-authorization" and blockers != []:
        errors.append("execution-eligible profile must have no unresolved blockers")
    if eligibility != "eligible-after-authorization" and (
        not isinstance(blockers, list) or not blockers
    ):
        errors.append("execution-ineligible profile must retain an unresolved blocker")
    if execution.get("authorized") is True and eligibility != "eligible-after-authorization":
        errors.append("authorized profile must be execution-eligible")
    return errors


def validate_experiment_run_profiles(root: Path = ROOT) -> list[str]:
    """Validate registry-declared paired profiles and their bound condition plans."""

    errors: list[str] = []
    registry = load_yaml(root / "experiments/registry.yaml")
    entries = registry.get("experiments", [])
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        experiment_id = entry.get("experiment_id")
        protocol_relative = entry.get("protocol")
        declared_profiles = entry.get("run_profiles", [])
        if not isinstance(experiment_id, str) or not isinstance(protocol_relative, str):
            continue
        if not isinstance(declared_profiles, list):
            errors.append(f"{experiment_id}: run_profiles must be a list")
            continue
        experiment_root = resolve_repo_path(root, protocol_relative).parent.resolve()
        profiles_root = experiment_root / "run-plans"
        referenced_conditions: set[Path] = set()
        declared_profile_paths: set[Path] = set()
        for profile_relative in declared_profiles:
            if not isinstance(profile_relative, str):
                errors.append(f"{experiment_id}: run profile path must be a string")
                continue
            profile_path = resolve_repo_path(root, profile_relative)
            declared_profile_paths.add(profile_path)
            profile_parent = profile_path.parent.resolve()
            historical_profile = profile_parent == (profiles_root / "proposals").resolve()
            if profile_parent != profiles_root and not historical_profile:
                errors.append(f"{experiment_id}: run profile must be inside its run-plans root")
                continue
            if not profile_path.is_file():
                errors.append(f"{experiment_id}: missing run profile {profile_relative}")
                continue
            profile = load_yaml(profile_path)
            profile_sha256 = hashlib.sha256(profile_path.read_bytes()).hexdigest()
            label = profile_path.relative_to(root)
            errors.extend(
                f"{label}: {error}"
                for error in validate_instance(profile, root / "schemas/run-profile.schema.json")
            )
            errors.extend(f"{label}: {error}" for error in validate_run_profile_readiness(profile))
            readiness = profile.get("readiness")
            if (
                isinstance(readiness, dict)
                and readiness.get("execution_eligibility")
                == "blocked-pending-later-phase-integration"
            ):
                errors.append(f"{label}: current profile must use a phase-independent blocker")
            profile_name = profile.get("profile")
            if profile.get("experiment_id") != experiment_id:
                errors.append(f"{label}: experiment ID mismatch")
            if not historical_profile and profile_name != profile_path.stem:
                errors.append(f"{label}: profile/name mismatch")
            execution = profile.get("execution")
            if not isinstance(execution, dict):
                errors.append(f"{label}: current repository profile execution is malformed")
            elif execution.get("authorized") is True and not isinstance(
                execution.get("authorization_reference"), str
            ):
                errors.append(f"{label}: authorized profile lacks its current-turn reference")
            condition_relatives = profile.get("condition_plan_paths", [])
            sampling = profile.get("sampling", {})
            profile_model = profile.get("model", {})
            if not isinstance(condition_relatives, list) or not isinstance(sampling, dict):
                continue
            condition_records: dict[Path, Mapping[str, Any]] = {}
            condition_names: list[str] = []
            condition_cost = Decimal(0)
            condition_gpu_hours = Decimal(0)
            condition_model_calls = 0
            condition_tokens = 0
            condition_tool_calls = 0
            condition_wall = 0
            for condition_relative in condition_relatives:
                if not isinstance(condition_relative, str):
                    continue
                condition_path = resolve_repo_path(root, condition_relative)
                if experiment_root not in condition_path.parents:
                    errors.append(f"{label}: condition plan escapes experiment")
                    continue
                if not condition_path.is_file():
                    errors.append(f"{label}: missing condition plan {condition_relative}")
                    continue
                referenced_conditions.add(condition_path)
                condition = load_yaml(condition_path)
                condition_records[condition_path] = condition
                condition_label = condition_path.relative_to(root)
                errors.extend(
                    f"{condition_label}: {error}"
                    for error in validate_instance(condition, root / "schemas/run-plan.schema.json")
                )
                if condition.get("experiment_id") != experiment_id:
                    errors.append(f"{condition_label}: experiment ID mismatch")
                if condition.get("profile") != profile_name:
                    errors.append(f"{condition_label}: profile mismatch")
                if condition.get("profile_plan_id") != profile.get("plan_id"):
                    errors.append(f"{condition_label}: parent profile plan ID mismatch")
                if condition.get("profile_sha256") != profile_sha256:
                    errors.append(f"{condition_label}: parent profile hash mismatch")
                task = condition.get("task")
                pairing = condition.get("pairing")
                if not isinstance(task, dict) or not isinstance(pairing, dict):
                    errors.append(f"{condition_label}: paired plan requires task and pairing")
                condition_execution = condition.get("execution")
                authorization = (
                    condition_execution.get("authorization")
                    if isinstance(condition_execution, dict)
                    else None
                )
                parent_authorization = execution if isinstance(execution, dict) else {}
                if not isinstance(authorization, dict) or authorization.get(
                    "authorized"
                ) is not parent_authorization.get("authorized"):
                    errors.append(f"{condition_label}: child authorization state drifted")
                elif authorization.get("authorized") is True and (
                    authorization.get("authorization_reference")
                    != parent_authorization.get("authorization_reference")
                    or not isinstance(authorization.get("command_sha256"), str)
                ):
                    errors.append(f"{condition_label}: child authorization binding drifted")
                condition_name = condition.get("condition")
                if isinstance(condition_name, str):
                    condition_names.append(condition_name)
                sources = condition.get("sources")
                if isinstance(sources, dict) and isinstance(profile_model, dict):
                    if sources.get("model_revision") != profile_model.get(
                        "proposed_immutable_revision"
                    ):
                        errors.append(f"{condition_label}: model revision/profile mismatch")
                    if isinstance(task, dict) and sources.get("dataset_revision") != task.get(
                        "dataset_revision"
                    ):
                        errors.append(f"{condition_label}: task/source dataset revision mismatch")
                budget = condition.get("budget")
                if isinstance(budget, dict):
                    max_cost = budget.get("max_cost_usd")
                    if isinstance(max_cost, (int, float)):
                        condition_cost += Decimal(str(max_cost))
                    if isinstance(budget.get("max_model_calls"), int):
                        condition_model_calls += budget["max_model_calls"]
                    if isinstance(budget.get("max_model_tokens"), int):
                        condition_tokens += budget["max_model_tokens"]
                    if isinstance(budget.get("max_tool_calls"), int):
                        condition_tool_calls += budget["max_tool_calls"]
                    if isinstance(budget.get("max_wall_seconds"), int):
                        condition_wall += budget["max_wall_seconds"]
                    max_gpu_hours = budget.get("max_gpu_hours")
                    if isinstance(max_gpu_hours, (int, float)):
                        condition_gpu_hours += Decimal(str(max_gpu_hours))
            pair_count = sampling.get("pair_count")
            expected_conditions = sampling.get("conditions", [])
            if isinstance(pair_count, int) and isinstance(expected_conditions, list):
                expected_plan_count = pair_count * len(expected_conditions)
                if len(condition_relatives) != expected_plan_count:
                    errors.append(f"{label}: pair_count requires {expected_plan_count} plans")
                if set(condition_names) != set(expected_conditions):
                    errors.append(f"{label}: condition plans/profile conditions disagree")
                for condition_name in expected_conditions:
                    if condition_names.count(condition_name) != pair_count:
                        errors.append(
                            f"{label}: {condition_name} must have exactly {pair_count} plans"
                        )
            counterbalancing = sampling.get("counterbalancing", [])
            bound_paths: set[Path] = set()
            pair_ids: set[str] = set()
            task_ids: set[str] = set()
            if isinstance(counterbalancing, list):
                if isinstance(pair_count, int) and len(counterbalancing) != pair_count:
                    errors.append(f"{label}: counterbalancing/pair_count mismatch")
                for pair in counterbalancing:
                    if not isinstance(pair, dict):
                        continue
                    pair_id = pair.get("pair_id")
                    task_id = pair.get("task_id")
                    first = pair.get("first")
                    second = pair.get("second")
                    if not isinstance(pair_id, str) or pair_id in pair_ids:
                        errors.append(f"{label}: pair IDs must be unique strings")
                    else:
                        pair_ids.add(pair_id)
                    if not isinstance(task_id, str) or task_id in task_ids:
                        errors.append(f"{label}: task IDs must be unique strings")
                    else:
                        task_ids.add(task_id)
                    if set((first, second)) != set(expected_conditions):
                        errors.append(f"{label}: pair order must contain each condition once")
                    bindings = pair.get("plans", [])
                    bound_records: list[Mapping[str, Any]] = []
                    if not isinstance(bindings, list):
                        continue
                    if {
                        item.get("condition") for item in bindings if isinstance(item, dict)
                    } != set(expected_conditions):
                        errors.append(f"{label}: pair bindings must contain each condition once")
                    for binding in bindings:
                        if not isinstance(binding, dict) or not isinstance(
                            binding.get("path"), str
                        ):
                            continue
                        bound_path = resolve_repo_path(root, binding["path"])
                        bound_paths.add(bound_path)
                        record = condition_records.get(bound_path)
                        if record is None:
                            errors.append(f"{label}: pair binding references an undeclared plan")
                            continue
                        bound_records.append(record)
                        condition_name = binding.get("condition")
                        if record.get("condition") != condition_name:
                            errors.append(f"{label}: pair binding condition mismatch")
                        task = record.get("task")
                        pairing = record.get("pairing")
                        if not isinstance(task, dict) or task.get("task_id") != task_id:
                            errors.append(f"{label}: pair binding task mismatch")
                        expected_order = 1 if condition_name == first else 2
                        if (
                            not isinstance(pairing, dict)
                            or pairing.get("pair_id") != pair_id
                            or pairing.get("order_index") != expected_order
                        ):
                            errors.append(f"{label}: pair identity/order mismatch")
                    if len(bound_records) == 2:
                        left, right = bound_records
                        for key in (
                            "profile_plan_id",
                            "profile_sha256",
                            "task",
                            "seed",
                            "attempt",
                        ):
                            if left.get(key) != right.get(key):
                                errors.append(f"{label}: matched pair drifts on {key}")
                        left_budget = left.get("budget")
                        right_budget = right.get("budget")
                        if (
                            isinstance(left_budget, dict)
                            and isinstance(right_budget, dict)
                            and left_budget != right_budget
                        ):
                            errors.append(f"{label}: matched pair drifts on fixed budget")
                        left_sources = left.get("sources")
                        right_sources = right.get("sources")
                        if isinstance(left_sources, dict) and isinstance(right_sources, dict):
                            for key in (
                                "giclab_commit",
                                "upstream_source_id",
                                "upstream_commit",
                                "protocol_sha256",
                                "config_sha256",
                                "model_revision",
                                "dataset_revision",
                                "environment_sha256",
                            ):
                                if left_sources.get(key) != right_sources.get(key):
                                    errors.append(f"{label}: matched pair source drift on {key}")
                        left_execution = left.get("execution")
                        right_execution = right.get("execution")
                        if isinstance(left_execution, dict) and isinstance(right_execution, dict):
                            for key in ("backend", "workload"):
                                if left_execution.get(key) != right_execution.get(key):
                                    errors.append(f"{label}: matched pair execution drift on {key}")
                            left_auth = left_execution.get("authorization")
                            right_auth = right_execution.get("authorization")
                            if isinstance(left_auth, dict) and isinstance(right_auth, dict):
                                for key in ("authorized", "authorization_reference"):
                                    if left_auth.get(key) != right_auth.get(key):
                                        errors.append(
                                            f"{label}: matched pair authorization drift on {key}"
                                        )
                        task = left.get("task")
                        task_source = pair.get("task_source")
                        if isinstance(task, dict) and isinstance(task_source, str):
                            if task.get("source_kind") == "dataset-slice":
                                dataset_id = task.get("dataset_id")
                                start_idx = task.get("start_idx")
                                end_idx = task.get("end_idx")
                                if not (
                                    isinstance(dataset_id, str)
                                    and isinstance(start_idx, int)
                                    and isinstance(end_idx, int)
                                ):
                                    errors.append(f"{label}: pair task slice identity is invalid")
                                    continue
                                expected_source = dataset_slice_task_source(
                                    dataset_id,
                                    start_idx,
                                    end_idx,
                                )
                                if task_source != expected_source:
                                    errors.append(f"{label}: pair task source/slice mismatch")
                            else:
                                query = task.get("query")
                                if not isinstance(query, str) or not open_query_task_source_matches(
                                    task_source, query
                                ):
                                    errors.append(f"{label}: pair task source/query mismatch")
            if bound_paths != set(condition_records):
                errors.append(f"{label}: pair bindings/condition plan paths are not bijective")
            profile_budget = profile.get("budget")
            if isinstance(profile_budget, dict):
                try:
                    expected_cost = Decimal(str(profile_budget.get("max_cost_usd")))
                except InvalidOperation:
                    expected_cost = Decimal(-1)
                if condition_cost != expected_cost:
                    errors.append(f"{label}: profile/condition cost caps disagree")
                if profile_budget.get("max_model_tokens") != condition_tokens:
                    errors.append(f"{label}: profile/condition token caps disagree")
                if (
                    "max_model_calls" in profile_budget
                    and profile_budget.get("max_model_calls") != condition_model_calls
                ):
                    errors.append(f"{label}: profile/condition model-call caps disagree")
                if profile_budget.get("max_wall_seconds") != condition_wall:
                    errors.append(f"{label}: profile/condition wall caps disagree")
                if (
                    "max_browser_actions" in profile_budget
                    and profile_budget.get("max_browser_actions") != condition_tool_calls
                ):
                    errors.append(f"{label}: profile/condition browser-action caps disagree")
                if "max_accelerator_hours" in profile_budget:
                    try:
                        expected_accelerator_hours = Decimal(
                            str(profile_budget.get("max_accelerator_hours"))
                        )
                    except InvalidOperation:
                        expected_accelerator_hours = Decimal(-1)
                    if condition_gpu_hours != expected_accelerator_hours:
                        errors.append(f"{label}: profile/condition accelerator-hour caps disagree")
                condition_limits = profile_budget.get("condition_limits")
                if isinstance(condition_limits, dict):
                    if set(condition_limits) != set(expected_conditions):
                        errors.append(f"{label}: condition-limit names/profile conditions disagree")
                    planned_model_calls = 0
                    planned_tokens = 0
                    planned_browser_actions = 0
                    planned_wall = 0
                    planned_openai_cost = Decimal(0)
                    planned_accelerator_hours = Decimal(0)
                    for condition_name, raw_limit in condition_limits.items():
                        if not isinstance(condition_name, str) or not isinstance(raw_limit, dict):
                            continue
                        attempts = raw_limit.get("attempts")
                        model_calls = raw_limit.get("max_model_calls_per_attempt")
                        tokens = raw_limit.get("max_model_tokens_per_attempt")
                        browser_actions = raw_limit.get("max_browser_actions_per_attempt")
                        wall = raw_limit.get("max_wall_seconds_per_attempt")
                        openai_cost = raw_limit.get("max_openai_cost_usd_per_attempt")
                        accelerator_hours = raw_limit.get("max_accelerator_hours_per_attempt")
                        if (
                            not all(
                                type(value) is int
                                for value in (attempts, model_calls, tokens, browser_actions, wall)
                            )
                            or not isinstance(openai_cost, (int, float))
                            or not isinstance(accelerator_hours, (int, float))
                        ):
                            continue
                        assert isinstance(attempts, int)
                        assert isinstance(model_calls, int)
                        assert isinstance(tokens, int)
                        assert isinstance(browser_actions, int)
                        assert isinstance(wall, int)
                        if condition_names.count(condition_name) != attempts:
                            errors.append(
                                f"{label}: {condition_name} condition-limit attempts disagree"
                            )
                        planned_model_calls += attempts * model_calls
                        planned_tokens += attempts * tokens
                        planned_browser_actions += attempts * browser_actions
                        planned_wall += attempts * wall
                        planned_openai_cost += attempts * Decimal(str(openai_cost))
                        planned_accelerator_hours += attempts * Decimal(str(accelerator_hours))
                        for condition_record in condition_records.values():
                            if condition_record.get("condition") != condition_name:
                                continue
                            child_budget = condition_record.get("budget")
                            if not isinstance(child_budget, dict):
                                continue
                            expected_child_values = {
                                "max_model_calls": model_calls,
                                "max_model_tokens": tokens,
                                "max_tool_calls": browser_actions,
                                "max_wall_seconds": wall,
                                "max_cost_usd": openai_cost,
                                "max_gpu_hours": accelerator_hours,
                            }
                            for field, expected in expected_child_values.items():
                                observed = child_budget.get(field)
                                if (
                                    not isinstance(observed, (int, float))
                                    or isinstance(observed, bool)
                                    or Decimal(str(observed)) != Decimal(str(expected))
                                ):
                                    errors.append(
                                        f"{label}: {condition_name} {field} disagrees with "
                                        "condition limits"
                                    )
                    aggregate_fields = {
                        "max_model_calls": planned_model_calls,
                        "max_model_tokens": planned_tokens,
                        "max_browser_actions": planned_browser_actions,
                        "max_wall_seconds": planned_wall,
                    }
                    for field, expected in aggregate_fields.items():
                        if profile_budget.get(field) != expected:
                            errors.append(f"{label}: {field} does not sum condition limits")
                    try:
                        profile_openai_cost = Decimal(str(profile_budget.get("max_cost_usd")))
                        profile_accelerator_hours = Decimal(
                            str(profile_budget.get("max_accelerator_hours"))
                        )
                    except InvalidOperation:
                        profile_openai_cost = Decimal(-1)
                        profile_accelerator_hours = Decimal(-1)
                    if planned_openai_cost != profile_openai_cost:
                        errors.append(f"{label}: model spend does not sum condition limits")
                    if planned_accelerator_hours != profile_accelerator_hours:
                        errors.append(f"{label}: accelerator hours do not sum condition limits")
                    try:
                        provider_compute_cost = Decimal(
                            str(profile_budget.get("max_provider_compute_cost_usd"))
                        )
                        total_cost = Decimal(str(profile_budget.get("max_total_cost_usd")))
                    except InvalidOperation:
                        provider_compute_cost = Decimal(-1)
                        total_cost = Decimal(-1)
                    preflight_provider_cost = Decimal(
                        str(profile_budget.get("max_preflight_provider_compute_cost_usd", 0))
                    )
                    if (
                        planned_openai_cost + provider_compute_cost + preflight_provider_cost
                        != total_cost
                    ):
                        errors.append(f"{label}: total spend cap arithmetic disagrees")
                pricing_relative = profile_budget.get("pricing_record")
                if isinstance(pricing_relative, str):
                    pricing_path = resolve_repo_path(root, pricing_relative)
                    if not pricing_path.is_file():
                        errors.append(f"{label}: pricing record does not resolve")
                    else:
                        pricing = load_yaml(pricing_path)
                        errors.extend(
                            f"{pricing_path.relative_to(root)}: {error}"
                            for error in validate_instance(
                                pricing, root / "schemas/pricing.schema.json"
                            )
                        )
                        if isinstance(profile_model, dict) and (
                            pricing.get("provider") != profile_model.get("provider")
                            or pricing.get("model_manifest_id") != profile_model.get("manifest_id")
                            or pricing.get("proposed_revision")
                            != profile_model.get("proposed_immutable_revision")
                        ):
                            errors.append(f"{label}: pricing/model identity mismatch")
        actual_profile_paths = set(profiles_root.glob("*.yaml"))
        declared_current_paths = {
            path for path in declared_profile_paths if path.parent.resolve() == profiles_root
        }
        if actual_profile_paths != declared_current_paths:
            errors.append(f"{experiment_id}: registry/profile declaration mismatch")
        actual_conditions = set((profiles_root / "conditions").glob("*.yaml"))
        proposal_conditions: set[Path] = set()
        proposal_paths = sorted(
            (profiles_root / "proposals").glob("T09_PILOT_RUNTIME_PROFILE_V*.yaml")
        )
        for proposal_path in proposal_paths:
            proposal = load_yaml(proposal_path)
            raw_proposal_conditions = proposal.get("condition_plan_paths")
            if isinstance(raw_proposal_conditions, list):
                for relative in raw_proposal_conditions:
                    if isinstance(relative, str):
                        proposal_conditions.add(resolve_repo_path(root, relative))
        if actual_conditions != referenced_conditions | proposal_conditions:
            errors.append(f"{experiment_id}: condition-plan reference mismatch")
    return errors


def _load_t09_downstream_finalizer_history(root: Path) -> dict[str, Any] | None:
    """Load the exact source closure for a historical commit absent from public refs."""

    path = root / T09_DOWNSTREAM_FINALIZER_HISTORY_RELATIVE
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != T09_DOWNSTREAM_FINALIZER_HISTORY_SHA256:
        return None
    document = load_json(path)
    changed_paths = document.get("changed_paths")
    changed_hashes = document.get("changed_source_sha256s")
    if (
        document.get("schema_version") != "1.0.0"
        or document.get("record_type") != "t09-downstream-finalizer-source-history"
        or document.get("public_ref_reachability") != "not-required-history-closure"
        or document.get("frozen_scientific_package_commit")
        != "6d3005bb5ce915eabb801ef35e11855cd9420338"
        or document.get("downstream_finalizer_commit") != "d6a080264c7d2ac83efc9806d2a2ae4c141a1113"
        or document.get("downstream_tree_sha1") != "24fac4555f5b855256a4bb0abf300b4339cf893b"
        or changed_paths
        != [
            "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py",
            "containers/sira-smoke/pragmatic/t09_remote_runner.py",
            "tests/test_t09_sira_pilot.py",
        ]
        or changed_hashes
        != {
            "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py": (
                "99705a977e94e5c84eaffd412c96a8a8828f3dd90acb86f510cd9859632cc5c0"
            ),
            "containers/sira-smoke/pragmatic/t09_remote_runner.py": (
                "69c96acbecc588a2fa0dd0bfd1e4569fa4bc254c0fabc5802e9e62f5b2592b40"
            ),
            "tests/test_t09_sira_pilot.py": (
                "18ea8e1347a7b0646418f027ab96f8ad851014aee6a106394a7f0cfc2d3e45be"
            ),
        }
    ):
        return None
    return document


def validate_exp0001_contract(root: Path = ROOT) -> list[str]:
    """Enforce EXP-0001-specific science, task, identity, and price locks."""

    registry = load_yaml(root / "experiments/registry.yaml")
    registered = {
        entry.get("experiment_id")
        for entry in registry.get("experiments", [])
        if isinstance(entry, dict)
    }
    if "EXP-0001" not in registered:
        return []
    errors: list[str] = []
    exp_root = root / "experiments/EXP-0001-sira-simulative-vs-reactive"
    protocol = load_yaml(exp_root / "protocol.yaml")
    config = load_yaml(exp_root / "config.yaml")
    if protocol.get("systems") != {
        "treatment": "SIRA-SIMULATIVE",
        "controls": ["SIRA-REACTIVE"],
    }:
        errors.append("EXP-0001: treatment/control contract drift")
    profiles = {name: load_yaml(exp_root / f"run-plans/{name}.yaml") for name in ("smoke", "pilot")}
    expected_model_id = "MODEL-OPENAI-GPT4O-2024-11-20"
    expected_revision = "gpt-4o-2024-11-20"
    for name, profile in profiles.items():
        model = profile.get("model", {})
        if not isinstance(model, dict) or (
            model.get("manifest_id") != expected_model_id
            or model.get("proposed_immutable_revision") != expected_revision
            or model.get("reproduction_level") != "directional-reproduction"
        ):
            errors.append(f"EXP-0001 {name}: locked model/substitution contract drift")
        expected_execution = (
            {
                "authorized": True,
                "authorization_reference": (
                    "AUTH-T09-AUTONOMOUS-RETRY2-2026-08-27:sha256:"
                    "aea63a42cf0270ad0a41a929b4b8eb19dd1c3af73abfe97163c1d90e6077d3da"
                ),
            }
            if name == "pilot"
            else {"authorized": False, "authorization_reference": None}
        )
        if profile.get("execution") != expected_execution:
            errors.append(f"EXP-0001 {name}: current authorization binding drift")
        expected_readiness = {
            "smoke": "eligible-after-authorization",
            "pilot": "eligible-after-authorization",
        }[name]
        if profile.get("readiness", {}).get("execution_eligibility") != expected_readiness:
            errors.append(f"EXP-0001 {name}: execution eligibility drift")
    expected_tasks = {
        "smoke": [
            (
                "README-GOOGLE-FLIGHTS",
                "open-ended-query",
                "go to google flights",
                None,
                None,
                None,
                None,
                "SIRA-REACTIVE",
                "SIRA-SIMULATIVE",
            )
        ],
        "pilot": [
            (
                "7dcbbbdc7f1120cd",
                "dataset-slice",
                None,
                "DATA-SIRA-FANOUTQA-DEV",
                "76ad1feb689b754bfe4e5e24d3ea371b647efa67",
                0,
                1,
                "SIRA-REACTIVE",
                "SIRA-SIMULATIVE",
            ),
            (
                "2120afba8009bad3",
                "dataset-slice",
                None,
                "DATA-SIRA-FANOUTQA-DEV",
                "76ad1feb689b754bfe4e5e24d3ea371b647efa67",
                1,
                2,
                "SIRA-SIMULATIVE",
                "SIRA-REACTIVE",
            ),
        ],
    }
    for name, expected in expected_tasks.items():
        counterbalancing = profiles[name].get("sampling", {}).get("counterbalancing", [])
        observed: list[tuple[Any, ...]] = []
        for pair in counterbalancing if isinstance(counterbalancing, list) else []:
            if not isinstance(pair, dict):
                continue
            bindings = pair.get("plans", [])
            if not isinstance(bindings, list) or not bindings:
                continue
            path = bindings[0].get("path") if isinstance(bindings[0], dict) else None
            if not isinstance(path, str):
                continue
            task = load_yaml(resolve_repo_path(root, path)).get("task", {})
            if isinstance(task, dict):
                observed.append(
                    (
                        task.get("task_id"),
                        task.get("source_kind"),
                        task.get("query"),
                        task.get("dataset_id"),
                        task.get("dataset_revision"),
                        task.get("start_idx"),
                        task.get("end_idx"),
                        pair.get("first"),
                        pair.get("second"),
                    )
                )
        if observed != expected:
            errors.append(f"EXP-0001 {name}: locked task or slice drift")
    pricing = load_yaml(exp_root / "pricing.yaml")
    expected_rates = {
        "input": Decimal("2.50"),
        "cached_input": Decimal("1.25"),
        "output": Decimal("10.00"),
    }
    rates = pricing.get("rates_per_million_tokens", {})
    if (
        not isinstance(rates, dict)
        or {key: Decimal(str(rates.get(key))) for key in expected_rates} != expected_rates
    ):
        errors.append("EXP-0001: official dated GPT-4o price record drift")
    if pricing.get("source") != "https://developers.openai.com/api/docs/models/gpt-4o":
        errors.append("EXP-0001: official pricing source drift")
    price_profiles = pricing.get("profiles", {})
    output_rate = expected_rates["output"]
    for name, profile in profiles.items():
        price_profile = price_profiles.get(name, {}) if isinstance(price_profiles, dict) else {}
        if not isinstance(price_profile, dict):
            errors.append(f"EXP-0001 {name}: missing price profile")
            continue
        per_attempt = (
            Decimal(price_profile.get("max_model_tokens_per_attempt", 0))
            / Decimal(1_000_000)
            * output_rate
        )
        attempts = price_profile.get("condition_attempts")
        proposed_cap = Decimal(str(price_profile.get("proposed_profile_cap_usd")))
        if (
            per_attempt != Decimal(str(price_profile.get("max_cost_usd_per_attempt")))
            or not isinstance(attempts, int)
            or per_attempt * attempts != proposed_cap
            or proposed_cap != Decimal(str(profile.get("budget", {}).get("max_cost_usd")))
            or pricing.get("authorization", {}).get(name) is not False
        ):
            errors.append(f"EXP-0001 {name}: pricing arithmetic or authorization drift")
    manifest_entries: dict[str, Mapping[str, Any]] = {}
    for relative in ("manifests/models.yaml", "manifests/datasets.yaml"):
        entries = load_yaml(root / relative).get("entries", [])
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                manifest_entries[entry["id"]] = entry
    model_entry = manifest_entries.get(expected_model_id, {})
    if model_entry.get("revision") != expected_revision:
        errors.append("EXP-0001: model manifest revision does not resolve")
    dataset_entry = manifest_entries.get("DATA-SIRA-FANOUTQA-DEV", {})
    pilot_dataset = config.get("sampling", {}).get("pilot", {})
    if not isinstance(pilot_dataset, dict) or (
        dataset_entry.get("revision") != pilot_dataset.get("dataset_revision")
        or dataset_entry.get("sha256") != pilot_dataset.get("dataset_sha256")
    ):
        errors.append("EXP-0001: dataset manifest identity does not resolve")

    pilot_lifecycle = profiles["pilot"].get("provider_lifecycle")
    expected_lifecycle = {
        "cumulative_accounting_origin": "actual-active-lambda-seconds",
        "preflight_clock_origin": "provider-launch-send-started",
        "preflight_iteration_wall_seconds": 3_600,
        "maximum_preflight_instance_active_seconds": 21_600,
        "maximum_cumulative_preflight_active_seconds": 43_200,
        "maximum_preflight_provider_cost_usd": 10.0,
        "max_preflight_launch_count": 8,
        "failed_preflight_termination_dispatch_seconds": 300,
        "empirical_clock_origin": "after-durable-frozen-run-manifest-publication",
        "empirical_campaign_wall_seconds": 14_400,
        "evidence_export_reserve_seconds": 600,
        "provider_termination_handoff_seconds": 60,
        "empirical_cleanup_reserve_seconds": 900,
        "empirical_termination_cutoff_seconds": 13_500,
        "maximum_empirical_provider_cost_usd": 8.0,
        "max_empirical_launch_count": 1,
        "max_lambda_instances": 1,
        "persistent_filesystems": 0,
        "replacement_launch_rule": {
            "allowed_only_before_empirical_entry": True,
            "prior_instance_terminal_and_absent_required": True,
            "prior_host_empirical_attempts_required": 0,
            "prior_host_model_requests_required": 0,
            "prior_host_browser_actions_required": 0,
            "ownership_outcome_unknown_forbidden": True,
            "cumulative_lambda_cap_required": True,
        },
        "admission_rule": (
            "remaining campaign time must cover the next 3600-second condition hard wall, "
            "600-second direct evidence export, 60-second provider termination handoff, "
            "and 900-second cleanup reserve"
        ),
        "supervised_release_wait_seconds": 300,
        "supervised_release_rule": (
            "the credential-free started entrypoint may wait up to 300 seconds for the final "
            "source-bound state, budget, core, exact-secret, and owned-container checks; the "
            "5160-second admission gate is rerun immediately before durable release and any "
            "timeout consumes the started identity as infrastructure-invalid"
        ),
        "control_plane": "autonomous-v9-provider-call-accounting-repair",
    }
    if pilot_lifecycle != expected_lifecycle:
        errors.append("EXP-0001 pilot: provider lifecycle contract drift")

    historical_disposition = exp_root / "T09_PRAGMATIC_PREFLIGHT_DISPOSITION.json"
    supersession_path = exp_root / "T09_PRAGMATIC_RETRY2_SUPERSESSION.json"
    if not historical_disposition.is_file() or not supersession_path.is_file():
        errors.append("EXP-0001 T09 Retry 2: historical disposition or supersession is missing")
    else:
        supersession = load_json(supersession_path)
        historical = supersession.get("historical_disposition")
        if (
            hashlib.sha256(historical_disposition.read_bytes()).hexdigest()
            != "cb6ba0b003b61aec83a2a42188ee784c93ee08ae7e504f5a15a7287af83ac709"
            or not isinstance(historical, dict)
            or historical.get("classification")
            != "preflight_blocked_by_overstrict_cross_run_image_digest_requirement"
            or historical.get("model_calls") != 0
            or historical.get("browser_actions") != 0
            or historical.get("condition_attempts") != 0
            or historical.get("empirical_boundary_crossed") is not False
        ):
            errors.append("EXP-0001 T09 Retry 2: prior failure preservation drifted")

    retry2_disposition_path = exp_root / "T09_PRAGMATIC_RETRY2_DISPOSITION.json"
    if not retry2_disposition_path.is_file():
        errors.append("EXP-0001 T09 Retry 2: terminal disposition is missing")
    else:
        disposition = load_json(retry2_disposition_path)
        attempts = disposition.get("attempts")
        usage = disposition.get("usage")
        provider = disposition.get("provider")
        costs = disposition.get("cost_reconciliation")
        cleanup = disposition.get("cleanup")
        pair_matching = disposition.get("pair_matching")
        evidence = disposition.get("evidence")
        reactive = attempts.get("task_a_reactive") if isinstance(attempts, dict) else None
        not_run_attempts = (
            [
                attempts.get(key)
                for key in ("task_a_simulative", "task_b_simulative", "task_b_reactive")
            ]
            if isinstance(attempts, dict)
            else []
        )
        if (
            disposition.get("record_id") != "T09-PRAGMATIC-RETRY2-DISPOSITION-0001"
            or disposition.get("plan_id") != "PLAN-EXP0001-PILOT-V4"
            or disposition.get("terminal_state") != "t09-pilot-blocked-material-risk"
            or disposition.get("lifecycle_state")
            != "stopped-after-one-valid-scored-attempt-before-pair-completion"
            or disposition.get("calibration_only") is not True
            or disposition.get("empirical_entry") is not True
            or disposition.get("scientific_result_claimed") is not False
            or disposition.get("experiment_outcome_assigned") is not False
            or disposition.get("experiment_evidence_status") != "not-evaluated"
        ):
            errors.append("EXP-0001 T09 Retry 2: terminal scientific boundary drifted")
        if (
            not isinstance(attempts, dict)
            or attempts.get("empirical_attempts_entered") != ["RUN-T09-TASK-A-REACTIVE-0002"]
            or attempts.get("attempts_completed") != ["RUN-T09-TASK-A-REACTIVE-0002"]
            or attempts.get("condition_retries") != 0
            or attempts.get("first_pair_checkpoint")
            != "not-reached-stopped-before-task-a-simulative"
            or attempts.get("realized_task_a_pair") is not False
            or attempts.get("realized_task_b_pair") is not False
            or not isinstance(reactive, dict)
            or reactive.get("task_completion") != "completed"
            or reactive.get("evaluator_validity") is not True
            or reactive.get("task_score") != 0.0
            or reactive.get("invalid_infrastructure_attempt") is not False
            or reactive.get("condition_failure") is not False
            or any(
                not isinstance(item, dict)
                or item.get("state") != "not-run"
                or item.get("empirical_entry") is not False
                for item in not_run_attempts
            )
        ):
            errors.append("EXP-0001 T09 Retry 2: one-attempt/no-pair disposition drifted")
        if usage != {
            "model_metadata_requests": 1,
            "task_model_calls": 52,
            "input_tokens": 114181,
            "cached_input_tokens": 0,
            "output_tokens": 7719,
            "total_tokens": 121900,
            "browser_actions": 13,
            "condition_attempts": 1,
            "condition_retries": 0,
            "openai_cost_usd": 0.3626425,
        }:
            errors.append("EXP-0001 T09 Retry 2: usage reconciliation drifted")
        if (
            not isinstance(provider, dict)
            or provider.get("launch_count") != 1
            or provider.get("maximum_launch_count") != 1
            or provider.get("persistent_filesystems") != 0
            or provider.get("termination_request_count") != 1
            or provider.get("terminal_or_absent") is not True
            or provider.get("zero_t09_instances") is not True
            or provider.get("security_restored") is not True
            or not isinstance(cleanup, dict)
            or cleanup.get("temporary_secret_removed") is not True
            or cleanup.get("direct_attempt_export_verified_before_termination") is not True
            or cleanup.get("provider_terminal_or_absent") is not True
            or cleanup.get("zero_t09_instances") is not True
            or cleanup.get("security_restored") is not True
        ):
            errors.append("EXP-0001 T09 Retry 2: cleanup/provider closeout drifted")
        if (
            not isinstance(pair_matching, dict)
            or pair_matching.get("task_a_static_pair_diff_valid") is not True
            or pair_matching.get("task_b_static_pair_diff_valid") is not True
            or pair_matching.get("task_a_realized_pair_available") is not False
            or pair_matching.get("task_b_realized_pair_available") is not False
            or pair_matching.get("paired_or_comparative_interpretation_permitted") is not False
        ):
            errors.append("EXP-0001 T09 Retry 2: pair boundary drifted")
        if isinstance(costs, dict):
            try:
                prior = Decimal(str(costs.get("prior_t09_cost_usd")))
                openai_cost = Decimal(str(costs.get("new_openai_cost_usd")))
                lambda_cost = Decimal(str(costs.get("new_lambda_cost_usd")))
                new_total = Decimal(str(costs.get("new_campaign_total_cost_usd")))
                cumulative = Decimal(str(costs.get("cumulative_t09_cost_usd")))
                new_cap = Decimal(str(costs.get("new_campaign_cap_usd")))
                cumulative_cap = Decimal(str(costs.get("cumulative_t09_cap_usd")))
            except InvalidOperation:
                errors.append("EXP-0001 T09 Retry 2: cost reconciliation is malformed")
            else:
                if (
                    new_total != openai_cost + lambda_cost
                    or abs(cumulative - (prior + new_total)) > Decimal("1e-15")
                    or new_total > new_cap
                    or cumulative > cumulative_cap
                    or costs.get("all_cost_caps_respected") is not True
                ):
                    errors.append("EXP-0001 T09 Retry 2: cost reconciliation drifted")
        else:
            errors.append("EXP-0001 T09 Retry 2: cost reconciliation is missing")
        if not isinstance(evidence, dict) or evidence.get("archive_id") != (
            "ARCHIVE-EXP0001-PILOT-V4-0002"
        ):
            errors.append("EXP-0001 T09 Retry 2: evidence archive identity drifted")
        elif any(
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for key, value in evidence.items()
            if key.endswith("_sha256")
        ):
            errors.append("EXP-0001 T09 Retry 2: evidence digest is malformed")

    retry3_disposition_path = exp_root / "T09_PRAGMATIC_RETRY3_DISPOSITION.json"
    if not retry3_disposition_path.is_file():
        errors.append("EXP-0001 T09 Retry 3: terminal disposition is missing")
    else:
        disposition = load_json(retry3_disposition_path)
        attempts = disposition.get("attempts")
        runtime = disposition.get("replacement_runtime")
        usage = disposition.get("usage")
        provider = disposition.get("provider")
        costs = disposition.get("cost_reconciliation")
        cleanup = disposition.get("cleanup")
        pair_matching = disposition.get("pair_matching")
        evidence = disposition.get("evidence")
        if (
            disposition.get("record_id") != "T09-PRAGMATIC-RETRY3-DISPOSITION-0001"
            or disposition.get("plan_id") != "PLAN-EXP0001-PILOT-V5"
            or disposition.get("terminal_state") != "t09-pilot-blocked-material-risk"
            or disposition.get("lifecycle_state")
            != (
                "stopped-preempirically-after-two-authorized-launches-"
                "campaign-admission-window-exhausted"
            )
            or disposition.get("calibration_only") is not True
            or disposition.get("empirical_entry") is not False
            or disposition.get("scientific_result_claimed") is not False
            or disposition.get("experiment_outcome_assigned") is not False
            or disposition.get("experiment_evidence_status") != "not-evaluated"
            or disposition.get("single_use_authority_exhausted") is not True
            or disposition.get("launch_slots_exhausted") is not True
        ):
            errors.append("EXP-0001 T09 Retry 3: terminal scientific boundary drifted")
        expected_not_run_ids = {
            "task_a_reactive": "RUN-T09-TASK-A-REACTIVE-0003",
            "task_a_simulative": "RUN-T09-TASK-A-SIMULATIVE-0003",
            "task_b_simulative": "RUN-T09-TASK-B-SIMULATIVE-0003",
            "task_b_reactive": "RUN-T09-TASK-B-REACTIVE-0003",
        }
        if (
            not isinstance(attempts, dict)
            or attempts.get("empirical_attempts_entered") != []
            or attempts.get("raw_attempts_complete") != []
            or attempts.get("attempts_completed") != []
            or attempts.get("condition_retries") != 0
            or attempts.get("first_pair_checkpoint") != "not-reached-no-empirical-attempt-started"
            or attempts.get("realized_task_a_pair") is not False
            or attempts.get("realized_task_b_pair") is not False
            or any(
                not isinstance(attempts.get(key), dict)
                or attempts[key].get("run_id") != run_id
                or attempts[key].get("state") != "not-run"
                or attempts[key].get("empirical_entry") is not False
                for key, run_id in expected_not_run_ids.items()
            )
        ):
            errors.append("EXP-0001 T09 Retry 3: zero-attempt disposition drifted")
        if usage != {
            "model_metadata_requests": 0,
            "task_model_calls": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "browser_actions": 0,
            "condition_attempts": 0,
            "condition_retries": 0,
            "openai_cost_usd": 0.0,
        }:
            errors.append("EXP-0001 T09 Retry 3: zero-usage reconciliation drifted")
        if (
            not isinstance(runtime, dict)
            or runtime.get("candidate_build_attempt_count") != 1
            or runtime.get("additional_build_count_on_slot2") != 0
            or runtime.get("loadable_image_archive_preserved") is not True
            or runtime.get("slot2_image_import_started") is not False
            or runtime.get("slot2_functional_qualification_started") is not False
            or runtime.get("replacement_image_qualified_for_v5") is not False
            or runtime.get("frozen_run_manifest_written") is not False
            or runtime.get("frozen_run_manifest_sha256") is not None
            or runtime.get("model_metadata_requests") != 0
            or runtime.get("task_model_requests") != 0
            or runtime.get("task_browser_actions") != 0
        ):
            errors.append("EXP-0001 T09 Retry 3: pre-empirical runtime boundary drifted")
        slot1 = provider.get("slot1") if isinstance(provider, dict) else None
        slot2 = provider.get("slot2") if isinstance(provider, dict) else None
        if (
            not isinstance(provider, dict)
            or provider.get("launch_count") != 2
            or provider.get("maximum_launch_count") != 2
            or provider.get("persistent_filesystems") != 0
            or provider.get("termination_request_count") != 2
            or provider.get("terminal_or_absent") is not True
            or provider.get("zero_t09_instances") is not True
            or provider.get("security_restored") is not True
            or provider.get("campaign_wall_exception") != "none"
            or not isinstance(slot1, dict)
            or not isinstance(slot2, dict)
            or any(
                slot.get("termination_request_count") != 1
                or slot.get("terminal_or_absent") is not True
                or slot.get("zero_t09_instances") is not True
                or slot.get("security_restored") is not True
                for slot in (slot1, slot2)
            )
            or not isinstance(cleanup, dict)
            or cleanup.get("slot1_temporary_secret_removed") is not True
            or cleanup.get("slot2_remote_secret_uploaded") is not False
            or cleanup.get("slot2_host_access_started") is not False
            or cleanup.get("provider_terminal_or_absent") is not True
            or cleanup.get("zero_t09_instances") is not True
            or cleanup.get("security_restored") is not True
            or cleanup.get("owned_provider_state_removed") is not True
        ):
            errors.append("EXP-0001 T09 Retry 3: provider/cleanup closeout drifted")
        if isinstance(provider, dict) and isinstance(slot1, dict) and isinstance(slot2, dict):
            try:
                active = Decimal(str(provider.get("active_lambda_duration_seconds")))
                active_sum = Decimal(str(slot1.get("owned_lambda_duration_seconds"))) + Decimal(
                    str(slot2.get("owned_lambda_duration_seconds"))
                )
                lambda_cost = Decimal(str(provider.get("list_cost_usd")))
                slot_cost_sum = Decimal(str(slot1.get("list_cost_usd"))) + Decimal(
                    str(slot2.get("list_cost_usd"))
                )
            except InvalidOperation:
                errors.append("EXP-0001 T09 Retry 3: provider accounting is malformed")
            else:
                if abs(active - active_sum) > Decimal("1e-12") or abs(
                    lambda_cost - slot_cost_sum
                ) > Decimal("1e-15"):
                    errors.append("EXP-0001 T09 Retry 3: two-slot provider accounting drifted")
        if (
            not isinstance(pair_matching, dict)
            or pair_matching.get("task_a_static_pair_diff_valid") is not True
            or pair_matching.get("task_b_static_pair_diff_valid") is not True
            or pair_matching.get("task_a_realized_pair_available") is not False
            or pair_matching.get("task_b_realized_pair_available") is not False
            or pair_matching.get("paired_or_comparative_interpretation_permitted") is not False
        ):
            errors.append("EXP-0001 T09 Retry 3: pair boundary drifted")
        if isinstance(costs, dict):
            try:
                prior = Decimal(str(costs.get("prior_t09_cost_usd")))
                openai_cost = Decimal(str(costs.get("new_openai_cost_usd")))
                lambda_cost = Decimal(str(costs.get("new_lambda_cost_usd")))
                new_total = Decimal(str(costs.get("new_campaign_total_cost_usd")))
                cumulative = Decimal(str(costs.get("cumulative_t09_cost_usd")))
                new_cap = Decimal(str(costs.get("new_campaign_cap_usd")))
                cumulative_cap = Decimal(str(costs.get("cumulative_t09_cap_usd")))
            except InvalidOperation:
                errors.append("EXP-0001 T09 Retry 3: cost reconciliation is malformed")
            else:
                if (
                    new_total != openai_cost + lambda_cost
                    or abs(cumulative - (prior + new_total)) > Decimal("1e-15")
                    or new_total > new_cap
                    or cumulative > cumulative_cap
                    or costs.get("all_cost_caps_respected") is not True
                ):
                    errors.append("EXP-0001 T09 Retry 3: cost reconciliation drifted")
        else:
            errors.append("EXP-0001 T09 Retry 3: cost reconciliation is missing")
        if not isinstance(evidence, dict) or evidence.get("archive_id") != (
            "ARCHIVE-EXP0001-PILOT-V5-PREEMPIRICAL-0003"
        ):
            errors.append("EXP-0001 T09 Retry 3: evidence archive identity drifted")
        elif any(
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for key, value in evidence.items()
            if key.endswith("_sha256")
        ):
            errors.append("EXP-0001 T09 Retry 3: evidence digest is malformed")

    contract_root = exp_root / "contracts"
    execution_path = contract_root / "T09_PILOT_EXECUTION_CONTRACT.json"
    runtime_path = contract_root / "T09_PILOT_RUNTIME_IDENTITY.json"
    command_path = contract_root / "T09_PILOT_COMMAND_MANIFESTS.json"
    required_contracts = (
        contract_root / "T09_PILOT_DATASET_CONTRACT.json",
        contract_root / "T09_PILOT_EVALUATOR_CONTRACT.json",
        execution_path,
        runtime_path,
        command_path,
    )
    missing_contracts = [
        path.relative_to(root).as_posix() for path in required_contracts if not path.is_file()
    ]
    if missing_contracts:
        errors.append(
            "EXP-0001 T09: required machine contracts missing: " + ", ".join(missing_contracts)
        )
        return errors

    execution = load_json(execution_path)
    errors.extend(
        f"EXP-0001 T09 execution: {error}"
        for error in validate_instance(
            execution, root / "schemas/t09-sira-pilot-execution.schema.json"
        )
    )
    bindings = execution.get("contract_bindings")
    if not isinstance(bindings, dict):
        errors.append("EXP-0001 T09: execution contract bindings are malformed")
    else:
        expected_binding_names = {
            "plan",
            "dataset",
            "evaluator",
            "runtime",
            "real_evidence_regression",
            "execution_schema",
            "score_schema",
            "evidence_schema",
        }
        if set(bindings) != expected_binding_names:
            errors.append("EXP-0001 T09: execution contract binding names drifted")
        for label, raw in bindings.items():
            if not isinstance(label, str) or not isinstance(raw, dict):
                continue
            binding_relative = raw.get("path")
            digest = raw.get("sha256")
            if not isinstance(binding_relative, str) or not isinstance(digest, str):
                errors.append(f"EXP-0001 T09: {label} binding lacks path or SHA-256")
                continue
            relative_path = Path(binding_relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                errors.append(f"EXP-0001 T09: {label} binding path is unsafe")
                continue
            bound = root / relative_path
            if not bound.is_file():
                errors.append(f"EXP-0001 T09: {label} binding path does not resolve")
                continue
            observed_digest = hashlib.sha256(bound.read_bytes()).hexdigest()
            if observed_digest != digest:
                errors.append(f"EXP-0001 T09: {label} binding SHA-256 drifted")
            size = raw.get("size_bytes")
            if size is not None and size != bound.stat().st_size:
                errors.append(f"EXP-0001 T09: {label} binding byte size drifted")

    runtime_identity = load_json(runtime_path)
    base_runtime = runtime_identity.get("base_runtime")
    replacement_policy = runtime_identity.get("replacement_image_policy")
    scientific_runtime = runtime_identity.get("scientific_runtime")
    if (
        not isinstance(base_runtime, dict)
        or base_runtime.get("container_image_digest") is not None
        or base_runtime.get("installed_package_manifest_sha256")
        != "4ff2603fa5e0f7033ba773decdcb86abf648dcce22e469d26bc48214e390e104"
        or base_runtime.get("chromium_sha256")
        != "0498f208c25339f386413ada7b3c35293b0b6250e67d85446ba9541d7fd636f7"
        or not isinstance(scientific_runtime, dict)
        or scientific_runtime.get("runner_sha256")
        != "b06793ad1b366a934b798f9f3272fc80a7104a220cb3304ab3bda2eb2a78b331"
        or not isinstance(replacement_policy, dict)
        or replacement_policy.get("historical_image_digest")
        != "sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c"
        or replacement_policy.get("exact_historical_digest_equality_required") is not False
        or replacement_policy.get("runtime_binding")
        != "source-derived-mode-0600-O_EXCL-frozen-run-manifest"
    ):
        errors.append("EXP-0001 T09: replacement runtime semantic identity drifted")
    instrumentation = runtime_identity.get("repository_instrumentation")
    files = instrumentation.get("files") if isinstance(instrumentation, dict) else None
    successor_plan_path = next(
        (
            candidate
            for candidate in (
                exp_root / "run-plans/proposals/PLAN-EXP0001-PILOT-V14.yaml",
                exp_root / "run-plans/proposals/PLAN-EXP0001-PILOT-V13.yaml",
                exp_root / "run-plans/proposals/PLAN-EXP0001-PILOT-V12.yaml",
            )
            if candidate.is_file()
        ),
        exp_root / "run-plans/proposals/PLAN-EXP0001-PILOT-V12.yaml",
    )
    successor_bindings = (
        _t09_successor_implementation_binding_map(load_yaml(successor_plan_path))
        if successor_plan_path.is_file()
        else {}
    )
    if not isinstance(files, list) or not files:
        errors.append("EXP-0001 T09: runtime instrumentation file bindings are missing")
    else:
        disposition_path = exp_root / "T09_AUTONOMOUS_PILOT_DISPOSITION.json"
        disposition = load_json(disposition_path) if disposition_path.is_file() else {}
        scientific_freeze = disposition.get("scientific_freeze")
        finalizer = disposition.get("finalizer")
        downstream_paths = {
            "containers/sira-smoke/pragmatic/t09_remote_runner.py": "selector_source_sha256",
            "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py": ("finalizer_source_sha256"),
        }
        downstream_commit = (
            finalizer.get("downstream_finalizer_commit") if isinstance(finalizer, dict) else None
        )
        finalizer_frozen_package_commit = (
            finalizer.get("frozen_scientific_package_commit")
            if isinstance(finalizer, dict)
            else None
        )
        frozen_package_commit = (
            scientific_freeze.get("frozen_package_commit")
            if isinstance(scientific_freeze, dict)
            else None
        )
        frozen_package_bindings = {
            "frozen_execution_contract_sha256": execution_path,
            "frozen_command_manifests_sha256": command_path,
            "frozen_runtime_identity_sha256": runtime_path,
        }
        if isinstance(scientific_freeze, dict) and execution.get("plan_id") == disposition.get(
            "plan_id"
        ):
            for field, path in frozen_package_bindings.items():
                observed_digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if scientific_freeze.get(field) != observed_digest:
                    errors.append(f"EXP-0001 T09: disposition {field} drifted")
                    continue
                try:
                    frozen_bytes = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(root),
                            "show",
                            f"{frozen_package_commit}:{path.relative_to(root).as_posix()}",
                        ],
                        check=True,
                        capture_output=True,
                    ).stdout
                except subprocess.CalledProcessError:
                    errors.append(f"EXP-0001 T09: frozen package does not bind {field}")
                    continue
                if hashlib.sha256(frozen_bytes).hexdigest() != observed_digest:
                    errors.append(f"EXP-0001 T09: frozen package source drifted for {field}")
        if isinstance(downstream_commit, str) and isinstance(frozen_package_commit, str):
            history = _load_t09_downstream_finalizer_history(root)
            expected_downstream_diff = (
                set(history["changed_paths"])
                if history is not None
                else {
                    "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py",
                    "containers/sira-smoke/pragmatic/t09_remote_runner.py",
                    "tests/test_t09_sira_pilot.py",
                }
            )
            history_matches_disposition = (
                history is not None
                and history.get("frozen_scientific_package_commit") == frozen_package_commit
                and history.get("downstream_finalizer_commit") == downstream_commit
                and isinstance(finalizer, dict)
                and history.get("changed_source_sha256s", {}).get(
                    "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
                )
                == finalizer.get("finalizer_source_sha256")
                and history.get("changed_source_sha256s", {}).get(
                    "containers/sira-smoke/pragmatic/t09_remote_runner.py"
                )
                == finalizer.get("selector_source_sha256")
            )
            if not history_matches_disposition:
                errors.append("EXP-0001 T09: downstream finalizer history closure drifted")
            try:
                downstream_diff = set(
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(root),
                            "diff",
                            "--name-only",
                            f"{frozen_package_commit}..{downstream_commit}",
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.splitlines()
                )
            except subprocess.CalledProcessError:
                if not history_matches_disposition:
                    errors.append("EXP-0001 T09: downstream finalizer history is unavailable")
            else:
                if downstream_diff != expected_downstream_diff:
                    errors.append("EXP-0001 T09: downstream finalizer change scope drifted")
                if history is not None:
                    try:
                        downstream_tree = subprocess.run(
                            [
                                "git",
                                "-C",
                                str(root),
                                "rev-parse",
                                f"{downstream_commit}^{{tree}}",
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                        ).stdout.strip()
                        downstream_hashes = {
                            path: hashlib.sha256(
                                subprocess.run(
                                    [
                                        "git",
                                        "-C",
                                        str(root),
                                        "show",
                                        f"{downstream_commit}:{path}",
                                    ],
                                    check=True,
                                    capture_output=True,
                                ).stdout
                            ).hexdigest()
                            for path in expected_downstream_diff
                        }
                    except subprocess.CalledProcessError:
                        errors.append("EXP-0001 T09: downstream finalizer history is incomplete")
                    else:
                        if downstream_tree != history.get(
                            "downstream_tree_sha1"
                        ) or downstream_hashes != history.get("changed_source_sha256s"):
                            errors.append(
                                "EXP-0001 T09: downstream finalizer source closure drifted"
                            )
        downstream_mismatches: set[str] = set()
        retry2_disposition_path = exp_root / "T09_AUTONOMOUS_RETRY2_V9_DISPOSITION.json"
        retry2_disposition = (
            load_json(retry2_disposition_path) if retry2_disposition_path.is_file() else {}
        )
        post_terminal_repair = retry2_disposition.get("post_terminal_repair")
        validated_post_terminal_paths: set[str] = set()
        if isinstance(post_terminal_repair, dict):
            repair_commit = post_terminal_repair.get("repair_commit")
            repair_parent_commit = post_terminal_repair.get("repair_parent_commit")
            repair_frozen_commit = post_terminal_repair.get("frozen_scientific_package_commit")
            repair_files = post_terminal_repair.get("files")
            expected_repair_paths = {
                "src/giclab/harness/sira_gate_a.py",
                "tests/test_t09_provider_accounting.py",
            }
            repair_bindings: dict[str, dict[str, Any]] = {}
            if isinstance(repair_files, list):
                for item in repair_files:
                    if not isinstance(item, dict):
                        continue
                    repair_path = item.get("path")
                    if isinstance(repair_path, str):
                        repair_bindings[repair_path] = item
            repair_identity_valid = (
                post_terminal_repair.get("status") == "retained-post-terminal"
                and post_terminal_repair.get("scientific_runtime_changed_after_empirical_entry")
                is False
                and post_terminal_repair.get("campaign_evidence_mutated") is False
                and post_terminal_repair.get("campaign_retried") is False
                and isinstance(repair_commit, str)
                and re.fullmatch(r"[0-9a-f]{40}", repair_commit) is not None
                and isinstance(repair_parent_commit, str)
                and re.fullmatch(r"[0-9a-f]{40}", repair_parent_commit) is not None
                and isinstance(repair_frozen_commit, str)
                and re.fullmatch(r"[0-9a-f]{40}", repair_frozen_commit) is not None
                and retry2_disposition.get("qualification_and_freeze", {}).get(
                    "frozen_package_commit"
                )
                == repair_frozen_commit
                and set(repair_bindings) == expected_repair_paths
            )
            if repair_identity_valid:
                try:
                    observed_parent = subprocess.run(
                        ["git", "-C", str(root), "rev-parse", f"{repair_commit}^"],
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip()
                    repair_diff = set(
                        subprocess.run(
                            [
                                "git",
                                "-C",
                                str(root),
                                "diff",
                                "--name-only",
                                f"{repair_parent_commit}..{repair_commit}",
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                        ).stdout.splitlines()
                    )
                except subprocess.CalledProcessError:
                    repair_identity_valid = False
                else:
                    repair_identity_valid = (
                        observed_parent == repair_parent_commit
                        and repair_diff == expected_repair_paths
                        and post_terminal_repair.get("commit_diff_paths")
                        == sorted(expected_repair_paths)
                    )
            if repair_identity_valid:
                instrumentation_digests = {
                    item.get("path"): item.get("sha256") for item in files if isinstance(item, dict)
                }
                for repair_path, repair_binding in repair_bindings.items():
                    current_path = root / repair_path
                    frozen_digest = repair_binding.get("frozen_sha256")
                    repaired_digest = repair_binding.get("repaired_sha256")
                    try:
                        frozen_bytes = subprocess.run(
                            [
                                "git",
                                "-C",
                                str(root),
                                "show",
                                f"{repair_frozen_commit}:{repair_path}",
                            ],
                            check=True,
                            capture_output=True,
                        ).stdout
                        repaired_bytes = subprocess.run(
                            [
                                "git",
                                "-C",
                                str(root),
                                "show",
                                f"{repair_commit}:{repair_path}",
                            ],
                            check=True,
                            capture_output=True,
                        ).stdout
                    except subprocess.CalledProcessError:
                        repair_identity_valid = False
                        break
                    current_digest = (
                        hashlib.sha256(current_path.read_bytes()).hexdigest()
                        if current_path.is_file()
                        else None
                    )
                    if (
                        hashlib.sha256(repaired_bytes).hexdigest() != repaired_digest
                        or hashlib.sha256(frozen_bytes).hexdigest() != frozen_digest
                        or (
                            repair_path == "src/giclab/harness/sira_gate_a.py"
                            and instrumentation_digests.get(repair_path) != frozen_digest
                        )
                        or (
                            current_digest != repaired_digest
                            and successor_bindings.get(repair_path) != current_digest
                        )
                    ):
                        repair_identity_valid = False
                        break
            if repair_identity_valid:
                validated_post_terminal_paths = expected_repair_paths
            else:
                errors.append("EXP-0001 T09: post-terminal repair binding drifted")
        for raw in files:
            if not isinstance(raw, dict):
                errors.append("EXP-0001 T09: runtime instrumentation binding is malformed")
                continue
            file_relative = raw.get("path")
            digest = raw.get("sha256")
            if not isinstance(file_relative, str) or not isinstance(digest, str):
                errors.append("EXP-0001 T09: runtime instrumentation binding is incomplete")
                continue
            relative_path = Path(file_relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                errors.append("EXP-0001 T09: runtime instrumentation path is unsafe")
                continue
            bound = root / relative_path
            if not bound.is_file():
                errors.append(f"EXP-0001 T09: runtime file binding drifted: {file_relative}")
                continue
            observed_digest = hashlib.sha256(bound.read_bytes()).hexdigest()
            if observed_digest == digest:
                continue
            if file_relative in validated_post_terminal_paths:
                continue
            if successor_bindings.get(file_relative) == observed_digest:
                continue
            disposition_field = downstream_paths.get(file_relative)
            disposition_digest = (
                finalizer.get(disposition_field)
                if isinstance(finalizer, dict) and disposition_field is not None
                else None
            )
            if (
                disposition_digest != observed_digest
                or not isinstance(downstream_commit, str)
                or not re.fullmatch(r"[0-9a-f]{40}", downstream_commit)
                or finalizer_frozen_package_commit != frozen_package_commit
            ):
                errors.append(f"EXP-0001 T09: runtime file binding drifted: {file_relative}")
                continue
            try:
                committed_bytes = subprocess.run(
                    ["git", "-C", str(root), "show", f"{downstream_commit}:{file_relative}"],
                    check=True,
                    capture_output=True,
                ).stdout
            except subprocess.CalledProcessError:
                errors.append(
                    f"EXP-0001 T09: downstream finalizer commit does not bind: {file_relative}"
                )
                continue
            if hashlib.sha256(committed_bytes).hexdigest() != observed_digest:
                errors.append(f"EXP-0001 T09: downstream finalizer source drifted: {file_relative}")
                continue
            downstream_mismatches.add(file_relative)
        if downstream_mismatches and downstream_mismatches != set(downstream_paths):
            errors.append(
                "EXP-0001 T09: downstream finalizer must bind both selector and evaluator"
            )

    command_document = load_json(command_path)
    execution_sha256 = hashlib.sha256(execution_path.read_bytes()).hexdigest()
    plan_path = exp_root / "run-plans/pilot.yaml"
    if (
        command_document.get("schema_version") != "0.1.0"
        or command_document.get("plan_id") != "PLAN-EXP0001-PILOT-V9"
        or command_document.get("execution_contract_sha256") != execution_sha256
        or command_document.get("plan_sha256") != hashlib.sha256(plan_path.read_bytes()).hexdigest()
    ):
        errors.append("EXP-0001 T09: command package identity or contract binding drifted")
    generator_relative = command_document.get("generator_path")
    generator_sha256 = command_document.get("generator_sha256")
    generator_path = root / generator_relative if isinstance(generator_relative, str) else None
    observed_generator_sha256 = (
        hashlib.sha256(generator_path.read_bytes()).hexdigest()
        if generator_path is not None and generator_path.is_file()
        else None
    )
    if (
        not isinstance(generator_relative, str)
        or Path(generator_relative).is_absolute()
        or ".." in Path(generator_relative).parts
        or not isinstance(generator_sha256, str)
        or observed_generator_sha256 is None
        or (
            observed_generator_sha256 != generator_sha256
            and successor_bindings.get(generator_relative) != observed_generator_sha256
        )
    ):
        errors.append("EXP-0001 T09: command generator binding drifted")
    from giclab.harness.t09_provider_contracts import (
        T09ProviderContractError,
        provider_contract_for_plan_id,
    )

    try:
        retained_package_contract = provider_contract_for_plan_id(str(execution.get("plan_id")))
    except T09ProviderContractError:
        errors.append("EXP-0001 T09: frozen package provider contract is unsupported")
        return errors
    if retained_package_contract.version == "V9":
        # The V9 package is immutable historical evidence.  Once the active
        # typed loader advances, do not reinterpret or rerender V9 with successor
        # constants. Its committed package/source bindings above remain
        # authoritative; the active successor gets an independent typed render
        # gate in its versioned plan validator and focused tests.
        pair_diffs = command_document.get("pair_diffs")
        if (
            not isinstance(pair_diffs, list)
            or len(pair_diffs) != 2
            or any(
                not isinstance(pair, dict) or pair.get("valid") is not True for pair in pair_diffs
            )
        ):
            errors.append("EXP-0001 T09: frozen historical command/config pair equality failed")
        return errors
    try:
        from giclab.harness.t09_sira_pilot import (
            diff_pair_manifests,
            load_execution_contract,
            render_command_manifest,
        )

        typed_contract = load_execution_contract(
            execution_path,
            expected_sha256=execution_sha256,
        )
        runtime_sha256 = hashlib.sha256(
            (root / "src/giclab/harness/sira_gate_a_runtime.py").read_bytes()
        ).hexdigest()
        library_sha256 = hashlib.sha256(
            (root / "src/giclab/harness/t09_sira_pilot.py").read_bytes()
        ).hexdigest()
        rendered = [
            render_command_manifest(
                typed_contract,
                attempt,
                execution_contract_runtime_path="/opt/giclab-contracts/execution.json",
                runtime_adaptation_path=("/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py"),
                runtime_adaptation_sha256=runtime_sha256,
                pilot_library_sha256=library_sha256,
                aggregate_ledger_path=(
                    "/opt/giclab-artifacts/pilot-v7/runtime-budget/aggregate-budget.json"
                ),
                pilot_state_path="/opt/giclab-artifacts/pilot-v7/pilot-state.json",
            )
            for attempt in typed_contract.attempts
        ]
        if command_document.get("manifests") != rendered:
            errors.append("EXP-0001 T09: frozen command manifests differ from exact rerender")
        expected_diffs = [
            diff_pair_manifests(rendered[0], rendered[1]),
            diff_pair_manifests(rendered[2], rendered[3]),
        ]
        if command_document.get("pair_diffs") != expected_diffs or any(
            item.get("valid") is not True for item in expected_diffs
        ):
            errors.append("EXP-0001 T09: command/config pair equality failed")
        commits = {attempt.giclab_commit for attempt in typed_contract.attempts}
        if len(commits) != 1 or "unknown" in commits:
            errors.append("EXP-0001 T09: reviewed implementation ancestor is not bound")
        else:
            reviewed_ancestor = next(iter(commits))
            if command_document.get("reviewed_implementation_ancestor") != reviewed_ancestor:
                errors.append("EXP-0001 T09: command/reviewed-ancestor binding drifted")
            if isinstance(files, list):
                for raw in files:
                    if not isinstance(raw, dict):
                        continue
                    runtime_relative = raw.get("path")
                    expected_digest = raw.get("sha256")
                    if not isinstance(runtime_relative, str) or not isinstance(
                        expected_digest, str
                    ):
                        continue
                    historical = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(root),
                            "show",
                            f"{reviewed_ancestor}:{runtime_relative}",
                        ],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    if (
                        historical.returncode != 0
                        or hashlib.sha256(historical.stdout).hexdigest() != expected_digest
                    ):
                        errors.append(
                            "EXP-0001 T09: reviewed ancestor runtime bytes drifted: "
                            + runtime_relative
                        )
        for attempt in typed_contract.attempts:
            condition_path = root / attempt.condition_plan_path
            if (
                not condition_path.is_file()
                or hashlib.sha256(condition_path.read_bytes()).hexdigest()
                != attempt.condition_plan_sha256
            ):
                errors.append(f"EXP-0001 T09: condition binding drifted: {attempt.run_id}")
                continue
            condition = load_yaml(condition_path)
            sources = condition.get("sources")
            if not isinstance(sources, dict):
                errors.append(f"EXP-0001 T09: condition sources missing: {attempt.run_id}")
                continue
            expected_common = {
                "protocol_sha256": attempt.protocol_sha256,
                "config_sha256": attempt.config_sha256,
                "environment_sha256": attempt.environment_sha256,
            }
            if any(sources.get(field) != digest for field, digest in expected_common.items()):
                errors.append(f"EXP-0001 T09: condition common binding drifted: {attempt.run_id}")
            actual_common = {
                "protocol_sha256": hashlib.sha256(
                    (exp_root / "protocol.yaml").read_bytes()
                ).hexdigest(),
                "config_sha256": hashlib.sha256(
                    (exp_root / "config.yaml").read_bytes()
                ).hexdigest(),
                "environment_sha256": hashlib.sha256(runtime_path.read_bytes()).hexdigest(),
            }
            if expected_common != actual_common:
                errors.append(f"EXP-0001 T09: condition common file hash drifted: {attempt.run_id}")
    except (OSError, ValueError) as exc:
        errors.append(f"EXP-0001 T09: typed execution/command contract failed: {exc}")
    return errors


def validate_transition_record(record: Mapping[str, Any], root: Path = ROOT) -> list[str]:
    """Validate one transition, including cross-reference invariants."""

    errors = validate_instance(record, root / "schemas/transition.schema.json")
    candidates = record.get("candidate_actions")
    candidate_ids: list[str] = []
    if isinstance(candidates, list):
        candidate_ids = [
            str(item.get("candidate_action_id"))
            for item in candidates
            if isinstance(item, dict) and isinstance(item.get("candidate_action_id"), str)
        ]
        if len(candidate_ids) != len(set(candidate_ids)):
            errors.append("candidate_action_id values must be unique within a transition")
    candidate_set = set(candidate_ids)
    futures = record.get("predicted_futures")
    if isinstance(futures, list):
        for index, future in enumerate(futures):
            if isinstance(future, dict) and future.get("candidate_action_id") not in candidate_set:
                errors.append(f"predicted_futures[{index}] references an unknown candidate action")
    plan = record.get("selected_plan")
    if isinstance(plan, dict):
        for candidate_id in plan.get("candidate_action_ids", []):
            if candidate_id not in candidate_set:
                errors.append(f"selected plan references unknown candidate action: {candidate_id}")
    executed = record.get("executed_action")
    if isinstance(executed, dict):
        candidate_id = executed.get("candidate_action_id")
        if candidate_id is not None and candidate_id not in candidate_set:
            errors.append("executed action references an unknown candidate action")
    return errors


def validate_episode_order(records: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    by_episode: dict[str, list[int]] = {}
    for record in records:
        episode = record.get("episode_id")
        step = record.get("step_index")
        if isinstance(episode, str) and isinstance(step, int):
            by_episode.setdefault(episode, []).append(step)
    for episode, steps in by_episode.items():
        if len(steps) != len(set(steps)):
            errors.append(f"episode {episode} has duplicate step indexes")
        if sorted(steps) != list(range(min(steps), max(steps) + 1)):
            errors.append(f"episode {episode} has a non-contiguous step sequence: {sorted(steps)}")
    return errors


def _stable_locator(locator: str) -> bool:
    parsed = urlparse(locator)
    return (
        parsed.scheme in {"https", "s3"}
        and not parsed.username
        and not parsed.password
        and not parsed.query
    )


def validate_manifests(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    all_ids: set[str] = set()
    for relative in MANIFEST_FILES:
        try:
            manifest = load_yaml(root / relative)
        except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{relative}: {exc}")
            continue
        errors.extend(
            f"{relative}: {error}"
            for error in validate_instance(manifest, root / "schemas/manifest.schema.json")
        )
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            errors.append(f"{relative}: entries must be a list")
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"{relative}[{index}]: entry must be a mapping")
                continue
            missing = sorted(MANIFEST_REQUIRED_FIELDS - entry.keys())
            if missing:
                errors.append(f"{relative}[{index}]: missing fields {missing}")
            entry_id = entry.get("id")
            if not isinstance(entry_id, str):
                errors.append(f"{relative}[{index}]: id must be a string")
            elif entry_id in all_ids:
                errors.append(f"duplicate manifest ID across files: {entry_id}")
            else:
                all_ids.add(entry_id)
            digest = entry.get("sha256")
            if digest is not None and (
                not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                errors.append(f"{entry_id}: sha256 must be null or 64 lowercase hex characters")
            commit = entry.get("commit")
            if commit is not None and (
                not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None
            ):
                errors.append(f"{entry_id}: commit must be null or 40 lowercase hex characters")
            if entry.get("verification_status") == "content-hash-verified" and digest is None:
                errors.append(f"{entry_id}: content-hash-verified requires sha256")
            locator = entry.get("storage_uri")
            if not isinstance(locator, str) or not _stable_locator(locator):
                errors.append(
                    f"{entry_id}: storage_uri must be a stable, credential-free https/s3 locator"
                )
    try:
        artifacts = load_yaml(root / "manifests/artifacts.yaml").get("entries")
        if not isinstance(artifacts, list):
            errors.append("manifests/artifacts.yaml: entries must be a list")
        else:
            for index, artifact in enumerate(artifacts):
                if not isinstance(artifact, dict):
                    errors.append(f"artifact {index}: must be a mapping")
                    continue
                errors.extend(
                    f"artifact {index}: {error}"
                    for error in validate_instance(artifact, root / "schemas/artifact.schema.json")
                )
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"manifests/artifacts.yaml: {exc}")
    try:
        compute_path = "manifests/compute.yaml"
        compute = load_yaml(root / compute_path)
        errors.extend(
            f"{compute_path}: {error}"
            for error in validate_instance(compute, root / "schemas/compute.schema.json")
        )
        summary = compute.get("phase_zero_summary")
        if not isinstance(summary, dict):
            errors.append("manifests/compute.yaml: phase_zero_summary must be a mapping")
        else:
            expected_zero = {
                "paid_compute_authorized": False,
                "cloud_mutations": 0,
                "accelerator_hours": 0,
                "cost_usd": 0,
                "prototype_runs": 0,
                "benchmark_runs": 0,
                "training_runs": 0,
            }
            for key, value in expected_zero.items():
                if summary.get(key) != value:
                    errors.append(f"manifests/compute.yaml: Phase 0 {key} must be {value!r}")
        registry = load_yaml(root / "experiments/registry.yaml")
        registered_ids = {
            entry.get("experiment_id")
            for entry in registry.get("experiments", [])
            if isinstance(entry, dict) and isinstance(entry.get("experiment_id"), str)
        }
        compute_entries = compute.get("entries")
        seen_compute_ids: set[str] = set()
        if isinstance(compute_entries, list):
            for index, entry in enumerate(compute_entries):
                if not isinstance(entry, dict):
                    continue
                compute_id = entry.get("id")
                if isinstance(compute_id, str):
                    if compute_id in seen_compute_ids:
                        errors.append(f"manifests/compute.yaml: duplicate compute ID {compute_id}")
                    seen_compute_ids.add(compute_id)
                experiment_id = entry.get("experiment_id")
                if isinstance(experiment_id, str) and experiment_id not in registered_ids:
                    errors.append(
                        "manifests/compute.yaml: "
                        f"entry {index} references unregistered experiment {experiment_id}"
                    )
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"manifests/compute.yaml: {exc}")
    return errors


def _repository_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = [root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    return [path for path in paths if path.exists()]


def validate_hygiene(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        files = _repository_files(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"cannot enumerate repository files: {exc}"]
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden large-artifact extension in repository: {relative}")
        if path.is_file() and path.stat().st_size > MAX_TRACKED_SOURCE_BYTES:
            errors.append(f"repository source exceeds 5 MiB ceiling: {relative}")
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible {label} in {relative}")
    ignore_text = (root / ".gitignore").read_text(encoding="utf-8")
    for required in (".env", "checkpoints/", "models/", "artifacts/", "data/", "traces/", "_site/"):
        if required not in ignore_text:
            errors.append(f".gitignore must cover {required}")
    return errors


def validate_markdown_links(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for path in _repository_files(root):
        if path.suffix.lower() not in {".md", ".qmd"}:
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().strip("<>").split("#", maxsplit=1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:", "/")):
                continue
            resolved = (path.parent / target).resolve()
            if root.resolve() not in resolved.parents and resolved != root.resolve():
                errors.append(f"{path.relative_to(root)}: link escapes repository: {target}")
            elif not resolved.exists():
                errors.append(f"{path.relative_to(root)}: broken local link: {target}")
    return errors


def _t09_git_blob_sha256(root: Path, revision: str, relative: str) -> str | None:
    """Return a historical Git blob digest without changing the checkout."""

    try:
        raw = subprocess.run(
            ["git", "-C", str(root), "show", f"{revision}:{relative}"],
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None
    return hashlib.sha256(raw).hexdigest()


def _validate_t09_successor_plan(
    root: Path,
    *,
    version: str,
    historical_source_bindings: bool,
) -> list[str]:
    """Validate one immutable T09 successor package and its byte closure."""

    label = f"T09 {version}"
    plan_id = f"PLAN-EXP0001-PILOT-{version}"
    slug = version.lower()
    errors: list[str] = []
    plan_path = (
        root
        / "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals"
        / f"{plan_id}.yaml"
    )
    schema_path = root / f"schemas/t09-{slug}-plan.schema.json"
    if not plan_path.is_file() or not schema_path.is_file():
        return [f"{label} plan or schema is missing"]
    plan = load_yaml(plan_path)
    errors.extend(f"{label} plan: {error}" for error in validate_instance(plan, schema_path))
    bindings = plan.get("implementation_bindings")
    if not isinstance(bindings, dict):
        return [*errors, f"{label} implementation bindings are malformed"]

    required_groups = [
        "provider_accounting",
        "offline_refinalization",
        "early_cleanup",
        "execution_plane",
    ]
    if version in {"V11", "V12", "V13", "V14"}:
        required_groups.insert(3, "owned_container_publication")
    if version in {"V12", "V13", "V14"}:
        required_groups.insert(4, "model_metadata_receipt")
    stopped_disposition_group = {
        "V13": "v12_stopped_disposition",
        "V14": "v13_stopped_disposition",
    }.get(version)
    if stopped_disposition_group is not None:
        required_groups.insert(5, stopped_disposition_group)
    groups = {name: bindings.get(name) for name in required_groups}
    if not all(isinstance(value, dict) for value in groups.values()):
        return [*errors, f"{label} implementation binding groups are malformed"]

    accounting = groups["provider_accounting"]
    refinalization = groups["offline_refinalization"]
    cleanup = groups["early_cleanup"]
    execution = groups["execution_plane"]
    model_metadata = groups.get("model_metadata_receipt")
    stopped_disposition = (
        groups.get(stopped_disposition_group) if stopped_disposition_group is not None else None
    )
    assert isinstance(accounting, dict)
    assert isinstance(refinalization, dict)
    assert isinstance(cleanup, dict)
    assert isinstance(execution, dict)
    if version in {"V12", "V13", "V14"}:
        assert isinstance(model_metadata, dict)
    if stopped_disposition_group is not None:
        assert isinstance(stopped_disposition, dict)

    source_ancestors: list[str] = []
    runtime_identity_relative = execution.get("runtime_identity_path")
    if historical_source_bindings and isinstance(runtime_identity_relative, str):
        identity_path = Path(runtime_identity_relative)
        if not identity_path.is_absolute() and ".." not in identity_path.parts:
            identity_target = root / identity_path
            if identity_target.is_file():
                identity = load_json(identity_target)
                instrumentation = identity.get("repository_instrumentation")
                candidate = (
                    instrumentation.get("reviewed_implementation_ancestor")
                    if isinstance(instrumentation, dict)
                    else None
                )
                if isinstance(candidate, str) and re.fullmatch(r"[0-9a-f]{40}", candidate):
                    source_ancestors.append(candidate)
    if historical_source_bindings and version == "V12":
        stopped_path = (
            root / "experiments/EXP-0001-sira-simulative-vs-reactive/"
            "T09_V12_STOPPED_DISPOSITION.json"
        )
        if stopped_path.is_file():
            stopped = load_json(stopped_path)
            merged_package = stopped.get("merged_package_commit")
            if isinstance(merged_package, str) and re.fullmatch(r"[0-9a-f]{40}", merged_package):
                source_ancestors.append(merged_package)
    if historical_source_bindings and not source_ancestors:
        errors.append(f"{label} historical source ancestor is malformed")

    specifications: list[tuple[Mapping[str, Any], str, str]] = [
        (accounting, "path", "sha256"),
        (accounting, "regression_path", "regression_sha256"),
        (refinalization, "finalizer_projection_path", "finalizer_projection_sha256"),
        (refinalization, "evaluator_driver_path", "evaluator_driver_sha256"),
        (refinalization, "selector_path", "selector_sha256"),
        (refinalization, "receipt_schema_path", "receipt_schema_sha256"),
        (cleanup, "implementation_path", "implementation_sha256"),
        (cleanup, "provider_integration_path", "provider_integration_sha256"),
        (cleanup, "schema_path", "schema_sha256"),
        (execution, "pilot_library_path", "pilot_library_sha256"),
        (execution, "campaign_lifecycle_path", "campaign_lifecycle_sha256"),
        (execution, "provider_path", "provider_sha256"),
        (execution, "provider_contracts_path", "provider_contracts_sha256"),
        (execution, "remote_runner_path", "remote_runner_sha256"),
        (execution, "command_generator_path", "command_generator_sha256"),
        (execution, "runtime_profile_path", "runtime_profile_sha256"),
        (execution, "execution_contract_path", "execution_contract_sha256"),
        (execution, "command_manifests_path", "command_manifests_sha256"),
        (execution, "runtime_identity_path", "runtime_identity_sha256"),
        (execution, "execution_schema_path", "execution_schema_sha256"),
    ]
    if version in {"V12", "V13", "V14"}:
        assert isinstance(model_metadata, dict)
        specifications.extend(
            [
                (execution, "runtime_adaptation_path", "runtime_adaptation_sha256"),
                (model_metadata, "implementation_path", "implementation_sha256"),
                (model_metadata, "schema_path", "schema_sha256"),
                (
                    model_metadata,
                    "public_price_contract_path",
                    "public_price_contract_sha256",
                ),
                (
                    model_metadata,
                    "public_deprecation_observation_path",
                    "public_deprecation_observation_sha256",
                ),
            ]
        )
    if version in {"V13", "V14"}:
        specifications.extend(
            [
                (execution, "preflight_path", "preflight_sha256"),
                (
                    execution,
                    "local_finalizer_qualification_path",
                    "local_finalizer_qualification_sha256",
                ),
            ]
        )
    if version == "V14":
        specifications.append(
            (
                cleanup,
                "export_handoff_schema_path",
                "export_handoff_schema_sha256",
            )
        )
    if isinstance(stopped_disposition, dict):
        specifications.append((stopped_disposition, "path", "sha256"))
    publication = groups.get("owned_container_publication")
    if isinstance(publication, dict):
        specifications.extend(
            [
                (publication, "reader_path", "reader_sha256"),
                (publication, "regression_path", "regression_sha256"),
            ]
        )
    for binding, path_field, hash_field in specifications:
        relative = binding.get(path_field)
        expected = binding.get(hash_field)
        if not isinstance(relative, str) or not isinstance(expected, str):
            errors.append(f"{label} {path_field} binding is malformed")
            continue
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            errors.append(f"{label} {path_field} binding is unsafe")
            continue
        target = root / path
        if not target.is_file():
            errors.append(f"{label} {path_field} binding is missing")
            continue
        if hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        historical_match = path.suffix == ".py" and any(
            _t09_git_blob_sha256(root, source_ancestor, relative) == expected
            for source_ancestor in source_ancestors
        )
        if not historical_match:
            errors.append(f"{label} {path_field} binding drifted")
    if isinstance(stopped_disposition, dict):
        relative = stopped_disposition.get("path")
        expected_size = stopped_disposition.get("size_bytes")
        if isinstance(relative, str) and isinstance(expected_size, int):
            stopped_target = root / relative
            if stopped_target.is_file() and stopped_target.stat().st_size != expected_size:
                errors.append(f"{label} stopped disposition byte size drifted")

    condition_plans = execution.get("condition_plans")
    if not isinstance(condition_plans, list) or len(condition_plans) != 4:
        errors.append(f"{label} condition plan bindings are malformed")
    else:
        for item in condition_plans:
            if not isinstance(item, dict):
                errors.append(f"{label} condition plan binding is malformed")
                continue
            relative = item.get("path")
            expected = item.get("sha256")
            if not isinstance(relative, str) or not isinstance(expected, str):
                errors.append(f"{label} condition plan binding is malformed")
                continue
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"{label} condition plan binding is unsafe")
                continue
            target = root / path
            if not target.is_file():
                errors.append(f"{label} condition plan binding is missing")
            elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                errors.append(f"{label} condition plan binding drifted")

    runtime_profile_relative = execution.get("runtime_profile_path")
    if isinstance(runtime_profile_relative, str):
        runtime_profile_target = root / runtime_profile_relative
        if runtime_profile_target.is_file():
            runtime_profile = load_yaml(runtime_profile_target)
            errors.extend(
                f"{label} runtime profile: {error}"
                for error in validate_instance(
                    runtime_profile, root / "schemas/run-profile.schema.json"
                )
            )
            errors.extend(
                f"{label} runtime profile: {error}"
                for error in validate_run_profile_readiness(runtime_profile)
            )
            if version in {"V12", "V13", "V14"}:
                lifecycle = runtime_profile.get("provider_lifecycle")
                expected_metadata_lifecycle = {
                    "model_metadata_request_count_total": 1,
                    "model_metadata_request_location": ("local-control-plane-before-lambda-launch"),
                    "provider_launch_model_metadata_request_count": 0,
                    "host_runtime_model_metadata_request_count": 0,
                    "model_metadata_receipt_required": True,
                    "model_metadata_receipt_replay_allowed": False,
                    "immutable_model_unavailable_disposition": (
                        "stop-before-lambda-launch-zero-lambda-cost"
                    ),
                }
                if not isinstance(lifecycle, dict) or any(
                    lifecycle.get(field) != expected
                    for field, expected in expected_metadata_lifecycle.items()
                ):
                    errors.append(f"{label} runtime profile metadata receipt lifecycle drifted")
            profile_sha256 = hashlib.sha256(runtime_profile_target.read_bytes()).hexdigest()
            environment_sha256 = (
                hashlib.sha256((root / runtime_identity_relative).read_bytes()).hexdigest()
                if isinstance(runtime_identity_relative, str)
                and (root / runtime_identity_relative).is_file()
                else None
            )
            if isinstance(condition_plans, list):
                for item in condition_plans:
                    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                        continue
                    condition_target = root / item["path"]
                    if not condition_target.is_file():
                        continue
                    condition = load_yaml(condition_target)
                    errors.extend(
                        f"{label} condition plan: {error}"
                        for error in validate_instance(
                            condition, root / "schemas/run-plan.schema.json"
                        )
                    )
                    sources = condition.get("sources")
                    if (
                        condition.get("profile_plan_id") != plan_id
                        or condition.get("profile_sha256") != profile_sha256
                        or not isinstance(sources, dict)
                        or sources.get("environment_sha256") != environment_sha256
                    ):
                        errors.append(f"{label} condition/profile identity binding drifted")

    execution_contract_path = execution.get("execution_contract_path")
    execution_schema_path = execution.get("execution_schema_path")
    command_manifests_path = execution.get("command_manifests_path")
    if all(
        isinstance(value, str)
        for value in (execution_contract_path, execution_schema_path, command_manifests_path)
    ):
        assert isinstance(execution_contract_path, str)
        assert isinstance(execution_schema_path, str)
        assert isinstance(command_manifests_path, str)
        contract_target = root / execution_contract_path
        schema_target = root / execution_schema_path
        command_target = root / command_manifests_path
        if contract_target.is_file() and schema_target.is_file():
            contract = load_json(contract_target)
            errors.extend(
                f"{label} execution contract: {error}"
                for error in validate_instance(contract, schema_target)
            )
            if (
                contract.get("plan_id") != plan_id
                or contract.get("authorized") is not False
                or contract.get("authorization_reference") is not None
                or contract.get("execution_eligibility")
                != "blocked-until-fresh-category-3-authorization"
            ):
                errors.append(f"{label} execution contract is not statically unauthorized")
            identities = plan.get("identities")
            attempts = contract.get("attempts")
            if isinstance(identities, dict) and isinstance(attempts, list):
                expected_order = identities.get("attempt_order")
                observed_order = [
                    attempt.get("run_id") for attempt in attempts if isinstance(attempt, dict)
                ]
                if observed_order != expected_order:
                    errors.append(f"{label} execution attempt order drifted from the plan")
            if version in {"V11", "V12", "V13", "V14"}:
                lifecycle = contract.get("provider_lifecycle")
                if not isinstance(lifecycle, dict) or (
                    lifecycle.get("model_metadata_before_lambda_launch") is not True
                    or lifecycle.get("model_metadata_request_count") != 1
                    or lifecycle.get("model_metadata_snapshot") != "gpt-4o-2024-11-20"
                    or lifecycle.get("model_substitution_allowed") is not False
                    or lifecycle.get("immutable_model_unavailable_disposition")
                    != "stop-before-lambda-launch-zero-lambda-cost"
                ):
                    errors.append(f"{label} metadata-before-Lambda contract drifted")
                if (
                    version in {"V12", "V13", "V14"}
                    and isinstance(lifecycle, dict)
                    and (
                        lifecycle.get("model_metadata_request_count_total") != 1
                        or lifecycle.get("model_metadata_request_location")
                        != "local-control-plane-before-lambda-launch"
                        or lifecycle.get("provider_launch_model_metadata_request_count") != 0
                        or lifecycle.get("host_runtime_model_metadata_request_count") != 0
                        or lifecycle.get("model_metadata_receipt_required") is not True
                        or lifecycle.get("model_metadata_receipt_replay_allowed") is not False
                    )
                ):
                    errors.append(f"{label} receipt handoff contract drifted")
        if command_target.is_file():
            commands = load_json(command_target)
            if commands.get("plan_id") != plan_id or commands.get(
                "execution_contract_sha256"
            ) != execution.get("execution_contract_sha256"):
                errors.append(f"{label} command manifest contract binding drifted")
            pair_diffs = commands.get("pair_diffs")
            if (
                not isinstance(pair_diffs, list)
                or len(pair_diffs) != 2
                or any(
                    not isinstance(pair, dict) or pair.get("valid") is not True
                    for pair in pair_diffs
                )
            ):
                errors.append(f"{label} command pair diff is invalid")
            if version in {"V11", "V12", "V13", "V14"}:
                reviewed_ancestor = bindings.get("reviewed_implementation_ancestor")
                if commands.get("reviewed_implementation_ancestor") != reviewed_ancestor:
                    errors.append(f"{label} command manifest source ancestor drifted")
    else:
        errors.append(f"{label} execution control paths are malformed")

    if version in {"V11", "V12", "V13", "V14"} and isinstance(runtime_identity_relative, str):
        identity_target = root / runtime_identity_relative
        if identity_target.is_file():
            identity = load_json(identity_target)
            instrumentation = identity.get("repository_instrumentation")
            reviewed_ancestor = bindings.get("reviewed_implementation_ancestor")
            if (
                not isinstance(instrumentation, dict)
                or instrumentation.get("reviewed_implementation_ancestor") != reviewed_ancestor
            ):
                errors.append(f"{label} runtime identity source ancestor drifted")

    budget = plan.get("budget_contract")
    if not isinstance(budget, dict):
        errors.append(f"{label} budget contract is malformed")
    else:
        try:
            prior_upper = Decimal(str(budget.get("prior_t09_conservative_upper_bound_usd")))
            nominal_new_total = Decimal(str(budget.get("maximum_new_total_cost_usd")))
            cumulative_cap = Decimal(str(budget.get("cumulative_t09_cost_cap_usd")))
            effective_new_total = (
                Decimal(
                    str(budget.get("effective_maximum_new_total_cost_under_cumulative_cap_usd"))
                )
                if version in {"V11", "V12", "V13", "V14"}
                else nominal_new_total
            )
        except InvalidOperation:
            errors.append(f"{label} budget values are malformed")
        else:
            if effective_new_total > nominal_new_total:
                errors.append(f"{label} effective budget exceeds the nominal cap")
            if prior_upper + effective_new_total > cumulative_cap:
                errors.append(f"{label} conservative budget exceeds the cumulative cap")
    return errors


def validate_t09_v10_plan(root: Path = ROOT) -> list[str]:
    """Validate V10 as immutable historical operational evidence."""

    return _validate_t09_successor_plan(
        root,
        version="V10",
        historical_source_bindings=True,
    )


def validate_t09_v11_plan(root: Path = ROOT) -> list[str]:
    """Validate the stopped V11 proposal against its reviewed source ancestor."""

    return _validate_t09_successor_plan(
        root,
        version="V11",
        historical_source_bindings=True,
    )


def validate_t09_v12_plan(root: Path = ROOT) -> list[str]:
    """Validate the stopped V12 package against its immutable source ancestor."""

    return _validate_t09_successor_plan(
        root,
        version="V12",
        historical_source_bindings=True,
    )


def validate_t09_v13_plan(root: Path = ROOT) -> list[str]:
    """Validate the stopped V13 package against its immutable source ancestor."""

    return _validate_t09_successor_plan(
        root,
        version="V13",
        historical_source_bindings=True,
    )


def validate_t09_v14_plan(root: Path = ROOT) -> list[str]:
    """Validate the unauthorized V14 cleanup-repair successor package."""

    return _validate_t09_successor_plan(
        root,
        version="V14",
        historical_source_bindings=False,
    )


def _load_workflow(path: Path) -> Mapping[str, Any]:
    data = load_yaml(path)
    return data


def validate_workflows(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    workflow_dir = root / ".github/workflows"
    for path in sorted(workflow_dir.glob("*.yml")):
        try:
            workflow = _load_workflow(path)
        except (OSError, TypeError, DuplicateKeyError, yaml.YAMLError) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
            continue
        for required in ("name", "jobs"):
            if required not in workflow:
                errors.append(f"{path.relative_to(root)}: missing top-level {required}")
        if "on" not in workflow:
            errors.append(f"{path.relative_to(root)}: missing top-level on trigger")
        jobs = workflow.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                errors.append(f"{path.relative_to(root)}: job {job_name} must be a mapping")
                continue
            steps = job.get("steps", [])
            if not isinstance(steps, list):
                errors.append(f"{path.relative_to(root)}: job {job_name} steps must be a list")
                continue
            for index, step in enumerate(steps):
                if not isinstance(step, dict):
                    errors.append(
                        f"{path.relative_to(root)}: job {job_name} step {index} must be a mapping"
                    )
                    continue
                uses = step.get("uses")
                if (
                    isinstance(uses, str)
                    and not uses.startswith("./")
                    and ACTION_PIN.fullmatch(uses) is None
                ):
                    errors.append(
                        f"{path.relative_to(root)}: action must be pinned to a "
                        f"40-character SHA: {uses}"
                    )
    publish = workflow_dir / "publish-notebook.yml"
    if publish.exists():
        text = publish.read_text(encoding="utf-8")
        if "pull_request:" in text and "deploy-pages" in text:
            errors.append("publish workflow must not deploy from pull_request events")
        for required in ("actions/upload-pages-artifact", "actions/deploy-pages", "make check"):
            if required not in text:
                errors.append(f"publish workflow missing required contract: {required}")
    return errors


def validate_site_output(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    site = root / "_site"
    expected = (
        "index.html",
        "generated/status.html",
        "generated/experiments.html",
        "generated/decisions.html",
        "generated/falsification.html",
        "failures/index.html",
        "weekly/index.html",
    )
    for relative in expected:
        if not (site / relative).is_file():
            errors.append(f"site output missing: {relative}")
    for html_path in sorted(site.rglob("*.html")) if site.is_dir() else []:
        parser = _LinkCollector()
        parser.feed(html_path.read_text(encoding="utf-8"))
        for raw_target in parser.targets:
            parsed = urlparse(raw_target)
            if parsed.scheme or raw_target.startswith(("#", "//")) or not parsed.path:
                continue
            path_text = unquote(parsed.path)
            if path_text.startswith("/"):
                candidate = site / path_text.lstrip("/")
            else:
                candidate = html_path.parent / path_text
            candidate = candidate.resolve()
            if candidate.is_dir():
                candidate = candidate / "index.html"
            if not candidate.exists():
                errors.append(
                    f"{html_path.relative_to(site)}: broken rendered target: {raw_target}"
                )
    return errors


def run_all(root: Path = ROOT) -> list[str]:
    validators: Iterable[tuple[str, Any]] = (
        ("required paths", validate_required_paths),
        ("plan lifecycle", validate_plan_lifecycle),
        ("project state", validate_project_state),
        ("schemas", validate_schema_documents),
        ("experiments", validate_experiment_registry),
        ("experiment run profiles", validate_experiment_run_profiles),
        ("EXP-0001 contract", validate_exp0001_contract),
        ("T09 V10 plan", validate_t09_v10_plan),
        ("T09 V11 plan", validate_t09_v11_plan),
        ("T09 V12 plan", validate_t09_v12_plan),
        ("T09 V13 plan", validate_t09_v13_plan),
        ("T09 V14 plan", validate_t09_v14_plan),
        ("manifests", validate_manifests),
        ("workflows", validate_workflows),
        ("repository hygiene", validate_hygiene),
        ("documentation links", validate_markdown_links),
    )
    errors: list[str] = []
    try:
        build_site_data(root)
    except Exception as exc:
        errors.append(f"[site data] generation failed: {type(exc).__name__}: {exc}")
    for label, validator in validators:
        try:
            errors.extend(f"[{label}] {error}" for error in validator(root))
        except Exception as exc:  # preserve actionable output instead of an opaque validator crash
            errors.append(f"[{label}] validator crashed: {type(exc).__name__}: {exc}")
    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("all", "site"), help="validation group to run")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    root = args.root.resolve()
    errors = run_all(root) if args.command == "all" else validate_site_output(root)
    if errors:
        print("GIC Lab validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print("GIC Lab validation passed.")


if __name__ == "__main__":
    main()
