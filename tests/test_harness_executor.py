from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from collections.abc import Iterator, Mapping
from dataclasses import replace
from pathlib import Path

import pytest
from harness_test_support import bind_plan, project_state, typed_plan

from giclab.harness.adapters.base import (
    AdapterNotice,
    AdapterNoticeSeverity,
    ArtifactAdapter,
    NormalizationResult,
)
from giclab.harness.artifacts import (
    ArtifactWorkspace,
    read_artifact_records,
    validate_artifact_directory,
)
from giclab.harness.events import read_events
from giclab.harness.executor import LocalExecutionError, LocalRunExecutor, _StreamingRedactor
from giclab.harness.models import (
    AdapterEventType,
    CommandSpec,
    EventProvenance,
    EventType,
    IncrementalLimitEnforcement,
    NonWallResourceAccounting,
    NormalizedEvent,
    OwnedOutputRoot,
    ResourceProjection,
    RunPlan,
    inherited_environment_binding,
    thaw_json,
)
from giclab.harness.policy import ExecutionDisallowed
from giclab.harness.safety import CredentialExposureError, ExactCredentialScrubber
from giclab.validation import ROOT


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _SyntheticAdapter:
    source_id = "synthetic-adapter"

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    def build_command(
        self,
        plan: RunPlan,
        upstream_root: Path,
        upstream_output_root: Path,
    ) -> CommandSpec:
        del plan
        raw_path = upstream_output_root / "synthetic-upstream.json"
        script = (
            "from pathlib import Path; "
            f"Path({str(raw_path)!r}).write_text('observed', encoding='utf-8')"
        )
        return CommandSpec(
            argv=(sys.executable, "-c", script),
            cwd=upstream_root,
            timeout_seconds=2,
            owned_output_roots=(OwnedOutputRoot(upstream_output_root),),
            resource_projection=ResourceProjection(
                tool_calls=1,
                enforcement=IncrementalLimitEnforcement.ADAPTER_COMMAND,
            ),
        )

    def normalize(self, plan: RunPlan, upstream_output_root: Path) -> NormalizationResult:
        del plan
        return NormalizationResult(
            events=(
                NormalizedEvent(
                    event_type=AdapterEventType.METRIC,
                    source=self.source_id,
                    provenance=EventProvenance.OBSERVED,
                    payload={"name": "synthetic-count", "value": 1},
                ),
            ),
            raw_artifacts=(upstream_output_root / "synthetic-upstream.json",),
            unavailable_fields=("source-unsupported-field",),
            notices=(),
            accounting=NonWallResourceAccounting(
                cost_usd=0.0,
                gpu_hours=0.0,
                model_tokens=0,
                tool_calls=1,
            ),
        )


class _TrapEnvironment(Mapping[str, str]):
    def __init__(self, values: Mapping[str, str]) -> None:
        self.values = dict(values)
        self.accessed: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.accessed.append(key)
        return self.values[key]

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("ambient environment must not be enumerated")

    def __len__(self) -> int:
        raise AssertionError("ambient environment size must not be inspected")


def _process_is_live(pid: int) -> bool:
    completed = subprocess.run(
        ("ps", "-o", "state=", "-p", str(pid)),
        check=False,
        capture_output=True,
        text=True,
    )
    state = completed.stdout.strip()
    return completed.returncode == 0 and bool(state) and not state.startswith("Z")


