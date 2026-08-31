"""Stable, network-disabled CLI for the agent/control foundation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml

from giclab.control.agent_check import run_agent_check
from giclab.control.composition import compose_control_plane
from giclab.control.incidents import validate_incidents
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.shadow import run_required_shadow_matrix, run_shadow_scenario
from giclab.control.state_capsule import generate_state_capsule
from giclab.control.version_lint import validate_active_version_dispatch
from giclab.harness.t09_provider_contracts import PROVIDER_CONTRACTS, provider_contract


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()


def _semantic_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write_receipts(output: Path, receipts: Mapping[str, object]) -> list[dict[str, object]]:
    output.mkdir(parents=True, exist_ok=True)
    identities: list[dict[str, object]] = []
    for name, receipt in receipts.items():
        path = output / f"{name}.json"
        encoded = _json_bytes(receipt)
        path.write_bytes(encoded)
        identities.append(
            {
                "scenario": name,
                "path": path.name,
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    return identities


def _bootstrap_capsule(
    repository: Path,
    *,
    registry_complete: bool,
    composition_valid: bool,
    lint_valid: bool,
) -> dict[str, object]:
    return generate_state_capsule(
        repository,
        registry_complete=registry_complete,
        composition_valid=composition_valid,
        version_lint_valid=lint_valid,
        shadow_happy_path=False,
        failure_matrix_valid=False,
        deterministic=True,
    )


def _verified_capsule(repository: Path, *, deterministic: bool) -> dict[str, object]:
    lint = validate_active_version_dispatch(repository)
    registry = validate_registry_completeness(repository)
    composition = compose_control_plane(
        repository,
        contract=provider_contract("V16"),  # giclab-version-lint: historical-identity
        registry_receipt=registry,
        version_lint_receipt=lint,
    )
    bootstrap = _bootstrap_capsule(
        repository,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        lint_valid=lint.get("complete") is True,
    )
    shadows = run_required_shadow_matrix(
        repository,
        contract=provider_contract("V16"),  # giclab-version-lint: historical-identity
        state_capsule_sha256=str(bootstrap["semantic_sha256"]),
    )
    shadow_valid = all(receipt.get("scenario_valid") is True for receipt in shadows.values())
    return generate_state_capsule(
        repository,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        version_lint_valid=lint.get("complete") is True,
        shadow_happy_path=(
            shadows["happy-path"].get("terminal_state") == "category3-shadow-complete-clean"
        ),
        failure_matrix_valid=shadow_valid,
        deterministic=deterministic,
    )


def _command_state_capsule(args: argparse.Namespace) -> tuple[object, bool]:
    capsule = _verified_capsule(args.repository, deterministic=args.deterministic)
    return capsule, True


def _command_registry(args: argparse.Namespace) -> tuple[object, bool]:
    receipt = validate_registry_completeness(args.repository)
    return receipt, receipt.get("complete") is True


def _command_version_lint(args: argparse.Namespace) -> tuple[object, bool]:
    receipt = validate_active_version_dispatch(args.repository)
    return receipt, receipt.get("complete") is True


def _command_compose(args: argparse.Namespace) -> tuple[object, bool]:
    lint = validate_active_version_dispatch(args.repository)
    registry = validate_registry_completeness(args.repository)
    contracts = (
        tuple(PROVIDER_CONTRACTS.values())
        if args.all_registered
        else (provider_contract(args.provider_contract),)
    )
    receipts = {
        contract.version: compose_control_plane(
            args.repository,
            contract=contract,
            registry_receipt=registry,
            version_lint_receipt=lint,
        )
        for contract in contracts
    }
    complete = all(receipt.get("static_composition_valid") is True for receipt in receipts.values())
    if not args.all_registered:
        return next(iter(receipts.values())), complete
    aggregate: dict[str, object] = {
        "schema_version": "1.0.0",
        "contract_count": len(receipts),
        "receipts": receipts,
        "complete": complete,
    }
    aggregate["semantic_sha256"] = _semantic_sha256(aggregate)
    return aggregate, complete


def _command_shadow(args: argparse.Namespace) -> tuple[object, bool]:
    contract = provider_contract(args.provider_contract)
    lint = validate_active_version_dispatch(args.repository)
    registry = validate_registry_completeness(args.repository)
    composition = compose_control_plane(
        args.repository,
        contract=contract,
        registry_receipt=registry,
        version_lint_receipt=lint,
    )
    bootstrap = _bootstrap_capsule(
        args.repository,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        lint_valid=lint.get("complete") is True,
    )
    if args.all_required:
        receipts = run_required_shadow_matrix(
            args.repository,
            contract=contract,
            state_capsule_sha256=str(bootstrap["semantic_sha256"]),
            fixed_tick=args.fixed_tick,
        )
    else:
        receipt = run_shadow_scenario(
            args.repository,
            contract=contract,
            scenario=args.scenario,
            state_capsule_sha256=str(bootstrap["semantic_sha256"]),
            fixed_tick=args.fixed_tick,
        )
        receipts = {args.scenario: receipt}
    written = _write_receipts(args.output, receipts) if args.output is not None else []
    complete = all(receipt.get("scenario_valid") is True for receipt in receipts.values())
    aggregate: dict[str, object] = {
        "schema_version": "1.0.0",
        "provider_contract_version": contract.version,
        "scenario_count": len(receipts),
        "receipts": receipts,
        "written_receipts": written,
        "complete": complete,
    }
    aggregate["semantic_sha256"] = _semantic_sha256(aggregate)
    return aggregate, complete


def _command_incidents(args: argparse.Namespace) -> tuple[object, bool]:
    receipt = validate_incidents(args.repository, execute_regressions=True)
    return receipt, receipt.get("complete") is True


def _command_agent_check(args: argparse.Namespace) -> tuple[object, bool]:
    receipt = run_agent_check(args.repository, execute_incident_regressions=True)
    return receipt, receipt.get("complete") is True


def _repository_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="explicit repository root (default: current directory)",
    )


def _output_file_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-file",
        type=Path,
        help="also write the emitted structured receipt to this explicit path",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="giclab-control")
    subcommands = parser.add_subparsers(dest="command", required=True)

    capsule = subcommands.add_parser("state-capsule")
    _repository_argument(capsule)
    _output_file_argument(capsule)
    capsule.add_argument("--deterministic", action="store_true")
    capsule.add_argument("--format", choices=("json", "yaml"), default="json")
    capsule.set_defaults(handler=_command_state_capsule)

    registry = subcommands.add_parser("registry-check")
    _repository_argument(registry)
    _output_file_argument(registry)
    registry.set_defaults(handler=_command_registry)

    lint = subcommands.add_parser("version-lint")
    _repository_argument(lint)
    _output_file_argument(lint)
    lint.set_defaults(handler=_command_version_lint)

    compose = subcommands.add_parser("compose")
    _repository_argument(compose)
    _output_file_argument(compose)
    compose_selection = compose.add_mutually_exclusive_group(required=True)
    compose_selection.add_argument("--provider-contract")
    compose_selection.add_argument("--all-registered", action="store_true")
    compose.set_defaults(handler=_command_compose)

    shadow = subcommands.add_parser("shadow")
    _repository_argument(shadow)
    shadow.add_argument("--provider-contract", required=True)
    shadow_selection = shadow.add_mutually_exclusive_group(required=True)
    shadow_selection.add_argument("--scenario")
    shadow_selection.add_argument("--all-required", action="store_true")
    shadow.add_argument("--fixed-tick", type=int, default=1000)
    shadow.add_argument("--output", type=Path)
    shadow.set_defaults(handler=_command_shadow)

    incidents = subcommands.add_parser("incident-check")
    _repository_argument(incidents)
    _output_file_argument(incidents)
    incidents.set_defaults(handler=_command_incidents)

    agent = subcommands.add_parser("agent-check")
    _repository_argument(agent)
    _output_file_argument(agent)
    agent.set_defaults(handler=_command_agent_check)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result, success = args.handler(args)
    except Exception as exc:
        print(f"giclab-control: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(json.dumps({"complete": False, "error": str(exc)}, sort_keys=True))
        return 1
    output_file = getattr(args, "output_file", None)
    if isinstance(output_file, Path):
        output_file.parent.mkdir(parents=True, exist_ok=True)
        if args.command == "state-capsule" and args.format == "yaml":
            output_file.write_text(yaml.safe_dump(result, sort_keys=True), encoding="utf-8")
        else:
            output_file.write_bytes(_json_bytes(result))
    if args.command == "state-capsule" and args.format == "yaml":
        print(yaml.safe_dump(result, sort_keys=True), end="")
    else:
        sys.stdout.buffer.write(_json_bytes(result))
    print(
        f"giclab-control {args.command}: {'passed' if success else 'failed'}",
        file=sys.stderr,
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
