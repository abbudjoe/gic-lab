from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import resource
import stat
from pathlib import Path
from types import ModuleType

import pytest

from giclab.harness.policy import load_project_execution_state
from giclab.harness.t09_sira_pilot import (
    ATTEMPT_ORDER,
    PLAN_ID,
    initialize_pilot_state,
    mark_empirical_entry,
)

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
ENTRYPOINT_SOURCE = ROOT / "containers/sira-smoke/container_entrypoint.py"
CORE_PREFLIGHT_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_core_preflight.py"
EXPERIMENT_ROOT = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
PRIOR_RETRY4_RUN_ID = "RUN-T09-TASK-A-REACTIVE-0004"
PRIOR_RETRY4_DISPOSITION = EXPERIMENT_ROOT / "T09_PRAGMATIC_RETRY4_DISPOSITION.json"
RETRY5_EXECUTION_CONTROL = EXPERIMENT_ROOT / "T09_PRAGMATIC_RETRY5_EXECUTION_CONTROL.json"


def _load_module(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _host(name: str) -> ModuleType:
    return _load_module(name, HOST_SOURCE)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def test_retry5_condition_and_finalizer_docker_invocations_disable_cores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_docker_core_limit")
    monkeypatch.setattr(host, "docker_prefix", lambda: ["docker"])
    (tmp_path / "key").write_text("test-key", encoding="ascii")
    (tmp_path / "key").chmod(0o600)
    args = argparse.Namespace(repository=ROOT, artifact_root=tmp_path, secret_file=tmp_path / "key")
    manifest = {
        "run_id": ATTEMPT_ORDER[0],
        "argv": ["python", "condition.py"],
    }
    argv = host.container_create_argv(
        args=args,
        manifest=manifest,
        attempt_root=tmp_path / "attempt",
        container_name="retry5-condition",
        image_id="sha256:" + "a" * 64,
    )
    assert argv.count("--ulimit") == 1
    assert argv[argv.index("--ulimit") + 1] == "core=0:0"

    projection = _load_module(
        "giclab_t09_retry5_finalizer_projection",
        ROOT / "containers/sira-smoke/pragmatic/t09_finalizer_projection.py",
    )
    source = (ROOT / "containers/sira-smoke/pragmatic/t09_finalizer_projection.py").read_text(
        encoding="utf-8"
    )
    assert '"--ulimit",\n        "core=0:0"' in source
    assert projection is not None


def test_retry5_entrypoint_and_descendants_inherit_zero_core_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entrypoint = _load_module("giclab_t09_retry5_entrypoint", ENTRYPOINT_SOURCE)
    assert entrypoint.enforce_zero_core_limit() == (0, 0)
    assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)

    preflight = _load_module("giclab_t09_retry5_core_preflight", CORE_PREFLIGHT_SOURCE)
    monkeypatch.setattr(preflight, "ATTEMPT_ROOT", tmp_path)
    monkeypatch.setattr(preflight, "RECEIPT_PATH", tmp_path / "core-suppression-preflight.json")
    assert preflight._run_suite() == 0
    receipt = json.loads((tmp_path / "core-suppression-preflight.json").read_text())
    child = receipt["inheritance"]
    grandchild = child["child"]
    assert (child["core_soft_limit"], child["core_hard_limit"]) == (0, 0)
    assert (grandchild["core_soft_limit"], grandchild["core_hard_limit"]) == (0, 0)
    assert receipt["synthetic_abort_nonzero"] is True
    assert receipt["synthetic_abort_signal"] == "SIGABRT"
    assert not any(
        path.name == "core" or path.name.startswith("core.") for path in tmp_path.rglob("*")
    )


def test_retry5_core_detector_uses_filename_and_elf_type_but_not_size(
    tmp_path: Path,
) -> None:
    host = _host("giclab_t09_retry5_core_detector")
    named = tmp_path / "core.381"
    named.write_bytes(b"bounded-safe-metadata-fixture")
    named.chmod(0o600)
    elf = tmp_path / "chromium-crash.bin"
    elf.write_bytes(b"\x7fELF" + bytes((2, 1, 1, 0)) + b"\x00" * 8 + b"\x04\x00")
    elf.chmod(0o600)
    ordinary = tmp_path / "large-scientific-output.bin"
    with ordinary.open("wb") as handle:
        handle.truncate(8 * 1024 * 1024)
    ordinary.chmod(0o600)

    records = host.detect_core_artifacts(tmp_path)
    assert {record["path"] for record in records} == {named.name, elf.name}
    by_path = {record["path"]: record for record in records}
    assert by_path[named.name]["indicators"] == ["known-core-filename"]
    assert by_path[elf.name]["indicators"] == ["elf-et-core"]
    assert by_path[elf.name]["elf_type"] == "ET_CORE"
    assert ordinary.name not in by_path
    host.remove_core_artifacts(tmp_path, records)
    assert not named.exists() and not elf.exists() and ordinary.exists()
    assert host.detect_core_artifacts(tmp_path) == []


