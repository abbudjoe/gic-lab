"""Behavioral characterizations of PR #15 review 5122766860.

These are component characterizations, not joined transaction evidence.
"""

from __future__ import annotations

import importlib.util
import json
import os
import select
import signal
import socket
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from functools import partial
from pathlib import Path

import pytest

from giclab.control import remote_execution_conformance as conformance
from giclab.control.remote_bridge import (
    MAX_BRIDGE_FRAME_BYTES,
    CanonicalFrameRelay,
    ConditionBridgeFrame,
    ConditionSessionBinding,
    FramedDuplexEndpoint,
    RemoteBridgeDisconnected,
    canonical_bytes,
)
from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("exit_code", [0, 7])
def test_r2_delayed_attach_delivers_actual_bytes_only_after_actual_exit(exit_code):
    import subprocess

    from tests.control.retained_candidate_effects import AttachAfterProcessExit

    payload = b"actual delayed fixture stdout\n" * 8192
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-c",
            "import os,sys; b=b'actual delayed fixture stdout\\n'*8192; "
            "n=0\nwhile n<len(b): n+=os.write(1,b[n:n+65536])\nsys.exit(int(sys.argv[1]))",
            str(exit_code),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 10
    carrier = AttachAfterProcessExit(process, deadline=deadline, maximum_bytes=len(payload))
    observed = bytearray()
    try:
        while True:
            assert time.monotonic() < deadline
            ready, _, _ = select.select([carrier.stdout], [], [], 0.1)
            if not ready:
                continue
            chunk = os.read(carrier.stdout.fileno(), 65536)
            # The real child was reaped before the carrier made a byte visible.
            assert process.poll() == exit_code
            if not chunk:
                break
            assert len(observed) + len(chunk) <= len(payload)
            observed.extend(chunk)
        assert carrier.wait(timeout=2) == exit_code
        assert bytes(observed) == payload
        assert carrier.observed_exit == exit_code
        assert carrier.observation["actual_process_exit"] == exit_code
        assert carrier.observation["buffered_stdout_bytes"] == len(payload)
        assert carrier.error is None and not carrier.thread.is_alive()
    finally:
        carrier.stdout.close()
        if process.poll() is None:
            process.kill()
        carrier.wait(timeout=2)
        process.stderr.close()


def test_shared_checkpoint_clock_uses_sealed_origin_and_rejects_drift(tmp_path):
    import hashlib
    from types import SimpleNamespace

    from giclab.control.production import ProductionCategory3World

    path = tmp_path / "frozen.json"
    encoded = canonical_bytes({"first_pair_started_at_epoch": 1132.625})
    path.write_bytes(encoded)
    receipt = SimpleNamespace(
        manifest_path=path,
        manifest_sha256=hashlib.sha256(encoded).hexdigest(),
        started_wall_time=1012.5,
        completed_wall_time=1133.0,
        started_monotonic=12.5,
        completed_monotonic=133.0,
    )
    assert ProductionCategory3World._frozen_campaign_origins(receipt) == (1132.625, 132.625)
    path.write_bytes(canonical_bytes({"first_pair_started_at_epoch": 1133.0}))
    with pytest.raises(RuntimeError, match="origin differs"):
        ProductionCategory3World._frozen_campaign_origins(receipt)
    path.write_bytes(encoded)
    receipt.completed_wall_time = 1132.0
    with pytest.raises(RuntimeError, match="origin differs"):
        ProductionCategory3World._frozen_campaign_origins(receipt)
    receipt.completed_wall_time = 1133.0
    receipt.completed_monotonic = 12.6
    with pytest.raises(RuntimeError, match="monotonic interval"):
        ProductionCategory3World._frozen_campaign_origins(receipt)


def _publish_runtime_record(role, path, **admission):
    from giclab.harness.sira_gate_a import ProviderBudgetUsage
    from giclab.harness.sira_gate_a_runtime import _write_json_evidence, _write_usage_ledger

    if role == "json":
        _write_json_evidence(path, {"evidence": "fixture-produced record"}, **admission)
    else:
        assert role == "usage-ledger"
        _write_usage_ledger(path, ProviderBudgetUsage(), 0, **admission)


@pytest.mark.parametrize("denied", [False, True])
@pytest.mark.parametrize("handed_off", [False, True])
def test_r6_essential_copy_consumes_prefunded_capacity_after_transport_failure(
    tmp_path, denied, handed_off
):
    from concurrent.futures import Future
    from threading import Event
    from types import SimpleNamespace

    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    boundary, observer = conformance._observer_for(_binding())
    observer.reserve_output_bytes(total_bytes=512)
    bridge = object.__new__(host._ConditionSessionBridge)
    bridge.attempt_root = tmp_path
    bridge.control_roots = ()

    def no_transport_retry(count):
        pytest.fail("cancelled host requested new capacity from the failed transport")

    bridge.host_output = SimpleNamespace(handed_off=handed_off, reserve=no_transport_retry)
    bridge.cancelled = Event()
    bridge.cancelled.set()
    bridge._host_publication_remaining = 512
    bridge.relay_future = Future()
    bridge.relay_future.set_exception(RemoteBridgeDisconnected("retained disconnected transport"))
    source = tmp_path / "source"
    source.write_bytes(b"x" * (1024 if denied else 128))
    destination = tmp_path / "essential-failure" / "condition.stdout"
    admission_reset = host._HOST_OUTPUT_ADMISSION.set(bridge.admit_path)
    try:
        if denied:
            with pytest.raises(host.T09HostError, match="shared failure reserve"):
                host._copy_failure_evidence_file(source, destination)
            assert not destination.parent.exists()
            assert source.read_bytes() == b"x" * 1024
            with pytest.raises(host.T09HostError, match="shared failure reserve"):
                host.write_bytes_exclusive(destination, b"later")
        else:
            result = host._copy_failure_evidence_file(source, destination)
            assert result["bytes"] == 128 and destination.read_bytes() == b"x" * 128
            assert bridge._host_publication_remaining == 384
            observer.output_bytes(total_bytes=128, retained_output_bytes=384)
            assert boundary.condition_observed_usage.output_bytes == 128
        assert (
            boundary.accounting_document()["reserved_upper_bound"]["condition"]["output_bytes"]
            == 512
        )
    finally:
        host._HOST_OUTPUT_ADMISSION.reset(admission_reset)


@pytest.mark.parametrize("descriptor", [1, 2])
@pytest.mark.parametrize("denied", [False, True])
def test_r6_actual_attach_streams_consume_shared_capacity_before_growth(
    tmp_path, monkeypatch, descriptor, denied
):
    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    monkeypatch.setattr(host, "ATTACH_OUTPUT_ALLOCATION_BYTES", 512)
    attempt = tmp_path / "attempt"
    attempt.mkdir(mode=0o700)
    pilot = tmp_path / "pilot"
    pilot.mkdir(mode=0o700)
    grants = []
    boundary, observer = conformance._observer_for(_binding())

    def reserve(count):
        observer.reserve_output_bytes(total_bytes=count)
        grants.append(count)

    script = f"import os; os.write({descriptor}, b'x'*{1024 if denied else 128})"
    now = time.time()
    result = host.run_attached_with_caps(
        prefix=[sys.executable, "-c", script],
        container_id="local-python-effect",
        attempt_root=attempt,
        pilot_root=pilot,
        attempt_started=time.monotonic(),
        pair_started_at_epoch=now,
        pilot_started_at_epoch=now,
        owned_lambda_started_at_epoch=now,
        prior_lambda_duration_seconds=0.0,
        prior_lambda_cost_usd=0.0,
        release_condition=lambda: None,
        output_admission=reserve,
    )
    assert grants == [512]
    output = (
        attempt / ("condition.stdout" if descriptor == 1 else "condition.stderr")
    ).read_bytes()
    assert output == (b"" if denied else b"x" * 128)
    observer.output_bytes(total_bytes=len(output))
    assert (
        boundary.accounting_document()["reserved_upper_bound"]["condition"]["output_bytes"] == 512
    )
    assert boundary.condition_usage.output_bytes == len(output)
    assert boundary.condition_observed_usage.output_bytes == len(output)
    assert result[2:] == (("condition_attach_output_admission", True) if denied else (None, False))


def test_r6_attach_allocation_denial_precedes_streams_and_process(tmp_path, monkeypatch):
    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    created = []
    monkeypatch.setattr(host.subprocess, "Popen", lambda *a, **k: created.append(True))

    def deny(count):
        assert count > 0
        raise RuntimeError("shared allocation denied")

    with pytest.raises(RuntimeError, match="shared allocation denied"):
        host.run_attached_with_caps(
            prefix=["unreachable"],
            container_id="unreachable",
            attempt_root=tmp_path,
            pilot_root=tmp_path,
            attempt_started=0,
            pair_started_at_epoch=0,
            pilot_started_at_epoch=0,
            owned_lambda_started_at_epoch=0,
            prior_lambda_duration_seconds=0,
            prior_lambda_cost_usd=0,
            release_condition=lambda: None,
            output_admission=deny,
        )
    assert not created and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("interrupted", [False, True])
def test_r6_attach_partial_write_and_interruption_preserve_prefix_and_reap(
    tmp_path, monkeypatch, interrupted
):
    import subprocess
    import threading

    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    native_write = os.write
    native_popen = subprocess.Popen
    children = []

    def start(*args, **kwargs):
        process = native_popen(*args, **kwargs)
        children.append(process)
        return process

    def write(descriptor, payload):
        if not interrupted and payload == b"x" * 1024:
            return native_write(descriptor, payload[:128])
        if not interrupted and payload == b"x" * 896:
            raise OSError("intentional partial attach write failure")
        return native_write(descriptor, payload)

    monkeypatch.setattr(host.subprocess, "Popen", start)
    monkeypatch.setattr(host.os, "write", write)
    grants = []
    now = time.time()

    def release():
        if interrupted:
            raise RuntimeError("intentional release interruption")

    args = dict(
        prefix=[sys.executable, "-c", "import os,time; os.write(1,b'x'*1024); time.sleep(30)"],
        container_id="local-python-effect",
        attempt_root=tmp_path,
        pilot_root=tmp_path,
        attempt_started=time.monotonic(),
        pair_started_at_epoch=now,
        pilot_started_at_epoch=now,
        owned_lambda_started_at_epoch=now,
        prior_lambda_duration_seconds=0,
        prior_lambda_cost_usd=0,
        release_condition=release,
        output_admission=grants.append,
    )
    # Only the exact environmental stop command is modeled. The attach producer
    # and its real stream writer remain local subprocess/thread execution.
    native_run = subprocess.run

    def stop_command(argv, **kwargs):
        if argv == [*args["prefix"], "kill", "local-python-effect"]:
            return subprocess.CompletedProcess(argv, 0)
        return native_run(argv, **kwargs)

    monkeypatch.setattr(host.subprocess, "run", stop_command)
    started = time.monotonic()
    if interrupted:
        with pytest.raises(RuntimeError, match="release interruption"):
            host.run_attached_with_caps(**args)
    else:
        result = host.run_attached_with_caps(**args)
        assert result[2:] == ("condition_attach_output_admission", True)
        assert (tmp_path / "condition.stdout").read_bytes() == b"x" * 128
    assert time.monotonic() - started < 6
    assert len(grants) == 1 and grants[0] == host.ATTACH_OUTPUT_ALLOCATION_BYTES
    assert len(children) == 1 and children[0].poll() is not None
    assert not any(t.name == "giclab-condition-attach-output" for t in threading.enumerate())


@pytest.mark.parametrize("role", ["json", "usage-ledger"])
def test_r6_atomic_runtime_record_requires_admission_before_creation(tmp_path, role):
    from giclab.harness.sira_gate_a import GateAContractError

    root = tmp_path / "uncreated-output"
    with pytest.raises(GateAContractError, match="output admission"):
        _publish_runtime_record(role, root / "record.json", require_output_admission=True)
    assert not root.exists()


@pytest.mark.parametrize("role", ["json", "usage-ledger"])
@pytest.mark.parametrize("replacing", [False, True])
def test_r6_atomic_runtime_record_shared_denial_preserves_files(tmp_path, role, replacing):
    from dataclasses import replace

    from giclab.harness.sira_gate_a import (
        ImmutableModelRouting,
        ProviderBudgetBoundary,
        ProviderBudgetExceeded,
        ProviderBudgetUsage,
    )

    boundary, observer = conformance._observer_for(_binding())
    full = replace(ProviderBudgetUsage(), output_bytes=boundary.aggregate_caps.max_output_bytes)
    observer.boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=boundary.aggregate_caps,
        condition_caps=boundary.condition_caps,
        initial_aggregate_usage=full,
        initial_aggregate_observed_usage=full,
    )
    path = tmp_path / "record.json"
    if replacing:
        path.write_bytes(b"previous exact record\n")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    requested = []

    def reserve(size):
        requested.append(size)
        observer.reserve_output_bytes(total_bytes=size)

    with pytest.raises(ProviderBudgetExceeded):
        _publish_runtime_record(
            role, path, reserve_temporary_bytes=reserve, require_output_admission=True
        )
    assert len(requested) == 1 and requested[0] > 0
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert observer.boundary.condition_usage.output_bytes == 0


@pytest.mark.parametrize("role", ["json", "usage-ledger"])
def test_r6_atomic_runtime_record_reserves_full_temporary_before_replace(tmp_path, role):
    boundary, observer = conformance._observer_for(_binding())
    path = tmp_path / "record.json"
    # A smaller replacement still needs its entire new file while the old
    # record exists. Counting only positive net final growth would admit zero.
    previous = b"previous record" * 1024
    path.write_bytes(previous)
    requested = []

    def reserve(size):
        assert path.read_bytes() == previous
        assert list(tmp_path.iterdir()) == [path]
        requested.append(size)
        observer.reserve_output_bytes(total_bytes=size)

    _publish_runtime_record(
        role, path, reserve_temporary_bytes=reserve, require_output_admission=True
    )
    assert requested == [path.stat().st_size]
    assert 0 < requested[0] < len(previous)
    assert list(tmp_path.iterdir()) == [path]
    assert isinstance(json.loads(path.read_bytes()), dict)
    # The writer does not report a guessed whole-scope observation or release
    # allowance merely because its local replacement has completed.
    assert observer.output_total_bytes is None
    accounting = boundary.accounting_document()
    assert accounting["observed_lower_bound"]["condition"]["output_bytes"] == 0
    assert accounting["reserved_upper_bound"]["condition"]["output_bytes"] == requested[0]


@pytest.mark.parametrize("role", ["json", "usage-ledger"])
def test_r6_atomic_runtime_record_failure_retains_prefix_and_reservation(
    tmp_path, monkeypatch, role
):
    from giclab.harness import sira_gate_a_runtime as runtime

    boundary, observer = conformance._observer_for(_binding())
    path = tmp_path / "record.json"
    path.write_bytes(b"previous exact record\n")
    requested = []

    def reserve(size):
        requested.append(size)
        observer.reserve_output_bytes(total_bytes=size)

    def interrupted_fsync(descriptor):
        assert os.fstat(descriptor).st_size == requested[0]
        raise OSError("injected evidence fsync interruption")

    monkeypatch.setattr(runtime.os, "fsync", interrupted_fsync)
    with pytest.raises(OSError, match="injected evidence fsync interruption"):
        _publish_runtime_record(
            role, path, reserve_temporary_bytes=reserve, require_output_admission=True
        )
    assert path.read_bytes() == b"previous exact record\n"
    retained = [p for p in tmp_path.iterdir() if p != path]
    assert len(retained) == 1 and retained[0].stat().st_size == requested[0]
    assert observer.output_total_bytes is None
    assert (
        boundary.accounting_document()["reserved_upper_bound"]["condition"]["output_bytes"]
        == requested[0]
    )
    exact_prefix = retained[0].read_bytes()
    # Retry cannot truncate the retained prefix, replace the old destination,
    # or silently clear the unresolved first publication.
    with pytest.raises(FileExistsError):
        _publish_runtime_record(
            role, path, reserve_temporary_bytes=reserve, require_output_admission=True
        )
    assert retained[0].read_bytes() == exact_prefix
    assert path.read_bytes() == b"previous exact record\n"


def test_r6_initial_runtime_event_requires_bound_admission(tmp_path):
    from giclab.harness.t09_sira_pilot import EventWriter, T09PilotError

    path = tmp_path / "normalized-events.jsonl"
    writer = EventWriter(path, require_output_admission=True)
    with pytest.raises(T09PilotError, match="output admission"):
        writer.append("regulation-decision-assignment", {"condition": "reactive"})
    assert not path.exists()
    assert writer.sequence == 0


