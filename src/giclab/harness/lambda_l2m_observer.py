"""Bounded control contracts for T07's human-operated Lambda Gate L2M.

Importing this module is network inert.  A future separately authorized supervisor
may explicitly construct the exact-host in-process GET transport and the observer
engine below.  The engine has no mutation method and user console actions remain the
only mutation boundary.
"""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import io
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
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final, Protocol, cast

from jsonschema import Draft202012Validator

from giclab.harness.lambda_campaign_lifecycle import (
    ObserverLifecycleLimits,
)
from giclab.harness.lambda_campaign_lifecycle import (
    billed_list_cost_cents as _billed_list_cost_cents,
)
from giclab.harness.lambda_l2m_checkpoints import (
    CheckpointBinding,
    CheckpointConsumptionEvidence,
    CheckpointConsumptionOutcomeUnknown,
    ValidatedHumanDecision,
    VerifiedCheckpoint,
    is_validated_human_decision,
)
from giclab.harness.lambda_l13_security import project_image_identities
from giclab.harness.lambda_ssh_key_fingerprint import (
    SSHKeyFingerprintError,
    parse_public_key,
)

TERMINAL_DECISION: Final = "blocked-human-image-selection"
SELECTED_INSTANCE_TYPE: Final = "gpu_1x_a10"
SELECTED_REGION: Final = "us-east-1"
SELECTED_ARCHITECTURE: Final = "x86_64"
REQUIRED_IMAGE_FAMILY: Final = "lambda-stack-22-04"
RECOMMENDED_IMAGE_ALIAS: Final = "img-0032"
RECOMMENDED_IMAGE_VERSION: Final = "22.4.5-2141"
HISTORICAL_GPU_BASE_ALIAS: Final = "img-0111"
HISTORICAL_GPU_BASE_VERSION: Final = "22.4.5-2141"
SELECTED_SSH_KEY_NAME: Final = "fractal-lambda-codex"
BUNDLE_MANIFEST_SHA256: Final = "dc9824649f97fab6cfd105b5fc0d0c6c1c5ff513fa25f70e0d517afa623cc261"

BUSYBOX_REFERENCE: Final = (
    "busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0"
)
BUSYBOX_MANIFEST_DIGEST: Final = (
    "sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0"
)
BUSYBOX_CONFIG_DIGEST: Final = (
    "sha256:db287cb6be81219cd18c1d82b70908f5d33eb028568b456f78eedff2ff2930e4"
)
BUSYBOX_LAYER_DIGEST: Final = (
    "sha256:436a1b1fd078ee8e117111472724c2827077657189af7a781829d0825d48d2ab"
)
BUSYBOX_LAYER_BYTES: Final = 2_211_507

MAX_PROVIDER_COST_CENTS: Final = 200
OBSERVED_PRICE_CENTS_PER_HOUR: Final = 129
MAX_PROVIDER_WALL_SECONDS: Final = 3_600
EXPECTED_PROVIDER_WALL_SECONDS: Final = 1_800
NORMAL_TERMINATION_CLICK_DEADLINE_SECONDS: Final = 1_800
LAUNCH_TO_ACTIVE_SECONDS: Final = 600
CLOUD_IDE_AVAILABILITY_SECONDS: Final = 600
JUPYTER_QUALIFICATION_SECONDS: Final = 300
EVIDENCE_DOWNLOAD_VALIDATION_SECONDS: Final = 300
TERMINATION_VERIFICATION_SECONDS: Final = 600
FIREWALL_CLEANUP_SECONDS: Final = 300
INCIDENT_HEADROOM_SECONDS: Final = 900
MAX_USER_CHECKPOINT_SECONDS: Final = 300

MAX_OBSERVER_GETS: Final = 44
MAX_RESPONSE_BYTES_PER_GET: Final = 1_048_576
MAX_AGGREGATE_RESPONSE_BYTES: Final = 16_777_216
MAX_OBSERVER_PRELAUNCH_SECONDS: Final = 1_200
MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS: Final = (
    FIREWALL_CLEANUP_SECONDS + INCIDENT_HEADROOM_SECONDS
)
MAX_OBSERVER_ARCHIVE_SECONDS: Final = 300
MAX_OBSERVER_ACTIVE_SECONDS: Final = (
    MAX_OBSERVER_PRELAUNCH_SECONDS
    + MAX_PROVIDER_WALL_SECONDS
    + MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS
)
MAX_OBSERVER_WALL_SECONDS: Final = MAX_OBSERVER_ACTIVE_SECONDS + MAX_OBSERVER_ARCHIVE_SECONDS
MAX_OBSERVER_REQUEST_SECONDS: Final = 60
MIN_REQUEST_SPACING_SECONDS: Final = 1


MAX_OBSERVER_EVENTS: Final = 512
MAX_OBSERVER_EVENT_BYTES: Final = 4_096
MAX_OBSERVER_JOURNAL_BYTES: Final = 2_097_152
MAX_LOCAL_PROCESS_CALLS: Final = 16
MAX_LOCAL_PROCESS_OUTPUT_BYTES: Final = 4_194_304
MAX_QUALIFICATION_ARCHIVE_BYTES: Final = 16_777_216
MAX_QUALIFICATION_UNPACKED_BYTES: Final = 33_554_432
MAX_QUALIFICATION_FILES: Final = 16
MAX_REMOTE_SOURCE_BYTES_PER_EVIDENCE_SET: Final = 16_777_216
MAX_REMOTE_ARCHIVE_BYTES_PER_EVIDENCE_SET: Final = 16_777_216
MAX_REMOTE_SOURCE_RETAINED_BYTES: Final = 34_603_008
MAX_REMOTE_ARCHIVE_RETAINED_BYTES: Final = 33_554_432
MAX_REMOTE_AGGREGATE_RETAINED_BYTES: Final = 68_157_440
MAX_LOCAL_SOURCE_EVIDENCE_BYTES: Final = 41_943_040
MAX_LOCAL_SEALED_EVIDENCE_BYTES: Final = 41_943_040
MAX_MAC_ACTIVE_EVIDENCE_BYTES: Final = 83_886_080
MAX_EXTERNAL_ARCHIVE_BYTES: Final = 41_943_040
MAX_BOUND_SCHEMA_BYTES: Final = 65_536

