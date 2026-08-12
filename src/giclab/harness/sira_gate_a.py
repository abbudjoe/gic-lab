"""T07 Gate A contracts for bounded, immutable SiRA smoke execution.

This module is deliberately provider-agnostic.  It contains no OpenAI client and
cannot make a network request.  A later runtime adaptation must pass every provider
attempt through :class:`ProviderBudgetBoundary` (or the equivalent standalone runtime
boundary) and supply the actual provider usage returned by its injected client.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import TypeVar

from giclab.registry import load_yaml

SIRA_PROVIDER = "OpenAI"
SIRA_API_BASE_URL = "https://api.openai.com/v1/"
SIRA_MODEL_REVISION = "gpt-4o-2024-11-20"
SIRA_SERVICE_TIER = "default"
SIRA_SECRET_VARIABLE = "SIRA_API_KEY"
SIRA_PROFILE_PLAN_ID = "PLAN-EXP0001-SMOKE"
SIRA_UPSTREAM_COMMIT = "93fb8d72de71f9a4a13419670adeb34d93cf7acd"


class GateAContractError(ValueError):
    """Raised when a planned SiRA run violates a Gate A contract."""


class ProviderBudgetExceeded(RuntimeError):
    """Raised before a provider attempt or while reconciling its response."""


class ModelRole(StrEnum):
    """All model-selection surfaces used by the pinned SiRA agent."""

    DEFAULT = "default"
    ENCODER = "encoder"
    MEMORY = "memory"
    POLICY = "policy"
    WORLD_MODEL = "world_model"
    CRITIC = "critic"
    ACTOR = "actor"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class ImmutableModelRouting:
    """Complete role routing with no provider or model fallback."""

    routes: Mapping[ModelRole, str]
    provider: str = SIRA_PROVIDER
    api_base_url: str = SIRA_API_BASE_URL
    provider_fallback_enabled: bool = False

    def __post_init__(self) -> None:
        if self.provider != SIRA_PROVIDER:
            raise GateAContractError(f"provider must be exactly {SIRA_PROVIDER}")
        if self.api_base_url != SIRA_API_BASE_URL:
            raise GateAContractError(f"API base URL must be exactly {SIRA_API_BASE_URL}")
        if self.provider_fallback_enabled:
            raise GateAContractError("provider fallback must be disabled")
        copied = dict(self.routes)
        if set(copied) != set(ModelRole):
            missing = sorted(role.value for role in set(ModelRole) - set(copied))
            extra = sorted(str(role) for role in set(copied) - set(ModelRole))
            raise GateAContractError(
                f"model routing must cover every role; missing={missing}, extra={extra}"
            )
        bad = sorted(role.value for role, model in copied.items() if model != SIRA_MODEL_REVISION)
        if bad:
            raise GateAContractError(
                "every SiRA model role must use the immutable revision; invalid=" + ", ".join(bad)
            )
        object.__setattr__(self, "routes", MappingProxyType(copied))

    @classmethod
    def locked(cls) -> ImmutableModelRouting:
        return cls(routes={role: SIRA_MODEL_REVISION for role in ModelRole})

    def document(self) -> dict[str, object]:
        return {
            "schema_version": "0.1.0",
            "provider": self.provider,
            "api_base_url": self.api_base_url,
            "provider_fallback_enabled": self.provider_fallback_enabled,
            "routes": {role.value: self.routes[role] for role in ModelRole},
        }

    def sha256(self) -> str:
        encoded = json.dumps(self.document(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ProviderBudgetCaps:
    """Hard caps for one provider/accounting scope."""

    max_cost_usd: float
    max_input_tokens: int
    max_cached_input_tokens: int
    max_output_tokens: int
    max_total_tokens: int
    max_model_call_attempts: int
    max_wall_seconds: int
    max_browser_actions: int
    max_output_bytes: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.max_cost_usd) or self.max_cost_usd < 0:
            raise GateAContractError("max_cost_usd must be finite and non-negative")
        for name in (
            "max_input_tokens",
            "max_cached_input_tokens",
            "max_output_tokens",
            "max_total_tokens",
            "max_model_call_attempts",
            "max_wall_seconds",
            "max_browser_actions",
            "max_output_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise GateAContractError(f"{name} must be a non-negative integer")
        if self.max_wall_seconds == 0 or self.max_output_bytes == 0:
            raise GateAContractError("wall-time and output-byte caps must be positive")


@dataclass(frozen=True, slots=True)
class ProviderBudgetUsage:
    """Observed provider, browser, and retained-output usage."""

    cost_usd: float = 0.0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model_call_attempts: int = 0
    default_service_tier_responses: int = 0
    browser_actions: int = 0
    output_bytes: int = 0

    def __post_init__(self) -> None:
        if not math.isfinite(self.cost_usd) or self.cost_usd < 0:
            raise GateAContractError("observed cost must be finite and non-negative")
        for name in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "total_tokens",
            "model_call_attempts",
            "default_service_tier_responses",
            "browser_actions",
            "output_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise GateAContractError(f"observed {name} must be a non-negative integer")
        if self.cached_input_tokens > self.input_tokens:
            raise GateAContractError("cached input tokens cannot exceed input tokens")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise GateAContractError("total tokens must equal input plus output tokens")
        if self.default_service_tier_responses > self.model_call_attempts:
            raise GateAContractError("default-tier responses cannot exceed provider call attempts")


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    """One provider attempt with an explicit worst-case envelope."""

    role: ModelRole
    model: str
    input_tokens: int
    max_output_tokens: int
    service_tier: str = SIRA_SERVICE_TIER
    implicit_transport_retries: int = 0
    retry_kind: str = "initial"

    def __post_init__(self) -> None:
        if not isinstance(self.role, ModelRole):
            raise GateAContractError("provider request role must be typed")
        if self.model != SIRA_MODEL_REVISION:
            raise GateAContractError("provider request uses an unapproved model identity")
        if type(self.input_tokens) is not int or self.input_tokens < 0:
            raise GateAContractError("request input_tokens must be non-negative")
        if type(self.max_output_tokens) is not int or self.max_output_tokens < 0:
            raise GateAContractError("request max_output_tokens must be non-negative")
        if self.service_tier != SIRA_SERVICE_TIER:
            raise GateAContractError("provider request service_tier must be exactly default")
        if self.implicit_transport_retries != 0:
            raise GateAContractError(
                "implicit provider retries are forbidden; retry through the budget boundary"
            )
        if self.retry_kind not in {"initial", "provider", "parser"}:
            raise GateAContractError("retry_kind must be initial, provider, or parser")


@dataclass(frozen=True, slots=True)
class ProviderResponseUsage:
    """Usage returned by one successful fake or later live provider response."""

    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    service_tier: str

    def __post_init__(self) -> None:
        for name in ("input_tokens", "cached_input_tokens", "output_tokens"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise GateAContractError(f"response {name} must be non-negative")
        if self.cached_input_tokens > self.input_tokens:
            raise GateAContractError("cached response tokens cannot exceed input tokens")
        if self.service_tier != SIRA_SERVICE_TIER:
            raise GateAContractError("provider response service_tier must be exactly default")


T = TypeVar("T")


class ProviderBudgetBoundary:
    """Single preflight/reconciliation boundary for every provider attempt.

    Failed sends still consume a model-call attempt.  Parser and explicit provider
    retries call :meth:`invoke` again and therefore share the same ledgers.  The class
    has no retry loop and cannot silently retry a provider operation.
    """

    INPUT_RATE_PER_MILLION = 2.50
    CACHED_INPUT_RATE_PER_MILLION = 1.25
    OUTPUT_RATE_PER_MILLION = 10.00

    def __init__(
        self,
        *,
        routing: ImmutableModelRouting,
        aggregate_caps: ProviderBudgetCaps,
        condition_caps: ProviderBudgetCaps,
        monotonic: Callable[[], float] = time.monotonic,
        persist: Callable[[ProviderBudgetUsage, int], None] | None = None,
    ) -> None:
        self.routing = routing
        self.aggregate_caps = aggregate_caps
        self.condition_caps = condition_caps
        self.aggregate_usage = ProviderBudgetUsage()
        self.condition_usage = ProviderBudgetUsage()
        self._aggregate_reserved = ProviderBudgetUsage()
        self._condition_reserved = ProviderBudgetUsage()
        self._lock = threading.RLock()
        self._monotonic = monotonic
        self._started = monotonic()
        self.unreconciled_provider_attempts = 0
        self._persist = persist

    def _persist_state(self) -> None:
        if self._persist is not None:
            self._persist(self.condition_usage, self.unreconciled_provider_attempts)

    @staticmethod
    def _cost(input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
        uncached = input_tokens - cached_tokens
        return (
            uncached * ProviderBudgetBoundary.INPUT_RATE_PER_MILLION
            + cached_tokens * ProviderBudgetBoundary.CACHED_INPUT_RATE_PER_MILLION
            + output_tokens * ProviderBudgetBoundary.OUTPUT_RATE_PER_MILLION
        ) / 1_000_000

    def _assert_usage(
        self,
        usage: ProviderBudgetUsage,
        caps: ProviderBudgetCaps,
        *,
        scope: str,
    ) -> None:
        elapsed = self._monotonic() - self._started
        violations: list[str] = []
        if usage.cost_usd > caps.max_cost_usd:
            violations.append("cost_usd")
        for field in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "total_tokens",
            "model_call_attempts",
            "browser_actions",
            "output_bytes",
        ):
            if getattr(usage, field) > getattr(caps, f"max_{field}"):
                violations.append(field)
        if elapsed > caps.max_wall_seconds:
            violations.append("wall_seconds")
        if violations:
            raise ProviderBudgetExceeded(f"{scope} budget exceeded: " + ", ".join(violations))

    @staticmethod
    def _add_usage(
        usage: ProviderBudgetUsage,
        *,
        cost_usd: float = 0.0,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        model_call_attempts: int = 0,
        default_service_tier_responses: int = 0,
        browser_actions: int = 0,
        output_bytes: int = 0,
    ) -> ProviderBudgetUsage:
        return ProviderBudgetUsage(
            cost_usd=usage.cost_usd + cost_usd,
            input_tokens=usage.input_tokens + input_tokens,
            cached_input_tokens=usage.cached_input_tokens + cached_input_tokens,
            output_tokens=usage.output_tokens + output_tokens,
            total_tokens=usage.total_tokens + input_tokens + output_tokens,
            model_call_attempts=usage.model_call_attempts + model_call_attempts,
            default_service_tier_responses=(
                usage.default_service_tier_responses + default_service_tier_responses
            ),
            browser_actions=usage.browser_actions + browser_actions,
            output_bytes=usage.output_bytes + output_bytes,
        )

    def invoke(
        self,
        request: ProviderRequest,
        send: Callable[[ProviderRequest], tuple[T, ProviderResponseUsage]],
    ) -> T:
        """Preflight one maximum envelope, send once, then reconcile actual usage."""

        if self.routing.routes[request.role] != request.model:
            raise GateAContractError("provider request does not match immutable role routing")
        worst_cost = self._cost(request.input_tokens, 0, request.max_output_tokens)
        reservation = ProviderBudgetUsage(
            cost_usd=worst_cost,
            input_tokens=request.input_tokens,
            output_tokens=request.max_output_tokens,
            total_tokens=request.input_tokens + request.max_output_tokens,
        )
        with self._lock:
            for scope, current, reserved, caps in (
                (
                    "aggregate",
                    self.aggregate_usage,
                    self._aggregate_reserved,
                    self.aggregate_caps,
                ),
                (
                    "condition",
                    self.condition_usage,
                    self._condition_reserved,
                    self.condition_caps,
                ),
            ):
                projected = self._add_usage(
                    self._sum_usage(current, reserved),
                    cost_usd=reservation.cost_usd,
                    input_tokens=reservation.input_tokens,
                    output_tokens=reservation.output_tokens,
                    model_call_attempts=1,
                )
                self._assert_usage(projected, caps, scope=scope)
            object.__setattr__(
                self,
                "aggregate_usage",
                self._add_usage(
                    self.aggregate_usage,
                    cost_usd=reservation.cost_usd,
                    input_tokens=reservation.input_tokens,
                    output_tokens=reservation.output_tokens,
                    model_call_attempts=1,
                ),
            )
            object.__setattr__(
                self,
                "condition_usage",
                self._add_usage(
                    self.condition_usage,
                    cost_usd=reservation.cost_usd,
                    input_tokens=reservation.input_tokens,
                    output_tokens=reservation.output_tokens,
                    model_call_attempts=1,
                ),
            )
            self._persist_state()
        try:
            result, actual = send(request)
        except Exception:
            with self._lock:
                self.unreconciled_provider_attempts += 1
                self._persist_state()
                self._assert_usage(self.aggregate_usage, self.aggregate_caps, scope="aggregate")
                self._assert_usage(self.condition_usage, self.condition_caps, scope="condition")
            raise
        declared_maximum_exceeded = (
            actual.input_tokens > request.input_tokens
            or actual.output_tokens > request.max_output_tokens
        )
        actual_cost = self._cost(
            actual.input_tokens, actual.cached_input_tokens, actual.output_tokens
        )
        with self._lock:
            object.__setattr__(
                self,
                "aggregate_usage",
                self._add_usage(
                    self._subtract_usage(self.aggregate_usage, reservation),
                    cost_usd=actual_cost,
                    input_tokens=actual.input_tokens,
                    cached_input_tokens=actual.cached_input_tokens,
                    output_tokens=actual.output_tokens,
                    default_service_tier_responses=1,
                ),
            )
            object.__setattr__(
                self,
                "condition_usage",
                self._add_usage(
                    self._subtract_usage(self.condition_usage, reservation),
                    cost_usd=actual_cost,
                    input_tokens=actual.input_tokens,
                    cached_input_tokens=actual.cached_input_tokens,
                    output_tokens=actual.output_tokens,
                    default_service_tier_responses=1,
                ),
            )
            self._assert_usage(self.aggregate_usage, self.aggregate_caps, scope="aggregate")
            self._assert_usage(self.condition_usage, self.condition_caps, scope="condition")
            self._persist_state()
        if declared_maximum_exceeded:
            raise ProviderBudgetExceeded(
                "provider usage exceeded its declared request maximum after reconciliation"
            )
        return result

    @staticmethod
    def _sum_usage(
        first: ProviderBudgetUsage,
        second: ProviderBudgetUsage,
    ) -> ProviderBudgetUsage:
        return ProviderBudgetBoundary._add_usage(
            first,
            cost_usd=second.cost_usd,
            input_tokens=second.input_tokens,
            cached_input_tokens=second.cached_input_tokens,
            output_tokens=second.output_tokens,
            model_call_attempts=second.model_call_attempts,
            default_service_tier_responses=second.default_service_tier_responses,
            browser_actions=second.browser_actions,
            output_bytes=second.output_bytes,
        )

    @staticmethod
    def _subtract_usage(
        current: ProviderBudgetUsage,
        decrement: ProviderBudgetUsage,
    ) -> ProviderBudgetUsage:
        return ProviderBudgetUsage(
            cost_usd=current.cost_usd - decrement.cost_usd,
            input_tokens=current.input_tokens - decrement.input_tokens,
            cached_input_tokens=current.cached_input_tokens - decrement.cached_input_tokens,
            output_tokens=current.output_tokens - decrement.output_tokens,
            total_tokens=current.total_tokens - decrement.total_tokens,
            model_call_attempts=current.model_call_attempts - decrement.model_call_attempts,
            default_service_tier_responses=(
                current.default_service_tier_responses - decrement.default_service_tier_responses
            ),
            browser_actions=current.browser_actions - decrement.browser_actions,
            output_bytes=current.output_bytes - decrement.output_bytes,
        )

    def _release_reservation(self, reservation: ProviderBudgetUsage) -> None:
        object.__setattr__(
            self,
            "_aggregate_reserved",
            self._subtract_usage(self._aggregate_reserved, reservation),
        )
        object.__setattr__(
            self,
            "_condition_reserved",
            self._subtract_usage(self._condition_reserved, reservation),
        )

    def record_browser_action(self) -> None:
        self._record_nonprovider(browser_actions=1)

    def record_output_bytes(self, count: int) -> None:
        if type(count) is not int or count < 0:
            raise GateAContractError("output-byte increment must be non-negative")
        self._record_nonprovider(output_bytes=count)

    def _record_nonprovider(self, **increments: int) -> None:
        with self._lock:
            aggregate = self._add_usage(self.aggregate_usage, **increments)
            condition = self._add_usage(self.condition_usage, **increments)
            self._assert_usage(aggregate, self.aggregate_caps, scope="aggregate")
            self._assert_usage(condition, self.condition_caps, scope="condition")
            object.__setattr__(self, "aggregate_usage", aggregate)
            object.__setattr__(self, "condition_usage", condition)
            self._persist_state()


@dataclass(frozen=True, slots=True)
class SiRAAttemptLayout:
    """All evidence destinations allocated before an upstream launch."""

    root: Path
    session: Path
    source_logs: Path
    stdout: Path
    stderr: Path
    screenshots: Path
    evaluator: Path
    normalized: Path
    environment: Path
    command: Path
    cleanup: Path
    provider_ledger: Path

    @classmethod
    def planned(cls, root: Path) -> SiRAAttemptLayout:
        if not root.is_absolute():
            raise GateAContractError("attempt root must be absolute")
        if root.exists():
            raise GateAContractError("attempt root must be fresh and immutable")
        canonical = root.resolve(strict=False)
        if canonical != root:
            raise GateAContractError("attempt root must be canonical")
        return cls(
            root=root,
            session=root / "upstream-session",
            source_logs=root / "source-logs",
            stdout=root / "stdout.log",
            stderr=root / "stderr.log",
            screenshots=root / "screenshots",
            evaluator=root / "evaluator",
            normalized=root / "events.jsonl",
            environment=root / "environment.json",
            command=root / "command.json",
            cleanup=root / "cleanup.json",
            provider_ledger=root / "provider-budget.json",
        )

    def allocate(self) -> None:
        """Create the attempt root exactly once before a process can launch."""

        self.root.mkdir(mode=0o700, parents=True, exist_ok=False)
        for path in (self.session, self.source_logs, self.screenshots, self.evaluator):
            path.mkdir(mode=0o700)


@dataclass(frozen=True, slots=True)
class SiRAEnvironmentContract:
    """Planned isolated installation locations and later identity fields."""

    upstream_checkout: Path
    external_environment: Path
    playwright_cache: Path
    uv_cache: Path
    python_version: str = "3.10"
    uv_lock_sha256: str = "138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e"
    playwright_version: str = "1.39.0"
    chromium_revision: str | None = None

    def __post_init__(self) -> None:
        for label, path in (
            ("upstream checkout", self.upstream_checkout),
            ("external environment", self.external_environment),
            ("Playwright cache", self.playwright_cache),
            ("uv cache", self.uv_cache),
        ):
            if not path.is_absolute() or path.resolve(strict=False) != path:
                raise GateAContractError(f"{label} must be an absolute canonical path")
        if (
            self.external_environment == self.upstream_checkout
            or self.upstream_checkout in self.external_environment.parents
        ):
            raise GateAContractError("SiRA environment must remain outside the source checkout")
        if (
            self.playwright_cache == self.upstream_checkout
            or self.upstream_checkout in self.playwright_cache.parents
        ):
            raise GateAContractError("Playwright cache must remain outside the source checkout")
        if (
            self.uv_cache == self.upstream_checkout
            or self.upstream_checkout in self.uv_cache.parents
        ):
            raise GateAContractError("uv cache must remain outside the source checkout")
        if len({self.external_environment, self.playwright_cache, self.uv_cache}) != 3:
            raise GateAContractError("environment, browser cache, and uv cache must be distinct")

    def dependency_install_argv(self, uv_executable: Path) -> tuple[str, ...]:
        return (
            str(uv_executable),
            "sync",
            "--frozen",
            "--extra",
            "eval",
            "--project",
            str(self.upstream_checkout),
            "--python",
            self.python_version,
        )

    def browser_install_argv(self) -> tuple[str, ...]:
        return (
            str(self.external_environment / "bin/python"),
            "-m",
            "playwright",
            "install",
            "chromium",
        )

    def installation_environment_names(self) -> tuple[str, ...]:
        return ("PLAYWRIGHT_BROWSERS_PATH", "UV_CACHE_DIR", "UV_PROJECT_ENVIRONMENT")


def validate_sira_secret_names(
    *,
    requested: Sequence[str],
    inherited: Sequence[str] = (),
) -> None:
    """Validate names only; never resolve, read, print, persist, or hash values."""

    if tuple(requested) != (SIRA_SECRET_VARIABLE,):
        raise GateAContractError(f"required secret variable is exactly {SIRA_SECRET_VARIABLE}")
    forbidden = {"OPENAI_API_KEY"}.intersection(inherited)
    if forbidden:
        raise GateAContractError("OPENAI_API_KEY fallback is forbidden")
    unapproved = set(inherited).intersection({SIRA_SECRET_VARIABLE, "OPENAI_API_KEY"})
    if unapproved:
        raise GateAContractError("credential variables cannot be inherited ambiently")


@dataclass(frozen=True, slots=True)
class CanonicalChild:
    condition: str
    path: str
    sha256: str
    command_sha256: str
    attempt: int = 1

    def __post_init__(self) -> None:
        if self.condition not in {"SIRA-REACTIVE", "SIRA-SIMULATIVE"}:
            raise GateAContractError("canonical child condition is outside the smoke pair")
        if self.attempt != 1:
            raise GateAContractError(
                "Gate A seals exactly attempt 1; replacements need new authorization"
            )
        path = Path(self.path)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise GateAContractError("canonical child path must be traversal-free and relative")
        for label, digest in (("plan", self.sha256), ("command", self.command_sha256)):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise GateAContractError(
                    f"canonical child {label} hash must be a lowercase SHA-256 digest"
                )


@dataclass(frozen=True, slots=True)
class SmokeAuthorizationMaterialization:
    """Exact future authorization surface; construction does not authorize execution."""

    profile_plan_id: str
    profile_path: str
    profile_sha256: str
    giclab_commit: str
    upstream_commit: str
    protocol_sha256: str
    config_sha256: str
    environment_sha256: str
    routing_sha256: str
    children: tuple[CanonicalChild, ...]
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if self.profile_plan_id != SIRA_PROFILE_PLAN_ID:
            raise GateAContractError("authorization may target only PLAN-EXP0001-SMOKE")
        if self.execution_authorized:
            raise GateAContractError("Gate A cannot materialize live execution authorization")
        if self.upstream_commit != SIRA_UPSTREAM_COMMIT:
            raise GateAContractError("authorization must retain the pinned SiRA commit")
        if len(self.children) != 2:
            raise GateAContractError("smoke authorization requires exactly two sealed children")
        conditions = {child.condition for child in self.children}
        if conditions != {"SIRA-REACTIVE", "SIRA-SIMULATIVE"}:
            raise GateAContractError("sealed children must be the exact smoke pair")
        for label, digest in (
            ("profile_sha256", self.profile_sha256),
            ("protocol_sha256", self.protocol_sha256),
            ("config_sha256", self.config_sha256),
            ("environment_sha256", self.environment_sha256),
            ("routing_sha256", self.routing_sha256),
        ):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise GateAContractError(f"{label} must be a lowercase SHA-256 digest")
        if len(self.giclab_commit) != 40 or any(
            character not in "0123456789abcdef" for character in self.giclab_commit
        ):
            raise GateAContractError("giclab_commit must be an exact commit")

    def assert_child_allowed(
        self,
        condition: str,
        plan_sha256: str,
        command_sha256: str,
        *,
        attempt: int,
    ) -> None:
        expected = {
            (child.condition, child.sha256, child.command_sha256, child.attempt)
            for child in self.children
        }
        if (condition, plan_sha256, command_sha256, attempt) not in expected:
            raise GateAContractError("invoked child is outside the sealed canonical set")


def file_sha256(path: Path) -> str:
    """Hash one regular local contract without following a symlink."""

    if path.is_symlink() or not path.is_file():
        raise GateAContractError(f"contract path must be a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def clean_git_commit(root: Path) -> str:
    """Return the exact tracked/untracked-clean commit for authorization binding."""

    git = shutil.which("git")
    if git is None:
        raise GateAContractError("git is required to bind the GIC Lab commit")
    try:
        top = subprocess.run(
            (git, "-C", str(root), "rev-parse", "--show-toplevel"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        commit = subprocess.run(
            (git, "-C", str(root), "rev-parse", "HEAD"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            (git, "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GateAContractError("cannot bind the GIC Lab Git identity") from exc
    if Path(top).resolve(strict=True) != root.resolve(strict=True):
        raise GateAContractError("GIC Lab root must be the exact Git top level")
    if status:
        raise GateAContractError("GIC Lab checkout must be clean before authorization")
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise GateAContractError("GIC Lab HEAD is not an exact commit")
    return commit


def prepare_smoke_preauthorization(
    repository_root: Path,
    *,
    environment_sha256: str,
    routing: ImmutableModelRouting,
    command_sha256s: Mapping[str, str],
) -> SmokeAuthorizationMaterialization:
    """Hash and validate the exact still-unauthorized EXP-0001 smoke family."""

    relative_root = Path("experiments/EXP-0001-sira-simulative-vs-reactive")
    profile_relative = relative_root / "run-plans/smoke.yaml"
    protocol_relative = relative_root / "protocol.yaml"
    config_relative = relative_root / "config.yaml"
    child_paths = {
        "SIRA-REACTIVE": relative_root / "run-plans/conditions/smoke-reactive.yaml",
        "SIRA-SIMULATIVE": relative_root / "run-plans/conditions/smoke-simulative.yaml",
    }

    def load(relative: Path) -> Mapping[str, object]:
        path = repository_root / relative
        try:
            value = load_yaml(path)
        except (OSError, ValueError) as exc:
            raise GateAContractError(f"cannot load authorization contract: {relative}") from exc
        if not isinstance(value, Mapping):
            raise GateAContractError(f"authorization contract is not a mapping: {relative}")
        return value

    giclab_commit = clean_git_commit(repository_root)
    project_state = load(Path("docs/PROJECT_STATE.yaml"))
    for field in (
        "paid_compute_allowed",
        "prototype_execution_allowed",
        "benchmark_execution_allowed",
        "training_allowed",
        "cloud_mutation_allowed",
    ):
        if project_state.get(field) is not False:
            raise GateAContractError(f"project state must keep {field} false")
    authorized_profile = project_state.get("authorized_run_profile")
    if not isinstance(authorized_profile, Mapping) or any(
        authorized_profile.get(field) not in (None, [])
        for field in ("plan_id", "profile_path", "profile_sha256", "condition_plan_sha256s")
    ):
        raise GateAContractError("project state must not authorize a run profile")

    profile = load(profile_relative)
    if profile.get("plan_id") != SIRA_PROFILE_PLAN_ID:
        raise GateAContractError("smoke profile plan ID changed")
    profile_execution = profile.get("execution")
    if (
        not isinstance(profile_execution, Mapping)
        or profile_execution.get("authorized") is not False
    ):
        raise GateAContractError("Gate A profile must remain unauthorized")
    if profile.get("profile") != "smoke" or profile.get("interpretation_allowed") is not False:
        raise GateAContractError("authorization scope escaped the noninterpretable smoke")
    profile_sha256 = file_sha256(repository_root / profile_relative)
    if set(command_sha256s) != set(child_paths):
        raise GateAContractError("command hashes must cover exactly the sealed smoke pair")
    children: list[CanonicalChild] = []
    for condition, relative in child_paths.items():
        child = load(relative)
        execution = child.get("execution")
        authorization = execution.get("authorization") if isinstance(execution, Mapping) else None
        sources = child.get("sources")
        if child.get("condition") != condition:
            raise GateAContractError(f"condition plan identity changed: {condition}")
        if child.get("profile_plan_id") != SIRA_PROFILE_PLAN_ID:
            raise GateAContractError("condition plan escaped the smoke parent")
        if child.get("profile_sha256") != profile_sha256:
            raise GateAContractError("condition plan no longer binds the exact smoke profile")
        if not isinstance(authorization, Mapping) or authorization.get("authorized") is not False:
            raise GateAContractError("Gate A condition plans must remain unauthorized")
        if not isinstance(sources, Mapping):
            raise GateAContractError("condition plan source identity is missing")
        if sources.get("upstream_commit") != SIRA_UPSTREAM_COMMIT:
            raise GateAContractError("condition plan changed the SiRA pin")
        if sources.get("model_revision") != SIRA_MODEL_REVISION:
            raise GateAContractError("condition plan changed the immutable model revision")
        children.append(
            CanonicalChild(
                condition=condition,
                path=relative.as_posix(),
                sha256=file_sha256(repository_root / relative),
                command_sha256=command_sha256s[condition],
            )
        )
    return SmokeAuthorizationMaterialization(
        profile_plan_id=SIRA_PROFILE_PLAN_ID,
        profile_path=profile_relative.as_posix(),
        profile_sha256=profile_sha256,
        giclab_commit=giclab_commit,
        upstream_commit=SIRA_UPSTREAM_COMMIT,
        protocol_sha256=file_sha256(repository_root / protocol_relative),
        config_sha256=file_sha256(repository_root / config_relative),
        environment_sha256=environment_sha256,
        routing_sha256=routing.sha256(),
        children=tuple(children),
    )


def environment_identity_document(
    contract: SiRAEnvironmentContract,
    *,
    python_sha256: str,
    dependency_tree_sha256: str,
    chromium_sha256: str,
    adaptation_sha256: str,
    os_name: str = os.uname().sysname,
    architecture: str = os.uname().machine,
) -> dict[str, object]:
    """Return the later post-installation fingerprint input; values must be observed."""

    digests = {
        "python_sha256": python_sha256,
        "dependency_tree_sha256": dependency_tree_sha256,
        "chromium_sha256": chromium_sha256,
        "adaptation_sha256": adaptation_sha256,
    }
    if any(len(value) != 64 for value in digests.values()):
        raise GateAContractError("environment identity requires complete SHA-256 values")
    return {
        "schema_version": "0.1.0",
        "upstream_commit": SIRA_UPSTREAM_COMMIT,
        "upstream_checkout": str(contract.upstream_checkout),
        "external_environment": str(contract.external_environment),
        "playwright_cache": str(contract.playwright_cache),
        "uv_cache": str(contract.uv_cache),
        "python_version": contract.python_version,
        "uv_lock_sha256": contract.uv_lock_sha256,
        "playwright_version": contract.playwright_version,
        "chromium_revision": contract.chromium_revision,
        "os": os_name,
        "architecture": architecture,
        **digests,
    }


def condition_caps(mode: str) -> ProviderBudgetCaps:
    """Return exact condition caps; model-attempt maxima are source-derived."""

    if mode == "reactive":
        model_calls = 16
    elif mode == "simulative":
        model_calls = 61
    else:
        raise GateAContractError("mode must be reactive or simulative")
    return ProviderBudgetCaps(
        max_cost_usd=2.0,
        max_input_tokens=200_000,
        max_cached_input_tokens=200_000,
        max_output_tokens=200_000,
        max_total_tokens=200_000,
        max_model_call_attempts=model_calls,
        max_wall_seconds=120,
        max_browser_actions=1,
        max_output_bytes=104_857_600,
    )


def aggregate_caps() -> ProviderBudgetCaps:
    return replace(
        condition_caps("reactive"),
        max_cost_usd=4.0,
        max_input_tokens=400_000,
        max_cached_input_tokens=400_000,
        max_output_tokens=400_000,
        max_total_tokens=400_000,
        max_model_call_attempts=77,
        max_wall_seconds=240,
        max_browser_actions=2,
        max_output_bytes=209_715_200,
    )
