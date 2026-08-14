"""Typed finite timing authority shared by Lambda observers and one-shot runners."""

from __future__ import annotations

from dataclasses import dataclass


class LambdaCampaignLifecycleError(ValueError):
    """One campaign's provider timing or cost limits are internally inconsistent."""


def billed_list_cost_cents(seconds: int, *, price_cents_per_hour: int = 129) -> int:
    if seconds < 0 or price_cents_per_hour <= 0:
        raise LambdaCampaignLifecycleError("provider wall or price is invalid")
    minutes = (seconds + 59) // 60
    return (minutes * price_cents_per_hour + 59) // 60


@dataclass(frozen=True, slots=True)
class ObserverLifecycleLimits:
    """Complete provider/observer timing authority for one manual campaign.

    The defaults preserve the historical T07 contract.  Successors must supply a
    complete, finite set; no workload may infer or extend its own provider window.
    """

    campaign_provider_wall_seconds: int = 3_600
    normal_termination_cutoff_seconds: int = 1_800
    cleanup_reserve_seconds: int = 900
    max_provider_cost_cents: int = 200
    price_cents_per_hour: int = 129

    def __post_init__(self) -> None:
        if (
            self.campaign_provider_wall_seconds <= 0
            or self.normal_termination_cutoff_seconds <= 0
            or self.cleanup_reserve_seconds <= 0
            or self.max_provider_cost_cents <= 0
            or self.normal_termination_cutoff_seconds + self.cleanup_reserve_seconds
            > self.campaign_provider_wall_seconds
            or billed_list_cost_cents(
                self.campaign_provider_wall_seconds,
                price_cents_per_hour=self.price_cents_per_hour,
            )
            > self.max_provider_cost_cents
        ):
            raise LambdaCampaignLifecycleError("observer lifecycle limits are inconsistent")

    @classmethod
    def t09_pragmatic_v3(cls) -> ObserverLifecycleLimits:
        return cls(
            campaign_provider_wall_seconds=14_400,
            normal_termination_cutoff_seconds=13_500,
            cleanup_reserve_seconds=900,
            max_provider_cost_cents=516,
        )

    @classmethod
    def t09_pragmatic_v4(cls) -> ObserverLifecycleLimits:
        """Retry 2 keeps the complete V3 campaign wall and cleanup envelope."""

        return cls.t09_pragmatic_v3()

    @classmethod
    def t09_pragmatic_v5(cls) -> ObserverLifecycleLimits:
        """Retry 3 keeps the complete reviewed four-hour campaign envelope."""

        return cls.t09_pragmatic_v3()

    def observer_active_seconds(
        self,
        *,
        prelaunch_seconds: int,
        post_provider_cleanup_seconds: int,
    ) -> int:
        return (
            prelaunch_seconds + self.campaign_provider_wall_seconds + post_provider_cleanup_seconds
        )


