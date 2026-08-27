from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import resource
import stat
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from giclab.harness.policy import load_project_execution_state
from giclab.harness.t09_sira_pilot import (
    ATTEMPT_ORDER,
    PLAN_ID,
    initialize_pilot_state,
    mark_attempt_completed,
    mark_empirical_entry,
    mark_nonempirical_infrastructure_attempt_consumed,
    mark_raw_attempt_complete,
    record_first_pair_checkpoint,
    reserve_condition_start,
)

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
PROVIDER_SOURCE = ROOT / "src/giclab/harness/t09_pragmatic_provider.py"
ENTRYPOINT_SOURCE = ROOT / "containers/sira-smoke/container_entrypoint.py"
CORE_PREFLIGHT_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_core_preflight.py"
RUNTIME_ADAPTATION_SOURCE = ROOT / "src/giclab/harness/sira_gate_a_runtime.py"
EXPERIMENT_ROOT = ROOT / "experiments/EXP-0001-sira-simulative-vs-reactive"
PRIOR_RETRY4_RUN_ID = "RUN-T09-TASK-A-REACTIVE-0004"
PRIOR_RETRY4_DISPOSITION = EXPERIMENT_ROOT / "T09_PRAGMATIC_RETRY4_DISPOSITION.json"
RETRY5_EXECUTION_CONTROL = EXPERIMENT_ROOT / "T09_PRAGMATIC_RETRY5_EXECUTION_CONTROL.json"


def _load_module(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _host(name: str) -> ModuleType:
    return _load_module(name, HOST_SOURCE)


def _provider(name: str) -> ModuleType:
    return _load_module(name, PROVIDER_SOURCE)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _raw_seal_recovery_fixture(
    host: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    complete_raw_prefix: bool,
) -> tuple[Path, Path, Path, Path, argparse.Namespace]:
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / "artifacts/EXP-0001/pilot-v7/task-a/reactive/attempt-0005"
    raw_root = attempt_root / "raw"
    supervisor_root = raw_root / host.CONDITION_SUPERVISOR_DIRNAME
    supervisor_root.mkdir(parents=True, mode=0o700)
    contract_sha256 = "1" * 64
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    initialize_pilot_state(
        state_path,
        execution_contract_sha256=contract_sha256,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    _reserve_and_mark_empirical(
        state_path,
        contract_sha256=contract_sha256,
        run_id=ATTEMPT_ORDER[0],
    )
    for name in (
        "container-state.json",
        "core-artifact-cleanup.json",
        "host-cleanup-receipt.json",
        "runtime-reconstruction-binding.json",
    ):
        _write_json(supervisor_root / name, {})
    raw_manifest_path = attempt_root / "raw-attempt-manifest.json"
    _write_json(raw_manifest_path, {"fixture": "interrupted-raw-authority"})
    if complete_raw_prefix:
        _write_json(attempt_root / "raw-attempt-complete.json", {"fixture": "complete"})
    manifest = {
        "run_id": ATTEMPT_ORDER[0],
        "pair_id": "PAIR-EXP0001-PILOT-V7-TASK-A",
        "task_id": "7dcbbbdc7f1120cd",
        "condition": "reactive",
        "condition_plan_sha256": "2" * 64,
        "argv_sha256": "3" * 64,
        "permitted_condition_owned": {
            "output_root": attempt_root.relative_to(artifact_root).as_posix(),
            "raw_output_root": raw_root.relative_to(artifact_root).as_posix(),
        },
    }
    monkeypatch.setattr(host, "verify_package", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        host,
        "load_frozen_run_manifest",
        lambda *_args, **_kwargs: (
            {"execution_contract_sha256": contract_sha256},
            "4" * 64,
        ),
    )
    monkeypatch.setattr(host, "manifest_for_run", lambda *_args, **_kwargs: manifest)
    monkeypatch.setattr(
        host,
        "reclassify_unreleased_condition_transaction",
        lambda **_kwargs: False,
    )
    credential_file = tmp_path / "single-secret"
    credential_file.write_bytes(b"fixture-secret-not-present-in-artifacts")
    credential_file.chmod(0o600)
    args = argparse.Namespace(
        repository=ROOT,
        artifact_root=artifact_root,
        package_commit="5" * 40,
        run_id=ATTEMPT_ORDER[0],
        secret_file=credential_file,
    )
    return artifact_root, attempt_root, raw_root, state_path, args


def _reserve_and_mark_empirical(
    state_path: Path,
    *,
    contract_sha256: str,
    run_id: str,
    ordinal: int = 1,
) -> None:
    start_sha256 = f"{ordinal % 16:x}" * 64
    release_sha256 = f"{(ordinal + 8) % 16:x}" * 64
    reserve_condition_start(
        state_path,
        execution_contract_sha256=contract_sha256,
        run_id=run_id,
        start_intent_sha256=start_sha256,
    )
    mark_empirical_entry(
        state_path,
        execution_contract_sha256=contract_sha256,
        run_id=run_id,
        supervised_release_receipt_sha256=release_sha256,
    )


def _reserve_and_mark_nonempirical(
    state_path: Path,
    *,
    contract_sha256: str,
    run_id: str,
    ordinal: int = 1,
) -> None:
    reserve_condition_start(
        state_path,
        execution_contract_sha256=contract_sha256,
        run_id=run_id,
        start_intent_sha256=f"{ordinal % 16:x}" * 64,
    )
    mark_nonempirical_infrastructure_attempt_consumed(
        state_path,
        execution_contract_sha256=contract_sha256,
        run_id=run_id,
    )


def _runtime_core_record(*, destruction_verifiable: bool) -> dict[str, object]:
    return {
        "artifact": "<condition-core-artifact-0001>",
        "writable_root": "/tmp",
        "bytes": 4096,
        "known_core_filename": True,
        "elf_et_core": False,
        "hardlink_alias_of_core_inode": False,
        "file_type": "regular",
        "filesystem_device": 10,
        "filesystem_inode": 20,
        "link_count": 1 if destruction_verifiable else 2,
        "classified_links_within_writable_roots": 1,
        "destruction_verifiable": destruction_verifiable,
        "content_or_hash_retained": False,
    }


def _write_runtime_cleanup_source(
    host: ModuleType,
    *,
    raw_root: Path,
    records: list[dict[str, object]],
    destruction_verified: bool,
    scan_integrity_failure: bool = False,
) -> Path:
    detection_path = raw_root / "runtime-core-detection.json"
    _write_json(
        detection_path,
        {
            "schema_version": "0.1.0",
            "scope": "condition-container-writable-roots-before-teardown",
            "core_artifacts_detected": records,
            "core_artifact_count": len(records),
            "core_scan_integrity_failure": scan_integrity_failure,
            "core_content_or_hash_retained": False,
            "destructive_cleanup_not_yet_claimed": True,
        },
    )
    cleanup_path = raw_root / "runtime-cleanup.json"
    _write_json(
        cleanup_path,
        {
            "secret_cleanup": {
                "credential_observed": True,
                "credential_removed_from_environment": True,
                "content_scan_permitted": True,
                "secret_bearing_artifacts_removed": [],
                "remaining_exact_credential_matches": 0,
            },
            "core_cleanup": {
                "core_artifacts_detected": records,
                "core_artifact_count": len(records),
                "core_scan_integrity_failure": scan_integrity_failure,
                "destruction_verified": destruction_verified,
                "credential_rotation_required_due_to_core_handling": (
                    scan_integrity_failure or (bool(records) and not destruction_verified)
                ),
                "core_content_or_hash_retained": False,
                "core_detection_receipt_sha256": host.file_sha256(detection_path),
            },
        },
    )
    return cleanup_path


def _write_terminal_failure_sources(
    host: ModuleType,
    *,
    artifact_root: Path,
    raw_root: Path,
    run_id: str,
    contract_sha256: str,
    frozen_run_manifest_sha256: str,
    condition_plan_sha256: str,
    condition_argv_sha256: str,
    empirical_entry_crossed: bool,
    returncode: int,
    stop_reason: str,
    hard_cap_breached: bool,
    tree_bytes_before_security_cleanup: int,
    tree_bytes_after_core_cleanup: int,
    core_records: list[dict[str, object]],
    core_destruction_verified: bool,
) -> Path:
    """Publish one production-shaped, source-bound terminal failure prefix."""

    host.docker_prefix = lambda: ["docker"]
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    supervisor_root = raw_root / host.CONDITION_SUPERVISOR_DIRNAME
    supervisor_root.mkdir(mode=0o700, exist_ok=True)
    container_id = "d" * 64
    create_argv_sha256 = "e" * 64
    start_intent = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": run_id,
        "container_name": f"{host.CONTAINER_PREFIX}01",
        "container_id": container_id,
        "docker_start_argv": [*host.docker_prefix(), "start", "--attach", container_id],
        "docker_create_argv_sha256": create_argv_sha256,
        "frozen_run_manifest_sha256": frozen_run_manifest_sha256,
        "condition_plan_sha256": condition_plan_sha256,
        "condition_argv_sha256": condition_argv_sha256,
        "start_reserved_at_epoch": 1.0,
        "create_outcome_ambiguous": False,
        "condition_identity_consumed_if_start_outcome_is_unknown": True,
    }
    start_path = supervisor_root / "condition-start-intent.json"
    _write_json(start_path, start_intent)
    _write_json(
        supervisor_root / "container-identity.json",
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": host.HOST_RUN_ID,
            "run_id": run_id,
            "container_name": start_intent["container_name"],
            "container_id": container_id,
            "owned_role": "condition",
            "docker_create_argv_sha256": create_argv_sha256,
        },
    )
    reserve_condition_start(
        state_path,
        execution_contract_sha256=contract_sha256,
        run_id=run_id,
        start_intent_sha256=host.file_sha256(start_path),
    )
    if empirical_entry_crossed:
        release_path = supervisor_root / "supervised-release.json"
        _write_json(
            release_path,
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "run_id": run_id,
                "container_name": start_intent["container_name"],
                "container_id": container_id,
                "release_precedes_first_credential_read": True,
            },
        )
        mark_empirical_entry(
            state_path,
            execution_contract_sha256=contract_sha256,
            run_id=run_id,
            supervised_release_receipt_sha256=host.file_sha256(release_path),
        )
    else:
        mark_nonempirical_infrastructure_attempt_consumed(
            state_path,
            execution_contract_sha256=contract_sha256,
            run_id=run_id,
        )
    if core_records:
        host.mark_core_safety_stop(
            state_path,
            execution_contract_sha256=contract_sha256,
        )
    _write_runtime_cleanup_source(
        host,
        raw_root=raw_root,
        records=[],
        destruction_verified=True,
    )
    runtime_detection_path = raw_root / "runtime-core-detection.json"
    detection_path = supervisor_root / "core-artifact-detection.json"
    detection_sha256 = host.persist_core_detection_before_cleanup(
        receipt_path=detection_path,
        records=core_records,
        scope="post-condition-complete-writable-root",
        scan_integrity_failure=False,
    )
    core_outcome = host.CoreCleanupOutcome(core_destruction_verified, None)
    _write_json(
        supervisor_root / "core-artifact-cleanup.json",
        {
            "schema_version": "0.1.0",
            "run_id": run_id,
            "core_limit_contract": host.CORE_LIMIT_CONTRACT,
            "docker_ulimit": "core=0:0",
            **host.core_cleanup_projection(core_records, core_outcome),
            "core_scan_integrity_failure": False,
            "core_detection_receipt_sha256": detection_sha256,
            "supplemental_core_detection_receipt_sha256": None,
            "producer": "producer_unavailable" if core_records else None,
            "runtime_core_artifacts_detected": [],
            "runtime_core_artifact_count": 0,
            "runtime_core_scan_integrity_failure": False,
            "runtime_core_destruction_verified": True,
            "runtime_core_detection_receipt_sha256": host.file_sha256(runtime_detection_path),
            "runtime_core_rotation_required": False,
        },
    )
    if hard_cap_breached:
        host.record_output_cap_event(
            raw_root=raw_root,
            run_id=run_id,
            stop_reason=stop_reason,
            hard_cap_breached=True,
            tree_bytes_before_security_cleanup=tree_bytes_before_security_cleanup,
            tree_bytes_after_core_cleanup=tree_bytes_after_core_cleanup,
            core_records=core_records,
        )
    _write_json(
        supervisor_root / "host-cleanup-receipt.json",
        {
            "schema_version": "0.1.0",
            "run_id": run_id,
            "returncode": returncode,
            "container_removed": True,
            "owned_container_residue": [],
            "container_state_receipt": (
                f"{host.CONDITION_SUPERVISOR_DIRNAME}/container-state.json"
            ),
            "secret_scan_passed": True,
            "secret_bearing_artifacts_removed": [],
            "runtime_secret_bearing_artifacts_removed": [],
            "runtime_secret_cleanup_malformed": False,
            "runtime_cleanup_classified_as_core_artifact": False,
            "runtime_cleanup_content_read_permitted": True,
            "secret_matching_paths": [],
            "actual_credential_exposure_detected": False,
            "core_artifact_count": len(core_records),
            "runtime_core_artifact_count": 0,
            "core_scan_integrity_failure": False,
            "runtime_core_scan_integrity_failure": False,
            "core_artifacts_destroyed": bool(core_records) and core_destruction_verified,
            "core_destruction_verified": core_destruction_verified,
            "runtime_core_destruction_verified": True,
            "runtime_core_detection_receipt_sha256": host.file_sha256(runtime_detection_path),
            "core_safety_stop_detected": bool(core_records),
            "credential_rotation_required": bool(core_records) and not core_destruction_verified,
            "campaign_continuation_permitted": False,
            "stop_reason": stop_reason,
            "hard_cap_breached": hard_cap_breached,
            "tree_bytes_before_security_cleanup": tree_bytes_before_security_cleanup,
            "started_condition_container": True,
            "condition_start_intent_sha256": host.file_sha256(start_path),
            "supervised_release_completed": empirical_entry_crossed,
            "infrastructure_stop_requires_essential_seal": True,
            "runner_exception_type": None,
            "container_removal_error_type": None,
            "timing": {
                "started_at": "2026-08-14T00:00:00Z",
                "stopped_at": "2026-08-14T00:00:01Z",
                "wall_seconds": 1.0,
            },
        },
    )
    return supervisor_root