def test_r6_initial_runtime_event_uses_shared_admission(tmp_path):
    from giclab.control.production import _AccountingObserver, _ValidatedRuntimeClock
    from giclab.harness.sira_gate_a import (
        ImmutableModelRouting,
        ProviderBudgetBoundary,
        aggregate_caps,
        condition_caps,
    )
    from giclab.harness.t09_sira_pilot import EventWriter

    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=aggregate_caps(),
        condition_caps=condition_caps("reactive"),
    )

    class Clock:
        monotonic = staticmethod(time.monotonic)
        wall_time = staticmethod(time.time)
        sleep = staticmethod(time.sleep)

    port = _AccountingObserver(
        run_id=V16_PROVIDER_CONTRACT.run_ids[0],
        model_revision="gpt-4o-2024-11-20",
        service_tier="default",
        boundary=boundary,
        prior_call_ids=frozenset(),
        prior_logical_call_ids=frozenset(),
        clock=_ValidatedRuntimeClock(Clock()),
        campaign_deadline_monotonic=time.monotonic() + 10,
    )
    path = tmp_path / "normalized-events.jsonl"
    writer = EventWriter(path, require_output_admission=True)
    writer.bind_output_admission(
        reserve_growth=lambda size: port.reserve_output_bytes(total_bytes=size),
        observe_growth=lambda size: port.output_bytes(total_bytes=size),
    )
    writer.append("regulation-decision-assignment", {"condition": "reactive"})
    assert boundary.condition_usage.output_bytes == path.stat().st_size


def _binding() -> ConditionSessionBinding:
    contract = V16_PROVIDER_CONTRACT
    return ConditionSessionBinding(
        session_id=f"SESSION-{contract.run_ids[0]}",
        provider_contract_version=contract.version,
        plan_id=contract.plan_id,
        host_run_id=contract.host_run_id,
        condition_run_id=contract.run_ids[0],
        evaluator_run_id=contract.evaluator_run_ids[0],
        frozen_manifest_sha256="a" * 64,
    )


def test_r1_fresh_runtime_processes_preserve_campaign_call_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observers = []
    original = conformance._observer_for

    def campaign_observer(binding: ConditionSessionBinding):
        boundary, observer = original(binding)
        observer.prior_call_ids = frozenset(
            call_id for previous in observers for call_id in previous.call_ids
        )
        observer.prior_logical_call_ids = frozenset(
            call_id for previous in observers for call_id in previous.logical_call_ids
        )
        observers.append(observer)
        return boundary, observer

    monkeypatch.setattr(conformance, "_observer_for", campaign_observer)
    with tempfile.TemporaryDirectory(prefix="t09-rr-", dir="/tmp") as directory:
        results = []
        failure = None
        for run_id in V16_PROVIDER_CONTRACT.run_ids:
            try:
                results.append(
                    conformance._duplex_subprocess_session(
                        ROOT,
                        Path(directory),
                        contract=V16_PROVIDER_CONTRACT,
                        run_id=run_id,
                        frozen_manifest_sha256="a" * 64,
                    )
                )
            except ValueError as exc:
                failure = f"{exc.__cause__!r}: {exc}"
                break
        assert len(results) == 4, failure
        call_ids = [call for observer in observers for call in observer.call_ids]
        assert len(call_ids) == len(set(call_ids))


def test_interrupted_bridge_prefix_rejects_completion_mutation_and_accounting_drift(monkeypatch):
    from copy import deepcopy
    from dataclasses import replace

    from giclab.control.effects import ConditionBridgePrefixEvidence
    from giclab.control.remote_bridge import (
        RemoteBridgeError,
        _frame_chain_identity,
        expected_condition_bridge_evidence,
        semantic_sha256,
        validate_condition_bridge_prefix,
    )

    original = conformance._observer_for
    observed = []

    def capture(binding):
        boundary, observer = original(binding)
        observed.append((binding, boundary))
        return boundary, observer

    monkeypatch.setattr(conformance, "_observer_for", capture)
    with tempfile.TemporaryDirectory(prefix="t09-prefix-", dir="/tmp") as directory:
        root = Path(directory)
        run = V16_PROVIDER_CONTRACT.run_ids[0]
        conformance._duplex_subprocess_session(
            ROOT, root, contract=V16_PROVIDER_CONTRACT, run_id=run, frozen_manifest_sha256="a" * 64
        )
        binding, boundary = observed[0]
        full = expected_condition_bridge_evidence(
            transaction_root=root, raw_root=root / "a/1/raw", run_id=run
        )
        selected = ConditionBridgePrefixEvidence(
            full.session_id,
            full.shared_transcript_path,
            full.remote_journal_path,
            full.relay_prefix_path,
        )
        documents = {
            p: json.loads(p.read_bytes())
            for p in (
                selected.shared_transcript_path,
                selected.remote_journal_path,
                selected.relay_prefix_path,
            )
        }
        accounting = boundary.accounting_document()

        def validate():
            return validate_condition_bridge_prefix(
                ROOT,
                selected,
                expected_binding=binding,
                shared_accounting=accounting,
                reader=lambda p: canonical_bytes(documents[p]),
            )

        with pytest.raises(RemoteBridgeError, match="fully acknowledged"):
            validate()
        # Explicit test inputs model a crash between observed shared completion
        # and remote journal publication. Originals produced above stay intact.
        count = len(documents[selected.relay_prefix_path]["frames"])
        for path, keep in (
            (selected.shared_transcript_path, count),
            (selected.remote_journal_path, count - 2),
        ):
            document = documents[path]
            document["frames"] = document["frames"][:keep]
            document["frame_count"] = document["terminal_sequence"] = keep
            document["terminal_frame_sha256"] = document["frames"][-1]["frame"]["frame_sha256"]
            document["frame_chain_sha256"] = _frame_chain_identity(
                binding, [e["frame"] for e in document["frames"]]
            )
            document.pop("transcript_sha256")
            document["transcript_sha256"] = semantic_sha256(document)
        assert len(validate()) == 64
        original_remote = deepcopy(documents[selected.remote_journal_path])
        documents[selected.remote_journal_path]["frames"][-1]["frame"]["payload"]["accepted"] = (
            False
        )
        with pytest.raises(RemoteBridgeError):
            validate()
        documents[selected.remote_journal_path] = original_remote
        accounting = deepcopy(accounting)
        accounting["calls"][0]["logical_call_id"] = "wrong-session-call"
        with pytest.raises(RemoteBridgeError, match="logical call"):
            validate()
        accounting = boundary.accounting_document()
        binding = replace(binding, frozen_manifest_sha256="b" * 64)
        with pytest.raises(RemoteBridgeError):
            validate()


def test_retained_runtime_lifecycle_projection_rejects_mirror_and_journal_drift(monkeypatch):
    from copy import deepcopy
    from dataclasses import replace

    from giclab.control.remote_bridge import RemoteBridgeError, remote_lifecycle_projection

    child = conformance._RUNTIME_CHILD
    marker = "    detached = port.detach_runtime()\n"
    assert child.count(marker) == 1
    child = child.replace(
        marker,
        marker
        + "    (raw_root / 'test-lifecycle.json').write_bytes(\n"
        + "        canonical_bytes(port.accounting_document()))\n",
    )
    monkeypatch.setattr(conformance, "_RUNTIME_CHILD", child)
    with tempfile.TemporaryDirectory(prefix="t09-lc-", dir="/tmp") as directory:
        root = Path(directory)
        conformance._duplex_subprocess_session(
            ROOT,
            root,
            contract=V16_PROVIDER_CONTRACT,
            run_id=V16_PROVIDER_CONTRACT.run_ids[0],
            frozen_manifest_sha256="a" * 64,
        )
        raw = root / "a/1/raw"
        journal = json.loads((raw / "duplex-remote-event-journal.json").read_bytes())
        mirror = json.loads((raw / "test-lifecycle.json").read_bytes())
        binding = _binding()
        result = remote_lifecycle_projection(ROOT, journal, mirror, expected_binding=binding)
        assert result["authoritative"] is False and result["unknown_outcomes"] == 0
        assert {c["call_id"] for c in result["calls"]} == set(mirror["calls"])
        assert all(c["history"][1] == "send_started" for c in result["calls"])
        for mutation in ("authority", "missing-call", "state", "usage", "observation"):
            altered = deepcopy(mirror)
            call = next(iter(altered["calls"]))
            if mutation == "authority":
                altered["authoritative"] = True
            elif mutation == "missing-call":
                del altered["calls"][call]
            elif mutation == "state":
                altered["calls"][call]["terminal_state"] = "ambiguous-send"
            elif mutation == "usage":
                altered["calls"][call]["actual_usage"]["input_tokens"] += 1
            else:
                altered["condition_usage_mirror"]["output_bytes"] += 1
            with pytest.raises(RemoteBridgeError):
                remote_lifecycle_projection(ROOT, journal, altered, expected_binding=binding)
        with pytest.raises(RemoteBridgeError):
            remote_lifecycle_projection(
                ROOT,
                journal,
                mirror,
                expected_binding=replace(binding, session_id="SESSION-WRONG"),
            )
        altered_journal = deepcopy(journal)
        altered_journal["frames"][0]["frame"]["payload"]["zero_retry"] = False
        with pytest.raises(RemoteBridgeError):
            remote_lifecycle_projection(ROOT, altered_journal, mirror, expected_binding=binding)


@pytest.mark.parametrize("transport", ["pipe", "unix-socket"])
@pytest.mark.parametrize("direction", ["endpoint", "relay-to-shared", "relay-to-remote"])
@pytest.mark.parametrize("drain_prefix", [False, True], ids=["never-reads", "stops-mid-frame"])
def test_r5_write_deadline_includes_kernel_backpressure(
    transport: str, direction: str, drain_prefix: bool
) -> None:
    """A watchdog reaps the old blocking implementation before asserting failure."""
    result_read, result_write = os.pipe()
    if transport == "pipe":
        data_read, data_write = os.pipe()
        channels = ()
    else:
        left, right = socket.socketpair()
        right.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        data_read, data_write = left.fileno(), right.fileno()
        channels = (left, right)
    child = os.fork()
    if child == 0:
        os.close(result_read)
        try:
            reader = os.fdopen(os.dup(data_read), "rb", buffering=0)
            writer = os.fdopen(os.dup(data_write), "wb", buffering=0)
            start = time.monotonic()
            deadline = start + 0.10
            try:
                if direction == "endpoint":
                    endpoint = FramedDuplexEndpoint(
                        reader=reader,
                        writer=writer,
                        binding=_binding(),
                        deadline_monotonic=deadline,
                    )
                    endpoint.write_event(
                        event_id="completion",
                        event_type="completion",
                        payload={"completed": True, "answer": "x" * 700_000, "error": ""},
                    )
                else:
                    relay = CanonicalFrameRelay(
                        remote_reader=reader,
                        remote_writer=writer,
                        shared_reader=reader,
                        shared_writer=writer,
                        binding=_binding(),
                        deadline_monotonic=deadline,
                    )
                    destination = (
                        relay.shared_writer
                        if direction == "relay-to-shared"
                        else relay.remote_writer
                    )
                    relay._write_packet(destination, b"x" * 700_000)
            except RemoteBridgeDisconnected:
                result = {"timed_out": True, "elapsed": time.monotonic() - start}
            else:
                result = {"timed_out": False, "elapsed": time.monotonic() - start}
            os.write(result_write, json.dumps(result).encode())
        except BaseException as exc:
            os.write(result_write, json.dumps({"unexpected": repr(exc)}).encode())
        finally:
            os._exit(0)
    os.close(result_write)
    try:
        if drain_prefix:
            ready, _, _ = select.select([data_read], [], [], 0.5)
            assert ready, "writer never supplied the first partial frame"
            assert os.read(data_read, 2048)
        ready, _, _ = select.select([result_read], [], [], 0.8)
        result = json.loads(os.read(result_read, 4096)) if ready else None
        assert result is not None, "kernel write remained blocked beyond the 0.10s deadline"
        assert "unexpected" not in result, result
        assert result["timed_out"] is True, result
        assert 0.08 <= result["elapsed"] < 0.7, result
    finally:
        waited, _ = os.waitpid(child, os.WNOHANG)
        if not waited:
            os.kill(child, signal.SIGKILL)
            os.waitpid(child, 0)
        os.close(result_read)
        if channels:
            for channel in channels:
                channel.close()
        else:
            os.close(data_read)
            os.close(data_write)


def test_retained_qualification_rejects_substitute_historical_archive(tmp_path: Path) -> None:
    """Blocker evidence: environmental fixture bytes cannot satisfy the frozen hash.

    This passes by preserving an existing source contract. It is not a red/green
    repair regression for R4 and does not claim any qualification phase passed.
    """
    name = "t09_review_archive_contract"
    specification = importlib.util.spec_from_file_location(
        name, ROOT / conformance.REMOTE_RUNNER_PATH
    )
    assert specification is not None and specification.loader is not None
    host = importlib.util.module_from_spec(specification)
    sys.modules[name] = host
    try:
        specification.loader.exec_module(host)
        source = tmp_path / "substitute.tar.gz"
        source.write_bytes(b"\0" * host.PRIVATE_REGRESSION_ARCHIVE_BYTES)
        source.chmod(0o600)
        destination = tmp_path / "staged.tar.gz"
        with pytest.raises(host.T09HostError, match="archive staging source hash drifted"):
            host.stage_verified_archive(
                source,
                destination,
                host.PRIVATE_REGRESSION_ARCHIVE_BYTES,
                host.PRIVATE_REGRESSION_ARCHIVE_SHA256,
            )
        assert not destination.exists()
    finally:
        sys.modules.pop(name, None)


@pytest.mark.parametrize("direction", ["endpoint", "relay"])
def test_r5_maximum_frame_survives_partial_io_eintr_eagain_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
    direction: str,
) -> None:
    left, right = socket.socketpair()
    left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    streams = tuple(
        channel.makefile(mode, buffering=0) for channel in (left, right) for mode in ("rb", "wb")
    )
    deadline = time.monotonic() + 3
    sender = FramedDuplexEndpoint(
        reader=streams[0], writer=streams[1], binding=_binding(), deadline_monotonic=deadline
    )
    receiver = FramedDuplexEndpoint(
        reader=streams[2], writer=streams[3], binding=_binding(), deadline_monotonic=deadline
    )
    payload = {"completed": True, "answer": "", "error": ""}
    frame = ConditionBridgeFrame.create(
        _binding(),
        sequence_number=1,
        previous_frame_sha256="0" * 64,
        event_id="completion",
        event_type="completion",
        payload=payload,
    )
    payload["answer"] = "x" * (MAX_BRIDGE_FRAME_BYTES - len(canonical_bytes(frame.to_document())))
    real_write, real_read = os.write, os.read
    injected = {
        "write_eintr": False,
        "write_eagain": False,
        "read_eintr": False,
        "read_eagain": False,
    }

    def write(fd, value):
        for name, error in [("write_eintr", InterruptedError), ("write_eagain", BlockingIOError)]:
            if fd == streams[1].fileno() and not injected[name]:
                injected[name] = True
                raise error()
        return real_write(fd, value[:2048])

    def read(fd, size):
        for name, error in [("read_eintr", InterruptedError), ("read_eagain", BlockingIOError)]:
            if fd == streams[2].fileno() and not injected[name]:
                injected[name] = True
                raise error()
        return real_read(fd, min(size, 2048))

    monkeypatch.setattr(os, "write", write)
    monkeypatch.setattr(os, "read", read)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            receiving = pool.submit(receiver.read_event)
            if direction == "endpoint":
                sent = sender.write_event(
                    event_id="completion", event_type="completion", payload=payload
                )
            else:
                import struct

                sent = ConditionBridgeFrame.create(
                    _binding(),
                    sequence_number=1,
                    previous_frame_sha256="0" * 64,
                    event_id="completion",
                    event_type="completion",
                    payload=payload,
                )
                encoded = canonical_bytes(sent.to_document())
                relay = CanonicalFrameRelay(
                    remote_reader=streams[0],
                    remote_writer=streams[1],
                    shared_reader=streams[0],
                    shared_writer=streams[1],
                    binding=_binding(),
                    deadline_monotonic=deadline,
                )
                relay._write_packet(streams[1], struct.pack("!I", len(encoded)) + encoded)
            received = receiving.result(timeout=1)
        assert len(canonical_bytes(sent.to_document())) == MAX_BRIDGE_FRAME_BYTES
        assert received == sent
        assert len(receiver.entries) == 1
        assert all(injected.values())
        assert not select.select([right], [], [], 0)[0]
        left.shutdown(socket.SHUT_WR)
        with pytest.raises(RemoteBridgeDisconnected, match="half-closed"):
            receiver.read_event(expected={"terminal-ack"})
    finally:
        for stream in streams:
            stream.close()
        left.close()
        right.close()


