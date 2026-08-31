from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from giclab.harness.t09_provider_contracts import V15_PROVIDER_CONTRACT
from giclab.harness.t09_sira_pilot import (
    T09PilotError,
    command_argv_sha256,
    file_sha256,
    load_execution_contract,
    render_command_manifest,
)
from giclab.validation import (
    _validate_t09_command_manifest_hashes,
    validate_t09_v11_plan,
    validate_t09_v12_plan,
    validate_t09_v13_plan,
    validate_t09_v14_plan,
    validate_t09_v15_plan,
)

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
EXECUTION = EXP / "contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V15.json"
COMMANDS = EXP / "contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V15.json"
STOPPED = EXP / "T09_V15_PRELIVE_COMMAND_MANIFEST_STOPPED_DISPOSITION.json"
RUNTIME_ADAPTATION = ROOT / "src/giclab/harness/sira_gate_a_runtime.py"
PILOT_LIBRARY = ROOT / "src/giclab/harness/t09_sira_pilot.py"
MERGED_DEFECT_COMMIT = "bce89afa79a120f7f5acb22fb20512ec9581f7a5"
COMMANDS_RELATIVE = COMMANDS.relative_to(ROOT).as_posix()
EXECUTION_RELATIVE = EXECUTION.relative_to(ROOT).as_posix()
RUNTIME_ADAPTATION_RELATIVE = RUNTIME_ADAPTATION.relative_to(ROOT).as_posix()
PILOT_LIBRARY_RELATIVE = PILOT_LIBRARY.relative_to(ROOT).as_posix()


def _load_script(name: str, relative: str) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


FREEZE = _load_script(
    "giclab_test_t09_v15_freeze_commands",
    "containers/sira-smoke/pragmatic/t09_freeze_commands.py",
)
PREFLIGHT = _load_script(
    "giclab_test_t09_v15_preflight",
    "containers/sira-smoke/pragmatic/t09_preflight.py",
)


def _direct_manifests() -> list[dict[str, object]]:
    contract = load_execution_contract(EXECUTION, expected_sha256=file_sha256(EXECUTION))
    control_root = V15_PROVIDER_CONTRACT.control_root_name
    return [
        render_command_manifest(
            contract,
            attempt,
            execution_contract_runtime_path="/opt/giclab-contracts/execution.json",
            runtime_adaptation_path="/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
            runtime_adaptation_sha256=file_sha256(RUNTIME_ADAPTATION),
            pilot_library_sha256=file_sha256(PILOT_LIBRARY),
            aggregate_ledger_path=(
                f"/opt/giclab-artifacts/{control_root}/runtime-budget/aggregate-budget.json"
            ),
            pilot_state_path=f"/opt/giclab-artifacts/{control_root}/pilot-state.json",
        )
        for attempt in contract.attempts
    ]


def _stored_manifests() -> list[dict[str, Any]]:
    document = json.loads(COMMANDS.read_text(encoding="utf-8"))
    return cast(list[dict[str, Any]], document["manifests"])


