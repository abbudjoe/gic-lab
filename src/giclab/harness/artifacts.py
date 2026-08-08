"""Confined artifact storage, SHA-256 records, and directory validation."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

from giclab.registry import load_json, loads_json

from .events import read_events, validate_event_stream
from .models import (
    SCHEMA_VERSION,
    ArtifactPolicy,
    ArtifactRecord,
    CommandSpec,
    EventType,
    HarnessEvent,
    RunIdentity,
    RunPlan,
    command_from_document,
    command_sha256,
    thaw_json,
)
from .plan import run_plan_from_mapping, validate_run_plan_data

ARTIFACT_RECORDS = "artifact-records.jsonl"
EVENT_STREAM = "events.jsonl"
RUN_PLAN_RECORD = "run-plan.json"
COMMAND_RECORD = "command.json"


class ArtifactError(ValueError):
    """Raised when an artifact path or record violates evidence boundaries."""


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _resolve_within(path: Path, root: Path, *, strict: bool) -> Path:
    resolved_root = root.resolve(strict=strict)
    resolved = path.resolve(strict=strict)
    if not _is_within(resolved, resolved_root):
        raise ArtifactError(f"artifact path escapes configured workspace: {path}")
    return resolved


@dataclass(frozen=True, slots=True)
class ArtifactWorkspace:
    """Explicit owner of every path a harness run may create."""

    root: Path

    @classmethod
    def open(cls, root: Path, *, create: bool) -> ArtifactWorkspace:
        if create:
            root.mkdir(parents=True, exist_ok=True)
        if not root.exists() or not root.is_dir() or root.is_symlink():
            raise ArtifactError("artifact workspace must be a non-symlink directory")
        return cls(root=root.resolve(strict=True))

    def plan_root(self, policy: ArtifactPolicy, *, create: bool) -> Path:
        candidate = self.root.joinpath(*policy.root.parts)
        resolved = _resolve_within(candidate, self.root, strict=False)
        if create:
            resolved.mkdir(parents=True, exist_ok=True)
            resolved = _resolve_within(resolved, self.root, strict=True)
        return resolved

    def attempt_directory(
        self,
        policy: ArtifactPolicy,
        identity: RunIdentity,
        *,
        create: bool,
    ) -> Path:
        root = self.plan_root(policy, create=create)
        candidate = root / identity.run_id / f"attempt-{identity.attempt:04d}"
        resolved = _resolve_within(candidate, self.root, strict=False)
        if create:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.mkdir(mode=0o700, exist_ok=False)
            resolved = _resolve_within(resolved, self.root, strict=True)
        return resolved


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return a regular file's lowercase SHA-256 digest."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if path.is_symlink() or not path.is_file():
        raise ArtifactError(f"artifact must be a regular non-symlink file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(path: Path, *, kind: str, relative_to: Path) -> ArtifactRecord:
    """Create immutable content metadata for one confined retained file."""

    if path.is_symlink():
        raise ArtifactError(f"artifact must be a regular non-symlink file: {path}")
    root = relative_to.resolve(strict=True)
    resolved = _resolve_within(path, root, strict=True)
    if not resolved.is_file():
        raise ArtifactError(f"artifact must be a regular non-symlink file: {path}")
    return ArtifactRecord(
        path=resolved.relative_to(root).as_posix(),
        kind=kind,
        size_bytes=resolved.stat().st_size,
        sha256=sha256_file(resolved),
        created_at_utc=datetime.now(UTC).isoformat(),
    )


def artifact_document(record: ArtifactRecord) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "path": record.path,
        "kind": record.kind,
        "size_bytes": record.size_bytes,
        "sha256": record.sha256,
        "created_at_utc": record.created_at_utc,
    }


def _record_from_document(value: dict[str, Any], line_number: int) -> ArtifactRecord:
    expected = {
        "schema_version",
        "path",
        "kind",
        "size_bytes",
        "sha256",
        "created_at_utc",
    }
    unknown = value.keys() - expected
    missing = expected - value.keys()
    if unknown or missing:
        raise ArtifactError(
            f"artifact record line {line_number} has missing={sorted(missing)} "
            f"unknown={sorted(unknown)}"
        )
    if value["schema_version"] != SCHEMA_VERSION:
        raise ArtifactError(f"artifact record line {line_number} has unsupported schema_version")
    if type(value["size_bytes"]) is not int:
        raise ArtifactError(f"artifact record line {line_number} size_bytes must be an integer")
    for key in ("path", "kind", "sha256", "created_at_utc"):
        if not isinstance(value[key], str):
            raise ArtifactError(f"artifact record line {line_number} {key} must be a string")
    try:
        return ArtifactRecord(
            path=value["path"],
            kind=value["kind"],
            size_bytes=value["size_bytes"],
            sha256=value["sha256"],
            created_at_utc=value["created_at_utc"],
        )
    except ValueError as exc:
        raise ArtifactError(f"invalid artifact record line {line_number}: {exc}") from exc


def _decode_record_lines(content: bytes, path: Path) -> tuple[ArtifactRecord, ...]:
    records: list[ArtifactRecord] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        if not raw_line.strip():
            raise ArtifactError(f"{path}: blank artifact record line {line_number} is forbidden")
        try:
            value = loads_json(raw_line)
        except ValueError as exc:
            raise ArtifactError(f"{path}: invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ArtifactError(f"{path}: artifact record line {line_number} must be an object")
        records.append(_record_from_document(cast(dict[str, Any], value), line_number))
    return tuple(records)


def read_artifact_records(path: Path) -> tuple[ArtifactRecord, ...]:
    if path.is_symlink() or not path.is_file():
        raise ArtifactError(f"artifact records must be a regular non-symlink file: {path}")
    return _decode_record_lines(path.read_bytes(), path)


class ArtifactRecordWriter:
    """Append one unique record per retained file without replacing metadata."""

    def __init__(self, artifact_directory: Path) -> None:
        if artifact_directory.is_symlink() or not artifact_directory.is_dir():
            raise ArtifactError("artifact directory must be a non-symlink directory")
        self.directory = artifact_directory.resolve(strict=True)
        self.path = self.directory / ARTIFACT_RECORDS

    def append(self, record: ArtifactRecord) -> None:
        flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "r+b", buffering=0) as handle:
                descriptor = -1
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                handle.seek(0)
                existing = _decode_record_lines(handle.read(), self.path)
                if any(item.path == record.path for item in existing):
                    raise ArtifactError(f"artifact path already recorded: {record.path}")
                encoded = json.dumps(
                    artifact_document(record),
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                handle.seek(0, os.SEEK_END)
                handle.write(encoded + b"\n")
                os.fsync(handle.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)


def _retained_paths(root: Path) -> tuple[set[str], list[str]]:
    paths: set[str] = set()
    errors: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            errors.append(f"symlink is forbidden in artifact directory: {relative}")
        elif path.is_file() and relative != ARTIFACT_RECORDS:
            paths.add(relative)
        elif not path.is_dir() and not path.is_file():
            errors.append(f"non-regular artifact entry is forbidden: {relative}")
    return paths, errors


def _validate_budget_history(
    events: tuple[HarnessEvent, ...],
    plan: RunPlan,
    command: CommandSpec,
) -> list[str]:
    errors: list[str] = []
    maxima: dict[str, float | int | None] = {
        "wall_seconds": plan.budget.max_wall_seconds,
        "cost_usd": plan.budget.max_cost_usd,
        "gpu_hours": plan.budget.max_gpu_hours,
        "model_tokens": plan.budget.max_model_tokens,
        "tool_calls": plan.budget.max_tool_calls,
        "output_bytes": plan.budget.max_output_bytes,
    }
    totals: dict[str, float | int] = {field: 0 for field in maxima}
    exceeded: set[str] = set()
    accounting_evidence = 0
    projection_exceeded: set[str] = set()
    projection = command.resource_projection
    projected: dict[str, float | int] = {
        "cost_usd": projection.cost_usd,
        "gpu_hours": projection.gpu_hours,
        "model_tokens": projection.model_tokens,
        "tool_calls": projection.tool_calls,
    }
    for event in events:
        if event.event_type is not EventType.BUDGET_UPDATE:
            continue
        payload = {key: thaw_json(value) for key, value in event.payload.items()}
        for field, maximum in maxima.items():
            if field not in payload:
                continue
            value = payload[field]
            integer_field = field in {"model_tokens", "tool_calls", "output_bytes"}
            if (
                isinstance(value, bool)
                or (integer_field and type(value) is not int)
                or (not integer_field and not isinstance(value, int | float))
                or (isinstance(value, int | float) and value < 0)
            ):
                errors.append(f"budget update {field} has an invalid total")
                continue
            numeric = cast(int | float, value)
            if numeric < totals[field]:
                errors.append(f"budget update {field} total decreased")
            totals[field] = numeric
            if maximum is not None and numeric > maximum:
                exceeded.add(field)
        raw_accounting = payload.get("nonwall_accounting")
        if raw_accounting is not None:
            accounting_evidence += 1
            expected_units = set(projected)
            if not isinstance(raw_accounting, dict) or set(raw_accounting) != expected_units:
                errors.append("non-wall accounting evidence has invalid unit fields")
                continue
            accounting_totals: dict[str, float | int] = {}
            for field in projected:
                if field not in payload:
                    errors.append(f"non-wall accounting evidence omits its numeric total: {field}")
                    continue
                value = payload[field]
                integer_field = field in {"model_tokens", "tool_calls"}
                if (
                    isinstance(value, bool)
                    or (integer_field and type(value) is not int)
                    or (not integer_field and not isinstance(value, int | float))
                    or (isinstance(value, int | float) and value < 0)
                ):
                    errors.append(
                        f"non-wall accounting evidence has an invalid numeric total: {field}"
                    )
                    continue
                accounting_totals[field] = cast(int | float, value)
            for field, authorized_projection in projected.items():
                status = raw_accounting[field]
                if status not in {"observed", "unavailable-reserved", "not-applicable"}:
                    errors.append(f"non-wall accounting {field} has an invalid status")
                    continue
                accounting_total = accounting_totals.get(field)
                if accounting_total is None:
                    continue
                if status == "not-applicable" and (
                    authorized_projection != 0 or accounting_total != 0
                ):
                    errors.append(
                        f"non-wall accounting {field} has an impossible not-applicable state"
                    )
                if status == "unavailable-reserved" and (
                    authorized_projection <= 0 or accounting_total != authorized_projection
                ):
                    errors.append(
                        f"unavailable non-wall unit was not charged exactly at its projection: "
                        f"{field}"
                    )
                if status == "observed" and accounting_total > authorized_projection:
                    projection_exceeded.add(field)
    terminal_status: str | None = None
    if events and events[-1].event_type is EventType.RUN_STOPPED:
        terminal = {key: thaw_json(value) for key, value in events[-1].payload.items()}
        status = terminal.get("status")
        if isinstance(status, str):
            terminal_status = status
    if accounting_evidence > 1:
        errors.append("non-wall accounting evidence may appear at most once")
    if command.resource_projection.has_usage and accounting_evidence != 1:
        errors.append(
            "projected non-wall execution requires exactly one accounting evidence record"
        )
    if projection_exceeded and terminal_status != "resource-projection-exceeded":
        errors.append(
            "observed non-wall usage exceeds its command projection without the required stop: "
            + ", ".join(sorted(projection_exceeded))
        )
    if exceeded and terminal_status not in {
        "budget-exceeded",
        "resource-projection-exceeded",
    }:
        errors.append(
            "budget update exceeds the retained plan without a budget-exceeded stop: "
            + ", ".join(sorted(exceeded))
        )
    return errors


def validate_artifact_directory(root: Path, *, schema_root: Path) -> list[str]:
    """Verify confinement, event semantics, completeness, sizes, and hashes."""

    if root.is_symlink() or not root.is_dir():
        return [f"artifact directory must be a regular non-symlink directory: {root}"]
    resolved_root = root.resolve(strict=True)
    manifest = resolved_root / ARTIFACT_RECORDS
    try:
        records = read_artifact_records(manifest)
    except (OSError, ArtifactError) as exc:
        return [str(exc)]
    errors: list[str] = []
    seen: set[str] = set()
    for record in records:
        if record.path in seen:
            errors.append(f"duplicate artifact record: {record.path}")
            continue
        seen.add(record.path)
        pure_path = PurePosixPath(record.path)
        candidate = resolved_root.joinpath(*pure_path.parts)
        try:
            resolved = _resolve_within(candidate, resolved_root, strict=True)
        except (OSError, ArtifactError) as exc:
            errors.append(f"{record.path}: {exc}")
            continue
        if resolved.is_symlink() or not resolved.is_file():
            errors.append(f"{record.path}: recorded artifact is not a regular file")
            continue
        if resolved.stat().st_size != record.size_bytes:
            errors.append(f"{record.path}: byte size does not match its record")
        try:
            digest = sha256_file(resolved)
        except (OSError, ArtifactError) as exc:
            errors.append(f"{record.path}: {exc}")
        else:
            if digest != record.sha256:
                errors.append(f"{record.path}: SHA-256 does not match its record")
    retained, path_errors = _retained_paths(resolved_root)
    errors.extend(path_errors)
    missing_records = sorted(retained - seen)
    missing_files = sorted(seen - retained)
    if missing_records:
        errors.append(f"retained files lack artifact records: {missing_records}")
    if missing_files:
        errors.append(f"artifact records lack retained files: {missing_files}")
    event_paths = sorted(path for path in retained if PurePosixPath(path).name == EVENT_STREAM)
    event_errors: list[str] = []
    event_path: Path | None = None
    events: tuple[HarnessEvent, ...] = ()
    if len(event_paths) != 1:
        errors.append("artifact directory must contain exactly one events.jsonl stream")
    else:
        event_path = resolved_root / event_paths[0]
        event_errors = validate_event_stream(event_path, schema_root=schema_root)
        errors.extend(event_errors)
        if not event_errors:
            try:
                events = read_events(event_path)
            except (OSError, ValueError) as exc:
                errors.append(f"{EVENT_STREAM}: {exc}")
    required_contracts = {RUN_PLAN_RECORD, COMMAND_RECORD}
    missing_contracts = sorted(required_contracts - retained)
    if missing_contracts:
        errors.append(f"artifact directory lacks retained run contracts: {missing_contracts}")
    else:
        try:
            plan_data = load_json(resolved_root / RUN_PLAN_RECORD)
            plan_errors = validate_run_plan_data(plan_data, schema_root=schema_root)
            errors.extend(f"{RUN_PLAN_RECORD}: {error}" for error in plan_errors)
            plan = run_plan_from_mapping(plan_data) if not plan_errors else None
        except (OSError, TypeError, ValueError) as exc:
            errors.append(f"{RUN_PLAN_RECORD}: {exc}")
            plan = None
        try:
            command_data = load_json(resolved_root / COMMAND_RECORD)
            command = command_from_document(command_data)
        except (OSError, TypeError, ValueError) as exc:
            errors.append(f"{COMMAND_RECORD}: {exc}")
            command = None
        if plan is not None and command is not None:
            expected = plan.execution.authorization.command_sha256
            if expected is None or command_sha256(command) != expected:
                errors.append("retained command does not match the run-plan authorization binding")
            if event_path is not None and not event_errors:
                errors.extend(_validate_budget_history(events, plan, command))
                try:
                    first_event = events[0]
                except IndexError as exc:
                    errors.append(f"{EVENT_STREAM}: {exc}")
                else:
                    if (first_event.run_id, first_event.attempt) != (
                        plan.identity.run_id,
                        plan.identity.attempt,
                    ):
                        errors.append("event identity does not match the retained run plan")
    if not records:
        errors.append("artifact directory must contain at least one artifact record")
    return errors
