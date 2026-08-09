from __future__ import annotations

import hashlib
import json
import os
import plistlib
from dataclasses import replace
from pathlib import Path

import pytest

from giclab.harness.sira_storage import (
    ACTIVE_ATTEMPT_CAP_BYTES,
    ACTIVE_ATTEMPT_ROOT,
    APPROVED_EXTERNAL_CAPACITY_BYTES,
    APPROVED_MOUNT,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    B2A_AUTHORIZATION_PLACEHOLDER,
    B2A_PLAN_ID,
    BUILD_STAGING_ROOT,
    DOCKER_DISK_IMAGE_ROOT,
    DOCKER_DMG_BYTES,
    EXTERNAL_INCREMENTAL_RESERVATION_BYTES,
    EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES,
    EXTERNAL_RETAINED_FREE_FLOOR_BYTES,
    SEALED_ARTIFACT_ROOT,
    SUPERSEDED_PLAN_ID,
    SUPERSEDED_PLAN_SHA256,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_MOUNT,
    SYSTEM_DATA_VOLUME_UUID,
    B2APlan,
    B2AStep,
    B2AStepKind,
    DockerPlacementEvidence,
    ReconnectQualification,
    ReconnectState,
    RootPurpose,
    StorageContractError,
    StorageGuardToken,
    SystemFloorInputs,
    VolumeObservation,
    _validate_b2a_argv,
    copy_sealed_attempt,
    retained_free_floor,
    sanitize_docker_settings,
    seal_attempt,
    validate_bounded_path,
    volume_observation_from_diskutil,
)
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]


def _external_observation(*, free_bytes: int = EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES):
    return VolumeObservation(
        mount_path=APPROVED_MOUNT,
        filesystem="apfs",
        writable=True,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        total_bytes=APPROVED_EXTERNAL_CAPACITY_BYTES,
        free_bytes=free_bytes,
        internal=False,
        owners_enabled=False,
        encrypted=True,
        unlocked=True,
        device_identifier="disk99s5",
        bus_protocol="Thunderbolt",
        device_tree_path="IODeviceTree:/UTDM@0",
    )


def _system_observation(*, free_bytes: int = SYSTEM_CAPACITY_BYTES):
    return VolumeObservation(
        mount_path=SYSTEM_DATA_MOUNT,
        filesystem="APFS",
        writable=True,
        volume_uuid=SYSTEM_DATA_VOLUME_UUID,
        physical_store_uuid=None,
        total_bytes=SYSTEM_CAPACITY_BYTES,
        free_bytes=free_bytes,
        internal=True,
        owners_enabled=True,
        encrypted=True,
        unlocked=True,
        device_identifier="disk3s5",
    )


def _user_step(action_id: str) -> B2AStep:
    return B2AStep(
        action_id=action_id,
        kind=B2AStepKind.USER_ONLY,
        timeout_seconds=60,
        output_limit_bytes=0,
        argv=None,
        instruction=f"Perform {action_id} personally and stop on any mismatch.",
        stop_on_failure=True,
        retry_limit=0,
    )


def _blocked_plan() -> B2APlan:
    steps = (
        B2AStep(
            action_id="repository-preflight",
            kind=B2AStepKind.AUTOMATABLE,
            timeout_seconds=10,
            output_limit_bytes=1024,
            argv=("/usr/bin/git", "status", "--short"),
            instruction=None,
            stop_on_failure=True,
            retry_limit=0,
        ),
        _user_step("accept-terms-personally"),
        _user_step("disable-automatic-update"),
        _user_step("select-external-disk-location"),
        _user_step("eject-disconnect"),
        _user_step("reconnect-remount-unlock"),
    )
    return B2APlan(
        schema_version="0.1.0",
        plan_id=B2A_PLAN_ID,
        authorization_reference=B2A_AUTHORIZATION_PLACEHOLDER,
        authorized=False,
        implementation_commit="a" * 40,
        aggregate_wall_seconds=600,
        aggregate_output_bytes=2048,
        aggregate_download_bytes=DOCKER_DMG_BYTES,
        system_floor_inputs=SystemFloorInputs(os_operating_headroom_bytes=None),
        external_incremental_disk_bytes=EXTERNAL_INCREMENTAL_RESERVATION_BYTES,
        active_attempt_bytes=ACTIVE_ATTEMPT_CAP_BYTES,
        steps=steps,
        superseded_plan_id=SUPERSEDED_PLAN_ID,
        superseded_plan_sha256=SUPERSEDED_PLAN_SHA256,
    )