_BOUND_HOST_EVIDENCE_SCHEMA_RELATIVE_PATH: Final = Path(
    "schemas/t07-lambda-l2m-host-evidence.schema.json"
)
_BOUND_HOST_EVIDENCE_SCHEMA_SHA256: Final = (
    "5c74fb37b81be2ae3fa2563a5b7508f13d19d2dd764a475e5c07e45b369bd195"
)
_BOUND_OBSERVER_JOURNAL_SCHEMA_RELATIVE_PATH: Final = Path(
    "schemas/t07-lambda-l2m-observer-journal.schema.json"
)
_BOUND_OBSERVER_JOURNAL_SCHEMA_SHA256: Final = (
    "5de43193d400e067ce84acd19dfba0128125cf79d3bc6d862176e7895d20473e"
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PRIVATE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_RULESET_NAME = re.compile(r"^t07-l2m-[a-f0-9]{40}$")
_RUN_ID = re.compile(r"^RUN-T07-L2M-[A-Z0-9._-]{3,64}$")
_DECISION_ALIAS = re.compile(r"^l2m-decision-[a-f0-9]{12}$")
_MARKER_ALIAS = re.compile(r"^l2m-marker-[a-f0-9]{12}$")
# Accept the explicit public Gate L2M namespace as well as the shorter fixture
# namespace; both remain bounded, non-pending authorization references.
_AUTHORIZATION_REFERENCE = re.compile(r"^AUTH-T07-(?:GATE-)?L2M-[A-Z0-9._-]{3,96}$")
_VERSION_PART = re.compile(r"\d+")


class L2MContractError(ValueError):
    """Raised when a future manual-console observation violates the contract."""


class L2MDeadlineError(L2MContractError):
    """Raised when a typed observer wall-time boundary is exhausted."""


L2M_DISKUTIL_OUTPUT_CAP_BYTES: Final = 4_194_304
L2M_DISKUTIL_TIMEOUT_SECONDS: Final = 10
L2M_MAX_DISKUTIL_CALLS: Final = 9


def _elapsed_ms_ns(clock_ns: Callable[[], int], started_ns: int) -> int:
    return max(0, (clock_ns() - started_ns) // 1_000_000)


class RulesetMatchState(StrEnum):
    ZERO = "zero_match"
    EXACT_ONE = "exact_one_match"
    MULTIPLE = "multiple_matches"
    DRIFT = "semantic_drift"


class InstanceMatchState(StrEnum):
    ZERO = "zero_match_stop_and_terminate"
    EXACT_ONE = "exact_one_bound"
    MULTIPLE = "multiple_match_manual_incident"
    DRIFT = "bound_instance_semantic_drift"


class ObserverOperation(StrEnum):
    LIST_INSTANCE_TYPES = "list_instance_types"
    LIST_IMAGES = "list_images"
    LIST_SSH_KEYS = "list_ssh_keys"
    LIST_INSTANCES = "list_instances"
    GET_INSTANCE = "get_instance"
    LIST_RULESETS = "list_rulesets"
    GET_RULESET = "get_ruleset"
    GET_GLOBAL_FIREWALL = "get_global_firewall"


class ObserverPhase(StrEnum):
    PREFLIGHT = "preflight"
    ORIGINAL_GLOBAL_SEAL = "original_global_seal"
    GLOBAL_RESTRICTED_VERIFY = "global_restricted_verify"
    RULESET_BIND = "ruleset_bind"
    INSTANCE_BIND = "instance_bind"
    CLOUD_IDE_CHECKPOINT = "cloud_ide_checkpoint"
    QUALIFICATION_LOCAL = "qualification_local"
    TERMINATION_VERIFY = "termination_verify"
    RULESET_ABSENCE = "ruleset_absence"
    GLOBAL_RESTORE = "global_restore"
    INCIDENT = "incident"


_ENDPOINT_SCHEMA_BINDINGS: Final[dict[ObserverOperation, tuple[str, str]]] = {
    ObserverOperation.LIST_INSTANCE_TYPES: (
        "containers/sira-smoke/lambda/endpoint-schemas-v3/instance-types.schema.json",
        "cfa9782f27021640ef0739c9c3896ad391eca76e6e89b02b3375487bfbf6bcf2",
    ),
    ObserverOperation.LIST_IMAGES: (
        "containers/sira-smoke/lambda/endpoint-schemas-v3/images.schema.json",
        "ba3b0ba8e6ecf1c97f94a54a3872056b44527ff81e4538fc35c40b911e896cba",
    ),
    ObserverOperation.LIST_SSH_KEYS: (
        "containers/sira-smoke/lambda/endpoint-schemas-v3/ssh-keys.schema.json",
        "bd5062e1f55e79535a3eb624826339482338600d272b3140b21a4f2096fd84cc",
    ),
    ObserverOperation.LIST_INSTANCES: (
        "containers/sira-smoke/lambda/endpoint-schemas-v3/instances.schema.json",
        "37de7898716eb42c8452cd76755b3218602214f4983755c44714038ff26e480c",
    ),
    ObserverOperation.GET_INSTANCE: (
        "containers/sira-smoke/lambda/endpoint-schemas-v3/instances.schema.json",
        "37de7898716eb42c8452cd76755b3218602214f4983755c44714038ff26e480c",
    ),
    ObserverOperation.LIST_RULESETS: (
        "containers/sira-smoke/lambda/endpoint-schemas-v3/firewall-rulesets.schema.json",
        "66b49463fca2e10db56b70127546691b5cefea5c20babcfafb6098f1844e09d3",
    ),
    ObserverOperation.GET_RULESET: (
        "containers/sira-smoke/lambda/endpoint-schemas-v3/firewall-rulesets.schema.json",
        "66b49463fca2e10db56b70127546691b5cefea5c20babcfafb6098f1844e09d3",
    ),
    ObserverOperation.GET_GLOBAL_FIREWALL: (
        "containers/sira-smoke/lambda/endpoint-schemas-v3/global-firewall-ruleset.schema.json",
        "9328a3cbd4cc97b40c695eb756ba2d339f15936dbf3d931c4f9915090661812f",
    ),
}


OBSERVER_PHASE_GET_LIMITS: Final[dict[ObserverPhase, int]] = {
    ObserverPhase.PREFLIGHT: 6,
    ObserverPhase.ORIGINAL_GLOBAL_SEAL: 1,
    ObserverPhase.GLOBAL_RESTRICTED_VERIFY: 1,
    ObserverPhase.RULESET_BIND: 1,
    ObserverPhase.INSTANCE_BIND: 9,
    ObserverPhase.CLOUD_IDE_CHECKPOINT: 0,
    ObserverPhase.QUALIFICATION_LOCAL: 0,
    ObserverPhase.TERMINATION_VERIFY: 10,
    ObserverPhase.RULESET_ABSENCE: 2,
    ObserverPhase.GLOBAL_RESTORE: 1,
    # One request moved from the incident reserve into mandatory SSH-key
    # preflight.  Thirteen incident GETs still cover the maximum cleanup path:
    # one instance listing, ten terminal polls, one ruleset listing, and one
    # global-firewall read.
    ObserverPhase.INCIDENT: 13,
}

_OBSERVER_PHASE_OPERATIONS: Final[dict[ObserverPhase, frozenset[ObserverOperation]]] = {
    ObserverPhase.PREFLIGHT: frozenset(
        {
            ObserverOperation.LIST_IMAGES,
            ObserverOperation.LIST_INSTANCE_TYPES,
            ObserverOperation.LIST_SSH_KEYS,
            ObserverOperation.LIST_INSTANCES,
            ObserverOperation.LIST_RULESETS,
            ObserverOperation.GET_GLOBAL_FIREWALL,
        }
    ),
    ObserverPhase.ORIGINAL_GLOBAL_SEAL: frozenset({ObserverOperation.GET_GLOBAL_FIREWALL}),
    ObserverPhase.GLOBAL_RESTRICTED_VERIFY: frozenset({ObserverOperation.GET_GLOBAL_FIREWALL}),
    ObserverPhase.RULESET_BIND: frozenset({ObserverOperation.LIST_RULESETS}),
    ObserverPhase.INSTANCE_BIND: frozenset({ObserverOperation.LIST_INSTANCES}),
    ObserverPhase.CLOUD_IDE_CHECKPOINT: frozenset(),
    ObserverPhase.QUALIFICATION_LOCAL: frozenset(),
    ObserverPhase.TERMINATION_VERIFY: frozenset({ObserverOperation.LIST_INSTANCES}),
    ObserverPhase.RULESET_ABSENCE: frozenset({ObserverOperation.LIST_RULESETS}),
    ObserverPhase.GLOBAL_RESTORE: frozenset({ObserverOperation.GET_GLOBAL_FIREWALL}),
    ObserverPhase.INCIDENT: frozenset(
        {
            ObserverOperation.LIST_INSTANCES,
            ObserverOperation.GET_INSTANCE,
            ObserverOperation.LIST_RULESETS,
            ObserverOperation.GET_RULESET,
            ObserverOperation.GET_GLOBAL_FIREWALL,
        }
    ),
}

_CLEANUP_OBSERVER_PHASES: Final = frozenset(
    {
        ObserverPhase.TERMINATION_VERIFY,
        ObserverPhase.RULESET_ABSENCE,
        ObserverPhase.GLOBAL_RESTORE,
        ObserverPhase.INCIDENT,
    }
)


@dataclass(frozen=True, slots=True)
class ImageCandidate:
    alias: str
    family: str
    version: str
    architecture: str
    region: str

    def public_document(self) -> dict[str, str]:
        return {
            "alias": self.alias,
            "family": self.family,
            "version": self.version,
            "architecture": self.architecture,
            "region": self.region,
        }


@dataclass(frozen=True, slots=True)
class ImageSelection:
    recommended: ImageCandidate
    alternates: tuple[ImageCandidate, ...]
    existing_gpu_base_documented_jupyter: bool = False
    human_approval_required: bool = True


@dataclass(frozen=True, slots=True)
class PrivateRulesetMarker:
    name: str = field(repr=False)
    marker_alias: str
    entropy_bits: int


@dataclass(frozen=True, slots=True)
class RulesetMatch:
    state: RulesetMatchState
    match_count: int
    ruleset_id: str | None = field(default=None, repr=False)
    ruleset_ids: tuple[str, ...] = field(default=(), repr=False)


@dataclass(frozen=True, slots=True)
class InstanceMatch:
    state: InstanceMatchState
    match_count: int
    instance_id: str | None = field(default=None, repr=False)
    status: str | None = None
    image_evidence_source: str = "private-human-selection-checkpoint"
    image_selection_checkpoint_sha256: str | None = None
    instance_ids: tuple[str, ...] = field(default=(), repr=False)


@dataclass(frozen=True, slots=True)
class ObservedDocument:
    run_id: str
    authorization_reference: str
    operation: ObserverOperation
    phase: ObserverPhase
    request_ordinal: int
    data: object = field(repr=False)
    response_sha256: str
    response_bytes: int
    http_status: int
    elapsed_ms: int
    request_binding_sha256: str = field(repr=False)
    _issuer: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ValidatedQualification:
    run_id: str
    authorization_reference: str
    archive_path: Path = field(repr=False)
    archive_device: int = field(repr=False)
    archive_inode: int = field(repr=False)
    archive_bytes: int
    archive_sha256: str
    evidence_sha256: str
    binding_sha256: str = field(repr=False)
    _issuer: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ValidatedQualificationFailure:
    """Engine-issued identity for a validated, cleanup-only qualification failure."""

    run_id: str
    authorization_reference: str
    archive_path: Path = field(repr=False)
    archive_device: int = field(repr=False)
    archive_inode: int = field(repr=False)
    archive_bytes: int
    archive_sha256: str
    evidence_sha256: str
    cleanup_complete: bool
    _issuer: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ObserverRequest:
    operation: ObserverOperation
    method: str
    scheme: str
    host: str
    path: str = field(repr=False)
    query_key_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ObserverResponse:
    status: int
    content_type: str
    body: bytes = field(repr=False)
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class ObserverTransportFailure(Exception):
    stage: str
    classification: str
    bytes_received: int = 0
    elapsed_ms: int = 0


class ReadOnlyObserverTransport(Protocol):
    def send(
        self,
        request: ObserverRequest,
        *,
        credential: str,
        timeout_seconds: float,
        absolute_deadline_monotonic_ns: int,
        max_response_bytes: int,
    ) -> ObserverResponse: ...


class LambdaHttpsL2MObserverTransport:
    """Exact-host, no-redirect, in-process HTTPS GET transport.

    Construction and import perform no I/O.  The caller must supply a credential
    only within a future authorized execution boundary.
    """

    def __init__(
        self,
        *,
        ssl_context: ssl.SSLContext | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._ssl_context = ssl_context or ssl.create_default_context()
        self._clock_ns = clock_ns

    def send(
        self,
        request: ObserverRequest,
        *,
        credential: str,
        timeout_seconds: float,
        absolute_deadline_monotonic_ns: int,
        max_response_bytes: int,
    ) -> ObserverResponse:
        validate_observer_request(request)
        if (
            not credential
            or len(credential) > 4_096
            or any(marker in credential for marker in ("\r", "\n", "\x00"))
        ):
            raise ObserverTransportFailure("secret_source", "secret_malformed")
        if not 0 < timeout_seconds <= MAX_OBSERVER_REQUEST_SECONDS:
            raise ObserverTransportFailure("deadline", "deadline_exceeded")
        if not 0 < max_response_bytes <= MAX_RESPONSE_BYTES_PER_GET:
            raise ObserverTransportFailure("response_size", "response_budget_unavailable")
        started_ns = self._clock_ns()
        deadline_ns = min(
            absolute_deadline_monotonic_ns,
            started_ns + math.floor(timeout_seconds * 1_000_000_000),
        )
        if deadline_ns <= started_ns:
            raise ObserverTransportFailure("deadline", "deadline_exceeded")
        body = bytearray()

        def remaining() -> float:
            remaining_ns = deadline_ns - self._clock_ns()
            if remaining_ns <= 0:
                raise ObserverTransportFailure(
                    "deadline",
                    "deadline_exceeded",
                    len(body),
                    _elapsed_ms_ns(self._clock_ns, started_ns),
                )
            return remaining_ns / 1_000_000_000

        def refresh_socket_deadline() -> None:
            timeout = remaining()
            if connection.sock is not None:
                connection.sock.settimeout(timeout)

        connection = http.client.HTTPSConnection(
            "cloud.lambda.ai",
            443,
            timeout=remaining(),
            context=self._ssl_context,
        )
        try:
            try:
                connection.timeout = remaining()
                connection.connect()
                refresh_socket_deadline()
            except ObserverTransportFailure:
                raise
            except (OSError, ssl.SSLError, http.client.HTTPException):
                raise ObserverTransportFailure(
                    "tls_handshake", "connection_or_tls_failure"
                ) from None
            try:
                refresh_socket_deadline()
                connection.request(
                    "GET",
                    request.path,
                    body=None,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {credential}",
                        "User-Agent": "giclab-t07-gate-l2m-observer-v1/1",
                    },
                )
                refresh_socket_deadline()
            except ObserverTransportFailure:
                raise
            except (OSError, ssl.SSLError, http.client.HTTPException):
                raise ObserverTransportFailure("request_write", "request_write_failure") from None
            try:
                refresh_socket_deadline()
                response = connection.getresponse()
                refresh_socket_deadline()
            except ObserverTransportFailure:
                raise
            except (OSError, ssl.SSLError, http.client.HTTPException):
                raise ObserverTransportFailure(
                    "response_headers", "response_headers_failure"
                ) from None
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].casefold()
            while True:
                try:
                    refresh_socket_deadline()
                    chunk = response.read(min(65_536, max_response_bytes + 1 - len(body)))
                except ObserverTransportFailure:
                    raise
                except (OSError, ssl.SSLError, http.client.HTTPException):
                    raise ObserverTransportFailure(
                        "response_body",
                        "response_body_failure",
                        len(body),
                        _elapsed_ms_ns(self._clock_ns, started_ns),
                    ) from None
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > max_response_bytes:
                    raise ObserverTransportFailure(
                        "response_size",
                        "response_too_large",
                        len(body),
                        _elapsed_ms_ns(self._clock_ns, started_ns),
                    )
            remaining()
            return ObserverResponse(
                response.status,
                content_type,
                bytes(body),
                _elapsed_ms_ns(self._clock_ns, started_ns),
            )
        finally:
            with contextlib.suppress(OSError):
                connection.close()


@dataclass(frozen=True, slots=True)
class QualificationEvidenceBinding:
    run_id: str
    decision_alias: str
    marker_alias: str
    instance_binding_sha256: str
    authorization_reference: str
    authorization_sha256: str


@dataclass(frozen=True, slots=True)
class ObserverReservation:
    request: ObserverRequest
    phase: ObserverPhase
    request_ordinal: int
    started_monotonic_ns: int | None
    response_byte_limit: int


@dataclass(frozen=True, slots=True)
class ObserverBudget:
    request_count: int = 0
    response_bytes: int = 0
    elapsed_ms: int = 0
    phase_counts: tuple[int, ...] = (0,) * len(ObserverPhase)
    first_start_monotonic_ns: int | None = None
    last_start_monotonic_ns: int | None = None
    max_wall_seconds: int = MAX_OBSERVER_WALL_SECONDS

    def prepare(
        self,
        request: ObserverRequest,
        *,
        phase: ObserverPhase,
    ) -> ObserverReservation:
        """Reserve one immutable ordinal and its caps before the send-start record."""

        validate_observer_request(request)
        if request.operation not in _OBSERVER_PHASE_OPERATIONS[phase]:
            raise L2MContractError("observer operation is not allowed in this phase")
        phase_index = tuple(ObserverPhase).index(phase)
        updated_phase_counts = list(self.phase_counts)
        updated_phase_counts[phase_index] += 1
        if updated_phase_counts[phase_index] > OBSERVER_PHASE_GET_LIMITS[phase]:
            raise L2MContractError("observer phase GET cap exceeded")
        if self.request_count + 1 > MAX_OBSERVER_GETS:
            raise L2MContractError("observer GET cap exceeded")
        response_byte_limit = min(
            MAX_RESPONSE_BYTES_PER_GET,
            MAX_AGGREGATE_RESPONSE_BYTES - self.response_bytes,
        )
        if response_byte_limit <= 0:
            raise L2MContractError("observer aggregate response cap exhausted")
        return ObserverReservation(
            request,
            phase,
            self.request_count + 1,
            None,
            response_byte_limit,
        )

    def start(
        self,
        reservation: ObserverReservation,
        *,
        started_monotonic_ns: int,
    ) -> tuple[ObserverBudget, ObserverReservation]:
        """Bind a prepared ordinal to the actual in-process transport-entry instant."""

        if (
            reservation.request_ordinal != self.request_count + 1
            or reservation.started_monotonic_ns is not None
            or reservation.request.operation not in _OBSERVER_PHASE_OPERATIONS[reservation.phase]
            or started_monotonic_ns < 0
        ):
            raise L2MContractError("observer prepared reservation identity drifted")
        if (
            self.last_start_monotonic_ns is not None
            and started_monotonic_ns - self.last_start_monotonic_ns
            < MIN_REQUEST_SPACING_SECONDS * 1_000_000_000
        ):
            raise L2MContractError("observer request-start spacing is below its minimum")
        first_start = (
            started_monotonic_ns
            if self.first_start_monotonic_ns is None
            else self.first_start_monotonic_ns
        )
        phase_index = tuple(ObserverPhase).index(reservation.phase)
        updated_phase_counts = list(self.phase_counts)
        updated_phase_counts[phase_index] += 1
        updated = replace(
            self,
            request_count=self.request_count + 1,
            phase_counts=tuple(updated_phase_counts),
            first_start_monotonic_ns=first_start,
            last_start_monotonic_ns=started_monotonic_ns,
        )
        return updated, replace(reservation, started_monotonic_ns=started_monotonic_ns)

    def burn(self, reservation: ObserverReservation) -> ObserverBudget:
        """Consume a prepared ordinal after send-start without claiming transport entry."""

        if (
            reservation.request_ordinal != self.request_count + 1
            or reservation.started_monotonic_ns is not None
            or reservation.request.operation not in _OBSERVER_PHASE_OPERATIONS[reservation.phase]
        ):
            raise L2MContractError("observer burned reservation identity drifted")
        phase_index = tuple(ObserverPhase).index(reservation.phase)
        updated_phase_counts = list(self.phase_counts)
        updated_phase_counts[phase_index] += 1
        return replace(
            self,
            request_count=self.request_count + 1,
            phase_counts=tuple(updated_phase_counts),
        )

    def reserve(
        self,
        request: ObserverRequest,
        *,
        phase: ObserverPhase,
        started_monotonic_ns: int,
    ) -> tuple[ObserverBudget, ObserverReservation]:
        """Compatibility composition for deterministic local budget tests."""

        return self.start(
            self.prepare(request, phase=phase),
            started_monotonic_ns=started_monotonic_ns,
        )

    def complete(
        self,
        reservation: ObserverReservation,
        *,
        response_bytes: int,
        finished_monotonic_ns: int,
    ) -> ObserverBudget:
        """Finalize one already-reserved request without changing its authority."""

        if (
            reservation.request_ordinal != self.request_count
            or reservation.started_monotonic_ns is None
            or reservation.started_monotonic_ns != self.last_start_monotonic_ns
            or self.first_start_monotonic_ns is None
            or finished_monotonic_ns < reservation.started_monotonic_ns
        ):
            raise L2MContractError("observer reservation identity drifted")
        if not 0 <= response_bytes <= reservation.response_byte_limit:
            raise L2MContractError("observer reserved response byte cap exceeded")
        wall_elapsed_ms = math.ceil(
            (finished_monotonic_ns - self.first_start_monotonic_ns) / 1_000_000
        )
        updated = replace(
            self,
            response_bytes=self.response_bytes + response_bytes,
            elapsed_ms=wall_elapsed_ms,
        )
        if updated.response_bytes > MAX_AGGREGATE_RESPONSE_BYTES:
            raise L2MContractError("observer aggregate response cap exceeded")
        if wall_elapsed_ms > self.max_wall_seconds * 1_000:
            raise L2MContractError("observer wall cap exceeded")
        return updated

    def consume(
        self,
        request: ObserverRequest,
        *,
        phase: ObserverPhase,
        response_bytes: int,
        started_monotonic_ns: int,
        finished_monotonic_ns: int,
    ) -> ObserverBudget:
        """Compatibility helper for deterministic local budget tests."""

        reserved, reservation = self.reserve(
            request,
            phase=phase,
            started_monotonic_ns=started_monotonic_ns,
        )
        return reserved.complete(
            reservation,
            response_bytes=response_bytes,
            finished_monotonic_ns=finished_monotonic_ns,
        )


class ManualPhase(StrEnum):
    PREFLIGHT = "preflight"
    GLOBAL_MUTATION_UNVERIFIED = "internal_global_mutation_unverified"
    RULESET_MUTATION_UNVERIFIED = "internal_ruleset_mutation_unverified"
    LAUNCH_OUTCOME_UNVERIFIED = "internal_launch_outcome_unverified"
    GLOBAL_RESTRICTED = "global_firewall_restricted"
    RULESET_CREATED = "regional_ruleset_created"
    LAUNCH_CLICKED = "launch_clicked_once"
    INSTANCE_BOUND = "instance_bound"
    CLOUD_IDE_OPENED = "cloud_ide_opened"
    QUALIFICATION_STARTED = "qualification_command_started"
    QUALIFICATION_COMPLETED = "qualification_command_completed"
    BUNDLE_DOWNLOADED = "qualification_bundle_downloaded"
    TERMINATION_CONFIRMED = "termination_confirmed_by_user"
    INSTANCE_TERMINAL = "instance_terminal_verified"
    RULESET_DELETED = "regional_ruleset_deleted"
    GLOBAL_RESTORED = "global_firewall_restored"
    COMPLETE = "complete"


class TransitionVerificationKind(StrEnum):
    LAUNCH_WIZARD_OFFEREDNESS_ATTESTED = "launch_wizard_offeredness_attested"
    GLOBAL_FIREWALL_EXACT = "global_firewall_exact"
    RULESET_EXACT = "ruleset_exact"
    LAUNCH_CONFIGURATION_ATTESTED = "launch_configuration_attested"
    LAUNCH_CLICK_ATTESTED = "launch_click_attested"
    INSTANCE_EXACT = "instance_exact"
    CLOUD_IDE_ATTESTED = "cloud_ide_attested"
    QUALIFICATION_BUNDLE_UPLOADED_ATTESTED = "qualification_bundle_uploaded_attested"
    QUALIFICATION_STARTED_ATTESTED = "qualification_started_attested"
    QUALIFICATION_COMPLETED_ATTESTED = "qualification_completed_attested"
    ARCHIVE_EXACT = "archive_exact"
    TERMINATION_ATTESTED = "termination_attested"
    INSTANCE_TERMINAL = "instance_terminal"
    RULESET_ABSENT = "ruleset_absent"
    GLOBAL_FIREWALL_RESTORED_EXACT = "global_firewall_restored_exact"


@dataclass(frozen=True, slots=True)
class TransitionProof:
    checkpoint_type: str
    checkpoint_sha256: str
    verification_kind: TransitionVerificationKind
    evidence_sha256: str
    _issuer: object = field(repr=False, compare=False)
    verified: bool = True


@dataclass(frozen=True, slots=True)
class PreparedTransition:
    evidence_sha256: str
    semantic_outcome: str
    semantic_count: int | None
    source_request_ordinal: int
    observation: ObservedDocument | None = field(repr=False)
    detail_validator: Callable[[VerifiedCheckpoint], None] = field(repr=False)
    apply: Callable[[VerifiedCheckpoint], None] = field(repr=False)
    fail: Callable[[], None] = field(repr=False)
    valid: bool = True
    failure_cleanup_phase: ObserverPhase | None = None


@dataclass(slots=True)
class CheckpointTransactionState:
    requested: ManualPhase
    transition_now_ns: int
    checkpoint_type: str
    verification_kind: TransitionVerificationKind
    prepared: PreparedTransition | None = None
    checkpoint: VerifiedCheckpoint | None = None
    proof: TransitionProof | None = None
    next_lifecycle: ManualLifecycle | None = None
    observation_consumed: bool = False
    applied: bool = False
    lifecycle_advanced: bool = False
    failure_handled: bool = False


_TRANSITION_PROOF_KINDS: Final[dict[ManualPhase, TransitionVerificationKind]] = {
    ManualPhase.GLOBAL_RESTRICTED: TransitionVerificationKind.GLOBAL_FIREWALL_EXACT,
    ManualPhase.RULESET_CREATED: TransitionVerificationKind.RULESET_EXACT,
    ManualPhase.LAUNCH_CLICKED: TransitionVerificationKind.LAUNCH_CLICK_ATTESTED,
    ManualPhase.INSTANCE_BOUND: TransitionVerificationKind.INSTANCE_EXACT,
    ManualPhase.CLOUD_IDE_OPENED: TransitionVerificationKind.CLOUD_IDE_ATTESTED,
    ManualPhase.QUALIFICATION_STARTED: (TransitionVerificationKind.QUALIFICATION_STARTED_ATTESTED),
    ManualPhase.QUALIFICATION_COMPLETED: (
        TransitionVerificationKind.QUALIFICATION_COMPLETED_ATTESTED
    ),
    ManualPhase.BUNDLE_DOWNLOADED: TransitionVerificationKind.ARCHIVE_EXACT,
    ManualPhase.TERMINATION_CONFIRMED: TransitionVerificationKind.TERMINATION_ATTESTED,
    ManualPhase.INSTANCE_TERMINAL: TransitionVerificationKind.INSTANCE_TERMINAL,
    ManualPhase.RULESET_DELETED: TransitionVerificationKind.RULESET_ABSENT,
    ManualPhase.GLOBAL_RESTORED: (TransitionVerificationKind.GLOBAL_FIREWALL_RESTORED_EXACT),
}

_MANUAL_TRANSITIONS: Final[dict[ManualPhase, frozenset[ManualPhase]]] = {
    ManualPhase.PREFLIGHT: frozenset({ManualPhase.GLOBAL_RESTRICTED}),
    ManualPhase.GLOBAL_MUTATION_UNVERIFIED: frozenset({ManualPhase.GLOBAL_RESTORED}),
    ManualPhase.RULESET_MUTATION_UNVERIFIED: frozenset(
        {ManualPhase.RULESET_DELETED, ManualPhase.GLOBAL_RESTORED}
    ),
    ManualPhase.LAUNCH_OUTCOME_UNVERIFIED: frozenset(
        {
            ManualPhase.LAUNCH_CLICKED,
            ManualPhase.TERMINATION_CONFIRMED,
            ManualPhase.INSTANCE_TERMINAL,
        }
    ),
    ManualPhase.GLOBAL_RESTRICTED: frozenset(
        {
            ManualPhase.RULESET_CREATED,
            ManualPhase.RULESET_DELETED,
            ManualPhase.GLOBAL_RESTORED,
        }
    ),
    ManualPhase.RULESET_CREATED: frozenset({ManualPhase.INSTANCE_TERMINAL}),
    ManualPhase.LAUNCH_CLICKED: frozenset(
        {
            ManualPhase.INSTANCE_BOUND,
            ManualPhase.TERMINATION_CONFIRMED,
            ManualPhase.INSTANCE_TERMINAL,
        }
    ),
    ManualPhase.INSTANCE_BOUND: frozenset(
        {ManualPhase.CLOUD_IDE_OPENED, ManualPhase.TERMINATION_CONFIRMED}
    ),
    ManualPhase.CLOUD_IDE_OPENED: frozenset(
        {ManualPhase.QUALIFICATION_STARTED, ManualPhase.TERMINATION_CONFIRMED}
    ),
    ManualPhase.QUALIFICATION_STARTED: frozenset(
        {ManualPhase.QUALIFICATION_COMPLETED, ManualPhase.TERMINATION_CONFIRMED}
    ),
    ManualPhase.QUALIFICATION_COMPLETED: frozenset(
        {ManualPhase.BUNDLE_DOWNLOADED, ManualPhase.TERMINATION_CONFIRMED}
    ),
    ManualPhase.BUNDLE_DOWNLOADED: frozenset({ManualPhase.TERMINATION_CONFIRMED}),
    ManualPhase.TERMINATION_CONFIRMED: frozenset({ManualPhase.INSTANCE_TERMINAL}),
    ManualPhase.INSTANCE_TERMINAL: frozenset({ManualPhase.RULESET_DELETED}),
    ManualPhase.RULESET_DELETED: frozenset({ManualPhase.GLOBAL_RESTORED}),
    ManualPhase.GLOBAL_RESTORED: frozenset(),
    ManualPhase.COMPLETE: frozenset(),
}

_CLEANUP_CHECKPOINT_PHASES: Final = frozenset(
    {
        ManualPhase.TERMINATION_CONFIRMED,
        ManualPhase.INSTANCE_TERMINAL,
        ManualPhase.RULESET_DELETED,
        ManualPhase.GLOBAL_RESTORED,
    }
)


@dataclass(frozen=True, slots=True)
class ManualLifecycle:
    phase: ManualPhase = ManualPhase.PREFLIGHT
    strict_firewall_preserved: bool = False
    incident_active: bool = False
    _proof_issuer: object | None = field(default=None, repr=False, compare=False)

    @classmethod
    def for_engine(cls, proof_issuer: object) -> ManualLifecycle:
        return cls(_proof_issuer=proof_issuer)

    def advance(self, checkpoint: VerifiedCheckpoint, proof: TransitionProof) -> ManualLifecycle:
        if self.incident_active:
            raise L2MContractError("manual incident must be resumed before cleanup")
        try:
            requested = ManualPhase(checkpoint.checkpoint_type)
        except ValueError:
            raise L2MContractError("checkpoint type is not a lifecycle phase") from None
        if self.phase is ManualPhase.COMPLETE:
            raise L2MContractError("terminal lifecycle cannot advance")
        if requested not in _MANUAL_TRANSITIONS[self.phase]:
            raise L2MContractError("manual checkpoint order drifted")
        if (
            proof.verified is not True
            or self._proof_issuer is None
            or proof._issuer is not self._proof_issuer
            or proof.checkpoint_type != checkpoint.checkpoint_type
            or proof.checkpoint_sha256 != checkpoint.encoded_sha256
            or _SHA256.fullmatch(proof.evidence_sha256) is None
            or proof.verification_kind is not _TRANSITION_PROOF_KINDS[requested]
        ):
            raise L2MContractError("manual transition proof is invalid")
        strict = self.strict_firewall_preserved or requested is ManualPhase.GLOBAL_RESTRICTED
        if requested is ManualPhase.GLOBAL_RESTORED:
            strict = False
            return ManualLifecycle(ManualPhase.COMPLETE, strict, False, self._proof_issuer)
        return ManualLifecycle(requested, strict, False, self._proof_issuer)

    def incident(self) -> ManualLifecycle:
        if self.phase is ManualPhase.COMPLETE:
            raise L2MContractError("completed lifecycle cannot enter an incident")
        return ManualLifecycle(
            self.phase,
            self.strict_firewall_preserved,
            True,
            self._proof_issuer,
        )

    def mutation_risk(self, phase: ManualPhase) -> ManualLifecycle:
        """Enter a cleanup-only state without claiming the mutation was verified."""

        if (
            phase
            not in {
                ManualPhase.GLOBAL_MUTATION_UNVERIFIED,
                ManualPhase.RULESET_MUTATION_UNVERIFIED,
                ManualPhase.LAUNCH_OUTCOME_UNVERIFIED,
            }
            or self.phase is ManualPhase.COMPLETE
        ):
            raise L2MContractError("manual mutation-risk phase is invalid")
        return ManualLifecycle(
            phase,
            self.strict_firewall_preserved,
            True,
            self._proof_issuer,
        )

    def resume_cleanup(self) -> ManualLifecycle:
        if not self.incident_active:
            raise L2MContractError("no manual incident is active")
        return ManualLifecycle(
            self.phase,
            self.strict_firewall_preserved,
            False,
            self._proof_issuer,
        )


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise L2MContractError(f"{context} must be an object")
    return value


def _sequence(value: object, *, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise L2MContractError(f"{context} must be an array")
    return value


def _string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise L2MContractError(f"{context} must be a nonempty string")
    return value


def _version_key(value: str) -> tuple[int, ...]:
    parts = tuple(int(part) for part in _VERSION_PART.findall(value))
    if not parts:
        raise L2MContractError("image version contains no numeric component")
    return parts


def select_manual_console_images(inventory: Mapping[str, object]) -> ImageSelection:
    """Return only sanitized Lambda Stack 22.04 candidates from sealed inventory."""

    offers = [
        _mapping(item, context="instance type")
        for item in _sequence(inventory.get("instance_types"), context="instance types")
    ]
    selected_offers = [item for item in offers if item.get("name") == SELECTED_INSTANCE_TYPE]
    if len(selected_offers) != 1:
        raise L2MContractError("selected instance type is not unique")
    offer = selected_offers[0]
    if offer.get("architecture") != SELECTED_ARCHITECTURE:
        raise L2MContractError("selected instance architecture drifted")
    regions = {
        _string(_mapping(item, context="capacity region").get("name"), context="region")
        for item in _sequence(offer.get("capacity_regions"), context="capacity regions")
    }
    if SELECTED_REGION not in regions:
        raise L2MContractError("selected instance has no sealed regional capacity")

    projection = project_image_identities(_sequence(inventory.get("images"), context="images"))
    candidates = [
        ImageCandidate(
            alias=image.alias,
            family=image.family,
            version=image.version,
            architecture=image.architecture,
            region=SELECTED_REGION,
        )
        for image in projection.images
        if image.family == REQUIRED_IMAGE_FAMILY
        and image.architecture == SELECTED_ARCHITECTURE
        and SELECTED_REGION in {availability.region_name for availability in image.availability}
    ]
    if not candidates:
        raise L2MContractError("no regional Lambda Stack 22.04 image candidate exists")
    candidates.sort(
        key=lambda item: (tuple(-part for part in _version_key(item.version)), item.alias)
    )
    return ImageSelection(candidates[0], tuple(candidates[1:]))


def derive_private_ruleset_marker(entropy: bytes, *, decision_alias: str) -> PrivateRulesetMarker:
    if len(entropy) < 20:
        raise L2MContractError("ruleset marker entropy is below 160 bits")
    if not re.fullmatch(r"l2m-decision-[a-f0-9]{12}", decision_alias):
        raise L2MContractError("decision alias is invalid")
    digest = hashlib.sha256(
        b"giclab-t07-l2m-ruleset-v1\0" + entropy + decision_alias.encode()
    ).hexdigest()
    name = f"t07-l2m-{digest[:40]}"
    if _RULESET_NAME.fullmatch(name) is None or len(name) > 64:
        raise L2MContractError("ruleset marker name is invalid")
    alias = "l2m-marker-" + hashlib.sha256(name.encode()).hexdigest()[:12]
    return PrivateRulesetMarker(name=name, marker_alias=alias, entropy_bits=len(entropy) * 8)


def _strict_ssh_rule(rule: Mapping[str, object], *, source_ipv4_cidr: str) -> bool:
    ports = rule.get("port_range")
    return (
        set(rule) == {"protocol", "port_range", "source_network", "description"}
        and rule.get("protocol") == "tcp"
        and isinstance(ports, list)
        and ports == [22, 22]
        and rule.get("source_network") == source_ipv4_cidr
        and isinstance(rule.get("description"), str)
        and len(str(rule["description"])) <= 128
    )


def validate_strict_firewall_rules(rules: object, *, source_ipv4_cidr: str) -> None:
    parsed = _sequence(rules, context="firewall rules")
    if len(parsed) != 1 or not _strict_ssh_rule(
        _mapping(parsed[0], context="firewall rule"), source_ipv4_cidr=source_ipv4_cidr
    ):
        raise L2MContractError("firewall is not exactly one private TCP/22 rule")


def firewall_semantic_sha256(rules: object) -> str:
    """Hash the versioned, description-aware complete firewall-rule multiset."""

    # Keep the manual observer's public exception boundary while sharing one exact
    # canonicalization contract with capture and future restoration payloads.
    from .lambda_firewall_baseline import (
        FirewallBaselineError,
        canonicalize_firewall_rules,
    )

    try:
        return canonicalize_firewall_rules(rules).semantic_sha256
    except FirewallBaselineError:
        raise L2MContractError("firewall rule semantics are incomplete or invalid") from None


def verify_global_firewall_restoration(
    ruleset: object,
    *,
    sealed_original_ruleset_id: str,
    sealed_original_ruleset_name: str,
    sealed_original_semantic_sha256: str,
) -> None:
    from .lambda_firewall_baseline import (
        FirewallBaselineError,
        verify_exact_firewall_baseline,
    )

    try:
        verify_exact_firewall_baseline(
            ruleset,
            expected_ruleset_id=sealed_original_ruleset_id,
            expected_ruleset_name=sealed_original_ruleset_name,
            expected_semantic_sha256=sealed_original_semantic_sha256,
        )
    except FirewallBaselineError:
        raise L2MContractError("global firewall was not exactly restored") from None


def verify_global_firewall_identity(
    ruleset: object,
    *,
    sealed_original_ruleset_id: str,
    sealed_original_ruleset_name: str,
) -> None:
    current = _mapping(ruleset, context="global firewall ruleset")
    if (
        not {"id", "name", "rules"} <= set(current)
        or sealed_original_ruleset_id != "global"
        or current.get("id") != sealed_original_ruleset_id
        or current.get("name") != sealed_original_ruleset_name
    ):
        raise L2MContractError("global firewall ruleset identity drifted")


def require_zero_prelaunch_instances(instances: object) -> None:
    if _sequence(instances, context="instances"):
        raise L2MContractError("prelaunch account is not instance-empty")


def classify_ruleset(
    rulesets: object,
    *,
    private_marker_name: str,
    source_ipv4_cidr: str,
) -> RulesetMatch:
    if _RULESET_NAME.fullmatch(private_marker_name) is None:
        raise L2MContractError("private ruleset marker is invalid")
    matching = [
        _mapping(item, context="ruleset")
        for item in _sequence(rulesets, context="rulesets")
        if _mapping(item, context="ruleset").get("name") == private_marker_name
    ]
    if not matching:
        return RulesetMatch(RulesetMatchState.ZERO, 0)
    valid_ids = tuple(
        sorted(
            {
                candidate
                for row in matching
                if isinstance((candidate := row.get("id")), str)
                and _PRIVATE_ID.fullmatch(candidate) is not None
            }
        )
    )
    if len(matching) > 1:
        return RulesetMatch(
            RulesetMatchState.MULTIPLE,
            len(matching),
            ruleset_ids=valid_ids,
        )
    row = matching[0]
    region = _mapping(row.get("region"), context="ruleset region")
    try:
        validate_strict_firewall_rules(row.get("rules"), source_ipv4_cidr=source_ipv4_cidr)
    except L2MContractError:
        return RulesetMatch(RulesetMatchState.DRIFT, 1, ruleset_ids=valid_ids)
    if len(valid_ids) != 1 or region.get("name") != SELECTED_REGION:
        return RulesetMatch(RulesetMatchState.DRIFT, 1, ruleset_ids=valid_ids)
    return RulesetMatch(
        RulesetMatchState.EXACT_ONE,
        1,
        valid_ids[0],
        valid_ids,
    )


def classify_instances_for_ruleset(
    instances: object,
    *,
    private_ruleset_id: str,
    image_selection_checkpoint_sha256: str,
) -> InstanceMatch:
    if _PRIVATE_ID.fullmatch(private_ruleset_id) is None:
        raise L2MContractError("private ruleset ID is invalid")
    if _SHA256.fullmatch(image_selection_checkpoint_sha256) is None:
        raise L2MContractError("image selection checkpoint hash is invalid")
    rows = [_mapping(raw, context="instance") for raw in _sequence(instances, context="instances")]
    if not rows:
        return InstanceMatch(InstanceMatchState.ZERO, 0)
    attached_rows: list[Mapping[str, object]] = []
    attached_ids: list[str] = []
    invalid_identity = False
    for row in rows:
        raw_instance_id = row.get("id")
        attached = _sequence(row.get("firewall_rulesets"), context="instance rulesets")
        attached_ruleset_ids = [
            _string(_mapping(item, context="instance ruleset").get("id"), context="ruleset ID")
            for item in attached
        ]
        if private_ruleset_id not in attached_ruleset_ids:
            continue
        attached_rows.append(row)
        if not isinstance(raw_instance_id, str) or _PRIVATE_ID.fullmatch(raw_instance_id) is None:
            invalid_identity = True
        else:
            attached_ids.append(raw_instance_id)
    if not attached_rows:
        # The private decision authorizes termination only for instances attached to
        # this run's unique ruleset.  An account row outside that scope is drift, not
        # inferred ownership from the earlier zero-instance observation.
        return InstanceMatch(InstanceMatchState.DRIFT, 0)
    if len(attached_rows) > 1 or len(rows) != len(attached_rows):
        return InstanceMatch(
            (
                InstanceMatchState.DRIFT
                if invalid_identity or len(rows) != len(attached_rows)
                else InstanceMatchState.MULTIPLE
            ),
            len(attached_rows),
            instance_ids=tuple(sorted(attached_ids)),
        )
    row = attached_rows[0]
    region = _mapping(row.get("region"), context="instance region")
    instance_type = _mapping(row.get("instance_type"), context="instance type")
    keys = _sequence(row.get("ssh_key_names"), context="SSH key names")
    attached_rulesets = _sequence(row.get("firewall_rulesets"), context="instance rulesets")
    attached_ruleset_ids = [
        _string(_mapping(item, context="instance ruleset").get("id"), context="ruleset ID")
        for item in attached_rulesets
    ]
    file_system_names = row.get("file_system_names", [])
    file_system_mounts = row.get("file_system_mounts", [])
    status = _string(row.get("status"), context="instance status")
    semantic_match = (
        region.get("name") == SELECTED_REGION
        and instance_type.get("name") == SELECTED_INSTANCE_TYPE
        and keys == [SELECTED_SSH_KEY_NAME]
        and attached_ruleset_ids == [private_ruleset_id]
        and file_system_names in (None, [])
        and file_system_mounts in (None, [])
        and status in {"booting", "active"}
    )
    raw_instance_id = row.get("id")
    instance_id = raw_instance_id if isinstance(raw_instance_id, str) else ""
    valid_instance_id = _PRIVATE_ID.fullmatch(instance_id) is not None
    if not semantic_match or not valid_instance_id:
        return InstanceMatch(
            InstanceMatchState.DRIFT,
            1,
            status=status,
            image_selection_checkpoint_sha256=image_selection_checkpoint_sha256,
            instance_ids=(instance_id,) if valid_instance_id else (),
        )
    return InstanceMatch(
        InstanceMatchState.EXACT_ONE,
        1,
        instance_id,
        status,
        image_selection_checkpoint_sha256=image_selection_checkpoint_sha256,
        instance_ids=(instance_id,),
    )


def launch_configuration_sha256(
    *,
    private_image_id: str,
    image_selection_checkpoint_sha256: str,
    image_alias: str,
    image_version: str,
    private_ruleset_id: str,
    private_marker_name: str,
    price_cents_per_hour: int,
) -> str:
    """Hash the exact private final-checklist selection without exposing its raw IDs."""

    if (
        _PRIVATE_ID.fullmatch(private_image_id) is None
        or _SHA256.fullmatch(image_selection_checkpoint_sha256) is None
        or image_alias != RECOMMENDED_IMAGE_ALIAS
        or image_version != RECOMMENDED_IMAGE_VERSION
        or _PRIVATE_ID.fullmatch(private_ruleset_id) is None
        or _RULESET_NAME.fullmatch(private_marker_name) is None
        or price_cents_per_hour != OBSERVED_PRICE_CENTS_PER_HOUR
    ):
        raise L2MContractError("launch configuration identity is invalid")
    return hashlib.sha256(
        json.dumps(
            {
                "architecture": SELECTED_ARCHITECTURE,
                "approved_image_offered_for_selected_type_region": True,
                "file_system_names": [],
                "image_alias": image_alias,
                "image_selection_checkpoint_sha256": image_selection_checkpoint_sha256,
                "image_version": image_version,
                "instance_type": SELECTED_INSTANCE_TYPE,
                "persistent_filesystem": False,
                "price_cents_per_hour": price_cents_per_hour,
                "private_image_id": private_image_id,
                "private_ruleset_id": private_ruleset_id,
                "private_ruleset_marker": private_marker_name,
                "region": SELECTED_REGION,
                "ssh_key_name": SELECTED_SSH_KEY_NAME,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def observer_request(
    operation: ObserverOperation, *, private_resource_id: str | None = None
) -> ObserverRequest:
    if operation is ObserverOperation.LIST_INSTANCE_TYPES:
        path = "/api/v1/instance-types"
    elif operation is ObserverOperation.LIST_IMAGES:
        path = "/api/v1/images"
    elif operation is ObserverOperation.LIST_SSH_KEYS:
        path = "/api/v1/ssh-keys"
    elif operation is ObserverOperation.LIST_INSTANCES:
        path = "/api/v1/instances"
    elif operation is ObserverOperation.LIST_RULESETS:
        path = "/api/v1/firewall-rulesets"
    elif operation is ObserverOperation.GET_GLOBAL_FIREWALL:
        path = "/api/v1/firewall-rulesets/global"
    elif operation in {ObserverOperation.GET_INSTANCE, ObserverOperation.GET_RULESET}:
        if private_resource_id is None or _PRIVATE_ID.fullmatch(private_resource_id) is None:
            raise L2MContractError("private resource identity is invalid")
        prefix = (
            "/api/v1/instances/"
            if operation is ObserverOperation.GET_INSTANCE
            else "/api/v1/firewall-rulesets/"
        )
        path = prefix + private_resource_id
    else:  # pragma: no cover - Enum closes the surface
        raise L2MContractError("observer operation is unsupported")
    request = ObserverRequest(operation, "GET", "https", "cloud.lambda.ai", path)
    validate_observer_request(request)
    return request


def validate_observer_request(request: ObserverRequest) -> None:
    if request.method != "GET" or request.scheme != "https" or request.host != "cloud.lambda.ai":
        raise L2MContractError("observer may use only read-only Lambda HTTPS GETs")
    if request.query_key_names:
        raise L2MContractError("observer requests may not contain a query")
    if request.operation in {ObserverOperation.GET_INSTANCE, ObserverOperation.GET_RULESET}:
        prefix = (
            "/api/v1/instances/"
            if request.operation is ObserverOperation.GET_INSTANCE
            else "/api/v1/firewall-rulesets/"
        )
        private_id = request.path.removeprefix(prefix)
        if not request.path.startswith(prefix) or _PRIVATE_ID.fullmatch(private_id) is None:
            raise L2MContractError("observer resource path drifted")
        return
    static_paths = {
        ObserverOperation.LIST_INSTANCE_TYPES: "/api/v1/instance-types",
        ObserverOperation.LIST_IMAGES: "/api/v1/images",
        ObserverOperation.LIST_SSH_KEYS: "/api/v1/ssh-keys",
        ObserverOperation.LIST_INSTANCES: "/api/v1/instances",
        ObserverOperation.LIST_RULESETS: "/api/v1/firewall-rulesets",
        ObserverOperation.GET_GLOBAL_FIREWALL: "/api/v1/firewall-rulesets/global",
    }
    if static_paths.get(request.operation) != request.path:
        raise L2MContractError("observer path drifted")


def billed_list_cost_cents(seconds: int) -> int:
    try:
        return _billed_list_cost_cents(
            seconds,
            price_cents_per_hour=OBSERVED_PRICE_CENTS_PER_HOUR,
        )
    except ValueError:
        raise L2MContractError("provider wall cannot be negative") from None


def exact_l2m_caps(
    lifecycle_limits: ObserverLifecycleLimits | None = None,
) -> dict[str, int | str]:
    limits = lifecycle_limits or ObserverLifecycleLimits()
    caps: dict[str, int | str] = {
        "observer_gets": MAX_OBSERVER_GETS,
        "response_bytes_per_get": MAX_RESPONSE_BYTES_PER_GET,
        "aggregate_response_bytes": MAX_AGGREGATE_RESPONSE_BYTES,
        "private_observation_files": MAX_OBSERVER_GETS,
        "private_observation_bytes_per_file": MAX_RESPONSE_BYTES_PER_GET,
        "private_observation_aggregate_bytes": MAX_AGGREGATE_RESPONSE_BYTES,
        "observer_wall_seconds": limits.observer_active_seconds(
            prelaunch_seconds=MAX_OBSERVER_PRELAUNCH_SECONDS,
            post_provider_cleanup_seconds=MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS,
        )
        + MAX_OBSERVER_ARCHIVE_SECONDS,
        "observer_active_seconds": limits.observer_active_seconds(
            prelaunch_seconds=MAX_OBSERVER_PRELAUNCH_SECONDS,
            post_provider_cleanup_seconds=MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS,
        ),
        "observer_prelaunch_seconds": MAX_OBSERVER_PRELAUNCH_SECONDS,
        "observer_post_provider_cleanup_seconds": (MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS),
        "observer_archive_seconds": MAX_OBSERVER_ARCHIVE_SECONDS,
        "observer_request_seconds": MAX_OBSERVER_REQUEST_SECONDS,
        "observer_events": MAX_OBSERVER_EVENTS,
        "observer_event_bytes": MAX_OBSERVER_EVENT_BYTES,
        "observer_journal_bytes": MAX_OBSERVER_JOURNAL_BYTES,
        "local_process_calls": MAX_LOCAL_PROCESS_CALLS,
        "local_process_output_bytes": MAX_LOCAL_PROCESS_OUTPUT_BYTES,
        "provider_wall_seconds": limits.campaign_provider_wall_seconds,
        "provider_cost_cents": limits.max_provider_cost_cents,
        "normal_termination_click_seconds": limits.normal_termination_cutoff_seconds,
        "launch_to_active_seconds": LAUNCH_TO_ACTIVE_SECONDS,
        "cloud_ide_availability_seconds": CLOUD_IDE_AVAILABILITY_SECONDS,
        "qualification_command_seconds": JUPYTER_QUALIFICATION_SECONDS,
        "evidence_download_validation_seconds": EVIDENCE_DOWNLOAD_VALIDATION_SECONDS,
        "termination_verification_seconds": TERMINATION_VERIFICATION_SECONDS,
        "firewall_cleanup_seconds": FIREWALL_CLEANUP_SECONDS,
        "incident_headroom_seconds": INCIDENT_HEADROOM_SECONDS,
        "normal_modeled_list_cost_cents": billed_list_cost_cents(2_400),
        "hard_wall_modeled_list_cost_cents": billed_list_cost_cents(
            limits.campaign_provider_wall_seconds
        ),
        "qualification_archive_bytes": MAX_QUALIFICATION_ARCHIVE_BYTES,
        "qualification_unpacked_bytes": MAX_QUALIFICATION_UNPACKED_BYTES,
        "remote_source_bytes_per_evidence_set": MAX_REMOTE_SOURCE_BYTES_PER_EVIDENCE_SET,
        "remote_archive_bytes_per_evidence_set": MAX_REMOTE_ARCHIVE_BYTES_PER_EVIDENCE_SET,
        "remote_source_retained_bytes": MAX_REMOTE_SOURCE_RETAINED_BYTES,
        "remote_archive_retained_bytes": MAX_REMOTE_ARCHIVE_RETAINED_BYTES,
        "remote_aggregate_retained_bytes": MAX_REMOTE_AGGREGATE_RETAINED_BYTES,
        "local_source_evidence_bytes": MAX_LOCAL_SOURCE_EVIDENCE_BYTES,
        "local_sealed_evidence_bytes": MAX_LOCAL_SEALED_EVIDENCE_BYTES,
        "mac_active_evidence_bytes": MAX_MAC_ACTIVE_EVIDENCE_BYTES,
        "external_archive_bytes": MAX_EXTERNAL_ARCHIVE_BYTES,
        "manual_launch_clicks": 1,
        "instances": 1,
        "persistent_filesystems": 0,
        "automated_cloud_mutations": 0,
        "ssh_operations": 0,
        "model_calls": 0,
        "model_tokens": 0,
        "browser_automation_actions": 0,
        "sira_executions": 0,
        "automatic_retries": 0,
        "pagination_requests": 0,
        "busybox_layer_bytes": BUSYBOX_LAYER_BYTES,
        "terminal_decision": TERMINAL_DECISION,
    }
    for phase, limit in OBSERVER_PHASE_GET_LIMITS.items():
        caps[f"observer_phase_{phase.value}_gets"] = limit
    return caps


def verify_bundle_manifest(bundle_root: Path) -> dict[str, object]:
    """Verify the committed upload bundle without executing any file."""

    root = bundle_root.resolve(strict=True)
    manifest_path = root / "manifest.json"
    document = json.loads(manifest_path.read_bytes())
    manifest = _mapping(document, context="bundle manifest")
    files = _sequence(manifest.get("files"), context="bundle files")
    expected_names = {
        "adversarial-containment.sh",
        "docker_inspector.py",
        "evidence_packager.py",
        "host_facts.py",
        "public-source-observations-l2-2.json",
        "qualification_driver.py",
    }
    observed_names: set[str] = set()
    for raw in files:
        item = _mapping(raw, context="bundle file")
        name = _string(item.get("path"), context="bundle path")
        if name not in expected_names or PurePosixPath(name).parts != (name,):
            raise L2MContractError("bundle manifest path is not allowlisted")
        path = root / name
        opened = path.open("rb")
        try:
            info = os.fstat(opened.fileno())
            encoded = opened.read(MAX_QUALIFICATION_UNPACKED_BYTES + 1)
        finally:
            opened.close()
        if not stat.S_ISREG(info.st_mode) or len(encoded) > MAX_QUALIFICATION_UNPACKED_BYTES:
            raise L2MContractError("bundle file identity or size is invalid")
        if (
            item.get("bytes") != len(encoded)
            or item.get("sha256") != hashlib.sha256(encoded).hexdigest()
        ):
            raise L2MContractError("bundle file hash drifted")
        observed_names.add(name)
    if observed_names != expected_names:
        raise L2MContractError("bundle manifest is incomplete")
    if manifest.get("busybox_reference") != BUSYBOX_REFERENCE:
        raise L2MContractError("bundle BusyBox pin drifted")
    return dict(manifest)


def _strict_json_value(encoded: bytes, *, context: str) -> object:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise L2MContractError(f"{context} contains a duplicate key")
            result[key] = value
        return result

    try:
        return json.loads(encoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise L2MContractError(f"{context} is not strict JSON") from None


def _repository_root_for_bound_path(
    requested_path: Path,
    *,
    relative_path: Path,
    context: str,
) -> Path:
    absolute = requested_path.absolute()
    if tuple(absolute.parts[-len(relative_path.parts) :]) != relative_path.parts:
        raise L2MContractError(f"{context} path is not repository-bound")
    root = absolute
    for _ in relative_path.parts:
        root = root.parent
    try:
        resolved = root.resolve(strict=True)
        identity = root.lstat()
    except OSError:
        raise L2MContractError(f"{context} repository root is unavailable") from None
    if resolved != root or not stat.S_ISDIR(identity.st_mode):
        raise L2MContractError(f"{context} repository root is unsafe")
    return root


def _load_bound_schema(
    requested_path: Path,
    *,
    relative_path: Path,
    expected_sha256: str,
    context: str,
) -> tuple[Mapping[str, object], Path]:
    repository_root = _repository_root_for_bound_path(
        requested_path,
        relative_path=relative_path,
        context=context,
    )
    bound_path = repository_root / relative_path
    if requested_path.absolute() != bound_path:
        raise L2MContractError(f"{context} path is not repository-bound")
    encoded = _read_bounded_regular(bound_path, max_bytes=MAX_BOUND_SCHEMA_BYTES)
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise L2MContractError(f"{context} identity drifted")
    return (
        _mapping(_strict_json_value(encoded, context=context), context=context),
        repository_root,
    )


def _validate_private_container_inspect(
    encoded: bytes, *, evidence: Mapping[str, object]
) -> tuple[str, str]:
    document = _mapping(
        _strict_json_value(encoded, context="container inspect evidence"),
        context="container inspect evidence",
    )
    expected_document_keys = {
        "documents",
        "fixture",
        "fixture_markers",
        "image",
        "post_term_process",
        "pre_stop_process",
        "residue_scan",
        "runtime",
    }
    if set(document) != expected_document_keys:
        raise L2MContractError("container inspect evidence contract drifted")
    _mapping(document.get("runtime"), context="private runtime evidence")
    fixture = _mapping(document.get("fixture"), context="private staged fixture evidence")
    fixture_bytes = fixture.get("bytes")
    if (
        set(fixture) != {"bytes", "identity_sha256", "sha256"}
        or type(fixture_bytes) is not int
        or not isinstance(fixture.get("sha256"), str)
        or _SHA256.fullmatch(str(fixture["sha256"])) is None
        or not isinstance(fixture.get("identity_sha256"), str)
        or _SHA256.fullmatch(str(fixture["identity_sha256"])) is None
    ):
        raise L2MContractError("private staged fixture evidence drifted")
    if not 1 <= fixture_bytes <= 1_048_576:
        raise L2MContractError("private staged fixture evidence drifted")
    image = _mapping(document.get("image"), context="private image evidence")
    repo_digests = _sequence(image.get("repo_digests"), context="private image repo digests")
    if (
        set(image) != {"architecture", "id", "os", "repo_digests"}
        or image.get("id") != BUSYBOX_CONFIG_DIGEST
        or image.get("os") != "linux"
        or image.get("architecture") != "amd64"
        or BUSYBOX_REFERENCE not in repo_digests
        or not 1 <= len(repo_digests) <= 16
        or any(not isinstance(item, str) or len(item) > 512 for item in repo_digests)
    ):
        raise L2MContractError("private image identity evidence drifted")
    busybox = _mapping(evidence.get("busybox"), context="BusyBox evidence")
    if (
        busybox.get("image_record_sha256")
        != hashlib.sha256(
            json.dumps(image, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    ):
        raise L2MContractError("private image identity hash drifted")

    process_keys = {
        "distinct_sid_count",
        "max_parent_depth",
        "process_count",
        "reparented_session_leader_count",
        "structural_sha256",
    }

    def validate_process_report(
        name: str,
    ) -> tuple[Mapping[str, object], int, int, int, int]:
        report = _mapping(document.get(name), context=f"{name} evidence")
        if set(report) != process_keys:
            raise L2MContractError("process structure evidence contract drifted")
        raw_numeric = (
            report.get("process_count"),
            report.get("max_parent_depth"),
            report.get("distinct_sid_count"),
            report.get("reparented_session_leader_count"),
        )
        if any(type(value) is not int for value in raw_numeric):
            raise L2MContractError("process structure evidence value drifted")
        process_count, max_parent_depth, distinct_sid_count, reparented_count = (
            cast(int, value) for value in raw_numeric
        )
        if (
            not 1 <= process_count <= 64
            or not 0 <= max_parent_depth <= 64
            or not 1 <= distinct_sid_count <= 64
            or not 0 <= reparented_count <= 64
            or not isinstance(report.get("structural_sha256"), str)
            or _SHA256.fullmatch(str(report["structural_sha256"])) is None
        ):
            raise L2MContractError("process structure evidence value drifted")
        return (
            report,
            process_count,
            max_parent_depth,
            distinct_sid_count,
            reparented_count,
        )

    (
        pre_stop,
        pre_stop_count,
        pre_stop_depth,
        pre_stop_sid_count,
        pre_stop_reparented_count,
    ) = validate_process_report("pre_stop_process")
    (
        post_term,
        post_term_count,
        post_term_depth,
        post_term_sid_count,
        _,
    ) = validate_process_report("post_term_process")
    markers = _mapping(document.get("fixture_markers"), context="fixture marker evidence")
    pid_limit_marker_count = markers.get("pid_limit_marker_count")
    if (
        set(markers)
        != {"applets_verified", "log_sha256", "pid_limit_marker_count", "pid_limit_observed"}
        or markers.get("applets_verified") is not True
        or markers.get("pid_limit_observed") is not True
        or type(pid_limit_marker_count) is not int
        or not isinstance(markers.get("log_sha256"), str)
        or _SHA256.fullmatch(str(markers["log_sha256"])) is None
    ):
        raise L2MContractError("fixture marker evidence drifted")
    if not 1 <= pid_limit_marker_count <= 2:
        raise L2MContractError("fixture marker evidence drifted")
    containment = _mapping(evidence.get("containment"), context="containment evidence")
    if containment.get("fixture_sha256") != fixture.get("sha256") or containment.get(
        "fixture_identity_sha256"
    ) != fixture.get("identity_sha256"):
        raise L2MContractError("staged fixture evidence cross-binding drifted")
    residue_scan = _mapping(document.get("residue_scan"), context="runtime residue scan")
    residue_keys = {
        "matched_cgroup_count",
        "matched_process_count",
        "scan_sha256",
        "scanned_cgroup_entries",
        "scanned_process_count",
    }
    residue_summary = {
        key: residue_scan.get(key)
        for key in (
            "matched_cgroup_count",
            "matched_process_count",
            "scanned_cgroup_entries",
            "scanned_process_count",
        )
    }
    if (
        set(residue_scan) != residue_keys
        or any(type(value) is not int or value < 0 for value in residue_summary.values())
        or residue_summary["matched_cgroup_count"] != 0
        or residue_summary["matched_process_count"] != 0
        or residue_scan.get("scan_sha256")
        != hashlib.sha256(
            json.dumps(residue_summary, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        or containment.get("background_process_residue_count")
        != residue_summary["matched_process_count"]
        or containment.get("owned_cgroup_residue_count") != residue_summary["matched_cgroup_count"]
        or containment.get("residue_scanned_process_count")
        != residue_summary["scanned_process_count"]
        or containment.get("residue_scanned_cgroup_entries")
        != residue_summary["scanned_cgroup_entries"]
        or containment.get("residue_scan_sha256") != residue_scan.get("scan_sha256")
    ):
        raise L2MContractError("runtime residue evidence cross-binding drifted")
    process_expectations = {
        "pre_stop_process_count": pre_stop.get("process_count"),
        "pre_stop_max_parent_depth": pre_stop.get("max_parent_depth"),
        "pre_stop_distinct_sid_count": pre_stop.get("distinct_sid_count"),
        "pre_stop_reparented_session_leader_count": pre_stop.get("reparented_session_leader_count"),
        "post_term_process_count": post_term.get("process_count"),
        "post_term_max_parent_depth": post_term.get("max_parent_depth"),
        "post_term_distinct_sid_count": post_term.get("distinct_sid_count"),
        "pid_limit_observed": True,
        "term_ignoring_descendants_proven": True,
    }
    if any(containment.get(key) != value for key, value in process_expectations.items()):
        raise L2MContractError("host/process structure evidence cross-binding drifted")
    process_document = {
        "fixture_markers": markers,
        "post_term": post_term,
        "pre_stop": pre_stop,
    }
    if (
        containment.get("process_structure_sha256")
        != hashlib.sha256(
            json.dumps(process_document, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    ):
        raise L2MContractError("process structure aggregate hash drifted")
    if (
        pre_stop_count < 60
        or pre_stop_depth < 2
        or pre_stop_sid_count < 2
        or pre_stop_reparented_count < 1
        or post_term_count < 3
        or post_term_depth < 2
        or post_term_sid_count < 2
    ):
        raise L2MContractError("adversarial descendant structure is insufficient")
    documents = _sequence(document.get("documents"), context="container inspect documents")
    if len(documents) != 3:
        raise L2MContractError("container inspect lifecycle is incomplete")
    expected_container_sha256 = _string(
        containment.get("container_id_sha256"), context="container identity hash"
    )
    states: list[bool] = []
    for raw in documents:
        row = _mapping(raw, context="container inspect document")
        container_id = _string(row.get("Id"), context="container ID")
        if hashlib.sha256(container_id.encode()).hexdigest() != expected_container_sha256:
            raise L2MContractError("container inspect identity binding drifted")
        host = _mapping(row.get("HostConfig"), context="container host config")
        config = _mapping(row.get("Config"), context="container config")
        state = _mapping(row.get("State"), context="container state")
        mounts = _sequence(row.get("Mounts"), context="container mounts")
        restart = _mapping(host.get("RestartPolicy"), context="container restart policy")
        log_config = _mapping(host.get("LogConfig"), context="container log config")
        labels = _mapping(config.get("Labels"), context="container labels")
        tmpfs = _mapping(host.get("Tmpfs"), context="container tmpfs")
        expected_host = {
            "NetworkMode": "none",
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "Privileged": False,
            "ReadonlyRootfs": True,
            "PidsLimit": 64,
            "NanoCpus": 1_000_000_000,
            "Memory": 536_870_912,
            "MemorySwap": 536_870_912,
            "ShmSize": 16_777_216,
            "Init": True,
        }
        if (
            any(host.get(key) != value for key, value in expected_host.items())
            or host.get("PidMode") not in {"", None}
            or restart.get("Name") != "no"
            or set(_sequence(host.get("CapDrop"), context="capability drops")) != {"ALL"}
            or "no-new-privileges=true"
            not in set(_sequence(host.get("SecurityOpt"), context="security options"))
            or set(tmpfs) != {"/tmp", "/run"}
            or any(
                set(str(value).split(",")) != {"rw", "noexec", "nosuid", "nodev", "size=16777216"}
                for value in tmpfs.values()
            )
            or log_config.get("Type") != "local"
            or _mapping(log_config.get("Config"), context="log options")
            != {"max-file": "1", "max-size": "1m"}
            or labels.get("giclab.t07.run") != evidence.get("run_id")
            or labels.get("giclab.t07.marker") != evidence.get("marker_alias")
            or config.get("Image") != BUSYBOX_REFERENCE
            or row.get("Image") != BUSYBOX_CONFIG_DIGEST
        ):
            raise L2MContractError("container inspect policy drifted")
        if len(mounts) != 1:
            raise L2MContractError("container inspect mount count drifted")
        mount = _mapping(mounts[0], context="container fixture mount")
        if (
            mount.get("Type") != "bind"
            or mount.get("Destination") != "/opt/t07/adversarial-containment.sh"
            or mount.get("RW") is not False
            or any(
                "docker.sock" in str(value) or "podman.sock" in str(value)
                for value in mount.values()
            )
        ):
            raise L2MContractError("container inspect fixture mount drifted")
        running = state.get("Running")
        if not isinstance(running, bool):
            raise L2MContractError("container inspect running state is invalid")
        states.append(running)
    if states != [False, True, False]:
        raise L2MContractError("container inspect TERM/KILL lifecycle drifted")
    return str(pre_stop["structural_sha256"]), str(post_term["structural_sha256"])


def _validate_qualification_log(
    encoded: bytes,
    *,
    evidence: Mapping[str, object],
    process_report_sha256s: tuple[str, str],
) -> None:
    lines = encoded.splitlines()
    expected_events = (
        "container_created",
        "pre_stop_process_evidence",
        "term_survived",
        "kill_terminal",
        "container_removed",
        "residue_verified",
        "qualification_passed",
    )
    if len(lines) != len(expected_events):
        raise L2MContractError("qualification lifecycle log is incomplete")
    events = [
        _mapping(
            _strict_json_value(line, context="qualification lifecycle event"),
            context="qualification lifecycle event",
        )
        for line in lines
    ]
    if [event.get("event") for event in events] != list(expected_events) or [
        event.get("sequence") for event in events
    ] != list(range(1, len(expected_events) + 1)):
        raise L2MContractError("qualification lifecycle event order drifted")
    containment = _mapping(evidence.get("containment"), context="containment evidence")
    container_sha256 = containment.get("container_id_sha256")
    create_sha256 = containment.get("create_argv_sha256")
    process_count = events[1].get("process_count")
    elapsed_seconds = events[6].get("elapsed_seconds")
    if (
        events[0].get("container_id_sha256") != container_sha256
        or events[0].get("create_argv_sha256") != create_sha256
        or any(events[index].get("container_id_sha256") != container_sha256 for index in (2, 3, 4))
        or process_count != containment.get("pre_stop_process_count")
        or events[1].get("report_sha256") != process_report_sha256s[0]
        or events[1].get("pid_limit_observed") is not True
        or events[2].get("process_count") != containment.get("post_term_process_count")
        or events[2].get("report_sha256") != process_report_sha256s[1]
        or {key: events[5].get(key) for key in ("container", "network", "volume")}
        != {"container": 0, "network": 0, "volume": 0}
        or not isinstance(elapsed_seconds, int)
        or isinstance(elapsed_seconds, bool)
        or not 1 <= elapsed_seconds <= JUPYTER_QUALIFICATION_SECONDS
    ):
        raise L2MContractError("qualification lifecycle evidence drifted")


def validate_qualification_archive(
    archive_path: Path,
    *,
    schema_path: Path,
    expected_bundle_manifest_sha256: str,
    expected_binding: QualificationEvidenceBinding,
    _encoded_archive: bytes | None = None,
) -> dict[str, object]:
    """Validate one bounded private Jupyter evidence ZIP without extracting it."""

    if _SHA256.fullmatch(expected_bundle_manifest_sha256) is None:
        raise L2MContractError("expected bundle hash is invalid")
    binding_patterns = (
        (_RUN_ID, expected_binding.run_id),
        (_DECISION_ALIAS, expected_binding.decision_alias),
        (_MARKER_ALIAS, expected_binding.marker_alias),
        (_SHA256, expected_binding.instance_binding_sha256),
        (_AUTHORIZATION_REFERENCE, expected_binding.authorization_reference),
        (_SHA256, expected_binding.authorization_sha256),
    )
    if any(pattern.fullmatch(value) is None for pattern, value in binding_patterns):
        raise L2MContractError("expected qualification evidence binding is invalid")
    encoded_archive = (
        _read_bounded_regular(archive_path, max_bytes=MAX_QUALIFICATION_ARCHIVE_BYTES)
        if _encoded_archive is None
        else _encoded_archive
    )
    if len(encoded_archive) > MAX_QUALIFICATION_ARCHIVE_BYTES:
        raise L2MContractError("qualification archive exceeds its byte cap")
    allowed = {
        "host-evidence.json",
        "qualification-log.jsonl",
        "container-inspect.json",
        "EVIDENCE_MANIFEST.json",
    }
    payloads: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(encoded_archive)) as archive:
        if len(archive.infolist()) > MAX_QUALIFICATION_FILES:
            raise L2MContractError("qualification archive has too many files")
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            if (
                path.parts != (member.filename,)
                or member.filename not in allowed
                or member.is_dir()
            ):
                raise L2MContractError("qualification archive path is unsafe")
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise L2MContractError("qualification archive contains a symlink")
            if member.filename in payloads:
                raise L2MContractError("qualification archive contains a duplicate path")
            total += member.file_size
            if total > MAX_QUALIFICATION_UNPACKED_BYTES:
                raise L2MContractError("qualification archive expands past its cap")
            payloads[member.filename] = archive.read(member)
    if set(payloads) != allowed:
        raise L2MContractError("qualification archive is incomplete")
    schema, _ = _load_bound_schema(
        schema_path,
        relative_path=_BOUND_HOST_EVIDENCE_SCHEMA_RELATIVE_PATH,
        expected_sha256=_BOUND_HOST_EVIDENCE_SCHEMA_SHA256,
        context="host evidence schema",
    )
    evidence = _strict_json_value(payloads["host-evidence.json"], context="host evidence")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(evidence), key=lambda error: list(error.path)
    )
    if errors:
        raise L2MContractError("host evidence failed its bound schema")
    evidence_map = _mapping(evidence, context="host evidence")
    if evidence_map.get("bundle_manifest_sha256") != expected_bundle_manifest_sha256:
        raise L2MContractError("host evidence bundle binding drifted")
    expected_values = {
        "run_id": expected_binding.run_id,
        "decision_alias": expected_binding.decision_alias,
        "marker_alias": expected_binding.marker_alias,
        "instance_binding_sha256": expected_binding.instance_binding_sha256,
        "authorization_reference": expected_binding.authorization_reference,
        "authorization_sha256": expected_binding.authorization_sha256,
    }
    if any(evidence_map.get(key) != value for key, value in expected_values.items()):
        raise L2MContractError("host evidence identity binding drifted")
    process_report_sha256s = _validate_private_container_inspect(
        payloads["container-inspect.json"], evidence=evidence_map
    )
    _validate_qualification_log(
        payloads["qualification-log.jsonl"],
        evidence=evidence_map,
        process_report_sha256s=process_report_sha256s,
    )
    manifest = _mapping(
        _strict_json_value(payloads["EVIDENCE_MANIFEST.json"], context="evidence manifest"),
        context="evidence manifest",
    )
    if set(manifest) != {"schema_version", "files"} or manifest.get("schema_version") != "0.1.0":
        raise L2MContractError("qualification evidence manifest contract drifted")
    files = _sequence(manifest.get("files"), context="evidence files")
    identities: dict[str, tuple[object, object]] = {}
    for raw in files:
        item = _mapping(raw, context="evidence file")
        if set(item) != {"path", "bytes", "sha256"}:
            raise L2MContractError("qualification evidence identity contract drifted")
        name = _string(item.get("path"), context="evidence path")
        if name in identities:
            raise L2MContractError("qualification evidence manifest has a duplicate path")
        identities[name] = (item.get("bytes"), item.get("sha256"))
    if set(identities) != allowed - {"EVIDENCE_MANIFEST.json"}:
        raise L2MContractError("qualification evidence manifest is incomplete")
    for name in allowed - {"EVIDENCE_MANIFEST.json"}:
        encoded = payloads[name]
        if identities.get(name) != (len(encoded), hashlib.sha256(encoded).hexdigest()):
            raise L2MContractError("qualification evidence manifest drifted")
    return dict(evidence_map)


def validate_qualification_failure_archive(
    archive_path: Path,
    *,
    expected_bundle_manifest_sha256: str,
    expected_binding: QualificationEvidenceBinding,
    _encoded_archive: bytes | None = None,
) -> dict[str, object]:
    """Validate a bounded failure archive; it can never satisfy host qualification."""

    encoded_archive = (
        _read_bounded_regular_with_identity(
            archive_path,
            max_bytes=MAX_QUALIFICATION_ARCHIVE_BYTES,
        )[0]
        if _encoded_archive is None
        else _encoded_archive
    )
    if len(encoded_archive) > MAX_QUALIFICATION_ARCHIVE_BYTES:
        raise L2MContractError("qualification failure archive exceeds its byte cap")
    allowed = {
        "qualification-failure.json",
        "qualification-log.jsonl",
        "container-inspect.json",
        "EVIDENCE_MANIFEST.json",
    }
    payloads: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(encoded_archive)) as archive:
        if len(archive.infolist()) > MAX_QUALIFICATION_FILES:
            raise L2MContractError("qualification failure archive has too many files")
        for member in archive.infolist():
            if (
                PurePosixPath(member.filename).parts != (member.filename,)
                or member.filename not in allowed
                or member.filename in payloads
                or member.is_dir()
                or stat.S_ISLNK(member.external_attr >> 16)
            ):
                raise L2MContractError("qualification failure archive path is unsafe")
            total += member.file_size
            if total > MAX_QUALIFICATION_UNPACKED_BYTES:
                raise L2MContractError("qualification failure archive expands past its cap")
            payloads[member.filename] = archive.read(member)
    if set(payloads) != allowed:
        raise L2MContractError("qualification failure archive is incomplete")
    disposition = _mapping(
        _strict_json_value(
            payloads["qualification-failure.json"], context="qualification failure disposition"
        ),
        context="qualification failure disposition",
    )
    expected_values = {
        "run_id": expected_binding.run_id,
        "authorization_reference": expected_binding.authorization_reference,
        "authorization_sha256": expected_binding.authorization_sha256,
        "decision_alias": expected_binding.decision_alias,
        "marker_alias": expected_binding.marker_alias,
        "instance_binding_sha256": expected_binding.instance_binding_sha256,
        "bundle_manifest_sha256": expected_bundle_manifest_sha256,
    }
    cleanup = _mapping(disposition.get("cleanup"), context="emergency cleanup evidence")
    expected_cleanup_keys = {
        "cgroup_residue_count",
        "container_id_sha256",
        "container_residue_count",
        "create_outcome_observations",
        "create_outcome_quiescence_proven",
        "create_outcome_resolution",
        "create_outcome_unknown",
        "docker_config_removed",
        "fixture_removed",
        "kill_attempted",
        "kill_succeeded",
        "network_residue_count",
        "process_residue_count",
        "remove_attempted",
        "remove_succeeded",
        "residue_scan_sha256",
        "residue_scanned_cgroup_entries",
        "residue_scanned_process_count",
        "volume_residue_count",
    }
    container_sha256 = cleanup.get("container_id_sha256")
    if (
        set(cleanup) != expected_cleanup_keys
        or (
            container_sha256 is not None
            and (
                not isinstance(container_sha256, str) or _SHA256.fullmatch(container_sha256) is None
            )
        )
        or any(
            type(cleanup.get(name)) is not bool
            for name in (
                "kill_attempted",
                "kill_succeeded",
                "remove_attempted",
                "remove_succeeded",
                "docker_config_removed",
                "fixture_removed",
                "create_outcome_unknown",
                "create_outcome_quiescence_proven",
            )
        )
        or any(
            value is not None and type(value) is not int
            for value in (
                cleanup.get("container_residue_count"),
                cleanup.get("network_residue_count"),
                cleanup.get("volume_residue_count"),
                cleanup.get("process_residue_count"),
                cleanup.get("cgroup_residue_count"),
                cleanup.get("residue_scanned_process_count"),
                cleanup.get("residue_scanned_cgroup_entries"),
                cleanup.get("create_outcome_observations"),
            )
        )
        or cleanup.get("create_outcome_resolution")
        not in {
            "not_applicable",
            "recovered_and_stably_absent",
            "unresolved_no_match",
            "ambiguous",
            "late_residue",
            "quiescence_failed",
            "recovered_pending_stable_absence",
        }
        or (
            cleanup.get("residue_scan_sha256") is not None
            and (
                not isinstance(cleanup.get("residue_scan_sha256"), str)
                or _SHA256.fullmatch(str(cleanup["residue_scan_sha256"])) is None
            )
        )
    ):
        raise L2MContractError("qualification failure cleanup contract drifted")
    residue_values = {
        cleanup.get("container_residue_count"),
        cleanup.get("network_residue_count"),
        cleanup.get("volume_residue_count"),
        cleanup.get("process_residue_count"),
        cleanup.get("cgroup_residue_count"),
    }
    expected_cleanup_complete = (
        cleanup.get("remove_succeeded") is True
        and residue_values == {0}
        and cleanup.get("docker_config_removed") is True
        and cleanup.get("fixture_removed") is True
        and cleanup.get("create_outcome_quiescence_proven") is True
    )
    expected_disposition_keys = {
        "authorization_reference",
        "authorization_sha256",
        "bundle_manifest_sha256",
        "cleanup",
        "cleanup_complete",
        "decision_alias",
        "instance_binding_sha256",
        "marker_alias",
        "provider_termination_required",
        "run_id",
        "sanitized_failure_stage",
        "schema_version",
    }
    if (
        set(disposition) != expected_disposition_keys
        or disposition.get("schema_version") != "0.1.0"
        or any(disposition.get(key) != value for key, value in expected_values.items())
        or disposition.get("sanitized_failure_stage")
        not in {
            "host_contract",
            "runtime_observation",
            "image_pull",
            "container_create",
            "containment_inspect",
            "container_start",
            "process_evidence",
            "term_survival",
            "kill_terminal",
            "container_remove",
            "residue_verification",
            "process_residue_verification",
            "qualification_wall",
            "evidence_write",
            "evidence_package",
        }
        or disposition.get("provider_termination_required") is not True
        or disposition.get("cleanup_complete") is not expected_cleanup_complete
    ):
        raise L2MContractError("qualification failure disposition drifted")

    log_lines = payloads["qualification-log.jsonl"].splitlines()
    log_events = [
        _mapping(
            _strict_json_value(line, context="qualification failure log event"),
            context="qualification failure log event",
        )
        for line in log_lines
    ]
    if (
        len(log_events) < 2
        or [event.get("sequence") for event in log_events] != list(range(1, len(log_events) + 1))
        or log_events[-2].get("event") != "qualification_failed"
        or log_events[-2].get("failure_stage") != disposition.get("sanitized_failure_stage")
        or log_events[-1].get("event") != "emergency_cleanup_observed"
        or log_events[-1].get("cleanup_complete") is not expected_cleanup_complete
        or log_events[-1].get("cleanup") != cleanup
    ):
        raise L2MContractError("qualification failure lifecycle evidence drifted")

    inspect = _mapping(
        _strict_json_value(payloads["container-inspect.json"], context="failure container inspect"),
        context="failure container inspect",
    )
    if set(inspect) != {"documents", "residue_scan", "runtime"}:
        raise L2MContractError("qualification failure inspect contract drifted")
    _mapping(inspect.get("runtime"), context="failure runtime evidence")
    inspect_documents = _sequence(
        inspect.get("documents"), context="failure container inspect documents"
    )
    failure_residue_scan = inspect.get("residue_scan")
    if failure_residue_scan is not None:
        scan = _mapping(failure_residue_scan, context="failure runtime residue scan")
        summary = {
            key: scan.get(key)
            for key in (
                "matched_cgroup_count",
                "matched_process_count",
                "scanned_cgroup_entries",
                "scanned_process_count",
            )
        }
        if (
            set(scan)
            != {
                "matched_cgroup_count",
                "matched_process_count",
                "scan_sha256",
                "scanned_cgroup_entries",
                "scanned_process_count",
            }
            or any(type(value) is not int or value < 0 for value in summary.values())
            or scan.get("scan_sha256")
            != hashlib.sha256(
                json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            or cleanup.get("process_residue_count") != summary["matched_process_count"]
            or cleanup.get("cgroup_residue_count") != summary["matched_cgroup_count"]
            or cleanup.get("residue_scanned_process_count") != summary["scanned_process_count"]
            or cleanup.get("residue_scanned_cgroup_entries") != summary["scanned_cgroup_entries"]
            or cleanup.get("residue_scan_sha256") != scan.get("scan_sha256")
        ):
            raise L2MContractError("qualification failure residue evidence drifted")
    elif any(
        cleanup.get(key) is not None
        for key in (
            "residue_scan_sha256",
            "residue_scanned_process_count",
            "residue_scanned_cgroup_entries",
        )
    ):
        raise L2MContractError("qualification failure residue evidence is incomplete")
    if len(inspect_documents) > 3:
        raise L2MContractError("qualification failure inspect lifecycle is oversized")
    observed_container_sha256s: set[str] = set()
    for raw in inspect_documents:
        row = _mapping(raw, context="failure container inspect document")
        raw_id = _string(row.get("Id"), context="failure container ID")
        state = _mapping(row.get("State"), context="failure container state")
        if not isinstance(state.get("Running"), bool):
            raise L2MContractError("qualification failure container state drifted")
        observed_container_sha256s.add(hashlib.sha256(raw_id.encode()).hexdigest())
    if (
        len(observed_container_sha256s) > 1
        or (bool(observed_container_sha256s) and observed_container_sha256s != {container_sha256})
        or (
            container_sha256 is not None
            and not observed_container_sha256s
            and cleanup.get("remove_attempted") is True
        )
    ):
        raise L2MContractError("qualification failure container identity drifted")
    manifest = _mapping(
        _strict_json_value(payloads["EVIDENCE_MANIFEST.json"], context="failure manifest"),
        context="failure manifest",
    )
    if set(manifest) != {"files", "schema_version"} or manifest.get("schema_version") != "0.1.0":
        raise L2MContractError("qualification failure manifest contract drifted")
    identities: dict[str, tuple[object, object]] = {}
    for raw in _sequence(manifest.get("files"), context="failure files"):
        item = _mapping(raw, context="failure file")
        if set(item) != {"bytes", "path", "sha256"}:
            raise L2MContractError("qualification failure file identity drifted")
        name = _string(item.get("path"), context="failure path")
        if name in identities:
            raise L2MContractError("qualification failure manifest has a duplicate path")
        identities[name] = (item.get("bytes"), item.get("sha256"))
    if set(identities) != allowed - {"EVIDENCE_MANIFEST.json"}:
        raise L2MContractError("qualification failure manifest is incomplete")
    for name in allowed - {"EVIDENCE_MANIFEST.json"}:
        encoded = payloads[name]
        if identities.get(name) != (len(encoded), hashlib.sha256(encoded).hexdigest()):
            raise L2MContractError("qualification failure evidence manifest drifted")
    return {
        "eligible_for_host_qualification": False,
        "cleanup_complete": disposition.get("cleanup_complete"),
        "provider_termination_required": True,
        "sanitized_failure_stage": disposition.get("sanitized_failure_stage"),
    }


@dataclass(frozen=True, slots=True)
class ObserverJournalEvidence:
    path: Path
    device: int
    inode: int
    byte_count: int
    sha256: str
    encoded: bytes = field(repr=False)
    complete: bool = True


class ObserverJournalAppendOutcomeUnknown(L2MContractError):
    """One journal event may have been written, so the run identity is burned."""

    def __init__(
        self,
        *,
        event_sequence: int,
        content_complete: bool,
        durability_complete: bool,
    ) -> None:
        super().__init__("observer journal append outcome is unknown")
        self.event_sequence = event_sequence
        self.content_complete = content_complete
        self.durability_complete = durability_complete


class ObserverJournal:
    """Exclusive, append-only, fsync-backed, public-safe local observer journal."""

    def __init__(
        self,
        descriptor: int,
        path: Path,
        schema: Mapping[str, object],
        repository_root: Path,
    ) -> None:
        self._descriptor = descriptor
        self._path = path.absolute()
        self._repository_root = repository_root
        identity = os.fstat(descriptor)
        self._device = identity.st_dev
        self._inode = identity.st_ino
        self._validator = Draft202012Validator(schema)
        self._events = 0
        self._bytes = 0
        self._closed = False
        self._final_evidence: ObserverJournalEvidence | None = None
        self._append_outcome_unknown = False
        self._unknown_record_start: int | None = None
        self._unknown_record: bytes | None = None
        self._unknown_prior_events: int | None = None

    @classmethod
    def create(cls, path: Path, *, schema_path: Path) -> ObserverJournal:
        schema, repository_root = _load_bound_schema(
            schema_path,
            relative_path=_BOUND_OBSERVER_JOURNAL_SCHEMA_RELATIVE_PATH,
            expected_sha256=_BOUND_OBSERVER_JOURNAL_SCHEMA_SHA256,
            context="observer journal schema",
        )
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent = path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode):
            raise L2MContractError("observer journal parent is unsafe")
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_APPEND
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        return cls(descriptor, path, schema, repository_root)

    @property
    def repository_root(self) -> Path:
        return self._repository_root

    def append(self, event: Mapping[str, object]) -> None:
        if self._closed or self._append_outcome_unknown:
            raise L2MContractError("observer journal is closed")
        expected_sequence = self._events + 1
        if event.get("event_sequence") != expected_sequence:
            raise L2MContractError("observer journal sequence drifted")
        errors = tuple(self._validator.iter_errors(event))
        if errors:
            raise L2MContractError("observer journal event failed schema validation")
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        if len(encoded) > MAX_OBSERVER_EVENT_BYTES:
            raise L2MContractError("observer journal event exceeds its cap")
        if (
            self._events + 1 > MAX_OBSERVER_EVENTS
            or self._bytes + len(encoded) > MAX_OBSERVER_JOURNAL_BYTES
        ):
            raise L2MContractError("observer journal capacity exceeded")
        identity = os.fstat(self._descriptor)
        if identity.st_size != self._bytes:
            raise L2MContractError("observer journal size drifted before append")
        record_start = self._bytes
        try:
            view = memoryview(encoded)
            while view:
                written = os.write(self._descriptor, view)
                if written <= 0:
                    raise OSError
                view = view[written:]
            os.fsync(self._descriptor)
        except BaseException:
            content_complete = False
            durability_complete = False
            try:
                observed_size = os.fstat(self._descriptor).st_size
                observed_length = observed_size - record_start
                if not 0 <= observed_length <= len(encoded):
                    raise OSError
                observed = os.pread(self._descriptor, observed_length, record_start)
                if observed != encoded[:observed_length]:
                    raise OSError
                remaining = memoryview(encoded)[observed_length:]
                while remaining:
                    written = os.write(self._descriptor, remaining)
                    if written <= 0:
                        raise OSError
                    remaining = remaining[written:]
                os.fsync(self._descriptor)
                durability_complete = True
                final = os.pread(self._descriptor, len(encoded), record_start)
                content_complete = final == encoded
            except BaseException:
                # The descriptor remains held and the exact expected record is kept
                # privately in memory so close() can validate and retain only an
                # observed prefix.  No later append is permitted.
                pass
            self._append_outcome_unknown = True
            self._unknown_record_start = record_start
            self._unknown_record = encoded
            self._unknown_prior_events = self._events
            if content_complete:
                self._events += 1
                self._bytes += len(encoded)
            raise ObserverJournalAppendOutcomeUnknown(
                event_sequence=expected_sequence,
                content_complete=content_complete,
                durability_complete=durability_complete,
            ) from None
        self._events += 1
        self._bytes += len(encoded)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def next_sequence(self) -> int:
        return self._events + 1

    @property
    def events_written(self) -> int:
        return self._events

    @property
    def bytes_written(self) -> int:
        return self._bytes

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def append_outcome_unknown(self) -> bool:
        return self._append_outcome_unknown

    def reserve_capacity(self, *, events: int, bytes_upper_bound: int) -> None:
        """Fail before a request when its complete terminal ledger cannot fit."""

        if (
            self._closed
            or self._append_outcome_unknown
            or events < 1
            or bytes_upper_bound < 1
            or self._events + events > MAX_OBSERVER_EVENTS
            or self._bytes + bytes_upper_bound > MAX_OBSERVER_JOURNAL_BYTES
        ):
            raise L2MContractError("observer journal terminal capacity is unavailable")

    def close(self) -> None:
        if not self._closed:
            try:
                durability_complete = True
                try:
                    os.fsync(self._descriptor)
                except BaseException:
                    durability_complete = False
                identity = os.fstat(self._descriptor)
                encoded = os.pread(self._descriptor, MAX_OBSERVER_JOURNAL_BYTES + 1, 0)
                linked = self._path.lstat()
                if (
                    not stat.S_ISREG(identity.st_mode)
                    or identity.st_nlink != 1
                    or identity.st_uid != os.getuid()
                    or (identity.st_dev, identity.st_ino) != (self._device, self._inode)
                    or (linked.st_dev, linked.st_ino) != (self._device, self._inode)
                    or len(encoded) != identity.st_size
                ):
                    raise L2MContractError("observer journal final identity drifted")
                if self._append_outcome_unknown:
                    record_start = self._unknown_record_start
                    expected_record = self._unknown_record
                    prior_events = self._unknown_prior_events
                    if (
                        record_start is None
                        or expected_record is None
                        or prior_events is None
                        or not record_start <= len(encoded) <= record_start + len(expected_record)
                        or encoded[record_start:] != expected_record[: len(encoded) - record_start]
                        or (record_start > 0 and not encoded[:record_start].endswith(b"\n"))
                        or len(encoded[:record_start].splitlines()) != prior_events
                    ):
                        raise L2MContractError("observer journal uncertain prefix identity drifted")
                elif len(encoded) != self._bytes or self._events != len(encoded.splitlines()):
                    raise L2MContractError("observer journal final sequence drifted")
                self._final_evidence = ObserverJournalEvidence(
                    self._path,
                    identity.st_dev,
                    identity.st_ino,
                    len(encoded),
                    hashlib.sha256(encoded).hexdigest(),
                    encoded,
                    complete=durability_complete and not self._append_outcome_unknown,
                )
            finally:
                os.close(self._descriptor)
                self._closed = True

    @property
    def final_evidence(self) -> ObserverJournalEvidence:
        if not self._closed or self._final_evidence is None:
            raise L2MContractError("observer journal evidence is not final")
        return self._final_evidence

    def __enter__(self) -> ObserverJournal:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class PrivateObservationRecord:
    request_ordinal: int
    path: Path = field(repr=False)
    device: int = field(repr=False)
    inode: int = field(repr=False)
    byte_count: int
    sha256: str
    encoded: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class PrivateObservationBinding:
    """In-memory binding between a raw response and its durable projection."""

    operation: ObserverOperation
    projection_bytes: int
    projection_sha256: str
    raw_response_bytes: int
    raw_response_sha256: str


@dataclass(frozen=True, slots=True)
class PrivateObservationEvidence:
    root: Path = field(repr=False)
    root_device: int = field(repr=False)
    root_inode: int = field(repr=False)
    records: tuple[PrivateObservationRecord, ...]
    total_bytes: int
    complete: bool = True


class PrivateObservationStore:
    """Fresh, private, fsync-backed retention for allowlisted response projections."""

    def __init__(self, descriptor: int, root: Path) -> None:
        self._descriptor = descriptor
        self._root = root.absolute()
        identity = os.fstat(descriptor)
        self._device = identity.st_dev
        self._inode = identity.st_ino
        self._records: list[PrivateObservationRecord] = []
        self._total_bytes = 0
        self._write_failed = False
        self._closed = False
        self._final_evidence: PrivateObservationEvidence | None = None

    @classmethod
    def create(cls, root: Path) -> PrivateObservationStore:
        parent = root.parent
        parent_identity = parent.lstat()
        if (
            not stat.S_ISDIR(parent_identity.st_mode)
            or parent_identity.st_uid != os.getuid()
            or root.exists()
            or root.is_symlink()
        ):
            raise L2MContractError("private observation evidence root is not fresh")
        try:
            root.mkdir(mode=0o700)
            descriptor = os.open(
                root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
            root_identity = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(root_identity.st_mode)
                or root_identity.st_uid != os.getuid()
                or stat.S_IMODE(root_identity.st_mode) != 0o700
            ):
                raise L2MContractError("private observation evidence root is unsafe")
            parent_descriptor = os.open(
                parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                os.fsync(parent_descriptor)
            finally:
                os.close(parent_descriptor)
            return cls(descriptor, root)
        except OSError:
            raise L2MContractError("private observation evidence root creation failed") from None

    @property
    def closed(self) -> bool:
        return self._closed

    def reserve_capacity(self, *, maximum_response_bytes: int) -> None:
        if (
            self._closed
            or not 0 < maximum_response_bytes <= MAX_RESPONSE_BYTES_PER_GET
            or len(self._records) + 1 > MAX_OBSERVER_GETS
            or self._total_bytes + maximum_response_bytes > MAX_AGGREGATE_RESPONSE_BYTES
        ):
            raise L2MContractError("private observation evidence capacity is unavailable")

    def write(self, request_ordinal: int, encoded: bytes) -> PrivateObservationRecord:
        if (
            self._closed
            or not 1 <= request_ordinal <= MAX_OBSERVER_GETS
            or (self._records and request_ordinal <= self._records[-1].request_ordinal)
            or len(encoded) > MAX_RESPONSE_BYTES_PER_GET
            or self._total_bytes + len(encoded) > MAX_AGGREGATE_RESPONSE_BYTES
        ):
            raise L2MContractError("private observation evidence identity or cap failed")
        name = f"observation-{request_ordinal:04d}.json"
        temporary_name = f".{name}.partial"
        try:
            _write_exclusive_record(self._descriptor, temporary_name, encoded)
            staged = _read_bounded_at(
                self._descriptor,
                temporary_name,
                max_bytes=MAX_RESPONSE_BYTES_PER_GET,
            )
            if staged != encoded:
                raise L2MContractError("private observation staging verification failed")
            os.rename(
                temporary_name,
                name,
                src_dir_fd=self._descriptor,
                dst_dir_fd=self._descriptor,
            )
            os.fsync(self._descriptor)
            identity = os.stat(name, dir_fd=self._descriptor, follow_symlinks=False)
        except BaseException as error:
            self._write_failed = True
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            raise L2MContractError("private observation evidence write failed") from None
        record = PrivateObservationRecord(
            request_ordinal,
            self._root / name,
            identity.st_dev,
            identity.st_ino,
            len(encoded),
            hashlib.sha256(encoded).hexdigest(),
            bytes(encoded),
        )
        self._records.append(record)
        self._total_bytes += len(encoded)
        return record

    def close(self) -> None:
        if self._closed:
            return
        try:
            os.fsync(self._descriptor)
            root_identity = os.fstat(self._descriptor)
            linked = self._root.lstat()
            if (
                not stat.S_ISDIR(root_identity.st_mode)
                or root_identity.st_uid != os.getuid()
                or (root_identity.st_dev, root_identity.st_ino) != (self._device, self._inode)
                or (linked.st_dev, linked.st_ino) != (self._device, self._inode)
            ):
                raise L2MContractError("private observation evidence root identity drifted")
            expected_names = {record.path.name for record in self._records}
            observed_names = set(os.listdir(self._descriptor))
            if self._write_failed or observed_names != expected_names:
                raise L2MContractError(
                    "private observation evidence root contains an untracked write"
                )
            verified: list[PrivateObservationRecord] = []
            for record in self._records:
                encoded = _read_bounded_at(
                    self._descriptor,
                    record.path.name,
                    max_bytes=MAX_RESPONSE_BYTES_PER_GET,
                )
                identity = os.stat(
                    record.path.name,
                    dir_fd=self._descriptor,
                    follow_symlinks=False,
                )
                if (
                    (identity.st_dev, identity.st_ino) != (record.device, record.inode)
                    or len(encoded) != record.byte_count
                    or encoded != record.encoded
                    or hashlib.sha256(encoded).hexdigest() != record.sha256
                ):
                    raise L2MContractError("private observation evidence changed before close")
                verified.append(record)
            self._final_evidence = PrivateObservationEvidence(
                self._root,
                root_identity.st_dev,
                root_identity.st_ino,
                tuple(verified),
                self._total_bytes,
            )
        finally:
            os.close(self._descriptor)
            self._closed = True

    @property
    def final_evidence(self) -> PrivateObservationEvidence:
        if not self._closed or self._final_evidence is None:
            raise L2MContractError("private observation evidence is not final")
        return self._final_evidence


class CheckpointReader(Protocol):
    binding: CheckpointBinding
    repository_root: Path

    @property
    def final_evidence(self) -> CheckpointConsumptionEvidence: ...

    def read_once(
        self,
        path: Path,
        *,
        expected_type: str,
        expected_nonce: str,
        not_before: datetime,
        not_after: datetime,
        detail_validator: Callable[[VerifiedCheckpoint], None] | None = None,
        on_consumed: Callable[[VerifiedCheckpoint], None] | None = None,
    ) -> VerifiedCheckpoint: ...

    def close(self) -> None: ...


_PAGINATION_KEYS: Final = frozenset(
    {
        "page_token",
        "next_page_token",
        "next_token",
        "continuation_token",
        "cursor",
        "has_more",
    }
)


def _pagination_present(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            (key in _PAGINATION_KEYS and child not in (None, False, "", [], {}))
            or _pagination_present(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_pagination_present(child) for child in value)
    return False


def _load_bound_endpoint_schema(
    operation: ObserverOperation,
    *,
    repository_root: Path,
) -> Mapping[str, object]:
    relative_path, expected_sha256 = _ENDPOINT_SCHEMA_BINDINGS[operation]
    path = repository_root / relative_path
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        identity = os.fstat(descriptor)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_nlink != 1
            or identity.st_size > 262_144
        ):
            raise L2MContractError("observer endpoint schema identity is unsafe")
        encoded = bytearray()
        while len(encoded) <= 262_144:
            chunk = os.read(descriptor, min(65_536, 262_145 - len(encoded)))
            if not chunk:
                break
            encoded.extend(chunk)
    finally:
        os.close(descriptor)
    if len(encoded) != identity.st_size or hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise L2MContractError("observer endpoint schema identity drifted")
    try:
        return _mapping(json.loads(encoded), context="observer endpoint schema")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise L2MContractError("observer endpoint schema is invalid JSON") from None


def _validate_endpoint_document(
    request: ObserverRequest,
    envelope: Mapping[str, object],
    *,
    schemas: Mapping[ObserverOperation, Mapping[str, object]],
) -> None:
    schema = schemas.get(request.operation)
    if schema is None:
        raise L2MContractError("observer endpoint schema was not preloaded")
    candidate: Mapping[str, object] = envelope
    if request.operation in {ObserverOperation.GET_INSTANCE, ObserverOperation.GET_RULESET}:
        candidate = {**envelope, "data": [envelope.get("data")]}
    if next(Draft202012Validator(schema).iter_errors(candidate), None) is not None:
        raise L2MContractError("observer response failed its bound endpoint schema")

    if request.operation in {ObserverOperation.LIST_INSTANCES, ObserverOperation.GET_INSTANCE}:
        data = envelope.get("data")
        rows = (
            [data]
            if request.operation is ObserverOperation.GET_INSTANCE
            else _sequence(data, context="observer instance data")
        )
        for raw in rows:
            row = _mapping(raw, context="observer instance")
            rulesets = _sequence(
                row.get("firewall_rulesets"), context="observer instance firewall rulesets"
            )
            for attached in rulesets:
                ruleset_id = _string(
                    _mapping(attached, context="observer instance firewall ruleset").get("id"),
                    context="observer instance firewall ruleset ID",
                )
                if _PRIVATE_ID.fullmatch(ruleset_id) is None:
                    raise L2MContractError("observer instance firewall ruleset identity is invalid")


def _observer_data(
    request: ObserverRequest,
    encoded: bytes,
    *,
    schemas: Mapping[ObserverOperation, Mapping[str, object]],
) -> object:
    envelope = _mapping(
        _strict_json_value(encoded, context="observer response"),
        context="observer response",
    )
    if "data" not in envelope:
        raise L2MContractError("observer response lacks the documented data envelope")
    if _pagination_present(envelope):
        raise L2MContractError("observer response contains pagination")
    _validate_endpoint_document(request, envelope, schemas=schemas)
    data = envelope["data"]
    list_operations = {
        ObserverOperation.LIST_IMAGES,
        ObserverOperation.LIST_SSH_KEYS,
        ObserverOperation.LIST_INSTANCES,
        ObserverOperation.LIST_RULESETS,
    }
    if request.operation in list_operations:
        _sequence(data, context="observer list data")
    else:
        _mapping(data, context="observer detail data")
    return data


def _project_region(value: object) -> dict[str, object]:
    region = _mapping(value, context="private observation region")
    return {"name": region.get("name")}


def _project_instance_type(value: object) -> dict[str, object]:
    instance_type = _mapping(value, context="private observation instance type")
    specs = _mapping(instance_type.get("specs"), context="private observation specs")
    return {
        "name": instance_type.get("name"),
        "price_cents_per_hour": instance_type.get("price_cents_per_hour"),
        "architecture": instance_type.get("architecture"),
        "specs": {key: specs.get(key) for key in ("vcpus", "memory_gib", "storage_gib", "gpus")},
    }


def _project_firewall_rule(value: object) -> dict[str, object]:
    rule = _mapping(value, context="private observation firewall rule")
    return {
        key: rule.get(key) for key in ("protocol", "port_range", "source_network", "description")
    }


def _project_instance(value: object) -> dict[str, object]:
    instance = _mapping(value, context="private observation instance")
    projected: dict[str, object] = {
        "id": instance.get("id"),
        "status": instance.get("status"),
        "ssh_key_names": list(
            _sequence(instance.get("ssh_key_names"), context="private observation SSH keys")
        ),
        "file_system_names": list(
            _sequence(
                instance.get("file_system_names"),
                context="private observation file systems",
            )
        ),
        "region": _project_region(instance.get("region")),
        "instance_type": _project_instance_type(instance.get("instance_type")),
        "firewall_rulesets": [
            {"id": _mapping(item, context="private observation attached ruleset").get("id")}
            for item in _sequence(
                instance.get("firewall_rulesets"),
                context="private observation attached rulesets",
            )
        ],
    }
    mounts = instance.get("file_system_mounts")
    if mounts is not None:
        projected["file_system_mounts"] = [
            {
                key: _mapping(item, context="private observation mount").get(key)
                for key in ("mount_point", "file_system_id")
            }
            for item in _sequence(mounts, context="private observation mounts")
        ]
    return projected


def _project_ruleset(value: object) -> dict[str, object]:
    ruleset = _mapping(value, context="private observation ruleset")
    return {
        "id": ruleset.get("id"),
        "name": ruleset.get("name"),
        "region": _project_region(ruleset.get("region")),
        "rules": [
            _project_firewall_rule(item)
            for item in _sequence(ruleset.get("rules"), context="private observation rules")
        ],
        "created": ruleset.get("created"),
        "instance_ids": list(
            _sequence(
                ruleset.get("instance_ids"),
                context="private observation ruleset instance IDs",
            )
        ),
    }


def _encode_private_observation_projection(
    operation: ObserverOperation,
    data: object,
    *,
    raw_response_sha256: str,
    raw_response_bytes: int,
) -> bytes:
    """Retain only the operational fields needed for later private verification."""

    if operation is ObserverOperation.LIST_IMAGES:
        projected: object = [
            {
                "id": row.get("id"),
                "created_time": row.get("created_time"),
                "updated_time": row.get("updated_time"),
                "name": row.get("name"),
                "family": row.get("family"),
                "version": row.get("version"),
                "architecture": row.get("architecture"),
                "region": _project_region(row.get("region")),
            }
            for item in _sequence(data, context="private observation images")
            for row in [_mapping(item, context="private observation image")]
        ]
    elif operation is ObserverOperation.LIST_INSTANCE_TYPES:
        projected = {
            key: {
                "instance_type": _project_instance_type(entry.get("instance_type")),
                "regions_with_capacity_available": [
                    _project_region(region)
                    for region in _sequence(
                        entry.get("regions_with_capacity_available"),
                        context="private observation capacity regions",
                    )
                ],
            }
            for key, value in sorted(
                _mapping(data, context="private observation instance types").items()
            )
            for entry in [_mapping(value, context="private observation instance type entry")]
        }
    elif operation is ObserverOperation.LIST_SSH_KEYS:
        projected = [
            {"id": row.get("id"), "name": row.get("name")}
            for item in _sequence(data, context="private observation SSH keys")
            for row in [_mapping(item, context="private observation SSH key")]
        ]
    elif operation is ObserverOperation.LIST_INSTANCES:
        projected = [
            _project_instance(item)
            for item in _sequence(data, context="private observation instances")
        ]
    elif operation is ObserverOperation.GET_INSTANCE:
        projected = _project_instance(data)
    elif operation is ObserverOperation.LIST_RULESETS:
        projected = [
            _project_ruleset(item)
            for item in _sequence(data, context="private observation rulesets")
        ]
    elif operation is ObserverOperation.GET_RULESET:
        projected = _project_ruleset(data)
    elif operation is ObserverOperation.GET_GLOBAL_FIREWALL:
        global_ruleset = _mapping(data, context="private observation global firewall")
        projected = {
            "id": global_ruleset.get("id"),
            "name": global_ruleset.get("name"),
            "rules": [
                _project_firewall_rule(item)
                for item in _sequence(
                    global_ruleset.get("rules"),
                    context="private observation global rules",
                )
            ],
        }
    else:  # pragma: no cover - exhaustive enum guard
        raise L2MContractError("private observation operation is unsupported")
    encoded = json.dumps(
        {
            "schema_version": "0.1.0",
            "operation": operation.value,
            "raw_response_bytes": raw_response_bytes,
            "raw_response_sha256": raw_response_sha256,
            "data": projected,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if len(encoded) > MAX_RESPONSE_BYTES_PER_GET:
        raise L2MContractError("private observation projection exceeds its cap")
    return encoded


def _observer_path_template(request: ObserverRequest) -> str:
    if request.operation is ObserverOperation.GET_INSTANCE:
        return "/api/v1/instances/{private_instance_id}"
    if request.operation is ObserverOperation.GET_RULESET:
        return "/api/v1/firewall-rulesets/{private_ruleset_id}"
    return request.path


def _checkpoint_detail(checkpoint: VerifiedCheckpoint, name: str) -> object:
    if name not in checkpoint.details:
        raise L2MContractError("checkpoint lacks the required typed detail")
    return checkpoint.details[name]


@dataclass(slots=True)
class L2MReadOnlyObserverEngine:
    """Trusted composition for future authorized read-only observation.

    The engine accepts an injected transport and credential; it never reads an
    environment or secret file.  All provider effects are constrained to the exact
    GET renderer and all user transitions are derived from a consumed checkpoint plus
    an engine-issued observation or local evidence validation.
    """

    run_id: str
    authorization_reference: str
    authorization_sha256: str = field(repr=False)
    journal: ObserverJournal
    checkpoint_reader: CheckpointReader
    transport: ReadOnlyObserverTransport
    private_marker_name: str = field(repr=False)
    source_ipv4_cidr: str = field(repr=False)
    human_decision: ValidatedHumanDecision = field(repr=False)
    sealed_original_global_sha256: str = field(repr=False)
    sealed_original_global_ruleset_id: str = field(repr=False)
    sealed_original_global_ruleset_name: str = field(repr=False)
    image_selection_checkpoint_sha256: str = field(repr=False)
    private_selected_image_id: str = field(repr=False)
    private_selected_ssh_key_id: str = field(repr=False)
    private_selected_ssh_key_fingerprint: str = field(repr=False)
    selected_image_alias: str
    selected_image_version: str
    require_l23_auxiliary_checkpoints: bool = False
    provider_limits: ObserverLifecycleLimits = field(default_factory=ObserverLifecycleLimits)
    clock_ns: Callable[[], int] = time.monotonic_ns
    sleeper: Callable[[float], None] = time.sleep
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC)
    budget: ObserverBudget = field(default_factory=ObserverBudget)
    lifecycle: ManualLifecycle = field(default_factory=ManualLifecycle)
    private_ruleset_id: str | None = field(default=None, repr=False)
    private_instance_id: str | None = field(default=None, repr=False)
    instance_binding_sha256: str | None = None
    stopped: bool = False
    _proof_issuer: object = field(default_factory=object, init=False, repr=False)
    _consumed_observation_ordinals: set[int] = field(default_factory=set, init=False, repr=False)
    _issued_observations: dict[int, ObservedDocument] = field(
        default_factory=dict, init=False, repr=False
    )
    _observer_started_ns: int | None = field(default=None, init=False, repr=False)
    _provider_started_ns: int | None = field(default=None, init=False, repr=False)
    _provider_terminal_ns: int | None = field(default=None, init=False, repr=False)
    _stopped_ns: int | None = field(default=None, init=False, repr=False)
    _begun: bool = field(default=False, init=False, repr=False)
    _preflight_complete: bool = field(default=False, init=False, repr=False)
    _preflight_observations: dict[ObserverOperation, ObservedDocument] = field(
        default_factory=dict, init=False, repr=False
    )
    _validated_qualification: ValidatedQualification | None = field(
        default=None, init=False, repr=False
    )
    _validated_qualification_encoded: bytes | None = field(default=None, init=False, repr=False)
    _validated_qualification_failure: ValidatedQualificationFailure | None = field(
        default=None, init=False, repr=False
    )
    _validated_qualification_failure_encoded: bytes | None = field(
        default=None, init=False, repr=False
    )
    _qualification_consumed: bool = field(default=False, init=False, repr=False)
    _incident_cleanup_only: bool = field(default=False, init=False, repr=False)
    _burned_request_ordinals: set[int] = field(default_factory=set, init=False, repr=False)
    _launch_match_state: InstanceMatchState | None = field(default=None, init=False, repr=False)
    _ambiguous_instance_ids: frozenset[str] = field(
        default_factory=frozenset, init=False, repr=False
    )
    _conservative_account_terminal: bool = field(default=False, init=False, repr=False)
    _instance_cleanup_proven: bool = field(default=False, init=False, repr=False)
    _ruleset_match_state: RulesetMatchState | None = field(default=None, init=False, repr=False)
    _ambiguous_ruleset_ids: frozenset[str] = field(
        default_factory=frozenset, init=False, repr=False
    )
    _ruleset_cleanup_required: bool = field(default=False, init=False, repr=False)
    _ruleset_cleanup_proven: bool = field(default=False, init=False, repr=False)
    _expected_observation_receipts: dict[int, tuple[str, str]] = field(
        default_factory=dict, init=False, repr=False
    )
    _durable_observation_receipts: dict[int, tuple[str, str]] = field(
        default_factory=dict, init=False, repr=False
    )
    _expected_transition_receipts: dict[str, tuple[int, str, str]] = field(
        default_factory=dict, init=False, repr=False
    )
    _durable_transition_receipts: dict[str, tuple[int, str, str]] = field(
        default_factory=dict, init=False, repr=False
    )
    _evidence_incomplete: bool = field(default=False, init=False, repr=False)
    _instance_bound_ns: int | None = field(default=None, init=False, repr=False)
    _cloud_ide_opened_ns: int | None = field(default=None, init=False, repr=False)
    _qualification_started_ns: int | None = field(default=None, init=False, repr=False)
    _qualification_completed_ns: int | None = field(default=None, init=False, repr=False)
    _termination_confirmed_ns: int | None = field(default=None, init=False, repr=False)
    _ruleset_deleted_ns: int | None = field(default=None, init=False, repr=False)
    _deadline_breached: bool = field(default=False, init=False, repr=False)
    _preflight_price_cents_per_hour: int | None = field(default=None, init=False, repr=False)
    _endpoint_schemas: Mapping[ObserverOperation, Mapping[str, object]] = field(
        default_factory=dict, init=False, repr=False
    )
    private_observation_store: PrivateObservationStore = field(init=False, repr=False)
    _expected_private_observations: dict[int, PrivateObservationBinding] = field(
        default_factory=dict, init=False, repr=False
    )
    _observation_store_failed: bool = field(default=False, init=False, repr=False)
    _checkpoint_transaction: CheckpointTransactionState | None = field(
        default=None, init=False, repr=False
    )
    _auxiliary_checkpoint_sha256: dict[str, str] = field(
        default_factory=dict, init=False, repr=False
    )
    _original_global_seal_response_sha256: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            _RUN_ID.fullmatch(self.run_id) is None
            or _AUTHORIZATION_REFERENCE.fullmatch(self.authorization_reference) is None
            or self.authorization_reference.endswith("-PENDING")
            or _SHA256.fullmatch(self.authorization_sha256) is None
            or _RULESET_NAME.fullmatch(self.private_marker_name) is None
            or _SHA256.fullmatch(self.sealed_original_global_sha256) is None
            or self.sealed_original_global_ruleset_id != "global"
            or not self.sealed_original_global_ruleset_name
            or _SHA256.fullmatch(self.image_selection_checkpoint_sha256) is None
            or _PRIVATE_ID.fullmatch(self.private_selected_image_id) is None
            or _PRIVATE_ID.fullmatch(self.private_selected_ssh_key_id) is None
            or not self.private_selected_ssh_key_fingerprint.startswith("SHA256:")
            or self.selected_image_alias != RECOMMENDED_IMAGE_ALIAS
            or self.selected_image_version != RECOMMENDED_IMAGE_VERSION
            or not is_validated_human_decision(self.human_decision)
            or self.human_decision.source_ipv4_cidr != self.source_ipv4_cidr
            or self.human_decision.repository_root != self.journal.repository_root
            or self.checkpoint_reader.repository_root != self.journal.repository_root
        ):
            raise L2MContractError("observer engine binding is invalid or pending")
        if self.budget == ObserverBudget():
            self.budget = replace(
                self.budget,
                max_wall_seconds=self.provider_limits.observer_active_seconds(
                    prelaunch_seconds=MAX_OBSERVER_PRELAUNCH_SECONDS,
                    post_provider_cleanup_seconds=MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS,
                )
                + MAX_OBSERVER_ARCHIVE_SECONDS,
            )
        elif self.budget.max_wall_seconds != self.provider_limits.observer_active_seconds(
            prelaunch_seconds=MAX_OBSERVER_PRELAUNCH_SECONDS,
            post_provider_cleanup_seconds=MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS,
        ) + MAX_OBSERVER_ARCHIVE_SECONDS:
            raise L2MContractError("observer budget and lifecycle wall differ")
        checkpoint_binding = self.checkpoint_reader.binding
        expected_marker_alias = (
            "l2m-marker-" + hashlib.sha256(self.private_marker_name.encode()).hexdigest()[:12]
        )
        if (
            checkpoint_binding.run_id != self.run_id
            or _DECISION_ALIAS.fullmatch(checkpoint_binding.decision_alias) is None
            or checkpoint_binding.decision_alias != self.human_decision.decision_alias
            or checkpoint_binding.marker_alias != expected_marker_alias
        ):
            raise L2MContractError("observer checkpoint binding differs from its engine")
        if (
            self.lifecycle.phase is not ManualPhase.PREFLIGHT
            or self.lifecycle.strict_firewall_preserved
            or self.lifecycle.incident_active
            or self.lifecycle._proof_issuer is not None
        ):
            raise L2MContractError("observer engine lifecycle must start fresh")
        self.lifecycle = ManualLifecycle.for_engine(self._proof_issuer)
        self._endpoint_schemas = MappingProxyType(
            {
                operation: _load_bound_endpoint_schema(
                    operation,
                    repository_root=self.journal.repository_root,
                )
                for operation in ObserverOperation
            }
        )
        self.private_observation_store = PrivateObservationStore.create(
            self.journal.path.with_name(f"{self.journal.path.stem}-provider-observations")
        )

    def _append_event(
        self,
        event_type: str,
        *,
        request: ObserverRequest | None = None,
        bytes_received: int = 0,
        elapsed_ms: int = 0,
        http_status: int | None = None,
        content_type: str = "none",
        sanitized_outcome: str = "not_applicable",
        request_ordinal: int | None = None,
        transport_entry_monotonic_ns: int | None = None,
        observer_phase: ObserverPhase | None = None,
        response_sha256: str | None = None,
        request_binding_sha256: str | None = None,
        checkpoint_type: str = "none",
        checkpoint_sha256: str | None = None,
        verification_kind: TransitionVerificationKind | None = None,
        evidence_sha256: str | None = None,
        source_request_ordinal: int = 0,
        semantic_outcome: str = "none",
        semantic_count: int | None = None,
    ) -> None:
        operation = "none" if request is None else request.operation.value
        self.journal.append(
            {
                "schema_version": "0.1.0",
                "run_id": self.run_id,
                "authorization_reference": self.authorization_reference,
                "authorization_sha256": self.authorization_sha256,
                "human_decision_sha256": self.human_decision.decision_sha256,
                "event_sequence": self.journal.next_sequence,
                "event_type": event_type,
                "monotonic_timestamp_ns": self.clock_ns(),
                "transport_entry_monotonic_ns": transport_entry_monotonic_ns,
                "wall_timestamp_utc": self.utc_now()
                .astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "operation": operation,
                "observer_phase": ("none" if observer_phase is None else observer_phase.value),
                "request_ordinal": 0
                if request is None
                else (
                    self.budget.request_count + 1 if request_ordinal is None else request_ordinal
                ),
                "method": "none" if request is None else request.method,
                "host": "none" if request is None else request.host,
                "path_template": "none" if request is None else _observer_path_template(request),
                "transport_kind": "none" if request is None else "in-process-https",
                "bytes_received": min(bytes_received, MAX_RESPONSE_BYTES_PER_GET),
                "elapsed_ms": min(
                    elapsed_ms,
                    (
                        self.provider_limits.observer_active_seconds(
                            prelaunch_seconds=MAX_OBSERVER_PRELAUNCH_SECONDS,
                            post_provider_cleanup_seconds=(
                                MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS
                            ),
                        )
                        + MAX_OBSERVER_ARCHIVE_SECONDS
                    )
                    * 1_000,
                ),
                "http_status": http_status,
                "content_type": content_type,
                "sanitized_outcome": sanitized_outcome,
                "response_sha256": response_sha256,
                "request_binding_sha256": request_binding_sha256,
                "checkpoint_type": checkpoint_type,
                "checkpoint_sha256": checkpoint_sha256,
                "verification_kind": (
                    "none" if verification_kind is None else verification_kind.value
                ),
                "evidence_sha256": evidence_sha256,
                "source_request_ordinal": source_request_ordinal,
                "semantic_outcome": semantic_outcome,
                "semantic_count": semantic_count,
                "retry_count": 0,
                "pagination_request": False,
            }
        )

    def begin(self) -> None:
        if self.stopped or self._begun or self.journal.events_written:
            raise L2MContractError("observer preflight cannot be reused")
        self._observer_started_ns = self.clock_ns()
        self._begun = True
        self._append_event("preflight_started")

    def _check_timeline(self, now_ns: int, *, cleanup_allowed: bool) -> None:
        if self._observer_started_ns is None or now_ns < self._observer_started_ns:
            raise L2MContractError("observer monotonic lifecycle is unavailable")
        if (
            now_ns - self._observer_started_ns
            > self.provider_limits.observer_active_seconds(
                prelaunch_seconds=MAX_OBSERVER_PRELAUNCH_SECONDS,
                post_provider_cleanup_seconds=MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS,
            )
            * 1_000_000_000
        ):
            raise L2MContractError("observer active wall cap exhausted")
        if self._provider_started_ns is None:
            if now_ns - self._observer_started_ns > MAX_OBSERVER_PRELAUNCH_SECONDS * 1_000_000_000:
                raise L2MContractError("observer prelaunch wall cap exhausted")
            return
        if self._provider_terminal_ns is not None:
            if (
                now_ns - self._provider_terminal_ns
                > MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS * 1_000_000_000
            ):
                raise L2MContractError("observer post-provider cleanup wall cap exhausted")
            return
        provider_elapsed_ns = now_ns - self._provider_started_ns
        if (
            provider_elapsed_ns
            > self.provider_limits.campaign_provider_wall_seconds * 1_000_000_000
        ):
            if not cleanup_allowed:
                raise L2MContractError("provider wall cap permits cleanup observations only")
            if (
                provider_elapsed_ns
                > (
                    self.provider_limits.campaign_provider_wall_seconds
                    + MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS
                )
                * 1_000_000_000
            ):
                raise L2MContractError("provider cleanup observation reserve exhausted")

    def _reject_late_normal_progression(self, reason: str) -> None:
        self._deadline_breached = True
        self._activate_cleanup_incident(None)
        try:
            self._append_event("manual_incident", sanitized_outcome="timeout")
        except L2MContractError:
            self._evidence_incomplete = True
        raise L2MDeadlineError(reason)

    def _enforce_observation_deadline(self, phase: ObserverPhase, now_ns: int) -> None:
        if phase in _CLEANUP_OBSERVER_PHASES or self._provider_started_ns is None:
            return
        provider_elapsed = now_ns - self._provider_started_ns
        if (
            provider_elapsed
            > self.provider_limits.normal_termination_cutoff_seconds * 1_000_000_000
        ):
            self._reject_late_normal_progression(
                "normal provider window expired; cleanup observations only"
            )
        if (
            phase is ObserverPhase.INSTANCE_BIND
            and provider_elapsed > LAUNCH_TO_ACTIVE_SECONDS * 1_000_000_000
        ):
            self._reject_late_normal_progression(
                "launch-to-active deadline expired; cleanup observations only"
            )

    def _enforce_transition_deadline(self, requested: ManualPhase, now_ns: int) -> None:
        cleanup_types = {
            ManualPhase.TERMINATION_CONFIRMED,
            ManualPhase.INSTANCE_TERMINAL,
            ManualPhase.RULESET_DELETED,
            ManualPhase.GLOBAL_RESTORED,
        }
        if self._provider_started_ns is not None and requested not in cleanup_types:
            provider_elapsed = now_ns - self._provider_started_ns
            if (
                provider_elapsed
                > self.provider_limits.normal_termination_cutoff_seconds * 1_000_000_000
            ):
                self._reject_late_normal_progression(
                    "normal provider window expired; cleanup checkpoints only"
                )
        if requested is ManualPhase.INSTANCE_BOUND:
            if (
                self._provider_started_ns is None
                or now_ns - self._provider_started_ns > LAUNCH_TO_ACTIVE_SECONDS * 1_000_000_000
            ):
                self._reject_late_normal_progression("launch-to-active checkpoint deadline expired")
        elif requested is ManualPhase.CLOUD_IDE_OPENED:
            if (
                self._instance_bound_ns is None
                or now_ns - self._instance_bound_ns > CLOUD_IDE_AVAILABILITY_SECONDS * 1_000_000_000
            ):
                self._reject_late_normal_progression(
                    "Cloud IDE availability checkpoint deadline expired"
                )
        elif requested is ManualPhase.QUALIFICATION_STARTED:
            required_headroom_seconds = (
                JUPYTER_QUALIFICATION_SECONDS + EVIDENCE_DOWNLOAD_VALIDATION_SECONDS
            )
            if (
                self._provider_started_ns is None
                or now_ns - self._provider_started_ns
                > (
                    self.provider_limits.normal_termination_cutoff_seconds
                    - required_headroom_seconds
                )
                * 1_000_000_000
            ):
                self._reject_late_normal_progression(
                    "qualification start lacks provider-window cleanup headroom"
                )
        elif requested is ManualPhase.QUALIFICATION_COMPLETED:
            if (
                self._qualification_started_ns is None
                or now_ns - self._qualification_started_ns
                > JUPYTER_QUALIFICATION_SECONDS * 1_000_000_000
            ):
                self._reject_late_normal_progression("qualification command deadline expired")
        elif requested is ManualPhase.BUNDLE_DOWNLOADED:
            if (
                self._qualification_completed_ns is None
                or now_ns - self._qualification_completed_ns
                > EVIDENCE_DOWNLOAD_VALIDATION_SECONDS * 1_000_000_000
            ):
                self._reject_late_normal_progression(
                    "qualification evidence download/validation deadline expired"
                )
        elif requested is ManualPhase.TERMINATION_CONFIRMED:
            if (
                self._provider_started_ns is not None
                and now_ns - self._provider_started_ns
                > self.provider_limits.normal_termination_cutoff_seconds * 1_000_000_000
            ):
                self._deadline_breached = True
                self._incident_cleanup_only = True
        elif requested is ManualPhase.INSTANCE_TERMINAL:
            if (
                self._termination_confirmed_ns is not None
                and now_ns - self._termination_confirmed_ns
                > TERMINATION_VERIFICATION_SECONDS * 1_000_000_000
            ):
                self._deadline_breached = True
                self._incident_cleanup_only = True
        elif (
            requested in {ManualPhase.RULESET_DELETED, ManualPhase.GLOBAL_RESTORED}
            and self._provider_terminal_ns is not None
            and now_ns - self._provider_terminal_ns > FIREWALL_CLEANUP_SECONDS * 1_000_000_000
        ):
            self._deadline_breached = True
            self._incident_cleanup_only = True

    def _remaining_request_seconds(self, now_ns: int, *, cleanup_allowed: bool) -> float:
        deadline_ns = self._request_deadline_ns(now_ns, cleanup_allowed=cleanup_allowed)
        return (deadline_ns - now_ns) / 1_000_000_000

    def _request_deadline_ns(self, now_ns: int, *, cleanup_allowed: bool) -> int:
        self._check_timeline(now_ns, cleanup_allowed=cleanup_allowed)
        if self._observer_started_ns is None:  # pragma: no cover - guarded above
            raise L2MContractError("observer monotonic lifecycle is unavailable")
        deadlines = [
            self._observer_started_ns
            + self.provider_limits.observer_active_seconds(
                prelaunch_seconds=MAX_OBSERVER_PRELAUNCH_SECONDS,
                post_provider_cleanup_seconds=MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS,
            )
            * 1_000_000_000
        ]
        if self._provider_started_ns is None:
            deadlines.append(
                self._observer_started_ns + MAX_OBSERVER_PRELAUNCH_SECONDS * 1_000_000_000
            )
        elif self._provider_terminal_ns is not None:
            deadlines.append(
                self._provider_terminal_ns
                + MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS * 1_000_000_000
            )
        else:
            provider_seconds = self.provider_limits.campaign_provider_wall_seconds + (
                MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS if cleanup_allowed else 0
            )
            deadlines.append(self._provider_started_ns + provider_seconds * 1_000_000_000)
        deadline_ns = min(
            *deadlines,
            now_ns + MAX_OBSERVER_REQUEST_SECONDS * 1_000_000_000,
        )
        remaining_ns = deadline_ns - now_ns
        if remaining_ns <= 0:
            raise L2MContractError("observer phase deadline is exhausted")
        return deadline_ns

    def _qualification_validation_remaining_seconds(self) -> float:
        """Return the hard local-validation window within normal provider headroom."""

        now_ns = self.clock_ns()
        if (
            self._qualification_completed_ns is None
            or self._provider_started_ns is None
            or self._observer_started_ns is None
        ):
            raise L2MContractError("qualification validation deadline is unavailable")
        deadline_ns = min(
            self._qualification_completed_ns + EVIDENCE_DOWNLOAD_VALIDATION_SECONDS * 1_000_000_000,
            self._provider_started_ns
            + self.provider_limits.normal_termination_cutoff_seconds * 1_000_000_000,
            self._observer_started_ns
            + self.provider_limits.observer_active_seconds(
                prelaunch_seconds=MAX_OBSERVER_PRELAUNCH_SECONDS,
                post_provider_cleanup_seconds=MAX_OBSERVER_POST_PROVIDER_CLEANUP_SECONDS,
            )
            * 1_000_000_000,
        )
        remaining_ns = deadline_ns - now_ns
        if remaining_ns <= 0:
            self._reject_late_normal_progression(
                "qualification evidence download/validation deadline expired"
            )
        return remaining_ns / 1_000_000_000

    def _validate_and_complete_preflight(self, observation: ObservedDocument) -> bool:
        expected_order = (
            ObserverOperation.LIST_IMAGES,
            ObserverOperation.LIST_INSTANCE_TYPES,
            ObserverOperation.LIST_SSH_KEYS,
            ObserverOperation.LIST_INSTANCES,
            ObserverOperation.LIST_RULESETS,
            ObserverOperation.GET_GLOBAL_FIREWALL,
        )
        index = len(self._preflight_observations)
        if index >= len(expected_order) or observation.operation is not expected_order[index]:
            raise L2MContractError("observer preflight operation order drifted")
        self._preflight_observations[observation.operation] = observation
        if len(self._preflight_observations) < len(expected_order):
            return False

        image_rows = [
            _mapping(item, context="preflight image")
            for item in _sequence(
                self._preflight_observations[ObserverOperation.LIST_IMAGES].data,
                context="preflight images",
            )
            if _mapping(item, context="preflight image").get("id") == self.private_selected_image_id
        ]
        if not image_rows:
            raise L2MContractError("selected private image ID is absent during preflight")
        selected_regions: set[str] = set()
        for row in image_rows:
            region = _mapping(row.get("region"), context="preflight image region")
            selected_regions.add(_string(region.get("name"), context="preflight image region"))
            if (
                row.get("family") != REQUIRED_IMAGE_FAMILY
                or row.get("version") != self.selected_image_version
                or row.get("architecture") != SELECTED_ARCHITECTURE
            ):
                raise L2MContractError("selected private image metadata drifted")
        if SELECTED_REGION not in selected_regions:
            raise L2MContractError("selected private image region drifted")
        instance_types = _mapping(
            self._preflight_observations[ObserverOperation.LIST_INSTANCE_TYPES].data,
            context="preflight instance types",
        )
        if SELECTED_INSTANCE_TYPE not in instance_types:
            raise L2MContractError("selected instance type is absent from inventory")
        selected_type = _mapping(
            instance_types.get(SELECTED_INSTANCE_TYPE),
            context="preflight selected instance type",
        )
        instance_type = _mapping(
            selected_type.get("instance_type"),
            context="preflight selected instance type details",
        )
        capacity_regions = _sequence(
            selected_type.get("regions_with_capacity_available"),
            context="preflight selected instance type capacity",
        )
        region_names = {
            _string(
                _mapping(item, context="preflight capacity region").get("name"),
                context="preflight capacity region name",
            )
            for item in capacity_regions
        }
        if (
            instance_type.get("name") != SELECTED_INSTANCE_TYPE
            or instance_type.get("architecture") != SELECTED_ARCHITECTURE
            or instance_type.get("price_cents_per_hour") != OBSERVED_PRICE_CENTS_PER_HOUR
            or SELECTED_REGION not in region_names
        ):
            raise L2MContractError("selected instance price, architecture, or capacity drifted")
        self._preflight_price_cents_per_hour = OBSERVED_PRICE_CENTS_PER_HOUR
        selected_ssh_keys = [
            _mapping(item, context="preflight SSH key")
            for item in _sequence(
                self._preflight_observations[ObserverOperation.LIST_SSH_KEYS].data,
                context="preflight SSH keys",
            )
            if _mapping(item, context="preflight SSH key").get("name") == SELECTED_SSH_KEY_NAME
        ]
        current_fingerprint: str | None = None
        if len(selected_ssh_keys) == 1:
            public_key = selected_ssh_keys[0].get("public_key")
            try:
                current_fingerprint = parse_public_key(str(public_key)).fingerprint
            except (SSHKeyFingerprintError, ValueError):
                current_fingerprint = None
        if (
            len(selected_ssh_keys) != 1
            or selected_ssh_keys[0].get("id") != self.private_selected_ssh_key_id
            or current_fingerprint != self.private_selected_ssh_key_fingerprint
        ):
            raise L2MContractError("selected SSH key identity or name drifted")
        require_zero_prelaunch_instances(
            self._preflight_observations[ObserverOperation.LIST_INSTANCES].data
        )
        preflight_rulesets = _sequence(
            self._preflight_observations[ObserverOperation.LIST_RULESETS].data,
            context="preflight rulesets",
        )
        if any(
            _mapping(item, context="preflight ruleset").get("name") == self.private_marker_name
            for item in preflight_rulesets
        ):
            raise L2MContractError("preflight ruleset marker is not fresh")
        global_data = _mapping(
            self._preflight_observations[ObserverOperation.GET_GLOBAL_FIREWALL].data,
            context="preflight global firewall",
        )
        verify_global_firewall_restoration(
            global_data,
            sealed_original_ruleset_id=self.sealed_original_global_ruleset_id,
            sealed_original_ruleset_name=self.sealed_original_global_ruleset_name,
            sealed_original_semantic_sha256=self.sealed_original_global_sha256,
        )
        self._preflight_complete = True
        return True

    def seal_original_global_firewall(self, observation: ObservedDocument) -> str:
        """Durably bind a fresh post-offeredness baseline before user mutation.

        The earlier preflight observation proves initial consistency, but the user may
        spend up to one checkpoint window in the launch wizard.  This distinct read
        closes that interval and must be durably journaled before the supervisor may
        expose the global-firewall replacement challenge.
        """

        if (
            self.stopped
            or not self._preflight_complete
            or self.lifecycle.phase is not ManualPhase.PREFLIGHT
            or "launch_wizard_image_offered" not in self._auxiliary_checkpoint_sha256
            or self._original_global_seal_response_sha256 is not None
        ):
            raise L2MContractError("original global firewall seal is out of order")
        observed = self._trusted_observation(
            observation,
            ObserverOperation.GET_GLOBAL_FIREWALL,
            frozenset({ObserverPhase.ORIGINAL_GLOBAL_SEAL}),
        )
        global_data = _mapping(observed.data, context="fresh original global firewall")
        verify_global_firewall_restoration(
            global_data,
            sealed_original_ruleset_id=self.sealed_original_global_ruleset_id,
            sealed_original_ruleset_name=self.sealed_original_global_ruleset_name,
            sealed_original_semantic_sha256=self.sealed_original_global_sha256,
        )
        try:
            self.journal.reserve_capacity(
                events=1,
                bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES,
            )
            self._append_event(
                "evidence_sealed",
                request=observer_request(ObserverOperation.GET_GLOBAL_FIREWALL),
                observer_phase=ObserverPhase.ORIGINAL_GLOBAL_SEAL,
                request_ordinal=observed.request_ordinal,
                response_sha256=observed.response_sha256,
                request_binding_sha256=observed.request_binding_sha256,
                evidence_sha256=self.sealed_original_global_sha256,
                source_request_ordinal=observed.request_ordinal,
                semantic_outcome="original_global_firewall_sealed",
                semantic_count=1,
                sanitized_outcome="passed",
            )
            self._consume_trusted_observation(observed)
        except L2MContractError:
            self._evidence_incomplete = True
            raise L2MContractError("original global firewall seal was not durable") from None
        self._original_global_seal_response_sha256 = observed.response_sha256
        return observed.response_sha256

    def _stop_after_send(
        self,
        *,
        request: ObserverRequest,
        phase: ObserverPhase,
        request_ordinal: int,
        sanitized_outcome: str,
        bytes_received: int = 0,
        elapsed_ms: int = 0,
        http_status: int | None = None,
        content_type: str = "none",
        transport_entry_monotonic_ns: int | None = None,
        response_sha256: str | None = None,
        request_binding_sha256: str | None = None,
    ) -> None:
        """Burn one ordinal and retain rollback authority after any possible mutation."""

        retain_cleanup = self._must_retain_cleanup(phase)
        if retain_cleanup:
            self._activate_cleanup_incident(phase)
        try:
            self._burned_request_ordinals.add(request_ordinal)
            self._append_event(
                "observation_failed",
                request=request,
                bytes_received=bytes_received,
                elapsed_ms=elapsed_ms,
                http_status=http_status,
                content_type=content_type,
                sanitized_outcome=sanitized_outcome,
                request_ordinal=request_ordinal,
                transport_entry_monotonic_ns=transport_entry_monotonic_ns,
                observer_phase=phase,
                response_sha256=response_sha256,
                request_binding_sha256=request_binding_sha256,
            )
            if retain_cleanup:
                self._append_event("manual_incident", sanitized_outcome=sanitized_outcome)
                return
            self._append_event("run_stopped", sanitized_outcome=sanitized_outcome)
        except BaseException:
            self._evidence_incomplete = True
            if self.journal.append_outcome_unknown:
                if not self.stopped:
                    self._finalize_stopped_run()
                raise L2MContractError(
                    "observer journal outcome is unknown; run identity is burned"
                ) from None
            if retain_cleanup:
                return
            self._finalize_stopped_run()
            raise
        self._finalize_stopped_run()

    def _stop_before_send(
        self,
        *,
        prepared: ObserverReservation,
        phase: ObserverPhase,
        sanitized_outcome: str,
    ) -> None:
        """Burn a prepared run when its durable pre-send control path fails."""

        if self.budget.request_count < prepared.request_ordinal:
            self.budget = self.budget.burn(prepared)
        elif self.budget.request_count != prepared.request_ordinal:
            raise L2MContractError("observer pre-send ordinal drifted")
        self._burned_request_ordinals.add(prepared.request_ordinal)
        retain_cleanup = self._must_retain_cleanup(phase)
        if retain_cleanup:
            self._activate_cleanup_incident(phase)
            try:
                self._append_event("manual_incident", sanitized_outcome=sanitized_outcome)
            except BaseException:
                self._evidence_incomplete = True
                if self.journal.append_outcome_unknown and not self.stopped:
                    self._finalize_stopped_run()
            return
        try:
            self._append_event("run_stopped", sanitized_outcome=sanitized_outcome)
        finally:
            self._finalize_stopped_run()

    def _stop_at_transport_boundary(
        self,
        *,
        prepared: ObserverReservation,
        phase: ObserverPhase,
        transport_entry_monotonic_ns: int,
        sanitized_outcome: str,
    ) -> None:
        """Burn an ordinal that crossed send-start but never entered transport."""

        if self.budget.request_count < prepared.request_ordinal:
            self.budget = self.budget.burn(prepared)
        elif self.budget.request_count != prepared.request_ordinal:
            raise L2MContractError("observer transport-boundary ordinal drifted")
        self._stop_after_send(
            request=prepared.request,
            phase=phase,
            request_ordinal=prepared.request_ordinal,
            transport_entry_monotonic_ns=transport_entry_monotonic_ns,
            sanitized_outcome=sanitized_outcome,
        )

    def _finalize_stopped_run(self) -> None:
        self.stopped = True
        self._stopped_ns = self.clock_ns()
        finalization_errors: list[BaseException] = []
        try:
            self.checkpoint_reader.close()
        except BaseException as error:  # all local evidence handles must still close
            finalization_errors.append(error)
        try:
            self.private_observation_store.close()
        except BaseException as error:
            finalization_errors.append(error)
        try:
            self.journal.close()
        except BaseException as error:
            finalization_errors.append(error)
        if not finalization_errors and (
            not self.checkpoint_reader.final_evidence.complete
            or not self.private_observation_store.final_evidence.complete
            or not self.journal.final_evidence.complete
        ):
            self._evidence_incomplete = True
        if finalization_errors:
            self._evidence_incomplete = True
            raise L2MContractError("observer local evidence finalization failed") from None

    def observe(
        self,
        operation: ObserverOperation,
        *,
        phase: ObserverPhase,
        credential: str,
        private_resource_id: str | None = None,
    ) -> ObservedDocument:
        if (
            self.stopped
            or self._observation_store_failed
            or not self._begun
            or self.journal.events_written < 1
        ):
            raise L2MContractError("observer is not in one active run")
        if self._incident_cleanup_only and phase not in _CLEANUP_OBSERVER_PHASES:
            raise L2MContractError("observer incident freezes all non-cleanup observations")
        if self.lifecycle.incident_active and phase is not ObserverPhase.INCIDENT:
            raise L2MContractError("active incident permits only incident observations")
        preflight_order = (
            ObserverOperation.LIST_IMAGES,
            ObserverOperation.LIST_INSTANCE_TYPES,
            ObserverOperation.LIST_SSH_KEYS,
            ObserverOperation.LIST_INSTANCES,
            ObserverOperation.LIST_RULESETS,
            ObserverOperation.GET_GLOBAL_FIREWALL,
        )
        if not self._preflight_complete:
            index = len(self._preflight_observations)
            if (
                phase is not ObserverPhase.PREFLIGHT
                or index >= len(preflight_order)
                or operation is not preflight_order[index]
            ):
                raise L2MContractError("observer preflight must complete in exact order")
        elif phase is ObserverPhase.PREFLIGHT:
            raise L2MContractError("observer preflight phase cannot be replayed")
        if (
            not credential
            or len(credential) > 4_096
            or any(marker in credential for marker in ("\r", "\n", "\x00"))
        ):
            raise L2MContractError("observer credential presence contract failed")
        request = observer_request(operation, private_resource_id=private_resource_id)
        now_ns = self.clock_ns()
        if self.budget.last_start_monotonic_ns is not None:
            spacing_ns = MIN_REQUEST_SPACING_SECONDS * 1_000_000_000
            remaining_ns = spacing_ns - (now_ns - self.budget.last_start_monotonic_ns)
            if remaining_ns > 0:
                self.sleeper(remaining_ns / 1_000_000_000)
                now_ns = self.clock_ns()
        self._enforce_observation_deadline(phase, now_ns)
        cleanup_allowed = phase in _CLEANUP_OBSERVER_PHASES
        self._remaining_request_seconds(now_ns, cleanup_allowed=cleanup_allowed)
        self.journal.reserve_capacity(
            events=4,
            bytes_upper_bound=4 * MAX_OBSERVER_EVENT_BYTES,
        )
        prepared = self.budget.prepare(request, phase=phase)
        self.private_observation_store.reserve_capacity(
            maximum_response_bytes=prepared.response_byte_limit
        )
        request_ordinal = prepared.request_ordinal
        request_binding_sha256 = hashlib.sha256(
            json.dumps(
                {
                    "authorization_reference": self.authorization_reference,
                    "authorization_sha256": self.authorization_sha256,
                    "operation": operation.value,
                    "path": request.path,
                    "phase": phase.value,
                    "request_ordinal": request_ordinal,
                    "run_id": self.run_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if request_ordinal in self._burned_request_ordinals:
            raise L2MContractError("observer request ordinal was already burned")
        try:
            self._append_event(
                "observation_intent_committed",
                request=request,
                request_ordinal=request_ordinal,
                observer_phase=phase,
            )
            self._remaining_request_seconds(self.clock_ns(), cleanup_allowed=cleanup_allowed)
            self._append_event(
                "observation_send_started",
                request=request,
                request_ordinal=request_ordinal,
                observer_phase=phase,
            )
        except L2MContractError as error:
            self._stop_before_send(
                prepared=prepared,
                phase=phase,
                sanitized_outcome=("timeout" if "deadline" in str(error) else "privacy_failure"),
            )
            raise L2MContractError("observer stopped before transport entry") from None
        transport_entry_ns = self.clock_ns()
        try:
            self.budget, reservation = self.budget.start(
                prepared,
                started_monotonic_ns=transport_entry_ns,
            )
            absolute_deadline_ns = self._request_deadline_ns(
                transport_entry_ns,
                cleanup_allowed=cleanup_allowed,
            )
        except L2MContractError as error:
            self._stop_at_transport_boundary(
                prepared=prepared,
                phase=phase,
                transport_entry_monotonic_ns=transport_entry_ns,
                sanitized_outcome=("timeout" if "deadline" in str(error) else "privacy_failure"),
            )
            raise L2MContractError("observer stopped at transport boundary") from None
        timeout_seconds = (absolute_deadline_ns - transport_entry_ns) / 1_000_000_000
        try:
            response = self.transport.send(
                request,
                credential=credential,
                timeout_seconds=timeout_seconds,
                absolute_deadline_monotonic_ns=absolute_deadline_ns,
                max_response_bytes=reservation.response_byte_limit,
            )
        except ObserverTransportFailure as failure:
            finished_ns = self.clock_ns()
            with contextlib.suppress(L2MContractError):
                self.budget = self.budget.complete(
                    reservation,
                    response_bytes=min(failure.bytes_received, reservation.response_byte_limit),
                    finished_monotonic_ns=finished_ns,
                )
            self._stop_after_send(
                request=request,
                phase=phase,
                bytes_received=failure.bytes_received,
                elapsed_ms=failure.elapsed_ms,
                sanitized_outcome=("timeout" if failure.stage == "deadline" else "provider_outage"),
                request_ordinal=request_ordinal,
                transport_entry_monotonic_ns=transport_entry_ns,
            )
            raise L2MContractError("observer transport failed with a sanitized class") from None
        except BaseException:
            finished_ns = self.clock_ns()
            with contextlib.suppress(L2MContractError):
                self.budget = self.budget.complete(
                    reservation,
                    response_bytes=0,
                    finished_monotonic_ns=finished_ns,
                )
            try:
                self._stop_after_send(
                    request=request,
                    phase=phase,
                    sanitized_outcome="outcome_unknown",
                    request_ordinal=request_ordinal,
                    transport_entry_monotonic_ns=transport_entry_ns,
                    request_binding_sha256=request_binding_sha256,
                )
            except BaseException:
                # Preserve the caller's interrupt/crash signal.  Receipt failure is
                # separately reflected in evidence completeness and must never mask
                # the fact that the network outcome became unknown after send-start.
                self._evidence_incomplete = True
                if not self._must_retain_cleanup(phase) and not self.stopped:
                    with contextlib.suppress(BaseException):
                        self._finalize_stopped_run()
            raise

        finished_ns = self.clock_ns()
        outcome = "schema_failure"
        response_sha256: str | None = None
        if response.status == 200 and response.content_type == "application/json":
            credential_bytes = credential.encode("utf-8", "strict")
            if credential_bytes in response.body:
                self._observation_store_failed = True
                self._evidence_incomplete = True
                with contextlib.suppress(L2MContractError):
                    self.budget = self.budget.complete(
                        reservation,
                        response_bytes=min(len(response.body), reservation.response_byte_limit),
                        finished_monotonic_ns=finished_ns,
                    )
                self._stop_after_send(
                    request=request,
                    phase=phase,
                    bytes_received=len(response.body),
                    elapsed_ms=response.elapsed_ms,
                    http_status=response.status,
                    content_type="application/json",
                    sanitized_outcome="privacy_failure",
                    request_ordinal=request_ordinal,
                    transport_entry_monotonic_ns=transport_entry_ns,
                    request_binding_sha256=request_binding_sha256,
                )
                raise L2MContractError("observer response failed secret non-retention")
            response_sha256 = hashlib.sha256(response.body).hexdigest()
        try:
            self.budget = self.budget.complete(
                reservation,
                response_bytes=len(response.body),
                finished_monotonic_ns=finished_ns,
            )
            if response.elapsed_ms > math.ceil(timeout_seconds * 1_000):
                outcome = "timeout"
                raise L2MContractError("observer end-to-end request deadline exceeded")
            self._check_timeline(finished_ns, cleanup_allowed=cleanup_allowed)
            if 300 <= response.status <= 399:
                outcome = "http_failure"
                raise L2MContractError("observer redirect is forbidden")
            if response.status != 200:
                outcome = "http_failure"
                raise L2MContractError("observer HTTP status is not successful")
            if response.content_type != "application/json":
                raise L2MContractError("observer content type is not JSON")
            data = _observer_data(
                request,
                response.body,
                schemas=self._endpoint_schemas,
            )
            if response_sha256 is None:  # pragma: no cover - status/type checks above
                raise L2MContractError("observer response identity is unavailable")
        except L2MContractError as error:
            if "pagination" in str(error):
                outcome = "pagination_stop"
            self._stop_after_send(
                request=request,
                phase=phase,
                bytes_received=len(response.body),
                elapsed_ms=response.elapsed_ms,
                http_status=response.status,
                content_type=(
                    "application/json"
                    if response.content_type == "application/json"
                    else "unexpected"
                ),
                sanitized_outcome=outcome,
                request_ordinal=request_ordinal,
                transport_entry_monotonic_ns=transport_entry_ns,
                response_sha256=response_sha256,
                request_binding_sha256=request_binding_sha256,
            )
            raise
        try:
            private_projection = _encode_private_observation_projection(
                operation,
                data,
                raw_response_sha256=response_sha256,
                raw_response_bytes=len(response.body),
            )
            private_record = self.private_observation_store.write(
                request_ordinal,
                private_projection,
            )
            self._expected_private_observations[request_ordinal] = PrivateObservationBinding(
                operation,
                private_record.byte_count,
                private_record.sha256,
                len(response.body),
                response_sha256,
            )
        except BaseException as error:
            self._observation_store_failed = True
            self._evidence_incomplete = True
            try:
                self._stop_after_send(
                    request=request,
                    phase=phase,
                    bytes_received=len(response.body),
                    elapsed_ms=response.elapsed_ms,
                    http_status=response.status,
                    content_type="application/json",
                    sanitized_outcome=(
                        "privacy_failure"
                        if isinstance(error, L2MContractError)
                        else "outcome_unknown"
                    ),
                    request_ordinal=request_ordinal,
                    transport_entry_monotonic_ns=transport_entry_ns,
                    response_sha256=response_sha256,
                    request_binding_sha256=request_binding_sha256,
                )
            except BaseException:
                self._evidence_incomplete = True
            if not isinstance(error, L2MContractError):
                raise
            raise L2MContractError(
                "observer private response projection could not be committed"
            ) from None
        try:
            observed = ObservedDocument(
                self.run_id,
                self.authorization_reference,
                operation,
                phase,
                request_ordinal,
                data,
                response_sha256,
                len(response.body),
                response.status,
                response.elapsed_ms,
                request_binding_sha256,
                self._proof_issuer,
            )
            preflight_completed = False
            if phase is ObserverPhase.PREFLIGHT:
                preflight_completed = self._validate_and_complete_preflight(observed)
        except L2MContractError:
            self._stop_after_send(
                request=request,
                phase=phase,
                bytes_received=len(response.body),
                elapsed_ms=response.elapsed_ms,
                http_status=response.status,
                content_type=(
                    "application/json"
                    if response.content_type == "application/json"
                    else "unexpected"
                ),
                sanitized_outcome="schema_failure",
                request_ordinal=request_ordinal,
                transport_entry_monotonic_ns=transport_entry_ns,
                response_sha256=response_sha256,
                request_binding_sha256=request_binding_sha256,
            )
            raise
        receipt_identity = (observed.response_sha256, observed.request_binding_sha256)
        self._expected_observation_receipts[request_ordinal] = receipt_identity
        semantic_count = (
            len(observed.data)
            if isinstance(observed.data, list)
            else (
                len(observed.data.get("rules", []))
                if isinstance(observed.data, Mapping)
                and isinstance(observed.data.get("rules"), list)
                else 1
            )
        )
        try:
            self._append_event(
                "observation_completed",
                request=request,
                bytes_received=len(response.body),
                elapsed_ms=response.elapsed_ms,
                http_status=response.status,
                content_type="application/json",
                sanitized_outcome="passed",
                request_ordinal=request_ordinal,
                transport_entry_monotonic_ns=transport_entry_ns,
                observer_phase=phase,
                response_sha256=observed.response_sha256,
                request_binding_sha256=observed.request_binding_sha256,
                source_request_ordinal=request_ordinal,
                semantic_outcome="schema_valid",
                semantic_count=semantic_count,
            )
            self._durable_observation_receipts[request_ordinal] = receipt_identity
            if preflight_completed:
                self._append_event("preflight_passed", sanitized_outcome="passed")
        except L2MContractError:
            self._stop_after_send(
                request=request,
                phase=phase,
                request_ordinal=request_ordinal,
                sanitized_outcome="outcome_unknown",
                bytes_received=len(response.body),
                elapsed_ms=response.elapsed_ms,
                http_status=response.status,
                content_type="application/json",
                transport_entry_monotonic_ns=transport_entry_ns,
                response_sha256=response_sha256,
                request_binding_sha256=request_binding_sha256,
            )
            raise L2MContractError("observer terminal ledger failed after send") from None
        self._issued_observations[request_ordinal] = observed
        return observed

    def _trusted_observation(
        self,
        observation: ObservedDocument | None,
        operation: ObserverOperation,
        phases: frozenset[ObserverPhase],
    ) -> ObservedDocument:
        if (
            observation is None
            or observation._issuer is not self._proof_issuer
            or observation.run_id != self.run_id
            or observation.authorization_reference != self.authorization_reference
            or observation.operation is not operation
            or observation.phase not in phases
            or not 1 <= observation.request_ordinal <= self.budget.request_count
            or _SHA256.fullmatch(observation.request_binding_sha256) is None
            or self._issued_observations.get(observation.request_ordinal) is not observation
            or observation.request_ordinal in self._consumed_observation_ordinals
        ):
            raise L2MContractError("transition lacks an engine-issued observation")
        return observation

    def _consume_trusted_observation(self, observation: ObservedDocument | None) -> None:
        if observation is None:
            return
        if observation.request_ordinal in self._consumed_observation_ordinals:
            raise L2MContractError("transition observation was already consumed")
        self._consumed_observation_ordinals.add(observation.request_ordinal)

    def _activate_cleanup_incident(self, phase: ObserverPhase | None) -> None:
        """Preserve rollback authority after any possible user mutation."""

        if phase is ObserverPhase.GLOBAL_RESTRICTED_VERIFY:
            self.lifecycle = self.lifecycle.mutation_risk(ManualPhase.GLOBAL_MUTATION_UNVERIFIED)
        elif phase is ObserverPhase.RULESET_BIND:
            self._ruleset_cleanup_required = True
            self.lifecycle = self.lifecycle.mutation_risk(ManualPhase.RULESET_MUTATION_UNVERIFIED)
        elif not self.lifecycle.incident_active:
            self.lifecycle = self.lifecycle.incident()
        self._incident_cleanup_only = True

    def _activate_launch_uncertain(self, now_ns: int | None = None) -> None:
        """Retain the marker and assume billing may have started after any launch ambiguity."""

        observed_ns = self.clock_ns() if now_ns is None else now_ns
        conservative_anchor = max(
            self._observer_started_ns or 0,
            observed_ns - MAX_USER_CHECKPOINT_SECONDS * 1_000_000_000,
        )
        if self._provider_started_ns is None:
            self._provider_started_ns = conservative_anchor
        else:
            self._provider_started_ns = min(self._provider_started_ns, conservative_anchor)
        self.lifecycle = self.lifecycle.mutation_risk(ManualPhase.LAUNCH_OUTCOME_UNVERIFIED)
        self._incident_cleanup_only = True

    def arm_launch_window(self) -> None:
        """Durably enter the billable-risk window before the user may click Launch."""

        if (
            self.stopped
            or not self._preflight_complete
            or self.lifecycle.phase is not ManualPhase.RULESET_CREATED
            or self._provider_started_ns is not None
            or (
                self.require_l23_auxiliary_checkpoints
                and "launch_configuration_selected" not in self._auxiliary_checkpoint_sha256
            )
        ):
            raise L2MContractError("launch window cannot be armed in the current state")
        now_ns = self.clock_ns()
        self._check_timeline(now_ns, cleanup_allowed=False)
        try:
            self.journal.reserve_capacity(
                events=1,
                bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES,
            )
            self._append_event("launch_window_armed", sanitized_outcome="passed")
        except L2MContractError:
            self._evidence_incomplete = True
            raise L2MContractError("launch window receipt could not be committed") from None
        self._provider_started_ns = now_ns
        self.lifecycle = ManualLifecycle(
            ManualPhase.LAUNCH_OUTCOME_UNVERIFIED,
            self.lifecycle.strict_firewall_preserved,
            False,
            self._proof_issuer,
        )

    def _must_retain_cleanup(self, phase: ObserverPhase | None = None) -> bool:
        return (
            self._incident_cleanup_only
            or self.lifecycle.phase not in {ManualPhase.PREFLIGHT, ManualPhase.COMPLETE}
            or phase
            in {
                ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
                ObserverPhase.RULESET_BIND,
                ObserverPhase.TERMINATION_VERIFY,
                ObserverPhase.RULESET_ABSENCE,
                ObserverPhase.GLOBAL_RESTORE,
                ObserverPhase.INCIDENT,
            }
            or self.lifecycle.strict_firewall_preserved
            or self._provider_started_ns is not None
        )

    def _launch_configuration_sha256(self) -> str:
        if self.private_ruleset_id is None:
            raise L2MContractError("launch configuration lacks a bound ruleset")
        return launch_configuration_sha256(
            private_image_id=self.private_selected_image_id,
            image_selection_checkpoint_sha256=self.image_selection_checkpoint_sha256,
            image_alias=self.selected_image_alias,
            image_version=self.selected_image_version,
            private_ruleset_id=self.private_ruleset_id,
            private_marker_name=self.private_marker_name,
            price_cents_per_hour=(
                self._preflight_price_cents_per_hour
                if self._preflight_price_cents_per_hour is not None
                else -1
            ),
        )

    def launch_configuration_binding_sha256(self) -> str:
        """Expose only the opaque hash the user must copy into a private checkpoint."""

        if (
            self.stopped
            or not self._preflight_complete
            or self.lifecycle.phase is not ManualPhase.RULESET_CREATED
        ):
            raise L2MContractError("launch configuration binding is unavailable")
        return self._launch_configuration_sha256()

    def instance_binding_challenge_sha256(self, observation: ObservedDocument) -> str:
        """Derive the opaque exact-one instance binding without consuming its observation."""

        observed = self._trusted_observation(
            observation,
            ObserverOperation.LIST_INSTANCES,
            frozenset({ObserverPhase.INSTANCE_BIND, ObserverPhase.INCIDENT}),
        )
        if self.private_ruleset_id is None:
            raise L2MContractError("instance binding lacks a private ruleset")
        match = classify_instances_for_ruleset(
            observed.data,
            private_ruleset_id=self.private_ruleset_id,
            image_selection_checkpoint_sha256=self.image_selection_checkpoint_sha256,
        )
        if match.state is not InstanceMatchState.EXACT_ONE or match.instance_id is None:
            raise L2MContractError("instance binding is not exactly one")
        return hashlib.sha256(
            json.dumps(
                {
                    "image_selection_checkpoint_sha256": self.image_selection_checkpoint_sha256,
                    "instance_id": match.instance_id,
                    "launch_configuration_sha256": self._launch_configuration_sha256(),
                    "ruleset_id": self.private_ruleset_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def assess_instance_binding_observation(
        self,
        observation: ObservedDocument,
        *,
        zero_is_terminal: bool,
    ) -> InstanceMatch:
        """Classify one launch poll without permitting ambiguous recovery to workload.

        ZERO may be treated as explicitly transient by the caller until its final
        bounded poll.  MULTIPLE and DRIFT always burn the observation and enter the
        cleanup-only incident state immediately.
        """

        observed = self._trusted_observation(
            observation,
            ObserverOperation.LIST_INSTANCES,
            frozenset({ObserverPhase.INSTANCE_BIND, ObserverPhase.INCIDENT}),
        )
        if self.private_ruleset_id is None:
            raise L2MContractError("instance assessment lacks a private ruleset")
        match = classify_instances_for_ruleset(
            observed.data,
            private_ruleset_id=self.private_ruleset_id,
            image_selection_checkpoint_sha256=self.image_selection_checkpoint_sha256,
        )
        if (
            match.state is InstanceMatchState.EXACT_ONE
            and observed.phase is ObserverPhase.INSTANCE_BIND
        ):
            return match
        retain_for_terminal_commit = (
            match.state is InstanceMatchState.ZERO
            and observed.phase is ObserverPhase.INCIDENT
            and zero_is_terminal
        )
        if not retain_for_terminal_commit:
            self._consume_trusted_observation(observed)
        if match.state is InstanceMatchState.ZERO and not zero_is_terminal:
            return match
        self._launch_match_state = match.state
        if match.state is InstanceMatchState.EXACT_ONE:
            self.private_instance_id = match.instance_id
        self._ambiguous_instance_ids = frozenset(match.instance_ids)
        self._conservative_account_terminal = match.state is InstanceMatchState.ZERO
        self._activate_cleanup_incident(None)
        try:
            self._append_event(
                "manual_incident",
                request=observer_request(ObserverOperation.LIST_INSTANCES),
                observer_phase=ObserverPhase.INSTANCE_BIND,
                request_ordinal=observed.request_ordinal,
                response_sha256=observed.response_sha256,
                request_binding_sha256=observed.request_binding_sha256,
                evidence_sha256=observed.response_sha256,
                source_request_ordinal=observed.request_ordinal,
                semantic_outcome="verification_failed",
                semantic_count=match.match_count,
                sanitized_outcome="resource_identity_ambiguous",
            )
        except L2MContractError:
            self._evidence_incomplete = True
        return match

    def bind_exact_instance_observation(self, observation: ObservedDocument) -> str:
        """Commit the observer-only step-11 exact instance receipt."""

        match = self.assess_instance_binding_observation(
            observation,
            zero_is_terminal=True,
        )
        if (
            match.state is not InstanceMatchState.EXACT_ONE
            or match.instance_id is None
            or self.lifecycle.phase is not ManualPhase.LAUNCH_CLICKED
            or self.lifecycle.incident_active
        ):
            raise L2MContractError("instance observation cannot become an exact binding")
        binding_sha256 = self.instance_binding_challenge_sha256(observation)
        try:
            self.journal.reserve_capacity(events=1, bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES)
            self._append_event(
                "evidence_sealed",
                request=observer_request(ObserverOperation.LIST_INSTANCES),
                observer_phase=ObserverPhase.INSTANCE_BIND,
                request_ordinal=observation.request_ordinal,
                response_sha256=observation.response_sha256,
                request_binding_sha256=observation.request_binding_sha256,
                verification_kind=TransitionVerificationKind.INSTANCE_EXACT,
                evidence_sha256=binding_sha256,
                source_request_ordinal=observation.request_ordinal,
                semantic_outcome="instance_provider_fields_exact_image_user_attested",
                semantic_count=1,
                sanitized_outcome="passed",
            )
            self._consume_trusted_observation(observation)
        except L2MContractError:
            self._evidence_incomplete = True
            self._activate_cleanup_incident(None)
            raise L2MContractError("exact instance receipt was not durable") from None
        self.private_instance_id = match.instance_id
        self.instance_binding_sha256 = binding_sha256
        self._launch_match_state = InstanceMatchState.EXACT_ONE
        self._ambiguous_instance_ids = frozenset(match.instance_ids)
        self._instance_bound_ns = self.clock_ns()
        self.lifecycle = ManualLifecycle(
            ManualPhase.INSTANCE_BOUND,
            self.lifecycle.strict_firewall_preserved,
            False,
            self._proof_issuer,
        )
        return binding_sha256

    def incident_scope_instance_ids(self) -> tuple[str, ...]:
        """Return only private IDs explicitly attached to the owned ruleset."""

        identifiers = set(self._ambiguous_instance_ids)
        if self.private_instance_id is not None:
            identifiers.add(self.private_instance_id)
        return tuple(sorted(identifiers))

    def terminal_checkpoint_state(self) -> str:
        """Return only the closed-enum state needed for the private terminal checkpoint."""

        if self._launch_match_state is None:
            raise L2MContractError("launch identity state is not yet classified")
        return self._launch_match_state.value

    def commit_terminal_instance_observation(self, observation: ObservedDocument) -> str:
        """Commit observer-only terminal evidence for exactly the authorized scope."""

        observed = self._trusted_observation(
            observation,
            ObserverOperation.LIST_INSTANCES,
            frozenset({ObserverPhase.TERMINATION_VERIFY, ObserverPhase.INCIDENT}),
        )
        if (
            self.lifecycle.phase
            not in {
                ManualPhase.TERMINATION_CONFIRMED,
                ManualPhase.LAUNCH_CLICKED,
                ManualPhase.LAUNCH_OUTCOME_UNVERIFIED,
                ManualPhase.RULESET_CREATED,
            }
            or self.lifecycle.incident_active
        ):
            raise L2MContractError("terminal observation is out of order")
        rows = [
            _mapping(item, context="terminal instance")
            for item in _sequence(observed.data, context="terminal instances")
        ]
        scope_ids = set(self.incident_scope_instance_ids())
        row_by_id: dict[str, Mapping[str, object]] = {}
        for row in rows:
            row_id = row.get("id")
            if not isinstance(row_id, str) or _PRIVATE_ID.fullmatch(row_id) is None:
                raise L2MContractError("terminal instance identity drifted")
            row_by_id[row_id] = row
        if set(row_by_id) - scope_ids:
            # An unattached or otherwise unbound account row is outside the private
            # human termination authority.  Preserve strict firewall state and stop
            # for a new decision instead of broadening the cleanup scope.
            self._activate_cleanup_incident(None)
            raise L2MContractError("terminal observation contains an unowned account row")
        if any(
            row_by_id.get(identifier, {}).get("status") not in {"terminated", "preempted"}
            for identifier in scope_ids
            if identifier in row_by_id
        ):
            raise L2MContractError("incident-scope instance is not terminal")
        if self._launch_match_state is not InstanceMatchState.ZERO and not scope_ids:
            raise L2MContractError("terminal observation lacks an authorized instance scope")
        state = (
            self._launch_match_state.value
            if self._launch_match_state is not None
            else InstanceMatchState.EXACT_ONE.value
        )
        evidence_sha256 = hashlib.sha256(
            json.dumps(
                {
                    "launch_identity_state": state,
                    "response_sha256": observed.response_sha256,
                    "scoped_ids_sha256": hashlib.sha256(
                        json.dumps(sorted(scope_ids), separators=(",", ":")).encode()
                    ).hexdigest(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        try:
            self.journal.reserve_capacity(events=1, bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES)
            self._append_event(
                "evidence_sealed",
                request=observer_request(ObserverOperation.LIST_INSTANCES),
                observer_phase=observed.phase,
                request_ordinal=observed.request_ordinal,
                response_sha256=observed.response_sha256,
                request_binding_sha256=observed.request_binding_sha256,
                verification_kind=TransitionVerificationKind.INSTANCE_TERMINAL,
                evidence_sha256=evidence_sha256,
                source_request_ordinal=observed.request_ordinal,
                semantic_outcome="instance_terminal_or_absent",
                semantic_count=len(scope_ids),
                sanitized_outcome="passed",
            )
            self._consume_trusted_observation(observed)
        except L2MContractError:
            self._evidence_incomplete = True
            self._activate_cleanup_incident(None)
            raise L2MContractError("terminal instance receipt was not durable") from None
        self._instance_cleanup_proven = True
        self._provider_terminal_ns = self.clock_ns()
        self.lifecycle = ManualLifecycle(
            ManualPhase.INSTANCE_TERMINAL,
            self.lifecycle.strict_firewall_preserved,
            False,
            self._proof_issuer,
        )
        return evidence_sha256

    def _prepare_transition(
        self,
        requested: ManualPhase,
        *,
        observation: ObservedDocument | None,
        qualification: ValidatedQualification | None,
    ) -> PreparedTransition:
        """Validate immutable evidence before a user checkpoint can be consumed."""

        def no_apply(checkpoint: VerifiedCheckpoint) -> None:
            del checkpoint

        def no_fail() -> None:
            return

        def require_true(checkpoint: VerifiedCheckpoint, name: str) -> None:
            if _checkpoint_detail(checkpoint, name) is not True:
                raise L2MContractError("user checkpoint lacks its exact attestation")

        if requested is ManualPhase.GLOBAL_RESTRICTED:
            if self.require_l23_auxiliary_checkpoints and (
                "launch_wizard_image_offered" not in self._auxiliary_checkpoint_sha256
                or self._original_global_seal_response_sha256 is None
            ):
                raise L2MContractError(
                    "offeredness or fresh original-firewall seal was not durable"
                )
            observed = self._trusted_observation(
                observation,
                ObserverOperation.GET_GLOBAL_FIREWALL,
                frozenset({ObserverPhase.GLOBAL_RESTRICTED_VERIFY}),
            )
            global_data = _mapping(observed.data, context="global firewall data")
            valid = True
            try:
                verify_global_firewall_identity(
                    global_data,
                    sealed_original_ruleset_id=self.sealed_original_global_ruleset_id,
                    sealed_original_ruleset_name=self.sealed_original_global_ruleset_name,
                )
                validate_strict_firewall_rules(
                    global_data.get("rules"), source_ipv4_cidr=self.source_ipv4_cidr
                )
            except L2MContractError:
                valid = False
            return PreparedTransition(
                observed.response_sha256,
                "global_firewall_exact" if valid else "verification_failed",
                1,
                observed.request_ordinal,
                observed,
                lambda checkpoint: require_true(checkpoint, "global_firewall_restricted"),
                no_apply,
                lambda: self._activate_cleanup_incident(ObserverPhase.GLOBAL_RESTRICTED_VERIFY),
                valid,
                ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
            )

        if requested is ManualPhase.RULESET_CREATED:
            observed = self._trusted_observation(
                observation,
                ObserverOperation.LIST_RULESETS,
                frozenset({ObserverPhase.RULESET_BIND}),
            )
            ruleset_match = classify_ruleset(
                observed.data,
                private_marker_name=self.private_marker_name,
                source_ipv4_cidr=self.source_ipv4_cidr,
            )
            valid = (
                ruleset_match.state is RulesetMatchState.EXACT_ONE
                and ruleset_match.ruleset_id is not None
            )

            def apply_ruleset(checkpoint: VerifiedCheckpoint) -> None:
                del checkpoint
                if (
                    ruleset_match.ruleset_id is None
                ):  # pragma: no cover - valid preparation invariant
                    raise L2MContractError("prepared ruleset identity disappeared")
                self.private_ruleset_id = ruleset_match.ruleset_id
                self._ruleset_match_state = RulesetMatchState.EXACT_ONE
                self._ambiguous_ruleset_ids = frozenset(ruleset_match.ruleset_ids)
                self._ruleset_cleanup_required = True

            def fail_ruleset() -> None:
                self._ruleset_match_state = ruleset_match.state
                self._ambiguous_ruleset_ids = frozenset(ruleset_match.ruleset_ids)
                self._ruleset_cleanup_required = ruleset_match.state is not RulesetMatchState.ZERO
                self.lifecycle = self.lifecycle.mutation_risk(
                    ManualPhase.RULESET_MUTATION_UNVERIFIED
                )
                self._incident_cleanup_only = True

            return PreparedTransition(
                observed.response_sha256,
                "ruleset_exact" if valid else "verification_failed",
                ruleset_match.match_count,
                observed.request_ordinal,
                observed,
                lambda checkpoint: require_true(checkpoint, "regional_ruleset_created"),
                apply_ruleset,
                fail_ruleset,
                valid,
                ObserverPhase.RULESET_BIND,
            )

        if requested is ManualPhase.LAUNCH_CLICKED:
            expected_configuration_sha256 = self._launch_configuration_sha256()
            now_utc = self.utc_now().astimezone(UTC)
            now_ns = self.clock_ns()
            provider_anchor_ns = now_ns

            def validate_launch(checkpoint: VerifiedCheckpoint) -> None:
                nonlocal provider_anchor_ns
                require_true(checkpoint, "launch_clicked_once")
                require_true(checkpoint, "approved_image_offered_for_selected_type_region")
                if (
                    _checkpoint_detail(checkpoint, "launch_configuration_sha256")
                    != expected_configuration_sha256
                ):
                    raise L2MContractError("launch configuration attestation hash drifted")
                wall_age_seconds = (
                    now_utc - checkpoint.observed_at_utc.astimezone(UTC)
                ).total_seconds()
                if not 0 <= wall_age_seconds <= MAX_USER_CHECKPOINT_SECONDS:
                    raise L2MContractError("launch checkpoint age cannot anchor provider wall")
                provider_anchor_ns = max(
                    self._observer_started_ns or 0,
                    now_ns - int(wall_age_seconds * 1_000_000_000),
                )

            def apply_launch(checkpoint: VerifiedCheckpoint) -> None:
                del checkpoint
                self._provider_started_ns = (
                    provider_anchor_ns
                    if self._provider_started_ns is None
                    else min(self._provider_started_ns, provider_anchor_ns)
                )

            return PreparedTransition(
                expected_configuration_sha256,
                "launch_configuration_user_attested",
                1,
                0,
                None,
                validate_launch,
                apply_launch,
                lambda: self._activate_launch_uncertain(now_ns),
            )

        if requested is ManualPhase.INSTANCE_BOUND:
            observed = self._trusted_observation(
                observation,
                ObserverOperation.LIST_INSTANCES,
                frozenset({ObserverPhase.INSTANCE_BIND}),
            )
            if self.private_ruleset_id is None:
                raise L2MContractError("instance binding preceded private ruleset binding")
            instance_match = classify_instances_for_ruleset(
                observed.data,
                private_ruleset_id=self.private_ruleset_id,
                image_selection_checkpoint_sha256=self.image_selection_checkpoint_sha256,
            )
            valid = (
                instance_match.state is InstanceMatchState.EXACT_ONE
                and instance_match.instance_id is not None
            )
            launch_sha256 = self._launch_configuration_sha256()
            binding_sha256 = (
                hashlib.sha256(
                    json.dumps(
                        {
                            "image_selection_checkpoint_sha256": (
                                self.image_selection_checkpoint_sha256
                            ),
                            "instance_id": instance_match.instance_id,
                            "launch_configuration_sha256": launch_sha256,
                            "ruleset_id": self.private_ruleset_id,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
                if valid
                else observed.response_sha256
            )

            def validate_instance(checkpoint: VerifiedCheckpoint) -> None:
                require_true(checkpoint, "instance_bound")
                if _checkpoint_detail(checkpoint, "instance_binding_sha256") != binding_sha256:
                    raise L2MContractError("instance checkpoint binding hash drifted")

            def apply_instance(checkpoint: VerifiedCheckpoint) -> None:
                del checkpoint
                if (
                    instance_match.instance_id is None
                ):  # pragma: no cover - valid preparation invariant
                    raise L2MContractError("prepared instance identity disappeared")
                self.private_instance_id = instance_match.instance_id
                self.instance_binding_sha256 = binding_sha256
                self._launch_match_state = InstanceMatchState.EXACT_ONE
                self._ambiguous_instance_ids = frozenset(instance_match.instance_ids)
                self._instance_bound_ns = self.clock_ns()

            def fail_instance() -> None:
                self._launch_match_state = instance_match.state
                self._ambiguous_instance_ids = frozenset(instance_match.instance_ids)
                self._conservative_account_terminal = (
                    instance_match.state is InstanceMatchState.ZERO
                    or (
                        instance_match.state is InstanceMatchState.DRIFT
                        and not instance_match.instance_ids
                    )
                )
                self._activate_cleanup_incident(None)

            return PreparedTransition(
                binding_sha256,
                (
                    "instance_provider_fields_exact_image_user_attested"
                    if valid
                    else "verification_failed"
                ),
                instance_match.match_count,
                observed.request_ordinal,
                observed,
                validate_instance,
                apply_instance,
                fail_instance,
                valid,
                ObserverPhase.INSTANCE_BIND,
            )

        if requested in {
            ManualPhase.CLOUD_IDE_OPENED,
            ManualPhase.QUALIFICATION_STARTED,
            ManualPhase.QUALIFICATION_COMPLETED,
            ManualPhase.TERMINATION_CONFIRMED,
        }:

            def apply_user(checkpoint: VerifiedCheckpoint) -> None:
                del checkpoint
                now_ns = self.clock_ns()
                if requested is ManualPhase.CLOUD_IDE_OPENED:
                    self._cloud_ide_opened_ns = now_ns
                elif requested is ManualPhase.QUALIFICATION_STARTED:
                    self._qualification_started_ns = now_ns
                elif requested is ManualPhase.QUALIFICATION_COMPLETED:
                    self._qualification_completed_ns = now_ns
                else:
                    self._termination_confirmed_ns = now_ns

            if (
                requested is ManualPhase.QUALIFICATION_STARTED
                and self.require_l23_auxiliary_checkpoints
                and "qualification_bundle_uploaded" not in self._auxiliary_checkpoint_sha256
            ):
                raise L2MContractError("qualification bundle upload was not durably attested")

            return PreparedTransition(
                "0" * 64,
                "user_attested",
                1,
                0,
                None,
                lambda checkpoint: require_true(checkpoint, requested.value),
                apply_user,
                lambda: self._activate_cleanup_incident(None),
            )

        if requested is ManualPhase.BUNDLE_DOWNLOADED:
            valid_qualification = (
                qualification is not None
                and qualification is self._validated_qualification
                and qualification._issuer is self._proof_issuer
                and qualification.run_id == self.run_id
                and qualification.authorization_reference == self.authorization_reference
                and not self._qualification_consumed
            )
            evidence_sha256 = (
                qualification.evidence_sha256 if qualification is not None else "0" * 64
            )

            def validate_bundle(checkpoint: VerifiedCheckpoint) -> None:
                require_true(checkpoint, "qualification_bundle_downloaded")
                if (
                    qualification is None
                    or _checkpoint_detail(checkpoint, "qualification_archive_sha256")
                    != qualification.archive_sha256
                ):
                    raise L2MContractError("qualification checkpoint archive hash drifted")

            def apply_bundle(checkpoint: VerifiedCheckpoint) -> None:
                del checkpoint
                self._qualification_consumed = True

            return PreparedTransition(
                evidence_sha256,
                "qualification_exact" if valid_qualification else "verification_failed",
                1,
                0,
                None,
                validate_bundle,
                apply_bundle,
                lambda: self._activate_cleanup_incident(None),
                valid_qualification,
                ObserverPhase.QUALIFICATION_LOCAL,
            )

        if requested is ManualPhase.INSTANCE_TERMINAL:
            observed = self._trusted_observation(
                observation,
                ObserverOperation.LIST_INSTANCES,
                frozenset({ObserverPhase.TERMINATION_VERIFY, ObserverPhase.INCIDENT}),
            )
            rows = [
                _mapping(item, context="terminal instance")
                for item in _sequence(observed.data, context="terminal instances")
            ]
            terminal_statuses = {"terminated", "preempted"}
            effective_launch_state = self._launch_match_state
            effective_instance_id = self.private_instance_id
            effective_instance_ids = set(self._ambiguous_instance_ids)
            if effective_instance_id is not None:
                effective_instance_ids.add(effective_instance_id)
            if effective_launch_state is None:
                if self.private_ruleset_id is None:
                    raise L2MContractError(
                        "launch-uncertain cleanup lacks a bound ruleset identity"
                    )
                recovered_match = classify_instances_for_ruleset(
                    observed.data,
                    private_ruleset_id=self.private_ruleset_id,
                    image_selection_checkpoint_sha256=self.image_selection_checkpoint_sha256,
                )
                effective_launch_state = recovered_match.state
                effective_instance_id = recovered_match.instance_id
                effective_instance_ids = set(recovered_match.instance_ids)
            # The preflight baseline was account-wide zero instances, so every row
            # observed after launch is cleanup-relevant.  Ruleset attachment is not a
            # safe filter: a provider-side launch/configuration fault may create an
            # unattached billable instance.
            relevant: list[Mapping[str, object]] = list(rows)
            current_ids: set[str] = set()
            identity_drift = False
            for item in rows:
                raw_id = item.get("id")
                row_id = (
                    raw_id
                    if isinstance(raw_id, str) and _PRIVATE_ID.fullmatch(raw_id) is not None
                    else None
                )
                if row_id is None:
                    identity_drift = True
                else:
                    current_ids.add(row_id)
            unexpected_current = current_ids - effective_instance_ids
            if unexpected_current:
                effective_launch_state = InstanceMatchState.MULTIPLE
                effective_instance_ids.update(unexpected_current)
                effective_instance_id = None
            valid = (
                not identity_drift
                and effective_launch_state is not None
                and all(item.get("status") in terminal_statuses for item in relevant)
                and (
                    self.lifecycle.phase is ManualPhase.TERMINATION_CONFIRMED
                    or (effective_launch_state is InstanceMatchState.ZERO and not relevant)
                )
            )

            def validate_terminal(checkpoint: VerifiedCheckpoint) -> None:
                require_true(checkpoint, "instance_terminal_verified")
                if _checkpoint_detail(checkpoint, "terminal_or_absent") is not True:
                    raise L2MContractError("terminal checkpoint lacks exact attestation")
                if (
                    effective_launch_state is None
                    or _checkpoint_detail(checkpoint, "launch_identity_state")
                    != effective_launch_state.value
                ):
                    raise L2MContractError("terminal checkpoint launch identity state drifted")

            def apply_terminal(checkpoint: VerifiedCheckpoint) -> None:
                del checkpoint
                if effective_launch_state is None:  # pragma: no cover - valid invariant
                    raise L2MContractError("terminal launch identity disappeared")
                self._launch_match_state = effective_launch_state
                self.private_instance_id = effective_instance_id
                self._ambiguous_instance_ids = frozenset(effective_instance_ids)
                self._instance_cleanup_proven = True
                self._provider_terminal_ns = self.clock_ns()

            def fail_terminal() -> None:
                self._launch_match_state = effective_launch_state
                self._ambiguous_instance_ids = frozenset(effective_instance_ids)
                self._activate_cleanup_incident(None)

            return PreparedTransition(
                observed.response_sha256,
                "instance_terminal_or_absent" if valid else "verification_failed",
                len(relevant),
                observed.request_ordinal,
                observed,
                validate_terminal,
                apply_terminal,
                fail_terminal,
                valid,
                observed.phase,
            )

        if requested is ManualPhase.RULESET_DELETED:
            observed = self._trusted_observation(
                observation,
                ObserverOperation.LIST_RULESETS,
                frozenset({ObserverPhase.RULESET_ABSENCE, ObserverPhase.INCIDENT}),
            )
            current_match = classify_ruleset(
                observed.data,
                private_marker_name=self.private_marker_name,
                source_ipv4_cidr=self.source_ipv4_cidr,
            )
            effective_ruleset_ids = set(self._ambiguous_ruleset_ids) | set(
                current_match.ruleset_ids
            )
            if self.private_ruleset_id is not None:
                effective_ruleset_ids.add(self.private_ruleset_id)
            matching = [
                _mapping(item, context="remaining ruleset")
                for item in _sequence(observed.data, context="remaining rulesets")
                if _mapping(item, context="remaining ruleset").get("id") in effective_ruleset_ids
                or _mapping(item, context="remaining ruleset").get("name")
                == self.private_marker_name
            ]
            valid = not matching and (
                self._provider_started_ns is None or self._instance_cleanup_proven
            )

            def validate_absence(checkpoint: VerifiedCheckpoint) -> None:
                require_true(checkpoint, "regional_ruleset_deleted")
                if _checkpoint_detail(checkpoint, "regional_ruleset_absent") is not True:
                    raise L2MContractError("ruleset absence checkpoint lacks attestation")

            def apply_absence(checkpoint: VerifiedCheckpoint) -> None:
                del checkpoint
                self._ruleset_cleanup_proven = True
                self._ruleset_match_state = RulesetMatchState.ZERO
                self._ambiguous_ruleset_ids = frozenset()
                self._ruleset_deleted_ns = self.clock_ns()

            def fail_absence() -> None:
                self._ruleset_match_state = current_match.state
                self._ambiguous_ruleset_ids = frozenset(effective_ruleset_ids)
                self._ruleset_cleanup_required = True
                self._activate_cleanup_incident(None)

            return PreparedTransition(
                observed.response_sha256,
                "ruleset_absent" if valid else "verification_failed",
                len(matching),
                observed.request_ordinal,
                observed,
                validate_absence,
                apply_absence,
                fail_absence,
                valid,
                observed.phase,
            )

        if requested is ManualPhase.GLOBAL_RESTORED:
            observed = self._trusted_observation(
                observation,
                ObserverOperation.GET_GLOBAL_FIREWALL,
                frozenset({ObserverPhase.GLOBAL_RESTORE, ObserverPhase.INCIDENT}),
            )
            global_data = _mapping(observed.data, context="restored global firewall data")
            valid = not self._ruleset_cleanup_required or self._ruleset_cleanup_proven
            try:
                verify_global_firewall_restoration(
                    global_data,
                    sealed_original_ruleset_id=self.sealed_original_global_ruleset_id,
                    sealed_original_ruleset_name=self.sealed_original_global_ruleset_name,
                    sealed_original_semantic_sha256=self.sealed_original_global_sha256,
                )
            except L2MContractError:
                valid = False

            def validate_restoration(checkpoint: VerifiedCheckpoint) -> None:
                require_true(checkpoint, "global_firewall_restored")
                if (
                    _checkpoint_detail(checkpoint, "global_firewall_semantic_sha256")
                    != self.sealed_original_global_sha256
                ):
                    raise L2MContractError("global restoration checkpoint hash drifted")

            return PreparedTransition(
                observed.response_sha256,
                "global_firewall_restored_exact" if valid else "verification_failed",
                1,
                observed.request_ordinal,
                observed,
                validate_restoration,
                no_apply,
                lambda: self._activate_cleanup_incident(None),
                valid,
                observed.phase,
            )

        raise L2MContractError("checkpoint phase is not observable")

    def consume_auxiliary_checkpoint(
        self,
        path: Path,
        *,
        expected_type: str,
        expected_nonce: str,
        not_before: datetime,
        not_after: datetime,
        expected_archive_sha256: str | None = None,
    ) -> VerifiedCheckpoint:
        """Consume one L2.3 user action that does not advance the L2.2 lifecycle."""

        contracts = {
            "launch_wizard_image_offered": (
                ManualPhase.PREFLIGHT,
                TransitionVerificationKind.LAUNCH_WIZARD_OFFEREDNESS_ATTESTED,
                "launch_wizard_offeredness_user_attested",
            ),
            "launch_configuration_selected": (
                ManualPhase.RULESET_CREATED,
                TransitionVerificationKind.LAUNCH_CONFIGURATION_ATTESTED,
                "launch_configuration_user_attested",
            ),
            "qualification_bundle_uploaded": (
                ManualPhase.CLOUD_IDE_OPENED,
                TransitionVerificationKind.QUALIFICATION_BUNDLE_UPLOADED_ATTESTED,
                "qualification_bundle_uploaded_user_attested",
            ),
            "qualification_bundle_downloaded": (
                ManualPhase.QUALIFICATION_COMPLETED,
                TransitionVerificationKind.ARCHIVE_EXACT,
                "user_attested",
            ),
        }
        if (
            not self.require_l23_auxiliary_checkpoints
            or self.stopped
            or not self._preflight_complete
            or expected_type not in contracts
            or expected_type in self._auxiliary_checkpoint_sha256
        ):
            raise L2MContractError("auxiliary checkpoint is unavailable or already consumed")
        required_phase, verification_kind, semantic_outcome = contracts[expected_type]
        if self.lifecycle.phase is not required_phase or self.lifecycle.incident_active:
            raise L2MContractError("auxiliary checkpoint order drifted")

        def validate_details(checkpoint: VerifiedCheckpoint) -> None:
            if expected_type == "launch_wizard_image_offered":
                expected = {
                    "launch_wizard_image_offered": True,
                    "selected_instance_type": SELECTED_INSTANCE_TYPE,
                    "selected_region": SELECTED_REGION,
                    "selected_image_alias": self.selected_image_alias,
                    "selected_image_version": self.selected_image_version,
                }
            elif expected_type == "launch_configuration_selected":
                expected = {
                    "launch_configuration_selected": True,
                    "launch_configuration_sha256": self._launch_configuration_sha256(),
                }
            elif expected_type == "qualification_bundle_uploaded":
                expected = {
                    "qualification_bundle_uploaded": True,
                    "qualification_bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256,
                }
            else:
                if (
                    expected_archive_sha256 is None
                    or _SHA256.fullmatch(expected_archive_sha256) is None
                ):
                    raise L2MContractError("downloaded archive identity is unavailable")
                expected = {
                    "qualification_bundle_downloaded": True,
                    "qualification_archive_sha256": expected_archive_sha256,
                }
            if dict(checkpoint.details) != expected:
                raise L2MContractError("auxiliary checkpoint details drifted")

        try:
            self.journal.reserve_capacity(events=2, bytes_upper_bound=2 * MAX_OBSERVER_EVENT_BYTES)
            self._append_event(
                "checkpoint_intent_committed",
                checkpoint_type=expected_type,
                verification_kind=verification_kind,
            )
            checkpoint = self.checkpoint_reader.read_once(
                path,
                expected_type=expected_type,
                expected_nonce=expected_nonce,
                not_before=not_before,
                not_after=not_after,
                detail_validator=validate_details,
            )
            receipt = (0, checkpoint.encoded_sha256, verification_kind.value)
            self._expected_transition_receipts[checkpoint.encoded_sha256] = receipt
            self._append_event(
                "checkpoint_validated",
                checkpoint_type=expected_type,
                checkpoint_sha256=checkpoint.encoded_sha256,
                verification_kind=verification_kind,
                evidence_sha256=checkpoint.encoded_sha256,
                semantic_outcome=semantic_outcome,
                semantic_count=1,
                sanitized_outcome="passed",
            )
            self._durable_transition_receipts[checkpoint.encoded_sha256] = receipt
        except BaseException as failure:
            if self.lifecycle.strict_firewall_preserved or self._provider_started_ns is not None:
                self._activate_cleanup_incident(None)
            if not isinstance(failure, Exception):
                raise
            raise L2MContractError("auxiliary checkpoint validation failed") from None
        self._auxiliary_checkpoint_sha256[expected_type] = checkpoint.encoded_sha256
        if expected_type == "launch_wizard_image_offered":
            self.image_selection_checkpoint_sha256 = checkpoint.encoded_sha256
        return checkpoint

    def commit_validated_qualification(self, qualification: ValidatedQualification) -> str:
        """Commit observer-only step 16 after the user's step-15 download attestation."""

        if (
            qualification is not self._validated_qualification
            or qualification._issuer is not self._proof_issuer
            or self.lifecycle.phase is not ManualPhase.QUALIFICATION_COMPLETED
            or "qualification_bundle_downloaded" not in self._auxiliary_checkpoint_sha256
            or self._qualification_consumed
        ):
            raise L2MContractError("validated qualification cannot be committed")
        try:
            self.journal.reserve_capacity(events=1, bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES)
            self._append_event(
                "evidence_sealed",
                verification_kind=TransitionVerificationKind.ARCHIVE_EXACT,
                evidence_sha256=qualification.evidence_sha256,
                semantic_outcome="qualification_exact",
                semantic_count=1,
                sanitized_outcome="passed",
            )
        except L2MContractError:
            self._evidence_incomplete = True
            self._activate_cleanup_incident(None)
            raise L2MContractError("qualification receipt was not durable") from None
        self._qualification_consumed = True
        self.lifecycle = ManualLifecycle(
            ManualPhase.BUNDLE_DOWNLOADED,
            self.lifecycle.strict_firewall_preserved,
            False,
            self._proof_issuer,
        )
        return qualification.evidence_sha256

    def validate_qualification(
        self,
        archive_path: Path,
        *,
        schema_path: Path,
        expected_bundle_manifest_sha256: str,
        expected_binding: QualificationEvidenceBinding,
        archive_directory_descriptor: int | None = None,
    ) -> ValidatedQualification:
        schema_repository_root = _repository_root_for_bound_path(
            schema_path,
            relative_path=_BOUND_HOST_EVIDENCE_SCHEMA_RELATIVE_PATH,
            context="host evidence schema",
        )
        if (
            self.stopped
            or not self._preflight_complete
            or self.lifecycle.phase is not ManualPhase.QUALIFICATION_COMPLETED
            or self._validated_qualification is not None
            or self._validated_qualification_failure is not None
            or schema_repository_root != self.journal.repository_root
        ):
            raise L2MContractError("qualification validation is out of order or already used")
        qualification_now_ns = self.clock_ns()
        self._check_timeline(qualification_now_ns, cleanup_allowed=False)
        self._enforce_transition_deadline(
            ManualPhase.BUNDLE_DOWNLOADED,
            qualification_now_ns,
        )
        if (
            expected_binding.run_id != self.run_id
            or expected_binding.authorization_reference != self.authorization_reference
            or expected_binding.authorization_sha256 != self.authorization_sha256
            or expected_binding.decision_alias != self.checkpoint_reader.binding.decision_alias
            or expected_binding.marker_alias != self.checkpoint_reader.binding.marker_alias
            or self.instance_binding_sha256 is None
            or expected_binding.instance_binding_sha256 != self.instance_binding_sha256
        ):
            raise L2MContractError("qualification binding differs from the active engine")
        try:
            self.journal.reserve_capacity(
                events=3,
                bytes_upper_bound=3 * MAX_OBSERVER_EVENT_BYTES,
            )
            self._append_event(
                "evidence_validation_intent_committed",
                semantic_outcome="none",
            )
        except L2MContractError:
            self._evidence_incomplete = True
            self._activate_cleanup_incident(None)
            raise L2MContractError(
                "qualification validation intent could not be committed"
            ) from None
        try:
            remaining = self._qualification_validation_remaining_seconds()
            with _ObserverHardAlarm(
                remaining,
                message="qualification evidence hard deadline exceeded",
            ):
                encoded, status = (
                    _read_bounded_regular_with_identity(
                        archive_path,
                        max_bytes=MAX_QUALIFICATION_ARCHIVE_BYTES,
                    )
                    if archive_directory_descriptor is None
                    else _read_bounded_regular_at_with_identity(
                        archive_directory_descriptor,
                        archive_path.name,
                        max_bytes=MAX_QUALIFICATION_ARCHIVE_BYTES,
                    )
                )
                archive_sha256 = hashlib.sha256(encoded).hexdigest()
                evidence = validate_qualification_archive(
                    archive_path,
                    schema_path=schema_path,
                    expected_bundle_manifest_sha256=expected_bundle_manifest_sha256,
                    expected_binding=expected_binding,
                    _encoded_archive=encoded,
                )
                evidence_sha256 = hashlib.sha256(
                    json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                self._check_timeline(self.clock_ns(), cleanup_allowed=False)
                self._enforce_transition_deadline(
                    ManualPhase.BUNDLE_DOWNLOADED,
                    self.clock_ns(),
                )
                self._qualification_validation_remaining_seconds()
                binding_sha256 = hashlib.sha256(
                    json.dumps(
                        {
                            "authorization_reference": expected_binding.authorization_reference,
                            "authorization_sha256": expected_binding.authorization_sha256,
                            "decision_alias": expected_binding.decision_alias,
                            "instance_binding_sha256": (expected_binding.instance_binding_sha256),
                            "marker_alias": expected_binding.marker_alias,
                            "run_id": expected_binding.run_id,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
                validated_qualification = ValidatedQualification(
                    self.run_id,
                    self.authorization_reference,
                    archive_path.absolute(),
                    status.st_dev,
                    status.st_ino,
                    status.st_size,
                    archive_sha256,
                    evidence_sha256,
                    binding_sha256,
                    self._proof_issuer,
                )
                self._append_event(
                    "evidence_validated",
                    sanitized_outcome="passed",
                    bytes_received=min(len(encoded), MAX_RESPONSE_BYTES_PER_GET),
                    response_sha256=archive_sha256,
                    request_binding_sha256=binding_sha256,
                    evidence_sha256=evidence_sha256,
                    semantic_outcome="qualification_exact",
                    semantic_count=1,
                )
                self._check_timeline(self.clock_ns(), cleanup_allowed=False)
                self._enforce_transition_deadline(
                    ManualPhase.BUNDLE_DOWNLOADED,
                    self.clock_ns(),
                )
                self._qualification_validation_remaining_seconds()
                self._validated_qualification = validated_qualification
                self._validated_qualification_encoded = encoded
        except BaseException as failure:
            self._evidence_incomplete = True
            self._activate_cleanup_incident(None)
            try:
                self._append_event(
                    "evidence_validation_failed",
                    sanitized_outcome=(
                        "timeout"
                        if isinstance(failure, L2MDeadlineError)
                        else (
                            "privacy_failure"
                            if isinstance(failure, Exception)
                            else "outcome_unknown"
                        )
                    ),
                    semantic_outcome="verification_failed",
                )
            except BaseException:
                self._evidence_incomplete = True
            if not isinstance(failure, Exception):
                raise
            raise L2MContractError("qualification evidence validation failed") from None
        return validated_qualification

    def validate_qualification_failure(
        self,
        archive_path: Path,
        *,
        expected_bundle_manifest_sha256: str,
        expected_binding: QualificationEvidenceBinding,
        archive_directory_descriptor: int | None = None,
    ) -> ValidatedQualificationFailure:
        """Bind a qualification failure archive to this run and enter cleanup-only state.

        A validated failure archive is evidence, never a qualification token.  The
        method intentionally leaves ``_validated_qualification`` unset, so the bundle
        checkpoint cannot become eligible even when emergency container cleanup was
        complete.
        """

        if (
            self.stopped
            or not self._preflight_complete
            or self.lifecycle.phase is not ManualPhase.QUALIFICATION_COMPLETED
            or self._validated_qualification is not None
            or self._validated_qualification_failure is not None
        ):
            raise L2MContractError(
                "qualification failure validation is out of order or already used"
            )
        if (
            expected_binding.run_id != self.run_id
            or expected_binding.authorization_reference != self.authorization_reference
            or expected_binding.authorization_sha256 != self.authorization_sha256
            or expected_binding.decision_alias != self.checkpoint_reader.binding.decision_alias
            or expected_binding.marker_alias != self.checkpoint_reader.binding.marker_alias
            or self.instance_binding_sha256 is None
            or expected_binding.instance_binding_sha256 != self.instance_binding_sha256
        ):
            raise L2MContractError("qualification failure binding differs from the active engine")
        qualification_now_ns = self.clock_ns()
        self._check_timeline(qualification_now_ns, cleanup_allowed=False)
        self._enforce_transition_deadline(
            ManualPhase.BUNDLE_DOWNLOADED,
            qualification_now_ns,
        )
        try:
            self.journal.reserve_capacity(
                events=3,
                bytes_upper_bound=3 * MAX_OBSERVER_EVENT_BYTES,
            )
            self._append_event(
                "evidence_validation_intent_committed",
                semantic_outcome="qualification_failure",
            )
        except L2MContractError:
            self._evidence_incomplete = True
            self._activate_cleanup_incident(None)
            raise L2MContractError(
                "qualification failure validation intent could not be committed"
            ) from None
        try:
            remaining = self._qualification_validation_remaining_seconds()
            with _ObserverHardAlarm(
                remaining,
                message="qualification failure evidence hard deadline exceeded",
            ):
                encoded, status = (
                    _read_bounded_regular_with_identity(
                        archive_path,
                        max_bytes=MAX_QUALIFICATION_ARCHIVE_BYTES,
                    )
                    if archive_directory_descriptor is None
                    else _read_bounded_regular_at_with_identity(
                        archive_directory_descriptor,
                        archive_path.name,
                        max_bytes=MAX_QUALIFICATION_ARCHIVE_BYTES,
                    )
                )
                archive_sha256 = hashlib.sha256(encoded).hexdigest()
                evidence = validate_qualification_failure_archive(
                    archive_path,
                    expected_bundle_manifest_sha256=expected_bundle_manifest_sha256,
                    expected_binding=expected_binding,
                    _encoded_archive=encoded,
                )
                evidence_sha256 = hashlib.sha256(
                    json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                cleanup_complete = evidence.get("cleanup_complete") is True
                self._check_timeline(self.clock_ns(), cleanup_allowed=False)
                self._enforce_transition_deadline(
                    ManualPhase.BUNDLE_DOWNLOADED,
                    self.clock_ns(),
                )
                self._qualification_validation_remaining_seconds()
                validated = ValidatedQualificationFailure(
                    self.run_id,
                    self.authorization_reference,
                    archive_path.absolute(),
                    status.st_dev,
                    status.st_ino,
                    status.st_size,
                    archive_sha256,
                    evidence_sha256,
                    cleanup_complete,
                    self._proof_issuer,
                )
                self._append_event(
                    "evidence_validated",
                    sanitized_outcome="cleanup_required",
                    bytes_received=min(len(encoded), MAX_RESPONSE_BYTES_PER_GET),
                    response_sha256=archive_sha256,
                    evidence_sha256=evidence_sha256,
                    semantic_outcome="qualification_failure",
                    semantic_count=1,
                )
                self._check_timeline(self.clock_ns(), cleanup_allowed=False)
                self._enforce_transition_deadline(
                    ManualPhase.BUNDLE_DOWNLOADED,
                    self.clock_ns(),
                )
                self._qualification_validation_remaining_seconds()
                self._validated_qualification_failure = validated
                self._validated_qualification_failure_encoded = encoded
        except BaseException as failure:
            self._evidence_incomplete = True
            self._activate_cleanup_incident(None)
            try:
                self._append_event(
                    "evidence_validation_failed",
                    sanitized_outcome=(
                        "timeout"
                        if isinstance(failure, L2MDeadlineError)
                        else (
                            "privacy_failure"
                            if isinstance(failure, Exception)
                            else "outcome_unknown"
                        )
                    ),
                    semantic_outcome="qualification_failure",
                )
            except BaseException:
                self._evidence_incomplete = True
            if not isinstance(failure, Exception):
                raise
            raise L2MContractError("qualification failure evidence validation failed") from None
        self._activate_cleanup_incident(None)
        return validated

    def _recover_checkpoint_transaction(self, transaction: CheckpointTransactionState) -> None:
        """Preserve cleanup authority after any failure following durable intent."""

        if transaction.failure_handled:
            return
        transaction.failure_handled = True
        self._evidence_incomplete = True
        prepared = transaction.prepared
        checkpoint = transaction.checkpoint
        if (
            transaction.requested in _CLEANUP_CHECKPOINT_PHASES
            and prepared is not None
            and checkpoint is not None
        ):
            try:
                proof = transaction.proof
                if proof is None:
                    effective_evidence_sha256 = (
                        checkpoint.encoded_sha256
                        if prepared.source_request_ordinal == 0
                        and prepared.semantic_outcome == "user_attested"
                        else prepared.evidence_sha256
                    )
                    proof = TransitionProof(
                        checkpoint_type=checkpoint.checkpoint_type,
                        checkpoint_sha256=checkpoint.encoded_sha256,
                        verification_kind=transaction.verification_kind,
                        evidence_sha256=effective_evidence_sha256,
                        _issuer=self._proof_issuer,
                    )
                    transaction.proof = proof
                next_lifecycle = transaction.next_lifecycle
                if next_lifecycle is None:
                    next_lifecycle = self.lifecycle.advance(checkpoint, proof)
                    transaction.next_lifecycle = next_lifecycle
                if not transaction.observation_consumed:
                    observation = prepared.observation
                    if (
                        observation is not None
                        and observation.request_ordinal not in self._consumed_observation_ordinals
                    ):
                        self._consume_trusted_observation(observation)
                    transaction.observation_consumed = True
                if not transaction.applied:
                    prepared.apply(checkpoint)
                    transaction.applied = True
                if not transaction.lifecycle_advanced:
                    self.lifecycle = next_lifecycle
                    transaction.lifecycle_advanced = True
                self._incident_cleanup_only = True
            except BaseException:
                self._activate_cleanup_incident(prepared.failure_cleanup_phase)
        else:
            if prepared is not None:
                with contextlib.suppress(BaseException):
                    prepared.fail()
            if transaction.requested is ManualPhase.LAUNCH_CLICKED:
                self._activate_launch_uncertain(transaction.transition_now_ns)
            else:
                risk_phase = (
                    ObserverPhase.GLOBAL_RESTRICTED_VERIFY
                    if transaction.requested is ManualPhase.GLOBAL_RESTRICTED
                    else (
                        ObserverPhase.RULESET_BIND
                        if transaction.requested is ManualPhase.RULESET_CREATED
                        else None
                    )
                )
                if (
                    risk_phase is not None
                    or self.lifecycle.strict_firewall_preserved
                    or self._provider_started_ns is not None
                ):
                    self._activate_cleanup_incident(risk_phase)
        try:
            self._append_event(
                "checkpoint_verification_failed",
                checkpoint_type=transaction.checkpoint_type,
                checkpoint_sha256=(None if checkpoint is None else checkpoint.encoded_sha256),
                verification_kind=transaction.verification_kind,
                evidence_sha256=(None if prepared is None else prepared.evidence_sha256),
                source_request_ordinal=(0 if prepared is None else prepared.source_request_ordinal),
                semantic_outcome="verification_failed",
                semantic_count=(None if prepared is None else prepared.semantic_count),
                sanitized_outcome="outcome_unknown",
            )
        except BaseException:
            self._evidence_incomplete = True

    def consume_checkpoint(
        self,
        path: Path,
        *,
        expected_type: str,
        expected_nonce: str,
        not_before: datetime,
        not_after: datetime,
        observation: ObservedDocument | None = None,
        qualification: ValidatedQualification | None = None,
    ) -> ManualLifecycle:
        if self._checkpoint_transaction is not None:
            raise L2MContractError("checkpoint transaction is already active")
        try:
            return self._consume_checkpoint_transaction(
                path,
                expected_type=expected_type,
                expected_nonce=expected_nonce,
                not_before=not_before,
                not_after=not_after,
                observation=observation,
                qualification=qualification,
            )
        except BaseException:
            transaction = self._checkpoint_transaction
            if transaction is not None:
                self._recover_checkpoint_transaction(transaction)
            raise
        finally:
            self._checkpoint_transaction = None

    def _consume_checkpoint_transaction(
        self,
        path: Path,
        *,
        expected_type: str,
        expected_nonce: str,
        not_before: datetime,
        not_after: datetime,
        observation: ObservedDocument | None = None,
        qualification: ValidatedQualification | None = None,
    ) -> ManualLifecycle:
        if self.stopped or not self._preflight_complete:
            raise L2MContractError("observer preflight is incomplete or stopped")
        try:
            requested = ManualPhase(expected_type)
        except ValueError:
            raise L2MContractError("checkpoint type is not a lifecycle phase") from None
        if self.lifecycle.incident_active:
            raise L2MContractError("manual incident must be resumed before cleanup")
        if self._incident_cleanup_only and requested not in _CLEANUP_CHECKPOINT_PHASES:
            raise L2MContractError("observer incident freezes all non-cleanup checkpoints")
        if requested not in _MANUAL_TRANSITIONS[self.lifecycle.phase]:
            raise L2MContractError("manual checkpoint order drifted")
        transition_now_ns = self.clock_ns()
        self._check_timeline(
            transition_now_ns,
            cleanup_allowed=requested in _CLEANUP_CHECKPOINT_PHASES,
        )
        self._enforce_transition_deadline(requested, transition_now_ns)
        verification_kind = _TRANSITION_PROOF_KINDS[requested]
        transaction = CheckpointTransactionState(
            requested=requested,
            transition_now_ns=transition_now_ns,
            checkpoint_type=expected_type,
            verification_kind=verification_kind,
        )
        self._checkpoint_transaction = transaction
        try:
            self.journal.reserve_capacity(
                events=3,
                bytes_upper_bound=3 * MAX_OBSERVER_EVENT_BYTES,
            )
            self._append_event(
                "checkpoint_intent_committed",
                checkpoint_type=expected_type,
                verification_kind=verification_kind,
            )
        except L2MContractError:
            self._evidence_incomplete = True
            if requested is ManualPhase.LAUNCH_CLICKED:
                self._activate_launch_uncertain(transition_now_ns)
            risk_phase = (
                ObserverPhase.GLOBAL_RESTRICTED_VERIFY
                if requested is ManualPhase.GLOBAL_RESTRICTED
                else (
                    ObserverPhase.RULESET_BIND if requested is ManualPhase.RULESET_CREATED else None
                )
            )
            if requested is not ManualPhase.LAUNCH_CLICKED and (
                risk_phase is not None or self.lifecycle.strict_firewall_preserved
            ):
                self._activate_cleanup_incident(risk_phase)
            transaction.failure_handled = True
            raise L2MContractError("checkpoint intent could not be committed") from None

        try:
            prepared = self._prepare_transition(
                requested,
                observation=observation,
                qualification=qualification,
            )
            transaction.prepared = prepared
        except BaseException as failure:
            if not isinstance(failure, Exception):
                raise
            if requested is ManualPhase.LAUNCH_CLICKED:
                self._activate_launch_uncertain(transition_now_ns)
            risk_phase = (
                ObserverPhase.GLOBAL_RESTRICTED_VERIFY
                if requested is ManualPhase.GLOBAL_RESTRICTED
                else (
                    ObserverPhase.RULESET_BIND if requested is ManualPhase.RULESET_CREATED else None
                )
            )
            if requested is not ManualPhase.LAUNCH_CLICKED and (
                risk_phase is not None
                or self.lifecycle.strict_firewall_preserved
                or self._provider_started_ns is not None
            ):
                self._activate_cleanup_incident(risk_phase)
            try:
                self._append_event(
                    "checkpoint_verification_failed",
                    checkpoint_type=expected_type,
                    verification_kind=verification_kind,
                    semantic_outcome="verification_failed",
                    sanitized_outcome="privacy_failure",
                )
                if self.lifecycle.incident_active:
                    self._append_event(
                        "manual_incident",
                        sanitized_outcome="privacy_failure",
                    )
            except BaseException:
                self._evidence_incomplete = True
            transaction.failure_handled = True
            raise L2MContractError("checkpoint evidence preparation failed") from None
        receipt_request = (
            None
            if prepared.observation is None
            else observer_request(prepared.observation.operation)
        )

        def record_failure() -> None:
            prepared.fail()
            self._consume_trusted_observation(prepared.observation)
            transaction.observation_consumed = True
            try:
                self._append_event(
                    "checkpoint_verification_failed",
                    request=receipt_request,
                    observer_phase=(
                        None if prepared.observation is None else prepared.observation.phase
                    ),
                    response_sha256=(
                        None
                        if prepared.observation is None
                        else prepared.observation.response_sha256
                    ),
                    request_binding_sha256=(
                        None
                        if prepared.observation is None
                        else prepared.observation.request_binding_sha256
                    ),
                    checkpoint_type=expected_type,
                    verification_kind=verification_kind,
                    evidence_sha256=prepared.evidence_sha256,
                    source_request_ordinal=prepared.source_request_ordinal,
                    request_ordinal=prepared.source_request_ordinal,
                    semantic_outcome="verification_failed",
                    semantic_count=prepared.semantic_count,
                    sanitized_outcome="resource_identity_ambiguous",
                )
                self._append_event(
                    "manual_incident",
                    sanitized_outcome="resource_identity_ambiguous",
                )
            except BaseException:
                self._evidence_incomplete = True

        if not prepared.valid:
            record_failure()
            transaction.failure_handled = True
            raise L2MContractError("checkpoint evidence verification failed")

        consumption_outcome_unknown = False
        consumption_interruption: BaseException | None = None
        try:
            checkpoint = self.checkpoint_reader.read_once(
                path,
                expected_type=expected_type,
                expected_nonce=expected_nonce,
                not_before=not_before,
                not_after=not_after,
                detail_validator=prepared.detail_validator,
                on_consumed=lambda value: setattr(transaction, "checkpoint", value),
            )
            transaction.checkpoint = checkpoint
        except CheckpointConsumptionOutcomeUnknown as failure:
            self._evidence_incomplete = True
            checkpoint = failure.checkpoint
            consumption_outcome_unknown = True
            consumption_interruption = failure.interruption
            transaction.checkpoint = checkpoint
            if requested not in _CLEANUP_CHECKPOINT_PHASES:
                record_failure()
                transaction.failure_handled = True
                if consumption_interruption is not None:
                    raise consumption_interruption from None
                raise L2MContractError(
                    "checkpoint consumption outcome is unknown; run identity is burned"
                ) from None
        except BaseException as failure:
            if not isinstance(failure, Exception):
                raise
            record_failure()
            transaction.failure_handled = True
            raise L2MContractError("checkpoint validation failed before consumption") from None

        effective_evidence_sha256 = (
            checkpoint.encoded_sha256
            if prepared.source_request_ordinal == 0 and prepared.semantic_outcome == "user_attested"
            else prepared.evidence_sha256
        )
        proof = TransitionProof(
            checkpoint_type=checkpoint.checkpoint_type,
            checkpoint_sha256=checkpoint.encoded_sha256,
            verification_kind=verification_kind,
            evidence_sha256=effective_evidence_sha256,
            _issuer=self._proof_issuer,
        )
        transaction.proof = proof
        next_lifecycle = self.lifecycle.advance(checkpoint, proof)
        transaction.next_lifecycle = next_lifecycle
        if consumption_outcome_unknown:
            self._consume_trusted_observation(prepared.observation)
            transaction.observation_consumed = True
            prepared.apply(checkpoint)
            transaction.applied = True
            self.lifecycle = next_lifecycle
            transaction.lifecycle_advanced = True
            self._incident_cleanup_only = True
            try:
                self._append_event(
                    "checkpoint_verification_failed",
                    request=receipt_request,
                    observer_phase=(
                        None if prepared.observation is None else prepared.observation.phase
                    ),
                    response_sha256=(
                        None
                        if prepared.observation is None
                        else prepared.observation.response_sha256
                    ),
                    request_binding_sha256=(
                        None
                        if prepared.observation is None
                        else prepared.observation.request_binding_sha256
                    ),
                    checkpoint_type=checkpoint.checkpoint_type,
                    checkpoint_sha256=checkpoint.encoded_sha256,
                    verification_kind=verification_kind,
                    evidence_sha256=effective_evidence_sha256,
                    source_request_ordinal=prepared.source_request_ordinal,
                    request_ordinal=prepared.source_request_ordinal,
                    semantic_outcome="verification_failed",
                    semantic_count=prepared.semantic_count,
                    sanitized_outcome="outcome_unknown",
                )
            except BaseException:
                self._evidence_incomplete = True
            transaction.failure_handled = True
            if consumption_interruption is not None:
                raise consumption_interruption from None
            raise L2MContractError(
                "checkpoint consumption outcome is unknown; cleanup transition advanced"
            ) from None
        receipt_identity = (
            prepared.source_request_ordinal,
            effective_evidence_sha256,
            verification_kind.value,
        )
        self._expected_transition_receipts[checkpoint.encoded_sha256] = receipt_identity
        try:
            self._append_event(
                "checkpoint_validated",
                request=receipt_request,
                observer_phase=(
                    None if prepared.observation is None else prepared.observation.phase
                ),
                response_sha256=(
                    None if prepared.observation is None else prepared.observation.response_sha256
                ),
                request_binding_sha256=(
                    None
                    if prepared.observation is None
                    else prepared.observation.request_binding_sha256
                ),
                checkpoint_type=checkpoint.checkpoint_type,
                checkpoint_sha256=checkpoint.encoded_sha256,
                verification_kind=verification_kind,
                evidence_sha256=effective_evidence_sha256,
                source_request_ordinal=prepared.source_request_ordinal,
                request_ordinal=prepared.source_request_ordinal,
                semantic_outcome=prepared.semantic_outcome,
                semantic_count=prepared.semantic_count,
                sanitized_outcome="passed",
            )
        except BaseException as failure:
            self._evidence_incomplete = True
            self._consume_trusted_observation(prepared.observation)
            transaction.observation_consumed = True
            if requested in _CLEANUP_CHECKPOINT_PHASES:
                # The private checkpoint and its provider observation were already
                # validated and durably consumed.  A public-journal receipt failure
                # must make the run scientifically ineligible, but it must not strand
                # provider/firewall cleanup behind a single-use checkpoint that can no
                # longer be replayed.
                prepared.apply(checkpoint)
                transaction.applied = True
                self.lifecycle = next_lifecycle
                transaction.lifecycle_advanced = True
                self._incident_cleanup_only = True
            else:
                prepared.fail()
            if not isinstance(failure, Exception):
                raise
            raise L2MContractError("checkpoint receipt could not be committed") from None
        self._durable_transition_receipts[checkpoint.encoded_sha256] = receipt_identity
        self._consume_trusted_observation(prepared.observation)
        transaction.observation_consumed = True
        prepared.apply(checkpoint)
        transaction.applied = True
        self.lifecycle = next_lifecycle
        transaction.lifecycle_advanced = True
        return self.lifecycle

    def resume_incident_cleanup(self) -> ManualLifecycle:
        if self.stopped or not self._incident_cleanup_only or not self.lifecycle.incident_active:
            raise L2MContractError("no observer incident is available for cleanup")
        next_lifecycle = self.lifecycle.resume_cleanup()
        try:
            self.journal.reserve_capacity(
                events=1,
                bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES,
            )
            self._append_event("manual_incident", sanitized_outcome="passed")
        except L2MContractError:
            self._evidence_incomplete = True
            raise L2MContractError("incident cleanup resume receipt failed") from None
        self.lifecycle = next_lifecycle
        return self.lifecycle

    def abort_for_separately_authorized_manual_cleanup(
        self,
        *,
        possible_user_mutation_phase: ObserverPhase | None = None,
    ) -> None:
        """Burn this run while preserving a truthful cleanup-required disposition.

        This is the fail-closed boundary for a wrapper failure that cannot safely
        continue the same observer transaction.  It grants no provider authority and
        never claims cleanup.  A later read-only recovery needs a new reviewed run and
        authorization; meanwhile the human operator follows the private console
        incident procedure and keeps the strict firewall in place until every
        incident-scope instance is terminal or absent.
        """

        if self.stopped:
            return
        try:
            self.enter_wrapper_incident(possible_user_mutation_phase=possible_user_mutation_phase)
            self.journal.reserve_capacity(events=1, bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES)
            self._append_event("run_stopped", sanitized_outcome="cleanup_required")
        except BaseException:
            self._evidence_incomplete = True
        finally:
            self._finalize_stopped_run()

    def enter_wrapper_incident(
        self,
        *,
        possible_user_mutation_phase: ObserverPhase | None = None,
    ) -> ManualLifecycle:
        """Enter cleanup-only state after a non-provider wrapper failure.

        The caller supplies only the two user mutation windows whose provider outcome
        can be unknown before a verification GET.  Later phases are derived from the
        engine's lifecycle and never from prose or a raw identifier.
        """

        if (
            self.stopped
            or self.lifecycle.phase is ManualPhase.COMPLETE
            or possible_user_mutation_phase
            not in {
                None,
                ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
                ObserverPhase.RULESET_BIND,
            }
        ):
            raise L2MContractError("wrapper incident cannot enter cleanup")
        self._evidence_incomplete = True
        self._activate_cleanup_incident(possible_user_mutation_phase)
        try:
            self.journal.reserve_capacity(events=1, bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES)
            self._append_event("manual_incident", sanitized_outcome="cleanup_required")
        except L2MContractError:
            self._evidence_incomplete = True
            raise L2MContractError("wrapper incident receipt failed") from None
        return self.lifecycle

    def stop(self, *, outcome: str = "manual_stop") -> None:
        if self.stopped:
            raise L2MContractError("observer run is already stopped")
        if self.lifecycle.phase is not ManualPhase.COMPLETE and (
            self.lifecycle.phase is not ManualPhase.PREFLIGHT or self._must_retain_cleanup(None)
        ):
            self._activate_cleanup_incident(None)
            try:
                self.journal.reserve_capacity(
                    events=1,
                    bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES,
                )
                self._append_event("manual_incident", sanitized_outcome="cleanup_required")
            except L2MContractError:
                self._evidence_incomplete = True
            raise L2MContractError("observer cleanup is mandatory before stop")
        try:
            self.journal.reserve_capacity(
                events=1,
                bytes_upper_bound=MAX_OBSERVER_EVENT_BYTES,
            )
            self._append_event("run_stopped", sanitized_outcome=outcome)
        except L2MContractError:
            self._evidence_incomplete = True
            raise
        finally:
            self._finalize_stopped_run()

    def receipt_integrity_complete(self) -> bool:
        """Cross-check durable receipts against every engine-issued observation/proof."""

        if (
            not self.stopped
            or not self.journal.closed
            or not self.private_observation_store.closed
            or self._evidence_incomplete
            or not self.journal.final_evidence.complete
        ):
            return False
        try:
            events = [
                _mapping(json.loads(line), context="observer receipt event")
                for line in self.journal.final_evidence.encoded.splitlines()
            ]
        except (ValueError, L2MContractError):
            return False
        if any(
            event.get("authorization_sha256") != self.authorization_sha256
            or event.get("authorization_reference") != self.authorization_reference
            or event.get("run_id") != self.run_id
            for event in events
        ):
            return False
        terminal_events = [
            index for index, event in enumerate(events) if event.get("event_type") == "run_stopped"
        ]
        if terminal_events != [len(events) - 1]:
            return False
        observation_receipts: dict[int, tuple[str, str]] = {}
        transition_receipts: dict[str, tuple[int, str, str]] = {}
        for event in events:
            if event.get("event_type") == "observation_completed":
                ordinal = event.get("request_ordinal")
                response_sha256 = event.get("response_sha256")
                request_binding_sha256 = event.get("request_binding_sha256")
                if (
                    type(ordinal) is not int
                    or not isinstance(response_sha256, str)
                    or not isinstance(request_binding_sha256, str)
                    or ordinal in observation_receipts
                ):
                    return False
                observation_receipts[ordinal] = (
                    response_sha256,
                    request_binding_sha256,
                )
            elif event.get("event_type") == "checkpoint_validated":
                checkpoint_sha256 = event.get("checkpoint_sha256")
                source_ordinal = event.get("source_request_ordinal")
                evidence_sha256 = event.get("evidence_sha256")
                verification_kind = event.get("verification_kind")
                if (
                    not isinstance(checkpoint_sha256, str)
                    or type(source_ordinal) is not int
                    or not isinstance(evidence_sha256, str)
                    or not isinstance(verification_kind, str)
                    or checkpoint_sha256 in transition_receipts
                ):
                    return False
                transition_receipts[checkpoint_sha256] = (
                    source_ordinal,
                    evidence_sha256,
                    verification_kind,
                )
        if (
            observation_receipts != self._expected_observation_receipts
            or observation_receipts != self._durable_observation_receipts
            or transition_receipts != self._expected_transition_receipts
            or transition_receipts != self._durable_transition_receipts
        ):
            return False
        private_observations = {
            record.request_ordinal: record
            for record in self.private_observation_store.final_evidence.records
        }
        if private_observations.keys() != self._expected_private_observations.keys():
            return False
        for ordinal, binding in self._expected_private_observations.items():
            record = private_observations[ordinal]
            issued = self._issued_observations.get(ordinal)
            response_identity = observation_receipts.get(ordinal)
            if (
                record.byte_count != binding.projection_bytes
                or record.sha256 != binding.projection_sha256
                or hashlib.sha256(record.encoded).hexdigest() != binding.projection_sha256
                or issued is None
                or response_identity is None
                or issued.operation is not binding.operation
                or issued.response_bytes != binding.raw_response_bytes
                or issued.response_sha256 != binding.raw_response_sha256
                or response_identity[0] != binding.raw_response_sha256
            ):
                return False
            try:
                projection = _mapping(
                    json.loads(record.encoded),
                    context="private observation receipt projection",
                )
            except (UnicodeDecodeError, ValueError, L2MContractError):
                return False
            if (
                set(projection)
                != {
                    "schema_version",
                    "operation",
                    "raw_response_bytes",
                    "raw_response_sha256",
                    "data",
                }
                or projection.get("schema_version") != "0.1.0"
                or projection.get("operation") != binding.operation.value
                or projection.get("raw_response_bytes") != binding.raw_response_bytes
                or projection.get("raw_response_sha256") != binding.raw_response_sha256
            ):
                return False
        return all(
            source_ordinal == 0 or source_ordinal in observation_receipts
            for source_ordinal, _, _ in transition_receipts.values()
        )


_EVIDENCE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,94}\.(?:json|jsonl|zip)$")
_MANIFEST_NAME: Final = "EVIDENCE_MANIFEST.json"
_LOCAL_SEAL_NAME: Final = "LOCAL_EVIDENCE_SEAL.json"
_COPY_RECORD_NAME: Final = "COPY_RECORD.json"
_EXTERNAL_SEAL_NAME: Final = "EXTERNAL_EVIDENCE_SEAL.json"


class _ObserverHardAlarm:
    """Hard process wall supplementing deterministic monotonic deadline checks."""

    def __init__(self, seconds: float, *, message: str) -> None:
        if seconds <= 0:
            raise L2MDeadlineError(message)
        self._message = message
        self._old_handler = signal.getsignal(signal.SIGALRM)
        self._old_timer = signal.getitimer(signal.ITIMER_REAL)
        self._started = time.monotonic()
        self._closed = False
        try:
            signal.signal(signal.SIGALRM, self._expired)
            signal.setitimer(signal.ITIMER_REAL, seconds)
        except (OSError, ValueError):
            with contextlib.suppress(OSError, ValueError):
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, self._old_handler)
            self._closed = True
            raise L2MContractError("observer hard alarm is unavailable") from None

    def _expired(self, signum: int, frame: object) -> None:
        del signum, frame
        raise L2MDeadlineError(self._message)

    def close(self) -> None:
        if self._closed:
            return
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self._old_handler)
        remaining, interval = self._old_timer
        if remaining > 0:
            elapsed = time.monotonic() - self._started
            signal.setitimer(signal.ITIMER_REAL, max(0.001, remaining - elapsed), interval)
        self._closed = True

    def __enter__(self) -> _ObserverHardAlarm:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()


@dataclass(frozen=True, slots=True)
class ObserverEvidenceRecord:
    name: str
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class SealedObserverEvidence:
    run_id: str
    authorization_reference: str
    authorization_sha256: str
    root: Path
    root_device: int
    root_inode: int
    records: tuple[ObserverEvidenceRecord, ...]
    manifest_sha256: str
    local_seal_sha256: str
    total_bytes: int


@dataclass(frozen=True, slots=True)
class ArchivedObserverEvidence:
    destination: Path
    bundle_sha256: str
    total_bytes: int
    destination_hashes_verified: bool
    source_retained: bool


def _write_exclusive_record(directory_fd: int, name: str, encoded: bytes) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory_fd,
    )
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written < 1:
                raise OSError
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
    finally:
        os.close(descriptor)


def _read_bounded_regular_with_identity(
    path: Path, *, max_bytes: int
) -> tuple[bytes, os.stat_result]:
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_uid != os.getuid()
        or before.st_size > max_bytes
    ):
        raise L2MContractError("observer evidence source identity or cap failed")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise L2MContractError("observer evidence source identity changed")
        encoded = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(encoded)))
            if not chunk:
                break
            encoded.extend(chunk)
            if len(encoded) > max_bytes:
                raise L2MContractError("observer evidence source exceeds its cap")
        after = os.fstat(descriptor)
        if (after.st_dev, after.st_ino, after.st_size) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
        ):
            raise L2MContractError("observer evidence source changed while held")
        return bytes(encoded), after
    finally:
        os.close(descriptor)


def _read_bounded_regular(path: Path, *, max_bytes: int) -> bytes:
    encoded, _ = _read_bounded_regular_with_identity(path, max_bytes=max_bytes)
    return encoded


def _read_bounded_regular_at_with_identity(
    directory_descriptor: int,
    name: str,
    *,
    max_bytes: int,
) -> tuple[bytes, os.stat_result]:
    """Read one bounded leaf through a caller-held no-follow directory."""

    if not name or "/" in name or name in {".", ".."}:
        raise L2MContractError("observer evidence leaf name is unsafe")
    before = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_descriptor,
    )
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_uid != os.getuid()
            or opened.st_size > max_bytes
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise L2MContractError("observer held-root evidence identity or cap failed")
        encoded = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(encoded)))
            if not chunk:
                break
            encoded.extend(chunk)
            if len(encoded) > max_bytes:
                raise L2MContractError("observer held-root evidence exceeds its cap")
        after = os.fstat(descriptor)
        linked = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
        ) or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino):
            raise L2MContractError("observer held-root evidence changed while held")
        return bytes(encoded), after
    finally:
        os.close(descriptor)


def _verify_final_evidence_source(
    evidence: ObserverJournalEvidence | CheckpointConsumptionEvidence,
    *,
    max_bytes: int,
    allow_incomplete: bool = False,
) -> bytes:
    if (not evidence.complete and not allow_incomplete) or evidence.byte_count > max_bytes:
        raise L2MContractError("final local evidence token is incomplete or oversized")
    encoded, identity = _read_bounded_regular_with_identity(
        evidence.path,
        max_bytes=max_bytes,
    )
    if (
        identity.st_dev != evidence.device
        or identity.st_ino != evidence.inode
        or len(encoded) != evidence.byte_count
        or encoded != evidence.encoded
        or hashlib.sha256(encoded).hexdigest() != evidence.sha256
    ):
        raise L2MContractError("final local evidence source changed before sealing")
    return encoded


def _verify_private_observation_source(record: PrivateObservationRecord) -> bytes:
    encoded, identity = _read_bounded_regular_with_identity(
        record.path,
        max_bytes=MAX_RESPONSE_BYTES_PER_GET,
    )
    if (
        identity.st_dev != record.device
        or identity.st_ino != record.inode
        or len(encoded) != record.byte_count
        or encoded != record.encoded
        or hashlib.sha256(encoded).hexdigest() != record.sha256
    ):
        raise L2MContractError("private provider observation changed before sealing")
    return encoded


def _read_bounded_at(directory_fd: int, name: str, *, max_bytes: int) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_fd,
    )
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise L2MContractError("observer archive member is not one regular file")
        encoded = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(encoded)))
            if not chunk:
                break
            encoded.extend(chunk)
            if len(encoded) > max_bytes:
                raise L2MContractError("observer archive member exceeds its cap")
        after = os.fstat(descriptor)
        if (after.st_dev, after.st_ino, after.st_size) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
        ):
            raise L2MContractError("observer archive member changed while held")
        return bytes(encoded)
    finally:
        os.close(descriptor)


@dataclass(slots=True)
class L2MObserverEvidenceStore:
    """Fresh, bounded local evidence writer with deterministic one-way sealing."""

    run_id: str
    authorization_reference: str
    authorization_sha256: str
    root: Path
    descriptor: int
    records: list[ObserverEvidenceRecord] = field(default_factory=list)
    bytes_written: int = 0
    sealed: bool = False

    @classmethod
    def create(
        cls,
        repository_root: Path,
        *,
        run_id: str,
        authorization_reference: str,
        authorization_sha256: str,
    ) -> L2MObserverEvidenceStore:
        if (
            _RUN_ID.fullmatch(run_id) is None
            or _AUTHORIZATION_REFERENCE.fullmatch(authorization_reference) is None
            or authorization_reference.endswith("-PENDING")
            or _SHA256.fullmatch(authorization_sha256) is None
        ):
            raise L2MContractError("observer evidence binding is invalid or pending")
        repository = repository_root.resolve(strict=True)
        parent = repository / "artifacts/t07/lambda/gate-l2m"
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        current = repository
        for component in Path("artifacts/t07/lambda/gate-l2m").parts:
            current = current / component
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise L2MContractError("observer evidence hierarchy is unsafe")
        root = parent / run_id
        try:
            root.mkdir(mode=0o700)
        except FileExistsError:
            raise L2MContractError("observer evidence run root already exists") from None
        descriptor = os.open(
            root,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        parent_descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
        return cls(run_id, authorization_reference, authorization_sha256, root, descriptor)

    def retain_file(self, name: str, source: Path, *, max_bytes: int) -> ObserverEvidenceRecord:
        if (
            self.sealed
            or _EVIDENCE_NAME.fullmatch(name) is None
            or any(record.name == name for record in self.records)
        ):
            raise L2MContractError("observer evidence record identity is invalid")
        encoded = _read_bounded_regular(source, max_bytes=max_bytes)
        return self.write_record(name, encoded)

    def write_record(self, name: str, encoded: bytes) -> ObserverEvidenceRecord:
        if (
            self.sealed
            or _EVIDENCE_NAME.fullmatch(name) is None
            or any(record.name == name for record in self.records)
            or len(encoded) > MAX_QUALIFICATION_ARCHIVE_BYTES
            or self.bytes_written + len(encoded) > MAX_LOCAL_SEALED_EVIDENCE_BYTES
        ):
            raise L2MContractError("observer evidence record identity or cap failed")
        try:
            _write_exclusive_record(self.descriptor, name, encoded)
            os.fsync(self.descriptor)
        except OSError:
            raise L2MContractError("observer evidence record write failed") from None
        record = ObserverEvidenceRecord(name, len(encoded), hashlib.sha256(encoded).hexdigest())
        self.records.append(record)
        self.bytes_written += len(encoded)
        return record

    def seal(self) -> SealedObserverEvidence:
        if self.sealed or not self.records:
            raise L2MContractError("observer evidence store is empty or already sealed")
        ordered = tuple(sorted(self.records, key=lambda item: item.name))
        manifest = json.dumps(
            {
                "schema_version": "0.1.0",
                "run_id": self.run_id,
                "authorization_reference": self.authorization_reference,
                "authorization_sha256": self.authorization_sha256,
                "records": [
                    {"name": item.name, "bytes": item.bytes, "sha256": item.sha256}
                    for item in ordered
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        manifest_sha256 = hashlib.sha256(manifest).hexdigest()
        seal = json.dumps(
            {
                "schema_version": "0.1.0",
                "run_id": self.run_id,
                "authorization_reference": self.authorization_reference,
                "authorization_sha256": self.authorization_sha256,
                "manifest_sha256": manifest_sha256,
                "record_count": len(ordered),
                "record_bytes": self.bytes_written,
                "source_retained": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        total = self.bytes_written + len(manifest) + len(seal)
        if total > MAX_LOCAL_SEALED_EVIDENCE_BYTES:
            raise L2MContractError("sealed observer evidence exceeds its local cap")
        try:
            _write_exclusive_record(self.descriptor, _MANIFEST_NAME, manifest)
            _write_exclusive_record(self.descriptor, _LOCAL_SEAL_NAME, seal)
            os.fsync(self.descriptor)
        except OSError:
            raise L2MContractError("observer evidence seal failed") from None
        self.sealed = True
        root_identity = os.fstat(self.descriptor)
        return SealedObserverEvidence(
            self.run_id,
            self.authorization_reference,
            self.authorization_sha256,
            self.root,
            root_identity.st_dev,
            root_identity.st_ino,
            ordered,
            manifest_sha256,
            hashlib.sha256(seal).hexdigest(),
            total,
        )

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1


def _copy_sealed_observer_evidence_held(
    bundle: SealedObserverEvidence,
    *,
    source_fd: int,
    destination_fd: int,
    destination_parent: Path,
    destination_device: int,
    destination_inode: int,
    archive_id: str,
    require_distinct_device: bool = True,
    deadline_check: Callable[[], None] = lambda: None,
) -> ArchivedObserverEvidence:
    """Copy through already-held roots after proving every local sealed identity."""

    deadline_check()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", archive_id):
        raise L2MContractError("observer archive identity is unsafe")
    source_info = os.fstat(source_fd)
    destination_info = os.fstat(destination_fd)
    if (
        not stat.S_ISDIR(source_info.st_mode)
        or not stat.S_ISDIR(destination_info.st_mode)
        or source_info.st_uid != os.getuid()
        or destination_info.st_uid != os.getuid()
        or (source_info.st_dev, source_info.st_ino) != (bundle.root_device, bundle.root_inode)
        or (destination_info.st_dev, destination_info.st_ino)
        != (destination_device, destination_inode)
        or (require_distinct_device and source_info.st_dev == destination_info.st_dev)
    ):
        raise L2MContractError("observer archive source/destination boundary is unsafe")

    source_members: dict[str, bytes] = {}
    for record in bundle.records:
        deadline_check()
        encoded = _read_bounded_at(
            source_fd, record.name, max_bytes=MAX_QUALIFICATION_ARCHIVE_BYTES
        )
        if len(encoded) != record.bytes or hashlib.sha256(encoded).hexdigest() != record.sha256:
            raise L2MContractError("sealed observer record changed after sealing")
        source_members[record.name] = encoded
    expected_manifest = json.dumps(
        {
            "schema_version": "0.1.0",
            "run_id": bundle.run_id,
            "authorization_reference": bundle.authorization_reference,
            "authorization_sha256": bundle.authorization_sha256,
            "records": [
                {"name": item.name, "bytes": item.bytes, "sha256": item.sha256}
                for item in bundle.records
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    actual_manifest = _read_bounded_at(
        source_fd, _MANIFEST_NAME, max_bytes=MAX_OBSERVER_JOURNAL_BYTES
    )
    if (
        actual_manifest != expected_manifest
        or hashlib.sha256(actual_manifest).hexdigest() != bundle.manifest_sha256
    ):
        raise L2MContractError("sealed observer manifest changed after sealing")
    expected_local_seal = json.dumps(
        {
            "schema_version": "0.1.0",
            "run_id": bundle.run_id,
            "authorization_reference": bundle.authorization_reference,
            "authorization_sha256": bundle.authorization_sha256,
            "manifest_sha256": bundle.manifest_sha256,
            "record_count": len(bundle.records),
            "record_bytes": sum(item.bytes for item in bundle.records),
            "source_retained": True,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    actual_local_seal = _read_bounded_at(
        source_fd, _LOCAL_SEAL_NAME, max_bytes=MAX_OBSERVER_JOURNAL_BYTES
    )
    if (
        actual_local_seal != expected_local_seal
        or hashlib.sha256(actual_local_seal).hexdigest() != bundle.local_seal_sha256
        or bundle.total_bytes
        != sum(item.bytes for item in bundle.records)
        + len(actual_manifest)
        + len(actual_local_seal)
    ):
        raise L2MContractError("sealed observer local seal changed after sealing")
    source_members[_MANIFEST_NAME] = actual_manifest
    source_members[_LOCAL_SEAL_NAME] = actual_local_seal

    staging_name = f".{archive_id}.partial"
    staging_fd = -1
    staging_created = False
    finalized = False
    try:
        deadline_check()
        for name in (archive_id, staging_name):
            try:
                os.stat(name, dir_fd=destination_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise L2MContractError("observer archive destination already exists")
        os.mkdir(staging_name, 0o700, dir_fd=destination_fd)
        staging_created = True
        os.fsync(destination_fd)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=destination_fd,
        )
        copied: list[dict[str, object]] = []
        total = 0
        for name, encoded in source_members.items():
            deadline_check()
            digest = hashlib.sha256(encoded).hexdigest()
            _write_exclusive_record(staging_fd, name, encoded)
            deadline_check()
            copied_encoded = _read_bounded_at(
                staging_fd, name, max_bytes=MAX_QUALIFICATION_ARCHIVE_BYTES
            )
            if copied_encoded != encoded:
                raise L2MContractError("observer archive member verification failed")
            copied.append({"name": name, "bytes": len(encoded), "sha256": digest})
            total += len(encoded)
        copy_record = json.dumps(
            {
                "schema_version": "0.1.0",
                "run_id": bundle.run_id,
                "authorization_reference": bundle.authorization_reference,
                "authorization_sha256": bundle.authorization_sha256,
                "archive_id": archive_id,
                "members": copied,
                "destination_hashes_verified": True,
                "source_retained": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        copy_sha256 = hashlib.sha256(copy_record).hexdigest()
        external_seal = json.dumps(
            {
                "schema_version": "0.1.0",
                "run_id": bundle.run_id,
                "authorization_reference": bundle.authorization_reference,
                "authorization_sha256": bundle.authorization_sha256,
                "archive_id": archive_id,
                "copy_record_sha256": copy_sha256,
                "source_manifest_sha256": bundle.manifest_sha256,
                "destination_hashes_verified": True,
                "source_retained": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        total += len(copy_record) + len(external_seal)
        if total > MAX_EXTERNAL_ARCHIVE_BYTES:
            raise L2MContractError("observer external archive exceeds its cap")
        _write_exclusive_record(staging_fd, _COPY_RECORD_NAME, copy_record)
        deadline_check()
        _write_exclusive_record(staging_fd, _EXTERNAL_SEAL_NAME, external_seal)
        os.fsync(staging_fd)
        deadline_check()
        if (
            _read_bounded_at(
                staging_fd,
                _COPY_RECORD_NAME,
                max_bytes=MAX_OBSERVER_JOURNAL_BYTES,
            )
            != copy_record
            or _read_bounded_at(
                staging_fd,
                _EXTERNAL_SEAL_NAME,
                max_bytes=MAX_OBSERVER_JOURNAL_BYTES,
            )
            != external_seal
        ):
            raise L2MContractError("observer archive staging control record drifted")
        os.fsync(staging_fd)
        deadline_check()
        os.rename(
            staging_name,
            archive_id,
            src_dir_fd=destination_fd,
            dst_dir_fd=destination_fd,
        )
        finalized = True
        os.fsync(destination_fd)
        deadline_check()
        for item in copied:
            final_encoded = _read_bounded_at(
                staging_fd,
                str(item["name"]),
                max_bytes=MAX_QUALIFICATION_ARCHIVE_BYTES,
            )
            if (
                len(final_encoded) != item["bytes"]
                or hashlib.sha256(final_encoded).hexdigest() != item["sha256"]
            ):
                raise L2MContractError("finalized observer archive member drifted")
        if (
            _read_bounded_at(staging_fd, _COPY_RECORD_NAME, max_bytes=MAX_OBSERVER_JOURNAL_BYTES)
            != copy_record
            or _read_bounded_at(
                staging_fd, _EXTERNAL_SEAL_NAME, max_bytes=MAX_OBSERVER_JOURNAL_BYTES
            )
            != external_seal
        ):
            raise L2MContractError("finalized observer archive control record drifted")
        final_source = os.fstat(source_fd)
        final_destination = os.fstat(destination_fd)
        final_child = os.stat(archive_id, dir_fd=destination_fd, follow_symlinks=False)
        held_child = os.fstat(staging_fd)
        if (
            (final_source.st_dev, final_source.st_ino)
            != (
                bundle.root_device,
                bundle.root_inode,
            )
            or (final_destination.st_dev, final_destination.st_ino)
            != (
                destination_device,
                destination_inode,
            )
            or not stat.S_ISDIR(final_child.st_mode)
            or (
                final_child.st_dev,
                final_child.st_ino,
            )
            != (
                held_child.st_dev,
                held_child.st_ino,
            )
        ):
            raise L2MContractError("held observer archive root identity drifted")
        deadline_check()
        bundle_sha256 = hashlib.sha256(
            json.dumps(
                {"members": copied, "copy_record_sha256": copy_sha256},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return ArchivedObserverEvidence(
            destination_parent / archive_id,
            bundle_sha256,
            total,
            True,
            True,
        )
    except OSError:
        raise L2MContractError("observer archive filesystem operation failed") from None
    finally:
        if staging_created and not finalized:
            if staging_fd >= 0:
                for name in (
                    *source_members,
                    _COPY_RECORD_NAME,
                    _EXTERNAL_SEAL_NAME,
                ):
                    with contextlib.suppress(FileNotFoundError, OSError):
                        os.unlink(name, dir_fd=staging_fd)
                os.close(staging_fd)
                staging_fd = -1
            with contextlib.suppress(FileNotFoundError, OSError):
                os.rmdir(staging_name, dir_fd=destination_fd)
            with contextlib.suppress(OSError):
                os.fsync(destination_fd)
        if staging_fd >= 0:
            os.close(staging_fd)


def _copy_sealed_observer_evidence(
    bundle: SealedObserverEvidence,
    *,
    destination_parent: Path,
    archive_id: str,
    require_distinct_device: bool = True,
    deadline_check: Callable[[], None] = lambda: None,
) -> ArchivedObserverEvidence:
    """Path convenience wrapper; production uses the held-descriptor entry point."""

    source_info = bundle.root.lstat()
    destination_info = destination_parent.lstat()
    source_fd = os.open(
        bundle.root,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    destination_fd = os.open(
        destination_parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        if (
            (source_info.st_dev, source_info.st_ino) != (bundle.root_device, bundle.root_inode)
            or (os.fstat(source_fd).st_dev, os.fstat(source_fd).st_ino)
            != (bundle.root_device, bundle.root_inode)
            or (os.fstat(destination_fd).st_dev, os.fstat(destination_fd).st_ino)
            != (destination_info.st_dev, destination_info.st_ino)
        ):
            raise L2MContractError("observer archive directory identity changed")
        archived = _copy_sealed_observer_evidence_held(
            bundle,
            source_fd=source_fd,
            destination_fd=destination_fd,
            destination_parent=destination_parent,
            destination_device=destination_info.st_dev,
            destination_inode=destination_info.st_ino,
            archive_id=archive_id,
            require_distinct_device=require_distinct_device,
            deadline_check=deadline_check,
        )
        linked_destination = destination_parent.lstat()
        if (linked_destination.st_dev, linked_destination.st_ino) != (
            destination_info.st_dev,
            destination_info.st_ino,
        ):
            raise L2MContractError("observer archive destination path changed")
        return archived
    finally:
        os.close(destination_fd)
        os.close(source_fd)


def _run_l2m_diskutil_streaming(
    argv: tuple[str, ...], *, max_output_bytes: int
) -> tuple[bytes, int]:
    """Run one exact read-only storage observation with a streaming ceiling."""

    from giclab.harness.lambda_cloud import secret_free_child_environment

    if not 0 < max_output_bytes <= L2M_DISKUTIL_OUTPUT_CAP_BYTES:
        raise L2MContractError("L2M storage output budget is unavailable")
    try:
        process = subprocess.Popen(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=secret_free_child_environment(),
            shell=False,
            bufsize=0,
        )
    except OSError:
        raise L2MContractError("L2M storage observation failed") from None
    if process.stdout is None or process.stderr is None:  # pragma: no cover
        process.kill()
        process.wait()
        raise L2MContractError("L2M storage observation pipe is unavailable")
    selector = selectors.DefaultSelector()
    stdout_chunks: list[bytes] = []
    total = 0
    deadline = time.monotonic() + L2M_DISKUTIL_TIMEOUT_SECONDS
    try:
        selector.register(process.stdout, selectors.EVENT_READ, data="stdout")
        selector.register(process.stderr, selectors.EVENT_READ, data="stderr")
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise L2MContractError("L2M storage observation timed out")
            events = selector.select(remaining)
            if not events:
                raise L2MContractError("L2M storage observation timed out")
            for key, _ in events:
                chunk = os.read(key.fd, min(65_536, max_output_bytes + 1 - total))
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                total += len(chunk)
                if total > max_output_bytes:
                    raise L2MContractError("L2M storage observation exceeded its output cap")
                if key.data == "stdout":
                    stdout_chunks.append(chunk)
        return_code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        if return_code != 0:
            raise L2MContractError("L2M storage observation returned failure")
        return b"".join(stdout_chunks), total
    except (OSError, subprocess.SubprocessError):
        raise L2MContractError("L2M storage observation failed") from None
    finally:
        if process.poll() is None:
            with contextlib.suppress(OSError):
                process.kill()
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                process.wait()
        selector.close()
        process.stdout.close()
        process.stderr.close()


@dataclass(slots=True)
class L2MDiskutilVolumeObserver:
    """L2M-only storage observer that burns calls and is terminal after failure."""

    max_calls: int = L2M_MAX_DISKUTIL_CALLS
    max_output_bytes: int = L2M_MAX_DISKUTIL_CALLS * L2M_DISKUTIL_OUTPUT_CAP_BYTES
    calls: int = 0
    output_bytes: int = 0
    failed: bool = False

    def _observe(self, argv: tuple[str, ...]) -> bytes:
        if self.failed:
            raise L2MContractError("L2M storage observer is terminal after failure")
        if self.calls + 1 > self.max_calls:
            raise L2MContractError("L2M storage observation call cap exhausted")
        remaining = self.max_output_bytes - self.output_bytes
        if remaining <= 0:
            raise L2MContractError("L2M storage observation output cap exhausted")
        self.calls += 1
        try:
            encoded, observed_bytes = _run_l2m_diskutil_streaming(
                argv,
                max_output_bytes=min(L2M_DISKUTIL_OUTPUT_CAP_BYTES, remaining),
            )
        except L2MContractError:
            self.failed = True
            raise
        self.output_bytes += observed_bytes
        return encoded

    def __call__(self) -> tuple[object, object]:
        from giclab.harness.sira_storage import (
            APPROVED_MOUNT,
            SYSTEM_DATA_MOUNT,
            StorageContractError,
            volume_observation_from_diskutil,
        )

        if self.failed or self.calls + 3 > self.max_calls:
            raise L2MContractError("L2M storage observation call cap exhausted")
        external_info = self._observe(("/usr/sbin/diskutil", "info", "-plist", str(APPROVED_MOUNT)))
        system_info = self._observe(
            ("/usr/sbin/diskutil", "info", "-plist", str(SYSTEM_DATA_MOUNT))
        )
        apfs_list = self._observe(("/usr/sbin/diskutil", "apfs", "list", "-plist"))
        try:
            return (
                volume_observation_from_diskutil(external_info, apfs_list),
                volume_observation_from_diskutil(system_info, apfs_list),
            )
        except StorageContractError:
            self.failed = True
            raise L2MContractError("L2M storage identity validation failed") from None


def copy_sealed_observer_evidence_to_approved_external(
    bundle: SealedObserverEvidence,
    *,
    archive_id: str,
    volume_observer: Callable[[], tuple[object, object]] | None = None,
    deadline_check: Callable[[], None] = lambda: None,
) -> ArchivedObserverEvidence:
    """Bind the one-way copy to the approved UTDM APFS identity and space floors."""

    from giclab.harness.lambda_archive import (
        InventoryArchiveError,
        _HeldDirectory,
        _open_or_create_archive_root,
        _same_identity,
        _validate_external,
        _validate_system,
    )
    from giclab.harness.lambda_l20_plan import (
        EXTERNAL_ARCHIVE_ROOT,
        MIN_LOCAL_PREWRITE_FREE_BYTES,
        MIN_LOCAL_RETAINED_FREE_BYTES,
    )
    from giclab.harness.sira_storage import VolumeObservation

    observe = volume_observer or L2MDiskutilVolumeObserver(
        max_calls=MAX_LOCAL_PROCESS_CALLS,
        max_output_bytes=MAX_LOCAL_PROCESS_OUTPUT_BYTES,
    )
    try:
        deadline_check()
        external_before, system_before = observe()
        deadline_check()
        if not isinstance(external_before, VolumeObservation) or not isinstance(
            system_before, VolumeObservation
        ):
            raise InventoryArchiveError("storage observer returned an invalid type")
        _validate_external(external_before, incremental_bytes=MAX_EXTERNAL_ARCHIVE_BYTES)
        _validate_system(system_before, floor_bytes=MIN_LOCAL_PREWRITE_FREE_BYTES)
        external_mount = _HeldDirectory.open(Path("/Volumes/Macintosh HD - Data"))
        archive_root = None
        source_fd = -1
        try:
            archive_root = _open_or_create_archive_root(external_mount, EXTERNAL_ARCHIVE_ROOT)
            external_mount.revalidate()
            archive_root.revalidate()
            source_fd = os.open(
                bundle.root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
            archived = _copy_sealed_observer_evidence_held(
                bundle,
                source_fd=source_fd,
                destination_fd=archive_root.descriptor,
                destination_parent=EXTERNAL_ARCHIVE_ROOT,
                destination_device=archive_root.device,
                destination_inode=archive_root.inode,
                archive_id=archive_id,
                require_distinct_device=True,
                deadline_check=deadline_check,
            )
            deadline_check()
            archive_root.revalidate()
            external_mount.revalidate()
            retained_source = bundle.root.lstat()
            if (retained_source.st_dev, retained_source.st_ino) != (
                bundle.root_device,
                bundle.root_inode,
            ):
                raise InventoryArchiveError("local sealed observer source identity changed")
            external_after, system_after = observe()
            deadline_check()
            if not isinstance(external_after, VolumeObservation) or not isinstance(
                system_after, VolumeObservation
            ):
                raise InventoryArchiveError("storage observer returned an invalid type")
            if not _same_identity(external_before, external_after) or not _same_identity(
                system_before, system_after
            ):
                raise InventoryArchiveError("storage identity changed during L2M copy")
            _validate_external(external_after, incremental_bytes=0)
            _validate_system(system_after, floor_bytes=MIN_LOCAL_RETAINED_FREE_BYTES)
            observed_calls = getattr(observe, "calls", 0)
            observed_output = getattr(observe, "output_bytes", 0)
            if (
                type(observed_calls) is not int
                or type(observed_output) is not int
                or observed_calls > MAX_LOCAL_PROCESS_CALLS
                or observed_output > MAX_LOCAL_PROCESS_OUTPUT_BYTES
            ):
                raise InventoryArchiveError("L2M storage observation budget exceeded")
            return archived
        finally:
            if source_fd >= 0:
                os.close(source_fd)
            if archive_root is not None:
                try:
                    archive_root.revalidate()
                finally:
                    archive_root.close()
            try:
                external_mount.revalidate()
            finally:
                external_mount.close()
    except (OSError, InventoryArchiveError):
        raise L2MContractError("approved external observer archive contract failed") from None


def _seal_observer_evidence_impl(
    engine: L2MReadOnlyObserverEngine,
    *,
    repository_root: Path,
    qualification_archive_path: Path | None = None,
    deadline_check: Callable[[], None],
) -> SealedObserverEvidence:
    """Retain and seal one complete local observer evidence set."""

    deadline_check()
    if not engine.stopped or not engine.journal.closed:
        raise L2MContractError("observer must be stopped and journal-closed before sealing")
    if (
        engine._stopped_ns is None
        or engine.clock_ns() - engine._stopped_ns > MAX_OBSERVER_ARCHIVE_SECONDS * 1_000_000_000
    ):
        raise L2MContractError("observer archive wall cap exhausted")
    journal_encoded = _verify_final_evidence_source(
        engine.journal.final_evidence,
        max_bytes=MAX_OBSERVER_JOURNAL_BYTES,
        allow_incomplete=True,
    )
    checkpoint_encoded = _verify_final_evidence_source(
        engine.checkpoint_reader.final_evidence,
        max_bytes=262_144,
        allow_incomplete=True,
    )
    private_observation_records = engine.private_observation_store.final_evidence.records
    validated_qualification = engine._validated_qualification
    validated_qualification_failure = engine._validated_qualification_failure
    receipt_integrity_complete = engine.receipt_integrity_complete()
    if qualification_archive_path is not None and (
        validated_qualification is None
        or qualification_archive_path.absolute() != validated_qualification.archive_path
    ):
        raise L2MContractError("qualification archive is not the engine-validated source")
    effective_qualification_path = (
        None if validated_qualification is None else validated_qualification.archive_path
    )
    qualification_encoded: bytes | None = None
    if effective_qualification_path is not None:
        if validated_qualification is None:  # pragma: no cover - derived above
            raise L2MContractError("qualification token disappeared")
        qualification_encoded = engine._validated_qualification_encoded
        if (
            qualification_encoded is None
            or len(qualification_encoded) != validated_qualification.archive_bytes
            or hashlib.sha256(qualification_encoded).hexdigest()
            != validated_qualification.archive_sha256
        ):
            raise L2MContractError("validated qualification bytes changed before sealing")
    qualification_failure_encoded: bytes | None = None
    if validated_qualification_failure is not None:
        qualification_failure_encoded = engine._validated_qualification_failure_encoded
        if (
            qualification_failure_encoded is None
            or validated_qualification_failure._issuer is not engine._proof_issuer
            or validated_qualification_failure.run_id != engine.run_id
            or validated_qualification_failure.authorization_reference
            != engine.authorization_reference
            or len(qualification_failure_encoded) != validated_qualification_failure.archive_bytes
            or hashlib.sha256(qualification_failure_encoded).hexdigest()
            != validated_qualification_failure.archive_sha256
        ):
            raise L2MContractError("validated qualification failure bytes changed before sealing")
    source_evidence_bytes = (
        len(journal_encoded)
        + len(checkpoint_encoded)
        + sum(record.byte_count for record in private_observation_records)
        + (0 if qualification_encoded is None else len(qualification_encoded))
        + (0 if qualification_failure_encoded is None else len(qualification_failure_encoded))
    )
    if source_evidence_bytes > MAX_LOCAL_SOURCE_EVIDENCE_BYTES:
        raise L2MContractError("observer retained source evidence exceeds its local cap")
    deadline_check()
    store = L2MObserverEvidenceStore.create(
        repository_root,
        run_id=engine.run_id,
        authorization_reference=engine.authorization_reference,
        authorization_sha256=engine.authorization_sha256,
    )
    try:
        store.write_record("observer-journal.jsonl", journal_encoded)
        deadline_check()
        store.write_record("checkpoint-consumption.jsonl", checkpoint_encoded)
        deadline_check()
        for record in private_observation_records:
            store.write_record(
                f"provider-observation-{record.request_ordinal:04d}.json",
                _verify_private_observation_source(record),
            )
            deadline_check()
        if qualification_encoded is not None:
            store.write_record("qualification-evidence.zip", qualification_encoded)
            deadline_check()
        if qualification_failure_encoded is not None:
            store.write_record(
                "qualification-failure-evidence.zip",
                qualification_failure_encoded,
            )
            deadline_check()
        store.write_record(
            "terminal-summary.json",
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": engine.run_id,
                    "authorization_reference": engine.authorization_reference,
                    "authorization_sha256": engine.authorization_sha256,
                    "human_decision_sha256": engine.human_decision.decision_sha256,
                    "lifecycle_phase": engine.lifecycle.phase.value,
                    "strict_firewall_preserved": engine.lifecycle.strict_firewall_preserved,
                    "observer_gets": engine.budget.request_count,
                    "observer_response_bytes": engine.budget.response_bytes,
                    "observer_elapsed_ms": engine.budget.elapsed_ms,
                    "cloud_mutations_by_observer": 0,
                    "automatic_retries": 0,
                    "pagination_requests": 0,
                    "qualification_validated": validated_qualification is not None,
                    "qualification_checkpoint_consumed": engine._qualification_consumed,
                    "qualification_failure_validated": (
                        validated_qualification_failure is not None
                    ),
                    "qualification_failure_cleanup_complete": (
                        None
                        if validated_qualification_failure is None
                        else validated_qualification_failure.cleanup_complete
                    ),
                    "deadline_breached": engine._deadline_breached,
                    "observer_journal_complete": engine.journal.final_evidence.complete,
                    "receipt_integrity_complete": receipt_integrity_complete,
                    "checkpoint_consumption_complete": (
                        engine.checkpoint_reader.final_evidence.complete
                    ),
                    "source_integrity_verified": True,
                    "evidence_complete": (
                        receipt_integrity_complete and not engine._evidence_incomplete
                    ),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode(),
        )
        deadline_check()
        sealed = store.seal()
        deadline_check()
        if source_evidence_bytes + sealed.total_bytes > MAX_MAC_ACTIVE_EVIDENCE_BYTES:
            raise L2MContractError("observer aggregate local retained evidence exceeds its cap")
        if (
            engine._stopped_ns is None
            or engine.clock_ns() - engine._stopped_ns > MAX_OBSERVER_ARCHIVE_SECONDS * 1_000_000_000
        ):
            raise L2MContractError("observer archive wall cap exhausted during sealing")
        return sealed
    finally:
        store.close()


def _archive_deadline(
    engine: L2MReadOnlyObserverEngine,
) -> tuple[Callable[[], None], float]:
    if engine._stopped_ns is None:
        raise L2MContractError("observer stop time is unavailable")
    deadline_ns = engine._stopped_ns + MAX_OBSERVER_ARCHIVE_SECONDS * 1_000_000_000

    def check() -> None:
        if engine.clock_ns() >= deadline_ns:
            raise L2MContractError("observer archive wall cap exhausted")

    remaining = (deadline_ns - engine.clock_ns()) / 1_000_000_000
    check()
    return check, remaining


def seal_observer_evidence(
    engine: L2MReadOnlyObserverEngine,
    *,
    repository_root: Path,
    qualification_archive_path: Path | None = None,
) -> SealedObserverEvidence:
    """Retain and seal under one hard and one monotonic archive deadline."""

    deadline_check, remaining = _archive_deadline(engine)
    with _ObserverHardAlarm(remaining, message="observer archive hard deadline exceeded"):
        return _seal_observer_evidence_impl(
            engine,
            repository_root=repository_root,
            qualification_archive_path=qualification_archive_path,
            deadline_check=deadline_check,
        )


def seal_and_copy_observer_evidence_to_approved_external(
    engine: L2MReadOnlyObserverEngine,
    *,
    repository_root: Path,
    archive_id: str,
    qualification_archive_path: Path | None = None,
    volume_observer: Callable[[], tuple[object, object]] | None = None,
) -> tuple[SealedObserverEvidence, ArchivedObserverEvidence]:
    """Seal locally and copy only through the approved UTDM archive guard."""

    deadline_check, remaining = _archive_deadline(engine)
    with _ObserverHardAlarm(remaining, message="observer archive hard deadline exceeded"):
        sealed = _seal_observer_evidence_impl(
            engine,
            repository_root=repository_root,
            qualification_archive_path=qualification_archive_path,
            deadline_check=deadline_check,
        )
        archived = copy_sealed_observer_evidence_to_approved_external(
            sealed,
            archive_id=archive_id,
            volume_observer=volume_observer,
            deadline_check=deadline_check,
        )
        deadline_check()
        return sealed, archived
