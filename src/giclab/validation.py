"""Offline validation for GIC Lab schemas, registries, provenance, and hygiene."""

from __future__ import annotations

import argparse
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
    return _format_validation_errors(validator, instance)


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
    for path in discover_plan_paths(root):
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
    if phase_number is not None and phase_number.is_finite() and phase_number < 1:
        for key in authorization_fields:
            if state.get(key) is not False:
                errors.append(f"docs/PROJECT_STATE.yaml: {key} must be false before Phase 1")

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
            if profile_path.parent.resolve() != profiles_root:
                errors.append(f"{experiment_id}: run profile must be inside its run-plans root")
                continue
            if not profile_path.is_file():
                errors.append(f"{experiment_id}: missing run profile {profile_relative}")
                continue
            profile = load_yaml(profile_path)
            label = profile_path.relative_to(root)
            errors.extend(
                f"{label}: {error}"
                for error in validate_instance(profile, root / "schemas/run-profile.schema.json")
            )
            profile_name = profile.get("profile")
            if profile.get("experiment_id") != experiment_id:
                errors.append(f"{label}: experiment ID mismatch")
            if profile_name != profile_path.stem:
                errors.append(f"{label}: profile/name mismatch")
            execution = profile.get("execution")
            if not isinstance(execution, dict) or execution.get("authorized") is not False:
                errors.append(f"{label}: current repository profile must remain unauthorized")
            condition_relatives = profile.get("condition_plan_paths", [])
            sampling = profile.get("sampling", {})
            profile_model = profile.get("model", {})
            if not isinstance(condition_relatives, list) or not isinstance(sampling, dict):
                continue
            condition_records: dict[Path, Mapping[str, Any]] = {}
            condition_names: list[str] = []
            condition_cost = Decimal(0)
            condition_tokens = 0
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
                if (
                    not isinstance(authorization, dict)
                    or authorization.get("authorized") is not False
                ):
                    errors.append(
                        f"{condition_label}: current repository plan must be unauthorized"
                    )
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
                    if isinstance(budget.get("max_model_tokens"), int):
                        condition_tokens += budget["max_model_tokens"]
                    if isinstance(budget.get("max_wall_seconds"), int):
                        condition_wall += budget["max_wall_seconds"]
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
                        for key in ("task", "budget", "seed", "attempt"):
                            if left.get(key) != right.get(key):
                                errors.append(f"{label}: matched pair drifts on {key}")
                        left_sources = left.get("sources")
                        right_sources = right.get("sources")
                        if isinstance(left_sources, dict) and isinstance(right_sources, dict):
                            for key in (
                                "giclab_commit",
                                "upstream_source_id",
                                "upstream_commit",
                                "protocol_sha256",
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
                                expected_source = (
                                    f"{task.get('dataset_id')}[{task.get('start_idx')}:"
                                    f"{task.get('end_idx')}]"
                                )
                                if task_source != expected_source:
                                    errors.append(f"{label}: pair task source/slice mismatch")
                            elif f"query={task.get('query')}" not in task_source:
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
                if profile_budget.get("max_wall_seconds") != condition_wall:
                    errors.append(f"{label}: profile/condition wall caps disagree")
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
        if actual_profile_paths != declared_profile_paths:
            errors.append(f"{experiment_id}: registry/profile declaration mismatch")
        actual_conditions = set((profiles_root / "conditions").glob("*.yaml"))
        if actual_conditions != referenced_conditions:
            errors.append(f"{experiment_id}: condition-plan reference mismatch")
    return errors


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
        if profile.get("execution") != {
            "authorized": False,
            "authorization_reference": None,
        }:
            errors.append(f"EXP-0001 {name}: current authorization must remain false")
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
