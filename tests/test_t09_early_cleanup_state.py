from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from giclab.harness.t09_cleanup_state import (
    CleanupActionResult,
    CleanupLifecycleStage,
    CleanupTarget,
    CleanupTargetKind,
    CleanupTargetState,
    EarlyCleanupJournal,
    EarlyCleanupStateError,
    TerminalCleanupDisposition,
    cleanup_locator_identity,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/t09-early-cleanup-state.schema.json"
PACKAGE_COMMIT = "a" * 40
PLAN_SHA256 = "b" * 64
PROVIDER_IDENTITY = "c" * 64
FIREWALL_IDENTITY = "d" * 64


class IncrementingClock:
    def __init__(self) -> None:
        self.value = 1_000.0

    def __call__(self) -> float:
        self.value += 1.0
        return self.value


def initialize_journal(tmp_path: Path, clock: IncrementingClock) -> EarlyCleanupJournal:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    return EarlyCleanupJournal.initialize(
        private_root / "preflight-cleanup-state",
        plan_id="PLAN-EXP0001-PILOT-V10",
        host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0003",
        package_commit=PACKAGE_COMMIT,
        plan_sha256=PLAN_SHA256,
        provider_instance_id="instance-owned-0003",
        provider_instance_identity_sha256=PROVIDER_IDENTITY,
        provider_started_at_epoch=999.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256=FIREWALL_IDENTITY,
        clock=clock,
    )


def successful_cleanup(target: CleanupTarget) -> CleanupActionResult:
    result = {
        CleanupTargetKind.PROVIDER_INSTANCE: CleanupTargetState.TERMINAL,
        CleanupTargetKind.FIREWALL_RESTORATION: CleanupTargetState.RESTORED,
        CleanupTargetKind.OWNED_RULESET: CleanupTargetState.ABSENT,
        CleanupTargetKind.TEMPORARY_LOCAL_CREDENTIAL: CleanupTargetState.REMOVED,
        CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL: CleanupTargetState.REMOVED,
        CleanupTargetKind.OWNED_CONTAINER: CleanupTargetState.ABSENT,
    }[target.kind]
    return CleanupActionResult(result, f"{target.kind.value}-verified")


@pytest.mark.parametrize(
    ("failure_stage", "register_secret"),
    [
        (None, False),  # failure before package transition
        (CleanupLifecycleStage.PACKAGE_TRANSITION, False),  # failure during transition
        (CleanupLifecycleStage.IMAGE_TRANSFER, False),  # failure before image import
        (CleanupLifecycleStage.SECRET_MATERIALIZATION, True),
        (CleanupLifecycleStage.BROWSER_STARTUP, False),  # before campaign-state initialization
    ],
)
def test_cleanup_is_complete_before_optional_state_exists(
    tmp_path: Path,
    failure_stage: CleanupLifecycleStage | None,
    register_secret: bool,
) -> None:
    clock = IncrementingClock()
    journal = initialize_journal(tmp_path, clock)
    if failure_stage is not None:
        journal.advance_lifecycle(failure_stage, clock=clock)
    if register_secret:
        locator = "/tmp/giclab-v10-openai-secret-upload"
        journal.register_target(
            target_id="temporary-local-secret-0001",
            kind=CleanupTargetKind.TEMPORARY_LOCAL_CREDENTIAL,
            locator=locator,
            ownership_sha256=cleanup_locator_identity(
                CleanupTargetKind.TEMPORARY_LOCAL_CREDENTIAL, locator
            ),
            public_alias="temporary-local-secret/0001",
            clock=clock,
        )

    private_root = journal.root.parent
    assert not (private_root / "pilot-state.json").exists()
    assert not (private_root / "campaign-state.json").exists()
    assert not (private_root / "finalizer-state.json").exists()
    closed = journal.cleanup(successful_cleanup, clock=clock)
    receipt_path = journal.write_basic_closeout_receipt(
        private_root / "EARLY_CLEANUP_CLOSEOUT.json"
    )

    assert closed.terminal_cleanup_disposition is TerminalCleanupDisposition.COMPLETE
    assert closed.lifecycle_stage is CleanupLifecycleStage.CLEANUP_FINISHED
    assert all(
        target.state
        in {
            CleanupTargetState.ABSENT,
            CleanupTargetState.TERMINAL,
            CleanupTargetState.RESTORED,
            CleanupTargetState.REMOVED,
        }
        for target in closed.targets
    )
    receipt = json.loads(receipt_path.read_text())
    assert receipt["pilot_state_used"] is False
    assert receipt["campaign_state_used"] is False
    assert receipt["finalizer_state_used"] is False
    assert "locator" not in receipt_path.read_text()


def test_cleanup_handles_absent_resources_and_repeated_invocation(tmp_path: Path) -> None:
    clock = IncrementingClock()
    journal = initialize_journal(tmp_path, clock)
    for target_id, kind, locator, alias in (
        (
            "owned-ruleset-0001",
            CleanupTargetKind.OWNED_RULESET,
            "ruleset-owned-0001",
            "owned-ruleset/0001",
        ),
        (
            "owned-container-0001",
            CleanupTargetKind.OWNED_CONTAINER,
            "container-owned-0001",
            "owned-container/0001",
        ),
    ):
        journal.register_target(
            target_id=target_id,
            kind=kind,
            locator=locator,
            ownership_sha256=cleanup_locator_identity(kind, locator),
            public_alias=alias,
            clock=clock,
        )

    calls: list[str] = []

    def absent_cleanup(target: CleanupTarget) -> CleanupActionResult:
        calls.append(target.target_id)
        return successful_cleanup(target)

    first = journal.cleanup(absent_cleanup, clock=clock)
    first_calls = list(calls)
    second = journal.cleanup(absent_cleanup, clock=clock)

    assert first.terminal_cleanup_disposition is TerminalCleanupDisposition.COMPLETE
    assert second == first
    assert calls == first_calls
    assert {target.target_id: target.state for target in second.targets} == {
        "provider-instance": CleanupTargetState.TERMINAL,
        "firewall-restoration": CleanupTargetState.RESTORED,
        "owned-ruleset-0001": CleanupTargetState.ABSENT,
        "owned-container-0001": CleanupTargetState.ABSENT,
    }


def test_partial_cleanup_is_durable_and_retry_only_attempts_unfinished_target(
    tmp_path: Path,
) -> None:
    clock = IncrementingClock()
    journal = initialize_journal(tmp_path, clock)
    calls: list[str] = []

    def partial_action(target: CleanupTarget) -> CleanupActionResult:
        calls.append(target.target_id)
        if target.kind is CleanupTargetKind.PROVIDER_INSTANCE:
            raise RuntimeError("fake provider termination failed")
        return successful_cleanup(target)

    partial = journal.cleanup(partial_action, clock=clock)
    partial_receipt = journal.write_basic_closeout_receipt(
        journal.root.parent / f"EARLY_CLEANUP_CLOSEOUT-{partial.sequence:08d}.json"
    )
    loaded = EarlyCleanupJournal(journal.root).load()

    assert loaded == partial
    assert partial.terminal_cleanup_disposition is TerminalCleanupDisposition.PARTIAL
    assert {target.target_id: target.state for target in partial.targets} == {
        "provider-instance": CleanupTargetState.FAILED,
        "firewall-restoration": CleanupTargetState.RESTORED,
    }
    assert json.loads(partial_receipt.read_text())["terminal_cleanup_disposition"] == "partial"

    calls.clear()
    complete = journal.cleanup(successful_cleanup, clock=clock)
    assert calls == []  # the replacement action does not share the first call recorder
    assert complete.terminal_cleanup_disposition is TerminalCleanupDisposition.COMPLETE
    assert complete.cleanup_attempts[-1].target_id == "provider-instance"
    assert len(complete.cleanup_attempts) == len(partial.cleanup_attempts) + 1


def test_journal_versions_validate_against_schema_and_reject_secret_canaries(
    tmp_path: Path,
) -> None:
    clock = IncrementingClock()
    journal = initialize_journal(tmp_path, clock)
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    journal.advance_lifecycle(CleanupLifecycleStage.PACKAGE_TRANSITION, clock=clock)
    for path in sorted(journal.versions.glob("*.json")):
        validator.validate(json.loads(path.read_text()))

    with pytest.raises(EarlyCleanupStateError, match="contains a secret"):
        journal.register_target(
            target_id="temporary-remote-secret-0001",
            kind=CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL,
            locator="s" + "k-" + "public-test-canary-value",
            ownership_sha256="e" * 64,
            public_alias="temporary-remote-secret/0001",
            clock=clock,
        )


def test_cleanup_attempt_continues_after_failure_and_retains_exact_provider(tmp_path: Path) -> None:
    clock = IncrementingClock()
    journal = initialize_journal(tmp_path, clock)
    observed: list[str] = []

    def action(target: CleanupTarget) -> CleanupActionResult:
        observed.append(target.target_id)
        if target.kind is CleanupTargetKind.FIREWALL_RESTORATION:
            raise OSError("fake firewall observation failure")
        return successful_cleanup(target)

    partial = journal.cleanup(action, clock=clock)

    assert observed == ["provider-instance", "firewall-restoration"]
    assert partial.provider_instance_id == "instance-owned-0003"
    assert partial.provider_instance_identity_sha256 == PROVIDER_IDENTITY
    assert partial.empirical_entry_status.value == "not-entered"
    assert partial.cleanup_attempts[-1].result is CleanupTargetState.FAILED


def test_uncreated_journal_has_typed_absence_semantics(tmp_path: Path) -> None:
    journal = EarlyCleanupJournal(tmp_path / "never-created")

    with pytest.raises(EarlyCleanupStateError, match="journal is missing"):
        journal.load()
    with pytest.raises(EarlyCleanupStateError, match="journal is missing"):
        journal.latest_version_sha256()


def test_operational_lifecycle_is_monotonic_across_preflight_and_conditions(
    tmp_path: Path,
) -> None:
    clock = IncrementingClock()
    journal = initialize_journal(tmp_path, clock)
    operational_stages = (
        CleanupLifecycleStage.PACKAGE_TRANSITION,
        CleanupLifecycleStage.SOURCE_STAGING,
        CleanupLifecycleStage.SECRET_MATERIALIZATION,
        CleanupLifecycleStage.ARTIFACT_ROOT_MUTATION,
        CleanupLifecycleStage.CAMPAIGN_INITIALIZATION,
        CleanupLifecycleStage.IMAGE_TRANSFER,
        CleanupLifecycleStage.IMAGE_LOAD_OR_BUILD,
        CleanupLifecycleStage.CONTAINER_CREATION,
        CleanupLifecycleStage.BROWSER_STARTUP,
        CleanupLifecycleStage.EMPIRICAL_ENTRY,
    )
    observed_stages: list[CleanupLifecycleStage] = []
    for stage in operational_stages[:7]:
        observed_stages.append(
            journal.advance_lifecycle_at_least(stage, clock=clock).lifecycle_stage
        )

    for index, role in enumerate(("core-preflight", "browser-preflight"), start=1):
        container_id = f"{index:064x}"
        journal.register_target(
            target_id=f"owned-container-{container_id}",
            kind=CleanupTargetKind.OWNED_CONTAINER,
            locator=container_id,
            ownership_sha256=cleanup_locator_identity(
                CleanupTargetKind.OWNED_CONTAINER, container_id
            ),
            public_alias=f"owned-container/{role}/giclab-t09-pilot-v10-{role}",
            clock=clock,
        )
        stage = (
            CleanupLifecycleStage.CONTAINER_CREATION
            if index == 1
            else CleanupLifecycleStage.BROWSER_STARTUP
        )
        observed_stages.append(
            journal.advance_lifecycle_at_least(stage, clock=clock).lifecycle_stage
        )
        journal.record_result(
            target_id=f"owned-container-{container_id}",
            result=CleanupTargetState.REMOVED,
            detail_code=f"{role}-removed",
            during_cleanup=False,
            clock=clock,
        )

    observed_stages.append(
        journal.advance_lifecycle_at_least(
            CleanupLifecycleStage.EMPIRICAL_ENTRY, clock=clock
        ).lifecycle_stage
    )
    for index in (3, 4):
        container_id = f"{index:064x}"
        journal.register_target(
            target_id=f"owned-container-{container_id}",
            kind=CleanupTargetKind.OWNED_CONTAINER,
            locator=container_id,
            ownership_sha256=cleanup_locator_identity(
                CleanupTargetKind.OWNED_CONTAINER, container_id
            ),
            public_alias=f"owned-container/condition/giclab-t09-pilot-v10-{index}",
            clock=clock,
        )
        journal.advance_lifecycle_at_least(CleanupLifecycleStage.CONTAINER_CREATION, clock=clock)
        journal.record_result(
            target_id=f"owned-container-{container_id}",
            result=CleanupTargetState.REMOVED,
            detail_code="condition-container-removed",
            during_cleanup=False,
            clock=clock,
        )

    final = journal.load()
    assert observed_stages == list(operational_stages)
    assert final.lifecycle_stage is CleanupLifecycleStage.EMPIRICAL_ENTRY
    assert final.empirical_entry_status.value == "entered"
    assert all(
        target.state is CleanupTargetState.REMOVED
        for target in final.targets
        if target.kind is CleanupTargetKind.OWNED_CONTAINER
    )


def test_exact_failed_target_reregistration_is_idempotent(tmp_path: Path) -> None:
    clock = IncrementingClock()
    journal = initialize_journal(tmp_path, clock)
    container_id = "1" * 64
    registration = {
        "target_id": f"owned-container-{container_id}",
        "kind": CleanupTargetKind.OWNED_CONTAINER,
        "locator": container_id,
        "ownership_sha256": cleanup_locator_identity(
            CleanupTargetKind.OWNED_CONTAINER, container_id
        ),
        "public_alias": "owned-container/condition/giclab-t09-pilot-v10-01",
    }
    journal.register_target(**registration, clock=clock)
    failed = journal.record_result(
        target_id=f"owned-container-{container_id}",
        result=CleanupTargetState.FAILED,
        detail_code="fake-removal-failure",
        clock=clock,
    )

    assert journal.register_target(**registration, clock=clock) == failed
    with pytest.raises(EarlyCleanupStateError, match="rebound"):
        journal.register_target(
            **{**registration, "public_alias": "owned-container/condition/drifted"},
            clock=clock,
        )


def test_remote_continuation_import_preserves_one_exact_hash_chain(tmp_path: Path) -> None:
    clock = IncrementingClock()
    local = initialize_journal(tmp_path, clock)
    remote_root = tmp_path / "remote-cleanup-state"
    shutil.copytree(local.root, remote_root)
    remote = EarlyCleanupJournal(remote_root)
    remote.advance_lifecycle_at_least(CleanupLifecycleStage.SOURCE_STAGING, clock=clock)
    remote_credential = "/tmp/giclab-v10-remote-secret"
    remote.register_target(
        target_id="temporary-remote-secret",
        kind=CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL,
        locator=remote_credential,
        ownership_sha256=cleanup_locator_identity(
            CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL, remote_credential
        ),
        public_alias="temporary-remote-secret",
        clock=clock,
    )
    remote.record_result(
        target_id="temporary-remote-secret",
        result=CleanupTargetState.ABSENT,
        detail_code="temporary-remote-secret-already-absent",
        clock=clock,
    )

    imported = local.import_continuation(remote)

    assert imported == remote.load()
    assert local.latest_version_sha256() == remote.latest_version_sha256()
    assert [path.read_bytes() for path in local._version_paths()] == [
        path.read_bytes() for path in remote._version_paths()
    ]
