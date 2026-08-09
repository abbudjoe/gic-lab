from __future__ import annotations

import hashlib
import json
import os
import plistlib
import stat
from dataclasses import replace
from pathlib import Path

import pytest

from giclab.harness.sira_storage import (
    _SUPERVISOR_CLOSE_ISSUER,
    ACTIVE_ATTEMPT_CAP_BYTES,
    ACTIVE_ATTEMPT_ROOT,
    APPROVED_EXTERNAL_CAPACITY_BYTES,
    APPROVED_MOUNT,
    APPROVED_PHYSICAL_STORE_UUID,
    APPROVED_VOLUME_UUID,
    B2A_AGGREGATE_DOWNLOAD_CAP_BYTES,
    B2A_AGGREGATE_OUTPUT_CAP_BYTES,
    B2A_AGGREGATE_WALL_SECONDS,
    B2A_AUTHORIZATION_PLACEHOLDER,
    B2A_IMPLEMENTATION_BOUND_PATHS,
    B2A_PLAN_ID,
    B2A_SCIENTIFIC_LOCKED_PATHS,
    BUILD_STAGING_ROOT,
    DOCKER_DISK_IMAGE_ROOT,
    EXTERNAL_INCREMENTAL_RESERVATION_BYTES,
    EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES,
    EXTERNAL_RETAINED_FREE_FLOOR_BYTES,
    SEALED_ARTIFACT_ROOT,
    SUPERSEDED_PLAN_ID,
    SUPERSEDED_PLAN_SHA256,
    SYSTEM_CAPACITY_BYTES,
    SYSTEM_DATA_MOUNT,
    SYSTEM_DATA_VOLUME_UUID,
    AttemptCloseEvidence,
    B2AActionResult,
    B2AExecutionSupervisor,
    B2APlan,
    B2AResourceSnapshot,
    B2AStep,
    B2AStepKind,
    DockerDiskIdentity,
    DockerEngineIdentity,
    DockerPlacementEvidence,
    ReconnectQualification,
    ReconnectState,
    RootPurpose,
    StorageContractError,
    SystemFloorInputs,
    VolumeObservation,
    _guard_argv,
    _seal_and_copy_argv,
    _validate_b2a_argv,
    copy_sealed_attempt,
    issue_storage_guard,
    load_b2a_plan,
    qualify_archive_placement,
    retained_free_floor,
    sanitize_docker_settings,
    seal_attempt,
    validate_bounded_path,
    verify_docker_dmg,
    verify_official_docker_metadata,
    volume_observation_from_diskutil,
)
from giclab.harness.sira_storage import (
    main as storage_main,
)
from giclab.validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]


def _external_observation(
    *, free_bytes: int = EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES
) -> VolumeObservation:
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


def _system_observation(*, free_bytes: int = SYSTEM_CAPACITY_BYTES) -> VolumeObservation:
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


def _close_evidence(source: Path, attempt_id: str) -> AttemptCloseEvidence:
    return AttemptCloseEvidence(
        attempt_id=attempt_id,
        source_path=source,
        supervisor_plan_id="PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V2-TEST",
        supervisor_plan_sha256="c" * 64,
        authorization_reference="AUTH-T07-GATE-B2A-TEST",
        all_actions_before_seal_complete=True,
        open_writer_count=0,
        closed_at_utc="2026-08-09T16:00:00Z",
        _issuer=_SUPERVISOR_CLOSE_ISSUER,
    )


def _user_step(action_id: str) -> B2AStep:
    return B2AStep(
        action_id=action_id,
        kind=B2AStepKind.USER_ONLY,
        timeout_seconds=60,
        output_limit_bytes=0,
        download_limit_bytes=0,
        internal_disk_limit_bytes=0,
        external_disk_limit_bytes=0,
        argv=None,
        instruction=f"Perform {action_id} personally and stop on any mismatch.",
        stop_on_failure=True,
        retry_limit=0,
    )


