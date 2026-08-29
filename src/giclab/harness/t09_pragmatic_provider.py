"""Exact provider lifecycle for the authorized T09 Retry 5 campaign.

This module is inert on import.  It reuses the provider request pattern retained by
the successful T07 pragmatic run, but makes its previously implicit lifecycle
contract explicit: separate cumulative-active, per-launch-preflight, and empirical
campaign clocks; at most two pre-empirical launch slots; one simultaneous owned
instance; bounded read-only polls; exact-target
termination, and source-bound entry/closeout receipts.  It is deliberately a small
linear lifecycle utility, not a general cloud platform or an independent watchdog.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import json
import os
import pwd
import re
import shutil
import ssl
import stat
import subprocess
import tarfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol, cast

import yaml

from giclab.harness.lambda_campaign_lifecycle import (
    AutonomousPilotLifecycleLimits,
    ObserverLifecycleLimits,
    Retry4LifecycleLimits,
)
from giclab.harness.lambda_l2m_observer import (
    MAX_RESPONSE_BYTES_PER_GET,
    LambdaHttpsL2MObserverTransport,
    ObserverOperation,
    ObserverTransportFailure,
    observer_request,
)
from giclab.harness.t09_cleanup_state import (
    CleanupLifecycleStage,
    CleanupTargetKind,
    CleanupTargetState,
    EarlyCleanupJournal,
    EarlyCleanupState,
    EarlyCleanupStateError,
)
from giclab.harness.t09_model_metadata_receipt import (
    MODEL_METADATA_PRELAUNCH_FRESHNESS_SECONDS,
    MODEL_METADATA_RECEIPT_FILENAME,
    ModelMetadataReceiptError,
    ModelMetadataReceiptValidationPolicy,
    ModelMetadataTransport,
    admit_model_metadata_receipt_at_prelaunch_boundary,
    bind_model_metadata_receipt_to_authorization_overlay,
    copy_model_metadata_receipt,
    create_model_metadata_receipt,
    model_metadata_authorization_overlay_sha256,
    model_metadata_receipt_sha256,
    semantic_projection_sha256,
    validate_model_metadata_authorization_overlay,
    validate_model_metadata_receipt,
)
from giclab.harness.t09_provider_contracts import (
    V5_PROVIDER_CONTRACT,
    V6_PROVIDER_CONTRACT,
    V7_PROVIDER_CONTRACT,
    V12_PROVIDER_CONTRACT,
    T09ProviderContract,
    T09ProviderContractError,
    load_provider_profile,
    provider_contract,
)

AUTONOMOUS_V9_LAUNCH_PACKAGE_COMMIT: Final = "807eab38d6dfec9aac0a154964c2997be994c9e9"
AUTONOMOUS_V9_STALE_COMMAND_AUTHORIZATION_SHA256S: Final = {
    "RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0002": (
        "eb48b64981a0e887881ed84e866bd5c56d870fec922875843d1efee21f3b20e2"
    ),
    "RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0002": (
        "83bb878d45499946c235812b5f584ae6ffa78b0b884d62d00575649a4953fc5e"
    ),
    "RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0002": (
        "c278c925964a237f7d40cc8816ecebfb76ec7ed99d912307fb0147691b3870ae"
    ),
    "RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0002": (
        "13bccb6d8009bae1c5bebae54d0574d28faeed77452cf3a279c5044eb545c68b"
    ),
}
HISTORICAL_V9_AUTHORIZATION_SOURCE_SHA256: Final = (
    "aea63a42cf0270ad0a41a929b4b8eb19dd1c3af73abfe97163c1d90e6077d3da"
)
API_HOST: Final = "cloud.lambda.ai"
API_PORT: Final = 443
INSTANCE_TYPE: Final = "gpu_1x_a10"
REGION: Final = "us-east-1"
IMAGE_ID: Final = "44fab622-b98a-49fe-ac6d-e4ce5531532f"
SSH_KEY_NAME: Final = "fractal-lambda-codex"
PRICE_CENTS_PER_HOUR: Final = 129
SLOT1_PACKAGE_COMMIT: Final = "3640f061ea6c0f0f3d24bf2a346d4beda1a400cf"
SLOT1_PLAN_SHA256: Final = "e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c"
SLOT1_CLOSEOUT_RECEIPT_SHA256: Final = (
    "a162c3b2f3d068da365ecdb7450fa0c4be8656983c9b7a7697ec85d8993ef034"
)
SLOT1_CLOSEOUT_SOURCE_MANIFEST_SHA256: Final = (
    "9b8b04b93697746feb65d016f97a7852d5ee0aae70c66a60750cde156e687ad9"
)
SLOT1_ZERO_USE_ARCHIVE_SHA256: Final = (
    "a4e07e03a68816f1c59a27a90863b2db5ae8d36956c539c3ede6bdf80b43feb4"
)
SLOT1_ZERO_USE_ARCHIVE_BYTES: Final = 547_824
SLOT1_IMAGE_ARCHIVE_SHA256: Final = (
    "623e717c2182eca9cee2f471b7ecd9a57bead2f5263dee64aa5cd954eae5ddb0"
)
SLOT1_IMAGE_ARCHIVE_BYTES: Final = 1_207_128_576
SLOT1_REPLACEMENT_IMAGE_ID: Final = (
    "sha256:abe8ed38f5c5b5a0a63fa726a74034dc5c192a12c0fccfe1319f97c27ceaf0a3"
)
SLOT1_QUALIFICATION_ID: Final = "QUAL-T09-PILOT-V5-IMAGE-0001"
SLOT2_QUALIFICATION_ID: Final = "QUAL-T09-PILOT-V5-IMAGE-0002"
SLOT2_ELIGIBILITY_KIND: Final = "post-closeout-built-image-slot1"
SLOT2_MINIMUM_LAUNCH_REMAINING_SECONDS: Final = 4_500
SLOT2_TRANSITION_ALLOWED_PATHS: Final = frozenset(
    {
        "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py",
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        "docs/harness/T09_PRAGMATIC_RETRY3_EXECUTION_PLAN.md",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_EXECUTION_CONTRACT.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_RUNTIME_IDENTITY.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/"
        "T09_PRAGMATIC_RETRY3_FINALIZER_REGRESSION.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v5-task-0000-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v5-task-0000-simulative.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v5-task-0001-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v5-task-0001-simulative.yaml",
        "schemas/t09-sira-pilot-evidence.schema.json",
        "src/giclab/harness/t09_pragmatic_provider.py",
        "src/giclab/harness/sira_gate_a_runtime.py",
        "src/giclab/harness/t09_sira_pilot.py",
        "tests/test_t09_retry3.py",
        "tests/test_t09_sira_pilot.py",
    }
)
RETRY4_SLOT1_PACKAGE_COMMIT: Final = "4e8b71771a5e7baf9b104b6f3b5466091e4596f2"
RETRY4_PLAN_ID: Final = "PLAN-EXP0001-PILOT-V6"
RETRY4_HOST_RUN_ID: Final = "RUN-T09-PILOT-HOST-0004"
RETRY4_AUTHORIZATION_SOURCE_SHA256: Final = (
    "e3222d38c9b21091a51839122d42594d691577716bc87fd3e09296c6b766df51"
)
RETRY4_SLOT1_PLAN_SHA256: Final = "d0294b3a1535c4fe4ddfcc856a6b923731a7fb0c7840dd161c5784db61f35d8c"
RETRY4_SLOT1_EXECUTION_SHA256: Final = (
    "5502318816bd088add14adf6b32759c062141e490bca9ba743a60dc3cff46919"
)
RETRY4_SLOT1_RUNTIME_SHA256: Final = (
    "e3bbb5bfeda2007ba918d365c01445f8f48c1bb37d4dd7571627cbd633aead90"
)
RETRY4_SLOT1_COMMANDS_SHA256: Final = (
    "5d7533b437cd8a335da6feae12475e20e986d8a03635da3fb4dd166264bde2c8"
)
RETRY4_SLOT1_ENTRY_RECEIPT_SHA256: Final = (
    "0c890a24b054ed3ddf0816c7e3c1d0da2601d03b3438d932e43a06e6df3a8335"
)
RETRY4_SLOT1_ENTRY_SOURCE_MANIFEST_SHA256: Final = (
    "0e96f1d7465d798f69ecfb264a815af2987bb814f6677d6e64fbdaf0412b74cd"
)
RETRY4_SLOT1_CLOSEOUT_RECEIPT_SHA256: Final = (
    "5dd82529791777519815a857cc83461568a6909889f4bbef57f3cd0ae743c953"
)
RETRY4_SLOT1_CLOSEOUT_SOURCE_MANIFEST_SHA256: Final = (
    "219e246e22257b874caa0b9a3ae88afaa89684811b310c00dcb71ef4e1121aa2"
)
RETRY4_SLOT1_FAILURE_ARCHIVE_SHA256: Final = (
    "18f6c7d6bcda6f6be4c53854dc89d1fd08fb286393fba187815184db8819134f"
)
RETRY4_SLOT1_FAILURE_ARCHIVE_BYTES: Final = 597_140
RETRY4_SLOT1_FROZEN_MANIFEST_SHA256: Final = (
    "4477f5313100422cb4415bf636e2cd476fc59a2bf1548fa3390ced7ecc306a57"
)
RETRY4_SLOT1_POSTFREEZE_SHA256: Final = (
    "348f1d659a57f075513b828ee3a17592d3081d108cbe972c812db5f868888bf2"
)
RETRY4_SLOT1_PREFLIGHT_SHA256: Final = (
    "aa333beb30db610223017b379074568c8a269a091405e7475b7f5e6fdfa8d39d"
)
RETRY4_SLOT1_BUILT_IMAGE_ID: Final = (
    "sha256:4ce9c92a37458587355d7525bea2f61d381e160c4fa62fcb64e5bdbfac4dab05"
)
RETRY4_SLOT1_CONDITION_STDERR_SHA256: Final = (
    "a9bc40f78d9f446abf5c3e97078f0dc01ae39679f4743943d782701dd2e4171e"
)
RETRY4_SLOT2_ELIGIBILITY_KIND: Final = "retry4-postfreeze-preentry-condition-failure"
RETRY4_SLOT2_TRANSITION_ALLOWED_PATHS: Final = frozenset(
    {
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        "docs/PROJECT_STATE.yaml",
        "docs/harness/T09_PRAGMATIC_RETRY4_EXECUTION_PLAN.md",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_EXECUTION_CONTRACT.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_RUNTIME_IDENTITY.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0000-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0000-simulative.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0001-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v6-task-0001-simulative.yaml",
        "src/giclab/harness/sira_gate_a_runtime.py",
        "src/giclab/harness/t09_pragmatic_provider.py",
        "src/giclab/harness/t09_sira_pilot.py",
        "tests/test_t09_retry4.py",
        "tests/test_t09_sira_pilot.py",
    }
)
RETRY4_ACTIVE_SLOT2_ENTRY_PACKAGE_COMMIT: Final = "9275bed0cce8bff5e033b94c9fcc8767af629fcd"
RETRY5_ACTIVE_SLOT1_PACKAGE_COMMIT: Final = "02524c74bfefdae6f1237b9c211d579294214cb6"
RETRY5_ACTIVE_SLOT1_PLAN_SHA256: Final = (
    "9f66f8f6ee9e137d27e86c5362187fe46d94b26a322994e55222e34c0c4c004e"
)
RETRY5_SLOT2_TRANSITION_ALLOWED_PATHS: Final = frozenset(
    {
        "containers/sira-smoke/pragmatic/t09_remote_runner.py",
        "docs/PROJECT_STATE.yaml",
        "docs/harness/T09_PRAGMATIC_RETRY5_EXECUTION_PLAN.md",
        "experiments/EXP-0001-sira-simulative-vs-reactive/"
        "T09_PRAGMATIC_RETRY5_TERMINAL_CONTROL.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_EXECUTION_CONTRACT.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_RUNTIME_IDENTITY.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v7-task-0000-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v7-task-0000-simulative.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v7-task-0001-reactive.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/"
        "pilot-v7-task-0001-simulative.yaml",
        "experiments/registry.yaml",
        "src/giclab/harness/t09_pragmatic_provider.py",
        "tests/test_t09_retry5.py",
    }
)
SOURCE_OBSERVER: Final = "t09-retry5-pragmatic-mutations-plus-l2m-read-only-observer-v1"
MAX_RESPONSE_BYTES: Final = 16_777_216
MAX_REQUEST_BYTES: Final = 65_536
MAX_ENTRY_POLLS: Final = 120
MAX_TERMINATION_POLLS: Final = 120
MAX_TERMINATION_POSTS: Final = 3
POLL_SECONDS: Final = 5.0
REQUEST_TIMEOUT_SECONDS: Final = 60.0
MAX_DOTENV_BYTES: Final = 65_536
TERMINAL_STATES: Final = frozenset({"terminated", "preempted"})
ALLOWED_PATHS: Final = frozenset(
    {
        "/api/v1/instance-types",
        "/api/v1/images",
        "/api/v1/ssh-keys",
        "/api/v1/firewall-rulesets",
        "/api/v1/firewall-rulesets/global",
        "/api/v1/instances",
        "/api/v1/instance-operations/launch",
        "/api/v1/instance-operations/terminate",
    }
)
_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_DOTENV_VALUE = re.compile(rb"^[A-Za-z0-9._:/+\-=]{16,4096}$")


class T09ProviderError(RuntimeError):
    """The exact pragmatic provider lifecycle failed closed."""


class ProviderOutcomeUnknown(T09ProviderError):
    """A request crossed send-start but no trustworthy response was retained."""

    def __init__(self, operation: str) -> None:
        super().__init__(f"provider operation outcome is unknown: {operation}")
        self.operation = operation


@dataclass(frozen=True, slots=True)
class CampaignLifecycle:
    contract: T09ProviderContract
    limits: AutonomousPilotLifecycleLimits | Retry4LifecycleLimits | ObserverLifecycleLimits
    max_instances: int
    max_launches: int
    persistent_filesystems: int

    def __post_init__(self) -> None:
        expected_limits: object
        if self.contract.version in {"V3", "V4", "V5"}:
            expected_limits = ObserverLifecycleLimits.t09_pragmatic_v3()
        elif self.contract.version in {"V6", "V7"}:
            expected_limits = Retry4LifecycleLimits()
        elif self.contract.version == "V8":
            expected_limits = AutonomousPilotLifecycleLimits(
                maximum_preflight_provider_cost_cents=2_000
            )
        elif self.contract.version in {"V9", "V10", "V11", "V12"}:
            expected_limits = AutonomousPilotLifecycleLimits()
        else:  # pragma: no cover - contracts validate supported versions before construction
            raise T09ProviderError("unsupported provider lifecycle contract")
        if (
            self.limits != expected_limits
            or self.max_instances != 1
            or self.max_launches != self.contract.max_launch_count
            or self.persistent_filesystems != 0
        ):
            raise T09ProviderError("pilot provider lifecycle drifted")

    @property
    def wall_seconds(self) -> int:
        if isinstance(self.limits, ObserverLifecycleLimits):
            return self.limits.campaign_provider_wall_seconds
        return self.limits.empirical_campaign_wall_seconds

    @property
    def preflight_wall_seconds(self) -> int:
        if isinstance(self.limits, AutonomousPilotLifecycleLimits):
            return self.limits.maximum_preflight_instance_active_seconds
        if isinstance(self.limits, Retry4LifecycleLimits):
            return self.limits.preflight_wall_seconds
        return 0

    @property
    def cleanup_reserve_seconds(self) -> int:
        if isinstance(self.limits, ObserverLifecycleLimits):
            return self.limits.cleanup_reserve_seconds
        return self.limits.empirical_cleanup_reserve_seconds

    @property
    def termination_cutoff_seconds(self) -> int:
        if isinstance(self.limits, ObserverLifecycleLimits):
            return self.limits.normal_termination_cutoff_seconds
        return self.limits.empirical_termination_cutoff_seconds

    @property
    def maximum_cumulative_preflight_active_seconds(self) -> int:
        if isinstance(self.limits, AutonomousPilotLifecycleLimits):
            return self.limits.maximum_cumulative_preflight_active_seconds
        if isinstance(self.limits, Retry4LifecycleLimits):
            return self.limits.maximum_cumulative_active_seconds
        return self.limits.campaign_provider_wall_seconds * self.max_launches

    def elapsed(self, *, started_at_epoch: float, now_epoch: float) -> float:
        if now_epoch < started_at_epoch:
            raise T09ProviderError("provider clock moved before its billable origin")
        return now_epoch - started_at_epoch

    def termination_due(self, *, started_at_epoch: float, now_epoch: float) -> bool:
        return self.elapsed(started_at_epoch=started_at_epoch, now_epoch=now_epoch) >= (
            self.termination_cutoff_seconds
        )


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    status: int
    content_type: str
    body: bytes = field(repr=False)
    received_at_epoch: float


class ProviderTransport(Protocol):
    def send(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        credential: bytearray,
    ) -> ProviderResponse: ...


class LambdaTransport:
    """Thin T09 adapter over the exact T07 pragmatic/observer request path.

    Every GET delegates to the existing T07 observer transport.  The only local
    extension is the two already-used T07 pragmatic mutation routes (one launch and
    exact-owned termination); there is no scheduler, service, or watchdog.
    """

    def __init__(
        self,
        *,
        context: ssl.SSLContext | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._context = context or ssl.create_default_context()
        self._clock = clock
        self._observer = LambdaHttpsL2MObserverTransport(
            ssl_context=self._context,
            clock_ns=time.monotonic_ns,
        )

    def send(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        credential: bytearray,
    ) -> ProviderResponse:
        if method not in {"GET", "POST"} or path not in ALLOWED_PATHS:
            raise T09ProviderError("provider route escaped the exact allowlist")
        if method == "GET" and body is not None:
            raise T09ProviderError("GET request unexpectedly has a body")
        if method == "POST" and (body is None or len(body) > MAX_REQUEST_BYTES):
            raise T09ProviderError("POST request body is absent or oversized")
        if not 16 <= len(credential) <= 4_096 or any(
            marker in credential for marker in (b"\r", b"\n", b"\0")
        ):
            raise T09ProviderError("Lambda credential is malformed")
        if method == "GET":
            operations = {
                "/api/v1/instance-types": ObserverOperation.LIST_INSTANCE_TYPES,
                "/api/v1/images": ObserverOperation.LIST_IMAGES,
                "/api/v1/ssh-keys": ObserverOperation.LIST_SSH_KEYS,
                "/api/v1/firewall-rulesets": ObserverOperation.LIST_RULESETS,
                "/api/v1/firewall-rulesets/global": ObserverOperation.GET_GLOBAL_FIREWALL,
                "/api/v1/instances": ObserverOperation.LIST_INSTANCES,
            }
            operation = operations.get(path)
            if operation is None:
                raise T09ProviderError("T09 GET escaped the existing observer surface")
            try:
                observed = self._observer.send(
                    observer_request(operation),
                    credential=credential.decode("ascii", "strict"),
                    timeout_seconds=REQUEST_TIMEOUT_SECONDS,
                    absolute_deadline_monotonic_ns=(
                        time.monotonic_ns() + int(REQUEST_TIMEOUT_SECONDS * 1_000_000_000)
                    ),
                    max_response_bytes=MAX_RESPONSE_BYTES_PER_GET,
                )
            except ObserverTransportFailure as exc:
                raise T09ProviderError(
                    f"existing T07 observer GET failed closed at {exc.stage}"
                ) from None
            return ProviderResponse(
                observed.status,
                observed.content_type,
                observed.body,
                self._clock(),
            )
        connection = http.client.HTTPSConnection(
            API_HOST,
            API_PORT,
            timeout=REQUEST_TIMEOUT_SECONDS,
            context=self._context,
        )
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + credential.decode("ascii", "strict"),
            "User-Agent": "giclab-t09-pragmatic-provider-v1/1",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].casefold()
            if 300 <= response.status <= 399:
                raise T09ProviderError("provider redirect is forbidden")
            if content_type != "application/json":
                raise T09ProviderError("provider response is not JSON")
            chunks = bytearray()
            while chunk := response.read(65_536):
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE_BYTES:
                    raise T09ProviderError("provider response exceeds its byte cap")
            return ProviderResponse(
                response.status,
                content_type,
                bytes(chunks),
                self._clock(),
            )
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise T09ProviderError("provider transport outcome is unavailable") from exc
        finally:
            with contextlib.suppress(OSError):
                connection.close()


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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_exclusive(path: Path, value: object, *, mode: int = 0o600) -> None:
    encoded = _canonical_bytes(value)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError("short write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def write_bytes_exclusive(path: Path, value: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(value):
            written = os.write(descriptor, value[offset:])
            if written <= 0:
                raise OSError("short write")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def launch_capability_path(
    launch_slot: int,
    *,
    contract: T09ProviderContract,
) -> Path:
    """Return one fixed capability path for each authorized launch slot."""

    if launch_slot not in range(1, contract.max_launch_count + 1):
        raise T09ProviderError("campaign launch slot is outside the authorized bound")

    return (
        Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
        / ".gic-lab-t09-private"
        / (f"{contract.plan_id}-{contract.host_run_id}-launch-slot-{launch_slot:02d}-consumed.json")
    )


def _assert_launch_capability_unused(path: Path) -> None:
    if not path.is_absolute():
        raise T09ProviderError("campaign launch capability path is not absolute")
    if os.path.lexists(path):
        raise T09ProviderError(
            "the selected campaign launch capability is already consumed; only cleanup is permitted"
        )


def _consume_launch_capability(
    path: Path,
    *,
    contract: T09ProviderContract,
    authorization_ledger: Path,
    authorization: Mapping[str, object],
    package_commit: str,
    plan_sha256: str,
    private_root: Path,
    launch_slot: int,
    replacement_eligibility_sha256: str | None,
    clock: Callable[[], float],
) -> None:
    """Atomically and durably burn exactly one authorized launch slot."""

    if launch_slot not in range(1, contract.max_launch_count + 1) or (
        (launch_slot == 1 and replacement_eligibility_sha256 is not None)
        or (
            launch_slot > 1
            and (
                replacement_eligibility_sha256 is None
                or _HEX64.fullmatch(replacement_eligibility_sha256) is None
            )
        )
    ):
        raise T09ProviderError("campaign launch-slot eligibility binding is invalid")

    parent = path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = parent.stat(follow_symlinks=False)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise T09ProviderError("campaign launch capability directory is unsafe")
    try:
        write_exclusive(
            path,
            {
                "schema_version": "0.1.0",
                "plan_id": contract.plan_id,
                "host_run_id": contract.host_run_id,
                "package_commit": package_commit,
                "plan_sha256": plan_sha256,
                "authorization_source_sha256": authorization["authorization_source_sha256"],
                "authorization_reference": authorization["authorization_reference"],
                "authorization_ledger_sha256": file_sha256(authorization_ledger),
                "launch_body_sha256": _sha256_bytes(
                    _canonical_bytes(_launch_body(contract=contract))
                ),
                "private_root_identity_sha256": _sha256_bytes(
                    str(private_root.resolve(strict=True)).encode()
                ),
                "launch_slot": launch_slot,
                "launch_capability_limit": contract.max_launch_count,
                "launch_capability_state": "consumed-cleanup-only-after-this-point",
                "replacement_eligibility_sha256": replacement_eligibility_sha256,
                "further_launch_forbidden": launch_slot == contract.max_launch_count,
                "consumed_at_epoch": clock(),
            },
        )
    except FileExistsError:
        raise T09ProviderError(
            "the plan/package authorization launch capability was concurrently consumed; "
            "only cleanup is permitted"
        ) from None


def _append_jsonl(path: Path, value: object) -> None:
    encoded = _canonical_bytes(value)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        if os.write(descriptor, encoded) != len(encoded):
            raise OSError("short append")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _load_json(path: Path, *, maximum_bytes: int = MAX_RESPONSE_BYTES) -> dict[str, object]:
    metadata = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or not 0 < metadata.st_size <= maximum_bytes
    ):
        raise T09ProviderError(f"unsafe JSON evidence: {path.name}")
    try:
        value: object = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise T09ProviderError(f"malformed JSON evidence: {path.name}") from exc
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise T09ProviderError(f"JSON evidence is not an object: {path.name}")
    return cast(dict[str, object], value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise T09ProviderError(f"{label} is not an object")
    return cast(dict[str, object], value)


def _list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise T09ProviderError(f"{label} is not a list")
    return value


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise T09ProviderError(f"{label} is not a string")
    return value


def _integer(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise T09ProviderError(f"{label} is not an integer")
    return value


def _number(value: object, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise T09ProviderError(f"{label} is not numeric")
    return float(value)


def _envelope(document: Mapping[str, object], *, label: str) -> object:
    if set(document) != {"data"}:
        raise T09ProviderError(f"{label} provider envelope drifted")
    return document["data"]


def _reject_pagination(document: Mapping[str, object], *, label: str) -> None:
    if any(key.casefold() in {"next", "next_page", "cursor", "pagination"} for key in document):
        raise T09ProviderError(f"{label} pagination is unsupported")


def _instance_identity_sha256(instance_id: str) -> str:
    if _SAFE_ID.fullmatch(instance_id) is None:
        raise T09ProviderError("provider instance identity is unsafe")
    return hashlib.sha256(b"giclab-t09-owned-instance-v1\0" + instance_id.encode()).hexdigest()


def _instance_set_identity_sha256(instance_ids: list[str]) -> str:
    if not instance_ids or len(instance_ids) != len(set(instance_ids)):
        raise T09ProviderError("provider instance identity set is empty or duplicated")
    identities = sorted(_instance_identity_sha256(instance_id) for instance_id in instance_ids)
    return _sha256_bytes(_canonical_bytes(identities))


def _network_identity_sha256(value: str) -> str:
    return hashlib.sha256(b"giclab-t09-source-cidr-v1\0" + value.encode()).hexdigest()


def _project_firewall_rule(value: object) -> dict[str, object]:
    rule = _mapping(value, label="provider firewall rule")
    source = _string(rule.get("source_network"), label="provider firewall source")
    return {
        "protocol": rule.get("protocol"),
        "port_range": rule.get("port_range"),
        "source_network_identity_sha256": _network_identity_sha256(source),
    }


def _project_instance(value: object) -> dict[str, object]:
    row = _mapping(value, label="provider instance")
    instance_id = _string(row.get("id"), label="provider instance ID")
    file_systems = row.get("file_system_names", [])
    return {
        "instance_identity_sha256": _instance_identity_sha256(instance_id),
        "name": row.get("name"),
        "status": row.get("status"),
        "instance_type": _instance_type_name(row),
        "region": _region_name(row),
        "persistent_filesystem_count": len(
            _list(file_systems, label="provider instance filesystems")
        ),
        "access_target_present": isinstance(row.get("ip"), str) and bool(row.get("ip")),
    }


def _project_provider_response(operation: str, body: bytes) -> bytes:
    """Retain a source-verifiable projection without access or account values."""

    try:
        document = _mapping(json.loads(body), label=f"{operation} response")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T09ProviderError(f"{operation} response is not JSON") from exc
    _reject_pagination(document, label=operation)
    data = _envelope(document, label=operation)
    if operation == "instance-types":
        offers = _mapping(data, label="instance types")
        offer = _mapping(offers.get(INSTANCE_TYPE), label="selected A10 offer")
        identity = _mapping(offer.get("instance_type"), label="selected A10 identity")
        regions = [
            _mapping(item, label="selected A10 capacity region")
            for item in _list(
                offer.get("regions_with_capacity_available"),
                label="selected A10 capacity regions",
            )
        ]
        projected: object = {
            INSTANCE_TYPE: {
                "instance_type": {
                    "name": identity.get("name"),
                    "price_cents_per_hour": identity.get("price_cents_per_hour"),
                },
                "regions_with_capacity_available": [
                    {"name": region.get("name")} for region in regions
                ],
            }
        }
    elif operation == "images":
        projected = [
            {
                "id": image.get("id"),
                "region": {"name": _region_name(image)},
                "family": image.get("family"),
            }
            for item in _list(data, label="provider images")
            if (image := _mapping(item, label="provider image")).get("id") == IMAGE_ID
        ]
    elif operation in {"prelaunch-instances", "active-instances", "termination-instances"}:
        projected = [
            _project_instance(item) for item in _list(data, label=f"{operation} instances")
        ]
    elif operation == "launch":
        launch = _mapping(data, label="launch response data")
        ids = [
            _string(item, label="launch response instance ID")
            for item in _list(launch.get("instance_ids"), label="launch response IDs")
        ]
        projected = {"instance_identity_sha256s": [_instance_identity_sha256(item) for item in ids]}
    elif operation == "terminate":
        termination = _mapping(data, label="termination response data")
        ids = [
            _string(_mapping(item, label="terminated instance").get("id"), label="terminated ID")
            for item in _list(termination.get("terminated_instances"), label="terminated instances")
        ]
        projected = {"instance_identity_sha256s": [_instance_identity_sha256(item) for item in ids]}
    elif operation in {"global-firewall", "post-global-firewall"}:
        firewall = _mapping(data, label="global firewall response data")
        projected = {
            "name": firewall.get("name"),
            "rules": [
                _project_firewall_rule(item)
                for item in _list(firewall.get("rules"), label="global firewall rules")
            ],
        }
    elif operation in {"regional-rulesets", "post-regional-rulesets"}:
        projected = {
            "ruleset_semantic_sha256s": sorted(
                _sha256_bytes(_canonical_bytes(_mapping(item, label="provider ruleset")))
                for item in _list(data, label="provider rulesets")
            )
        }
    elif operation == "ssh-keys":
        projected = [
            {
                "name": _mapping(item, label="provider SSH key").get("name"),
                "public_key": _mapping(item, label="provider SSH key").get("public_key"),
            }
            for item in _list(data, label="provider SSH keys")
            if _mapping(item, label="provider SSH key").get("name") == SSH_KEY_NAME
        ]
    else:
        raise T09ProviderError(f"unsupported provider projection operation: {operation}")
    return _canonical_bytes({"data": projected})


def load_campaign_lifecycle(
    repository: Path,
    *,
    contract: T09ProviderContract,
) -> CampaignLifecycle:
    """Load lifecycle limits from the explicitly selected frozen profile."""

    try:
        profile = _mapping(load_provider_profile(repository, contract), label="pilot plan")
    except (OSError, T09ProviderContractError) as exc:
        raise T09ProviderError("provider lifecycle profile identity drifted") from exc
    raw = _mapping(profile.get("provider_lifecycle"), label="provider lifecycle")

    if contract.version in {"V3", "V4", "V5"}:
        observer_limits = ObserverLifecycleLimits.t09_pragmatic_v3()
        if (
            raw.get("campaign_provider_wall_seconds")
            != observer_limits.campaign_provider_wall_seconds
            or raw.get("normal_cleanup_reserve_seconds") != observer_limits.cleanup_reserve_seconds
            or raw.get("provider_termination_cutoff_seconds")
            != observer_limits.normal_termination_cutoff_seconds
            or raw.get("max_lambda_instances") != 1
            or raw.get("max_launch_count") != contract.max_launch_count
            or raw.get("persistent_filesystems") != 0
        ):
            raise T09ProviderError("historical pragmatic provider lifecycle drifted")
        return CampaignLifecycle(
            contract=contract,
            limits=observer_limits,
            max_instances=1,
            max_launches=contract.max_launch_count,
            persistent_filesystems=0,
        )

    if contract.version in {"V6", "V7"}:
        retry_limits = Retry4LifecycleLimits(
            preflight_wall_seconds=_integer(raw["preflight_wall_seconds"], label="preflight wall"),
            failed_preflight_termination_dispatch_seconds=_integer(
                raw["failed_preflight_termination_dispatch_seconds"],
                label="failed preflight termination dispatch",
            ),
            empirical_campaign_wall_seconds=_integer(
                raw["empirical_campaign_wall_seconds"], label="empirical wall"
            ),
            evidence_export_reserve_seconds=_integer(
                raw.get("evidence_export_reserve_seconds", 600),
                label="evidence export reserve",
            ),
            provider_termination_handoff_seconds=_integer(
                raw.get("provider_termination_handoff_seconds", 60),
                label="termination handoff",
            ),
            empirical_cleanup_reserve_seconds=_integer(
                raw["empirical_cleanup_reserve_seconds"], label="cleanup reserve"
            ),
            empirical_termination_cutoff_seconds=_integer(
                raw["empirical_termination_cutoff_seconds"], label="termination cutoff"
            ),
            maximum_successful_host_active_seconds=_integer(
                raw["maximum_successful_host_active_seconds"],
                label="successful host active cap",
            ),
            maximum_cumulative_active_seconds=_integer(
                raw["maximum_cumulative_active_seconds"], label="cumulative active cap"
            ),
            maximum_provider_cost_cents=int(
                _number(raw.get("maximum_provider_cost_usd", 8.0), label="provider cost cap") * 100
            ),
            maximum_launches=_integer(raw["max_launch_count"], label="launch cap"),
            maximum_simultaneous_instances=_integer(
                raw["max_lambda_instances"], label="instance cap"
            ),
            persistent_filesystems=_integer(raw["persistent_filesystems"], label="filesystem cap"),
        )
        return CampaignLifecycle(
            contract=contract,
            limits=retry_limits,
            max_instances=retry_limits.maximum_simultaneous_instances,
            max_launches=retry_limits.maximum_launches,
            persistent_filesystems=retry_limits.persistent_filesystems,
        )

    if contract.version not in {"V8", "V9", "V10", "V11", "V12"}:
        raise T09ProviderError("provider lifecycle contract is unsupported")
    lifecycle_fields = {
        "cumulative_accounting_origin",
        "preflight_clock_origin",
        "preflight_iteration_wall_seconds",
        "maximum_preflight_instance_active_seconds",
        "maximum_cumulative_preflight_active_seconds",
        "maximum_preflight_provider_cost_usd",
        "max_preflight_launch_count",
        "failed_preflight_termination_dispatch_seconds",
        "empirical_clock_origin",
        "empirical_campaign_wall_seconds",
        "evidence_export_reserve_seconds",
        "provider_termination_handoff_seconds",
        "empirical_cleanup_reserve_seconds",
        "empirical_termination_cutoff_seconds",
        "maximum_empirical_provider_cost_usd",
        "max_empirical_launch_count",
        "max_lambda_instances",
        "persistent_filesystems",
        "replacement_launch_rule",
        "admission_rule",
        "supervised_release_wait_seconds",
        "supervised_release_rule",
        "control_plane",
    }
    if contract.version == "V12":
        lifecycle_fields.update(
            {
                "immutable_model_unavailable_disposition",
                "model_metadata_request_count_total",
                "model_metadata_request_location",
                "provider_launch_model_metadata_request_count",
                "host_runtime_model_metadata_request_count",
                "model_metadata_prelaunch_freshness_seconds",
                "model_metadata_freshness_owner",
                "provider_launch_requires_current_freshness",
                "host_runtime_requires_current_freshness",
                "host_runtime_requires_prelaunch_timestamp_ordering",
                "model_metadata_receipt_required",
                "model_metadata_receipt_replay_allowed",
            }
        )
    if set(raw) != lifecycle_fields:
        raise T09ProviderError("provider lifecycle plan surface drifted")
    if (
        raw.get("cumulative_accounting_origin") != "actual-active-lambda-seconds"
        or raw.get("preflight_clock_origin") != "provider-launch-send-started"
        or raw.get("empirical_clock_origin") != "after-durable-frozen-run-manifest-publication"
        or raw.get("supervised_release_wait_seconds") != 300
        or raw.get("supervised_release_rule")
        != (
            "the credential-free started entrypoint may wait up to 300 seconds for the final "
            "source-bound state, budget, core, exact-secret, and owned-container checks; the "
            "5160-second admission gate is rerun immediately before durable release and any "
            "timeout consumes the started identity as infrastructure-invalid"
        )
        or raw.get("replacement_launch_rule")
        != {
            "allowed_only_before_empirical_entry": True,
            "prior_instance_terminal_and_absent_required": True,
            "prior_host_empirical_attempts_required": 0,
            "prior_host_model_requests_required": 0,
            "prior_host_browser_actions_required": 0,
            "ownership_outcome_unknown_forbidden": True,
            "cumulative_lambda_cap_required": True,
        }
    ):
        raise T09ProviderError("provider clock or replacement-launch contract drifted")
    if contract.version == "V12" and (
        raw.get("immutable_model_unavailable_disposition")
        != "stop-before-lambda-launch-zero-lambda-cost"
        or raw.get("model_metadata_request_count_total") != 1
        or raw.get("model_metadata_request_location") != "local-control-plane-before-lambda-launch"
        or raw.get("provider_launch_model_metadata_request_count") != 0
        or raw.get("host_runtime_model_metadata_request_count") != 0
        or raw.get("model_metadata_prelaunch_freshness_seconds")
        != MODEL_METADATA_PRELAUNCH_FRESHNESS_SECONDS
        or raw.get("model_metadata_freshness_owner") != "provider-final-transport-boundary"
        or raw.get("provider_launch_requires_current_freshness") is not True
        or raw.get("host_runtime_requires_current_freshness") is not False
        or raw.get("host_runtime_requires_prelaunch_timestamp_ordering") is not True
        or raw.get("model_metadata_receipt_required") is not True
        or raw.get("model_metadata_receipt_replay_allowed") is not False
    ):
        raise T09ProviderError("V12 model metadata freshness ownership drifted")
    autonomous_limits = AutonomousPilotLifecycleLimits(
        preflight_iteration_wall_seconds=_integer(
            raw["preflight_iteration_wall_seconds"], label="preflight iteration wall"
        ),
        maximum_preflight_instance_active_seconds=_integer(
            raw["maximum_preflight_instance_active_seconds"],
            label="preflight instance active cap",
        ),
        maximum_cumulative_preflight_active_seconds=_integer(
            raw["maximum_cumulative_preflight_active_seconds"],
            label="cumulative preflight active cap",
        ),
        maximum_preflight_provider_cost_cents=int(
            _number(
                raw["maximum_preflight_provider_cost_usd"],
                label="preflight provider cost cap",
            )
            * 100
        ),
        maximum_preflight_launches=_integer(
            raw["max_preflight_launch_count"], label="preflight launch cap"
        ),
        empirical_campaign_wall_seconds=_integer(
            raw["empirical_campaign_wall_seconds"], label="empirical wall"
        ),
        empirical_cleanup_reserve_seconds=_integer(
            raw["empirical_cleanup_reserve_seconds"], label="cleanup reserve"
        ),
        empirical_termination_cutoff_seconds=_integer(
            raw["empirical_termination_cutoff_seconds"], label="termination cutoff"
        ),
        maximum_empirical_provider_cost_cents=int(
            _number(
                raw["maximum_empirical_provider_cost_usd"],
                label="empirical provider cost cap",
            )
            * 100
        ),
        maximum_empirical_launches=_integer(
            raw["max_empirical_launch_count"], label="empirical launch cap"
        ),
        maximum_simultaneous_instances=_integer(raw["max_lambda_instances"], label="instance cap"),
        persistent_filesystems=_integer(raw["persistent_filesystems"], label="filesystem cap"),
    )
    return CampaignLifecycle(
        contract=contract,
        limits=autonomous_limits,
        max_instances=_integer(raw["max_lambda_instances"], label="instance cap"),
        max_launches=_integer(raw["max_preflight_launch_count"], label="launch cap"),
        persistent_filesystems=_integer(raw["persistent_filesystems"], label="filesystem cap"),
    )


def _verify_clean_package(repository: Path, package_commit: str) -> None:
    if _HEX40.fullmatch(package_commit) is None:
        raise T09ProviderError("package commit is malformed")
    environment = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    try:
        head = (
            subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=True,
                timeout=10,
            )
            .stdout.decode("ascii", "strict")
            .strip()
        )
        dirty = subprocess.run(
            ["git", "-C", str(repository), "status", "--porcelain=v1"],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
        raise T09ProviderError("clean package identity could not be verified") from exc
    if head != package_commit or dirty:
        raise T09ProviderError("provider mutation requires the exact clean package commit")


def _git_commit_tree(repository: Path, commit: str) -> str:
    if _HEX40.fullmatch(commit) is None:
        raise T09ProviderError("package commit is malformed")
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", f"{commit}^{{tree}}"],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise T09ProviderError("package tree identity is unavailable")
    tree = result.stdout.decode("ascii", "strict").strip()
    if _HEX40.fullmatch(tree) is None:
        raise T09ProviderError("package tree identity is malformed")
    return tree


def validate_authorization_ledger(
    path: Path,
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
) -> dict[str, object]:
    if contract.version == "V12":
        try:
            package_tree = _git_commit_tree(repository, package_commit)
            overlay = validate_model_metadata_authorization_overlay(
                path,
                contract=contract,
                package_commit=package_commit,
                package_tree=package_tree,
                plan_sha256=file_sha256(repository / contract.provider_profile_path),
                require_receipt_binding=True,
            )
            return {
                **overlay,
                "authorization_ledger_sha256": file_sha256(path),
            }
        except (ModelMetadataReceiptError, OSError, subprocess.SubprocessError) as exc:
            raise T09ProviderError("V12 authorization overlay is invalid") from exc
    if contract.version != "V11":
        raise T09ProviderError(
            "frozen historical provider authority is inspectable but cannot be replayed"
        )
    metadata = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise T09ProviderError("private authorization ledger metadata is unsafe")
    value = _load_json(path, maximum_bytes=65_536)
    authorized_package_commit = value.get("clean_package_commit")
    if (
        not isinstance(authorized_package_commit, str)
        or _HEX40.fullmatch(authorized_package_commit) is None
    ):
        raise T09ProviderError("private authorization ledger package identity is malformed")
    if authorized_package_commit != package_commit:
        autonomous_preflight_package_transition(
            repository,
            contract=contract,
            from_package_commit=authorized_package_commit,
            to_package_commit=package_commit,
        )
    plan_relative_path = contract.provider_profile_path
    authorized_plan_sha256 = (
        file_sha256(repository / plan_relative_path)
        if authorized_package_commit == package_commit
        else hashlib.sha256(
            _git_blob(repository, authorized_package_commit, plan_relative_path)
        ).hexdigest()
    )
    authorization_source_sha256 = value.get("authorization_source_sha256")
    authorization_reference = value.get("authorization_reference")
    if not isinstance(authorization_source_sha256, str) or not isinstance(
        authorization_reference, str
    ):
        raise T09ProviderError("V11 authorization identity is malformed or not fresh")
    try:
        contract.validate_authority(authorization_reference, authorization_source_sha256)
    except T09ProviderContractError as exc:
        raise T09ProviderError("V11 authorization identity is malformed or not fresh") from exc
    required = {
        "schema_version": "0.1.0",
        "authorization_source_sha256": authorization_source_sha256,
        "authorization_reference": authorization_reference,
        "authorized": True,
        "single_use": True,
        "clean_package_commit": authorized_package_commit,
        "plan_id": contract.plan_id,
        "plan_sha256": authorized_plan_sha256,
        "max_lambda_instances": 1,
        "max_preflight_launch_count": 8,
        "max_empirical_launch_count": 1,
        "maximum_preflight_instance_active_seconds": 21_600,
        "maximum_cumulative_preflight_active_seconds": 43_200,
        "persistent_filesystems": 0,
        "preflight_lambda_cost_cap_usd": 10.0,
        "lambda_cost_cap_usd": 8.0,
        "openai_cost_cap_usd": 40.0,
        "aggregate_cost_cap_usd": 58.0,
        "prior_t09_cost_usd": contract.prior_t09_cost_usd,
        "cumulative_t09_cost_cap_usd": 90.0,
        "replacement_image_policy": "retained-exact-load-or-one-fallback-build-v1",
        "artifact_destination": ("/Volumes/Macintosh HD - Data/GIC-Lab/t09/v11"),
    }
    if value != required:
        raise T09ProviderError("private authorization ledger drifted")
    return value


def validate_cleanup_authority_ledger(
    path: Path,
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
) -> dict[str, object]:
    """Validate frozen authority for exact-resource cleanup, never for launch.

    Historical launch authority is not replayable, but its exact provider owner
    remains the authority for terminating or verifying absence of that retained
    resource.  This narrower validator intentionally omits all launch admission.
    """

    if contract.version in {"V11", "V12"}:
        return validate_authorization_ledger(
            path,
            contract=contract,
            repository=repository,
            package_commit=package_commit,
        )
    metadata = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise T09ProviderError("historical cleanup authority metadata is unsafe")
    value = _load_json(path, maximum_bytes=65_536)
    authorization_reference = value.get("authorization_reference")
    authorization_source_sha256 = value.get("authorization_source_sha256")
    if not isinstance(authorization_reference, str) or not isinstance(
        authorization_source_sha256, str
    ):
        raise T09ProviderError("historical cleanup authority identity is malformed")
    try:
        contract.validate_authority(authorization_reference, authorization_source_sha256)
    except T09ProviderContractError as exc:
        raise T09ProviderError("historical cleanup authority crosses versions") from exc
    if (
        value.get("authorized") is not True
        or value.get("single_use") is not True
        or value.get("clean_package_commit") != package_commit
        or value.get("plan_id") != contract.plan_id
        or value.get("plan_sha256")
        != file_sha256(repository.resolve(strict=True) / contract.provider_profile_path)
        or value.get("max_lambda_instances") != 1
        or value.get("persistent_filesystems") != 0
    ):
        raise T09ProviderError("historical cleanup authority binding drifted")
    return value


def load_dotenv_assignment(path: Path, name: str) -> bytearray:
    if name != "LAMBDA_API_KEY" or not path.is_absolute():
        raise T09ProviderError("Lambda dotenv binding is invalid")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or metadata.st_mode & 0o022
            or not 0 < metadata.st_size <= MAX_DOTENV_BYTES
        ):
            raise T09ProviderError("dotenv metadata is unsafe")
        raw = os.read(descriptor, MAX_DOTENV_BYTES + 1)
        after = os.fstat(descriptor)
        if len(raw) != metadata.st_size or (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
        ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise T09ProviderError("dotenv changed while held")
    finally:
        os.close(descriptor)
    selected: bytearray | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(b"#"):
            continue
        if b"=" not in stripped:
            raise T09ProviderError("dotenv syntax is unsupported")
        raw_name, raw_value = stripped.split(b"=", 1)
        if raw_name == name.encode():
            if selected is not None or _DOTENV_VALUE.fullmatch(raw_value) is None:
                raise T09ProviderError("Lambda dotenv assignment is ambiguous")
            selected = bytearray(raw_value)
    if selected is None:
        raise T09ProviderError("Lambda dotenv assignment is missing")
    return selected


def model_metadata_preflight(
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
    authorization_overlay: Path,
    openai_dotenv: Path,
    output: Path,
    transport: ModelMetadataTransport | None = None,
    clock: Callable[[], float] = time.time,
) -> Path:
    """Run the sole V12 model GET and hand its sealed receipt to later planes."""

    if contract is not V12_PROVIDER_CONTRACT:
        raise T09ProviderError("model metadata preflight requires the V12 provider contract")
    repository = repository.resolve(strict=True)
    _verify_clean_package(repository, package_commit)
    package_tree = _git_commit_tree(repository, package_commit)
    plan_sha256 = file_sha256(repository / contract.provider_profile_path)
    try:
        overlay = validate_model_metadata_authorization_overlay(
            authorization_overlay,
            contract=contract,
            package_commit=package_commit,
            package_tree=package_tree,
            plan_sha256=plan_sha256,
        )
        receipt = create_model_metadata_receipt(
            repository_commit=package_commit,
            repository_tree=package_tree,
            plan_id=contract.plan_id,
            plan_sha256=plan_sha256,
            provider_contract_version=contract.version,
            host_run_id=contract.host_run_id,
            authorization_reference=cast(str, overlay["authorization_reference"]),
            authorization_source_sha256=cast(str, overlay["authorization_source_sha256"]),
            authorization_overlay_sha256=model_metadata_authorization_overlay_sha256(
                authorization_overlay
            ),
            public_price_contract_sha256=cast(str, overlay["public_price_contract_sha256"]),
            public_deprecation_observation_sha256=cast(
                str, overlay["public_deprecation_observation_sha256"]
            ),
            output=output,
            dotenv=openai_dotenv,
            authorization_overlay=authorization_overlay,
            transport=transport,
            clock=clock,
        )
        bind_model_metadata_receipt_to_authorization_overlay(
            authorization_overlay,
            receipt_sha256=model_metadata_receipt_sha256(receipt),
        )
        return receipt
    except ModelMetadataReceiptError as exc:
        raise T09ProviderError("V12 model metadata receipt was not sealed") from exc


def _destroy_bytearray(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0
    value.clear()


def _destroy_operational_file(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise T09ProviderError("private operational state is unsafe")
        remaining = metadata.st_size
        os.lseek(descriptor, 0, os.SEEK_SET)
        zeros = b"\0" * min(max(remaining, 1), 65_536)
        while remaining:
            written = os.write(descriptor, zeros[: min(remaining, len(zeros))])
            if written <= 0:
                raise T09ProviderError("private operational state destruction failed")
            remaining -= written
        os.ftruncate(descriptor, 0)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    path.unlink()
    _fsync_parent(path)


@dataclass(slots=True)
class PreparedProviderRequest:
    """A fully encoded request whose local preparation is already complete."""

    ordinal: int
    operation: str
    method: str
    path: str
    body: bytes | None = field(repr=False)
    target_identity_sha256: str | None
    intent_without_timestamp: Mapping[str, object]


@dataclass(slots=True)
class RequestRecorder:
    root: Path
    transport: ProviderTransport
    credential: bytearray = field(repr=False)
    clock: Callable[[], float] = time.time
    next_ordinal: int = 1

    def prepare(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
        target_identity_sha256: str | None = None,
    ) -> PreparedProviderRequest:
        if path not in ALLOWED_PATHS or method not in {"GET", "POST"}:
            raise T09ProviderError("recorded request escaped the allowlist")
        ordinal = self.next_ordinal
        self.next_ordinal += 1
        encoded = None if body is None else _canonical_bytes(body)
        intent_without_timestamp: dict[str, object] = {
            "schema_version": "0.1.0",
            "ordinal": ordinal,
            "operation": operation,
            "method": method,
            "host": API_HOST,
            "port": API_PORT,
            "path": path,
            "request_body_sha256": None if encoded is None else _sha256_bytes(encoded),
            "automatic_retry": False,
            "target_identity_sha256": target_identity_sha256,
        }
        if (operation == "terminate") != (
            isinstance(target_identity_sha256, str)
            and _HEX64.fullmatch(target_identity_sha256) is not None
        ):
            raise T09ProviderError("provider target identity binding drifted")
        return PreparedProviderRequest(
            ordinal=ordinal,
            operation=operation,
            method=method,
            path=path,
            body=encoded,
            target_identity_sha256=target_identity_sha256,
            intent_without_timestamp=intent_without_timestamp,
        )

    def request(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
        target_identity_sha256: str | None = None,
    ) -> ProviderResponse:
        prepared = self.prepare(
            operation,
            method,
            path,
            body=body,
            target_identity_sha256=target_identity_sha256,
        )
        return self.send_prepared(prepared)

    def send_prepared(
        self,
        prepared: PreparedProviderRequest,
        *,
        final_admission: Callable[[], float] | None = None,
    ) -> ProviderResponse:
        """Send one prepared request.

        Ordinary historical requests retain their pre-send journal behavior.
        A V12 launch supplies final_admission: after that callback returns, the
        very next effect is transport.send. Its send-started journal is written
        retrospectively after the attempt because Phase A already fsynced the
        nonreplayable send intent.
        """

        retrospective_journal = final_admission is not None
        if final_admission is None:
            send_started_at_epoch = self.clock()
            intent = {
                **prepared.intent_without_timestamp,
                "send_started_at_epoch": send_started_at_epoch,
            }
            _append_jsonl(
                self.root / "request-journal.jsonl",
                {**intent, "event": "send-started"},
            )
        else:
            # Final admission re-reads the receipt and samples the fresh clock.
            # Do not insert any write, subprocess, sleep, or other blocking
            # local mutation between this return and the transport call.
            send_started_at_epoch = final_admission()
            try:
                response = self.transport.send(
                    prepared.method,
                    prepared.path,
                    body=prepared.body,
                    credential=self.credential,
                )
            except BaseException:
                intent = {
                    **prepared.intent_without_timestamp,
                    "send_started_at_epoch": send_started_at_epoch,
                }
                _append_jsonl(
                    self.root / "request-journal.jsonl",
                    {**intent, "event": "send-started"},
                )
                _append_jsonl(
                    self.root / "request-journal.jsonl",
                    {
                        **intent,
                        "event": "response-unknown",
                        "outcome_observed_at_epoch": self.clock(),
                    },
                )
                raise ProviderOutcomeUnknown(prepared.operation) from None
            intent = {
                **prepared.intent_without_timestamp,
                "send_started_at_epoch": send_started_at_epoch,
            }
            _append_jsonl(
                self.root / "request-journal.jsonl",
                {**intent, "event": "send-started"},
            )
        if not retrospective_journal:
            try:
                response = self.transport.send(
                    prepared.method,
                    prepared.path,
                    body=prepared.body,
                    credential=self.credential,
                )
            except BaseException:
                _append_jsonl(
                    self.root / "request-journal.jsonl",
                    {
                        **intent,
                        "event": "response-unknown",
                        "outcome_observed_at_epoch": self.clock(),
                    },
                )
                raise ProviderOutcomeUnknown(prepared.operation) from None
        if response.status < 200 or response.status >= 300:
            _append_jsonl(
                self.root / "request-journal.jsonl",
                {
                    **intent,
                    "event": "response-rejected",
                    "http_status": response.status,
                    "response_received_at_epoch": response.received_at_epoch,
                    "response_sha256": _sha256_bytes(response.body),
                    "response_bytes": len(response.body),
                },
            )
            raise T09ProviderError(f"provider operation {prepared.operation} returned non-2xx")
        try:
            retained = _project_provider_response(prepared.operation, response.body)
        except (T09ProviderError, UnicodeDecodeError, ValueError):
            # A response that crossed send-start but cannot be interpreted is no
            # safer than a transport ambiguity.  Persist a terminal journal event
            # before returning control so a mutation can never be silently
            # repeated from an unmatched send-start record.
            _append_jsonl(
                self.root / "request-journal.jsonl",
                {
                    **intent,
                    "event": "response-unknown",
                    "http_status": response.status,
                    "response_received_at_epoch": response.received_at_epoch,
                    "raw_response_sha256": _sha256_bytes(response.body),
                    "raw_response_bytes": len(response.body),
                    "outcome_observed_at_epoch": self.clock(),
                    "classification": "untrusted-response-semantics",
                },
            )
            raise ProviderOutcomeUnknown(prepared.operation) from None
        filename = f"{prepared.ordinal:03d}-{prepared.operation}.json"
        write_bytes_exclusive(self.root / filename, retained)
        _append_jsonl(
            self.root / "request-journal.jsonl",
            {
                **intent,
                "event": "response-complete",
                "http_status": response.status,
                "content_type": response.content_type,
                "response_received_at_epoch": response.received_at_epoch,
                "response_sha256": _sha256_bytes(retained),
                "response_bytes": len(retained),
                "raw_response_sha256": _sha256_bytes(response.body),
                "raw_response_bytes": len(response.body),
                "retention_projection": "t09-provider-structural-redaction-v1",
                "response_file": filename,
            },
        )
        return response


def _journal_events(root: Path) -> list[dict[str, object]]:
    path = root / "request-journal.jsonl"
    if path.stat().st_size > 2_097_152:
        raise T09ProviderError("provider journal exceeds its cap")
    events: list[dict[str, object]] = []
    for line in path.read_bytes().splitlines():
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise T09ProviderError("provider journal is malformed") from exc
        events.append(_mapping(value, label="provider journal event"))
    return events


def _response_documents(root: Path) -> dict[str, list[tuple[dict[str, object], dict[str, object]]]]:
    events = _journal_events(root)
    if not events or len(events) % 2:
        raise T09ProviderError("provider journal has an incomplete request")
    completed: list[dict[str, object]] = []
    for index in range(0, len(events), 2):
        sent, response = events[index : index + 2]
        ordinal = index // 2 + 1
        shared = ("ordinal", "operation", "method", "host", "port", "path")
        if (
            sent.get("event") != "send-started"
            or response.get("event")
            not in {"response-complete", "response-unknown", "response-rejected"}
            or sent.get("ordinal") != ordinal
            or response.get("ordinal") != ordinal
            or any(sent.get(key) != response.get(key) for key in shared)
            or sent.get("host") != API_HOST
            or sent.get("port") != API_PORT
            or sent.get("path") not in ALLOWED_PATHS
            or sent.get("method") not in {"GET", "POST"}
            or sent.get("automatic_retry") is not False
            or response.get("automatic_retry") is not False
        ):
            raise T09ProviderError("provider journal request sequence drifted")
        if response.get("event") == "response-complete":
            completed.append(response)
    result: dict[str, list[tuple[dict[str, object], dict[str, object]]]] = {}
    for event in completed:
        filename = _string(event.get("response_file"), label="response file")
        body_path = root / filename
        if body_path.parent != root or file_sha256(body_path) != event.get("response_sha256"):
            raise T09ProviderError("provider response hash drifted from its journal")
        document = _load_json(body_path)
        _reject_pagination(document, label=str(event.get("operation")))
        result.setdefault(str(event.get("operation")), []).append((event, document))
    return result


def _instance_rows(document: Mapping[str, object], *, label: str) -> list[dict[str, object]]:
    return [
        _mapping(item, label=f"{label} instance")
        for item in _list(_envelope(document, label=label), label=f"{label} data")
    ]


def _instance_type_name(row: Mapping[str, object]) -> str:
    value = row.get("instance_type")
    if isinstance(value, str):
        return value
    return _string(_mapping(value, label="instance type").get("name"), label="instance type")


def _region_name(row: Mapping[str, object]) -> str:
    value = row.get("region")
    if isinstance(value, str):
        return value
    return _string(_mapping(value, label="instance region").get("name"), label="region")


def _validate_prelaunch_documents(
    documents: Mapping[str, list[tuple[dict[str, object], dict[str, object]]]],
    *,
    contract: T09ProviderContract,
    expected_public_key: str,
    expected_public_ipv4: str | None = None,
    expected_source_cidr_sha256: str | None = None,
) -> None:
    required_once = {
        "instance-types",
        "images",
        "ssh-keys",
        "global-firewall",
        "regional-rulesets",
        "prelaunch-instances",
        "launch",
    }
    if any(len(documents.get(name, [])) != 1 for name in required_once):
        raise T09ProviderError("provider entry request set drifted")
    types = _mapping(
        _envelope(documents["instance-types"][0][1], label="instance types"),
        label="instance types data",
    )
    offer = _mapping(types.get(INSTANCE_TYPE), label="A10 offer")
    identity = _mapping(offer.get("instance_type"), label="A10 identity")
    regions = [
        _mapping(item, label="capacity region")
        for item in _list(offer.get("regions_with_capacity_available"), label="capacity")
    ]
    if (
        identity.get("name") != INSTANCE_TYPE
        or identity.get("price_cents_per_hour") != PRICE_CENTS_PER_HOUR
        or not any(region.get("name") == REGION for region in regions)
    ):
        raise T09ProviderError("A10 capacity or price drifted")
    images = _list(
        _envelope(documents["images"][0][1], label="images"),
        label="images data",
    )
    selected_images = [
        _mapping(item, label="image")
        for item in images
        if isinstance(item, dict) and item.get("id") == IMAGE_ID and _region_name(item) == REGION
    ]
    if len(selected_images) != 1:
        raise T09ProviderError("frozen pragmatic image is unavailable in us-east-1")
    keys = _list(
        _envelope(documents["ssh-keys"][0][1], label="SSH keys"),
        label="SSH keys data",
    )
    matching_keys = [
        _mapping(item, label="SSH key")
        for item in keys
        if isinstance(item, dict) and item.get("name") == SSH_KEY_NAME
    ]
    if (
        len(matching_keys) != 1
        or _string(matching_keys[0].get("public_key"), label="provider SSH public key").strip()
        != expected_public_key.strip()
    ):
        raise T09ProviderError("provider SSH key does not match the exact local public key")
    global_firewall = _mapping(
        _envelope(documents["global-firewall"][0][1], label="global firewall"),
        label="global firewall data",
    )
    rules = _list(global_firewall.get("rules"), label="global firewall rules")
    source_cidr_sha256 = expected_source_cidr_sha256 or _network_identity_sha256(
        f"{expected_public_ipv4}/32"
    )
    exact_ssh = [
        _mapping(item, label="firewall rule")
        for item in rules
        if isinstance(item, dict)
        and item.get("protocol") == "tcp"
        and item.get("source_network_identity_sha256") == source_cidr_sha256
        and item.get("port_range") in [[22, 22], [22]]
    ]
    if len(exact_ssh) != 1:
        raise T09ProviderError("current source IPv4 lacks one exact SSH firewall rule")
    if _instance_rows(documents["prelaunch-instances"][0][1], label="prelaunch instances"):
        raise T09ProviderError("prelaunch provider inventory is not zero")
    launch = _mapping(_envelope(documents["launch"][0][1], label="launch"), label="launch data")
    if documents["launch"][0][0].get("request_body_sha256") != _sha256_bytes(
        _canonical_bytes(_launch_body(contract=contract))
    ):
        raise T09ProviderError("launch request body drifted from the exact no-filesystem body")
    instance_ids = _list(
        launch.get("instance_identity_sha256s"), label="launch instance identities"
    )
    if (
        len(instance_ids) != 1
        or not isinstance(instance_ids[0], str)
        or _HEX64.fullmatch(instance_ids[0]) is None
    ):
        raise T09ProviderError("launch did not return exactly one safe instance ID")


def _launch_body(*, contract: T09ProviderContract) -> dict[str, object]:
    return {
        "region_name": REGION,
        "instance_type_name": INSTANCE_TYPE,
        "ssh_key_names": [SSH_KEY_NAME],
        "file_system_names": [],
        "file_system_mounts": [],
        "name": contract.instance_name,
        "hostname": contract.instance_name,
        "image": {"id": IMAGE_ID},
    }


def _terminate_body(instance_id: str) -> dict[str, object]:
    if _SAFE_ID.fullmatch(instance_id) is None:
        raise T09ProviderError("owned instance identity is unsafe")
    return {"instance_ids": [instance_id]}


def _terminate_many_body(instance_ids: list[str]) -> dict[str, object]:
    _instance_set_identity_sha256(instance_ids)
    return {"instance_ids": list(instance_ids)}


def _initial_preflight_cleanup_state(
    *,
    contract: T09ProviderContract,
    entry_root: Path,
    private_root: Path,
    package_commit: str,
    plan_sha256: str,
    instance_id: str,
    launch_slot: int,
    replacement_eligibility_sha256: str | None,
    clock: Callable[[], float],
) -> dict[str, object]:
    """Create the first durable post-launch authority, independent of pilot state."""

    journal = _journal_events(entry_root)
    sends = [
        event
        for event in journal
        if event.get("event") == "send-started" and event.get("operation") == "launch"
    ]
    responses = [
        event
        for event in journal
        if event.get("event") == "response-complete" and event.get("operation") == "launch"
    ]
    if len(sends) != 1 or len(responses) != 1:
        raise T09ProviderError("initial cleanup state lacks one launch journal pair")
    owned_identity = _instance_identity_sha256(instance_id)
    baseline_identity = _sha256_bytes(
        _canonical_bytes(
            {
                "global_firewall_sha256": file_sha256(entry_root / "004-global-firewall.json"),
                "regional_rulesets_sha256": file_sha256(entry_root / "005-regional-rulesets.json"),
            }
        )
    )
    try:
        cleanup_journal = EarlyCleanupJournal.initialize(
            private_root / "preflight-cleanup-state",
            plan_id=contract.plan_id,
            host_run_id=contract.host_run_id,
            package_commit=package_commit,
            plan_sha256=plan_sha256,
            provider_instance_id=instance_id,
            provider_instance_identity_sha256=owned_identity,
            provider_started_at_epoch=_number(
                sends[0].get("send_started_at_epoch"), label="launch send start"
            ),
            launch_slot=launch_slot,
            replacement_eligibility_sha256=replacement_eligibility_sha256,
            firewall_baseline_identity_sha256=baseline_identity,
            temporary_local_secret_locator=str(private_root / "openai-secret-upload"),
            temporary_remote_secret_locator=("/home/ubuntu/.config/giclab/sira_api_key"),
            clock=clock,
        )
    except EarlyCleanupStateError as exc:
        raise T09ProviderError("initial durable cleanup authority could not be created") from exc
    return _initial_cleanup_compatibility_projection(
        cleanup_journal.load(), private_root=private_root, contract=contract
    )


def _initial_cleanup_compatibility_projection(
    state: EarlyCleanupState,
    *,
    private_root: Path,
    contract: T09ProviderContract,
) -> dict[str, object]:
    """Project the versioned authority for existing exact-owner closeout code."""

    local_upload_path = private_root / "openai-secret-upload"
    return {
        "schema_version": "1.0.0",
        "state_type": "t09-versioned-preflight-cleanup-authority-projection",
        "journal_id": state.journal_id,
        "journal_sequence": state.sequence,
        "plan_id": state.plan_id,
        "host_run_id": state.host_run_id,
        "package_commit": state.package_commit,
        "plan_sha256": state.plan_sha256,
        "private_instance_id": state.provider_instance_id,
        "owned_instance_identity_sha256": state.provider_instance_identity_sha256,
        "instance_name": contract.instance_name,
        "launch_slot": state.launch_slot,
        "replacement_eligibility_sha256": state.replacement_eligibility_sha256,
        "lambda_started_at_epoch": state.provider_started_at_epoch,
        "provider_termination_path": "/api/v1/instance-operations/terminate",
        "provider_termination_body_sha256": _sha256_bytes(
            _canonical_bytes(_terminate_body(state.provider_instance_id))
        ),
        "provider_security_baseline_sources": [
            "entry-source/004-global-firewall.json",
            "entry-source/005-regional-rulesets.json",
        ],
        "temporary_firewall_resource_ids": [],
        "temporary_ruleset_resource_ids": [],
        "temporary_local_secret_locations": [str(local_upload_path)],
        "temporary_remote_secret_locations": ["/home/ubuntu/.config/giclab/sira_api_key"],
        "planned_remote_artifact_root": contract.remote_root,
        "source_staging_started": False,
        "artifact_root_created": False,
        "credential_materialized": False,
        "container_created": False,
        "browser_started": False,
        "empirical_entry_crossed": False,
        "pilot_state_required_for_cleanup": False,
        "attempt_state_required_for_cleanup": False,
        "private_operational_state_not_for_archive": True,
        "created_at_epoch": state.created_at_epoch,
    }


def _validate_initial_preflight_cleanup_state(
    path: Path,
    *,
    contract: T09ProviderContract,
    package_commit: str,
    plan_sha256: str,
) -> dict[str, object]:
    try:
        state = EarlyCleanupJournal(path).load()
    except EarlyCleanupStateError as exc:
        raise T09ProviderError("initial preflight cleanup state drifted") from exc
    if (
        state.plan_id != contract.plan_id
        or state.host_run_id != contract.host_run_id
        or state.package_commit != package_commit
        or state.plan_sha256 != plan_sha256
        or state.provider_instance_identity_sha256
        != _instance_identity_sha256(state.provider_instance_id)
        or state.launch_slot not in range(1, contract.max_launch_count + 1)
    ):
        raise T09ProviderError("initial preflight cleanup identity drifted")
    return _initial_cleanup_compatibility_projection(
        state,
        private_root=path.parent,
        contract=contract,
    )


_REMOTE_CONTINUATION_TARGET_KINDS: Final = frozenset(
    {
        CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL,
        CleanupTargetKind.OWNED_CONTAINER,
    }
)
_PROVIDER_CLOSEOUT_TARGET_IDS: Final = (
    "provider-instance",
    "firewall-restoration",
    "temporary-local-secret",
)


def _cleanup_journal_for_closeout(
    *,
    contract: T09ProviderContract,
    private_root: Path,
    package_commit: str,
    plan_sha256: str,
    remote_cleanup_journal: Path | None,
) -> EarlyCleanupJournal:
    """Load the provider prefix and optionally append its exact remote continuation."""

    local = EarlyCleanupJournal(private_root / "preflight-cleanup-state")
    try:
        local_state = local.load()
        if remote_cleanup_journal is not None:
            remote = EarlyCleanupJournal(remote_cleanup_journal.resolve(strict=True))
            remote_state = remote.load()
            local_targets = {target.target_id: target for target in local_state.targets}
            remote_targets = {target.target_id: target for target in remote_state.targets}
            for target_id, local_target in local_targets.items():
                remote_target = remote_targets.get(target_id)
                if remote_target is None:
                    raise EarlyCleanupStateError("cleanup continuation lost a retained target")
                if (
                    local_target.kind not in _REMOTE_CONTINUATION_TARGET_KINDS
                    and remote_target != local_target
                ):
                    raise EarlyCleanupStateError(
                        "remote cleanup continuation changed provider-owned authority"
                    )
            if any(
                target_id not in local_targets
                and target.kind is not CleanupTargetKind.OWNED_CONTAINER
                for target_id, target in remote_targets.items()
            ):
                raise EarlyCleanupStateError(
                    "remote cleanup continuation added a non-container authority"
                )
            for attempt in remote_state.cleanup_attempts[len(local_state.cleanup_attempts) :]:
                target = remote_targets.get(attempt.target_id)
                if target is None or target.kind not in _REMOTE_CONTINUATION_TARGET_KINDS:
                    raise EarlyCleanupStateError(
                        "remote cleanup continuation acted on provider-owned authority"
                    )
            local.import_continuation(remote)
        state = local.load()
    except (OSError, EarlyCleanupStateError) as exc:
        raise T09ProviderError("durable cleanup continuation is invalid") from exc
    if (
        state.plan_id != contract.plan_id
        or state.host_run_id != contract.host_run_id
        or state.package_commit != package_commit
        or state.plan_sha256 != plan_sha256
        or state.provider_instance_identity_sha256
        != _instance_identity_sha256(state.provider_instance_id)
    ):
        raise T09ProviderError("durable cleanup continuation changed exact ownership")
    return local


def _write_provider_cleanup_receipt(
    cleanup_journal: EarlyCleanupJournal,
    *,
    private_root: Path,
) -> Path:
    state = cleanup_journal.load()
    return cleanup_journal.write_basic_closeout_receipt(
        private_root / f"EARLY_CLEANUP_CLOSEOUT-{state.sequence:08d}.json"
    )


def _record_provider_closeout_cleanup(
    cleanup_journal: EarlyCleanupJournal,
    *,
    private_root: Path,
    closeout_receipt: Mapping[str, object],
    clock: Callable[[], float],
) -> Path:
    """Persist provider, firewall, and local-secret closeout on the shared chain."""

    if (
        closeout_receipt.get("terminal_or_absent") is not True
        or closeout_receipt.get("security_restored") is not True
    ):
        raise T09ProviderError("provider closeout is not terminal with restored security")
    cleanup_journal.record_result(
        target_id="provider-instance",
        result=(
            CleanupTargetState.ABSENT
            if closeout_receipt.get("zero_t09_instances") is True
            else CleanupTargetState.TERMINAL
        ),
        detail_code="provider-terminal-state-verified",
        clock=clock,
    )
    cleanup_journal.record_result(
        target_id="firewall-restoration",
        result=CleanupTargetState.RESTORED,
        detail_code="provider-firewall-baseline-verified",
        clock=clock,
    )
    local_credential = private_root / "openai-secret-upload"
    target = next(
        (
            item
            for item in cleanup_journal.load().targets
            if item.target_id == "temporary-local-secret"
        ),
        None,
    )
    if target is None or target.locator != str(local_credential):
        raise T09ProviderError("local secret cleanup authority drifted")
    if os.path.lexists(local_credential):
        metadata = local_credential.lstat()
        if local_credential.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise T09ProviderError("local secret cleanup target is unsafe")
        local_credential.unlink()
        result = CleanupTargetState.REMOVED
        detail = "temporary-local-secret-removed"
    else:
        result = CleanupTargetState.ABSENT
        detail = "temporary-local-secret-already-absent"
    cleanup_journal.record_result(
        target_id="temporary-local-secret",
        result=result,
        detail_code=detail,
        clock=clock,
    )
    return _write_provider_cleanup_receipt(cleanup_journal, private_root=private_root)


def _record_provider_closeout_failure(
    cleanup_journal: EarlyCleanupJournal,
    *,
    private_root: Path,
    error: BaseException,
    clock: Callable[[], float],
) -> None:
    """Retain a typed partial receipt without fabricating remote cleanup results."""

    terminal = {
        CleanupTargetState.ABSENT,
        CleanupTargetState.TERMINAL,
        CleanupTargetState.RESTORED,
        CleanupTargetState.REMOVED,
    }
    state = cleanup_journal.load()
    pending = next(
        (
            target
            for target_id in _PROVIDER_CLOSEOUT_TARGET_IDS
            for target in state.targets
            if target.target_id == target_id and target.state not in terminal
        ),
        None,
    )
    if pending is not None:
        cleanup_journal.record_result(
            target_id=pending.target_id,
            result=CleanupTargetState.FAILED,
            detail_code=type(error).__name__,
            clock=clock,
        )
    _write_provider_cleanup_receipt(cleanup_journal, private_root=private_root)


def _provisional_owner_binding(
    *,
    contract: T09ProviderContract,
    entry_root: Path,
    capability_path: Path,
    package_commit: str,
    plan_sha256: str,
    private_root: Path,
    instance_id: str,
    launch_slot: int,
    replacement_eligibility_sha256: str | None,
) -> dict[str, object]:
    """Bind one returned private ID before any active-state or receipt work."""

    owned_identity = _instance_identity_sha256(instance_id)
    capability = _load_json(capability_path, maximum_bytes=65_536)
    expected_private_root_identity = _sha256_bytes(str(private_root.resolve(strict=True)).encode())
    if (
        capability.get("plan_id") != contract.plan_id
        or capability.get("host_run_id") != contract.host_run_id
        or capability.get("package_commit") != package_commit
        or capability.get("plan_sha256") != plan_sha256
        or capability.get("launch_body_sha256")
        != _sha256_bytes(_canonical_bytes(_launch_body(contract=contract)))
        or capability.get("private_root_identity_sha256") != expected_private_root_identity
        or capability.get("launch_slot") != launch_slot
        or capability.get("launch_capability_limit") != contract.max_launch_count
        or capability.get("replacement_eligibility_sha256") != replacement_eligibility_sha256
        or capability.get("further_launch_forbidden") != (launch_slot == contract.max_launch_count)
    ):
        raise T09ProviderError("consumed launch capability cannot bind provisional ownership")
    journal = _journal_events(entry_root)
    launch_sends = [
        event
        for event in journal
        if event.get("event") == "send-started" and event.get("operation") == "launch"
    ]
    launch_responses = [
        event
        for event in journal
        if event.get("event") == "response-complete" and event.get("operation") == "launch"
    ]
    if len(launch_sends) != 1 or len(launch_responses) != 1:
        raise T09ProviderError("provisional owner lacks one completed launch journal pair")
    sent, response = launch_sends[0], launch_responses[0]
    launch_response_index = journal.index(response)
    launch_journal_prefix = journal[: launch_response_index + 1]
    response_file = _string(response.get("response_file"), label="launch projection file")
    response_path = entry_root / response_file
    if (
        response_path.parent != entry_root
        or sent.get("ordinal") != response.get("ordinal")
        or sent.get("request_body_sha256")
        != _sha256_bytes(_canonical_bytes(_launch_body(contract=contract)))
        or response.get("response_sha256") != file_sha256(response_path)
        or _mapping(
            _envelope(_load_json(response_path), label="launch projection"),
            label="launch projection data",
        ).get("instance_identity_sha256s")
        != [owned_identity]
    ):
        raise T09ProviderError("provisional owner drifted from the retained launch projection")
    return {
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "package_commit": package_commit,
        "plan_sha256": plan_sha256,
        "private_instance_id": instance_id,
        "owned_instance_identity_sha256": owned_identity,
        "instance_name": contract.instance_name,
        "launch_slot": launch_slot,
        "replacement_eligibility_sha256": replacement_eligibility_sha256,
        "lambda_started_at_epoch": sent["send_started_at_epoch"],
        "launch_request_ordinal": sent["ordinal"],
        "launch_request_body_sha256": sent["request_body_sha256"],
        "launch_projection_file": response_file,
        "launch_projection_sha256": response["response_sha256"],
        "launch_raw_response_sha256": response["raw_response_sha256"],
        "launch_journal_prefix_sha256": _sha256_bytes(_canonical_bytes(launch_journal_prefix)),
        "launch_capability_sha256": file_sha256(capability_path),
        "launch_capability_state": "consumed-cleanup-only-until-entry-receipt",
        "further_launch_forbidden": launch_slot == contract.max_launch_count,
        "private_operational_state_not_for_archive": True,
    }


def _write_provisional_console_marker(
    *,
    contract: T09ProviderContract,
    private_root: Path,
    instance_id: str,
    owned_identity: str,
    reason: str,
    clock: Callable[[], float],
) -> Path:
    marker = private_root / "PROVISIONAL_OWNER_CLEANUP_REQUIRES_CONSOLE.json"
    if not marker.exists():
        write_exclusive(
            marker,
            {
                "schema_version": "0.1.0",
                "plan_id": contract.plan_id,
                "host_run_id": contract.host_run_id,
                "private_instance_id": instance_id,
                "owned_instance_identity_sha256": owned_identity,
                "instance_name": contract.instance_name,
                "reason": reason,
                "launch_capability_state": "consumed-cleanup-only",
                "second_launch_forbidden": True,
                "required_action": (
                    "in the Lambda console, terminate this exact private instance ID if present; "
                    "verify that ID and every exact T09 instance-name match are terminal or "
                    "absent; do not launch again"
                ),
                "private_operational_state_not_for_archive": True,
                "created_at_epoch": clock(),
            },
        )
    return marker


def _provisional_replacement_permitted(
    contract: T09ProviderContract,
    *,
    launch_slot: int,
) -> bool:
    """Return whether the selected contract retains one exact launch slot."""

    if launch_slot not in range(1, contract.max_launch_count + 1):
        raise T09ProviderError("provisional launch slot escaped the selected contract")
    return launch_slot < contract.max_launch_count


def _cleanup_provisional_owner(
    *,
    contract: T09ProviderContract,
    transport: ProviderTransport,
    credential: bytearray,
    private_root: Path,
    provisional_binding: Mapping[str, object],
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> None:
    """Close an exact launched owner without requiring an entry receipt."""

    instance_id = _string(
        provisional_binding.get("private_instance_id"), label="provisional private instance ID"
    )
    owned_identity = _string(
        provisional_binding.get("owned_instance_identity_sha256"),
        label="provisional owned identity",
    )
    if _instance_identity_sha256(instance_id) != owned_identity:
        raise T09ProviderError("provisional private ID and identity binding disagree")
    launch_slot = _integer(provisional_binding.get("launch_slot"), label="provisional launch slot")
    replacement_permitted = _provisional_replacement_permitted(
        contract,
        launch_slot=launch_slot,
    )
    try:
        contract.validate_owner(
            plan_id=_string(provisional_binding.get("plan_id"), label="provisional plan ID"),
            host_run_id=_string(
                provisional_binding.get("host_run_id"), label="provisional host run ID"
            ),
            instance_name=_string(
                provisional_binding.get("instance_name"), label="provisional instance name"
            ),
        )
    except T09ProviderContractError as exc:
        raise T09ProviderError("provisional cleanup ownership crosses versions") from exc
    candidate_cleanup_journal = EarlyCleanupJournal(private_root / "preflight-cleanup-state")
    try:
        cleanup_state: EarlyCleanupState | None = candidate_cleanup_journal.load()
        cleanup_journal: EarlyCleanupJournal | None = candidate_cleanup_journal
    except EarlyCleanupStateError:
        cleanup_state = None
        cleanup_journal = None
    if (
        cleanup_journal is not None
        and cleanup_state is not None
        and (
            cleanup_state.provider_instance_id != instance_id
            or cleanup_state.provider_instance_identity_sha256 != owned_identity
            or cleanup_state.plan_id != contract.plan_id
            or cleanup_state.host_run_id != contract.host_run_id
            or cleanup_state.package_commit != provisional_binding.get("package_commit")
        )
    ):
        raise T09ProviderError("durable early cleanup authority changed exact ownership")
    entry_source = private_root / "entry-source"
    if not (entry_source / "source-manifest.json").is_file():
        seal_source_bundle(entry_source, contract=contract)
    cleanup_root = private_root / "provisional-closeout-source"
    cleanup_root.mkdir(mode=0o700, exist_ok=False)
    write_exclusive(
        cleanup_root / "provisional-owner-binding.json",
        dict(provisional_binding),
    )
    recorder = RequestRecorder(cleanup_root, transport, credential, clock)
    try:
        with contextlib.suppress(T09ProviderError):
            recorder.request(
                "terminate",
                "POST",
                "/api/v1/instance-operations/terminate",
                body=_terminate_body(instance_id),
                target_identity_sha256=owned_identity,
            )
        disposition: str | None = None
        for _ in range(MAX_TERMINATION_POLLS):
            sleeper(POLL_SECONDS)
            recorder.request("termination-instances", "GET", "/api/v1/instances")
            rows = _instance_rows(
                _response_documents(cleanup_root)["termination-instances"][-1][1],
                label="provisional cleanup instances",
            )
            owned = [row for row in rows if row.get("instance_identity_sha256") == owned_identity]
            exact_name_rows = [row for row in rows if row.get("name") == contract.instance_name]
            # A terminal row is useful cleanup evidence, but it is not absence and
            # cannot authorize a replacement.  Match normal closeout by retaining
            # the exact owner until both its identity and every exact-name row have
            # disappeared from the all-page inventory.
            if not owned and not exact_name_rows:
                disposition = "absent"
                break
        if disposition is None:
            raise T09ProviderError("provisional owner did not become absent in the bounded window")
        if cleanup_journal is not None:
            cleanup_journal.record_result(
                target_id="provider-instance",
                result=CleanupTargetState(disposition),
                detail_code="provider-terminal-state-verified",
                clock=clock,
            )
        recorder.request("post-global-firewall", "GET", "/api/v1/firewall-rulesets/global")
        sleeper(1.0)
        recorder.request("post-regional-rulesets", "GET", "/api/v1/firewall-rulesets")
        documents = _response_documents(cleanup_root)
        post_global = documents.get("post-global-firewall", [])
        post_rulesets = documents.get("post-regional-rulesets", [])
        if len(post_global) != 1 or len(post_rulesets) != 1:
            raise T09ProviderError("provisional cleanup lacks final security observations")
        security_restored = _security_projection(
            _load_json(entry_source / "004-global-firewall.json")
        ) == _security_projection(post_global[0][1]) and _rulesets_projection(
            _load_json(entry_source / "005-regional-rulesets.json")
        ) == _rulesets_projection(post_rulesets[0][1])
        if not security_restored:
            raise T09ProviderError("provisional cleanup did not restore provider security state")
        if cleanup_journal is not None:
            cleanup_journal.record_result(
                target_id="firewall-restoration",
                result=CleanupTargetState.RESTORED,
                detail_code="provider-firewall-baseline-verified",
                clock=clock,
            )
            local_credential_path = private_root / "openai-secret-upload"
            if os.path.lexists(local_credential_path):
                if local_credential_path.is_symlink() or not local_credential_path.is_file():
                    raise T09ProviderError("provisional local secret target is unsafe")
                local_credential_path.unlink()
                local_secret_result = CleanupTargetState.REMOVED
                local_secret_detail = "provisional-local-secret-removed"
            else:
                local_secret_result = CleanupTargetState.ABSENT
                local_secret_detail = "provisional-local-secret-never-created"
            cleanup_journal.record_result(
                target_id="temporary-local-secret",
                result=local_secret_result,
                detail_code=local_secret_detail,
                clock=clock,
            )
            cleanup_journal.record_result(
                target_id="temporary-remote-secret",
                result=CleanupTargetState.ABSENT,
                detail_code="provisional-remote-secret-never-created",
                clock=clock,
            )
            terminal_cleanup = cleanup_journal.load()
            cleanup_journal.write_basic_closeout_receipt(
                private_root / f"EARLY_CLEANUP_CLOSEOUT-{terminal_cleanup.sequence:08d}.json"
            )
        else:
            write_exclusive(
                private_root / "EARLY_CLEANUP_BOOTSTRAP_CLOSEOUT.json",
                {
                    "schema_version": "1.0.0",
                    "receipt_type": "t09-bootstrap-exact-owner-closeout",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "provider_instance_id": instance_id,
                    "provider_instance_identity_sha256": owned_identity,
                    "provider_disposition": disposition,
                    "firewall_restored": True,
                    "pilot_state_used": False,
                    "campaign_state_used": False,
                    "finalizer_state_used": False,
                    "cleanup_authority_source": "durable-provider-launch-journal",
                },
            )
        manifest = seal_source_bundle(cleanup_root, contract=contract)
        closed_at = clock()
        write_exclusive(
            private_root / "PROVISIONAL_OWNER_CLOSED.json",
            {
                "schema_version": "0.1.0",
                "plan_id": contract.plan_id,
                "host_run_id": contract.host_run_id,
                "private_instance_id": instance_id,
                "owned_instance_identity_sha256": owned_identity,
                "instance_name": contract.instance_name,
                "provider_disposition": disposition,
                "zero_t09_instances": disposition == "absent",
                "security_restored": security_restored,
                "source_manifest_sha256": file_sha256(cleanup_root / "source-manifest.json"),
                "source_bundle_bytes": manifest["total_bytes"],
                "launch_capability_state": "consumed-closed",
                "replacement_launch_eligibility_pending": replacement_permitted,
                "private_operational_state_not_for_archive": True,
                "closed_at_epoch": closed_at,
            },
        )
        if replacement_permitted:
            started = _number(
                provisional_binding.get("lambda_started_at_epoch"),
                label="provisional Lambda start",
            )
            duration = closed_at - started
            if duration < 0:
                raise T09ProviderError("provisional closeout chronology moved backwards")
            write_exclusive(
                private_root / "replacement-launch-eligibility.json",
                {
                    "schema_version": "0.1.0",
                    "eligibility_kind": "provider-entry-failed-preempirical",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "package_commit": provisional_binding["package_commit"],
                    "closed_launch_slot": launch_slot,
                    "entry_source_manifest_sha256": file_sha256(
                        private_root / "entry-source/source-manifest.json"
                    ),
                    "provisional_closeout_manifest_sha256": file_sha256(
                        cleanup_root / "source-manifest.json"
                    ),
                    "campaign_started_at_epoch": started,
                    "prior_lambda_duration_seconds": duration,
                    "prior_lambda_cost_usd": duration * 1.29 / 3600.0,
                    "empirical_attempts_entered": 0,
                    "model_task_requests": 0,
                    "task_browser_actions": 0,
                    "replacement_image_build_count": 0,
                    "slot2_image_archive_sha256": SLOT1_IMAGE_ARCHIVE_SHA256,
                    "slot2_image_archive_bytes": SLOT1_IMAGE_ARCHIVE_BYTES,
                    "slot2_expected_image_id": SLOT1_REPLACEMENT_IMAGE_ID,
                    "slot2_image_import_required": True,
                    "slot2_additional_image_build_count": 0,
                    "terminal_or_absent": True,
                    "zero_t09_instances": True,
                    "security_restored": True,
                    "second_launch_permitted": replacement_permitted,
                },
            )
    except BaseException as exc:
        with contextlib.suppress(BaseException):
            if cleanup_journal is not None:
                partial_state = cleanup_journal.load()
                pending_target = next(
                    (
                        target
                        for target in partial_state.targets
                        if target.state
                        not in {
                            CleanupTargetState.ABSENT,
                            CleanupTargetState.TERMINAL,
                            CleanupTargetState.RESTORED,
                            CleanupTargetState.REMOVED,
                        }
                    ),
                    None,
                )
                if pending_target is not None:
                    partial_state = cleanup_journal.record_result(
                        target_id=pending_target.target_id,
                        result=CleanupTargetState.FAILED,
                        detail_code=type(exc).__name__,
                        clock=clock,
                    )
                cleanup_journal.write_basic_closeout_receipt(
                    private_root / f"EARLY_CLEANUP_CLOSEOUT-{partial_state.sequence:08d}.json"
                )
        with contextlib.suppress(BaseException):
            _write_provisional_console_marker(
                contract=contract,
                private_root=private_root,
                instance_id=instance_id,
                owned_identity=owned_identity,
                reason=type(exc).__name__,
                clock=clock,
            )
        if not (cleanup_root / "source-manifest.json").exists():
            with contextlib.suppress(BaseException):
                seal_source_bundle(cleanup_root, contract=contract)
        raise T09ProviderError(
            "provisional exact-owner cleanup failed; perform the durable exact-ID console action"
        ) from exc


def _close_multi_instance_launch_incident(
    *,
    contract: T09ProviderContract,
    recorder: RequestRecorder,
    entry_root: Path,
    private_root: Path,
    instance_ids: list[str],
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> None:
    """Destroy every ID returned by one contract-violating launch response."""

    # Retain the complete provider-returned list *before* applying exact-set
    # validation.  In particular, duplicate IDs are an incident fact, not a
    # reason to lose the identities needed for cleanup.
    raw_identity_hashes = [_instance_identity_sha256(instance_id) for instance_id in instance_ids]
    unique_instance_ids = list(dict.fromkeys(instance_ids))
    projected_target_set = _sha256_bytes(_canonical_bytes(sorted(set(raw_identity_hashes))))
    write_exclusive(
        private_root / "MULTI_INSTANCE_LAUNCH_INCIDENT.json",
        {
            "schema_version": "0.1.0",
            "plan_id": contract.plan_id,
            "host_run_id": contract.host_run_id,
            "private_instance_ids_as_returned": list(instance_ids),
            "private_unique_instance_ids": unique_instance_ids,
            "instance_identity_sha256s_as_returned": raw_identity_hashes,
            "unique_instance_identity_sha256s": sorted(set(raw_identity_hashes)),
            "launch_count": 1,
            "second_launch_forbidden": True,
            "cleanup_target_set_sha256": projected_target_set,
            "private_operational_state_not_for_archive": True,
            "created_at_epoch": clock(),
        },
    )
    target_set = _instance_set_identity_sha256(unique_instance_ids)
    if target_set != projected_target_set:
        raise T09ProviderError("multi-instance cleanup target projection drifted")

    def require_console(reason: str) -> None:
        marker = private_root / "MULTI_INSTANCE_CLEANUP_REQUIRES_CONSOLE.json"
        if not marker.exists():
            write_exclusive(
                marker,
                {
                    "schema_version": "0.1.0",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "private_unique_instance_ids": unique_instance_ids,
                    "unique_instance_identity_sha256s": sorted(set(raw_identity_hashes)),
                    "cleanup_target_set_sha256": target_set,
                    "reason": reason,
                    "second_launch_forbidden": True,
                    "required_action": (
                        "in the Lambda console, terminate every exact private instance ID; "
                        "verify every ID is terminal or absent; do not launch again"
                    ),
                    "private_operational_state_not_for_archive": True,
                    "created_at_epoch": clock(),
                },
            )

    # A rejected or ambiguous exact-set mutation is reconciled only by fresh
    # inventory.  It is never repeated as a second scientific launch.
    with contextlib.suppress(T09ProviderError):
        recorder.request(
            "terminate",
            "POST",
            "/api/v1/instance-operations/terminate",
            body=_terminate_many_body(unique_instance_ids),
            target_identity_sha256=target_set,
        )
    expected = set(raw_identity_hashes)
    for _ in range(MAX_TERMINATION_POLLS):
        try:
            sleeper(POLL_SECONDS)
            recorder.request("termination-instances", "GET", "/api/v1/instances")
            rows = _instance_rows(
                _response_documents(entry_root)["termination-instances"][-1][1],
                label="multi-launch incident instances",
            )
        except T09ProviderError:
            require_console("fresh-inventory-reconciliation-failed")
            seal_source_bundle(entry_root, contract=contract)
            raise T09ProviderError(
                "multi-instance launch cleanup lost fresh inventory; use the exact-ID "
                "console marker and do not launch again"
            ) from None
        remaining = [
            row
            for row in rows
            if row.get("instance_identity_sha256") in expected
            and row.get("status") not in TERMINAL_STATES
        ]
        if not remaining:
            seal_source_bundle(entry_root, contract=contract)
            raise T09ProviderError(
                "one launch returned multiple instances; every returned identity was closed; "
                "the campaign is permanently stopped"
            )
    require_console("bounded-cleanup-did-not-prove-terminal")
    seal_source_bundle(entry_root, contract=contract)
    raise T09ProviderError(
        "one launch returned multiple instances and bounded cleanup did not prove them terminal; "
        "use the exact-ID console marker and do not launch again"
    )


def _manifest(root: Path, *, contract: T09ProviderContract) -> dict[str, object]:
    files: list[dict[str, object]] = []
    total = 0
    excluded = {"source-manifest.json", "entry-receipt.json", "closeout-receipt.json"}
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name in excluded:
            continue
        size = path.stat().st_size
        total += size
        if total > 33_554_432:
            raise T09ProviderError("provider source bundle exceeds its cap")
        files.append({"path": path.name, "bytes": size, "sha256": file_sha256(path)})
    return {
        "schema_version": "0.1.0",
        "source_observer": SOURCE_OBSERVER,
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "files": files,
        "total_bytes": total,
    }


def seal_source_bundle(root: Path, *, contract: T09ProviderContract) -> dict[str, object]:
    manifest = _manifest(root, contract=contract)
    write_exclusive(root / "source-manifest.json", manifest)
    return manifest


def validate_source_manifest(
    root: Path,
    *,
    contract: T09ProviderContract,
) -> dict[str, object]:
    manifest = _load_json(root / "source-manifest.json", maximum_bytes=1_048_576)
    if manifest != _manifest(root, contract=contract):
        raise T09ProviderError("provider source manifest does not match retained bytes")
    return manifest


def _entry_projection(
    root: Path,
    *,
    contract: T09ProviderContract,
    package_commit: str,
    plan_sha256: str,
    expected_public_key: str,
    expected_public_ipv4: str | None = None,
    expected_source_cidr_sha256: str | None = None,
) -> dict[str, object]:
    manifest = validate_source_manifest(root, contract=contract)
    authorization = _load_json(root / "authorization-binding.json", maximum_bytes=65_536)
    authorization_source_sha256 = authorization.get("authorization_source_sha256")
    authorization_reference = authorization.get("authorization_reference")
    authorization_fields = {
        "schema_version",
        "plan_id",
        "host_run_id",
        "authorization_source_sha256",
        "authorization_reference",
        "authorization_ledger_sha256",
    }
    model_metadata_receipt_sha256_value: str | None = None
    if contract.version == "V12":
        authorization_fields.add("model_metadata_receipt_sha256")
        candidate_receipt_sha256 = authorization.get("model_metadata_receipt_sha256")
        if (
            not isinstance(candidate_receipt_sha256, str)
            or _HEX64.fullmatch(candidate_receipt_sha256) is None
        ):
            raise T09ProviderError("V12 provider authorization lacks the receipt binding")
        model_metadata_receipt_sha256_value = candidate_receipt_sha256
    if (
        set(authorization) != authorization_fields
        or authorization.get("schema_version") != "0.1.0"
        or authorization.get("plan_id") != contract.plan_id
        or authorization.get("host_run_id") != contract.host_run_id
        or not isinstance(authorization_source_sha256, str)
        or _HEX64.fullmatch(authorization_source_sha256) is None
        or not isinstance(authorization_reference, str)
        or not isinstance(authorization.get("authorization_ledger_sha256"), str)
        or _HEX64.fullmatch(cast(str, authorization["authorization_ledger_sha256"])) is None
    ):
        raise T09ProviderError("provider entry authorization binding drifted")
    try:
        contract.validate_authority(authorization_reference, authorization_source_sha256)
    except T09ProviderContractError as exc:
        raise T09ProviderError("provider entry authorization binding drifted") from exc
    if contract.version == "V12":
        receipt_binding = _load_json(
            root / "model-metadata-receipt-binding.json", maximum_bytes=65_536
        )
        if (
            set(receipt_binding)
            != {
                "schema_version",
                "receipt_sha256",
                "receipt_filename",
                "provider_contract_version",
                "plan_id",
                "host_run_id",
                "prelaunch_required",
            }
            or receipt_binding.get("schema_version") != "1.0.0"
            or receipt_binding.get("receipt_sha256") != model_metadata_receipt_sha256_value
            or receipt_binding.get("receipt_filename") != MODEL_METADATA_RECEIPT_FILENAME
            or receipt_binding.get("provider_contract_version") != contract.version
            or receipt_binding.get("plan_id") != contract.plan_id
            or receipt_binding.get("host_run_id") != contract.host_run_id
            or receipt_binding.get("prelaunch_required") is not True
        ):
            raise T09ProviderError("provider model-metadata receipt binding drifted")
        try:
            retained_receipt_sha256 = model_metadata_receipt_sha256(
                root / MODEL_METADATA_RECEIPT_FILENAME
            )
        except (ModelMetadataReceiptError, OSError) as exc:
            raise T09ProviderError(
                "provider source lacks a safe retained model metadata receipt"
            ) from exc
        if retained_receipt_sha256 != model_metadata_receipt_sha256_value:
            raise T09ProviderError("provider source retained receipt hash drifted")
    elif (root / "model-metadata-receipt-binding.json").exists():
        raise T09ProviderError("historical provider entry unexpectedly retained a metadata receipt")
    cleanup_handoff = _load_json(root / "early-cleanup-handoff.json", maximum_bytes=65_536)
    if (
        set(cleanup_handoff)
        != {
            "schema_version",
            "journal_id",
            "journal_sequence",
            "journal_version_sha256",
            "provider_instance_identity_sha256",
            "transfer_policy",
        }
        or cleanup_handoff.get("schema_version") != "1.0.0"
        or not isinstance(cleanup_handoff.get("journal_id"), str)
        or _HEX64.fullmatch(cast(str, cleanup_handoff["journal_id"])) is None
        or not isinstance(cleanup_handoff.get("journal_sequence"), int)
        or not isinstance(cleanup_handoff.get("journal_version_sha256"), str)
        or _HEX64.fullmatch(cast(str, cleanup_handoff["journal_version_sha256"])) is None
        or cleanup_handoff.get("transfer_policy")
        != "copy-exact-hash-chain-before-remote-resource-mutation"
    ):
        raise T09ProviderError("early cleanup handoff binding drifted")
    campaign_binding = _load_json(root / "campaign-launch-binding.json", maximum_bytes=65_536)
    documents = _response_documents(root)
    _validate_prelaunch_documents(
        documents,
        contract=contract,
        expected_public_key=expected_public_key,
        expected_public_ipv4=expected_public_ipv4,
        expected_source_cidr_sha256=expected_source_cidr_sha256,
    )
    launch_event, launch_document = documents["launch"][0]
    launch_data = _mapping(_envelope(launch_document, label="launch"), label="launch data")
    instance_identity_sha256 = _string(
        _list(launch_data.get("instance_identity_sha256s"), label="launch identities")[0],
        label="instance identity",
    )
    if cleanup_handoff.get("provider_instance_identity_sha256") != instance_identity_sha256:
        raise T09ProviderError("early cleanup handoff changed provider ownership")
    active_documents = documents.get("active-instances", [])
    if not active_documents:
        raise T09ProviderError("entry bundle lacks an active-instance observation")
    matching: list[dict[str, object]] = []
    for _, document in active_documents:
        matching = [
            row
            for row in _instance_rows(document, label="active instances")
            if row.get("instance_identity_sha256") == instance_identity_sha256
            and row.get("name") == contract.instance_name
            and row.get("status") == "active"
        ]
        if matching:
            break
    if (
        len(matching) != 1
        or _instance_type_name(matching[0]) != INSTANCE_TYPE
        or (_region_name(matching[0]) != REGION)
    ):
        raise T09ProviderError("owned instance never reached the exact active identity")
    launch_started = launch_event.get("send_started_at_epoch")
    captured = active_documents[-1][0].get("response_received_at_epoch")
    if not isinstance(launch_started, (int, float)) or not isinstance(captured, (int, float)):
        raise T09ProviderError("provider entry chronology is unavailable")
    if not 0 <= float(captured) - float(launch_started) <= 1_800:
        raise T09ProviderError("provider entry observation exceeded its bounded window")
    launch_slot = _integer(campaign_binding.get("launch_slot"), label="campaign launch slot")
    campaign_started = _number(
        campaign_binding.get("campaign_started_at_epoch"), label="campaign start"
    )
    prior_lambda_duration = _number(
        campaign_binding.get("prior_lambda_duration_seconds"), label="prior Lambda duration"
    )
    prior_lambda_cost = _number(
        campaign_binding.get("prior_lambda_cost_usd"), label="prior Lambda cost"
    )
    campaign_binding_fields = {
        "schema_version",
        "plan_id",
        "host_run_id",
        "package_commit",
        "launch_slot",
        "campaign_started_at_epoch",
        "owned_lambda_started_at_epoch",
        "prior_lambda_duration_seconds",
        "prior_lambda_cost_usd",
        "replacement_eligibility_sha256",
    }
    if contract.version == "V12":
        campaign_binding_fields.add("model_metadata_receipt_sha256")
    binding_fields = set(campaign_binding)
    if (
        binding_fields
        not in {
            frozenset(campaign_binding_fields),
            frozenset(
                campaign_binding_fields
                | {
                    "replacement_eligibility_preempirical_source_manifest_sha256",
                    "normalized_slot2_authority_tree_manifest_sha256",
                }
            ),
        }
        or campaign_binding.get("schema_version") != "0.1.0"
        or campaign_binding.get("plan_id") != contract.plan_id
        or campaign_binding.get("host_run_id") != contract.host_run_id
        or campaign_binding.get("package_commit") != package_commit
        or launch_slot not in range(1, contract.max_launch_count + 1)
        or campaign_binding.get("owned_lambda_started_at_epoch") != float(launch_started)
        or (
            contract.version == "V12"
            and campaign_binding.get("model_metadata_receipt_sha256")
            != model_metadata_receipt_sha256_value
        )
        or not 0 < campaign_started <= float(launch_started)
        or prior_lambda_duration < 0
        or prior_lambda_cost < 0
        or (launch_slot == 1 and (prior_lambda_duration != 0 or prior_lambda_cost != 0))
        or campaign_started != float(launch_started)
    ):
        raise T09ProviderError("campaign launch chronology or cumulative binding drifted")
    eligibility_sha256 = campaign_binding.get("replacement_eligibility_sha256")
    eligibility_source_manifest_sha256 = campaign_binding.get(
        "replacement_eligibility_preempirical_source_manifest_sha256"
    )
    normalized_authority_tree_manifest_sha256 = campaign_binding.get(
        "normalized_slot2_authority_tree_manifest_sha256"
    )
    if launch_slot == 1 and eligibility_sha256 is not None:
        raise T09ProviderError("first launch unexpectedly has replacement eligibility")
    if launch_slot == 1 and eligibility_source_manifest_sha256 is not None:
        raise T09ProviderError("first launch unexpectedly has replacement source evidence")
    if launch_slot == 1 and normalized_authority_tree_manifest_sha256 is not None:
        raise T09ProviderError("first launch unexpectedly has a normalized authority tree")
    if launch_slot > 1 and (
        not isinstance(eligibility_sha256, str) or _HEX64.fullmatch(eligibility_sha256) is None
    ):
        raise T09ProviderError("replacement launch lacks its eligibility hash")
    if launch_slot > 1 and (
        not isinstance(eligibility_source_manifest_sha256, str)
        or _HEX64.fullmatch(eligibility_source_manifest_sha256) is None
        or not isinstance(normalized_authority_tree_manifest_sha256, str)
        or _HEX64.fullmatch(normalized_authority_tree_manifest_sha256) is None
    ):
        raise T09ProviderError("replacement launch lacks its two typed authority hashes")
    result: dict[str, object] = {
        "schema_version": "0.1.0",
        "receipt_type": "t09-pragmatic-provider-entry",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "package_commit": package_commit,
        "plan_sha256": plan_sha256,
        "authorization_source_sha256": authorization["authorization_source_sha256"],
        "authorization_reference": authorization["authorization_reference"],
        "authorization_ledger_sha256": authorization["authorization_ledger_sha256"],
        "early_cleanup_journal_id": cleanup_handoff["journal_id"],
        "early_cleanup_journal_sequence": cleanup_handoff["journal_sequence"],
        "early_cleanup_journal_version_sha256": cleanup_handoff["journal_version_sha256"],
        "captured_at_epoch": float(captured),
        "lambda_started_at_epoch": campaign_started,
        "provider_preflight_started_at_epoch": campaign_started,
        "owned_lambda_started_at_epoch": float(launch_started),
        "owned_instance_identity_sha256": instance_identity_sha256,
        "source_manifest_sha256": file_sha256(root / "source-manifest.json"),
        "source_bundle_bytes": manifest["total_bytes"],
        "source_observer": SOURCE_OBSERVER,
        "ssh_public_key_sha256": hashlib.sha256(expected_public_key.strip().encode()).hexdigest(),
        "source_ipv4_cidr_sha256": expected_source_cidr_sha256
        or _network_identity_sha256(f"{expected_public_ipv4}/32"),
        "zero_prior_nonterminal_instances": True,
        "launch_slot": launch_slot,
        "launch_count": launch_slot,
        "max_preflight_launch_count": contract.max_launch_count,
        "replacement_eligibility_sha256": eligibility_sha256,
        "max_instances": 1,
        "instance_type": INSTANCE_TYPE,
        "region": REGION,
        "persistent_filesystems": 0,
        "hourly_price_usd": 1.29,
        "new_campaign_openai_cost_cap_usd": contract.campaign_openai_cost_cap_usd,
        "new_preflight_lambda_cost_cap_usd": contract.preflight_lambda_cost_cap_usd,
        "new_campaign_lambda_cost_cap_usd": contract.campaign_lambda_cost_cap_usd,
        "new_campaign_aggregate_cost_cap_usd": contract.campaign_aggregate_cost_cap_usd,
        "prior_campaign_lambda_duration_seconds": prior_lambda_duration,
        "prior_campaign_lambda_cost_usd": prior_lambda_cost,
        "prior_t09_cost_usd": contract.prior_t09_cost_usd,
        "cumulative_t09_cost_cap_usd": contract.cumulative_t09_cost_cap_usd,
        "billable_clock_source": "actual-active-lambda-seconds",
        "provider_projection_retained_private": True,
        "raw_response_identity_retained": True,
        "raw_provider_payload_retained": False,
        "structural_redaction_passed": True,
    }
    if model_metadata_receipt_sha256_value is not None:
        result["model_metadata_receipt_sha256"] = model_metadata_receipt_sha256_value
    if "replacement_eligibility_preempirical_source_manifest_sha256" in campaign_binding:
        result["replacement_eligibility_preempirical_source_manifest_sha256"] = (
            eligibility_source_manifest_sha256
        )
        result["normalized_slot2_authority_tree_manifest_sha256"] = (
            normalized_authority_tree_manifest_sha256
        )
    return result


def create_entry_receipt(
    root: Path,
    *,
    contract: T09ProviderContract,
    package_commit: str,
    plan_sha256: str,
    expected_public_key: str,
    expected_public_ipv4: str,
    model_metadata_receipt_sha256: str | None = None,
) -> Path:
    receipt = _entry_projection(
        root,
        contract=contract,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        expected_public_key=expected_public_key,
        expected_public_ipv4=expected_public_ipv4,
    )
    if (
        model_metadata_receipt_sha256 is not None
        and receipt.get("model_metadata_receipt_sha256") != model_metadata_receipt_sha256
    ):
        raise T09ProviderError("provider entry receipt metadata binding drifted")
    path = root / "entry-receipt.json"
    write_exclusive(path, receipt)
    return path


def validate_entry_receipt(
    receipt_path: Path,
    source_root: Path,
    *,
    contract: T09ProviderContract,
    package_commit: str,
    plan_sha256: str,
    expected_public_key: str,
    expected_public_ipv4: str,
) -> dict[str, object]:
    observed = _load_json(receipt_path, maximum_bytes=65_536)
    expected = _entry_projection(
        source_root,
        contract=contract,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        expected_public_key=expected_public_key,
        expected_public_ipv4=expected_public_ipv4,
    )
    if observed != expected:
        raise T09ProviderError("provider entry receipt is not derived from its source bundle")
    return observed


def validate_entry_receipt_source_bound(
    receipt_path: Path,
    source_root: Path,
    *,
    contract: T09ProviderContract,
    package_commit: str,
    plan_sha256: str,
) -> dict[str, object]:
    """Reconstruct an entry receipt from raw provider bytes without private prose."""

    observed = _load_json(receipt_path, maximum_bytes=65_536)
    documents = _response_documents(source_root)
    key_rows = [
        _mapping(item, label="SSH key")
        for item in _list(
            _envelope(documents["ssh-keys"][0][1], label="SSH keys"),
            label="SSH key data",
        )
        if isinstance(item, dict) and item.get("name") == SSH_KEY_NAME
    ]
    if len(key_rows) != 1:
        raise T09ProviderError("entry source lacks the one selected SSH key")
    public_key = _string(key_rows[0].get("public_key"), label="SSH public key")
    if hashlib.sha256(public_key.strip().encode()).hexdigest() != observed.get(
        "ssh_public_key_sha256"
    ):
        raise T09ProviderError("entry SSH-key binding is not source-derived")
    firewall = _mapping(
        _envelope(documents["global-firewall"][0][1], label="global firewall"),
        label="global firewall data",
    )
    candidate_cidrs = [
        source_hash
        for rule in (
            _mapping(item, label="firewall rule")
            for item in _list(firewall.get("rules"), label="firewall rules")
        )
        if rule.get("protocol") == "tcp"
        and rule.get("port_range") in [[22, 22], [22]]
        and isinstance((source_hash := rule.get("source_network_identity_sha256")), str)
        and source_hash == observed.get("source_ipv4_cidr_sha256")
    ]
    if len(candidate_cidrs) != 1:
        raise T09ProviderError("entry source-CIDR binding is not uniquely source-derived")
    expected = _entry_projection(
        source_root,
        contract=contract,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        expected_public_key=public_key,
        expected_source_cidr_sha256=candidate_cidrs[0],
    )
    if observed != expected:
        raise T09ProviderError("provider entry receipt is not derived from its source bundle")
    return observed


def _security_projection(document: Mapping[str, object]) -> str:
    data = _mapping(_envelope(document, label="firewall"), label="firewall data")
    projection = {
        "name": data.get("name"),
        "rules": data.get("rules"),
    }
    return _sha256_bytes(_canonical_bytes(projection))


def _rulesets_projection(document: Mapping[str, object]) -> str:
    data = _mapping(_envelope(document, label="rulesets"), label="rulesets data")
    hashes = _list(data.get("ruleset_semantic_sha256s"), label="ruleset hashes")
    if any(not isinstance(item, str) or _HEX64.fullmatch(item) is None for item in hashes):
        raise T09ProviderError("ruleset semantic projection is malformed")
    return _sha256_bytes(_canonical_bytes(hashes))


def _closeout_projection(
    root: Path,
    *,
    contract: T09ProviderContract,
    entry_receipt: Mapping[str, object],
    entry_source_root: Path,
    package_commit: str,
    plan_sha256: str,
    lifecycle: CampaignLifecycle,
    empirical_clock_manifest: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if lifecycle.contract != contract:
        raise T09ProviderError("closeout lifecycle and provider contract disagree")
    if empirical_clock_manifest is None:
        retained_clock = root / "empirical-clock-manifest.json"
        if retained_clock.is_file():
            empirical_clock_manifest = _load_json(retained_clock, maximum_bytes=1_048_576)
    manifest = validate_source_manifest(root, contract=contract)
    documents = _response_documents(root)
    owned_state = _load_json(root / "owned-state-binding.json", maximum_bytes=65_536)
    owned_identity_sha256 = _string(
        owned_state.get("owned_instance_identity_sha256"), label="owned instance identity"
    )
    started = _number(entry_receipt["lambda_started_at_epoch"], label="campaign start")
    owned_started = _number(
        entry_receipt["owned_lambda_started_at_epoch"], label="owned Lambda start"
    )
    prior_lambda_duration = _number(
        entry_receipt["prior_campaign_lambda_duration_seconds"],
        label="prior campaign Lambda duration",
    )
    prior_lambda_cost = _number(
        entry_receipt["prior_campaign_lambda_cost_usd"], label="prior campaign Lambda cost"
    )
    if owned_state.get("owned_instance_identity_sha256") != entry_receipt.get(
        "owned_instance_identity_sha256"
    ):
        raise T09ProviderError("closeout owned identity drifted from entry")
    journal = _journal_events(root)
    termination_sends = [
        event
        for event in journal
        if event.get("event") == "send-started" and event.get("operation") == "terminate"
    ]
    if not 1 <= len(termination_sends) <= MAX_TERMINATION_POSTS:
        raise T09ProviderError("closeout has no bounded exact-target termination request")
    if any(
        event.get("method") != "POST"
        or event.get("path") != "/api/v1/instance-operations/terminate"
        or event.get("target_identity_sha256") != owned_identity_sha256
        for event in termination_sends
    ):
        raise T09ProviderError("termination request target drifted from the exact owned target")
    terminations = documents.get("terminate", [])
    for _, document in terminations:
        data = _mapping(_envelope(document, label="termination"), label="termination data")
        terminated_rows = _list(data.get("instance_identity_sha256s"), label="terminated instances")
        if owned_identity_sha256 not in terminated_rows:
            raise T09ProviderError("termination response did not bind the exact owned instance")
    termination_started = min(
        _number(event["send_started_at_epoch"], label="termination send time")
        for event in termination_sends
    )
    terminal_at: float | None = None
    zero_at: float | None = None
    for event, document in documents.get("termination-instances", []):
        rows = _instance_rows(document, label="termination instances")
        owned = [
            row for row in rows if row.get("instance_identity_sha256") == owned_identity_sha256
        ]
        t09 = [row for row in rows if row.get("name") == contract.instance_name]
        timestamp = _number(event["response_received_at_epoch"], label="poll response time")
        if not owned or all(row.get("status") in TERMINAL_STATES for row in owned):
            terminal_at = timestamp
        # "Zero" means absent from the all-page exact-name inventory.  A
        # terminal row is useful billing/cleanup evidence, but it is not zero.
        if not t09:
            zero_at = timestamp
        if terminal_at is not None and zero_at is not None:
            break
    if terminal_at is None or zero_at is None:
        raise T09ProviderError("closeout lacks terminal and zero-T09 observations")
    if (
        len(documents.get("post-global-firewall", [])) != 1
        or len(documents.get("post-regional-rulesets", [])) != 1
    ):
        raise T09ProviderError("closeout lacks final security observations")
    pre_global = _load_json(entry_source_root / "004-global-firewall.json")
    pre_rulesets = _load_json(entry_source_root / "005-regional-rulesets.json")
    post_global = documents["post-global-firewall"][0][1]
    post_rulesets = documents["post-regional-rulesets"][0][1]
    security_restored = _security_projection(pre_global) == _security_projection(
        post_global
    ) and _rulesets_projection(pre_rulesets) == _rulesets_projection(post_rulesets)
    captured = max(
        _number(
            documents["post-global-firewall"][0][0]["response_received_at_epoch"],
            label="firewall response time",
        ),
        _number(
            documents["post-regional-rulesets"][0][0]["response_received_at_epoch"],
            label="ruleset response time",
        ),
        terminal_at,
        zero_at,
    )
    empirical_started: float | None = None
    if empirical_clock_manifest is not None:
        empirical_started = _number(
            empirical_clock_manifest.get("campaign_started_at_epoch"),
            label="empirical campaign start",
        )
        if (
            empirical_clock_manifest.get("plan_id") != contract.plan_id
            or empirical_clock_manifest.get("host_run_id") != contract.host_run_id
            or empirical_clock_manifest.get("clean_package_commit") != package_commit
            or empirical_clock_manifest.get("provider_entry_receipt_sha256")
            != entry_receipt.get("receipt_sha256")
            or empirical_clock_manifest.get("owned_instance_identity_sha256")
            != owned_identity_sha256
            or empirical_started <= started
        ):
            raise T09ProviderError("empirical clock manifest is not source-bound")
    clock_origin = empirical_started if empirical_started is not None else started
    terminal_elapsed = max(terminal_at, zero_at) - clock_origin
    owned_lambda_duration = max(terminal_at, zero_at) - owned_started
    lambda_duration = prior_lambda_duration + owned_lambda_duration
    lambda_list_cost_usd = prior_lambda_cost + owned_lambda_duration * 1.29 / 3600.0
    empirical_lambda_cost_usd = (
        (max(terminal_at, zero_at) - empirical_started) * 1.29 / 3600.0
        if empirical_started is not None
        else 0.0
    )
    if (
        owned_lambda_duration < 0
        or lambda_duration < 0
        or lambda_list_cost_usd < 0
        or (
            empirical_started is None
            and lambda_list_cost_usd > contract.preflight_lambda_cost_cap_usd
        )
        or empirical_lambda_cost_usd > contract.campaign_lambda_cost_cap_usd
        or contract.prior_t09_cost_usd + lambda_list_cost_usd > contract.cumulative_t09_cost_cap_usd
    ):
        raise T09ProviderError("autonomous Lambda phase or cumulative cost exceeded its cap")
    preflight_failure_timing: dict[str, object] | None = None
    failed_preflight_dispatch_deadline: float | None = None
    failed_preflight_started: float | None = None
    failed_preflight_iteration_started: float | None = None
    failed_preflight_failed_at: float | None = None
    if empirical_started is None and (root / "preflight-failure-timing.json").is_file():
        preflight_failure_timing = _load_json(
            root / "preflight-failure-timing.json", maximum_bytes=65_536
        )
        raw_dispatch_deadline = preflight_failure_timing.get("termination_dispatch_deadline_epoch")
        failed_preflight_dispatch_deadline = (
            _number(raw_dispatch_deadline, label="preflight dispatch deadline")
            if raw_dispatch_deadline is not None
            else None
        )
        failed_preflight_started = _number(
            preflight_failure_timing.get("provider_preflight_started_at_epoch"),
            label="failed preflight start",
        )
        failed_preflight_failed_at = _number(
            preflight_failure_timing.get("failed_at_epoch"),
            label="preflight failure time",
        )
        if isinstance(lifecycle.limits, AutonomousPilotLifecycleLimits):
            autonomous_limits = lifecycle.limits
            failed_preflight_iteration_started = _number(
                preflight_failure_timing.get("preflight_iteration_started_at_epoch"),
                label="failed preflight iteration start",
            )
            failed_preflight_iteration_elapsed = _number(
                preflight_failure_timing.get("preflight_iteration_elapsed_seconds"),
                label="failed preflight iteration elapsed time",
            )
            failed_preflight_provider_elapsed = _number(
                preflight_failure_timing.get("provider_instance_elapsed_seconds"),
                label="failed preflight provider instance elapsed time",
            )
            if (
                set(preflight_failure_timing)
                != {
                    "schema_version",
                    "plan_id",
                    "host_run_id",
                    "preflight_failure_sha256",
                    "provider_preflight_started_at_epoch",
                    "preflight_iteration_started_at_epoch",
                    "failed_at_epoch",
                    "preflight_iteration_elapsed_seconds",
                    "provider_instance_elapsed_seconds",
                    "termination_dispatch_deadline_epoch",
                    "preflight_engineering_state",
                }
                or preflight_failure_timing.get("schema_version") != "0.1.0"
                or preflight_failure_timing.get("plan_id") != contract.plan_id
                or preflight_failure_timing.get("host_run_id") != contract.host_run_id
                or failed_preflight_started != started
                or not failed_preflight_started
                <= failed_preflight_iteration_started
                <= failed_preflight_failed_at
                or failed_preflight_iteration_elapsed
                != failed_preflight_failed_at - failed_preflight_iteration_started
                or failed_preflight_provider_elapsed
                != failed_preflight_failed_at - failed_preflight_started
                or not 0
                <= failed_preflight_iteration_elapsed
                <= autonomous_limits.preflight_iteration_wall_seconds + 5
                or not 0
                <= failed_preflight_provider_elapsed
                <= autonomous_limits.maximum_preflight_instance_active_seconds
                or preflight_failure_timing.get("preflight_engineering_state")
                != "resumable-same-host"
                or failed_preflight_dispatch_deadline is not None
            ):
                raise T09ProviderError("preflight failure timing receipt drifted")
        elif isinstance(lifecycle.limits, Retry4LifecycleLimits):
            failed_preflight_elapsed = _number(
                preflight_failure_timing.get("elapsed_seconds"),
                label="failed preflight elapsed time",
            )
            if (
                set(preflight_failure_timing)
                != {
                    "schema_version",
                    "plan_id",
                    "host_run_id",
                    "preflight_failure_sha256",
                    "provider_preflight_started_at_epoch",
                    "failed_at_epoch",
                    "elapsed_seconds",
                    "termination_dispatch_deadline_epoch",
                }
                or preflight_failure_timing.get("schema_version") != "0.1.0"
                or preflight_failure_timing.get("plan_id") != contract.plan_id
                or preflight_failure_timing.get("host_run_id") != contract.host_run_id
                or failed_preflight_started != started
                or failed_preflight_elapsed != failed_preflight_failed_at - failed_preflight_started
                or failed_preflight_elapsed < 0
                or failed_preflight_dispatch_deadline
                != failed_preflight_failed_at
                + lifecycle.limits.failed_preflight_termination_dispatch_seconds
            ):
                raise T09ProviderError("preflight failure timing receipt drifted")
        else:
            raise T09ProviderError(
                "manual historical closeout cannot contain a preflight timing receipt"
            )
    campaign_exception = _classify_campaign_wall_exception(
        lifecycle=lifecycle,
        provider_started_at_epoch=started,
        empirical_started_at_epoch=empirical_started,
        termination_started_at_epoch=termination_started,
        terminal_observed_at_epoch=max(terminal_at, zero_at),
        owned_lambda_duration_seconds=owned_lambda_duration,
        cumulative_lambda_duration_seconds=lambda_duration,
        failed_preflight_dispatch_deadline_epoch=failed_preflight_dispatch_deadline,
        failed_preflight_started_at_epoch=(
            failed_preflight_iteration_started
            if isinstance(lifecycle.limits, AutonomousPilotLifecycleLimits)
            else failed_preflight_started
        ),
        failed_preflight_failed_at_epoch=failed_preflight_failed_at,
    )
    return {
        "schema_version": "0.1.0",
        "receipt_type": "t09-pragmatic-provider-closeout",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "package_commit": package_commit,
        "plan_sha256": plan_sha256,
        "captured_at_epoch": captured,
        "lambda_started_at_epoch": started,
        "empirical_campaign_started_at_epoch": empirical_started,
        "owned_lambda_started_at_epoch": owned_started,
        "termination_started_at_epoch": termination_started,
        "terminal_observed_at_epoch": terminal_at,
        "zero_instance_observed_at_epoch": zero_at,
        "owned_instance_identity_sha256": entry_receipt["owned_instance_identity_sha256"],
        "termination_target_identity_sha256": owned_identity_sha256,
        "entry_receipt_sha256": entry_receipt["receipt_sha256"],
        "source_manifest_sha256": file_sha256(root / "source-manifest.json"),
        "source_bundle_bytes": manifest["total_bytes"],
        "source_observer": SOURCE_OBSERVER,
        "launch_slot": entry_receipt["launch_slot"],
        "launch_count": entry_receipt["launch_count"],
        "max_preflight_launch_count": contract.max_launch_count,
        "termination_request_count": len(termination_sends),
        "terminal_or_absent": True,
        "zero_t09_instances": True,
        "security_restored": security_restored,
        "provider_projection_retained_private": True,
        "raw_response_identity_retained": True,
        "raw_provider_payload_retained": False,
        "structural_redaction_passed": True,
        "campaign_wall_exception": campaign_exception,
        "campaign_elapsed_seconds": terminal_elapsed,
        "provider_preflight_duration_seconds": (
            empirical_started - started if empirical_started is not None else None
        ),
        "preflight_failure_timing_sha256": (
            file_sha256(root / "preflight-failure-timing.json")
            if preflight_failure_timing is not None
            else None
        ),
        "failed_preflight_duration_seconds": (
            failed_preflight_failed_at - failed_preflight_started
            if failed_preflight_failed_at is not None and failed_preflight_started is not None
            else None
        ),
        "owned_lambda_duration_seconds": owned_lambda_duration,
        "prior_campaign_lambda_duration_seconds": prior_lambda_duration,
        "lambda_duration_seconds": lambda_duration,
        "lambda_list_cost_usd": lambda_list_cost_usd,
        "new_campaign_lambda_cost_cap_usd": contract.campaign_lambda_cost_cap_usd,
        "prior_t09_cost_usd": contract.prior_t09_cost_usd,
        "cumulative_t09_cost_before_openai_usd": (
            contract.prior_t09_cost_usd + lambda_list_cost_usd
        ),
        "cumulative_t09_cost_cap_usd": contract.cumulative_t09_cost_cap_usd,
    }


HARD_CAMPAIGN_WALL_EXCEPTIONS: Final = frozenset(
    {
        "failed-preflight-termination-dispatch-violated",
        "failed-preflight-wall-violated",
        "successful-host-active-cap-violated",
        "cumulative-active-cap-violated",
        "termination-cutoff-violated",
    }
)
RETRY4_HARD_CAMPAIGN_WALL_EXCEPTIONS: Final = HARD_CAMPAIGN_WALL_EXCEPTIONS | {
    "successful-preflight-wall-violated"
}


def _hard_campaign_wall_exceptions(lifecycle: CampaignLifecycle) -> frozenset[str]:
    if isinstance(lifecycle.limits, Retry4LifecycleLimits):
        return RETRY4_HARD_CAMPAIGN_WALL_EXCEPTIONS
    return HARD_CAMPAIGN_WALL_EXCEPTIONS


def _classify_campaign_wall_exception(
    *,
    lifecycle: CampaignLifecycle,
    provider_started_at_epoch: float,
    empirical_started_at_epoch: float | None,
    termination_started_at_epoch: float,
    terminal_observed_at_epoch: float,
    owned_lambda_duration_seconds: float,
    cumulative_lambda_duration_seconds: float,
    failed_preflight_dispatch_deadline_epoch: float | None,
    failed_preflight_started_at_epoch: float | None,
    failed_preflight_failed_at_epoch: float | None,
) -> str:
    """Classify every hard provider-clock boundary from exact observed epochs."""

    limits = lifecycle.limits
    if isinstance(limits, ObserverLifecycleLimits):
        if empirical_started_at_epoch is not None:
            raise T09ProviderError("manual campaign unexpectedly has a separate empirical clock")
        if termination_started_at_epoch - provider_started_at_epoch > (
            lifecycle.termination_cutoff_seconds
        ):
            return "termination-cutoff-violated"
        if terminal_observed_at_epoch - provider_started_at_epoch > lifecycle.wall_seconds:
            return "best-effort-termination-provider-control-plane-delay"
        return "none"
    if isinstance(limits, Retry4LifecycleLimits):
        if cumulative_lambda_duration_seconds > limits.maximum_cumulative_active_seconds:
            return "cumulative-active-cap-violated"
        if empirical_started_at_epoch is None:
            if (
                failed_preflight_started_at_epoch is not None
                and failed_preflight_failed_at_epoch is not None
                and failed_preflight_failed_at_epoch - failed_preflight_started_at_epoch
                > lifecycle.preflight_wall_seconds
            ):
                return "failed-preflight-wall-violated"
            if failed_preflight_dispatch_deadline_epoch is not None:
                return (
                    "failed-preflight-termination-dispatch-violated"
                    if termination_started_at_epoch > failed_preflight_dispatch_deadline_epoch
                    else "none"
                )
            if termination_started_at_epoch - provider_started_at_epoch > (
                lifecycle.preflight_wall_seconds
                + limits.failed_preflight_termination_dispatch_seconds
            ):
                return "failed-preflight-termination-dispatch-violated"
            return "none"
        if (
            empirical_started_at_epoch - provider_started_at_epoch
            > lifecycle.preflight_wall_seconds
        ):
            return "successful-preflight-wall-violated"
        if owned_lambda_duration_seconds > limits.maximum_successful_host_active_seconds:
            return "successful-host-active-cap-violated"
        if (
            termination_started_at_epoch - empirical_started_at_epoch
            > lifecycle.termination_cutoff_seconds
        ):
            return "termination-cutoff-violated"
        if terminal_observed_at_epoch - empirical_started_at_epoch > lifecycle.wall_seconds:
            return "best-effort-termination-provider-control-plane-delay"
        return "none"
    if not isinstance(limits, AutonomousPilotLifecycleLimits):  # pragma: no cover
        raise T09ProviderError("provider lifecycle limits are unsupported")
    if empirical_started_at_epoch is None:
        if cumulative_lambda_duration_seconds > limits.maximum_cumulative_preflight_active_seconds:
            return "cumulative-active-cap-violated"
        if (
            failed_preflight_started_at_epoch is not None
            and failed_preflight_failed_at_epoch is not None
            and failed_preflight_failed_at_epoch - failed_preflight_started_at_epoch
            > lifecycle.preflight_wall_seconds
        ):
            return "failed-preflight-wall-violated"
        if failed_preflight_dispatch_deadline_epoch is not None:
            return (
                "failed-preflight-termination-dispatch-violated"
                if termination_started_at_epoch > failed_preflight_dispatch_deadline_epoch
                else "none"
            )
        if termination_started_at_epoch - provider_started_at_epoch > (
            lifecycle.preflight_wall_seconds + 300
        ):
            return "failed-preflight-termination-dispatch-violated"
        return "none"
    if owned_lambda_duration_seconds > limits.maximum_preflight_instance_active_seconds:
        return "successful-host-active-cap-violated"
    if (
        termination_started_at_epoch - empirical_started_at_epoch
        > lifecycle.termination_cutoff_seconds
    ):
        return "termination-cutoff-violated"
    if terminal_observed_at_epoch - empirical_started_at_epoch > lifecycle.wall_seconds:
        return "best-effort-termination-provider-control-plane-delay"
    return "none"


def create_closeout_receipt(
    root: Path,
    *,
    contract: T09ProviderContract,
    entry_receipt_path: Path,
    entry_source_root: Path,
    package_commit: str,
    plan_sha256: str,
    lifecycle: CampaignLifecycle,
    empirical_clock_manifest: Mapping[str, object] | None = None,
) -> Path:
    entry = _load_json(entry_receipt_path, maximum_bytes=65_536)
    entry["receipt_sha256"] = file_sha256(entry_receipt_path)
    receipt = _closeout_projection(
        root,
        contract=contract,
        entry_receipt=entry,
        entry_source_root=entry_source_root,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        lifecycle=lifecycle,
        empirical_clock_manifest=empirical_clock_manifest,
    )
    path = root / "closeout-receipt.json"
    write_exclusive(path, receipt)
    return path


def validate_closeout_receipt(
    receipt_path: Path,
    source_root: Path,
    *,
    contract: T09ProviderContract,
    entry_receipt_path: Path,
    entry_source_root: Path,
    package_commit: str,
    plan_sha256: str,
    lifecycle: CampaignLifecycle,
) -> dict[str, object]:
    observed = _load_json(receipt_path, maximum_bytes=65_536)
    entry = validate_entry_receipt_source_bound(
        entry_receipt_path,
        entry_source_root,
        contract=contract,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
    )
    entry["receipt_sha256"] = file_sha256(entry_receipt_path)
    empirical_clock_manifest = (
        _load_json(source_root / "empirical-clock-manifest.json", maximum_bytes=1_048_576)
        if (source_root / "empirical-clock-manifest.json").is_file()
        else None
    )
    expected = _closeout_projection(
        source_root,
        contract=contract,
        entry_receipt=entry,
        entry_source_root=entry_source_root,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
        lifecycle=lifecycle,
        empirical_clock_manifest=empirical_clock_manifest,
    )
    if observed != expected:
        raise T09ProviderError("provider closeout receipt is not derived from its source bundle")
    if observed.get("campaign_wall_exception") in _hard_campaign_wall_exceptions(lifecycle):
        raise T09ProviderError("provider termination missed its source-bound cutoff")
    if observed.get("security_restored") is not True:
        raise T09ProviderError("provider security state was not restored")
    return observed


def _git_blob(repository: Path, commit: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"{commit}:{relative}"],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        raise T09ProviderError(f"slot-2 transition cannot read reviewed Git path: {relative}")
    return result.stdout


def _slot2_science_projection(
    repository: Path,
    commit: str,
    *,
    expected_plan_sha256: str = SLOT1_PLAN_SHA256,
) -> dict[str, object]:
    """Project only scientific execution fields across the slot-1→slot-2 repair."""

    immutable_paths = (
        "experiments/EXP-0001-sira-simulative-vs-reactive/protocol.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/config.yaml",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_DATASET_CONTRACT.json",
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_EVALUATOR_CONTRACT.json",
        "src/giclab/harness/sira_gate_a.py",
        "src/giclab/harness/safety.py",
    )
    plan_relative = "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml"
    commands_relative = (
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json"
    )
    plan_bytes = _git_blob(repository, commit, plan_relative)
    if hashlib.sha256(plan_bytes).hexdigest() != expected_plan_sha256:
        raise T09ProviderError("slot-2 transition changed the locked pilot plan")
    try:
        commands_raw: object = json.loads(_git_blob(repository, commit, commands_relative))
    except json.JSONDecodeError as exc:
        raise T09ProviderError("slot-2 command manifests are malformed") from exc
    commands = _mapping(commands_raw, label="slot-2 command manifests")
    raw_manifests = _list(commands.get("manifests"), label="slot-2 command manifests")
    if len(raw_manifests) != 4:
        raise T09ProviderError("slot-2 transition lacks four command manifests")
    scientific_commands: list[dict[str, object]] = []
    for raw in raw_manifests:
        manifest = _mapping(raw, label="slot-2 command manifest")
        argv = _list(manifest.get("argv"), label="slot-2 command argv")
        if any(not isinstance(item, str) for item in argv) or "--" not in argv:
            raise T09ProviderError("slot-2 command argv is malformed")
        split = cast(list[str], argv).index("--")
        equality = _mapping(manifest.get("equality_surface"), label="slot-2 equality surface")
        equality_scientific = {
            key: value
            for key, value in equality.items()
            if key not in {"giclab_commit", "environment_sha256"}
        }
        scientific_commands.append(
            {
                "run_id": manifest.get("run_id"),
                "task_id": manifest.get("task_id"),
                "condition": manifest.get("condition"),
                "pair_id": manifest.get("pair_id"),
                "order_index": manifest.get("order_index"),
                "upstream_argv": argv[split + 1 :],
                "equality_surface": equality_scientific,
            }
        )
    pair_diffs = _list(commands.get("pair_diffs"), label="slot-2 pair diffs")
    if len(pair_diffs) != 2 or any(
        not isinstance(item, dict) or item.get("valid") is not True for item in pair_diffs
    ):
        raise T09ProviderError("slot-2 pair matching is not valid")
    return {
        "plan_sha256": expected_plan_sha256,
        "immutable_file_sha256s": {
            relative: hashlib.sha256(_git_blob(repository, commit, relative)).hexdigest()
            for relative in immutable_paths
        },
        "commands": scientific_commands,
    }


def _slot2_runtime_control_projection(repository: Path, commit: str) -> dict[str, object]:
    """Bind the reviewed control-runtime rebase separately from frozen science."""

    runtime_relative = (
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_RUNTIME_IDENTITY.json"
    )
    commands_relative = (
        "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
        "T09_PILOT_COMMAND_MANIFESTS.json"
    )
    runtime_bytes = _git_blob(repository, commit, runtime_relative)
    try:
        runtime_raw: object = json.loads(runtime_bytes)
        commands_raw: object = json.loads(_git_blob(repository, commit, commands_relative))
    except json.JSONDecodeError as exc:
        raise T09ProviderError("slot-2 runtime control projection is malformed") from exc
    runtime = _mapping(runtime_raw, label="slot-2 runtime identity")
    instrumentation = _mapping(
        runtime.get("repository_instrumentation"),
        label="slot-2 runtime instrumentation",
    )
    ancestor = _string(
        instrumentation.get("reviewed_implementation_ancestor"),
        label="slot-2 reviewed implementation ancestor",
    )
    raw_files = _list(
        instrumentation.get("files"),
        label="slot-2 runtime instrumentation files",
    )
    files: list[dict[str, str]] = []
    for raw in raw_files:
        item = _mapping(raw, label="slot-2 runtime instrumentation file")
        relative = _string(item.get("path"), label="slot-2 instrumentation path")
        expected_sha256 = _string(item.get("sha256"), label="slot-2 instrumentation SHA-256")
        if (
            Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or _HEX64.fullmatch(expected_sha256) is None
            or hashlib.sha256(_git_blob(repository, ancestor, relative)).hexdigest()
            != expected_sha256
        ):
            raise T09ProviderError("slot-2 runtime instrumentation binding drifted")
        files.append({"path": relative, "sha256": expected_sha256})
    commands = _mapping(commands_raw, label="slot-2 command manifests")
    raw_manifests = _list(commands.get("manifests"), label="slot-2 command manifests")
    environment_hashes: set[str] = set()
    giclab_commits: set[str] = set()
    for raw in raw_manifests:
        manifest = _mapping(raw, label="slot-2 command manifest")
        equality = _mapping(manifest.get("equality_surface"), label="slot-2 equality surface")
        environment_hashes.add(
            _string(equality.get("environment_sha256"), label="slot-2 environment SHA-256")
        )
        giclab_commits.add(_string(equality.get("giclab_commit"), label="slot-2 GIC Lab commit"))
    runtime_sha256 = hashlib.sha256(runtime_bytes).hexdigest()
    if (
        len(raw_manifests) != 4
        or environment_hashes != {runtime_sha256}
        or giclab_commits != {ancestor}
        or commands.get("reviewed_implementation_ancestor") != ancestor
    ):
        raise T09ProviderError("slot-2 command/runtime control binding drifted")
    return {
        "runtime_identity_sha256": runtime_sha256,
        "reviewed_implementation_ancestor": ancestor,
        "instrumentation_files": files,
        "instrumentation_files_sha256": _sha256_bytes(_canonical_bytes(files)),
        "command_environment_sha256": runtime_sha256,
        "command_giclab_commit": ancestor,
    }


def _source_bound_slot2_git_transition(
    repository: Path,
    package_commit: str,
    *,
    from_package_commit: str,
    plan_sha256: str,
    allowed_paths: frozenset[str],
    required_changed_paths: frozenset[str],
) -> dict[str, object]:
    if _HEX40.fullmatch(package_commit) is None:
        raise T09ProviderError("slot-2 package commit is malformed")
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            from_package_commit,
            package_commit,
        ],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if ancestry.returncode != 0:
        raise T09ProviderError("slot-2 package is not a descendant of the launched package")
    changed_result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "diff",
            "--name-status",
            "--no-renames",
            from_package_commit,
            package_commit,
        ],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=60,
    )
    changed_lines = [line for line in changed_result.stdout.decode().splitlines() if line]
    if not changed_lines or any("\t" not in line for line in changed_lines):
        raise T09ProviderError("slot-2 package transition is empty or malformed")
    statuses_and_paths = [line.split("\t", 1) for line in changed_lines]
    changed_paths = sorted(path for _status, path in statuses_and_paths)
    if (
        any(status not in {"A", "M"} for status, _path in statuses_and_paths)
        or not set(changed_paths).issubset(allowed_paths)
        or not required_changed_paths.issubset(changed_paths)
    ):
        raise T09ProviderError("slot-2 package changed a non-allowlisted control surface")
    previous_science = _slot2_science_projection(
        repository,
        from_package_commit,
        expected_plan_sha256=plan_sha256,
    )
    current_science = _slot2_science_projection(
        repository,
        package_commit,
        expected_plan_sha256=plan_sha256,
    )
    if previous_science != current_science:
        raise T09ProviderError("slot-2 package changed the scientific execution projection")
    previous_runtime_control = _slot2_runtime_control_projection(repository, from_package_commit)
    current_runtime_control = _slot2_runtime_control_projection(repository, package_commit)
    binary_diff = subprocess.run(
        ["git", "-C", str(repository), "diff", "--binary", from_package_commit, package_commit],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    return {
        "from_package_commit": from_package_commit,
        "to_package_commit": package_commit,
        "from_package_is_ancestor": True,
        "to_package_tree": subprocess.run(
            ["git", "-C", str(repository), "rev-parse", f"{package_commit}^{{tree}}"],
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
            timeout=30,
        )
        .stdout.decode()
        .strip(),
        "changed_paths": changed_paths,
        "changed_paths_sha256": _sha256_bytes(_canonical_bytes(changed_paths)),
        "binary_diff_sha256": hashlib.sha256(binary_diff).hexdigest(),
        "scientific_projection_sha256": _sha256_bytes(_canonical_bytes(current_science)),
        "scientific_contract_changed": False,
        "control_runtime_transition": {
            "previous": previous_runtime_control,
            "current": current_runtime_control,
        },
        "control_runtime_transition_sha256": _sha256_bytes(
            _canonical_bytes(
                {
                    "previous": previous_runtime_control,
                    "current": current_runtime_control,
                }
            )
        ),
    }


def _slot2_git_transition(repository: Path, package_commit: str) -> dict[str, object]:
    """Reconstruct the archived Retry 3 slot transition."""

    return _source_bound_slot2_git_transition(
        repository,
        package_commit,
        from_package_commit=SLOT1_PACKAGE_COMMIT,
        plan_sha256=SLOT1_PLAN_SHA256,
        allowed_paths=SLOT2_TRANSITION_ALLOWED_PATHS,
        required_changed_paths=frozenset(
            {
                "containers/sira-smoke/pragmatic/t09_remote_runner.py",
                "src/giclab/harness/t09_pragmatic_provider.py",
            }
        ),
    )


def _retry4_slot2_git_transition(repository: Path, package_commit: str) -> dict[str, object]:
    """Bind the focused V6 pre-entry repair without changing frozen science."""

    return _source_bound_slot2_git_transition(
        repository,
        package_commit,
        from_package_commit=RETRY4_SLOT1_PACKAGE_COMMIT,
        plan_sha256=RETRY4_SLOT1_PLAN_SHA256,
        allowed_paths=RETRY4_SLOT2_TRANSITION_ALLOWED_PATHS,
        required_changed_paths=frozenset(
            {
                "containers/sira-smoke/pragmatic/t09_remote_runner.py",
                "src/giclab/harness/sira_gate_a_runtime.py",
                "src/giclab/harness/t09_pragmatic_provider.py",
            }
        ),
    )


def retry4_active_slot2_entry_transition(
    repository: Path, package_commit: str
) -> dict[str, object]:
    """Bind a focused pre-entry repair after the already-consumed slot-2 POST.

    The provider receipt remains validated under the exact package that issued
    the POST.  This transition proves that the host package is a clean,
    science-invariant descendant whose changes stay inside the previously
    reviewed Retry 4 control surface.
    """

    return _source_bound_slot2_git_transition(
        repository,
        package_commit,
        from_package_commit=RETRY4_ACTIVE_SLOT2_ENTRY_PACKAGE_COMMIT,
        plan_sha256=RETRY4_SLOT1_PLAN_SHA256,
        allowed_paths=RETRY4_SLOT2_TRANSITION_ALLOWED_PATHS,
        required_changed_paths=frozenset(
            {
                "containers/sira-smoke/pragmatic/t09_remote_runner.py",
                "src/giclab/harness/t09_pragmatic_provider.py",
                "src/giclab/harness/t09_sira_pilot.py",
            }
        ),
    )


def retry5_closed_slot1_package_transition(
    repository: Path, package_commit: str
) -> dict[str, object]:
    """Bind the focused V7 preflight repair after launch slot 1 closed.

    Slot 1 was issued by the immutable package named below and terminated with
    zero empirical/model/browser use.  Slot 2 may use a clean descendant only
    when the diff stays on this exact control surface and the projected science
    is byte-equivalent.
    """

    return _source_bound_slot2_git_transition(
        repository,
        package_commit,
        from_package_commit=RETRY5_ACTIVE_SLOT1_PACKAGE_COMMIT,
        plan_sha256=RETRY5_ACTIVE_SLOT1_PLAN_SHA256,
        allowed_paths=RETRY5_SLOT2_TRANSITION_ALLOWED_PATHS,
        required_changed_paths=frozenset(
            {
                "containers/sira-smoke/pragmatic/t09_remote_runner.py",
                "src/giclab/harness/t09_pragmatic_provider.py",
            }
        ),
    )


def autonomous_preflight_package_transition(
    repository: Path,
    *,
    contract: T09ProviderContract,
    from_package_commit: str,
    to_package_commit: str,
) -> dict[str, object]:
    """Bind one current-turn clean descendant without granting scientific drift.

    The immutable authorization source governs the whole pre-empirical engineering
    session.  Package commits may advance, but only along one Git ancestry and only
    while the selected version's typed science package and primary inputs remain
    identical.
    """

    if (
        contract.version not in {"V8", "V9", "V10", "V11"}
        or contract.execution_contract_path is None
        or contract.command_manifest_path is None
        or _HEX40.fullmatch(from_package_commit) is None
        or _HEX40.fullmatch(to_package_commit) is None
        or from_package_commit == to_package_commit
    ):
        raise T09ProviderError("autonomous package transition identity is invalid")
    _verify_clean_package(repository, to_package_commit)
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            from_package_commit,
            to_package_commit,
        ],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    if ancestry.returncode != 0:
        raise T09ProviderError("autonomous package is not a descendant of its launch package")
    changed = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "diff",
            "--name-status",
            "--no-renames",
            from_package_commit,
            to_package_commit,
        ],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=60,
    )
    lines = [line for line in changed.stdout.decode().splitlines() if line]
    if not lines or any("\t" not in line for line in lines):
        raise T09ProviderError("autonomous package transition is empty or malformed")
    statuses_and_paths = [line.split("\t", 1) for line in lines]
    changed_paths = sorted(path for _status, path in statuses_and_paths)
    if any(status not in {"A", "M"} for status, _path in statuses_and_paths):
        raise T09ProviderError("autonomous package transition deleted or renamed tracked state")

    immutable_paths = tuple(
        path
        for path in (
            contract.science_projection_path,
            "experiments/EXP-0001-sira-simulative-vs-reactive/protocol.yaml",
            "experiments/EXP-0001-sira-simulative-vs-reactive/config.yaml",
            "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
            "T09_PILOT_DATASET_CONTRACT.json",
            "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
            "T09_PILOT_EVALUATOR_CONTRACT.json",
            "src/giclab/harness/sira_gate_a.py",
            "src/giclab/harness/safety.py",
        )
        if path is not None
    )
    previous = {
        path: hashlib.sha256(_git_blob(repository, from_package_commit, path)).hexdigest()
        for path in immutable_paths
    }
    current = {
        path: hashlib.sha256(_git_blob(repository, to_package_commit, path)).hexdigest()
        for path in immutable_paths
    }
    if previous != current:
        raise T09ProviderError("autonomous package transition changed frozen science")
    previous_science = _autonomous_package_science_state(
        repository,
        from_package_commit,
        contract=contract,
        stale_command_authorization_sha256s=(
            AUTONOMOUS_V9_STALE_COMMAND_AUTHORIZATION_SHA256S
            if contract.version == "V9"
            and from_package_commit == AUTONOMOUS_V9_LAUNCH_PACKAGE_COMMIT
            else None
        ),
    )
    current_science = _autonomous_package_science_state(
        repository,
        to_package_commit,
        contract=contract,
    )
    if previous_science != current_science:
        raise T09ProviderError("autonomous package transition changed derived science")
    binary_diff = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "diff",
            "--binary",
            from_package_commit,
            to_package_commit,
        ],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    return {
        "transition_kind": "authorized-autonomous-preempirical-clean-descendant-v1",
        "authorization_source_sha256": contract.authorization_source_sha256,
        "provider_contract_version": contract.version,
        "from_package_commit": from_package_commit,
        "to_package_commit": to_package_commit,
        "from_package_is_ancestor": True,
        "to_package_tree": subprocess.run(
            ["git", "-C", str(repository), "rev-parse", f"{to_package_commit}^{{tree}}"],
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
            timeout=30,
        )
        .stdout.decode()
        .strip(),
        "changed_paths": changed_paths,
        "changed_paths_sha256": _sha256_bytes(_canonical_bytes(changed_paths)),
        "binary_diff_sha256": hashlib.sha256(binary_diff).hexdigest(),
        "scientific_projection_sha256": (
            previous[contract.science_projection_path]
            if contract.science_projection_path is not None
            else _sha256_bytes(_canonical_bytes(previous_science))
        ),
        "derived_science_state_sha256": _sha256_bytes(_canonical_bytes(previous_science)),
        "scientific_contract_changed": False,
    }


def _git_json_object(repository: Path, commit: str, path: str) -> dict[str, object]:
    try:
        value = json.loads(_git_blob(repository, commit, path))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise T09ProviderError(f"autonomous package JSON is malformed: {path}") from exc
    if not isinstance(value, dict):
        raise T09ProviderError(f"autonomous package JSON is not an object: {path}")
    return cast(dict[str, object], value)


def _json_value_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _derived_science_projection(execution: Mapping[str, object]) -> dict[str, object]:
    raw_attempts = execution.get("attempts")
    if not isinstance(raw_attempts, list) or len(raw_attempts) != 4:
        raise T09ProviderError("autonomous execution contract must contain four attempts")
    attempts: list[dict[str, object]] = []
    for raw in raw_attempts:
        if not isinstance(raw, dict):
            raise T09ProviderError("autonomous execution attempt is malformed")
        argv = raw.get("upstream_argv")
        if (
            not isinstance(argv, list)
            or len(argv) != 27
            or any(not isinstance(item, str) for item in argv)
            or argv.count("--output_dir") != 1
        ):
            raise T09ProviderError("autonomous execution argv is incomplete")
        normalized_argv = list(argv)
        normalized_argv[0] = "<FRESH-UPSTREAM-RUN-ID>"
        output_index = normalized_argv.index("--output_dir") + 1
        if output_index >= len(normalized_argv):
            raise T09ProviderError("autonomous execution output flag is orphaned")
        normalized_argv[output_index] = "<FRESH-OUTPUT-ROOT>"
        attempts.append(
            {
                "task_id": raw.get("task_id"),
                "task_index": raw.get("task_index"),
                "condition": raw.get("condition"),
                "order_index": raw.get("order_index"),
                "protocol_sha256": raw.get("protocol_sha256"),
                "config_sha256": raw.get("config_sha256"),
                "upstream_argv": normalized_argv,
            }
        )
    bindings = execution.get("contract_bindings")
    if not isinstance(bindings, dict):
        raise T09ProviderError("autonomous execution bindings are malformed")
    return {
        "experiment_id": execution.get("experiment_id"),
        "sira_commit": execution.get("sira_commit"),
        "model_revision": execution.get("model_revision"),
        "service_tier": execution.get("service_tier"),
        "randomization_seed": execution.get("randomization_seed"),
        "dataset_binding": bindings.get("dataset"),
        "evaluator_binding": bindings.get("evaluator"),
        "attempts": attempts,
    }


def _condition_science_projection(document: Mapping[str, object]) -> dict[str, object]:
    sources = document.get("sources")
    task = document.get("task")
    pairing = document.get("pairing")
    budget = document.get("budget")
    execution = document.get("execution")
    if not all(isinstance(item, dict) for item in (sources, task, pairing, budget, execution)):
        raise T09ProviderError("autonomous condition science surface is malformed")
    assert isinstance(sources, dict)
    assert isinstance(task, dict)
    assert isinstance(pairing, dict)
    assert isinstance(budget, dict)
    assert isinstance(execution, dict)
    return {
        "experiment_id": document.get("experiment_id"),
        "condition": document.get("condition"),
        "seed": document.get("seed"),
        "interpretation_allowed": document.get("interpretation_allowed"),
        "execution": {
            "workload": execution.get("workload"),
        },
        "sources": {
            key: sources.get(key)
            for key in (
                "upstream_source_id",
                "upstream_commit",
                "protocol_sha256",
                "config_sha256",
                "model_revision",
                "dataset_revision",
            )
        },
        "task": task,
        "pairing": {
            "order_index": pairing.get("order_index"),
        },
        "budget": {
            key: budget.get(key)
            for key in (
                "max_wall_seconds",
                "max_cost_usd",
                "max_gpu_hours",
                "max_model_calls",
                "max_model_tokens",
                "max_tool_calls",
            )
        },
    }


def _normalized_pair_argv(argv: list[str]) -> dict[str, str]:
    if len(argv) != 27 or len(argv[1:]) % 2 != 0:
        raise T09ProviderError("autonomous pair argv shape is malformed")
    values: dict[str, str] = {}
    for index in range(1, len(argv), 2):
        flag = argv[index]
        if not flag.startswith("--") or flag in values:
            raise T09ProviderError("autonomous pair argv flags are malformed")
        values[flag] = argv[index + 1]
    for permitted in ("--mode", "--config_name", "--output_dir"):
        values.pop(permitted, None)
    return values


def _autonomous_package_science_state(
    repository: Path,
    commit: str,
    *,
    contract: T09ProviderContract,
    stale_command_authorization_sha256s: Mapping[str, str] | None = None,
) -> dict[str, object]:
    execution_path = contract.execution_contract_path
    commands_path = contract.command_manifest_path
    if execution_path is None or commands_path is None:
        raise T09ProviderError("provider contract has no autonomous scientific package")
    execution_blob = _git_blob(repository, commit, execution_path)
    execution = _git_json_object(repository, commit, execution_path)
    derived_projection = _derived_science_projection(execution)
    if contract.science_projection_path is not None:
        stored_projection = _git_json_object(
            repository,
            commit,
            contract.science_projection_path,
        )
        if stored_projection != derived_projection:
            raise T09ProviderError(
                "autonomous stored science projection is stale relative to execution"
            )
    bindings = execution.get("contract_bindings")
    raw_attempts = execution.get("attempts")
    if (
        execution.get("plan_id") != contract.plan_id
        or not isinstance(bindings, dict)
        or not isinstance(raw_attempts, list)
        or tuple(
            attempt.get("run_id") if isinstance(attempt, dict) else None for attempt in raw_attempts
        )
        != contract.run_ids
    ):
        raise T09ProviderError("autonomous execution package is malformed")
    for name in ("dataset", "evaluator"):
        binding = bindings.get(name)
        if not isinstance(binding, dict):
            raise T09ProviderError(f"autonomous {name} binding is malformed")
        path = binding.get("path")
        digest = binding.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or hashlib.sha256(_git_blob(repository, commit, path)).hexdigest() != digest
        ):
            raise T09ProviderError(f"autonomous {name} binding drifted")

    condition_science: list[dict[str, object]] = []
    condition_digests: list[str] = []
    for raw_attempt in raw_attempts:
        if not isinstance(raw_attempt, dict):
            raise T09ProviderError("autonomous execution attempt is malformed")
        condition_path = raw_attempt.get("condition_plan_path")
        condition_sha256 = raw_attempt.get("condition_plan_sha256")
        if not isinstance(condition_path, str) or not isinstance(condition_sha256, str):
            raise T09ProviderError("autonomous condition binding is malformed")
        condition_blob = _git_blob(repository, commit, condition_path)
        if hashlib.sha256(condition_blob).hexdigest() != condition_sha256:
            raise T09ProviderError("autonomous condition binding drifted")
        condition = yaml.safe_load(condition_blob)
        if not isinstance(condition, dict):
            raise T09ProviderError("autonomous condition plan is malformed")
        authorization = condition.get("execution", {}).get("authorization")
        argv = raw_attempt.get("upstream_argv")
        run_id = raw_attempt.get("run_id")
        retained_command_sha256 = (
            authorization.get("command_sha256") if isinstance(authorization, dict) else None
        )
        command_authorization_valid = retained_command_sha256 == _json_value_sha256(argv)
        exact_launch_package_exception = (
            stale_command_authorization_sha256s is not None
            and isinstance(run_id, str)
            and stale_command_authorization_sha256s.get(run_id) == retained_command_sha256
        )
        if (
            not isinstance(authorization, dict)
            or not isinstance(argv, list)
            or run_id not in contract.run_ids
            or condition.get("run_id") != run_id
            or condition.get("profile_plan_id") != contract.plan_id
            or not (command_authorization_valid or exact_launch_package_exception)
            or condition.get("condition") != f"SIRA-{str(raw_attempt.get('condition')).upper()}"
            or condition.get("task", {}).get("task_id") != raw_attempt.get("task_id")
            or condition.get("pairing", {}).get("order_index") != raw_attempt.get("order_index")
        ):
            raise T09ProviderError("autonomous condition does not match its execution attempt")
        projected = _condition_science_projection(condition)
        condition_science.append(projected)
        condition_digests.append(_sha256_bytes(_canonical_bytes(projected)))

    commands = _git_json_object(repository, commit, commands_path)
    raw_manifests = commands.get("manifests")
    raw_pair_diffs = commands.get("pair_diffs")
    execution_sha256 = hashlib.sha256(execution_blob).hexdigest()
    if (
        commands.get("plan_id") != contract.plan_id
        or not isinstance(raw_manifests, list)
        or len(raw_manifests) != 4
        or tuple(
            manifest.get("run_id") if isinstance(manifest, dict) else None
            for manifest in raw_manifests
        )
        != contract.run_ids
        or not isinstance(raw_pair_diffs, list)
        or len(raw_pair_diffs) != 2
        or commands.get("execution_contract_sha256") != execution_sha256
    ):
        raise T09ProviderError("autonomous command package is malformed")
    upstream_vectors: list[list[str]] = []
    equality_surfaces: list[dict[str, object]] = []
    for raw_attempt, manifest in zip(raw_attempts, raw_manifests, strict=True):
        if not isinstance(raw_attempt, dict) or not isinstance(manifest, dict):
            raise T09ProviderError("autonomous command manifest is malformed")
        argv = manifest.get("argv")
        upstream = raw_attempt.get("upstream_argv")
        equality = manifest.get("equality_surface")
        if (
            not isinstance(argv, list)
            or any(not isinstance(item, str) for item in argv)
            or argv.count("--") != 1
            or not isinstance(upstream, list)
            or argv[argv.index("--") + 1 :] != upstream
            or manifest.get("argv_sha256") != _json_value_sha256(argv)
            or manifest.get("execution_contract_sha256") != execution_sha256
            or manifest.get("run_id") != raw_attempt.get("run_id")
            or manifest.get("task_id") != raw_attempt.get("task_id")
            or manifest.get("condition") != raw_attempt.get("condition")
            or manifest.get("order_index") != raw_attempt.get("order_index")
            or manifest.get("pair_id") != raw_attempt.get("pair_id")
            or manifest.get("condition_plan_path") != raw_attempt.get("condition_plan_path")
            or manifest.get("condition_plan_sha256") != raw_attempt.get("condition_plan_sha256")
            or not isinstance(equality, dict)
        ):
            raise T09ProviderError("autonomous command manifest drifted from execution")
        upstream_vectors.append(cast(list[str], upstream))
        equality_surfaces.append(cast(dict[str, object], equality))
    for pair_index, (left, right) in enumerate(((0, 1), (2, 3))):
        pair_diff = raw_pair_diffs[pair_index]
        if (
            equality_surfaces[left] != equality_surfaces[right]
            or raw_attempts[left].get("task_id") != raw_attempts[right].get("task_id")
            or _normalized_pair_argv(upstream_vectors[left])
            != _normalized_pair_argv(upstream_vectors[right])
            or not isinstance(pair_diff, dict)
            or pair_diff.get("valid") is not True
            or pair_diff.get("required_equality_surface_equal") is not True
            or pair_diff.get("normalized_actual_argv_equal") is not True
            or pair_diff.get("task_id_equal") is not True
        ):
            raise T09ProviderError("autonomous command pair diff is not independently valid")
    return {
        "derived_science_projection": derived_projection,
        "condition_science_sha256s": condition_digests,
        "command_upstream_argv_sha256s": [_json_value_sha256(argv) for argv in upstream_vectors],
    }


def _safe_regular_identity(path: Path, *, expected_bytes: int, expected_sha256: str) -> None:
    resolved = path.resolve(strict=True)
    metadata = resolved.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_size != expected_bytes
        or file_sha256(resolved) != expected_sha256
    ):
        raise T09ProviderError("slot-1 retained archive identity or metadata drifted")


def _slot1_failure_archive_projection(path: Path) -> dict[str, object]:
    _safe_regular_identity(
        path,
        expected_bytes=SLOT1_ZERO_USE_ARCHIVE_BYTES,
        expected_sha256=SLOT1_ZERO_USE_ARCHIVE_SHA256,
    )
    prefix = "t09-pilot-v5/pilot-v5/"
    required = {
        "pilot-state.json",
        "aggregate-budget.json",
        "provider-entry.json",
        "host-cleanup.json",
        "replacement-image-qualification/receipt.json",
        "preempirical-slot1-files-v2.sha256",
    }
    documents: dict[str, dict[str, object]] = {}
    members_seen: set[str] = set()
    total = 0
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if not 1 <= len(members) <= 1_000:
            raise T09ProviderError("slot-1 failure archive member count is unsafe")
        for member in members:
            pure = Path(member.name)
            if pure.is_absolute() or ".." in pure.parts or not (member.isfile() or member.isdir()):
                raise T09ProviderError("slot-1 failure archive contains an unsafe member")
            if member.isfile():
                total += member.size
                if total > 67_108_864:
                    raise T09ProviderError("slot-1 failure archive expands beyond its cap")
            if member.name.startswith(prefix) and member.isfile():
                relative = member.name[len(prefix) :]
                members_seen.add(relative)
                if relative in required - {"preempirical-slot1-files-v2.sha256"}:
                    handle = archive.extractfile(member)
                    if handle is None or member.size > 1_048_576:
                        raise T09ProviderError("slot-1 failure document is unavailable")
                    try:
                        raw: object = json.loads(handle.read())
                    except json.JSONDecodeError as exc:
                        raise T09ProviderError("slot-1 failure document is malformed") from exc
                    documents[relative] = _mapping(raw, label="slot-1 failure document")
    if not required.issubset(members_seen):
        raise T09ProviderError("slot-1 failure archive lacks its exact zero-use closure")
    state = documents["pilot-state.json"]
    aggregate = documents["aggregate-budget.json"]
    cleanup = documents["host-cleanup.json"]
    materialization = documents["replacement-image-qualification/receipt.json"]
    provider_entry = documents["provider-entry.json"]
    usage = _mapping(aggregate.get("usage"), label="slot-1 aggregate usage")
    if (
        state.get("plan_id") != RETRY4_PLAN_ID
        or state.get("empirical_attempts_entered") != []
        or state.get("raw_attempts_complete") != []
        or state.get("attempts_completed") != []
        or state.get("first_pair_decision") is not None
        or aggregate.get("unreconciled_provider_attempts") != 0
        or any(value not in (0, 0.0) for value in usage.values())
        or cleanup.get("global_secret_scan_passed") is not True
        or cleanup.get("remote_secret_removed") is not True
        or cleanup.get("owned_container_residue") != []
        or materialization.get("qualification_id") != SLOT1_QUALIFICATION_ID
        or materialization.get("image_id") != SLOT1_REPLACEMENT_IMAGE_ID
        or materialization.get("build_count") != 1
        or provider_entry.get("package_commit") != SLOT1_PACKAGE_COMMIT
        or provider_entry.get("receipt_sha256")
        != "5f813865ff758f6e1ab31de2194cd3b94282d9a2eddfb9a21cf513880d41b272"
        or "frozen-run-manifest.json" in members_seen
        or "preflight.json" in members_seen
        or any(name.startswith("model-metadata-preflight/") for name in members_seen)
        or any(name.startswith("browser-preflight/") for name in members_seen)
        or any(name.startswith("artifacts/") for name in members_seen)
    ):
        raise T09ProviderError("slot-1 failure archive is not source-grounded zero-use")
    return {
        "archive_sha256": SLOT1_ZERO_USE_ARCHIVE_SHA256,
        "archive_bytes": SLOT1_ZERO_USE_ARCHIVE_BYTES,
        "expanded_bytes": total,
        "member_count": len(members_seen),
        "qualification_id": SLOT1_QUALIFICATION_ID,
        "replacement_image_id": SLOT1_REPLACEMENT_IMAGE_ID,
        "candidate_build_attempt_count": 1,
        "empirical_attempts_entered": 0,
        "model_metadata_requests": 0,
        "task_model_requests": 0,
        "task_browser_actions": 0,
        "raw_attempts_complete": 0,
        "attempts_completed": 0,
        "credentials_removed": True,
        "owned_containers_absent": True,
    }


def _retry4_slot1_failure_archive_projection(path: Path) -> dict[str, object]:
    """Reconstruct the exact V6 post-freeze, pre-entry failure stage."""

    _safe_regular_identity(
        path,
        expected_bytes=RETRY4_SLOT1_FAILURE_ARCHIVE_BYTES,
        expected_sha256=RETRY4_SLOT1_FAILURE_ARCHIVE_SHA256,
    )
    manifest_name = "pilot-v6/evidence-stage-manifest.json"
    document_names = {
        "state": "pilot-v6/pilot-state.json",
        "aggregate": "pilot-v6/aggregate-budget.json",
        "frozen": "pilot-v6/frozen-run-manifest.json",
        "postfreeze": "pilot-v6/postfreeze-validation.json",
        "preflight": "pilot-v6/preflight.json",
        "cleanup": "pilot-v6/host-cleanup.json",
        "materialization": "pilot-v6/replacement-image-qualification/receipt.json",
        "metadata_scan": "pilot-v6/model-metadata-credential-scan.json",
        "failure": (
            "artifacts/EXP-0001/pilot-v6/task-a/reactive/attempt-0004/"
            "preentry-condition-failure.json"
        ),
    }
    documents: dict[str, dict[str, object]] = {}
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if not 1 <= len(members) <= 1_000:
            raise T09ProviderError("Retry 4 slot-1 archive member count is unsafe")
        names: set[str] = set()
        member_by_name: dict[str, tarfile.TarInfo] = {}
        expanded_bytes = 0
        for member in members:
            pure = Path(member.name)
            if (
                member.name in names
                or pure.is_absolute()
                or ".." in pure.parts
                or not (member.isfile() or member.isdir())
            ):
                raise T09ProviderError("Retry 4 slot-1 archive contains an unsafe member")
            names.add(member.name)
            member_by_name[member.name] = member
            if member.isfile():
                expanded_bytes += member.size
                if member.size > 16_777_216 or expanded_bytes > 33_554_432:
                    raise T09ProviderError("Retry 4 slot-1 archive expands beyond its cap")
        manifest_member = member_by_name.get(manifest_name)
        if manifest_member is None or not manifest_member.isfile():
            raise T09ProviderError("Retry 4 slot-1 archive lacks its stage manifest")
        manifest_handle = archive.extractfile(manifest_member)
        if manifest_handle is None:
            raise T09ProviderError("Retry 4 slot-1 stage manifest is unavailable")
        try:
            manifest_raw: object = json.loads(manifest_handle.read())
        except json.JSONDecodeError as exc:
            raise T09ProviderError("Retry 4 slot-1 stage manifest is malformed") from exc
        manifest = _mapping(manifest_raw, label="Retry 4 slot-1 stage manifest")
        raw_files = _list(manifest.get("files"), label="Retry 4 slot-1 stage files")
        expected_files: dict[str, tuple[int, str]] = {}
        for raw in raw_files:
            item = _mapping(raw, label="Retry 4 slot-1 staged file")
            relative = _string(item.get("path"), label="Retry 4 staged path")
            expected_bytes = _integer(item.get("bytes"), label="Retry 4 staged bytes")
            expected_sha256 = _string(item.get("sha256"), label="Retry 4 staged SHA-256")
            if (
                relative in expected_files
                or Path(relative).is_absolute()
                or ".." in Path(relative).parts
                or expected_bytes < 0
                or _HEX64.fullmatch(expected_sha256) is None
            ):
                raise T09ProviderError("Retry 4 stage manifest has an unsafe file binding")
            expected_files[relative] = (expected_bytes, expected_sha256)
        archive_files = {name for name, member in member_by_name.items() if member.isfile()}
        if archive_files != {*expected_files, manifest_name}:
            raise T09ProviderError("Retry 4 stage manifest does not cover the exact archive")
        actual_total = 0
        wanted = {value: key for key, value in document_names.items()}
        for relative, (expected_bytes, expected_sha256) in expected_files.items():
            member = member_by_name[relative]
            handle = archive.extractfile(member)
            if handle is None:
                raise T09ProviderError("Retry 4 staged evidence member is unavailable")
            payload = handle.read()
            actual_total += len(payload)
            if (
                len(payload) != expected_bytes
                or hashlib.sha256(payload).hexdigest() != expected_sha256
            ):
                raise T09ProviderError("Retry 4 staged evidence member drifted")
            label = wanted.get(relative)
            if label is not None:
                try:
                    raw_document: object = json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise T09ProviderError("Retry 4 staged control document is malformed") from exc
                documents[label] = _mapping(
                    raw_document,
                    label=f"Retry 4 staged {label}",
                )
    if set(documents) != set(document_names):
        raise T09ProviderError("Retry 4 slot-1 archive lacks its control closure")
    if (
        manifest.get("schema_version") != "0.1.0"
        or manifest.get("archive_id") != "ARCHIVE-EXP0001-PILOT-V6-0004"
        or manifest.get("stage_id") != "STAGE-EXP0001-PILOT-V6-0004"
        or manifest.get("frozen_run_manifest_id") != "RUN-MANIFEST-EXP0001-PILOT-V6-0004"
        or manifest.get("frozen_run_manifest_sha256") != RETRY4_SLOT1_FROZEN_MANIFEST_SHA256
        or manifest.get("private_access_controlled") is not True
        or manifest.get("provider_closeout_pending") is not True
        or manifest.get("secret_scan_passed") is not True
        or manifest.get("total_bytes") != actual_total
    ):
        raise T09ProviderError("Retry 4 slot-1 stage disposition drifted")
    state = documents["state"]
    aggregate = documents["aggregate"]
    frozen = documents["frozen"]
    postfreeze = documents["postfreeze"]
    preflight = documents["preflight"]
    cleanup = documents["cleanup"]
    materialization = documents["materialization"]
    metadata_scan = documents["metadata_scan"]
    failure = documents["failure"]
    usage = _mapping(aggregate.get("usage"), label="Retry 4 slot-1 aggregate usage")
    raw_failure_entries = _list(
        failure.get("failure_prefix_entries"),
        label="Retry 4 pre-entry failure entries",
    )
    failure_entries = [
        _mapping(item, label="Retry 4 pre-entry failure entry") for item in raw_failure_entries
    ]
    condition_stderr = [
        item for item in failure_entries if item.get("path") == "raw/condition.stderr"
    ]
    pair_diffs = _list(frozen.get("pair_diffs"), label="Retry 4 frozen pair diffs")
    if (
        state.get("plan_id") != RETRY4_PLAN_ID
        or state.get("execution_contract_sha256") != RETRY4_SLOT1_EXECUTION_SHA256
        or state.get("launch_slot") != 1
        or state.get("launch_count") != 1
        or state.get("empirical_attempts_entered") != []
        or state.get("raw_attempts_complete") != []
        or state.get("attempts_completed") != []
        or state.get("raw_attempt_bindings") != {}
        or state.get("attempt_finalizations") != {}
        or state.get("attempt_finalization_history") != {}
        or state.get("first_pair_decision") is not None
        or state.get("actual_credential_exposure_detected") is not False
        or state.get("credential_safety_stop_detected") is not False
        or aggregate.get("plan_id") != RETRY4_PLAN_ID
        or aggregate.get("execution_contract_sha256") != RETRY4_SLOT1_EXECUTION_SHA256
        or aggregate.get("unreconciled_provider_attempts") != 0
        or any(value not in (0, 0.0) for value in usage.values())
        or frozen.get("plan_id") != RETRY4_PLAN_ID
        or frozen.get("host_run_id") != RETRY4_HOST_RUN_ID
        or frozen.get("clean_package_commit") != RETRY4_SLOT1_PACKAGE_COMMIT
        or frozen.get("plan_sha256") != RETRY4_SLOT1_PLAN_SHA256
        or frozen.get("execution_contract_sha256") != RETRY4_SLOT1_EXECUTION_SHA256
        or frozen.get("runtime_contract_sha256") != RETRY4_SLOT1_RUNTIME_SHA256
        or frozen.get("command_manifests_sha256") != RETRY4_SLOT1_COMMANDS_SHA256
        or frozen.get("provider_entry_receipt_sha256") != RETRY4_SLOT1_ENTRY_RECEIPT_SHA256
        or frozen.get("source_contract_sha256") != RETRY4_AUTHORIZATION_SOURCE_SHA256
        or frozen.get("launch_slot") != 1
        or frozen.get("launch_count") != 1
        or frozen.get("qualification_id") != "QUAL-T09-PILOT-V6-IMAGE-0001"
        or frozen.get("replacement_image_id") != RETRY4_SLOT1_BUILT_IMAGE_ID
        or frozen.get("build_count") != 1
        or frozen.get("image_import_count") != 0
        or frozen.get("additional_build_count") != 0
        or frozen.get("empirical_entry_crossed") is not False
        or frozen.get("model_metadata_request_count") != 1
        or frozen.get("model_task_request_count") != 0
        or frozen.get("task_browser_action_count") != 0
        or frozen.get("actual_credential_exposure_detected") is not False
        or frozen.get("credential_safety_stop_detected") is not False
        or len(pair_diffs) != 2
        or any(not isinstance(item, dict) or item.get("valid") is not True for item in pair_diffs)
        or expected_files["pilot-v6/frozen-run-manifest.json"][1]
        != RETRY4_SLOT1_FROZEN_MANIFEST_SHA256
        or expected_files["pilot-v6/postfreeze-validation.json"][1]
        != RETRY4_SLOT1_POSTFREEZE_SHA256
        or expected_files["pilot-v6/preflight.json"][1] != RETRY4_SLOT1_PREFLIGHT_SHA256
        or postfreeze.get("package_commit") != RETRY4_SLOT1_PACKAGE_COMMIT
        or postfreeze.get("frozen_run_manifest_sha256") != RETRY4_SLOT1_FROZEN_MANIFEST_SHA256
        or postfreeze.get("fresh_empirical_campaign_headroom_passed_before_metadata_get")
        is not True
        or postfreeze.get("model_metadata_request_count") != 1
        or postfreeze.get("model_task_request_count") != 0
        or postfreeze.get("task_browser_action_count") != 0
        or postfreeze.get("actual_credential_exposure_detected") is not False
        or preflight.get("clean_package_commit") != RETRY4_SLOT1_PACKAGE_COMMIT
        or preflight.get("frozen_run_manifest_sha256") != RETRY4_SLOT1_FROZEN_MANIFEST_SHA256
        or preflight.get("empirical_entry_crossed") is not False
        or preflight.get("model_metadata_request_count") != 1
        or preflight.get("model_task_request_count") != 0
        or cleanup.get("actual_credential_exposure_detected") is not False
        or cleanup.get("credential_safety_stop_detected") is not False
        or cleanup.get("global_secret_scan_passed") is not True
        or cleanup.get("global_secret_bearing_artifacts_removed") != []
        or cleanup.get("global_secret_matching_paths") != []
        or cleanup.get("remote_secret_removed") is not True
        or cleanup.get("owned_container_residue") != []
        or cleanup.get("qualified_runtime_image_removed") is not True
        or materialization.get("qualification_id") != "QUAL-T09-PILOT-V6-IMAGE-0001"
        or materialization.get("image_id") != RETRY4_SLOT1_BUILT_IMAGE_ID
        or materialization.get("build_count") != 1
        or materialization.get("image_import_count") != 0
        or materialization.get("additional_build_count") != 0
        or metadata_scan.get("actual_credential_exposure_detected") is not False
        or metadata_scan.get("exact_secret_scan_passed") is not True
        or metadata_scan.get("remaining_exact_secret_matches") != []
        or metadata_scan.get("secret_bearing_artifacts_removed") != []
        or failure.get("plan_id") != RETRY4_PLAN_ID
        or failure.get("host_run_id") != RETRY4_HOST_RUN_ID
        or failure.get("clean_package_commit") != RETRY4_SLOT1_PACKAGE_COMMIT
        or failure.get("execution_contract_sha256") != RETRY4_SLOT1_EXECUTION_SHA256
        or failure.get("run_id") != "RUN-T09-TASK-A-REACTIVE-0004"
        or failure.get("frozen_run_manifest_sha256") != RETRY4_SLOT1_FROZEN_MANIFEST_SHA256
        or failure.get("returncode") != 1
        or failure.get("reason")
        != "condition-runtime-ended-before-first-model-request-or-browser-action"
        or failure.get("empirical_entry_crossed") is not False
        or failure.get("attempt_identity_consumed") is not False
        or failure.get("retry_same_frozen_condition_permitted") is not True
        or failure.get("actual_credential_exposure_detected") is not False
        or failure.get("credential_cleanup_integrity_failure") is not False
        or failure.get("container_absent") is not True
        or failure.get("remaining_exact_secret_matches") != []
        or failure.get("secret_bearing_artifacts_removed") != []
        or failure.get("structural_privacy_violations") != []
        or len(condition_stderr) != 1
        or condition_stderr[0].get("sha256") != RETRY4_SLOT1_CONDITION_STDERR_SHA256
    ):
        raise T09ProviderError("Retry 4 slot-1 evidence is not a zero-use pre-entry failure")
    return {
        "archive_sha256": RETRY4_SLOT1_FAILURE_ARCHIVE_SHA256,
        "archive_bytes": RETRY4_SLOT1_FAILURE_ARCHIVE_BYTES,
        "expanded_bytes": expanded_bytes,
        "member_count": len(expected_files) + 1,
        "stage_files_sha256": _sha256_bytes(_canonical_bytes(raw_files)),
        "frozen_run_manifest_sha256": RETRY4_SLOT1_FROZEN_MANIFEST_SHA256,
        "postfreeze_validation_sha256": RETRY4_SLOT1_POSTFREEZE_SHA256,
        "preflight_sha256": RETRY4_SLOT1_PREFLIGHT_SHA256,
        "qualification_id": "QUAL-T09-PILOT-V6-IMAGE-0001",
        "slot1_built_image_id": RETRY4_SLOT1_BUILT_IMAGE_ID,
        "candidate_build_attempt_count": 1,
        "image_import_count": 0,
        "model_metadata_requests": 1,
        "task_model_requests": 0,
        "task_browser_actions": 0,
        "empirical_attempts_entered": 0,
        "raw_attempts_complete": 0,
        "attempts_completed": 0,
        "failed_attempt_run_id": "RUN-T09-TASK-A-REACTIVE-0004",
        "failed_attempt_identity_consumed": False,
        "preentry_retry_permitted": True,
        "condition_stderr_sha256": RETRY4_SLOT1_CONDITION_STDERR_SHA256,
        "credentials_clean": True,
        "owned_containers_absent": True,
    }


def _slot2_authority_tree_manifest(
    root: Path,
    *,
    contract: T09ProviderContract,
) -> dict[str, object]:
    files: list[dict[str, object]] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path == root / "source-manifest.json" or path.is_dir():
            continue
        metadata = path.stat(follow_symlinks=False)
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise T09ProviderError("slot-2 authority source contains an unsafe member")
        total += metadata.st_size
        if total > 67_108_864:
            raise T09ProviderError("slot-2 authority source exceeds its cap")
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": metadata.st_size,
                "sha256": file_sha256(path),
            }
        )
    if not files:
        raise T09ProviderError("slot-2 authority source is empty")
    return {
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "files": files,
        "file_count": len(files),
        "total_bytes": total,
        "files_sha256": _sha256_bytes(_canonical_bytes(files)),
    }


def _copy_slot2_authority_tree(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        metadata = path.stat(follow_symlinks=False)
        if path.is_symlink():
            raise T09ProviderError("slot-1 provider source contains a symlink")
        if path.is_dir():
            target.mkdir(mode=0o700, parents=True, exist_ok=True)
            continue
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise T09ProviderError("slot-1 provider source contains an unsafe file")
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open("rb") as source_handle, target.open("xb") as target_handle:
            shutil.copyfileobj(source_handle, target_handle, 1_048_576)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        target.chmod(0o600)


def _current_v7_slot2_authority_paths(
    root: Path,
) -> tuple[Path, Path, Path]:
    """Resolve direct slot-1 evidence or its normalized retained copy."""

    normalized = root / "slot2-eligibility-source"
    if normalized.is_dir():
        manifest_path = normalized / "source-manifest.json"
        observed = _load_json(manifest_path, maximum_bytes=1_048_576)
        expected = _slot2_authority_tree_manifest(normalized, contract=V7_PROVIDER_CONTRACT)
        if observed != expected:
            raise T09ProviderError("retained V7 slot-2 authority manifest drifted")
        return (
            normalized / "slot1-entry-source",
            normalized / "slot1-closeout-source",
            normalized / "slot1-preempirical-source",
        )
    return (
        root / "entry-source",
        root / "closeout-source",
        root / "preempirical-source",
    )


def _retain_current_v7_slot2_authority(source_root: Path, destination_root: Path) -> None:
    """Copy the closed slot-1 source without colliding with the new entry root."""

    entry, closeout, preempirical = _current_v7_slot2_authority_paths(source_root)
    destination_root.mkdir(mode=0o700, exist_ok=False)
    for source, relative in (
        (entry, "slot1-entry-source"),
        (closeout, "slot1-closeout-source"),
        (preempirical, "slot1-preempirical-source"),
    ):
        _copy_slot2_authority_tree(source, destination_root / relative)
    write_exclusive(
        destination_root / "source-manifest.json",
        _slot2_authority_tree_manifest(destination_root, contract=V7_PROVIDER_CONTRACT),
    )


def _slot2_eligibility_projection(
    *,
    repository: Path,
    package_commit: str,
    source_root: Path,
    image_archive: Path,
) -> dict[str, object]:
    transition = _slot2_git_transition(repository, package_commit)
    entry_path = source_root / "slot1-entry-source/entry-receipt.json"
    closeout_path = source_root / "slot1-closeout-source/closeout-receipt.json"
    entry = validate_entry_receipt_source_bound(
        entry_path,
        source_root / "slot1-entry-source",
        contract=V5_PROVIDER_CONTRACT,
        package_commit=SLOT1_PACKAGE_COMMIT,
        plan_sha256=SLOT1_PLAN_SHA256,
    )
    closeout = validate_closeout_receipt(
        closeout_path,
        source_root / "slot1-closeout-source",
        contract=V5_PROVIDER_CONTRACT,
        entry_receipt_path=entry_path,
        entry_source_root=source_root / "slot1-entry-source",
        package_commit=SLOT1_PACKAGE_COMMIT,
        plan_sha256=SLOT1_PLAN_SHA256,
        lifecycle=load_campaign_lifecycle(repository, contract=V5_PROVIDER_CONTRACT),
    )
    if (
        file_sha256(closeout_path) != SLOT1_CLOSEOUT_RECEIPT_SHA256
        or file_sha256(source_root / "slot1-closeout-source/source-manifest.json")
        != SLOT1_CLOSEOUT_SOURCE_MANIFEST_SHA256
        or entry.get("launch_slot") != 1
        or entry.get("launch_count") != 1
        or closeout.get("terminal_or_absent") is not True
        or closeout.get("zero_t09_instances") is not True
        or closeout.get("security_restored") is not True
    ):
        raise T09ProviderError("slot-1 provider closeout cannot authorize slot 2")
    failure = _slot1_failure_archive_projection(source_root / "slot1-zero-use.tar.gz")
    _safe_regular_identity(
        image_archive,
        expected_bytes=SLOT1_IMAGE_ARCHIVE_BYTES,
        expected_sha256=SLOT1_IMAGE_ARCHIVE_SHA256,
    )
    prior_duration = _number(closeout.get("lambda_duration_seconds"), label="slot-1 duration")
    prior_cost = _number(closeout.get("lambda_list_cost_usd"), label="slot-1 Lambda cost")
    campaign_started = _number(entry.get("lambda_started_at_epoch"), label="campaign start")
    if (
        prior_duration <= 0
        or prior_cost <= 0
        or abs(prior_cost - prior_duration * PRICE_CENTS_PER_HOUR / 100 / 3600) > 1e-9
        or prior_cost >= V5_PROVIDER_CONTRACT.campaign_lambda_cost_cap_usd
    ):
        raise T09ProviderError("slot-1 active Lambda accounting cannot authorize slot 2")
    return {
        "schema_version": "0.2.0",
        "eligibility_kind": SLOT2_ELIGIBILITY_KIND,
        "plan_id": V5_PROVIDER_CONTRACT.plan_id,
        "host_run_id": V5_PROVIDER_CONTRACT.host_run_id,
        "closed_launch_slot": 1,
        "next_launch_slot": 2,
        "launch_count_before_next_send": 1,
        "max_launch_count": 2,
        "slot1_package_commit": SLOT1_PACKAGE_COMMIT,
        "slot2_package_commit": package_commit,
        "slot1_plan_sha256": SLOT1_PLAN_SHA256,
        "slot2_plan_sha256": SLOT1_PLAN_SHA256,
        "package_transition": transition,
        "package_transition_sha256": _sha256_bytes(_canonical_bytes(transition)),
        "slot1_entry_receipt_sha256": file_sha256(entry_path),
        "slot1_entry_source_manifest_sha256": file_sha256(
            source_root / "slot1-entry-source/source-manifest.json"
        ),
        "slot1_closeout_receipt_sha256": file_sha256(closeout_path),
        "slot1_closeout_source_manifest_sha256": file_sha256(
            source_root / "slot1-closeout-source/source-manifest.json"
        ),
        "slot1_failure": failure,
        "slot1_failure_sha256": _sha256_bytes(_canonical_bytes(failure)),
        "slot1_image_archive_sha256": SLOT1_IMAGE_ARCHIVE_SHA256,
        "slot1_image_archive_bytes": SLOT1_IMAGE_ARCHIVE_BYTES,
        "slot1_replacement_image_id": SLOT1_REPLACEMENT_IMAGE_ID,
        "slot1_qualification_id": SLOT1_QUALIFICATION_ID,
        "slot2_qualification_id": SLOT2_QUALIFICATION_ID,
        "candidate_build_attempt_count": 1,
        "selected_image_build_count": 1,
        "additional_image_build_count": 0,
        "slot2_image_import_required": True,
        "campaign_started_at_epoch": campaign_started,
        "prior_lambda_duration_seconds": prior_duration,
        "prior_lambda_cost_usd": prior_cost,
        "empirical_attempts_entered": 0,
        "model_metadata_requests": 0,
        "task_model_requests": 0,
        "task_browser_actions": 0,
        "terminal_or_absent": True,
        "zero_t09_instances": True,
        "security_restored": True,
        "second_launch_permitted": True,
    }


def _retry4_slot2_eligibility_projection(
    *,
    repository: Path,
    package_commit: str,
    source_root: Path,
    image_archive: Path,
) -> dict[str, object]:
    transition = _retry4_slot2_git_transition(repository, package_commit)
    entry_source = source_root / "slot1-entry-source"
    closeout_source = source_root / "slot1-closeout-source"
    entry_path = entry_source / "entry-receipt.json"
    closeout_path = closeout_source / "closeout-receipt.json"
    entry = validate_entry_receipt_source_bound(
        entry_path,
        entry_source,
        contract=V6_PROVIDER_CONTRACT,
        package_commit=RETRY4_SLOT1_PACKAGE_COMMIT,
        plan_sha256=RETRY4_SLOT1_PLAN_SHA256,
    )
    closeout = validate_closeout_receipt(
        closeout_path,
        closeout_source,
        contract=V6_PROVIDER_CONTRACT,
        entry_receipt_path=entry_path,
        entry_source_root=entry_source,
        package_commit=RETRY4_SLOT1_PACKAGE_COMMIT,
        plan_sha256=RETRY4_SLOT1_PLAN_SHA256,
        lifecycle=load_campaign_lifecycle(repository, contract=V6_PROVIDER_CONTRACT),
    )
    if (
        file_sha256(entry_path) != RETRY4_SLOT1_ENTRY_RECEIPT_SHA256
        or file_sha256(entry_source / "source-manifest.json")
        != RETRY4_SLOT1_ENTRY_SOURCE_MANIFEST_SHA256
        or file_sha256(closeout_path) != RETRY4_SLOT1_CLOSEOUT_RECEIPT_SHA256
        or file_sha256(closeout_source / "source-manifest.json")
        != RETRY4_SLOT1_CLOSEOUT_SOURCE_MANIFEST_SHA256
        or entry.get("launch_slot") != 1
        or entry.get("launch_count") != 1
        or entry.get("prior_campaign_lambda_duration_seconds") != 0.0
        or entry.get("prior_campaign_lambda_cost_usd") != 0.0
        or closeout.get("launch_slot") != 1
        or closeout.get("launch_count") != 1
        or closeout.get("terminal_or_absent") is not True
        or closeout.get("zero_t09_instances") is not True
        or closeout.get("security_restored") is not True
        or closeout.get("campaign_wall_exception") != "none"
    ):
        raise T09ProviderError("Retry 4 slot-1 provider closure cannot authorize slot 2")
    failure = _retry4_slot1_failure_archive_projection(source_root / "slot1-preentry-stage.tar.gz")
    _safe_regular_identity(
        image_archive,
        expected_bytes=SLOT1_IMAGE_ARCHIVE_BYTES,
        expected_sha256=SLOT1_IMAGE_ARCHIVE_SHA256,
    )
    prior_duration = _number(closeout.get("lambda_duration_seconds"), label="slot-1 duration")
    prior_cost = _number(closeout.get("lambda_list_cost_usd"), label="slot-1 Lambda cost")
    started = _number(entry.get("lambda_started_at_epoch"), label="slot-1 Lambda start")
    if (
        prior_duration <= 0
        or prior_duration > Retry4LifecycleLimits().preflight_wall_seconds
        or prior_cost <= 0
        or abs(prior_cost - prior_duration * PRICE_CENTS_PER_HOUR / 100 / 3_600) > 1e-9
        or prior_cost >= V6_PROVIDER_CONTRACT.campaign_lambda_cost_cap_usd
    ):
        raise T09ProviderError("Retry 4 slot-1 active accounting cannot authorize slot 2")
    return {
        "schema_version": "0.3.0",
        "eligibility_kind": RETRY4_SLOT2_ELIGIBILITY_KIND,
        "plan_id": RETRY4_PLAN_ID,
        "host_run_id": RETRY4_HOST_RUN_ID,
        "closed_launch_slot": 1,
        "next_launch_slot": 2,
        "launch_count_before_next_send": 1,
        "max_launch_count": 2,
        "slot1_package_commit": RETRY4_SLOT1_PACKAGE_COMMIT,
        "slot2_package_commit": package_commit,
        "slot1_plan_sha256": RETRY4_SLOT1_PLAN_SHA256,
        "slot2_plan_sha256": RETRY4_SLOT1_PLAN_SHA256,
        "package_transition": transition,
        "package_transition_sha256": _sha256_bytes(_canonical_bytes(transition)),
        "slot1_entry_receipt_sha256": file_sha256(entry_path),
        "slot1_entry_source_manifest_sha256": file_sha256(entry_source / "source-manifest.json"),
        "slot1_closeout_receipt_sha256": file_sha256(closeout_path),
        "slot1_closeout_source_manifest_sha256": file_sha256(
            closeout_source / "source-manifest.json"
        ),
        "slot1_failure": failure,
        "slot1_failure_sha256": _sha256_bytes(_canonical_bytes(failure)),
        "slot1_candidate_build_count": 1,
        "slot1_candidate_image_id": RETRY4_SLOT1_BUILT_IMAGE_ID,
        "slot1_candidate_removed_before_termination": True,
        "slot2_image_archive_sha256": SLOT1_IMAGE_ARCHIVE_SHA256,
        "slot2_image_archive_bytes": SLOT1_IMAGE_ARCHIVE_BYTES,
        "slot2_expected_image_id": SLOT1_REPLACEMENT_IMAGE_ID,
        "slot2_image_import_required": True,
        "slot2_additional_image_build_count": 0,
        "qualification_id": "QUAL-T09-PILOT-V6-IMAGE-0001",
        "slot1_lambda_started_at_epoch": started,
        "prior_lambda_duration_seconds": prior_duration,
        "prior_lambda_cost_usd": prior_cost,
        "empirical_attempts_entered": 0,
        "raw_attempts_complete": 0,
        "attempts_completed": 0,
        "slot1_model_metadata_requests": 1,
        "task_model_requests": 0,
        "task_browser_actions": 0,
        "failed_attempt_identity_consumed": False,
        "same_frozen_attempt_identity_permitted": True,
        "terminal_or_absent": True,
        "zero_t09_instances": True,
        "security_restored": True,
        "second_launch_permitted": True,
    }


def derive_retry4_preentry_replacement_eligibility(
    *,
    repository: Path,
    package_commit: str,
    prior_private_root: Path,
    slot1_failure_archive: Path,
    slot1_image_archive: Path,
) -> Path:
    """Seal slot 2 from the exact closed V6 pre-entry failure prefix."""

    prior = prior_private_root.resolve(strict=True)
    source_root = prior / "slot2-eligibility-source"
    source_root.mkdir(mode=0o700, exist_ok=False)
    _copy_slot2_authority_tree(prior / "entry-source", source_root / "slot1-entry-source")
    _copy_slot2_authority_tree(prior / "closeout-source", source_root / "slot1-closeout-source")
    target_failure = source_root / "slot1-preentry-stage.tar.gz"
    with (
        slot1_failure_archive.resolve(strict=True).open("rb") as source,
        target_failure.open("xb") as target,
    ):
        shutil.copyfileobj(source, target, 1_048_576)
        target.flush()
        os.fsync(target.fileno())
    target_failure.chmod(0o600)
    projection = _retry4_slot2_eligibility_projection(
        repository=repository.resolve(strict=True),
        package_commit=package_commit,
        source_root=source_root,
        image_archive=slot1_image_archive.resolve(strict=True),
    )
    write_exclusive(source_root / "transition.json", projection["package_transition"])
    manifest = _slot2_authority_tree_manifest(
        source_root,
        contract=V6_PROVIDER_CONTRACT,
    )
    write_exclusive(source_root / "source-manifest.json", manifest)
    eligibility = {
        **projection,
        "source_manifest_sha256": file_sha256(source_root / "source-manifest.json"),
        "source_files_sha256": manifest["files_sha256"],
        "created_at_epoch": time.time(),
    }
    path = prior / "replacement-launch-eligibility.json"
    write_exclusive(path, eligibility)
    return path


def validate_retry4_preentry_replacement_eligibility(
    prior_private_root: Path,
    *,
    repository: Path,
    package_commit: str,
    slot1_image_archive: Path,
) -> dict[str, object]:
    prior = prior_private_root.resolve(strict=True)
    source_root = prior / "slot2-eligibility-source"
    manifest_path = source_root / "source-manifest.json"
    observed_manifest = _load_json(manifest_path, maximum_bytes=1_048_576)
    expected_manifest = _slot2_authority_tree_manifest(
        source_root,
        contract=V6_PROVIDER_CONTRACT,
    )
    if observed_manifest != expected_manifest:
        raise T09ProviderError("Retry 4 slot-2 authority source manifest drifted")
    expected = _retry4_slot2_eligibility_projection(
        repository=repository.resolve(strict=True),
        package_commit=package_commit,
        source_root=source_root,
        image_archive=slot1_image_archive.resolve(strict=True),
    )
    path = prior / "replacement-launch-eligibility.json"
    observed = _load_json(path, maximum_bytes=262_144)
    created = observed.pop("created_at_epoch", None)
    required = {
        **expected,
        "source_manifest_sha256": file_sha256(manifest_path),
        "source_files_sha256": expected_manifest["files_sha256"],
    }
    metadata = path.stat(follow_symlinks=False)
    if (
        observed != required
        or not isinstance(created, (int, float))
        or isinstance(created, bool)
        or not _number(expected["slot1_lambda_started_at_epoch"], label="slot-1 start")
        <= float(created)
        <= time.time()
        or path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise T09ProviderError("Retry 4 slot-2 eligibility is not source-bound")
    return {**required, "created_at_epoch": created, "receipt_sha256": file_sha256(path)}


def derive_built_image_replacement_eligibility(
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
    prior_private_root: Path,
    slot1_failure_archive: Path,
    slot1_image_archive: Path,
) -> Path:
    """Seal the one authorized slot-2 capability from closed slot-1 evidence."""

    if contract not in {V5_PROVIDER_CONTRACT, V6_PROVIDER_CONTRACT}:
        raise T09ProviderError(
            "replacement eligibility is unsupported for the selected provider contract"
        )
    failure_path = slot1_failure_archive.resolve(strict=True)
    is_retry4_failure = (
        failure_path.stat(follow_symlinks=False).st_size == RETRY4_SLOT1_FAILURE_ARCHIVE_BYTES
        and file_sha256(failure_path) == RETRY4_SLOT1_FAILURE_ARCHIVE_SHA256
    )
    if contract is V6_PROVIDER_CONTRACT:
        if not is_retry4_failure:
            raise T09ProviderError("V6 replacement eligibility requires its exact failure archive")
        return derive_retry4_preentry_replacement_eligibility(
            repository=repository,
            package_commit=package_commit,
            prior_private_root=prior_private_root,
            slot1_failure_archive=failure_path,
            slot1_image_archive=slot1_image_archive,
        )
    if is_retry4_failure:
        raise T09ProviderError("V5 replacement eligibility rejects the V6 failure archive")
    prior = prior_private_root.resolve(strict=True)
    source_root = prior / "slot2-eligibility-source"
    source_root.mkdir(mode=0o700, exist_ok=False)
    _copy_slot2_authority_tree(prior / "entry-source", source_root / "slot1-entry-source")
    _copy_slot2_authority_tree(prior / "closeout-source", source_root / "slot1-closeout-source")
    target_failure = source_root / "slot1-zero-use.tar.gz"
    with (
        slot1_failure_archive.resolve(strict=True).open("rb") as source,
        target_failure.open("xb") as target,
    ):
        shutil.copyfileobj(source, target, 1_048_576)
        target.flush()
        os.fsync(target.fileno())
    target_failure.chmod(0o600)
    projection = _slot2_eligibility_projection(
        repository=repository.resolve(strict=True),
        package_commit=package_commit,
        source_root=source_root,
        image_archive=slot1_image_archive.resolve(strict=True),
    )
    write_exclusive(source_root / "transition.json", projection["package_transition"])
    manifest = _slot2_authority_tree_manifest(source_root, contract=V5_PROVIDER_CONTRACT)
    write_exclusive(source_root / "source-manifest.json", manifest)
    eligibility = {
        **projection,
        "source_manifest_sha256": file_sha256(source_root / "source-manifest.json"),
        "source_files_sha256": manifest["files_sha256"],
        "created_at_epoch": time.time(),
    }
    path = prior / "replacement-launch-eligibility.json"
    write_exclusive(path, eligibility)
    return path


def validate_built_image_replacement_eligibility(
    prior_private_root: Path,
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
    slot1_image_archive: Path,
) -> dict[str, object]:
    if contract is V6_PROVIDER_CONTRACT:
        return validate_retry4_preentry_replacement_eligibility(
            prior_private_root,
            repository=repository,
            package_commit=package_commit,
            slot1_image_archive=slot1_image_archive,
        )
    if contract is not V5_PROVIDER_CONTRACT:
        raise T09ProviderError(
            "built-image replacement eligibility belongs to another provider contract"
        )
    prior = prior_private_root.resolve(strict=True)
    source_root = prior / "slot2-eligibility-source"
    manifest_path = source_root / "source-manifest.json"
    observed_manifest = _load_json(manifest_path, maximum_bytes=1_048_576)
    expected_manifest = _slot2_authority_tree_manifest(source_root, contract=V5_PROVIDER_CONTRACT)
    if observed_manifest != expected_manifest:
        raise T09ProviderError("slot-2 authority source manifest drifted")
    expected = _slot2_eligibility_projection(
        repository=repository.resolve(strict=True),
        package_commit=package_commit,
        source_root=source_root,
        image_archive=slot1_image_archive.resolve(strict=True),
    )
    path = prior / "replacement-launch-eligibility.json"
    observed = _load_json(path, maximum_bytes=262_144)
    created = observed.pop("created_at_epoch", None)
    required = {
        **expected,
        "source_manifest_sha256": file_sha256(manifest_path),
        "source_files_sha256": expected_manifest["files_sha256"],
    }
    metadata = path.stat(follow_symlinks=False)
    if (
        observed != required
        or not isinstance(created, (int, float))
        or isinstance(created, bool)
        or not _number(expected["campaign_started_at_epoch"], label="campaign start")
        <= float(created)
        <= time.time()
        or path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise T09ProviderError("slot-2 replacement eligibility is not source-bound")
    return {**required, "created_at_epoch": created, "receipt_sha256": file_sha256(path)}


def validate_slot2_launch_headroom(
    eligibility: Mapping[str, object],
    *,
    lifecycle: CampaignLifecycle,
    now: float,
) -> dict[str, float]:
    """Enforce cumulative active-time/cost headroom at the slot-2 send boundary."""

    prior_duration = _number(
        eligibility.get("prior_lambda_duration_seconds"), label="slot-1 Lambda duration"
    )
    prior_cost = _number(eligibility.get("prior_lambda_cost_usd"), label="slot-1 Lambda cost")
    limits = lifecycle.limits
    if isinstance(limits, ObserverLifecycleLimits):
        raise T09ProviderError("replacement headroom requires a preflight lifecycle contract")
    # V6/V7 froze two launches and admitted slot 2 only when the complete
    # 18,000-second successful-host envelope remained. Autonomous V8+ instead
    # admits one bounded 300-second engineering continuation at a time.
    minimum_headroom = 18_000 if lifecycle.contract.version in {"V6", "V7"} else 300
    projected_duration = prior_duration + minimum_headroom
    projected_cost = prior_cost + minimum_headroom * PRICE_CENTS_PER_HOUR / 100 / 3600
    if (
        now <= 0
        or prior_duration < 0
        or prior_duration > lifecycle.maximum_cumulative_preflight_active_seconds
        or projected_duration > lifecycle.maximum_cumulative_preflight_active_seconds
        or projected_cost > lifecycle.contract.preflight_lambda_cost_cap_usd
        or lifecycle.contract.prior_t09_cost_usd + projected_cost
        > lifecycle.contract.cumulative_t09_cost_cap_usd
    ):
        raise T09ProviderError("slot-2 launch lacks cumulative active-time or cost headroom")
    return {
        "prior_lambda_duration_seconds": prior_duration,
        "prior_lambda_cost_usd": prior_cost,
        "projected_cumulative_active_seconds": projected_duration,
        "projected_cumulative_lambda_cost_usd": projected_cost,
    }


def _read_public_file(path: Path, *, maximum_bytes: int) -> str:
    metadata = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode) or not 1 <= metadata.st_size <= maximum_bytes:
        raise T09ProviderError("bound local public file is unsafe")
    return path.read_text(encoding="utf-8").strip()


def _validate_replacement_launch_eligibility(
    prior_private_root: Path,
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
    slot1_image_archive: Path | None,
) -> dict[str, object]:
    """Prove the immediately preceding launch closed before a replacement."""

    prior = prior_private_root.resolve(strict=True)
    if slot1_image_archive is None:
        raise T09ProviderError("replacement launch requires the exact retained image archive")
    _safe_regular_identity(
        slot1_image_archive,
        expected_bytes=SLOT1_IMAGE_ARCHIVE_BYTES,
        expected_sha256=SLOT1_IMAGE_ARCHIVE_SHA256,
    )
    path = prior / "replacement-launch-eligibility.json"
    metadata = path.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise T09ProviderError("replacement-launch eligibility metadata is unsafe")
    value = _load_json(path, maximum_bytes=262_144)
    closed_slot = _integer(value.get("closed_launch_slot"), label="closed launch slot")
    if closed_slot not in range(1, contract.max_launch_count):
        raise T09ProviderError("replacement eligibility closed slot is outside authority")
    if value.get("eligibility_kind") == RETRY4_SLOT2_ELIGIBILITY_KIND:
        if contract is not V6_PROVIDER_CONTRACT:
            raise T09ProviderError(
                "Retry 4 replacement eligibility belongs to another provider contract"
            )
        prior_capability = _load_json(
            launch_capability_path(closed_slot, contract=V6_PROVIDER_CONTRACT),
            maximum_bytes=65_536,
        )
        if (
            closed_slot != 1
            or prior_capability.get("plan_id") != V6_PROVIDER_CONTRACT.plan_id
            or prior_capability.get("host_run_id") != V6_PROVIDER_CONTRACT.host_run_id
            or prior_capability.get("package_commit") != RETRY4_SLOT1_PACKAGE_COMMIT
            or prior_capability.get("plan_sha256") != RETRY4_SLOT1_PLAN_SHA256
            or prior_capability.get("launch_slot") != 1
            or prior_capability.get("launch_capability_limit") != 2
            or prior_capability.get("replacement_eligibility_sha256") is not None
        ):
            raise T09ProviderError("Retry 4 slot-1 capability cannot authorize slot 2")
        return validate_retry4_preentry_replacement_eligibility(
            prior,
            repository=repository,
            package_commit=package_commit,
            slot1_image_archive=slot1_image_archive,
        )
    if value.get("eligibility_kind") == SLOT2_ELIGIBILITY_KIND:
        if contract is not V5_PROVIDER_CONTRACT:
            raise T09ProviderError(
                "built-image replacement eligibility belongs to another provider contract"
            )
        prior_capability = _load_json(
            launch_capability_path(closed_slot, contract=V5_PROVIDER_CONTRACT),
            maximum_bytes=65_536,
        )
        if (
            closed_slot != 1
            or prior_capability.get("plan_id") != V5_PROVIDER_CONTRACT.plan_id
            or prior_capability.get("host_run_id") != V5_PROVIDER_CONTRACT.host_run_id
            or prior_capability.get("package_commit") != SLOT1_PACKAGE_COMMIT
            or prior_capability.get("plan_sha256") != SLOT1_PLAN_SHA256
            or prior_capability.get("launch_slot") != 1
            or prior_capability.get("launch_capability_limit") != 2
            or prior_capability.get("replacement_eligibility_sha256") is not None
        ):
            raise T09ProviderError("slot-1 launch capability cannot authorize slot 2")
        return validate_built_image_replacement_eligibility(
            prior,
            contract=contract,
            repository=repository,
            package_commit=package_commit,
            slot1_image_archive=slot1_image_archive,
        )
    prior_capability = _load_json(
        launch_capability_path(closed_slot, contract=contract), maximum_bytes=65_536
    )
    source_package_commit = value.get("package_commit")
    if (
        not isinstance(source_package_commit, str)
        or _HEX40.fullmatch(source_package_commit) is None
        or prior_capability.get("plan_id") != contract.plan_id
        or prior_capability.get("host_run_id") != contract.host_run_id
        or prior_capability.get("package_commit") != source_package_commit
        or prior_capability.get("launch_slot") != closed_slot
        or prior_capability.get("launch_capability_limit") != contract.max_launch_count
        or (closed_slot == 1 and prior_capability.get("replacement_eligibility_sha256") is not None)
        or (
            closed_slot > 1
            and not isinstance(prior_capability.get("replacement_eligibility_sha256"), str)
        )
    ):
        raise T09ProviderError("first launch capability cannot authorize replacement")
    package_transition: dict[str, object] | None = None
    if source_package_commit != package_commit:
        if (
            source_package_commit == RETRY5_ACTIVE_SLOT1_PACKAGE_COMMIT
            and prior_capability.get("plan_sha256") == RETRY5_ACTIVE_SLOT1_PLAN_SHA256
            and value.get("eligibility_kind") is None
        ):
            package_transition = retry5_closed_slot1_package_transition(repository, package_commit)
        else:
            package_transition = autonomous_preflight_package_transition(
                repository,
                contract=contract,
                from_package_commit=source_package_commit,
                to_package_commit=package_commit,
            )
    if value.get("eligibility_kind") == "provider-entry-failed-preempirical":
        provisional = _load_source_validated_provisional_owner(
            prior,
            contract=contract,
            repository=repository,
            package_commit=package_commit,
        )
        entry_manifest = validate_source_manifest(prior / "entry-source", contract=contract)
        closeout_manifest = validate_source_manifest(
            prior / "provisional-closeout-source", contract=contract
        )
        closed = _load_json(prior / "PROVISIONAL_OWNER_CLOSED.json", maximum_bytes=65_536)
        started = _number(
            provisional.get("lambda_started_at_epoch"), label="provisional campaign start"
        )
        closed_at = _number(closed.get("closed_at_epoch"), label="provisional close time")
        duration = closed_at - started
        expected_provisional = {
            "schema_version": "0.1.0",
            "eligibility_kind": "provider-entry-failed-preempirical",
            "plan_id": contract.plan_id,
            "host_run_id": contract.host_run_id,
            "package_commit": package_commit,
            "closed_launch_slot": closed_slot,
            "entry_source_manifest_sha256": file_sha256(
                prior / "entry-source/source-manifest.json"
            ),
            "provisional_closeout_manifest_sha256": file_sha256(
                prior / "provisional-closeout-source/source-manifest.json"
            ),
            "campaign_started_at_epoch": started,
            "prior_lambda_duration_seconds": duration,
            "prior_lambda_cost_usd": duration * 1.29 / 3600.0,
            "empirical_attempts_entered": 0,
            "model_task_requests": 0,
            "task_browser_actions": 0,
            "replacement_image_build_count": 0,
            "slot2_image_archive_sha256": SLOT1_IMAGE_ARCHIVE_SHA256,
            "slot2_image_archive_bytes": SLOT1_IMAGE_ARCHIVE_BYTES,
            "slot2_expected_image_id": SLOT1_REPLACEMENT_IMAGE_ID,
            "slot2_image_import_required": True,
            "slot2_additional_image_build_count": 0,
            "terminal_or_absent": True,
            "zero_t09_instances": True,
            "security_restored": True,
            "second_launch_permitted": True,
        }
        if (
            value != expected_provisional
            or not entry_manifest
            or not closeout_manifest
            or provisional.get("launch_slot") != closed_slot
            or not _provisional_replacement_permitted(contract, launch_slot=closed_slot)
            or closed.get("owned_instance_identity_sha256")
            != provisional.get("owned_instance_identity_sha256")
            or closed.get("provider_disposition") != "absent"
            or closed.get("zero_t09_instances") is not True
            or closed.get("security_restored") is not True
            or duration < 0
            or duration * 1.29 / 3600.0 >= contract.preflight_lambda_cost_cap_usd
        ):
            raise T09ProviderError("provisional replacement eligibility drifted")
        return value
    entry_source, closeout_source, retained_preempirical_source = _current_v7_slot2_authority_paths(
        prior
    )
    entry_path = entry_source / "entry-receipt.json"
    closeout_path = closeout_source / "closeout-receipt.json"
    observed_entry = _load_json(entry_path, maximum_bytes=65_536)
    source_plan_sha256 = observed_entry.get("plan_sha256")
    if not isinstance(source_plan_sha256, str) or _HEX64.fullmatch(source_plan_sha256) is None:
        raise T09ProviderError("replacement source plan identity is malformed")
    lifecycle = load_campaign_lifecycle(repository, contract=contract)
    entry = validate_entry_receipt_source_bound(
        entry_path,
        entry_source,
        contract=contract,
        package_commit=source_package_commit,
        plan_sha256=source_plan_sha256,
    )
    closeout = validate_closeout_receipt(
        closeout_path,
        closeout_source,
        contract=contract,
        entry_receipt_path=entry_path,
        entry_source_root=entry_source,
        package_commit=source_package_commit,
        plan_sha256=source_plan_sha256,
        lifecycle=lifecycle,
    )
    host_disposition = _validate_host_preempirical_disposition(
        retained_preempirical_source / "preempirical-disposition.json",
        retained_preempirical_source,
        contract=contract,
        package_commit=source_package_commit,
        entry_receipt_sha256=file_sha256(entry_path),
        provider_preflight_started_at_epoch=_number(
            entry.get("provider_preflight_started_at_epoch"),
            label="provider preflight start",
        ),
    )
    required = {
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "package_commit": source_package_commit,
        "closed_launch_slot": entry["launch_slot"],
        "entry_receipt_sha256": file_sha256(entry_path),
        "closeout_receipt_sha256": file_sha256(closeout_path),
        "host_preempirical_receipt_sha256": file_sha256(
            retained_preempirical_source / "preempirical-disposition.json"
        ),
        "host_preempirical_source_manifest_sha256": file_sha256(
            retained_preempirical_source / "source-manifest.json"
        ),
        "source_manifest_sha256": file_sha256(
            retained_preempirical_source / "source-manifest.json"
        ),
        "campaign_started_at_epoch": entry["lambda_started_at_epoch"],
        "prior_lambda_duration_seconds": closeout["lambda_duration_seconds"],
        "prior_lambda_cost_usd": closeout["lambda_list_cost_usd"],
        "empirical_attempts_entered": 0,
        "model_task_requests": 0,
        "task_browser_actions": 0,
        "replacement_image_build_count": 0,
        "replacement_image_import_count": host_disposition["replacement_image_import_count"],
        "replacement_image_id": host_disposition["replacement_image_id"],
        "replacement_image_archive_sha256": host_disposition["replacement_image_archive_sha256"],
        "slot2_image_archive_sha256": SLOT1_IMAGE_ARCHIVE_SHA256,
        "slot2_image_archive_bytes": SLOT1_IMAGE_ARCHIVE_BYTES,
        "slot2_expected_image_id": SLOT1_REPLACEMENT_IMAGE_ID,
        "slot2_image_import_required": True,
        "slot2_additional_image_build_count": 0,
        "terminal_or_absent": True,
        "zero_t09_instances": True,
        "security_restored": True,
        "next_replacement_launch_permitted": (
            _integer(entry["launch_slot"], label="closed launch slot") < contract.max_launch_count
        ),
    }
    if value != required or host_disposition.get("empirical_attempts_entered") != 0:
        raise T09ProviderError("replacement launch is not source-bound and pre-empirical")
    if (
        closeout.get("terminal_or_absent") is not True
        or closeout.get("zero_t09_instances") is not True
        or closeout.get("security_restored") is not True
        or _number(value["prior_lambda_cost_usd"], label="prior Lambda cost")
        >= contract.preflight_lambda_cost_cap_usd
    ):
        raise T09ProviderError("replacement launch lacks terminal, security, or budget closure")
    return {
        **value,
        "package_transition": package_transition,
        "package_transition_sha256": (
            _sha256_bytes(_canonical_bytes(package_transition))
            if package_transition is not None
            else None
        ),
    }


def _validate_host_preempirical_disposition(
    receipt_path: Path,
    source_root: Path,
    *,
    contract: T09ProviderContract,
    package_commit: str,
    entry_receipt_sha256: str,
    provider_preflight_started_at_epoch: float,
) -> dict[str, object]:
    """Validate the copied host prefix proving launch 1 never crossed entry."""

    source = source_root.resolve(strict=True)
    receipt = receipt_path.resolve(strict=True)
    if receipt.parent != source:
        raise T09ProviderError("pre-empirical receipt escaped its copied source root")
    manifest_path = source / "source-manifest.json"
    manifest = _load_json(manifest_path, maximum_bytes=1_048_576)
    files: list[dict[str, object]] = []
    total = 0
    for path in sorted(source.iterdir()):
        if path.name == "source-manifest.json":
            continue
        metadata = path.stat(follow_symlinks=False)
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise T09ProviderError("pre-empirical source contains an unsafe member")
        total += metadata.st_size
        files.append({"path": path.name, "bytes": metadata.st_size, "sha256": file_sha256(path)})
    expected_manifest = {
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "files": files,
        "total_bytes": total,
    }
    if manifest != expected_manifest or not 0 < total <= 1_048_576:
        raise T09ProviderError("pre-empirical source manifest drifted")
    value = _load_json(receipt, maximum_bytes=65_536)
    state_path = source / "pilot-state.json"
    cleanup_path = source / "host-cleanup.json"
    failure_path = source / "preflight-failure.json"
    late_gate_path = source / "late-preflight-gate-absence.json"
    state = _load_json(state_path, maximum_bytes=65_536)
    cleanup = _load_json(cleanup_path, maximum_bytes=65_536)
    failure = _load_json(failure_path, maximum_bytes=65_536)
    late_gate = _load_json(late_gate_path, maximum_bytes=65_536)
    failed_at = _number(failure.get("failed_at_epoch"), label="preflight failure time")
    failure_started = _number(
        failure.get("provider_preflight_started_at_epoch"),
        label="provider preflight start",
    )
    iteration_started = _number(
        failure.get("preflight_iteration_started_at_epoch"),
        label="preflight iteration start",
    )
    iteration_elapsed = _number(
        failure.get("preflight_iteration_elapsed_seconds"),
        label="preflight iteration elapsed time",
    )
    provider_instance_elapsed = _number(
        failure.get("provider_instance_elapsed_seconds"),
        label="provider instance elapsed time",
    )
    dispatch_deadline = failure.get("termination_dispatch_deadline_epoch")
    if dispatch_deadline is not None and (
        not isinstance(dispatch_deadline, (int, float)) or isinstance(dispatch_deadline, bool)
    ):
        raise T09ProviderError("preflight termination dispatch deadline is malformed")
    image_import_count = value.get("replacement_image_import_count")
    replacement_image_id = value.get("replacement_image_id")
    replacement_archive_sha256 = value.get("replacement_image_archive_sha256")
    if (
        (
            image_import_count == 0
            and (replacement_image_id is not None or replacement_archive_sha256 is not None)
        )
        or (
            image_import_count == 1
            and (
                replacement_image_id != SLOT1_REPLACEMENT_IMAGE_ID
                or replacement_archive_sha256 != SLOT1_IMAGE_ARCHIVE_SHA256
            )
        )
        or image_import_count not in {0, 1}
    ):
        raise T09ProviderError("pre-empirical image materialization evidence drifted")
    required = {
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "package_commit": package_commit,
        "provider_entry_receipt_sha256": entry_receipt_sha256,
        "pilot_state_sha256": file_sha256(state_path),
        "host_cleanup_sha256": file_sha256(cleanup_path),
        "preflight_failure_sha256": file_sha256(failure_path),
        "late_preflight_gate_absence_sha256": file_sha256(late_gate_path),
        "preflight_failed_at_epoch": failed_at,
        "provider_preflight_started_at_epoch": failure_started,
        "preflight_iteration_started_at_epoch": iteration_started,
        "preflight_iteration_elapsed_seconds": iteration_elapsed,
        "provider_instance_elapsed_seconds": provider_instance_elapsed,
        "termination_dispatch_deadline_epoch": dispatch_deadline,
        "preflight_engineering_state": failure.get("preflight_engineering_state"),
        "empirical_attempts_entered": 0,
        "model_metadata_requests": 0,
        "model_task_requests": 0,
        "task_browser_actions": 0,
        "replacement_image_build_count": 0,
        "replacement_image_import_count": image_import_count,
        "replacement_image_id": replacement_image_id,
        "replacement_image_archive_sha256": replacement_archive_sha256,
        "credentials_removed": True,
        "owned_containers_absent": True,
        "core_safety_stop_detected": False,
        "core_destruction_verified": True,
        "credential_rotation_required_due_to_core_handling": False,
        "replacement_launch_evidence_only": True,
    }
    if (
        value != required
        or state.get("plan_id") != contract.plan_id
        or state.get("empirical_attempts_entered") != []
        or state.get("nonempirical_infrastructure_attempts_consumed") != []
        or state.get("raw_attempts_complete") != []
        or state.get("attempts_completed") != []
        or state.get("essential_failure_seals") != {}
        or state.get("core_safety_stop_detected") is not False
        or cleanup.get("owned_container_residue") != []
        or cleanup.get("global_secret_scan_passed") is not True
        or cleanup.get("remote_secret_removed") is not True
        or cleanup.get("core_destruction_verified") is not True
        or cleanup.get("core_safety_stop_detected") is not False
        or cleanup.get("credential_rotation_required_due_to_core_handling") is not False
        or late_gate
        != {
            "schema_version": "0.1.0",
            "plan_id": contract.plan_id,
            "host_run_id": contract.host_run_id,
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
        }
        or failure.get("plan_id") != contract.plan_id
        or failure.get("host_run_id") != contract.host_run_id
        or failure.get("package_commit") != package_commit
        or failure.get("empirical_attempts_entered") != 0
        or failure.get("preflight_engineering_state") != "resumable-same-host"
        or failure.get("termination_dispatch_required") is not False
        or failure_started != provider_preflight_started_at_epoch
        or not failure_started <= iteration_started <= failed_at
        or iteration_elapsed != failed_at - iteration_started
        or provider_instance_elapsed != failed_at - failure_started
        or not 0
        <= iteration_elapsed
        <= AutonomousPilotLifecycleLimits().preflight_iteration_wall_seconds + 5
        or not 0
        <= provider_instance_elapsed
        <= AutonomousPilotLifecycleLimits().maximum_preflight_instance_active_seconds
        or dispatch_deadline is not None
    ):
        raise T09ProviderError("host pre-empirical disposition is not source-grounded zero-use")
    return value


def _retain_host_preempirical_source(source_root: Path, private_root: Path) -> Path:
    """Copy the validated zero-use host bundle into launch-1 private evidence."""

    source = source_root.resolve(strict=True)
    destination = private_root / "preempirical-source"
    destination.mkdir(mode=0o700, exist_ok=False)
    total = 0
    for source_path in sorted(source.iterdir()):
        metadata = source_path.stat(follow_symlinks=False)
        if (
            source_path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise T09ProviderError("pre-empirical source cannot be retained safely")
        total += metadata.st_size
        if total > 1_048_576:
            raise T09ProviderError("pre-empirical source exceeds its retention cap")
        source_descriptor = os.open(
            source_path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        destination_path = destination / source_path.name
        destination_descriptor = os.open(
            destination_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            remaining = metadata.st_size
            while remaining:
                chunk = os.read(source_descriptor, min(65_536, remaining))
                if not chunk:
                    raise T09ProviderError("pre-empirical source copy ended early")
                offset = 0
                while offset < len(chunk):
                    written = os.write(destination_descriptor, chunk[offset:])
                    if written <= 0:
                        raise T09ProviderError("pre-empirical source copy made no progress")
                    offset += written
                remaining -= len(chunk)
            if os.read(source_descriptor, 1):
                raise T09ProviderError("pre-empirical source changed during copy")
            os.fsync(destination_descriptor)
        finally:
            os.close(destination_descriptor)
            os.close(source_descriptor)
        if file_sha256(destination_path) != file_sha256(source_path):
            raise T09ProviderError("pre-empirical retained copy hash mismatch")
    directory = os.open(destination, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return destination


def _load_source_validated_owned_state(
    private_root: Path,
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
) -> dict[str, object]:
    """Bind the destructive target back to launch evidence before any POST."""

    plan_path = repository / contract.provider_profile_path
    plan_sha256 = file_sha256(plan_path)
    entry_source = private_root / "entry-source"
    entry_path = entry_source / "entry-receipt.json"
    entry = validate_entry_receipt_source_bound(
        entry_path,
        entry_source,
        contract=contract,
        package_commit=package_commit,
        plan_sha256=plan_sha256,
    )
    candidates: list[dict[str, object]] = []
    for name in ("owned-state.json", "owned-state-active.json"):
        candidate = private_root / name
        if candidate.is_file():
            state = _load_json(candidate, maximum_bytes=65_536)
            expected_keys = {
                "schema_version",
                "plan_id",
                "host_run_id",
                "package_commit",
                "plan_sha256",
                "instance_id",
                "owned_instance_identity_sha256",
                "instance_name",
                "launch_slot",
                "replacement_eligibility_sha256",
                "lambda_started_at_epoch",
            }
            if name == "owned-state-active.json":
                expected_keys.add("ssh_target")
            if set(state) != expected_keys:
                raise T09ProviderError("owned instance state field set drifted")
            instance_id = _string(state.get("instance_id"), label="owned instance ID")
            identity = _instance_identity_sha256(instance_id)
            if (
                state.get("schema_version") != "0.1.0"
                or state.get("plan_id") != contract.plan_id
                or state.get("host_run_id") != contract.host_run_id
                or state.get("package_commit") != package_commit
                or state.get("plan_sha256") != plan_sha256
                or state.get("instance_name") != contract.instance_name
                or state.get("launch_slot") != entry.get("launch_slot")
                or state.get("replacement_eligibility_sha256")
                != entry.get("replacement_eligibility_sha256")
                or state.get("owned_instance_identity_sha256") != identity
                or entry.get("owned_instance_identity_sha256") != identity
                or state.get("lambda_started_at_epoch")
                != entry.get("owned_lambda_started_at_epoch")
            ):
                raise T09ProviderError("owned instance state is not source-bound")
            candidates.append(state)
    if not candidates:
        raise T09ProviderError(
            "owned instance state is unavailable; do not relaunch; terminate the unique exact "
            "instance name through the Lambda console and verify it absent"
        )
    shared = {key: candidates[0][key] for key in candidates[0] if key != "ssh_target"}
    if any(
        {key: value for key, value in candidate.items() if key != "ssh_target"} != shared
        for candidate in candidates[1:]
    ):
        raise T09ProviderError("owned instance state copies disagree")
    return candidates[-1]


def _load_source_validated_provisional_owner(
    private_root: Path,
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
) -> dict[str, object]:
    """Recover an exact pre-entry owner after an interrupted launch process."""

    plan_path = repository / contract.provider_profile_path
    observed = _load_json(private_root / "provisional-owned-state.json", maximum_bytes=65_536)
    instance_id = _string(
        observed.get("private_instance_id"), label="provisional private instance ID"
    )
    launch_slot = _integer(observed.get("launch_slot"), label="provisional launch slot")
    replacement_eligibility_sha256 = observed.get("replacement_eligibility_sha256")
    if replacement_eligibility_sha256 is not None and not isinstance(
        replacement_eligibility_sha256, str
    ):
        raise T09ProviderError("provisional replacement eligibility hash is malformed")
    expected = _provisional_owner_binding(
        contract=contract,
        entry_root=private_root / "entry-source",
        capability_path=launch_capability_path(launch_slot, contract=contract),
        package_commit=package_commit,
        plan_sha256=file_sha256(plan_path),
        private_root=private_root,
        instance_id=instance_id,
        launch_slot=launch_slot,
        replacement_eligibility_sha256=replacement_eligibility_sha256,
    )
    if observed != expected:
        raise T09ProviderError("provisional owner is not source-bound")
    initial = _validate_initial_preflight_cleanup_state(
        private_root / "preflight-cleanup-state",
        contract=contract,
        package_commit=package_commit,
        plan_sha256=file_sha256(plan_path),
    )
    if (
        initial.get("private_instance_id") != observed.get("private_instance_id")
        or initial.get("owned_instance_identity_sha256")
        != observed.get("owned_instance_identity_sha256")
        or initial.get("lambda_started_at_epoch") != observed.get("lambda_started_at_epoch")
    ):
        raise T09ProviderError("provisional owner drifted from initial cleanup authority")
    return observed


def _validate_model_metadata_receipt_for_provider(
    receipt_path: Path,
    *,
    contract: T09ProviderContract,
    package_commit: str,
    package_tree: str,
    plan_sha256: str,
    authorization_ledger: Path,
) -> dict[str, object]:
    """Re-read and validate every immutable receipt binding without a clock."""

    return validate_model_metadata_receipt(
        receipt_path,
        contract=contract,
        package_commit=package_commit,
        package_tree=package_tree,
        plan_sha256=plan_sha256,
        authorization_overlay=authorization_ledger,
        validation_policy=ModelMetadataReceiptValidationPolicy.DURABLE_OFFLINE,
    )


def launch_campaign(
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
    authorization_ledger: Path,
    dotenv: Path,
    private_root: Path,
    public_ipv4_file: Path,
    ssh_public_key_file: Path,
    transport: ProviderTransport,
    launch_slot: int = 1,
    prior_private_root: Path | None = None,
    slot1_image_archive: Path | None = None,
    model_metadata_receipt: Path | None = None,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> Path:
    repository = repository.resolve(strict=True)
    if launch_slot not in range(1, contract.max_launch_count + 1):
        raise T09ProviderError("launch slot is outside the authorized autonomous bound")
    replacement_eligibility: dict[str, object] | None = None
    if launch_slot == 1:
        if prior_private_root is not None or slot1_image_archive is not None:
            raise T09ProviderError("first launch cannot accept prior campaign state")
    else:
        if prior_private_root is None:
            raise T09ProviderError("replacement launch requires exact prior closeout evidence")
        replacement_eligibility = _validate_replacement_launch_eligibility(
            prior_private_root,
            contract=contract,
            repository=repository,
            package_commit=package_commit,
            slot1_image_archive=slot1_image_archive,
        )
        if not launch_capability_path(launch_slot - 1, contract=contract).is_file():
            raise T09ProviderError("replacement launch cannot skip its preceding launch slot")
    replacement_eligibility_sha256 = (
        file_sha256(prior_private_root.resolve(strict=True) / "replacement-launch-eligibility.json")
        if prior_private_root is not None
        else None
    )
    capability_path = launch_capability_path(launch_slot, contract=contract)
    # This check precedes credential loading and every provider request.  The
    # later O_EXCL consume is the concurrent, mutation-adjacent enforcement.
    _assert_launch_capability_unused(capability_path)
    _verify_clean_package(repository, package_commit)
    authorization = validate_authorization_ledger(
        authorization_ledger,
        contract=contract,
        repository=repository,
        package_commit=package_commit,
    )
    lifecycle = load_campaign_lifecycle(repository, contract=contract)
    plan_path = repository / contract.provider_profile_path
    plan_sha256 = file_sha256(plan_path)
    package_tree = (
        _git_commit_tree(repository, package_commit) if contract.version == "V12" else None
    )
    model_metadata_receipt_sha256_value: str | None = None
    if contract.version == "V12":
        if model_metadata_receipt is None:
            raise T09ProviderError("V12 provider launch requires the model metadata receipt")
        if package_tree is None:  # pragma: no cover - guarded by the typed contract
            raise T09ProviderError("V12 package tree is unavailable")
        v12_package_tree = package_tree
        try:
            validated_receipt = _validate_model_metadata_receipt_for_provider(
                model_metadata_receipt,
                contract=contract,
                package_commit=package_commit,
                package_tree=v12_package_tree,
                plan_sha256=plan_sha256,
                authorization_ledger=authorization_ledger,
            )
            model_metadata_receipt_sha256_value = semantic_projection_sha256(validated_receipt)
        except (ModelMetadataReceiptError, OSError, subprocess.SubprocessError) as exc:
            raise T09ProviderError("V12 model metadata receipt validation failed") from exc
    elif model_metadata_receipt is not None:
        raise T09ProviderError("model metadata receipt is only valid for V12")
    if private_root.exists():
        raise T09ProviderError("provider private root already exists; launch slot is single use")
    private_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    if replacement_eligibility is not None and slot1_image_archive is not None:
        assert prior_private_root is not None
        retained_source = private_root / "slot2-eligibility-source"
        prior = prior_private_root.resolve(strict=True)
        if replacement_eligibility.get("eligibility_kind") in {
            RETRY4_SLOT2_ELIGIBILITY_KIND,
            SLOT2_ELIGIBILITY_KIND,
        }:
            _copy_slot2_authority_tree(
                prior / "slot2-eligibility-source",
                retained_source,
            )
        elif replacement_eligibility.get("eligibility_kind") is None:
            _retain_current_v7_slot2_authority(prior, retained_source)
        else:
            raise T09ProviderError(
                "provider-entry replacement evidence cannot be normalized as a host closeout"
            )
        retained_eligibility = private_root / "replacement-launch-eligibility.json"
        with (
            (prior / "replacement-launch-eligibility.json").open("rb") as source,
            retained_eligibility.open("xb") as target,
        ):
            shutil.copyfileobj(source, target, 1_048_576)
            target.flush()
            os.fsync(target.fileno())
        retained_eligibility.chmod(0o600)
        retained = _validate_replacement_launch_eligibility(
            private_root,
            contract=contract,
            repository=repository,
            package_commit=package_commit,
            slot1_image_archive=slot1_image_archive,
        )
        if retained != replacement_eligibility:
            raise T09ProviderError("retained slot-2 eligibility changed during copy")
    entry_root = private_root / "entry-source"
    entry_root.mkdir(mode=0o700)
    retained_model_metadata_receipt: Path | None = None
    if model_metadata_receipt_sha256_value is not None:
        retained_receipt = entry_root / MODEL_METADATA_RECEIPT_FILENAME
        retained_model_metadata_receipt = retained_receipt
        retained_receipt_sha256 = copy_model_metadata_receipt(
            cast(Path, model_metadata_receipt),
            retained_receipt,
        )
        if retained_receipt_sha256 != model_metadata_receipt_sha256_value:
            raise T09ProviderError("retained model metadata receipt changed during copy")
        write_exclusive(
            private_root / "model-metadata-receipt-binding.json",
            {
                "schema_version": "1.0.0",
                "receipt_sha256": model_metadata_receipt_sha256_value,
                "receipt_filename": MODEL_METADATA_RECEIPT_FILENAME,
                "provider_contract_version": contract.version,
                "plan_id": contract.plan_id,
                "host_run_id": contract.host_run_id,
                "prelaunch_required": True,
            },
        )
    authorization_binding: dict[str, object] = {
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "authorization_source_sha256": authorization["authorization_source_sha256"],
        "authorization_reference": authorization["authorization_reference"],
        "authorization_ledger_sha256": file_sha256(authorization_ledger),
    }
    if model_metadata_receipt_sha256_value is not None:
        authorization_binding["model_metadata_receipt_sha256"] = model_metadata_receipt_sha256_value
    write_exclusive(
        entry_root / "authorization-binding.json",
        authorization_binding,
    )
    if model_metadata_receipt_sha256_value is not None:
        write_exclusive(
            entry_root / "model-metadata-receipt-binding.json",
            {
                "schema_version": "1.0.0",
                "receipt_sha256": model_metadata_receipt_sha256_value,
                "receipt_filename": MODEL_METADATA_RECEIPT_FILENAME,
                "provider_contract_version": contract.version,
                "plan_id": contract.plan_id,
                "host_run_id": contract.host_run_id,
                "prelaunch_required": True,
            },
        )
    expected_public_ipv4 = _read_public_file(public_ipv4_file, maximum_bytes=64)
    expected_public_key = _read_public_file(ssh_public_key_file, maximum_bytes=16_384)
    credential = load_dotenv_assignment(dotenv, "LAMBDA_API_KEY")
    recorder = RequestRecorder(entry_root, transport, credential, clock)
    try:
        for operation, path in (
            ("instance-types", "/api/v1/instance-types"),
            ("images", "/api/v1/images"),
            ("ssh-keys", "/api/v1/ssh-keys"),
            ("global-firewall", "/api/v1/firewall-rulesets/global"),
            ("regional-rulesets", "/api/v1/firewall-rulesets"),
            ("prelaunch-instances", "/api/v1/instances"),
        ):
            recorder.request(operation, "GET", path)
            sleeper(1.0)
        documents = _response_documents(entry_root)
        # Validate every non-mutation fact before the one irreversible launch send.
        provisional = dict(documents)
        provisional["launch"] = [
            (
                {
                    "response_received_at_epoch": clock(),
                    "request_body_sha256": _sha256_bytes(
                        _canonical_bytes(_launch_body(contract=contract))
                    ),
                },
                {"data": {"instance_identity_sha256s": ["0" * 64]}},
            )
        ]
        _validate_prelaunch_documents(
            provisional,
            contract=contract,
            expected_public_key=expected_public_key,
            expected_public_ipv4=expected_public_ipv4,
        )
        if replacement_eligibility is not None:
            validate_slot2_launch_headroom(
                replacement_eligibility,
                lifecycle=lifecycle,
                now=clock(),
            )
        prepared_launch = recorder.prepare(
            "launch",
            "POST",
            "/api/v1/instance-operations/launch",
            body=_launch_body(contract=contract),
        )
        final_launch_admission: Callable[[], float] | None = None
        if model_metadata_receipt_sha256_value is not None:
            receipt_for_launch = retained_model_metadata_receipt
            if receipt_for_launch is None:
                raise T09ProviderError("V12 retained model metadata receipt is unavailable")

            # Phase A: all possibly blocking local preparation is durable before
            # the final freshness sample. The capability and send intent remain
            # nonreplayable even when final admission later rejects the receipt.
            _consume_launch_capability(
                capability_path,
                contract=contract,
                authorization_ledger=authorization_ledger,
                authorization=authorization,
                package_commit=package_commit,
                plan_sha256=plan_sha256,
                private_root=private_root,
                launch_slot=launch_slot,
                replacement_eligibility_sha256=replacement_eligibility_sha256,
                clock=clock,
            )
            launch_body_sha256 = cast(
                str,
                prepared_launch.intent_without_timestamp["request_body_sha256"],
            )
            write_exclusive(
                private_root / "launch-intent.json",
                {
                    "schema_version": "0.1.0",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "package_commit": package_commit,
                    "launch_body_sha256": launch_body_sha256,
                    "launch_slot": launch_slot,
                    "launch_count_after_send": launch_slot,
                    "max_preflight_launch_count": contract.max_launch_count,
                    "replacement_eligibility_sha256": replacement_eligibility_sha256,
                    "launch_capability_sha256": file_sha256(capability_path),
                    "launch_capability_state": "consumed-during-local-preparation",
                    "model_metadata_receipt_sha256": model_metadata_receipt_sha256_value,
                    "created_at_epoch": clock(),
                },
            )
            write_exclusive(
                private_root / "launch-send-intent.json",
                {
                    "schema_version": "1.0.0",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "package_commit": package_commit,
                    "package_tree": v12_package_tree,
                    "launch_slot": launch_slot,
                    "request_ordinal": prepared_launch.ordinal,
                    "method": prepared_launch.method,
                    "path": prepared_launch.path,
                    "request_body_sha256": launch_body_sha256,
                    "model_metadata_receipt_sha256": model_metadata_receipt_sha256_value,
                    "send_intent_created_at_epoch": clock(),
                    "send_started_at_epoch": None,
                    "transport_calls_completed": 0,
                    "automatic_retry": False,
                    "replay_allowed": False,
                    "state": "durable-before-final-admission",
                },
            )

            def admit_v12_launch() -> float:
                # Phase B step 1: re-read the exact retained bytes and overlay.
                validated = _validate_model_metadata_receipt_for_provider(
                    receipt_for_launch,
                    contract=contract,
                    package_commit=package_commit,
                    package_tree=v12_package_tree,
                    plan_sha256=plan_sha256,
                    authorization_ledger=authorization_ledger,
                )
                if semantic_projection_sha256(validated) != model_metadata_receipt_sha256_value:
                    raise T09ProviderError(
                        "V12 retained model metadata receipt changed before provider launch"
                    )
                # Phase B steps 2-4: sample only after the re-read, then make a
                # pure in-memory decision. RequestRecorder calls transport.send
                # as its immediately following effect.
                boundary_epoch = clock()
                admit_model_metadata_receipt_at_prelaunch_boundary(
                    validated,
                    boundary_epoch=boundary_epoch,
                )
                return boundary_epoch

            final_launch_admission = admit_v12_launch
        else:
            _consume_launch_capability(
                capability_path,
                contract=contract,
                authorization_ledger=authorization_ledger,
                authorization=authorization,
                package_commit=package_commit,
                plan_sha256=plan_sha256,
                private_root=private_root,
                launch_slot=launch_slot,
                replacement_eligibility_sha256=replacement_eligibility_sha256,
                clock=clock,
            )
            write_exclusive(
                private_root / "launch-intent.json",
                {
                    "schema_version": "0.1.0",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "package_commit": package_commit,
                    "launch_body_sha256": _sha256_bytes(
                        _canonical_bytes(_launch_body(contract=contract))
                    ),
                    "launch_slot": launch_slot,
                    "launch_count_after_send": launch_slot,
                    "max_preflight_launch_count": contract.max_launch_count,
                    "replacement_eligibility_sha256": replacement_eligibility_sha256,
                    "launch_capability_sha256": file_sha256(capability_path),
                    "launch_capability_state": "consumed-before-provider-post",
                    "created_at_epoch": clock(),
                },
            )
        try:
            launch_response = recorder.send_prepared(
                prepared_launch,
                final_admission=final_launch_admission,
            )
        except ModelMetadataReceiptError as exc:
            raise T09ProviderError(
                "V12 model metadata receipt failed at the provider launch boundary"
            ) from exc
        except ProviderOutcomeUnknown:
            write_exclusive(
                private_root / "LAUNCH_OUTCOME_UNKNOWN.json",
                {
                    "schema_version": "0.1.0",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "instance_name": contract.instance_name,
                    "launch_body_sha256": _sha256_bytes(
                        _canonical_bytes(_launch_body(contract=contract))
                    ),
                    "second_launch_forbidden": True,
                    "required_action": (
                        "inspect the Lambda console for the unique exact instance name; "
                        "terminate any matching instance; verify no matching instance remains"
                    ),
                },
            )
            seal_source_bundle(entry_root, contract=contract)
            raise T09ProviderError(
                "launch outcome is unknown; do not launch again; perform the exact "
                "console cleanup in LAUNCH_OUTCOME_UNKNOWN.json"
            ) from None
        raw_launch = _mapping(
            json.loads(launch_response.body),
            label="raw launch response",
        )
        launch_data = _mapping(_envelope(raw_launch, label="raw launch"), label="raw launch data")
        instance_ids = [
            _string(item, label="instance ID")
            for item in _list(launch_data.get("instance_ids"), label="launch IDs")
        ]
        if len(instance_ids) != 1:
            if instance_ids:
                _close_multi_instance_launch_incident(
                    contract=contract,
                    recorder=recorder,
                    entry_root=entry_root,
                    private_root=private_root,
                    instance_ids=instance_ids,
                    clock=clock,
                    sleeper=sleeper,
                )
            write_exclusive(
                private_root / "LAUNCH_OUTCOME_UNKNOWN.json",
                {
                    "schema_version": "0.1.0",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "instance_name": contract.instance_name,
                    "launch_body_sha256": _sha256_bytes(
                        _canonical_bytes(_launch_body(contract=contract))
                    ),
                    "second_launch_forbidden": True,
                    "required_action": (
                        "inspect the Lambda console for the unique exact instance name; "
                        "terminate every match; verify no matching instance remains"
                    ),
                },
            )
            seal_source_bundle(entry_root, contract=contract)
            raise T09ProviderError(
                "launch returned no trustworthy exact-one identity; do not launch again"
            )
        instance_id = instance_ids[0]
        owned_hash = _instance_identity_sha256(instance_id)
        provisional_binding: dict[str, object] = {
            "schema_version": "0.1.0",
            "plan_id": contract.plan_id,
            "host_run_id": contract.host_run_id,
            "package_commit": package_commit,
            "plan_sha256": plan_sha256,
            "private_instance_id": instance_id,
            "owned_instance_identity_sha256": owned_hash,
            "instance_name": contract.instance_name,
            "launch_slot": launch_slot,
            "replacement_eligibility_sha256": replacement_eligibility_sha256,
            "further_launch_forbidden": launch_slot == contract.max_launch_count,
            "private_operational_state_not_for_archive": True,
        }
        launch_send_starts = [
            event.get("send_started_at_epoch")
            for event in _journal_events(entry_root)
            if event.get("event") == "send-started" and event.get("operation") == "launch"
        ]
        if (
            len(launch_send_starts) == 1
            and isinstance(launch_send_starts[0], (int, float))
            and not isinstance(launch_send_starts[0], bool)
        ):
            # This value comes from the already-fsynced provider request
            # journal.  Retaining it here lets exact-owner cleanup complete
            # even if the richer cleanup journal cannot be bootstrapped.
            provisional_binding["lambda_started_at_epoch"] = launch_send_starts[0]
        try:
            # The exact owner and every basic cleanup target are durable before
            # package transition, source upload, image operation, artifact-root
            # mutation, secret, container, browser, or campaign state.  If this
            # journal bootstrap itself fails, the same protective block still
            # terminates the exact owner from the durable launch journal.
            initial_cleanup_state = _initial_preflight_cleanup_state(
                contract=contract,
                entry_root=entry_root,
                private_root=private_root,
                package_commit=package_commit,
                plan_sha256=plan_sha256,
                instance_id=instance_id,
                launch_slot=launch_slot,
                replacement_eligibility_sha256=replacement_eligibility_sha256,
                clock=clock,
            )
            cleanup_journal = EarlyCleanupJournal(private_root / "preflight-cleanup-state")
            cleanup_journal.advance_lifecycle(
                CleanupLifecycleStage.PACKAGE_TRANSITION,
                clock=clock,
            )
            provisional_binding = _provisional_owner_binding(
                contract=contract,
                entry_root=entry_root,
                capability_path=capability_path,
                package_commit=package_commit,
                plan_sha256=plan_sha256,
                private_root=private_root,
                instance_id=instance_id,
                launch_slot=launch_slot,
                replacement_eligibility_sha256=replacement_eligibility_sha256,
            )
            if (
                provisional_binding.get("private_instance_id")
                != initial_cleanup_state.get("private_instance_id")
                or provisional_binding.get("owned_instance_identity_sha256")
                != initial_cleanup_state.get("owned_instance_identity_sha256")
                or provisional_binding.get("lambda_started_at_epoch")
                != initial_cleanup_state.get("lambda_started_at_epoch")
            ):
                raise T09ProviderError("provisional owner drifted from initial cleanup state")
            cleanup_journal.advance_lifecycle(
                CleanupLifecycleStage.SOURCE_STAGING,
                clock=clock,
            )
            write_exclusive(
                private_root / "provisional-owned-state.json",
                provisional_binding,
            )
            write_exclusive(
                private_root / "owned-state.json",
                {
                    "schema_version": "0.1.0",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "package_commit": package_commit,
                    "plan_sha256": plan_sha256,
                    "instance_id": instance_id,
                    "owned_instance_identity_sha256": owned_hash,
                    "instance_name": contract.instance_name,
                    "launch_slot": launch_slot,
                    "replacement_eligibility_sha256": replacement_eligibility_sha256,
                    "lambda_started_at_epoch": provisional_binding["lambda_started_at_epoch"],
                },
            )
            for _ in range(MAX_ENTRY_POLLS):
                sleeper(POLL_SECONDS)
                active_response = recorder.request("active-instances", "GET", "/api/v1/instances")
                rows = _instance_rows(
                    _response_documents(entry_root)["active-instances"][-1][1],
                    label="active instances",
                )
                active = [
                    row
                    for row in rows
                    if row.get("instance_identity_sha256") == owned_hash
                    and row.get("name") == contract.instance_name
                    and row.get("status") == "active"
                ]
                if len(active) == 1:
                    raw_active = _mapping(
                        json.loads(active_response.body), label="raw active response"
                    )
                    raw_rows = _instance_rows(raw_active, label="raw active instances")
                    raw_match = [
                        row
                        for row in raw_rows
                        if row.get("id") == instance_id
                        and row.get("name") == contract.instance_name
                        and row.get("status") == "active"
                    ]
                    if len(raw_match) != 1:
                        raise T09ProviderError(
                            "active instance projection drifted from raw response"
                        )
                    ip_value = raw_match[0].get("ip")
                    if not isinstance(ip_value, str) or not ip_value:
                        raise T09ProviderError("active owned instance lacks its private SSH target")
                    state = _load_json(private_root / "owned-state.json", maximum_bytes=65_536)
                    state["ssh_target"] = ip_value
                    write_exclusive(private_root / "owned-state-active.json", state)
                    break
            else:
                raise T09ProviderError("owned instance did not become active in the bounded window")
            owned_started = _number(
                provisional_binding["lambda_started_at_epoch"], label="owned Lambda start"
            )
            write_exclusive(
                entry_root / "campaign-launch-binding.json",
                {
                    "schema_version": "0.1.0",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "package_commit": package_commit,
                    "launch_slot": launch_slot,
                    # Retry 5 gives every launch its own infrastructure-preflight
                    # origin.  Prior active time is carried separately below and
                    # offline gaps never consume a billable or empirical clock.
                    "campaign_started_at_epoch": owned_started,
                    "owned_lambda_started_at_epoch": owned_started,
                    "prior_lambda_duration_seconds": (
                        replacement_eligibility["prior_lambda_duration_seconds"]
                        if replacement_eligibility is not None
                        else 0.0
                    ),
                    "prior_lambda_cost_usd": (
                        replacement_eligibility["prior_lambda_cost_usd"]
                        if replacement_eligibility is not None
                        else 0.0
                    ),
                    "replacement_eligibility_sha256": replacement_eligibility_sha256,
                    **(
                        {"model_metadata_receipt_sha256": (model_metadata_receipt_sha256_value)}
                        if model_metadata_receipt_sha256_value is not None
                        else {}
                    ),
                    "replacement_eligibility_preempirical_source_manifest_sha256": (
                        replacement_eligibility.get("source_manifest_sha256")
                        if replacement_eligibility is not None
                        else None
                    ),
                    "normalized_slot2_authority_tree_manifest_sha256": (
                        file_sha256(private_root / "slot2-eligibility-source/source-manifest.json")
                        if replacement_eligibility is not None
                        else None
                    ),
                },
            )
            handoff_state = cleanup_journal.load()
            write_exclusive(
                entry_root / "early-cleanup-handoff.json",
                {
                    "schema_version": "1.0.0",
                    "journal_id": handoff_state.journal_id,
                    "journal_sequence": handoff_state.sequence,
                    "journal_version_sha256": cleanup_journal.latest_version_sha256(),
                    "provider_instance_identity_sha256": (
                        handoff_state.provider_instance_identity_sha256
                    ),
                    "transfer_policy": ("copy-exact-hash-chain-before-remote-resource-mutation"),
                },
            )
            seal_source_bundle(entry_root, contract=contract)
            entry_receipt = create_entry_receipt(
                entry_root,
                contract=contract,
                package_commit=package_commit,
                plan_sha256=plan_sha256,
                expected_public_key=expected_public_key,
                expected_public_ipv4=expected_public_ipv4,
                model_metadata_receipt_sha256=model_metadata_receipt_sha256_value,
            )
        except BaseException as entry_exc:
            try:
                _cleanup_provisional_owner(
                    contract=contract,
                    transport=transport,
                    credential=credential,
                    private_root=private_root,
                    provisional_binding=provisional_binding,
                    clock=clock,
                    sleeper=sleeper,
                )
            except BaseException as cleanup_exc:
                with contextlib.suppress(BaseException):
                    _write_provisional_console_marker(
                        contract=contract,
                        private_root=private_root,
                        instance_id=instance_id,
                        owned_identity=owned_hash,
                        reason=type(cleanup_exc).__name__,
                        clock=clock,
                    )
                raise T09ProviderError(
                    "post-launch entry failed and exact-owner cleanup requires the durable "
                    "console action; do not launch again"
                ) from cleanup_exc
            if _provisional_replacement_permitted(contract, launch_slot=launch_slot):
                raise T09ProviderError(
                    "post-launch entry failed; the exact launched instance was closed; "
                    "a replacement is permitted only when the retained source-bound "
                    "eligibility receipt validates the closed slot as zero-use"
                ) from entry_exc
            raise T09ProviderError(
                "post-launch entry failed; the exact launched instance was closed; "
                "the selected provider contract has no remaining launch authority"
            ) from entry_exc
        return entry_receipt
    finally:
        _destroy_bytearray(credential)


def closeout_campaign(
    *,
    contract: T09ProviderContract,
    repository: Path,
    package_commit: str,
    authorization_ledger: Path,
    dotenv: Path,
    private_root: Path,
    transport: ProviderTransport,
    preempirical_receipt: Path | None = None,
    preempirical_source_root: Path | None = None,
    empirical_clock_manifest: Path | None = None,
    remote_cleanup_journal: Path | None = None,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> Path:
    repository = repository.resolve(strict=True)
    validate_cleanup_authority_ledger(
        authorization_ledger,
        contract=contract,
        repository=repository,
        package_commit=package_commit,
    )
    lifecycle = load_campaign_lifecycle(repository, contract=contract)
    entry_receipt_path = private_root / "entry-source/entry-receipt.json"
    if (preempirical_receipt is None) != (preempirical_source_root is None):
        raise T09ProviderError("pre-empirical replacement evidence is incomplete")
    replacement_evidence_validated = False
    retained_preempirical_source: Path | None = None
    validated_host_disposition: dict[str, object] | None = None
    if preempirical_receipt is not None and preempirical_source_root is not None:
        if preempirical_receipt.name != "preempirical-disposition.json":
            raise T09ProviderError("pre-empirical receipt identity is unexpected")
        entry_for_replacement = _load_json(entry_receipt_path, maximum_bytes=65_536)
        if entry_for_replacement.get("launch_slot") not in range(1, contract.max_launch_count):
            raise T09ProviderError("only a nonterminal preflight slot can authorize replacement")
        validated_host_disposition = _validate_host_preempirical_disposition(
            preempirical_receipt,
            preempirical_source_root,
            contract=contract,
            package_commit=package_commit,
            entry_receipt_sha256=file_sha256(entry_receipt_path),
            provider_preflight_started_at_epoch=_number(
                entry_for_replacement.get("provider_preflight_started_at_epoch"),
                label="provider preflight start",
            ),
        )
        retained_preempirical_source = _retain_host_preempirical_source(
            preempirical_source_root,
            private_root,
        )
        retained_host_disposition = _validate_host_preempirical_disposition(
            retained_preempirical_source / preempirical_receipt.name,
            retained_preempirical_source,
            contract=contract,
            package_commit=package_commit,
            entry_receipt_sha256=file_sha256(entry_receipt_path),
            provider_preflight_started_at_epoch=_number(
                entry_for_replacement.get("provider_preflight_started_at_epoch"),
                label="provider preflight start",
            ),
        )
        if retained_host_disposition != validated_host_disposition:
            raise T09ProviderError("retained pre-empirical source changed during copy")
        replacement_evidence_validated = True
    provisional_path = private_root / "provisional-owned-state.json"
    initial_cleanup_path = private_root / "preflight-cleanup-state"
    campaign_cleanup_journal: EarlyCleanupJournal | None = None
    if initial_cleanup_path.is_dir():
        plan_path = repository / contract.provider_profile_path
        campaign_cleanup_journal = _cleanup_journal_for_closeout(
            contract=contract,
            private_root=private_root,
            package_commit=package_commit,
            plan_sha256=file_sha256(plan_path),
            remote_cleanup_journal=remote_cleanup_journal,
        )
    elif remote_cleanup_journal is not None:
        raise T09ProviderError("remote cleanup continuation has no provider journal prefix")
    if (
        not entry_receipt_path.is_file()
        and not provisional_path.is_file()
        and initial_cleanup_path.is_dir()
    ):
        plan_path = repository / contract.provider_profile_path
        initial_cleanup = _validate_initial_preflight_cleanup_state(
            initial_cleanup_path,
            contract=contract,
            package_commit=package_commit,
            plan_sha256=file_sha256(plan_path),
        )
        closed_path = private_root / "PROVISIONAL_OWNER_CLOSED.json"
        if closed_path.is_file():
            closed = _load_json(closed_path, maximum_bytes=65_536)
            if (
                closed.get("private_instance_id") != initial_cleanup.get("private_instance_id")
                or closed.get("owned_instance_identity_sha256")
                != initial_cleanup.get("owned_instance_identity_sha256")
                or closed.get("provider_disposition") != "absent"
                or closed.get("zero_t09_instances") is not True
                or closed.get("security_restored") is not True
            ):
                raise T09ProviderError("initial cleanup closeout marker drifted")
            return closed_path
        instance_id = _string(
            initial_cleanup.get("private_instance_id"), label="initial cleanup instance ID"
        )
        owned_identity = _string(
            initial_cleanup.get("owned_instance_identity_sha256"),
            label="initial cleanup owned identity",
        )
        credential = load_dotenv_assignment(dotenv, "LAMBDA_API_KEY")
        try:
            _cleanup_provisional_owner(
                contract=contract,
                transport=transport,
                credential=credential,
                private_root=private_root,
                provisional_binding=initial_cleanup,
                clock=clock,
                sleeper=sleeper,
            )
        except BaseException as exc:
            with contextlib.suppress(BaseException):
                _write_provisional_console_marker(
                    contract=contract,
                    private_root=private_root,
                    instance_id=instance_id,
                    owned_identity=owned_identity,
                    reason=type(exc).__name__,
                    clock=clock,
                )
            raise
        finally:
            _destroy_bytearray(credential)
        return private_root / "PROVISIONAL_OWNER_CLOSED.json"
    if not entry_receipt_path.is_file() and provisional_path.is_file():
        provisional = _load_source_validated_provisional_owner(
            private_root,
            contract=contract,
            repository=repository,
            package_commit=package_commit,
        )
        closed_path = private_root / "PROVISIONAL_OWNER_CLOSED.json"
        if closed_path.is_file():
            closed = _load_json(closed_path, maximum_bytes=65_536)
            if (
                closed.get("private_instance_id") != provisional.get("private_instance_id")
                or closed.get("owned_instance_identity_sha256")
                != provisional.get("owned_instance_identity_sha256")
                or closed.get("provider_disposition") != "absent"
                or closed.get("zero_t09_instances") is not True
                or closed.get("security_restored") is not True
                or closed.get("replacement_launch_eligibility_pending")
                != _provisional_replacement_permitted(
                    contract,
                    launch_slot=_integer(
                        provisional.get("launch_slot"),
                        label="provisional launch slot",
                    ),
                )
            ):
                raise T09ProviderError("provisional closeout marker drifted")
            return closed_path
        instance_id = _string(
            provisional.get("private_instance_id"), label="provisional private instance ID"
        )
        owned_identity = _string(
            provisional.get("owned_instance_identity_sha256"),
            label="provisional owned identity",
        )
        credential = load_dotenv_assignment(dotenv, "LAMBDA_API_KEY")
        try:
            _cleanup_provisional_owner(
                contract=contract,
                transport=transport,
                credential=credential,
                private_root=private_root,
                provisional_binding=provisional,
                clock=clock,
                sleeper=sleeper,
            )
        except BaseException as exc:
            with contextlib.suppress(BaseException):
                _write_provisional_console_marker(
                    contract=contract,
                    private_root=private_root,
                    instance_id=instance_id,
                    owned_identity=owned_identity,
                    reason=type(exc).__name__,
                    clock=clock,
                )
            raise
        finally:
            _destroy_bytearray(credential)
        for name in ("owned-state-active.json", "owned-state.json"):
            _destroy_operational_file(private_root / name)
        return closed_path
    state = _load_source_validated_owned_state(
        private_root,
        contract=contract,
        repository=repository,
        package_commit=package_commit,
    )
    if campaign_cleanup_journal is None:
        raise T09ProviderError("durable provider cleanup journal is unavailable")
    instance_id = _string(state.get("instance_id"), label="owned instance ID")
    owned_identity = _string(
        state.get("owned_instance_identity_sha256"), label="owned instance identity"
    )
    entry_for_clock = _load_json(entry_receipt_path, maximum_bytes=65_536)
    started = _number(entry_for_clock["lambda_started_at_epoch"], label="campaign start")
    closeout_root = private_root / "closeout-source"
    closeout_root.mkdir(mode=0o700, exist_ok=False)
    if validated_host_disposition is not None:
        write_exclusive(
            closeout_root / "preflight-failure-timing.json",
            {
                "schema_version": "0.1.0",
                "plan_id": contract.plan_id,
                "host_run_id": contract.host_run_id,
                "preflight_failure_sha256": validated_host_disposition["preflight_failure_sha256"],
                "provider_preflight_started_at_epoch": validated_host_disposition[
                    "provider_preflight_started_at_epoch"
                ],
                "preflight_iteration_started_at_epoch": validated_host_disposition[
                    "preflight_iteration_started_at_epoch"
                ],
                "failed_at_epoch": validated_host_disposition["preflight_failed_at_epoch"],
                "preflight_iteration_elapsed_seconds": validated_host_disposition[
                    "preflight_iteration_elapsed_seconds"
                ],
                "provider_instance_elapsed_seconds": validated_host_disposition[
                    "provider_instance_elapsed_seconds"
                ],
                "termination_dispatch_deadline_epoch": validated_host_disposition[
                    "termination_dispatch_deadline_epoch"
                ],
                "preflight_engineering_state": validated_host_disposition[
                    "preflight_engineering_state"
                ],
            },
        )
    if empirical_clock_manifest is not None:
        source_manifest = empirical_clock_manifest.resolve(strict=True)
        metadata = source_manifest.stat(follow_symlinks=False)
        if (
            source_manifest.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size > 1_048_576
        ):
            raise T09ProviderError("empirical clock manifest metadata is unsafe")
        destination = closeout_root / "empirical-clock-manifest.json"
        with source_manifest.open("rb") as source, destination.open("xb") as target:
            shutil.copyfileobj(source, target, 1_048_576)
            target.flush()
            os.fsync(target.fileno())
        destination.chmod(0o600)
    write_exclusive(
        closeout_root / "owned-state-binding.json",
        {
            "schema_version": "0.1.0",
            "plan_id": contract.plan_id,
            "host_run_id": contract.host_run_id,
            "package_commit": package_commit,
            "owned_instance_identity_sha256": state["owned_instance_identity_sha256"],
            "lambda_started_at_epoch": state["lambda_started_at_epoch"],
        },
    )
    credential = load_dotenv_assignment(dotenv, "LAMBDA_API_KEY")
    recorder = RequestRecorder(closeout_root, transport, credential, clock)
    try:
        termination_sent = False
        for _post_index in range(MAX_TERMINATION_POSTS):
            if not termination_sent:
                write_exclusive(
                    closeout_root / "termination-intent.json",
                    {
                        "schema_version": "0.1.0",
                        "owned_instance_identity_sha256": state["owned_instance_identity_sha256"],
                        "termination_target_identity_sha256": state[
                            "owned_instance_identity_sha256"
                        ],
                        "send_started_at_epoch": clock(),
                        "campaign_elapsed_seconds": clock() - started,
                        "termination_cutoff_seconds": lifecycle.termination_cutoff_seconds,
                    },
                )
                termination_sent = True
            # Once an exact-target POST crosses send-start, only fresh GETs can
            # determine whether a recovery POST is needed.  This is cleanup
            # recovery, never a scientific retry.
            with contextlib.suppress(T09ProviderError):
                recorder.request(
                    "terminate",
                    "POST",
                    "/api/v1/instance-operations/terminate",
                    body=_terminate_body(instance_id),
                    target_identity_sha256=_string(
                        owned_identity,
                        label="owned instance identity",
                    ),
                )
            for _ in range(MAX_TERMINATION_POLLS // MAX_TERMINATION_POSTS):
                sleeper(POLL_SECONDS)
                recorder.request("termination-instances", "GET", "/api/v1/instances")
                rows = _instance_rows(
                    _response_documents(closeout_root)["termination-instances"][-1][1],
                    label="termination instances",
                )
                owned = [
                    row for row in rows if row.get("instance_identity_sha256") == owned_identity
                ]
                exact_name_rows = [row for row in rows if row.get("name") == contract.instance_name]
                # Do not stop at a terminal row and later label it as zero.  Keep
                # polling until both the exact owned identity and every exact-name
                # row are absent from the all-page inventory.
                if not owned and not exact_name_rows:
                    break
            else:
                continue
            break
        else:
            raise T09ProviderError("owned instance did not terminate after bounded recovery")
        recorder.request("post-global-firewall", "GET", "/api/v1/firewall-rulesets/global")
        sleeper(1.0)
        recorder.request("post-regional-rulesets", "GET", "/api/v1/firewall-rulesets")
        seal_source_bundle(closeout_root, contract=contract)
        plan_path = repository / contract.provider_profile_path
        entry_path = private_root / "entry-source/entry-receipt.json"
        empirical_clock_document = (
            _load_json(
                closeout_root / "empirical-clock-manifest.json",
                maximum_bytes=1_048_576,
            )
            if (closeout_root / "empirical-clock-manifest.json").is_file()
            else None
        )
        receipt = create_closeout_receipt(
            closeout_root,
            contract=contract,
            entry_receipt_path=entry_path,
            entry_source_root=private_root / "entry-source",
            package_commit=package_commit,
            plan_sha256=file_sha256(plan_path),
            lifecycle=lifecycle,
            empirical_clock_manifest=empirical_clock_document,
        )
        closeout_document = _load_json(receipt, maximum_bytes=65_536)
        _record_provider_closeout_cleanup(
            campaign_cleanup_journal,
            private_root=private_root,
            closeout_receipt=closeout_document,
            clock=clock,
        )
        entry_document = _load_json(entry_path, maximum_bytes=65_536)
        if replacement_evidence_validated:
            if retained_preempirical_source is None:
                raise T09ProviderError("replacement source binding is unavailable")
            if (
                closeout_document.get("terminal_or_absent") is not True
                or closeout_document.get("zero_t09_instances") is not True
                or closeout_document.get("security_restored") is not True
            ):
                raise T09ProviderError("closed host cannot authorize replacement launch")
            eligibility = {
                "schema_version": "0.1.0",
                "plan_id": contract.plan_id,
                "host_run_id": contract.host_run_id,
                "package_commit": package_commit,
                "closed_launch_slot": entry_document["launch_slot"],
                "entry_receipt_sha256": file_sha256(entry_path),
                "closeout_receipt_sha256": file_sha256(receipt),
                "host_preempirical_receipt_sha256": file_sha256(
                    retained_preempirical_source / "preempirical-disposition.json"
                ),
                "host_preempirical_source_manifest_sha256": file_sha256(
                    retained_preempirical_source / "source-manifest.json"
                ),
                "source_manifest_sha256": file_sha256(
                    retained_preempirical_source / "source-manifest.json"
                ),
                "campaign_started_at_epoch": entry_document["lambda_started_at_epoch"],
                "prior_lambda_duration_seconds": closeout_document["lambda_duration_seconds"],
                "prior_lambda_cost_usd": closeout_document["lambda_list_cost_usd"],
                "empirical_attempts_entered": 0,
                "model_task_requests": 0,
                "task_browser_actions": 0,
                "replacement_image_build_count": 0,
                "replacement_image_import_count": retained_host_disposition[
                    "replacement_image_import_count"
                ],
                "replacement_image_id": retained_host_disposition["replacement_image_id"],
                "replacement_image_archive_sha256": retained_host_disposition[
                    "replacement_image_archive_sha256"
                ],
                "slot2_image_archive_sha256": SLOT1_IMAGE_ARCHIVE_SHA256,
                "slot2_image_archive_bytes": SLOT1_IMAGE_ARCHIVE_BYTES,
                "slot2_expected_image_id": SLOT1_REPLACEMENT_IMAGE_ID,
                "slot2_image_import_required": True,
                "slot2_additional_image_build_count": 0,
                "terminal_or_absent": True,
                "zero_t09_instances": True,
                "security_restored": True,
                "next_replacement_launch_permitted": (
                    _integer(entry_document["launch_slot"], label="closed launch slot")
                    < contract.max_launch_count
                ),
            }
            write_exclusive(private_root / "replacement-launch-eligibility.json", eligibility)
        for name in (
            "owned-state-active.json",
            "owned-state.json",
            "provisional-owned-state.json",
        ):
            _destroy_operational_file(private_root / name)
        return receipt
    except BaseException as exc:
        with contextlib.suppress(BaseException):
            _record_provider_closeout_failure(
                campaign_cleanup_journal,
                private_root=private_root,
                error=exc,
                clock=clock,
            )
        marker = private_root / "CLOSEOUT_REQUIRES_CONSOLE.json"
        if not marker.exists():
            write_exclusive(
                marker,
                {
                    "schema_version": "0.1.0",
                    "plan_id": contract.plan_id,
                    "host_run_id": contract.host_run_id,
                    "private_instance_id": instance_id,
                    "instance_name": contract.instance_name,
                    "owned_instance_identity_sha256": owned_identity,
                    "error_type": type(exc).__name__,
                    "required_action": (
                        "in the Lambda console, terminate the exact private instance ID if "
                        "present; verify that ID and every exact T09 instance-name match are "
                        "terminal or absent; do not launch again"
                    ),
                    "private_operational_state_not_for_archive": True,
                },
            )
        raise
    finally:
        _destroy_bytearray(credential)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument(
        "--provider-contract",
        choices=("V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11", "V12"),
        required=True,
    )
    result.add_argument("--repository", type=Path, required=True)
    result.add_argument("--package-commit", required=True)
    # The local V12 metadata gate deliberately does not need Lambda authority,
    # Lambda credentials, or a provider private root.  Keep those lifecycle
    # paths optional at parse time and require them only on operations that use
    # them, so the narrow preflight command cannot be accidentally coupled to
    # the mutation path.
    result.add_argument("--authorization-ledger", type=Path)
    result.add_argument("--dotenv", type=Path)
    result.add_argument("--private-root", type=Path)
    operations = result.add_subparsers(dest="operation", required=True)
    launch = operations.add_parser("launch")
    launch.add_argument("--public-ipv4-file", type=Path, required=True)
    launch.add_argument("--ssh-public-key-file", type=Path, required=True)
    launch.add_argument("--launch-slot", type=int, choices=tuple(range(1, 9)), default=1)
    launch.add_argument("--prior-private-root", type=Path)
    launch.add_argument("--slot1-image-archive", type=Path)
    launch.add_argument("--model-metadata-receipt", type=Path)
    metadata = operations.add_parser("model-metadata-preflight")
    metadata.add_argument("--openai-dotenv", type=Path, required=True)
    metadata.add_argument("--authorization-overlay", type=Path, required=True)
    metadata.add_argument("--output", type=Path, required=True)
    closeout = operations.add_parser("closeout")
    closeout.add_argument("--preempirical-receipt", type=Path)
    closeout.add_argument("--preempirical-source-root", type=Path)
    closeout.add_argument("--empirical-clock-manifest", type=Path)
    closeout.add_argument("--remote-cleanup-journal", type=Path)
    eligibility = operations.add_parser("derive-replacement-eligibility")
    eligibility.add_argument("--prior-private-root", type=Path, required=True)
    eligibility.add_argument("--slot1-failure-archive", type=Path, required=True)
    eligibility.add_argument("--slot1-image-archive", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    contract = provider_contract(args.provider_contract)
    if args.operation == "model-metadata-preflight":
        if contract is not V12_PROVIDER_CONTRACT:
            raise T09ProviderError("model metadata preflight requires the V12 provider contract")
        model_metadata_preflight(
            contract=contract,
            repository=args.repository,
            package_commit=args.package_commit,
            authorization_overlay=args.authorization_overlay,
            openai_dotenv=args.openai_dotenv,
            output=args.output,
        )
        return 0
    if args.operation in {"launch", "closeout"} and not all(
        isinstance(getattr(args, field_name, None), Path)
        for field_name in ("authorization_ledger", "dotenv", "private_root")
    ):
        raise T09ProviderError(
            f"{args.operation} requires --authorization-ledger, --dotenv, and --private-root"
        )
    transport = LambdaTransport()
    if args.operation == "launch":
        launch_campaign(
            contract=contract,
            repository=args.repository,
            package_commit=args.package_commit,
            authorization_ledger=args.authorization_ledger,
            dotenv=args.dotenv,
            private_root=args.private_root,
            public_ipv4_file=args.public_ipv4_file,
            ssh_public_key_file=args.ssh_public_key_file,
            transport=transport,
            launch_slot=args.launch_slot,
            prior_private_root=args.prior_private_root,
            slot1_image_archive=args.slot1_image_archive,
            model_metadata_receipt=args.model_metadata_receipt,
        )
        return 0
    if args.operation == "closeout":
        closeout_campaign(
            contract=contract,
            repository=args.repository,
            package_commit=args.package_commit,
            authorization_ledger=args.authorization_ledger,
            dotenv=args.dotenv,
            private_root=args.private_root,
            transport=transport,
            preempirical_receipt=args.preempirical_receipt,
            preempirical_source_root=args.preempirical_source_root,
            empirical_clock_manifest=args.empirical_clock_manifest,
            remote_cleanup_journal=args.remote_cleanup_journal,
        )
        return 0
    if args.operation == "derive-replacement-eligibility":
        derive_built_image_replacement_eligibility(
            contract=contract,
            repository=args.repository,
            package_commit=args.package_commit,
            prior_private_root=args.prior_private_root,
            slot1_failure_archive=args.slot1_failure_archive,
            slot1_image_archive=args.slot1_image_archive,
        )
        return 0
    raise T09ProviderError("unknown provider lifecycle operation")


if __name__ == "__main__":
    raise SystemExit(main())