def test_retry5_browser_teardown_scans_for_cores_after_container_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_browser_teardown")
    events: list[str] = []
    monkeypatch.setattr(host, "docker_prefix", lambda: ["docker"])

    def run_logged(argv: list[str], **_: object) -> None:
        if "start" not in argv:
            return
        attempt = tmp_path / "pilot-v7/browser-preflight"
        _write_json(
            attempt / "browser-preflight.json",
            {
                "network_mode": "none",
                "source": "local-static-file",
                "screenshot_captures": 1,
                "playwright_version": "1.39.0",
                "chromium_revision": "1084",
                "chromium_executable_sha256": host.EXPECTED_CHROMIUM_SHA256,
                "installed_package_manifest_sha256": host.EXPECTED_PACKAGE_MANIFEST_SHA256,
                "core_soft_limit": 0,
                "core_hard_limit": 0,
            },
        )
        (attempt / "browser-preflight.png").write_bytes(b"safe-png-fixture")
        (attempt / "browser-preflight.png").chmod(0o600)

    monkeypatch.setattr(host, "run_logged", run_logged)
    monkeypatch.setattr(host, "container_state_receipt", lambda *_: {"status": "exited"})

    def remove_container(*_: object) -> bool:
        events.append("remove")
        return True

    def detect_core_artifacts(*_: object) -> list[dict[str, object]]:
        events.append("scan")
        return []

    monkeypatch.setattr(host, "remove_container", remove_container)
    monkeypatch.setattr(host, "detect_core_artifacts", detect_core_artifacts)
    monkeypatch.setattr(host, "owned_containers", lambda *_: [])
    monkeypatch.setattr(host.subprocess, "run", lambda *args, **kwargs: None)
    result = host.browser_lifecycle_preflight(
        artifact_root=tmp_path,
        prefix=["docker"],
        image_id="sha256:" + "a" * 64,
    )
    assert result["core_filename_count"] == 0
    assert result["elf_et_core_count"] == 0
    assert events == ["remove", "scan"]