def _complete_task_a_pair(
    state_path: Path,
    *,
    contract_sha256: str,
    first_pair_started_at_epoch: float,
) -> None:
    for index, run_id in enumerate(ATTEMPT_ORDER[:2], start=1):
        _reserve_and_mark_empirical(
            state_path,
            contract_sha256=contract_sha256,
            run_id=run_id,
            ordinal=index,
        )
        mark_raw_attempt_complete(
            state_path,
            execution_contract_sha256=contract_sha256,
            run_id=run_id,
            raw_manifest_sha256=f"{index:x}" * 64,
            raw_receipt_sha256=f"{index + 2:x}" * 64,
        )
        mark_attempt_completed(
            state_path,
            execution_contract_sha256=contract_sha256,
            run_id=run_id,
            finalizer_execution_mode="qualified-image",
            finalizer_runtime_qualification_sha256="4" * 64,
            finalizer_source_sha256="5" * 64,
            finalizer_projection_source_sha256="6" * 64,
            finalizer_commit="7" * 40,
            finalizer_dependency_manifest_sha256="8" * 64,
            evaluator_contract_sha256="9" * 64,
            interpreter="/opt/sira/.venv/bin/python",
            interpreter_sha256="a" * 64,
            semantic_projection_sha256=f"{index + 10:x}" * 64,
            finalized_output_root=f"finalized/{run_id}/v1",
            finalization_complete_sha256=f"{index + 12:x}" * 64,
        )
    record_first_pair_checkpoint(
        state_path,
        execution_contract_sha256=contract_sha256,
        decision={
            "decision": "continue-to-task-b",
            "first_pair_started_at_epoch": first_pair_started_at_epoch,
            "second_pair_started_at_epoch": first_pair_started_at_epoch + 1.0,
            "decided_at_epoch": first_pair_started_at_epoch + 1.0,
        },
        decided_at_epoch=first_pair_started_at_epoch + 1.0,
    )


def _essential_seal_fixture(
    tmp_path: Path,
    *,
    module_name: str,
) -> tuple[ModuleType, Path, Path, Path, dict[str, object], str]:
    host = _host(module_name)
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / "artifacts/EXP-0001/pilot-v7/task-a/reactive/attempt-0005"
    raw_root = attempt_root / "raw"
    raw_root.mkdir(parents=True, mode=0o700)
    contract_sha256 = "1" * 64
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    initialize_pilot_state(
        state_path,
        execution_contract_sha256=contract_sha256,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    _reserve_and_mark_nonempirical(
        state_path,
        contract_sha256=contract_sha256,
        run_id=ATTEMPT_ORDER[0],
    )
    _write_json(
        artifact_root / "pilot-v7/frozen-run-manifest.json",
        {"replacement_image_id": "sha256:" + "a" * 64},
    )
    _write_json(
        raw_root / "host-cleanup-receipt.json",
        {
            "run_id": ATTEMPT_ORDER[0],
            "returncode": 1,
            "stop_reason": "synthetic-infrastructure-stop",
            "hard_cap_breached": False,
            "tree_bytes_before_security_cleanup": 0,
            "core_scan_integrity_failure": False,
            "core_destruction_verified": True,
            "infrastructure_stop_requires_essential_seal": True,
            "actual_credential_exposure_detected": False,
            "runtime_secret_cleanup_malformed": False,
            "credential_rotation_required": False,
            "timing": {"stopped_at": "2026-08-14T00:00:00Z"},
        },
    )
    _write_json(
        raw_root / "core-artifact-cleanup.json",
        {
            "core_artifacts_detected": [],
            "core_artifact_count": 0,
            "destruction_verified": True,
        },
    )
    manifest: dict[str, object] = {
        "run_id": ATTEMPT_ORDER[0],
        "pair_id": "PAIR-EXP0001-PILOT-V7-TASK-A",
        "task_id": "7dcbbbdc7f1120cd",
        "condition": "reactive",
        "condition_plan_sha256": "2" * 64,
        "argv_sha256": "3" * 64,
        "permitted_condition_owned": {
            "output_root": attempt_root.relative_to(artifact_root).as_posix(),
            "raw_output_root": raw_root.relative_to(artifact_root).as_posix(),
        },
    }
    return host, artifact_root, attempt_root, raw_root, manifest, contract_sha256


def test_retry5_condition_and_finalizer_docker_invocations_disable_cores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_docker_core_limit")
    monkeypatch.setattr(host, "docker_prefix", lambda: ["docker"])
    (tmp_path / "key").write_text("test-key", encoding="ascii")
    (tmp_path / "key").chmod(0o600)
    (tmp_path / "pilot-v7/runtime-budget").mkdir(parents=True, mode=0o700)
    raw_root = tmp_path / "attempt"
    (raw_root / ".giclab-supervisor").mkdir(parents=True, mode=0o700)
    args = argparse.Namespace(repository=ROOT, artifact_root=tmp_path, secret_file=tmp_path / "key")
    manifest = {
        "run_id": ATTEMPT_ORDER[0],
        "argv": ["python", "condition.py"],
    }
    argv = host.container_create_argv(
        args=args,
        manifest=manifest,
        attempt_root=raw_root,
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
    container_tmp = tmp_path / "container-tmp"
    container_tmp.mkdir(mode=0o700)
    monkeypatch.setattr(preflight, "TMP_ROOT", container_tmp)
    container_shm = tmp_path / "container-shm"
    container_shm.mkdir(mode=0o700)
    monkeypatch.setattr(preflight, "SHM_ROOT", container_shm)
    monkeypatch.setattr(preflight, "RECEIPT_PATH", tmp_path / "core-suppression-preflight.json")
    assert preflight._run_suite() == 0
    receipt = json.loads((tmp_path / "core-suppression-preflight.json").read_text())
    child = receipt["inheritance"]
    grandchild = child["child"]
    assert (child["core_soft_limit"], child["core_hard_limit"]) == (0, 0)
    assert (grandchild["core_soft_limit"], grandchild["core_hard_limit"]) == (0, 0)
    assert receipt["synthetic_abort_nonzero"] is True
    assert receipt["synthetic_abort_signal"] == "SIGABRT"
    assert receipt["writable_root_core_artifact_count"] == 0
    assert not any(
        path.name == "core" or path.name.startswith("core.") for path in tmp_path.rglob("*")
    )


def test_retry5_supervised_release_wait_covers_a_delayed_final_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entrypoint = _load_module("giclab_t09_retry5_delayed_release", ENTRYPOINT_SOURCE)
    ready = tmp_path / ".giclab-entrypoint-ready"
    release = tmp_path / ".giclab-release"
    monkeypatch.setattr(entrypoint, "ATTEMPT_ROOT", tmp_path)
    monkeypatch.setattr(entrypoint, "READY_PATH", ready)
    monkeypatch.setattr(entrypoint, "RELEASE_PATH", release)
    clock = [0.0]
    monkeypatch.setattr(entrypoint.time, "monotonic", lambda: clock[0])

    def finish_delayed_gate(_: float) -> None:
        clock[0] += 31.0
        release.write_bytes(b"release\n")
        release.chmod(0o600)

    monkeypatch.setattr(entrypoint.time, "sleep", finish_delayed_gate)
    entrypoint.wait_for_supervisor_release()
    assert entrypoint.RELEASE_WAIT_SECONDS == 300
    assert ready.read_bytes() == b"ready\n"


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


@pytest.mark.parametrize(
    ("core_scan_integrity_failure", "core_destruction_verified"),
    ((True, False), (False, False)),
)
def test_retry5_runtime_never_content_scans_when_core_safety_is_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    core_scan_integrity_failure: bool,
    core_destruction_verified: bool,
) -> None:
    runtime = _load_module(
        "giclab_t09_retry5_runtime_core_privacy_"
        f"{int(core_scan_integrity_failure)}_{int(core_destruction_verified)}",
        RUNTIME_ADAPTATION_SOURCE,
    )
    attempt_root = tmp_path / "attempt"
    attempt_root.mkdir(mode=0o700)
    retained_core = attempt_root / "core.unsafe"
    retained_core.write_bytes(b"credential-and-core-memory-must-not-be-opened")
    retained_core.chmod(0o600)
    monkeypatch.setenv(runtime.SIRA_SECRET_VARIABLE, "fixture-runtime-secret")

    def forbidden_scrubber(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("credential scrubber must not inspect retained core bytes")

    monkeypatch.setattr(runtime, "ExactCredentialScrubber", forbidden_scrubber)
    monkeypatch.setattr(runtime, "_remove_secret_bearing_artifacts", forbidden_scrubber)
    cleanup, errors = runtime._privacy_safe_runtime_secret_cleanup(
        attempt_root=attempt_root,
        observed_credentials=("fixture-runtime-secret",),
        core_scan_integrity_failure=core_scan_integrity_failure,
        core_destruction_verified=core_destruction_verified,
    )
    assert runtime.SIRA_SECRET_VARIABLE not in os.environ
    assert cleanup["credential_removed_from_environment"] is True
    assert cleanup["content_scan_permitted"] is False
    assert cleanup["secret_bearing_artifacts_removed"] == []
    assert cleanup["remaining_exact_credential_matches"] is None
    assert errors == ["CredentialCleanupIntegrityUnknownDueToCoreSafety"]
    assert retained_core.read_bytes() == b"credential-and-core-memory-must-not-be-opened"


def test_retry5_runtime_core_census_includes_the_writable_budget_mount(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _load_module(
        "giclab_t09_retry5_runtime_budget_core_census",
        RUNTIME_ADAPTATION_SOURCE,
    )
    attempt_root = tmp_path / "attempt"
    runtime_budget_root = tmp_path / "pilot-v7/runtime-budget"
    attempt_root.mkdir(mode=0o700)
    runtime_budget_root.mkdir(parents=True, mode=0o700)
    named_core = runtime_budget_root / "core.budget"
    named_core.write_bytes(b"runtime-budget-core-canary")
    named_core.chmod(0o600)
    alias = runtime_budget_root / "aggregate-budget-alias.json"
    os.link(named_core, alias)
    records, paths = runtime._runtime_core_census_roots(
        (("attempt-root", attempt_root), ("runtime-budget", runtime_budget_root))
    )
    assert {record["writable_root"] for record in records} == {"runtime-budget"}
    assert {path.name for path in paths} == {"core.budget", "aggregate-budget-alias.json"}
    assert any(record["hardlink_alias_of_core_inode"] is True for record in records)
    monkeypatch.setattr(
        runtime,
        "_runtime_core_census",
        lambda *_args, **_kwargs: runtime._runtime_core_census_roots(
            (("attempt-root", attempt_root), ("runtime-budget", runtime_budget_root))
        ),
    )
    assert runtime._remove_runtime_core_artifacts(
        attempt_root,
        paths,
        records,
        runtime_budget_root=runtime_budget_root,
    )
    assert not named_core.exists() and not alias.exists()


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
                "browser_running_before_container_stop": False,
                "browser_closed_by_fixture": True,
                "chromium_process_count_after_close": 0,
                "writable_root_core_artifact_count": 0,
            },
        )
        _write_json(
            attempt / "browser-writable-root-core-scan.json",
            {
                "schema_version": "0.1.0",
                "scan_roots": ["/giclab/attempt", "/tmp", "/dev/shm"],
                "core_artifact_count": 0,
                "core_artifacts": [],
                "core_content_or_hash_retained": False,
            },
        )
        (attempt / "browser-preflight.png").write_bytes(b"safe-png-fixture")
        (attempt / "browser-preflight.png").chmod(0o600)

    monkeypatch.setattr(host, "run_logged", run_logged)
    monkeypatch.setattr(host, "_container_id_by_exact_name", lambda *_: None)
    identity = host.OwnedContainerIdentity(
        "a" * 64,
        f"{host.CONTAINER_PREFIX}browser-preflight",
        {
            "giclab.t09.plan": PLAN_ID,
            "giclab.t09.host_run": host.HOST_RUN_ID,
            "giclab.t09.role": "browser-lifecycle-preflight",
        },
    )
    monkeypatch.setattr(host, "inspect_owned_container", lambda *args, **kwargs: identity)
    monkeypatch.setattr(
        host,
        "container_state_receipt",
        lambda *_: {
            "status": "exited",
            "running": False,
            "paused": False,
            "restarting": False,
            "oom_killed": False,
            "dead": False,
            "exit_code": 0,
        },
    )

    def remove_container(*_: object, **__: object) -> bool:
        events.append("remove")
        return True

    def detect_core_artifacts(*_: object) -> list[dict[str, object]]:
        events.append("scan")
        return []

    monkeypatch.setattr(host, "remove_container", remove_container)
    monkeypatch.setattr(host, "detect_core_artifacts", detect_core_artifacts)
    monkeypatch.setattr(host, "owned_containers", lambda *_: [])
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    result = host.browser_lifecycle_preflight(
        artifact_root=tmp_path,
        prefix=["docker"],
        image_id="sha256:" + "a" * 64,
    )
    assert result["core_filename_count"] == 0
    assert result["elf_et_core_count"] == 0
    assert events == ["remove", "scan"]


@pytest.mark.parametrize(
    ("descriptor", "stream_name", "expected_reason"),
    (
        (1, "condition.stdout", "condition_stdout_bytes"),
        (2, "condition.stderr", "condition_stderr_bytes"),
    ),
)
def test_retry5_attach_stream_limit_is_an_explicit_infrastructure_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    descriptor: int,
    stream_name: str,
    expected_reason: str,
) -> None:
    host = _host("giclab_t09_retry5_attach_stream_limit")
    attempt = tmp_path / "attempt"
    pilot = tmp_path / "pilot"
    attempt.mkdir(mode=0o700)
    pilot.mkdir(mode=0o700)
    now = time.time()
    monkeypatch.setattr(host, "MAX_ATTEMPT_STREAM_BYTES", 512)
    monkeypatch.setattr(host, "MAX_ATTEMPT_OUTPUT_BYTES", 1024)
    script = f"import os; payload=b'x'*2048; os.write({descriptor},payload)"
    returncode, _wall, stop_reason, hard_cap_breached = host.run_attached_with_caps(
        prefix=[sys.executable, "-c", script],
        container_id="ignored-by-python-fixture",
        attempt_root=attempt,
        pilot_root=pilot,
        attempt_started=time.monotonic(),
        pair_started_at_epoch=now,
        pilot_started_at_epoch=now,
        owned_lambda_started_at_epoch=now,
        prior_lambda_duration_seconds=0.0,
        prior_lambda_cost_usd=0.0,
        release_condition=lambda: None,
    )
    assert returncode == 0
    assert (attempt / stream_name).stat().st_size == 512
    assert stop_reason == expected_reason
    assert hard_cap_breached is True