def test_project_floor_is_greater_of_150_gib_and_20_percent() -> None:
    assert retained_free_floor(APPROVED_EXTERNAL_CAPACITY_BYTES) == 200_048_192_717
    assert retained_free_floor(500 * 1024**3) == 161_061_273_600


def test_external_volume_requires_both_stable_uuids_apfs_and_writable() -> None:
    _external_observation().validate_external(reserve_incremental=True)
    for changed in (
        {"volume_uuid": "00000000-0000-0000-0000-000000000000"},
        {"physical_store_uuid": "00000000-0000-0000-0000-000000000000"},
        {"filesystem": "hfs"},
        {"writable": False},
        {"internal": True},
        {"unlocked": False},
    ):
        with pytest.raises(StorageContractError):
            replace(_external_observation(), **changed).validate_external(reserve_incremental=True)


def test_missing_or_renamed_external_volume_fails() -> None:
    with pytest.raises(StorageContractError, match="missing or mounted"):
        replace(_external_observation(), mount_path=Path("/Volumes/Renamed")).validate_external(
            reserve_incremental=True
        )


def test_external_floor_is_enforced_before_and_after_actions() -> None:
    with pytest.raises(StorageContractError):
        _external_observation(free_bytes=EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES - 1).validate_external(
            reserve_incremental=True
        )
    _external_observation(free_bytes=EXTERNAL_RETAINED_FREE_FLOOR_BYTES).validate_external(
        reserve_incremental=False
    )
    with pytest.raises(StorageContractError):
        _external_observation(free_bytes=EXTERNAL_RETAINED_FREE_FLOOR_BYTES - 1).validate_external(
            reserve_incremental=False
        )


def test_system_floor_fails_closed_until_every_evidence_term_is_known() -> None:
    unresolved = SystemFloorInputs(os_operating_headroom_bytes=None)
    with pytest.raises(StorageContractError, match="unresolved"):
        _system_observation().validate_system(floor_inputs=unresolved)
    resolved = SystemFloorInputs(
        os_operating_headroom_bytes=20,
        installed_app_bytes=30,
        support_files_bytes=40,
        update_rollback_bytes=50,
        failure_cleanup_bytes=60,
        first_start_internal_bytes=70,
    )
    assert resolved.resolved_floor_bytes() == 573_592_444 + 67_108_864 + 270
    with pytest.raises(StorageContractError, match="below required"):
        _system_observation(free_bytes=1).validate_system(floor_inputs=resolved)


def test_diskutil_parser_uses_stable_fields_not_device_numbers() -> None:
    volume = plistlib.dumps(
        {
            "MountPoint": str(APPROVED_MOUNT),
            "FilesystemType": "apfs",
            "VolumeUUID": APPROVED_VOLUME_UUID,
            "DeviceIdentifier": "disk99s5",
            "Writable": True,
            "WritableVolume": True,
            "Internal": False,
            "OSInternalMedia": False,
            "GlobalPermissionsEnabled": False,
            "Encryption": True,
            "Locked": False,
            "BusProtocol": "Thunderbolt",
            "DeviceTreePath": "IODeviceTree:/UTDM@0",
        }
    )
    apfs_list = plistlib.dumps(
        {
            "Containers": [
                {
                    "CapacityCeiling": APPROVED_EXTERNAL_CAPACITY_BYTES,
                    "CapacityFree": EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES,
                    "PhysicalStores": [{"DiskUUID": APPROVED_PHYSICAL_STORE_UUID}],
                    "Volumes": [{"APFSVolumeUUID": APPROVED_VOLUME_UUID}],
                }
            ]
        }
    )
    observation = volume_observation_from_diskutil(volume, apfs_list)
    observation.validate_external(reserve_incremental=True)
    assert observation.device_identifier == "disk99s5"
    assert not observation.owners_enabled


