"""Test-only construction of an exact untracked successor package."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from giclab.harness import (
    t09_pragmatic_provider,
    t09_provider_contracts,
    t09_sira_pilot,
)
from giclab.harness.t09_provider_contracts import T09ProviderContract
from giclab.harness.t09_sira_pilot import command_argv_sha256

_EXPERIMENT = "experiments/EXP-0001-sira-simulative-vs-reactive"
_V16_PLAN = f"{_EXPERIMENT}/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V16.yaml"
_V17_PLAN = f"{_EXPERIMENT}/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V17.yaml"
_V16_EXECUTION = f"{_EXPERIMENT}/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V16.json"
_V17_EXECUTION = f"{_EXPERIMENT}/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V17.json"
_V16_COMMAND = f"{_EXPERIMENT}/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V16.json"
_V17_COMMAND = f"{_EXPERIMENT}/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V17.json"
_HEX_IDENTITY_LENGTHS = {40, 64}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _successor_string(value: str) -> str:
    if len(value) in _HEX_IDENTITY_LENGTHS and all(
        character in "0123456789abcdef" for character in value
    ):
        return value
    return value.replace("V16", "V17").replace("v16", "v17").replace("0009", "0010")


def _successor_value(value: Any) -> Any:
    if isinstance(value, str):
        return _successor_string(value)
    if isinstance(value, list):
        return [_successor_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _successor_value(item) for key, item in value.items()}
    return value


def _write_relative(repository: Path, relative: str, encoded: bytes) -> None:
    path = repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)


def copy_working_repository(source: Path, destination: Path) -> None:
    """Copy current task files while retaining historical Git objects for fixtures."""

    subprocess.run(
        ["git", "clone", "--shared", "--quiet", str(source), str(destination)],
        check=True,
    )
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        capture_output=True,
        check=True,
    )
    for encoded_relative in completed.stdout.split(b"\0"):
        if not encoded_relative:
            continue
        relative = encoded_relative.decode("utf-8")
        source_path = source / relative
        destination_path = destination / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path, follow_symlinks=False)


def commit_repository(repository: Path) -> tuple[str, str]:
    """Create a deterministic local-only commit for immutable-receipt tests."""

    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_DATE": "2026-09-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-09-01T00:00:00+00:00",
    }
    if not (repository / ".git").is_dir():
        subprocess.run(["git", "init", "-q", str(repository)], env=environment, check=True)
    subprocess.run(["git", "-C", str(repository), "add", "--all"], env=environment, check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=GIC Lab Test",
            "-c",
            "user.email=gic-lab-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "synthetic successor fixture",
        ],
        env=environment,
        check=True,
    )
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD", "HEAD^{tree}"],
        env=environment,
        capture_output=True,
        check=True,
        text=True,
    )
    commit, tree = completed.stdout.splitlines()
    return commit, tree


def materialize_synthetic_successor(source: Path, repository: Path) -> dict[str, object]:
    """Write test-owned V17 package data and return its exact byte identities."""

    goal_path = repository / "control/goals/EXP-0001.yaml"
    if not goal_path.exists():
        _write_relative(
            repository,
            "control/goals/EXP-0001.yaml",
            (source / "control/goals/EXP-0001.yaml").read_bytes(),
        )
    target_schema = repository / "schemas/t09-control-target.schema.json"
    if not target_schema.exists():
        _write_relative(
            repository,
            "schemas/t09-control-target.schema.json",
            (source / "schemas/t09-control-target.schema.json").read_bytes(),
        )

    goal = yaml.safe_load(goal_path.read_text(encoding="utf-8"))
    goal["runtime_package"]["next_status"] = "package-bound-not-authorized"
    goal_path.write_text(yaml.safe_dump(goal, sort_keys=False), encoding="utf-8")

    plan = _successor_value(yaml.safe_load((source / _V16_PLAN).read_text(encoding="utf-8")))
    execution = _successor_value(json.loads((source / _V16_EXECUTION).read_bytes()))
    command = _successor_value(json.loads((source / _V16_COMMAND).read_bytes()))
    assert isinstance(plan, dict) and isinstance(execution, dict) and isinstance(command, dict)

    raw_attempts = execution["attempts"]
    assert isinstance(raw_attempts, list)
    condition_identities: dict[str, tuple[int, str]] = {}
    for attempt in raw_attempts:
        assert isinstance(attempt, dict)
        source_condition = str(attempt["condition_plan_path"]).replace("v17", "v16")
        condition = _successor_value(
            yaml.safe_load((source / source_condition).read_text(encoding="utf-8"))
        )
        assert isinstance(condition, dict)
        authorization = condition["execution"]["authorization"]
        assert isinstance(authorization, dict)
        authorization["command_sha256"] = _canonical_sha256(attempt["upstream_argv"])
        encoded_condition = yaml.safe_dump(condition, sort_keys=False).encode()
        relative_condition = str(attempt["condition_plan_path"])
        _write_relative(repository, relative_condition, encoded_condition)
        condition_sha256 = hashlib.sha256(encoded_condition).hexdigest()
        attempt["condition_plan_sha256"] = condition_sha256
        condition_identities[str(attempt["run_id"])] = (
            len(encoded_condition),
            condition_sha256,
        )

    encoded_plan = yaml.safe_dump(plan, sort_keys=False).encode()
    _write_relative(repository, _V17_PLAN, encoded_plan)
    plan_sha256 = hashlib.sha256(encoded_plan).hexdigest()
    bindings = execution["contract_bindings"]
    assert isinstance(bindings, dict) and isinstance(bindings["plan"], dict)
    bindings["plan"].update(
        {"path": _V17_PLAN, "sha256": plan_sha256, "size_bytes": len(encoded_plan)}
    )

    encoded_execution = _json_bytes(execution)
    _write_relative(repository, _V17_EXECUTION, encoded_execution)
    execution_sha256 = hashlib.sha256(encoded_execution).hexdigest()

    command.update(
        {
            "plan_id": "PLAN-EXP0001-PILOT-V17",
            "plan_path": _V17_PLAN,
            "plan_sha256": plan_sha256,
            "plan_size_bytes": len(encoded_plan),
            "execution_contract_path": _V17_EXECUTION,
            "execution_contract_sha256": execution_sha256,
        }
    )
    manifests = command["manifests"]
    assert isinstance(manifests, list)
    attempts_by_run = {
        str(attempt["run_id"]): attempt for attempt in raw_attempts if isinstance(attempt, dict)
    }
    for manifest in manifests:
        assert isinstance(manifest, dict)
        attempt = attempts_by_run[str(manifest["run_id"])]
        argv = manifest["argv"]
        assert isinstance(argv, list)
        separator = argv.index("--")
        manifest["argv"] = [*argv[: separator + 1], *attempt["upstream_argv"]]
        manifest["argv_sha256"] = command_argv_sha256(manifest["argv"])
        manifest["execution_contract_sha256"] = execution_sha256
        manifest["condition_plan_sha256"] = attempt["condition_plan_sha256"]
        permitted = manifest.get("permitted_condition_owned")
        if isinstance(permitted, dict):
            permitted["condition_plan_sha256"] = attempt["condition_plan_sha256"]
    encoded_command = _json_bytes(command)
    _write_relative(repository, _V17_COMMAND, encoded_command)
    command_sha256 = hashlib.sha256(encoded_command).hexdigest()
    return {
        "plan_bytes": len(encoded_plan),
        "plan_sha256": plan_sha256,
        "execution_sha256": execution_sha256,
        "command_sha256": command_sha256,
        "condition_identities": condition_identities,
    }


def synthetic_contract(
    identities: dict[str, object],
    *,
    source_commit: str = "0" * 40,
) -> T09ProviderContract:
    """Derive the test-only central declaration from V16's semantic capabilities."""

    retained = t09_provider_contracts.V16_PROVIDER_CONTRACT
    return replace(
        retained,
        version="V17",
        source_commit=source_commit,
        plan_id="PLAN-EXP0001-PILOT-V17",
        host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0010",
        authorization_prefix="AUTH-T09-V17-",
        instance_name="giclab-t09-pilot-v17-autonomous-0010",
        plan_path=_V17_PLAN,
        expected_plan_bytes=int(identities["plan_bytes"]),
        expected_plan_sha256=str(identities["plan_sha256"]),
        provider_profile_id="PLAN-EXP0001-PILOT-V17",
        provider_profile_path=_V17_PLAN,
        expected_provider_profile_bytes=int(identities["plan_bytes"]),
        expected_provider_profile_sha256=str(identities["plan_sha256"]),
        execution_contract_path=_V17_EXECUTION,
        command_manifest_path=_V17_COMMAND,
        expected_command_manifest_sha256=str(identities["command_sha256"]),
        frozen_run_manifest_id="RUN-MANIFEST-EXP0001-PILOT-V17-AUTONOMOUS-0010",
        local_finalizer_qualification_id=("QUAL-T09-PILOT-V17-LOCAL-FINALIZER-AUTONOMOUS-0010"),
        evaluator_run_ids=tuple(_successor_string(item) for item in retained.evaluator_run_ids),
        control_root_name="pilot-v17",
        evidence_archive_id="ARCHIVE-EXP0001-PILOT-V17-AUTONOMOUS-0010",
        evidence_stage_id="STAGE-EXP0001-PILOT-V17-AUTONOMOUS-0010",
        run_ids=tuple(_successor_string(item) for item in retained.run_ids),
        image_qualification_ids=("QUAL-T09-PILOT-V17-IMAGE-AUTONOMOUS-0010",),
        active_image_qualification_id="QUAL-T09-PILOT-V17-IMAGE-AUTONOMOUS-0010",
        replacement_image_tag="giclab/t09-pilot-v17:synthetic-autonomous-0010",
        container_prefix="giclab-t09-pilot-v17-autonomous-",
    )


def install_synthetic_registry(monkeypatch: Any, contract: T09ProviderContract) -> None:
    """Install the equivalent of one future central declarative registry entry."""

    contracts = MappingProxyType(
        {**t09_provider_contracts.PROVIDER_CONTRACTS, contract.version: contract}
    )
    by_plan = MappingProxyType({item.plan_id: item for item in contracts.values()})
    monkeypatch.setattr(t09_provider_contracts, "PROVIDER_CONTRACTS", contracts)
    monkeypatch.setattr(t09_provider_contracts, "PROVIDER_CONTRACTS_BY_PLAN_ID", by_plan)
    monkeypatch.setattr(t09_sira_pilot, "PROVIDER_CONTRACTS", contracts)
    monkeypatch.setattr(t09_pragmatic_provider, "PROVIDER_CONTRACTS", contracts)
    monkeypatch.setattr(
        t09_sira_pilot,
        "_AUTONOMOUS_ATTEMPT_IDS",
        frozenset(
            run_id
            for provider in contracts.values()
            if provider.execution_contract_path is not None
            for run_id in provider.run_ids
        ),
    )