def test_retry5_host_runner_exception_is_not_mislabeled_as_an_output_cap(
    tmp_path: Path,
) -> None:
    host = _host("giclab_t09_retry5_runner_exception")
    disposition = host.condition_runner_exception_disposition(RuntimeError("private detail"))
    assert disposition.returncode == 125
    assert disposition.stop_reason == "host-runner-exception"
    assert disposition.hard_cap_breached is False
    assert disposition.infrastructure_stop_requires_essential_seal is True
    assert disposition.exception_type == "RuntimeError"
    assert (
        host.record_output_cap_event(
            raw_root=tmp_path,
            run_id=ATTEMPT_ORDER[0],
            stop_reason=disposition.stop_reason,
            hard_cap_breached=disposition.hard_cap_breached,
            tree_bytes_before_security_cleanup=0,
            tree_bytes_after_core_cleanup=0,
            core_records=[],
        )
        is None
    )
    assert not (tmp_path / "output-cap-event.json").exists()


def test_retry5_raw_seal_validation_failure_routes_to_noncap_essential_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_raw_seal_failure")
    raw_root = tmp_path / "attempt/raw"
    raw_root.mkdir(parents=True, mode=0o700)
    (raw_root / host.CONDITION_SUPERVISOR_DIRNAME).mkdir(mode=0o700)
    captured: dict[str, object] = {}

    def fail_raw(**_: object) -> None:
        raise host.T09HostError("private malformed-evidence detail")

    def capture_essential(**values: object) -> tuple[Path, Path]:
        captured.update(values)
        return tmp_path / "manifest", tmp_path / "receipt"

    monkeypatch.setattr(host, "seal_raw_attempt", fail_raw)
    monkeypatch.setattr(host, "seal_essential_failure", capture_essential)
    with pytest.raises(Exception, match="sealed as an infrastructure-invalid essential failure"):
        host.seal_consumed_raw_or_essential_failure(
            artifact_root=tmp_path,
            attempt_root=raw_root.parent,
            raw_root=raw_root,
            manifest={"run_id": ATTEMPT_ORDER[0]},
            package_commit="a" * 40,
            frozen_run_manifest_sha256="b" * 64,
            execution_contract_sha256="c" * 64,
            returncode=1,
            tree_bytes_before_security_cleanup=42,
            core_records=[],
            core_destruction_verified=True,
        )
    event = json.loads(
        (
            raw_root / host.CONDITION_SUPERVISOR_DIRNAME / "raw-seal-validation-event.json"
        ).read_text()
    )
    assert event == {
        "essential_failure_seal_required": True,
        "exception_message_retained": False,
        "exception_type": "T09HostError",
        "hard_cap_breached": False,
        "run_id": ATTEMPT_ORDER[0],
        "schema_version": "0.1.0",
        "stop_reason": "raw-seal-validation-failed",
    }
    assert captured["stop_reason"] == "raw-seal-validation-failed"
    assert captured["hard_cap_breached"] is False
    assert captured["empirical_entry_crossed"] is True


