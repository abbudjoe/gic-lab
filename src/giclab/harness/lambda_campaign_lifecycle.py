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

    def observer_active_seconds(
        self,
        *,
        prelaunch_seconds: int,
        post_provider_cleanup_seconds: int,
    ) -> int:
        return (
            prelaunch_seconds + self.campaign_provider_wall_seconds + post_provider_cleanup_seconds
        )
