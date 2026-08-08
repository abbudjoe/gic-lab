"""Command-line interface for the generic GIC Lab experiment harness."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from giclab.registry import discover_repo_root

from .artifacts import ArtifactError, ArtifactWorkspace, validate_artifact_directory
from .budget import BudgetContractChanged, BudgetExceeded
from .events import EventStreamError
from .executor import LocalExecutionError, LocalRunExecutor, render_command
from .models import (
    CommandSpec,
    IncrementalLimitEnforcement,
    ResourceProjection,
    command_sha256,
    inherited_environment_binding,
)
from .plan import RunPlanError, load_run_plan
from .policy import ExecutionDisallowed, load_project_execution_state


def _add_command_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="subprocess working directory")
    parser.add_argument("--timeout-seconds", type=int, required=True, help="hard process timeout")
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="non-secret literal environment entry; repeatable",
    )
    parser.add_argument(
        "--inherit-env",
        action="append",
        default=[],
        metavar="NAME",
        help="non-secret host environment name to inherit; repeatable",
    )
    parser.add_argument(
        "--secret-env",
        action="append",
        default=[],
        metavar="NAME",
        help="secret host environment name to inject and redact; repeatable",
    )
    parser.add_argument("--projected-cost-usd", type=float, default=0.0)
    parser.add_argument("--projected-gpu-hours", type=float, default=0.0)
    parser.add_argument("--projected-model-tokens", type=int, default=0)
    parser.add_argument("--projected-tool-calls", type=int, default=0)
    parser.add_argument(
        "--incremental-limit-enforcement",
        choices=tuple(item.value for item in IncrementalLimitEnforcement),
        default=IncrementalLimitEnforcement.NOT_APPLICABLE.value,
        help="adapter command contract for projected non-wall resource maxima",
    )


def _build_parser() -> argparse.ArgumentParser:
    root = discover_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)

    validate_plan = subparsers.add_parser("validate-plan", help="validate one run plan")
    validate_plan.add_argument("plan", type=Path)
    validate_plan.add_argument("--schema-root", type=Path, default=root)

    render = subparsers.add_parser("render-command", help="render without executing")
    render.add_argument("plan", type=Path)
    render.add_argument("--schema-root", type=Path, default=root)
    _add_command_arguments(render)

    run = subparsers.add_parser("run-local", help="dry-run or execute one local run")
    run.add_argument("plan", type=Path)
    run.add_argument("--project-root", type=Path, default=root)
    run.add_argument("--schema-root", type=Path, default=root)
    run.add_argument("--artifact-workspace", type=Path, required=True)
    run.add_argument("--dry-run", action="store_true")
    _add_command_arguments(run)

    validate_artifacts = subparsers.add_parser(
        "validate-artifacts", help="validate one completed attempt directory"
    )
    validate_artifacts.add_argument("artifact_directory", type=Path)
    validate_artifacts.add_argument("--schema-root", type=Path, default=root)
    return parser


def _environment(entries: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"--env requires NAME=VALUE, got {entry!r}")
        name, value = entry.split("=", maxsplit=1)
        if name in result:
            raise ValueError(f"duplicate --env name: {name}")
        result[name] = value
    return result


def _command_spec(args: argparse.Namespace, command: Sequence[str]) -> CommandSpec:
    inherited = []
    seen: set[str] = set()
    for name in args.inherit_env:
        if name in seen:
            raise ValueError(f"duplicate --inherit-env name: {name}")
        seen.add(name)
        value = os.environ.get(name)
        if value is None:
            raise ValueError(f"cannot bind missing inherited environment variable: {name}")
        inherited.append(inherited_environment_binding(name, value))
    return CommandSpec(
        argv=tuple(command),
        cwd=args.cwd,
        timeout_seconds=args.timeout_seconds,
        environment=_environment(args.env),
        inherit_environment=tuple(inherited),
        secret_environment=tuple(args.secret_env),
        resource_projection=ResourceProjection(
            cost_usd=args.projected_cost_usd,
            gpu_hours=args.projected_gpu_hours,
            model_tokens=args.projected_model_tokens,
            tool_calls=args.projected_tool_calls,
            enforcement=IncrementalLimitEnforcement(args.incremental_limit_enforcement),
        ),
    )


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def run(argv: Sequence[str] | None = None) -> int:
    """Run one CLI operation and return its process exit code."""

    raw_arguments = list(argv) if argv is not None else sys.argv[1:]
    command: list[str] = []
    if "--" in raw_arguments:
        delimiter = raw_arguments.index("--")
        command = raw_arguments[delimiter + 1 :]
        raw_arguments = raw_arguments[:delimiter]
    args = _build_parser().parse_args(raw_arguments)
    try:
        if args.operation == "validate-plan":
            load_run_plan(args.plan, schema_root=args.schema_root.resolve())
            print(f"Run plan is valid: {args.plan}")
            return 0
        if args.operation == "validate-artifacts":
            errors = validate_artifact_directory(
                args.artifact_directory, schema_root=args.schema_root.resolve()
            )
            if errors:
                print("Artifact validation failed:", file=sys.stderr)
                for error in errors:
                    print(f"- {error}", file=sys.stderr)
                return 1
            print(f"Artifact directory is valid: {args.artifact_directory}")
            return 0

        plan = load_run_plan(args.plan, schema_root=args.schema_root.resolve())
        command_spec = _command_spec(args, command)
        if args.operation == "render-command":
            _print_json(
                {
                    "command": render_command(command_spec),
                    "command_sha256": command_sha256(command_spec),
                }
            )
            return 0
        if args.operation != "run-local":  # pragma: no cover - argparse controls choices
            raise AssertionError(f"unsupported operation: {args.operation}")
        project_root = args.project_root.resolve()
        state = load_project_execution_state(
            project_root,
            schema_root=args.schema_root.resolve(),
        )
        if not args.dry_run and command_spec.resource_projection.has_usage:
            raise ExecutionDisallowed(
                "adapterless run-local cannot close non-wall resource accounting; "
                "use the typed adapter API"
            )
        workspace = ArtifactWorkspace.open(args.artifact_workspace, create=not args.dry_run)
        executor = LocalRunExecutor(workspace)
        if args.dry_run:
            report = executor.dry_run(plan, command_spec, state)
            _print_json(
                {
                    "status": "dry-run",
                    "executed": False,
                    "execution_allowed": report.execution_allowed,
                    "blockers": list(report.blockers),
                    "command": report.command,
                    "command_sha256": report.command_sha256,
                    "prospective_artifact_directory": str(report.prospective_artifact_directory),
                }
            )
            return 0
        session = executor.execute(plan, command_spec, state)
        outcome = session.seal()
        _print_json(
            {
                "status": outcome.status,
                "return_code": outcome.return_code,
                "wall_seconds": outcome.wall_seconds,
                "timed_out": outcome.timed_out,
                "events": str(outcome.events_path),
                "artifact_records": str(outcome.artifact_records_path),
            }
        )
        if outcome.timed_out:
            return 124
        return outcome.return_code if 0 <= outcome.return_code <= 255 else 1
    except LocalExecutionError as exc:
        if exc.session is not None and not exc.session.sealed:
            try:
                exc.session.seal()
            except (LocalExecutionError, OSError, ValueError) as seal_error:
                print(
                    "giclab-harness: failure session remains open for adapter normalization: "
                    f"{seal_error}",
                    file=sys.stderr,
                )
        print(f"giclab-harness: {exc}", file=sys.stderr)
        return 1
    except (
        ArtifactError,
        BudgetContractChanged,
        BudgetExceeded,
        EventStreamError,
        ExecutionDisallowed,
        OSError,
        RunPlanError,
        ValueError,
    ) as exc:
        print(f"giclab-harness: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
