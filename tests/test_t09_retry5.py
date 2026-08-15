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
)

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
PROVIDER_SOURCE = ROOT / "src/giclab/harness/t09_pragmatic_provider.py"
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


def _complete_task_a_pair(
    state_path: Path,
    *,
    contract_sha256: str,
    first_pair_started_at_epoch: float,
) -> None:
    for index, run_id in enumerate(ATTEMPT_ORDER[:2], start=1):
        mark_empirical_entry(
            state_path,
            execution_contract_sha256=contract_sha256,
            run_id=run_id,
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
        name="ignored-by-python-fixture",
        attempt_root=attempt,
        pilot_root=pilot,
        attempt_started=time.monotonic(),
        pair_started_at_epoch=now,
        pilot_started_at_epoch=now,
        owned_lambda_started_at_epoch=now,
        prior_lambda_duration_seconds=0.0,
        prior_lambda_cost_usd=0.0,
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
    event = json.loads((raw_root / "raw-seal-validation-event.json").read_text())
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
    marker = (
        mark_empirical_entry
        if empirical_entry_crossed
        else mark_nonempirical_infrastructure_attempt_consumed
    )
    marker(state_path, execution_contract_sha256=contract_sha, run_id=run_id)
    _write_json(
        artifact_root / "pilot-v7/frozen-run-manifest.json",
        {"replacement_image_id": "sha256:" + "a" * 64},
    )
    _write_json(raw_root / "container-command.json", {"run_id": run_id})
    _write_json(
        raw_root / "host-cleanup-receipt.json",
        {
            "run_id": run_id,
            "actual_credential_exposure_detected": False,
        },
    )
    _write_json(
        raw_root / "output-cap-event.json",
        {"stop_reason": "attempt_output_bytes", "hard_cap_breached": True},
    )
    _write_json(
        raw_root / "attempt-wall.json",
        {"evidence_handoff_deadline_epoch": now + 60},
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
    excluded = json.loads((bundle / "excluded-artifacts.json").read_text())["excluded"]
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
            "qualification_id": "QUAL-T09-PILOT-V7-LOCAL-FINALIZER-0001",
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
        exports_root.mkdir(mode=0o700)
        acknowledgements_root.mkdir(mode=0o700)
        for prior_run_id in ATTEMPT_ORDER[:2]:
            prior_archive = exports_root / f"{prior_run_id}.tar.gz"
            prior_archive.write_bytes(f"verified-{prior_run_id}".encode())
            prior_archive.chmod(0o600)
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
                    "frozen_run_manifest_sha256": frozen_sha256,
                    "replacement_image_id": replacement_image_id,
                    "empirical_entry_crossed": True,
                    "provider_entry_receipt_sha256": host.file_sha256(provider_entry),
                    "owned_instance_identity_sha256": "b" * 64,
                    "lambda_started_at_epoch": now - 14_000,
                    "verified_before_provider_termination": True,
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
    secret = tmp_path / "single-secret"
    secret.write_bytes(b"fixture-secret-value")
    secret.chmod(0o600)
    export_args = SimpleNamespace(
        repository=ROOT,
        artifact_root=artifact_root,
        run_id=run_id,
        package_commit="4" * 40,
        secret_file=secret,
    )
    stream = io.BytesIO()
    export_result = host.export_attempt(export_args, stream)
    assert export_result["bytes"] == len(stream.getvalue())
    inbound = tmp_path / "inbound"
    inbound.mkdir(mode=0o700)
    inbound_archive = inbound / f"{run_id}.tar.gz"
    inbound_archive.write_bytes(stream.getvalue())
    inbound_archive.chmod(0o600)
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
            run_id=run_id,
            package_commit="4" * 40,
            provider_entry_receipt=provider_entry,
            restore_artifact_root=restored_root,
            restoration_commit=None,
        )
    )
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
    assert host._reconstructable_disposition(restored_root)["essential_failure_seals"]
    if failed_index >= 2:
        restored_state["first_pair_checkpoint_binding"] = None
        _write_json(restored_root / "pilot-v7/pilot-state.json", restored_state)
        with pytest.raises(Exception, match="receipt-backed"):
            host._reconstructable_disposition(restored_root)


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
    mark_nonempirical_infrastructure_attempt_consumed(
        state_path,
        execution_contract_sha256=digest,
        run_id=ATTEMPT_ORDER[0],
    )
    with pytest.raises(Exception, match="consumed infrastructure failure"):
        host.admit_next_attempt(artifact_root)
    with pytest.raises(Exception, match="consumed pre-empirical infrastructure failure"):
        mark_empirical_entry(
            state_path,
            execution_contract_sha256=digest,
            run_id=ATTEMPT_ORDER[0],
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
    ) -> tuple[Path, Path]:
        source = tmp_path / label
        source.mkdir(mode=0o700)
        failed_at = 1000.0
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
            "failed_at_epoch": failed_at,
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
        )["core_destruction_verified"]
        is True
    )
    unsafe_receipt, unsafe_source = write_source(label="unsafe", destruction_verified=False)
    with pytest.raises(Exception, match="source-grounded zero-use"):
        provider._validate_host_preempirical_disposition(
            unsafe_receipt,
            unsafe_source,
            package_commit=package_commit,
            entry_receipt_sha256=entry_sha256,
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
    mark_nonempirical_infrastructure_attempt_consumed(
        state,
        execution_contract_sha256=contract_sha,
        run_id=ATTEMPT_ORDER[0],
    )
    _write_json(
        artifact_root / "pilot-v7/frozen-run-manifest.json",
        {"replacement_image_id": "sha256:" + "a" * 64},
    )
    _write_json(raw_root / "output-cap-event.json", {"hard_cap_breached": True})
    manifest = {
        "run_id": ATTEMPT_ORDER[0],
        "pair_id": "PAIR-EXP0001-PILOT-V7-TASK-A",
        "task_id": "7dcbbbdc7f1120cd",
        "condition": "reactive",
        "condition_plan_sha256": "2" * 64,
        "argv_sha256": "3" * 64,
    }
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
    with pytest.raises(Exception, match="core artifact permanently stops"):
        mark_empirical_entry(
            state_path,
            execution_contract_sha256=contract_sha256,
            run_id=ATTEMPT_ORDER[0],
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
