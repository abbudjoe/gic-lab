from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from giclab.harness.t09_cleanup_state import (
    CleanupExportLifecyclePhase,
    CleanupExportPhaseEvidence,
    CleanupLifecycleStage,
    EarlyCleanupJournal,
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
) -> tuple[dict[str, object], str]:
    frozen: dict[str, object] = {
        "manifest_id": V13_PROVIDER_CONTRACT.frozen_run_manifest_id,
        "plan_id": V13_PROVIDER_CONTRACT.plan_id,
        "host_run_id": V13_PROVIDER_CONTRACT.host_run_id,
        "clean_package_commit": PACKAGE_COMMIT,
        "replacement_image_id": "sha256:" + "5" * 64,
    }
    frozen_path = pilot_root / "frozen-run-manifest.json"
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
    _publish_frozen_boundary(host, pilot_root, monkeypatch)
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
    _publish_frozen_boundary(host, pilot_root, monkeypatch, include_preflight=True)
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
