from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from harness_test_support import bind_plan, project_state, typed_plan

from giclab.harness.adapters.base import NormalizationResult
from giclab.harness.artifacts import (
    ARTIFACT_RECORDS,
    COMMAND_RECORD,
    RUN_PLAN_RECORD,
    ArtifactError,
    ArtifactRecordWriter,
    ArtifactWorkspace,
    artifact_record,
    read_artifact_records,
    validate_artifact_directory,
)
from giclab.harness.events import JsonlEventWriter
from giclab.harness.executor import LocalRunExecutor
from giclab.harness.models import (
    CommandSpec,
    EventProvenance,
    EventType,
    HarnessEvent,
    IncrementalLimitEnforcement,
    JsonValue,
    NonWallResourceAccounting,
    ResourceProjection,
    RunPlan,
    command_document,
)
from giclab.harness.plan import run_plan_document
from giclab.validation import ROOT


def _write_event(attempt_dir: Path, plan: RunPlan) -> Path:
    path = attempt_dir / "events.jsonl"
    writer = JsonlEventWriter(path, plan.identity)
    lifecycle: tuple[tuple[int, EventType, dict[str, JsonValue]], ...] = (
        (1, EventType.RUN_STARTED, {}),
        (2, EventType.PREFLIGHT_COMPLETED, {}),
        (3, EventType.COMMAND_STARTED, {}),
        (4, EventType.COMMAND_COMPLETED, {}),
        (5, EventType.RUN_STOPPED, {"status": "completed", "return_code": 0}),
    )
    for sequence, event_type, payload in lifecycle:
        writer.append(
            HarnessEvent(
                run_id=plan.identity.run_id,
                attempt=plan.identity.attempt,
                sequence=sequence,
                timestamp_utc="2026-08-07T12:00:00+00:00",
                event_type=event_type,
                source="giclab-harness",
                provenance=EventProvenance.OBSERVED,
                payload=payload,
            )
        )
    return path


def _complete_attempt(tmp_path: Path) -> Path:
    command = CommandSpec(argv=(sys.executable, "-c", "pass"), cwd=tmp_path, timeout_seconds=2)
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    attempt_dir = workspace.attempt_directory(plan.artifacts, plan.identity, create=True)
    events = _write_event(attempt_dir, plan)
    stdout = attempt_dir / "stdout.log"
    stdout.write_text("synthetic output\n", encoding="utf-8")
    run_plan_path = attempt_dir / RUN_PLAN_RECORD
    command_path = attempt_dir / COMMAND_RECORD
    run_plan_path.write_text(json.dumps(run_plan_document(plan)), encoding="utf-8")
    command_path.write_text(json.dumps(command_document(command)), encoding="utf-8")
    records = ArtifactRecordWriter(attempt_dir)
    records.append(artifact_record(events, kind="event-stream", relative_to=attempt_dir))
    records.append(artifact_record(stdout, kind="raw-log", relative_to=attempt_dir))
    records.append(artifact_record(run_plan_path, kind="run-plan", relative_to=attempt_dir))
    records.append(artifact_record(command_path, kind="command", relative_to=attempt_dir))
    return attempt_dir


def _rehash_manifest(attempt_dir: Path) -> None:
    manifest = attempt_dir / ARTIFACT_RECORDS
    prior = read_artifact_records(manifest)
    manifest.unlink()
    writer = ArtifactRecordWriter(attempt_dir)
    for item in prior:
        writer.append(
            artifact_record(attempt_dir / item.path, kind=item.kind, relative_to=attempt_dir)
        )


def test_artifact_directory_validates_sizes_hashes_and_events(tmp_path: Path) -> None:
    attempt_dir = _complete_attempt(tmp_path)
    assert validate_artifact_directory(attempt_dir, schema_root=ROOT) == []
    assert (attempt_dir / ARTIFACT_RECORDS).is_file()


def test_artifact_validation_detects_changed_content(tmp_path: Path) -> None:
    attempt_dir = _complete_attempt(tmp_path)
    (attempt_dir / "stdout.log").write_text("changed\n", encoding="utf-8")
    errors = validate_artifact_directory(attempt_dir, schema_root=ROOT)
    assert any("SHA-256" in error or "byte size" in error for error in errors)


