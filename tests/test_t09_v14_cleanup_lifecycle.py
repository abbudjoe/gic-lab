from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from giclab.harness.t09_cleanup_state import (
    CleanupExportLifecyclePhase,
    CleanupExportPhaseEvidence,
    CleanupLifecycleStage,
    CleanupTargetKind,
    CleanupTargetState,
    EarlyCleanupJournal,
    TerminalCleanupDisposition,
    cleanup_locator_identity,
)
from giclab.harness.t09_provider_contracts import V13_PROVIDER_CONTRACT
from giclab.harness.t09_sira_pilot import initialize_pilot_state

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
BASE_COMMIT = "12a6c4fba0972d3b6f9f16dcfae048dbb770d78a"
PACKAGE_COMMIT = BASE_COMMIT
HANDOFF_SCHEMA = ROOT / "schemas/t09-cleanup-export-handoff.schema.json"


def _host(name: str) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, HOST_SOURCE)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _v13_stopped_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, object], EarlyCleanupJournal]:
    artifact_root = tmp_path / "artifacts"
    pilot_root = artifact_root / V13_PROVIDER_CONTRACT.control_root_name
    state_path = pilot_root / "pilot-state.json"
    initialize_pilot_state(
        state_path,
        provider_contract=V13_PROVIDER_CONTRACT,
        execution_contract_sha256="1" * 64,
        pilot_started_at_epoch=1_900_000_000.0,
        lambda_started_at_epoch=1_899_996_524.306765,
    )
    _write_json(
        pilot_root / "provider-entry.json",
        {
            "plan_id": V13_PROVIDER_CONTRACT.plan_id,
            "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
            "receipt_sha256": "2" * 64,
            "owned_instance_identity_sha256": "3" * 64,
            "lambda_started_at_epoch": 1_899_996_524.306765,
        },
    )
    journal = EarlyCleanupJournal.initialize(
        tmp_path / "early-cleanup-state",
        plan_id=V13_PROVIDER_CONTRACT.plan_id,
        host_run_id=V13_PROVIDER_CONTRACT.host_run_id,
        package_commit=PACKAGE_COMMIT,
        plan_sha256=V13_PROVIDER_CONTRACT.expected_plan_sha256,
        provider_instance_id="sanitized-v13-provider-instance",
        provider_instance_identity_sha256="3" * 64,
        provider_started_at_epoch=1_899_996_524.306765,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="4" * 64,
        clock=lambda: 1_900_000_001.0,
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert isinstance(state, dict)
    return artifact_root, pilot_root, state, journal


def _derive(
    host: ModuleType,
    artifact_root: Path,
    state: dict[str, object],
    journal: EarlyCleanupJournal,
    *,
    retained_chronology: object | None = None,
    retained_pending: object | None = None,
) -> CleanupExportPhaseEvidence:
    return cast(
        CleanupExportPhaseEvidence,
        host.derive_cleanup_export_phase(
            artifact_root,
            repository=ROOT,
            state=state,
            package_commit=PACKAGE_COMMIT,
            cleanup_journal_state=journal.load(),
            retained_chronology=retained_chronology,
            retained_pending=retained_pending,
        ),
    )


def _publish_frozen_boundary(
    host: ModuleType,
    pilot_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_preflight: bool = False,
    journal: EarlyCleanupJournal | None = None,
) -> tuple[dict[str, object], str]:
    frozen: dict[str, object] = {
        "manifest_id": V13_PROVIDER_CONTRACT.frozen_run_manifest_id,
        "plan_id": V13_PROVIDER_CONTRACT.plan_id,
        "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
        "clean_package_commit": PACKAGE_COMMIT,
        "replacement_image_id": "sha256:" + "5" * 64,
    }
    frozen_path = pilot_root / "frozen-run-manifest.json"
    if journal is not None:
        journal.begin_freeze_publication(clock=lambda: 1_900_000_002.0)
    _write_json(frozen_path, frozen)
    frozen_sha256 = _sha256(frozen_path)
    postfreeze_path = pilot_root / "postfreeze-validation.json"
    _write_json(
        postfreeze_path,
        {
            "schema_version": "0.1.0",
            "plan_id": V13_PROVIDER_CONTRACT.plan_id,
            "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
            "package_commit": PACKAGE_COMMIT,
            "frozen_run_manifest_sha256": frozen_sha256,
            "frozen_manifest_published_before_empirical_clock": True,
            "frozen_manifest_published_at_epoch": 1_900_000_010.0,
        },
    )
    if include_preflight:
        _write_json(
            pilot_root / "preflight.json",
            {
                "plan_id": V13_PROVIDER_CONTRACT.plan_id,
                "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
                "clean_package_commit": PACKAGE_COMMIT,
                "frozen_run_manifest_sha256": frozen_sha256,
                "postfreeze_validation_sha256": _sha256(postfreeze_path),
            },
        )
    monkeypatch.setattr(
        host,
        "load_frozen_run_manifest",
        lambda *_args, **_kwargs: (frozen, frozen_sha256),
    )
    return frozen, frozen_sha256


def _valid_chronology(run_id: str) -> list[dict[str, object]]:
    return [
        {
            "run_id": run_id,
            "evidence_authority": "immutable-raw-attempt",
            "empirical_entry_crossed": True,
            "archive_bytes": 1,
            "archive_sha256": "6" * 64,
            "manifest_sha256": "7" * 64,
            "export_completion_receipt_sha256": "8" * 64,
            "acknowledgement_receipt_sha256": "9" * 64,
            "export_completed_at_epoch": 1_900_000_020.0,
            "verified_at_epoch": 1_900_000_021.0,
            "maximum_cross_host_clock_skew_seconds": 5.0,
        }
    ]


def _publish_valid_raw_export_prefix(
    host: ModuleType,
    pilot_root: Path,
    state: dict[str, object],
    *,
    run_id: str,
    frozen_sha256: str,
) -> None:
    archive_root = pilot_root / "attempt-exports"
    archive_root.mkdir(mode=0o700)
    archive = archive_root / f"{run_id}.tar.gz"
    archive.write_bytes(b"privacy-safe-acknowledged-export")
    archive.chmod(0o600)
    archive_sha256 = _sha256(archive)
    completion = pilot_root / "attempt-export-completions" / f"{run_id}-export-completion.json"
    _write_json(
        completion,
        {
            "schema_version": "0.1.0",
            "plan_id": V13_PROVIDER_CONTRACT.plan_id,
            "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
            "run_id": run_id,
            "package_commit": PACKAGE_COMMIT,
            "archive_bytes": archive.stat().st_size,
            "archive_sha256": archive_sha256,
            "manifest_sha256": "7" * 64,
            "frozen_run_manifest_sha256": frozen_sha256,
            "replacement_image_id": "sha256:" + "5" * 64,
            "provider_entry_receipt_sha256": "2" * 64,
            "owned_instance_identity_sha256": "3" * 64,
            "lambda_started_at_epoch": 1_899_996_524.306765,
            "export_completed_at_epoch": 1_900_000_020.0,
        },
    )
    _write_json(
        pilot_root / "received-export-acknowledgements" / f"{run_id}.json",
        {
            "schema_version": "0.1.0",
            "plan_id": V13_PROVIDER_CONTRACT.plan_id,
            "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
            "run_id": run_id,
            "package_commit": PACKAGE_COMMIT,
            "archive_path": archive.name,
            "archive_bytes": archive.stat().st_size,
            "archive_sha256": archive_sha256,
            "manifest_sha256": "7" * 64,
            "frozen_run_manifest_sha256": frozen_sha256,
            "replacement_image_id": "sha256:" + "5" * 64,
            "evidence_authority": "immutable-raw-attempt",
            "empirical_entry_crossed": True,
            "provider_entry_receipt_sha256": "2" * 64,
            "owned_instance_identity_sha256": "3" * 64,
            "lambda_started_at_epoch": 1_899_996_524.306765,
            "export_completion_receipt_sha256": _sha256(completion),
            "export_completed_at_epoch": 1_900_000_020.0,
            "verified_at_epoch": 1_900_000_021.0,
            "maximum_cross_host_clock_skew_seconds": (host.EVIDENCE_CHRONOLOGY_CLOCK_SKEW_SECONDS),
        },
    )
    state["empirical_attempts_entered"] = [run_id]
    state["supervised_release_bindings"] = {run_id: "a" * 64}
    state["raw_attempts_complete"] = [run_id]
    state["raw_attempt_bindings"] = {
        run_id: {"manifest_sha256": "b" * 64, "receipt_sha256": "c" * 64}
    }
    state["attempts_completed"] = [run_id]
    _write_json(pilot_root / "pilot-state.json", state)


def test_historical_v13_cleanup_retry_loaded_the_absent_manifest(tmp_path: Path) -> None:
    host = _host("giclab_t09_v14_historical_defect")
    artifact_root, pilot_root, _state, _journal = _v13_stopped_fixture(tmp_path)
    base_source = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{BASE_COMMIT}:{HOST_SOURCE.relative_to(ROOT)}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    function = base_source.split("def require_prior_export_acknowledgements(", 1)[1].split(
        "\ndef require_attempt_export_acknowledgement(", 1
    )[0]
    assert function.index('load_object(frozen_manifest_path, label="frozen run manifest")') < (
        function.index("state = _runtime_budget_state(root)")
    )
    with pytest.raises(FileNotFoundError):
        host.load_object(
            pilot_root / "frozen-run-manifest.json",
            label="historical frozen run manifest",
        )
    assert artifact_root.is_dir()


def test_v13_prefreeze_zero_attempt_cleanup_is_terminal_and_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_v14_prefreeze_idempotence")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    monkeypatch.setattr(
        host,
        "load_frozen_run_manifest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pre-freeze cleanup must not load the frozen manifest")
        ),
    )
    immutable_paths = (pilot_root / "provider-entry.json", pilot_root / "pilot-state.json")
    immutable_hashes = tuple(_sha256(path) for path in immutable_paths)
    journal_hash = journal.latest_version_sha256()

    phase = _derive(host, artifact_root, state, journal)
    assert phase.lifecycle_phase is CleanupExportLifecyclePhase.PREFREEZE_ZERO_ATTEMPT
    first = host._cleanup_export_handoff(
        artifact_root,
        repository=ROOT,
        state=state,
        package_commit=PACKAGE_COMMIT,
        lifecycle_phase=phase,
        cleanup_journal=journal,
    )
    receipt_path = pilot_root / "cleanup-export-handoff.json"
    first_receipt_bytes = receipt_path.read_bytes()
    resumed_phase = _derive(
        host,
        artifact_root,
        state,
        journal,
        retained_chronology=[],
    )
    second = host._cleanup_export_handoff(
        artifact_root,
        repository=ROOT,
        state=state,
        package_commit=PACKAGE_COMMIT,
        lifecycle_phase=resumed_phase,
        cleanup_journal=journal,
        retained_chronology=[],
    )

    assert first == second == ([], None)
    assert receipt_path.read_bytes() == first_receipt_bytes
    receipt = json.loads(first_receipt_bytes)
    schema = json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(receipt)
    assert receipt["lifecycle_phase"] == "prefreeze-zero-attempt"
    assert receipt["frozen_manifest_state"] == "not-published-expected"
    assert receipt["empirical_attempt_count"] == 0
    assert receipt["required_export_acknowledgement_count"] == 0
    assert receipt["observed_export_acknowledgement_count"] == 0
    assert receipt["acknowledgement_receipt_sha256s"] == []
    assert receipt["export_handoff_complete"] is True
    assert receipt["cleanup_may_continue"] is True
    assert tuple(_sha256(path) for path in immutable_paths) == immutable_hashes
    assert journal.latest_version_sha256() == journal_hash
    assert {target.target_id for target in journal.load().targets} >= {
        "provider-instance",
        "firewall-restoration",
    }