def _blocked_plan() -> B2APlan:
    implementation_commit = "a" * 40
    repository_steps = tuple(
        B2AStep(
            action_id=action_id,
            kind=B2AStepKind.AUTOMATABLE,
            timeout_seconds=10,
            output_limit_bytes=1024,
            download_limit_bytes=0,
            internal_disk_limit_bytes=0,
            external_disk_limit_bytes=0,
            argv=argv,
            instruction=None,
            stop_on_failure=True,
            retry_limit=0,
            expected_stdout=expected_stdout,
        )
        for action_id, argv, expected_stdout in (
            ("repository-status", ("/usr/bin/git", "status", "--short"), ""),
            (
                "repository-branch",
                ("/usr/bin/git", "branch", "--show-current"),
                "phase-1/sira-smoke\n",
            ),
            (
                "repository-implementation-ancestor",
                (
                    "/usr/bin/git",
                    "merge-base",
                    "--is-ancestor",
                    implementation_commit,
                    "HEAD",
                ),
                "",
            ),
            (
                "repository-implementation-tree",
                (
                    "/usr/bin/git",
                    "diff",
                    "--quiet",
                    implementation_commit,
                    "--",
                    *B2A_IMPLEMENTATION_BOUND_PATHS,
                ),
                "",
            ),
            (
                "repository-science-tree",
                (
                    "/usr/bin/git",
                    "diff",
                    "--quiet",
                    implementation_commit,
                    "--",
                    *B2A_SCIENTIFIC_LOCKED_PATHS,
                ),
                "",
            ),
        )
    )
    select_guard = B2AStep(
        action_id="guard-select-external-disk-location",
        kind=B2AStepKind.AUTOMATABLE,
        timeout_seconds=10,
        output_limit_bytes=1024,
        download_limit_bytes=0,
        internal_disk_limit_bytes=0,
        external_disk_limit_bytes=0,
        argv=_guard_argv(
            "select-external-disk-location",
            (RootPurpose.DOCKER_DISK, RootPurpose.BUILD_STAGING, RootPurpose.B2A_WORK),
            require_existing=True,
        ),
        instruction=None,
        stop_on_failure=True,
        retry_limit=0,
        guard_for_action="select-external-disk-location",
        guard_purposes=(
            RootPurpose.DOCKER_DISK,
            RootPurpose.BUILD_STAGING,
            RootPurpose.B2A_WORK,
        ),
    )
    steps = (
        *repository_steps,
        _user_step("accept-terms-personally"),
        _user_step("disable-automatic-update"),
        select_guard,
        _user_step("select-external-disk-location"),
        _user_step("eject-disconnect"),
        _user_step("reconnect-remount-unlock"),
    )
    return B2APlan(
        schema_version="0.1.0",
        plan_id=B2A_PLAN_ID,
        status="blocked-design-only",
        blocking_requirements=("synthetic unresolved storage evidence",),
        authorization_reference=B2A_AUTHORIZATION_PLACEHOLDER,
        authorized=False,
        implementation_commit=implementation_commit,
        aggregate_wall_seconds=B2A_AGGREGATE_WALL_SECONDS,
        aggregate_output_bytes=B2A_AGGREGATE_OUTPUT_CAP_BYTES,
        aggregate_download_bytes=B2A_AGGREGATE_DOWNLOAD_CAP_BYTES,
        system_incremental_disk_bytes=None,
        system_floor_inputs=SystemFloorInputs(os_operating_headroom_bytes=None),
        external_incremental_disk_bytes=EXTERNAL_INCREMENTAL_RESERVATION_BYTES,
        active_attempt_bytes=ACTIVE_ATTEMPT_CAP_BYTES,
        steps=steps,
        superseded_plan_id=SUPERSEDED_PLAN_ID,
        superseded_plan_sha256=SUPERSEDED_PLAN_SHA256,
        aggregate_automatable_calls=6,
        document_sha256="c" * 64,
    )


