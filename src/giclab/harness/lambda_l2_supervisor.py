"""Offline transaction-control primitives for T07 Lambda Gate L2.1.

The module contains draft policies, durable journals, aggregate budget helpers,
request/process boundaries, launch/discovery/termination semantics, and completion
eligibility. Importing it performs no I/O. Independent review established that these
pieces do not compose an authoritative live runner, so they are non-executable design
evidence under the terminal ``manual-console-launch-required`` decision.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import http.client
import json
import math
import os
import re
import selectors
import signal
import ssl
import stat
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol

from jsonschema import Draft202012Validator

from .lambda_l2_ownership import (
    DiscoveryKind,
    DiscoveryResult,
    ExpectedOwnedInstance,
    OwnershipContractError,
    classify_discovery,
    revalidate_owned_instance_detail,
)


class L21SupervisorError(ValueError):
    """The Gate L2.1 supervisor contract failed closed."""


BRANCH: Final = "phase-1/sira-smoke-lambda"
PLAN_ID: Final = "PLAN-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V2"
RUN_ID: Final = "RUN-T07-L2-LAMBDA-HOST-QUALIFICATION-0002"
AUTHORIZATION_PLACEHOLDER: Final = "AUTH-T07-GATE-L2-LAMBDA-HOST-QUALIFICATION-V2-PENDING"
API_HOST: Final = "cloud.lambda.ai"
API_BASE_URL: Final = "https://cloud.lambda.ai"
TERMINAL_DECISION: Final = "manual-console-launch-required"
TRANSACTION_SCHEMA_PATH: Final = "schemas/t07-lambda-l2-transaction-journal.schema.json"

INITIAL_LAUNCH_RESPONSE_SECONDS: Final = 30
NORMAL_DISCOVERY_SECONDS: Final = 300
QUALIFICATION_PROVIDER_WALL_SECONDS: Final = 3_600
POST_FAILURE_DISCOVERY_SECONDS: Final = 1_800
MANUAL_CONSOLE_RESPONSE_SECONDS: Final = 900
ABSOLUTE_INCIDENT_SECONDS: Final = 5_400
PROVIDER_REQUEST_SPACING_SECONDS: Final = 1
DISCOVERY_POLL_SPACING_SECONDS: Final = 12
WATCHDOG_HEARTBEAT_SECONDS: Final = 2
WATCHDOG_STALE_SECONDS: Final = 10
WATCHDOG_READY_SECONDS: Final = 15

MAX_PROVIDER_COST_CENTS: Final = 200
SELECTED_LIST_PRICE_CENTS_PER_HOUR: Final = 129
NORMAL_PROJECTED_COST_CENTS: Final = 129
INCIDENT_PROJECTED_COST_CENTS: Final = 194
MAX_PROVIDER_CALLS: Final = 420
MAX_PREFLIGHT_CALLS: Final = 7
MAX_FIREWALL_MUTATION_CALLS: Final = 4
MAX_FIREWALL_VERIFICATION_CALLS: Final = 4
MAX_LAUNCH_CALLS: Final = 1
MAX_NORMAL_DISCOVERY_LIST_CALLS: Final = 25
MAX_NORMAL_DISCOVERY_DETAIL_CALLS: Final = 5
MAX_ACTIVE_POLLS: Final = 30
MAX_INCIDENT_DISCOVERY_LIST_CALLS: Final = 150
MAX_INCIDENT_DISCOVERY_DETAIL_CALLS: Final = 20
MAX_OWNED_INSTANCE_IDS: Final = 4
MAX_TERMINATION_CALLS: Final = 4
MAX_TERMINAL_POLLS: Final = 160
MAX_FINAL_ZERO_INSTANCE_CALLS: Final = 1
MAX_PROVIDER_RESPONSE_BYTES_PER_CALL: Final = 1_048_576
MAX_PROVIDER_RESPONSE_BYTES_AGGREGATE: Final = 67_108_864
MAX_PROVIDER_REQUEST_BODY_BYTES: Final = 65_536

MAX_TRANSACTION_EVENTS: Final = 4_096
MAX_TRANSACTION_EVENT_BYTES: Final = 4_096
MAX_TRANSACTION_BYTES: Final = 16_777_216
MAX_WATCHDOG_EVENTS: Final = 4_096
MAX_WATCHDOG_EVENT_BYTES: Final = 4_096
MAX_WATCHDOG_BYTES: Final = 16_777_216
MAX_HEARTBEAT_EVENTS: Final = 2_700
MAX_HEARTBEAT_BYTES: Final = 524_288

MAX_PROCESS_CALLS: Final = 128
MAX_PROCESS_OUTPUT_BYTES_PER_CALL: Final = 1_048_576
MAX_PROCESS_OUTPUT_BYTES_AGGREGATE: Final = 33_554_432
MAX_TCP_READINESS_PROBES: Final = 30
MAX_SSH_AGENT_CALLS: Final = 1
MAX_SSH_KEYSCAN_CALLS: Final = 1
MAX_SSH_SESSIONS: Final = 33
MAX_REMOTE_COMMANDS: Final = 33
MAX_SSH_TRANSFER_CALLS: Final = 33
MAX_DOCKER_CALLS: Final = 24
MAX_CONTAINER_COUNT: Final = 1
MAX_CONTAINER_WALL_SECONDS: Final = 30
MAX_CONTAINER_OUTPUT_BYTES: Final = 16_777_216
MAX_REMOTE_EVIDENCE_BYTES: Final = 62_914_560
MAX_TRANSFER_BYTES: Final = 62_914_560
MAX_LOCAL_EVIDENCE_BYTES: Final = 67_108_864
MAX_ARCHIVE_BYTES: Final = 67_108_864
MAX_ARCHIVE_COPY_CALLS: Final = 1
MAX_LOCAL_INCREMENTAL_BYTES: Final = 135_266_304
MIN_LOCAL_PREWRITE_FREE_BYTES: Final = 8_725_200_896
MIN_LOCAL_RETAINED_FREE_BYTES: Final = 8_589_934_592
EXTERNAL_RETAINED_FREE_FLOOR_BYTES: Final = 200_048_192_717
EXTERNAL_PRECOPY_FREE_FLOOR_BYTES: Final = 200_115_301_581
RESIDUAL_RISK_STATEMENT: Final = (
    "The Lambda API does not document launch idempotency. A unique name/hostname/tag "
    "marker plus prelaunch zero-match check and exact-ID discovery provides strong "
    "ownership evidence but cannot guarantee cleanup during a prolonged Lambda API and "
    "console outage, Mac power/network loss, or simultaneous supervisor/watchdog failure. "
    "In those cases a billable instance may remain until control-plane access is restored."
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SAFE_PROVIDER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SAFE_ALIAS = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def reject_retired_live_effector(kind: str) -> None:
    """Enforce D-027 before any concrete network, process, or fork effect."""

    raise L21SupervisorError(f"{TERMINAL_DECISION} blocks the concrete Gate L2 {kind}")


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_reference(value: str, *, context: str) -> str:
    if _SAFE_REFERENCE.fullmatch(value) is None:
        raise L21SupervisorError(f"{context} is not a safe immutable reference")
    return value


def _safe_hash(value: str, *, context: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise L21SupervisorError(f"{context} is not a lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    plan_id: str
    plan_sha256: str
    run_id: str
    authorization_reference: str
    repository_commit: str
    reviewed_implementation_commit: str
    human_decision_seal_sha256: str
    launch_recovery_decision_seal_sha256: str
    private_parameter_seal_reference: str

    def __post_init__(self) -> None:
        if self.plan_id != PLAN_ID or self.run_id != RUN_ID:
            raise L21SupervisorError("plan or run identity differs from Gate L2 V2")
        for value, context in (
            (self.plan_id, "plan ID"),
            (self.run_id, "run ID"),
            (self.authorization_reference, "authorization reference"),
            (self.private_parameter_seal_reference, "private seal reference"),
        ):
            _safe_reference(value, context=context)
        if self.authorization_reference.endswith("-PENDING"):
            raise L21SupervisorError("pending authorization cannot execute")
        for value, context in (
            (self.plan_sha256, "plan hash"),
            (self.human_decision_seal_sha256, "human decision seal"),
            (
                self.launch_recovery_decision_seal_sha256,
                "launch-recovery decision seal",
            ),
        ):
            _safe_hash(value, context=context)
        if (
            _COMMIT.fullmatch(self.repository_commit) is None
            or _COMMIT.fullmatch(self.reviewed_implementation_commit) is None
        ):
            raise L21SupervisorError("repository or implementation commit is invalid")


def exact_l21_limits() -> dict[str, int | str]:
    """Return every non-null Gate L2.1 cap used by plan rendering and tests."""

    return {
        "initial_launch_response_seconds": INITIAL_LAUNCH_RESPONSE_SECONDS,
        "normal_discovery_seconds": NORMAL_DISCOVERY_SECONDS,
        "qualification_provider_wall_seconds": QUALIFICATION_PROVIDER_WALL_SECONDS,
        "post_failure_discovery_seconds": POST_FAILURE_DISCOVERY_SECONDS,
        "manual_console_response_seconds": MANUAL_CONSOLE_RESPONSE_SECONDS,
        "absolute_incident_seconds": ABSOLUTE_INCIDENT_SECONDS,
        "provider_request_spacing_seconds": PROVIDER_REQUEST_SPACING_SECONDS,
        "discovery_poll_spacing_seconds": DISCOVERY_POLL_SPACING_SECONDS,
        "watchdog_heartbeat_seconds": WATCHDOG_HEARTBEAT_SECONDS,
        "watchdog_stale_seconds": WATCHDOG_STALE_SECONDS,
        "watchdog_ready_seconds": WATCHDOG_READY_SECONDS,
        "provider_cost_cents": MAX_PROVIDER_COST_CENTS,
        "normal_projected_cost_cents": NORMAL_PROJECTED_COST_CENTS,
        "incident_projected_cost_cents_at_5400_seconds": INCIDENT_PROJECTED_COST_CENTS,
        "selected_list_price_cents_per_hour": SELECTED_LIST_PRICE_CENTS_PER_HOUR,
        "provider_calls": MAX_PROVIDER_CALLS,
        "preflight_calls": MAX_PREFLIGHT_CALLS,
        "firewall_mutation_calls": MAX_FIREWALL_MUTATION_CALLS,
        "firewall_verification_calls": MAX_FIREWALL_VERIFICATION_CALLS,
        "launch_calls": MAX_LAUNCH_CALLS,
        "normal_discovery_list_calls": MAX_NORMAL_DISCOVERY_LIST_CALLS,
        "normal_discovery_detail_calls": MAX_NORMAL_DISCOVERY_DETAIL_CALLS,
        "active_polls": MAX_ACTIVE_POLLS,
        "incident_discovery_list_calls": MAX_INCIDENT_DISCOVERY_LIST_CALLS,
        "incident_discovery_detail_calls": MAX_INCIDENT_DISCOVERY_DETAIL_CALLS,
        "owned_instance_ids": MAX_OWNED_INSTANCE_IDS,
        "termination_calls": MAX_TERMINATION_CALLS,
        "terminal_polls": MAX_TERMINAL_POLLS,
        "final_zero_instance_calls": MAX_FINAL_ZERO_INSTANCE_CALLS,
        "automatic_retries": 0,
        "pagination_requests": 0,
        "provider_response_bytes_per_call": MAX_PROVIDER_RESPONSE_BYTES_PER_CALL,
        "provider_response_bytes_aggregate": MAX_PROVIDER_RESPONSE_BYTES_AGGREGATE,
        "provider_request_body_bytes": MAX_PROVIDER_REQUEST_BODY_BYTES,
        "transaction_events": MAX_TRANSACTION_EVENTS,
        "transaction_event_bytes": MAX_TRANSACTION_EVENT_BYTES,
        "transaction_bytes": MAX_TRANSACTION_BYTES,
        "watchdog_events": MAX_WATCHDOG_EVENTS,
        "watchdog_event_bytes": MAX_WATCHDOG_EVENT_BYTES,
        "watchdog_bytes": MAX_WATCHDOG_BYTES,
        "heartbeat_events": MAX_HEARTBEAT_EVENTS,
        "heartbeat_bytes": MAX_HEARTBEAT_BYTES,
        "process_calls": MAX_PROCESS_CALLS,
        "process_output_bytes_per_call": MAX_PROCESS_OUTPUT_BYTES_PER_CALL,
        "process_output_bytes_aggregate": MAX_PROCESS_OUTPUT_BYTES_AGGREGATE,
        "tcp_readiness_probes": MAX_TCP_READINESS_PROBES,
        "ssh_agent_calls": MAX_SSH_AGENT_CALLS,
        "ssh_keyscan_calls": MAX_SSH_KEYSCAN_CALLS,
        "ssh_sessions": MAX_SSH_SESSIONS,
        "remote_commands": MAX_REMOTE_COMMANDS,
        "ssh_transfer_calls": MAX_SSH_TRANSFER_CALLS,
        "docker_calls": MAX_DOCKER_CALLS,
        "container_count": MAX_CONTAINER_COUNT,
        "container_wall_seconds": MAX_CONTAINER_WALL_SECONDS,
        "container_output_bytes": MAX_CONTAINER_OUTPUT_BYTES,
        "remote_evidence_bytes": MAX_REMOTE_EVIDENCE_BYTES,
        "transfer_bytes": MAX_TRANSFER_BYTES,
        "local_evidence_bytes": MAX_LOCAL_EVIDENCE_BYTES,
        "archive_bytes": MAX_ARCHIVE_BYTES,
        "archive_copy_calls": MAX_ARCHIVE_COPY_CALLS,
        "local_incremental_bytes": MAX_LOCAL_INCREMENTAL_BYTES,
        "local_prewrite_free_floor_bytes": MIN_LOCAL_PREWRITE_FREE_BYTES,
        "local_retained_free_floor_bytes": MIN_LOCAL_RETAINED_FREE_BYTES,
        "external_retained_free_floor_bytes": EXTERNAL_RETAINED_FREE_FLOOR_BYTES,
        "external_precopy_free_floor_bytes": EXTERNAL_PRECOPY_FREE_FLOOR_BYTES,
        "instance_count_normal": 1,
        "persistent_filesystem_count": 0,
        "model_calls": 0,
        "model_tokens": 0,
        "model_api_cost_cents": 0,
        "browser_actions": 0,
        "sira_executions": 0,
        "scientific_executions": 0,
    }


class Actor(StrEnum):
    PRIMARY = "primary"
    WATCHDOG = "watchdog"


class ProviderOperation(StrEnum):
    LIST_INSTANCE_TYPES = "list_instance_types"
    LIST_IMAGES = "list_images"
    LIST_REGIONS = "list_regions"
    LIST_SSH_KEYS = "list_ssh_keys"
    LIST_FIREWALL_RULESETS = "list_firewall_rulesets"
    GET_GLOBAL_FIREWALL = "get_global_firewall"
    LIST_INSTANCES = "list_instances"
    PATCH_GLOBAL_STRICT = "patch_global_strict"
    VERIFY_GLOBAL_STRICT = "verify_global_strict"
    CREATE_REGIONAL_RULESET = "create_regional_ruleset"
    GET_REGIONAL_RULESET = "get_regional_ruleset"
    DELETE_REGIONAL_RULESET = "delete_regional_ruleset"
    VERIFY_REGIONAL_ABSENT = "verify_regional_absent"
    LAUNCH_INSTANCE = "launch_instance"
    GET_INSTANCE_DETAIL = "get_instance_detail"
    TERMINATE_INSTANCE = "terminate_instance"
    RESTORE_GLOBAL_FIREWALL = "restore_global_firewall"
    VERIFY_GLOBAL_RESTORED = "verify_global_restored"


WATCHDOG_PROVIDER_ALLOWLIST: Final = frozenset(
    {
        ProviderOperation.LIST_INSTANCES,
        ProviderOperation.GET_INSTANCE_DETAIL,
        ProviderOperation.TERMINATE_INSTANCE,
        ProviderOperation.DELETE_REGIONAL_RULESET,
        ProviderOperation.VERIFY_REGIONAL_ABSENT,
        ProviderOperation.RESTORE_GLOBAL_FIREWALL,
        ProviderOperation.VERIFY_GLOBAL_RESTORED,
    }
)


class ProcessOperation(StrEnum):
    TCP_READINESS = "tcp_readiness"
    SSH_AGENT_INSPECTION = "ssh_agent_inspection"
    SSH_KEYSCAN = "ssh_keyscan"
    SSH_HOST_INSPECTION = "ssh_host_inspection"
    SSH_TRANSFER = "ssh_transfer"
    REMOTE_DOCKER = "remote_docker"
    CONTAINMENT_FIXTURE = "containment_fixture"
    EVIDENCE_VERIFY = "evidence_verify"


class JournalEvent(StrEnum):
    SUPERVISOR_STARTED = "supervisor_started"
    PREFLIGHT_INVENTORY_VERIFIED = "preflight_inventory_verified"
    WATCHDOG_READY = "watchdog_ready"
    FIREWALL_SNAPSHOT_SEALED = "firewall_snapshot_sealed"
    GLOBAL_FIREWALL_STRICT_VERIFIED = "global_firewall_strict_verified"
    REGIONAL_RULESET_STRICT_VERIFIED = "regional_ruleset_strict_verified"
    LAUNCH_BODY_SEALED = "launch_body_sealed"
    LAUNCH_INTENT_COMMITTED = "launch_intent_committed"
    LAUNCH_SEND_STARTED = "launch_send_started"
    LAUNCH_RESPONSE_RECEIVED = "launch_response_received"
    LAUNCH_RESPONSE_VALIDATED = "launch_response_validated"
    LAUNCH_RESPONSE_UNKNOWN_AFTER_SEND = "launch_response_unknown_after_send"
    LAUNCH_DEFINITIVELY_REJECTED = "launch_definitively_rejected"
    DISCOVERY_STARTED = "discovery_started"
    OWNED_INSTANCE_NOT_YET_VISIBLE = "owned_instance_not_yet_visible"
    OWNED_INSTANCE_DISCOVERED = "owned_instance_discovered"
    OWNED_INSTANCE_AMBIGUOUS = "owned_instance_ambiguous"
    OWNED_INSTANCE_BOUND = "owned_instance_bound"
    PROVIDER_REQUEST_INTENT = "provider_request_intent"
    PROVIDER_REQUEST_SEND_STARTED = "provider_request_send_started"
    PROVIDER_RESPONSE_RECEIVED = "provider_response_received"
    PROVIDER_REQUEST_FAILED = "provider_request_failed"
    PROCESS_INTENT = "process_intent"
    PROCESS_COMPLETED = "process_completed"
    CHECKPOINT_PASSED = "checkpoint_passed"
    HOST_INSPECTION_PASSED = "host_inspection_passed"
    CONTAINMENT_PASSED = "containment_passed"
    EVIDENCE_TRANSFER_PASSED = "evidence_transfer_passed"
    CLEANUP_REQUIRED = "cleanup_required"
    TERMINATION_INTENT_COMMITTED = "termination_intent_committed"
    TERMINATION_SEND_STARTED = "termination_send_started"
    TERMINATION_RESPONSE_UNKNOWN = "termination_response_unknown"
    INSTANCE_TERMINAL_PROVEN = "instance_terminal_proven"
    REGIONAL_RULESET_DELETED = "regional_ruleset_deleted"
    GLOBAL_FIREWALL_RESTORED = "global_firewall_restored"
    ARCHIVE_FINALIZED = "archive_finalized"
    ALL_CLEAN_SEALED = "all_clean_sealed"
    HIGH_SEVERITY_INCIDENT = "high_severity_incident"
    SUPERVISOR_STOPPED = "supervisor_stopped"


class SupervisorPhase(StrEnum):
    NEW = "new"
    PREFLIGHT = "preflight"
    WATCHDOG_READY = "watchdog_ready"
    FIREWALL_MUTATED = "firewall_mutated"
    LAUNCH_PREPARED = "launch_prepared"
    LAUNCH_OUTCOME_UNKNOWN = "launch_outcome_unknown"
    DISCOVERY = "discovery"
    INSTANCE_BOUND = "instance_bound"
    QUALIFYING = "qualifying"
    CLEANUP = "cleanup"
    INSTANCE_TERMINAL = "instance_terminal"
    FIREWALL_RESTORED = "firewall_restored"
    ARCHIVING = "archiving"
    CLOSED = "closed"
    INCIDENT = "incident"


@dataclass(frozen=True, slots=True)
class SupervisorState:
    phase: SupervisorPhase = SupervisorPhase.NEW
    launch_body_sha256: str | None = None
    launch_send_count: int = 0
    launch_outcome_unknown: bool = False
    marker_burned: bool = False
    owned_instance_ids: tuple[str, ...] = ()
    termination_send_ids: tuple[str, ...] = ()
    terminal_instance_ids: tuple[str, ...] = ()
    global_firewall_mutated: bool = False
    regional_ruleset_created: bool = False
    regional_ruleset_deleted: bool = False
    global_firewall_restored: bool = False
    archive_finalized: bool = False
    incident_class: str | None = None


@dataclass(frozen=True, slots=True)
class CompletionEvidence:
    """Complete success/incident eligibility required before sealing a disposition."""

    authorization_sha256: str
    plan_sha256: str
    transaction_journal_sha256: str
    watchdog_journal_sha256: str
    private_parameter_seal_sha256: str
    host_evidence_manifest_sha256: str
    containment_evidence_sha256: str
    transfer_verification_sha256: str
    provider_terminal_proven: bool
    regional_ruleset_absent: bool
    global_firewall_exactly_restored: bool
    zero_owned_residue_proven: bool
    secret_scan_passed: bool
    local_source_retained: bool
    destination_hashes_verified: bool
    archive_fsynced_and_atomically_finalized: bool
    watchdog_terminal_state: str

    def __post_init__(self) -> None:
        for value, context in (
            (self.authorization_sha256, "authorization hash"),
            (self.plan_sha256, "plan hash"),
            (self.transaction_journal_sha256, "transaction journal hash"),
            (self.watchdog_journal_sha256, "watchdog journal hash"),
            (self.private_parameter_seal_sha256, "private parameter seal hash"),
            (self.host_evidence_manifest_sha256, "host evidence manifest hash"),
            (self.containment_evidence_sha256, "containment evidence hash"),
            (self.transfer_verification_sha256, "transfer verification hash"),
        ):
            _safe_hash(value, context=context)
        if self.watchdog_terminal_state not in {"all_clean", "incident_sealed"}:
            raise L21SupervisorError("watchdog terminal evidence is absent")


def require_success_evidence(evidence: CompletionEvidence) -> None:
    required = (
        evidence.provider_terminal_proven,
        evidence.regional_ruleset_absent,
        evidence.global_firewall_exactly_restored,
        evidence.zero_owned_residue_proven,
        evidence.secret_scan_passed,
        evidence.local_source_retained,
        evidence.destination_hashes_verified,
        evidence.archive_fsynced_and_atomically_finalized,
        evidence.watchdog_terminal_state == "all_clean",
    )
    if not all(required):
        raise L21SupervisorError("success evidence eligibility is incomplete")


@dataclass(frozen=True, slots=True)
class BudgetState:
    provider_calls: int = 0
    provider_response_bytes: int = 0
    process_calls: int = 0
    process_output_bytes: int = 0
    launch_calls: int = 0
    termination_calls: int = 0
    firewall_mutation_calls: int = 0
    archive_copy_calls: int = 0
    retained_bytes: int = 0


class SharedBudget:
    """One aggregate in-memory counter used by primary and fake watchdog tests."""

    def __init__(self, state: BudgetState | None = None) -> None:
        self.state = state or BudgetState()

    def reserve_provider(
        self,
        operation: ProviderOperation,
        *,
        actor: Actor,
        response_bytes: int = 0,
    ) -> BudgetState:
        if actor is Actor.WATCHDOG and operation not in WATCHDOG_PROVIDER_ALLOWLIST:
            raise L21SupervisorError("watchdog provider operation is not cleanup-only")
        if not 0 <= response_bytes <= MAX_PROVIDER_RESPONSE_BYTES_PER_CALL:
            raise L21SupervisorError("provider response exceeded its per-call cap")
        launches = self.state.launch_calls + (operation is ProviderOperation.LAUNCH_INSTANCE)
        terminations = self.state.termination_calls + (
            operation is ProviderOperation.TERMINATE_INSTANCE
        )
        firewall_mutation = self.state.firewall_mutation_calls + (
            operation
            in {
                ProviderOperation.PATCH_GLOBAL_STRICT,
                ProviderOperation.CREATE_REGIONAL_RULESET,
                ProviderOperation.DELETE_REGIONAL_RULESET,
                ProviderOperation.RESTORE_GLOBAL_FIREWALL,
            }
        )
        updated = replace(
            self.state,
            provider_calls=self.state.provider_calls + 1,
            provider_response_bytes=self.state.provider_response_bytes + response_bytes,
            launch_calls=launches,
            termination_calls=terminations,
            firewall_mutation_calls=firewall_mutation,
        )
        if (
            updated.provider_calls > MAX_PROVIDER_CALLS
            or updated.provider_response_bytes > MAX_PROVIDER_RESPONSE_BYTES_AGGREGATE
            or updated.launch_calls > MAX_LAUNCH_CALLS
            or updated.termination_calls > MAX_TERMINATION_CALLS
            or updated.firewall_mutation_calls > MAX_FIREWALL_MUTATION_CALLS
        ):
            raise L21SupervisorError("aggregate provider budget would be exceeded")
        self.state = updated
        return updated

    def reserve_process(self, output_bytes: int) -> BudgetState:
        if not 0 <= output_bytes <= MAX_PROCESS_OUTPUT_BYTES_PER_CALL:
            raise L21SupervisorError("process output exceeded its per-call cap")
        updated = replace(
            self.state,
            process_calls=self.state.process_calls + 1,
            process_output_bytes=self.state.process_output_bytes + output_bytes,
        )
        if (
            updated.process_calls > MAX_PROCESS_CALLS
            or updated.process_output_bytes > MAX_PROCESS_OUTPUT_BYTES_AGGREGATE
        ):
            raise L21SupervisorError("aggregate process budget would be exceeded")
        self.state = updated
        return updated

    def charge_provider_response(self, response_bytes: int) -> BudgetState:
        if not 0 <= response_bytes <= MAX_PROVIDER_RESPONSE_BYTES_PER_CALL:
            raise L21SupervisorError("provider response exceeded its per-call cap")
        updated = replace(
            self.state,
            provider_response_bytes=self.state.provider_response_bytes + response_bytes,
        )
        if updated.provider_response_bytes > MAX_PROVIDER_RESPONSE_BYTES_AGGREGATE:
            raise L21SupervisorError("aggregate provider response budget would be exceeded")
        self.state = updated
        return updated

    def reserve_archive(self, retained_bytes: int) -> BudgetState:
        if not 0 <= retained_bytes <= MAX_ARCHIVE_BYTES:
            raise L21SupervisorError("archive exceeds its byte cap")
        updated = replace(
            self.state,
            archive_copy_calls=self.state.archive_copy_calls + 1,
            retained_bytes=self.state.retained_bytes + retained_bytes,
        )
        if updated.archive_copy_calls > MAX_ARCHIVE_COPY_CALLS:
            raise L21SupervisorError("archive copy count exceeded")
        self.state = updated
        return updated


class FsyncSharedBudget:
    """Cross-process aggregate counter guarded by one run-owned flock lock.

    The state is replaced atomically under the lock and the containing directory is
    fsynced.  Both primary and watchdog must use this store; the in-memory
    ``SharedBudget`` remains the deterministic test/policy primitive.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.lock_path = root / "aggregate-budget.lock"
        self.state_path = root / "aggregate-budget.json"
        self._lock_fd = os.open(
            self.lock_path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )

    @classmethod
    def create(cls, root: Path) -> FsyncSharedBudget:
        if not root.is_dir() or root.is_symlink():
            raise L21SupervisorError("budget root is not a held run-owned directory")
        instance = cls(root)
        fcntl.flock(instance._lock_fd, fcntl.LOCK_EX)
        try:
            if instance.state_path.exists():
                raise L21SupervisorError("aggregate budget identity is not fresh")
            instance._write(BudgetState())
        finally:
            fcntl.flock(instance._lock_fd, fcntl.LOCK_UN)
        return instance

    def _read(self) -> BudgetState:
        try:
            descriptor = os.open(
                self.state_path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                status = os.fstat(descriptor)
                if not stat.S_ISREG(status.st_mode) or status.st_size > 16_384:
                    raise L21SupervisorError("aggregate budget state is unsafe")
                encoded = os.read(descriptor, 16_385)
            finally:
                os.close(descriptor)
            raw = json.loads(encoded)
            if not isinstance(raw, dict) or set(raw) != set(asdict(BudgetState())):
                raise L21SupervisorError("aggregate budget state shape drifted")
            return BudgetState(**raw)
        except (OSError, json.JSONDecodeError, TypeError):
            raise L21SupervisorError("aggregate budget state is unreadable") from None

    def _write(self, state: BudgetState) -> None:
        temporary = self.root / ".aggregate-budget.next"
        encoded = canonical_bytes(asdict(state))
        descriptor = -1
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            os.write(descriptor, encoded)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.replace(temporary, self.state_path)
            parent = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except OSError:
            raise L21SupervisorError("aggregate budget state write failed") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()

    def update(self, reservation: Callable[[SharedBudget], BudgetState]) -> BudgetState:
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
        try:
            budget = SharedBudget(self._read())
            updated = reservation(budget)
            self._write(updated)
            return updated
        finally:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)

    def close(self) -> None:
        if self._lock_fd >= 0:
            os.close(self._lock_fd)
            self._lock_fd = -1


