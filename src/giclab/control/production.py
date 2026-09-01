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
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path, PurePosixPath
from types import MappingProxyType, ModuleType
from typing import Final, cast

import yaml

from giclab.control.adapters import (
    AdapterCall,
    AdapterFailure,
    AmbiguousProviderOutcome,
    Category3Adapters,
    CleanupInterrupted,
    ImplementationFlavor,
    MetadataEnvelope,
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
    CleanupExecutionReceipt,
    CleanupExecutionRequest,
    ConditionAction,
    ConditionAmbiguousSend,
    ConditionEventObserver,
    ConditionExecutionRequest,
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
    HostPreflightReceipt,
    HostPreflightRejected,
    HostPreflightRequest,
    HostQualificationReceipt,
    HostQualificationRequest,
    LowLevelEffects,
    PackageRuntimeBudget,
    PackageStageReceipt,
    PackageStageRequest,
    ProviderHandle,
    RuntimeClock,
    ScientificFreezeReceipt,
    ScientificFreezeRequest,
    TrackedPackageMember,
    checked_deadline,
    finite_time,
    validate_package_effect_registration,
)
from giclab.control.registry_validation import resolve_registered_command_package
from giclab.harness import t09_model_metadata_receipt as metadata
from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness import t09_sira_pilot as pilot
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
from giclab.harness.t09_provider_contracts import T09ProviderContract
from giclab.registry import load_json

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


def _safe_existing_file(root: Path, path: Path, *, label: str) -> Path:
    approved = root.resolve(strict=True)
    candidate = path.resolve(strict=True)
    if approved not in candidate.parents or candidate.is_symlink() or not candidate.is_file():
        raise AdapterFailure(f"{label} is outside its exact effect transaction root")
    metadata_value = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata_value.st_mode) or metadata_value.st_nlink != 1:
        raise AdapterFailure(f"{label} is not a single-link regular file")
    return candidate


def _safe_directory(root: Path, path: Path, *, label: str) -> Path:
    approved = root.resolve(strict=True)
    candidate = path.resolve(strict=True)
    if (
        (candidate != approved and approved not in candidate.parents)
        or candidate.is_symlink()
        or not candidate.is_dir()
    ):
        raise AdapterFailure(f"{label} is outside its exact effect transaction root")
    return candidate