@pytest.mark.parametrize(
    ("empirical_entry_crossed", "failed_index"),
    ((False, 0), (True, 0), (False, 2), (True, 2)),
)
def test_retry5_oversized_tree_gets_private_essential_failure_seal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    empirical_entry_crossed: bool,
    failed_index: int,
) -> None:
    host = _host("giclab_t09_retry5_essential_failure")
    now = time.time()
    monkeypatch.setattr(host.time, "time", lambda: now)
    run_id = ATTEMPT_ORDER[failed_index]
    task_slug = "task-a" if failed_index < 2 else "task-b"
    condition = ("reactive", "simulative", "simulative", "reactive")[failed_index]
    artifact_root = tmp_path / "artifacts"
    attempt_root = (
        artifact_root / f"artifacts/EXP-0001/pilot-v7/{task_slug}/{condition}/attempt-0005"
    )
    raw_root = attempt_root / "raw"
    raw_root.mkdir(parents=True, mode=0o700)
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    contract_sha = "1" * 64
    initialize_pilot_state(
        state_path,
        execution_contract_sha256=contract_sha,
        pilot_started_at_epoch=now - 100,
        # The provider/preflight clock can be much older than the empirical
        # clock.  Attempt export must use the latter for the 13,500 s cutoff.
        lambda_started_at_epoch=now - 14_000,
    )
    if failed_index >= 2:
        _complete_task_a_pair(
            state_path,
            contract_sha256=contract_sha,
            first_pair_started_at_epoch=now - 100,
        )
        _write_json(
            state_path.parent / "first-pair-checkpoint.json",
            {
                "decision": "continue-to-task-b",
                "first_pair_started_at_epoch": now - 100,
                "second_pair_started_at_epoch": now - 99,
                "decided_at_epoch": now - 99,
            },
        )
    _write_json(
        artifact_root / "pilot-v7/frozen-run-manifest.json",
        {"replacement_image_id": "sha256:" + "a" * 64},
    )
    (raw_root / "condition.stdout").write_text("bounded failure output\n", encoding="utf-8")
    (raw_root / "condition.stdout").chmod(0o600)
    secret_canary = "fixture-exact-secret-canary-" + "A" * 24
    private = raw_root / "sira-output/private.json"
    _write_json(private, {"private_ip": "10.0.0.4", "value": secret_canary})
    screenshot_canary = b"\x89PNG\r\n\x1a\nvisual-private-pixel-canary"
    screenshot = raw_root / "sira-output/private-render.png"
    screenshot.write_bytes(screenshot_canary)
    screenshot.chmod(0o600)
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
        "filesystem_device": 1,
        "filesystem_inode": 2,
        "mtime_ns": 1,
        "file_type": "regular",
        "link_count": 2,
        "classified_links_within_scan_root": 1,
        "destruction_verifiable": False,
        "elf_type": "ET_CORE",
        "indicators": ["known-core-filename", "elf-et-core"],
        "artifact_classification": "prohibited-transient-security-artifact",
        "scientific_raw_evidence": False,
        "content_or_hash_retained": False,
    }
    manifest = {
        "run_id": run_id,
        "pair_id": (
            "PAIR-EXP0001-PILOT-V7-TASK-A" if failed_index < 2 else "PAIR-EXP0001-PILOT-V7-TASK-B"
        ),
        "task_id": "7dcbbbdc7f1120cd" if failed_index < 2 else "2120afba8009bad3",
        "condition": condition,
        "condition_plan_sha256": "2" * 64,
        "argv_sha256": "3" * 64,
        "permitted_condition_owned": {
            "output_root": attempt_root.relative_to(artifact_root).as_posix(),
            "raw_output_root": raw_root.relative_to(artifact_root).as_posix(),
        },
    }
    _write_terminal_failure_sources(
        host,
        artifact_root=artifact_root,
        raw_root=raw_root,
        run_id=run_id,
        contract_sha256=contract_sha,
        frozen_run_manifest_sha256="5" * 64,
        condition_plan_sha256="2" * 64,
        condition_argv_sha256="3" * 64,
        empirical_entry_crossed=empirical_entry_crossed,
        returncode=143,
        stop_reason="attempt_output_bytes",
        hard_cap_breached=True,
        tree_bytes_before_security_cleanup=236_556_320,
        tree_bytes_after_core_cleanup=4096,
        core_records=[core_record],
        core_destruction_verified=False,
    )
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
        core_destruction_verified=False,
        empirical_entry_crossed=empirical_entry_crossed,
    )
    retained_manifest, retained_receipt = host.validate_essential_failure_seal(
        attempt_root=attempt_root,
        run_id=run_id,
        package_commit="4" * 40,
        condition_manifest=manifest,
    )
    assert retained_manifest["failure_reconstructable"] is True
    assert retained_receipt["infrastructure_invalid"] is True
    assert retained_receipt["unscored"] is True
    assert retained_receipt["condition_retry_permitted"] is False
    assert manifest_path.stat().st_size < 1_048_576
    assert receipt_path.stat().st_size < 1_048_576
    bundle = attempt_root / "essential-failure"
    failure_summary = json.loads((bundle / "failure-summary.json").read_text())
    task_index = failed_index // 2
    assert failure_summary["task_text_sha256"] == host.TASK_TEXT_SHA256S[task_index]
    assert failure_summary["task_reference_sha256"] == host.TASK_REFERENCE_SHA256S[task_index]
    assert host.detect_core_artifacts(bundle) == []
    retained_bytes = b"".join(path.read_bytes() for path in bundle.rglob("*") if path.is_file())
    assert secret_canary.encode() not in retained_bytes
    assert b"10.0.0.4" not in retained_bytes
    assert screenshot_canary not in retained_bytes
    excluded = json.loads((bundle / "excluded-artifacts.json").read_text())["excluded"]
    assert any(
        item["path"] == "sira-output/private-render.png"
        and item["category"] == "not-in-essential-failure-allowlist"
        for item in excluded
    )
    core = next(
        item
        for item in excluded
        if item["category"] == "prohibited-core-artifact-destruction-unverified"
    )
    assert core["sha256"] is None
    assert core["bytes"] == 234_479_616
    assert failure_summary["core_artifacts_destroyed"] is False
    assert failure_summary["core_destruction_verified"] is False
    assert failure_summary["empirical_entry_crossed"] is empirical_entry_crossed
    assert failure_summary["credential_rotation_required_due_to_core_handling"] is True
    state = json.loads(state_path.read_text())
    assert state["essential_failure_seals"][run_id] == {
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    }
    monkeypatch.setattr(host, "MAX_ATTEMPT_OUTPUT_BYTES", 67_108_864)

    replacement_image_id = "sha256:" + "a" * 64
    provider_entry = tmp_path / "provider-entry-source.json"
    _write_json(
        provider_entry,
        {
            "owned_instance_identity_sha256": "b" * 64,
            "lambda_started_at_epoch": now - 14_000,
        },
    )
    pilot_root = artifact_root / "pilot-v7"
    _write_json(
        pilot_root / "provider-entry.json",
        {
            "receipt_sha256": host.file_sha256(provider_entry),
            "owned_instance_identity_sha256": "b" * 64,
            "lambda_started_at_epoch": now - 14_000,
        },
    )
    local_qualification = pilot_root / "local-finalizer-qualification.json"
    _write_json(
        local_qualification,
        {
            "qualification_id": (
                "QUAL-T09-PILOT-V8-LOCAL-FINALIZER-AUTONOMOUS-0001"
            ),
            "package_commit": "4" * 40,
        },
    )
    frozen_document = {
        "manifest_id": host.FROZEN_RUN_MANIFEST_ID,
        "plan_id": PLAN_ID,
        "clean_package_commit": "4" * 40,
        "replacement_image_id": replacement_image_id,
        "local_finalizer_qualification_sha256": host.file_sha256(local_qualification),
        "preflight_transition_mode": "fresh",
    }
    _write_json(pilot_root / "frozen-run-manifest.json", frozen_document)
    frozen_sha256 = host.file_sha256(pilot_root / "frozen-run-manifest.json")
    for relative in (
        "postfreeze-validation.json",
        "model-metadata-credential-scan.json",
        "core-suppression-preflight/host-core-suppression.json",
        "final-image-file-hashes/receipt.json",
        "qualified-real-evidence-regression/receipt.json",
        "replacement-image-qualification/build-context-exclusions.json",
    ):
        _write_json(pilot_root / relative, {"fixture": relative})
    if failed_index >= 2:
        exports_root = pilot_root / "attempt-exports"
        acknowledgements_root = pilot_root / "received-export-acknowledgements"
        completions_root = pilot_root / "attempt-export-completions"
        exports_root.mkdir(mode=0o700)
        acknowledgements_root.mkdir(mode=0o700)
        completions_root.mkdir(mode=0o700)
        for prior_run_id in ATTEMPT_ORDER[:2]:
            prior_archive = exports_root / f"{prior_run_id}.tar.gz"
            prior_archive.write_bytes(f"verified-{prior_run_id}".encode())
            prior_archive.chmod(0o600)
            prior_manifest_sha256 = "e" * 64
            prior_completion = completions_root / f"{prior_run_id}-export-completion.json"
            _write_json(
                prior_completion,
                {
                    "schema_version": "0.1.0",
                    "plan_id": PLAN_ID,
                    "host_run_id": host.HOST_RUN_ID,
                    "run_id": prior_run_id,
                    "package_commit": "4" * 40,
                    "archive_bytes": prior_archive.stat().st_size,
                    "archive_sha256": host.file_sha256(prior_archive),
                    "manifest_sha256": prior_manifest_sha256,
                    "frozen_run_manifest_sha256": frozen_sha256,
                    "replacement_image_id": replacement_image_id,
                    "provider_entry_receipt_sha256": host.file_sha256(provider_entry),
                    "owned_instance_identity_sha256": "b" * 64,
                    "lambda_started_at_epoch": now - 14_000,
                    "export_completed_at_epoch": now - 20,
                },
            )
            _write_json(
                acknowledgements_root / f"{prior_run_id}.json",
                {
                    "schema_version": "0.1.0",
                    "plan_id": PLAN_ID,
                    "host_run_id": host.HOST_RUN_ID,
                    "run_id": prior_run_id,
                    "package_commit": "4" * 40,
                    "archive_path": prior_archive.name,
                    "archive_bytes": prior_archive.stat().st_size,
                    "archive_sha256": host.file_sha256(prior_archive),
                    "manifest_sha256": prior_manifest_sha256,
                    "frozen_run_manifest_sha256": frozen_sha256,
                    "replacement_image_id": replacement_image_id,
                    "evidence_authority": "immutable-raw-attempt",
                    "empirical_entry_crossed": True,
                    "provider_entry_receipt_sha256": host.file_sha256(provider_entry),
                    "owned_instance_identity_sha256": "b" * 64,
                    "lambda_started_at_epoch": now - 14_000,
                    "export_completion_receipt_sha256": host.file_sha256(prior_completion),
                    "export_completed_at_epoch": now - 20,
                    "verified_at_epoch": now - 10,
                    "maximum_cross_host_clock_skew_seconds": (
                        host.EVIDENCE_CHRONOLOGY_CLOCK_SKEW_SECONDS
                    ),
                },
            )
    monkeypatch.setattr(
        host,
        "load_frozen_run_manifest",
        lambda *_args, **_kwargs: (frozen_document, frozen_sha256),
    )
    monkeypatch.setattr(
        host,
        "manifest_for_run",
        lambda _document, run_id: (
            manifest if run_id == manifest["run_id"] else (_ for _ in ()).throw(KeyError(run_id))
        ),
    )
    credential_file = tmp_path / "single-secret"
    credential_file.write_bytes(b"fixture-secret-value")
    credential_file.chmod(0o600)
    export_args = SimpleNamespace(
        repository=ROOT,
        artifact_root=artifact_root,
        run_id=run_id,
        package_commit="4" * 40,
        secret_file=credential_file,
    )
    interrupted_cleanup_replay = not empirical_entry_crossed and failed_index == 0
    interrupted_manifest_bytes: bytes | None = None
    if interrupted_cleanup_replay:

        class InterruptedDestination(io.BytesIO):
            def write(self, _value: bytes) -> int:
                raise OSError("synthetic transfer interruption")

        with pytest.raises(OSError, match="synthetic transfer interruption"):
            host.export_attempt(export_args, InterruptedDestination())
        interrupted_manifest_path = attempt_root / "attempt-export-manifest.json"
        interrupted_manifest_bytes = interrupted_manifest_path.read_bytes()
        assert not host._attempt_export_completion_path(artifact_root, run_id).exists()
        cleanup_chronology, pending = host._cleanup_export_handoff(
            artifact_root,
            repository=ROOT,
            state=json.loads(state_path.read_text(encoding="utf-8")),
            package_commit="4" * 40,
        )
        assert cleanup_chronology == []
        assert pending is not None
        assert pending["export_completion_status_at_cleanup_intent"] == "absent"
        assert pending["export_manifest_sha256"] == host.file_sha256(interrupted_manifest_path)
        cleanup_intent = pilot_root / "global-cleanup-intent.json"
        _write_json(
            cleanup_intent,
            {
                "schema_version": "0.1.0",
                "pending_essential_export_after_cleanup": pending,
            },
        )
        _write_json(
            pilot_root / "credential-destruction-ready.json",
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "host_run_id": host.HOST_RUN_ID,
                "cleanup_intent_sha256": host.file_sha256(cleanup_intent),
                "remaining_exact_credential_match_count": 0,
                "secret_value_or_hash_retained": False,
                "destructive_secret_cleanup_authorized": True,
            },
        )
        credential_file.unlink()
    # Essential authority is the emergency bounded handoff after either the
    # per-attempt or aggregate pilot tree is already oversized.  Its direct
    # stream must not reopen the superseded tree through the pilot-disk gate.
    monkeypatch.setattr(host, "MAX_PILOT_DISK_BYTES", 1)
    stream = io.BytesIO()
    export_result = host.export_attempt(export_args, stream)
    if interrupted_manifest_bytes is not None:
        assert (attempt_root / "attempt-export-manifest.json").read_bytes() == (
            interrupted_manifest_bytes
        )
    assert export_result["bytes"] == len(stream.getvalue())
    first_stream_bytes = stream.getvalue()
    remote_completion = host._attempt_export_completion_path(artifact_root, run_id)
    first_completion_bytes = remote_completion.read_bytes()
    # A lost first transfer is replayed after its immutable completion receipt
    # exists.  Advancing the clock must not alter either the gzip header, tar
    # member metadata, archive identity, or retained completion timestamp.
    monkeypatch.setattr(host.time, "time", lambda: now + 1)
    replay_stream = io.BytesIO()
    replay_result = host.export_attempt(export_args, replay_stream)
    assert replay_stream.getvalue() == first_stream_bytes
    assert replay_result == export_result
    assert remote_completion.read_bytes() == first_completion_bytes
    inbound = tmp_path / "inbound"
    inbound.mkdir(mode=0o700)
    inbound_archive = inbound / f"{run_id}.tar.gz"
    inbound_archive.write_bytes(replay_stream.getvalue())
    inbound_archive.chmod(0o600)
    inbound_completion = inbound / f"{run_id}-export-completion.json"
    inbound_completion.write_bytes(remote_completion.read_bytes())
    inbound_completion.chmod(0o600)
    attempt_binding = SimpleNamespace(
        output_root=attempt_root.relative_to(artifact_root).as_posix(),
        raw_output_root=raw_root.relative_to(artifact_root).as_posix(),
    )
    restored_contract = SimpleNamespace(
        sha256=contract_sha,
        attempt=lambda run_id: (
            attempt_binding
            if run_id == manifest["run_id"]
            else (_ for _ in ()).throw(KeyError(run_id))
        ),
    )
    monkeypatch.setattr(host, "verify_package", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        host, "load_execution_contract", lambda *_args, **_kwargs: restored_contract
    )
    restored_root = tmp_path / "restored-offhost"
    if failed_index >= 2:
        # Task-B disposition is reconstructed atop the two independently
        # verified Task-A exports; the terminal export does not duplicate them.
        restored_exports = restored_root / "pilot-v7/attempt-exports"
        restored_exports.mkdir(parents=True, mode=0o700)
        for prior_run_id in ATTEMPT_ORDER[:2]:
            source = pilot_root / "attempt-exports" / f"{prior_run_id}.tar.gz"
            destination = restored_exports / source.name
            destination.write_bytes(source.read_bytes())
            destination.chmod(0o600)
    host.verify_attempt_export(
        SimpleNamespace(
            repository=ROOT,
            inbound_root=inbound,
            attempt_export=inbound_archive,
            attempt_export_completion=inbound_completion,
            run_id=run_id,
            package_commit="4" * 40,
            provider_entry_receipt=provider_entry,
            restore_artifact_root=restored_root,
            restoration_commit=None,
        )
    )
    verification_path = inbound / f"{run_id}-export-verification.json"
    uploaded_acknowledgement = tmp_path / f"uploaded-{run_id}-verification.json"
    uploaded_acknowledgement.write_bytes(verification_path.read_bytes())
    uploaded_acknowledgement.chmod(0o600)
    host.acknowledge_attempt_export(
        SimpleNamespace(
            artifact_root=artifact_root,
            acknowledgement_file=uploaded_acknowledgement,
            run_id=run_id,
            package_commit="4" * 40,
        )
    )
    chronology = host.require_prior_export_acknowledgements(
        artifact_root,
        next_attempt_index=failed_index + 1,
        package_commit="4" * 40,
    )
    assert chronology[-1]["evidence_authority"] == "essential-infrastructure-failure"
    assert chronology[-1]["empirical_entry_crossed"] is empirical_entry_crossed
    assert not (pilot_root / "attempt-exports" / f"{run_id}.tar.gz").exists()
    restored_attempt = restored_root / attempt_binding.output_root
    restored_receipt = json.loads(
        (restored_attempt / "offhost-restore-complete.json").read_text(encoding="utf-8")
    )
    assert restored_receipt["evidence_authority"] == "essential-infrastructure-failure"
    assert restored_receipt["empirical_entry_crossed"] is empirical_entry_crossed
    assert restored_receipt["essential_failure_reconstructable"] is True
    assert restored_receipt["qualified_local_finalization_ready"] is False
    assert not (restored_attempt / "finalized").exists()
    restored_state = json.loads(
        (restored_root / "pilot-v7/pilot-state.json").read_text(encoding="utf-8")
    )
    expected_prior = list(ATTEMPT_ORDER[:failed_index])
    assert restored_state["empirical_attempts_entered"] == (
        [*expected_prior, run_id] if empirical_entry_crossed else expected_prior
    )
    assert restored_state["nonempirical_infrastructure_attempts_consumed"] == (
        [] if empirical_entry_crossed else [run_id]
    )
    reconstruction_commands = {
        "manifests": [
            manifest if candidate == run_id else {"run_id": candidate}
            for candidate in ATTEMPT_ORDER
        ],
        "pair_diffs": [{"valid": True}, {"valid": True}],
    }
    assert host._reconstructable_disposition(
        restored_root,
        command_document=reconstruction_commands,
        package_commit="4" * 40,
    )["essential_failure_seals"]
    if failed_index >= 2:
        restored_state["first_pair_checkpoint_binding"] = None
        _write_json(restored_root / "pilot-v7/pilot-state.json", restored_state)
        with pytest.raises(Exception, match="receipt-backed"):
            host._reconstructable_disposition(
                restored_root,
                command_document=reconstruction_commands,
                package_commit="4" * 40,
            )


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
    reserve_condition_start(
        state,
        execution_contract_sha256=digest,
        run_id=ATTEMPT_ORDER[0],
        start_intent_sha256="b" * 64,
    )
    with pytest.raises(Exception, match="core artifact permanently stops"):
        mark_empirical_entry(
            state,
            execution_contract_sha256=digest,
            run_id=ATTEMPT_ORDER[0],
            supervised_release_receipt_sha256="c" * 64,
        )
    assert host.MAX_ATTEMPT_OUTPUT_BYTES == 536_870_912
    assert host.MAX_PILOT_DISK_BYTES == 2_147_483_648
    assert host.MAX_ESSENTIAL_FAILURE_BYTES == 67_108_864


