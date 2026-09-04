from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import cast

import pytest
import yaml

from giclab.control.adapters import AdapterFailure
from giclab.control.effects import checked_deadline, finite_time
from giclab.control.production import ProductionCategory3World, _ValidatedRuntimeClock
from giclab.control.shadow_effects import (
    DeterministicLowLevelEffects,
    ShadowFaultPlan,
    build_production_shadow_assembly,
)
from giclab.harness import t09_model_metadata_receipt as metadata
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[2]


class _SystemRuntimeClock:
    def __init__(self) -> None:
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        return time.monotonic()

    def wall_time(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        time.sleep(seconds)


class _SequenceClock:
    def __init__(self, *, monotonic: list[float], wall: list[float]) -> None:
        self.monotonic_values = monotonic
        self.wall_values = wall
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        return self.monotonic_values.pop(0)

    def wall_time(self) -> float:
        return self.wall_values.pop(0)

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)


class _RecordingMetadataChannel:
    def __init__(
        self,
        *,
        expected_sha256: str,
        response_clock: object,
        reject: bool = False,
    ) -> None:
        self.expected_sha256 = expected_sha256
        self.response_clock = response_clock
        self.reject = reject
        self.requests: list[tuple[str, float]] = []
        self.credential_buffers: list[bytearray] = []

    def get_model_metadata(
        self,
        *,
        model_id: str,
        credential: bytearray,
        started_at: float,
    ) -> metadata.ModelMetadataResponse:
        self.requests.append((model_id, started_at))
        self.credential_buffers.append(credential)
        observed = hashlib.sha256(bytes(credential)).hexdigest()
        if self.reject or observed != self.expected_sha256:
            raise metadata.ModelMetadataReceiptError(
                "test metadata channel rejected the supplied credential"
            )
        wall_time = self.response_clock.wall_time
        body = (json.dumps({"id": model_id}, separators=(",", ":"), sort_keys=True) + "\n").encode()
        return metadata.ModelMetadataResponse(
            status=200,
            body=body,
            response_completed_at=wall_time(),
        )


def _metadata_world(
    name: str,
) -> tuple[ProductionCategory3World, DeterministicLowLevelEffects]:
    world = build_production_shadow_assembly(
        ROOT,
        V16_PROVIDER_CONTRACT,
        ShadowFaultPlan(name),
        control_binding_semantic_sha256="a" * 64,
        fixed_tick=3_000,
    )
    effects = cast(DeterministicLowLevelEffects, world.low_level_effects)
    return world, effects


def test_live_shaped_runtime_clock_delegates_real_time_and_sleep() -> None:
    source = _SystemRuntimeClock()
    clock = _ValidatedRuntimeClock(source)
    first_monotonic = clock.monotonic()
    first_wall = clock.wall_time()
    clock.sleep(0.0)
    assert source.sleep_calls == [0.0]
    assert clock.sleep_calls == [0.0]
    assert clock.monotonic_samples[-1] >= first_monotonic
    assert clock.wall_samples[-1] >= first_wall


@pytest.mark.parametrize(
    ("domain", "source", "error"),
    [
        ("monotonic", _SequenceClock(monotonic=[2.0, 1.0], wall=[10.0]), "moved backward"),
        ("wall_time", _SequenceClock(monotonic=[1.0], wall=[2.0, 1.0]), "moved backward"),
        ("monotonic", _SequenceClock(monotonic=[math.nan], wall=[1.0]), "finite"),
        ("wall_time", _SequenceClock(monotonic=[1.0], wall=[math.inf]), "finite"),
    ],
)
def test_runtime_clock_rejects_backward_or_nonfinite_samples(
    domain: str,
    source: _SequenceClock,
    error: str,
) -> None:
    clock = _ValidatedRuntimeClock(source)
    method = getattr(clock, domain)
    if "backward" in error:
        method()
    with pytest.raises((AdapterFailure, ValueError), match=error):
        method()