def test_dry_run_does_not_execute_or_create_attempt(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    plan = typed_plan()
    workspace_root = tmp_path / "artifacts"
    workspace_root.mkdir()
    executor = LocalRunExecutor(ArtifactWorkspace.open(workspace_root, create=False))
    command = CommandSpec(
        argv=(sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    report = executor.dry_run(plan, command, project_state(prototype=False))
    assert report.execution_allowed is False
    assert "run plan is not authorized" in report.blockers
    assert not marker.exists()
    assert not report.prospective_artifact_directory.exists()


def test_construction_dry_run_and_unauthorized_execution_do_not_read_ambient_secrets(
    tmp_path: Path,
) -> None:
    host = _TrapEnvironment(
        {
            "NAMED_CREDENTIAL": "private-value-never-read",
            "UNRELATED_VALUE": "unrelated-value-never-read",
        }
    )
    workspace_root = tmp_path / "artifacts"
    workspace_root.mkdir()
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("NAMED_CREDENTIAL",),
    )
    executor = LocalRunExecutor(
        ArtifactWorkspace.open(workspace_root, create=False),
        host_environment=host,
    )
    executor.dry_run(bind_plan(typed_plan(), command), command, project_state())
    with pytest.raises(ExecutionDisallowed, match="not authorized"):
        executor.execute(typed_plan(), command, project_state())
    assert host.accessed == []


def test_live_run_refuses_unauthorized_plan_before_creating_evidence(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(workspace)
    command = CommandSpec(argv=(sys.executable, "-c", "pass"), cwd=tmp_path, timeout_seconds=2)
    with pytest.raises(ExecutionDisallowed, match="not authorized"):
        executor.execute(typed_plan(), command, project_state())
    assert list(workspace.root.iterdir()) == []


def test_live_run_refuses_disabled_project_state(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(workspace)
    command = CommandSpec(argv=(sys.executable, "-c", "pass"), cwd=tmp_path, timeout_seconds=2)
    plan = bind_plan(typed_plan(), command)
    with pytest.raises(ExecutionDisallowed, match="prototype"):
        executor.execute(plan, command, project_state(prototype=False))


def test_live_run_redacts_named_secrets_and_validates_artifacts(tmp_path: Path) -> None:
    credential_value = "synthetic-secret-value-12345"
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(
        workspace,
        host_environment={"PATH": "", "SYNTHETIC_API_KEY": credential_value},
    )
    script = (
        "import os,sys; value=os.environ['SYNTHETIC_API_KEY']; "
        "print(value); print(value, file=sys.stderr)"
    )
    command = CommandSpec(
        argv=(sys.executable, "-c", script),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("SYNTHETIC_API_KEY",),
    )
    plan = bind_plan(typed_plan(), command)
    outcome = executor.execute(plan, command, project_state()).seal()
    assert outcome.return_code == 0
    assert outcome.stdout_redactions == 1
    assert outcome.stderr_redactions == 1
    assert credential_value.encode() not in outcome.stdout_path.read_bytes()
    assert credential_value.encode() not in outcome.stderr_path.read_bytes()
    assert b"[REDACTED]" in outcome.stdout_path.read_bytes()
    attempt_dir = outcome.events_path.parent
    assert validate_artifact_directory(attempt_dir, schema_root=ROOT) == []


def test_named_environment_nul_is_refused_before_attempt_creation(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("NUL_CREDENTIAL",),
    )
    plan = bind_plan(typed_plan(), command)
    executor = LocalRunExecutor(
        workspace,
        host_environment={"NUL_CREDENTIAL": "bad\0value"},
    )
    with pytest.raises(ExecutionDisallowed, match="NUL byte"):
        executor.execute(plan, command, project_state())
    assert list(workspace.root.iterdir()) == []


def test_credential_equal_to_owned_artifact_name_is_refused_before_attempt(
    tmp_path: Path,
) -> None:
    private_value = "stdout.log"
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("PATH_CREDENTIAL",),
    )
    plan = bind_plan(typed_plan(), command)
    executor = LocalRunExecutor(
        workspace,
        host_environment={"PATH_CREDENTIAL": private_value},
    )
    with pytest.raises(CredentialExposureError, match="artifact path"):
        executor.execute(plan, command, project_state())
    assert list(workspace.root.iterdir()) == []


def test_retry_collision_cannot_overwrite_raw_logs(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(workspace)
    command = CommandSpec(
        argv=(sys.executable, "-c", "print('first')"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(), command)
    outcome = executor.execute(plan, command, project_state()).seal()
    stdout_digest = _digest(outcome.stdout_path)
    with pytest.raises(FileExistsError):
        executor.execute(plan, command, project_state())
    assert _digest(outcome.stdout_path) == stdout_digest


def test_run_session_authority_and_budget_owner_cannot_be_replaced(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(), command)
    session = LocalRunExecutor(workspace).execute(plan, command, project_state())
    for field in (
        "plan",
        "command",
        "guard",
        "_plan",
        "_command",
        "_guard",
        "_accounting_attested",
        "_status",
        "_usage",
    ):
        with pytest.raises(AttributeError):
            setattr(session, field, object())
    for owner, field in (
        (session._scrubber, "_private_bytes"),
        (session._scrubber, "private_bytes"),
    ):
        with pytest.raises(AttributeError):
            setattr(owner, field, object())
    with pytest.raises(TypeError):
        session._retained[tmp_path / "unowned.txt"] = "upstream-raw"
    outcome = session.seal()
    assert outcome.usage.wall_seconds <= plan.budget.max_wall_seconds
    assert validate_artifact_directory(session.attempt_directory, schema_root=ROOT) == []


def test_secret_value_cannot_be_duplicated_in_serialized_command(tmp_path: Path) -> None:
    credential_value = "not-pattern-matched-but-still-private"
    executor = LocalRunExecutor(
        ArtifactWorkspace.open(tmp_path / "artifacts", create=True),
        host_environment={"SYNTHETIC_API_KEY": credential_value},
    )
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass", credential_value),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("SYNTHETIC_API_KEY",),
        inherit_environment=(),
    )
    plan = bind_plan(typed_plan(), command)
    with pytest.raises(CredentialExposureError, match="exact injected credential"):
        executor.execute(plan, command, project_state())


def test_named_secret_value_cannot_be_duplicated_in_serialized_cwd(tmp_path: Path) -> None:
    private_value = "synthetic-private-directory"
    command_cwd = tmp_path / private_value
    command_cwd.mkdir()
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(
        workspace,
        host_environment={"SYNTHETIC_API_KEY": private_value},
    )
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=command_cwd,
        timeout_seconds=2,
        secret_environment=("SYNTHETIC_API_KEY",),
        inherit_environment=(),
    )
    plan = bind_plan(typed_plan(), command)
    with pytest.raises(CredentialExposureError, match="exact injected credential"):
        executor.execute(plan, command, project_state())
    assert list(workspace.root.iterdir()) == []


def test_authorization_binding_covers_command_and_output_ownership(tmp_path: Path) -> None:
    other_cwd = tmp_path / "other"
    other_cwd.mkdir()
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(workspace)
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        environment={"SYNTHETIC_MODE": "one"},
        inherit_environment=(),
    )
    plan = bind_plan(typed_plan(), command)
    mutations = (
        replace(command, argv=(sys.executable, "-c", "print('changed')")),
        replace(command, cwd=other_cwd),
        replace(command, environment={"SYNTHETIC_MODE": "two"}),
        replace(command, timeout_seconds=3),
        replace(
            command,
            owned_output_roots=(OwnedOutputRoot(tmp_path / "changed-output-owner"),),
        ),
    )
    for mutated in mutations:
        report = executor.dry_run(plan, mutated, project_state())
        assert "command does not match the run plan authorization binding" in report.blockers
        with pytest.raises(ExecutionDisallowed, match="authorization binding"):
            executor.execute(plan, mutated, project_state())
    assert list(workspace.root.iterdir()) == []


def test_synthetic_adapter_normalizes_and_accounts_before_sealing(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    initial_plan = typed_plan(max_tool_calls=2)
    prospective = workspace.attempt_directory(
        initial_plan.artifacts, initial_plan.identity, create=False
    )
    adapter: ArtifactAdapter = _SyntheticAdapter(tmp_path)
    command = adapter.build_command(initial_plan, tmp_path, prospective)
    plan = bind_plan(initial_plan, command)
    session = LocalRunExecutor(workspace).execute(plan, command, project_state())
    session.apply_normalization(adapter.normalize(plan, session.attempt_directory))
    outcome = session.seal()

    assert outcome.usage.tool_calls == 1
    records = read_artifact_records(outcome.artifact_records_path)
    assert any(record.path == "synthetic-upstream.json" for record in records)
    events = read_events(outcome.events_path)
    metric = next(event for event in events if event.event_type is EventType.METRIC)
    assert metric.source == "synthetic-adapter"
    assert events[-1].event_type is EventType.RUN_STOPPED
    assert validate_artifact_directory(session.attempt_directory, schema_root=ROOT) == []


def test_adapter_notices_emit_harness_owned_typed_control_events(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(), command)
    session = LocalRunExecutor(workspace).execute(plan, command, project_state())
    session.apply_normalization(
        NormalizationResult(
            events=(),
            raw_artifacts=(),
            unavailable_fields=(),
            notices=(
                AdapterNotice(
                    severity=AdapterNoticeSeverity.WARNING,
                    kind="source-warning",
                    message="observed source warning",
                    source="synthetic-adapter",
                    source_paths=("history[0].warning",),
                    provenance=EventProvenance.DERIVED,
                ),
                AdapterNotice(
                    severity=AdapterNoticeSeverity.ERROR,
                    kind="source-error",
                    message="observed source error",
                    source="synthetic-adapter",
                    source_paths=("error",),
                    provenance=EventProvenance.OBSERVED,
                ),
            ),
            accounting=NonWallResourceAccounting(0.0, 0.0, 0, 0),
        )
    )
    outcome = session.seal()
    events = read_events(outcome.events_path)
    warning = next(event for event in events if event.event_type is EventType.WARNING)
    error = next(event for event in events if event.event_type is EventType.ERROR)
    assert warning.source == "giclab-harness"
    assert warning.provenance is EventProvenance.DERIVED
    assert warning.payload["adapter_source"] == "synthetic-adapter"
    assert error.source == "giclab-harness"
    assert error.provenance is EventProvenance.OBSERVED
    assert thaw_json(error.payload["source_paths"]) == ["error"]


def test_nonwall_projection_requires_explicit_accounting_before_seal(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
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
    session = LocalRunExecutor(workspace).execute(plan, command, project_state())
    with pytest.raises(AttributeError, match="write-owned"):
        session._accounting_attested = True
    with pytest.raises(LocalExecutionError, match="must be observed or explicitly unavailable"):
        session.seal()
    assert not session.sealed
    session.apply_normalization(
        NormalizationResult(
            events=(),
            raw_artifacts=(),
            unavailable_fields=(),
            notices=(),
            accounting=NonWallResourceAccounting(
                cost_usd=0.0,
                gpu_hours=0.0,
                model_tokens=0,
                tool_calls=None,
            ),
        )
    )
    outcome = session.seal()
    assert outcome.usage.tool_calls == 1
    events = read_events(outcome.events_path)
    assert any(event.payload.get("kind") == "resource-accounting-unavailable" for event in events)
    assert validate_artifact_directory(session.attempt_directory, schema_root=ROOT) == []


def test_normalization_result_cannot_omit_accounting_attestation() -> None:
    with pytest.raises(TypeError, match="accounting"):
        NormalizationResult(  # type: ignore[call-arg]
            events=(),
            raw_artifacts=(),
            unavailable_fields=(),
            notices=(),
        )


def test_nonwall_projection_over_budget_cannot_execute_marker(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    marker = tmp_path / "must-not-exist"
    command = CommandSpec(
        argv=(
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).touch()",
        ),
        cwd=tmp_path,
        timeout_seconds=2,
        resource_projection=ResourceProjection(
            tool_calls=1,
            enforcement=IncrementalLimitEnforcement.ADAPTER_COMMAND,
        ),
    )
    plan = bind_plan(typed_plan(max_tool_calls=0), command)
    with pytest.raises(ExecutionDisallowed, match="tool_calls"):
        LocalRunExecutor(workspace).execute(plan, command, project_state())

    assert not marker.exists()
    assert list(workspace.root.iterdir()) == []


def test_command_output_root_outside_exact_attempt_is_refused_before_execution(
    tmp_path: Path,
) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    outside_root = tmp_path / "outside"
    marker = outside_root / "must-not-exist"
    command = CommandSpec(
        argv=(
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).touch()",
        ),
        cwd=tmp_path,
        timeout_seconds=2,
        owned_output_roots=(OwnedOutputRoot(outside_root),),
    )
    plan = bind_plan(typed_plan(), command)
    executor = LocalRunExecutor(workspace)

    report = executor.dry_run(plan, command, project_state())
    assert any("outside the exact harness run attempt" in item for item in report.blockers)
    with pytest.raises(ExecutionDisallowed, match="outside the exact harness run attempt"):
        executor.execute(plan, command, project_state())
    assert not marker.exists()
    assert list(workspace.root.iterdir()) == []


def test_owned_output_root_symlink_substitution_is_rechecked(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    initial_plan = typed_plan()
    attempt = workspace.attempt_directory(
        initial_plan.artifacts,
        initial_plan.identity,
        create=False,
    )
    output_root = attempt / "source-output"
    marker = output_root / "must-not-exist"
    command = CommandSpec(
        argv=(
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).touch()",
        ),
        cwd=tmp_path,
        timeout_seconds=2,
        owned_output_roots=(OwnedOutputRoot(output_root),),
    )
    plan = bind_plan(initial_plan, command)
    executor = LocalRunExecutor(workspace)
    assert executor.dry_run(plan, command, project_state()).execution_allowed

    attempt.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    output_root.symlink_to(outside, target_is_directory=True)
    report = executor.dry_run(plan, command, project_state())
    assert any("owned output root resolution changed" in item for item in report.blockers)
    with pytest.raises(ExecutionDisallowed, match="owned output root resolution changed"):
        executor.execute(plan, command, project_state())
    assert not (outside / "must-not-exist").exists()


def test_observed_usage_over_projection_seals_failure_evidence(tmp_path: Path) -> None:
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    initial_plan = typed_plan(max_tool_calls=2)
    prospective = workspace.attempt_directory(
        initial_plan.artifacts, initial_plan.identity, create=False
    )
    adapter: ArtifactAdapter = _SyntheticAdapter(tmp_path)
    command = adapter.build_command(initial_plan, tmp_path, prospective)
    plan = bind_plan(initial_plan, command)
    session = LocalRunExecutor(workspace).execute(plan, command, project_state())
    normalized = adapter.normalize(plan, session.attempt_directory)
    over_projection = replace(
        normalized,
        accounting=NonWallResourceAccounting(
            cost_usd=0.0,
            gpu_hours=0.0,
            model_tokens=0,
            tool_calls=2,
        ),
    )
    with pytest.raises(LocalExecutionError, match="preflight enforcement contract"):
        session.apply_normalization(over_projection)

    assert session.sealed
    assert validate_artifact_directory(session.attempt_directory, schema_root=ROOT) == []
    assert read_events(session.attempt_directory / "events.jsonl")[-1].payload["status"] == (
        "resource-projection-exceeded"
    )


def test_changed_inherited_path_is_refused_before_execution(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    command = CommandSpec(
        argv=(
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).touch()",
        ),
        cwd=tmp_path,
        timeout_seconds=2,
        inherit_environment=(inherited_environment_binding("PATH", "/approved/bin"),),
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(workspace, host_environment={"PATH": "/substituted/bin"})
    report = executor.dry_run(plan, command, project_state())
    assert "inherited environment binding changed: PATH" in report.blockers
    with pytest.raises(ExecutionDisallowed, match="inherited environment binding changed"):
        executor.execute(plan, command, project_state())
    assert not marker.exists()
    assert list(workspace.root.iterdir()) == []


def test_authorized_cwd_cannot_be_replaced_by_a_symlink(tmp_path: Path) -> None:
    authorized_cwd = tmp_path / "authorized-cwd"
    substituted_cwd = tmp_path / "substituted-cwd"
    authorized_cwd.mkdir()
    substituted_cwd.mkdir()
    command = CommandSpec(
        argv=(
            sys.executable,
            "-c",
            "from pathlib import Path; Path('must-not-exist').touch()",
        ),
        cwd=authorized_cwd,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(), command)
    authorized_cwd.rmdir()
    authorized_cwd.symlink_to(substituted_cwd, target_is_directory=True)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(workspace)
    report = executor.dry_run(plan, command, project_state())
    assert "command cwd resolution changed after authorization" in report.blockers
    with pytest.raises(ExecutionDisallowed, match="cwd resolution changed"):
        executor.execute(plan, command, project_state())
    assert not (substituted_cwd / "must-not-exist").exists()
    assert list(workspace.root.iterdir()) == []


def test_process_group_cleanup_terminates_descendant_holding_stdout(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.pid"
    script = (
        "import subprocess,sys; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"open({str(child_pid_path)!r},'w',encoding='utf-8').write(str(child.pid)); "
        "print('parent-finished', flush=True)"
    )
    command = CommandSpec(
        argv=(sys.executable, "-c", script),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    started = time.monotonic()
    outcome = LocalRunExecutor(workspace).execute(plan, command, project_state()).seal()
    elapsed = time.monotonic() - started

    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2
    while _process_is_live(child_pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert elapsed < 5
    assert not _process_is_live(child_pid)
    assert outcome.return_code == 0
    assert validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT) == []


def test_output_budget_streams_to_a_hard_cap_and_seals_failure_evidence(
    tmp_path: Path,
) -> None:
    command = CommandSpec(
        argv=(
            sys.executable,
            "-c",
            "import os,time; os.write(1,b'x'*131072); time.sleep(5)",
        ),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(max_output_bytes=1024), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    with pytest.raises(LocalExecutionError, match="hard budget") as captured:
        LocalRunExecutor(workspace).execute(plan, command, project_state())

    session = captured.value.session
    assert session is not None
    outcome = session.seal()
    attempt = outcome.events_path.parent
    assert (attempt / "stdout.log").stat().st_size + (attempt / "stderr.log").stat().st_size <= 1024
    assert validate_artifact_directory(attempt, schema_root=ROOT) == []
    stopped = read_events(attempt / "events.jsonl")[-1]
    assert stopped.event_type is EventType.RUN_STOPPED
    assert stopped.payload["status"] == "output-budget-exceeded"


def test_streaming_redaction_matches_across_input_chunk_boundaries() -> None:
    private_value = b"synthetic-private-boundary-value"
    redactor = _StreamingRedactor((private_value,))
    output = b"".join(
        (
            redactor.feed(b"prefix:" + private_value[:9]),
            redactor.feed(private_value[9:21]),
            redactor.feed(private_value[21:] + b":suffix"),
            redactor.finish(),
        )
    )
    assert redactor.redactions == 1
    assert output == b"prefix:[REDACTED]:suffix"


def test_redaction_replacement_cannot_retain_a_one_character_credential() -> None:
    scrubber = ExactCredentialScrubber(("R",))
    assert scrubber.replacement == b""
    redactor = _StreamingRedactor(
        scrubber.private_bytes,
        replacement=scrubber.replacement,
    )
    output = b"".join((redactor.feed(b"prefix:R:suffix"), redactor.finish()))
    assert redactor.redactions == 1
    assert b"R" not in output


def test_output_quota_applies_after_redaction_expansion(tmp_path: Path) -> None:
    private_value = "~"
    command = CommandSpec(
        argv=(
            sys.executable,
            "-c",
            "import os,sys; sys.stdout.write(os.environ['SHORT_SECRET'] * 10000)",
        ),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("SHORT_SECRET",),
    )
    plan = bind_plan(typed_plan(max_output_bytes=100), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(
        workspace,
        host_environment={"PATH": "", "SHORT_SECRET": private_value},
    )
    with pytest.raises(LocalExecutionError, match="hard budget") as captured:
        executor.execute(plan, command, project_state())

    session = captured.value.session
    assert session is not None
    outcome = session.seal()
    attempt = outcome.events_path.parent
    assert (attempt / "stdout.log").stat().st_size + (attempt / "stderr.log").stat().st_size <= 100
    assert private_value.encode() not in (attempt / "stdout.log").read_bytes()
    assert validate_artifact_directory(attempt, schema_root=ROOT) == []


def test_launch_failure_has_no_command_started_or_completed_event(tmp_path: Path) -> None:
    executable = tmp_path / "not-executable"
    executable.write_text("not a runnable program\n", encoding="utf-8")
    command = CommandSpec(
        argv=(str(executable),),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    with pytest.raises(LocalExecutionError, match="could not be started"):
        LocalRunExecutor(workspace).execute(plan, command, project_state())

    attempt = workspace.attempt_directory(plan.artifacts, plan.identity, create=False)
    events = read_events(attempt / "events.jsonl")
    event_types = tuple(event.event_type for event in events)
    assert EventType.COMMAND_STARTED not in event_types
    assert EventType.COMMAND_COMPLETED not in event_types
    assert EventType.ERROR in event_types
    assert event_types[-1] is EventType.RUN_STOPPED
    assert validate_artifact_directory(attempt, schema_root=ROOT) == []


def test_exact_credential_in_retained_run_plan_is_refused_before_attempt(tmp_path: Path) -> None:
    private_value = "synthetic-plan-private-value-987"
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("PLAN_CREDENTIAL",),
    )
    initial_plan = typed_plan()
    plan = bind_plan(
        replace(
            initial_plan,
            identity=replace(initial_plan.identity, condition=private_value),
        ),
        command,
    )
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(
        workspace,
        host_environment={"PLAN_CREDENTIAL": private_value},
    )
    with pytest.raises(CredentialExposureError, match="retained run plan"):
        executor.execute(plan, command, project_state())
    assert list(workspace.root.iterdir()) == []


def test_exact_credential_in_normalized_event_is_never_appended(tmp_path: Path) -> None:
    private_value = "synthetic-event-private-value-987"
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("EVENT_CREDENTIAL",),
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(
        workspace,
        host_environment={"EVENT_CREDENTIAL": private_value},
    )
    session = executor.execute(plan, command, project_state())
    result = NormalizationResult(
        events=(
            NormalizedEvent(
                event_type=AdapterEventType.OBSERVATION,
                source="synthetic-adapter",
                provenance=EventProvenance.OBSERVED,
                payload={"value": private_value},
            ),
        ),
        raw_artifacts=(),
        unavailable_fields=(),
        notices=(),
        accounting=NonWallResourceAccounting(0.0, 0.0, 0, 0),
    )
    with pytest.raises(CredentialExposureError, match="harness event"):
        session.apply_normalization(result)
    outcome = session.seal()
    assert private_value.encode() not in outcome.events_path.read_bytes()
    assert validate_artifact_directory(session.attempt_directory, schema_root=ROOT) == []


def test_exact_credential_in_raw_adapter_artifact_is_never_retained(tmp_path: Path) -> None:
    private_value = "synthetic-raw-private-value-987"
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("RAW_CREDENTIAL",),
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    executor = LocalRunExecutor(
        workspace,
        host_environment={"RAW_CREDENTIAL": private_value},
    )
    session = executor.execute(plan, command, project_state())
    with pytest.raises(AttributeError):
        session._scrubber.private_bytes = ()
    with pytest.raises(AttributeError):
        session._scrubber._private_bytes = ()
    raw_path = session.attempt_directory / "adapter-raw.txt"
    raw_path.write_text(private_value, encoding="utf-8")
    result = NormalizationResult(
        events=(),
        raw_artifacts=(raw_path,),
        unavailable_fields=(),
        notices=(),
        accounting=NonWallResourceAccounting(0.0, 0.0, 0, 0),
    )
    with pytest.raises(CredentialExposureError, match="adapter raw artifact"):
        session.apply_normalization(result)
    assert not raw_path.exists()
    outcome = session.seal()
    assert outcome.status == "credential-artifact-refused"
    for retained in session.attempt_directory.iterdir():
        if retained.is_file():
            assert private_value.encode() not in retained.read_bytes()
    assert validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT) == []


def test_omitted_credential_file_is_removed_and_prevents_successful_seal(
    tmp_path: Path,
) -> None:
    private_value = "synthetic-omitted-private-value-987"
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("OMITTED_CREDENTIAL",),
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    session = LocalRunExecutor(
        workspace,
        host_environment={"OMITTED_CREDENTIAL": private_value},
    ).execute(plan, command, project_state())
    omitted = session.attempt_directory / "omitted-raw.txt"
    omitted.write_text(private_value, encoding="utf-8")
    with pytest.raises(CredentialExposureError, match="refused and removed"):
        session.seal()
    assert not omitted.exists()
    assert not session.sealed
    outcome = session.seal()
    assert outcome.status == "credential-artifact-refused"
    assert validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT) == []


def test_credential_bearing_fifo_is_physically_removed_on_refusal(tmp_path: Path) -> None:
    private_value = "synthetic-fifo-private-value-987"
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("FIFO_CREDENTIAL",),
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    session = LocalRunExecutor(
        workspace,
        host_environment={"FIFO_CREDENTIAL": private_value},
    ).execute(plan, command, project_state())
    fifo = session.attempt_directory / private_value
    os.mkfifo(fifo)
    with pytest.raises(CredentialExposureError, match="refused and removed"):
        session.seal()
    assert not fifo.exists()
    outcome = session.seal()
    assert outcome.status == "credential-artifact-refused"
    assert validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT) == []


def test_safe_unowned_file_must_be_claimed_by_normalization(tmp_path: Path) -> None:
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    session = LocalRunExecutor(workspace).execute(plan, command, project_state())
    raw_path = session.attempt_directory / "safe-raw.txt"
    raw_path.write_text("safe observed value", encoding="utf-8")
    with pytest.raises(LocalExecutionError, match="must be declared"):
        session.seal()
    session.apply_normalization(
        NormalizationResult(
            events=(),
            raw_artifacts=(raw_path,),
            unavailable_fields=(),
            notices=(),
            accounting=NonWallResourceAccounting(0.0, 0.0, 0, 0),
        )
    )
    outcome = session.seal()
    assert validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT) == []


def test_budget_failure_session_preserves_adapter_owned_raw_output(tmp_path: Path) -> None:
    initial_plan = typed_plan(max_output_bytes=1024)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    prospective = workspace.attempt_directory(
        initial_plan.artifacts,
        initial_plan.identity,
        create=False,
    )
    raw_path = prospective / "failure-observation.json"
    script = (
        "from pathlib import Path; import os,time; "
        f"Path({str(raw_path)!r}).write_text('observed-before-stop', encoding='utf-8'); "
        "os.write(1,b'x'*131072); time.sleep(5)"
    )
    command = CommandSpec(
        argv=(sys.executable, "-c", script),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = bind_plan(initial_plan, command)
    with pytest.raises(LocalExecutionError, match="failure session") as captured:
        LocalRunExecutor(workspace).execute(plan, command, project_state())

    session = captured.value.session
    assert session is not None
    assert not session.sealed
    session.apply_normalization(
        NormalizationResult(
            events=(),
            raw_artifacts=(raw_path,),
            unavailable_fields=(),
            notices=(),
            accounting=NonWallResourceAccounting(0.0, 0.0, 0, 0),
        )
    )
    outcome = session.seal()
    assert raw_path.read_text(encoding="utf-8") == "observed-before-stop"
    assert any(
        record.path == raw_path.name
        for record in read_artifact_records(outcome.artifact_records_path)
    )
    assert validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT) == []


def test_wall_budget_failure_outcome_retains_observed_usage(tmp_path: Path) -> None:
    command = CommandSpec(
        argv=(sys.executable, "-c", "import time; time.sleep(3)"),
        cwd=tmp_path,
        timeout_seconds=1,
    )
    plan = bind_plan(typed_plan(max_wall_seconds=1), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    with pytest.raises(LocalExecutionError, match="hard budget") as captured:
        LocalRunExecutor(workspace).execute(plan, command, project_state())

    session = captured.value.session
    assert session is not None
    outcome = session.seal()
    assert outcome.status == "budget-exceeded"
    assert outcome.usage.wall_seconds == outcome.wall_seconds
    assert outcome.usage.wall_seconds > plan.budget.max_wall_seconds
    assert validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT) == []


def test_invalid_adapter_artifact_path_does_not_echo_a_credential(tmp_path: Path) -> None:
    private_value = "synthetic-private-path-value-987"
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
        secret_environment=("PATH_CREDENTIAL",),
    )
    plan = bind_plan(typed_plan(), command)
    workspace = ArtifactWorkspace.open(tmp_path / "artifacts", create=True)
    session = LocalRunExecutor(
        workspace,
        host_environment={"PATH_CREDENTIAL": private_value},
    ).execute(plan, command, project_state())
    invalid = session.attempt_directory / private_value / "missing.json"
    with pytest.raises(CredentialExposureError) as captured:
        session.apply_normalization(
            NormalizationResult(
                events=(),
                raw_artifacts=(invalid,),
                unavailable_fields=(),
                notices=(),
                accounting=NonWallResourceAccounting(0.0, 0.0, 0, 0),
            )
        )
    assert private_value not in str(captured.value)
    outcome = session.seal()
    assert validate_artifact_directory(outcome.events_path.parent, schema_root=ROOT) == []