def test_artifact_validation_detects_unrecorded_file(tmp_path: Path) -> None:
    attempt_dir = _complete_attempt(tmp_path)
    (attempt_dir / "extra.txt").write_text("unrecorded", encoding="utf-8")
    assert any(
        "lack artifact records" in error
        for error in validate_artifact_directory(attempt_dir, schema_root=ROOT)
    )


def test_artifact_record_writer_rejects_duplicate_path(tmp_path: Path) -> None:
    attempt_dir = _complete_attempt(tmp_path)
    record = artifact_record(attempt_dir / "stdout.log", kind="raw-log", relative_to=attempt_dir)
    with pytest.raises(ArtifactError, match="already recorded"):
        ArtifactRecordWriter(attempt_dir).append(record)


def test_attempt_directory_is_exclusive_across_retry_collision(tmp_path: Path) -> None:
    plan = typed_plan()
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    workspace.attempt_directory(plan.artifacts, plan.identity, create=True)
    with pytest.raises(FileExistsError):
        workspace.attempt_directory(plan.artifacts, plan.identity, create=True)


def test_symlink_escape_from_workspace_is_rejected(tmp_path: Path) -> None:
    plan = typed_plan()
    workspace_root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    workspace_root.mkdir()
    outside.mkdir()
    (workspace_root / "synthetic").symlink_to(outside, target_is_directory=True)
    workspace = ArtifactWorkspace.open(workspace_root, create=False)
    with pytest.raises(ArtifactError, match="escapes"):
        workspace.plan_root(plan.artifacts, create=False)


def test_artifact_validation_rejects_symlinks(tmp_path: Path) -> None:
    attempt_dir = _complete_attempt(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (attempt_dir / "linked.txt").symlink_to(outside)
    assert any(
        "symlink is forbidden" in error
        for error in validate_artifact_directory(attempt_dir, schema_root=ROOT)
    )


def test_artifact_records_reject_duplicate_json_keys(tmp_path: Path) -> None:
    attempt_dir = _complete_attempt(tmp_path)
    manifest = attempt_dir / ARTIFACT_RECORDS
    content = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        content.replace(
            '"path":"events.jsonl"',
            '"path":"events.jsonl","path":"shadow.jsonl"',
            1,
        ),
        encoding="utf-8",
    )
    assert any(
        "duplicate JSON key" in error
        for error in validate_artifact_directory(attempt_dir, schema_root=ROOT)
    )


def test_artifact_validation_checks_command_against_authorized_digest(tmp_path: Path) -> None:
    attempt_dir = _complete_attempt(tmp_path)
    command_path = attempt_dir / COMMAND_RECORD
    command = json.loads(command_path.read_text(encoding="utf-8"))
    command["timeout_seconds"] = 3
    command_path.write_text(json.dumps(command), encoding="utf-8")
    _rehash_manifest(attempt_dir)
    errors = validate_artifact_directory(attempt_dir, schema_root=ROOT)
    assert any("authorization binding" in error for error in errors)


def test_artifact_validation_rejects_completed_budget_totals_above_retained_plan(
    tmp_path: Path,
) -> None:
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    outcome = LocalRunExecutor(workspace).execute(plan, command, project_state()).seal()
    lines = outcome.events_path.read_text(encoding="utf-8").splitlines()
    documents = [json.loads(line) for line in lines]
    budget = next(item for item in documents if item["event_type"] == "budget_update")
    budget["payload"]["wall_seconds"] = plan.budget.max_wall_seconds + 1
    outcome.events_path.write_text(
        "\n".join(json.dumps(item) for item in documents) + "\n",
        encoding="utf-8",
    )
    _rehash_manifest(outcome.events_path.parent)
    errors = validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT)
    assert any("exceeds the retained plan" in error for error in errors)