def test_r6_runtime_event_writer_cannot_grow_without_shared_output_headroom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual factory/EventWriter component; exhausted shared allowance is input.

    The shared accountant starts with previously consumed aggregate output at the
    unchanged plan cap. This is not a policy override or a joined campaign proof.
    """
    from dataclasses import replace

    from giclab.harness.sira_gate_a import (
        ImmutableModelRouting,
        ProviderBudgetBoundary,
        ProviderBudgetUsage,
    )

    original_observer = conformance._observer_for
    observed = []

    def exhausted_campaign(binding):
        boundary, observer = original_observer(binding)
        full = replace(ProviderBudgetUsage(), output_bytes=boundary.aggregate_caps.max_output_bytes)
        exhausted = ProviderBudgetBoundary(
            routing=ImmutableModelRouting.locked(),
            aggregate_caps=boundary.aggregate_caps,
            condition_caps=boundary.condition_caps,
            initial_aggregate_usage=full,
            initial_aggregate_observed_usage=full,
        )
        observer.boundary = exhausted
        observed.append(observer)
        return exhausted, observer

    child = conformance._RUNTIME_CHILD
    marker = "    ledger_path=raw_root / 'unused-historical-ledger.json',\n"
    assert child.count(marker) == 1
    child = child.replace(
        marker,
        marker + "    pilot_events=__import__('giclab.harness.t09_sira_pilot', "
        "fromlist=['EventWriter']).EventWriter(raw_root / 'runtime-output-events.jsonl'),\n",
    )
    monkeypatch.setattr(conformance, "_RUNTIME_CHILD", child)
    monkeypatch.setattr(conformance, "_observer_for", exhausted_campaign)
    failure = None
    # Unix socket pathname length is bounded; use the established private test root.
    with tempfile.TemporaryDirectory(prefix="t09-r6-", dir="/tmp") as directory:
        root = Path(directory)
        try:
            conformance._duplex_subprocess_session(
                ROOT,
                root,
                contract=V16_PROVIDER_CONTRACT,
                run_id=V16_PROVIDER_CONTRACT.run_ids[0],
                frozen_manifest_sha256="a" * 64,
            )
        except ValueError as exc:
            failure = exc
        assert failure is not None, "exhausted output must stop the remote condition"
        assert observed and observed[0].output_total_bytes is None
        events = root / "a/1/raw/runtime-output-events.jsonl"
        actual = events.read_bytes() if events.exists() else b""
        evidence = tmp_path / "r6-unadmitted-runtime-event-prefix.jsonl"
        evidence.write_bytes(actual)
        evidence.chmod(0o600)
        assert actual == b"", (
            f"actual retained runtime EventWriter wrote {len(actual)} unadmitted bytes "
            "before shared output rejection"
        )


@pytest.mark.parametrize("observed_bytes", [0, 20, 80])
def test_r6_campaign_checkpoint_retains_unconsumed_output_allowance(observed_bytes):
    """Exercise the real production history consumer, without entering a campaign.

    Eighty bytes were admitted in condition one. Only its observed subset may be
    called usage, but the unconsumed remainder must still constrain condition two.
    No cleanup/reconciliation proof releases that capacity in this component.
    """
    from dataclasses import replace
    from types import SimpleNamespace
    from typing import Any, cast

    from giclab.control.production import ProductionCategory3World
    from giclab.harness.sira_gate_a import (
        ImmutableModelRouting,
        ProviderBudgetBoundary,
        ProviderBudgetExceeded,
        ProviderBudgetUsage,
    )

    boundary, observer = conformance._observer_for(_binding())
    boundary.aggregate_caps = replace(boundary.aggregate_caps, max_output_bytes=100)
    boundary.condition_caps = replace(boundary.condition_caps, max_output_bytes=100)
    observer.reserve_output_bytes(total_bytes=80)
    observer.output_bytes(total_bytes=observed_bytes)
    owner = SimpleNamespace(
        _accounting={},
        _aggregate_usage=ProviderBudgetUsage(),
        _aggregate_observed_usage=ProviderBudgetUsage(),
        _seen_call_ids=set(),
        _seen_logical_call_ids=set(),
    )
    ProductionCategory3World._record_boundary_state(
        cast(Any, owner), _binding().condition_run_id, observer
    )
    assert owner._aggregate_observed_usage.output_bytes == observed_bytes
    assert owner._aggregate_usage.output_bytes == 80, "campaign history lost admitted capacity"
    next_boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        aggregate_caps=boundary.aggregate_caps,
        condition_caps=boundary.condition_caps,
        initial_aggregate_usage=owner._aggregate_usage,
        initial_aggregate_observed_usage=owner._aggregate_observed_usage,
    )
    next_boundary.reserve_output_bytes(total_bytes=20)
    with pytest.raises(ProviderBudgetExceeded):
        next_boundary.reserve_output_bytes(total_bytes=21)
    accounting = next_boundary.accounting_document()
    assert accounting["reserved_upper_bound"]["aggregate"]["output_bytes"] == 100
    assert accounting["observed_lower_bound"]["aggregate"]["output_bytes"] == observed_bytes


@pytest.mark.parametrize("role", ["sira-output", "source-logs"])
@pytest.mark.parametrize("opener", ["path", "builtin"])
def test_r6_source_writer_denies_before_creation_or_truncation(tmp_path, role, opener):
    from giclab.harness.sira_gate_a import GateAContractError
    from giclab.harness.sira_gate_a_runtime import (
        _admit_source_writers,
        _AdmittedPublicationAllowance,
    )

    directory = tmp_path / role
    directory.mkdir()
    target = directory / "record.txt"
    target.write_bytes(b"previous exact bytes")
    allowance = _AdmittedPublicationAllowance(0)
    with (
        pytest.raises(GateAContractError, match="retained denial"),
        _admit_source_writers(tmp_path, allowance),
    ):
        with (
            target.open("w") if opener == "path" else open(target, "w") as stream,
            pytest.raises(GateAContractError, match="allowance exhausted"),
        ):
            stream.write("denied bytes")
        assert target.read_bytes() == b"previous exact bytes"
    assert allowance.remaining == 0


def test_r6_actual_json_and_logging_writers_consume_exact_utf8_bytes(tmp_path):
    import logging

    from giclab.harness.sira_gate_a_runtime import (
        _admit_source_writers,
        _AdmittedPublicationAllowance,
    )

    for role in ("sira-output", "source-logs"):
        (tmp_path / role).mkdir()
    allowance = _AdmittedPublicationAllowance(1024)
    session_path = tmp_path / "sira-output/session.json"
    log_path = tmp_path / "source-logs/runtime.log"
    with _admit_source_writers(tmp_path, allowance):
        with session_path.open("x", encoding="utf-8") as stream:
            json.dump({"answer": "fixture λ"}, stream, ensure_ascii=False)
            stream.write("\n")
        handler = logging.FileHandler(log_path, encoding="utf-8")
        try:
            handler.setFormatter(logging.Formatter("%(message)s"))
            handler.handle(
                logging.LogRecord("fixture", logging.INFO, "fixture.py", 1, "bounded λ", (), None)
            )
        finally:
            handler.close()
    total = session_path.stat().st_size + log_path.stat().st_size
    assert json.loads(session_path.read_bytes())["answer"] == "fixture λ"
    assert log_path.read_text() == "bounded λ\n"
    assert allowance.remaining == 1024 - total


def test_r6_source_writer_keeps_admitted_prefix_after_later_denial(tmp_path):
    from giclab.harness.sira_gate_a import GateAContractError
    from giclab.harness.sira_gate_a_runtime import (
        _admit_source_writers,
        _AdmittedPublicationAllowance,
    )

    (tmp_path / "sira-output").mkdir()
    target = tmp_path / "sira-output/session.bin"
    allowance = _AdmittedPublicationAllowance(3)
    with (
        pytest.raises(GateAContractError, match="retained denial"),
        _admit_source_writers(tmp_path, allowance),
        target.open("xb") as stream,
    ):
        assert stream.write(b"yes") == 3
        with pytest.raises(GateAContractError, match="allowance exhausted"):
            stream.write(b"no")
    assert target.read_bytes() == b"yes"
    assert allowance.remaining == 0


@pytest.mark.parametrize("replacement", ["hardlink", "symlink", "fifo"])
def test_r6_source_writer_rejects_unowned_file_role_before_truncation(tmp_path, replacement):
    import os

    from giclab.harness.sira_gate_a import GateAContractError
    from giclab.harness.sira_gate_a_runtime import (
        _admit_source_writers,
        _AdmittedPublicationAllowance,
    )

    (tmp_path / "sira-output").mkdir()
    target = tmp_path / "sira-output/session.txt"
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_bytes(b"unrelated original")
    with _admit_source_writers(tmp_path, _AdmittedPublicationAllowance(1024)):
        stream = target.open("w", encoding="utf-8")
        if replacement == "hardlink":
            os.link(unrelated, target)
        elif replacement == "symlink":
            target.symlink_to(unrelated)
        else:
            os.mkfifo(target)
        with pytest.raises((GateAContractError, OSError)):
            stream.write("must not replace")
        stream.close()
    assert unrelated.read_bytes() == b"unrelated original"


def test_r6_source_writer_rejects_non_utf8_locale(tmp_path, monkeypatch):
    from giclab.harness import sira_gate_a_runtime as runtime
    from giclab.harness.sira_gate_a import GateAContractError

    (tmp_path / "sira-output").mkdir()
    target = tmp_path / "sira-output/session.txt"
    monkeypatch.setattr(runtime.locale, "getencoding", lambda: "ascii")
    with (
        runtime._admit_source_writers(tmp_path, runtime._AdmittedPublicationAllowance(1024)),
        pytest.raises(GateAContractError, match="UTF-8"),
    ):
        target.open("w")
    assert not target.exists()


def test_r6_logging_caught_denial_still_invalidates_runtime(tmp_path, monkeypatch):
    import logging

    from giclab.harness.sira_gate_a import GateAContractError
    from giclab.harness.sira_gate_a_runtime import (
        _admit_source_writers,
        _AdmittedPublicationAllowance,
    )

    (tmp_path / "source-logs").mkdir()
    target = tmp_path / "source-logs/runtime.log"
    allowance = _AdmittedPublicationAllowance(3)
    monkeypatch.setattr(logging, "raiseExceptions", False)
    with (
        pytest.raises(GateAContractError, match="retained denial"),
        _admit_source_writers(tmp_path, allowance),
    ):
        handler = logging.FileHandler(target, encoding="utf-8")
        try:
            handler.handle(
                logging.LogRecord("fixture", logging.INFO, "fixture.py", 1, "denied", (), None)
            )
            # FileHandler swallows emit errors; the same pool cannot permit a
            # smaller follow-up write or let runtime completion clear the fault.
            with pytest.raises(GateAContractError, match="allowance exhausted"):
                allowance(1)
            assert allowance.remaining == 3
        finally:
            handler.close()
    assert not target.exists()


@pytest.mark.parametrize("role", ["json", "release"])
@pytest.mark.parametrize("denied", [False, True])
def test_r6_retained_host_writer_admits_before_any_mutation(tmp_path, role, denied):
    from dataclasses import replace

    from giclab.control.production import _host_module
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    host = _host_module(ROOT)
    boundary, observer = conformance._observer_for(_binding())
    if denied:
        boundary.condition_caps = replace(boundary.condition_caps, max_output_bytes=1)
    target = tmp_path / "absent-parent/control.json"
    payload = {"condition": "bound-control", "value": "é"}
    expected = (
        (json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
        if role == "json"
        else b"release\n"
    )
    calls = []

    def reserve(path, count):
        assert path == target and count == len(expected)
        assert not target.parent.exists()
        calls.append(count)
        observer.reserve_output_bytes(total_bytes=count)

    admission_reset = host._HOST_OUTPUT_ADMISSION.set(reserve)
    try:

        def publish():
            if role == "json":
                host.write_exclusive(target, payload)
            else:
                host.write_bytes_exclusive(target, expected)

        if denied:
            with pytest.raises(ProviderBudgetExceeded):
                publish()
            assert not target.parent.exists()
        else:
            publish()
            assert target.read_bytes() == expected
            assert list(target.parent.iterdir()) == [target]
    finally:
        host._HOST_OUTPUT_ADMISSION.reset(admission_reset)
    assert calls == [len(expected)]
    assert observer.output_total_bytes is None


@pytest.mark.parametrize("role", ["json", "release"])
def test_r6_retained_host_writer_interruption_keeps_admitted_prefix(tmp_path, monkeypatch, role):
    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    boundary, observer = conformance._observer_for(_binding())
    target = tmp_path / "control.json"
    grants = []

    def reserve(path, count):
        grants.append(count)
        observer.reserve_output_bytes(total_bytes=count)

    original = host.os.write

    def partial(descriptor, data):
        if os.fstat(descriptor).st_size:
            raise OSError("injected host write interruption")
        return original(descriptor, data[:3])

    monkeypatch.setattr(host.os, "write", partial)
    admission_reset = host._HOST_OUTPUT_ADMISSION.set(reserve)
    try:

        def publish():
            if role == "json":
                host.write_exclusive(target, {"exact": "host"})
            else:
                host.write_bytes_exclusive(target, b"release\n")

        with pytest.raises(OSError, match="injected host write interruption"):
            publish()
        temporary = host._atomic_publication_temporary(target)
        assert not target.exists() and temporary.stat().st_size == 3
        prefix = temporary.read_bytes()
        with pytest.raises(FileExistsError, match="unresolved prefix"):
            publish()
        assert temporary.read_bytes() == prefix and len(grants) == 1
    finally:
        host._HOST_OUTPUT_ADMISSION.reset(admission_reset)
    assert (
        boundary.accounting_document()["reserved_upper_bound"]["condition"]["output_bytes"]
        == grants[0]
    )


def test_r6_host_prefix_continues_exact_shared_chain(tmp_path):
    from giclab.control.remote_bridge import ConditionSessionSupervisor, HostOutputAdmission

    left, right = socket.socketpair()
    streams = (
        left.makefile("rb", buffering=0),
        left.makefile("wb", buffering=0),
        right.makefile("rb", buffering=0),
        right.makefile("wb", buffering=0),
    )
    deadline = time.monotonic() + 5
    host_endpoint = FramedDuplexEndpoint(
        reader=streams[0], writer=streams[1], binding=_binding(), deadline_monotonic=deadline
    )
    shared = FramedDuplexEndpoint(
        reader=streams[2], writer=streams[3], binding=_binding(), deadline_monotonic=deadline
    )
    boundary, observer = conformance._observer_for(_binding())
    supervisor = ConditionSessionSupervisor(
        shared, observer, accounting_document=boundary.accounting_document
    )

    def serve():
        hello = shared.read_event(expected={"condition-session-hello"})
        supervisor._write(hello, "condition-session-accepted", {"accepted": True})
        for _ in range(2):
            supervisor._simple_event(shared.read_event(expected={"output-allowance-request"}))

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(serve)
            port = HostOutputAdmission(host_endpoint)
            assert list(tmp_path.iterdir()) == []
            port.reserve(6)
            (tmp_path / "ready").write_bytes(b"ready\n")
            port.reserve(8)
            (tmp_path / "release").write_bytes(b"release\n")
            future.result(timeout=5)
        document = {
            "binding": _binding().to_document(),
            "frames": [e.frame.to_document() for e in host_endpoint.entries],
        }
        resumed = FramedDuplexEndpoint(
            reader=streams[0], writer=streams[1], binding=_binding(), deadline_monotonic=deadline
        )
        assert resumed.adopt_host_output_prefix(document) == 14
        assert resumed.entries == host_endpoint.entries
        assert resumed.next_sequence == shared.next_sequence == 7
        assert resumed.previous_frame_sha256 == shared.previous_frame_sha256
        relay = CanonicalFrameRelay(
            remote_reader=streams[0],
            remote_writer=streams[1],
            shared_reader=streams[2],
            shared_writer=streams[3],
            binding=_binding(),
            deadline_monotonic=deadline,
        )
        relay.continue_host_output_prefix(host_endpoint.entries)
        assert [e["frame"] for e in relay.transcript_document()["frames"]] == document["frames"]
        assert (
            boundary.accounting_document()["reserved_upper_bound"]["condition"]["output_bytes"]
            == 14
        )
        with pytest.raises(Exception, match="ambiguous"):
            resumed.adopt_host_output_prefix(document)
    finally:
        for stream in streams:
            stream.close()
        left.close()
        right.close()


@pytest.mark.parametrize("failure", ["denied", "wrong-reply", "disconnect"])
def test_r6_host_bootstrap_rejection_is_sticky_before_writer(tmp_path, failure):
    from giclab.control.remote_bridge import HostOutputAdmission, RemoteBridgeError

    left, right = socket.socketpair()
    streams = (
        left.makefile("rb", buffering=0),
        left.makefile("wb", buffering=0),
        right.makefile("rb", buffering=0),
        right.makefile("wb", buffering=0),
    )
    deadline = time.monotonic() + 2
    host = FramedDuplexEndpoint(
        reader=streams[0], writer=streams[1], binding=_binding(), deadline_monotonic=deadline
    )
    shared = FramedDuplexEndpoint(
        reader=streams[2], writer=streams[3], binding=_binding(), deadline_monotonic=deadline
    )

    def serve():
        hello = shared.read_event()
        shared.write_event(
            event_id=hello.event_id + ".reply",
            event_type="condition-session-accepted",
            payload={"accepted": True},
        )
        request = shared.read_event()
        if failure == "disconnect":
            right.shutdown(socket.SHUT_WR)
        else:
            shared.write_event(
                event_id=(request.event_id + ".reply" if failure == "denied" else "wrong.reply"),
                event_type=(
                    "output-allowance-rejected"
                    if failure == "denied"
                    else "output-allowance-granted"
                ),
                payload=(
                    {"accepted": False, "reason": "ProviderBudgetExceeded"}
                    if failure == "denied"
                    else {"accepted": True, "total_bytes": 6}
                ),
            )

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(serve)
            port = HostOutputAdmission(host)
            with pytest.raises(RemoteBridgeError):
                port.reserve(6)
                (tmp_path / "ready").write_bytes(b"ready\n")
            before = host.entries
            with pytest.raises(RemoteBridgeError, match="outside"):
                port.reserve(1)
            assert host.entries == before and port.total == 0 and list(tmp_path.iterdir()) == []
            future.result(timeout=2)
    finally:
        for stream in streams:
            stream.close()
        left.close()
        right.close()


@pytest.mark.parametrize("outcome", ["complete", "denied", "partial"])
def test_r6_relay_publication_preserves_admitted_failure_prefix(tmp_path, monkeypatch, outcome):
    from dataclasses import replace

    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    read_fd, write_fd = os.pipe()
    reader, writer = os.fdopen(read_fd, "rb", buffering=0), os.fdopen(write_fd, "wb", buffering=0)
    try:
        relay = CanonicalFrameRelay(
            remote_reader=reader,
            remote_writer=writer,
            shared_reader=reader,
            shared_writer=writer,
            binding=_binding(),
            deadline_monotonic=time.monotonic() + 5,
        )
        expected = canonical_bytes(relay.transcript_document())
        boundary, observer = conformance._observer_for(_binding())
        if outcome == "denied":
            boundary.condition_caps = replace(boundary.condition_caps, max_output_bytes=1)
        target = tmp_path / "relay.json"
        temporary = tmp_path / ".relay.json.tmp"
        grants = []

        def consume(count):
            assert not target.exists() and not temporary.exists()
            assert count == len(expected)
            observer.reserve_output_bytes(total_bytes=count)
            grants.append(count)

        original = os.write
        if outcome == "partial":

            def interrupted(descriptor, data):
                if os.fstat(descriptor).st_size:
                    raise OSError("injected relay publication interruption")
                return original(descriptor, data[:7])

            monkeypatch.setattr(os, "write", interrupted)
        if outcome == "denied":
            with pytest.raises(ProviderBudgetExceeded):
                relay.persist_transcript(target, consume_output_allowance=consume)
            assert list(tmp_path.iterdir()) == [] and grants == []
        elif outcome == "partial":
            with pytest.raises(OSError, match="injected relay publication interruption"):
                relay.persist_transcript(target, consume_output_allowance=consume)
            assert not target.exists() and temporary.read_bytes() == expected[:7]
            assert grants == [len(expected)]
        else:
            relay.persist_transcript(target, consume_output_allowance=consume)
            assert target.read_bytes() == expected and not temporary.exists()
            assert grants == [len(expected)]
        assert observer.output_total_bytes is None
    finally:
        reader.close()
        writer.close()


def test_retained_essential_privacy_role_does_not_publish_mount_paths(tmp_path):
    from giclab.control.effects import hold_sealed_artifact, hold_transaction_root
    from giclab.control.production import ProductionCategory3World, _host_module

    root = hold_transaction_root(tmp_path)
    directory = tmp_path / "essential-failure"
    directory.mkdir(mode=0o700)
    path = directory / "container-command.json"
    path.write_bytes(canonical_bytes({"docker_create_argv": ["docker", "/giclab/attempt"]}))
    path.chmod(0o600)
    held = hold_sealed_artifact(root, path, max_bytes=1024)
    world = object.__new__(ProductionCategory3World)
    world._raw_artifacts = {"run": (held,)}
    world._finalized_artifacts = {}
    world._essential_failure_artifacts = {}
    world._condition_bridge_artifacts = {}
    host = _host_module(ROOT)
    try:
        # Real held-descriptor scanner preserves the validated original's role.
        assert world._held_evidence_privacy_findings(host) == []
        # A second, public role must be checked even for the same held inode.
        world._essential_failure_artifacts = {"run": (held,)}
        assert world._held_evidence_privacy_findings(host) == [
            "essential-failure/container-command.json:private-structure"
        ]
        # Source classification never permits credential/network material.
        for value in ({"authorization_header": "Bearer secret"}, {"address": "10.0.0.1"}):
            assert world._privacy_findings_for_bytes(
                host,
                relative="essential-failure/source.json",
                encoded=canonical_bytes(value),
                role="retained-source",
            )
    finally:
        held.close()
        root.close()


@pytest.mark.parametrize("interrupted", [False, True])
def test_r6_shared_carrier_writer_preserves_partial_bytes_and_disjoint_capacity(
    tmp_path, monkeypatch, interrupted
):
    from giclab.control.remote_bridge import SharedCarrierOutput
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    boundary, observer = conformance._observer_for(_binding())
    transcript = tmp_path / "shared/transcript.json"
    terminal = tmp_path / "shared/terminal.json"
    diagnostic = tmp_path / "carrier.stderr"
    writer = SharedCarrierOutput(
        observer, transcript_path=transcript, terminal_path=terminal, diagnostic_path=diagnostic
    )
    capacity = sum(writer.caps.values())
    observer.reserve_output_bytes(total_bytes=100)
    observer.output_bytes(total_bytes=20, retained_output_bytes=80)
    # A remote observation cannot consume a still-owned controller allocation.
    with pytest.raises(ProviderBudgetExceeded):
        observer.output_bytes(total_bytes=101)
    payload = {"actual": "carrier-generated é"}
    original = os.write
    if interrupted:

        def partial(fd, value):
            if os.fstat(fd).st_size:
                raise OSError("injected shared publication interruption")
            return original(fd, value[:3])

        monkeypatch.setattr(os, "write", partial)
        with pytest.raises(OSError, match="shared publication interruption"):
            writer.publish(transcript, payload)
        expected = canonical_bytes(payload)[:3]
    else:
        writer.publish(transcript, payload)
        expected = canonical_bytes(payload)
    assert transcript.read_bytes() == expected
    assert writer.observed == len(expected)
    assert writer.consumed[transcript] == len(canonical_bytes(payload))
    # The exact protocol snapshot precedes its own file publication accounting.
    terminal_accounting = observer.terminal_accounting_document()
    assert terminal_accounting["observed_lower_bound"]["condition"]["output_bytes"] == 20
    observer.reconcile_controller_output()
    accounting = boundary.accounting_document()
    assert accounting["observed_lower_bound"]["condition"]["output_bytes"] == 20 + len(expected)
    assert accounting["reserved_upper_bound"]["condition"]["output_bytes"] == 100 + capacity
    observer.reconcile_controller_output()
    assert accounting == boundary.accounting_document()
    assert terminal_accounting["observed_lower_bound"]["condition"]["output_bytes"] == 20


def test_r6_shared_carrier_grant_denial_precedes_all_file_creation(tmp_path):
    from dataclasses import replace

    from giclab.control.remote_bridge import SharedCarrierOutput
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    boundary, observer = conformance._observer_for(_binding())
    boundary.condition_caps = replace(boundary.condition_caps, max_output_bytes=1)
    with pytest.raises(ProviderBudgetExceeded):
        SharedCarrierOutput(
            observer,
            transcript_path=tmp_path / "absent/transcript.json",
            terminal_path=tmp_path / "absent/terminal.json",
            diagnostic_path=tmp_path / "absent/stderr",
        )
    assert list(tmp_path.iterdir()) == []


def test_r6_shared_carrier_diagnostic_denies_before_growth_and_is_sticky(tmp_path):
    from giclab.control.remote_bridge import RemoteBridgeError, SharedCarrierOutput

    boundary, observer = conformance._observer_for(_binding())
    diagnostic = tmp_path / "stderr"
    writer = SharedCarrierOutput(
        observer,
        transcript_path=tmp_path / "transcript.json",
        terminal_path=tmp_path / "terminal.json",
        diagnostic_path=diagnostic,
    )
    with diagnostic.open("xb", buffering=0) as stream:
        writer.write_diagnostic(diagnostic, stream.fileno(), b"actual-prefix")
        before = diagnostic.read_bytes()
        with pytest.raises(RemoteBridgeError, match="denied before growth"):
            writer.write_diagnostic(diagnostic, stream.fileno(), b"x" * 65536)
        assert diagnostic.read_bytes() == before
        with pytest.raises(RemoteBridgeError, match="denied before growth"):
            writer.publish(tmp_path / "terminal.json", {"not": "written"})
        assert not (tmp_path / "terminal.json").exists()
    observer.reconcile_controller_output()
    assert boundary.accounting_document()["observed_lower_bound"]["condition"][
        "output_bytes"
    ] == len(before)


def test_r6_shared_carrier_cannot_extend_caps_or_relabel_writer(tmp_path):
    from giclab.control.remote_bridge import RemoteBridgeError, SharedCarrierOutput

    _, observer = conformance._observer_for(_binding())
    diagnostic = tmp_path / "stderr"
    transcript = tmp_path / "transcript.json"
    writer = SharedCarrierOutput(
        observer,
        transcript_path=transcript,
        terminal_path=tmp_path / "terminal.json",
        diagnostic_path=diagnostic,
    )
    with pytest.raises(TypeError):
        writer.caps[diagnostic] += 1
    with pytest.raises(RemoteBridgeError, match="publication role changed"):
        writer.publish(diagnostic, {"not": "a terminal receipt"})
    assert not diagnostic.exists()
    with (
        transcript.open("xb", buffering=0) as stream,
        pytest.raises(RemoteBridgeError, match="diagnostic role changed"),
    ):
        writer.write_diagnostic(transcript, stream.fileno(), b"not a transcript")
    assert transcript.read_bytes() == b""
    assert writer.observed == 0


@pytest.mark.parametrize("role", ["finalizer", "selection", "mutable-state"])
@pytest.mark.parametrize("denied", [False, True])
def test_r6_downstream_writer_admits_exact_bytes_before_creation(tmp_path, role, denied):
    from giclab.control.production import _host_module
    from giclab.harness import t09_sira_pilot as pilot
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    _host_module(ROOT)
    spec = importlib.util.spec_from_file_location(
        "r6_actual_retained_finalizer",
        ROOT / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py",
    )
    finalizer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(finalizer)
    _, observer = conformance._observer_for(_binding())
    target = tmp_path / "absent/record.json"
    payload = {"actual": "derived é"}
    expected = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    grants = []

    def admit(path, count):
        assert path == target and not path.parent.exists()
        assert count == len(expected)
        grants.append(count)
        if denied:
            raise ProviderBudgetExceeded("injected shared grant denial")
        observer.allocate_controller_output_bytes(count=count)

    def publish():
        if role == "finalizer":
            finalizer._write_exclusive(target, payload, before_output_growth=admit)
        elif role == "selection":
            pilot._write_json_exclusive(target, payload, before_write=admit)
        else:
            pilot._write_json_atomic(target, payload, before_write=admit)

    if denied:
        with pytest.raises(ProviderBudgetExceeded, match="shared grant denial"):
            publish()
        assert not target.parent.exists()
    else:
        publish()
        assert target.read_bytes() == expected
    assert grants == [len(expected)]


@pytest.mark.parametrize("fault", ["none", "denied", "write-interrupted", "wrong-hash"])
def test_r6_actual_evidence_copy_admits_before_read_and_preserves_failure(
    tmp_path, monkeypatch, fault
):
    import hashlib
    import io

    from giclab.control.production import _host_module
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    host = _host_module(ROOT)
    payload = b"exact retained source bytes"
    target = tmp_path / "absent/source.bin"
    grants = []
    observed = []

    def admit(path, count):
        assert not path.parent.exists() and path == target and count == len(payload)
        grants.append(count)
        if fault == "denied":
            raise ProviderBudgetExceeded("injected shared copy denial")

    class Source(io.BytesIO):
        def read(self, count=-1):
            assert grants == [len(payload)]
            return super().read(count)

    original = os.write
    if fault == "write-interrupted":

        def interrupted(fd, data):
            if os.fstat(fd).st_size:
                raise OSError("injected copy interruption")
            return original(fd, data[:3])

        monkeypatch.setattr(os, "write", interrupted)

    def copy():
        host._write_stream_exclusive_or_compare(
            stream=Source(payload),
            destination=target,
            expected_bytes=len(payload),
            expected_sha256=hashlib.sha256(
                b"wrong" if fault == "wrong-hash" else payload
            ).hexdigest(),
            before_output_growth=admit,
            after_output_write=observed.append,
        )

    if fault == "none":
        copy()
        assert target.read_bytes() == payload and sum(observed) == len(payload)
    elif fault == "denied":
        with pytest.raises(ProviderBudgetExceeded):
            copy()
        assert not target.parent.exists() and observed == []
    elif fault == "write-interrupted":
        with pytest.raises(OSError, match="copy interruption"):
            copy()
        assert target.read_bytes() == payload[:3] and observed == [3]
    else:
        with pytest.raises(host.T09HostError, match="hash mismatch"):
            copy()
        assert target.read_bytes() == payload and sum(observed) == len(payload)
    assert grants == [len(payload)]


@pytest.mark.parametrize("mode", ["valid", "denied", "partial", "expired"])
def test_r6_retained_failure_publication_consumes_preentry_reserve(tmp_path, monkeypatch, mode):
    from giclab.control.effects import hold_transaction_root
    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    boundary, observer = conformance._observer_for(_binding())
    from dataclasses import replace

    from giclab.harness.sira_gate_a import (
        ImmutableModelRouting,
        ProviderBudgetBoundary,
        aggregate_caps,
        condition_caps,
    )

    # This publisher runs under the retained 512-MiB attempt policy. The
    # generic duplex component fixture deliberately has a smaller 100-MiB cap.
    boundary = ProviderBudgetBoundary(
        routing=ImmutableModelRouting.locked(),
        condition_caps=replace(
            condition_caps("reactive"), max_output_bytes=host.MAX_ATTEMPT_OUTPUT_BYTES
        ),
        aggregate_caps=replace(aggregate_caps(), max_output_bytes=host.MAX_PILOT_DISK_BYTES),
    )
    observer.boundary = boundary
    observer.prepare_failure_output()
    grant = boundary.accounting_document()["reserved_upper_bound"]["condition"]["output_bytes"]
    assert grant == 2 * host.MAX_ESSENTIAL_FAILURE_BYTES
    with pytest.raises(RuntimeError, match="already established"):
        observer.prepare_failure_output()
    path = tmp_path / "failure" / "payload.json"
    path.parent.mkdir(mode=0o700)
    held = hold_transaction_root(tmp_path)
    data = b"actual retained envelope\n"
    if mode == "denied":
        observer.consume_failure_output_bytes(count=grant)
    if mode == "expired":
        observer.campaign_deadline_monotonic = -1
    write = os.write
    count = 0

    def partial(fd, value):
        nonlocal count
        count += 1
        if count == 1:
            raise InterruptedError()
        if count == 2:
            return write(fd, value[:5])
        raise OSError("injected partial failure publication")

    try:
        if mode == "partial":
            monkeypatch.setattr(os, "write", partial)
            with pytest.raises(OSError, match="injected partial"):
                host._publish_failure_bytes(held, path, data, output_observer=observer)
            assert not path.exists()
            temporary = host._atomic_publication_temporary(path)
            assert temporary.read_bytes() == data[:5]
            assert observer._controller_output_observed == 5
            assert observer._failure_output_remaining == grant - len(data)
            with pytest.raises(FileExistsError):
                host._publish_failure_bytes(held, path, data, output_observer=observer)
            assert temporary.read_bytes() == data[:5]
        elif mode == "denied":
            with pytest.raises(RuntimeError, match="pre-entry allowance"):
                host._publish_failure_bytes(held, path, data, output_observer=observer)
            assert not path.exists()
            assert list(path.parent.iterdir()) == []
            assert observer._controller_output_observed == 0
        else:
            host._publish_failure_bytes(held, path, data, output_observer=observer)
            assert path.read_bytes() == data
            assert observer._controller_output_observed == len(data)
            remaining = observer._failure_output_remaining
            host._publish_failure_bytes(held, path, data, output_observer=observer)
            assert observer._failure_output_remaining == remaining
            assert observer._controller_output_observed == len(data)
        observer.reconcile_controller_output()
        accounting = boundary.accounting_document()
        assert accounting["reserved_upper_bound"]["condition"]["output_bytes"] == grant
        assert (
            accounting["observed_lower_bound"]["condition"]["output_bytes"]
            == observer._controller_output_observed
        )
    finally:
        held.close()


@pytest.mark.parametrize("terminal_state", ["absent", "complete", "partial", "corrupt-link"])
def test_failed_workload_selects_actual_transport_role_without_terminal_downgrade(
    tmp_path, terminal_state
):
    from giclab.control.remote_bridge import (
        RemoteBridgeError,
        expected_condition_bridge_evidence,
        retained_failure_bridge_evidence,
    )

    root = tmp_path / "attempt" / "essential-failure"
    root.mkdir(parents=True, mode=0o700)
    run = V16_PROVIDER_CONTRACT.run_ids[0]
    full = expected_condition_bridge_evidence(transaction_root=tmp_path, raw_root=root, run_id=run)
    members = [
        full.shared_transcript_path,
        full.remote_journal_path,
        full.relay_prefix_path,
        full.runtime_detachment_path,
    ]
    terminals = [
        full.relay_transcript_path,
        full.host_terminal_receipt_path,
        full.shared_terminal_receipt_path,
    ]
    for path in members:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(b'{"test": "role selection only; full validator still required"}\n')
        path.chmod(0o600)
    for path in (
        terminals
        if terminal_state == "complete"
        else terminals[:1]
        if terminal_state != "absent"
        else []
    ):
        path.write_bytes(b'{"test": "actual publication exists"}\n')
        path.chmod(0o600)
    if terminal_state == "corrupt-link":
        full.host_terminal_receipt_path.symlink_to(full.relay_transcript_path)
    if terminal_state in {"partial", "corrupt-link"}:
        with pytest.raises((RemoteBridgeError, OSError, ValueError)):
            retained_failure_bridge_evidence(
                transaction_root=tmp_path, essential_root=root, run_id=run
            )
        assert terminals[0].read_bytes() == b'{"test": "actual publication exists"}\n'
    else:
        selected, prefix = retained_failure_bridge_evidence(
            transaction_root=tmp_path, essential_root=root, run_id=run
        )
        if terminal_state == "complete":
            assert selected == full and prefix is None
        else:
            assert selected is None and prefix is not None
            assert prefix.remote_journal_path == full.remote_journal_path


def test_r6_failure_reserve_cannot_expand_insufficient_policy_bound():
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    boundary, observer = conformance._observer_for(_binding())
    before = boundary.accounting_document()
    with pytest.raises(ProviderBudgetExceeded):
        observer.prepare_failure_output()
    assert observer._failure_output_remaining is None
    assert boundary.accounting_document() == before


@pytest.mark.parametrize("fault", ["none", "denied", "partial"])
def test_r6_actual_archive_writer_reserves_each_chunk_before_write(tmp_path, monkeypatch, fault):
    from giclab.control.production import _host_module
    from giclab.harness.sira_gate_a import GateAContractError
    from giclab.harness.sira_gate_a_runtime import _AdmittedPublicationAllowance

    host = _host_module(ROOT)
    path = tmp_path / "archive.gz"
    allocation = _AdmittedPublicationAllowance(0 if fault == "denied" else 64)
    requests = []
    with path.open("xb", buffering=0) as output:

        def admit(target, count):
            assert target == path and output.tell() == 0
            requests.append(count)
            allocation(count)

        admission_reset = host._HOST_OUTPUT_ADMISSION.set(admit)
        original = output.write
        calls = 0

        class Partial:
            def tell(self):
                return output.tell()

            def flush(self):
                output.flush()

            def write(self, value):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise InterruptedError()
                if calls == 2:
                    return original(value[:3])
                raise OSError("retained archive partial failure")

        writer = host._BoundedArchiveWriter(
            Partial() if fault == "partial" else output, output_path=path
        )
        try:
            if fault == "denied":
                with pytest.raises(GateAContractError, match="allowance exhausted"):
                    writer.write(b"payload")
                assert output.tell() == 0
            elif fault == "partial":
                with pytest.raises(OSError, match="partial failure"):
                    writer.write(b"payload")
                assert output.tell() == 3
                assert allocation.remaining == 57
            else:
                assert writer.write(b"payload") == 7
                assert output.tell() == 7 and allocation.remaining == 57
        finally:
            host._HOST_OUTPUT_ADMISSION.reset(admission_reset)
    assert requests == [7]
    assert path.read_bytes() == {"none": b"payload", "denied": b"", "partial": b"pay"}[fault]


@pytest.mark.parametrize("denied", [False, True])
def test_r6_retained_restoration_state_is_admitted_before_temporary_creation(tmp_path, denied):
    from giclab.control.production import _host_module
    from giclab.harness.sira_gate_a import GateAContractError
    from giclab.harness.sira_gate_a_runtime import _AdmittedPublicationAllowance

    host = _host_module(ROOT)
    target = tmp_path / "state.json"
    original = b'{"prior": true}\n'
    target.write_bytes(original)
    target.chmod(0o600)
    value = {"next": True}
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    allowance = _AdmittedPublicationAllowance(0 if denied else len(encoded))

    def admit(path, count):
        assert path == target and count == len(encoded)
        assert target.read_bytes() == original
        assert list(tmp_path.iterdir()) == [target]
        allowance(count)

    admission_reset = host._HOST_OUTPUT_ADMISSION.set(admit)
    try:
        if denied:
            with pytest.raises(GateAContractError, match="allowance exhausted"):
                host._replace_restored_state(target, value)
            assert target.read_bytes() == original
            assert list(tmp_path.iterdir()) == [target]
        else:
            host._replace_restored_state(target, value)
            assert target.read_bytes() == encoded
            assert allowance.remaining == 0
    finally:
        host._HOST_OUTPUT_ADMISSION.reset(admission_reset)


def test_r6_carrier_cannot_reset_prior_controller_writer_allocation_or_usage(tmp_path):
    from giclab.control.remote_bridge import SharedCarrierOutput

    boundary, observer = conformance._observer_for(_binding())
    observer.allocate_controller_output_bytes(count=1024)
    observer.observe_controller_output_bytes(count=300)
    writer = SharedCarrierOutput(
        observer,
        transcript_path=tmp_path / "transcript.json",
        terminal_path=tmp_path / "terminal.json",
        diagnostic_path=tmp_path / "stderr",
    )
    assert observer._controller_output_allowance == 1024 + sum(writer.caps.values())
    writer.publish(tmp_path / "transcript.json", {"actual": "later carrier publication"})
    assert observer._controller_output_observed == 300 + writer.observed
    observer.reconcile_controller_output()
    accounting = boundary.accounting_document()
    assert accounting["reserved_upper_bound"]["condition"]["output_bytes"] == 1024 + sum(
        writer.caps.values()
    )
    assert accounting["observed_lower_bound"]["condition"]["output_bytes"] == 300 + writer.observed


def test_r6_closed_host_census_reconciles_only_prior_remote_capacity():
    boundary, observer = conformance._observer_for(_binding())
    observer.reserve_output_bytes(total_bytes=200)
    observer.allocate_controller_output_bytes(count=300)
    observer.output_bytes(total_bytes=50, retained_output_bytes=150)
    observer.observe_controller_output_bytes(count=30)
    terminal = dict(observer.terminal_accounting_document())
    observer.retain_closed_remote_output(total_bytes=125)
    assert observer.output_total_bytes == 50  # Original runtime event is immutable.
    assert observer.protocol_accounting_document() == terminal
    observer.reconcile_closed_remote_output()
    observer.reconcile_controller_output()
    result = boundary.accounting_document()
    assert result["observed_lower_bound"]["condition"]["output_bytes"] == 155
    assert result["reserved_upper_bound"]["condition"]["output_bytes"] == 500
    assert observer.protocol_accounting_document() == terminal
    observer.reconcile_closed_remote_output()
    observer.reconcile_controller_output()
    assert boundary.accounting_document() == result
    with pytest.raises(RuntimeError, match="prior allowance or census"):
        observer.retain_closed_remote_output(total_bytes=125)
    with pytest.raises(RuntimeError):
        observer.output_bytes(total_bytes=125)
    called = []
    with pytest.raises(RuntimeError, match="after terminal runtime"):
        observer.browser_action(action_id="after-close", perform=lambda: called.append(True))
    assert called == []


@pytest.mark.parametrize("total", [49, 201, -1, True])
def test_r6_closed_host_census_cannot_borrow_controller_allowance(total):
    boundary, observer = conformance._observer_for(_binding())
    observer.reserve_output_bytes(total_bytes=200)
    observer.allocate_controller_output_bytes(count=1000)
    observer.output_bytes(total_bytes=50, retained_output_bytes=150)
    prior = boundary.accounting_document()
    with pytest.raises(RuntimeError, match="prior allowance or census"):
        observer.retain_closed_remote_output(total_bytes=total)
    assert boundary.accounting_document() == prior
    assert observer.output_total_bytes == 50


@pytest.mark.parametrize("capacity", [True, -1, 1.5, float("inf"), "1024", None])
def test_r6_consumption_allowance_rejects_untyped_capacity(capacity):
    from giclab.harness.sira_gate_a import GateAContractError
    from giclab.harness.sira_gate_a_runtime import _AdmittedPublicationAllowance

    with pytest.raises(GateAContractError, match="capacity is malformed"):
        _AdmittedPublicationAllowance(capacity)


def test_r6_zero_consumption_window_denies_actual_positive_growth():
    from giclab.harness.sira_gate_a import GateAContractError
    from giclab.harness.sira_gate_a_runtime import _AdmittedPublicationAllowance

    allowance = _AdmittedPublicationAllowance(0)
    allowance(0)
    with pytest.raises(GateAContractError, match="allowance exhausted"):
        allowance(1)
    assert allowance.remaining == 0
    with pytest.raises(GateAContractError, match="retained denial"):
        allowance.require_no_denial()


@pytest.mark.parametrize("binding", ["exact", "missing", "wrong-inode"])
def test_retained_openat_guard_tracks_real_directory_dup(tmp_path, binding):
    spec = importlib.util.spec_from_file_location(
        "r6_retained_duplicate_guard", ROOT / "tests/control/retained_candidate_effects.py"
    )
    worker = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = worker
    spec.loader.exec_module(worker)
    root = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    duplicate = None
    calls = []
    try:
        metadata = os.fstat(root)
        identity = (metadata.st_dev, metadata.st_ino)
        directories = (
            {}
            if binding == "missing"
            else {
                root: (tmp_path, identity if binding == "exact" else (identity[0], identity[1] + 1))
            }
        )

        def perform(fd):
            calls.append(fd)
            return os.dup(fd)

        if binding != "exact":
            with pytest.raises(RuntimeError, match="unbound directory descriptor"):
                worker._duplicate_tracked_descriptor(
                    root, native_dup=perform, native_close=os.close, directories=directories
                )
            assert calls == []
        else:
            duplicate = worker._duplicate_tracked_descriptor(
                root, native_dup=perform, native_close=os.close, directories=directories
            )
            assert duplicate != root and calls == [root]
            assert directories[duplicate] == directories[root]
            assert os.fstat(duplicate).st_ino == metadata.st_ino
    finally:
        if duplicate is not None:
            os.close(duplicate)
        os.close(root)


@pytest.mark.parametrize("role", ["pilot-start", "cleanup-journal", "control-json"])
@pytest.mark.parametrize("denied", [False, True])
def test_r6_condition_bridge_admits_control_roots_before_actual_writers(tmp_path, role, denied):
    from dataclasses import replace
    from threading import Event
    from types import SimpleNamespace

    from giclab.control.production import _host_module
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded
    from giclab.harness.t09_cleanup_state import CleanupLifecycleStage
    from giclab.harness.t09_provider_contracts import V11_PROVIDER_CONTRACT
    from giclab.harness.t09_sira_pilot import initialize_pilot_state
    from tests.test_t09_early_cleanup_state import IncrementingClock, initialize_journal

    host = _host_module(ROOT)
    boundary, observer = conformance._observer_for(_binding())
    if denied:
        boundary.condition_caps = replace(boundary.condition_caps, max_output_bytes=1)
    control = tmp_path / "pilot-v11"
    control.mkdir(mode=0o700)
    state = control / "pilot-state.json"
    initialize_pilot_state(
        state,
        provider_contract=V11_PROVIDER_CONTRACT,
        execution_contract_sha256="a" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    clock = IncrementingClock()
    journal = initialize_journal(tmp_path, clock)
    bridge = object.__new__(host._ConditionSessionBridge)
    bridge.attempt_root = tmp_path / "attempt"
    bridge.control_roots = (control, journal.root)
    bridge.cancelled = Event()
    grants = []

    def reserve(count):
        grants.append(count)
        observer.reserve_output_bytes(total_bytes=observer._remote_output_allowance + count)

    bridge.host_output = SimpleNamespace(handed_off=False, reserve=reserve)
    prior = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for root in bridge.control_roots
        for p in root.rglob("*")
        if p.is_file()
    }
    admission_reset = host._HOST_OUTPUT_ADMISSION.set(bridge.admit_path)
    try:

        def publish():
            if role == "pilot-start":
                host.reserve_condition_start(
                    state,
                    execution_contract_sha256="a" * 64,
                    run_id=V11_PROVIDER_CONTRACT.run_ids[0],
                    start_intent_sha256="2" * 64,
                    before_write=host._HOST_OUTPUT_ADMISSION.get(),
                )
            elif role == "cleanup-journal":
                host.early_cleanup_journal(
                    SimpleNamespace(early_cleanup_journal=journal.root)
                ).advance_lifecycle(CleanupLifecycleStage.PACKAGE_TRANSITION, clock=clock)
            else:
                host.write_exclusive(control / "new-control.json", {"actual": "control-write"})

        if denied:
            with pytest.raises(ProviderBudgetExceeded):
                publish()
            assert {
                str(p.relative_to(tmp_path)): p.read_bytes()
                for root in bridge.control_roots
                for p in root.rglob("*")
                if p.is_file()
            } == prior
        else:
            publish()
            after = sum(host.full_attempt_tree_usage(p).bytes for p in bridge.control_roots)
            growth = after - sum(map(len, prior.values()))
            observer.output_bytes(
                total_bytes=growth, retained_output_bytes=observer._remote_output_allowance - growth
            )
            assert boundary.condition_observed_usage.output_bytes == growth > 0
            assert observer._remote_output_allowance == sum(grants)
        assert len(grants) == 1
        with pytest.raises(host.T09HostError, match="declared writer roots"):
            host.write_exclusive(tmp_path / "foreign/denied.json", {"forbidden": True})
        assert not (tmp_path / "foreign").exists()
    finally:
        host._HOST_OUTPUT_ADMISSION.reset(admission_reset)


def test_r6_shared_pilot_entry_establishes_and_reuses_one_accountant(tmp_path):
    from dataclasses import replace
    from types import SimpleNamespace

    from giclab.control.production import ProductionCategory3World
    from giclab.harness.t09_sira_pilot import (
        initialize_pilot_state,
        mark_empirical_entry,
        mark_essential_failure_sealed,
        reserve_condition_start,
    )

    boundary, template = conformance._observer_for(_binding())
    world = object.__new__(ProductionCategory3World)
    world.repository = ROOT
    world.root = tmp_path
    world._pilot_state = tmp_path / "pilot-state.json"
    world._condition_observers = {}
    world._remote_cleanup_sessions = {}
    world._campaign_output_boundary = None
    world._campaign_cleanup_remaining = None
    world._campaign_cleanup_lock = threading.Lock()
    world._campaign_admission_blocked = False
    # This primitive invokes the real production failure reservation. Its
    # allowance comes from the unchanged pinned execution contract, rather than
    # the deliberately smaller conformance-only observer fixture. The separate
    # insufficient-cap regression remains active and rejects that fixture.
    execution = json.loads((ROOT / V16_PROVIDER_CONTRACT.execution_contract_path).read_bytes())
    cap = execution["runtime_limits"]["max_output_bytes_per_attempt"]
    world._runtime_budget = SimpleNamespace(
        condition_caps={template.run_id: replace(boundary.condition_caps, max_output_bytes=cap)},
        aggregate_caps=boundary.aggregate_caps,
        model_revision=template.model_revision,
        service_tier=template.service_tier,
    )
    world._campaign_deadline_monotonic = template.campaign_deadline_monotonic
    world.clock = template.clock
    world._seen_call_ids = {"prior-session-call"}
    world._seen_logical_call_ids = {"prior-session-logical"}
    world._aggregate_usage = boundary.aggregate_usage
    world._aggregate_observed_usage = boundary.aggregate_observed_usage
    world._accounting = {}
    initialize_pilot_state(
        world._pilot_state,
        provider_contract=V16_PROVIDER_CONTRACT,
        execution_contract_sha256="a" * 64,
        pilot_started_at_epoch=1.0,
        lambda_started_at_epoch=1.0,
    )
    assert world._condition_observers == {}
    with world._pilot_control_writer(template.run_id) as (admit, observed):
        observer = world._condition_observers[template.run_id]
        assert observer.prior_call_ids == frozenset({"prior-session-call"})
        assert observer.prior_logical_call_ids == frozenset({"prior-session-logical"})
        reserve_condition_start(
            world._pilot_state,
            execution_contract_sha256="a" * 64,
            run_id=template.run_id,
            start_intent_sha256="2" * 64,
            before_write=admit,
            after_output_write=observed,
        )
    written = world._pilot_state.stat().st_size
    allowance = observer._controller_output_allowance
    assert observer._controller_output_observed == written
    assert world._condition_accountant(template.run_id) is observer
    assert observer._controller_output_allowance == allowance
    with world._pilot_control_writer(template.run_id) as (admit, observed):
        mark_empirical_entry(
            world._pilot_state,
            execution_contract_sha256="a" * 64,
            run_id=template.run_id,
            supervised_release_receipt_sha256="3" * 64,
            before_write=admit,
            after_output_write=observed,
        )
    written += world._pilot_state.stat().st_size
    assert world._condition_accountant(template.run_id) is observer
    assert observer._controller_output_observed == written
    assert world._aggregate_usage.output_bytes == (
        observer._controller_output_allowance + observer.boundary.campaign_output_granted
    )
    assert world._aggregate_observed_usage.output_bytes == observer._controller_output_observed
    assert observer._controller_output_allowance > observer._controller_output_observed

    # The actual failure seal clears a longer start reservation. Occupancy
    # shrinks, while the real write count remains positive and fully admitted.
    before_seal = world._pilot_state.stat().st_size
    with world._pilot_control_writer(template.run_id, failure=True) as (admit, observed):
        mark_essential_failure_sealed(
            world._pilot_state,
            execution_contract_sha256="a" * 64,
            run_id=template.run_id,
            manifest_sha256="4" * 64,
            receipt_sha256="5" * 64,
            before_write=admit,
            after_output_write=observed,
        )
    after_seal = world._pilot_state.stat().st_size
    assert after_seal < before_seal
    written += after_seal
    assert observer._controller_output_observed == written
    assert world._aggregate_observed_usage.output_bytes == written
    assert observer._controller_output_allowance > written
    # Inject a writer bypass to prove the independent census still rejects
    # uncovered growth. This is detection coverage, not pre-growth prevention.
    from giclab.control.adapters import AdapterFailure

    with (
        pytest.raises(AdapterFailure, match="occupancy do not reconcile"),
        world._pilot_control_writer(template.run_id),
    ):
        (tmp_path / "injected-unadmitted.json").write_bytes(b"{}")


def test_r6_failed_initial_control_reserve_cannot_be_reused(tmp_path):
    from types import SimpleNamespace

    from giclab.control.adapters import AdapterFailure
    from giclab.control.production import ProductionCategory3World
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    boundary, template = conformance._observer_for(_binding())
    world = object.__new__(ProductionCategory3World)
    world._condition_observers = {}
    world._remote_cleanup_sessions = {}
    world._campaign_output_boundary = None
    world._campaign_cleanup_remaining = None
    world._campaign_cleanup_lock = threading.Lock()
    world._campaign_admission_blocked = False
    world._runtime_budget = SimpleNamespace(
        condition_caps={template.run_id: boundary.condition_caps},
        aggregate_caps=boundary.aggregate_caps,
        model_revision=template.model_revision,
        service_tier=template.service_tier,
    )
    world._campaign_deadline_monotonic = template.campaign_deadline_monotonic
    world.clock = template.clock
    world._seen_call_ids = set()
    world._seen_logical_call_ids = set()
    world._aggregate_usage = boundary.aggregate_usage
    world._aggregate_observed_usage = boundary.aggregate_observed_usage
    with pytest.raises(ProviderBudgetExceeded):
        world._condition_accountant(template.run_id)
    observed = world._condition_observers[template.run_id]
    before = observed.boundary.accounting_document()
    with pytest.raises(AdapterFailure, match="failed before its first writer"):
        world._condition_accountant(template.run_id)
    assert observed.boundary.accounting_document() == before
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("fault", ["none", "deny", "partial", "retirement-drift"])
def test_r6_mutable_control_counts_actual_writes_instead_of_signed_occupancy(
    tmp_path, monkeypatch, fault
):
    from giclab.harness import t09_sira_pilot as pilot

    path = tmp_path / "state.json"
    original = b"x" * 4096
    path.write_bytes(original)
    grants, writes = [], []

    def admit(candidate, count):
        assert candidate == path
        assert path.read_bytes() == original
        assert list(tmp_path.iterdir()) == [path]
        if fault == "deny":
            raise RuntimeError("synthetic pre-growth denial")
        grants.append(count)

    actual_write = pilot.os.write

    def write(fd, data):
        if fault == "partial":
            if writes:
                raise OSError("synthetic interrupted admitted write")
            data = data[:7]
        count = actual_write(fd, data)
        if fault == "retirement-drift" and not writes:
            replacement = tmp_path / "foreign-replacement"
            replacement.write_bytes(b"foreign owned replacement")
            replacement.replace(path)
        return count

    monkeypatch.setattr(pilot.os, "write", write)
    if fault == "none":
        pilot._write_json_atomic(
            path, {"small": True}, before_write=admit, after_output_write=writes.append
        )
        assert len(path.read_bytes()) < len(original)
        assert sum(writes) == path.stat().st_size == sum(grants)
    else:
        with pytest.raises((RuntimeError, OSError), match=r"synthetic|retirement identity"):
            pilot._write_json_atomic(
                path, {"small": True}, before_write=admit, after_output_write=writes.append
            )
        assert path.read_bytes() == (
            b"foreign owned replacement" if fault == "retirement-drift" else original
        )
        temporary = list(tmp_path.glob(".state.json.*.tmp"))
        if fault == "deny":
            assert not temporary and not grants and not writes
        else:
            assert len(temporary) == 1
            assert temporary[0].stat().st_size == sum(writes)
            if fault == "retirement-drift":
                assert sum(writes) == sum(grants)
            else:
                assert sum(writes) == 7 < sum(grants)


# Campaign writers use the production admission connection and real file writers.
def _campaign_writer_world(root):
    from dataclasses import replace
    from types import SimpleNamespace

    from giclab.control.production import ProductionCategory3World

    boundary, template = conformance._observer_for(_binding())
    execution = json.loads((ROOT / V16_PROVIDER_CONTRACT.execution_contract_path).read_bytes())
    cap = execution["runtime_limits"]["max_output_bytes_per_attempt"]
    world = object.__new__(ProductionCategory3World)
    world.root = root
    world.contract = V16_PROVIDER_CONTRACT
    world.clock = template.clock
    controls = SimpleNamespace(
        capability_path=lambda slot, contract: root / f"launch-slot-{slot:02d}.json"
    )
    world.low_level_effects = SimpleNamespace(campaign_low_level_controls=lambda: controls)
    world._runtime_budget = SimpleNamespace(
        aggregate_caps=replace(boundary.aggregate_caps, max_output_bytes=4 * cap),
        condition_caps={
            run: replace(boundary.condition_caps, max_output_bytes=cap)
            for run in V16_PROVIDER_CONTRACT.run_ids
        },
        model_revision=template.model_revision,
        service_tier=template.service_tier,
    )
    world._aggregate_usage = boundary.aggregate_usage
    world._aggregate_observed_usage = boundary.aggregate_observed_usage
    world._campaign_output_boundary = None
    world._campaign_cleanup_remaining = None
    world._campaign_cleanup_lock = threading.Lock()
    world._campaign_writes = []
    world._campaign_admission_blocked = False
    world._campaign_started_monotonic = None
    world._campaign_deadline_monotonic = None
    world._condition_observers = {}
    world._remote_cleanup_sessions = {}
    world._seen_call_ids = set()
    world._seen_logical_call_ids = set()
    world._accounting = {}
    return world, template


def _campaign_actual_writer(root, role):
    from giclab.harness import t09_model_metadata_receipt as metadata
    from giclab.harness import t09_pragmatic_provider as provider
    from giclab.harness.t09_cleanup_state import CleanupLifecycleStage, EarlyCleanupJournal

    target = root / "output.json"
    if role == "record":
        return lambda: provider.write_exclusive(target, {"actual": "π"}), target
    if role == "bytes":
        return lambda: provider.write_bytes_exclusive(target, b"actual bytes"), target
    if role == "append":
        target.write_bytes(b"prior\n")
        return lambda: provider._append_jsonl(target, {"actual": "π"}), target
    if role in {"copy", "held-copy"}:
        source = root / "source"
        source.write_bytes(b"retained fixture bytes")
        source.chmod(0o600)
        if role == "copy":
            return lambda: provider._copy_campaign_file(source, target), target
        return lambda: provider._copy_exact_private_file(source, target, label="fixture"), target
    if role == "metadata":
        root.chmod(0o700)
        return lambda: metadata._write_private_exclusive(target, {"actual": "π"}), target
    journal = EarlyCleanupJournal.initialize(
        root / "journal",
        plan_id="PLAN-EXP0001-PILOT-V10",
        host_run_id="RUN-T09-PILOT-HOST-AUTONOMOUS-0003",
        package_commit="a" * 40,
        plan_sha256="b" * 64,
        provider_instance_id="instance-owned-0003",
        provider_instance_identity_sha256="c" * 64,
        provider_started_at_epoch=999.0,
        launch_slot=1,
        replacement_eligibility_sha256=None,
        firewall_baseline_identity_sha256="d" * 64,
        clock=lambda: 1000.0,
    )
    if role == "cleanup-journal":
        return lambda: journal.advance_lifecycle(
            CleanupLifecycleStage.SOURCE_STAGING, clock=lambda: 1001.0
        ), journal.versions / "00000002.json"
    assert role == "cleanup-receipt"
    return lambda: journal.write_basic_closeout_receipt(target), target


@pytest.mark.parametrize(
    "role",
    [
        "record",
        "bytes",
        "append",
        "copy",
        "held-copy",
        "metadata",
        "cleanup-journal",
        "cleanup-receipt",
    ],
)
@pytest.mark.parametrize("denied", [False, True])
def test_r6_campaign_actual_writers_shared_admission_precedes_growth(tmp_path, role, denied):
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    world, _ = _campaign_writer_world(tmp_path)
    emit, target = _campaign_actual_writer(tmp_path, role)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    boundary = world._campaign_accountant()
    assert boundary._started is None and world._campaign_started_monotonic is None
    if denied:
        boundary.reserve_campaign_output_bytes(
            boundary.aggregate_caps.max_output_bytes - boundary.aggregate_usage.output_bytes
        )
        with pytest.raises(ProviderBudgetExceeded), world._campaign_writer_scope():
            emit()
        after = {
            p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
        }
        assert after == before
        assert boundary.campaign_output_observed == 0
        assert world._campaign_admission_blocked
    else:
        with world._campaign_writer_scope():
            emit()
        allowance = world._campaign_writes[-1]
        assert allowance.observed == allowance.granted > 0
        prior = len(before.get(target.relative_to(tmp_path), b""))
        assert target.stat().st_size - prior == allowance.observed
        assert boundary.campaign_output_observed == allowance.observed
        assert boundary.aggregate_observed_usage.output_bytes == allowance.observed
        assert world._aggregate_usage.output_bytes == boundary.campaign_output_granted


@pytest.mark.parametrize(
    "role",
    [
        "record",
        "bytes",
        "append",
        "copy",
        "held-copy",
        "metadata",
        "cleanup-journal",
        "cleanup-receipt",
    ],
)
def test_r6_campaign_partial_writer_keeps_actual_prefix_and_unused_grant(
    tmp_path, monkeypatch, role
):
    world, _ = _campaign_writer_world(tmp_path)
    emit, _ = _campaign_actual_writer(tmp_path, role)
    original_write = os.write
    calls = 0

    def interrupted(fd, data):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original_write(fd, data[:7])
        raise OSError("injected campaign writer interruption")

    with monkeypatch.context() as patch:
        patch.setattr(os, "write", interrupted)
        with pytest.raises(OSError), world._campaign_writer_scope():
            emit()
    allowance = world._campaign_writes[-1]
    assert allowance.observed == 7 < allowance.granted
    boundary = world._campaign_accountant()
    assert boundary.campaign_output_observed == 7
    assert boundary.campaign_output_granted == world._aggregate_usage.output_bytes
    assert world._aggregate_observed_usage.output_bytes == 7


def test_r6_campaign_capacity_conserved_across_four_condition_boundaries_and_cleanup(tmp_path):
    from giclab.harness import t09_pragmatic_provider as provider

    world, template = _campaign_writer_world(tmp_path)
    with world._campaign_writer_scope():
        provider.write_bytes_exclusive(tmp_path / "entry", b"entry")
    initial = world._campaign_accountant()
    assert initial._started is None
    assert world._campaign_deadline_monotonic is None
    world._campaign_deadline_monotonic = template.campaign_deadline_monotonic
    for index, run in enumerate(V16_PROVIDER_CONTRACT.run_ids):
        observer = world._condition_accountant(run)
        observer.allocate_controller_output_bytes(count=100)
        observer.observe_controller_output_bytes(count=7)
        world._record_boundary_state(run, observer)
        assert world._aggregate_observed_usage.output_bytes == 5 + 7 * (index + 1)
        assert observer.boundary.campaign_output_observed == 5
        assert observer.boundary.campaign_output_granted == initial.campaign_output_granted
    upper = world._aggregate_usage.output_bytes
    with world._campaign_writer_scope(cleanup=True):
        provider.write_bytes_exclusive(tmp_path / "cleanup", b"clean")
    assert world._aggregate_usage.output_bytes == upper
    assert world._aggregate_observed_usage.output_bytes == 38
    assert world._campaign_accountant().campaign_output_observed == 10


def test_r6_campaign_denial_is_sticky_but_prefunded_cleanup_survives(tmp_path):
    from giclab.harness import t09_pragmatic_provider as provider
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    world, template = _campaign_writer_world(tmp_path)
    boundary = world._campaign_accountant()
    boundary.reserve_campaign_output_bytes(
        boundary.aggregate_caps.max_output_bytes - boundary.aggregate_usage.output_bytes
    )
    with (
        pytest.raises(ProviderBudgetExceeded, match="caught campaign"),
        world._campaign_writer_scope(),
    ):
        from contextlib import suppress

        with suppress(ProviderBudgetExceeded):
            provider.write_bytes_exclusive(tmp_path / "denied", b"denied")
    assert not (tmp_path / "denied").exists()
    with world._campaign_writer_scope(cleanup=True):
        provider.write_bytes_exclusive(tmp_path / "failure", b"bounded failure")
    assert boundary.aggregate_observed_usage.output_bytes == len(b"bounded failure")
    world._campaign_deadline_monotonic = template.campaign_deadline_monotonic
    with pytest.raises(ProviderBudgetExceeded, match="blocked campaign"):
        world._condition_accountant(V16_PROVIDER_CONTRACT.run_ids[0])
    assert not world._condition_observers


@pytest.mark.parametrize("alias", ["symlink", "hardlink", "outside"])
def test_r6_campaign_writer_rejects_alias_before_admission(tmp_path, alias):
    from giclab.control.adapters import AdapterFailure
    from giclab.harness import t09_pragmatic_provider as provider

    owned = tmp_path / "owned"
    owned.mkdir(mode=0o700)
    outside = tmp_path / "foreign"
    outside.write_bytes(b"unrelated")
    world, _ = _campaign_writer_world(owned)
    target = owned / "target"
    if alias == "symlink":
        target.symlink_to(outside)
    elif alias == "hardlink":
        os.link(outside, target)
    else:
        target = outside
    boundary = world._campaign_accountant()
    before = boundary.accounting_document()
    with pytest.raises(AdapterFailure), world._campaign_writer_scope():
        provider._append_jsonl(target, {"denied": True})
    assert outside.read_bytes() == b"unrelated"
    assert boundary.accounting_document() == before
    assert not world._campaign_writes


def test_r6_campaign_writer_capability_expires_at_scope_exit(tmp_path):
    from giclab.harness import t09_pragmatic_provider as provider

    world, _ = _campaign_writer_world(tmp_path)
    with world._campaign_writer_scope():
        provider.write_bytes_exclusive(tmp_path / "output", b"valid")
    allowance = world._campaign_writes[-1]
    before = world._campaign_accountant().accounting_document()
    with pytest.raises(RuntimeError, match="own admitted allowance"):
        allowance.observe(0)
    assert world._campaign_accountant().accounting_document() == before


# Cleanup has its own campaign identity and consumes the shared prefunded reserve.
def _cleanup_output_binding(root):
    from giclab.harness.campaign_output import CleanupOutputBinding

    return CleanupOutputBinding(
        "plan-cleanup",
        "host-cleanup",
        "a" * 40,
        "b" * 40,
        "c" * 64,
        str(root),
        "d" * 64,
        1,
        output_roots=(str(root),),
    )


@pytest.mark.parametrize(
    "role",
    [
        "host-json",
        "host-bytes",
        "host-atomic",
        "pilot-atomic",
        "pilot-exclusive",
        "cleanup-journal",
        "cleanup-receipt",
        "phase-control",
        "phase-receipt",
        "environment-state",
    ],
)
@pytest.mark.parametrize("denied", [False, True])
def test_r6_cleanup_child_channel_actual_writer_before_growth(tmp_path, role, denied):
    import threading

    from giclab.control.production import _host_module
    from giclab.harness import t09_sira_pilot as pilot
    from giclab.harness.campaign_output import (
        CleanupOutputAuthority,
        CleanupOutputChannel,
        campaign_output_scope,
        cleanup_output_inventory,
        reconcile_cleanup_output,
    )
    from tests.control.retained_candidate_effects import write

    host = _host_module(ROOT)
    world, _ = _campaign_writer_world(tmp_path)
    target = tmp_path / "record.json"
    calls = []
    if role.startswith("cleanup-"):
        action, target = _campaign_actual_writer(tmp_path, role)
    elif role == "host-json":
        action = partial(host.write_exclusive, target, {"actual": "value"})
    elif role == "host-bytes":
        action = partial(host.write_bytes_exclusive, target, b"actual bytes")
    elif role == "host-atomic":
        target.write_bytes(b"prior bytes")
        action = partial(host.write_atomic, target, {"actual": "replacement"})
    elif role == "pilot-atomic":
        target.write_bytes(b"prior bytes")
        action = partial(
            pilot._write_json_atomic,
            target,
            {"actual": "replacement"},
            before_write=lambda *_: calls.append("legacy"),
            after_output_write=lambda *_: calls.append("legacy-observe"),
        )
    elif role == "pilot-exclusive":
        action = partial(
            pilot._write_json_exclusive,
            target,
            {"actual": "value"},
            before_write=lambda *_: calls.append("legacy"),
            after_output_write=lambda *_: calls.append("legacy-observe"),
        )
    elif role == "environment-state":
        from types import SimpleNamespace

        from tests.control.retained_candidate_effects import ImageCommandChannel

        state = object.__new__(ImageCommandChannel)
        state.transaction_root = tmp_path
        state.binding = SimpleNamespace(digest="f" * 64)
        state.loaded = state.tagged = False
        state.load_count = state.removal_count = 0
        state.before_load = set()
        state.containers = {}
        target.write_bytes(b"prior fixture state")
        action = partial(state.save_state, target)
    elif role == "phase-receipt":
        from giclab.harness.t09_remote_host_phases import write_phase_receipt

        action = partial(write_phase_receipt, target, {"actual": "phase-receipt"})
    else:
        action = partial(write, target, {"actual": "phase"})
    inventory_before = cleanup_output_inventory(tmp_path)
    before = target.read_bytes() if target.exists() else None
    original_paths = set(tmp_path.rglob("*"))
    left, right = socket.socketpair()
    errors = []
    deadline = time.monotonic() + 5
    from giclab.harness.sira_gate_a import ProviderBudgetExceeded

    with (
        pytest.raises(ProviderBudgetExceeded) if denied else nullcontext(),
        world._campaign_writer_scope(cleanup=True),
    ):
        authority = CleanupOutputAuthority(
            _cleanup_output_binding(tmp_path), deadline=deadline, monotonic=time.monotonic
        )
        if denied:
            world._campaign_cleanup_remaining = 0
        server = CleanupOutputChannel(left.fileno(), authority.binding, deadline)
        client = CleanupOutputChannel(right.fileno(), authority.binding, deadline)

        def serve():
            try:
                server.serve(authority)
            except BaseException as exc:
                errors.append(type(exc).__name__)
            finally:
                left.close()

        thread = threading.Thread(target=serve)
        thread.start()
        try:
            client.connect()
            admission_reset = host._HOST_OUTPUT_ADMISSION.set(
                lambda *_: calls.append("legacy-host")
            )
            try:
                with campaign_output_scope(client.admit):
                    if denied:
                        with pytest.raises(RuntimeError):
                            action()
                    else:
                        action()
            finally:
                host._HOST_OUTPUT_ADMISSION.reset(admission_reset)
            if not denied:
                client.finish()
        finally:
            right.close()
            thread.join(timeout=5)
            authority.close()
        assert not thread.is_alive()
        assert not calls, "a second callback must not charge the same campaign write"
        if denied:
            assert errors == ["ProviderBudgetExceeded"]
            assert (target.read_bytes() if target.exists() else None) == before
            assert set(tmp_path.rglob("*")) == original_paths
            assert not authority.leases
        else:
            assert not errors
            assert len(authority.leases) == 1
            lease = authority.leases[0]
            assert lease.granted == lease.observed == target.stat().st_size
            assert world._campaign_accountant().campaign_output_observed == lease.observed
            assert any(x["operation"] == "verify" for x in authority.events)
            assert authority.events[-1]["operation"] == "close"
            retirement = len(before) if before is not None else 0
            assert lease.retired_bytes == retirement
            census = reconcile_cleanup_output(
                inventory_before, cleanup_output_inventory(tmp_path), authority
            )
            assert census["actual_written_bytes"] == lease.observed
            assert census["exact_replaced_old_bytes"] == retirement
            assert census["occupancy_delta_bytes"] == lease.observed - retirement
            assert census["unreconciled_bytes"] == 0
            assert not census["uncovered_writes"]


@pytest.mark.parametrize("mutation", ["source", "root", "attempt", "replay", "closed", "expired"])
def test_r6_cleanup_authority_rejects_identity_lifetime_before_effect(tmp_path, mutation):
    from dataclasses import replace

    from giclab.harness.campaign_output import CampaignWriterRole, CleanupOutputAuthority

    world, _ = _campaign_writer_world(tmp_path)
    now = [5.0]
    with world._campaign_writer_scope(cleanup=True):
        authority = CleanupOutputAuthority(
            _cleanup_output_binding(tmp_path), deadline=10.0, monotonic=lambda: now[0]
        )
        binding = authority.binding
        if mutation == "source":
            binding = replace(binding, source_commit="e" * 40)
        if mutation == "root":
            binding = replace(binding, transaction_root=str(tmp_path / "other"))
        if mutation == "attempt":
            binding = replace(binding, attempt=2)
        if mutation == "replay":
            authority.claim(binding.document())
        if mutation == "closed":
            authority.close()
        if mutation == "expired":
            now[0] = 10.0
        with pytest.raises((RuntimeError, TimeoutError)):
            authority.claim(binding.document())
            authority.admit(tmp_path / "denied", 12, CampaignWriterRole.HOST_CONTROL)
        assert not authority.leases and not list(tmp_path.iterdir())


def test_r6_cleanup_journal_callback_selects_one_owner(tmp_path):
    from giclab.harness.t09_cleanup_state import CleanupLifecycleStage, EarlyCleanupJournal
    from tests.test_t09_early_cleanup_state import IncrementingClock, initialize_journal

    calls = []
    journal = initialize_journal(tmp_path, IncrementingClock())
    journal = EarlyCleanupJournal(journal.root, before_write=lambda *_: calls.append("legacy"))
    world, _ = _campaign_writer_world(tmp_path)
    with world._campaign_writer_scope(cleanup=True):
        journal.advance_lifecycle(CleanupLifecycleStage.SOURCE_STAGING, clock=lambda: 1001.0)
    assert not calls and len(world._campaign_writes) == 1
    assert world._campaign_writes[0].observed > 0


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate-sequence",
        "wrong-role",
        "outside-root",
        "disconnect-before-observe",
        "unverified-close",
        "partial-write",
    ],
)
def test_r6_cleanup_wire_failure_keeps_grant_and_actual_prefix(tmp_path, fault):
    import threading

    from giclab.harness.campaign_output import (
        CampaignWriterRole,
        CleanupOutputAuthority,
        CleanupOutputChannel,
    )

    world, _ = _campaign_writer_world(tmp_path)
    deadline = time.monotonic() + 3
    errors = []
    left, right = socket.socketpair()
    with world._campaign_writer_scope(cleanup=True):
        authority = CleanupOutputAuthority(
            _cleanup_output_binding(tmp_path), deadline=deadline, monotonic=time.monotonic
        )
        server = CleanupOutputChannel(left.fileno(), authority.binding, deadline)
        client = CleanupOutputChannel(right.fileno(), authority.binding, deadline)

        def serve():
            try:
                server.serve(authority)
            except BaseException as exc:
                errors.append(type(exc).__name__)
            finally:
                left.close()

        thread = threading.Thread(target=serve)
        thread.start()
        before = world._campaign_cleanup_remaining
        path = tmp_path / "prefix"
        try:
            client.connect()
            if fault == "duplicate-sequence":
                client.sequence = 0
                with pytest.raises(RuntimeError):
                    client.request("grant", path=str(path), size=16, role="host-control")
            elif fault == "wrong-role":
                with pytest.raises(RuntimeError):
                    client.request("grant", path=str(path), size=16, role="empirical-condition")
            elif fault == "outside-root":
                with pytest.raises(RuntimeError):
                    client.admit(tmp_path.parent / "escape", 16, CampaignWriterRole.HOST_CONTROL)
            else:
                lease = client.admit(path, 16, CampaignWriterRole.HOST_CONTROL)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                try:
                    count = os.write(fd, b"partial")
                    assert count == 7
                finally:
                    os.close(fd)
                if fault != "disconnect-before-observe":
                    lease.observe(count)
                if fault == "unverified-close":
                    with pytest.raises(RuntimeError):
                        client.finish()
                # Partial output/ambiguous possibly-sent consumption is retained;
                # disconnection is never evidence permitting a refund.
        finally:
            right.close()
            thread.join(timeout=4)
            authority.close()
        assert not thread.is_alive() and errors
        if fault in {"disconnect-before-observe", "unverified-close", "partial-write"}:
            assert path.read_bytes() == b"partial"
            assert world._campaign_cleanup_remaining == before - 16
            assert authority.leases[0].granted == 16
            assert authority.leases[0].observed == (
                0 if fault == "disconnect-before-observe" else 7
            )
            assert authority.leases[0].closed
        else:
            assert not path.exists() and not authority.leases
            assert world._campaign_cleanup_remaining == before


@pytest.mark.parametrize("binary", [False, True])
def test_r6_cleanup_campaign_keeps_unresolved_atomic_prefix(tmp_path, binary):
    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    target = tmp_path / "published.json"
    pending = host._atomic_publication_temporary(target)
    pending.write_bytes(b"earlier admitted partial evidence")
    pending.chmod(0o600)
    world, _ = _campaign_writer_world(tmp_path)
    with world._campaign_writer_scope(cleanup=True), pytest.raises(FileExistsError):
        if binary:
            host.write_bytes_exclusive(target, b"new bytes")
        else:
            host.write_exclusive(target, {"new": "bytes"})
    assert pending.read_bytes() == b"earlier admitted partial evidence"
    assert not target.exists()
    assert world._campaign_writes[0].observed == 0
    assert world._campaign_writes[0].granted > 0


def test_r6_cleanup_explicit_missing_authority_before_pipe_allocation(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from tests.control.retained_candidate_effects import RetainedCandidateEffects

    effects = object.__new__(RetainedCandidateEffects)
    calls = []

    def forbidden_pipe():
        calls.append("pipe")
        raise AssertionError("missing authority allocated a descriptor")

    monkeypatch.setattr(os, "pipe", forbidden_pipe)
    with pytest.raises(AssertionError):
        effects._cleanup_channel({}, tmp_path, SimpleNamespace(output_authority=None))
    assert not calls


def test_r6_cleanup_census_rejects_disconnected_writer_without_retrospective_grant(tmp_path):
    from giclab.harness.campaign_output import (
        CleanupOutputAuthority,
        cleanup_output_inventory,
        reconcile_cleanup_output,
    )

    world, _ = _campaign_writer_world(tmp_path)
    with world._campaign_writer_scope(cleanup=True):
        authority = CleanupOutputAuthority(
            _cleanup_output_binding(tmp_path),
            deadline=time.monotonic() + 5,
            monotonic=time.monotonic,
        )
        before = cleanup_output_inventory(tmp_path)
        (tmp_path / "unadmitted-control.json").write_bytes(b"unadmitted actual write")
        with pytest.raises(RuntimeError, match="without prior admission"):
            reconcile_cleanup_output(before, cleanup_output_inventory(tmp_path), authority)
        assert not authority.leases
        assert world._campaign_accountant().campaign_output_observed == 0
        assert (tmp_path / "unadmitted-control.json").read_bytes() == b"unadmitted actual write"


def test_r6_cleanup_child_cannot_spend_output_grant_on_immutable_input(tmp_path):
    from dataclasses import replace

    from giclab.harness.campaign_output import CampaignWriterRole, CleanupOutputAuthority

    world, _ = _campaign_writer_world(tmp_path)
    binding = replace(_cleanup_output_binding(tmp_path), output_roots=(str(tmp_path / "output"),))
    with world._campaign_writer_scope(cleanup=True):
        authority = CleanupOutputAuthority(
            binding, deadline=time.monotonic() + 5, monotonic=time.monotonic
        )
        authority.claim(binding.document())
        before = world._campaign_cleanup_remaining
        with pytest.raises(RuntimeError, match="bound root"):
            authority.admit(tmp_path / "input/source", 10, CampaignWriterRole.HOST_CONTROL)
        assert world._campaign_cleanup_remaining == before
        assert not list(tmp_path.iterdir()) and not authority.leases


@pytest.mark.parametrize(
    "fault",
    [
        "first-capture",
        "second-capture",
        "descendant-exit",
        "descendant-term",
        "descendant-backpressure",
        "first-pipe",
        "second-pipe",
        "parent-close",
        "first-output",
        "second-output",
        "popen",
    ],
)
def test_r5_retained_cleanup_process_capture_ownership(
    tmp_path, monkeypatch, record_property, fault
):
    """Contained old-path red: the fixture finally owns every deliberately stranded resource."""
    import subprocess
    import threading
    from types import SimpleNamespace

    import tests.control.retained_candidate_effects as retained
    from giclab.harness.campaign_output import CleanupOutputAuthority

    root = tmp_path / "transaction"
    root.mkdir()
    phases = root / "phases"
    phases.mkdir()
    pid_path = tmp_path / "fixture-descendant.json"
    world, _ = _campaign_writer_world(root)
    effects = object.__new__(retained.RetainedCandidateEffects)
    effects._root = root
    effects.source_inputs = SimpleNamespace(root=ROOT)
    effects.fault_plan = SimpleNamespace(fail_operation=None)
    native_popen = subprocess.Popen
    native_open = os.open
    native_start = threading.Thread.start
    native_pipe = os.pipe
    pipes = []
    output_attempts = []
    processes, workers, output_fds = [], [], []
    starts = []
    script = "import time; time.sleep(30)"
    if fault.startswith("descendant-"):
        descendant = (
            "import os,signal,time; "
            "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
            "os.write(1,b'held stdout\\n'); os.write(2,b'held stderr\\n'); time.sleep(30)"
        )
        if fault == "descendant-backpressure":
            descendant = (
                "import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                "os.write(1,b'x'*1048576); os.write(2,b'y'*1048576); time.sleep(30)"
            )
        script = (
            "import subprocess,sys,json,time; from pathlib import Path; "
            f"p=subprocess.Popen([sys.executable,'-c',{descendant!r}]); "
            f"Path({str(pid_path)!r}).write_text(json.dumps({{'pid':p.pid}})); "
            "time.sleep(0.15); " + ("sys.exit(0)" if fault.endswith("exit") else "time.sleep(30)")
        )

    def launch(_argv, **kwargs):
        if fault == "popen":
            raise OSError("synthetic popen allocation failure")
        process = native_popen([sys.executable, "-c", script], **kwargs)
        processes.append(process)
        return process

    def opened(path, flags, mode=0o777, **kwargs):
        if (
            isinstance(path, (str, Path))
            and Path(path).name in {"host-cleanup-stdout.log", "host-cleanup-stderr.log"}
            and flags & os.O_CREAT
        ):
            output_attempts.append(str(path))
            if (fault == "first-output" and len(output_attempts) == 1) or (
                fault == "second-output" and len(output_attempts) == 2
            ):
                raise OSError("synthetic output allocation failure")
        fd = native_open(path, flags, mode, **kwargs)
        if (
            isinstance(path, (str, Path))
            and Path(path).name in {"host-cleanup-stdout.log", "host-cleanup-stderr.log"}
            and flags & os.O_CREAT
        ):
            st = os.fstat(fd)
            output_fds.append((fd, (st.st_dev, st.st_ino)))
        return fd

    def start(thread, *args, **kwargs):
        workers.append(thread)
        starts.append(len(starts) + 1)
        if fault in {"first-capture", "second-capture"} and len(starts) == (
            1 if fault == "first-capture" else 2
        ):
            raise RuntimeError("synthetic capture startup failure")
        return native_start(thread, *args, **kwargs)

    def pipe():
        if fault == "first-pipe" or (fault == "second-pipe" and pipes):
            raise OSError("synthetic pipe allocation failure")
        pair = native_pipe()
        pipes.append(pair)
        for fd in pair:
            st = os.fstat(fd)
            output_fds.append((fd, (st.st_dev, st.st_ino)))
        return pair

    monkeypatch.setattr(retained.os, "pipe", pipe)
    monkeypatch.setattr(retained.subprocess, "Popen", launch)
    monkeypatch.setattr(retained.os, "open", opened)
    # Green implementation may remove capture threads entirely; inject the
    # equivalent actual capture-registration boundary rather than fake a receipt.
    owner = getattr(retained, "RetainedProcessOwner", None)
    if owner is not None and fault == "parent-close":
        native_close_descriptor = owner.close_descriptor
        close_calls = []

        def close_descriptor(self, fd):
            close_calls.append(fd)
            if len(close_calls) == 1:
                raise OSError("synthetic parent pipe close failure")
            return native_close_descriptor(self, fd)

        monkeypatch.setattr(owner, "close_descriptor", close_descriptor)
    if owner is None:
        monkeypatch.setattr(threading.Thread, "start", start)
    elif fault in {"first-capture", "second-capture"}:
        native_capture = owner.start_capture

        def start_capture(self, *args, **kwargs):
            starts.append(len(starts) + 1)
            if len(starts) == (1 if fault == "first-capture" else 2):
                raise RuntimeError("synthetic capture startup failure")
            return native_capture(self, *args, **kwargs)

        monkeypatch.setattr(owner, "start_capture", start_capture)

    def open_outputs():
        result = []
        for fd, identity in output_fds:
            try:
                st = os.fstat(fd)
            except OSError:
                continue
            if (st.st_dev, st.st_ino) == identity:
                result.append(fd)
        return result

    def descendant_live():
        if not pid_path.exists():
            return False
        pid = json.loads(pid_path.read_bytes())["pid"]
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        except FileNotFoundError:
            return False
        return fields[0] != "Z"

    began = time.monotonic()
    deadline = began + 0.8
    error = None
    observations = None
    try:
        with world._campaign_writer_scope(cleanup=True):
            authority = CleanupOutputAuthority(
                _cleanup_output_binding(root), deadline=deadline, monotonic=time.monotonic
            )
            try:
                effects._cleanup_channel({}, phases, SimpleNamespace(output_authority=authority))
            except BaseException as exc:
                error = type(exc).__name__ + ": " + str(exc)
            finally:
                authority.close()
        receipt = phases / "host-cleanup-output-admission.json"
        observations = {
            "fault": fault,
            "error": error,
            "elapsed": time.monotonic() - began,
            "deadline_seconds": 0.8,
            "capture_workers_alive": sum(t.is_alive() for t in workers),
            "owned_output_fds_open": open_outputs(),
            "owned_streams_open": sum(
                not stream.closed
                for process in processes
                for stream in (process.stdout, process.stderr)
                if stream is not None
            ),
            "descendant_live": descendant_live(),
            "receipt_available": receipt.exists(),
            "capture_file_bytes": {
                p.name: p.stat().st_size for p in phases.glob("host-cleanup-*.log")
            },
            "started_capture_boundaries": len(starts),
        }
        if receipt.exists():
            data = json.loads(receipt.read_bytes())
            observations["receipt_error"] = data["error"]
            observations["child_reaped"] = data["reaped"]
            observations["ownership"] = data.get("ownership")
    finally:
        # Separate, bounded regression containment, including the broken old path.
        # No process name search or unrelated signal target is used.
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)
        if pid_path.exists() and descendant_live():
            os.kill(json.loads(pid_path.read_bytes())["pid"], signal.SIGKILL)
        for thread in workers:
            if thread.ident is not None:
                thread.join(timeout=2)
        for process in processes:
            for stream in (process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
        for fd in open_outputs():
            os.close(fd)
        assert not any(t.is_alive() for t in workers), "regression containment failed"
        until = time.monotonic() + 2
        while descendant_live() and time.monotonic() < until:
            time.sleep(0.01)
        assert not descendant_live(), "regression descendant containment failed"
    assert observations is not None
    record_property("cleanup_ownership", json.dumps(observations, sort_keys=True))
    assert observations["receipt_available"], observations
    assert observations["owned_output_fds_open"] == [], observations
    assert all(count <= 65536 for count in observations["capture_file_bytes"].values()), (
        observations
    )
    assert observations["owned_streams_open"] == 0, observations
    assert observations["capture_workers_alive"] == 0, observations
    assert not observations["descendant_live"], observations
    assert observations["elapsed"] < 1.0, observations
    assert observations["child_reaped"], observations
    if fault in {"first-capture", "second-capture"}:
        assert "synthetic capture startup failure" in observations["error"], observations


@pytest.mark.parametrize("fault", ["finalizer", "group-identity"])
def test_r5_retained_owner_independent_release_and_signal_identity(
    tmp_path, monkeypatch, record_property, fault
):
    import subprocess

    from giclab.control.remote_bridge import RetainedProcessOwner

    owner = RetainedProcessOwner(time.monotonic() + 1)
    read_fd, write_fd = owner.pipe()
    process = owner.start(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    finalized = []

    def finish_first():
        finalized.append("first")
        if fault == "finalizer":
            raise OSError("synthetic first capture finalizer failure")

    owner.start_capture(process.stdout, lambda b: None, finish_first)
    owner.start_capture(process.stderr, lambda b: None, lambda: finalized.append("second"))
    signals = []
    native_killpg = os.killpg

    def killpg(group, sig):
        signals.append((group, sig))
        return native_killpg(group, sig)

    monkeypatch.setattr(os, "killpg", killpg)
    if fault == "group-identity":
        monkeypatch.setattr(os, "getpgid", lambda pid: pid + 1)
    try:
        receipt = owner.close()
        repeated = owner.close()
        assert (
            repeated["signals"] == receipt["signals"]
            and repeated["closed_descriptors"] == receipt["closed_descriptors"]
        )
        assert receipt["reaped"] and receipt["streams_closed"]
        assert not receipt["open_owned_descriptors"]
        assert receipt["created_descriptors"] == receipt["closed_descriptors"] == 2
        assert finalized == ["first", "second"]
        assert receipt["errors"]
        if fault == "group-identity":
            assert all(sig == 0 for _, sig in signals), signals
            assert "ownership changed" in receipt["errors"][0]
        else:
            assert "synthetic first capture finalizer failure" in receipt["errors"][0]
        for fd in (read_fd, write_fd):
            with pytest.raises(OSError):
                os.fstat(fd)
        record_property("retained_owner_release", json.dumps(receipt, sort_keys=True))
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=1)


@pytest.mark.parametrize("fault", ["capture-start", "output-open", "popen"])
def test_r5_condition_carrier_partial_start_uses_same_owner(
    tmp_path, monkeypatch, record_property, fault
):
    from types import SimpleNamespace

    import tests.control.retained_candidate_effects as retained

    root = tmp_path / "transaction"
    root.mkdir()
    inv = root / "condition-invocation.json"
    inv.write_text("{}")
    effects = object.__new__(retained.RetainedCandidateEffects)
    effects.contract = V16_PROVIDER_CONTRACT
    effects.repository = ROOT
    effects.fault_plan = SimpleNamespace(fail_operation=None)
    effects.condition_ownership = {}
    effects.source_inputs = SimpleNamespace(root=ROOT)
    effects.transfer_request = SimpleNamespace(
        binding=SimpleNamespace(remote_root=str(root / "remote")),
        provider_entry_receipt_path=root / "entry/source/receipt.json",
    )
    (root / "remote" / V16_PROVIDER_CONTRACT.control_root_name).mkdir(parents=True)
    (root / "entry/preflight-cleanup-state").mkdir(parents=True)
    consumed = []
    observer = SimpleNamespace(
        allocate_controller_output_bytes=lambda **kw: consumed.append(kw),
        observe_controller_output_bytes=lambda **kw: None,
    )
    request = SimpleNamespace(
        transaction_root=root,
        run_id=V16_PROVIDER_CONTRACT.run_ids[0],
        evaluator_run_id="fixture-evaluator",
        frozen_manifest_sha256="a" * 64,
        raw_output_root="attempts/one/raw",
    )
    owners = []
    native_owner = retained.RetainedProcessOwner

    def owned(deadline):
        value = native_owner(deadline)
        owners.append(value)
        return value

    monkeypatch.setattr(retained, "RetainedProcessOwner", owned)
    native_popen = retained.subprocess.Popen

    def launch(argv, **kwargs):
        if fault == "popen":
            raise OSError("synthetic condition popen failure")
        return native_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)

    monkeypatch.setattr(retained.subprocess, "Popen", launch)

    def fail_capture(*args, **kwargs):
        raise RuntimeError("synthetic condition capture startup failure")

    monkeypatch.setattr(native_owner, "start_capture", fail_capture)
    native_open = os.open

    def opened(path, flags, mode=0o777, **kwargs):
        if fault == "output-open" and path == inv.with_suffix(".stderr"):
            raise OSError("synthetic condition output open failure")
        return native_open(path, flags, mode, **kwargs)

    monkeypatch.setattr(os, "open", opened)
    result = effects._condition_channel(inv, request, observer)
    assert result.returncode != 0 and "synthetic condition" in result.stderr
    assert len(owners) == 1 and consumed
    document = owners[0].document()
    assert document["reaped"] and document["streams_closed"]
    assert not document["open_owned_descriptors"] and not document["errors"]
    assert document["capture_workers"] == 0
    record_property("condition_owner", json.dumps(document, sort_keys=True))


@pytest.mark.parametrize("failure", ["partial", "retirement-drift"])
def test_r6_actual_atomic_writer_retains_partial_and_rejects_retirement_drift(
    tmp_path, monkeypatch, failure
):
    from giclab.control.production import _host_module
    from giclab.harness.campaign_output import (
        CleanupOutputAuthority,
        campaign_output_scope,
        cleanup_output_inventory,
        reconcile_cleanup_output,
    )

    host = _host_module(ROOT)
    world, _ = _campaign_writer_world(tmp_path)
    target = tmp_path / "actual.json"
    target.write_bytes(b"old exact bytes")
    temporary = target.with_suffix(f".{os.getpid()}.tmp")
    original_write = os.write
    before = cleanup_output_inventory(tmp_path)
    changed = False

    def interrupted_write(fd, data):
        nonlocal changed
        if temporary.exists() and os.fstat(fd).st_ino == temporary.lstat().st_ino:
            if failure == "partial":
                if changed:
                    raise OSError("injected actual partial publication")
                changed = True
                return original_write(fd, data[:7])
            if not changed:
                changed = True
                foreign = tmp_path / "foreign-input"
                foreign.write_bytes(b"foreign replacement preserved")
                foreign.replace(target)
        return original_write(fd, data)

    monkeypatch.setattr(os, "write", interrupted_write)
    with world._campaign_writer_scope(cleanup=True):
        authority = CleanupOutputAuthority(
            _cleanup_output_binding(tmp_path),
            deadline=time.monotonic() + 5,
            monotonic=time.monotonic,
        )
        authority.claim(authority.binding.document())
        with campaign_output_scope(authority.admit), pytest.raises((OSError, RuntimeError)):
            host.write_atomic(target, {"actual": "replacement"})
        (lease,) = authority.leases
        assert lease.granted > 0 and lease.retired_bytes == 0 and lease.final_identity is None
        assert lease.temporary_path == temporary
        assert temporary.stat().st_size == lease.observed > 0
        assert world._campaign_accountant().campaign_output_observed == lease.observed
        after = cleanup_output_inventory(tmp_path)
        if failure == "partial":
            assert lease.observed == 7 and target.read_bytes() == b"old exact bytes"
            census = reconcile_cleanup_output(before, after, authority)
            assert census["actual_written_bytes"] == 7 and census["unreconciled_bytes"] == 0
        else:
            assert target.read_bytes() == b"foreign replacement preserved"
            with pytest.raises(RuntimeError, match="byte equation"):
                reconcile_cleanup_output(before, after, authority)
        assert world._campaign_cleanup_remaining >= 0
        authority.close()


def test_r6_repeated_replacement_reconciles_each_exact_retirement_without_refund(tmp_path):
    from giclab.control.production import _host_module
    from giclab.harness.campaign_output import (
        CleanupOutputAuthority,
        campaign_output_scope,
        cleanup_output_inventory,
        reconcile_cleanup_output,
    )

    host = _host_module(ROOT)
    world, _ = _campaign_writer_world(tmp_path)
    path = tmp_path / "mutable.json"
    path.write_bytes(b"prior retained state")
    initial = path.stat().st_size
    before = cleanup_output_inventory(tmp_path)
    with world._campaign_writer_scope(cleanup=True):
        authority = CleanupOutputAuthority(
            _cleanup_output_binding(tmp_path),
            deadline=time.monotonic() + 5,
            monotonic=time.monotonic,
        )
        authority.claim(authority.binding.document())
        remaining = world._campaign_cleanup_remaining
        with campaign_output_scope(authority.admit):
            host.write_atomic(path, {"payload": "x" * 101})
            first_size = path.stat().st_size
            host.write_atomic(path, {"payload": "small"})
        first, second = authority.leases
        assert first.retired_bytes == initial
        assert second.retired_bytes == first_size
        assert first.final_identity == second.initial_identity
        assert remaining - world._campaign_cleanup_remaining == first.granted + second.granted
        assert (
            world._campaign_accountant().campaign_output_observed
            == first.observed + second.observed
        )
        census = reconcile_cleanup_output(before, cleanup_output_inventory(tmp_path), authority)
        assert census["exact_replaced_old_bytes"] == initial + first_size
        assert census["unreconciled_bytes"] == 0
        assert len(census["retirements"]) == 2
        authority.close()


@pytest.mark.parametrize("partial_state", [False, True])
def test_r6_selection_callback_counts_nested_receipt_and_replaced_state(
    tmp_path, monkeypatch, partial_state
):
    from giclab.harness import t09_sira_pilot as pilot

    world, _ = _campaign_writer_world(tmp_path)
    world.repository = ROOT
    world.public_root = tmp_path / "public"
    world.public_root.mkdir(mode=0o700)
    world._pilot_state = tmp_path / "control/state.json"
    world._pilot_state.parent.mkdir(mode=0o700)
    original = b"old retained state" * 256
    world._pilot_state.write_bytes(original)
    world._campaign_deadline_monotonic = time.monotonic() + 30
    run = V16_PROVIDER_CONTRACT.run_ids[0]
    observer = world._condition_accountant(run)
    receipt = world._pilot_state.parent / "selections" / run / "selection-0001.json"
    actual_write = pilot.os.write
    calls = 0

    def write(fd, data):
        nonlocal calls
        calls += 1
        if partial_state and calls >= 2:
            if calls > 2:
                raise OSError("synthetic selection state interruption")
            data = data[:7]
        return actual_write(fd, data)

    monkeypatch.setattr(pilot.os, "write", write)
    with (
        pytest.raises(OSError, match="synthetic selection") if partial_state else nullcontext(),
        world._pilot_control_writer(run, extra_paths=(receipt,)) as (admit, observed),
    ):
        pilot._write_json_exclusive(
            receipt,
            {"selection": "actual receipt"},
            before_write=admit,
            after_output_write=observed,
        )
        pilot._write_json_atomic(
            world._pilot_state, {"selected": True}, before_write=admit, after_output_write=observed
        )
    receipt_size = receipt.stat().st_size
    if partial_state:
        assert world._pilot_state.read_bytes() == original
        temporary = list(world._pilot_state.parent.glob(".state.json.*.tmp"))
        assert len(temporary) == 1 and temporary[0].stat().st_size == 7
        expected = receipt_size + 7
    else:
        assert world._pilot_state.stat().st_size < len(original)
        expected = receipt_size + world._pilot_state.stat().st_size
    census = observer.control_write_reconciliations[-1]
    assert census["actual_written_bytes"] == expected and census["unreconciled_bytes"] == 0
    assert census["exact_retired_old_bytes"] == (0 if partial_state else len(original))
    assert len(census["retirements"]) == (0 if partial_state else 1)
    assert observer._controller_output_observed == expected
    assert observer._controller_output_reconciled == expected
    accounting = observer.boundary.accounting_document()
    assert accounting["observed_lower_bound"]["condition"]["output_bytes"] == expected
    assert accounting["reserved_upper_bound"]["condition"]["output_bytes"] >= expected


@pytest.mark.parametrize(
    ("exit_code", "sessions", "accepted"),
    [(1, 0, True), (0, 0, False), (1, 1, True), (0, 1, True), (1, 2, False)],
)
def test_r2_raw_completion_requires_session_unless_sealed_process_failed(
    tmp_path, exit_code, sessions, accepted
):
    """Exercise the exact-byte reader on a labelled synthetic raw-seal fixture.

    The joined send-loss case supplies full producer/export/cleanup qualification;
    this component isolates missing/ambiguous-session and exit-tampering rejection.
    No source validator or completion consumer is replaced.
    """
    from giclab.control.production import _host_module

    host = _host_module(ROOT)
    contract = V16_PROVIDER_CONTRACT
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "host-cleanup-receipt.json").write_bytes(canonical_bytes({"returncode": exit_code}))
    if sessions:
        (raw / "sira-output").mkdir()
        for index in range(sessions):
            (raw / "sira-output" / f"session-{index}.json").write_bytes(
                canonical_bytes(
                    {
                        "is_complete": True,
                        "history": [[{}, "send_msg_to_user('partial fixture answer')"]],
                        "error": "",
                    }
                )
            )
    files, total = host._raw_attempt_files(raw)
    common = {
        "schema_version": "0.1.0",
        "plan_id": contract.plan_id,
        "host_run_id": contract.host_run_id,
        "provider_contract_version": contract.version,
        "run_id": contract.run_ids[0],
    }
    manifest = {
        **common,
        "package_commit": "a" * 40,
        "raw_attempt_root": "raw",
        "files": files,
        "total_bytes": total,
    }
    manifest_path = tmp_path / "raw-attempt-manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    (tmp_path / "raw-attempt-complete.json").write_bytes(
        canonical_bytes(
            {
                **common,
                "raw_attempt_complete": True,
                "empirical_attempt_consumed": True,
                "raw_manifest_sha256": host.file_sha256(manifest_path),
                "raw_total_bytes": total,
                "raw_file_count": len(files),
                "condition_retry_permitted": False,
            }
        )
    )
    arguments = dict(attempt_root=tmp_path, run_id=contract.run_ids[0], package_commit="a" * 40)
    if not accepted:
        with pytest.raises(host.T09HostError, match="exactly one sealed session"):
            host.read_retained_condition_completion(**arguments, exit_code=exit_code)
    else:
        result = host.read_retained_condition_completion(**arguments, exit_code=exit_code)
        assert result["process_exit_code"] == exit_code
        assert result["completed"] is bool(sessions)
        assert result["answer"] == ("partial fixture answer" if sessions else None)
        assert (result["source_session"] is None) is (sessions == 0)
        with pytest.raises(host.T09HostError, match="exit differs from sealed evidence"):
            host.read_retained_condition_completion(**arguments, exit_code=exit_code + 1)
    assert host._raw_attempt_files(raw) == (files, total)
