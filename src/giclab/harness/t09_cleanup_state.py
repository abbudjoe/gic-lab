"""Durable exact-owner cleanup authority for T09 provider transitions.

The journal is created as soon as a provider returns one exact instance ID.  It
does not depend on pilot, campaign, attempt, image, or finalizer state.  Every
change is a hash-chained, exclusive, fsync'd version so an interrupted cleanup
cannot erase an earlier target or result.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Final, cast

from giclab.harness.campaign_output import (
    CampaignWriterRole,
    admit_campaign_write,
    observe_campaign_write,
    verify_campaign_write,
)

EARLY_CLEANUP_SCHEMA_VERSION: Final = "1.0.0"
EARLY_CLEANUP_RECEIPT_SCHEMA_VERSION: Final = "1.0.0"
CLEANUP_EXPORT_HANDOFF_SCHEMA_VERSION: Final = "1.0.0"

_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SAFE_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_VERSION_NAME = re.compile(r"^(?P<sequence>[0-9]{8})\.json$")
_SECRET_CANARY = re.compile(r"(?:sk-[A-Za-z0-9_-]{16,}|(?:api[_-]?key|token|password)=)", re.I)


class EarlyCleanupStateError(RuntimeError):
    """The durable cleanup authority is missing, contradictory, or unsafe."""


class CleanupLifecycleStage(StrEnum):
    PROVIDER_IDENTITY_ACQUIRED = "provider-identity-acquired"
    PACKAGE_TRANSITION = "package-transition"
    SOURCE_STAGING = "source-staging"
    SECRET_MATERIALIZATION = "secret-materialization"
    ARTIFACT_ROOT_MUTATION = "artifact-root-mutation"
    CAMPAIGN_INITIALIZATION = "campaign-initialization"
    IMAGE_TRANSFER = "image-transfer"
    IMAGE_LOAD_OR_BUILD = "image-load-or-build"
    CONTAINER_CREATION = "container-creation"
    BROWSER_STARTUP = "browser-startup"
    EMPIRICAL_ENTRY = "empirical-entry"
    CLEANUP_IN_PROGRESS = "cleanup-in-progress"
    CLEANUP_FINISHED = "cleanup-finished"


_STAGE_ORDER: Final = {stage: index for index, stage in enumerate(CleanupLifecycleStage)}


class EmpiricalEntryStatus(StrEnum):
    NOT_ENTERED = "not-entered"
    ENTERED = "entered"


class CleanupExportLifecyclePhase(StrEnum):
    """Evidence-derived export obligations at cleanup time."""

    PREFREEZE_ZERO_ATTEMPT = "prefreeze-zero-attempt"
    POSTFREEZE_ZERO_ATTEMPT = "postfreeze-zero-attempt"
    EMPIRICAL_PREFIX = "empirical-prefix"


@dataclass(frozen=True, slots=True)
class CleanupExportPhaseEvidence:
    """Typed projection of the durable facts that select cleanup export policy."""

    lifecycle_phase: CleanupExportLifecyclePhase
    provider_contract_version: str
    plan_id: str
    host_run_id: str
    frozen_manifest_state: str
    frozen_manifest_sha256: str | None
    empirical_attempt_count: int
    raw_attempt_complete_count: int
    attempt_completed_count: int
    condition_start_reservation_count: int
    condition_start_intent_count: int
    attempt_specific_state_count: int
    postfreeze_entry_receipt_count: int
    required_export_acknowledgement_count: int
    observed_export_acknowledgement_count: int
    # Historical field name retained for schema compatibility.  This is the
    # count backed by durable acknowledgement members, never the transient
    # global-cleanup-intent chronology supplied by a resume caller.
    retained_export_chronology_count: int

    def __post_init__(self) -> None:
        if (
            _SAFE_ID.fullmatch(self.provider_contract_version) is None
            or _SAFE_ID.fullmatch(self.plan_id) is None
            or _SAFE_ID.fullmatch(self.host_run_id) is None
        ):
            raise EarlyCleanupStateError("cleanup export phase identity is malformed")
        counts = (
            self.empirical_attempt_count,
            self.raw_attempt_complete_count,
            self.attempt_completed_count,
            self.condition_start_reservation_count,
            self.condition_start_intent_count,
            self.attempt_specific_state_count,
            self.postfreeze_entry_receipt_count,
            self.required_export_acknowledgement_count,
            self.observed_export_acknowledgement_count,
            self.retained_export_chronology_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise EarlyCleanupStateError("cleanup export phase counts are malformed")
        manifest_is_published = self.frozen_manifest_state == "published-valid"
        if manifest_is_published != (
            isinstance(self.frozen_manifest_sha256, str)
            and _HEX64.fullmatch(self.frozen_manifest_sha256) is not None
        ):
            raise EarlyCleanupStateError("cleanup export manifest state is contradictory")
        if self.observed_export_acknowledgement_count > self.required_export_acknowledgement_count:
            raise EarlyCleanupStateError("cleanup export acknowledgement count is overbroad")
        if self.retained_export_chronology_count != self.observed_export_acknowledgement_count:
            raise EarlyCleanupStateError(
                "cleanup export chronology count lacks durable acknowledgement evidence"
            )
        if self.lifecycle_phase is CleanupExportLifecyclePhase.PREFREEZE_ZERO_ATTEMPT:
            if (
                self.frozen_manifest_state != "not-published-expected"
                or self.frozen_manifest_sha256 is not None
                or any(counts)
            ):
                raise EarlyCleanupStateError("pre-freeze zero-attempt evidence is contradictory")
        elif self.lifecycle_phase is CleanupExportLifecyclePhase.POSTFREEZE_ZERO_ATTEMPT:
            if (
                not manifest_is_published
                or self.postfreeze_entry_receipt_count != 1
                or any(
                    (
                        self.empirical_attempt_count,
                        self.raw_attempt_complete_count,
                        self.attempt_completed_count,
                        self.condition_start_reservation_count,
                        self.condition_start_intent_count,
                        self.attempt_specific_state_count,
                        self.required_export_acknowledgement_count,
                        self.observed_export_acknowledgement_count,
                        self.retained_export_chronology_count,
                    )
                )
            ):
                raise EarlyCleanupStateError("post-freeze zero-attempt evidence is contradictory")
        elif self.lifecycle_phase is CleanupExportLifecyclePhase.EMPIRICAL_PREFIX:
            if not manifest_is_published or self.postfreeze_entry_receipt_count != 1:
                raise EarlyCleanupStateError("empirical cleanup lacks a published frozen manifest")
        else:  # pragma: no cover - StrEnum construction excludes this branch.
            raise EarlyCleanupStateError("cleanup export lifecycle phase is unknown")

    def to_document(self) -> dict[str, object]:
        return {
            "lifecycle_phase": self.lifecycle_phase.value,
            "provider_contract_version": self.provider_contract_version,
            "plan_id": self.plan_id,
            "host_run_id": self.host_run_id,
            "frozen_manifest_state": self.frozen_manifest_state,
            "frozen_manifest_sha256": self.frozen_manifest_sha256,
            "empirical_attempt_count": self.empirical_attempt_count,
            "raw_attempt_complete_count": self.raw_attempt_complete_count,
            "attempt_completed_count": self.attempt_completed_count,
            "condition_start_reservation_count": self.condition_start_reservation_count,
            "condition_start_intent_count": self.condition_start_intent_count,
            "attempt_specific_state_count": self.attempt_specific_state_count,
            "postfreeze_entry_receipt_count": self.postfreeze_entry_receipt_count,
            "required_export_acknowledgement_count": (self.required_export_acknowledgement_count),
            "observed_export_acknowledgement_count": (self.observed_export_acknowledgement_count),
            "retained_export_chronology_count": self.retained_export_chronology_count,
        }


class CleanupTargetKind(StrEnum):
    PROVIDER_INSTANCE = "provider-instance"
    FIREWALL_RESTORATION = "firewall-restoration"
    OWNED_RULESET = "owned-ruleset"
    TEMPORARY_LOCAL_CREDENTIAL = "temporary-local-secret"
    TEMPORARY_REMOTE_CREDENTIAL = "temporary-remote-secret"
    OWNED_CONTAINER = "owned-container"
    SOURCE_PACKAGE_ARCHIVE = "source-package-archive"


class CleanupTargetState(StrEnum):
    OWNED = "owned"
    FAILED = "failed"
    ABSENT = "absent"
    TERMINAL = "terminal"
    RESTORED = "restored"
    REMOVED = "removed"


class TerminalCleanupDisposition(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETE = "complete"


_TERMINAL_TARGET_STATES: Final = frozenset(
    {
        CleanupTargetState.ABSENT,
        CleanupTargetState.TERMINAL,
        CleanupTargetState.RESTORED,
        CleanupTargetState.REMOVED,
    }
)

_ALLOWED_TERMINAL_STATES: Final = {
    CleanupTargetKind.PROVIDER_INSTANCE: frozenset(
        {CleanupTargetState.ABSENT, CleanupTargetState.TERMINAL}
    ),
    CleanupTargetKind.FIREWALL_RESTORATION: frozenset({CleanupTargetState.RESTORED}),
    CleanupTargetKind.OWNED_RULESET: frozenset(
        {CleanupTargetState.ABSENT, CleanupTargetState.REMOVED}
    ),
    CleanupTargetKind.TEMPORARY_LOCAL_CREDENTIAL: frozenset(
        {CleanupTargetState.ABSENT, CleanupTargetState.REMOVED}
    ),
    CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL: frozenset(
        {CleanupTargetState.ABSENT, CleanupTargetState.REMOVED}
    ),
    CleanupTargetKind.OWNED_CONTAINER: frozenset(
        {CleanupTargetState.ABSENT, CleanupTargetState.REMOVED}
    ),
    CleanupTargetKind.SOURCE_PACKAGE_ARCHIVE: frozenset(
        {CleanupTargetState.ABSENT, CleanupTargetState.REMOVED}
    ),
}


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def cleanup_locator_identity(kind: CleanupTargetKind, locator: str) -> str:
    """Return a domain-separated identity for one exact cleanup locator."""

    _validate_locator(locator, kind=kind)
    return _sha256_bytes(f"giclab-t09-cleanup-target-v1\0{kind}\0{locator}".encode())


def _validate_locator(value: str, *, kind: CleanupTargetKind | None = None) -> None:
    if (
        not value
        or len(value.encode()) > 4_096
        or "\x00" in value
        or "\n" in value
        or "\r" in value
        or _SECRET_CANARY.search(value) is not None
    ):
        raise EarlyCleanupStateError("cleanup locator is empty, unsafe, or contains a secret")
    if (
        kind
        in {
            CleanupTargetKind.PROVIDER_INSTANCE,
            CleanupTargetKind.OWNED_RULESET,
            CleanupTargetKind.OWNED_CONTAINER,
        }
        and _SAFE_ID.fullmatch(value) is None
    ):
        raise EarlyCleanupStateError("resource cleanup locator is not one exact safe ID")
    if kind is CleanupTargetKind.FIREWALL_RESTORATION and value != (
        "entry-source/provider-firewall-baseline"
    ):
        raise EarlyCleanupStateError("firewall cleanup locator is not the exact baseline alias")
    if kind is CleanupTargetKind.TEMPORARY_LOCAL_CREDENTIAL:
        # Current journals bind this target as one root-relative role so the
        # held private-root descriptor, rather than an unstable absolute
        # pathname, owns cleanup. Historical absolute locators remain readable.
        path = Path(value)
        if value != "openai-secret-upload" and (
            not path.is_absolute() or ".." in path.parts or path == Path(path.anchor)
        ):
            raise EarlyCleanupStateError("temporary-secret cleanup locator is not an exact path")
    if kind in {
        CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL,
        CleanupTargetKind.SOURCE_PACKAGE_ARCHIVE,
    }:
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts or path == Path(path.anchor):
            raise EarlyCleanupStateError("temporary-secret cleanup locator is not an exact path")


def _require_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EarlyCleanupStateError(f"{label} must be a nonempty string")
    return value


def _require_sha256(value: object, *, label: str) -> str:
    result = _require_string(value, label=label)
    if _HEX64.fullmatch(result) is None:
        raise EarlyCleanupStateError(f"{label} must be a lowercase SHA-256")
    return result


def _require_number(value: object, *, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise EarlyCleanupStateError(f"{label} must be a finite nonnegative number")
    return float(value)


def _require_integer(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise EarlyCleanupStateError(f"{label} must be a nonnegative integer")
    return value


def _require_mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise EarlyCleanupStateError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _require_list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise EarlyCleanupStateError(f"{label} must be an array")
    return cast(list[object], value)


@dataclass(frozen=True)
class CleanupTarget:
    target_id: str
    kind: CleanupTargetKind
    locator: str
    ownership_sha256: str
    public_alias: str
    state: CleanupTargetState
    registered_at_epoch: float
    last_attempt_id: str | None = None

    def __post_init__(self) -> None:
        if _SAFE_ID.fullmatch(self.target_id) is None:
            raise EarlyCleanupStateError("cleanup target ID is unsafe")
        _validate_locator(self.locator, kind=self.kind)
        if _HEX64.fullmatch(self.ownership_sha256) is None:
            raise EarlyCleanupStateError("cleanup target ownership identity is malformed")
        if _SAFE_ALIAS.fullmatch(self.public_alias) is None or self.public_alias.startswith("/"):
            raise EarlyCleanupStateError("cleanup target public alias is unsafe")
        _require_number(self.registered_at_epoch, label="target registration time")
        if self.last_attempt_id is not None and _SAFE_ID.fullmatch(self.last_attempt_id) is None:
            raise EarlyCleanupStateError("cleanup target attempt ID is unsafe")
        if (
            self.state in _TERMINAL_TARGET_STATES
            and self.state not in _ALLOWED_TERMINAL_STATES[self.kind]
        ):
            raise EarlyCleanupStateError("cleanup target terminal state contradicts its kind")

    def to_document(self) -> dict[str, object]:
        return {
            "target_id": self.target_id,
            "kind": self.kind.value,
            "locator": self.locator,
            "ownership_sha256": self.ownership_sha256,
            "public_alias": self.public_alias,
            "state": self.state.value,
            "registered_at_epoch": self.registered_at_epoch,
            "last_attempt_id": self.last_attempt_id,
        }

    @classmethod
    def from_document(cls, value: object) -> CleanupTarget:
        document = _require_mapping(value, label="cleanup target")
        if set(document) != {
            "target_id",
            "kind",
            "locator",
            "ownership_sha256",
            "public_alias",
            "state",
            "registered_at_epoch",
            "last_attempt_id",
        }:
            raise EarlyCleanupStateError("cleanup target fields drifted")
        last_attempt = document["last_attempt_id"]
        if last_attempt is not None:
            last_attempt = _require_string(last_attempt, label="last cleanup attempt ID")
        try:
            kind = CleanupTargetKind(_require_string(document["kind"], label="target kind"))
            state = CleanupTargetState(_require_string(document["state"], label="target state"))
        except ValueError as exc:
            raise EarlyCleanupStateError("cleanup target kind or state is unknown") from exc
        return cls(
            target_id=_require_string(document["target_id"], label="target ID"),
            kind=kind,
            locator=_require_string(document["locator"], label="target locator"),
            ownership_sha256=_require_sha256(
                document["ownership_sha256"], label="target ownership identity"
            ),
            public_alias=_require_string(document["public_alias"], label="target alias"),
            state=state,
            registered_at_epoch=_require_number(
                document["registered_at_epoch"], label="target registration time"
            ),
            last_attempt_id=last_attempt,
        )


@dataclass(frozen=True)
class CleanupAttempt:
    attempt_id: str
    target_id: str
    result: CleanupTargetState
    detail_code: str
    started_at_epoch: float
    completed_at_epoch: float

    def __post_init__(self) -> None:
        if (
            _SAFE_ID.fullmatch(self.attempt_id) is None
            or _SAFE_ID.fullmatch(self.target_id) is None
        ):
            raise EarlyCleanupStateError("cleanup attempt identity is unsafe")
        if _SAFE_ID.fullmatch(self.detail_code) is None:
            raise EarlyCleanupStateError("cleanup attempt detail code is unsafe")
        started = _require_number(self.started_at_epoch, label="cleanup attempt start")
        completed = _require_number(self.completed_at_epoch, label="cleanup attempt completion")
        if completed < started:
            raise EarlyCleanupStateError("cleanup attempt chronology moved backwards")

    def to_document(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "target_id": self.target_id,
            "result": self.result.value,
            "detail_code": self.detail_code,
            "started_at_epoch": self.started_at_epoch,
            "completed_at_epoch": self.completed_at_epoch,
        }

    @classmethod
    def from_document(cls, value: object) -> CleanupAttempt:
        document = _require_mapping(value, label="cleanup attempt")
        if set(document) != {
            "attempt_id",
            "target_id",
            "result",
            "detail_code",
            "started_at_epoch",
            "completed_at_epoch",
        }:
            raise EarlyCleanupStateError("cleanup attempt fields drifted")
        try:
            result = CleanupTargetState(_require_string(document["result"], label="cleanup result"))
        except ValueError as exc:
            raise EarlyCleanupStateError("cleanup attempt result is unknown") from exc
        return cls(
            attempt_id=_require_string(document["attempt_id"], label="cleanup attempt ID"),
            target_id=_require_string(document["target_id"], label="cleanup target ID"),
            result=result,
            detail_code=_require_string(document["detail_code"], label="cleanup detail code"),
            started_at_epoch=_require_number(
                document["started_at_epoch"], label="cleanup attempt start"
            ),
            completed_at_epoch=_require_number(
                document["completed_at_epoch"], label="cleanup attempt completion"
            ),
        )


@dataclass(frozen=True)
class CleanupActionResult:
    state: CleanupTargetState
    detail_code: str


@dataclass(frozen=True)
class EarlyCleanupState:
    journal_id: str
    sequence: int
    previous_version_sha256: str | None
    plan_id: str
    host_run_id: str
    package_commit: str
    plan_sha256: str
    provider_instance_id: str
    provider_instance_identity_sha256: str
    provider_started_at_epoch: float
    launch_slot: int
    replacement_eligibility_sha256: str | None
    created_at_epoch: float
    recorded_at_epoch: float
    lifecycle_stage: CleanupLifecycleStage
    empirical_entry_status: EmpiricalEntryStatus
    targets: tuple[CleanupTarget, ...]
    cleanup_attempts: tuple[CleanupAttempt, ...]
    terminal_cleanup_disposition: TerminalCleanupDisposition
    # None preserves an older journal whose writer did not track this boundary.
    freeze_publication_started: bool | None = None

    def to_document(self) -> dict[str, object]:
        return {
            "schema_version": EARLY_CLEANUP_SCHEMA_VERSION,
            "state_type": "t09-early-cleanup-state",
            "journal_id": self.journal_id,
            "sequence": self.sequence,
            "previous_version_sha256": self.previous_version_sha256,
            "plan_id": self.plan_id,
            "host_run_id": self.host_run_id,
            "package_commit": self.package_commit,
            "plan_sha256": self.plan_sha256,
            "provider_instance_id": self.provider_instance_id,
            "provider_instance_identity_sha256": self.provider_instance_identity_sha256,
            "provider_started_at_epoch": self.provider_started_at_epoch,
            "launch_slot": self.launch_slot,
            "replacement_eligibility_sha256": self.replacement_eligibility_sha256,
            "created_at_epoch": self.created_at_epoch,
            "recorded_at_epoch": self.recorded_at_epoch,
            "lifecycle_stage": self.lifecycle_stage.value,
            "empirical_entry_status": self.empirical_entry_status.value,
            "pilot_state_required_for_cleanup": False,
            "campaign_state_required_for_cleanup": False,
            "finalizer_state_required_for_cleanup": False,
            "targets": [target.to_document() for target in self.targets],
            "cleanup_attempts": [attempt.to_document() for attempt in self.cleanup_attempts],
            "terminal_cleanup_disposition": self.terminal_cleanup_disposition.value,
            **(
                {"freeze_publication_started": self.freeze_publication_started}
                if self.freeze_publication_started is not None
                else {}
            ),
        }

    @classmethod
    def from_document(cls, value: object) -> EarlyCleanupState:
        document = _require_mapping(value, label="early cleanup state")
        expected = {
            "schema_version",
            "state_type",
            "journal_id",
            "sequence",
            "previous_version_sha256",
            "plan_id",
            "host_run_id",
            "package_commit",
            "plan_sha256",
            "provider_instance_id",
            "provider_instance_identity_sha256",
            "provider_started_at_epoch",
            "launch_slot",
            "replacement_eligibility_sha256",
            "created_at_epoch",
            "recorded_at_epoch",
            "lifecycle_stage",
            "empirical_entry_status",
            "pilot_state_required_for_cleanup",
            "campaign_state_required_for_cleanup",
            "finalizer_state_required_for_cleanup",
            "targets",
            "cleanup_attempts",
            "terminal_cleanup_disposition",
        }
        if "freeze_publication_started" in document:
            expected.add("freeze_publication_started")
            if type(document["freeze_publication_started"]) is not bool:
                raise EarlyCleanupStateError("freeze publication tracking is malformed")
        if set(document) != expected:
            raise EarlyCleanupStateError("early cleanup state fields drifted")
        if (
            document["schema_version"] != EARLY_CLEANUP_SCHEMA_VERSION
            or document["state_type"] != "t09-early-cleanup-state"
            or document["pilot_state_required_for_cleanup"] is not False
            or document["campaign_state_required_for_cleanup"] is not False
            or document["finalizer_state_required_for_cleanup"] is not False
        ):
            raise EarlyCleanupStateError("early cleanup state contract drifted")
        previous = document["previous_version_sha256"]
        if previous is not None:
            previous = _require_sha256(previous, label="previous cleanup version")
        replacement_identity = document["replacement_eligibility_sha256"]
        if replacement_identity is not None:
            replacement_identity = _require_sha256(
                replacement_identity, label="replacement eligibility identity"
            )
        try:
            lifecycle = CleanupLifecycleStage(
                _require_string(document["lifecycle_stage"], label="cleanup lifecycle stage")
            )
            empirical = EmpiricalEntryStatus(
                _require_string(document["empirical_entry_status"], label="empirical status")
            )
            disposition = TerminalCleanupDisposition(
                _require_string(
                    document["terminal_cleanup_disposition"], label="cleanup disposition"
                )
            )
        except ValueError as exc:
            raise EarlyCleanupStateError("early cleanup enum value is unknown") from exc
        state = cls(
            journal_id=_require_sha256(document["journal_id"], label="cleanup journal ID"),
            sequence=_require_integer(document["sequence"], label="cleanup sequence"),
            previous_version_sha256=previous,
            plan_id=_require_string(document["plan_id"], label="plan ID"),
            host_run_id=_require_string(document["host_run_id"], label="host run ID"),
            package_commit=_require_string(document["package_commit"], label="package commit"),
            plan_sha256=_require_sha256(document["plan_sha256"], label="plan identity"),
            provider_instance_id=_require_string(
                document["provider_instance_id"], label="provider instance ID"
            ),
            provider_instance_identity_sha256=_require_sha256(
                document["provider_instance_identity_sha256"],
                label="provider instance identity",
            ),
            provider_started_at_epoch=_require_number(
                document["provider_started_at_epoch"], label="provider start"
            ),
            launch_slot=_require_integer(document["launch_slot"], label="launch slot"),
            replacement_eligibility_sha256=replacement_identity,
            created_at_epoch=_require_number(document["created_at_epoch"], label="creation time"),
            recorded_at_epoch=_require_number(
                document["recorded_at_epoch"], label="recording time"
            ),
            lifecycle_stage=lifecycle,
            empirical_entry_status=empirical,
            targets=tuple(
                CleanupTarget.from_document(item)
                for item in _require_list(document["targets"], label="cleanup targets")
            ),
            cleanup_attempts=tuple(
                CleanupAttempt.from_document(item)
                for item in _require_list(document["cleanup_attempts"], label="cleanup attempts")
            ),
            terminal_cleanup_disposition=disposition,
            freeze_publication_started=cast(
                bool | None, document.get("freeze_publication_started")
            ),
        )
        state.validate()
        return state

    def validate(self) -> None:
        if (
            self.sequence < 1
            or (self.sequence == 1) != (self.previous_version_sha256 is None)
            or _SAFE_ID.fullmatch(self.plan_id) is None
            or _SAFE_ID.fullmatch(self.host_run_id) is None
            or _HEX40.fullmatch(self.package_commit) is None
            or _SAFE_ID.fullmatch(self.provider_instance_id) is None
            or self.launch_slot < 1
            or self.recorded_at_epoch < self.created_at_epoch
        ):
            raise EarlyCleanupStateError("early cleanup state identity or chronology drifted")
        target_ids = [target.target_id for target in self.targets]
        if len(target_ids) != len(set(target_ids)) or "provider-instance" not in target_ids:
            raise EarlyCleanupStateError("cleanup targets are duplicated or lack the provider")
        attempts = {attempt.attempt_id: attempt for attempt in self.cleanup_attempts}
        if len(attempts) != len(self.cleanup_attempts):
            raise EarlyCleanupStateError("cleanup attempt IDs are duplicated")
        for attempt in attempts.values():
            if attempt.target_id not in target_ids:
                raise EarlyCleanupStateError("cleanup attempt references an unknown target")
        for target in self.targets:
            if target.last_attempt_id is not None:
                last_attempt = attempts.get(target.last_attempt_id)
                if last_attempt is None or last_attempt.target_id != target.target_id:
                    raise EarlyCleanupStateError("target last attempt is not source-bound")
                if last_attempt.result != target.state:
                    raise EarlyCleanupStateError("target state contradicts its last attempt")
        all_terminal = all(target.state in _TERMINAL_TARGET_STATES for target in self.targets)
        if (
            self.terminal_cleanup_disposition is TerminalCleanupDisposition.COMPLETE
        ) != all_terminal:
            raise EarlyCleanupStateError("terminal cleanup disposition contradicts targets")
        if (
            self.terminal_cleanup_disposition is TerminalCleanupDisposition.PENDING
            and self.cleanup_attempts
        ):
            raise EarlyCleanupStateError("attempted cleanup cannot remain pending")


class EarlyCleanupJournal:
    """Hash-chained version store for one exact provider ownership scope."""

    def __init__(
        self, root: Path, *, before_write: Callable[[Path, int], None] | None = None
    ) -> None:
        self.before_write = before_write
        self.root = root
        self.versions = root / "versions"
        self.lock_path = root / ".lock"

    @classmethod
    def initialize(
        cls,
        root: Path,
        *,
        plan_id: str,
        host_run_id: str,
        package_commit: str,
        plan_sha256: str,
        provider_instance_id: str,
        provider_instance_identity_sha256: str,
        provider_started_at_epoch: float,
        launch_slot: int,
        replacement_eligibility_sha256: str | None,
        firewall_baseline_identity_sha256: str,
        temporary_local_secret_locator: str | None = None,
        temporary_remote_secret_locator: str | None = None,
        clock: Callable[[], float] = time.time,
        before_write: Callable[[Path, int], None] | None = None,
    ) -> EarlyCleanupJournal:
        if root.exists():
            raise EarlyCleanupStateError("early cleanup journal already exists")
        root.mkdir(mode=0o700, parents=False, exist_ok=False)
        cls._fsync_directory(root.parent)
        versions = root / "versions"
        versions.mkdir(mode=0o700, exist_ok=False)
        cls._fsync_directory(root)
        journal = cls(root, before_write=before_write)
        created = clock()
        provider_target = CleanupTarget(
            target_id="provider-instance",
            kind=CleanupTargetKind.PROVIDER_INSTANCE,
            locator=provider_instance_id,
            ownership_sha256=provider_instance_identity_sha256,
            public_alias="provider-instance",
            state=CleanupTargetState.OWNED,
            registered_at_epoch=created,
        )
        firewall_target = CleanupTarget(
            target_id="firewall-restoration",
            kind=CleanupTargetKind.FIREWALL_RESTORATION,
            locator="entry-source/provider-firewall-baseline",
            ownership_sha256=firewall_baseline_identity_sha256,
            public_alias="provider-firewall-baseline",
            state=CleanupTargetState.OWNED,
            registered_at_epoch=created,
        )
        identity = {
            "plan_id": plan_id,
            "host_run_id": host_run_id,
            "package_commit": package_commit,
            "plan_sha256": plan_sha256,
            "provider_instance_id": provider_instance_id,
            "provider_instance_identity_sha256": provider_instance_identity_sha256,
            "provider_started_at_epoch": provider_started_at_epoch,
            "launch_slot": launch_slot,
            "replacement_eligibility_sha256": replacement_eligibility_sha256,
        }
        targets = [provider_target, firewall_target]
        for target_id, kind, locator, alias in (
            (
                "temporary-local-secret",
                CleanupTargetKind.TEMPORARY_LOCAL_CREDENTIAL,
                temporary_local_secret_locator,
                "temporary-local-secret",
            ),
            (
                "temporary-remote-secret",
                CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL,
                temporary_remote_secret_locator,
                "temporary-remote-secret",
            ),
        ):
            if locator is not None:
                targets.append(
                    CleanupTarget(
                        target_id=target_id,
                        kind=kind,
                        locator=locator,
                        ownership_sha256=cleanup_locator_identity(kind, locator),
                        public_alias=alias,
                        state=CleanupTargetState.OWNED,
                        registered_at_epoch=created,
                    )
                )
        state = EarlyCleanupState(
            journal_id=_sha256_bytes(_canonical_bytes(identity)),
            sequence=1,
            previous_version_sha256=None,
            plan_id=plan_id,
            host_run_id=host_run_id,
            package_commit=package_commit,
            plan_sha256=plan_sha256,
            provider_instance_id=provider_instance_id,
            provider_instance_identity_sha256=provider_instance_identity_sha256,
            provider_started_at_epoch=provider_started_at_epoch,
            launch_slot=launch_slot,
            replacement_eligibility_sha256=replacement_eligibility_sha256,
            created_at_epoch=created,
            recorded_at_epoch=created,
            lifecycle_stage=CleanupLifecycleStage.PROVIDER_IDENTITY_ACQUIRED,
            empirical_entry_status=EmpiricalEntryStatus.NOT_ENTERED,
            targets=tuple(targets),
            cleanup_attempts=(),
            terminal_cleanup_disposition=TerminalCleanupDisposition.PENDING,
            freeze_publication_started=False,
        )
        state.validate()
        with journal._lock():
            journal._append_unlocked(state)
        return journal

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        if not self.root.is_dir() or not self.versions.is_dir():
            raise EarlyCleanupStateError("early cleanup journal is missing")
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except FileNotFoundError as exc:
            raise EarlyCleanupStateError("early cleanup journal is missing") from exc
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _version_paths(self) -> list[Path]:
        paths: list[tuple[int, Path]] = []
        for path in self.versions.iterdir():
            match = _VERSION_NAME.fullmatch(path.name)
            if match is None:
                if ".pending." in path.name:
                    continue
                raise EarlyCleanupStateError("early cleanup versions contain an unknown member")
            paths.append((int(match.group("sequence")), path))
        paths.sort(key=lambda item: item[0])
        return [path for _, path in paths]

    def _load_unlocked(self) -> tuple[EarlyCleanupState, str]:
        if not self.root.is_dir() or not self.versions.is_dir():
            raise EarlyCleanupStateError("early cleanup journal is missing")
        paths = self._version_paths()
        if not paths:
            raise EarlyCleanupStateError("early cleanup journal has no durable version")
        previous_sha256: str | None = None
        state: EarlyCleanupState | None = None
        for expected_sequence, path in enumerate(paths, start=1):
            if path.name != f"{expected_sequence:08d}.json" or path.is_symlink():
                raise EarlyCleanupStateError("early cleanup version sequence drifted")
            raw = path.read_bytes()
            if not raw or len(raw) > 1_048_576:
                raise EarlyCleanupStateError("early cleanup version size is invalid")
            try:
                parsed = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EarlyCleanupStateError("early cleanup version is not valid JSON") from exc
            if raw != _canonical_bytes(parsed):
                raise EarlyCleanupStateError("early cleanup version is not canonical JSON")
            candidate = EarlyCleanupState.from_document(parsed)
            if (
                candidate.sequence != expected_sequence
                or candidate.previous_version_sha256 != previous_sha256
            ):
                raise EarlyCleanupStateError("early cleanup hash chain is broken")
            if state is not None:
                self._validate_transition(state, candidate)
            previous_sha256 = _sha256_bytes(raw)
            state = candidate
        assert state is not None and previous_sha256 is not None
        return state, previous_sha256

    @staticmethod
    def _validate_transition(before: EarlyCleanupState, after: EarlyCleanupState) -> None:
        immutable_before = replace(
            before,
            sequence=after.sequence,
            previous_version_sha256=after.previous_version_sha256,
            recorded_at_epoch=after.recorded_at_epoch,
            lifecycle_stage=after.lifecycle_stage,
            empirical_entry_status=after.empirical_entry_status,
            targets=after.targets,
            cleanup_attempts=after.cleanup_attempts,
            terminal_cleanup_disposition=after.terminal_cleanup_disposition,
            freeze_publication_started=after.freeze_publication_started,
        )
        if immutable_before != after:
            raise EarlyCleanupStateError("early cleanup immutable identity changed")
        if (
            after.sequence != before.sequence + 1
            or after.recorded_at_epoch < before.recorded_at_epoch
        ):
            raise EarlyCleanupStateError("early cleanup version chronology drifted")
        if _STAGE_ORDER[after.lifecycle_stage] < _STAGE_ORDER[before.lifecycle_stage]:
            raise EarlyCleanupStateError("early cleanup lifecycle moved backwards")
        if (
            before.empirical_entry_status is EmpiricalEntryStatus.ENTERED
            and after.empirical_entry_status is not EmpiricalEntryStatus.ENTERED
        ):
            raise EarlyCleanupStateError("empirical entry status moved backwards")
        if (
            after.freeze_publication_started is not before.freeze_publication_started
            and after.freeze_publication_started is not True
        ):
            raise EarlyCleanupStateError("freeze publication tracking moved backwards")
        before_targets = {target.target_id: target for target in before.targets}
        after_targets = {target.target_id: target for target in after.targets}
        if not before_targets.keys() <= after_targets.keys():
            raise EarlyCleanupStateError("early cleanup target disappeared")
        for target_id, target in before_targets.items():
            successor = after_targets[target_id]
            if (
                replace(target, state=successor.state, last_attempt_id=successor.last_attempt_id)
                != successor
            ):
                raise EarlyCleanupStateError("early cleanup target identity changed")
            if target.state in _TERMINAL_TARGET_STATES and successor != target:
                raise EarlyCleanupStateError("terminal cleanup target changed")
        if after.cleanup_attempts[: len(before.cleanup_attempts)] != before.cleanup_attempts:
            raise EarlyCleanupStateError("cleanup attempt history changed")

    def _append_unlocked(self, state: EarlyCleanupState) -> None:
        encoded = _canonical_bytes(state.to_document())
        final_name = f"{state.sequence:08d}.json"
        pending_name = f".{final_name}.pending.{uuid.uuid4().hex}"
        pending_path = self.versions / pending_name
        final_path = self.versions / final_name
        allowance = admit_campaign_write(
            final_path, len(encoded), CampaignWriterRole.CLEANUP_JOURNAL
        )
        if allowance is None and self.before_write is not None:
            self.before_write(final_path, len(encoded))
        descriptor = os.open(
            pending_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            offset = 0
            while offset < len(encoded):
                written = os.write(descriptor, encoded[offset:])
                if written <= 0:
                    raise OSError("short early cleanup state write")
                observe_campaign_write(allowance, written)
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if final_path.exists():
            raise EarlyCleanupStateError("early cleanup version already exists")
        os.rename(pending_path, final_path)
        verify_campaign_write(allowance, final_path)
        self._fsync_directory(self.versions)

    def load(self) -> EarlyCleanupState:
        with self._lock():
            return self._load_unlocked()[0]

    def latest_version_sha256(self) -> str:
        with self._lock():
            return self._load_unlocked()[1]

    def version_state_and_sha256(self, sequence: int) -> tuple[EarlyCleanupState, str]:
        """Return one immutable version after validating the complete journal chain."""

        if type(sequence) is not int or sequence < 1:
            raise EarlyCleanupStateError("early cleanup version sequence is invalid")
        with self._lock():
            latest, _latest_sha256 = self._load_unlocked()
            if sequence > latest.sequence:
                raise EarlyCleanupStateError("early cleanup version is not retained")
            path = self.versions / f"{sequence:08d}.json"
            raw = path.read_bytes()
            try:
                parsed = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EarlyCleanupStateError("early cleanup version is not valid JSON") from exc
            state = EarlyCleanupState.from_document(parsed)
            if state.sequence != sequence or state.journal_id != latest.journal_id:
                raise EarlyCleanupStateError("early cleanup retained version identity drifted")
            return state, _sha256_bytes(raw)

    def _next_state(
        self,
        state: EarlyCleanupState,
        previous_sha256: str,
        *,
        clock: Callable[[], float],
        lifecycle_stage: CleanupLifecycleStage | None = None,
        empirical_entry_status: EmpiricalEntryStatus | None = None,
        targets: tuple[CleanupTarget, ...] | None = None,
        cleanup_attempts: tuple[CleanupAttempt, ...] | None = None,
        terminal_cleanup_disposition: TerminalCleanupDisposition | None = None,
        freeze_publication_started: bool | None = None,
    ) -> EarlyCleanupState:
        successor = replace(
            state,
            sequence=state.sequence + 1,
            previous_version_sha256=previous_sha256,
            recorded_at_epoch=clock(),
            lifecycle_stage=lifecycle_stage or state.lifecycle_stage,
            empirical_entry_status=empirical_entry_status or state.empirical_entry_status,
            targets=targets or state.targets,
            cleanup_attempts=(
                cleanup_attempts if cleanup_attempts is not None else state.cleanup_attempts
            ),
            terminal_cleanup_disposition=(
                terminal_cleanup_disposition
                if terminal_cleanup_disposition is not None
                else state.terminal_cleanup_disposition
            ),
            freeze_publication_started=(
                freeze_publication_started
                if freeze_publication_started is not None
                else state.freeze_publication_started
            ),
        )
        successor.validate()
        self._validate_transition(state, successor)
        return successor

    def advance_lifecycle(
        self,
        stage: CleanupLifecycleStage,
        *,
        clock: Callable[[], float] = time.time,
    ) -> EarlyCleanupState:
        with self._lock():
            state, previous_sha256 = self._load_unlocked()
            if stage == state.lifecycle_stage:
                return state
            if _STAGE_ORDER[stage] < _STAGE_ORDER[state.lifecycle_stage]:
                raise EarlyCleanupStateError("cleanup lifecycle cannot move backwards")
            empirical = state.empirical_entry_status
            if stage is CleanupLifecycleStage.EMPIRICAL_ENTRY:
                empirical = EmpiricalEntryStatus.ENTERED
            successor = self._next_state(
                state,
                previous_sha256,
                clock=clock,
                lifecycle_stage=stage,
                empirical_entry_status=empirical,
            )
            self._append_unlocked(successor)
            return successor

    def advance_lifecycle_at_least(
        self,
        stage: CleanupLifecycleStage,
        *,
        clock: Callable[[], float] = time.time,
    ) -> EarlyCleanupState:
        """Advance to a minimum stage without regressing a later durable stage."""

        with self._lock():
            state, previous_sha256 = self._load_unlocked()
            if _STAGE_ORDER[state.lifecycle_stage] >= _STAGE_ORDER[stage]:
                return state
            empirical = state.empirical_entry_status
            if stage is CleanupLifecycleStage.EMPIRICAL_ENTRY:
                empirical = EmpiricalEntryStatus.ENTERED
            successor = self._next_state(
                state,
                previous_sha256,
                clock=clock,
                lifecycle_stage=stage,
                empirical_entry_status=empirical,
            )
            self._append_unlocked(successor)
            return successor

    def import_continuation(self, continuation: EarlyCleanupJournal) -> EarlyCleanupState:
        """Append an exact transferred continuation to this journal's hash chain."""

        if self.root.resolve(strict=True) == continuation.root.resolve(strict=True):
            return self.load()
        with continuation._lock():
            continuation_state, _ = continuation._load_unlocked()
            continuation_versions = [
                (path.name, path.read_bytes()) for path in continuation._version_paths()
            ]
        with self._lock():
            local_state, _ = self._load_unlocked()
            local_paths = self._version_paths()
            if continuation_state.journal_id != local_state.journal_id:
                raise EarlyCleanupStateError("cleanup continuation belongs to another journal")
            if len(continuation_versions) < len(local_paths):
                raise EarlyCleanupStateError("cleanup continuation is older than the local journal")
            for local_path, (name, remote_bytes) in zip(
                local_paths,
                continuation_versions,
                strict=False,
            ):
                if local_path.name != name or local_path.read_bytes() != remote_bytes:
                    raise EarlyCleanupStateError("cleanup continuation changed its retained prefix")
            for name, remote_bytes in continuation_versions[len(local_paths) :]:
                try:
                    document = json.loads(remote_bytes)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise EarlyCleanupStateError(
                        "cleanup continuation version is not valid JSON"
                    ) from exc
                candidate = EarlyCleanupState.from_document(document)
                if name != f"{candidate.sequence:08d}.json":
                    raise EarlyCleanupStateError("cleanup continuation sequence drifted")
                self._append_unlocked(candidate)
            imported, _ = self._load_unlocked()
            if imported != continuation_state:
                raise EarlyCleanupStateError("cleanup continuation import was not exact")
            return imported

    def begin_freeze_publication(
        self, *, clock: Callable[[], float] = time.time
    ) -> EarlyCleanupState:
        """Record a durable intent before the first frozen-manifest publication."""
        with self._lock():
            state, previous_sha256 = self._load_unlocked()
            if state.freeze_publication_started is True:
                raise EarlyCleanupStateError("freeze publication cannot be repeated")
            if state.lifecycle_stage in {
                CleanupLifecycleStage.CLEANUP_IN_PROGRESS,
                CleanupLifecycleStage.CLEANUP_FINISHED,
            }:
                raise EarlyCleanupStateError("cleanup does not authorize freeze publication")
            successor = self._next_state(
                state, previous_sha256, clock=clock, freeze_publication_started=True
            )
            self._append_unlocked(successor)
            return successor

    def register_target(
        self,
        *,
        target_id: str,
        kind: CleanupTargetKind,
        locator: str,
        ownership_sha256: str,
        public_alias: str,
        clock: Callable[[], float] = time.time,
    ) -> EarlyCleanupState:
        with self._lock():
            state, previous_sha256 = self._load_unlocked()
            target = CleanupTarget(
                target_id=target_id,
                kind=kind,
                locator=locator,
                ownership_sha256=ownership_sha256,
                public_alias=public_alias,
                state=CleanupTargetState.OWNED,
                registered_at_epoch=clock(),
            )
            existing = {item.target_id: item for item in state.targets}.get(target_id)
            if existing is not None:
                if (
                    existing.target_id != target.target_id
                    or existing.kind is not target.kind
                    or existing.locator != target.locator
                    or existing.ownership_sha256 != target.ownership_sha256
                    or existing.public_alias != target.public_alias
                ):
                    raise EarlyCleanupStateError("cleanup target ID was rebound")
                return state
            successor = self._next_state(
                state,
                previous_sha256,
                clock=clock,
                targets=(*state.targets, target),
            )
            self._append_unlocked(successor)
            return successor

    @staticmethod
    def _result_for_target(target: CleanupTarget, result: CleanupTargetState) -> None:
        if (
            result is not CleanupTargetState.FAILED
            and result not in _ALLOWED_TERMINAL_STATES[target.kind]
        ):
            raise EarlyCleanupStateError("cleanup result contradicts target kind")

    def record_result(
        self,
        *,
        target_id: str,
        result: CleanupTargetState,
        detail_code: str,
        started_at_epoch: float | None = None,
        during_cleanup: bool = True,
        clock: Callable[[], float] = time.time,
    ) -> EarlyCleanupState:
        with self._lock():
            state, previous_sha256 = self._load_unlocked()
            targets = {target.target_id: target for target in state.targets}
            target = targets.get(target_id)
            if target is None:
                raise EarlyCleanupStateError("cleanup result references an unknown target")
            self._result_for_target(target, result)
            if target.state in _TERMINAL_TARGET_STATES:
                if target.state != result:
                    raise EarlyCleanupStateError("terminal cleanup result cannot change")
                return state
            started = clock() if started_at_epoch is None else started_at_epoch
            completed = clock()
            attempt_id = f"cleanup-{state.sequence + 1:08d}-{target_id}"
            attempt = CleanupAttempt(
                attempt_id=attempt_id,
                target_id=target_id,
                result=result,
                detail_code=detail_code,
                started_at_epoch=started,
                completed_at_epoch=completed,
            )
            updated_targets = tuple(
                replace(item, state=result, last_attempt_id=attempt_id)
                if item.target_id == target_id
                else item
                for item in state.targets
            )
            all_terminal = all(item.state in _TERMINAL_TARGET_STATES for item in updated_targets)
            successor = self._next_state(
                state,
                previous_sha256,
                clock=clock,
                lifecycle_stage=(
                    CleanupLifecycleStage.CLEANUP_FINISHED
                    if during_cleanup and all_terminal
                    else CleanupLifecycleStage.CLEANUP_IN_PROGRESS
                    if during_cleanup
                    else state.lifecycle_stage
                ),
                targets=updated_targets,
                cleanup_attempts=(*state.cleanup_attempts, attempt),
                terminal_cleanup_disposition=(
                    TerminalCleanupDisposition.COMPLETE
                    if all_terminal
                    else TerminalCleanupDisposition.PARTIAL
                ),
            )
            self._append_unlocked(successor)
            return successor

    def cleanup(
        self,
        action: Callable[[CleanupTarget], CleanupActionResult],
        *,
        clock: Callable[[], float] = time.time,
    ) -> EarlyCleanupState:
        """Attempt every unfinished exact target, persisting each outcome."""

        state = self.load()
        if state.terminal_cleanup_disposition is TerminalCleanupDisposition.COMPLETE:
            return state
        for target in state.targets:
            current = {item.target_id: item for item in self.load().targets}[target.target_id]
            if current.state in _TERMINAL_TARGET_STATES:
                continue
            started = clock()
            try:
                result = action(current)
                self._result_for_target(current, result.state)
                detail_code = result.detail_code
                result_state = result.state
            except BaseException as exc:
                detail_code = type(exc).__name__
                result_state = CleanupTargetState.FAILED
            self.record_result(
                target_id=current.target_id,
                result=result_state,
                detail_code=detail_code,
                started_at_epoch=started,
                clock=clock,
            )
        return self.load()

    def basic_closeout_receipt(self) -> dict[str, object]:
        with self._lock():
            state, version_sha256 = self._load_unlocked()
        return {
            "schema_version": EARLY_CLEANUP_RECEIPT_SCHEMA_VERSION,
            "receipt_type": "t09-basic-early-cleanup-closeout",
            "journal_id": state.journal_id,
            "journal_sequence": state.sequence,
            "journal_version_sha256": version_sha256,
            "plan_id": state.plan_id,
            "host_run_id": state.host_run_id,
            "provider_instance_id": state.provider_instance_id,
            "provider_instance_identity_sha256": state.provider_instance_identity_sha256,
            "empirical_entry_status": state.empirical_entry_status.value,
            "lifecycle_stage": state.lifecycle_stage.value,
            "pilot_state_used": False,
            "campaign_state_used": False,
            "finalizer_state_used": False,
            "cleanup_attempt_count": len(state.cleanup_attempts),
            "targets": [
                {
                    "target_id": target.target_id,
                    "kind": target.kind.value,
                    "public_alias": target.public_alias,
                    "ownership_sha256": target.ownership_sha256,
                    "state": target.state.value,
                }
                for target in state.targets
            ],
            "terminal_cleanup_disposition": state.terminal_cleanup_disposition.value,
        }

    def write_basic_closeout_receipt(self, path: Path) -> Path:
        receipt = self.basic_closeout_receipt()
        encoded = _canonical_bytes(receipt)
        if path.exists():
            if path.is_symlink() or path.read_bytes() != encoded:
                raise EarlyCleanupStateError("basic cleanup closeout receipt drifted")
            return path
        allowance = admit_campaign_write(path, len(encoded), CampaignWriterRole.CLEANUP_RECEIPT)
        if allowance is None and self.before_write is not None:
            self.before_write(path, len(encoded))
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            offset = 0
            while offset < len(encoded):
                written = os.write(descriptor, encoded[offset:])
                if written <= 0:
                    raise OSError("short basic cleanup closeout write")
                observe_campaign_write(allowance, written)
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        verify_campaign_write(allowance, path)
        self._fsync_directory(path.parent)
        return path
