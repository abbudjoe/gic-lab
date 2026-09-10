"""Live-capable production assembly for the shared Category 3 controller.

This module owns package validation, state transitions, budgets, accounting, and
effect-output validation. It contains no deterministic credentials, canned task
answers, synthetic clock, fault-plan branches, or provider/host implementation.
Those environmental operations are supplied through ``LowLevelEffects``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import subprocess
import tarfile
import threading
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import asdict, replace
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path, PurePosixPath
from types import MappingProxyType, ModuleType
from typing import Final, Literal, NoReturn, cast

import yaml
from jsonschema import Draft202012Validator

from giclab.control.adapters import (
    AdapterCall,
    AdapterFailure,
    AmbiguousProviderOutcome,
    Category3Adapters,
    CleanupInterrupted,
    ConsumedConditionFailure,
    EssentialFailureRecord,
    FirstPairCheckpointDisposition,
    FirstPairCheckpointResult,
    ImplementationFlavor,
    MetadataEnvelope,
    PrivacyUnresolved,
    ReplacementEligibleFailure,
    StructuralPrivacyFinding,
    TerminationUnavailable,
    UndeclaredAdapterCall,
)
from giclab.control.consumers import (
    CONTROL_CONSUMERS,
    ConsumerResolution,
    resolve_control_consumers,
)
from giclab.control.effects import (
    EFFECT_PROTOCOL_VERSION,
    MAX_ESSENTIAL_FAILURE_BYTES,
    MAX_ESSENTIAL_FAILURE_FILES,
    MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES,
    CleanupExecutionReceipt,
    CleanupExecutionRequest,
    ConditionAction,
    ConditionAmbiguousSend,
    ConditionBridgeEvidence,
    ConditionBridgePrefixEvidence,
    ConditionEventObserver,
    ConditionExecutionRequest,
    ConditionFailureClass,
    ConditionFailureExportInterrupted,
    ConditionFailureExportReceipt,
    ConditionFailureExportRequest,
    ConditionFailurePreservationRequest,
    ConditionInfrastructureFailureOutcome,
    ConditionKnownProviderError,
    ConditionKnownTransportError,
    ConditionModelCall,
    ConditionModelResponse,
    ConditionProcessOutcome,
    ConditionResponseAccountingIncomplete,
    ConditionSend,
    EffectAuthorityGrant,
    EffectAuthorityKind,
    EffectAuthorizationContext,
    EffectExecutionMode,
    EvaluatorExecutionOutcome,
    EvaluatorExecutionRequest,
    FinalizerExecutionOutcome,
    FinalizerExecutionRequest,
    HeldArtifact,
    HeldEffectSource,
    HeldTransactionRoot,
    HostPackageTransferReceipt,
    HostPackageTransferRejected,
    HostPackageTransferRequest,
    HostPhaseBinding,
    HostPreflightReceipt,
    HostPreflightRejected,
    HostPreflightRequest,
    HostQualificationReceipt,
    HostQualificationRequest,
    HostTransferBinding,
    LocalPackageAssemblyReceipt,
    LocalPackageAssemblyRequest,
    LowLevelEffects,
    PackageRuntimeBudget,
    ProviderCostObservationRequest,
    ProviderCostReceipt,
    ProviderHandle,
    ProviderLifecycleCostProof,
    ProviderLifecycleInterval,
    RetainedConditionSource,
    RuntimeClock,
    ScientificFreezeReceipt,
    ScientificFreezeRequest,
    TrackedPackageMember,
    ValidatedLiveEffectAuthority,
    checked_deadline,
    finite_time,
    hold_sealed_artifact,
)
from giclab.control.registry_validation import resolve_registered_command_package
from giclab.control.remote_bridge import (
    RETAINED_FROZEN_MANIFEST_SCHEMA_VERSION,
    ConditionSessionBinding,
    RemoteBridgeError,
    condition_session_id,
    expected_condition_bridge_evidence,
    load_full_frozen_manifest,
    validate_condition_bridge_evidence,
    validate_full_dynamic_frozen_manifest,
    validate_postfreeze_receipt,
)
from giclab.harness import t09_model_metadata_receipt as metadata
from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness import t09_sira_pilot as pilot
from giclab.harness.campaign_output import (
    CampaignWriteAllowance,
    CampaignWriterRole,
    CleanupOutputAuthority,
    CleanupOutputBinding,
    campaign_cleanup_active,
    campaign_output_scope,
)
from giclab.harness.sira_gate_a import (
    ImmutableModelRouting,
    ProviderBudgetBoundary,
    ProviderBudgetCaps,
    ProviderBudgetExceeded,
    ProviderBudgetUsage,
    ProviderFailureDisposition,
    ProviderRequest,
    ProviderResponseReceiptError,
    ProviderResponseUsage,
)
from giclab.harness.t09_candidate_inputs import CandidateSourceSnapshot
from giclab.harness.t09_provider_contracts import (
    T09ProviderContract,
    T09ProviderContractError,
    load_provider_profile,
)
from giclab.registry import load_json, local_schema_registry

_RUNTIME_CONSUMERS: Final = {
    name: consumer
    for name, consumer in CONTROL_CONSUMERS.items()
    if name != "production_adapter_assembly"
}
_HEX40: Final = re.compile(r"^[a-f0-9]{40}$")
_HEX64: Final = re.compile(r"^[a-f0-9]{64}$")
_SAFE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_MAX_STAGE_ARCHIVE_BYTES: Final = 128 * 1024 * 1024
_MAX_STAGE_MEMBER_BYTES: Final = 32 * 1024 * 1024
_MAX_STAGE_MEMBERS: Final = 4096


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


def _identity(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _decimal_number(value: object, *, label: str) -> Decimal:
    """Parse one finite nonnegative decimal without binary-float arithmetic."""

    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise AdapterFailure(f"{label} is not an exact nonnegative decimal")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise AdapterFailure(f"{label} is not an exact nonnegative decimal") from exc
    if not result.is_finite() or result < 0:
        raise AdapterFailure(f"{label} is not an exact nonnegative decimal")
    return result


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _git_identity(repository: Path) -> tuple[str, str]:
    environment = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    identities: list[str] = []
    for revision in ("HEAD", "HEAD^{tree}"):
        completed = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", revision],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
            timeout=10,
        )
        identities.append(completed.stdout.decode("ascii").strip())
    return identities[0], identities[1]


def _tracked(repository: Path, relative: str) -> None:
    completed = subprocess.run(
        ["git", "-C", str(repository), "ls-files", "--error-unmatch", "--", relative],
        env={
            "PATH": os.defpath,
            "LANG": "C",
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
        },
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=10,
    )
    if completed.returncode != 0:  # pragma: no cover - check=True guard
        raise ValueError("package member is not tracked")


def _lexical_no_symlink_path(root: Path, path: Path, *, label: str) -> Path:
    approved = Path(os.path.abspath(root))
    candidate = Path(os.path.abspath(path))
    try:
        relative = candidate.relative_to(approved)
    except ValueError as exc:
        raise AdapterFailure(f"{label} is outside its exact effect transaction root") from exc
    current = approved
    for component in relative.parts:
        current /= component
        try:
            metadata_value = current.stat(follow_symlinks=False)
        except OSError as exc:
            raise AdapterFailure(f"{label} contains an unavailable path component") from exc
        if stat.S_ISLNK(metadata_value.st_mode):
            raise AdapterFailure(f"{label} contains a symlink path component")
    return candidate


def _safe_existing_file(root: Path, path: Path, *, label: str) -> Path:
    candidate = _lexical_no_symlink_path(root, path, label=label)
    metadata_value = candidate.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(metadata_value.st_mode)
        or metadata_value.st_uid != os.getuid()
        or metadata_value.st_nlink != 1
    ):
        raise AdapterFailure(f"{label} is not a single-link regular file")
    return candidate


def _safe_directory(root: Path, path: Path, *, label: str) -> Path:
    candidate = _lexical_no_symlink_path(root, path, label=label)
    metadata_value = candidate.stat(follow_symlinks=False)
    if not stat.S_ISDIR(metadata_value.st_mode) or metadata_value.st_uid != os.getuid():
        raise AdapterFailure(f"{label} is outside its exact effect transaction root")
    return candidate


def _require_sha(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise AdapterFailure(f"{label} is not an exact SHA-256")
    return value


def _caps_document(caps: ProviderBudgetCaps) -> dict[str, int | float]:
    return cast(dict[str, int | float], asdict(caps))


def retained_process_expectations(request: ConditionExecutionRequest) -> dict[str, object]:
    """Frozen command/policy inputs; process exit and answer remain observed facts."""
    return {
        "run_id": request.run_id,
        "retry_count": 0,
        "command_argv": list(request.command_argv),
        "command_sha256": request.command_sha256,
        "condition_plan_path": request.condition_plan_path,
        "condition_plan_sha256": request.condition_plan_sha256,
        "model_revision": request.model_revision,
        "service_tier": request.service_tier,
        "caps": _caps_document(request.caps),
    }


class _ValidatedRuntimeClock:
    """Fail-closed sampler that never compares monotonic and wall-time domains."""

    def __init__(self, source: RuntimeClock) -> None:
        self._source = source
        self._last_monotonic: float | None = None
        self._last_wall: float | None = None
        self.monotonic_samples: list[float] = []
        self.wall_samples: list[float] = []
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        value = finite_time(self._source.monotonic(), label="runtime monotonic time")
        if self._last_monotonic is not None and value < self._last_monotonic:
            raise AdapterFailure("runtime monotonic clock moved backward")
        self._last_monotonic = value
        self.monotonic_samples.append(value)
        return value

    def wall_time(self) -> float:
        value = finite_time(self._source.wall_time(), label="runtime wall time")
        if self._last_wall is not None and value < self._last_wall:
            raise AdapterFailure("runtime wall clock moved backward")
        self._last_wall = value
        self.wall_samples.append(value)
        return value

    def sleep(self, seconds: float) -> None:
        duration = finite_time(seconds, label="runtime sleep duration")
        checked_deadline(self.monotonic(), duration, label="runtime sleep")
        checked_deadline(self.wall_time(), duration, label="runtime sleep wall")
        self.sleep_calls.append(duration)
        self._source.sleep(duration)
        self.monotonic()
        self.wall_time()


class _MetadataChannelTransport:
    """Adapt the retained one-send API to the injected credential-bearing channel."""

    def __init__(self, effects: LowLevelEffects, clock: _ValidatedRuntimeClock) -> None:
        self._channel = effects.metadata_channel()
        self._clock = clock

    def get_model_metadata(
        self,
        model_id: str,
        *,
        credential: bytearray,
    ) -> metadata.ModelMetadataResponse:
        return self._channel.get_model_metadata(
            model_id=model_id,
            credential=credential,
            started_at=self._clock.wall_time(),
        )


@lru_cache(maxsize=1)
def _host_module_from(path_text: str) -> ModuleType:
    import importlib.util
    import sys

    path = Path(path_text)
    name = "giclab_t09_live_capable_production_host"
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError("retained host runtime cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _host_module(repository: Path) -> ModuleType:
    return _host_module_from(
        str(repository / "containers/sira-smoke/pragmatic/t09_remote_runner.py")
    )


def probe_production_adapter_assembly(
    repository: Path,
    contract: T09ProviderContract,
    *,
    source_inputs: CandidateSourceSnapshot | None = None,
) -> dict[str, object]:
    """Prove every production consumer and low-level channel is explicit."""

    resolutions = resolve_control_consumers(
        repository,
        contract,
        consumers=_RUNTIME_CONSUMERS,
        source_inputs=source_inputs,
    )
    required = {
        "lifecycle_resolver",
        "cleanup_handler",
        "command_package_loader",
        "control_root_resolver",
        "authorization_policy_resolver",
        "stage_identity_resolver",
    }
    if contract.capabilities.metadata_policy.value != "none":
        required.add("metadata_controller")
    if contract.max_launch_count > 1:
        required.add("replacement_authority_handler")
    if contract.capabilities.package_transition_policy.value != "none":
        required.add("package_transition_resolver")
    if contract.capabilities.provider_selector_policy.value != "none":
        required.add("provider_selector_resolver")
    if contract.effect_registration is not None:
        required.add("package_effect_loader")
    missing = sorted(name for name in required if resolutions.get(name) is None)
    if missing:
        raise ValueError("production adapter assembly lacks consumers: " + ", ".join(missing))
    return {
        "implementation_flavor": ImplementationFlavor.PRODUCTION_WRAPPER.value,
        "effect_protocol_version": EFFECT_PROTOCOL_VERSION,
        "resolved_consumers": sorted(required),
        "low_level_effects_injected": True,
        "controller_bypass": False,
        "controller_entrypoint": "giclab.control.category3:execute_category3_transaction",
        "production_assembly_entrypoint": (
            "giclab.control.production:build_production_adapter_assembly"
        ),
        "future_live_source_changes_required": False,
        "live_authority_factory_present": False,
        "authoritative_condition_accounting": "real-time-typed-event-observer",
        "required_low_level_channels": [
            "runtime_clock",
            "metadata_channel",
            "campaign_transport",
            "assemble_local_package",
            "transfer_package_to_host",
            "preflight_host",
            "qualify_host",
            "freeze_science",
            "execute_condition",
            "finalize_condition",
            "evaluate_condition",
            "cleanup_transaction",
        ],
    }


class _AccountingObserver(ConditionEventObserver):
    """Sole condition accountant around the retained provider budget boundary."""

    def __init__(
        self,
        *,
        run_id: str,
        model_revision: str,
        service_tier: str,
        boundary: ProviderBudgetBoundary,
        prior_call_ids: frozenset[str],
        prior_logical_call_ids: frozenset[str],
        clock: _ValidatedRuntimeClock,
        campaign_deadline_monotonic: float,
    ) -> None:
        self.run_id = run_id
        self.model_revision = model_revision
        self.service_tier = service_tier
        self.boundary = boundary
        self.prior_call_ids = prior_call_ids
        self.prior_logical_call_ids = prior_logical_call_ids
        self.clock = clock
        self.campaign_deadline_monotonic = campaign_deadline_monotonic
        self.call_ids: set[str] = set()
        self.logical_call_ids: set[str] = set()
        self.action_ids: set[str] = set()
        self.call_order: list[str] = []
        self.logical_call_order: list[str] = []
        self.action_order: list[str] = []
        self.action_terminal_states: dict[str, str] = {}
        self.output_total_bytes: int | None = None
        # Runtime totals describe the remote attempt. Controller-side copies and
        # carrier journals are disjoint occupancy, never spare remote allowance.
        self._output_lock = threading.RLock()
        self._remote_output_allowance = 0
        self._controller_output_allowance = 0
        self._controller_output_observed = 0
        self._controller_output_reconciled = 0
        self._failure_output_remaining: int | None = None
        self._closed_remote_output: int | None = None
        self._closed_remote_reconciled = False
        self._runtime_terminal_accounting: dict[str, object] | None = None
        self.exit_code: int | None = None
        self.completion_state: tuple[bool, str | None, str] | None = None
        self.raw_publication: tuple[str, str] | None = None

    def _assert_campaign_open(self) -> None:
        if self.clock.monotonic() > self.campaign_deadline_monotonic:
            raise ProviderBudgetExceeded("package campaign wall budget exceeded")

    @staticmethod
    def _disposition(exc: BaseException) -> ProviderFailureDisposition:
        if isinstance(exc, ConditionKnownProviderError):
            return ProviderFailureDisposition.PROVIDER_ERROR
        if isinstance(exc, ConditionKnownTransportError):
            return ProviderFailureDisposition.TRANSPORT_ERROR_KNOWN
        if isinstance(
            exc,
            (
                ConditionAmbiguousSend,
                ConditionResponseAccountingIncomplete,
                ProviderResponseReceiptError,
            ),
        ):
            return ProviderFailureDisposition.OUTCOME_UNKNOWN
        return ProviderFailureDisposition.OUTCOME_UNKNOWN

    def model_call(
        self,
        event: ConditionModelCall,
        send: ConditionSend,
        *,
        before_send: ConditionAction | None = None,
    ) -> str:
        self._assert_campaign_open()
        if self._runtime_terminal_accounting is not None or self._closed_remote_output is not None:
            raise AdapterFailure("model activity after terminal runtime accounting")
        if (
            event.call_id in self.call_ids
            or event.call_id in self.prior_call_ids
            or event.logical_call_id in self.logical_call_ids
            or event.logical_call_id in self.prior_logical_call_ids
            or _SAFE_ID.fullmatch(event.call_id) is None
            or _SAFE_ID.fullmatch(event.logical_call_id) is None
            or event.request.model != self.model_revision
            or event.request.service_tier != self.service_tier
            or event.request.implicit_transport_retries != 0
            or event.request.retry_kind != "initial"
        ):
            raise AdapterFailure("condition model-call identity or immutable routing drifted")
        self.call_ids.add(event.call_id)
        self.logical_call_ids.add(event.logical_call_id)
        self.call_order.append(event.call_id)
        self.logical_call_order.append(event.logical_call_id)

        def invoke(_request: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
            response = send()
            if not isinstance(response, ConditionModelResponse):
                raise ConditionResponseAccountingIncomplete(
                    "condition response lacks a typed usage receipt"
                )
            return response.content, response.usage

        return self.boundary.invoke(
            event.request,
            invoke,
            before_send=before_send,
            call_id=event.call_id,
            logical_call_id=event.logical_call_id,
            classify_failure=self._disposition,
        )

    def browser_action(self, *, action_id: str, perform: ConditionAction) -> None:
        self._assert_campaign_open()
        if self._runtime_terminal_accounting is not None or self._closed_remote_output is not None:
            raise AdapterFailure("browser activity after terminal runtime accounting")
        if _SAFE_ID.fullmatch(action_id) is None or action_id in self.action_ids:
            raise AdapterFailure("condition browser-action identity was reused or malformed")
        self.action_ids.add(action_id)
        self.action_order.append(action_id)
        try:
            self.boundary.record_browser_action(before_action=perform)
        except ProviderBudgetExceeded:
            self.action_terminal_states[action_id] = "admission-rejected"
            raise
        except BaseException:
            self.action_terminal_states[action_id] = "execution-failed"
            raise
        self.action_terminal_states[action_id] = "completed"

    def reserve_output_bytes(self, *, total_bytes: int) -> None:
        self._assert_campaign_open()
        with self._output_lock:
            if type(total_bytes) is not int or total_bytes < self._remote_output_allowance:
                raise AdapterFailure("remote output allowance moved backward")
            self.boundary.reserve_output_bytes(
                total_bytes=total_bytes + self._controller_output_allowance
            )
            self._remote_output_allowance = total_bytes

    def reserve_controller_output_bytes(self, *, total_bytes: int) -> None:
        """Fund disjoint controller output before the writer or producer exists."""
        self._assert_campaign_open()
        with self._output_lock:
            if type(total_bytes) is not int or total_bytes < self._controller_output_allowance:
                raise AdapterFailure("controller output allowance moved backward")
            self.boundary.reserve_output_bytes(
                total_bytes=total_bytes + self._remote_output_allowance
            )
            self._controller_output_allowance = total_bytes

    def prepare_failure_output(self) -> None:
        """Reserve the bounded envelope and its carrier copy before condition entry."""
        with self._output_lock:
            if self._failure_output_remaining is not None:
                raise AdapterFailure("failure output reserve was already established")
            count = 2 * MAX_ESSENTIAL_FAILURE_BYTES
            self.allocate_controller_output_bytes(count=count)
            self._failure_output_remaining = count

    def consume_failure_output_bytes(self, *, count: int) -> None:
        # A failed transport or expired campaign cannot mint more capacity, but
        # does not revoke the already-funded essential preservation allowance.
        with self._output_lock:
            if (
                type(count) is not int
                or count < 0
                or self._failure_output_remaining is None
                or count > self._failure_output_remaining
            ):
                raise AdapterFailure("essential writer exceeds its pre-entry allowance")
            self._failure_output_remaining -= count

    def allocate_controller_output_bytes(self, *, count: int) -> None:
        with self._output_lock:
            if type(count) is not int or count < 0:
                raise AdapterFailure("controller allocation increment is malformed")
            self.reserve_controller_output_bytes(
                total_bytes=self._controller_output_allowance + count
            )

    def observe_controller_output_bytes(self, *, count: int) -> None:
        with self._output_lock:
            if type(count) is not int or count < 0:
                raise AdapterFailure("controller observation increment is malformed")
            self.controller_output_bytes(total_bytes=self._controller_output_observed + count)

    def controller_output_bytes(self, *, total_bytes: int) -> None:
        """Retain actual controller writes separately from the runtime census.

        Publication follows the terminal protocol event. Reconcile these observed
        bytes after validating that event against its exact accounting snapshot;
        its own journal/receipt cannot circularly attest their later publication.
        The entire reservation remains in the upper bound throughout.
        """
        with self._output_lock:
            if (
                type(total_bytes) is not int
                or total_bytes < self._controller_output_observed
                or total_bytes > self._controller_output_allowance
            ):
                raise AdapterFailure("controller output exceeds its disjoint allowance")
            self._controller_output_observed = total_bytes

    def retain_closed_remote_output(self, *, total_bytes: int) -> None:
        """Retain the terminal host census without altering the runtime's event.

        This admits nothing. The producer has stopped, every byte must fit its
        existing remote reservation, and the original runtime census remains in
        its transcript. Reconciliation waits until the shared terminal validator
        has consumed the earlier protocol accounting snapshot.
        """
        with self._output_lock:
            if (
                self._closed_remote_output is not None
                or type(total_bytes) is not int
                or not (self.output_total_bytes or 0)
                <= total_bytes
                <= self._remote_output_allowance
            ):
                raise AdapterFailure("closed remote output lacks its prior allowance or census")
            self._closed_remote_output = total_bytes

    def reconcile_closed_remote_output(self) -> None:
        with self._output_lock:
            if self._closed_remote_output is None or self._closed_remote_reconciled:
                return
            count = self._closed_remote_output - (self.output_total_bytes or 0)
            if count:
                self.boundary.record_output_bytes(
                    count,
                    retained_output_bytes=(
                        self._remote_output_allowance
                        - self._closed_remote_output
                        + self._controller_output_allowance
                        - self._controller_output_reconciled
                    ),
                )
            self._closed_remote_reconciled = True

    def reconcile_controller_output(self) -> None:
        with self._output_lock:
            remote_observed = self.output_total_bytes or 0
            if self._closed_remote_reconciled:
                assert self._closed_remote_output is not None
                remote_observed = self._closed_remote_output
            count = self._controller_output_observed - self._controller_output_reconciled
            if count:
                self.boundary.record_output_bytes(
                    count,
                    retained_output_bytes=(
                        self._controller_output_allowance
                        - self._controller_output_observed
                        + self._remote_output_allowance
                        - remote_observed
                    ),
                )
                self._controller_output_reconciled = self._controller_output_observed

    def terminal_accounting_document(self) -> Mapping[str, object]:
        """Capture the actual accountant at the terminal protocol boundary once."""
        with self._output_lock:
            if self._runtime_terminal_accounting is not None:
                raise AdapterFailure("runtime terminal accounting was already captured")
            document = self.boundary.accounting_document()
            self._runtime_terminal_accounting = cast(
                dict[str, object], json.loads(json.dumps(document))
            )
            return document

    def protocol_accounting_document(self) -> Mapping[str, object]:
        """Return the immutable protocol boundary, separate from later output occupancy."""
        current = self.boundary.accounting_document()
        snapshot = self._runtime_terminal_accounting
        if snapshot is None:
            return current
        if current.get("calls") != snapshot.get("calls"):
            raise AdapterFailure("terminal model accounting changed after runtime closure")
        return cast(dict[str, object], json.loads(json.dumps(snapshot)))

    def output_bytes(self, *, total_bytes: int, retained_output_bytes: int = 0) -> None:
        self._assert_campaign_open()
        with self._output_lock:
            if (
                self._closed_remote_output is not None
                or type(total_bytes) is not int
                or total_bytes < 0
                or type(retained_output_bytes) is not int
                or retained_output_bytes < 0
                or (self.output_total_bytes is not None and total_bytes < self.output_total_bytes)
            ):
                raise AdapterFailure("condition output-byte total is malformed or moved backward")
            prior = self.output_total_bytes or 0
            self.boundary.record_output_bytes(
                total_bytes - prior,
                retained_output_bytes=(
                    retained_output_bytes
                    + self._controller_output_allowance
                    - self._controller_output_reconciled
                ),
            )
            self.output_total_bytes = total_bytes

    def process_exit(self, *, exit_code: int) -> None:
        self._assert_campaign_open()
        if self.exit_code is not None or type(exit_code) is not int:
            raise AdapterFailure("condition process-exit event is duplicate or malformed")
        self.exit_code = exit_code

    def completion(self, *, completed: bool, answer: str | None, error: str) -> None:
        self._assert_campaign_open()
        if (
            self.completion_state is not None
            or type(completed) is not bool
            or not isinstance(error, str)
            or (answer is not None and not isinstance(answer, str))
        ):
            raise AdapterFailure("condition completion event is duplicate or malformed")
        if completed and (not answer or error):
            raise AdapterFailure("completed condition lacks an answer or contains an error")
        self.completion_state = (completed, answer, error)

    def raw_artifact_published(
        self,
        *,
        manifest_sha256: str,
        receipt_sha256: str,
    ) -> None:
        self._assert_campaign_open()
        if self.raw_publication is not None:
            raise AdapterFailure("condition raw-publication event was duplicated")
        self.raw_publication = (
            _require_sha(manifest_sha256, label="condition raw manifest"),
            _require_sha(receipt_sha256, label="condition raw receipt"),
        )


class ProductionCategory3World:
    """One effect-neutral production wrapper bound to an exact package context."""

    def __init__(
        self,
        repository: Path,
        contract: T09ProviderContract,
        *,
        low_level_effects: LowLevelEffects,
        authorization_context: EffectAuthorizationContext,
        authority: EffectAuthorityGrant,
        held_transaction_root: HeldTransactionRoot,
        held_effect_source: HeldEffectSource | None,
        source_inputs: CandidateSourceSnapshot | None = None,
    ) -> None:
        self.repository = repository.resolve(strict=True)
        self.source_inputs = source_inputs
        self.contract = contract
        self.low_level_effects = low_level_effects
        self.authorization_context = authorization_context
        self.authority = authority
        self.held_transaction_root = held_transaction_root
        self.held_effect_source = held_effect_source
        self._resources_released = False
        self.clock = _ValidatedRuntimeClock(low_level_effects.runtime_clock())
        held_transaction_root.revalidate()
        self.root = held_transaction_root.path
        if low_level_effects.transaction_root() != self.root:
            raise ValueError("effect transaction root differs from the shared-held root")
        self._root_identity_mismatch = False
        self.private_root = self.root / "control-private"
        self.public_root = self.root / "control-public"
        self.private_root.mkdir(mode=0o700)
        self.public_root.mkdir(mode=0o700)
        self._dotenv = self.private_root / "mixed.env"
        self._metadata_overlay = self.private_root / "authorization-overlay.json"
        self._metadata_receipt = self.private_root / metadata.MODEL_METADATA_RECEIPT_FILENAME
        self._pilot_state = self.private_root / "pilot-state.json"
        self._public_ipv4 = self.private_root / "source-ipv4.txt"
        self._public_key = self.private_root / "provider-key.pub"
        self._calls: list[AdapterCall] = []
        self._counts: Counter[str] = Counter()
        self._undeclared_calls: list[str] = []
        self._primitive_calls: list[str] = []
        self._closed_launch_slots: list[int] = []
        self._termination_failures = 0
        self._campaign_roots: dict[int, Path] = {}
        self._entry_receipts: dict[int, Path] = {}
        self._provider_handles: dict[int, ProviderHandle] = {}
        self._provider_entry_failed_slots: set[int] = set()
        self._execution_contract: pilot.PilotExecutionContract | None = None
        self._command_document: dict[str, object] | None = None
        self._command_package_sha256: str | None = None
        self._runtime_budget: PackageRuntimeBudget | None = None
        self._metadata_document: dict[str, object] | None = None
        self._local_assembly: LocalPackageAssemblyReceipt | None = None
        self._local_assembly_artifact: HeldArtifact | None = None
        self._local_assembly_verification_artifact: HeldArtifact | None = None
        self._host_transfers: dict[int, HostPackageTransferReceipt] = {}
        self._host_preflights: dict[int, HostPreflightReceipt] = {}
        self._qualification: HostQualificationReceipt | None = None
        self._freeze: ScientificFreezeReceipt | None = None
        self._condition_outcomes: dict[str, ConditionProcessOutcome] = {}
        self._condition_requests: dict[str, ConditionExecutionRequest] = {}
        self._condition_observers: dict[str, _AccountingObserver] = {}
        self._condition_failures: dict[str, ConditionInfrastructureFailureOutcome] = {}
        self._essential_failure_exports: dict[str, ConditionFailureExportReceipt] = {}
        self._essential_failure_artifacts: dict[str, tuple[HeldArtifact, ...]] = {}
        self._essential_failure_artifact_bindings: dict[str, str] = {}
        self._essential_failure_roots: set[str] = set()
        self._raw_artifacts: dict[str, tuple[HeldArtifact, ...]] = {}
        self._raw_artifact_bindings: dict[str, str] = {}
        self._condition_bridge_bindings: dict[str, str] = {}
        self._condition_bridge_artifacts: dict[str, tuple[HeldArtifact, ...]] = {}
        self._finalizations: dict[str, FinalizerExecutionOutcome] = {}
        self._finalized_artifacts: dict[str, tuple[HeldArtifact, ...]] = {}
        self._finalized_artifact_bindings: dict[str, str] = {}
        self._accounting: dict[str, dict[str, object]] = {}
        self._aggregate_usage = ProviderBudgetUsage()
        self._aggregate_observed_usage = ProviderBudgetUsage()
        self._campaign_output_boundary: ProviderBudgetBoundary | None = None
        self._campaign_cleanup_remaining: int | None = None
        self._campaign_writes: list[CampaignWriteAllowance] = []
        self._campaign_admission_blocked = False
        self._evaluations: dict[str, dict[str, object]] = {}
        self._raw_export_acknowledgements: dict[str, str] = {}
        self._provider_cost_receipt: ProviderCostReceipt | None = None
        self._provider_lifecycle_cost_proof: ProviderLifecycleCostProof | None = None
        self._checkpoint_result: FirstPairCheckpointResult | None = None
        self._checkpoint_document: dict[str, object] | None = None
        self._cleanup_handoff_bytes: bytes | None = None
        self._cleanup_receipt: CleanupExecutionReceipt | None = None
        self._cleanup_calls = 0
        self._cleanup_started_after_campaign_deadline = False
        self._authority_launch_consumed = False
        self._package_assembly_evidence: dict[str, object] | None = None
        self._condition_started_wall: dict[str, float] = {}
        self._condition_started_monotonic: dict[str, float] = {}
        self._entered_run_ids: list[str] = []
        self._raw_completed_run_ids: list[str] = []
        self._campaign_started_monotonic: float | None = None
        self._campaign_deadline_monotonic: float | None = None
        self._seen_call_ids: set[str] = set()
        self._seen_logical_call_ids: set[str] = set()
        self._consumer_resolutions = resolve_control_consumers(
            self.repository,
            contract,
            consumers=_RUNTIME_CONSUMERS,
            source_inputs=source_inputs,
        )

    def _source_identity(self) -> tuple[str, str]:
        if self.source_inputs is not None:
            return self.source_inputs.package_identity(self.repository)
        return _git_identity(self.repository)

    @property
    def calls(self) -> tuple[AdapterCall, ...]:
        return tuple(self._calls)

    @property
    def undeclared_calls(self) -> tuple[str, ...]:
        return tuple(self._undeclared_calls)

    def adapters(self) -> Category3Adapters:
        return Category3Adapters(
            implementation_flavor=ImplementationFlavor.PRODUCTION_WRAPPER,
            authorization_context=self.authorization_context,
            authority=self.authority,
            clock=self.clock,
            secret_channel=self,
            metadata_transport=self,
            provider_transport=self,
            host_runtime=self,
            condition_runtime=self,
            evidence_store=self,
            audit=self,
            diagnostics=self,
        )

    def _operation_limit(self, operation: str) -> int | None:
        attempts = len(self.contract.run_ids)
        launches = self.contract.max_launch_count
        return {
            "secret.read": 1,
            "metadata.request": 1,
            "metadata.is_fresh": 1,
            "provider.inventory": launches + 2,
            "provider.launch": launches,
            "provider.enter": launches,
            "provider.terminate": launches + 1,
            "host.assemble_local": 1,
            "host.transfer": launches,
            "host.preflight": launches,
            "host.qualify": 1,
            "host.freeze": 1,
            "host.cleanup": 2,
            "condition.reserve": attempts,
            "condition.enter": attempts,
            "condition.run": attempts,
            "condition.export_raw": attempts,
            "condition.finalize": attempts,
            "condition.evaluate": attempts,
            "evidence.record": attempts * 3 + 2,
            "evidence.checkpoint": 1,
            "evidence.scan_privacy": 1,
        }.get(operation)

    def _begin(self, operation: str, subject: str) -> int:
        try:
            self.held_transaction_root.revalidate()
            if self.low_level_effects.transaction_root() != self.root:
                raise ValueError("effect returned a different transaction root")
        except ValueError as exc:
            self._root_identity_mismatch = True
            try:
                self.held_transaction_root.revalidate_descriptor()
            except ValueError as descriptor_exc:
                raise AdapterFailure("held transaction root descriptor changed") from descriptor_exc
            cleanup_only_operation = operation in {
                "host.cleanup",
                "evidence.scan_privacy",
            } or (
                self._cleanup_calls > 0
                and operation in {"provider.terminate", "provider.inventory"}
            )
            if not cleanup_only_operation:
                raise AdapterFailure("held transaction root identity changed") from exc
        occurrence = self._counts[operation] + 1
        self._counts[operation] = occurrence
        limit = self._operation_limit(operation)
        if limit is None or occurrence > limit:
            marker = f"{operation}#{occurrence}"
            self._undeclared_calls.append(marker)
            self._record(operation, subject, "undeclared")
            raise UndeclaredAdapterCall(marker)
        return occurrence

    def _record(self, operation: str, subject: str, outcome: str) -> None:
        adapter, _separator, _method = operation.partition(".")
        self._calls.append(
            AdapterCall(
                index=len(self._calls) + 1,
                adapter=adapter,
                operation=operation,
                subject=subject,
                outcome=outcome,
            )
        )

    def _primitive(self, name: str) -> None:
        self._primitive_calls.append(name)

    def _resolution(self, name: str) -> ConsumerResolution:
        resolution = self._consumer_resolutions.get(name)
        if resolution is None:
            raise AdapterFailure(f"production consumer is unavailable: {name}")
        return resolution

    @staticmethod
    def _destroy_buffer(value: bytearray | None) -> None:
        if value is not None:
            metadata._destroy_bytearray(value)

    def read(self) -> str:
        operation = "secret.read"
        self._begin(operation, "strict-mixed-dotenv")
        model_material: bytearray | None = None
        provider_material: bytearray | None = None
        selected: bytearray | None = None
        try:
            if isinstance(self.authority, ValidatedLiveEffectAuthority):
                if not self.authority.is_valid_for(self.authorization_context):
                    raise AdapterFailure("live authority is not valid at the secret boundary")
                self.authority.reserve_before_secret()
                self._primitive("reserve_live_authority_before_secret")
            model_material = self.low_level_effects.read_model_secret()
            provider_material = self.low_level_effects.read_provider_secret()
            if not model_material or not provider_material:
                raise AdapterFailure("secret channel returned empty credential material")
            self._dotenv.write_bytes(
                b"OPENAI_API_KEY="
                + bytes(model_material)
                + b"\nLAMBDA_API_KEY="
                + bytes(provider_material)
                + b"\n"
            )
            self._dotenv.chmod(0o600)
            selected = metadata.load_openai_dotenv_assignment(self._dotenv)
            if not selected:
                raise AdapterFailure("strict dotenv selected no OpenAI assignment")
            self._public_ipv4.write_text(self.low_level_effects.public_ipv4(), encoding="utf-8")
            self._public_ipv4.chmod(0o600)
            self._public_key.write_text(self.low_level_effects.ssh_public_key(), encoding="utf-8")
            self._public_key.chmod(0o600)
        except BaseException as exc:
            self._record(operation, "strict-mixed-dotenv", "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(
                f"secret-channel qualification failed ({type(exc).__name__})"
            ) from exc
        finally:
            self._destroy_buffer(selected)
            self._destroy_buffer(model_material)
            self._destroy_buffer(provider_material)
        self._primitive("load_openai_dotenv_assignment")
        self._record(operation, "strict-mixed-dotenv", "passed")
        return _identity({"secret_channel": self.contract.version})

    def request(self, *, contract_version: str) -> MetadataEnvelope:
        operation = "metadata.request"
        self._begin(operation, contract_version)
        if contract_version != self.contract.version or not self._dotenv.is_file():
            raise AdapterFailure("metadata request lacks its exact prepared secret channel")
        commit, tree = self._source_identity()
        binding = dict(
            self.low_level_effects.metadata_authorization_binding(contract=self.contract)
        )
        reference = binding.get("authorization_reference")
        source_sha = binding.get("authorization_source_sha256")
        price_sha = binding.get("public_price_contract_sha256")
        deprecation_sha = binding.get("public_deprecation_observation_sha256")
        if (
            not isinstance(reference, str)
            or not isinstance(self.contract.authorization_prefix, str)
            or not reference.startswith(self.contract.authorization_prefix)
            or not isinstance(source_sha, str)
            or _HEX64.fullmatch(source_sha) is None
            or not isinstance(price_sha, str)
            or _HEX64.fullmatch(price_sha) is None
            or not isinstance(deprecation_sha, str)
            or _HEX64.fullmatch(deprecation_sha) is None
            or binding.get("authorized") is not True
            or binding.get("single_use") is not True
        ):
            self._record(operation, contract_version, "failed")
            raise AdapterFailure("metadata authorization binding is incomplete")
        if isinstance(self.authority, ValidatedLiveEffectAuthority):
            try:
                self.contract.validate_authority(reference, source_sha)
                self.authority.assert_phase_binding(
                    reference=reference,
                    source_sha256=source_sha,
                )
                self.authority.mark_metadata_send_attempted()
            except (ValueError, provider.T09ProviderError) as exc:
                self._record(operation, contract_version, "failed")
                raise AdapterFailure(
                    "effect and metadata authority are not one transaction"
                ) from exc
            self._primitive("validate_unified_live_authority:metadata")
        overlay = {
            "schema_version": metadata.MODEL_METADATA_SCHEMA_VERSION,
            "authorization_reference": reference,
            "authorization_source_sha256": source_sha,
            "provider_contract_version": self.contract.version,
            "repository_commit": commit,
            "repository_tree": tree,
            "plan_id": self.contract.plan_id,
            "plan_sha256": self.contract.expected_provider_profile_sha256,
            "host_run_id": self.contract.host_run_id,
            "public_price_contract_sha256": price_sha,
            "public_deprecation_observation_sha256": deprecation_sha,
            "model_metadata_receipt_sha256": None,
            "authorized": True,
            "single_use": True,
        }
        self._metadata_overlay.write_bytes(_canonical_bytes(overlay))
        self._metadata_overlay.chmod(0o600)
        overlay_sha = metadata.model_metadata_authorization_overlay_sha256(self._metadata_overlay)
        issued_monotonic = self.clock.monotonic()
        try:
            metadata.create_model_metadata_receipt(
                repository_commit=commit,
                repository_tree=tree,
                plan_id=self.contract.plan_id,
                plan_sha256=self.contract.expected_provider_profile_sha256,
                provider_contract_version=self.contract.version,
                host_run_id=self.contract.host_run_id,
                authorization_reference=reference,
                authorization_source_sha256=source_sha,
                authorization_overlay_sha256=overlay_sha,
                public_price_contract_sha256=price_sha,
                public_deprecation_observation_sha256=deprecation_sha,
                output=self._metadata_receipt,
                dotenv=self._dotenv,
                authorization_overlay=self._metadata_overlay,
                transport=_MetadataChannelTransport(self.low_level_effects, self.clock),
                clock=self.clock.wall_time,
            )
            receipt_sha = metadata.model_metadata_receipt_sha256(self._metadata_receipt)
            metadata.bind_model_metadata_receipt_to_authorization_overlay(
                self._metadata_overlay,
                receipt_sha256=receipt_sha,
            )
            if isinstance(self.authority, ValidatedLiveEffectAuthority):
                self.authority.mark_metadata_bound()
            document = metadata.validate_model_metadata_receipt(
                self._metadata_receipt,
                contract=self.contract,
                package_commit=commit,
                package_tree=tree,
                plan_sha256=self.contract.expected_provider_profile_sha256,
                authorization_overlay=self._metadata_overlay,
                validation_policy=(metadata.ModelMetadataReceiptValidationPolicy.DURABLE_OFFLINE),
            )
            issued_wall = metadata._parse_timestamp(
                document.get("receipt_created_at"), label="receipt creation"
            )
            expires_wall = checked_deadline(
                issued_wall,
                metadata.MODEL_METADATA_PRELAUNCH_FRESHNESS_SECONDS,
                label="metadata freshness",
            )
        except BaseException as exc:
            self._record(operation, contract_version, "failed")
            raise AdapterFailure(
                f"production metadata receipt failed ({type(exc).__name__})"
            ) from exc
        self._metadata_document = document
        self._primitive("create_model_metadata_receipt")
        self._primitive("bind_model_metadata_receipt_to_authorization_overlay")
        self._primitive("validate_model_metadata_receipt:durable-offline")
        self._record(operation, contract_version, "passed")
        return MetadataEnvelope(
            receipt_sha256=receipt_sha,
            issued_wall_time=issued_wall,
            expires_wall_time=expires_wall,
            issued_monotonic=issued_monotonic,
            max_monotonic_age_seconds=metadata.MODEL_METADATA_PRELAUNCH_FRESHNESS_SECONDS,
        )

    def is_fresh(self, envelope: MetadataEnvelope) -> bool:
        operation = "metadata.is_fresh"
        self._begin(operation, envelope.receipt_sha256)
        if self._metadata_document is None:
            raise AdapterFailure("metadata freshness lacks a validated receipt")
        wall_boundary = self.clock.wall_time()
        monotonic_boundary = self.clock.monotonic()
        try:
            metadata.admit_model_metadata_receipt_at_prelaunch_boundary(
                self._metadata_document,
                boundary_epoch=wall_boundary,
            )
            monotonic_age = monotonic_boundary - finite_time(
                envelope.issued_monotonic,
                label="metadata monotonic issue time",
            )
            if (
                monotonic_age < 0
                or monotonic_age > envelope.max_monotonic_age_seconds
                or wall_boundary > envelope.expires_wall_time
                or wall_boundary < envelope.issued_wall_time
            ):
                raise metadata.ModelMetadataReceiptError("metadata timing envelope expired")
        except (metadata.ModelMetadataReceiptError, ValueError):
            self._record(operation, envelope.receipt_sha256, "expired")
            return False
        self._primitive("admit_model_metadata_receipt_at_prelaunch_boundary")
        self._record(operation, envelope.receipt_sha256, "passed")
        return True

    def inventory(self) -> tuple[str, ...] | None:
        operation = "provider.inventory"
        self._begin(operation, "owned-resources")
        try:
            values = self.low_level_effects.provider_inventory()
        except BaseException as exc:
            self._record(operation, "owned-resources", "failed")
            raise AdapterFailure(f"production provider inventory failed: {exc}") from exc
        if values is not None and (
            not isinstance(values, tuple)
            or any(not isinstance(item, str) or not item for item in values)
            or tuple(sorted(set(values))) != values
        ):
            self._record(operation, "owned-resources", "failed")
            raise AdapterFailure("provider inventory is not an exact sorted identity set")
        self._record(
            operation,
            "owned-resources",
            "ambiguous" if values is None else ("zero" if not values else "observed"),
        )
        return values

    def launch(self, *, launch_ordinal: int) -> ProviderHandle:
        operation = "provider.launch"
        self._begin(operation, f"launch-{launch_ordinal}")
        private_root = self.private_root / f"campaign-slot-{launch_ordinal:02d}"
        try:
            projection = provider.validate_campaign_launch_projection(
                self.repository,
                contract=self.contract,
                launch_slot=launch_ordinal,
                closed_launch_slots=tuple(self._closed_launch_slots),
            )
            self._primitive("validate_campaign_launch_projection")
            if projection.get("launch_slot") != launch_ordinal:
                raise AdapterFailure("production launch projection drifted")
            transport = self.low_level_effects.campaign_transport(
                contract=self.contract,
                launch_ordinal=launch_ordinal,
                clock=self.clock,
            )
            prior = self._campaign_roots.get(launch_ordinal - 1)
            retained_image = (
                None
                if prior is None
                else self.low_level_effects.retained_image_archive(launch_ordinal=launch_ordinal)
            )
            commit, _tree = self._source_identity()
            try:
                if isinstance(self.authority, ValidatedLiveEffectAuthority):
                    launch_binding = dict(
                        self.low_level_effects.metadata_authorization_binding(
                            contract=self.contract
                        )
                    )
                    self.authority.assert_phase_binding(
                        reference=cast(str, launch_binding.get("authorization_reference")),
                        source_sha256=cast(
                            str,
                            launch_binding.get("authorization_source_sha256"),
                        ),
                    )
                    if not self._authority_launch_consumed:
                        self.authority.consume_provider_launch()
                        self._authority_launch_consumed = True
                    self._primitive("validate_unified_live_authority:provider-launch")
                with self._campaign_writer_scope(), self.low_level_effects.campaign_scope():
                    entry_receipt = provider.launch_campaign(
                        contract=self.contract,
                        repository=self.repository,
                        package_commit=commit,
                        authorization_ledger=self._metadata_overlay,
                        dotenv=self._dotenv,
                        private_root=private_root,
                        public_ipv4_file=self._public_ipv4,
                        ssh_public_key_file=self._public_key,
                        transport=transport,
                        launch_slot=launch_ordinal,
                        prior_private_root=prior,
                        slot1_image_archive=retained_image,
                        model_metadata_receipt=self._metadata_receipt,
                        shadow_controls=(self.low_level_effects.campaign_low_level_controls()),
                        clock=self.clock.wall_time,
                        sleeper=self.clock.sleep,
                    )
            except provider.T09ProviderError:
                eligibility = private_root / "replacement-launch-eligibility.json"
                if not eligibility.is_file():
                    raise
                self._provider_entry_failed_slots.add(launch_ordinal)
                self._primitive("_cleanup_provisional_owner")
                self._primitive("_publish_replacement_launch_eligibility")
            else:
                self._entry_receipts[launch_ordinal] = entry_receipt
            ownership_candidates = (
                private_root / "owned-state-active.json",
                private_root / "provisional-owned-state.json",
            )
            ownership_path = next(
                (path for path in ownership_candidates if path.is_file()),
                None,
            )
            if ownership_path is None:
                raise AdapterFailure("retained launch lacks its exact owned-state receipt")
            ownership = load_json(ownership_path)
            identity = ownership.get("owned_instance_identity_sha256")
            if not isinstance(identity, str) or _HEX64.fullmatch(identity) is None:
                raise AdapterFailure("retained launch has no opaque provider identity")
            handle = ProviderHandle(identity, launch_ordinal)
            self._campaign_roots[launch_ordinal] = private_root
            self._provider_handles[launch_ordinal] = handle
            self._primitive("launch_campaign")
            if launch_ordinal > 1:
                normalized = private_root / provider.PROVIDER_ENTRY_AUTHORITY_ROOT_NAME
                if not (normalized / "source-manifest.json").is_file():
                    raise AdapterFailure(
                        "replacement launch did not retain normalized provider-entry authority"
                    )
                self._primitive("_normalize_provider_entry_replacement_authority")
                self._primitive("_retain_replacement_launch_authority")
        except (TimeoutError, ConditionAmbiguousSend) as exc:
            self._record(operation, f"launch-{launch_ordinal}", "ambiguous")
            raise AmbiguousProviderOutcome("provider launch acknowledgement is ambiguous") from exc
        except BaseException as exc:
            self._record(operation, f"launch-{launch_ordinal}", "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"production launch preparation failed: {exc}") from exc
        self._record(operation, handle.opaque_identity, "accepted")
        return handle

    def provider_entry(self, handle: ProviderHandle) -> None:
        operation = "provider.enter"
        self._begin(operation, handle.opaque_identity)
        try:
            self.contract.validate_owner(
                plan_id=self.contract.plan_id,
                host_run_id=self.contract.host_run_id,
                instance_name=self.contract.instance_name,
            )
            self._primitive("T09ProviderContract.validate_owner")
            if handle.launch_ordinal in self._provider_entry_failed_slots:
                raise ReplacementEligibleFailure("provider-entry-failed replacement eligibility")
            entry_receipt = self._entry_receipts.get(handle.launch_ordinal)
            private_root = self._campaign_roots.get(handle.launch_ordinal)
            commit, _tree = self._source_identity()
            if entry_receipt is None or private_root is None:
                raise AdapterFailure("provider entry lacks its retained source-bound receipt")
            with self.low_level_effects.campaign_scope():
                provider.validate_entry_receipt_source_bound(
                    entry_receipt,
                    private_root / "entry-source",
                    contract=self.contract,
                    package_commit=commit,
                    plan_sha256=provider.file_sha256(
                        self.repository / self.contract.provider_profile_path
                    ),
                )
            self.low_level_effects.provider_entry(handle)
        except BaseException as exc:
            self._record(operation, handle.opaque_identity, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"provider-entry validation failed: {exc}") from exc
        self._primitive("validate_entry_receipt_source_bound")
        self._record(operation, handle.opaque_identity, "passed")

    def terminate(self, handle: ProviderHandle) -> None:
        operation = "provider.terminate"
        self._begin(operation, handle.opaque_identity)
        try:
            self.low_level_effects.provider_terminate(handle)
        except BaseException as exc:
            self._termination_failures += 1
            self._record(operation, handle.opaque_identity, "unavailable")
            raise TerminationUnavailable("bounded provider termination unavailable") from exc
        if handle.launch_ordinal not in self._closed_launch_slots:
            self._closed_launch_slots.append(handle.launch_ordinal)
            self._closed_launch_slots.sort()
        self._record(operation, handle.opaque_identity, "accepted")

    def _condition_plan_caps(
        self,
        path: Path,
        expected_sha256: str,
        *,
        run_id: str,
        condition: str,
        plan_sha256: str,
        model_revision: str,
    ) -> ProviderBudgetCaps:
        if _file_sha256(path) != expected_sha256:
            raise AdapterFailure("condition plan hash drifted")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise AdapterFailure("condition plan is not strict YAML") from exc
        if not isinstance(document, dict) or not isinstance(document.get("budget"), dict):
            raise AdapterFailure("condition plan lacks its owned budget")
        sources = document.get("sources")
        execution = document.get("execution")
        authorization = execution.get("authorization") if isinstance(execution, dict) else None
        if (
            document.get("run_id") != run_id
            or document.get("profile_plan_id") != self.contract.plan_id
            or document.get("profile_sha256") != plan_sha256
            or document.get("condition") != f"SIRA-{condition.upper()}"
            or not isinstance(sources, dict)
            or sources.get("model_revision") != model_revision
            or not isinstance(authorization, dict)
            or authorization.get("authorized") is not False
            or authorization.get("authorization_reference") is not None
        ):
            raise AdapterFailure("condition plan identity or false authority drifted")
        budget = cast(dict[str, object], document["budget"])
        values = {
            "max_cost_usd": budget.get("max_cost_usd"),
            "max_input_tokens": budget.get("max_model_tokens"),
            "max_cached_input_tokens": budget.get("max_model_tokens"),
            "max_output_tokens": budget.get("max_model_tokens"),
            "max_total_tokens": budget.get("max_model_tokens"),
            "max_model_call_attempts": budget.get("max_model_calls"),
            "max_wall_seconds": budget.get("max_wall_seconds"),
            "max_browser_actions": budget.get("max_tool_calls"),
            "max_output_bytes": budget.get("max_output_bytes"),
        }
        try:
            return ProviderBudgetCaps(**values)  # type: ignore[arg-type]
        except Exception as exc:
            raise AdapterFailure("condition plan budget is malformed") from exc

    def _load_plan_budget(
        self,
        execution: pilot.PilotExecutionContract,
    ) -> tuple[
        ProviderBudgetCaps,
        Mapping[str, ProviderBudgetCaps],
        str,
        str,
        bool,
    ]:
        plan_path = self.repository / self.contract.plan_path
        encoded = plan_path.read_bytes()
        if (
            plan_path.is_symlink()
            or len(encoded) != self.contract.expected_plan_bytes
            or hashlib.sha256(encoded).hexdigest() != self.contract.expected_plan_sha256
        ):
            raise AdapterFailure("selected plan byte identity drifted")
        try:
            plan = yaml.safe_load(encoded)
        except (UnicodeError, yaml.YAMLError) as exc:
            raise AdapterFailure("selected plan is not strict YAML") from exc
        if not isinstance(plan, dict):
            raise AdapterFailure("selected plan is not an object")
        execution_document = load_json(execution.path)
        model = plan.get("model")
        plan_execution = plan.get("execution")
        plan_budget = plan.get("budget")
        lifecycle = plan.get("provider_lifecycle")
        failure_policy = plan.get("failure_evidence_policy")
        model_revision = execution_document.get("model_revision")
        service_tier = execution_document.get("service_tier")
        if (
            plan.get("plan_id") != self.contract.plan_id
            or not isinstance(model, dict)
            or model.get("proposed_immutable_revision") != model_revision
            or not isinstance(model_revision, str)
            or not model_revision
            or not isinstance(service_tier, str)
            or not service_tier
            or not isinstance(plan_execution, dict)
            or plan_execution.get("authorized") is not False
            or plan_execution.get("authorization_reference") is not None
            or execution_document.get("authorized") is not False
            or execution_document.get("authorization_reference") is not None
            or not isinstance(plan_budget, dict)
            or not isinstance(lifecycle, dict)
            or not isinstance(failure_policy, dict)
        ):
            raise AdapterFailure("selected plan runtime or false authority drifted")
        output_per_attempt = failure_policy.get("full_attempt_cap_bytes")
        if type(output_per_attempt) is not int or output_per_attempt <= 0:
            raise AdapterFailure("selected plan output cap is malformed")
        aggregate_values = {
            "max_cost_usd": plan_budget.get("max_cost_usd"),
            "max_input_tokens": plan_budget.get("max_model_tokens"),
            "max_cached_input_tokens": plan_budget.get("max_model_tokens"),
            "max_output_tokens": plan_budget.get("max_model_tokens"),
            "max_total_tokens": plan_budget.get("max_model_tokens"),
            "max_model_call_attempts": plan_budget.get("max_model_calls"),
            "max_wall_seconds": plan_budget.get("max_wall_seconds"),
            "max_browser_actions": plan_budget.get("max_browser_actions"),
            "max_output_bytes": output_per_attempt * len(self.contract.run_ids),
        }
        try:
            aggregate = ProviderBudgetCaps(**aggregate_values)  # type: ignore[arg-type]
        except Exception as exc:
            raise AdapterFailure("selected plan aggregate budget is malformed") from exc
        raw_condition_limits = plan_budget.get("condition_limits")
        if not isinstance(raw_condition_limits, dict):
            raise AdapterFailure("selected plan lacks condition-owned limits")
        by_condition: dict[str, ProviderBudgetCaps] = {}
        expected_condition_counts: dict[str, int] = {}
        for condition in ("reactive", "simulative"):
            raw = raw_condition_limits.get(f"SIRA-{condition.upper()}")
            if not isinstance(raw, dict):
                raise AdapterFailure("selected plan omits a condition limit")
            values = {
                "max_cost_usd": raw.get("max_openai_cost_usd_per_attempt"),
                "max_input_tokens": raw.get("max_model_tokens_per_attempt"),
                "max_cached_input_tokens": raw.get("max_model_tokens_per_attempt"),
                "max_output_tokens": raw.get("max_model_tokens_per_attempt"),
                "max_total_tokens": raw.get("max_model_tokens_per_attempt"),
                "max_model_call_attempts": raw.get("max_model_calls_per_attempt"),
                "max_wall_seconds": raw.get("max_wall_seconds_per_attempt"),
                "max_browser_actions": raw.get("max_browser_actions_per_attempt"),
                "max_output_bytes": output_per_attempt,
            }
            try:
                by_condition[condition] = ProviderBudgetCaps(**values)  # type: ignore[arg-type]
            except Exception as exc:
                raise AdapterFailure("selected plan condition budget is malformed") from exc
            attempts = raw.get("attempts")
            if type(attempts) is not int or attempts <= 0:
                raise AdapterFailure("selected plan condition attempt count is malformed")
            expected_condition_counts[condition] = attempts
        observed_condition_counts = Counter(item.condition for item in execution.attempts)
        condition_paths = plan.get("condition_plan_paths")
        if (
            observed_condition_counts != Counter(expected_condition_counts)
            or not isinstance(condition_paths, list)
            or tuple(condition_paths)
            != tuple(item.condition_plan_path for item in execution.attempts)
            or aggregate != execution.limits.aggregate_provider_caps()
            or aggregate.max_cost_usd != self.contract.campaign_openai_cost_cap_usd
            or plan_budget.get("prior_t09_cost_usd") != self.contract.prior_t09_cost_usd
            or plan_budget.get("cumulative_t09_cost_cap_usd")
            != self.contract.cumulative_t09_cost_cap_usd
            or plan_budget.get("effective_max_total_cost_under_cumulative_cap_usd")
            != self.contract.campaign_aggregate_cost_cap_usd
            or plan_budget.get("max_provider_compute_cost_usd")
            != self.contract.campaign_lambda_cost_cap_usd
            or plan_budget.get("max_preflight_provider_compute_cost_usd")
            != self.contract.preflight_lambda_cost_cap_usd
            or lifecycle.get("preflight_iteration_wall_seconds")
            != execution.campaign.preflight_iteration_wall_seconds
            or lifecycle.get("empirical_campaign_wall_seconds")
            != execution.campaign.empirical_campaign_wall_seconds
            or lifecycle.get("evidence_export_reserve_seconds")
            != execution.campaign.evidence_export_reserve_seconds
            or lifecycle.get("provider_termination_handoff_seconds")
            != execution.campaign.provider_termination_handoff_seconds
            or lifecycle.get("empirical_cleanup_reserve_seconds")
            != execution.campaign.empirical_cleanup_reserve_seconds
            or lifecycle.get("empirical_termination_cutoff_seconds")
            != execution.campaign.empirical_termination_cutoff_seconds
        ):
            raise AdapterFailure("plan, execution, provider, or lifecycle budget drifted")
        zero_retry = execution.limits.max_retries_after_empirical_entry == 0
        return aggregate, MappingProxyType(by_condition), model_revision, service_tier, zero_retry

    def _load_runtime_package(self) -> tuple[tuple[TrackedPackageMember, ...], str]:
        command, command_sha, source = resolve_registered_command_package(
            self.repository,
            self.contract,
            source_inputs=self.source_inputs,
        )
        execution_sha = command.get("execution_contract_sha256")
        if (
            not isinstance(execution_sha, str)
            or _HEX64.fullmatch(execution_sha) is None
            or self.contract.execution_contract_path is None
            or self.contract.command_manifest_path is None
        ):
            raise AdapterFailure("registered command package is incomplete")
        execution = pilot.load_execution_contract(
            self.repository / self.contract.execution_contract_path,
            expected_sha256=execution_sha,
        )
        if (
            execution.plan_id != self.contract.plan_id
            or execution.provider_contract_version != self.contract.version
            or tuple(item.run_id for item in execution.attempts) != self.contract.run_ids
            or execution.limits.max_retries_after_empirical_entry != 0
        ):
            raise AdapterFailure("execution contract contradicts its provider contract")
        (
            plan_aggregate,
            plan_condition_caps,
            model_revision,
            service_tier,
            zero_retry,
        ) = self._load_plan_budget(execution)
        manifests = command.get("manifests")
        if not isinstance(manifests, list):
            raise AdapterFailure("command package manifest list is absent")
        by_run: dict[str, dict[str, object]] = {}
        condition_caps: dict[str, ProviderBudgetCaps] = {}
        condition_hashes: set[str] = set()
        for raw in manifests:
            if not isinstance(raw, dict) or not isinstance(raw.get("run_id"), str):
                raise AdapterFailure("command package contains a malformed condition")
            manifest = cast(dict[str, object], raw)
            run_id = cast(str, manifest["run_id"])
            if run_id in by_run:
                raise AdapterFailure("command package duplicates a condition")
            attempt = execution.attempt(run_id)
            argv = manifest.get("argv")
            upstream_argv = (
                argv[argv.index("--") + 1 :] if isinstance(argv, list) and "--" in argv else None
            )
            if (
                not isinstance(argv, list)
                or not all(isinstance(item, str) for item in argv)
                or not isinstance(upstream_argv, list)
                or tuple(upstream_argv) != attempt.upstream_argv
                or manifest.get("argv_sha256") != pilot.command_argv_sha256(argv)
                or manifest.get("condition_plan_path") != attempt.condition_plan_path
                or manifest.get("condition_plan_sha256") != attempt.condition_plan_sha256
                or manifest.get("execution_contract_sha256") != execution.sha256
            ):
                raise AdapterFailure("command and execution condition identities drifted")
            assert isinstance(upstream_argv, list)
            retry_positions = [
                index for index, value in enumerate(upstream_argv) if value == "--max_retry"
            ]
            model_positions = [
                index for index, value in enumerate(upstream_argv) if value == "--model"
            ]
            if len(retry_positions) != 1 or len(model_positions) != 1:
                raise AdapterFailure("command model or zero-retry selector is ambiguous")
            retry_index = retry_positions[0]
            model_index = model_positions[0]
            if (
                retry_index + 1 >= len(upstream_argv)
                or upstream_argv[retry_index + 1] != "0"
                or model_index + 1 >= len(upstream_argv)
                or upstream_argv[model_index + 1] != model_revision
            ):
                raise AdapterFailure("command model or zero-retry policy drifted")
            caps = self._condition_plan_caps(
                self.repository / attempt.condition_plan_path,
                attempt.condition_plan_sha256,
                run_id=run_id,
                condition=attempt.condition,
                plan_sha256=self.contract.expected_plan_sha256,
                model_revision=model_revision,
            )
            equality = manifest.get("equality_surface")
            declared = equality.get("budgets") if isinstance(equality, dict) else None
            expected_declared = {
                "max_browser_actions": caps.max_browser_actions,
                "max_model_calls": caps.max_model_call_attempts,
                "max_model_tokens": caps.max_total_tokens,
                "max_openai_cost_usd": caps.max_cost_usd,
                "max_output_bytes": caps.max_output_bytes,
            }
            if (
                declared != expected_declared
                or not isinstance(equality, dict)
                or equality.get("condition_wall_seconds") != caps.max_wall_seconds
                or equality.get("model") != model_revision
                or caps != plan_condition_caps.get(attempt.condition)
            ):
                raise AdapterFailure("command manifest and condition budget drifted")
            by_run[run_id] = manifest
            condition_caps[run_id] = caps
            condition_hashes.add(attempt.condition_plan_sha256)
        if tuple(by_run) != self.contract.run_ids or len(condition_hashes) != len(
            self.contract.run_ids
        ):
            raise AdapterFailure("condition order or condition-plan ownership drifted")
        execution_caps = execution.limits.condition_provider_caps()
        if any(caps != execution_caps for caps in condition_caps.values()):
            raise AdapterFailure("condition plan caps differ from the execution contract")
        aggregate = execution.limits.aggregate_provider_caps()
        if (
            aggregate != plan_aggregate
            or aggregate.max_cost_usd != self.contract.campaign_openai_cost_cap_usd
            or aggregate.max_model_call_attempts
            != execution_caps.max_model_call_attempts * len(self.contract.run_ids)
            or aggregate.max_wall_seconds != execution.limits.max_total_wall_seconds
        ):
            raise AdapterFailure("aggregate package caps drifted from exact plan values")
        self._execution_contract = execution
        self._command_document = command
        self._command_package_sha256 = command_sha
        self._runtime_budget = PackageRuntimeBudget(
            aggregate_caps=aggregate,
            condition_caps=MappingProxyType(condition_caps),
            attempt_order=self.contract.run_ids,
            model_revision=model_revision,
            service_tier=service_tier,
            zero_retry=zero_retry,
            command_package_sha256=command_sha,
            execution_contract_sha256=execution.sha256,
            plan_sha256=self.contract.expected_plan_sha256,
        )
        host = _host_module(self.repository)
        paths = {
            self.contract.plan_path,
            self.contract.provider_profile_path,
            self.contract.command_manifest_path,
            self.contract.execution_contract_path,
            execution.dataset_contract_path,
            execution.evaluator_contract_path,
            *(attempt.condition_plan_path for attempt in execution.attempts),
            host.FINALIZER_RELATIVE_PATH,
            host.FINALIZER_PROJECTION_RELATIVE_PATH,
        }
        if self.contract.effect_registration is not None:
            paths.add(self.contract.effect_registration.implementation_path)
        if self.source_inputs is not None:
            paths.update(
                member["path"] for member in self.source_inputs.document()["source_members"]
            )
            paths.add(".offline-candidate-source.json")
        members: list[TrackedPackageMember] = []
        for relative in sorted(paths):
            if not isinstance(relative, str):
                raise AdapterFailure("tracked package path is missing")
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
                raise AdapterFailure("tracked package path is unsafe")
            if self.source_inputs is None:
                _tracked(self.repository, relative)
            path = self.repository / relative
            metadata_value = path.stat(follow_symlinks=False)
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata_value.st_mode)
                or metadata_value.st_nlink != 1
                or metadata_value.st_size > _MAX_STAGE_MEMBER_BYTES
            ):
                raise AdapterFailure("tracked package member is unsafe or oversized")
            members.append(
                TrackedPackageMember(
                    path=relative,
                    bytes=metadata_value.st_size,
                    sha256=_file_sha256(path),
                )
            )
        return tuple(members), source

    @staticmethod
    def _local_assembly_receipt_identity(receipt: LocalPackageAssemblyReceipt) -> str:
        return _identity(
            {
                "provider_contract_version": receipt.provider_contract_version,
                "plan_id": receipt.plan_id,
                "plan_sha256": receipt.plan_sha256,
                "command_package_sha256": receipt.command_package_sha256,
                "execution_contract_sha256": receipt.execution_contract_sha256,
                "archive_sha256": receipt.archive_sha256,
                "archive_bytes": receipt.archive_bytes,
                "members": [member.to_document() for member in receipt.members],
                "source_commit": receipt.source_commit,
                "source_tree": receipt.source_tree,
                "source_manifest_sha256": receipt.source_manifest_sha256,
                "deterministic_render_count": receipt.deterministic_render_count,
                "verification_archive_sha256": receipt.verification_archive_sha256,
            }
        )

    def _validate_archive(
        self,
        receipt: LocalPackageAssemblyReceipt,
        expected: tuple[TrackedPackageMember, ...],
    ) -> None:
        archive = _safe_existing_file(
            self.root,
            receipt.archive_path,
            label="staged package archive",
        )
        verification = _safe_existing_file(
            self.root,
            receipt.verification_archive_path,
            label="verification package archive",
        )
        if (
            archive.stat().st_size != receipt.archive_bytes
            or receipt.archive_bytes > _MAX_STAGE_ARCHIVE_BYTES
            or _file_sha256(archive) != receipt.archive_sha256
            or receipt.members != expected
            or receipt.deterministic_render_count != 2
            or receipt.verification_archive_sha256 != receipt.archive_sha256
            or verification.stat().st_size != receipt.archive_bytes
            or _file_sha256(verification) != receipt.verification_archive_sha256
            or archive.read_bytes() != verification.read_bytes()
            or receipt.receipt_sha256 != self._local_assembly_receipt_identity(receipt)
        ):
            raise AdapterFailure("local package assembly receipt identity drifted")
        observed: list[TrackedPackageMember] = []
        try:
            with tarfile.open(archive, mode="r:*") as handle:
                entries = handle.getmembers()
                if len(entries) > _MAX_STAGE_MEMBERS:
                    raise AdapterFailure("staged package archive has too many members")
                for entry in entries:
                    pure = PurePosixPath(entry.name)
                    if (
                        not entry.isfile()
                        or pure.is_absolute()
                        or ".." in pure.parts
                        or pure.as_posix() != entry.name
                        or entry.size > _MAX_STAGE_MEMBER_BYTES
                    ):
                        raise AdapterFailure("staged package archive member is unsafe")
                    stream = handle.extractfile(entry)
                    if stream is None:
                        raise AdapterFailure("staged package archive member is unreadable")
                    encoded = stream.read(_MAX_STAGE_MEMBER_BYTES + 1)
                    observed.append(
                        TrackedPackageMember(
                            path=entry.name,
                            bytes=len(encoded),
                            sha256=hashlib.sha256(encoded).hexdigest(),
                        )
                    )
        except (tarfile.TarError, OSError) as exc:
            raise AdapterFailure("staged package archive is invalid") from exc
        if tuple(observed) != expected:
            raise AdapterFailure("assembled archive bytes differ from tracked package closure")

    def assemble_local_package(self) -> str:
        operation = "host.assemble_local"
        self._begin(operation, "tracked-package-archive")
        try:
            members, source = self._load_runtime_package()
            assert self._runtime_budget is not None
            commit, tree = self._source_identity()
            request = LocalPackageAssemblyRequest(
                repository=self.repository,
                control_commit=commit,
                control_tree=tree,
                provider_contract_version=self.contract.version,
                plan_id=self.contract.plan_id,
                plan_sha256=self.contract.expected_plan_sha256,
                command_package_sha256=self._runtime_budget.command_package_sha256,
                execution_contract_sha256=self._runtime_budget.execution_contract_sha256,
                members=members,
                max_archive_bytes=_MAX_STAGE_ARCHIVE_BYTES,
                max_member_bytes=_MAX_STAGE_MEMBER_BYTES,
                max_members=_MAX_STAGE_MEMBERS,
            )
            source_manifest_sha = _identity(
                {
                    "source_commit": commit,
                    "source_tree": tree,
                    "members": [member.to_document() for member in members],
                }
            )
            receipt = self.low_level_effects.assemble_local_package(request)
            if (
                receipt.provider_contract_version != request.provider_contract_version
                or receipt.plan_id != request.plan_id
                or receipt.plan_sha256 != request.plan_sha256
                or receipt.command_package_sha256 != request.command_package_sha256
                or receipt.execution_contract_sha256 != request.execution_contract_sha256
                or receipt.source_commit != commit
                or receipt.source_tree != tree
                or receipt.source_manifest_sha256 != source_manifest_sha
            ):
                raise AdapterFailure("local package assembly source identity drifted")
            self._validate_archive(receipt, members)
            self._local_assembly_artifact = hold_sealed_artifact(
                self.held_transaction_root,
                receipt.archive_path,
                max_bytes=_MAX_STAGE_ARCHIVE_BYTES,
            )
            self._local_assembly_verification_artifact = hold_sealed_artifact(
                self.held_transaction_root,
                receipt.verification_archive_path,
                max_bytes=_MAX_STAGE_ARCHIVE_BYTES,
            )
            self._local_assembly_artifact.revalidate()
            self._local_assembly_verification_artifact.revalidate()
        except BaseException as exc:
            self._record(operation, "tracked-package-archive", "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"tracked package assembly failed: {exc}") from exc
        self._local_assembly = receipt
        self._package_assembly_evidence = {
            "command_package_sha256": self._runtime_budget.command_package_sha256,
            "execution_contract_sha256": self._runtime_budget.execution_contract_sha256,
            "plan_sha256": self._runtime_budget.plan_sha256,
            "package_source": source,
            "archive_sha256": receipt.archive_sha256,
            "archive_bytes": receipt.archive_bytes,
            "archive_member_count": len(receipt.members),
            "source_manifest_sha256": receipt.source_manifest_sha256,
            "deterministic_render_count": receipt.deterministic_render_count,
            "verification_archive_sha256": receipt.verification_archive_sha256,
            "contains_provider_handle": False,
            "contains_remote_path": False,
            "uploaded": False,
            "tracked_only": self.source_inputs is None,
            **(
                {
                    "candidate_source_binding_sha256": self.source_inputs.digest,
                    "source_classification": "non-scientific-no-network-non-live",
                }
                if self.source_inputs is not None
                else {}
            ),
        }
        self._primitive("resolve_registered_command_package")
        self._primitive("load_execution_contract")
        self._primitive("assemble_local_package:two-byte-identical-renders")
        self._primitive("validate_tracked_package_archive")
        self._record(operation, "tracked-package-archive", "passed")
        return receipt.receipt_sha256

    @staticmethod
    def _transfer_receipt_identity(receipt: HostPackageTransferReceipt) -> str:
        return _identity(
            {
                "binding": receipt.binding.to_document(),
                "remote_package_path": receipt.remote_package_path,
                "remote_manifest_path": receipt.remote_manifest_path,
                "remote_archive_bytes": receipt.remote_archive_bytes,
                "remote_archive_sha256": receipt.remote_archive_sha256,
                "remote_members": [member.to_document() for member in receipt.remote_members],
                "remote_member_manifest_sha256": receipt.remote_member_manifest_sha256,
                "host_acknowledgement_sha256": receipt.host_acknowledgement_sha256,
                "started_wall_time": receipt.started_wall_time,
                "completed_wall_time": receipt.completed_wall_time,
                "started_monotonic": receipt.started_monotonic,
                "completed_monotonic": receipt.completed_monotonic,
                "cleanup_state_sha256": receipt.cleanup_state_sha256,
                "phase_output_sha256s": list(receipt.phase_output_sha256s),
            }
        )

    def transfer_package(self, handle: ProviderHandle) -> str:
        """Transfer the held assembly only after the exact provider entry exists."""

        operation = "host.transfer"
        self._begin(operation, handle.opaque_identity)
        assembly = self._local_assembly
        held = self._local_assembly_artifact
        entry_path = self._entry_receipts.get(handle.launch_ordinal)
        campaign_root = self._campaign_roots.get(handle.launch_ordinal)
        if assembly is None or held is None:
            raise AdapterFailure("host transfer lacks the deterministic local assembly")
        if entry_path is None or campaign_root is None:
            raise AdapterFailure("host transfer cannot precede exact provider entry")
        try:
            held.revalidate()
            commit, tree = self._source_identity()
            entry_sha = _file_sha256(entry_path)
            binding = HostTransferBinding(
                provider_contract_version=self.contract.version,
                plan_id=self.contract.plan_id,
                host_run_id=self.contract.host_run_id,
                provider_handle_identity=handle.opaque_identity,
                provider_launch_ordinal=handle.launch_ordinal,
                provider_entry_receipt_sha256=entry_sha,
                local_assembly_receipt_sha256=assembly.receipt_sha256,
                source_commit=commit,
                source_tree=tree,
                remote_root=(
                    self.contract.remote_root
                    if self.source_inputs is None
                    else (self.root / f"offline-remote-{handle.launch_ordinal}").as_posix()
                ),
                candidate_source_binding_sha256=(
                    None if self.source_inputs is None else self.source_inputs.digest
                ),
            )
            started_wall = self.clock.wall_time()
            started_mono = self.clock.monotonic()
            assert self._execution_contract is not None
            request = HostPackageTransferRequest(
                binding=binding,
                provider_handle=handle,
                provider_entry_receipt_path=entry_path,
                local_assembly=assembly,
                requested_wall_time=started_wall,
                requested_monotonic=started_mono,
                transfer_deadline_monotonic=checked_deadline(
                    started_mono,
                    self._execution_contract.campaign.preflight_iteration_wall_seconds,
                    label="host package transfer",
                ),
            )
            try:
                receipt = self.low_level_effects.transfer_package_to_host(request)
            except HostPackageTransferRejected as exc:
                self._close_rejected_host_phase(handle, exc)
                raise ReplacementEligibleFailure(str(exc)) from exc
            returned_wall = self.clock.wall_time()
            returned_mono = self.clock.monotonic()
            for remote_value, label in (
                (receipt.remote_package_path, "remote package path"),
                (receipt.remote_manifest_path, "remote manifest path"),
            ):
                remote_path = PurePosixPath(remote_value)
                remote_root = PurePosixPath(binding.remote_root)
                if not remote_path.is_absolute() or not remote_root.is_absolute():
                    raise AdapterFailure(f"{label} is not absolute")
                try:
                    remote_path.relative_to(remote_root)
                except ValueError as exc:
                    raise AdapterFailure(f"{label} escaped the selected remote root") from exc
            start_wall = finite_time(receipt.started_wall_time, label="host transfer start wall")
            end_wall = finite_time(
                receipt.completed_wall_time,
                label="host transfer completion wall",
            )
            start_mono = finite_time(
                receipt.started_monotonic,
                label="host transfer start monotonic",
            )
            end_mono = finite_time(
                receipt.completed_monotonic,
                label="host transfer completion monotonic",
            )
            if (
                receipt.binding != binding
                or receipt.remote_archive_bytes != assembly.archive_bytes
                or receipt.remote_archive_sha256 != assembly.archive_sha256
                or receipt.remote_members != assembly.members
                or start_wall < started_wall
                or start_mono < started_mono
                or end_wall < start_wall
                or end_mono < start_mono
                or end_wall > returned_wall
                or end_mono > returned_mono
                or end_mono > request.transfer_deadline_monotonic
                or len(receipt.phase_output_sha256s) < 4
                or any(_HEX64.fullmatch(value) is None for value in receipt.phase_output_sha256s)
                or any(
                    _HEX64.fullmatch(value) is None
                    for value in (
                        receipt.remote_member_manifest_sha256,
                        receipt.host_acknowledgement_sha256,
                        receipt.cleanup_state_sha256,
                    )
                )
                or receipt.receipt_sha256 != self._transfer_receipt_identity(receipt)
            ):
                raise AdapterFailure("host package transfer receipt identity drifted")
            expected_member_manifest = _identity(
                [member.to_document() for member in assembly.members]
            )
            if receipt.remote_member_manifest_sha256 != expected_member_manifest:
                raise AdapterFailure("remote package member rehash differs from local assembly")
            held.revalidate()
        except ReplacementEligibleFailure:
            self._record(operation, handle.opaque_identity, "failed")
            raise
        except BaseException as exc:
            self._record(operation, handle.opaque_identity, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"host package transfer failed: {exc}") from exc
        self._host_transfers[handle.launch_ordinal] = receipt
        self._primitive("host-transfer-verify")
        self._record(operation, handle.opaque_identity, "passed")
        return receipt.receipt_sha256

    @staticmethod
    def _preflight_receipt_identity(receipt: HostPreflightReceipt) -> str:
        return _identity(
            {
                "binding": receipt.binding.to_document(),
                "previous_phase_receipt_sha256": receipt.previous_phase_receipt_sha256,
                "metadata_receipt_sha256": receipt.metadata_receipt_sha256,
                "remote_path_qualification_sha256": (receipt.remote_path_qualification_sha256),
                "started_wall_time": receipt.started_wall_time,
                "completed_wall_time": receipt.completed_wall_time,
                "started_monotonic": receipt.started_monotonic,
                "completed_monotonic": receipt.completed_monotonic,
                "cleanup_state_sha256": receipt.cleanup_state_sha256,
                "phase_output_sha256s": list(receipt.phase_output_sha256s),
            }
        )

    def _close_rejected_host_phase(
        self,
        handle: ProviderHandle,
        rejection: HostPreflightRejected | HostPackageTransferRejected,
    ) -> None:
        private_root = self._campaign_roots[handle.launch_ordinal]
        disposition = _safe_existing_file(
            self.root,
            rejection.disposition_path,
            label="preflight rejection disposition",
        )
        source_root = _safe_directory(
            self.root,
            rejection.source_root,
            label="preflight rejection source",
        )
        continuation = _safe_directory(
            self.root,
            rejection.remote_cleanup_journal,
            label="preflight cleanup journal",
        )
        transport = self.low_level_effects.campaign_closeout_transport(
            contract=self.contract,
            launch_ordinal=handle.launch_ordinal,
            handle=handle,
            clock=self.clock,
        )
        commit, _tree = self._source_identity()
        with self._campaign_writer_scope(cleanup=True), self.low_level_effects.campaign_scope():
            provider.closeout_campaign(
                contract=self.contract,
                repository=self.repository,
                package_commit=commit,
                authorization_ledger=self._metadata_overlay,
                dotenv=self._dotenv,
                private_root=private_root,
                transport=transport,
                preempirical_receipt=disposition,
                preempirical_source_root=source_root,
                remote_cleanup_journal=continuation,
                clock=self.clock.wall_time,
                sleeper=self.clock.sleep,
            )
        if not (private_root / "replacement-launch-eligibility.json").is_file():
            raise AdapterFailure("host closeout did not publish replacement eligibility")
        self._primitive("closeout_campaign")
        self._primitive("_publish_replacement_launch_eligibility")

    def preflight(self, handle: ProviderHandle) -> None:
        operation = "host.preflight"
        self._begin(operation, handle.opaque_identity)
        if (
            self._metadata_document is None
            or self._local_assembly is None
            or self._execution_contract is None
        ):
            raise AdapterFailure("host preflight lacks assembled package and metadata authority")
        entry_path = self._entry_receipts.get(handle.launch_ordinal)
        transfer = self._host_transfers.get(handle.launch_ordinal)
        if entry_path is None:
            raise AdapterFailure("host preflight lacks the retained provider-entry receipt")
        if transfer is None:
            raise AdapterFailure("host preflight cannot precede acknowledged package transfer")
        entry_sha = _file_sha256(entry_path)
        metadata_sha = metadata.model_metadata_receipt_sha256(self._metadata_receipt)
        requested_wall = self.clock.wall_time()
        requested_mono = self.clock.monotonic()
        binding = HostPhaseBinding(
            transfer=transfer.binding,
            host_transfer_receipt_sha256=transfer.receipt_sha256,
        )
        request = HostPreflightRequest(
            binding=binding,
            provider_handle=handle,
            campaign_private_root=self._campaign_roots[handle.launch_ordinal],
            provider_entry_receipt_path=entry_path,
            provider_entry_receipt_sha256=entry_sha,
            metadata_receipt_path=self._metadata_receipt,
            metadata_receipt_sha256=metadata_sha,
            requested_wall_time=requested_wall,
            requested_monotonic=requested_mono,
        )
        try:
            receipt = self.low_level_effects.preflight_host(request)
        except HostPreflightRejected as exc:
            try:
                self._close_rejected_host_phase(handle, exc)
            except BaseException as closeout_exc:
                self._record(operation, handle.opaque_identity, "failed")
                raise AdapterFailure(
                    f"retained host preflight closeout failed: {closeout_exc}"
                ) from closeout_exc
            self._record(operation, handle.opaque_identity, "failed")
            raise ReplacementEligibleFailure(str(exc)) from exc
        except BaseException as exc:
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure(f"host preflight effect failed: {exc}") from exc
        try:
            returned_wall = self.clock.wall_time()
            returned_mono = self.clock.monotonic()
            start_wall = finite_time(receipt.started_wall_time, label="host preflight start wall")
            end_wall = finite_time(
                receipt.completed_wall_time, label="host preflight completion wall"
            )
            start_mono = finite_time(
                receipt.started_monotonic, label="host preflight start monotonic"
            )
            end_mono = finite_time(
                receipt.completed_monotonic, label="host preflight completion monotonic"
            )
            if (
                receipt.binding != binding
                or receipt.previous_phase_receipt_sha256 != transfer.receipt_sha256
                or receipt.metadata_receipt_sha256 != metadata_sha
                or start_wall < requested_wall
                or start_mono < requested_mono
                or end_wall > returned_wall
                or end_mono > returned_mono
                or end_wall < start_wall
                or end_mono < start_mono
                or end_mono - start_mono
                > self._execution_contract.campaign.preflight_iteration_wall_seconds
                or len(receipt.phase_output_sha256s) < 2
                or any(_HEX64.fullmatch(value) is None for value in receipt.phase_output_sha256s)
                or _HEX64.fullmatch(receipt.cleanup_state_sha256) is None
                or receipt.receipt_sha256 != self._preflight_receipt_identity(receipt)
            ):
                raise AdapterFailure("host preflight receipt identity or timing drifted")
            _require_sha(
                receipt.remote_path_qualification_sha256,
                label="remote path qualification",
            )
            commit, _tree = self._source_identity()
            provider_entry = load_json(entry_path)
            if (
                provider_entry.get("model_metadata_receipt_sha256") != metadata_sha
                or provider_entry.get("provider_preflight_started_at_epoch") is None
            ):
                raise AdapterFailure(
                    "retained provider-entry receipt lacks exact metadata/start authority"
                )
            artifact_root = self.private_root / f"host-validation-{handle.launch_ordinal}"
            (artifact_root / self.contract.control_root_name).mkdir(parents=True, mode=0o700)
            host = _host_module(self.repository)
            host.validate_model_metadata_receipt_offline(
                receipt_path=self._metadata_receipt,
                repository=self.repository,
                package_commit=commit,
                provider_entry=provider_entry,
                artifact_root=artifact_root,
                contract=self.contract,
                source_inputs=self.source_inputs,
            )
        except BaseException as exc:
            self._record(operation, handle.opaque_identity, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"host preflight receipt validation failed: {exc}") from exc
        self._primitive("validate_model_metadata_receipt_offline")
        self._primitive("validate_host_preflight_receipt")
        self._host_preflights[handle.launch_ordinal] = receipt
        self._record(operation, handle.opaque_identity, "passed")

    @staticmethod
    def _qualification_receipt_identity(receipt: HostQualificationReceipt) -> str:
        values = asdict(receipt)
        values.pop("receipt_sha256")
        return _identity(values)

    def qualify(self, handle: ProviderHandle) -> str:
        operation = "host.qualify"
        self._begin(operation, handle.opaque_identity)
        if self._local_assembly is None:
            raise AdapterFailure("host qualification lacks its assembled package")
        entry_path = self._entry_receipts.get(handle.launch_ordinal)
        transfer = self._host_transfers.get(handle.launch_ordinal)
        preflight = self._host_preflights.get(handle.launch_ordinal)
        if entry_path is None:
            raise AdapterFailure("host qualification lacks provider-entry evidence")
        if transfer is None or preflight is None:
            raise AdapterFailure("host qualification cannot precede transfer and preflight")
        if (
            self.contract.replacement_image_tag is None
            or self.contract.image_materialization_policy is None
            or self.contract.active_image_qualification_id is None
            or self.contract.local_finalizer_qualification_id is None
        ):
            raise AdapterFailure("selected package lacks host qualification identities")
        requested_wall = self.clock.wall_time()
        requested_mono = self.clock.monotonic()
        binding = HostPhaseBinding(
            transfer=transfer.binding,
            host_transfer_receipt_sha256=transfer.receipt_sha256,
        )
        request = HostQualificationRequest(
            binding=binding,
            provider_handle=handle,
            preflight_receipt_sha256=preflight.receipt_sha256,
            replacement_image_tag=self.contract.replacement_image_tag,
            image_materialization_policy=self.contract.image_materialization_policy,
            active_image_qualification_id=self.contract.active_image_qualification_id,
            local_finalizer_qualification_id=(self.contract.local_finalizer_qualification_id),
            requested_wall_time=requested_wall,
            requested_monotonic=requested_mono,
        )
        try:
            receipt = self.low_level_effects.qualify_host(request)
            returned_wall = self.clock.wall_time()
            returned_mono = self.clock.monotonic()
            commit, _tree = self._source_identity()
            host = _host_module(self.repository)
            source_bindings = host.validate_finalizer_source(
                repository=self.repository,
                package_commit=commit,
                finalizer_commit=commit,
                source=self.repository / host.FINALIZER_RELATIVE_PATH,
                projection_source=(self.repository / host.FINALIZER_PROJECTION_RELATIVE_PATH),
                source_inputs=self.source_inputs,
            )
            source_sha, projection_sha, selector_sha, schema_sha = source_bindings[:4]
            exact_sha_fields = (
                receipt.image_materialization_receipt_sha256,
                receipt.python_interpreter_sha256,
                receipt.dependency_manifest_sha256,
                receipt.dependency_tree_sha256,
                receipt.browser_qualification_sha256,
                receipt.downstream_source_roles_sha256,
                receipt.finalizer_source_sha256,
                receipt.finalizer_projection_source_sha256,
                receipt.finalizer_selector_sha256,
                receipt.finalizer_schema_sha256,
                receipt.local_finalizer_qualification_sha256,
                receipt.local_finalizer_interpreter_sha256,
                receipt.local_finalizer_dependency_manifest_sha256,
                receipt.local_finalizer_dependency_tree_sha256,
                receipt.local_evaluator_dependency_tree_sha256,
                receipt.cleanup_readiness_sha256,
                *receipt.phase_output_sha256s,
            )
            if (
                receipt.binding != binding
                or receipt.previous_phase_receipt_sha256 != preflight.receipt_sha256
                or receipt.replacement_image_tag != request.replacement_image_tag
                or receipt.image_materialization_policy != request.image_materialization_policy
                or receipt.qualification_id != self.contract.active_image_qualification_id
                or receipt.local_finalizer_qualification_id
                != request.local_finalizer_qualification_id
                or re.fullmatch(r"sha256:[a-f0-9]{64}", receipt.image_digest) is None
                or not receipt.python_interpreter.startswith("/")
                or not receipt.local_finalizer_interpreter.startswith("/")
                or any(_HEX64.fullmatch(value) is None for value in exact_sha_fields)
                or receipt.finalizer_source_sha256 != source_sha
                or receipt.finalizer_projection_source_sha256 != projection_sha
                or receipt.finalizer_selector_sha256 != selector_sha
                or receipt.finalizer_schema_sha256 != schema_sha
                or receipt.downstream_source_roles_sha256 != _identity(source_bindings[5])
                or receipt.started_wall_time < requested_wall
                or receipt.started_monotonic < requested_mono
                or receipt.completed_wall_time < receipt.started_wall_time
                or receipt.completed_monotonic < receipt.started_monotonic
                or receipt.completed_wall_time > returned_wall
                or receipt.completed_monotonic > returned_mono
                or len(receipt.phase_output_sha256s) < 4
                or receipt.receipt_sha256 != self._qualification_receipt_identity(receipt)
            ):
                raise AdapterFailure("host qualification receipt identity drifted")
        except BaseException as exc:
            self._record(operation, handle.opaque_identity, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"host qualification failed: {exc}") from exc
        self._qualification = receipt
        self._primitive("validate_finalizer_source")
        self._primitive("validate_host_qualification_receipt")
        self._record(operation, handle.opaque_identity, "passed")
        return receipt.receipt_sha256

    @staticmethod
    def _freeze_receipt_identity(receipt: ScientificFreezeReceipt) -> str:
        return _identity(
            {
                "binding": receipt.binding.to_document(),
                "previous_phase_receipt_sha256": receipt.previous_phase_receipt_sha256,
                "manifest_sha256": receipt.manifest_sha256,
                "manifest_schema_version": receipt.manifest_schema_version,
                "manifest_projection_sha256": receipt.manifest_projection_sha256,
                "postfreeze_validation_sha256": receipt.postfreeze_validation_sha256,
                "started_wall_time": receipt.started_wall_time,
                "completed_wall_time": receipt.completed_wall_time,
                "started_monotonic": receipt.started_monotonic,
                "completed_monotonic": receipt.completed_monotonic,
                "cleanup_state_sha256": receipt.cleanup_state_sha256,
                "phase_output_sha256s": list(receipt.phase_output_sha256s),
            }
        )

    def freeze(self, handle: ProviderHandle) -> str:
        operation = "host.freeze"
        self._begin(operation, handle.opaque_identity)
        if (
            self._execution_contract is None
            or self._local_assembly is None
            or self._qualification is None
            or self._command_package_sha256 is None
            or self._command_document is None
            or self.contract.frozen_run_manifest_id is None
        ):
            raise AdapterFailure("scientific freeze lacks its exact qualified package")
        entry = self._entry_receipts.get(handle.launch_ordinal)
        transfer = self._host_transfers.get(handle.launch_ordinal)
        preflight = self._host_preflights.get(handle.launch_ordinal)
        if entry is None or transfer is None or preflight is None:
            raise AdapterFailure("scientific freeze lacks provider-entry evidence")
        entry_document = load_json(entry)
        command_manifests = self._command_document.get("manifests")
        if not isinstance(command_manifests, list):
            raise AdapterFailure("scientific freeze lacks canonical command manifests")
        command_argv_sha256s = [
            item.get("argv_sha256") for item in command_manifests if isinstance(item, dict)
        ]
        if len(command_argv_sha256s) != len(self.contract.run_ids) or any(
            not isinstance(value, str) for value in command_argv_sha256s
        ):
            raise AdapterFailure("scientific freeze command identities are incomplete")
        metadata_sha = metadata.model_metadata_receipt_sha256(self._metadata_receipt)
        commit, _tree = self._source_identity()
        binding = HostPhaseBinding(
            transfer=transfer.binding,
            host_transfer_receipt_sha256=transfer.receipt_sha256,
        )
        expected_projection: dict[str, object] = {
            "manifest_id": self.contract.frozen_run_manifest_id,
            "plan_id": self.contract.plan_id,
            "host_run_id": self.contract.host_run_id,
            "qualification_id": self.contract.active_image_qualification_id,
            "source_contract_sha256": entry_document.get("authorization_source_sha256"),
            "clean_package_commit": commit,
            "plan_sha256": self.contract.expected_plan_sha256,
            "execution_contract_sha256": self._execution_contract.sha256,
            "runtime_contract_sha256": _file_sha256(
                _host_module(self.repository).contract_paths(self.repository, self.contract)[
                    "runtime"
                ]
            ),
            "command_manifests_sha256": self._command_package_sha256,
            "provider_entry_receipt_sha256": _file_sha256(entry),
            "owned_instance_identity_sha256": handle.opaque_identity,
            "replacement_image_id": self._qualification.image_digest,
            "model_metadata_receipt_sha256": metadata_sha,
            "model_metadata_request_count": 1,
            "model_task_request_count": 0,
            "task_browser_action_count": 0,
            "actual_credential_exposure_detected": False,
            "credential_safety_stop_detected": False,
            "core_safety_stop_detected": False,
            "local_finalizer_qualification_sha256": (
                self._qualification.local_finalizer_qualification_sha256
            ),
            "local_finalizer_interpreter_sha256": (
                self._qualification.local_finalizer_interpreter_sha256
            ),
            "local_finalizer_interpreter_dependency_manifest_sha256": (
                self._qualification.local_finalizer_dependency_manifest_sha256
            ),
            "local_finalizer_interpreter_dependency_tree_sha256": (
                self._qualification.local_finalizer_dependency_tree_sha256
            ),
            "local_finalizer_evaluator_dependency_tree_sha256": (
                self._qualification.local_evaluator_dependency_tree_sha256
            ),
            "command_argv_sha256s": command_argv_sha256s,
            "attempt_order": list(self.contract.run_ids),
            "empirical_entry_crossed": False,
            "post_entry_code_science_image_freeze": True,
        }
        started_wall = self.clock.wall_time()
        started_mono = self.clock.monotonic()
        request = ScientificFreezeRequest(
            binding=binding,
            provider_handle=handle,
            frozen_manifest_id=self.contract.frozen_run_manifest_id,
            preflight_receipt_sha256=preflight.receipt_sha256,
            command_package_sha256=self._command_package_sha256,
            execution_contract_sha256=self._execution_contract.sha256,
            qualification_receipt_sha256=self._qualification.receipt_sha256,
            image_digest=self._qualification.image_digest,
            manifest_root=self.root,
            manifest_schema_version=RETAINED_FROZEN_MANIFEST_SCHEMA_VERSION,
            expected_manifest_projection=MappingProxyType(expected_projection),
            started_wall_time=started_wall,
            started_monotonic=started_mono,
        )
        try:
            receipt = self.low_level_effects.freeze_science(request)
            returned_wall = self.clock.wall_time()
            returned_mono = self.clock.monotonic()
            manifest_path = _safe_existing_file(
                self.root,
                receipt.manifest_path,
                label="frozen-run manifest",
            )
            validation_path = _safe_existing_file(
                self.root,
                receipt.postfreeze_validation_path,
                label="postfreeze validation",
            )
            validated_manifest = validate_full_dynamic_frozen_manifest(
                self.repository,
                manifest_path,
                contract=self.contract,
                expected_projection=request.expected_manifest_projection,
            )
            validate_postfreeze_receipt(
                validation_path,
                contract=self.contract,
                manifest_sha256=receipt.manifest_sha256,
            )
            end_wall = finite_time(receipt.completed_wall_time, label="freeze completion wall")
            end_mono = finite_time(receipt.completed_monotonic, label="freeze completion monotonic")
            if (
                receipt.binding != binding
                or receipt.previous_phase_receipt_sha256 != self._qualification.receipt_sha256
                or receipt.started_wall_time != started_wall
                or receipt.started_monotonic != started_mono
                or end_wall < started_wall
                or end_mono < started_mono
                or end_wall > returned_wall
                or end_mono > returned_mono
                or receipt.manifest_schema_version != request.manifest_schema_version
                or receipt.manifest_projection_sha256 != validated_manifest.projection_sha256
                or _file_sha256(manifest_path) != receipt.manifest_sha256
                or _file_sha256(validation_path) != receipt.postfreeze_validation_sha256
                or len(receipt.phase_output_sha256s) < 3
                or any(_HEX64.fullmatch(value) is None for value in receipt.phase_output_sha256s)
                or _HEX64.fullmatch(receipt.cleanup_state_sha256) is None
                or receipt.receipt_sha256 != self._freeze_receipt_identity(receipt)
            ):
                raise AdapterFailure("scientific freeze receipts drifted")
            owned_started = finite_time(
                entry_document.get("owned_lambda_started_at_epoch"),
                label="owned provider start",
            )
            prior_duration = finite_time(
                entry_document.get("prior_campaign_lambda_duration_seconds"),
                label="prior provider duration",
            )
            prior_cost = finite_time(
                entry_document.get("prior_campaign_lambda_cost_usd"),
                label="prior provider cost",
            )
            if owned_started > end_wall:
                raise AdapterFailure("provider ownership starts after the empirical freeze")
            campaign_wall, campaign_mono = self._frozen_campaign_origins(receipt)
            self._campaign_started_monotonic = campaign_mono
            self._campaign_deadline_monotonic = checked_deadline(
                campaign_mono,
                self._execution_contract.campaign.empirical_campaign_wall_seconds,
                label="empirical campaign",
            )
            with self._pilot_control_writer(self.contract.run_ids[0]) as (admit, observed):
                pilot.initialize_pilot_state(
                    self._pilot_state,
                    provider_contract=self.contract,
                    execution_contract_sha256=self._execution_contract.sha256,
                    pilot_started_at_epoch=campaign_wall,
                    lambda_started_at_epoch=owned_started,
                    prior_campaign_lambda_duration_seconds=prior_duration,
                    prior_campaign_lambda_cost_usd=prior_cost,
                    before_write=admit,
                    after_output_write=observed,
                )
        except BaseException as exc:
            self._record(operation, handle.opaque_identity, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"scientific freeze failed: {exc}") from exc
        self._freeze = receipt
        self._campaign_started_monotonic = campaign_mono
        self._campaign_deadline_monotonic = checked_deadline(
            campaign_mono,
            self._execution_contract.campaign.empirical_campaign_wall_seconds,
            label="empirical campaign",
        )
        self._primitive("publish_dynamic_frozen_run_manifest")
        self._primitive("validate_postfreeze_receipt")
        self._primitive("initialize_pilot_state")
        self._record(operation, handle.opaque_identity, "passed")
        return receipt.receipt_sha256

    @staticmethod
    def _frozen_campaign_origins(receipt: ScientificFreezeReceipt) -> tuple[float, float]:
        """Use the sealed empirical origin, preserving time spent returning the receipt."""
        document, digest = load_full_frozen_manifest(receipt.manifest_path)
        wall = finite_time(document.get("first_pair_started_at_epoch"), label="frozen pair start")
        if (
            digest != receipt.manifest_sha256
            or not receipt.started_wall_time <= wall <= receipt.completed_wall_time
        ):
            raise AdapterFailure("frozen empirical origin differs from its phase interval")
        monotonic = receipt.completed_monotonic - (receipt.completed_wall_time - wall)
        if not receipt.started_monotonic <= monotonic <= receipt.completed_monotonic:
            raise AdapterFailure("frozen empirical origin cannot bind the local monotonic interval")
        return wall, monotonic

    def _require_execution(self) -> pilot.PilotExecutionContract:
        if (
            self._execution_contract is None
            or self._runtime_budget is None
            or self._command_document is None
            or self._freeze is None
            or not self._pilot_state.is_file()
        ):
            raise AdapterFailure("condition runtime lacks its frozen package state")
        return self._execution_contract

    def _campaign_remaining(self) -> tuple[float, float]:
        if self._campaign_started_monotonic is None or self._campaign_deadline_monotonic is None:
            raise AdapterFailure("empirical campaign monotonic deadline is unavailable")
        now = self.clock.monotonic()
        if now > self._campaign_deadline_monotonic:
            raise AdapterFailure("empirical campaign monotonic deadline expired")
        return now, self._campaign_deadline_monotonic - now

    def _campaign_accountant(self) -> ProviderBudgetBoundary:
        if self._runtime_budget is None:
            raise AdapterFailure("campaign writer lacks validated aggregate policy")
        if self._campaign_output_boundary is None:
            self._campaign_output_boundary = ProviderBudgetBoundary(
                routing=ImmutableModelRouting.locked(),
                aggregate_caps=self._runtime_budget.aggregate_caps,
                condition_caps=None,
                monotonic=self.clock.monotonic,
                initial_aggregate_usage=self._aggregate_usage,
                initial_aggregate_observed_usage=self._aggregate_observed_usage,
            )
        boundary = self._campaign_output_boundary
        if self._campaign_cleanup_remaining is None:
            # Fund bounded cleanup before provider entry, within the same exact
            # aggregate cap. This does not enter an empirical condition.
            boundary.reserve_campaign_output_bytes(MAX_ESSENTIAL_FAILURE_BYTES)
            self._campaign_cleanup_remaining = MAX_ESSENTIAL_FAILURE_BYTES
        return boundary

    def _carry_campaign_accounting(self, boundary: ProviderBudgetBoundary) -> None:
        document = boundary.accounting_document()
        upper = cast(Mapping[str, object], document["reserved_upper_bound"])
        lower = cast(Mapping[str, object], document["observed_lower_bound"])
        self._aggregate_usage = pilot.usage_from_document(upper["aggregate"])
        self._aggregate_observed_usage = pilot.usage_from_document(lower["aggregate"])

    @contextmanager
    def _campaign_writer_scope(self, *, cleanup: bool = False) -> Iterator[None]:
        boundary = self._campaign_accountant()
        first_writer = len(self._campaign_writes)
        observation_lock = threading.Lock()
        denied_here = False

        def observe(count: int) -> None:
            with observation_lock:
                boundary.observe_campaign_output_bytes(count)

        controls = self.low_level_effects.campaign_low_level_controls()
        capabilities = {
            (
                provider.launch_capability_path(slot, contract=self.contract)
                if controls is None
                else controls.capability_path(slot, self.contract)
            )
            for slot in range(1, self.contract.max_launch_count + 1)
        }

        def admit(path: Path, size: int, role: CampaignWriterRole) -> CampaignWriteAllowance:
            nonlocal denied_here
            if type(size) is not int or size < 0:
                raise AdapterFailure("campaign writer has invalid output size")
            if not path.is_absolute() or ".." in path.parts:
                raise AdapterFailure("campaign writer path is not canonical")
            if not path.is_relative_to(self.root) and path not in capabilities:
                raise AdapterFailure("campaign writer is outside its exact owned scope")
            root_device = self.root.lstat().st_dev
            for parent in (path, *path.parents):
                try:
                    metadata = parent.lstat()
                except FileNotFoundError:
                    continue
                if stat.S_ISLNK(metadata.st_mode):
                    raise AdapterFailure("campaign writer path contains a symlink")
                if parent.is_relative_to(self.root) and (
                    metadata.st_uid != os.getuid() or metadata.st_dev != root_device
                ):
                    raise AdapterFailure("campaign writer crossed its owned filesystem")
                if parent == path and (
                    not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                ):
                    raise AdapterFailure("campaign writer target is not an exact regular file")
            if cleanup or campaign_cleanup_active():
                remaining = self._campaign_cleanup_remaining
                if remaining is None or size > remaining:
                    denied_here = True
                    self._campaign_admission_blocked = True
                    raise ProviderBudgetExceeded("bounded campaign cleanup output exhausted")
                self._campaign_cleanup_remaining = remaining - size
            else:
                if self._campaign_admission_blocked:
                    raise ProviderBudgetExceeded("campaign output admission is already blocked")
                try:
                    boundary.reserve_campaign_output_bytes(size)
                except ProviderBudgetExceeded:
                    denied_here = True
                    self._campaign_admission_blocked = True
                    raise
            allowance = CampaignWriteAllowance(
                path,
                role,
                size,
                observe,
                cleanup=cleanup or campaign_cleanup_active(),
            )
            self._campaign_writes.append(allowance)
            return allowance

        try:
            with campaign_output_scope(admit):
                yield
            if denied_here or (self._campaign_admission_blocked and not cleanup):
                raise ProviderBudgetExceeded("caught campaign output denial remains blocking")
        finally:
            for allowance in self._campaign_writes[first_writer:]:
                allowance.closed = True
            self._carry_campaign_accounting(boundary)

    def _condition_accountant(self, run_id: str) -> _AccountingObserver:
        """Establish the one condition accountant before its first control write."""
        existing = self._condition_observers.get(run_id)
        if existing is not None:
            if existing._failure_output_remaining is None:
                raise AdapterFailure("condition output admission failed before its first writer")
            return existing
        if self._runtime_budget is None or self._campaign_deadline_monotonic is None:
            raise AdapterFailure("condition control writer lacks its frozen budget")
        if self._campaign_admission_blocked:
            raise ProviderBudgetExceeded("condition entry follows blocked campaign output")
        caps = self._runtime_budget.condition_caps.get(run_id)
        if caps is None:
            raise AdapterFailure("condition control writer has no exact run cap")
        previous = self._campaign_accountant()
        self._carry_campaign_accounting(previous)
        boundary = ProviderBudgetBoundary(
            routing=ImmutableModelRouting.locked(),
            aggregate_caps=self._runtime_budget.aggregate_caps,
            condition_caps=caps,
            monotonic=self.clock.monotonic,
            initial_aggregate_usage=self._aggregate_usage,
            initial_aggregate_observed_usage=self._aggregate_observed_usage,
            initial_campaign_output_granted=previous.campaign_output_granted,
            initial_campaign_output_observed=previous.campaign_output_observed,
        )
        self._campaign_output_boundary = boundary
        observer = _AccountingObserver(
            run_id=run_id,
            model_revision=self._runtime_budget.model_revision,
            service_tier=self._runtime_budget.service_tier,
            boundary=boundary,
            prior_call_ids=frozenset(self._seen_call_ids),
            prior_logical_call_ids=frozenset(self._seen_logical_call_ids),
            clock=self.clock,
            campaign_deadline_monotonic=self._campaign_deadline_monotonic,
        )
        self._condition_observers[run_id] = observer
        observer.prepare_failure_output()
        return observer

    @contextmanager
    def _pilot_control_writer(
        self, run_id: str, *, extra_paths: tuple[Path, ...] = (), failure: bool = False
    ) -> Iterator[tuple[Callable[[Path, int], None], Callable[[int], None]]]:
        """Fund before growth and count actual writes, including replaced state bytes.

        Mutable state can shrink when a reservation is cleared. Its signed net
        occupancy change is not this monotonic controller-write counter. Observe
        each successful write syscall, including any retained partial temporary.
        No capacity is returned by replacement and no observation admits bytes.
        """
        observer = self._condition_accountant(run_id)
        host = _host_module(self.repository)
        allowed = (self._pilot_state, *extra_paths)
        if len(set(allowed)) != len(allowed) or any(
            path.parent not in (self._pilot_state.parent, self.public_root) for path in extra_paths
        ):
            raise AdapterFailure("control writer has an undeclared publication path")

        roots = tuple(dict.fromkeys(path.parent for path in allowed))
        before_bytes = sum(host.full_attempt_tree_usage(root).bytes for root in roots)
        before_files = {
            path: path.stat(follow_symlinks=False) for path in allowed if os.path.lexists(path)
        }
        admitted: dict[Path, int] = {}
        written_bytes = 0

        def admit(path: Path, count: int) -> None:
            if path not in allowed or any(part.is_symlink() for part in (path, *path.parents)):
                raise AdapterFailure("pilot writer escaped its exact control path")
            if path in admitted:
                raise AdapterFailure("control publication was admitted twice in one operation")
            if failure:
                observer.consume_failure_output_bytes(count=count)
            else:
                observer.allocate_controller_output_bytes(count=count)
            admitted[path] = count

        def observed(count: int) -> None:
            nonlocal written_bytes
            if (
                type(count) is not int
                or count < 0
                or written_bytes + count > sum(admitted.values())
            ):
                raise AdapterFailure("control write observation lacks its preceding admission")
            observer.observe_controller_output_bytes(count=count)
            written_bytes += count

        try:
            yield admit, observed
        finally:
            # Keep an independent signed occupancy check. Replacing an owned
            # mutable state retires its previous file bytes; an interrupted
            # temporary remains counted. This check never grants output or
            # clamps a decrease away, and includes the whole declared roots.
            try:
                retired_bytes = 0
                for path, before in before_files.items():
                    after = path.stat(follow_symlinks=False)
                    if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
                        if path not in admitted:
                            raise AdapterFailure("unadmitted control replacement")
                        retired_bytes += before.st_size
                growth = (
                    sum(host.full_attempt_tree_usage(root).bytes for root in roots) - before_bytes
                )
                if growth != written_bytes - retired_bytes:
                    raise AdapterFailure("control writer and retained occupancy do not reconcile")
            finally:
                self._record_boundary_state(run_id, observer)

    def reserve(self, run_id: str) -> str:
        operation = "condition.reserve"
        self._begin(operation, run_id)
        execution = self._require_execution()
        if run_id not in self.contract.run_ids:
            raise AdapterFailure("condition reservation is outside the exact attempt order")
        assert self._runtime_budget is not None
        caps = self._runtime_budget.condition_caps.get(run_id)
        if caps is None:
            raise AdapterFailure("condition reservation lacks its exact package cap")
        _now, remaining = self._campaign_remaining()
        if not execution.campaign.admit_remaining(
            remaining_campaign_seconds=remaining,
            attempt_hard_wall_seconds=int(caps.max_wall_seconds),
        ):
            raise AdapterFailure("remaining campaign wall cannot admit the exact condition")
        start_intent = _identity(
            {
                "provider_contract_version": self.contract.version,
                "execution_contract_sha256": execution.sha256,
                "run_id": run_id,
                "command_package_sha256": self._command_package_sha256,
            }
        )
        try:
            with self._pilot_control_writer(run_id) as (admit, observed):
                pilot.reserve_condition_start(
                    self._pilot_state,
                    execution_contract_sha256=execution.sha256,
                    run_id=run_id,
                    start_intent_sha256=start_intent,
                    before_write=admit,
                    after_output_write=observed,
                )
        except BaseException as exc:
            self._record(operation, run_id, "failed")
            raise AdapterFailure(f"condition reservation failed: {exc}") from exc
        self._primitive("reserve_condition_start")
        self._record(operation, run_id, "passed")
        return start_intent

    def enter(self, run_id: str) -> str:
        operation = "condition.enter"
        self._begin(operation, run_id)
        execution = self._require_execution()
        released_at = self.clock.wall_time()
        released_monotonic = self.clock.monotonic()
        release = _identity(
            {
                "run_id": run_id,
                "execution_contract_sha256": execution.sha256,
                "released_at_wall_time": released_at,
            }
        )
        try:
            with self._pilot_control_writer(run_id) as (admit, observed):
                pilot.mark_empirical_entry(
                    self._pilot_state,
                    execution_contract_sha256=execution.sha256,
                    run_id=run_id,
                    supervised_release_receipt_sha256=release,
                    before_write=admit,
                    after_output_write=observed,
                )
        except BaseException as exc:
            self._record(operation, run_id, "failed")
            raise AdapterFailure(f"empirical entry failed: {exc}") from exc
        self._condition_started_wall[run_id] = released_at
        self._condition_started_monotonic[run_id] = released_monotonic
        self._entered_run_ids.append(run_id)
        self._primitive("mark_empirical_entry")
        self._record(operation, run_id, "passed")
        return release

    def _manifest_for_run(self, run_id: str) -> dict[str, object]:
        if self._command_document is None:
            raise AdapterFailure("command package is unavailable")
        manifests = self._command_document.get("manifests")
        if not isinstance(manifests, list):
            raise AdapterFailure("command package manifest list is unavailable")
        matches = [
            cast(dict[str, object], item)
            for item in manifests
            if isinstance(item, dict) and item.get("run_id") == run_id
        ]
        if len(matches) != 1:
            raise AdapterFailure("condition command manifest is absent or duplicated")
        return matches[0]

    def _record_boundary_state(
        self,
        run_id: str,
        observer: _AccountingObserver,
    ) -> None:
        observer.reconcile_closed_remote_output()
        observer.reconcile_controller_output()
        document = observer.boundary.accounting_document()
        self._accounting[run_id] = document
        # Carry the accountant's admitted upper bound, including capacity whose
        # consumption acknowledgement was lost. Observed bytes alone cannot
        # release a prior condition's reservation when the next boundary starts.
        upper = cast(Mapping[str, object], document["reserved_upper_bound"])
        lower = cast(Mapping[str, object], document["observed_lower_bound"])
        self._aggregate_usage = pilot.usage_from_document(upper["aggregate"])
        self._aggregate_observed_usage = pilot.usage_from_document(lower["aggregate"])
        self._seen_call_ids.update(observer.call_ids)
        self._seen_logical_call_ids.update(observer.logical_call_ids)

    @staticmethod
    def _artifact_binding(artifacts: tuple[HeldArtifact, ...]) -> str:
        return _identity([artifact.to_public_document() for artifact in artifacts])

    def _hold_artifact_set(
        self,
        paths: tuple[Path, ...],
        *,
        max_member_bytes: int | None = None,
        max_json_member_bytes: int | None = None,
        max_files: int | None = None,
        max_total_bytes: int | None = None,
    ) -> tuple[HeldArtifact, ...]:
        """Hold one exact set and derive every optional admission value from fstat."""

        held: list[HeldArtifact] = []
        try:
            candidates = tuple(sorted(set(paths), key=lambda item: item.as_posix()))
            if max_files is not None and len(candidates) > max_files:
                raise AdapterFailure("held artifact set exceeds its finite entry cap")
            for path in candidates:
                member_cap = max_member_bytes
                if (
                    path.suffix.casefold() in {".json", ".jsonl"}
                    and max_json_member_bytes is not None
                ):
                    member_cap = (
                        max_json_member_bytes
                        if member_cap is None
                        else min(member_cap, max_json_member_bytes)
                    )
                held.append(
                    hold_sealed_artifact(
                        self.held_transaction_root,
                        path,
                        max_bytes=member_cap,
                    )
                )
            identities = {(item.device, item.inode) for item in held}
            if len(identities) != len(held):
                raise AdapterFailure("held artifact roles share one filesystem identity")
            if max_files is not None and len(held) > max_files:
                raise AdapterFailure("held artifact set exceeds its finite entry cap")
            if max_total_bytes is not None and sum(item.bytes for item in held) > max_total_bytes:
                raise AdapterFailure("held artifact set exceeds its aggregate byte cap")
            return tuple(held)
        except BaseException:
            for artifact in held:
                artifact.close()
            raise

    @staticmethod
    def _revalidate_artifacts(
        artifacts: tuple[HeldArtifact, ...],
        *,
        allow_root_path_mismatch: bool = False,
    ) -> None:
        for artifact in artifacts:
            artifact.revalidate(allow_root_path_mismatch=allow_root_path_mismatch)

    @staticmethod
    def _load_held_json(artifact: HeldArtifact, *, label: str) -> dict[str, object]:
        try:
            value = json.loads(artifact.read_bytes())
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise AdapterFailure(f"{label} is not valid JSON") from exc
        if not isinstance(value, dict):
            raise AdapterFailure(f"{label} must contain one JSON object")
        return cast(dict[str, object], value)

    @staticmethod
    def _load_canonical_held_json(
        artifact: HeldArtifact,
        *,
        label: str,
    ) -> dict[str, object]:
        """Load canonical JSON while rejecting duplicate keys and extensions."""

        encoded = artifact.read_bytes()

        def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise AdapterFailure(f"{label} contains a duplicate JSON key")
                result[key] = value
            return result

        try:
            value = json.loads(encoded, object_pairs_hook=reject_duplicates)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise AdapterFailure(f"{label} is not strict JSON") from exc
        if not isinstance(value, dict) or encoded != _canonical_bytes(value):
            raise AdapterFailure(f"{label} is not canonical JSON")
        return cast(dict[str, object], value)

    @staticmethod
    def _reject_private_failure_structure(
        value: object, *, label: str, reject_absolute_paths: bool = True
    ) -> None:
        forbidden_key_tokens = (
            "api_key",
            "authorization_header",
            "credential_hash",
            "credential_sha",
            "headers",
            "private_path",
            "absolute_path",
        )

        def visit(item: object, path: str) -> None:
            if isinstance(item, dict):
                for raw_key, child in item.items():
                    key = str(raw_key).casefold()
                    if any(token in key for token in forbidden_key_tokens):
                        raise AdapterFailure(f"{label} contains a secret-shaped field at {path}")
                    visit(child, f"{path}.{raw_key}")
            elif isinstance(item, list):
                for index, child in enumerate(item):
                    visit(child, f"{path}[{index}]")
            elif reject_absolute_paths and isinstance(item, str) and item.startswith("/"):
                raise AdapterFailure(f"{label} contains a private absolute path at {path}")

        visit(value, "$")

    def _validate_failure_schema(
        self,
        relative_schema: str,
        document: Mapping[str, object],
        *,
        label: str,
    ) -> None:
        schema = load_json(self.repository / relative_schema)
        errors = sorted(
            Draft202012Validator(
                schema,
                registry=local_schema_registry(self.repository / "schemas"),
            ).iter_errors(document),
            key=lambda error: tuple(str(item) for item in error.absolute_path),
        )
        if errors:
            raise AdapterFailure(f"{label} fails its exact schema: {errors[0].message}")

    def _enumerate_essential_envelope(self, root: Path) -> tuple[Path, ...]:
        """Enumerate candidate names through held no-follow directory descriptors."""

        try:
            relative_root = root.relative_to(self.held_transaction_root.path).as_posix()
        except ValueError as exc:
            raise AdapterFailure("essential failure root is outside the held transaction") from exc
        try:
            root_fd = self.held_transaction_root.open_relative_no_follow(
                relative_root,
                flags=os.O_RDONLY | os.O_DIRECTORY,
            )
        except (OSError, ValueError) as exc:
            raise AdapterFailure("essential failure root cannot be held for enumeration") from exc
        members: list[Path] = []

        def visit(directory_fd: int, prefix: PurePosixPath) -> None:
            try:
                names = sorted(os.listdir(directory_fd))
            except OSError as exc:
                raise AdapterFailure("essential failure directory enumeration failed") from exc
            for name in names:
                if not name or name in {".", ".."} or "/" in name:
                    raise AdapterFailure("essential failure contains an unsafe member name")
                relative = prefix / name
                try:
                    metadata_value = os.stat(
                        name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                except OSError as exc:
                    raise AdapterFailure(
                        "essential failure member changed during enumeration"
                    ) from exc
                mode = stat.S_IMODE(metadata_value.st_mode)
                if stat.S_ISDIR(metadata_value.st_mode):
                    if metadata_value.st_uid != os.getuid() or mode & 0o022:
                        raise AdapterFailure("essential failure contains an unsafe directory")
                    try:
                        child_fd = os.open(
                            name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=directory_fd,
                        )
                    except OSError as exc:
                        raise AdapterFailure(
                            "essential failure directory changed during enumeration"
                        ) from exc
                    try:
                        held_metadata = os.fstat(child_fd)
                        if (
                            (held_metadata.st_dev, held_metadata.st_ino)
                            != (metadata_value.st_dev, metadata_value.st_ino)
                            or not stat.S_ISDIR(held_metadata.st_mode)
                            or held_metadata.st_uid != os.getuid()
                            or stat.S_IMODE(held_metadata.st_mode) & 0o022
                        ):
                            raise AdapterFailure(
                                "essential failure directory identity changed during enumeration"
                            )
                        visit(child_fd, relative)
                    finally:
                        os.close(child_fd)
                    continue
                members.append(self.held_transaction_root.path / Path(relative.as_posix()))
                if len(members) > MAX_ESSENTIAL_FAILURE_FILES:
                    raise AdapterFailure("essential failure exceeds its finite candidate cap")

        try:
            visit(root_fd, PurePosixPath(relative_root))
        finally:
            os.close(root_fd)
        return tuple(members)

    @staticmethod
    def _validate_condition_ledgers(
        *,
        run_id: str,
        observer: _AccountingObserver,
        call_ledger: Path,
        browser_ledger: Path,
    ) -> None:
        call_document = load_json(call_ledger)
        browser_document = load_json(browser_ledger)
        raw_calls = call_document.get("calls")
        raw_actions = browser_document.get("actions")
        accounting = observer.boundary.accounting_document()
        accounting_calls = accounting.get("calls")
        if (
            call_document.get("run_id") != run_id
            or browser_document.get("run_id") != run_id
            or not isinstance(raw_calls, list)
            or not isinstance(raw_actions, list)
            or not isinstance(accounting_calls, list)
            or len(raw_calls) != len(observer.call_order)
            or len(raw_actions) != len(observer.action_order)
            or len(accounting_calls) != len(observer.call_order)
        ):
            raise AdapterFailure("condition ledgers do not cover the authoritative events")
        accounting_by_id = {
            row.get("call_id"): row
            for row in accounting_calls
            if isinstance(row, dict) and isinstance(row.get("call_id"), str)
        }
        if len(accounting_by_id) != len(observer.call_order):
            raise AdapterFailure("condition accounting call identities are duplicated")
        for index, raw in enumerate(raw_calls):
            if not isinstance(raw, dict):
                raise AdapterFailure("condition call ledger row is malformed")
            call_id = observer.call_order[index]
            logical_id = observer.logical_call_order[index]
            authoritative = accounting_by_id.get(call_id)
            if (
                authoritative is None
                or raw.get("call_id") != call_id
                or raw.get("logical_call_id") != logical_id
                or raw.get("logical_call_id") != authoritative.get("logical_call_id")
                or raw.get("role") != authoritative.get("role")
                or raw.get("model") != authoritative.get("model")
                or raw.get("service_tier") != observer.service_tier
                or raw.get("terminal_state") != authoritative.get("terminal_state")
                or _HEX64.fullmatch(str(raw.get("response_sha256"))) is None
            ):
                raise AdapterFailure("condition call ledger contradicts shared accounting")
        for index, raw in enumerate(raw_actions):
            if (
                not isinstance(raw, dict)
                or raw.get("action_id") != observer.action_order[index]
                or raw.get("terminal_state") != "completed"
            ):
                raise AdapterFailure("condition browser ledger contradicts shared accounting")

    def _validate_condition_bridge(
        self,
        *,
        request: ConditionExecutionRequest,
        observer: _AccountingObserver,
        raw_root: Path,
        raw_manifest_sha256: str,
        raw_receipt_sha256: str,
        evidence: ConditionBridgeEvidence | None,
        artifacts: tuple[HeldArtifact, ...],
    ) -> str | None:
        """Require and hold the complete duplex chain for every external-live session."""

        if evidence is None:
            if self.authorization_context.execution_mode is EffectExecutionMode.EXTERNAL_LIVE:
                raise AdapterFailure(
                    "external-live condition lacks its complete remote bridge evidence"
                )
            return None
        expected_evidence = expected_condition_bridge_evidence(
            transaction_root=self.root,
            raw_root=raw_root,
            run_id=request.run_id,
        )
        if evidence != expected_evidence:
            raise AdapterFailure("condition bridge evidence paths or selector drifted")
        expected_binding = ConditionSessionBinding(
            session_id=evidence.session_id,
            provider_contract_version=request.provider_contract_version,
            plan_id=request.plan_id,
            host_run_id=self.contract.host_run_id,
            condition_run_id=request.run_id,
            evaluator_run_id=request.evaluator_run_id,
            frozen_manifest_sha256=request.frozen_manifest_sha256,
        )
        by_path = {artifact.path: artifact for artifact in artifacts}
        bridge_paths = tuple(
            value
            for value in (
                evidence.shared_transcript_path,
                evidence.remote_journal_path,
                evidence.relay_prefix_path,
                evidence.relay_transcript_path,
                evidence.runtime_detachment_path,
                evidence.host_terminal_receipt_path,
                evidence.shared_terminal_receipt_path,
            )
        )
        if any(path not in by_path for path in bridge_paths):
            raise AdapterFailure("condition bridge evidence lacks one held artifact")
        try:
            validated = validate_condition_bridge_evidence(
                self.repository,
                evidence,
                expected_binding=expected_binding,
                raw_manifest_sha256=raw_manifest_sha256,
                raw_receipt_sha256=raw_receipt_sha256,
                shared_accounting=observer.protocol_accounting_document(),
                reader=lambda path: by_path[path].read_bytes(),
            )
        except (KeyError, RemoteBridgeError, ValueError) as exc:
            raise AdapterFailure("condition bridge evidence failed shared validation") from exc
        self._revalidate_artifacts(tuple(by_path[path] for path in bridge_paths))
        return validated.evidence_binding_sha256

    @staticmethod
    def _condition_failure_class(exc: BaseException) -> ConditionFailureClass:
        if isinstance(exc, ConditionKnownProviderError):
            return ConditionFailureClass.KNOWN_PROVIDER
        if isinstance(exc, ConditionKnownTransportError):
            return ConditionFailureClass.KNOWN_TRANSPORT
        if isinstance(exc, ConditionAmbiguousSend):
            return ConditionFailureClass.AMBIGUOUS_SEND
        if isinstance(
            exc,
            (ConditionResponseAccountingIncomplete, ProviderResponseReceiptError),
        ):
            return ConditionFailureClass.RESPONSE_ACCOUNTING_INCOMPLETE
        if isinstance(exc, ProviderBudgetExceeded):
            return ConditionFailureClass.BUDGET_ADMISSION
        if isinstance(exc, AdapterFailure):
            return ConditionFailureClass.OUTCOME_VALIDATION
        return ConditionFailureClass.PROCESS_CRASH

    def _hold_retained_failure_source(
        self,
        request: ConditionExecutionRequest,
        source: RetainedConditionSource,
        bridge_artifacts: tuple[HeldArtifact, ...],
    ) -> tuple[tuple[HeldArtifact, ...], dict[str, object]]:
        return cast(
            tuple[tuple[HeldArtifact, ...], dict[str, object]],
            _host_module(self.repository).hold_retained_condition_source(
                self.held_transaction_root,
                request,
                source,
                bridge_artifacts,
                condition_manifest=self._manifest_for_run(request.run_id),
                clock=self.clock.wall_time,
            ),
        )

    def _validate_and_seal_condition_failure(
        self,
        *,
        request: ConditionExecutionRequest,
        observer: _AccountingObserver,
        stopping_phase: str = "condition-execution",
        failure_class: ConditionFailureClass,
        process_exit_code: int | None,
        completed: bool,
        answer: str | None,
        existing: ConditionInfrastructureFailureOutcome | None = None,
        retained_source: RetainedConditionSource | None = None,
        bridge_evidence: ConditionBridgeEvidence | None = None,
        partial_bridge_evidence: ConditionBridgePrefixEvidence | None = None,
    ) -> EssentialFailureRecord:
        """Validate, seal, export, and retain one consumed infrastructure failure."""

        execution = self._require_execution()
        observer.boundary.close_in_flight(grace_seconds=0.0, sleeper=self.clock.sleep)
        accounting = observer.boundary.accounting_document()
        calls = accounting.get("calls")
        unknown_call_ids = tuple(
            cast(str, item["call_id"])
            for item in cast(list[dict[str, object]], calls if isinstance(calls, list) else [])
            if isinstance(item, dict)
            and isinstance(item.get("call_id"), str)
            and item.get("terminal_state") == "sent_outcome_unknown"
        )
        partial_raw_root = self.root / request.raw_output_root
        preservation = ConditionFailurePreservationRequest(
            execution=request,
            failure_class=failure_class,
            process_exit_code=process_exit_code,
            completed=completed,
            answer=answer,
            error=failure_class.value,
            partial_raw_root=partial_raw_root,
            accounting_document=accounting,
            call_ids=tuple(observer.call_order),
            logical_call_ids=tuple(observer.logical_call_order),
            browser_actions=tuple(
                (action_id, observer.action_terminal_states[action_id])
                for action_id in observer.action_order
            ),
            unknown_call_ids=unknown_call_ids,
            output_bytes=observer.output_total_bytes or 0,
            retry_count=0,
            retained_source=retained_source,
            partial_bridge_evidence=partial_bridge_evidence,
            condition_manifest=self._manifest_for_run(request.run_id),
            output_observer=observer,
            bridge_evidence=bridge_evidence
            or (
                self._condition_outcomes[request.run_id].bridge_evidence
                if request.run_id in self._condition_outcomes
                else None
            ),
        )
        outcome = (
            existing
            if existing is not None
            else self.low_level_effects.preserve_condition_failure(preservation)
        )
        expected_root = (
            partial_raw_root.parent / "derived-condition/essential-failure"
            if retained_source is not None
            else partial_raw_root.parent / "essential-failure"
        )
        if (
            outcome.retained_source != retained_source
            or outcome.partial_bridge_evidence != partial_bridge_evidence
        ):
            raise AdapterFailure("essential failure switched its retained source")
        root = _safe_directory(self.root, outcome.essential_root, label="essential failure root")
        self._essential_failure_roots.add(root.relative_to(self.root).as_posix())
        payload_root = _safe_directory(
            root,
            root / "payload",
            label="essential failure payload root",
        )
        manifest_path = _safe_existing_file(
            root,
            outcome.essential_manifest_path,
            label="essential failure manifest",
        )
        receipt_path = _safe_existing_file(
            root,
            outcome.essential_receipt_path,
            label="essential failure receipt",
        )
        role_paths = tuple(
            _safe_existing_file(payload_root, path, label="essential failure role")
            for path in (
                outcome.call_ledger_path,
                outcome.browser_ledger_path,
                outcome.process_outcome_path,
                outcome.completion_path,
            )
        )
        if outcome.stdout_path is not None:
            role_paths += (
                _safe_existing_file(payload_root, outcome.stdout_path, label="essential stdout"),
            )
        if outcome.stderr_path is not None:
            role_paths += (
                _safe_existing_file(payload_root, outcome.stderr_path, label="essential stderr"),
            )
        bridge_copy_paths: tuple[Path, ...] = ()
        bridge_paths: tuple[Path, ...] = ()
        if outcome.bridge_evidence is not None:
            bridge_copy_paths = tuple(
                _safe_existing_file(
                    payload_root,
                    payload_root / name,
                    label="essential bridge transcript prefix",
                )
                for name in (
                    "duplex-remote-event-journal.json",
                    "duplex-transcript-prefix.json",
                    "duplex-runtime-detached.json",
                )
            )
            bridge_paths = tuple(
                _safe_existing_file(
                    self.root,
                    path,
                    label="condition failure bridge evidence",
                )
                for path in (
                    outcome.bridge_evidence.shared_transcript_path,
                    outcome.bridge_evidence.remote_journal_path,
                    outcome.bridge_evidence.relay_prefix_path,
                    outcome.bridge_evidence.relay_transcript_path,
                    outcome.bridge_evidence.runtime_detachment_path,
                    outcome.bridge_evidence.host_terminal_receipt_path,
                    outcome.bridge_evidence.shared_terminal_receipt_path,
                )
            )
        elif partial_bridge_evidence is not None:
            if (
                retained_source is None
                or retained_source.authority != "essential-infrastructure-failure"
                or process_exit_code is None
            ):
                raise AdapterFailure(
                    "interrupted bridge requires an unscored retained essential source"
                )
            attempt_root = partial_raw_root.parent
            expected_partial = ConditionBridgePrefixEvidence(
                session_id=condition_session_id(request.run_id),
                shared_transcript_path=self.root
                / "control-private/condition-bridges"
                / request.run_id
                / "shared-authoritative-transcript.json",
                remote_journal_path=attempt_root
                / "essential-failure/duplex-remote-event-journal.json",
                relay_prefix_path=attempt_root / "essential-failure/duplex-transcript-prefix.json",
            )
            if partial_bridge_evidence != expected_partial:
                raise AdapterFailure("interrupted bridge role or source changed")
            bridge_paths = (
                expected_partial.shared_transcript_path,
                expected_partial.remote_journal_path,
                expected_partial.relay_prefix_path,
            )
            bridge_copy_paths = tuple(
                payload_root / name
                for name in (
                    "shared-authoritative-transcript-prefix.json",
                    "duplex-remote-event-journal.json",
                    "duplex-transcript-prefix.json",
                )
            )
        elif self.authorization_context.execution_mode is EffectExecutionMode.EXTERNAL_LIVE:
            raise AdapterFailure("external-live essential failure lacks its duplex bridge evidence")
        evidence_paths = self._enumerate_essential_envelope(root)
        host = _host_module(self.repository)
        held_failure: tuple[HeldArtifact, ...] = ()
        held_bridge: tuple[HeldArtifact, ...] = ()
        held_source: tuple[HeldArtifact, ...] = ()
        source_binding: dict[str, object] | None = None
        try:
            held_failure = self._hold_artifact_set(
                evidence_paths,
                max_member_bytes=MAX_ESSENTIAL_FAILURE_BYTES,
                max_json_member_bytes=MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES,
                max_files=preservation.essential_failure_file_cap,
                max_total_bytes=preservation.essential_failure_cap_bytes,
            )
            held_bridge = self._hold_artifact_set(
                bridge_paths,
                max_member_bytes=MAX_ESSENTIAL_FAILURE_BYTES,
                max_json_member_bytes=MAX_ESSENTIAL_FAILURE_BYTES,
                max_files=7,
                max_total_bytes=7 * MAX_ESSENTIAL_FAILURE_BYTES,
            )
            if retained_source is not None:
                held_source, source_binding = self._hold_retained_failure_source(
                    request, retained_source, held_bridge
                )
                source_projection = payload_root / "retained-source-binding.json"
                projection = next(
                    (item for item in held_failure if item.path == source_projection), None
                )
                if (
                    projection is None
                    or self._load_canonical_held_json(projection, label="retained source binding")
                    != source_binding
                    or source_binding["process_exit_code"] != process_exit_code
                    or source_binding["completed"] is not completed
                    or source_binding["answer"] != answer
                ):
                    raise AdapterFailure(
                        "essential failure projection differs from retained source"
                    )
            if any(
                self._privacy_findings_for_bytes(
                    host,
                    relative=artifact.relative_path,
                    encoded=artifact.read_bytes(),
                )
                for artifact in held_failure
            ):
                raise AdapterFailure(
                    "essential failure contains private or credential-like material"
                )
            by_path = {artifact.path: artifact for artifact in held_failure}
            if len(by_path) != len(held_failure) or any(
                path not in by_path
                for path in (
                    manifest_path,
                    receipt_path,
                    *role_paths,
                    *bridge_copy_paths,
                )
            ):
                raise AdapterFailure("essential failure roles lack one held artifact identity")
            preexport_artifacts = tuple(
                artifact for artifact in held_failure if root in artifact.path.parents
            )
            if len(preexport_artifacts) != len(evidence_paths):
                raise AdapterFailure("essential failure held file inventory drifted")
            payload_artifacts = tuple(
                artifact
                for artifact in preexport_artifacts
                if payload_root in artifact.path.parents
            )
            payload_files = sorted(
                (
                    {
                        "path": artifact.path.relative_to(root).as_posix(),
                        "bytes": artifact.bytes,
                        "sha256": artifact.sha256,
                    }
                    for artifact in payload_artifacts
                ),
                key=lambda item: cast(str, item["path"]),
            )
            payload_total = sum(cast(int, item["bytes"]) for item in payload_files)
            preexport_total = sum(artifact.bytes for artifact in preexport_artifacts)
            if (
                preexport_total > MAX_ESSENTIAL_FAILURE_BYTES
                or len(preexport_artifacts) > MAX_ESSENTIAL_FAILURE_FILES
            ):
                raise AdapterFailure("essential failure exceeds its independent evidence cap")
            manifest_artifact = by_path[manifest_path]
            receipt_artifact = by_path[receipt_path]
            manifest = self._load_canonical_held_json(
                manifest_artifact,
                label="essential failure manifest",
            )
            receipt = self._load_canonical_held_json(
                receipt_artifact,
                label="essential failure receipt",
            )
            call_ledger = self._load_canonical_held_json(
                by_path[outcome.call_ledger_path],
                label="essential failure call ledger",
            )
            browser_ledger = self._load_canonical_held_json(
                by_path[outcome.browser_ledger_path],
                label="essential failure browser ledger",
            )
            process_document = self._load_canonical_held_json(
                by_path[outcome.process_outcome_path],
                label="essential failure process outcome",
            )
            completion_document = self._load_canonical_held_json(
                by_path[outcome.completion_path],
                label="essential failure completion",
            )
            manifest_sha = manifest_artifact.sha256
            receipt_sha = receipt_artifact.sha256
            bridge_binding: str | None = None
            if outcome.bridge_evidence is not None:
                original_by_path = {artifact.path: artifact for artifact in held_bridge}
                prefix_pairs = (
                    (
                        bridge_copy_paths[0],
                        outcome.bridge_evidence.remote_journal_path,
                    ),
                    (
                        bridge_copy_paths[1],
                        outcome.bridge_evidence.relay_prefix_path,
                    ),
                    (
                        bridge_copy_paths[2],
                        outcome.bridge_evidence.runtime_detachment_path,
                    ),
                )
                if any(
                    by_path[copied].read_bytes() != original_by_path[source].read_bytes()
                    for copied, source in prefix_pairs
                ):
                    raise AdapterFailure(
                        "essential failure bridge prefix differs from its held source"
                    )
                if source_binding is not None:
                    terminal_manifest_sha = cast(str, source_binding["manifest_sha256"])
                    terminal_receipt_sha = cast(str, source_binding["receipt_sha256"])
                elif existing is not None:
                    terminal_manifest_sha = manifest_sha
                    terminal_receipt_sha = receipt_sha
                else:
                    accepted = self._condition_outcomes.get(request.run_id)
                    accepted_artifacts = self._raw_artifacts.get(request.run_id)
                    if accepted is None or accepted_artifacts is None:
                        raise AdapterFailure(
                            "downstream essential failure lost its accepted bridge source"
                        )
                    accepted_by_path = {artifact.path: artifact for artifact in accepted_artifacts}
                    terminal_manifest_sha = accepted_by_path[accepted.raw_manifest_path].sha256
                    terminal_receipt_sha = accepted_by_path[accepted.raw_receipt_path].sha256
                bridge_binding = self._validate_condition_bridge(
                    request=request,
                    observer=observer,
                    raw_root=(
                        retained_source.manifest_path.parent / "essential-failure"
                        if retained_source is not None
                        and retained_source.authority == "essential-infrastructure-failure"
                        else partial_raw_root
                    ),
                    raw_manifest_sha256=terminal_manifest_sha,
                    raw_receipt_sha256=terminal_receipt_sha,
                    evidence=outcome.bridge_evidence,
                    artifacts=held_bridge,
                )
            elif partial_bridge_evidence is not None:
                from giclab.control.remote_bridge import validate_condition_bridge_prefix

                original_by_path = {artifact.path: artifact for artifact in held_bridge}
                if any(
                    by_path[copied].read_bytes() != original_by_path[source].read_bytes()
                    for copied, source in zip(bridge_copy_paths, bridge_paths, strict=True)
                ):
                    raise AdapterFailure("interrupted bridge copy changed observed bytes")
                bridge_binding = validate_condition_bridge_prefix(
                    self.repository,
                    partial_bridge_evidence,
                    expected_binding=ConditionSessionBinding(
                        session_id=condition_session_id(request.run_id),
                        provider_contract_version=request.provider_contract_version,
                        plan_id=request.plan_id,
                        host_run_id=self.contract.host_run_id,
                        condition_run_id=request.run_id,
                        evaluator_run_id=request.evaluator_run_id,
                        frozen_manifest_sha256=request.frozen_manifest_sha256,
                    ),
                    shared_accounting=accounting,
                    reader=lambda path: original_by_path[path].read_bytes(),
                )
        except BaseException:
            for artifact in (*held_failure, *held_bridge, *held_source):
                artifact.close()
            raise
        complete_held: tuple[HeldArtifact, ...] = ()
        retained = False
        try:
            if (
                outcome.run_id != request.run_id
                or outcome.evaluator_run_id != request.evaluator_run_id
                or outcome.failure_class is not failure_class
                or outcome.process_exit_code != process_exit_code
                or outcome.completed is not completed
                or outcome.answer != answer
                or outcome.error != failure_class.value
                or root != expected_root
                or manifest_path != expected_root / "essential-failure-manifest.json"
                or receipt_path != expected_root / "essential-failure-complete.json"
                or len(set(role_paths)) != len(role_paths)
                or outcome.payload_file_count != len(payload_files)
                or outcome.payload_total_bytes != payload_total
                or outcome.essential_file_count != len(preexport_artifacts)
                or outcome.essential_total_bytes != preexport_total
                or preexport_total > preservation.essential_failure_cap_bytes
                or len(preexport_artifacts) > preservation.essential_failure_file_cap
                or outcome.output_bytes != preservation.output_bytes
                or outcome.unknown_call_ids != unknown_call_ids
                or not outcome.writers_closed
                or not outcome.browser_descendants_closed
                or not outcome.credential_cleanup_clean
                or outcome.core_dump_present
                or outcome.structural_privacy_findings
                or not outcome.cleanup_ready
                or outcome.retry_count != 0
                or set(manifest)
                != {
                    "schema_version",
                    "provider_contract_version",
                    "plan_id",
                    "run_id",
                    "evaluator_run_id",
                    "package_commit",
                    "execution_contract_sha256",
                    "frozen_manifest_sha256",
                    "condition_plan_sha256",
                    "command_sha256",
                    "failure_class",
                    "evidence_root",
                    "manifest_scope",
                    "files",
                    "payload_file_count",
                    "payload_total_bytes",
                    "envelope_file_cap",
                    "envelope_total_bytes_cap",
                    "unknown_call_ids",
                    "failure_reconstructable",
                    "private_access_controlled",
                    "publication_blocked_pending_privacy_review",
                    "scientific_result",
                }
                or manifest.get("schema_version") != "2.0.0"
                or manifest.get("provider_contract_version") != self.contract.version
                or manifest.get("plan_id") != self.contract.plan_id
                or manifest.get("run_id") != request.run_id
                or manifest.get("evaluator_run_id") != request.evaluator_run_id
                or manifest.get("package_commit") != request.package_commit
                or manifest.get("execution_contract_sha256") != request.execution_contract_sha256
                or manifest.get("frozen_manifest_sha256") != request.frozen_manifest_sha256
                or manifest.get("condition_plan_sha256") != request.condition_plan_sha256
                or manifest.get("command_sha256") != request.command_sha256
                or manifest.get("failure_class") != failure_class.value
                or manifest.get("evidence_root") != "essential-failure"
                or manifest.get("manifest_scope") != "payload-members-only-noncircular"
                or manifest.get("files") != payload_files
                or manifest.get("payload_file_count") != len(payload_files)
                or manifest.get("payload_total_bytes") != payload_total
                or manifest.get("envelope_file_cap") != preservation.essential_failure_file_cap
                or manifest.get("envelope_total_bytes_cap")
                != preservation.essential_failure_cap_bytes
                or manifest.get("unknown_call_ids") != list(unknown_call_ids)
                or manifest.get("failure_reconstructable") is not True
                or manifest.get("private_access_controlled") is not True
                or manifest.get("publication_blocked_pending_privacy_review") is not True
                or manifest.get("scientific_result") is not False
                or set(receipt)
                != {
                    "schema_version",
                    "run_id",
                    "essential_failure_seal_complete",
                    "attempt_identity_consumed",
                    "infrastructure_invalid",
                    "unscored",
                    "evaluator_permitted",
                    "condition_retry_permitted",
                    "manifest_sha256",
                    "payload_file_count",
                    "payload_total_bytes",
                    "writers_closed",
                    "browser_descendants_closed",
                    "credential_cleanup_clean",
                    "core_dump_present",
                    "structural_privacy_findings",
                    "cleanup_ready",
                }
                or receipt.get("schema_version") != "2.0.0"
                or receipt.get("run_id") != request.run_id
                or receipt.get("essential_failure_seal_complete") is not True
                or receipt.get("attempt_identity_consumed") is not True
                or receipt.get("infrastructure_invalid") is not True
                or receipt.get("unscored") is not True
                or receipt.get("evaluator_permitted") is not False
                or receipt.get("condition_retry_permitted") is not False
                or receipt.get("manifest_sha256") != manifest_sha
                or receipt.get("payload_file_count") != len(payload_files)
                or receipt.get("payload_total_bytes") != payload_total
                or receipt.get("writers_closed") is not True
                or receipt.get("browser_descendants_closed") is not True
                or receipt.get("credential_cleanup_clean") is not True
                or receipt.get("core_dump_present") is not False
                or receipt.get("structural_privacy_findings") != []
                or receipt.get("cleanup_ready") is not True
                or set(call_ledger)
                != {"run_id", "call_ids", "logical_call_ids", "unknown_call_ids", "accounting"}
                or call_ledger.get("run_id") != request.run_id
                or call_ledger.get("accounting") != accounting
                or call_ledger.get("call_ids") != list(observer.call_order)
                or call_ledger.get("logical_call_ids") != list(observer.logical_call_order)
                or call_ledger.get("unknown_call_ids") != list(unknown_call_ids)
                or set(browser_ledger) != {"run_id", "actions"}
                or browser_ledger.get("run_id") != request.run_id
                or browser_ledger.get("actions")
                != [
                    {"action_id": action_id, "terminal_state": terminal_state}
                    for action_id, terminal_state in preservation.browser_actions
                ]
                or set(process_document)
                != {
                    "run_id",
                    "failure_class",
                    "exit_code",
                    "retry_count",
                    "command_argv_count",
                    "command_argv_sha256",
                    "command_sha256",
                    "condition_plan_path",
                    "condition_plan_sha256",
                    "writers_closed",
                    "browser_descendants_closed",
                }
                or process_document.get("run_id") != request.run_id
                or process_document.get("failure_class") != failure_class.value
                or process_document.get("exit_code") != process_exit_code
                or process_document.get("retry_count") != 0
                or process_document.get("command_argv_count") != len(request.command_argv)
                or process_document.get("command_argv_sha256") != request.command_sha256
                or process_document.get("command_sha256") != request.command_sha256
                or process_document.get("condition_plan_path") != request.condition_plan_path
                or process_document.get("condition_plan_sha256") != request.condition_plan_sha256
                or process_document.get("writers_closed") is not True
                or process_document.get("browser_descendants_closed") is not True
                or set(completion_document)
                != {"run_id", "completed", "answer", "error", "evaluator_eligible"}
                or completion_document.get("run_id") != request.run_id
                or completion_document.get("completed") is not completed
                or completion_document.get("answer") != answer
                or completion_document.get("error") != failure_class.value
                or completion_document.get("evaluator_eligible") is not False
            ):
                raise AdapterFailure("essential failure outcome is not reconstructable")
            for label, document in (
                ("essential failure manifest", manifest),
                ("essential failure receipt", receipt),
                ("essential failure call ledger", call_ledger),
                ("essential failure browser ledger", browser_ledger),
                ("essential failure process outcome", process_document),
                ("essential failure completion", completion_document),
            ):
                self._reject_private_failure_structure(document, label=label)
            self._validate_failure_schema(
                "schemas/t09-essential-failure-manifest.schema.json",
                manifest,
                label="essential failure manifest",
            )
            self._validate_failure_schema(
                "schemas/t09-essential-failure-complete.schema.json",
                receipt,
                label="essential failure completion receipt",
            )
            with self._pilot_control_writer(request.run_id, failure=True) as (admit, observed):
                pilot.mark_essential_failure_sealed(
                    self._pilot_state,
                    execution_contract_sha256=execution.sha256,
                    run_id=request.run_id,
                    manifest_sha256=manifest_sha,
                    receipt_sha256=receipt_sha,
                    before_write=admit,
                    after_output_write=observed,
                )
            export_identity = _identity(
                {
                    "run_id": request.run_id,
                    "essential_manifest_sha256": manifest_sha,
                    "essential_receipt_sha256": receipt_sha,
                    "essential_file_count": len(preexport_artifacts),
                    "essential_total_bytes": preexport_total,
                }
            )
            export_request = ConditionFailureExportRequest(
                run_id=request.run_id,
                essential_root=root,
                essential_manifest_path=manifest_path,
                essential_receipt_path=receipt_path,
                essential_manifest_sha256=manifest_sha,
                essential_receipt_sha256=receipt_sha,
                essential_file_count=len(preexport_artifacts),
                essential_total_bytes=preexport_total,
                export_identity=export_identity,
                output_observer=observer,
            )
            resumed = False
            try:
                self._revalidate_artifacts((*held_failure, *held_source))
                export = self.low_level_effects.export_condition_failure(export_request)
            except ConditionFailureExportInterrupted:
                resumed = True
                self._revalidate_artifacts((*held_failure, *held_source))
                export = self.low_level_effects.export_condition_failure(export_request)
            self._revalidate_artifacts((*held_failure, *held_source))

            acknowledgement_path = _safe_existing_file(
                root,
                export.acknowledgement_path,
                label="essential failure export acknowledgement",
            )
            if acknowledgement_path != root / "export-acknowledgement.json":
                raise AdapterFailure("essential failure acknowledgement path drifted")
            complete_paths = self._enumerate_essential_envelope(root)
            complete_held = self._hold_artifact_set(
                complete_paths,
                max_member_bytes=MAX_ESSENTIAL_FAILURE_BYTES,
                max_json_member_bytes=MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES,
                max_files=preservation.essential_failure_file_cap,
                max_total_bytes=preservation.essential_failure_cap_bytes,
            )
            complete_total = sum(artifact.bytes for artifact in complete_held)
            if len(complete_held) != len(complete_paths):
                raise AdapterFailure("complete essential failure held inventory drifted")
            complete_by_path = {artifact.path: artifact for artifact in complete_held}
            acknowledgement_artifact = complete_by_path.get(acknowledgement_path)
            if acknowledgement_artifact is None:
                raise AdapterFailure("essential failure acknowledgement identity is not held")
            acknowledgement = self._load_canonical_held_json(
                acknowledgement_artifact,
                label="essential failure export acknowledgement",
            )
            expected_acknowledgement_keys = {
                "schema_version",
                "run_id",
                "export_identity",
                "essential_manifest_sha256",
                "essential_receipt_sha256",
                "essential_file_count",
                "essential_total_bytes",
                "destination_identity",
                "export_complete",
                "resumed",
                "envelope_padding",
            }
            padding = acknowledgement.get("envelope_padding")
            expected_complete_paths = set(evidence_paths) | {acknowledgement_path}
            if padding is not None:
                if not isinstance(padding, dict) or set(padding) != {"path", "bytes", "sha256"}:
                    raise AdapterFailure("essential failure padding descriptor is malformed")
                padding_path_value = padding.get("path")
                if (
                    not isinstance(padding_path_value, str)
                    or Path(padding_path_value).name != padding_path_value
                ):
                    raise AdapterFailure("essential failure padding path is not one local member")
                padding_path = _safe_existing_file(
                    root,
                    root / padding_path_value,
                    label="essential failure envelope padding",
                )
                padding_artifact = complete_by_path.get(padding_path)
                if (
                    padding_artifact is None
                    or padding.get("bytes") != padding_artifact.bytes
                    or padding.get("sha256") != padding_artifact.sha256
                ):
                    raise AdapterFailure("essential failure padding identity drifted")
                expected_complete_paths.add(padding_path)
            if (
                set(complete_paths) != expected_complete_paths
                or set(acknowledgement) != expected_acknowledgement_keys
                or acknowledgement.get("schema_version") != "2.0.0"
                or acknowledgement.get("run_id") != request.run_id
                or acknowledgement.get("export_identity") != export_identity
                or acknowledgement.get("essential_manifest_sha256") != manifest_sha
                or acknowledgement.get("essential_receipt_sha256") != receipt_sha
                or acknowledgement.get("essential_file_count") != len(complete_held)
                or acknowledgement.get("essential_total_bytes") != complete_total
                or acknowledgement.get("destination_identity") != export.destination_identity
                or acknowledgement.get("export_complete") is not True
                or acknowledgement.get("resumed") is not resumed
                or export.run_id != request.run_id
                or export.export_identity != export_identity
                or _HEX64.fullmatch(export.destination_identity) is None
                or export.essential_manifest_sha256 != manifest_sha
                or export.essential_receipt_sha256 != receipt_sha
                or export.essential_file_count != len(complete_held)
                or export.essential_total_bytes != complete_total
                or export.acknowledgement_bytes != acknowledgement_artifact.bytes
                or not export.export_complete
                or export.resumed is not resumed
                or export.receipt_sha256 != acknowledgement_artifact.sha256
                or complete_by_path[manifest_path].sha256 != manifest_sha
                or complete_by_path[receipt_path].sha256 != receipt_sha
            ):
                raise AdapterFailure("essential failure export acknowledgement drifted")
            self._reject_private_failure_structure(
                acknowledgement,
                label="essential failure export acknowledgement",
            )
            self._validate_failure_schema(
                "schemas/t09-essential-failure-export-acknowledgement.schema.json",
                acknowledgement,
                label="essential failure export acknowledgement",
            )
            if any(
                self._privacy_findings_for_bytes(
                    host,
                    relative=artifact.relative_path,
                    encoded=artifact.read_bytes(),
                )
                for artifact in complete_held
            ):
                raise AdapterFailure("complete essential envelope failed privacy validation")
            self._revalidate_artifacts(held_failure)
            self._revalidate_artifacts(complete_held)

            complete_outcome = replace(
                outcome,
                essential_file_count=len(complete_held),
                essential_total_bytes=complete_total,
            )
            for artifact in held_failure:
                artifact.close()
            held_failure = ()
            self._condition_failures[request.run_id] = complete_outcome
            self._essential_failure_exports[request.run_id] = export
            self._essential_failure_artifacts[request.run_id] = complete_held
            self._essential_failure_artifact_bindings[request.run_id] = self._artifact_binding(
                complete_held
            )
            if bridge_binding is not None:
                self._condition_bridge_bindings[request.run_id] = bridge_binding
                self._condition_bridge_artifacts[request.run_id] = held_bridge
                held_bridge = ()
            if held_source:
                previous_source = self._raw_artifacts.get(request.run_id, ())
                self._raw_artifacts[request.run_id] = held_source
                self._raw_artifact_bindings[request.run_id] = self._artifact_binding(held_source)
                held_source = ()
                # A downstream failure re-holds already accepted raw evidence.
                # Release the displaced holds after the replacement is complete.
                for artifact in previous_source:
                    artifact.close()
            retained = True
            self._primitive("mark_essential_failure_sealed")
            self._primitive("validate_essential_failure_bundle")
            self._primitive("export_essential_failure_bundle")
            return EssentialFailureRecord(
                run_id=request.run_id,
                stopping_phase=stopping_phase,
                failure_class=failure_class.value,
                manifest_sha256=manifest_sha,
                receipt_sha256=receipt_sha,
                export_receipt_sha256=export.receipt_sha256,
                essential_file_count=len(complete_held),
                essential_total_bytes=complete_total,
                evidence_binding_sha256=_identity(
                    {
                        "manifest_sha256": manifest_sha,
                        "receipt_sha256": receipt_sha,
                        "export_receipt_sha256": export.receipt_sha256,
                        "essential_file_count": len(complete_held),
                        "essential_total_bytes": complete_total,
                        "held_artifact_binding_sha256": (
                            self._essential_failure_artifact_bindings[request.run_id]
                        ),
                        "accounting": accounting,
                        "condition_bridge_evidence_binding_sha256": bridge_binding,
                    }
                ),
            )
        finally:
            if not retained:
                for artifact in (*held_failure, *held_bridge, *held_source, *complete_held):
                    artifact.close()

    def _seal_accepted_condition_failure(
        self,
        *,
        run_id: str,
        stopping_phase: str,
        failure_class: ConditionFailureClass,
    ) -> EssentialFailureRecord:
        """Turn a downstream post-entry failure into one immutable stop record."""

        request = self._condition_requests.get(run_id)
        observer = self._condition_observers.get(run_id)
        if request is None or observer is None:
            raise AdapterFailure("post-entry failure lacks its exact condition transaction")
        completion = observer.completion_state
        outcome = self._condition_outcomes.get(run_id)
        return self._validate_and_seal_condition_failure(
            request=request,
            observer=observer,
            stopping_phase=stopping_phase,
            failure_class=failure_class,
            process_exit_code=observer.exit_code,
            completed=completion[0] if completion is not None else False,
            answer=completion[1] if completion is not None else None,
            retained_source=outcome.retained_source if outcome is not None else None,
            bridge_evidence=outcome.bridge_evidence if outcome is not None else None,
        )

    def _raise_downstream_consumed_failure(
        self,
        *,
        operation: str,
        run_id: str,
        stopping_phase: str,
        failure_class: ConditionFailureClass,
        message: str,
        cause: BaseException,
    ) -> NoReturn:
        self._record(operation, run_id, "failed")
        try:
            record = self._seal_accepted_condition_failure(
                run_id=run_id,
                stopping_phase=stopping_phase,
                failure_class=failure_class,
            )
        except BaseException as seal_exc:
            self._record(operation, run_id, "essential-failure-unsealed")
            raise AdapterFailure(f"{message} could not be sealed and exported") from seal_exc
        self._record(operation, run_id, "essential-failure-sealed")
        raise ConsumedConditionFailure(
            f"{message} stopped with reconstructable essential evidence",
            record=record,
        ) from cause

    def run(self, run_id: str) -> str:
        operation = "condition.run"
        self._begin(operation, run_id)
        execution = self._require_execution()
        assert self._runtime_budget is not None
        assert self._freeze is not None
        if self._campaign_deadline_monotonic is None:
            raise AdapterFailure("condition runtime lacks its campaign deadline")
        manifest = self._manifest_for_run(run_id)
        attempt = execution.attempt(run_id)
        argv = manifest.get("argv")
        argv_sha = manifest.get("argv_sha256")
        upstream_argv = (
            argv[argv.index("--") + 1 :] if isinstance(argv, list) and "--" in argv else None
        )
        if (
            not isinstance(argv, list)
            or not all(isinstance(item, str) for item in argv)
            or not isinstance(upstream_argv, list)
            or tuple(upstream_argv) != attempt.upstream_argv
            or argv_sha != pilot.command_argv_sha256(argv)
            or manifest.get("condition_plan_path") != attempt.condition_plan_path
            or manifest.get("condition_plan_sha256") != attempt.condition_plan_sha256
        ):
            raise AdapterFailure("condition command bytes drifted before effect invocation")
        caps = self._runtime_budget.condition_caps.get(run_id)
        if caps is None:
            raise AdapterFailure("condition-owned cap is absent")
        request = ConditionExecutionRequest(
            run_id=run_id,
            evaluator_run_id=self.contract.evaluator_run_ids[self.contract.run_ids.index(run_id)],
            command_argv=tuple(cast(list[str], argv)),
            command_sha256=argv_sha,
            condition_plan_path=attempt.condition_plan_path,
            condition_plan_sha256=attempt.condition_plan_sha256,
            raw_output_root=attempt.raw_output_root,
            finalized_output_root=attempt.finalized_output_root,
            model_revision=self._runtime_budget.model_revision,
            service_tier=self._runtime_budget.service_tier,
            zero_retry=self._runtime_budget.zero_retry,
            caps=caps,
            execution_contract_sha256=execution.sha256,
            frozen_manifest_sha256=self._freeze.manifest_sha256,
            provider_contract_version=self.contract.version,
            plan_id=self.contract.plan_id,
            package_commit=self._source_identity()[0],
            transaction_root=self.root,
            condition_started_wall_time=self._condition_started_wall[run_id],
            condition_started_monotonic=self._condition_started_monotonic[run_id],
            campaign_deadline_monotonic=self._campaign_deadline_monotonic,
            first_pair_checkpoint=(
                _canonical_bytes(
                    {
                        "schema_version": "1.0.0",
                        "role": "shared-first-pair-checkpoint",
                        "plan_id": self.contract.plan_id,
                        "provider_contract_version": self.contract.version,
                        "execution_contract_sha256": execution.sha256,
                        "frozen_manifest_sha256": self._freeze.manifest_sha256,
                        "package_commit": self._source_identity()[0],
                        "decision": self._checkpoint_document,
                        "task_a": {
                            prior: {
                                "raw_manifest_sha256": self._finalizations[
                                    prior
                                ].consumed_raw_manifest_sha256,
                                "raw_receipt_sha256": self._finalizations[
                                    prior
                                ].consumed_raw_receipt_sha256,
                                "semantic_projection_sha256": self._finalizations[
                                    prior
                                ].semantic_projection_sha256,
                            }
                            for prior in self.contract.run_ids[:2]
                        },
                    }
                )
                if self.contract.run_ids.index(run_id) >= 2
                else None
            ),
        )
        observer = self._condition_accountant(run_id)
        started = self.clock.monotonic()
        if started < request.condition_started_monotonic:
            raise AdapterFailure("condition monotonic start moved backward")
        self._condition_requests[run_id] = request
        self._condition_observers[run_id] = observer
        failure_preservation_started = False
        returned_source = None
        returned_bridge = None
        returned_partial_bridge = None
        try:
            typed_outcome = self.low_level_effects.execute_condition(
                request,
                observer=observer,
            )
            # Retain the supplied source references before validating the shared
            # projection. A later projection rejection must still preserve the
            # exact raw source; the preservation consumer independently validates
            # these references and cannot acquire authority from this assignment.
            returned_source = typed_outcome.retained_source
            returned_bridge = typed_outcome.bridge_evidence
            returned_partial_bridge = typed_outcome.partial_bridge_evidence
            if isinstance(typed_outcome, ConditionInfrastructureFailureOutcome):
                failure_preservation_started = True
                record = self._validate_and_seal_condition_failure(
                    request=request,
                    observer=observer,
                    failure_class=typed_outcome.failure_class,
                    process_exit_code=typed_outcome.process_exit_code,
                    completed=typed_outcome.completed,
                    answer=typed_outcome.answer,
                    existing=typed_outcome,
                    retained_source=typed_outcome.retained_source,
                    bridge_evidence=typed_outcome.bridge_evidence,
                    partial_bridge_evidence=typed_outcome.partial_bridge_evidence,
                )
                raise ConsumedConditionFailure(
                    "condition returned an infrastructure-invalid outcome",
                    record=record,
                )
            outcome = typed_outcome
            essential_source = (
                outcome.retained_source is not None
                and outcome.retained_source.authority == "essential-infrastructure-failure"
            )
            if outcome.exit_code != 0 or essential_source:
                failure_preservation_started = True
                record = self._validate_and_seal_condition_failure(
                    request=request,
                    observer=observer,
                    failure_class=(
                        ConditionFailureClass.PROCESS_EXIT_NONZERO
                        if outcome.exit_code != 0
                        else ConditionFailureClass.OUTCOME_VALIDATION
                    ),
                    retained_source=outcome.retained_source,
                    bridge_evidence=outcome.bridge_evidence,
                    partial_bridge_evidence=outcome.partial_bridge_evidence,
                    process_exit_code=outcome.exit_code,
                    completed=outcome.completed,
                    answer=outcome.answer,
                )
                raise ConsumedConditionFailure(
                    "condition process or retained essential source is infrastructure-invalid",
                    record=record,
                )
            completed = self.clock.monotonic()
            if (
                completed > self._campaign_deadline_monotonic
                or completed - started > caps.max_wall_seconds
            ):
                raise ProviderBudgetExceeded("condition wall budget exceeded")
            expected_raw = _safe_directory(
                self.root,
                self.root / attempt.raw_output_root,
                label="bound condition raw root",
            )
            raw_root = _safe_directory(
                self.root,
                outcome.raw_root,
                label="condition raw root",
            )
            manifest_path = _safe_existing_file(
                self.root,
                outcome.raw_manifest_path,
                label="condition raw manifest",
            )
            receipt_path = _safe_existing_file(
                self.root,
                outcome.raw_receipt_path,
                label="condition raw receipt",
            )
            evidence_root = raw_root
            projection_paths: tuple[Path, ...] = ()
            if outcome.control_projection_path is not None:
                source = outcome.retained_source
                if (
                    source is None
                    or outcome.bridge_evidence is None
                    or source.authority != "immutable-raw-attempt"
                    or source.manifest_path != manifest_path
                    or source.receipt_path != receipt_path
                    or outcome.control_projection_path
                    != raw_root.parent / "shared-control-projection/manifest.json"
                ):
                    raise AdapterFailure("derived control evidence lacks retained source binding")
                evidence_root = _safe_directory(
                    self.root,
                    outcome.control_projection_path.parent,
                    label="derived condition control root",
                )
                _host_module(self.repository).retained_control_projection(
                    attempt_root=raw_root.parent,
                    run_id=run_id,
                    package_commit=request.package_commit,
                    exit_code=outcome.exit_code,
                    process_expectations=retained_process_expectations(request),
                    publish=False,
                )
                projection_paths = tuple(
                    evidence_root / name
                    for name in (
                        "manifest.json",
                        "call-ledger.json",
                        "browser-ledger.json",
                        "completion.json",
                        "process-outcome.json",
                    )
                )
            call_ledger = _safe_existing_file(
                evidence_root,
                outcome.call_ledger_path,
                label="condition call ledger",
            )
            browser_ledger = _safe_existing_file(
                evidence_root,
                outcome.browser_ledger_path,
                label="condition browser ledger",
            )
            completion_path = _safe_existing_file(
                evidence_root,
                outcome.completion_path,
                label="condition completion evidence",
            )
            process_outcome_path = _safe_existing_file(
                evidence_root,
                outcome.process_outcome_path,
                label="condition process outcome",
            )
            if (
                len(
                    {
                        call_ledger,
                        browser_ledger,
                        completion_path,
                        process_outcome_path,
                    }
                )
                != 4
            ):
                raise AdapterFailure("condition evidence roles reuse one file")
            self._validate_condition_ledgers(
                run_id=run_id,
                observer=observer,
                call_ledger=call_ledger,
                browser_ledger=browser_ledger,
            )
            completion = observer.completion_state
            completion_document = load_json(completion_path)
            process_document = load_json(process_outcome_path)
            manifest_sha = _file_sha256(manifest_path)
            receipt_sha = _file_sha256(receipt_path)
            if (
                outcome.run_id != run_id
                or outcome.evaluator_run_id != request.evaluator_run_id
                or raw_root != expected_raw
                or manifest_path.parent != raw_root.parent
                or receipt_path.parent != raw_root.parent
                or call_ledger.parent != evidence_root
                or browser_ledger.parent != evidence_root
                or outcome.retry_count != 0
                or observer.exit_code != outcome.exit_code
                or completion != (outcome.completed, outcome.answer, outcome.error)
                or observer.raw_publication != (manifest_sha, receipt_sha)
                or observer.output_total_bytes is None
                or outcome.output_bytes != observer.output_total_bytes
                or self._seen_call_ids.intersection(observer.call_ids)
                or completion_document.get("run_id") != run_id
                or completion_document.get("completed") is not outcome.completed
                or completion_document.get("answer") != outcome.answer
                or completion_document.get("error") != outcome.error
                or process_document.get("run_id") != run_id
                or process_document.get("exit_code") != outcome.exit_code
                or process_document.get("retry_count") != outcome.retry_count
                or process_document.get("command_argv") != list(request.command_argv)
                or process_document.get("command_sha256") != request.command_sha256
                or process_document.get("condition_plan_path") != request.condition_plan_path
                or process_document.get("condition_plan_sha256") != request.condition_plan_sha256
                or process_document.get("model_revision") != request.model_revision
                or process_document.get("service_tier") != request.service_tier
                or process_document.get("caps") != _caps_document(request.caps)
            ):
                raise AdapterFailure("condition process outcome contradicts typed events")
            # A normally exiting runner can end without completing the task.
            # Keep that scientific outcome separate from process validity; the
            # retained finalizer/evaluator apply the unchanged no-answer policy.
            host = _host_module(self.repository)
            raw_manifest, raw_receipt = host.validate_raw_attempt_seal(
                attempt_root=raw_root.parent,
                raw_root=raw_root,
                run_id=run_id,
                package_commit=request.package_commit,
            )
            if (
                raw_manifest.get("total_bytes") != outcome.raw_total_bytes
                or raw_receipt.get("raw_file_count") != outcome.raw_file_count
                or raw_receipt.get("raw_total_bytes") != outcome.raw_total_bytes
                or raw_receipt.get("condition_retry_permitted") is not False
            ):
                raise AdapterFailure("condition raw publication is incomplete")
            bridge_paths: tuple[Path, ...] = ()
            if outcome.bridge_evidence is not None:
                bridge_paths = tuple(
                    _safe_existing_file(
                        self.root,
                        path,
                        label="condition bridge evidence",
                    )
                    for path in (
                        outcome.bridge_evidence.shared_transcript_path,
                        outcome.bridge_evidence.remote_journal_path,
                        outcome.bridge_evidence.relay_prefix_path,
                        outcome.bridge_evidence.relay_transcript_path,
                        outcome.bridge_evidence.runtime_detachment_path,
                        outcome.bridge_evidence.host_terminal_receipt_path,
                        outcome.bridge_evidence.shared_terminal_receipt_path,
                    )
                )
            bridge_set = set(bridge_paths)
            raw_paths = (
                manifest_path,
                receipt_path,
                *projection_paths,
                *tuple(
                    path
                    for path in raw_root.rglob("*")
                    if not path.is_dir() and path not in bridge_set
                ),
            )
            held_bridge: tuple[HeldArtifact, ...] = ()
            held_raw: tuple[HeldArtifact, ...] = ()
            retained_raw = False
            try:
                held_bridge = self._hold_artifact_set(
                    bridge_paths,
                    max_member_bytes=67_108_864,
                    max_json_member_bytes=67_108_864,
                    max_files=7,
                    max_total_bytes=7 * 67_108_864,
                )
                held_raw = self._hold_artifact_set(raw_paths)
                complete_held = tuple(
                    sorted(
                        (*held_raw, *held_bridge),
                        key=lambda artifact: artifact.relative_path,
                    )
                )
                if len({(item.device, item.inode) for item in complete_held}) != len(complete_held):
                    raise AdapterFailure("condition evidence roles share one file identity")
                bridge_binding = self._validate_condition_bridge(
                    request=request,
                    observer=observer,
                    raw_root=raw_root,
                    raw_manifest_sha256=manifest_sha,
                    raw_receipt_sha256=receipt_sha,
                    evidence=outcome.bridge_evidence,
                    artifacts=complete_held,
                )
                self._raw_artifacts[run_id] = complete_held
                self._raw_artifact_bindings[run_id] = self._artifact_binding(complete_held)
                if bridge_binding is not None:
                    self._condition_bridge_bindings[run_id] = bridge_binding
                retained_raw = True
            finally:
                if not retained_raw:
                    for artifact in (*held_raw, *held_bridge):
                        artifact.close()
        except ConsumedConditionFailure:
            self._record_boundary_state(run_id, observer)
            self._primitive("ProviderBudgetBoundary.invoke")
            self._record(operation, run_id, "essential-failure-sealed")
            raise
        except BaseException as exc:
            if failure_preservation_started:
                self._record_boundary_state(run_id, observer)
                self._primitive("ProviderBudgetBoundary.invoke")
                self._record(operation, run_id, "essential-failure-unsealed")
                raise AdapterFailure(
                    "consumed condition failure could not be sealed and exported"
                ) from exc
            failure_class = self._condition_failure_class(exc)
            try:
                record = self._validate_and_seal_condition_failure(
                    request=request,
                    observer=observer,
                    failure_class=failure_class,
                    process_exit_code=observer.exit_code,
                    completed=(
                        observer.completion_state[0]
                        if observer.completion_state is not None
                        else False
                    ),
                    answer=(
                        observer.completion_state[1]
                        if observer.completion_state is not None
                        else None
                    ),
                    retained_source=returned_source,
                    bridge_evidence=returned_bridge,
                    partial_bridge_evidence=returned_partial_bridge,
                )
            except BaseException as seal_exc:
                self._record_boundary_state(run_id, observer)
                self._primitive("ProviderBudgetBoundary.invoke")
                self._record(operation, run_id, "essential-failure-unsealed")
                raise AdapterFailure(
                    "consumed condition failure could not be sealed and exported"
                ) from seal_exc
            self._record_boundary_state(run_id, observer)
            self._primitive("ProviderBudgetBoundary.invoke")
            self._record(operation, run_id, "essential-failure-sealed")
            raise ConsumedConditionFailure(
                "consumed condition stopped with reconstructable essential evidence",
                record=record,
            ) from exc
        self._condition_outcomes[run_id] = outcome
        self._record_boundary_state(run_id, observer)
        self._primitive("ProviderBudgetBoundary.invoke")
        self._primitive("ProviderBudgetBoundary.record_browser_action")
        self._primitive("ProviderBudgetBoundary.record_output_bytes")
        self._primitive("execute_typed_condition_session")
        if run_id in self._condition_bridge_bindings:
            self._primitive("validate_condition_bridge_evidence")
        self._record(operation, run_id, "passed")
        return _identity(
            {
                "run_id": run_id,
                "raw_manifest_sha256": next(
                    artifact.sha256
                    for artifact in self._raw_artifacts[run_id]
                    if artifact.path == outcome.raw_manifest_path
                ),
                "raw_receipt_sha256": next(
                    artifact.sha256
                    for artifact in self._raw_artifacts[run_id]
                    if artifact.path == outcome.raw_receipt_path
                ),
                "raw_artifact_binding_sha256": self._raw_artifact_bindings[run_id],
                "answer_sha256": (
                    hashlib.sha256(outcome.answer.encode()).hexdigest()
                    if outcome.answer is not None
                    else None
                ),
            }
        )

    def export_raw(self, run_id: str) -> str:
        operation = "condition.export_raw"
        self._begin(operation, run_id)
        execution = self._require_execution()
        try:
            outcome = self._condition_outcomes.get(run_id)
            raw_artifacts = self._raw_artifacts.get(run_id)
            if outcome is None or raw_artifacts is None:
                raise AdapterFailure("raw export lacks its accepted held condition outcome")
            self._revalidate_artifacts(raw_artifacts)
            artifact_by_path = {artifact.path: artifact for artifact in raw_artifacts}
            manifest_artifact = artifact_by_path.get(outcome.raw_manifest_path)
            receipt_artifact = artifact_by_path.get(outcome.raw_receipt_path)
            if manifest_artifact is None or receipt_artifact is None:
                raise AdapterFailure("raw export manifest or receipt is not held")
            manifest_sha = manifest_artifact.sha256
            receipt_sha = receipt_artifact.sha256
        except BaseException as exc:
            self._raise_downstream_consumed_failure(
                operation=operation,
                run_id=run_id,
                stopping_phase="raw-export",
                failure_class=ConditionFailureClass.RAW_EXPORT,
                message="raw export",
                cause=exc,
            )
        try:
            host = _host_module(self.repository)
            manifest, receipt = host.validate_raw_attempt_seal(
                attempt_root=outcome.raw_root.parent,
                raw_root=outcome.raw_root,
                run_id=run_id,
                package_commit=self._source_identity()[0],
            )
            files = manifest.get("files")
            if (
                not isinstance(files, list)
                or len(files) != outcome.raw_file_count
                or manifest.get("total_bytes") != outcome.raw_total_bytes
                or receipt.get("raw_file_count") != outcome.raw_file_count
                or receipt.get("raw_total_bytes") != outcome.raw_total_bytes
                or manifest.get("condition_plan_sha256")
                != execution.attempt(run_id).condition_plan_sha256
                or manifest.get("condition_argv_sha256")
                != self._manifest_for_run(run_id).get("argv_sha256")
                or receipt.get("condition_retry_permitted") is not False
            ):
                raise AdapterFailure("raw evidence manifest or accounting identity drifted")
            exported = self.public_root / (
                f"raw-export-{self.contract.run_ids.index(run_id):02d}.json"
            )
            export_document = {
                "run_id": run_id,
                "raw_manifest_sha256": manifest_sha,
                "raw_receipt_sha256": receipt_sha,
                "raw_file_count": outcome.raw_file_count,
                "raw_total_bytes": outcome.raw_total_bytes,
            }
            with self._pilot_control_writer(run_id, extra_paths=(exported,)) as (admit, observed):
                encoded_export = _canonical_bytes(export_document)
                host = _host_module(self.repository)
                token = host._HOST_OUTPUT_ADMISSION.set(admit)
                try:
                    host.write_bytes_exclusive(
                        exported, encoded_export, after_output_write=observed
                    )
                finally:
                    host._HOST_OUTPUT_ADMISSION.reset(token)
                if load_json(exported) != export_document:
                    raise AdapterFailure("off-host raw acknowledgement changed bytes")
                pilot.mark_raw_attempt_complete(
                    self._pilot_state,
                    execution_contract_sha256=execution.sha256,
                    run_id=run_id,
                    raw_manifest_sha256=manifest_sha,
                    raw_receipt_sha256=receipt_sha,
                    before_write=admit,
                    after_output_write=observed,
                )
            self._raw_completed_run_ids.append(run_id)
            self._revalidate_artifacts(raw_artifacts)
        except BaseException as exc:
            self._raise_downstream_consumed_failure(
                operation=operation,
                run_id=run_id,
                stopping_phase="raw-export",
                failure_class=ConditionFailureClass.RAW_EXPORT,
                message="raw export",
                cause=exc,
            )
        acknowledgement = _file_sha256(exported)
        self._raw_export_acknowledgements[run_id] = acknowledgement
        self._primitive("validate_raw_attempt_seal")
        self._primitive("mark_raw_attempt_complete")
        self._primitive("exact_raw_export_acknowledgement")
        self._record(operation, run_id, "passed")
        return receipt_sha

    @staticmethod
    def _finalizer_outcome_identity(outcome: FinalizerExecutionOutcome) -> str:
        return _identity(
            {
                "run_id": outcome.run_id,
                "completion_receipt_sha256": outcome.completion_receipt_sha256,
                "semantic_projection_sha256": outcome.semantic_projection_sha256,
                "session_sha256s": [_file_sha256(path) for path in outcome.session_paths],
                "consumed_raw_manifest_sha256": outcome.consumed_raw_manifest_sha256,
                "consumed_raw_receipt_sha256": outcome.consumed_raw_receipt_sha256,
                "consumed_raw_artifact_binding_sha256": (
                    outcome.consumed_raw_artifact_binding_sha256
                ),
                "infrastructure_valid": outcome.infrastructure_valid,
            }
        )

    def finalize(self, run_id: str) -> str:
        operation = "condition.finalize"
        self._begin(operation, run_id)
        execution = self._require_execution()
        try:
            raw = self._condition_outcomes.get(run_id)
            qualification = self._qualification
            raw_artifacts = self._raw_artifacts.get(run_id)
            raw_binding = self._raw_artifact_bindings.get(run_id)
            if raw is None or qualification is None or raw_artifacts is None or raw_binding is None:
                raise AdapterFailure(
                    "finalizer lacks raw, held evidence, or qualification authority"
                )
            self._revalidate_artifacts(raw_artifacts)
            artifact_by_path = {
                self.root / artifact.relative_path: artifact for artifact in raw_artifacts
            }
            manifest_artifact = artifact_by_path.get(raw.raw_manifest_path)
            receipt_artifact = artifact_by_path.get(raw.raw_receipt_path)
            answer_artifact = artifact_by_path.get(raw.completion_path)
            process_artifact = artifact_by_path.get(raw.process_outcome_path)
            if any(
                artifact is None
                for artifact in (
                    manifest_artifact,
                    receipt_artifact,
                    answer_artifact,
                    process_artifact,
                )
            ):
                raise AdapterFailure("finalizer input roles are absent from held raw evidence")
            assert manifest_artifact is not None
            assert receipt_artifact is not None
            assert answer_artifact is not None
            assert process_artifact is not None
            attempt = execution.attempt(run_id)
            manifest_sha = manifest_artifact.sha256
            receipt_sha = receipt_artifact.sha256
            expected_finalized = self.root / attempt.finalized_output_root
            host = _host_module(self.repository)
            request = FinalizerExecutionRequest(
                run_id=run_id,
                evaluator_run_id=self.contract.evaluator_run_ids[
                    self.contract.run_ids.index(run_id)
                ],
                execution_mode="qualified-local",
                runtime_qualification_id=qualification.local_finalizer_qualification_id,
                runtime_qualification_sha256=(qualification.local_finalizer_qualification_sha256),
                raw_root=raw.raw_root,
                raw_manifest_path=raw.raw_manifest_path,
                raw_receipt_path=raw.raw_receipt_path,
                raw_manifest_sha256=manifest_sha,
                raw_receipt_sha256=receipt_sha,
                raw_completion_path=raw.completion_path,
                raw_completion_sha256=answer_artifact.sha256,
                raw_artifacts=raw_artifacts,
                raw_artifact_binding_sha256=raw_binding,
                answer_artifact=answer_artifact,
                process_outcome_path=raw.process_outcome_path,
                process_outcome_sha256=process_artifact.sha256,
                raw_output_root=attempt.raw_output_root,
                finalized_root=expected_finalized,
                finalized_output_root=attempt.finalized_output_root,
                finalizer_source_sha256=qualification.finalizer_source_sha256,
                finalizer_projection_source_sha256=(
                    qualification.finalizer_projection_source_sha256
                ),
                finalizer_selector_sha256=qualification.finalizer_selector_sha256,
                finalizer_schema_sha256=qualification.finalizer_schema_sha256,
                interpreter=qualification.local_finalizer_interpreter,
                interpreter_sha256=qualification.local_finalizer_interpreter_sha256,
                dependency_manifest_sha256=(
                    qualification.local_finalizer_dependency_manifest_sha256
                ),
                dependency_tree_sha256=(qualification.local_finalizer_dependency_tree_sha256),
                evaluator_dependency_tree_sha256=(
                    qualification.local_evaluator_dependency_tree_sha256
                ),
                evaluator_contract_sha256=execution.evaluator_contract_sha256,
                package_commit=self._source_identity()[0],
                output_observer=self._condition_observers[run_id],
            )
        except BaseException as exc:
            self._raise_downstream_consumed_failure(
                operation=operation,
                run_id=run_id,
                stopping_phase="finalization",
                failure_class=ConditionFailureClass.FINALIZER,
                message="finalizer",
                cause=exc,
            )
        held_finalized: tuple[HeldArtifact, ...] = ()
        finalized_binding: str | None = None
        try:
            raw_manifest, raw_receipt = host.validate_raw_attempt_seal(
                attempt_root=raw.raw_root.parent,
                raw_root=raw.raw_root,
                run_id=run_id,
                package_commit=request.package_commit,
            )
            if (
                raw_manifest.get("total_bytes") != raw.raw_total_bytes
                or len(cast(list[object], raw_manifest.get("files", []))) != raw.raw_file_count
                or raw_receipt.get("raw_file_count") != raw.raw_file_count
                or raw_receipt.get("raw_total_bytes") != raw.raw_total_bytes
                or _file_sha256(raw.raw_manifest_path) != manifest_sha
                or _file_sha256(raw.raw_receipt_path) != receipt_sha
            ):
                raise AdapterFailure("raw evidence changed before finalizer entry")
            self._revalidate_artifacts(raw_artifacts)
            try:
                outcome = self.low_level_effects.finalize_condition(request)
            finally:
                self._record_boundary_state(run_id, self._condition_observers[run_id])
            self._revalidate_artifacts(raw_artifacts)
            post_manifest, post_receipt = host.validate_raw_attempt_seal(
                attempt_root=raw.raw_root.parent,
                raw_root=raw.raw_root,
                run_id=run_id,
                package_commit=request.package_commit,
            )
            if post_manifest != raw_manifest or post_receipt != raw_receipt:
                raise AdapterFailure("finalizer changed immutable raw evidence")
            final_root = _safe_directory(
                self.root,
                outcome.finalized_root,
                label="finalized condition root",
            )
            completion_path = _safe_existing_file(
                final_root,
                outcome.completion_receipt_path,
                label="finalization completion receipt",
            )
            sessions = tuple(
                _safe_existing_file(final_root, path, label="finalized session")
                for path in outcome.session_paths
            )
            completion = load_json(completion_path)
            session_hashes = [_file_sha256(path) for path in sessions]
            expected_completion = {
                "schema_version": "1.0.0",
                "run_id": run_id,
                "evaluator_run_id": request.evaluator_run_id,
                "execution_mode": request.execution_mode,
                "runtime_qualification_id": request.runtime_qualification_id,
                "runtime_qualification_sha256": request.runtime_qualification_sha256,
                "raw_output_root": request.raw_output_root,
                "finalized_output_root": request.finalized_output_root,
                "consumed_raw_manifest_sha256": manifest_sha,
                "consumed_raw_receipt_sha256": receipt_sha,
                "consumed_raw_completion_sha256": request.raw_completion_sha256,
                "consumed_process_outcome_sha256": request.process_outcome_sha256,
                "consumed_raw_artifact_binding_sha256": (request.raw_artifact_binding_sha256),
                "finalizer_source_sha256": request.finalizer_source_sha256,
                "finalizer_projection_source_sha256": (request.finalizer_projection_source_sha256),
                "finalizer_selector_sha256": request.finalizer_selector_sha256,
                "finalizer_schema_sha256": request.finalizer_schema_sha256,
                "interpreter": request.interpreter,
                "interpreter_sha256": request.interpreter_sha256,
                "dependency_manifest_sha256": request.dependency_manifest_sha256,
                "dependency_tree_sha256": request.dependency_tree_sha256,
                "evaluator_dependency_tree_sha256": (request.evaluator_dependency_tree_sha256),
                "evaluator_contract_sha256": request.evaluator_contract_sha256,
                "semantic_projection_sha256": outcome.semantic_projection_sha256,
                "session_sha256s": session_hashes,
                "infrastructure_valid": outcome.infrastructure_valid,
            }
            rebound = host.validate_finalizer_source(
                repository=self.repository,
                package_commit=request.package_commit,
                finalizer_commit=request.package_commit,
                source=self.repository / host.FINALIZER_RELATIVE_PATH,
                projection_source=(self.repository / host.FINALIZER_PROJECTION_RELATIVE_PATH),
                source_inputs=self.source_inputs,
            )
            if (
                outcome.run_id != run_id
                or final_root != expected_finalized
                or not sessions
                or len(set(sessions)) != len(sessions)
                or completion != expected_completion
                or _file_sha256(completion_path) != outcome.completion_receipt_sha256
                or outcome.consumed_raw_manifest_sha256 != manifest_sha
                or outcome.consumed_raw_receipt_sha256 != receipt_sha
                or outcome.consumed_raw_artifact_binding_sha256 != raw_binding
                or _file_sha256(raw.raw_manifest_path) != manifest_sha
                or _file_sha256(raw.raw_receipt_path) != receipt_sha
                or _file_sha256(raw.completion_path) != request.raw_completion_sha256
                or _file_sha256(raw.process_outcome_path) != request.process_outcome_sha256
                or not outcome.infrastructure_valid
                or _HEX64.fullmatch(outcome.semantic_projection_sha256) is None
                or tuple(rebound[:4])
                != (
                    request.finalizer_source_sha256,
                    request.finalizer_projection_source_sha256,
                    request.finalizer_selector_sha256,
                    request.finalizer_schema_sha256,
                )
            ):
                raise AdapterFailure("finalizer outcome or retained source identity drifted")
            finalized_paths = tuple(path for path in final_root.rglob("*") if not path.is_dir())
            held_finalized = self._hold_artifact_set(finalized_paths)
            finalized_binding = self._artifact_binding(held_finalized)
            observer = self._condition_observers[run_id]
            selection_root = self._pilot_state.parent
            before_selection = host.full_attempt_tree_usage(selection_root).bytes

            def admit_selection(path: Path, count: int) -> None:
                if not path.is_relative_to(selection_root) or any(
                    item.is_symlink() for item in (path, *path.parents)
                ):
                    raise AdapterFailure("shared finalizer selection escaped its control root")
                observer.allocate_controller_output_bytes(count=count)

            try:
                pilot.mark_attempt_completed(
                    self._pilot_state,
                    execution_contract_sha256=execution.sha256,
                    run_id=run_id,
                    finalizer_execution_mode=request.execution_mode,
                    finalizer_runtime_qualification_sha256=(request.runtime_qualification_sha256),
                    finalizer_source_sha256=request.finalizer_source_sha256,
                    finalizer_projection_source_sha256=(request.finalizer_projection_source_sha256),
                    finalizer_commit=request.package_commit,
                    finalizer_dependency_manifest_sha256=(request.dependency_manifest_sha256),
                    evaluator_contract_sha256=execution.evaluator_contract_sha256,
                    interpreter=request.interpreter,
                    interpreter_sha256=request.interpreter_sha256,
                    semantic_projection_sha256=outcome.semantic_projection_sha256,
                    finalized_output_root=attempt.finalized_output_root,
                    finalization_complete_sha256=outcome.completion_receipt_sha256,
                    before_write=admit_selection,
                )
            finally:
                observed_selection = (
                    host.full_attempt_tree_usage(selection_root).bytes - before_selection
                )
                if observed_selection < 0:
                    raise AdapterFailure("shared finalizer selection removed retained evidence")
                observer.observe_controller_output_bytes(count=observed_selection)
                self._record_boundary_state(run_id, observer)

        except BaseException as exc:
            for artifact in held_finalized:
                artifact.close()
            self._raise_downstream_consumed_failure(
                operation=operation,
                run_id=run_id,
                stopping_phase="finalization",
                failure_class=ConditionFailureClass.FINALIZER,
                message="finalizer",
                cause=exc,
            )
        assert finalized_binding is not None
        self._finalizations[run_id] = outcome
        self._finalized_artifacts[run_id] = held_finalized
        self._finalized_artifact_bindings[run_id] = finalized_binding
        self._primitive("validate_raw_attempt_seal:pre-finalizer")
        self._primitive("validate_raw_attempt_seal:post-finalizer")
        self._primitive("validate_finalizer_source")
        self._primitive("mark_attempt_completed")
        self._primitive("execute_offline_finalizer")
        self._record(operation, run_id, "passed")
        return outcome.completion_receipt_sha256

    @staticmethod
    def _evaluator_outcome_identity(outcome: EvaluatorExecutionOutcome) -> str:
        return _identity(
            {
                "run_id": outcome.run_id,
                "evaluator_run_id": outcome.evaluator_run_id,
                "consumed_session_sha256s": list(outcome.consumed_session_sha256s),
                "consumed_finalized_artifact_binding_sha256": (
                    outcome.consumed_finalized_artifact_binding_sha256
                ),
                "evaluator_contract_sha256": outcome.evaluator_contract_sha256,
                "evaluator_valid": outcome.evaluator_valid,
                "task_completed": outcome.task_completed,
                "answer_produced": outcome.answer_produced,
                "score": outcome.score,
                "infrastructure_failure": outcome.infrastructure_failure,
                "missing_required_evidence": outcome.missing_required_evidence,
            }
        )

    def evaluate(self, run_id: str) -> str:
        operation = "condition.evaluate"
        self._begin(operation, run_id)
        execution = self._require_execution()
        try:
            finalized = self._finalizations.get(run_id)
            finalized_artifacts = self._finalized_artifacts.get(run_id)
            finalized_binding = self._finalized_artifact_bindings.get(run_id)
            if (
                finalized is None
                or not finalized.infrastructure_valid
                or finalized_artifacts is None
                or finalized_binding is None
            ):
                raise AdapterFailure("infrastructure-invalid finalization remains unscored")
            self._revalidate_artifacts(finalized_artifacts)
            artifact_paths = {
                self.root / artifact.relative_path: artifact for artifact in finalized_artifacts
            }
            if any(path not in artifact_paths for path in finalized.session_paths):
                raise AdapterFailure("evaluator sessions are absent from held finalization")
            attempt = execution.attempt(run_id)
            request = EvaluatorExecutionRequest(
                run_id=run_id,
                evaluator_run_id=self.contract.evaluator_run_ids[
                    self.contract.run_ids.index(run_id)
                ],
                task_id=attempt.task_id,
                task_index=attempt.task_index,
                finalized_root=finalized.finalized_root,
                session_paths=finalized.session_paths,
                finalized_artifacts=finalized_artifacts,
                finalized_artifact_binding_sha256=finalized_binding,
                evaluator_contract_path=execution.evaluator_contract_path,
                evaluator_contract_sha256=execution.evaluator_contract_sha256,
                package_commit=self._source_identity()[0],
            )
        except BaseException as exc:
            self._raise_downstream_consumed_failure(
                operation=operation,
                run_id=run_id,
                stopping_phase="evaluation",
                failure_class=ConditionFailureClass.EVALUATOR,
                message="evaluator",
                cause=exc,
            )
        try:
            self._revalidate_artifacts(finalized_artifacts)
            outcome = self.low_level_effects.evaluate_condition(request)
            self._revalidate_artifacts(finalized_artifacts)
            session_hashes = tuple(artifact_paths[path].sha256 for path in request.session_paths)
            if (
                outcome.run_id != run_id
                or outcome.evaluator_run_id != request.evaluator_run_id
                or Path(os.path.abspath(outcome.consumed_finalized_root))
                != Path(os.path.abspath(request.finalized_root))
                or outcome.consumed_session_sha256s != session_hashes
                or outcome.consumed_finalized_artifact_binding_sha256 != finalized_binding
                or outcome.evaluator_contract_sha256 != execution.evaluator_contract_sha256
                or outcome.receipt_sha256 != self._evaluator_outcome_identity(outcome)
                or outcome.infrastructure_failure
                or outcome.missing_required_evidence
                or (
                    outcome.score is not None
                    and (
                        not isinstance(outcome.score, (int, float))
                        or isinstance(outcome.score, bool)
                        or not math.isfinite(float(outcome.score))
                    )
                )
            ):
                raise AdapterFailure("evaluator outcome drifted from finalized effect output")
            contract = pilot.outcome_contract(
                process_exit_code=0,
                artifact_executed=True,
                task_completed=outcome.task_completed,
                answer_produced=outcome.answer_produced,
                evaluator_valid=outcome.evaluator_valid,
                score=outcome.score,
                infrastructure_failure=outcome.infrastructure_failure,
                missing_required_evidence=outcome.missing_required_evidence,
            )
        except BaseException as exc:
            self._raise_downstream_consumed_failure(
                operation=operation,
                run_id=run_id,
                stopping_phase="evaluation",
                failure_class=ConditionFailureClass.EVALUATOR,
                message="evaluator",
                cause=exc,
            )
        self._evaluations[run_id] = {
            "evaluator_run_id": outcome.evaluator_run_id,
            "evaluator_valid": outcome.evaluator_valid,
            "task_completed": outcome.task_completed,
            "answer_produced": outcome.answer_produced,
            "score": outcome.score,
            "valid_scored_attempt": contract["valid_scored_attempt"],
            "receipt_sha256": outcome.receipt_sha256,
            "classification": (
                "control-conformance-output-not-science"
                if self.authority.kind is EffectAuthorityKind.SHADOW_ONLY
                else "package-effect-evaluator-output-awaiting-scientific-validation"
            ),
        }
        self._primitive("EvaluatorIdentity.verify")
        self._primitive("evaluate_retained_session")
        self._primitive("outcome_contract")
        self._record(operation, run_id, "passed")
        return outcome.receipt_sha256

    def record(self, *, kind: str, identity: str) -> None:
        operation = "evidence.record"
        self._begin(operation, kind)
        try:
            _require_sha(identity, label=f"{kind} evidence")
        except AdapterFailure:
            self._record(operation, kind, "failed")
            raise
        self._record(operation, kind, f"retained:{identity[:12]}")

    @staticmethod
    def _provider_cost_receipt_identity(receipt: ProviderCostReceipt) -> str:
        values = asdict(receipt)
        values.pop("receipt_sha256")
        return _identity(values)

    @staticmethod
    def _provider_lifecycle_proof_identity(
        proof: ProviderLifecycleCostProof,
    ) -> str:
        values = asdict(proof)
        values.pop("receipt_sha256")
        return _identity(values)

    def _retained_provider_price(
        self,
        entry_source: Path,
    ) -> tuple[Decimal, str]:
        """Revalidate the exact retained offer that froze provider pricing."""

        provider.validate_source_manifest(entry_source, contract=self.contract)
        price_source = entry_source / "001-instance-types.json"
        source = load_json(price_source)
        data = source.get("data")
        offer = data.get(provider.INSTANCE_TYPE) if isinstance(data, dict) else None
        identity = offer.get("instance_type") if isinstance(offer, dict) else None
        cents = identity.get("price_cents_per_hour") if isinstance(identity, dict) else None
        if type(cents) is not int or cents <= 0:
            raise AdapterFailure("retained provider price source is malformed or zero")
        return Decimal(cents) / Decimal(100), _file_sha256(price_source)

    def _closed_provider_interval(
        self,
        *,
        ordinal: int,
        prior_cumulative: Decimal,
        expected_price: Decimal,
    ) -> tuple[ProviderLifecycleInterval, Decimal, str]:
        """Reconstruct one closed preflight/replacement slot from retained bytes."""

        root = self._campaign_roots.get(ordinal)
        if root is None:
            raise AdapterFailure("provider lifecycle omitted one consumed launch root")
        eligibility_path = root / "replacement-launch-eligibility.json"
        eligibility = load_json(eligibility_path)
        if (
            eligibility.get("closed_launch_slot") != ordinal
            or eligibility.get("terminal_or_absent") is not True
            or eligibility.get("zero_t09_instances") is not True
            or eligibility.get("security_restored") is not True
        ):
            raise AdapterFailure("closed provider slot lacks terminal retained eligibility")
        cumulative = _decimal_number(
            eligibility.get("prior_lambda_cost_usd"),
            label="closed provider cumulative cost",
        )
        if cumulative < prior_cumulative:
            raise AdapterFailure("closed provider cumulative cost moved backward")

        entry_source = root / "entry-source"
        price, price_sha = self._retained_provider_price(entry_source)
        if price != expected_price:
            raise AdapterFailure("closed provider slot used another frozen hourly price")
        entry_path = entry_source / "entry-receipt.json"
        closeout_path = root / "closeout-source/closeout-receipt.json"
        commit, _tree = self._source_identity()
        plan_sha = _file_sha256(self.repository / self.contract.provider_profile_path)
        if entry_path.is_file() and closeout_path.is_file():
            with self.low_level_effects.campaign_scope():
                entry = provider.validate_entry_receipt_source_bound(
                    entry_path,
                    entry_source,
                    contract=self.contract,
                    package_commit=commit,
                    plan_sha256=plan_sha,
                )
                closeout = provider.validate_closeout_receipt(
                    closeout_path,
                    root / "closeout-source",
                    contract=self.contract,
                    entry_receipt_path=entry_path,
                    entry_source_root=entry_source,
                    package_commit=commit,
                    plan_sha256=plan_sha,
                    lifecycle=provider.load_campaign_lifecycle(
                        self.repository,
                        contract=self.contract,
                    ),
                )
            owner = cast(str, entry["owned_instance_identity_sha256"])
            started = finite_time(
                entry.get("owned_lambda_started_at_epoch"),
                label="closed provider active start",
            )
            ended = max(
                finite_time(
                    closeout.get("terminal_observed_at_epoch"),
                    label="closed provider terminal observation",
                ),
                finite_time(
                    closeout.get("zero_instance_observed_at_epoch"),
                    label="closed provider zero observation",
                ),
            )
            entry_identity = _file_sha256(entry_path)
            closeout_identity = _file_sha256(closeout_path)
            retained_cumulative = _decimal_number(
                closeout.get("lambda_list_cost_usd"),
                label="source-bound closeout cumulative cost",
            )
        else:
            owner_path = root / "provisional-owned-state.json"
            closed_path = root / "PROVISIONAL_OWNER_CLOSED.json"
            owner_document = load_json(owner_path)
            closed_document = load_json(closed_path)
            owner = cast(str, owner_document.get("owned_instance_identity_sha256"))
            if (
                not isinstance(owner, str)
                or _HEX64.fullmatch(owner) is None
                or closed_document.get("owned_instance_identity_sha256") != owner
                or closed_document.get("provider_disposition") != "absent"
            ):
                raise AdapterFailure("provisional provider closeout identity drifted")
            started = finite_time(
                owner_document.get("lambda_started_at_epoch"),
                label="provisional provider active start",
            )
            ended = finite_time(
                closed_document.get("closed_at_epoch"),
                label="provisional provider active end",
            )
            entry_identity = _file_sha256(owner_path)
            closeout_identity = _file_sha256(closed_path)
            retained_cumulative = cumulative
        if ended < started:
            raise AdapterFailure("closed provider interval ends before it starts")
        interval_cost = (Decimal(str(ended)) - Decimal(str(started))) * price / Decimal(3600)
        billable = (
            self.authorization_context.execution_mode
            is not EffectExecutionMode.DETERMINISTIC_NO_NETWORK
        )
        # The no-network lifecycle preserves simulated time/price arithmetic while
        # its typed proof projects zero real spend.
        derived_cumulative = prior_cumulative + interval_cost
        tolerance = Decimal("0.000000001")
        if (
            abs(retained_cumulative - cumulative) > tolerance
            or abs(derived_cumulative - cumulative) > tolerance
        ):
            raise AdapterFailure("closed provider interval cost is not source-derived")
        interval = ProviderLifecycleInterval(
            launch_ordinal=ordinal,
            owned_instance_identity=owner,
            entry_or_owner_receipt_sha256=entry_identity,
            closeout_receipt_sha256=closeout_identity,
            active_started_wall_time=started,
            active_ended_wall_time=ended,
            hourly_price_usd=_decimal_text(price),
            billed_cost_usd=_decimal_text(interval_cost if billable else Decimal(0)),
            billable_real_effect=billable,
        )
        return (
            interval,
            cumulative,
            _identity(
                {
                    "eligibility_sha256": _file_sha256(eligibility_path),
                    "entry_or_owner_receipt_sha256": entry_identity,
                    "closeout_receipt_sha256": closeout_identity,
                    "provider_price_source_sha256": price_sha,
                }
            ),
        )

    def _derive_provider_lifecycle_cost_proof(
        self,
        *,
        state: Mapping[str, object],
        active: ProviderHandle,
        observed_wall: float,
        observed_monotonic: float,
    ) -> ProviderLifecycleCostProof:
        """Derive checkpoint provider cost solely from retained lifecycle evidence."""

        try:
            profile = load_provider_profile(self.repository, self.contract)
        except (OSError, T09ProviderContractError) as exc:
            raise AdapterFailure("provider lifecycle profile identity drifted") from exc
        lifecycle = profile.get("provider_lifecycle")
        budget = profile.get("budget")
        if (
            not isinstance(lifecycle, dict)
            or lifecycle.get("cumulative_accounting_origin") != "actual-active-lambda-seconds"
            or not isinstance(budget, dict)
            or budget.get("max_provider_compute_cost_usd")
            != self.contract.campaign_lambda_cost_cap_usd
        ):
            raise AdapterFailure("provider profile does not freeze lifecycle cost policy")
        profile_sha = _file_sha256(self.repository / self.contract.provider_profile_path)
        if profile_sha != self.contract.expected_provider_profile_sha256:
            raise AdapterFailure("provider profile hash differs from the selected contract")

        expected_closed = tuple(range(1, active.launch_ordinal))
        if tuple(self._closed_launch_slots) != expected_closed:
            raise AdapterFailure("provider lifecycle closed-slot set is incomplete or duplicated")
        active_root = self._campaign_roots.get(active.launch_ordinal)
        entry_path = self._entry_receipts.get(active.launch_ordinal)
        if active_root is None or entry_path is None:
            raise AdapterFailure("provider lifecycle lacks its active source-bound entry")
        entry_source = active_root / "entry-source"
        commit, _tree = self._source_identity()
        with self.low_level_effects.campaign_scope():
            entry = provider.validate_entry_receipt_source_bound(
                entry_path,
                entry_source,
                contract=self.contract,
                package_commit=commit,
                plan_sha256=profile_sha,
            )
        price, active_price_sha = self._retained_provider_price(entry_source)
        if _decimal_number(entry.get("hourly_price_usd"), label="entry hourly price") != price:
            raise AdapterFailure("provider entry price differs from its retained offer")
        if (
            entry.get("owned_instance_identity_sha256") != active.opaque_identity
            or entry.get("launch_slot") != active.launch_ordinal
        ):
            raise AdapterFailure("active provider entry identity drifted")

        campaign_wall = finite_time(
            state.get("campaign_started_at_epoch"),
            label="campaign wall origin",
        )
        if self._freeze is None or self._campaign_started_monotonic is None:
            raise AdapterFailure("empirical provider clock is not bound to the durable freeze")
        frozen_wall, frozen_mono = self._frozen_campaign_origins(self._freeze)
        if campaign_wall != frozen_wall or self._campaign_started_monotonic != frozen_mono:
            raise AdapterFailure("empirical provider clock drifted from the sealed origin")
        campaign_mono = self._campaign_started_monotonic
        wall_elapsed = observed_wall - campaign_wall
        monotonic_elapsed = observed_monotonic - campaign_mono
        if wall_elapsed < 0 or monotonic_elapsed < 0 or abs(wall_elapsed - monotonic_elapsed) > 1.0:
            raise AdapterFailure("provider observation mixes or shifts clock domains")

        intervals: list[ProviderLifecycleInterval] = []
        price_source_hashes: list[str] = []
        closed_receipt_hashes: list[str] = []
        prior_cumulative = Decimal(0)
        prior_end: float | None = None
        for ordinal in expected_closed:
            interval, prior_cumulative, source_binding = self._closed_provider_interval(
                ordinal=ordinal,
                prior_cumulative=prior_cumulative,
                expected_price=price,
            )
            if prior_end is not None and interval.active_started_wall_time < prior_end:
                raise AdapterFailure("provider lifecycle intervals overlap")
            assert interval.active_ended_wall_time is not None
            prior_end = interval.active_ended_wall_time
            intervals.append(interval)
            price_source_hashes.append(
                _file_sha256(self._campaign_roots[ordinal] / "entry-source/001-instance-types.json")
            )
            closed_receipt_hashes.append(source_binding)

        active_started = finite_time(
            entry.get("owned_lambda_started_at_epoch"),
            label="active provider start",
        )
        if (
            active_started > campaign_wall
            or campaign_wall > observed_wall
            or (prior_end is not None and active_started < prior_end)
        ):
            raise AdapterFailure("active provider interval chronology drifted")
        retained_prior = _decimal_number(
            entry.get("prior_campaign_lambda_cost_usd"),
            label="active entry prior provider cost",
        )
        state_prior = _decimal_number(
            state.get("prior_campaign_lambda_cost_usd"),
            label="pilot-state prior provider cost",
        )
        if (
            abs(retained_prior - prior_cumulative) > Decimal("0.000000001")
            or state_prior != retained_prior
        ):
            raise AdapterFailure("prior provider cost omits or duplicates a closed slot")

        deterministic = (
            self.authorization_context.execution_mode
            is EffectExecutionMode.DETERMINISTIC_NO_NETWORK
        )
        current_preflight = (
            (Decimal(str(campaign_wall)) - Decimal(str(active_started))) * price / Decimal(3600)
        )
        empirical = (
            (Decimal(str(observed_wall)) - Decimal(str(campaign_wall))) * price / Decimal(3600)
        )
        if deterministic:
            prior_cost = Decimal(0)
            empirical_cost = Decimal(0)
            active_cost = Decimal(0)
        else:
            prior_cost = prior_cumulative + current_preflight
            empirical_cost = empirical
            active_cost = current_preflight + empirical
        intervals.append(
            ProviderLifecycleInterval(
                launch_ordinal=active.launch_ordinal,
                owned_instance_identity=active.opaque_identity,
                entry_or_owner_receipt_sha256=_file_sha256(entry_path),
                closeout_receipt_sha256=None,
                active_started_wall_time=active_started,
                active_ended_wall_time=None,
                hourly_price_usd=_decimal_text(price),
                billed_cost_usd=_decimal_text(active_cost),
                billable_real_effect=not deterministic,
            )
        )
        price_source_hashes.append(active_price_sha)
        price_binding = _identity(price_source_hashes)
        cumulative = prior_cost + empirical_cost
        provisional = ProviderLifecycleCostProof(
            provider_contract_version=self.contract.version,
            plan_id=self.contract.plan_id,
            provider_profile_sha256=profile_sha,
            provider_price_source_sha256=price_binding,
            active_entry_receipt_sha256=_file_sha256(entry_path),
            closed_slot_source_binding_sha256s=tuple(closed_receipt_hashes),
            intervals=tuple(intervals),
            prior_preflight_cost_usd=_decimal_text(prior_cost),
            current_empirical_cost_usd=_decimal_text(empirical_cost),
            cumulative_provider_cost_usd=_decimal_text(cumulative),
            observed_wall_time=observed_wall,
            observed_monotonic=observed_monotonic,
            real_provider_effects=not deterministic,
            receipt_sha256="0" * 64,
        )
        proof = ProviderLifecycleCostProof(
            **{
                **asdict(provisional),
                "intervals": provisional.intervals,
                "receipt_sha256": self._provider_lifecycle_proof_identity(provisional),
            }
        )
        if proof.receipt_sha256 != self._provider_lifecycle_proof_identity(proof):
            raise AdapterFailure("provider lifecycle proof identity drifted")
        self._provider_lifecycle_cost_proof = proof
        self._primitive("validate_provider_lifecycle_cost_proof")
        return proof

    def _observe_provider_cost(
        self,
        *,
        state: Mapping[str, object],
    ) -> ProviderLifecycleCostProof:
        candidates = [
            handle
            for ordinal, handle in sorted(self._provider_handles.items())
            if ordinal not in self._closed_launch_slots
        ]
        if len(candidates) != 1:
            raise AdapterFailure("checkpoint lacks one exact active provider owner")
        if self._campaign_started_monotonic is None:
            raise AdapterFailure("checkpoint lacks its campaign monotonic origin")
        observed_wall = self.clock.wall_time()
        observed_monotonic = self.clock.monotonic()
        proof = self._derive_provider_lifecycle_cost_proof(
            state=state,
            active=candidates[0],
            observed_wall=observed_wall,
            observed_monotonic=observed_monotonic,
        )
        active_interval = proof.intervals[-1]
        request = ProviderCostObservationRequest(
            provider_handle=candidates[0],
            observed_wall_time=observed_wall,
            observed_monotonic=observed_monotonic,
            campaign_started_wall_time=finite_time(
                state.get("campaign_started_at_epoch"),
                label="campaign wall origin",
            ),
            campaign_started_monotonic=self._campaign_started_monotonic,
            provider_profile_sha256=proof.provider_profile_sha256,
            provider_price_source_sha256=proof.provider_price_source_sha256,
            active_entry_receipt_sha256=proof.active_entry_receipt_sha256,
            closed_slot_receipt_sha256s=proof.closed_slot_source_binding_sha256s,
            frozen_hourly_price_usd=float(active_interval.hourly_price_usd),
            active_started_wall_time=active_interval.active_started_wall_time,
            prior_preflight_cost_usd=float(proof.prior_preflight_cost_usd),
            current_empirical_cost_usd=float(proof.current_empirical_cost_usd),
            cumulative_provider_cost_usd=float(proof.cumulative_provider_cost_usd),
        )
        receipt = self.low_level_effects.provider_cost_receipt(request)
        self._validate_provider_cost_reconciliation(
            receipt=receipt,
            request=request,
            proof=proof,
            contract=self.contract,
        )
        self._provider_cost_receipt = receipt
        return proof

    @staticmethod
    def _validate_provider_cost_reconciliation(
        *,
        receipt: ProviderCostReceipt,
        request: ProviderCostObservationRequest,
        proof: ProviderLifecycleCostProof,
        contract: T09ProviderContract,
    ) -> None:
        """Reject any effect-selected value that differs from shared lifecycle truth."""

        if (
            receipt.provider_contract_version != contract.version
            or receipt.plan_id != contract.plan_id
            or receipt.owned_instance_identity != request.provider_handle.opaque_identity
            or receipt.launch_ordinal != request.provider_handle.launch_ordinal
            or receipt.provider_profile_sha256 != request.provider_profile_sha256
            or receipt.provider_price_source_sha256 != request.provider_price_source_sha256
            or receipt.active_entry_receipt_sha256 != request.active_entry_receipt_sha256
            or receipt.closed_slot_receipt_sha256s != request.closed_slot_receipt_sha256s
            or receipt.hourly_price_usd != request.frozen_hourly_price_usd
            or receipt.active_started_wall_time != request.active_started_wall_time
            or receipt.active_ended_wall_time is not None
            or receipt.observed_wall_time != request.observed_wall_time
            or receipt.observed_monotonic != request.observed_monotonic
            or receipt.prior_preflight_cost_usd != request.prior_preflight_cost_usd
            or receipt.current_empirical_cost_usd != request.current_empirical_cost_usd
            or receipt.cumulative_provider_cost_usd != request.cumulative_provider_cost_usd
            or receipt.real_provider_effects is not proof.real_provider_effects
            or receipt.receipt_sha256
            != ProductionCategory3World._provider_cost_receipt_identity(receipt)
        ):
            raise AdapterFailure(
                "effect provider-cost receipt differs from shared-derived lifecycle evidence"
            )

    def _checkpoint_cost_projection(
        self,
        *,
        actual_provider_cost_usd: float,
    ) -> float:
        execution = self._require_execution()
        document = load_json(execution.path)
        calibration = document.get("budget_calibration")
        expected = calibration.get("expected") if isinstance(calibration, dict) else None
        reactive = expected.get("reactive_attempt") if isinstance(expected, dict) else None
        simulative = expected.get("simulative_attempt") if isinstance(expected, dict) else None
        values = (
            expected.get("aggregate_total_cost_usd") if isinstance(expected, dict) else None,
            reactive.get("total_cost_usd") if isinstance(reactive, dict) else None,
            simulative.get("total_cost_usd") if isinstance(simulative, dict) else None,
        )
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or float(value) < 0
            for value in values
        ):
            raise AdapterFailure("frozen checkpoint cost projection is malformed")
        aggregate_expected, reactive_expected, simulative_expected = (
            float(cast(float, value)) for value in values
        )
        remaining_expected = reactive_expected + simulative_expected
        actual_first_pair = self._aggregate_usage.cost_usd + actual_provider_cost_usd
        projected = max(aggregate_expected, actual_first_pair + remaining_expected)
        if not math.isfinite(projected) or projected < actual_first_pair:
            raise AdapterFailure("checkpoint cost projection is not conservative")
        return projected

    def _task_a_checkpoint_evidence(
        self,
        *,
        state: Mapping[str, object],
    ) -> tuple[
        tuple[bool, bool],
        tuple[bool, bool],
        tuple[bool, bool],
        bool,
        bool,
        bool,
        bool,
        bool,
        dict[str, object],
    ]:
        self._require_execution()
        host = _host_module(self.repository)
        run_ids = self.contract.run_ids[:2]
        raw_bindings = state.get("raw_attempt_bindings")
        selections = state.get("attempt_finalizations")
        if not isinstance(raw_bindings, dict) or not isinstance(selections, dict):
            raise AdapterFailure("checkpoint retained attempt state is malformed")
        raw_valid: list[bool] = []
        evaluator_valid: list[bool] = []
        valid_scored: list[bool] = []
        credential_issue = bool(state.get("credential_safety_stop_detected"))
        cleanup_issue = bool(state.get("core_safety_stop_detected"))
        evidence_bindings: dict[str, object] = {}
        for run_id in run_ids:
            outcome = self._condition_outcomes.get(run_id)
            finalized = self._finalizations.get(run_id)
            evaluation = self._evaluations.get(run_id)
            binding = raw_bindings.get(run_id)
            valid = False
            raw_receipt: dict[str, object] = {}
            manifest_identity: str | None = None
            receipt_identity: str | None = None
            try:
                if outcome is None or not isinstance(binding, dict):
                    raise AdapterFailure("Task A raw outcome is absent")
                manifest, raw_receipt = host.validate_raw_attempt_seal(
                    attempt_root=outcome.raw_root.parent,
                    raw_root=outcome.raw_root,
                    run_id=run_id,
                    package_commit=self._source_identity()[0],
                )
                manifest_sha = _file_sha256(outcome.raw_manifest_path)
                receipt_sha = _file_sha256(outcome.raw_receipt_path)
                manifest_identity = manifest_sha
                receipt_identity = receipt_sha
                exported = self.public_root / (
                    f"raw-export-{self.contract.run_ids.index(run_id):02d}.json"
                )
                export_document = load_json(exported)
                valid = (
                    binding == {"manifest_sha256": manifest_sha, "receipt_sha256": receipt_sha}
                    and run_id in cast(list[object], state.get("raw_attempts_complete", []))
                    and manifest.get("total_bytes") == outcome.raw_total_bytes
                    and raw_receipt.get("raw_file_count") == outcome.raw_file_count
                    and raw_receipt.get("raw_total_bytes") == outcome.raw_total_bytes
                    and export_document
                    == {
                        "run_id": run_id,
                        "raw_manifest_sha256": manifest_sha,
                        "raw_receipt_sha256": receipt_sha,
                        "raw_file_count": outcome.raw_file_count,
                        "raw_total_bytes": outcome.raw_total_bytes,
                    }
                    and self._raw_export_acknowledgements.get(run_id) == _file_sha256(exported)
                    and finalized is not None
                    and finalized.consumed_raw_manifest_sha256 == manifest_sha
                    and finalized.consumed_raw_receipt_sha256 == receipt_sha
                    and finalized.infrastructure_valid
                    and _file_sha256(finalized.completion_receipt_path)
                    == finalized.completion_receipt_sha256
                )
            except (AdapterFailure, OSError, ValueError, KeyError):
                valid = False
            raw_valid.append(valid)
            credential_issue = credential_issue or any(
                raw_receipt.get(field) is True
                for field in (
                    "actual_credential_exposure_detected",
                    "credential_cleanup_integrity_failure",
                )
            )
            cleanup_issue = cleanup_issue or (
                raw_receipt.get("condition_terminated") is not True
                or raw_receipt.get("container_and_browser_cleanup_clean") is not True
                or raw_receipt.get("credential_cleanup_clean") is not True
                or raw_receipt.get("structural_privacy_findings") != []
            )
            evaluator_valid.append(
                isinstance(evaluation, dict) and evaluation.get("evaluator_valid") is True
            )
            valid_scored.append(
                isinstance(evaluation, dict)
                and evaluation.get("valid_scored_attempt") is True
                and isinstance(evaluation.get("score"), (int, float))
                and not isinstance(evaluation.get("score"), bool)
                and math.isfinite(float(cast(float, evaluation.get("score"))))
            )
            evidence_bindings[run_id] = {
                "raw_valid": valid,
                "raw_manifest_sha256": manifest_identity,
                "raw_receipt_sha256": receipt_identity,
                "finalization_complete_sha256": (
                    None if finalized is None else finalized.completion_receipt_sha256
                ),
                "evaluator_receipt_sha256": (
                    None if evaluation is None else evaluation.get("receipt_sha256")
                ),
                "evaluator_valid": evaluator_valid[-1],
                "valid_scored_attempt": valid_scored[-1],
            }
        command, command_sha, _source = resolve_registered_command_package(
            self.repository,
            self.contract,
            source_inputs=self.source_inputs,
        )
        manifests = command.get("manifests")
        pair_diffs = command.get("pair_diffs")
        if not isinstance(manifests, list) or len(manifests) < 2:
            raise AdapterFailure("checkpoint command pair is absent")
        left, right = manifests[:2]
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise AdapterFailure("checkpoint command pair is malformed")
        recomputed_pair = pilot.diff_pair_manifests(left, right)
        pair_match = (
            command_sha == self._command_package_sha256
            and isinstance(pair_diffs, list)
            and bool(pair_diffs)
            and pair_diffs[0] == recomputed_pair
            and recomputed_pair.get("valid") is True
        )
        selection_values = [selections.get(run_id) for run_id in run_ids]
        try:
            closure_hashes = {
                pilot._selection_closure_sha256(cast(dict[str, object], value))
                for value in selection_values
                if isinstance(value, dict)
            }
            finalizer_closure = (
                all(isinstance(value, dict) for value in selection_values)
                and len(closure_hashes) == 1
            )
        except (KeyError, pilot.T09PilotError):
            finalizer_closure = False
        scores = [
            evaluation.get("score") if isinstance(evaluation, dict) else None
            for evaluation in (self._evaluations.get(run_id) for run_id in run_ids)
        ]
        task_completed = [
            evaluation.get("task_completed") if isinstance(evaluation, dict) else None
            for evaluation in (self._evaluations.get(run_id) for run_id in run_ids)
        ]
        severe_floor_or_ceiling = all(valid_scored) and (
            (scores == [0.0, 0.0] and task_completed == [False, False])
            or (scores == [1.0, 1.0] and task_completed == [True, True])
        )
        evidence_bindings["pair"] = {
            "command_package_sha256": command_sha,
            "recomputed_pair_diff": recomputed_pair,
            "finalizer_closure_valid": finalizer_closure,
        }
        return (
            cast(tuple[bool, bool], tuple(raw_valid)),
            cast(tuple[bool, bool], tuple(evaluator_valid)),
            cast(tuple[bool, bool], tuple(valid_scored)),
            finalizer_closure,
            pair_match,
            credential_issue,
            cleanup_issue,
            severe_floor_or_ceiling,
            evidence_bindings,
        )

    def checkpoint(self, *, name: str) -> FirstPairCheckpointResult:
        operation = "evidence.checkpoint"
        self._begin(operation, name)
        execution = self._require_execution()
        try:
            state = pilot.load_validated_pilot_state(
                self._pilot_state,
                execution_contract_sha256=execution.sha256,
            )
            first_started = finite_time(
                state.get("first_pair_started_at_epoch"),
                label="first-pair start",
            )
            decided = self.clock.wall_time()
            decided_monotonic, remaining = self._campaign_remaining()
            first_monotonic = self._condition_started_monotonic.get(self.contract.run_ids[0])
            if (
                first_monotonic is None
                or decided < first_started
                or decided_monotonic < first_monotonic
            ):
                raise AdapterFailure("first-pair checkpoint time origins are invalid")
            (
                raw_valid,
                evaluator_valid,
                valid_scored,
                finalizer_closure,
                pair_match,
                credential_issue,
                cleanup_issue,
                severe_floor_or_ceiling,
                evidence_bindings,
            ) = self._task_a_checkpoint_evidence(state=state)
            provider_cost = self._observe_provider_cost(state=state)
            provider_cost_value = float(provider_cost.cumulative_provider_cost_usd)
            projected_cost = self._checkpoint_cost_projection(
                actual_provider_cost_usd=provider_cost_value,
            )
            assert self._runtime_budget is not None
            next_caps = self._runtime_budget.condition_caps.get(self.contract.run_ids[2])
            if next_caps is None:
                raise AdapterFailure("checkpoint lacks the next exact condition cap")
            checkpoint_input = pilot.PairCheckpointInput(
                plan_id=self.contract.plan_id,
                attempt_run_ids=cast(tuple[str, str], self.contract.run_ids[:2]),
                valid_evidence=raw_valid,
                evaluator_succeeded=evaluator_valid,
                pair_match_valid=pair_match,
                credential_issue=credential_issue,
                cleanup_issue=cleanup_issue,
                severe_floor_or_ceiling_failure=severe_floor_or_ceiling,
                actual_usage=self._aggregate_usage,
                actual_pair_wall_seconds=decided_monotonic - first_monotonic,
                projected_aggregate_cost_usd=projected_cost,
                actual_lambda_cost_usd=provider_cost_value,
                remaining_campaign_seconds=remaining,
                next_attempt_hard_wall_seconds=int(next_caps.max_wall_seconds),
                prior_t09_cost_usd=self.contract.prior_t09_cost_usd,
                cumulative_t09_cost_cap_usd=self.contract.cumulative_t09_cost_cap_usd,
                valid_scored_attempt=valid_scored,
                finalizer_closure_valid=finalizer_closure,
            )
            retained_decision = pilot.first_pair_decision(checkpoint_input)
            decision = {
                **retained_decision,
                "first_pair_started_at_epoch": first_started,
                "second_pair_started_at_epoch": (
                    decided if retained_decision.get("decision") == "continue-to-task-b" else None
                ),
                "decided_at_epoch": decided,
                "evidence_binding_sha256": _identity(evidence_bindings),
                "provider_cost_receipt_sha256": provider_cost.receipt_sha256,
                "provider_lifecycle_cost_proof_sha256": provider_cost.receipt_sha256,
            }
            decision_path = self._pilot_state.parent / "first-pair-checkpoint-decision.json"
            with self._pilot_control_writer(
                self.contract.run_ids[1], extra_paths=(decision_path,)
            ) as (admit, observed):
                pilot.record_first_pair_checkpoint(
                    self._pilot_state,
                    execution_contract_sha256=execution.sha256,
                    decision=decision,
                    decided_at_epoch=decided,
                    before_write=admit,
                    after_output_write=observed,
                )
            retained_state = pilot.load_validated_pilot_state(
                self._pilot_state,
                execution_contract_sha256=execution.sha256,
            )
            binding = retained_state.get("first_pair_checkpoint_binding")
            decision_sha = pilot.canonical_sha256(decision)
            if (
                retained_state.get("first_pair_decision") != retained_decision.get("decision")
                or retained_state.get("first_pair_decision_sha256") != decision_sha
                or not isinstance(binding, dict)
                or binding.get("decision_sha256") != decision_sha
            ):
                raise AdapterFailure("persisted first-pair decision binding drifted")
        except BaseException as exc:
            self._record(operation, name, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"first-pair checkpoint failed: {exc}") from exc
        disposition = FirstPairCheckpointDisposition(cast(str, retained_decision["decision"]))
        reasons = retained_decision.get("reasons")
        if not isinstance(reasons, list) or not all(isinstance(item, str) for item in reasons):
            self._record(operation, name, "failed")
            raise AdapterFailure("retained checkpoint reasons are malformed")
        result = FirstPairCheckpointResult(
            disposition=disposition,
            reasons=tuple(reasons),
            decision_sha256=decision_sha,
            evidence_binding_sha256=cast(str, decision["evidence_binding_sha256"]),
        )
        self._checkpoint_result = result
        self._checkpoint_document = decision
        self._primitive("first_pair_decision")
        self._primitive("record_first_pair_checkpoint")
        self._record(operation, name, disposition.value)
        return result

    @staticmethod
    def _cleanup_receipt_identity(receipt: CleanupExecutionReceipt) -> str:
        values = asdict(receipt)
        values.pop("receipt_sha256")
        return _identity(values)

    def _destroy_secret_file(self, path: Path) -> None:
        """Destroy one exact root-relative secret through no-follow directory FDs."""

        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise AdapterFailure("secret cleanup path escaped the held root") from exc
        pure = PurePosixPath(relative)
        if pure.is_absolute() or relative in {"", ".", ".."} or ".." in pure.parts:
            raise AdapterFailure("secret cleanup path is not one exact root-relative member")
        self.held_transaction_root.revalidate_descriptor()
        parent_relative = pure.parent.as_posix()
        if parent_relative == ".":
            parent_descriptor = os.dup(self.held_transaction_root.descriptor)
        else:
            parent_descriptor = self.held_transaction_root.open_relative_no_follow(
                parent_relative,
                flags=os.O_RDONLY | os.O_DIRECTORY,
            )
        leaf = pure.name
        try:
            try:
                named = os.stat(leaf, dir_fd=parent_descriptor, follow_symlinks=False)
            except FileNotFoundError:
                return
            if (
                not stat.S_ISREG(named.st_mode)
                or named.st_uid != os.getuid()
                or named.st_nlink != 1
            ):
                raise AdapterFailure("secret cleanup target identity is unsafe")
            descriptor = os.open(
                leaf,
                os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_descriptor,
            )
            try:
                metadata_value = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(metadata_value.st_mode)
                    or metadata_value.st_dev != named.st_dev
                    or metadata_value.st_ino != named.st_ino
                    or metadata_value.st_uid != os.getuid()
                    or metadata_value.st_nlink != 1
                ):
                    raise AdapterFailure("secret cleanup target identity is unsafe")
                size = metadata_value.st_size
                offset = 0
                block = b"\x00" * min(1_048_576, max(1, size))
                while offset < size:
                    written = os.pwrite(
                        descriptor,
                        block[: min(len(block), size - offset)],
                        offset,
                    )
                    if written <= 0:
                        raise AdapterFailure("secret cleanup overwrite made no progress")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.unlink(leaf, dir_fd=parent_descriptor)
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)

    def cleanup(self, handle: ProviderHandle | None) -> str:
        operation = "host.cleanup"
        subject = handle.opaque_identity if handle is not None else "no-known-instance"
        self._begin(operation, subject)
        self._cleanup_calls += 1
        execution = self._execution_contract
        interrupted = False
        try:
            state: dict[str, object]
            if self._root_identity_mismatch:
                state = {
                    "empirical_attempts_entered": list(self._entered_run_ids),
                    "raw_attempts_complete": list(self._raw_completed_run_ids),
                }
                self._primitive("held_in_memory_empirical_prefix:cleanup")
            elif execution is not None and self._pilot_state.is_file():
                state = pilot.load_validated_pilot_state(
                    self._pilot_state,
                    execution_contract_sha256=execution.sha256,
                )
                self._primitive("load_validated_pilot_state:cleanup")
            else:
                state = {"empirical_attempts_entered": [], "raw_attempts_complete": []}
            handoff = _canonical_bytes(
                {
                    "schema_version": "1.0.0",
                    "provider_contract_version": self.contract.version,
                    "plan_id": self.contract.plan_id,
                    "host_run_id": self.contract.host_run_id,
                    "empirical_prefix": state.get("empirical_attempts_entered", []),
                    "raw_prefix": state.get("raw_attempts_complete", []),
                    "provider_owner": self.contract.instance_name,
                    "container_prefix": self.contract.container_prefix,
                    "firewall_owner": self.contract.host_run_id,
                    "ruleset_owner": self.contract.plan_id,
                    "transaction_root_identity": (
                        self.authorization_context.transaction_root_identity
                    ),
                }
            )
            if self._cleanup_handoff_bytes is None:
                self._cleanup_handoff_bytes = handoff
            elif handoff != self._cleanup_handoff_bytes:
                raise AdapterFailure("cleanup resume handoff changed bytes")
            handoff_sha = hashlib.sha256(handoff).hexdigest()
            started_wall = self.clock.wall_time()
            started_monotonic = self.clock.monotonic()
            if (
                self._campaign_deadline_monotonic is not None
                and started_monotonic <= self._campaign_deadline_monotonic
            ):
                cleanup_deadline = self._campaign_deadline_monotonic
            else:
                self._cleanup_started_after_campaign_deadline = (
                    self._campaign_deadline_monotonic is not None
                )
                reserve_seconds = (
                    execution.campaign.empirical_cleanup_reserve_seconds
                    if execution is not None
                    else 0
                )
                cleanup_deadline = checked_deadline(
                    started_monotonic,
                    reserve_seconds,
                    label="cleanup",
                )
            request = CleanupExecutionRequest(
                provider_contract_version=self.contract.version,
                plan_id=self.contract.plan_id,
                host_run_id=self.contract.host_run_id,
                provider_handle=handle,
                transaction_root=self.root,
                held_transaction_root=self.held_transaction_root,
                authorization_reference=(
                    self.authorization_context.external_authorization_reference
                ),
                authorization_source_sha256=(
                    self.authorization_context.external_authorization_source_sha256
                ),
                immutable_handoff_sha256=handoff_sha,
                empirical_prefix=tuple(
                    cast(list[str], state.get("empirical_attempts_entered", []))
                ),
                raw_prefix=tuple(cast(list[str], state.get("raw_attempts_complete", []))),
                owned_instance_name=self.contract.instance_name,
                owned_container_prefix=self.contract.container_prefix,
                started_wall_time=started_wall,
                started_monotonic=started_monotonic,
                cleanup_deadline_monotonic=cleanup_deadline,
            )
            if isinstance(self.authority, ValidatedLiveEffectAuthority):
                cleanup_binding = dict(
                    self.low_level_effects.metadata_authorization_binding(contract=self.contract)
                )
                self.authority.assert_phase_binding(
                    reference=cast(str, cleanup_binding.get("authorization_reference")),
                    source_sha256=cast(
                        str,
                        cleanup_binding.get("authorization_source_sha256"),
                    ),
                    allow_root_path_mismatch=self._root_identity_mismatch,
                )
                if (
                    request.authorization_reference
                    != self.authority.external_authorization_reference
                    or request.authorization_source_sha256
                    != self.authority.external_authorization_source_sha256
                ):
                    raise AdapterFailure("cleanup authority differs from the live transaction")
                self._primitive("validate_unified_live_authority:cleanup")
            with self._campaign_writer_scope(cleanup=True):
                commit, tree = self._source_identity()
                # The child receives writable outputs, not the whole source/input
                # closure. Historical local effects do not use this child bridge.
                output_roots: tuple[str, ...] = (str(self.root),)
                if self.source_inputs is not None:
                    slot = handle.launch_ordinal if handle is not None else 1
                    remote_root = self.root / f"offline-remote-{slot}"
                    declared = [
                        remote_root / "phases",
                        remote_root / self.contract.control_root_name,
                        self.root
                        / "control-private"
                        / f"campaign-slot-{slot:02d}"
                        / "preflight-cleanup-state",
                        self.root / "retained-phase-traces",
                    ]
                    if execution is not None:
                        declared.extend(
                            remote_root / Path(attempt.raw_output_root).parent
                            for attempt in execution.attempts
                        )
                    output_roots = tuple(sorted({str(path) for path in declared}))
                output_authority = CleanupOutputAuthority(
                    CleanupOutputBinding(
                        self.contract.plan_id,
                        self.contract.host_run_id,
                        commit,
                        tree,
                        self.source_inputs.digest if self.source_inputs is not None else None,
                        str(self.root),
                        handoff_sha,
                        self._cleanup_calls,
                        output_roots=output_roots,
                    ),
                    deadline=cleanup_deadline,
                    monotonic=self.clock.monotonic,
                )
                try:
                    receipt = self.low_level_effects.cleanup_transaction(
                        replace(request, output_authority=output_authority)
                    )
                finally:
                    output_authority.close()
            returned_wall = self.clock.wall_time()
            returned_monotonic = self.clock.monotonic()
            if (
                receipt.immutable_handoff_sha256 != handoff_sha
                or not receipt.owned_containers_absent
                or receipt.exact_secret_matches != 0
                or not receipt.remote_secret_removed
                or not receipt.firewall_restored
                or not receipt.rulesets_restored
                or receipt.started_wall_time != started_wall
                or receipt.started_monotonic != started_monotonic
                or receipt.completed_wall_time < started_wall
                or receipt.completed_wall_time > returned_wall
                or receipt.completed_monotonic < started_monotonic
                or receipt.completed_monotonic > returned_monotonic
                or receipt.completed_monotonic > cleanup_deadline
                or receipt.receipt_sha256 != self._cleanup_receipt_identity(receipt)
            ):
                raise AdapterFailure("cleanup receipt did not reach exact zero/security state")
        except CleanupInterrupted:
            interrupted = True
            self._record(operation, subject, "interrupted-resumable")
            raise
        except BaseException as exc:
            if isinstance(self.authority, ValidatedLiveEffectAuthority):
                with suppress(ValueError):
                    self.authority.terminal_failed_nonreplayable()
            self._record(operation, subject, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"retained cleanup handler failed: {exc}") from exc
        finally:
            # The bounded controller continuation still needs its exact held
            # credential for retained closeout. Final release covers an abandoned
            # continuation; no replacement credential or renewed grant is minted.
            if not interrupted:
                self._destroy_secret_file(self._dotenv)
        self._cleanup_receipt = receipt
        self._primitive("immutable_cleanup_export_handoff")
        self._primitive("validate_cleanup_execution_receipt")
        self._record(operation, subject, "passed")
        return receipt.receipt_sha256

    @staticmethod
    def _privacy_findings_for_bytes(
        host: ModuleType,
        *,
        relative: str,
        encoded: bytes,
        role: Literal["retained-source", "shared-evidence"] = "shared-evidence",
    ) -> list[str]:
        """Scan source bytes and public-envelope structure as distinct roles.

        Validated original runtime evidence may contain its retained mount argv.
        It remains private source, not a newly publishable shared failure envelope.
        Credential/network checks apply to both roles without exclusions.
        """
        if role not in {"retained-source", "shared-evidence"}:
            raise AdapterFailure("artifact privacy role is not declared")
        findings: list[str] = []
        text = encoded.decode("utf-8", errors="ignore")
        for label, matcher in (
            ("jupyter-url", host._JUPYTER_URL),
            ("credential-pattern", host._CREDENTIAL_TEXT),
        ):
            if matcher.search(text):
                findings.append(f"{relative}:{label}")
        if host._private_network_values(text):
            findings.append(f"{relative}:private-network")
        if relative.endswith(".json") and len(encoded) <= host.MAX_PRIVACY_JSON_BYTES:
            try:
                value: object = json.loads(encoded)
            except (UnicodeError, json.JSONDecodeError):
                value = None
            if value is not None and host._sensitive_json_paths(value):
                findings.append(f"{relative}:sensitive-json-field")
            if value is not None and "essential-failure" in PurePosixPath(relative).parts:
                try:
                    ProductionCategory3World._reject_private_failure_structure(
                        value,
                        label=relative,
                        reject_absolute_paths=role == "shared-evidence",
                    )
                except AdapterFailure:
                    findings.append(f"{relative}:private-structure")
        elif relative.endswith(".jsonl"):
            for raw_line in encoded.splitlines():
                if len(raw_line) > host.MAX_PRIVACY_LINE_BYTES:
                    continue
                try:
                    value = json.loads(raw_line)
                except (UnicodeError, json.JSONDecodeError):
                    continue
                if host._sensitive_json_paths(value):
                    findings.append(f"{relative}:sensitive-json-field")
                    break
        return findings

    def _held_tree_privacy_findings(
        self,
        host: ModuleType,
        *,
        relative_root: str,
    ) -> list[str]:
        """Scan one subtree through the held root, never its pathname."""

        findings: list[str] = []
        entry_count = 0

        def visit(directory_fd: int, prefix: str) -> None:
            nonlocal entry_count
            with os.scandir(directory_fd) as entries:
                for entry in sorted(entries, key=lambda item: item.name):
                    entry_count += 1
                    if entry_count > 100_000:
                        findings.append("control-public:entry-cap-exceeded")
                        return
                    relative = f"{prefix}/{entry.name}" if prefix else entry.name
                    metadata_value = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(metadata_value.st_mode):
                        findings.append(f"{relative}:symlink")
                        continue
                    if stat.S_ISDIR(metadata_value.st_mode):
                        child = os.open(
                            entry.name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=directory_fd,
                        )
                        try:
                            visit(child, relative)
                        finally:
                            os.close(child)
                        continue
                    if not stat.S_ISREG(metadata_value.st_mode):
                        findings.append(f"{relative}:nonregular")
                        continue
                    descriptor = os.open(
                        entry.name,
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                        dir_fd=directory_fd,
                    )
                    try:
                        observed = os.fstat(descriptor)
                        if (
                            observed.st_dev != metadata_value.st_dev
                            or observed.st_ino != metadata_value.st_ino
                            or observed.st_uid != os.getuid()
                            or observed.st_nlink != 1
                        ):
                            findings.append(f"{relative}:unsafe-identity")
                            continue
                        chunks: list[bytes] = []
                        offset = 0
                        while True:
                            chunk = os.pread(descriptor, 1_048_576, offset)
                            if not chunk:
                                break
                            chunks.append(chunk)
                            offset += len(chunk)
                        encoded = b"".join(chunks)
                    finally:
                        os.close(descriptor)
                    findings.extend(
                        self._privacy_findings_for_bytes(
                            host,
                            relative=relative,
                            encoded=encoded,
                        )
                    )

        try:
            public_fd = self.held_transaction_root.open_relative_no_follow(
                relative_root,
                flags=os.O_RDONLY | os.O_DIRECTORY,
            )
        except (OSError, ValueError):
            return [f"{relative_root}:held-root-unavailable"]
        try:
            visit(public_fd, relative_root)
        finally:
            os.close(public_fd)
        return findings

    def _held_evidence_privacy_findings(self, host: ModuleType) -> list[str]:
        """Scan every held raw/finalized/failure member through its descriptor."""

        findings: list[str] = []
        seen: set[tuple[int, int, str]] = set()
        for groups, role in (
            (self._raw_artifacts, "retained-source"),
            (self._finalized_artifacts, "shared-evidence"),
            (self._essential_failure_artifacts, "shared-evidence"),
            (self._condition_bridge_artifacts, "shared-evidence"),
        ):
            for artifacts in groups.values():
                for artifact in artifacts:
                    identity = (artifact.device, artifact.inode, role)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    try:
                        artifact.revalidate(allow_root_path_mismatch=True)
                    except ValueError:
                        findings.append(f"{artifact.relative_path}:held-identity-changed")
                        continue
                    findings.extend(
                        self._privacy_findings_for_bytes(
                            host,
                            relative=artifact.relative_path,
                            encoded=artifact.read_bytes(),
                            role=cast(Literal["retained-source", "shared-evidence"], role),
                        )
                    )
        return findings

    def scan_privacy(self) -> str:
        operation = "evidence.scan_privacy"
        self._begin(operation, "effect-evidence")
        receipt = self._cleanup_receipt
        host = _host_module(self.repository)
        findings: list[str] = []
        if receipt is None:
            findings.append("cleanup receipt missing")
        else:
            findings.extend(receipt.structural_privacy_findings)
            if receipt.exact_secret_matches != 0:
                findings.append("exact credential material retained")
        findings.extend(
            self._held_tree_privacy_findings(
                host,
                relative_root=self.public_root.relative_to(self.root).as_posix(),
            )
        )
        for relative_root in sorted(self._essential_failure_roots):
            findings.extend(self._held_tree_privacy_findings(host, relative_root=relative_root))
        findings.extend(self._held_evidence_privacy_findings(host))
        self._primitive("privacy_violations:held-descriptor")
        if findings:
            self._record(operation, "effect-evidence", "finding")
            raise StructuralPrivacyFinding("retained structural privacy scanner found a violation")
        assert receipt is not None
        if self._root_identity_mismatch:
            self._record(operation, "effect-evidence", "path-identity-unresolved")
            raise PrivacyUnresolved(
                "held-root privacy scan completed but the original path identity changed"
            )
        self._record(operation, "effect-evidence", "passed")
        return _identity({"privacy": "clean", "cleanup": receipt.receipt_sha256})

    def terminalize_authority(self, *, complete: bool) -> Mapping[str, object]:
        """Guarantee one terminal live-authority receipt before descriptor release."""

        if not isinstance(self.authority, ValidatedLiveEffectAuthority):
            return {
                "terminal_state": "shadow-only",
                "single_use": False,
                "contains_private_overlay_contents": False,
            }
        terminal_complete = (
            complete and self._authority_launch_consumed and not self._root_identity_mismatch
        )
        if terminal_complete:
            self.authority.terminal_complete()
        else:
            self.authority.terminal_failed_nonreplayable(
                allow_root_path_mismatch=self._root_identity_mismatch
            )
        self._primitive("publish_live_authority_consumption_receipt")
        return self._public_authority_consumption(
            self.authority.consumption_receipt(
                allow_root_path_mismatch=self._root_identity_mismatch
            )
        )

    @staticmethod
    def _public_authority_consumption(
        private_receipt: Mapping[str, object],
    ) -> dict[str, object]:
        """Project a terminal proof without private-root-derived hash values."""

        return {
            "authorization_reference": private_receipt.get("authorization_reference"),
            "authorization_source_sha256_validated": True,
            "authorization_context_validated": True,
            "transaction_root_identity_validated": True,
            "terminal_state": private_receipt.get("terminal_state"),
            "single_use": private_receipt.get("single_use"),
            "replay_permitted": private_receipt.get("replay_permitted"),
            "contains_private_overlay_contents": private_receipt.get(
                "contains_private_overlay_contents"
            ),
            "private_runtime_identity_values_retained": False,
        }

    def control_evidence(self) -> Mapping[str, object]:
        lower_cost = self._aggregate_observed_usage.cost_usd
        upper_cost = self._aggregate_usage.cost_usd
        non_live = (
            self.authorization_context.execution_mode
            is EffectExecutionMode.DETERMINISTIC_NO_NETWORK
        )
        budget = self._runtime_budget
        return {
            "implementation_flavor": ImplementationFlavor.PRODUCTION_WRAPPER.value,
            "effect_protocol_version": EFFECT_PROTOCOL_VERSION,
            "effect_authority": self.authority.kind.value,
            "authority_source": self.authority.source,
            "authority_consumption": (
                self._public_authority_consumption(
                    self.authority.consumption_receipt(
                        allow_root_path_mismatch=self._root_identity_mismatch
                    )
                )
                if isinstance(self.authority, ValidatedLiveEffectAuthority)
                else {
                    "terminal_state": "shadow-only",
                    "single_use": False,
                    "contains_private_overlay_contents": False,
                }
            ),
            "held_transaction_root": self.held_transaction_root.to_public_document(),
            "authorization_context_semantic_sha256": (
                self.authorization_context.public_semantic_sha256
            ),
            "effect_implementation": (
                self.authorization_context.effect_implementation.to_document()
            ),
            "production_primitives": sorted(set(self._primitive_calls)),
            "resolved_consumers": {
                name: (resolution.handler_id if resolution is not None else "not-applicable")
                for name, resolution in sorted(self._consumer_resolutions.items())
            },
            "package_budget": (
                None
                if budget is None
                else {
                    "plan_sha256": budget.plan_sha256,
                    "command_package_sha256": budget.command_package_sha256,
                    "execution_contract_sha256": budget.execution_contract_sha256,
                    "attempt_order": list(budget.attempt_order),
                    "model_revision": budget.model_revision,
                    "service_tier": budget.service_tier,
                    "zero_retry": budget.zero_retry,
                    "aggregate_caps": _caps_document(budget.aggregate_caps),
                    "condition_caps": {
                        run_id: _caps_document(caps)
                        for run_id, caps in budget.condition_caps.items()
                    },
                    "condition_plan_sha256s": {
                        attempt.run_id: attempt.condition_plan_sha256
                        for attempt in cast(
                            pilot.PilotExecutionContract,
                            self._execution_contract,
                        ).attempts
                    },
                }
            ),
            "accounting": {
                "authority": "ProviderBudgetBoundary-real-time-event-observer",
                "conditions": dict(self._accounting),
                "aggregate_observed_cost_usd": lower_cost,
                "aggregate_charged_upper_cost_usd": upper_cost,
                "projected_real_cost_usd": 0.0 if non_live else upper_cost,
                "fake_usage": non_live,
                "zero_retries": True,
                "unique_call_ids": len(self._seen_call_ids),
            },
            "runtime_clock": {
                "wall_samples": list(self.clock.wall_samples),
                "monotonic_samples": list(self.clock.monotonic_samples),
                "sleep_calls": list(self.clock.sleep_calls),
                "domains_separate": True,
            },
            "evaluations": dict(self._evaluations),
            "first_pair_checkpoint": self._checkpoint_document,
            "provider_cost_receipt": (
                None if self._provider_cost_receipt is None else asdict(self._provider_cost_receipt)
            ),
            "provider_lifecycle_cost_proof": (
                None
                if self._provider_lifecycle_cost_proof is None
                else asdict(self._provider_lifecycle_cost_proof)
            ),
            "essential_failures": {
                run_id: {
                    "failure_class": outcome.failure_class.value,
                    "manifest_sha256": next(
                        artifact.sha256
                        for artifact in self._essential_failure_artifacts[run_id]
                        if artifact.path == outcome.essential_manifest_path
                    ),
                    "receipt_sha256": next(
                        artifact.sha256
                        for artifact in self._essential_failure_artifacts[run_id]
                        if artifact.path == outcome.essential_receipt_path
                    ),
                    "file_count": outcome.essential_file_count,
                    "total_bytes": outcome.essential_total_bytes,
                    "unknown_call_ids": list(outcome.unknown_call_ids),
                    "process_exit_code": outcome.process_exit_code,
                    "completed": outcome.completed,
                    "unscored": True,
                    "retry_count": outcome.retry_count,
                    "export_receipt_sha256": self._essential_failure_exports[run_id].receipt_sha256,
                    "export_resumed": self._essential_failure_exports[run_id].resumed,
                    "held_artifact_binding_sha256": (
                        self._essential_failure_artifact_bindings[run_id]
                    ),
                }
                for run_id, outcome in self._condition_failures.items()
            },
            "held_evidence": {
                "raw": dict(self._raw_artifact_bindings),
                "finalized": dict(self._finalized_artifact_bindings),
                "essential_failure": dict(self._essential_failure_artifact_bindings),
                "condition_bridge": dict(self._condition_bridge_bindings),
                "revalidated_across_consumers": True,
            },
            "package_assembly": self._package_assembly_evidence,
            "host_transfers": {
                str(ordinal): {
                    "receipt_sha256": receipt.receipt_sha256,
                    "archive_sha256": receipt.remote_archive_sha256,
                    "member_manifest_sha256": receipt.remote_member_manifest_sha256,
                    "host_acknowledgement_sha256": receipt.host_acknowledgement_sha256,
                }
                for ordinal, receipt in sorted(self._host_transfers.items())
            },
            "host_receipts": {
                "qualification": (
                    self._qualification.receipt_sha256 if self._qualification is not None else None
                ),
                "frozen_manifest": (
                    self._freeze.manifest_sha256 if self._freeze is not None else None
                ),
                "postfreeze_validation": (
                    self._freeze.postfreeze_validation_sha256 if self._freeze is not None else None
                ),
            },
            "replacement_history": {
                "closed_launch_slots": list(self._closed_launch_slots),
                "normalization_handler": (
                    provider._normalize_provider_entry_replacement_authority.__name__
                ),
                "termination_failures": self._termination_failures,
            },
            "raw_export_acknowledgements": dict(self._raw_export_acknowledgements),
            "cleanup_handoff_sha256": (
                hashlib.sha256(self._cleanup_handoff_bytes).hexdigest()
                if self._cleanup_handoff_bytes is not None
                else None
            ),
            "cleanup_resume_byte_identical": self._cleanup_handoff_bytes is not None,
            "cleanup_receipt_sha256": (
                self._cleanup_receipt.receipt_sha256 if self._cleanup_receipt is not None else None
            ),
            "cleanup_used_held_root_after_path_mismatch": (
                self._root_identity_mismatch and self._cleanup_receipt is not None
            ),
        }

    def release_resources(self) -> None:
        """Release descriptors only after terminal evidence has been materialized."""

        if self._resources_released:
            return
        failures: list[BaseException] = []
        try:
            self._destroy_secret_file(self._dotenv)
        except BaseException as exc:
            failures.append(exc)
        artifact_groups = (
            self._raw_artifacts,
            self._finalized_artifacts,
            self._essential_failure_artifacts,
            self._condition_bridge_artifacts,
        )
        for groups in artifact_groups:
            for artifacts in groups.values():
                for artifact in artifacts:
                    try:
                        artifact.close()
                    except BaseException as exc:  # finish releasing every independent hold
                        failures.append(exc)
        if isinstance(self.authority, ValidatedLiveEffectAuthority):
            try:
                self.authority.close()
            except BaseException as exc:
                failures.append(exc)
        if self.held_effect_source is not None:
            try:
                self.held_effect_source.close()
            except BaseException as exc:
                failures.append(exc)
        if self._local_assembly_artifact is not None:
            try:
                self._local_assembly_artifact.close()
            except BaseException as exc:
                failures.append(exc)
        if self._local_assembly_verification_artifact is not None:
            try:
                self._local_assembly_verification_artifact.close()
            except BaseException as exc:
                failures.append(exc)
        try:
            self.held_transaction_root.close()
        except BaseException as exc:
            failures.append(exc)
        self._resources_released = True
        if failures:
            raise AdapterFailure(
                "one or more held descriptors could not be released"
            ) from failures[0]


def build_production_adapter_assembly(
    repository: Path,
    contract: T09ProviderContract,
    *,
    low_level_effects: LowLevelEffects,
    authorization_context: EffectAuthorizationContext,
    authority: EffectAuthorityGrant,
    held_transaction_root: HeldTransactionRoot,
    held_effect_source: HeldEffectSource | None = None,
    source_inputs: CandidateSourceSnapshot | None = None,
) -> ProductionCategory3World:
    """Build the sole production assembly after exact package/grant validation."""

    root = repository.resolve(strict=True)
    commit, tree = (
        _git_identity(root) if source_inputs is None else source_inputs.package_identity(root)
    )
    command_sha = (
        contract.expected_command_manifest_sha256
        if source_inputs is None
        else source_inputs.command_package_sha256(root)
    )
    if (
        source_inputs is not None
        and authorization_context.authority_kind is not EffectAuthorityKind.SHADOW_ONLY
    ):
        raise ValueError("candidate source inputs cannot bind live effect authority")
    expected_transaction_root_identity = (
        held_transaction_root.semantic_sha256
        if authorization_context.authority_kind is EffectAuthorityKind.LIVE_AUTHORIZED
        else held_transaction_root.public_attestation_semantic_sha256
    )
    if (
        command_sha is None
        or authorization_context.control_commit != commit
        or authorization_context.control_tree != tree
        or authorization_context.provider_contract_version != contract.version
        or authorization_context.plan_id != contract.plan_id
        or authorization_context.plan_path != contract.plan_path
        or authorization_context.plan_bytes != contract.expected_plan_bytes
        or authorization_context.plan_sha256 != contract.expected_plan_sha256
        or authorization_context.command_package_sha256 != command_sha
        or authorization_context.candidate_source_binding_sha256
        != (None if source_inputs is None else source_inputs.digest)
        or authorization_context.effect_implementation
        != low_level_effects.implementation_identity()
        or authorization_context.transaction_root_identity != expected_transaction_root_identity
        or authorization_context.cost_limits.preflight_provider_cost_usd
        != contract.preflight_lambda_cost_cap_usd
        or authorization_context.cost_limits.campaign_provider_cost_usd
        != contract.campaign_lambda_cost_cap_usd
        or authorization_context.cost_limits.campaign_openai_cost_usd
        != contract.campaign_openai_cost_cap_usd
        or authorization_context.cost_limits.campaign_aggregate_cost_usd
        != contract.campaign_aggregate_cost_cap_usd
        or authorization_context.cost_limits.prior_t09_cost_usd != contract.prior_t09_cost_usd
        or authorization_context.cost_limits.cumulative_t09_cost_usd
        != contract.cumulative_t09_cost_cap_usd
        or authorization_context.zero_retry is not True
        or authorization_context.interpretation != "descriptive-calibration-only"
        or authorization_context.campaign_count != 1
        or low_level_effects.provider_contract_version != contract.version
        or low_level_effects.effect_protocol_version != EFFECT_PROTOCOL_VERSION
        or authority.kind is not authorization_context.authority_kind
        or not authority.authorizes(authorization_context)
    ):
        raise ValueError("effect authority does not bind the exact control/package context")
    held_transaction_root.revalidate()
    if low_level_effects.transaction_root() != held_transaction_root.path:
        raise ValueError("effect transaction root is not the shared-held directory")
    if authorization_context.authority_kind is EffectAuthorityKind.LIVE_AUTHORIZED and (
        not isinstance(authority, ValidatedLiveEffectAuthority)
        or authority.held_transaction_root is not held_transaction_root
        or held_effect_source is None
        or held_effect_source.identity != authorization_context.effect_implementation
    ):
        raise ValueError("live effect authority is not an opaque validator product")
    if held_effect_source is not None:
        held_effect_source.revalidate(root)
    probe_production_adapter_assembly(root, contract, source_inputs=source_inputs)
    return ProductionCategory3World(
        root,
        contract,
        low_level_effects=low_level_effects,
        authorization_context=authorization_context,
        authority=authority,
        held_transaction_root=held_transaction_root,
        held_effect_source=held_effect_source,
        source_inputs=source_inputs,
    )


__all__ = [
    "ProductionCategory3World",
    "build_production_adapter_assembly",
    "probe_production_adapter_assembly",
]
