"""Stable, network-disabled CLI for the agent/control foundation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml

from giclab.control.agent_check import run_agent_check
from giclab.control.composition import compose_control_plane
from giclab.control.incidents import validate_incidents
from giclab.control.proofs import (
    REPOSITORY_SLUG,
    ControlProofReference,
    generate_control_binding_document,
    generate_source_binding_receipt,
    validate_control_receipt_set,
)
from giclab.control.registry_validation import validate_registry_completeness
from giclab.control.scenarios import HAPPY_PATH, REQUIRED_FAILURE_SCENARIOS
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


def _write_json(path: Path, document: object) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _json_bytes(document)
    path.write_bytes(encoded)
    semantic = document.get("semantic_sha256") if isinstance(document, dict) else None
    return {
        "path": path.as_posix(),
        "bytes": len(encoded),
        "file_sha256": hashlib.sha256(encoded).hexdigest(),
        "semantic_sha256": semantic,
    }


def _clean_git_identity(repository: Path) -> tuple[str, str]:
    status = subprocess.run(
        ["git", "-C", str(repository), "status", "--porcelain=v1", "--untracked-files=all"],
        capture_output=True,
        check=True,
        text=True,
    )
    dirty_paths = []
    for line in status.stdout.splitlines():
        relative = line[3:]
        if " -> " in relative:
            relative = relative.split(" -> ", maxsplit=1)[1]
        if not relative.startswith("control/receipts/"):
            dirty_paths.append(relative)
    if dirty_paths:
        raise ValueError(
            "receipt refresh requires an immutable implementation ancestor; "
            "non-receipt paths are dirty: " + ", ".join(dirty_paths)
        )
    identity = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD", "HEAD^{tree}"],
        capture_output=True,
        check=True,
        text=True,
    )
    commit, tree = identity.stdout.splitlines()
    return commit, tree


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
        state_capsule=bootstrap,
        registry_receipt=registry,
        version_lint_receipt=lint,
        composition_receipt=composition,
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
            state_capsule=bootstrap,
            registry_receipt=registry,
            version_lint_receipt=lint,
            composition_receipt=composition,
            fixed_tick=args.fixed_tick,
        )
    else:
        receipt = run_shadow_scenario(
            args.repository,
            contract=contract,
            scenario=args.scenario,
            state_capsule=bootstrap,
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


def _command_refresh_receipts(args: argparse.Namespace) -> tuple[object, bool]:
    """Regenerate the complete non-circular control evidence from clean HEAD."""

    repository = args.repository.resolve(strict=True)
    output = repository / "control/receipts"
    commit, tree = _clean_git_identity(repository)
    contract = provider_contract("V16")  # giclab-version-lint: historical-identity

    lint = validate_active_version_dispatch(repository)
    registry = validate_registry_completeness(repository)
    composition = compose_control_plane(
        repository,
        contract=contract,
        registry_receipt=registry,
        version_lint_receipt=lint,
    )
    bootstrap_capsule = _bootstrap_capsule(
        repository,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        lint_valid=lint.get("complete") is True,
    )
    shadows = run_required_shadow_matrix(
        repository,
        contract=contract,
        state_capsule=bootstrap_capsule,
        registry_receipt=registry,
        version_lint_receipt=lint,
        composition_receipt=composition,
    )
    shadow_complete = all(receipt.get("scenario_valid") is True for receipt in shadows.values())
    capsule = generate_state_capsule(
        repository,
        registry_complete=registry.get("complete") is True,
        composition_valid=composition.get("static_composition_valid") is True,
        version_lint_valid=lint.get("complete") is True,
        shadow_happy_path=(
            shadows[HAPPY_PATH].get("terminal_state") == "category3-shadow-complete-clean"
        ),
        failure_matrix_valid=shadow_complete,
        deterministic=True,
    )
    incidents = validate_incidents(repository, execute_regressions=True)
    source_binding = generate_source_binding_receipt(
        repository,
        source_commit=commit,
        source_tree=tree,
    )
    agent_check = run_agent_check(repository, execute_incident_regressions=True)

    written = [
        _write_json(output / "active-version-lint.json", lint),
        _write_json(output / "registry-completeness.json", registry),
        _write_json(output / "v16-composition.json", composition),
        _write_json(output / "state-capsule.json", capsule),
        _write_json(output / "incidents.json", incidents),
        _write_json(output / "t09-control-plane-source-binding.json", source_binding),
    ]
    shadow_root = output / "category3-shadow"
    for scenario, receipt in shadows.items():
        written.append(_write_json(shadow_root / f"{scenario}.json", receipt))
    written.append(_write_json(output / "agent-check.json", agent_check))

    command_sha = composition.get("command_package_sha256")
    if not isinstance(command_sha, str):
        raise ValueError("composition lacks the command package identity")
    binding = generate_control_binding_document(
        repository,
        output,
        control_commit=commit,
        control_tree=tree,
        contract=contract,
        command_package_sha256=command_sha,
        registry_receipt=output / "registry-completeness.json",
        active_version_lint_receipt=output / "active-version-lint.json",
        composition_receipt=output / "v16-composition.json",
        state_capsule=output / "state-capsule.json",
        shadow_happy_path=shadow_root / f"{HAPPY_PATH}.json",
        shadow_failures={
            scenario: shadow_root / f"{scenario}.json" for scenario in REQUIRED_FAILURE_SCENARIOS
        },
        agent_check_receipt=output / "agent-check.json",
        source_binding_receipt=output / "t09-control-plane-source-binding.json",
        incident_receipt=output / "incidents.json",
    )
    binding_identity = _write_json(output / "t09-control-receipt-bindings.json", binding)
    binding_sha = binding_identity["file_sha256"]
    assert isinstance(binding_sha, str)
    validate_control_receipt_set(
        repository,
        contract,
        ControlProofReference(
            approved_root=output,
            binding_path=output / "t09-control-receipt-bindings.json",
            expected_file_sha256=binding_sha,
            expected_control_commit=commit,
            expected_control_tree=tree,
            expected_repository_slug=REPOSITORY_SLUG,
            expected_provider_contract_version=contract.version,
            expected_plan_id=contract.plan_id,
            expected_command_package_sha256=command_sha,
        ),
    )
    written.append(binding_identity)
    complete = all(
        (
            lint.get("complete") is True,
            registry.get("complete") is True,
            composition.get("static_composition_valid") is True,
            shadow_complete,
            incidents.get("complete") is True,
            agent_check.get("complete") is True,
        )
    )
    result: dict[str, object] = {
        "schema_version": "1.0.0",
        "control_commit": commit,
        "control_tree": tree,
        "binding_file_sha256": binding_sha,
        "receipt_count": len(written),
        "receipts": written,
        "complete": complete,
    }
    result["semantic_sha256"] = _semantic_sha256(result)
    return result, complete


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

    refresh = subcommands.add_parser("refresh-receipts")
    _repository_argument(refresh)
    refresh.set_defaults(handler=_command_refresh_receipts)
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