def test_artifact_validation_requires_projected_nonwall_accounting_evidence(
    tmp_path: Path,
) -> None:
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        resource_projection=ResourceProjection(
            tool_calls=1,
            enforcement=IncrementalLimitEnforcement.ADAPTER_COMMAND,
        ),
    )
    plan = bind_plan(typed_plan(max_tool_calls=1), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    session = LocalRunExecutor(workspace).execute(plan, command, project_state())
    session.apply_normalization(
        NormalizationResult(
            events=(),
            raw_artifacts=(),
            unavailable_fields=(),
            warnings=(),
            accounting=NonWallResourceAccounting(0.0, 0.0, 0, 0),
        )
    )
    outcome = session.seal()
    documents = [
        json.loads(line) for line in outcome.events_path.read_text(encoding="utf-8").splitlines()
    ]
    documents = [
        item
        for item in documents
        if not (item["event_type"] == "budget_update" and "nonwall_accounting" in item["payload"])
    ]
    outcome.events_path.write_text(
        "\n".join(json.dumps(item) for item in documents) + "\n",
        encoding="utf-8",
    )
    _rehash_manifest(outcome.events_path.parent)
    errors = validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT)
    assert any("requires exactly one accounting evidence" in error for error in errors)


def _zero_accounted_attempt(tmp_path: Path) -> Path:
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    session = LocalRunExecutor(workspace).execute(plan, command, project_state())
    session.apply_normalization(
        NormalizationResult(
            events=(),
            raw_artifacts=(),
            unavailable_fields=(),
            warnings=(),
            accounting=NonWallResourceAccounting(0.0, 0.0, 0, 0),
        )
    )
    return session.seal().events_path.parent


def test_artifact_validation_rejects_impossible_nonwall_accounting_status(
    tmp_path: Path,
) -> None:
    attempt = _zero_accounted_attempt(tmp_path)
    events_path = attempt / "events.jsonl"
    documents = [json.loads(line) for line in events_path.read_text().splitlines()]
    accounting = next(
        item
        for item in documents
        if item["event_type"] == "budget_update" and "nonwall_accounting" in item["payload"]
    )
    accounting["payload"]["nonwall_accounting"]["tool_calls"] = "unavailable-reserved"
    events_path.write_text(
        "\n".join(json.dumps(item) for item in documents) + "\n",
        encoding="utf-8",
    )
    _rehash_manifest(attempt)
    errors = validate_artifact_directory(attempt, schema_root=ROOT)
    assert any("impossible" in error or "charged exactly" in error for error in errors)


def test_artifact_validation_rejects_duplicate_nonwall_accounting_evidence(
    tmp_path: Path,
) -> None:
    attempt = _zero_accounted_attempt(tmp_path)
    events_path = attempt / "events.jsonl"
    documents = [json.loads(line) for line in events_path.read_text().splitlines()]
    accounting = next(
        item
        for item in documents
        if item["event_type"] == "budget_update" and "nonwall_accounting" in item["payload"]
    )
    first_budget = next(
        item
        for item in documents
        if item["event_type"] == "budget_update" and "nonwall_accounting" not in item["payload"]
    )
    for field in ("cost_usd", "gpu_hours", "model_tokens", "tool_calls"):
        first_budget["payload"][field] = accounting["payload"][field]
    first_budget["payload"]["nonwall_accounting"] = accounting["payload"]["nonwall_accounting"]
    events_path.write_text(
        "\n".join(json.dumps(item) for item in documents) + "\n",
        encoding="utf-8",
    )
    _rehash_manifest(attempt)
    errors = validate_artifact_directory(attempt, schema_root=ROOT)
    assert any("at most once" in error for error in errors)


def test_artifact_validation_requires_all_accounting_event_totals(tmp_path: Path) -> None:
    attempt = _zero_accounted_attempt(tmp_path)
    events_path = attempt / "events.jsonl"
    documents = [json.loads(line) for line in events_path.read_text().splitlines()]
    accounting = next(
        item
        for item in documents
        if item["event_type"] == "budget_update" and "nonwall_accounting" in item["payload"]
    )
    del accounting["payload"]["tool_calls"]
    events_path.write_text(
        "\n".join(json.dumps(item) for item in documents) + "\n",
        encoding="utf-8",
    )
    _rehash_manifest(attempt)
    errors = validate_artifact_directory(attempt, schema_root=ROOT)
    assert any("omits its numeric total: tool_calls" in error for error in errors)
