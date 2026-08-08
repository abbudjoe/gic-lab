from __future__ import annotations

import sys
from pathlib import Path

from harness_test_support import write_plan, write_project_state

from giclab.harness.cli import run
from giclab.harness.models import (
    CommandSpec,
    IncrementalLimitEnforcement,
    ResourceProjection,
)
from giclab.validation import ROOT


def test_cli_validates_and_renders_without_executing(tmp_path: Path, capsys: object) -> None:
    plan = write_plan(tmp_path / "plan.json")
    assert run(("validate-plan", str(plan), "--schema-root", str(ROOT))) == 0
    assert (
        run(
            (
                "render-command",
                str(plan),
                "--schema-root",
                str(ROOT),
                "--cwd",
                str(tmp_path),
                "--timeout-seconds",
                "2",
                "--secret-env",
                "SYNTHETIC_API_KEY",
                "--",
                sys.executable,
                "-c",
                "pass",
            )
        )
        == 0
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert '"shell": false' in captured.out
    assert '"command_sha256":' in captured.out
    assert "SYNTHETIC_API_KEY" in captured.out


def test_cli_dry_run_reports_blockers_without_creating_evidence(
    tmp_path: Path, capsys: object
) -> None:
    project = tmp_path / "project"
    write_project_state(project, prototype=False)
    plan = write_plan(tmp_path / "plan.json")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    marker = tmp_path / "must-not-exist"
    result = run(
        (
            "run-local",
            str(plan),
            "--project-root",
            str(project),
            "--schema-root",
            str(ROOT),
            "--artifact-workspace",
            str(artifacts),
            "--dry-run",
            "--cwd",
            str(tmp_path),
            "--timeout-seconds",
            "2",
            "--",
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).touch()",
        )
    )
    assert result == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert '"executed": false' in captured.out
    assert '"command_sha256":' in captured.out
    assert "run plan is not authorized" in captured.out
    assert not marker.exists()
    assert list(artifacts.iterdir()) == []


def test_cli_executes_only_an_authorized_enabled_synthetic_run(
    tmp_path: Path, capsys: object
) -> None:
    project = tmp_path / "project"
    write_project_state(project, prototype=True)
    command = CommandSpec(
        argv=(sys.executable, "-c", "print('synthetic')"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = write_plan(tmp_path / "plan.json", authorized=True, command=command)
    artifacts = tmp_path / "artifacts"
    result = run(
        (
            "run-local",
            str(plan),
            "--project-root",
            str(project),
            "--schema-root",
            str(ROOT),
            "--artifact-workspace",
            str(artifacts),
            "--cwd",
            str(tmp_path),
            "--timeout-seconds",
            "2",
            "--",
            sys.executable,
            "-c",
            "print('synthetic')",
        )
    )
    assert result == 0
    attempt = artifacts / "synthetic/RUN-SYNTHETIC-001/attempt-0001"
    assert attempt.is_dir()
    assert run(("validate-artifacts", str(attempt), "--schema-root", str(ROOT))) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert '"status": "completed"' in captured.out
    assert "Artifact directory is valid" in captured.out


def test_cli_refuses_live_execution_under_disabled_project_state(
    tmp_path: Path, capsys: object
) -> None:
    project = tmp_path / "project"
    write_project_state(project, prototype=False)
    command = CommandSpec(
        argv=(sys.executable, "-c", "pass"),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = write_plan(tmp_path / "plan.json", authorized=True, command=command)
    artifacts = tmp_path / "artifacts"
    result = run(
        (
            "run-local",
            str(plan),
            "--project-root",
            str(project),
            "--schema-root",
            str(ROOT),
            "--artifact-workspace",
            str(artifacts),
            "--cwd",
            str(tmp_path),
            "--timeout-seconds",
            "2",
            "--",
            sys.executable,
            "-c",
            "pass",
        )
    )
    assert result == 1
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "disallows prototype" in captured.err
    assert list(artifacts.iterdir()) == []


def test_adapterless_cli_refuses_nonwall_projection_before_execution(
    tmp_path: Path,
    capsys: object,
) -> None:
    project = tmp_path / "project"
    write_project_state(project, prototype=True)
    marker = tmp_path / "must-not-exist"
    script = f"from pathlib import Path; Path({str(marker)!r}).touch()"
    command = CommandSpec(
        argv=(sys.executable, "-c", script),
        cwd=tmp_path,
        timeout_seconds=2,
        resource_projection=ResourceProjection(
            tool_calls=1,
            enforcement=IncrementalLimitEnforcement.ADAPTER_COMMAND,
        ),
    )
    plan = write_plan(
        tmp_path / "plan.json",
        authorized=True,
        command=command,
        max_tool_calls=1,
    )
    artifacts = tmp_path / "artifacts"
    result = run(
        (
            "run-local",
            str(plan),
            "--project-root",
            str(project),
            "--schema-root",
            str(ROOT),
            "--artifact-workspace",
            str(artifacts),
            "--cwd",
            str(tmp_path),
            "--timeout-seconds",
            "2",
            "--projected-tool-calls",
            "1",
            "--incremental-limit-enforcement",
            "adapter-command",
            "--",
            sys.executable,
            "-c",
            script,
        )
    )
    assert result == 1
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "cannot close non-wall resource accounting" in captured.err
    assert not marker.exists()
    assert not artifacts.exists()


def test_adapterless_cli_seals_an_attached_budget_failure_session(
    tmp_path: Path,
    capsys: object,
) -> None:
    project = tmp_path / "project"
    write_project_state(project, prototype=True)
    script = "import os; os.write(1, b'x' * 131072)"
    command = CommandSpec(
        argv=(sys.executable, "-c", script),
        cwd=tmp_path,
        timeout_seconds=2,
    )
    plan = write_plan(
        tmp_path / "plan.json",
        authorized=True,
        command=command,
        max_output_bytes=128,
    )
    artifacts = tmp_path / "artifacts"
    result = run(
        (
            "run-local",
            str(plan),
            "--project-root",
            str(project),
            "--schema-root",
            str(ROOT),
            "--artifact-workspace",
            str(artifacts),
            "--cwd",
            str(tmp_path),
            "--timeout-seconds",
            "2",
            "--",
            sys.executable,
            "-c",
            script,
        )
    )
    assert result == 1
    attempt = artifacts / "synthetic/RUN-SYNTHETIC-001/attempt-0001"
    assert run(("validate-artifacts", str(attempt), "--schema-root", str(ROOT))) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "hard budget" in captured.err
    assert "Artifact directory is valid" in captured.out
