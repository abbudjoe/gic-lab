"""Hard run-budget accounting and immutable stop decisions."""

from __future__ import annotations

import math
from dataclasses import replace

from .models import BudgetUsage, RunBudget


class BudgetExceeded(RuntimeError):
    """Raised before or during an action that would exceed a hard budget."""


class BudgetContractChanged(RuntimeError):
    """Raised when a caller tries to replace limits after accounting begins."""


class BudgetGuard:
    """Mutable usage ledger bound permanently to immutable limits."""

    __slots__ = ("_limits", "_usage")

    def __setattr__(self, name: str, value: object) -> None:
        if name in self.__slots__ and hasattr(self, name):
            raise AttributeError(f"budget guard state is write-owned: {name}")
        object.__setattr__(self, name, value)

    def __init__(self, limits: RunBudget) -> None:
        self._limits = limits
        self._usage = BudgetUsage()

    @property
    def limits(self) -> RunBudget:
        return self._limits

    @property
    def usage(self) -> BudgetUsage:
        return self._usage

    @property
    def remaining_wall_seconds(self) -> float:
        return max(0.0, self._limits.max_wall_seconds - self._usage.wall_seconds)

    def assert_limits_unchanged(self, limits: RunBudget) -> None:
        if limits != self._limits:
            raise BudgetContractChanged("run budget limits are immutable after guard creation")

    def assert_projected(
        self,
        *,
        wall_seconds: float = 0.0,
        cost_usd: float = 0.0,
        gpu_hours: float = 0.0,
        model_tokens: int = 0,
        tool_calls: int = 0,
        output_bytes: int = 0,
    ) -> BudgetUsage:
        candidate = self._candidate(
            wall_seconds=wall_seconds,
            cost_usd=cost_usd,
            gpu_hours=gpu_hours,
            model_tokens=model_tokens,
            tool_calls=tool_calls,
            output_bytes=output_bytes,
        )
        self.assert_within(candidate)
        return candidate

    def record(
        self,
        *,
        wall_seconds: float = 0.0,
        cost_usd: float = 0.0,
        gpu_hours: float = 0.0,
        model_tokens: int = 0,
        tool_calls: int = 0,
        output_bytes: int = 0,
    ) -> BudgetUsage:
        candidate = self.assert_projected(
            wall_seconds=wall_seconds,
            cost_usd=cost_usd,
            gpu_hours=gpu_hours,
            model_tokens=model_tokens,
            tool_calls=tool_calls,
            output_bytes=output_bytes,
        )
        object.__setattr__(self, "_usage", candidate)
        return candidate

    def _candidate(
        self,
        *,
        wall_seconds: float,
        cost_usd: float,
        gpu_hours: float,
        model_tokens: int,
        tool_calls: int,
        output_bytes: int,
    ) -> BudgetUsage:
        floats = {
            "wall_seconds": wall_seconds,
            "cost_usd": cost_usd,
            "gpu_hours": gpu_hours,
        }
        for label, value in floats.items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{label} increment must be finite and non-negative")
        for label, value in {
            "model_tokens": model_tokens,
            "tool_calls": tool_calls,
            "output_bytes": output_bytes,
        }.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} increment must be a non-negative integer")
        return replace(
            self._usage,
            wall_seconds=self._usage.wall_seconds + wall_seconds,
            cost_usd=self._usage.cost_usd + cost_usd,
            gpu_hours=self._usage.gpu_hours + gpu_hours,
            model_tokens=self._usage.model_tokens + model_tokens,
            tool_calls=self._usage.tool_calls + tool_calls,
            output_bytes=self._usage.output_bytes + output_bytes,
        )

    def assert_within(self, usage: BudgetUsage | None = None) -> None:
        current = usage or self._usage
        violations: list[str] = []
        if current.wall_seconds > self._limits.max_wall_seconds:
            violations.append("wall_seconds")
        if current.cost_usd > self._limits.max_cost_usd:
            violations.append("cost_usd")
        if current.gpu_hours > self._limits.max_gpu_hours:
            violations.append("gpu_hours")
        if (
            self._limits.max_model_tokens is not None
            and current.model_tokens > self._limits.max_model_tokens
        ):
            violations.append("model_tokens")
        if (
            self._limits.max_tool_calls is not None
            and current.tool_calls > self._limits.max_tool_calls
        ):
            violations.append("tool_calls")
        if current.output_bytes > self._limits.max_output_bytes:
            violations.append("output_bytes")
        if violations:
            raise BudgetExceeded("budget exceeded: " + ", ".join(violations))