def _git_blob(revision: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def test_command_argv_sha256_has_one_explicit_independent_contract() -> None:
    argv = ["runner", "--label", "café", "two words"]
    independently_encoded = json.dumps(
        argv,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert command_argv_sha256(argv) == hashlib.sha256(independently_encoded).hexdigest()


@pytest.mark.parametrize(
    "invalid_argv",
    [
        [],
        ["runner", 1],
        ["runner", "embedded\0nul"],
        "runner",
    ],
)
def test_command_argv_sha256_rejects_invalid_surfaces(invalid_argv: object) -> None:
    with pytest.raises(T09PilotError):
        command_argv_sha256(cast(Sequence[str], invalid_argv))


def test_renderer_hashes_the_final_frozen_argv() -> None:
    for manifest in _direct_manifests():
        argv = cast(list[str], manifest["argv"])
        assert argv
        assert all(isinstance(item, str) and "\0" not in item for item in argv)
        assert manifest["argv_sha256"] == command_argv_sha256(argv)


def test_generator_is_byte_deterministic_and_equals_direct_render() -> None:
    first = FREEZE.render(ROOT, provider_version="V15")
    second = FREEZE.render(ROOT, provider_version="V15")
    first_bytes = FREEZE.encode_command_manifest_document(first)
    second_bytes = FREEZE.encode_command_manifest_document(second)
    assert first_bytes == second_bytes
    assert first["manifests"] == _direct_manifests()


def test_source_controlled_v15_artifact_equals_generator_bytes() -> None:
    generated = FREEZE.render(ROOT, provider_version="V15")
    first_bytes = FREEZE.encode_command_manifest_document(generated)
    assert first_bytes == COMMANDS.read_bytes()


def test_merged_v15_defect_is_retained_and_exact_preflight_rejects_it(
    tmp_path: Path,
) -> None:
    stopped = json.loads(STOPPED.read_text(encoding="utf-8"))
    assert stopped["old_package"]["merge_commit"] == MERGED_DEFECT_COMMIT
    old_document = json.loads(_git_blob(MERGED_DEFECT_COMMIT, COMMANDS_RELATIVE))
    old_manifests = old_document["manifests"]
    old_execution = _git_blob(MERGED_DEFECT_COMMIT, EXECUTION_RELATIVE)
    old_execution_path = tmp_path / "execution.json"
    old_execution_path.write_bytes(old_execution)
    old_contract = load_execution_contract(
        old_execution_path,
        expected_sha256=hashlib.sha256(old_execution).hexdigest(),
    )
    control_root = V15_PROVIDER_CONTRACT.control_root_name
    fresh_manifests = [
        render_command_manifest(
            old_contract,
            attempt,
            execution_contract_runtime_path="/opt/giclab-contracts/execution.json",
            runtime_adaptation_path="/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
            runtime_adaptation_sha256=hashlib.sha256(
                _git_blob(MERGED_DEFECT_COMMIT, RUNTIME_ADAPTATION_RELATIVE)
            ).hexdigest(),
            pilot_library_sha256=hashlib.sha256(
                _git_blob(MERGED_DEFECT_COMMIT, PILOT_LIBRARY_RELATIVE)
            ).hexdigest(),
            aggregate_ledger_path=(
                f"/opt/giclab-artifacts/{control_root}/runtime-budget/aggregate-budget.json"
            ),
            pilot_state_path=f"/opt/giclab-artifacts/{control_root}/pilot-state.json",
        )
        for attempt in old_contract.attempts
    ]
    assert len(old_manifests) == len(stopped["hash_mismatches"]) == 4
    for old, fresh, mismatch in zip(
        old_manifests,
        fresh_manifests,
        stopped["hash_mismatches"],
        strict=True,
    ):
        assert old["run_id"] == mismatch["run_id"]
        assert old["argv_sha256"] == mismatch["stored_argv_sha256"]
        assert command_argv_sha256(old["argv"]) == mismatch["fresh_argv_sha256"]
        assert old["argv"] == fresh["argv"]
        assert old["equality_surface"] == fresh["equality_surface"]
        assert fresh["argv_sha256"] == mismatch["fresh_argv_sha256"]
        assert old["argv_sha256"] != fresh["argv_sha256"]
        normalized_old = copy.deepcopy(old)
        normalized_old["argv_sha256"] = fresh["argv_sha256"]
        assert normalized_old == fresh
    assert all(item["valid"] is True for item in old_document["pair_diffs"])
    assert all(
        item["equality_surface"]["provider_contract_selector"]["value"] == "V15"
        for item in old_manifests
    )
    with pytest.raises(PREFLIGHT.PreflightError, match="stored argv self-hash invalid"):
        PREFLIGHT.validate_command_manifest_documents(old_manifests, fresh_manifests)


def _mutate_stored_manifest(
    mutation: str,
    manifests: list[dict[str, Any]],
) -> None:
    first = manifests[0]
    argv = cast(list[str], first["argv"])
    if mutation == "argv-member":
        argv[3] = "3599s"
    elif mutation == "hash-only":
        first["argv_sha256"] = "0" * 64
    elif mutation == "argv-order":
        argv[1], argv[2] = argv[2], argv[1]
    elif mutation == "argv-insert":
        argv.insert(1, "--unexpected")
    elif mutation == "argv-remove":
        argv.pop(1)
    elif mutation == "cross-run-id":
        run_flag = argv.index("--gate-pilot-attempt-id")
        argv[run_flag + 1] = manifests[1]["run_id"]
    elif mutation == "runtime-path":
        argv[5] = "/opt/giclab-src/giclab/harness/changed.py"
    elif mutation == "output-path":
        output_flag = argv.index("--gate-attempt-root")
        argv[output_flag + 1] += "-changed"
    elif mutation == "provider-selector":
        first["equality_surface"]["provider_contract_selector"]["value"] = "V14"
    elif mutation == "condition-owned":
        first["permitted_condition_owned"]["output_root"] += "-changed"
    elif mutation == "equality-surface":
        first["equality_surface"]["instrumentation"] = "changed"
    elif mutation == "post-hash-append":
        argv.append("--post-hash")
    elif mutation == "rehashed-argv":
        argv[3] = "3599s"
        first["argv_sha256"] = command_argv_sha256(argv)
    else:
        raise AssertionError(f"unknown mutation: {mutation}")


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("argv-member", "stored argv self-hash invalid"),
        ("hash-only", "stored argv self-hash invalid"),
        ("argv-order", "stored argv self-hash invalid"),
        ("argv-insert", "stored argv self-hash invalid"),
        ("argv-remove", "stored argv self-hash invalid"),
        ("cross-run-id", "stored argv self-hash invalid"),
        ("runtime-path", "stored argv self-hash invalid"),
        ("output-path", "stored argv self-hash invalid"),
        ("provider-selector", "stored/fresh manifest mismatch"),
        ("condition-owned", "stored/fresh manifest mismatch"),
        ("equality-surface", "stored/fresh manifest mismatch"),
        ("post-hash-append", "stored argv self-hash invalid"),
        ("rehashed-argv", "stored/fresh argv mismatch"),
    ],
)
def test_preflight_rejects_stale_or_mutated_command_surfaces(
    mutation: str,
    error: str,
) -> None:
    fresh = _direct_manifests()
    stored = copy.deepcopy(fresh)
    _mutate_stored_manifest(mutation, stored)
    with pytest.raises(PREFLIGHT.PreflightError, match=error):
        PREFLIGHT.validate_command_manifest_documents(stored, fresh)