@dataclass(frozen=True, slots=True)
class JournalSnapshot:
    path: Path
    bytes: int
    events: int
    sha256: str


class FsyncTransactionJournal:
    """Exclusive, append-only, schema-validated, fsync-per-event journal."""

    def __init__(
        self,
        *,
        path: Path,
        descriptor: int,
        binding: ExecutionBinding,
        actor: Actor,
        validator: Draft202012Validator,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.path = path
        self.descriptor = descriptor
        self.binding = binding
        self.actor = actor
        self.validator = validator
        self.monotonic_ns = monotonic_ns
        self.utc_now = utc_now
        self.sequence = 1
        self.events = 0
        self.bytes_written = 0
        self.closed = False

    @classmethod
    def create(
        cls,
        repository_root: Path,
        *,
        path: Path,
        binding: ExecutionBinding,
        actor: Actor = Actor.PRIMARY,
    ) -> FsyncTransactionJournal:
        root = repository_root.resolve(strict=True)
        target = path.absolute()
        try:
            target.relative_to(root)
        except ValueError:
            raise L21SupervisorError("transaction journal escaped the repository") from None
        if not target.parent.is_dir() or target.is_symlink():
            raise L21SupervisorError("transaction journal parent is unsafe")
        try:
            schema_raw = json.loads((root / TRANSACTION_SCHEMA_PATH).read_bytes())
            validator = Draft202012Validator(schema_raw)
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            parent = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except (OSError, json.JSONDecodeError):
            raise L21SupervisorError("transaction journal creation failed") from None
        return cls(
            path=target,
            descriptor=descriptor,
            binding=binding,
            actor=actor,
            validator=validator,
        )

    def append(
        self,
        event: JournalEvent,
        *,
        operation_ordinal: int,
        request_ordinal: int | None,
        resource_alias: str,
        budget: BudgetState,
        terminal_status: str,
        elapsed_ms: int = 0,
        response_bytes: int = 0,
        sanitized_failure_class: str | None = None,
    ) -> None:
        if self.closed:
            raise L21SupervisorError("transaction journal is closed")
        if operation_ordinal < 0 or (request_ordinal is not None and request_ordinal < 1):
            raise L21SupervisorError("journal operation or request ordinal is invalid")
        if _SAFE_ALIAS.fullmatch(resource_alias) is None:
            raise L21SupervisorError("journal resource alias is unsafe")
        document = {
            "schema_version": "0.1.0",
            "run_id": self.binding.run_id,
            "plan_id": self.binding.plan_id,
            "authorization_reference": self.binding.authorization_reference,
            "actor": self.actor.value,
            "event_sequence": self.sequence,
            "event_type": event.value,
            "operation_ordinal": operation_ordinal,
            "request_ordinal": request_ordinal,
            "resource_alias": resource_alias,
            "private_parameter_seal_reference": (self.binding.private_parameter_seal_reference),
            "monotonic_timestamp_ns": self.monotonic_ns(),
            "wall_timestamp_utc": self.utc_now().isoformat().replace("+00:00", "Z"),
            "elapsed_ms": elapsed_ms,
            "response_bytes": response_bytes,
            "provider_calls_used": budget.provider_calls,
            "process_calls_used": budget.process_calls,
            "output_bytes_used": (budget.provider_response_bytes + budget.process_output_bytes),
            "terminal_status": terminal_status,
            "sanitized_failure_class": sanitized_failure_class,
        }
        errors = list(self.validator.iter_errors(document))
        if errors:
            raise L21SupervisorError("transaction journal event failed schema validation")
        encoded = canonical_bytes(document)
        if (
            len(encoded) > MAX_TRANSACTION_EVENT_BYTES
            or self.events + 1 > MAX_TRANSACTION_EVENTS
            or self.bytes_written + len(encoded) > MAX_TRANSACTION_BYTES
        ):
            raise L21SupervisorError("transaction journal capacity exceeded")
        try:
            written = os.write(self.descriptor, encoded)
            if written != len(encoded):
                raise OSError("short write")
            os.fsync(self.descriptor)
        except OSError:
            raise L21SupervisorError("transaction journal fsync failed") from None
        self.sequence += 1
        self.events += 1
        self.bytes_written += len(encoded)

    def snapshot(self) -> JournalSnapshot:
        if not self.closed:
            os.fsync(self.descriptor)
        encoded = self.path.read_bytes()
        if len(encoded) != self.bytes_written:
            raise L21SupervisorError("transaction journal byte count drifted")
        return JournalSnapshot(
            self.path,
            len(encoded),
            self.events,
            sha256_bytes(encoded),
        )

    def close(self) -> None:
        if self.descriptor >= 0:
            os.fsync(self.descriptor)
            os.close(self.descriptor)
            self.descriptor = -1
        self.closed = True


@dataclass(frozen=True, slots=True)
class ProviderCall:
    operation: ProviderOperation
    method: str
    path: str
    body: Mapping[str, object] | None = field(default=None, repr=False)

    @property
    def body_bytes(self) -> bytes | None:
        return None if self.body is None else canonical_bytes(self.body)


@dataclass(frozen=True, slots=True)
class ProviderResult:
    status: int
    content_type: str
    body: bytes = field(repr=False)
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class ProviderFailure(Exception):
    stage: str
    classification: str
    bytes_may_have_been_sent: bool


class ProviderBoundary(Protocol):
    def send(
        self,
        call: ProviderCall,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> ProviderResult: ...


_EXACT_PROVIDER_ROUTES: Final[dict[ProviderOperation, tuple[str, str]]] = {
    ProviderOperation.LIST_INSTANCE_TYPES: ("GET", "/api/v1/instance-types"),
    ProviderOperation.LIST_IMAGES: ("GET", "/api/v1/images"),
    ProviderOperation.LIST_REGIONS: ("GET", "/api/v1/regions"),
    ProviderOperation.LIST_SSH_KEYS: ("GET", "/api/v1/ssh-keys"),
    ProviderOperation.LIST_FIREWALL_RULESETS: ("GET", "/api/v1/firewall-rulesets"),
    ProviderOperation.GET_GLOBAL_FIREWALL: ("GET", "/api/v1/firewall-rulesets/global"),
    ProviderOperation.LIST_INSTANCES: ("GET", "/api/v1/instances"),
    ProviderOperation.PATCH_GLOBAL_STRICT: ("PATCH", "/api/v1/firewall-rulesets/global"),
    ProviderOperation.VERIFY_GLOBAL_STRICT: ("GET", "/api/v1/firewall-rulesets/global"),
    ProviderOperation.CREATE_REGIONAL_RULESET: ("POST", "/api/v1/firewall-rulesets"),
    ProviderOperation.LAUNCH_INSTANCE: ("POST", "/api/v1/instance-operations/launch"),
    ProviderOperation.TERMINATE_INSTANCE: (
        "POST",
        "/api/v1/instance-operations/terminate",
    ),
    ProviderOperation.RESTORE_GLOBAL_FIREWALL: (
        "PATCH",
        "/api/v1/firewall-rulesets/global",
    ),
    ProviderOperation.VERIFY_GLOBAL_RESTORED: (
        "GET",
        "/api/v1/firewall-rulesets/global",
    ),
}
_DYNAMIC_ROUTES: Final[dict[ProviderOperation, tuple[str, re.Pattern[str]]]] = {
    ProviderOperation.GET_REGIONAL_RULESET: (
        "GET",
        re.compile(r"^/api/v1/firewall-rulesets/[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$"),
    ),
    ProviderOperation.DELETE_REGIONAL_RULESET: (
        "DELETE",
        re.compile(r"^/api/v1/firewall-rulesets/[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$"),
    ),
    ProviderOperation.VERIFY_REGIONAL_ABSENT: (
        "GET",
        re.compile(r"^/api/v1/firewall-rulesets/[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$"),
    ),
    ProviderOperation.GET_INSTANCE_DETAIL: (
        "GET",
        re.compile(r"^/api/v1/instances/[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$"),
    ),
}


def validate_provider_call(call: ProviderCall) -> None:
    """Reject any method/path/body outside the closed provider policy."""

    expected = _EXACT_PROVIDER_ROUTES.get(call.operation)
    if expected is not None:
        if (call.method, call.path) != expected:
            raise L21SupervisorError("provider route differs from its exact operation")
    else:
        dynamic = _DYNAMIC_ROUTES.get(call.operation)
        if dynamic is None or call.method != dynamic[0] or dynamic[1].fullmatch(call.path) is None:
            raise L21SupervisorError("provider dynamic route is unresolved or unsafe")
    if "?" in call.path or "#" in call.path or not call.path.startswith("/api/v1/"):
        raise L21SupervisorError("provider route contains query/fragment or wrong base")
    body_bytes = call.body_bytes
    if call.method in {"POST", "PATCH"} and body_bytes is None:
        raise L21SupervisorError("provider mutation lacks an exact body")
    if call.method in {"GET", "DELETE"} and body_bytes is not None:
        raise L21SupervisorError("provider read/delete unexpectedly carries a body")
    if body_bytes is not None and len(body_bytes) > MAX_PROVIDER_REQUEST_BODY_BYTES:
        raise L21SupervisorError("provider body exceeds its cap")


class InProcessLambdaBoundary:
    """Retired concrete HTTPS boundary; only fake boundaries remain usable."""

    def __init__(
        self,
        *,
        ssl_context: ssl.SSLContext | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ssl_context = ssl_context or ssl.create_default_context()
        self.clock = clock

    def send(
        self,
        call: ProviderCall,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> ProviderResult:
        reject_retired_live_effector("HTTPS boundary")
        validate_provider_call(call)
        if (
            not credential
            or len(credential) > 4_096
            or any(character in credential for character in ("\r", "\n", "\x00"))
        ):
            raise ProviderFailure("secret_source", "secret_malformed", False)
        if not 0 < timeout_seconds <= INITIAL_LAUNCH_RESPONSE_SECONDS:
            raise ProviderFailure("deadline", "deadline_invalid", False)
        started = self.clock()
        connection = http.client.HTTPSConnection(
            API_HOST,
            443,
            timeout=timeout_seconds,
            context=self.ssl_context,
        )
        encoded = call.body_bytes
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {credential}",
            "User-Agent": "giclab-t07-gate-l2-v2/1",
        }
        if encoded is not None:
            headers["Content-Type"] = "application/json"
        try:
            try:
                connection.request(call.method, call.path, body=encoded, headers=headers)
            except (OSError, ssl.SSLError, http.client.HTTPException):
                raise ProviderFailure("request_write", "request_write_failure", True) from None
            try:
                response = connection.getresponse()
            except (OSError, ssl.SSLError, http.client.HTTPException):
                raise ProviderFailure(
                    "response_headers", "response_headers_failure", True
                ) from None
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].casefold()
            if 300 <= response.status <= 399:
                raise ProviderFailure("redirect", "http_redirect", True)
            if content_type != "application/json":
                raise ProviderFailure("content_type", "unexpected_content_type", True)
            body = bytearray()
            while True:
                try:
                    chunk = response.read(65_536)
                except (OSError, ssl.SSLError, http.client.HTTPException):
                    raise ProviderFailure("response_body", "response_body_failure", True) from None
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > MAX_PROVIDER_RESPONSE_BYTES_PER_CALL:
                    raise ProviderFailure("response_size", "response_too_large", True)
            elapsed_ms = max(0, int((self.clock() - started) * 1_000))
            return ProviderResult(response.status, content_type, bytes(body), elapsed_ms)
        finally:
            with contextlib.suppress(OSError):
                connection.close()


@dataclass(frozen=True, slots=True)
class ProcessCall:
    operation: ProcessOperation
    argv: tuple[str, ...] = field(repr=False)
    timeout_seconds: int
    max_output_bytes: int
    environment: Mapping[str, str] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: bytes = field(repr=False)
    stderr: bytes = field(repr=False)
    elapsed_ms: int


class ProcessBoundary(Protocol):
    def run(self, call: ProcessCall) -> ProcessResult: ...


_PROCESS_EXECUTABLES: Final[dict[ProcessOperation, frozenset[str]]] = {
    ProcessOperation.TCP_READINESS: frozenset({"/usr/bin/nc"}),
    ProcessOperation.SSH_AGENT_INSPECTION: frozenset({"/usr/bin/ssh-add"}),
    ProcessOperation.SSH_KEYSCAN: frozenset({"/usr/bin/ssh-keyscan"}),
    ProcessOperation.SSH_HOST_INSPECTION: frozenset({"/usr/bin/ssh"}),
    ProcessOperation.SSH_TRANSFER: frozenset({"/usr/bin/scp", "/usr/bin/ssh"}),
    ProcessOperation.REMOTE_DOCKER: frozenset({"/usr/bin/ssh"}),
    ProcessOperation.CONTAINMENT_FIXTURE: frozenset({"/usr/bin/ssh"}),
    ProcessOperation.EVIDENCE_VERIFY: frozenset({"/usr/bin/shasum"}),
}
_ALLOWED_PROCESS_ENVIRONMENT: Final = frozenset({"PATH", "LANG", "LC_ALL", "SSH_AUTH_SOCK"})


def validate_process_call(call: ProcessCall) -> None:
    if (
        not call.argv
        or call.argv[0] not in _PROCESS_EXECUTABLES[call.operation]
        or any(not argument or "\x00" in argument for argument in call.argv)
        or not 1 <= call.timeout_seconds <= QUALIFICATION_PROVIDER_WALL_SECONDS
        or not 0 < call.max_output_bytes <= MAX_PROCESS_OUTPUT_BYTES_PER_CALL
    ):
        raise L21SupervisorError("process call is outside the shell-free policy")
    if not set(call.environment).issubset(_ALLOWED_PROCESS_ENVIRONMENT):
        raise L21SupervisorError("process environment contains an unapproved name")
    if any(
        key != "SSH_AUTH_SOCK" and ("KEY" in key or "TOKEN" in key or "SECRET" in key)
        for key in call.environment
    ):
        raise L21SupervisorError("process environment contains credential material")


class ShellFreeProcessBoundary:
    """Retired concrete process boundary; only fake boundaries remain usable."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock

    def run(self, call: ProcessCall) -> ProcessResult:
        reject_retired_live_effector("process boundary")
        validate_process_call(call)
        started = self.clock()
        environment = {key: value for key, value in call.environment.items()}
        process = subprocess.Popen(
            call.argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            start_new_session=True,
            env=environment,
        )
        assert process.stdout is not None and process.stderr is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        chunks: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
        deadline = started + call.timeout_seconds
        try:
            while selector.get_map():
                remaining = deadline - self.clock()
                if remaining <= 0:
                    raise L21SupervisorError("process deadline exceeded")
                events = selector.select(min(remaining, 0.25))
                for key, _mask in events:
                    stream_name = str(key.data)
                    chunk = os.read(key.fd, 65_536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    chunks[stream_name].extend(chunk)
                    if sum(len(value) for value in chunks.values()) > call.max_output_bytes:
                        raise L21SupervisorError("process output cap exceeded")
            returncode = process.wait(timeout=max(0.01, deadline - self.clock()))
        except (L21SupervisorError, subprocess.TimeoutExpired):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
            raise L21SupervisorError("bounded process failed or exceeded a cap") from None
        finally:
            selector.close()
        return ProcessResult(
            returncode=returncode,
            stdout=bytes(chunks["stdout"]),
            stderr=bytes(chunks["stderr"]),
            elapsed_ms=max(0, int((self.clock() - started) * 1_000)),
        )


def parse_json_response(result: ProviderResult) -> Mapping[str, object]:
    if result.content_type != "application/json":
        raise L21SupervisorError("provider response content type drifted")
    try:
        document = json.loads(result.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise L21SupervisorError("provider response is malformed JSON") from None
    if not isinstance(document, Mapping) or any(not isinstance(key, str) for key in document):
        raise L21SupervisorError("provider response is not an object")
    return document


def parse_launch_instance_ids(result: ProviderResult) -> tuple[str, ...]:
    """Require exactly one ID for a successful launch response."""

    document = parse_json_response(result)
    raw_data = document.get("data", document)
    if not isinstance(raw_data, Mapping):
        raise L21SupervisorError("launch response data is not an object")
    raw_ids = raw_data.get("instance_ids")
    if (
        not isinstance(raw_ids, list)
        or len(raw_ids) != 1
        or not isinstance(raw_ids[0], str)
        or _SAFE_PROVIDER_ID.fullmatch(raw_ids[0]) is None
    ):
        raise L21SupervisorError("launch response did not contain exactly one safe ID")
    return (raw_ids[0],)


def parse_instance_list(result: ProviderResult) -> Sequence[Mapping[str, object]]:
    document = parse_json_response(result)
    raw_data = document.get("data")
    if not isinstance(raw_data, list) or any(not isinstance(item, Mapping) for item in raw_data):
        raise L21SupervisorError("instance list response shape drifted")
    return raw_data


def parse_instance_detail(result: ProviderResult) -> Mapping[str, object]:
    document = parse_json_response(result)
    raw_data = document.get("data")
    if not isinstance(raw_data, Mapping):
        raise L21SupervisorError("instance detail response shape drifted")
    return raw_data


def validate_launch_body(body: Mapping[str, object], expected: ExpectedOwnedInstance) -> bytes:
    """Require one exact no-filesystem launch body and freeze its bytes."""

    exact_keys = {
        "region_name",
        "instance_type_name",
        "ssh_key_names",
        "file_system_names",
        "file_system_mounts",
        "name",
        "hostname",
        "image",
        "tags",
        "firewall_rulesets",
    }
    if set(body) != exact_keys:
        raise L21SupervisorError("launch body field set drifted")
    if (
        body.get("region_name") != expected.region_name
        or body.get("instance_type_name") != expected.instance_type_name
        or body.get("ssh_key_names") != list(expected.ssh_key_names)
        or body.get("file_system_names") != []
        or body.get("file_system_mounts") != []
        or body.get("name") != expected.marker.name
        or body.get("hostname") != expected.marker.hostname
        or body.get("tags") != expected.marker.provider_tags()
        or body.get("firewall_rulesets") != [{"id": expected.firewall_ruleset_ids[0]}]
        or not isinstance(body.get("image"), Mapping)
    ):
        raise L21SupervisorError("launch body differs from its private exact bindings")
    image = body["image"]
    assert isinstance(image, Mapping)
    if set(image) != {"id"} or not isinstance(image.get("id"), str):
        raise L21SupervisorError("launch image is not one exact private ID")
    encoded = canonical_bytes(body)
    if len(encoded) > MAX_PROVIDER_REQUEST_BODY_BYTES:
        raise L21SupervisorError("launch body exceeds its cap")
    return encoded


def validate_recovery_decision(document: Mapping[str, object]) -> None:
    """Require every separately reviewed residual-risk decision before execution."""

    expected_keys = {
        "schema_version",
        "decision_id",
        "approve_unique_marker_discovery",
        "approve_terminate_all_exact_full_marker_matches",
        "approve_no_launch_retry_after_possible_send",
        "approve_manual_console_fallback",
        "acknowledge_provider_control_plane_outage_residual_risk",
        "residual_risk_statement",
        "manual_console_fallback_operator",
        "manual_console_response_window_seconds",
        "decision_nonce",
    }
    if set(document) != expected_keys:
        raise L21SupervisorError("launch-recovery decision field set drifted")
    required_true = {
        "approve_unique_marker_discovery",
        "approve_terminate_all_exact_full_marker_matches",
        "approve_no_launch_retry_after_possible_send",
        "approve_manual_console_fallback",
        "acknowledge_provider_control_plane_outage_residual_risk",
    }
    if any(document.get(key) is not True for key in required_true):
        raise L21SupervisorError("a launch-recovery approval or acknowledgment is absent")
    if (
        document.get("schema_version") != "0.1.0"
        or document.get("decision_id") != "T07-L2-LAUNCH-RECOVERY-DECISION-V1"
        or document.get("residual_risk_statement") != RESIDUAL_RISK_STATEMENT
        or document.get("manual_console_fallback_operator") != "user"
        or document.get("manual_console_response_window_seconds") != MANUAL_CONSOLE_RESPONSE_SECONDS
        or not isinstance(document.get("decision_nonce"), str)
        or re.fullmatch(r"[a-f0-9]{64}", str(document.get("decision_nonce"))) is None
    ):
        raise L21SupervisorError("manual fallback or decision nonce differs from contract")


class GateL2Supervisor:
    """Offline Gate L2 launch/recovery policy state machine.

    Network and process effects are available only through injected policy boundaries.
    Methods journal modeled before/after semantics and update a process-local budget.
    No reviewed runner composes every method into an authoritative sequence or shares
    one budget with a watchdog; unit tests therefore use only fakes and establish no
    live execution authority.
    """

    def __init__(
        self,
        *,
        binding: ExecutionBinding,
        expected: ExpectedOwnedInstance,
        journal: FsyncTransactionJournal,
        provider: ProviderBoundary,
        process: ProcessBoundary,
        credential: str,
        budget: SharedBudget | None = None,
    ) -> None:
        if journal.binding != binding or journal.actor is not Actor.PRIMARY:
            raise L21SupervisorError("journal binding or actor differs from supervisor")
        if not credential or len(credential) > 4_096:
            raise L21SupervisorError("provider credential is unavailable or malformed")
        self.binding = binding
        self.expected = expected
        self.journal = journal
        self.provider = provider
        self.process = process
        self.credential = credential
        self.budget = budget or SharedBudget()
        self.state = SupervisorState(phase=SupervisorPhase.PREFLIGHT)
        self.operation_ordinal = 0
        self.request_ordinal = 0
        self.started_monotonic = time.monotonic()
        self._journal(
            JournalEvent.SUPERVISOR_STARTED,
            resource_alias="gate-l2-run",
            terminal_status="in_progress",
        )

    def _journal(
        self,
        event: JournalEvent,
        *,
        resource_alias: str,
        terminal_status: str,
        request_ordinal: int | None = None,
        elapsed_ms: int = 0,
        response_bytes: int = 0,
        failure: str | None = None,
    ) -> None:
        self.operation_ordinal += 1
        self.journal.append(
            event,
            operation_ordinal=self.operation_ordinal,
            request_ordinal=request_ordinal,
            resource_alias=resource_alias,
            budget=self.budget.state,
            terminal_status=terminal_status,
            elapsed_ms=elapsed_ms,
            response_bytes=response_bytes,
            sanitized_failure_class=failure,
        )

    def mark_preflight_verified(self, discovery: DiscoveryResult) -> None:
        if self.state.phase is not SupervisorPhase.PREFLIGHT:
            raise L21SupervisorError("preflight may advance exactly once")
        if discovery.kind is not DiscoveryKind.ZERO_MATCHES:
            raise L21SupervisorError("preflight contains a complete or partial marker match")
        self._journal(
            JournalEvent.PREFLIGHT_INVENTORY_VERIFIED,
            resource_alias="preflight-inventory",
            terminal_status="passed",
        )

    def request_provider(
        self,
        call: ProviderCall,
        *,
        resource_alias: str,
        expected_statuses: frozenset[int] = frozenset({200}),
    ) -> ProviderResult:
        """Make one observed non-launch/non-termination call through the sole boundary."""

        validate_provider_call(call)
        if call.operation in {
            ProviderOperation.LAUNCH_INSTANCE,
            ProviderOperation.TERMINATE_INSTANCE,
        }:
            raise L21SupervisorError("launch and termination require their irreversible paths")
        self.request_ordinal += 1
        request_ordinal = self.request_ordinal
        self.budget.reserve_provider(call.operation, actor=Actor.PRIMARY)
        self._journal(
            JournalEvent.PROVIDER_REQUEST_INTENT,
            resource_alias=resource_alias,
            terminal_status="committed",
            request_ordinal=request_ordinal,
        )
        self._journal(
            JournalEvent.PROVIDER_REQUEST_SEND_STARTED,
            resource_alias=resource_alias,
            terminal_status="outcome_unknown",
            request_ordinal=request_ordinal,
        )
        try:
            result = self.provider.send(
                call,
                credential=self.credential,
                timeout_seconds=INITIAL_LAUNCH_RESPONSE_SECONDS,
            )
        except ProviderFailure as failure:
            self._journal(
                JournalEvent.PROVIDER_REQUEST_FAILED,
                resource_alias=resource_alias,
                terminal_status=(
                    "outcome_unknown" if failure.bytes_may_have_been_sent else "not_sent"
                ),
                request_ordinal=request_ordinal,
                failure=failure.classification,
            )
            raise L21SupervisorError("provider request failed with a sanitized class") from None
        self.budget.charge_provider_response(len(result.body))
        self._journal(
            JournalEvent.PROVIDER_RESPONSE_RECEIVED,
            resource_alias=resource_alias,
            terminal_status="observed",
            request_ordinal=request_ordinal,
            elapsed_ms=result.elapsed_ms,
            response_bytes=len(result.body),
        )
        if result.status not in expected_statuses:
            raise L21SupervisorError("provider status differs from its exact operation")
        return result

    def mark_watchdog_ready(self) -> None:
        if self.state.phase is not SupervisorPhase.PREFLIGHT:
            raise L21SupervisorError("watchdog readiness order drifted")
        self.state = replace(self.state, phase=SupervisorPhase.WATCHDOG_READY)
        self._journal(
            JournalEvent.WATCHDOG_READY,
            resource_alias="cleanup-watchdog",
            terminal_status="ready",
        )

    def mark_firewall_strict(self) -> None:
        if self.state.phase is not SupervisorPhase.WATCHDOG_READY:
            raise L21SupervisorError("firewall mutation started before watchdog readiness")
        self.state = replace(
            self.state,
            phase=SupervisorPhase.FIREWALL_MUTATED,
            global_firewall_mutated=True,
            regional_ruleset_created=True,
        )
        for event, alias in (
            (JournalEvent.FIREWALL_SNAPSHOT_SEALED, "global-firewall"),
            (JournalEvent.GLOBAL_FIREWALL_STRICT_VERIFIED, "global-firewall"),
            (JournalEvent.REGIONAL_RULESET_STRICT_VERIFIED, "owned-regional-ruleset"),
        ):
            self._journal(event, resource_alias=alias, terminal_status="passed")

    def seal_launch_body(self, body: Mapping[str, object]) -> str:
        if self.state.phase is not SupervisorPhase.FIREWALL_MUTATED:
            raise L21SupervisorError("launch body sealing order drifted")
        encoded = validate_launch_body(body, self.expected)
        digest = sha256_bytes(encoded)
        self.state = replace(
            self.state,
            phase=SupervisorPhase.LAUNCH_PREPARED,
            launch_body_sha256=digest,
        )
        self._journal(
            JournalEvent.LAUNCH_BODY_SEALED,
            resource_alias="launch-body",
            terminal_status="sealed",
            response_bytes=len(encoded),
        )
        return digest

    def launch_send_started(self, body: Mapping[str, object]) -> None:
        encoded = validate_launch_body(body, self.expected)
        if (
            self.state.phase is not SupervisorPhase.LAUNCH_PREPARED
            or self.state.launch_send_count != 0
            or self.state.marker_burned
            or sha256_bytes(encoded) != self.state.launch_body_sha256
        ):
            raise L21SupervisorError("launch body changed or launch/marker was already used")
        self._journal(
            JournalEvent.LAUNCH_INTENT_COMMITTED,
            resource_alias="owned-launch",
            terminal_status="committed",
        )
        self.request_ordinal += 1
        self.budget.reserve_provider(ProviderOperation.LAUNCH_INSTANCE, actor=Actor.PRIMARY)
        self.state = replace(
            self.state,
            phase=SupervisorPhase.LAUNCH_OUTCOME_UNKNOWN,
            launch_send_count=1,
            marker_burned=True,
            launch_outcome_unknown=True,
        )
        self._journal(
            JournalEvent.LAUNCH_SEND_STARTED,
            resource_alias="owned-launch",
            terminal_status="outcome_unknown",
            request_ordinal=self.request_ordinal,
        )

    def execute_launch(self, body: Mapping[str, object]) -> tuple[str, ...] | None:
        """Send the launch exactly once and enter discovery on every post-send ambiguity."""

        # The body and state are fully validated before the durable send-start event.
        validate_launch_body(body, self.expected)
        self.launch_send_started(body)
        call = ProviderCall(
            ProviderOperation.LAUNCH_INSTANCE,
            "POST",
            "/api/v1/instance-operations/launch",
            body,
        )
        validate_provider_call(call)
        try:
            result = self.provider.send(
                call,
                credential=self.credential,
                timeout_seconds=INITIAL_LAUNCH_RESPONSE_SECONDS,
            )
        except ProviderFailure as failure:
            self.record_launch_unknown(failure_class=failure.classification)
            return None
        except Exception:
            self.record_launch_unknown(failure_class="unknown_after_send")
            return None
        self.budget.charge_provider_response(len(result.body))
        return self.record_launch_response(result)

    def record_launch_response(self, result: ProviderResult) -> tuple[str, ...] | None:
        if self.state.phase is not SupervisorPhase.LAUNCH_OUTCOME_UNKNOWN:
            raise L21SupervisorError("launch response has no matching possible send")
        self._journal(
            JournalEvent.LAUNCH_RESPONSE_RECEIVED,
            resource_alias="owned-launch",
            terminal_status="observed",
            request_ordinal=self.request_ordinal,
            elapsed_ms=result.elapsed_ms,
            response_bytes=len(result.body),
        )
        if result.status == 200:
            ids = parse_launch_instance_ids(result)
            self._journal(
                JournalEvent.LAUNCH_RESPONSE_VALIDATED,
                resource_alias="owned-launch",
                terminal_status="valid",
                request_ordinal=self.request_ordinal,
            )
            return ids
        if 400 <= result.status <= 599:
            self.state = replace(self.state, phase=SupervisorPhase.DISCOVERY)
            self._journal(
                JournalEvent.DISCOVERY_STARTED,
                resource_alias="owned-launch",
                terminal_status="confirmation_required",
                failure=f"http_{result.status}",
            )
            return None
        raise L21SupervisorError("launch response status is outside the closed policy")

    def record_launch_unknown(self, *, failure_class: str) -> None:
        if self.state.phase is not SupervisorPhase.LAUNCH_OUTCOME_UNKNOWN:
            raise L21SupervisorError("unknown launch outcome has no possible send")
        self.state = replace(self.state, phase=SupervisorPhase.DISCOVERY)
        self._journal(
            JournalEvent.LAUNCH_RESPONSE_UNKNOWN_AFTER_SEND,
            resource_alias="owned-launch",
            terminal_status="outcome_unknown",
            request_ordinal=self.request_ordinal,
            failure=failure_class,
        )
        self._journal(
            JournalEvent.DISCOVERY_STARTED,
            resource_alias="owned-launch",
            terminal_status="discovery_only",
        )

    def bind_candidate_detail(
        self,
        *,
        candidate_id: str,
        detail: Mapping[str, object],
    ) -> None:
        if self.state.phase not in {
            SupervisorPhase.LAUNCH_OUTCOME_UNKNOWN,
            SupervisorPhase.DISCOVERY,
        }:
            raise L21SupervisorError("owned instance binding order drifted")
        try:
            revalidate_owned_instance_detail(
                detail,
                expected_instance_id=candidate_id,
                expected=self.expected,
            )
        except OwnershipContractError:
            self.raise_incident("owned_instance_conflicting_details")
            raise L21SupervisorError("candidate detail failed full ownership") from None
        self.state = replace(
            self.state,
            phase=SupervisorPhase.INSTANCE_BOUND,
            launch_outcome_unknown=False,
            owned_instance_ids=(candidate_id,),
        )
        self._journal(
            JournalEvent.OWNED_INSTANCE_BOUND,
            resource_alias="owned-instance",
            terminal_status="bound",
        )

    def apply_discovery(self, result: DiscoveryResult, *, approve_duplicates: bool) -> None:
        if self.state.phase is not SupervisorPhase.DISCOVERY:
            raise L21SupervisorError("discovery result arrived outside discovery")
        if result.kind is DiscoveryKind.ZERO_MATCHES:
            self._journal(
                JournalEvent.OWNED_INSTANCE_NOT_YET_VISIBLE,
                resource_alias="owned-launch",
                terminal_status="continue_discovery",
            )
            return
        if result.kind in {DiscoveryKind.PARTIAL_MARKER, DiscoveryKind.CONFLICTING_DETAILS}:
            self.raise_incident(result.kind.value)
            return
        if result.kind is DiscoveryKind.MULTIPLE_FULL_MATCHES:
            if not approve_duplicates or not (
                1 < len(result.full_match_ids) <= MAX_OWNED_INSTANCE_IDS
            ):
                self.raise_incident("provider_duplicate_owned_instances")
                return
            self.state = replace(self.state, owned_instance_ids=result.full_match_ids)
            self._journal(
                JournalEvent.OWNED_INSTANCE_AMBIGUOUS,
                resource_alias="owned-instances",
                terminal_status="exact_full_matches_require_detail_revalidation",
            )
            return
        if result.kind is DiscoveryKind.ONE_FULL_MATCH:
            self._journal(
                JournalEvent.OWNED_INSTANCE_DISCOVERED,
                resource_alias="owned-instance",
                terminal_status="detail_revalidation_required",
            )
            return
        raise L21SupervisorError("discovery result is outside the closed enum")

    def execute_discovery_list(self) -> DiscoveryResult:
        if self.state.phase is not SupervisorPhase.DISCOVERY:
            raise L21SupervisorError("instance discovery call is outside discovery")
        result = self.request_provider(
            ProviderCall(
                ProviderOperation.LIST_INSTANCES,
                "GET",
                "/api/v1/instances",
            ),
            resource_alias="owned-launch",
        )
        return classify_discovery(parse_instance_list(result), self.expected)

    def execute_candidate_detail(self, candidate_id: str) -> Mapping[str, object]:
        if self.state.phase not in {
            SupervisorPhase.LAUNCH_OUTCOME_UNKNOWN,
            SupervisorPhase.DISCOVERY,
            SupervisorPhase.CLEANUP,
        }:
            raise L21SupervisorError("instance detail call order drifted")
        if _SAFE_PROVIDER_ID.fullmatch(candidate_id) is None:
            raise L21SupervisorError("candidate ID is unsafe")
        result = self.request_provider(
            ProviderCall(
                ProviderOperation.GET_INSTANCE_DETAIL,
                "GET",
                f"/api/v1/instances/{candidate_id}",
            ),
            resource_alias="owned-instance",
        )
        return parse_instance_detail(result)

    def begin_qualification(self) -> None:
        if self.state.phase is not SupervisorPhase.INSTANCE_BOUND:
            raise L21SupervisorError("qualification lacks one revalidated owned instance")
        self.state = replace(self.state, phase=SupervisorPhase.QUALIFYING)

    def run_process(self, call: ProcessCall, *, alias: str) -> ProcessResult:
        if self.state.phase is not SupervisorPhase.QUALIFYING:
            raise L21SupervisorError("process action is outside qualification")
        validate_process_call(call)
        self._journal(
            JournalEvent.PROCESS_INTENT,
            resource_alias=alias,
            terminal_status="committed",
        )
        result = self.process.run(call)
        output_bytes = len(result.stdout) + len(result.stderr)
        self.budget.reserve_process(output_bytes)
        if result.returncode != 0:
            self.require_cleanup("qualification_process_failed")
            raise L21SupervisorError("qualification process returned nonzero")
        self._journal(
            JournalEvent.PROCESS_COMPLETED,
            resource_alias=alias,
            terminal_status="passed",
            elapsed_ms=result.elapsed_ms,
            response_bytes=output_bytes,
        )
        return result

    def require_cleanup(self, failure_class: str | None = None) -> None:
        if not self.state.global_firewall_mutated:
            raise L21SupervisorError("cleanup transition has no prior mutation")
        if self.state.phase is SupervisorPhase.CLOSED:
            raise L21SupervisorError("closed transaction cannot reenter cleanup")
        self.state = replace(self.state, phase=SupervisorPhase.CLEANUP)
        self._journal(
            JournalEvent.CLEANUP_REQUIRED,
            resource_alias="gate-l2-run",
            terminal_status="cleanup_required",
            failure=failure_class,
        )

    def record_termination_send(self, instance_id: str) -> None:
        if self.state.phase is not SupervisorPhase.CLEANUP:
            raise L21SupervisorError("termination is outside cleanup")
        if (
            instance_id not in self.state.owned_instance_ids
            or instance_id in self.state.termination_send_ids
        ):
            raise L21SupervisorError("termination target is not a fresh exact owned ID")
        self.budget.reserve_provider(ProviderOperation.TERMINATE_INSTANCE, actor=Actor.PRIMARY)
        self.request_ordinal += 1
        self._journal(
            JournalEvent.TERMINATION_INTENT_COMMITTED,
            resource_alias="owned-instance",
            terminal_status="committed",
            request_ordinal=self.request_ordinal,
        )
        self.state = replace(
            self.state,
            termination_send_ids=(*self.state.termination_send_ids, instance_id),
        )
        self._journal(
            JournalEvent.TERMINATION_SEND_STARTED,
            resource_alias="owned-instance",
            terminal_status="outcome_unknown",
            request_ordinal=self.request_ordinal,
        )

    def execute_termination(self, instance_id: str) -> ProviderResult | None:
        """Send one exact-ID termination once; unknown response is resolved by polling."""

        self.record_termination_send(instance_id)
        call = ProviderCall(
            ProviderOperation.TERMINATE_INSTANCE,
            "POST",
            "/api/v1/instance-operations/terminate",
            {"instance_ids": [instance_id]},
        )
        validate_provider_call(call)
        try:
            result = self.provider.send(
                call,
                credential=self.credential,
                timeout_seconds=INITIAL_LAUNCH_RESPONSE_SECONDS,
            )
        except ProviderFailure as failure:
            self._journal(
                JournalEvent.TERMINATION_RESPONSE_UNKNOWN,
                resource_alias="owned-instance",
                terminal_status="poll_terminal_without_resend",
                request_ordinal=self.request_ordinal,
                failure=failure.classification,
            )
            return None
        except Exception:
            self._journal(
                JournalEvent.TERMINATION_RESPONSE_UNKNOWN,
                resource_alias="owned-instance",
                terminal_status="poll_terminal_without_resend",
                request_ordinal=self.request_ordinal,
                failure="unknown_after_send",
            )
            return None
        self.budget.charge_provider_response(len(result.body))
        self._journal(
            JournalEvent.PROVIDER_RESPONSE_RECEIVED,
            resource_alias="owned-instance",
            terminal_status="termination_response_observed",
            request_ordinal=self.request_ordinal,
            elapsed_ms=result.elapsed_ms,
            response_bytes=len(result.body),
        )
        if result.status != 200:
            raise L21SupervisorError("termination response status drifted")
        return result

    def record_terminal(self, instance_id: str, status: str) -> None:
        if self.state.phase is not SupervisorPhase.CLEANUP:
            raise L21SupervisorError("terminal proof is outside cleanup")
        if instance_id not in self.state.owned_instance_ids:
            raise L21SupervisorError("terminal proof does not bind an owned ID")
        if status not in {"terminated", "absent_after_termination"}:
            raise L21SupervisorError("instance status is not terminal/nonbillable proof")
        terminal_ids = tuple(dict.fromkeys((*self.state.terminal_instance_ids, instance_id)))
        phase = (
            SupervisorPhase.INSTANCE_TERMINAL
            if set(terminal_ids) == set(self.state.owned_instance_ids)
            else SupervisorPhase.CLEANUP
        )
        self.state = replace(self.state, phase=phase, terminal_instance_ids=terminal_ids)
        self._journal(
            JournalEvent.INSTANCE_TERMINAL_PROVEN,
            resource_alias="owned-instance",
            terminal_status=status,
        )

    def record_firewall_restored(self) -> None:
        if self.state.phase is not SupervisorPhase.INSTANCE_TERMINAL or set(
            self.state.terminal_instance_ids
        ) != set(self.state.owned_instance_ids):
            raise L21SupervisorError("firewall restoration requires all terminal proofs")
        self.state = replace(
            self.state,
            phase=SupervisorPhase.FIREWALL_RESTORED,
            regional_ruleset_deleted=True,
            global_firewall_restored=True,
        )
        self._journal(
            JournalEvent.REGIONAL_RULESET_DELETED,
            resource_alias="owned-regional-ruleset",
            terminal_status="absent",
        )
        self._journal(
            JournalEvent.GLOBAL_FIREWALL_RESTORED,
            resource_alias="global-firewall",
            terminal_status="exactly_restored",
        )

    def record_archive_finalized(self, retained_bytes: int) -> None:
        if self.state.phase is not SupervisorPhase.FIREWALL_RESTORED:
            raise L21SupervisorError("archive cannot finalize before provider cleanup")
        self.budget.reserve_archive(retained_bytes)
        self.state = replace(
            self.state,
            phase=SupervisorPhase.ARCHIVING,
            archive_finalized=True,
        )
        self._journal(
            JournalEvent.ARCHIVE_FINALIZED,
            resource_alias="sealed-archive",
            terminal_status="source_destination_verified",
            response_bytes=retained_bytes,
        )

    def close_success(self, evidence: CompletionEvidence) -> None:
        require_success_evidence(evidence)
        if (
            self.state.phase is not SupervisorPhase.ARCHIVING
            or not self.state.archive_finalized
            or not self.state.regional_ruleset_deleted
            or not self.state.global_firewall_restored
            or set(self.state.terminal_instance_ids) != set(self.state.owned_instance_ids)
        ):
            raise L21SupervisorError("success evidence is incomplete")
        self.state = replace(self.state, phase=SupervisorPhase.CLOSED)
        self._journal(
            JournalEvent.ALL_CLEAN_SEALED,
            resource_alias="gate-l2-run",
            terminal_status="success",
        )
        self._journal(
            JournalEvent.SUPERVISOR_STOPPED,
            resource_alias="gate-l2-run",
            terminal_status="closed",
        )

    def raise_incident(self, incident_class: str) -> None:
        if not incident_class or len(incident_class) > 96:
            raise L21SupervisorError("incident class is invalid")
        self.state = replace(
            self.state,
            phase=SupervisorPhase.INCIDENT,
            incident_class=incident_class,
        )
        self._journal(
            JournalEvent.HIGH_SEVERITY_INCIDENT,
            resource_alias="gate-l2-run",
            terminal_status="possible_orphaned_launch",
            failure=incident_class,
        )

    def project_private_provider_evidence(
        self, document: Mapping[str, object]
    ) -> dict[str, object]:
        """Retain private operational fields without ever copying Jupyter secrets."""

        allowed = {
            "id",
            "name",
            "hostname",
            "status",
            "region",
            "instance_type",
            "ssh_key_names",
            "firewall_rulesets",
            "file_system_names",
            "file_system_mounts",
            "tags",
            "ip",
            "private_ip",
        }
        return {key: document[key] for key in sorted(set(document) & allowed)}

    def public_evidence_projection(self) -> dict[str, object]:
        """Return only aliases, counters, state and hash-safe public metadata."""

        return {
            "schema_version": "0.1.0",
            "plan_id": self.binding.plan_id,
            "run_id": self.binding.run_id,
            "repository_commit": self.binding.repository_commit,
            "marker_sha256": self.expected.marker.marker_sha256,
            "phase": self.state.phase.value,
            "owned_instance_count": len(self.state.owned_instance_ids),
            "terminal_instance_count": len(self.state.terminal_instance_ids),
            "regional_ruleset_deleted": self.state.regional_ruleset_deleted,
            "global_firewall_restored": self.state.global_firewall_restored,
            "archive_finalized": self.state.archive_finalized,
            "provider_calls": self.budget.state.provider_calls,
            "process_calls": self.budget.state.process_calls,
            "output_bytes": (
                self.budget.state.provider_response_bytes + self.budget.state.process_output_bytes
            ),
            "normal_cost_ceiling_cents": MAX_PROVIDER_COST_CENTS,
            "incident_projected_cost_cents": INCIDENT_PROJECTED_COST_CENTS,
            "raw_provider_ids_retained_publicly": False,
            "provider_addresses_retained_publicly": False,
            "jupyter_credentials_retained": False,
        }


def projected_list_cost_cents(seconds: int) -> int:
    if not 0 <= seconds <= ABSOLUTE_INCIDENT_SECONDS:
        raise L21SupervisorError("cost projection seconds exceed the automated incident ceiling")
    return math.ceil(SELECTED_LIST_PRICE_CENTS_PER_HOUR * seconds / 3_600)


def incident_requires_manual_console(
    *,
    launch_may_have_been_sent: bool,
    owned_instance_resolved: bool,
    terminal_proof_observed: bool,
) -> bool:
    return launch_may_have_been_sent and (
        not owned_instance_resolved or not terminal_proof_observed
    )
