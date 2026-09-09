"""Writer consumption of campaign capacity owned by the shared budget boundary.

This module makes no policy decisions. The production controller supplies the
admission callback; a writer receives only its finite, single-write allowance.
Historical standalone callers retain their explicit unbound context.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class CampaignWriterRole(StrEnum):
    PROVIDER_RECORD = "provider-record"
    PROVIDER_JOURNAL = "provider-journal"
    RETAINED_COPY = "retained-copy"
    CLEANUP_JOURNAL = "cleanup-journal"
    CLEANUP_RECEIPT = "cleanup-receipt"


@dataclass
class CampaignWriteAllowance:
    path: Path
    role: CampaignWriterRole
    granted: int
    consume: Callable[[int], None]
    observed: int = 0
    cleanup: bool = False
    closed: bool = False

    def observe(self, count: int) -> None:
        if (
            self.closed
            or type(count) is not int
            or count < 0
            or self.observed + count > self.granted
        ):
            raise RuntimeError("campaign writer exceeded its own admitted allowance")
        self.consume(count)
        self.observed += count


class CampaignOutputAdmission(Protocol):
    def __call__(
        self, path: Path, size: int, role: CampaignWriterRole
    ) -> CampaignWriteAllowance: ...


_ADMISSION: ContextVar[CampaignOutputAdmission | None] = ContextVar(
    "gic_campaign_output_admission", default=None
)
_CLEANUP: ContextVar[bool] = ContextVar("gic_campaign_cleanup_output", default=False)


@contextmanager
def campaign_cleanup_scope() -> Iterator[None]:
    token = _CLEANUP.set(True)
    try:
        yield
    finally:
        _CLEANUP.reset(token)


def campaign_cleanup_active() -> bool:
    return _CLEANUP.get()


@contextmanager
def campaign_output_scope(admission: CampaignOutputAdmission) -> Iterator[None]:
    token = _ADMISSION.set(admission)
    try:
        yield
    finally:
        _ADMISSION.reset(token)


def admit_campaign_write(
    path: Path, size: int, role: CampaignWriterRole
) -> CampaignWriteAllowance | None:
    if type(size) is not int or size < 0:
        raise ValueError("campaign writer length must be a non-negative integer")
    admission = _ADMISSION.get()
    return None if admission is None else admission(path, size, role)


def observe_campaign_write(allowance: CampaignWriteAllowance | None, count: int) -> None:
    if allowance is not None:
        allowance.observe(count)