def test_time_helpers_reject_cross_domain_invalidity_and_overflow() -> None:
    for value in (-1.0, math.nan, math.inf, -math.inf, True, "1"):
        with pytest.raises(ValueError, match="finite and non-negative"):
            finite_time(value, label="test time")
    with pytest.raises(ValueError, match="overflowed"):
        checked_deadline(1e308, 1e308, label="test")


def test_noncanonical_parser_credential_reaches_injected_channel_and_is_destroyed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, effects = _metadata_world("credential-seam-success")
    credential = ("runtime-created-noncanonical-" + hashlib.sha256(b"seed").hexdigest()).encode()
    returned: list[bytearray] = []

    def read_model_secret() -> bytearray:
        value = bytearray(credential)
        returned.append(value)
        return value

    channel = _RecordingMetadataChannel(
        expected_sha256=hashlib.sha256(credential).hexdigest(),
        response_clock=effects.runtime_clock(),
    )
    monkeypatch.setattr(effects, "read_model_secret", read_model_secret)
    monkeypatch.setattr(effects, "_metadata_channel", channel)
    world.read()
    assert len(returned) == 1 and not any(returned[0])
    envelope = world.request(contract_version=V16_PROVIDER_CONTRACT.version)
    assert len(channel.requests) == 1
    assert channel.requests[0][0] == metadata.MODEL_METADATA_MODEL_ID
    assert channel.requests[0][1] == envelope.issued_wall_time
    assert len(channel.credential_buffers) == 1
    assert not any(channel.credential_buffers[0])
    assert world.is_fresh(envelope) is True


def test_mutated_credential_fails_inside_channel_and_buffer_is_destroyed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, effects = _metadata_world("credential-seam-failure")
    credential = ("runtime-created-mutated-" + hashlib.sha256(b"different").hexdigest()).encode()
    returned: list[bytearray] = []

    def read_model_secret() -> bytearray:
        value = bytearray(credential)
        returned.append(value)
        return value

    channel = _RecordingMetadataChannel(
        expected_sha256="f" * 64,
        response_clock=effects.runtime_clock(),
        reject=True,
    )
    monkeypatch.setattr(effects, "read_model_secret", read_model_secret)
    monkeypatch.setattr(effects, "_metadata_channel", channel)
    world.read()
    assert not any(returned[0])
    with pytest.raises(AdapterFailure) as caught:
        world.request(contract_version=V16_PROVIDER_CONTRACT.version)
    assert credential.decode() not in str(caught.value)
    assert len(channel.requests) == 1
    assert len(channel.credential_buffers) == 1
    assert not any(channel.credential_buffers[0])


def test_plan_and_condition_budgets_reject_drift_and_cross_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, _effects = _metadata_world("package-budget-mutations")
    world._load_runtime_package()
    execution = world._execution_contract
    budget = world._runtime_budget
    assert execution is not None and budget is not None
    assert budget.aggregate_caps.max_model_call_attempts == 4_620
    assert all(caps.max_model_call_attempts == 1_155 for caps in budget.condition_caps.values())

    reactive = execution.attempt(V16_PROVIDER_CONTRACT.run_ids[0])
    simulative = execution.attempt(V16_PROVIDER_CONTRACT.run_ids[1])
    with pytest.raises(AdapterFailure, match="identity"):
        world._condition_plan_caps(
            ROOT / simulative.condition_plan_path,
            simulative.condition_plan_sha256,
            run_id=reactive.run_id,
            condition=reactive.condition,
            plan_sha256=V16_PROVIDER_CONTRACT.expected_plan_sha256,
            model_revision=budget.model_revision,
        )

    retained = yaml.safe_load

    def drift_plan(value: object) -> object:
        document = retained(value)
        if isinstance(document, dict) and document.get("plan_id") == V16_PROVIDER_CONTRACT.plan_id:
            mutated = cast(dict[str, object], document["budget"])
            mutated["max_model_calls"] = 4_621
        return document

    monkeypatch.setattr("giclab.control.production.yaml.safe_load", drift_plan)
    with pytest.raises(AdapterFailure, match="budget drifted"):
        world._load_plan_budget(execution)