def test_autonomous_slot2_authority_uses_distinct_nested_and_tree_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_autonomous_slot2_authority")
    monkeypatch.setattr(host, "PLAN_ID", "PLAN-EXP0001-PILOT-V7")
    monkeypatch.setattr(host, "HOST_RUN_ID", "RUN-T09-PILOT-HOST-0005")
    source = Path(
        "/Volumes/Macintosh HD - Data/GIC-Lab/t09/"
        "provider-private-v7-0005-slot2"
    )
    if not source.is_dir():
        pytest.skip("retained Retry 5 Slot 2 authority is unavailable")
    destination = tmp_path / "retained-authority"
    host.retain_slot2_authority(source, destination)
    binding = host.slot2_authority_binding(destination)
    nested = destination / (
        "slot2-eligibility-source/slot1-preempirical-source/source-manifest.json"
    )
    outer = destination / "slot2-eligibility-source/source-manifest.json"
    assert binding["replacement_eligibility_preempirical_source_manifest_sha256"] == (
        host.file_sha256(nested)
    )
    assert binding["normalized_slot2_authority_tree_manifest_sha256"] == (
        host.file_sha256(outer)
    )
    assert host.file_sha256(nested) == (
        "13033996d3bb8277e7ba52d5ebc368327db09d5ada6b64ac38ef44b3019d5767"
    )
    assert host.file_sha256(outer) == (
        "a3709fc6450e058db023925431c488855e73c800d106580f8029116c7b9ee7e7"
    )
    assert host.file_sha256(nested) != host.file_sha256(outer)


def test_autonomous_preflight_initializes_cleanup_state_before_authority_copy() -> None:
    source = HOST_SOURCE.read_text(encoding="utf-8")
    preflight = source[
        source.index("def preflight(args:") : source.index("def preflight_with_deadline")
    ]
    assert preflight.index("initialize_state(") < preflight.index("retain_slot2_authority(")
    assert preflight.index("initialize_state(") < preflight.index(
        "materialize_retained_or_build_image("
    )
    assert "except (OSError, T09HostError):" in source


def test_retry5_nonempirical_consumption_blocks_replay_before_docker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_nonempirical_replay")
    artifact_root = tmp_path / "artifacts"
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    digest = "a" * 64
    now = time.time()
    initialize_pilot_state(
        state_path,
        execution_contract_sha256=digest,
        pilot_started_at_epoch=now,
        lambda_started_at_epoch=now,
    )
    _reserve_and_mark_nonempirical(
        state_path,
        contract_sha256=digest,
        run_id=ATTEMPT_ORDER[0],
    )
    with pytest.raises(Exception, match="consumed infrastructure failure"):
        host.admit_next_attempt(artifact_root)
    with pytest.raises(Exception, match="consumed pre-empirical infrastructure failure"):
        mark_empirical_entry(
            state_path,
            execution_contract_sha256=digest,
            run_id=ATTEMPT_ORDER[0],
            supervised_release_receipt_sha256="c" * 64,
        )
    package_checked = False

    def unexpected_package_check(*_: object, **__: object) -> None:
        nonlocal package_checked
        package_checked = True

    monkeypatch.setattr(host, "verify_package", unexpected_package_check)
    with pytest.raises(Exception, match="consumed infrastructure failure"):
        host.execute_condition(
            SimpleNamespace(
                repository=ROOT,
                artifact_root=artifact_root,
                run_id=ATTEMPT_ORDER[0],
            )
        )
    assert package_checked is False


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


def test_retry5_preentry_structural_privacy_finding_is_not_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_preentry_privacy_stop")
    state_path = tmp_path / "pilot-state.json"
    attempt_root = tmp_path / "attempt"
    attempt_root.mkdir(mode=0o700)
    (attempt_root / "10.0.0.1.txt").write_text("benign", encoding="utf-8")
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
    monkeypatch.setattr(host, "_container_id_by_exact_name", lambda *_: None)

    with pytest.raises(Exception, match="security stop or residue"):
        host.record_preentry_condition_failure(
            pilot_state_path=state_path,
            attempt_root=attempt_root,
            secret_file=secret_path,
            prefix=["docker"],
            container_name="giclab-t09-pilot-v7-preentry",
            run_id=ATTEMPT_ORDER[0],
            reason="synthetic-preentry-private-path",
            returncode=1,
            package_commit="b" * 40,
            execution_contract_sha256=digest,
            frozen_run_manifest_sha256="c" * 64,
            condition_plan_sha256="d" * 64,
            condition_argv_sha256="e" * 64,
        )
    receipt = json.loads((attempt_root / "preentry-condition-failure.json").read_text())
    assert receipt["structural_privacy_violations"] == ["10.0.0.1.txt:private-network-path"]
    assert receipt["retry_same_frozen_condition_permitted"] is False


def test_retry5_evidence_chronology_must_precede_provider_termination() -> None:
    host = _host("giclab_t09_retry5_evidence_chronology")
    host._require_pretermination_evidence_chronology(
        lambda_started_at_epoch=100.0,
        export_completed_at_epoch=200.0,
        verified_at_epoch=250.0,
        termination_started_at_epoch=250.0,
        label="fixture",
    )
    with pytest.raises(Exception, match="not completed and verified before termination"):
        host._require_pretermination_evidence_chronology(
            lambda_started_at_epoch=100.0,
            export_completed_at_epoch=200.0,
            verified_at_epoch=251.0,
            termination_started_at_epoch=250.0,
            label="fixture",
        )
    with pytest.raises(Exception, match="not completed and verified before termination"):
        host._require_pretermination_evidence_chronology(
            lambda_started_at_epoch=100.0,
            export_completed_at_epoch=260.0,
            verified_at_epoch=270.0,
            termination_started_at_epoch=250.0,
            label="fixture",
        )