def test_empirical_prefix_handoff_resume_reuses_byte_identical_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_v14_empirical_handoff_resume")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    _frozen, frozen_sha256 = _publish_frozen_boundary(
        host,
        pilot_root,
        monkeypatch,
        journal=journal,
        include_preflight=True,
    )
    run_id = V13_PROVIDER_CONTRACT.run_ids[0]
    _publish_valid_raw_export_prefix(
        host,
        pilot_root,
        state,
        run_id=run_id,
        frozen_sha256=frozen_sha256,
    )
    monkeypatch.setattr(host.time, "time", lambda: 1_900_000_030.0)
    journal.advance_lifecycle(
        CleanupLifecycleStage.EMPIRICAL_ENTRY,
        clock=lambda: 1_900_000_030.0,
    )

    first_phase = _derive(host, artifact_root, state, journal)
    first_chronology, first_pending = host._cleanup_export_handoff(
        artifact_root,
        repository=ROOT,
        state=state,
        package_commit=PACKAGE_COMMIT,
        lifecycle_phase=first_phase,
        cleanup_journal=journal,
    )
    receipt_path = pilot_root / "cleanup-export-handoff.json"
    first_receipt_bytes = receipt_path.read_bytes()

    resumed_phase = _derive(
        host,
        artifact_root,
        state,
        journal,
        retained_chronology=first_chronology,
    )
    resumed_chronology, resumed_pending = host._cleanup_export_handoff(
        artifact_root,
        repository=ROOT,
        state=state,
        package_commit=PACKAGE_COMMIT,
        lifecycle_phase=resumed_phase,
        cleanup_journal=journal,
        retained_chronology=first_chronology,
    )

    assert first_phase.lifecycle_phase is CleanupExportLifecyclePhase.EMPIRICAL_PREFIX
    assert first_phase.observed_export_acknowledgement_count == 1
    assert first_phase.retained_export_chronology_count == 1
    assert resumed_phase.to_document() == first_phase.to_document()
    assert first_pending is resumed_pending is None
    assert resumed_chronology == first_chronology
    assert [item["run_id"] for item in resumed_chronology] == [run_id]
    assert receipt_path.read_bytes() == first_receipt_bytes