@dataclass(frozen=True, slots=True)
class Retry4LifecycleLimits:
    """Three-clock authority for the pragmatic Retry 4 calibration campaign."""

    preflight_wall_seconds: int = 3_600
    failed_preflight_termination_dispatch_seconds: int = 300
    empirical_campaign_wall_seconds: int = 14_400
    empirical_cleanup_reserve_seconds: int = 900
    empirical_termination_cutoff_seconds: int = 13_500
    maximum_successful_host_active_seconds: int = 18_000
    maximum_cumulative_active_seconds: int = 21_600
    maximum_provider_cost_cents: int = 800
    price_cents_per_hour: int = 129
    maximum_launches: int = 2
    maximum_simultaneous_instances: int = 1
    persistent_filesystems: int = 0

    def __post_init__(self) -> None:
        if (
            self.preflight_wall_seconds != 3_600
            or self.failed_preflight_termination_dispatch_seconds != 300
            or self.empirical_campaign_wall_seconds != 14_400
            or self.empirical_cleanup_reserve_seconds != 900
            or self.empirical_termination_cutoff_seconds != 13_500
            or self.empirical_termination_cutoff_seconds + self.empirical_cleanup_reserve_seconds
            != self.empirical_campaign_wall_seconds
            or self.maximum_successful_host_active_seconds
            != self.preflight_wall_seconds + self.empirical_campaign_wall_seconds
            or self.maximum_cumulative_active_seconds != 21_600
            or self.maximum_provider_cost_cents != 800
            or self.price_cents_per_hour != 129
            or self.maximum_launches != 2
            or self.maximum_simultaneous_instances != 1
            or self.persistent_filesystems != 0
            or billed_list_cost_cents(
                self.maximum_cumulative_active_seconds,
                price_cents_per_hour=self.price_cents_per_hour,
            )
            > self.maximum_provider_cost_cents
        ):
            raise LambdaCampaignLifecycleError("Retry 4 lifecycle limits are inconsistent")

    @staticmethod
    def _elapsed(*, started_at_epoch: float, now_epoch: float, label: str) -> float:
        elapsed = now_epoch - started_at_epoch
        if started_at_epoch <= 0 or elapsed < 0:
            raise LambdaCampaignLifecycleError(f"{label} clock is unavailable or in the future")
        return elapsed

    def preflight_elapsed(self, *, launched_at_epoch: float, now_epoch: float) -> float:
        return self._elapsed(
            started_at_epoch=launched_at_epoch,
            now_epoch=now_epoch,
            label="provider preflight",
        )

    def preflight_remaining(self, *, launched_at_epoch: float, now_epoch: float) -> float:
        return max(
            0.0,
            self.preflight_wall_seconds
            - self.preflight_elapsed(
                launched_at_epoch=launched_at_epoch,
                now_epoch=now_epoch,
            ),
        )

    def preflight_timed_out(self, *, launched_at_epoch: float, now_epoch: float) -> bool:
        return (
            self.preflight_elapsed(
                launched_at_epoch=launched_at_epoch,
                now_epoch=now_epoch,
            )
            >= self.preflight_wall_seconds
        )

    def empirical_elapsed(self, *, empirical_started_at_epoch: float, now_epoch: float) -> float:
        return self._elapsed(
            started_at_epoch=empirical_started_at_epoch,
            now_epoch=now_epoch,
            label="empirical campaign",
        )

    def empirical_remaining(
        self,
        *,
        empirical_started_at_epoch: float,
        now_epoch: float,
    ) -> float:
        return max(
            0.0,
            self.empirical_campaign_wall_seconds
            - self.empirical_elapsed(
                empirical_started_at_epoch=empirical_started_at_epoch,
                now_epoch=now_epoch,
            ),
        )

    def admit_empirical_attempt(
        self,
        *,
        empirical_started_at_epoch: float,
        now_epoch: float,
        attempt_hard_wall_seconds: int,
    ) -> bool:
        if attempt_hard_wall_seconds <= 0:
            raise LambdaCampaignLifecycleError("attempt wall must be positive")
        return (
            self.empirical_remaining(
                empirical_started_at_epoch=empirical_started_at_epoch,
                now_epoch=now_epoch,
            )
            >= attempt_hard_wall_seconds + self.empirical_cleanup_reserve_seconds
        )

    def empirical_termination_due(
        self,
        *,
        empirical_started_at_epoch: float,
        now_epoch: float,
    ) -> bool:
        return (
            self.empirical_elapsed(
                empirical_started_at_epoch=empirical_started_at_epoch,
                now_epoch=now_epoch,
            )
            >= self.empirical_termination_cutoff_seconds
        )

    def cumulative_active_seconds(
        self,
        *,
        prior_active_seconds: float,
        launched_at_epoch: float,
        now_epoch: float,
    ) -> float:
        if prior_active_seconds < 0:
            raise LambdaCampaignLifecycleError("prior active Lambda time is negative")
        return prior_active_seconds + self.preflight_elapsed(
            launched_at_epoch=launched_at_epoch,
            now_epoch=now_epoch,
        )

    def cumulative_cost_usd(self, *, cumulative_active_seconds: float) -> float:
        if cumulative_active_seconds < 0:
            raise LambdaCampaignLifecycleError("cumulative active Lambda time is negative")
        return cumulative_active_seconds * self.price_cents_per_hour / 100.0 / 3_600.0

    def active_caps_available(self, *, cumulative_active_seconds: float) -> bool:
        return (
            cumulative_active_seconds <= self.maximum_cumulative_active_seconds
            and self.cumulative_cost_usd(cumulative_active_seconds=cumulative_active_seconds)
            <= self.maximum_provider_cost_cents / 100.0
        )