@pytest.mark.parametrize("evidence_authority", ("immutable-raw-attempt", "essential"))
def test_retry5_aggregate_stage_rejects_a_consumed_prefix_without_direct_export_ack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    evidence_authority: str,
) -> None:
    host = _host(f"giclab_t09_retry5_stage_requires_ack_{evidence_authority}")
    artifact_root = tmp_path / "artifacts"
    pilot_root = artifact_root / "pilot-v7"
    pilot_root.mkdir(parents=True, mode=0o700)
    run_id = ATTEMPT_ORDER[0]
    state = {
        "raw_attempts_complete": [run_id] if evidence_authority == "immutable-raw-attempt" else [],
        "empirical_attempts_entered": [run_id],
        "essential_failure_seals": (
            {} if evidence_authority == "immutable-raw-attempt" else {run_id: {"fixture": True}}
        ),
        "campaign_started_at_epoch": time.time() - 1,
        "lambda_started_at_epoch": time.time() - 2,
    }
    _write_json(pilot_root / "pilot-state.json", state)
    _write_json(
        pilot_root / "host-cleanup.json",
        {
            "global_secret_scan_passed": True,
            "remote_secret_removed": True,
            "core_destruction_verified": True,
            "core_safety_stop_detected": False,
            "credential_rotation_required_due_to_core_handling": False,
            "core_scan_integrity_failure": False,
        },
    )
    _write_json(
        pilot_root / "frozen-run-manifest.json",
        {
            "manifest_id": host.FROZEN_RUN_MANIFEST_ID,
            "replacement_image_id": "sha256:" + "a" * 64,
        },
    )
    _write_json(
        pilot_root / "provider-entry.json",
        {
            "receipt_sha256": "b" * 64,
            "owned_instance_identity_sha256": "c" * 64,
            "lambda_started_at_epoch": state["lambda_started_at_epoch"],
        },
    )
    monkeypatch.setattr(host, "verify_package", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(host, "staged_archive_headroom_ok", lambda: True)
    monkeypatch.setattr(host, "detect_core_artifacts", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(host, "_reconstructable_disposition", lambda *_args, **_kwargs: state)

    with pytest.raises(Exception, match="lacks its off-host verification acknowledgement"):
        host.stage(
            SimpleNamespace(
                artifact_root=artifact_root,
                repository=ROOT,
                package_commit="d" * 40,
            )
        )


def test_retry5_cleanup_rejects_unacknowledged_raw_before_any_destructive_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_cleanup_requires_ack")
    artifact_root = tmp_path / "artifacts"
    pilot_root = artifact_root / "pilot-v7"
    pilot_root.mkdir(parents=True, mode=0o700)
    run_id = ATTEMPT_ORDER[0]
    state_path = pilot_root / "pilot-state.json"
    initialize_pilot_state(
        state_path,
        execution_contract_sha256="e" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    _reserve_and_mark_empirical(
        state_path,
        contract_sha256="e" * 64,
        run_id=run_id,
    )
    mark_raw_attempt_complete(
        state_path,
        execution_contract_sha256="e" * 64,
        run_id=run_id,
        raw_manifest_sha256="f" * 64,
        raw_receipt_sha256="1" * 64,
    )
    _write_json(
        pilot_root / "provider-entry.json",
        {
            "receipt_sha256": "a" * 64,
            "owned_instance_identity_sha256": "b" * 64,
            "lambda_started_at_epoch": 1.0,
        },
    )
    _write_json(
        pilot_root / "frozen-run-manifest.json",
        {"replacement_image_id": "sha256:" + "c" * 64},
    )

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("cleanup crossed its direct-export gate")

    monkeypatch.setattr(host, "docker_prefix", forbidden)
    monkeypatch.setattr(host, "destroy_secret", forbidden)
    with pytest.raises(Exception, match="lacks its off-host verification acknowledgement"):
        host.cleanup(
            SimpleNamespace(
                artifact_root=artifact_root,
                repository=ROOT,
                package_commit="d" * 40,
                secret_file=tmp_path / "secret-never-read",
            )
        )
    assert not (pilot_root / "global-cleanup-intent.json").exists()


def test_retry5_cleanup_requires_started_reservation_recovery_before_destruction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_cleanup_requires_reservation_recovery")
    artifact_root = tmp_path / "artifacts"
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    initialize_pilot_state(
        state_path,
        execution_contract_sha256="a" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    reserve_condition_start(
        state_path,
        execution_contract_sha256="a" * 64,
        run_id=ATTEMPT_ORDER[0],
        start_intent_sha256="b" * 64,
    )

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("cleanup crossed its started-reservation recovery gate")

    monkeypatch.setattr(host, "docker_prefix", forbidden)
    monkeypatch.setattr(host, "destroy_secret", forbidden)
    with pytest.raises(Exception, match="requires recover-attempt-seal"):
        host.cleanup(
            SimpleNamespace(
                artifact_root=artifact_root,
                repository=ROOT,
                package_commit="c" * 40,
                secret_file=tmp_path / "secret-never-read",
            )
        )
    assert not (artifact_root / "pilot-v7/global-cleanup-intent.json").exists()


def test_retry5_slot2_requires_the_exact_retained_image_archive(tmp_path: Path) -> None:
    provider = _provider("giclab_t09_retry5_slot2_image_archive")
    prior_root = tmp_path / "prior"
    prior_root.mkdir(mode=0o700)
    with pytest.raises(Exception, match="requires the exact retained image archive"):
        provider._validate_replacement_launch_eligibility(
            prior_root,
            repository=ROOT,
            package_commit="d" * 40,
            slot1_image_archive=None,
        )
    wrong_archive = tmp_path / "wrong-image.tar"
    wrong_archive.write_bytes(b"not-the-retained-image")
    wrong_archive.chmod(0o600)
    with pytest.raises(Exception, match="archive identity or metadata drifted"):
        provider._validate_replacement_launch_eligibility(
            prior_root,
            repository=ROOT,
            package_commit="d" * 40,
            slot1_image_archive=wrong_archive,
        )


def test_retry5_historical_regression_keeps_its_original_finalizer_identity() -> None:
    host = _host("giclab_t09_retry5_historical_regression_identity")

    receipt = host.validate_real_evidence_regression(
        ROOT,
        expected_finalizer_source_sha256=host.HISTORICAL_REAL_EVIDENCE_FINALIZER_SHA256,
    )

    assert receipt["finalizer_source_sha256"] == host.HISTORICAL_REAL_EVIDENCE_FINALIZER_SHA256
    current_finalizer_sha256 = host.file_sha256(ROOT / host.FINALIZER_RELATIVE_PATH)
    assert current_finalizer_sha256 != host.HISTORICAL_REAL_EVIDENCE_FINALIZER_SHA256
    with pytest.raises(Exception, match="real-evidence finalizer regression"):
        host.validate_real_evidence_regression(ROOT)


def test_retry5_slot2_normalizes_direct_slot1_authority_without_name_collision(
    tmp_path: Path,
) -> None:
    provider = _provider("giclab_t09_retry5_slot2_authority_normalization")
    source_root = tmp_path / "slot1"
    for directory, filename in (
        ("entry-source", "entry-receipt.json"),
        ("closeout-source", "closeout-receipt.json"),
        ("preempirical-source", "preempirical-disposition.json"),
    ):
        _write_json(source_root / directory / filename, {"source": directory})

    retained_root = tmp_path / "slot2/slot2-eligibility-source"
    retained_root.parent.mkdir(mode=0o700)
    provider._retain_current_v7_slot2_authority(source_root, retained_root)
    entry, closeout, preempirical = provider._current_v7_slot2_authority_paths(retained_root.parent)

    assert entry == retained_root / "slot1-entry-source"
    assert closeout == retained_root / "slot1-closeout-source"
    assert preempirical == retained_root / "slot1-preempirical-source"
    assert provider._load_json(
        retained_root / "source-manifest.json", maximum_bytes=1_048_576
    ) == provider._slot2_authority_tree_manifest(retained_root)
    assert not (retained_root / "entry-source").exists()


def test_retry5_slot2_package_transition_is_exact_and_science_invariant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider("giclab_t09_retry5_slot2_package_transition")
    observed: dict[str, object] = {}

    def transition(
        repository: Path,
        package_commit: str,
        **kwargs: object,
    ) -> dict[str, object]:
        observed.update(
            {
                "repository": repository,
                "package_commit": package_commit,
                **kwargs,
            }
        )
        return {"scientific_contract_changed": False}

    monkeypatch.setattr(provider, "_source_bound_slot2_git_transition", transition)
    target_commit = "b" * 40

    result = provider.retry5_closed_slot1_package_transition(tmp_path, target_commit)

    assert result == {"scientific_contract_changed": False}
    assert observed == {
        "repository": tmp_path,
        "package_commit": target_commit,
        "from_package_commit": provider.RETRY5_ACTIVE_SLOT1_PACKAGE_COMMIT,
        "plan_sha256": provider.RETRY5_ACTIVE_SLOT1_PLAN_SHA256,
        "allowed_paths": provider.RETRY5_SLOT2_TRANSITION_ALLOWED_PATHS,
        "required_changed_paths": frozenset(
            {
                "containers/sira-smoke/pragmatic/t09_remote_runner.py",
                "src/giclab/harness/t09_pragmatic_provider.py",
            }
        ),
    }


def test_retry5_provider_classifies_every_hard_clock_boundary() -> None:
    provider = _provider("giclab_t09_retry5_provider_clock_boundaries")
    lifecycle = provider.CampaignLifecycle(
        retry4_limits=provider.Retry4LifecycleLimits(),
        max_instances=1,
        max_launches=2,
        persistent_filesystems=0,
    )

    def classify(
        *,
        empirical_started: float = 3_600.0,
        owned_duration: float = 18_000.0,
        cumulative_duration: float = 21_600.0,
    ) -> str:
        return provider._classify_campaign_wall_exception(
            lifecycle=lifecycle,
            provider_started_at_epoch=0.0,
            empirical_started_at_epoch=empirical_started,
            termination_started_at_epoch=empirical_started + 13_500.0,
            terminal_observed_at_epoch=empirical_started + 14_400.0,
            owned_lambda_duration_seconds=owned_duration,
            cumulative_lambda_duration_seconds=cumulative_duration,
            failed_preflight_dispatch_deadline_epoch=None,
            failed_preflight_started_at_epoch=None,
            failed_preflight_failed_at_epoch=None,
        )

    assert classify() == "none"
    assert classify(empirical_started=3_600.0 + 1e-6) == ("successful-preflight-wall-violated")
    assert classify(owned_duration=18_000.0 + 1e-6) == ("successful-host-active-cap-violated")
    assert classify(cumulative_duration=21_600.0 + 1e-6) == ("cumulative-active-cap-violated")
    assert (
        provider._classify_campaign_wall_exception(
            lifecycle=lifecycle,
            provider_started_at_epoch=0.0,
            empirical_started_at_epoch=None,
            termination_started_at_epoch=3_900.0,
            terminal_observed_at_epoch=3_900.0,
            owned_lambda_duration_seconds=3_900.0,
            cumulative_lambda_duration_seconds=3_900.0,
            failed_preflight_dispatch_deadline_epoch=3_900.0,
            failed_preflight_started_at_epoch=0.0,
            failed_preflight_failed_at_epoch=3_600.0,
        )
        == "none"
    )
    assert (
        provider._classify_campaign_wall_exception(
            lifecycle=lifecycle,
            provider_started_at_epoch=0.0,
            empirical_started_at_epoch=None,
            termination_started_at_epoch=3_900.0,
            terminal_observed_at_epoch=3_900.0,
            owned_lambda_duration_seconds=3_900.0,
            cumulative_lambda_duration_seconds=3_900.0,
            failed_preflight_dispatch_deadline_epoch=3_900.0 + 1e-6,
            failed_preflight_started_at_epoch=0.0,
            failed_preflight_failed_at_epoch=3_600.0 + 1e-6,
        )
        == "failed-preflight-wall-violated"
    )
    assert {
        "failed-preflight-termination-dispatch-violated",
        "failed-preflight-wall-violated",
        "successful-preflight-wall-violated",
        "successful-host-active-cap-violated",
        "cumulative-active-cap-violated",
        "termination-cutoff-violated",
    } == provider.HARD_CAMPAIGN_WALL_EXCEPTIONS


def test_autonomous_science_and_zero_retry_identifiers_are_fresh() -> None:
    execution = json.loads(
        (EXPERIMENT_ROOT / "contracts/T09_PILOT_EXECUTION_CONTRACT.json").read_text()
    )
    assert PLAN_ID == "PLAN-EXP0001-PILOT-V8"
    assert tuple(item["run_id"] for item in execution["attempts"]) == ATTEMPT_ORDER
    assert PRIOR_RETRY4_RUN_ID not in ATTEMPT_ORDER
    assert all(
        item["upstream_argv"][item["upstream_argv"].index("--max_retry") + 1] == "0"
        for item in execution["attempts"]
    )
    assert execution["sira_commit"] == "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
    assert execution["model_revision"] == "gpt-4o-2024-11-20"
    assert execution["runtime"]["container_image_policy"] == (
        "retained-exact-archive-load-or-one-fallback-build-preentry-frozen-run-manifest-v1"
    )
    evidence = execution["runtime_limits"]["expected_full_attempt_evidence_basis"]
    projected = sum(
        value for key, value in evidence.items() if key != "remaining_cap_headroom_bytes"
    )
    assert projected == execution["runtime_limits"]["expected_full_attempt_evidence_bytes"]
    assert projected + evidence["remaining_cap_headroom_bytes"] == 536_870_912
    assert execution["budget_calibration"]["hard"][
        "maximum_new_cost_under_cumulative_cap_usd"
    ] == pytest.approx(75.0 - 6.813138735)
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


def test_retry5_postrun_control_is_archived_while_v8_is_current() -> None:
    state = load_project_execution_state(ROOT)
    assert state.terminal_execution_control is None
    assert state.authorized_run_profile is not None
    assert state.authorized_run_profile.plan_id == "PLAN-EXP0001-PILOT-V8"
    control = json.loads(RETRY5_EXECUTION_CONTROL.read_text())
    assert control["authorized"] is True
    assert control["single_use"] is True
    assert control["execution_state"] == (
        "authorized-pending-clean-v7-package-and-dynamic-preflight"
    )
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
        "filesystem_device",
        "filesystem_inode",
        "mtime_ns",
        "file_type",
        "link_count",
        "classified_links_within_scan_root",
        "destruction_verifiable",
        "elf_type",
        "indicators",
        "artifact_classification",
        "scientific_raw_evidence",
        "content_or_hash_retained",
    }
    assert record["content_or_hash_retained"] is False
    assert "sha256" not in record


def test_retry5_hardlinked_core_is_detected_and_cleanup_fails_closed(
    tmp_path: Path,
) -> None:
    host = _host("giclab_t09_retry5_hardlinked_core")
    owned = tmp_path / "owned"
    owned.mkdir(mode=0o700)
    core = owned / "core.123"
    core.write_bytes(b"\x7fELF" + bytes((2, 1, 1, 0)) + b"\x00" * 8 + b"\x04\x00")
    core.chmod(0o600)
    outside = tmp_path / "outside-retained-link"
    os.link(core, outside)

    records = host.detect_core_artifacts(owned)
    assert len(records) == 1
    assert records[0]["indicators"] == ["known-core-filename", "elf-et-core"]
    assert records[0]["link_count"] == 2
    assert records[0]["classified_links_within_scan_root"] == 1
    assert records[0]["destruction_verifiable"] is False
    assert host.remove_core_artifacts(owned, records) is False
    assert not core.exists()
    assert outside.exists()
    assert host.detect_core_artifacts(owned) == []

    external_target = tmp_path / "external-core-target"
    external_target.write_bytes(b"private-core-bytes")
    external_target.chmod(0o600)
    symlink = owned / "core.symlink"
    symlink.symlink_to(external_target)
    symlink_records = host.detect_core_artifacts(owned)
    assert len(symlink_records) == 1
    assert symlink_records[0]["file_type"] == "symlink"
    assert symlink_records[0]["destruction_verifiable"] is False
    assert host.remove_core_artifacts(owned, symlink_records) is False
    assert not symlink.exists()
    assert external_target.exists()


def test_retry5_slot2_rejects_any_unverified_core_destruction(
    tmp_path: Path,
) -> None:
    provider = _provider("giclab_t09_retry5_provider_core_gate")
    package_commit = "a" * 40
    entry_sha256 = "b" * 64

    def write_source(
        *,
        label: str,
        destruction_verified: bool,
        nonempirical_consumed: bool = False,
        failure_elapsed_seconds: float = 1000.0,
    ) -> tuple[Path, Path]:
        source = tmp_path / label
        source.mkdir(mode=0o700)
        preflight_started = 0.0
        failed_at = preflight_started + failure_elapsed_seconds
        state = {
            "plan_id": PLAN_ID,
            "empirical_attempts_entered": [],
            "nonempirical_infrastructure_attempts_consumed": (
                [ATTEMPT_ORDER[0]] if nonempirical_consumed else []
            ),
            "raw_attempts_complete": [],
            "attempts_completed": [],
            "essential_failure_seals": (
                {ATTEMPT_ORDER[0]: {"manifest_sha256": "c" * 64, "receipt_sha256": "d" * 64}}
                if nonempirical_consumed
                else {}
            ),
            "core_safety_stop_detected": not destruction_verified,
        }
        cleanup = {
            "owned_container_residue": [],
            "global_secret_scan_passed": True,
            "remote_secret_removed": True,
            "core_destruction_verified": destruction_verified,
            "core_safety_stop_detected": not destruction_verified,
            "credential_rotation_required_due_to_core_handling": not destruction_verified,
        }
        failure = {
            "plan_id": PLAN_ID,
            "host_run_id": provider.HOST_RUN_ID,
            "package_commit": package_commit,
            "empirical_attempts_entered": 0,
            "termination_dispatch_required": True,
            "provider_preflight_started_at_epoch": preflight_started,
            "failed_at_epoch": failed_at,
            "elapsed_seconds": failed_at - preflight_started,
            "termination_dispatch_deadline_epoch": failed_at + 300.0,
        }
        for name, value in {
            "pilot-state.json": state,
            "host-cleanup.json": cleanup,
            "preflight-failure.json": failure,
            "late-preflight-gate-absence.json": {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "host_run_id": provider.HOST_RUN_ID,
                "checked_relative_paths": [
                    "model-metadata-preflight",
                    "model-metadata-credential-scan.json",
                    "frozen-run-manifest.json",
                    "postfreeze-validation.json",
                    "preflight.json",
                ],
                "present_relative_paths": [],
                "model_metadata_requests": 0,
                "frozen_manifest_published": False,
                "postfreeze_validation_published": False,
                "preflight_completion_published": False,
            },
        }.items():
            _write_json(source / name, value)
        receipt = {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": provider.HOST_RUN_ID,
            "package_commit": package_commit,
            "provider_entry_receipt_sha256": entry_sha256,
            "pilot_state_sha256": provider.file_sha256(source / "pilot-state.json"),
            "host_cleanup_sha256": provider.file_sha256(source / "host-cleanup.json"),
            "preflight_failure_sha256": provider.file_sha256(source / "preflight-failure.json"),
            "late_preflight_gate_absence_sha256": provider.file_sha256(
                source / "late-preflight-gate-absence.json"
            ),
            "preflight_failed_at_epoch": failed_at,
            "provider_preflight_started_at_epoch": preflight_started,
            "preflight_elapsed_seconds": failed_at - preflight_started,
            "termination_dispatch_deadline_epoch": failed_at + 300.0,
            "empirical_attempts_entered": 0,
            "model_metadata_requests": 0,
            "model_task_requests": 0,
            "task_browser_actions": 0,
            "replacement_image_build_count": 0,
            "replacement_image_import_count": 0,
            "replacement_image_id": None,
            "replacement_image_archive_sha256": None,
            "credentials_removed": True,
            "owned_containers_absent": True,
            "core_safety_stop_detected": False,
            "core_destruction_verified": True,
            "credential_rotation_required_due_to_core_handling": False,
            "replacement_launch_evidence_only": True,
        }
        _write_json(source / "preempirical-disposition.json", receipt)
        files = [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": provider.file_sha256(path),
            }
            for path in sorted(source.iterdir())
        ]
        _write_json(
            source / "source-manifest.json",
            {
                "schema_version": "0.1.0",
                "plan_id": PLAN_ID,
                "host_run_id": provider.HOST_RUN_ID,
                "files": files,
                "total_bytes": sum(int(item["bytes"]) for item in files),
            },
        )
        return source / "preempirical-disposition.json", source

    safe_receipt, safe_source = write_source(label="safe", destruction_verified=True)
    assert (
        provider._validate_host_preempirical_disposition(
            safe_receipt,
            safe_source,
            package_commit=package_commit,
            entry_receipt_sha256=entry_sha256,
            provider_preflight_started_at_epoch=0.0,
        )["core_destruction_verified"]
        is True
    )
    late_receipt, late_source = write_source(
        label="late-preflight",
        destruction_verified=True,
        failure_elapsed_seconds=3_600.0 + 1e-6,
    )
    with pytest.raises(Exception, match="source-grounded zero-use"):
        provider._validate_host_preempirical_disposition(
            late_receipt,
            late_source,
            package_commit=package_commit,
            entry_receipt_sha256=entry_sha256,
            provider_preflight_started_at_epoch=0.0,
        )
    unsafe_receipt, unsafe_source = write_source(label="unsafe", destruction_verified=False)
    with pytest.raises(Exception, match="source-grounded zero-use"):
        provider._validate_host_preempirical_disposition(
            unsafe_receipt,
            unsafe_source,
            package_commit=package_commit,
            entry_receipt_sha256=entry_sha256,
            provider_preflight_started_at_epoch=0.0,
        )
    consumed_receipt, consumed_source = write_source(
        label="consumed",
        destruction_verified=True,
        nonempirical_consumed=True,
    )
    with pytest.raises(Exception, match="source-grounded zero-use"):
        provider._validate_host_preempirical_disposition(
            consumed_receipt,
            consumed_source,
            package_commit=package_commit,
            entry_receipt_sha256=entry_sha256,
            provider_preflight_started_at_epoch=0.0,
        )


def test_retry5_slot2_rejects_any_post_metadata_or_freeze_prefix(tmp_path: Path) -> None:
    host = _host("giclab_t09_retry5_late_gate_absence")
    root = tmp_path / "artifacts"
    (root / "pilot-v7").mkdir(parents=True, mode=0o700)
    absence = host._preempirical_late_gate_absence(root)
    assert absence["model_metadata_requests"] == 0
    for relative in host._PREEMPIRICAL_LATE_GATE_PATHS:
        target = root / "pilot-v7" / relative
        if Path(relative).suffix:
            target.write_text("{}\n", encoding="utf-8")
        else:
            target.mkdir(mode=0o700)
        with pytest.raises(Exception, match="model-metadata/freeze boundary"):
            host._preempirical_late_gate_absence(root)
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()


def test_retry5_fallback_build_crash_has_label_bound_cleanup_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_fallback_build_cleanup")
    package_commit = "a" * 40
    materialization = tmp_path / "pilot-v7/replacement-image-qualification"
    materialization.mkdir(parents=True, mode=0o700)
    labels = host._fallback_image_labels(package_commit)
    build_argv = ["docker", "build"]
    for key, value in sorted(labels.items()):
        build_argv.extend(("--label", f"{key}={value}"))
    build_argv.extend(("--tag", host.REPLACEMENT_IMAGE_TAG, "."))
    command_path = materialization / "build-command.json"
    _write_json(
        command_path,
        {
            "argv": build_argv,
            "argv_sha256": host.canonical_sha256(build_argv),
            "source_date_epoch": host.SOURCE_DATE_EPOCH,
            "network_fetches": {
                "sira_commit": host.SIRA_COMMIT,
                "uv_wheel_url": host.UV_URL,
                "uv_wheel_sha256": host.UV_SHA256,
            },
        },
    )
    intent_path = materialization / "fallback-build-intent.json"
    _write_json(
        intent_path,
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": host.HOST_RUN_ID,
            "qualification_id": host.QUALIFICATION_ID,
            "package_commit": package_commit,
            "image_tag": host.REPLACEMENT_IMAGE_TAG,
            "materialization_policy": host.SLOT1_IMAGE_MATERIALIZATION_POLICY,
            "expected_tag_present_before_build": False,
            "authorized_build_count": 1,
            "resulting_image_id_known_before_build": False,
            "owned_image_labels": labels,
            "build_argv_sha256": host.canonical_sha256(build_argv),
            "build_command_sha256": host.file_sha256(command_path),
        },
    )
    candidate = "sha256:" + "b" * 64
    visible = {host.REPLACEMENT_IMAGE_TAG: candidate, candidate: candidate}
    monkeypatch.setattr(host, "image_id_if_present", lambda _prefix, value: visible.get(value))
    monkeypatch.setattr(host, "_image_config_labels", lambda _prefix, _value: labels)
    assert (
        host._fallback_build_cleanup_candidate(
            prefix=["docker"],
            materialization=materialization,
            package_commit=package_commit,
            final_receipt_present=False,
        )
        == candidate
    )
    recovery = json.loads(
        (materialization / "fallback-build-cleanup-recovery.json").read_text(encoding="utf-8")
    )
    assert recovery["image_id"] == candidate
    assert recovery["fallback_build_intent_sha256"] == host.file_sha256(intent_path)

    # A crash after resolving the ID and before removal resumes from the exact
    # recovery identity; a tag disappearing does not lose cleanup authority.
    visible[host.REPLACEMENT_IMAGE_TAG] = None
    assert (
        host._fallback_build_cleanup_candidate(
            prefix=["docker"],
            materialization=materialization,
            package_commit=package_commit,
            final_receipt_present=False,
        )
        == candidate
    )
    monkeypatch.setattr(host, "_image_config_labels", lambda _prefix, _value: {})
    with pytest.raises(Exception, match="candidate labels drifted"):
        host._fallback_build_cleanup_candidate(
            prefix=["docker"],
            materialization=materialization,
            package_commit=package_commit,
            final_receipt_present=False,
        )


@pytest.mark.parametrize(
    ("runtime_core_unverified", "host_scan_failure"),
    ((False, False), (True, False), (False, True)),
)
def test_retry5_reserved_condition_recovery_seals_runtime_core_truth_without_unsafe_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runtime_core_unverified: bool,
    host_scan_failure: bool,
) -> None:
    host = _host(
        "giclab_t09_retry5_reserved_recovery_"
        f"{int(runtime_core_unverified)}_{int(host_scan_failure)}"
    )
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / "artifacts/EXP-0001/pilot-v7/task-a/reactive/attempt-0005"
    raw_root = attempt_root / "raw"
    raw_root.mkdir(parents=True, mode=0o700)
    supervisor_root = raw_root / host.CONDITION_SUPERVISOR_DIRNAME
    supervisor_root.mkdir(mode=0o700)
    contract_sha256 = "1" * 64
    frozen_sha256 = "2" * 64
    condition_plan_sha256 = "3" * 64
    condition_argv_sha256 = "4" * 64
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    initialize_pilot_state(
        state_path,
        execution_contract_sha256=contract_sha256,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    _write_json(
        artifact_root / "pilot-v7/frozen-run-manifest.json",
        {"replacement_image_id": "sha256:" + "a" * 64},
    )
    container_id = "d" * 64
    container_name = f"{host.CONTAINER_PREFIX}01"
    start_intent = {
        "schema_version": "0.1.0",
        "plan_id": PLAN_ID,
        "run_id": ATTEMPT_ORDER[0],
        "container_name": container_name,
        "container_id": container_id,
        "docker_start_argv": ["docker", "start", "--attach", container_id],
        "docker_create_argv_sha256": "5" * 64,
        "frozen_run_manifest_sha256": frozen_sha256,
        "condition_plan_sha256": condition_plan_sha256,
        "condition_argv_sha256": condition_argv_sha256,
        "start_reserved_at_epoch": 1.0,
        "create_outcome_ambiguous": False,
        "condition_identity_consumed_if_start_outcome_is_unknown": True,
    }
    start_path = supervisor_root / "condition-start-intent.json"
    _write_json(start_path, start_intent)
    _write_json(
        supervisor_root / "container-identity.json",
        {
            "schema_version": "0.1.0",
            "plan_id": PLAN_ID,
            "host_run_id": host.HOST_RUN_ID,
            "run_id": ATTEMPT_ORDER[0],
            "container_name": container_name,
            "container_id": container_id,
            "owned_role": "condition",
            "docker_create_argv_sha256": "5" * 64,
        },
    )
    reserve_condition_start(
        state_path,
        execution_contract_sha256=contract_sha256,
        run_id=ATTEMPT_ORDER[0],
        start_intent_sha256=host.file_sha256(start_path),
    )
    if host_scan_failure:
        runtime_cleanup = raw_root / "runtime-cleanup.json"
        runtime_cleanup.write_bytes(b"core-memory-canary-must-never-be-read")
        runtime_cleanup.chmod(0o600)
    else:
        runtime_records = (
            [_runtime_core_record(destruction_verifiable=False)] if runtime_core_unverified else []
        )
        _write_runtime_cleanup_source(
            host,
            raw_root=raw_root,
            records=runtime_records,
            destruction_verified=not runtime_core_unverified,
        )
    credential_file = tmp_path / "single-secret"
    credential_file.write_bytes(b"fixture-secret-not-present-in-artifacts")
    credential_file.chmod(0o600)
    monkeypatch.setattr(host, "docker_prefix", lambda: ["docker"])
    monkeypatch.setattr(
        host,
        "container_state_receipt",
        lambda *_args, **_kwargs: {"status": "exited", "running": False},
    )
    monkeypatch.setattr(host, "remove_container", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(host, "owned_containers", lambda _prefix: [])
    if host_scan_failure:
        monkeypatch.setattr(
            host,
            "detect_core_artifacts",
            lambda root: (
                (_ for _ in ()).throw(host.T09HostError("scan saturated"))
                if root == artifact_root
                else []
            ),
        )
        original_file_sha256 = host.file_sha256

        def guarded_file_sha256(path: Path) -> str:
            if path == raw_root / "runtime-cleanup.json":
                raise AssertionError("unsafe runtime cleanup content/hash read")
            return original_file_sha256(path)

        monkeypatch.setattr(host, "file_sha256", guarded_file_sha256)
    else:
        monkeypatch.setattr(host, "detect_core_artifacts", lambda _root: [])
    host.recover_condition_start_reservation(
        artifact_root=artifact_root,
        raw_root=raw_root,
        run_id=ATTEMPT_ORDER[0],
        secret_file=credential_file,
        execution_contract_sha256=contract_sha256,
        frozen_run_manifest_sha256=frozen_sha256,
    )
    terminal = host._essential_terminal_source_projection(
        source_root=raw_root,
        run_id=ATTEMPT_ORDER[0],
    )
    assert terminal["runtime_core_artifact_count"] == int(runtime_core_unverified)
    assert terminal["runtime_core_scan_integrity_failure"] is host_scan_failure
    assert terminal["runtime_core_rotation_required"] is (
        runtime_core_unverified or host_scan_failure
    )
    assert terminal["credential_rotation_required"] is (
        runtime_core_unverified or host_scan_failure
    )
    manifest = {
        "run_id": ATTEMPT_ORDER[0],
        "pair_id": "PAIR-EXP0001-PILOT-V7-TASK-A",
        "task_id": "7dcbbbdc7f1120cd",
        "condition": "reactive",
        "condition_plan_sha256": condition_plan_sha256,
        "argv_sha256": condition_argv_sha256,
        "permitted_condition_owned": {
            "output_root": attempt_root.relative_to(artifact_root).as_posix(),
            "raw_output_root": raw_root.relative_to(artifact_root).as_posix(),
        },
    }
    manifest_path, receipt_path = host.seal_essential_failure(
        artifact_root=artifact_root,
        attempt_root=attempt_root,
        raw_root=raw_root,
        manifest=manifest,
        package_commit="6" * 40,
        frozen_run_manifest_sha256=frozen_sha256,
        execution_contract_sha256=contract_sha256,
        returncode=125,
        stop_reason="condition-start-outcome-unknown-after-supervisor-interruption",
        hard_cap_breached=False,
        tree_bytes_before_security_cleanup=int(terminal["tree_bytes_before_security_cleanup"]),
        core_records=[],
        core_destruction_verified=not host_scan_failure,
        empirical_entry_crossed=False,
        raw_tree_scan_safe=not host_scan_failure,
        core_scan_integrity_failure=host_scan_failure,
    )
    host.validate_essential_failure_seal(
        attempt_root=attempt_root,
        run_id=ATTEMPT_ORDER[0],
        package_commit="6" * 40,
        condition_manifest=manifest,
    )
    assert manifest_path.is_file() and receipt_path.is_file()
    retained = b"".join(
        path.read_bytes()
        for path in (attempt_root / "essential-failure").rglob("*")
        if path.is_file()
    )
    assert b"core-memory-canary-must-never-be-read" not in retained


@pytest.mark.parametrize("complete_raw_prefix", (False, True))
@pytest.mark.parametrize("core_kind", ("known-name", "elf-et-core", "external-hardlink"))
def test_retry5_raw_recovery_censuses_core_before_any_raw_authority_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    complete_raw_prefix: bool,
    core_kind: str,
) -> None:
    host = _host(
        "giclab_t09_retry5_raw_recovery_core_gate_"
        f"{core_kind.replace('-', '_')}_{int(complete_raw_prefix)}"
    )
    _artifact_root, attempt_root, raw_root, state_path, args = _raw_seal_recovery_fixture(
        host,
        tmp_path,
        monkeypatch,
        complete_raw_prefix=complete_raw_prefix,
    )
    core_canary = b"synthetic-core-memory-canary-must-never-be-retained"
    if core_kind == "elf-et-core":
        core_path = raw_root / "ordinary-evaluator-output.bin"
        core_bytes = b"\x7fELF\x02\x01" + (b"\x00" * 10) + b"\x04\x00" + core_canary
    else:
        core_path = raw_root / "core.123"
        core_bytes = core_canary
    core_path.write_bytes(core_bytes)
    core_path.chmod(0o600)
    external_alias: Path | None = None
    if core_kind == "external-hardlink":
        external_alias = tmp_path / "external-core-alias"
        os.link(core_path, external_alias)

    raw_control_paths = {
        attempt_root / "raw-attempt-manifest.json",
        attempt_root / "raw-attempt-complete.json",
    }
    original_file_sha256 = host.file_sha256

    def guarded_file_sha256(path: Path) -> str:
        if path in raw_control_paths or path == core_path:
            raise AssertionError("raw/core content was hashed before the fresh security gate")
        return original_file_sha256(path)

    def forbidden_raw_authority(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("raw authority was read after a fresh core incident")

    monkeypatch.setattr(host, "file_sha256", guarded_file_sha256)
    monkeypatch.setattr(host, "seal_raw_attempt", forbidden_raw_authority)
    monkeypatch.setattr(host, "validate_raw_attempt_seal", forbidden_raw_authority)
    with pytest.raises(
        Exception,
        match="fresh recovery security incident blocks every raw-authority content read",
    ):
        host.recover_attempt_seal(args)

    assert not core_path.exists()
    if external_alias is not None:
        assert external_alias.is_file()
        assert external_alias.stat().st_nlink == 1
    recovery_root = attempt_root / "recovery-control"
    detection = json.loads(
        (recovery_root / "post-terminal-core-detection.json").read_text(encoding="utf-8")
    )
    cleanup = json.loads(
        (recovery_root / "post-terminal-core-cleanup.json").read_text(encoding="utf-8")
    )
    census = json.loads(
        (recovery_root / "recovery-security-census.json").read_text(encoding="utf-8")
    )
    assert detection["core_artifact_count"] == 1
    assert cleanup["core_artifact_count"] == 1
    assert census["core_artifact_count"] == 1
    assert census["recovery_content_copy_permitted"] is True
    assert cleanup["credential_rotation_required_due_to_core_handling"] is (
        core_kind == "external-hardlink"
    )
    assert all(
        record["content_or_hash_retained"] is False
        for record in detection["core_artifacts_detected"]
    )
    retained_control = b"".join(
        path.read_bytes() for path in recovery_root.rglob("*") if path.is_file()
    )
    assert core_canary not in retained_control
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["core_safety_stop_detected"] is True


def test_retry5_clean_manifest_only_raw_recovery_censuses_then_resumes_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_retry5_clean_raw_recovery_order")
    _artifact_root, attempt_root, _raw_root, _state_path, args = _raw_seal_recovery_fixture(
        host,
        tmp_path,
        monkeypatch,
        complete_raw_prefix=False,
    )
    raw_manifest_path = attempt_root / "raw-attempt-manifest.json"
    raw_manifest_before = raw_manifest_path.read_bytes()
    raw_receipt_path = attempt_root / "raw-attempt-complete.json"
    events: list[str] = []

    def resume_raw(**_kwargs: object) -> tuple[Path, Path]:
        census = json.loads(
            (attempt_root / "recovery-control/recovery-security-census.json").read_text(
                encoding="utf-8"
            )
        )
        assert host.recovery_security_census_permits_raw_authority_reads(census) is True
        events.append("seal")
        _write_json(raw_receipt_path, {"fixture": "resumed"})
        return raw_manifest_path, raw_receipt_path

    def validate_raw(**_kwargs: object) -> None:
        events.append("validate")

    def mark_raw(*_args: object, **_kwargs: object) -> None:
        events.append("mark")

    monkeypatch.setattr(host, "seal_raw_attempt", resume_raw)
    monkeypatch.setattr(host, "validate_raw_attempt_seal", validate_raw)
    monkeypatch.setattr(host, "mark_raw_attempt_complete", mark_raw)
    result = host.recover_attempt_seal(args)
    assert result["evidence_authority"] == "immutable-raw-attempt"
    assert result["condition_reexecuted"] is False
    assert events == ["seal", "validate", "mark"]
    assert raw_manifest_path.read_bytes() == raw_manifest_before


def test_retry5_internal_core_hardlink_alias_is_removed_before_essential_seal(
    tmp_path: Path,
) -> None:
    host = _host("giclab_t09_retry5_internal_core_alias")
    artifact_root = tmp_path / "artifacts"
    attempt_root = artifact_root / "artifacts/EXP-0001/pilot-v7/task-a/reactive/attempt-0005"
    raw_root = attempt_root / "raw"
    raw_root.mkdir(parents=True, mode=0o700)
    core_canary = b"core-memory-canary-never-retain"
    named_core = raw_root / "core.123"
    named_core.write_bytes(core_canary)
    named_core.chmod(0o600)
    allowlisted_alias = raw_root / "condition.stdout"
    os.link(named_core, allowlisted_alias)
    records = host.detect_core_artifacts(raw_root)
    assert {record["path"] for record in records} == {"core.123", "condition.stdout"}
    alias = next(record for record in records if record["path"] == "condition.stdout")
    assert alias["indicators"] == ["hardlink-alias-of-core-inode"]
    assert all(record["destruction_verifiable"] is True for record in records)
    assert host.remove_core_artifacts(raw_root, records) is True
    assert not named_core.exists() and not allowlisted_alias.exists()

    contract_sha = "1" * 64
    state = artifact_root / "pilot-v7/pilot-state.json"
    initialize_pilot_state(
        state,
        execution_contract_sha256=contract_sha,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    _write_json(
        artifact_root / "pilot-v7/frozen-run-manifest.json",
        {"replacement_image_id": "sha256:" + "a" * 64},
    )
    manifest = {
        "run_id": ATTEMPT_ORDER[0],
        "pair_id": "PAIR-EXP0001-PILOT-V7-TASK-A",
        "task_id": "7dcbbbdc7f1120cd",
        "condition": "reactive",
        "condition_plan_sha256": "2" * 64,
        "argv_sha256": "3" * 64,
        "permitted_condition_owned": {
            "output_root": attempt_root.relative_to(artifact_root).as_posix(),
            "raw_output_root": raw_root.relative_to(artifact_root).as_posix(),
        },
    }
    _write_terminal_failure_sources(
        host,
        artifact_root=artifact_root,
        raw_root=raw_root,
        run_id=ATTEMPT_ORDER[0],
        contract_sha256=contract_sha,
        frozen_run_manifest_sha256="5" * 64,
        condition_plan_sha256="2" * 64,
        condition_argv_sha256="3" * 64,
        empirical_entry_crossed=False,
        returncode=143,
        stop_reason="attempt_output_bytes",
        hard_cap_breached=True,
        tree_bytes_before_security_cleanup=len(core_canary) * 2,
        tree_bytes_after_core_cleanup=0,
        core_records=records,
        core_destruction_verified=True,
    )
    host.seal_essential_failure(
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
        tree_bytes_before_security_cleanup=len(core_canary) * 2,
        core_records=records,
        core_destruction_verified=True,
        empirical_entry_crossed=False,
    )
    retained = b"".join(
        path.read_bytes()
        for path in (attempt_root / "essential-failure").rglob("*")
        if path.is_file()
    )
    assert core_canary not in retained


def test_retry5_finalizer_core_is_removed_and_stops_selection(tmp_path: Path) -> None:
    host = _host("giclab_t09_retry5_finalizer_core_stop")
    artifact_root = tmp_path / "artifacts"
    state_path = artifact_root / "pilot-v7/pilot-state.json"
    contract_sha256 = "a" * 64
    initialize_pilot_state(
        state_path,
        execution_contract_sha256=contract_sha256,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    finalized_root = artifact_root / "finalized/v1"
    finalized_root.mkdir(parents=True, mode=0o700)
    core = finalized_root / "core.finalizer"
    core.write_bytes(b"finalizer-core-canary")
    core.chmod(0o600)
    receipt = artifact_root / "pilot-v7/security-incidents/finalizer/core-artifact-cleanup.json"
    with pytest.raises(Exception, match="finalizer produced a prohibited core"):
        host.reject_and_remove_finalized_core_artifacts(
            artifact_root=artifact_root,
            finalized_root=finalized_root,
            run_id=ATTEMPT_ORDER[0],
            execution_contract_sha256=contract_sha256,
            receipt_path=receipt,
            detection_stage="synthetic-finalizer-regression",
        )
    assert not core.exists()
    retained = json.loads(receipt.read_text(encoding="utf-8"))
    assert retained["core_artifact_count"] == 1
    assert retained["core_content_or_hash_retained"] is False
    assert retained["destruction_verified"] is True
    assert retained["campaign_continuation_permitted"] is False
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["core_safety_stop_detected"] is True
    reserve_condition_start(
        state_path,
        execution_contract_sha256=contract_sha256,
        run_id=ATTEMPT_ORDER[0],
        start_intent_sha256="b" * 64,
    )
    with pytest.raises(Exception, match="core artifact permanently stops"):
        mark_empirical_entry(
            state_path,
            execution_contract_sha256=contract_sha256,
            run_id=ATTEMPT_ORDER[0],
            supervised_release_receipt_sha256="c" * 64,
        )


@pytest.mark.parametrize(
    "malformed",
    (
        {},
        {"core_artifacts_detected": [], "destruction_verified": True},
        {
            "core_artifacts_detected": "none",
            "core_artifact_count": 0,
            "destruction_verified": True,
            "core_content_or_hash_retained": False,
            "core_transferred_outside_remote_host": False,
            "credential_rotation_required_due_to_core_handling": False,
        },
        {
            "core_artifacts_detected": [],
            "core_artifact_count": 0,
            "destruction_verified": False,
            "core_content_or_hash_retained": False,
            "core_transferred_outside_remote_host": False,
            "credential_rotation_required_due_to_core_handling": False,
        },
    ),
)
def test_retry5_malformed_core_cleanup_evidence_fails_closed(
    malformed: dict[str, object],
) -> None:
    host = _host("giclab_t09_retry5_malformed_core_cleanup")
    assert host._core_cleanup_receipt_destruction_unverified(malformed) is True
    valid_empty = {
        "core_artifacts_detected": [],
        "core_artifact_count": 0,
        "destruction_verified": True,
        "core_content_or_hash_retained": False,
        "core_transferred_outside_remote_host": False,
        "credential_rotation_required_due_to_core_handling": False,
    }
    assert host._core_cleanup_receipt_destruction_unverified(valid_empty) is False