def _authorized_plan() -> B2APlan:
    floor_inputs = SystemFloorInputs(
        os_operating_headroom_bytes=0,
        installed_app_bytes=0,
        support_files_bytes=0,
        update_rollback_bytes=0,
        failure_cleanup_bytes=0,
        first_start_internal_bytes=0,
    )
    floor = floor_inputs.resolved_floor_bytes()
    blocked = _blocked_plan()
    steps = tuple(
        replace(
            step,
            argv=_guard_argv(
                step.guard_for_action,
                step.guard_purposes,
                require_existing=True,
                system_floor_bytes=str(floor),
            ),
        )
        if step.guard_for_action is not None
        else step
        for step in blocked.steps
    )
    return replace(
        blocked,
        plan_id="PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V2-TEST",
        status="authorized-executable",
        blocking_requirements=(),
        authorization_reference="AUTH-T07-GATE-B2A-TEST",
        authorized=True,
        system_incremental_disk_bytes=1024,
        system_floor_inputs=floor_inputs,
        steps=steps,
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
            "Locked": False,
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


def test_diskutil_parser_requires_explicit_lock_and_utdm_evidence() -> None:
    volume = {
        "MountPoint": str(APPROVED_MOUNT),
        "FilesystemType": "apfs",
        "VolumeUUID": APPROVED_VOLUME_UUID,
        "DeviceIdentifier": "disk99s5",
        "Writable": True,
        "WritableVolume": True,
        "Internal": False,
        "OSInternalMedia": False,
        "BusProtocol": "Thunderbolt",
        "DeviceTreePath": "IODeviceTree:/UTDM@0",
    }
    container = {
        "CapacityCeiling": APPROVED_EXTERNAL_CAPACITY_BYTES,
        "CapacityFree": EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES,
        "PhysicalStores": [{"DiskUUID": APPROVED_PHYSICAL_STORE_UUID}],
        "Volumes": [{"APFSVolumeUUID": APPROVED_VOLUME_UUID}],
    }
    with pytest.raises(StorageContractError, match="lock-state"):
        volume_observation_from_diskutil(
            plistlib.dumps(volume), plistlib.dumps({"Containers": [container]})
        )
    volume["Locked"] = False
    observation = volume_observation_from_diskutil(
        plistlib.dumps(volume), plistlib.dumps({"Containers": [container]})
    )
    with pytest.raises(StorageContractError, match="Thunderbolt UTDM"):
        replace(observation, bus_protocol="USB").validate_external(reserve_incremental=True)


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
    external_device = 101
    system_device = 202

    def resolve_device(path: Path) -> int:
        return external_device if path.is_relative_to(external) else system_device

    bundle = issue_storage_guard(
        external=_external_observation(),
        system=_system_observation(),
        external_device=external_device,
        system_device=system_device,
        system_floor_bytes=1,
        purposes=(RootPurpose.DOCKER_DISK,),
        require_existing=False,
        issued_monotonic_ns=100,
        device_resolver=resolve_device,
    )
    guard = bundle.tokens[RootPurpose.DOCKER_DISK]
    guard.maximum_age_ns = 10
    guard.consume(
        observation=_external_observation(),
        now_monotonic_ns=105,
        device_resolver=resolve_device,
    )
    with pytest.raises(StorageContractError, match="already consumed"):
        guard.consume(
            observation=_external_observation(),
            now_monotonic_ns=106,
            device_resolver=resolve_device,
        )
    stale = replace(guard, consumed=False, issued_monotonic_ns=100)
    with pytest.raises(StorageContractError, match="stale"):
        stale.consume(
            observation=_external_observation(),
            now_monotonic_ns=111,
            device_resolver=resolve_device,
        )


def test_active_attempt_and_external_archive_roles_are_distinct() -> None:
    assert ACTIVE_ATTEMPT_ROOT.is_relative_to(Path("/Users/joseph"))
    assert not ACTIVE_ATTEMPT_ROOT.is_relative_to(APPROVED_MOUNT)
    assert DOCKER_DISK_IMAGE_ROOT.is_relative_to(APPROVED_MOUNT / "GIC-Lab")
    assert BUILD_STAGING_ROOT.is_relative_to(APPROVED_MOUNT / "GIC-Lab")
    assert SEALED_ARTIFACT_ROOT.is_relative_to(APPROVED_MOUNT / "GIC-Lab")
    assert len({DOCKER_DISK_IMAGE_ROOT, BUILD_STAGING_ROOT, SEALED_ARTIFACT_ROOT}) == 3


def test_reconnect_state_machine_rejects_skip_replay_and_identity_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    external_root = tmp_path / "external"
    disk_root = external_root / "disk"
    build_root = external_root / "build"
    archive_root = external_root / "archive"
    for path in (disk_root, build_root, archive_root):
        path.mkdir(parents=True)
    monkeypatch.setattr("giclab.harness.sira_storage.APPROVED_EXTERNAL_ROOT", external_root)
    monkeypatch.setattr("giclab.harness.sira_storage.DOCKER_DISK_IMAGE_ROOT", disk_root)
    monkeypatch.setattr("giclab.harness.sira_storage.BUILD_STAGING_ROOT", build_root)
    monkeypatch.setattr("giclab.harness.sira_storage.SEALED_ARTIFACT_ROOT", archive_root)
    external_device = 101
    system_device = 202

    def resolve_device(path: Path) -> int:
        return external_device if path.is_relative_to(external_root) else system_device

    disk = DockerDiskIdentity(
        path=disk_root / "Docker.raw",
        inode=123,
        logical_bytes=456,
        birthtime_ns=789,
    )
    engine = DockerEngineIdentity(
        engine_id="engine-1",
        context="desktop-linux",
        server_os="linux",
        architecture="aarch64",
        healthy=True,
        default_internal_active=False,
    )
    qualification = ReconnectQualification(
        expected_volume_uuid=APPROVED_VOLUME_UUID,
        expected_physical_store_uuid=APPROVED_PHYSICAL_STORE_UUID,
        expected_disk_identity=disk,
        expected_engine_identity=engine,
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
            volume_observation=replace(
                _external_observation(),
                volume_uuid="00000000-0000-0000-0000-000000000000",
            ),
        )
    qualification.advance(
        ReconnectState.VOLUME_REQUALIFIED,
        volume_observation=_external_observation(),
    )
    bundle = issue_storage_guard(
        external=_external_observation(),
        system=_system_observation(),
        external_device=external_device,
        system_device=system_device,
        system_floor_bytes=1,
        purposes=(
            RootPurpose.DOCKER_DISK,
            RootPurpose.BUILD_STAGING,
            RootPurpose.SEALED_ARCHIVE,
        ),
        require_existing=True,
        issued_monotonic_ns=100,
        device_resolver=resolve_device,
    )
    qualification.advance(
        ReconnectState.PATHS_REQUALIFIED,
        storage_guard=bundle,
        now_monotonic_ns=105,
        device_resolver=resolve_device,
    )
    qualification.advance(ReconnectState.USER_ENGINE_RESTARTED, storage_guard=bundle)
    with pytest.raises(StorageContractError, match="different disk"):
        qualification.advance(
            ReconnectState.SAME_DISK_REOPENED,
            disk_identity=replace(disk, inode=999),
        )
    qualification.advance(ReconnectState.SAME_DISK_REOPENED, disk_identity=disk)
    qualification.advance(ReconnectState.ENGINE_HEALTHY, engine_identity=engine)
    qualification.advance(ReconnectState.FINAL_ENGINE_STOPPED)
    qualification.advance(ReconnectState.EVIDENCE_SEALED)
    with pytest.raises(StorageContractError, match="out of order"):
        qualification.advance(ReconnectState.EVIDENCE_SEALED)


def test_settings_evidence_is_minimized_and_placement_is_machine_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    disk_root = tmp_path / "docker-disk"
    disk_root.mkdir()
    disk_path = disk_root / "Docker.raw"
    disk_path.write_bytes(b"sparse-disk-fixture")
    monkeypatch.setattr("giclab.harness.sira_storage.DOCKER_DISK_IMAGE_ROOT", disk_root)
    settings = {
        "dataFolder": str(disk_root),
        "diskSizeMiB": 65536,
        "autoDownloadUpdates": False,
        "credentialHelper": "must-not-retain",
        "proxy": "must-not-retain",
    }
    sanitized = sanitize_docker_settings(settings)
    assert set(sanitized) == {"dataFolder", "diskSizeMiB", "autoDownloadUpdates"}
    encoded = json.dumps(sanitized, sort_keys=True, separators=(",", ":")).encode()
    observed = disk_path.lstat()
    evidence = DockerPlacementEvidence(
        configured_data_folder=disk_root,
        disk_path=disk_path,
        disk_device=observed.st_dev,
        disk_inode=observed.st_ino,
        disk_logical_bytes=observed.st_size,
        disk_allocated_bytes=observed.st_blocks * 512,
        engine_identity="engine-1",
        settings_sha256=hashlib.sha256(encoded).hexdigest(),
        default_internal_exists=False,
        default_internal_active=False,
    )
    evidence.validate(external_device=observed.st_dev, sanitized_settings=sanitized)
    with pytest.raises(StorageContractError, match="data folder"):
        evidence.validate(external_device=observed.st_dev, sanitized_settings={})
    schema_data_folder = "/Volumes/Macintosh HD - Data/GIC-Lab/t07/docker-desktop/disk-image"
    schema_settings = {
        "dataFolder": schema_data_folder,
        "diskSizeMiB": 65536,
        "autoDownloadUpdates": False,
    }
    schema_settings_hash = hashlib.sha256(
        json.dumps(schema_settings, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    placement_document = {
        "schema_version": "0.1.0",
        "volume_uuid": APPROVED_VOLUME_UUID,
        "physical_store_uuid": APPROVED_PHYSICAL_STORE_UUID,
        "configured_data_folder": schema_settings["dataFolder"],
        "settings_source": "/version-verified/source",
        "settings_key": "versionVerifiedKey",
        "sanitized_settings": schema_settings,
        "settings_sha256": schema_settings_hash,
        "disk": {
            "path": schema_data_folder + "/Docker.raw",
            "device": 44,
            "inode": 123,
            "logical_bytes": 64 * 1024**3,
            "allocated_bytes": 1024,
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
            external_device=observed.st_dev, sanitized_settings=sanitized
        )
    escaped = replace(evidence, disk_path=disk_root / ".." / "escape.raw")
    with pytest.raises(StorageContractError, match="escaped"):
        escaped.validate(external_device=observed.st_dev, sanitized_settings=sanitized)


def test_archive_copy_verifies_hashes_and_retains_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    system_root = tmp_path / "system"
    external_root = tmp_path / "external/GIC-Lab"
    evidence_root = system_root / "evidence"
    source = evidence_root / "session"
    source.mkdir(parents=True)
    (source / "nested").mkdir()
    (source / "nested/evidence.txt").write_text("bounded evidence\n")
    archive = external_root / "t07/sealed-artifacts"
    archive.mkdir(parents=True)
    monkeypatch.setattr("giclab.harness.sira_storage.APPROVED_EXTERNAL_ROOT", external_root)
    monkeypatch.setattr("giclab.harness.sira_storage.SEALED_ARTIFACT_ROOT", archive)
    monkeypatch.setattr("giclab.harness.sira_storage.B2A_EVIDENCE_ROOT", evidence_root)
    monkeypatch.setattr("giclab.harness.sira_storage.B2A_EVIDENCE_SESSION_ROOT", source)
    source_device = 101
    destination_device = 202

    def resolve_device(path: Path) -> int:
        if path == SYSTEM_DATA_MOUNT or path.is_relative_to(system_root):
            return source_device
        if path == APPROVED_MOUNT or path.is_relative_to(external_root):
            return destination_device
        raise AssertionError(f"unexpected fixture path: {path}")

    archive_id = "attempt-1-sealed"
    immutable_paths: set[Path] = set()
    seal = seal_attempt(
        source,
        attempt_id=archive_id,
        max_bytes=1024,
        close_evidence=_close_evidence(source, archive_id),
        immutable_setter=immutable_paths.add,
    )
    placement = qualify_archive_placement(
        source,
        archive_parent=archive,
        source_observation=_system_observation(),
        destination_observation=_external_observation(),
        system_floor_bytes=1,
        issued_monotonic_ns=100,
        device_resolver=resolve_device,
    )
    record_path = evidence_root / "copy-records" / f"{archive_id}.json"
    with pytest.raises(StorageContractError, match="identity is unsafe"):
        copy_sealed_attempt(
            source,
            archive_parent=archive,
            archive_id="../escape",
            copy_record_path=record_path,
            max_bytes=1024,
            placement=placement,
            source_observation=_system_observation(),
            destination_observation=_external_observation(),
            copied_at_utc="2026-08-09T16:00:00Z",
            now_monotonic_ns=105,
            device_resolver=resolve_device,
            immutability_probe=immutable_paths.__contains__,
        )
    redirected = system_root / "redirected-copy-records"
    redirected.mkdir()
    record_path.parent.symlink_to(redirected, target_is_directory=True)
    with pytest.raises(StorageContractError, match="symlink"):
        copy_sealed_attempt(
            source,
            archive_parent=archive,
            archive_id=archive_id,
            copy_record_path=record_path,
            max_bytes=1024,
            placement=placement,
            source_observation=_system_observation(),
            destination_observation=_external_observation(),
            copied_at_utc="2026-08-09T16:00:00Z",
            now_monotonic_ns=105,
            device_resolver=resolve_device,
            immutability_probe=immutable_paths.__contains__,
        )
    record_path.parent.unlink()
    assert list(redirected.iterdir()) == []
    record = copy_sealed_attempt(
        source,
        archive_parent=archive,
        archive_id=archive_id,
        copy_record_path=record_path,
        max_bytes=1024,
        placement=placement,
        source_observation=_system_observation(),
        destination_observation=_external_observation(),
        copied_at_utc="2026-08-09T16:00:00Z",
        now_monotonic_ns=105,
        device_resolver=resolve_device,
        immutability_probe=immutable_paths.__contains__,
    )
    assert seal["total_payload_bytes"] == len("bounded evidence\n")
    assert record["source_retained"] is True
    assert record["source_immutable"] is True
    assert source.exists()
    assert (archive / "attempt-1-sealed/nested/evidence.txt").read_text() == "bounded evidence\n"
    assert json.loads(record_path.read_text())["files_verified"] == 1
    assert stat.S_IMODE((archive / "attempt-1-sealed").stat().st_mode) == 0o500
    assert stat.S_IMODE((archive / "attempt-1-sealed/nested/evidence.txt").stat().st_mode) == 0o400
    assert validate_instance(record, ROOT / "schemas/sealed-artifact-copy.schema.json") == []
    for candidate in sorted(
        (archive / "attempt-1-sealed").rglob("*"),
        key=lambda item: len(item.parts),
    ):
        if candidate.is_dir():
            os.chmod(candidate, 0o700)
        else:
            os.chmod(candidate, 0o600)
    os.chmod(archive / "attempt-1-sealed", 0o700)
    os.chmod(source, 0o700)
    os.chmod(source / "nested", 0o700)
    os.chmod(source / "nested/evidence.txt", 0o600)
    os.chmod(source / "SEAL.json", 0o600)


def test_archive_rejects_symlinks_and_byte_overflow(tmp_path: Path) -> None:
    source = tmp_path / "attempt"
    source.mkdir()
    with pytest.raises(StorageContractError, match="no evidence"):
        seal_attempt(
            source,
            attempt_id="attempt",
            max_bytes=1024,
            close_evidence=_close_evidence(source, "attempt"),
        )
    (source / "escape").symlink_to(tmp_path)
    with pytest.raises(StorageContractError, match="symlink"):
        seal_attempt(
            source,
            attempt_id="attempt",
            max_bytes=1024,
            close_evidence=_close_evidence(source, "attempt"),
        )
    (source / "escape").unlink()
    (source / "large").write_bytes(b"x" * 10)
    with pytest.raises(StorageContractError, match="byte cap"):
        seal_attempt(
            source,
            attempt_id="attempt",
            max_bytes=9,
            close_evidence=_close_evidence(source, "attempt"),
        )


def test_attempt_close_evidence_requires_fresh_executable_authority(tmp_path: Path) -> None:
    source = tmp_path / "attempt"
    source.mkdir()
    (source / "evidence.txt").write_text("bounded\n")
    close = _close_evidence(source, "attempt")
    with pytest.raises(StorageContractError, match="executable authority"):
        seal_attempt(
            source,
            attempt_id="attempt",
            max_bytes=1024,
            close_evidence=replace(
                close,
                authorization_reference=B2A_AUTHORIZATION_PLACEHOLDER,
            ),
        )
    assert (
        validate_instance(
            close.document(),
            ROOT / "schemas/attempt-close-evidence.schema.json",
        )
        == []
    )


def test_standalone_seal_and_copy_is_fail_closed() -> None:
    with pytest.raises(StorageContractError, match="supervisor-owned"):
        storage_main(
            [
                "seal-and-copy",
                "--source",
                "/not/used",
                "--archive-parent",
                "/not/used",
                "--archive-id",
                "not-used",
                "--copy-record",
                "/not/used",
                "--max-bytes",
                "1",
                "--system-floor-bytes",
                "1",
            ]
        )


def test_blocked_b2a_plan_is_separate_from_b2b_and_old_plan() -> None:
    plan = _blocked_plan()
    plan.validate()
    assert plan.plan_id != SUPERSEDED_PLAN_ID
    assert "B2B" not in plan.plan_id
    assert not plan.authorized
    with pytest.raises(StorageContractError, match="V1 identity"):
        replace(plan, plan_id=SUPERSEDED_PLAN_ID).validate()
    with pytest.raises(StorageContractError, match="binding is incomplete"):
        replace(plan, implementation_commit="b" * 40).validate()
    with pytest.raises(StorageContractError, match="binding is incomplete"):
        replace(
            plan,
            steps=tuple(step for step in plan.steps if step.action_id != "repository-science-tree"),
            aggregate_automatable_calls=(plan.aggregate_automatable_calls or 0) - 1,
        ).validate()


def test_authorized_plan_requires_exact_numeric_guard_floor() -> None:
    plan = _authorized_plan()
    plan.validate()
    floor = str(plan.system_floor_inputs.resolved_floor_bytes())
    guard_index = next(
        index for index, step in enumerate(plan.steps) if step.guard_for_action is not None
    )
    guard = plan.steps[guard_index]
    assert guard.argv is not None and floor in guard.argv and "unresolved" not in guard.argv
    drifted_guard = replace(
        guard, argv=tuple("1" if value == floor else value for value in guard.argv)
    )
    drifted_steps = list(plan.steps)
    drifted_steps[guard_index] = drifted_guard
    with pytest.raises(StorageContractError, match="exact rendered action"):
        replace(plan, steps=tuple(drifted_steps)).validate()
    drifted_steps[guard_index] = replace(guard, guard_purposes=(RootPurpose.B2A_WORK,))
    with pytest.raises(StorageContractError, match="guard action metadata"):
        replace(plan, steps=tuple(drifted_steps)).validate()


def test_b2a_supervisor_blocks_unauthorized_plan_and_enforces_caps() -> None:
    with pytest.raises(StorageContractError, match="unauthorized"):
        blocked = _blocked_plan()
        B2AExecutionSupervisor(
            blocked,
            expected_plan_id=blocked.plan_id,
            expected_plan_sha256=blocked.document_sha256 or "",
            expected_authorization_reference=blocked.authorization_reference,
        )
    authorized = _authorized_plan()
    with pytest.raises(StorageContractError, match="external authority"):
        B2AExecutionSupervisor(
            authorized,
            expected_plan_id=authorized.plan_id,
            expected_plan_sha256="d" * 64,
            expected_authorization_reference=authorized.authorization_reference,
        )
    supervisor = B2AExecutionSupervisor(
        authorized,
        expected_plan_id=authorized.plan_id,
        expected_plan_sha256=authorized.document_sha256 or "",
        expected_authorization_reference=authorized.authorization_reference,
    )
    floor = authorized.system_floor_inputs.resolved_floor_bytes()
    snapshot = B2AResourceSnapshot(
        system_free_bytes=floor + 1024,
        external_free_bytes=EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES + 1024,
        active_attempt_bytes=0,
    )
    supervisor.start(snapshot, now_monotonic_ns=100)
    supervisor.begin_action("repository-status", snapshot, now_monotonic_ns=101)
    with pytest.raises(StorageContractError, match="output cap"):
        supervisor.finish_action(
            B2AActionResult(
                exit_code=0,
                stdout=b"x" * 1025,
                stderr=b"",
                downloaded_bytes=0,
                resources_after=snapshot,
            ),
            now_monotonic_ns=102,
        )


def test_b2a_supervisor_consumes_adjacent_guard_and_exact_call_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _authorized_plan()
    external_root = tmp_path / "external"
    system_root = tmp_path / "system"
    disk_root = external_root / "disk"
    build_root = external_root / "build"
    work_root = system_root / "work"
    for path in (disk_root, build_root, work_root):
        path.mkdir(parents=True)
    monkeypatch.setattr("giclab.harness.sira_storage.APPROVED_EXTERNAL_ROOT", external_root)
    monkeypatch.setattr("giclab.harness.sira_storage.DOCKER_DISK_IMAGE_ROOT", disk_root)
    monkeypatch.setattr("giclab.harness.sira_storage.BUILD_STAGING_ROOT", build_root)
    monkeypatch.setattr("giclab.harness.sira_storage.SYSTEM_GICLAB_ROOT", system_root)
    monkeypatch.setattr("giclab.harness.sira_storage.B2A_WORK_ROOT", work_root)
    external_device = 101
    system_device = 202

    def resolve_device(path: Path) -> int:
        return external_device if path.is_relative_to(external_root) else system_device

    guard = issue_storage_guard(
        external=_external_observation(),
        system=_system_observation(),
        external_device=external_device,
        system_device=system_device,
        system_floor_bytes=plan.system_floor_inputs.resolved_floor_bytes(),
        purposes=(
            RootPurpose.DOCKER_DISK,
            RootPurpose.BUILD_STAGING,
            RootPurpose.B2A_WORK,
        ),
        require_existing=True,
        issued_monotonic_ns=1_000,
        device_resolver=resolve_device,
    )
    snapshot = B2AResourceSnapshot(
        system_free_bytes=plan.system_floor_inputs.resolved_floor_bytes() + 1024,
        external_free_bytes=EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES + 1024,
        active_attempt_bytes=0,
    )
    supervisor = B2AExecutionSupervisor(
        plan,
        expected_plan_id=plan.plan_id,
        expected_plan_sha256=plan.document_sha256 or "",
        expected_authorization_reference=plan.authorization_reference,
    )
    supervisor.start(snapshot, now_monotonic_ns=1_000)
    now = 1_001
    for step in plan.steps:
        supervisor.begin_action(
            step.action_id,
            snapshot,
            now_monotonic_ns=now,
            device_resolver=resolve_device,
        )
        now += 1
        supervisor.finish_action(
            B2AActionResult(
                exit_code=0,
                stdout=(b"" if step.expected_stdout is None else step.expected_stdout.encode()),
                stderr=b"",
                downloaded_bytes=0,
                resources_after=snapshot,
            ),
            now_monotonic_ns=now,
            guard_bundle=(guard if step.guard_for_action is not None else None),
        )
        now += 1
    supervisor.complete(now_monotonic_ns=now)
    assert guard.all_consumed(
        (RootPurpose.DOCKER_DISK, RootPurpose.BUILD_STAGING, RootPurpose.B2A_WORK)
    )


def test_b2a_supervisor_mints_single_use_close_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _authorized_plan()
    floor = base.system_floor_inputs.resolved_floor_bytes()
    seal_purposes = (RootPurpose.SEALED_ARCHIVE, RootPurpose.B2A_WORK)
    seal_guard_step = B2AStep(
        action_id="guard-seal-and-copy-b2a-evidence",
        kind=B2AStepKind.AUTOMATABLE,
        timeout_seconds=10,
        output_limit_bytes=1024,
        download_limit_bytes=0,
        internal_disk_limit_bytes=0,
        external_disk_limit_bytes=0,
        argv=_guard_argv(
            "seal-and-copy-b2a-evidence",
            seal_purposes,
            require_existing=True,
            system_floor_bytes=str(floor),
        ),
        instruction=None,
        stop_on_failure=True,
        retry_limit=0,
        guard_for_action="seal-and-copy-b2a-evidence",
        guard_purposes=seal_purposes,
    )
    seal_step = B2AStep(
        action_id="seal-and-copy-b2a-evidence",
        kind=B2AStepKind.AUTOMATABLE,
        timeout_seconds=10,
        output_limit_bytes=1024,
        download_limit_bytes=0,
        internal_disk_limit_bytes=0,
        external_disk_limit_bytes=1024,
        argv=_seal_and_copy_argv(system_floor_bytes=str(floor)),
        instruction=None,
        stop_on_failure=True,
        retry_limit=0,
    )
    plan = replace(
        base,
        steps=(*base.steps, seal_guard_step, seal_step),
        aggregate_automatable_calls=(base.aggregate_automatable_calls or 0) + 2,
    )
    plan.validate()
    supervisor = B2AExecutionSupervisor(
        plan,
        expected_plan_id=plan.plan_id,
        expected_plan_sha256=plan.document_sha256 or "",
        expected_authorization_reference=plan.authorization_reference,
    )

    external_root = tmp_path / "external"
    system_root = tmp_path / "system"
    disk_root = external_root / "disk"
    build_root = external_root / "build"
    archive_root = external_root / "archive"
    work_root = system_root / "work"
    source = work_root / "evidence/session"
    for path in (disk_root, build_root, archive_root, source):
        path.mkdir(parents=True)
    (source / "evidence.txt").write_text("bounded\n")
    monkeypatch.setattr("giclab.harness.sira_storage.APPROVED_EXTERNAL_ROOT", external_root)
    monkeypatch.setattr("giclab.harness.sira_storage.DOCKER_DISK_IMAGE_ROOT", disk_root)
    monkeypatch.setattr("giclab.harness.sira_storage.BUILD_STAGING_ROOT", build_root)
    monkeypatch.setattr("giclab.harness.sira_storage.SEALED_ARTIFACT_ROOT", archive_root)
    monkeypatch.setattr("giclab.harness.sira_storage.SYSTEM_GICLAB_ROOT", system_root)
    monkeypatch.setattr("giclab.harness.sira_storage.B2A_WORK_ROOT", work_root)
    external_device = 101
    system_device = 202

    def resolve_device(path: Path) -> int:
        return external_device if path.is_relative_to(external_root) else system_device

    select_guard = issue_storage_guard(
        external=_external_observation(),
        system=_system_observation(),
        external_device=external_device,
        system_device=system_device,
        system_floor_bytes=floor,
        purposes=(
            RootPurpose.DOCKER_DISK,
            RootPurpose.BUILD_STAGING,
            RootPurpose.B2A_WORK,
        ),
        require_existing=True,
        issued_monotonic_ns=1_000,
        device_resolver=resolve_device,
    )
    seal_guard = issue_storage_guard(
        external=_external_observation(),
        system=_system_observation(),
        external_device=external_device,
        system_device=system_device,
        system_floor_bytes=floor,
        purposes=seal_purposes,
        require_existing=True,
        issued_monotonic_ns=1_000,
        device_resolver=resolve_device,
    )
    guards = {
        "guard-select-external-disk-location": select_guard,
        "guard-seal-and-copy-b2a-evidence": seal_guard,
    }
    snapshot = B2AResourceSnapshot(
        system_free_bytes=floor + 1024,
        external_free_bytes=EXTERNAL_PRE_B2A_FREE_FLOOR_BYTES + 1024,
        active_attempt_bytes=0,
    )
    supervisor.start(snapshot, now_monotonic_ns=1_000)
    now = 1_001
    for step in plan.steps[:-1]:
        supervisor.begin_action(
            step.action_id,
            snapshot,
            now_monotonic_ns=now,
            device_resolver=resolve_device,
        )
        now += 1
        supervisor.finish_action(
            B2AActionResult(
                exit_code=0,
                stdout=(b"" if step.expected_stdout is None else step.expected_stdout.encode()),
                stderr=b"",
                downloaded_bytes=0,
                resources_after=snapshot,
            ),
            now_monotonic_ns=now,
            guard_bundle=guards.get(step.action_id),
        )
        now += 1
    with pytest.raises(StorageContractError, match="open writers"):
        supervisor.prepare_seal(
            source=source,
            attempt_id="attempt-close",
            closed_at_utc="2026-08-09T16:00:00Z",
            now_monotonic_ns=now,
            writer_probe=lambda _: 1,
        )
    close = supervisor.prepare_seal(
        source=source,
        attempt_id="attempt-close",
        closed_at_utc="2026-08-09T16:00:00Z",
        now_monotonic_ns=now,
        writer_probe=lambda _: 0,
    )
    supervisor.begin_action(
        seal_step.action_id,
        snapshot,
        now_monotonic_ns=now + 1,
        device_resolver=resolve_device,
    )
    immutable_paths: set[Path] = set()
    seal_attempt(
        source,
        attempt_id="attempt-close",
        max_bytes=1024,
        close_evidence=close,
        immutable_setter=immutable_paths.add,
    )
    supervisor.finish_action(
        B2AActionResult(
            exit_code=0,
            stdout=b"",
            stderr=b"",
            downloaded_bytes=0,
            resources_after=snapshot,
        ),
        now_monotonic_ns=now + 2,
        close_evidence=close,
    )
    supervisor.complete(now_monotonic_ns=now + 3)
    with pytest.raises(StorageContractError, match="already consumed"):
        close.validate(source=source, attempt_id="attempt-close")
    os.chmod(source, 0o700)
    os.chmod(source / "evidence.txt", 0o600)
    os.chmod(source / "SEAL.json", 0o600)


def test_committed_b2a_plan_has_exact_hash_and_remains_blocked() -> None:
    path = ROOT / "containers/sira-smoke/gate-b2a-install-storage-binding-plan.json"
    digest = "c7f7079ce92a0d5596498716a63153e3db7ff155abe287d7a51e0a4b7239c8ea"
    plan = load_b2a_plan(path, expected_sha256=digest)
    assert plan.implementation_commit == "6d35887a5a75fe499650aed346aa7a7435207ed9"
    assert not plan.authorized
    assert plan.system_incremental_disk_bytes is None


def test_b2b_stub_contains_requirements_but_no_executable_authority() -> None:
    stub = (ROOT / "docs/harness/T07_GATE_B2B_REQUIREMENTS_STUB.md").read_text()
    assert "Required B2a outputs" in stub
    for prohibited in (
        "PLAN-T07-GATE-B2B",
        "AUTH-T07-GATE-B2B",
        '"argv"',
        "/usr/bin/",
        "/Applications/",
    ):
        assert prohibited not in stub


def test_b2a_packet_is_bound_and_explicitly_authorizes_nothing() -> None:
    packet = (ROOT / "docs/harness/T07_GATE_B2A_INSTALL_AUTHORIZATION_PACKET.md").read_text()
    assert "this packet and its plan authorize nothing" in packet
    assert "c7f7079ce92a0d5596498716a63153e3db7ff155abe287d7a51e0a4b7239c8ea" in packet
    assert "6d35887a5a75fe499650aed346aa7a7435207ed9" in packet
    assert "There is no truthful ready-to-copy **installation authorization**" in packet


def test_official_metadata_verifier_binds_selected_item_not_channel_link(
    tmp_path: Path,
) -> None:
    appcast = tmp_path / "appcast.xml"
    appcast.write_text(
        """<rss xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
<channel><link>https://desktop.docker.com/mac/main/arm64/older/Docker.dmg</link>
<item><title>Version 4.85.0 (235549)</title>
<sparkle:minimumSystemVersion>14.0.0</sparkle:minimumSystemVersion>
<enclosure url="https://desktop.docker.com/mac/main/arm64/235549/Docker.dmg"
 sparkle:version="235549" sparkle:shortVersionString="4.85.0"
 length="573592444" type="application/octet-stream"/></item></channel></rss>"""
    )
    checksums = tmp_path / "checksums.txt"
    checksums.write_text(
        "84b1224c93456fe261955ebc91f3cd88ce19778ffdb6d0a0d423ce37246f7c2b *Docker.dmg\n"
    )
    evidence = verify_official_docker_metadata(appcast, checksums)
    assert evidence["build"] == "235549"
    assert evidence["bytes"] == 573_592_444
    checksums.write_text("0" * 64 + " *Docker.dmg\n")
    with pytest.raises(StorageContractError, match="checksum"):
        verify_official_docker_metadata(appcast, checksums)


def test_dmg_verifier_requires_exact_bytes_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dmg = tmp_path / "Docker.dmg"
    dmg.write_bytes(b"selected immutable artifact")
    monkeypatch.setattr("giclab.harness.sira_storage.DOCKER_DMG_BYTES", dmg.stat().st_size)
    monkeypatch.setattr(
        "giclab.harness.sira_storage.DOCKER_DMG_SHA256",
        hashlib.sha256(dmg.read_bytes()).hexdigest(),
    )
    assert verify_docker_dmg(dmg)["bytes"] == dmg.stat().st_size
    dmg.write_bytes(b"drift")
    with pytest.raises(StorageContractError):
        verify_docker_dmg(dmg)


@pytest.mark.parametrize(
    "argv",
    [
        ("/Applications/Docker.app/Contents/Resources/bin/docker", "pull", "image"),
        ("/Applications/Docker.app/Contents/Resources/bin/docker", "build", "."),
        ("/Applications/Docker.app/Contents/Resources/bin/docker", "create", "image"),
        ("/usr/bin/python3", "-m", "playwright", "install", "chromium"),
        ("/usr/bin/python3", "-m", "giclab", "--secret-file", "/tmp/value"),
        ("/bin/sh", "-c", "true"),
        ("/usr/sbin/diskutil", "eraseDisk", "APFS", "bad", "disk99"),
        ("/usr/bin/git", "clean", "-fdx"),
        ("/usr/bin/python3", "-c", "print('unexpected')"),
        (
            "/usr/bin/curl",
            "--output",
            "/tmp/unbounded",
            "https://example.com/unapproved",
        ),
        ("/Applications/Docker.app/Contents/Resources/bin/docker", "system", "dial-stdio"),
        ("/bin/mkdir", "-m", "0700", "/tmp/outside-approved-roots"),
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