def test_pending_essential_resume_preserves_nonempty_acknowledged_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_v14_pending_essential_resume")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    _frozen, frozen_sha256 = _publish_frozen_boundary(
        host,
        pilot_root,
        monkeypatch,
        journal=journal,
        include_preflight=True,
    )
    first_run_id, pending_run_id = V13_PROVIDER_CONTRACT.run_ids[:2]
    _publish_valid_raw_export_prefix(
        host,
        pilot_root,
        state,
        run_id=first_run_id,
        frozen_sha256=frozen_sha256,
    )
    command_manifest_path = V13_PROVIDER_CONTRACT.command_manifest_path
    assert command_manifest_path is not None
    commands = json.loads((ROOT / command_manifest_path).read_text(encoding="utf-8"))
    condition = next(item for item in commands["manifests"] if item["run_id"] == pending_run_id)
    attempt_root = artifact_root / condition["permitted_condition_owned"]["output_root"]
    essential_manifest = attempt_root / "essential-failure-manifest.json"
    essential_receipt = attempt_root / "essential-failure-complete.json"
    _write_json(essential_manifest, {"run_id": pending_run_id, "sealed": True})
    _write_json(essential_receipt, {"run_id": pending_run_id, "complete": True})
    state["nonempirical_infrastructure_attempts_consumed"] = [pending_run_id]
    state["essential_failure_seals"] = {
        pending_run_id: {
            "manifest_sha256": _sha256(essential_manifest),
            "receipt_sha256": _sha256(essential_receipt),
        }
    }
    _write_json(pilot_root / "pilot-state.json", state)
    monkeypatch.setattr(host.time, "time", lambda: 1_900_000_030.0)
    monkeypatch.setattr(host, "validate_essential_failure_seal", lambda **_kwargs: None)
    journal.advance_lifecycle(
        CleanupLifecycleStage.EMPIRICAL_ENTRY,
        clock=lambda: 1_900_000_030.0,
    )

    first_phase = _derive(host, artifact_root, state, journal)
    first_chronology, first_pending = host._cleanup_export_handoff(
        artifact_root,
        repository=ROOT,
        state=state,
        package_commit=PACKAGE_COMMIT,
        lifecycle_phase=first_phase,
        cleanup_journal=journal,
    )
    receipt_path = pilot_root / "cleanup-export-handoff.json"
    first_receipt_bytes = receipt_path.read_bytes()
    assert first_pending is not None

    resumed_phase = _derive(
        host,
        artifact_root,
        state,
        journal,
        retained_chronology=first_chronology,
        retained_pending=first_pending,
    )
    resumed_chronology, resumed_pending = host._cleanup_export_handoff(
        artifact_root,
        repository=ROOT,
        state=state,
        package_commit=PACKAGE_COMMIT,
        lifecycle_phase=resumed_phase,
        cleanup_journal=journal,
        retained_chronology=first_chronology,
        retained_pending=first_pending,
    )

    assert first_phase.required_export_acknowledgement_count == 2
    assert first_phase.observed_export_acknowledgement_count == 1
    assert first_phase.retained_export_chronology_count == 1
    assert resumed_phase.to_document() == first_phase.to_document()
    assert [item["run_id"] for item in resumed_chronology] == [first_run_id]
    assert resumed_chronology == first_chronology
    assert resumed_pending == first_pending
    assert receipt_path.read_bytes() == first_receipt_bytes