def test_preflight_distinguishes_invalid_fresh_self_hash() -> None:
    stored = _direct_manifests()
    fresh = copy.deepcopy(stored)
    fresh[0]["argv_sha256"] = "f" * 64
    with pytest.raises(PREFLIGHT.PreflightError, match="fresh argv self-hash invalid"):
        PREFLIGHT.validate_command_manifest_documents(stored, fresh)


def test_repository_package_validator_recomputes_stored_hashes() -> None:
    document = FREEZE.render(ROOT, provider_version="V15")
    assert _validate_t09_command_manifest_hashes(document, label="T09 V15") == []
    document["manifests"][0]["argv"][3] = "3599s"
    assert _validate_t09_command_manifest_hashes(document, label="T09 V15") == [
        "T09 V15 command manifest 0 argv self-hash is invalid"
    ]


def test_source_controlled_v15_package_passes_exact_preflight_comparison() -> None:
    contract = load_execution_contract(EXECUTION, expected_sha256=file_sha256(EXECUTION))
    document = json.loads(COMMANDS.read_text(encoding="utf-8"))
    control_root = V15_PROVIDER_CONTRACT.control_root_name
    rendered = PREFLIGHT.validate_command_manifest_package(
        contract=contract,
        command_document=document,
        runtime_adaptation_sha256=file_sha256(RUNTIME_ADAPTATION),
        pilot_library_sha256=file_sha256(PILOT_LIBRARY),
        aggregate_ledger_path=(
            f"/opt/giclab-artifacts/{control_root}/runtime-budget/aggregate-budget.json"
        ),
        pilot_state_path=f"/opt/giclab-artifacts/{control_root}/pilot-state.json",
    )
    assert rendered == document["manifests"]
    assert all(item["argv_sha256"] == command_argv_sha256(item["argv"]) for item in rendered)


@pytest.mark.parametrize(
    ("version", "expected_sha256", "validator"),
    [
        (
            "V11",
            "c36e1417b4668f6a0ae99abd63e4f3c6344c2af6c0942e2ac036633b3817a4e1",
            validate_t09_v11_plan,
        ),
        (
            "V12",
            "fbca4bced586375508e945cde23b60a62b491d306c7c3dd1405933360360a7d4",
            validate_t09_v12_plan,
        ),
        (
            "V13",
            "b83b6ba6704e30048b11f68f498fadef7b6da2dbc71d2ce02f71db66bc090c28",
            validate_t09_v13_plan,
        ),
        (
            "V14",
            "d8b8b46e04a59ceb49d333bc8a345055f60e8161ba0fea5ea4d260096fe5dddc",
            validate_t09_v14_plan,
        ),
    ],
)
def test_v11_through_v14_command_artifacts_remain_byte_identical_and_valid(
    version: str,
    expected_sha256: str,
    validator: Callable[[Path], list[str]],
) -> None:
    manifest_path = EXP / f"contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_{version}.json"
    assert file_sha256(manifest_path) == expected_sha256
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert _validate_t09_command_manifest_hashes(document, label=f"T09 {version}") == []
    assert validator(ROOT) == []


def test_v15_complete_package_validator_passes() -> None:
    assert validate_t09_v15_plan(ROOT) == []
