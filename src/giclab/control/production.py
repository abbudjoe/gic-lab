"""Production-coupled Category 3 adapters over injected low-level effects.

The wrappers in this module execute retained T09 lifecycle, metadata, accounting,
evidence, finalizer, evaluator, and cleanup primitives.  Public CI supplies the
deterministic low-level implementation below.  A later package can supply another
``LowLevelEffects`` implementation and an externally validated authority grant; it
does not need another controller or another production adapter assembly.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Final, Protocol

from giclab.control.adapters import (
    AdapterCall,
    AdapterFailure,
    AmbiguousProviderOutcome,
    Category3Adapters,
    CleanupInterrupted,
    EffectAuthorityGrant,
    EffectAuthorityKind,
    FakeScenario,
    ImplementationFlavor,
    MetadataEnvelope,
    ProviderHandle,
    StructuralPrivacyFinding,
    TerminationUnavailable,
    UndeclaredAdapterCall,
    mint_shadow_effect_authority,
)
from giclab.control.consumers import (
    CONTROL_CONSUMERS,
    ConsumerResolution,
    resolve_control_consumers,
)
from giclab.control.registry_validation import resolve_registered_command_package
from giclab.harness import t09_model_metadata_receipt as metadata
from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness import t09_sira_pilot as pilot
from giclab.harness.sira_gate_a import (
    SIRA_MODEL_REVISION,
    ImmutableModelRouting,
    ModelRole,
    ProviderBudgetBoundary,
    ProviderBudgetCaps,
    ProviderBudgetExceeded,
    ProviderBudgetUsage,
    ProviderFailureDisposition,
    ProviderRequest,
    ProviderResponseReceiptError,
    ProviderResponseUsage,
)
from giclab.harness.t09_cleanup_state import CleanupTargetState, EarlyCleanupJournal
from giclab.harness.t09_provider_contracts import T09ProviderContract
from giclab.registry import load_json

_FAKE_OPENAI_VALUE: Final = b"fixture-openai-production-shadow-value"
_FAKE_LAMBDA_VALUE: Final = b"fixture-lambda-production-shadow-value"
_FAKE_PUBLIC_IPV4: Final = "203.0.113.7"
_FAKE_PUBLIC_KEY: Final = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixture production-shadow"
_RUNTIME_CONSUMERS: Final = {
    name: consumer
    for name, consumer in CONTROL_CONSUMERS.items()
    if name != "production_adapter_assembly"
}
_TASK_A_ANSWER: Final = (
    "Pat Burrell Right; Mark Mulder Left; Corey Patterson Left; Jeff Austin Right; JD Drew Left"
)
_TASK_B_ANSWER: Final = (
    "The Phantom Menace x$ 1.027 billion; Attack of the Clones x$ 653.8 million; "
    "Revenge of the Sith x$ 868.4 million; The Force Awakens x$ 2.071 billion; "
    "The Last Jedi x$ 1.334 billion; The Rise of Skywalker x$ 1.077 billion"
)


class LowLevelEffects(Protocol):
    """Injected channels beneath retained production logic."""

    def transaction_root(self) -> Path | None: ...

    def read_model_secret(self) -> bytearray: ...

    def read_provider_secret(self) -> bytearray: ...

    def public_ipv4(self) -> str: ...

    def ssh_public_key(self) -> str: ...

    def metadata_response(self, *, completed_at: float) -> metadata.ModelMetadataResponse: ...

    def metadata_authorization_binding(
        self,
        *,
        contract: T09ProviderContract,
    ) -> Mapping[str, object]: ...

    def provider_inventory(self) -> tuple[str, ...] | None: ...

    def provider_launch(self, *, launch_ordinal: int) -> ProviderHandle: ...

    def provider_entry(self, handle: ProviderHandle) -> None: ...

    def provider_terminate(self, handle: ProviderHandle) -> None: ...

    def campaign_transport(
        self,
        *,
        contract: T09ProviderContract,
        launch_ordinal: int,
        clock: Callable[[], float],
        provider_entry_failure: bool,
    ) -> provider.ProviderTransport: ...

    def retained_image_archive(self, *, launch_ordinal: int) -> Path | None: ...

    def model_send(
        self,
        *,
        run_id: str,
        request: ProviderRequest,
    ) -> tuple[str, ProviderResponseUsage]: ...

    def browser_action(self, *, run_id: str) -> None: ...

    def offline_command(self, argv: tuple[str, ...]) -> bytes: ...


@dataclass(slots=True)
class DeterministicShadowEffects:
    """Network-, container-, and provider-free channels used only by public CI."""

    scenario: FakeScenario
    _active: dict[str, ProviderHandle]
    _ambiguous_launch: bool = False

    @classmethod
    def create(cls, scenario: FakeScenario) -> DeterministicShadowEffects:
        return cls(scenario=scenario, _active={})

    def transaction_root(self) -> Path | None:
        return None

    def read_model_secret(self) -> bytearray:
        return bytearray(_FAKE_OPENAI_VALUE)

    def read_provider_secret(self) -> bytearray:
        return bytearray(_FAKE_LAMBDA_VALUE)

    def public_ipv4(self) -> str:
        return _FAKE_PUBLIC_IPV4

    def ssh_public_key(self) -> str:
        return _FAKE_PUBLIC_KEY

    def metadata_response(self, *, completed_at: float) -> metadata.ModelMetadataResponse:
        body = (
            json.dumps({"id": metadata.MODEL_METADATA_MODEL_ID}, sort_keys=True) + "\n"
        ).encode()
        return metadata.ModelMetadataResponse(
            status=200,
            body=body,
            response_completed_at=completed_at,
        )

    def metadata_authorization_binding(
        self,
        *,
        contract: T09ProviderContract,
    ) -> Mapping[str, object]:
        return {
            "authorization_reference": (f"{contract.authorization_prefix}SHADOW-CONTROL-0001"),
            "authorization_source_sha256": "1" * 64,
            "public_price_contract_sha256": "2" * 64,
            "public_deprecation_observation_sha256": "3" * 64,
            "authorized": True,
            "single_use": True,
        }

    def provider_inventory(self) -> tuple[str, ...] | None:
        if self._ambiguous_launch and self.scenario.ambiguous_inventory_after_launch:
            return None
        return tuple(sorted(self._active))

    def provider_launch(self, *, launch_ordinal: int) -> ProviderHandle:
        if self.scenario.name == "ambiguous-provider-call-outcome":
            self._ambiguous_launch = True
            raise TimeoutError("deterministic launch acknowledgement unavailable")
        handle = ProviderHandle(
            opaque_identity=f"shadow-instance-{launch_ordinal}",
            launch_ordinal=launch_ordinal,
        )
        self._active[handle.opaque_identity] = handle
        return handle

    def provider_entry(self, handle: ProviderHandle) -> None:
        if handle.opaque_identity not in self._active:
            raise RuntimeError("provider entry lacks its owned handle")

    def provider_terminate(self, handle: ProviderHandle) -> None:
        self._active.pop(handle.opaque_identity, None)

    def campaign_transport(
        self,
        *,
        contract: T09ProviderContract,
        launch_ordinal: int,
        clock: Callable[[], float],
        provider_entry_failure: bool,
    ) -> provider.ProviderTransport:
        return _QueuedProviderTransport(
            responses=_shadow_launch_responses(
                contract,
                launch_ordinal,
                provider_entry_failure=provider_entry_failure,
            ),
            effects=self,
            clock=clock,
            launch_ordinal=launch_ordinal,
        )

    def retained_image_archive(self, *, launch_ordinal: int) -> Path | None:
        del launch_ordinal
        return None

    def model_send(
        self,
        *,
        run_id: str,
        request: ProviderRequest,
    ) -> tuple[str, ProviderResponseUsage]:
        del request
        return (
            f"shadow-response:{run_id}",
            ProviderResponseUsage(
                input_tokens=24,
                cached_input_tokens=8,
                output_tokens=6,
                service_tier="default",
            ),
        )

    def browser_action(self, *, run_id: str) -> None:
        if not run_id:
            raise RuntimeError("browser action lacks a run identity")

    def offline_command(self, argv: tuple[str, ...]) -> bytes:
        if not argv or any(not item for item in argv):
            raise RuntimeError("offline command is malformed")
        return ("offline:" + " ".join(argv)).encode()


@dataclass(slots=True)
class _QueuedProviderTransport:
    """Fake HTTP channel beneath the retained provider request recorder."""

    responses: list[object]
    effects: LowLevelEffects
    clock: Callable[[], float]
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
        if credential != _FAKE_LAMBDA_VALUE or not self.responses:
            raise RuntimeError("production shadow provider channel drifted")
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
            received_at_epoch=self.clock(),
        )


def _shadow_instance(
    contract: T09ProviderContract,
    launch_ordinal: int,
    *,
    status: str,
) -> dict[str, object]:
    return {
        "id": f"shadow-instance-{launch_ordinal}",
        "name": contract.instance_name,
        "hostname": contract.instance_name,
        "instance_type": {"name": provider.INSTANCE_TYPE},
        "region": {"name": provider.REGION},
        "status": status,
        "ip": f"198.51.100.{launch_ordinal + 8}",
        "file_system_names": [],
    }


def _shadow_global_firewall() -> dict[str, object]:
    return {
        "data": {
            "id": "global",
            "name": "global",
            "workspace_id": "production-shadow-workspace",
            "rules": [
                {
                    "protocol": "tcp",
                    "port_range": [22, 22],
                    "source_network": f"{_FAKE_PUBLIC_IPV4}/32",
                    "description": "production-shadow-fixture",
                }
            ],
        }
    }


def _shadow_launch_responses(
    contract: T09ProviderContract,
    launch_ordinal: int,
    *,
    provider_entry_failure: bool,
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
        {"data": [{"name": provider.SSH_KEY_NAME, "public_key": _FAKE_PUBLIC_KEY}]},
        _shadow_global_firewall(),
        {"data": []},
        {"data": []},
        {"data": {"instance_ids": [f"shadow-instance-{launch_ordinal}"]}},
    ]
    if not provider_entry_failure:
        return [
            *prefix,
            {"data": [_shadow_instance(contract, launch_ordinal, status="active")]},
        ]
    return [
        *prefix,
        RuntimeError("deterministic active-poll transport failure"),
        RuntimeError("deterministic termination acknowledgement ambiguity"),
        {"data": [_shadow_instance(contract, launch_ordinal, status="terminated")]},
        {"data": []},
        _shadow_global_firewall(),
        {"data": []},
    ]


class _MetadataTransport:
    def __init__(self, effects: LowLevelEffects, clock: Callable[[], float]) -> None:
        self._effects = effects
        self._clock = clock

    def get_model_metadata(
        self,
        model_id: str,
        *,
        credential: bytearray,
    ) -> metadata.ModelMetadataResponse:
        if model_id != metadata.MODEL_METADATA_MODEL_ID or credential != _FAKE_OPENAI_VALUE:
            raise metadata.ModelMetadataReceiptError("shadow metadata request identity drifted")
        return self._effects.metadata_response(completed_at=self._clock())


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _identity(*parts: object) -> str:
    return hashlib.sha256(_canonical_bytes(parts)).hexdigest()


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


@lru_cache(maxsize=1)
def _host_module_from(path_text: str) -> ModuleType:
    path = Path(path_text)
    name = "giclab_t09_control_production_host"
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
    """Prove that all runtime consumers required by the assembly resolve."""

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
    missing = sorted(name for name in required if resolutions.get(name) is None)
    if missing:
        raise ValueError("production adapter assembly lacks consumers: " + ", ".join(missing))
    return {
        "implementation_flavor": ImplementationFlavor.PRODUCTION_WRAPPER.value,
        "resolved_consumers": sorted(required),
        "low_level_effects_injected": True,
        "controller_bypass": False,
        "controller_entrypoint": ("giclab.control.category3:execute_category3_transaction"),
        "future_live_source_changes_required": False,
        "live_authority_factory_present": False,
        "required_low_level_channels": [
            "transaction_root",
            "read_model_secret",
            "read_provider_secret",
            "public_ipv4",
            "ssh_public_key",
            "metadata_response",
            "metadata_authorization_binding",
            "provider_inventory",
            "provider_launch",
            "provider_entry",
            "provider_terminate",
            "campaign_transport",
            "retained_image_archive",
            "model_send",
            "browser_action",
            "offline_command",
        ],
    }


class ProductionCategory3World:
    """One production wrapper assembly bound to exact low-level channels."""

    _MAX_CALLS: Final[Mapping[str, int]] = {
        "secret.read": 1,
        "metadata.request": 1,
        "metadata.is_fresh": 1,
        "provider.inventory": 4,
        "provider.launch": 2,
        "provider.enter": 2,
        "provider.terminate": 3,
        "host.stage": 1,
        "host.preflight": 2,
        "host.qualify": 1,
        "host.freeze": 1,
        "host.cleanup": 2,
        "condition.reserve": 4,
        "condition.enter": 4,
        "condition.run": 4,
        "condition.export_raw": 4,
        "condition.finalize": 4,
        "condition.evaluate": 4,
        "evidence.record": 16,
        "evidence.checkpoint": 1,
        "evidence.scan_privacy": 1,
    }

    def __init__(
        self,
        repository: Path,
        contract: T09ProviderContract,
        scenario: FakeScenario,
        *,
        low_level_effects: LowLevelEffects,
        authority: EffectAuthorityGrant,
        fixed_tick: int,
    ) -> None:
        self.repository = repository.resolve(strict=True)
        self.contract = contract
        self.scenario = scenario
        self.low_level_effects = low_level_effects
        self.authority = authority
        self._tick = fixed_tick
        self._clock_epoch = 1_700_000_000.0
        self._calls: list[AdapterCall] = []
        self._counts: Counter[str] = Counter()
        self._undeclared_calls: list[str] = []
        self._primitive_calls: list[str] = []
        self._closed_launch_slots: list[int] = []
        self._termination_failures = 0
        self._cleanup_calls = 0
        requested_root = self.low_level_effects.transaction_root()
        self._temporary: tempfile.TemporaryDirectory[str] | None
        if requested_root is None:
            if self.authority.kind is EffectAuthorityKind.LIVE_AUTHORIZED:
                raise ValueError("live low-level effects require a durable transaction root")
            self._temporary = tempfile.TemporaryDirectory(prefix="giclab-t09-shadow-")
            self.root = Path(self._temporary.name).resolve(strict=True)
        else:
            self._temporary = None
            self.root = requested_root.resolve(strict=True)
        self.private_root = self.root / "private"
        self.public_root = self.root / "public"
        self.private_root.mkdir(mode=0o700)
        self.public_root.mkdir(mode=0o700)
        self._dotenv = self.private_root / "mixed.env"
        self._metadata_overlay = self.private_root / "authorization-overlay.json"
        self._metadata_receipt = self.private_root / metadata.MODEL_METADATA_RECEIPT_FILENAME
        self._pilot_state = self.private_root / "pilot-state.json"
        self._public_ipv4 = self.private_root / "source-ipv4.txt"
        self._public_key = self.private_root / "provider-key.pub"
        self._image_fixture: Path | None = None
        self._campaign_controls: provider.ShadowCampaignLowLevelControls | None = None
        if self.authority.kind is EffectAuthorityKind.SHADOW_ONLY:
            self._image_fixture = self.private_root / "retained-image.fixture"
            capability_root = self.private_root / "launch-capabilities"
            capability_root.mkdir(mode=0o700)
            self._image_fixture.write_bytes(b"production-shadow-retained-image-fixture")
            self._image_fixture.chmod(0o600)
            package_commit, _package_tree = _git_identity(self.repository)
            self._campaign_controls = provider._mint_shadow_campaign_low_level_controls(
                capability_root=capability_root,
                expected_package_commit=package_commit,
                image_fixture=self._image_fixture,
            )
        self._campaign_roots: dict[int, Path] = {}
        self._entry_receipts: dict[int, Path] = {}
        self._provider_handles: dict[int, ProviderHandle] = {}
        self._provider_entry_failed_slots: set[int] = set()
        self._execution_contract: pilot.PilotExecutionContract | None = None
        self._metadata_document: dict[str, object] | None = None
        self._accounting: dict[str, dict[str, object]] = {}
        self._aggregate_usage = ProviderBudgetUsage()
        self._aggregate_observed_usage = ProviderBudgetUsage()
        self._evaluations: dict[str, dict[str, object]] = {}
        self._raw_export_acknowledgements: dict[str, str] = {}
        self._cleanup_handoff_bytes: bytes | None = None
        self._stage_evidence: dict[str, object] | None = None
        self._finalizer_bindings: tuple[str, str, str, str, object, object] | None = None
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
            authority=self.authority,
            clock=self,
            secret_channel=self,
            metadata_transport=self,
            provider_transport=self,
            host_runtime=self,
            condition_runtime=self,
            evidence_store=self,
            audit=self,
            diagnostics=self,
        )

    def tick(self) -> int:
        return self._tick

    def _wall_clock(self) -> float:
        self._clock_epoch += 0.125
        return self._clock_epoch

    def _begin(self, operation: str, subject: str) -> int:
        occurrence = self._counts[operation] + 1
        self._counts[operation] = occurrence
        limit = self._MAX_CALLS.get(operation)
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

    def _declared_failure(self, operation: str, occurrence: int) -> bool:
        return (
            self.scenario.fail_operation == operation
            and self.scenario.fail_occurrence == occurrence
        )

    def _primitive(self, name: str) -> None:
        self._primitive_calls.append(name)

    def _resolution(self, name: str) -> ConsumerResolution:
        resolution = self._consumer_resolutions.get(name)
        if resolution is None:
            raise AdapterFailure(f"production consumer is unavailable: {name}")
        return resolution

    def read(self) -> str:
        operation = "secret.read"
        occurrence = self._begin(operation, "strict-mixed-dotenv")
        if self._declared_failure(operation, occurrence):
            self._record(operation, "strict-mixed-dotenv", "failed")
            raise AdapterFailure("secret-channel qualification failed")
        model_secret = self.low_level_effects.read_model_secret()
        provider_secret = self.low_level_effects.read_provider_secret()
        raw = (
            b"OPENAI_API_KEY="
            + bytes(model_secret)
            + b"\nLAMBDA_API_KEY="
            + bytes(provider_secret)
            + b"\n"
        )
        self._dotenv.write_bytes(raw)
        self._dotenv.chmod(0o600)
        self._public_ipv4.write_text(self.low_level_effects.public_ipv4(), encoding="utf-8")
        self._public_key.write_text(self.low_level_effects.ssh_public_key(), encoding="utf-8")
        selected = metadata.load_openai_dotenv_assignment(self._dotenv)
        self._primitive("load_openai_dotenv_assignment")
        matched = selected == model_secret
        metadata._destroy_bytearray(selected)
        metadata._destroy_bytearray(model_secret)
        metadata._destroy_bytearray(provider_secret)
        if not matched:
            raise AdapterFailure("strict dotenv selected another assignment")
        self._record(operation, "strict-mixed-dotenv", "passed")
        return _identity("qualified-secret-channel", self.contract.version)

    def request(self, *, contract_version: str) -> MetadataEnvelope:
        operation = "metadata.request"
        occurrence = self._begin(operation, contract_version)
        if self._declared_failure(operation, occurrence):
            self._record(operation, contract_version, "failed")
            raise AdapterFailure("shadow metadata transport failed")
        if contract_version != self.contract.version or not self._dotenv.is_file():
            raise AdapterFailure("metadata request lacks its exact prepared secret channel")
        commit, tree = _git_identity(self.repository)
        binding = dict(
            self.low_level_effects.metadata_authorization_binding(contract=self.contract)
        )
        reference = binding.get("authorization_reference")
        authorization_source_sha256 = binding.get("authorization_source_sha256")
        public_price_contract_sha256 = binding.get("public_price_contract_sha256")
        public_deprecation_observation_sha256 = binding.get("public_deprecation_observation_sha256")
        if (
            not isinstance(reference, str)
            or not isinstance(authorization_source_sha256, str)
            or not isinstance(public_price_contract_sha256, str)
            or not isinstance(public_deprecation_observation_sha256, str)
            or binding.get("authorized") is not True
            or binding.get("single_use") is not True
        ):
            raise AdapterFailure("metadata authorization binding is incomplete")
        overlay = {
            "schema_version": metadata.MODEL_METADATA_SCHEMA_VERSION,
            "authorization_reference": reference,
            "authorization_source_sha256": authorization_source_sha256,
            "provider_contract_version": self.contract.version,
            "repository_commit": commit,
            "repository_tree": tree,
            "plan_id": self.contract.plan_id,
            "plan_sha256": self.contract.expected_provider_profile_sha256,
            "host_run_id": self.contract.host_run_id,
            "public_price_contract_sha256": public_price_contract_sha256,
            "public_deprecation_observation_sha256": (public_deprecation_observation_sha256),
            "model_metadata_receipt_sha256": None,
            "authorized": True,
            "single_use": True,
        }
        self._metadata_overlay.write_bytes(_canonical_bytes(overlay))
        self._metadata_overlay.chmod(0o600)
        overlay_sha256 = metadata.model_metadata_authorization_overlay_sha256(
            self._metadata_overlay
        )
        try:
            metadata.create_model_metadata_receipt(
                repository_commit=commit,
                repository_tree=tree,
                plan_id=self.contract.plan_id,
                plan_sha256=self.contract.expected_provider_profile_sha256,
                provider_contract_version=self.contract.version,
                host_run_id=self.contract.host_run_id,
                authorization_reference=reference,
                authorization_source_sha256=authorization_source_sha256,
                authorization_overlay_sha256=overlay_sha256,
                public_price_contract_sha256=public_price_contract_sha256,
                public_deprecation_observation_sha256=(public_deprecation_observation_sha256),
                output=self._metadata_receipt,
                dotenv=self._dotenv,
                authorization_overlay=self._metadata_overlay,
                transport=_MetadataTransport(self.low_level_effects, self._wall_clock),
                clock=self._wall_clock,
            )
            receipt_sha256 = metadata.model_metadata_receipt_sha256(self._metadata_receipt)
            metadata.bind_model_metadata_receipt_to_authorization_overlay(
                self._metadata_overlay,
                receipt_sha256=receipt_sha256,
            )
            document = metadata.validate_model_metadata_receipt(
                self._metadata_receipt,
                contract=self.contract,
                package_commit=commit,
                package_tree=tree,
                plan_sha256=self.contract.expected_provider_profile_sha256,
                authorization_overlay=self._metadata_overlay,
                validation_policy=metadata.ModelMetadataReceiptValidationPolicy.DURABLE_OFFLINE,
            )
        except Exception as exc:
            self._record(operation, contract_version, "failed")
            raise AdapterFailure(f"production metadata receipt failed: {exc}") from exc
        self._primitive("create_model_metadata_receipt")
        self._primitive("bind_model_metadata_receipt_to_authorization_overlay")
        self._primitive("validate_model_metadata_receipt:durable-offline")
        self._metadata_document = document
        issued = self._tick
        expires = issued if self.scenario.metadata_expires_before_launch else issued + 10
        self._record(operation, contract_version, "passed")
        self._tick += 1
        return MetadataEnvelope(
            receipt_sha256=metadata.model_metadata_receipt_sha256(self._metadata_receipt),
            issued_tick=issued,
            expires_tick=expires,
        )

    def is_fresh(self, envelope: MetadataEnvelope) -> bool:
        operation = "metadata.is_fresh"
        occurrence = self._begin(operation, envelope.receipt_sha256)
        if self._metadata_document is None:
            raise AdapterFailure("metadata freshness lacks a validated receipt")
        boundary = self._wall_clock()
        try:
            metadata.admit_model_metadata_receipt_at_prelaunch_boundary(
                self._metadata_document,
                boundary_epoch=boundary,
            )
        except metadata.ModelMetadataReceiptError:
            self._record(operation, envelope.receipt_sha256, "expired")
            return False
        self._primitive("admit_model_metadata_receipt_at_prelaunch_boundary")
        fresh = self._tick < envelope.expires_tick and not self._declared_failure(
            operation, occurrence
        )
        self._record(operation, envelope.receipt_sha256, "passed" if fresh else "expired")
        return fresh

    def inventory(self) -> tuple[str, ...] | None:
        operation = "provider.inventory"
        occurrence = self._begin(operation, "owned-resources")
        if self._declared_failure(operation, occurrence):
            self._record(operation, "owned-resources", "failed")
            raise AdapterFailure("production provider inventory failed")
        values = self.low_level_effects.provider_inventory()
        self._record(
            operation,
            "owned-resources",
            "ambiguous" if values is None else ("zero" if not values else "observed"),
        )
        return values

    def _sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise RuntimeError("production shadow clock cannot move backward")
        self._clock_epoch += seconds

    def _campaign_scope(self) -> AbstractContextManager[None]:
        if self._campaign_controls is None:
            return nullcontext()
        return provider._shadow_campaign_control_scope(self._campaign_controls)

    def launch(self, *, launch_ordinal: int) -> ProviderHandle:
        operation = "provider.launch"
        occurrence = self._begin(operation, f"launch-{launch_ordinal}")
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
            if self._declared_failure(operation, occurrence):
                self.low_level_effects.provider_launch(launch_ordinal=launch_ordinal)
                raise TimeoutError("declared provider launch ambiguity")
            provider_entry_failure = (
                self.scenario.name == "provider-entry-replacement" and launch_ordinal == 1
            )
            transport = self.low_level_effects.campaign_transport(
                contract=self.contract,
                launch_ordinal=launch_ordinal,
                clock=self._wall_clock,
                provider_entry_failure=provider_entry_failure,
            )
            private_root = self.private_root / f"campaign-slot-{launch_ordinal:02d}"
            prior = self._campaign_roots.get(launch_ordinal - 1)
            retained_image = None
            if prior is not None:
                retained_image = (
                    self._image_fixture
                    if self._campaign_controls is not None
                    else self.low_level_effects.retained_image_archive(
                        launch_ordinal=launch_ordinal
                    )
                )
            commit, _tree = _git_identity(self.repository)
            try:
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
                    shadow_controls=self._campaign_controls,
                    clock=self._wall_clock,
                    sleeper=self._sleep,
                )
            except provider.T09ProviderError:
                eligibility = private_root / "replacement-launch-eligibility.json"
                if not provider_entry_failure or not eligibility.is_file():
                    raise
                self._provider_entry_failed_slots.add(launch_ordinal)
                self._primitive("_cleanup_provisional_owner")
                self._primitive("_publish_replacement_launch_eligibility")
            else:
                self._entry_receipts[launch_ordinal] = entry_receipt
            if isinstance(transport, _QueuedProviderTransport):
                handle = transport.launched_handle
            else:
                ownership_path = private_root / (
                    "provisional-owned-state.json"
                    if provider_entry_failure
                    else "owned-state-active.json"
                )
                ownership = load_json(ownership_path)
                identity = ownership.get("owned_instance_identity_sha256")
                handle = (
                    ProviderHandle(identity, launch_ordinal) if isinstance(identity, str) else None
                )
            if handle is None:
                raise AdapterFailure("retained launch did not bind one provider handle")
            self._campaign_roots[launch_ordinal] = private_root
            self._provider_handles[launch_ordinal] = handle
            self._primitive("launch_campaign")
            if launch_ordinal > 1:
                normalized = private_root / provider.PROVIDER_ENTRY_AUTHORITY_ROOT_NAME
                if not (normalized / "source-manifest.json").is_file():
                    raise AdapterFailure("replacement launch did not retain normalized authority")
                self._primitive("_normalize_provider_entry_replacement_authority")
                self._primitive("_retain_replacement_launch_authority")
        except TimeoutError as exc:
            self._record(operation, f"launch-{launch_ordinal}", "ambiguous")
            raise AmbiguousProviderOutcome("provider launch acknowledgement is ambiguous") from exc
        except Exception as exc:
            self._record(operation, f"launch-{launch_ordinal}", "failed")
            raise AdapterFailure(f"production launch preparation failed: {exc}") from exc
        self._record(operation, handle.opaque_identity, "accepted")
        return handle

    def provider_entry(self, handle: ProviderHandle) -> None:
        operation = "provider.enter"
        occurrence = self._begin(operation, handle.opaque_identity)
        self.contract.validate_owner(
            plan_id=self.contract.plan_id,
            host_run_id=self.contract.host_run_id,
            instance_name=self.contract.instance_name,
        )
        self._primitive("T09ProviderContract.validate_owner")
        if handle.launch_ordinal in self._provider_entry_failed_slots or self._declared_failure(
            operation, occurrence
        ):
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure("provider-entry-failed replacement eligibility")
        entry_receipt = self._entry_receipts.get(handle.launch_ordinal)
        private_root = self._campaign_roots.get(handle.launch_ordinal)
        commit, _tree = _git_identity(self.repository)
        if entry_receipt is None or private_root is None:
            raise AdapterFailure("provider entry lacks its retained source-bound receipt")
        with self._campaign_scope():
            provider.validate_entry_receipt_source_bound(
                entry_receipt,
                private_root / "entry-source",
                contract=self.contract,
                package_commit=commit,
                plan_sha256=provider.file_sha256(
                    self.repository / self.contract.provider_profile_path
                ),
            )
        self._primitive("validate_entry_receipt_source_bound")
        self.low_level_effects.provider_entry(handle)
        self._record(operation, handle.opaque_identity, "passed")

    def terminate(self, handle: ProviderHandle) -> None:
        operation = "provider.terminate"
        occurrence = self._begin(operation, handle.opaque_identity)
        if occurrence <= self.scenario.termination_failure_count or self._declared_failure(
            operation, occurrence
        ):
            self._termination_failures += 1
            self._record(operation, handle.opaque_identity, "unavailable")
            raise TerminationUnavailable("bounded provider termination unavailable")
        self.low_level_effects.provider_terminate(handle)
        if handle.launch_ordinal not in self._closed_launch_slots:
            self._closed_launch_slots.append(handle.launch_ordinal)
            self._closed_launch_slots.sort()
        self._record(operation, handle.opaque_identity, "accepted")

    def stage(self) -> str:
        operation = "host.stage"
        occurrence = self._begin(operation, "local-package-and-archive")
        if self._declared_failure(operation, occurrence):
            self._record(operation, "local-package-and-archive", "failed")
            raise AdapterFailure("deterministic staging failed")
        package, package_sha256, source = resolve_registered_command_package(
            self.repository,
            self.contract,
        )
        execution_sha256 = package.get("execution_contract_sha256")
        if not isinstance(execution_sha256, str) or self.contract.execution_contract_path is None:
            raise AdapterFailure("registered execution package is incomplete")
        self._execution_contract = pilot.load_execution_contract(
            self.repository / self.contract.execution_contract_path,
            expected_sha256=execution_sha256,
        )
        archive_bytes = _canonical_bytes(
            {
                "contract": self.contract.version,
                "package_sha256": package_sha256,
                "run_ids": list(self.contract.run_ids),
            }
        )
        source_path = self.private_root / "stage-source.bin"
        target_path = self.private_root / "stage-canonical.bin"
        source_path.write_bytes(archive_bytes)
        source_path.chmod(0o600)
        host = _host_module(self.repository)
        staged = host.stage_verified_archive(
            source_path,
            target_path,
            len(archive_bytes),
            hashlib.sha256(archive_bytes).hexdigest(),
        )
        self.low_level_effects.offline_command(("validate-command-package", self.contract.version))
        self._primitive("resolve_registered_command_package")
        self._primitive("load_execution_contract")
        self._primitive("stage_verified_archive")
        self._stage_evidence = {
            "command_package_sha256": package_sha256,
            "execution_contract_sha256": execution_sha256,
            "package_source": source,
            "archive_sha256": staged.get("sha256"),
            "archive_bytes": len(archive_bytes),
            "regular_no_follow": True,
            "storage_roundtrip": target_path.read_bytes() == archive_bytes,
        }
        self._record(operation, "local-package-and-archive", "passed")
        return _identity(self._stage_evidence)

    def _host_preempirical_source(self, handle: ProviderHandle) -> tuple[Path, Path]:
        entry_receipt = self._entry_receipts[handle.launch_ordinal]
        entry = load_json(entry_receipt)
        started = float(entry["provider_preflight_started_at_epoch"])
        iteration_started = started + 1.0
        failed_at = iteration_started + 1.0
        source = self.private_root / f"host-preempirical-slot-{handle.launch_ordinal:02d}"
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
            "provider_entry_receipt_sha256": provider.file_sha256(entry_receipt),
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
        return source / "preempirical-disposition.json", source

    def _close_host_preflight_for_replacement(self, handle: ProviderHandle) -> None:
        private_root = self._campaign_roots[handle.launch_ordinal]
        disposition, source = self._host_preempirical_source(handle)
        continuation = self.private_root / (f"remote-cleanup-slot-{handle.launch_ordinal:02d}")
        shutil.copytree(private_root / "preflight-cleanup-state", continuation)
        EarlyCleanupJournal(continuation).record_result(
            target_id="temporary-remote-secret",
            result=CleanupTargetState.ABSENT,
            detail_code="temporary-remote-secret-already-absent",
            clock=self._wall_clock,
        )
        transport = _QueuedProviderTransport(
            responses=[
                RuntimeError("deterministic termination acknowledgement ambiguity"),
                {"data": []},
                _shadow_global_firewall(),
                {"data": []},
            ],
            effects=self.low_level_effects,
            clock=self._wall_clock,
            launch_ordinal=handle.launch_ordinal,
            launched_handle=handle,
        )
        commit, _tree = _git_identity(self.repository)
        with self._campaign_scope():
            provider.closeout_campaign(
                contract=self.contract,
                repository=self.repository,
                package_commit=commit,
                authorization_ledger=self._metadata_overlay,
                dotenv=self._dotenv,
                private_root=private_root,
                transport=transport,
                preempirical_receipt=disposition,
                preempirical_source_root=source,
                remote_cleanup_journal=continuation,
                clock=self._wall_clock,
                sleeper=self._sleep,
            )
        if not (private_root / "replacement-launch-eligibility.json").is_file():
            raise AdapterFailure("host closeout did not publish replacement eligibility")
        self._primitive("closeout_campaign")
        self._primitive("_publish_replacement_launch_eligibility")

    def preflight(self, handle: ProviderHandle) -> None:
        operation = "host.preflight"
        occurrence = self._begin(operation, handle.opaque_identity)
        if self._declared_failure(operation, occurrence):
            try:
                self._close_host_preflight_for_replacement(handle)
            except Exception as exc:
                self._record(operation, handle.opaque_identity, "failed")
                raise AdapterFailure(f"retained host preflight closeout failed: {exc}") from exc
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure("retained host preflight failed")
        if self._metadata_document is None:
            raise AdapterFailure("host preflight lacks metadata receipt")
        commit, _tree = _git_identity(self.repository)
        provider_entry = {
            "model_metadata_receipt_sha256": metadata.model_metadata_receipt_sha256(
                self._metadata_receipt
            ),
            "authorization_reference": self._metadata_document["authorization_reference"],
            "authorization_source_sha256": self._metadata_document["authorization_source_sha256"],
            "provider_preflight_started_at_epoch": self._wall_clock(),
        }
        artifact_root = self.private_root / f"host-{handle.launch_ordinal}"
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
        self._primitive("validate_model_metadata_receipt_offline")
        self._record(operation, handle.opaque_identity, "passed")

    def qualify(self, handle: ProviderHandle) -> str:
        operation = "host.qualify"
        occurrence = self._begin(operation, handle.opaque_identity)
        if self._declared_failure(operation, occurrence):
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure("image/finalizer qualification failed")
        commit, _tree = _git_identity(self.repository)
        host = _host_module(self.repository)
        try:
            self._finalizer_bindings = host.validate_finalizer_source(
                repository=self.repository,
                package_commit=commit,
                finalizer_commit=commit,
                source=self.repository / host.FINALIZER_RELATIVE_PATH,
                projection_source=self.repository / host.FINALIZER_PROJECTION_RELATIVE_PATH,
            )
        except Exception as exc:
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure(f"downstream finalizer qualification failed: {exc}") from exc
        self._primitive("validate_finalizer_source")
        self._record(operation, handle.opaque_identity, "passed")
        return _identity("qualified-finalizer", *self._finalizer_bindings[:4])

    def freeze(self, handle: ProviderHandle) -> str:
        operation = "host.freeze"
        occurrence = self._begin(operation, handle.opaque_identity)
        if self._declared_failure(operation, occurrence):
            self._record(operation, handle.opaque_identity, "failed")
            raise AdapterFailure("scientific freeze failed")
        if self._execution_contract is None:
            raise AdapterFailure("scientific freeze lacks staged execution contract")
        pilot.initialize_pilot_state(
            self._pilot_state,
            provider_contract=self.contract,
            execution_contract_sha256=self._execution_contract.sha256,
            pilot_started_at_epoch=1_700_000_000.0,
            lambda_started_at_epoch=1_700_000_000.0,
        )
        self._primitive("initialize_pilot_state")
        self._record(operation, handle.opaque_identity, "passed")
        return _identity("scientific-freeze", self._execution_contract.sha256)

    def cleanup(self, handle: ProviderHandle | None) -> str:
        operation = "host.cleanup"
        subject = handle.opaque_identity if handle is not None else "no-known-instance"
        occurrence = self._begin(operation, subject)
        self._cleanup_calls += 1
        state: dict[str, object]
        if self._pilot_state.is_file() and self._execution_contract is not None:
            try:
                state = pilot.load_validated_pilot_state(
                    self._pilot_state,
                    execution_contract_sha256=self._execution_contract.sha256,
                )
            except Exception as exc:
                self._record(operation, subject, "failed")
                raise AdapterFailure(f"cleanup empirical-prefix handoff failed: {exc}") from exc
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
                "secret_owner": "strict-mixed-dotenv",
                "firewall_owner": self.contract.host_run_id,
                "ruleset_owner": self.contract.plan_id,
            }
        )
        if self._cleanup_handoff_bytes is None:
            self._cleanup_handoff_bytes = handoff
        elif handoff != self._cleanup_handoff_bytes:
            raise AdapterFailure("cleanup resume handoff changed bytes")
        if occurrence <= self.scenario.cleanup_interruption_count:
            self._record(operation, subject, "interrupted-resumable")
            raise CleanupInterrupted("cleanup interrupted after immutable handoff")
        if self._declared_failure(operation, occurrence):
            self._record(operation, subject, "failed")
            raise AdapterFailure("retained cleanup handler failed")
        self._primitive("immutable_cleanup_export_handoff")
        self._record(operation, subject, "passed")
        return hashlib.sha256(handoff).hexdigest()

    def _require_execution(self) -> pilot.PilotExecutionContract:
        if self._execution_contract is None or not self._pilot_state.is_file():
            raise AdapterFailure("condition runtime lacks frozen pilot state")
        return self._execution_contract

    def reserve(self, run_id: str) -> str:
        operation = "condition.reserve"
        occurrence = self._begin(operation, run_id)
        if self._declared_failure(operation, occurrence):
            self._record(operation, run_id, "failed")
            raise AdapterFailure("condition reservation failed")
        execution = self._require_execution()
        start_intent = _identity("condition-start-intent", run_id)
        pilot.reserve_condition_start(
            self._pilot_state,
            execution_contract_sha256=execution.sha256,
            run_id=run_id,
            start_intent_sha256=start_intent,
        )
        self._primitive("reserve_condition_start")
        self._record(operation, run_id, "passed")
        return start_intent

    def enter(self, run_id: str) -> str:
        operation = "condition.enter"
        occurrence = self._begin(operation, run_id)
        if self._declared_failure(operation, occurrence):
            self._record(operation, run_id, "failed")
            raise AdapterFailure("empirical entry failed")
        execution = self._require_execution()
        release = _identity("supervised-release", run_id)
        pilot.mark_empirical_entry(
            self._pilot_state,
            execution_contract_sha256=execution.sha256,
            run_id=run_id,
            supervised_release_receipt_sha256=release,
        )
        self._primitive("mark_empirical_entry")
        self._record(operation, run_id, "passed")
        return release

    @staticmethod
    def _condition_caps(*, admission_stop: bool) -> ProviderBudgetCaps:
        return ProviderBudgetCaps(
            max_cost_usd=0.0 if admission_stop else 1.0,
            max_input_tokens=128,
            max_cached_input_tokens=128,
            max_output_tokens=128,
            max_total_tokens=256,
            max_model_call_attempts=1,
            max_wall_seconds=60,
            max_browser_actions=1,
            max_output_bytes=4096,
        )

    @staticmethod
    def _aggregate_caps() -> ProviderBudgetCaps:
        return ProviderBudgetCaps(
            max_cost_usd=4.0,
            max_input_tokens=512,
            max_cached_input_tokens=512,
            max_output_tokens=512,
            max_total_tokens=1024,
            max_model_call_attempts=4,
            max_wall_seconds=240,
            max_browser_actions=4,
            max_output_bytes=16_384,
        )

    def run(self, run_id: str) -> str:
        operation = "condition.run"
        occurrence = self._begin(operation, run_id)
        if self._declared_failure(operation, occurrence):
            self._record(operation, run_id, "failed")
            raise AdapterFailure("condition execution failed")
        admission_stop = self.scenario.name == "cost-token-admission-stop"
        boundary = ProviderBudgetBoundary(
            routing=ImmutableModelRouting.locked(),
            aggregate_caps=self._aggregate_caps(),
            condition_caps=self._condition_caps(admission_stop=admission_stop),
            monotonic=lambda: float(self._tick),
            initial_aggregate_usage=self._aggregate_usage,
            initial_aggregate_observed_usage=self._aggregate_observed_usage,
        )
        request = ProviderRequest(
            role=ModelRole.CRITIC,
            model=SIRA_MODEL_REVISION,
            input_tokens=32,
            max_output_tokens=16,
        )
        call_id = f"CALL-SHADOW-{len(self._accounting) + 1:04d}"

        def send(value: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
            if self.scenario.name == "known-provider-exception":
                raise RuntimeError("deterministic known provider error")
            if self.scenario.name == "response-accounting-incomplete":
                raise ProviderResponseReceiptError("deterministic usage receipt failure")
            if self.scenario.name == "ambiguous-task-model-send":
                raise TimeoutError("deterministic model send ambiguity")
            return self.low_level_effects.model_send(run_id=run_id, request=value)

        def classify(exc: BaseException) -> ProviderFailureDisposition:
            if self.scenario.name == "known-provider-exception":
                return ProviderFailureDisposition.PROVIDER_ERROR
            if isinstance(exc, ProviderResponseReceiptError):
                return ProviderFailureDisposition.OUTCOME_UNKNOWN
            return ProviderFailureDisposition.OUTCOME_UNKNOWN

        try:
            result = boundary.invoke(
                request,
                send,
                call_id=call_id,
                logical_call_id=f"LOGICAL-{run_id}",
                classify_failure=classify,
            )
            boundary.record_browser_action(
                before_action=lambda: self.low_level_effects.browser_action(run_id=run_id)
            )
            boundary.record_output_bytes(len(result.encode()))
        except ProviderBudgetExceeded as exc:
            self._accounting[run_id] = boundary.accounting_document()
            self._record(operation, run_id, "admission-stopped")
            raise AdapterFailure("cost/token admission stopped before model send") from exc
        except BaseException as exc:
            self._accounting[run_id] = boundary.accounting_document()
            self._aggregate_usage = boundary.aggregate_usage
            self._aggregate_observed_usage = boundary.aggregate_observed_usage
            self._primitive("ProviderBudgetBoundary.invoke")
            self._record(operation, run_id, "unknown" if boundary.unknown_outcomes else "failed")
            raise AdapterFailure(
                f"model-call accounting stopped condition: {type(exc).__name__}"
            ) from exc
        self._accounting[run_id] = boundary.accounting_document()
        self._aggregate_usage = boundary.aggregate_usage
        self._aggregate_observed_usage = boundary.aggregate_observed_usage
        self._primitive("ProviderBudgetBoundary.invoke")
        self._primitive("ProviderBudgetBoundary.record_browser_action")
        self._primitive("ProviderBudgetBoundary.record_output_bytes")
        self._record(operation, run_id, "passed")
        return result

    def export_raw(self, run_id: str) -> str:
        operation = "condition.export_raw"
        occurrence = self._begin(operation, run_id)
        if self._declared_failure(operation, occurrence):
            self._record(operation, run_id, "failed")
            raise AdapterFailure("raw export acknowledgement failed")
        execution = self._require_execution()
        raw_manifest = _identity("raw-manifest", run_id, self._accounting.get(run_id))
        raw_receipt = _identity("raw-receipt", run_id, raw_manifest)
        try:
            pilot.mark_raw_attempt_complete(
                self._pilot_state,
                execution_contract_sha256=execution.sha256,
                run_id=run_id,
                raw_manifest_sha256=raw_manifest,
                raw_receipt_sha256=raw_receipt,
            )
            exported = _canonical_bytes(
                {
                    "run_id": run_id,
                    "manifest_sha256": raw_manifest,
                    "receipt_sha256": raw_receipt,
                }
            )
            local = self.public_root / f"{run_id}.raw.json"
            off_host = self.public_root / f"{run_id}.exported.json"
            local.write_bytes(exported)
            off_host.write_bytes(local.read_bytes())
            if off_host.read_bytes() != exported:
                raise AdapterFailure("off-host raw export bytes changed")
        except Exception as exc:
            self._record(operation, run_id, "failed")
            raise AdapterFailure(f"retained raw export failed: {exc}") from exc
        acknowledgement = hashlib.sha256(exported).hexdigest()
        self._raw_export_acknowledgements[run_id] = acknowledgement
        self._primitive("mark_raw_attempt_complete")
        self._primitive("exact_raw_export_acknowledgement")
        self._record(operation, run_id, "passed")
        return raw_receipt

    def finalize(self, run_id: str) -> str:
        operation = "condition.finalize"
        occurrence = self._begin(operation, run_id)
        if self._declared_failure(operation, occurrence):
            self._record(operation, run_id, "failed")
            raise AdapterFailure("typed infrastructure-invalid finalizer failure")
        execution = self._require_execution()
        if self._finalizer_bindings is None:
            raise AdapterFailure("downstream finalizer source was not qualified")
        commit, _tree = _git_identity(self.repository)
        source_sha, projection_sha, _selector_sha, _schema_sha = self._finalizer_bindings[:4]
        semantic = _identity("finalized-semantic-projection", run_id)
        complete = _identity("finalization-complete", run_id)
        host = _host_module(self.repository)
        try:
            rebound = host.validate_finalizer_source(
                repository=self.repository,
                package_commit=commit,
                finalizer_commit=commit,
                source=self.repository / host.FINALIZER_RELATIVE_PATH,
                projection_source=self.repository / host.FINALIZER_PROJECTION_RELATIVE_PATH,
            )
            if rebound[:4] != self._finalizer_bindings[:4]:
                raise AdapterFailure("downstream finalizer binding changed before use")
            pilot.mark_attempt_completed(
                self._pilot_state,
                execution_contract_sha256=execution.sha256,
                run_id=run_id,
                finalizer_execution_mode="qualified-image",
                finalizer_runtime_qualification_sha256=_identity("runtime-qualification"),
                finalizer_source_sha256=source_sha,
                finalizer_projection_source_sha256=projection_sha,
                finalizer_commit=commit,
                finalizer_dependency_manifest_sha256=_identity("finalizer-dependencies"),
                evaluator_contract_sha256=execution.evaluator_contract_sha256,
                interpreter="/opt/sira/.venv/bin/python",
                interpreter_sha256=_identity("qualified-interpreter"),
                semantic_projection_sha256=semantic,
                finalized_output_root=f"shadow-finalized/{run_id}",
                finalization_complete_sha256=complete,
            )
        except Exception as exc:
            self._record(operation, run_id, "failed")
            raise AdapterFailure(f"typed infrastructure-invalid finalizer failure: {exc}") from exc
        self._primitive("mark_attempt_completed")
        self._record(operation, run_id, "passed")
        return complete

    def evaluate(self, run_id: str) -> str:
        operation = "condition.evaluate"
        occurrence = self._begin(operation, run_id)
        if self._declared_failure(operation, occurrence):
            self._record(operation, run_id, "failed")
            raise AdapterFailure("pinned evaluator fixture failed")
        index = self.contract.run_ids.index(run_id)
        task_index = 0 if index < 2 else 1
        action = _TASK_A_ANSWER if task_index == 0 else _TASK_B_ANSWER
        session = self.private_root / f"session-{index}.json"
        session.write_bytes(
            _canonical_bytes(
                {
                    "goal": "deterministic pinned evaluator fixture",
                    "instance_id": None,
                    "history": [
                        [
                            {"url": "about:blank"},
                            f"send_msg_to_user({action!r})",
                            {"thought": "fixture"},
                        ]
                    ],
                    "is_complete": True,
                    "error": "",
                }
            )
        )
        identity = pilot.EvaluatorIdentity(
            root=self.repository / "tests/fixtures/t09/pinned-evaluator",
            dataset_path=self.repository / "tests/fixtures/t09/fanout-two-task-fixture.json",
            task_index=task_index,
            fixture_subset=True,
        )
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = pilot.evaluate_retained_session(identity, [session])
        raw_score = result.get("score")
        fixture_score = float(raw_score) if isinstance(raw_score, (int, float)) else None
        outcome = pilot.outcome_contract(
            process_exit_code=0,
            artifact_executed=True,
            task_completed=result.get("task_completed") is True,
            answer_produced=result.get("answer_produced") is True,
            evaluator_valid=result.get("evaluator_valid") is True,
            score=fixture_score,
            infrastructure_failure=False,
            missing_required_evidence=False,
        )
        self._evaluations[run_id] = {
            "evaluator_valid": result.get("evaluator_valid"),
            "task_completed": result.get("task_completed"),
            "fixture_score": raw_score,
            "valid_scored_attempt": outcome["valid_scored_attempt"],
            "classification": "deterministic-fixture-control-output-not-science",
        }
        self._primitive("EvaluatorIdentity.verify")
        self._primitive("evaluate_retained_session")
        self._primitive("outcome_contract")
        self._record(operation, run_id, "passed")
        return _identity(self._evaluations[run_id])

    def record(self, *, kind: str, identity: str) -> None:
        operation = "evidence.record"
        occurrence = self._begin(operation, kind)
        if self._declared_failure(operation, occurrence):
            self._record(operation, kind, "failed")
            raise AdapterFailure("evidence retention failed")
        self._record(operation, kind, f"retained:{identity[:12]}")

    def checkpoint(self, *, name: str) -> str:
        operation = "evidence.checkpoint"
        occurrence = self._begin(operation, name)
        if self._declared_failure(operation, occurrence):
            self._record(operation, name, "failed")
            raise AdapterFailure("first-pair checkpoint failed")
        execution = self._require_execution()
        decision = {
            "decision": "continue-to-task-b",
            "first_pair_started_at_epoch": 1_700_000_000.0,
            "second_pair_started_at_epoch": 1_700_000_100.0,
            "decided_at_epoch": 1_700_000_100.0,
        }
        pilot.record_first_pair_checkpoint(
            self._pilot_state,
            execution_contract_sha256=execution.sha256,
            decision=decision,
            decided_at_epoch=1_700_000_100.0,
        )
        self._primitive("record_first_pair_checkpoint")
        self._record(operation, name, "passed")
        return _identity(decision)

    def scan_privacy(self) -> str:
        operation = "evidence.scan_privacy"
        occurrence = self._begin(operation, "shadow-evidence")
        if self._declared_failure(operation, occurrence):
            finding = self.public_root / "finding.json"
            finding.write_bytes(_canonical_bytes({"api_key": "redacted-fixture"}))
        host = _host_module(self.repository)
        findings = host.privacy_violations(self.public_root)
        self._primitive("privacy_violations")
        if findings:
            self._record(operation, "shadow-evidence", "finding")
            raise StructuralPrivacyFinding("retained structural privacy scanner found a violation")
        self._record(operation, "shadow-evidence", "passed")
        return _identity("privacy-clean", occurrence)

    def control_evidence(self) -> Mapping[str, object]:
        lower_cost = self._aggregate_observed_usage.cost_usd
        upper_cost = self._aggregate_usage.cost_usd
        shadow_only = self.authority.kind is EffectAuthorityKind.SHADOW_ONLY
        return {
            "implementation_flavor": ImplementationFlavor.PRODUCTION_WRAPPER.value,
            "effect_authority": self.authority.kind.value,
            "authority_source": self.authority.source,
            "production_primitives": sorted(set(self._primitive_calls)),
            "resolved_consumers": {
                name: (resolution.handler_id if resolution is not None else "not-applicable")
                for name, resolution in sorted(self._consumer_resolutions.items())
            },
            "accounting": {
                "conditions": dict(self._accounting),
                "aggregate_observed_cost_usd": lower_cost,
                "aggregate_charged_upper_cost_usd": upper_cost,
                "projected_real_cost_usd": 0.0 if shadow_only else upper_cost,
                "fake_usage": shadow_only,
                "zero_retries": True,
            },
            "evaluations": dict(self._evaluations),
            "deterministic_staging": self._stage_evidence,
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
            "cleanup_resume_byte_identical": self._cleanup_calls < 2
            or self._cleanup_handoff_bytes is not None,
        }


def build_production_adapter_assembly(
    repository: Path,
    contract: T09ProviderContract,
    scenario: FakeScenario,
    *,
    low_level_effects: LowLevelEffects,
    authority: EffectAuthorityGrant,
    fixed_tick: int = 1000,
) -> ProductionCategory3World:
    """Build the sole production adapter assembly used by shadow and future live effects."""

    commit, _tree = _git_identity(repository)
    if not authority.authorizes(
        contract_version=contract.version,
        control_revision=commit,
    ):
        raise ValueError("external effect authority does not bind this control revision")
    probe_production_adapter_assembly(repository, contract)
    return ProductionCategory3World(
        repository,
        contract,
        scenario,
        low_level_effects=low_level_effects,
        authority=authority,
        fixed_tick=fixed_tick,
    )


def build_production_shadow_assembly(
    repository: Path,
    contract: T09ProviderContract,
    scenario: FakeScenario,
    *,
    fixed_tick: int = 1000,
) -> ProductionCategory3World:
    """Build production wrappers over the only low-level effects shipped in PR 1."""

    effects = DeterministicShadowEffects.create(scenario)
    authority = mint_shadow_effect_authority(source="validated-production-shadow")
    return build_production_adapter_assembly(
        repository,
        contract,
        scenario,
        low_level_effects=effects,
        authority=authority,
        fixed_tick=fixed_tick,
    )