def test_retry5_oversized_tree_gets_private_essential_failure_seal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_essential_failure")
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / "artifacts/EXP-0001/pilot-v7/task-a/reactive/attempt-0005"
    raw_root = attempt_root / "raw"
    raw_root.mkdir(parents=True, mode=0o700)
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    contract_sha = "1" * 64
    initialize_pilot_state(
        state_path,
        execution_contract_sha256=contract_sha,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    mark_empirical_entry(
        state_path,
        execution_contract_sha256=contract_sha,
        run_id=ATTEMPT_ORDER[0],
    )
    _write_json(
        artifact_root / "pilot-v7/frozen-run-manifest.json",
        {"replacement_image_id": "sha256:" + "a" * 64},
    )
    _write_json(raw_root / "container-command.json", {"run_id": ATTEMPT_ORDER[0]})
    _write_json(
        raw_root / "host-cleanup-receipt.json",
        {
            "run_id": ATTEMPT_ORDER[0],
            "actual_credential_exposure_detected": False,
        },
    )
    _write_json(
        raw_root / "output-cap-event.json",
        {"stop_reason": "attempt_output_bytes", "hard_cap_breached": True},
    )
    (raw_root / "condition.stdout").write_text("bounded failure output\n", encoding="utf-8")
    (raw_root / "condition.stdout").chmod(0o600)
    secret_canary = "sk-" + "A" * 24
    private = raw_root / "sira-output/private.json"
    _write_json(private, {"private_ip": "10.0.0.4", "value": secret_canary})
    oversized = raw_root / "unrelated-large.bin"
    oversized.write_bytes(b"x" * 4096)
    oversized.chmod(0o600)
    monkeypatch.setattr(host, "MAX_ATTEMPT_OUTPUT_BYTES", 1024)
    core_record = {
        "path": "core.381",
        "bytes": 234_479_616,
        "mode": "0600",
        "owner_uid": os.getuid(),
        "owner_gid": os.getgid(),
        "mtime_ns": 1,
        "elf_type": "ET_CORE",
        "indicators": ["known-core-filename", "elf-et-core"],
        "artifact_classification": "prohibited-transient-security-artifact",
        "scientific_raw_evidence": False,
        "content_or_hash_retained": False,
    }
    manifest = {
        "run_id": ATTEMPT_ORDER[0],
        "pair_id": "PAIR-EXP0001-PILOT-V7-TASK-A",
        "task_id": "7dcbbbdc7f1120cd",
        "condition": "reactive",
        "condition_plan_sha256": "2" * 64,
        "argv_sha256": "3" * 64,
    }
    manifest_path, receipt_path = host.seal_essential_failure(
        artifact_root=artifact_root,
        attempt_root=attempt_root,
        raw_root=raw_root,
        manifest=manifest,
        package_commit="4" * 40,
        frozen_run_manifest_sha256="5" * 64,
        execution_contract_sha256=contract_sha,
        returncode=143,
        stop_reason="attempt_output_bytes",
        hard_cap_breached=True,
        tree_bytes_before_security_cleanup=236_556_320,
        core_records=[core_record],
    )
    retained_manifest, retained_receipt = host.validate_essential_failure_seal(
        attempt_root=attempt_root,
        run_id=ATTEMPT_ORDER[0],
        package_commit="4" * 40,
    )
    assert retained_manifest["failure_reconstructable"] is True
    assert retained_receipt["infrastructure_invalid"] is True
    assert retained_receipt["unscored"] is True
    assert retained_receipt["condition_retry_permitted"] is False
    assert manifest_path.stat().st_size < 1_048_576
    assert receipt_path.stat().st_size < 1_048_576
    bundle = attempt_root / "essential-failure"
    failure_summary = json.loads((bundle / "failure-summary.json").read_text())
    assert failure_summary["task_text_sha256"] == (
        "153a4f251fbeb29bee8e5ca4626e6db14426063728b0d5cfa7eed3a9a230992b"
    )
    assert failure_summary["task_reference_sha256"] == (
        "fc40734fa183e839b56a7c89b16faa5900865cbee7a4210fcb251a99176f98de"
    )
    assert host.detect_core_artifacts(bundle) == []
    retained_bytes = b"".join(path.read_bytes() for path in bundle.rglob("*") if path.is_file())
    assert secret_canary.encode() not in retained_bytes
    assert b"10.0.0.4" not in retained_bytes
    excluded = json.loads((bundle / "excluded-artifacts.json").read_text())["excluded"]
    core = next(
        item for item in excluded if item["category"] == "prohibited-core-artifact-destroyed"
    )
    assert core["sha256"] is None
    assert core["bytes"] == 234_479_616
    state = json.loads(state_path.read_text())
    assert state["essential_failure_seals"][ATTEMPT_ORDER[0]] == {
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    }


def test_retry5_attempt_cap_and_core_stop_are_inviolable(
    tmp_path: Path,
) -> None:
    host = _host("giclab_t09_retry5_state_stop")
    state = tmp_path / "pilot-state.json"
    digest = "a" * 64
    initialize_pilot_state(
        state,
        execution_contract_sha256=digest,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    host.mark_core_safety_stop(
        state,
        execution_contract_sha256=digest,
    )
    with pytest.raises(Exception, match="core artifact permanently stops"):
        mark_empirical_entry(
            state,
            execution_contract_sha256=digest,
            run_id=ATTEMPT_ORDER[0],
        )
    assert host.MAX_ATTEMPT_OUTPUT_BYTES == 67_108_864
    assert host.MAX_ESSENTIAL_FAILURE_BYTES == 16_777_216


def test_retry5_preentry_core_incident_is_a_permanent_nonretryable_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_preentry_core_stop")
    state_path = tmp_path / "pilot-state.json"
    attempt_root = tmp_path / "attempt"
    attempt_root.mkdir(mode=0o700)
    secret_path = tmp_path / "sira.key"
    secret_path.write_text("A" * 32, encoding="ascii")
    secret_path.chmod(0o600)
    digest = "a" * 64
    initialize_pilot_state(
        state_path,
        execution_contract_sha256=digest,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    monkeypatch.setattr(host, "remove_container", lambda *_: True)
    monkeypatch.setattr(host, "owned_containers", lambda *_: [])

    with pytest.raises(Exception, match="security stop or residue"):
        host.record_preentry_condition_failure(
            pilot_state_path=state_path,
            attempt_root=attempt_root,
            secret_file=secret_path,
            prefix=["docker"],
            container_name="giclab-t09-pilot-v7-preentry",
            run_id=ATTEMPT_ORDER[0],
            reason="synthetic-preentry-core-incident",
            returncode=134,
            package_commit="b" * 40,
            execution_contract_sha256=digest,
            frozen_run_manifest_sha256="c" * 64,
            condition_plan_sha256="d" * 64,
            condition_argv_sha256="e" * 64,
            core_safety_stop_detected=True,
        )
    state = json.loads(state_path.read_text())
    receipt = json.loads((attempt_root / "preentry-condition-failure.json").read_text())
    assert state["core_safety_stop_detected"] is True
    assert receipt["core_safety_stop_detected"] is True
    assert receipt["retry_same_frozen_condition_permitted"] is False


def test_retry5_science_and_zero_retry_identifiers_are_fresh() -> None:
    execution = json.loads(
        (EXPERIMENT_ROOT / "contracts/T09_PILOT_EXECUTION_CONTRACT.json").read_text()
    )
    assert PLAN_ID == "PLAN-EXP0001-PILOT-V7"
    assert tuple(item["run_id"] for item in execution["attempts"]) == ATTEMPT_ORDER
    assert PRIOR_RETRY4_RUN_ID not in ATTEMPT_ORDER
    assert all(
        item["upstream_argv"][item["upstream_argv"].index("--max_retry") + 1] == "0"
        for item in execution["attempts"]
    )
    assert execution["sira_commit"] == "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
    assert execution["model_revision"] == "gpt-4o-2024-11-20"
    evidence = execution["runtime_limits"]["expected_full_attempt_evidence_basis"]
    projected = sum(
        value for key, value in evidence.items() if key != "remaining_cap_headroom_bytes"
    )
    assert projected == execution["runtime_limits"]["expected_full_attempt_evidence_bytes"]
    assert projected + evidence["remaining_cap_headroom_bytes"] == 67_108_864
    assert execution["budget_calibration"]["hard"][
        "maximum_new_cost_under_cumulative_cap_usd"
    ] == pytest.approx(60.0 - 5.7424506112)
    command_contract = json.loads(
        (EXPERIMENT_ROOT / "contracts/T09_PILOT_COMMAND_MANIFESTS.json").read_text()
    )
    assert len(command_contract["pair_diffs"]) == 2
    assert all(item["valid"] is True for item in command_contract["pair_diffs"])
    disposition = json.loads(PRIOR_RETRY4_DISPOSITION.read_text())
    assert disposition["attempts"]["task_a_reactive"]["run_id"] == PRIOR_RETRY4_RUN_ID
    assert disposition["attempts"]["task_a_reactive"]["state"] == (
        "consumed-infrastructure-invalid-unscored"
    )
    assert disposition["attempts"]["task_a_reactive"]["evaluator_valid"] is False
    assert disposition["attempts"]["task_a_reactive"]["task_score"] is None


def test_retry5_is_the_only_registered_fresh_successor_without_replaying_v6() -> None:
    state = load_project_execution_state(ROOT)
    terminal = state.terminal_execution_control
    assert terminal is not None
    assert terminal.superseded_plan_ids == {
        "PLAN-EXP0001-SMOKE",
        "PLAN-EXP0001-PILOT-V6",
    }
    assert terminal.registered_successor is not None
    assert terminal.registered_successor.plan_id == "PLAN-EXP0001-PILOT-V7"
    assert state.authorized_run_profile is None
    assert hashlib.sha256(RETRY5_EXECUTION_CONTROL.read_bytes()).hexdigest() == (
        "97539fa4b65f627880b159e0f40c9a7efab26cd2a746c7c12ddbe15e44684346"
    )


def test_retry5_core_metadata_records_only_safe_fields(tmp_path: Path) -> None:
    host = _host("giclab_t09_retry5_core_metadata")
    core = tmp_path / "core"
    core.write_bytes(b"not-memory-content")
    core.chmod(stat.S_IRUSR | stat.S_IWUSR)
    record = host.detect_core_artifacts(tmp_path)[0]
    assert set(record) == {
        "path",
        "bytes",
        "mode",
        "owner_uid",
        "owner_gid",
        "mtime_ns",
        "elf_type",
        "indicators",
        "artifact_classification",
        "scientific_raw_evidence",
        "content_or_hash_retained",
    }
    assert record["content_or_hash_retained"] is False
    assert "sha256" not in record