def _require_sha(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise AdapterFailure(f"{label} is not an exact SHA-256")
    return value


def _caps_document(caps: ProviderBudgetCaps) -> dict[str, int | float]:
    return cast(dict[str, int | float], asdict(caps))


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
) -> dict[str, object]:
    """Prove every production consumer and low-level channel is explicit."""

    resolutions = resolve_control_consumers(
        repository,
        contract,
        consumers=_RUNTIME_CONSUMERS,
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
            "stage_package",
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
        self.output_total_bytes: int | None = None
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

    def model_call(self, event: ConditionModelCall, send: ConditionSend) -> str:
        self._assert_campaign_open()
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
            call_id=event.call_id,
            logical_call_id=event.logical_call_id,
            classify_failure=self._disposition,
        )

    def browser_action(self, *, action_id: str, perform: ConditionAction) -> None:
        self._assert_campaign_open()
        if _SAFE_ID.fullmatch(action_id) is None or action_id in self.action_ids:
            raise AdapterFailure("condition browser-action identity was reused or malformed")
        self.action_ids.add(action_id)
        self.action_order.append(action_id)
        self.boundary.record_browser_action(before_action=perform)

    def output_bytes(self, *, total_bytes: int) -> None:
        self._assert_campaign_open()
        if self.output_total_bytes is not None or type(total_bytes) is not int or total_bytes < 0:
            raise AdapterFailure("condition output-byte event is duplicate or malformed")
        self.boundary.record_output_bytes(total_bytes)
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
    ) -> None:
        self.repository = repository.resolve(strict=True)
        self.contract = contract
        self.low_level_effects = low_level_effects
        self.authorization_context = authorization_context
        self.authority = authority
        self.clock = _ValidatedRuntimeClock(low_level_effects.runtime_clock())
        self.root = low_level_effects.transaction_root().resolve(strict=True)
        if self.root.is_symlink() or stat.S_IMODE(self.root.stat().st_mode) & 0o022:
            raise ValueError("effect transaction root is symlinked or group/world writable")
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
        self._stage_receipt: PackageStageReceipt | None = None
        self._qualification: HostQualificationReceipt | None = None
        self._freeze: ScientificFreezeReceipt | None = None
        self._condition_outcomes: dict[str, ConditionProcessOutcome] = {}
        self._finalizations: dict[str, FinalizerExecutionOutcome] = {}
        self._accounting: dict[str, dict[str, object]] = {}
        self._aggregate_usage = ProviderBudgetUsage()
        self._aggregate_observed_usage = ProviderBudgetUsage()
        self._evaluations: dict[str, dict[str, object]] = {}
        self._raw_export_acknowledgements: dict[str, str] = {}
        self._cleanup_handoff_bytes: bytes | None = None
        self._cleanup_receipt: CleanupExecutionReceipt | None = None
        self._cleanup_calls = 0
        self._cleanup_started_after_campaign_deadline = False
        self._stage_evidence: dict[str, object] | None = None
        self._condition_started_wall: dict[str, float] = {}
        self._condition_started_monotonic: dict[str, float] = {}
        self._campaign_started_monotonic: float | None = None
        self._campaign_deadline_monotonic: float | None = None
        self._seen_call_ids: set[str] = set()
        self._seen_logical_call_ids: set[str] = set()
        self._consumer_resolutions = resolve_control_consumers(
            self.repository,
            contract,
            consumers=_RUNTIME_CONSUMERS,
        )

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
            "host.stage": 1,
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
        commit, tree = _git_identity(self.repository)
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
            or any(
                _HEX64.fullmatch(value) is None
                for value in (source_sha, price_sha, deprecation_sha)
                if isinstance(value, str)
            )
            or not all(isinstance(value, str) for value in (source_sha, price_sha, deprecation_sha))
            or binding.get("authorized") is not True
            or binding.get("single_use") is not True
        ):
            self._record(operation, contract_version, "failed")
            raise AdapterFailure("metadata authorization binding is incomplete")
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
                authorization_source_sha256=cast(str, source_sha),
                authorization_overlay_sha256=overlay_sha,
                public_price_contract_sha256=cast(str, price_sha),
                public_deprecation_observation_sha256=cast(str, deprecation_sha),
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
            commit, _tree = _git_identity(self.repository)
            try:
                with self.low_level_effects.campaign_scope():
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
            commit, _tree = _git_identity(self.repository)
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
        members: list[TrackedPackageMember] = []
        for relative in sorted(paths):
            if not isinstance(relative, str):
                raise AdapterFailure("tracked package path is missing")
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
                raise AdapterFailure("tracked package path is unsafe")
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
    def _stage_receipt_identity(receipt: PackageStageReceipt) -> str:
        return _identity(
            {
                "provider_contract_version": receipt.provider_contract_version,
                "plan_id": receipt.plan_id,
                "plan_sha256": receipt.plan_sha256,
                "command_package_sha256": receipt.command_package_sha256,
                "execution_contract_sha256": receipt.execution_contract_sha256,
                "evidence_stage_id": receipt.evidence_stage_id,
                "host_run_id": receipt.host_run_id,
                "archive_sha256": receipt.archive_sha256,
                "archive_bytes": receipt.archive_bytes,
                "members": [member.to_document() for member in receipt.members],
                "source_commit": receipt.source_commit,
                "source_tree": receipt.source_tree,
                "host_acknowledgement_sha256": receipt.host_acknowledgement_sha256,
                "host_rehash_sha256": receipt.host_rehash_sha256,
                "uploaded": receipt.uploaded,
            }
        )

    def _validate_archive(
        self,
        receipt: PackageStageReceipt,
        expected: tuple[TrackedPackageMember, ...],
    ) -> None:
        archive = _safe_existing_file(
            self.root,
            receipt.archive_path,
            label="staged package archive",
        )
        if (
            archive.stat().st_size != receipt.archive_bytes
            or receipt.archive_bytes > _MAX_STAGE_ARCHIVE_BYTES
            or _file_sha256(archive) != receipt.archive_sha256
            or receipt.host_rehash_sha256 != receipt.archive_sha256
            or receipt.members != expected
            or receipt.receipt_sha256 != self._stage_receipt_identity(receipt)
        ):
            raise AdapterFailure("staged package receipt identity drifted")
        _require_sha(receipt.host_acknowledgement_sha256, label="host stage acknowledgement")
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
            raise AdapterFailure("staged archive bytes differ from tracked package closure")

    def stage(self) -> str:
        operation = "host.stage"
        self._begin(operation, "tracked-package-archive")
        try:
            members, source = self._load_runtime_package()
            assert self._runtime_budget is not None
            commit, tree = _git_identity(self.repository)
            request = PackageStageRequest(
                repository=self.repository,
                control_commit=commit,
                control_tree=tree,
                provider_contract_version=self.contract.version,
                plan_id=self.contract.plan_id,
                plan_sha256=self.contract.expected_plan_sha256,
                command_package_sha256=self._runtime_budget.command_package_sha256,
                execution_contract_sha256=self._runtime_budget.execution_contract_sha256,
                evidence_stage_id=self.contract.evidence_stage_id,
                host_run_id=self.contract.host_run_id,
                members=members,
                max_archive_bytes=_MAX_STAGE_ARCHIVE_BYTES,
                max_member_bytes=_MAX_STAGE_MEMBER_BYTES,
                max_members=_MAX_STAGE_MEMBERS,
            )
            receipt = self.low_level_effects.stage_package(request)
            if (
                receipt.provider_contract_version != request.provider_contract_version
                or receipt.plan_id != request.plan_id
                or receipt.plan_sha256 != request.plan_sha256
                or receipt.command_package_sha256 != request.command_package_sha256
                or receipt.execution_contract_sha256 != request.execution_contract_sha256
                or receipt.evidence_stage_id != request.evidence_stage_id
                or receipt.host_run_id != request.host_run_id
                or receipt.source_commit != commit
                or receipt.source_tree != tree
                or receipt.archive_sha256 != receipt.host_rehash_sha256
            ):
                raise AdapterFailure("staged package source or host rehash drifted")
            self._validate_archive(receipt, members)
            accepted = self.private_root / "accepted-package.tar"
            host = _host_module(self.repository)
            staged = host.stage_verified_archive(
                receipt.archive_path,
                accepted,
                receipt.archive_bytes,
                receipt.archive_sha256,
            )
            if (
                staged.get("sha256") != receipt.archive_sha256
                or _file_sha256(accepted) != receipt.archive_sha256
            ):
                raise AdapterFailure("accepted staged archive changed bytes")
        except BaseException as exc:
            self._record(operation, "tracked-package-archive", "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"tracked package staging failed: {exc}") from exc
        self._stage_receipt = receipt
        self._stage_evidence = {
            "command_package_sha256": self._runtime_budget.command_package_sha256,
            "execution_contract_sha256": self._runtime_budget.execution_contract_sha256,
            "plan_sha256": self._runtime_budget.plan_sha256,
            "package_source": source,
            "archive_sha256": receipt.archive_sha256,
            "archive_bytes": receipt.archive_bytes,
            "archive_member_count": len(receipt.members),
            "host_acknowledgement_sha256": receipt.host_acknowledgement_sha256,
            "host_rehash_sha256": receipt.host_rehash_sha256,
            "tracked_only": True,
        }
        self._primitive("resolve_registered_command_package")
        self._primitive("load_execution_contract")
        self._primitive("stage_verified_archive")
        self._primitive("validate_tracked_package_archive")
        self._record(operation, "tracked-package-archive", "passed")
        return receipt.receipt_sha256

    @staticmethod
    def _preflight_receipt_identity(receipt: HostPreflightReceipt) -> str:
        return _identity(
            {
                "provider_contract_version": receipt.provider_contract_version,
                "plan_id": receipt.plan_id,
                "host_run_id": receipt.host_run_id,
                "provider_handle_identity": receipt.provider_handle_identity,
                "provider_launch_ordinal": receipt.provider_launch_ordinal,
                "provider_entry_receipt_sha256": receipt.provider_entry_receipt_sha256,
                "metadata_receipt_sha256": receipt.metadata_receipt_sha256,
                "stage_receipt_sha256": receipt.stage_receipt_sha256,
                "remote_path_qualification_sha256": (receipt.remote_path_qualification_sha256),
                "started_wall_time": receipt.started_wall_time,
                "completed_wall_time": receipt.completed_wall_time,
                "started_monotonic": receipt.started_monotonic,
                "completed_monotonic": receipt.completed_monotonic,
            }
        )

    def _close_rejected_preflight(
        self,
        handle: ProviderHandle,
        rejection: HostPreflightRejected,
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
        commit, _tree = _git_identity(self.repository)
        with self.low_level_effects.campaign_scope():
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
            or self._stage_receipt is None
            or self._execution_contract is None
        ):
            raise AdapterFailure("host preflight lacks staged package and metadata authority")
        entry_path = self._entry_receipts.get(handle.launch_ordinal)
        if entry_path is None:
            raise AdapterFailure("host preflight lacks the retained provider-entry receipt")
        entry_sha = _file_sha256(entry_path)
        metadata_sha = metadata.model_metadata_receipt_sha256(self._metadata_receipt)
        requested_wall = self.clock.wall_time()
        requested_mono = self.clock.monotonic()
        request = HostPreflightRequest(
            provider_contract_version=self.contract.version,
            plan_id=self.contract.plan_id,
            host_run_id=self.contract.host_run_id,
            provider_handle=handle,
            campaign_private_root=self._campaign_roots[handle.launch_ordinal],
            provider_entry_receipt_path=entry_path,
            provider_entry_receipt_sha256=entry_sha,
            metadata_receipt_path=self._metadata_receipt,
            metadata_receipt_sha256=metadata_sha,
            stage_receipt_sha256=self._stage_receipt.receipt_sha256,
            remote_root=self.contract.remote_root,
            requested_wall_time=requested_wall,
            requested_monotonic=requested_mono,
        )
        try:
            receipt = self.low_level_effects.preflight_host(request)
        except HostPreflightRejected as exc:
            try:
                self._close_rejected_preflight(handle, exc)
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
                receipt.provider_contract_version != request.provider_contract_version
                or receipt.plan_id != request.plan_id
                or receipt.host_run_id != request.host_run_id
                or receipt.provider_handle_identity != handle.opaque_identity
                or receipt.provider_launch_ordinal != handle.launch_ordinal
                or receipt.provider_entry_receipt_sha256 != entry_sha
                or receipt.metadata_receipt_sha256 != metadata_sha
                or receipt.stage_receipt_sha256 != self._stage_receipt.receipt_sha256
                or start_wall < requested_wall
                or start_mono < requested_mono
                or end_wall > returned_wall
                or end_mono > returned_mono
                or end_wall < start_wall
                or end_mono < start_mono
                or end_mono - start_mono
                > self._execution_contract.campaign.preflight_iteration_wall_seconds
                or receipt.receipt_sha256 != self._preflight_receipt_identity(receipt)
            ):
                raise AdapterFailure("host preflight receipt identity or timing drifted")
            _require_sha(
                receipt.remote_path_qualification_sha256,
                label="remote path qualification",
            )
            commit, _tree = _git_identity(self.repository)
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
            )
        except BaseException as exc:
            self._record(operation, handle.opaque_identity, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"host preflight receipt validation failed: {exc}") from exc
        self._primitive("validate_model_metadata_receipt_offline")
        self._primitive("validate_host_preflight_receipt")
        self._record(operation, handle.opaque_identity, "passed")

    @staticmethod
    def _qualification_receipt_identity(receipt: HostQualificationReceipt) -> str:
        values = asdict(receipt)
        values.pop("receipt_sha256")
        return _identity(values)

    def qualify(self, handle: ProviderHandle) -> str:
        operation = "host.qualify"
        self._begin(operation, handle.opaque_identity)
        if self._stage_receipt is None:
            raise AdapterFailure("host qualification lacks its staged package")
        entry_path = self._entry_receipts.get(handle.launch_ordinal)
        if entry_path is None:
            raise AdapterFailure("host qualification lacks provider-entry evidence")
        if (
            self.contract.replacement_image_tag is None
            or self.contract.image_materialization_policy is None
            or self.contract.active_image_qualification_id is None
            or self.contract.local_finalizer_qualification_id is None
        ):
            raise AdapterFailure("selected package lacks host qualification identities")
        request = HostQualificationRequest(
            provider_contract_version=self.contract.version,
            plan_id=self.contract.plan_id,
            host_run_id=self.contract.host_run_id,
            provider_handle=handle,
            provider_entry_receipt_sha256=_file_sha256(entry_path),
            stage_receipt_sha256=self._stage_receipt.receipt_sha256,
            replacement_image_tag=self.contract.replacement_image_tag,
            image_materialization_policy=self.contract.image_materialization_policy,
            active_image_qualification_id=self.contract.active_image_qualification_id,
            local_finalizer_qualification_id=(self.contract.local_finalizer_qualification_id),
        )
        try:
            receipt = self.low_level_effects.qualify_host(request)
            commit, _tree = _git_identity(self.repository)
            host = _host_module(self.repository)
            source_bindings = host.validate_finalizer_source(
                repository=self.repository,
                package_commit=commit,
                finalizer_commit=commit,
                source=self.repository / host.FINALIZER_RELATIVE_PATH,
                projection_source=(self.repository / host.FINALIZER_PROJECTION_RELATIVE_PATH),
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
            )
            if (
                receipt.provider_contract_version != request.provider_contract_version
                or receipt.plan_id != request.plan_id
                or receipt.host_run_id != request.host_run_id
                or receipt.provider_handle_identity != handle.opaque_identity
                or receipt.provider_launch_ordinal != handle.launch_ordinal
                or receipt.provider_entry_receipt_sha256 != request.provider_entry_receipt_sha256
                or receipt.stage_receipt_sha256 != request.stage_receipt_sha256
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
                "manifest_sha256": receipt.manifest_sha256,
                "postfreeze_validation_sha256": receipt.postfreeze_validation_sha256,
                "started_wall_time": receipt.started_wall_time,
                "completed_wall_time": receipt.completed_wall_time,
                "started_monotonic": receipt.started_monotonic,
                "completed_monotonic": receipt.completed_monotonic,
            }
        )

    def freeze(self, handle: ProviderHandle) -> str:
        operation = "host.freeze"
        self._begin(operation, handle.opaque_identity)
        if (
            self._execution_contract is None
            or self._stage_receipt is None
            or self._qualification is None
            or self._command_package_sha256 is None
            or self.contract.frozen_run_manifest_id is None
        ):
            raise AdapterFailure("scientific freeze lacks its exact qualified package")
        entry = self._entry_receipts.get(handle.launch_ordinal)
        if entry is None:
            raise AdapterFailure("scientific freeze lacks provider-entry evidence")
        started_wall = self.clock.wall_time()
        started_mono = self.clock.monotonic()
        request = ScientificFreezeRequest(
            provider_contract_version=self.contract.version,
            plan_id=self.contract.plan_id,
            host_run_id=self.contract.host_run_id,
            frozen_manifest_id=self.contract.frozen_run_manifest_id,
            provider_entry_receipt_sha256=_file_sha256(entry),
            stage_receipt_sha256=self._stage_receipt.receipt_sha256,
            command_package_sha256=self._command_package_sha256,
            execution_contract_sha256=self._execution_contract.sha256,
            qualification_receipt_sha256=self._qualification.receipt_sha256,
            image_digest=self._qualification.image_digest,
            manifest_root=self.root,
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
            manifest = load_json(manifest_path)
            validation = load_json(validation_path)
            end_wall = finite_time(receipt.completed_wall_time, label="freeze completion wall")
            end_mono = finite_time(receipt.completed_monotonic, label="freeze completion monotonic")
            expected_manifest = {
                "schema_version": "1.0.0",
                "provider_contract_version": self.contract.version,
                "plan_id": self.contract.plan_id,
                "host_run_id": self.contract.host_run_id,
                "frozen_manifest_id": self.contract.frozen_run_manifest_id,
                "provider_entry_receipt_sha256": _file_sha256(entry),
                "stage_receipt_sha256": self._stage_receipt.receipt_sha256,
                "command_package_sha256": self._command_package_sha256,
                "execution_contract_sha256": self._execution_contract.sha256,
                "qualification_receipt_sha256": self._qualification.receipt_sha256,
                "image_digest": self._qualification.image_digest,
                "frozen_at_wall_time": receipt.completed_wall_time,
            }
            expected_validation = {
                "schema_version": "1.0.0",
                "provider_contract_version": self.contract.version,
                "plan_id": self.contract.plan_id,
                "host_run_id": self.contract.host_run_id,
                "frozen_manifest_sha256": receipt.manifest_sha256,
                "validated_at_wall_time": receipt.completed_wall_time,
                "postfreeze_valid": True,
            }
            if (
                receipt.started_wall_time != started_wall
                or receipt.started_monotonic != started_mono
                or end_wall < started_wall
                or end_mono < started_mono
                or end_wall > returned_wall
                or end_mono > returned_mono
                or manifest != expected_manifest
                or validation != expected_validation
                or _file_sha256(manifest_path) != receipt.manifest_sha256
                or _file_sha256(validation_path) != receipt.postfreeze_validation_sha256
                or receipt.receipt_sha256 != self._freeze_receipt_identity(receipt)
            ):
                raise AdapterFailure("scientific freeze receipts drifted")
            pilot.initialize_pilot_state(
                self._pilot_state,
                provider_contract=self.contract,
                execution_contract_sha256=self._execution_contract.sha256,
                pilot_started_at_epoch=started_wall,
                lambda_started_at_epoch=started_wall,
            )
        except BaseException as exc:
            self._record(operation, handle.opaque_identity, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"scientific freeze failed: {exc}") from exc
        self._freeze = receipt
        self._campaign_started_monotonic = end_mono
        self._campaign_deadline_monotonic = checked_deadline(
            end_mono,
            self._execution_contract.campaign.empirical_campaign_wall_seconds,
            label="empirical campaign",
        )
        self._primitive("publish_dynamic_frozen_run_manifest")
        self._primitive("validate_postfreeze_receipt")
        self._primitive("initialize_pilot_state")
        self._record(operation, handle.opaque_identity, "passed")
        return receipt.receipt_sha256

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
            pilot.reserve_condition_start(
                self._pilot_state,
                execution_contract_sha256=execution.sha256,
                run_id=run_id,
                start_intent_sha256=start_intent,
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
            pilot.mark_empirical_entry(
                self._pilot_state,
                execution_contract_sha256=execution.sha256,
                run_id=run_id,
                supervised_release_receipt_sha256=release,
            )
        except BaseException as exc:
            self._record(operation, run_id, "failed")
            raise AdapterFailure(f"empirical entry failed: {exc}") from exc
        self._condition_started_wall[run_id] = released_at
        self._condition_started_monotonic[run_id] = released_monotonic
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
        document = observer.boundary.accounting_document()
        self._accounting[run_id] = document
        self._aggregate_usage = observer.boundary.aggregate_usage
        self._aggregate_observed_usage = observer.boundary.aggregate_observed_usage
        self._seen_call_ids.update(observer.call_ids)
        self._seen_logical_call_ids.update(observer.logical_call_ids)

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
            package_commit=_git_identity(self.repository)[0],
            transaction_root=self.root,
            condition_started_wall_time=self._condition_started_wall[run_id],
            condition_started_monotonic=self._condition_started_monotonic[run_id],
            campaign_deadline_monotonic=self._campaign_deadline_monotonic,
        )
        boundary = ProviderBudgetBoundary(
            routing=ImmutableModelRouting.locked(),
            aggregate_caps=self._runtime_budget.aggregate_caps,
            condition_caps=caps,
            monotonic=self.clock.monotonic,
            initial_aggregate_usage=self._aggregate_usage,
            initial_aggregate_observed_usage=self._aggregate_observed_usage,
        )
        observer = _AccountingObserver(
            run_id=run_id,
            model_revision=request.model_revision,
            service_tier=request.service_tier,
            boundary=boundary,
            prior_call_ids=frozenset(self._seen_call_ids),
            prior_logical_call_ids=frozenset(self._seen_logical_call_ids),
            clock=self.clock,
            campaign_deadline_monotonic=self._campaign_deadline_monotonic,
        )
        started = self.clock.monotonic()
        if started < request.condition_started_monotonic:
            raise AdapterFailure("condition monotonic start moved backward")
        try:
            outcome = self.low_level_effects.execute_condition(
                request,
                observer=observer,
            )
            completed = self.clock.monotonic()
            if (
                completed > self._campaign_deadline_monotonic
                or completed - started > caps.max_wall_seconds
            ):
                raise ProviderBudgetExceeded("condition wall budget exceeded")
            expected_raw = (self.root / attempt.raw_output_root).resolve()
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
            call_ledger = _safe_existing_file(
                raw_root,
                outcome.call_ledger_path,
                label="condition call ledger",
            )
            browser_ledger = _safe_existing_file(
                raw_root,
                outcome.browser_ledger_path,
                label="condition browser ledger",
            )
            completion_path = _safe_existing_file(
                raw_root,
                outcome.completion_path,
                label="condition completion evidence",
            )
            process_outcome_path = _safe_existing_file(
                raw_root,
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
                or call_ledger.parent != raw_root
                or browser_ledger.parent != raw_root
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
            if outcome.exit_code == 0 and not outcome.completed:
                raise AdapterFailure("successful condition process did not complete")
        except BaseException as exc:
            self._record_boundary_state(run_id, observer)
            self._primitive("ProviderBudgetBoundary.invoke")
            outcome_name = (
                "admission-stopped"
                if isinstance(exc, ProviderBudgetExceeded)
                else "unknown"
                if boundary.unknown_outcomes
                else "failed"
            )
            self._record(operation, run_id, outcome_name)
            if isinstance(exc, AdapterFailure):
                raise
            if isinstance(exc, ProviderBudgetExceeded):
                raise AdapterFailure(
                    "cost/token/action/output/wall admission stopped condition"
                ) from exc
            raise AdapterFailure(f"condition session stopped: {type(exc).__name__}: {exc}") from exc
        self._condition_outcomes[run_id] = outcome
        self._record_boundary_state(run_id, observer)
        self._primitive("ProviderBudgetBoundary.invoke")
        self._primitive("ProviderBudgetBoundary.record_browser_action")
        self._primitive("ProviderBudgetBoundary.record_output_bytes")
        self._primitive("execute_typed_condition_session")
        self._record(operation, run_id, "passed")
        return _identity(
            {
                "run_id": run_id,
                "raw_manifest_sha256": _file_sha256(outcome.raw_manifest_path),
                "raw_receipt_sha256": _file_sha256(outcome.raw_receipt_path),
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
        outcome = self._condition_outcomes.get(run_id)
        if outcome is None:
            raise AdapterFailure("raw export lacks its accepted condition outcome")
        manifest_sha = _file_sha256(outcome.raw_manifest_path)
        receipt_sha = _file_sha256(outcome.raw_receipt_path)
        try:
            host = _host_module(self.repository)
            manifest, receipt = host.validate_raw_attempt_seal(
                attempt_root=outcome.raw_root.parent,
                raw_root=outcome.raw_root,
                run_id=run_id,
                package_commit=_git_identity(self.repository)[0],
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
            exported.write_bytes(_canonical_bytes(export_document))
            exported.chmod(0o600)
            if load_json(exported) != export_document:
                raise AdapterFailure("off-host raw acknowledgement changed bytes")
            pilot.mark_raw_attempt_complete(
                self._pilot_state,
                execution_contract_sha256=execution.sha256,
                run_id=run_id,
                raw_manifest_sha256=manifest_sha,
                raw_receipt_sha256=receipt_sha,
            )
        except BaseException as exc:
            self._record(operation, run_id, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"retained raw validation/export failed: {exc}") from exc
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
                "infrastructure_valid": outcome.infrastructure_valid,
            }
        )

    def finalize(self, run_id: str) -> str:
        operation = "condition.finalize"
        self._begin(operation, run_id)
        execution = self._require_execution()
        raw = self._condition_outcomes.get(run_id)
        qualification = self._qualification
        if raw is None or qualification is None:
            raise AdapterFailure("finalizer lacks raw or qualification authority")
        attempt = execution.attempt(run_id)
        manifest_sha = _file_sha256(raw.raw_manifest_path)
        receipt_sha = _file_sha256(raw.raw_receipt_path)
        expected_finalized = (self.root / attempt.finalized_output_root).resolve()
        host = _host_module(self.repository)
        request = FinalizerExecutionRequest(
            run_id=run_id,
            evaluator_run_id=self.contract.evaluator_run_ids[self.contract.run_ids.index(run_id)],
            execution_mode="qualified-local",
            runtime_qualification_id=qualification.local_finalizer_qualification_id,
            runtime_qualification_sha256=(qualification.local_finalizer_qualification_sha256),
            raw_root=raw.raw_root,
            raw_manifest_path=raw.raw_manifest_path,
            raw_receipt_path=raw.raw_receipt_path,
            raw_manifest_sha256=manifest_sha,
            raw_receipt_sha256=receipt_sha,
            raw_completion_path=raw.completion_path,
            raw_completion_sha256=_file_sha256(raw.completion_path),
            process_outcome_path=raw.process_outcome_path,
            process_outcome_sha256=_file_sha256(raw.process_outcome_path),
            raw_output_root=attempt.raw_output_root,
            finalized_root=expected_finalized,
            finalized_output_root=attempt.finalized_output_root,
            finalizer_source_sha256=qualification.finalizer_source_sha256,
            finalizer_projection_source_sha256=(qualification.finalizer_projection_source_sha256),
            finalizer_selector_sha256=qualification.finalizer_selector_sha256,
            finalizer_schema_sha256=qualification.finalizer_schema_sha256,
            interpreter=qualification.local_finalizer_interpreter,
            interpreter_sha256=qualification.local_finalizer_interpreter_sha256,
            dependency_manifest_sha256=(qualification.local_finalizer_dependency_manifest_sha256),
            dependency_tree_sha256=(qualification.local_finalizer_dependency_tree_sha256),
            evaluator_dependency_tree_sha256=(qualification.local_evaluator_dependency_tree_sha256),
            evaluator_contract_sha256=execution.evaluator_contract_sha256,
            package_commit=_git_identity(self.repository)[0],
        )
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
            outcome = self.low_level_effects.finalize_condition(request)
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
            )
        except BaseException as exc:
            self._record(operation, run_id, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"typed infrastructure-invalid finalizer failure: {exc}") from exc
        self._finalizations[run_id] = outcome
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
        finalized = self._finalizations.get(run_id)
        if finalized is None or not finalized.infrastructure_valid:
            self._record(operation, run_id, "failed")
            raise AdapterFailure("infrastructure-invalid finalization remains unscored")
        attempt = execution.attempt(run_id)
        request = EvaluatorExecutionRequest(
            run_id=run_id,
            evaluator_run_id=self.contract.evaluator_run_ids[self.contract.run_ids.index(run_id)],
            task_id=attempt.task_id,
            task_index=attempt.task_index,
            finalized_root=finalized.finalized_root,
            session_paths=finalized.session_paths,
            evaluator_contract_path=execution.evaluator_contract_path,
            evaluator_contract_sha256=execution.evaluator_contract_sha256,
            package_commit=_git_identity(self.repository)[0],
        )
        try:
            outcome = self.low_level_effects.evaluate_condition(request)
            session_hashes = tuple(_file_sha256(path) for path in request.session_paths)
            if (
                outcome.run_id != run_id
                or outcome.evaluator_run_id != request.evaluator_run_id
                or outcome.consumed_finalized_root.resolve() != request.finalized_root.resolve()
                or outcome.consumed_session_sha256s != session_hashes
                or outcome.evaluator_contract_sha256 != execution.evaluator_contract_sha256
                or outcome.receipt_sha256 != self._evaluator_outcome_identity(outcome)
                or outcome.infrastructure_failure
                or outcome.missing_required_evidence
                or not outcome.evaluator_valid
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
            self._record(operation, run_id, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"pinned evaluator failed: {exc}") from exc
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

    def checkpoint(self, *, name: str) -> str:
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
            decided_monotonic, _remaining = self._campaign_remaining()
            first_monotonic = self._condition_started_monotonic.get(self.contract.run_ids[0])
            if (
                first_monotonic is None
                or decided < first_started
                or decided_monotonic - first_monotonic > execution.limits.max_pair_wall_seconds
            ):
                raise AdapterFailure("first-pair checkpoint exceeded its package wall cap")
            decision = {
                "decision": "continue-to-task-b",
                "first_pair_started_at_epoch": first_started,
                "second_pair_started_at_epoch": decided,
                "decided_at_epoch": decided,
            }
            pilot.record_first_pair_checkpoint(
                self._pilot_state,
                execution_contract_sha256=execution.sha256,
                decision=decision,
                decided_at_epoch=decided,
            )
        except BaseException as exc:
            self._record(operation, name, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"first-pair checkpoint failed: {exc}") from exc
        self._primitive("record_first_pair_checkpoint")
        self._record(operation, name, "passed")
        return _identity(decision)

    @staticmethod
    def _cleanup_receipt_identity(receipt: CleanupExecutionReceipt) -> str:
        values = asdict(receipt)
        values.pop("receipt_sha256")
        return _identity(values)

    @staticmethod
    def _destroy_secret_file(path: Path) -> None:
        if not path.is_file() or path.is_symlink():
            return
        try:
            size = path.stat(follow_symlinks=False).st_size
            with path.open("r+b", buffering=0) as handle:
                handle.write(b"\x00" * size)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            path.unlink(missing_ok=True)

    def cleanup(self, handle: ProviderHandle | None) -> str:
        operation = "host.cleanup"
        subject = handle.opaque_identity if handle is not None else "no-known-instance"
        self._begin(operation, subject)
        self._cleanup_calls += 1
        execution = self._execution_contract
        try:
            if execution is not None and self._pilot_state.is_file():
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
            receipt = self.low_level_effects.cleanup_transaction(request)
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
            self._record(operation, subject, "interrupted-resumable")
            raise
        except BaseException as exc:
            self._record(operation, subject, "failed")
            if isinstance(exc, AdapterFailure):
                raise
            raise AdapterFailure(f"retained cleanup handler failed: {exc}") from exc
        finally:
            self._destroy_secret_file(self._dotenv)
        self._cleanup_receipt = receipt
        self._primitive("immutable_cleanup_export_handoff")
        self._primitive("validate_cleanup_execution_receipt")
        self._record(operation, subject, "passed")
        return receipt.receipt_sha256

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
        findings.extend(str(value) for value in host.privacy_violations(self.public_root))
        for outcome in self._condition_outcomes.values():
            findings.extend(str(value) for value in host.privacy_violations(outcome.raw_root))
        self._primitive("privacy_violations")
        if findings:
            self._record(operation, "effect-evidence", "finding")
            raise StructuralPrivacyFinding("retained structural privacy scanner found a violation")
        assert receipt is not None
        self._record(operation, "effect-evidence", "passed")
        return _identity({"privacy": "clean", "cleanup": receipt.receipt_sha256})

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
            "authorization_context_semantic_sha256": (self.authorization_context.semantic_sha256),
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
            "package_staging": self._stage_evidence,
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
        }


def build_production_adapter_assembly(
    repository: Path,
    contract: T09ProviderContract,
    *,
    low_level_effects: LowLevelEffects,
    authorization_context: EffectAuthorizationContext,
    authority: EffectAuthorityGrant,
) -> ProductionCategory3World:
    """Build the sole production assembly after exact package/grant validation."""

    root = repository.resolve(strict=True)
    commit, tree = _git_identity(root)
    command_sha = contract.expected_command_manifest_sha256
    if (
        command_sha is None
        or authorization_context.control_commit != commit
        or authorization_context.control_tree != tree
        or authorization_context.provider_contract_version != contract.version
        or authorization_context.plan_id != contract.plan_id
        or authorization_context.plan_sha256 != contract.expected_plan_sha256
        or authorization_context.command_package_sha256 != command_sha
        or authorization_context.effect_implementation
        != low_level_effects.implementation_identity()
        or authorization_context.transaction_root_identity
        != low_level_effects.transaction_root_identity()
        or low_level_effects.provider_contract_version != contract.version
        or low_level_effects.effect_protocol_version != EFFECT_PROTOCOL_VERSION
        or authority.kind is not authorization_context.authority_kind
        or not authority.authorizes(authorization_context)
    ):
        raise ValueError("effect authority does not bind the exact control/package context")
    transaction_root = low_level_effects.transaction_root().resolve(strict=True)
    registered_identity = validate_package_effect_registration(root, contract)
    if (
        transaction_root.is_symlink()
        or not transaction_root.is_dir()
        or stat.S_IMODE(transaction_root.stat().st_mode) & 0o022
    ):
        raise ValueError("effect transaction root is not a private exact directory")
    if (
        authorization_context.authority_kind is EffectAuthorityKind.LIVE_AUTHORIZED
        and registered_identity != authorization_context.effect_implementation
    ):
        raise ValueError("live effect authority does not bind the registered package factory")
    probe_production_adapter_assembly(root, contract)
    return ProductionCategory3World(
        root,
        contract,
        low_level_effects=low_level_effects,
        authorization_context=authorization_context,
        authority=authority,
    )


__all__ = [
    "ProductionCategory3World",
    "build_production_adapter_assembly",
    "probe_production_adapter_assembly",
]