def test_diskutil_parser_rejects_missing_or_duplicate_volume_container_match() -> None:
    volume = plistlib.dumps(
        {
            "MountPoint": str(APPROVED_MOUNT),
            "FilesystemType": "apfs",
            "VolumeUUID": APPROVED_VOLUME_UUID,
            "DeviceIdentifier": "disk99s5",
            "Writable": True,
            "WritableVolume": True,
        }
    )
    container = {
        "CapacityCeiling": APPROVED_EXTERNAL_CAPACITY_BYTES,
        "CapacityFree": EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES,
        "PhysicalStores": [{"DiskUUID": APPROVED_PHYSICAL_STORE_UUID}],
        "Volumes": [{"APFSVolumeUUID": APPROVED_VOLUME_UUID}],
    }
    with pytest.raises(StorageContractError, match="exactly one"):
        volume_observation_from_diskutil(volume, plistlib.dumps({"Containers": []}))
    with pytest.raises(StorageContractError, match="exactly one"):
        volume_observation_from_diskutil(
            volume, plistlib.dumps({"Containers": [container, container]})
        )


def test_path_guard_rejects_symlink_escape_and_internal_fallback(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    expected_device = root.stat().st_dev
    link = root / "link"
    link.symlink_to(tmp_path)
    with pytest.raises(StorageContractError, match="symlink"):
        validate_bounded_path(
            link / "escaped",
            approved_root=root,
            expected_device=expected_device,
            prohibited_device=expected_device + 1,
            allow_missing_leaf=True,
        )
    with pytest.raises(StorageContractError, match="prohibited"):
        validate_bounded_path(
            root / "safe",
            approved_root=root,
            expected_device=expected_device,
            prohibited_device=expected_device,
            allow_missing_leaf=True,
        )


def test_path_guard_rejects_escape_and_missing_required_path(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    with pytest.raises(StorageContractError, match="escaped"):
        validate_bounded_path(
            tmp_path / "outside",
            approved_root=root,
            expected_device=root.stat().st_dev,
            prohibited_device=root.stat().st_dev + 1,
            allow_missing_leaf=True,
        )
    with pytest.raises(StorageContractError, match="missing"):
        validate_bounded_path(
            root / "missing",
            approved_root=root,
            expected_device=root.stat().st_dev,
            prohibited_device=root.stat().st_dev + 1,
            allow_missing_leaf=False,
        )


def test_storage_guard_token_is_single_use_and_stale_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Production tokens bind exact roots.  Redirect the constants to a bounded fixture
    # while preserving the same validator and one-shot consumption path.
    external = tmp_path / "external"
    external.mkdir()
    disk_root = external / "disk"
    monkeypatch.setattr("giclab.harness.sira_storage.DOCKER_DISK_IMAGE_ROOT", disk_root)
    monkeypatch.setattr("giclab.harness.sira_storage.APPROVED_EXTERNAL_ROOT", external)
    guard = StorageGuardToken(
        purpose=RootPurpose.DOCKER_DISK,
        path=disk_root,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        external_device=external.stat().st_dev,
        system_device=external.stat().st_dev + 1,
        issued_monotonic_ns=100,
        maximum_age_ns=10,
    )
    guard.consume(observation=_external_observation(), now_monotonic_ns=105)
    with pytest.raises(StorageContractError, match="already consumed"):
        guard.consume(observation=_external_observation(), now_monotonic_ns=106)
    stale = replace(guard, consumed=False, issued_monotonic_ns=100)
    with pytest.raises(StorageContractError, match="stale"):
        stale.consume(observation=_external_observation(), now_monotonic_ns=111)


def test_active_attempt_and_external_archive_roles_are_distinct() -> None:
    assert ACTIVE_ATTEMPT_ROOT.is_relative_to(Path("/Users/joseph"))
    assert not ACTIVE_ATTEMPT_ROOT.is_relative_to(APPROVED_MOUNT)
    assert DOCKER_DISK_IMAGE_ROOT.is_relative_to(APPROVED_MOUNT / "GIC-Lab")
    assert BUILD_STAGING_ROOT.is_relative_to(APPROVED_MOUNT / "GIC-Lab")
    assert SEALED_ARTIFACT_ROOT.is_relative_to(APPROVED_MOUNT / "GIC-Lab")
    assert len({DOCKER_DISK_IMAGE_ROOT, BUILD_STAGING_ROOT, SEALED_ARTIFACT_ROOT}) == 3


def test_reconnect_state_machine_rejects_skip_replay_and_identity_change() -> None:
    qualification = ReconnectQualification(
        expected_volume_uuid=APPROVED_VOLUME_UUID,
        expected_physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        expected_disk_identity="inode:123:size:456",
        expected_engine_identity="engine-1",
    )
    with pytest.raises(StorageContractError, match="out of order"):
        qualification.advance(ReconnectState.USER_EJECTED)
    qualification.advance(ReconnectState.PRE_EJECT_ENGINE_STOPPED)
    qualification.advance(ReconnectState.USER_EJECTED)
    qualification.advance(ReconnectState.USER_DISCONNECTED)
    qualification.advance(ReconnectState.USER_RECONNECTED)
    with pytest.raises(StorageContractError, match="UUID mismatch"):
        qualification.advance(
            ReconnectState.VOLUME_REQUALIFIED,
            volume_uuid="wrong",
            physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        )
    qualification.advance(
        ReconnectState.VOLUME_REQUALIFIED,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
    )
    qualification.advance(
        ReconnectState.PATHS_REQUALIFIED,
        volume_uuid=APPROVED_VOLUME_UUID,
        physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
    )
    qualification.advance(ReconnectState.USER_ENGINE_RESTARTED)
    with pytest.raises(StorageContractError, match="different disk"):
        qualification.advance(ReconnectState.SAME_DISK_REOPENED, disk_identity="inode:999:size:456")
    qualification.advance(ReconnectState.SAME_DISK_REOPENED, disk_identity="inode:123:size:456")
    qualification.advance(ReconnectState.ENGINE_HEALTHY, engine_identity="engine-1")
    qualification.advance(ReconnectState.FINAL_ENGINE_STOPPED)
    qualification.advance(ReconnectState.EVIDENCE_SEALED)
    with pytest.raises(StorageContractError, match="out of order"):
        qualification.advance(ReconnectState.EVIDENCE_SEALED)


def test_settings_evidence_is_minimized_and_placement_is_machine_checked() -> None:
    settings = {
        "dataFolder": str(DOCKER_DISK_IMAGE_ROOT),
        "diskSizeMiB": 65536,
        "autoDownloadUpdates": False,
        "credentialHelper": "must-not-retain",
        "proxy": "must-not-retain",
    }
    sanitized = sanitize_docker_settings(settings)
    assert set(sanitized) == {"dataFolder", "diskSizeMiB", "autoDownloadUpdates"}
    encoded = json.dumps(sanitized, sort_keys=True, separators=(",", ":")).encode()
    evidence = DockerPlacementEvidence(
        configured_data_folder=DOCKER_DISK_IMAGE_ROOT,
        disk_path=DOCKER_DISK_IMAGE_ROOT / "Docker.raw",
        disk_device=44,
        disk_inode=123,
        disk_logical_bytes=64 * 1024**3,
        disk_allocated_bytes=1024,
        engine_identity="engine-1",
        settings_sha256=hashlib.sha256(encoded).hexdigest(),
        default_internal_exists=False,
        default_internal_active=False,
    )
    evidence.validate(external_device=44, sanitized_settings=sanitized)
    placement_document = {
        "schema_version": "0.1.0",
        "volume_uuid": APPROVED_VOLUME_UUID,
        "physical_store_uuid": APPROVED_PHYSICAL_STORE_UUID,
        "configured_data_folder": str(DOCKER_DISK_IMAGE_ROOT),
        "settings_source": "/version-verified/source",
        "settings_key": "versionVerifiedKey",
        "settings_sha256": evidence.settings_sha256,
        "disk": {
            "path": str(evidence.disk_path),
            "device": evidence.disk_device,
            "inode": evidence.disk_inode,
            "logical_bytes": evidence.disk_logical_bytes,
            "allocated_bytes": evidence.disk_allocated_bytes,
        },
        "engine_identity": evidence.engine_identity,
        "default_internal": {
            "verified_path": "/version-verified/default/Docker.raw",
            "exists": False,
            "active": False,
        },
        "captured_at_utc": "2026-08-09T16:00:00Z",
    }
    assert (
        validate_instance(
            placement_document,
            ROOT / "schemas/docker-storage-placement-evidence.schema.json",
        )
        == []
    )
    with pytest.raises(StorageContractError, match="internal"):
        replace(evidence, default_internal_exists=True).validate(
            external_device=44, sanitized_settings=sanitized
        )


def test_archive_copy_verifies_hashes_and_retains_source(tmp_path: Path) -> None:
    source = tmp_path / "active" / "attempt-1"
    source.mkdir(parents=True)
    (source / "nested").mkdir()
    (source / "nested/evidence.txt").write_text("bounded evidence\n")
    archive = tmp_path / "archive"
    archive.mkdir()
    records = tmp_path / "records"
    seal = seal_attempt(source, attempt_id="attempt-1", max_bytes=1024)
    record = copy_sealed_attempt(
        source,
        archive_parent=archive,
        archive_id="attempt-1-sealed",
        copy_record_path=records / "attempt-1.json",
        max_bytes=1024,
        source_volume_uuid=SYSTEM_DATA_VOLUME_UUID,
        destination_volume_uuid=APPROVED_VOLUME_UUID,
        copied_at_utc="2026-08-09T16:00:00Z",
    )
    assert seal["total_payload_bytes"] == len("bounded evidence\n")
    assert record["source_retained"] is True
    assert source.exists()
    assert (archive / "attempt-1-sealed/nested/evidence.txt").read_text() == "bounded evidence\n"
    assert json.loads((records / "attempt-1.json").read_text())["files_verified"] == 1
    assert validate_instance(record, ROOT / "schemas/sealed-artifact-copy.schema.json") == []
    os.chmod(source, 0o700)
    os.chmod(source / "nested", 0o700)
    os.chmod(source / "nested/evidence.txt", 0o600)
    os.chmod(source / "SEAL.json", 0o600)


def test_archive_rejects_symlinks_and_byte_overflow(tmp_path: Path) -> None:
    source = tmp_path / "attempt"
    source.mkdir()
    (source / "escape").symlink_to(tmp_path)
    with pytest.raises(StorageContractError, match="symlink"):
        seal_attempt(source, attempt_id="attempt", max_bytes=1024)
    (source / "escape").unlink()
    (source / "large").write_bytes(b"x" * 10)
    with pytest.raises(StorageContractError, match="byte cap"):
        seal_attempt(source, attempt_id="attempt", max_bytes=9)


def test_blocked_b2a_plan_is_separate_from_b2b_and_old_plan() -> None:
    plan = _blocked_plan()
    plan.validate()
    assert plan.plan_id != SUPERSEDED_PLAN_ID
    assert "B2B" not in plan.plan_id
    assert not plan.authorized
    with pytest.raises(StorageContractError, match="stale"):
        replace(plan, plan_id=SUPERSEDED_PLAN_ID).validate()


@pytest.mark.parametrize(
    "argv",
    [
        ("/Applications/Docker.app/Contents/Resources/bin/docker", "pull", "image"),
        ("/Applications/Docker.app/Contents/Resources/bin/docker", "build", "."),
        ("/Applications/Docker.app/Contents/Resources/bin/docker", "create", "image"),
        ("/usr/bin/python3", "-m", "playwright", "install", "chromium"),
        ("/usr/bin/python3", "-m", "giclab", "--secret-file", "/tmp/value"),
        ("/bin/sh", "-c", "true"),
    ],
)
def test_b2a_rejects_pull_build_container_browser_api_secret_and_shell(
    argv: tuple[str, ...],
) -> None:
    with pytest.raises(StorageContractError):
        _validate_b2a_argv(argv)


def test_module_has_no_secret_value_or_environment_access_path() -> None:
    source = (ROOT / "src/giclab/harness/sira_storage.py").read_text().casefold()
    assert "os.environ" not in source
    assert "getenv(" not in source


def test_locked_exp_0001_scientific_files_did_not_drift() -> None:
    experiment = "experiments/EXP-0001-sira-simulative-vs-reactive"
    expected = {
        f"{experiment}/protocol.yaml": (
            "5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c"
        ),
        f"{experiment}/config.yaml": (
            "f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d"
        ),
        f"{experiment}/run-plans/smoke.yaml": (
            "ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425"
        ),
        f"{experiment}/run-plans/conditions/smoke-reactive.yaml": (
            "7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018"
        ),
        f"{experiment}/run-plans/conditions/smoke-simulative.yaml": (
            "68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436"
        ),
    }
    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
