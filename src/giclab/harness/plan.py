"""Run-plan schema validation, loading, and typed construction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from giclab.registry import load_json, load_yaml

from .models import (
    SCHEMA_VERSION,
    ArtifactPolicy,
    ExecutionAuthorization,
    ExecutionBackend,
    ExecutionContract,
    PairingIdentity,
    RunBudget,
    RunIdentity,
    RunPlan,
    RunProfile,
    RunTask,
    SourceVersions,
    TaskSourceKind,
    WorkloadKind,
)

RUN_PLAN_SCHEMA = "schemas/run-plan.schema.json"


class RunPlanError(ValueError):
    """Raised when a run-plan document violates its schema or typed contract."""


def _schema_errors(data: Mapping[str, Any], schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RunPlanError(f"{label} must be an object with string keys")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise RunPlanError(f"{label} must be a string")
    return value


def _optional_string(value: object, label: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise RunPlanError(f"{label} must be a string or null")


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise RunPlanError(f"{label} must be an integer")
    return value


def _optional_integer(value: object, label: str) -> int | None:
    if value is None:
        return None
    return _integer(value, label)


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RunPlanError(f"{label} must be a number")
    return float(value)


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise RunPlanError(f"{label} must be a boolean")
    return value


def run_plan_from_mapping(data: Mapping[str, Any]) -> RunPlan:
    """Construct the typed run plan after schema validation."""

    execution_data = _mapping(data.get("execution"), "execution")
    authorization_data = _mapping(execution_data.get("authorization"), "execution.authorization")
    source_data = _mapping(data.get("sources"), "sources")
    budget_data = _mapping(data.get("budget"), "budget")
    artifact_data = _mapping(data.get("artifacts"), "artifacts")
    identity = RunIdentity(
        experiment_id=_string(data.get("experiment_id"), "experiment_id"),
        run_id=_string(data.get("run_id"), "run_id"),
        condition=_string(data.get("condition"), "condition"),
        attempt=_integer(data.get("attempt"), "attempt"),
        seed=_optional_integer(data.get("seed"), "seed"),
    )
    authorization = ExecutionAuthorization(
        authorized=_boolean(authorization_data.get("authorized"), "execution.authorized"),
        authorization_reference=_optional_string(
            authorization_data.get("authorization_reference"),
            "execution.authorization_reference",
        ),
        command_sha256=_optional_string(
            authorization_data.get("command_sha256"),
            "execution.command_sha256",
        ),
    )
    execution = ExecutionContract(
        backend=ExecutionBackend(_string(execution_data.get("backend"), "execution.backend")),
        workload=WorkloadKind(_string(execution_data.get("workload"), "execution.workload")),
        authorization=authorization,
    )
    sources = SourceVersions(
        giclab_commit=_string(source_data.get("giclab_commit"), "sources.giclab_commit"),
        upstream_source_id=_string(
            source_data.get("upstream_source_id"), "sources.upstream_source_id"
        ),
        upstream_commit=_string(source_data.get("upstream_commit"), "sources.upstream_commit"),
        protocol_sha256=_string(source_data.get("protocol_sha256"), "sources.protocol_sha256"),
        config_sha256=_string(source_data.get("config_sha256"), "sources.config_sha256"),
        model_revision=_optional_string(
            source_data.get("model_revision"), "sources.model_revision"
        ),
        dataset_revision=_optional_string(
            source_data.get("dataset_revision"), "sources.dataset_revision"
        ),
        environment_sha256=_string(
            source_data.get("environment_sha256"), "sources.environment_sha256"
        ),
    )
    budget = RunBudget(
        max_wall_seconds=_integer(budget_data.get("max_wall_seconds"), "budget.max_wall_seconds"),
        max_cost_usd=_number(budget_data.get("max_cost_usd"), "budget.max_cost_usd"),
        max_gpu_hours=_number(budget_data.get("max_gpu_hours"), "budget.max_gpu_hours"),
        max_model_tokens=_optional_integer(
            budget_data.get("max_model_tokens"), "budget.max_model_tokens"
        ),
        max_tool_calls=_optional_integer(
            budget_data.get("max_tool_calls"), "budget.max_tool_calls"
        ),
        max_output_bytes=_integer(budget_data.get("max_output_bytes"), "budget.max_output_bytes"),
    )
    artifacts = ArtifactPolicy(
        root=Path(_string(artifact_data.get("root"), "artifacts.root")),
        retain_raw=_boolean(artifact_data.get("retain_raw"), "artifacts.retain_raw"),
    )
    task: RunTask | None = None
    pairing: PairingIdentity | None = None
    task_value = data.get("task")
    pairing_value = data.get("pairing")
    if task_value is not None or pairing_value is not None:
        task_data = _mapping(task_value, "task")
        pairing_data = _mapping(pairing_value, "pairing")
        task = RunTask(
            task_id=_string(task_data.get("task_id"), "task.task_id"),
            source_kind=TaskSourceKind(_string(task_data.get("source_kind"), "task.source_kind")),
            query=_optional_string(task_data.get("query"), "task.query"),
            dataset_id=_optional_string(task_data.get("dataset_id"), "task.dataset_id"),
            dataset_revision=_optional_string(
                task_data.get("dataset_revision"), "task.dataset_revision"
            ),
            start_idx=_optional_integer(task_data.get("start_idx"), "task.start_idx"),
            end_idx=_optional_integer(task_data.get("end_idx"), "task.end_idx"),
        )
        pairing = PairingIdentity(
            pair_id=_string(pairing_data.get("pair_id"), "pairing.pair_id"),
            order_index=_integer(pairing_data.get("order_index"), "pairing.order_index"),
        )
    return RunPlan(
        identity=identity,
        profile=RunProfile(_string(data.get("profile"), "profile")),
        profile_plan_id=_optional_string(data.get("profile_plan_id"), "profile_plan_id"),
        profile_sha256=_optional_string(data.get("profile_sha256"), "profile_sha256"),
        interpretation_allowed=_boolean(
            data.get("interpretation_allowed"), "interpretation_allowed"
        ),
        execution=execution,
        sources=sources,
        budget=budget,
        artifacts=artifacts,
        task=task,
        pairing=pairing,
    )


def run_plan_document(plan: RunPlan) -> dict[str, Any]:
    """Return the canonical schema-valid representation retained with every run."""

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": plan.identity.experiment_id,
        "run_id": plan.identity.run_id,
        "profile": plan.profile.value,
        "condition": plan.identity.condition,
        "attempt": plan.identity.attempt,
        "seed": plan.identity.seed,
        "interpretation_allowed": plan.interpretation_allowed,
        "execution": {
            "backend": plan.execution.backend.value,
            "workload": plan.execution.workload.value,
            "authorization": {
                "authorized": plan.execution.authorization.authorized,
                "authorization_reference": (plan.execution.authorization.authorization_reference),
                "command_sha256": plan.execution.authorization.command_sha256,
            },
        },
        "sources": {
            "giclab_commit": plan.sources.giclab_commit,
            "upstream_source_id": plan.sources.upstream_source_id,
            "upstream_commit": plan.sources.upstream_commit,
            "protocol_sha256": plan.sources.protocol_sha256,
            "config_sha256": plan.sources.config_sha256,
            "model_revision": plan.sources.model_revision,
            "dataset_revision": plan.sources.dataset_revision,
            "environment_sha256": plan.sources.environment_sha256,
        },
        "budget": {
            "max_wall_seconds": plan.budget.max_wall_seconds,
            "max_cost_usd": plan.budget.max_cost_usd,
            "max_gpu_hours": plan.budget.max_gpu_hours,
            "max_model_tokens": plan.budget.max_model_tokens,
            "max_tool_calls": plan.budget.max_tool_calls,
            "max_output_bytes": plan.budget.max_output_bytes,
        },
        "artifacts": {
            "root": plan.artifacts.root.as_posix(),
            "retain_raw": plan.artifacts.retain_raw,
        },
    }
    if plan.profile_plan_id is not None and plan.profile_sha256 is not None:
        document["profile_plan_id"] = plan.profile_plan_id
        document["profile_sha256"] = plan.profile_sha256
    if plan.task is not None and plan.pairing is not None:
        document["task"] = {
            "task_id": plan.task.task_id,
            "source_kind": plan.task.source_kind.value,
            "query": plan.task.query,
            "dataset_id": plan.task.dataset_id,
            "dataset_revision": plan.task.dataset_revision,
            "start_idx": plan.task.start_idx,
            "end_idx": plan.task.end_idx,
        }
        document["pairing"] = {
            "pair_id": plan.pairing.pair_id,
            "order_index": plan.pairing.order_index,
        }
    return document


def run_plan_authorization_sha256(plan: RunPlan) -> str:
    """Hash every child-plan field authorized by a parent, excluding its parent hash.

    Excluding ``profile_sha256`` avoids a circular digest: the parent profile binds this
    child fingerprint, while the child independently binds the complete parent file.
    """

    document = run_plan_document(plan)
    document.pop("profile_sha256", None)
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_run_plan_data(
    data: Mapping[str, Any],
    *,
    schema_root: Path,
) -> list[str]:
    """Return all schema errors followed by any typed semantic error."""

    errors = _schema_errors(data, schema_root / RUN_PLAN_SCHEMA)
    if errors:
        return errors
    try:
        run_plan_from_mapping(data)
    except (RunPlanError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def load_run_plan(path: Path, *, schema_root: Path) -> RunPlan:
    """Load JSON/YAML with duplicate-key rejection and return a typed run plan."""

    try:
        if path.suffix.lower() == ".json":
            data = load_json(path)
        elif path.suffix.lower() in {".yaml", ".yml"}:
            data = load_yaml(path)
        else:
            raise RunPlanError("run plan must use .json, .yaml, or .yml")
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise RunPlanError(f"cannot load run plan {path}: {exc}") from exc
    errors = validate_run_plan_data(data, schema_root=schema_root)
    if errors:
        joined = "\n- ".join(errors)
        raise RunPlanError(f"run plan validation failed:\n- {joined}")
    return run_plan_from_mapping(data)
