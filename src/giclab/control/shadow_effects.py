"""Deterministic, network-disabled effects for the production Category 3 assembly.

All test credentials, provider response fixtures, synthetic package hosts, canned
benchmark answers, fake time, and fault injection live below the shared production
effect boundary in this module.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from contextlib import AbstractContextManager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, cast

from giclab.control.adapters import AdapterFailure, CleanupInterrupted
from giclab.control.effects import (
    EFFECT_PROTOCOL_VERSION,
    CleanupExecutionReceipt,
    CleanupExecutionRequest,
    ConditionAmbiguousSend,
    ConditionEventObserver,
    ConditionExecutionRequest,
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
    EffectAuthorityGrant,
    EffectAuthorityKind,
    EffectAuthorizationContext,
    EffectAuthorizationLimits,
    EffectExecutionMode,
    EffectImplementationIdentity,
    EvaluatorExecutionOutcome,
    EvaluatorExecutionRequest,
    FinalizerExecutionOutcome,
    FinalizerExecutionRequest,
    HeldTransactionRoot,
    HostPreflightReceipt,
    HostPreflightRejected,
    HostPreflightRequest,
    HostQualificationReceipt,
    HostQualificationRequest,
    LowLevelEffects,
    ModelMetadataChannel,
    PackageStageReceipt,
    PackageStageRequest,
    ProviderCostObservationRequest,
    ProviderCostReceipt,
    ProviderHandle,
    RuntimeClock,
    ScientificFreezeReceipt,
    ScientificFreezeRequest,
    ValidatedLiveEffectAuthority,
    hold_transaction_root,
    mint_shadow_effect_authority,
    repository_effect_identity,
)
from giclab.control.production import (
    ProductionCategory3World,
    _host_module,
    build_production_adapter_assembly,
)
from giclab.control.proofs import ValidatedShadowRehearsal
from giclab.harness import t09_model_metadata_receipt as metadata
from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness import t09_sira_pilot as pilot
from giclab.harness.sira_gate_a import ModelRole, ProviderRequest, ProviderResponseUsage
from giclab.harness.t09_cleanup_state import CleanupTargetState, EarlyCleanupJournal
from giclab.harness.t09_provider_contracts import T09ProviderContract

_FACTORY_ENTRY_POINT: Final = "build_deterministic_effects"


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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_identity(repository: Path) -> tuple[str, str]:
    environment = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    values: list[str] = []
    for revision in ("HEAD", "HEAD^{tree}"):
        completed = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", revision],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
            timeout=10,
        )
        values.append(completed.stdout.decode("ascii").strip())
    return values[0], values[1]


@dataclass(frozen=True, slots=True)
class ShadowFaultPlan:
    """One deterministic test-only fault schedule."""

    name: str
    fail_operation: str | None = None
    fail_occurrence: int = 1
    metadata_expires_before_launch: bool = False
    ambiguous_inventory_after_launch: bool = False
    termination_failure_count: int = 0
    cleanup_interruption_count: int = 0
    answer_overrides: tuple[str, str] | None = None
    model_input_tokens_over_cap: bool = False
    model_cost_over_cap: bool = False
    browser_actions_over_cap: bool = False
    output_bytes_over_cap: bool = False
    condition_wall_over_cap: bool = False
    failure_export_interruption_count: int = 0
    essential_target_bytes: int | None = None
    essential_artifact_fault: str | None = None
    essential_envelope_fault: str | None = None
    mutate_essential_during_export: bool = False
    evaluator_unscored_run_index: int | None = None
    evaluator_invalid_run_index: int | None = None
    task_a_zero_scores: bool = False
    checkpoint_missing_raw_after_task_a: bool = False
    held_identity_fault: str | None = None
    root_replacement_before_cleanup: bool = False
    provider_cost_receipt_fault: str | None = None
    provider_lifecycle_source_fault: str | None = None


class DeterministicRuntimeClock(RuntimeClock):
    """Explicit fake time source used only by deterministic effects."""

    def __init__(self, *, fixed_tick: int) -> None:
        if type(fixed_tick) is not int or fixed_tick < 0:
            raise ValueError("deterministic clock seed must be a non-negative integer")
        self._monotonic = float(fixed_tick)
        self._wall = 1_800_000_000.0 + float(fixed_tick)
        self.sleep_durations: list[float] = []

    def monotonic(self) -> float:
        return self._monotonic

    def wall_time(self) -> float:
        return self._wall

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("deterministic clock cannot sleep backward")
        self.sleep_durations.append(seconds)
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        self._monotonic += seconds
        self._wall += seconds


class _DeterministicMetadataChannel(ModelMetadataChannel):
    def __init__(
        self,
        *,
        expected_credential_sha256: str,
        clock: DeterministicRuntimeClock,
    ) -> None:
        self._expected_credential_sha256 = expected_credential_sha256
        self._clock = clock
        self.request_count = 0
        self.credential_identity_sha256: str | None = None
        self.started_at: float | None = None

    def get_model_metadata(
        self,
        *,
        model_id: str,
        credential: bytearray,
        started_at: float,
    ) -> metadata.ModelMetadataResponse:
        self.request_count += 1
        observed = hashlib.sha256(bytes(credential)).hexdigest()
        self.credential_identity_sha256 = observed
        self.started_at = started_at
        if (
            self.request_count != 1
            or model_id != metadata.MODEL_METADATA_MODEL_ID
            or observed != self._expected_credential_sha256
        ):
            raise metadata.ModelMetadataReceiptError(
                "deterministic metadata channel rejected credential or request identity"
            )
        body = _canonical_bytes({"id": model_id})
        return metadata.ModelMetadataResponse(
            status=200,
            body=body,
            response_completed_at=self._clock.wall_time(),
        )


@dataclass(slots=True)
class _QueuedProviderTransport:
    responses: list[object]
    effects: DeterministicLowLevelEffects
    clock: RuntimeClock
    launch_ordinal: int
    launched_handle: ProviderHandle | None = None

    def send(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        credential: bytearray,
    ) -> provider.ProviderResponse:
        del body
        if (
            hashlib.sha256(bytes(credential)).hexdigest() != self.effects.provider_credential_sha256
            or not self.responses
        ):
            raise RuntimeError("deterministic provider channel rejected request identity")
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        if method == "POST" and path == "/api/v1/instance-operations/launch":
            self.launched_handle = self.effects.provider_launch(launch_ordinal=self.launch_ordinal)
        if (
            method == "POST"
            and path == "/api/v1/instance-operations/terminate"
            and self.launched_handle is not None
        ):
            self.effects.provider_terminate(self.launched_handle)
        if (
            method == "GET"
            and path == "/api/v1/instances"
            and self.launched_handle is not None
            and isinstance(value, dict)
            and value.get("data") == []
        ):
            self.effects.provider_terminate(self.launched_handle)
        status = 200
        if isinstance(value, tuple):
            status, value = value
        encoded = value if isinstance(value, bytes) else json.dumps(value).encode()
        return provider.ProviderResponse(
            status=int(status),
            content_type="application/json",
            body=encoded,
            received_at_epoch=self.clock.wall_time(),
        )


def _provider_instance(
    contract: T09ProviderContract,
    launch_ordinal: int,
    *,
    status: str,
) -> dict[str, object]:
    return {
        "id": f"deterministic-instance-{launch_ordinal}",
        "name": contract.instance_name,
        "hostname": contract.instance_name,
        "instance_type": {"name": provider.INSTANCE_TYPE},
        "region": {"name": provider.REGION},
        "status": status,
        "ip": f"198.51.100.{launch_ordinal + 20}",
        "file_system_names": [],
    }


def _global_firewall(public_ipv4: str) -> dict[str, object]:
    return {
        "data": {
            "id": "global",
            "name": "global",
            "workspace_id": "deterministic-workspace",
            "rules": [
                {
                    "protocol": "tcp",
                    "port_range": [22, 22],
                    "source_network": f"{public_ipv4}/32",
                    "description": "deterministic-network-disabled-fixture",
                }
            ],
        }
    }


def _launch_responses(
    contract: T09ProviderContract,
    launch_ordinal: int,
    *,
    provider_entry_failure: bool,
    public_key: str,
    public_ipv4: str,
) -> list[object]:
    prefix: list[object] = [
        {
            "data": {
                provider.INSTANCE_TYPE: {
                    "instance_type": {
                        "name": provider.INSTANCE_TYPE,
                        "price_cents_per_hour": provider.PRICE_CENTS_PER_HOUR,
                    },
                    "regions_with_capacity_available": [{"name": provider.REGION}],
                }
            }
        },
        {
            "data": [
                {
                    "id": provider.IMAGE_ID,
                    "region": {"name": provider.REGION},
                    "family": "lambda-stack-22-04",
                }
            ]
        },
        {"data": [{"name": provider.SSH_KEY_NAME, "public_key": public_key}]},
        _global_firewall(public_ipv4),
        {"data": []},
        {"data": []},
        {"data": {"instance_ids": [f"deterministic-instance-{launch_ordinal}"]}},
    ]
    if not provider_entry_failure:
        return [
            *prefix,
            {"data": [_provider_instance(contract, launch_ordinal, status="active")]},
        ]
    return [
        *prefix,
        RuntimeError("deterministic active-poll transport failure"),
        RuntimeError("deterministic termination acknowledgement ambiguity"),
        {"data": [_provider_instance(contract, launch_ordinal, status="terminated")]},
        {"data": []},
        _global_firewall(public_ipv4),
        {"data": []},
    ]


class DeterministicLowLevelEffects:
    """Complete no-network implementation of the package effect protocol."""

    effect_protocol_version = EFFECT_PROTOCOL_VERSION

    def __init__(
        self,
        *,
        repository: Path,
        contract: T09ProviderContract,
        fault_plan: ShadowFaultPlan,
        fixed_tick: int,
        transaction_root: Path | None = None,
    ) -> None:
        self.repository = repository.resolve(strict=True)
        self.contract = contract
        self.provider_contract_version = contract.version
        self.fault_plan = fault_plan
        self._clock = DeterministicRuntimeClock(fixed_tick=fixed_tick)
        seed = _identity(
            {
                "purpose": "runtime-created-test-canary",
                "contract": contract.version,
                "fault": fault_plan.name,
                "fixed_tick": fixed_tick,
            }
        )
        if transaction_root is None:
            temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
            self._root = temporary_root / f"giclab-t09-effects-{seed[:32]}"
            if self._root.exists():
                if self._root.is_symlink() or self._root.parent != temporary_root:
                    raise RuntimeError("deterministic effect root is not an exact private path")
                for child in self._root.iterdir():
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            else:
                self._root.mkdir(mode=0o700)
        else:
            self._root = Path(os.path.abspath(transaction_root))
            metadata_value = self._root.stat(follow_symlinks=False)
            if (
                self._root != transaction_root
                or self._root.is_symlink()
                or not stat.S_ISDIR(metadata_value.st_mode)
                or metadata_value.st_uid != os.getuid()
                or stat.S_IMODE(metadata_value.st_mode) & 0o022
            ):
                raise RuntimeError("injected deterministic transaction root is unsafe")
        self._model_seed = f"test-model-canary-{seed[:24]}"
        self._provider_seed = f"test-provider-canary-{seed[24:48]}"
        self.model_credential_sha256 = hashlib.sha256(self._model_seed.encode()).hexdigest()
        self.provider_credential_sha256 = hashlib.sha256(self._provider_seed.encode()).hexdigest()
        self._metadata_channel = _DeterministicMetadataChannel(
            expected_credential_sha256=self.model_credential_sha256,
            clock=self._clock,
        )
        self._active: dict[int, ProviderHandle] = {}
        self._provider_active_started_wall: dict[int, float] = {}
        self._ambiguous_launch = False
        self._inventory_calls = 0
        self._termination_calls = 0
        self._cleanup_calls = 0
        self._failure_export_calls: dict[str, int] = {}
        self._essential_envelope_targets: dict[str, int] = {}
        self._effect_counts: dict[str, int] = {}
        self._public_ipv4 = "203.0.113.71"
        self._public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDeterministicNoNetworkOnly"
        self._image_fixture = self._root / "retained-image.fixture"
        self._image_fixture.write_bytes(b"production-shadow-retained-image-fixture")
        self._image_fixture.chmod(0o600)
        capability_root = self._root / "launch-capabilities"
        capability_root.mkdir(mode=0o700)
        package_commit, _tree = _git_identity(self.repository)
        self._campaign_controls = provider._mint_shadow_campaign_low_level_controls(
            capability_root=capability_root,
            expected_package_commit=package_commit,
            image_fixture=self._image_fixture,
        )
        self._last_answers: dict[str, str] = {}

    def _declared_failure(self, operation: str) -> bool:
        occurrence = self._effect_counts.get(operation, 0) + 1
        self._effect_counts[operation] = occurrence
        return (
            self.fault_plan.fail_operation == operation
            and self.fault_plan.fail_occurrence == occurrence
        )

    def implementation_identity(self) -> EffectImplementationIdentity:
        return repository_effect_identity(
            self.repository / "src/giclab/control/shadow_effects.py",
            repository=self.repository,
            factory=_FACTORY_ENTRY_POINT,
        )

    def runtime_clock(self) -> RuntimeClock:
        return self._clock

    def transaction_root(self) -> Path:
        return self._root

    def read_model_secret(self) -> bytearray:
        return bytearray(self._model_seed.encode())

    def read_provider_secret(self) -> bytearray:
        return bytearray(self._provider_seed.encode())

    def public_ipv4(self) -> str:
        return self._public_ipv4

    def ssh_public_key(self) -> str:
        return self._public_key

    def metadata_channel(self) -> ModelMetadataChannel:
        return self._metadata_channel

    @property
    def metadata_request_count(self) -> int:
        return self._metadata_channel.request_count

    @property
    def metadata_credential_identity_sha256(self) -> str | None:
        return self._metadata_channel.credential_identity_sha256

    def metadata_authorization_binding(
        self,
        *,
        contract: T09ProviderContract,
    ) -> dict[str, object]:
        return {
            "authorization_reference": (f"{contract.authorization_prefix}DETERMINISTIC-CONTROL"),
            "authorization_source_sha256": _identity("deterministic-authority-source"),
            "public_price_contract_sha256": _identity("deterministic-price-source"),
            "public_deprecation_observation_sha256": _identity("deterministic-deprecation-source"),
            "authorized": True,
            "single_use": True,
        }

    def provider_inventory(self) -> tuple[str, ...] | None:
        self._inventory_calls += 1
        if self._inventory_calls == 1 and self.fault_plan.metadata_expires_before_launch:
            self._clock.advance(metadata.MODEL_METADATA_MAX_AGE_SECONDS + 1.0)
        if self._ambiguous_launch and self.fault_plan.ambiguous_inventory_after_launch:
            return None
        return tuple(sorted(handle.opaque_identity for handle in self._active.values()))

    def provider_launch(self, *, launch_ordinal: int) -> ProviderHandle:
        handle = ProviderHandle(
            opaque_identity=f"deterministic-instance-{launch_ordinal}",
            launch_ordinal=launch_ordinal,
        )
        self._active[launch_ordinal] = handle
        self._provider_active_started_wall[launch_ordinal] = self._clock.wall_time()
        return handle

    def provider_entry(self, handle: ProviderHandle) -> None:
        if handle.launch_ordinal not in self._active:
            raise AdapterFailure("deterministic provider entry lacks an active owner")

    def provider_cost_receipt(
        self,
        request: ProviderCostObservationRequest,
    ) -> ProviderCostReceipt:
        handle = self._active.get(request.provider_handle.launch_ordinal)
        started = self._provider_active_started_wall.get(request.provider_handle.launch_ordinal)
        if handle is None or started is None:
            raise AdapterFailure("deterministic provider cost lacks its active owner")
        values = {
            "provider_contract_version": self.contract.version,
            "plan_id": self.contract.plan_id,
            "owned_instance_identity": request.provider_handle.opaque_identity,
            "launch_ordinal": request.provider_handle.launch_ordinal,
            "provider_profile_sha256": request.provider_profile_sha256,
            "provider_price_source_sha256": request.provider_price_source_sha256,
            "active_entry_receipt_sha256": request.active_entry_receipt_sha256,
            "closed_slot_receipt_sha256s": request.closed_slot_receipt_sha256s,
            "hourly_price_usd": request.frozen_hourly_price_usd,
            "active_started_wall_time": request.active_started_wall_time,
            "active_ended_wall_time": None,
            "observed_wall_time": request.observed_wall_time,
            "observed_monotonic": request.observed_monotonic,
            "prior_preflight_cost_usd": request.prior_preflight_cost_usd,
            "current_empirical_cost_usd": request.current_empirical_cost_usd,
            "cumulative_provider_cost_usd": request.cumulative_provider_cost_usd,
            "real_provider_effects": False,
        }
        fault = self.fault_plan.provider_cost_receipt_fault
        if fault == "zero-price":
            values["hourly_price_usd"] = 0.0
        elif fault == "wrong-price":
            values["hourly_price_usd"] = request.frozen_hourly_price_usd + 1.0
        elif fault == "shifted-active-start":
            values["active_started_wall_time"] = request.observed_wall_time
        elif fault == "active-end-before-start":
            values["active_ended_wall_time"] = request.active_started_wall_time - 1.0
        elif fault == "active-end-after-observation":
            values["active_ended_wall_time"] = request.observed_wall_time + 1.0
        elif fault == "wrong-owner":
            values["owned_instance_identity"] = "f" * 64
        elif fault == "wrong-ordinal":
            values["launch_ordinal"] = request.provider_handle.launch_ordinal + 1
        elif fault == "wrong-profile-hash":
            values["provider_profile_sha256"] = "f" * 64
        elif fault == "wrong-price-source-hash":
            values["provider_price_source_sha256"] = "f" * 64
        elif fault == "wrong-entry-hash":
            values["active_entry_receipt_sha256"] = "f" * 64
        elif fault == "omitted-closed-slot":
            values["closed_slot_receipt_sha256s"] = ()
        elif fault == "omitted-preflight-cost":
            values["prior_preflight_cost_usd"] = 0.0
        elif fault == "understated-self-hashed":
            values["current_empirical_cost_usd"] = 0.0
            values["cumulative_provider_cost_usd"] = 0.0
        elif fault == "stale-observation":
            values["observed_wall_time"] = request.observed_wall_time - 60.0
        elif fault == "cross-domain-observation":
            values["observed_monotonic"] = request.observed_wall_time
        return ProviderCostReceipt(
            **values,  # type: ignore[arg-type]
            receipt_sha256=_identity(values),
        )

    def provider_terminate(self, handle: ProviderHandle) -> None:
        self._termination_calls += 1
        if self._termination_calls <= self.fault_plan.termination_failure_count:
            raise RuntimeError("deterministic provider termination outage")
        self._active.pop(handle.launch_ordinal, None)

    def campaign_transport(
        self,
        *,
        contract: T09ProviderContract,
        launch_ordinal: int,
        clock: RuntimeClock,
    ) -> provider.ProviderTransport:
        if self.fault_plan.name == "ambiguous-provider-call-outcome":
            self._ambiguous_launch = True
            raise TimeoutError("deterministic launch acknowledgement unavailable")
        provider_entry_failure = (
            self.fault_plan.name == "provider-entry-replacement" and launch_ordinal == 1
        )
        return _QueuedProviderTransport(
            responses=_launch_responses(
                contract,
                launch_ordinal,
                provider_entry_failure=provider_entry_failure,
                public_key=self._public_key,
                public_ipv4=self._public_ipv4,
            ),
            effects=self,
            clock=clock,
            launch_ordinal=launch_ordinal,
        )

    def campaign_scope(self) -> AbstractContextManager[None]:
        return provider._shadow_campaign_control_scope(self._campaign_controls)

    def campaign_low_level_controls(
        self,
    ) -> provider.ShadowCampaignLowLevelControls | None:
        return self._campaign_controls

    def campaign_closeout_transport(
        self,
        *,
        contract: T09ProviderContract,
        launch_ordinal: int,
        handle: ProviderHandle,
        clock: RuntimeClock,
    ) -> provider.ProviderTransport:
        return _QueuedProviderTransport(
            responses=[
                RuntimeError("deterministic termination acknowledgement ambiguity"),
                {"data": []},
                _global_firewall(self._public_ipv4),
                {"data": []},
            ],
            effects=self,
            clock=clock,
            launch_ordinal=launch_ordinal,
            launched_handle=handle,
        )

    def retained_image_archive(self, *, launch_ordinal: int) -> Path | None:
        del launch_ordinal
        return self._image_fixture

    def stage_package(self, request: PackageStageRequest) -> PackageStageReceipt:
        if self._declared_failure("host.stage"):
            raise AdapterFailure("deterministic package staging failure")
        stage_root = self._root / "package-stage"
        stage_root.mkdir(mode=0o700)
        archive = stage_root / "tracked-package.tar"
        with tarfile.open(archive, mode="w") as handle:
            for member in request.members:
                encoded = (request.repository / member.path).read_bytes()
                if (
                    len(encoded) != member.bytes
                    or hashlib.sha256(encoded).hexdigest() != member.sha256
                ):
                    raise AdapterFailure("deterministic stage observed package byte drift")
                info = tarfile.TarInfo(member.path)
                info.size = len(encoded)
                info.mode = 0o600
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                handle.addfile(info, io.BytesIO(encoded))
        archive.chmod(0o600)
        archive_sha = _file_sha256(archive)
        acknowledgement = _identity(
            {
                "host_run_id": request.host_run_id,
                "evidence_stage_id": request.evidence_stage_id,
                "archive_sha256": archive_sha,
                "member_count": len(request.members),
            }
        )
        document = {
            "provider_contract_version": request.provider_contract_version,
            "plan_id": request.plan_id,
            "plan_sha256": request.plan_sha256,
            "command_package_sha256": request.command_package_sha256,
            "execution_contract_sha256": request.execution_contract_sha256,
            "evidence_stage_id": request.evidence_stage_id,
            "host_run_id": request.host_run_id,
            "archive_sha256": archive_sha,
            "archive_bytes": archive.stat().st_size,
            "members": [member.to_document() for member in request.members],
            "source_commit": request.control_commit,
            "source_tree": request.control_tree,
            "host_acknowledgement_sha256": acknowledgement,
            "host_rehash_sha256": archive_sha,
            "uploaded": False,
        }
        return PackageStageReceipt(
            provider_contract_version=request.provider_contract_version,
            plan_id=request.plan_id,
            plan_sha256=request.plan_sha256,
            command_package_sha256=request.command_package_sha256,
            execution_contract_sha256=request.execution_contract_sha256,
            evidence_stage_id=request.evidence_stage_id,
            host_run_id=request.host_run_id,
            archive_path=archive,
            archive_sha256=archive_sha,
            archive_bytes=archive.stat().st_size,
            members=request.members,
            source_commit=request.control_commit,
            source_tree=request.control_tree,
            host_acknowledgement_sha256=acknowledgement,
            host_rehash_sha256=archive_sha,
            uploaded=False,
            receipt_sha256=_identity(document),
        )

    def _preflight_rejection(
        self,
        request: HostPreflightRequest,
    ) -> HostPreflightRejected:
        entry = json.loads(request.provider_entry_receipt_path.read_bytes())
        started = float(entry["provider_preflight_started_at_epoch"])
        iteration_started = started + 1.0
        failed_at = iteration_started + 1.0
        source = self._root / f"preflight-rejection-{request.provider_handle.launch_ordinal}"
        source.mkdir(mode=0o700)
        commit, _tree = _git_identity(self.repository)
        documents: dict[str, dict[str, object]] = {
            "pilot-state.json": {
                "plan_id": self.contract.plan_id,
                "empirical_attempts_entered": [],
                "nonempirical_infrastructure_attempts_consumed": [],
                "raw_attempts_complete": [],
                "attempts_completed": [],
                "essential_failure_seals": {},
                "core_safety_stop_detected": False,
            },
            "host-cleanup.json": {
                "owned_container_residue": [],
                "global_secret_scan_passed": True,
                "remote_secret_removed": True,
                "core_destruction_verified": True,
                "core_safety_stop_detected": False,
                "credential_rotation_required_due_to_core_handling": False,
            },
            "preflight-failure.json": {
                "plan_id": self.contract.plan_id,
                "host_run_id": self.contract.host_run_id,
                "package_commit": commit,
                "empirical_attempts_entered": 0,
                "preflight_engineering_state": "resumable-same-host",
                "termination_dispatch_required": False,
                "provider_preflight_started_at_epoch": started,
                "preflight_iteration_started_at_epoch": iteration_started,
                "failed_at_epoch": failed_at,
                "preflight_iteration_elapsed_seconds": failed_at - iteration_started,
                "provider_instance_elapsed_seconds": failed_at - started,
                "termination_dispatch_deadline_epoch": None,
            },
            "late-preflight-gate-absence.json": {
                "schema_version": "0.1.0",
                "plan_id": self.contract.plan_id,
                "host_run_id": self.contract.host_run_id,
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
            },
        }
        for name, document in documents.items():
            provider.write_exclusive(source / name, document)
        disposition = {
            "schema_version": "0.1.0",
            "plan_id": self.contract.plan_id,
            "host_run_id": self.contract.host_run_id,
            "package_commit": commit,
            "provider_entry_receipt_sha256": request.provider_entry_receipt_sha256,
            "pilot_state_sha256": provider.file_sha256(source / "pilot-state.json"),
            "host_cleanup_sha256": provider.file_sha256(source / "host-cleanup.json"),
            "preflight_failure_sha256": provider.file_sha256(source / "preflight-failure.json"),
            "late_preflight_gate_absence_sha256": provider.file_sha256(
                source / "late-preflight-gate-absence.json"
            ),
            "preflight_failed_at_epoch": failed_at,
            "provider_preflight_started_at_epoch": started,
            "preflight_iteration_started_at_epoch": iteration_started,
            "preflight_iteration_elapsed_seconds": failed_at - iteration_started,
            "provider_instance_elapsed_seconds": failed_at - started,
            "termination_dispatch_deadline_epoch": None,
            "preflight_engineering_state": "resumable-same-host",
            "empirical_attempts_entered": 0,
            "model_metadata_requests": 0,
            "model_task_requests": 0,
            "task_browser_actions": 0,
            "replacement_image_build_count": 0,
            "replacement_image_import_count": 0,
            "replacement_image_id": None,
            "replacement_image_archive_sha256": None,
            "credentials_removed": True,
            "owned_containers_absent": True,
            "core_safety_stop_detected": False,
            "core_destruction_verified": True,
            "credential_rotation_required_due_to_core_handling": False,
            "replacement_launch_evidence_only": True,
        }
        provider.write_exclusive(source / "preempirical-disposition.json", disposition)
        files = [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": provider.file_sha256(path),
            }
            for path in sorted(source.iterdir())
        ]
        provider.write_exclusive(
            source / "source-manifest.json",
            {
                "schema_version": "0.1.0",
                "plan_id": self.contract.plan_id,
                "host_run_id": self.contract.host_run_id,
                "files": files,
                "total_bytes": sum(path.stat().st_size for path in source.iterdir()),
            },
        )
        continuation = self._root / (f"remote-cleanup-{request.provider_handle.launch_ordinal}")
        shutil.copytree(
            request.campaign_private_root / "preflight-cleanup-state",
            continuation,
        )
        EarlyCleanupJournal(continuation).record_result(
            target_id="temporary-remote-secret",
            result=CleanupTargetState.ABSENT,
            detail_code="temporary-remote-secret-already-absent",
            clock=self._clock.wall_time,
        )
        return HostPreflightRejected(
            "retained host preflight failed",
            disposition_path=source / "preempirical-disposition.json",
            source_root=source,
            remote_cleanup_journal=continuation,
        )

    def preflight_host(self, request: HostPreflightRequest) -> HostPreflightReceipt:
        if self._declared_failure("host.preflight"):
            raise self._preflight_rejection(request)
        started_wall = request.requested_wall_time
        started_mono = request.requested_monotonic
        completed_wall = self._clock.wall_time()
        completed_mono = self._clock.monotonic()
        document = {
            "provider_contract_version": request.provider_contract_version,
            "plan_id": request.plan_id,
            "host_run_id": request.host_run_id,
            "provider_handle_identity": request.provider_handle.opaque_identity,
            "provider_launch_ordinal": request.provider_handle.launch_ordinal,
            "provider_entry_receipt_sha256": request.provider_entry_receipt_sha256,
            "metadata_receipt_sha256": request.metadata_receipt_sha256,
            "stage_receipt_sha256": request.stage_receipt_sha256,
            "remote_path_qualification_sha256": _identity(
                {
                    "remote_root": request.remote_root,
                    "host_run_id": request.host_run_id,
                }
            ),
            "started_wall_time": started_wall,
            "completed_wall_time": completed_wall,
            "started_monotonic": started_mono,
            "completed_monotonic": completed_mono,
        }
        return HostPreflightReceipt(
            provider_contract_version=request.provider_contract_version,
            plan_id=request.plan_id,
            host_run_id=request.host_run_id,
            provider_handle_identity=request.provider_handle.opaque_identity,
            provider_launch_ordinal=request.provider_handle.launch_ordinal,
            provider_entry_receipt_sha256=request.provider_entry_receipt_sha256,
            metadata_receipt_sha256=request.metadata_receipt_sha256,
            stage_receipt_sha256=request.stage_receipt_sha256,
            remote_path_qualification_sha256=cast(
                str,
                document["remote_path_qualification_sha256"],
            ),
            started_wall_time=started_wall,
            completed_wall_time=completed_wall,
            started_monotonic=started_mono,
            completed_monotonic=completed_mono,
            receipt_sha256=_identity(document),
        )

    def qualify_host(
        self,
        request: HostQualificationRequest,
    ) -> HostQualificationReceipt:
        if self._declared_failure("host.qualify"):
            raise AdapterFailure("deterministic host qualification failure")
        host = _host_module(self.repository)
        host_file = getattr(host, "__file__", None)
        if not isinstance(host_file, str):
            raise AdapterFailure("deterministic host module lacks a source path")
        commit, _tree = _git_identity(self.repository)
        role_sources = {
            host.DownstreamSourceRole.SELECTOR: Path(host_file).resolve(strict=True),
            host.DownstreamSourceRole.FINALIZER: (
                self.repository / host.FINALIZER_RELATIVE_PATH
            ).resolve(strict=True),
            host.DownstreamSourceRole.FINALIZER_PROJECTION: (
                self.repository / host.FINALIZER_PROJECTION_RELATIVE_PATH
            ).resolve(strict=True),
            host.DownstreamSourceRole.REFINALIZATION_SCHEMA: (
                self.repository / host.REFINALIZATION_RECEIPT_SCHEMA_RELATIVE_PATH
            ).resolve(strict=True),
        }
        source_bindings = {
            role.value: host.validate_git_bound_downstream_source(
                repository=self.repository,
                commit=commit,
                role=role,
                relative=host.DOWNSTREAM_SOURCE_CONTRACTS[role].relative_path,
                source=path,
            )
            for role, path in role_sources.items()
        }
        source_sha = _file_sha256(role_sources[host.DownstreamSourceRole.FINALIZER])
        projection_sha = _file_sha256(role_sources[host.DownstreamSourceRole.FINALIZER_PROJECTION])
        selector_sha = _file_sha256(role_sources[host.DownstreamSourceRole.SELECTOR])
        schema_sha = _file_sha256(role_sources[host.DownstreamSourceRole.REFINALIZATION_SCHEMA])
        values: dict[str, object] = {
            "provider_contract_version": request.provider_contract_version,
            "plan_id": request.plan_id,
            "host_run_id": request.host_run_id,
            "provider_handle_identity": request.provider_handle.opaque_identity,
            "provider_launch_ordinal": request.provider_handle.launch_ordinal,
            "provider_entry_receipt_sha256": request.provider_entry_receipt_sha256,
            "stage_receipt_sha256": request.stage_receipt_sha256,
            "replacement_image_tag": request.replacement_image_tag,
            "image_materialization_policy": request.image_materialization_policy,
            "qualification_id": request.active_image_qualification_id,
            "local_finalizer_qualification_id": (request.local_finalizer_qualification_id),
            "image_materialization_receipt_sha256": _identity(
                {
                    "image": request.replacement_image_tag,
                    "policy": request.image_materialization_policy,
                }
            ),
            "image_digest": "sha256:" + _identity("deterministic-qualified-image"),
            "python_interpreter": "/opt/sira/.venv/bin/python",
            "python_interpreter_sha256": _identity("deterministic-image-interpreter"),
            "dependency_manifest_sha256": _identity("deterministic-image-dependencies"),
            "dependency_tree_sha256": _identity("deterministic-image-dependency-tree"),
            "browser_qualification_sha256": _identity("deterministic-browser-qualification"),
            "downstream_source_roles_sha256": _identity(source_bindings),
            "finalizer_source_sha256": source_sha,
            "finalizer_projection_source_sha256": projection_sha,
            "finalizer_selector_sha256": selector_sha,
            "finalizer_schema_sha256": schema_sha,
            "local_finalizer_qualification_sha256": _identity(
                "deterministic-local-finalizer-qualification"
            ),
            "local_finalizer_interpreter": "/opt/sira/.venv/bin/python",
            "local_finalizer_interpreter_sha256": _identity("deterministic-local-interpreter"),
            "local_finalizer_dependency_manifest_sha256": _identity(
                "deterministic-local-dependencies"
            ),
            "local_finalizer_dependency_tree_sha256": _identity(
                "deterministic-local-dependency-tree"
            ),
            "local_evaluator_dependency_tree_sha256": _identity(
                "deterministic-evaluator-dependency-tree"
            ),
            "cleanup_readiness_sha256": _identity("deterministic-cleanup-readiness"),
        }
        return HostQualificationReceipt(
            **values,  # type: ignore[arg-type]
            receipt_sha256=_identity(values),
        )

    def freeze_science(
        self,
        request: ScientificFreezeRequest,
    ) -> ScientificFreezeReceipt:
        if self._declared_failure("host.freeze"):
            raise AdapterFailure("deterministic scientific freeze failure")
        freeze_root = self._root / "scientific-freeze"
        freeze_root.mkdir(mode=0o700)
        completed_wall = self._clock.wall_time()
        completed_mono = self._clock.monotonic()
        manifest = {
            "schema_version": "1.0.0",
            "provider_contract_version": request.provider_contract_version,
            "plan_id": request.plan_id,
            "host_run_id": request.host_run_id,
            "frozen_manifest_id": request.frozen_manifest_id,
            "provider_entry_receipt_sha256": request.provider_entry_receipt_sha256,
            "stage_receipt_sha256": request.stage_receipt_sha256,
            "command_package_sha256": request.command_package_sha256,
            "execution_contract_sha256": request.execution_contract_sha256,
            "qualification_receipt_sha256": request.qualification_receipt_sha256,
            "image_digest": request.image_digest,
            "frozen_at_wall_time": completed_wall,
        }
        manifest_path = freeze_root / "frozen-run-manifest.json"
        manifest_path.write_bytes(_canonical_bytes(manifest))
        manifest_path.chmod(0o600)
        manifest_sha = _file_sha256(manifest_path)
        validation = {
            "schema_version": "1.0.0",
            "provider_contract_version": request.provider_contract_version,
            "plan_id": request.plan_id,
            "host_run_id": request.host_run_id,
            "frozen_manifest_sha256": manifest_sha,
            "validated_at_wall_time": completed_wall,
            "postfreeze_valid": True,
        }
        validation_path = freeze_root / "postfreeze-validation.json"
        validation_path.write_bytes(_canonical_bytes(validation))
        validation_path.chmod(0o600)
        validation_sha = _file_sha256(validation_path)
        receipt_document = {
            "manifest_sha256": manifest_sha,
            "postfreeze_validation_sha256": validation_sha,
            "started_wall_time": request.started_wall_time,
            "completed_wall_time": completed_wall,
            "started_monotonic": request.started_monotonic,
            "completed_monotonic": completed_mono,
        }
        return ScientificFreezeReceipt(
            manifest_path=manifest_path,
            manifest_sha256=manifest_sha,
            postfreeze_validation_path=validation_path,
            postfreeze_validation_sha256=validation_sha,
            started_wall_time=request.started_wall_time,
            completed_wall_time=completed_wall,
            started_monotonic=request.started_monotonic,
            completed_monotonic=completed_mono,
            receipt_sha256=_identity(receipt_document),
        )

    def _answer_for(self, request: ConditionExecutionRequest) -> str:
        task_index = self.contract.run_ids.index(request.run_id) // 2
        if self.fault_plan.answer_overrides is not None:
            return self.fault_plan.answer_overrides[task_index]
        answers = (
            "Pat Burrell Right; Mark Mulder Left; Corey Patterson Left; "
            "Jeff Austin Right; JD Drew Left",
            "The Phantom Menace x$ 1.027 billion; Attack of the Clones x$ 653.8 "
            "million; Revenge of the Sith x$ 868.4 million; The Force Awakens x$ "
            "2.071 billion; The Last Jedi x$ 1.334 billion; The Rise of Skywalker "
            "x$ 1.077 billion",
        )
        return answers[task_index]

    def _condition_shape(
        self,
        request: ConditionExecutionRequest,
    ) -> tuple[tuple[ModelRole, ...], int]:
        if "SIMULATIVE" in request.run_id:
            return (
                (
                    ModelRole.WORLD_MODEL,
                    ModelRole.ACTOR,
                    ModelRole.CRITIC,
                    ModelRole.POLICY,
                    ModelRole.DEFAULT,
                ),
                2,
            )
        return (
            (ModelRole.CRITIC, ModelRole.ACTOR, ModelRole.DEFAULT),
            2,
        )

    def preserve_condition_failure(
        self,
        request: ConditionFailurePreservationRequest,
    ) -> ConditionInfrastructureFailureOutcome:
        """Close deterministic descendants and publish one bounded private bundle."""

        execution = request.execution
        essential_root = request.partial_raw_root.parent / "essential-failure"
        essential_root.mkdir(parents=True, mode=0o700, exist_ok=True)
        payload_root = essential_root / "payload"
        payload_root.mkdir(mode=0o700, exist_ok=True)
        manifest_path = essential_root / "essential-failure-manifest.json"
        receipt_path = essential_root / "essential-failure-complete.json"
        call_ledger = payload_root / "provider-call-accounting.json"
        browser_ledger = payload_root / "browser-action-ledger.json"
        process_path = payload_root / "process-outcome.json"
        completion_path = payload_root / "completion-state.json"
        documents: list[tuple[Path, object]] = [
            (
                call_ledger,
                {
                    "run_id": execution.run_id,
                    "call_ids": list(request.call_ids),
                    "logical_call_ids": list(request.logical_call_ids),
                    "unknown_call_ids": list(request.unknown_call_ids),
                    "accounting": request.accounting_document,
                },
            ),
            (
                browser_ledger,
                {
                    "run_id": execution.run_id,
                    "actions": [
                        {"action_id": action_id, "terminal_state": terminal_state}
                        for action_id, terminal_state in request.browser_actions
                    ],
                },
            ),
            (
                process_path,
                {
                    "run_id": execution.run_id,
                    "failure_class": request.failure_class.value,
                    "exit_code": request.process_exit_code,
                    "retry_count": request.retry_count,
                    "command_argv_count": len(execution.command_argv),
                    "command_argv_sha256": execution.command_sha256,
                    "command_sha256": execution.command_sha256,
                    "condition_plan_path": execution.condition_plan_path,
                    "condition_plan_sha256": execution.condition_plan_sha256,
                    "writers_closed": True,
                    "browser_descendants_closed": True,
                },
            ),
            (
                completion_path,
                {
                    "run_id": execution.run_id,
                    "completed": request.completed,
                    "answer": request.answer,
                    "error": request.error,
                    "evaluator_eligible": False,
                },
            ),
        ]
        for path, document in documents:
            encoded = _canonical_bytes(document)
            if path.exists():
                if path.read_bytes() != encoded:
                    raise AdapterFailure("deterministic essential-failure resume drifted")
            else:
                path.write_bytes(encoded)
                path.chmod(0o400)
        if self.fault_plan.essential_target_bytes is not None:
            self._essential_envelope_targets[execution.run_id] = (
                self.fault_plan.essential_target_bytes
            )
        artifact_fault = self.fault_plan.essential_artifact_fault
        if artifact_fault == "symlink":
            (payload_root / "unsafe-symlink").symlink_to(call_ledger.name)
        elif artifact_fault == "nonregular":
            os.mkfifo(payload_root / "unsafe-fifo", mode=0o400)
        elif artifact_fault == "hardlink":
            os.link(call_ledger, payload_root / "unsafe-hardlink.json")
        files = sorted(
            [
                {
                    "path": path.relative_to(essential_root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": _file_sha256(path),
                }
                for path in payload_root.iterdir()
                if path.is_file() and not path.is_symlink()
            ],
            key=lambda item: cast(str, item["path"]),
        )
        total = sum(cast(int, item["bytes"]) for item in files)
        if (
            total > request.essential_failure_cap_bytes
            or len(files) > request.essential_failure_file_cap
        ):
            raise AdapterFailure("deterministic essential-failure bundle exceeds its cap")
        manifest = {
            "schema_version": "2.0.0",
            "provider_contract_version": execution.provider_contract_version,
            "plan_id": execution.plan_id,
            "run_id": execution.run_id,
            "evaluator_run_id": execution.evaluator_run_id,
            "package_commit": execution.package_commit,
            "execution_contract_sha256": execution.execution_contract_sha256,
            "frozen_manifest_sha256": execution.frozen_manifest_sha256,
            "condition_plan_sha256": execution.condition_plan_sha256,
            "command_sha256": execution.command_sha256,
            "failure_class": request.failure_class.value,
            "evidence_root": "essential-failure",
            "manifest_scope": "payload-members-only-noncircular",
            "files": files,
            "payload_file_count": len(files),
            "payload_total_bytes": total,
            "envelope_file_cap": request.essential_failure_file_cap,
            "envelope_total_bytes_cap": request.essential_failure_cap_bytes,
            "unknown_call_ids": list(request.unknown_call_ids),
            "failure_reconstructable": True,
            "private_access_controlled": True,
            "publication_blocked_pending_privacy_review": True,
            "scientific_result": False,
        }
        manifest_encoded = _canonical_bytes(manifest)
        if manifest_path.exists():
            if manifest_path.read_bytes() != manifest_encoded:
                raise AdapterFailure("deterministic essential manifest resume drifted")
        else:
            manifest_path.write_bytes(manifest_encoded)
            manifest_path.chmod(0o400)
        receipt = {
            "schema_version": "2.0.0",
            "run_id": execution.run_id,
            "essential_failure_seal_complete": True,
            "attempt_identity_consumed": True,
            "infrastructure_invalid": True,
            "unscored": True,
            "evaluator_permitted": False,
            "condition_retry_permitted": False,
            "manifest_sha256": _file_sha256(manifest_path),
            "payload_file_count": len(files),
            "payload_total_bytes": total,
            "writers_closed": True,
            "browser_descendants_closed": True,
            "credential_cleanup_clean": True,
            "core_dump_present": False,
            "structural_privacy_findings": [],
            "cleanup_ready": True,
        }
        receipt_encoded = _canonical_bytes(receipt)
        if receipt_path.exists():
            if receipt_path.read_bytes() != receipt_encoded:
                raise AdapterFailure("deterministic essential receipt resume drifted")
        else:
            receipt_path.write_bytes(receipt_encoded)
            receipt_path.chmod(0o400)
        envelope_fault = self.fault_plan.essential_envelope_fault

        def replace_bytes(path: Path, encoded: bytes) -> None:
            path.chmod(0o600)
            path.write_bytes(encoded)
            path.chmod(0o400)

        if envelope_fault == "oversized-manifest":
            replace_bytes(
                manifest_path,
                _canonical_bytes({**manifest, "padding": "x" * 1_048_576}),
            )
        elif envelope_fault == "oversized-completion-receipt":
            replace_bytes(
                receipt_path,
                _canonical_bytes({**receipt, "padding": "x" * 1_048_576}),
            )
        elif envelope_fault == "secret-manifest-field":
            replace_bytes(
                manifest_path, _canonical_bytes({**manifest, "credential_hash": "f" * 64})
            )
        elif envelope_fault == "header-completion-field":
            replace_bytes(receipt_path, _canonical_bytes({**receipt, "headers": {"x": "y"}}))
        elif envelope_fault == "private-absolute-path":
            replace_bytes(manifest_path, _canonical_bytes({**manifest, "private_path": "/tmp/x"}))
        elif envelope_fault == "duplicate-json-key":
            replace_bytes(
                manifest_path,
                b'{"schema_version":"2.0.0","schema_version":"2.0.0"}\n',
            )
        elif envelope_fault == "noncanonical-json":
            replace_bytes(manifest_path, json.dumps(manifest, indent=2).encode() + b"\n")
        elif envelope_fault == "undeclared-field":
            replace_bytes(manifest_path, _canonical_bytes({**manifest, "undeclared": False}))
        elif envelope_fault == "manifest-symlink":
            manifest_path.unlink()
            manifest_path.symlink_to(call_ledger.relative_to(essential_root))
        elif envelope_fault == "receipt-symlink":
            receipt_path.unlink()
            receipt_path.symlink_to(call_ledger.relative_to(essential_root))
        elif envelope_fault == "manifest-hardlink":
            os.link(manifest_path, essential_root / "manifest-second-link.json")
        elif envelope_fault == "receipt-hardlink":
            os.link(receipt_path, essential_root / "receipt-second-link.json")
        preexport_members = tuple(
            path
            for path in sorted(essential_root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        )
        preexport_total = sum(path.stat().st_size for path in preexport_members)
        return ConditionInfrastructureFailureOutcome(
            run_id=execution.run_id,
            evaluator_run_id=execution.evaluator_run_id,
            failure_class=request.failure_class,
            process_exit_code=request.process_exit_code,
            completed=request.completed,
            answer=request.answer,
            error=request.error,
            essential_root=essential_root,
            essential_manifest_path=manifest_path,
            essential_receipt_path=receipt_path,
            call_ledger_path=call_ledger,
            browser_ledger_path=browser_ledger,
            process_outcome_path=process_path,
            completion_path=completion_path,
            stdout_path=None,
            stderr_path=None,
            payload_file_count=len(files),
            payload_total_bytes=total,
            essential_file_count=len(preexport_members),
            essential_total_bytes=preexport_total,
            output_bytes=request.output_bytes,
            unknown_call_ids=request.unknown_call_ids,
            writers_closed=True,
            browser_descendants_closed=True,
            credential_cleanup_clean=True,
            core_dump_present=False,
            structural_privacy_findings=(),
            cleanup_ready=True,
            retry_count=request.retry_count,
        )

    def export_condition_failure(
        self,
        request: ConditionFailureExportRequest,
    ) -> ConditionFailureExportReceipt:
        calls = self._failure_export_calls.get(request.run_id, 0) + 1
        self._failure_export_calls[request.run_id] = calls
        if calls <= self.fault_plan.failure_export_interruption_count:
            raise ConditionFailureExportInterrupted(
                "deterministic essential-failure export interrupted"
            )
        if self.fault_plan.mutate_essential_during_export:
            process_path = request.essential_root / "payload/process-outcome.json"
            process_path.chmod(0o600)
            process_path.write_bytes(process_path.read_bytes() + b"\n")
            process_path.chmod(0o400)
        destination = self._root / "failure-exports" / f"{request.run_id}.json"
        destination.parent.mkdir(mode=0o700, exist_ok=True)
        destination_document = {
            "run_id": request.run_id,
            "export_identity": request.export_identity,
            "essential_manifest_sha256": request.essential_manifest_sha256,
            "essential_receipt_sha256": request.essential_receipt_sha256,
            "essential_file_count": request.essential_file_count,
            "essential_total_bytes": request.essential_total_bytes,
        }
        encoded = _canonical_bytes(destination_document)
        if destination.exists():
            if destination.read_bytes() != encoded:
                raise AdapterFailure("deterministic failure export resume changed bytes")
        else:
            destination.write_bytes(encoded)
            destination.chmod(0o400)
        values = {
            "schema_version": "2.0.0",
            **destination_document,
            "destination_identity": _file_sha256(destination),
            "export_complete": True,
            "resumed": calls > 1,
        }
        acknowledgement = request.essential_root / "export-acknowledgement.json"
        target = self._essential_envelope_targets.get(request.run_id)
        padding_path = request.essential_root / "envelope-padding.bin"
        padding_bytes = 0
        padding_sha256: str | None = None

        def zero_sha256(size: int) -> str:
            digest = hashlib.sha256()
            block = b"\0" * (1024 * 1024)
            remaining = size
            while remaining:
                chunk = block if remaining >= len(block) else block[:remaining]
                digest.update(chunk)
                remaining -= len(chunk)
            return digest.hexdigest()

        def acknowledgement_document() -> dict[str, object]:
            return {
                **values,
                "envelope_padding": (
                    None
                    if padding_sha256 is None
                    else {
                        "path": padding_path.name,
                        "bytes": padding_bytes,
                        "sha256": padding_sha256,
                    }
                ),
            }

        if target is not None:
            padding_bytes = max(0, target - request.essential_total_bytes - 1024)
            for _iteration in range(16):
                padding_sha256 = zero_sha256(padding_bytes)
                acknowledgement_encoded = _canonical_bytes(acknowledgement_document())
                delta = target - (
                    request.essential_total_bytes + padding_bytes + len(acknowledgement_encoded)
                )
                if delta == 0:
                    break
                padding_bytes += delta
                if padding_bytes < 0:
                    raise AdapterFailure("deterministic essential target is below its envelope")
            else:
                raise AdapterFailure("deterministic essential envelope target did not converge")
            descriptor = os.open(
                padding_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                0o400,
            )
            try:
                os.ftruncate(descriptor, padding_bytes)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        acknowledgement_encoded = _canonical_bytes(acknowledgement_document())
        acknowledgement_fault = self.fault_plan.essential_envelope_fault
        if acknowledgement_fault == "oversized-export-acknowledgement":
            acknowledgement_encoded = _canonical_bytes(
                {**acknowledgement_document(), "padding_text": "x" * 1_048_576}
            )
        elif acknowledgement_fault == "sensitive-export-acknowledgement":
            acknowledgement_encoded = _canonical_bytes(
                {**acknowledgement_document(), "authorization_header": "not-a-secret"}
            )
        if acknowledgement.exists():
            if acknowledgement.read_bytes() != acknowledgement_encoded:
                raise AdapterFailure("deterministic failure export acknowledgement drifted")
        else:
            acknowledgement.write_bytes(acknowledgement_encoded)
            acknowledgement.chmod(0o400)
        receipt_sha256 = _file_sha256(acknowledgement)
        if acknowledgement_fault == "mutated-export-acknowledgement":
            mutated = bytearray(acknowledgement.read_bytes())
            mutated[-2] = 0x20 if mutated[-2] != 0x20 else 0x09
            acknowledgement.chmod(0o600)
            acknowledgement.write_bytes(mutated)
            acknowledgement.chmod(0o400)
        if acknowledgement_fault == "same-size-manifest-swap-during-export":
            manifest = request.essential_manifest_path
            encoded_manifest = manifest.read_bytes()
            displaced = manifest.with_name(manifest.name + ".displaced")
            manifest.rename(displaced)
            manifest.write_bytes(encoded_manifest)
            manifest.chmod(0o400)
        return ConditionFailureExportReceipt(
            run_id=request.run_id,
            export_identity=request.export_identity,
            destination_identity=cast(str, values["destination_identity"]),
            essential_manifest_sha256=request.essential_manifest_sha256,
            essential_receipt_sha256=request.essential_receipt_sha256,
            essential_file_count=request.essential_file_count,
            essential_total_bytes=request.essential_total_bytes,
            acknowledgement_path=acknowledgement,
            acknowledgement_bytes=len(acknowledgement_encoded),
            export_complete=True,
            resumed=calls > 1,
            receipt_sha256=receipt_sha256,
        )

    def execute_condition(
        self,
        request: ConditionExecutionRequest,
        *,
        observer: ConditionEventObserver,
    ) -> ConditionProcessOutcome:
        if self._declared_failure("condition.run"):
            raise AdapterFailure("deterministic condition execution failure")
        roles, browser_count = self._condition_shape(request)
        if self.fault_plan.model_input_tokens_over_cap:
            roles = (ModelRole.DEFAULT,)
        if self.fault_plan.browser_actions_over_cap:
            browser_count = request.caps.max_browser_actions + 1
        run_index = self.contract.run_ids.index(request.run_id) + 1
        calls: list[dict[str, object]] = []
        for call_index, role in enumerate(roles, start=1):
            provider_request = ProviderRequest(
                role=role,
                model=request.model_revision,
                input_tokens=(
                    request.caps.max_total_tokens + 1
                    if self.fault_plan.model_input_tokens_over_cap
                    else (0 if self.fault_plan.model_cost_over_cap else 48 + call_index)
                ),
                max_output_tokens=(
                    request.caps.max_output_tokens + 1
                    if self.fault_plan.model_cost_over_cap
                    else 24
                ),
                service_tier=request.service_tier,
                implicit_transport_retries=0,
                retry_kind="initial",
            )
            call_id = f"FX-{run_index:02d}-{call_index:04d}"
            logical_id = f"LOGICAL-{run_index:02d}-{call_index:04d}"
            event = ConditionModelCall(
                call_id=call_id,
                logical_call_id=logical_id,
                request=provider_request,
            )

            def send(
                *,
                index: int = call_index,
                value: ProviderRequest = provider_request,
            ) -> ConditionModelResponse:
                if index == 1 and self.fault_plan.name == "known-provider-exception":
                    raise ConditionKnownProviderError("deterministic known provider exception")
                if index == 1 and self.fault_plan.name == "known-transport-failure":
                    raise ConditionKnownTransportError(
                        "deterministic transport proved no provider acceptance"
                    )
                if index == 1 and self.fault_plan.name == "response-accounting-incomplete":
                    raise ConditionResponseAccountingIncomplete(
                        "deterministic response usage is incomplete"
                    )
                if index == 1 and self.fault_plan.name == "ambiguous-task-model-send":
                    raise ConditionAmbiguousSend(
                        "deterministic model send acknowledgement is ambiguous"
                    )
                return ConditionModelResponse(
                    content=f"deterministic-response-{run_index}-{index}",
                    usage=ProviderResponseUsage(
                        input_tokens=value.input_tokens - 3,
                        cached_input_tokens=7,
                        output_tokens=12,
                        service_tier=request.service_tier,
                    ),
                )

            content = observer.model_call(event, send)
            calls.append(
                {
                    "call_id": call_id,
                    "logical_call_id": logical_id,
                    "role": role.value,
                    "model": request.model_revision,
                    "service_tier": request.service_tier,
                    "terminal_state": "sent_response_reconciled",
                    "response_sha256": hashlib.sha256(content.encode()).hexdigest(),
                }
            )
        actions: list[dict[str, object]] = []
        for action_index in range(1, browser_count + 1):
            action_id = f"BROWSER-{run_index:02d}-{action_index:04d}"
            observer.browser_action(action_id=action_id, perform=lambda: None)
            actions.append(
                {
                    "action_id": action_id,
                    "terminal_state": "completed",
                }
            )
        if self.fault_plan.name == "process-crash-before-answer":
            raise RuntimeError("deterministic condition process crashed before answer")
        answer = self._answer_for(request)
        self._last_answers[request.run_id] = answer
        answer_bytes = len(answer.encode())
        nonzero_mode = self.fault_plan.name in {
            "process-exit-nonzero-before-answer",
            "process-exit-nonzero-after-answer",
            "process-exit-nonzero-completed",
        }
        if nonzero_mode:
            before_answer = self.fault_plan.name == "process-exit-nonzero-before-answer"
            completed_with_answer = self.fault_plan.name == "process-exit-nonzero-completed"
            failure_answer = None if before_answer else answer
            output_bytes = 0 if before_answer else answer_bytes
            observer.output_bytes(total_bytes=output_bytes)
            observer.process_exit(exit_code=23)
            observer.completion(
                completed=completed_with_answer,
                answer=failure_answer,
                error="" if completed_with_answer else "process exited 23",
            )
            raw_root = request.transaction_root / request.raw_output_root
            return ConditionProcessOutcome(
                run_id=request.run_id,
                evaluator_run_id=request.evaluator_run_id,
                exit_code=23,
                completed=completed_with_answer,
                answer=failure_answer,
                error="" if completed_with_answer else "process exited 23",
                raw_root=raw_root,
                raw_manifest_path=raw_root.parent / "raw-attempt-manifest.json",
                raw_receipt_path=raw_root.parent / "raw-attempt-complete.json",
                raw_file_count=0,
                raw_total_bytes=0,
                output_bytes=output_bytes,
                call_ledger_path=raw_root / "provider-call-ledger.json",
                browser_ledger_path=raw_root / "browser-action-ledger.json",
                completion_path=raw_root / "condition-answer.json",
                process_outcome_path=raw_root / "process-outcome.json",
                retry_count=0,
            )
        observer.output_bytes(
            total_bytes=(
                request.caps.max_output_bytes + 1
                if self.fault_plan.output_bytes_over_cap
                else answer_bytes
            )
        )
        observer.process_exit(exit_code=0)
        observer.completion(completed=True, answer=answer, error="")
        if self.fault_plan.name == "process-crash-after-answer":
            raise RuntimeError("deterministic condition process crashed after answer")
        requested_raw_root = request.transaction_root / request.raw_output_root
        if self.fault_plan.held_identity_fault == "raw-root-symlink":
            requested_raw_root.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            target = requested_raw_root.parent / "raw-symlink-target"
            target.mkdir(mode=0o700)
            requested_raw_root.symlink_to(target.name, target_is_directory=True)
        raw_root = requested_raw_root
        attempt_root = raw_root.parent
        raw_root.mkdir(parents=True, mode=0o700)
        call_ledger = raw_root / "provider-call-ledger.json"
        browser_ledger = raw_root / "browser-action-ledger.json"
        answer_path = raw_root / "condition-answer.json"
        process_path = raw_root / "process-outcome.json"
        call_ledger.write_bytes(_canonical_bytes({"run_id": request.run_id, "calls": calls}))
        browser_ledger.write_bytes(_canonical_bytes({"run_id": request.run_id, "actions": actions}))
        answer_path.write_bytes(
            _canonical_bytes(
                {
                    "run_id": request.run_id,
                    "completed": True,
                    "answer": answer,
                    "error": "",
                }
            )
        )
        process_path.write_bytes(
            _canonical_bytes(
                {
                    "run_id": request.run_id,
                    "exit_code": 0,
                    "retry_count": 0,
                    "command_argv": list(request.command_argv),
                    "command_sha256": request.command_sha256,
                    "condition_plan_path": request.condition_plan_path,
                    "condition_plan_sha256": request.condition_plan_sha256,
                    "model_revision": request.model_revision,
                    "service_tier": request.service_tier,
                    "caps": asdict(request.caps),
                }
            )
        )
        for path in (call_ledger, browser_ledger, answer_path, process_path):
            path.chmod(0o600)
        if self.fault_plan.name == "raw-publication-failure":
            raise RuntimeError("deterministic raw publication failed after partial files")
        host = _host_module(self.repository)
        files, total = host._raw_attempt_files(raw_root)
        manifest = {
            "schema_version": "0.1.0",
            "plan_id": request.plan_id,
            "host_run_id": self.contract.host_run_id,
            "run_id": request.run_id,
            "package_commit": request.package_commit,
            "execution_contract_sha256": request.execution_contract_sha256,
            "frozen_run_manifest_sha256": request.frozen_manifest_sha256,
            "condition_plan_sha256": request.condition_plan_sha256,
            "condition_argv_sha256": request.command_sha256,
            "raw_attempt_root": "raw",
            "files": files,
            "total_bytes": total,
            "condition_writers_closed": True,
            "raw_source_mutable_by_finalizer": False,
            "source_grounded_empirical_event_count": len(calls) + len(actions),
            "retained_session_count": 0,
            "reconstructable_disposition": "answer-ready-for-offline-finalizer",
            "actual_credential_exposure_detected": False,
            "credential_cleanup_integrity_failure": False,
            "credential_cleanup_clean": True,
            "structural_privacy_findings": [],
            "public_release_clearance": True,
            "private_access_controlled": True,
        }
        manifest_path = attempt_root / "raw-attempt-manifest.json"
        manifest_path.write_bytes(_canonical_bytes(manifest))
        manifest_path.chmod(0o600)
        receipt = {
            "schema_version": "0.1.0",
            "plan_id": request.plan_id,
            "host_run_id": self.contract.host_run_id,
            "run_id": request.run_id,
            "raw_attempt_complete": True,
            "empirical_attempt_consumed": True,
            "condition_terminated": True,
            "container_and_browser_cleanup_clean": True,
            "credential_cleanup_clean": True,
            "actual_credential_exposure_detected": False,
            "credential_cleanup_integrity_failure": False,
            "raw_manifest_path": manifest_path.name,
            "raw_manifest_sha256": _file_sha256(manifest_path),
            "raw_total_bytes": total,
            "raw_file_count": len(files),
            "source_grounded_empirical_event_count": len(calls) + len(actions),
            "retained_session_count": 0,
            "reconstructable_disposition": "answer-ready-for-offline-finalizer",
            "structural_privacy_findings": [],
            "public_release_clearance": True,
            "finalizer_network_policy": "none",
            "condition_retry_permitted": False,
            "recorded_at": self._clock.wall_time(),
        }
        if self.fault_plan.name == "raw-export-failure":
            receipt["raw_file_count"] = len(files) + 1
        receipt_path = attempt_root / "raw-attempt-complete.json"
        receipt_path.write_bytes(_canonical_bytes(receipt))
        receipt_path.chmod(0o600)
        if self.fault_plan.held_identity_fault == "raw-manifest-hardlink":
            os.link(manifest_path, attempt_root / "raw-manifest-hardlink.json")
        if self.fault_plan.held_identity_fault == "raw-receipt-hardlink":
            os.link(receipt_path, attempt_root / "raw-receipt-hardlink.json")
        manifest_sha = _file_sha256(manifest_path)
        receipt_sha = _file_sha256(receipt_path)
        observer.raw_artifact_published(
            manifest_sha256=manifest_sha,
            receipt_sha256=receipt_sha,
        )
        if self.fault_plan.condition_wall_over_cap:
            self._clock.advance(request.caps.max_wall_seconds + 1.0)
        return ConditionProcessOutcome(
            run_id=request.run_id,
            evaluator_run_id=request.evaluator_run_id,
            exit_code=0,
            completed=True,
            answer=answer,
            error="",
            raw_root=raw_root,
            raw_manifest_path=manifest_path,
            raw_receipt_path=receipt_path,
            raw_file_count=len(files),
            raw_total_bytes=total,
            output_bytes=answer_bytes,
            call_ledger_path=call_ledger,
            browser_ledger_path=browser_ledger,
            completion_path=answer_path,
            process_outcome_path=process_path,
            retry_count=0,
        )

    def finalize_condition(
        self,
        request: FinalizerExecutionRequest,
    ) -> FinalizerExecutionOutcome:
        if self._declared_failure("condition.finalize"):
            raise AdapterFailure("deterministic offline finalizer failure")
        if self.fault_plan.held_identity_fault == "raw-same-size-swap-before-finalizer":
            answer_path = request.answer_artifact.path
            encoded = answer_path.read_bytes()
            displaced = answer_path.with_name(answer_path.name + ".displaced")
            answer_path.rename(displaced)
            answer_path.write_bytes(encoded)
            answer_path.chmod(0o400)
        for artifact in request.raw_artifacts:
            artifact.revalidate()
        if (
            _file_sha256(request.raw_manifest_path) != request.raw_manifest_sha256
            or _file_sha256(request.raw_receipt_path) != request.raw_receipt_sha256
            or _file_sha256(request.raw_completion_path) != request.raw_completion_sha256
            or _file_sha256(request.process_outcome_path) != request.process_outcome_sha256
            or request.execution_mode != "qualified-local"
            or request.runtime_qualification_id != self.contract.local_finalizer_qualification_id
            or request.raw_artifact_binding_sha256
            != _identity([artifact.to_public_document() for artifact in request.raw_artifacts])
        ):
            raise AdapterFailure("deterministic finalizer received mutated raw evidence")
        answer_document = json.loads(request.answer_artifact.read_bytes())
        answer = answer_document.get("answer")
        if not isinstance(answer, str) or not answer:
            raise AdapterFailure("deterministic finalizer raw answer is absent")
        if self.fault_plan.held_identity_fault == "finalized-root-symlink":
            request.finalized_root.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            target = request.finalized_root.parent / "finalized-symlink-target"
            target.mkdir(mode=0o700)
            request.finalized_root.symlink_to(target.name, target_is_directory=True)
        request.finalized_root.mkdir(parents=True, mode=0o700, exist_ok=True)
        task_index = self.contract.run_ids.index(request.run_id) // 2
        dataset = json.loads(
            (self.repository / "tests/fixtures/t09/fanout-two-task-fixture.json").read_bytes()
        )
        goal = dataset[task_index]["question"]
        session = request.finalized_root / "session.json"
        session.write_bytes(
            _canonical_bytes(
                {
                    "goal": goal,
                    "instance_id": None,
                    "history": [
                        [
                            {"url": "about:blank"},
                            f"send_msg_to_user({answer!r})",
                            {"thought": "effect-produced"},
                        ]
                    ],
                    "is_complete": True,
                    "error": "",
                }
            )
        )
        session.chmod(0o600)
        semantic = _identity(
            {
                "run_id": request.run_id,
                "session_sha256": _file_sha256(session),
                "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
            }
        )
        completion = {
            "schema_version": "1.0.0",
            "run_id": request.run_id,
            "evaluator_run_id": request.evaluator_run_id,
            "execution_mode": request.execution_mode,
            "runtime_qualification_id": request.runtime_qualification_id,
            "runtime_qualification_sha256": request.runtime_qualification_sha256,
            "raw_output_root": request.raw_output_root,
            "finalized_output_root": request.finalized_output_root,
            "consumed_raw_manifest_sha256": request.raw_manifest_sha256,
            "consumed_raw_receipt_sha256": request.raw_receipt_sha256,
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
            "semantic_projection_sha256": semantic,
            "session_sha256s": [_file_sha256(session)],
            "infrastructure_valid": True,
        }
        completion_path = request.finalized_root / "finalization-complete.json"
        completion_path.write_bytes(_canonical_bytes(completion))
        completion_path.chmod(0o600)
        if self.fault_plan.held_identity_fault == "raw-mutation-during-finalizer":
            answer_path = request.answer_artifact.path
            mutated_answer = bytearray(answer_path.read_bytes())
            mutated_answer[-1] = 0x20 if mutated_answer[-1] != 0x20 else 0x0A
            answer_path.chmod(0o600)
            answer_path.write_bytes(mutated_answer)
            answer_path.chmod(0o400)
        return FinalizerExecutionOutcome(
            run_id=request.run_id,
            finalized_root=request.finalized_root,
            completion_receipt_path=completion_path,
            completion_receipt_sha256=_file_sha256(completion_path),
            semantic_projection_sha256=semantic,
            session_paths=(session,),
            consumed_raw_manifest_sha256=request.raw_manifest_sha256,
            consumed_raw_receipt_sha256=request.raw_receipt_sha256,
            consumed_raw_artifact_binding_sha256=(request.raw_artifact_binding_sha256),
            infrastructure_valid=True,
        )

    def evaluate_condition(
        self,
        request: EvaluatorExecutionRequest,
    ) -> EvaluatorExecutionOutcome:
        if self._declared_failure("condition.evaluate"):
            raise AdapterFailure("deterministic evaluator failure")
        if self.fault_plan.held_identity_fault == "session-swap-before-evaluator":
            session = request.session_paths[0]
            encoded = session.read_bytes()
            displaced = session.with_name(session.name + ".displaced")
            session.rename(displaced)
            session.write_bytes(encoded)
            session.chmod(0o400)
        for artifact in request.finalized_artifacts:
            artifact.revalidate()
        if request.finalized_artifact_binding_sha256 != _identity(
            [artifact.to_public_document() for artifact in request.finalized_artifacts]
        ):
            raise AdapterFailure("deterministic evaluator received split held evidence")
        by_path = {artifact.path: artifact for artifact in request.finalized_artifacts}
        try:
            session_artifacts = tuple(by_path[path] for path in request.session_paths)
        except KeyError as exc:
            raise AdapterFailure("deterministic evaluator session identity is not held") from exc
        identity = pilot.EvaluatorIdentity(
            root=self.repository / "tests/fixtures/t09/pinned-evaluator",
            dataset_path=(self.repository / "tests/fixtures/t09/fanout-two-task-fixture.json"),
            task_index=request.task_index,
            fixture_subset=True,
        )
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = pilot.evaluate_retained_session(identity, list(request.session_paths))
        raw_score = result.get("score")
        score = float(raw_score) if isinstance(raw_score, (int, float)) else None
        run_index = self.contract.run_ids.index(request.run_id)
        evaluator_valid = result.get("evaluator_valid") is True
        task_completed = result.get("task_completed") is True
        answer_produced = result.get("answer_produced") is True
        if self.fault_plan.task_a_zero_scores and run_index < 2:
            score = 0.0
            evaluator_valid = True
            task_completed = True
            answer_produced = True
        if self.fault_plan.evaluator_unscored_run_index == run_index:
            score = None
            evaluator_valid = False
        if self.fault_plan.evaluator_invalid_run_index == run_index:
            score = None
            evaluator_valid = False
        session_hashes = tuple(artifact.sha256 for artifact in session_artifacts)
        values = {
            "run_id": request.run_id,
            "evaluator_run_id": request.evaluator_run_id,
            "consumed_session_sha256s": list(session_hashes),
            "consumed_finalized_artifact_binding_sha256": (
                request.finalized_artifact_binding_sha256
            ),
            "evaluator_contract_sha256": request.evaluator_contract_sha256,
            "evaluator_valid": evaluator_valid,
            "task_completed": task_completed,
            "answer_produced": answer_produced,
            "score": score,
            "infrastructure_failure": False,
            "missing_required_evidence": False,
        }
        outcome = EvaluatorExecutionOutcome(
            run_id=request.run_id,
            evaluator_run_id=request.evaluator_run_id,
            consumed_finalized_root=request.finalized_root,
            consumed_session_sha256s=session_hashes,
            consumed_finalized_artifact_binding_sha256=(request.finalized_artifact_binding_sha256),
            evaluator_contract_sha256=request.evaluator_contract_sha256,
            evaluator_valid=cast(bool, values["evaluator_valid"]),
            task_completed=cast(bool, values["task_completed"]),
            answer_produced=cast(bool, values["answer_produced"]),
            score=score,
            infrastructure_failure=False,
            missing_required_evidence=False,
            receipt_sha256=_identity(values),
        )
        if run_index == 1:
            source_fault = self.fault_plan.provider_lifecycle_source_fault
            campaign_roots = sorted((self._root / "private").glob("campaign-slot-*"))
            if source_fault is not None and not campaign_roots:
                raise AdapterFailure("provider lifecycle fault lacks retained campaign roots")
            if source_fault == "active-entry-receipt-mutated":
                path = campaign_roots[-1] / "entry-source/entry-receipt.json"
                path.write_bytes(path.read_bytes() + b"\n")
            elif source_fault == "active-price-source-mutated":
                path = campaign_roots[-1] / "entry-source/001-instance-types.json"
                path.write_bytes(path.read_bytes() + b"\n")
            elif source_fault == "closed-slot-omitted":
                (campaign_roots[0] / "replacement-launch-eligibility.json").unlink()
        if self.fault_plan.checkpoint_missing_raw_after_task_a and run_index == 1:
            first_manifest = sorted(self._root.rglob("raw-attempt-manifest.json"))[0]
            first_manifest.unlink()
        return outcome

    def cleanup_transaction(
        self,
        request: CleanupExecutionRequest,
    ) -> CleanupExecutionReceipt:
        self._cleanup_calls += 1
        if self._cleanup_calls <= self.fault_plan.cleanup_interruption_count:
            raise CleanupInterrupted("deterministic cleanup interruption")
        if self.fault_plan.root_replacement_before_cleanup and self._cleanup_calls == 1:
            original = request.held_transaction_root.path
            displaced = original.with_name(original.name + "-held-owned")
            original.rename(displaced)
            original.mkdir(mode=0o700)
            sentinel = original / "replacement-sentinel.bin"
            sentinel.write_bytes(b"replacement-directory-must-remain-unchanged\n")
            sentinel.chmod(0o400)
        findings: tuple[str, ...] = ()
        if (
            self.fault_plan.name == "structural-privacy-finding"
            or self.fault_plan.fail_operation == "evidence.scan_privacy"
        ):
            findings = ("deterministic structural privacy finding",)
        completed_wall = self._clock.wall_time()
        completed_monotonic = self._clock.monotonic()
        values = {
            "immutable_handoff_sha256": request.immutable_handoff_sha256,
            "owned_containers_absent": True,
            "exact_secret_matches": 0,
            "structural_privacy_findings": list(findings),
            "remote_secret_removed": True,
            "firewall_restored": True,
            "rulesets_restored": True,
            "started_wall_time": request.started_wall_time,
            "completed_wall_time": completed_wall,
            "started_monotonic": request.started_monotonic,
            "completed_monotonic": completed_monotonic,
        }
        return CleanupExecutionReceipt(
            immutable_handoff_sha256=request.immutable_handoff_sha256,
            owned_containers_absent=True,
            exact_secret_matches=0,
            structural_privacy_findings=findings,
            remote_secret_removed=True,
            firewall_restored=True,
            rulesets_restored=True,
            started_wall_time=request.started_wall_time,
            completed_wall_time=completed_wall,
            started_monotonic=request.started_monotonic,
            completed_monotonic=completed_monotonic,
            receipt_sha256=_identity(values),
        )


class LiveShapedNoNetworkEffects:
    """Composition proxy giving a temporary package module its own exact identity."""

    def __init__(
        self,
        *,
        delegate: DeterministicLowLevelEffects,
        identity: EffectImplementationIdentity,
        authorization_context: EffectAuthorizationContext,
        authority: EffectAuthorityGrant,
        held_transaction_root: HeldTransactionRoot,
    ) -> None:
        if (
            authorization_context.authority_kind is not EffectAuthorityKind.LIVE_AUTHORIZED
            or authorization_context.execution_mode
            is not EffectExecutionMode.DETERMINISTIC_NO_NETWORK
            or authorization_context.effect_implementation != identity
            or authorization_context.transaction_root_identity
            != held_transaction_root.semantic_sha256
            or not isinstance(authority, ValidatedLiveEffectAuthority)
            or not authority.is_valid_for(authorization_context)
            or authority.held_transaction_root is not held_transaction_root
            or delegate.transaction_root() != held_transaction_root.path
        ):
            raise ValueError("live-shaped no-network effects lack exact external authority")
        self._delegate = delegate
        self._identity = identity
        self._authorization_context = authorization_context
        self._authority = authority
        self._held_transaction_root = held_transaction_root

    @property
    def effect_protocol_version(self) -> str:
        return self._delegate.effect_protocol_version

    @property
    def provider_contract_version(self) -> str:
        return self._delegate.provider_contract_version

    def implementation_identity(self) -> EffectImplementationIdentity:
        return self._identity

    def metadata_authorization_binding(
        self,
        *,
        contract: T09ProviderContract,
    ) -> dict[str, object]:
        binding = dict(self._delegate.metadata_authorization_binding(contract=contract))
        binding["authorization_reference"] = (
            self._authorization_context.external_authorization_reference
        )
        binding["authorization_source_sha256"] = (
            self._authorization_context.external_authorization_source_sha256
        )
        return binding

    def cleanup_transaction(
        self,
        request: CleanupExecutionRequest,
    ) -> CleanupExecutionReceipt:
        request.held_transaction_root.revalidate_descriptor()
        if (
            request.held_transaction_root is not self._held_transaction_root
            or request.transaction_root != self._held_transaction_root.path
            or request.authorization_reference
            != self._authorization_context.external_authorization_reference
            or request.authorization_source_sha256
            != self._authorization_context.external_authorization_source_sha256
        ):
            raise AdapterFailure("live-shaped cleanup received split authority or root")
        return self._delegate.cleanup_transaction(request)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


def build_live_shaped_no_network_effects(
    *,
    repository: Path,
    contract: T09ProviderContract,
    implementation_identity: EffectImplementationIdentity,
    authorization_context: EffectAuthorizationContext,
    authority: EffectAuthorityGrant,
    held_transaction_root: HeldTransactionRoot,
    fault_plan: ShadowFaultPlan | None = None,
) -> LowLevelEffects:
    """Construct the test-only live-shaped package effect by composition."""

    delegate = DeterministicLowLevelEffects(
        repository=repository,
        contract=contract,
        fault_plan=fault_plan or ShadowFaultPlan("live-shaped-conformance"),
        fixed_tick=2000,
        transaction_root=held_transaction_root.path,
    )
    return LiveShapedNoNetworkEffects(
        delegate=delegate,
        identity=implementation_identity,
        authorization_context=authorization_context,
        authority=authority,
        held_transaction_root=held_transaction_root,
    )


def build_deterministic_effects(
    *,
    repository: Path,
    contract: T09ProviderContract,
    authorization_context: EffectAuthorizationContext | None = None,
    authority: object | None = None,
    fault_plan: ShadowFaultPlan | None = None,
    fixed_tick: int = 1000,
    transaction_root: Path | None = None,
) -> DeterministicLowLevelEffects:
    """Factory used by public CI; optional authority arguments are never grants."""

    del authorization_context, authority
    return DeterministicLowLevelEffects(
        repository=repository,
        contract=contract,
        fault_plan=fault_plan or ShadowFaultPlan("happy-path"),
        fixed_tick=fixed_tick,
        transaction_root=transaction_root,
    )


def build_production_shadow_assembly(
    repository: Path,
    contract: T09ProviderContract,
    fault_plan: ShadowFaultPlan,
    *,
    rehearsal: ValidatedShadowRehearsal | None = None,
    control_binding_semantic_sha256: str | None = None,
    fixed_tick: int = 1000,
    transaction_root: Path | None = None,
) -> ProductionCategory3World:
    """Bind deterministic effects to the exact same production assembly."""

    effects = build_deterministic_effects(
        repository=repository,
        contract=contract,
        fault_plan=fault_plan,
        fixed_tick=fixed_tick,
        transaction_root=transaction_root,
    )
    held_transaction_root = hold_transaction_root(effects.transaction_root())
    commit, tree = _git_identity(repository)
    command_sha = contract.expected_command_manifest_sha256
    if command_sha is None:
        raise ValueError("deterministic production assembly requires a command package")
    binding_sha = (
        rehearsal.staging.semantic_sha256
        if rehearsal is not None
        else control_binding_semantic_sha256
    )
    if (
        not isinstance(binding_sha, str)
        or len(binding_sha) != 64
        or (rehearsal is not None and control_binding_semantic_sha256 is not None)
    ):
        raise ValueError("deterministic assembly requires one exact control binding")
    context = EffectAuthorizationContext(
        authority_kind=EffectAuthorityKind.SHADOW_ONLY,
        execution_mode=EffectExecutionMode.DETERMINISTIC_NO_NETWORK,
        control_commit=commit,
        control_tree=tree,
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        plan_path=contract.plan_path,
        plan_bytes=contract.expected_plan_bytes,
        plan_sha256=contract.expected_plan_sha256,
        command_package_sha256=command_sha,
        control_binding_semantic_sha256=binding_sha,
        effect_implementation=effects.implementation_identity(),
        # Shadow authority binds the shared-held root's stable attestation rather
        # than leaking nondeterministic private inode/path identity into receipts.
        # Live authority continues to bind the exact runtime-private identity.
        transaction_root_identity=held_transaction_root.public_attestation_semantic_sha256,
        external_authorization_reference=None,
        external_authorization_source_sha256=None,
        cost_limits=EffectAuthorizationLimits(
            preflight_provider_cost_usd=contract.preflight_lambda_cost_cap_usd,
            campaign_provider_cost_usd=contract.campaign_lambda_cost_cap_usd,
            campaign_openai_cost_usd=contract.campaign_openai_cost_cap_usd,
            campaign_aggregate_cost_usd=contract.campaign_aggregate_cost_cap_usd,
            prior_t09_cost_usd=contract.prior_t09_cost_usd,
            cumulative_t09_cost_usd=contract.cumulative_t09_cost_cap_usd,
        ),
        zero_retry=True,
        interpretation="descriptive-calibration-only",
        current_turn_scope="deterministic-shadow",
        campaign_count=1,
    )
    authority = mint_shadow_effect_authority(
        source="validated-deterministic-production-effects",
        context=context,
    )
    return build_production_adapter_assembly(
        repository,
        contract,
        low_level_effects=effects,
        authorization_context=context,
        authority=authority,
        held_transaction_root=held_transaction_root,
    )


__all__ = [
    "DeterministicLowLevelEffects",
    "DeterministicRuntimeClock",
    "ShadowFaultPlan",
    "build_deterministic_effects",
    "build_live_shaped_no_network_effects",
    "build_production_shadow_assembly",
]
