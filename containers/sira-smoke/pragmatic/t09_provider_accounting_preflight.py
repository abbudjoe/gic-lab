#!/usr/bin/env python3
"""Exact-container fake-transport regression for T09 provider accounting."""

from __future__ import annotations

import argparse
import json
import os
import platform
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

from giclab.harness.sira_gate_a import (
    SIRA_MODEL_REVISION,
    ImmutableModelRouting,
    ModelRole,
    ProviderBudgetBoundary,
    ProviderBudgetExceeded,
    ProviderCallTerminalState,
    ProviderFailureDisposition,
    ProviderRequest,
    ProviderResponseUsage,
    aggregate_caps,
    condition_caps,
)


class SyntheticProviderError(RuntimeError):
    """Purpose-built known provider failure with no private payload."""


def _request() -> ProviderRequest:
    return ProviderRequest(
        role=ModelRole.CRITIC,
        model=SIRA_MODEL_REVISION,
        input_tokens=10,
        max_output_tokens=20,
    )


def _success(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
    return "synthetic", ProviderResponseUsage(10, 2, 4, "default")


def _write_exclusive(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def run(output: Path) -> None:
    receipts: list[dict[str, object]] = []
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=condition_caps("simulative"),
        persist_accounting=lambda document: receipts.append(dict(document)),
    )
    for index in range(30):
        boundary.invoke(
            _request(),
            _success,
            call_id=f"EXACT-CALL-{index:04d}",
        )
    for index in range(30, 33):
        with suppress(SyntheticProviderError):
            boundary.invoke(
                _request(),
                lambda _: (_ for _ in ()).throw(SyntheticProviderError("synthetic")),
                call_id=f"EXACT-CALL-{index:04d}",
                classify_failure=lambda _: ProviderFailureDisposition.PROVIDER_ERROR,
            )
    accounting = boundary.accounting_document()
    if (
        accounting["unreconciled_provider_attempts"] != 0
        or accounting["unknown_outcomes"] != 0
        or accounting["terminal_counts"]["sent_response_reconciled"] != 30
        or accounting["terminal_counts"]["sent_provider_error_reconciled"] != 3
    ):
        raise RuntimeError("33/30/3 exact-container accounting regression failed")

    constrained = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=replace(
            aggregate_caps(),
            max_input_tokens=10,
            max_output_tokens=10,
            max_total_tokens=10,
        ),
        condition_caps=replace(
            condition_caps("simulative"),
            max_input_tokens=10,
            max_output_tokens=10,
            max_total_tokens=10,
        ),
    )
    entered = threading.Event()
    release = threading.Event()
    thread_errors: list[str] = []

    def slow(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        entered.set()
        release.wait(timeout=5)
        return "synthetic", ProviderResponseUsage(3, 0, 1, "default")

    def owner() -> None:
        try:
            constrained.invoke(
                replace(_request(), input_tokens=3, max_output_tokens=3),
                slow,
            )
        except Exception as exc:
            thread_errors.append(type(exc).__name__)

    thread = threading.Thread(target=owner)
    thread.start()
    if not entered.wait(timeout=5):
        raise RuntimeError("concurrent reservation owner did not enter")
    cap_rejected = False
    try:
        constrained.invoke(
            replace(_request(), input_tokens=4, max_output_tokens=4),
            _success,
        )
    except ProviderBudgetExceeded:
        cap_rejected = True
    release.set()
    thread.join(timeout=5)
    if not cap_rejected or thread.is_alive() or thread_errors:
        raise RuntimeError("concurrent reservation regression failed")

    shutdown = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=condition_caps("simulative"),
    )
    shutdown_entered = threading.Event()
    shutdown_release = threading.Event()

    def blocked(_: ProviderRequest) -> tuple[str, ProviderResponseUsage]:
        shutdown_entered.set()
        shutdown_release.wait(timeout=5)
        return _success(_request())

    shutdown_thread = threading.Thread(
        target=lambda: _ignore_failure(lambda: shutdown.invoke(_request(), blocked))
    )
    shutdown_thread.start()
    if not shutdown_entered.wait(timeout=5):
        raise RuntimeError("shutdown regression call did not enter")
    shutdown.close_in_flight(grace_seconds=0)
    if shutdown.call_records[0].terminal_state is not ProviderCallTerminalState.OUTCOME_UNKNOWN:
        raise RuntimeError("shutdown did not create a typed unknown outcome")
    shutdown_release.set()
    shutdown_thread.join(timeout=5)
    if shutdown_thread.is_alive():
        raise RuntimeError("shutdown regression thread did not close")

    _write_exclusive(
        output,
        {
            "schema_version": "0.1.0",
            "regression": "t09-provider-accounting-exact-container",
            "python_version": platform.python_version(),
            "model_revision": SIRA_MODEL_REVISION,
            "transport": "synthetic-local-no-network",
            "live_model_requests": 0,
            "task_browser_actions": 0,
            "thirty_response_three_provider_error": "passed",
            "concurrent_atomic_reservation": "passed",
            "bounded_shutdown_unknown_terminalization": "passed",
            "accounting_snapshot": accounting,
            "persistence_transition_count": len(receipts),
            "result": "passed",
        },
    )


def _ignore_failure(operation: Callable[[], object]) -> None:
    with suppress(Exception):
        operation()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(strict=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