def test_empirical_full_cleanup_resume_does_not_repeat_exact_resource_mutations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_v14_empirical_full_cleanup_resume")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    _frozen, frozen_sha256 = _publish_frozen_boundary(
        host,
        pilot_root,
        monkeypatch,
        journal=journal,
        include_preflight=True,
    )
    _write_json(
        pilot_root / "offline-runtime-preflight/offline-runtime-preflight.json",
        {
            "schema_version": "0.1.0",
            "python_version": "3.11.14",
            "offline_evaluator_fixture_results": [
                {
                    "name": "task-b-normalization-edge",
                    "score": 1.0,
                    "evaluator_valid": True,
                    "session_sha256": "a" * 64,
                }
            ],
            "provider_or_task_request": False,
            "browser_action": False,
            "provider_or_model_requests": 0,
            "browser_actions": 0,
            "secret_reads": 0,
        },
    )
    run_id = V13_PROVIDER_CONTRACT.run_ids[0]
    _publish_valid_raw_export_prefix(
        host,
        pilot_root,
        state,
        run_id=run_id,
        frozen_sha256=frozen_sha256,
    )
    monkeypatch.setattr(host.time, "time", lambda: 1_900_000_030.0)
    monkeypatch.setattr(host, "utc_now", lambda: "2030-03-17T17:47:10Z")
    journal.advance_lifecycle(
        CleanupLifecycleStage.EMPIRICAL_ENTRY,
        clock=lambda: 1_900_000_030.0,
    )

    secret_file = tmp_path / "fixture-remote-credential"
    secret_file.write_bytes(b"privacy-safe-fixture-credential")
    secret_file.chmod(0o600)
    journal.register_target(
        target_id="temporary-remote-secret",
        kind=CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL,
        locator=str(secret_file),
        ownership_sha256=cleanup_locator_identity(
            CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL,
            str(secret_file),
        ),
        public_alias="temporary-remote-secret",
        clock=lambda: 1_900_000_031.0,
    )
    ruleset_id = "ruleset-v14-resume-fixture"
    journal.register_target(
        target_id="owned-ruleset-resume-fixture",
        kind=CleanupTargetKind.OWNED_RULESET,
        locator=ruleset_id,
        ownership_sha256=cleanup_locator_identity(
            CleanupTargetKind.OWNED_RULESET,
            ruleset_id,
        ),
        public_alias="owned-ruleset/resume-fixture",
        clock=lambda: 1_900_000_032.0,
    )
    journal.record_result(
        target_id="provider-instance",
        result=CleanupTargetState.TERMINAL,
        detail_code="provider-terminal-before-host-resume-fixture",
        during_cleanup=False,
        clock=lambda: 1_900_000_033.0,
    )
    journal.record_result(
        target_id="firewall-restoration",
        result=CleanupTargetState.RESTORED,
        detail_code="firewall-restored-before-host-resume-fixture",
        during_cleanup=False,
        clock=lambda: 1_900_000_034.0,
    )
    journal.record_result(
        target_id="owned-ruleset-resume-fixture",
        result=CleanupTargetState.REMOVED,
        detail_code="ruleset-removed-before-host-resume-fixture",
        during_cleanup=False,
        clock=lambda: 1_900_000_035.0,
    )

    image_archive = tmp_path / "replacement-image-archive.tar"
    regression_archive = tmp_path / "private-regression-archive.tar"
    image_archive.write_bytes(b"fixture-image-archive")
    image_archive.chmod(0o600)
    regression_archive.write_bytes(b"fixture-regression-archive")
    regression_archive.chmod(0o600)
    monkeypatch.setattr(host, "IMAGE_ARCHIVE_PATH", image_archive)
    monkeypatch.setattr(host, "PRIVATE_REGRESSION_ARCHIVE_PATH", regression_archive)

    container_id = "d" * 64
    container_name = f"{V13_PROVIDER_CONTRACT.container_prefix}resume-fixture"
    container_role = "condition"
    container_identity = host.OwnedContainerIdentity(
        container_id,
        container_name,
        {
            "giclab.t09.plan": V13_PROVIDER_CONTRACT.plan_id,
            "giclab.t09.host_run": V13_PROVIDER_CONTRACT.host_run_id,
            "giclab.t09.role": container_role,
        },
    )
    operations = {
        "container_removal": 0,
        "credential_destruction": 0,
        "core_cleanup": 0,
        "container_enumeration": 0,
    }

    def enumerate_owned(*_args: object, **_kwargs: object) -> list[object]:
        operations["container_enumeration"] += 1
        return [container_identity] if operations["container_enumeration"] == 1 else []

    def remove_owned(*_args: object, **_kwargs: object) -> bool:
        operations["container_removal"] += 1
        return True

    destroy_credential_file = host.destroy_secret

    def destroy_fixture_secret(path: Path) -> bool:
        operations["credential_destruction"] += 1
        return bool(destroy_credential_file(path))

    def clean_fixture_cores(*_args: object, **_kwargs: object) -> object:
        operations["core_cleanup"] += 1
        return host.CoreCleanupOutcome(destruction_verified=True, error_type=None)

    monkeypatch.setattr(host, "enforce_host_core_limit", lambda: None)
    monkeypatch.setattr(host, "docker_prefix", lambda: ["fixture-docker"])
    monkeypatch.setattr(
        host,
        "owned_container_intents",
        lambda *_args, **_kwargs: {container_name: container_role},
    )
    monkeypatch.setattr(host, "owned_container_identities", enumerate_owned)
    monkeypatch.setattr(host, "remove_container", remove_owned)
    monkeypatch.setattr(host, "_owned_containers_for", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        host,
        "_prior_typed_core_incidents",
        lambda **_kwargs: (False, False),
    )
    monkeypatch.setattr(host, "detect_core_artifacts", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(host, "cleanup_core_artifacts", clean_fixture_cores)
    monkeypatch.setattr(host, "_fallback_build_cleanup_candidate", lambda **_kwargs: None)
    monkeypatch.setattr(host, "image_id_if_present", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(host, "secret_hits", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(host, "destroy_secret", destroy_fixture_secret)
    monkeypatch.setattr(host, "provider_seconds_remaining", lambda *_args, **_kwargs: 120.0)
    monkeypatch.setattr(host, "gpu_snapshot", lambda: {})
    monkeypatch.setattr(
        host,
        "load_validated_pilot_state",
        lambda *_args, **_kwargs: dict(state),
    )

    cleanup_epoch = 1_900_000_040.0

    def cleanup_clock() -> float:
        nonlocal cleanup_epoch
        cleanup_epoch += 0.001
        return cleanup_epoch

    original_advance_lifecycle = host.EarlyCleanupJournal.advance_lifecycle
    original_register_target = host.EarlyCleanupJournal.register_target
    original_record_result = host.EarlyCleanupJournal.record_result

    def advance_lifecycle_with_fixture_clock(
        journal_instance: object,
        stage: CleanupLifecycleStage,
        **_kwargs: object,
    ) -> object:
        return original_advance_lifecycle(
            journal_instance,
            stage,
            clock=cleanup_clock,
        )

    def register_target_with_fixture_clock(
        journal_instance: object,
        **kwargs: object,
    ) -> object:
        kwargs["clock"] = cleanup_clock
        return original_register_target(journal_instance, **kwargs)

    def record_result_with_fixture_clock(
        journal_instance: object,
        **kwargs: object,
    ) -> object:
        kwargs["clock"] = cleanup_clock
        return original_record_result(journal_instance, **kwargs)

    monkeypatch.setattr(
        host.EarlyCleanupJournal,
        "advance_lifecycle",
        advance_lifecycle_with_fixture_clock,
    )
    monkeypatch.setattr(
        host.EarlyCleanupJournal,
        "register_target",
        register_target_with_fixture_clock,
    )
    monkeypatch.setattr(
        host.EarlyCleanupJournal,
        "record_result",
        record_result_with_fixture_clock,
    )

    arguments = SimpleNamespace(
        provider_contract="V13",
        artifact_root=artifact_root,
        repository=ROOT,
        package_commit=PACKAGE_COMMIT,
        secret_file=secret_file,
        early_cleanup_journal=journal.root,
    )
    assert host.privacy_violations(artifact_root) == []
    host.cleanup(arguments)

    receipt_paths = (
        pilot_root / "cleanup-export-handoff.json",
        pilot_root / "global-cleanup-intent.json",
        pilot_root / "credential-destruction-ready.json",
        pilot_root / "host-cleanup.json",
    )
    first_receipt_bytes = {path.name: path.read_bytes() for path in receipt_paths}
    first_journal_bytes = {
        str(path.relative_to(journal.root)): path.read_bytes()
        for path in journal.root.rglob("*")
        if path.is_file()
    }
    first_journal_state = journal.load()
    cleanup_projection = json.loads((pilot_root / "host-cleanup.json").read_text(encoding="utf-8"))
    assert cleanup_projection["structural_privacy_scan_passed"] is True
    assert cleanup_projection["structural_privacy_violations"] == []
    protected_target_projection = {
        target.target_id: (target.state, target.last_attempt_id)
        for target in first_journal_state.targets
        if target.kind
        in {
            CleanupTargetKind.PROVIDER_INSTANCE,
            CleanupTargetKind.FIREWALL_RESTORATION,
            CleanupTargetKind.OWNED_RULESET,
        }
    }
    assert operations == {
        "container_removal": 1,
        "credential_destruction": 1,
        "core_cleanup": 1,
        "container_enumeration": 1,
    }
    assert not image_archive.exists()
    assert not regression_archive.exists()
    assert not secret_file.exists()
    assert first_journal_state.terminal_cleanup_disposition is (TerminalCleanupDisposition.COMPLETE)

    def forbidden_target_result(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("completed cleanup must not repeat any exact-target result")

    def forbidden_unlink(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("completed cleanup must not repeat archive or credential unlink")

    monkeypatch.setattr(host.EarlyCleanupJournal, "record_result", forbidden_target_result)
    monkeypatch.setattr(Path, "unlink", forbidden_unlink)
    host.cleanup(arguments)

    assert operations == {
        "container_removal": 1,
        "credential_destruction": 1,
        "core_cleanup": 1,
        "container_enumeration": 2,
    }
    assert {path.name: path.read_bytes() for path in receipt_paths} == first_receipt_bytes
    assert {
        str(path.relative_to(journal.root)): path.read_bytes()
        for path in journal.root.rglob("*")
        if path.is_file()
    } == first_journal_bytes
    resumed_journal_state = journal.load()
    assert resumed_journal_state.sequence == first_journal_state.sequence
    assert {
        target.target_id: (target.state, target.last_attempt_id)
        for target in resumed_journal_state.targets
        if target.kind
        in {
            CleanupTargetKind.PROVIDER_INSTANCE,
            CleanupTargetKind.FIREWALL_RESTORATION,
            CleanupTargetKind.OWNED_RULESET,
        }
    } == protected_target_projection


@pytest.mark.parametrize(
    "mutation",
    (
        "empirical-entry",
        "raw-completion",
        "attempt-completion",
        "condition-reservation",
        "condition-intent",
        "export-acknowledgement",
        "retained-chronology",
    ),
)
def test_missing_manifest_with_attempt_evidence_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    host = _host(f"giclab_t09_v14_missing_manifest_{mutation.replace('-', '_')}")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    chronology: object | None = None
    run_id = V13_PROVIDER_CONTRACT.run_ids[0]
    if mutation == "empirical-entry":
        state["empirical_attempts_entered"] = [run_id]
    elif mutation == "raw-completion":
        state["raw_attempts_complete"] = [run_id]
    elif mutation == "attempt-completion":
        state["attempts_completed"] = [run_id]
    elif mutation == "condition-reservation":
        state["condition_start_reservation"] = {"run_id": run_id}
    elif mutation == "condition-intent":
        command_manifest_path = V13_PROVIDER_CONTRACT.command_manifest_path
        assert command_manifest_path is not None
        command_document = json.loads((ROOT / command_manifest_path).read_text(encoding="utf-8"))
        manifest = next(item for item in command_document["manifests"] if item["run_id"] == run_id)
        attempt_root = artifact_root / manifest["permitted_condition_owned"]["output_root"]
        _write_json(
            attempt_root / "raw/.giclab-supervisor/condition-start-intent.json",
            {"plan_id": V13_PROVIDER_CONTRACT.plan_id, "run_id": run_id},
        )
    elif mutation == "export-acknowledgement":
        _write_json(
            pilot_root / "received-export-acknowledgements" / f"{run_id}.json",
            {"plan_id": V13_PROVIDER_CONTRACT.plan_id, "run_id": run_id},
        )
    else:
        chronology = _valid_chronology(run_id)
    with pytest.raises(host.CleanupExportEvidenceError, match="frozen manifest"):
        _derive(
            host,
            artifact_root,
            state,
            journal,
            retained_chronology=chronology,
        )


def test_publication_receipt_without_manifest_fails_closed(tmp_path: Path) -> None:
    host = _host("giclab_t09_v14_partial_publication")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    _write_json(
        pilot_root / "postfreeze-validation.json",
        {
            "plan_id": V13_PROVIDER_CONTRACT.plan_id,
            "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
            "frozen_manifest_published_before_empirical_clock": True,
        },
    )
    with pytest.raises(host.CleanupExportEvidenceError, match="publication evidence is partial"):
        _derive(host, artifact_root, state, journal)


def test_valid_postfreeze_zero_attempt_handoff_requires_no_attempt_acknowledgement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_v14_postfreeze_zero")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    _publish_frozen_boundary(host, pilot_root, monkeypatch, journal=journal)
    phase = _derive(host, artifact_root, state, journal)
    assert phase.lifecycle_phase is CleanupExportLifecyclePhase.POSTFREEZE_ZERO_ATTEMPT
    assert phase.required_export_acknowledgement_count == 0
    assert host._cleanup_export_handoff(
        artifact_root,
        repository=ROOT,
        state=state,
        package_commit=PACKAGE_COMMIT,
        lifecycle_phase=phase,
        cleanup_journal=journal,
    ) == ([], None)
    receipt = json.loads((pilot_root / "cleanup-export-handoff.json").read_text(encoding="utf-8"))
    assert receipt["lifecycle_phase"] == "postfreeze-zero-attempt"
    assert receipt["frozen_manifest_state"] == "published-valid"


def test_empirical_prefix_missing_acknowledgement_remains_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host("giclab_t09_v14_empirical_missing_ack")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    _publish_frozen_boundary(host, pilot_root, monkeypatch, journal=journal, include_preflight=True)
    run_id = V13_PROVIDER_CONTRACT.run_ids[0]
    state["empirical_attempts_entered"] = [run_id]
    state["supervised_release_bindings"] = {run_id: "a" * 64}
    state["raw_attempts_complete"] = [run_id]
    state["raw_attempt_bindings"] = {
        run_id: {"manifest_sha256": "b" * 64, "receipt_sha256": "c" * 64}
    }
    _write_json(pilot_root / "pilot-state.json", state)
    journal.advance_lifecycle(
        CleanupLifecycleStage.EMPIRICAL_ENTRY,
        clock=lambda: 1_900_000_030.0,
    )
    phase = _derive(host, artifact_root, state, journal)
    assert phase.lifecycle_phase is CleanupExportLifecyclePhase.EMPIRICAL_PREFIX
    assert phase.required_export_acknowledgement_count == 1
    with pytest.raises(
        host.T09HostError,
        match="prior attempt archive lacks its off-host verification acknowledgement",
    ):
        host._cleanup_export_handoff(
            artifact_root,
            repository=ROOT,
            state=state,
            package_commit=PACKAGE_COMMIT,
            lifecycle_phase=phase,
            cleanup_journal=journal,
        )
    assert not (pilot_root / "cleanup-export-handoff.json").exists()


@pytest.mark.parametrize(
    "unsafe_kind",
    ("malformed", "symlink", "directory", "wrong-mode", "replaced"),
)
def test_published_manifest_with_unsafe_identity_fails_closed(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    host = _host(f"giclab_t09_v14_unsafe_manifest_{unsafe_kind}")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    journal.begin_freeze_publication(clock=lambda: 1_900_000_002.0)
    manifest_path = pilot_root / "frozen-run-manifest.json"
    if unsafe_kind == "malformed":
        manifest_path.write_text("{", encoding="utf-8")
        manifest_path.chmod(0o600)
    elif unsafe_kind == "symlink":
        target = pilot_root / "manifest-target.json"
        _write_json(target, {"plan_id": V13_PROVIDER_CONTRACT.plan_id})
        os.symlink(target.name, manifest_path)
    elif unsafe_kind == "directory":
        manifest_path.mkdir(mode=0o700)
    else:
        _write_json(
            manifest_path,
            {
                "manifest_id": V13_PROVIDER_CONTRACT.frozen_run_manifest_id,
                "plan_id": V13_PROVIDER_CONTRACT.plan_id,
                "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
                "clean_package_commit": PACKAGE_COMMIT,
                "replacement_image_id": "sha256:" + "5" * 64,
            },
        )
        if unsafe_kind == "wrong-mode":
            manifest_path.chmod(0o644)
    receipt_sha256 = (
        "d" * 64 if unsafe_kind in {"directory", "replaced"} else _sha256(manifest_path)
    )
    _write_json(
        pilot_root / "postfreeze-validation.json",
        {
            "plan_id": V13_PROVIDER_CONTRACT.plan_id,
            "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
            "package_commit": PACKAGE_COMMIT,
            "frozen_run_manifest_sha256": receipt_sha256,
            "frozen_manifest_published_before_empirical_clock": True,
            "frozen_manifest_published_at_epoch": 1_900_000_010.0,
        },
    )
    with pytest.raises(host.CleanupExportEvidenceError, match="published frozen manifest"):
        _derive(host, artifact_root, state, journal)


def test_wrong_cleanup_journal_plan_identity_fails_closed(tmp_path: Path) -> None:
    host = _host("giclab_t09_v14_wrong_cleanup_plan")
    artifact_root, _pilot_root, state, _journal = _v13_stopped_fixture(tmp_path)
    wrong_journal = EarlyCleanupJournal.initialize(
        tmp_path / "wrong-early-cleanup-state",
        plan_id=V13_PROVIDER_CONTRACT.plan_id,
        host_run_id=V13_PROVIDER_CONTRACT.host_run_id,
        package_commit=PACKAGE_COMMIT,
        plan_sha256="e" * 64,
        provider_instance_id="wrong-plan-provider-instance",
        provider_instance_identity_sha256="f" * 64,
        provider_started_at_epoch=1_899_996_524.306765,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="0" * 64,
    )
    with pytest.raises(host.CleanupExportEvidenceError, match="selected provider contract"):
        _derive(host, artifact_root, state, wrong_journal)


def test_wrong_provider_entry_host_identity_fails_closed(tmp_path: Path) -> None:
    host = _host("giclab_t09_v14_wrong_cleanup_host")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    entry_path = pilot_root / "provider-entry.json"
    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    entry["host_run_id"] = "RUN-T09-PILOT-HOST-AUTONOMOUS-WRONG"
    _write_json(entry_path, entry)
    with pytest.raises(host.T09HostError, match="another provider contract"):
        _derive(host, artifact_root, state, journal)


def test_published_manifest_cannot_contradict_tracked_no_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host = _host("giclab_t09_r3_publication_contradiction")
    artifact_root, pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    assert journal.load().freeze_publication_started is False
    _publish_frozen_boundary(host, pilot_root, monkeypatch)
    with pytest.raises(host.CleanupExportEvidenceError, match=r"publication.*contradict"):
        _derive(host, artifact_root, state, journal)


def test_missing_manifest_after_publication_intent_is_not_prefreeze(tmp_path: Path) -> None:
    host = _host("giclab_t09_r3_missing_publication")
    artifact_root, _pilot_root, state, journal = _v13_stopped_fixture(tmp_path)
    journal.begin_freeze_publication(clock=lambda: 1_900_000_002.0)
    with pytest.raises(host.CleanupExportEvidenceError, match=r"pre-freeze.*contradict"):
        _derive(host, artifact_root, state, journal)
